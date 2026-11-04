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

use crate::classfile::{MemberRef, Type};
use crate::classpath::ClassPath;
use crate::harness::{self, CallArg};
use crate::interp::Value;
use crate::jbmc::{self, Argument, JbmcResult, JbmcRun};
use crate::sarif::{self, Finding};
use crate::{shared, witness, Error, Verdict};

/// JDK classes whose real bytecode JBMC analyses, instead of the small models it ships.
pub const JDK_CLASSES: &[&str] = &["java/lang/Math", "java/lang/StrictMath", "java/lang/Integer", "java/lang/Long", "java/lang/Short", "java/lang/Byte"];

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
    /// The longest array an array parameter is given.
    pub max_array_length: u32,
    /// Whether to shrink a counterexample in the interpreter before reporting it.
    pub shrink: bool,
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
    /// Which checker proves the harness: JBMC (the default), the tool's own ([`crate::bmc`]), or the tool's own
    /// where the harness is within its fragment and JBMC elsewhere.
    pub engine: crate::Engine,
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
            models: true,
            refine_strings: false,
            sat_solver: Some("cadical".into()),
            engine: crate::Engine::Jbmc,
            shared_callees: true,
            before_target: None,
            before_arguments: None,
            results_agree_when: None,
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
    Ok(Some(harness::RecordType { class: name.clone(), components }))
}

fn locals_of(params: &[harness::Param], arguments: &[Argument]) -> (Vec<Value>, Vec<(u16, Vec<Value>)>) {
    let mut locals = Vec::new();
    let mut arrays = Vec::new();
    for (a, p) in arguments.iter().zip(params) {
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
    (locals, arrays)
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
        Ok(Outcome { verdict: Verdict::Unverifiable, target: options.target.clone(), domain: None, counterexample: None, proof: None, problem: Some(problem), statement: None, findings, output: out.clone(), work: work.clone(), shared: Vec::new(), previous: None, relation: None })
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
        let record = record_of(&after_cp, t)?;
        if !t.is_primitive() && harness::expr::element_ty(t).is_none() && record.is_none() {
            return refuse(&mut out, line, format!("parameter {name} has type {}; the symbolic verifier handles primitive parameters, arrays of integral or boolean elements, and records whose components are primitive. Finite types (enums, booleans) are covered by behavioural contracts.", t.java_name()));
        }
        records.push(record);
    }
    let result_record = record_of(&after_cp, &descriptor.ret)?;

    // The previous version: the target under the same name with the same parameters, or the method named by
    // --before-target, called with the arguments --before-arguments gives.
    let before_target = options.before_target.clone().unwrap_or_else(|| options.target.clone());
    let plain = options.before_target.is_none() && options.before_arguments.is_none() && options.results_agree_when.is_none();
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
    let mut both_records = Vec::new();
    for ((name, t), record) in names.iter().zip(&descriptor.params).zip(&records) {
        both_records.push(match record {
            Some(r) if components_passed => Some((r.clone(), None)),
            Some(r) => match record_of(&before_cp, t)? {
                Some(b) if b.same_shape(r) => Some((r.clone(), Some(b))),
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
    // The records among the previous version's parameters, each built by a constructor call among the expressions.
    let mut previous_records = Vec::new();
    for t in &before_descriptor.params {
        previous_records.push(if components_passed { record_of(&before_cp, t)? } else { None });
    }
    let result = match (&result_record, record_of(&before_cp, &before_descriptor.ret)?) {
        (Some(r), Some(b)) if b.same_shape(r) => Some((r.clone(), b)),
        (Some(r), Some(b)) => return refuse(&mut out, line, format!("the result's components changed: {} before, {} now; a regression proof relates the same components in both versions", b.describe(), r.describe())),
        (Some(_), None) => return refuse(&mut out, line, format!("the previous version returns {} and the new one the record {}; a regression proof relates the same components in both versions", before_descriptor.ret.java_name(), descriptor.ret.java_name())),
        (None, Some(b)) if descriptor.ret.is_primitive() || options.results_agree_when.is_none() => return refuse(&mut out, line, format!("the previous version returns the record {} and the new one {}; a regression proof relates the same components in both versions", b.java_name(), descriptor.ret.java_name())),
        _ => None,
    };
    let layout = harness::Layout::new(before_receiver, &names, &descriptor.params, &both_records, result);
    let params = &layout.params;
    let flat_types = layout.types();
    let has_arrays = params.iter().any(|p| matches!(p.ty, Type::Array(_)));
    if before_descriptor.ret != descriptor.ret && options.results_agree_when.is_none() && layout.result.is_none() {
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
    let before_layout = harness::Layout::new(
        previous_receiver.clone().map(|r| (r.clone(), Some(r))),
        &before_names,
        &before_descriptor.params,
        &previous_records.iter().map(|r| r.clone().map(|r| (r.clone(), Some(r)))).collect::<Vec<_>>(),
        None,
    );
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
        relation: options.results_agree_when.clone(),
    });
    let previous_display = previous.as_ref().map(|b| b.display(&class_internal));
    let relation = match (&previous_display, &options.results_agree_when) {
        (Some(p), Some(r)) => format!("agrees with the previous {p} on every input, the results related by {r}"),
        (Some(p), None) => format!("behaves as the previous {p} on every input"),
        (None, _) => "behaves as before on every input".to_string(),
    };
    let domain = layout.domain(options.max_array_length);

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
    let mut plan = if options.shared_callees {
        shared::plan(&shared_before_cp, &shared_after_cp, &MemberRef::new(&before_class_internal, &before_method_name, &before_method.descriptor), &MemberRef::new(&class_internal, &method_name, &method.descriptor), plain)
    } else {
        shared::Plan::default()
    };
    // The harness builds each record through its constructor in both versions: a target identical in both needs no
    // proof only when the constructors are too.
    if plan.identical.is_some() {
        let constructors: Vec<MemberRef> = layout
            .records()
            .iter()
            .filter_map(|s| match s {
                harness::Slot::Record { record, .. } => Some(MemberRef::new(&record.class, "<init>", &record.constructor())),
                harness::Slot::Plain(_) => None,
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
        return Ok(Outcome { verdict: Verdict::Verified, target: options.target.clone(), domain: Some(domain), counterexample: None, proof: Some(how), problem: None, statement: Some(statement), findings: Vec::new(), output: out, work, shared: Vec::new(), previous: None, relation: None });
    }
    let shared_names = shared::names(&plan.callees);

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
    if !plan.callees.is_empty() {
        let dir = work.join("shared-classes");
        std::fs::create_dir_all(&dir)?;
        std::fs::write(dir.join(format!("{}.class", shared::CLASS)), shared::stub(&shared_after_cp, &plan.callees)?)?;
        let lookup = |m: &MemberRef| -> Option<String> {
            let owner = shared::original_owner(&m.owner, "before");
            plan.callees.iter().position(|c| c.owner == owner && c.name == m.name && c.descriptor == m.descriptor).map(|i| plan.callees[i].stub_method(i))
        };
        shared::redirect_directory(&options.after, &dir, &lookup)?;
        shared::redirect_directory(&before_dir, &dir, &lookup)?;
        let mut cp = classpath.clone();
        cp.insert(1, dir);
        shared_classpath = Some(cp);
    }
    let started = std::time::Instant::now();
    let mut last = None;
    // The tool's own checker first, when asked: its verdict stands, and where it has none, JBMC's turn (under
    // `auto`), or that is the answer (under `native`).
    let mut stages: &[Option<&str>] = STAGES;
    if options.engine != crate::Engine::Jbmc {
        let entries: Vec<PathBuf> = classpath.iter().filter(|p| **p != jdk_dir && **p != models_dir).cloned().collect();
        let result = crate::bmc::run_for_proof(&entries, options.models, harness::CLASS, harness::METHOD, options.unwind, Duration::from_secs(options.timeout_seconds), &work)?;
        if result.verdict != Verdict::Unverifiable || options.engine == crate::Engine::Native {
            stages = &[];
            last = Some(result);
        } else {
            let _ = writeln!(out, "note: the tool's own checker gave no verdict ({}); JBMC", result.problem.as_deref().unwrap_or("no reason"));
        }
    }
    // An array parameter is never null, and is bounded in length: the copying and comparing loops, and the
    // method's own, are what the unwinding bound must cover.
    let extra_args = if has_arrays {
        vec!["--java-assume-inputs-non-null".to_string(), "--max-nondet-array-length".to_string(), options.max_array_length.to_string()]
    } else {
        Vec::new()
    };
    let run_stages = |classpath: &[PathBuf], tag: &str| -> Result<Option<JbmcResult>, Error> {
        let mut last = None;
        for stage in stages {
            let run = JbmcRun {
                executable: options.jbmc.clone(),
                class: harness::CLASS.into(),
                function: harness::METHOD.into(),
                classpath: classpath.to_vec(),
                unwind: options.unwind,
                timeout: Duration::from_secs(options.timeout_seconds),
                stage: stage.map(str::to_string),
                refine_strings: options.refine_strings,
                sat_solver: options.sat_solver.clone(),
                log: work.join(format!("jbmc{tag}{}.log", stage.map(|s| format!("-{}", s.replace(|c: char| !c.is_ascii_digit() && c != '-', "_"))).unwrap_or_default())),
                extra_args: extra_args.clone(),
            };
            let result = jbmc::run(&run)?;
            let stop = result.verdict != Verdict::Verified;
            last = Some(result);
            if stop {
                break;
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
    let replay_both = |arguments: &[Argument]| -> Replays {
        let after = witness::replay_in(&replay_cp, &layout, None, &class_internal, &method_name, &method.descriptor, &descriptor, arguments);
        let after_text = after.with_leftovers(params, arguments);
        let (before, before_text) = match map_arguments(arguments) {
            Ok(mapped) => {
                // With the previous version's arguments as expressions, each is a primitive or an array; otherwise
                // the previous version's records are built from the same components.
                let replayed = if harness.before_args.is_some() {
                    witness::replay_in(&replay_cp, &before_layout, Some("before"), &before_owner, &before_method_name, &before_relocated, &before_descriptor, &mapped)
                } else {
                    witness::replay_in(&replay_cp, &layout, Some("before"), &before_owner, &before_method_name, &before_relocated, &before_descriptor, &mapped)
                };
                let text = if harness.before_args.is_some() { replayed.with_leftovers(before_params, &mapped) } else { replayed.with_leftovers(params, &mapped) };
                (Some(replayed), text)
            }
            Err(e) => (None, format!("<could not replay: the previous version's arguments could not be computed: {e}>")),
        };
        let same = before_text == after_text && !before_text.starts_with("<could not replay");
        let (agree, relation_note) = match (&harness.relation, &before) {
            (Some(r), Some(b)) if b.returned.is_some() && after.returned.is_some() => {
                let (mut locals, mut arrays) = locals_of(params, arguments);
                locals.resize(usize::from(r.previous.max(r.result)) + 2, Value::Int(0));
                locals[usize::from(r.previous)] = b.returned.unwrap_or(Value::Null);
                locals[usize::from(r.result)] = after.returned.unwrap_or(Value::Null);
                if let Some(data) = &b.result_array {
                    arrays.push((r.previous, data.clone()));
                }
                if let Some(data) = &after.result_array {
                    arrays.push((r.result, data.clone()));
                }
                let text = options.results_agree_when.as_deref().unwrap_or_default();
                let leftovers = |t: &str| t.find(", leaving").map(|i| t[i..].to_string()).unwrap_or_default();
                match harness::expr::eval_with(&r.expr, &locals, &arrays) {
                    Ok(Value::Int(1)) => (leftovers(&before_text) == leftovers(&after_text), None),
                    Ok(_) => (false, Some(format!("the results are not related by {text}"))),
                    Err(e) => (false, Some(format!("the relation {text} cannot be evaluated on these results: {e}"))),
                }
            }
            _ => (same, None),
        };
        Replays { before: before_text, after: after_text, agree, relation_note }
    };
    // With the shared callees first: a proof with them is a proof, and a counterexample with them is one when it
    // reproduces through the bytecode as written; otherwise the abstraction was too coarse, and the callees are
    // proved as written.
    let mut shared_used = Vec::new();
    if last.is_none() {
        if let Some(cp) = &shared_classpath {
            if let Some(result) = run_stages(cp, "-shared")? {
                let keep = match result.verdict {
                    Verdict::Violation => !replay_both(&result.arguments(&flat_types)?).agree,
                    _ => true,
                };
                if keep {
                    shared_used = shared_names.clone();
                    last = Some(result);
                } else {
                    let _ = writeln!(out, "note: the counterexample found with {} taken as one function in both versions does not reproduce once computed as written; proving with the callees' bytecode", shared_names.join(", "));
                }
            }
        }
        if last.is_none() {
            last = run_stages(&classpath, "")?;
        }
    }
    let last = last.expect("at least one stage");
    let seconds = started.elapsed().as_secs_f64();
    let sharing = match shared_used.len() {
        0 => String::new(),
        1 => format!("; {} unchanged in both versions and taken as one function in both", shared_used[0]),
        n => format!("; {n} callees unchanged in both versions and taken as one function in both: {}", shared_used.join(", ")),
    };

    let mut findings = Vec::new();
    let mut counterexample = None;
    let mut proof = None;
    let mut problem = None;
    let mut verdict = last.verdict;
    match last.verdict {
        Verdict::Verified => {
            let how = format!("{}: {} properties proved over {domain} in {seconds:.1} s; loops unwound {} times with unwinding assertions{sharing}", last.version, last.properties, options.unwind);
            let _ = writeln!(out, "✓ {} {relation}{restriction} ({how})", options.target);
            proof = Some(how);
        }
        Verdict::Violation => {
            let found = last.arguments(&flat_types)?;
            let replays = replay_both(&found);
            // A counterexample the interpreter cannot reproduce is no counterexample: JBMC has given an arbitrary
            // result to a method it had no bytecode for (one outside its models and the class path it was given).
            if replays.agree {
                let (rendered, _) = witness::call_in(&method_name, &layout, &found);
                let both = if replays.before == replays.after { format!("both versions give {}", replays.before) } else { format!("the versions give {} and {}, which the relation relates,", replays.before, replays.after) };
                let p = format!("JBMC's counterexample {rendered} does not reproduce: {both} in the interpreter. A method the target calls is probably missing from JBMC's class path (its models cover little of the JDK beyond java.lang.Math and the integer wrappers) and was treated as returning an arbitrary value");
                let message = format!("{} cannot be verified: {p}", options.target);
                let _ = writeln!(out, "✗ {message}");
                findings.push(Finding::new("unverifiable", message, uri.clone(), line));
                problem = Some(p);
                verdict = Verdict::Unverifiable;
                if let Some(report) = &options.report {
                    sarif::write(&report.join("equivalence.sarif"), &findings)?;
                }
                return Ok(Outcome { verdict, target: options.target.clone(), domain: Some(domain), counterexample, proof, problem, statement: Some(statement), findings, output: out, work, shared: shared_used, previous: previous_display.clone(), relation: options.results_agree_when.clone() });
            }
            // Shrink the witness: the harness class JBMC checked, run in the interpreter on smaller inputs.
            let mut shrink_runs = 0;
            let mut arguments = found.clone();
            if options.shrink {
                let harness_cp = witness::classpath([harness_dir.as_path(), options.after.as_path(), before_dir.as_path()].into_iter().chain(options.classpath.iter().map(PathBuf::as_path)))?;
                let shrunk = witness::shrink_in_harness(&harness_cp, harness::CLASS, &flat_types, found.clone());
                shrink_runs = shrunk.runs;
                arguments = shrunk.arguments;
            }
            let shrunk = arguments != found;
            let replays = if shrunk { replay_both(&arguments) } else { replays };
            let Replays { before: before_outcome, after: after_outcome, relation_note, .. } = replays;
            let (mut rendered, witnesses) = witness::call_in(&method_name, &layout, &arguments);
            let (rendered_found, _) = witness::call_in(&method_name, &layout, &found);
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
            let how = format!("found by {} in {seconds:.1} s{stage}{shrinking}, replayed in the interpreter; domain {domain}{sharing}", last.version);
            let _ = writeln!(out, "  ({how})");
            if let Some(scope) = &harness.scope {
                let (locals, arrays) = locals_of(params, &arguments);
                if let Ok(Value::Int(1)) = harness::expr::eval_with(scope, &locals, &arrays) {
                    let _ = writeln!(out, "  (note: the interpreter evaluates the scope expression as true on this input, which the harness should have skipped; check the expression)");
                }
            }
            findings.push(Finding::new("behaviour-changed", message, uri.clone(), line));
            proof = Some(how);
            counterexample = Some(Counterexample { input: rendered, before: before_outcome, after: after_outcome, values: witnesses, found: shrunk.then_some(rendered_found), shrink_runs });
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
    Ok(Outcome { verdict, target: options.target.clone(), domain: Some(domain), counterexample, proof, problem, statement: Some(statement), findings, output: out, work, shared: shared_used, previous: previous_display, relation: options.results_agree_when.clone() })
}

/// Both versions replayed on one input.
struct Replays {
    before: String,
    after: String,
    /// Whether the two outcomes agree: under a relation between the results, whether it holds.
    agree: bool,
    /// Why they do not, when a relation was given and both versions returned.
    relation_note: Option<String>,
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
