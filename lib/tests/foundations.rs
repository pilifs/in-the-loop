//! The integration contract of `llm-dlc/loops/foundations.md` (Phase 0): the joint example's fixture, the golden
//! files of its IR, and a check per stream's part. `llm-dlc/tools/foundations-integration.sh` runs it on a merge of
//! the four streams while they work.
//!
//! A part passes when it reaches the verdict `golden/expected.json` gives each case, or still returns its named
//! [`Unsupported`]; it fails on anything else (a wrong verdict, a different error, a result that drops a required
//! observation). The test prints which parts are still unsupported, so the integration report shows progress as well
//! as breakage. The joint example is done when nothing is unsupported.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::spec::observe::{Change, EntryPointSpec};
use jvmcontract::spec::{
    align, cache, heap, observe, CanonicalClaim, Correspondence, Derivation, EnvironmentModel, Evidence, HintContent, Hints, Intent,
    ObjectDomain, Observation, OrderPolicy, Outcome, Part, PreservationContract, Unsupported, Verdict,
};
use serde::de::DeserializeOwned;
use serde::Serialize;
use serde_json::Value;

const DEFECTS: &[&str] = &["offset", "alias-to-copy", "dropped-effect", "duplicated-effect", "outside-domain", "route-change"];

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/foundations")
}

fn golden<T: DeserializeOwned>(name: &str) -> T {
    let path = root().join("golden").join(format!("{name}.json"));
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    serde_json::from_str(&text).unwrap_or_else(|e| panic!("{}: {e}", path.display()))
}

/// Parses a golden file as `T` and writes it back: the same JSON, so the file and the type agree on every field.
fn round_trips<T: DeserializeOwned + Serialize>(name: &str) {
    let path = root().join("golden").join(format!("{name}.json"));
    let original: Value = serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
    let parsed: T = serde_json::from_value(original.clone()).unwrap_or_else(|e| panic!("{name}.json: {e}"));
    assert_eq!(serde_json::to_value(&parsed).unwrap(), original, "{name}.json round-trips");
}

#[test]
fn the_golden_files_are_the_shared_types() {
    round_trips::<PreservationContract>("contract");
    round_trips::<PreservationContract>("kernel-contract");
    round_trips::<ObjectDomain>("domain");
    round_trips::<Vec<Observation>>("observations");
    round_trips::<Correspondence>("correspondence");
    round_trips::<EnvironmentModel>("environment");
    round_trips::<CanonicalClaim>("claim");
    round_trips::<CanonicalClaim>("kernel-claim");
    round_trips::<Outcome>("outcome");
    round_trips::<Hints>("hints");
}

#[test]
fn the_golden_claims_hold_together() {
    let claim: CanonicalClaim = golden("claim");
    let required: Vec<String> = claim.observations.iter().map(Observation::id).collect();
    assert_eq!(claim.contract.required, required, "the entry point's claim observes exactly what its contract requires");
    assert!(claim.contract.inputs.iter().all(|i| i.derivation == Derivation::Identity), "the entry point's inputs are anchored");
    assert_eq!(claim.environment.as_ref().map(|e| e.order), Some(OrderPolicy::Exact));
    let kernel: CanonicalClaim = golden("kernel-claim");
    let domain = kernel.domain.as_ref().expect("the kernel claim has an object domain");
    assert!(domain.label.contains("constructor"), "a constructor-made domain says so");
    let hints: Hints = golden("hints");
    assert!(hints.entries.iter().all(|h| h.intent == Intent::Proposed && h.evidence == Evidence::Unchecked), "nothing inferred starts approved or proved");
}

// The fixture's builds.

fn has(program: &str) -> bool {
    let found = Command::new(program).arg("-version").output().is_ok();
    if !found {
        let skip = std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1");
        assert!(skip, "{program} not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip the tests that need it");
    }
    found
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

/// The builds by name: `before`, `after`, and each defect overlaid on `after` (its files replace theirs). Compiled once,
/// against the Spring stand-ins of `tests/fixtures/spring/org`. None without javac.
fn builds() -> Option<&'static Vec<(String, PathBuf)>> {
    static BUILDS: OnceLock<Option<Vec<(String, PathBuf)>>> = OnceLock::new();
    BUILDS
        .get_or_init(|| {
            if !has("javac") {
                return None;
            }
            let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("foundations");
            let _ = std::fs::remove_dir_all(&out);
            let spring = out.join("spring");
            let stand_ins = java_files(&Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/spring/org"));
            javac(&spring, &[], &stand_ins);
            let after = java_files(&root().join("after"));
            let mut builds = vec![("before".to_string(), java_files(&root().join("before"))), ("after".to_string(), after.clone())];
            for defect in DEFECTS {
                let dir = root().join("defects").join(defect);
                let overlay = java_files(&dir);
                let names: Vec<_> = overlay.iter().map(|p| p.strip_prefix(&dir).unwrap().to_path_buf()).collect();
                let mut files: Vec<PathBuf> = after.iter().filter(|p| !names.contains(&p.strip_prefix(root().join("after")).unwrap().to_path_buf())).cloned().collect();
                files.extend(overlay);
                builds.push((defect.to_string(), files));
            }
            Some(
                builds
                    .into_iter()
                    .map(|(name, files)| {
                        let dir = out.join(&name);
                        javac(&dir, &[&spring], &files);
                        (name, dir)
                    })
                    .collect(),
            )
        })
        .as_ref()
}

fn javac(out: &Path, classpath: &[&Path], files: &[PathBuf]) {
    std::fs::create_dir_all(out).unwrap();
    let mut cmd = Command::new("javac");
    cmd.args(["-g", "-parameters", "-proc:none", "-d"]).arg(out);
    if !classpath.is_empty() {
        cmd.arg("-cp").arg(std::env::join_paths(classpath).unwrap());
    }
    let status = cmd.args(files).status().expect("javac runs");
    assert!(status.success(), "the foundations fixture compiles into {}", out.display());
}

fn build(name: &str) -> &'static Path {
    &builds().unwrap().iter().find(|(n, _)| n == name).unwrap_or_else(|| panic!("no build {name}")).1
}

// The parts.

#[derive(Default)]
struct Report {
    pending: Vec<String>,
    failures: Vec<String>,
    passed: Vec<String>,
}

impl Report {
    /// A part's result for one check: passed, still unsupported, or failed (with why).
    fn take<T>(&mut self, check: &str, result: Result<T, Unsupported>, judge: impl FnOnce(T) -> Result<(), String>) {
        match result {
            Err(u) => self.pending.push(format!("{check}: {u}")),
            Ok(value) => match judge(value) {
                Ok(()) => self.passed.push(check.to_string()),
                Err(why) => self.failures.push(format!("{check}: {why}")),
            },
        }
    }
}

fn expected_cases() -> Vec<Value> {
    let expected: Value = golden("expected");
    expected["cases"].as_array().unwrap().clone()
}

fn verdict(case: &Value) -> Verdict {
    serde_json::from_value(case["verdict"].clone()).unwrap()
}

/// The heap part: the kernel subjects (`pkg.Class#method`) under the golden correspondence and domain.
fn heap_part(report: &mut Report) {
    let kernel: CanonicalClaim = golden("kernel-claim");
    for case in expected_cases().iter().filter(|c| !c["subject"].as_str().unwrap().starts_with("POST ")) {
        let (b, subject) = (case["build"].as_str().unwrap(), case["subject"].as_str().unwrap());
        let mut claim = kernel.clone();
        claim.contract.subject = subject.to_string();
        if let Some(obs) = case.get("observations") {
            let extra: Vec<Observation> = serde_json::from_value(obs.clone()).unwrap();
            claim.contract.required.extend(extra.iter().map(Observation::id));
            claim.observations.extend(extra);
        }
        let want = verdict(case);
        let mention = case.get("domain_mentions").and_then(Value::as_str).map(str::to_string);
        let required = claim.contract.required.clone();
        report.take(&format!("heap {b} {subject}"), heap::check(&claim, build("before"), build(b)), |o| {
            if o.verdict != want {
                return Err(format!("{:?}, expected {:?}", o.verdict, want));
            }
            if want == Verdict::Refuted && o.witness.is_none() {
                return Err("a refutation without a witness".into());
            }
            if let Some(m) = mention {
                if !o.domain.contains(&m) {
                    return Err(format!("its domain '{}' doesn't say '{m}'", o.domain));
                }
            }
            let accounted: Vec<&str> = o.accounting.iter().map(|a| a.observation.as_str()).collect();
            match required.iter().find(|r| !accounted.contains(&r.as_str())) {
                Some(r) => Err(format!("the observation {r} is missing from the accounting")),
                None => Ok(()),
            }
        });
    }
}

/// The observations part: the entry points' specs, and two builds compared into obligations.
fn observations_part(report: &mut Report) {
    let golden_obs: Vec<Observation> = golden("observations");
    let specs = |b: &str| observe::entry_points(build(b));
    let find = |specs: &[EntryPointSpec], id: &str| specs.iter().find(|s| s.id == id).cloned();
    report.take("observations specs before", specs("before"), |s| {
        let quotes = find(&s, "POST /quotes").ok_or("no POST /quotes")?;
        if !quotes.inputs.iter().all(|i| i.derivation == Derivation::Identity) {
            return Err("an entry point's inputs are anchored, by identity".into());
        }
        if let Some(missing) = golden_obs.iter().find(|o| !quotes.observations.contains(o)) {
            return Err(format!("POST /quotes doesn't observe {}", missing.id()));
        }
        let text = find(&s, "POST /quotes/text").ok_or("no POST /quotes/text")?;
        if text.unresolved.is_empty() {
            return Err("POST /quotes/text's string concatenation isn't named as unresolved".into());
        }
        Ok(())
    });
    for case in expected_cases().iter().filter(|c| c["subject"].as_str().unwrap().starts_with("POST ")) {
        let (b, subject) = (case["build"].as_str().unwrap(), case["subject"].as_str().unwrap());
        let want = case.get("obligations").cloned();
        let result = specs("before").and_then(|old| specs(b).and_then(|new| observe::compare(&old, &new)));
        report.take(&format!("observations compare {b} {subject}"), result, |obligations| {
            let mine: Vec<_> = obligations.iter().filter(|o| o.entry == subject).collect();
            if mine.is_empty() {
                return Err(format!("no obligation for {subject}"));
            }
            match &want {
                Some(Value::Object(changes)) => {
                    for (entry, change) in changes {
                        let change: Change = serde_json::from_value(change.clone()).unwrap();
                        if !obligations.iter().any(|o| &o.entry == entry && o.change == change) {
                            return Err(format!("{entry} isn't {change:?}"));
                        }
                    }
                }
                _ if verdict(case) != Verdict::Unresolved => {
                    let old = golden_obs.iter().map(Observation::id);
                    for id in old {
                        if !mine.iter().any(|o| o.observation == id) {
                            return Err(format!("the old observation {id} is not accounted for"));
                        }
                    }
                }
                _ => {}
            }
            Ok(())
        });
    }
    let claim: CanonicalClaim = golden("claim");
    for case in expected_cases().iter().filter(|c| c["subject"].as_str().unwrap().starts_with("POST ") && c.get("obligations").is_none()) {
        let (b, subject) = (case["build"].as_str().unwrap(), case["subject"].as_str().unwrap());
        let want = verdict(case);
        let mut claim = claim.clone();
        claim.contract.subject = subject.to_string();
        let required = claim.contract.required.clone();
        let result = specs("before").and_then(|old| {
            let new = specs(b)?;
            let missing = || Unsupported::new(Part::Observations, format!("no spec for {subject}"));
            observe::check(&claim, &find(&old, subject).ok_or_else(missing)?, &find(&new, subject).ok_or_else(missing)?, build("before"), build(b))
        });
        report.take(&format!("observations check {b} {subject}"), result, |o| {
            if o.verdict != want {
                return Err(format!("{:?}, expected {:?}", o.verdict, want));
            }
            if want == Verdict::Refuted && o.witness.is_none() {
                return Err("a refutation without a witness".into());
            }
            if want == Verdict::Verified {
                let accounted: Vec<&str> = o.accounting.iter().map(|a| a.observation.as_str()).collect();
                if let Some(r) = required.iter().find(|r| !accounted.contains(&r.as_str())) {
                    return Err(format!("the observation {r} is missing from the accounting"));
                }
            }
            Ok(())
        });
    }
    report.take("observations effect log", specs("after").and_then(|s| {
        let quotes = find(&s, "POST /quotes").ok_or_else(|| Unsupported::new(Part::Observations, "no POST /quotes"))?;
        observe::effect_log(&quotes)
    }), |plan| {
        if plan.environment.order != OrderPolicy::Exact || plan.environment.trace_bound == 0 {
            return Err("the effect log compares in exact order, within a bound".into());
        }
        Ok(())
    });
}

/// The alignment part: the correspondence it proposes for the kernel, and what it must never propose.
fn alignment_part(report: &mut Report) {
    let contract: PreservationContract = golden("kernel-contract");
    let want: Correspondence = golden("correspondence");
    for b in ["after", "offset"] {
        report.take(&format!("alignment propose {b}"), align::propose(&contract, build("before"), build(b)), |hints| {
            if let Some(h) = hints.entries.iter().find(|h| h.intent == Intent::Approved) {
                return Err(format!("an inferred hint for {} starts approved", h.subject));
            }
            let correspondences: Vec<&Correspondence> = hints
                .entries
                .iter()
                .filter_map(|h| match &h.content {
                    HintContent::Correspondence { correspondence } => Some(correspondence),
                    _ => None,
                })
                .collect();
            if b == "after" && !correspondences.contains(&&want) {
                return Err("the golden correspondence is not among the proposals".into());
            }
            if b == "offset" {
                if let Some(c) = correspondences.iter().find(|c| c.inputs.iter().any(|e| e.new.contains('+') || e.new.contains('-'))) {
                    return Err(format!("a proposal shifts an input: {:?}", c.inputs));
                }
            }
            Ok(())
        });
    }
}

/// The summaries part: claim keys that tell claims apart exactly, and a cache that gives back what it stored.
fn summaries_part(report: &mut Report) {
    let claim: CanonicalClaim = golden("claim");
    let outcome: Outcome = golden("outcome");
    report.take("summaries keys", cache::key(&claim), |k| {
        let same = cache::key(&claim.clone()).map_err(|u| u.to_string())?;
        if same != k {
            return Err("the same claim gives two keys".into());
        }
        let mut moved = claim.clone();
        moved.contract.subject = "POST /quote".into();
        let mut bounds = claim.clone();
        bounds.bounds.unwind += 1;
        let mut stub = claim.clone();
        stub.assumptions.push("another stub".into());
        for (what, other) in [("the route", moved), ("the unwinding bound", bounds), ("an assumption", stub)] {
            if cache::key(&other).map_err(|u| u.to_string())? == k {
                return Err(format!("changing {what} keeps the key"));
            }
        }
        Ok(())
    });
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("foundations-cache");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let stored = cache::key(&claim).and_then(|key| {
        if cache::lookup(&dir, &key)?.is_some() {
            return Ok(Err("an empty cache has a hit".to_string()));
        }
        let record = cache::ResultRecord { key: key.clone(), outcome: outcome.clone(), provenance: "lib/tests/foundations.rs".into() };
        cache::store(&dir, &record)?;
        Ok(match cache::lookup(&dir, &key)? {
            Some(r) if r.outcome == outcome => Ok(()),
            Some(_) => Err("the cache gave back a different outcome".to_string()),
            None => Err("a stored result is a miss".to_string()),
        })
    });
    report.take("summaries cache", stored, |r| r);
    for case in expected_cases().iter().filter(|c| c.get("reused_in").is_some()) {
        let (callee, caller) = (case["subject"].as_str().unwrap(), case["reused_in"].as_str().unwrap());
        report.take(&format!("summaries reuse of {callee} in {caller}"), cache::callee_reuse(&dir, caller, build("before"), build("after")), |reuse| {
            if reuse.iter().any(|r| matches!(r, cache::Reuse::Callee { callee: c, .. } if c == callee)) {
                Ok(())
            } else {
                Err(format!("{caller}'s check doesn't reuse {callee}'s proof"))
            }
        });
    }
}

#[test]
fn the_integration_contract() {
    if builds().is_none() {
        return;
    }
    let mut report = Report::default();
    heap_part(&mut report);
    observations_part(&mut report);
    alignment_part(&mut report);
    summaries_part(&mut report);
    println!("integration contract: {} passed, {} still unsupported, {} failed", report.passed.len(), report.pending.len(), report.failures.len());
    for p in &report.passed {
        println!("  passed       {p}");
    }
    for p in &report.pending {
        println!("  unsupported  {p}");
    }
    for f in &report.failures {
        println!("  FAILED       {f}");
    }
    assert!(report.failures.is_empty(), "{} part(s) of the integration contract failed: {:?}", report.failures.len(), report.failures);
}
