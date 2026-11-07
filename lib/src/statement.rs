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

use serde::Serialize;

use crate::bmc::gaps::{GapMode, GapTreatment};
use crate::classfile::Type;
use crate::equivalence::{Confirmed, Search};
use crate::harness::{self, Layout, Param, Slot};
use crate::jbmc::JbmcResult;

#[derive(Debug, Clone, PartialEq, Serialize)]
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
    /// The gap mode of the checker the verdict comes from (the own checker's; none for JBMC, which has none).
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
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Vacuity {
    pub status: VacuityStatus,
    pub basis: VacuityBasis,
    /// The status in a sentence, with how it is known.
    pub text: String,
    /// An input that reaches the calls, as the probe found it (the harness's arguments, as a call).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub witness: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum VacuityStatus {
    /// Some input in D reaches the calls.
    NonVacuous,
    /// No input in D reaches the calls: the proof covers none, and says nothing.
    Vacuous,
    /// Not known either way: the probe gave no verdict.
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
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
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Domain {
    /// The target's receiver and parameters, as the target takes them (a record as one, built from its components).
    pub parameters: Vec<Parameter>,
    /// Whether two array parameters may be one array. Only where a property's domain says which may
    /// (`--may-alias`, the own checker alone): otherwise each is an array of its own in both engines (JBMC under
    /// `--java-assume-inputs-non-null`), so a claim refuted only by aliased arrays is outside D.
    pub shared_arrays: bool,
    /// The groups of array parameters any two of which may be one array, by name.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub may_alias: Vec<Vec<String>>,
    /// The domain as the proof line writes it: `a: int[] of length ≤ 8, not null × n: int`.
    pub text: String,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
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
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub components: Vec<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum ParameterKind {
    Primitive,
    Array,
    /// A record of primitive components, built through its canonical constructor.
    Record,
}

/// One conjunct of A.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Assumption {
    pub kind: AssumptionKind,
    /// What it says, in words.
    pub text: String,
    pub basis: Basis,
    /// The gap's stable id, for a gap ([`crate::bmc::gaps::Gap::id`]).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
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
}

/// Why an assumption is taken: what stands behind it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
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
    /// about, and a real JVM's test does not refute (`--contracts`).
    Proved,
    /// A contract for a gap that a real JVM ran the JDK's call against, on boundary and seeded random inputs, none
    /// refuting it (`--contracts`): evidence, not a proof.
    Tested,
    /// A contract for a gap that nothing has checked against the JDK's bytecode or a JVM: whoever wrote it vouches
    /// for it (`--contracts`).
    Trusted,
}

/// Obs: what is observed of a call.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Observations {
    /// What is compared or checked of the result.
    pub result: String,
    /// What is compared or checked of an exception.
    pub exceptions: String,
    /// The array parameters whose contents after the call are compared too.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub arrays: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Bounds {
    /// The loop unwinding bound, which unwinding assertions check: a proof's every loop ends within it. None when no
    /// checker ran (identical bytecode).
    pub unwind: Option<u32>,
    /// The longest array an array parameter is given; none without one.
    pub max_array_length: Option<u32>,
    /// Whether the search covered every execution of every input in D within the bounds: a proof's did, and a
    /// counterexample needs no such thing.
    pub complete: bool,
}

/// The models of the JDK the checker read in place of the JDK's own classes, and the JDK whose classes it read.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Models {
    /// Whether the tool's models (`lib/models`, [`crate::models`]) were used.
    pub used: bool,
    /// `sha256:` and the digest of every model's name and class file, in class path order; none when unused.
    pub digest: Option<String>,
    pub classes: usize,
    /// The JDK's version (`<java home>/release`), whose classes the own checker reads and JBMC's six come from.
    pub jdk: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
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
#[derive(Debug, Clone, PartialEq, Serialize)]
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
                kind: ParameterKind::Record,
                null: false,
                max_length: None,
                components: record.components.iter().map(|(c, t)| format!("{c}: {}", t.java_name())).collect(),
            },
        })
        .collect();
    Domain { parameters, shared_arrays: false, may_alias: Vec::new(), text: layout.domain(max_array_length) }
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
    Domain { parameters, shared_arrays: !may_alias.is_empty(), may_alias: may_alias.to_vec(), text }
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
        if let Slot::Record { name, record, before, .. } = slot {
            let versions = if before.is_some() { "either version's" } else { "the new version's" };
            out.push(Assumption {
                kind: AssumptionKind::Constructible,
                text: format!("{versions} constructor {} accepts the components of {name}: an input it rejects is skipped, so the statement is about the records both versions can build, and whether the constructors accept the same inputs is not part of it", record.describe()),
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

/// What a regression proof observes: the result as compared (or related), the exception's class among the harness's
/// categories, and what the versions leave in each array parameter.
pub fn regression_observations(layout: &Layout, ret: &Type, relation: Option<&str>) -> Observations {
    let result = match (relation, &layout.result.0, ret) {
        (Some(r), _, _) => format!("the results, related by {r} whenever both versions return"),
        (None, Some(record), _) => format!("the result, a {} compared component by component ({})", record.simple_name(), record.components.iter().map(|(c, _)| c.as_str()).collect::<Vec<_>>().join(", ")),
        (None, None, Type::Void) => "nothing: the method returns no value".into(),
        (None, None, Type::Array(_)) => "the result, an array compared element by element".into(),
        (None, None, _) => "the result, equal in both versions".into(),
    };
    let arrays = layout.params.iter().filter(|p| matches!(p.ty, Type::Array(_))).map(|p| p.name.clone()).collect();
    Observations { result, exceptions: exception_categories("the same in both versions"), arrays }
}

/// What a property proof observes: the result against the assertion, and an exception against the throws clauses.
pub fn property_observations(assertion: &str, throws_checked: &[String]) -> Observations {
    let exceptions = if throws_checked.is_empty() { "none may be thrown".to_string() } else { format!("none may be thrown but as a throws clause says: {}", throws_checked.join("; ")) };
    Observations { result: if assertion == "true" { "nothing beyond returning".into() } else { format!("the result and the parameters, against {assertion}") }, exceptions, arrays: Vec::new() }
}

/// How the regression harness tells exceptions apart: by class, among a fixed list.
fn exception_categories(how: &str) -> String {
    format!(
        "whether it throws, and which of {} exception classes it throws ({} and the rest; another class counts as the first of them it is an instance of), {how}; the message and the exception's state are not compared",
        harness::EXCEPTIONS.len(),
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
    Models { used, digest, classes: if used { crate::models::MODELS.len() } else { 0 }, jdk: crate::bmc::gaps::jdk_release() }
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
    Bounds { unwind, max_array_length: domain.has_arrays().then_some(max_array_length), complete }
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
