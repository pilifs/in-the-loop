//! The summaries stream's tests (`llm-dlc/loops/foundations-summaries.md`): code closure digests (S1), over small
//! Java builds compiled with `javac` at test time. Each case compiles a base build and a variant, and checks that the
//! closure of a target changes exactly when something its proof reads changes, and names which part did.

use std::collections::BTreeSet;
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
    // Two entries: the check's, and that of `base`, the changed helper it shares once proved first (S4).
    assert_eq!(walk_files(&dir).len(), 2, "two entries");
    assert!(cold.output.contains("Fee.base, changed: its two versions have the same outcome"), "{}", cold.output);
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
    let reported: String = cold.output.lines().filter(|l| !l.starts_with("note: the proof cache has no result") && !l.starts_with("note: stored in the proof cache") && !l.starts_with("note: the proof cache took")).map(|l| format!("{l}\n")).collect();
    assert!(warm.output.starts_with(&reported) && !warm.output.contains("has no result"), "{}", warm.output);
    // Each run names its own time with the cache, once, apart from the checker's: the stored report has none.
    for run in [&cold, &warm] {
        let timings: Vec<&str> = run.output.lines().filter(|l| l.starts_with("note: the proof cache took")).collect();
        assert_eq!(timings.len(), 1, "{}", run.output);
        assert!(timings[0].contains(" s to compute this claim's key (both versions' closures, the harness's digest and the tools') and "), "{}", timings[0]);
    }
    assert!(warm.output.ends_with(" s to look it up\n"), "this run's, after the reuse: {}", warm.output);
    assert_eq!(cold.output.matches("note: Fee.base's own check took ").count(), 1, "{}", cold.output);
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

// S3: change impact.

use jvmcontract::impact::{self, Claim, ClaimImpact};

const MONEY: &str = "package k;\npublic record Money(long cents) { public Money { if (cents < 0) throw new IllegalArgumentException(); } }\n";
const TILL: &str = "package k;\npublic final class Till { public static long add(Money a, Money b) { return a.cents() + b.cents(); } }\n";

fn report(a: &Path, b: &Path, claims: &[Claim]) -> Vec<ClaimImpact> {
    let none = Configuration::none();
    impact::impact(&cp(a), &cp(b), &none, &none, claims).claims
}

fn status(c: &ClaimImpact) -> &'static str {
    match c.verdict {
        impact::Verdict::Unchanged => "unchanged",
        impact::Verdict::Invalidated { .. } => "invalidated",
        impact::Verdict::Unresolved { .. } => "unresolved",
    }
}

fn parts(c: &ClaimImpact) -> Vec<String> {
    match &c.verdict {
        impact::Verdict::Invalidated { changes, .. } => changes.iter().map(|p| format!("{p:?}")).collect(),
        _ => Vec::new(),
    }
}

#[test]
fn the_impact_report_names_the_claims_a_change_invalidates_and_the_parts_that_changed() {
    let changed = PRICING.replace("gross / RATE", "gross / RATE + 0 * gross");
    let (Some(a), Some(b)) = (base("impact-a", &[]), base("impact-b", &[("k/Pricing.java", &changed)])) else { return };
    let claims = [Claim::new("k.Pricing#total"), Claim::new("k.Pricing#discount"), Claim::new("k.Other#one"), Claim::new("k.Shape#twice")];
    let out = report(&a, &b, &claims);
    assert_eq!(out.iter().map(status).collect::<Vec<_>>(), ["invalidated", "invalidated", "unchanged", "unchanged"]);
    let discount = PartChange::Changed { part: "method k/Pricing.discount(J)J".into() };
    assert_eq!(parts(&out[0]), [format!("{discount:?}")], "total is invalidated by its callee, and nothing else");
    assert_eq!(parts(&out[1]), [format!("{discount:?}")]);
    // The same build twice invalidates nothing.
    assert!(report(&a, &a, &claims).iter().all(|c| status(c) == "unchanged"));
}

#[test]
fn a_renamed_target_a_target_gone_and_one_not_in_the_first_build() {
    let renamed = PRICING.replace("long total(", "long net(");
    let (Some(a), Some(b)) = (base("impact-rename-a", &[]), base("impact-rename-b", &[("k/Pricing.java", &renamed)])) else { return };
    let mut moved = Claim::new("k.Pricing#net");
    moved.before_target = Some("k.Pricing#total".into());
    let out = report(&a, &b, &[moved, Claim::new("k.Pricing#total"), Claim::new("k.Pricing#net"), Claim::new("k.Nowhere#x")]);
    assert_eq!(out.iter().map(status).collect::<Vec<_>>(), ["invalidated", "invalidated", "unresolved", "unresolved"]);
    assert!(parts(&out[0]).iter().any(|p| p.contains("Removed") && p.contains("k/Pricing.total(J)J")), "{:?}", parts(&out[0]));
    assert!(parts(&out[0]).iter().any(|p| p.contains("Added") && p.contains("k/Pricing.net(J)J")), "{:?}", parts(&out[0]));
    let impact::Verdict::Invalidated { reason: Some(reason), .. } = &out[1].verdict else { panic!("{:?}", out[1]) };
    assert!(reason.contains("gone from the second build"), "{reason}");
}

#[test]
fn a_record_input_s_constructor_is_part_of_the_claim_s_code() {
    let checked = MONEY.replace("cents < 0", "cents < -1");
    let (Some(a), Some(b)) = (base("impact-record-a", &[("k/Money.java", MONEY), ("k/Till.java", TILL)]), base("impact-record-b", &[("k/Money.java", &checked), ("k/Till.java", TILL)])) else { return };
    let add = MemberRef::new("k/Till", "add", "(Lk/Money;Lk/Money;)J");
    assert!(changes(&a, &b, &add).is_empty(), "add's own closure never runs the constructor");
    let roots = impact::roots(&cp(&a), "k.Till#add").unwrap();
    assert_eq!(roots, [add, MemberRef::new("k/Money", "<init>", "(J)V")], "the target and the record's canonical constructor");
    let out = report(&a, &b, &[Claim::new("k.Till#add")]);
    assert_eq!(status(&out[0]), "invalidated");
    assert_eq!(parts(&out[0]), [format!("{:?}", PartChange::Changed { part: "method k/Money.<init>(J)V".into() })]);
    // The verdict is the cache key's: the version digest over the same roots differs.
    let (x, y) = version_digests(&a, &b, &roots);
    assert_ne!(x, y);
}

#[test]
fn claims_are_read_from_build_py_s_records_as_they_are() {
    let plan: Value = serde_json::json!([{"example": "023", "claim": {"approach": "B11", "target": "p.A#f"}},
        {"example": "128", "claim": {"target": "p.B#g", "previousSymbol": "p.C#g"}}]);
    let record: Value = serde_json::json!({"id": "0123abcd", "example": "031", "statement": {"target": "p.D#h"}});
    let own: Value = serde_json::json!({"claims": [{"id": "x", "target": "p.E#i", "beforeTarget": "p.E#j", "status": "unchanged"}]});
    let claims: Vec<Claim> = [plan, record, own].iter().flat_map(|v| impact::claims_from_json(v).unwrap()).collect();
    let expected = [("023", "p.A#f", None), ("128", "p.B#g", Some("p.C#g")), ("031", "p.D#h", None), ("x", "p.E#i", Some("p.E#j"))];
    assert_eq!(claims, expected.map(|(id, t, b)| Claim { id: id.into(), target: t.into(), before_target: b.map(str::to_string) }));
    assert!(impact::claims_from_json(&serde_json::json!([{"example": "1"}])).is_err(), "a claim with no target is refused");
}

// S4: a changed helper proved equivalent, shared in its callers.

use jvmcontract::statement::{AssumptionKind, Basis};

const SPLIT: &str = r#"package h;
public class Split {
    static long share(long total, int ways) { return ways <= 0 ? 0 : total / ways; }
    public static long perSeat(long total, int seats) { return share(total, seats) + 1; }
    public static long perRow(long total, int rows) { return rows > 100 ? 0 : share(total, rows) * 2; }
}
"#;

/// `SPLIT` with the helper written the other way round: the same outcome on every input.
const SPLIT_REFACTORED: &str = r#"package h;
public class Split {
    static long share(long total, int ways) {
        if (ways < 1) return 0;
        return total / ways;
    }
    public static long perSeat(long total, int seats) { return share(total, seats) + 1; }
    public static long perRow(long total, int rows) { return rows > 100 ? 0 : share(total, rows) * 2; }
}
"#;

/// `SPLIT` with the helper rounding up: a regression wherever the division leaves a remainder.
const SPLIT_ROUNDED_UP: &str = r#"package h;
public class Split {
    static long share(long total, int ways) {
        if (ways < 1) return 0;
        return (total + ways - 1) / ways;
    }
    public static long perSeat(long total, int seats) { return share(total, seats) + 1; }
    public static long perRow(long total, int rows) { return rows > 100 ? 0 : share(total, rows) * 2; }
}
"#;

/// `SPLIT` with the helper changed only above a thousand ways, which `perRow` never asks for.
const SPLIT_CAPPED: &str = r#"package h;
public class Split {
    static long share(long total, int ways) {
        if (ways < 1 || ways > 1000) return 0;
        return total / ways;
    }
    public static long perSeat(long total, int seats) { return share(total, seats) + 1; }
    public static long perRow(long total, int rows) { return rows > 100 ? 0 : share(total, rows) * 2; }
}
"#;

fn split(name: &str, source: &str) -> Option<PathBuf> {
    compile(name, &[("h/Split.java", source)])
}

/// A native regression check of `target` with the cache `cache`.
fn check_target(before: &Path, after: &Path, cache: &Path, name: &str, target: &str) -> equivalence::Outcome {
    check(before, after, cache, name, |o| o.target = target.into())
}

/// The `callee` assumptions of a result: (text, basis, id).
fn callee_assumptions(outcome: &equivalence::Outcome) -> Vec<(String, Basis, Option<String>)> {
    outcome.stated.iter().flat_map(|s| s.assumptions.iter()).filter(|a| a.kind == AssumptionKind::Callee).map(|a| (a.text.clone(), a.basis, a.id.clone())).collect()
}

#[test]
fn a_changed_helper_proved_once_is_one_function_in_each_of_its_callers() {
    let (Some(before), Some(after)) = (split("split-before", SPLIT), split("split-refactored", SPLIT_REFACTORED)) else { return };
    let dir = empty_cache("split");
    let first = check_target(&before, &after, &dir, "split-per-seat", "h.Split#perSeat");
    assert_eq!(first.verdict, jvmcontract::Verdict::Verified, "{}", first.output);
    assert!(first.output.contains("note: Split.share, changed: its two versions have the same outcome, result or exception, on every input, proved now and stored in the proof cache (claim sha256:"), "{}", first.output);
    let assumed = callee_assumptions(&first);
    assert_eq!(assumed.len(), 1, "{assumed:?}");
    let (text, basis, id) = &assumed[0];
    let key = id.clone().expect("the helper proof's claim key");
    assert_eq!(*basis, Basis::Proved);
    assert!(text.starts_with("Split.share(long, int), changed, is one function in both versions") && text.contains(&key), "{text}");
    assert_eq!(first.shared, vec!["Split.share".to_string()]);
    let proof = first.proof.clone().unwrap_or_default();
    assert!(proof.contains(&format!("Split.share changed, its two versions proved to have the same outcome on every input (claim {key}), and taken as one function in both")), "{proof}");
    // The one function is the helper's new version: the previous version's calls of it were redirected there.
    let substituted = std::fs::read(first.work.join("substituted-classes/before/h/Split.class")).expect("the previous version's class, redirected");
    let class = jvmcontract::classfile::ClassFile::parse(&substituted).unwrap();
    let calls: Vec<String> = class
        .methods
        .iter()
        .filter_map(|m| m.code.as_ref())
        .flat_map(|c| c.instructions().unwrap())
        .filter_map(|(_, i)| match i {
            jvmcontract::classfile::Insn::InvokeStatic(i) => class.pool.member(i).ok().map(|m| format!("{}.{}", m.owner, m.name)),
            _ => None,
        })
        .collect();
    assert_eq!(calls, vec!["h/Split.share".to_string(), "h/Split.share".to_string()], "perSeat's and perRow's calls");
    // The helper's proof is in the cache under its own claim, the one a check of the helper alone has.
    assert!(cache::lookup(&dir, &ClaimKey(key.clone())).unwrap().is_some_and(|r| r.outcome.verdict == Verdict::Verified));
    let alone = check_target(&before, &after, &dir, "split-share", "h.Split#share(long, int)");
    assert_eq!(exact_key(&alone), Some(ClaimKey(key.clone())), "{}", alone.output);
    // Another caller of the helper reuses that proof, and proves nothing of the helper again.
    let second = check_target(&before, &after, &dir, "split-per-row", "h.Split#perRow");
    assert_eq!(second.verdict, jvmcontract::Verdict::Verified, "{}", second.output);
    assert!(second.output.contains(&format!("found in the proof cache (claim {key}); one function in both versions")), "{}", second.output);
    // The helper's own check is timed apart from the caller's, just before what came of it.
    let timed = second.output.lines().position(|l| l.starts_with("note: Split.share's own check took ") && l.ends_with(" s")).expect("the helper's time");
    assert!(second.output.lines().nth(timed + 1).is_some_and(|l| l.starts_with("note: Split.share, changed: ")), "{}", second.output);
    assert_eq!(callee_assumptions(&second).iter().map(|a| a.2.clone()).collect::<Vec<_>>(), vec![Some(key.clone())]);
    // The helper proof is part of each caller's claim: its stored statement names it.
    let rerun = check_target(&before, &after, &dir, "split-per-seat-again", "h.Split#perSeat");
    assert!(exact_key(&rerun).is_some(), "{}", rerun.output);
    assert_eq!(callee_assumptions(&rerun), assumed, "{:#?}\n{}", rerun.stated, rerun.output);
}

/// The claim keys a cache directory holds, from its entries' file names.
fn stored_keys(dir: &Path) -> BTreeSet<String> {
    let mut keys = BTreeSet::new();
    for shard in std::fs::read_dir(dir.join("claims")).into_iter().flatten().flatten() {
        for entry in std::fs::read_dir(shard.path()).into_iter().flatten().flatten() {
            let name = entry.file_name().to_string_lossy().into_owned();
            if let Some(hex) = name.strip_suffix(".json") {
                keys.insert(hex.to_string());
            }
        }
    }
    keys
}

#[test]
fn a_caller_s_key_is_the_same_whichever_run_proved_its_helper() {
    // The same classes built in other directories, and checked a second later into another cache: the run the
    // helper's proof came from (its time, its directories) is provenance, not part of any claim.
    let (Some(before), Some(after)) = (split("split-before-portable", SPLIT), split("split-refactored-portable", SPLIT_REFACTORED)) else { return };
    let (Some(before2), Some(after2)) = (split("split-before-portable-2", SPLIT), split("split-refactored-portable-2", SPLIT_REFACTORED)) else { return };
    let (one, two) = (empty_cache("split-portable"), empty_cache("split-portable-2"));
    let first = check_target(&before, &after, &one, "split-portable-per-seat", "h.Split#perSeat");
    std::thread::sleep(std::time::Duration::from_millis(1100));
    let second = check_target(&before2, &after2, &two, "split-portable-per-seat-2", "h.Split#perSeat");
    assert_eq!(first.verdict, jvmcontract::Verdict::Verified, "{}", first.output);
    assert_eq!(callee_assumptions(&first).len(), 1, "{}", first.output);
    assert_eq!(callee_assumptions(&first), callee_assumptions(&second));
    let keys = stored_keys(&one);
    assert_eq!(keys.len(), 2, "the helper's proof and its caller's: {keys:?}");
    assert_eq!(keys, stored_keys(&two));
}

#[test]
fn a_wrong_helper_change_is_not_shared_and_its_caller_s_check_finds_it() {
    let (Some(before), Some(wrong)) = (split("split-before-2", SPLIT), split("split-rounded-up", SPLIT_ROUNDED_UP)) else { return };
    let dir = empty_cache("split-wrong");
    let outcome = check_target(&before, &wrong, &dir, "split-wrong-per-seat", "h.Split#perSeat");
    assert_eq!(outcome.verdict, jvmcontract::Verdict::Violation, "{}", outcome.output);
    assert!(outcome.output.contains("note: Split.share, changed, stays as written in both versions: its two versions differ, at share("), "{}", outcome.output);
    assert!(callee_assumptions(&outcome).is_empty() && outcome.shared.is_empty());
    assert!(outcome.replay.as_ref().is_some_and(|r| r.reproduced), "a counterexample replayed: {:?}", outcome.replay);
    let c = outcome.counterexample.expect("a counterexample");
    assert_ne!(c.before, c.after, "{c:?}");
}

#[test]
fn a_helper_that_differs_only_where_its_caller_never_calls_it_is_proved_as_written() {
    let (Some(before), Some(capped)) = (split("split-before-3", SPLIT), split("split-capped", SPLIT_CAPPED)) else { return };
    let dir = empty_cache("split-capped");
    let outcome = check_target(&before, &capped, &dir, "split-capped-per-row", "h.Split#perRow");
    assert_eq!(outcome.verdict, jvmcontract::Verdict::Verified, "{}", outcome.output);
    assert!(outcome.output.contains("note: Split.share, changed, stays as written in both versions: its two versions differ"), "{}", outcome.output);
    assert!(callee_assumptions(&outcome).is_empty() && outcome.shared.is_empty());
    // Its other caller does call it there.
    let other = check_target(&before, &capped, &dir, "split-capped-per-seat", "h.Split#perSeat");
    assert_eq!(other.verdict, jvmcontract::Verdict::Violation, "{}", other.output);
}

/// Helpers outside the narrow kind: one that throws an exception of its own, whose message a regression proof
/// doesn't compare, and one over `double`.
const ODD_HELPERS: &str = r#"package h;
public class Odd {
    static long checked(long total, int ways) { if (ways <= 0) throw new IllegalArgumentException("no ways: " + ways); return total / ways; }
    static double half(double x) { return x / 2; }
    public static long use(long total, int ways, double x) { return checked(total, ways) + (long) half(x); }
}
"#;

const ODD_HELPERS_CHANGED: &str = r#"package h;
public class Odd {
    static long checked(long total, int ways) { if (ways < 1) throw new IllegalArgumentException("ways " + ways + " < 1"); return total / ways; }
    static double half(double x) { return x * 0.5; }
    public static long use(long total, int ways, double x) { return checked(total, ways) + (long) half(x); }
}
"#;

#[test]
fn only_a_helper_over_integers_that_raises_no_exception_of_its_own_is_offered_for_proof() {
    let (Some(before), Some(after)) = (compile("odd-before", &[("h/Odd.java", ODD_HELPERS)]), compile("odd-after", &[("h/Odd.java", ODD_HELPERS_CHANGED)])) else { return };
    let (b, a) = (cp(&before), cp(&after));
    let target = MemberRef::new("h/Odd", "use", "(JID)J");
    let mut asked = Vec::new();
    let plan = shared::plan_with(&b, &a, &target, &target, true, &mut |c| {
        asked.push(c.name.clone());
        None
    });
    assert!(asked.is_empty(), "asked about {asked:?}");
    assert!(plan.callees.is_empty(), "{:?}", plan.callees);
    // The same helpers over the split: asked, and shared with the proof given.
    let (Some(before), Some(after)) = (split("split-plan-before", SPLIT), split("split-plan-after", SPLIT_REFACTORED)) else { return };
    let (b, a) = (cp(&before), cp(&after));
    let target = MemberRef::new("h/Split", "perSeat", "(JI)J");
    let given = shared::Proved { key: "sha256:given".into(), from: "a test".into() };
    let plan = shared::plan_with(&b, &a, &target, &target, true, &mut |c| (c.name == "share").then(|| given.clone()));
    assert_eq!(plan.callees.len(), 1);
    assert_eq!((plan.callees[0].name.as_str(), plan.callees[0].proved.as_ref()), ("share", Some(&given)));
    assert_eq!(plan.callees[0].throws, vec!["java/lang/ArithmeticException".to_string()]);
    assert!(shared::plan(&b, &a, &target, &target, true).callees.is_empty(), "without a proof, nothing is shared");
}

/// Two changed helpers that call each other, each the other's helper: neither proof may rest on the other's.
const MUTUAL: &str = r#"package h;
public class Mutual {
    public static int f(int n) { return n > 10 ? g(10) + 1 : n * 2 + 1; }
    static int g(int n) { return n > 5 ? f(5) * 3 : n * 3; }
}
"#;

const MUTUAL_REWRITTEN: &str = r#"package h;
public class Mutual {
    public static int f(int n) { if (n <= 10) return n * 2 + 1; return g(10) + 1; }
    static int g(int n) { if (n <= 5) return n * 3; return f(5) * 3; }
}
"#;

#[test]
fn a_helper_s_proof_never_rests_on_the_proof_it_is_used_in() {
    let (Some(before), Some(after)) = (compile("mutual-before", &[("h/Mutual.java", MUTUAL)]), compile("mutual-after", &[("h/Mutual.java", MUTUAL_REWRITTEN)])) else { return };
    let dir = empty_cache("mutual");
    let outcome = check_target(&before, &after, &dir, "mutual-f", "h.Mutual#f");
    assert_eq!(outcome.verdict, jvmcontract::Verdict::Verified, "{}", outcome.output);
    let assumed = callee_assumptions(&outcome);
    assert_eq!(assumed.len(), 1, "g's proof is reused in f's: {assumed:?}");
    let key = ClaimKey(assumed[0].2.clone().unwrap());
    // g's proof was made with f as written: f's proof is the one it is used in.
    let (record, detail) = cache::lookup_detail(&dir, &key).unwrap().expect("g's proof is stored");
    assert_eq!(record.outcome.verdict, Verdict::Verified);
    let detail = detail.expect("its report");
    let output = detail["output"].as_str().unwrap();
    assert!(output.contains("note: Mutual.f, changed, stays as written in both versions: its proof would rest on the proof it is used in"), "{output}");
    let rests: Vec<&Value> = detail["statement"]["assumptions"].as_array().unwrap().iter().filter(|a| a["kind"] == "callee").collect();
    assert!(rests.is_empty(), "{rests:?}");
}

// S5: refinement per callee. A counterexample JBMC finds with the shared callees as stubs that doesn't reproduce
// once computed as written is put down to the callees whose stubs it rests on, and only those are computed as
// written in the next run.

fn has_jbmc() -> bool {
    let found = Command::new("jbmc").arg("--version").output().is_ok_and(|o| o.status.success());
    if !found {
        let skip = std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1");
        assert!(skip, "jbmc not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip the tests that need it");
    }
    found
}

/// Two callees identical in both versions, both shared: `twice`'s results are always even, which the two versions'
/// uses of it (`& 1` and `% 2`) need to agree, and `third`'s value cancels out, whatever it is.
const PAIR: &str = r#"package fixtures;
public final class Shares {
    static int twice(int x) { return x * 2; }
    static int third(int x) { return x / 3; }
    public static long split(long total, int seats, int fee) { return third(seats) + (twice(fee) & 1); }
}
"#;

fn pair(name: &str, source: &str) -> Option<PathBuf> {
    compile(name, &[("fixtures/Shares.java", source)])
}

/// A regression check of `fixtures.Shares#split` under JBMC, in a work directory of its own.
fn jbmc_check(before: &Path, after: &Path, name: &str) -> equivalence::Outcome {
    let mut options = equivalence::Options::new(before, after, "fixtures.Shares#split");
    options.engine = jvmcontract::Engine::Jbmc;
    options.timeout_seconds = 120;
    let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("summaries-refinement").join(name);
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    equivalence::run(&options).unwrap()
}

fn shares_callee(name: &str) -> shared::Callee {
    shared::Callee { owner: "fixtures/Shares".into(), name: name.into(), descriptor: "(I)I".into(), throws: Vec::new(), proved: None }
}

/// Needs no JBMC: the replay stub gives the answers it is given on their arguments, and is the callee as written
/// on any others, or when it is given none.
#[test]
fn the_replay_stub_gives_the_stub_s_answers_again_and_is_the_callee_elsewhere() {
    use jvmcontract::interp::{Machine, Value as V};
    let Some(classes) = pair("replay-stub", PAIR) else { return };
    let callees = [shares_callee("third"), shares_callee("twice")];
    let answered = [shared::Answer { arguments: vec![V::Int(5)], outcome: shared::Answered::Returned(Some(V::Int(-1))) }, shared::Answer { arguments: vec![V::Int(100_000)], outcome: shared::Answered::Returned(Some(V::Int(70_000))) }];
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("summaries").join("replay-stub-class");
    std::fs::create_dir_all(&dir).unwrap();
    let after_cp = cp(&classes);
    std::fs::write(dir.join("SharedCallees.class"), shared::replay_stub(&after_cp, &callees, &[None, Some(&answered)]).unwrap()).unwrap();
    let mut both = cp(&classes);
    both.add(&dir).unwrap();
    let mut m = Machine::new(&both);
    let mut call = |method: &str, x: i32| m.call_static("SharedCallees", method, "(I)I", vec![V::Int(x)]).ok().flatten();
    assert_eq!(call("m1_twice", 5), Some(V::Int(-1)), "the answer given");
    assert_eq!(call("m1_twice", 100_000), Some(V::Int(70_000)), "a constant beyond a short's range");
    assert_eq!(call("m1_twice", 6), Some(V::Int(12)), "other arguments: as written");
    assert_eq!(call("m0_third", 9), Some(V::Int(3)), "no answers: as written");
}

/// With both callees as stubs, JBMC finds a counterexample in which `twice` returns an odd number, which it never
/// does. Replayed with `twice` as written, the versions agree on it; with `third` as written, they still differ.
/// So only `twice` is computed as written in the next run, and `third` stays one function: the proof needs no
/// division bit-blasted.
#[test]
fn only_the_callee_a_spurious_counterexample_rests_on_is_computed_as_written() {
    if !has_jbmc() {
        return;
    }
    let after = PAIR.replace("(twice(fee) & 1)", "(twice(fee) % 2)");
    let (Some(before), Some(after)) = (pair("pair-before", PAIR), pair("pair-after", &after)) else { return };
    let outcome = jbmc_check(&before, &after, "pair");
    assert_eq!(outcome.verdict, jvmcontract::Verdict::Verified, "{}", outcome.output);
    assert_eq!(outcome.shared, vec!["Shares.third".to_string()], "{}", outcome.output);
    assert!(outcome.output.contains("note: the counterexample found with Shares.third, Shares.twice taken as one function in both versions does not reproduce once computed as written; it rests on the answers of Shares.twice's stub (with it as written, the two versions agree on its input), so the proof runs again with Shares.twice as written and Shares.third still one function in both"), "{}", outcome.output);
    assert!(outcome.proof.as_deref().unwrap().ends_with("; Shares.third unchanged in both versions and taken as one function in both"), "{:?}", outcome.proof);
    let work = &outcome.work;
    assert!(work.join("jbmc-shared-1.log").exists(), "the second run, with third's stub alone");
    assert!(!work.join("jbmc.log").exists(), "no run with every callee as written");
    let purposes: Vec<&str> = outcome.search.as_ref().unwrap().runs.iter().map(|r| r.purpose.as_str()).collect();
    assert_eq!(purposes, ["shared", "shared"]);
}

/// Refinement never makes a real regression disappear: whichever counterexample the stubs give first, the one
/// reported reproduces as written.
#[test]
fn a_real_regression_is_still_found_through_the_refinement() {
    if !has_jbmc() {
        return;
    }
    let after = PAIR.replace("(twice(fee) & 1)", "(twice(fee) % 2) + (fee == 7 ? 1 : 0)");
    let (Some(before), Some(after)) = (pair("pair-wrong-before", PAIR), pair("pair-wrong-after", &after)) else { return };
    let outcome = jbmc_check(&before, &after, "pair-wrong");
    assert_eq!(outcome.verdict, jvmcontract::Verdict::Violation, "{}", outcome.output);
    let witness = outcome.counterexample.as_ref().unwrap();
    assert!(witness.input.contains("fee=7"), "{}", witness.input);
    assert!(outcome.replay.as_ref().is_some_and(|r| r.reproduced), "{:?}", outcome.replay);
}
