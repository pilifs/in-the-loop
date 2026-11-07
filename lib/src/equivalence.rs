//! Regression verification: proves that a method behaves exactly as its previous version on every input, or shows
//! an input where it does not. This is the contract check for methods whose inputs are not finite, such as a
//! `long` price and an `int` seat count, where running every input is impossible.
//!
//! The statement is "for all inputs, old(x) and new(x) return the same value or throw the same exception",
//! optionally restricted to the inputs the developer did *not* mean to change. It is proved by bounded model
//! checking of the bytecode with JBMC: both versions are compiled into one program (the old one relocated into a
//! `before` package by [`crate::relocate`]), a generated harness asserts the statement ([`crate::harness`]), and
//! JBMC turns the harness into a satisfiability problem whose unsatisfiability is the proof. A satisfying
//! assignment is a concrete counterexample, which this module shrinks ([`crate::shrink`]) and replays in the
//! interpreter to show the two outcomes.
//!
//! An array parameter is a symbolic array of every length up to a bound ([`Options::max_array_length`]), never
//! `null`; the version before is called on a copy of it, and what the two versions leave in the array is compared
//! with their results, so a method that writes into its argument is held to the writes as well. An array result is
//! compared element by element.
//!
//! Before the solver is asked, the two versions' bytecode is compared ([`crate::shared`]): a target that is
//! identical in both, together with everything it reaches, is verified without a proof, and a callee that both
//! versions call unchanged is taken as one function in both, so that the solver relates how the versions use it
//! and never its arithmetic. A counterexample found that way is replayed through the bytecode as written, and the
//! proof is run again with the callees as written when it does not reproduce.
//!
//! The previous version need not have the target's name or parameters: a method renamed or moved is named with
//! [`Options::before_target`], and one whose parameters were reordered, added, removed or retyped is called with
//! the arguments given by [`Options::before_arguments`], expressions over the new parameters, so that the statement
//! proved is "new(x) agrees with old(f(x))" for the stated relation. A method whose result changed its type or
//! meaning (a boolean that became a remaining time, nanoseconds that became milliseconds) is related to the previous
//! one by [`Options::results_agree_when`], a boolean expression over the new parameters, `previous` and `result`,
//! which takes the place of equality whenever both versions return.
//!
//! A method of a record whose components are primitive is a target too, as is a method taking or returning such a
//! record: the components are the symbolic inputs, the record is built from them in both versions through its
//! canonical constructor (an input a constructor rejects is outside the statement), and a record result is
//! compared component by component ([`harness::Layout`]). A static method that became a method of a record, or
//! took one as a parameter (the components it took gathered into a record), is related to its previous version
//! by [`Options::before_arguments`] over the components, `this.component` or `parameter.component`.

use std::fmt::Write as _;
use std::path::{Path, PathBuf};
use std::time::Duration;

use serde::Serialize;

use crate::bmc::gaps::GapTreatment;
use crate::classfile::{MemberRef, Type};
use crate::classpath::ClassPath;
use crate::deadline::{Deadline, Run};
use crate::harness::{self, CallArg};
use crate::interp::Value;
use crate::jbmc::{self, Argument, JbmcResult, JbmcRun};
use crate::sarif::{self, Finding};
use crate::statement::Vacuity;
use crate::{shared, witness, Error, Verdict};

/// JDK classes whose real bytecode JBMC analyses, instead of the small models it ships.
pub const JDK_CLASSES: &[&str] = &["java/lang/Math", "java/lang/StrictMath", "java/lang/Integer", "java/lang/Long", "java/lang/Short", "java/lang/Byte"];

pub use crate::deadline::STAGES;

#[derive(Debug, Clone)]
pub struct Options {
    pub before: PathBuf,
    pub after: PathBuf,
    /// `pkg.Class#method`.
    pub target: String,
    pub unchanged_unless: Option<String>,
    pub classpath: Vec<PathBuf>,
    /// Working directory; a temporary one when `None`.
    pub work: Option<PathBuf>,
    pub report: Option<PathBuf>,
    pub sources: Vec<PathBuf>,
    pub base: PathBuf,
    pub unwind: u32,
    /// The longest array an array parameter is given.
    pub max_array_length: u32,
    /// Whether to shrink a counterexample in the interpreter before reporting it.
    pub shrink: bool,
    /// The check's one deadline ([`crate::deadline`]); `--confirm` gets one of its own.
    pub timeout_seconds: u64,
    pub jbmc: String,
    /// The JDK to take `java.lang.Math` from; found through `JAVA_HOME`/`PATH` when `None`.
    pub java_home: Option<PathBuf>,
    /// Whether the tool's models of JDK classes ([`crate::models`]) go on JBMC's class path and into the replay
    /// (they do, unless turned off to see what JBMC makes of the stubs).
    pub models: bool,
    /// Whether to run JBMC with its string solver ([`crate::jbmc::JbmcRun::refine_strings`]); off by default.
    pub refine_strings: bool,
    /// The SAT solver to ask JBMC for ([`crate::jbmc::JbmcRun::sat_solver`]); CaDiCaL by default.
    pub sat_solver: Option<String>,
    /// Which of JBMC's interval stages run before the full range ([`crate::deadline::Staging`]); the full range
    /// alone by default. The own checker's stages and `--confirm`'s one run do not follow it.
    pub jbmc_staging: crate::deadline::Staging,
    /// Which checker proves the harness: JBMC (the default), the tool's own ([`crate::bmc`]), or the tool's own
    /// where the harness is within its fragment and JBMC elsewhere.
    pub engine: crate::Engine,
    /// What the tool's own checker does at a gap ([`crate::bmc::gaps`]): refuses it (strict, the default) or
    /// assumes its approximation and names it in the verdict. It has no effect on JBMC.
    pub gaps: crate::bmc::gaps::GapMode,
    /// Under advised, the contracts for the gaps (`--contracts`, [`crate::gap_contracts`]).
    pub contracts: Option<PathBuf>,
    /// Under advised, whether the contract library closes a gap `contracts` has none for
    /// ([`crate::contract_library`]); on by default (`--no-contract-library`).
    pub contract_library: bool,
    /// Under advised, the most trusted contracts the proof may rest on (`--max-trust`); none means any number.
    pub max_trust: Option<usize>,
    /// Under `--engine auto`, whether a proof of the tool's own checker is checked by JBMC too
    /// ([`crate::equivalence::Confirmation`]); off by default, since JBMC takes ten to a hundred times longer.
    pub confirm: bool,
    /// Whether callees unchanged in both versions are taken as one function in both ([`crate::shared`]), and a
    /// target identical in both versions is verified without a proof. On by default.
    pub shared_callees: bool,
    /// The previous version's method, `pkg.Class#method`, when it is not the target's: renamed or moved.
    pub before_target: Option<String>,
    /// The previous version's arguments as expressions over the new parameters, separated by commas, when its
    /// parameters are not the new version's: reordered, added, removed or retyped. An array parameter is passed by
    /// name.
    pub before_arguments: Option<String>,
    /// The relation the two results must satisfy, a boolean expression over the new parameters, `previous` (the
    /// previous version's result) and `result` (the new one's), when it is not equality: the return type or the
    /// meaning of the result changed.
    pub results_agree_when: Option<String>,
    /// The proof cache's directory (`--cache`, [`crate::proof_cache`]): a result stored there for the same prepared
    /// claim is the result, and a verified or refuted one is stored; none means no cache.
    pub cache: Option<PathBuf>,
    /// How the previous version's objects are made from the new version's and compared with them where their
    /// shapes differ (step H5 of `llm-dlc/loops/foundations-heap.md`): a correspondence's input equations giving
    /// field paths of the previous version's parameter from the new one's, or an expression over them, the new
    /// version's primitive parameters and its other objects' arguments ([`crate::spec::heap::relate`]), output relations for such a parameter's fields as the calls leave them in
    /// place of the equations about them, or for the fields of one of the same shape in both versions in place of
    /// equality for their paths ([`crate::spec::heap::relate_same_shape`]), and an output relation for the result in place of
    /// [`Options::results_agree_when`] ([`crate::spec::heap::output_relation`]).
    pub correspondence: Option<crate::spec::Correspondence>,
    /// Object parameters made by their constructor that may be null (`--nullable`, step H2 of
    /// `llm-dlc/loops/foundations-heap.md`); every other is an object.
    pub nullable: Vec<String>,
    /// Pairs of object parameters of one class that may be the same object (`--may-alias a,b`), closed under chains;
    /// every other is an object of its own.
    pub may_alias: Vec<(String, String)>,
}

impl Options {
    pub fn new(before: &Path, after: &Path, target: &str) -> Options {
        Options {
            before: before.to_path_buf(),
            after: after.to_path_buf(),
            target: target.to_string(),
            unchanged_unless: None,
            classpath: Vec::new(),
            work: None,
            report: None,
            sources: Vec::new(),
            base: std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")),
            unwind: 16,
            max_array_length: 8,
            shrink: true,
            timeout_seconds: 600,
            jbmc: "jbmc".into(),
            java_home: None,
            cache: None,
            models: true,
            refine_strings: false,
            sat_solver: Some("cadical".into()),
            jbmc_staging: crate::deadline::Staging::FullRange,
            engine: crate::Engine::Jbmc,
            gaps: crate::bmc::gaps::GapMode::Strict,
            contracts: None,
            contract_library: true,
            max_trust: None,
            confirm: false,
            shared_callees: true,
            before_target: None,
            before_arguments: None,
            results_agree_when: None,
            correspondence: None,
            nullable: Vec::new(),
            may_alias: Vec::new(),
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct Counterexample {
    /// `totalCents(priceCents=5, seats=7)`.
    pub input: String,
    /// What the version before did: its result or the exception it threw, and what it left in the arrays it changed.
    pub before: String,
    pub after: String,
    /// The raw argument values, in parameter order.
    pub values: Vec<String>,
    /// The input as JBMC found it, when `input` is the shrunk one.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub found: Option<String>,
    /// How many smaller inputs the interpreter tried while shrinking.
    pub shrink_runs: u32,
    /// The inputs, typed and exact, under the harness's names (a record's components as `this.c`), in its order.
    pub inputs: Vec<witness::Typed>,
    /// The inputs as JBMC found them, when `inputs` are the shrunk ones.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub found_inputs: Option<Vec<witness::Typed>>,
    /// The new version's call on the inputs.
    pub call: witness::Call,
    /// The previous version's call on them: the same arguments, or those `--before-arguments` computes from them.
    /// Absent when they could not be computed.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub previous_call: Option<witness::Call>,
    /// The observations the two versions' replays differ in, by id ([`crate::spec::Observation::id`]): `result`,
    /// `exception`, `array:a`, `field:q` (an object parameter as left), `identity:result==q`. Empty where the
    /// previous version's arguments are expressions.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub differs: Vec<String>,
    /// The JDK a real JVM ran the harness on `input` on and found it failing too, where the witness is over objects
    /// or differs in a field or an identity relation (step H4 of `llm-dlc/loops/foundations-heap.md`), or where only
    /// a JVM could run it.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub jvm: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Outcome {
    pub verdict: Verdict,
    pub target: String,
    /// `priceCents: long × seats: int`.
    pub domain: Option<String>,
    pub counterexample: Option<Counterexample>,
    /// How the verdict was reached, for reports.
    pub proof: Option<String>,
    pub problem: Option<String>,
    pub statement: Option<PathBuf>,
    pub findings: Vec<Finding>,
    pub output: String,
    pub work: PathBuf,
    /// The callees taken as one function in both versions, as `Class.method`.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub shared: Vec<String>,
    /// The previous version's call, `pkg.Class#method(args)` or `method(args)`, when it is not the target's.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub previous: Option<String>,
    /// The relation between the results the proof is of, when it is not equality.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub relation: Option<String>,
    /// Why a verified statement says nothing: no input in the domain reaches the calls, every one being skipped
    /// before them (among the intended inputs, rejected by a constructor, or without previous-version arguments).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vacuous: Option<String>,
    /// The checker run the verdict comes from; none when no checker ran (identical bytecode, or a refusal before
    /// the search).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub search: Option<Search>,
    /// How the checker's witness was replayed on both versions, when it found one.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub replay: Option<Replay>,
    /// The statement the verdict is about, as data: its domain, assumptions and observations, with the bounds,
    /// models, checker, gap mode and confirmation it rests on ([`crate::statement`]). None when the claim was
    /// refused before a statement was built.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stated: Option<crate::statement::Statement>,
    /// Under `--gaps advised`, the gaps the proof reaches with no contract, and what a contract for each must state
    /// ([`crate::advice`]): the run stopped before solving.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub advice: Option<crate::advice::Advice>,
    /// How the result was reused from the proof cache (`--cache`, [`crate::proof_cache`]), when it was: then no
    /// checker ran, and `search` is none.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reuse: Option<crate::spec::cache::Reuse>,
}

/// The checker run a verdict comes from, with the settings it ran under: what a report needs to say how the verdict
/// was reached without reading the proof line.
#[derive(Debug, Clone, Serialize)]
pub struct Search {
    /// `jbmc`, or `native` for the tool's own checker.
    pub engine: String,
    /// The checker as the proof line names it: `JBMC 6.11.0`, or the own checker with its solver.
    pub checker: String,
    /// From the first engine and input range tried to the verdict.
    pub seconds: f64,
    /// The properties the checker proved or checked (JBMC's count; one for the own checker).
    pub properties: u32,
    pub unwind: u32,
    pub max_array_length: u32,
    /// The input range of the run the verdict comes from, as `[0:20]`; none for the whole range.
    pub stage: Option<String>,
    /// The policy JBMC's interval stages followed (`--jbmc-staging`), when the verdict is JBMC's.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub staging: Option<crate::deadline::Staging>,
    /// Why the own checker gave no verdict before JBMC was run, under `--engine auto`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fallback: Option<String>,
    /// The own checker's account of its search, when the verdict is its.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub native: Option<crate::bmc::Stats>,
    /// The gap mode the own checker ran under, when the verdict is its.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gap_mode: Option<crate::bmc::gaps::GapMode>,
    /// The gaps the own checker met, each refused or assumed ([`crate::bmc::gaps`]): under assume, what a verified
    /// statement takes for granted besides its domain.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub gaps: Vec<crate::bmc::gaps::GapRecord>,
    /// What JBMC made of the own checker's proof, under `--engine auto --confirm`; none when it was not asked for,
    /// or when the verdict is no proof of the own checker's.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub confirmation: Option<Confirmation>,
    /// The check's one deadline, `--timeout` ([`crate::deadline`]).
    pub deadline_seconds: f64,
    /// Every checker run of the check, in order, each with its budget out of the deadline; the confirmation's
    /// run is its own check.
    pub runs: Vec<Run>,
    /// Where the check's time went outside its runs: the harness, gaps, contracts, replay, the JVM
    /// ([`crate::phases::Check`]); each run's own phases are under `runs`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub phases: Option<crate::phases::Check>,
}

/// The own checker's budget: under `auto` the check but the part kept for JBMC's fallback, otherwise all of it.
pub(crate) fn own_budget(deadline: &Deadline, engine: crate::Engine) -> Duration {
    if engine == crate::Engine::Auto { deadline.all_but(crate::deadline::FALLBACK_SHARE) } else { deadline.left() }
}

/// JBMC's check of a statement the tool's own checker proved (`--engine auto --confirm`): the one expensive check
/// of step 1e of the sound-verdicts brief, so opt-in. JBMC is a second implementation of the JVM's semantics, with
/// models of its own, so its proof is evidence the own checker's was not of a different statement.
#[derive(Debug, Clone, Serialize)]
pub struct Confirmation {
    pub status: Confirmed,
    /// The checker asked, `JBMC 6.11.0`; none when it was not asked.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub checker: Option<String>,
    pub seconds: f64,
    /// Why it is not confirmed: JBMC's problem, or why JBMC was not asked.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
}

/// How a confirmation ended.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, serde::Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Confirmed {
    /// JBMC proved the statement too, over every input.
    Confirmed,
    /// JBMC refutes it: the engines disagree, and the verdict is neither theirs (it is unverifiable, with JBMC's
    /// witness as the counterexample, replayed in the interpreter).
    Disagreed,
    /// JBMC gave no verdict (a timeout, its memory, a construct it refuses): the own checker's proof stands, not
    /// confirmed.
    NoVerdict,
    /// JBMC was not asked: the own checker assumed a behaviour (`--gaps assume`) that JBMC has no bytecode for
    /// either, and only approximates with a stub of its own, so a proof of JBMC's would not check it.
    NotAsked,
}

/// The contracts the own checker's proof rests on, for JBMC to apply at the same gaps when it confirms the proof
/// ([`crate::jbmc_contracts::apply`]): the setting, the class path directories whose call sites are rewritten, the
/// class path with the JDK (for overrides and exceptions), and where the rewritten classes go.
pub(crate) struct ConfirmContracts<'a> {
    pub setting: &'a crate::bmc::gaps::GapSetting,
    pub rewrite: Vec<PathBuf>,
    pub cp: &'a crate::classpath::ClassPath,
    pub dir: PathBuf,
}

/// Asks JBMC to prove, over every input, the harness the own checker proved (`native`). `run` is JBMC's run of the
/// same harness, on the same class path. Where the own checker applied contracts for its gaps (`--gaps advised`),
/// JBMC applies the same ones at the same calls (`contracts`), so that both checkers prove the statement on the
/// contracts' word: the confirmation checks the reasoning given the contracts, whose own evidence (proved, tested,
/// trusted) is the verdict's. Returns the confirmation, and JBMC's result when it refutes the statement.
///
/// A refutation is a disagreement, unless JBMC's preflight finds a construct the harness reaches that JBMC runs
/// otherwise than the JVM ([`crate::jbmc_gaps::Defect`]) and its witness does not reproduce in the interpreter
/// (`reproduces`, the caller's replay of it in the harness): then the refutation is the defect's, as a proof
/// through one is refused, and JBMC gives no verdict. The own checker's proof stands, not confirmed. A witness that
/// reproduces is a disagreement whatever JBMC reaches.
pub(crate) fn confirm(native: &JbmcResult, run: &JbmcRun, contracts: Option<ConfirmContracts<'_>>, reproduces: &dyn Fn(&JbmcResult) -> Result<Option<bool>, Error>) -> Result<(Confirmation, Option<JbmcResult>), Error> {
    let approximated = |contract: bool| -> Vec<&str> { native.gaps.iter().filter(|g| !g.jbmc && (g.treatment == Some(GapTreatment::Contract)) == contract).map(|g| g.call.as_str()).collect() };
    let (assumed, contracted) = (approximated(false), approximated(true));
    let not_asked = |reason: String| Ok((Confirmation { status: Confirmed::NotAsked, checker: None, seconds: 0.0, reason: Some(reason) }, None));
    if !assumed.is_empty() {
        return not_asked(format!("the tool's own checker assumed {} (--gaps assume), which JBMC has no bytecode for either, and would only approximate with a stub of its own", assumed.join(", ")));
    }
    let mut run = run.clone();
    let mut applied = None;
    if !contracted.is_empty() {
        let Some(c) = contracts else {
            return not_asked(format!("the tool's own checker applied a contract at {} (--contracts), and JBMC was not given the contracts to apply", contracted.join(", ")));
        };
        let pre = crate::jbmc_gaps::preflight(&run, Duration::from_secs(crate::jbmc_gaps::PREFLIGHT_SECONDS))?;
        let Some(found) = pre.found.as_ref() else {
            return not_asked(format!("the tool's own checker applied a contract at {}, and JBMC's goto program could not be read to apply it: {}", contracted.join(", "), pre.problem.as_deref().unwrap_or("no reason")));
        };
        let a = crate::jbmc_contracts::apply(c.setting, found, &run.classpath, &c.rewrite, c.cp, &c.dir)?;
        run = JbmcRun { classpath: a.classpath.clone(), log: c.dir.join("jbmc-confirm.log"), ..run };
        applied = Some(a);
    }
    let mut result = jbmc::run(&run)?;
    // JBMC's proof is held to what it approximates on the way, under the own checker's gap mode: a proof that
    // reaches a stub confirms nothing under strict, nor under advised where no contract closes the stub.
    if result.verdict == Verdict::Verified {
        let pre = crate::jbmc_gaps::preflight(&run, Duration::from_secs(crate::jbmc_gaps::PREFLIGHT_SECONDS))?;
        crate::jbmc_gaps::hold(&mut result, &pre, native.gap_mode.unwrap_or_default());
    }
    if let Some(a) = &applied {
        crate::jbmc_contracts::settle(&mut result, a);
    }
    let mut confirmation = Confirmation { status: Confirmed::Confirmed, checker: Some(result.version.clone()), seconds: result.seconds, reason: None };
    let (assumed, _) = assumed_gaps(&result);
    if result.verdict == Verdict::Verified {
        let mut said = Vec::new();
        if !assumed.is_empty() {
            said.push(assumed.trim_start_matches(", ").to_string());
        }
        if let Some(a) = applied.as_ref().filter(|a| !a.records.is_empty()) {
            let ids: Vec<&str> = a.records.iter().map(|r| r.id.as_str()).collect();
            said.push(format!("on the same contract{} as the tool's own checker, for {}", if ids.len() == 1 { "" } else { "s" }, ids.join(", ")));
        }
        confirmation.reason = Some(said.join("; ")).filter(|s| !s.is_empty());
    }
    match result.verdict {
        Verdict::Verified => Ok((confirmation, None)),
        Verdict::Violation => {
            let pre = crate::jbmc_gaps::preflight(&run, Duration::from_secs(crate::jbmc_gaps::PREFLIGHT_SECONDS))?;
            let defects = pre.found.as_ref().map(|f| f.defects.as_slice()).unwrap_or_default();
            if !defects.is_empty() && reproduces(&result)? == Some(false) {
                let n = defects.len();
                confirmation.status = Confirmed::NoVerdict;
                confirmation.reason = Some(format!(
                    "its counterexample does not reproduce in the interpreter, and on the way it runs {n} construct{} otherwise than the JVM: {}",
                    if n == 1 { "" } else { "s" },
                    defects.iter().map(crate::jbmc_gaps::Defect::line).collect::<Vec<_>>().join("; ")
                ));
                return Ok((confirmation, None));
            }
            confirmation.status = Confirmed::Disagreed;
            Ok((confirmation, Some(result)))
        }
        Verdict::Unverifiable => {
            confirmation.status = Confirmed::NoVerdict;
            confirmation.reason = Some(result.problem.clone().unwrap_or_else(|| "no reason".into()));
            Ok((confirmation, None))
        }
    }
}

/// The line under a verified verdict that says what came of `--confirm`.
pub(crate) fn confirmation_line(c: &Confirmation) -> String {
    let checker = c.checker.as_deref().unwrap_or("JBMC");
    match c.status {
        Confirmed::Confirmed => format!("  confirmed: {checker} proves it too, over every input, in {:.1} s (--confirm)\n", c.seconds),
        Confirmed::NoVerdict => format!("  not confirmed: {checker} gave no verdict in {:.1} s ({}); the proof is the tool's own checker's alone\n", c.seconds, c.reason.as_deref().unwrap_or("no reason")),
        Confirmed::NotAsked => format!("  not confirmed: JBMC was not asked, since {}; the proof is the tool's own checker's alone\n", c.reason.as_deref().unwrap_or("no reason")),
        Confirmed::Disagreed => String::new(),
    }
}

/// Whether the own checker's run refused a gap (under strict, or one with no assume form) that JBMC does not
/// implement either: then `--engine auto` does not ask JBMC, which has no bytecode for the call either, and whose
/// stub is a gap of its own ([`crate::jbmc_gaps`]), refused or assumed as the own checker's is. A class
/// initializer, and a call of a JDK class JBMC is given the bytecode of ([`JDK_CLASSES`]), are asked of it.
pub(crate) fn refuses_gaps(result: &JbmcResult) -> bool {
    result.gaps.iter().any(|g| g.treatment == Some(GapTreatment::Refused) && !g.jbmc)
}

/// The note `--engine auto` writes when the own checker refused a gap, or applied a contract at one, and JBMC is
/// not asked.
pub(crate) const NOT_JBMC: &str = "note: the tool's own checker refused a gap or applied a contract at one, so JBMC is not asked: it has no bytecode for the call either, and would only approximate it with a stub of its own";

/// Why a checker's counterexample may not reproduce in the interpreter: a contract the own checker applied says
/// what the JDK's call does not, or a method JBMC had no bytecode for returned an arbitrary value.
pub(crate) fn unreproduced_cause(result: &JbmcResult) -> String {
    let applied: Vec<&str> = result.gaps.iter().filter(|g| g.treatment == Some(GapTreatment::Contract)).map(|g| g.id.as_str()).collect();
    if !applied.is_empty() {
        return format!("The path to it goes through the contract{} for {}, which the interpreter does not apply: it runs the JDK's call, so a contract probably says what the call does not (--contracts)", if applied.len() == 1 { "" } else { "s" }, applied.join(", "));
    }
    let stubs: Vec<&str> = result.gaps.iter().filter(|g| g.checker.as_deref() == Some("jbmc")).map(|g| g.id.as_str()).collect();
    if !stubs.is_empty() {
        return format!("The path to it probably goes through what JBMC approximates ({}): a stub returns any value of its type, which may be one the JDK's call never returns", stubs.join(", "));
    }
    "A method the target calls is probably missing from JBMC's class path (its models cover little of the JDK beyond java.lang.Math and the integer wrappers) and was treated as returning an arbitrary value".into()
}

/// Why a counterexample of a run that applied contracts is no verdict when the interpreter cannot run the method on
/// it (`replay` is what it said): a contract admits what the JDK's call may never do (any value in a range, any
/// elements of an array), so a witness through it is one the contracts admit, and only a run of the JDK's call
/// shows whether the JVM does it. `None` when the run applied no contract.
pub(crate) fn unconfirmed_through_contracts(result: &JbmcResult, rendered: &str, replay: &str) -> Option<String> {
    let applied: Vec<&str> = result.gaps.iter().filter(|g| g.treatment == Some(GapTreatment::Contract)).map(|g| g.id.as_str()).collect();
    if applied.is_empty() {
        return None;
    }
    let why = replay.trim_start_matches("<could not replay: ").replace(['<', '>'], "");
    Some(format!(
        "{who}'s counterexample {rendered} goes through the contract{s} for {list}, and the interpreter cannot run the method on it to confirm it ({why}). A contract admits what the JDK's call may never do, so the witness is one the contract{s} admit{verb}: run the method on it on a JVM",
        who = checker_name(result),
        s = if applied.len() == 1 { "" } else { "s" },
        verb = if applied.len() == 1 { "s" } else { "" },
        list = applied.join(", ")
    ))
}

/// Why a witness through contracts that a JVM ran is no verdict: on the JVM, with the JDK's own calls where the
/// contracts stood, the statement holds on it (`what` says what the method did there). The contracts admit what
/// the JDK's calls did not do on this input, which is no fault of theirs (a contract may admit more than a call
/// does), but the witness is not one the JVM gives.
/// In a regression proof (`regression`), each version's call takes a value of its own under a contract, so two
/// calls the versions make alike may differ under it where the JDK's do not.
pub(crate) fn not_reproduced_on_jvm(result: &JbmcResult, rendered: &str, jdk: &str, what: &str, regression: bool) -> String {
    let applied: Vec<&str> = result.gaps.iter().filter(|g| g.treatment == Some(GapTreatment::Contract)).map(|g| g.id.as_str()).collect();
    let hint = if regression {
        "; each version's call takes a value of its own under a contract, so a call the two versions make alike can differ under it although the JDK's does not"
    } else {
        "; a contract that says more of the call (the value it returns, not only a range) may decide the claim"
    };
    format!(
        "{who}'s counterexample {rendered} goes through the contract{s} for {list}, and does not reproduce on a JVM (JDK {jdk}): {what}. The contract{s} admit{verb} what the JDK's call{s} did not do on this input, so the witness is not the JVM's{hint}",
        who = checker_name(result),
        s = if applied.len() == 1 { "" } else { "s" },
        verb = if applied.len() == 1 { "s" } else { "" },
        list = applied.join(", ")
    )
}

/// The checker that gave a result, as a message names it: `the tool's own checker`, or `JBMC`.
fn checker_name(result: &JbmcResult) -> &'static str {
    if result.native.is_some() {
        "the tool's own checker"
    } else {
        "JBMC"
    }
}

/// How a witness was confirmed when the interpreter could not run it and a JVM did.
pub(crate) fn run_on_jvm_words(jdk: &str) -> String {
    format!("run on a JVM (JDK {jdk}) with the JDK's own calls where the contracts stood, since the interpreter cannot run it")
}

/// The verdict's words for the contracts a verified run rests on (`--contracts`), `, relying on 2 contracts for
/// gaps of the tool's own checker, 1 tested, 1 trusted (--gaps advised)`, and a line for each; nothing when it
/// applied none.
pub(crate) fn relied_contracts(result: &JbmcResult) -> (String, String) {
    let used: Vec<&crate::bmc::gaps::GapRecord> = result.gaps.iter().filter(|g| g.treatment == Some(GapTreatment::Contract)).collect();
    if used.is_empty() {
        return (String::new(), String::new());
    }
    let n = used.len();
    let levels = contract_levels(used.iter().filter_map(|g| g.contract.as_ref().map(|c| c.evidence)));
    let words = format!(", relying on {n} contract{} for gaps of {}, {levels} (--gaps advised)", if n == 1 { "" } else { "s" }, checker_name(result));
    let lines = used
        .iter()
        .map(|g| match &g.contract {
            Some(c) => format!("  contract: {} at {}: {} (written by {}; {})\n", g.id, g.sites.join(", "), c.summary, c.written_by, evidence_words(c)),
            None => format!("  contract: {} at {}\n", g.id, g.sites.join(", ")),
        })
        .collect();
    (words, lines)
}

/// How many contracts are at each level, strongest first: `1 tested, 1 trusted`.
pub(crate) fn contract_levels(levels: impl Iterator<Item = crate::gap_contracts::Evidence>) -> String {
    let mut counts = std::collections::BTreeMap::new();
    for e in levels {
        *counts.entry(e).or_insert(0usize) += 1;
    }
    counts.iter().map(|(e, k)| format!("{k} {}", e.name())).collect::<Vec<_>>().join(", ")
}

/// What backs a contract, in words: what testing found, or why it is trusted.
pub(crate) fn evidence_words(c: &crate::bmc::gaps::ContractUse) -> String {
    let tested = match (&c.testing, &c.untested) {
        (Some(t), _) => t.words(),
        (None, Some(why)) if c.proof.is_some() => format!("no JVM test, since {why}"),
        (None, Some(why)) => format!("trusted: no JVM test, since {why}"),
        (None, None) => "trusted: checked against neither the JDK's bytecode nor a JVM".into(),
    };
    let words = match &c.proof {
        Some(p) => format!("{}; {tested}", p.words()),
        None => tested,
    };
    match &c.recorded {
        Some(r) => format!("{words}; {r}"),
        None => words,
    }
}

/// The verdict's words for the gaps a verified run assumed, `, assuming 2 behaviours the tool's own checker does not
/// implement`, and a line for each; nothing when it assumed none.
pub(crate) fn assumed_gaps(result: &JbmcResult) -> (String, String) {
    let assumed: Vec<&crate::bmc::gaps::GapRecord> = result.gaps.iter().filter(|g| g.treatment == Some(GapTreatment::Assumed)).collect();
    if result.gap_mode != Some(crate::bmc::gaps::GapMode::Assume) || assumed.is_empty() {
        return (String::new(), String::new());
    }
    let n = assumed.len();
    let who = if assumed.iter().all(|g| g.checker.as_deref() == Some("jbmc")) { "JBMC" } else { "the tool's own checker" };
    let words = format!(", assuming {n} behaviour{} {who} does not implement (--gaps assume)", if n == 1 { "" } else { "s" });
    let lines = assumed.iter().map(|g| format!("  assumed: {}\n", g.line())).collect();
    (words, lines)
}

/// How a witness was replayed on both versions. The checker's input is run again on each version's bytecode, and
/// its result kept as the counterexample only if the two still disagree.
#[derive(Debug, Clone, Serialize)]
pub struct Replay {
    /// What ran the bytecode: `interpreter`, the tool's own bytecode interpreter (not a JVM), or `jvm`, a real JVM
    /// running the harness on the witness, when the interpreter cannot run a witness found through contracts.
    pub by: String,
    /// Whether the replay showed the disagreement the checker found; when it did not, the verdict is unverifiable.
    pub reproduced: bool,
}

/// Whether a verified statement is vacuous: the probe (the harness with the calls replaced by the assertion's
/// failure, `Harness::probe`) is run by the tool's own checker, over the harness's own domain. An input that
/// reaches the calls violates it, and a proof of it says no input in the domain does, whichever engine proved
/// the statement: the statement's proof covers no input. `skipped_by` says how an input is skipped, for the
/// reason; `render` writes the probe's witness as a call. Returns the `vacuously:` reason when vacuous, and the
/// status with how it is known (non-vacuous with the probe's witness, vacuous, or unknown when the probe gave no
/// verdict), each with its line under `✓`.
#[allow(clippy::too_many_arguments)] // the settings of the proof it probes
#[allow(clippy::too_many_arguments)]
pub(crate) fn vacuity(out: &mut String, probe: &[u8], class: &str, entries: &[PathBuf], models: bool, unwind: u32, max_array_length: u32, timeout: Duration, gaps: &crate::bmc::gaps::GapSetting, parameters: &crate::bmc::Parameters, work: &Path, skipped_by: &str, render: &dyn Fn(&JbmcResult) -> Option<String>, search: &mut Option<Search>) -> Result<(Option<String>, Vacuity), Error> {
    let probe_dir = work.join("probe");
    std::fs::create_dir_all(&probe_dir)?;
    std::fs::write(probe_dir.join(format!("{class}.class")), probe)?;
    let mut probe_entries = vec![probe_dir.clone()];
    probe_entries.extend(entries.iter().cloned());
    let result = crate::bmc::run_for_proof(&probe_entries, models, class, harness::METHOD, unwind, max_array_length, timeout, gaps, parameters, &probe_dir)?;
    if let Some(s) = search {
        s.runs.push(Run::of(&result, "probe", timeout));
    }
    Ok(match result.verdict {
        Verdict::Verified => {
            let reason = format!("no input in the domain reaches the calls, every one {skipped_by}; the proof covers no input and says nothing");
            let _ = writeln!(out, "  vacuously: {reason}");
            let vacuity = Vacuity::vacuous(&reason);
            (Some(reason), vacuity)
        }
        Verdict::Violation => {
            let witness = render(&result);
            if let Some(w) = &witness {
                let _ = writeln!(out, "  not vacuous: {w} reaches the calls");
            }
            (None, Vacuity::reached(witness))
        }
        Verdict::Unverifiable => {
            let problem = result.problem.as_deref().unwrap_or("no reason");
            let _ = writeln!(out, "  vacuity unknown: the tool's own checker gave no verdict on whether any input in the domain reaches the calls ({problem})");
            (None, Vacuity::unknown(problem))
        }
    })
}

/// The parameter values as the harness's locals, with the arrays' elements by slot, for evaluating an expression
/// over the parameters on a counterexample.
/// The record a type names, when it is an application record whose components are all primitive.
fn record_of(cp: &ClassPath, t: &Type) -> Result<Option<harness::RecordType>, Error> {
    let Type::Object(name) = t else { return Ok(None) };
    let Some(cf) = cp.application(name)? else { return Ok(None) };
    if !cf.is_record() {
        return Ok(None);
    }
    let mut components = Vec::new();
    for c in cf.record_components()? {
        let ct = Type::parse(&c.descriptor)?;
        if !ct.is_primitive() {
            return Ok(None);
        }
        components.push((c.name, ct));
    }
    Ok(Some(harness::RecordType::record(name, components)))
}

/// What a parameter of type `t` is made of in a regression check: a record of primitive components
/// ([`record_of`]); an object of an application class made by its constructor (step H2 of
/// `llm-dlc/loops/foundations-heap.md`), whose constructor parameters are primitives or objects made the same way
/// and whose fields are primitives, arrays of primitives, or references to objects of application classes whose
/// fields are so in turn; or none, for a type that is not an application class. An application class outside that
/// is a named gap: `Err` says why.
fn object_of(cp: &ClassPath, t: &Type) -> Result<Result<Option<harness::RecordType>, String>, Error> {
    if let Some(record) = record_of(cp, t)? {
        return Ok(Ok(Some(record)));
    }
    let Type::Object(name) = t else { return Ok(Ok(None)) };
    if cp.application(name)?.is_none() {
        return Ok(Ok(None));
    }
    made_of(cp, name, &mut Vec::new()).map(|r| r.map(Some))
}

/// The construction of an object of the application class `name`, as [`object_of`] says; `within` are the classes
/// whose construction this one is part of, which it may not need again (a cycle).
pub(crate) fn made_of(cp: &ClassPath, name: &str, within: &mut Vec<String>) -> Result<Result<harness::RecordType, String>, Error> {
    let java = name.replace('/', ".");
    let Some(cf) = cp.application(name)? else { return Ok(Err(format!("{java} is not among the application's classes"))) };
    if within.iter().any(|w| w == name) {
        return Ok(Err(format!("making {java} needs a {java} already: objects that contain themselves are not supported")));
    }
    if cf.is_interface() || cf.is_abstract() || cf.is_enum() {
        return Ok(Err(format!("{java} is {}; only a concrete class made by its constructor is", if cf.is_interface() { "an interface" } else if cf.is_enum() { "an enum" } else { "abstract" })));
    }
    let expected_super = if cf.is_record() { "java/lang/Record" } else { "java/lang/Object" };
    if cf.super_class.as_deref() != Some(expected_super) {
        return Ok(Err(format!("{java} extends {}; a class made by its constructor must extend Object directly", cf.super_class.as_deref().unwrap_or("nothing").replace('/', "."))));
    }
    let constructors: Vec<_> = cf.methods.iter().filter(|m| m.is_constructor() && !m.is_private() && !m.is_synthetic()).collect();
    let constructor = match constructors.as_slice() {
        [one] => *one,
        [] => return Ok(Err(format!("{java} has no constructor a caller can use"))),
        many => return Ok(Err(format!("{java} has {} constructors; an object made by one of several is not supported yet", many.len()))),
    };
    let descriptor = constructor.parsed_descriptor()?;
    let names = constructor.parameter_names(&cf.pool);
    within.push(name.to_string());
    let mut params = Vec::new();
    let mut inner = Vec::new();
    for (n, pt) in names.iter().zip(&descriptor.params) {
        match pt {
            pt if pt.is_primitive() => {}
            Type::Object(class) if cp.application(class)?.is_some() => match made_of(cp, class, within)? {
                Ok(r) => inner.push(r),
                Err(gap) => {
                    within.pop();
                    return Ok(Err(format!("the argument {n} of {java}'s constructor: {gap}")));
                }
            },
            other => {
                within.pop();
                return Ok(Err(format!("the argument {n} of {java}'s constructor has type {}; a constructor's arguments must be primitives or objects made by their constructors", other.java_name())));
            }
        }
        params.push((n.clone(), pt.clone()));
    }
    let fields = fields_of(cp, name, &mut vec![]);
    within.pop();
    match fields? {
        Ok(fields) => Ok(Ok(harness::RecordType::made(name, params, inner, fields))),
        Err(gap) => Ok(Err(gap)),
    }
}

/// The instance fields of the application class `name`, followed into the application classes they refer to
/// ([`harness::Fields`]); `within` as for [`made_of`]. A field of another type is a named gap.
pub(crate) fn fields_of(cp: &ClassPath, name: &str, within: &mut Vec<String>) -> Result<Result<harness::Fields, String>, Error> {
    let java = name.replace('/', ".");
    let Some(cf) = cp.application(name)? else { return Ok(Err(format!("{java} is not among the application's classes"))) };
    if within.iter().any(|w| w == name) {
        return Ok(Err(format!("a {java} can refer to another {java}: objects that refer to their own class are not supported yet")));
    }
    let expected_super = if cf.is_record() { "java/lang/Record" } else { "java/lang/Object" };
    if cf.super_class.as_deref() != Some(expected_super) {
        return Ok(Err(format!("{java} extends {}; the fields of a class that extends another are not supported yet", cf.super_class.as_deref().unwrap_or("nothing").replace('/', "."))));
    }
    within.push(name.to_string());
    let mut fields = Vec::new();
    for f in cf.fields.iter().filter(|f| !f.is_static()) {
        let ft = Type::parse(&f.descriptor)?;
        let kind = match &ft {
            ft if ft.is_primitive() => harness::FieldKind::Value(ft.clone()),
            Type::Array(element) if element.is_primitive() => harness::FieldKind::Array(ft.clone()),
            Type::Object(class) if cp.application(class)?.is_some() => match fields_of(cp, class, within)? {
                Ok(inner) => harness::FieldKind::Object(Box::new(inner)),
                Err(gap) => {
                    within.pop();
                    return Ok(Err(format!("the field {} of {java}: {gap}", f.name)));
                }
            },
            other => {
                within.pop();
                return Ok(Err(format!("the field {} of {java} has type {}; the fields of an object input must be primitives, arrays of primitives, or objects of application classes", f.name, other.java_name())));
            }
        };
        fields.push((f.name.clone(), kind));
    }
    within.pop();
    Ok(Ok(harness::Fields { class: name.to_string(), fields }))
}

/// Whether a regression witness is run on a JVM as well as in the interpreter (step H4): where it has an object made
/// by its constructor among its inputs, a result compared field by field, or the versions differ on it in a field
/// of an object or an identity relation. A witness of primitives, arrays and records of primitive components alone
/// is replayed in the interpreter, as before.
fn observes_objects(layout: &harness::Layout, differs: &[String]) -> bool {
    made_by_constructor(layout) || layout.result_fields.0.is_some() || layout.result_fields.1.is_some() || differs.iter().any(|d| d.starts_with("field:") || d.starts_with("identity:"))
}

/// Whether an input is an object of an application class made by its constructor (step H2), in either version: its
/// states are those the constructor makes, which a claim over it names. A record of primitive components is not
/// among them, its constructor making every state its components can hold that it accepts.
pub(crate) fn made_by_constructor(layout: &harness::Layout) -> bool {
    layout.receiver.iter().chain(&layout.args).any(|s| matches!(s, harness::Slot::Record { record, before, .. } if record.fields.is_some() || before.as_ref().is_some_and(|b| b.fields.is_some() || b.corresponds.is_some())))
}

fn locals_of(params: &[harness::Param], arguments: &[Argument]) -> (Vec<Value>, Vec<(u16, Vec<Value>)>) {
    witness::locals_of(params, arguments, &[])
}

/// The value an expression gives, as the parameter of type `t` receives it: widened to `long`, or narrowed as a
/// cast narrows, as the harness does.
fn as_parameter(v: Value, t: &Type) -> Value {
    match (t, v) {
        (Type::Long, Value::Int(i)) => Value::Long(i64::from(i)),
        (Type::Byte, Value::Int(i)) => Value::Int(i32::from(i as i8)),
        (Type::Short, Value::Int(i)) => Value::Int(i32::from(i as i16)),
        (Type::Char, Value::Int(i)) => Value::Int(i32::from(i as u16)),
        _ => v,
    }
}

/// Runs the regression proof.
pub fn run(options: &Options) -> Result<Outcome, Error> {
    crate::phases::begin();
    let outcome = run_check(options);
    let runs = outcome.as_ref().ok().and_then(|o| o.search.as_ref()).map(|s| s.runs.iter().map(|r| r.seconds).sum()).unwrap_or(0.0);
    let check = crate::phases::end(runs);
    let mut outcome = outcome?;
    if let Some(search) = &mut outcome.search {
        search.phases = check;
    }
    Ok(outcome)
}

/// [`run`], whose phases it times.
fn run_check(options: &Options) -> Result<Outcome, Error> {
    let work = match &options.work {
        Some(w) => w.clone(),
        None => crate::tla::tempfile_path("jvmcontract-equivalence"),
    };
    std::fs::create_dir_all(&work)?;
    let mut out = String::new();
    let (class_internal, method_name) = crate::verifier::parse_target(&options.target).ok_or_else(|| Error::new("target must be <class>#<method>"))?;
    let uri = sarif::source_file(&class_internal, &options.sources).map(|f| sarif::relative_uri(&options.base, &f));
    let refuse = |out: &mut String, line: u32, problem: String| -> Result<Outcome, Error> {
        let message = format!("{} cannot be verified: {problem}", options.target);
        let _ = writeln!(out, "✗ {message}");
        let findings = vec![Finding::new("unverifiable", message, uri.clone(), line)];
        if let Some(report) = &options.report {
            sarif::write(&report.join("equivalence.sarif"), &findings)?;
        }
        Ok(Outcome { verdict: Verdict::Unverifiable, target: options.target.clone(), domain: None, counterexample: None, proof: None, problem: Some(problem), statement: None, findings, output: out.clone(), work: work.clone(), shared: Vec::new(), previous: None, relation: None, vacuous: None, search: None, replay: None, stated: None, advice: None, reuse: None })
    };

    if options.contracts.is_some() && options.gaps != crate::bmc::gaps::GapMode::Advised {
        return Err(Error::new(crate::gap_contracts::CONTRACTS_NEED_ADVISED));
    }

    // 1. Both versions in one program: the old one relocated into the package "before".
    let before_dir = work.join("before-classes");
    crate::relocate::directory(&options.before, &before_dir, "before")?;

    // 2. The method, from the new version.
    let mut after_cp = ClassPath::new();
    after_cp.add(&options.after)?;
    for entry in &options.classpath {
        if entry.exists() {
            after_cp.add(entry)?;
        }
    }
    let Some(class) = after_cp.application(&class_internal)? else {
        return refuse(&mut out, 1, format!("class not found: {}", class_internal.replace('/', ".")));
    };
    let method = match crate::verifier::select_method(&class, &options.target) {
        Ok(m) => m.clone(),
        Err(problem) => return refuse(&mut out, 1, problem),
    };
    let line = method.first_line().map(u32::from).unwrap_or(1);
    let descriptor = method.parsed_descriptor()?;
    let names = method.parameter_names(&class.pool);
    // A record whose components are primitive stands in for a value of it: the receiver, a parameter or the result.
    let receiver_type = Type::Object(class_internal.clone());
    let receiver = if method.is_static() {
        None
    } else {
        match record_of(&after_cp, &receiver_type)? {
            Some(r) => Some(r),
            None => return refuse(&mut out, line, format!("{} is an instance method; a method of a record whose components are primitive is proved on the record's components, otherwise only static methods are", method_name)),
        }
    };
    let mut records = Vec::new();
    for (name, t) in names.iter().zip(&descriptor.params) {
        let record = match object_of(&after_cp, t)? {
            Ok(r) => r,
            Err(gap) => return refuse(&mut out, line, format!("parameter {name} has type {}, which is outside the objects a regression check makes: {gap}", t.java_name())),
        };
        if !t.is_primitive() && harness::expr::element_ty(t).is_none() && record.is_none() {
            return refuse(&mut out, line, format!("parameter {name} has type {}; the symbolic verifier handles primitive parameters, arrays of integral or boolean elements, records whose components are primitive, and objects of application classes made by their constructor. Finite types (enums, booleans) are covered by behavioural contracts.", t.java_name()));
        }
        records.push(record);
    }
    let result_record = record_of(&after_cp, &descriptor.ret)?;

    // The previous version: the target under the same name with the same parameters, or the method named by
    // --before-target, called with the arguments --before-arguments gives.
    let before_target = options.before_target.clone().unwrap_or_else(|| options.target.clone());
    // The relation between the results: --results-agree-when's, or a correspondence's output relation for the
    // result (step H5), as one over previous and result.
    let results_agree_when = match options.correspondence.as_ref().map(crate::spec::heap::output_relation) {
        Some(Err(gap)) => return refuse(&mut out, line, gap),
        Some(Ok(Some(_))) if options.results_agree_when.is_some() || options.before_arguments.is_some() => {
            return refuse(&mut out, line, "a correspondence and --before-arguments or --results-agree-when together are not supported; state the relation one way".into());
        }
        Some(Ok(Some(r))) => Some(r),
        _ => options.results_agree_when.clone(),
    };
    // As the user wrote it, for the report.
    let relation_shown = match &options.correspondence {
        Some(c) if options.results_agree_when.is_none() => c.outputs.first().map(|r| r.holds.clone()).or_else(|| results_agree_when.clone()),
        _ => results_agree_when.clone(),
    };
    let plain = options.before_target.is_none() && options.before_arguments.is_none() && results_agree_when.is_none();
    let (before_class_internal, before_method_name) = crate::verifier::parse_target(&before_target).ok_or_else(|| Error::new("--before-target must be <class>#<method>"))?;
    let mut before_cp = ClassPath::new();
    before_cp.add(&options.before)?;
    for entry in &options.classpath {
        if entry.exists() {
            before_cp.add(entry)?;
        }
    }
    let Some(before_class) = before_cp.application(&before_class_internal)? else {
        return refuse(&mut out, line, format!("class not found in the previous version: {}", before_class_internal.replace('/', ".")));
    };
    let before_method = match crate::verifier::select_method(&before_class, &before_target) {
        Ok(m) => m.clone(),
        Err(problem) => return refuse(&mut out, line, format!("in the previous version, {problem}; name the method as it was with --before-target")),
    };
    let before_descriptor = before_method.parsed_descriptor()?;
    let before_names = before_method.parameter_names(&before_class.pool);
    // The previous version's records: the same components, under the previous version's names. A static previous
    // version that took the components themselves (the record introduced since) is called with them by the
    // expressions of --before-arguments, which name them `this.component` or `parameter.component`.
    // A record of other components, or one the new version has no record for (a record's method made static),
    // is built from the new parameters by a constructor call among the expressions of --before-arguments, the
    // receiver's first: `new Window(this.lo, this.hi), x`.
    let components_passed = options.before_arguments.is_some();
    let receiver_built = options.before_arguments.as_deref().is_some_and(|a| a.trim_start().starts_with("new") && a.trim_start()[3..].starts_with(char::is_whitespace));
    let mut previous_receiver = None;
    let before_receiver = match (&receiver, before_method.is_static()) {
        (None, true) => None,
        (Some(r), true) if components_passed => Some((r.clone(), None)),
        (_, false) => match record_of(&before_cp, &Type::Object(before_class_internal.clone()))? {
            Some(b) if receiver.as_ref().is_some_and(|r| b.same_shape(r)) && !receiver_built => Some((receiver.clone().expect("checked"), Some(b))),
            Some(b) if components_passed => {
                previous_receiver = Some(b);
                receiver.as_ref().map(|r| (r.clone(), None))
            }
            Some(b) => {
                let build = format!("new {}({})", b.simple_name(), b.components.iter().map(|(c, _)| if receiver.is_some() { format!("this.{c}") } else { c.clone() }).collect::<Vec<_>>().join(", "));
                let example = std::iter::once(build).chain(before_names.iter().cloned()).collect::<Vec<_>>().join(", ");
                return match &receiver {
                    Some(r) => refuse(&mut out, line, format!("the receiver's components changed: {} before, {} now; build the previous version's receiver from the new components with --before-arguments, such as \"{example}\"", b.describe(), r.describe())),
                    None => refuse(&mut out, line, format!("the previous version is a method of the record {} and the new one a static method; build its receiver from the new parameters with --before-arguments, such as \"{example}\"", b.simple_name())),
                };
            }
            None => return refuse(&mut out, line, format!("the previous version's class {} is not a record whose components are primitive", before_class_internal.replace('/', "."))),
        },
        (Some(r), true) => {
            let example = r.components.iter().map(|(c, _)| format!("this.{c}")).chain(names.iter().cloned()).collect::<Vec<_>>().join(", ");
            return refuse(&mut out, line, format!("the previous version is a static method and the new one a method of the record {}; give the previous version's arguments as expressions over the record's components and the parameters with --before-arguments, such as \"{example}\"", r.simple_name()));
        }
    };
    // A correspondence's input equations (step H5): each giving a field path of the previous version's parameter, from
    // a path or an expression over the same parameter's, the primitive parameters and other objects' arguments (H5's
    // rest).
    let correspondence = options.correspondence.as_ref().filter(|c| !c.inputs.is_empty() || !c.outputs.is_empty());
    if let Some(c) = correspondence {
        if components_passed || options.results_agree_when.is_some() {
            return refuse(&mut out, line, "a correspondence and --before-arguments or --results-agree-when together are not supported; state the relation one way".into());
        }
        let roots = match crate::spec::heap::roots(c) {
            Ok(r) => r,
            Err(gap) => return refuse(&mut out, line, gap),
        };
        for (old_root, new_root, whole) in roots {
            // Equations about no parameter of either version relate no input of this method, and say nothing here.
            if !before_names.contains(&old_root) && !new_root.as_ref().is_some_and(|r| names.contains(r)) {
                let _ = writeln!(out, "note: the correspondence's equation about {old_root} relates no parameter of either version, and says nothing about this method");
                continue;
            }
            let position = before_names.iter().position(|n| *n == old_root);
            // An expression that reads no field (`new.n * 100`) is about the parameter in the previous one's place.
            let new_root = new_root.unwrap_or_else(|| position.and_then(|i| names.get(i)).cloned().unwrap_or_default());
            let same = position.is_some_and(|i| names.get(i) == Some(&new_root));
            let object = position.is_some_and(|i| records.get(i).is_some_and(|r| r.as_ref().is_some_and(harness::RecordType::is_made)));
            match (same, object, whole) {
                (true, true, false) | (true, false, true) => {}
                (true, true, true) => return refuse(&mut out, line, format!("the correspondence relates the previous version's {old_root} to the new one's as a whole; give equations between their fields")),
                (true, false, false) => return refuse(&mut out, line, format!("the correspondence names a field of {old_root}, which is not an object made by its constructor")),
                (false, _, _) => return refuse(&mut out, line, format!("the correspondence relates the previous version's {old_root} to the new version's {new_root}, which is not the parameter in its place; only equations between the two versions' same parameter are supported yet")),
            }
        }
    }
    let mut both_records = Vec::new();
    // The new version's parameters, which an input equation's expression may read (H5's rest).
    let new_params: Vec<(String, Type)> = names.iter().cloned().zip(descriptor.params.iter().cloned()).collect();
    // And its object parameters made by their constructor, whose leaves an expression may read (H5's rest).
    let new_objects: Vec<(String, harness::RecordType)> = names.iter().zip(&records).filter_map(|(n, r)| r.as_ref().filter(|r| r.is_made()).map(|r| (n.clone(), r.clone()))).collect();
    for (i, ((name, t), record)) in names.iter().zip(&descriptor.params).zip(&records).enumerate() {
        both_records.push(match record {
            Some(r) if components_passed => Some((r.clone(), None)),
            Some(r) => match object_of(&before_cp, t)?.ok().flatten() {
                // Under a correspondence's input equations about it, the previous version's object is made from
                // the new one's leaves as they say, of whatever shape.
                Some(mut b) if correspondence.is_some() && r.is_made() && b.is_made() && crate::spec::heap::relate(correspondence.expect("checked"), &before_names[i], name, r, &b, &new_params, &new_objects).is_some() => {
                    match crate::spec::heap::relate(correspondence.expect("checked"), &before_names[i], name, r, &b, &new_params, &new_objects).expect("checked") {
                        Ok(related) => {
                            b.corresponds = Some(related);
                            Some((r.clone(), Some(b)))
                        }
                        Err(gap) => return refuse(&mut out, line, gap),
                    }
                }
                // Of the same shape and with no input equation about it, but output relations for its fields (H5's
                // rest): each in place of equality for its path, the other paths compared for equality.
                Some(mut b) if correspondence.is_some() && r.is_made() && b.is_made() && b.same_shape(r) && crate::spec::heap::relate_same_shape(correspondence.expect("checked"), &before_names[i], name, r, &b).is_some() => {
                    match crate::spec::heap::relate_same_shape(correspondence.expect("checked"), &before_names[i], name, r, &b).expect("checked") {
                        Ok(related) => {
                            b.corresponds = Some(related);
                            Some((r.clone(), Some(b)))
                        }
                        Err(gap) => return refuse(&mut out, line, gap),
                    }
                }
                Some(b) if b.same_shape(r) => Some((r.clone(), Some(b))),
                Some(b) if r.is_made() || b.is_made() => {
                    return refuse(&mut out, line, format!("parameter {name} is made differently in the two versions: {} before, {} now; relate them with a correspondence's input equations between their fields, such as old.{name}.f == new.{name}.g", b.domain_part(name), r.domain_part(name)));
                }
                Some(b) => {
                    let example = names.iter().zip(&records).map(|(n, rec)| match rec {
                        Some(_) if n == name => format!("new {}({})", b.simple_name(), b.components.iter().map(|(c, _)| format!("{n}.{c}")).collect::<Vec<_>>().join(", ")),
                        _ => n.clone(),
                    }).collect::<Vec<_>>().join(", ");
                    return refuse(&mut out, line, format!("the components of parameter {name} changed: {} before, {} now; build the previous version's record from the new components with --before-arguments, such as \"{example}\"", b.describe(), r.describe()));
                }
                None => return refuse(&mut out, line, format!("in the previous version, {} is not a record whose components are primitive; give its arguments as expressions over the record's components with --before-arguments", t.java_name())),
            },
            None => None,
        });
    }
    // An output relation for a parameter's fields (H5's rest) is compared with the parameter its input equations
    // relate; one about anything else is refused.
    if let Some(c) = correspondence {
        for (root, r) in crate::spec::heap::field_relation_roots(c) {
            let taken = before_names.iter().position(|n| *n == root).and_then(|i| both_records.get(i)).and_then(|b| b.as_ref()).and_then(|(_, b)| b.as_ref()).and_then(|b| b.corresponds.as_ref()).is_some_and(|c| c.relations.iter().any(|x| x.observation(&root) == r.observation));
            if !taken {
                return refuse(&mut out, line, format!("the correspondence's output relation for {} ({}) is about {root}, which is not an object parameter made by its constructor that the correspondence's input equations relate or that has the same shape in both versions: only relations for such a parameter's fields, and one for the result, are supported yet", r.observation, r.holds));
            }
        }
    }
    // The records among the previous version's parameters, each built by a constructor call among the expressions.
    let mut previous_records = Vec::new();
    for t in &before_descriptor.params {
        previous_records.push(if components_passed { record_of(&before_cp, t)? } else { None });
    }
    // The result's records: of the same shape, compared component by component; otherwise, or when the result
    // became a record or stopped being one, related by --results-agree-when over the components.
    let relation_given = results_agree_when.is_some();
    let before_result = record_of(&before_cp, &before_descriptor.ret)?;
    let first_component = |r: &harness::RecordType| r.components.first().map(|(c, _)| c.clone()).unwrap_or_default();
    let relate = "say how the results are related with --results-agree-when, a boolean expression over the new parameters";
    let result = match (&result_record, &before_result) {
        (Some(r), Some(b)) if b.same_shape(r) && !relation_given => (Some(r.clone()), Some(b.clone())),
        (Some(r), Some(b)) if !relation_given => {
            let common: Vec<String> = b.components.iter().filter(|(c, t)| r.components.iter().any(|(d, u)| d == c && u == t)).map(|(c, _)| format!("previous.{c} == result.{c}")).collect();
            let example = if common.is_empty() { format!("previous.{} == result.{}", first_component(b), first_component(r)) } else { common.join(" && ") };
            return refuse(&mut out, line, format!("the result's components changed: {} before, {} now; {relate} and the results' components previous.c and result.c, such as \"{example}\"", b.describe(), r.describe()));
        }
        (Some(r), None) if !relation_given && (before_descriptor.ret.is_primitive() || matches!(before_descriptor.ret, Type::Array(_))) => {
            return refuse(&mut out, line, format!("the previous version returns {} and the new one the record {}; {relate}, previous and the result's components result.c, such as \"previous == result.{}\"", before_descriptor.ret.java_name(), r.describe(), first_component(r)));
        }
        (Some(_), None) if !relation_given => return refuse(&mut out, line, format!("the previous version returns {} and the new one the record {}; a regression proof relates the same components in both versions", before_descriptor.ret.java_name(), descriptor.ret.java_name())),
        (None, Some(b)) if !relation_given && (descriptor.ret.is_primitive() || matches!(descriptor.ret, Type::Array(_))) => {
            return refuse(&mut out, line, format!("the previous version returns the record {} and the new one {}; {relate}, the previous result's components previous.c and result, such as \"previous.{} == result\"", b.describe(), descriptor.ret.java_name(), first_component(b)));
        }
        (None, Some(b)) if !relation_given => return refuse(&mut out, line, format!("the previous version returns the record {} and the new one {}; a regression proof relates the same components in both versions", b.java_name(), descriptor.ret.java_name())),
        (r, b) => (r.clone(), b.clone()),
    };
    // A result of an application class other than a record of primitive components (step H3 of
    // `llm-dlc/loops/foundations-heap.md`): compared by its fields, as an object parameter is, and followed for the
    // identity relations. An enum, an interface or an abstract class is compared as before.
    let mut result_equations = None;
    let result_fields = if result.0.is_some() || result.1.is_some() {
        (None, None)
    } else {
        let fields = |cp: &ClassPath, t: &Type| -> Result<Option<Result<harness::Fields, String>>, Error> {
            let Type::Object(name) = t else { return Ok(None) };
            match cp.application(name)? {
                Some(cf) if !cf.is_enum() && !cf.is_interface() && !cf.is_abstract() => Ok(Some(fields_of(cp, name, &mut Vec::new())?)),
                _ => Ok(None),
            }
        };
        // Results of the classes of a parameter the correspondence relates are compared under its equations.
        let related = |new: &harness::Fields, old: &harness::Fields| {
            both_records.iter().flatten().find_map(|(r, b)| match (&r.fields, b) {
                // Equations that read a parameter (H5's rest) are about the parameter in this call, not about every
                // object of its classes.
                (Some(f), Some(b)) if f.class == new.class && b.fields.as_ref().is_some_and(|g| g.class == old.class) => b.corresponds.as_ref().filter(|c| !c.same_shape && !c.equations.iter().any(harness::FieldEquation::reads_parameters)).map(|c| c.equations.clone()),
                _ => None,
            })
        };
        match (fields(&after_cp, &descriptor.ret)?, fields(&before_cp, &before_descriptor.ret)?) {
            // Under a relation between the results, an object result is in it by its field paths, of whatever
            // shape in each version (step H5).
            (Some(Err(gap)), _) if relation_given => return refuse(&mut out, line, format!("the result has type {}, which a result relation cannot read: {gap}", descriptor.ret.java_name())),
            (_, Some(Err(gap))) if relation_given => return refuse(&mut out, line, format!("in the previous version, the result has type {}, which a result relation cannot read: {gap}", before_descriptor.ret.java_name())),
            (new, old) if relation_given => (new.and_then(Result::ok), old.and_then(Result::ok)),
            (Some(Ok(new)), Some(Ok(old))) if related(&new, &old).is_some() => {
                result_equations = related(&new, &old);
                (Some(new), Some(old))
            }
            (Some(Err(gap)), _) => return refuse(&mut out, line, format!("the result has type {}, which is outside the objects a regression check compares: {gap}", descriptor.ret.java_name())),
            (_, Some(Err(gap))) => return refuse(&mut out, line, format!("in the previous version, the result has type {}, which is outside the objects a regression check compares: {gap}", before_descriptor.ret.java_name())),
            (Some(Ok(new)), Some(Ok(old))) if new.same_shape(&old) => (Some(new), Some(old)),
            (Some(Ok(new)), Some(Ok(old))) => {
                let paths = |f: &harness::Fields| f.paths().iter().map(|(p, _)| p.clone()).collect::<Vec<_>>().join(", ");
                return refuse(&mut out, line, format!("the result's fields changed: {} ({}) before, {} ({}) now; a correspondence relates results of different shapes only where its input equations relate a parameter of the same classes", old.class.replace('/', "."), paths(&old), new.class.replace('/', "."), paths(&new)));
            }
            _ => (None, None),
        }
    };
    let mut layout = harness::Layout::new(before_receiver, &names, &descriptor.params, &both_records, result);
    layout.result_fields = result_fields;
    layout.result_equations = result_equations;
    // Object parameters that may be null or one object (step H2): a choice each, made by the harness's flags.
    if !options.nullable.is_empty() || !options.may_alias.is_empty() {
        let order: Vec<String> = std::iter::once("this".to_string()).chain(names.iter().cloned()).collect();
        if let Some((a, _)) = options.may_alias.iter().find(|(a, b)| a == b) {
            return refuse(&mut out, line, format!("--may-alias {a},{a}: name two different parameters"));
        }
        if let Err(problem) = layout.choose(&options.nullable, &harness::alias_groups(&options.may_alias, &order)) {
            return refuse(&mut out, line, problem);
        }
        // An input equation reads another object's leaves as the arguments it was made from (H5's rest), which
        // are not its fields where it is null or another parameter's object.
        for (i, slot) in layout.args.iter().enumerate() {
            let harness::Slot::Record { name, before: Some(previous), .. } = slot else { continue };
            let Some(c) = previous.corresponds.as_ref() else { continue };
            let read = c.equations.iter().find_map(|e| e.computed.as_ref()?.reads.iter().filter(|r| r.param).find_map(|r| r.path.split_once('.').map(|(root, _)| (e, root.to_string(), r.path.clone()))));
            if let Some((e, root, path)) = read.filter(|(_, root, _)| layout.choice(root).is_some()) {
                return refuse(&mut out, line, format!("the correspondence's input equation {} reads new.{path}, and {root} may be null or another parameter's object: an equation that reads another object's fields is supported only where that object is made by its constructor, of its own", e.text(&before_names[i], name)));
            }
        }
    }
    // The correspondence's output relations for identity relations (H5's rest), each compared in place of "holds
    // before iff it holds now" for one the check observes.
    if let Some(c) = correspondence {
        match crate::spec::heap::identity_relations(c, &layout.identity_pairs(&descriptor.ret, &before_descriptor.ret, options.before_arguments.is_none())) {
            Ok(relations) => layout.identity_relations = relations,
            Err(gap) => return refuse(&mut out, line, gap),
        }
    }
    let layout = layout;
    let params = &layout.params;
    let flat_types = layout.types();
    let has_arrays = params.iter().any(|p| matches!(p.ty, Type::Array(_)));
    if before_descriptor.ret != descriptor.ret && results_agree_when.is_none() && !(layout.result.0.is_some() && layout.result.1.is_some()) {
        return refuse(&mut out, line, format!("the previous version returns {} and the new one {}; say how the results are related with --results-agree-when, a boolean expression over the new parameters, previous and result", before_descriptor.ret.java_name(), descriptor.ret.java_name()));
    }
    if plain && before_descriptor.params != descriptor.params {
        return refuse(&mut out, line, format!(
            "the previous version takes ({}) and the new one ({}); give the previous version's arguments as expressions over the new parameters with --before-arguments",
            before_descriptor.params.iter().map(Type::java_name).collect::<Vec<_>>().join(", "),
            descriptor.params.iter().map(Type::java_name).collect::<Vec<_>>().join(", ")
        ));
    }
    // The previous version's own layout, for replaying it on the arguments computed by the expressions: its
    // records, built by expressions, flattened into their components.
    let mut before_layout = harness::Layout::new(
        previous_receiver.clone().map(|r| (r.clone(), Some(r))),
        &before_names,
        &before_descriptor.params,
        &previous_records.iter().map(|r| r.clone().map(|r| (r.clone(), Some(r)))).collect::<Vec<_>>(),
        (None, None),
    );
    before_layout.result_fields = layout.result_fields.clone();
    before_layout.result_equations = layout.result_equations.clone();
    let before_layout = before_layout;
    let before_params = &before_layout.params;
    let previous = (!plain).then(|| harness::BeforeMethod {
        owner: before_class_internal.clone(),
        method: before_method_name.clone(),
        descriptor: before_method.descriptor.clone(),
        params: before_descriptor.params.clone(),
        names: before_names.clone(),
        arguments: options.before_arguments.clone(),
        receiver: previous_receiver.clone(),
        records: previous_records.clone(),
        ret: before_descriptor.ret.clone(),
        relation: results_agree_when.clone(),
    });
    let previous_display = previous.as_ref().map(|b| b.display(&class_internal));
    // An object made by its constructor stands for the states its constructor makes and no others (a throttle that
    // starts full is never one that calls have drained), so where the claim says "every input" it says that too.
    let every = if made_by_constructor(&layout) { "every input of constructor-made objects" } else { "every input" };
    let relation = match (&previous_display, &relation_shown) {
        (Some(p), Some(r)) => format!("agrees with the previous {p} on {every}, the results related by {r}"),
        (Some(p), None) => format!("behaves as the previous {p} on {every}"),
        (None, _) => format!("behaves as before on {every}"),
    };
    let domain = layout.domain(options.max_array_length);
    // The statement as data: what holds of every verdict on this harness, and what the run it comes from adds.
    let stated_domain = crate::statement::domain(&layout, options.max_array_length);
    let mut observations = crate::statement::regression_observations(&layout, &descriptor.ret, relation_shown.as_deref());
    observations.identities = layout
        .identity_pairs(&descriptor.ret, &before_descriptor.ret, options.before_arguments.is_none())
        .iter()
        .map(|(x, y)| match layout.identity_relation(x, y) {
            Some(r) => format!("{x} == {y}, under the output relation {}", r.holds.trim()),
            None => format!("{x} == {y}"),
        })
        .collect();
    let observations = observations;
    let mut claim_assumptions = crate::statement::regression_assumptions(&layout, options.unchanged_unless.as_deref(), options.before_arguments.as_deref());

    // 3. The statement, as a harness JBMC can check.
    let harness = match harness::generate(&class_internal, &method_name, &layout, &descriptor.ret, options.unchanged_unless.as_deref(), options.max_array_length, previous.as_ref()) {
        Ok(h) => h,
        Err(e) => return refuse(&mut out, line, e.to_string()),
    };
    let harness_dir = work.join("harness");
    std::fs::create_dir_all(&harness_dir)?;
    std::fs::write(harness_dir.join(format!("{}.class", harness::CLASS)), &harness.bytes)?;
    let statement = harness_dir.join(format!("{}.java", harness::CLASS));
    std::fs::write(&statement, &harness.source)?;
    let restriction = options.unchanged_unless.as_deref().map(|s| format!(" where !({s})")).unwrap_or_default();

    // 4. What the two versions share: a target identical in both, with everything it reaches, needs no proof; a
    // callee unchanged in both is one function in both.
    let with_jdk = |dir: &Path| -> Result<ClassPath, Error> {
        let mut cp = ClassPath::new();
        cp.add(dir)?;
        for entry in &options.classpath {
            if entry.exists() {
                cp.add(entry)?;
            }
        }
        Ok(cp.with_default_jdk())
    };
    let shared_after_cp = with_jdk(&options.after)?;
    let shared_before_cp = with_jdk(&options.before)?;
    // A changed pure helper is shared too once its own proof shows its two versions agree on every input
    // ([`crate::proof_cache::Helpers`]): under `--cache` and `--engine native`, proved first or found in the cache.
    let mut helpers = crate::proof_cache::Helpers::new(options, &work);
    let mut plan = if options.shared_callees {
        shared::plan_with(&shared_before_cp, &shared_after_cp, &MemberRef::new(&before_class_internal, &before_method_name, &before_method.descriptor), &MemberRef::new(&class_internal, &method_name, &method.descriptor), plain, &mut |c| helpers.prove(c))
    } else {
        shared::Plan::default()
    };
    out.push_str(&helpers.notes);
    claim_assumptions.extend(helpers.assumptions().iter().cloned());
    let stated = |last: Option<&JbmcResult>, search: Option<&Search>, complete: bool| crate::statement::Statement {
        kind: "regression".into(),
        domain: stated_domain.clone(),
        assumptions: claim_assumptions.iter().cloned().chain(crate::statement::checker_assumptions(last)).collect(),
        observations: observations.clone(),
        bounds: crate::statement::bounds(last.map(|_| options.unwind), &stated_domain, options.max_array_length, complete),
        models: crate::statement::models(options.models && last.is_some()),
        checker: crate::statement::checker(search, options.sat_solver.as_deref(), || crate::jbmc::sat(&options.jbmc, options.sat_solver.as_deref(), options.refine_strings)),
        gap_mode: last.and_then(|l| l.gap_mode),
        confirmation: search.and_then(|s| s.confirmation.as_ref()).map(|c| c.status),
        vacuity: None,
        spec: None,
    };
    // The harness builds each record through its constructor in both versions: a target identical in both needs no
    // proof only when the constructors are too.
    if plan.identical.is_some() {
        let constructors: Vec<MemberRef> = layout
            .records()
            .iter()
            .flat_map(|s| match s {
                harness::Slot::Record { record, .. } => record.constructors().into_iter().map(|(owner, d)| MemberRef::new(&owner, "<init>", &d)).collect(),
                harness::Slot::Plain(_) => Vec::new(),
            })
            .collect();
        if !shared::identical_closure(&shared_before_cp, &shared_after_cp, &constructors) {
            plan.identical = None;
        }
    }
    if let Some(compared) = plan.identical {
        let how = match compared - 1 {
            0 => "its bytecode is identical in both versions and it reaches no other method; nothing to prove".to_string(),
            1 => "its bytecode and that of the method it reaches are identical in both versions; nothing to prove".to_string(),
            n => format!("its bytecode and that of the {n} methods it reaches are identical in both versions; nothing to prove"),
        };
        let _ = writeln!(out, "✓ {} {relation}{restriction} ({how})", options.target);
        if let Some(report) = &options.report {
            sarif::write(&report.join("equivalence.sarif"), &[])?;
        }
        // The constructors are among the identical bytecode, so they accept the same inputs: no caveat applies.
        let mut identical = stated(None, None, true);
        identical.assumptions.retain(|a| a.kind != crate::statement::AssumptionKind::Constructible);
        identical.vacuity = Some(Vacuity::identical());
        return Ok(Outcome { verdict: Verdict::Verified, target: options.target.clone(), domain: Some(domain), counterexample: None, proof: Some(how), problem: None, statement: Some(statement), findings: Vec::new(), output: out, work, shared: Vec::new(), previous: None, relation: None, vacuous: None, search: None, replay: None, stated: Some(identical), advice: None, reuse: None });
    }
    let shared_names = shared::names(&plan.callees);
    // The proof cache (`--cache`, [`crate::proof_cache`]), on the claim as prepared: a result stored for it is the
    // result, a refuted one once its witness reproduces again.
    let (cache, hit) = crate::proof_cache::Regression {
        options,
        before_cp: &shared_before_cp,
        after_cp: &shared_after_cp,
        before_target: MemberRef::new(&before_class_internal, &before_method_name, &before_method.descriptor),
        target: MemberRef::new(&class_internal, &method_name, &method.descriptor),
        layout: &layout,
        previous: previous.as_ref(),
        before_parameters: &before_names,
        domain: &stated_domain,
        observations: &observations,
        assumptions: &claim_assumptions,
        shared: &shared_names,
        harness: &harness_dir,
        before_classes: &before_dir,
        shown: crate::proof_cache::Shown { domain: &domain, statement: &statement, work: &work, previous: previous_display.as_deref(), uri: uri.as_deref(), line },
    }
    .lookup(&mut out)?;
    if let Some(hit) = hit {
        return Ok(hit);
    }

    // 5. The JDK bytecode JBMC needs beyond its own models, and the tool's models of the JDK classes it has none of.
    let jdk_dir = work.join("jdk");
    if let Err(e) = extract_jdk_classes(&jdk_dir, options.java_home.as_deref()) {
        let _ = writeln!(out, "note: {e}; JBMC will use its own models of java.lang.Math");
    }
    let models_dir = work.join("models");
    if options.models {
        crate::models::write_to(&models_dir)?;
    }

    // 6. Prove, or search for a counterexample: small inputs first, then all of them. The models come last on the
    // class path, so that a class the application or its class path has takes precedence. With callees to share,
    // the stub and the classes whose calls are redirected to it come first, ahead of the versions as written.
    let mut classpath = vec![harness_dir.clone(), options.after.clone(), before_dir.clone(), jdk_dir.clone()];
    classpath.extend(options.classpath.iter().cloned());
    if options.models {
        classpath.push(models_dir.clone());
    }
    let mut shared_classpath = None;
    let shared_versions = [options.after.as_path(), before_dir.as_path()];
    if !plan.callees.is_empty() {
        let dir = work.join("shared-classes");
        shared::stub_directory(&shared_after_cp, &plan.callees, &shared_versions, &dir)?;
        let mut cp = classpath.clone();
        cp.insert(1, dir);
        shared_classpath = Some(cp);
    }
    let started = std::time::Instant::now();
    // One deadline for the whole check, each run a budget out of it ([`crate::deadline`]).
    let deadline = Deadline::starting_now(helpers.remaining(Duration::from_secs(options.timeout_seconds)));
    let mut runs = Vec::new();
    let mut last = None;
    // The tool's own checker first, when asked: its verdict stands, and where it has none, JBMC's turn (under
    // `auto`), or that is the answer (under `native`). JBMC's interval stages run only where they bound an input,
    // and only those its staging policy picks ([`crate::deadline::Staging`]).
    let mut stages = options.jbmc_staging.stages(&crate::deadline::entry_parameters(&harness.bytes, harness::METHOD)?);
    let mut fallback = None;
    let mut gap_setting = crate::bmc::gaps::GapSetting::from(options.gaps);
    let mut entries: Vec<PathBuf> = classpath.iter().filter(|p| **p != jdk_dir && **p != models_dir).cloned().collect();
    // Under the tool's own checker, a changed helper proved equivalent is its new version in both: the previous
    // version's calls of it are redirected there ([`shared::substitute_directory`]).
    let native_shared = shared::substitute(&plan.callees, &before_dir, &work.join("substituted-classes"), &mut entries)?;
    let contract_options = crate::gap_contracts::ContractOptions { file: options.contracts.clone(), library: options.contract_library, max_trust: options.max_trust };
    let claim = crate::advice::Claim { kind: "regression".into(), target: options.target.clone(), text: format!("{relation}{restriction}"), harness: statement.clone() };
    // Under advised, a gap the proof reaches with no contract goes to the agent before anything is solved.
    let stop_with = |out: &mut String, advice: crate::advice::Advice| -> Result<Outcome, Error> {
        let p = advice.problem();
        let message = format!("{} cannot be verified: {p}", options.target);
        let _ = writeln!(out, "✗ {message}");
        out.push_str(&advice.lines());
        let findings = vec![Finding::new("gaps-need-contracts", message, uri.clone(), line)];
        if let Some(report) = &options.report {
            sarif::write(&report.join("equivalence.sarif"), &findings)?;
        }
        let mut s = stated(None, None, false);
        s.checker = crate::statement::scan_checker();
        s.gap_mode = Some(crate::bmc::gaps::GapMode::Advised);
        Ok(Outcome { verdict: Verdict::Unverifiable, target: options.target.clone(), domain: Some(domain.clone()), counterexample: None, proof: None, problem: Some(p), statement: Some(statement.clone()), findings, output: out.clone(), work: work.clone(), shared: Vec::new(), previous: previous_display.clone(), relation: relation_shown.clone(), vacuous: None, search: None, replay: None, stated: Some(s), advice: Some(advice), reuse: None })
    };
    if options.engine != crate::Engine::Jbmc {
        // Under advised, what the harness may reach first: the contract library closes only gaps it reaches.
        let scanned = if options.gaps == crate::bmc::gaps::GapMode::Advised { Some(crate::advice::scan_harness(&entries, options.models, harness::CLASS, harness::METHOD)?) } else { None };
        let (setting, loaded, notes) = crate::gap_contracts::setting(options.gaps, &contract_options, scanned.as_ref().map(|(_, s)| s), &entries, options.models, &work)?;
        gap_setting = setting;
        out.push_str(&notes);
        if options.gaps == crate::bmc::gaps::GapMode::Advised {
            let (cp, scan) = scanned.as_ref().expect("scanned under advised");
            if let Some(advice) = crate::advice::preflight(cp, scan, claim.clone(), &work, loaded.as_ref(), None)? {
                return stop_with(&mut out, advice);
            }
        }
        let budget = own_budget(&deadline, options.engine);
        let result = crate::bmc::run_for_proof(&entries, options.models, harness::CLASS, harness::METHOD, options.unwind, options.max_array_length, budget, &gap_setting, &crate::bmc::Parameters::default(), &work)?;
        runs.push(Run::of(&result, "proof", budget));
        if result.verdict != Verdict::Unverifiable || options.engine == crate::Engine::Native || refuses_gaps(&result) {
            if options.engine == crate::Engine::Auto && result.verdict == Verdict::Unverifiable {
                let _ = writeln!(out, "{}", NOT_JBMC);
            }
            stages.clear();
            last = Some(result);
        } else {
            let _ = writeln!(out, "note: the tool's own checker gave no verdict ({}); JBMC", result.problem.as_deref().unwrap_or("no reason"));
            fallback = Some(result.problem.clone().unwrap_or_else(|| "no reason".into()));
        }
    }
    // An array parameter is never null, and is bounded in length: the copying and comparing loops, and the
    // method's own, are what the unwinding bound must cover.
    let extra_args = if has_arrays {
        vec!["--java-assume-inputs-non-null".to_string(), "--max-nondet-array-length".to_string(), options.max_array_length.to_string()]
    } else {
        Vec::new()
    };
    let base = |classpath: &[PathBuf], tag: &str| JbmcRun {
        executable: crate::jbmc::executable(&options.jbmc),
        class: harness::CLASS.into(),
        function: harness::METHOD.into(),
        classpath: classpath.to_vec(),
        unwind: options.unwind,
        timeout: Duration::ZERO,
        stage: None,
        refine_strings: options.refine_strings,
        sat_solver: options.sat_solver.clone(),
        log: work.join(format!("jbmc{tag}.log")),
        extra_args: extra_args.clone(),
    };
    // Under `--engine jbmc --gaps advised`, the contracts for the gaps JBMC's program reaches, with the advice when
    // one has none ([`crate::jbmc_contracts`]); under `auto`, JBMC applies the own checker's.
    if options.gaps == crate::bmc::gaps::GapMode::Advised && options.engine == crate::Engine::Jbmc && !stages.is_empty() {
        let pre = crate::jbmc_gaps::preflight(&base(&classpath, ""), deadline.share(crate::deadline::STAGE_SHARE))?;
        let prepared = crate::jbmc_contracts::prepare(&pre, &contract_options, claim.clone(), &entries, options.models, &work)?;
        out.push_str(&prepared.notes);
        gap_setting = prepared.setting;
        if let Some(advice) = prepared.advice {
            return stop_with(&mut out, advice);
        }
    }
    let contract_cp = witness::classpath(entries.iter().map(PathBuf::as_path))?;
    // Each class path's runs are held to what JBMC approximates on it (its stubs, the call sites it does not
    // link), from its goto program ([`crate::jbmc_gaps`]); under advised, with the contracts for its gaps applied.
    let run_stages = |classpath: &[PathBuf], tag: &str, purpose: &str, runs: &mut Vec<Run>, notes: &mut String| -> Result<Option<JbmcResult>, Error> {
        let mut last: Option<JbmcResult> = None;
        let mut first = base(classpath, tag);
        let mut preflight = if stages.is_empty() { None } else { Some(crate::jbmc_gaps::preflight(&first, deadline.share(crate::deadline::STAGE_SHARE))?) };
        let mut applied = None;
        if let (crate::bmc::gaps::GapMode::Advised, Some(found)) = (options.gaps, preflight.as_ref().and_then(|p| p.found.as_ref())) {
            if !gap_setting.contracts.is_empty() {
                let dir = work.join(format!("jbmc-contracts{tag}"));
                let rewrite: Vec<PathBuf> = classpath.iter().filter(|p| **p != jdk_dir && **p != models_dir).cloned().collect();
                let a = crate::jbmc_contracts::apply(&gap_setting, found, classpath, &rewrite, &contract_cp, &dir)?;
                notes.push_str(&a.notes);
                if !a.records.is_empty() {
                    let _ = writeln!(notes, "note: JBMC applies {} contract{} for its gaps, at their call sites in {} class{} rewritten ({})", a.records.len(), if a.records.len() == 1 { "" } else { "s" }, a.classes, if a.classes == 1 { "" } else { "es" }, dir.display());
                    first = JbmcRun { classpath: a.classpath.clone(), log: dir.join("jbmc.log"), ..first };
                    preflight = Some(crate::jbmc_gaps::preflight(&first, deadline.share(crate::deadline::STAGE_SHARE))?);
                    applied = Some(a);
                }
            }
        }
        for stage in &stages {
            let budget = deadline.for_stage(*stage, options.jbmc_staging);
            let run = JbmcRun { timeout: budget, stage: stage.map(str::to_string), log: work.join(format!("jbmc{tag}{}.log", stage.map(|s| format!("-{}", s.replace(|c: char| !c.is_ascii_digit() && c != '-', "_"))).unwrap_or_default())), ..first.clone() };
            let result = jbmc::run(&run)?;
            runs.push(Run::of(&result, purpose, budget));
            // A preliminary stage out of its budget hands on: only the last stage is the proof.
            let stop = result.verdict != Verdict::Verified && !(stage.is_some() && result.out_of_time());
            last = Some(result);
            if stop {
                break;
            }
        }
        if let (Some(result), Some(pre)) = (last.as_mut(), preflight.as_ref()) {
            notes.push_str(&pre.note());
            crate::jbmc_gaps::hold(result, pre, options.gaps);
            if let Some(a) = &applied {
                crate::jbmc_contracts::settle(result, a);
            }
        }
        Ok(last)
    };
    let replay_cp = witness::classpath([options.after.as_path(), before_dir.as_path()].into_iter().chain(options.classpath.iter().map(PathBuf::as_path)))?.with_models(options.models);
    let before_owner = format!("before/{before_class_internal}");
    // The previous version's method as relocated: its records are under before/ too.
    let before_relocated = match &previous {
        Some(b) => b.relocated_descriptor(&layout),
        None => layout.before_descriptor(&before_descriptor.params, &before_descriptor.ret),
    };
    // The previous version's arguments on a counterexample: the new version's, or the expressions over them, as
    // the flat parameters of the previous version's layout (a record built by an expression as its components).
    let map_arguments = |arguments: &[Argument]| -> Result<Vec<Argument>, Error> {
        let Some(args) = &harness.before_args else { return Ok(arguments.to_vec()) };
        let (locals, arrays) = locals_of(params, arguments);
        let types = previous.as_ref().map(harness::BeforeMethod::argument_types).unwrap_or_default();
        let mut flat = Vec::new();
        for (arg, t) in args.iter().zip(&types) {
            match arg {
                CallArg::Value(e) => flat.push(Argument::Scalar(as_parameter(harness::expr::eval_with(e, &locals, &arrays)?, t))),
                CallArg::Array(_, slot) => flat.push(params.iter().zip(arguments).find(|(p, _)| p.slot == *slot).map(|(_, a)| a.clone()).unwrap_or(Argument::Null)),
                CallArg::Record(record, components) => {
                    for (e, (_, t)) in components.iter().zip(&record.components) {
                        flat.push(Argument::Scalar(as_parameter(harness::expr::eval_with(e, &locals, &arrays)?, t)));
                    }
                }
            }
        }
        Ok(flat)
    };
    // Both versions replayed on an input: what each did, and whether the two agree, which under a relation between
    // the results is the relation holding when both return (with the arrays left the same), and otherwise the two
    // outcomes reading the same; a replay that failed never agrees.
    // The identity relations the harness compares, which the replays state where they hold.
    let identity_pairs = layout.identity_pairs(&descriptor.ret, &before_descriptor.ret, options.before_arguments.is_none());
    // Those compared as "holds before iff it holds now": the rest are under an output relation (H5's rest), which
    // is evaluated over the two replays below.
    let iff_pairs: Vec<(String, String)> = identity_pairs.iter().filter(|(x, y)| layout.identity_relation(x, y).is_none()).cloned().collect();
    // A relation that reads the results' objects is evaluated by the harness itself, run in the interpreter.
    let relation_cp = match &harness.relation {
        Some(r) if r.expr.reads_objects() => Some(witness::classpath([harness_dir.as_path(), options.after.as_path(), before_dir.as_path()].into_iter().chain(options.classpath.iter().map(PathBuf::as_path)))?.with_models(options.models)),
        _ => None,
    };
    let replay_on = |replay_cp: &ClassPath, arguments: &[Argument]| -> Replays {
        let after = witness::replay_in(replay_cp, &layout, None, &class_internal, &method_name, &method.descriptor, &descriptor, arguments);
        let after_text = format!("{}{}", after.with_leftovers(params, arguments), after.identities(&identity_pairs));
        let after_compared = after.compared(params, arguments, &iff_pairs);
        let mut before_compared = String::new();
        let (before, before_text) = match map_arguments(arguments) {
            Ok(mapped) => {
                // With the previous version's arguments as expressions, each is a primitive or an array; otherwise
                // the previous version's records are built from the same components.
                let replayed = if harness.before_args.is_some() {
                    witness::replay_in(replay_cp, &before_layout, Some("before"), &before_owner, &before_method_name, &before_relocated, &before_descriptor, &mapped)
                } else {
                    witness::replay_in(replay_cp, &layout, Some("before"), &before_owner, &before_method_name, &before_relocated, &before_descriptor, &mapped)
                };
                let text = if harness.before_args.is_some() { replayed.with_leftovers(before_params, &mapped) } else { replayed.with_leftovers(params, &mapped) };
                let text = format!("{text}{}", replayed.identities(&identity_pairs));
                before_compared = if harness.before_args.is_some() { text.clone() } else { replayed.compared(params, &mapped, &iff_pairs) };
                (Some(replayed), text)
            }
            Err(e) => (None, format!("<could not replay: the previous version's arguments could not be computed: {e}>")),
        };
        // Under a correspondence the two are compared through its equations; otherwise as they read.
        let same = if harness.before_args.is_some() { before_text == after_text } else { before_compared == after_compared } && !before_text.starts_with("<could not replay");
        // Which observations the two differ in, by id, for the accounting of a refutation.
        let mut differs = match &before {
            Some(b) if harness.before_args.is_none() => witness::differences(b, &after, params, arguments, &iff_pairs),
            _ => Vec::new(),
        };
        // The correspondence's output relations for an object parameter's fields (H5's rest), each evaluated over
        // the two versions' objects as the calls left them; one that fails is a difference in its observation.
        let mut field_notes: Vec<String> = Vec::new();
        if let Some(b) = &before {
            for slot in &layout.args {
                let harness::Slot::Record { name, before: Some(previous), .. } = slot else { continue };
                let Some(c) = &previous.corresponds else { continue };
                let paths = |x: &witness::Replayed| x.object_paths.iter().find(|(n, _)| n == name).map(|(_, p)| p.clone());
                let (Some(old), Some(new)) = (paths(b), paths(&after)) else { continue };
                for r in &c.relations {
                    let values: Option<Vec<Value>> = r.reads.iter().map(|x| if x.previous { old.get(&x.path) } else { new.get(&x.path) }.copied()).collect();
                    let shown = r.observation(name).trim_start_matches("field:").to_string();
                    let note = match values.map(|v| r.eval(&v)) {
                        Some(Ok(true)) => continue,
                        Some(Ok(false)) => format!("{shown} as the calls leave it is not related by {}", r.holds.trim()),
                        None => format!("{shown} as the calls leave it is not related by {}: a path it reads goes through null", r.holds.trim()),
                        Some(Err(e)) => format!("the relation {} cannot be evaluated on {shown} as the calls leave it: {e}", r.holds.trim()),
                    };
                    field_notes.push(note);
                    differs.push(r.observation(name));
                }
            }
            // The output relations for identity relations, over whether each holds in either replay.
            for r in &layout.identity_relations {
                let (x, y) = (&r.pair.0, &r.pair.1);
                let (old, new) = (b.identity_holds(x, y), after.identity_holds(x, y));
                let shown = |holds: bool| if holds { "holds" } else { "does not hold" };
                let note = match r.eval(old, new) {
                    Ok(true) => continue,
                    Ok(false) => format!("{x} == {y} is not related by {}: it {} before and {} now", r.holds.trim(), shown(old), shown(new)),
                    Err(e) => format!("the relation {} cannot be evaluated on {x} == {y}: {e}", r.holds.trim()),
                };
                field_notes.push(note);
                differs.push(r.observation());
            }
        }
        let finish = |mut r: Replays| -> Replays {
            if !field_notes.is_empty() {
                r.agree = false;
                r.relation_note = Some(r.relation_note.into_iter().chain(field_notes.iter().cloned()).collect::<Vec<_>>().join("; "));
            }
            r
        };
        // A side that returned: a primitive or array value, or a record (null or not).
        let returned = |x: &witness::Replayed, record: bool| if record { x.thrown.is_none() && !x.outcome.starts_with('<') && x.outcome != "void" } else { x.returned.is_some() };
        let (agree, relation_note) = match (&harness.relation, &before) {
            (Some(r), Some(b)) if returned(b, r.previous_read()) && returned(&after, r.result_read()) => {
                let text = relation_shown.as_deref().unwrap_or_default();
                let leftovers = |t: &str| t.find(", leaving").map(|i| t[i..].to_string()).unwrap_or_default();
                // A null record: two agree, one beside a record or a value does not, as the harness has it.
                let null_before = r.previous_read() && b.result_fields.is_none();
                let null_after = r.result_read() && after.result_fields.is_none();
                if null_before || null_after {
                    let (agree, note) = match (null_before, null_after) {
                        (true, true) => (leftovers(&before_text) == leftovers(&after_text), None),
                        (true, false) => (false, Some("the previous version's result is null and the new one's is not".to_string())),
                        _ => (false, Some("the new version's result is null and the previous one's is not".to_string())),
                    };
                    if !agree && !differs.iter().any(|d| d == "result") {
                        differs.push("result".into());
                    }
                    return finish(Replays { before: before_text, after: after_text, agree, relation_note: note, differs });
                }
                if let Some(cp) = &relation_cp {
                    // Over objects, the relation reads each result's field paths as the replay left them; whether
                    // the two agree on everything else too is the harness's to say, run on the input.
                    let (locals, arrays) = locals_of(params, arguments);
                    // And the previous version's objects it reads (H5's rest), as its replay left them.
                    let read = |f: &harness::expr::FieldPath| {
                        let object = |name: &str| b.object_paths.iter().find(|(n, _)| n == name).map(|(_, p)| p);
                        let paths = if f.slot == r.previous {
                            &b.result_paths
                        } else if f.slot == r.result {
                            &after.result_paths
                        } else {
                            r.previous_objects.iter().find(|(_, slot)| *slot == f.slot).and_then(|(name, _)| object(name))?
                        };
                        f.shown.split_once('.').and_then(|(_, p)| paths.get(p).copied())
                    };
                    let note = match harness::expr::eval_reading(&r.expr, &locals, &arrays, &read) {
                        Ok(Value::Int(1)) => None,
                        Ok(_) => Some(format!("the results are not related by {text}")),
                        Err(e) => Some(format!("the relation {text} cannot be evaluated on these results: {e}")),
                    };
                    let holds = witness::fails_in_harness(cp, harness::CLASS, &flat_types, arguments) == Some(false);
                    // The results of two shapes read differently as text: they differ only where the relation fails.
                    differs.retain(|d| d != "result");
                    if note.is_some() {
                        differs.push("result".into());
                    }
                    return finish(Replays { before: before_text, after: after_text, agree: holds && note.is_none(), relation_note: note, differs });
                }
                let (mut locals, mut arrays) = locals_of(params, arguments);
                locals.resize(usize::from(r.previous.max(r.result).max(r.slots_end)) + 2, Value::Int(0));
                locals[usize::from(r.previous)] = b.returned.unwrap_or(Value::Null);
                locals[usize::from(r.result)] = after.returned.unwrap_or(Value::Null);
                for (components, fields) in [(&r.previous_components, &b.result_fields), (&r.result_components, &after.result_fields)] {
                    if let (Some((record, slots)), Some(fields)) = (components, fields) {
                        for ((name, _), slot) in record.components.iter().zip(slots) {
                            locals[usize::from(*slot)] = fields.get(name).copied().unwrap_or(Value::Int(0));
                        }
                    }
                }
                if let Some(data) = &b.result_array {
                    arrays.push((r.previous, data.clone()));
                }
                if let Some(data) = &after.result_array {
                    arrays.push((r.result, data.clone()));
                }
                match harness::expr::eval_with(&r.expr, &locals, &arrays) {
                    Ok(Value::Int(1)) => (leftovers(&before_text) == leftovers(&after_text), None),
                    Ok(_) => (false, Some(format!("the results are not related by {text}"))),
                    Err(e) => (false, Some(format!("the relation {text} cannot be evaluated on these results: {e}"))),
                }
            }
            _ => (same, None),
        };
        if relation_note.is_some() && !differs.iter().any(|d| d == "result") {
            differs.push("result".into());
        }
        finish(Replays { before: before_text, after: after_text, agree, relation_note, differs })
    };
    let replay_both = |arguments: &[Argument]| replay_on(&replay_cp, arguments);
    // With the shared callees first: a proof with them is a proof, and a counterexample with them is one when it
    // reproduces through the bytecode as written. Otherwise the abstraction was too coarse: the callees whose stubs
    // the counterexample rests on are computed as written, and the rest stay one function, until a run's verdict
    // stands or none is left ([`shared::spurious`]).
    let mut shared_used = if last.as_ref().is_some_and(|l: &JbmcResult| l.native.is_some()) { native_shared } else { Vec::new() };
    let mut jbmc_notes = String::new();
    if last.is_none() {
        if let Some(first) = &shared_classpath {
            let marker = format!("{}.{}", harness::CLASS, harness::METHOD);
            let mut stubbed: Vec<usize> = (0..plan.callees.len()).collect();
            let mut cp = first.clone();
            let mut round = 0;
            while let Some(result) = run_stages(&cp, &if round == 0 { "-shared".to_string() } else { format!("-shared-{round}") }, "shared", &mut runs, &mut jbmc_notes)? {
                let names: Vec<String> = stubbed.iter().map(|&i| shared_names[i].clone()).collect();
                let found = if result.verdict == Verdict::Violation { Some(result.arguments(&flat_types)?) } else { None };
                let Some(found) = found.filter(|a| replay_both(a).agree) else {
                    shared_used = names;
                    last = Some(result);
                    break;
                };
                let subset: Vec<shared::Callee> = stubbed.iter().map(|&i| plan.callees[i].clone()).collect();
                let answers = std::fs::read_to_string(&result.log).ok().and_then(|o| shared::answers(&o, &subset, &marker));
                let redirected = cp[1].clone();
                let blamed = match answers {
                    Some(answers) => shared::spurious(&shared_after_cp, &subset, &answers, &work.join(format!("shared-replay-{round}")), &mut |entry| {
                        let entries = [entry, redirected.as_path(), options.after.as_path(), before_dir.as_path()];
                        witness::classpath(entries.into_iter().chain(options.classpath.iter().map(PathBuf::as_path))).map(|c| !replay_on(&c.with_models(options.models), &found).agree).unwrap_or(true)
                    })?,
                    None => None,
                };
                let kept: Vec<usize> = match &blamed {
                    Some(b) if b.len() < subset.len() => (0..subset.len()).filter(|k| !b.contains(k)).map(|k| stubbed[k]).collect(),
                    _ => Vec::new(),
                };
                if kept.is_empty() {
                    let _ = writeln!(out, "note: the counterexample found with {} taken as one function in both versions does not reproduce once computed as written; proving with the callees' bytecode", names.join(", "));
                    break;
                }
                let blamed: Vec<String> = blamed.unwrap_or_default().iter().map(|&k| names[k].clone()).collect();
                let left: Vec<String> = kept.iter().map(|&i| shared_names[i].clone()).collect();
                let (rests, them) = if blamed.len() == 1 { ("stub", "it") } else { ("stubs", "them") };
                let _ = writeln!(out, "note: the counterexample found with {} taken as one function in both versions does not reproduce once computed as written; it rests on the answers of {}'s {rests} (with {them} as written, the two versions agree on its input), so the proof runs again with {} as written and {} still one function in both", names.join(", "), blamed.join(", "), blamed.join(", "), left.join(", "));
                stubbed = kept;
                round += 1;
                let dir = work.join(format!("shared-classes-{round}"));
                let subset: Vec<shared::Callee> = stubbed.iter().map(|&i| plan.callees[i].clone()).collect();
                shared::stub_directory(&shared_after_cp, &subset, &shared_versions, &dir)?;
                cp = classpath.clone();
                cp.insert(1, dir);
            }
        }
        if last.is_none() {
            let purpose = if runs.iter().any(|r| r.purpose == "shared") { "as-written" } else if fallback.is_some() { "fallback" } else { "proof" };
            last = run_stages(&classpath, "", purpose, &mut runs, &mut jbmc_notes)?;
        }
    }
    out.push_str(&jbmc_notes);
    let last = last.expect("at least one stage");
    let seconds = started.elapsed().as_secs_f64();
    // Under `--confirm`, the own checker's proof is JBMC's to prove again, over every input in one run, on the
    // class path the own checker proved it on (the callees as written). It is a second check, by a second checker,
    // with a deadline of its own.
    let (confirmation, refuting) = if options.confirm && options.engine == crate::Engine::Auto && last.native.is_some() && last.verdict == Verdict::Verified {
        let run = JbmcRun { timeout: Duration::from_secs(options.timeout_seconds), log: work.join("jbmc-confirm.log"), ..base(&classpath, "") };
        let rewrite: Vec<PathBuf> = classpath.iter().filter(|p| **p != jdk_dir && **p != models_dir).cloned().collect();
        let contracts = ConfirmContracts { setting: &gap_setting, rewrite, cp: &contract_cp, dir: work.join("jbmc-confirm-contracts") };
        let harness_cp = witness::classpath([harness_dir.as_path(), options.after.as_path(), before_dir.as_path()].into_iter().chain(options.classpath.iter().map(PathBuf::as_path)))?.with_models(options.models);
        let reproduces = |r: &JbmcResult| -> Result<Option<bool>, Error> { Ok(witness::fails_in_harness(&harness_cp, harness::CLASS, &flat_types, &r.arguments(&flat_types)?)) };
        let (c, refuting) = confirm(&last, &run, Some(contracts), &reproduces)?;
        (Some(c), refuting)
    } else {
        (None, None)
    };
    let mut search = Some(Search {
        engine: if last.native.is_some() { "native" } else { "jbmc" }.into(),
        checker: last.version.clone(),
        seconds,
        properties: last.properties,
        unwind: options.unwind,
        max_array_length: options.max_array_length,
        stage: last.stage.clone(),
        staging: last.native.is_none().then_some(options.jbmc_staging),
        fallback,
        native: last.native.clone(),
        gap_mode: last.gap_mode,
        gaps: last.gaps.clone(),
        confirmation,
        deadline_seconds: deadline.total().as_secs_f64(),
        runs,
        phases: None,
    });
    let mut replay = None;
    let sharing = shared::sharing(&plan.callees, &shared_used);

    let mut findings = Vec::new();
    let mut counterexample = None;
    let mut proof = None;
    let mut problem = None;
    let mut vacuous = None;
    let mut vacuity_status = None;
    let mut verdict = last.verdict;
    // JBMC refutes what the own checker proved: neither verdict stands. JBMC's witness is the counterexample, with
    // both versions run on it in the interpreter, which shares the own checker's models and so settles nothing.
    if let Some(refuting) = &refuting {
        let found = refuting.arguments(&flat_types)?;
        let replays = replay_both(&found);
        let harness_cp = witness::classpath([harness_dir.as_path(), options.after.as_path(), before_dir.as_path()].into_iter().chain(options.classpath.iter().map(PathBuf::as_path)))?.with_models(options.models);
        let reproduced = witness::fails_in_harness(&harness_cp, harness::CLASS, &flat_types, &found);
        let (mut rendered, values) = witness::call_in(&method_name, &layout, &found);
        if harness.before_args.is_some() {
            if let Ok(mapped) = map_arguments(&found) {
                rendered = format!("{rendered}, previously {}", witness::call_in(&before_method_name, &before_layout, &mapped).0);
            }
        }
        let (assuming, _) = assumed_gaps(&last);
        let p = format!(
            "the engines disagree: the tool's own checker proves {relation}{restriction}{assuming} ({}, {seconds:.1} s), and {} refutes it on\n  {rendered}\n    before in the interpreter: {}\n    after in the interpreter:  {}, {}",
            last.version,
            refuting.version,
            replays.before,
            replays.after,
            crate::property::reproduced_words(reproduced)
        );
        let message = format!("{} cannot be verified: {p}", options.target);
        let _ = writeln!(out, "✗ {message}");
        let _ = writeln!(out, "\nNeither verdict stands. Run both versions on the input above on a JVM: if they differ there, the tool's own checker is wrong, and otherwise JBMC is.");
        findings.push(Finding::new("engines-disagree", message, uri.clone(), line));
        if let Some(report) = &options.report {
            sarif::write(&report.join("equivalence.sarif"), &findings)?;
        }
        let after_target = witness::Target { class_internal: &class_internal, method: &method_name, descriptor: &method.descriptor, is_static: method.is_static(), classes: "after" };
        let before_target = witness::Target { class_internal: &before_class_internal, method: &before_method_name, descriptor: &before_method.descriptor, is_static: before_method.is_static(), classes: "before" };
        let call = witness::typed_call(&after_target, &layout, &found, false, &[]);
        let previous_call = if harness.before_args.is_some() {
            let sources = previous.as_ref().map(harness::BeforeMethod::argument_sources).unwrap_or_default();
            map_arguments(&found).ok().map(|mapped| witness::typed_call(&before_target, &before_layout, &mapped, true, &sources))
        } else {
            Some(witness::typed_call(&before_target, &layout, &found, true, &[]))
        };
        let inputs = witness::typed_inputs(params, &found);
        let counterexample = Some(Counterexample { input: rendered, before: replays.before, after: replays.after, values, found: None, shrink_runs: 0, inputs, found_inputs: None, call, previous_call, differs: replays.differs, jvm: None });
        let replay = Some(Replay { by: "interpreter".into(), reproduced: reproduced == Some(true) });
        let stated = Some(stated(Some(&last), search.as_ref(), false));
        return Ok(Outcome { verdict: Verdict::Unverifiable, target: options.target.clone(), domain: Some(domain), counterexample, proof: None, problem: Some(p), statement: Some(statement), findings, output: out, work, shared: Vec::new(), previous: previous_display.clone(), relation: relation_shown.clone(), vacuous: None, search, replay, stated, advice: None, reuse: None });
    }
    match last.verdict {
        Verdict::Verified => {
            let how = format!("{}: {} properties proved over {domain} in {seconds:.1} s; loops unwound {} times with unwinding assertions{sharing}", last.version, last.properties, options.unwind);
            let (assuming, assumed) = assumed_gaps(&last);
            let (relying, relied) = relied_contracts(&last);
            let _ = writeln!(out, "✓ {} {relation}{restriction}{assuming}{relying} ({how})", options.target);
            out.push_str(&assumed);
            out.push_str(&relied);
            if let Some(c) = search.as_ref().and_then(|s| s.confirmation.as_ref()) {
                out.push_str(&confirmation_line(c));
            }
            proof = Some(how);
            // A statement that skips inputs before the calls may skip every one in the domain: a scope every input
            // satisfies, a bound on the arrays below what the scope asks, a constructor that rejects every input.
            if harness::skips_inputs(&layout, options.unchanged_unless.as_deref(), previous.as_ref()) {
                let mut ways = Vec::new();
                if options.unchanged_unless.is_some() {
                    ways.push("being among the intended inputs (--unchanged-unless)");
                }
                if !layout.records().is_empty() {
                    ways.push("rejected by a record's constructor");
                }
                if layout.records().iter().any(|s| matches!(s, harness::Slot::Record { before: Some(b), .. } if b.corresponds.as_ref().is_some_and(|c| !c.same_shape))) {
                    ways.push("outside the correspondence's input equations");
                }
                if previous.as_ref().is_some_and(|b| b.arguments.is_some()) {
                    ways.push("without arguments for the previous version (--before-arguments throws on it)");
                }
                let mut entries = vec![options.after.clone(), before_dir.clone()];
                entries.extend(options.classpath.iter().cloned());
                let render = |r: &JbmcResult| r.arguments(&flat_types).ok().map(|found| witness::call_in(&method_name, &layout, &found).0);
                let (reason, status) = vacuity(&mut out, &harness.probe, harness::CLASS, &entries, options.models, options.unwind, options.max_array_length, deadline.left(), &gap_setting, &crate::bmc::Parameters::default(), &work, &ways.join(" or "), &render, &mut search)?;
                vacuous = reason;
                vacuity_status = Some(status);
            } else {
                vacuity_status = Some(Vacuity::every_input());
            }
            // A record built through its constructor: the statement is about the records it accepts, and whether
            // the two versions' constructors accept the same inputs is another statement.
            for a in &claim_assumptions {
                if a.kind == crate::statement::AssumptionKind::Constructible {
                    let _ = writeln!(out, "  constructors: {}", a.text);
                }
            }
        }
        Verdict::Violation => {
            let found = last.arguments(&flat_types)?;
            let mut replays = replay_both(&found);
            replay = Some(Replay { by: "interpreter".into(), reproduced: !replays.agree });
            let unreplayed = [&replays.before, &replays.after].into_iter().find(|t| t.starts_with("<could not replay"));
            let mut unconfirmed = unreplayed.and_then(|t| unconfirmed_through_contracts(&last, &witness::call_in(&method_name, &layout, &found).0, t));
            // A witness through a contract that the interpreter cannot run is run on a JVM: the harness on it, with
            // the JDK's real calls where the contracts stood, then each version alone when both are static
            // methods of the harness's parameters, for what each did.
            let mut on_jvm: Option<String> = None;
            let mut on_jvm_too: Option<String> = None;
            let mut jvm_ran = false;
            if let Some(p) = &unconfirmed {
                let mut entries = vec![harness_dir.clone(), options.after.clone(), before_dir.clone()];
                entries.extend(options.classpath.iter().cloned());
                let alone = layout.receiver.is_none() && layout.args.iter().all(|s| matches!(s, harness::Slot::Plain(_))) && harness.before_args.is_none() && method.is_static() && before_method.is_static();
                let calls = if alone {
                    vec![
                        crate::jvm_witness::DirectCall { owner: before_owner.clone(), name: before_method_name.clone(), descriptor: before_relocated.clone(), ret: before_descriptor.ret.clone() },
                        crate::jvm_witness::DirectCall { owner: class_internal.clone(), name: method_name.clone(), descriptor: method.descriptor.clone(), ret: descriptor.ret.clone() },
                    ]
                } else {
                    Vec::new()
                };
                let slots: Vec<u16> = layout.params.iter().map(|p| p.slot).collect();
                let rendered = witness::call_in(&method_name, &layout, &found).0;
                match crate::jvm_witness::run(&work.join("jvm-witness"), harness::CLASS, &flat_types, &slots, &found, &calls, &entries) {
                    Ok(run) if run.check == crate::jvm_witness::Check::Refuted => {
                        let alone_words = "<not run alone on the JVM, which the harness's assertion fails on>".to_string();
                        let (before, after) = match run.calls.as_slice() {
                            [b, a] => (b.with_leftovers(params, &found), a.with_leftovers(params, &found)),
                            _ => (if replays.before.starts_with("<could not replay") { alone_words.clone() } else { replays.before.clone() }, if replays.after.starts_with("<could not replay") { alone_words } else { replays.after.clone() }),
                        };
                        replays = Replays { before, after, agree: false, relation_note: None, differs: replays.differs.clone() };
                        on_jvm = Some(run.jdk);
                        unconfirmed = None;
                    }
                    Ok(run) if run.check == crate::jvm_witness::Check::Holds => {
                        jvm_ran = true;
                        let what = match run.calls.as_slice() {
                            [b, a] => format!("the previous version gives {} and the new one {} there, which the harness holds to agree", b.with_leftovers(params, &found), a.with_leftovers(params, &found)),
                            _ => "the harness finds the two versions agreeing there".to_string(),
                        };
                        unconfirmed = Some(not_reproduced_on_jvm(&last, &rendered, &run.jdk, &what, true));
                    }
                    Ok(run) => {
                        jvm_ran = true;
                        unconfirmed = Some(format!("{p}; run on a JVM, the harness threw {}", match run.check { crate::jvm_witness::Check::Threw(c) => c, _ => unreachable!() }));
                    }
                    Err(e) => unconfirmed = Some(format!("{p}; it could not be run on a JVM either: {e}")),
                }
            }
            if let Some(p) = unconfirmed {
                let message = format!("{} cannot be verified: {p}", options.target);
                let _ = writeln!(out, "✗ {message}");
                findings.push(Finding::new("unverifiable", message, uri.clone(), line));
                problem = Some(p);
                verdict = Verdict::Unverifiable;
                replay = Some(Replay { by: if jvm_ran { "jvm" } else { "interpreter" }.into(), reproduced: false });
                if let Some(report) = &options.report {
                    sarif::write(&report.join("equivalence.sarif"), &findings)?;
                }
                let stated = Some(stated(Some(&last), search.as_ref(), false));
                return Ok(Outcome { verdict, target: options.target.clone(), domain: Some(domain), counterexample, proof, problem, statement: Some(statement), findings, output: out, work, shared: shared_used, previous: previous_display.clone(), relation: relation_shown.clone(), vacuous: None, search, replay, stated, advice: None, reuse: None });
            }
            // A counterexample the interpreter cannot reproduce is no counterexample: JBMC has given an arbitrary
            // result to a method it had no bytecode for (one outside its models and the class path it was given).
            if replays.agree {
                let (rendered, _) = witness::call_in(&method_name, &layout, &found);
                let both = if replays.before == replays.after { format!("both versions give {}", replays.before) } else { format!("the versions give {} and {}, which the relation relates,", replays.before, replays.after) };
                let p = format!("{}'s counterexample {rendered} does not reproduce: {both} in the interpreter. {}", if last.native.is_some() { "The tool's own checker" } else { "JBMC" }, unreproduced_cause(&last));
                let message = format!("{} cannot be verified: {p}", options.target);
                let _ = writeln!(out, "✗ {message}");
                findings.push(Finding::new("unverifiable", message, uri.clone(), line));
                problem = Some(p);
                verdict = Verdict::Unverifiable;
                if let Some(report) = &options.report {
                    sarif::write(&report.join("equivalence.sarif"), &findings)?;
                }
                let stated = Some(stated(Some(&last), search.as_ref(), false));
                return Ok(Outcome { verdict, target: options.target.clone(), domain: Some(domain), counterexample, proof, problem, statement: Some(statement), findings, output: out, work, shared: shared_used, previous: previous_display.clone(), relation: relation_shown.clone(), vacuous: None, search, replay, stated, advice: None, reuse: None });
            }
            // Shrink the witness: the harness class JBMC checked, run in the interpreter on smaller inputs.
            let mut shrink_runs = 0;
            let mut arguments = found.clone();
            // The interpreter is the shrinker's oracle, and it cannot run a witness only a JVM could.
            if options.shrink && on_jvm.is_none() {
                let harness_cp = witness::classpath([harness_dir.as_path(), options.after.as_path(), before_dir.as_path()].into_iter().chain(options.classpath.iter().map(PathBuf::as_path)))?;
                let shrunk = witness::shrink_in_harness_keeping(&harness_cp, harness::CLASS, &flat_types, found.clone(), &layout.flags());
                shrink_runs = shrunk.runs;
                arguments = shrunk.arguments;
            }
            let shrunk = arguments != found;
            let replays = if shrunk { replay_both(&arguments) } else { replays };
            let Replays { before: before_outcome, after: after_outcome, relation_note, differs, .. } = replays;
            let (mut rendered, witnesses) = witness::call_in(&method_name, &layout, &arguments);
            let (rendered_found, _) = witness::call_in(&method_name, &layout, &found);
            // A witness over objects, or one the versions differ on in a field or an identity relation, is run on a
            // JVM as well as in the interpreter (step H4 of `llm-dlc/loops/foundations-heap.md`): the harness on the
            // input, which makes its objects from the same leaves, with the same identities, as in the interpreter,
            // loading the application's classes opened so that it may read their fields. The JVM is the reference:
            // where its harness finds the versions agreeing, the interpreter was wrong and nothing is reported.
            let mut jvm_note = None;
            if on_jvm.is_none() && observes_objects(&layout, &differs) {
                let mut entries = vec![harness_dir.clone(), options.after.clone(), before_dir.clone()];
                entries.extend(options.classpath.iter().cloned());
                let slots: Vec<u16> = layout.params.iter().map(|p| p.slot).collect();
                match crate::jvm_witness::run(&work.join("jvm-witness"), harness::CLASS, &flat_types, &slots, &arguments, &[], &entries) {
                    Ok(run) if run.check == crate::jvm_witness::Check::Refuted => {
                        jvm_note = Some(format!("and run on a JVM (JDK {}), where the harness fails on it too", run.jdk));
                        on_jvm_too = Some(run.jdk);
                    }
                    Ok(run) if run.check == crate::jvm_witness::Check::Holds => {
                        let p = format!("the counterexample {rendered} replays in the interpreter as before: {before_outcome}; after: {after_outcome}, but on a JVM (JDK {}) the harness finds the two versions agreeing on it. The JVM is the reference, so the tool's interpreter is wrong here and the witness is not reported", run.jdk);
                        let message = format!("{} cannot be verified: {p}", options.target);
                        let _ = writeln!(out, "✗ {message}");
                        findings.push(Finding::new("unverifiable", message, uri.clone(), line));
                        problem = Some(p);
                        verdict = Verdict::Unverifiable;
                        replay = Some(Replay { by: "jvm".into(), reproduced: false });
                        if let Some(report) = &options.report {
                            sarif::write(&report.join("equivalence.sarif"), &findings)?;
                        }
                        let stated = Some(stated(Some(&last), search.as_ref(), false));
                        return Ok(Outcome { verdict, target: options.target.clone(), domain: Some(domain), counterexample, proof, problem, statement: Some(statement), findings, output: out, work, shared: shared_used, previous: previous_display.clone(), relation: relation_shown.clone(), vacuous: None, search, replay, stated, advice: None, reuse: None });
                    }
                    Ok(run) => jvm_note = Some(format!("not confirmed on a JVM, where the harness threw {}", match run.check { crate::jvm_witness::Check::Threw(c) => c, _ => unreachable!() })),
                    Err(e) => jvm_note = Some(format!("not run on a JVM: {e}")),
                }
            }
            if harness.before_args.is_some() {
                if let Ok(mapped) = map_arguments(&arguments) {
                    rendered = format!("{rendered}, previously {}", witness::call_in(&before_method_name, &before_layout, &mapped).0);
                }
            }
            let message = format!(
                "{}{}:\n  {rendered}\n    before: {before_outcome}\n    after:  {after_outcome}{}",
                match &previous_display {
                    Some(p) => format!("{} differs from the previous {p}", options.target),
                    None => format!("Behaviour of {} changed", options.target),
                },
                options.unchanged_unless.as_deref().map(|s| format!(" outside the intended inputs ({s})")).unwrap_or_default(),
                relation_note.map(|n| format!("\n    {n}")).unwrap_or_default()
            );
            let _ = writeln!(out, "✗ {message}");
            let stage = last.stage.as_deref().map(|s| format!(" searching inputs in {s}")).unwrap_or_default();
            let shrinking = if shrunk { format!(" as {rendered_found}, shrunk to the input above in {shrink_runs} interpreter runs") } else { String::new() };
            let replayed_by = match (&on_jvm, &jvm_note) {
                (Some(jdk), _) => run_on_jvm_words(jdk),
                (None, Some(note)) => format!("replayed in the interpreter {note}"),
                (None, None) => "replayed in the interpreter".into(),
            };
            let how = format!("found by {} in {seconds:.1} s{stage}{shrinking}, {replayed_by}; domain {domain}{sharing}", last.version);
            if on_jvm.is_some() {
                replay = Some(Replay { by: "jvm".into(), reproduced: true });
            }
            let _ = writeln!(out, "  ({how})");
            if let Some(scope) = &harness.scope {
                let (locals, arrays) = locals_of(params, &arguments);
                if let Ok(Value::Int(1)) = harness::expr::eval_with(scope, &locals, &arrays) {
                    let _ = writeln!(out, "  (note: the interpreter evaluates the scope expression as true on this input, which the harness should have skipped; check the expression)");
                }
            }
            findings.push(Finding::new("behaviour-changed", message, uri.clone(), line));
            proof = Some(how);
            let after_target = witness::Target { class_internal: &class_internal, method: &method_name, descriptor: &method.descriptor, is_static: method.is_static(), classes: "after" };
            let before_target = witness::Target { class_internal: &before_class_internal, method: &before_method_name, descriptor: &before_method.descriptor, is_static: before_method.is_static(), classes: "before" };
            let call = witness::typed_call(&after_target, &layout, &arguments, false, &[]);
            let previous_call = if harness.before_args.is_some() {
                let sources = previous.as_ref().map(harness::BeforeMethod::argument_sources).unwrap_or_default();
                map_arguments(&arguments).ok().map(|mapped| witness::typed_call(&before_target, &before_layout, &mapped, true, &sources))
            } else {
                Some(witness::typed_call(&before_target, &layout, &arguments, true, &[]))
            };
            let inputs = witness::typed_inputs(params, &arguments);
            let found_inputs = shrunk.then(|| witness::typed_inputs(params, &found));
            counterexample = Some(Counterexample { input: rendered, before: before_outcome, after: after_outcome, values: witnesses, found: shrunk.then_some(rendered_found), shrink_runs, inputs, found_inputs, call, previous_call, differs, jvm: on_jvm.clone().or(on_jvm_too) });
        }
        Verdict::Unverifiable => {
            let p = last.problem.clone().unwrap_or_else(|| "no verdict".into());
            let message = format!("{} cannot be verified: {p}", options.target);
            let _ = writeln!(out, "✗ {message}");
            findings.push(Finding::new("unverifiable", message, uri.clone(), line));
            problem = Some(p);
        }
    }
    if let Some(report) = &options.report {
        sarif::write(&report.join("equivalence.sarif"), &findings)?;
    }
    if verdict == Verdict::Violation {
        let _ = writeln!(out, "\nIf the change is intended, say for which inputs with --unchanged-unless, and the verifier proves that nothing else changed. The expression is what a reviewer approves.");
    }
    let mut stated = stated(Some(&last), search.as_ref(), verdict == Verdict::Verified);
    crate::proof_cache::keep_used(&mut stated, &plan.callees, &shared_used);
    stated.vacuity = vacuity_status.filter(|_| verdict == Verdict::Verified);
    let stated = Some(stated);
    let mut outcome = Outcome { verdict, target: options.target.clone(), domain: Some(domain), counterexample, proof, problem, statement: Some(statement), findings, output: out, work, shared: shared_used, previous: previous_display, relation: relation_shown.clone(), vacuous, search, replay, stated, advice: None, reuse: None };
    cache.store(&mut outcome);
    Ok(outcome)
}

/// Both versions replayed on one input.
struct Replays {
    before: String,
    after: String,
    /// Whether the two outcomes agree: under a relation between the results, whether it holds.
    agree: bool,
    /// Why they do not, when a relation was given and both versions returned.
    relation_note: Option<String>,
    /// The observations the two differ in, by id ([`crate::spec::Observation::id`]); empty where the previous
    /// version's arguments are expressions, whose replays are not compared observation by observation.
    differs: Vec<String>,
}

/// Copies the JDK classes in [`JDK_CLASSES`] out of the JDK image, for JBMC's class path.
pub fn extract_jdk_classes(dir: &Path, java_home: Option<&Path>) -> Result<(), Error> {
    crate::phases::timed(crate::phases::Step::Setup, || extract_jdk_classes_untimed(dir, java_home))
}

fn extract_jdk_classes_untimed(dir: &Path, java_home: Option<&Path>) -> Result<(), Error> {
    let home = match java_home {
        Some(h) => h.to_path_buf(),
        None => crate::jimage::JImage::find_java_home().ok_or_else(|| Error::new("no JDK found (set JAVA_HOME)"))?,
    };
    let image = crate::jimage::JImage::open(&home)?;
    for name in JDK_CLASSES {
        let bytes = image.read_class(name)?.ok_or_else(|| Error::new(format!("{name} is not in the JDK image")))?;
        let target = dir.join(format!("{name}.class"));
        if let Some(parent) = target.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(target, bytes)?;
    }
    Ok(())
}
