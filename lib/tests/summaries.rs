//! The summaries stream's tests (`llm-dlc/loops/foundations-summaries.md`): code closure digests (S1), over small
//! Java builds compiled with `javac` at test time. Each case compiles a base build and a variant, and checks that the
//! closure of a target changes exactly when something its proof reads changes, and names which part did.

use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::classfile::MemberRef;
use jvmcontract::classpath::ClassPath;
use jvmcontract::closure::{self, Closure, Configuration, PartChange, PartKind};
use jvmcontract::shared;

fn has_javac() -> bool {
    let found = Command::new("javac").arg("-version").output().is_ok_and(|o| o.status.success());
    if !found {
        let skip = std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1");
        assert!(skip, "javac not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip the tests that need it");
    }
    found
}

/// Compiles `files` (path under the source root, source) into `target/tmp/summaries/NAME`. None without javac.
fn compile(name: &str, files: &[(&str, &str)]) -> Option<PathBuf> {
    if !has_javac() {
        return None;
    }
    let root = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("summaries").join(name);
    let _ = std::fs::remove_dir_all(&root);
    let (src, out) = (root.join("src"), root.join("classes"));
    let mut paths = Vec::new();
    for (path, text) in files {
        let p = src.join(path);
        std::fs::create_dir_all(p.parent().unwrap()).unwrap();
        std::fs::write(&p, text).unwrap();
        paths.push(p);
    }
    std::fs::create_dir_all(&out).unwrap();
    let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-d"]).arg(&out).args(&paths).status().expect("javac runs");
    assert!(status.success(), "{name} compiles");
    Some(out)
}

fn cp(dir: &Path) -> ClassPath {
    let mut cp = ClassPath::new().with_default_jdk();
    cp.add(dir).unwrap();
    cp
}

fn closure_of(dir: &Path, root: &MemberRef, configuration: &Configuration) -> Closure {
    closure::closure(&cp(dir), root, configuration)
}

/// The changes of `root`'s closure from build `a` to build `b`.
fn changes(a: &Path, b: &Path, root: &MemberRef) -> Vec<PartChange> {
    let none = Configuration::none();
    closure_of(a, root, &none).changes(&closure_of(b, root, &none))
}

const SHAPES: &str = r#"package k;
public abstract class Shape {
    public abstract long area();
    public static long twice(Shape s) { return 2 * s.area(); }
}
"#;
const SQUARE: &str = r#"package k;
public class Square extends Shape {
    final long side;
    public Square(long side) { this.side = side; }
    public long area() { return side * side; }
}
"#;
const PRICING: &str = r#"package k;
public final class Pricing {
    static final int RATE = 10;
    static long discount(long gross) { return gross / RATE; }
    public static long total(long gross) { return gross - discount(gross); }
}
"#;
const OTHER: &str = r#"package k;
public final class Other { public static int one() { return 1; } }
"#;

fn base(name: &str, extra: &[(&str, &str)]) -> Option<PathBuf> {
    let mut files = vec![("k/Shape.java", SHAPES), ("k/Square.java", SQUARE), ("k/Pricing.java", PRICING), ("k/Other.java", OTHER)];
    for (path, text) in extra {
        files.retain(|(p, _)| p != path);
        files.push((path, text));
    }
    compile(name, &files)
}

fn total() -> MemberRef {
    MemberRef::new("k/Pricing", "total", "(J)J")
}

fn twice() -> MemberRef {
    MemberRef::new("k/Shape", "twice", "(Lk/Shape;)J")
}

#[test]
fn the_same_sources_compiled_twice_give_the_same_closure() {
    let (Some(a), Some(b)) = (base("same-a", &[]), base("same-b", &[])) else { return };
    let none = Configuration::none();
    let (x, y) = (closure_of(&a, &total(), &none), closure_of(&b, &total(), &none));
    assert_eq!(x, y);
    assert_eq!(x.digest(), y.digest());
    assert!(x.parts.contains_key("method k/Pricing.discount(J)J"), "the callee is in the closure: {:?}", x.parts.keys());
    assert!(x.parts.contains_key("class k/Pricing"));
    assert!(!x.parts.keys().any(|p| p.contains("k/Other")), "an unrelated class is not");
}

#[test]
fn a_changed_callee_body_names_the_callee() {
    let changed = PRICING.replace("gross / RATE", "gross / RATE + 0 * gross");
    let (Some(a), Some(b)) = (base("callee-a", &[]), base("callee-b", &[("k/Pricing.java", &changed)])) else { return };
    assert_eq!(changes(&a, &b, &total()), vec![PartChange::Changed { part: "method k/Pricing.discount(J)J".into() }]);
}

#[test]
fn an_unrelated_change_leaves_the_closure_alone() {
    let other = OTHER.replace("return 1", "return 2");
    let (Some(a), Some(b)) = (base("unrelated-a", &[]), base("unrelated-b", &[("k/Other.java", &other)])) else { return };
    assert!(changes(&a, &b, &total()).is_empty());
    assert!(changes(&a, &b, &twice()).is_empty());
}

#[test]
fn a_constant_field_changes_the_class_part() {
    let rate = PRICING.replace("RATE = 10", "RATE = 20");
    let (Some(a), Some(b)) = (base("constant-a", &[]), base("constant-b", &[("k/Pricing.java", &rate)])) else { return };
    let got = changes(&a, &b, &total());
    // javac inlines the constant into discount's body as well; the field's declaration is what must be named.
    assert!(got.contains(&PartChange::Changed { part: "class k/Pricing".into() }), "{got:?}");
}

#[test]
fn a_new_class_that_adds_a_dispatch_target_changes_the_closure_with_no_body_changed() {
    let circle = r#"package k;
public class Circle extends Shape {
    final long r;
    public Circle(long r) { this.r = r; }
    public long area() { return 3 * r * r; }
}
"#;
    let (Some(a), Some(b)) = (base("dispatch-a", &[]), base("dispatch-b", &[("k/Circle.java", circle)])) else { return };
    let got = changes(&a, &b, &twice());
    assert!(got.contains(&PartChange::Changed { part: "dispatch k/Shape.area()J".into() }), "{got:?}");
    assert!(got.contains(&PartChange::Added { part: "method k/Circle.area()J".into() }), "{got:?}");
    assert!(!got.iter().any(|c| matches!(c, PartChange::Changed { part } if part.starts_with("method "))), "no body changed: {got:?}");
}

#[test]
fn a_new_subclass_that_overrides_nothing_leaves_the_dispatch_alone() {
    let big = r#"package k;
public class BigSquare extends Square {
    public BigSquare(long side) { super(side); }
}
"#;
    let (Some(a), Some(b)) = (base("nonoverride-a", &[]), base("nonoverride-b", &[("k/BigSquare.java", big)])) else { return };
    assert!(changes(&a, &b, &twice()).is_empty());
}

#[test]
fn a_changed_superclass_changes_the_class_part() {
    let middle = r#"package k;
public abstract class Middle extends Shape {}
"#;
    let square = SQUARE.replace("extends Shape", "extends Middle");
    let (Some(a), Some(b)) = (base("hierarchy-a", &[]), base("hierarchy-b", &[("k/Middle.java", middle), ("k/Square.java", &square)])) else { return };
    let got = changes(&a, &b, &twice());
    assert!(got.contains(&PartChange::Changed { part: "class k/Square".into() }), "{got:?}");
}

const SERVICE_ANNOTATION: &str = r#"package org.springframework.stereotype;
import java.lang.annotation.*;
@Retention(RetentionPolicy.RUNTIME) @Target(ElementType.TYPE)
public @interface Service { String value() default ""; }
"#;
const ROUTE_ANNOTATION: &str = r#"package org.springframework.web.bind.annotation;
import java.lang.annotation.*;
@Retention(RetentionPolicy.RUNTIME) @Target(ElementType.METHOD)
public @interface PostMapping { String[] value() default {}; }
"#;
const CONTROLLER: &str = r#"package k;
import org.springframework.stereotype.Service;
import org.springframework.web.bind.annotation.PostMapping;
@Service
public class Controller {
    @PostMapping("/quotes")
    public long quote(long gross) { return Pricing.total(gross); }
}
"#;

fn spring(name: &str, controller: &str) -> Option<PathBuf> {
    base(name, &[("org/springframework/stereotype/Service.java", SERVICE_ANNOTATION), ("org/springframework/web/bind/annotation/PostMapping.java", ROUTE_ANNOTATION), ("k/Controller.java", controller)])
}

fn quote() -> MemberRef {
    MemberRef::new("k/Controller", "quote", "(J)J")
}

#[test]
fn a_framework_annotation_the_claim_uses_changes_the_closure() {
    let moved = CONTROLLER.replace("\"/quotes\"", "\"/quote\"");
    let (Some(a), Some(b)) = (spring("annotation-a", CONTROLLER), spring("annotation-b", &moved)) else { return };
    assert_eq!(changes(&a, &b, &quote()), vec![PartChange::Changed { part: "method k/Controller.quote(J)J".into() }]);
}

#[test]
fn configuration_is_part_of_a_closure_that_touches_spring_and_of_no_other() {
    let Some(a) = spring("configuration", CONTROLLER) else { return };
    let one = Configuration::of(&[("application.properties", b"shop.rate=10\n")]);
    let two = Configuration::of(&[("application.properties", b"shop.rate=20\n")]);
    let (x, y) = (closure_of(&a, &quote(), &one), closure_of(&a, &quote(), &two));
    assert_eq!(x.changes(&y), vec![PartChange::Changed { part: "config application.properties".into() }]);
    assert!(x.parts.keys().any(|p| PartKind::of(p) == PartKind::Config));
    // The pure kernel the controller calls reads no configuration.
    assert_eq!(closure_of(&a, &total(), &one), closure_of(&a, &total(), &two));
}

#[test]
fn a_target_the_build_does_not_have_is_named_missing() {
    let Some(a) = base("missing", &[]) else { return };
    let c = closure_of(&a, &MemberRef::new("k/Pricing", "gone", "()V"), &Configuration::none());
    assert_eq!(c.parts.keys().collect::<Vec<_>>(), ["missing k/Pricing.gone()V"]);
}

/// A change only inside a dynamic constant's bootstrap arguments: `case Color.GREEN` against `case Color.BLUE` in a
/// pattern switch. javac makes the enum constant a `Dynamic` constant whose bootstrap entry holds the name, so a
/// fingerprint that prints a dynamic constant by its bootstrap index alone sees two equal bodies.
#[test]
fn a_changed_enum_case_in_a_pattern_switch_is_a_changed_body() {
    let color = "package k;\npublic enum Color { RED, GREEN, BLUE }\n";
    let switch = r#"package k;
public final class Paint {
    public static int code(Object o) {
        return switch (o) {
            case Color c when c == Color.RED -> 1;
            case Color.GREEN -> 2;
            default -> 3;
        };
    }
}
"#;
    let blue = switch.replace("Color.GREEN ->", "Color.BLUE ->");
    let (Some(a), Some(b)) = (
        compile("condy-a", &[("k/Color.java", color), ("k/Paint.java", switch)]),
        compile("condy-b", &[("k/Color.java", color), ("k/Paint.java", &blue)]),
    ) else {
        return;
    };
    let root = MemberRef::new("k/Paint", "code", "(Ljava/lang/Object;)I");
    assert!(!shared::identical_closure(&cp(&a), &cp(&b), std::slice::from_ref(&root)), "the two versions differ, so a proof is needed");
    assert_eq!(changes(&a, &b, &root), vec![PartChange::Changed { part: "method k/Paint.code(Ljava/lang/Object;)I".into() }]);
}
