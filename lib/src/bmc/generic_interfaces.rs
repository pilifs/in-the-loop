//! Resolve concrete, top-level interface signatures on an application class mirror.
//! Each parameterized type and its argument storage belong to the declaring class's
//! repository. The public arrays are fresh copies. The implementation's own bytecode
//! computes equality, hashing and the public projections from its real fields.
use super::*;
use crate::classfile::{ClassFile, MemberRef};

const CLASS: &str = "java/lang/Class";
const TYPE: &str = "java/lang/reflect/Type";
const PARAMETERIZED: &str = "sun/reflect/generics/reflectiveObjects/ParameterizedTypeImpl";
const CACHE: &str = "<JDK.genericInterfaces>";

fn identifier(name: &str) -> bool {
    !name.is_empty() && !name.as_bytes()[0].is_ascii_digit()
        && name.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_')
}

// The reflective constructor asks its raw declaration for its type parameters.
// Admit only declarations whose entire signature (including its bounds) can be
// resolved here. A wrong arity or malformed Signature must still be able to throw.
fn plain_arity(cf: &ClassFile) -> Option<usize> {
    let signature = cf.generic_signature()?;
    let formals = signature.strip_prefix('<')?.strip_suffix(">Ljava/lang/Object;")?;
    let mut names = std::collections::BTreeSet::new();
    let mut rest = formals;
    while !rest.is_empty() {
        let (name, tail) = rest.split_once(":Ljava/lang/Object;")?;
        if !identifier(name) || !names.insert(name) { return None; }
        rest = tail;
    }
    Some(names.len())
}

fn interfaces(cp: &ClassPath, cf: &ClassFile) -> Option<Vec<(String, Vec<String>)>> {
    let signature = cf.generic_signature()?;
    let mut rest = signature.strip_prefix("Ljava/lang/Object;")?;
    if cf.super_class.as_deref() != Some("java/lang/Object") || cf.interfaces.is_empty() { return None; }
    let mut result = Vec::new();
    for name in &cf.interfaces {
        let raw = cp.application(name).ok()??;
        if !name.split('/').all(identifier) || !raw.is_interface() || raw.outer_class().is_some() { return None; }
        rest = rest.strip_prefix('L')?.strip_prefix(name)?;
        let mut arguments = Vec::new();
        if let Some(mut tail) = rest.strip_prefix('<') {
            while !tail.starts_with('>') {
                let (arg, next) = tail.strip_prefix('L')?.split_once(';')?;
                if !arg.split('/').all(identifier) { return None; }
                let loaded = cp.load(arg).ok()??;
                if loaded.origin != crate::classpath::Origin::Jdk || !arg.starts_with("java/lang/")
                    || loaded.class.name != arg || loaded.class.outer_class().is_some() { return None; }
                arguments.push(arg.to_string());
                tail = next;
            }
            if arguments.is_empty() || arguments.len() != plain_arity(&raw)? { return None; }
            rest = tail.strip_prefix('>')?;
        }
        rest = rest.strip_prefix(';')?;
        result.push((name.clone(), arguments));
    }
    rest.is_empty().then_some(result)
}

impl Engine<'_> {
    fn reflective_type_array(&self, path: &mut Path, refs: Vec<Val>) -> usize {
        let id = self.alloc(path, "[Ljava/lang/reflect/Type;");
        path.objects[id].array = Some(Array { element: Type::Object(TYPE.into()), length: self.b.constant(refs.len() as i64, 32),
            cells: vec![], refs });
        id
    }

    pub(super) fn generic_interface_call(&mut self, path: &mut Path, o: usize, m: &MemberRef, args: &[Val]) -> Option<Step> {
        if path.objects[o].class == PARAMETERIZED && path.objects[o].fields.contains_key(CACHE) {
            if (m.owner.as_str(), m.name.as_str(), m.descriptor.as_str()) == ("java/lang/Object", "getClass", "()Ljava/lang/Class;") {
                let class = self.literal(path, Literal::Class(PARAMETERIZED.into()), CLASS);
                self.push(path, Val::R(Some(class)));
                self.advance(path);
                return Some(Ok(None));
            }
            if !self.cp.is_subtype(PARAMETERIZED, &m.owner) || self.cp.find_method(&m.owner, &m.name, &m.descriptor).is_none()
                || !matches!((m.name.as_str(), m.descriptor.as_str()),
                    ("getRawType" | "getOwnerType", "()Ljava/lang/reflect/Type;") |
                    ("getRawType", "()Ljava/lang/Class;") |
                    ("getActualTypeArguments", "()[Ljava/lang/reflect/Type;") |
                    ("equals", "(Ljava/lang/Object;)Z") | ("hashCode", "()I")) { return None; }
            let (cf, method) = self.cp.find_method(PARAMETERIZED, &m.name, &m.descriptor)?;
            if cf.name != PARAMETERIZED { return None; }
            let mut full = vec![Val::R(Some(o))];
            full.extend_from_slice(args);
            return Some(self.enter_method(path, &m.owner, cf, method, full));
        }
        if (m.owner.as_str(), m.name.as_str(), m.descriptor.as_str()) != (CLASS, "getGenericInterfaces", "()[Ljava/lang/reflect/Type;")
            || !self.cp.generic_interface_image() || self.gap_mode != GapMode::Strict
            || self.previous.is_some() || !self.contracts.is_empty() { return None; }
        let declaring = self.class_named(path, o)?;
        let cf = self.cp.application(&declaring).ok().flatten();
        let Some(description) = cf.as_ref().and_then(|cf| interfaces(self.cp, cf)) else {
            let calls = path.frames.iter().rev().take(6).map(|f| site(f).display()).collect::<Vec<_>>();
            return Some(unsupported(format!("Class.getGenericInterfaces on {} with {} at {}", declaring.replace('/', "."),
                cf.and_then(|c| c.generic_signature()).as_deref().unwrap_or("no bound application Signature"), calls.join(" called by "))));
        };
        if let Err(stop) = self.keeps(path, None, "consults the class mirror's generic repository") { return Some(Err(stop)); }
        self.assumed.insert(runtime::CLASS_PATH_ASSUMPTION.into());
        let refs = if let Some(Val::R(Some(storage))) = path.objects[o].fields.get(CACHE) {
            path.objects[*storage].as_array()?.refs.clone()
        } else {
            let mut refs = Vec::new();
            for (name, args) in description {
                let raw = self.literal(path, Literal::Class(name), CLASS);
                if args.is_empty() {
                    refs.push(Val::R(Some(raw)));
                } else {
                    let arguments = args.into_iter().map(|a| Val::R(Some(self.literal(path, Literal::Class(a), CLASS)))).collect();
                    let storage = self.reflective_type_array(path, arguments);
                    let ty = self.alloc(path, PARAMETERIZED);
                    path.objects[ty].fields.extend([(CACHE.into(), Val::I(self.b.constant(1, 32))),
                        ("actualTypeArguments".into(), Val::R(Some(storage))), ("rawType".into(), Val::R(Some(raw))),
                        ("ownerType".into(), Val::R(None))]);
                    refs.push(Val::R(Some(ty)));
                }
            }
            let storage = self.reflective_type_array(path, refs.clone());
            path.objects[o].fields.insert(CACHE.into(), Val::R(Some(storage)));
            refs
        };
        let copy = self.reflective_type_array(path, refs);
        self.push(path, Val::R(Some(copy)));
        self.advance(path);
        Some(Ok(None))
    }
}
