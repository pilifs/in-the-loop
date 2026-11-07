//! The heap stream's engine tests (`llm-dlc/loops/foundations-heap.md`): symbolic references in the own checker
//! (H1). Each claim is a Java method that throws `AssertionError` where it fails, compiled here and checked by
//! [`jvmcontract::bmc::check`] directly, so that the merge threshold can be set: merged from the start, a
//! reference that differs between the paths that meet is a choice among objects; never merged, every path keeps
//! its references known, as before symbolic references. Both must give the same verdict, the merged one in far
//! fewer paths, and every violation's input must fail the claim on a real JVM too.
//!
//! Object inputs (H2) start with array parameters that may be null or one array with another
//! (`--nullable`, `--may-alias`): their claims are in the conformance corpus, and here a witness with one array
//! passed twice, or a null, is run on the JVM as it is.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::bmc::{self, Options};
use jvmcontract::classpath::ClassPath;
use jvmcontract::Verdict;

const SOURCE: &str = r#"
package heap;

public class Refs {
    static class A { int x; int k() { return 0; } }
    static class B extends A { int k() { return 1; } }

    // Ten independent choices between a and b, then a write through the one chosen, seen through both names.
    static int swaps(int n) {
        A a = new A(); a.x = 1;
        A b = new A(); b.x = 2;
        A x = (n & 1) != 0 ? b : a;
        SWAPS(x = x == a ? b : a;)
        x.x += 10;
        return a.x * 100 + b.x + (x == a ? 1000 : 0);
    }

    public static void swapsHold(int n) { int r = swaps(n); if (r != 2102 && r != 112) throw new AssertionError(); }

    public static void swapsEven(int n) { if (swaps(n) != 2102) throw new AssertionError(); }

    // The same, with null among the options: a read through it throws where it is null.
    static int orNull(int n) {
        A a = new A(); a.x = 1;
        A b = new A(); b.x = 2;
        A x = (n & 1) != 0 ? null : a;
        SWAPS(x = x == a ? b : x == b ? a : null;)
        return x.x;
    }

    public static void orNullHolds(int n) {
        try { int r = orNull(n); if (r != 1 && r != 2) throw new AssertionError(); }
        catch (NullPointerException e) { if ((n & 1) == 0) throw new AssertionError(); }
    }

    public static void orNullNeverThrows(int n) {
        try { orNull(n); } catch (NullPointerException e) { throw new AssertionError(); }
    }

    // Objects of two classes: instanceof and a cast through the choice, and a virtual call, which splits on it.
    static int classes(int n) {
        A a = new A(); a.x = 1;
        A b = new B(); b.x = 2;
        A x = (n & 1) != 0 ? b : a;
        SWAPS(x = x == a ? b : a;)
        int r = x instanceof B ? 10 : 20;
        return r + x.k() * 100 + ((A) x).x;
    }

    public static void classesHold(int n) { int r = classes(n); if (r != 112 && r != 21) throw new AssertionError(); }

    public static void classesOdd(int n) { if (classes(n) != 112) throw new AssertionError(); }

    public static void main(String[] args) throws Exception {
        try {
            Refs.class.getMethod(args[0], int.class).invoke(null, Integer.parseInt(args[1]));
            System.out.println("holds");
        } catch (java.lang.reflect.InvocationTargetException e) {
            System.out.println(e.getCause() instanceof AssertionError ? "fails" : "throws " + e.getCause());
        }
    }
}
"#;

fn compiled() -> Option<&'static Path> {
    static DIR: OnceLock<Option<PathBuf>> = OnceLock::new();
    DIR.get_or_init(|| {
        let found = Command::new("javac").arg("--version").output().is_ok_and(|o| o.status.success());
        if !found {
            assert!(std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1"), "javac not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1");
            return None;
        }
        let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("heap-refs");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(dir.join("heap")).unwrap();
        // SWAPS(s) is s for each of bits 1 to 9 of n.
        let mut source = String::new();
        for line in SOURCE.lines() {
            match line.trim().strip_prefix("SWAPS(").and_then(|s| s.strip_suffix(')')) {
                Some(body) => (1..10).for_each(|i| source += &format!("        if ((n & {}) != 0) {body}\n", 1 << i)),
                None => source += &format!("{line}\n"),
            }
        }
        let file = dir.join("heap/Refs.java");
        std::fs::write(&file, source).unwrap();
        let status = Command::new("javac").args(["-g", "-proc:none", "-d"]).arg(&dir).arg(&file).status().expect("javac runs");
        assert!(status.success(), "Refs.java compiles");
        Some(dir)
    })
    .as_deref()
}

fn check(dir: &Path, method: &str, merge_after: u64) -> bmc::Outcome {
    let mut cp = ClassPath::new().with_default_jdk();
    cp.add(dir).unwrap();
    let options = Options { merge_after, ..Options::default() };
    bmc::check(&cp, "heap/Refs", method, &options).unwrap_or_else(|e| panic!("{method}: {e}"))
}

fn on_the_jvm(dir: &Path, method: &str, n: &str) -> String {
    let run = Command::new("java").arg("-cp").arg(dir).arg("heap.Refs").arg(method).arg(n).output().expect("java runs");
    assert!(run.status.success(), "{}", String::from_utf8_lossy(&run.stderr));
    String::from_utf8_lossy(&run.stdout).trim().to_string()
}

/// Checks `method` merged from the start and never merged: the same verdict, the one expected, and a violation's
/// input failing the claim on the JVM. Returns the paths each explored.
fn both_ways(method: &str, expected: Verdict) -> Option<(u64, u64)> {
    let dir = compiled()?;
    let merged = check(dir, method, 0);
    let unmerged = check(dir, method, u64::MAX);
    for (how, outcome) in [("merged", &merged), ("unmerged", &unmerged)] {
        assert_eq!(outcome.verdict, expected, "{method}, {how}: {}", outcome.summary());
        if expected == Verdict::Violation {
            let n = &outcome.raw_inputs[&0];
            assert_eq!(on_the_jvm(dir, method, n), "fails", "{method}, {how}: the witness n = {n} fails the claim on the JVM");
        }
    }
    eprintln!("{method}: merged {} paths, {} merges; unmerged {} paths", merged.paths, merged.merges, unmerged.paths);
    Some((merged.paths, unmerged.paths))
}

#[test]
fn paths_that_differ_in_a_reference_merge_and_a_write_through_it_is_seen_through_every_name() {
    let Some((merged, unmerged)) = both_ways("swapsHold", Verdict::Verified) else { return };
    assert!(unmerged >= 1024, "unmerged, every combination of the ten choices is a path: {unmerged}");
    assert!(merged < 100, "merged, the choices are one path per join: {merged} paths");
    both_ways("swapsEven", Verdict::Violation);
}

#[test]
fn a_read_through_a_reference_that_may_be_null_throws_where_it_is() {
    let Some((merged, unmerged)) = both_ways("orNullHolds", Verdict::Verified) else { return };
    assert!(merged * 10 < unmerged, "merged {merged} paths, unmerged {unmerged}");
    both_ways("orNullNeverThrows", Verdict::Violation);
}

#[test]
fn instanceof_is_a_formula_over_the_choice_and_a_call_on_it_splits_the_path() {
    both_ways("classesHold", Verdict::Verified);
    both_ways("classesOdd", Verdict::Violation);
}

/// A harness that fails where its two arrays are one, and a method that writes through both.
const ALIASES: &str = r#"
public class AliasCheck {
    public static void check(int[] a, int[] b) { if (a == b) throw new AssertionError(); }
    public static int first(int[] a, int[] b) { a[0] = 1; b[0] = 2; return a[0]; }
}
"#;

/// A witness whose arrays are one array, or one of them null, runs on the JVM as it is: the same array passed
/// twice, a write through one seen through the other (`jvm_witness::run`, which the property check uses where the
/// interpreter cannot replay a witness).
#[test]
fn a_witness_with_one_array_twice_or_null_runs_on_the_jvm_as_it_is() {
    use jvmcontract::classfile::Type;
    use jvmcontract::interp::Value;
    use jvmcontract::jbmc::Argument;
    use jvmcontract::jvm_witness::{self, Check, DirectCall};
    if compiled().is_none() {
        return;
    }
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("heap-aliases");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("AliasCheck.java"), ALIASES).unwrap();
    let status = Command::new("javac").args(["-g", "-proc:none", "-d"]).arg(&dir).arg(dir.join("AliasCheck.java")).status().expect("javac runs");
    assert!(status.success());
    let types = [Type::Array(Box::new(Type::Int)), Type::Array(Box::new(Type::Int))];
    let call = DirectCall { owner: "AliasCheck".into(), name: "first".into(), descriptor: "([I[I)I".into(), ret: Type::Int };
    let run = |arguments: &[Argument]| jvm_witness::run(&dir.join("run"), "AliasCheck", &types, &[0, 1], arguments, std::slice::from_ref(&call), std::slice::from_ref(&dir)).unwrap();

    let same = run(&[Argument::Array(vec![Value::Int(0)]), Argument::Same(0)]);
    assert_eq!(same.check, Check::Refuted, "the harness is given one array twice");
    assert_eq!(same.calls[0].outcome, "2", "the second write is seen through the first name");
    assert_eq!(same.calls[0].arrays_after, vec![(0, vec![Value::Int(2)]), (1, vec![Value::Int(2)])]);

    let distinct = run(&[Argument::Array(vec![Value::Int(0)]), Argument::Array(vec![Value::Int(0)])]);
    assert_eq!(distinct.check, Check::Holds);
    assert_eq!(distinct.calls[0].outcome, "1");

    let null = run(&[Argument::Array(vec![Value::Int(0)]), Argument::Null]);
    assert_eq!(null.check, Check::Holds);
    assert_eq!(null.calls[0].thrown.as_deref(), Some("java/lang/NullPointerException"));
    assert_eq!(null.calls[0].arrays_after, vec![(0, vec![Value::Int(1)])], "the null leaves nothing, the array what was written before the throw");
}
