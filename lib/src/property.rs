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
use crate::harness;
use crate::interp::{render, Fault, Machine, Object, Value};
use crate::jbmc::{self, Argument, JbmcRun};
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
    /// The longest array an array parameter is given.
    pub max_array_length: u32,
    /// Whether to shrink a counterexample in the interpreter before reporting it.
    pub shrink: bool,
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
            max_array_length: 8,
            shrink: true,
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
    /// The input as JBMC found it, when `input` is the shrunk one.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub found: Option<String>,
    /// How many smaller inputs the interpreter tried while shrinking.
    pub shrink_runs: u32,
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
    // An array parameter is never null, and is bounded in length: a quantifier over it is a loop the unwinding
    // bound must cover.
    let extra_args = if has_arrays {
        vec!["--java-assume-inputs-non-null".to_string(), "--max-nondet-array-length".to_string(), options.max_array_length.to_string()]
    } else {
        Vec::new()
    };
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
    let where_ = options.assume.as_deref().map(|a| format!(" where {a}")).unwrap_or_default();

    let mut findings = Vec::new();
    let mut counterexample = None;
    let mut proof = None;
    let mut problem = None;
    let mut verdict = last.verdict;
    match last.verdict {
        Verdict::Verified => {
            let how = format!("{}: {} properties proved over {domain} in {seconds:.1} s; loops unwound {} times with unwinding assertions", last.version, last.properties, options.unwind);
            let _ = writeln!(out, "✓ {} satisfies `{assertion}` on every input{where_} ({how})", options.target);
            proof = Some(how);
        }
        Verdict::Violation => {
            let found = last.arguments(&descriptor.params)?;
            let (outcome_found, returned, result_array, arrays_after) = replay(options, &class_internal, &method_name, &method.descriptor, &descriptor, &found)?;
            let render_input = |arguments: &[Argument]| -> (Vec<String>, String) {
                let witnesses: Vec<String> = params.iter().zip(arguments).map(|(p, a)| render_argument(a, &p.ty)).collect();
                let rendered = format!("{method_name}({})", params.iter().zip(&witnesses).map(|(p, w)| format!("{}={w}", p.name)).collect::<Vec<_>>().join(", "));
                (witnesses, rendered)
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
            let evaluable = !harness.assertion.has_call();
            if let Some(result) = returned.filter(|_| evaluable) {
                if let Ok(Value::Int(1)) = assertion_on(&found, result, &result_array, &arrays_after) {
                    let (_, rendered) = render_input(&found);
                    let p = format!("JBMC's counterexample {rendered} does not reproduce: the method returns {outcome_found} in the interpreter and the property holds on it. A method the target calls is probably missing from JBMC's class path (its models cover little of the JDK beyond java.lang.Math and the integer wrappers) and was treated as returning an arbitrary value");
                    let message = format!("{} cannot be verified: {p}", options.target);
                    let _ = writeln!(out, "✗ {message}");
                    findings.push(Finding::new("unverifiable", message, uri.clone(), line));
                    problem = Some(p);
                    verdict = Verdict::Unverifiable;
                    if let Some(report) = &options.report {
                        sarif::write(&report.join("property.sarif"), &findings)?;
                    }
                    return Ok(Outcome { verdict, target: options.target.clone(), domain: Some(domain), assume: options.assume.clone(), assert: Some(assertion), counterexample, proof, problem, statement: Some(statement), findings, output: out, work });
                }
            }
            // Shrink the witness: the harness class JBMC checked, run in the interpreter on smaller inputs.
            let mut shrink_runs = 0;
            let mut arguments = found.clone();
            if options.shrink {
                let shrunk = shrink_in_harness(options, &harness_dir, &descriptor.params, found.clone())?;
                shrink_runs = shrunk.runs;
                arguments = shrunk.arguments;
            }
            let shrunk = arguments != found;
            let (mut outcome, returned, result_array, arrays_after) = if shrunk {
                replay(options, &class_internal, &method_name, &method.descriptor, &descriptor, &arguments)?
            } else {
                (outcome_found, returned, result_array, arrays_after)
            };
            // An assertion that cannot be evaluated on the outcome (an index out of bounds) is what failed.
            if let Some(result) = returned.filter(|_| evaluable) {
                if let Err(e) = assertion_on(&arguments, result, &result_array, &arrays_after) {
                    outcome = format!("{outcome}; the assertion itself cannot be evaluated on it ({e})");
                }
            }
            for (p, a) in params.iter().zip(&arguments) {
                if let (Argument::Array(before), Type::Array(element)) = (a, &p.ty) {
                    if let Some((_, after)) = arrays_after.iter().find(|(slot, after)| *slot == p.slot && after != before) {
                        outcome = format!("{outcome}, leaving {}={}", p.name, render_array(after, element));
                    }
                }
            }
            let (witnesses, rendered) = render_input(&arguments);
            let (_, rendered_found) = render_input(&found);
            let message = format!("Property of {} violated: `{assertion}`{}:\n  {rendered}\n    outcome: {outcome}", options.target, where_);
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
            counterexample = Some(Counterexample { input: rendered, outcome, values: witnesses, found: shrunk.then_some(rendered_found), shrink_runs });
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
        let _ = writeln!(out, "\nThe input above is a concrete witness: run the method on it. If the property is meant to hold on fewer inputs, narrow it with --assume; the assumption is what a reviewer approves.");
    }
    Ok(Outcome {
        verdict,
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
    /// `arrays:` the longest array an array parameter is given for this property, overriding the command line.
    pub max_array_length: Option<u32>,
}

/// Reads a properties file: blocks of a target line (`pkg.Class#method`) followed by indented `assume:`,
/// `assert:` and `arrays:` lines; `#` comments and `key: value` headers are skipped.
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
                out.push(Declaration { target: body.to_string(), assume: None, assert: None, max_array_length: None });
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
            Some(("arrays", value)) => {
                last.max_array_length = Some(value.trim().parse().map_err(|_| Error::new(format!("{origin}:{}: `arrays:` needs a number of elements, found {:?}", number + 1, value.trim())))?)
            }
            _ => return Err(Error::new(format!("{origin}:{}: expected `assume:`, `assert:` or `arrays:`, found {body:?}", number + 1))),
        }
    }
    Ok(out)
}

pub fn read_declarations(file: &std::path::Path) -> Result<Vec<Declaration>, Error> {
    let text = std::fs::read_to_string(file).map_err(|e| Error::new(format!("{}: {e}", file.display())))?;
    parse_declarations(&text, &file.display().to_string())
}

/// A witness argument as Java would write it: `17`, `'a'`, `[3, 5, 8]`, `null`.
fn render_argument(argument: &Argument, t: &Type) -> String {
    match (argument, t) {
        (Argument::Scalar(v), _) => render::witness(*v, t),
        (Argument::Array(data), Type::Array(element)) => render_array(data, element),
        (Argument::Array(_), _) => "<array>".into(),
        (Argument::Null, _) => "null".into(),
    }
}

fn render_array(data: &[Value], element: &Type) -> String {
    format!("[{}]", data.iter().map(|v| render::witness(*v, element)).collect::<Vec<_>>().join(", "))
}

/// The elements of the arrays among `values`, by parameter slot, as they are now.
fn arrays_of(m: &Machine, values: &[Value], signature: &crate::classfile::MethodDescriptor) -> Vec<(u16, Vec<Value>)> {
    let mut out = Vec::new();
    let mut slot = 0;
    for (v, t) in values.iter().zip(&signature.params) {
        if let Value::Ref(r) = v {
            if let Object::Array { data, .. } = m.heap.get(*r) {
                out.push((slot, data.clone()));
            }
        }
        slot += t.slots();
    }
    out
}

/// How many smaller inputs the shrinker may try.
const SHRINK_BUDGET: u32 = 4000;

/// Shrinks a counterexample with the harness as the oracle: the generated class in `harness_dir`, run in the
/// interpreter, violates the property on an input exactly when it throws `AssertionError` on it (the assumption
/// is part of the harness, so an input outside it passes). An input the interpreter cannot run is not accepted.
fn shrink_in_harness(options: &Options, harness_dir: &std::path::Path, types: &[Type], found: Vec<Argument>) -> Result<crate::shrink::Shrunk, Error> {
    let mut cp = ClassPath::new();
    cp.add(harness_dir)?;
    for path in options.classes.iter().chain(&options.classpath) {
        if path.exists() {
            cp.add(path)?;
        }
    }
    let cp = cp.with_default_jdk();
    let mut m = Machine::new(&cp);
    m.monitor = false;
    let check_descriptor = format!("({})V", types.iter().map(Type::descriptor).collect::<String>());
    let mut fails = |arguments: &[Argument]| -> Option<bool> {
        let mark = m.begin_case();
        let mut values = Vec::new();
        for (argument, t) in arguments.iter().zip(types) {
            values.push(match argument {
                Argument::Scalar(v) => *v,
                Argument::Null => Value::Null,
                Argument::Array(data) => {
                    let element = match t {
                        Type::Array(e) => (**e).clone(),
                        _ => Type::Int,
                    };
                    m.new_array_of(element, data.clone())
                }
            });
        }
        let verdict = match m.call_static(harness::PROPERTY_CLASS, harness::METHOD, &check_descriptor, values) {
            Ok(_) => Some(false),
            Err(Fault::Throw(r)) if m.class_of(r) == "java/lang/AssertionError" => Some(true),
            Err(_) => None,
        };
        m.end_case(mark);
        verdict
    };
    // The interpreter must agree that the input found is a counterexample before it is trusted on smaller ones.
    if fails(&found) != Some(true) {
        return Ok(crate::shrink::Shrunk { arguments: found, runs: 0 });
    }
    Ok(crate::shrink::shrink(types, found, SHRINK_BUDGET, fails))
}

/// Runs the counterexample through the method in the interpreter, with the effect monitor off: the outcome as
/// text, the value returned if the method returned a primitive or an array, the elements of a returned array,
/// and the elements of the array arguments after the call.
#[allow(clippy::type_complexity)]
fn replay(options: &Options, class_internal: &str, method: &str, descriptor: &str, signature: &crate::classfile::MethodDescriptor, arguments: &[Argument]) -> Result<(String, Option<Value>, Option<Vec<Value>>, Vec<(u16, Vec<Value>)>), Error> {
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
    let ret = &signature.ret;
    let mut values = Vec::new();
    for (argument, t) in arguments.iter().zip(&signature.params) {
        values.push(match argument {
            Argument::Scalar(v) => *v,
            Argument::Null => Value::Null,
            Argument::Array(data) => {
                let element = match t {
                    Type::Array(e) => (**e).clone(),
                    _ => Type::Int,
                };
                m.new_array_of(element, data.clone())
            }
        });
    }
    let outcome = m.call_static(class_internal, method, descriptor, values.clone());
    let after = arrays_of(&m, &values, signature);
    Ok(match outcome {
        Ok(Some(v)) => {
            let array = match v {
                Value::Ref(r) => match m.heap.get(r) {
                    Object::Array { data, .. } => Some(data.clone()),
                    _ => None,
                },
                _ => None,
            };
            let text = match (&array, ret) {
                (Some(data), Type::Array(element)) => render_array(data, element),
                _ => render::value(&mut m, v, ret).unwrap_or_else(|f| render::fault(&m, &f)),
            };
            let returned = (ret.is_primitive() || array.is_some()).then_some(v);
            (text, returned, array, after)
        }
        Ok(None) => ("void".to_string(), None, None, after),
        Err(Fault::Throw(r)) => (render::thrown(&m, r), None, None, after),
        Err(f) => (format!("<could not replay: {}>", render::fault(&m, &f)), None, None, after),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_a_properties_file() {
        let text = "# Property contract\nkind: properties\nmodule: quorum\n\nnet.example.Quorum#majority\n  assume: n > 0\n  assert: 2L * result > n\n  arrays: 4\n\nnet.example.Laws#holds\n";
        let declarations = parse_declarations(text, "properties.contract").unwrap();
        assert_eq!(declarations.len(), 2);
        assert_eq!(declarations[0].target, "net.example.Quorum#majority");
        assert_eq!(declarations[0].assume.as_deref(), Some("n > 0"));
        assert_eq!(declarations[0].assert.as_deref(), Some("2L * result > n"));
        assert_eq!(declarations[0].max_array_length, Some(4));
        assert_eq!(declarations[1], Declaration { target: "net.example.Laws#holds".into(), assume: None, assert: None, max_array_length: None });
        assert!(parse_declarations("  assume: x > 0\n", "f").is_err(), "no target");
        assert!(parse_declarations("net.example.A#b\n  require: x\n", "f").is_err(), "unknown key");
        assert!(parse_declarations("net.example.A#b\n  arrays: many\n", "f").is_err(), "not a number");
    }
}
