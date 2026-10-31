//! Regression verification: proves that a method behaves exactly as its previous version on every input, or shows
//! an input where it does not. This is the contract check for methods whose inputs are not finite, such as a
//! `long` price and an `int` seat count, where running every input is impossible.
//!
//! The statement is "for all inputs, old(x) and new(x) return the same value or throw the same exception",
//! optionally restricted to the inputs the developer did *not* mean to change. It is proved by bounded model
//! checking of the bytecode with JBMC: both versions are compiled into one program (the old one relocated into a
//! `before` package by [`crate::relocate`]), a generated harness asserts the statement ([`crate::harness`]), and
//! JBMC turns the harness into a satisfiability problem whose unsatisfiability is the proof. A satisfying
//! assignment is a concrete counterexample, which this module replays in the interpreter to show the two outcomes.

use std::fmt::Write as _;
use std::path::{Path, PathBuf};
use std::time::Duration;

use serde::Serialize;

use crate::classfile::Type;
use crate::classpath::ClassPath;
use crate::harness;
use crate::interp::{render, Fault, Machine, Value};
use crate::jbmc::{self, JbmcRun};
use crate::sarif::{self, Finding};
use crate::{Error, Verdict};

/// JDK classes whose real bytecode JBMC analyses, instead of the small models it ships.
pub const JDK_CLASSES: &[&str] = &["java/lang/Math", "java/lang/StrictMath"];

/// Searched first, so that a counterexample is small enough to read; the last stage is the proof over all inputs.
pub const STAGES: &[Option<&str>] = &[Some("[0:20]"), Some("[-100000:100000]"), None];

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
    pub timeout_seconds: u64,
    pub jbmc: String,
    /// The JDK to take `java.lang.Math` from; found through `JAVA_HOME`/`PATH` when `None`.
    pub java_home: Option<PathBuf>,
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
            timeout_seconds: 600,
            jbmc: "jbmc".into(),
            java_home: None,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct Counterexample {
    /// `totalCents(priceCents=5, seats=7)`.
    pub input: String,
    pub before: String,
    pub after: String,
    /// The raw argument values, in parameter order.
    pub values: Vec<String>,
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
}

/// Runs the regression proof.
pub fn run(options: &Options) -> Result<Outcome, Error> {
    let work = match &options.work {
        Some(w) => w.clone(),
        None => {
            let nanos = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_nanos()).unwrap_or(0);
            std::env::temp_dir().join(format!("jvmcontract-equivalence-{}-{nanos}", std::process::id()))
        }
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
        Ok(Outcome { verdict: Verdict::Unverifiable, target: options.target.clone(), domain: None, counterexample: None, proof: None, problem: Some(problem), statement: None, findings, output: out.clone(), work: work.clone() })
    };

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
    let candidates: Vec<_> = class.methods.iter().filter(|m| m.name == method_name && !m.is_synthetic() && !m.is_bridge()).collect();
    if candidates.len() != 1 {
        return refuse(&mut out, 1, format!("expected one method named {method_name}, found {}", candidates.len()));
    }
    let method = candidates[0].clone();
    let line = method.first_line().map(u32::from).unwrap_or(1);
    if !method.is_static() {
        return refuse(&mut out, line, "only static methods are supported".into());
    }
    let descriptor = method.parsed_descriptor()?;
    let names = method.parameter_names(&class.pool);
    for (name, t) in names.iter().zip(&descriptor.params) {
        if !t.is_primitive() {
            return refuse(&mut out, line, format!("parameter {name} has type {}; the symbolic verifier handles primitive parameters only. Finite types (enums, booleans, records) are covered by behavioural contracts.", t.java_name()));
        }
    }
    let params = harness::params(&names, &descriptor.params);
    let domain = params.iter().map(|p| format!("{}: {}", p.name, p.ty.java_name())).collect::<Vec<_>>().join(" × ");

    // 3. The statement, as a harness JBMC can check.
    let harness = match harness::generate(&class_internal, &method_name, &params, &descriptor.ret, options.unchanged_unless.as_deref()) {
        Ok(h) => h,
        Err(e) => return refuse(&mut out, line, format!("the scope is not a boolean expression over the parameters: {e}")),
    };
    let harness_dir = work.join("harness");
    std::fs::create_dir_all(&harness_dir)?;
    std::fs::write(harness_dir.join(format!("{}.class", harness::CLASS)), &harness.bytes)?;
    let statement = harness_dir.join(format!("{}.java", harness::CLASS));
    std::fs::write(&statement, &harness.source)?;

    // 4. The JDK bytecode JBMC needs beyond its own models.
    let jdk_dir = work.join("jdk");
    if let Err(e) = extract_jdk_classes(&jdk_dir, options.java_home.as_deref()) {
        let _ = writeln!(out, "note: {e}; JBMC will use its own models of java.lang.Math");
    }

    // 5. Prove, or search for a counterexample: small inputs first, then all of them.
    let mut classpath = vec![harness_dir.clone(), options.after.clone(), before_dir.clone(), jdk_dir.clone()];
    classpath.extend(options.classpath.iter().cloned());
    let started = std::time::Instant::now();
    let mut last = None;
    for stage in STAGES {
        let run = JbmcRun {
            executable: options.jbmc.clone(),
            class: harness::CLASS.into(),
            function: harness::METHOD.into(),
            classpath: classpath.clone(),
            unwind: options.unwind,
            timeout: Duration::from_secs(options.timeout_seconds),
            stage: stage.map(str::to_string),
            log: work.join(format!("jbmc{}.log", stage.map(|s| format!("-{}", s.replace(|c: char| !c.is_ascii_digit() && c != '-', "_"))).unwrap_or_default())),
            extra_args: Vec::new(),
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
    let restriction = options.unchanged_unless.as_deref().map(|s| format!(" where !({s})")).unwrap_or_default();

    let mut findings = Vec::new();
    let mut counterexample = None;
    let mut proof = None;
    let mut problem = None;
    match last.verdict {
        Verdict::Verified => {
            let how = format!("{}: {} properties proved over {domain} in {seconds:.1} s; loops unwound {} times with unwinding assertions", last.version, last.properties, options.unwind);
            let _ = writeln!(out, "✓ {} behaves as before on every input{restriction} ({how})", options.target);
            proof = Some(how);
        }
        Verdict::Violation => {
            let values = last.inputs(&descriptor.params)?;
            let (before_outcome, after_outcome) = replay(options, &before_dir, &class_internal, &method_name, &method.descriptor, &descriptor.ret, &values)?;
            let rendered = format!("{method_name}({})", params.iter().zip(&values).map(|(p, v)| format!("{}={}", p.name, render::primitive(*v, &p.ty))).collect::<Vec<_>>().join(", "));
            let message = format!(
                "Behaviour of {} changed{}:\n  {rendered}\n    before: {before_outcome}\n    after:  {after_outcome}",
                options.target,
                options.unchanged_unless.as_deref().map(|s| format!(" outside the intended inputs ({s})")).unwrap_or_default()
            );
            let _ = writeln!(out, "✗ {message}");
            let how = format!("found by {} in {seconds:.1} s{}, replayed in the interpreter; domain {domain}", last.version, last.stage.as_deref().map(|s| format!(" searching inputs in {s}")).unwrap_or_default());
            let _ = writeln!(out, "  ({how})");
            if let Some(scope) = &harness.scope {
                let mut locals = Vec::new();
                for v in &values {
                    locals.push(*v);
                    if v.is_wide() {
                        locals.push(Value::Int(0));
                    }
                }
                if let Ok(Value::Int(1)) = harness::expr::eval(scope, &locals) {
                    let _ = writeln!(out, "  (note: the interpreter evaluates the scope expression as true on this input, which the harness should have skipped; check the expression)");
                }
            }
            findings.push(Finding::new("behaviour-changed", message, uri.clone(), line));
            proof = Some(how);
            counterexample = Some(Counterexample { input: rendered, before: before_outcome, after: after_outcome, values: values.iter().zip(&params).map(|(v, p)| render::primitive(*v, &p.ty)).collect() });
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
    if last.verdict == Verdict::Violation {
        let _ = writeln!(out, "\nIf the change is intended, say for which inputs with --unchanged-unless, and the verifier proves that nothing else changed. The expression is what a reviewer approves.");
    }
    Ok(Outcome { verdict: last.verdict, target: options.target.clone(), domain: Some(domain), counterexample, proof, problem, statement: Some(statement), findings, output: out, work })
}

/// Runs the counterexample through both versions in the interpreter, with the effect monitor off.
fn replay(options: &Options, before_dir: &Path, class_internal: &str, method: &str, descriptor: &str, ret: &Type, values: &[Value]) -> Result<(String, String), Error> {
    let mut cp = ClassPath::new();
    cp.add(&options.after)?;
    cp.add(before_dir)?;
    for entry in &options.classpath {
        if entry.exists() {
            cp.add(entry)?;
        }
    }
    let cp = cp.with_default_jdk();
    let mut m = Machine::new(&cp);
    m.monitor = false;
    let mut outcomes = Vec::new();
    for owner in [format!("before/{class_internal}"), class_internal.to_string()] {
        let _ = m.begin_case();
        let outcome = match m.call_static(&owner, method, descriptor, values.to_vec()) {
            Ok(Some(v)) => render::value(&mut m, v, ret).unwrap_or_else(|f| render::fault(&m, &f)),
            Ok(None) => "void".to_string(),
            Err(Fault::Throw(r)) => render::thrown(&m, r),
            Err(f) => format!("<could not replay: {}>", render::fault(&m, &f)),
        };
        outcomes.push(outcome);
    }
    Ok((outcomes.remove(0), outcomes.remove(0)))
}

/// Copies the JDK classes in [`JDK_CLASSES`] out of the JDK image, for JBMC's class path.
pub fn extract_jdk_classes(dir: &Path, java_home: Option<&Path>) -> Result<(), Error> {
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
