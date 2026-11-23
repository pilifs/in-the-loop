//! A lookup on a class literal reads the loaded application class file. The selected JDK
//! returns a fresh reflective copy. Only the metadata of that copy is available to the caller.
use super::*;
use crate::classfile::{flags, ClassFile, MemberRef};

const CLASS: &str = "java/lang/Class";
const METHOD: &str = "java/lang/reflect/Method";
const FIELD: &str = "java/lang/reflect/Field";

#[derive(Debug, PartialEq, Eq)]
pub(super) struct Member {
    owner: String,
    name: String,
    modifiers: u16,
    ty: Type,
}

// getDeclaredFields0 and getDeclaredMethods0 also resolve types of the *other* declarations.
// Restrict their entire tables, so an unavailable parameter, return or exception type cannot disappear.
fn bootstrap_type(ty: &Type) -> bool {
    match ty {
        Type::Object(name) => matches!(name.as_str(), "java/lang/String" | "java/lang/Object"),
        Type::Array(element) => bootstrap_type(element),
        _ => true,
    }
}

fn plain_declarations(cf: &ClassFile) -> bool {
    cf.is_final() && cf.interfaces.is_empty()
        && matches!(cf.super_class.as_deref(), Some("java/lang/Object" | "java/lang/Record"))
        && cf.fields.iter().all(|f| Type::parse(&f.descriptor).is_ok_and(|t| bootstrap_type(&t)))
        && cf.methods.iter().all(|m| m.attributes.iter().all(|a| a.name != "Exceptions")
            && m.parsed_descriptor().is_ok_and(|d| bootstrap_type(&d.ret) && d.params.iter().all(bootstrap_type)))
}

impl Engine<'_> {
    pub(super) fn reflection_method(&mut self, path: &mut Path, o: usize, call: &MemberRef, args: &[Val]) -> Option<Step> {
        let (name, desc) = (call.name.as_str(), call.descriptor.as_str());
        if let Some(member) = path.objects[o].member.clone() {
            if !matches!(call.owner.as_str(), METHOD | FIELD | "java/lang/reflect/Executable" | "java/lang/reflect/Member")
                || !self.cp.is_subtype(&path.objects[o].class, &call.owner)
                || self.cp.find_method(&call.owner, name, desc).is_none() { return None; }
            let value = match (name, desc) {
                ("getName", "()Ljava/lang/String;") => {
                    let text = self.literal(path, Literal::Str(member.name.encode_utf16().collect()), STRING);
                    Val::R(Some(text))
                }
                ("getModifiers", "()I") => Val::I(self.b.constant(i64::from(member.modifiers), 32)),
                ("getParameterCount", "()I") if path.objects[o].class == METHOD => Val::I(self.b.constant(0, 32)),
                ("getDeclaringClass", "()Ljava/lang/Class;") =>
                    Val::R(Some(self.literal(path, Literal::Class(member.owner.clone()), CLASS))),
                ("getReturnType", "()Ljava/lang/Class;") if path.objects[o].class == METHOD => {
                    let key = if member.ty.is_reference() { Literal::Class(class_of(&member.ty)) }
                        else { Literal::PrimitiveClass(member.ty.descriptor()) };
                    Val::R(Some(self.literal(path, key, CLASS)))
                }
                _ => return None,
            };
            self.push(path, value);
            self.advance(path);
            return Some(Ok(None));
        }
        let method = match (call.owner.as_str(), name, desc) {
            (CLASS, "getMethod", "(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;") => true,
            (CLASS, "getDeclaredField", "(Ljava/lang/String;)Ljava/lang/reflect/Field;") => false,
            _ => return None,
        };
        if !self.cp.reflection_copies() || !self.cp.is_application(&path.frames.last()?.class.name) { return None; }
        let declaring = self.class_named(path, o)?;
        let cf = self.cp.application(&declaring).ok()??;
        if !plain_declarations(&cf) { return None; }
        let Val::R(Some(text)) = args.first()? else { return None };
        let member_name = String::from_utf16(&self.constant_units(path, *text)?).ok()?;
        // On the bound image a non-proxy class and a caller from the same application loader
        // require neither a declared-member permission nor a package check.
        self.assumed.insert(runtime::CLASS_PATH_ASSUMPTION.to_owned());
        let (modifiers, ty) = if method {
            let [_, Val::R(Some(types))] = args else { return None };
            let array = path.objects[*types].as_array()?;
            if self.b.constant_value(&array.length) != Some(0) || member_name.starts_with('<') { return None; }
            let mut candidates = cf.methods.iter().filter(|m| m.name == member_name && m.is_public() && m.descriptor.starts_with("()"));
            let m = candidates.next()?;
            if candidates.next().is_some() || m.access & !(flags::PUBLIC | flags::FINAL | flags::STATIC) != 0 { return None; }
            (m.access, m.parsed_descriptor().ok()?.ret)
        } else {
            let mut matches = cf.fields.iter().filter(|f| f.name == member_name);
            let Some(f) = matches.next() else { return Some(self.missing_declared_field(path, *text)); };
            if matches.next().is_some() { return None; }
            (f.access, Type::parse(&f.descriptor).ok()?)
        };
        let copy = self.alloc(path, if method { METHOD } else { FIELD });
        path.objects[copy].member = Some(Rc::new(Member { owner: declaring, name: member_name, modifiers, ty }));
        path.objects[copy].unknown = true; // other VM fields were never supplied
        self.push(path, Val::R(Some(copy)));
        self.advance(path);
        Some(Ok(None))
    }
}
