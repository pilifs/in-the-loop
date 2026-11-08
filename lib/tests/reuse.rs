//! The reuse stream's tests (`llm-dlc/loops/application-core-reuse.md`). R1, the native property cache: a verified
//! and a refuted property reused exactly, a refutation reused only once its witness fails the harness again, and
//! the claim key changed by every part of the claim that can change a verdict (the assertion, the domain, the bounds,
//! the code its inputs are made by, a construction plan's history), never by an unrelated change, and never shared
//! with a regression claim of the same target. Over the frozen quote fixture (`tests/fixtures/application-core/`)
//! and small builds compiled here, on the own checker, with no JBMC.

use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::spec::cache::ClaimKey;
use jvmcontract::{property, reuse, Engine, Verdict};
use serde_json::Value;

const NO_JBMC: &str = "/nonexistent/jbmc";

fn tmp(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("reuse").join(name)
}

/// Compiles the Java `sources` (each a directory of a source tree, later ones replacing the files of earlier ones)
/// into `target/tmp/reuse/NAME`. The tests need `javac`: without it they fail rather than pass by skipping.
fn compile(name: &str, sources: &[&Path]) -> PathBuf {
    let mut files = std::collections::BTreeMap::new();
    for dir in sources {
        for f in java_files(dir) {
            files.insert(f.strip_prefix(dir).unwrap().to_path_buf(), f.clone());
        }
    }
    let out = tmp(name).join("classes");
    let _ = std::fs::remove_dir_all(&out);
    let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out).args(files.values()).status().expect("the tests need javac");
    assert!(status.success(), "{name} compiles");
    out
}

/// Compiles the sources given as (path, text) into `target/tmp/reuse/NAME`.
fn compile_text(name: &str, files: &[(&str, &str)]) -> PathBuf {
    let src = tmp(name).join("src");
    let _ = std::fs::remove_dir_all(&src);
    for (path, text) in files {
        let p = src.join(path);
        std::fs::create_dir_all(p.parent().unwrap()).unwrap();
        std::fs::write(p, text).unwrap();
    }
    compile(name, &[&src])
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

fn quote(build: &str) -> PathBuf {
    let family = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/application-core/quote");
    let after = family.join("after");
    match build {
        "before" => compile("quote-before", &[&family.join("before")]),
        "after" => compile("quote-after", &[&after]),
        defect => compile(&format!("quote-{defect}"), &[&after, &family.join("defects").join(defect)]),
    }
}

/// A property check of `target` in `classes` under the cache `cache`, on the own checker.
fn options(classes: &Path, target: &str, assert: &str, cache: &Path, run: &str) -> property::Options {
    let mut o = property::Options::new(&[classes.to_path_buf()], target);
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.assert = Some(assert.into());
    o.cache = Some(cache.to_path_buf());
    o.work = Some(tmp(run));
    o.timeout_seconds = 300;
    o
}

fn fresh(name: &str) -> PathBuf {
    let dir = tmp(name);
    let _ = std::fs::remove_dir_all(&dir);
    dir
}

fn key(o: &property::Options) -> ClaimKey {
    reuse::property_key(o).unwrap().expect("the property has a claim")
}

/// The entry file of `key` in the cache `dir`.
fn entry(dir: &Path, key: &ClaimKey) -> PathBuf {
    let hex = key.0.strip_prefix("sha256:").unwrap();
    dir.join("claims").join(&hex[..2]).join(format!("{hex}.json"))
}

fn entries(dir: &Path) -> usize {
    let Ok(groups) = std::fs::read_dir(dir.join("claims")) else { return 0 };
    groups.map(|g| std::fs::read_dir(g.unwrap().path()).unwrap().count()).sum()
}

const REUSED: &str = "reused from the proof cache";

#[test]
fn a_verified_property_is_stored_then_reused_exactly_with_its_statement() {
    let classes = quote("after");
    let cache = fresh("verified-cache");
    let o = options(&classes, "quotes.QuoteService#units", "quantities.length > 0 || result == 0", &cache, "verified-cold");
    let cold = property::run(&o).unwrap();
    assert_eq!(cold.verdict, Verdict::Verified, "{}", cold.output);
    assert!(!cold.output.contains(REUSED), "{}", cold.output);
    assert!(entry(&cache, &key(&o)).exists(), "the verified result is stored under its key");

    let mut again = o.clone();
    again.work = Some(tmp("verified-rerun"));
    let hit = property::run(&again).unwrap();
    assert_eq!(hit.verdict, Verdict::Verified);
    assert!(hit.output.contains(REUSED) && hit.output.contains(&key(&o).0), "{}", hit.output);
    assert!(hit.proof.as_deref().is_some_and(|p| p.starts_with(REUSED)), "{:?}", hit.proof);
    assert!(hit.search.is_none(), "no checker ran");
    // The assurance stated is the proof's own: its domain, bounds, assumptions and evidence.
    assert_eq!(serde_json::to_value(&hit.stated).unwrap(), serde_json::to_value(&cold.stated).unwrap());
    assert_eq!(hit.domain, cold.domain);
    assert!(hit.statement.as_ref().is_some_and(|s| s.exists()), "the harness's source is there to read");
}

#[test]
fn a_refuted_property_is_reused_only_once_its_witness_fails_the_harness_again() {
    let classes = quote("after");
    let cache = fresh("refuted-cache");
    let o = options(&classes, "quotes.QuoteService#units", "result >= 0", &cache, "refuted-cold");
    let cold = property::run(&o).unwrap();
    assert_eq!(cold.verdict, Verdict::Violation, "{}", cold.output);
    let file = entry(&cache, &key(&o));
    assert!(file.exists(), "the refutation is stored: its witness fails the harness");

    let mut again = o.clone();
    again.work = Some(tmp("refuted-rerun"));
    let hit = property::run(&again).unwrap();
    assert_eq!(hit.verdict, Verdict::Violation);
    assert!(hit.output.contains(REUSED) && hit.output.contains("failed the stored harness again"), "{}", hit.output);
    let replay = hit.replay.as_ref().unwrap();
    assert!(replay.reproduced && replay.by == "interpreter");
    assert_eq!(hit.counterexample.as_ref().unwrap().input, cold.counterexample.as_ref().unwrap().input);

    // A stored witness that no longer fails (here, the empty array, on which the property holds) is not the result:
    // the check proves again, and stores its own refutation in its place.
    let mut record: Value = serde_json::from_str(&std::fs::read_to_string(&file).unwrap()).unwrap();
    record["outcome"]["witness"] = Value::String(r#"[{"name":"quantities","type":"int[]","value":[]}]"#.into());
    std::fs::write(&file, record.to_string()).unwrap();
    let mut tampered = o.clone();
    tampered.work = Some(tmp("refuted-tampered"));
    let proved = property::run(&tampered).unwrap();
    assert_eq!(proved.verdict, Verdict::Violation, "{}", proved.output);
    assert!(!proved.output.contains(REUSED), "{}", proved.output);
    let restored: Value = serde_json::from_str(&std::fs::read_to_string(&file).unwrap()).unwrap();
    assert_ne!(restored["outcome"]["witness"], record["outcome"]["witness"], "the check's own witness replaces the one that no longer fails");
}

#[test]
fn an_unresolved_result_is_never_stored() {
    let classes = quote("after");
    let cache = fresh("unresolved-cache");
    let refused = property::run(&options(&classes, "quotes.QuoteService#units", "result >", &cache, "unresolved")).unwrap();
    assert_eq!(refused.verdict, Verdict::Unverifiable, "{}", refused.output);
    assert_eq!(entries(&cache), 0);
}

#[test]
fn every_part_of_a_property_claim_that_can_change_its_verdict_changes_its_key() {
    let classes = quote("after");
    let cache = tmp("keys-cache");
    let base = options(&classes, "quotes.QuoteService#units", "result >= 0", &cache, "keys");
    let k = key(&base);
    let mut changes: Vec<(&str, property::Options)> = Vec::new();
    let mut change = |what: &'static str, f: &dyn Fn(&mut property::Options)| {
        let mut o = base.clone();
        f(&mut o);
        changes.push((what, o));
    };
    change("the assertion", &|o| o.assert = Some("result >= -1".into()));
    change("an assumption", &|o| o.assume = Some("quantities.length < 3".into()));
    change("a throws clause", &|o| o.throws = vec!["ArithmeticException when quantities.length == 9".into()]);
    change("a null array", &|o| o.nullable = vec!["quantities".into()]);
    change("the array bound", &|o| o.max_array_length = 4);
    change("the unwinding bound", &|o| o.unwind = 9);
    change("the models", &|o| o.models = false);
    change("the gap mode", &|o| o.gaps = jvmcontract::bmc::gaps::GapMode::Advised);
    change("shrinking", &|o| o.shrink = false);
    change("the target", &|o| o.target = "quotes.Codes#vip".into());
    let mut seen = vec![("the base", k.clone())];
    for (what, o) in &changes {
        let other = key(o);
        assert!(!seen.iter().any(|(_, s)| *s == other), "{what}: the key of another claim");
        seen.push((what, other));
    }
    // What decides no verdict leaves the key alone: where the check works, its deadline, the store itself.
    let mut same = base.clone();
    same.work = Some(tmp("elsewhere"));
    same.timeout_seconds = 5;
    same.cache = Some(tmp("another-cache"));
    assert_eq!(key(&same), k);

    // The code: a rewrite of the target changes it; a change of a method it never reaches does not.
    assert_ne!(key(&options(&quote("before"), "quotes.QuoteService#units", "result >= 0", &cache, "keys")), k);
    assert_eq!(key(&options(&quote("wrong-prefix"), "quotes.QuoteService#units", "result >= 0", &cache, "keys")), k);
}

#[test]
fn a_construction_plans_history_is_part_of_the_claim() {
    let golden = |name: &str| -> jvmcontract::construction::Plans {
        let claim: Value = serde_json::from_str(&std::fs::read_to_string(Path::new(env!("CARGO_MANIFEST_DIR")).join(format!("tests/fixtures/application-core/golden/{name}.json"))).unwrap()).unwrap();
        serde_json::from_value(serde_json::json!({ "before": claim["domain"]["made_by"]["before"], "after": claim["domain"]["made_by"]["after"] })).unwrap()
    };
    let classes = quote("after");
    let cache = tmp("plans-cache");
    let mut constructed = options(&classes, "quotes.QuoteService#units", "result >= 0", &cache, "plans");
    constructed.plan = Some(golden("throttle-constructed-claim"));
    let mut setup = constructed.clone();
    setup.plan = Some(golden("throttle-setup-claim"));
    let plain = options(&classes, "quotes.QuoteService#units", "result >= 0", &cache, "plans");
    let keys = [key(&plain), key(&constructed), key(&setup)];
    assert!(keys[0] != keys[1] && keys[1] != keys[2] && keys[0] != keys[2], "constructor-only and setup-sequence claims are different claims: {keys:?}");
}

/// The code a claim covers is what its inputs are made by, not only the class of the method: a parameter's
/// constructor that changes what it admits invalidates the stored proof, though the method's body is the same.
#[test]
fn a_changed_constructor_of_an_input_invalidates_the_stored_proof() {
    let clamped = compile_text("box-clamped", &[("k/Box.java", "package k; public class Box { final int v; public Box(int v) { this.v = v < 0 ? 0 : v; } }"), ("k/Use.java", "package k; public class Use { static int get(Box b) { return b.v; } }")]);
    let open = compile_text("box-open", &[("k/Box.java", "package k; public class Box { final int v; public Box(int v) { this.v = v; } }"), ("k/Use.java", "package k; public class Use { static int get(Box b) { return b.v; } }")]);
    let cache = fresh("box-cache");
    let first = property::run(&options(&clamped, "k.Use#get", "result >= 0", &cache, "box-clamped")).unwrap();
    assert_eq!(first.verdict, Verdict::Verified, "{}", first.output);
    let second = property::run(&options(&open, "k.Use#get", "result >= 0", &cache, "box-open")).unwrap();
    assert_eq!(second.verdict, Verdict::Violation, "{}", second.output);
    assert!(!second.output.contains(REUSED), "{}", second.output);
}

/// A property proof can't reuse a regression result because the target matches, nor the other way round: the two
/// claims of one target, in one cache, are two keys.
#[test]
fn property_and_regression_claims_of_one_target_never_share_a_key() {
    let (before, after) = (quote("before"), quote("after"));
    let cache = fresh("kinds-cache");
    let mut regression = jvmcontract::equivalence::Options::new(&before, &after, "quotes.QuoteService#units");
    regression.engine = Engine::Native;
    regression.jbmc = NO_JBMC.into();
    regression.cache = Some(cache.clone());
    regression.work = Some(tmp("kinds-regression"));
    let mark = jvmcontract::proof_cache::key_mark();
    let proved = jvmcontract::equivalence::run(&regression).unwrap();
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);
    let regression_key = jvmcontract::proof_cache::key_since("quotes.QuoteService#units", mark).expect("the regression claim is keyed");

    let o = options(&after, "quotes.QuoteService#units", "quantities.length > 0 || result == 0", &cache, "kinds-property");
    assert_ne!(key(&o), regression_key);
    let claim = reuse::property_claim(&o).unwrap().unwrap();
    assert_eq!(claim.assumptions[0], reuse::PROPERTY_CLAIM);
    let property = property::run(&o).unwrap();
    assert!(!property.output.contains(REUSED), "{}", property.output);
    assert_eq!(entries(&cache), 2);
}
