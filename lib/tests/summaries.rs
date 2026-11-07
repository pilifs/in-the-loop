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

// S2: the claim key and the proof cache.

use jvmcontract::proof_cache;
use jvmcontract::spec::cache::{self, ClaimKey, ResultRecord};
use jvmcontract::spec::{ApprovedChange, CanonicalClaim, Outcome, Verdict};
use serde_json::Value;

fn golden<T: serde::de::DeserializeOwned>(name: &str) -> T {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/foundations/golden").join(format!("{name}.json"));
    serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap()
}

/// A claim with every part filled: the joint example's kernel claim, with the entry point's environment, an approved
/// observation change, a nullable path, an alias pair, a stated derivation, an output relation, and computed digests.
fn full_claim() -> CanonicalClaim {
    let mut claim: CanonicalClaim = golden("kernel-claim");
    let entry: CanonicalClaim = golden("claim");
    claim.environment = entry.environment;
    claim.observations.extend(entry.observations);
    claim.observations.push(jvmcontract::spec::Observation::Identity { left: "result".into(), right: "q".into() });
    claim.observations.push(jvmcontract::spec::Observation::ArrayParameter { parameter: "a".into() });
    claim.observations.push(jvmcontract::spec::Observation::FieldPath { path: "result.total.cents".into() });
    claim.contract.approved_changes.push(ApprovedChange { observation: "status".into(), text: "201 in place of 200".into() });
    claim.contract.inputs.push(jvmcontract::spec::ExternalInput { name: "n".into(), ty: "int".into(), derivation: jvmcontract::spec::Derivation::Stated { expression: "n + 0".into() } });
    let domain = claim.domain.as_mut().unwrap();
    domain.nullable.push("q.note".into());
    domain.may_alias.push(("q".into(), "r".into()));
    let correspondence = claim.correspondence.as_mut().unwrap();
    correspondence.outputs.push(jvmcontract::spec::Relation { observation: "result".into(), holds: "old.result == new.result.cents".into() });
    claim.assumptions = vec!["shop.Pricing#discount proved equivalent under claim sha256:aa".into(), "contract: Math.abs(long) (proved)".into()];
    claim.closures.before = "sha256:before".into();
    claim.closures.after = "sha256:after".into();
    claim.tools = proof_cache::tools(true, "native strict; shared callees");
    claim
}

fn key_of(claim: &CanonicalClaim) -> ClaimKey {
    cache::key(claim).unwrap_or_else(|u| panic!("{u}"))
}

/// Every way to change one leaf or one array of `v`, with the path changed.
fn mutations(v: &Value, path: &str, out: &mut Vec<(String, Value)>) {
    let mut push = |p: String, changed: Value| out.push((p, changed));
    match v {
        Value::String(s) => push(path.into(), Value::String(format!("{s}x"))),
        Value::Number(n) => push(path.into(), Value::from(n.as_u64().map(|x| x + 1).unwrap_or(1))),
        Value::Bool(b) => push(path.into(), Value::Bool(!b)),
        Value::Null => {}
        Value::Array(items) => {
            if let Some(first) = items.first() {
                let mut more = items.clone();
                more.push(first.clone());
                push(format!("{path}+"), Value::Array(more));
                push(format!("{path}-"), Value::Array(items[1..].to_vec()));
            }
            for (i, item) in items.iter().enumerate() {
                let mut inner = Vec::new();
                mutations(item, &format!("{path}[{i}]"), &mut inner);
                for (p, changed) in inner {
                    let mut copy = items.clone();
                    copy[i] = changed;
                    out.push((p, Value::Array(copy)));
                }
            }
        }
        Value::Object(map) => {
            for (k, child) in map {
                let mut inner = Vec::new();
                mutations(child, &format!("{path}.{k}"), &mut inner);
                for (p, changed) in inner {
                    let mut copy = map.clone();
                    copy.insert(k.clone(), changed);
                    out.push((p, Value::Object(copy)));
                }
            }
        }
    }
}

#[test]
fn every_part_of_the_claim_changed_in_turn_changes_the_key() {
    let claim = full_claim();
    let k = key_of(&claim);
    assert_eq!(key_of(&claim.clone()), k, "the same claim, the same key");
    assert!(k.0.starts_with("sha256:") && k.0.len() == 7 + 64, "{}", k.0);
    let value = serde_json::to_value(&claim).unwrap();
    let mut all = Vec::new();
    mutations(&value, "", &mut all);
    let mut checked = 0;
    for (path, changed) in &all {
        // A changed enum tag is no claim at all; every other change is one.
        let Ok(other) = serde_json::from_value::<CanonicalClaim>(changed.clone()) else { continue };
        assert_ne!(other, claim, "{path} changes the claim");
        assert_ne!(key_of(&other), k, "changing {path} keeps the key");
        checked += 1;
    }
    assert!(checked >= 60, "only {checked} of {} changes were claims", all.len());
}

/// The brief's list, each named: every one changes the key.
#[test]
fn each_part_the_brief_names_changes_the_key() {
    let claim = full_claim();
    let k = key_of(&claim);
    let cases: Vec<(&str, Box<dyn Fn(&mut CanonicalClaim)>)> = vec![
        ("the old version's closure", Box::new(|c| c.closures.before = "sha256:other".into())),
        ("the new version's closure", Box::new(|c| c.closures.after = "sha256:other".into())),
        ("the subject of the preservation contract", Box::new(|c| c.contract.subject = "shop.Pricing#totalOf".into())),
        ("a required observation", Box::new(|c| { c.contract.required.pop(); })),
        ("an input's derivation", Box::new(|c| c.contract.inputs[0].derivation = jvmcontract::spec::Derivation::Stated { expression: "q".into() })),
        ("the domain's input-object bound", Box::new(|c| c.domain.as_mut().unwrap().bounds.after.input_objects += 1)),
        ("the domain's allocation bound", Box::new(|c| c.domain.as_mut().unwrap().bounds.before.allocations += 1)),
        ("the domain's policy: who may be null", Box::new(|c| { c.domain.as_mut().unwrap().nullable.clear(); })),
        ("the domain's policy: who may alias", Box::new(|c| { c.domain.as_mut().unwrap().may_alias.clear(); })),
        ("the constructor a domain makes its inputs with", Box::new(|c| c.domain.as_mut().unwrap().made_by = jvmcontract::spec::Construction::Constructors { calls: vec!["after: shop.Quote.of(long, int)".into()] })),
        ("the domain made field by field", Box::new(|c| c.domain.as_mut().unwrap().made_by = jvmcontract::spec::Construction::FieldByField)),
        ("an observation's payload", Box::new(|c| if let Some(jvmcontract::spec::Observation::Effect { payload, .. }) = c.observations.iter_mut().find(|o| matches!(o, jvmcontract::spec::Observation::Effect { .. })) { payload.pop(); })),
        ("the observation policy: an identity relation dropped", Box::new(|c| c.observations.retain(|o| !matches!(o, jvmcontract::spec::Observation::Identity { .. })))),
        ("the correspondence", Box::new(|c| c.correspondence.as_mut().unwrap().inputs[0].new = "new.q.amount.cents + 1".into())),
        ("the correspondence dropped", Box::new(|c| c.correspondence = None)),
        ("the unwinding bound", Box::new(|c| c.bounds.unwind += 1)),
        ("the array bound", Box::new(|c| c.bounds.max_array_length -= 1)),
        ("the environment model: a recording stub's outcomes", Box::new(|c| c.environment.as_mut().unwrap().calls[0].outcomes.push("org.springframework.kafka.KafkaException".into()))),
        ("the environment model: the trace bound", Box::new(|c| c.environment.as_mut().unwrap().trace_bound += 1)),
        ("the environment model dropped", Box::new(|c| c.environment = None)),
        ("a contract the proof rests on", Box::new(|c| c.assumptions[1] = "contract: Math.abs(long) (tested)".into())),
        ("a stub", Box::new(|c| c.assumptions.push("shop.Rates#rate taken as one function in both versions".into()))),
        ("the assumptions of a callee proof the result reused", Box::new(|c| c.assumptions[0] = "shop.Pricing#discount proved equivalent under claim sha256:bb".into())),
        ("the models", Box::new(|c| c.tools.models = "none".into())),
        ("the JDK", Box::new(|c| c.tools.jdk = "sha256:another-build".into())),
        ("the gap mode", Box::new(|c| c.tools.checker = "native assume; shared callees".into())),
        ("the checker's configuration", Box::new(|c| c.tools.checker = "native strict".into())),
        ("the binary, rebuilt with no version bump", Box::new(|c| c.tools.binary = "sha256:rebuilt".into())),
    ];
    for (what, change) in cases {
        let mut other = claim.clone();
        change(&mut other);
        assert_ne!(other, claim, "{what} is a change");
        assert_ne!(key_of(&other), k, "changing {what} keeps the key");
    }
}

#[test]
fn the_key_does_not_depend_on_how_the_claim_was_written() {
    let claim = full_claim();
    let value = serde_json::to_value(&claim).unwrap();
    // The same claim parsed from JSON with its fields in reverse order.
    fn reversed(v: &Value) -> Value {
        match v {
            Value::Object(map) => {
                let mut text = String::from("{");
                let entries: Vec<_> = map.iter().rev().collect();
                for (i, (k, child)) in entries.iter().enumerate() {
                    if i > 0 {
                        text.push(',');
                    }
                    text.push_str(&format!("{}:{}", Value::String((*k).clone()), reversed(child)));
                }
                text.push('}');
                serde_json::from_str(&text).unwrap()
            }
            Value::Array(items) => Value::Array(items.iter().map(reversed).collect()),
            other => other.clone(),
        }
    }
    let again: CanonicalClaim = serde_json::from_value(reversed(&value)).unwrap();
    assert_eq!(key_of(&again), key_of(&claim));
    assert_eq!(cache::canonical(&serde_json::json!({"b": [1, {"d": "x", "c": true}], "a": null})), r#"{"a":null,"b":[1,{"c":true,"d":"x"}]}"#);
}

#[test]
fn a_field_the_projection_does_not_know_makes_the_claim_uncacheable() {
    let value = serde_json::to_value(full_claim()).unwrap();
    assert!(cache::projection(&value).is_ok());
    // A field another stream might add to the domain, to an observation, or at the top.
    let mut domain = value.clone();
    domain["domain"]["ownership"] = Value::from("unique");
    let mut observation = value.clone();
    observation["observations"][0]["projection"] = Value::from("serialized");
    let mut top = value.clone();
    top["heap_model"] = Value::from(2);
    for (changed, path) in [(domain, "domain.ownership"), (observation, "observations[].projection"), (top, "heap_model")] {
        let refused = cache::projection(&changed).expect_err(path);
        assert!(refused.what.contains("uncacheable") && refused.what.contains(path), "{}", refused.what);
    }
}

#[test]
fn a_part_not_computed_makes_the_claim_uncacheable() {
    let claim = full_claim();
    for (what, change) in [
        ("closures.before", Box::new(|c: &mut CanonicalClaim| c.closures.before.clear()) as Box<dyn Fn(&mut CanonicalClaim)>),
        ("closures.after", Box::new(|c| c.closures.after = " ".into())),
        ("tools.binary", Box::new(|c| c.tools.binary.clear())),
        ("tools.jdk", Box::new(|c| c.tools.jdk.clear())),
        ("tools.models", Box::new(|c| c.tools.models.clear())),
        ("tools.checker", Box::new(|c| c.tools.checker.clear())),
    ] {
        let mut other = claim.clone();
        change(&mut other);
        let refused = cache::key(&other).expect_err(what);
        assert!(refused.what.contains(what) && refused.what.contains("not computed"), "{}", refused.what);
    }
}

#[test]
fn the_binary_identity_is_the_digest_of_its_bytes() {
    let exe = std::fs::read(std::env::current_exe().unwrap()).unwrap();
    assert_eq!(proof_cache::binary(), format!("sha256:{}", jvmcontract::digest::sha256_hex(&exe)), "not a version number");
    let tools = proof_cache::tools(false, "native strict");
    assert_eq!(tools.models, "none");
    assert_ne!(proof_cache::tools(true, "native strict").models, tools.models);
    assert!(tools.jdk.starts_with("sha256:"), "a JDK is found: {}", tools.jdk);
}

/// The version digests of `twice` in two builds, with the constructors of `roots` among its roots.
fn version_digests(a: &Path, b: &Path, roots: &[MemberRef]) -> (String, String) {
    let none = Configuration::none();
    (closure::version_digest(&cp(a), roots, &none), closure::version_digest(&cp(b), roots, &none))
}

#[test]
fn the_code_changes_that_no_body_shows_change_the_claim() {
    // A new dispatch target, with no method body changed.
    let circle = "package k;\npublic class Circle extends Shape { public long area() { return 3; } }\n";
    let (Some(a), Some(b)) = (base("claim-dispatch-a", &[]), base("claim-dispatch-b", &[("k/Circle.java", circle)])) else { return };
    let (x, y) = version_digests(&a, &b, &[twice()]);
    assert_ne!(x, y, "a new dispatch target");
    // An unrelated change keeps it.
    let other = OTHER.replace("return 1", "return 2");
    let Some(c) = base("claim-unrelated", &[("k/Other.java", &other)]) else { return };
    assert_eq!(version_digests(&a, &c, &[twice()]).0, version_digests(&a, &c, &[twice()]).1, "an unrelated change");
    // The constructor the domain makes its inputs with: outside `twice`'s own closure, so it is a root of its own.
    let square = SQUARE.replace("this.side = side;", "this.side = side + 0 * side;");
    let Some(d) = base("claim-constructor", &[("k/Square.java", &square)]) else { return };
    let constructor = MemberRef::new("k/Square", "<init>", "(J)V");
    assert_eq!(version_digests(&a, &d, &[twice()]).0, version_digests(&a, &d, &[twice()]).1, "twice alone never runs the constructor");
    let (x, y) = version_digests(&a, &d, &[twice(), constructor]);
    assert_ne!(x, y, "the constructor the inputs are made with");
}

#[test]
fn a_framework_annotation_or_configuration_value_changes_the_claim() {
    let moved = CONTROLLER.replace("\"/quotes\"", "\"/quote\"");
    let (Some(a), Some(b)) = (spring("claim-annotation-a", CONTROLLER), spring("claim-annotation-b", &moved)) else { return };
    let none = Configuration::none();
    assert_ne!(closure::version_digest(&cp(&a), &[quote()], &none), closure::version_digest(&cp(&b), &[quote()], &none), "the route");
    let one = Configuration::of(&[("application.properties", b"shop.rate=10\n")]);
    let two = Configuration::of(&[("application.properties", b"shop.rate=20\n")]);
    assert_ne!(closure::version_digest(&cp(&a), &[quote()], &one), closure::version_digest(&cp(&a), &[quote()], &two), "a configuration value");
}

fn record(claim: &CanonicalClaim, verdict: Verdict, witness: Option<&str>) -> ResultRecord {
    let outcome = Outcome { verdict, domain: "q: a shop.Quote made by its constructor".into(), accounting: Vec::new(), witness: witness.map(str::to_string) };
    ResultRecord { key: key_of(claim), outcome, provenance: "lib/tests/summaries.rs".into() }
}

fn empty_cache(name: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("summaries-cache").join(name);
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

#[test]
fn the_cache_gives_back_what_it_stored_for_that_key_only() {
    let dir = empty_cache("round-trip");
    let claim = full_claim();
    let verified = record(&claim, Verdict::Verified, None);
    assert_eq!(cache::lookup(&dir, &verified.key).unwrap(), None, "an empty cache misses");
    cache::store(&dir, &verified).unwrap();
    assert_eq!(cache::lookup(&dir, &verified.key).unwrap(), Some(verified.clone()));
    let mut other = claim.clone();
    other.bounds.unwind += 1;
    assert_eq!(cache::lookup(&dir, &key_of(&other)).unwrap(), None, "another claim misses");
    // A refutation, with the witness its reuse replays.
    let refuted = record(&other, Verdict::Refuted, Some("total(q=Quote[cents=1, quantity=2])"));
    cache::store(&dir, &refuted).unwrap();
    assert_eq!(cache::lookup(&dir, &refuted.key).unwrap(), Some(refuted));
    let leftovers: Vec<_> = walk_files(&dir).into_iter().filter(|p| !p.extension().is_some_and(|e| e == "json")).collect();
    assert!(leftovers.is_empty(), "no temporary file is left: {leftovers:?}");
    assert!(cache::lookup(&dir, &ClaimKey("md5:1".into())).is_err(), "not a key");
}

fn walk_files(dir: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    for e in std::fs::read_dir(dir).unwrap().filter_map(Result::ok) {
        let p = e.path();
        if p.is_dir() {
            out.extend(walk_files(&p));
        } else {
            out.push(p);
        }
    }
    out
}

#[test]
fn an_unresolved_result_or_a_refutation_without_a_witness_is_never_stored() {
    let dir = empty_cache("never");
    let claim = full_claim();
    let unresolved = record(&claim, Verdict::Unresolved, None);
    assert!(cache::store(&dir, &unresolved).unwrap_err().what.contains("unresolved"));
    let bare = record(&claim, Verdict::Refuted, None);
    assert!(cache::store(&dir, &bare).unwrap_err().what.contains("witness"));
    assert!(walk_files(&dir).is_empty(), "nothing was written");
}

#[test]
fn an_entry_that_is_corrupt_for_another_key_or_unresolved_is_a_miss() {
    let dir = empty_cache("miss");
    let claim = full_claim();
    let verified = record(&claim, Verdict::Verified, None);
    cache::store(&dir, &verified).unwrap();
    let path = walk_files(&dir).pop().unwrap();
    // Written by hand: a record moved under another key, one made unresolved, and half a record.
    let mut moved = verified.clone();
    moved.key = ClaimKey(format!("sha256:{}", "0".repeat(64)));
    std::fs::write(&path, serde_json::to_string(&moved).unwrap()).unwrap();
    assert_eq!(cache::lookup(&dir, &verified.key).unwrap(), None, "a record for another key");
    let mut unresolved = verified.clone();
    unresolved.outcome.verdict = Verdict::Unresolved;
    std::fs::write(&path, serde_json::to_string(&unresolved).unwrap()).unwrap();
    assert_eq!(cache::lookup(&dir, &verified.key).unwrap(), None, "an unresolved record");
    std::fs::write(&path, "{\"key\":").unwrap();
    assert_eq!(cache::lookup(&dir, &verified.key).unwrap(), None, "half a record");
}

// S2b: the proof cache in a regression proof (`equivalence::run` with `--cache`).

use jvmcontract::equivalence;
use jvmcontract::spec::cache::Reuse;

const FEE: &str = r#"package c;
public class Fee {
    static int base(int n) { return n * 3; }
    public static int fee(int n) { return n < 0 ? 0 : base(n) + 1; }
}
"#;

/// `FEE` with `base` rewritten, behaviour kept.
const FEE_SUMMED: &str = r#"package c;
public class Fee {
    static int base(int n) { return n + n + n; }
    public static int fee(int n) { return n < 0 ? 0 : base(n) + 1; }
}
"#;

/// `FEE` rewritten another way, behaviour kept: another closure.
const FEE_SHIFTED: &str = r#"package c;
public class Fee {
    static int base(int n) { return (n << 1) + n; }
    public static int fee(int n) { return n < 0 ? 0 : base(n) + 1; }
}
"#;

/// `FEE` with a regression above 100.
const FEE_WRONG: &str = r#"package c;
public class Fee {
    static int base(int n) { return n * 3; }
    public static int fee(int n) { return n < 0 ? 0 : base(n) + (n > 100 ? 2 : 1); }
}
"#;

fn fee(name: &str, source: &str) -> Option<PathBuf> {
    compile(name, &[("c/Fee.java", source)])
}

/// A native regression check of `c.Fee#fee` with the cache `cache`, in a work directory of its own.
fn check(before: &Path, after: &Path, cache: &Path, name: &str, change: impl FnOnce(&mut equivalence::Options)) -> equivalence::Outcome {
    let mut options = equivalence::Options::new(before, after, "c.Fee#fee");
    options.engine = jvmcontract::Engine::Native;
    options.timeout_seconds = 120;
    options.cache = Some(cache.to_path_buf());
    let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("summaries-equivalence").join(name);
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    change(&mut options);
    equivalence::run(&options).unwrap()
}

fn exact_key(outcome: &equivalence::Outcome) -> Option<ClaimKey> {
    match &outcome.reuse {
        Some(Reuse::Exact { key, from }) => {
            assert!(from.contains("--engine native"), "the run it came from: {from}");
            Some(key.clone())
        }
        _ => None,
    }
}

#[test]
fn a_rerun_of_the_same_claim_is_an_exact_hit() {
    let (Some(before), Some(after)) = (fee("fee-hit-before", FEE), fee("fee-hit-after", FEE_SUMMED)) else { return };
    let dir = empty_cache("hit");
    let cold = check(&before, &after, &dir, "hit-cold", |_| {});
    assert_eq!(cold.verdict, jvmcontract::Verdict::Verified, "{}", cold.output);
    assert!(cold.reuse.is_none() && cold.search.is_some(), "the first run proves");
    assert!(cold.output.contains("stored in the proof cache"), "{}", cold.output);
    assert_eq!(walk_files(&dir).len(), 1, "one entry");
    // Another work directory: where a check works is not part of its claim.
    let warm = check(&before, &after, &dir, "hit-warm", |_| {});
    assert_eq!(warm.verdict, jvmcontract::Verdict::Verified, "{}", warm.output);
    let key = exact_key(&warm).expect("an exact reuse");
    assert!(warm.output.contains(&format!("an exact hit of claim {}", key.0)), "{}", warm.output);
    assert!(warm.search.is_none(), "no checker ran");
    assert_eq!(warm.stated, cold.stated, "the same statement, gap mode and vacuity included");
    assert_eq!(warm.stated.as_ref().and_then(|s| s.gap_mode), Some(jvmcontract::bmc::gaps::GapMode::Strict));
    assert_eq!((warm.vacuous.clone(), warm.shared.clone()), (cold.vacuous.clone(), cold.shared.clone()));
    assert!(warm.proof.as_deref().is_some_and(|p| p.starts_with("reused from the proof cache")), "{:?}", warm.proof);
    // The result as it was reported, without what the cache said then.
    let reported: String = cold.output.lines().filter(|l| !l.starts_with("note: the proof cache has no result") && !l.starts_with("note: stored in the proof cache")).map(|l| format!("{l}\n")).collect();
    assert!(warm.output.starts_with(&reported) && !warm.output.contains("has no result"), "{}", warm.output);
}

#[test]
fn a_changed_version_or_setting_is_a_miss() {
    let (Some(before), Some(after), Some(other)) = (fee("fee-miss-before", FEE), fee("fee-miss-after", FEE_SUMMED), fee("fee-miss-other", FEE_SHIFTED)) else { return };
    let dir = empty_cache("miss-claim");
    let cold = check(&before, &after, &dir, "miss-cold", |_| {});
    assert_eq!(cold.verdict, jvmcontract::Verdict::Verified, "{}", cold.output);
    let changes: Vec<(&str, PathBuf, Box<dyn FnOnce(&mut equivalence::Options)>)> = vec![
        ("another new version, behaviour kept", other.clone(), Box::new(|_| {})),
        ("another unwinding bound", after.clone(), Box::new(|o| o.unwind += 1)),
        ("another array bound", after.clone(), Box::new(|o| o.max_array_length += 1)),
        ("a scope", after.clone(), Box::new(|o| o.unchanged_unless = Some("n > 5".into()))),
        ("another gap mode", after.clone(), Box::new(|o| o.gaps = jvmcontract::bmc::gaps::GapMode::Assume)),
        ("no models", after.clone(), Box::new(|o| o.models = false)),
        ("no shared callees", after.clone(), Box::new(|o| o.shared_callees = false)),
    ];
    for (i, (what, version, change)) in changes.into_iter().enumerate() {
        let run = check(&before, &version, &dir, &format!("miss-{i}"), change);
        assert!(exact_key(&run).is_none(), "{what} is another claim:\n{}", run.output);
        assert!(run.output.contains("the proof cache has no result for this claim"), "{what}:\n{}", run.output);
    }
}

#[test]
fn a_refuted_hit_replays_its_witness_first() {
    let (Some(before), Some(after)) = (fee("fee-refuted-before", FEE), fee("fee-refuted-after", FEE_WRONG)) else { return };
    let dir = empty_cache("refuted");
    let cold = check(&before, &after, &dir, "refuted-cold", |_| {});
    assert_eq!(cold.verdict, jvmcontract::Verdict::Violation, "{}", cold.output);
    assert!(cold.output.contains("stored in the proof cache"), "{}", cold.output);
    let warm = check(&before, &after, &dir, "refuted-warm", |_| {});
    assert_eq!(warm.verdict, jvmcontract::Verdict::Violation, "{}", warm.output);
    assert!(exact_key(&warm).is_some(), "an exact reuse:\n{}", warm.output);
    assert!(warm.output.contains("its witness replayed again on both versions in the interpreter, and reproduces"), "{}", warm.output);
    let (c, w) = (cold.counterexample.as_ref().unwrap(), warm.counterexample.as_ref().unwrap());
    assert_eq!((&w.input, &w.before, &w.after, &w.values), (&c.input, &c.before, &c.after, &c.values));
    assert_eq!(serde_json::to_value(w).unwrap(), serde_json::to_value(c).unwrap(), "the counterexample, typed inputs and calls included");
    assert!(warm.replay.as_ref().is_some_and(|r| r.reproduced));
    // A stored witness that no longer reproduces (here, written by hand: an input both versions agree on) is never
    // the result: the claim is proved again.
    let path = walk_files(&dir).pop().unwrap();
    let mut entry: Value = serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
    let mut witness: Value = serde_json::from_str(entry["outcome"]["witness"].as_str().unwrap()).unwrap();
    witness[0]["value"] = Value::from(1);
    entry["outcome"]["witness"] = Value::String(witness.to_string());
    std::fs::write(&path, entry.to_string()).unwrap();
    let again = check(&before, &after, &dir, "refuted-again", |_| {});
    assert!(again.reuse.is_none() && again.search.is_some(), "proved again:\n{}", again.output);
    assert!(again.output.contains("no longer reproduces"), "{}", again.output);
    assert_eq!(again.verdict, jvmcontract::Verdict::Violation, "{}", again.output);
}

#[test]
fn a_stored_witness_reads_back_as_the_arguments_it_was() {
    use jvmcontract::classfile::Type;
    use jvmcontract::interp::Value as V;
    use jvmcontract::jbmc::Argument;
    let types = [Type::Int, Type::Long, Type::Boolean, Type::Char, Type::Double, Type::Array(Box::new(Type::Byte)), Type::Array(Box::new(Type::Int))];
    let witness = r#"[{"name":"a","type":"int","value":-7},{"name":"b","type":"long","value":"-9223372036854775808"},
        {"name":"c","type":"boolean","value":true},{"name":"d","type":"char","value":65535},{"name":"e","type":"double","value":"-0.0"},
        {"name":"f","type":"byte[]","value":[-128,0,127]},{"name":"g","type":"int[]","value":null}]"#;
    let arguments = proof_cache::witness_arguments(&types, witness).expect("reads back");
    assert_eq!(arguments[..4], [Argument::Scalar(V::Int(-7)), Argument::Scalar(V::Long(i64::MIN)), Argument::Scalar(V::Int(1)), Argument::Scalar(V::Int(65535))]);
    assert!(matches!(arguments[4], Argument::Scalar(V::Double(d)) if d == 0.0 && d.is_sign_negative()));
    assert_eq!(arguments[5..], [Argument::Array(vec![V::Int(-128), V::Int(0), V::Int(127)]), Argument::Null]);
    assert_eq!(proof_cache::witness_arguments(&types[..2], witness), None, "one value for each parameter, no more");
    assert_eq!(proof_cache::witness_arguments(&[Type::Int], r#"[{"name":"a","type":"int","value":"x"}]"#), None, "not an int");
}

#[test]
fn the_cache_is_used_with_the_own_checker_only() {
    let (Some(before), Some(after)) = (fee("fee-auto-before", FEE), fee("fee-auto-after", FEE_SUMMED)) else { return };
    let dir = empty_cache("auto");
    // Under auto the own checker decides this one, so JBMC never runs; the claim is still one JBMC may decide.
    let run = check(&before, &after, &dir, "auto", |o| o.engine = jvmcontract::Engine::Auto);
    assert_eq!(run.verdict, jvmcontract::Verdict::Verified, "{}", run.output);
    assert!(run.output.contains("the proof cache is not used") && run.output.contains("JBMC"), "{}", run.output);
    assert!(walk_files(&dir).is_empty(), "nothing stored");
}
