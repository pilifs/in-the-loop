//! The statement a verdict is about, as data (step 2a of `llm-dlc/loops/sound-verdicts.md`).
//!
//! A regression proof establishes ∀x ∈ D, A(x) ⇒ Obs(old, x) = Obs(new, x), and a property proof
//! ∀x ∈ D, A(x) ⇒ P(Obs(x)): D is the input domain ([`Domain`]), A the assumptions ([`Assumption`]), Obs what is
//! observed of a call ([`Observations`]). The proof line says the same in words, but two verdicts about different
//! statements can read alike there; here each part is a field. Beside them, what the verdict rests on: the bounds
//! and whether the search covered them ([`Bounds`]), the models of the JDK ([`Models`]), the checker and its solver
//! ([`Checker`]), the gap mode, and whether JBMC confirmed the own checker's proof (`--confirm`).
//!
//! An assumption carries its basis: stated by the claim (`--unchanged-unless`, `--assume`), made by how the harness
//! builds the statement (an input a record's constructor rejects is skipped), part of a checker's semantics (a JDK
//! class taken as initialized, a JDK method JBMC has no bytecode for), or a gap assumed under `--gaps assume` with
//! nothing to show for it. Phase 3 of the brief adds the contracts an agent proposes, with the evidence each was
//! checked to.
//!
//! A verified statement also says whether it is about any input at all ([`Vacuity`], step 2b): an implication whose
//! A(x) no input in D satisfies holds of every program. Its status is non-vacuous, vacuous, or unknown, with how that
//! is known. A vacuous `Verified` still exits 0, which is the user's to change (the brief's open question 1).

use serde::{Deserialize, Serialize};

use crate::bmc::gaps::{GapMode, GapTreatment};
use crate::classfile::Type;
use crate::equivalence::{Confirmed, Search};
use crate::harness::{self, Layout, Param, Slot};
use crate::jbmc::JbmcResult;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Statement {
    /// `regression` (two versions compared) or `property` (one version against an assertion).
    pub kind: String,
    pub domain: Domain,
    /// A(x): what an input must satisfy, or what the checker takes for granted, for the statement to be about it.
    pub assumptions: Vec<Assumption>,
    pub observations: Observations,
    pub bounds: Bounds,
    pub models: Models,
    pub checker: Checker,
    /// The gap mode of the checker the verdict comes from (the own checker's; none for JBMC, which has none). Not
    /// read back with the rest (its type doesn't deserialize): a reader that needs it restores it by its name.
    #[serde(skip_deserializing)]
    pub gap_mode: Option<GapMode>,
    /// What JBMC made of the own checker's proof under `--confirm`; none when it was not asked for.
    pub confirmation: Option<Confirmed>,
    /// Whether the statement is about any input: for a `Verified` verdict only. A violation's witness is itself an
    /// input that reaches the calls, and a statement with no verdict established nothing to be vacuous.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vacuity: Option<Vacuity>,
    /// What `llm-dlc/loops/foundations.md` adds: the preservation contract, object domain, observations and
    /// correspondence. None until a stream of that brief fills it.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub spec: Option<crate::spec::StatementSpec>,
}

/// Whether some input in D satisfies A and reaches the calls, so that a proof of the statement says something.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Vacuity {
    pub status: VacuityStatus,
    pub basis: VacuityBasis,
    /// The status in a sentence, with how it is known.
    pub text: String,
    /// An input that reaches the calls, as the probe found it (the harness's arguments, as a call).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub witness: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum VacuityStatus {
    /// Some input in D reaches the calls.
    NonVacuous,
    /// No input in D reaches the calls: the proof covers none, and says nothing.
    Vacuous,
    /// Not known either way: the probe gave no verdict.
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum VacuityBasis {
    /// Nothing in the harness skips an input before the calls, so every input in D reaches them.
    Harness,
    /// The probe: the harness with the calls replaced by a failure, run by the own checker over D. An input that
    /// reaches the calls violates it; a proof of it is a proof that none does.
    Probe,
    /// No harness: the versions' bytecode is identical, so they agree on every input in D, whatever A says.
    Identical,
}

impl Vacuity {
    /// A statement whose harness skips no input before the calls.
    pub fn every_input() -> Vacuity {
        Vacuity { status: VacuityStatus::NonVacuous, basis: VacuityBasis::Harness, text: "Nothing skips an input in the domain before the calls, so the verdict is about every one of them.".into(), witness: None }
    }

    /// Identical bytecode: the versions agree on every input, intended or not.
    pub fn identical() -> Vacuity {
        Vacuity { status: VacuityStatus::NonVacuous, basis: VacuityBasis::Identical, text: "The versions' bytecode is identical, so they agree on every input in the domain, among the assumed ones or not.".into(), witness: None }
    }

    /// The probe found an input that reaches the calls.
    pub fn reached(witness: Option<String>) -> Vacuity {
        let text = match &witness {
            Some(w) => format!("Some input in the domain reaches the calls: the tool's own checker found {w}."),
            None => "Some input in the domain reaches the calls: the tool's own checker found one.".into(),
        };
        Vacuity { status: VacuityStatus::NonVacuous, basis: VacuityBasis::Probe, text, witness }
    }

    /// The probe was proved: no input reaches the calls. `reason` is the `vacuously:` line.
    pub fn vacuous(reason: &str) -> Vacuity {
        Vacuity { status: VacuityStatus::Vacuous, basis: VacuityBasis::Probe, text: format!("The verdict is vacuous: {reason}."), witness: None }
    }

    /// The probe gave no verdict.
    pub fn unknown(problem: &str) -> Vacuity {
        Vacuity { status: VacuityStatus::Unknown, basis: VacuityBasis::Probe, text: format!("Whether any input in the domain reaches the calls is not known: the tool's own checker gave no verdict on it ({problem})."), witness: None }
    }
}

/// D: the inputs the statement is about.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Domain {
    /// The target's receiver and parameters, as the target takes them (a record as one, built from its components).
    pub parameters: Vec<Parameter>,
    /// Whether two array parameters may be one array. Only where a property's domain says which may
    /// (`--may-alias`, the own checker alone): otherwise each is an array of its own in both engines (JBMC under
    /// `--java-assume-inputs-non-null`), so a claim refuted only by aliased arrays is outside D.
    pub shared_arrays: bool,
    /// The groups of parameters any two of which may be one array (a property's), or one object (a regression
    /// check's object parameters made by their constructor, step H2), by name.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub may_alias: Vec<Vec<String>>,
    /// The domain as the proof line writes it: `a: int[] of length ≤ 8, not null × n: int`.
    pub text: String,
    /// How many input objects each version's inputs are made of, the previous version's first, where a parameter
    /// is an object made by its constructor: every one its construction makes (a `Quote` of a `Money` is two).
    /// Under a correspondence the two may differ (step H5 of `llm-dlc/loops/foundations-heap.md`).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_objects: Option<(u32, u32)>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Parameter {
    /// `n`, `this` for a record's receiver.
    pub name: String,
    /// The Java type: `int`, `int[]`, `net.example.Backoff`.
    #[serde(rename = "type")]
    pub ty: String,
    pub kind: ParameterKind,
    /// Whether `null` is among its values: only for an array parameter a property's domain lets be null
    /// (`--nullable`); otherwise an array is a fresh array and a record one its constructor built.
    pub null: bool,
    /// The longest array it is given, for an array.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_length: Option<u32>,
    /// A record's components, `name: type`, which are the symbolic inputs it is built from.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub components: Vec<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ParameterKind {
    Primitive,
    Array,
    /// A record of primitive components, built through its canonical constructor.
    Record,
    /// An object of an application class made by its constructor, from primitives and objects made so in turn;
    /// its fields after the call are observed.
    Object,
    /// A value of a value adapter's domain, a String or an immutable list, within its bounds (the values stream's,
    /// `spec::plans::ValueDomain`).
    Value,
}

/// One conjunct of A.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Assumption {
    pub kind: AssumptionKind,
    /// What it says, in words.
    pub text: String,
    pub basis: Basis,
    /// The gap's stable id, for a gap ([`crate::bmc::gaps::Gap::id`]).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum AssumptionKind {
    /// A regression proof's scope: the inputs outside the intended change (`--unchanged-unless`).
    IntendedInputs,
    /// A property's assumption (`--assume`).
    Precondition,
    /// An input a record's constructor rejects, in either version, is skipped.
    Constructible,
    /// An input on which the previous version's arguments (`--before-arguments`) throw is skipped.
    PreviousArguments,
    /// What the checker takes as already initialized.
    Initialization,
    /// What a checker does at a call it has no bytecode for.
    Library,
    /// A gap the own checker assumed (`--gaps assume`).
    Gap,
    /// What a contract for a gap states, which the own checker applied at the call (`--contracts`).
    Contract,
    /// A callee whose two versions differ, taken as one function in both because a regression proof of its own
    /// showed they have the same outcome on every input ([`crate::shared::Proved`]); `id` is that proof's claim key.
    Callee,
    /// A modelled dependency's outcomes, the environment model's generated stubs in place of the real dependency
    /// (the environment stream's, `spec::plans::CallModel`): a result under it is about the model, not the service.
    Environment,
    /// A helper's summary applied at a call in place of its body, its applicability discharged there (the reuse
    /// stream's, `spec::plans::Summary`); `id` is the claim key of the helper's own proof.
    Summary,
    /// The states a construction plan's setup sequence reaches, and no others (the objects stream's O3).
    Setup,
}

/// Why an assumption is taken: what stands behind it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Basis {
    /// The claim states it: it is part of what is claimed, not a weakness of the proof.
    Stated,
    /// How the harness builds the statement makes it.
    Harness,
    /// The checker's semantics make it, for every proof that checker gives.
    Engine,
    /// An approximation the own checker took at a gap (`--gaps assume`), checked against nothing.
    Assumed,
    /// A contract for a gap that the tool's own checker proved against the JDK's bytecode on every input it is
    /// about, and a real JVM's test does not refute (`--contracts`). For a [`AssumptionKind::Callee`], the regression
    /// proof of the callee's two versions under the claim key in `id`.
    Proved,
    /// A contract for a gap that a real JVM ran the JDK's call against, on boundary and seeded random inputs, none
    /// refuting it (`--contracts`): evidence, not a proof.
    Tested,
    /// A contract for a gap that nothing has checked against the JDK's bytecode or a JVM: whoever wrote it vouches
    /// for it (`--contracts`).
    Trusted,
}

/// Obs: what is observed of a call.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Observations {
    /// What is compared or checked of the result.
    pub result: String,
    /// What is compared or checked of an exception.
    pub exceptions: String,
    /// The array parameters whose contents after the call are compared too.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub arrays: Vec<String>,
    /// The object parameters made by their constructors whose fields after the call are compared too, each as
    /// `q: amount.cents, quantity`, the fields by path.
    #[serde(skip_serializing_if = "Vec::is_empty", default)]
    pub objects: Vec<String>,
    /// The identity relations within each version compared as "holds before iff it holds now", `result == q`
    /// (step H3 of `llm-dlc/loops/foundations-heap.md`); objects are never compared by identity across versions.
    #[serde(skip_serializing_if = "Vec::is_empty", default)]
    pub identities: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Bounds {
    /// The loop unwinding bound, which unwinding assertions check: a proof's every loop ends within it. None when no
    /// checker ran (identical bytecode).
    pub unwind: Option<u32>,
    /// The longest array an array parameter is given; none without one.
    pub max_array_length: Option<u32>,
    /// Whether the search covered every execution of every input in D within the bounds: a proof's did, and a
    /// counterexample needs no such thing.
    pub complete: bool,
    /// The longest String or list a value parameter is given (the values stream's), where one is.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_value_length: Option<u32>,
    /// The most calls of the setup sequence before the target (the objects stream's O3), where there is one.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub setup_calls: Option<u32>,
    /// The most modelled-call attempts a trace records (the environment stream's), where an environment is modelled.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub trace_bound: Option<u32>,
}

/// The models of the JDK the checker read in place of the JDK's own classes, and the JDK whose classes it read.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Models {
    /// Whether the tool's models (`lib/models`, [`crate::models`]) were used.
    pub used: bool,
    /// `sha256:` and the digest of every model's name and class file, in class path order; none when unused.
    pub digest: Option<String>,
    pub classes: usize,
    /// The JDK's version (`<java home>/release`), whose classes the own checker reads and JBMC's six come from.
    pub jdk: Option<String>,
    /// The value models the check ran under (the values stream's: a String's, a list family's), each with its
    /// source, JDK, evidence level and what it leaves out (`spec::plans::ModelEvidence`).
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub values: Vec<crate::spec::plans::ModelEvidence>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Checker {
    /// `native`, `jbmc`, or `none` when no checker ran (identical bytecode).
    pub engine: String,
    /// `JBMC 6.11.0`, or the own checker with its solver, as the proof line names it.
    pub name: String,
    /// The SAT solver: JBMC's `--sat-solver`, or the own checker's bundled CaDiCaL with its version; none for
    /// JBMC's default.
    pub solver: Option<String>,
    /// Why the own checker gave no verdict before JBMC was run, under `--engine auto`.
    pub fallback: Option<String>,
    /// The SAT solver the verdict was solved on, with its version and configuration; none when no checker ran.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sat: Option<Sat>,
}

/// The SAT solver a checker ran on, as the evidence for a result names it: the own checker's bundled CaDiCaL
/// ([`native_sat`]), or the one JBMC was asked for ([`crate::jbmc::sat`]). The benchmark gathers them into
/// `results.json`'s environment.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Sat {
    /// `CaDiCaL`, or the solver JBMC used by default.
    pub solver: String,
    /// The solver's own version, as `1.9.5`; none when it could not be read.
    pub version: Option<String>,
    /// Where the solver comes from: the Rust crate that bundles it, or the JBMC executable it is linked into.
    pub source: String,
    /// How it was configured: its options, or the checker's that bear on it.
    pub configuration: Vec<String>,
}

/// The own checker's solver, as the solver [`crate::bmc::sat::ENV`] chooses records itself
/// ([`crate::bmc::sat::Sat::record`]): CaDiCaL as the `cadical` crate bundles it, with the crate's version from
/// `Cargo.lock`, run incrementally with its default options, unless the variable chooses Bitwuzla. A choice that
/// doesn't work here, which a check refuses before solving, is recorded as no solver, with why.
pub fn native_sat() -> Sat {
    match crate::bmc::sat::configuration() {
        Ok(make) => make().record(),
        Err(e) => Sat { solver: "none".into(), version: None, source: e.0, configuration: Vec::new() },
    }
}

/// A dependency's version as `Cargo.lock` pins it.
pub(crate) fn locked_version(name: &str) -> Option<String> {
    const LOCK: &str = include_str!("../Cargo.lock");
    let header = format!("name = \"{name}\"\n");
    let at = LOCK.find(&header)? + header.len();
    LOCK[at..].lines().next()?.strip_prefix("version = \"")?.strip_suffix('"').map(str::to_string)
}

/// The domain of a target laid out as `layout`.
pub fn domain(layout: &Layout, max_array_length: u32) -> Domain {
    let parameters = layout
        .receiver
        .iter()
        .chain(layout.args.iter())
        .map(|s| match s {
            Slot::Plain(i) => parameter(&layout.params[*i], max_array_length),
            Slot::Record { name, record, .. } => Parameter {
                name: name.clone(),
                ty: record.java_name(),
                kind: if record.is_made() { ParameterKind::Object } else { ParameterKind::Record },
                null: layout.choice(name).is_some_and(|c| c.null.is_some()),
                max_length: None,
                components: record.components.iter().map(|(c, t)| format!("{c}: {}", t.java_name())).collect(),
            },
        })
        .collect();
    let made: Vec<(u32, u32)> = layout
        .records()
        .iter()
        .filter_map(|s| match s {
            Slot::Record { record, before, .. } if record.is_made() => Some((before.as_ref().unwrap_or(record).objects(), record.objects())),
            _ => None,
        })
        .collect();
    let input_objects = (!made.is_empty()).then(|| made.iter().fold((0, 0), |(b, a), (x, y)| (b + x, a + y)));
    Domain { parameters, shared_arrays: false, may_alias: layout.alias_groups(), text: layout.domain(max_array_length), input_objects }
}

/// The domain of a method of plain parameters (a property's).
pub fn plain_domain(params: &[Param], max_array_length: u32) -> Domain {
    plain_domain_of(params, max_array_length, &[], &[])
}

/// [`plain_domain`], with the array parameters that may be null (`nullable`) and the groups that may be one array
/// (`may_alias`), by name ([`harness::domain_of`]).
pub fn plain_domain_of(params: &[Param], max_array_length: u32, nullable: &[String], may_alias: &[Vec<String>]) -> Domain {
    let text = harness::domain_of(params, max_array_length, nullable, may_alias);
    let parameters = params.iter().map(|p| Parameter { null: nullable.contains(&p.name), ..parameter(p, max_array_length) }).collect();
    Domain { parameters, shared_arrays: !may_alias.is_empty(), may_alias: may_alias.to_vec(), text, input_objects: None }
}

fn parameter(p: &Param, max_array_length: u32) -> Parameter {
    let array = matches!(p.ty, Type::Array(_));
    Parameter {
        name: p.name.clone(),
        ty: p.ty.java_name(),
        kind: if array { ParameterKind::Array } else { ParameterKind::Primitive },
        null: false,
        max_length: array.then_some(max_array_length),
        components: Vec::new(),
    }
}

impl Domain {
    pub fn has_arrays(&self) -> bool {
        self.parameters.iter().any(|p| p.kind == ParameterKind::Array)
    }
}

/// The assumptions a checker's run adds to those of the claim: what its semantics take for granted, and the gaps
/// it assumed. None for a run of no checker.
pub fn checker_assumptions(last: Option<&JbmcResult>) -> Vec<Assumption> {
    let Some(last) = last else { return Vec::new() };
    let mut out = Vec::new();
    if last.native.is_some() {
        out.push(Assumption { kind: AssumptionKind::Initialization, text: "every JDK class is initialized already, its static initializer having run and thrown nothing".into(), basis: Basis::Engine, id: None });
    } else {
        out.push(Assumption {
            kind: AssumptionKind::Library,
            // What the method reaches of JBMC's stubs is a gap of its own (crate::jbmc_gaps); what is left is what a
            // JDK class's initializer reaches.
            text: format!("a JDK class is initialized by its static initializer as JBMC runs it, where a JDK method it calls outside the tool's models and the JDK classes JBMC is given ({}) is JBMC's stub, which throws nothing and returns any value of its type", crate::equivalence::JDK_CLASSES.iter().map(|c| c.replace('/', ".")).collect::<Vec<_>>().join(", ")),
            basis: Basis::Engine,
            id: None,
        });
    }
    for g in &last.gaps {
        if g.treatment == Some(GapTreatment::Assumed) {
            out.push(Assumption { kind: AssumptionKind::Gap, text: format!("{} {}", g.call, g.approximation), basis: Basis::Assumed, id: Some(g.id.clone()) });
        }
        if let (Some(GapTreatment::Contract), Some(c)) = (g.treatment, &g.contract) {
            let basis = match c.evidence {
                crate::gap_contracts::Evidence::Proved => Basis::Proved,
                crate::gap_contracts::Evidence::Tested => Basis::Tested,
                crate::gap_contracts::Evidence::Trusted => Basis::Trusted,
            };
            out.push(Assumption { kind: AssumptionKind::Contract, text: format!("{}: {} (written by {})", g.call, c.summary, c.written_by), basis, id: Some(g.id.clone()) });
        }
    }
    out
}

/// The regression proof's assumptions from how its statement is built: the scope, the records' constructors and
/// the previous version's arguments.
pub fn regression_assumptions(layout: &Layout, unchanged_unless: Option<&str>, before_arguments: Option<&str>) -> Vec<Assumption> {
    let mut out = Vec::new();
    if let Some(s) = unchanged_unless {
        out.push(Assumption { kind: AssumptionKind::IntendedInputs, text: format!("!({s}): the input is not among those the change is meant for"), basis: Basis::Stated, id: None });
    }
    for slot in layout.records() {
        if let Slot::Record { name, record, before: Some(previous), .. } = slot {
            if let Some(c) = previous.corresponds.as_ref().filter(|c| !c.same_shape) {
                out.push(Assumption {
                    kind: AssumptionKind::Constructible,
                    text: format!("the new version's constructor {} accepts the arguments of {name}, and the previous version's {} accepts those the correspondence's input equations give it from them, the two objects as made satisfying the equations ({}): an input either constructor rejects, or on which they do not hold, is skipped, so the statement is about the pairs of objects the correspondence relates", record.describe(), previous.describe(), c.equations.iter().map(|e| e.text(name, name)).collect::<Vec<_>>().join(", ")),
                    basis: Basis::Harness,
                    id: None,
                });
                continue;
            }
        }
        // The objects stream's O2 (application-core): where the harness compares the versions' admission of an
        // input, only an input both versions' constructors reject is skipped.
        if let (true, Slot::Record { name, record, .. }) = (layout.compares_admission(), slot) {
            let (what, built) = if record.is_made() { ("arguments", "objects") } else { ("components", "records") };
            out.push(Assumption {
                kind: AssumptionKind::Constructible,
                text: format!("either version's constructor {} accepts the {what} of {name}: an input both versions' constructors reject is skipped, and one that only one version's reject is a difference, on the exception, so the statement is about the {built} both versions can build, and that they can build the same ones", record.describe()),
                basis: Basis::Harness,
                id: None,
            });
            continue;
        }
        if let Slot::Record { name, record, before, .. } = slot {
            let versions = if before.is_some() { "either version's" } else { "the new version's" };
            let (what, built) = if record.is_made() { ("arguments", "objects") } else { ("components", "records") };
            out.push(Assumption {
                kind: AssumptionKind::Constructible,
                text: format!("{versions} constructor {} accepts the {what} of {name}: an input it rejects is skipped, so the statement is about the {built} both versions can build, and whether the constructors accept the same inputs is not part of it", record.describe()),
                basis: Basis::Harness,
                id: None,
            });
        }
    }
    if let Some(a) = before_arguments {
        out.push(Assumption { kind: AssumptionKind::PreviousArguments, text: format!("the previous version's arguments {a} are computed without throwing: an input on which they throw is skipped"), basis: Basis::Harness, id: None });
    }
    out
}

/// A property's assumptions from how its harness makes its inputs (step H2 of `llm-dlc/loops/foundations-heap.md`):
/// each object parameter made by its constructor, which skips an input it rejects.
pub fn property_assumptions(layout: &Layout) -> Vec<Assumption> {
    layout
        .records()
        .iter()
        .filter_map(|slot| match slot {
            Slot::Record { name, record, .. } => Some(Assumption {
                kind: AssumptionKind::Constructible,
                text: format!("the constructor {} accepts the arguments of {name}: an input it rejects is skipped, so the property is about the objects it makes", record.describe()),
                basis: Basis::Harness,
                id: None,
            }),
            Slot::Plain(_) => None,
        })
        .collect()
}

/// What a regression proof observes: the result as compared (or related), the exception's class among the harness's
/// categories, and what the versions leave in each array parameter.
pub fn regression_observations(layout: &Layout, ret: &Type, relation: Option<&str>) -> Observations {
    let result = match (relation, &layout.result.0, ret) {
        (Some(r), _, _) => format!("the results, related by {r} whenever both versions return"),
        (None, Some(record), _) => format!("the result, a {} compared component by component ({})", record.simple_name(), record.components.iter().map(|(c, _)| c.as_str()).collect::<Vec<_>>().join(", ")),
        (None, None, Type::Object(_)) if layout.result_equations.is_some() => {
            let fields = layout.result_fields.0.as_ref().expect("a result under a correspondence has fields");
            let equations = layout.result_equations.as_deref().unwrap_or_default();
            format!("the result, a {} compared under the correspondence ({}), two nulls agreeing", crate::classfile::simple_name_of(&fields.class), equations.iter().map(|e| e.text("result", "result")).collect::<Vec<_>>().join(", "))
        }
        (None, None, Type::Object(_)) if layout.result_fields.0.is_some() => {
            let fields = layout.result_fields.0.as_ref().expect("checked");
            format!("the result, a {} compared field by field ({}), two nulls agreeing", crate::classfile::simple_name_of(&fields.class), fields.paths().iter().map(|(p, _)| p.as_str()).collect::<Vec<_>>().join(", "))
        }
        (None, None, Type::Void) => "nothing: the method returns no value".into(),
        (None, None, Type::Array(_)) => "the result, an array compared element by element".into(),
        (None, None, _) => "the result, equal in both versions".into(),
    };
    let arrays = layout.params.iter().filter(|p| matches!(p.ty, Type::Array(_))).map(|p| p.name.clone()).collect();
    let objects = layout
        .records()
        .iter()
        .filter_map(|s| match s {
            // The equations an output relation for a field takes the place of are left out, and the relation
            // follows (H5's rest): `p: under the correspondence; p.cents under the output relation …`.
            // Of two objects of the same shape (H5's rest), the paths compared, then the relations: `l: price.cents;
            // l.quantity under the output relation …`.
            Slot::Record { name, before: Some(previous), .. } if previous.corresponds.as_ref().is_some_and(|c| c.same_shape) => previous.corresponds.as_ref().map(|c| {
                let paths = c.compared_equations().iter().map(|e| e.old.clone()).collect::<Vec<_>>().join(", ");
                let mut parts = if paths.is_empty() { Vec::new() } else { vec![paths] };
                for r in &c.relations {
                    let path = if r.path.is_empty() { name.clone() } else { format!("{name}.{}", r.path) };
                    parts.push(format!("{path} under the output relation {}", r.holds.trim()));
                }
                format!("{name}: {}", parts.join("; "))
            }),
            Slot::Record { name, before: Some(previous), .. } if previous.corresponds.is_some() => previous.corresponds.as_ref().map(|c| {
                let equations = c.compared_equations().iter().map(|e| e.text(name, name)).collect::<Vec<_>>().join(", ");
                let mut text = if equations.is_empty() { format!("{name}: under the correspondence") } else { format!("{name}: under the correspondence, {equations}") };
                for r in &c.relations {
                    let path = if r.path.is_empty() { name.clone() } else { format!("{name}.{}", r.path) };
                    text.push_str(&format!("; {path} under the output relation {}", r.holds.trim()));
                }
                text
            }),
            Slot::Record { name, record, before: Some(_), .. } => record.fields.as_ref().map(|f| format!("{name}: {}", f.paths().iter().map(|(p, _)| p.as_str()).collect::<Vec<_>>().join(", "))),
            _ => None,
        })
        .collect();
    Observations { result, exceptions: exception_categories("the same in both versions", &layout.checked), arrays, objects, identities: Vec::new() }
}

/// What a property proof observes: the result against the assertion, and an exception against the throws clauses.
pub fn property_observations(assertion: &str, throws_checked: &[String]) -> Observations {
    let exceptions = if throws_checked.is_empty() { "none may be thrown".to_string() } else { format!("none may be thrown but as a throws clause says: {}", throws_checked.join("; ")) };
    Observations { result: if assertion == "true" { "nothing beyond returning".into() } else { format!("the result and the parameters, against {assertion}") }, exceptions, arrays: Vec::new(), objects: Vec::new(), identities: Vec::new() }
}

/// How the regression harness tells exceptions apart: by class, among a fixed list, then the checked exceptions
/// either version declares ([`harness::Layout::exceptions`]).
fn exception_categories(how: &str, checked: &[harness::Checked]) -> String {
    let declared = if checked.is_empty() {
        String::new()
    } else {
        format!(", then the checked exception{} either version declares, {}", if checked.len() == 1 { "" } else { "s" }, checked.iter().map(|c| c.class.replace('/', ".")).collect::<Vec<_>>().join(", "))
    };
    format!(
        "whether it throws, and which of {} exception classes it throws ({} and the rest{declared}; another class counts as the first of them it is an instance of), {how}; the message and the exception's state are not compared",
        harness::EXCEPTIONS.len() + checked.len(),
        harness::EXCEPTIONS.iter().take(3).map(|e| e.rsplit('/').next().unwrap_or(e)).collect::<Vec<_>>().join(", ")
    )
}

/// The models a run used.
pub fn models(used: bool) -> Models {
    let digest = used.then(|| {
        let mut all = Vec::new();
        for m in crate::models::MODELS {
            all.extend_from_slice(m.name.as_bytes());
            all.push(0);
            all.extend_from_slice(&(m.bytes.len() as u64).to_be_bytes());
            all.extend_from_slice(m.bytes);
        }
        format!("sha256:{}", crate::digest::sha256_hex(&all))
    });
    Models { used, digest, classes: if used { crate::models::MODELS.len() } else { 0 }, jdk: crate::bmc::gaps::jdk_release(), values: Vec::new() }
}

/// The checker the verdict comes from, from its search; `sat_solver` is the one JBMC was asked for, and
/// `jbmc_sat` its record ([`crate::jbmc::sat`]), asked for only when JBMC gave the verdict.
pub fn checker(search: Option<&Search>, sat_solver: Option<&str>, jbmc_sat: impl FnOnce() -> Sat) -> Checker {
    match search {
        None => Checker { engine: "none".into(), name: "bytecode comparison: no checker ran".into(), solver: None, fallback: None, sat: None },
        Some(s) => Checker {
            engine: s.engine.clone(),
            name: s.checker.clone(),
            solver: if s.engine == "native" { Some(crate::bmc::solver_signature()) } else { sat_solver.map(str::to_string) },
            fallback: s.fallback.clone(),
            sat: Some(if s.engine == "native" { native_sat() } else { jbmc_sat() }),
        },
    }
}

/// The checker of a run under `--gaps advised` that stopped at the gap scan: nothing was solved.
pub fn scan_checker() -> Checker {
    Checker { engine: "none".into(), name: "gap scan: nothing was solved (--gaps advised)".into(), solver: None, fallback: None, sat: None }
}

/// The bounds of a run of a checker.
pub fn bounds(unwind: Option<u32>, domain: &Domain, max_array_length: u32, complete: bool) -> Bounds {
    Bounds { unwind, max_array_length: domain.has_arrays().then_some(max_array_length), complete, max_value_length: None, setup_calls: None, trace_bound: None }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_model_digest_names_the_bundle_and_is_absent_without_it() {
        let used = models(true);
        assert!(used.digest.as_deref().is_some_and(|d| d.starts_with("sha256:") && d.len() == 7 + 64), "{used:?}");
        assert_eq!(used.classes, crate::models::MODELS.len());
        assert_eq!(models(true).digest, used.digest, "stable");
        let unused = models(false);
        assert_eq!((unused.digest, unused.classes), (None, 0));
    }

    #[test]
    fn the_own_checkers_solver_is_the_bundled_cadical_with_the_crates_version() {
        let sat = native_sat();
        assert_eq!(sat.solver, "CaDiCaL");
        assert_eq!(Some(format!("CaDiCaL {} (bundled)", sat.version.as_deref().unwrap())), Some(crate::bmc::solver_signature()), "as the proof line names it");
        let crate_version = locked_version("cadical").expect("the cadical crate is in Cargo.lock");
        assert!(crate_version.chars().next().is_some_and(|c| c.is_ascii_digit()), "{crate_version}");
        assert_eq!(sat.source, format!("bundled by the Rust crate cadical {crate_version}"));
        assert!(!sat.configuration.is_empty());
        assert_eq!(locked_version("no-such-crate"), None);
        assert_eq!(sat, crate::bmc::sat::configured().record(), "the solver checks run on, as it records itself");
        let search = |engine: &str| Search {
            engine: engine.into(),
            checker: "c".into(),
            seconds: 0.0,
            properties: 1,
            unwind: 16,
            max_array_length: 8,
            stage: None,
            staging: None,
            fallback: None,
            native: None,
            gap_mode: None,
            gaps: Vec::new(),
            confirmation: None,
            deadline_seconds: 1.0,
            runs: Vec::new(),
            phases: None,
        };
        let jbmc_sat = || Sat { solver: "asked".into(), version: None, source: "here".into(), configuration: Vec::new() };
        assert_eq!(checker(Some(&search("native")), Some("cadical"), || unreachable!("JBMC was not run")).sat, Some(sat));
        assert_eq!(checker(Some(&search("jbmc")), Some("cadical"), jbmc_sat).sat.map(|s| s.solver), Some("asked".into()));
        assert_eq!(checker(None, Some("cadical"), || unreachable!()).sat, None);
    }

    #[test]
    fn a_domain_is_its_parameters_with_nullability_and_bounds() {
        let layout = Layout::plain(&["a".into(), "n".into()], &[Type::Array(Box::new(Type::Int)), Type::Int]);
        let d = domain(&layout, 8);
        assert_eq!(d.text, "a: int[] of length ≤ 8, not null × n: int");
        assert_eq!(d.parameters[0], Parameter { name: "a".into(), ty: "int[]".into(), kind: ParameterKind::Array, null: false, max_length: Some(8), components: Vec::new() });
        assert_eq!(d.parameters[1].kind, ParameterKind::Primitive);
        assert!(!d.shared_arrays);
        assert_eq!(bounds(Some(16), &d, 8, true).max_array_length, Some(8));
        let scalar = domain(&Layout::plain(&["n".into()], &[Type::Int]), 8);
        assert_eq!(bounds(Some(16), &scalar, 8, true).max_array_length, None);
        let observed = regression_observations(&layout, &Type::Int, None);
        assert_eq!((observed.result.as_str(), observed.arrays), ("the result, equal in both versions", vec!["a".to_string()]));
        assert!(regression_observations(&layout, &Type::Int, Some("previous == result")).result.contains("related by previous == result"));
    }
}
