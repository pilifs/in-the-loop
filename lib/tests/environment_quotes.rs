//! The quote family's E1 and E2 rows at the merge (interface request 5 of `llm-dlc/loops/application-core.md`'s
//! Phase 5, its second half): a claim about an ordinary method, `quotes.QuoteService#quote` or `#offerQuote`, whose
//! receiver and request its planned domain makes (`construction::flat_roots`), each dependency null and answered
//! by the environment model's stubs (`effects::check_planned`, behind `environment::check`). The request's code is
//! the values stream's String, the rate dependency is keyed by it, and the event's code is snapshotted by its
//! content. The contract (`tests/application_core.rs`) holds every frozen case to its expected verdict; this file
//! holds what the contract doesn't: the witness's words, the bounds past which the log is unresolved, the refusals
//! by name, and the claim key under the proof cache.

use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::effects;
use jvmcontract::spec::plans::{PlanValue, Returned};
use jvmcontract::spec::{CanonicalClaim, Construction, Observation, ObservationState, Part, Verdict};

fn fixtures() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/application-core")
}

fn golden(name: &str) -> CanonicalClaim {
    serde_json::from_str(&std::fs::read_to_string(fixtures().join(format!("golden/{name}.json"))).unwrap()).unwrap()
}

/// The quote family's `base` build (`before` or `after`) with each (file, text, replacement) edit applied to its
/// source, compiled under `name`. The contract needs javac, and so does this file.
fn build(name: &str, base: &str, edits: &[(&str, &str, &str)]) -> PathBuf {
    let root = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("environment-quotes").join(name);
    let src = root.join("src");
    let _ = std::fs::remove_dir_all(&root);
    std::fs::create_dir_all(src.join("quotes")).unwrap();
    let mut files = Vec::new();
    for entry in std::fs::read_dir(fixtures().join("quote").join(base).join("quotes")).unwrap() {
        let path = entry.unwrap().path();
        let file = path.file_name().unwrap().to_string_lossy().into_owned();
        let mut text = std::fs::read_to_string(&path).unwrap();
        for (f, from, to) in edits {
            if *f == file {
                assert!(text.contains(from), "{file} has {from}");
                text = text.replace(from, to);
            }
        }
        let out = src.join("quotes").join(&file);
        std::fs::write(&out, text).unwrap();
        files.push(out);
    }
    let classes = root.join("classes");
    let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&classes).args(&files).status().expect("this test needs javac");
    assert!(status.success(), "{name} compiles");
    classes
}

fn check(claim: &CanonicalClaim, before: &Path, after: &Path) -> effects::Checked {
    effects::check_planned(claim, before, after, None).unwrap_or_else(|u| panic!("refused: {u}"))
}

/// A wrong query key is refuted on the result under an environment that names the String keys, and an event sent on
/// the wrong branch on the effect, its code snapshotted by content: each replayed on a JVM.
#[test]
fn a_string_keyed_rate_and_an_events_code_are_refuted_and_replayed_by_content() {
    let claim = golden("quote-claim");
    let before = build("key-before", "before", &[]);
    let key = build("key-std-key", "after", &[("QuoteService.java", "rates.rate(code)", "rates.rate(\"STD\")")]);
    let c = check(&claim, &before, &key);
    assert_eq!(c.outcome.verdict, Verdict::Refuted, "{c:?}");
    let witness = c.outcome.witness.clone().unwrap();
    assert!(witness.contains("rates.rate") && witness.contains("\"STD\"") && witness.contains("Replayed on a JVM"), "{witness}");
    assert!(c.outcome.accounting.iter().any(|a| a.observation == "result" && a.state == ObservationState::Refuted), "{c:?}");
    assert!(c.assumptions.iter().any(|a| a.contains("a String key is compared by its content")), "{:?}", c.assumptions);

    let branch = build("key-zero-announced", "after", &[("QuoteService.java", "if (total <= 0) {", "if (total < 0) {")]);
    let c = check(&claim, &before, &branch);
    assert_eq!(c.outcome.verdict, Verdict::Refuted, "{c:?}");
    let event = "effect:quotes/Events#send(Lquotes/QuoteEvent;)V";
    assert!(c.outcome.accounting.iter().any(|a| a.observation == event && a.state == ObservationState::Refuted), "{c:?}");
    // The new build announces a quote of 0: its attempt names the event's code by its content, a String literal.
    let after = c.after.clone().unwrap();
    let attempt = &after.attempts.first().unwrap_or_else(|| panic!("an attempt: {after:?}")).2;
    assert!(attempt.starts_with("Events.send(event.code=\"") && attempt.contains("event.amountCents=0"), "{attempt}");
    assert!(c.before.as_ref().unwrap().attempts.is_empty(), "{c:?}");
}

/// A key or a payload String longer than the claim's String bound (4 code units) is no answer the table holds and no
/// snapshot: the result is unresolved, naming the bound, never verified on a coupled default or a cut String.
#[test]
fn a_key_or_payload_string_past_the_bound_leaves_the_result_unresolved() {
    let claim = golden("quote-claim");
    let before = build("bound-before", "before", &[]);
    let long_key = build("bound-long-key", "after", &[("QuoteService.java", "rates.rate(code)", "rates.rate(\"PREMIUM\")")]);
    let c = check(&claim, &before, &long_key);
    assert_eq!(c.outcome.verdict, Verdict::Unresolved, "{c:?}");
    assert!(c.reason.as_deref().unwrap_or_default().contains("keyed by a string of more than 4 code units"), "{c:?}");

    let long_code = build("bound-long-code", "after", &[("QuoteService.java", "new QuoteEvent(code, total)", "new QuoteEvent(\"QUOTED\", total)")]);
    let c = check(&claim, &before, &long_code);
    assert_eq!(c.outcome.verdict, Verdict::Unresolved, "{c:?}");
    assert!(c.reason.as_deref().unwrap_or_default().contains("a string of more than 4 code units"), "{c:?}");
}

/// What the planned check doesn't make, or a domain option it would not enforce, is refused by name before any
/// proof; a domain bound the code exceeds leaves the result unresolved.
#[test]
fn what_the_planned_check_does_not_make_is_refused_by_name() {
    let claim = golden("quote-claim");
    let before = build("refused-before", "before", &[]);
    let after = build("refused-after", "after", &[]);
    let edit = |f: &dyn Fn(&mut CanonicalClaim)| {
        let mut c = claim.clone();
        f(&mut c);
        c
    };
    let plans = |c: &mut CanonicalClaim, f: &dyn Fn(&mut jvmcontract::spec::plans::ConstructionPlan)| {
        let Some(Construction::Planned { before, after }) = c.domain.as_mut().map(|d| &mut d.made_by) else { panic!() };
        f(before);
        f(after);
    };
    let cases: Vec<(&str, CanonicalClaim, Part)> = vec![
        ("bounded at 3 code units", edit(&|c| plans(c, &|p| {
            for a in &mut p.nodes[1].args {
                if let PlanValue::Adapted { domain, .. } = a {
                    domain.max_length = 3;
                }
            }
        })), Part::Values),
        ("bounded at 3 elements", edit(&|c| plans(c, &|p| {
            for a in &mut p.nodes[1].args {
                if let PlanValue::Array { max_length, .. } = a {
                    *max_length = 3;
                }
            }
        })), Part::Objects),
        ("may be null or another root's object", edit(&|c| plans(c, &|p| {
            if let PlanValue::Node { nullable, .. } = &mut p.roots[1].value {
                *nullable = true;
            }
        })), Part::Objects),
        ("the constructor takes a quotes.Rates", edit(&|c| plans(c, &|p| {
            if let PlanValue::Dependency { class, .. } = &mut p.nodes[0].args[2] {
                *class = "quotes.Offers".into();
            }
        })), Part::Objects),
        ("aren't the ones its plans make", edit(&|c| c.domain.as_mut().unwrap().classes.push("quotes.Offer".into())), Part::Environment),
        ("the effect check compares", edit(&|c| c.observations.push(Observation::FieldPath { path: "request.code".into() })), Part::Environment),
    ];
    for (words, c, part) in cases {
        let gap = effects::check_planned(&c, &before, &after, None).err().unwrap_or_else(|| panic!("{words}: refused"));
        assert!(gap.what.contains(words), "{words}: {gap}");
        assert_eq!(gap.part, part, "{words}: {gap}");
    }
    // The event the quote makes is one allocation: a bound of 0 leaves the result unresolved before any proof.
    let tight = edit(&|c| {
        let d = c.domain.as_mut().unwrap();
        d.bounds.before.allocations = 0;
        d.bounds.after.allocations = 0;
    });
    let c = check(&tight, &before, &after);
    assert_eq!(c.outcome.verdict, Verdict::Unresolved, "{c:?}");
    assert!(c.reason.as_deref().unwrap_or_default().contains("may make 1 objects in one call, more than the claim's allocation bound of 0"), "{c:?}");
}

/// Under the proof cache, a planned effect claim's proof is reused exactly on a rerun, and not under another String
/// and array bound, nor when its DTO response may no longer be null: each is another key.
#[test]
fn a_planned_effect_claims_proof_is_reused_exactly_and_not_under_another_claim() {
    let claim = golden("offer-claim");
    let before = build("cache-before", "before", &[]);
    let after = build("cache-after", "after", &[]);
    let cache = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("environment-quotes-cache");
    let _ = std::fs::remove_dir_all(&cache);
    let run = |c: &CanonicalClaim| effects::check_planned(c, &before, &after, Some(&cache)).unwrap_or_else(|u| panic!("refused: {u}"));
    let cold = run(&claim);
    assert_eq!(cold.outcome.verdict, Verdict::Verified, "{cold:?}");
    assert!(cold.reuse.is_none(), "{cold:?}");
    let key = cold.key.clone().expect("a key");
    let rerun = run(&claim);
    assert_eq!(rerun.outcome.verdict, Verdict::Verified, "{rerun:?}");
    assert!(rerun.reuse.is_some() && rerun.key.as_ref() == Some(&key), "{rerun:?}");

    let mut smaller = claim.clone();
    smaller.bounds.max_array_length = 3;
    let Some(Construction::Planned { before: pb, after: pa }) = smaller.domain.as_mut().map(|d| &mut d.made_by) else { panic!() };
    for p in [pb, pa] {
        p.bounds.max_array_length = 3;
        for a in &mut p.nodes[1].args {
            match a {
                PlanValue::Adapted { domain, .. } => domain.max_length = 3,
                PlanValue::Array { max_length, .. } => *max_length = 3,
                _ => {}
            }
        }
    }
    let other = run(&smaller);
    assert_eq!(other.outcome.verdict, Verdict::Verified, "{other:?}");
    assert!(other.reuse.is_none() && other.key.is_some() && other.key != Some(key.clone()), "{other:?}");

    let mut never_null = claim.clone();
    let model = never_null.environment.as_mut().unwrap().calls[0].model.as_mut().unwrap();
    let jvmcontract::spec::plans::ModelledResult::Returns { value: Returned::Object { nullable, .. } } = &mut model.results[0] else { panic!() };
    *nullable = false;
    let other = run(&never_null);
    assert_eq!(other.outcome.verdict, Verdict::Verified, "{other:?}");
    assert!(other.reuse.is_none() && other.key != Some(key), "{other:?}");
}
