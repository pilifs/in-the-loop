//! The gaps of the tool's own checker: what in the bytecode a method reaches the engine does not implement as the
//! JVM does, each with a stable id ([`Gap::id`]), found statically before anything is proved ([`scan`]) and met by
//! the engine as it runs ([`super::check`]).
//!
//! | [`GapKind`] | What the engine takes it to do under `--gaps assume` | What the JVM does | Met by the engine |
//! |---|---|---|---|
//! | `jdk-constructor` | constructs the object and does nothing else | runs the constructor, which may throw (`new ArrayList<>(-1)`) or keep its arguments | yes |
//! | `jdk-void-method` | returns and does nothing | runs it, and it may change its receiver or arguments (`Random.nextBytes` fills its array), or throw | yes |
//! | `jdk-reference-method` | returns a new object, never null | may return null or an object that exists already, or throw | yes |
//! | `string-conversion` | makes a new string without converting its arguments | calls `toString` on an object argument, which may throw (bytecode of javac 9 to 18: from 19 on, javac calls `String.valueOf` first, which the engine refuses) | yes |
//! | `class-initializer` | takes the class's `<clinit>` to have run already, and thrown nothing | runs it at the class's first `new`, `getstatic`, `putstatic` or `invokestatic` (JVMS §5.5), after its superclasses' and those of its superinterfaces that declare a default method, and it may throw (`ExceptionInInitializerError`) or set state | yes |
//!
//! Under `--gaps strict`, the default, a path that reaches a gap ends there, and a run that met one has no verdict
//! unless another path violates the property; under `--gaps assume` the engine goes on as the second column says,
//! and a verdict names every gap it assumed. A JDK class is taken to be initialized already: its initializer sets
//! the JDK's own state, which the engine reads only through the calls it models.
//!
//! What step 1c of `llm-dlc/loops/sound-verdicts.md` made exact, and so is no gap: a field is resolved as the JVM
//! resolves it (JVMS §5.4.3.2, [`ClassPath::resolve_field`]), so a field a subclass declares again is a second field
//! ([`ClassPath::field_key`]), and every `ldc` of one string or class literal is the same object, as the JVM interns
//! strings (JLS §3.10.5) and has one `Class` object per class. A string concatenation makes a new string, as JLS
//! §15.18.1 says it does unless the expression is a constant, which javac folds into a literal.
//!
//! A JDK call the engine reproduces exactly is not a gap ([`jdk_instance_call`]): `Object.<init>`,
//! `Record.<init>`, the constructors of the JDK's exceptions that take no argument or a message (and a cause),
//! which change nothing the proof observes, and the static JDK methods it models ([`super::models_jdk_static`]).
//! The scan counts those it relied on. A construct the engine refuses (floating point, a static field written, an
//! array of references, a primitive result of a JDK instance method, ...) is not a gap either: it ends the proof
//! with no verdict, as it should, in either mode. The scan lists those reasons too, since a method that has one is
//! outside the engine whatever its gaps. `monitorenter` and `monitorexit` are implemented: they throw
//! `NullPointerException` on null and otherwise do nothing, which is all they do in a run of one thread.
//!
//! [`scan`] walks the methods a set of roots may reach, as the engine resolves them: the application's own methods
//! (with every override an application class declares, since the receiver's class picks one), and the static
//! methods of the tool's models. It reads every instruction of each, so it may report a gap on a path no input
//! takes. The harness itself, and the
//! expressions of a property or relation compiled into it, are not walked. Step 1a of
//! `llm-dlc/loops/sound-verdicts.md`: what strictness would cost each recorded example.

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::fmt::Write as _;
use std::sync::OnceLock;

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
    ClassInitializer,
    StringConversion,
}

impl GapKind {
    pub fn name(self) -> &'static str {
        match self {
            GapKind::JdkConstructor => "jdk-constructor",
            GapKind::JdkVoidMethod => "jdk-void-method",
            GapKind::JdkReferenceMethod => "jdk-reference-method",
            GapKind::ClassInitializer => "class-initializer",
            GapKind::StringConversion => "string-conversion",
        }
    }

    /// Whether JBMC implements the construct, so that `--engine auto` asks it when the tool's own checker refused
    /// one: it runs class initializers, but approximates a JDK call it has no bytecode for as the engine's assume
    /// mode does, without naming it (step 4c of `llm-dlc/loops/sound-verdicts.md`).
    pub fn jbmc_implements(self) -> bool {
        matches!(self, GapKind::ClassInitializer)
    }

    /// What the engine takes the construct to do under `--gaps assume`: the assumption a verdict states.
    pub fn approximation(self) -> &'static str {
        match self {
            GapKind::JdkConstructor => "constructs the object and does nothing else: it throws nothing and keeps nothing of its arguments",
            GapKind::JdkVoidMethod => "returns and does nothing: it throws nothing and changes neither its receiver nor its arguments",
            GapKind::JdkReferenceMethod => "returns a new object, never null: it throws nothing and changes neither its receiver nor its arguments",
            GapKind::ClassInitializer => "has run already, and threw nothing",
            GapKind::StringConversion => "makes a new string without calling toString on its object arguments",
        }
    }
}

/// How the tool's own checker treats a gap: refuses it (`strict`, the default: the path ends there and the run
/// has no verdict unless another path is a violation), or takes the approximation of
/// [`GapKind::approximation`] and names it in the verdict (`assume`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum GapMode {
    #[default]
    Strict,
    Assume,
}

impl GapMode {
    pub fn name(self) -> &'static str {
        match self {
            GapMode::Strict => "strict",
            GapMode::Assume => "assume",
        }
    }
}

impl std::str::FromStr for GapMode {
    type Err = Error;

    fn from_str(s: &str) -> Result<GapMode, Error> {
        match s {
            "strict" => Ok(GapMode::Strict),
            "assume" => Ok(GapMode::Assume),
            other => Err(Error::new(format!("unknown gap mode {other:?}: strict or assume"))),
        }
    }
}

/// One gap: the kind, and the member it is about (a call, a field, a class's initializer, a literal's class).
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Gap {
    pub kind: GapKind,
    /// The class, internal name.
    pub owner: String,
    /// The method or field, or empty for a literal.
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

/// One gap, as `--json` prints it: of a scan, or met by a run of the engine, with what it is taken to do under
/// `--gaps assume` and, for a run, whether it was (`assumed`) or the path ended there (`refused`).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct GapRecord {
    pub id: String,
    pub kind: GapKind,
    pub call: String,
    pub sites: Vec<String>,
    pub approximation: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub treatment: Option<GapTreatment>,
}

/// What a run did at a gap it met.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum GapTreatment {
    Refused,
    Assumed,
}

impl GapRecord {
    /// The gap as a verdict's line names it: `id: call at site, ...`.
    pub fn line(&self) -> String {
        format!("{}: {} {}, at {}", self.id, self.call, self.approximation, self.sites.join(", "))
    }
}

/// The records of gaps with the sites that meet them, under the JDK `jdk`, treated as `treatment` (none for a scan).
pub fn records(gaps: &BTreeMap<Gap, BTreeSet<Site>>, jdk: Option<&str>, treatment: Option<GapTreatment>) -> Vec<GapRecord> {
    gaps.iter().map(|(g, sites)| GapRecord { id: g.id(jdk), kind: g.kind, call: g.call(), sites: sites.iter().map(Site::display).collect(), approximation: g.kind.approximation().to_string(), treatment }).collect()
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
        records(&self.gaps, self.jdk.as_deref(), None)
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

/// The version of the JDK whose image the class path reads, from `<java home>/release`; read once per process.
pub fn jdk_release() -> Option<String> {
    static RELEASE: OnceLock<Option<String>> = OnceLock::new();
    RELEASE
        .get_or_init(|| {
            let home = crate::jimage::JImage::find_java_home()?;
            let text = std::fs::read_to_string(home.join("release")).ok()?;
            text.lines().find_map(|l| l.strip_prefix("JAVA_VERSION=")).map(|v| v.trim().trim_matches('"').to_string())
        })
        .clone()
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

/// What the engine does with an instance call (or a constructor) that resolves to no application method with code.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum JdkCall {
    /// It reproduces the call exactly ([`exact_jdk_call`]).
    Exact,
    /// The call is a gap of this kind.
    Gap(GapKind),
    /// It refuses the call: a primitive or array result it could only make up.
    Refused,
}

/// How the engine treats an instance call `owner.name(descriptor)` that runs JDK code: the one classification the
/// engine and the scan share.
pub fn jdk_instance_call(cp: &ClassPath, owner: &str, name: &str, descriptor: &str) -> JdkCall {
    if exact_jdk_call(cp, owner, name, descriptor) {
        return JdkCall::Exact;
    }
    if name == "<init>" {
        return JdkCall::Gap(GapKind::JdkConstructor);
    }
    match MethodDescriptor::parse(descriptor).map(|d| d.ret) {
        Ok(Type::Void) => JdkCall::Gap(GapKind::JdkVoidMethod),
        Ok(Type::Object(_)) => JdkCall::Gap(GapKind::JdkReferenceMethod),
        _ => JdkCall::Refused,
    }
}

/// The object arguments a string concatenation by `invokedynamic` would convert with `toString`: every parameter
/// of its descriptor that is an object other than a `String` (a `string-conversion` gap each).
pub fn converted_arguments(descriptor: &MethodDescriptor) -> Vec<String> {
    descriptor.params.iter().filter_map(|p| if let Type::Object(class) = p { Some(class.clone()) } else { None }).filter(|c| c != "java/lang/String").collect()
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

/// The application classes whose `<clinit>` the JVM runs when a use of `class` initializes it (JVMS §5.5), in the
/// order it runs them: for a class, its superclass's first (recursively), then those of its superinterfaces that
/// declare a non-abstract instance method (a default method), then its own; for an interface, its own alone. A
/// class without a `<clinit>`, and a JDK class, which the engine takes to be initialized already, add none.
pub fn initializers(cp: &ClassPath, class: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut seen = BTreeSet::new();
    initializers_of(cp, class, &mut out, &mut seen);
    out
}

fn initializers_of(cp: &ClassPath, class: &str, out: &mut Vec<String>, seen: &mut BTreeSet<String>) {
    if crate::classpath::is_jdk_name(class) || !seen.insert(class.to_string()) {
        return;
    }
    let Ok(Some(cf)) = cp.application(class) else { return };
    if !cf.is_interface() {
        if let Some(sup) = &cf.super_class {
            initializers_of(cp, sup, out, seen);
        }
        let mut interfaces = Vec::new();
        let mut visit: Vec<String> = cf.interfaces.iter().rev().cloned().collect();
        while let Some(i) = visit.pop() {
            if interfaces.contains(&i) || crate::classpath::is_jdk_name(&i) {
                continue;
            }
            if let Ok(Some(icf)) = cp.application(&i) {
                visit.extend(icf.interfaces.iter().rev().cloned());
            }
            interfaces.push(i);
        }
        for i in interfaces {
            let Ok(Some(icf)) = cp.application(&i) else { continue };
            if icf.methods.iter().any(|m| !m.is_static() && !m.is_abstract() && m.name != "<clinit>") {
                initializers_of(cp, &i, out, seen);
            }
        }
    }
    if cf.method("<clinit>", "()V").is_some() {
        out.push(class.to_string());
    }
}

struct Walker<'a> {
    cp: &'a ClassPath,
    scan: Scan,
    queue: VecDeque<(String, String, String)>,
    seen: BTreeSet<(String, String, String)>,
    initialised: BTreeSet<String>,
}

/// Scans what the roots (`(owner, name, descriptor)`, internal names) may reach. A root that is a static method
/// or a constructor initialises its class, as the harness's call does.
pub fn scan(cp: &ClassPath, roots: &[MemberRef]) -> Result<Scan, Error> {
    let mut w = Walker { cp, scan: Scan { jdk: jdk_release(), ..Scan::default() }, queue: VecDeque::new(), seen: BTreeSet::new(), initialised: BTreeSet::new() };
    for r in roots {
        let root = Site { class: "harness".into(), method: "check".into(), line: None };
        w.initialise(&r.owner, &root);
        w.enqueue(&r.owner, &r.name, &r.descriptor);
    }
    while let Some((owner, name, descriptor)) = w.queue.pop_front() {
        w.walk(&owner, &name, &descriptor)?;
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

    /// A use of `class` that initializes it (JVMS §5.5): each `<clinit>` that runs ([`initializers`]) is a gap,
    /// since the engine runs none, recorded where the walk first reaches it.
    fn initialise(&mut self, class: &str, site: &Site) {
        for c in initializers(self.cp, class) {
            if self.initialised.insert(c.clone()) {
                self.gap(GapKind::ClassInitializer, &c, "<clinit>", "()V", site.clone());
            }
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
                Insn::Ldc(index) => {
                    if let Ok(BootstrapArg::Float(_) | BootstrapArg::Double(_)) = cf.pool.loadable(index) {
                        self.refuse("floating point", "a floating-point constant".into(), &site);
                    }
                }
                Insn::GetStatic(index) => {
                    let member = cf.pool.member(index).map_err(|e| Error::new(e.to_string()))?;
                    if !self.constant(&member.owner, &member.name) {
                        self.refuse("reads a static field that is not a compile-time constant", format!("{}.{}", member.owner.replace('/', "."), member.name), &site);
                    }
                    let declaring = self.cp.resolve_field(&member.owner, &member.name, &member.descriptor).unwrap_or_else(|| member.owner.clone());
                    self.initialise(&declaring, &site);
                }
                Insn::New(index) => {
                    let class = cf.pool.class_name(index).map_err(|e| Error::new(e.to_string()))?.to_string();
                    self.initialise(&class, &site);
                }
                Insn::InvokeDynamic(index) => {
                    let (_, _, text) = cf.pool.invoke_dynamic(index).map_err(|e| Error::new(e.to_string()))?;
                    let d = MethodDescriptor::parse(text).map_err(|e| Error::new(e.to_string()))?;
                    if d.ret != Type::Object("java/lang/String".into()) {
                        self.refuse("invokedynamic other than string concatenation", format!("invokedynamic {text}"), &site);
                        continue;
                    }
                    for class in converted_arguments(&d) {
                        self.gap(GapKind::StringConversion, &class, "toString", "()Ljava/lang/String;", site.clone());
                    }
                }
                Insn::InvokeStatic(index) => {
                    let member = cf.pool.member(index).map_err(|e| Error::new(e.to_string()))?;
                    if self.cp.is_application(&member.owner) {
                        let declaring = self.cp.bytecode_method(&member.owner, &member.name, &member.descriptor).map(|(c, _)| c.name.clone()).unwrap_or_else(|| member.owner.clone());
                        self.initialise(&declaring, &site);
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
                    match jdk_instance_call(self.cp, &member.owner, &member.name, &member.descriptor) {
                        JdkCall::Exact => *self.scan.exact.entry(format!("{}.{}{}", member.owner.replace('/', "."), member.name, member.descriptor)).or_default() += 1,
                        JdkCall::Gap(kind) => self.gap(kind, &member.owner, &member.name, &member.descriptor, site),
                        JdkCall::Refused => self.refuse("a primitive result of a JDK instance method", java_call(&member.owner, &member.name, &member.descriptor), &site),
                    }
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
}
