//! Countermodels of three rules the other streams of domain-advances added on 2026-11-17, each a false proof on the
//! line that added it, built apart (the challenge stream, item 5):
//! - `wd`: under `--gaps assume` a JDK call that returns an object is taken to return one of exactly its declared
//!   class, so `HashSet.clone()` and `Date.clone()`, declared to return `Object`, return no `HashSet` and no `Date`
//!   (the state stream's gap refusal, `qysmsruu`, which keys on the declared class).
//! - `ob`: an observed class initializer bound to what it was observed on (the evidence stream, `lzpqszyo`) leaves out
//!   a write to a supertype's static or to a superinterface's array, a property read through the `Properties` map,
//!   and the settings the JDK reads for itself (the default time zone) or that no property holds (the environment).
//! - `lg`: a line logged at WARNING (the preservation stream, `unswkkxp`) is taken to do nothing a check observes for
//!   a record "confined to itself", but the default handler calls the record's getters, which write the record the
//!   caller holds, or throw a `Throwable` the handler does not catch.
//! The fixtures are `tests/fixtures/rule-countermodels`, and this test holds them to what a JVM says. The checker's
//! side, the proofs it should not make, is in the fixtures' README, one test for each stream that owns a rule.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

fn has(tool: &str) -> bool {
    Command::new(tool).arg("-version").output().is_ok()
}

fn walk(dir: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    for entry in std::fs::read_dir(dir).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            out.extend(walk(&path));
        } else if path.extension().is_some_and(|e| e == "java") {
            out.push(path);
        }
    }
    out.sort();
    out
}

/// The fixtures, compiled into one folder: `None` without a JDK.
fn classes() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/rule-countermodels");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("rule-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "--release", "21", "-d"]).arg(&out).args(walk(&sources)).status().expect("javac runs");
        assert!(status.success(), "the fixtures compile");
        Some(out)
    })
    .as_deref()
}

/// What one class's `main` prints on a JVM in UTC with neither `ob.value` nor `OB_VALUE` set.
fn jvm(class: &str, args: &[&str]) -> String {
    let classes = classes().expect("a JDK");
    let out = Command::new("java").env_remove("OB_VALUE").env_remove("JAVA_TOOL_OPTIONS").arg("-Duser.timezone=UTC").arg("-cp").arg(classes).arg(class).args(args).output().expect("java runs");
    assert!(out.status.success(), "{class} {args:?}: {}", String::from_utf8_lossy(&out.stderr));
    String::from_utf8_lossy(&out.stdout).trim().to_string()
}

/// Each entry point is what a JVM says it is: a JDK clone is of its receiver's class, an initializer's writes outside
/// its class stand, a setting read is the run's, and the default handler calls a record's getters.
#[test]
fn each_fixture_is_what_a_jvm_says_it_is() {
    jvmcontract::tool_tier!();
    if classes().is_none() {
        return;
    }
    assert_eq!(jvm("wd.Widened", &[]), "setCloned=1 setClonedSize=1 dateCloned=1");
    for (entry, said) in [("inherited", 1), ("filled", 5), ("bypassed", 6), ("zoned", 0), ("environ", 6)] {
        assert_eq!(jvm("ob.M", &[entry]), format!("{entry}={said}"));
    }
    // The setting each was observed under gives another value.
    let classes = classes().unwrap();
    let set = |settings: &[&str], env: Option<(&str, &str)>, entry: &str| {
        let mut c = Command::new("java");
        c.env_remove("OB_VALUE").env_remove("JAVA_TOOL_OPTIONS").args(settings).arg("-cp").arg(classes).args(["ob.M", entry]);
        if let Some((k, v)) = env {
            c.env(k, v);
        }
        String::from_utf8_lossy(&c.output().unwrap().stdout).trim().to_string()
    };
    assert_eq!(set(&["-Dob.value=xyz"], None, "bypassed"), "bypassed=3");
    assert_eq!(set(&["-Duser.timezone=Asia/Tokyo"], None, "zoned"), "zoned=9");
    assert_eq!(set(&[], Some(("OB_VALUE", "xyz")), "environ"), "environ=3");
    // The handler writes the record to System.err; what is returned is on System.out.
    assert_eq!(jvm("lg.M", &[]), "seen=1 escaped=0");
}

/// The checker's side, for the preservation stream (`unswkkxp`): no proof that logging a record left it as it was, or
/// returned, where the default handler's formatting called a getter that wrote the record or threw a `Throwable`.
/// A JVM gives seen() 1 and escaped() 0 (the test above).
#[test]
fn logging_a_record_is_not_taken_to_skip_what_its_formatting_runs() {
    jvmcontract::tool_tier!();
    use jvmcontract::{property, Engine, Verdict};
    let Some(classes) = classes() else { return };
    let mut wrong = Vec::new();
    for (method, assertion) in [("seen", "result == 0"), ("escaped", "result == 1")] {
        let mut o = property::Options::new(&[classes.to_path_buf()], &format!("lg.M#{method}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assert = Some(assertion.into());
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("rule-countermodels").join(method));
        let out = property::run(&o).unwrap();
        eprintln!("--- {method}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(method);
        }
    }
    assert!(wrong.is_empty(), "proved that the default handler ran none of a record's getters, which a JVM runs: {wrong:?}");
}
