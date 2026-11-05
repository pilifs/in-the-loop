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
use crate::equivalence::{extract_jdk_classes, STAGES};
use crate::harness::{self, Signal};
use crate::interp::Value;
use crate::jbmc::{self, Argument, JbmcRun};
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
    /// Which checker proves the harness: JBMC (the default), the tool's own ([`crate::bmc`]), or the tool's own
    /// where the harness is within its fragment and JBMC elsewhere.
    pub engine: crate::Engine,
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
            engine: crate::Engine::Jbmc,
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
}

/// Runs the property proof.
pub fn run(options: &Options) -> Result<Outcome, Error> {
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
        })
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
    if !method.is_static() {
        return refuse(&mut out, line, "only static methods are supported".into());
    }
    let descriptor = method.parsed_descriptor()?;
    let names = method.parameter_names(&class.pool);
    for (name, t) in names.iter().zip(&descriptor.params) {
        if !t.is_primitive() && harness::expr::element_ty(t).is_none() {
            return refuse(&mut out, line, format!("parameter {name} has type {}; the symbolic verifier handles primitive parameters and arrays of integral or boolean elements. Finite types (enums, booleans, records) are covered by behavioural contracts.", t.java_name()));
        }
    }
    let params = harness::params(&names, &descriptor.params);
    let has_arrays = params.iter().any(|p| matches!(p.ty, Type::Array(_)));
    let domain = params
        .iter()
        .map(|p| match p.ty {
            Type::Array(_) => format!("{}: {} of length ≤ {}", p.name, p.ty.java_name(), options.max_array_length),
            _ => format!("{}: {}", p.name, p.ty.java_name()),
        })
        .collect::<Vec<_>>()
        .join(" × ");

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
    let harness = match harness::generate_property(&class_internal, &method_name, &params, &descriptor.ret, options.assume.as_deref(), options.assert.as_deref(), &signals, options.max_array_length) {
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
    let mut last = None;
    // The tool's own checker first, when asked: its verdict stands, and where it has none, JBMC's turn (under
    // `auto`), or that is the answer (under `native`).
    let mut stages: &[Option<&str>] = STAGES;
    let mut fallback = None;
    if options.engine != crate::Engine::Jbmc {
        let entries: Vec<PathBuf> = classpath.iter().filter(|p| **p != jdk_dir && **p != models_dir).cloned().collect();
        let result = crate::bmc::run_for_proof(&entries, options.models, harness::PROPERTY_CLASS, harness::METHOD, options.unwind, options.max_array_length, Duration::from_secs(options.timeout_seconds), &work)?;
        if result.verdict != Verdict::Unverifiable || options.engine == crate::Engine::Native {
            stages = &[];
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
    for stage in stages {
        let run = JbmcRun {
            executable: options.jbmc.clone(),
            class: harness::PROPERTY_CLASS.into(),
            function: harness::METHOD.into(),
            classpath: classpath.clone(),
            unwind: options.unwind,
            timeout: Duration::from_secs(options.timeout_seconds),
            stage: stage.map(str::to_string),
            refine_strings: options.refine_strings,
            sat_solver: options.sat_solver.clone(),
            log: work.join(format!("jbmc{}.log", stage.map(|s| format!("-{}", s.replace(|c: char| !c.is_ascii_digit() && c != '-', "_"))).unwrap_or_default())),
            extra_args: extra_args.clone(),
        };
        let result = jbmc::run(&run)?;
        let stop = result.verdict != Verdict::Verified;
        last = Some(result);
        if stop {
            break;
        }
    }
    let last = last.expect("at least one stage");
    let seconds = started.elapsed().as_secs_f64();
    let search = Some(crate::equivalence::Search {
        engine: if last.native.is_some() { "native" } else { "jbmc" }.into(),
        checker: last.version.clone(),
        seconds,
        properties: last.properties,
        unwind: options.unwind,
        max_array_length: options.max_array_length,
        stage: last.stage.clone(),
        fallback,
        native: last.native.clone(),
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
    let mut verdict = last.verdict;
    match last.verdict {
        Verdict::Verified => {
            let how = format!("{}: {} properties proved over {domain} in {seconds:.1} s; loops unwound {} times with unwinding assertions", last.version, last.properties, options.unwind);
            let _ = writeln!(out, "✓ {} {claim} on every input{where_}{and_throws} ({how})", options.target);
            proof = Some(how);
            // An assumption may admit no input in the domain: the property is then checked on none.
            if !harness.probe.is_empty() {
                let mut entries = options.classes.clone();
                entries.extend(options.classpath.iter().cloned());
                vacuous = crate::equivalence::vacuity(&mut out, &harness.probe, harness::PROPERTY_CLASS, &entries, options.models, options.unwind, options.max_array_length, Duration::from_secs(options.timeout_seconds), &work, "failing the assumption (--assume)")?;
                if let Some(reason) = &vacuous {
                    let _ = writeln!(out, "  vacuously: {reason}");
                }
            }
        }
        Verdict::Violation => {
            let found = last.arguments(&descriptor.params)?;
            let replay_cp = witness::classpath(options.classes.iter().chain(&options.classpath).map(PathBuf::as_path))?.with_models(options.models);
            let replayed = witness::replay(&replay_cp, &class_internal, &method_name, &method.descriptor, &descriptor, &found);
            // The throws clause that applies to an input: the first whose condition holds; `None` when none does
            // or a condition cannot be evaluated outside the harness (it calls the method).
            let applying = |arguments: &[Argument]| -> Option<usize> {
                let mut locals = Vec::new();
                let mut arrays = Vec::new();
                for (a, p) in arguments.iter().zip(&params) {
                    match a {
                        Argument::Scalar(v) => {
                            locals.push(*v);
                            if v.is_wide() {
                                locals.push(Value::Int(0));
                            }
                        }
                        Argument::Array(data) => {
                            locals.push(Value::Null);
                            arrays.push((p.slot, data.clone()));
                        }
                        Argument::Null => locals.push(Value::Null),
                    }
                }
                harness.signals.iter().position(|(_, when)| matches!(harness::expr::eval_with(when, &locals, &arrays), Ok(Value::Int(1))))
            };
            // A counterexample on which the interpreter finds the property holding is no counterexample: JBMC has
            // given an arbitrary result to a method it had no bytecode for. (A property that calls the method
            // under proof is checked in the harness only, so it is taken at JBMC's word.) The assertion reads an
            // array parameter after the call, as the harness does, so a method that writes into it is held to
            // what it wrote.
            let assertion_on = |arguments: &[Argument], result: Value, result_array: &Option<Vec<Value>>, arrays_after: &[(u16, Vec<Value>)]| -> Result<Value, Error> {
                let mut locals = Vec::new();
                let mut arrays = Vec::new();
                for (a, p) in arguments.iter().zip(&params) {
                    match a {
                        Argument::Scalar(v) => {
                            locals.push(*v);
                            if v.is_wide() {
                                locals.push(Value::Int(0));
                            }
                        }
                        Argument::Array(data) => {
                            locals.push(Value::Null);
                            let after = arrays_after.iter().find(|(slot, _)| *slot == p.slot).map(|(_, d)| d.clone());
                            arrays.push((p.slot, after.unwrap_or_else(|| data.clone())));
                            // What \old(a) reads: the array as the call received it.
                            if let Some((_, copy)) = harness.old.iter().find(|(slot, _)| *slot == p.slot) {
                                arrays.push((*copy, data.clone()));
                            }
                        }
                        Argument::Null => locals.push(Value::Null),
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
            let evaluable = !harness.assertion.has_call() && harness.signals.iter().all(|(_, when)| !when.has_call());
            let holds_on_found = match (applying(&found), replayed.returned, replayed.thrown.as_deref()) {
                (Some(i), _, Some(thrown)) => cp.is_subtype(thrown, &harness.signals[i].0.class),
                (Some(_), _, None) => false,
                (None, Some(result), _) => matches!(assertion_on(&found, result, &replayed.result_array, &replayed.arrays_after), Ok(Value::Int(1))),
                (None, None, _) => false,
            };
            if evaluable && holds_on_found {
                let (rendered, _) = witness::call(&method_name, &params, &found);
                let did = if replayed.thrown.is_some() { replayed.outcome.clone() } else { format!("returns {}", replayed.outcome) };
                let p = format!("JBMC's counterexample {rendered} does not reproduce: the method {did} in the interpreter and the property holds on it. A method the target calls is probably missing from JBMC's class path (its models cover little of the JDK beyond java.lang.Math and the integer wrappers) and was treated as returning an arbitrary value");
                let message = format!("{} cannot be verified: {p}", options.target);
                let _ = writeln!(out, "✗ {message}");
                findings.push(Finding::new("unverifiable", message, uri.clone(), line));
                problem = Some(p);
                verdict = Verdict::Unverifiable;
                if let Some(report) = &options.report {
                    sarif::write(&report.join("property.sarif"), &findings)?;
                }
                let replay = Some(crate::equivalence::Replay { by: "interpreter".into(), reproduced: false });
                return Ok(Outcome { verdict, target: options.target.clone(), domain: Some(domain), assume: options.assume.clone(), assert: Some(assertion), throws: options.throws.clone(), throws_checked, counterexample, proof, problem, statement: Some(statement), findings, output: out, work, vacuous: None, search, replay });
            }
            // Shrink the witness: the harness class JBMC checked, run in the interpreter on smaller inputs.
            let mut shrink_runs = 0;
            let mut arguments = found.clone();
            if options.shrink {
                let harness_cp = witness::classpath(std::iter::once(harness_dir.as_path()).chain(options.classes.iter().chain(&options.classpath).map(PathBuf::as_path)))?.with_models(options.models);
                let shrunk = witness::shrink_in_harness(&harness_cp, harness::PROPERTY_CLASS, &descriptor.params, found.clone());
                shrink_runs = shrunk.runs;
                arguments = shrunk.arguments;
            }
            let shrunk = arguments != found;
            let replayed = if shrunk { witness::replay(&replay_cp, &class_internal, &method_name, &method.descriptor, &descriptor, &arguments) } else { replayed };
            let (mut outcome, returned, result_array, arrays_after, thrown) = (replayed.with_leftovers(&params, &arguments), replayed.returned, &replayed.result_array, &replayed.arrays_after, &replayed.thrown);
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
            let (rendered, witnesses) = witness::call(&method_name, &params, &arguments);
            let (rendered_found, _) = witness::call(&method_name, &params, &found);
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
            let how = format!("found by {} in {seconds:.1} s{stage}{shrinking}, replayed in the interpreter; domain {domain}", last.version);
            let _ = writeln!(out, "  ({how})");
            findings.push(Finding::new("property-violated", message, uri.clone(), line));
            proof = Some(how);
            replay = Some(crate::equivalence::Replay { by: "interpreter".into(), reproduced: evaluable });
            let target = witness::Target { class_internal: &class_internal, method: &method_name, descriptor: &method.descriptor, is_static: method.is_static(), classes: "after" };
            let names: Vec<String> = params.iter().map(|p| p.name.clone()).collect();
            let call = witness::typed_call(&target, &harness::Layout::plain(&names, &descriptor.params), &arguments, false, &[]);
            let inputs = witness::typed_inputs(&params, &arguments);
            let found_inputs = shrunk.then(|| witness::typed_inputs(&params, &found));
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
    })
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
    const MODELLED: &[&str] = &["java/lang/Object", "java/lang/Throwable", "java/lang/Exception", "java/lang/Error", "java/lang/RuntimeException"];
    let mut done = std::collections::HashSet::new();
    for signal in signals {
        let mut current = Some(signal.class.clone());
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
