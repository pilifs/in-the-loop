//! Countermodels of an effect contract's stub inside a proof that limits writes (2026-11-17): the stub's writes do
//! not meet `Engine::keeps`, which refuses the same write made by the method as written, inside a proof by induction
//! (`--decreases`) and under a write set (`--writes`). The fixture is `tests/fixtures/stub-countermodels/sc`, and this
//! test holds it to what a JVM says. The checker's side, the proofs it should not make, is in the fixture's README,
//! for the state stream, whose effect contracts these are (domain-advances-state).

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

fn has(tool: &str) -> bool {
    Command::new(tool).arg("-version").output().is_ok()
}

/// The fixture, compiled: `None` without a JDK.
fn classes() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/stub-countermodels/sc");
        let mut sources: Vec<PathBuf> = std::fs::read_dir(&dir).unwrap().map(|e| e.unwrap().path()).filter(|p| p.extension().is_some_and(|e| e == "java")).collect();
        sources.sort();
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("stub-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let status = Command::new("javac").args(["-g", "-proc:none", "-nowarn", "--release", "21", "-d"]).arg(&out).args(&sources).status().expect("javac runs");
        assert!(status.success(), "the fixture compiles");
        Some(out)
    })
    .as_deref()
}

/// f(2)'s call of itself sets the level the caller then reads, and touch writes the bean Touch holds: what the
/// hypothesis and the empty write set say does not happen.
#[test]
fn the_call_of_itself_and_the_framed_method_write_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let out = Command::new("java").env_remove("JAVA_TOOL_OPTIONS").arg("-cp").arg(classes).arg("sc.M").output().expect("java runs");
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert_eq!(String::from_utf8_lossy(&out.stdout).trim(), "f=-1 held=5");
}
