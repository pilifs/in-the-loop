//! The gaps of the tool's own checker: what in the bytecode a method reaches the engine does not implement as the
//! JVM does, found statically, before anything is proved.
//!
//! Each [`Gap`] is a construct the engine ([`super`]) approximates today rather than refuses:
//!
//! | [`GapKind`] | What the engine does | What the JVM does |
//! |---|---|---|
//! | `jdk-constructor` | skips a JDK constructor | runs it, and it may throw (`new ArrayList<>(-1)`) or keep its arguments |
//! | `jdk-void-method` | does nothing for a `void` JDK instance method | runs it, and it may mutate its receiver or arguments, or throw |
//! | `jdk-reference-method` | returns a fresh non-null object for a JDK instance method returning a reference | may return null or an object that exists already, or throw |
//! | `monitor` | pops the operand of `monitorenter`/`monitorexit` | throws `NullPointerException` on null |
//! | `hidden-field` | keys an object's fields by name alone | a field declared again by a subclass is a second field |
//! | `literal-identity` | makes each `ldc` of a string or class a fresh object | one object per distinct literal, so `==` on two loads of it is true |
//! | `class-initializer` | never runs a `<clinit>` | runs it on first use, and it may throw or set state |
//! | `string-conversion` | makes a string concatenation a fresh string without converting its arguments | calls `toString` on an object argument, which may throw (bytecode of javac 9 to 18: from 19 on, javac calls `String.valueOf` first, which the engine refuses) |
//!
//! A JDK call the engine reproduces exactly is not a gap: `Object.<init>`, `Record.<init>`, the constructors of the
//! JDK's exceptions that take no argument or a message (and a cause), which change nothing the proof observes, and
//! the static JDK methods it models ([`super::models_jdk_static`]). The scan counts those it relied on.
//! A construct the engine refuses (floating point, a static field written, an array of references, a primitive
//! result of a JDK instance method, ...) is not a gap either: it ends the proof with no verdict, as it should.
//! The scan lists those reasons too, since a method that has one is outside the engine whatever its gaps.
//!
//! [`scan`] walks the methods a set of roots may reach, as the engine resolves them: the application's own methods
//! (with every override an application class declares, since the receiver's class picks one), and the static
//! methods of the tool's models. It reads every instruction of each, so it may report a gap on a path no input
//! takes, and a literal is a gap wherever the code walked also compares references at all (an enum compared with
//! `==`, say), since which references meet at an `if_acmp` is a question for the paths. The harness itself, and the
//! expressions of a property or relation compiled into it, are not walked. Step 1a of
//! `llm-dlc/loops/sound-verdicts.md`: what strictness would cost each recorded example.

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::fmt::Write as _;

use serde::Serialize;

use crate::classfile::{BootstrapArg, Insn, Kind, MemberRef, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::Error;

/// What kind of construct a gap is.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum GapKind {
    JdkConstructor,
    JdkVoidMethod,
    JdkReferenceMethod,
    Monitor,
    HiddenField,
    LiteralIdentity,
    ClassInitializer,
    StringConversion,
}

impl GapKind {
    pub fn name(self) -> &'static str {
        match self {
            GapKind::JdkConstructor => "jdk-constructor",
            GapKind::JdkVoidMethod => "jdk-void-method",
            GapKind::JdkReferenceMethod => "jdk-reference-method",
            GapKind::Monitor => "monitor",
            GapKind::HiddenField => "hidden-field",
            GapKind::LiteralIdentity => "literal-identity",
            GapKind::ClassInitializer => "class-initializer",
            GapKind::StringConversion => "string-conversion",
        }
    }
}

/// One gap: the kind, and the member it is about (a call, a field, a class's initializer, a literal's class).
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Gap {
    pub kind: GapKind,
    /// The class, internal name.
    pub owner: String,
    /// The method or field, or empty for a literal or a monitor.
    pub name: String,
    /// The JVM descriptor, or empty.
    pub descriptor: String,
}

impl Gap {
    /// The stable id: the kind and the member, with the JDK's version for a call into the JDK, so that a contract
    /// for it (Phase 3 of the brief) names what it was checked against.
    pub fn id(&self, jdk: Option<&str>) -> String {
        let owner = self.owner.replace('/', ".");
        let member = match (self.name.is_empty(), self.descriptor.starts_with('(')) {
            (true, _) => owner,
            (false, true) => format!("{owner}.{}{}", self.name, self.descriptor),
            (false, false) => format!("{owner}.{}:{}", self.name, self.descriptor),
        };
        let of_the_jdk = matches!(self.kind, GapKind::JdkConstructor | GapKind::JdkVoidMethod | GapKind::JdkReferenceMethod);
        match jdk.filter(|_| of_the_jdk) {
            Some(v) => format!("{}:{member}@jdk-{v}", self.kind.name()),
            None => format!("{}:{member}", self.kind.name()),
        }
    }

    /// The member as a reader writes it: `java.util.ArrayList.<init>(int)`.
    pub fn call(&self) -> String {
        java_call(&self.owner, &self.name, &self.descriptor)
    }
}

/// A member as a reader writes it: `java.util.ArrayList.<init>(int)` for a method, `pkg.Class.field` for a field,
/// the class alone for no name.
fn java_call(owner: &str, name: &str, descriptor: &str) -> String {
    let owner = owner.replace('/', ".");
    if name.is_empty() {
        return owner;
    }
    match MethodDescriptor::parse(descriptor) {
        Ok(d) => format!("{owner}.{name}({})", d.params.iter().map(Type::java_name).collect::<Vec<_>>().join(", ")),
        Err(_) => format!("{owner}.{name}"),
    }
}

/// Where a gap is met: the method, and the source line when the class has line numbers.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
pub struct Site {
    pub class: String,
    pub method: String,
    pub line: Option<u16>,
}

impl Site {
    pub fn display(&self) -> String {
        match self.line {
            Some(l) => format!("{}.{}:{l}", self.class.replace('/', "."), self.method),
            None => format!("{}.{}", self.class.replace('/', "."), self.method),
        }
    }
}

/// What the scan found.
#[derive(Debug, Clone, Default)]
pub struct Scan {
    /// The methods walked, `pkg.Class.name(descriptor)`.
    pub methods: BTreeSet<String>,
    /// Each gap with the sites that meet it.
    pub gaps: BTreeMap<Gap, BTreeSet<Site>>,
    /// The JDK calls reproduced exactly that the walked code makes, with how many sites make each.
    pub exact: BTreeMap<String, usize>,
    /// Why the engine would refuse some of the walked code: each kind of reason, with the first member it is about
    /// and its site, and how many sites have it.
    pub refused: BTreeMap<String, Refusal>,
    /// The JDK the gaps of JDK members are about, from its `release` file.
    pub jdk: Option<String>,
}

/// A kind of construct the engine refuses, as the scan met it: the first member or construct and where, and how
/// many sites in all.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Refusal {
    pub first: String,
    pub at: String,
    pub sites: usize,
}

/// One gap of a scan, as `--json` prints it.
#[derive(Debug, Clone, Serialize)]
pub struct GapRecord {
    pub id: String,
    pub kind: GapKind,
    pub call: String,
    pub sites: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ScanRecord {
    pub roots: Vec<String>,
    pub methods: usize,
    pub jdk: Option<String>,
    pub gaps: Vec<GapRecord>,
    pub exact: BTreeMap<String, usize>,
    pub refused: BTreeMap<String, Refusal>,
}

impl Scan {
    pub fn records(&self) -> Vec<GapRecord> {
        self.gaps.iter().map(|(g, sites)| GapRecord { id: g.id(self.jdk.as_deref()), kind: g.kind, call: g.call(), sites: sites.iter().map(Site::display).collect() }).collect()
    }

    pub fn record(&self, roots: &[String]) -> ScanRecord {
        ScanRecord { roots: roots.to_vec(), methods: self.methods.len(), jdk: self.jdk.clone(), gaps: self.records(), exact: self.exact.clone(), refused: self.refused.clone() }
    }

    /// The report `jvmcontract gaps` prints.
    pub fn report(&self, roots: &[String]) -> String {
        let mut out = String::new();
        let n = self.gaps.len();
        let _ = writeln!(out, "{}: {} method{} reached, {n} gap{}", roots.join(", "), self.methods.len(), if self.methods.len() == 1 { "" } else { "s" }, if n == 1 { "" } else { "s" });
        for r in self.records() {
            let _ = writeln!(out, "  gap {}  {} at {}", r.kind.name(), r.call, r.sites.join(", "));
        }
        if !self.exact.is_empty() {
            let _ = writeln!(out, "  reproduced exactly: {}", self.exact.iter().map(|(c, k)| format!("{c} ×{k}")).collect::<Vec<_>>().join(", "));
        }
        for (why, r) in &self.refused {
            let _ = writeln!(out, "  outside the fragment: {why}: {} at {}{}", r.first, r.at, if r.sites > 1 { format!(", {} sites in all", r.sites) } else { String::new() });
        }
        out
    }
}

/// The version of the JDK whose image the class path reads, from `<java home>/release`.
pub fn jdk_release() -> Option<String> {
    let home = crate::jimage::JImage::find_java_home()?;
    let text = std::fs::read_to_string(home.join("release")).ok()?;
    text.lines().find_map(|l| l.strip_prefix("JAVA_VERSION=")).map(|v| v.trim().trim_matches('"').to_string())
}

/// Whether the engine reproduces a call into the JDK exactly: the constructors of `Object` and `Record`, which do
/// nothing, and those of the JDK's exceptions that take nothing, a message, or a message and a cause, which set
/// what no proof observes (the engine compares exceptions by class) and throw nothing.
pub fn exact_jdk_call(cp: &ClassPath, owner: &str, name: &str, descriptor: &str) -> bool {
    if name != "<init>" {
        return false;
    }
    if (owner == "java/lang/Object" || owner == "java/lang/Record") && descriptor == "()V" {
        return true;
    }
    matches!(descriptor, "()V" | "(Ljava/lang/String;)V" | "(Ljava/lang/String;Ljava/lang/Throwable;)V") && crate::classpath::is_jdk_name(owner) && cp.is_subtype(owner, "java/lang/Throwable")
}

/// The roots a proof of each target starts from: the method, and the constructors of its class when it is an
/// instance method, and of each application class among its parameter and result types, since the harness builds
/// those values through their constructors.
pub fn roots(cp: &ClassPath, targets: &[String]) -> Result<Vec<MemberRef>, Error> {
    let mut out = Vec::new();
    for target in targets {
        let (class, _) = crate::verifier::parse_target(target).ok_or_else(|| Error::new("target must be <class>#<method>"))?;
        let cf = cp.application(&class)?.ok_or_else(|| Error::new(format!("class not found: {}", class.replace('/', "."))))?;
        let m = crate::verifier::select_method(&cf, target).map_err(Error::new)?;
        out.push(MemberRef::new(&class, &m.name, &m.descriptor));
        let d = MethodDescriptor::parse(&m.descriptor).map_err(|e| Error::new(e.to_string()))?;
        let mut built: Vec<String> = d.params.iter().chain(std::iter::once(&d.ret)).filter_map(|t| if let Type::Object(c) = t { Some(c.clone()) } else { None }).filter(|c| cp.is_application(c)).collect();
        if !m.is_static() {
            built.insert(0, class.clone());
        }
        for c in built {
            if let Ok(Some(k)) = cp.application(&c) {
                for init in k.methods.iter().filter(|i| i.name == "<init>") {
                    out.push(MemberRef::new(&c, "<init>", &init.descriptor));
                }
            }
        }
    }
    Ok(out)
}

struct Walker<'a> {
    cp: &'a ClassPath,
    scan: Scan,
    queue: VecDeque<(String, String, String)>,
    seen: BTreeSet<(String, String, String)>,
    initialised: BTreeSet<String>,
    literals: BTreeSet<(String, Site)>,
    compares_references: bool,
}

/// Scans what the roots (`(owner, name, descriptor)`, internal names) may reach. A root that is a static method
/// or a constructor initialises its class, as the harness's call does.
pub fn scan(cp: &ClassPath, roots: &[MemberRef]) -> Result<Scan, Error> {
    let mut w = Walker { cp, scan: Scan { jdk: jdk_release(), ..Scan::default() }, queue: VecDeque::new(), seen: BTreeSet::new(), initialised: BTreeSet::new(), literals: BTreeSet::new(), compares_references: false };
    for r in roots {
        let root = Site { class: "harness".into(), method: "check".into(), line: None };
        w.initialise(&r.owner, &root);
        w.enqueue(&r.owner, &r.name, &r.descriptor);
    }
    while let Some((owner, name, descriptor)) = w.queue.pop_front() {
        w.walk(&owner, &name, &descriptor)?;
    }
    if w.compares_references {
        for (class, site) in std::mem::take(&mut w.literals) {
            w.gap(GapKind::LiteralIdentity, &class, "", "", site);
        }
    }
    Ok(w.scan)
}

impl Walker<'_> {
    fn enqueue(&mut self, owner: &str, name: &str, descriptor: &str) {
        let key = (owner.to_string(), name.to_string(), descriptor.to_string());
        if self.seen.insert(key.clone()) {
            self.queue.push_back(key);
        }
    }

    fn gap(&mut self, kind: GapKind, owner: &str, name: &str, descriptor: &str, site: Site) {
        self.scan.gaps.entry(Gap { kind, owner: owner.to_string(), name: name.to_string(), descriptor: descriptor.to_string() }).or_default().insert(site);
    }

    fn refuse(&mut self, why: &str, what: String, site: &Site) {
        self.scan.refused.entry(why.to_string()).or_insert_with(|| Refusal { first: what, at: site.display(), sites: 0 }).sites += 1;
    }

    /// A use of `class` that initialises it (JVMS §5.5): its `<clinit>`, and its superclasses', are gaps, since the
    /// engine runs none. A JDK class is taken as initialised already.
    fn initialise(&mut self, class: &str, site: &Site) {
        let mut current = Some(class.to_string());
        while let Some(c) = current {
            if crate::classpath::is_jdk_name(&c) || !self.initialised.insert(c.clone()) {
                break;
            }
            let Ok(Some(cf)) = self.cp.application(&c) else { break };
            if !cf.is_interface() && cf.method("<clinit>", "()V").is_some() {
                self.gap(GapKind::ClassInitializer, &c, "<clinit>", "()V", site.clone());
            }
            current = cf.super_class.clone();
        }
    }

    /// The application classes that are `owner` or below it and declare `name(descriptor)`: the methods an
    /// invocation on a receiver of one of them runs.
    fn overrides(&self, owner: &str, name: &str, descriptor: &str) -> Vec<String> {
        let Ok(classes) = self.cp.application_classes() else { return Vec::new() };
        classes.iter().filter(|(n, cf)| cf.method(name, descriptor).is_some_and(|m| m.code.is_some()) && self.cp.is_subtype(n, owner)).map(|(n, _)| n.clone()).collect()
    }

    fn walk(&mut self, owner: &str, name: &str, descriptor: &str) -> Result<(), Error> {
        let Some((cf, m)) = self.cp.bytecode_method(owner, name, descriptor) else { return Ok(()) };
        let label = format!("{}.{name}{descriptor}", cf.name.replace('/', "."));
        if !self.scan.methods.insert(label) {
            return Ok(());
        }
        let Some(code) = m.code.as_ref() else {
            let site = Site { class: cf.name.clone(), method: name.into(), line: None };
            self.refuse("a method without code", format!("{}.{name}", cf.name.replace('/', ".")), &site);
            return Ok(());
        };
        let insns = code.instructions().map_err(|e| Error::new(format!("{}.{name}: {e}", cf.name)))?;
        for (pc, insn) in insns {
            let site = Site { class: cf.name.clone(), method: name.to_string(), line: code.line_at(pc) };
            match insn {
                Insn::FConst(_) | Insn::DConst(_) => self.refuse("floating point", "a floating-point constant".into(), &site),
                Insn::Arith(_, k) | Insn::Return(Some(k)) | Insn::Load(k, _) | Insn::Store(k, _) | Insn::Convert(k, _) if matches!(k, Kind::Float | Kind::Double) => self.refuse("floating point", "floating-point arithmetic".into(), &site),
                Insn::Jsr(_) | Insn::Ret(_) => self.refuse("jsr/ret", "jsr".into(), &site),
                Insn::PutStatic(index) => {
                    let member = cf.pool.member(index).map_err(|e| Error::new(e.to_string()))?;
                    self.refuse("writes a static field", format!("{}.{}", member.owner.replace('/', "."), member.name), &site);
                }
                Insn::ANewArray(_) | Insn::MultiANewArray(..) => self.refuse("arrays of references", "a new array of references".into(), &site),
                Insn::IfACmp(..) => self.compares_references = true,
                Insn::MonitorEnter | Insn::MonitorExit => self.gap(GapKind::Monitor, &cf.name, "", "", site),
                Insn::Ldc(index) => match cf.pool.loadable(index) {
                    Ok(BootstrapArg::Str(_)) => {
                        self.literals.insert(("java/lang/String".into(), site));
                    }
                    Ok(BootstrapArg::Class(_)) => {
                        self.literals.insert(("java/lang/Class".into(), site));
                    }
                    Ok(BootstrapArg::Float(_) | BootstrapArg::Double(_)) => self.refuse("floating point", "a floating-point constant".into(), &site),
                    _ => {}
                },
                Insn::GetStatic(index) => {
                    let member = cf.pool.member(index).map_err(|e| Error::new(e.to_string()))?;
                    if !self.constant(&member.owner, &member.name) {
                        self.refuse("reads a static field that is not a compile-time constant", format!("{}.{}", member.owner.replace('/', "."), member.name), &site);
                    }
                    self.initialise(&member.owner, &site);
                }
                Insn::New(index) => {
                    let class = cf.pool.class_name(index).map_err(|e| Error::new(e.to_string()))?.to_string();
                    self.initialise(&class, &site);
                }
                Insn::GetField(index) | Insn::PutField(index) => {
                    let member = cf.pool.member(index).map_err(|e| Error::new(e.to_string()))?;
                    if self.hidden(&member.owner, &member.name) {
                        self.gap(GapKind::HiddenField, &member.owner, &member.name, &member.descriptor, site);
                    }
                }
                Insn::InvokeDynamic(index) => {
                    let (_, _, text) = cf.pool.invoke_dynamic(index).map_err(|e| Error::new(e.to_string()))?;
                    let d = MethodDescriptor::parse(text).map_err(|e| Error::new(e.to_string()))?;
                    if d.ret != Type::Object("java/lang/String".into()) {
                        self.refuse("invokedynamic other than string concatenation", format!("invokedynamic {text}"), &site);
                        continue;
                    }
                    for p in &d.params {
                        if let Type::Object(class) = p {
                            if class != "java/lang/String" {
                                self.gap(GapKind::StringConversion, class, "toString", "()Ljava/lang/String;", site.clone());
                            }
                        }
                    }
                }
                Insn::InvokeStatic(index) => {
                    let member = cf.pool.member(index).map_err(|e| Error::new(e.to_string()))?;
                    if self.cp.is_application(&member.owner) {
                        self.initialise(&member.owner, &site);
                        self.enqueue(&member.owner, &member.name, &member.descriptor);
                    } else if self.cp.model(&member.owner).is_some() && self.cp.bytecode_method(&member.owner, &member.name, &member.descriptor).is_some_and(|(_, m)| m.code.is_some()) {
                        self.enqueue(&member.owner, &member.name, &member.descriptor);
                    } else if super::models_jdk_static(&member.owner, &member.name) {
                        *self.scan.exact.entry(format!("{}.{}", member.owner.replace('/', "."), member.name)).or_default() += 1;
                    } else {
                        self.refuse("a static JDK method it does not model", java_call(&member.owner, &member.name, &member.descriptor), &site);
                    }
                }
                Insn::InvokeSpecial(index) | Insn::InvokeVirtual(index) | Insn::InvokeInterface(index) => {
                    let member = cf.pool.member(index).map_err(|e| Error::new(e.to_string()))?;
                    let special = matches!(insn, Insn::InvokeSpecial(_));
                    let resolved = self.cp.bytecode_method(&member.owner, &member.name, &member.descriptor).filter(|(c, m)| self.cp.is_application(&c.name) && m.code.is_some());
                    let overrides = if special { Vec::new() } else { self.overrides(&member.owner, &member.name, &member.descriptor) };
                    for o in &overrides {
                        self.enqueue(o, &member.name, &member.descriptor);
                    }
                    if let Some((c, _)) = resolved {
                        self.enqueue(&c.name, &member.name, &member.descriptor);
                        continue;
                    }
                    // The method is the JDK's, on this receiver: the engine's fallback.
                    if exact_jdk_call(self.cp, &member.owner, &member.name, &member.descriptor) {
                        *self.scan.exact.entry(format!("{}.{}{}", member.owner.replace('/', "."), member.name, member.descriptor)).or_default() += 1;
                        continue;
                    }
                    let d = MethodDescriptor::parse(&member.descriptor).map_err(|e| Error::new(e.to_string()))?;
                    let kind = if member.name == "<init>" {
                        GapKind::JdkConstructor
                    } else {
                        match d.ret {
                            Type::Void => GapKind::JdkVoidMethod,
                            Type::Object(_) => GapKind::JdkReferenceMethod,
                            _ => {
                                self.refuse("a primitive result of a JDK instance method", java_call(&member.owner, &member.name, &member.descriptor), &site);
                                continue;
                            }
                        }
                    };
                    self.gap(kind, &member.owner, &member.name, &member.descriptor, site);
                }
                _ => {}
            }
        }
        Ok(())
    }

    /// Whether the engine reads the static field as a constant ([`super::Engine::get_static`]): the integer
    /// wrappers' bounds, or an application field with a `ConstantValue` attribute.
    fn constant(&self, owner: &str, name: &str) -> bool {
        if matches!((owner, name), ("java/lang/Integer" | "java/lang/Long", "MAX_VALUE" | "MIN_VALUE")) {
            return true;
        }
        let Ok(Some(cf)) = self.cp.bytecode(owner) else { return false };
        cf.field(name).filter(|f| f.is_static()).is_some_and(|f| f.attributes.iter().any(|a| a.name == "ConstantValue"))
    }

    /// Whether a field name stands for two fields along `owner`'s class hierarchy: declared by `owner` or a
    /// superclass, and again by another of them or by an application class below `owner`.
    fn hidden(&self, owner: &str, name: &str) -> bool {
        let mut declaring = BTreeSet::new();
        let mut current = Some(owner.to_string());
        while let Some(c) = current {
            let Ok(Some(cf)) = self.cp.application(&c) else { break };
            if cf.field(name).is_some_and(|f| !f.is_static()) {
                declaring.insert(c.clone());
            }
            current = cf.super_class.clone();
        }
        if let Ok(classes) = self.cp.application_classes() {
            for (n, cf) in &classes {
                if cf.field(name).is_some_and(|f| !f.is_static()) && self.cp.is_subtype(n, owner) {
                    declaring.insert(n.clone());
                }
            }
        }
        declaring.len() > 1
    }
}
