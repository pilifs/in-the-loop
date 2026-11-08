//! The values stream's model conformance tests (`llm-dlc/loops/application-core-values.md`): small Java methods over
//! Strings, run on a real JVM and in the interpreter, which must give the same outcome, a String's code units
//! included. The JVM is the semantic reference. A case the interpreter refuses (`Fault::Unsupported`) passes only
//! where it is listed as refusable, and is never a different answer: sampled conformance is evidence of the level
//! `tested`, not a proof of the model.

use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::OnceLock;

use jvmcontract::classfile::{MethodDescriptor, Type};
use jvmcontract::classpath::ClassPath;
use jvmcontract::interp::{Fault, Machine, Value};

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
    let input: String = cases.iter().map(|c| format!("{} {} {}\n", c.class, c.method, c.args.iter().map(|a| a.to_string()).collect::<Vec<_>>().join(" "))).collect();
    let mut child = Command::new("java").arg("-cp").arg(classes).arg("ValuesRunner").stdin(Stdio::piped()).stdout(Stdio::piped()).spawn().expect("java runs");
    use std::io::Write as _;
    child.stdin.take().unwrap().write_all(input.as_bytes()).unwrap();
    let out = child.wait_with_output().unwrap();
    assert!(out.status.success(), "the runner runs every case");
    let lines: Vec<String> = String::from_utf8(out.stdout).unwrap().lines().map(str::to_string).collect();
    assert_eq!(lines.len(), cases.len());
    lines
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
