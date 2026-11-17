//! Countermodels of the code two versions are taken to share, past the preservation stream's `qopxypnn`
//! (2026-11-17), its fix for `domain-advances-preservation-I019`: `shared::reach` now walks both versions, resolves
//! each field to the class that declares it and takes in the initializers the JVM runs. What it still leaves out is a
//! class's supertypes. A static method inherited from a superclass the new version changed, an interface the previous
//! version's class implements and the new one does not (`instanceof`, `checkcast`), and a default method taken from
//! another interface: in each, every method of every class is the same text in both versions, and only a class header
//! differs. The fixtures are `tests/fixtures/supertype-countermodels` (`old/` and `new/`); each version's `main` runs
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
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/supertype-countermodels");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("supertype-countermodels-classes");
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

/// Each version alone, at an input past 1000: the supertypes decide what each method returns (-1 is the cast's
/// ClassCastException).
#[test]
fn each_version_alone_differs_by_a_supertype_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let alone = |version: &Path| {
        let out = Command::new("java").env_remove("JAVA_TOOL_OPTIONS").arg("-cp").arg(version).arg("app.Entry").output().expect("java runs");
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).trim().to_string()
    };
    assert_eq!(alone(old), "rebased=2 marked=2 cast=2 mixed=2 looped=2");
    assert_eq!(alone(new), "rebased=1 marked=1 cast=-1 mixed=1 looped=1");
}
