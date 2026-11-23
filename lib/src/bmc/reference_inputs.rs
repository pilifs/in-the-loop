//! Direct parameters of type T[] for a final, flat application class T. Each non-null
//! cell can point to any earlier allocation or to a fresh object with independent int fields.

use super::{choice, Array, Bits, Blaster, Lit, Obj, Val, TRUE};
use crate::classfile::{flags, Insn, Kind, Type};
use crate::classpath::ClassPath;
use crate::jbmc::ObjectCell;
use std::collections::BTreeMap;

pub(crate) fn component(ty: &Type) -> Option<&str> {
    match ty {
        Type::Array(element) => match element.as_ref() {
            Type::Object(name) if name != "java/lang/String" => Some(name),
            _ => None,
        },
        _ => None,
    }
}

pub(crate) struct Shape {
    class: String,
    fields: Vec<String>,
}

/// Check the actual component bytes. A subclass, inherited state, static initialization or
/// a constructor with effects would require a different object factory and replay.
pub(crate) fn shape(cp: &ClassPath, params: &[Type], bound: u32) -> Result<Option<Shape>, String> {
    let Some(class) = params.iter().find_map(component) else { return Ok(None) };
    if params.iter().filter(|t| !t.is_primitive()).count() != 1 {
        return Err("a direct object-array input together with another reference parameter: sharing between their heaps is not supported".into());
    }
    // Each pair of cells can be an alias. Refuse before building the quadratic choice table.
    if bound > 32 {
        return Err(format!("a direct {class}[] input of bound {bound}: the native object factory supports up to 32 cells"));
    }
    let Some(cf) = cp.application(class).map_err(|e| e.to_string())? else {
        return Err(format!("the component of {class}[] is not an application class"));
    };
    if !cf.is_final() || cf.is_abstract() || cf.super_class.as_deref() != Some("java/lang/Object")
        || !cf.interfaces.is_empty() || cf.method("<clinit>", "()V").is_some() {
        return Err(format!("the component of {class}[] must be a concrete final direct subclass of Object with no interfaces or class initializer"));
    }
    let ctor = cf.method("<init>", "()V").filter(|m| !m.is_private()).and_then(|m| m.code.as_ref());
    let trivial = ctor.filter(|code| code.exception_table.is_empty()).and_then(|code| code.instructions().ok())
        .is_some_and(|insns| matches!(insns.as_slice(),
            [(_, Insn::Load(Kind::Ref, 0)), (_, Insn::InvokeSpecial(i)), (_, Insn::Return(None))]
            if cf.pool.member(*i).is_ok_and(|m| m.owner == "java/lang/Object" && m.name == "<init>" && m.descriptor == "()V")));
    if !trivial {
        return Err(format!("the component of {class}[] needs a package-accessible no-argument constructor that only calls Object()"));
    }
    let mut fields = Vec::new();
    for f in cf.fields.iter().filter(|f| !f.is_static()) {
        if f.descriptor != "I" || f.is_final() || f.access & flags::PRIVATE != 0 {
            return Err(format!("{class}.{}:{} is outside direct array inputs with writable, package-accessible int fields", f.name, f.descriptor));
        }
        fields.push(f.name.clone());
    }
    Ok(Some(Shape { class: class.into(), fields }))
}

pub(super) struct InputArray {
    pub slot: u32,
    length: Bits,
    // Per index, guards select null or an index into the original, unmodified field vectors.
    choices: Vec<Vec<(Lit, Option<usize>)>>,
    fields: Vec<BTreeMap<String, Bits>>,
}

impl InputArray {
    pub(super) fn field_words(&self) -> impl Iterator<Item = &Bits> {
        self.fields.iter().flat_map(BTreeMap::values)
    }

    pub(super) fn allocate(shape: &Shape, slot: u32, length: Bits, bound: u32, b: &mut Blaster, objects: &mut Vec<Obj>) -> Self {
        let first = objects.len();
        let mut input = Self { slot, length: length.clone(), choices: Vec::new(), fields: Vec::new() };
        let mut refs = Vec::new();
        for index in 0..bound as usize {
            let mut object = Obj::new(&shape.class);
            let fields: BTreeMap<_, _> = shape.fields.iter().map(|name| (name.clone(), b.fresh(32))).collect();
            object.fields = fields.iter().map(|(name, bits)| (name.clone(), Val::I(bits.clone()))).collect();
            objects.push(object);
            input.fields.push(fields);

            let mut remaining = TRUE;
            let mut picks = Vec::new();
            for node in std::iter::once(None).chain((0..index).map(Some)) {
                let take = b.var();
                picks.push((b.and(remaining, take), node));
                remaining = b.and(remaining, -take);
            }
            picks.push((remaining, Some(index)));
            refs.push(choice(b, picks.iter().map(|&(guard, node)| (guard, node.map(|i| first + i))).collect()));
            input.choices.push(picks);
        }
        let element = Type::Object(shape.class.clone());
        let descriptor = format!("[{}", element.descriptor());
        objects.push(Obj { array: Some(Array { element, length, refs, cells: Vec::new() }), ..Obj::new(&descriptor) });
        input
    }

    /// Name each object by its first live cell. A later cell can select a previously
    /// allocated object even if its nominal first cell was null or chose another object.
    pub(super) fn witness(&self, b: &Blaster) -> Vec<String> {
        let mut first = BTreeMap::new();
        self.choices.iter().take(b.eval(&self.length) as usize).enumerate().map(|(i, picks)| {
            let node = picks.iter().find(|(guard, _)| b.value(*guard)).expect("exhaustive cell choices").1;
            let cell = match node {
                None => ObjectCell::Null,
                Some(node) => match first.get(&node) {
                    Some(&index) => ObjectCell::Same { index },
                    None => {
                        first.insert(node, i);
                        ObjectCell::Object { fields: self.fields[node].iter().map(|(name, bits)| (name.clone(), b.eval(bits) as i32)).collect() }
                    }
                },
            };
            serde_json::to_string(&cell).expect("an object cell is JSON")
        }).collect()
    }
}
