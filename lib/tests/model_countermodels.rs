//! Countermodels of the models on request (`--model`, `jvmcontract::models::ON_REQUEST`) under `--gaps assume`:
//! the state stream added `java.util.ArrayDeque` and `java.util.HashSet` to `java.util.ArrayList` (`kztoupry`,
//! 2026-11-17). A collection made by a call the model does not keep (`ArrayDeque.clone()`, `ArrayDeque(Collection)`,
//! `ArrayList(Collection)`) is, under assume, a new object of the class with no field written, and the model's
//! `size()` then reads 0 where a JVM reads 1; without the model `size()` is a gap refused under assume too. The
//! fixtures are `tests/fixtures/model-countermodels/mc`, and this test holds them to what a JVM says. The checker's
//! side, the proofs it should not make, is in the fixtures' README for the stream that owns the models
//! (domain-advances-state), and the last test here holds the checker to it.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::bmc::gaps::GapMode;
use jvmcontract::{property, Engine, Verdict};

fn has(tool: &str) -> bool {
    Command::new(tool).arg("-version").output().is_ok()
}

/// The fixtures, compiled: `None` without a JDK.
fn classes() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/model-countermodels/mc");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("model-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out).arg(sources.join("Gapped.java")).status().expect("javac runs");
        assert!(status.success(), "the fixtures compile");
        Some(out)
    })
    .as_deref()
}

/// Each collection holds the one element it was made with, on a JVM.
#[test]
fn each_collection_a_gap_makes_is_what_a_jvm_says_it_is() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let out = Command::new("java").arg("-cp").arg(classes).arg("mc.Gapped").output().expect("java runs");
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert_eq!(String::from_utf8_lossy(&out.stdout).trim(), "cloned=1 copied=1 listed=1");
}

/// The checker's side: under `--gaps assume`, with the class's model asked for, no proof that the collection is
/// empty, since a JVM says it holds one element (the test above). A gap that would make or construct an object of a
/// class whose model the check runs is refused by name, as a value that could only be made up.
#[test]
fn a_model_does_not_read_fields_no_constructor_of_it_wrote() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let mut wrong = Vec::new();
    for (method, model, call) in [("cloned", "java.util.ArrayDeque", "java.util.ArrayDeque.clone()"), ("copied", "java.util.ArrayDeque", "java.util.ArrayDeque.<init>(Ljava/util/Collection;)V"), ("listed", "java.util.ArrayList", "java.util.ArrayList.<init>(Ljava/util/Collection;)V")] {
        let mut o = property::Options::new(&[classes.to_path_buf()], &format!("mc.Gapped#{method}"));
        o.engine = Engine::Native;
        o.jbmc = "/nonexistent/jbmc".into();
        o.gaps = GapMode::Assume;
        o.assert = Some("result == 0".into());
        o.requested_models = vec![model.to_string()];
        o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("model-countermodels").join(method));
        let out = property::run(&o).unwrap();
        eprintln!("--- {method}: {:?}\n{}", out.verdict, out.output);
        if out.verdict == Verdict::Verified {
            wrong.push(method);
        }
        assert!(out.verdict == Verdict::Unverifiable && out.output.contains(call) && out.output.contains("could only be made up"), "{method}: refused by name\n{}", out.output);
    }
    assert!(wrong.is_empty(), "proved empty, though a JVM says each holds one element: {wrong:?}");
}
