//! Resolve concrete, top-level interface signatures on an application class mirror.
//! Each parameterized type and its argument storage belong to the declaring class's
//! repository. The public arrays are fresh copies. The implementation's own bytecode
//! computes equality, hashing and the public projections from its real fields.
use super::*;
use crate::classfile::{signature::Sig, ClassFile, MemberRef};

const CLASS: &str = "java/lang/Class";
const TYPE: &str = "java/lang/reflect/Type";
const PARAMETERIZED: &str = "sun/reflect/generics/reflectiveObjects/ParameterizedTypeImpl";
const WILDCARD: &str = "sun/reflect/generics/reflectiveObjects/WildcardTypeImpl";
const VARIABLE: &str = "sun/reflect/generics/reflectiveObjects/TypeVariableImpl";
const VARIABLE_INTERFACE: &str = "java/lang/reflect/TypeVariable";
const CACHE: &str = "<JDK.genericInterfaces>";

fn identifier(name: &str) -> bool {
    !name.is_empty() && !name.as_bytes()[0].is_ascii_digit()
        && name.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_')
}

fn collection_interface(cp: &ClassPath, name: &str) -> bool {
    matches!(name, "java/util/List" | "java/util/SequencedCollection" | "java/util/Collection" | "java/lang/Iterable")
        && cp.method_return_image()
}

fn declaration(cp: &ClassPath, name: &str) -> Option<Rc<ClassFile>> {
    cp.application(name).ok().flatten().or_else(|| {
        if !collection_interface(cp, name) { return None; }
        let loaded = cp.load(name).ok()??;
        (loaded.origin == crate::classpath::Origin::Jdk).then_some(loaded.class)
    })
}

// The reflective constructor asks its raw declaration for its type parameters.
// Admit only declarations whose entire signature (including its bounds) can be
// resolved here. A wrong arity or malformed Signature must still be able to throw.
fn plain_formals(cp: &ClassPath, cf: &ClassFile) -> Option<Vec<String>> {
    let signature = cf.generic_signature()?;
    let (formals, supers) = signature.strip_prefix('<')?.split_once('>')?;
    if supers != "Ljava/lang/Object;" && !collection_interface(cp, &cf.name) { return None; }
    let mut names = Vec::new();
    let mut rest = formals;
    while !rest.is_empty() {
        let (name, tail) = rest.split_once(":Ljava/lang/Object;")?;
        if !identifier(name) || names.iter().any(|n| n == name) { return None; }
        names.push(name.to_owned());
        rest = tail;
    }
    (!names.is_empty()).then_some(names)
}

#[derive(Debug)]
enum ReflectType {
    Class(String),
    Variable { declaration: String, name: String },
    Parameterized { raw: String, owner: Option<String>, arguments: Vec<ReflectType> },
    Wildcard { bound: Option<(bool, Box<ReflectType>)> },
}

/// Only a static member whose enclosing declaration agrees can have a raw Class owner here.
/// A local or anonymous type must not be assigned the nest host as a declaring class.
fn owner(cp: &ClassPath, raw: &ClassFile) -> Option<Option<String>> {
    if raw.outer_class().is_none() { return Some(None); }
    let members = raw.inner_classes().ok()?;
    let entry = members.iter().find(|m| m.inner == raw.name && m.access & crate::classfile::flags::STATIC != 0 && m.simple_name.is_some())?;
    let enclosing = entry.outer.as_ref()?;
    let outer = cp.application(enclosing).ok()??;
    outer.inner_classes().ok()?.contains(entry).then(|| Some(enclosing.clone()))
}

fn described(cp: &ClassPath, sig: &Sig, encoding: &mut String, allow_wildcard: bool, formals: Option<(&str, &[String])>) -> Option<ReflectType> {
    match sig {
        Sig::Class { name, args } => {
            if !name.split(['/', '$']).all(identifier) { return None; }
            let loaded = cp.load(name).ok()??;
            if loaded.class.name != *name { return None; }
            encoding.push('L');
            encoding.push_str(name);
            let ty = if args.is_empty() {
                ReflectType::Class(name.clone())
            } else {
                // Enum's F-bound resolves back to Enum<E> on the bound bootstrap image.
                let arity = if name == "java/lang/Enum" && loaded.origin == crate::classpath::Origin::Jdk && cp.wildcard_type_image() { 1 }
                    else { plain_formals(cp, &loaded.class)?.len() };
                if args.len() != arity { return None; }
                let owner = owner(cp, &loaded.class)?;
                encoding.push('<');
                let arguments = args.iter().map(|arg| described(cp, arg, encoding, true, formals)).collect::<Option<Vec<_>>>()?;
                encoding.push('>');
                ReflectType::Parameterized { raw: name.clone(), owner, arguments }
            };
            encoding.push(';');
            Some(ty)
        }
        Sig::Variable(name) => {
            let (declaration, params) = formals?;
            if !params.contains(name) { return None; }
            encoding.push('T');
            encoding.push_str(name);
            encoding.push(';');
            Some(ReflectType::Variable { declaration: declaration.to_owned(), name: name.clone() })
        }
        Sig::Wildcard(bound) if allow_wildcard && cp.wildcard_type_image() => {
            let bound = match bound {
                None => { encoding.push('*'); None }
                Some((upper, ty)) => {
                    encoding.push(if *upper { '+' } else { '-' });
                    Some((*upper, Box::new(described(cp, ty, encoding, false, formals)?)))
                }
            };
            Some(ReflectType::Wildcard { bound })
        }
        _ => None,
    }
}

fn interfaces(cp: &ClassPath, cf: &ClassFile) -> Option<Vec<ReflectType>> {
    let signature = cf.generic_signature()?;
    let (formals, supers) = if signature.starts_with('<') {
        (Some(plain_formals(cp, cf)?), signature.split_once('>')?.1)
    } else { (None, signature.as_str()) };
    let mut rest = supers.strip_prefix("Ljava/lang/Object;")?;
    if cf.super_class.as_deref() != Some("java/lang/Object")
        || rest.contains('[') || rest.matches('<').count() > 32 { return None; }
    let mut result = Vec::new();
    for name in &cf.interfaces {
        let raw = declaration(cp, name)?;
        if !raw.is_interface() { return None; }
        let (sig, tail) = crate::classfile::signature::parse_type_prefix(rest)?;
        if sig.class_name()? != name { return None; }
        let mut encoding = String::new();
        result.push(described(cp, &sig, &mut encoding, false, formals.as_deref().map(|names| (cf.name.as_str(), names)))?);
        // The general signature reader flattens owner arguments. Require exactly the
        // supported class-member encoding, including every delimiter and argument.
        if rest.strip_prefix(&encoding)? != tail { return None; }
        rest = tail;
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

    fn reify_interface_type(&mut self, path: &mut Path, ty: ReflectType) -> usize {
        match ty {
            ReflectType::Class(name) => self.literal(path, Literal::Class(name), CLASS),
            ReflectType::Variable { declaration, name } => self.class_variable(path, declaration, name),
            ReflectType::Parameterized { raw, owner, arguments } => {
                let arguments = arguments.into_iter().map(|t| Val::R(Some(self.reify_interface_type(path, t)))).collect();
                let args = self.reflective_type_array(path, arguments);
                let class = self.literal(path, Literal::Class(raw), CLASS);
                let owner = owner.map(|name| self.literal(path, Literal::Class(name), CLASS));
                let object = self.alloc(path, PARAMETERIZED);
                path.objects[object].fields.extend([(CACHE.into(), Val::I(self.b.constant(1, 32))),
                    ("actualTypeArguments".into(), Val::R(Some(args))), ("rawType".into(), Val::R(Some(class))),
                    ("ownerType".into(), Val::R(owner))]);
                object
            }
            ReflectType::Wildcard { bound } => {
                // Reify the bounds now. The pinned class tests their runtime array type and
                // returns a fresh clone, just as after its own lazy reification has finished.
                let mut lower = Vec::new();
                let upper = match bound {
                    Some((true, t)) => self.reify_interface_type(path, *t),
                    b => {
                        if let Some((false, t)) = b {
                            lower.push(Val::R(Some(self.reify_interface_type(path, *t))));
                        }
                        self.literal(path, Literal::Class("java/lang/Object".into()), CLASS)
                    }
                };
                let top = self.reflective_type_array(path, vec![Val::R(Some(upper))]);
                let bottom = self.reflective_type_array(path, lower);
                let object = self.alloc(path, WILDCARD);
                path.objects[object].fields.extend([(CACHE.into(), Val::I(self.b.constant(1, 32))),
                    ("upperBounds".into(), Val::R(Some(top))), ("lowerBounds".into(), Val::R(Some(bottom)))]);
                object
            }
        }
    }

    fn class_variable(&mut self, path: &mut Path, declaration: String, name: String) -> usize {
        let mirror = self.literal(path, Literal::Class(declaration), CLASS);
        let key = format!("<JDK.typeVariable.{name}>");
        if let Some(Val::R(Some(id))) = path.objects[mirror].fields.get(&key) { return *id; }
        let text = self.literal(path, Literal::Str(name.encode_utf16().collect()), STRING);
        let object = self.literal(path, Literal::Class("java/lang/Object".into()), CLASS);
        let bounds = self.reflective_type_array(path, vec![Val::R(Some(object))]);
        let variable = self.alloc(path, VARIABLE);
        path.objects[variable].fields.extend([(CACHE.into(), Val::I(self.b.constant(1, 32))),
            ("genericDeclaration".into(), Val::R(Some(mirror))), ("name".into(), Val::R(Some(text))),
            ("bounds".into(), Val::R(Some(bounds)))]);
        path.objects[mirror].fields.insert(key, Val::R(Some(variable)));
        variable
    }

    pub(super) fn generic_method_return(&mut self, path: &mut Path, copy: usize, declaring: &str, name: &str, ret: &Type) -> Option<Step> {
        if !self.cp.method_return_image() || !self.cp.generic_interface_image() || self.previous.is_some()
            || self.gap_mode != GapMode::Strict || !self.contracts.is_empty() { return None; }
        let cf = self.cp.application(declaring).ok()??;
        let method = cf.method(name, &format!("(){}", ret.descriptor()))?;
        let signature = method.generic_signature(&cf.pool)?;
        let text = signature.strip_prefix("()")?;
        if text.contains('[') || text.matches('<').count() > 32 { return None; }
        let formals = plain_formals(self.cp, &cf)?;
        let sig = crate::classfile::signature::parse_type(text)?;
        if ret != &Type::Object(sig.class_name()?.to_owned()) { return None; }
        let mut canonical = String::new();
        let description = described(self.cp, &sig, &mut canonical, false, Some((declaring, &formals)))?;
        if canonical != text { return None; }
        if let Err(stop) = self.keeps(path, None, "consults a reflective method repository") { return Some(Err(stop)); }
        let key = "<JDK.genericReturnType>";
        let id = if let Some(Val::R(Some(id))) = path.objects[copy].fields.get(key) { *id } else {
            let id = self.reify_interface_type(path, description);
            path.objects[copy].fields.insert(key.into(), Val::R(Some(id)));
            id
        };
        self.push(path, Val::R(Some(id)));
        self.advance(path);
        Some(Ok(None))
    }

    pub(super) fn generic_interface_call(&mut self, path: &mut Path, o: usize, m: &MemberRef, args: &[Val]) -> Option<Step> {
        let implementation = path.objects[o].class.clone();
        if matches!(implementation.as_str(), PARAMETERIZED | WILDCARD | VARIABLE) && path.objects[o].fields.contains_key(CACHE) {
            if (m.owner.as_str(), m.name.as_str(), m.descriptor.as_str()) == ("java/lang/Object", "getClass", "()Ljava/lang/Class;") {
                let class = self.literal(path, Literal::Class(implementation), CLASS);
                self.push(path, Val::R(Some(class)));
                self.advance(path);
                return Some(Ok(None));
            }
            if !self.cp.is_subtype(&implementation, &m.owner) || self.cp.find_method(&m.owner, &m.name, &m.descriptor).is_none()
                || !matches!((m.name.as_str(), m.descriptor.as_str()),
                    ("getRawType" | "getOwnerType", "()Ljava/lang/reflect/Type;") |
                    ("getRawType", "()Ljava/lang/Class;") |
                    ("getName", "()Ljava/lang/String;") |
                    ("getGenericDeclaration", "()Ljava/lang/reflect/GenericDeclaration;") |
                    ("getActualTypeArguments" | "getUpperBounds" | "getLowerBounds" | "getBounds", "()[Ljava/lang/reflect/Type;") |
                    ("equals", "(Ljava/lang/Object;)Z") | ("hashCode", "()I")) { return None; }
            let (cf, method) = self.cp.find_method(&implementation, &m.name, &m.descriptor)?;
            if cf.name != implementation { return None; }
            let mut full = vec![Val::R(Some(o))];
            full.extend_from_slice(args);
            return Some(self.enter_method(path, &m.owner, cf, method, full));
        }
        if (m.owner.as_str(), m.name.as_str(), m.descriptor.as_str()) == (CLASS, "getTypeParameters", "()[Ljava/lang/reflect/TypeVariable;")
            && self.cp.method_return_image() && self.previous.is_none() && self.gap_mode == GapMode::Strict && self.contracts.is_empty() {
            let declaring = self.class_named(path, o)?;
            let cf = declaration(self.cp, &declaring)?;
            let formals = plain_formals(self.cp, &cf)?;
            if let Err(stop) = self.keeps(path, None, "consults the class mirror's type-variable repository") { return Some(Err(stop)); }
            self.assumed.insert(runtime::CLASS_PATH_ASSUMPTION.into());
            let refs: Vec<_> = formals.into_iter().map(|n| Val::R(Some(self.class_variable(path, declaring.clone(), n)))).collect();
            let copy = self.alloc(path, "[Ljava/lang/reflect/TypeVariable;");
            path.objects[copy].array = Some(Array { element: Type::Object(VARIABLE_INTERFACE.into()), length: self.b.constant(refs.len() as i64, 32),
                cells: vec![], refs });
            self.push(path, Val::R(Some(copy)));
            self.advance(path);
            return Some(Ok(None));
        }
        if (m.owner.as_str(), m.name.as_str(), m.descriptor.as_str()) != (CLASS, "getGenericInterfaces", "()[Ljava/lang/reflect/Type;")
            || !self.cp.generic_interface_image() || self.gap_mode != GapMode::Strict
            || self.previous.is_some() || !self.contracts.is_empty() { return None; }
        let declaring = self.class_named(path, o)?;
        let cf = declaration(self.cp, &declaring);
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
            let refs: Vec<Val> = description.into_iter().map(|ty| Val::R(Some(self.reify_interface_type(path, ty)))).collect();
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
