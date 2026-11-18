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

/// The checker's side, for the state stream (`nslmqyry`): no caller's property proved through an effect contract
/// that read a final field a constructor computed from a setting. A JVM gives 0 for each (the test above).
#[test]
fn an_effect_contract_reads_no_final_field_a_caller_made_in_another_state() {
    jvmcontract::tool_tier!();
    use jvmcontract::{property, Engine, Verdict};
    let Some(classes) = classes() else { return };
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("contract-countermodels");
    let _ = std::fs::create_dir_all(&dir);
    let mut wrong = Vec::new();
    for (caller, contract) in [
        ("snapshotLevel", "cc.Held$Snapshot#setLevel\n  writes: this.level\n  assert: this.level == level\n"),
        ("scaledLevel", "cc.Held$Scaled#setFrom\n  writes: this.level\n  assert: this.level == level\n"),
    ] {
        let file = dir.join(format!("{caller}.contract"));
        std::fs::write(&file, contract).unwrap();
        let mut o = property::Options::new(&[classes.to_path_buf()], &format!("cc.Held#{caller}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assert = Some("result == level".into());
        o.lemmas = Some(file);
        o.work = Some(dir.join(caller));
        let out = property::run(&o).unwrap();
        eprintln!("--- {caller}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(caller);
        }
        // The state stream's addition: the contract is refused for the read, by name.
        assert!(out.output.contains("reads the final field") && out.output.contains("the state a caller made it in"), "{caller}: the refusal names the final field read: {}", out.output);
    }
    assert!(wrong.is_empty(), "a call proved through an effect contract that read a caller's final field: {wrong:?}");
}
