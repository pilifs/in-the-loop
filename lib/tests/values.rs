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
use jvmcontract::interp::{Fault, JStr, Machine, Value};
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

/// The witness's arguments, in parameter order.
fn witness(out: &Outcome, params: &[Type]) -> Vec<Arg> {
    let mut args = Vec::new();
    let mut index_of = std::collections::BTreeMap::new();
    for (slot, t) in params.iter().enumerate() {
        let slot = slot as u32;
        index_of.insert(slot, args.len());
        args.push(match t {
            Type::Object(_) => match (out.raw_same.get(&slot), out.raw_arrays.get(&slot)) {
                (Some(first), _) => Arg::Same(index_of[first]),
                (None, Some(None)) => Arg::Null,
                (None, Some(Some(units))) => Arg::Str(units.iter().map(|u| u.parse().expect("a code unit")).collect()),
                (None, None) => panic!("no witness for the String in slot {slot}"),
            },
            _ => Arg::Number(out.raw_inputs.get(&slot).map(|v| v.parse().unwrap()).unwrap_or(0)),
        });
    }
    args
}

/// What the witness does on the JVM and in the interpreter, in the runner's form.
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
            Arg::Str(units) => m.new_string(JStr::from_units(units.clone())),
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
        let args = witness(&out, &params);
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
