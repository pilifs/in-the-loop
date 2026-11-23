//! Bounded direct reference arrays. A cell may hold null, share another cell's object,
//! or refer to a fresh flat application object or a fresh primitive row.

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

pub(crate) fn row_element(ty: &Type) -> Option<&Type> {
    let Type::Array(row) = ty else { return None };
    let Type::Array(element) = row.as_ref() else { return None };
    matches!(element.as_ref(), Type::Int | Type::Long).then_some(element)
}

pub(crate) fn heap_array(ty: &Type) -> bool {
    component(ty).is_some() || row_element(ty).is_some()
}

pub(crate) enum Shape {
    Object { class: String, fields: Vec<String> },
    Rows(Type),
}

/// An application component needs a qualified constructor. Primitive rows
/// instead receive independent lengths and complete signed cell domains.
pub(crate) fn shape(cp: &ClassPath, params: &[Type], bound: u32) -> Result<Option<Shape>, String> {
    let Some(ty) = params.iter().find(|t| heap_array(t)) else { return Ok(None) };
    if params.iter().filter(|t| !t.is_primitive()).count() != 1 {
        return Err("a direct object-array input together with another reference parameter: sharing between their heaps is not supported".into());
    }
    if bound > 32 {
        return Err(format!("a direct {} input of bound {bound}: the native object factory supports up to 32 cells", ty.java_name()));
    }
    if let Some(element) = row_element(ty) { return Ok(Some(Shape::Rows(element.clone()))); }
    let class = component(ty).expect("classified application component");
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
    Ok(Some(Shape::Object { class: class.into(), fields }))
}

enum InitialNode {
    Object(BTreeMap<String, Bits>),
    Row { element: Type, length: Bits, cells: Vec<Bits> },
}

pub(super) struct InputArray {
    pub slot: u32,
    length: Bits,
    // Per index, guards select null or an index into the original, unmodified field vectors.
    choices: Vec<Vec<(Lit, Option<usize>)>>,
    nodes: Vec<InitialNode>,
}

impl InputArray {
    pub(super) fn input_literals(&self, into: &mut Vec<Lit>) {
        into.extend_from_slice(&self.length);
        for options in &self.choices { into.extend(options.iter().map(|(guard, _)| *guard)); }
        for node in &self.nodes {
            match node {
                InitialNode::Object(fields) => into.extend(fields.values().flatten().copied()),
                InitialNode::Row { length, cells, .. } => {
                    into.extend_from_slice(length);
                    into.extend(cells.iter().flatten().copied());
                }
            }
        }
    }

    pub(super) fn stage_words(&self, values: &mut Vec<(Type, Bits)>) {
        for node in &self.nodes {
            match node {
                InitialNode::Object(fields) => values.extend(fields.values().map(|v| (Type::Int, v.clone()))),
                InitialNode::Row { element, cells, .. } => values.extend(cells.iter().map(|v| (element.clone(), v.clone()))),
            }
        }
    }

    pub(super) fn allocate(shape: &Shape, slot: u32, length: Bits, bound: u32, b: &mut Blaster, objects: &mut Vec<Obj>, cond: &mut Vec<Lit>) -> Self {
        let first = objects.len();
        let mut input = Self { slot, length: length.clone(), choices: Vec::new(), nodes: Vec::new() };
        let element = match shape { Shape::Object { class, .. } => Type::object(class),
            Shape::Rows(primitive) => Type::Array(Box::new(primitive.clone())) };
        let mut refs = Vec::new();
        for index in 0..bound as usize {
            let mut object = Obj::new(&super::class_of(&element));
            let node = match shape {
                Shape::Object { fields, .. } => {
                    let initial: BTreeMap<_, _> = fields.iter().map(|name| (name.clone(), b.fresh(32))).collect();
                    object.fields = initial.iter().map(|(name, bits)| (name.clone(), Val::I(bits.clone()))).collect();
                    InitialNode::Object(initial)
                }
                Shape::Rows(primitive) => {
                    let n = b.fresh(32);
                    cond.push(-b.ult(&b.constant(i64::from(bound), 32), &n));
                    let cells: Vec<_> = (0..bound).map(|_| b.fresh(super::cell_width(primitive))).collect();
                    object.array = Some(Array { element: primitive.clone(), length: n.clone(), refs: Vec::new(), cells: cells.clone() });
                    InitialNode::Row { element: primitive.clone(), length: n, cells }
                }
            };
            input.nodes.push(node);
            objects.push(object);

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
            let Some(node) = node else { return "null".into() };
            if let Some(&index) = first.get(&node) {
                return serde_json::to_string(&ObjectCell::Same { index }).expect("alias is JSON");
            }
            first.insert(node, i);
            match &self.nodes[node] {
                InitialNode::Object(fields) => serde_json::to_string(&ObjectCell::Object {
                    fields: fields.iter().map(|(name, bits)| (name.clone(), b.eval(bits) as i32)).collect(),
                }).expect("object fields are JSON"),
                InitialNode::Row { element, length, cells } => {
                    let values = cells[..b.eval(length) as usize].iter().map(|word| {
                        let n = b.eval(word);
                        if *element == Type::Long { serde_json::Value::String(n.to_string()) } else { serde_json::Value::from(n as i32) }
                    }).collect();
                    serde_json::Value::Array(values).to_string()
                }
            }
        }).collect()
    }
}
