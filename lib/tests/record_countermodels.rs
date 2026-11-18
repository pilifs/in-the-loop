//! Countermodels of a call's record, the preservation stream's call-level rule as `mwvyxxyr` (2026-11-18) leaves it
//! (`lib/src/bmc/ties.rs`, `collect` and `renumber` in `lib/src/bmc/mod.rs`). A call taken as one function of both
//! versions is recorded with its result by the object's number, and a later call of the same code on equal inputs
//! takes the cells that object holds when the later call is made. `stale`: the caller writes into the first call's
//! array before the second call, and the second takes what the caller wrote. `swapped`: two paths number the first
//! call's array differently, and a merge of the two keeps one path's number. The fixtures are
//! `tests/fixtures/record-countermodels` (`old/` and `new/`, whose `Shared` is the same bytes in both); each
//! version's `main` runs both methods alone, and this test holds the fixtures to what a JVM says. The checker's side,
//! the proof it should not make, is in the fixtures' README for the stream that owns the rule
//! (domain-advances-preservation).

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

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
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/record-countermodels");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("record-countermodels-classes");
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

/// Each version alone: the previous version's second call of `Shared.make(k)` gives a new array holding k, whatever
/// the caller did to the first one's, and the new version gives what the checker takes the previous one to give.
#[test]
fn each_version_alone_differs_past_the_second_call_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let shared = |version: &Path| std::fs::read(version.join("app/Shared.class")).expect("Shared compiled");
    assert_eq!(shared(old), shared(new), "Shared is the same bytes in both versions");
    let alone = |version: &Path| {
        let out = Command::new("java").env_remove("JAVA_TOOL_OPTIONS").arg("-cp").arg(version).arg("app.Entry").output().expect("java runs");
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).trim().to_string()
    };
    assert_eq!(alone(old), "stale=0 swapped=3");
    assert_eq!(alone(new), "stale=99 swapped=2");
}
