//! Countermodels of a call taken as one function of both versions, past the preservation stream's fix for I023
//! (`puuwrruu`, 2026-11-18): `shared::one_function` now refuses an array whose length the inputs give and checks at
//! the call that each array the code makes is at most 65536 long, so that an `OutOfMemoryError` is not among a call's
//! outcomes. `kept`: each array is of a constant length, 16384, but a loop the inputs bound keeps them all, 32 TiB once
//! k >= 1, which no heap holds. `around` is the control: a recursion through an override, which the reach refuses as
//! overridable code. The fixtures are `tests/fixtures/allocation-countermodels` (`old/` and `new/`, whose `Shared`,
//! `Node` and `Deep` are the same bytes in both); each version's `main` runs both methods alone, and this test holds the
//! fixtures to what a JVM says. The checker's side, the proof it should not make, is in the fixtures' README for the
//! stream that owns the rule (domain-advances-preservation).

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::{equivalence, Engine, Verdict};

fn has(tool: &str) -> bool {
    Command::new(tool).arg("-version").output().is_ok()
}

/// The previous version and the new one, compiled: `None` without a JDK.
fn classes() -> Option<&'static (PathBuf, PathBuf)> {
    static OUT: OnceLock<Option<(PathBuf, PathBuf)>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/allocation-countermodels");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("allocation-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let javac = |dir: &str| {
            let mut files: Vec<PathBuf> = std::fs::read_dir(sources.join(dir).join("app")).unwrap().map(|e| e.unwrap().path()).collect();
            files.sort();
            let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "--release", "21", "-d"]).arg(out.join(dir)).args(&files).status().expect("javac runs");
            assert!(status.success(), "{dir} compiles");
            out.join(dir)
        };
        Some((javac("old"), javac("new")))
    })
    .as_ref()
}

/// Each version alone: the shared code raises an Error on the inputs `main` gives, and the two versions answer it
/// differently. The heap is capped at 64 MiB so the test stays small; `kept` asks for 32 TiB, past any heap.
#[test]
fn each_version_alone_answers_the_shared_codes_error_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    for class in ["Shared", "Node", "Deep"] {
        let read = |version: &Path| std::fs::read(version.join(format!("app/{class}.class"))).expect("compiled");
        assert_eq!(read(old), read(new), "{class} is the same bytes in both versions");
    }
    let alone = |version: &Path| {
        let out = Command::new("java").env_remove("JAVA_TOOL_OPTIONS").args(["-Xmx64m", "-cp"]).arg(version).arg("app.Entry").output().expect("java runs");
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).trim().to_string()
    };
    assert_eq!(alone(old), "kept=-1 around=-1");
    assert_eq!(alone(new), "kept=-2 around=-2");
}

/// The checker's side: each version alone answers the Error differently (the test above), so a proof that they
/// agree is false. `shared::one_function` refuses code that can keep what a loop makes (here an array of
/// references), so `kept` runs as written.
#[test]
fn a_calls_outcome_holds_the_memory_its_code_keeps() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let mut wrong = Vec::new();
    for name in ["kept", "around"] {
        let mut o = equivalence::Options::new(old, new, &format!("app.Entry#{name}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assume = Some("k >= 0".into());
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("allocation-countermodels").join(name));
        let out = equivalence::run(&o).unwrap();
        eprintln!("--- {name}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(name);
        }
    }
    assert!(wrong.is_empty(), "proved to agree, though each version alone tells them apart: {wrong:?}");
}
