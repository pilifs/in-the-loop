//! Countermodels of a checked summary (`prove --lemmas`, `lib/src/summary.rs`, `Engine::reads` and `Engine::keeps`
//! in `lib/src/bmc/mod.rs`): what the foundation's refusals left. A lemma is proved from the state the harness
//! starts in, and its summary then stands in for its method's calls in whatever state they are made. The fixtures
//! are `tests/fixtures/lemma-countermodels/lc`, and `lc.M.main` runs one entry point on a JVM. Each property the
//! tests below call false is false there; each was proved (`Verified`) by the checker at `llwznzwm` (2026-11-17),
//! and is now refused or refuted. The fixtures' README has the table and what was tried and found guarded.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::property::{self, Outcome};
use jvmcontract::{Engine, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";

fn has(tool: &str) -> bool {
    Command::new(tool).arg("--version").output().is_ok()
}

/// The fixtures, compiled: `None` without a JDK.
fn classes() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/lemma-countermodels/lc");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("lemma-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let mut files: Vec<PathBuf> = std::fs::read_dir(&sources).unwrap().map(|e| e.unwrap().path()).filter(|p| p.extension().is_some_and(|e| e == "java")).collect();
        files.sort();
        let status = Command::new("javac").args(["-g", "-proc:none", "-d"]).arg(&out).args(files).status().expect("javac runs");
        assert!(status.success(), "the fixtures compile");
        Some(out)
    })
    .as_deref()
}

/// What `lc.M` prints for each entry point, each in a JVM of its own (which classes are initialized, and when,
/// is what they turn on), in English.
#[test]
fn each_entry_point_is_what_a_jvm_says_it_is() {
    jvmcontract::tool_tier!();
    let Some(c) = classes() else { return };
    let said: Vec<String> = [
        "seen",
        "heldSeen",
        "derivedLimit",
        "setThenOwn",
        "turkishThenLowered",
        "setThenCopied",
        "appendThenLogged",
        "appendThenLoggedThroughLambda",
        "setThenBoxed",
        "addThenItems",
        "setThenReflected",
        "once",
        "pinged",
    ]
    .iter()
    .map(|m| {
        let out = Command::new("java").args(["-Duser.language=en", "-Duser.country=US", "-cp"]).arg(c).args(["lc.M", m]).output().expect("java runs");
        assert!(out.status.success(), "{m}: {}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).trim().to_string()
    })
    .collect();
    assert_eq!(
        said.join(" "),
        "seen=0 heldSeen=0 derivedLimit=7 setThenOwn=5 turkishThenLowered=305 setThenCopied=5 appendThenLogged=1 appendThenLoggedThroughLambda=1 setThenBoxed=5 addThenItems=1 setThenReflected=5 once=StackOverflowError pinged=StackOverflowError"
    );
}

fn lemmas(name: &str, text: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("lemma-countermodels").join("lemmas");
    std::fs::create_dir_all(&dir).unwrap();
    let file = dir.join(format!("{name}.contract"));
    std::fs::write(&file, text).unwrap();
    file
}

/// The check of `target` that `result == expected`, with the lemma `lemma` (a target line and its clauses).
fn check(name: &str, target: &str, expected: i32, lemma: &str) -> Outcome {
    let c = classes().unwrap();
    let mut o = property::Options::new(&[c.to_path_buf()], target);
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.assert = Some(format!("result == {expected}"));
    o.lemmas = Some(lemmas(name, lemma));
    o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("lemma-countermodels").join(name));
    property::run(&o).unwrap()
}

/// The lemma's own proof runs, through the harness or its assumption, the initializer of the class whose final
/// static field its method reads; a caller may call the method from inside that very initializer, before the
/// field is written. `Derived.limit()` is 7 once `Base` is initialized, and `Base.SEEN` its call from `Base`'s
/// initializer, 0: the summary made it 7. The foundation's guard looked at the method's own class only (`Derived`,
/// initialized); `Holder` is the same through a class that is no superclass, initialized by the lemma's
/// assumption. Now no summary is used while any class is being initialized, and the call runs as written: the
/// checker refutes both, and still uses the lemma where no initializer is under way.
#[test]
fn no_summary_stands_in_for_a_call_made_while_a_class_is_being_initialized() {
    jvmcontract::tool_tier!();
    if classes().is_none() {
        return;
    }
    let o = check("seen", "lc.M#seen", 7, "lc.Derived#limit\n  assert: result == 7\n");
    assert!(o.output.contains("lemma: ✓ lc.Derived#limit"), "the lemma itself is true: {}", o.output);
    assert_eq!(o.verdict, Verdict::Violation, "seen() is 0 on a JVM: {}", o.output);
    let o = check("held", "lc.M#heldSeen", 7, "lc.Reader#limit\n  assume: lc.Holder.SEEN >= 0\n  assert: result == 7\n");
    assert!(o.output.contains("lemma: ✓ lc.Reader#limit"), "the lemma itself is true: {}", o.output);
    assert_eq!(o.verdict, Verdict::Violation, "heldSeen() is 0 on a JVM: {}", o.output);
    let o = check("derived", "lc.M#derivedLimit", 7, "lc.Derived#limit\n  assert: result == 7\n");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.output.contains("note: lemma, proved above"), "the summary is still used: {}", o.output);
}

/// A final static field is written by its class's initializer alone, which is why a lemma may read one; but the
/// lemma's proof runs that initializer in the state the harness starts in, and a caller may initialize the class
/// later, after changing what the initializer reads: a static (`Own.LIMIT = Settings.value`), the default locale
/// (`Lowered.I = "I".toLowerCase()`), an array of a class initialized before it (`Copied.FIRST = Table.T[0]`). Each
/// was proved 0 or 105 where a JVM says 5 or 305. Now an initializer the lemma's proof runs reads nothing a caller
/// can change, as the lemma itself.
#[test]
fn a_lemma_rests_on_no_initializer_that_reads_what_a_caller_can_change() {
    jvmcontract::tool_tier!();
    if classes().is_none() {
        return;
    }
    for (name, target, expected, lemma, why) in [
        ("own", "lc.M#setThenOwn", 0, "lc.Own#limit\n  assert: result == 0\n", "the initializer of lc.Own, which the proof of the lemma about lc.Own.limit runs, reads the static field lc.Settings.value"),
        ("lowered", "lc.M#turkishThenLowered", 105, "lc.Lowered#lowered\n  assert: result == 105\n", "the initializer of lc.Lowered, which the proof of the lemma about lc.Lowered.lowered runs, reads the default locale"),
        ("copied", "lc.M#setThenCopied", 0, "lc.Copied#first\n  assert: result == 0\n", "the initializer of lc.Copied, which the proof of the lemma about lc.Copied.first runs, reads an array"),
    ] {
        let o = check(name, target, expected, lemma);
        assert_eq!(o.verdict, Verdict::Unverifiable, "{name}: {}", o.output);
        let problem = o.problem.as_deref().unwrap_or_default();
        assert!(problem.contains(why) && problem.contains("which a caller can change before it initializes the class"), "{name}: {}", o.output);
    }
}

/// A StringBuilder is no String: one a final static field holds, or a method reference captured, is there before
/// the call, and a caller appends to it. `Logged.logged()` was proved 0 where a JVM says 1, directly and through
/// `LOG::length`. Now a lemma reads no builder that was there before the call.
#[test]
fn a_lemma_reads_no_builder_a_caller_can_change() {
    jvmcontract::tool_tier!();
    if classes().is_none() {
        return;
    }
    for (name, target, lemma) in [("logged", "lc.M#appendThenLogged", "lc.Logged#logged\n  assert: result == 0\n"), ("lambda", "lc.M#appendThenLoggedThroughLambda", "lc.Logged#loggedThroughLambda\n  assert: result == 0\n")] {
        let o = check(name, target, 0, lemma);
        assert_eq!(o.verdict, Verdict::Unverifiable, "{name}: {}", o.output);
        assert!(o.problem.as_deref().unwrap_or_default().contains("reads a StringBuilder that was there before the call (length)"), "{name}: {}", o.output);
    }
}

/// Tried and found guarded, with the code that guards each: an array a lambda captured (`Engine::reads` on an
/// array that was there), the ArrayList model's size (a field of an object that was there, `reads_field`),
/// reflection (a gap), a lemma about a method that calls itself forever, and two lemmas about methods that call
/// each other (a lemma's proof is given no lemma, `property.rs`, so neither stands in for the other's call).
#[test]
fn what_was_tried_and_found_guarded() {
    jvmcontract::tool_tier!();
    if classes().is_none() {
        return;
    }
    for (name, target, expected, lemma, why) in [
        ("boxed", "lc.M#setThenBoxed", 0, "lc.Boxed#boxed\n  assert: result == 0\n", "reads an array that was there before the call"),
        ("reflected", "lc.M#setThenReflected", 0, "lc.Reflected#reflected\n  assert: result == 0\n", "java.lang.Class.getDeclaredField"),
        ("self", "lc.Self#once", 5, "lc.Self#forever\n  assert: result == 5\n", "calls nested deeper than 64"),
        ("mutual", "lc.M#pinged", 5, "lc.Mutual#ping\n  assert: result == 5\nlc.Mutual#pong\n  assert: result == 5\n", "calls nested deeper than 64"),
    ] {
        let o = check(name, target, expected, lemma);
        assert_eq!(o.verdict, Verdict::Unverifiable, "{name}: {}", o.output);
        assert!(o.problem.as_deref().unwrap_or_default().contains(why), "{name}: {}", o.output);
    }
    let c = classes().unwrap();
    let mut items = property::Options::new(&[c.to_path_buf()], "lc.M#addThenItems");
    items.engine = Engine::Native;
    items.jbmc = NO_JBMC.into();
    items.assert = Some("result == 0".into());
    items.lemmas = Some(lemmas("items", "lc.Listed#items\n  assert: result == 0\n"));
    items.requested_models = vec!["java.util.ArrayList".into()];
    items.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("lemma-countermodels").join("items"));
    let o = property::run(&items).unwrap();
    assert_eq!(o.verdict, Verdict::Unverifiable, "items: {}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("reads the field size of an object that was there before the call"), "items: {}", o.output);
}
