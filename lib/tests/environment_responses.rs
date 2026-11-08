//! E3 of the environment stream (`llm-dlc/loops/application-core-environment.md`), interface request 5 of
//! `llm-dlc/loops/application-core.md`'s Phase 5: a dependency's response that is a DTO, an object of an application
//! class made by the common construction plan (`spec::plans::Returned::Object`, `construction::root`) from primitive
//! leaves, or null. The stubs make it by its constructor from the environment table's entry, a new object for every
//! call under a fresh identity, one object per entry under a stable one, so the identity policy is part of the
//! claim. A correct rewrite proves, a wrong null branch or a wrong field is refuted and replayed on a JVM, and a
//! handler or DTO that goes beyond data (a method of the DTO called, a field written, an object field) is refused by
//! name.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::{Mutex, OnceLock};

use jvmcontract::effects::{self, Checked};
use jvmcontract::spec::observe::{self, EntryPointSpec};
use jvmcontract::spec::plans::{CallModel, ConstructionPlan, Coupling, Identity, Maker, ModelledResult, Node, Occurrence, PlanBounds, PlanValue, Returned, Root};
use jvmcontract::spec::{CanonicalClaim, ClaimBounds, ModeledCall, ObservationState, Part, Unsupported, Verdict};

const FIND: &str = "offers/Offers#find(I)Loffers/Offer;";

fn has(program: &str) -> bool {
    Command::new(program).arg("-version").output().is_ok_and(|o| o.status.success())
}

fn java_files(dir: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    for entry in std::fs::read_dir(dir).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            out.extend(java_files(&path));
        } else if path.extension().is_some_and(|e| e == "java") {
            out.push(path);
        }
    }
    out.sort();
    out
}

fn javac(out: &Path, classpath: Option<&Path>, files: &[PathBuf]) {
    std::fs::create_dir_all(out).unwrap();
    let mut cmd = Command::new("javac");
    cmd.args(["-g", "-parameters", "-proc:none", "-d"]).arg(out);
    if let Some(cp) = classpath {
        cmd.arg("-cp").arg(cp);
    }
    assert!(cmd.args(files).status().expect("javac runs").success());
}

/// The controller of every build: a standing offer the application's `Offers` finds for the request's code, or
/// null; `body` is the handler's.
fn controller(body: &str) -> String {
    format!(
        r#"package offers;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class OfferController {{
    private final Offers offers;

    public OfferController(Offers offers) {{
        this.offers = offers;
    }}

    @PostMapping("/offer")
    public long offer(@RequestParam int code, @RequestParam int quantity) {{
{body}
    }}
}}
"#
    )
}

const OFFERS: &str = "package offers;\n\n/** The dependency that finds a code's standing offer, or null: a read-only query. */\npublic interface Offers {\n    Offer find(int code);\n}\n";
/// The DTO: two primitive fields, set by its one constructor.
const OFFER: &str = "package offers;\n\n/** A standing offer: a DTO with primitive fields. */\npublic final class Offer {\n    final long unitCents;\n    final int minimumUnits;\n\n    public Offer(long unitCents, int minimumUnits) {\n        this.unitCents = unitCents;\n        this.minimumUnits = minimumUnits;\n    }\n}\n";

/// `name`'s build, its handler `body` and its DTO `offer`, compiled once. None without javac and java.
fn build_with(name: &str, body: &str, offer: &str) -> Option<PathBuf> {
    static SPRING: OnceLock<Option<PathBuf>> = OnceLock::new();
    static BUILDING: Mutex<()> = Mutex::new(());
    let _one_at_a_time = BUILDING.lock().unwrap_or_else(|e| e.into_inner());
    let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("environment-responses");
    let spring = SPRING
        .get_or_init(|| {
            if !has("javac") || !has("java") {
                return None;
            }
            let _ = std::fs::remove_dir_all(&out);
            let dir = out.join("spring");
            javac(&dir, None, &java_files(&Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/spring/org")));
            Some(dir)
        })
        .as_ref()?;
    let dir = out.join(name);
    if !dir.exists() {
        let src = out.join("sources").join(name).join("offers");
        std::fs::create_dir_all(&src).unwrap();
        std::fs::write(src.join("OfferController.java"), controller(body)).unwrap();
        std::fs::write(src.join("Offers.java"), OFFERS).unwrap();
        std::fs::write(src.join("Offer.java"), offer).unwrap();
        javac(&dir, Some(spring), &[src.join("OfferController.java"), src.join("Offers.java"), src.join("Offer.java")]);
    }
    Some(dir)
}

fn build(name: &str, body: &str) -> Option<PathBuf> {
    build_with(name, body, OFFER)
}

/// The handler's offer: -1 without one, 0 under its minimum, else the units at its price.
const BEFORE: &str = "        Offer offer = offers.find(code);\n        if (offer == null) return -1;\n        if (quantity < offer.minimumUnits) return 0;\n        return offer.unitCents * quantity;";

fn spec(dir: &Path) -> EntryPointSpec {
    observe::entry_points(dir).expect("the fixture's classes read").into_iter().find(|s| s.id == "POST /offer").expect("POST /offer")
}

/// The plan of the response: one `Offer` made by its constructor from the leaves `result.unitCents` and
/// `result.minimumUnits`.
fn offer_plan() -> ConstructionPlan {
    ConstructionPlan {
        nodes: vec![Node {
            id: 0,
            class: "offers.Offer".into(),
            maker: Maker::Constructor { descriptor: "(JI)V".into() },
            args: vec![PlanValue::Leaf { path: "result.unitCents".into(), ty: "long".into() }, PlanValue::Leaf { path: "result.minimumUnits".into(), ty: "int".into() }],
        }],
        roots: vec![Root { name: "result".into(), value: PlanValue::Node { id: 0, nullable: false, same_as: vec![] } }],
        restrictions: vec![],
        bounds: PlanBounds { nodes: 1, max_array_length: 0, setup_calls: 0 },
        setup: vec![],
    }
}

/// `Offers.find` as a deterministic read-only query of its code: an `Offer` of [`offer_plan`], or null when
/// `nullable`, of the identity `identity`, `bound` calls per trace.
fn finding(nullable: bool, identity: Identity, bound: u32) -> ModeledCall {
    let model = CallModel { id: "offers.find".into(), key: vec!["arg0".into()], coupling: Coupling::Query {}, results: vec![ModelledResult::Returns { value: Returned::Object { plan: offer_plan(), nullable, identity } }], bound };
    ModeledCall { call: FIND.into(), outcomes: vec!["returns".into()], model: Some(model) }
}

fn claim(before: &Path, model: &ModeledCall) -> CanonicalClaim {
    let s = spec(before);
    effects::with_environment(effects::claim_for(&s, None, ClaimBounds { unwind: 8, max_array_length: 4 }), std::slice::from_ref(model), &s.handler)
}

/// `before` checked against `after` (handler bodies), `Offers.find` modelled as `model`; or what the check refuses.
fn try_check(name: &str, before: &str, after: &str, model: &ModeledCall) -> Option<Result<Checked, Unsupported>> {
    let b = build(&format!("{name}-before"), before)?;
    let a = build(name, after)?;
    Some(effects::check(&claim(&b, model), &spec(&b), &spec(&a), &b, &a))
}

fn check(name: &str, before: &str, after: &str, model: &ModeledCall) -> Option<Checked> {
    try_check(name, before, after, model).map(|r| r.unwrap_or_else(|u| panic!("{name}: {u}")))
}

fn state(c: &Checked, id: &str) -> ObservationState {
    c.outcome.accounting.iter().find(|a| a.observation == id).unwrap_or_else(|| panic!("{id} isn't accounted for: {:?}", c.outcome.accounting)).state
}

/// The correct case: a rewrite that tests for null the other way round and reads the fields once proves, under a
/// response that is a fresh `Offer` or null; the claim says how the response is made and what its identity is.
#[test]
fn a_handler_that_reads_a_nullable_dto_response_proves_its_rewrite() {
    let after = "        Offer offer = offers.find(code);\n        if (offer != null) {\n            long units = quantity;\n            return units >= offer.minimumUnits ? units * offer.unitCents : 0;\n        }\n        return -1;";
    let Some(c) = check("rewrite", BEFORE, after, &finding(true, Identity::Fresh, 1)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Verified, "{c:?}");
    assert_eq!(state(&c, "result"), ObservationState::Preserved);
    let words = c.assumptions.iter().find(|a| a.contains("Offers.find is a generated stub")).unwrap_or_else(|| panic!("{:?}", c.assumptions));
    assert!(words.contains("a new offers.Offer made by its constructor (JI)V from the leaves (unitCents, minimumUnits) for every call, or null"), "{words}");
    assert!(c.outcome.domain.contains("Offers.find (offers.find): any function of (arg0) to"), "{}", c.outcome.domain);
}

/// The null branch: a rewrite that answers 0 without an offer is refuted on a witness whose offer is null, and the
/// JVM replays it under the stubs.
#[test]
fn a_changed_null_branch_is_refuted_on_a_null_response_and_replayed() {
    let wrong = "        Offer offer = offers.find(code);\n        if (offer == null) return 0;\n        if (quantity < offer.minimumUnits) return 0;\n        return offer.unitCents * quantity;";
    let Some(c) = check("null-branch", BEFORE, wrong, &finding(true, Identity::Fresh, 1)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Refuted, "{c:?}");
    assert_eq!(state(&c, "result"), ObservationState::Refuted);
    let witness = c.outcome.witness.as_deref().unwrap();
    assert!(witness.contains("under the environment Offers.find (offers.find): (arg0=") && witness.contains("gives null") && witness.contains("Replayed on a JVM"), "{witness}");
    let (b, a) = (c.before.as_ref().unwrap(), c.after.as_ref().unwrap());
    assert_eq!((b.result, a.result), (-1, 0), "{witness}");
    // Under a response that is never null, the two agree.
    let Some(c) = check("null-branch", BEFORE, wrong, &finding(false, Identity::Fresh, 1)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Verified, "{c:?}");
}

/// A field: a rewrite that takes the minimum as exclusive is refuted on an offer made from the witness's leaves.
#[test]
fn a_wrong_field_test_is_refuted_on_a_made_response_and_replayed() {
    let wrong = "        Offer offer = offers.find(code);\n        if (offer == null) return -1;\n        if (quantity <= offer.minimumUnits) return 0;\n        return offer.unitCents * quantity;";
    let Some(c) = check("field", BEFORE, wrong, &finding(true, Identity::Fresh, 1)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Refuted, "{c:?}");
    let witness = c.outcome.witness.as_deref().unwrap();
    assert!(witness.contains("gives a new Offer(unitCents=") && witness.contains("minimumUnits=") && witness.contains("Replayed on a JVM"), "{witness}");
    let (b, a) = (c.before.as_ref().unwrap(), c.after.as_ref().unwrap());
    assert_ne!(b.result, a.result, "{witness}");
    assert_eq!(a.result, 0, "{witness}");
}

/// The identity policy is the claim's: a handler that asks twice and compares the two responses by identity sees
/// one object under a stable identity and two under a fresh one, so the rewrite that assumes one object proves
/// under the first and is refuted, replayed, under the second.
#[test]
fn whether_two_responses_are_one_object_is_the_models_identity_policy() {
    let compares = "        Offer a = offers.find(code);\n        Offer b = offers.find(code);\n        return a == b ? 1 : 0;";
    let assumes = "        offers.find(code);\n        offers.find(code);\n        return 1;";
    let Some(c) = check("identity", compares, assumes, &finding(true, Identity::Stable, 2)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Verified, "{c:?}");
    assert!(c.assumptions.iter().any(|a| a.contains("the same object for every call that gets that entry's answer")), "{:?}", c.assumptions);
    let Some(c) = check("identity", compares, assumes, &finding(true, Identity::Fresh, 2)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Refuted, "{c:?}");
    let (b, a) = (c.before.as_ref().unwrap(), c.after.as_ref().unwrap());
    assert_eq!((b.result, a.result), (0, 1), "{:?}", c.outcome.witness);
    assert!(c.outcome.witness.as_deref().is_some_and(|w| w.contains("Replayed on a JVM")), "{:?}", c.outcome.witness);
}

/// A response its constructor won't make from the entry's leaves is no response the dependency gives: the log is
/// unresolved there, never an exception of the dependency's.
#[test]
fn a_response_its_constructor_rejects_leaves_the_log_unresolved() {
    let checked = OFFER.replace("        this.unitCents = unitCents;", "        if (minimumUnits < 0) throw new IllegalArgumentException();\n        this.unitCents = unitCents;");
    let catching = "        try {\n            Offer offer = offers.find(code);\n            return offer == null ? -1 : offer.minimumUnits;\n        } catch (IllegalArgumentException e) {\n            return -2;\n        }";
    let (Some(b), Some(a)) = (build_with("rejecting-before", catching, &checked), build_with("rejecting", catching, &checked)) else { return };
    let model = finding(true, Identity::Fresh, 1);
    let c = effects::check(&claim(&b, &model), &spec(&b), &spec(&a), &b, &a).unwrap();
    assert_eq!(c.outcome.verdict, Verdict::Unresolved, "{c:?}");
    let words = format!("{:?}{:?}", c.reason, c.before);
    assert!(words.contains("a response its constructor wouldn't make"), "{words}");
}

/// What the model isn't is refused by name: a DTO is data its dependency gives, not an object with behaviour.
#[test]
fn a_dto_response_beyond_data_is_refused_by_name() {
    let model = finding(true, Identity::Fresh, 1);
    let refusal = |name: &str, body: &str, offer: &str| -> Option<Unsupported> {
        let b = build_with(&format!("{name}-before"), BEFORE, offer)?;
        let a = build_with(name, body, offer)?;
        Some(effects::check(&claim(&b, &model), &spec(&b), &spec(&a), &b, &a).expect_err(name))
    };
    let with_method = OFFER.replace("    public Offer(", "    public long total(int quantity) {\n        return unitCents * quantity;\n    }\n\n    public Offer(");
    let with_object = OFFER.replace("    final int minimumUnits;", "    final int minimumUnits;\n    Offer next;");
    let with_static = OFFER.replace("    final int minimumUnits;", "    final int minimumUnits;\n    static int made;");
    let calls = "        Offer offer = offers.find(code);\n        if (offer == null) return -1;\n        if (quantity < offer.minimumUnits) return 0;\n        return offer.hashCode();";
    let writes = "        Offer offer = offers.find(code);\n        if (offer == null) return -1;\n        if (quantity < offer.minimumUnits) return 0;\n        offer.unitCents2 = 1;\n        return offer.unitCents * quantity;";
    let writable = OFFER.replace("    final int minimumUnits;", "    final int minimumUnits;\n    long unitCents2;").replace("        this.minimumUnits = minimumUnits;", "        this.minimumUnits = minimumUnits;\n        this.unitCents2 = unitCents;");
    let cases: [(&str, &str, &str, &str); 5] = [
        ("method", BEFORE, &with_method, "has a method total"),
        ("object-field", BEFORE, &with_object, "field next of type offers.Offer"),
        ("static-field", BEFORE, &with_static, "static field made"),
        ("calls", calls, OFFER, "calls java.lang.Object.hashCode in offers.OfferController.offer"),
        ("writes", writes, &writable, "writes its field unitCents2"),
    ];
    for (name, body, offer, words) in cases {
        let Some(gap) = refusal(name, body, offer) else { return };
        assert_eq!(gap.part, Part::Environment, "{name}: {gap}");
        assert!(gap.what.contains(words) && gap.what.contains("a DTO response"), "{name}: {words}: {gap}");
    }
}

/// The claim key: the identity policy, nullability and the DTO's constructor are each part of the claim, and an
/// unchanged rerun is an exact hit, a refutation replayed again.
#[test]
fn a_dto_responses_plan_and_identity_are_in_the_claim_key() {
    use jvmcontract::spec::cache::Reuse;
    let after = "        Offer offer = offers.find(code);\n        if (offer != null) {\n            long units = quantity;\n            return units >= offer.minimumUnits ? units * offer.unitCents : 0;\n        }\n        return -1;";
    let wrong = "        Offer offer = offers.find(code);\n        if (offer == null) return 0;\n        if (quantity < offer.minimumUnits) return 0;\n        return offer.unitCents * quantity;";
    let edited = OFFER.replace("        this.minimumUnits = minimumUnits;", "        this.minimumUnits = minimumUnits + 0;");
    let (Some(b), Some(a), Some(w), Some(e)) = (build("cached-before", BEFORE), build("cached", after), build("cached-wrong", wrong), build_with("cached-edited", after, &edited)) else { return };
    let cache = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("environment-responses-cache");
    let _ = std::fs::remove_dir_all(&cache);
    let run = |dir: &Path, model: &ModeledCall| effects::check_with(&claim(&b, model), &spec(&b), &spec(dir), &b, dir, Some(&cache)).unwrap();
    let cold = run(&a, &finding(true, Identity::Fresh, 1));
    assert_eq!(cold.outcome.verdict, Verdict::Verified, "{cold:?}");
    let key = cold.key.clone().expect("the proof ran under a claim key");
    let warm = run(&a, &finding(true, Identity::Fresh, 1));
    assert!(matches!(&warm.reuse, Some(Reuse::Exact { key: k, .. }) if *k == key), "an unchanged rerun is an exact hit: {warm:?}");
    let stable = run(&a, &finding(true, Identity::Stable, 1));
    let never_null = run(&a, &finding(false, Identity::Fresh, 1));
    let other_dto = run(&e, &finding(true, Identity::Fresh, 1));
    for c in [&stable, &never_null, &other_dto] {
        assert_eq!(c.outcome.verdict, Verdict::Verified, "{c:?}");
        assert!(c.reuse.is_none(), "{c:?}");
    }
    let keys = [Some(key), stable.key.clone(), never_null.key.clone(), other_dto.key.clone()];
    assert!(keys.iter().all(Option::is_some) && keys.iter().collect::<std::collections::HashSet<_>>().len() == keys.len(), "another identity, nullability or DTO constructor is another claim: {keys:?}");
    let refuted = run(&w, &finding(true, Identity::Fresh, 1));
    assert_eq!(refuted.outcome.verdict, Verdict::Refuted, "{refuted:?}");
    let again = run(&w, &finding(true, Identity::Fresh, 1));
    assert!(matches!(again.reuse, Some(Reuse::Exact { .. })), "{again:?}");
    assert!(again.outcome.witness.as_deref().is_some_and(|x| x.contains("gives null") && x.contains("Replayed on a JVM")), "a reused refutation is replayed again: {:?}", again.outcome.witness);
}

/// The model's shape, refused before any build is read: a per-call choice of a stable identity, and a plan that is
/// more than one DTO of primitive leaves.
#[test]
fn a_response_plan_beyond_one_dto_of_primitive_leaves_is_refused() {
    let lower = |m: &ModeledCall| jvmcontract::environment::lower(m, m.model.as_ref().unwrap()).expect_err("refused");
    let mut per_call = finding(true, Identity::Stable, 1);
    per_call.model.as_mut().unwrap().coupling = Coupling::Choice { policy: Occurrence::PerCall {} };
    let with = |f: &dyn Fn(&mut ConstructionPlan)| {
        let mut m = finding(true, Identity::Fresh, 1);
        let ModelledResult::Returns { value: Returned::Object { plan, .. } } = &mut m.model.as_mut().unwrap().results[0] else { unreachable!() };
        f(plan);
        m
    };
    let cases = [
        (lower(&per_call), "a stable identity under a per-call choice"),
        (lower(&with(&|p| {
            p.nodes[0].args[1] = PlanValue::Array { path: "result.minimumUnits".into(), element: "int".into(), max_length: 2, nullable: false };
            p.bounds.max_array_length = 2;
        })), "an array"),
        (lower(&with(&|p| p.nodes[0].maker = Maker::Factory { method: "offers.Offers#of(JI)Loffers/Offer;".into() })), "a factory"),
        (lower(&with(&|p| p.nodes[0].class = "offers.Other".into())), "where the call returns offers.Offer"),
        (lower(&with(&|p| p.roots.push(Root { name: "other".into(), value: PlanValue::Node { id: 0, nullable: false, same_as: vec![] } }))), "one root"),
        (lower(&ModeledCall { call: "offers/Offers#find(I)J".into(), ..finding(true, Identity::Fresh, 1) }), "where the call returns long"),
    ];
    for (gap, words) in cases {
        assert_eq!(gap.part, Part::Environment, "{words}: {gap}");
        assert!(gap.what.contains(words), "{words}: {gap}");
    }
}
