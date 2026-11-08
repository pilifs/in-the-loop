//! The joint run of `llm-dlc/loops/foundations.md`'s Phase 5 (`jvmcontract compare`) on the joint example: each row of
//! the phase's table, checked on the fixture's builds with nothing written by hand. The integration contract
//! (`tests/foundations.rs`) checks each stream's part on its own, under the golden files; this checks them together,
//! each fed by the others: alignment's proposal is the heap check's correspondence, the proof cache is the heap
//! check's, and the observation specs give the entry points' claims.

mod foundations_fixture;
use foundations_fixture::{build, builds, root};

use std::path::PathBuf;

use jvmcontract::compare::{self, KernelCheck, Options, Report};
use jvmcontract::spec::cache::Reuse;
use jvmcontract::spec::observe::Change;
use jvmcontract::spec::{ClaimBounds, Correspondence, Evidence, HintContent, Intent, ObservationState, Outcome, Source, Verdict};
use serde_json::Value;

fn run(after: &str, cache: &std::path::Path) -> Report {
    let options = Options { before: build("before").to_path_buf(), after: build(after).to_path_buf(), cache: Some(cache.to_path_buf()), bounds: ClaimBounds { unwind: 16, max_array_length: 8 }, environment: Vec::new(), domains: Default::default() };
    compare::run(&options).unwrap_or_else(|u| panic!("compare before {after}: {u}"))
}

fn entry<'r>(r: &'r Report, id: &str) -> &'r Outcome {
    let e = r.entries.iter().find(|e| e.entry == id).unwrap_or_else(|| panic!("no entry point {id}"));
    &e.checked.as_ref().unwrap_or_else(|| panic!("{id} unsupported: {:?}", e.unsupported)).outcome
}

fn kernel<'r>(r: &'r Report, subject: &str) -> &'r KernelCheck {
    r.kernel.iter().find(|k| k.subject == subject).unwrap_or_else(|| panic!("no kernel pair {subject}"))
}

fn outcome<'r>(r: &'r Report, subject: &str) -> &'r Outcome {
    let k = kernel(r, subject);
    k.outcome.as_ref().unwrap_or_else(|| panic!("{subject} unchecked: {:?}", k.unsupported))
}

/// The verdict a subject reached in a report: an entry point's or a kernel pair's.
fn verdict_of(r: &Report, subject: &str) -> (Verdict, Option<String>) {
    let o = if subject.starts_with("POST ") { entry(r, subject) } else { outcome(r, subject) };
    (o.verdict, o.witness.clone())
}

#[test]
fn the_joint_example_passes_every_row() {
    if builds("foundations-compare").is_none() {
        return;
    }
    let cache = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("foundations-compare-cache");
    let _ = std::fs::remove_dir_all(&cache);
    let cold = run("after", &cache);
    let warm = run("after", &cache);

    // Automatic mapping: the kernel's correspondence is alignment's own proposal, inferred and only proposed, and no
    // person made any decision.
    let golden: Correspondence = serde_json::from_str(&std::fs::read_to_string(root().join("golden/correspondence.json")).unwrap()).unwrap();
    for subject in ["shop.Pricing#total", "shop.Pricing#withQuantity"] {
        let k = kernel(&cold, subject);
        let hint = k.hint.as_ref().unwrap_or_else(|| panic!("{subject}: no proposal"));
        assert_eq!((hint.source, hint.intent), (Source::Inferred, Intent::Proposed), "{subject}'s correspondence is inferred and proposed");
        let HintContent::Correspondence { correspondence } = &hint.content else { panic!("{subject}: not a correspondence") };
        assert_eq!(k.claim.correspondence.as_ref(), Some(correspondence), "{subject} is checked under the proposal");
        assert!(correspondence.outputs.is_empty(), "{subject}: no output relation stands in for the contract's equality: {:?}", correspondence.outputs);
        assert!(golden.inputs.iter().all(|e| correspondence.inputs.contains(e)), "{subject}: the proposal relates q as the golden correspondence does");
    }
    assert!(cold.effort.decisions.values().all(|n| *n == 0), "no person decided anything: {:?}", cold.effort.decisions);
    assert_eq!(cold.effort.decisions.len(), compare::CATEGORIES.len(), "every category is counted, zero included");

    // Object correspondence: checked over the declared, constructor-made domain, with the proof as the proposal's
    // evidence under its claim key.
    for subject in ["shop.Pricing#total", "shop.Pricing#withQuantity"] {
        let o = outcome(&cold, subject);
        assert_eq!(o.verdict, Verdict::Verified, "{subject}: {:?}", o.problem);
        assert!(o.domain.contains("made by its constructor"), "{subject}'s domain says how its inputs are made: {}", o.domain);
        assert!(o.accounting.iter().all(|a| a.state == ObservationState::Preserved), "{subject}: {:?}", o.accounting);
        assert!(matches!(&kernel(&cold, subject).hint.as_ref().unwrap().evidence, Evidence::Proved { claim_key } if claim_key.starts_with("sha256:")), "{subject}'s proposal is proved for a claim key");
    }
    assert!(outcome(&cold, "shop.Pricing#withQuantity").accounting.iter().any(|a| a.observation == "identity:result==q" && a.state == ObservationState::Preserved), "withQuantity is held to result == q");

    // Boundary preservation: the response and the effect proved preserved, and every old observation accounted for.
    let quotes = entry(&cold, "POST /quotes");
    assert_eq!(quotes.verdict, Verdict::Verified, "{:?}", quotes.problem);
    for id in ["result", "exception", "status"] {
        assert!(quotes.accounting.iter().any(|a| a.observation == id && a.state == ObservationState::Preserved), "POST /quotes's {id} is preserved: {:?}", quotes.accounting);
    }
    assert!(quotes.accounting.iter().any(|a| a.observation.starts_with("effect:") && a.observation.contains("KafkaTemplate#send") && a.state == ObservationState::Preserved), "the event is preserved: {:?}", quotes.accounting);
    let accounted: Vec<&str> = cold.obligations.iter().filter(|o| o.entry == "POST /quotes").map(|o| o.observation.as_str()).collect();
    assert!(quotes.accounting.iter().all(|a| accounted.contains(&a.observation.as_str())), "every observation of POST /quotes is an obligation: {accounted:?}");

    // Exact reuse: the unchanged rerun's results are the stored ones, each from the first run: the entry point's
    // effect-trace proof, under a key of the rewritten builds (recording stubs included), and the kernel's checks.
    let checked = |r: &Report, id: &str| r.entries.iter().find(|e| e.entry == id).and_then(|e| e.checked.clone()).unwrap_or_else(|| panic!("{id} unchecked"));
    let (cold_quotes, warm_quotes) = (checked(&cold, "POST /quotes"), checked(&warm, "POST /quotes"));
    assert!(cold_quotes.reuse.is_none(), "POST /quotes: nothing to reuse on a cold cache");
    let Some(Reuse::Exact { key, .. }) = &warm_quotes.reuse else { panic!("POST /quotes: the rerun is not an exact hit: {warm_quotes:?}") };
    assert_eq!(Some(key), cold_quotes.key.as_ref(), "POST /quotes: the hit is the first run's claim");
    assert_eq!((warm_quotes.outcome.verdict, &warm_quotes.outcome.accounting), (cold_quotes.outcome.verdict, &cold_quotes.outcome.accounting), "POST /quotes: the reused result is the stored one");
    // Each reuse names the run it came from by the builds that run was given, the entry point's included, whose
    // proof ran on rewritten copies of them in a temporary directory.
    let (before, after) = (build("before").display().to_string(), build("after").display().to_string());
    let from_first_run = |from: &str| from.contains(&before) && from.contains(&after) && !from.contains("jvmcontract-effects");
    let Some(Reuse::Exact { from, .. }) = &warm_quotes.reuse else { unreachable!() };
    assert!(from_first_run(from), "POST /quotes: the reuse names the first run's builds: {from}");
    for subject in ["shop.Pricing#total", "shop.Pricing#withQuantity", "shop.Pricing#discount"] {
        assert!(kernel(&cold, subject).reuse.is_none(), "{subject}: nothing to reuse on a cold cache");
        let Some(Reuse::Exact { key, from }) = &kernel(&warm, subject).reuse else { panic!("{subject}: the rerun is not an exact hit") };
        assert!(from_first_run(from), "{subject}: the reuse names the first run's builds: {from}");
        assert_eq!(outcome(&warm, subject).verdict, outcome(&cold, subject).verdict, "{subject}: the reused verdict is the stored one");
        if let Some(Evidence::Proved { claim_key }) = kernel(&cold, subject).hint.as_ref().map(|h| &h.evidence) {
            assert_eq!(&key.0, claim_key, "{subject}: the hit is the claim the proposal was proved under");
        }
    }

    // Compositional reuse: the changed helper's own proof is used in total's.
    let callees = &kernel(&cold, "shop.Pricing#total").callees;
    assert!(callees.iter().any(|c| matches!(c, Reuse::Callee { callee, key } if callee == "Pricing.discount" && key.0.starts_with("sha256:"))), "total reuses discount's proof: {callees:?}");

    // Honest incompleteness: the string route stays unresolved, named, and so do the kernel pairs the check can't
    // take yet.
    let text = entry(&cold, "POST /quotes/text");
    assert_eq!(text.verdict, Verdict::Unresolved);
    assert!(text.problem.as_deref().is_some_and(|p| p.contains("string concatenation")), "{:?}", text.problem);
    assert!(text.accounting.iter().all(|a| a.state == ObservationState::Unresolved), "{:?}", text.accounting);
    assert!(!cold.all_verified(), "a run with an unresolved part is not all verified");

    // Defect detection: every case of golden/expected.json, each defect overlaid on after, with a witness replayed
    // on a JVM for a refutation.
    let expected: Value = serde_json::from_str(&std::fs::read_to_string(root().join("golden/expected.json")).unwrap()).unwrap();
    let mut reports = vec![("after".to_string(), cold.clone())];
    for case in expected["cases"].as_array().unwrap() {
        let (b, subject) = (case["build"].as_str().unwrap(), case["subject"].as_str().unwrap());
        if !reports.iter().any(|(n, _)| n == b) {
            reports.push((b.to_string(), run(b, &cache)));
        }
        let r = &reports.iter().find(|(n, _)| n == b).unwrap().1;
        let want: Verdict = serde_json::from_value(case["verdict"].clone()).unwrap();
        let (got, witness) = verdict_of(r, subject);
        if let Some(changes) = case.get("obligations").and_then(Value::as_object) {
            for (id, change) in changes {
                let change: Change = serde_json::from_value(change.clone()).unwrap();
                assert!(r.obligations.iter().any(|o| &o.entry == id && o.change == change), "{b}: {id} is {change:?}");
            }
            assert!(r.effort.questions.iter().any(|q| q.subject == subject && q.category == "observation change"), "{b}: a person is asked about {subject}");
            assert_eq!(got, want, "{b} {subject}");
            continue;
        }
        if case.get("reused_in").is_some() {
            assert_eq!(got, want, "{b} {subject}");
            continue;
        }
        assert_eq!(got, want, "{b} {subject}: {witness:?}");
        if want == Verdict::Refuted {
            let w = witness.unwrap_or_else(|| panic!("{b} {subject}: a refutation without a witness"));
            if subject.starts_with("POST ") {
                assert!(w.contains("Replayed on a JVM"), "{b} {subject}: {w}");
            }
        }
        if let Some(obs) = case.get("observations").and_then(Value::as_array) {
            let o = if subject.starts_with("POST ") { entry(r, subject) } else { outcome(r, subject) };
            for ob in obs {
                let id = format!("identity:{}=={}", ob["left"].as_str().unwrap(), ob["right"].as_str().unwrap());
                let state = if want == Verdict::Refuted { ObservationState::Refuted } else { ObservationState::Preserved };
                assert!(o.accounting.iter().any(|a| a.observation == id && a.state == state), "{b} {subject}: {id} is {state:?}: {:?}", o.accounting);
            }
        }
        if let Some(m) = case.get("domain_mentions").and_then(Value::as_str) {
            assert!(outcome(r, subject).domain.contains(m), "{b} {subject}: the domain says {m}");
        }
    }
    // The alias-to-copy defect is told apart by identity alone: every field agrees.
    let copy = outcome(&reports.iter().find(|(n, _)| n == "alias-to-copy").unwrap().1, "shop.Pricing#withQuantity");
    let refuted: Vec<&str> = copy.accounting.iter().filter(|a| a.state == ObservationState::Refuted).map(|a| a.observation.as_str()).collect();
    assert_eq!(refuted, ["identity:result==q"], "only the identity relation differs: {:?}", copy.witness);
    // A defect in the kernel is a fresh proof, not the stored result of after's claim.
    let offset = &reports.iter().find(|(n, _)| n == "offset").unwrap().1;
    assert!(kernel(offset, "shop.Pricing#total").reuse.is_none(), "offset's total is proved again");
    // And so is a defect at the boundary, in the code POST /quotes reaches; alias-to-copy changes only withQuantity,
    // which it doesn't reach, so its rewritten builds are after's and the stored proof is the same claim's.
    let quotes_of = |name: &str| checked(&reports.iter().find(|(n, _)| n == name).unwrap().1, "POST /quotes");
    for name in ["offset", "dropped-effect", "duplicated-effect", "outside-domain"] {
        let q = quotes_of(name);
        assert!(q.reuse.is_none() && q.key.as_ref() != cold_quotes.key.as_ref(), "{name}: POST /quotes is proved again under another key: {:?}", q.reuse);
    }
    let unreached = quotes_of("alias-to-copy");
    assert!(matches!(&unreached.reuse, Some(Reuse::Exact { key, .. }) if Some(key) == cold_quotes.key.as_ref()), "alias-to-copy: a change POST /quotes doesn't reach is a hit: {:?}", unreached.reuse);
    assert_eq!(unreached.outcome.verdict, Verdict::Verified);
    let Some(Reuse::Exact { from, .. }) = &unreached.reuse else { unreachable!() };
    assert!(from_first_run(from) && !from.contains(&build("alias-to-copy").display().to_string()), "alias-to-copy: the hit names the run on after it came from: {from}");
    let text = compare::render(&warm);
    assert!(text.lines().filter(|l| l.contains("reused: ") && !l.contains("one function in both versions")).all(from_first_run), "every exact reuse in the text names the first run's builds:\n{text}");
    assert!(text.lines().filter(|l| l.contains("reused: ")).count() >= 4, "the entry point's and the three kernel pairs' reuses are in the text:\n{text}");

    // The report's findings: one per refuted part, of the kind its check is, anchored at the source given; none for
    // the correct refactor.
    let sources = [root().join("after")];
    assert!(compare::findings(&cold, &sources, Some(&root())).is_empty(), "the correct refactor has no finding");
    let found = compare::findings(offset, &sources, Some(&root()));
    let rules: Vec<(&str, Option<&str>)> = found.iter().map(|f| (f.rule_id.as_str(), f.uri.as_deref())).collect();
    assert_eq!(rules, [("effects-changed", Some("after/shop/QuotesController.java")), ("behaviour-changed", Some("after/shop/Pricing.java"))], "offset: {found:?}");
    assert!(found[1].message.contains("shop.Pricing#total"), "{}", found[1].message);

    // Effort: the correct refactor asks nothing; the route change asks about each of the old route's observations.
    assert!(cold.effort.questions.is_empty(), "{:?}", cold.effort.questions);
    assert!(!cold.effort.assumed.is_empty(), "what the verdicts rest on is listed");
    let route = &reports.iter().find(|(n, _)| n == "route-change").unwrap().1;
    let asked: Vec<&str> = route.effort.questions.iter().map(|q| q.category.as_str()).collect();
    assert_eq!(asked, ["observation change"; 4], "{:?}", route.effort.questions);
}
