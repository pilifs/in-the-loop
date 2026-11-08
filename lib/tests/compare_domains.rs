//! `compare --domains` (`compare::Options::domains`): a domain a person declares for a kernel subject is that
//! subject's claim domain, passed to the heap check as it is. On the shared contract's throttle family
//! (`tests/fixtures/application-core/throttle`) and its two frozen claims' domains: `after-setup` is one unit short
//! only once a setup call has taken some, so `compare` verifies it over the constructor domain, and refutes it, with
//! the whole history replayed on a JVM, over the setup plan's domain. Each capability has its correct case, its
//! planted defect, its named refusals, and its cached evidence kept apart from another domain's.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::compare::{self, KernelCheck, Options, Report};
use jvmcontract::spec::cache::Reuse;
use jvmcontract::spec::{ClaimBounds, Construction, ObjectDomain, ObservationState, Outcome, Verdict};

const SUBJECT: &str = "throttle.Throttle#allows";

/// A build of the throttle family: `before`, `after`, or a defect overlaid on `after`, compiled under `name`.
fn throttle(name: &str, build: &str) -> PathBuf {
    let family = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/application-core/throttle");
    let overlay = family.join("defects").join(build);
    let file = if overlay.exists() { overlay } else { family.join(if build == "before" { "before" } else { "after" }) }.join("throttle/Throttle.java");
    let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("compare-domains").join(name).join(build);
    let _ = std::fs::remove_dir_all(&out);
    let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out).arg(file).status().expect("the tests need javac");
    assert!(status.success(), "{build} compiles");
    out
}

/// The domain of a frozen throttle claim (`golden/NAME.json`), as a person would declare it.
fn domain(name: &str) -> ObjectDomain {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join(format!("tests/fixtures/application-core/golden/{name}.json"));
    let claim: jvmcontract::spec::CanonicalClaim = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    claim.domain.unwrap()
}

fn options(before: &Path, after: &Path, cache: Option<&Path>, domains: &[(&str, ObjectDomain)]) -> Options {
    Options {
        before: before.to_path_buf(),
        after: after.to_path_buf(),
        cache: cache.map(Path::to_path_buf),
        bounds: ClaimBounds { unwind: 16, max_array_length: 8 },
        environment: Vec::new(),
        domains: domains.iter().map(|(s, d)| (s.to_string(), d.clone())).collect(),
    }
}

fn run(before: &Path, after: &Path, cache: Option<&Path>, domains: &[(&str, ObjectDomain)]) -> Report {
    compare::run(&options(before, after, cache, domains)).unwrap_or_else(|u| panic!("compare {}: {u}", after.display()))
}

fn kernel(r: &Report) -> &KernelCheck {
    r.kernel.iter().find(|k| k.subject == SUBJECT).unwrap_or_else(|| panic!("no kernel pair {SUBJECT}: {:?}", r.kernel))
}

fn outcome(r: &Report) -> &Outcome {
    let k = kernel(r);
    k.outcome.as_ref().unwrap_or_else(|| panic!("{SUBJECT} unchecked: {:?}", k.unsupported))
}

/// The correct case and the planted defect: over the constructor domain `compare` verifies `after-setup`, labelled
/// so; over the declared setup plan it refutes it on the result, the witness the whole history; the rewrite `after`
/// is verified over it, and `one-short` refuted over the constructor-only plan. The claim carries the declared domain
/// as it is, and the effort report counts it as a person's domain restriction.
#[test]
fn a_subjects_declared_domain_is_its_kernel_claims_domain() {
    let before = throttle("claim", "before");
    let (setup, constructed) = (domain("throttle-setup-claim"), domain("throttle-constructed-claim"));

    let plain = run(&before, &throttle("claim", "after-setup"), None, &[]);
    assert_eq!(outcome(&plain).verdict, Verdict::Verified, "{:?}", outcome(&plain));
    assert!(outcome(&plain).domain.contains("made by its constructor"), "{}", outcome(&plain).domain);
    assert_eq!(kernel(&plain).claim.domain, None);
    assert_eq!(plain.effort.decisions.get("domain restriction"), Some(&0), "{:?}", plain.effort.decisions);

    let history = run(&before, &throttle("claim", "after-setup"), None, &[(SUBJECT, setup.clone())]);
    let o = outcome(&history);
    assert_eq!(o.verdict, Verdict::Refuted, "{o:?}");
    let witness = o.witness.as_deref().unwrap();
    assert!(witness.contains("allows(this=new Throttle(") && witness.contains("after the setup this.take(setup.0.n="), "the whole history: {witness}");
    assert!(o.accounting.iter().any(|a| a.observation == "result" && a.state == ObservationState::Refuted), "{o:?}");
    assert!(o.domain.starts_with(&setup.label) && o.domain.contains("this after the setup this.take(setup.0.n)"), "the declared domain is the result's: {}", o.domain);
    assert_eq!(kernel(&history).claim.domain.as_ref(), Some(&setup), "the claim carries the declared domain as it is");
    assert_eq!(history.effort.decisions.get("domain restriction"), Some(&1), "{:?}", history.effort.decisions);
    assert!(!history.all_verified());
    assert!(compare::render(&history).contains("domain restriction 1"));

    let rewrite = run(&before, &throttle("claim", "after"), None, &[(SUBJECT, setup.clone())]);
    assert_eq!(outcome(&rewrite).verdict, Verdict::Verified, "{:?}", outcome(&rewrite));
    assert!(rewrite.all_verified());

    let zero = run(&before, &throttle("claim", "after-setup"), None, &[(SUBJECT, constructed.clone())]);
    assert_eq!(outcome(&zero).verdict, Verdict::Verified, "{:?}", outcome(&zero));
    assert!(outcome(&zero).domain.contains("right after its constructor") && !outcome(&zero).domain.contains("setup"), "the constructor-only scope is labelled: {}", outcome(&zero).domain);
    let short = run(&before, &throttle("claim", "one-short"), None, &[(SUBJECT, constructed)]);
    assert_eq!(outcome(&short).verdict, Verdict::Refuted, "{:?}", outcome(&short));
}

/// The cached evidence: an exact rerun under the declared domain is the stored result; the same subject under the
/// constructor-only plan is another claim and is checked again; and an edit of the target under the declared domain
/// is never answered by the stored proof. The proof cache keys the check a domain makes (its harness, the methods
/// that make its inputs, the stated domain), not the domain's label or bounds, which the heap check enforces after
/// it: so the constructor-only plan, which makes exactly the constructor domain's harness, and no declared domain
/// share one stored proof, each result stating its own domain.
#[test]
fn a_declared_domain_is_part_of_the_cached_claim() {
    let cache = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("compare-domains-cache");
    let _ = std::fs::remove_dir_all(&cache);
    let before = throttle("cache", "before");
    let after = throttle("cache", "after");
    let (setup, constructed) = (domain("throttle-setup-claim"), domain("throttle-constructed-claim"));
    let key = |r: &Report| match &kernel(r).reuse {
        Some(Reuse::Exact { key, .. }) => key.clone(),
        other => panic!("not an exact hit: {other:?}"),
    };

    let cold = run(&before, &after, Some(&cache), &[(SUBJECT, setup.clone())]);
    assert_eq!(outcome(&cold).verdict, Verdict::Verified, "{:?}", outcome(&cold));
    assert!(kernel(&cold).reuse.is_none(), "nothing to reuse on a cold cache");
    let warm = run(&before, &after, Some(&cache), &[(SUBJECT, setup.clone())]);
    let setup_key = key(&warm);
    assert_eq!((outcome(&warm).verdict, &outcome(&warm).domain), (outcome(&cold).verdict, &outcome(&cold).domain), "the exact rerun is the stored result");

    let zero = run(&before, &after, Some(&cache), &[(SUBJECT, constructed.clone())]);
    assert_eq!(outcome(&zero).verdict, Verdict::Verified, "{:?}", outcome(&zero));
    assert!(kernel(&zero).reuse.is_none(), "the constructor-only plan is another claim than the setup plan's, checked again: {:?}", kernel(&zero).reuse);
    let zero_key = key(&run(&before, &after, Some(&cache), &[(SUBJECT, constructed)]));
    assert_ne!(zero_key, setup_key);
    let plain = run(&before, &after, Some(&cache), &[]);
    assert_eq!(key(&plain), zero_key, "the constructor domain's check is the constructor-only plan's");
    assert!(outcome(&plain).domain.starts_with("this: a Throttle made by its constructor"), "the reused result states its own claim's domain: {}", outcome(&plain).domain);

    let defect = run(&before, &throttle("cache", "after-setup"), Some(&cache), &[(SUBJECT, setup)]);
    assert_eq!(outcome(&defect).verdict, Verdict::Refuted, "an edit of the target is never answered by the stored proof: {:?}", outcome(&defect));
    assert!(kernel(&defect).reuse.is_none());
}

/// The named refusals: a domain for a subject the run checks no claim of, a domain the heap check doesn't build, and
/// a domain file with a field a domain doesn't have, a subject that isn't a method, or a plan the plan check refuses.
/// None is read as another domain.
#[test]
fn a_domain_compare_cannot_read_is_refused_by_name() {
    let before = throttle("refusals", "before");
    let after = throttle("refusals", "after-setup");
    let setup = domain("throttle-setup-claim");

    for subject in ["throttle.Throttle#take", "throttle.Throttle#allow"] {
        let refused = compare::run(&options(&before, &after, None, &[(subject, setup.clone())])).expect_err(subject).what;
        assert!(refused.contains(subject) && refused.contains("checks no kernel claim of") && refused.contains(SUBJECT), "{subject}: {refused}");
    }

    let mut field_by_field = setup.clone();
    field_by_field.made_by = Construction::FieldByField {};
    let r = run(&before, &after, None, &[(SUBJECT, field_by_field)]);
    assert!(kernel(&r).outcome.is_none(), "{:?}", kernel(&r).outcome);
    assert!(kernel(&r).unsupported.as_deref().unwrap_or_default().contains("field by field"), "{:?}", kernel(&r).unsupported);

    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("compare-domains-files");
    std::fs::create_dir_all(&dir).unwrap();
    let file = |name: &str, value: serde_json::Value| {
        let path = dir.join(name);
        std::fs::write(&path, serde_json::to_string(&value).unwrap()).unwrap();
        path
    };
    let base = serde_json::to_value(&setup).unwrap();
    let with = |edit: &dyn Fn(&mut serde_json::Value)| {
        let mut d = base.clone();
        edit(&mut d);
        d
    };
    let good = file("good.json", serde_json::json!({ SUBJECT: base.clone() }));
    let read = compare::load_domains(&good).unwrap();
    assert_eq!(read, BTreeMap::from([(SUBJECT.to_string(), setup.clone())]));
    for (name, value, words) in [
        ("misspelt.json", serde_json::json!({ SUBJECT: with(&|d| d["nulable"] = serde_json::json!(["this"])) }), "unknown field `nulable`"),
        ("bounds.json", serde_json::json!({ SUBJECT: with(&|d| d["bounds"]["after"]["setup_calls"] = serde_json::json!(2)) }), "unknown field `setup_calls`"),
        ("made-by.json", serde_json::json!({ SUBJECT: with(&|d| d["made_by"] = serde_json::json!({"kind": "field-by-field", "fields": ["used"]})) }), "unknown field `fields`"),
        ("subject.json", serde_json::json!({ "throttle.Throttle": base.clone() }), "throttle.Throttle is not a method"),
        ("plan.json", serde_json::json!({ SUBJECT: with(&|d| d["made_by"]["after"]["roots"][0]["name"] = serde_json::json!("self")) }), "a setup sequence and no receiver"),
    ] {
        let refused = compare::load_domains(&file(name, value)).expect_err(name).what;
        assert!(refused.contains("--domains") && refused.contains(words), "{name}: {refused}");
    }

    // The command line reads the file, and its exit status is the report's.
    let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).arg("compare").arg(&before).arg(&after).arg("--domains").arg(&good).arg("--json").output().expect("the command runs");
    assert_eq!(out.status.code(), Some(1), "{}", String::from_utf8_lossy(&out.stderr));
    let report: serde_json::Value = serde_json::from_slice(&out.stdout).unwrap();
    assert_eq!(report["kernel"][0]["outcome"]["verdict"], "refuted", "{report}");
    assert_eq!(report["effort"]["decisions"]["domain restriction"], 1, "{report}");
    let bad = file("bad.json", serde_json::json!({ "throttle.Throttle#take": base }));
    let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).arg("compare").arg(&before).arg(&after).arg("--domains").arg(&bad).output().expect("the command runs");
    assert!(!out.status.success() && String::from_utf8_lossy(&out.stderr).contains("throttle.Throttle#take"), "{}", String::from_utf8_lossy(&out.stderr));
}
