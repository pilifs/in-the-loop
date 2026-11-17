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

/// The checker's side: a caller's handler tells each pair of versions apart when each runs alone (the test above), so
/// a proof that they agree is false, but for what the pair states it does not compare. `marked` (an interface) and
/// `based` (a superclass's superclass) are what `catch`, `instanceof` and a cast see of an exception's class, and are
/// compared. `wrapped` (the cause) stops at a gap. `messaged` (the message) and `coded` (an own field) are outside
/// the pair's reading of "the same exception", one class: the brief's claims of 287 and 307 mean that reading, since
/// a JVM's message for the `NullPointerException` it raises names the method the null met, and 307's two versions
/// call `getBytes` with two different descriptors. So those two may be proved, and then the outcome's note says what
/// was not compared.
#[test]
fn the_pair_does_not_prove_two_versions_agree_whose_exceptions_a_handler_tells_apart() {
    jvmcontract::tool_tier!();
    use jvmcontract::{equivalence, Engine, Verdict};
    let Some((old, new)) = classes() else { return };
    let mut wrong = Vec::new();
    for name in ["marked", "messaged", "coded", "wrapped", "based"] {
        let mut o = equivalence::Options::new(old, new, &format!("app.Entry#{name}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assume = Some("k >= 0 && k < 4".into());
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("thrown-pair-countermodels").join(name));
        let out = equivalence::run(&o).unwrap();
        eprintln!("--- {name}: {:?}\n{}", out.verdict, out.output);
        let stated = out.output.contains("an exception's message, cause and own fields are not compared");
        if out.verdict == Verdict::Verified && !(matches!(name, "messaged" | "coded") && stated) {
            wrong.push(name);
        }
    }
    assert!(wrong.is_empty(), "proved to agree, though a caller's handler tells the versions apart by what the pair compares or without saying what it does not: {wrong:?}");
}
