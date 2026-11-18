//! Loops that go round more often than `--unwind`, covered by invariants the own checker finds and proves
//! (`lib/src/bmc/loops.rs`): the proof holds of every iteration and names the loops, a defect past such a loop is
//! refuted on the least input, run before it is believed, and what only the invariant admits is no verdict.
//!
//! The fixture (`tests/fixtures/loops/loops/Rounds.java`) is a hash in the shape of bcrypt's: `2^cost` rounds over
//! a state, each a pass two words at a time, each word looked up in a table of 128 at an index the state computes,
//! the key read round and round with `% length`. Every check runs at `--unwind 3`, which no loop of it is within.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::property::{self, Outcome};
use jvmcontract::{Engine, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";

/// What `digest` throws, and exactly when.
const THROWS: &str = "java.lang.IllegalArgumentException when key.length > 8 || cost < 4 || cost > 30";

fn has(program: &str) -> bool {
    let found = Command::new(program).arg("--version").output().map(|o| o.status.success()).unwrap_or(false);
    if !found {
        let skip = std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1");
        assert!(skip, "{program} not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip the tests that need it");
    }
    found
}

/// The fixture, compiled once with its parameter names.
fn classes() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let source = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/loops/loops/Rounds.java");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("loops-classes");
        let _ = std::fs::remove_dir_all(&out);
        std::fs::create_dir_all(&out).unwrap();
        let status = Command::new("javac").args(["-g", "-proc:none", "-d"]).arg(&out).arg(source).status().expect("javac runs");
        assert!(status.success(), "the loops fixture compiles");
        Some(out)
    })
    .as_deref()
}

fn options(classes: &Path, method: &str, assert: &str, work: &str) -> property::Options {
    let mut o = property::Options::new(&[classes.to_path_buf()], &format!("loops.Rounds#{method}"));
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.unwind = 3;
    o.max_array_length = 12;
    o.assert = Some(assert.into());
    o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("loops").join(work));
    o
}

fn run(o: &property::Options) -> Outcome {
    property::run(o).unwrap()
}

/// The hash with its length check is proved to throw exactly as stated and nothing else, through `2^cost` rounds of
/// nested loops, the table and the key read cyclically; the verdict names the loops an invariant covers.
#[test]
fn a_loop_beyond_the_bound_is_covered_by_an_invariant_and_named_in_the_verdict() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let mut o = options(classes, "digest", "true", "digest");
    o.assume = Some("key != null".into());
    o.throws = vec![THROWS.into()];
    let o = run(&o);
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.output.contains("loops unwound 3 times with unwinding assertions; 4 loops beyond the bound covered by invariants the checker found and proved (loops.Rounds.<clinit> at pc 10, loops.Rounds.mixed at pc 52, loops.Rounds.mixed at pc 64, loops.Rounds.word at pc 9)"), "{}", o.output);
    // Each loop has a local that grows: nothing is taken for granted about their ending.
    let stated = o.stated.as_ref().expect("a statement");
    assert!(!stated.assumptions.iter().any(|a| a.text.contains("ends")), "{:?}", stated.assumptions);

    // What an invariant keeps of a number is its bounds and its low bits: a count kept in a field and a static
    // stays even, whatever the iterations.
    let o = run(&options(classes, "counted", "(result & 1) == 0", "counted-even"));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
}

/// The same hash without the length check is refuted: the witness is the least input the violating path has (the
/// lowest cost, where the solver's first was the highest of its stage), and it is run before it is reported.
#[test]
fn a_defect_past_a_summarized_loop_is_refuted_on_the_least_input_and_replayed() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let mut o = options(classes, "unchecked", "true", "unchecked");
    o.assume = Some("key != null".into());
    o.throws = vec![THROWS.into()];
    let o = run(&o);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let witness = o.counterexample.as_ref().expect("a witness");
    assert!(witness.input.contains("cost=4"), "the fewest rounds: {}", witness.input);
    assert!(o.output.contains("replayed in the interpreter"), "{}", o.output);

    // A pass that steps past the state's end throws in the loop's body, which the path past the invariant runs.
    let mut o = options(classes, "overrun", "true", "overrun");
    o.assume = Some("key != null".into());
    o.throws = vec!["java.lang.IllegalArgumentException when key.length > 8".into()];
    let o = run(&o);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.output.contains("replayed in the interpreter"), "{}", o.output);
}

/// An invariant says less of a loop than its iterations do. A claim that needs more (the count is twice `n`; a cell
/// of a table a loop filled) is no verdict, with the loops named and the way out; a larger bound decides it.
#[test]
fn what_only_the_invariant_admits_is_no_verdict_and_names_the_loop() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let o = run(&options(classes, "counted", "n <= 0 ? result == 0 : result == 2 * n", "counted-exact"));
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.output.contains("does not reproduce"), "{}", o.output);
    assert!(o.output.contains("goes past a loop the tool's own checker covers by an invariant (loops.Rounds.<clinit> at pc 10, loops.Rounds.counted at pc 10)"), "{}", o.output);
    assert!(o.output.contains("A larger --unwind follows more iterations exactly"), "{}", o.output);

    // The table's 128 cells are any values past its loop's invariant, and its own values within the bound.
    let o = run(&options(classes, "table", "result", "table"));
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.output.contains("loops.Rounds.<clinit> at pc 10"), "{}", o.output);
    let mut within = options(classes, "table", "result", "table-within");
    within.unwind = 130;
    let o = run(&within);
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(!o.output.contains("beyond the bound"), "{}", o.output);
}

/// A loop no invariant of numbers covers stays the unwound loop it was, with why; and a loop in which no local
/// grows is proved of the runs in which it ends, which the statement says.
#[test]
fn a_loop_that_is_not_covered_says_why_and_one_not_shown_to_end_is_stated() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let o = run(&options(classes, "renewed", "result == 1", "renewed"));
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.output.contains("a loop was not fully unwound with --unwind 3 (loops.Rounds.renewed at pc 6; no invariant was found that covers its further iterations: an iteration changes local 1, which holds a reference (at the head "), "{}", o.output);

    let o = run(&options(classes, "stuck", "true", "stuck"));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().expect("a statement");
    assert!(stated.assumptions.iter().any(|a| a.text.contains("the loop of loops.Rounds.stuck at pc 4 ends")), "{:?}", stated.assumptions);
}
