//! Countermodels of a stand-in sampled on a JVM (`prove --stand-in`, the state stream's `qlylowvo`, 2026-11-17)
//! where a check rests on it through a lemma. A lemma's proof is a check of its own, given the check's options, the
//! stand-ins included; the check that uses the lemma states the lemma as proved and states only what its own run
//! rested on. So where the lemma's proof made the stand-in's call and the check's own path did not, the check's result
//! does not say it rests on anything sampled. The fixture is `tests/fixtures/stand-in-countermodels`: a reflective
//! property writer, a stand-in whose sampler is honest but narrow (four names, never "Age"), a lemma about a method
//! that makes the call, and a method that uses it. This test holds the fixture to what a JVM says; the checker's
//! side, the result it should not give without the stand-in in it, is in the fixture's README for the stream that
//! owns the rule (domain-advances-state).

use std::path::PathBuf;
use std::process::Command;

fn has(tool: &str) -> bool {
    Command::new(tool).arg("-version").output().is_ok()
}

/// On "Age" the method writes age, so the lemma's `result == 0` is false on a JVM, and so is the check through it;
/// the stand-in's own sampler finds the four samples it tries the same.
#[test]
fn the_lemma_and_the_check_through_it_are_false_on_a_jvm_and_the_samples_agree() {
    jvmcontract::tool_tier!();
    if !has("javac") || !has("java") {
        return;
    }
    let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/stand-in-countermodels/sn");
    let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("stand-in-countermodels-classes");
    let _ = std::fs::remove_dir_all(&out);
    let mut files: Vec<PathBuf> = std::fs::read_dir(&sources).unwrap().map(|e| e.unwrap().path()).collect();
    files.sort();
    let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "--release", "21", "-d"]).arg(&out).args(&files).status().expect("javac runs");
    assert!(status.success(), "the fixture compiles");
    let run = |class: &str| {
        let o = Command::new("java").env_remove("JAVA_TOOL_OPTIONS").arg("-cp").arg(&out).arg(class).output().expect("java runs");
        assert!(o.status.success(), "{}", String::from_utf8_lossy(&o.stderr));
        String::from_utf8_lossy(&o.stdout).trim().to_string()
    };
    assert_eq!(run("sn.Use"), "ageAfter=32 viaLemma=32");
    let samples = run("sn.NarrowStandIn");
    let lines: Vec<&str> = samples.lines().collect();
    assert_eq!(lines.len(), 4, "{samples}");
    for line in lines {
        let parts: Vec<&str> = line.split('\t').collect();
        assert_eq!(parts.len(), 4, "{line}");
        assert_eq!(parts[2], parts[3], "{line}");
    }
}
