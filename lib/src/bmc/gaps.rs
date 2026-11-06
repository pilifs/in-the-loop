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
//! | `jdk-primitive-method` | nothing: refused as under strict | runs it, and returns a value the engine could only make up (`Random.nextInt(bound)`), or throws | yes |
//! | `jdk-static-method` | nothing: refused as under strict | runs a static JDK method the engine does not model (`Integer.numberOfLeadingZeros`, `Arrays.fill`), which may return any value, change an argument array, or throw | yes |
//! | `missing-body` | (JBMC's stub, [`crate::jbmc_gaps`]) returns any value of its type, or `null` or a new object, and does nothing else | runs a method JBMC has no bytecode for (its class is not on JBMC's class path, or it is abstract or native), which may throw or change its arguments | no: JBMC only |
//! | `monitor` | (JBMC, [`crate::jbmc_gaps`]) drops `monitorenter` and `monitorexit`: a null monitor throws nothing (this engine implements them: NPE on null) | throws `NullPointerException` at a null monitor | no: JBMC only |
//! | `invokedynamic` | (JBMC, [`crate::jbmc_gaps`]) takes the call site's value to be zero, `false` or `null`, and runs nothing | links the call site by its bootstrap method and runs what it links: a string concatenation, a record's `equals`, `hashCode` or `toString`, a lambda for a JDK interface | no: JBMC only |
//!
//! Under `--gaps strict`, the default, a path that reaches a gap ends there, and a run that met one has no verdict
//! unless another path violates the property; under `--gaps assume` the engine goes on as the second column says,
//! and a verdict names every gap it assumed. The last two kinds have no assume form ([`GapKind::assumable`]): the
//! only approximation of a value is a made-up one, so they are refused under assume too, and only a contract
//! (`--gaps advised`, [`crate::gap_contracts`]) closes them. A JDK class is taken to be initialized already: its initializer sets
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
//! array of references, a floating-point or array result of a JDK method, ...) is not a gap either: it ends the proof
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
    /// A JDK instance method with an integral, `char` or `boolean` result.
    JdkPrimitiveMethod,
    /// A static JDK method the engine does not model ([`super::models_jdk_static`], `lib/models`).
    JdkStaticMethod,
    /// A method JBMC has no bytecode for outside the JDK (its class is not on JBMC's class path, or it is abstract
    /// or native), which JBMC gives a stub ([`crate::jbmc_gaps`]). Never met by the own checker, which refuses it.
    MissingBody,
    /// An `invokedynamic` JBMC does not link, whose value it takes to be zero or `null` ([`crate::jbmc_gaps`]).
    /// The own checker refuses every `invokedynamic` it has no model of.
    InvokeDynamic,
    /// A method JBMC runs that synchronizes: JBMC drops monitor instructions ([`crate::jbmc_gaps`]), where this
    /// engine implements them.
    Monitor,
}

impl GapKind {
    pub fn name(self) -> &'static str {
        match self {
            GapKind::JdkConstructor => "jdk-constructor",
            GapKind::JdkVoidMethod => "jdk-void-method",
            GapKind::JdkReferenceMethod => "jdk-reference-method",
            GapKind::ClassInitializer => "class-initializer",
            GapKind::StringConversion => "string-conversion",
            GapKind::JdkPrimitiveMethod => "jdk-primitive-method",
            GapKind::JdkStaticMethod => "jdk-static-method",
            GapKind::MissingBody => "missing-body",
            GapKind::InvokeDynamic => "invokedynamic",
            GapKind::Monitor => "monitor",
        }
    }

    /// Every kind, in order.
    pub const ALL: [GapKind; 10] = [GapKind::JdkConstructor, GapKind::JdkVoidMethod, GapKind::JdkReferenceMethod, GapKind::ClassInitializer, GapKind::StringConversion, GapKind::JdkPrimitiveMethod, GapKind::JdkStaticMethod, GapKind::MissingBody, GapKind::InvokeDynamic, GapKind::Monitor];

    /// The kind an id's first part names.
    pub fn from_name(name: &str) -> Option<GapKind> {
        GapKind::ALL.into_iter().find(|k| k.name() == name)
    }

    /// Whether it is a call into the JDK, whose id names the JDK's version.
    pub fn of_the_jdk(self) -> bool {
        matches!(self, GapKind::JdkConstructor | GapKind::JdkVoidMethod | GapKind::JdkReferenceMethod | GapKind::JdkPrimitiveMethod | GapKind::JdkStaticMethod)
    }

    /// Whether `--gaps assume` has an approximation for it. A call whose value the proof reads has none: the engine
    /// could only make the value up, and a made-up value is no approximation of the call's. Such a gap is refused
    /// in every mode, and only a contract closes it.
    pub fn assumable(self) -> bool {
        !matches!(self, GapKind::JdkPrimitiveMethod | GapKind::JdkStaticMethod)
    }


    /// What the engine takes the construct to do under `--gaps assume`: the assumption a verdict states.
    pub fn approximation(self) -> &'static str {
        match self {
            GapKind::JdkConstructor => "constructs the object and does nothing else: it throws nothing and keeps nothing of its arguments",
            GapKind::JdkVoidMethod => "returns and does nothing: it throws nothing and changes neither its receiver nor its arguments",
            GapKind::JdkReferenceMethod => "returns a new object, never null: it throws nothing and changes neither its receiver nor its arguments",
            GapKind::ClassInitializer => "has run already, and threw nothing",
            GapKind::StringConversion => "makes a new string without calling toString on its object arguments",
            GapKind::JdkPrimitiveMethod | GapKind::JdkStaticMethod => "has no approximation: its value could only be made up, so it is refused under --gaps assume too, and only a contract closes it (--gaps advised)",
            GapKind::MissingBody => "is JBMC's stub: it returns any value of its type and does nothing else",
            GapKind::InvokeDynamic => "is a call site JBMC does not link: it takes the value zero or null",
            GapKind::Monitor => "synchronizes, and JBMC drops its monitor instructions: a null monitor throws nothing",
        }
    }
}

/// How the tool's own checker treats a gap: refuses it (`strict`, the default: the path ends there and the run
/// has no verdict unless another path is a violation), takes the approximation of [`GapKind::approximation`] and
/// names it in the verdict (`assume`), or hands it to the agent driving the tool before anything is solved
/// (`advised`, [`crate::advice`]): a run that reaches a gap with no contract stops with what a contract for each
/// must state, and otherwise goes on as under strict, which is the advised mode given no contracts.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum GapMode {
    #[default]
    Strict,
    Assume,
    Advised,
}

impl GapMode {
    pub fn name(self) -> &'static str {
        match self {
            GapMode::Strict => "strict",
            GapMode::Assume => "assume",
            GapMode::Advised => "advised",
        }
    }

    /// Whether a path that reaches a gap ends there: under strict, and under advised, where a gap with no contract
    /// is refused as under strict.
    pub fn refuses(self) -> bool {
        self != GapMode::Assume
    }
}

impl std::str::FromStr for GapMode {
    type Err = Error;

    fn from_str(s: &str) -> Result<GapMode, Error> {
        match s {
            "strict" => Ok(GapMode::Strict),
            "assume" => Ok(GapMode::Assume),
            "advised" => Ok(GapMode::Advised),
            other => Err(Error::new(format!("unknown gap mode {other:?}: strict, assume or advised"))),
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
        match jdk.filter(|_| self.kind.of_the_jdk()) {
            Some(v) => format!("{}:{member}@jdk-{v}", self.kind.name()),
            None => format!("{}:{member}", self.kind.name()),
        }
    }

    /// The member as a reader writes it: `java.util.ArrayList.<init>(int)`.
    pub fn call(&self) -> String {
        java_call(&self.owner, &self.name, &self.descriptor)
    }

    /// Whether JBMC implements the construct, so that `--engine auto` asks it when the tool's own checker refused
    /// it: JBMC runs class initializers, and the bytecode of the JDK classes it is given
    /// ([`crate::equivalence::JDK_CLASSES`]), but has no bytecode for any other JDK call, which it gives a stub
    /// that is a gap of its own ([`crate::jbmc_gaps`]).
    pub fn jbmc_implements(&self) -> bool {
        self.kind == GapKind::ClassInitializer || (self.kind.of_the_jdk() && crate::equivalence::JDK_CLASSES.contains(&self.owner.as_str()))
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
/// `--gaps assume` and, for a run, whether it was (`assumed`), the path ended there (`refused`), or a contract
/// closed it (`contract`, with the contract).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct GapRecord {
    pub id: String,
    pub kind: GapKind,
    pub call: String,
    pub sites: Vec<String>,
    pub approximation: String,
    /// Whether JBMC implements it ([`Gap::jbmc_implements`]).
    #[serde(skip)]
    pub jbmc: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub treatment: Option<GapTreatment>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub contract: Option<ContractUse>,
    /// The checker whose approximation it is: `jbmc` for JBMC's ([`crate::jbmc_gaps`]), absent for the tool's own.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub checker: Option<String>,
}

/// What a run did at a gap it met.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum GapTreatment {
    Refused,
    Assumed,
    /// A contract closed it (`--contracts`, [`crate::gap_contracts`]): the engine applied what it states.
    Contract,
}

/// The contract a run applied at a gap: what it states, who wrote it, and what backs it.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ContractUse {
    pub summary: String,
    pub written_by: String,
    pub evidence: crate::gap_contracts::Evidence,
    /// What testing it on a real JVM found, when the JVM could test it.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub testing: Option<crate::gap_contracts::Testing>,
    /// Why the JVM did not test it: what kept it from it.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub untested: Option<String>,
    /// The proof against the JDK's bytecode, for a proved contract ([`crate::contract_proving`]).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub proof: Option<crate::gap_contracts::Proof>,
    /// Why it is not proved: the call is not one a proof is about, or the checker gave no proof.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unproved: Option<String>,
    /// When its evidence is the contract library's record of a check, not this run's ([`crate::contract_library`]):
    /// `checked once, on JDK 25.0.4.1 by jvmcontract 0.1.0, and recorded in the contract library, ...`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub recorded: Option<String>,
    /// The contracts file (the agent's, or the library's), and the line of the contract's id.
    pub file: String,
    pub line: usize,
    /// Its number among the file's accepted contracts, which the generated method is named by.
    #[serde(skip)]
    pub index: usize,
}

/// How the engine applies a contract at its gap.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Closing {
    /// By calling `method` of [`crate::gap_contracts::CLASS`] with the call's arguments, after the receiver when
    /// `receiver`.
    Stub { method: String, descriptor: String, receiver: bool },
    /// The class is taken to be initialized: its initializer throws nothing and sets nothing the proof reads.
    Initialised,
}

/// A gap a contract closes: how, and the contract.
#[derive(Debug, Clone, PartialEq)]
pub struct Closure {
    pub how: Closing,
    pub contract: ContractUse,
}

/// What the engine does at a gap: the mode, and under advised the contracts that close some, with the directory
/// of the class that applies them, which goes on the engine's class path.
#[derive(Debug, Clone, Default)]
pub struct GapSetting {
    pub mode: GapMode,
    pub contracts: std::sync::Arc<BTreeMap<Gap, Closure>>,
    pub class_dir: Option<std::path::PathBuf>,
}

impl From<GapMode> for GapSetting {
    fn from(mode: GapMode) -> GapSetting {
        GapSetting { mode, ..GapSetting::default() }
    }
}

impl GapRecord {
    /// The gap as a verdict's line names it: `id: call at site, ...`.
    pub fn line(&self) -> String {
        format!("{}: {} {}, at {}", self.id, self.call, self.approximation, self.sites.join(", "))
    }
}

/// The records of gaps with the sites that meet them, under the JDK `jdk`, treated as `treatment` (none for a scan).
/// A gap with no assume form is refused, whatever `treatment` says of the others.
pub fn records(gaps: &BTreeMap<Gap, BTreeSet<Site>>, jdk: Option<&str>, treatment: Option<GapTreatment>) -> Vec<GapRecord> {
    gaps.iter()
        .map(|(g, sites)| {
            let treatment = match treatment {
                Some(GapTreatment::Assumed) if !g.kind.assumable() => Some(GapTreatment::Refused),
                t => t,
            };
            GapRecord { id: g.id(jdk), kind: g.kind, call: g.call(), sites: sites.iter().map(Site::display).collect(), approximation: g.kind.approximation().to_string(), jbmc: g.jbmc_implements(), treatment, contract: None, checker: None }
        })
        .collect()
}

/// The records of the gaps contracts closed, with the sites where each was applied.
pub fn contract_records(applied: &BTreeMap<Gap, BTreeSet<Site>>, contracts: &BTreeMap<Gap, Closure>, jdk: Option<&str>) -> Vec<GapRecord> {
    let mut out = records(applied, jdk, Some(GapTreatment::Contract));
    for (r, g) in out.iter_mut().zip(applied.keys()) {
        r.contract = contracts.get(g).map(|c| c.contract.clone());
    }
    out
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
    /// It refuses the call: a floating-point or array result, or floating-point arguments, which it does not have.
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
        Ok(t) if crate::harness::expr::ty_of(&t).is_some() => JdkCall::Gap(GapKind::JdkPrimitiveMethod),
        _ => JdkCall::Refused,
    }
}

/// How the engine treats a static call of the JDK `owner.name(descriptor)` that no model of `lib/models` runs: one
/// it models ([`super::models_jdk_static`]) is exact, one with a floating-point parameter or result, or an array
/// result, is refused, and any other is a `jdk-static-method` gap. The engine and the scan share it.
pub fn jdk_static_call(owner: &str, name: &str, descriptor: &str) -> JdkCall {
    let Ok(d) = MethodDescriptor::parse(descriptor) else { return JdkCall::Refused };
    let floating = |t: &Type| matches!(t, Type::Float | Type::Double);
    if d.params.iter().any(floating) || matches!(d.ret, Type::Float | Type::Double | Type::Array(_)) {
        return JdkCall::Refused;
    }
    if super::models_jdk_static(owner, name) {
        return JdkCall::Exact;
    }
    JdkCall::Gap(GapKind::JdkStaticMethod)
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
                    } else {
                        match jdk_static_call(&member.owner, &member.name, &member.descriptor) {
                            JdkCall::Exact => *self.scan.exact.entry(format!("{}.{}", member.owner.replace('/', "."), member.name)).or_default() += 1,
                            JdkCall::Gap(kind) => self.gap(kind, &member.owner, &member.name, &member.descriptor, site),
                            JdkCall::Refused => self.refuse("floating point or an array result of a static JDK method", java_call(&member.owner, &member.name, &member.descriptor), &site),
                        }
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
                        JdkCall::Refused => self.refuse("a floating-point or array result of a JDK instance method", java_call(&member.owner, &member.name, &member.descriptor), &site),
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

#[cfg(test)]
mod tests {
    use super::*;

    /// Step 3c of `llm-dlc/loops/sound-verdicts.md`: a static JDK method the engine does not model, and a JDK
    /// method with a primitive result, are gaps with no assume form, which only a contract closes; a call JBMC
    /// has the bytecode of is one `--engine auto` asks it about.
    #[test]
    fn a_call_whose_value_the_proof_reads_is_a_gap_with_no_assume_form() {
        assert_eq!(jdk_static_call("java/lang/Integer", "numberOfLeadingZeros", "(I)I"), JdkCall::Gap(GapKind::JdkStaticMethod));
        assert_eq!(jdk_static_call("java/util/Arrays", "fill", "([II)V"), JdkCall::Gap(GapKind::JdkStaticMethod));
        assert_eq!(jdk_static_call("java/lang/Math", "addExact", "(II)I"), JdkCall::Exact);
        assert_eq!(jdk_static_call("java/lang/Math", "sqrt", "(D)D"), JdkCall::Refused);
        assert_eq!(jdk_static_call("java/util/Arrays", "copyOf", "([II)[I"), JdkCall::Refused);
        let cp = ClassPath::new().with_default_jdk();
        assert_eq!(jdk_instance_call(&cp, "java/util/Random", "nextInt", "(I)I"), JdkCall::Gap(GapKind::JdkPrimitiveMethod));
        assert_eq!(jdk_instance_call(&cp, "java/util/BitSet", "get", "(I)Z"), JdkCall::Gap(GapKind::JdkPrimitiveMethod));
        assert_eq!(jdk_instance_call(&cp, "java/util/Random", "nextDouble", "()D"), JdkCall::Refused);
        for kind in GapKind::ALL {
            assert_eq!(GapKind::from_name(kind.name()), Some(kind));
            assert_eq!(kind.assumable(), !matches!(kind, GapKind::JdkPrimitiveMethod | GapKind::JdkStaticMethod), "{}", kind.name());
        }
        let nlz = Gap { kind: GapKind::JdkStaticMethod, owner: "java/lang/Integer".into(), name: "numberOfLeadingZeros".into(), descriptor: "(I)I".into() };
        assert_eq!(nlz.id(Some("25")), "jdk-static-method:java.lang.Integer.numberOfLeadingZeros(I)I@jdk-25");
        assert!(nlz.jbmc_implements(), "JBMC is given java.lang.Integer's bytecode");
        let next = Gap { kind: GapKind::JdkPrimitiveMethod, owner: "java/util/Random".into(), name: "nextInt".into(), descriptor: "(I)I".into() };
        assert!(!next.jbmc_implements(), "JBMC stubs java.util.Random");
        // Under assume, a gap with no approximation is refused, and the others assumed.
        let met: BTreeMap<Gap, BTreeSet<Site>> = [(nlz, BTreeSet::new()), (Gap { kind: GapKind::JdkConstructor, owner: "java/util/Random".into(), name: "<init>".into(), descriptor: "(J)V".into() }, BTreeSet::new())].into_iter().collect();
        let treatments: Vec<_> = records(&met, None, Some(GapTreatment::Assumed)).into_iter().map(|r| (r.kind, r.treatment)).collect();
        assert_eq!(treatments, [(GapKind::JdkConstructor, Some(GapTreatment::Assumed)), (GapKind::JdkStaticMethod, Some(GapTreatment::Refused))]);
    }
}
