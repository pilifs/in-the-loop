//! Countermodels of a write set (`prove --writes`, the state stream's first effect contract, `qrqtplwq`,
//! 2026-11-17). The frame is read after a normal return, of a call whose object inputs are distinct objects each made
//! by its constructor. A method that writes a protected field and then throws a declared exception, or one handed the
//! same object twice, leaves the field written on a JVM while the check proves it unchanged. The fixtures are
//! `tests/fixtures/frame-countermodels/fc`, and this test holds them to what a JVM says. The checker's side, the
//! proofs it should not make, is in the fixtures' README for the stream that owns the write set
//! (domain-advances-state).

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

fn has(tool: &str) -> bool {
    Command::new(tool).arg("-version").output().is_ok()
}

/// The fixtures, compiled: `None` without a JDK.
fn classes() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/frame-countermodels/fc");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("frame-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out).arg(sources.join("Framed.java")).status().expect("javac runs");
        assert!(status.success(), "the fixtures compile");
        Some(out)
    })
    .as_deref()
}

/// Each method leaves on a JVM the protected field written that its write set does not name.
#[test]
fn each_protected_field_a_frame_misses_is_written_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let out = Command::new("java").arg("-cp").arg(classes).arg("fc.Framed").output().expect("java runs");
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert_eq!(String::from_utf8_lossy(&out.stdout).trim(), "rename.threw=true rename.admin=true promote.this.admin=true grant.from.admin=true");
}
