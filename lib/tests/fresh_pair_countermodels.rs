//! Countermodels of the pair of versions as the preservation stream changed it (`jvmcontract::pairing` at
//! `zmvkptqz`, 2026-11-17: each version starts from a fresh state, and an exception is compared by its class's
//! name). Two versions of a method that a caller tells apart when each runs alone on a JVM, and that the generated
//! `RegressionPair.agree` still finds agreeing: the scope reads the caller's own arrays before the pair copies them,
//! and two classes of one name are one answer whatever they extend. The fixtures are
//! `tests/fixtures/fresh-pair-countermodels` (`old/` and `new/`); each version's `main` runs one method alone, and
//! this test holds the fixtures to what a JVM says. The checker's side, the proofs it should not make, is the second
//! test, added with the fix (domain-advances-preservation, 2026-11-17): the scope reads copies of its own, and an
//! exception is compared by its class's name and those of the classes above it.

use jvmcontract::{equivalence, Engine, Verdict};
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
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/fresh-pair-countermodels");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("fresh-pair-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let javac = |dir: &str| {
            let mut files: Vec<PathBuf> = std::fs::read_dir(sources.join(dir).join("app")).unwrap().map(|e| e.unwrap().path()).collect();
            files.sort();
            let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(out.join(dir)).args(&files).status().expect("javac runs");
            assert!(status.success(), "{dir} compiles");
            out.join(dir)
        };
        Some((javac("old"), javac("new")))
    })
    .as_ref()
}

/// What each version's `main` prints for each method, each in a JVM of its own: the first cell of `{5}` against 0,
/// and a caller's handler for an `IllegalArgumentException` catching the previous version's `app.Failure` and not
/// the new one's.
#[test]
fn each_version_alone_is_what_a_jvm_says_it_is() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let alone = |version: &Path| {
        ["first", "failing"]
            .iter()
            .map(|m| {
                let out = Command::new("java").arg("-cp").arg(version).args(["app.Entry", m]).output().expect("java runs");
                assert!(out.status.success(), "{m}: {}", String::from_utf8_lossy(&out.stderr));
                String::from_utf8_lossy(&out.stdout).trim().to_string()
            })
            .collect::<Vec<_>>()
            .join(" ")
    };
    assert_eq!(alone(old), "first=5 failing=handled");
    assert_eq!(alone(new), "first=0 failing=escaped app.Failure");
}

/// The checker's side: each pair of versions is told apart by a caller when each runs alone (the test above), so a
/// proof that they agree is false.
#[test]
fn the_fresh_pair_does_not_prove_two_versions_agree_that_a_caller_tells_apart() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let mut wrong = Vec::new();
    for (name, assume, scope) in [("first", "cells != null", Some("app.Entry.zeroed(cells)")), ("failing", "k >= 0 && k < 4", None)] {
        let mut o = equivalence::Options::new(old, new, &format!("app.Entry#{name}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.max_array_length = 2;
        o.assume = Some(assume.into());
        o.unchanged_unless = scope.map(Into::into);
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("fresh-pair-countermodels").join(name));
        let out = equivalence::run(&o).unwrap();
        eprintln!("--- {name}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(name);
        }
    }
    assert!(wrong.is_empty(), "proved to agree, though a caller tells the versions apart when each runs alone: {wrong:?}");
}
