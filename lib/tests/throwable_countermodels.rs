//! Countermodels of an exception's message kept from the constructor the engine saw run (the state stream's
//! `vwrmzmst`, `lib/src/bmc/throwables.rs`, 2026-11-17). A JDK exception's `getMessage()`, `getLocalizedMessage()`
//! and `toString()` are modelled where the engine ran the constructor that set the message. That includes an
//! exception a model of the engine's makes (`lib/models`), and a model's message is not always the JDK's:
//! `ImmutableCollections.List12.get` throws `new IndexOutOfBoundsException()` where the JDK's has "Index: 2 Size: 1",
//! and `HashMap(int)` throws `new IllegalArgumentException()` where the JDK's has "Illegal initial capacity: -1". The
//! fixtures are `tests/fixtures/throwable-countermodels`; this test holds them to what a JVM says. The checker's side,
//! the proofs it should not make, is in the fixtures' README for the stream that owns the rule (domain-advances-state).

use std::path::PathBuf;
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::{property, Engine, Verdict};

fn has(tool: &str) -> bool {
    Command::new(tool).arg("-version").output().is_ok()
}

fn classes() -> Option<&'static PathBuf> {
    static CLASSES: OnceLock<Option<PathBuf>> = OnceLock::new();
    CLASSES.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let source = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/throwable-countermodels/tm/Thrown.java");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("throwable-countermodels-classes");
        let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "--release", "21", "-d"]).arg(&out).arg(source).status().unwrap();
        assert!(status.success());
        Some(out)
    }).as_ref()
}

/// On a JVM each message is the JDK's, not none: `listed` 2, `listedText` the 53 units of
/// "java.lang.IndexOutOfBoundsException: Index: 2 Size: 1", `sized` 2, `sizedLocalized` the 28 units of
/// "Illegal initial capacity: -1".
#[test]
fn each_jdk_message_is_there_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some(out) = classes() else { return };
    let run = Command::new("java").env_remove("JAVA_TOOL_OPTIONS").arg("-cp").arg(out).arg("tm.Thrown").output().expect("java runs");
    assert!(run.status.success(), "{}", String::from_utf8_lossy(&run.stderr));
    assert_eq!(String::from_utf8_lossy(&run.stdout).trim(), "listed=2 listedText=53 sized=2 sizedLocalized=28");
}

#[test]
fn modeled_exception_details_do_not_establish_the_four_jdk_countermodels() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    for (name, assume, assertion) in [
        ("listed", "k >= 1 && k < 3", "result != 2"),
        ("listedText", "k == 2", "result == 35"),
        ("sized", "k < 0", "result != 2"),
        ("sizedLocalized", "k == -1", "result == -1"),
    ] {
        let mut options = property::Options::new(std::slice::from_ref(classes), &format!("tm.Thrown#{name}"));
        options.engine = Engine::Native;
        options.jbmc = "/nonexistent/jbmc".into();
        options.assume = Some(assume.into());
        options.assert = Some(assertion.into());
        let outcome = property::run(&options).unwrap();
        assert_eq!(outcome.verdict, Verdict::Unverifiable, "{name}: {}", outcome.output);
        assert!(outcome.problem.as_deref().is_some_and(|p| p.contains("exception details supplied by a JDK model")), "{name}: {}", outcome.output);
    }
}
