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

use jvmcontract::{property, Engine, Verdict};

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

/// The checker's side: no caller's property proved through a contract where a JVM breaks it (the test above).
#[test]
fn an_effect_contract_does_not_prove_a_call_a_jvm_breaks() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("effect-countermodels");
    let _ = std::fs::create_dir_all(&dir);
    let mut wrong = Vec::new();
    for (caller, assertion, contract) in [
        ("lockedLevel", "result == level", "ec.Uses$Locked#setLevel\n  writes: this.level\n  assert: this.level == level\n"),
        ("pairedLevel", "result == theirs", "ec.Pair#setBoth\n  writes: this.level, other.level\n  assert: this.level == mine && other.level == theirs\n"),
        ("linkedAdmin", "!result", "ec.Uses$Linking#link\n  writes: this.links\n  assert: this.links == links\n"),
    ] {
        let file = dir.join(format!("{caller}.contract"));
        std::fs::write(&file, contract).unwrap();
        let mut o = property::Options::new(&[classes.to_path_buf()], &format!("ec.Uses#{caller}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assert = Some(assertion.into());
        o.lemmas = Some(file);
        o.work = Some(dir.join(caller));
        let out = property::run(&o).unwrap();
        eprintln!("--- {caller}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(caller);
        }
    }
    assert!(wrong.is_empty(), "a call proved through an effect contract where a JVM breaks the property: {wrong:?}");
}

/// The challenge stream's stub countermodels (`tests/fixtures/stub-countermodels/sc`, `uqrzluvx`), compiled: `None`
/// without a JDK.
fn stub_classes() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/stub-countermodels/sc");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("effect-countermodels-stub-classes");
        let _ = std::fs::remove_dir_all(&out);
        let files = ["Bean.java", "Store.java", "Touch.java", "M.java"].map(|f| sources.join(f));
        let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out).args(files).status().expect("javac runs");
        assert!(status.success(), "the fixtures compile");
        Some(out)
    })
    .as_deref()
}

/// An effect contract's stub inside a proof by induction or under a write set: each write it makes passes the gate
/// the method's own write would meet (`Engine::keeps`), so neither is proved and each is refused for that write. On a
/// JVM f(2) is -1 and touch(5) sets HELD.level (tests/stub_countermodels.rs). The fixture's README's test, with the
/// refusal also required to name the write.
#[test]
fn an_effect_contracts_writes_meet_the_induction_and_the_write_set() {
    jvmcontract::tool_tier!();
    let Some(classes) = stub_classes() else { return };
    let contract = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/stub-countermodels/set-level.contract");
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("effect-countermodels-stub");
    for (entry, assertion, decreases, writes, refusal) in [
        ("sc.Store#f", "result == 0", Some("k"), None, "sc.Store.f writes a field of an object made before it was called, and the induction hypothesis states the result of its calls of itself only"),
        ("sc.Touch#touch", "result == v", None, Some(Vec::new()), "sc.Touch.touch writes a field of an object made before it was called and none of its inputs, outside its write set"),
    ] {
        let mut o = property::Options::new(&[classes.to_path_buf()], entry);
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assert = Some(assertion.into());
        o.decreases = decreases.map(String::from);
        o.writes = writes;
        o.lemmas = Some(contract.clone());
        o.work = Some(dir.join(entry.replace('#', "-")));
        let out = property::run(&o).unwrap();
        assert_ne!(out.verdict, Verdict::Verified, "{entry}: proved where a JVM says otherwise\n{}", out.output);
        assert!(out.output.contains("effect: ✓ sc.Bean#setLevel"), "{entry}: the contract was not proved, so no stub stood in for the call\n{}", out.output);
        assert!(out.output.contains(refusal), "{entry}: not refused for the stub's write\n{}", out.output);
    }
}
