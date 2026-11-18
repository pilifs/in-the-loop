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

fn has(tool: &str) -> bool {
    Command::new(tool).arg("-version").output().is_ok()
}

/// On a JVM each message is the JDK's, not none: `listed` 2, `listedText` the 53 units of
/// "java.lang.IndexOutOfBoundsException: Index: 2 Size: 1", `sized` 2, `sizedLocalized` the 28 units of
/// "Illegal initial capacity: -1".
#[test]
fn each_jdk_message_is_there_on_a_jvm() {
    jvmcontract::tool_tier!();
    if !has("javac") || !has("java") {
        return;
    }
    let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/throwable-countermodels/tm");
    let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("throwable-countermodels-classes");
    let _ = std::fs::remove_dir_all(&out);
    let mut files: Vec<PathBuf> = std::fs::read_dir(&sources).unwrap().map(|e| e.unwrap().path()).collect();
    files.sort();
    let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "--release", "21", "-d"]).arg(&out).args(&files).status().expect("javac runs");
    assert!(status.success(), "the fixture compiles");
    let run = Command::new("java").env_remove("JAVA_TOOL_OPTIONS").arg("-cp").arg(&out).arg("tm.Thrown").output().expect("java runs");
    assert!(run.status.success(), "{}", String::from_utf8_lossy(&run.stderr));
    assert_eq!(String::from_utf8_lossy(&run.stdout).trim(), "listed=2 listedText=53 sized=2 sizedLocalized=28");
}
