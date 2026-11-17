//! Countermodels of an effect contract past its fix (the state stream's `nslmqyry`, 2026-11-17): a contract's proof
//! makes its receiver and arguments with their constructors in the harness's fresh state, and reads their final
//! fields freely, but a caller's objects were made in the caller's state. The fixture is
//! `tests/fixtures/contract-countermodels/cc`, and this test holds it to what a JVM says. The checker's side, the
//! proofs it should not make, is in the fixture's README, for the stream that owns the effect contract
//! (domain-advances-state).

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
        let source = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/contract-countermodels/cc/Held.java");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("contract-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "--release", "21", "-d"]).arg(&out).arg(source).status().expect("javac runs");
        assert!(status.success(), "the fixture compiles");
        Some(out)
    })
    .as_deref()
}

/// Each setter, called on an object made while the setting was on, does not take the level: its final field holds
/// what its constructor made of that setting, or of the constructor the caller chose.
#[test]
fn each_setter_on_an_object_made_in_another_state_keeps_the_level_out_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let out = Command::new("java").env_remove("JAVA_TOOL_OPTIONS").arg("-cp").arg(classes).arg("cc.Held").output().expect("java runs");
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert_eq!(String::from_utf8_lossy(&out.stdout).trim(), "snapshot=0 chosen=0 scaled=0");
}
