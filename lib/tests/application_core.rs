//! The integration contract of `llm-dlc/loops/application-core.md` (Phase 0 step 4), run by
//! `llm-dlc/tools/application-core-integration.sh` on the merge of the four streams while they work. One test per
//! row of the acceptance contract (`llm-dlc/loops/application-core-acceptance.md`) that a unit-level run can reach,
//! on the frozen fixtures of `tests/fixtures/application-core/` and the verdicts their `golden/expected.json` fixes.
//!
//! Each case must reach its expected verdict, or give the named refusal of a stream that owns the row and hasn't
//! built its part yet: `Unsupported` naming that part, or a check refused with that stream's words. Anything else
//! fails: another verdict, a refusal naming no stream of the row, or one naming another's. Every check runs on the
//! native engine with no JBMC (J2's guard): `jbmc` is a path that doesn't exist.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::spec::{self, CanonicalClaim, Construction, ObservationState, Part, Unsupported};
use jvmcontract::{equivalence, property, Verdict};
use serde_json::Value;

const NO_JBMC: &str = "/nonexistent/jbmc";

fn fixtures() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/application-core")
}

fn expected() -> &'static Value {
    static EXPECTED: OnceLock<Value> = OnceLock::new();
    EXPECTED.get_or_init(|| serde_json::from_str(&std::fs::read_to_string(fixtures().join("golden/expected.json")).unwrap()).unwrap())
}

fn golden(name: &str) -> CanonicalClaim {
    let path = fixtures().join(format!("golden/{name}.json"));
    serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap_or_else(|e| panic!("{}: {e}", path.display()))
}

/// Every build of every family, compiled once: `before`, `after`, and each defect overlaid on `after`. The
/// contract needs `javac`: without it, it fails rather than pass by skipping.
fn builds() -> &'static Path {
    static DIR: OnceLock<PathBuf> = OnceLock::new();
    DIR.get_or_init(|| {
        let root = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core");
        let _ = std::fs::remove_dir_all(&root);
        for family in ["quote", "throttle", "basket"] {
            let dir = fixtures().join(family);
            let mut names = vec!["before".to_string(), "after".to_string()];
            names.extend(std::fs::read_dir(dir.join("defects")).unwrap().map(|e| e.unwrap().file_name().to_string_lossy().into_owned()));
            for name in names {
                let base = dir.join(if name == "before" { "before" } else { "after" });
                let mut files = std::collections::BTreeMap::new();
                for f in java_files(&base) {
                    files.insert(f.strip_prefix(&base).unwrap().to_path_buf(), f.clone());
                }
                let overlay = dir.join("defects").join(&name);
                for f in java_files(&overlay) {
                    files.insert(f.strip_prefix(&overlay).unwrap().to_path_buf(), f.clone());
                }
                let out = root.join(family).join(&name);
                let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out).args(files.values()).status().expect("the contract needs javac");
                assert!(status.success(), "{family}/{name} compiles");
            }
        }
        root
    })
}

fn java_files(dir: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    let Ok(entries) = std::fs::read_dir(dir) else { return out };
    for e in entries {
        let p = e.unwrap().path();
        if p.is_dir() {
            out.extend(java_files(&p));
        } else if p.extension().is_some_and(|x| x == "java") {
            out.push(p);
        }
    }
    out
}

fn build(family: &str, name: &str) -> PathBuf {
    builds().join(family).join(name)
}

/// The builds a family's expectations name for `case` (a claim, or a method under `regressions`), with what each
/// must reach.
fn cases(family: &str, case: &str) -> Vec<(String, Value)> {
    let e = &expected()[family][case];
    let cases: Vec<(String, Value)> = e.as_object().unwrap_or_else(|| panic!("no expectations for {family} {case}")).iter().filter(|(k, _)| !k.starts_with('$')).map(|(k, v)| (k.clone(), v.clone())).collect();
    assert!(!cases.is_empty());
    cases
}

/// A claim's outcome against what `expected` says, or the refusal of one of `parts`.
fn holds(what: &str, result: Result<spec::Outcome, Unsupported>, expected: &Value, parts: &[Part]) {
    match result {
        Err(u) => assert!(parts.contains(&u.part), "{what}: refused by {:?}, which isn't among the row's streams {parts:?}: {}", u.part, u.what),
        Ok(o) => match expected {
            Value::String(s) if s == "verified" => assert_eq!(o.verdict, spec::Verdict::Verified, "{what}: {o:?}"),
            Value::Array(a) => {
                assert_eq!(o.verdict, spec::Verdict::Refuted, "{what}: {o:?}");
                let observation = a[1].as_str().unwrap();
                let state = o.accounting.iter().find(|x| x.observation == observation).map(|x| x.state);
                assert_eq!(state, Some(ObservationState::Refuted), "{what}: {observation} refuted, with its witness replayed: {o:?}");
                assert!(o.witness.is_some(), "{what}: a refutation has its witness");
            }
            other => panic!("{what}: an expectation {other}"),
        },
    }
}

/// A plain regression check's outcome against what `expected` says ("verified" or "violation", the violation's
/// witness replayed), or a refusal in the words of one of `streams`: "the objects stream builds it".
fn regression_holds(what: &str, o: &equivalence::Outcome, expected: &str, streams: &[&str]) {
    match o.verdict {
        Verdict::Unverifiable => {
            let problem = o.problem.as_deref().unwrap_or_default();
            assert!(streams.iter().any(|s| problem.contains(&format!("the {s} stream builds it"))), "{what}: refused, but not by the row's streams {streams:?}: {problem}");
        }
        Verdict::Verified => assert_eq!(expected, "verified", "{what}: {}", o.output),
        Verdict::Violation => {
            assert_eq!(expected, "violation", "{what}: {}", o.output);
            assert!(o.replay.as_ref().is_some_and(|r| r.reproduced), "{what}: the witness replays: {}", o.output);
        }
    }
}

fn regression(family: &str, build_name: &str, target: &str, bound: Option<u32>) -> equivalence::Outcome {
    let mut options = equivalence::Options::new(&build(family, "before"), &build(family, build_name), target);
    if let Some(b) = bound {
        options.max_array_length = b;
    }
    options.engine = jvmcontract::Engine::Native;
    options.jbmc = NO_JBMC.into();
    let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-work").join(format!("{}-{build_name}", target.replace(['#', '.'], "-")));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    equivalence::run(&options).unwrap()
}

/// Every build a family's expectations name for `target`, checked against `before`.
fn regressions(family: &str, target: &str, streams: &[&str]) {
    regressions_within(family, target, streams, None);
}

/// [`regressions`] under the bound `bound` (`--max-array-length`) where one is given.
fn regressions_within(family: &str, target: &str, streams: &[&str], bound: Option<u32>) {
    for (name, verdict) in cases("regressions", target) {
        let o = regression(family, &name, target, bound);
        regression_holds(&format!("{target} {name}"), &o, verdict.as_str().unwrap(), streams);
    }
}

/// Every build a family's expectations name under the frozen claim `claim`, checked by `check`.
fn claims(family: &str, claim: &str, parts: &[Part], check: impl Fn(&CanonicalClaim, &Path, &Path) -> Result<spec::Outcome, Unsupported>) {
    let c = golden(claim);
    for (name, verdict) in cases(family, claim) {
        holds(&format!("{claim} {name}"), check(&c, &build(family, "before"), &build(family, &name)), &verdict, parts);
    }
}

/// The frozen claims are the shared types: each parses as a canonical claim and writes back the same JSON, and each
/// plan has the shape of a bounded DAG of its own nodes.
#[test]
fn the_frozen_claims_are_the_shared_types() {
    for entry in std::fs::read_dir(fixtures().join("golden")).unwrap() {
        let path = entry.unwrap().path();
        let name = path.file_stem().unwrap().to_string_lossy().into_owned();
        if !name.ends_with("-claim") {
            continue;
        }
        let original: Value = serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        let claim = golden(&name);
        assert_eq!(serde_json::to_value(&claim).unwrap(), original, "{name} round-trips");
        let Some(Construction::Planned { before, after }) = claim.domain.as_ref().map(|d| &d.made_by) else { panic!("{name} has a planned domain") };
        for plan in [before, after] {
            assert_eq!(plan.shape_problem(), None, "{name}");
        }
    }
}

/// Every build of every family compiles, and the expectations name each one under every claim and regression.
#[test]
fn every_build_compiles_and_every_case_has_its_verdict() {
    for family in ["quote", "throttle", "basket"] {
        let mut names: Vec<String> = std::fs::read_dir(builds().join(family)).unwrap().map(|e| e.unwrap().file_name().to_string_lossy().into_owned()).filter(|n| n != "before").collect();
        names.sort();
        for (case, cases) in expected()[family].as_object().unwrap() {
            let mut named: Vec<String> = cases.as_object().unwrap().keys().cloned().collect();
            named.sort();
            assert_eq!(named, names, "{family} {case}");
        }
    }
}

/// G0: the gate that validates the supported domain. A domain made field by field or of invariants, or by
/// constructors and classes other than the check's, is refused before any verdict; the kernel's own claim, whose
/// constructors are the check's, is verified. Permanent: no stream of this wave builds these.
#[test]
fn g0_an_unsupported_domain_policy_is_refused_before_any_verdict() {
    let fixture = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/foundations");
    let root = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-g0");
    let _ = std::fs::remove_dir_all(&root);
    for (name, classes) in [("before", vec!["Pricing", "Quote"]), ("after", vec!["Pricing", "Quote", "Money"])] {
        let files: Vec<PathBuf> = classes.iter().map(|c| fixture.join(name).join(format!("shop/{c}.java"))).collect();
        assert!(Command::new("javac").args(["-g", "-parameters", "-proc:none", "-d"]).arg(root.join(name)).args(&files).status().expect("the contract needs javac").success());
    }
    let kernel: CanonicalClaim = serde_json::from_str(&std::fs::read_to_string(fixture.join("golden/kernel-claim.json")).unwrap()).unwrap();
    let check = |claim: &CanonicalClaim| spec::heap::check(claim, &root.join("before"), &root.join("after"));
    assert_eq!(check(&kernel).expect("the kernel's own claim is supported").verdict, spec::Verdict::Verified);
    let with = |made_by: Construction| {
        let mut c = kernel.clone();
        c.domain.as_mut().unwrap().made_by = made_by;
        c
    };
    let calls = |calls: &[&str]| Construction::Constructors { calls: calls.iter().map(|c| c.to_string()).collect() };
    let mut extra_class = kernel.clone();
    extra_class.domain.as_mut().unwrap().classes.push("shop.Discount".into());
    for (what, claim) in [
        ("field by field", with(Construction::FieldByField {})),
        ("invariants", with(Construction::Invariant { invariants: vec!["q.quantity > 0".into()] })),
        ("a factory the kernel doesn't have", with(calls(&["before: shop.Quote(long cents, int quantity)", "after: shop.Quote.of(long cents, int quantity)"]))),
        ("a constructor left out", with(calls(&["before: shop.Quote(long cents, int quantity)", "after: shop.Quote(shop.Money amount, int quantity)"]))),
        ("a class the check makes no object of", extra_class),
    ] {
        let gap = check(&claim).expect_err(what);
        assert_eq!(gap.part, Part::Heap, "{what}: {gap}");
    }
}

/// O1: an ordinary receiver through the regression and property entry points: the throttle's `allows`, right after
/// its constructor, verified, and `one-short`'s defect replayed.
#[test]
fn o1_an_ordinary_receiver_in_the_regression_and_property_checks() {
    regressions("throttle", "throttle.Throttle#allows", &["objects"]);
    let mut options = property::Options::new(&[build("throttle", "after")], "throttle.Throttle#allows");
    options.engine = jvmcontract::Engine::Native;
    options.jbmc = NO_JBMC.into();
    options.assume = Some("n >= 0".into());
    options.assert = Some("result || n > 0".into());
    options.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-work/o1-property"));
    // The receiver is wired since the objects stream's O1: no refusal is accepted (the joint acceptance's finding).
    let o = property::run(&options).unwrap();
    assert_eq!(o.verdict, Verdict::Verified, "allows(0) holds of every throttle: {}", o.output);
}

/// O2: an array-valued constructor, faithful to identity: `checked` hands back the caller's request, made with its
/// code and quantities array, and `alias-to-copy`'s copy is refuted on identity alone.
#[test]
fn o2_an_array_valued_constructor_faithful_to_identity() {
    // The service's dependencies are passed null, and the request's String code is a leaf of its construction
    // compared by content, since Phase 5 (application-core.md's Progress): no refusal is accepted.
    // `checked-claim` bounds each version's allocations at 3, the user's decision of 2026-11-08 (the frozen 1 counted
    // only the method's own exception): `alias-to-copy`'s copy, the exception its constructor may throw and the
    // method's own are within the claim, so the copy is refuted on `identity:result==request`, as `expected.json`
    // says.
    claims("quote", "checked-claim", &[], spec::heap::check);
}

/// O3: a defect only a history reaches. Under the constructor-only claim, `after-setup` is verified, labelled for
/// that domain; under one setup call, it is refuted with the whole history replayed.
#[test]
fn o3_a_defect_only_a_history_reaches() {
    claims("throttle", "throttle-constructed-claim", &[Part::Objects], spec::heap::check);
    claims("throttle", "throttle-setup-claim", &[Part::Objects], spec::heap::check);
}

/// V1: a symbolic String crosses the proof boundary: `Codes.vip`'s rewrite with `length` and `charAt` verified, and
/// a shorter prefix refuted on a replayed witness.
#[test]
fn v1_a_symbolic_string_crosses_the_proof_boundary() {
    // Wired at the merge (Phase 5 step 1): no stream's refusal is accepted any more.
    regressions("quote", "quotes.Codes#vip", &[]);
}

/// V2: a bounded immutable list as input: order, duplicates and identity kept.
#[test]
fn v2_a_bounded_supported_list_as_input() {
    // The list parameter is wired at the merge (Phase 5 step 1): no stream's refusal is accepted any more for the
    // plain checks, under the frozen claims' list bound of 3 (`basket-*-claim.json`'s `max_length`).
    regressions_within("basket", "basket.Basket#total", &[], Some(3));
    regressions_within("basket", "basket.Basket#clearAll", &[], Some(3));
    // The frozen claims' adapted list root too (Phase 5 step 1): no refusal is accepted.
    claims("basket", "basket-total-claim", &[], spec::heap::check);
    claims("basket", "basket-clear-claim", &[], spec::heap::check);
    // `basket-first-claim` bounds each version's allocations at 2, the user's decision of 2026-11-08 (the frozen 0
    // left the copy outside the claim): `copied-first`'s copy makes a Line and the IllegalArgumentException its
    // constructor may throw, as O3's decision counted the exception `allows` throws, so the copy is refuted on
    // `identity:result==lines[0]`, as `expected.json` says.
    claims("basket", "basket-first-claim", &[], spec::heap::check);
}

/// E1: a consumed return value and a declared failure, under one explicit environment: the rate a dependency
/// returns, or its checked `RateUnavailable`. Wired at the merge (Phase 5 step 1): no stream's refusal is accepted.
#[test]
fn e1_a_consumed_return_value_and_a_declared_failure() {
    claims("quote", "quote-claim", &[], jvmcontract::environment::check);
}

/// E2: a nullable returned DTO, made by the shared construction plan. Wired at the merge: no refusal is accepted.
#[test]
fn e2_a_nullable_returned_dto() {
    claims("quote", "offer-claim", &[], jvmcontract::environment::check);
}

/// R1: the native property cache: a verified property, then its exact reuse, under `prove --cache`.
#[test]
fn r1_the_native_property_cache() {
    let cache = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-r1-cache");
    let _ = std::fs::remove_dir_all(&cache);
    for run in ["cold", "rerun"] {
        let mut options = property::Options::new(&[build("quote", "after")], "quotes.QuoteService#units");
        options.engine = jvmcontract::Engine::Native;
        options.jbmc = NO_JBMC.into();
        options.assert = Some("quantities.length > 0 || result == 0".into());
        options.cache = Some(cache.clone());
        options.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join(format!("application-core-work/r1-{run}")));
        // The property cache is built (R1): no refusal is accepted, and the rerun is the stored result.
        let o = property::run(&options).unwrap_or_else(|e| panic!("{run}: {e}"));
        assert_eq!(o.verdict, Verdict::Verified, "{run}: {}", o.output);
        assert_eq!(o.reuse.is_some(), run == "rerun", "{run}: {}", o.output);
    }
}

/// R2: a heap-reading helper on its own: `fee`, which reads the receiver's fee policy, proved, and
/// `helper-extra-field`'s extra read refuted. Its reuse in a changed caller is J1's, at the merge.
#[test]
fn r2_a_heap_reading_helper_on_its_own() {
    // The receiver's three dependencies are passed null since the merge, `fee` never reaching them: no refusal.
    regressions("quote", "quotes.QuoteService#fee", &[]);
}

/// J3: semantic changes change the claim key: a setup call, a modelled outcome, a value bound. Until the reuse
/// stream registers the new fields, such a claim is uncacheable, by name; once it does, each change gives another key.
#[test]
fn j3_semantic_changes_change_the_claim_key() {
    let differs = |what: &str, a: &CanonicalClaim, b: &CanonicalClaim| match (spec::cache::key(a), spec::cache::key(b)) {
        (Ok(x), Ok(y)) => assert_ne!(x, y, "{what}: the same key"),
        (Err(u), _) | (_, Err(u)) => assert_eq!(u.part, Part::Summaries, "{what}: uncacheable, by the claim key's own refusal: {u}"),
    };
    differs("a setup call", &golden("throttle-constructed-claim"), &golden("throttle-setup-claim"));
    let quote = golden("quote-claim");
    let mut fewer = quote.clone();
    let rate = &mut fewer.environment.as_mut().unwrap().calls[0];
    rate.model.as_mut().unwrap().results.pop();
    rate.outcomes.pop();
    differs("a modelled outcome", &quote, &fewer);
    let mut shorter = golden("basket-total-claim");
    if let Construction::Planned { before, after } = &mut shorter.domain.as_mut().unwrap().made_by {
        for plan in [before, after] {
            if let spec::plans::PlanValue::Adapted { domain, .. } = &mut plan.roots[0].value {
                domain.max_length = 2;
            }
        }
    }
    differs("a value bound", &golden("basket-total-claim"), &shorter);
}

/// The examples' result schema (`examples/schema/result.schema.json`, step 6 of Phase 0) registers every kind the
/// streams' statements may carry, as `jvmcontract --json` writes them and `build.py` keeps them in camelCase: a
/// value parameter, the environment's, a summary's and a setup sequence's assumptions, the new bounds, the value
/// models' evidence levels, and a replay under the environment model.
#[test]
fn the_result_schema_registers_the_statements_new_kinds() {
    use jvmcontract::spec::plans::EvidenceLevel;
    use jvmcontract::statement::{AssumptionKind, ParameterKind};
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/schema/result.schema.json");
    let schema: Value = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    let statement = &schema["$defs"]["statement"]["properties"];
    let names = |v: &Value| -> Vec<String> { v.as_array().unwrap().iter().map(|x| x.as_str().unwrap().to_string()).collect() };
    let word = |v: Value| v.as_str().unwrap().to_string();
    let parameter_kinds = names(&statement["domain"]["properties"]["parameters"]["items"]["properties"]["kind"]["enum"]);
    assert!(parameter_kinds.contains(&word(serde_json::to_value(ParameterKind::Value).unwrap())), "{parameter_kinds:?}");
    let assumption_kinds = names(&statement["assumptions"]["items"]["properties"]["kind"]["enum"]);
    for kind in [AssumptionKind::Environment, AssumptionKind::Summary, AssumptionKind::Setup] {
        assert!(assumption_kinds.contains(&word(serde_json::to_value(kind).unwrap())), "{kind:?}: {assumption_kinds:?}");
    }
    for bound in ["maxValueLength", "setupCalls", "traceBound"] {
        assert!(statement["bounds"]["properties"][bound].is_object(), "{bound}");
    }
    let levels = names(&statement["models"]["properties"]["values"]["items"]["properties"]["level"]["enum"]);
    for level in [EvidenceLevel::Implemented, EvidenceLevel::Modelled, EvidenceLevel::Tested, EvidenceLevel::Trusted, EvidenceLevel::Proved] {
        assert!(levels.contains(&word(serde_json::to_value(level).unwrap())), "{level:?}: {levels:?}");
    }
    assert!(names(&schema["properties"]["replay"]["properties"]["by"]["enum"]).contains(&"model".to_string()));
}
