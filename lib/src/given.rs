//! A parameter of an interface type, given an implementation: where a method under proof takes an object of an
//! application interface (`WebMvcTags.method(HttpServletRequest request)`), the check makes one of a class it
//! generates, which implements the interface's accessors and nothing else.
//!
//! An **accessor** ([`accessors`]) is an abstract method of the interface, or of an interface it extends, that
//! takes no parameter and returns an integral or boolean primitive or a `String`: `getMethod()`, `getServerPort()`,
//! `isSecure()`. The generated class ([`Given`]) answers the accessors the target may call
//! ([`crate::bmc::gaps::calls_on_given`], the gap scan's walk): it has a final field per accessor, set by its one
//! constructor and returned by the accessor, so an object of it is *an implementation that answers each of those
//! accessors with one value, the same on every call*: any value of a primitive, and any String the check's bound
//! admits, never null. That is the domain a result over it claims, and the domain line says so. It is a class made by
//! its constructor like any other ([`crate::harness::RecordType`]), so the accessors' values are the harness's
//! symbolic inputs, a witness names them, and the interpreter and a JVM replay the same class file the checker ran.
//!
//! Every other method of the interface is left as the interface has it. A default method runs as written. An
//! abstract one the class doesn't implement (one that takes arguments or returns an object, `getHeader(String)`,
//! `getSession()`, or an accessor the walk did not see called) has no answer here: a target that calls one meets it
//! as the call of a method with no body: a gap, which the own checker refuses by name under strict gaps and otherwise
//! assumes with the assumption named in the verdict, and which a JVM throws `AbstractMethodError` from, so a check
//! never passes over it silently.
//!
//! The same accessors are how an interface's object is read ([`crate::equivalence::fields_of`]): a property's
//! expressions call them (`result.getKey().equals("method")`), and a regression check compares two versions' results
//! of an interface type by them.

use crate::classfile::writer::{ClassWriter, CodeBuilder, FieldWriter, MethodWriter};
use crate::classfile::{flags, Kind, Type};
use crate::classpath::ClassPath;
use crate::harness::{FieldKind, Fields, RecordType};
use crate::Error;

/// The package the generated classes are in: `given/javax/servlet/http/HttpServletRequest` implements
/// `javax/servlet/http/HttpServletRequest`. Their own, so that no class of the application's packages is added to.
pub const PACKAGE: &str = "given";

/// Whether a method of an interface returning `t` and taking nothing is an accessor: its value is one the checks
/// make, a primitive of the own checker's fragment or a String.
fn is_value(t: &Type) -> bool {
    matches!(t, Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int | Type::Long) || crate::values::is_string(t)
}

/// The accessors of the application interface `interface` (an internal name), each with its return type: its own
/// in declaration order, then those of the interfaces it extends, in order, each method once.
pub fn accessors(cp: &ClassPath, interface: &str) -> Result<Vec<(String, Type)>, Error> {
    let mut out: Vec<(String, Type)> = Vec::new();
    let mut seen = Vec::new();
    let mut waiting = std::collections::VecDeque::from([interface.to_string()]);
    while let Some(name) = waiting.pop_front() {
        if seen.contains(&name) {
            continue;
        }
        seen.push(name.clone());
        let Some(cf) = cp.application(&name)? else { continue };
        for m in cf.methods.iter().filter(|m| m.is_abstract() && !m.is_static()) {
            let d = m.parsed_descriptor()?;
            if d.params.is_empty() && is_value(&d.ret) && !out.iter().any(|(n, _)| *n == m.name) {
                out.push((m.name.clone(), d.ret));
            }
        }
        waiting.extend(cf.interfaces.iter().cloned());
    }
    Ok(out)
}

/// The abstract methods of `interface` that are no accessor, each as `name(descriptor)`: what reading an object
/// through its accessors leaves unread. A method an interface nearer to `interface` declares (a default that
/// implements its parent's abstract method) is that one's.
pub fn unread(cp: &ClassPath, interface: &str) -> Result<Vec<String>, Error> {
    let mut out = Vec::new();
    let mut declared: Vec<(String, String)> = Vec::new();
    let mut seen = Vec::new();
    let mut waiting = std::collections::VecDeque::from([interface.to_string()]);
    while let Some(name) = waiting.pop_front() {
        if seen.contains(&name) {
            continue;
        }
        seen.push(name.clone());
        let Some(cf) = cp.application(&name)? else { continue };
        for m in cf.methods.iter().filter(|m| !m.is_static()) {
            let key = (m.name.clone(), m.descriptor.clone());
            if declared.contains(&key) {
                continue;
            }
            declared.push(key);
            let d = m.parsed_descriptor()?;
            if m.is_abstract() && !(d.params.is_empty() && is_value(&d.ret)) {
                out.push(format!("{}({}){}", m.name, d.params.iter().map(Type::java_name).collect::<Vec<_>>().join(", "), if d.ret == Type::Void { String::new() } else { format!(": {}", d.ret.java_name()) }));
            }
        }
        waiting.extend(cf.interfaces.iter().cloned());
    }
    Ok(out)
}

/// An interface's object as the checks read it: each accessor a pseudo-field named `getKey()`
/// ([`crate::harness::expr::accessor_name`]), a value or a String.
pub fn fields(cp: &ClassPath, interface: &str) -> Result<Fields, Error> {
    let fields = accessors(cp, interface)?.into_iter().map(|(name, t)| (crate::harness::expr::accessor_name(&name), if crate::values::is_string(&t) { FieldKind::String } else { FieldKind::Value(t) })).collect();
    Ok(Fields { class: interface.to_string(), fields })
}

/// The class generated for a parameter of an interface type.
#[derive(Debug, Clone)]
pub struct Given {
    /// The interface, an internal name.
    pub interface: String,
    /// The generated class's internal name, under [`PACKAGE`].
    pub class: String,
    /// The accessors it implements, each with its return type: the parameters of its constructor, in order.
    pub accessors: Vec<(String, Type)>,
    pub bytes: Vec<u8>,
}

impl Given {
    /// The implementation of `interface` in `cp` that answers its accessors among `called`, the methods the target
    /// may call on it by name and descriptor ([`crate::bmc::gaps::calls_on_given`]), in the interface's order.
    pub fn of(cp: &ClassPath, interface: &str, called: &std::collections::BTreeSet<(String, String)>) -> Result<Given, Error> {
        let accessors: Vec<(String, Type)> = accessors(cp, interface)?.into_iter().filter(|(name, t)| called.contains(&(name.clone(), format!("(){}", t.descriptor())))).collect();
        let class = format!("{PACKAGE}/{interface}");
        let bytes = generate(&class, interface, &accessors);
        Ok(Given { interface: interface.to_string(), class, accessors, bytes })
    }

    /// The same implementation for the previous version of a regression check, whose classes are under `prefix/`:
    /// `before/given/…`, implementing the interface as that version names it (`interface`, under the prefix too
    /// when the previous version has its own copy of it).
    pub fn before(&self, prefix: &str, interface: &str) -> Given {
        let class = format!("{prefix}/{}", self.class);
        Given { interface: interface.to_string(), bytes: generate(&class, interface, &self.accessors), class, accessors: self.accessors.clone() }
    }

    /// How the harness makes and reads an object of it: by the constructor, from one leaf per accessor, named as
    /// the accessor is (`request.getMethod`), passed as the interface and read through it.
    pub fn record(&self, cp: &ClassPath) -> Result<RecordType, Error> {
        // Read through the accessors it answers: another one has no answer to read.
        let mut read = fields(cp, &self.interface)?;
        read.fields.retain(|(name, _)| self.accessors.iter().any(|(a, _)| crate::harness::expr::accessor_name(a) == *name));
        let mut record = RecordType::made(&self.class, self.accessors.clone(), Vec::new(), read);
        record.given = Some(self.interface.clone());
        Ok(record)
    }

    /// Writes the class file under `dir`, a class path entry.
    pub fn write_to(&self, dir: &std::path::Path) -> Result<(), Error> {
        let path = dir.join(format!("{}.class", self.class));
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(path, &self.bytes)?;
        Ok(())
    }
}

/// The class `class` implementing `interface`: a private final field per accessor, a public constructor that takes
/// them in order, and each accessor returning its field. Straight-line code, so it needs no `StackMapTable`.
fn generate(class: &str, interface: &str, accessors: &[(String, Type)]) -> Vec<u8> {
    let mut writer = ClassWriter::new(class);
    writer.interfaces.push(interface.to_string());
    let object_init = writer.pool.method_ref("java/lang/Object", "<init>", "()V");
    let mut init = CodeBuilder::new();
    init.load(Kind::Ref, 0);
    init.op_u16(0xb7, object_init); // invokespecial
    let mut slot = 1;
    for (name, t) in accessors {
        let field = writer.pool.field_ref(class, name, &t.descriptor());
        writer.fields.push(FieldWriter { access: flags::PRIVATE | flags::FINAL, name: name.clone(), descriptor: t.descriptor() });
        let kind = kind_of(t);
        init.load(Kind::Ref, 0);
        init.load(kind, slot);
        init.op_u16(0xb5, field); // putfield
        slot += t.slots();
        let mut get = CodeBuilder::new();
        get.load(Kind::Ref, 0);
        get.op_u16(0xb4, field); // getfield
        get.return_(Some(kind));
        get.max_stack = 2;
        get.max_locals = 1;
        writer.methods.push(MethodWriter { access: flags::PUBLIC, name: name.clone(), descriptor: format!("(){}", t.descriptor()), code: Some(get) });
    }
    init.return_(None);
    init.max_stack = 3;
    init.max_locals = slot;
    let descriptor = format!("({})V", accessors.iter().map(|(_, t)| t.descriptor()).collect::<String>());
    writer.methods.insert(0, MethodWriter { access: flags::PUBLIC, name: "<init>".into(), descriptor, code: Some(init) });
    writer.to_bytes()
}

fn kind_of(t: &Type) -> Kind {
    match t {
        Type::Long => Kind::Long,
        Type::Object(_) | Type::Array(_) => Kind::Ref,
        _ => Kind::Int,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::classfile::ClassFile;

    /// An interface of `methods` (name, descriptor, abstract), extending `extends`, as a class file in `dir`.
    fn interface(dir: &std::path::Path, name: &str, extends: &[&str], methods: &[(&str, &str, bool)]) {
        let mut w = ClassWriter::new(name);
        w.access = flags::PUBLIC | flags::INTERFACE | flags::ABSTRACT;
        w.interfaces = extends.iter().map(|s| s.to_string()).collect();
        w.major = 52;
        for (m, d, is_abstract) in methods {
            let code = (!is_abstract).then(|| {
                let mut c = CodeBuilder::new();
                c.iconst(7);
                c.return_(Some(Kind::Int));
                c.max_stack = 1;
                c.max_locals = 1;
                c
            });
            w.methods.push(MethodWriter { access: flags::PUBLIC | if *is_abstract { flags::ABSTRACT } else { 0 }, name: m.to_string(), descriptor: d.to_string(), code });
        }
        let path = dir.join(format!("{name}.class"));
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(path, w.to_bytes()).unwrap();
    }

    #[test]
    fn an_interface_is_given_its_accessors_own_first_then_inherited_and_nothing_else() {
        let dir = crate::tla::tempfile_path("jvmcontract-given");
        interface(&dir, "web/Base", &[], &[("getPort", "()I", true), ("getName", "()Ljava/lang/String;", true), ("getRatio", "()D", true)]);
        interface(&dir, "web/Request", &["web/Base"], &[("getMethod", "()Ljava/lang/String;", true), ("getHeader", "(Ljava/lang/String;)Ljava/lang/String;", true), ("getSession", "()Ljava/lang/Object;", true), ("getName", "()Ljava/lang/String;", true), ("answer", "()I", false), ("isSecure", "()Z", true), ("getLength", "()J", true)]);
        let mut cp = ClassPath::new();
        cp.add(&dir).unwrap();
        // Its own in order, then the inherited ones it doesn't declare again; no method with a parameter, an object or
        // a floating-point result, or a body.
        let found = accessors(&cp, "web/Request").unwrap();
        assert_eq!(found.iter().map(|(n, t)| format!("{n}:{}", t.descriptor())).collect::<Vec<_>>(), ["getMethod:Ljava/lang/String;", "getName:Ljava/lang/String;", "isSecure:Z", "getLength:J", "getPort:I"]);
        // What reading it through its accessors leaves unread: each other abstract method, and none of an
        // interface whose abstract methods a nearer one gives a body (`Tag`'s `compareTo`).
        assert_eq!(unread(&cp, "web/Request").unwrap(), ["getHeader(java.lang.String): java.lang.String", "getSession(): java.lang.Object", "getRatio(): double"]);
        interface(&dir, "web/Ordered", &[], &[("rank", "(Ljava/lang/Object;)I", true)]);
        interface(&dir, "web/Tag", &["web/Ordered"], &[("getKey", "()Ljava/lang/String;", true), ("rank", "(Ljava/lang/Object;)I", false)]);
        assert_eq!(unread(&cp, "web/Tag").unwrap(), Vec::<String>::new());
        assert_eq!(unread(&cp, "web/Ordered").unwrap(), ["rank(java.lang.Object): int"]);
        // The implementation answers the accessors the target may call, and no other method.
        let called: std::collections::BTreeSet<(String, String)> = [("getPort", "()I"), ("getMethod", "()Ljava/lang/String;"), ("getHeader", "(Ljava/lang/String;)Ljava/lang/String;"), ("isSecure", "()Z"), ("getLength", "()J"), ("getName", "()I")].iter().map(|(n, d)| (n.to_string(), d.to_string())).collect();
        let given = Given::of(&cp, "web/Request", &called).unwrap();
        assert_eq!(given.class, "given/web/Request");
        let cf = ClassFile::parse(&given.bytes).unwrap();
        assert_eq!(cf.interfaces, ["web/Request"]);
        assert_eq!(cf.methods.iter().map(|m| format!("{}{}", m.name, m.descriptor)).collect::<Vec<_>>(), ["<init>(Ljava/lang/String;ZJI)V", "getMethod()Ljava/lang/String;", "isSecure()Z", "getLength()J", "getPort()I"]);
        // Made by its constructor from a leaf per accessor, passed as the interface, read through those accessors.
        let record = given.record(&cp).unwrap();
        assert_eq!(record.declared(), "web/Request");
        assert_eq!(record.constructor(), "(Ljava/lang/String;ZJI)V");
        assert_eq!(record.components.iter().map(|(n, _)| n.as_str()).collect::<Vec<_>>(), ["getMethod", "isSecure", "getLength", "getPort"]);
        let fields = record.fields.clone().unwrap();
        assert_eq!((fields.class.as_str(), fields.fields.clone()), ("web/Request", vec![("getMethod()".to_string(), FieldKind::String), ("isSecure()".to_string(), FieldKind::Value(Type::Boolean)), ("getLength()".to_string(), FieldKind::Value(Type::Long)), ("getPort()".to_string(), FieldKind::Value(Type::Int))]));
        assert_eq!(record.given_part("request", 8), "request: an implementation of Request that answers getMethod() (a String of ≤ 8 code units, not null), isSecure() (a boolean), getLength() (a long) and getPort() (an int), each with one value on every call, and no other abstract method");
        // The previous version's, under its prefix, of the interface as that version names it.
        let before = given.before("before", "before/web/Request");
        let cf = ClassFile::parse(&before.bytes).unwrap();
        assert_eq!((cf.name.as_str(), cf.interfaces.clone()), ("before/given/web/Request", vec!["before/web/Request".to_string()]));
        // A target that calls no accessor is given an implementation that answers nothing.
        let none = Given::of(&cp, "web/Request", &Default::default()).unwrap();
        assert_eq!(ClassFile::parse(&none.bytes).unwrap().methods.iter().map(|m| format!("{}{}", m.name, m.descriptor)).collect::<Vec<_>>(), ["<init>()V"]);
        assert_eq!(none.record(&cp).unwrap().given_part("request", 8), "request: an implementation of Request that answers none of its abstract methods");
        std::fs::remove_dir_all(&dir).ok();
    }
}
