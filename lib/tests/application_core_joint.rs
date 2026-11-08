//! The joint acceptance at the merge of `llm-dlc/loops/application-core.md` (Phase 5 step 2): rows J1 and J2 of the
//! acceptance contract (`llm-dlc/loops/application-core-acceptance.md`), and the H and L families, on the frozen
//! fixtures of `tests/fixtures/application-core/` and the verdicts their `golden/expected.json` fixes.
//!
//! Unlike the integration contract (`tests/application_core.rs`), which accepted a stream's named refusal while the
//! streams ran, this accepts none: every case must reach its expected verdict on the merged revision, each refutation
//! on the observation it names with its witness run on a JVM, each verified result with every observation of its
//! claim preserved. Each claim is also run twice under one proof cache: the rerun must be the stored result under the
//! same key, and a build whose expected verdict differs from `after`'s must have another key and never be answered by
//! a stored one. A run under the cache records whether a build `after`'s result answered (an unrelated edit, J4's).
//!
//! Every check is on the tool's own engine with no JBMC: the equivalence and property checks are given a `jbmc`
//! that doesn't exist, and the claim checks run the own checker only. The job that runs this puts a `jbmc` first on
//! `PATH` that records being called, and fails if it was (J2's guard for the checks that take no `jbmc` option).
//!
//! Each run prints one line `evidence: {json}`, the acceptance contract's evidence record as far as the run has it:
//! the row, the claim or target and build, the claim key, the domain as stated, the expected and the actual verdict,
//! each observation's state, the witness and whether it was replayed on a JVM, and what the cache reused. The job's
//! log keeps them; the revision and the binary are the job's.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::classfile::MemberRef;
use jvmcontract::equivalence::Confirmed;
use jvmcontract::spec::cache::Reuse;
use jvmcontract::spec::{self, CanonicalClaim, Construction, ObservationState};
use jvmcontract::{effects, equivalence, property, reuse, Engine, Verdict};
use serde_json::{json, Value};

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

/// Every build of every family, compiled once, as the integration contract compiles them: `before`, `after`, and
/// each defect overlaid on `after`.
fn builds() -> &'static Path {
    static DIR: OnceLock<PathBuf> = OnceLock::new();
    DIR.get_or_init(|| {
        let root = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-joint-builds");
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
                let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out).args(files.values()).status().expect("the joint acceptance needs javac");
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

/// A fresh directory of this test binary's.
fn fresh(name: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-joint").join(name);
    let _ = std::fs::remove_dir_all(&dir);
    dir
}

/// The builds a family's expectations name for `case`, `after` first, so that a rerun of another build that
/// `after`'s stored result answers is seen as such.
fn cases(family: &str, case: &str) -> Vec<(String, Value)> {
    let e = &expected()[family][case];
    let mut cases: Vec<(String, Value)> = e.as_object().unwrap_or_else(|| panic!("no expectations for {family} {case}")).iter().filter(|(k, _)| !k.starts_with('$')).map(|(k, v)| (k.clone(), v.clone())).collect();
    cases.sort_by_key(|(k, _)| (k != "after", k.clone()));
    assert_eq!(cases.first().map(|(k, _)| k.as_str()), Some("after"));
    cases
}

fn evidence(record: Value) {
    println!("evidence: {record}");
}

fn reuse_word(r: Option<&Reuse>) -> Value {
    match r {
        None => Value::Null,
        Some(Reuse::Exact { key, from }) => json!({"exact": key.0, "from": from}),
        Some(Reuse::Callee { callee, key }) => json!({"callee": callee, "key": key.0}),
    }
}

/// One run of a frozen claim.
struct ClaimRun {
    outcome: spec::Outcome,
    key: Option<String>,
    exact: bool,
    /// Whether a JVM ran the witness: a refutation of the heap check is one by construction (an observation is
    /// refuted only where the replayed witness differs in it); the effect check's carries both builds' traces.
    replayed: bool,
    reused: Value,
    assumptions: Vec<String>,
}

#[derive(Clone, Copy)]
enum Check {
    /// `spec::heap::check_with`: a method's claim over objects, under the regression cache.
    Heap,
    /// `effects::check_planned`, `environment::check` under the cache: a method's claim under an environment.
    Planned,
}

fn run_claim(check: Check, claim: &CanonicalClaim, family: &str, name: &str, cache: &Path) -> ClaimRun {
    let (before, after) = (build(family, "before"), build(family, name));
    match check {
        Check::Heap => {
            let mut reused = spec::heap::Reused::default();
            let outcome = spec::heap::check_with(claim, &before, &after, Some(cache), &mut reused).unwrap_or_else(|u| panic!("{} {name}: refused: {u}", claim.contract.subject));
            let replayed = outcome.verdict == spec::Verdict::Refuted;
            let callees: Vec<Value> = reused.callees.iter().map(|r| reuse_word(Some(r))).collect();
            ClaimRun { exact: reused.exact.is_some(), key: reused.key.map(|k| k.0), replayed, reused: json!({"exact": reuse_word(reused.exact.as_ref()), "callees": callees}), assumptions: vec![], outcome }
        }
        Check::Planned => {
            let c = effects::check_planned(claim, &before, &after, Some(cache)).unwrap_or_else(|u| panic!("{} {name}: refused: {u}", claim.contract.subject));
            let replayed = c.before.is_some() && c.after.is_some();
            ClaimRun { exact: c.reuse.is_some(), key: c.key.map(|k| k.0), replayed, reused: json!({"exact": reuse_word(c.reuse.as_ref())}), assumptions: c.assumptions, outcome: c.outcome }
        }
    }
}

/// `run`'s outcome is what `expected` says, with no refusal: verified with every observation of `claim` preserved,
/// or refuted on the observation named, its witness replayed.
fn strictly(what: &str, claim: &CanonicalClaim, run: &ClaimRun, expected: &Value) {
    let o = &run.outcome;
    let ids: Vec<String> = claim.observations.iter().map(|x| x.id()).collect();
    for id in &ids {
        assert!(o.accounting.iter().any(|a| &a.observation == id), "{what}: the claim's observation {id} is accounted for: {o:?}");
    }
    match expected {
        Value::String(s) if s == "verified" => {
            assert_eq!(o.verdict, spec::Verdict::Verified, "{what}: {o:?}");
            for a in &o.accounting {
                assert!(matches!(a.state, ObservationState::Preserved | ObservationState::ChangedWithApproval), "{what}: {} is {:?} in a verified result", a.observation, a.state);
            }
        }
        Value::Array(a) => {
            assert_eq!(o.verdict, spec::Verdict::Refuted, "{what}: {o:?}");
            let observation = a[1].as_str().unwrap();
            let state = o.accounting.iter().find(|x| x.observation == observation).map(|x| x.state);
            assert_eq!(state, Some(ObservationState::Refuted), "{what}: {observation} refuted: {o:?}");
            assert!(o.witness.is_some(), "{what}: a refutation has its witness");
            assert!(run.replayed, "{what}: the witness ran on a JVM");
        }
        other => panic!("{what}: an expectation {other}"),
    }
}

fn record(row: &str, family: &str, claim: &str, name: &str, run_name: &str, expected: &Value, run: &ClaimRun) {
    let o = &run.outcome;
    evidence(json!({
        "row": row, "family": family, "claim": claim, "build": name, "run": run_name,
        "engine": "native (the tool's own checker, CaDiCaL), no JBMC",
        "key": run.key, "domain": o.domain, "expected": expected, "verdict": o.verdict,
        "accounting": o.accounting.iter().map(|a| json!([a.observation, a.state])).collect::<Vec<_>>(),
        "witness": o.witness, "replayed": run.replayed, "problem": o.problem,
        "reused": run.reused, "assumptions": run.assumptions,
    }));
}

/// Every build of `family` under the frozen claim `name`, each run cold and then again under one cache: the result
/// as expected each time, the rerun the stored result under the same key, and every build whose expected verdict
/// differs from `after`'s under another key, never answered by a stored result. `held` names a build held to
/// another outcome than `expected.json`'s, with the check it must pass instead (a user's decision still open).
fn claim_family(row: &str, family: &str, name: &str, check: Check, held: Option<(&str, &dyn Fn(&spec::Outcome))>) -> Vec<(String, Option<String>)> {
    let claim = golden(name);
    let cache = fresh(&format!("cache-{name}"));
    let mut keys: Vec<(String, Option<String>)> = Vec::new();
    let mut after_key = None;
    for (build_name, verdict) in cases(family, name) {
        let what = format!("{name} {build_name}");
        let cold = run_claim(check, &claim, family, &build_name, &cache);
        record(row, family, name, &build_name, "cold", &verdict, &cold);
        let key = cold.key.clone();
        assert!(key.is_some(), "{what}: the claim is cacheable, so that its reuse can be shown: {:?}", cold.outcome);
        match held {
            Some((held_name, hold)) if held_name == build_name => hold(&cold.outcome),
            _ => strictly(&what, &claim, &cold, &verdict),
        }
        if build_name == "after" {
            assert!(!cold.exact, "{what}: the first run under a fresh cache reuses nothing");
            after_key = key.clone();
        } else if verdict != expected()[family][name]["after"] {
            assert!(!cold.exact, "{what}: a build whose verdict differs from after's is never answered by a stored result");
            assert_ne!(key, after_key, "{what}: another key than after's");
        }
        let unresolved = cold.outcome.verdict == spec::Verdict::Unresolved;
        let again = run_claim(check, &claim, family, &build_name, &cache);
        record(row, family, name, &build_name, "rerun", &verdict, &again);
        assert_eq!(again.key, key, "{what}: the rerun has the same key");
        assert_eq!(again.outcome.verdict, cold.outcome.verdict, "{what}: the rerun has the same verdict");
        assert_eq!(again.outcome.accounting, cold.outcome.accounting, "{what}: the same accounting");
        // A verified or refuted result is stored, so its rerun is the stored one. An unresolved one is the gate's
        // after the proof (an allocation or input bound): the heap check stores the proof and applies the gate
        // again to the stored one, so its rerun may be a hit, with the gate's verdict again, as asserted above.
        if !unresolved {
            assert!(again.exact, "{what}: the rerun is the stored result");
        }
        keys.push((build_name, key));
    }
    keys
}

fn regression_options(family: &str, name: &str, target: &str, cache: Option<&Path>, work: &str) -> equivalence::Options {
    let mut o = equivalence::Options::new(&build(family, "before"), &build(family, name), target);
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.cache = cache.map(Path::to_path_buf);
    o.work = Some(fresh(work));
    o
}

fn regression_record(row: &str, target: &str, name: &str, run_name: &str, expected: &str, o: &equivalence::Outcome) {
    let confirmation = o.search.as_ref().and_then(|s| s.confirmation.as_ref());
    evidence(json!({
        "row": row, "target": target, "build": name, "run": run_name,
        "engine": o.search.as_ref().map(|s| s.checker.clone()),
        "domain": o.domain, "expected": expected, "verdict": format!("{:?}", o.verdict),
        "witness": o.counterexample.as_ref().map(|c| format!("{c:?}")),
        "replay": o.replay.as_ref().map(|r| json!({"by": r.by, "reproduced": r.reproduced})),
        "confirmation": confirmation.map(|c| json!({"status": c.status, "reason": c.reason})),
        "problem": o.problem, "reused": reuse_word(o.reuse.as_ref()), "proof": o.proof,
    }));
}

/// A plain regression check's outcome is what `expected` says, with no refusal: a violation replayed.
fn regression_strictly(what: &str, o: &equivalence::Outcome, expected: &str) {
    match expected {
        "verified" => assert_eq!(o.verdict, Verdict::Verified, "{what}: {}", o.output),
        "violation" => {
            assert_eq!(o.verdict, Verdict::Violation, "{what}: {}", o.output);
            assert!(o.replay.as_ref().is_some_and(|r| r.reproduced), "{what}: the witness replays: {}", o.output);
        }
        other => panic!("{what}: an expectation {other}"),
    }
}

/// Every build the `regressions` expectations name for `target`, cold and again under one cache, within `bound`.
fn regression_family(row: &str, family: &str, target: &str, bound: Option<u32>) {
    let cache = fresh(&format!("cache-{}", target.replace(['#', '.'], "-")));
    for (name, verdict) in cases("regressions", target) {
        let verdict = verdict.as_str().unwrap();
        let what = format!("{target} {name}");
        let mut outcomes = Vec::new();
        for run_name in ["cold", "rerun"] {
            let mut options = regression_options(family, &name, target, Some(&cache), &format!("{}-{name}-{run_name}", target.replace(['#', '.'], "-")));
            if let Some(b) = bound {
                options.max_array_length = b;
            }
            let o = equivalence::run(&options).unwrap();
            regression_record(row, target, &name, run_name, verdict, &o);
            regression_strictly(&format!("{what} {run_name}"), &o, verdict);
            outcomes.push(o);
        }
        if name == "after" {
            assert!(outcomes[0].reuse.is_none(), "{what}: the first run under a fresh cache reuses nothing");
        } else if verdict != "verified" {
            assert!(!matches!(outcomes[0].reuse, Some(Reuse::Exact { .. })), "{what}: a defect is never answered by a stored result");
        }
        assert!(matches!(outcomes[1].reuse, Some(Reuse::Exact { .. })), "{what}: the rerun is the stored result: {}", outcomes[1].output);
    }
}

/// J1: the quote family composes O, V, E and R on the merged revision, through the checks themselves (no
/// hand-written adapter): the receiver and the request made by their construction plan (O), the request's code a
/// bounded symbolic String (V), the rate, the offer and the event under one environment model (E), and the proof
/// cache and the helper's summary (R). Every case of `quote-claim` and `offer-claim` reaches its verdict with every
/// observation accounted for, each refutation replayed on a JVM, and each rerun is the stored result; `Codes#vip`
/// reaches its verdicts as a plain regression; `fee`'s summary rests on its own proof, is the stored one when asked
/// again, and the defect reading an extra field has none; `units`' property is reused exactly and another assertion
/// is another claim; and a change of the environment model is another key, checked again. `checked-claim` and
/// `fee` as a plain regression are apart, below.
#[test]
fn j1_the_quote_family_composes_the_four_streams() {
    claim_family("J1 (E1)", "quote", "quote-claim", Check::Planned, None);
    claim_family("J1 (E2)", "quote", "offer-claim", Check::Planned, None);
    regression_family("J1 (V1)", "quote", "quotes.Codes#vip", None);

    // Invalidation by the environment model: without the rate's modelled `RateUnavailable`, the claim is another
    // key, and `after` is checked again rather than answered by the stored proof.
    let cache = fresh("cache-quote-environment");
    let quote = golden("quote-claim");
    let full = run_claim(Check::Planned, &quote, "quote", "after", &cache);
    let mut fewer = quote.clone();
    let rate = &mut fewer.environment.as_mut().unwrap().calls[0];
    rate.model.as_mut().unwrap().results.pop();
    rate.outcomes.pop();
    let narrowed = run_claim(Check::Planned, &fewer, "quote", "after", &cache);
    record("J1 (J3)", "quote", "quote-claim without RateUnavailable", "after", "cold", &json!("verified"), &narrowed);
    assert_ne!(narrowed.key, full.key, "a modelled outcome less is another claim");
    assert!(!narrowed.exact, "and is never answered by the full model's stored proof");
    assert_eq!(narrowed.outcome.verdict, spec::Verdict::Verified, "{:?}", narrowed.outcome);

    // R2: `fee`'s summary, proved on its own under the cache, then the stored one; none for the extra read.
    let cache = fresh("cache-fee-summary");
    let fee = MemberRef::new("quotes/QuoteService", "fee", "(I)J");
    let summarize = |name: &str, run: &str| {
        let o = regression_options("quote", name, "quotes.QuoteService#quote", Some(&cache), run);
        reuse::summarize(&o, &fee, &fresh(&format!("{run}-summary")))
    };
    let summary = summarize("after", "fee-summary-cold").expect("fee's two versions have a summary");
    assert_eq!(summary.reads, ["this.feeCents", "arg0"]);
    let stored = |dir: &Path| -> usize { std::fs::read_dir(dir.join("claims")).map(|g| g.map(|e| std::fs::read_dir(e.unwrap().path()).unwrap().count()).sum()).unwrap_or(0) };
    let before_rerun = stored(&cache);
    let again = summarize("after", "fee-summary-rerun").unwrap();
    assert_eq!(again, summary, "the same summary, on the stored proof");
    assert_eq!(stored(&cache), before_rerun, "nothing new is stored");
    let extra = summarize("helper-extra-field", "fee-summary-extra").expect_err("an extra read has no summary");
    assert!(extra.what.contains("its two versions differ"), "{}", extra.what);
    evidence(json!({"row": "J1 (R2)", "helper": summary.helper, "summary": summary, "rerun": "the same summary, nothing new stored", "helper-extra-field": extra.what}));

    // R1: `units`' property under the cache, then its exact reuse; another assertion is another claim.
    let cache = fresh("cache-units-property");
    let units = |assertion: &str, run: &str| {
        let mut options = property::Options::new(&[build("quote", "after")], "quotes.QuoteService#units");
        options.engine = Engine::Native;
        options.jbmc = NO_JBMC.into();
        options.assert = Some(assertion.into());
        options.cache = Some(cache.clone());
        options.work = Some(fresh(run));
        let o = property::run(&options).unwrap();
        evidence(json!({"row": "J1 (R1)", "target": "quotes.QuoteService#units", "assert": assertion, "run": run, "verdict": format!("{:?}", o.verdict), "reused": reuse_word(o.reuse.as_ref()), "problem": o.problem}));
        o
    };
    let cold = units("quantities.length > 0 || result == 0", "units-cold");
    assert_eq!(cold.verdict, Verdict::Verified, "{}", cold.output);
    assert!(cold.reuse.is_none());
    let rerun = units("quantities.length > 0 || result == 0", "units-rerun");
    assert_eq!(rerun.verdict, Verdict::Verified, "{}", rerun.output);
    assert!(matches!(rerun.reuse, Some(Reuse::Exact { .. })), "{}", rerun.output);
    let other = units("quantities.length != 0 || result == 0", "units-other");
    assert_eq!(other.verdict, Verdict::Verified, "{}", other.output);
    assert!(other.reuse.is_none(), "another assertion is another claim: {}", other.output);
}

/// J1's R2 part on the quote family: the helper `fee` on its own, as a plain regression on a receiver made by its
/// constructor, the service's three dependencies (interfaces `fee` never reaches) passed null; `helper-extra-field`'s
/// extra read refuted, its witness run on a JVM, which calls the package-private helper. Each rerun is the stored
/// result.
///
/// Found by the joint acceptance at the merge, refused then ("only a concrete class made by its constructor"), and
/// so part of the job after its first (`20261108-180246-…`): its own job.
#[test]
fn j1_r2_a_receiver_with_dependencies() {
    regression_family("J1 (R2)", "quote", "quotes.QuoteService#fee", None);
}

/// J1's O2 part on the quote family: `checked` hands back the caller's own request, made by its plan with its code
/// and quantities, and `alias-to-copy`'s copy is refuted on identity alone, under `checked-claim`. Each rerun is the
/// stored result.
///
/// The service's dependencies are passed null now, as for R2. The request's String code is still refused: the heap
/// check's plan doesn't make an adapted value inside a node, and an object with a String field isn't observed by
/// the regression check ("the values stream builds it"). Ignored until it is, the next piece of work of the brief's
/// Progress, and not part of a job until then.
#[test]
#[ignore = "refused: the regression check doesn't make a String inside an object yet (application-core.md's Progress)"]
fn j1_o2_a_receiver_with_dependencies_and_a_request_with_a_string() {
    claim_family("J1 (O2)", "quote", "checked-claim", Check::Heap, None);
}

/// H: the throttle family. Right after the constructor, `after-setup` is verified, labelled for that domain only,
/// and `one-short` refuted; after one `take`, both are refuted, the witness holding the whole history (the
/// construction, the setup call, the target), replayed on a JVM. The two domains are two claims: every build has
/// another key under each. `allows` also reaches its verdicts as a plain regression and as a property.
#[test]
fn h_the_throttle_family() {
    let constructed = claim_family("H (O3)", "throttle", "throttle-constructed-claim", Check::Heap, None);
    let setup = claim_family("H (O3)", "throttle", "throttle-setup-claim", Check::Heap, None);
    for ((name, a), (_, b)) in constructed.iter().zip(&setup) {
        assert_ne!(a, b, "{name}: the constructor-only and the setup domain are two claims");
    }
    let claim = golden("throttle-constructed-claim");
    let o = spec::heap::check(&claim, &build("throttle", "before"), &build("throttle", "after-setup")).unwrap();
    assert!(o.domain.contains("right after its constructor"), "the constructor-only result is labelled so: {}", o.domain);
    let claim = golden("throttle-setup-claim");
    let o = spec::heap::check(&claim, &build("throttle", "before"), &build("throttle", "after-setup")).unwrap();
    let witness = o.witness.clone().unwrap_or_default();
    assert!(witness.contains("take"), "the witness holds the setup call: {witness}");
    assert!(o.domain.contains("one call of take"), "{}", o.domain);

    regression_family("H (O1)", "throttle", "throttle.Throttle#allows", None);
    let mut options = property::Options::new(&[build("throttle", "after")], "throttle.Throttle#allows");
    options.engine = Engine::Native;
    options.jbmc = NO_JBMC.into();
    options.assume = Some("n >= 0".into());
    options.assert = Some("result || n > 0".into());
    options.work = Some(fresh("allows-property"));
    let o = property::run(&options).unwrap();
    evidence(json!({"row": "H (O1)", "target": "throttle.Throttle#allows", "assert": "result || n > 0", "verdict": format!("{:?}", o.verdict), "problem": o.problem}));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
}

/// L: the basket family over a bounded immutable list. `total`, `first` and `clearAll` reach their verdicts under
/// their frozen claims and as plain regressions within the claims' bound of 3: order, duplicates and identity kept,
/// each defect refuted and replayed. `basket-first-claim`'s `copied-first` is held to the allocation gate's outcome
/// until the user decides its bound (the brief's Progress). A smaller list bound is another claim, checked again.
#[test]
fn l_the_basket_family() {
    claim_family("L (V2)", "basket", "basket-total-claim", Check::Heap, None);
    claim_family("L (V2)", "basket", "basket-clear-claim", Check::Heap, None);
    let gate = |o: &spec::Outcome| {
        assert_eq!(o.verdict, spec::Verdict::Unresolved, "copied-first under basket-first-claim: {o:?}");
        assert!(o.problem.as_deref().is_some_and(|p| p.contains("more than the claim's allocation bound of 0")), "{o:?}");
    };
    claim_family("L (V2)", "basket", "basket-first-claim", Check::Heap, Some(("copied-first", &gate)));
    regression_family("L (V2)", "basket", "basket.Basket#total", Some(3));
    regression_family("L (V2)", "basket", "basket.Basket#clearAll", Some(3));

    let cache = fresh("cache-basket-bound");
    let total = golden("basket-total-claim");
    let three = run_claim(Check::Heap, &total, "basket", "after", &cache);
    let mut shorter = total.clone();
    if let Some(Construction::Planned { before, after }) = shorter.domain.as_mut().map(|d| &mut d.made_by) {
        for plan in [before, after] {
            if let spec::plans::PlanValue::Adapted { domain, .. } = &mut plan.roots[0].value {
                domain.max_length = 2;
            }
        }
    }
    let two = run_claim(Check::Heap, &shorter, "basket", "after", &cache);
    record("L (J3)", "basket", "basket-total-claim within 2", "after", "cold", &json!("verified"), &two);
    assert_ne!(two.key, three.key, "a smaller list bound is another claim");
    assert!(!two.exact, "and never borrows the larger bound's stored proof");
    assert_eq!(two.outcome.verdict, spec::Verdict::Verified, "{:?}", two.outcome);
}

/// J2: the new native claims with JBMC unavailable, under `--engine auto`, the default for a person who has no
/// JBMC: each reaches its verdict on the own checker, and `--confirm` says explicitly what became of the
/// confirmation, never a verdict of JBMC's. An ordinary receiver's proof is left unconfirmed (JBMC gave none: it
/// isn't installed); a String's and a list's are not asked, since JBMC wouldn't check the same claim. A defect is
/// still refuted and replayed, and a property is still proved.
#[test]
fn j2_the_native_claims_without_jbmc() {
    assert!(Command::new(NO_JBMC).arg("--version").output().is_err(), "{NO_JBMC} is no JBMC");
    let auto = |family: &str, name: &str, target: &str, bound: Option<u32>, confirm: bool, work: &str| {
        let mut o = regression_options(family, name, target, None, work);
        o.engine = Engine::Auto;
        o.confirm = confirm;
        if let Some(b) = bound {
            o.max_array_length = b;
        }
        let outcome = equivalence::run(&o).unwrap();
        regression_record("J2", target, name, if confirm { "auto --confirm" } else { "auto" }, "", &outcome);
        outcome
    };
    for (family, target, bound, status, reason) in [
        ("throttle", "throttle.Throttle#allows", None, Confirmed::NoVerdict, "not installed"),
        ("quote", "quotes.Codes#vip", None, Confirmed::NotAsked, "a String parameter"),
        ("basket", "basket.Basket#total", Some(3), Confirmed::NotAsked, "a list parameter"),
    ] {
        let o = auto(family, "after", target, bound, true, &format!("j2-{family}-confirm"));
        assert_eq!(o.verdict, Verdict::Verified, "{target}: {}", o.output);
        let search = o.search.as_ref().expect("a search");
        assert!(search.checker.contains("own checker"), "{target}: the own checker proved it: {}", search.checker);
        let c = search.confirmation.as_ref().expect("--confirm records what became of the confirmation");
        assert_eq!(c.status, status, "{target}: {c:?}");
        assert!(c.reason.as_deref().is_some_and(|r| r.contains(reason)), "{target}: {c:?}");
        // A confirmation JBMC was asked for names it as the checker asked (`JBMC`, with no version, since none ran);
        // its status says it gave no verdict.
        assert!(c.checker.as_deref().is_none_or(|v| !v.contains('.')), "{target}: no JBMC ran: {c:?}");
    }
    for (family, defect, target, bound) in [
        ("throttle", "one-short", "throttle.Throttle#allows", None),
        ("quote", "wrong-prefix", "quotes.Codes#vip", None),
        ("basket", "duplicate-skipped", "basket.Basket#total", Some(3)),
    ] {
        let o = auto(family, defect, target, bound, false, &format!("j2-{family}-{defect}"));
        regression_strictly(&format!("{target} {defect} under auto"), &o, "violation");
    }
    let mut options = property::Options::new(&[build("quote", "after")], "quotes.QuoteService#units");
    options.engine = Engine::Auto;
    options.jbmc = NO_JBMC.into();
    options.assert = Some("quantities.length > 0 || result == 0".into());
    options.work = Some(fresh("j2-units-property"));
    let o = property::run(&options).unwrap();
    evidence(json!({"row": "J2", "target": "quotes.QuoteService#units", "engine": "auto", "verdict": format!("{:?}", o.verdict), "problem": o.problem}));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
}
