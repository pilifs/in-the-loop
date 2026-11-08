//! The values stream's model conformance tests (`llm-dlc/loops/application-core-values.md`): small Java methods over
//! Strings, run on a real JVM and in the interpreter, which must give the same outcome, a String's code units
//! included. The JVM is the semantic reference. A case the interpreter refuses (`Fault::Unsupported`) passes only
//! where it is listed as refusable, and is never a different answer: sampled conformance is evidence of the level
//! `tested`, not a proof of the model.

use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::OnceLock;

use jvmcontract::bmc::{self, Options, Outcome, Parameters};
use jvmcontract::classfile::{MethodDescriptor, Type};
use jvmcontract::classpath::ClassPath;
use jvmcontract::interp::{Fault, Machine, Value};
use jvmcontract::spec::plans::{ValueDomain, ValueKind, WitnessValue};
use jvmcontract::values::{self, ListAdapter, Nodes, StringAdapter, ValueAdapter, Witnessed};
use jvmcontract::Verdict;

fn has(program: &str) -> bool {
    let found = Command::new(program).arg("--version").output().map(|o| o.status.success()).unwrap_or(false);
    if !found {
        let skip = std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1");
        assert!(skip, "{program} not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip the tests that need it");
    }
    found
}

fn fixtures() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/values")
}

fn java_files(dir: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    for entry in std::fs::read_dir(dir).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            out.extend(java_files(&path));
        } else if path.extension().is_some_and(|e| e == "java") {
            out.push(path);
        }
    }
    out.sort();
    out
}

/// The fixtures and the runner, compiled once.
fn compiled() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("values-classes");
        let _ = std::fs::remove_dir_all(&out);
        std::fs::create_dir_all(&out).unwrap();
        let status = Command::new("javac").args(["-g", "-proc:none", "-d"]).arg(&out).args(java_files(&fixtures())).status().expect("javac runs");
        assert!(status.success(), "the values fixtures compile");
        Some(out)
    })
    .as_deref()
}

/// One call: a static method of a fixture class and its int arguments.
struct Case {
    class: &'static str,
    method: &'static str,
    args: &'static [i32],
    /// Whether the interpreter may refuse it, by name, instead of answering.
    refusable: bool,
}

const fn case(class: &'static str, method: &'static str, args: &'static [i32]) -> Case {
    Case { class, method, args, refusable: false }
}

const fn refusable(class: &'static str, method: &'static str, args: &'static [i32]) -> Case {
    Case { class, method, args, refusable: true }
}

/// What the JVM gave for each case, by [`ValuesRunner`](fixtures/values/ValuesRunner.java).
fn on_jvm(classes: &Path, cases: &[Case]) -> Vec<String> {
    let lines: Vec<String> = cases.iter().map(|c| format!("{} {} {}", c.class, c.method, c.args.iter().map(|a| a.to_string()).collect::<Vec<_>>().join(" "))).collect();
    run_on_jvm(classes, &lines)
}

/// What the JVM gave for each line of the runner's input.
fn run_on_jvm(classes: &Path, lines: &[String]) -> Vec<String> {
    let input: String = lines.iter().map(|l| format!("{l}\n")).collect();
    let mut child = Command::new("java").arg("-cp").arg(classes).arg("ValuesRunner").stdin(Stdio::piped()).stdout(Stdio::piped()).spawn().expect("java runs");
    use std::io::Write as _;
    child.stdin.take().unwrap().write_all(input.as_bytes()).unwrap();
    let out = child.wait_with_output().unwrap();
    assert!(out.status.success(), "the runner runs every case");
    let out: Vec<String> = String::from_utf8(out.stdout).unwrap().lines().map(str::to_string).collect();
    assert_eq!(out.len(), lines.len());
    out
}

/// What the interpreter gave, in the runner's form, or `Err` with its refusal.
fn in_interpreter(cp: &ClassPath, case: &Case) -> Result<String, String> {
    let internal = case.class.replace('.', "/");
    let class = cp.application(&internal).unwrap().expect("the fixture class");
    let method = class.methods.iter().find(|m| m.name == case.method && MethodDescriptor::parse(&m.descriptor).unwrap().params.len() == case.args.len()).expect("the case's method");
    let ret = MethodDescriptor::parse(&method.descriptor).unwrap().ret;
    let mut m = Machine::new(cp);
    match m.call_static(&internal, case.method, &method.descriptor, case.args.iter().map(|&a| Value::Int(a)).collect()) {
        Ok(Some(Value::Int(n))) if ret == Type::Boolean => Ok(format!("bool {}", n != 0)),
        Ok(Some(Value::Int(n))) => Ok(format!("int {n}")),
        Ok(Some(Value::Null)) => Ok("null".into()),
        Ok(Some(Value::Ref(r))) => match m.heap.string(r) {
            Some(s) => Ok(std::iter::once("str".to_string()).chain(s.units().iter().map(|u| format!("{u:04x}"))).collect::<Vec<_>>().join(" ")),
            None => Ok(format!("unrendered {}", m.class_of(r).replace('/', "."))),
        },
        Ok(other) => Ok(format!("unrendered {other:?}")),
        Err(Fault::Throw(r)) => Ok(format!("throws {}", m.class_of(r).replace('/', "."))),
        Err(Fault::Unsupported(why)) => Err(why),
        Err(other) => panic!("{}.{}{:?}: {other:?}", case.class, case.method, case.args),
    }
}

/// Every case gives on the interpreter what it gives on the JVM, or is refused where it may be.
fn conforms(cases: &[Case]) {
    let Some(classes) = compiled() else { return };
    let jvm = on_jvm(classes, cases);
    let mut cp = ClassPath::new();
    cp.add(classes).unwrap();
    let cp = cp.with_default_jdk();
    let mut wrong = Vec::new();
    for (case, expected) in cases.iter().zip(&jvm) {
        let what = format!("{}.{}{:?}", case.class, case.method, case.args);
        match in_interpreter(&cp, case) {
            Ok(got) if &got == expected => {}
            Ok(got) => wrong.push(format!("{what}: the JVM gives {expected}, the interpreter {got}")),
            Err(why) if case.refusable => assert!(!why.is_empty(), "{what}: a refusal names what it refuses"),
            Err(why) => wrong.push(format!("{what}: the JVM gives {expected}, the interpreter refuses it: {why}")),
        }
    }
    assert!(wrong.is_empty(), "the interpreter differs from the JVM:\n{}", wrong.join("\n"));
}

const S: &str = "values.Strings";
/// An isolated high surrogate, an isolated low one, the replacement character a lossy conversion makes of either,
/// NUL, and a supplementary character's pair (U+1F600).
const HIGH: i32 = 0xD800;
const LOW: i32 = 0xDC00;
const FFFD: i32 = 0xFFFD;
const SMILE: (i32, i32) = (0xD83D, 0xDE00);

/// The interpreter's Strings are UTF-16 code units, as the JVM's: an isolated surrogate is kept, never made the
/// replacement character, and a surrogate pair can be split and joined again. Before, the interpreter held a
/// String as Rust UTF-8 text and lost every isolated surrogate to U+FFFD.
#[test]
fn the_interpreters_strings_keep_every_code_unit() {
    conforms(&[
        case(S, "unit", &[HIGH]),
        case(S, "unit", &[LOW]),
        case(S, "unit", &[0]),
        case(S, "two", &[LOW, HIGH]),
        case(S, "two", &[SMILE.0, SMILE.1]),
        case(S, "made", &[HIGH, 0x41]),
        case(S, "joined", &[HIGH, 0x41]),
        case(S, "joined", &[SMILE.0, SMILE.1]),
        case(S, "withLiteral", &[LOW]),
        case(S, "built", &[0x41, HIGH]),
        case(S, "concatenated", &[SMILE.0, HIGH]),
        case(S, "length", &[SMILE.0, SMILE.1]),
        case(S, "length", &[HIGH, LOW]),
        case(S, "charAt", &[HIGH, 0x41, 0]),
        case(S, "charAt", &[SMILE.0, SMILE.1, 1]),
        case(S, "charAt", &[0x41, 0x42, 2]),
        case(S, "charAt", &[0x41, 0x42, -1]),
        case(S, "tail", &[SMILE.0, SMILE.1]),
        case(S, "head", &[SMILE.0, SMILE.1]),
        case(S, "same", &[HIGH, FFFD]),
        case(S, "same", &[HIGH, HIGH]),
        case(S, "same", &[HIGH, LOW]),
        case(S, "hash", &[HIGH]),
        case(S, "hash", &[0]),
        case(S, "compare", &[HIGH, FFFD]),
        case(S, "compare", &[LOW, HIGH]),
        case(S, "starts", &[SMILE.0, SMILE.1, SMILE.0]),
        case(S, "starts", &[FFFD, 0x41, HIGH]),
        case(S, "ends", &[SMILE.0, SMILE.1, SMILE.1]),
        case(S, "ends", &[0x41, FFFD, LOW]),
        case(S, "indexOf", &[SMILE.0, SMILE.1, SMILE.1]),
        case(S, "indexOf", &[FFFD, HIGH, HIGH]),
        case(S, "contains", &[FFFD, 0x41, HIGH]),
        case(S, "replaced", &[HIGH, 0x41, 0x42]),
        case(S, "replaced", &[0x41, HIGH, LOW]),
        case(S, "builtLength", &[SMILE.0, SMILE.1]),
        case(S, "builtCharAt", &[0x41, LOW, 1]),
        case(S, "empty", &[0]),
        case(S, "empty", &[HIGH]),
        case(S, "upper", &[0x61]),
        case(S, "stripped", &[0xA0, 0x1C]),
        case(S, "stripped", &[0x2003, HIGH]),
        case(S, "trimmed", &[0x1F, 0xA0]),
        case(S, "blank", &[0x20, 0xA0]),
        case(S, "blank", &[0x1C, 0x3000]),
        case(S, "reversed", &[SMILE.0, SMILE.1, 0x41]),
        case(S, "reversed", &[LOW, HIGH, 0x41]),
        case(S, "reversed", &[HIGH, 0x41, LOW]),
        case(S, "indexOfPoint", &[SMILE.0, SMILE.1, 0x1F600]),
        case(S, "indexOfPoint", &[SMILE.0, SMILE.1, SMILE.1]),
        case(S, "indexOfPoint", &[0x41, 0x42, -1]),
        case(S, "lastIndexOfPoint", &[SMILE.0, SMILE.1, 0x1F600]),
        case(S, "lastIndexOfPoint", &[HIGH, HIGH, HIGH]),
        case(S, "codePointAt", &[SMILE.0, SMILE.1, 0]),
        case(S, "codePointAt", &[SMILE.0, SMILE.1, 1]),
        case(S, "codePointAt", &[HIGH, 0x41, 0]),
        case(S, "spread", &[SMILE.0, SMILE.1]),
        case(S, "region", &[HIGH, LOW, 1, 1]),
        case(S, "region", &[HIGH, LOW, 1, 2]),
        case(S, "region", &[HIGH, LOW, -1, 1]),
        case(S, "inserted", &[HIGH, LOW]),
        case(S, "parsed", &[0x37]),
        case(S, "charString", &[LOW]),
        case(S, "copied", &[HIGH]),
        // Integer.parseInt takes any Unicode digit (Character.digit): refused outside ASCII, not guessed.
        refusable(S, "parsed", &[0x0667]),
        refusable(S, "parsed", &[HIGH]),
        // Case conversion over an isolated surrogate is the Unicode tables' business: refused, never guessed.
        refusable(S, "upper", &[HIGH]),
    ]);
}

// The own checker's bounded Strings (V1 step 2): harness-shaped methods of `values.Checks`, each throwing an
// AssertionError where its claim fails, checked by `bmc::check` with String parameters of every content up to a
// bound. A violation's witness is replayed on the JVM and in the interpreter, and must fail the claim on both.

const CHECKS: &str = "values/Checks";

/// The fixtures on a class path with the JDK, for the checker.
fn checker_classes() -> Option<ClassPath> {
    let classes = compiled()?;
    let mut cp = ClassPath::new();
    cp.add(classes).unwrap();
    Some(cp.with_default_jdk())
}

/// The check of `method` with Strings of at most `bound` code units, merging paths from the start or never.
fn checked(cp: &ClassPath, method: &str, parameters: Parameters, merge_after: u64) -> Outcome {
    bmc::check(cp, CHECKS, method, &Options { parameters, merge_after, ..Options::default() }).unwrap()
}

fn bounded(bound: u32) -> Parameters {
    Parameters { max_string_length: Some(bound), ..Parameters::default() }
}

fn params_of(cp: &ClassPath, method: &str) -> Vec<Type> {
    let class = cp.application(CHECKS).unwrap().expect("the checks");
    let m = class.methods.iter().find(|m| m.name == method).expect("the check");
    MethodDescriptor::parse(&m.descriptor).unwrap().params
}

/// One argument of a witness: a String's code units, null, the same object as an earlier argument, or a number.
#[derive(Debug, Clone, PartialEq)]
enum Arg {
    Str(Vec<u16>),
    Null,
    Same(usize),
    Number(i64),
}

/// The witness's arguments, in parameter order, each String read through the values adapter
/// (`values::StringAdapter::read`) under the check's domain: its bound, and whether its slot may be null.
fn witness(out: &Outcome, params: &[Type], parameters: &Parameters) -> Vec<Arg> {
    let mut args = Vec::new();
    let mut index_of = std::collections::BTreeMap::new();
    for (slot, t) in params.iter().enumerate() {
        let slot = slot as u32;
        index_of.insert(slot, args.len());
        args.push(match t {
            Type::Object(_) => {
                let adapter = StringAdapter::new(parameters.max_string_length.expect("a bound"), parameters.nullable.contains(&slot));
                match adapter.read(&out.raw_arrays, &out.raw_same, slot).unwrap_or_else(|u| panic!("the witness's String in slot {slot}: {u}")) {
                    Witnessed::SameAs(first) => Arg::Same(index_of[&first]),
                    Witnessed::Value(WitnessValue::Null) => Arg::Null,
                    Witnessed::Value(WitnessValue::String { units }) => Arg::Str(units),
                    Witnessed::Value(other) => panic!("not a String's witness: {other:?}"),
                }
            }
            _ => Arg::Number(out.raw_inputs.get(&slot).map(|v| v.parse().unwrap()).unwrap_or(0)),
        });
    }
    args
}

/// What the witness does on the JVM and in the interpreter, in the runner's form; in the interpreter, each String
/// is rebuilt through the values adapter (`ValueAdapter::rebuild`), which encodes it back as the same units.
fn replayed(cp: &ClassPath, method: &str, args: &[Arg]) -> (String, String) {
    let text: Vec<String> = args
        .iter()
        .map(|a| match a {
            Arg::Str(units) => format!("s:{}", units.iter().map(|u| u.to_string()).collect::<Vec<_>>().join(",")),
            Arg::Null => "null".into(),
            Arg::Same(i) => format!("same:{i}"),
            Arg::Number(n) => n.to_string(),
        })
        .collect();
    let jvm = run_on_jvm(compiled().unwrap(), &[format!("values.Checks {method} {}", text.join(" "))]).remove(0);
    let class = cp.application(CHECKS).unwrap().unwrap();
    let descriptor = class.methods.iter().find(|m| m.name == method).unwrap().descriptor.clone();
    let mut m = Machine::new(cp);
    let mut values: Vec<Value> = Vec::new();
    for a in args {
        values.push(match a {
            Arg::Str(units) => {
                let adapter = StringAdapter::new(units.len() as u32, false);
                let w = WitnessValue::String { units: units.clone() };
                let v = adapter.rebuild(&mut m, &w, &Nodes::new()).unwrap();
                assert_eq!(adapter.encode(&m, v, &Nodes::new()).unwrap(), w, "a rebuilt String encodes as its witness");
                v
            }
            Arg::Null => Value::Null,
            Arg::Same(i) => values[*i],
            Arg::Number(n) => Value::Int(*n as i32),
        });
    }
    let interpreter = match m.call_static(CHECKS, method, &descriptor, values) {
        Ok(_) => "null".to_string(),
        Err(Fault::Throw(r)) => format!("throws {}", m.class_of(r).replace('/', ".")),
        Err(other) => format!("{other:?}"),
    };
    (jvm, interpreter)
}

/// A violation, under both search orders, whose witness fails the claim on the JVM and in the interpreter.
fn refuted(cp: &ClassPath, method: &str, parameters: Parameters) -> Vec<Arg> {
    let params = params_of(cp, method);
    let mut found = Vec::new();
    for merge_after in [0, u64::MAX] {
        let out = checked(cp, method, parameters.clone(), merge_after);
        assert_eq!(out.verdict, Verdict::Violation, "{method} (merging after {merge_after}): {:?}", out.problem);
        let args = witness(&out, &params, &parameters);
        let (jvm, interpreter) = replayed(cp, method, &args);
        assert_eq!(jvm, "throws java.lang.AssertionError", "{method}{args:?} on the JVM");
        assert_eq!(interpreter, jvm, "{method}{args:?} in the interpreter");
        found.push(args);
    }
    found.remove(0)
}

fn verified(cp: &ClassPath, method: &str, parameters: Parameters) {
    for merge_after in [0, u64::MAX] {
        let out = checked(cp, method, parameters.clone(), merge_after);
        assert_eq!(out.verdict, Verdict::Verified, "{method} (merging after {merge_after}): {:?}", out.problem);
    }
}

fn no_verdict(cp: &ClassPath, method: &str, parameters: Parameters, saying: &str) {
    let out = checked(cp, method, parameters, u64::MAX);
    assert_eq!(out.verdict, Verdict::Unverifiable, "{method}");
    let problem = out.problem.unwrap_or_default();
    assert!(problem.contains(saying), "{method}: {problem}");
}

fn units(text: &str) -> Vec<u16> {
    text.encode_utf16().collect()
}

/// The quote fixture's `Codes.vip`, by content: its rewrite on `length` and `charAt` is proved the same as
/// `startsWith("VIP")` on every String of up to five code units, and the defect that checks only "VI" is refuted
/// with a code that starts "VI" and not "VIP", replayed. Before, a String parameter was outside the fragment.
#[test]
fn the_own_checker_proves_the_codes_rewrite_and_refutes_a_dropped_prefix_character() {
    let Some(cp) = checker_classes() else { return };
    verified(&cp, "vipRewritten", bounded(5));
    let [Arg::Str(code)] = &refuted(&cp, "vipShortened", bounded(5))[..] else { panic!("one String") };
    assert!(code.starts_with(&units("VI")) && !code.starts_with(&units("VIP")), "{code:?}");
}

/// A String's content is any code units: an isolated surrogate and a NUL are found as inputs, and a supplementary
/// character is two units, so a defect that takes it for one is refuted with the pair.
#[test]
fn a_strings_content_is_any_code_units_and_a_supplementary_character_is_two() {
    let Some(cp) = checker_classes() else { return };
    let [Arg::Str(lone)] = &refuted(&cp, "noLoneSurrogate", bounded(3))[..] else { panic!() };
    assert!(lone.len() == 1 && (0xD800..=0xDBFF).contains(&lone[0]), "{lone:?}");
    let [Arg::Str(nul)] = &refuted(&cp, "embeddedNul", bounded(3))[..] else { panic!() };
    assert_eq!(nul, &[0x41, 0]);
    verified(&cp, "pairIsTwoUnits", bounded(3));
    let [Arg::Str(pair)] = &refuted(&cp, "pairAsOneUnit", bounded(3))[..] else { panic!() };
    assert!(pair.starts_with(&[0xD83D, 0xDE00]), "{pair:?}");
}

/// `equals` is content, `==` identity: equal content behind two references refutes a claim that they are one
/// object, and one object (under a domain that lets the two be one) is equal to itself.
#[test]
fn equality_is_content_and_identity_is_apart_from_it() {
    let Some(cp) = checker_classes() else { return };
    verified(&cp, "equalsByUnits", bounded(3));
    let [Arg::Str(a), Arg::Str(b)] = &refuted(&cp, "equalIsIdentical", bounded(3))[..] else { panic!("two Strings of their own") };
    assert_eq!(a, b);
    let aliased = Parameters { may_alias: vec![vec![0, 1]], ..bounded(3) };
    verified(&cp, "identicalIsEqual", aliased.clone());
    let [Arg::Str(_), second] = &refuted(&cp, "equalIsIdentical", aliased)[..] else { panic!() };
    assert!(matches!(second, Arg::Str(_)), "equal content, not the same object: {second:?}");
    verified(&cp, "equalsNullOrOther", bounded(3));
    verified(&cp, "literal", bounded(4));
}

/// The modelled methods' exceptions: `charAt` out of range, `startsWith(null)`, and a null String under a domain
/// that lets it be null.
#[test]
fn the_modelled_methods_throw_as_the_jdks_do() {
    let Some(cp) = checker_classes() else { return };
    verified(&cp, "charAtBounds", bounded(3));
    verified(&cp, "startsWithNull", bounded(3));
    verified(&cp, "emptyIsLengthZero", bounded(3));
    let nullable = Parameters { nullable: vec![0], ..bounded(3) };
    assert_eq!(refuted(&cp, "notNull", nullable.clone()), vec![Arg::Null]);
    verified(&cp, "notNull", bounded(3));
    no_verdict(&cp, "lengthOfNullable", nullable, "NullPointerException");
}

/// A String parameter's length is an input-domain bound the check states: every content up to it, none beyond, and
/// no String parameter at all without one.
#[test]
fn a_string_parameters_bound_is_explicit_and_every_length_up_to_it_is_an_input() {
    let Some(cp) = checker_classes() else { return };
    verified(&cp, "atMostFour", bounded(4));
    let [Arg::Str(five)] = &refuted(&cp, "atMostFour", bounded(5))[..] else { panic!() };
    assert_eq!(five.len(), 5);
    no_verdict(&cp, "atMostFour", Parameters::default(), "a java.lang.String parameter with no bound on its length");
}

/// A compiler-generated concatenation of Strings, chars and constants has their content, `null` as "null"; one
/// that could pass the content cap has none, and is a named limit where its content is asked for, and a number
/// converted (numeric formatting, outside the model) is the gap it was.
#[test]
fn a_concatenation_has_its_parts_content_up_to_a_named_cap() {
    let Some(cp) = checker_classes() else { return };
    verified(&cp, "concatenated", bounded(4));
    verified(&cp, "joined", bounded(3));
    verified(&cp, "nullConcatenated", Parameters { nullable: vec![0], ..bounded(3) });
    let [Arg::Str(a), Arg::Str(b)] = &refuted(&cp, "concatenationCommutes", bounded(2))[..] else { panic!() };
    assert_ne!(a, b);
    verified(&cp, "longJoin", bounded(7));
    no_verdict(&cp, "longJoin", bounded(8), "a concatenation of up to 72 code units, beyond the own checker's content cap of 64");
    no_verdict(&cp, "numbered", bounded(3), "jdk-primitive-method");
}

/// The gap scan agrees with the engine: a String method the engine models on content is no gap, counted among the
/// calls it reproduces, and any other String method a check reaches still is one.
#[test]
fn the_gap_scan_counts_the_modelled_string_methods_and_no_others() {
    let Some(cp) = checker_classes() else { return };
    let scan = |target: &str| bmc::gaps::scan(&cp, &bmc::gaps::roots(&cp, &[format!("values.Checks#{target}")]).unwrap()).unwrap();
    let vip = scan("vipShortened");
    assert!(vip.gaps.is_empty(), "{:?}", vip.gaps);
    for call in ["startsWith(Ljava/lang/String;)Z", "length()I", "charAt(I)C"] {
        assert!(vip.exact.contains_key(&format!("java.lang.String.{call} (on its content)")), "{call}: {:?}", vip.exact);
    }
    // `Strings.upper` calls `toUpperCase`, which no model covers: still a gap.
    let other = bmc::gaps::scan(&cp, &bmc::gaps::roots(&cp, &["values.Strings#upper".into()]).unwrap()).unwrap();
    assert!(other.gaps.keys().any(|g| g.owner == "java/lang/String" && g.name == "toUpperCase"), "{:?}", other.gaps);
}

const LISTS: &str = "values/Lists";

/// The check of a list method of [`LISTS`], every argument an `int`, merging paths from the start or never.
fn list_checked(cp: &ClassPath, method: &str, merge_after: u64) -> Outcome {
    bmc::check(cp, LISTS, method, &Options { merge_after, ..Options::default() }).unwrap()
}

/// A list check's violation, under both search orders, whose witness (its `int` arguments) fails the claim on the
/// JVM and in the interpreter, which makes its lists with its own `List.of`.
fn list_refuted(cp: &ClassPath, method: &str) -> Vec<i32> {
    let class = cp.application(LISTS).unwrap().unwrap();
    let descriptor = class.methods.iter().find(|m| m.name == method).unwrap().descriptor.clone();
    let arity = MethodDescriptor::parse(&descriptor).unwrap().params.len();
    let mut found = Vec::new();
    for merge_after in [0, u64::MAX] {
        let out = list_checked(cp, method, merge_after);
        assert_eq!(out.verdict, Verdict::Violation, "{method} (merging after {merge_after}): {:?}", out.problem);
        let args: Vec<i32> = (0..arity as u32).map(|slot| out.raw_inputs.get(&slot).map(|v| v.parse().unwrap()).unwrap_or(0)).collect();
        let jvm = run_on_jvm(compiled().unwrap(), &[format!("values.Lists {method} {}", args.iter().map(|a| a.to_string()).collect::<Vec<_>>().join(" "))]).remove(0);
        assert_eq!(jvm, "throws java.lang.AssertionError", "{method}{args:?} on the JVM");
        let mut m = Machine::new(cp);
        let interpreter = match m.call_static(LISTS, method, &descriptor, args.iter().map(|&a| Value::Int(a)).collect()) {
            Err(Fault::Throw(r)) => format!("throws {}", m.class_of(r).replace('/', ".")),
            other => format!("{other:?}"),
        };
        assert_eq!(interpreter, jvm, "{method}{args:?} in the interpreter");
        found.push(args);
    }
    found.remove(0)
}

fn list_verified(cp: &ClassPath, method: &str) {
    for merge_after in [0, u64::MAX] {
        let out = list_checked(cp, method, merge_after);
        assert_eq!(out.verdict, Verdict::Verified, "{method} (merging after {merge_after}): {:?}", out.problem);
    }
}

/// The basket's kernels over lists made by `List.of`, as a harness makes them: each rewrite proved on every list
/// of up to three lines, any two of which may be one object, and each planted defect refuted with a replayed
/// witness: a duplicate skipped (two elements one line), the last line for the first (two different lines), a copy
/// for the element (identity), and every line read before any is cleared (an alias between elements). Before, the
/// own checker ran none of the list models (`List.of` was the gap `jdk-static-method`), so no check reached a list.
#[test]
fn the_own_checker_runs_the_immutable_list_models_and_keeps_order_duplicates_and_aliases() {
    let Some(cp) = checker_classes() else { return };
    for method in ["totalRewritten", "firstRewritten", "clearRewritten"] {
        list_verified(&cp, method);
    }
    // n, c1, c2, then each line's unit price and quantity.
    let dup = list_refuted(&cp, "totalSkippingDuplicates");
    assert!(dup[0] >= 2 && (dup[1] == 0 || (dup[0] == 3 && dup[2] == 1 && dup[1] == 1)), "a line given twice in a row: {dup:?}");
    let reordered = list_refuted(&cp, "firstReordered");
    assert!(reordered[0] >= 2, "a list with a last line other than its first: {reordered:?}");
    let copied = list_refuted(&cp, "firstByCopy");
    assert!(copied[0] >= 1, "any line: {copied:?}");
    let aliased = list_refuted(&cp, "clearBlindToAliases");
    assert!(aliased[0] >= 2, "one line given twice: {aliased:?}");
    let distinct = list_refuted(&cp, "elementsAreDistinct");
    assert_eq!(distinct[1], 0, "elements 0 and 1 one line: {distinct:?}");
}

/// An array's cell holds a symbolic reference as a field does: stored as it is when every object it may be is of the
/// array's element type, so that `List.of`'s varargs array over a harness's picks costs no split per pick (each pick
/// had split the path per object it may be, `n!` paths for `n` elements: the list sweep's cliff past five lines). The
/// reference read back is the one stored (proved), a claim that it is the first line is refuted where it is the
/// second, and a store the JVM refuses (`ArrayStoreException`, a String into a `Line[]`) is still refused by name
/// under both search orders, never stored.
#[test]
fn an_array_cell_holds_a_symbolic_reference_of_its_element_type() {
    let Some(cp) = checker_classes() else { return };
    list_verified(&cp, "cellKeepsTheReference");
    let first = list_refuted(&cp, "cellHoldsTheFirst");
    assert_ne!(first[0], 0, "the second line: {first:?}");
    for merge_after in [0, u64::MAX] {
        let out = list_checked(&cp, "cellOfAnotherClass", merge_after);
        assert_eq!(out.verdict, Verdict::Unverifiable, "merging after {merge_after}");
        let problem = out.problem.unwrap_or_default();
        assert!(problem.contains("an aastore of a java.lang.String into a values.Lists$Line[] (ArrayStoreException)"), "merging after {merge_after}: {problem}");
    }
}

/// The models' other behaviour the kernels may reach, as the JDK's: `size`, `isEmpty` and the iterator (each
/// element in order, then `NoSuchElementException`); `get` out of range an `IndexOutOfBoundsException` from a list
/// of one or two and an `ArrayIndexOutOfBoundsException` from any other, a claim that they are one class refuted;
/// a null element refused by `List.of`; every change refused; `copyOf` of such a list the list itself, and one empty
/// list. `copyOf` of another implementation (an `ArrayList`) is refused by name, never taken for one of these.
#[test]
fn the_list_models_throw_refuse_and_share_as_the_jdks_do() {
    let Some(cp) = checker_classes() else { return };
    for method in ["sizeAndIteration", "getOutOfRange", "ofRejectsNull", "changesAreRefused", "copyOfIsTheList", "oneEmptyList"] {
        list_verified(&cp, method);
    }
    let one_class = list_refuted(&cp, "getThrowsOneClass");
    assert!(one_class[0] == 1 || one_class[0] == 2, "a List12: {one_class:?}");
    // The gap scan agrees: the models' methods are walked, as the engine runs them, and none is a gap; an
    // `ArrayList` still is one.
    let scan = |target: &str| bmc::gaps::scan(&cp, &bmc::gaps::roots(&cp, &[format!("values.Lists#{target}")]).unwrap()).unwrap();
    for (target, walked) in [("sizeAndIteration", "java.util.ImmutableCollections$ListItr.next"), ("clearRewritten", "java.util.ImmutableCollections$ListN.get"), ("copyOfIsTheList", "java.util.ImmutableCollections.listCopy")] {
        let s = scan(target);
        assert!(s.gaps.is_empty() && s.refused.is_empty(), "{target}: {:?} {:?}", s.gaps, s.refused);
        assert!(s.methods.iter().any(|m| m.starts_with(walked)), "{target}: {:?}", s.methods);
    }
    assert!(scan("copyOfAnotherImplementation").gaps.keys().any(|g| g.owner == "java/util/ArrayList"));
    let out = list_checked(&cp, "copyOfAnotherImplementation", u64::MAX);
    assert_eq!(out.verdict, Verdict::Unverifiable);
    let problem = out.problem.unwrap_or_default();
    assert!(problem.contains("jdk-constructor") && problem.contains("java.util.ArrayList"), "{problem}");
}

/// The kernels a check of [`adapted_lists`] compares, by name in `values.Lists`, each taking the list.
struct AdaptedCheck {
    method: &'static str,
    before: &'static str,
    after: &'static str,
    /// The claim, in Java, over the versions' lists `before` and `after` and their made lines `b0`..`b2`, `a0`..`a2`.
    claim: &'static str,
    nullable: bool,
}

const ADAPTED_CHECKS: &[AdaptedCheck] = &[
    AdaptedCheck { method: "total", before: "totalBefore", after: "totalAfter", claim: "Lists.totalBefore(before) == Lists.totalAfter(after)", nullable: false },
    AdaptedCheck { method: "totalDuplicateSkipped", before: "totalBefore", after: "totalDuplicateSkipped", claim: "Lists.totalBefore(before) == Lists.totalDuplicateSkipped(after)", nullable: false },
    AdaptedCheck { method: "first", before: "firstBefore", after: "firstAfter", claim: "node(Lists.firstBefore(before), b0, b1, b2) == node(Lists.firstAfter(after), a0, a1, a2)", nullable: false },
    AdaptedCheck { method: "firstIsLast", before: "firstBefore", after: "firstIsLast", claim: "node(Lists.firstBefore(before), b0, b1, b2) == node(Lists.firstIsLast(after), a0, a1, a2)", nullable: false },
    AdaptedCheck { method: "firstCopied", before: "firstBefore", after: "firstCopied", claim: "node(Lists.firstBefore(before), b0, b1, b2) == node(Lists.firstCopied(after), a0, a1, a2)", nullable: false },
    AdaptedCheck { method: "clear", before: "clearBefore", after: "clearAfter", claim: "Lists.clearBefore(before) == Lists.clearAfter(after) && b0.quantity == a0.quantity && b1.quantity == a1.quantity && b2.quantity == a2.quantity", nullable: false },
    AdaptedCheck { method: "clearAliasBlind", before: "clearBefore", after: "clearAliasBlind", claim: "Lists.clearBefore(before) == Lists.clearAliasBlind(after) && b0.quantity == a0.quantity && b1.quantity == a1.quantity && b2.quantity == a2.quantity", nullable: false },
    AdaptedCheck { method: "nullableTotal", before: "totalBefore", after: "totalAfter", claim: "(before == null ? -1 : Lists.totalBefore(before)) == (after == null ? -1 : Lists.totalAfter(after))", nullable: true },
    AdaptedCheck { method: "neverNull", before: "totalBefore", after: "totalAfter", claim: "before != null", nullable: true },
];

/// The adapter of the basket's domain: at most 3 lines, nullable or not.
fn basket_lists(nullable: bool) -> ListAdapter {
    ListAdapter::new(jvmcontract::spec::plans::ElementKind::Object { class: "values.Lists.Line".into() }, 3, nullable).unwrap()
}

/// `values.AdaptedLists`: one harness-shaped check per [`ADAPTED_CHECKS`] entry, its lists made by the adapter's
/// own Java (`ListAdapter::admitted`, `ListAdapter::java`) over three lines each version makes by their
/// constructor, from the same inputs: the adapter's choices, then each line's unit price and quantity. Compiled
/// against the fixtures, into a directory of its own.
fn adapted_lists() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        let fixtures = compiled()?;
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("values-adapted");
        let _ = std::fs::remove_dir_all(&out);
        std::fs::create_dir_all(out.join("src/values")).unwrap();
        let mut java = String::from("package values;\n\n/** Generated by lib/tests/values.rs from values::ListAdapter's Java. */\npublic final class AdaptedLists {\n    private AdaptedLists() {\n    }\n\n    /** Which made line `r` is, by identity: 0 to 2, -1 for another object, -2 for null. */\n    static int node(Lists.Line r, Lists.Line m0, Lists.Line m1, Lists.Line m2) {\n        return r == null ? -2 : r == m0 ? 0 : r == m1 ? 1 : r == m2 ? 2 : -1;\n    }\n");
        for check in ADAPTED_CHECKS {
            let adapter = basket_lists(check.nullable);
            let params: Vec<String> = adapter.choices("lines").iter().map(|c| format!("int {c}")).chain((0..3).flat_map(|i| [format!("int u{i}"), format!("int q{i}")])).collect();
            java.push_str(&format!("\n    public static void {}({}) {{\n", check.method, params.join(", ")));
            java.push_str(&format!("        if (!({}) || q0 < 0 || q1 < 0 || q2 < 0) {{\n            return;\n        }}\n", adapter.admitted("lines")));
            for (version, letter) in [("before", 'b'), ("after", 'a')] {
                let made: Vec<String> = (0..3).map(|i| format!("{letter}{i}")).collect();
                for (i, m) in made.iter().enumerate() {
                    java.push_str(&format!("        Lists.Line {m} = new Lists.Line(u{i}, q{i});\n"));
                }
                for line in adapter.java("lines", version, "Lists.Line", &made).unwrap().lines() {
                    java.push_str(&format!("        {line}\n"));
                }
            }
            java.push_str(&format!("        if (!({})) {{\n            throw new AssertionError();\n        }}\n    }}\n", check.claim));
        }
        java.push_str("}\n");
        let source = out.join("src/values/AdaptedLists.java");
        std::fs::write(&source, java).unwrap();
        let status = Command::new("javac").args(["-g", "-proc:none", "-cp"]).arg(fixtures).arg("-d").arg(out.join("classes")).arg(&source).status().expect("javac runs");
        assert!(status.success(), "the adapter's Java compiles");
        Some(out.join("classes"))
    })
    .as_deref()
}

/// What a version did on a rebuilt witness, as a check observes it: the kernel's result (a number, or which plan
/// node it returned), and each made line's quantity after.
fn observed(m: &mut Machine, nodes: &Nodes, kernel: &str, list: Value) -> (String, Vec<i32>) {
    let class = m.cp.application(LISTS).unwrap().unwrap();
    let descriptor = class.methods.iter().find(|x| x.name == kernel).unwrap().descriptor.clone();
    let result = match m.call_static(LISTS, kernel, &descriptor, vec![list]) {
        Ok(Some(Value::Long(n))) => n.to_string(),
        Ok(Some(Value::Null)) => "null".into(),
        Ok(Some(r @ Value::Ref(_))) => nodes.id_of(r).map_or("another object".into(), |id| format!("node {id}")),
        Err(Fault::Throw(r)) => format!("throws {}", m.class_of(r)),
        other => panic!("{kernel}: {other:?}"),
    };
    let quantities = (0..3).map(|id| match m.get_field(nodes.get(id).unwrap(), "quantity") {
        Ok(Value::Int(q)) => q,
        other => panic!("{other:?}"),
    });
    (result, quantities.collect())
}

/// A check of [`adapted_lists`] refuted under both search orders, its witness read by the adapter
/// (`ListAdapter::read`: the list as the plan's nodes) and replayed two ways: the harness on the JVM, which must
/// throw its `AssertionError`, and each version's kernel in the interpreter, called on its own on the list the
/// adapter rebuilds over that version's lines (`ValueAdapter::rebuild`), which must observe a difference. Each
/// rebuilt list encodes back as the witness's (`ValueAdapter::encode`). Returns the witness's list and its inputs.
fn adapted_refuted(cp: &ClassPath, classes: &str, check: &AdaptedCheck) -> (WitnessValue, Vec<i32>) {
    let adapter = basket_lists(check.nullable);
    let class = cp.application("values/AdaptedLists").unwrap().unwrap();
    let arity = MethodDescriptor::parse(&class.methods.iter().find(|m| m.name == check.method).unwrap().descriptor).unwrap().params.len();
    let mut found = Vec::new();
    for merge_after in [0, u64::MAX] {
        let out = bmc::check(cp, "values/AdaptedLists", check.method, &Options { merge_after, ..Options::default() }).unwrap();
        assert_eq!(out.verdict, Verdict::Violation, "{} (merging after {merge_after}): {:?}", check.method, out.problem);
        let args: Vec<i32> = (0..arity as u32).map(|slot| out.raw_inputs.get(&slot).map(|v| v.parse().unwrap()).unwrap_or(0)).collect();
        let jvm = run_on_jvm(Path::new(classes), &[format!("values.AdaptedLists {} {}", check.method, args.iter().map(|a| a.to_string()).collect::<Vec<_>>().join(" "))]).remove(0);
        assert_eq!(jvm, "throws java.lang.AssertionError", "{}{args:?} on the JVM", check.method);
        let choices = adapter.choices("lines").len();
        let witness = adapter.read(&args[..choices].iter().map(|&a| i64::from(a)).collect::<Vec<_>>(), &[0, 1, 2]).unwrap();
        let mut m = Machine::new(cp);
        let mut seen = Vec::new();
        for kernel in [check.before, check.after] {
            let mut nodes = Nodes::new();
            for id in 0..3 {
                let (u, q) = (args[choices + 2 * id], args[choices + 2 * id + 1]);
                let line = m.construct("values/Lists$Line", "(JI)V", vec![Value::Long(i64::from(u)), Value::Int(q)]).unwrap();
                nodes.insert(id as u32, line);
            }
            let list = adapter.rebuild(&mut m, &witness, &nodes).unwrap();
            assert_eq!(adapter.encode(&m, list, &nodes).unwrap(), witness, "a rebuilt list encodes as its witness");
            seen.push(if list == Value::Null { ("null".into(), vec![]) } else { observed(&mut m, &nodes, kernel, list) });
        }
        if check.claim != "before != null" {
            assert_ne!(seen[0], seen[1], "{}{args:?}: the versions differ on the rebuilt lists ({witness:?})", check.method);
        }
        found.push((witness, args));
    }
    found.remove(0)
}

/// V2's adapter, end to end: the basket's kernels checked over lists a harness makes by the adapter's own Java,
/// three lines per version picked by the adapter's choices, so that any two elements may be one object. Each
/// rewrite proved; each planted defect refuted, its witness read by the adapter as the plan's nodes in order and
/// replayed on the JVM and, through the adapter's rebuilt lists, in the interpreter. The negative controls: a
/// duplicated element (one line twice), a reordered one (the last for the first), a copy for the element
/// (identity, observed as the node returned), and an alias between mutable elements (one line cleared twice). A
/// nullable domain's null is a witness of its own. Before, no adapter existed (`values::adapter` refused every
/// list), and nothing read a list out of a witness or rebuilt one.
#[test]
fn the_list_adapter_makes_reads_and_rebuilds_lists_that_keep_order_duplicates_and_identity() {
    let (Some(fixtures), Some(adapted)) = (compiled(), adapted_lists()) else { return };
    let mut cp = ClassPath::new();
    cp.add(fixtures).unwrap();
    cp.add(adapted).unwrap();
    let cp = cp.with_default_jdk();
    let classes = format!("{}:{}", adapted.display(), fixtures.display());
    let node = |id| WitnessValue::Node { id };
    for check in ADAPTED_CHECKS.iter().filter(|c| ["total", "first", "clear", "nullableTotal"].contains(&c.method)) {
        for merge_after in [0, u64::MAX] {
            let out = bmc::check(&cp, "values/AdaptedLists", check.method, &Options { merge_after, ..Options::default() }).unwrap();
            assert_eq!(out.verdict, Verdict::Verified, "{} (merging after {merge_after}): {:?}", check.method, out.problem);
        }
    }
    let by = |name: &str| ADAPTED_CHECKS.iter().find(|c| c.method == name).unwrap();
    let elements = |w: &WitnessValue| match w {
        WitnessValue::List { elements } => elements.clone(),
        other => panic!("{other:?}"),
    };
    let (dup, _) = adapted_refuted(&cp, &classes, by("totalDuplicateSkipped"));
    assert!(elements(&dup).windows(2).any(|w| w[0] == w[1]), "a line given twice in a row: {dup:?}");
    let (last, _) = adapted_refuted(&cp, &classes, by("firstIsLast"));
    let last = elements(&last);
    assert!(last.len() >= 2 && last.first() != last.last(), "a last line other than the first: {last:?}");
    let (copied, _) = adapted_refuted(&cp, &classes, by("firstCopied"));
    assert_eq!(elements(&copied).first(), Some(&node(0)), "any line: {copied:?}");
    let (aliased, args) = adapted_refuted(&cp, &classes, by("clearAliasBlind"));
    let aliased = elements(&aliased);
    let twice = aliased.iter().find(|e| aliased.iter().filter(|o| o == e).count() > 1);
    assert!(twice.is_some(), "one line given twice: {aliased:?}");
    let Some(WitnessValue::Node { id }) = twice else { panic!() };
    assert!(args[3 + 2 * *id as usize + 1] > 0, "with a quantity to clear: {args:?}");
    let (none, _) = adapted_refuted(&cp, &classes, by("neverNull"));
    assert_eq!(none, WitnessValue::Null);
}

// The evidence records of the modelled operations (V3 step 1, `values::OPERATIONS`), checked against the boundary
// cases of `values.Operations` that sample them, on the JVM, in the interpreter and in the own checker.

const OPS: &str = "values.Operations";
const C: i32 = 0x41;

/// The boundary cases of every modelled operation: empty, one, the most, past the end; null where an operation
/// takes it; isolated surrogates, a pair and NUL as content; duplicates and aliases as elements.
const OPERATION_CASES: &[Case] = &[
    case(OPS, "literalUnit", &[0]),
    case(OPS, "literalUnit", &[1]),
    case(OPS, "literalUnit", &[2]),
    case(OPS, "literalUnit", &[3]),
    case(OPS, "literalInterned", &[]),
    case(OPS, "concatenated", &[0, 0, 0, 0, 0, 0, 0, 0]),
    case(OPS, "concatenated", &[-1, 0, 0, 0, 2, SMILE.0, SMILE.1, 0]),
    case(OPS, "concatenated", &[3, HIGH, 0, LOW, -1, 0, 0, 0]),
    case(OPS, "withChar", &[2, C, LOW, 0, HIGH]),
    case(OPS, "withChar", &[-1, 0, 0, 0, 0]),
    case(OPS, "length", &[0, 0, 0, 0]),
    case(OPS, "length", &[2, SMILE.0, SMILE.1, 0]),
    case(OPS, "length", &[3, HIGH, 0, LOW]),
    case(OPS, "length", &[-1, 0, 0, 0]),
    case(OPS, "isEmpty", &[0, 0, 0, 0]),
    case(OPS, "isEmpty", &[1, 0, 0, 0]),
    case(OPS, "isEmpty", &[-1, 0, 0, 0]),
    case(OPS, "charAt", &[3, HIGH, 0, LOW, 0]),
    case(OPS, "charAt", &[3, HIGH, 0, LOW, 2]),
    case(OPS, "charAt", &[3, HIGH, 0, LOW, 3]),
    case(OPS, "charAt", &[3, HIGH, 0, LOW, -1]),
    case(OPS, "charAt", &[0, 0, 0, 0, 0]),
    case(OPS, "charAt", &[-1, 0, 0, 0, 0]),
    case(OPS, "equalsContent", &[2, SMILE.0, SMILE.1, 0, 2, SMILE.0, SMILE.1, 0]),
    case(OPS, "equalsContent", &[1, HIGH, 0, 0, 1, FFFD, 0, 0]),
    case(OPS, "equalsContent", &[1, HIGH, 0, 0, 1, LOW, 0, 0]),
    case(OPS, "equalsContent", &[1, C, 0, 0, 2, C, 0, 0]),
    case(OPS, "equalsContent", &[0, 0, 0, 0, 0, 0, 0, 0]),
    case(OPS, "equalsContent", &[1, 0, 0, 0, -1, 0, 0, 0]),
    case(OPS, "equalsContent", &[-1, 0, 0, 0, 1, 0, 0, 0]),
    case(OPS, "equalsItself", &[1, HIGH, 0, 0]),
    case(OPS, "equalsAnotherClass", &[0, 0, 0, 0]),
    case(OPS, "equalNotSame", &[2, HIGH, 0, 0]),
    case(OPS, "equalNotSame", &[0, 0, 0, 0]),
    case(OPS, "startsWith", &[2, SMILE.0, SMILE.1, 0, 1, SMILE.0, 0, 0]),
    case(OPS, "startsWith", &[2, SMILE.0, SMILE.1, 0, 1, SMILE.1, 0, 0]),
    case(OPS, "startsWith", &[1, C, 0, 0, 0, 0, 0, 0]),
    case(OPS, "startsWith", &[1, C, 0, 0, 2, C, C, 0]),
    case(OPS, "startsWith", &[1, C, 0, 0, -1, 0, 0, 0]),
    case(OPS, "startsWith", &[-1, 0, 0, 0, 0, 0, 0, 0]),
    case(OPS, "ofWithNull", &[1, 0]),
    case(OPS, "ofWithNull", &[2, 1]),
    case(OPS, "ofWithNull", &[3, 2]),
    case(OPS, "ofWithNull", &[2, 2]),
    case(OPS, "ofKeepsDuplicates", &[7]),
    case(OPS, "elementsAreTheObjects", &[5]),
    case(OPS, "emptyIsShared", &[]),
    case(OPS, "otherwiseFresh", &[1]),
    case(OPS, "otherwiseFresh", &[3]),
    case(OPS, "copyOfIsTheList", &[0]),
    case(OPS, "copyOfIsTheList", &[2]),
    case(OPS, "copyOfIsTheList", &[3]),
    case(OPS, "copyOfIsTheList", &[-1]),
    case(OPS, "size", &[0]),
    case(OPS, "size", &[1]),
    case(OPS, "size", &[2]),
    case(OPS, "size", &[3]),
    case(OPS, "size", &[10]),
    case(OPS, "isEmptyList", &[0]),
    case(OPS, "isEmptyList", &[1]),
    case(OPS, "get", &[1, 0]),
    case(OPS, "get", &[1, 1]),
    case(OPS, "get", &[2, 1]),
    case(OPS, "get", &[2, -1]),
    case(OPS, "get", &[3, 2]),
    case(OPS, "get", &[3, 3]),
    case(OPS, "get", &[10, 9]),
    case(OPS, "get", &[10, 10]),
    case(OPS, "get", &[0, 0]),
    case(OPS, "iterated", &[0]),
    case(OPS, "iterated", &[2]),
    case(OPS, "iterated", &[3]),
    case(OPS, "nextPastTheEnd", &[0, 0]),
    case(OPS, "nextPastTheEnd", &[0, 1]),
    case(OPS, "nextPastTheEnd", &[2, 2]),
    case(OPS, "nextPastTheEnd", &[2, 3]),
    case(OPS, "nextPastTheEnd", &[3, 1]),
    case(OPS, "add", &[0]),
    case(OPS, "add", &[3]),
    case(OPS, "set", &[1, 0]),
    case(OPS, "set", &[1, 5]),
    case(OPS, "removeAt", &[2, 0]),
    case(OPS, "clear", &[0]),
    case(OPS, "clear", &[2]),
    case(OPS, "iteratorRemove", &[1]),
    case(OPS, "iteratorRemove", &[3]),
];

/// Exceptions a case may throw, each after the ones of them that are its subclasses, so that a generated check
/// catches exactly the JVM's class.
const SUBCLASSES: &[(&str, &[&str])] = &[("java.lang.IndexOutOfBoundsException", &["java.lang.StringIndexOutOfBoundsException", "java.lang.ArrayIndexOutOfBoundsException"])];

/// A method of `values.Sampled` per case, which throws an AssertionError unless the case gives what the JVM gave,
/// for the own checker: a String result by its length and code units, an exception by its exact class.
fn sampled_checks(fixtures: &Path, cp: &ClassPath, cases: &[Case], jvm: &[String]) -> PathBuf {
    let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("values-sampled");
    let _ = std::fs::remove_dir_all(&out);
    std::fs::create_dir_all(out.join("src/values")).unwrap();
    let class = cp.application("values/Operations").unwrap().unwrap();
    let mut java = String::from("package values;\n\n/** Generated by lib/tests/values.rs: each method fails unless its case of Operations gives the JVM's outcome. */\nfinal class Sampled {\n    private Sampled() {\n    }\n");
    for (i, (case, expected)) in cases.iter().zip(jvm).enumerate() {
        let method = class.methods.iter().find(|m| m.name == case.method && MethodDescriptor::parse(&m.descriptor).unwrap().params.len() == case.args.len()).unwrap();
        let ret = MethodDescriptor::parse(&method.descriptor).unwrap().ret;
        let call = format!("Operations.{}({})", case.method, case.args.iter().map(|a| a.to_string()).collect::<Vec<_>>().join(", "));
        let fail = "throw new AssertionError();";
        let body = match expected.split_once(' ').unwrap_or((expected, "")) {
            ("throws", class) => {
                let subs = SUBCLASSES.iter().find(|(c, _)| *c == class).map(|(_, s)| *s).unwrap_or(&[]);
                let mut b = format!("try {{\n            {call};\n        }}");
                for sub in subs {
                    b.push_str(&format!(" catch ({sub} e) {{\n            {fail}\n        }}"));
                }
                b.push_str(&format!(" catch ({class} e) {{\n            return;\n        }}\n        {fail}"));
                b
            }
            ("int", n) => format!("if ({call} != {n}) {{\n            {fail}\n        }}"),
            ("bool", "true") => format!("if (!{call}) {{\n            {fail}\n        }}"),
            ("bool", "false") => format!("if ({call}) {{\n            {fail}\n        }}"),
            ("null", _) => format!("if ({call} != null) {{\n            {fail}\n        }}"),
            ("str", units) => {
                assert_eq!(ret, Type::Object("java/lang/String".into()));
                let units: Vec<&str> = units.split_whitespace().collect();
                let each: String = units.iter().enumerate().map(|(k, u)| format!(" || r.charAt({k}) != 0x{u}")).collect();
                format!("String r = {call};\n        if (r == null || r.length() != {}{each}) {{\n            {fail}\n        }}", units.len())
            }
            other => panic!("{other:?}"),
        };
        java.push_str(&format!("\n    /** {}{:?}: {expected} */\n    static void c{i}() {{\n        {body}\n    }}\n", case.method, case.args));
    }
    java.push_str("}\n");
    let source = out.join("src/values/Sampled.java");
    std::fs::write(&source, java).unwrap();
    let status = Command::new("javac").args(["-g", "-proc:none", "-cp"]).arg(fixtures).arg("-d").arg(out.join("classes")).arg(&source).status().expect("javac runs");
    assert!(status.success(), "the sampled checks compile");
    out.join("classes")
}

/// Every modelled operation has an evidence record, and each record holds against the cases that sample it: each
/// case gives the JVM's outcome in the interpreter and in the own checker, and the exceptions its cases throw on
/// the JVM are exactly the record's `throws`. Before, the models' evidence was one record per model
/// (`values::string_model`, `values::list_model`), saying nothing of an operation's inputs or exceptions.
#[test]
fn every_modelled_operation_has_a_record_its_boundary_cases_hold_on_the_jvm_the_interpreter_and_the_checker() {
    use jvmcontract::spec::plans::EvidenceLevel;
    use jvmcontract::values::{Family, OPERATIONS};
    // The records' own consistency: each samples methods that have cases, each case's method is one record's,
    // sampled conformance is never more than `tested`, and the JDK is the one the cases run on.
    for record in OPERATIONS {
        assert!(!record.sampled_by.is_empty(), "{}", record.operation);
        assert_eq!(record.level, EvidenceLevel::Tested, "{}", record.operation);
        for method in record.sampled_by {
            assert!(OPERATION_CASES.iter().any(|c| c.method == *method), "{}: no case of {method}", record.operation);
        }
        assert_eq!(record.model().level, EvidenceLevel::Tested);
    }
    for case in OPERATION_CASES {
        assert_eq!(OPERATIONS.iter().filter(|r| r.sampled_by.contains(&case.method)).count(), 1, "{}: one record samples it", case.method);
    }
    // Every String method the own checker models on content has a record, and every record of one is modelled.
    let string_records: Vec<(&str, &str)> = OPERATIONS
        .iter()
        .filter_map(|r| r.operation.strip_prefix("java.lang.String."))
        .map(|m| m.split_at(m.find('(').unwrap()))
        .collect();
    for (name, descriptor) in &string_records {
        assert!(bmc::models_string_method("java/lang/String", name, descriptor), "{name}{descriptor}");
    }
    let Some(cp) = checker_classes() else { return };
    let string = cp.load("java/lang/String").unwrap().expect("the JDK's String").class;
    let modelled: Vec<String> = string.methods.iter().filter(|m| bmc::models_string_method("java/lang/String", &m.name, &m.descriptor)).map(|m| format!("{}{}", m.name, m.descriptor)).collect();
    assert_eq!(modelled.len(), string_records.len(), "a record for each of {modelled:?}");
    for record in OPERATIONS {
        assert_eq!(Some(record.jdk().to_string()), bmc::gaps::jdk_release(), "{}: sampled on the JDK the cases run on", record.operation);
        assert!(matches!(record.family, Family::String | Family::List));
    }

    // The interpreter gives the JVM's outcome on every case.
    conforms(OPERATION_CASES);
    let fixtures = compiled().unwrap();
    let jvm = on_jvm(fixtures, OPERATION_CASES);

    // The exceptions each record's cases throw on the JVM are exactly the ones it lists.
    for record in OPERATIONS {
        let mut seen: Vec<&str> = OPERATION_CASES.iter().zip(&jvm).filter(|(c, _)| record.sampled_by.contains(&c.method)).filter_map(|(_, o)| o.strip_prefix("throws ")).collect();
        seen.sort();
        seen.dedup();
        let mut listed = record.throws.to_vec();
        listed.sort();
        assert_eq!(seen, listed, "{}: the exceptions its cases throw on the JVM", record.operation);
    }

    // The own checker reaches the JVM's outcome on every case: each generated check is proved.
    let sampled = sampled_checks(fixtures, &cp, OPERATION_CASES, &jvm);
    let mut with = ClassPath::new();
    with.add(&sampled).unwrap();
    with.add(fixtures).unwrap();
    let with = with.with_default_jdk();
    let mut wrong = Vec::new();
    for (i, (case, expected)) in OPERATION_CASES.iter().zip(&jvm).enumerate() {
        let out = bmc::check(&with, "values/Sampled", &format!("c{i}"), &Options::default()).unwrap();
        if out.verdict != Verdict::Verified {
            wrong.push(format!("{}{:?} (the JVM: {expected}): {:?} {:?}", case.method, case.args, out.verdict, out.problem));
        }
    }
    assert!(wrong.is_empty(), "the own checker differs from the JVM:\n{}", wrong.join("\n"));
}

const OUTSIDE: &str = "values/Outside";

/// The checks of [`OUTSIDE`], each reaching one operation outside the values models, with the gap the strict engine
/// must name for it (its id up to the JDK's version), or the words of its refusal: `java.util.List.toArray()` has
/// an array result, which the engine refuses for any JDK call. A list method the models implement is outside them
/// when no record of `values::OPERATIONS` samples it.
const OUTSIDE_THE_MODELS: &[(&str, &str)] = &[
    ("upper", "jdk-reference-method:java.lang.String.toUpperCase()Ljava/lang/String;"),
    ("indexOf", "jdk-primitive-method:java.lang.String.indexOf(I)I"),
    ("hashCodeOf", "jdk-primitive-method:java.lang.String.hashCode()I"),
    ("substring", "jdk-reference-method:java.lang.String.substring(I)Ljava/lang/String;"),
    ("compareTo", "jdk-primitive-method:java.lang.String.compareTo(Ljava/lang/String;)I"),
    ("equalsAsObject", "jdk-primitive-method:java.lang.Object.equals(Ljava/lang/Object;)Z"),
    ("lengthAsCharSequence", "jdk-primitive-method:java.lang.CharSequence.length()I"),
    ("valueOf", "jdk-static-method:java.lang.String.valueOf(I)Ljava/lang/String;"),
    ("contains", "jdk-primitive-method:java.util.List.contains(Ljava/lang/Object;)Z"),
    ("indexOfElement", "jdk-primitive-method:java.util.List.indexOf(Ljava/lang/Object;)I"),
    ("lastIndexOf", "jdk-primitive-method:java.util.List.lastIndexOf(Ljava/lang/Object;)I"),
    ("equalLists", "jdk-primitive-method:java.util.List.equals(Ljava/lang/Object;)Z"),
    ("emptyHashCode", "jdk-primitive-method:java.util.List.hashCode()I"),
    ("hashCodeAsObject", "jdk-primitive-method:java.lang.Object.hashCode()I"),
    ("toArray", "outside the fragment: java.util.List.toArray on an object the engine does not model"),
    ("addAll", "jdk-primitive-method:java.util.List.addAll(Ljava/util/Collection;)Z"),
    ("removeElement", "jdk-primitive-method:java.util.List.remove(Ljava/lang/Object;)Z"),
    ("sort", "jdk-void-method:java.util.List.sort(Ljava/util/Comparator;)V"),
    ("arrayForm", "jdk-static-method:java.util.List.of([Ljava/lang/Object;)Ljava/util/List;"),
    ("elevenElements", "jdk-static-method:java.util.List.of([Ljava/lang/Object;)Ljava/util/List;"),
];

/// V3's strict gap detection: an operation outside the values models is a named gap under the strict engine, never
/// a verdict. Every claim of [`OUTSIDE`] holds on the JVM, so a verdict could only rest on semantics no record
/// vouches for: a String method other than the five modelled on content, or a list method or form the list models
/// implement (`contains`, `equals`, `hashCode`, `addAll`, `List.of(E...)` …) that no record samples. Each run, merging
/// from the start and never, has no verdict and names the operation's gap (or its refusal), and the gap scan reports
/// the same gap and walks none of the models' unsampled methods. Before, the own checker ran every method the list
/// models implement, so `contains`, `indexOf`, `equals`, `hashCode`, `addAll`, `sort` and the array form were proved.
#[test]
fn an_operation_outside_the_values_models_is_a_named_gap_under_strict() {
    let Some(cp) = checker_classes() else { return };
    let class = cp.application(OUTSIDE).unwrap().expect("the checks");
    let lines: Vec<String> = OUTSIDE_THE_MODELS
        .iter()
        .map(|(method, _)| {
            let m = class.methods.iter().find(|m| m.name == *method).unwrap_or_else(|| panic!("{method}"));
            let arg = if MethodDescriptor::parse(&m.descriptor).unwrap().params[0] == Type::Int { "7" } else { "s:97,98" };
            format!("values.Outside {method} {arg}")
        })
        .collect();
    let jvm = run_on_jvm(compiled().unwrap(), &lines);
    let mut wrong = Vec::new();
    for ((method, expected), on_jvm) in OUTSIDE_THE_MODELS.iter().zip(&jvm) {
        assert_eq!(on_jvm, "null", "{method}: its claim holds on the JVM");
        for merge_after in [0, u64::MAX] {
            let out = bmc::check(&cp, OUTSIDE, method, &Options { parameters: bounded(3), merge_after, ..Options::default() }).unwrap();
            let problem = out.problem.clone().unwrap_or_default();
            let named = if expected.starts_with("outside") { problem.contains(expected) } else { out.gaps.iter().any(|g| g.id.starts_with(&format!("{expected}@")) && g.treatment == Some(bmc::gaps::GapTreatment::Refused)) };
            if out.verdict != Verdict::Unverifiable || !named {
                wrong.push(format!("{method} (merging after {merge_after}): {:?}, {problem}; gaps {:?}", out.verdict, out.gaps.iter().map(|g| &g.id).collect::<Vec<_>>()));
            }
        }
        let scan = bmc::gaps::scan(&cp, &bmc::gaps::roots(&cp, &[format!("values.Outside#{method}")]).unwrap()).unwrap();
        let reported = if expected.starts_with("outside") { scan.refused.values().any(|r| r.first.starts_with("java.util.List.toArray")) } else { scan.gaps.keys().any(|g| g.id(bmc::gaps::jdk_release().as_deref()).starts_with(&format!("{expected}@"))) };
        let unsampled: Vec<&String> = scan.methods.iter().filter(|m| m.starts_with("java.util.ImmutableCollections") && [".contains", ".indexOf", ".lastIndexOf", ".equals", ".hashCode", ".toArray", ".addAll", ".remove(Ljava/lang/Object;)", ".sort", ".listFromArray"].iter().any(|n| m.contains(n))).collect();
        if !reported || !unsampled.is_empty() {
            wrong.push(format!("{method}: the scan reports {:?} {:?}, and walks {unsampled:?}", scan.gaps.keys().map(|g| g.id(None)).collect::<Vec<_>>(), scan.refused));
        }
    }
    assert!(wrong.is_empty(), "{} operations outside the models not named as gaps:\n{}", wrong.len(), wrong.join("\n"));
}

// The tiny bound sweep (the values brief's acceptance: "a tiny sweep over the bound finds any immediate encoding
// cliff"): one correct check and one planted defect per family, each at a few bounds, timed. It asserts verdicts
// only; the times are printed (`--nocapture`) and recorded in the brief's Progress, never asserted.

/// The lengths the list sweep makes `values.SweptLists` for: up to [`jvmcontract::values::MAX_LIST_LENGTH`].
const SWEPT_LENGTHS: &[u32] = &[1, 2, 3, 4, 5, 6, 7, 8, 10];

/// `values.SweptLists`: for each of [`SWEPT_LENGTHS`], `total{n}` (the basket's rewrite by index) and `skipped{n}`
/// (its duplicate-skipping defect), over lists of up to `n` lines made by the list adapter's own Java, as
/// [`adapted_lists`] makes them for three.
fn swept_lists() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        let fixtures = compiled()?;
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("values-swept");
        let _ = std::fs::remove_dir_all(&out);
        std::fs::create_dir_all(out.join("src/values")).unwrap();
        let mut java = String::from("package values;\n\n/** Generated by lib/tests/values.rs's bound sweep from values::ListAdapter's Java. */\npublic final class SweptLists {\n    private SweptLists() {\n    }\n");
        for &n in SWEPT_LENGTHS {
            let adapter = ListAdapter::new(jvmcontract::spec::plans::ElementKind::Object { class: "values.Lists.Line".into() }, n, false).unwrap();
            for (method, after) in [(format!("total{n}"), "totalAfter"), (format!("skipped{n}"), "totalDuplicateSkipped")] {
                let params: Vec<String> = adapter.choices("lines").iter().map(|c| format!("int {c}")).chain((0..n).flat_map(|i| [format!("int u{i}"), format!("int q{i}")])).collect();
                java.push_str(&format!("\n    public static void {method}({}) {{\n", params.join(", ")));
                let quantities: Vec<String> = (0..n).map(|i| format!("q{i} < 0")).collect();
                java.push_str(&format!("        if (!({}) || {}) {{\n            return;\n        }}\n", adapter.admitted("lines"), quantities.join(" || ")));
                for (version, letter) in [("before", 'b'), ("after", 'a')] {
                    let made: Vec<String> = (0..n).map(|i| format!("{letter}{i}")).collect();
                    for (i, m) in made.iter().enumerate() {
                        java.push_str(&format!("        Lists.Line {m} = new Lists.Line(u{i}, q{i});\n"));
                    }
                    for line in adapter.java("lines", version, "Lists.Line", &made).unwrap().lines() {
                        java.push_str(&format!("        {line}\n"));
                    }
                }
                java.push_str(&format!("        if (Lists.totalBefore(before) != Lists.{after}(after)) {{\n            throw new AssertionError();\n        }}\n    }}\n"));
            }
        }
        java.push_str("}\n");
        let source = out.join("src/values/SweptLists.java");
        std::fs::write(&source, java).unwrap();
        let status = Command::new("javac").args(["-g", "-proc:none", "-cp"]).arg(fixtures).arg("-d").arg(out.join("classes")).arg(&source).status().expect("javac runs");
        assert!(status.success(), "the sweep's Java compiles");
        Some(out.join("classes"))
    })
    .as_deref()
}

/// One check of the sweep, timed, with a time limit of its own.
fn swept(cp: &ClassPath, class: &str, method: &str, parameters: Parameters, merge_after: u64, unwind: u32) -> (Outcome, f64) {
    let start = std::time::Instant::now();
    let out = bmc::check(cp, class, method, &Options { parameters, merge_after, unwind, timeout: std::time::Duration::from_secs(60), ..Options::default() }).unwrap();
    (out, start.elapsed().as_secs_f64())
}

/// The basket's total proved and its duplicate defect refuted over lists of up to `n` lines, for each of `lengths`,
/// merging paths from the start, and also never where `n` is at most 4; each printed with its time and the checker's
/// counts.
fn sweep_lists(lengths: &[u32]) {
    let (Some(fixtures), Some(swept_classes)) = (compiled(), swept_lists()) else { return };
    let mut cp = ClassPath::new();
    cp.add(fixtures).unwrap();
    cp.add(swept_classes).unwrap();
    let cp = cp.with_default_jdk();
    for &n in lengths {
        for (method, expected) in [(format!("total{n}"), Verdict::Verified), (format!("skipped{n}"), if n >= 2 { Verdict::Violation } else { Verdict::Verified })] {
            for merge_after in if n <= 4 { vec![0, u64::MAX] } else { vec![0] } {
                let (out, secs) = swept(&cp, "values/SweptLists", &method, Parameters::default(), merge_after, Options::default().unwind);
                println!("sweep list {method} merge {}: {:?} in {secs:.2} s ({} paths, {} merges, {} solves in {:.2} s, {} clauses)", if merge_after == 0 { "start" } else { "never" }, out.verdict, out.paths, out.merges, out.solves, out.solving, out.clauses);
                assert_eq!(out.verdict, expected, "{method} (merging after {merge_after}): {:?}", out.problem);
            }
        }
    }
}

/// The sweep: a String check proved and its defect refuted at bounds 1 to 64 (the content cap) under both search
/// orders, and the basket's total and its defect over lists of 1 to 10 lines (the adapter's bound,
/// [`jvmcontract::values::MAX_LIST_LENGTH`]), each with its time printed. A verdict that changes with the bound
/// (beyond the defect needing an input long enough) fails, and so does a check that doesn't finish within its time
/// limit. The list sweep had a cliff past five lines: each pick split the path per object at `List.of`'s varargs
/// array, `n!` paths, and 7 lines didn't finish. Since an array's cell holds a symbolic reference
/// ([`an_array_cell_holds_a_symbolic_reference_of_its_element_type`]), 10 lines take 908 paths and about 12 s.
#[test]
fn a_tiny_sweep_over_the_string_and_list_bounds() {
    let Some(cp) = checker_classes() else { return };
    // `equalsByUnits` loops over a String's units itself, so its loop needs an unwinding bound past the String's:
    // a bound of the check apart from the String's, and under the default (16) a longer String is the named
    // unwinding limit, never a verdict.
    let (out, _) = swept(&cp, CHECKS, "equalsByUnits", bounded(32), 0, Options::default().unwind);
    assert_eq!(out.verdict, Verdict::Unverifiable);
    assert!(out.problem.as_deref().unwrap_or_default().contains("a loop was not fully unwound with --unwind 16"), "{:?}", out.problem);
    for bound in [1, 2, 4, 8, 16, 32, 64] {
        for (method, expected) in [("vipRewritten", Verdict::Verified), ("vipShortened", if bound >= 2 { Verdict::Violation } else { Verdict::Verified }), ("equalsByUnits", Verdict::Verified)] {
            for merge_after in [0, u64::MAX] {
                let (out, secs) = swept(&cp, CHECKS, method, bounded(bound), merge_after, bound.max(16) + 1);
                println!("sweep string {method} bound {bound} merge {}: {:?} in {secs:.2} s ({} paths, {} clauses)", if merge_after == 0 { "start" } else { "never" }, out.verdict, out.paths, out.clauses);
                assert_eq!(out.verdict, expected, "{method} under {bound} (merging after {merge_after}): {:?}", out.problem);
            }
        }
    }
    sweep_lists(SWEPT_LENGTHS);
}

/// Every value domain of a claim (`kind: adapted`, in a construction plan or a modelled call's result) resolved
/// under `models` ([`values::ValueModels::resolve`]), with how many of each family it holds.
fn resolved_claim(claim: &serde_json::Value, models: &values::ValueModels) -> Result<(serde_json::Value, usize, usize), jvmcontract::spec::Unsupported> {
    fn walk(v: &mut serde_json::Value, models: &values::ValueModels, counts: &mut (usize, usize)) -> Result<(), jvmcontract::spec::Unsupported> {
        match v {
            serde_json::Value::Object(map) => {
                if map.get("kind").and_then(|k| k.as_str()) == Some("adapted") {
                    let stated: ValueDomain = serde_json::from_value(map["domain"].clone()).expect("an adapted value's domain is a ValueDomain");
                    match stated.kind {
                        ValueKind::String => counts.0 += 1,
                        ValueKind::List { .. } => counts.1 += 1,
                    }
                    map.insert("domain".into(), serde_json::to_value(models.resolve(&stated)?).unwrap());
                }
                map.values_mut().try_for_each(|x| walk(x, models, counts))
            }
            serde_json::Value::Array(items) => items.iter_mut().try_for_each(|x| walk(x, models, counts)),
            _ => Ok(()),
        }
    }
    let mut out = claim.clone();
    let mut counts = (0, 0);
    walk(&mut out, models, &mut counts)?;
    Ok((out, counts.0, counts.1))
}

/// Every adapted domain's `max_length` lowered by one.
fn shorter(claim: &serde_json::Value) -> serde_json::Value {
    let mut out = claim.clone();
    fn walk(v: &mut serde_json::Value) {
        match v {
            serde_json::Value::Object(map) => {
                if map.get("kind").and_then(|k| k.as_str()) == Some("adapted") {
                    let n = map["domain"]["max_length"].as_u64().unwrap();
                    map.get_mut("domain").unwrap()["max_length"] = (n - 1).into();
                }
                map.values_mut().for_each(walk);
            }
            serde_json::Value::Array(items) => items.iter_mut().for_each(walk),
            _ => {}
        }
    }
    walk(&mut out);
    out
}

/// The acceptance's "changing a String or list bound, a model's semantics or a snapshot rule invalidates the cached
/// evidence it affects", on the frozen claims of `tests/fixtures/application-core/golden/`: each claim's value
/// domains resolved under this tool's models carry their identity (the list model's with its bytecode's digest, and
/// each with its snapshot rule's, `values::STRING_SNAPSHOT` and `values::LIST_SNAPSHOT`, which the values unit test
/// `the_snapshot_rules_are_pinned_to_the_digests_the_models_identities_carry` holds to the adapters' encoding), so
/// a change of the list model or its snapshot rule changes exactly the claims over a list, a change of the String
/// model or its snapshot rule exactly those over a String, and a lower bound every claim with a value domain. "Changes" is checked on the claim the key digests whole (the
/// reuse stream's projection), and on the key itself: two claims never get one key, and until the projection knows
/// a planned domain, such a claim is uncacheable by the key's own refusal, never keyed without its domains.
#[test]
fn a_change_of_value_model_or_bound_changes_exactly_the_claims_it_affects() {
    use jvmcontract::spec::{self, CanonicalClaim, Part};
    let golden = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/application-core/golden");
    let current = values::ValueModels::current();
    let mut list_changed = current.clone();
    list_changed.list.source = format!("{}; models sha256 {}", values::LIST_MODEL, "0".repeat(64));
    let mut string_changed = current.clone();
    string_changed.string.source = values::STRING_MODEL.replace("model 1", "model 2");
    assert_ne!(string_changed.string, current.string, "the String model's identity names its version");
    let mut list_snapshot = current.clone();
    list_snapshot.list.source = current.list.source.replace(values::LIST_SNAPSHOT, &"0".repeat(64));
    let mut string_snapshot = current.clone();
    string_snapshot.string.source = current.string.source.replace(values::STRING_SNAPSHOT, &"0".repeat(64));
    assert!(list_snapshot.list != current.list && string_snapshot.string != current.string, "each identity carries its snapshot rule's digest");
    let differs = |what: &str, a: &serde_json::Value, b: &serde_json::Value| {
        assert_ne!(spec::cache::canonical(a), spec::cache::canonical(b), "{what}: the same claim");
        let (a, b): (CanonicalClaim, CanonicalClaim) = (serde_json::from_value(a.clone()).unwrap(), serde_json::from_value(b.clone()).unwrap());
        match (spec::cache::key(&a), spec::cache::key(&b)) {
            (Ok(x), Ok(y)) => assert_ne!(x, y, "{what}: the same key"),
            (Err(u), _) | (_, Err(u)) => assert_eq!(u.part, Part::Summaries, "{what}: uncacheable, by the claim key's own refusal: {u}"),
        }
    };
    let (mut strings, mut lists) = (0, 0);
    let mut names: Vec<_> = std::fs::read_dir(&golden).unwrap().map(|e| e.unwrap().file_name().into_string().unwrap()).filter(|n| n.ends_with("-claim.json")).collect();
    names.sort();
    for name in &names {
        let claim: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(golden.join(name)).unwrap()).unwrap();
        let (resolved, s, l) = resolved_claim(&claim, &current).unwrap_or_else(|u| panic!("{name}: {u}"));
        strings += s;
        lists += l;
        // The resolved claim is still the shared type, and resolving it again changes nothing.
        let parsed: CanonicalClaim = serde_json::from_value(resolved.clone()).unwrap_or_else(|e| panic!("{name}: {e}"));
        assert_eq!(serde_json::to_value(&parsed).unwrap(), resolved, "{name}");
        assert_eq!(resolved_claim(&resolved, &current).unwrap().0, resolved, "{name}: resolving is idempotent");
        let text = resolved.to_string();
        assert!(!text.contains(values::STATED_STRING_MODEL) && !text.contains(values::STATED_LIST_MODEL), "{name}: a stated model left in");
        assert_eq!(text.contains(values::STRING_MODEL), s > 0, "{name}: the String model's identity");
        assert_eq!(text.contains(&values::list_model_digest()), l > 0, "{name}: the list models' digest");
        assert_eq!(text.contains(values::STRING_SNAPSHOT), s > 0, "{name}: the String snapshot rule's digest");
        assert_eq!(text.contains(values::LIST_SNAPSHOT), l > 0, "{name}: the list snapshot rule's digest");
        // A change of a model reaches the claims over its family, and no other.
        for (what, changed, affected) in [
            ("the list model", &list_changed, l > 0),
            ("the String model", &string_changed, s > 0),
            ("the list snapshot rule", &list_snapshot, l > 0),
            ("the String snapshot rule", &string_snapshot, s > 0),
        ] {
            let after = resolved_claim(&claim, changed).unwrap().0;
            if affected {
                differs(&format!("{name}, {what} changed"), &resolved, &after);
                // A claim resolved under the earlier model is never resolved under the new one.
                let stale = resolved_claim(&resolved, changed).unwrap_err();
                assert!(stale.what.contains("evidence of another model's semantics isn't this one's"), "{name}: {stale}");
            } else {
                assert_eq!(after, resolved, "{name}: {what} changed, which it doesn't use");
            }
        }
        if s + l > 0 {
            differs(&format!("{name}, a lower bound"), &resolved, &resolved_claim(&shorter(&claim), &current).unwrap().0);
        }
    }
    // The frozen claims have both families: Q's codes are Strings, L's baskets lists.
    assert!(strings > 0 && lists > 0, "{strings} String and {lists} list domains in {names:?}");
    eprintln!("{} claims, {strings} String and {lists} list domains resolved", names.len());
}

/// A stand-in for JBMC in `dir`: `--version` is 6.11.0, the goto listing (`--show-goto-functions`) is `goto.txt`,
/// and every other run answers with `answer.txt`, or `answer.json` under `--json-ui`.
fn stand_in_jbmc(dir: &Path) -> PathBuf {
    let _ = std::fs::remove_dir_all(dir);
    std::fs::create_dir_all(dir).unwrap();
    let script = dir.join("jbmc");
    std::fs::write(&script, "#!/bin/sh\nif [ \"$1\" = --version ]; then echo 6.11.0; exit 0; fi\nd=$(dirname \"$0\")\ncase \"$*\" in *--show-goto-functions*) cat \"$d/goto.txt\"; exit 0;; esac\ncase \"$*\" in *--json-ui*) cat \"$d/answer.json\";; *) cat \"$d/answer.txt\";; esac\n").unwrap();
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(&script, std::fs::Permissions::from_mode(0o755)).unwrap();
    script
}

/// VF-023's tool side, a reproducer for the merge's change to `equivalence::confirm` (the objects stream's file;
/// the interface request in `llm-dlc/loops/application-core-values.md`). Stock JBMC 6.11.0 refutes the size of a
/// list that is one of two (`Choice.oneOrTwo`, job `20261108-093809-…`): its program dispatches `size()` by class,
/// with `java.util.List.size()`'s stub as the fallback, and on a reference to one of two objects it takes the wrong
/// branch. The own checker proves the claim, and the interpreter replays JBMC's witness as holding. A JBMC proof
/// through a stub confirms nothing under strict (`jbmc_gaps::hold`), and a JBMC refutation through a construct it
/// runs otherwise than the JVM that doesn't reproduce is no verdict (`confirm_takes_a_refutation_through_a_jbmc_defect_for_no_verdict`
/// in `tests/conformance.rs`). A refutation through a stub that doesn't reproduce is a stub's value, so it should
/// be no verdict too, the proof standing as the own checker's alone, not "the engines disagree". JBMC is a stand-in
/// here, answering with the refutation the real one gives (`n=1`) over a program that reaches the stub.
#[test]
#[ignore = "VF-023: fails until the merge makes a JBMC refutation through a stub that doesn't reproduce no verdict in equivalence::confirm"]
fn confirm_takes_a_refutation_through_a_jbmc_stub_that_does_not_reproduce_for_no_verdict() {
    let Some(classes) = compiled() else { return };
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("values-confirm-stub");
    let jbmc = stand_in_jbmc(&dir);
    let harness = jvmcontract::harness::PROPERTY_CLASS;
    let program = format!(
        "{harness}.check(int) /* java::{harness}.check:(I)V */\n        // 1 file {harness}.java line 1 function java::{harness}.check:(I)V bytecode-index 1\n     1: CALL java::values.Choice.oneOrTwo:(I)I(java::{harness}.check:(I)V::arg0i)\n\n^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\nvalues.Choice.oneOrTwo(int) /* java::values.Choice.oneOrTwo:(I)I */\n        // 2 file values/Choice.java line 17 function java::values.Choice.oneOrTwo:(I)I bytecode-index 30\n     2: CALL java::java.util.List.size:()I(java::values.Choice.oneOrTwo:(I)I::33::l)\n\n^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\njava.util.List.size() /* java::java.util.List.size:()I */\n        // 3 no location\n        SKIP\n\n^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"
    );
    std::fs::write(dir.join("goto.txt"), program).unwrap();
    // JBMC's refutation of the harness's assertion with n=1, as `--json-ui` and as text.
    let bits = format!("{:032b}", 1u32);
    let trace = format!("{{\"stepType\": \"input\", \"inputID\": \"arg0i\", \"values\": [{{\"binary\": \"{bits}\", \"data\": \"1\", \"name\": \"integer\", \"type\": \"int\", \"width\": 32}}]}}");
    let mut results = vec![format!("{{\"property\": \"java::{harness}.check:(I)V.assertion.1\", \"status\": \"FAILURE\", \"trace\": [{trace}]}}")];
    results.extend((2..=5).map(|n| format!("{{\"property\": \"java::{harness}.check:(I)V.assertion.{n}\", \"status\": \"SUCCESS\"}}")));
    let json = format!(
        "[\n  {{\n    \"program\": \"JBMC 6.11.0 (cbmc-6.11.0)\"\n  }},\n  {{\n    \"messageText\": \"JBMC version 6.11.0 (cbmc-6.11.0) 64-bit\",\n    \"messageType\": \"STATUS-MESSAGE\"\n  }},\n  {{\n    \"result\": [{}]\n  }},\n  {{\n    \"cProverStatus\": \"failure\"\n  }}\n]\n",
        results.join(", ")
    );
    std::fs::write(dir.join("answer.json"), json).unwrap();
    std::fs::write(dir.join("answer.txt"), format!("JBMC version 6.11.0 (cbmc-6.11.0)\n[{harness}.check:(I)V.assertion.1] line 1 assertion at file {harness}.java line 1 function java::{harness}.check:(I)V bytecode-index 9: FAILURE\n  INPUT arg0a: 1\n** 1 of 5 failed (2 iterations)\nVERIFICATION FAILED\n")).unwrap();

    let mut options = jvmcontract::property::Options::new(&[classes.to_path_buf()], "values.Choice#oneOrTwo");
    options.assume = Some("n >= 1 && n <= 2".into());
    options.assert = Some("result == n".into());
    options.engine = jvmcontract::Engine::Auto;
    options.confirm = true;
    options.jbmc = jbmc.display().to_string();
    options.work = Some(dir.join("work"));
    let outcome = jvmcontract::property::run(&options).unwrap();
    let confirmation = outcome.search.as_ref().and_then(|s| s.confirmation.as_ref()).expect("a confirmation");
    assert!(!outcome.output.contains("the engines disagree"), "a stub's value is no refutation: {}", outcome.output);
    assert_eq!(confirmation.status, jvmcontract::equivalence::Confirmed::NoVerdict, "{}", outcome.output);
    assert_eq!(outcome.verdict, Verdict::Verified, "the own checker's proof stands, not confirmed: {}", outcome.output);
    assert!(outcome.output.contains("  not confirmed: JBMC 6.11.0 gave no verdict") && outcome.output.contains("java.util.List.size()"), "{}", outcome.output);
}
