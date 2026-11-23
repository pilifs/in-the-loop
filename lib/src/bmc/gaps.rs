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
//! | `class-initializer` | takes the class's `<clinit>` to have run already, and thrown nothing (an initializer it does not run, [`runs_initializer`]: one outside its fragment; it runs any other, an enum's included) | runs it at the class's first `new`, `getstatic`, `putstatic` or `invokestatic` (JVMS §5.5), after its superclasses' and those of its superinterfaces that declare a default method, and it may throw (`ExceptionInInitializerError`) or set state | yes |
//! | `jdk-primitive-method` | nothing: refused as under strict | runs it, and returns a value the engine could only make up (`Random.nextInt(bound)`), or throws | yes |
//! | `jdk-static-method` | nothing: refused as under strict | runs a static JDK method the engine does not model (`Integer.numberOfTrailingZeros`, `Arrays.fill`), which may return any value, change an argument array, or throw | yes |
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
//! Nor are the String methods it models on a String's content ([`super::models_string_method`]): on a String whose
//! content it doesn't hold (a number's digits) it meets the call as the gap it was, where it runs it. The engine
//! runs them on a String whatever class the call names (`Object.equals`, `CharSequence.length`), as the JVM
//! dispatches them; the scan, which sees the class named and not the receiver, reports such a call as the gap it
//! may be. Nor are `Objects.requireNonNull` and `Pattern.compile` of a constant regular expression of the plain
//! form or of the checker's own syntax ([`super::models_jdk_reference_static`], [`crate::jdk_facts::plain_regex`],
//! [`super::regex::compiles_constant`]), nor the calls of the
//! `HashMap` model (`lib/models/java/util/HashMap.java`: its two constructors, `put`, `get`, `containsKey`,
//! `size`, `isEmpty`), each with an evidence record of `values::OPERATIONS`, nor those of the `LinkedHashMap`
//! model over it (its constructor, `values()`, the collection's `size` and `iterator`, the iterator's `hasNext`
//! and `next`) and of the model of the list `Arrays.asList` returns (`lib/models/java/util/lists`: `size`, `get`,
//! `toArray()`), whose evidence is `claims.M` (`lib/tests/claims.rs`). Nor are the
//! calls of the immutable-list models an evidence record of `values::OPERATIONS` samples, including the fixed
//! and varargs factories, element searches, `copyOf`, indexed access and the iterator. Other methods called
//! from outside the models, including `equals`, `hashCode` and `addAll`, remain outside the profile. Both the engine and the scan take each
//! for the JDK call it names ([`outside_the_list_records`]), a gap of its kind.
//! Nor is an initializer the check has the observed state of (`--observed-initializer`, [`crate::observed`]): it is
//! neither run nor walked, and what the run then rests on is stated with its result.
//! Nor is an application class's initializer the engine runs, as the JVM does, since Phase 5 of
//! `llm-dlc/loops/engine-priorities.md`: one whose code, and the application methods it calls, are in the fragment.
//! The scan counts those it relied on. A construct the engine refuses (floating point, a static field of the JDK
//! written, an unsupported floating-point operation or array result of a JDK method, ...) is not a gap either: it ends the proof
//! with no verdict, as it should, in either mode. The scan lists those reasons too, since a method that has one is
//! outside the engine whatever its gaps. `monitorenter` and `monitorexit` are implemented: they throw
//! `NullPointerException` on null and otherwise do nothing, which is all they do in a run of one thread.
//!
//! [`scan`] walks the methods a set of roots may reach, as the engine resolves them: the application's own methods
//! and the static methods of the tool's models. A virtual or interface call is followed into the method each
//! class has for it whose objects the walk has seen made, by a `new` it walked or by the harness (a root's
//! constructor, and the constructors of its parameters' classes in turn), since the receiver's class picks one
//! ([`Walker::dispatch`], rapid type analysis), and is classified when the walk has seen them all
//! ([`Walker::settle`]). An object the walk never saw made is one a gap made (a JDK constructor or method), met
//! where the engine runs the call. Following every class below the call's owner instead reached, for a call on a
//! `java.util.Map` in a class initializer, every `Map` of the application's libraries. It reads every instruction
//! of each method, so it may report a gap on a path no input takes. The harness itself, and the
//! expressions of a property or relation compiled into it, are not walked. An initializer the engine runs is
//! walked like a method; one that is a gap is not, so a class that only such an initializer initializes is not
//! reached. Step 1a of
//! `llm-dlc/loops/sound-verdicts.md`: what strictness would cost each recorded example. Each `class-initializer`
//! gap's `<clinit>` is given a shape ([`initializer_shape`]), by which Phase 4b of
//! `llm-dlc/loops/engine-priorities.md` counts them.

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::fmt::Write as _;
use std::sync::OnceLock;

use serde::Serialize;

use crate::classfile::{Insn, MemberRef, MethodDescriptor, Type};
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
    /// The shape of each `class-initializer` gap's `<clinit>` ([`initializer_shape`]), by class.
    pub initializers: BTreeMap<String, Initializer>,
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
    /// The class initializers the engine takes the observed state of in place of running them
    /// ([`crate::observed`]), in any mode.
    pub observed: std::sync::Arc<crate::observed::Observations>,
    /// The models on request the engine runs ([`crate::models::ON_REQUEST`]), by internal name, in any mode.
    pub models: std::sync::Arc<BTreeSet<String>>,
    /// The library methods a stand-in sampled on a JVM replaces ([`super::StandIn`]), in any mode.
    pub stand_ins: std::sync::Arc<Vec<super::StandIn>>,
    /// The previous version of a pair the check holds beside the new one ([`crate::relocate::Previous`]).
    pub previous: Option<std::sync::Arc<crate::relocate::Previous>>,
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
    /// The shape of each `class-initializer` gap's `<clinit>`.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub initializers: Vec<Initializer>,
}

impl Scan {
    pub fn records(&self) -> Vec<GapRecord> {
        records(&self.gaps, self.jdk.as_deref(), None)
    }

    pub fn record(&self, roots: &[String]) -> ScanRecord {
        ScanRecord { roots: roots.to_vec(), methods: self.methods.len(), jdk: self.jdk.clone(), gaps: self.records(), exact: self.exact.clone(), refused: self.refused.clone(), initializers: self.initializers.values().cloned().collect() }
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
        for i in self.initializers.values() {
            let _ = writeln!(out, "  initializer of {}: {} ({})", i.class, i.shape.name(), i.traits.iter().copied().collect::<Vec<_>>().join(", "));
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
/// nothing, and those of the JDK's exceptions that take nothing, a message, or a message and a cause, and only pass
/// them up to `Throwable`'s ([`super::throwables::plain_constructor`]), which sets the message and the cause (the
/// own checker keeps them, [`super::throwables`]) and throws nothing. A JDK exception's constructor that does more
/// (`UnknownFormatConversionException(String)` throws `NullPointerException` for null) is a gap like any other.
pub fn exact_jdk_call(cp: &ClassPath, owner: &str, name: &str, descriptor: &str) -> bool {
    if name != "<init>" {
        return false;
    }
    // `AbstractCollection()` is the JDK's empty protected constructor, which the immutable lists' model
    // (`ImmutableCollections.AbstractImmutableList`, run by the own checker) calls as the JDK's lists do; and so
    // is `AbstractList()`, which the model of `Arrays.asList`'s list calls, and `AbstractSet()` (which calls
    // `AbstractCollection()` alone), which the `HashSet` model calls.
    if (owner == "java/lang/Object" || owner == "java/lang/Record" || owner == "java/util/AbstractCollection" || owner == "java/util/AbstractList" || owner == "java/util/AbstractSet") && descriptor == "()V" {
        return true;
    }
    crate::classpath::is_jdk_name(owner) && super::throwables::plain_constructor(cp, owner, descriptor)
}

/// The JDK interfaces the immutable-list models and the `HashMap` model implement that no other object the engine
/// holds does, unless a gap made it: a `java.util` collection, iterator or map is never a parameter of a check but
/// one of the list models' (the values adapter refuses any other implementation), and is otherwise made by a
/// constructor of a model (`new HashMap()`), or by a JDK constructor or a JDK method, each a gap where it is made.
const MODEL_INTERFACES: &[&str] = &["java/util/List", "java/util/Collection", "java/lang/Iterable", "java/util/Iterator", "java/util/Map"];

/// Whether a virtual or interface call `owner.name(descriptor)` reaches only methods the engine runs, so that the
/// scan counts it as no gap: `owner` is one of the models the engine runs ([`crate::models::CHECKER_RUNS`]), whose
/// subclasses are the models' own, or one of [`MODEL_INTERFACES`]; a model implements the method
/// (`overrides`, the walk's), and every application class below `owner` has code for it too, its own or a model's.
/// On a receiver a gap made, the engine meets the JDK call where it runs it, as before.
fn dispatched_to_models(cp: &ClassPath, owner: &str, name: &str, descriptor: &str, overrides: &[String], made: &BTreeSet<String>) -> bool {
    if !(cp.runs_model(owner) || MODEL_INTERFACES.contains(&owner)) || !overrides.iter().any(|o| cp.runs_model(o)) {
        return false;
    }
    made.iter().filter(|n| cp.is_application(n) && cp.is_subtype(n, owner)).all(|n| cp.checker_method(n, name, descriptor).is_some_and(|(c, m)| cp.checker_runs(&c.name) && m.code.is_some()))
}

/// Whether a call from code of class `caller` into `callee`, one of the immutable-list models the engine runs
/// ([`crate::models::of_the_list_family`]), is outside the values models: no evidence record samples
/// `name(descriptor)` ([`crate::values::samples_list_call`]). The engine and the scan then take the call for the JDK call it names, a gap (or a
/// refusal, for an array result), and don't run or walk the model's method. The models' calls among themselves
/// are theirs, never outside.
pub fn outside_the_list_records(caller: &str, callee: &str, name: &str, descriptor: &str) -> bool {
    crate::models::of_the_list_family(callee) && !crate::models::of_the_list_family(caller) && !crate::values::samples_list_call(name, descriptor)
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

/// Whether the own checker models an instance call of the JDK on an object whose content it holds: a
/// `StringBuilder`'s constructors and methods ([`super::strings`]), a class literal's name and loader, whether a
/// Logger logs a level and what logging a line does, `new ArrayList()` and a `ConcurrentHashMap` made empty ([`super::runtime`]). They are the own checker's alone: to JBMC the same calls are its stubs
/// ([`crate::jbmc_gaps`] asks [`exact_jdk_call`], never this), and a contract for one is still a contract for a gap
/// ([`unmodelled_instance_call`]), which the engine applies in place of its model where one is given.
pub fn modelled_jdk_call(owner: &str, name: &str, descriptor: &str) -> bool {
    super::strings::models_builder(owner, name, descriptor)
        || (owner == "java/lang/String" && name == "<init>" && matches!(descriptor, "([BIII)V" | "([CII)V" | "([C)V" | "(Ljava/lang/String;)V"))
        || super::runtime::models_instance(owner, name, descriptor)
        || super::runtime::models_logging(owner, name, descriptor)
        || (name == "<init>" && (super::runtime::plain_constructor(owner, descriptor) || super::runtime::capacity_constructor(owner, descriptor)))
}

/// How the engine treats an instance call `owner.name(descriptor)` that runs JDK code: the one classification the
/// engine and the scan share. A call the engine models on content it holds ([`modelled_jdk_call`]) is no gap.
pub fn jdk_instance_call(cp: &ClassPath, owner: &str, name: &str, descriptor: &str) -> JdkCall {
    if modelled_jdk_call(owner, name, descriptor) {
        return JdkCall::Exact;
    }
    unmodelled_instance_call(cp, owner, name, descriptor)
}

/// What an instance call of the JDK is where the engine has no model of its own for it, or is given a contract in
/// place of the model: exact for the constructors that do nothing a proof observes, refused, or a gap of the kind
/// its result gives it. A contract is read against this ([`crate::gap_contracts`]).
pub fn unmodelled_instance_call(cp: &ClassPath, owner: &str, name: &str, descriptor: &str) -> JdkCall {
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
    // A model that makes an array (`Arrays.copyOf`) is one before an array result is refused.
    if super::bytes::models_static(owner, name, descriptor) || super::strings::models_static(owner, name, descriptor)
        || super::arraycopy::is_call(owner, name, descriptor) || super::floating::models_static(owner, name, descriptor) {
        return JdkCall::Exact;
    }
    if d.params.iter().any(floating) || matches!(d.ret, Type::Float | Type::Double | Type::Array(_)) {
        return JdkCall::Refused;
    }
    if super::models_jdk_reference_static(owner, name, descriptor) || super::models_jdk_static(owner, name) {
        return JdkCall::Exact;
    }
    JdkCall::Gap(GapKind::JdkStaticMethod)
}

/// The object arguments a string concatenation by `invokedynamic` would convert with `toString`: every parameter
/// of its descriptor that is an object other than a `String` (a `string-conversion` gap each).
pub fn converted_arguments(descriptor: &MethodDescriptor) -> Vec<String> {
    descriptor.params.iter().filter_map(|p| match p {
        Type::Object(class) if !matches!(class.as_str(), "java/lang/String" | "java/lang/Character") => Some(class.clone()),
        _ => None,
    }).collect()
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
    if !cp.checker_statics(class) || !seen.insert(class.to_string()) {
        return;
    }
    let Some(cf) = cp.checker_class(class) else { return };
    for s in initialization_supers(cp, class) {
        initializers_of(cp, &s, out, seen);
    }
    if cf.method("<clinit>", "()V").is_some() {
        out.push(class.to_string());
    }
}

/// What the JVM initializes before `class` (JVMS §5.5, step 7), in order: for a class, its superclass, then each of
/// its superinterfaces, direct or indirect, that declares a non-abstract instance method (a default method), in the
/// order of a recursive enumeration that lists an interface's superinterfaces before it; for an interface, nothing.
/// Application classes only: a JDK class is taken to be initialized already, and so is a class of a JDK package
/// that an entry of the class path holds (`javax.servlet`'s), unless the check has the observed state of its
/// initializer ([`crate::observed`]).
pub fn initialization_supers(cp: &ClassPath, class: &str) -> Vec<String> {
    let Ok(Some(cf)) = cp.application(class) else { return Vec::new() };
    if cf.is_interface() {
        return Vec::new();
    }
    // A class of a JDK package counts as the JDK's unless the check has the observed state of its initializer.
    fn of_the_jdk(cp: &ClassPath, name: &str) -> bool {
        crate::classpath::is_jdk_name(name) && !cp.observed_initializers.borrow().contains(name)
    }
    let mut out: Vec<String> = cf.super_class.iter().filter(|s| !of_the_jdk(cp, s) && cp.is_application(s)).cloned().collect();
    fn enumerate(cp: &ClassPath, i: &str, out: &mut Vec<String>, seen: &mut BTreeSet<String>) {
        if of_the_jdk(cp, i) || !seen.insert(i.to_string()) {
            return;
        }
        let Ok(Some(icf)) = cp.application(i) else { return };
        for s in &icf.interfaces {
            enumerate(cp, s, out, seen);
        }
        if icf.methods.iter().any(|m| !m.is_static() && !m.is_abstract()) {
            out.push(i.to_string());
        }
    }
    let mut seen = BTreeSet::new();
    for i in &cf.interfaces {
        enumerate(cp, i, &mut out, &mut seen);
    }
    out
}

/// A straight-line initializer that constructs final object or array constants through
/// application code. Strict checking can execute these assignments and their callees
/// path by path. A refusal in an untaken constructor branch need not block every use
/// of the class. This predicate chooses work to attempt; it proves nothing about it.
pub(super) fn builds_static_objects(cp: &ClassPath, cf: &crate::classfile::ClassFile) -> bool {
    let Some(code) = cf.method("<clinit>", "()V").and_then(|m| m.code.as_ref()) else { return false };
    let Ok(insns) = code.instructions() else { return false };
    if cp.is_application(&cf.name) && assertion_prologue(cf, &insns).is_some() { return true; }
    if cp.is_application(&cf.name) {
        // Optional dependency discovery uses the declaring class's loader and handles lookup failures
        // in its own bytecode. A shared empty array is another common prefix of a metadata cache.
        // In both cases execute to the end, including subsequent calls and exception handlers.
        match insns.as_slice() {
            [(_, Insn::InvokeStatic(call)), (_, Insn::PutStatic(slot)), (_, Insn::Return(None))]
                if cf.pool.member(*call).is_ok_and(|m| cp.is_application(&m.owner) && m.descriptor == "()Z")
                    && cf.pool.member(*slot).is_ok_and(|m| m.owner == cf.name && m.descriptor == "Z"
                        && cf.field(&m.name).is_some_and(|f| f.descriptor == "Z" && f.is_final() && f.is_static())) => return true,
            [(_, Insn::Ldc(c)), (_, Insn::InvokeVirtual(m)), ..] if cf.pool.class_name(*c).ok() == Some(&cf.name)
                && cf.pool.member(*m).is_ok_and(|m| (m.owner.as_str(), m.name.as_str(), m.descriptor.as_str())
                    == ("java/lang/Class", "getClassLoader", "()Ljava/lang/ClassLoader;")) => return true,
            [(_, Insn::IConst(0)), (_, Insn::ANewArray(_)), (_, Insn::PutStatic(slot)), ..]
                if cf.pool.member(*slot).is_ok_and(|m| m.owner == cf.name && m.descriptor.starts_with('[')
                    && cf.field(&m.name).is_some_and(|f| f.is_final() && f.is_static() && f.descriptor == m.descriptor)) => return true,
            _ => {}
        }
    }
    // A straight-line initializer can publish a singleton before configuring it.
    // Execute the entire initializer, including later calls, static writes and failures.
    if let [(_, Insn::New(owner)), (_, Insn::Dup), (_, Insn::InvokeSpecial(ctor)), (_, Insn::PutStatic(slot)), ..] = insns.as_slice() {
        if code.exception_table.is_empty() && cp.is_application(&cf.name) && insns.iter().all(|(_, op)| op.targets().is_empty())
            && cf.pool.class_name(*owner).is_ok_and(|name| cp.is_application(name)
                && cf.pool.member(*ctor).is_ok_and(|m| m.owner == name && m.name == "<init>" && m.descriptor == "()V"))
            && cf.pool.member(*slot).is_ok_and(|m| m.owner == cf.name && cf.field(&m.name).is_some_and(|f|
                f.is_static() && f.is_final() && f.descriptor == m.descriptor)) {
            return true;
        }
    }
    let mut writes_constant = false;
    code.exception_table.is_empty() && insns.iter().all(|(_, insn)| match insn {
        Insn::Nop | Insn::AConstNull | Insn::IConst(_) | Insn::LConst(_) | Insn::FConst(_) | Insn::DConst(_)
        | Insn::Ldc(_) | Insn::Dup | Insn::Pop | Insn::NewArray(_) | Insn::ANewArray(_) | Insn::ArrayStore(_) | Insn::Return(None) => true,
        Insn::Load(crate::classfile::Kind::Ref, _) | Insn::Store(crate::classfile::Kind::Ref, _) => cp.is_application(&cf.name),
        Insn::GetStatic(i) => cf.pool.member(*i).is_ok_and(|m| m.descriptor.starts_with(['L', '['])
            && cp.resolve_field(&m.owner, &m.name, &m.descriptor).and_then(|owner| cp.load(&owner).ok().flatten())
                .is_some_and(|l| l.class.field(&m.name).is_some_and(|f| f.is_static() && f.is_final()))),
        Insn::New(i) => cf.pool.class_name(*i).is_ok_and(|class| cp.is_application(class)
            || (class == "java/util/HashMap" && cp.map_image_class(class).is_some())
            || (cp.is_application(&cf.name) && matches!(class, "java/util/HashSet" | "java/util/EnumMap"))
            || (class == crate::models::CONCURRENT_MAP && cp.concurrent_map_method("<init>", "(I)V").is_some())),
        Insn::InvokeDynamic(i) => cf.pool.invoke_dynamic(*i).ok().and_then(|(index, _, _)|
            cf.bootstrap_methods().ok()?.into_iter().nth(usize::from(index))).is_some_and(|b|
            b.method.member.owner == "java/lang/invoke/LambdaMetafactory"
                && matches!(b.method.member.name.as_str(), "metafactory" | "altMetafactory")),
        Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) | Insn::InvokeVirtual(i) | Insn::InvokeInterface(i) =>
            cf.pool.member(*i).is_ok_and(|m| cp.is_application(&m.owner)
                || cp.checked_image_class(&m.owner).is_some()
                || matches!((m.owner.as_str(), m.name.as_str(), m.descriptor.as_str()),
                    ("java/lang/Class", "getClassLoader", "()Ljava/lang/ClassLoader;")
                    | ("java/lang/Integer", "valueOf", "(I)Ljava/lang/Integer;")
                    | ("java/util/TimeZone", "getTimeZone", "(Ljava/lang/String;)Ljava/util/TimeZone;")
                    | ("java/util/HashSet", "<init>", "(I)V")
                    | ("java/util/Set", "add", "(Ljava/lang/Object;)Z")
                    | (crate::models::CONCURRENT_MAP, "newKeySet", "(I)Ljava/util/concurrent/ConcurrentHashMap$KeySetView;"))
                || cp.collection_static(&m.owner, &m.name, &m.descriptor)
                || (m.owner == crate::models::CONCURRENT_MAP && cp.concurrent_map_method(&m.name, &m.descriptor).is_some())
                || (m.owner == super::bytes::CHARSET && m.name == "name" && m.descriptor == "()Ljava/lang/String;")
                || (matches!(m.owner.as_str(), "java/util/Map" | "java/util/HashMap")
                    && cp.map_image_method("java/util/HashMap", &m.name, &m.descriptor).is_some())),
        Insn::PutStatic(i) => {
            writes_constant = true;
            cf.pool.member(*i).is_ok_and(|m| m.owner == cf.name && m.descriptor.starts_with(['L', '['])
                && cf.field(&m.name).is_some_and(|f| f.is_static() && f.is_final() && f.descriptor == m.descriptor))
        }
        _ => false,
    }) && writes_constant
}

/// The first read of its own class's assertion setting in a javac initializer.
/// This selects code to execute. The bytecode still sets the actual static field.
pub(super) fn assertion_prologue(cf: &crate::classfile::ClassFile, ops: &[(u32, Insn)]) -> Option<u32> {
    let [(_, Insn::Ldc(class)), (pc, Insn::InvokeVirtual(call)), ..] = ops else { return None };
    let method = cf.pool.member(*call).ok()?;
    if cf.pool.class_name(*class).ok()? != cf.name || method.owner != "java/lang/Class"
        || method.name != "desiredAssertionStatus" || method.descriptor != "()Z" { return None; }
    let field = cf.field("$assertionsDisabled")?;
    (field.is_static() && field.is_final() && field.descriptor == "Z"
        && ops.iter().take(8).any(|(_, i)| matches!(i, Insn::PutStatic(f) if cf.pool.member(*f)
            .is_ok_and(|m| m.owner == cf.name && m.name == field.name && m.descriptor == field.descriptor)))).then_some(*pc)
}

/// Try an application's primitive lookup-table initializer on the actual path. A
/// conservative walk through every CharacterData plane would reject a loop whose
/// indices always select Latin-1. Its writes, callees and exceptions still execute.
pub(super) fn builds_primitive_tables(cf: &crate::classfile::ClassFile) -> bool {
    let mut statics = cf.fields.iter().filter(|f| f.is_static()).peekable();
    if statics.peek().is_none() || !statics.all(|f| f.is_final() && matches!(f.descriptor.as_str(),
        "[B" | "[C" | "[S" | "[I" | "[J" | "[F" | "[D" | "[Z")) { return false; }
    let Some(code) = cf.method("<clinit>", "()V").and_then(|m| m.code.as_ref()) else { return false };
    let Ok(insns) = code.instructions() else { return false };
    insns.iter().any(|(_, op)| matches!(op, Insn::NewArray(_)))
        && insns.iter().any(|(pc, op)| op.targets().iter().any(|target| target < pc))
}

/// Whether the engine runs `class`'s `<clinit>` when a use initializes the class, rather than meeting a
/// `class-initializer` gap there: the class has one, and nothing in it, or in the application methods it calls,
/// is outside the engine's fragment ([`scan`]'s refusals). That includes a static field it reads or writes of a
/// class whose initializer the engine does not run (a constant read apart), so an enum outside keeps its
/// `$SwitchMap` classes out with it. Initializers that use each other's fields run if each would given that the
/// others do: so one runs exactly when it, and every initializer it reaches through the static fields they use, is
/// inside the fragment, which one walk of them together decides ([`Walker::runs`]). A walk that finds nothing
/// outside settles every initializer it took in, since each one's own walk is part of it. Decided once for a class
/// path, whoever asks: deciding one again for each chain of initializers that led to it took the scan of a method
/// that reaches a `Map` call minutes.
pub fn runs_initializer(cp: &ClassPath, class: &str) -> bool {
    // One the check has the observed state of: the engine has what it leaves, and a use of its static fields
    // puts nothing outside the fragment.
    if cp.observed_initializers.borrow().contains(class) {
        return true;
    }
    if let Some(&runs) = cp.initializer_runs.borrow().get(class) {
        return runs;
    }
    let together = (|| {
        let cf = cp.checker_class(class)?;
        cf.method("<clinit>", "()V")?;
        let mut w = Walker::new(cp, true);
        w.deciding_with.insert(class.to_string());
        w.enqueue(class, "<clinit>", "()V");
        while let Some((owner, name, descriptor)) = w.queue.pop_front() {
            w.walk(&owner, &name, &descriptor).ok()?;
            if !w.scan.refused.is_empty() {
                return None;
            }
        }
        w.settle();
        if !w.scan.refused.is_empty() {
            return None;
        }
        Some(w.deciding_with)
    })();
    let mut decided = cp.initializer_runs.borrow_mut();
    match together {
        Some(all) => {
            decided.extend(all.into_iter().map(|c| (c, true)));
            true
        }
        None => {
            decided.insert(class.to_string(), false);
            false
        }
    }
}

/// The shape of an application class's `<clinit>`, by which Phase 4b of `llm-dlc/loops/engine-priorities.md` counts
/// the `class-initializer` gaps to choose what the engine runs. Read from the bytecode of the initializer and of the
/// application methods it calls, transitively; the first that applies, in this order.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum InitializerShape {
    /// An enum's: each constant made by the enum's constructor, which calls `Enum.<init>(String, int)`, and
    /// `$VALUES`, an array of references.
    Enum,
    /// One that may throw: an `athrow` in it or in an application method it calls.
    Throws,
    /// One that reads or writes another class's static fields: the `$SwitchMap` class javac makes for a switch over
    /// an enum reads the enum's constants.
    OtherStatics,
    /// One that only assigns its own static fields constants or literal tables (arrays filled with constants).
    Constants,
    /// Any other: one that calls methods or constructs objects to compute its fields.
    Other,
}

impl InitializerShape {
    pub fn name(self) -> &'static str {
        match self {
            InitializerShape::Enum => "enum",
            InitializerShape::Throws => "throws",
            InitializerShape::OtherStatics => "other-statics",
            InitializerShape::Constants => "constants",
            InitializerShape::Other => "other",
        }
    }
}

/// An application class's `<clinit>`, classified ([`initializer_shape`]): its shape, and what was found in it and
/// in the application methods it calls (`athrow`, `reads-other-statics`, `writes-other-statics`,
/// `calls-application`, `calls-jdk`, `constructs`, `arrays-of-references`, `handlers`, `switch-map`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Initializer {
    pub class: String,
    pub shape: InitializerShape,
    pub traits: BTreeSet<&'static str>,
}

/// The shape of `class`'s `<clinit>`, or None when it has none (or is not an application class).
pub fn initializer_shape(cp: &ClassPath, class: &str) -> Option<Initializer> {
    let cf = cp.application(class).ok()??;
    cf.method("<clinit>", "()V")?;
    let mut traits = BTreeSet::new();
    let mut only_constants = true;
    let mut seen = BTreeSet::new();
    let mut queue = VecDeque::from([(class.to_string(), "<clinit>".to_string(), "()V".to_string())]);
    while let Some((owner, name, descriptor)) = queue.pop_front() {
        if !seen.insert((owner.clone(), name.clone(), descriptor.clone())) {
            continue;
        }
        let Some((mcf, m)) = cp.bytecode_method(&owner, &name, &descriptor) else { continue };
        let Some(code) = m.code.as_ref() else { continue };
        let Ok(insns) = code.instructions() else { continue };
        let own = mcf.name == class && name == "<clinit>";
        if !code.exception_table.is_empty() {
            traits.insert("handlers");
        }
        for (_, insn) in insns {
            match insn {
                Insn::AThrow => {
                    traits.insert("athrow");
                }
                Insn::GetStatic(i) | Insn::PutStatic(i) => {
                    let Ok(f) = mcf.pool.member(i) else { continue };
                    let put = matches!(insn, Insn::PutStatic(_));
                    if f.owner != class {
                        traits.insert(if put { "writes-other-statics" } else { "reads-other-statics" });
                    }
                    if f.name.starts_with("$SwitchMap$") {
                        traits.insert("switch-map");
                    }
                    if own && (!put || f.owner != class) {
                        only_constants = false;
                    }
                }
                Insn::New(_) => {
                    traits.insert("constructs");
                    only_constants &= !own;
                }
                Insn::ANewArray(_) | Insn::MultiANewArray(..) => {
                    traits.insert("arrays-of-references");
                }
                Insn::InvokeStatic(i) | Insn::InvokeSpecial(i) | Insn::InvokeVirtual(i) | Insn::InvokeInterface(i) => {
                    only_constants &= !own;
                    let Ok(c) = mcf.pool.member(i) else { continue };
                    match cp.bytecode_method(&c.owner, &c.name, &c.descriptor).filter(|(k, m)| cp.is_application(&k.name) && m.code.is_some()) {
                        Some((k, _)) => {
                            traits.insert("calls-application");
                            queue.push_back((k.name.clone(), c.name.clone(), c.descriptor.clone()));
                        }
                        None => {
                            traits.insert("calls-jdk");
                        }
                    }
                }
                Insn::InvokeDynamic(_) => {
                    traits.insert("calls-jdk");
                    only_constants &= !own;
                }
                Insn::Nop | Insn::AConstNull | Insn::IConst(_) | Insn::LConst(_) | Insn::FConst(_) | Insn::DConst(_) | Insn::Ldc(_) | Insn::Dup | Insn::Pop | Insn::NewArray(_) | Insn::ArrayStore(_) | Insn::Return(None) => {}
                _ => only_constants &= !own,
            }
        }
    }
    let shape = if cf.is_enum() && cf.super_class.as_deref() == Some("java/lang/Enum") {
        InitializerShape::Enum
    } else if traits.contains("athrow") {
        InitializerShape::Throws
    } else if traits.contains("reads-other-statics") || traits.contains("writes-other-statics") {
        InitializerShape::OtherStatics
    } else if only_constants {
        InitializerShape::Constants
    } else {
        InitializerShape::Other
    };
    Some(Initializer { class: class.replace('/', "."), shape, traits })
}

struct Walker<'a> {
    cp: &'a ClassPath,
    scan: Scan,
    queue: VecDeque<(String, String, String)>,
    seen: BTreeSet<(String, String, String)>,
    initialised: BTreeSet<String>,
    /// False for a scan. True for the walk that decides whether an initializer runs ([`runs_initializer`]): it
    /// initializes no class by a use, and walks with it, in `deciding_with`, the initializers of the classes whose
    /// static fields it reads or writes, which must run for it to.
    deciding: bool,
    deciding_with: BTreeSet<String>,
    /// The classes the walk has seen made, by a `new` or by the harness (a root's constructor): the receivers a
    /// virtual or interface call may have ([`Walker::dispatch`]).
    made: BTreeSet<String>,
    /// The virtual and interface calls the walk has met (the calling class, then the call), each followed again
    /// into a class made later.
    dispatched: BTreeSet<(String, String, String, String)>,
    /// The virtual and interface calls that resolved to no application method (the calling class, the call and its
    /// site), to classify when the walk ends ([`Walker::settle`]).
    deferred: Vec<(String, String, String, String, Site)>,
}

/// Scans what the roots (`(owner, name, descriptor)`, internal names) may reach. A root that is a static method
/// or a constructor initialises its class, as the harness's call does.
pub fn scan(cp: &ClassPath, roots: &[MemberRef]) -> Result<Scan, Error> {
    Ok(walked(cp, roots, &[])?.scan)
}

/// The methods a walk from `roots` may call on an object of the application interface `interface` that a check gives
/// an implementation of ([`crate::given`]), by name and descriptor: every virtual or interface call the walk meets
/// whose owner the interface is or extends. The interface's default methods are walked, as on any object of it.
pub fn calls_on_given(cp: &ClassPath, roots: &[MemberRef], interface: &str) -> Result<BTreeSet<(String, String)>, Error> {
    let w = walked(cp, roots, &[interface])?;
    Ok(w.dispatched.iter().filter(|(_, owner, _, _)| cp.is_subtype(interface, owner)).map(|(_, _, name, descriptor)| (name.clone(), descriptor.clone())).collect())
}

/// The walk of what `roots` may reach, with an object of each of the interfaces `given` made by the harness.
fn walked<'a>(cp: &'a ClassPath, roots: &[MemberRef], given: &[&str]) -> Result<Walker<'a>, Error> {
    let mut w = Walker::new(cp, false);
    w.scan.jdk = jdk_release();
    for interface in given {
        w.make(interface);
    }
    for r in roots {
        let root = Site { class: "harness".into(), method: "check".into(), line: None };
        w.initialise(&r.owner, &root);
        // A root's constructor is the harness's call: it makes an object of the class, and of each class among the
        // constructor's parameters in turn, as an object made by its constructor is made.
        if r.name == "<init>" {
            w.made_by_harness(&r.owner, &r.descriptor);
        }
        w.enqueue(&r.owner, &r.name, &r.descriptor);
    }
    while let Some((owner, name, descriptor)) = w.queue.pop_front() {
        w.walk(&owner, &name, &descriptor)?;
    }
    w.settle();
    Ok(w)
}

impl<'a> Walker<'a> {
    fn new(cp: &'a ClassPath, deciding: bool) -> Walker<'a> {
        Walker { cp, scan: Scan::default(), queue: VecDeque::new(), seen: BTreeSet::new(), initialised: BTreeSet::new(), deciding, deciding_with: BTreeSet::new(), made: BTreeSet::new(), dispatched: BTreeSet::new(), deferred: Vec::new() }
    }

    /// Whether the engine runs `class`'s `<clinit>` ([`runs_initializer`]). In the walk that decides one, an
    /// initializer already known not to run decides it; any other is walked with it, and runs if the walk finds
    /// nothing outside the fragment.
    fn runs(&mut self, class: &str) -> bool {
        if !self.deciding || self.cp.observed_initializers.borrow().contains(class) {
            return runs_initializer(self.cp, class);
        }
        if let Some(&runs) = self.cp.initializer_runs.borrow().get(class) {
            if !runs {
                return false;
            }
        }
        if self.deciding_with.insert(class.to_string()) {
            self.enqueue(class, "<clinit>", "()V");
        }
        true
    }

    /// An object of `class` is made: every virtual or interface call met so far that it may receive is followed
    /// into the method it runs for it.
    fn make(&mut self, class: &str) {
        if !self.made.insert(class.to_string()) {
            return;
        }
        for (caller, owner, name, descriptor) in self.dispatched.clone() {
            if self.cp.is_subtype(class, &owner) {
                self.dispatch_to(&caller, class, &name, &descriptor);
            }
        }
    }

    /// The harness makes an object of `class` by the constructor of `descriptor`, and an object of each
    /// application class among its parameters by that class's constructors in turn.
    fn made_by_harness(&mut self, class: &str, descriptor: &str) {
        if self.made.contains(class) {
            return;
        }
        self.make(class);
        let Ok(d) = MethodDescriptor::parse(descriptor) else { return };
        for t in &d.params {
            let Type::Object(inner) = t else { continue };
            let Ok(Some(cf)) = self.cp.application(inner) else { continue };
            for init in cf.methods.iter().filter(|m| m.name == "<init>") {
                self.made_by_harness(inner, &init.descriptor);
            }
        }
    }

    /// Follows a call from code of `caller` of `name(descriptor)` on a receiver of `class` into the method that
    /// runs: the one an application class, or a model the engine runs, has code for, unless it is a list model's
    /// that no evidence record samples ([`outside_the_list_records`]). Its declaring class, when there is one.
    fn dispatch_to(&mut self, caller: &str, class: &str, name: &str, descriptor: &str) -> Option<String> {
        let (cf, m) = self.cp.checker_method(class, name, descriptor)?;
        if !self.cp.checker_runs(&cf.name) || m.code.is_none() || outside_the_list_records(caller, &cf.name, name, descriptor) {
            return None;
        }
        self.enqueue(&cf.name, name, descriptor);
        Some(cf.name.clone())
    }

    /// The methods a virtual or interface call of `owner.name(descriptor)` may run that the engine runs as
    /// bytecode, each followed, by the class that declares it: the receiver's class picks the method, and a
    /// receiver is an object the walk has seen made ([`Walker::make`]: rapid type analysis). Following every
    /// class below `owner` instead reached, for a call on a `java.util.Map` in a class initializer, every `Map`
    /// of the application's libraries, and found the initializer outside the fragment for what one of them does.
    /// An object the walk never saw made (one a static field held before, one a JDK call returned) is met where
    /// the engine runs the call.
    fn dispatch(&mut self, caller: &str, owner: &str, name: &str, descriptor: &str) -> Vec<String> {
        self.dispatched.insert((caller.to_string(), owner.to_string(), name.to_string(), descriptor.to_string()));
        let receivers: Vec<String> = self.made.iter().filter(|c| self.cp.is_subtype(c, owner)).cloned().collect();
        let mut out: Vec<String> = receivers.iter().filter_map(|c| self.dispatch_to(caller, c, name, descriptor)).collect();
        out.sort();
        out.dedup();
        out
    }

    /// Classifies the virtual and interface calls that resolved to no application method, once the walk has found
    /// every object made: a call the models the engine runs implement for every receiver made, a String method
    /// modelled on content, or the JDK call it names. Following a call again follows nothing new.
    fn settle(&mut self) {
        for (caller, owner, name, descriptor, site) in std::mem::take(&mut self.deferred) {
            let overrides = self.dispatch(&caller, &owner, &name, &descriptor);
            // A call on a list, its iterator or a map that the models the engine runs implement (`size`, `get`,
            // `iterator`, `next` …), walked among the overrides: see [`dispatched_to_models`].
            if dispatched_to_models(self.cp, &owner, &name, &descriptor, &overrides, &self.made) {
                let models = if matches!(owner.as_str(), "java/util/Map" | "java/util/HashMap") { "on the map model" } else { "on the list models" };
                *self.scan.exact.entry(format!("{}.{name}{descriptor} ({models})", owner.replace('/', "."))).or_default() += 1;
                continue;
            }
            // A String method the engine models on content it holds; on a String with none (a number's digits)
            // the engine meets the JDK call as a gap where it is run.
            if super::models_string_method(&owner, &name, &descriptor) {
                *self.scan.exact.entry(format!("{}.{name}{descriptor} (on its content)", owner.replace('/', "."))).or_default() += 1;
                continue;
            }
            // The method is the JDK's, on this receiver: the engine's fallback.
            match jdk_instance_call(self.cp, &owner, &name, &descriptor) {
                JdkCall::Exact => *self.scan.exact.entry(format!("{}.{name}{descriptor}", owner.replace('/', "."))).or_default() += 1,
                JdkCall::Gap(kind) => self.gap(kind, &owner, &name, &descriptor, site),
                JdkCall::Refused => self.refuse("a floating-point or array result of a JDK instance method", java_call(&owner, &name, &descriptor), &site),
            }
        }
        debug_assert!(self.queue.is_empty(), "a settled call followed a method the walk had not");
    }

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

    /// A use of `class` that initializes it (JVMS §5.5): each `<clinit>` that runs ([`initializers`]) is walked
    /// when the engine runs it ([`runs_initializer`]), and is otherwise a gap, recorded where the walk first
    /// reaches it. The walk that decides an initializer follows no other.
    fn initialise(&mut self, class: &str, site: &Site) {
        if self.deciding {
            return;
        }
        for c in initializers(self.cp, class) {
            if self.initialised.insert(c.clone()) {
                // An observed initializer is not the engine's to run, and not walked.
                if self.cp.observed_initializers.borrow().contains(&c) {
                    continue;
                }
                if self.runs(&c) {
                    self.enqueue(&c, "<clinit>", "()V");
                    continue;
                }
                self.gap(GapKind::ClassInitializer, &c, "<clinit>", "()V", site.clone());
                if let Some(shape) = initializer_shape(self.cp, &c) {
                    self.scan.initializers.insert(c.clone(), shape);
                }
            }
        }
    }

    /// A `getstatic` or `putstatic` (`put`) of `owner.name`: the engine holds an application class's static fields
    /// once its initializer has run, and reads a JDK field only when it is a constant
    /// ([`super::Engine::get_static`]). Initializes the class that declares the field.
    fn static_field(&mut self, owner: &str, name: &str, descriptor: &str, put: bool, site: &Site) {
        let declaring = self.cp.resolve_field(owner, name, descriptor).unwrap_or_else(|| owner.to_string());
        if !put && (self.cp.numeric_assertion_flag(&declaring, name, descriptor)
            || (declaring.as_str(), name, descriptor) == ("java/io/File", "separatorChar", "C")
            || (declaring.as_str(), name, descriptor) == ("java/util/Arrays$LegacyMergeSort", "userRequested", "Z")
            || (name == "TYPE" && descriptor == "Ljava/lang/Class;" && Type::for_wrapper(&declaring).is_some())
            || ((declaring.as_str(), name, descriptor) == ("java/util/Collections", "EMPTY_LIST", "Ljava/util/List;") && self.cp.collections_empty_singleton("emptyList"))) { return; }
        let what = format!("{}.{name}", declaring.replace('/', "."));
        let constant = !put && self.constant(&declaring, name);
        if !self.cp.checker_statics(&declaring) {
            if put {
                self.refuse("writes a static field of the JDK", what, site);
            } else if !constant {
                self.refuse("reads a static field of the JDK that is not a compile-time constant", what, site);
            }
        } else if !constant && self.cp.checker_class(&declaring).is_some_and(|cf| cf.method("<clinit>", "()V").is_some()) && !self.runs(&declaring) {
            self.refuse(if put { "writes a static field of a class whose initializer the engine does not run" } else { "reads a static field of a class whose initializer the engine does not run" }, what, site);
        }
        self.initialise(&declaring, site);
    }

    fn walk(&mut self, owner: &str, name: &str, descriptor: &str) -> Result<(), Error> {
        let Some((cf, m)) = self.cp.checker_method(owner, name, descriptor)
            .or_else(|| self.cp.numeric_image_method(owner, name, descriptor))
            .or_else(|| self.cp.library_image_method(owner, name, descriptor)) else { return Ok(()) };
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
        // The String constant the instruction before loaded, for a call that is modelled on a constant alone.
        let mut constant: Option<Vec<u16>> = None;
        for (pc, insn) in insns {
            let site = Site { class: cf.name.clone(), method: name.to_string(), line: code.line_at(pc) };
            let loaded = constant.take();
            if let Insn::Ldc(index) = insn {
                constant = cf.pool.loadable(index).ok().and_then(|c| c.string_units().map(|units| units.into_owned()));
            }
            match insn {
                Insn::Jsr(_) | Insn::Ret(_) => self.refuse("jsr/ret", "jsr".into(), &site),
                Insn::PutStatic(index) | Insn::GetStatic(index) => {
                    let member = cf.pool.member(index).map_err(|e| Error::new(e.to_string()))?;
                    self.static_field(&member.owner, &member.name, &member.descriptor, matches!(insn, Insn::PutStatic(_)), &site);
                }
                Insn::New(index) => {
                    let class = cf.pool.class_name(index).map_err(|e| Error::new(e.to_string()))?.to_string();
                    self.initialise(&class, &site);
                    self.make(&class);
                }
                Insn::InvokeDynamic(index) => {
                    let (bootstrap, _, text) = cf.pool.invoke_dynamic(index).map_err(|e| Error::new(e.to_string()))?;
                    let d = MethodDescriptor::parse(text).map_err(|e| Error::new(e.to_string()))?;
                    // A lambda or a method reference makes an object, as the engine makes it; its method runs
                    // where the interface's is called on the object. The walk that lists what a method reaches
                    // follows an application's there. The one that decides an initializer does not: making the
                    // object runs nothing, and a method it names for a class path that has another library (a
                    // logging adapter's, one for each library it looks for) is never called on this one.
                    let lambda = cf.bootstrap_methods().ok().and_then(|b| b.into_iter().nth(usize::from(bootstrap))).filter(|b| {
                        use crate::classfile::BootstrapArg::Int;
                        b.method.member.owner == "java/lang/invoke/LambdaMetafactory" && (b.method.member.name == "metafactory"
                            || (b.method.member.name == "altMetafactory" && matches!(b.args.get(3..), Some([Int(0)] | [Int(1)] | [Int(5), Int(0)]))))
                    });
                    if let Some(lambda) = lambda {
                        if let (false, Some(crate::classfile::BootstrapArg::MethodHandle(handle))) = (self.deciding, lambda.args.get(1)) {
                            if self.cp.is_application(&handle.member.owner) {
                                self.enqueue(&handle.member.owner, &handle.member.name, &handle.member.descriptor);
                            }
                        }
                        continue;
                    }
                    if d.ret != Type::Object("java/lang/String".into()) {
                        self.refuse("invokedynamic other than a lambda and string concatenation", format!("invokedynamic {text}"), &site);
                        continue;
                    }
                    for class in converted_arguments(&d) {
                        self.gap(GapKind::StringConversion, &class, "toString", "()Ljava/lang/String;", site.clone());
                    }
                }
                Insn::InvokeStatic(index) => {
                    let member = cf.pool.member(index).map_err(|e| Error::new(e.to_string()))?;
                    if super::runtime::enum_identity_read(&cf.name, name, &member) {
                        *self.scan.exact.entry("Enum.hashCode (all stable JVM identity hashes)".into()).or_default() += 1;
                    } else if member.owner == "java/lang/Enum" && member.name == "valueOf"
                        && member.descriptor == "(Ljava/lang/Class;Ljava/lang/String;)Ljava/lang/Enum;"
                        && self.cp.enum_values_field(&cf.name).is_some() && self.cp.enum_lookup_image() {
                        *self.scan.exact.entry("Enum.valueOf (checked enum constants and name)".into()).or_default() += 1;
                    } else if self.cp.platform_native(&member) {
                        *self.scan.exact.entry(format!("System.{} (all JVM values, counterexamples require reachability)", member.name)).or_default() += 1;
                    } else if self.cp.is_application(&member.owner) || self.cp.checked_image_class(&member.owner).is_some() {
                        let declaring = self.cp.bytecode_method(&member.owner, &member.name, &member.descriptor).map(|(c, _)| c.name.clone()).unwrap_or_else(|| member.owner.clone());
                        self.initialise(&declaring, &site);
                        self.enqueue(&member.owner, &member.name, &member.descriptor);
                    } else if self.cp.model(&member.owner).is_some() && self.cp.bytecode_method(&member.owner, &member.name, &member.descriptor).is_some_and(|(_, m)| m.code.is_some()) {
                        self.enqueue(&member.owner, &member.name, &member.descriptor);
                    } else if self.cp.collection_static(&member.owner, &member.name, &member.descriptor) && self.cp.library_image_method(&member.owner, &member.name, &member.descriptor).is_some() {
                        self.enqueue(&member.owner, &member.name, &member.descriptor);
                    } else if self.cp.numeric_image_method(&member.owner, &member.name, &member.descriptor).is_some() {
                        // A class initializer can call the factory on an input for which it reads no cached
                        // object. Execution checks the path it takes. The full scan lists all possible reads.
                        if !self.deciding {
                            self.enqueue(&member.owner, &member.name, &member.descriptor);
                        }
                    } else if let Some((c, _)) = self.cp.checker_method(&member.owner, &member.name, &member.descriptor).filter(|(c, m)| self.cp.checker_runs(&member.owner) && self.cp.checker_runs(&c.name) && m.code.is_some() && !outside_the_list_records(&cf.name, &c.name, &member.name, &member.descriptor)) {
                        // A model the engine runs although it is only for JBMC's class path (`List.of`), as it does.
                        self.initialise(&c.name, &site);
                        self.enqueue(&c.name, &member.name, &member.descriptor);
                    } else if (member.owner.as_str(), member.name.as_str()) == ("java/util/regex/Pattern", "compile") && super::models_jdk_reference_static(&member.owner, &member.name, &member.descriptor) && !loaded.as_ref().is_some_and(|units| crate::jdk_facts::plain_regex(units) || super::regex::compiles_constant(units)) {
                        // The engine compiles a constant regex of the plain form ([`crate::jdk_facts::plain_regex`]) or of
                        // its own syntax with a class, a group or a count ([`super::regex::compiles_constant`]) alone:
                        // any other, or one this walk doesn't see loaded just before the call, may be the gap it meets.
                        self.gap(GapKind::JdkStaticMethod, &member.owner, &member.name, &member.descriptor, site);
                    } else if (member.owner.as_str(), member.name.as_str()) == (super::locale::LOCALE, "forLanguageTag") && super::locale::models_static(&member.owner, &member.name, &member.descriptor) && !loaded.as_ref().is_some_and(|units| super::locale::plain_tag_language(units).is_some()) {
                        // The engine reads a constant language tag of the plain form alone ([`super::locale`]): any
                        // other, or one this walk doesn't see loaded just before the call, may be the gap it meets.
                        self.gap(GapKind::JdkStaticMethod, &member.owner, &member.name, &member.descriptor, site);
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
                    if special && member.name == "<init>"
                        && self.cp.numeric_image_method(&member.owner, &member.name, &member.descriptor).is_some() {
                        self.enqueue(&member.owner, &member.name, &member.descriptor);
                        continue;
                    }
                    // An array's `clone`, which the engine copies.
                    if !special && member.owner.starts_with('[') && member.name == "clone" && member.descriptor == "()Ljava/lang/Object;" {
                        *self.scan.exact.entry("array.clone()".into()).or_default() += 1;
                        continue;
                    }
                    // A list model's method no evidence record samples is the JDK call it names, called from
                    // outside the models: neither resolved to nor walked ([`outside_the_list_records`]).
                    let outside = |class: &str| outside_the_list_records(&cf.name, class, &member.name, &member.descriptor);
                    let resolved = self.cp.checker_method(&member.owner, &member.name, &member.descriptor).filter(|(c, _)| self.cp.checker_runs(&c.name) && !outside(&c.name));
                    if !special {
                        self.dispatch(&cf.name, &member.owner, &member.name, &member.descriptor);
                    }
                    // An application method; an abstract one (an enum constant's body, an interface's) is one of the
                    // overrides above on the receiver the engine dispatches on, and no call into the JDK.
                    if let Some((c, m)) = resolved {
                        if m.code.is_some() {
                            self.enqueue(&c.name, &member.name, &member.descriptor);
                        }
                        continue;
                    }
                    // Any other virtual or interface call runs what the receiver's class has for it, and the walk
                    // is still finding the objects made: classified when it ends ([`Walker::settle`]).
                    if !special {
                        self.deferred.push((cf.name.clone(), member.owner.clone(), member.name.clone(), member.descriptor.clone(), site));
                        continue;
                    }
                    // A constructor or a superclass's method that is the JDK's: the engine's fallback.
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
        // The JDK's objects the engine has one of for a run: the UTF-8 and US-ASCII charsets, `Locale`'s constants,
        // the logging levels but `OFF`, and `Boolean.TRUE` and `Boolean.FALSE`.
        if super::bytes::charset_constant(owner, name).is_some() || super::locale::constant(owner, name) || super::runtime::level_constant(owner, name).is_some() || super::runtime::truth_constant(owner, name).is_some() {
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
        assert_eq!(jdk_static_call("java/lang/Integer", "numberOfTrailingZeros", "(I)I"), JdkCall::Gap(GapKind::JdkStaticMethod));
        assert_eq!(jdk_static_call("java/lang/Integer", "numberOfLeadingZeros", "(I)I"), JdkCall::Exact);
        assert_eq!(jdk_static_call("java/lang/Long", "numberOfLeadingZeros", "(J)I"), JdkCall::Exact);
        assert_eq!(jdk_static_call("java/util/Arrays", "fill", "([II)V"), JdkCall::Gap(GapKind::JdkStaticMethod));
        assert_eq!(jdk_static_call("java/lang/Math", "addExact", "(II)I"), JdkCall::Exact);
        assert_eq!(jdk_static_call("java/lang/Math", "sqrt", "(D)D"), JdkCall::Exact);
        assert_eq!(jdk_static_call("java/lang/Math", "exp", "(D)D"), JdkCall::Refused);
        assert_eq!(jdk_static_call("java/util/Arrays", "copyOfRange", "([III)[I"), JdkCall::Refused);
        assert_eq!(jdk_static_call("java/util/Arrays", "copyOf", "([II)[I"), JdkCall::Exact);
        let cp = ClassPath::new().with_default_jdk();
        assert_eq!(jdk_instance_call(&cp, "java/util/Random", "nextInt", "(I)I"), JdkCall::Gap(GapKind::JdkPrimitiveMethod));
        assert_eq!(jdk_instance_call(&cp, "java/util/BitSet", "get", "(I)Z"), JdkCall::Gap(GapKind::JdkPrimitiveMethod));
        assert_eq!(jdk_instance_call(&cp, "java/util/Random", "nextDouble", "()D"), JdkCall::Refused);
        for kind in GapKind::ALL {
            assert_eq!(GapKind::from_name(kind.name()), Some(kind));
            assert_eq!(kind.assumable(), !matches!(kind, GapKind::JdkPrimitiveMethod | GapKind::JdkStaticMethod), "{}", kind.name());
        }
        let ntz = Gap { kind: GapKind::JdkStaticMethod, owner: "java/lang/Integer".into(), name: "numberOfTrailingZeros".into(), descriptor: "(I)I".into() };
        assert_eq!(ntz.id(Some("25")), "jdk-static-method:java.lang.Integer.numberOfTrailingZeros(I)I@jdk-25");
        assert!(ntz.jbmc_implements(), "JBMC is given java.lang.Integer's bytecode");
        let next = Gap { kind: GapKind::JdkPrimitiveMethod, owner: "java/util/Random".into(), name: "nextInt".into(), descriptor: "(I)I".into() };
        assert!(!next.jbmc_implements(), "JBMC stubs java.util.Random");
        // Under assume, a gap with no approximation is refused, and the others assumed.
        let met: BTreeMap<Gap, BTreeSet<Site>> = [(ntz, BTreeSet::new()), (Gap { kind: GapKind::JdkConstructor, owner: "java/util/Random".into(), name: "<init>".into(), descriptor: "(J)V".into() }, BTreeSet::new())].into_iter().collect();
        let treatments: Vec<_> = records(&met, None, Some(GapTreatment::Assumed)).into_iter().map(|r| (r.kind, r.treatment)).collect();
        assert_eq!(treatments, [(GapKind::JdkConstructor, Some(GapTreatment::Assumed)), (GapKind::JdkStaticMethod, Some(GapTreatment::Refused))]);
    }
}
