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
//! The native engine's verdicts are recorded per claim. JBMC, `--engine auto` and `--engine auto --confirm` run in
//! the ignored tests, pipeline jobs: `cargo test --release --test conformance -- --ignored`. What `--confirm` does
//! with each answer JBMC can give is tested here with a script standing in for JBMC.

use std::fmt::Write as _;
use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::bmc::gaps::{GapMode, GapTreatment};
use jvmcontract::equivalence::Confirmed;
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
    confirm: bool,
    contracts: bool,
    outcome: property::Outcome,
}

/// An engine, a gap mode, whether a proof of the own checker's is confirmed by JBMC (`--confirm`), and whether the
/// corpus's contracts are given (`--contracts`, under advised).
type Mode = (Engine, GapMode, bool, bool);

/// Contracts for the corpus's gaps, each stating what the JDK's call does as the corpus's calls show it on the JVM
/// (step 3b of the sound-verdicts brief), written by an agent: the session that wrote the step. The initializers
/// that throw are given contracts that say so, which the own checker refuses (it applies an initializer's only
/// when it throws nothing), so those claims stay without a verdict. Since 3c each is tested on the JVM before it is
/// applied, and the test fails if one is refuted or left untested.
const CORPUS_CONTRACTS: &str = "kind: gap-contracts

jdk-constructor:java.util.ArrayList.<init>(I)V@{jdk}
  call: java.util.ArrayList.<init>(int initialCapacity)
  throws: IllegalArgumentException when initialCapacity < 0
  modifies: nothing
  written-by: an agent (claude-opus-5-5, sound-verdicts step 3b)

jdk-constructor:java.lang.StringBuilder.<init>(I)V@{jdk}
  call: java.lang.StringBuilder.<init>(int capacity)
  throws: NegativeArraySizeException when capacity < 0
  modifies: nothing
  written-by: an agent (claude-opus-5-5, sound-verdicts step 3b)

jdk-constructor:java.util.HashMap.<init>(I)V@{jdk}
  call: java.util.HashMap.<init>(int initialCapacity)
  throws: IllegalArgumentException when initialCapacity < 0
  modifies: nothing
  written-by: an agent (claude-opus-5-5, sound-verdicts step 3b)

jdk-constructor:java.util.HashSet.<init>(I)V@{jdk}
  call: java.util.HashSet.<init>(int initialCapacity)
  throws: IllegalArgumentException when initialCapacity < 0
  modifies: nothing
  written-by: an agent (claude-opus-5-5, sound-verdicts step 3b)

jdk-constructor:java.util.Random.<init>(J)V@{jdk}
  call: java.util.Random.<init>(long seed)
  modifies: nothing
  written-by: an agent (claude-opus-5-5, sound-verdicts step 3b)

jdk-void-method:java.util.Random.nextBytes([B)V@{jdk}
  call: java.util.Random.nextBytes(byte[] bytes)
  modifies: this, bytes
  written-by: an agent (claude-opus-5-5, sound-verdicts step 3b)

class-initializer:conformance.Conformance$Quiet.<clinit>()V
  call: conformance.Conformance$Quiet.<clinit>()
  modifies: nothing
  written-by: an agent (claude-opus-5-5, sound-verdicts step 3b)

class-initializer:conformance.Conformance$Boom.<clinit>()V
  call: conformance.Conformance$Boom.<clinit>()
  throws: IllegalStateException when true
  modifies: nothing
  written-by: an agent (claude-opus-5-5, sound-verdicts step 3b)
";

/// The corpus's contracts, for the JDK the tests run on.
fn corpus_contracts() -> PathBuf {
    let dir = target_tmp().join("conformance-contracts");
    std::fs::create_dir_all(&dir).unwrap();
    let file = dir.join("corpus.contracts");
    let jdk = jvmcontract::bmc::gaps::jdk_release().map(|v| format!("jdk-{v}")).unwrap_or_default();
    std::fs::write(&file, CORPUS_CONTRACTS.replace("{jdk}", &jdk)).unwrap();
    file
}

fn prove(case: &Case, claim: &Claim, index: usize, (engine, gaps, confirm, contracts): Mode, classes: &Path) -> property::Outcome {
    let mut options = property::Options::new(std::slice::from_ref(&classes.to_path_buf()), &format!("{CLASS}#{}", case.method));
    options.assume = claim.assume.map(str::to_string);
    options.assert = Some(claim.assert.to_string());
    options.throws = claim.throws.iter().map(|s| s.to_string()).collect();
    options.engine = engine;
    options.gaps = gaps;
    options.confirm = confirm;
    options.contracts = contracts.then(corpus_contracts);
    let work = target_tmp().join(format!("conformance-{engine:?}-{gaps:?}{}{}", if confirm { "-confirm" } else { "" }, if contracts { "-contracts" } else { "" })).join(format!("{}-{index}", case.method));
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
fn conformance(engines: &[Mode], recorded: bool) -> Option<Vec<String>> {
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
            for &(engine, gaps, confirm, contracts) in engines {
                let outcome = prove(case, claim, k, (engine, gaps, confirm, contracts), &compiled.classes);
                runs.push(Run { case: c, claim: k, engine, gaps, confirm, contracts, outcome });
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
    let mut advised = Vec::new();
    let mut contracted = Vec::new();
    for run in &runs {
        let case = &corpus[run.case];
        let claim = &case.claims[run.claim];
        let refuted = refuted_on_the_jvm.contains(&(run.case, run.claim));
        let label = format!("{} [{}]", case.method, claim_text(claim));
        let verdict = run.outcome.verdict;
        let confirmation = run.outcome.search.as_ref().and_then(|s| s.confirmation.as_ref()).map(|c| c.status);
        let _ = writeln!(table, "{:<16} {:?}/{:?}{}{} {:<12} {}", case.method, run.engine, run.gaps, if run.contracts { "+contracts" } else { "" }, confirmation.map(|c| format!(" {c:?}")).unwrap_or_default(), format!("{verdict:?}"), claim_text(claim));
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
        // A confirmation is JBMC's word on the own checker's proof, and the JVM is the judge of both.
        match (refuted, confirmation) {
            (true, Some(Confirmed::Confirmed)) => failures.push(format!("{label}: JBMC confirms a proof of the own checker's under --gaps {:?}, and the JVM refutes it: {}", run.gaps, run.outcome.output)),
            (false, Some(Confirmed::Disagreed)) => failures.push(format!("{label}: JBMC disagrees with a proof of the own checker's under --gaps {:?}, and the JVM does not refute it: {}", run.gaps, run.outcome.output)),
            _ => {}
        }
        if confirmation == Some(Confirmed::Disagreed) && verdict != Verdict::Unverifiable {
            failures.push(format!("{label}: the engines disagree, and the verdict is {verdict:?}"));
        }
        if run.confirm && confirmation.is_none() && verdict == Verdict::Verified && run.outcome.search.as_ref().is_some_and(|s| s.engine == "native") {
            failures.push(format!("{label}: --confirm left no confirmation on a proof of the own checker's"));
        }
        if recorded && run.engine == Engine::Native && run.gaps == GapMode::Strict && verdict != claim.native {
            failures.push(format!("{label}: the native engine says {verdict:?} where the corpus records {:?}: {}", claim.native, run.outcome.output));
        }
        if recorded && run.engine == Engine::Native && run.gaps == GapMode::Assume && gaps == 0 && claim.native != Verdict::Unverifiable && verdict != claim.native {
            failures.push(format!("{label}: with no gap met, --gaps assume says {verdict:?} where strict says {:?}", claim.native));
        }
        // Advised is strict given no contracts: with no gap in what the harness reaches it goes on as strict does,
        // and otherwise it stops before solving, with advice.
        if recorded && run.engine == Engine::Native && run.gaps == GapMode::Advised && !run.contracts {
            match &run.outcome.advice {
                None if verdict != claim.native => failures.push(format!("{label}: with no gap in the harness, --gaps advised says {verdict:?} where strict says {:?}", claim.native)),
                Some(_) if verdict != Verdict::Unverifiable || run.outcome.search.is_some() => failures.push(format!("{label}: --gaps advised gave advice and solved anyway: {}", run.outcome.output)),
                // The scan may see a gap on a path no input takes; on this corpus it sees none strict does not meet.
                Some(_) if claim.native != Verdict::Unverifiable => failures.push(format!("{label}: --gaps advised asks for contracts where strict decides the claim ({:?}): {}", claim.native, run.outcome.output)),
                Some(a) => advised.push(format!("{} ({}; strict: {:?})", case.method, a.gaps.iter().map(|g| g.id.split('@').next().unwrap()).collect::<Vec<_>>().join(", "), claim.native)),
                None => {}
            }
        }
        // With contracts that state what the JVM does, a gap they close is decided as the JVM decides it: no
        // `Verified` it refutes, a violation it reproduces (step 3 above), and a claim with no gap as strict.
        if run.contracts {
            let closed = run.outcome.search.as_ref().map(|s| s.gaps.iter().filter(|g| g.treatment == Some(GapTreatment::Contract)).count()).unwrap_or(0);
            if refuted && verdict == Verdict::Verified {
                failures.push(format!("{label}: Verified with the corpus's contracts, and the JVM refutes it: {}", run.outcome.output));
            }
            if recorded && closed == 0 && run.outcome.advice.is_none() && verdict != claim.native {
                failures.push(format!("{label}: with no contract applied, --contracts says {verdict:?} where strict says {:?}", claim.native));
            }
            if closed > 0 {
                contracted.push(format!("{} {verdict:?} (strict: {:?})", case.method, claim.native));
            }
            // They state what the JVM does, so a JVM test refutes none of them, and each is tested (step 3c).
            for g in run.outcome.search.iter().flat_map(|s| &s.gaps).filter(|g| g.treatment == Some(GapTreatment::Contract)) {
                let evidence = g.contract.as_ref().map(|c| c.evidence);
                if evidence != Some(jvmcontract::gap_contracts::Evidence::Tested) {
                    failures.push(format!("{label}: the corpus's contract for {} is {evidence:?}, not tested: {}", g.id, run.outcome.output));
                }
            }
            if let Some(refused) = run.outcome.advice.iter().flat_map(|a| &a.gaps).find_map(|g| g.refused_contract.as_ref().filter(|r| r.starts_with("a JVM refutes it"))) {
                failures.push(format!("{label}: a JVM refutes one of the corpus's contracts: {refused}"));
            }
        }
    }
    eprintln!("{table}");
    let claims: usize = corpus.iter().map(|c| c.claims.len()).sum();
    let refuted = corpus.iter().flat_map(|c| &c.claims).filter(|c| c.refuted).count();
    eprintln!("{} cases, {claims} claims ({refuted} refuted on the JVM), {} runs; the interpreter refuses {}", corpus.len(), runs.len(), refused.join(", "));
    if !advised.is_empty() {
        eprintln!("--gaps advised asks for contracts on {} claims: {}", advised.len(), advised.join("; "));
    }
    if !contracted.is_empty() {
        eprintln!("the corpus's contracts close the gaps of {} claims: {}", contracted.len(), contracted.join("; "));
    }
    Some(failures)
}

/// Under strict, the tool's own checker gives no `Verified` the JVM refutes, and each of its violations is one the
/// JVM reproduces; under assume it gives `Verified` for a refuted claim only when it names the gap it assumed.
#[test]
fn the_corpus_agrees_with_the_jvm_on_the_tools_own_checker() {
    let Some(failures) = conformance(&[(Engine::Native, GapMode::Strict, false, false), (Engine::Native, GapMode::Assume, false, false), (Engine::Native, GapMode::Advised, false, false), (Engine::Native, GapMode::Advised, false, true)], true) else { return };
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
    let Some(failures) = conformance(&[(Engine::Jbmc, GapMode::Strict, false, false), (Engine::Auto, GapMode::Strict, false, false)], false) else { return };
    assert!(failures.is_empty(), "{} disagreements with the JVM:\n{}", failures.len(), failures.join("\n"));
}

/// `--engine auto --confirm` under strict and assume, on the same corpus: JBMC proves again every claim the own
/// checker proved, a pipeline job like the one above. Under assume, JBMC runs the class initializers the own checker
/// assumes ran, so a claim a throwing one refutes is a disagreement, and a claim that assumed a JDK call is not
/// sent to JBMC. A JBMC confirmation of a claim the JVM refutes fails, as does a disagreement over one it does not.
#[test]
#[ignore = "runs JBMC on every claim the own checker proves: a pipeline job"]
fn the_corpus_agrees_with_the_jvm_under_auto_confirm() {
    if !has("jbmc") {
        return;
    }
    let Some(failures) = conformance(&[(Engine::Auto, GapMode::Strict, true, false), (Engine::Auto, GapMode::Assume, true, false)], false) else { return };
    assert!(failures.is_empty(), "{} disagreements with the JVM:\n{}", failures.len(), failures.join("\n"));
}

/// A stand-in for JBMC that answers every run with `answer.txt` next to it and keeps the arguments it was given in
/// `args.txt`: what `--confirm` does with each answer is then tested without running JBMC.
fn fake_jbmc(name: &str) -> PathBuf {
    let dir = target_tmp().join(format!("fake-jbmc-{name}"));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let script = dir.join("jbmc");
    std::fs::write(&script, "#!/bin/sh\nif [ \"$1\" = --version ]; then echo 6.11.0; exit 0; fi\nd=$(dirname \"$0\")\necho \"$@\" > \"$d/args.txt\"\ncat \"$d/answer.txt\"\n").unwrap();
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(&script, std::fs::Permissions::from_mode(0o755)).unwrap();
    script
}

const PROVED: &str = "JBMC version 6.11.0 (cbmc-6.11.0)\n** 0 of 5 failed (1 iterations)\nVERIFICATION SUCCESSFUL\n";
const NO_ANSWER: &str = "JBMC version 6.11.0 (cbmc-6.11.0)\nRunning with 8 object bits\n";

fn refuted_by_jbmc(class: &str, descriptor: &str, input: &str) -> String {
    format!("JBMC version 6.11.0 (cbmc-6.11.0)\n[{class}.check:{descriptor}.assertion.1] line 1 assertion at file {class}.java line 1 function java::{class}.check:{descriptor} bytecode-index 9: FAILURE\n  INPUT arg0a: {input}\n** 1 of 5 failed (2 iterations)\nVERIFICATION FAILED\n")
}

/// `--engine auto --confirm`: a proof of the own checker's that JBMC proves too is confirmed, one JBMC refutes is
/// neither verdict, one JBMC has no verdict on stays the own checker's and says so, and one that assumed a JDK call
/// JBMC would approximate as well is not sent to JBMC. JBMC is a stand-in script here; the real one runs the
/// corpus in the ignored test.
#[test]
fn confirm_reports_what_jbmc_made_of_a_proof_of_the_own_checker() {
    let Some(compiled) = compile() else { return };
    let jbmc = fake_jbmc("confirm");
    let dir = jbmc.parent().unwrap().to_path_buf();
    let answer = |text: &str| {
        std::fs::write(dir.join("answer.txt"), text).unwrap();
        let _ = std::fs::remove_file(dir.join("args.txt"));
    };
    let prove = |method: &str, assert: &str, gaps: GapMode, name: &str| {
        let mut options = property::Options::new(std::slice::from_ref(&compiled.classes), &format!("{CLASS}#{method}"));
        options.assert = Some(assert.to_string());
        options.engine = Engine::Auto;
        options.gaps = gaps;
        options.confirm = true;
        options.jbmc = jbmc.display().to_string();
        let work = target_tmp().join(format!("confirm-{name}"));
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        property::run(&options).unwrap()
    };
    let status = |o: &property::Outcome| o.search.as_ref().and_then(|s| s.confirmation.as_ref()).map(|c| c.status);

    answer(PROVED);
    let confirmed = prove("increment", "result == x + 1", GapMode::Strict, "proved");
    assert_eq!(confirmed.verdict, Verdict::Verified, "{}", confirmed.output);
    assert_eq!(status(&confirmed), Some(Confirmed::Confirmed));
    assert!(confirmed.output.contains("  confirmed: JBMC 6.11.0 proves it too, over every input"), "{}", confirmed.output);
    assert_eq!(confirmed.search.as_ref().unwrap().engine, "native");
    let args = std::fs::read_to_string(dir.join("args.txt")).unwrap();
    assert!(args.contains("PropertyHarness") && !args.contains("--java-assume-inputs-interval"), "one run over every input: {args}");
    let json = serde_json::to_value(&confirmed).unwrap();
    assert_eq!(json["search"]["confirmation"]["status"], "confirmed");

    answer(&refuted_by_jbmc("PropertyHarness", "(I)V", "5"));
    let disagreed = prove("increment", "result == x + 1", GapMode::Strict, "refuted");
    assert_eq!(disagreed.verdict, Verdict::Unverifiable, "neither verdict: {}", disagreed.output);
    assert_eq!(status(&disagreed), Some(Confirmed::Disagreed));
    assert!(disagreed.output.contains("the engines disagree") && disagreed.output.contains("increment(x=5)"), "{}", disagreed.output);
    assert!(disagreed.output.contains("where the harness holds"), "the interpreter runs the witness: {}", disagreed.output);
    assert_eq!(disagreed.findings[0].rule_id, "engines-disagree");
    let witness = disagreed.counterexample.as_ref().expect("JBMC's witness");
    assert_eq!(runner_arguments(&witness.inputs), "5");
    assert!(!disagreed.replay.as_ref().unwrap().reproduced);

    answer(NO_ANSWER);
    let unconfirmed = prove("increment", "result == x + 1", GapMode::Strict, "silent");
    assert_eq!(unconfirmed.verdict, Verdict::Verified, "{}", unconfirmed.output);
    assert_eq!(status(&unconfirmed), Some(Confirmed::NoVerdict));
    assert!(unconfirmed.output.contains("  not confirmed: JBMC 6.11.0 gave no verdict"), "{}", unconfirmed.output);

    // `new ArrayList<>(n)` assumed to return: JBMC has no bytecode for it either, so it is not asked.
    answer(PROVED);
    let assumed = prove("capacity", "result == 1", GapMode::Assume, "assumed");
    assert_eq!(assumed.verdict, Verdict::Verified, "{}", assumed.output);
    assert_eq!(status(&assumed), Some(Confirmed::NotAsked));
    assert!(!dir.join("args.txt").exists(), "JBMC was run");
    assert!(assumed.output.contains("not confirmed: JBMC was not asked, since the tool's own checker assumed java.util.ArrayList.<init>(int)"), "{}", assumed.output);

    // A refutation of the own checker's is its own, whatever JBMC would say: nothing to confirm.
    let refuted = prove("increment", "result > x", GapMode::Strict, "violation");
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    assert_eq!(status(&refuted), None);

    // A regression proof: the same class as both versions, proved rather than taken as identical.
    answer(&refuted_by_jbmc("EquivalenceHarness", "(I)V", "7"));
    let mut options = jvmcontract::equivalence::Options::new(&compiled.classes, &compiled.classes, &format!("{CLASS}#increment"));
    options.engine = Engine::Auto;
    options.confirm = true;
    options.shared_callees = false;
    options.jbmc = jbmc.display().to_string();
    let work = target_tmp().join("confirm-equivalence");
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    let equivalence = jvmcontract::equivalence::run(&options).unwrap();
    assert_eq!(equivalence.verdict, Verdict::Unverifiable, "{}", equivalence.output);
    assert_eq!(equivalence.search.as_ref().and_then(|s| s.confirmation.as_ref()).map(|c| c.status), Some(Confirmed::Disagreed));
    assert!(equivalence.output.contains("increment(x=7)") && equivalence.output.contains("before in the interpreter: 8"), "{}", equivalence.output);

    // The command line has --confirm under --engine auto only.
    let cli = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).args(["prove", "--classes"]).arg(&compiled.classes).args([&format!("{CLASS}#increment"), "--assert", "result == x + 1", "--engine", "native", "--confirm"]).output().unwrap();
    assert!(!cli.status.success());
    assert!(String::from_utf8_lossy(&cli.stderr).contains("--confirm needs --engine auto"), "{}", String::from_utf8_lossy(&cli.stderr));
}

/// Step 2a of the brief: the statement a verdict is about is data, and two verdicts that differ only in their
/// domain, observations, assumptions or models say so in that part and no other.
#[test]
fn the_statement_says_what_a_verdict_is_about() {
    use jvmcontract::statement::{AssumptionKind, Basis, ParameterKind, Statement};
    let Some(compiled) = compile() else { return };
    let prove = |name: &str, method: &str, assert: &str, set: &dyn Fn(&mut property::Options)| {
        let mut options = property::Options::new(std::slice::from_ref(&compiled.classes), &format!("{CLASS}#{method}"));
        options.assert = Some(assert.to_string());
        options.engine = Engine::Native;
        set(&mut options);
        let work = target_tmp().join(format!("stated-{name}"));
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        let outcome = property::run(&options).unwrap();
        assert_eq!(outcome.verdict, V, "{}", outcome.output);
        outcome.stated.clone().expect("a statement")
    };
    // The parts of a statement other than the one named, for comparing two statements but for it.
    let but = |s: &Statement, part: &str| {
        let mut json = serde_json::to_value(s).unwrap();
        json.as_object_mut().unwrap().remove(part);
        if part == "domain" {
            json["bounds"].as_object_mut().unwrap().remove("max_array_length");
        }
        json
    };

    let plain = prove("plain", "increment", "result == x + 1", &|_| {});
    assert_eq!(plain.kind, "property");
    assert_eq!(plain.domain.text, "x: int");
    assert_eq!(plain.domain.parameters[0].kind, ParameterKind::Primitive);
    assert_eq!(plain.observations.result, "the result and the parameters, against result == x + 1");
    assert_eq!(plain.observations.exceptions, "none may be thrown");
    assert_eq!((plain.checker.engine.as_str(), plain.gap_mode, plain.confirmation), ("native", Some(GapMode::Strict), None));
    assert!(plain.checker.solver.as_deref().is_some_and(|s| s.starts_with("CaDiCaL ")), "{:?}", plain.checker);
    assert!(plain.bounds.complete && plain.bounds.unwind == Some(16) && plain.bounds.max_array_length.is_none());
    assert!(plain.models.used && plain.models.digest.as_deref().is_some_and(|d| d.starts_with("sha256:")));
    assert_eq!(plain.assumptions.iter().map(|a| (a.kind, a.basis)).collect::<Vec<_>>(), [(AssumptionKind::Initialization, Basis::Engine)]);

    // Assumptions: the claim's precondition is one of them, stated by the claim.
    let assuming = prove("assume", "increment", "result > x", &|o| o.assume = Some("x < 100".into()));
    assert_eq!((assuming.assumptions[0].kind, assuming.assumptions[0].basis, assuming.assumptions[0].text.as_str()), (AssumptionKind::Precondition, Basis::Stated, "x < 100"));
    // Observations: what the result is checked against.
    let other = prove("observed", "increment", "result != x", &|_| {});
    assert_ne!(other.observations, plain.observations);
    assert_eq!(but(&other, "observations"), but(&plain, "observations"));
    // The model bundle: without the tool's models, no digest.
    let unmodelled = prove("models", "increment", "result == x + 1", &|o| o.models = false);
    assert_eq!((unmodelled.models.used, unmodelled.models.digest.as_deref()), (false, None));
    assert_eq!(but(&unmodelled, "models"), but(&plain, "models"));
    // The domain: the arrays' bound, which the bounds repeat.
    let eight = prove("eight", "length", "result <= 8", &|_| {});
    let four = prove("four", "length", "result <= 8", &|o| o.max_array_length = 4);
    assert_eq!(eight.domain.text, "a: int[] of length ≤ 8, not null");
    assert_eq!(four.domain.parameters[0].max_length, Some(4));
    assert_eq!((four.domain.parameters[0].null, four.bounds.max_array_length), (false, Some(4)));
    assert_eq!(but(&four, "domain"), but(&eight, "domain"));
    // A gap assumed is an assumption with its id, on nothing but the approximation.
    let gap = prove("gap", "capacity", "result == 1", &|o| o.gaps = GapMode::Assume);
    let assumed = gap.assumptions.iter().find(|a| a.kind == AssumptionKind::Gap).expect("the gap");
    assert_eq!(assumed.basis, Basis::Assumed);
    assert!(assumed.id.as_deref().is_some_and(|id| id.starts_with("jdk-constructor:java.util.ArrayList.<init>(I)V")), "{assumed:?}");
    assert_eq!(gap.gap_mode, Some(GapMode::Assume));

    // A regression proof: two arrays, each its own, and what the versions leave in them observed.
    let regress = |name: &str, method: &str, set: &dyn Fn(&mut jvmcontract::equivalence::Options)| {
        let mut options = jvmcontract::equivalence::Options::new(&compiled.classes, &compiled.classes, &format!("{CLASS}#{method}"));
        options.engine = Engine::Native;
        options.shared_callees = false;
        set(&mut options);
        let work = target_tmp().join(format!("stated-{name}"));
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        let outcome = jvmcontract::equivalence::run(&options).unwrap();
        assert_eq!(outcome.verdict, V, "{}", outcome.output);
        outcome
    };
    let arrays = regress("arrays", "twoArrays", &|_| {}).stated.unwrap();
    assert_eq!(arrays.kind, "regression");
    assert_eq!(arrays.domain.text, "a: int[] of length ≤ 8, not null × b: int[] of length ≤ 8, not null; no two the same array");
    assert!(!arrays.domain.shared_arrays);
    assert_eq!(arrays.observations.arrays, ["a", "b"]);
    assert_eq!(arrays.observations.result, "the result, equal in both versions");
    assert!(arrays.observations.exceptions.contains("exception classes"), "{}", arrays.observations.exceptions);
    // A scope and a relation between the results.
    let scoped = regress("scoped", "increment", &|o| {
        o.unchanged_unless = Some("x == 0".into());
        o.results_agree_when = Some("previous == result".into());
    })
    .stated
    .unwrap();
    assert_eq!((scoped.assumptions[0].kind, scoped.assumptions[0].basis), (AssumptionKind::IntendedInputs, Basis::Stated));
    assert!(scoped.assumptions[0].text.starts_with("!(x == 0)"), "{:?}", scoped.assumptions[0]);
    assert_eq!(scoped.observations.result, "the results, related by previous == result whenever both versions return");
    // Identical bytecode: no checker ran, and no model was read.
    let identical = regress("identical", "increment", &|o| o.shared_callees = true);
    let s = identical.stated.unwrap();
    assert_eq!((s.checker.engine.as_str(), s.models.used, s.bounds.unwind, s.gap_mode), ("none", false, None, None));
    let json = serde_json::to_value(regress("json", "twoArrays", &|_| {})).unwrap();
    assert_eq!(json["stated"]["domain"]["parameters"][0]["kind"], "array");
    assert_eq!(json["stated"]["assumptions"][0]["basis"], "engine");
}

/// Vacuity as a status (step 2b): a verified statement says whether it is about any input, and how that is known.
/// Nothing skipped before the calls is non-vacuous by the harness; a precondition, a scope or a record's constructor
/// is probed, and the probe's witness, its proof (vacuous) or its lack of a verdict (unknown) is the status. A record
/// built through its constructor carries the caveat that the constructors' agreement is another statement.
#[test]
fn vacuity_is_a_status_of_a_verified_statement() {
    use jvmcontract::statement::{AssumptionKind, VacuityBasis, VacuityStatus};
    let Some(compiled) = compile() else { return };
    let prove = |name: &str, assume: Option<&str>| {
        let mut options = property::Options::new(std::slice::from_ref(&compiled.classes), &format!("{CLASS}#increment"));
        options.assert = Some("result > x".to_string());
        options.assume = assume.map(str::to_string);
        options.engine = Engine::Native;
        let work = target_tmp().join(format!("vacuity-{name}"));
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        let outcome = property::run(&options).unwrap();
        assert_eq!(outcome.verdict, V, "{}", outcome.output);
        outcome
    };
    let status = |s: &Option<jvmcontract::statement::Statement>| {
        let v = s.as_ref().and_then(|s| s.vacuity.clone()).expect("a vacuity status");
        (v.status, v.basis, v.witness, v.text)
    };

    // A precondition some input satisfies: probed, and the probe's witness is the evidence.
    let every = prove("assumed", Some("x < 2147483647"));
    let (st, basis, witness, _) = status(&every.stated);
    assert_eq!((st, basis), (VacuityStatus::NonVacuous, VacuityBasis::Probe), "{}", every.output);
    let witness = witness.expect("the probe's witness");
    assert!(witness.starts_with("increment(x="), "{witness}");
    assert!(every.output.contains(&format!("\n  not vacuous: {witness} reaches the calls\n")), "{}", every.output);
    assert!(every.vacuous.is_none());
    // No precondition: every input reaches the call, and nothing needs probing.
    let mut options = property::Options::new(std::slice::from_ref(&compiled.classes), &format!("{CLASS}#increment"));
    options.assert = Some("result == x + 1".to_string());
    options.engine = Engine::Native;
    options.work = Some(target_tmp().join("vacuity-plain"));
    let plain = property::run(&options).unwrap();
    assert_eq!(status(&plain.stated).0, VacuityStatus::NonVacuous);
    assert_eq!(status(&plain.stated).1, VacuityBasis::Harness);
    assert!(!plain.output.contains("vacuous"), "{}", plain.output);

    // A precondition no input satisfies: vacuous, and `vacuous` keeps its reason for the readers it had.
    let none = prove("none", Some("x > 0 && x < 0"));
    let (st, basis, _, text) = status(&none.stated);
    assert_eq!((st, basis), (VacuityStatus::Vacuous, VacuityBasis::Probe));
    assert!(none.vacuous.as_deref().is_some_and(|r| text.contains(r)), "{text}");
    assert!(none.output.contains("\n  vacuously: no input in the domain reaches the calls"), "{}", none.output);
    let json = serde_json::to_value(&none).unwrap();
    assert_eq!((json["stated"]["vacuity"]["status"].as_str(), json["stated"]["vacuity"]["basis"].as_str()), (Some("vacuous"), Some("probe")));

    // A violation has no status: its witness is an input that reaches the calls.
    let mut options = property::Options::new(std::slice::from_ref(&compiled.classes), &format!("{CLASS}#increment"));
    options.assert = Some("result > x".to_string());
    options.engine = Engine::Native;
    options.work = Some(target_tmp().join("vacuity-violation"));
    let refuted = property::run(&options).unwrap();
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    assert!(refuted.stated.as_ref().unwrap().vacuity.is_none());
    assert!(serde_json::to_value(&refuted).unwrap()["stated"].get("vacuity").is_none());

    // A record built through its constructor: probed, and the caveat about the constructors stated.
    let regress = |name: &str, target: &str, set: &dyn Fn(&mut jvmcontract::equivalence::Options)| {
        let mut options = jvmcontract::equivalence::Options::new(&compiled.classes, &compiled.classes, &format!("{CLASS}${target}"));
        options.engine = Engine::Native;
        options.shared_callees = false;
        set(&mut options);
        let work = target_tmp().join(format!("vacuity-{name}"));
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        jvmcontract::equivalence::run(&options).unwrap()
    };
    let span = regress("span", "Range#span", &|_| {});
    assert_eq!(span.verdict, V, "{}", span.output);
    let (st, basis, witness, _) = status(&span.stated);
    assert_eq!((st, basis), (VacuityStatus::NonVacuous, VacuityBasis::Probe), "{}", span.output);
    assert!(witness.as_deref().is_some_and(|w| w.starts_with("span(this=Range[lo=")), "{witness:?}");
    let caveat = span.stated.as_ref().unwrap().assumptions.iter().find(|a| a.kind == AssumptionKind::Constructible).expect("the constructors' caveat");
    assert!(caveat.text.contains("whether the constructors accept the same inputs is not part of it"), "{}", caveat.text);
    assert!(span.output.contains(&format!("\n  constructors: {}\n", caveat.text)), "{}", span.output);
    // A scope every input satisfies: vacuous, records or not.
    let scoped = regress("span-scoped", "Range#span", &|o| o.unchanged_unless = Some("this.lo <= this.hi".into()));
    assert_eq!(status(&scoped.stated).0, VacuityStatus::Vacuous, "{}", scoped.output);
    // Identical bytecode, constructors included: no caveat, and every input in the domain is covered.
    let identical = regress("span-identical", "Range#span", &|o| o.shared_callees = true);
    let s = identical.stated.as_ref().unwrap();
    assert_eq!(s.checker.engine, "none", "{}", identical.output);
    assert!(s.assumptions.iter().all(|a| a.kind != AssumptionKind::Constructible), "{:?}", s.assumptions);
    assert_eq!(status(&identical.stated).1, VacuityBasis::Identical);
    assert!(!identical.output.contains("constructors:"), "{}", identical.output);

    // Unknown: JBMC (a stand-in here) proves a statement over records whose constructor meets a gap, which the own
    // checker's probe refuses under strict.
    let jbmc = fake_jbmc("vacuity");
    std::fs::write(jbmc.parent().unwrap().join("answer.txt"), PROVED).unwrap();
    let sized = regress("sized", "Sized#twice", &|o| {
        o.engine = Engine::Jbmc;
        o.jbmc = jbmc.display().to_string();
    });
    assert_eq!(sized.verdict, V, "{}", sized.output);
    let (st, basis, witness, text) = status(&sized.stated);
    assert_eq!((st, basis, witness), (VacuityStatus::Unknown, VacuityBasis::Probe, None), "{}", sized.output);
    assert!(text.contains("jdk-constructor:java.util.ArrayList.<init>(I)V"), "{text}");
    assert!(sized.output.contains("\n  vacuity unknown: the tool's own checker gave no verdict on whether any input in the domain reaches the calls ("), "{}", sized.output);
}
