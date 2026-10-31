//! Property proofs: a statement about one method on every input, proved by bounded model checking or refuted with
//! a concrete input. Where a regression proof ([`crate::equivalence`]) compares two versions, a property proof
//! checks one version against what the developer says it guarantees: a postcondition such as
//! `result >= baseMillis && result <= capMillis`, or a law such as `result == merge(b, a)`.
//!
//! The statement is "for all inputs where `assume` holds, the method returns without throwing and `assert` holds".
//! It is the theorem a property-based test states and samples; here the solver covers every input. The harness is
//! generated as bytecode ([`crate::harness::generate_property`]), JBMC turns it into a satisfiability problem, and a
//! satisfying assignment is replayed in the interpreter to show the outcome that violates the property.

use std::fmt::Write as _;
use std::path::PathBuf;
use std::time::Duration;

use serde::Serialize;

use crate::classfile::Type;
use crate::classpath::ClassPath;
use crate::equivalence::{extract_jdk_classes, STAGES};
use crate::harness;
use crate::interp::{render, Fault, Machine, Value};
use crate::jbmc::{self, JbmcRun};
use crate::sarif::{self, Finding};
use crate::{Error, Verdict};

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
    pub work: Option<PathBuf>,
    pub report: Option<PathBuf>,
    pub sources: Vec<PathBuf>,
    pub base: PathBuf,
    pub unwind: u32,
    pub timeout_seconds: u64,
    pub jbmc: String,
    pub java_home: Option<PathBuf>,
}

impl Options {
    pub fn new(classes: &[PathBuf], target: &str) -> Options {
        Options {
            classes: classes.to_vec(),
            classpath: Vec::new(),
            target: target.to_string(),
            assume: None,
            assert: None,
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
    /// `delayMillis(attempt=63, baseMillis=1, capMillis=1)`.
    pub input: String,
    /// What the method did: its result, or the exception it threw.
    pub outcome: String,
    pub values: Vec<String>,
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
    pub counterexample: Option<Counterexample>,
    pub proof: Option<String>,
    pub problem: Option<String>,
    pub statement: Option<PathBuf>,
    pub findings: Vec<Finding>,
    pub output: String,
    pub work: PathBuf,
}

/// Runs the property proof.
pub fn run(options: &Options) -> Result<Outcome, Error> {
    let work = match &options.work {
        Some(w) => w.clone(),
        None => {
            let nanos = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_nanos()).unwrap_or(0);
            std::env::temp_dir().join(format!("jvmcontract-property-{}-{nanos}", std::process::id()))
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
            sarif::write(&report.join("property.sarif"), &findings)?;
        }
        Ok(Outcome {
            verdict: Verdict::Unverifiable,
            target: options.target.clone(),
            domain: None,
            assume: options.assume.clone(),
            assert: options.assert.clone(),
            counterexample: None,
            proof: None,
            problem: Some(problem),
            statement: None,
            findings,
            output: out.clone(),
            work: work.clone(),
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

    // 2. The statement.
    let harness = match harness::generate_property(&class_internal, &method_name, &params, &descriptor.ret, options.assume.as_deref(), options.assert.as_deref()) {
        Ok(h) => h,
        Err(e) => return refuse(&mut out, line, format!("the property is not well-formed: {e}")),
    };
    let harness_dir = work.join("harness");
    std::fs::create_dir_all(&harness_dir)?;
    std::fs::write(harness_dir.join(format!("{}.class", harness::PROPERTY_CLASS)), &harness.bytes)?;
    let statement = harness_dir.join(format!("{}.java", harness::PROPERTY_CLASS));
    std::fs::write(&statement, &harness.source)?;
    let assertion = harness.assertion_text.clone();

    // 3. The JDK bytecode JBMC needs beyond its own models.
    let jdk_dir = work.join("jdk");
    if let Err(e) = extract_jdk_classes(&jdk_dir, options.java_home.as_deref()) {
        let _ = writeln!(out, "note: {e}; JBMC will use its own models of java.lang.Math");
    }

    // 4. Prove, or search for a counterexample: small inputs first, then all of them.
    let mut classpath = vec![harness_dir.clone()];
    classpath.extend(options.classes.iter().cloned());
    classpath.push(jdk_dir.clone());
    classpath.extend(options.classpath.iter().cloned());
    let started = std::time::Instant::now();
    let mut last = None;
    for stage in STAGES {
        let run = JbmcRun {
            executable: options.jbmc.clone(),
            class: harness::PROPERTY_CLASS.into(),
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
    let where_ = options.assume.as_deref().map(|a| format!(" where {a}")).unwrap_or_default();

    let mut findings = Vec::new();
    let mut counterexample = None;
    let mut proof = None;
    let mut problem = None;
    match last.verdict {
        Verdict::Verified => {
            let how = format!("{}: {} properties proved over {domain} in {seconds:.1} s; loops unwound {} times with unwinding assertions", last.version, last.properties, options.unwind);
            let _ = writeln!(out, "✓ {} satisfies `{assertion}` on every input{where_} ({how})", options.target);
            proof = Some(how);
        }
        Verdict::Violation => {
            let values = last.inputs(&descriptor.params)?;
            let outcome = replay(options, &class_internal, &method_name, &method.descriptor, &descriptor.ret, &values)?;
            let rendered = format!("{method_name}({})", params.iter().zip(&values).map(|(p, v)| format!("{}={}", p.name, render::primitive(*v, &p.ty))).collect::<Vec<_>>().join(", "));
            let message = format!("Property of {} violated: `{assertion}`{}:\n  {rendered}\n    outcome: {outcome}", options.target, where_);
            let _ = writeln!(out, "✗ {message}");
            let how = format!("found by {} in {seconds:.1} s{}, replayed in the interpreter; domain {domain}", last.version, last.stage.as_deref().map(|s| format!(" searching inputs in {s}")).unwrap_or_default());
            let _ = writeln!(out, "  ({how})");
            findings.push(Finding::new("property-violated", message, uri.clone(), line));
            proof = Some(how);
            counterexample = Some(Counterexample { input: rendered, outcome, values: values.iter().zip(&params).map(|(v, p)| render::primitive(*v, &p.ty)).collect() });
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
    if last.verdict == Verdict::Violation {
        let _ = writeln!(out, "\nThe input above is a concrete witness: run the method on it. If the property is meant to hold on fewer inputs, narrow it with --assume; the assumption is what a reviewer approves.");
    }
    Ok(Outcome {
        verdict: last.verdict,
        target: options.target.clone(),
        domain: Some(domain),
        assume: options.assume.clone(),
        assert: Some(assertion),
        counterexample,
        proof,
        problem,
        statement: Some(statement),
        findings,
        output: out,
        work,
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
}

/// Reads a properties file: blocks of a target line (`pkg.Class#method`) followed by indented `assume:` and
/// `assert:` lines; `#` comments and `key: value` headers are skipped.
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
                out.push(Declaration { target: body.to_string(), assume: None, assert: None });
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
            _ => return Err(Error::new(format!("{origin}:{}: expected `assume:` or `assert:`, found {body:?}", number + 1))),
        }
    }
    Ok(out)
}

pub fn read_declarations(file: &std::path::Path) -> Result<Vec<Declaration>, Error> {
    let text = std::fs::read_to_string(file).map_err(|e| Error::new(format!("{}: {e}", file.display())))?;
    parse_declarations(&text, &file.display().to_string())
}

/// Runs the counterexample through the method in the interpreter, with the effect monitor off.
fn replay(options: &Options, class_internal: &str, method: &str, descriptor: &str, ret: &Type, values: &[Value]) -> Result<String, Error> {
    let mut cp = ClassPath::new();
    for path in options.classes.iter().chain(&options.classpath) {
        if path.exists() {
            cp.add(path)?;
        }
    }
    let cp = cp.with_default_jdk();
    let mut m = Machine::new(&cp);
    m.monitor = false;
    let _ = m.begin_case();
    Ok(match m.call_static(class_internal, method, descriptor, values.to_vec()) {
        Ok(Some(v)) => render::value(&mut m, v, ret).unwrap_or_else(|f| render::fault(&m, &f)),
        Ok(None) => "void".to_string(),
        Err(Fault::Throw(r)) => render::thrown(&m, r),
        Err(f) => format!("<could not replay: {}>", render::fault(&m, &f)),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_a_properties_file() {
        let text = "# Property contract\nkind: properties\nmodule: quorum\n\nnet.example.Quorum#majority\n  assume: n > 0\n  assert: 2L * result > n\n\nnet.example.Laws#holds\n";
        let declarations = parse_declarations(text, "properties.contract").unwrap();
        assert_eq!(declarations.len(), 2);
        assert_eq!(declarations[0].target, "net.example.Quorum#majority");
        assert_eq!(declarations[0].assume.as_deref(), Some("n > 0"));
        assert_eq!(declarations[0].assert.as_deref(), Some("2L * result > n"));
        assert_eq!(declarations[1], Declaration { target: "net.example.Laws#holds".into(), assume: None, assert: None });
        assert!(parse_declarations("  assume: x > 0\n", "f").is_err(), "no target");
        assert!(parse_declarations("net.example.A#b\n  require: x\n", "f").is_err(), "unknown key");
    }
}
