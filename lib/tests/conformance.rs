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
const NPE: &str = "throws java.lang.NullPointerException";
const UOE: &str = "throws java.lang.UnsupportedOperationException";

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
        Case::new("boom", &[("3", "throws java.lang.ExceptionInInitializerError")]).refuted(None, "result == n", &[], X),
        Case::new("inherited", &[("3", "throws java.lang.ExceptionInInitializerError")]).refuted(None, "result == n", &[], X),
        Case::new("quiet", &[("3", "returns 3")]).holds(None, "result == n", &[], V),
        // Class initialization (Phase 5 of llm-dlc/loops/engine-priorities.md).
        Case::new("counter", &[("3", "returns 8")]).holds(None, "result == n + 5", &[], V).refuted(None, "result == n", &[], X),
        Case::new("constructed", &[("3", "returns 6")]).holds(None, "result == n + 3", &[], V).refuted(None, "result == n + 1", &[], X),
        Case::new("superFirst", &[("3", "returns 12")]).holds(None, "result == 12", &[], V).refuted(None, "result == 21", &[], X),
        Case::new("cycle", &[("3", "returns 5")]).holds(None, "result == n + 2", &[], V).refuted(None, "result == n + 1", &[], X),
        Case::new("declaring", &[("3", "returns 10")]).holds(None, "result == n + 7", &[], V).refuted(None, "result == n + 107", &[], X),
        Case::new("defaults", &[("3", "returns 3")]).holds(None, "result == 3", &[], V).refuted(None, "result == 34", &[], X),
        Case::new("fatal", &[("3", "returns 2")]).holds(None, "result == 2", &[], V).refuted(None, "result == 1", &[], X),
        Case::new("boomTwice", &[("3", "returns 2")]).holds(None, "result == 2", &[], V).refuted(None, "result == 1", &[], X),
        // Enums and immutable lists (Phase 5 of llm-dlc/loops/engine-priorities.md): the calls lib/models models for
        // JBMC alone ([`ON_THE_MODELS`]), as the JVM runs them.
        Case::new("enumState", &[("0", "returns 3"), ("1", "returns 17"), ("5", "returns 23")]).holds(Some("n == 1"), "result == 17", &[], V).refuted(None, "result < 20", &[], X),
        // Enums in the own checker (Phase 5, its last step): `$VALUES` at an index that is an input, a switch through
        // javac's `$SwitchMap` class, constants with bodies and a field named as `Enum`'s private one, an enum whose
        // initializer throws, and `valueOf`, which stays a gap (`Enum.valueOf(Class, String)` is reflection).
        Case::new("enumValues", &[("0", "returns 1003"), ("2", "returns 1023"), ("3", "throws java.lang.ArrayIndexOutOfBoundsException"), ("-1", "throws java.lang.ArrayIndexOutOfBoundsException")])
            .holds(None, "result == 1003 + n * 10", &["ArrayIndexOutOfBoundsException when n < 0 || n > 2"], V)
            .refuted(Some("n >= 0 && n <= 2"), "result < 1020", &[], X),
        Case::new("enumSwitch", &[("0", "returns 10"), ("1", "returns 21"), ("101", "returns 32"), ("-7", "returns 21")]).holds(Some("n > 100"), "result == 32", &[], V).refuted(None, "result != 21", &[], X),
        Case::new("enumBodies", &[("5", "returns 1160"), ("0", "returns 1181"), ("-3", "returns 1151")])
            .holds(Some("n > 0 && n < 1000"), "result == n * 10 + 1110", &[], V)
            .refuted(Some("n <= 0 && n > -1000"), "result == 1181", &[], X),
        Case::new("enumBroken", &[("3", "returns 12")]).holds(None, "result == 12", &[], V).refuted(None, "result == 13", &[], X),
        Case::new("enumValueOf", &[("4", "returns 5")]).holds(None, "result == n + 1", &[], U).refuted(None, "result == n", &[], U),
        Case::new("listSizes", &[("0", "returns 1"), ("1", "returns 10"), ("2", "returns 20"), ("3", "returns 30"), ("-4", "returns 30")])
            .holds(Some("n >= 1 && n <= 3"), "result == n * 10", &[], U)
            .refuted(None, "result >= 10", &[], U),
        Case::new("listNull", &[("0", NPE), ("1", NPE), ("2", "returns 5")]).holds(Some("n > 1"), "result == 5", &[], U).refuted(None, "result == 5", &[], U),
        Case::new("listChange", &[("0", "returns 1"), ("1", UOE), ("2", UOE), ("3", UOE), ("4", UOE), ("5", UOE), ("6", UOE), ("7", UOE), ("8", "returns 1"), ("10", "returns 3"), ("13", UOE), ("-1", "returns 1")])
            .holds(Some("n == 0 || n == 8"), "result == 1", &[], U)
            .refuted(None, "result >= 1", &[], U),
        Case::new("listCopySame", &[("0", "returns 3"), ("1", "returns 3"), ("2", "returns 3")]).holds(None, "result == 3", &[], U).refuted(None, "result == 1", &[], U),
        Case::new("listCopyMutable", &[("0", "returns 1"), ("1", "returns 10"), ("2", NPE), ("9", NPE)])
            .holds(Some("n <= 0"), "result == 1", &[], U)
            .refuted(None, "result <= 10", &[], U),
        Case::new("listGet", &[("0", "returns 1"), ("1", "throws java.lang.IndexOutOfBoundsException"), ("-1", "throws java.lang.IndexOutOfBoundsException"), ("10", "returns 2"), ("12", "returns 1"), ("13", "throws java.lang.ArrayIndexOutOfBoundsException"), ("20", "throws java.lang.ArrayIndexOutOfBoundsException")])
            .holds(Some("n == 0 || n == 12"), "result == 1", &[], U)
            .refuted(None, "result >= 1", &[], U),
        Case::new("listSearch", &[("0", NPE), ("2", "returns -1089"), ("5", "returns 90"), ("7", "returns -1110")])
            .holds(Some("n == 5"), "result == 90", &[], U)
            .refuted(None, "result < 0", &[], U),
        Case::new("listEquals", &[("2", "returns 11"), ("3", "returns 0")]).holds(Some("n != 2"), "result == 0", &[], U).refuted(None, "result == 0", &[], U),
        Case::new("listIterate", &[("0", "returns 6"), ("1", "throws java.util.NoSuchElementException")]).holds(Some("n <= 0"), "result == 6", &[], U).refuted(None, "result == 6", &[], U),
        Case::new("listOfArray", &[("0", "returns 111"), ("9", NPE)]).holds(Some("n != 9"), "result == 111", &[], U).refuted(None, "result == 111", &[], U),
        // Exceptions.
        Case::new("finallyWins", &[("0", "returns 2"), ("1", "returns 2")]).holds(None, "result == 2", &[], V).refuted(None, "result == 1", &[], X),
        Case::new("caught", &[("0", "returns -1"), ("5", "returns 2")]).holds(None, "n != 0 || result == -1", &[], V).refuted(None, "result != -1", &[], X)
            // JBMC 6.11.0 computes the returned quotient past the handler, so it proved this (tests/fixtures/jbmc-defects).
            .refuted(None, "result == 10 / n", &["ArithmeticException when n == 0"], X),
        Case::new("caughtAsRuntime", &[("0", "returns -1"), ("5", "returns 2")]).holds(None, "n != 0 || result == -1", &[], V).refuted(None, "result == 10 / n", &["ArithmeticException when n == 0"], X),
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
        // JBMC 6.11.0 right-shifts by the whole distance, unmasked: it proved the third claim of each (an
        // `unmasked-shift` defect, which its preflight now names and refuses a proof through).
        Case::new("shiftRight", &[("-1;7", "returns -1"), ("-1;33", "returns -1"), ("4;33", "returns 2")])
            .holds(Some("x == -1"), "result == -1", &[], V)
            .refuted(Some("s == 33"), "result == x / 2", &[], X)
            .refuted(Some("s == 33"), "result == 0 || result == -1", &[], X),
        Case::new("shiftUnsigned", &[("-1;32", "returns -1"), ("-1;1", "returns 2147483647")])
            .refuted(Some("x < 0 && s == 32"), "result > 0", &[], X)
            .holds(Some("x < 0 && s == 1"), "result > 0", &[], V)
            .refuted(Some("s == 32"), "result == 0", &[], X),
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
#[derive(Clone)]
struct Compiled {
    classes: PathBuf,
    runner: PathBuf,
}

/// The corpus and the runner, compiled once for every test of the run: the tests run in parallel, and one that
/// compiled again would delete the classes another is reading.
fn compile() -> Option<Compiled> {
    static COMPILED: std::sync::OnceLock<Option<Compiled>> = std::sync::OnceLock::new();
    COMPILED.get_or_init(compile_now).clone()
}

fn compile_now() -> Option<Compiled> {
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
    contracts: Contracts,
    outcome: property::Outcome,
}

/// Where a run under advised takes contracts for its gaps from.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Contracts {
    /// Nowhere: advised is strict given no contracts (`--no-contract-library`).
    None,
    /// The corpus's file (`--contracts`), and not the library.
    File,
    /// The contract library alone, whose records the run applies without checking them again (step 3d).
    Library,
}

/// An engine, a gap mode, whether a proof of the own checker's is confirmed by JBMC (`--confirm`), and where the
/// contracts come from under advised.
type Mode = (Engine, GapMode, bool, Contracts);

/// Contracts for the corpus's gaps, each stating what the JDK's call does as the corpus's calls show it on the JVM
/// (step 3b of the sound-verdicts brief), written by an agent: the session that wrote the step. The initializers'
/// contracts close nothing since Phase 5 of llm-dlc/loops/engine-priorities.md: the own checker runs those
/// initializers, so they are no gaps, and the claims are decided as under strict. Since 3c each is tested on the JVM
/// before it is applied, and the test fails if one is refuted or left untested.
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
    options.contracts = (contracts == Contracts::File).then(corpus_contracts);
    options.contract_library = contracts == Contracts::Library;
    let work = target_tmp().join(format!("conformance-{engine:?}-{gaps:?}{}{}", if confirm { "-confirm" } else { "" }, match contracts { Contracts::None => "", Contracts::File => "-contracts", Contracts::Library => "-library" })).join(format!("{}-{index}", case.method));
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
        let _ = writeln!(table, "{:<16} {:?}/{:?}{}{} {:<12} {}", case.method, run.engine, run.gaps, match run.contracts { Contracts::None => "", Contracts::File => "+contracts", Contracts::Library => "+library" }, confirmation.map(|c| format!(" {c:?}")).unwrap_or_default(), format!("{verdict:?}"), claim_text(claim));
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
        if recorded && run.engine == Engine::Native && run.gaps == GapMode::Advised && run.contracts == Contracts::None {
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
        if run.contracts != Contracts::None {
            let closed = run.outcome.search.as_ref().map(|s| s.gaps.iter().filter(|g| g.treatment == Some(GapTreatment::Contract)).count()).unwrap_or(0);
            if refuted && verdict == Verdict::Verified {
                failures.push(format!("{label}: Verified with the corpus's contracts, and the JVM refutes it: {}", run.outcome.output));
            }
            if recorded && closed == 0 && run.outcome.advice.is_none() && verdict != claim.native {
                failures.push(format!("{label}: with no contract applied, --contracts says {verdict:?} where strict says {:?}", claim.native));
            }
            if closed > 0 {
                contracted.push(format!("{} {:?} {verdict:?} (strict: {:?})", case.method, run.contracts, claim.native));
            }
            // They state what the JVM does, so a JVM test refutes none of them, and each is tested (step 3c).
            for g in run.outcome.search.iter().flat_map(|s| &s.gaps).filter(|g| g.treatment == Some(GapTreatment::Contract)) {
                let evidence = g.contract.as_ref().map(|c| c.evidence);
                if evidence != Some(jvmcontract::gap_contracts::Evidence::Tested) {
                    failures.push(format!("{label}: the corpus's contract for {} is {evidence:?}, not tested: {}", g.id, run.outcome.output));
                }
                // The library's are applied on their records, which the run does not check again (step 3d).
                let on_record = g.contract.as_ref().is_some_and(|c| c.recorded.is_some() && c.file.starts_with(jvmcontract::contract_library::ORIGIN));
                if (run.contracts == Contracts::Library) != on_record {
                    failures.push(format!("{label}: the contract for {} is {}the library's, on its record: {}", g.id, if on_record { "" } else { "not " }, run.outcome.output));
                }
                if run.contracts == Contracts::Library && run.outcome.work.join("contract-tests").exists() {
                    failures.push(format!("{label}: the library's contracts were tested again on the JVM, where their records hold"));
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
        eprintln!("contracts close the gaps of {} claims (the corpus's, then the library's): {}", contracted.len(), contracted.join("; "));
    }
    Some(failures)
}

/// Under strict, the tool's own checker gives no `Verified` the JVM refutes, and each of its violations is one the
/// JVM reproduces; under assume it gives `Verified` for a refuted claim only when it names the gap it assumed.
#[test]
fn the_corpus_agrees_with_the_jvm_on_the_tools_own_checker() {
    let Some(failures) = conformance(&[(Engine::Native, GapMode::Strict, false, Contracts::None), (Engine::Native, GapMode::Assume, false, Contracts::None), (Engine::Native, GapMode::Advised, false, Contracts::None), (Engine::Native, GapMode::Advised, false, Contracts::File), (Engine::Native, GapMode::Advised, false, Contracts::Library)], true) else { return };
    assert!(failures.is_empty(), "{} disagreements with the JVM:\n{}", failures.len(), failures.join("\n"));
}

/// The cases whose calls go through the models of `lib/models` that only JBMC runs (`Model::jbmc_only`:
/// `java.lang.Enum`, the factories of `java.util.List` and the immutable lists they return).
const ON_THE_MODELS: &[&str] = &["enumState", "enumValues", "enumSwitch", "enumBodies", "enumBroken", "listSizes", "listNull", "listChange", "listCopySame", "listCopyMutable", "listGet", "listSearch", "listEquals", "listIterate", "listOfArray"];

/// The models only JBMC runs, run on a JVM. The interpreter keeps its own natives for these classes, so the corpus
/// above checks those natives, and this test checks the models themselves: relocated out of `java.*` (a JVM loads
/// no class of its own there), with the corpus's references to them following, the calls of [`ON_THE_MODELS`] give
/// the outcomes they give on the JDK's own classes.
#[test]
fn the_models_only_jbmc_runs_agree_with_the_jvm() {
    let Some(compiled) = compile() else { return };
    let own: std::collections::BTreeSet<String> = jvmcontract::models::MODELS.iter().filter(|m| m.jbmc_only).map(|m| m.name.to_string()).collect();
    assert!(own.contains("java/lang/Enum") && own.contains("java/util/List"), "{own:?}");
    let relocated = target_tmp().join("conformance-on-the-models");
    let _ = std::fs::remove_dir_all(&relocated);
    let mut renamed = 0;
    for entry in std::fs::read_dir(compiled.classes.join("conformance")).unwrap() {
        let path = entry.unwrap().path();
        let bytes = std::fs::read(&path).unwrap();
        let out = jvmcontract::relocate::class_file(&bytes, &own, "model").unwrap();
        renamed += usize::from(out != bytes);
        let target = relocated.join("conformance").join(path.file_name().unwrap());
        std::fs::create_dir_all(target.parent().unwrap()).unwrap();
        std::fs::write(target, out).unwrap();
    }
    assert!(renamed >= 2, "the corpus and its enum refer to the models");
    for model in jvmcontract::models::MODELS.iter().filter(|m| m.jbmc_only) {
        let target = relocated.join("model").join(format!("{}.class", model.name));
        std::fs::create_dir_all(target.parent().unwrap()).unwrap();
        std::fs::write(target, jvmcontract::relocate::class_file(model.bytes, &own, "model").unwrap()).unwrap();
    }
    let corpus = corpus();
    let mut lines = Vec::new();
    for name in ON_THE_MODELS {
        let case = corpus.iter().find(|c| c.method == *name).unwrap_or_else(|| panic!("{name} is not in the corpus"));
        lines.extend(case.calls.iter().map(|(arguments, _)| format!("call\t{CLASS}#{name}\t{arguments}")));
    }
    let on_the_jdk = on_the_jvm(&compiled, &lines, "on-the-jdk");
    let on_the_models = on_the_jvm(&Compiled { classes: relocated, runner: compiled.runner.clone() }, &lines, "on-the-models");
    let differences: Vec<String> = lines.iter().zip(on_the_jdk.iter().zip(&on_the_models)).filter(|(_, (a, b))| a != b).map(|(line, (a, b))| format!("{}: the JDK's classes: {a}; the models: {b}", line.replace('\t', " "))).collect();
    assert!(differences.is_empty(), "{} calls differ on the models:\n{}", differences.len(), differences.join("\n"));
}

/// The benchmark corpus of step 5a (`lib/benchmark/`) takes its first group from this corpus, as
/// `lib/benchmark/conformance.json`: each claim with its method, the answer the JVM gives (`violation` for a claim
/// one of the case's calls refutes, which the test above checks on a JVM, `verified` otherwise), and the native
/// engine's verdict recorded here. The file must say what the corpus says: `JVMCONTRACT_BLESS=1` writes it.
#[test]
fn the_benchmark_takes_its_first_group_from_this_corpus() {
    let verdict = |v: &Verdict| match v {
        V => "verified",
        X => "violation",
        U => "unverifiable",
    };
    let mut claims = Vec::new();
    for case in corpus() {
        for (i, claim) in case.claims.iter().enumerate() {
            claims.push(serde_json::json!({
                "id": format!("conformance/{}/{}", case.method, i + 1),
                "group": 1,
                "workload": "semantics",
                "kind": "property",
                "target": format!("{CLASS}#{}", case.method),
                "assume": claim.assume,
                "assert": claim.assert,
                "throws": claim.throws,
                "expected": if claim.refuted { "violation" } else { "verified" },
                "basis": if claim.refuted { "a call the corpus lists refutes it on the JVM" } else { "no call the corpus lists refutes it on the JVM, and the corpus states it" },
                "nativeStrict": verdict(&claim.native),
            }));
        }
    }
    let corpus = serde_json::json!({
        "about": "Group 1 of the benchmark corpus: the conformance corpus of lib/tests/conformance.rs, written out by its test the_benchmark_takes_its_first_group_from_this_corpus. Do not edit: change the corpus and run the test with JVMCONTRACT_BLESS=1.",
        "source": "lib/tests/conformance/conformance/Conformance.java",
        "class": CLASS,
        "cases": claims,
    });
    let text = serde_json::to_string_pretty(&corpus).unwrap() + "\n";
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("benchmark/conformance.json");
    if std::env::var("JVMCONTRACT_BLESS").is_ok_and(|v| v == "1") {
        std::fs::write(&path, &text).unwrap();
    }
    let recorded = std::fs::read_to_string(&path).unwrap_or_default();
    assert!(recorded == text, "{} is not the corpus as it is: run this test with JVMCONTRACT_BLESS=1 to write it", path.display());
}

/// JBMC and `--engine auto` under strict, on the same corpus: a pipeline job, since it runs JBMC once or more per
/// claim (`cargo test --release --test conformance -- --ignored`).
#[test]
#[ignore = "runs JBMC on every claim: a pipeline job"]
fn the_corpus_agrees_with_the_jvm_under_jbmc_and_auto() {
    if !has("jbmc") {
        return;
    }
    let Some(failures) = conformance(&[(Engine::Jbmc, GapMode::Strict, false, Contracts::None), (Engine::Auto, GapMode::Strict, false, Contracts::None)], false) else { return };
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
    let Some(failures) = conformance(&[(Engine::Auto, GapMode::Strict, true, Contracts::None), (Engine::Auto, GapMode::Assume, true, Contracts::None)], false) else { return };
    assert!(failures.is_empty(), "{} disagreements with the JVM:\n{}", failures.len(), failures.join("\n"));
}

/// A stand-in for JBMC that answers every run with `answer.txt` next to it and keeps the arguments it was given in
/// `args.txt`: what `--confirm` does with each answer is then tested without running JBMC. Its program, for the
/// preflight, is `goto.txt` next to it where there is one, and otherwise the harness's function alone.
fn fake_jbmc(name: &str) -> PathBuf {
    let dir = target_tmp().join(format!("fake-jbmc-{name}"));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let script = dir.join("jbmc");
    std::fs::write(&script, "#!/bin/sh\nif [ \"$1\" = --version ]; then echo 6.11.0; exit 0; fi\nd=$(dirname \"$0\")\ncase \"$*\" in *--show-goto-functions*) [ -f \"$d/goto.txt\" ] && { cat \"$d/goto.txt\"; exit 0; }; p=; for a in \"$@\"; do [ \"$p\" = --function ] && f=$a; p=$a; done; echo \"check /* java::$f:()V */\"; exit 0;; esac\necho \"$@\" > \"$d/args.txt\"\ncase \"$*\" in *--json-ui*) cat \"$d/answer.json\";; *) cat \"$d/answer.txt\";; esac\n").unwrap();
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(&script, std::fs::Permissions::from_mode(0o755)).unwrap();
    script
}

/// A stand-in for JBMC that answers each interval stage from a file of its own next to it: `small.json` for
/// `[0:20]`, `wide.json` for `[-100000:100000]` and `full.json` for every input. Where `STAGE.sleep` is there
/// instead, the run outlasts any budget. Each run's stage is appended to `calls.txt`.
fn staged_jbmc(name: &str) -> PathBuf {
    let dir = target_tmp().join(format!("staged-jbmc-{name}"));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let script = dir.join("jbmc");
    std::fs::write(&script, "#!/bin/sh\nif [ \"$1\" = --version ]; then echo 6.11.0; exit 0; fi\nd=$(dirname \"$0\")\ncase \"$*\" in *--show-goto-functions*) p=; for a in \"$@\"; do [ \"$p\" = --function ] && f=$a; p=$a; done; echo \"check /* java::$f:()V */\"; exit 0;; esac\ns=full; p=; for a in \"$@\"; do [ \"$p\" = --java-assume-inputs-interval ] && s=$a; p=$a; done\ncase \"$s\" in '[0:20]') s=small;; '[-100000:100000]') s=wide;; esac\necho $s >> \"$d/calls.txt\"\n[ -f \"$d/$s.sleep\" ] && exec sleep 20\ncat \"$d/$s.json\"\n").unwrap();
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(&script, std::fs::Permissions::from_mode(0o755)).unwrap();
    script
}

/// `--jbmc-staging` (step 2a of `llm-dlc/loops/engine-priorities.md`): each policy runs its own interval stages,
/// each on its own budget out of the one deadline, on property proofs and regression checks alike. Only the full
/// range proves, a preliminary stage out of its budget hands on, a violation stops the search, and a witness from
/// the full range is shrunk as any other. JBMC is a stand-in script answering stage by stage.
#[test]
fn jbmcs_staging_policy_picks_the_stages_it_runs_and_their_budgets() {
    use jvmcontract::deadline::Staging;
    let Some(compiled) = compile() else { return };
    let jbmc = staged_jbmc("staging");
    let dir = jbmc.parent().unwrap().to_path_buf();
    // What each stage answers: `None` outlasts its budget.
    let answer = |small: Option<&Answer>, wide: Option<&Answer>, full: &Answer| {
        for (stage, a) in [("small", small), ("wide", wide), ("full", Some(full))] {
            let _ = std::fs::remove_file(dir.join(format!("{stage}.sleep")));
            match a {
                Some(a) => std::fs::write(dir.join(format!("{stage}.json")), &a.json).unwrap(),
                None => std::fs::write(dir.join(format!("{stage}.sleep")), "").unwrap(),
            }
        }
    };
    let calls = || {
        let c = std::fs::read_to_string(dir.join("calls.txt")).unwrap_or_default();
        let _ = std::fs::remove_file(dir.join("calls.txt"));
        c.lines().map(str::to_string).collect::<Vec<_>>().join(" ")
    };
    let work = |name: &str| {
        let work = target_tmp().join(format!("staging-{name}"));
        let _ = std::fs::remove_dir_all(&work);
        Some(work)
    };
    let prove = |staging: Staging, assert: &str, name: &str| {
        let mut options = property::Options::new(std::slice::from_ref(&compiled.classes), &format!("{CLASS}#increment"));
        options.assert = Some(assert.to_string());
        options.jbmc = jbmc.display().to_string();
        options.jbmc_staging = staging;
        options.timeout_seconds = 8;
        options.work = work(&format!("{name}-{staging}"));
        let outcome = property::run(&options).unwrap();
        let search = outcome.search.clone().expect("JBMC's search");
        (outcome, search)
    };
    let regress = |staging: Staging, name: &str| {
        let mut options = jvmcontract::equivalence::Options::new(&compiled.classes, &compiled.classes, &format!("{CLASS}#increment"));
        options.shared_callees = false;
        options.jbmc = jbmc.display().to_string();
        options.jbmc_staging = staging;
        options.timeout_seconds = 8;
        options.work = work(&format!("regress-{name}-{staging}"));
        let outcome = jvmcontract::equivalence::run(&options).unwrap();
        let search = outcome.search.clone().expect("JBMC's search");
        (outcome, search)
    };
    let all = [Staging::Staged, Staging::FullRange, Staging::Tight];
    let expected_calls = |staging: Staging| match staging {
        Staging::Staged => "small wide full",
        Staging::FullRange => "full",
        Staging::Tight => "small full",
    };

    // Every stage proves: each policy runs its stages to the full range, the preliminary ones on their share
    // (an eighth of 8 s staged, a fortieth tight), the last on what is left.
    answer(Some(&proved()), Some(&proved()), &proved());
    for staging in all {
        let (o, search) = prove(staging, "result == x + 1", "proved");
        assert_eq!(o.verdict, V, "{staging}: {}", o.output);
        assert_eq!(calls(), expected_calls(staging), "{staging}");
        assert_eq!(search.staging, Some(staging));
        assert_eq!(search.stage, None, "{staging}: the proof is the full range's");
        let (last, preliminary) = search.runs.split_last().unwrap();
        assert!(last.stage.is_none() && last.budget_seconds > 7.0, "{staging}: {:?}", search.runs);
        let share = if staging == Staging::Tight { 0.2 } else { 1.0 };
        assert!(preliminary.iter().all(|r| r.stage.is_some() && r.budget_seconds <= share && r.ended == "verified"), "{staging}: {:?}", search.runs);
        assert_eq!(serde_json::to_value(&o).unwrap()["search"]["staging"], staging.to_string());

        let (r, search) = regress(staging, "proved");
        assert_eq!(r.verdict, V, "{staging}: {}", r.output);
        assert_eq!(calls(), expected_calls(staging), "{staging}: the regression check follows the same policy");
        assert_eq!(search.staging, Some(staging));
    }

    // `[0:20]` outlasts its budget: it hands on, and the full range still proves.
    answer(None, Some(&proved()), &proved());
    for staging in all {
        let (o, search) = prove(staging, "result == x + 1", "slow");
        assert_eq!(o.verdict, V, "{staging}: {}", o.output);
        assert_eq!(calls(), expected_calls(staging), "{staging}");
        if staging != Staging::FullRange {
            assert_eq!(search.runs[0].ended, "out-of-time", "{staging}: {:?}", search.runs);
        }
        let (r, _) = regress(staging, "slow");
        assert_eq!(r.verdict, V, "{staging}: {}", r.output);
        assert_eq!(calls(), expected_calls(staging), "{staging}");
    }

    // `result < 100` fails from 99 up. The wide stage finds 5000, the full range 1000000: a violation stops the
    // search, and either witness is shrunk in the interpreter to the same 99.
    answer(Some(&proved()), Some(&refuted_by_jbmc("PropertyHarness", "(I)V", 5000)), &refuted_by_jbmc("PropertyHarness", "(I)V", 1_000_000));
    for (staging, stage, found) in [(Staging::Staged, Some("[-100000:100000]"), "5000"), (Staging::FullRange, None, "1000000"), (Staging::Tight, None, "1000000")] {
        let (o, search) = prove(staging, "result < 100", "refuted");
        assert_eq!(o.verdict, X, "{staging}: {}", o.output);
        assert_eq!(calls(), expected_calls(staging).replace(" full", if staging == Staging::Staged { "" } else { " full" }), "{staging}");
        assert_eq!(search.stage.as_deref(), stage, "{staging}");
        let witness = o.counterexample.as_ref().expect("a witness");
        assert_eq!(runner_arguments(&witness.inputs), "99", "{staging}: {}", o.output);
        assert_eq!(witness.found_inputs.as_deref().map(runner_arguments).as_deref(), Some(found), "{staging}: as JBMC found it");
    }
}

/// What a stand-in JBMC answers: `text` as JBMC prints it, `json` as it prints it under `--json-ui`, the one the
/// run asks for.
struct Answer {
    text: String,
    json: String,
}

fn write_answer(dir: &Path, answer: &Answer) {
    std::fs::write(dir.join("answer.txt"), &answer.text).unwrap();
    std::fs::write(dir.join("answer.json"), &answer.json).unwrap();
}

/// JBMC's JSON: the program, a version message, the results and the overall status, as CBMC 6.11.0 writes them.
fn json_answer(results: &[String], status: Option<&str>) -> String {
    let status = status.map(|s| format!(",\n  {{\n    \"cProverStatus\": \"{s}\"\n  }}")).unwrap_or_default();
    let results = if results.is_empty() { String::new() } else { format!(",\n  {{\n    \"result\": [{}]\n  }}", results.join(", ")) };
    format!("[\n  {{\n    \"program\": \"JBMC 6.11.0 (cbmc-6.11.0)\"\n  }},\n  {{\n    \"messageText\": \"JBMC version 6.11.0 (cbmc-6.11.0) 64-bit\",\n    \"messageType\": \"STATUS-MESSAGE\"\n  }}{results}{status}\n]\n")
}

fn proved() -> Answer {
    let results: Vec<String> = (1..=5).map(|n| format!("{{\"property\": \"java::H.check:(I)V.assertion.{n}\", \"status\": \"SUCCESS\"}}")).collect();
    Answer { text: "JBMC version 6.11.0 (cbmc-6.11.0)\n** 0 of 5 failed (1 iterations)\nVERIFICATION SUCCESSFUL\n".into(), json: json_answer(&results, Some("success")) }
}

/// A run that stops before any result, the array left open.
fn no_answer() -> Answer {
    Answer {
        text: "JBMC version 6.11.0 (cbmc-6.11.0)\nRunning with 8 object bits\n".into(),
        json: "[\n  {\n    \"program\": \"JBMC 6.11.0 (cbmc-6.11.0)\"\n  },\n  {\n    \"messageText\": \"Running with 8 object bits\",\n    \"messageType\": \"STATUS-MESSAGE\"\n  }".into(),
    }
}

/// The harness's assertion refuted on an `int` first parameter.
fn refuted_by_jbmc(class: &str, descriptor: &str, input: i32) -> Answer {
    let bits = format!("{:032b}", input as u32);
    let trace = format!("{{\"stepType\": \"input\", \"inputID\": \"arg0i\", \"values\": [{{\"binary\": \"{bits}\", \"data\": \"{input}\", \"name\": \"integer\", \"type\": \"int\", \"width\": 32}}]}}");
    let mut results = vec![format!("{{\"property\": \"java::{class}.check:{descriptor}.assertion.1\", \"status\": \"FAILURE\", \"trace\": [{trace}]}}")];
    results.extend((2..=5).map(|n| format!("{{\"property\": \"java::{class}.check:{descriptor}.assertion.{n}\", \"status\": \"SUCCESS\"}}")));
    Answer {
        text: format!("JBMC version 6.11.0 (cbmc-6.11.0)\n[{class}.check:{descriptor}.assertion.1] line 1 assertion at file {class}.java line 1 function java::{class}.check:{descriptor} bytecode-index 9: FAILURE\n  INPUT arg0a: {input}\n** 1 of 5 failed (2 iterations)\nVERIFICATION FAILED\n"),
        json: json_answer(&results, Some("failure")),
    }
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
    let answer = |a: &Answer| {
        write_answer(&dir, a);
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

    answer(&proved());
    let confirmed = prove("increment", "result == x + 1", GapMode::Strict, "proved");
    assert_eq!(confirmed.verdict, Verdict::Verified, "{}", confirmed.output);
    assert_eq!(status(&confirmed), Some(Confirmed::Confirmed));
    assert!(confirmed.output.contains("  confirmed: JBMC 6.11.0 proves it too, over every input"), "{}", confirmed.output);
    assert_eq!(confirmed.search.as_ref().unwrap().engine, "native");
    let args = std::fs::read_to_string(dir.join("args.txt")).unwrap();
    assert!(args.contains("PropertyHarness") && !args.contains("--java-assume-inputs-interval"), "one run over every input: {args}");
    let json = serde_json::to_value(&confirmed).unwrap();
    assert_eq!(json["search"]["confirmation"]["status"], "confirmed");

    answer(&refuted_by_jbmc("PropertyHarness", "(I)V", 5));
    let disagreed = prove("increment", "result == x + 1", GapMode::Strict, "refuted");
    assert_eq!(disagreed.verdict, Verdict::Unverifiable, "neither verdict: {}", disagreed.output);
    assert_eq!(status(&disagreed), Some(Confirmed::Disagreed));
    assert!(disagreed.output.contains("the engines disagree") && disagreed.output.contains("increment(x=5)"), "{}", disagreed.output);
    assert!(disagreed.output.contains("where the harness holds"), "the interpreter runs the witness: {}", disagreed.output);
    assert_eq!(disagreed.findings[0].rule_id, "engines-disagree");
    let witness = disagreed.counterexample.as_ref().expect("JBMC's witness");
    assert_eq!(runner_arguments(&witness.inputs), "5");
    assert!(!disagreed.replay.as_ref().unwrap().reproduced);

    answer(&no_answer());
    let unconfirmed = prove("increment", "result == x + 1", GapMode::Strict, "silent");
    assert_eq!(unconfirmed.verdict, Verdict::Verified, "{}", unconfirmed.output);
    assert_eq!(status(&unconfirmed), Some(Confirmed::NoVerdict));
    assert!(unconfirmed.output.contains("  not confirmed: JBMC 6.11.0 gave no verdict"), "{}", unconfirmed.output);

    // `new ArrayList<>(n)` assumed to return: JBMC has no bytecode for it either, so it is not asked.
    answer(&proved());
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
    answer(&refuted_by_jbmc("EquivalenceHarness", "(I)V", 7));
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

/// `--confirm` where JBMC refutes the own checker's proof through a construct it runs otherwise than the JVM
/// (`jbmc_gaps::Defect`, step 3 of `llm-dlc/loops/engine-priorities.md`), on a witness the interpreter does not
/// reproduce: the refutation is the defect's, so JBMC gives no verdict and the proof stands, not confirmed. The
/// stand-in JBMC answers `caught(0)` (javac's `return 10 / n` inside `try`), where the real one lets the
/// division's exception past the handler; without the defect in its program, the same answer is a disagreement
/// (`confirm_reports_what_jbmc_made_of_a_proof_of_the_own_checker`).
#[test]
fn confirm_takes_a_refutation_through_a_jbmc_defect_for_no_verdict() {
    let Some(compiled) = compile() else { return };
    let jbmc = fake_jbmc("confirm-defect");
    let dir = jbmc.parent().unwrap().to_path_buf();
    let program = |harness: &str| format!("{harness}.check(int) /* java::{harness}.check:(I)V */\n        // 1 file {harness}.java line 1 function java::{harness}.check:(I)V bytecode-index 1\n     1: CALL java::{CLASS}.caught:(I)I(java::{harness}.check:(I)V::arg0i)\n\n^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n{CLASS}.caught(int) /* java::{CLASS}.caught:(I)I */\n        SKIP\n");
    std::fs::write(dir.join("goto.txt"), program("PropertyHarness")).unwrap();
    write_answer(&dir, &refuted_by_jbmc("PropertyHarness", "(I)V", 0));
    let mut options = property::Options::new(std::slice::from_ref(&compiled.classes), &format!("{CLASS}#caught"));
    options.assert = Some("n != 0 || result == -1".into());
    options.engine = Engine::Auto;
    options.confirm = true;
    options.jbmc = jbmc.display().to_string();
    let work = target_tmp().join("confirm-defect-property");
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    // The defect is named at the line of `caught`'s `return 10 / n`, read from the corpus so that cases added above
    // it don't move the expectation.
    let source = std::fs::read_to_string(Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/conformance/conformance/Conformance.java")).unwrap();
    let line = source.lines().position(|l| l.trim() == "return 10 / n;").expect("caught's return in the corpus") + 1;
    let at = format!("return-past-handler at conformance.Conformance.caught:{line}");
    let outcome = property::run(&options).unwrap();
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    let confirmation = outcome.search.as_ref().and_then(|s| s.confirmation.as_ref()).expect("a confirmation");
    assert_eq!(confirmation.status, Confirmed::NoVerdict, "{}", outcome.output);
    assert!(outcome.output.contains("  not confirmed: JBMC 6.11.0 gave no verdict"), "{}", outcome.output);
    assert!(outcome.output.contains(&format!("its counterexample does not reproduce in the interpreter, and on the way it runs 1 construct otherwise than the JVM: {at}")), "{}", outcome.output);
    assert!(outcome.counterexample.is_none() && !outcome.output.contains("the engines disagree"), "{}", outcome.output);
    let json = serde_json::to_value(&outcome).unwrap();
    assert_eq!(json["search"]["confirmation"]["status"], "no-verdict");

    // A regression proof of the method against itself, as written: the same.
    std::fs::write(dir.join("goto.txt"), program("EquivalenceHarness")).unwrap();
    write_answer(&dir, &refuted_by_jbmc("EquivalenceHarness", "(I)V", 0));
    let mut options = jvmcontract::equivalence::Options::new(&compiled.classes, &compiled.classes, &format!("{CLASS}#caught"));
    options.engine = Engine::Auto;
    options.confirm = true;
    options.shared_callees = false;
    options.jbmc = jbmc.display().to_string();
    let work = target_tmp().join("confirm-defect-equivalence");
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    let equivalence = jvmcontract::equivalence::run(&options).unwrap();
    assert_eq!(equivalence.verdict, Verdict::Verified, "{}", equivalence.output);
    assert_eq!(equivalence.search.as_ref().and_then(|s| s.confirmation.as_ref()).map(|c| c.status), Some(Confirmed::NoVerdict), "{}", equivalence.output);
    assert!(equivalence.output.contains(&at), "{}", equivalence.output);
}

/// Step 4a of the brief: JBMC's interval stages run only where they bound an input, and a check has one deadline,
/// each run a budget out of it. JBMC is a stand-in script that logs every run it is given, and can be made to hang
/// on the interval stages, or on every run.
#[test]
fn jbmc_runs_only_the_stages_that_change_the_domain_within_one_deadline() {
    let Some(compiled) = compile() else { return };
    let dir = target_tmp().join("fake-jbmc-stages");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let jbmc = dir.join("jbmc");
    std::fs::write(&jbmc, "#!/bin/sh\nif [ \"$1\" = --version ]; then echo 6.11.0; exit 0; fi\nd=$(dirname \"$0\")\ncase \"$*\" in *--show-goto-functions*) p=; for a in \"$@\"; do [ \"$p\" = --function ] && f=$a; p=$a; done; echo \"check /* java::$f:()V */\"; exit 0;; esac\necho \"$@\" >> \"$d/runs.txt\"\ncase \"$*\" in *--java-assume-inputs-interval*) [ -e \"$d/hang-stages\" ] && exec sleep 30;; esac\n[ -e \"$d/hang\" ] && exec sleep 30\ncase \"$*\" in *--json-ui*) cat \"$d/answer.json\";; *) cat \"$d/answer.txt\";; esac\n").unwrap();
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(&jbmc, std::fs::Permissions::from_mode(0o755)).unwrap();
    write_answer(&dir, &proved());
    let set = |hang_stages: bool, hang: bool| {
        let _ = std::fs::remove_file(dir.join("runs.txt"));
        for (name, on) in [("hang-stages", hang_stages), ("hang", hang)] {
            if on { std::fs::write(dir.join(name), "").unwrap() } else { let _ = std::fs::remove_file(dir.join(name)); }
        }
    };
    let stages_run = || -> Vec<Option<String>> {
        std::fs::read_to_string(dir.join("runs.txt")).unwrap_or_default().lines().map(|l| l.split_once("--java-assume-inputs-interval ").map(|(_, r)| r.split(' ').next().unwrap().to_string())).collect()
    };
    let prove = |method: &str, assert: &str, timeout: u64, name: &str| {
        let mut options = property::Options::new(std::slice::from_ref(&compiled.classes), &format!("{CLASS}#{method}"));
        options.assert = Some(assert.to_string());
        options.engine = Engine::Jbmc;
        // The stages are `staged`'s; the default policy runs the full range alone since job 20261106-201041.
        options.jbmc_staging = jvmcontract::deadline::Staging::Staged;
        options.timeout_seconds = timeout;
        options.jbmc = jbmc.display().to_string();
        let work = target_tmp().join(format!("stages-{name}"));
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        let started = std::time::Instant::now();
        let outcome = property::run(&options).unwrap();
        (outcome, started.elapsed())
    };
    let s = |x: &str| Some(x.to_string());

    // Arrays alone, as 142's harness (chars, out): an interval bounds no element, so JBMC runs once.
    set(false, false);
    let (arrays, _) = prove("length", "result >= 0", 600, "arrays");
    assert_eq!(arrays.verdict, Verdict::Verified, "{}", arrays.output);
    assert_eq!(stages_run(), vec![None], "one run over every input");
    let search = arrays.search.as_ref().unwrap();
    assert_eq!(search.deadline_seconds, 600.0);
    assert_eq!(search.runs.len(), 1);
    assert_eq!((search.runs[0].checker.as_str(), search.runs[0].purpose.as_str(), search.runs[0].stage.as_deref(), search.runs[0].ended.as_str()), ("jbmc", "proof", None, "verified"));
    let json = serde_json::to_value(&arrays).unwrap();
    assert_eq!(json["search"]["runs"][0]["purpose"], "proof");
    assert!(json["search"]["runs"][0]["budget_seconds"].as_f64().unwrap() > 599.0);

    // Two bytes: [-100000:100000] holds every byte, so only [0:20] goes before the proof.
    set(false, false);
    let (bytes, _) = prove("byteSum", "result == a + b", 600, "bytes");
    assert_eq!(bytes.verdict, Verdict::Verified, "{}", bytes.output);
    assert_eq!(stages_run(), vec![s("[0:20]"), None]);
    // An int: all three.
    set(false, false);
    let (int, _) = prove("increment", "result == x + 1", 600, "int");
    assert_eq!(int.verdict, Verdict::Verified, "{}", int.output);
    assert_eq!(stages_run(), vec![s("[0:20]"), s("[-100000:100000]"), None]);
    let budgets: Vec<f64> = int.search.as_ref().unwrap().runs.iter().map(|r| r.budget_seconds).collect();
    assert!(budgets[0] <= 75.0 && budgets[1] <= 75.0 && budgets[2] > 449.0, "an eighth of the check for each preliminary stage, the rest for the proof: {budgets:?}");

    // Preliminary stages that hang run out of their budgets, an eighth of the check each, and hand on to the
    // proof: the check is decided in a quarter of its time, where each stage used to have all of it and the first
    // to hang ended the check with no verdict.
    set(true, false);
    let (handed_on, elapsed) = prove("increment", "result == x + 1", 16, "hang-stages");
    assert_eq!(handed_on.verdict, Verdict::Verified, "{}", handed_on.output);
    assert_eq!(stages_run(), vec![s("[0:20]"), s("[-100000:100000]"), None]);
    let ended: Vec<&str> = handed_on.search.as_ref().unwrap().runs.iter().map(|r| r.ended.as_str()).collect();
    assert_eq!(ended, vec!["out-of-time", "out-of-time", "verified"]);
    assert!(elapsed < std::time::Duration::from_secs(8), "{elapsed:?}");

    // Every run hangs: the check ends at its deadline, not three timeouts later.
    set(false, true);
    let (hung, elapsed) = prove("increment", "result == x + 1", 4, "hang");
    assert_eq!(hung.verdict, Verdict::Unverifiable, "{}", hung.output);
    assert!(elapsed < std::time::Duration::from_secs(6), "past the 4 s deadline: {elapsed:?}");
    let runs = &hung.search.as_ref().unwrap().runs;
    assert_eq!(runs.iter().map(|r| r.ended.as_str()).collect::<Vec<_>>(), vec!["out-of-time"; 3]);
    let budget: f64 = runs.iter().map(|r| r.budget_seconds).sum();
    assert!(budget <= 4.0 + 0.01, "the budgets add up to the deadline: {runs:?}");
    assert!(hung.output.contains("JBMC did not finish within"), "{}", hung.output);

    // A regression proof over arrays alone runs once too.
    set(false, false);
    let mut options = jvmcontract::equivalence::Options::new(&compiled.classes, &compiled.classes, &format!("{CLASS}#length"));
    options.engine = Engine::Jbmc;
    options.shared_callees = false;
    options.jbmc = jbmc.display().to_string();
    let work = target_tmp().join("stages-equivalence");
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    let equivalence = jvmcontract::equivalence::run(&options).unwrap();
    assert_eq!(equivalence.verdict, Verdict::Verified, "{}", equivalence.output);
    assert_eq!(stages_run(), vec![None]);
    assert_eq!(equivalence.search.as_ref().unwrap().runs.len(), 1);

    // The own checker's runs are recorded too, with its probe: under auto it has the check but the quarter kept for
    // JBMC's fallback.
    set(false, false);
    let mut options = property::Options::new(std::slice::from_ref(&compiled.classes), &format!("{CLASS}#increment"));
    options.assert = Some("result == x + 1".into());
    options.assume = Some("x > 0".into());
    options.engine = Engine::Auto;
    options.timeout_seconds = 100;
    options.jbmc = jbmc.display().to_string();
    let work = target_tmp().join("stages-auto");
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    let auto = property::run(&options).unwrap();
    assert_eq!(auto.verdict, Verdict::Verified, "{}", auto.output);
    let runs = &auto.search.as_ref().unwrap().runs;
    assert_eq!(runs.iter().map(|r| (r.checker.as_str(), r.purpose.as_str())).collect::<Vec<_>>(), vec![("native", "proof"), ("native", "probe")], "{runs:?}");
    assert!(runs[0].budget_seconds <= 75.0 && runs[0].budget_seconds > 74.0, "{runs:?}");
    assert!(stages_run().is_empty(), "JBMC was not asked");
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
    write_answer(jbmc.parent().unwrap(), &proved());
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
