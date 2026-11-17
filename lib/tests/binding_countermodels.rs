//! Countermodels of an observed initializer's binding past its fixes (the evidence stream's `lzpqszyo`, and the state
//! stream's `llyzwmyp`, which names a lambda's hidden class by what it was defined from; 2026-11-17): what an
//! initializer writes that the comparison of the classes it initialized does not hold (a lambda of another class, an
//! object another class holds) or that is not a class of the class path at all (the JDK's default locale). The
//! fixture is `tests/fixtures/binding-countermodels/bc`, and this test holds it to what a JVM says. The checker's side,
//! the proofs it should not make, is in the fixture's README, for the streams that own the binding
//! (domain-advances-evidence, domain-advances-state).

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
        let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/binding-countermodels/bc");
        let mut sources: Vec<PathBuf> = std::fs::read_dir(&dir).unwrap().map(|e| e.unwrap().path()).filter(|p| p.extension().is_some_and(|e| e == "java")).collect();
        sources.sort();
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("binding-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let status = Command::new("javac").args(["-g", "-proc:none", "-nowarn", "--release", "21", "-d"]).arg(&out).args(&sources).status().expect("javac runs");
        assert!(status.success(), "the fixture compiles");
        Some(out)
    })
    .as_deref()
}

/// Each initializer leaves what the check, given its observation, does not: Hooks' lambda replaced by another of
/// Hooks' own, the Box Boxes holds written, and the default locale Turkish.
#[test]
fn each_initializer_leaves_a_state_beside_its_own_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let out = Command::new("java").env_remove("JAVA_TOOL_OPTIONS").arg("-cp").arg(classes).arg("bc.M").output().expect("java runs");
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert_eq!(String::from_utf8_lossy(&out.stdout).trim(), "rehooked=5 boxed=5 relocaled=305");
}
