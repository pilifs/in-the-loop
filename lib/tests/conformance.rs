//! The conformance corpus of step 1d of `llm-dlc/loops/sound-verdicts.md`: small Java methods
//! (`tests/conformance/conformance/Conformance.java`), each with claims, run through the tool's engines and against
//! a real JVM. The JVM is the semantic reference: the interpreter and the engines share models, so their agreement
//! proves nothing about the JVM, and a disagreement with it is a bug in the tool whichever side the verdict falls on.
//!
//! For every case the test checks, on a JVM that `tests/conformance/Runner.java` drives:
//! - each listed call gives the outcome recorded here, and the interpreter gives the same one;
//! - each claim's harness, the class the tool generates and every engine checks, holds or is refuted on the
//!   listed calls as recorded, so a claim recorded as refuted has a refuting input the JVM confirms;
//! - no engine gives `Verified` for a claim the JVM refutes, under `--gaps strict`; under `--gaps assume` only
//!   when the verdict names a gap it assumed;
//! - every violation an engine reports has a witness on which the JVM refutes the harness too.
//!
//! An input outside the domain the engines prove over (a null array parameter, or two parameters that are one
//! array) is run on the JVM only, and a `Verified` verdict for a claim of that case must state the restriction
//! that leaves the input out.
//!
//! The native engine's verdicts are recorded per claim. JBMC and `--engine auto` run in the ignored test, a
//! pipeline job: `cargo test --release --test conformance -- --ignored`.

use std::fmt::Write as _;
use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::bmc::gaps::GapMode;
use jvmcontract::interp::Value;
use jvmcontract::jbmc::Argument;
use jvmcontract::{property, Engine, Verdict};

use Verdict::{Unverifiable as U, Verified as V, Violation as X};

const CLASS: &str = "conformance.Conformance";

fn has(program: &str) -> bool {
    let found = Command::new(program).arg("--version").output().map(|o| o.status.success()).unwrap_or(false);
    if !found {
        let skip = std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1");
        assert!(skip, "{program} not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip the tests that need it");
    }
    found
}

fn target_tmp() -> PathBuf {
    PathBuf::from(env!("CARGO_TARGET_TMPDIR"))
}

/// One claim about a case's method: the property proof's `--assume`, `--assert` and `--throws`.
struct Claim {
    assume: Option<&'static str>,
    assert: &'static str,
    throws: &'static [&'static str],
    /// Whether one of the case's calls refutes it on the JVM.
    refuted: bool,
    /// The native engine's verdict under `--gaps strict`.
    native: Verdict,
}

struct Case {
    method: &'static str,
    /// Calls in the engines' domain, as the runner reads arguments, each with the JVM's outcome.
    calls: Vec<(&'static str, &'static str)>,
    /// Calls outside the engines' domain, with the JVM's outcome and the words of the domain that leave them out.
    outside: Vec<(&'static str, &'static str, &'static str)>,
    claims: Vec<Claim>,
}

impl Case {
    fn new(method: &'static str, calls: &[(&'static str, &'static str)]) -> Case {
        Case { method, calls: calls.to_vec(), outside: Vec::new(), claims: Vec::new() }
    }
    fn holds(mut self, assume: Option<&'static str>, assert: &'static str, throws: &'static [&'static str], native: Verdict) -> Case {
        self.claims.push(Claim { assume, assert, throws, refuted: false, native });
        self
    }
    fn refuted(mut self, assume: Option<&'static str>, assert: &'static str, throws: &'static [&'static str], native: Verdict) -> Case {
        self.claims.push(Claim { assume, assert, throws, refuted: true, native });
        self
    }
    fn outside(mut self, arguments: &'static str, outcome: &'static str, domain_says: &'static str) -> Case {
        self.outside.push((arguments, outcome, domain_says));
        self
    }
}

const MIN: &str = "-2147483648";
const IAE: &str = "throws java.lang.IllegalArgumentException";

/// The corpus. A claim's native verdict is what the engine gives today; `U` on a claim the JVM refutes is a gap or
/// a construct refused by name, which is the correct answer under strict.
fn corpus() -> Vec<Case> {
    vec![
        // Gaps (step 1b): a JDK constructor that throws, refused by name; a monitor on null, an NPE.
        Case::new("capacity", &[("-1", IAE), ("3", "returns 1")]).refuted(None, "result == 1", &[], U),
        Case::new("builderCapacity", &[("-1", "throws java.lang.NegativeArraySizeException"), ("3", "returns 1")]).refuted(None, "result == 1", &[], U),
        Case::new("mapCapacity", &[("-1", IAE), ("3", "returns 1")]).refuted(None, "result == 1", &[], U),
        Case::new("setCapacity", &[("-1", IAE), ("3", "returns 1")]).refuted(None, "result == 1", &[], U),
        Case::new("loadFactor", &[("0", IAE), ("-1", IAE), ("1", "returns 1")]).refuted(None, "result == 1", &[], U),
        Case::new("nullMonitor", &[("0", "throws java.lang.NullPointerException")]).refuted(None, "result == 1", &[], X),
        Case::new("monitor", &[("4", "returns 4")]).holds(None, "result == n", &[], V),
        Case::new("firstByte", &[("[0]", "returns 115"), ("[]", "returns 0")]).refuted(None, "out.length == 0 || result == \\old(out[0])", &[], U),
        // Identity and initialization (step 1c).
        Case::new("hiding", &[("5", "returns 5")]).holds(None, "result == n", &[], V).refuted(None, "result == 2", &[], X),
        Case::new("hidden", &[("5", "returns 2")]).holds(None, "result == 2", &[], V).refuted(None, "result == n", &[], X),
        Case::new("sameLiteral", &[("0", "returns 1")]).holds(None, "result", &[], V).refuted(None, "!result", &[], X),
        Case::new("otherLiteral", &[("0", "returns 0")]).holds(None, "!result", &[], V).refuted(None, "result", &[], X),
        Case::new("sameClass", &[("0", "returns 1")]).holds(None, "result", &[], V).refuted(None, "!result", &[], X),
        Case::new("concatenated", &[("0", "returns 0")]).holds(None, "!result", &[], V).refuted(None, "result", &[], X),
        Case::new("boom", &[("3", "throws java.lang.ExceptionInInitializerError")]).refuted(None, "result == n", &[], U),
        Case::new("inherited", &[("3", "throws java.lang.ExceptionInInitializerError")]).refuted(None, "result == n", &[], U),
        Case::new("quiet", &[("3", "returns 3")]).holds(None, "result == n", &[], U),
        // Exceptions.
        Case::new("finallyWins", &[("0", "returns 2"), ("1", "returns 2")]).holds(None, "result == 2", &[], V).refuted(None, "result == 1", &[], X),
        Case::new("caught", &[("0", "returns -1"), ("5", "returns 2")]).holds(None, "n != 0 || result == -1", &[], V).refuted(None, "result != -1", &[], X),
        Case::new("nestedHandler", &[("0", "returns -2"), ("3", "returns 33")]).holds(None, "n != 0 || result == -2", &[], V).refuted(None, "result != -2", &[], X),
        Case::new("element", &[("[];0", "throws java.lang.ArrayIndexOutOfBoundsException"), ("[4,5];1", "returns 5")])
            .holds(None, "result == a[i]", &["ArrayIndexOutOfBoundsException when i < 0 || i >= a.length"], V)
            .refuted(None, "result == a[i]", &["ArrayIndexOutOfBoundsException when i < 0"], X),
        Case::new("cast", &[("1", "throws java.lang.ClassCastException"), ("0", "returns 0")])
            .holds(None, "result == 0", &["ClassCastException when n > 0"], V)
            .refuted(None, "result == 0", &[], X),
        Case::new("throwNull", &[("0", "throws java.lang.NullPointerException"), ("1", "throws java.lang.IllegalStateException"), ("-5", "returns 0")])
            .holds(None, "result == 0", &["IllegalStateException when n > 0", "NullPointerException when n > -5 && n <= 0"], V)
            .refuted(None, "result == 0", &["IllegalStateException when n > -5"], X),
        Case::new("rethrown", &[("-1", "throws java.lang.IllegalStateException"), ("2", "returns 2")])
            .holds(None, "result == n", &["IllegalStateException when n < 0"], V)
            .refuted(None, "result == n", &["IllegalArgumentException when n < 0"], X),
        // Aliasing.
        Case::new("aliasedLocals", &[("1", "returns 1")]).holds(None, "result == n", &[], V).refuted(None, "result == 0", &[], X),
        Case::new("aliasedObjects", &[("1", "returns 1")]).holds(None, "result == n", &[], V).refuted(None, "result == 0", &[], X),
        Case::new("twoArrays", &[("[0];[0]", "returns 1")])
            .holds(Some("a.length > 0 && b.length > 0"), "result == 1", &[], V)
            .outside("[0];@0", "returns 2", "no two the same array"),
        Case::new("writeThrough", &[("[]", "returns 7"), ("[1]", "returns 7")]).holds(None, "result == 7", &[], V),
        // Null arrays.
        Case::new("length", &[("[1,2]", "returns 2")]).holds(None, "result >= 0", &[], V).outside("null", "throws java.lang.NullPointerException", "a: int[] of length ≤ 8, not null"),
        Case::new("lengthOrMinusOne", &[("[]", "returns 0")]).holds(None, "result >= 0", &[], V).outside("null", "returns -1", "a: int[] of length ≤ 8, not null"),
        Case::new("nullLocal", &[("0", "throws java.lang.NullPointerException"), ("1", "returns 1")])
            .holds(None, "result == 1", &["NullPointerException when n <= 0"], V)
            .refuted(None, "result == 1", &[], X),
        // Records.
        Case::new("width", &[("1;0", IAE), ("-1;2147483647", "returns -2147483648"), ("2;5", "returns 3")])
            .holds(None, "result == hi - lo", &["IllegalArgumentException when lo > hi"], V)
            .refuted(None, "result >= 0", &["IllegalArgumentException when lo > hi"], X)
            .refuted(None, "result == hi - lo", &[], X),
        Case::new("clamp", &[("-1", "returns 0"), ("3", "returns 3")]).holds(None, "result >= 0", &[], V).refuted(None, "result == n", &[], X),
        Case::new("pairsEqual", &[("1;2", "returns 1")]).holds(None, "result", &[], U).refuted(None, "!result", &[], U),
        // Dispatch.
        Case::new("sides", &[("1", "returns 4"), ("-1", "returns 5"), ("0", "returns 0")])
            .holds(None, "(n <= 0 || result == 4) && (n >= 0 || result == 5) && (n != 0 || result == 0)", &[], V)
            .refuted(None, "result == 4", &[], X),
        Case::new("code", &[("1", "returns 2"), ("0", "returns 1")]).holds(None, "(n <= 0 || result == 2) && (n > 0 || result == 1)", &[], V).refuted(None, "result == 2", &[], X),
        // Arithmetic edge cases.
        Case::new("divide", &[("-2147483648;-1", "returns -2147483648"), ("7;0", "throws java.lang.ArithmeticException"), ("-7;2", "returns -3")])
            .holds(Some("b == -1"), "result == -a", &[], V)
            .refuted(Some("b == -1 && a < 0"), "result > 0", &[], X)
            .holds(None, "result * b + a % b == a", &["ArithmeticException when b == 0"], V)
            .refuted(None, "result * b + a % b == a", &[], X),
        Case::new("divideLong", &[("-9223372036854775808;-1", "returns -9223372036854775808"), ("-7;2", "returns -3")])
            .refuted(Some("b == -1 && a < 0"), "result > 0", &[], X)
            .holds(Some("b == -1"), "result == -a", &[], V),
        Case::new("remainder", &[("-1;2", "returns -1"), ("-2147483648;-1", "returns 0"), ("7;-3", "returns 1")])
            .holds(Some("b > 0"), "result > -b && result < b", &[], V)
            .refuted(Some("b > 0"), "result >= 0", &[], X)
            .holds(Some("b == -1"), "result == 0", &[], V),
        Case::new("remainderLong", &[("-1;2", "returns -1"), ("-9223372036854775808;-1", "returns 0")])
            .holds(Some("b == -1"), "result == 0", &[], V)
            .refuted(Some("a < 0 && b > 0"), "result >= 0", &[], X),
        Case::new("shiftLeft", &[("1;32", "returns 1"), ("1;-1", "returns -2147483648")])
            .holds(Some("s == 32"), "result == x", &[], V)
            .refuted(Some("s == 32"), "result == 0", &[], X)
            .holds(Some("s == -1 && x == 1"), "result == -2147483648", &[], V),
        Case::new("shiftLeftLong", &[("1;64", "returns 1"), ("1;32", "returns 4294967296")])
            .holds(Some("s == 64"), "result == x", &[], V)
            .refuted(Some("s == 64"), "result == 0", &[], X)
            .holds(Some("s == 32 && x == 1"), "result > 2147483647", &[], V),
        Case::new("shiftRight", &[("-1;7", "returns -1"), ("-1;33", "returns -1")])
            .holds(Some("x == -1"), "result == -1", &[], V)
            .refuted(Some("s == 33"), "result == x / 2", &[], X),
        Case::new("shiftUnsigned", &[("-1;32", "returns -1"), ("-1;1", "returns 2147483647")])
            .refuted(Some("x < 0 && s == 32"), "result > 0", &[], X)
            .holds(Some("x < 0 && s == 1"), "result > 0", &[], V),
        Case::new("square", &[("46341", "returns -2147479015")]).refuted(None, "result >= 0", &[], X),
        Case::new("negate", &[(MIN, "returns -2147483648")]).refuted(Some("x < 0"), "result > 0", &[], X),
        Case::new("toByte", &[("128", "returns -128"), ("-129", "returns 127")])
            .refuted(Some("x >= 0"), "result >= 0", &[], X)
            .holds(None, "result >= -128 && result <= 127", &[], V),
        Case::new("toChar", &[("-1", "returns 65535")]).holds(None, "result >= 0 && result <= 65535", &[], V).refuted(None, "result == x", &[], X),
        Case::new("toShort", &[("32768", "returns -32768")]).holds(Some("x == 32768"), "result == -32768", &[], V),
        Case::new("fromLong", &[("2147483648", "returns -2147483648")]).refuted(Some("x > 2147483647"), "result > 0", &[], X),
        Case::new("nextChar", &[("65535", "returns 0")]).holds(Some("c == 65535"), "result == 0", &[], V).refuted(None, "result > c", &[], X),
        Case::new("absolute", &[(MIN, "returns -2147483648"), ("-3", "returns 3")]).refuted(None, "result >= 0", &[], X),
        Case::new("increment", &[("2147483647", "returns -2147483648")]).holds(Some("x == 2147483647"), "result == -2147483648", &[], V),
        Case::new("byteSum", &[("-1;0", "returns -1"), ("127;127", "returns 254")])
            .holds(None, "result >= -256 && result <= 254", &[], V)
            .refuted(None, "result >= 0", &[], X),
    ]
}

/// The corpus and the runner, compiled.
struct Compiled {
    classes: PathBuf,
    runner: PathBuf,
}

fn compile() -> Option<Compiled> {
    if !has("javac") || !has("java") {
        return None;
    }
    let src = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/conformance");
    let classes = target_tmp().join("conformance-classes");
    let runner = target_tmp().join("conformance-runner");
    for (out, file) in [(&classes, src.join("conformance/Conformance.java")), (&runner, src.join("Runner.java"))] {
        let _ = std::fs::remove_dir_all(out);
        std::fs::create_dir_all(out).unwrap();
        let status = Command::new("javac").args(["-parameters", "-g", "-proc:none", "-d"]).arg(out).arg(&file).status().expect("javac runs");
        assert!(status.success(), "{} compiles", file.display());
    }
    Some(Compiled { classes, runner })
}

/// Runs `lines` (`call` and `check` lines, as the runner's documentation says) on the JVM, one output line each.
fn on_the_jvm(compiled: &Compiled, lines: &[String], name: &str) -> Vec<String> {
    let file = target_tmp().join(format!("conformance-{name}.txt"));
    std::fs::write(&file, lines.join("\n") + "\n").unwrap();
    let run = Command::new("java").arg("-cp").arg(&compiled.runner).arg("Runner").arg(&compiled.classes).arg(&file).output().expect("java runs");
    assert!(run.status.success(), "the runner fails: {}", String::from_utf8_lossy(&run.stderr));
    let out: Vec<String> = String::from_utf8_lossy(&run.stdout).lines().map(str::to_string).collect();
    assert_eq!(out.len(), lines.len(), "one line per line: {out:?}");
    out
}

/// A runner argument as the interpreter's: a number, a boolean, `null` or an array of numbers.
fn interpreter_argument(token: &str, t: &jvmcontract::classfile::Type) -> Argument {
    use jvmcontract::classfile::Type;
    let scalar = |s: &str, t: &Type| match t {
        Type::Boolean => Value::Int(i32::from(s == "true")),
        Type::Long => Value::Long(s.parse().unwrap()),
        _ => Value::Int(s.parse().unwrap()),
    };
    match (token, t) {
        ("null", _) => Argument::Null,
        (_, Type::Array(element)) => {
            let body = token.trim_start_matches('[').trim_end_matches(']').trim();
            Argument::Array(if body.is_empty() { Vec::new() } else { body.split(',').map(|s| scalar(s.trim(), element)).collect() })
        }
        _ => Argument::Scalar(scalar(token, t)),
    }
}

/// The interpreter's outcome of a call, in the runner's words.
fn in_the_interpreter(cp: &jvmcontract::classpath::ClassPath, method: &str, arguments: &str) -> String {
    let class = cp.application("conformance/Conformance").unwrap().unwrap();
    let m = class.methods.iter().find(|m| m.name == method).unwrap_or_else(|| panic!("no method {method}"));
    let signature = jvmcontract::classfile::MethodDescriptor::parse(&m.descriptor).unwrap();
    let tokens: Vec<&str> = if arguments.is_empty() { Vec::new() } else { arguments.split(';').collect() };
    let values: Vec<Argument> = tokens.iter().zip(&signature.params).map(|(t, ty)| interpreter_argument(t.trim(), ty)).collect();
    let replayed = jvmcontract::witness::replay(cp, "conformance/Conformance", method, &m.descriptor, &signature, &values);
    if let Some(thrown) = &replayed.thrown {
        return format!("throws {}", thrown.replace('/', "."));
    }
    match (&replayed.result_array, replayed.returned) {
        (Some(data), _) => format!("returns [{}]", data.iter().map(|v| show(*v)).collect::<Vec<_>>().join(", ")),
        (None, Some(v)) => format!("returns {}", show(v)),
        (None, None) => replayed.outcome.clone(),
    }
}

fn show(v: Value) -> String {
    match v {
        Value::Int(x) => x.to_string(),
        Value::Long(x) => x.to_string(),
        other => format!("{other:?}"),
    }
}

/// A witness's inputs as the runner reads them.
fn runner_arguments(inputs: &[jvmcontract::witness::Typed]) -> String {
    fn token(v: &serde_json::Value) -> String {
        match v {
            serde_json::Value::Bool(b) => b.to_string(),
            serde_json::Value::Number(n) => n.to_string(),
            serde_json::Value::String(s) => s.clone(),
            serde_json::Value::Array(items) => format!("[{}]", items.iter().map(token).collect::<Vec<_>>().join(",")),
            _ => "null".to_string(),
        }
    }
    inputs.iter().map(|t| t.value.as_ref().map(token).unwrap_or_else(|| "null".into())).collect::<Vec<_>>().join(";")
}

/// One engine's run of one claim.
struct Run {
    case: usize,
    claim: usize,
    engine: Engine,
    gaps: GapMode,
    outcome: property::Outcome,
}

fn prove(case: &Case, claim: &Claim, index: usize, engine: Engine, gaps: GapMode, classes: &Path) -> property::Outcome {
    let mut options = property::Options::new(std::slice::from_ref(&classes.to_path_buf()), &format!("{CLASS}#{}", case.method));
    options.assume = claim.assume.map(str::to_string);
    options.assert = Some(claim.assert.to_string());
    options.throws = claim.throws.iter().map(|s| s.to_string()).collect();
    options.engine = engine;
    options.gaps = gaps;
    let work = target_tmp().join(format!("conformance-{engine:?}-{gaps:?}")).join(format!("{}-{index}", case.method));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    property::run(&options).unwrap()
}

fn claim_text(claim: &Claim) -> String {
    let mut s = String::new();
    if let Some(a) = claim.assume {
        let _ = write!(s, "assume {a}; ");
    }
    let _ = write!(s, "assert {}", claim.assert);
    for t in claim.throws {
        let _ = write!(s, "; throws {t}");
    }
    s
}

/// Runs the corpus through `engines` and the JVM, and returns what disagrees with it; `recorded` also holds the
/// native engine's strict verdicts to the corpus's.
fn conformance(engines: &[(Engine, GapMode)], recorded: bool) -> Option<Vec<String>> {
    let compiled = compile()?;
    let corpus = corpus();
    let mut failures = Vec::new();
    let cp = jvmcontract::witness::classpath([compiled.classes.as_path()]).unwrap().with_models(true);

    // 1. The calls, on the JVM and in the interpreter.
    let mut lines = Vec::new();
    for case in &corpus {
        for (arguments, _) in &case.calls {
            lines.push(format!("call\t{CLASS}#{}\t{arguments}", case.method));
        }
        for (arguments, _, _) in &case.outside {
            lines.push(format!("call\t{CLASS}#{}\t{arguments}", case.method));
        }
    }
    let jvm = on_the_jvm(&compiled, &lines, "calls");
    let mut refused = Vec::new();
    let mut at = 0;
    for case in &corpus {
        for (arguments, expected) in &case.calls {
            if jvm[at] != *expected {
                failures.push(format!("{}({arguments}): the JVM {} where the corpus says {expected}", case.method, jvm[at]));
            }
            // The interpreter may refuse a call it does not model, which is not a disagreement.
            let interpreted = in_the_interpreter(&cp, case.method, arguments);
            if interpreted.starts_with("<could not replay") {
                refused.push(format!("{}({arguments})", case.method));
            } else if interpreted != jvm[at] {
                failures.push(format!("{}({arguments}): the interpreter {interpreted} where the JVM {}", case.method, jvm[at]));
            }
            at += 1;
        }
        for (arguments, expected, _) in &case.outside {
            if jvm[at] != *expected {
                failures.push(format!("{}({arguments}): the JVM {} where the corpus says {expected}", case.method, jvm[at]));
            }
            at += 1;
        }
    }

    // 2. The claims, through each engine.
    let mut runs = Vec::new();
    for (c, case) in corpus.iter().enumerate() {
        for (k, claim) in case.claims.iter().enumerate() {
            for &(engine, gaps) in engines {
                let outcome = prove(case, claim, k, engine, gaps, &compiled.classes);
                runs.push(Run { case: c, claim: k, engine, gaps, outcome });
            }
        }
    }

    // 3. Each claim's harness on the JVM: on the case's calls, and on every witness an engine found.
    let mut checks = Vec::new();
    let mut harness_of = std::collections::BTreeMap::new();
    for run in &runs {
        let Some(statement) = &run.outcome.statement else { continue };
        let dir = statement.parent().unwrap().to_path_buf();
        harness_of.entry((run.case, run.claim)).or_insert_with(|| dir.clone());
        if let Some(witness) = &run.outcome.counterexample {
            checks.push((Some(runs.iter().position(|r| std::ptr::eq(r, run)).unwrap()), run.case, run.claim, format!("check\t{}\t{}", dir.display(), runner_arguments(&witness.inputs))));
        }
    }
    for (c, case) in corpus.iter().enumerate() {
        for k in 0..case.claims.len() {
            let Some(dir) = harness_of.get(&(c, k)) else {
                failures.push(format!("{} [{}]: no engine wrote a harness", case.method, claim_text(&case.claims[k])));
                continue;
            };
            for (arguments, _) in &case.calls {
                checks.push((None, c, k, format!("check\t{}\t{arguments}", dir.display())));
            }
        }
    }
    let lines: Vec<String> = checks.iter().map(|(_, _, _, line)| line.clone()).collect();
    let verdicts = on_the_jvm(&compiled, &lines, "checks");
    let mut refuted_on_the_jvm = std::collections::BTreeSet::new();
    for ((witness_of, c, k, line), said) in checks.iter().zip(&verdicts) {
        let case = &corpus[*c];
        if said.starts_with("error") || (said.starts_with("throws") && witness_of.is_none()) {
            failures.push(format!("{} [{}]: the harness does not run on the JVM: {said} ({line})", case.method, claim_text(&case.claims[*k])));
        }
        match witness_of {
            None if said == "refuted" => {
                refuted_on_the_jvm.insert((*c, *k));
            }
            Some(r) if said != "refuted" => {
                let run = &runs[*r];
                let witness = run.outcome.counterexample.as_ref().unwrap();
                failures.push(format!("{} [{}]: {:?} --gaps {:?} reports a violation on {} that the JVM does not reproduce: the harness {said}", case.method, claim_text(&case.claims[*k]), run.engine, run.gaps, witness.input));
            }
            _ => {}
        }
    }

    // 4. The verdicts against the JVM.
    let mut table = String::new();
    for run in &runs {
        let case = &corpus[run.case];
        let claim = &case.claims[run.claim];
        let refuted = refuted_on_the_jvm.contains(&(run.case, run.claim));
        let label = format!("{} [{}]", case.method, claim_text(claim));
        let verdict = run.outcome.verdict;
        let _ = writeln!(table, "{:<16} {:?}/{:?} {:<12} {}", case.method, run.engine, run.gaps, format!("{verdict:?}"), claim_text(claim));
        if refuted != claim.refuted {
            failures.push(format!("{label}: the corpus says it is {}, the JVM {}", if claim.refuted { "refuted" } else { "not refuted" }, if refuted { "refutes it" } else { "does not on any of its calls" }));
        }
        let gaps = run.outcome.search.as_ref().map(|s| s.gaps.len()).unwrap_or(0);
        match (refuted, verdict, run.gaps) {
            (true, Verdict::Verified, GapMode::Strict) => failures.push(format!("{label}: {:?} --gaps strict says Verified, and the JVM refutes it: {}", run.engine, run.outcome.output)),
            (true, Verdict::Verified, _) if gaps == 0 => failures.push(format!("{label}: {:?} --gaps {:?} says Verified with no gap assumed, and the JVM refutes it: {}", run.engine, run.gaps, run.outcome.output)),
            _ => {}
        }
        if verdict == Verdict::Verified {
            for (arguments, _, says) in &case.outside {
                let domain = run.outcome.domain.as_deref().unwrap_or("");
                if !domain.contains(says) || !run.outcome.output.contains(says) {
                    failures.push(format!("{label}: verified over the domain {domain:?}, which does not say {says:?}, the words that leave out {}({arguments})", case.method));
                }
            }
        }
        if recorded && run.engine == Engine::Native && run.gaps == GapMode::Strict && verdict != claim.native {
            failures.push(format!("{label}: the native engine says {verdict:?} where the corpus records {:?}: {}", claim.native, run.outcome.output));
        }
        if recorded && run.engine == Engine::Native && run.gaps == GapMode::Assume && gaps == 0 && claim.native != Verdict::Unverifiable && verdict != claim.native {
            failures.push(format!("{label}: with no gap met, --gaps assume says {verdict:?} where strict says {:?}", claim.native));
        }
    }
    eprintln!("{table}");
    let claims: usize = corpus.iter().map(|c| c.claims.len()).sum();
    let refuted = corpus.iter().flat_map(|c| &c.claims).filter(|c| c.refuted).count();
    eprintln!("{} cases, {claims} claims ({refuted} refuted on the JVM), {} runs; the interpreter refuses {}", corpus.len(), runs.len(), refused.join(", "));
    Some(failures)
}

/// Under strict, the tool's own checker gives no `Verified` the JVM refutes, and each of its violations is one the
/// JVM reproduces; under assume it gives `Verified` for a refuted claim only when it names the gap it assumed.
#[test]
fn the_corpus_agrees_with_the_jvm_on_the_tools_own_checker() {
    let Some(failures) = conformance(&[(Engine::Native, GapMode::Strict), (Engine::Native, GapMode::Assume)], true) else { return };
    assert!(failures.is_empty(), "{} disagreements with the JVM:\n{}", failures.len(), failures.join("\n"));
}

/// JBMC and `--engine auto` under strict, on the same corpus: a pipeline job, since it runs JBMC once or more per
/// claim (`cargo test --release --test conformance -- --ignored`).
#[test]
#[ignore = "runs JBMC on every claim: a pipeline job"]
fn the_corpus_agrees_with_the_jvm_under_jbmc_and_auto() {
    if !has("jbmc") {
        return;
    }
    let Some(failures) = conformance(&[(Engine::Jbmc, GapMode::Strict), (Engine::Auto, GapMode::Strict)], false) else { return };
    assert!(failures.is_empty(), "{} disagreements with the JVM:\n{}", failures.len(), failures.join("\n"));
}
