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

// Object inputs in regression checks (H2): a parameter of an application class, made in the harness by its
// constructor from symbolic arguments, an object argument made by its own constructor in turn. Both versions get
// their own objects from the same arguments, and their fields after the calls are compared.

const MONEY: &str = "package objects;\npublic record Money(long cents) {}\n";

const LINE: &str = r#"package objects;
public final class Line {
    Money price;
    int quantity;
    public Line(Money price, int quantity) {
        if (quantity <= 0) throw new IllegalArgumentException();
        this.price = price;
        this.quantity = quantity;
    }
}
"#;

const TAGGED: &str = r#"package objects;
public final class Tagged {
    String tag;
    int n;
    public Tagged(int n) { this.n = n; this.tag = "t"; }
}
"#;

const KERNEL_BEFORE: &str = r#"package objects;
public final class Kernel {
    public static long total(Line l) { return l.price.cents() * l.quantity; }
    public static long checked(Line l) { return l.price.cents() * l.quantity; }
    public static void bump(Line l) { l.quantity += 1; }
    public static int tagged(Tagged t) { return t.n; }
    public static Line withQuantity(Line l, int quantity) { l.quantity = quantity; return l; }
    public static Line doubled(Line l) { return new Line(l.price, l.quantity * 2); }
    public static int[] filled(int[] a) { for (int i = 0; i < a.length; i++) a[i] = 7; return a; }
    public static void move(Line from, Line to) { from.quantity -= 1; to.quantity += 1; }
    public static int size(Line l) { return l == null ? 0 : l.quantity; }
}
"#;

const KERNEL_AFTER: &str = r#"package objects;
public final class Kernel {
    public static long total(Line l) { return l.quantity * l.price.cents(); }
    // Wrong only for a quantity the constructor rejects.
    public static long checked(Line l) { if (l.quantity <= 0) return -1; return l.quantity * l.price.cents(); }
    public static void bump(Line l) { l.quantity = l.quantity + 1; }
    public static int tagged(Tagged t) { return t.n; }
    public static Line withQuantity(Line l, int quantity) { Line same = l; same.quantity = quantity; return same; }
    public static Line doubled(Line l) { return new Line(l.price, l.quantity + l.quantity); }
    public static int[] filled(int[] a) { int i = 0; while (i < a.length) { a[i] = 7; i++; } return a; }
    // In the other order, which is the same when from and to are one line too.
    public static void move(Line from, Line to) { to.quantity += 1; from.quantity -= 1; }
    public static int size(Line l) { return l != null ? l.quantity : 0; }
}
"#;

const KERNEL_DEFECT: &str = r#"package objects;
public final class Kernel {
    public static long total(Line l) { return (l.price.cents() + 1) * l.quantity; }
    public static long checked(Line l) { return l.price.cents() * l.quantity; }
    // Seen only in the parameter as the call leaves it.
    public static void bump(Line l) { l.quantity += 2; }
    public static int tagged(Tagged t) { return t.n; }
    // The alias-to-copy defect: a copy with the same values, the same price object, in place of the line itself.
    public static Line withQuantity(Line l, int quantity) { l.quantity = quantity; Line copy = new Line(l.price, 1); copy.quantity = quantity; return copy; }
    public static Line doubled(Line l) { return new Line(l.price, l.quantity * 3); }
    // The same defect for an array: filled in place, then a copy handed back.
    public static int[] filled(int[] a) { int[] b = new int[a.length]; for (int i = 0; i < a.length; i++) { a[i] = 7; b[i] = 7; } return b; }
    // Both quantities read before either is written: the same for two lines, but a move from a line to itself
    // now adds one where it changed nothing.
    public static void move(Line from, Line to) { int f = from.quantity - 1; int t = to.quantity + 1; from.quantity = f; to.quantity = t; }
    // The null check dropped.
    public static int size(Line l) { return l.quantity; }
}
"#;

/// The three builds of the object kernel, compiled once: `before`, `after` and `defect`.
fn object_builds() -> Option<&'static PathBuf> {
    static DIR: OnceLock<Option<PathBuf>> = OnceLock::new();
    DIR.get_or_init(|| {
        compiled()?;
        let root = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("heap-objects");
        let _ = std::fs::remove_dir_all(&root);
        for (build, kernel) in [("before", KERNEL_BEFORE), ("after", KERNEL_AFTER), ("defect", KERNEL_DEFECT)] {
            let src = root.join(format!("{build}-src/objects"));
            std::fs::create_dir_all(&src).unwrap();
            for (name, text) in [("Money", MONEY), ("Line", LINE), ("Tagged", TAGGED), ("Kernel", kernel)] {
                std::fs::write(src.join(format!("{name}.java")), text).unwrap();
            }
            let files: Vec<PathBuf> = ["Money", "Line", "Tagged", "Kernel"].iter().map(|n| src.join(format!("{n}.java"))).collect();
            let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-d"]).arg(root.join(build)).args(&files).status().expect("javac runs");
            assert!(status.success(), "the object kernel compiles");
        }
        Some(root)
    })
    .as_ref()
}

fn regression(after: &str, method: &str) -> Option<jvmcontract::equivalence::Outcome> {
    regression_over(after, method, &[], &[])
}

/// [`regression`] with object parameters that may be null (`nullable`) or one object (`may_alias`), step H2.
fn regression_over(after: &str, method: &str, nullable: &[&str], may_alias: &[(&str, &str)]) -> Option<jvmcontract::equivalence::Outcome> {
    let root = object_builds()?;
    let mut options = jvmcontract::equivalence::Options::new(&root.join("before"), &root.join(after), &format!("objects.Kernel#{method}"));
    options.engine = jvmcontract::Engine::Native;
    options.nullable = nullable.iter().map(|n| n.to_string()).collect();
    options.may_alias = may_alias.iter().map(|(a, b)| (a.to_string(), b.to_string())).collect();
    let work = root.join(format!("work-{after}-{method}-{}-{}", nullable.len(), may_alias.len()));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    Some(jvmcontract::equivalence::run(&options).unwrap())
}

/// A witness over objects is run on a JVM as well as in the interpreter (step H4): the harness on it, its objects
/// made from the same leaves, loading the application's classes opened so that it may read their private and
/// package-private fields.
fn confirmed_on_the_jvm(o: &jvmcontract::equivalence::Outcome) {
    let c = o.counterexample.as_ref().expect("a counterexample");
    assert!(c.jvm.is_some(), "{}", o.output);
    assert!(o.output.contains("replayed in the interpreter and run on a JVM (JDK "), "{}", o.output);
}

#[test]
fn an_object_made_by_its_constructor_is_a_regression_input_and_the_domain_says_how_it_is_made() {
    let Some(o) = regression("after", "total") else { return };
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let domain = o.domain.clone().unwrap();
    assert!(domain.contains("l: a Line made by its constructor, Line(price: Money(cents: long), quantity: int), from any arguments it accepts"), "{domain}");
    let stated = o.stated.as_ref().unwrap();
    assert_eq!(stated.observations.objects, vec!["l: price.cents, quantity".to_string()]);
}

#[test]
fn a_changed_result_over_an_object_input_is_refuted_with_a_construction_recipe() {
    let Some(o) = regression("defect", "total") else { return };
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().expect("a counterexample");
    assert!(c.input.starts_with("total(l=new Line(new Money("), "{}", c.input);
    assert_ne!(c.before, c.after, "the replays differ");
    confirmed_on_the_jvm(&o);
}

#[test]
fn a_change_seen_only_in_an_object_input_as_the_call_leaves_it_is_refuted() {
    let Some(o) = regression("defect", "bump") else { return };
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().expect("a counterexample");
    assert!(c.before.contains("leaving l=Line{price=Money{cents="), "{}", c.before);
    assert_ne!(c.before, c.after, "the replays differ");
    confirmed_on_the_jvm(&o);
    let Some(same) = regression("after", "bump") else { return };
    assert_eq!(same.verdict, Verdict::Verified, "{}", same.output);
}

#[test]
fn a_difference_only_where_the_constructor_refuses_is_outside_the_claim() {
    let Some(o) = regression("after", "checked") else { return };
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    // The headline names the domain too: never "on every input" alone over an object its constructor makes.
    assert!(o.output.starts_with("✓ objects.Kernel#checked behaves as before on every input of constructor-made objects ("), "{}", o.output);
    assert!(o.domain.as_deref().unwrap().contains("made by its constructor"));
    let stated = o.stated.as_ref().unwrap();
    assert!(stated.assumptions.iter().any(|a| a.text.contains("the objects both versions can build")), "{:?}", stated.assumptions);
}

#[test]
fn an_object_with_a_field_outside_the_supported_kinds_is_a_named_gap() {
    let Some(o) = regression("after", "tagged") else { return };
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    let problem = o.problem.unwrap();
    assert!(problem.contains("the field tag of objects.Tagged has type java.lang.String"), "{problem}");
}

#[test]
fn the_same_object_handed_back_is_compared_by_its_identity_relations_within_each_version() {
    let Some(o) = regression("after", "withQuantity") else { return };
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().unwrap();
    assert_eq!(stated.observations.identities, vec!["result == l".to_string(), "result.price == l.price".to_string()]);
    assert!(stated.observations.result.contains("a Line compared field by field (price.cents, quantity)"), "{}", stated.observations.result);
}

#[test]
fn an_alias_turned_into_a_copy_with_the_same_values_is_refuted_by_its_identity_relation() {
    let Some(o) = regression("defect", "withQuantity") else { return };
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().expect("a counterexample");
    assert!(c.before.contains("with result == l and result.price == l.price"), "{}", c.before);
    assert!(c.after.contains("with result.price == l.price") && !c.after.contains("result == l "), "{}", c.after);
    // Every field agrees: only the relation tells them apart.
    let fields = |t: &str| t.split(", with").next().unwrap().to_string();
    assert_eq!(fields(&c.before), fields(&c.after));
    confirmed_on_the_jvm(&o);
}

#[test]
fn a_result_of_a_class_made_by_its_constructor_is_compared_field_by_field() {
    let Some(o) = regression("after", "doubled") else { return };
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let Some(d) = regression("defect", "doubled") else { return };
    assert_eq!(d.verdict, Verdict::Violation, "{}", d.output);
    let c = d.counterexample.as_ref().expect("a counterexample");
    assert!(c.before.starts_with("Line{price=Money{cents="), "{}", c.before);
    assert_ne!(c.before, c.after);
    confirmed_on_the_jvm(&d);
}

#[test]
fn an_array_handed_back_in_place_of_a_copy_is_refuted_by_its_identity_relation() {
    let Some(o) = regression("after", "filled") else { return };
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert_eq!(o.stated.as_ref().unwrap().observations.identities, vec!["result == a".to_string()]);
    let Some(d) = regression("defect", "filled") else { return };
    assert_eq!(d.verdict, Verdict::Violation, "{}", d.output);
    let c = d.counterexample.as_ref().expect("a counterexample");
    assert!(c.before.contains("with result == a") && !c.after.contains("with result == a"), "{} / {}", c.before, c.after);
    confirmed_on_the_jvm(&d);
}

// Object parameters that may be null or one object (the rest of H2): a choice the harness makes with a flag of its
// own, in both versions alike, which the witness keeps and the JVM replays with one object or none.

#[test]
fn a_bug_only_when_two_parameters_are_one_object_is_outside_the_default_domain_and_refuted_inside_one_that_lets_them_be() {
    // Two lines of their own: the buffered move is the same.
    let Some(apart) = regression("defect", "move") else { return };
    assert_eq!(apart.verdict, Verdict::Verified, "{}", apart.output);
    assert!(!apart.domain.as_deref().unwrap().contains("the same object"), "{:?}", apart.domain);
    // Lines that may be one: a move from a line to itself, with one object, as the JVM runs it too.
    let Some(o) = regression_over("defect", "move", &[], &[("from", "to")]) else { return };
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let domain = o.domain.clone().unwrap();
    assert!(domain.ends_with("; from and to may be the same object"), "{domain}");
    let c = o.counterexample.as_ref().expect("a counterexample");
    assert!(c.input.contains("to=the same object as from"), "{}", c.input);
    assert!(c.before.contains("with from == to") && c.after.contains("with from == to"), "{} / {}", c.before, c.after);
    assert!(c.differs.iter().any(|d| d == "field:from"), "{:?}", c.differs);
    confirmed_on_the_jvm(&o);
    let to = c.call.arguments.iter().find(|a| a.name == "to").unwrap();
    assert_eq!(to.value, Some(serde_json::json!({ "same": "from" })));
    let stated = o.stated.as_ref().unwrap();
    assert_eq!(stated.domain.may_alias, vec![vec!["from".to_string(), "to".to_string()]]);
    assert!(stated.observations.identities.iter().any(|i| i == "from == to"), "{:?}", stated.observations.identities);
    // The rewrite in the other order is the same on one line too.
    let Some(ok) = regression_over("after", "move", &[], &[("from", "to")]) else { return };
    assert_eq!(ok.verdict, Verdict::Verified, "{}", ok.output);
}

#[test]
fn a_dropped_null_check_is_refuted_with_a_null_object_where_the_domain_lets_it_be_null() {
    let Some(apart) = regression("defect", "size") else { return };
    assert_eq!(apart.verdict, Verdict::Verified, "never null by default: {}", apart.output);
    let Some(o) = regression_over("defect", "size", &["l"], &[]) else { return };
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.domain.as_deref().unwrap().contains("from any arguments it accepts, or null"), "{:?}", o.domain);
    let c = o.counterexample.as_ref().expect("a counterexample");
    assert_eq!(c.input, "size(l=null)");
    assert!(c.after.contains("NullPointerException"), "{}", c.after);
    confirmed_on_the_jvm(&o);
    assert!(o.stated.as_ref().unwrap().domain.parameters[0].null);
    let Some(ok) = regression_over("after", "size", &["l"], &[]) else { return };
    assert_eq!(ok.verdict, Verdict::Verified, "{}", ok.output);
}

#[test]
fn a_choice_of_null_or_one_object_is_refused_by_name_outside_object_parameters() {
    let Some(o) = regression_over("after", "withQuantity", &[], &[("l", "quantity")]) else { return };
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap().contains("--may-alias quantity: quantity is a int, and in a regression check only an object parameter made by its constructor may be"), "{:?}", o.problem);
    let Some(n) = regression_over("after", "filled", &["a"], &[]) else { return };
    assert!(n.problem.as_deref().unwrap().contains("an array parameter may be, in a property check"), "{:?}", n.problem);
}

// H5's narrow case: the joint example's kernel (`tests/fixtures/foundations`), whose `Quote` holds a `long` before
// and a `Money` now, related by the kernel claim's correspondence.

/// The kernel of the joint example, compiled once: `before`, `after`, and each kernel defect overlaid on `after`.
fn kernel_builds() -> Option<&'static PathBuf> {
    static DIR: OnceLock<Option<PathBuf>> = OnceLock::new();
    DIR.get_or_init(|| {
        compiled()?;
        let fixture = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/foundations");
        let root = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("heap-kernel");
        let _ = std::fs::remove_dir_all(&root);
        let kernel = |dir: &Path, names: &[&str]| -> Vec<PathBuf> { names.iter().map(|n| dir.join(format!("shop/{n}.java"))).filter(|p| p.exists()).collect() };
        let mut builds = vec![("before".to_string(), kernel(&fixture.join("before"), &["Pricing", "Quote"]))];
        let after = kernel(&fixture.join("after"), &["Pricing", "Quote", "Money"]);
        builds.push(("after".into(), after.clone()));
        for defect in ["offset", "alias-to-copy", "outside-domain"] {
            let overlay = fixture.join("defects").join(defect).join("shop/Pricing.java");
            let mut files: Vec<PathBuf> = after.iter().filter(|p| !p.ends_with("Pricing.java")).cloned().collect();
            files.push(overlay);
            builds.push((defect.into(), files));
        }
        for (name, files) in builds {
            let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-d"]).arg(root.join(&name)).args(&files).status().expect("javac runs");
            assert!(status.success(), "the kernel compiles as {name}");
        }
        Some(root)
    })
    .as_ref()
}

fn kernel_claim(subject: &str, extra: &[jvmcontract::spec::Observation]) -> jvmcontract::spec::CanonicalClaim {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/foundations/golden/kernel-claim.json");
    let mut claim: jvmcontract::spec::CanonicalClaim = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    claim.contract.subject = subject.to_string();
    for o in extra {
        claim.contract.required.push(o.id());
        claim.observations.push(o.clone());
    }
    claim
}

fn kernel_check(build: &str, claim: &jvmcontract::spec::CanonicalClaim) -> Option<Result<jvmcontract::spec::Outcome, jvmcontract::spec::Unsupported>> {
    let root = kernel_builds()?;
    Some(jvmcontract::spec::heap::check(claim, &root.join("before"), &root.join(build)))
}

fn identity_result_q() -> jvmcontract::spec::Observation {
    jvmcontract::spec::Observation::Identity { left: "result".into(), right: "q".into() }
}

fn state_of(o: &jvmcontract::spec::Outcome, id: &str) -> jvmcontract::spec::ObservationState {
    o.accounting.iter().find(|a| a.observation == id).unwrap_or_else(|| panic!("{id} is accounted for: {o:?}")).state
}

#[test]
fn the_two_shapes_of_quote_are_related_by_the_correspondence_and_total_is_proved_over_them() {
    use jvmcontract::spec::{ObservationState, Verdict as V};
    let Some(r) = kernel_check("after", &kernel_claim("shop.Pricing#total", &[])) else { return };
    let o = r.expect("supported");
    assert_eq!(o.verdict, V::Verified, "{o:?}");
    assert_eq!(state_of(&o, "result"), ObservationState::Preserved);
    assert_eq!(state_of(&o, "exception"), ObservationState::Preserved);
    assert!(o.domain.starts_with("q: a Quote made by its constructor, Quote(amount: Money(cents: long), quantity: int), from any arguments it accepts; in the previous version, a Quote made by its constructor, Quote(cents: long, quantity: int), from the new q's amount.cents and quantity as the correspondence's input equations say (old.q.cents == new.q.amount.cents, old.q.quantity == new.q.quantity)"), "{}", o.domain);
    // The result handed back is compared under the same equations, and so is the parameter as left.
    let Some(r) = kernel_check("after", &kernel_claim("shop.Pricing#withQuantity", &[identity_result_q()])) else { return };
    let o = r.expect("supported");
    assert_eq!(o.verdict, V::Verified, "{o:?}");
    assert_eq!(state_of(&o, "identity:result==q"), ObservationState::Preserved);
}

#[test]
fn a_claim_whose_domain_lets_a_parameter_be_null_is_checked_over_null_too_and_a_field_path_is_not_yet() {
    use jvmcontract::spec::Verdict as V;
    let mut claim = kernel_claim("shop.Pricing#total", &[]);
    claim.domain.as_mut().expect("the kernel claim has a domain").nullable = vec!["q".into()];
    let Some(r) = kernel_check("after", &claim) else { return };
    let o = r.expect("supported");
    // Both versions throw the same NullPointerException on a null quote.
    assert_eq!(o.verdict, V::Verified, "{o:?}");
    assert!(o.domain.contains("from any arguments it accepts, or null; in the previous version"), "{}", o.domain);
    claim.domain.as_mut().unwrap().nullable = vec!["q.amount".into()];
    let Some(r) = kernel_check("after", &claim) else { return };
    let gap = r.expect_err("a field path is not made yet");
    assert!(gap.what.contains("the domain's q.amount is a field path"), "{gap:?}");
}

#[test]
fn an_offset_total_is_refuted_under_the_correspondence_by_a_recipe_of_the_new_shape() {
    use jvmcontract::spec::{ObservationState, Verdict as V};
    let Some(r) = kernel_check("offset", &kernel_claim("shop.Pricing#total", &[])) else { return };
    let o = r.expect("supported");
    assert_eq!(o.verdict, V::Refuted, "{o:?}");
    assert_eq!(state_of(&o, "result"), ObservationState::Refuted);
    assert_eq!(state_of(&o, "exception"), ObservationState::Unresolved, "a refutation proves nothing of the rest");
    assert_eq!(o.witness.as_deref(), Some("total(q=new Quote(new Money(0), 1)): before, 0; after, 1"));
}

#[test]
fn the_alias_turned_into_a_copy_is_refuted_by_result_is_q_wherever_its_copy_can_be_made() {
    use jvmcontract::spec::{ObservationState, Verdict as V};
    let Some(root) = kernel_builds() else { return };
    // The fixture's copy is made by the constructor, which rejects a quantity of 0 or less: there the defect throws
    // as well. Elsewhere only the identity relation tells the versions apart.
    let claim = kernel_claim("shop.Pricing#withQuantity", &[]);
    let mut options = jvmcontract::equivalence::Options::new(&root.join("before"), &root.join("alias-to-copy"), "shop.Pricing#withQuantity");
    options.engine = jvmcontract::Engine::Native;
    options.correspondence = claim.correspondence.clone();
    options.unchanged_unless = Some("quantity <= 0".into());
    let work = root.join("work-alias-to-copy");
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    let o = jvmcontract::equivalence::run(&options).unwrap();
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let cx = o.counterexample.as_ref().unwrap();
    assert_eq!(cx.input, "withQuantity(q=new Quote(new Money(0), 1), quantity=1)");
    assert_eq!(cx.before, "Quote{cents=0, quantity=1}, with result == q");
    assert_eq!(cx.after, "Quote{amount=Money{cents=0}, quantity=1}");
    assert_eq!(cx.differs, ["identity:result==q"], "the fields agree under the correspondence");
    confirmed_on_the_jvm(&o);
    let source = std::fs::read_to_string(o.statement.as_ref().unwrap()).unwrap();
    assert!(source.contains("before.shop.Quote a = null;"), "{source}");
    assert!(source.contains("q_before = new before.shop.Quote(q_amount_cents, q_quantity); q_after = new shop.Quote(new shop.Money(q_amount_cents), q_quantity);"), "{source}");
    assert!(source.contains("if (!(q_before.cents == q_after.amount.cents && q_before.quantity == q_after.quantity)) { return; }"), "{source}");
    let stated = o.stated.as_ref().unwrap();
    assert_eq!(stated.observations.identities, ["result == q"]);
    assert_eq!(stated.domain.input_objects, Some((1, 2)), "a Quote before, a Quote of a Money now");
    // As the claim has it, over every quantity: refuted, with the relation accounted for.
    let Some(r) = kernel_check("alias-to-copy", &kernel_claim("shop.Pricing#withQuantity", &[identity_result_q()])) else { return };
    let o = r.expect("supported");
    assert_eq!(o.verdict, V::Refuted, "{o:?}");
    assert!(o.accounting.iter().any(|a| a.observation == "identity:result==q"));
    assert_eq!(state_of(&o, "exception"), ObservationState::Refuted, "{o:?}");
}

#[test]
fn a_witness_that_differs_only_where_the_claim_does_not_look_refutes_nothing() {
    use jvmcontract::spec::{ObservationState, Verdict as V};
    let mut claim = kernel_claim("shop.Pricing#withQuantity", &[]);
    claim.contract.required = vec!["result".into()];
    claim.observations.retain(|o| o.id() == "result");
    let Some(r) = kernel_check("alias-to-copy", &claim) else { return };
    let o = r.expect("supported");
    assert_eq!(o.verdict, V::Unresolved, "{o:?}");
    assert_eq!(state_of(&o, "result"), ObservationState::Unresolved);
    assert!(o.problem.as_deref().unwrap().contains("differ only in exception"), "{o:?}");
    assert!(o.witness.is_some(), "the witness is still shown");
}

#[test]
fn what_the_correspondence_leaves_out_and_bounds_it_exceeds_are_never_proved() {
    use jvmcontract::spec::Verdict as V;
    let mut claim = kernel_claim("shop.Pricing#total", &[]);
    claim.correspondence.as_mut().unwrap().inputs.retain(|e| e.old == "old.q.quantity");
    let Some(r) = kernel_check("after", &claim) else { return };
    let gap = r.expect_err("a correspondence that leaves out a field the previous version was held to is a gap");
    assert!(gap.what.contains("q.cents is in no equation of the correspondence"), "{}", gap.what);
    let mut claim = kernel_claim("shop.Pricing#total", &[]);
    claim.correspondence = None;
    let gap = kernel_check("after", &claim).unwrap().expect_err("two shapes and no correspondence");
    assert!(gap.what.contains("relate them with a correspondence's input equations"), "{}", gap.what);
    let mut claim = kernel_claim("shop.Pricing#total", &[]);
    claim.domain.as_mut().unwrap().bounds.after.input_objects = 1;
    let o = kernel_check("after", &claim).unwrap().expect("supported");
    assert_eq!(o.verdict, V::Unresolved, "{o:?}");
    assert!(o.problem.as_deref().unwrap().contains("made of 2 objects, more than the claim's bound of 1"), "{o:?}");
}

// Object inputs in property checks (H2's rest): `jvmcontract prove` over a parameter of an application class, made
// in the harness by its constructor from symbolic arguments, which the property reads by its field paths, before
// the call under `\old`, and compares by identity; null and one object where the domain lets them be.

/// A property of `objects.Kernel#method` in the build `build`, on the own checker.
fn property_over(build: &str, method: &str, assume: Option<&str>, assert: &str, nullable: &[&str], may_alias: &[(&str, &str)]) -> Option<jvmcontract::property::Outcome> {
    property_on(jvmcontract::Engine::Native, false, build, method, assume, assert, nullable, may_alias)
}

/// [`property_over`] on the checker `engine`, `--confirm` under `auto` where `confirm`.
#[allow(clippy::too_many_arguments)]
fn property_on(engine: jvmcontract::Engine, confirm: bool, build: &str, method: &str, assume: Option<&str>, assert: &str, nullable: &[&str], may_alias: &[(&str, &str)]) -> Option<jvmcontract::property::Outcome> {
    let root = object_builds()?;
    let mut options = jvmcontract::property::Options::new(&[root.join(build)], &format!("objects.Kernel#{method}"));
    options.engine = engine;
    options.confirm = confirm;
    options.assume = assume.map(str::to_string);
    options.assert = Some(assert.to_string());
    options.nullable = nullable.iter().map(|n| n.to_string()).collect();
    options.may_alias = may_alias.iter().map(|(a, b)| (a.to_string(), b.to_string())).collect();
    let tag: String = format!("{engine:?}{confirm}{assume:?}{assert}{nullable:?}{may_alias:?}").bytes().fold(0u64, |h, b| h.wrapping_mul(31).wrapping_add(u64::from(b))).to_string();
    let work = root.join(format!("property-{build}-{method}-{tag}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    Some(jvmcontract::property::run(&options).unwrap())
}

/// A property's witness over objects is run on a JVM as well as in the interpreter: the harness on it, which makes
/// the objects from the same leaves.
fn property_confirmed_on_the_jvm(o: &jvmcontract::property::Outcome) {
    assert_eq!(o.replay.as_ref().map(|r| (r.by.as_str(), r.reproduced)), Some(("jvm", true)), "{}", o.output);
    assert!(o.output.contains("replayed in the interpreter and run on a JVM (JDK "), "{}", o.output);
}

#[test]
fn a_property_reads_an_object_parameter_by_its_field_paths_before_and_after_the_call() {
    let law = "l.quantity == \\old(l.quantity) + 1 && l.price.cents == \\old(l.price.cents)";
    let Some(o) = property_over("after", "bump", None, law, &[], &[]) else { return };
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.output.contains("on every input of constructor-made objects"), "{}", o.output);
    assert_eq!(o.domain.as_deref(), Some("l: a Line made by its constructor, Line(price: Money(cents: long), quantity: int), from any arguments it accepts"));
    let stated = o.stated.as_ref().unwrap();
    assert_eq!(stated.domain.parameters[0].kind, jvmcontract::statement::ParameterKind::Object);
    assert!(stated.assumptions.iter().any(|a| a.text.starts_with("the constructor Line(price: Money(cents: long), quantity: int) accepts the arguments of l")), "{:?}", stated.assumptions);
    let source = std::fs::read_to_string(o.statement.as_ref().unwrap()).unwrap();
    assert!(source.contains("try { l = new objects.Line(new objects.Money(l_price_cents), l_quantity); } catch (Throwable t) { return; }"), "{source}");
    // Adding two is seen in the object as the call leaves it, and refuted with a construction recipe, on the JVM too.
    let Some(bad) = property_over("defect", "bump", None, law, &[], &[]) else { return };
    assert_eq!(bad.verdict, Verdict::Violation, "{}", bad.output);
    let c = bad.counterexample.as_ref().unwrap();
    assert_eq!(c.input, "bump(l=new Line(new Money(0), 1))", "{}", bad.output);
    assert!(c.outcome.contains("leaving l=Line{price=Money{cents=0}, quantity=3}"), "{}", c.outcome);
    property_confirmed_on_the_jvm(&bad);
}

#[test]
fn a_property_compares_an_object_result_with_its_argument_by_identity_and_the_alias_to_copy_defect_fails_it() {
    let law = "result == l && result.quantity == quantity && result.price == l.price";
    let Some(o) = property_over("after", "withQuantity", None, law, &[], &[]) else { return };
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let Some(bad) = property_over("defect", "withQuantity", None, law, &[], &[]) else { return };
    assert_eq!(bad.verdict, Verdict::Violation, "{}", bad.output);
    assert_eq!(bad.counterexample.as_ref().unwrap().input, "withQuantity(l=new Line(new Money(0), 1), quantity=0)", "{}", bad.output);
    property_confirmed_on_the_jvm(&bad);
    // The copy has the same values and the same price: only its identity tells it apart.
    let Some(values) = property_over("defect", "withQuantity", None, "result.quantity == quantity && result.price == l.price", &[], &[]) else { return };
    assert_eq!(values.verdict, Verdict::Verified, "{}", values.output);
}

#[test]
fn a_property_over_an_object_that_may_be_null_is_checked_on_null_too() {
    let law = "result == (l == null ? 0 : l.quantity)";
    let Some(o) = property_over("after", "size", None, law, &["l"], &[]) else { return };
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.domain.as_deref().unwrap().ends_with("from any arguments it accepts, or null"), "{:?}", o.domain);
    assert!(o.stated.as_ref().unwrap().domain.parameters[0].null);
    let Some(bad) = property_over("defect", "size", None, law, &["l"], &[]) else { return };
    assert_eq!(bad.verdict, Verdict::Violation, "{}", bad.output);
    let c = bad.counterexample.as_ref().unwrap();
    assert_eq!(c.input, "size(l=null)");
    assert!(c.outcome.contains("NullPointerException"), "{}", c.outcome);
    assert_eq!(c.call.arguments[0].value, Some(serde_json::Value::Null), "{:?}", c.call);
    property_confirmed_on_the_jvm(&bad);
    // Not null by default; and an input on which the assumption throws (a path through null) is outside it.
    let Some(apart) = property_over("defect", "size", None, law, &[], &[]) else { return };
    assert_eq!(apart.verdict, Verdict::Verified, "{}", apart.output);
    let Some(assumed) = property_over("defect", "size", Some("l.quantity > 1"), "result == l.quantity", &["l"], &[]) else { return };
    assert_eq!(assumed.verdict, Verdict::Verified, "{}", assumed.output);
    assert!(assumed.vacuous.is_none(), "{}", assumed.output);
}

#[test]
fn a_property_over_two_objects_that_may_be_one_is_refuted_with_one_object_where_the_bug_needs_it() {
    let law = "from == to ? from.quantity == \\old(from.quantity) : from.quantity == \\old(from.quantity) - 1 && to.quantity == \\old(to.quantity) + 1";
    let Some(o) = property_over("after", "move", None, law, &[], &[("from", "to")]) else { return };
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.domain.as_deref().unwrap().ends_with("; from and to may be the same object"), "{:?}", o.domain);
    let Some(apart) = property_over("defect", "move", None, law, &[], &[]) else { return };
    assert_eq!(apart.verdict, Verdict::Verified, "two lines of their own: {}", apart.output);
    let Some(bad) = property_over("defect", "move", None, law, &[], &[("from", "to")]) else { return };
    assert_eq!(bad.verdict, Verdict::Violation, "{}", bad.output);
    let c = bad.counterexample.as_ref().unwrap();
    assert_eq!(c.input, "move(from=new Line(new Money(0), 1), to=the same object as from)", "{}", bad.output);
    assert_eq!(c.call.arguments[1].value, Some(serde_json::json!({"same": "from"})), "{:?}", c.call);
    property_confirmed_on_the_jvm(&bad);
}

#[test]
fn a_property_wrong_only_where_the_constructor_refuses_holds_within_the_constructor_made_claim() {
    let Some(o) = property_over("after", "checked", None, "result == l.price.cents * l.quantity", &[], &[]) else { return };
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.output.contains("on every input of constructor-made objects"), "{}", o.output);
}

#[test]
fn a_property_over_an_object_outside_the_supported_kinds_or_written_wrong_is_refused_by_name() {
    let Some(o) = property_over("after", "tagged", None, "result == t.n", &[], &[]) else { return };
    assert_eq!(o.verdict, Verdict::Unverifiable);
    assert!(o.problem.as_deref().unwrap().contains("the field tag of objects.Tagged has type java.lang.String"), "{:?}", o.problem);
    let wrong = [
        ("\\old(l) == l", "\\old(l) is an object"),
        ("l.price == l", "incomparable types"),
        ("l.amount == 0", "objects.Line has no field amount; its fields are price, quantity"),
        ("l.price > 0", "l.price is an object"),
    ];
    for (law, words) in wrong {
        let Some(o) = property_over("after", "bump", None, law, &[], &[]) else { return };
        assert_eq!(o.verdict, Verdict::Unverifiable, "{law}");
        assert!(o.problem.as_deref().unwrap().contains(words), "{law}: {:?}", o.problem);
    }
    let Some(o) = property_over("after", "withQuantity", None, "true", &["quantity"], &[]) else { return };
    assert!(o.problem.as_deref().unwrap().contains("--nullable quantity: quantity is a int, and only an array parameter or an object made by its constructor may be null"), "{:?}", o.problem);
}

/// The object properties above under JBMC, which checks the same harness (its inputs the leaves and the choices'
/// flags, all primitive), and under `auto --confirm`, where JBMC proves again what the own checker proved: each
/// verdict as the own checker's, each violation's witness run on a JVM. A pipeline job
/// (`cargo test --release --test heap -- --ignored`).
#[test]
#[ignore = "runs JBMC on the object properties: a pipeline job"]
fn the_object_properties_have_the_same_verdicts_under_jbmc_and_auto_confirm() {
    if Command::new("jbmc").arg("--version").output().is_err() {
        return;
    }
    let bump = "l.quantity == \\old(l.quantity) + 1 && l.price.cents == \\old(l.price.cents)";
    let with = "result == l && result.quantity == quantity && result.price == l.price";
    let size = "result == (l == null ? 0 : l.quantity)";
    let moved = "from == to ? from.quantity == \\old(from.quantity) : from.quantity == \\old(from.quantity) - 1 && to.quantity == \\old(to.quantity) + 1";
    let cases: [(&str, &str, &str, &[&str], &[(&str, &str)], Verdict); 8] = [
        ("after", "bump", bump, &[], &[], Verdict::Verified),
        ("defect", "bump", bump, &[], &[], Verdict::Violation),
        ("after", "withQuantity", with, &[], &[], Verdict::Verified),
        ("defect", "withQuantity", with, &[], &[], Verdict::Violation),
        ("after", "size", size, &["l"], &[], Verdict::Verified),
        ("defect", "size", size, &["l"], &[], Verdict::Violation),
        ("after", "move", moved, &[], &[("from", "to")], Verdict::Verified),
        ("defect", "move", moved, &[], &[("from", "to")], Verdict::Violation),
    ];
    let mut failures = Vec::new();
    for (engine, confirm) in [(jvmcontract::Engine::Jbmc, false), (jvmcontract::Engine::Auto, true)] {
        for (build, method, law, nullable, may_alias, expected) in &cases {
            let Some(o) = property_on(engine, confirm, build, method, None, law, nullable, may_alias) else { return };
            let jvm = o.replay.as_ref().is_some_and(|r| r.by == "jvm" && r.reproduced);
            if o.verdict != *expected || (*expected == Verdict::Violation && !jvm) {
                failures.push(format!("{engine:?} confirm={confirm} {build} {method}: {:?} (expected {expected:?}, on a JVM {jvm})\n{}", o.verdict, o.output));
            }
        }
    }
    assert!(failures.is_empty(), "{}", failures.join("\n\n"));
}
