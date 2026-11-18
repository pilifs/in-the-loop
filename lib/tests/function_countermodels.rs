//! Countermodels of a call taken as one function of both versions, the preservation stream's call-level rule
//! (`lib/src/bmc/ties.rs`, `shared::one_function`; `uxyusvsv` and `xuwlklyo`, 2026-11-17). The rule takes a call of
//! code both versions share as a function of its inputs: equal arguments and statics give one outcome, which is
//! whether it throws and which class, the result, and the cells it writes. What the outcome leaves out: cells a JDK
//! method writes when the callee has no array store of its own (`Arrays.fill`, `System.arraycopy`); a String's
//! identity, both as an input (`s == "key"`) and as a result (a new String, or a literal); and an `Error` the JVM
//! raises (`StackOverflowError`, `OutOfMemoryError`). The fixtures are `tests/fixtures/function-countermodels`
//! (`old/` and `new/`, whose `Shared` is the same bytes in both); each version's `main` runs every method alone, and
//! this test holds the fixtures to what a JVM says. The checker's side, the proofs it should not make, is the last
//! test, from the fixtures' README.

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
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/function-countermodels");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("function-countermodels-classes");
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

/// Each version alone: every method calls the same code of `Shared` (or the previous version reads what the new
/// one does not), and a JVM tells the two apart on each. -1 and -2 are each version's handler of the callee's
/// exception or Error.
#[test]
fn each_version_alone_differs_past_the_shared_call_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let shared = |version: &Path| std::fs::read(version.join("app/Shared.class")).expect("Shared compiled");
    assert_eq!(shared(old), shared(new), "Shared is the same bytes in both versions");
    let alone = |version: &Path| {
        let out = Command::new("java").env_remove("JAVA_TOOL_OPTIONS").arg("-cp").arg(version).arg("app.Entry").output().expect("java runs");
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).trim().to_string()
    };
    assert_eq!(alone(old), "filled=5 copied=5 hashed=0 interned=1 same=0 tagged=1 encoded=-1 overflowed=-1 exhausted=-1 messaged=1");
    assert_eq!(alone(new), "filled=0 copied=0 hashed=1 interned=0 same=1 tagged=0 encoded=-2 overflowed=-2 exhausted=-2 messaged=0");
}

/// The checker's side: each version alone tells every method apart (the test above), so a proof that they agree is
/// false.
#[test]
fn a_call_taken_as_one_function_does_not_prove_what_its_outcome_leaves_out() {
    jvmcontract::tool_tier!();
    let Some((old, new)) = classes() else { return };
    let mut wrong = Vec::new();
    for name in ["filled", "copied", "hashed", "interned", "same", "tagged", "encoded", "overflowed", "exhausted", "messaged"] {
        let mut o = equivalence::Options::new(old, new, &format!("app.Entry#{name}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.assume = Some("k >= 0".into());
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("function-countermodels").join(name));
        let out = equivalence::run(&o).unwrap();
        eprintln!("--- {name}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(name);
        }
    }
    assert!(wrong.is_empty(), "proved to agree, though each version alone tells them apart: {wrong:?}");
}
