//! Countermodels of what the pair of versions takes as the same code (2026-11-17): the reach of
//! `jvmcontract::shared` follows no call through a JDK interface or a JDK class's virtual method, so an application
//! class reached that way is not part of the code compared. Two checks rest on that reach: the shortcut that verifies
//! a target "identical in both versions" with nothing to prove (older than the run), and the preservation stream's
//! ties of `owrsowqm`, which give a loop summarized in both versions one set of bits where the code and state are
//! "the same". The fixtures are `tests/fixtures/tie-countermodels` (`old/` and `new/`); each version's `main` runs
//! the three methods alone, and this test holds the fixtures to what a JVM says. The checker's side, the proofs it
//! should not make, is in the fixtures' README for the stream that changes the pairing
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
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/tie-countermodels");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("tie-countermodels-classes");
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

/// Each version alone, at an input past 1000: the private helper and the initializer the versions change are what
/// each method returns.
#[test]
fn each_version_alone_differs_past_a_thousand_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let alone = |version: &Path| {
        let out = Command::new("java").env_remove("JAVA_TOOL_OPTIONS").arg("-cp").arg(version).arg("app.Entry").output().expect("java runs");
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).trim().to_string()
    };
    assert_eq!(alone(old), "supplied=2 summed=2 configured=2");
    assert_eq!(alone(new), "supplied=1 summed=1 configured=1");
}
