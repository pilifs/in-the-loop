//! Countermodels of an effect contract at a call (the state stream's `vwktulky`, 2026-11-17): a setter's checked
//! write set stands in for its calls by the writes it states. Each contract here is proved, and each caller calls
//! its setter where the call does what the contract does not say: in a class initialized from a setting the caller
//! changed first, on one object passed twice, or with an argument of a subclass. The fixtures are
//! `tests/fixtures/effect-countermodels/ec`, and this test holds them to what a JVM says. The checker's side, the
//! proofs it should not make, is in the fixtures' README for the stream that owns the effect contract
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
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/effect-countermodels/ec");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("effect-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let files = ["Uses.java", "Pair.java", "Peer.java", "Rogue.java"].map(|f| sources.join(f));
        let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out).args(files).status().expect("javac runs");
        assert!(status.success(), "the fixtures compile");
        Some(out)
    })
    .as_deref()
}

/// Each caller sees on a JVM what its setter's contract says it cannot: a level the setter did not take, the
/// argument's level where the receiver's was written last, an admin made by linking.
#[test]
fn each_call_an_effect_contract_stands_in_for_does_what_it_does_not_say_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let out = Command::new("java").arg("-cp").arg(classes).arg("ec.Uses").output().expect("java runs");
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert_eq!(String::from_utf8_lossy(&out.stdout).trim(), "locked=0 paired=1 linked.admin=true failed.admin=true");
}
