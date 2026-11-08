//! A string literal's code units, as the class file holds them (Phase 5 step 1 of
//! `llm-dlc/loops/application-core.md`, the values stream's request for the merge): an isolated surrogate in a
//! literal's source is a code unit of its own, as the JVM reads it. Before, the class reader decoded every
//! `CONSTANT_Utf8` as Rust text, so `"\uDBFF"` and `"\uDBFE"` were both `"\uFFFD"`, for the interpreter, the own
//! checker, the closure digests and the relocated classes the JVM runs alike. A rewrite to the JVM's constant was
//! refuted, a changed literal was proved, and a proof stored for one literal was reused for the other.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::equivalence;
use jvmcontract::spec::cache::Reuse;
use jvmcontract::{Engine, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";
const TARGET: &str = "s.Lit#unit";

fn tmp(name: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("string-literals").join(name);
    let _ = std::fs::remove_dir_all(&dir);
    dir
}

/// `s.Lit` as each build has it. `before` reads the literal `"\uDBFF"` for the empty String; `constant` returns the
/// JVM's code unit, 0xDBFF, without a literal; `other` reads `"\uDBFE"`, which differs only in its surrogate.
/// `rewrite` is `before` with its branches swapped, and `rewrite-other` is `rewrite` reading `"\uDBFE"`: two
/// bodies that a reading of both literals as U+FFFD can't tell apart.
fn build(name: &str) -> PathBuf {
    static ROOT: OnceLock<PathBuf> = OnceLock::new();
    let root = ROOT.get_or_init(|| {
        let root = tmp("builds");
        let swapped = |unit: &str| format!("s.length() != 0 ? (\"\\uDBFF\" == \"\\uDBFE\" ? -1 : s.length()) : \"{unit}\".charAt(0)");
        for (name, body) in [
            ("before", "s.length() == 0 ? \"\\uDBFF\".charAt(0) : \"\\uDBFF\" == \"\\uDBFE\" ? -1 : s.length()".to_string()),
            ("constant", "s.length() == 0 ? 0xDBFF : s.length()".to_string()),
            ("other", "s.length() == 0 ? \"\\uDBFE\".charAt(0) : \"\\uDBFF\" == \"\\uDBFE\" ? -1 : s.length()".to_string()),
            ("rewrite", swapped("\\uDBFF")),
            ("rewrite-other", swapped("\\uDBFE")),
        ] {
            let source = root.join("src").join(name).join("s/Lit.java");
            std::fs::create_dir_all(source.parent().unwrap()).unwrap();
            std::fs::write(&source, format!("package s;\npublic final class Lit {{\n    public static int unit(String s) {{ return {body}; }}\n}}\n")).unwrap();
            let status = Command::new("javac").args(["-g", "-proc:none", "-nowarn", "-d"]).arg(root.join(name)).arg(&source).status().expect("the test needs javac");
            assert!(status.success(), "{name} compiles");
        }
        root
    });
    root.join(name)
}

fn options(before: &Path, after: &Path, work: &str, cache: Option<&Path>) -> equivalence::Options {
    let mut o = equivalence::Options::new(before, after, TARGET);
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.work = Some(tmp(work));
    o.cache = cache.map(Path::to_path_buf);
    o
}

/// The own checker reads a literal by its code units: the rewrite to the constant 0xDBFF is proved (two different
/// literals are never one interned object, so `-1` is never returned), and the literal changed to `"\uDBFE"` is
/// refuted on the empty String, on a witness replayed in the interpreter and on a JVM, which run the old version
/// relocated: copied as text, its literal would have become `"\uFFFD"` there too.
#[test]
fn a_literals_isolated_surrogate_is_its_own_code_unit_for_the_checker_the_interpreter_and_the_jvm() {
    let proved = equivalence::run(&options(&build("before"), &build("constant"), "constant", None)).unwrap();
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);

    let refuted = equivalence::run(&options(&build("before"), &build("other"), "other", None)).unwrap();
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    assert!(refuted.replay.as_ref().is_some_and(|r| r.reproduced), "{}", refuted.output);
    let c = refuted.counterexample.as_ref().expect("a witness");
    assert!(c.jvm.is_some(), "run on a JVM: {}", refuted.output);
    assert_eq!(c.input, "unit(s=\"\")", "{}", refuted.output);
    assert!(refuted.output.contains("56319") && refuted.output.contains("56318"), "each version's unit, 0xDBFF and 0xDBFE: {}", refuted.output);
}

/// A literal is part of the claim key by its code units: the proof of `rewrite`, stored, is reused for the same
/// builds exactly, and never for `rewrite-other`, whose literal differs only in its surrogate: it is proved again,
/// and refuted.
#[test]
fn a_cached_proof_is_never_reused_for_a_literal_that_differs_only_in_its_surrogate() {
    let cache = tmp("cache");
    let stored = equivalence::run(&options(&build("before"), &build("rewrite"), "cold", Some(&cache))).unwrap();
    assert_eq!(stored.verdict, Verdict::Verified, "{}", stored.output);
    assert!(stored.reuse.is_none(), "{}", stored.output);

    let again = equivalence::run(&options(&build("before"), &build("rewrite"), "again", Some(&cache))).unwrap();
    assert_eq!(again.verdict, Verdict::Verified, "{}", again.output);
    assert!(matches!(again.reuse, Some(Reuse::Exact { .. })), "the exact rerun is reused: {}", again.output);

    let other = equivalence::run(&options(&build("before"), &build("rewrite-other"), "edited", Some(&cache))).unwrap();
    assert!(other.reuse.is_none(), "another literal is another claim: {}", other.output);
    assert_eq!(other.verdict, Verdict::Violation, "{}", other.output);
}
