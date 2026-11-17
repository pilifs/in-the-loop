//! Countermodels of a loop invariant (`lib/src/bmc/loops.rs`): loops whose later iterations do what the first ones
//! do not, each read after the loop. The invariant search runs an iteration from the state past the bound, sets
//! what it wrote to any value, and keeps the candidates an iteration does not break; a false invariant would be a
//! false proof of everything after the loop. The challenge stream tried (domain-advances, item 4, 2026-11-17): a
//! value written only in a late iteration, by the loop and by a callee into statics, an array under two names, a
//! relation between two cells, an object reached through an array's cell, a loop inside a loop, and a table written
//! at a computed index. The fixture is `tests/fixtures/loop-countermodels/lo/L.java`, and `lo.L.main` prints what
//! a JVM says. None was proved: past the bound each is no verdict, and a bound that covers the late iteration
//! refutes it. Its README says what guards each.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::property::{self, Outcome};
use jvmcontract::{Engine, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";

fn has(tool: &str) -> bool {
    Command::new(tool).arg("--version").output().is_ok()
}

/// The fixture, compiled: `None` without a JDK.
fn classes() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let source = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/loop-countermodels/lo/L.java");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("loop-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let status = Command::new("javac").args(["-g", "-proc:none", "-d"]).arg(&out).arg(source).status().expect("javac runs");
        assert!(status.success(), "the fixture compiles");
        Some(out)
    })
    .as_deref()
}

/// What `lo.L` prints: each entry point on the least input whose late iteration does what the first do not.
#[test]
fn each_loop_is_what_a_jvm_says_it_is() {
    jvmcontract::tool_tier!();
    let Some(c) = classes() else { return };
    let out = Command::new("java").arg("-cp").arg(c).arg("lo.L").output().expect("java runs");
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert_eq!(String::from_utf8_lossy(&out.stdout).trim(), "late=1 callee=1 aliased=9 twoCells=102 boxed=7 nested=1 large=4");
}

fn check(target: &str, assume: &str, assert: &str, unwind: u32) -> Outcome {
    let c = classes().unwrap();
    let mut o = property::Options::new(&[c.to_path_buf()], &format!("lo.L#{target}"));
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.unwind = unwind;
    o.assume = Some(assume.into());
    o.assert = Some(assert.into());
    o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("loop-countermodels").join(format!("{target}-{unwind}")));
    property::run(&o).unwrap()
}

/// At `--unwind 2` every loop goes past the bound before its late iteration, and the checker proves none of the
/// false properties: the invariant leaves what the loop writes any value, the path past it reaches a state no run
/// reaches, its witness does not reproduce, and that is no verdict, with the loop named.
#[test]
fn no_invariant_keeps_what_a_later_iteration_breaks() {
    jvmcontract::tool_tier!();
    if classes().is_none() {
        return;
    }
    for (target, assume, assert) in [
        ("late", "n >= 0", "result == 0"),
        ("callee", "n >= 0", "result == 0"),
        ("aliased", "n >= 0", "result == 0"),
        ("twoCells", "n >= 0", "result < 100"),
        ("boxed", "n >= 0", "result == 0"),
        ("nested", "n >= 0 && m >= 0", "result == 0"),
        ("large", "n >= 0", "result <= 3"),
    ] {
        let o = check(target, assume, assert, 2);
        assert_eq!(o.verdict, Verdict::Unverifiable, "{target}: {}", o.output);
        assert!(o.output.contains("does not reproduce") && o.output.contains(&format!("covers by an invariant (lo.L.{target} at pc")), "{target}: {}", o.output);
    }
    // A bound that reaches the late iteration refutes it.
    let o = check("late", "n >= 0", "result == 0", 7);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
}
