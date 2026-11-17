//! Countermodels of the pair of versions past the preservation stream's fix (`jvmcontract::pairing` at `wokytpkz`,
//! 2026-11-17: the scope is read on copies of its own, and an exception is compared by its class's name and the names
//! of every class above it up to `Object`). Two versions of a method that a caller's handler tells apart when each
//! runs alone on a JVM, through what the comparison leaves out of an exception: an interface its class implements, its
//! message, and a field of its own. The fixtures are `tests/fixtures/thrown-pair-countermodels` (`old/` and `new/`);
//! each version's `main` runs one method alone, and this test holds the fixtures to what a JVM says. The checker's
//! side, the proofs it should not make, is in the fixtures' README for the stream that changes the pairing
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
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/thrown-pair-countermodels");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("thrown-pair-countermodels-classes");
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

/// What each version's caller makes of each method at 1, each in a JVM of its own: a failure it may retry against
/// one that escapes, two messages, two status codes, a cause of two classes, and a failure whose superclass's
/// superclass changed.
#[test]
fn each_handler_tells_the_versions_apart_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let alone = |version: &Path| {
        ["marked", "messaged", "coded", "wrapped", "based"]
            .iter()
            .map(|m| {
                let out = Command::new("java").arg("-cp").arg(version).args(["app.Entry", m]).output().expect("java runs");
                assert!(out.status.success(), "{m}: {}", String::from_utf8_lossy(&out.stderr));
                String::from_utf8_lossy(&out.stdout).trim().to_string()
            })
            .collect::<Vec<_>>()
            .join(" | ")
    };
    assert_eq!(alone(old), "marked=retried | messaged=argument negative | coded=code 403 | wrapped=argument inside | based=argument bad");
    assert_eq!(alone(new), "marked=escaped app.Marked | messaged=argument too long | coded=code 404 | wrapped=escaped java.lang.RuntimeException | based=escaped app.Based");
}
