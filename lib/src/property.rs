//! Property proofs: a statement about one method on every input, proved by bounded model checking or refuted with
//! a concrete input. Where a regression proof ([`crate::equivalence`]) compares two versions, a property proof
//! checks one version against what the developer says it guarantees: a postcondition such as
//! `result >= baseMillis && result <= capMillis`, or a law such as `result == merge(b, a)`.
//!
//! The statement is "for all inputs where `assume` holds, the method returns without throwing and `assert` holds".
//! It is the theorem a property-based test states and samples; here the solver covers every input. The harness is
//! generated as bytecode ([`crate::harness::generate_property`]), JBMC turns it into a satisfiability problem, and a
//! satisfying assignment is replayed in the interpreter to show the outcome that violates the property.
//!
//! An array parameter is a symbolic array of every length up to a bound ([`Options::max_array_length`]), never
//! `null`, and the property may quantify over it (`\forall int i; 0 <= i && i < a.length; a[i] != key`); so may
//! an array `result`.
//!
//! A parameter of an application class is an object made by its constructor from symbolic leaves (step H2 of
//! `llm-dlc/loops/foundations-heap.md`), null or the same object as another where `--nullable` and `--may-alias`
//! say so; the property reads its field paths (`l.price.cents`, `\old(l.quantity)`) and compares references by
//! identity (`result == l`). A witness over objects is checked by running the harness itself, in the interpreter
//! and on a JVM, since only the harness reads the heap.
//!
//! A method that throws by design declares it: `throws: java.lang.ArithmeticException when divisor == 0` (JML's
//! `signals`) says that on the inputs where the condition holds the method throws that exception, and that
//! elsewhere it returns and the assertion holds. The exceptional path is then proved like the normal one, instead
//! of being assumed away.
//!
//! The counterexample JBMC finds is whatever satisfied the solver. Before it is reported it is shrunk
//! ([`crate::shrink`]) by running the harness class itself in the interpreter on smaller inputs, so the witness
//! shown is small and the same on every run; the solver's own is kept alongside it.

use std::fmt::Write as _;
use std::path::PathBuf;
use std::time::Duration;

use serde::Serialize;

use crate::classfile::Type;
use crate::classpath::ClassPath;
use crate::deadline::{Deadline, Run};
use crate::equivalence::extract_jdk_classes;
use crate::harness::{self, Signal};
use crate::interp::Value;
use crate::jbmc::{self, Argument, JbmcResult, JbmcRun};
use crate::sarif::{self, Finding};
use crate::{witness, Error, Verdict};

#[derive(Debug, Clone)]
pub struct Options {
    /// The compiled classes of the method under proof.
    pub classes: Vec<PathBuf>,
    pub classpath: Vec<PathBuf>,
    /// `pkg.Class#method`.
    pub target: String,
    /// The inputs the property is about: a boolean expression over the parameters, or every input when `None`.
    pub assume: Option<String>,
    /// The property: a boolean expression over the parameters, `result`, and calls of the method; `result` itself
    /// for a boolean method when `None`.
    pub assert: Option<String>,
    /// The exceptional behaviour: `<exception class> when <condition>`, each; the method throws that exception
    /// (or a subclass) exactly on the inputs where the condition holds.
    pub throws: Vec<String>,
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
    /// Array parameters that may be null (`--nullable`); every other is an array.
    pub nullable: Vec<String>,
    /// Pairs of array parameters that may be one array (`--may-alias a,b`), closed under transitivity: any two of
    /// a group may be; every other parameter is an array of its own. Only the own checker takes such a domain.
    pub may_alias: Vec<(String, String)>,
    /// A local proof cache directory (`prove --cache`): the property claim's key and its stored result, through
    /// `reuse::property_lookup` and `reuse::property_store`.
    pub cache: Option<PathBuf>,
    /// The construction plan of `prove --plan FILE` (its `after`, [`crate::construction::Plans`]): the receiver and
    /// parameters the check makes. What it can't make is refused by name.
    pub plan: Option<crate::construction::Plans>,
}

impl Options {
    pub fn new(classes: &[PathBuf], target: &str) -> Options {
        Options {
            classes: classes.to_vec(),
            classpath: Vec::new(),
            target: target.to_string(),
            assume: None,
            assert: None,
            throws: Vec::new(),
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
            nullable: Vec::new(),
            may_alias: Vec::new(),
            cache: None,
            plan: None,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct Counterexample {
    /// `delayMillis(attempt=63, baseMillis=1, capMillis=1)`.
    pub input: String,
    /// What the method did: its result, or the exception it threw.
    pub outcome: String,
    /// What a throws clause required instead, when one applies to the input or the method threw with none applying.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expected: Option<String>,
    pub values: Vec<String>,
    /// The input as JBMC found it, when `input` is the shrunk one.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub found: Option<String>,
    /// How many smaller inputs the interpreter tried while shrinking.
    pub shrink_runs: u32,
    /// The inputs, typed and exact, in parameter order.
    pub inputs: Vec<crate::witness::Typed>,
    /// The inputs as JBMC found them, when `inputs` are the shrunk ones.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub found_inputs: Option<Vec<crate::witness::Typed>>,
    /// The method's call on the inputs.
    pub call: crate::witness::Call,
}

#[derive(Debug, Clone, Serialize)]
pub struct Outcome {
    pub verdict: Verdict,
    pub target: String,
    pub domain: Option<String>,
    /// The assumption, as given.
    pub assume: Option<String>,
    /// The assertion, as checked.
    pub assert: Option<String>,
    /// The throws clauses, as given.
    pub throws: Vec<String>,
    /// The throws clauses as checked, each exception named in full (`java.lang.ArithmeticException when b == 0`);
    /// empty when the property was refused before they were resolved.
    pub throws_checked: Vec<String>,
    pub counterexample: Option<Counterexample>,
    pub proof: Option<String>,
    pub problem: Option<String>,
    pub statement: Option<PathBuf>,
    pub findings: Vec<Finding>,
    pub output: String,
    pub work: PathBuf,
    /// Why a verified property says nothing: the assumption admits no input in the domain.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vacuous: Option<String>,
    /// The checker run the verdict comes from; none when the property was refused before any checker ran.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub search: Option<crate::equivalence::Search>,
    /// How the checker's counterexample was replayed on the method, when it found one. `reproduced` is whether the
    /// interpreter's run of the method showed the property failing on it: false when the replay showed it holding
    /// (the verdict is then unverifiable), and false too when the property calls the method under proof and can be
    /// evaluated only in the harness, so that the violation is the checker's word.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub replay: Option<crate::equivalence::Replay>,
    /// The statement the verdict is about, as data ([`crate::statement`]); none when the property was refused
    /// before its harness was built.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stated: Option<crate::statement::Statement>,
    /// Under `--gaps advised`, the gaps the proof reaches with no contract, and what a contract for each must state
    /// ([`crate::advice`]): the run stopped before solving.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub advice: Option<crate::advice::Advice>,
    /// The name of the rule that refused the property before any checker ran, where it has one, so that a caller
    /// can tell a refusal from a run that went wrong: [`WIDENED_DOMAIN`]. None for every other refusal, and for a
    /// property a checker ran on.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub refused: Option<&'static str>,
}

/// The refusal of a domain JBMC is not given, where an array parameter may be null or one array with another
/// (`--nullable`, `--may-alias`), under `--engine jbmc` or `--confirm`: JBMC would prove a narrower claim.
pub const WIDENED_DOMAIN: &str = "widened-domain";

/// Runs the property proof.
pub fn run(options: &Options) -> Result<Outcome, Error> {
    crate::phases::begin();
    // The proof cache (`reuse::property_lookup`, `reuse::property_store`): a stored result for the same property
    // claim is the result, and a verified or refuted one is stored.
    // The property claim's key doesn't read a construction plan (its constructors, its setup sequence), so a plan's
    // check under the cache is refused by name, never stored under another plan's key.
    if options.cache.is_some() && options.plan.is_some() {
        crate::phases::end(0.0);
        return Err(Error::new("prove --cache with --plan: the property claim's key does not read the construction plan yet (the reuse stream's), so a result could be reused across plans"));
    }
    if options.cache.is_some() {
        match crate::reuse::property_lookup(options) {
            Err(u) => {
                crate::phases::end(0.0);
                return Err(Error::new(u.to_string()));
            }
            Ok(Some(hit)) => {
                crate::phases::end(0.0);
                return Ok(hit);
            }
            Ok(None) => {}
        }
    }
    let outcome = run_check(options);
    if let (Some(_), Ok(o)) = (&options.cache, &outcome) {
        if matches!(o.verdict, crate::Verdict::Verified | crate::Verdict::Violation) {
            crate::reuse::property_store(options, o).map_err(|u| Error::new(u.to_string()))?;
        }
    }
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
        None => crate::tla::tempfile_path("jvmcontract-property"),
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
            sarif::write(&report.join("property.sarif"), &findings)?;
        }
        Ok(Outcome {
            verdict: Verdict::Unverifiable,
            target: options.target.clone(),
            domain: None,
            assume: options.assume.clone(),
            assert: options.assert.clone(),
            throws: options.throws.clone(),
            throws_checked: Vec::new(),
            counterexample: None,
            proof: None,
            problem: Some(problem),
            statement: None,
            findings,
            output: out.clone(),
            work: work.clone(),
            vacuous: None,
            search: None,
            replay: None,
            stated: None,
            advice: None,
            refused: None,
        })
    };

    if options.contracts.is_some() && options.gaps != crate::bmc::gaps::GapMode::Advised {
        return Err(Error::new(crate::gap_contracts::CONTRACTS_NEED_ADVISED));
    }
    // A construction plan (`--plan`, its `after`): the receiver and each object parameter made as it says, and its
    // setup sequence called before the target (O1 and O3 of `llm-dlc/loops/application-core-objects.md`).
    let plan = match &options.plan {
        Some(plans) => {
            if let Err(u) = crate::construction::check_plans(&plans.before, &plans.after) {
                return refuse(&mut out, 1, u.what);
            }
            if !options.nullable.is_empty() || !options.may_alias.is_empty() {
                return refuse(&mut out, 1, "--nullable or --may-alias with a construction plan: the plan's nodes say which inputs may be null or one object".into());
            }
            if let Some(problem) = crate::construction::array_bound_problem(&plans.after, options.max_array_length) {
                return refuse(&mut out, 1, problem);
            }
            Some(&plans.after)
        }
        None => None,
    };

    // 1. The method.
    let mut cp = ClassPath::new();
    for path in options.classes.iter().chain(&options.classpath) {
        if path.exists() {
            cp.add(path)?;
        }
    }
    let Some(class) = cp.application(&class_internal)? else {
        return refuse(&mut out, 1, format!("class not found: {}", class_internal.replace('/', ".")));
    };
    let method = match crate::verifier::select_method(&class, &options.target) {
        Ok(m) => m.clone(),
        Err(problem) => return refuse(&mut out, 1, problem),
    };
    let line = method.first_line().map(u32::from).unwrap_or(1);
    // An instance method is called on an ordinary receiver made by its constructor (O1 of
    // `llm-dlc/loops/application-core-objects.md`), `this`, as an object parameter is made.
    let receiver = if method.is_static() {
        if plan.is_some_and(|p| p.roots.iter().any(|r| r.name == "this")) {
            return refuse(&mut out, line, format!("the plan has a root this, and {method_name} is a static method"));
        }
        None
    } else if let Some(p) = plan {
        match crate::construction::root(&cp, p, "this") {
            Ok(Some(crate::construction::Rooted::Object(r))) if r.class == class_internal => Some((r, None)),
            Ok(Some(_)) => return refuse(&mut out, line, format!("the plan's root this is not an object of {}", class_internal.replace('/', "."))),
            Ok(None) => return refuse(&mut out, line, format!("{method_name} is an instance method, and the plan has no root this")),
            Err(u) => return refuse(&mut out, line, u.what),
        }
    } else {
        match crate::construction::receiver(&cp, &class_internal) {
            Ok(r) => Some((r, None)),
            Err(u) => return refuse(&mut out, line, format!("{method_name} is an instance method, whose receiver is outside the objects a property check makes: {}", u.what)),
        }
    };
    let descriptor = method.parsed_descriptor()?;
    let names = method.parameter_names(&class.pool);
    // A parameter of an application class is an object made by its constructor (step H2 of
    // `llm-dlc/loops/foundations-heap.md`), from symbolic leaves, as in a regression check.
    let mut records = Vec::new();
    for (name, t) in names.iter().zip(&descriptor.params) {
        if let Some(p) = plan {
            match crate::construction::root(&cp, p, name) {
                Ok(Some(crate::construction::Rooted::Object(r))) if Type::Object(r.class.clone()) == *t => {
                    records.push(Some((r, None)));
                    continue;
                }
                Ok(Some(crate::construction::Rooted::Leaf(leaf))) if leaf == *t => {
                    records.push(None);
                    continue;
                }
                Ok(Some(_)) => return refuse(&mut out, line, format!("the plan's root {name} is not of the parameter's type {}", t.java_name())),
                Ok(None) if matches!(t, Type::Object(_)) => return refuse(&mut out, line, format!("the plan has no root {name}, an object parameter of {method_name}")),
                Ok(None) => {}
                Err(u) => return refuse(&mut out, line, u.what),
            }
        }
        if t.is_primitive() || harness::expr::element_ty(t).is_some() {
            records.push(None);
            continue;
        }
        let made = match t {
            Type::Object(class) if cp.application(class)?.is_some() => crate::equivalence::made_of(&cp, class, &mut Vec::new())?,
            _ => return refuse(&mut out, line, format!("parameter {name} has type {}; the symbolic verifier handles primitive parameters, arrays of integral or boolean elements, and objects of application classes made by their constructor. Finite types (enums, booleans) are covered by behavioural contracts.{}", t.java_name(), crate::equivalence::adapted_refusal(t, options.max_array_length))),
        };
        match made {
            Ok(record) => records.push(Some((record, None))),
            Err(gap) => return refuse(&mut out, line, format!("parameter {name} has type {}, which is outside the objects a property check makes: {gap}", t.java_name())),
        }
    }
    let params = harness::params(&names, &descriptor.params);
    // A result of an application class is read by its fields (`result.quantity`) and compared by identity.
    let result_fields = match &descriptor.ret {
        Type::Object(class) if cp.application(class)?.is_some() => crate::equivalence::fields_of(&cp, class, &mut Vec::new())?.ok(),
        _ => None,
    };
    let over_objects = receiver.is_some() || records.iter().any(Option::is_some) || result_fields.is_some();
    if let Some(extra) = plan.and_then(|p| p.roots.iter().find(|r| r.name != "this" && !names.contains(&r.name))) {
        return refuse(&mut out, line, format!("the plan's root {} is no parameter of {method_name}, whose parameters are {}", extra.name, names.join(", ")));
    }
    let mut layout = if over_objects { harness::Layout::new(receiver, &names, &descriptor.params, &records, (None, None)) } else { harness::Layout::plain(&names, &descriptor.params) };
    layout.result_fields.0 = result_fields;
    // The plan's setup sequence (O3): a history whose call throws reaches no state, and is outside the property.
    if let Some(p) = plan.filter(|p| !p.setup.is_empty()) {
        let calls = match crate::construction::setup_calls(&cp, p, &class_internal) {
            Ok(c) => c,
            Err(u) => return refuse(&mut out, line, u.what),
        };
        for (m, d, args) in calls {
            if let Err(problem) = layout.add_setup(&m, &d, &args) {
                return refuse(&mut out, line, problem);
            }
        }
    }
    // The choices of null and of one object: an array parameter's are the own checker's, an object parameter's the
    // harness's flags.
    // Over objects, a name that is not an array's is the layout's to judge (an object's, or one it refuses by name).
    let is_array = |n: &str| !over_objects || params.iter().any(|p| p.name == n && matches!(p.ty, Type::Array(_)));
    let (array_nullable, object_nullable): (Vec<String>, Vec<String>) = options.nullable.iter().cloned().partition(|n| is_array(n));
    let mut object_pairs = Vec::new();
    let mut array_pairs = Vec::new();
    for (a, b) in &options.may_alias {
        match (is_array(a), is_array(b)) {
            (true, true) => array_pairs.push((a.clone(), b.clone())),
            (false, false) => object_pairs.push((a.clone(), b.clone())),
            _ => return refuse(&mut out, line, format!("--may-alias {a},{b}: an array and {} are never one", if is_array(a) { b } else { a })),
        }
    }
    if over_objects && (!array_nullable.is_empty() || !array_pairs.is_empty()) {
        return refuse(&mut out, line, "a property over objects does not let an array parameter be null or one array with another yet; check the arrays' choices in a property of no object parameters".into());
    }
    let (parameters, groups) = match parameter_domain(&params, &array_nullable, &array_pairs) {
        Ok(p) => p,
        Err(problem) => return refuse(&mut out, line, problem),
    };
    // The plan's choices (O2), as in a regression check: flags for null and for one of other roots' objects, and a
    // node at two roots one object with no flag.
    if let Some(c) = plan.map(crate::construction::choices).filter(|c| !c.is_empty()) {
        let order: Vec<String> = layout.receiver.iter().map(|_| "this".to_string()).chain(names.iter().cloned()).collect();
        if let Err(problem) = layout.choose_in(&c.nullable, &harness::alias_groups(&c.may_alias, &order), true) {
            return refuse(&mut out, line, format!("the plan's choices: {problem}"));
        }
        for (name, other) in &c.shared {
            if let Err(problem) = layout.share(name, other) {
                return refuse(&mut out, line, format!("the plan's node at the roots {other} and {name}: {problem}"));
            }
        }
    }
    if !object_nullable.is_empty() || !object_pairs.is_empty() {
        let order: Vec<String> = layout.receiver.iter().map(|_| "this".to_string()).chain(names.iter().cloned()).collect();
        if let Err(problem) = layout.choose_in(&object_nullable, &harness::alias_groups(&object_pairs, &order), true) {
            return refuse(&mut out, line, problem);
        }
    }
    let has_arrays = params.iter().any(|p| matches!(p.ty, Type::Array(_)));
    // The harness's own parameters: the method's, or over objects their leaves and the choices' flags.
    let entry_types = layout.types();
    let entry_slots: Vec<u16> = layout.params.iter().map(|p| p.slot).collect();
    let flat = layout.params.clone();
    let render = |arguments: &[Argument]| if over_objects { witness::call_in(&method_name, &layout, arguments) } else { witness::call(&method_name, &params, arguments) };
    let domain = if over_objects { layout.domain(options.max_array_length) } else { harness::domain_of(&params, options.max_array_length, &options.nullable, &groups) };
    // A claim over objects made by their constructor is about those objects alone, and says so.
    let every = if crate::equivalence::made_by_constructor(&layout) { "every input of constructor-made objects" } else { "every input" };
    // JBMC gives each array parameter an array of its own, never null: it would prove a narrower claim.
    let widened = !parameters.is_default();
    if widened && (options.engine == crate::Engine::Jbmc || options.confirm) {
        let how = if options.confirm { "--confirm would have JBMC check a narrower claim than this one" } else { "JBMC is not given it" };
        let mut refused = refuse(&mut out, line, format!("the domain {domain} lets an array parameter be null or one array with another, which only the tool's own checker takes, and {how}: check it with --engine native or auto"))?;
        refused.refused = Some(WIDENED_DOMAIN);
        return Ok(refused);
    }

    // 2. The statement. A declared exception is named as in Java, `java.lang.ArithmeticException`, or by its simple
    // name when it is in java.lang or the target's package.
    let cp = cp.with_default_jdk();
    let mut signals = Vec::new();
    for clause in &options.throws {
        let mut signal = match Signal::parse(clause) {
            Ok(s) => s,
            Err(e) => return refuse(&mut out, line, format!("the property is not well-formed: {e}")),
        };
        if !signal.class.contains('/') {
            let package = class_internal.rsplit_once('/').map(|(p, _)| format!("{p}/")).unwrap_or_default();
            match [format!("java/lang/{}", signal.class), format!("{package}{}", signal.class)].into_iter().find(|c| cp.exists(c)) {
                Some(c) => signal.class = c,
                None => return refuse(&mut out, line, format!("the property is not well-formed: in the throws clause `{}`: no class {} in java.lang or the target's package", signal.render(), signal.class)),
            }
        } else if !cp.exists(&signal.class) {
            return refuse(&mut out, line, format!("the property is not well-formed: in the throws clause `{}`: class not found", signal.render()));
        }
        if !cp.is_subtype(&signal.class, "java/lang/Throwable") {
            return refuse(&mut out, line, format!("the property is not well-formed: in the throws clause `{}`: {} is not a Throwable", signal.render(), signal.java_name()));
        }
        signals.push(signal);
    }
    let harness = match harness::generate_property_over(&class_internal, &method_name, &layout, &descriptor.ret, options.assume.as_deref(), options.assert.as_deref(), &signals, options.max_array_length) {
        Ok(h) => h,
        Err(e) => return refuse(&mut out, line, format!("the property is not well-formed: {e}")),
    };
    let throws_text = signals.iter().map(Signal::render).collect::<Vec<_>>();
    let throws_checked = signals.iter().map(|s| format!("{} when {}", s.java_name(), s.when)).collect::<Vec<_>>();
    let harness_dir = work.join("harness");
    std::fs::create_dir_all(&harness_dir)?;
    std::fs::write(harness_dir.join(format!("{}.class", harness::PROPERTY_CLASS)), &harness.bytes)?;
    let statement = harness_dir.join(format!("{}.java", harness::PROPERTY_CLASS));
    std::fs::write(&statement, &harness.source)?;
    let assertion = harness.assertion_text.clone();
    let stated_domain = if over_objects { crate::statement::domain(&layout, options.max_array_length) } else { crate::statement::plain_domain_of(&params, options.max_array_length, &options.nullable, &groups) };
    let observations = crate::statement::property_observations(&assertion, &throws_checked);
    let stated = |last: Option<&crate::jbmc::JbmcResult>, search: Option<&crate::equivalence::Search>, complete: bool| crate::statement::Statement {
        kind: "property".into(),
        domain: stated_domain.clone(),
        assumptions: options
            .assume
            .iter()
            .map(|a| crate::statement::Assumption { kind: crate::statement::AssumptionKind::Precondition, text: a.clone(), basis: crate::statement::Basis::Stated, id: None })
            .chain(crate::statement::property_assumptions(&layout))
            .chain((!layout.setup.is_empty()).then(|| crate::statement::Assumption {
                kind: crate::statement::AssumptionKind::Setup,
                text: format!("the receiver is in a state {} reaches from its construction, on any arguments it accepts, and in no other; a history whose call throws is outside the property", layout.setup_text(&|i| layout.params[i].name.clone()).join(" then ")),
                basis: crate::statement::Basis::Stated,
                id: None,
            }))
            .chain(crate::statement::checker_assumptions(last))
            .collect(),
        observations: observations.clone(),
        bounds: crate::construction::stated_bounds(&layout, crate::statement::bounds(Some(options.unwind), &stated_domain, options.max_array_length, complete), options.max_array_length),
        models: crate::statement::models(options.models),
        checker: crate::statement::checker(search, options.sat_solver.as_deref(), || crate::jbmc::sat(&options.jbmc, options.sat_solver.as_deref(), options.refine_strings)),
        gap_mode: last.and_then(|l| l.gap_mode),
        confirmation: search.and_then(|s| s.confirmation.as_ref()).map(|c| c.status),
        vacuity: None,
        spec: None,
    };

    // 3. The JDK bytecode JBMC needs beyond its own models, and the tool's models of the JDK classes it has none of.
    let jdk_dir = work.join("jdk");
    if let Err(e) = extract_jdk_classes(&jdk_dir, options.java_home.as_deref()) {
        let _ = writeln!(out, "note: {e}; JBMC will use its own models of java.lang.Math");
    }
    let models_dir = work.join("models");
    if options.models {
        crate::models::write_to(&models_dir)?;
    }
    // A declared JDK exception JBMC has no model of (a ClassFormatError, say) is taken from the JDK image with its
    // superclasses up to one JBMC models, so that the harness's handler for it and the method's `new` of it agree.
    if let Err(e) = extract_exception_classes(&jdk_dir, &cp, &signals) {
        let _ = writeln!(out, "note: {e}");
    }

    // 4. Prove, or search for a counterexample: small inputs first, then all of them.
    let mut classpath = vec![harness_dir.clone()];
    classpath.extend(options.classes.iter().cloned());
    classpath.push(jdk_dir.clone());
    classpath.extend(options.classpath.iter().cloned());
    if options.models {
        classpath.push(models_dir.clone()); // last, so that a class the application or its class path has takes precedence
    }
    let started = std::time::Instant::now();
    // One deadline for the whole check, each run a budget out of it ([`crate::deadline`]).
    let deadline = Deadline::starting_now(Duration::from_secs(options.timeout_seconds));
    let mut runs = Vec::new();
    let mut last = None;
    // The tool's own checker first, when asked: its verdict stands, and where it has none, JBMC's turn (under
    // `auto`), or that is the answer (under `native`). JBMC's interval stages run only where they bound an input,
    // and only those its staging policy picks ([`crate::deadline::Staging`]).
    let mut stages = options.jbmc_staging.stages(&crate::deadline::entry_parameters(&harness.bytes, harness::METHOD)?);
    let mut fallback = None;
    let mut gap_setting = crate::bmc::gaps::GapSetting::from(options.gaps);
    let entries: Vec<PathBuf> = classpath.iter().filter(|p| **p != jdk_dir && **p != models_dir).cloned().collect();
    let contract_options = crate::gap_contracts::ContractOptions { file: options.contracts.clone(), library: options.contract_library, max_trust: options.max_trust };
    let where_ = options.assume.as_deref().map(|a| format!(" where {a}")).unwrap_or_default();
    let claim = crate::advice::Claim { kind: "property".into(), target: options.target.clone(), text: format!("satisfies `{assertion}` on {every}{where_}"), harness: statement.clone() };
    // Under advised, a gap the proof reaches with no contract goes to the agent before anything is solved.
    let stop_with = |out: &mut String, advice: crate::advice::Advice| -> Result<Outcome, Error> {
        let p = advice.problem();
        let message = format!("{} cannot be verified: {p}", options.target);
        let _ = writeln!(out, "✗ {message}");
        out.push_str(&advice.lines());
        let findings = vec![Finding::new("gaps-need-contracts", message, uri.clone(), line)];
        if let Some(report) = &options.report {
            sarif::write(&report.join("property.sarif"), &findings)?;
        }
        let mut s = stated(None, None, false);
        s.checker = crate::statement::scan_checker();
        s.gap_mode = Some(crate::bmc::gaps::GapMode::Advised);
        Ok(Outcome { verdict: Verdict::Unverifiable, target: options.target.clone(), domain: Some(domain.clone()), assume: options.assume.clone(), assert: Some(assertion.clone()), throws: options.throws.clone(), throws_checked: throws_checked.clone(), counterexample: None, proof: None, problem: Some(p), statement: Some(statement.clone()), findings, output: out.clone(), work: work.clone(), vacuous: None, search: None, replay: None, stated: Some(s), advice: Some(advice), refused: None })
    };
    if options.engine != crate::Engine::Jbmc {
        // Under advised, what the harness may reach first: the contract library closes only gaps it reaches.
        let scanned = if options.gaps == crate::bmc::gaps::GapMode::Advised { Some(crate::advice::scan_harness(&entries, options.models, harness::PROPERTY_CLASS, harness::METHOD)?) } else { None };
        let (setting, loaded, notes) = crate::gap_contracts::setting(options.gaps, &contract_options, scanned.as_ref().map(|(_, s)| s), &entries, options.models, &work)?;
        gap_setting = setting;
        out.push_str(&notes);
        if options.gaps == crate::bmc::gaps::GapMode::Advised {
            let (cp, scan) = scanned.as_ref().expect("scanned under advised");
            if let Some(advice) = crate::advice::preflight(cp, scan, claim.clone(), &work, loaded.as_ref(), None)? {
                return stop_with(&mut out, advice);
            }
        }
        let budget = crate::equivalence::own_budget(&deadline, options.engine);
        let result = crate::bmc::run_for_proof(&entries, options.models, harness::PROPERTY_CLASS, harness::METHOD, options.unwind, options.max_array_length, budget, &gap_setting, &parameters, &work)?;
        runs.push(Run::of(&result, "proof", budget));
        if result.verdict != Verdict::Unverifiable || options.engine == crate::Engine::Native || crate::equivalence::refuses_gaps(&result) || widened {
            if options.engine == crate::Engine::Auto && result.verdict == Verdict::Unverifiable {
                let _ = writeln!(out, "{}", if widened { NOT_JBMC_DOMAIN } else { crate::equivalence::NOT_JBMC });
            }
            stages.clear();
            last = Some(result);
        } else {
            let _ = writeln!(out, "note: the tool's own checker gave no verdict ({}); JBMC", result.problem.as_deref().unwrap_or("no reason"));
            fallback = Some(result.problem.clone().unwrap_or_else(|| "no reason".into()));
        }
    }
    // An array parameter is never null, and is bounded in length: a quantifier over it is a loop the unwinding
    // bound must cover.
    let extra_args = if has_arrays {
        vec!["--java-assume-inputs-non-null".to_string(), "--max-nondet-array-length".to_string(), options.max_array_length.to_string()]
    } else {
        Vec::new()
    };
    let purpose = if fallback.is_some() { "fallback" } else { "proof" };
    let base = JbmcRun {
        executable: crate::jbmc::executable(&options.jbmc),
        class: harness::PROPERTY_CLASS.into(),
        function: harness::METHOD.into(),
        classpath: classpath.clone(),
        unwind: options.unwind,
        timeout: Duration::ZERO,
        stage: None,
        refine_strings: options.refine_strings,
        sat_solver: options.sat_solver.clone(),
        log: work.join("jbmc.log"),
        extra_args: extra_args.clone(),
        tells_exceptions: !options.throws.is_empty(),
    };
    // What JBMC approximates on the way (its stubs, the call sites it does not link), from its goto program.
    let mut preflight = if stages.is_empty() { None } else { Some(crate::jbmc_gaps::preflight(&base, deadline.share(crate::deadline::STAGE_SHARE))?) };
    // Under advised, JBMC applies the contracts for its gaps ([`crate::jbmc_contracts`]): under `--engine jbmc` they
    // are read for the gaps its program reaches, with the advice when one has none; under `auto`, they are the own
    // checker's.
    let mut base = base;
    let mut applied = None;
    if let (crate::bmc::gaps::GapMode::Advised, Some(pre)) = (options.gaps, preflight.as_ref()) {
        if options.engine == crate::Engine::Jbmc {
            let prepared = crate::jbmc_contracts::prepare(pre, &contract_options, claim.clone(), &entries, options.models, &work)?;
            out.push_str(&prepared.notes);
            gap_setting = prepared.setting;
            if let Some(advice) = prepared.advice {
                return stop_with(&mut out, advice);
            }
        }
        if let Some(found) = pre.found.as_ref().filter(|_| !gap_setting.contracts.is_empty()) {
            let a = crate::jbmc_contracts::apply(&gap_setting, found, &base.classpath, &entries, &cp, &work.join("jbmc-contracts"))?;
            out.push_str(&a.notes);
            if !a.records.is_empty() {
                let _ = writeln!(out, "note: JBMC applies {} contract{} for its gaps, at their call sites in {} class{} rewritten ({})", a.records.len(), if a.records.len() == 1 { "" } else { "s" }, a.classes, if a.classes == 1 { "" } else { "es" }, work.join("jbmc-contracts").display());
                base = JbmcRun { classpath: a.classpath.clone(), log: work.join("jbmc-contracts").join("jbmc.log"), ..base };
                // What JBMC still approximates once the contracts stand at their calls.
                preflight = Some(crate::jbmc_gaps::preflight(&base, deadline.share(crate::deadline::STAGE_SHARE))?);
                applied = Some(a);
            }
        }
    }
    for stage in &stages {
        let budget = deadline.for_stage(*stage, options.jbmc_staging);
        let run = JbmcRun { timeout: budget, stage: stage.map(str::to_string), log: work.join(format!("jbmc{}.log", stage.map(|s| format!("-{}", s.replace(|c: char| !c.is_ascii_digit() && c != '-', "_"))).unwrap_or_default())), ..base.clone() };
        let result = jbmc::run(&run)?;
        runs.push(Run::of(&result, purpose, budget));
        // A preliminary stage out of its budget hands on: only the last stage is the proof.
        let stop = result.verdict != Verdict::Verified && !(stage.is_some() && result.out_of_time());
        last = Some(result);
        if stop {
            break;
        }
    }
    let mut last = last.expect("at least one stage");
    if let Some(pre) = preflight.as_ref().filter(|_| last.native.is_none()) {
        out.push_str(&pre.note());
        crate::jbmc_gaps::hold(&mut last, pre, options.gaps);
        if let Some(a) = &applied {
            crate::jbmc_contracts::settle(&mut last, a);
        }
    }
    let seconds = started.elapsed().as_secs_f64();
    // Under `--confirm`, the own checker's proof is JBMC's to prove again, over every input in one run: the stages
    // only find a small witness sooner, and the proof is the last one's. It is a second check, by a second checker,
    // with a deadline of its own.
    let (confirmation, refuting) = if options.confirm && options.engine == crate::Engine::Auto && last.native.is_some() && last.verdict == Verdict::Verified {
        let run = JbmcRun { timeout: Duration::from_secs(options.timeout_seconds), log: work.join("jbmc-confirm.log"), ..base.clone() };
        let contracts = crate::equivalence::ConfirmContracts { setting: &gap_setting, rewrite: entries.clone(), cp: &cp, dir: work.join("jbmc-confirm-contracts") };
        let harness_cp = witness::classpath(std::iter::once(harness_dir.as_path()).chain(options.classes.iter().chain(&options.classpath).map(PathBuf::as_path)))?.with_models(options.models);
        let reproduces = |r: &JbmcResult| -> Result<Option<bool>, Error> { Ok(witness::fails_in_harness(&harness_cp, harness::PROPERTY_CLASS, &entry_types, &r.arguments(&entry_types)?)) };
        let (c, refuting) = crate::equivalence::confirm(&last, &run, Some(contracts), &reproduces)?;
        (Some(c), refuting)
    } else {
        (None, None)
    };
    let mut search = Some(crate::equivalence::Search {
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
    let where_ = options.assume.as_deref().map(|a| format!(" where {a}")).unwrap_or_default();
    let and_throws = if throws_text.is_empty() { String::new() } else { format!(", and {}", throws_text.join(", and ")) };
    // A property that is its throws clauses alone claims that the method returns elsewhere.
    let claim = if assertion == "true" && !signals.is_empty() { "returns".to_string() } else { format!("satisfies `{assertion}`") };

    let mut findings = Vec::new();
    let mut counterexample = None;
    let mut proof = None;
    let mut problem = None;
    let mut vacuous = None;
    let mut vacuity_status = None;
    let mut verdict = last.verdict;
    // JBMC refutes what the own checker proved: neither verdict stands. JBMC's witness is the counterexample, and
    // the interpreter's run of the method on it is shown, but it decides nothing: it shares the own checker's
    // models, and the disagreement is for a person (or a JVM) to settle.
    if let Some(refuting) = &refuting {
        let found = refuting.arguments(&entry_types)?;
        let replay_cp = witness::classpath(options.classes.iter().chain(&options.classpath).map(PathBuf::as_path))?.with_models(options.models);
        let replayed = witness::replay_in(&replay_cp, &layout, None, &class_internal, &method_name, &method.descriptor, &descriptor, &found);
        let outcome = replayed.with_leftovers(&flat, &found);
        let harness_cp = witness::classpath(std::iter::once(harness_dir.as_path()).chain(options.classes.iter().chain(&options.classpath).map(PathBuf::as_path)))?.with_models(options.models);
        let reproduced = witness::fails_in_harness(&harness_cp, harness::PROPERTY_CLASS, &entry_types, &found);
        let (rendered, values) = render(&found);
        let (assuming, _) = crate::equivalence::assumed_gaps(&last);
        let p = format!(
            "the engines disagree: the tool's own checker proves that it {claim} on {every}{where_}{and_throws}{assuming} ({}, {seconds:.1} s), and {} refutes it on\n  {rendered}\n    outcome in the interpreter: {outcome}, {}",
            last.version,
            refuting.version,
            reproduced_words(reproduced)
        );
        let message = format!("{} cannot be verified: {p}", options.target);
        let _ = writeln!(out, "✗ {message}");
        let _ = writeln!(out, "\nNeither verdict stands. Run the method on the input above on a JVM: if the property fails there, the tool's own checker is wrong, and otherwise JBMC is.");
        findings.push(Finding::new("engines-disagree", message, uri.clone(), line));
        if let Some(report) = &options.report {
            sarif::write(&report.join("property.sarif"), &findings)?;
        }
        let target = witness::Target { class_internal: &class_internal, method: &method_name, descriptor: &method.descriptor, is_static: method.is_static(), classes: "after" };
        let call = witness::typed_call(&target, &layout, &found, false, &[]);
        let counterexample = Some(Counterexample { input: rendered, outcome, expected: None, values, found: None, shrink_runs: 0, inputs: witness::typed_inputs(&flat, &found), found_inputs: None, call });
        let replay = Some(crate::equivalence::Replay { by: "interpreter".into(), reproduced: reproduced == Some(true) });
        return Ok(Outcome { verdict: Verdict::Unverifiable, target: options.target.clone(), domain: Some(domain), assume: options.assume.clone(), assert: Some(assertion), throws: options.throws.clone(), throws_checked, counterexample, proof: None, problem: Some(p), statement: Some(statement), findings, output: out, work, vacuous: None, stated: Some(stated(Some(&last), search.as_ref(), false)), search, replay, advice: None, refused: None });
    }
    match last.verdict {
        Verdict::Verified => {
            let how = format!("{}: {} properties proved over {domain} in {seconds:.1} s; loops unwound {} times with unwinding assertions", last.version, last.properties, options.unwind);
            let (assuming, assumed) = crate::equivalence::assumed_gaps(&last);
            let (relying, relied) = crate::equivalence::relied_contracts(&last);
            let _ = writeln!(out, "✓ {} {claim} on {every}{where_}{and_throws}{assuming}{relying} ({how})", options.target);
            out.push_str(&assumed);
            out.push_str(&relied);
            if let Some(c) = search.as_ref().and_then(|s| s.confirmation.as_ref()) {
                out.push_str(&crate::equivalence::confirmation_line(c));
            }
            proof = Some(how);
            // An assumption may admit no input in the domain: the property is then checked on none.
            if !harness.probe.is_empty() {
                let mut entries = options.classes.clone();
                entries.extend(options.classpath.iter().cloned());
                let render = |r: &JbmcResult| r.arguments(&entry_types).ok().map(|found| render(&found).0);
                let (reason, status) = crate::equivalence::vacuity(&mut out, &harness.probe, harness::PROPERTY_CLASS, &entries, options.models, options.unwind, options.max_array_length, deadline.left(), &gap_setting, &parameters, &work, "failing the assumption (--assume)", &render, &mut search)?;
                vacuous = reason;
                vacuity_status = Some(status);
            } else {
                vacuity_status = Some(crate::statement::Vacuity::every_input());
            }
        }
        Verdict::Violation => {
            let found = last.arguments(&entry_types)?;
            let replay_cp = witness::classpath(options.classes.iter().chain(&options.classpath).map(PathBuf::as_path))?.with_models(options.models);
            let replay_on = |arguments: &[Argument]| witness::replay_in(&replay_cp, &layout, None, &class_internal, &method_name, &method.descriptor, &descriptor, arguments);
            let mut replayed = replay_on(&found);
            // The JDK the witness was run on, when the interpreter could not run it and a JVM did.
            let mut on_jvm: Option<String> = None;
            let mut jvm_ran = false;
            // The throws clause that applies to an input: the first whose condition holds; `None` when none does
            // or a condition cannot be evaluated outside the harness (it calls the method).
            let applying = |arguments: &[Argument]| -> Option<usize> {
                if over_objects {
                    return None;
                }
                let (locals, arrays) = witness::locals_of(&params, arguments, &[]);
                harness.signals.iter().position(|(_, when)| matches!(harness::expr::eval_with(when, &locals, &arrays), Ok(Value::Int(1))))
            };
            // A counterexample on which the interpreter finds the property holding is no counterexample: JBMC has
            // given an arbitrary result to a method it had no bytecode for. (A property that calls the method
            // under proof is checked in the harness only, so it is taken at JBMC's word.) The assertion reads an
            // array parameter after the call, as the harness does, so a method that writes into it is held to
            // what it wrote.
            let assertion_on = |arguments: &[Argument], result: Value, result_array: &Option<Vec<Value>>, arrays_after: &[(u16, Vec<Value>)]| -> Result<Value, Error> {
                let (mut locals, mut arrays) = witness::locals_of(&params, arguments, arrays_after);
                // What \old(a) reads: the array as the call received it.
                for (a, p) in arguments.iter().zip(&params) {
                    let before = match a {
                        Argument::Array(data) => Some(data),
                        Argument::Same(i) => match arguments.get(*i) {
                            Some(Argument::Array(data)) => Some(data),
                            _ => None,
                        },
                        _ => None,
                    };
                    if let (Some(data), Some((_, copy))) = (before, harness.old.iter().find(|(slot, _)| *slot == p.slot)) {
                        arrays.push((*copy, data.clone()));
                    }
                }
                let result_slot = locals.len() as u16;
                locals.push(result);
                if result.is_wide() {
                    locals.push(Value::Int(0));
                }
                if let Some(data) = result_array {
                    arrays.push((result_slot, data.clone()));
                }
                harness::expr::eval_with(&harness.assertion, &locals, &arrays)
            };
            // A witness that the interpreter cannot run (a JDK call outside it) is run on a JVM: the harness on the
            // witness, with the JDK's real calls where any contracts stood. It is a counterexample when the property
            // fails there, and none when the JVM's calls do not take the method where the checker supposed. Without
            // a contract too: an outcome the interpreter could not produce reproduces nothing (O2, after VF-015).
            let unreplayed = Some(&replayed).filter(|r| r.could_not_replay()).map(|r| r.outcome.clone());
            let through_contracts = unreplayed.as_deref().and_then(|t| crate::equivalence::unconfirmed_through_contracts(&last, &render(&found).0, t));
            let contracted = through_contracts.is_some();
            let mut unconfirmed = through_contracts.or_else(|| unreplayed.as_deref().map(|t| crate::equivalence::unreplayed(&last, &render(&found).0, t, "the method")));
            if let Some(p) = &unconfirmed {
                let mut entries = vec![harness_dir.clone()];
                entries.extend(options.classes.iter().cloned());
                entries.extend(options.classpath.iter().cloned());
                // Over objects the JVM runs the harness alone, which makes them: a direct call takes flat values.
                let calls = if over_objects { Vec::new() } else { vec![crate::jvm_witness::DirectCall { owner: class_internal.clone(), name: method_name.clone(), descriptor: method.descriptor.clone(), ret: descriptor.ret.clone() }] };
                let rendered = render(&found).0;
                match crate::jvm_witness::run(&work.join("jvm-witness"), harness::PROPERTY_CLASS, &entry_types, &entry_slots, &found, &calls, &entries) {
                    Ok(run) if run.check == crate::jvm_witness::Check::Refuted => {
                        if let Some(call) = run.calls.into_iter().next() {
                            replayed = call;
                        }
                        on_jvm = Some(run.jdk);
                        unconfirmed = None;
                    }
                    Ok(run) if run.check == crate::jvm_witness::Check::Holds => {
                        jvm_ran = true;
                        let did = run.calls.first().map(|r| if r.thrown.is_some() || r.outcome == "void" { r.with_leftovers(&flat, &found) } else { format!("returns {}", r.with_leftovers(&flat, &found)) }).unwrap_or_default();
                        let what = format!("the method {did} there and the property holds on it");
                        unconfirmed = Some(if contracted { crate::equivalence::not_reproduced_on_jvm(&last, &rendered, &run.jdk, &what, false) } else { format!("{p}; on a JVM (JDK {}), {what}, so it is no counterexample. {}", run.jdk, crate::equivalence::unreproduced_cause(&last)) });
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
                if let Some(report) = &options.report {
                    sarif::write(&report.join("property.sarif"), &findings)?;
                }
                let by = if jvm_ran { "jvm" } else { "interpreter" };
                let replay = Some(crate::equivalence::Replay { by: by.into(), reproduced: false });
                return Ok(Outcome { verdict, target: options.target.clone(), domain: Some(domain), assume: options.assume.clone(), assert: Some(assertion), throws: options.throws.clone(), throws_checked, counterexample, proof, problem, statement: Some(statement), findings, output: out, work, vacuous: None, stated: Some(stated(Some(&last), search.as_ref(), false)), search, replay, advice: None, refused: None });
            }
            // Over objects the property reads the heap, which only the harness can: the interpreter runs the harness
            // itself on the witness, which makes the objects as the checker did.
            let evaluable = !over_objects && !harness.assertion.has_call() && harness.signals.iter().all(|(_, when)| !when.has_call());
            let harness_cp = witness::classpath(std::iter::once(harness_dir.as_path()).chain(options.classes.iter().chain(&options.classpath).map(PathBuf::as_path)))?.with_models(options.models);
            let in_harness = if over_objects { witness::fails_in_harness(&harness_cp, harness::PROPERTY_CLASS, &entry_types, &found) } else { None };
            let holds_on_found = match (applying(&found), replayed.returned, replayed.thrown.as_deref()) {
                _ if over_objects => in_harness == Some(false),
                (Some(i), _, Some(thrown)) => cp.is_subtype(thrown, &harness.signals[i].0.class),
                (Some(_), _, None) => false,
                (None, Some(result), _) => matches!(assertion_on(&found, result, &replayed.result_array, &replayed.arrays_after), Ok(Value::Int(1))),
                (None, None, _) => false,
            };
            if (evaluable || over_objects) && holds_on_found {
                let (rendered, _) = render(&found);
                let did = if replayed.thrown.is_some() { replayed.outcome.clone() } else { format!("returns {}", replayed.outcome) };
                let p = format!("{}'s counterexample {rendered} does not reproduce: the method {did} in the interpreter and the property holds on it. {}", if last.native.is_some() { "The tool's own checker" } else { "JBMC" }, preflight.as_ref().filter(|_| last.native.is_none()).and_then(crate::jbmc_gaps::Preflight::unreproduced_cause).unwrap_or_else(|| crate::equivalence::unreproduced_cause(&last)));
                let message = format!("{} cannot be verified: {p}", options.target);
                let _ = writeln!(out, "✗ {message}");
                findings.push(Finding::new("unverifiable", message, uri.clone(), line));
                problem = Some(p);
                verdict = Verdict::Unverifiable;
                if let Some(report) = &options.report {
                    sarif::write(&report.join("property.sarif"), &findings)?;
                }
                let replay = Some(crate::equivalence::Replay { by: "interpreter".into(), reproduced: false });
                return Ok(Outcome { verdict, target: options.target.clone(), domain: Some(domain), assume: options.assume.clone(), assert: Some(assertion), throws: options.throws.clone(), throws_checked, counterexample, proof, problem, statement: Some(statement), findings, output: out, work, vacuous: None, stated: Some(stated(Some(&last), search.as_ref(), false)), search, replay, advice: None, refused: None });
            }
            // Shrink the witness: the harness class JBMC checked, run in the interpreter on smaller inputs.
            let mut shrink_runs = 0;
            let mut arguments = found.clone();
            // The interpreter is the shrinker's oracle, and it cannot run a witness only a JVM could.
            // It changes the leaves alone, never a choice's flag, so that it never merges or splits objects.
            if options.shrink && on_jvm.is_none() {
                // A candidate is the same failure where it fails in the same way as the input found (O2): the same
                // throws clause applying, and the same exception or a normal return, never another kind of failure.
                let failure = (applying(&found), replayed.thrown.clone());
                let same = |candidate: &[Argument]| (applying(candidate), replay_on(candidate).thrown) == failure;
                let shrunk = witness::shrink_in_harness_keeping(&harness_cp, harness::PROPERTY_CLASS, &entry_types, found.clone(), &layout.flags(), same);
                shrink_runs = shrunk.runs;
                arguments = shrunk.arguments;
            }
            let shrunk = arguments != found;
            let replayed = if shrunk { replay_on(&arguments) } else { replayed };
            // A witness over objects is run on a JVM too (step H4 of `llm-dlc/loops/foundations-heap.md`): the
            // harness, which makes the objects from the same leaves with the same identities, the application's
            // classes opened so that it may read their fields. The JVM is the reference: where its harness holds on
            // the witness, the interpreter was wrong and nothing is reported.
            let mut jvm_note = None;
            if over_objects && on_jvm.is_none() {
                let mut entries = vec![harness_dir.clone()];
                entries.extend(options.classes.iter().cloned());
                entries.extend(options.classpath.iter().cloned());
                let rendered = render(&arguments).0;
                match crate::jvm_witness::run(&work.join("jvm-witness"), harness::PROPERTY_CLASS, &entry_types, &entry_slots, &arguments, &[], &entries) {
                    Ok(run) if run.check == crate::jvm_witness::Check::Refuted => jvm_note = Some((true, format!("and run on a JVM (JDK {}), where the harness fails on it too", run.jdk))),
                    Ok(run) if run.check == crate::jvm_witness::Check::Holds => {
                        let p = format!("the counterexample {rendered} fails the property's harness in the interpreter, but on a JVM (JDK {}) the harness holds on it. The JVM is the reference, so the tool's interpreter is wrong here and the witness is not reported", run.jdk);
                        let message = format!("{} cannot be verified: {p}", options.target);
                        let _ = writeln!(out, "✗ {message}");
                        findings.push(Finding::new("unverifiable", message, uri.clone(), line));
                        if let Some(report) = &options.report {
                            sarif::write(&report.join("property.sarif"), &findings)?;
                        }
                        let replay = Some(crate::equivalence::Replay { by: "jvm".into(), reproduced: false });
                        return Ok(Outcome { verdict: Verdict::Unverifiable, target: options.target.clone(), domain: Some(domain), assume: options.assume.clone(), assert: Some(assertion), throws: options.throws.clone(), throws_checked, counterexample, proof, problem: Some(p), statement: Some(statement), findings, output: out, work, vacuous: None, stated: Some(stated(Some(&last), search.as_ref(), false)), search, replay, advice: None, refused: None });
                    }
                    Ok(run) => jvm_note = Some((false, format!("not confirmed on a JVM, where the harness threw {}", match run.check { crate::jvm_witness::Check::Threw(c) => c, _ => unreachable!() }))),
                    Err(e) => jvm_note = Some((false, format!("not run on a JVM: {e}"))),
                }
            }
            let (mut outcome, returned, result_array, arrays_after, thrown) = (replayed.with_leftovers(&flat, &arguments), replayed.returned, &replayed.result_array, &replayed.arrays_after, &replayed.thrown);
            // What a throws clause required of this input, when that is what failed.
            let expected = match (applying(&arguments), thrown) {
                (Some(i), _) => Some(format!("throws {}, since {}", harness.signals[i].0.java_name(), harness.signals[i].0.when)),
                (None, Some(_)) if !harness.signals.is_empty() => Some("a normal return: no throws clause applies to this input".to_string()),
                _ => None,
            };
            // An assertion that cannot be evaluated on the outcome (an index out of bounds) is what failed.
            if let Some(result) = returned.filter(|_| evaluable) {
                if let Err(e) = assertion_on(&arguments, result, result_array, arrays_after) {
                    outcome = format!("{outcome}; the assertion itself cannot be evaluated on it ({e})");
                }
            }
            let (rendered, witnesses) = render(&arguments);
            let (rendered_found, _) = render(&found);
            let expected_line = expected.as_ref().map(|e| format!("\n    expected: {e}")).unwrap_or_default();
            let claimed = if claim == "returns" { "returns".to_string() } else { format!("`{assertion}`") };
            let message = format!("Property of {} violated: {claimed}{where_}{and_throws}:\n  {rendered}\n    outcome: {outcome}{expected_line}", options.target);
            let _ = writeln!(out, "✗ {message}");
            let stage = last.stage.as_deref().map(|s| format!(" searching inputs in {s}")).unwrap_or_default();
            let shrinking = if shrunk {
                format!(" as {rendered_found}, shrunk to the input above in {shrink_runs} interpreter runs")
            } else {
                String::new()
            };
            let replayed_by = match (&on_jvm, &jvm_note) {
                (Some(jdk), _) => crate::equivalence::run_on_jvm_words(jdk, contracted),
                (None, Some((_, note))) => format!("replayed in the interpreter {note}"),
                (None, None) => "replayed in the interpreter".into(),
            };
            let how = format!("found by {} in {seconds:.1} s{stage}{shrinking}, {replayed_by}; domain {domain}", last.version);
            let _ = writeln!(out, "  ({how})");
            findings.push(Finding::new("property-violated", message, uri.clone(), line));
            proof = Some(how);
            replay = Some(match (&on_jvm, &jvm_note) {
                (Some(_), _) | (None, Some((true, _))) => crate::equivalence::Replay { by: "jvm".into(), reproduced: true },
                (None, _) => crate::equivalence::Replay { by: "interpreter".into(), reproduced: evaluable || in_harness == Some(true) },
            });
            let target = witness::Target { class_internal: &class_internal, method: &method_name, descriptor: &method.descriptor, is_static: method.is_static(), classes: "after" };
            let call = witness::typed_call(&target, &layout, &arguments, false, &[]);
            let inputs = witness::typed_inputs(&flat, &arguments);
            let found_inputs = shrunk.then(|| witness::typed_inputs(&flat, &found));
            counterexample = Some(Counterexample { input: rendered, outcome, expected, values: witnesses, found: shrunk.then_some(rendered_found), shrink_runs, inputs, found_inputs, call });
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
        sarif::write(&report.join("property.sarif"), &findings)?;
    }
    if verdict == Verdict::Violation {
        let _ = writeln!(out, "\nThe input above is a concrete witness: run the method on it. If the property is meant to hold on fewer inputs, narrow it with --assume; the assumption is what a reviewer approves.{}", if signals.is_empty() { " If the method throws there by design, declare it with --throws." } else { "" });
    }
    let mut stated = stated(Some(&last), search.as_ref(), verdict == Verdict::Verified);
    stated.vacuity = vacuity_status.filter(|_| verdict == Verdict::Verified);
    let stated = Some(stated);
    Ok(Outcome {
        verdict,
        target: options.target.clone(),
        domain: Some(domain),
        assume: options.assume.clone(),
        assert: Some(assertion),
        throws: options.throws.clone(),
        throws_checked,
        counterexample,
        proof,
        problem,
        statement: Some(statement),
        findings,
        output: out,
        work,
        vacuous,
        search,
        replay,
        stated,
        advice: None,
        refused: None,
    })
}


const NOT_JBMC_DOMAIN: &str = "note: the domain lets an array parameter be null or one array with another, which JBMC is not given, so JBMC is not asked";

/// The own checker's [`crate::bmc::Parameters`] for `--nullable` and `--may-alias`, and the groups of parameters
/// that may be one array, by name in parameter order: each name an array parameter, and the two of a pair of the
/// same type and different.
fn parameter_domain(params: &[harness::Param], nullable: &[String], may_alias: &[(String, String)]) -> Result<(crate::bmc::Parameters, Vec<Vec<String>>), String> {
    let array = |name: &str, flag: &str| -> Result<&harness::Param, String> {
        match params.iter().find(|p| p.name == name) {
            Some(p) if matches!(p.ty, Type::Array(_)) => Ok(p),
            Some(p) => Err(format!("{flag} {name}: {name} is a {}, and only an array parameter may be null or one array with another", p.ty.java_name())),
            None => Err(format!("{flag} {name}: no parameter is named {name}; the parameters are {}", params.iter().map(|p| p.name.as_str()).collect::<Vec<_>>().join(", "))),
        }
    };
    let mut out = crate::bmc::Parameters::default();
    for name in nullable {
        let p = array(name, "--nullable")?;
        if !out.nullable.contains(&u32::from(p.slot)) {
            out.nullable.push(u32::from(p.slot));
        }
    }
    // Groups, merged pair by pair.
    let mut groups: Vec<Vec<u16>> = Vec::new();
    for (a, b) in may_alias {
        let (pa, pb) = (array(a, "--may-alias")?, array(b, "--may-alias")?);
        if pa.slot == pb.slot {
            return Err(format!("--may-alias {a},{b}: name two different parameters"));
        }
        if pa.ty != pb.ty {
            return Err(format!("--may-alias {a},{b}: a {} and a {} are never one array", pa.ty.java_name(), pb.ty.java_name()));
        }
        let joined: Vec<u16> = groups.iter().filter(|g| g.contains(&pa.slot) || g.contains(&pb.slot)).flatten().copied().chain([pa.slot, pb.slot]).collect();
        groups.retain(|g| !g.contains(&pa.slot) && !g.contains(&pb.slot));
        let mut group: Vec<u16> = joined;
        group.sort_unstable();
        group.dedup();
        groups.push(group);
    }
    groups.sort();
    out.may_alias = groups.iter().map(|g| g.iter().map(|s| u32::from(*s)).collect()).collect();
    let named = groups.iter().map(|g| g.iter().map(|s| params.iter().find(|p| p.slot == *s).expect("a parameter").name.clone()).collect()).collect();
    Ok((out, named))
}

/// What the interpreter made of a witness of JBMC's that refutes a proof of the own checker's, which shares its
/// models: evidence for a person, not a verdict.
pub(crate) fn reproduced_words(reproduced: Option<bool>) -> &'static str {
    match reproduced {
        Some(true) => "where the harness fails too (the interpreter shares the own checker's models, so this settles nothing)",
        Some(false) => "where the harness holds, as the own checker says",
        None => "where the interpreter cannot run the harness",
    }
}

/// The file of a module's properties, next to its other contracts.
pub const FILE_NAME: &str = "properties.contract";

/// One property as declared in a properties file.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Declaration {
    pub target: String,
    pub assume: Option<String>,
    pub assert: Option<String>,
    /// `throws:` lines, `<exception class> when <condition>`, in order.
    pub throws: Vec<String>,
    /// `arrays:` the longest array an array parameter is given for this property, overriding the command line.
    pub max_array_length: Option<u32>,
    /// `unwind:` the loop unwinding bound for this property, overriding the command line: the bound a sort of
    /// four elements needs is five, and what the solver does with the sixteen the default unwinds is paid for.
    pub unwind: Option<u32>,
}

/// Reads a properties file: blocks of a target line (`pkg.Class#method`) followed by indented `assume:`,
/// `assert:`, `throws:`, `arrays:` and `unwind:` lines; `#` comments and `key: value` headers are skipped.
pub fn parse_declarations(text: &str, origin: &str) -> Result<Vec<Declaration>, Error> {
    let mut out: Vec<Declaration> = Vec::new();
    for (number, raw) in text.lines().enumerate() {
        let line = raw.trim_end();
        if line.trim().is_empty() || line.trim_start().starts_with('#') {
            continue;
        }
        let indented = line.starts_with(' ') || line.starts_with('\t');
        let body = line.trim();
        if !indented {
            if body.contains('#') && !body.contains(':') {
                out.push(Declaration { target: body.to_string(), assume: None, assert: None, throws: Vec::new(), max_array_length: None, unwind: None });
                continue;
            }
            if body.split_once(':').is_some() {
                continue; // a header such as `kind: properties`
            }
            return Err(Error::new(format!("{origin}:{}: expected a target `pkg.Class#method`, found {body:?}", number + 1)));
        }
        let Some(last) = out.last_mut() else {
            return Err(Error::new(format!("{origin}:{}: {body:?} belongs to no target", number + 1)));
        };
        match body.split_once(':') {
            Some(("assume", value)) => last.assume = Some(value.trim().to_string()),
            Some(("assert", value)) => last.assert = Some(value.trim().to_string()),
            Some(("throws", value)) => {
                Signal::parse(value).map_err(|e| Error::new(format!("{origin}:{}: {e}", number + 1)))?;
                last.throws.push(value.trim().to_string());
            }
            Some(("arrays", value)) => {
                last.max_array_length = Some(value.trim().parse().map_err(|_| Error::new(format!("{origin}:{}: `arrays:` needs a number of elements, found {:?}", number + 1, value.trim())))?)
            }
            Some(("unwind", value)) => last.unwind = Some(value.trim().parse().map_err(|_| Error::new(format!("{origin}:{}: `unwind:` needs a number of loop iterations, found {:?}", number + 1, value.trim())))?),
            _ => return Err(Error::new(format!("{origin}:{}: expected `assume:`, `assert:`, `throws:`, `arrays:` or `unwind:`, found {body:?}", number + 1))),
        }
    }
    Ok(out)
}

pub fn read_declarations(file: &std::path::Path) -> Result<Vec<Declaration>, Error> {
    let text = std::fs::read_to_string(file).map_err(|e| Error::new(format!("{}: {e}", file.display())))?;
    parse_declarations(&text, &file.display().to_string())
}

/// Copies the declared exceptions that are JDK classes, and their superclasses up to one JBMC has a model of,
/// out of the JDK image into `dir`.
fn extract_exception_classes(dir: &std::path::Path, cp: &ClassPath, signals: &[Signal]) -> Result<(), Error> {
    let names: Vec<String> = signals.iter().map(|s| s.class.clone()).collect();
    extract_exceptions(dir, cp, &names)
}

/// Each JDK exception class of `names` that JBMC has no model of and the harness does not catch by name, with its
/// superclasses up to one JBMC models, taken from the JDK image into `dir`: JBMC matches a handler by class, so
/// a class it has no bytecode for is no `Throwable` to it.
pub(crate) fn extract_exceptions(dir: &std::path::Path, cp: &ClassPath, names: &[String]) -> Result<(), Error> {
    const MODELLED: &[&str] = &["java/lang/Object", "java/lang/Throwable", "java/lang/Exception", "java/lang/Error", "java/lang/RuntimeException"];
    let mut done = std::collections::HashSet::new();
    for class in names {
        let mut current = Some(class.clone());
        while let Some(name) = current {
            if MODELLED.contains(&name.as_str()) || harness::EXCEPTIONS.contains(&name.as_str()) || cp.is_application(&name) || !done.insert(name.clone()) {
                break;
            }
            let bytes = cp.jdk().and_then(|jdk| jdk.read_class(&name).ok().flatten()).ok_or_else(|| Error::new(format!("{} is not in the JDK image; JBMC will treat it as an unknown class", name.replace('/', "."))))?;
            let target = dir.join(format!("{name}.class"));
            if let Some(parent) = target.parent() {
                std::fs::create_dir_all(parent)?;
            }
            std::fs::write(target, bytes)?;
            current = cp.superclass(&name);
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_a_properties_file() {
        let text = "# Property contract\nkind: properties\nmodule: quorum\n\nnet.example.Quorum#majority\n  assume: n > 0\n  assert: 2L * result > n\n  arrays: 4\n  unwind: 5\n\nnet.example.Laws#holds\n";
        let declarations = parse_declarations(text, "properties.contract").unwrap();
        assert_eq!(declarations.len(), 2);
        assert_eq!(declarations[0].target, "net.example.Quorum#majority");
        assert_eq!(declarations[0].assume.as_deref(), Some("n > 0"));
        assert_eq!(declarations[0].assert.as_deref(), Some("2L * result > n"));
        assert_eq!(declarations[0].max_array_length, Some(4));
        assert_eq!(declarations[0].unwind, Some(5));
        assert_eq!(declarations[1], Declaration { target: "net.example.Laws#holds".into(), assume: None, assert: None, throws: Vec::new(), max_array_length: None, unwind: None });
        assert!(parse_declarations("net.example.A#b\n  unwind: many\n", "f").is_err(), "a number");
        let signals = parse_declarations("net.example.A#div\n  throws: java.lang.ArithmeticException when b == 0\n  throws: IllegalArgumentException when a < 0\n", "f").unwrap();
        assert_eq!(signals[0].throws, vec!["java.lang.ArithmeticException when b == 0".to_string(), "IllegalArgumentException when a < 0".to_string()]);
        assert!(parse_declarations("net.example.A#b\n  throws: ArithmeticException\n", "f").is_err(), "a throws clause needs a condition");
        assert!(parse_declarations("  assume: x > 0\n", "f").is_err(), "no target");
        assert!(parse_declarations("net.example.A#b\n  require: x\n", "f").is_err(), "unknown key");
        assert!(parse_declarations("net.example.A#b\n  arrays: many\n", "f").is_err(), "not a number");
    }
}
