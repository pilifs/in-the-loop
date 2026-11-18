//! Countermodels of the code two versions are taken to share, past the preservation stream's `kskmpmny`
//! (2026-11-17), which closed the reach of `jvmcontract::shared` against calls back through the JDK and took in the
//! initializers of the application classes the code uses. What the reach still leaves out: an override the previous
//! version declared and the new one removed (only the new version's reach is walked, and the old one is looked up by
//! the new one's declaring class), a field the previous version declared that hides an inherited one (fields are not
//! compared), an interface's initializer run by a read through a class that implements it or by making an object of
//! a class that implements one with a default method (only superclasses are taken in), and the target's own class's
//! initializer. The fixtures are `tests/fixtures/reach-countermodels` (`old/` and `new/`); each version's `main` runs
//! every method alone, and this test holds the fixtures to what a JVM says. The checker's side, the proofs it should
//! not make, is in the fixtures' README for the stream that changes the pairing (domain-advances-preservation).

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
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/reach-countermodels");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("reach-countermodels-classes");
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

/// Each version alone, at an input past 1000: what the reach leaves out is what each method returns.
#[test]
fn each_version_alone_differs_where_the_reach_does_not_look_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let alone = |version: &Path| {
        let out = Command::new("java").env_remove("JAVA_TOOL_OPTIONS").arg("-cp").arg(version).arg("app.Entry").output().expect("java runs");
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).trim().to_string()
    };
    assert_eq!(alone(old), "removed=2 constant=2 defaulted=2 hidden=0 own=2 looped=2");
    assert_eq!(alone(new), "removed=1 constant=1 defaulted=1 hidden=1 own=1 looped=1");
}
