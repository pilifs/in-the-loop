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
    public static long price(Line l) { return l.price.cents() * l.quantity; }
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
    // The amount became a value object.
    public static Money price(Line l) { return new Money(l.quantity * l.price.cents()); }
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
    // A cent too much in the value object.
    public static Money price(Line l) { return new Money(l.price.cents() * l.quantity + 1); }
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
    // The object and each path it differs in, so that a claim requiring the path is refuted in it (H5's rest).
    assert_eq!(c.differs, ["field:l", "field:l.quantity"], "{}", o.output);
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
/// The joint example's new `Pricing` with another `withQuantity` in place of `WITH_QUANTITY`.
const PRICING_OF: &str = r#"package shop;
public final class Pricing {
    private Pricing() {}
    static long discount(long gross, int quantity) {
        if (quantity < 10) return 0;
        return gross / 10;
    }
    public static long total(Quote q) {
        long gross = q.amount.cents() * q.quantity;
        return gross - discount(gross, q.quantity);
    }
    public static Quote withQuantity(Quote q, int quantity) {
WITH_QUANTITY
    }
}
"#;

/// The alias turned into a copy on purpose: the quote changed in place, and a copy with the same values handed
/// back, made past the constructor's check so that it never throws where the previous version doesn't.
const PRICING_COPIED: &str = "        q.quantity = quantity;\n        Quote copy = new Quote(q.amount, 1);\n        copy.quantity = quantity;\n        return copy;";

/// As [`PRICING_COPIED`], but the quote itself handed back where its quantity is already the one asked for.
const PRICING_SOMETIMES: &str = "        if (q.quantity == quantity) return q;\n        q.quantity = quantity;\n        Quote copy = new Quote(q.amount, 1);\n        copy.quantity = quantity;\n        return copy;";

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
        // Two more of the new shape's withQuantity, for output relations for an identity relation (H5's rest).
        for (name, body) in [("copied", PRICING_COPIED), ("sometimes-copied", PRICING_SOMETIMES)] {
            let overlay = root.join(format!("src-{name}/shop/Pricing.java"));
            std::fs::create_dir_all(overlay.parent().unwrap()).unwrap();
            std::fs::write(&overlay, PRICING_OF.replace("WITH_QUANTITY", body)).unwrap();
            let mut files: Vec<PathBuf> = after.iter().filter(|p| !p.ends_with("Pricing.java")).cloned().collect();
            files.push(overlay);
            builds.push((name.into(), files));
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

// Output relations (H5's rest): a correspondence's relation for the result, in place of equality, over a result
// that changed type (a value object in place of a primitive) or shape (an object read by its field paths), and
// how a claim accounts for a required observation compared under one.

fn correspondence(inputs: &[(&str, &str)], result: Option<&str>) -> jvmcontract::spec::Correspondence {
    jvmcontract::spec::Correspondence {
        inputs: inputs.iter().map(|(o, n)| jvmcontract::spec::Equation { old: (*o).into(), new: (*n).into() }).collect(),
        outputs: result.map(|h| jvmcontract::spec::Relation { observation: "result".into(), holds: h.into() }).into_iter().collect(),
    }
}

/// A regression check of `pkg.Class#method` between `before` and `after` under the root `root`, on the own
/// checker, under `correspondence`.
fn related(root: &Path, after: &str, target: &str, c: jvmcontract::spec::Correspondence, tag: &str) -> jvmcontract::equivalence::Outcome {
    related_on(jvmcontract::Engine::Native, false, root, after, target, c, tag)
}

/// [`related`] on the engine `engine`, under `--confirm` if `confirm`.
fn related_on(engine: jvmcontract::Engine, confirm: bool, root: &Path, after: &str, target: &str, c: jvmcontract::spec::Correspondence, tag: &str) -> jvmcontract::equivalence::Outcome {
    let mut options = jvmcontract::equivalence::Options::new(&root.join("before"), &root.join(after), target);
    options.engine = engine;
    options.confirm = confirm;
    options.correspondence = Some(c);
    let work = root.join(format!("work-related-{after}-{tag}-{engine:?}-{confirm}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    jvmcontract::equivalence::run(&options).unwrap()
}

#[test]
fn a_result_that_became_a_value_object_is_related_by_the_correspondences_output_relation() {
    let Some(root) = object_builds() else { return };
    let relation = correspondence(&[], Some("old.result == new.result.cents"));
    let o = related(root, "after", "objects.Kernel#price", relation.clone(), "price");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.output.contains("the results related by old.result == new.result.cents"), "{}", o.output);
    assert_eq!(o.relation.as_deref(), Some("old.result == new.result.cents"));
    // Without it the two return types are refused, as they were.
    let o = regression("after", "price").unwrap();
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap().contains("say how the results are related"), "{}", o.output);
    // A cent too much in the value object breaks it, on a witness the JVM runs too.
    let o = related(root, "defect", "objects.Kernel#price", relation, "price");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let cx = o.counterexample.as_ref().unwrap();
    assert_eq!(cx.input, "price(l=new Line(new Money(0), 1))");
    assert_eq!((cx.before.as_str(), cx.after.as_str()), ("0", "Money[cents=1]"));
    assert_eq!(cx.differs, ["result"]);
    confirmed_on_the_jvm(&o);
    // Refused by name: a relation for an identity relation the check does not observe.
    // A relation for a field of l, of the same shape in both versions, is taken beside it (H5's rest).
    let mut beside = correspondence(&[], Some("old.result == new.result.cents"));
    beside.outputs.push(jvmcontract::spec::Relation { observation: "field:l.quantity".into(), holds: "old.l.quantity == new.l.quantity".into() });
    let o = related(root, "after", "objects.Kernel#price", beside, "beside");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let mut gap = correspondence(&[], Some("old.result == new.result.cents"));
    gap.outputs.push(jvmcontract::spec::Relation { observation: "identity:result==l".into(), holds: "true".into() });
    let o = related(root, "after", "objects.Kernel#price", gap, "gap-identity");
    assert!(o.problem.as_deref().unwrap().contains("names result == l, which is not an identity relation the check observes (none)"), "{}", o.output);
}

#[test]
fn an_object_result_of_another_shape_is_related_by_its_field_paths_and_identity_is_still_compared() {
    let Some(root) = kernel_builds() else { return };
    let inputs = [("old.q.cents", "new.q.amount.cents"), ("old.q.quantity", "new.q.quantity")];
    let relation = "old.result.cents == new.result.amount.cents && old.result.quantity == new.result.quantity";
    let o = related(root, "after", "shop.Pricing#withQuantity", correspondence(&inputs, Some(relation)), "fields");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert_eq!(o.stated.as_ref().unwrap().observations.identities, ["result == q"], "identity relations are observed under a relation too");
    let source = std::fs::read_to_string(o.statement.as_ref().unwrap()).unwrap();
    assert!(source.contains("before.shop.Quote previous = a; shop.Quote result = b;"), "{source}");
    // The relation holds of the alias-to-copy defect's copy, and result == q still tells the versions apart.
    let o = related(root, "alias-to-copy", "shop.Pricing#withQuantity", correspondence(&inputs, Some(relation)), "fields");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let cx = o.counterexample.as_ref().unwrap();
    // The copy's constructor rejects a quantity of 0, so a witness may differ in the exception too, never in the
    // result, whose two shapes the relation relates.
    assert!(cx.differs.iter().any(|d| d == "identity:result==q") && !cx.differs.iter().any(|d| d == "result"), "{:?}", cx.differs);
    confirmed_on_the_jvm(&o);
    // A relation the versions don't satisfy is refuted, the harness deciding it in the interpreter and on a JVM.
    let wrong = "old.result.quantity == new.result.quantity + 1";
    let o = related(root, "after", "shop.Pricing#withQuantity", correspondence(&inputs, Some(wrong)), "wrong");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let cx = o.counterexample.as_ref().unwrap();
    assert_eq!(cx.differs, ["result"], "{}", o.output);
    assert!(o.output.contains(&format!("the results are not related by {wrong}")), "{}", o.output);
    confirmed_on_the_jvm(&o);
    // A path the result doesn't have is named.
    let o = related(root, "after", "shop.Pricing#withQuantity", correspondence(&inputs, Some("old.result.amount == new.result.quantity")), "unknown");
    assert!(o.problem.as_deref().unwrap().contains("Quote has no field amount"), "{}", o.output);
}

#[test]
fn a_required_observation_under_an_output_relation_is_unresolved_until_a_person_approves_the_change() {
    use jvmcontract::spec::{ApprovedChange, ObservationState, Verdict as V};
    // `true` relates any two totals: it would hide the offset defect, and the claim says it can't be the contract.
    let mut claim = kernel_claim("shop.Pricing#total", &[]);
    claim.correspondence.as_mut().unwrap().outputs.push(jvmcontract::spec::Relation { observation: "result".into(), holds: "true".into() });
    let Some(r) = kernel_check("offset", &claim) else { return };
    let o = r.expect("supported");
    assert_eq!(o.verdict, V::Unresolved, "{o:?}");
    assert_eq!(state_of(&o, "result"), ObservationState::Unresolved);
    assert_eq!(state_of(&o, "exception"), ObservationState::Preserved);
    assert!(o.problem.as_deref().unwrap().contains("compares result in place of equality, which the preservation contract requires and no person approved as changed"), "{o:?}");
    // Approved, the relation is the claim: changed with approval, and the offset is then what it allows.
    claim.contract.approved_changes.push(ApprovedChange { observation: "result".into(), text: "any total".into() });
    let o = kernel_check("offset", &claim).unwrap().expect("supported");
    assert_eq!(o.verdict, V::Verified, "{o:?}");
    assert_eq!(state_of(&o, "result"), ObservationState::ChangedWithApproval);
    // A relation the versions don't satisfy refutes nothing the contract requires until it is approved.
    let mut claim = kernel_claim("shop.Pricing#total", &[]);
    claim.correspondence.as_mut().unwrap().outputs.push(jvmcontract::spec::Relation { observation: "result".into(), holds: "old.result == new.result + 1".into() });
    let o = kernel_check("after", &claim).unwrap().expect("supported");
    assert_eq!(o.verdict, V::Unresolved, "{o:?}");
    assert_eq!(state_of(&o, "result"), ObservationState::Unresolved);
    assert!(o.problem.as_deref().unwrap().contains("differ under the correspondence's output relation for result"), "{o:?}");
}

#[test]
fn the_equivalence_command_takes_a_correspondence_file_in_the_irs_form() {
    let Some(root) = kernel_builds() else { return };
    let golden = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/foundations/golden/correspondence.json");
    let run = |file: &Path, after: &str| Command::new(env!("CARGO_BIN_EXE_jvmcontract")).arg("equivalence").arg("--before").arg(root.join("before")).arg("--after").arg(root.join(after)).args(["--target", "shop.Pricing#total", "--engine", "native", "--correspondence"]).arg(file).output().unwrap();
    let out = run(&golden, "after");
    let text = String::from_utf8_lossy(&out.stdout);
    assert_eq!(out.status.code(), Some(0), "{text}{}", String::from_utf8_lossy(&out.stderr));
    assert!(text.contains("as the correspondence's input equations say"), "{text}");
    let out = run(&golden, "offset");
    assert_eq!(out.status.code(), Some(1), "{}", String::from_utf8_lossy(&out.stdout));
    let bad = root.join("not-a-correspondence.json");
    std::fs::write(&bad, "{\"inputs\": 3}").unwrap();
    let out = run(&bad, "after");
    assert!(String::from_utf8_lossy(&out.stderr).contains("not a correspondence"), "{}", String::from_utf8_lossy(&out.stderr));
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

/// The output relations under JBMC and under `auto --confirm`: the same verdicts as on the own checker, each
/// refutation's witness run on a JVM, since JBMC checks the same harness (the relation read through the results'
/// fields in its bytecode). A pipeline job (`cargo test --release --test heap -- --ignored output_relations`).
#[test]
#[ignore = "runs JBMC on the output relations: a pipeline job"]
fn the_output_relations_have_the_same_verdicts_under_jbmc_and_auto_confirm() {
    if Command::new("jbmc").arg("--version").output().is_err() {
        return;
    }
    let (Some(objects), Some(kernel)) = (object_builds(), kernel_builds()) else { return };
    let inputs = [("old.q.cents", "new.q.amount.cents"), ("old.q.quantity", "new.q.quantity")];
    let fields = "old.result.cents == new.result.amount.cents && old.result.quantity == new.result.quantity";
    let wrong = "old.result.quantity == new.result.quantity + 1";
    let cases: [(&Path, &str, &str, jvmcontract::spec::Correspondence, Verdict); 5] = [
        (objects, "after", "objects.Kernel#price", correspondence(&[], Some("old.result == new.result.cents")), Verdict::Verified),
        (objects, "defect", "objects.Kernel#price", correspondence(&[], Some("old.result == new.result.cents")), Verdict::Violation),
        (kernel, "after", "shop.Pricing#withQuantity", correspondence(&inputs, Some(fields)), Verdict::Verified),
        (kernel, "alias-to-copy", "shop.Pricing#withQuantity", correspondence(&inputs, Some(fields)), Verdict::Violation),
        (kernel, "after", "shop.Pricing#withQuantity", correspondence(&inputs, Some(wrong)), Verdict::Violation),
    ];
    let mut failures = Vec::new();
    for (engine, confirm) in [(jvmcontract::Engine::Jbmc, false), (jvmcontract::Engine::Auto, true)] {
        for (i, (root, build, target, c, expected)) in cases.iter().enumerate() {
            let o = related_on(engine, confirm, root, build, target, c.clone(), &format!("case{i}"));
            let jvm = o.counterexample.as_ref().is_some_and(|cx| cx.jvm.is_some());
            if o.verdict != *expected || (*expected == Verdict::Violation && !jvm) {
                failures.push(format!("{engine:?} confirm={confirm} {build} {target}: {:?} (expected {expected:?}, on a JVM {jvm})\n{}", o.verdict, o.output));
            }
        }
    }
    assert!(failures.is_empty(), "{}", failures.join("\n\n"));
}

// Input equations that compute (H5's rest): the previous version's field given by an expression over the new
// version's leaves, `old.p.cents == new.p.dollars * 100 + new.p.cents`, made into the previous object before the
// call and compared after it; refused by a claim whose preservation contract anchors the input.

const PRICE_BEFORE: &str = r#"package prices;
public final class Price {
    long cents;
    public Price(long cents) {
        if (cents < 0) throw new IllegalArgumentException();
        this.cents = cents;
    }
}
"#;

const PRICE_AFTER: &str = r#"package prices;
public final class Price {
    long dollars;
    int cents;
    public Price(long dollars, int cents) {
        if (dollars < 0 || cents < 0 || cents >= 100) throw new IllegalArgumentException();
        this.dollars = dollars;
        this.cents = cents;
    }
}
"#;

const PRICES_BEFORE: &str = r#"package prices;
public final class Prices {
    public static long total(Price p, int n) { return p.cents * n; }
    public static Price doubled(Price p) { return new Price(p.cents * 2); }
    public static void raise(Price p, int by) { if (by > 0) p.cents += by; }
}
"#;

const PRICES_AFTER: &str = r#"package prices;
public final class Prices {
    public static long total(Price p, int n) { return (p.dollars * 100 + p.cents) * n; }
    public static Price doubled(Price p) { long c = (p.dollars * 100 + p.cents) * 2; return new Price(c / 100, (int) (c % 100)); }
    public static void raise(Price p, int by) {
        if (by > 0) { long c = p.dollars * 100 + p.cents + by; p.dollars = c / 100; p.cents = (int) (c % 100); }
    }
}
"#;

const PRICES_DEFECT: &str = r#"package prices;
public final class Prices {
    // A cent too much on each item.
    public static long total(Price p, int n) { return (p.dollars * 100 + p.cents + 1) * n; }
    public static Price doubled(Price p) { long c = (p.dollars * 100 + p.cents) * 2; return new Price(c / 100, (int) (c % 100)); }
    // The carry into the dollars dropped: seen only in the price as the call leaves it.
    public static void raise(Price p, int by) {
        if (by > 0) { long c = p.dollars * 100 + p.cents + by; p.cents = (int) (c % 100); }
    }
}
"#;

const PRICES_ROUNDED: &str = r#"package prices;
public final class Prices {
    public static long total(Price p, int n) { return (p.dollars * 100 + p.cents) * n; }
    public static Price doubled(Price p) { long c = (p.dollars * 100 + p.cents) * 2; return new Price(c / 100, (int) (c % 100)); }
    // Raised, then rounded up to whole dollars: a change in what the price holds after the call.
    public static void raise(Price p, int by) {
        if (by > 0) { long c = p.dollars * 100 + p.cents + by; p.dollars = c % 100 > 0 ? c / 100 + 1 : c / 100; p.cents = 0; }
    }
}
"#;

/// The price kernel's builds, compiled once: `before` (`Price(long cents)`), and `after`, `defect` and `rounded`
/// (`Price(long dollars, int cents)`).
fn price_builds() -> Option<&'static PathBuf> {
    static DIR: OnceLock<Option<PathBuf>> = OnceLock::new();
    DIR.get_or_init(|| {
        compiled()?;
        let root = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("heap-prices");
        let _ = std::fs::remove_dir_all(&root);
        for (build, price, prices) in [("before", PRICE_BEFORE, PRICES_BEFORE), ("after", PRICE_AFTER, PRICES_AFTER), ("defect", PRICE_AFTER, PRICES_DEFECT), ("rounded", PRICE_AFTER, PRICES_ROUNDED)] {
            let src = root.join(format!("{build}-src/prices"));
            std::fs::create_dir_all(&src).unwrap();
            std::fs::write(src.join("Price.java"), price).unwrap();
            std::fs::write(src.join("Prices.java"), prices).unwrap();
            let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-d"]).arg(root.join(build)).arg(src.join("Price.java")).arg(src.join("Prices.java")).status().expect("javac runs");
            assert!(status.success(), "the price kernel compiles");
        }
        Some(root)
    })
    .as_ref()
}

fn dollars_and_cents() -> jvmcontract::spec::Correspondence {
    correspondence(&[("old.p.cents", "new.p.dollars * 100 + new.p.cents")], None)
}

/// The kernel claim made over the price kernel: `subject`, with `p` anchored (identity) and `correspondence`.
fn price_claim(subject: &str, c: jvmcontract::spec::Correspondence) -> jvmcontract::spec::CanonicalClaim {
    use jvmcontract::spec::{Derivation, ExternalInput};
    let mut claim = kernel_claim(subject, &[]);
    claim.contract.inputs = vec![ExternalInput { name: "p".into(), ty: "prices.Price".into(), derivation: Derivation::Identity }, ExternalInput { name: "n".into(), ty: "int".into(), derivation: Derivation::Identity }];
    let domain = claim.domain.as_mut().unwrap();
    domain.classes = vec!["prices.Price".into()];
    domain.bounds.after.input_objects = 1;
    claim.correspondence = Some(c);
    claim
}

#[test]
fn a_previous_field_an_expression_gives_from_the_new_leaves_relates_two_shapes_of_a_price() {
    let Some(root) = price_builds() else { return };
    let o = related(root, "after", "prices.Prices#total", dollars_and_cents(), "total");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let domain = o.domain.as_deref().unwrap_or_default();
    assert!(domain.contains("in the previous version, a Price made by its constructor, Price(cents: long), from the new p's dollars * 100 + cents as the correspondence's input equations say (old.p.cents == new.p.dollars * 100 + new.p.cents)"), "{domain}");
    let source = std::fs::read_to_string(o.statement.as_ref().unwrap()).unwrap();
    assert!(source.contains("p_before = new before.prices.Price((long) (p_dollars * 100 + p_cents));"), "{source}");
    assert!(source.contains("if (!(p_before.cents == (p_after.dollars * 100 + p_after.cents))) { return; }"), "{source}");
    // A result of the same pair of classes is compared under the equation, and so is the parameter as left.
    for method in ["doubled", "raise"] {
        let o = related(root, "after", &format!("prices.Prices#{method}"), dollars_and_cents(), method);
        assert_eq!(o.verdict, Verdict::Verified, "{method}: {}", o.output);
    }
    // A cent too much is refuted, the previous object made from the witness's leaves, on a JVM too.
    let o = related(root, "defect", "prices.Prices#total", dollars_and_cents(), "total");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let cx = o.counterexample.as_ref().unwrap();
    assert!(cx.input.starts_with("total(p=new Price("), "{}", cx.input);
    assert_eq!(cx.differs, ["result"], "{}", o.output);
    confirmed_on_the_jvm(&o);
    // A carry dropped is seen in the price as the call leaves it, through the equation.
    let o = related(root, "defect", "prices.Prices#raise", dollars_and_cents(), "raise");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let cx = o.counterexample.as_ref().unwrap();
    assert_eq!(cx.differs, ["field:p", "field:p.cents"], "{}", o.output);
    // The new version's price as left reads, through the equation, as it was made: only the previous one moved.
    assert!(cx.before.starts_with("void, leaving p=Price{cents=") && cx.after == "void", "{} / {}", cx.before, cx.after);
    confirmed_on_the_jvm(&o);
}

#[test]
fn an_offset_in_a_computed_equation_hides_a_changed_total_and_a_claim_that_anchors_the_input_refuses_it() {
    use jvmcontract::spec::{Derivation, ObservationState, Verdict as V};
    let Some(root) = price_builds() else { return };
    // The model case: an equation one cent off makes the defect's totals agree. Stated by hand with no contract, it
    // is the user's, and the check proves what it was given.
    let offset = correspondence(&[("old.p.cents", "new.p.dollars * 100 + new.p.cents + 1")], None);
    let o = related(root, "defect", "prices.Prices#total", offset.clone(), "offset");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    // A claim whose contract anchors p refuses it by name: both versions receive the same p, and an equation that
    // computes may change what it means. So is the right equation, which the tool can't tell from the offset.
    let check = |build: &str, claim: &jvmcontract::spec::CanonicalClaim| jvmcontract::spec::heap::check(claim, &root.join("before"), &root.join(build));
    for c in [offset.clone(), dollars_and_cents()] {
        let gap = check("defect", &price_claim("prices.Prices#total", c)).expect_err("an anchored input");
        assert!(gap.what.contains("the preservation contract anchors p (its derivation is identity)"), "{gap:?}");
    }
    // A derivation a person stated has it: then it is theirs. The right one refutes the defect and proves the
    // rewrite; the offset, stated, is what the check proves the defect against, and a stated derivation that says
    // something else refuses the equation.
    let stated = |c: jvmcontract::spec::Correspondence, expression: &str| {
        let mut claim = price_claim("prices.Prices#total", c);
        claim.contract.inputs[0].derivation = Derivation::Stated { expression: expression.into() };
        claim
    };
    let right = stated(dollars_and_cents(), "old.p.cents == new.p.dollars * 100 + new.p.cents");
    let o = check("defect", &right).expect("stated by a person");
    assert_eq!(o.verdict, V::Refuted, "{o:?}");
    assert_eq!(state_of(&o, "result"), ObservationState::Refuted);
    let o = check("after", &right).expect("stated by a person");
    assert_eq!(o.verdict, V::Verified, "{o:?}");
    assert_eq!(state_of(&o, "result"), ObservationState::Preserved);
    let o = check("defect", &stated(offset.clone(), "old.p.cents == new.p.dollars * 100 + new.p.cents + 1")).expect("stated by a person");
    assert_eq!(o.verdict, V::Verified, "{o:?}");
    let gap = check("defect", &stated(offset, "old.p.cents == new.p.dollars * 100 + new.p.cents")).expect_err("not what the person stated");
    assert!(gap.what.contains("does not say"), "{gap:?}");
}

// Output relations for a parameter's field as the call leaves it (H5's rest): compared in place of the input
// equation about its path, which still makes the previous object, and accounted for as the result's are.

/// Within a dollar above: `raise` that rounds up to whole dollars, as the price kernel's `rounded` build does.
const ROUNDED_UP: &str = "new.p.dollars * 100 + new.p.cents - old.p.cents >= 0 && new.p.dollars * 100 + new.p.cents - old.p.cents < 100";

fn rounded_up() -> jvmcontract::spec::Correspondence {
    let mut c = dollars_and_cents();
    c.outputs.push(jvmcontract::spec::Relation { observation: "field:p.cents".into(), holds: ROUNDED_UP.into() });
    c
}

#[test]
fn an_output_relation_for_a_parameters_field_compares_it_as_the_call_leaves_it_in_place_of_the_equation() {
    let Some(root) = price_builds() else { return };
    // Under the equation alone, rounding up is a change in the price as left.
    let o = related(root, "rounded", "prices.Prices#raise", dollars_and_cents(), "raise-equation");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert_eq!(o.counterexample.as_ref().unwrap().differs, ["field:p", "field:p.cents"], "{}", o.output);
    // Under the relation for p.cents it is what the relation allows; so is the exact rewrite.
    let o = related(root, "rounded", "prices.Prices#raise", rounded_up(), "raise-relation");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().unwrap();
    assert_eq!(stated.observations.objects, [format!("p: under the correspondence; p.cents under the output relation {ROUNDED_UP}")]);
    let domain = o.domain.as_deref().unwrap_or_default();
    assert!(domain.contains("as the correspondence's input equations say (old.p.cents == new.p.dollars * 100 + new.p.cents)"), "the equation still makes the previous object: {domain}");
    let source = std::fs::read_to_string(o.statement.as_ref().unwrap()).unwrap();
    assert!(source.contains("if (!(p_before.cents == (p_after.dollars * 100 + p_after.cents))) { return; }"), "assumed of the objects as made: {source}");
    assert!(source.contains("(true) && (p_after.dollars * 100 + p_after.cents - p_before.cents >= 0 && p_after.dollars * 100 + p_after.cents - p_before.cents < 100)"), "compared as left: {source}");
    let o = related(root, "after", "prices.Prices#raise", rounded_up(), "raise-relation");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    // The carry dropped breaks it: refuted in the relation's observation, on a JVM too.
    let o = related(root, "defect", "prices.Prices#raise", rounded_up(), "raise-relation");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let cx = o.counterexample.as_ref().unwrap();
    assert_eq!(cx.differs, ["field:p.cents"], "{}", o.output);
    assert!(o.output.contains(&format!("p.cents as the calls leave it is not related by {ROUNDED_UP}")), "{}", o.output);
    confirmed_on_the_jvm(&o);
    // A relation whose path the previous version doesn't have is named.
    let mut c = dollars_and_cents();
    c.outputs.push(jvmcontract::spec::Relation { observation: "field:p.dollars".into(), holds: "true".into() });
    let o = related(root, "rounded", "prices.Prices#raise", c, "raise-unknown");
    assert!(o.problem.as_deref().unwrap().contains("names dollars, which is not a field path of the previous version's Price"), "{}", o.output);
}

#[test]
fn a_required_field_under_an_output_relation_is_unresolved_until_approved_and_then_changed_with_approval_or_refuted() {
    use jvmcontract::spec::{ApprovedChange, Derivation, Observation, ObservationState, Verdict as V};
    let Some(root) = price_builds() else { return };
    let claim_of = |c: jvmcontract::spec::Correspondence| {
        let mut claim = price_claim("prices.Prices#raise", c);
        claim.contract.inputs[0].derivation = Derivation::Stated { expression: "old.p.cents == new.p.dollars * 100 + new.p.cents".into() };
        let field = Observation::FieldPath { path: "p.cents".into() };
        claim.contract.required.push(field.id());
        claim.observations.push(field);
        claim
    };
    let check = |build: &str, claim: &jvmcontract::spec::CanonicalClaim| jvmcontract::spec::heap::check(claim, &root.join("before"), &root.join(build)).expect("supported");
    // Without the relation, rounding up is refuted in the price as left.
    let o = check("rounded", &claim_of(dollars_and_cents()));
    assert_eq!(o.verdict, V::Refuted, "{o:?}");
    assert_eq!(state_of(&o, "field:p.cents"), ObservationState::Refuted, "{o:?}");
    // Under the relation, the contract still requires equality: unresolved, never verified, until a person approves.
    let mut claim = claim_of(rounded_up());
    let o = check("rounded", &claim);
    assert_eq!(o.verdict, V::Unresolved, "{o:?}");
    assert_eq!(state_of(&o, "field:p.cents"), ObservationState::Unresolved);
    assert_eq!(state_of(&o, "result"), ObservationState::Preserved);
    assert!(o.problem.as_deref().unwrap().contains("compares field:p.cents in place of equality"), "{o:?}");
    // `true` would hide the dropped carry: it too stays unresolved.
    let mut anything = claim_of(dollars_and_cents());
    anything.correspondence.as_mut().unwrap().outputs.push(jvmcontract::spec::Relation { observation: "field:p.cents".into(), holds: "true".into() });
    let o = check("defect", &anything);
    assert_eq!(o.verdict, V::Unresolved, "{o:?}");
    assert_eq!(state_of(&o, "field:p.cents"), ObservationState::Unresolved);
    // Approved, by its path or the object's: changed with approval where it holds, refuted where it doesn't.
    for approved in ["field:p.cents", "field:p"] {
        claim.contract.approved_changes = vec![ApprovedChange { observation: approved.into(), text: "rounded up to whole dollars".into() }];
        let o = check("rounded", &claim);
        assert_eq!(o.verdict, V::Verified, "{approved}: {o:?}");
        assert_eq!(state_of(&o, "field:p.cents"), ObservationState::ChangedWithApproval);
        assert_eq!(state_of(&o, "exception"), ObservationState::Preserved);
    }
    let o = check("defect", &claim);
    assert_eq!(o.verdict, V::Refuted, "{o:?}");
    assert_eq!(state_of(&o, "field:p.cents"), ObservationState::Refuted);
    // An approval of another path approves nothing here.
    claim.contract.approved_changes = vec![ApprovedChange { observation: "field:p.dollars".into(), text: "elsewhere".into() }];
    assert_eq!(check("rounded", &claim).verdict, V::Unresolved);
}

/// The output relations for a parameter's field under JBMC and under `auto --confirm`: the same verdicts as on the
/// own checker, each refutation's witness run on a JVM, since JBMC checks the same harness (the relation compared in
/// its bytecode). A pipeline job (`cargo test --release --test heap -- --ignored field_relations`).
#[test]
#[ignore = "runs JBMC on the field relations: a pipeline job"]
fn the_field_relations_have_the_same_verdicts_under_jbmc_and_auto_confirm() {
    if Command::new("jbmc").arg("--version").output().is_err() {
        return;
    }
    let Some(root) = price_builds() else { return };
    let cases = [("rounded", false, Verdict::Violation), ("rounded", true, Verdict::Verified), ("after", true, Verdict::Verified), ("defect", true, Verdict::Violation)];
    let mut failures = Vec::new();
    for (engine, confirm) in [(jvmcontract::Engine::Jbmc, false), (jvmcontract::Engine::Auto, true)] {
        for (build, relation, expected) in cases {
            let c = if relation { rounded_up() } else { dollars_and_cents() };
            let o = related_on(engine, confirm, root, build, "prices.Prices#raise", c, &format!("field-{relation}"));
            let jvm = o.counterexample.as_ref().is_some_and(|cx| cx.jvm.is_some());
            if o.verdict != expected || (expected == Verdict::Violation && !jvm) {
                failures.push(format!("{engine:?} confirm={confirm} {build} relation={relation}: {:?} (expected {expected:?}, on a JVM {jvm})\n{}", o.verdict, o.output));
            }
        }
    }
    assert!(failures.is_empty(), "{}", failures.join("\n\n"));
}

/// The computed input equations under JBMC and under `auto --confirm`: the same verdicts as on the own checker,
/// each refutation's witness run on a JVM, since JBMC checks the same harness (the previous leaf computed in its
/// bytecode). A pipeline job (`cargo test --release --test heap -- --ignored computed_equations`).
#[test]
#[ignore = "runs JBMC on the computed equations: a pipeline job"]
fn the_computed_equations_have_the_same_verdicts_under_jbmc_and_auto_confirm() {
    if Command::new("jbmc").arg("--version").output().is_err() {
        return;
    }
    let Some(root) = price_builds() else { return };
    let cases = [("after", "total", Verdict::Verified), ("after", "doubled", Verdict::Verified), ("after", "raise", Verdict::Verified), ("defect", "total", Verdict::Violation), ("defect", "raise", Verdict::Violation)];
    let mut failures = Vec::new();
    for (engine, confirm) in [(jvmcontract::Engine::Jbmc, false), (jvmcontract::Engine::Auto, true)] {
        for (build, method, expected) in cases {
            let o = related_on(engine, confirm, root, build, &format!("prices.Prices#{method}"), dollars_and_cents(), method);
            let jvm = o.counterexample.as_ref().is_some_and(|cx| cx.jvm.is_some());
            if o.verdict != expected || (expected == Verdict::Violation && !jvm) {
                failures.push(format!("{engine:?} confirm={confirm} {build} {method}: {:?} (expected {expected:?}, on a JVM {jvm})\n{}", o.verdict, o.output));
            }
        }
    }
    assert!(failures.is_empty(), "{}", failures.join("\n\n"));
}

// Input equations whose expression reads the new version's primitive parameters as well as the object's fields
// (H5's rest): a line that held its total now holds its unit price, the count passed beside it in both versions.

const LINE_BEFORE: &str = r#"package lines;
public final class Line {
    long total;
    public Line(long total) {
        if (total < 0) throw new IllegalArgumentException();
        this.total = total;
    }
}
"#;

const LINE_AFTER: &str = r#"package lines;
public final class Line {
    long price;
    public Line(long price) {
        if (price < 0) throw new IllegalArgumentException();
        this.price = price;
    }
}
"#;

const LINES_BEFORE: &str = r#"package lines;
public final class Lines {
    public static long discounted(Line l, int n) { return n >= 10 ? l.total - l.total / 10 : l.total; }
    public static void reprice(Line l, int n, long price) { if (price >= 0) l.total = price * n; }
}
"#;

const LINES_AFTER: &str = r#"package lines;
public final class Lines {
    public static long discounted(Line l, int n) { long t = l.price * n; return n >= 10 ? t - t / 10 : t; }
    public static void reprice(Line l, int n, long price) { if (price >= 0) l.price = price; }
}
"#;

const LINES_DEFECT: &str = r#"package lines;
public final class Lines {
    // The discount from the eleventh item rather than the tenth.
    public static long discounted(Line l, int n) { long t = l.price * n; return n > 10 ? t - t / 10 : t; }
    // The unit price set to the line's amount: seen only in the line as the call leaves it.
    public static void reprice(Line l, int n, long price) { if (price >= 0) l.price = price * n; }
}
"#;

/// The line kernel's builds, compiled once: `before` (`Line(long total)`), and `after` and `defect` (`Line(long
/// price)`).
fn line_builds() -> Option<&'static PathBuf> {
    static DIR: OnceLock<Option<PathBuf>> = OnceLock::new();
    DIR.get_or_init(|| {
        compiled()?;
        let root = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("heap-lines");
        let _ = std::fs::remove_dir_all(&root);
        for (build, line, lines) in [("before", LINE_BEFORE, LINES_BEFORE), ("after", LINE_AFTER, LINES_AFTER), ("defect", LINE_AFTER, LINES_DEFECT)] {
            let src = root.join(format!("{build}-src/lines"));
            std::fs::create_dir_all(&src).unwrap();
            std::fs::write(src.join("Line.java"), line).unwrap();
            std::fs::write(src.join("Lines.java"), lines).unwrap();
            let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-d"]).arg(root.join(build)).arg(src.join("Line.java")).arg(src.join("Lines.java")).status().expect("javac runs");
            assert!(status.success(), "the line kernel compiles");
        }
        Some(root)
    })
    .as_ref()
}

const UNIT_PRICE: &str = "new.l.price * new.n";

fn unit_price() -> jvmcontract::spec::Correspondence {
    correspondence(&[("old.l.total", UNIT_PRICE)], None)
}

#[test]
fn an_equations_expression_over_the_objects_fields_and_a_primitive_parameter_makes_and_compares_the_previous_object() {
    let Some(root) = line_builds() else { return };
    let o = related(root, "after", "lines.Lines#discounted", unit_price(), "discounted");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let domain = o.domain.as_deref().unwrap_or_default();
    assert!(domain.contains("as the correspondence's input equations say (old.l.total == new.l.price * new.n)"), "{domain}");
    let source = std::fs::read_to_string(o.statement.as_ref().unwrap()).unwrap();
    assert!(source.contains("l_before = new before.lines.Line((long) (l_price * n));"), "made from the parameter too: {source}");
    assert!(source.contains("if (!(l_before.total == (l_after.price * n))) { return; }"), "{source}");
    // The line as the call leaves it is compared through the same equation, the count as the call got it.
    let o = related(root, "after", "lines.Lines#reprice", unit_price(), "reprice");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().unwrap();
    assert_eq!(stated.observations.objects, ["l: under the correspondence, old.l.total == new.l.price * new.n"]);
    // A discount from the eleventh item is refuted in the result, the previous line made from the witness's price
    // and count, on a JVM too.
    let o = related(root, "defect", "lines.Lines#discounted", unit_price(), "discounted");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let cx = o.counterexample.as_ref().unwrap();
    assert!(cx.input.contains("n=10"), "{}", cx.input);
    assert_eq!(cx.differs, ["result"], "{}", o.output);
    confirmed_on_the_jvm(&o);
    // A unit price set to the line's amount is seen in the line as left.
    let o = related(root, "defect", "lines.Lines#reprice", unit_price(), "reprice");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let cx = o.counterexample.as_ref().unwrap();
    assert_eq!(cx.differs, ["field:l", "field:l.total"], "{}", o.output);
    confirmed_on_the_jvm(&o);
    // Refused by name: a parameter the new version doesn't have, and the object read as a whole.
    let o = related(root, "after", "lines.Lines#discounted", correspondence(&[("old.l.total", "new.l.price * new.m")], None), "unknown");
    assert!(o.problem.as_deref().unwrap().contains("reads new.m, which is not a parameter of the new version (l, n)"), "{}", o.output);
    let o = related(root, "after", "lines.Lines#discounted", correspondence(&[("old.l.total", "new.l.price * new.n + new.l")], None), "whole");
    assert!(o.problem.as_deref().unwrap().contains("reads new.l as a whole"), "{}", o.output);
}

#[test]
fn a_claim_over_an_equation_that_reads_a_parameter_is_refused_where_the_contract_anchors_the_object_and_checked_where_a_person_stated_it() {
    use jvmcontract::spec::{Derivation, ExternalInput, ObservationState, Verdict as V};
    let Some(root) = line_builds() else { return };
    let claim_of = |subject: &str, derivation: Derivation| {
        let mut claim = kernel_claim(subject, &[]);
        claim.contract.inputs = vec![ExternalInput { name: "l".into(), ty: "lines.Line".into(), derivation }, ExternalInput { name: "n".into(), ty: "int".into(), derivation: Derivation::Identity }];
        let domain = claim.domain.as_mut().unwrap();
        domain.classes = vec!["lines.Line".into()];
        domain.bounds.after.input_objects = 1;
        claim.correspondence = Some(unit_price());
        claim
    };
    let check = |build: &str, claim: &jvmcontract::spec::CanonicalClaim| jvmcontract::spec::heap::check(claim, &root.join("before"), &root.join(build));
    let gap = check("after", &claim_of("lines.Lines#discounted", Derivation::Identity)).expect_err("an anchored input");
    assert!(gap.what.contains("the preservation contract anchors l (its derivation is identity)"), "{gap:?}");
    let stated = Derivation::Stated { expression: format!("old.l.total == {UNIT_PRICE}") };
    for (build, method, verdict, state) in [("after", "discounted", V::Verified, ObservationState::Preserved), ("defect", "discounted", V::Refuted, ObservationState::Refuted), ("after", "reprice", V::Verified, ObservationState::Preserved)] {
        let o = check(build, &claim_of(&format!("lines.Lines#{method}"), stated.clone())).expect("stated by a person");
        assert_eq!(o.verdict, verdict, "{build} {method}: {o:?}");
        assert_eq!(state_of(&o, "result"), state, "{build} {method}: {o:?}");
    }
    // The line as left differs, which a claim that requires its field refutes, and one that doesn't leaves outside.
    let mut claim = claim_of("lines.Lines#reprice", stated);
    let o = check("defect", &claim).expect("stated by a person");
    assert_eq!(o.verdict, V::Unresolved, "{o:?}");
    assert!(o.problem.as_deref().unwrap().contains("differ only in field:l, field:l.total, which the claim does not require"), "{o:?}");
    let field = jvmcontract::spec::Observation::FieldPath { path: "l.total".into() };
    claim.contract.required.push(field.id());
    claim.observations.push(field);
    let o = check("defect", &claim).expect("stated by a person");
    assert_eq!(o.verdict, V::Refuted, "{o:?}");
    assert_eq!(state_of(&o, "field:l.total"), ObservationState::Refuted, "{o:?}");
}

/// The equations that read a parameter under JBMC and under `auto --confirm`: the same verdicts as on the own
/// checker, each refutation's witness run on a JVM, since JBMC checks the same harness (the previous leaf computed
/// from the parameter in its bytecode). A pipeline job (`cargo test --release --test heap -- --ignored
/// parameter_reads`).
#[test]
#[ignore = "runs JBMC on the equations that read a parameter: a pipeline job"]
fn the_parameter_reads_have_the_same_verdicts_under_jbmc_and_auto_confirm() {
    if Command::new("jbmc").arg("--version").output().is_err() {
        return;
    }
    let Some(root) = line_builds() else { return };
    let cases = [("after", "discounted", Verdict::Verified), ("after", "reprice", Verdict::Verified), ("defect", "discounted", Verdict::Violation), ("defect", "reprice", Verdict::Violation)];
    let mut failures = Vec::new();
    for (engine, confirm) in [(jvmcontract::Engine::Jbmc, false), (jvmcontract::Engine::Auto, true)] {
        for (build, method, expected) in cases {
            let o = related_on(engine, confirm, root, build, &format!("lines.Lines#{method}"), unit_price(), method);
            let jvm = o.counterexample.as_ref().is_some_and(|cx| cx.jvm.is_some());
            if o.verdict != expected || (expected == Verdict::Violation && !jvm) {
                failures.push(format!("{engine:?} confirm={confirm} {build} {method}: {:?} (expected {expected:?}, on a JVM {jvm})\n{}", o.verdict, o.output));
            }
        }
    }
    assert!(failures.is_empty(), "{}", failures.join("\n\n"));
}

// Input equations whose expression reads another object parameter's fields (H5's rest): a line that held its total
// now holds its unit price, the count kept by an order passed beside it in both versions.

const ORDER: &str = r#"package orders;
public final class Order {
    int count;
    public Order(int count) {
        if (count < 0) throw new IllegalArgumentException();
        this.count = count;
    }
}
"#;

const ORDER_LINE_BEFORE: &str = r#"package orders;
public final class Line {
    long total;
    public Line(long total) {
        if (total < 0) throw new IllegalArgumentException();
        this.total = total;
    }
}
"#;

const ORDER_LINE_AFTER: &str = r#"package orders;
public final class Line {
    long price;
    public Line(long price) {
        if (price < 0) throw new IllegalArgumentException();
        this.price = price;
    }
}
"#;

const ORDERS_BEFORE: &str = r#"package orders;
public final class Orders {
    public static long discounted(Line l, Order o) { return o.count >= 10 ? l.total - l.total / 10 : l.total; }
    public static void reprice(Line l, Order o, long price) { if (price >= 0) l.total = price * o.count; }
}
"#;

const ORDERS_AFTER: &str = r#"package orders;
public final class Orders {
    public static long discounted(Line l, Order o) { long t = l.price * o.count; return o.count >= 10 ? t - t / 10 : t; }
    public static void reprice(Line l, Order o, long price) { if (price >= 0) l.price = price; }
}
"#;

const ORDERS_DEFECT: &str = r#"package orders;
public final class Orders {
    // The discount from the eleventh item rather than the tenth.
    public static long discounted(Line l, Order o) { long t = l.price * o.count; return o.count > 10 ? t - t / 10 : t; }
    // The unit price set to the line's amount: seen only in the line as the call leaves it.
    public static void reprice(Line l, Order o, long price) { if (price >= 0) l.price = price * o.count; }
}
"#;

/// The order kernel's builds, compiled once: `before` (`Line(long total)`), and `after` and `defect` (`Line(long
/// price)`), each with the same `Order(int count)`.
fn order_builds() -> Option<&'static PathBuf> {
    static DIR: OnceLock<Option<PathBuf>> = OnceLock::new();
    DIR.get_or_init(|| {
        compiled()?;
        let root = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("heap-orders");
        let _ = std::fs::remove_dir_all(&root);
        for (build, line, orders) in [("before", ORDER_LINE_BEFORE, ORDERS_BEFORE), ("after", ORDER_LINE_AFTER, ORDERS_AFTER), ("defect", ORDER_LINE_AFTER, ORDERS_DEFECT)] {
            let src = root.join(format!("{build}-src/orders"));
            std::fs::create_dir_all(&src).unwrap();
            std::fs::write(src.join("Order.java"), ORDER).unwrap();
            std::fs::write(src.join("Line.java"), line).unwrap();
            std::fs::write(src.join("Orders.java"), orders).unwrap();
            let files = ["Order.java", "Line.java", "Orders.java"].map(|f| src.join(f));
            let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-d"]).arg(root.join(build)).args(&files).status().expect("javac runs");
            assert!(status.success(), "the order kernel compiles");
        }
        Some(root)
    })
    .as_ref()
}

const ORDER_PRICE: &str = "new.l.price * new.o.count";

fn order_price() -> jvmcontract::spec::Correspondence {
    correspondence(&[("old.l.total", ORDER_PRICE)], None)
}

#[test]
fn an_equations_expression_over_another_object_parameters_fields_makes_and_compares_the_previous_object() {
    let Some(root) = order_builds() else { return };
    let o = related(root, "after", "orders.Orders#discounted", order_price(), "discounted");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let domain = o.domain.as_deref().unwrap_or_default();
    assert!(domain.contains("as the correspondence's input equations say (old.l.total == new.l.price * new.o.count)"), "{domain}");
    let source = std::fs::read_to_string(o.statement.as_ref().unwrap()).unwrap();
    // The previous line is made from the order's argument, its flat parameter, and so checked as made.
    assert!(source.contains("l_before = new before.orders.Line((long) (l_price * o_count));"), "made from the order's count: {source}");
    assert!(source.contains("if (!(l_before.total == (l_after.price * o_count))) { return; }"), "{source}");
    // The line as the call leaves it is compared through the same equation, the order's count as the call got it;
    // the order itself is compared field by field as without the correspondence.
    let o = related(root, "after", "orders.Orders#reprice", order_price(), "reprice");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().unwrap();
    assert_eq!(stated.observations.objects, ["l: under the correspondence, old.l.total == new.l.price * new.o.count", "o: count"]);
    // A discount from the eleventh item is refuted in the result, on a JVM too.
    let o = related(root, "defect", "orders.Orders#discounted", order_price(), "discounted");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let cx = o.counterexample.as_ref().unwrap();
    assert!(cx.input.contains("o=new Order(10)"), "{}", cx.input);
    assert_eq!(cx.differs, ["result"], "{}", o.output);
    confirmed_on_the_jvm(&o);
    // A unit price set to the line's amount is seen in the line as left.
    let o = related(root, "defect", "orders.Orders#reprice", order_price(), "reprice");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let cx = o.counterexample.as_ref().unwrap();
    assert_eq!(cx.differs, ["field:l", "field:l.total"], "{}", o.output);
    confirmed_on_the_jvm(&o);
    // Refused by name: a path the order doesn't have, and an order that may be null, whose count is then no field.
    let o = related(root, "after", "orders.Orders#discounted", correspondence(&[("old.l.total", "new.l.price * new.o.size")], None), "unknown");
    assert!(o.problem.as_deref().unwrap().contains("reads o.size, which is not a primitive field path of the new version's Order (count)"), "{}", o.output);
    let mut options = jvmcontract::equivalence::Options::new(&root.join("before"), &root.join("after"), "orders.Orders#discounted");
    options.engine = jvmcontract::Engine::Native;
    options.correspondence = Some(order_price());
    options.nullable = vec!["o".into()];
    options.work = Some(root.join("work-related-nullable"));
    let o = jvmcontract::equivalence::run(&options).unwrap();
    assert!(o.problem.as_deref().unwrap().contains("reads new.o.count, and o may be null or another parameter's object"), "{}", o.output);
}

#[test]
fn a_claim_over_an_equation_that_reads_another_object_is_checked_where_a_person_stated_it() {
    use jvmcontract::spec::{Derivation, ExternalInput, ObservationState, Verdict as V};
    let Some(root) = order_builds() else { return };
    let claim_of = |subject: &str, derivation: Derivation| {
        let mut claim = kernel_claim(subject, &[]);
        claim.contract.inputs = vec![ExternalInput { name: "l".into(), ty: "orders.Line".into(), derivation }, ExternalInput { name: "o".into(), ty: "orders.Order".into(), derivation: Derivation::Identity }];
        let domain = claim.domain.as_mut().unwrap();
        domain.classes = vec!["orders.Line".into(), "orders.Order".into()];
        domain.bounds.before.input_objects = 2;
        domain.bounds.after.input_objects = 2;
        claim.correspondence = Some(order_price());
        claim
    };
    let check = |build: &str, claim: &jvmcontract::spec::CanonicalClaim| jvmcontract::spec::heap::check(claim, &root.join("before"), &root.join(build));
    let gap = check("after", &claim_of("orders.Orders#discounted", Derivation::Identity)).expect_err("an anchored input");
    assert!(gap.what.contains("the preservation contract anchors l (its derivation is identity)"), "{gap:?}");
    let stated = Derivation::Stated { expression: format!("old.l.total == {ORDER_PRICE}") };
    for (build, method, verdict, state) in [("after", "discounted", V::Verified, ObservationState::Preserved), ("defect", "discounted", V::Refuted, ObservationState::Refuted), ("after", "reprice", V::Verified, ObservationState::Preserved)] {
        let o = check(build, &claim_of(&format!("orders.Orders#{method}"), stated.clone())).expect("stated by a person");
        assert_eq!(o.verdict, verdict, "{build} {method}: {o:?}");
        assert_eq!(state_of(&o, "result"), state, "{build} {method}: {o:?}");
    }
}

/// The equations that read another object under JBMC and under `auto --confirm`: the same verdicts as on the own
/// checker, each refutation's witness run on a JVM, since JBMC checks the same harness. A pipeline job (`cargo test
/// --release --test heap -- --ignored the_other_object_reads`).
#[test]
#[ignore = "runs JBMC on the equations that read another object: a pipeline job"]
fn the_other_object_reads_have_the_same_verdicts_under_jbmc_and_auto_confirm() {
    if Command::new("jbmc").arg("--version").output().is_err() {
        return;
    }
    let Some(root) = order_builds() else { return };
    let cases = [("after", "discounted", Verdict::Verified), ("after", "reprice", Verdict::Verified), ("defect", "discounted", Verdict::Violation), ("defect", "reprice", Verdict::Violation)];
    let mut failures = Vec::new();
    for (engine, confirm) in [(jvmcontract::Engine::Jbmc, false), (jvmcontract::Engine::Auto, true)] {
        for (build, method, expected) in cases {
            let o = related_on(engine, confirm, root, build, &format!("orders.Orders#{method}"), order_price(), method);
            let jvm = o.counterexample.as_ref().is_some_and(|cx| cx.jvm.is_some());
            if o.verdict != expected || (expected == Verdict::Violation && !jvm) {
                failures.push(format!("{engine:?} confirm={confirm} {build} {method}: {:?} (expected {expected:?}, on a JVM {jvm})\n{}", o.verdict, o.output));
            }
        }
    }
    assert!(failures.is_empty(), "{}", failures.join("\n\n"));
}

// Output relations for identity relations (H5's rest): a correspondence's relation over whether `result == q` holds
// in each version, compared in place of "holds before iff it holds now", for a change that hands back a copy on
// purpose.

/// The joint example's correspondence, with an output relation for `identity:result==q`.
fn identity_relation(holds: &str) -> jvmcontract::spec::Correspondence {
    let mut c = correspondence(&[("old.q.cents", "new.q.amount.cents"), ("old.q.quantity", "new.q.quantity")], None);
    c.outputs.push(jvmcontract::spec::Relation { observation: "identity:result==q".into(), holds: holds.into() });
    c
}

/// The previous version handed back the quote itself; the new one always hands back another object.
const ALWAYS_A_COPY: &str = "old.result == old.q && new.result != new.q";

#[test]
fn an_output_relation_for_an_identity_relation_compares_it_in_place_of_holds_before_iff_it_holds_now() {
    let Some(root) = kernel_builds() else { return };
    let target = "shop.Pricing#withQuantity";
    // Without the relation, the copy is the alias-to-copy defect, told apart by result == q alone.
    let plain = correspondence(&[("old.q.cents", "new.q.amount.cents"), ("old.q.quantity", "new.q.quantity")], None);
    let o = related(root, "copied", target, plain, "identity-plain");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert_eq!(o.counterexample.as_ref().unwrap().differs, ["identity:result==q"], "{}", o.output);
    // Under it, the copy is what the relation says.
    let o = related(root, "copied", target, identity_relation(ALWAYS_A_COPY), "identity");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert_eq!(o.stated.as_ref().unwrap().observations.identities, [format!("result == q, under the output relation {ALWAYS_A_COPY}")]);
    let source = std::fs::read_to_string(o.statement.as_ref().unwrap()).unwrap();
    assert!(source.contains("&& ((a == q_before) && !(b == q_after))"), "{source}");
    // The quote itself handed back breaks it, as does handing it back only sometimes: each refuted in the relation,
    // with a note, on a JVM too.
    let o = related(root, "after", target, identity_relation(ALWAYS_A_COPY), "identity");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let cx = o.counterexample.as_ref().unwrap();
    assert_eq!(cx.differs, ["identity:result==q"], "{}", o.output);
    assert!(o.output.contains(&format!("result == q is not related by {ALWAYS_A_COPY}: it holds before and holds now")), "{}", o.output);
    confirmed_on_the_jvm(&o);
    let o = related(root, "sometimes-copied", target, identity_relation(ALWAYS_A_COPY), "identity");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let cx = o.counterexample.as_ref().unwrap();
    assert_eq!(cx.differs, ["identity:result==q"], "{}", o.output);
    assert!(cx.input.starts_with("withQuantity(q=new Quote(new Money("), "{}", cx.input);
    confirmed_on_the_jvm(&o);
    // "Holds before iff it holds now", written out, is the default's verdict on each.
    let iff = "(old.result == old.q) == (new.result == new.q)";
    assert_eq!(related(root, "after", target, identity_relation(iff), "identity-iff").verdict, Verdict::Verified);
    assert_eq!(related(root, "copied", target, identity_relation(iff), "identity-iff").verdict, Verdict::Violation);
    // Refused by name: a relation the check doesn't observe, and one that reads a field.
    let mut gap = identity_relation("true");
    gap.outputs[0].observation = "identity:result==quantity".into();
    let o = related(root, "copied", target, gap, "identity-gap");
    assert!(o.problem.as_deref().unwrap().contains("names result == quantity, which is not an identity relation the check observes (result == q)"), "{}", o.output);
    let o = related(root, "copied", target, identity_relation("new.q.quantity > 0"), "identity-field");
    assert!(o.problem.as_deref().unwrap().contains("reads new.q.quantity alone"), "{}", o.output);
}

#[test]
fn a_required_identity_relation_under_an_output_relation_is_unresolved_until_approved_and_then_changed_with_approval_or_refuted() {
    use jvmcontract::spec::{ApprovedChange, ObservationState, Verdict as V};
    let claim_with = |approved: bool| {
        let mut claim = kernel_claim("shop.Pricing#withQuantity", &[identity_result_q()]);
        claim.correspondence = Some(identity_relation(ALWAYS_A_COPY));
        if approved {
            claim.contract.approved_changes.push(ApprovedChange { observation: "identity:result==q".into(), text: "withQuantity hands back a copy now".into() });
        }
        claim
    };
    // Unapproved, the copy is unresolved in the relation, whatever the check finds, and the rest preserved.
    let Some(r) = kernel_check("copied", &claim_with(false)) else { return };
    let o = r.expect("supported");
    assert_eq!(o.verdict, V::Unresolved, "{o:?}");
    assert_eq!(state_of(&o, "identity:result==q"), ObservationState::Unresolved);
    assert_eq!(state_of(&o, "result"), ObservationState::Preserved);
    assert!(o.problem.as_deref().unwrap().contains("compares identity:result==q in place of equality, which the preservation contract requires and no person approved as changed"), "{o:?}");
    let o = kernel_check("after", &claim_with(false)).unwrap().expect("supported");
    assert_eq!(o.verdict, V::Unresolved, "{o:?}");
    assert!(o.problem.as_deref().unwrap().contains("differ under the correspondence's output relation for identity:result==q"), "{o:?}");
    // Approved, the relation is the claim: the copy changed with approval, and the quote itself handed back, always
    // or sometimes, refuted in it.
    let o = kernel_check("copied", &claim_with(true)).unwrap().expect("supported");
    assert_eq!(o.verdict, V::Verified, "{o:?}");
    assert_eq!(state_of(&o, "identity:result==q"), ObservationState::ChangedWithApproval);
    assert_eq!(state_of(&o, "result"), ObservationState::Preserved);
    assert_eq!(state_of(&o, "exception"), ObservationState::Preserved);
    for build in ["after", "sometimes-copied"] {
        let o = kernel_check(build, &claim_with(true)).unwrap().expect("supported");
        assert_eq!(o.verdict, V::Refuted, "{build}: {o:?}");
        assert_eq!(state_of(&o, "identity:result==q"), ObservationState::Refuted, "{build}");
    }
}

#[test]
#[ignore = "runs JBMC on the identity relations: a pipeline job"]
fn the_identity_relations_have_the_same_verdicts_under_jbmc_and_auto_confirm() {
    if Command::new("jbmc").arg("--version").output().is_err() {
        return;
    }
    let Some(root) = kernel_builds() else { return };
    let cases = [("copied", Verdict::Verified), ("after", Verdict::Violation), ("sometimes-copied", Verdict::Violation)];
    let mut failures = Vec::new();
    for (engine, confirm) in [(jvmcontract::Engine::Jbmc, false), (jvmcontract::Engine::Auto, true)] {
        for (build, expected) in cases {
            let o = related_on(engine, confirm, root, build, "shop.Pricing#withQuantity", identity_relation(ALWAYS_A_COPY), "identity");
            let jvm = o.counterexample.as_ref().is_some_and(|cx| cx.jvm.is_some());
            if o.verdict != expected || (expected == Verdict::Violation && !jvm) {
                failures.push(format!("{engine:?} confirm={confirm} {build}: {:?} (expected {expected:?}, on a JVM {jvm})\n{}", o.verdict, o.output));
            }
        }
    }
    assert!(failures.is_empty(), "{}", failures.join("\n\n"));
}

// Output relations for a field of a parameter whose two versions have the same shape and no input equations (H5's
// rest): the object kernel's `bump`, whose defect adds two where the previous version added one.

const ONE_MORE: &str = "new.l.quantity == old.l.quantity + 1";

/// A correspondence with no input equations and one output relation, for `field:l.quantity`.
fn quantity_relation(holds: &str) -> jvmcontract::spec::Correspondence {
    let mut c = correspondence(&[], None);
    c.outputs.push(jvmcontract::spec::Relation { observation: "field:l.quantity".into(), holds: holds.into() });
    c
}

#[test]
fn an_output_relation_for_a_field_of_a_parameter_of_the_same_shape_compares_it_in_place_of_equality() {
    let Some(root) = object_builds() else { return };
    let target = "objects.Kernel#bump";
    // `+= 2` in place of `+= 1`, refuted without a relation, is verified under one saying the new version adds one more.
    let o = related(root, "defect", target, quantity_relation(ONE_MORE), "bump-more");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().unwrap();
    assert_eq!(stated.observations.objects, [format!("l: price.cents; l.quantity under the output relation {ONE_MORE}")]);
    // The two objects are made from the same leaves as without a correspondence: no equation is assumed of them.
    let domain = o.domain.as_deref().unwrap();
    assert!(!domain.contains("in the previous version"), "{domain}");
    assert!(stated.assumptions.iter().any(|a| a.text.starts_with("either version's constructor Line(price: Money(cents: long), quantity: int) accepts the arguments of l")), "{:?}", stated.assumptions);
    let source = std::fs::read_to_string(o.statement.as_ref().unwrap()).unwrap();
    assert!(source.contains("&& (l_before.price.cents == l_after.price.cents) && (l_after.quantity == l_before.quantity + 1)"), "{source}");
    assert!(!source.contains("of the objects as made"), "{source}");
    // The new version's `+ 1`, the same as before, breaks it, in l.quantity alone, on a witness the JVM runs too.
    let o = related(root, "after", target, quantity_relation(ONE_MORE), "bump-same");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let cx = o.counterexample.as_ref().unwrap();
    assert_eq!(cx.differs, ["field:l.quantity"], "{}", o.output);
    assert!(o.output.contains(&format!("l.quantity as the calls leave it is not related by {ONE_MORE}")), "{}", o.output);
    confirmed_on_the_jvm(&o);
    // Its other paths are still compared for equality: under a relation for l.price.cents alone, the defect is
    // refuted in the quantity.
    let mut price = correspondence(&[], None);
    price.outputs.push(jvmcontract::spec::Relation { observation: "field:l.price.cents".into(), holds: "true".into() });
    let o = related(root, "defect", target, price, "bump-price");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert_eq!(o.counterexample.as_ref().unwrap().differs, ["field:l", "field:l.quantity"], "{}", o.output);
    confirmed_on_the_jvm(&o);
    // Equality written out gives the default's verdicts.
    let same = quantity_relation("new.l.quantity == old.l.quantity");
    assert_eq!(related(root, "after", target, same.clone(), "bump-equal").verdict, Verdict::Verified);
    assert_eq!(related(root, "defect", target, same, "bump-equal").verdict, Verdict::Violation);
    // Refused by name: a path the previous version's Line doesn't have, and a relation for an int parameter's field.
    let mut unknown = correspondence(&[], None);
    unknown.outputs.push(jvmcontract::spec::Relation { observation: "field:l.count".into(), holds: "true".into() });
    let o = related(root, "after", target, unknown, "bump-unknown");
    assert!(o.problem.as_deref().unwrap().contains("names count, which is not a field path of the previous version's Line (price.cents, quantity)"), "{}", o.output);
    let mut int = correspondence(&[], None);
    int.outputs.push(jvmcontract::spec::Relation { observation: "field:quantity".into(), holds: "true".into() });
    let o = related(root, "after", "objects.Kernel#withQuantity", int, "with-int");
    assert!(o.problem.as_deref().unwrap().contains("is about quantity, which is not an object parameter made by its constructor that the correspondence's input equations relate or that has the same shape in both versions"), "{}", o.output);
}

/// The claim over the object kernel's `bump`, `l` anchored (identity) and `l.quantity` and `l.price.cents`
/// required, under `correspondence`.
fn bump_claim(c: jvmcontract::spec::Correspondence) -> jvmcontract::spec::CanonicalClaim {
    use jvmcontract::spec::{Derivation, ExternalInput, Observation};
    let fields = [Observation::FieldPath { path: "l.quantity".into() }, Observation::FieldPath { path: "l.price.cents".into() }];
    let mut claim = kernel_claim("objects.Kernel#bump", &fields);
    claim.contract.inputs = vec![ExternalInput { name: "l".into(), ty: "objects.Line".into(), derivation: Derivation::Identity }];
    let domain = claim.domain.as_mut().unwrap();
    domain.classes = vec!["objects.Line".into(), "objects.Money".into()];
    domain.bounds.before.input_objects = 2;
    domain.bounds.after.input_objects = 2;
    claim.correspondence = Some(c);
    claim
}

#[test]
fn a_required_field_of_a_parameter_of_the_same_shape_under_an_output_relation_is_unresolved_until_approved() {
    use jvmcontract::spec::{ApprovedChange, ObservationState, Verdict as V};
    let Some(root) = object_builds() else { return };
    let check = |build: &str, claim: &jvmcontract::spec::CanonicalClaim| jvmcontract::spec::heap::check(claim, &root.join("before"), &root.join(build)).expect("supported");
    // Without the relation, adding two is refuted in the quantity.
    let o = check("defect", &bump_claim(correspondence(&[], None)));
    assert_eq!(o.verdict, V::Refuted, "{o:?}");
    assert_eq!(state_of(&o, "field:l.quantity"), ObservationState::Refuted);
    // Under it, the contract still requires equality: unresolved until a person approves, the price preserved.
    let mut claim = bump_claim(quantity_relation(ONE_MORE));
    let o = check("defect", &claim);
    assert_eq!(o.verdict, V::Unresolved, "{o:?}");
    assert_eq!(state_of(&o, "field:l.quantity"), ObservationState::Unresolved);
    assert_eq!(state_of(&o, "field:l.price.cents"), ObservationState::Preserved);
    assert!(o.problem.as_deref().unwrap().contains("compares field:l.quantity in place of equality"), "{o:?}");
    // Approved, by its path or the object's: changed with approval where it holds, refuted where it doesn't.
    for approved in ["field:l.quantity", "field:l"] {
        claim.contract.approved_changes = vec![ApprovedChange { observation: approved.into(), text: "a bump adds two now".into() }];
        let o = check("defect", &claim);
        assert_eq!(o.verdict, V::Verified, "{approved}: {o:?}");
        assert_eq!(state_of(&o, "field:l.quantity"), ObservationState::ChangedWithApproval);
        assert_eq!(state_of(&o, "field:l.price.cents"), ObservationState::Preserved);
        let o = check("after", &claim);
        assert_eq!(o.verdict, V::Refuted, "{approved}: {o:?}");
        assert_eq!(state_of(&o, "field:l.quantity"), ObservationState::Refuted);
    }
}

/// The output relations for a field of a parameter of the same shape under JBMC and under `auto --confirm`: the
/// same verdicts as on the own checker, each refutation's witness run on a JVM, since JBMC checks the same harness.
/// A pipeline job (`cargo test --release --test heap -- --ignored same_shape_relations`).
#[test]
#[ignore = "runs JBMC on the same-shape field relations: a pipeline job"]
fn the_same_shape_relations_have_the_same_verdicts_under_jbmc_and_auto_confirm() {
    if Command::new("jbmc").arg("--version").output().is_err() {
        return;
    }
    let Some(root) = object_builds() else { return };
    let cases = [("defect", Verdict::Verified), ("after", Verdict::Violation)];
    let mut failures = Vec::new();
    for (engine, confirm) in [(jvmcontract::Engine::Jbmc, false), (jvmcontract::Engine::Auto, true)] {
        for (build, expected) in cases {
            let o = related_on(engine, confirm, root, build, "objects.Kernel#bump", quantity_relation(ONE_MORE), "same-shape");
            let jvm = o.counterexample.as_ref().is_some_and(|cx| cx.jvm.is_some());
            if o.verdict != expected || (expected == Verdict::Violation && !jvm) {
                failures.push(format!("{engine:?} confirm={confirm} {build}: {:?} (expected {expected:?}, on a JVM {jvm})\n{}", o.verdict, o.output));
            }
        }
    }
    assert!(failures.is_empty(), "{}", failures.join("\n\n"));
}
