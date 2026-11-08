//! The reuse stream's tests (`llm-dlc/loops/application-core-reuse.md`). R1, the native property cache: a verified
//! and a refuted property reused exactly, a refutation reused only once its witness fails the harness again, and
//! the claim key changed by every part of the claim that can change a verdict (the assertion, the domain, the bounds,
//! the code its inputs are made by, a construction plan's history), never by an unrelated change, and never shared
//! with a regression claim of the same target. Over the frozen quote fixture (`tests/fixtures/application-core/`)
//! and small builds compiled here, on the own checker, with no JBMC. J3, the key over the streams' new claim parts:
//! every frozen claim has a key of its own, every change to a planned domain's history, a modelled call's outcomes
//! or a value bound gives another, and a field those typed parts don't declare makes the claim uncacheable.

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
/// into `target/tmp/reuse/NAME`, once per run of the tests: a NAME is one build, and tests running side by side
/// would otherwise remove each other's classes while they are read. The tests need `javac`: without it they fail
/// rather than pass by skipping.
fn compile(name: &str, sources: &[&Path]) -> PathBuf {
    static BUILT: std::sync::Mutex<Vec<String>> = std::sync::Mutex::new(Vec::new());
    let mut built = BUILT.lock().unwrap_or_else(|e| e.into_inner());
    let out = tmp(name).join("classes");
    if built.iter().any(|b| b == name) {
        return out;
    }
    let mut files = std::collections::BTreeMap::new();
    for dir in sources {
        for f in java_files(dir) {
            files.insert(f.strip_prefix(dir).unwrap().to_path_buf(), f.clone());
        }
    }
    let _ = std::fs::remove_dir_all(&out);
    let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out).args(files.values()).status().expect("the tests need javac");
    assert!(status.success(), "{name} compiles");
    built.push(name.to_string());
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

// J3: the claim key over the streams' new claim parts, a planned domain's plans and a modelled call's model, which
// `spec::cache::TYPED` digests whole as their strict types.

fn golden_claim(name: &str) -> Value {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/application-core/golden").join(format!("{name}.json"));
    serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap()
}

/// The key of a claim given as JSON, read as a `CanonicalClaim` first, so that every changed claim is one the types
/// admit.
fn claim_key(v: &Value) -> ClaimKey {
    let claim: jvmcontract::spec::CanonicalClaim = serde_json::from_value(v.clone()).unwrap_or_else(|e| panic!("a claim: {e}"));
    jvmcontract::spec::cache::key(&claim).unwrap_or_else(|u| panic!("a key: {u}"))
}

#[test]
fn every_frozen_claim_has_a_key_of_its_own() {
    let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/application-core/golden");
    let mut keys = std::collections::HashMap::new();
    for entry in std::fs::read_dir(&dir).unwrap() {
        let name = entry.unwrap().file_name().into_string().unwrap();
        if let Some(name) = name.strip_suffix("-claim.json") {
            let key = claim_key(&golden_claim(&format!("{name}-claim")));
            assert!(keys.insert(key, name.to_string()).is_none(), "{name} shares a key");
        }
    }
    assert_eq!(keys.len(), 8, "{keys:?}");
}

#[test]
fn every_semantic_part_of_a_plan_or_a_model_changes_the_key() {
    type Change = (&'static str, &'static str, fn(&mut Value));
    let changes: &[Change] = &[
        // Histories: the setup sequence, the constructor, the plan's bounds, and either version's plan alone.
        ("throttle-setup-claim", "no setup call", |v| {
            v["domain"]["made_by"]["after"].as_object_mut().unwrap().remove("setup");
            v["domain"]["made_by"]["before"].as_object_mut().unwrap().remove("setup");
        }),
        ("throttle-setup-claim", "a second setup call", |v| {
            for side in ["before", "after"] {
                let plan = &mut v["domain"]["made_by"][side];
                let call = plan["setup"][0].clone();
                plan["setup"].as_array_mut().unwrap().push(call);
                plan["bounds"]["setup_calls"] = 2.into();
            }
        }),
        ("throttle-setup-claim", "another setup method", |v| v["domain"]["made_by"]["after"]["setup"][0]["method"] = "take(J)V".into()),
        ("throttle-setup-claim", "a setup argument's type", |v| v["domain"]["made_by"]["before"]["setup"][0]["args"][0]["type"] = "long".into()),
        ("throttle-setup-claim", "the setup bound alone", |v| v["domain"]["made_by"]["after"]["bounds"]["setup_calls"] = 3.into()),
        ("throttle-setup-claim", "another constructor", |v| v["domain"]["made_by"]["after"]["nodes"][0]["maker"]["descriptor"] = "(J)V".into()),
        ("throttle-setup-claim", "a factory for a constructor", |v| {
            v["domain"]["made_by"]["after"]["nodes"][0]["maker"] = serde_json::json!({"kind": "factory", "method": "throttle/Throttle#of(I)Lthrottle/Throttle;"})
        }),
        ("throttle-setup-claim", "a restriction stated", |v| v["domain"]["made_by"]["before"]["restrictions"][0] = "the states two calls reach".into()),
        // Model outcomes: one fewer, another exception, another coupling, key, bound or occurrence policy.
        ("quote-claim", "a modelled outcome fewer", |v| {
            let call = &mut v["environment"]["calls"][0];
            call["model"]["results"].as_array_mut().unwrap().pop();
            call["outcomes"].as_array_mut().unwrap().pop();
        }),
        ("quote-claim", "another modelled exception", |v| v["environment"]["calls"][0]["model"]["results"][1]["class"] = "java.lang.IllegalStateException".into()),
        ("quote-claim", "a choice for a query", |v| {
            v["environment"]["calls"][0]["model"]["coupling"] = serde_json::json!({"kind": "choice", "policy": {"kind": "per-call"}})
        }),
        ("quote-claim", "a script for a choice per call", |v| {
            v["environment"]["calls"][0]["model"]["coupling"] = serde_json::json!({"kind": "choice", "policy": {"kind": "script", "results": [0, 1]}})
        }),
        ("quote-claim", "a query keyed on nothing", |v| v["environment"]["calls"][0]["model"]["key"] = serde_json::json!([])),
        ("quote-claim", "a larger call bound", |v| v["environment"]["calls"][0]["model"]["bound"] = 2.into()),
        ("quote-claim", "another modelled operation", |v| v["environment"]["calls"][0]["model"]["id"] = "rates.other".into()),
        ("quote-claim", "a model on the event call", |v| {
            v["environment"]["calls"][1]["model"] = serde_json::json!({"id": "events.send", "key": [], "coupling": {"kind": "query"}, "results": [{"kind": "returns", "value": {"kind": "void"}}], "bound": 1})
        }),
        // Value bounds and models: a String's length, nullability and evidence, an array's length.
        ("quote-claim", "a shorter String", |v| v["domain"]["made_by"]["after"]["nodes"][1]["args"][0]["domain"]["max_length"] = 3.into()),
        ("quote-claim", "a nullable String", |v| v["domain"]["made_by"]["before"]["nodes"][1]["args"][0]["domain"]["nullable"] = true.into()),
        ("quote-claim", "a shorter array", |v| v["domain"]["made_by"]["after"]["nodes"][1]["args"][1]["max_length"] = 1.into()),
        ("quote-claim", "another dependency class", |v| v["domain"]["made_by"]["after"]["nodes"][0]["args"][2]["class"] = "quotes.CachedRates".into()),
        ("basket-total-claim", "a shorter list", |v| {
            for side in ["before", "after"] {
                v["domain"]["made_by"][side]["roots"][0]["value"]["domain"]["max_length"] = 2.into();
            }
        }),
        // A returned object's identity and nullability, and the plan it is made by.
        ("offer-claim", "a stable returned object", |v| v["environment"]["calls"][0]["model"]["results"][0]["value"]["identity"] = "stable".into()),
        ("offer-claim", "a returned object never null", |v| v["environment"]["calls"][0]["model"]["results"][0]["value"]["nullable"] = false.into()),
        ("offer-claim", "a returned object's field type", |v| {
            v["environment"]["calls"][0]["model"]["results"][0]["value"]["plan"]["nodes"][0]["args"][1]["type"] = "long".into()
        }),
    ];
    let mut seen = std::collections::HashMap::new();
    for name in ["throttle-setup-claim", "quote-claim", "basket-total-claim", "offer-claim"] {
        seen.insert(claim_key(&golden_claim(name)), format!("{name} as frozen"));
    }
    for (name, what, change) in changes {
        let mut changed = golden_claim(name);
        change(&mut changed);
        let key = claim_key(&changed);
        if let Some(other) = seen.insert(key, format!("{name}: {what}")) {
            panic!("{name}: {what} has the key of {other}");
        }
    }
    // The constructor-only claim and the claim after a setup call are two claims (row J3's history).
    assert_ne!(claim_key(&golden_claim("throttle-constructed-claim")), claim_key(&golden_claim("throttle-setup-claim")));
    // A value domain's evidence is the model's, not the claim's words: the key resolves it under this tool's model
    // first (`values::resolve_claim`), which replaces a stated level no stronger than the model's, and what the claim
    // says the model leaves out, by the model's own record. So these are the claim as frozen, checked and keyed alike;
    // a change of the model itself changes the key (`tests/values.rs`), and a stronger level is never keyed.
    let same: &[Change] = &[
        ("quote-claim", "a String model of the model's own level", |v| v["domain"]["made_by"]["after"]["nodes"][1]["args"][0]["domain"]["model"]["level"] = "tested".into()),
        ("basket-total-claim", "a list model that says it leaves out nothing", |v| {
            v["domain"]["made_by"]["after"]["roots"][0]["value"]["domain"]["model"].as_object_mut().unwrap().remove("leaves_out");
        }),
    ];
    for (name, what, change) in same {
        let mut changed = golden_claim(name);
        change(&mut changed);
        assert_eq!(seen.get(&claim_key(&changed)), Some(&format!("{name} as frozen")), "{name}: {what}");
    }
    // Never keyed: a domain the values models don't resolve.
    let refused: &[(Change, &str)] = &[
        (("quote-claim", "a String model stated as proved", |v| v["domain"]["made_by"]["after"]["nodes"][1]["args"][0]["domain"]["model"]["level"] = "proved".into()), "never borrows a stronger level"),
        (("basket-total-claim", "a list of Strings", |v| v["domain"]["made_by"]["after"]["roots"][0]["value"]["domain"]["kind"]["element"] = serde_json::json!({"kind": "string"})), "a list of Strings"),
    ];
    for ((name, what, change), why) in refused {
        let mut changed = golden_claim(name);
        change(&mut changed);
        let claim: jvmcontract::spec::CanonicalClaim = serde_json::from_value(changed).unwrap();
        let u = jvmcontract::spec::cache::key(&claim).expect_err(what);
        assert!(u.what.contains("uncacheable") && u.what.contains(why), "{name}: {what}: {u}");
    }
}

#[test]
fn a_field_a_plan_or_a_model_does_not_declare_makes_the_claim_uncacheable() {
    use jvmcontract::spec::{cache, Part};
    let refused = |v: &Value, path: &str| {
        let u = cache::projection(v).expect_err(path);
        assert_eq!(u.part, Part::Summaries, "{u}");
        assert!(u.what.contains("uncacheable") && u.what.contains(path), "{}", u.what);
        u.what
    };
    let quote = golden_claim("quote-claim");
    assert!(cache::projection(&quote).is_ok());
    let mut node = quote.clone();
    node["domain"]["made_by"]["after"]["nodes"][0]["ownership"] = "unique".into();
    assert!(refused(&node, "domain.made_by.after").contains("ownership"));
    let mut model = quote.clone();
    model["environment"]["calls"][0]["model"]["cache_hint"] = "warm".into();
    assert!(refused(&model, "environment.calls[].model").contains("cache_hint"));
    let mut variant = quote.clone();
    variant["environment"]["calls"][0]["model"]["coupling"] = serde_json::json!({"kind": "sometimes"});
    refused(&variant, "environment.calls[].model");
    // A plan that reads as its type but not back as written: an empty setup sequence spelled out.
    let mut spelled = golden_claim("throttle-constructed-claim");
    spelled["domain"]["made_by"]["before"]["setup"] = serde_json::json!([]);
    assert!(refused(&spelled, "domain.made_by.before").contains("does not read back"));
}

// The regression cache's own hole, found by the objects stream: a regression claim's code is the closure of every
// constructor the harness calls, both versions', not only a made object's own.

/// `get(new Wrap(new Inner(v), k))` in a build whose `Inner` constructor stores `inner` and whose `get` is `body`.
fn wrapped(name: &str, inner: &str, body: &str) -> PathBuf {
    let inner = format!("package boxes; public class Inner {{ final int v; public Inner(int v) {{ this.v = {inner}; }} }}");
    let wrap = "package boxes; public class Wrap { final Inner in; final int k; public Wrap(Inner in, int k) { this.in = in; this.k = k; } }";
    let get = format!("package boxes; public class Box {{ public static int get(Wrap w) {{ return {body}; }} }}");
    compile_text(name, &[("boxes/Inner.java", &inner), ("boxes/Wrap.java", wrap), ("boxes/Box.java", &get)])
}

fn regression(before: &Path, after: &Path, cache: &Path, run: &str) -> jvmcontract::equivalence::Outcome {
    let mut o = jvmcontract::equivalence::Options::new(before, after, "boxes.Box#get");
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.cache = Some(cache.to_path_buf());
    o.work = Some(fresh(run));
    jvmcontract::equivalence::run(&o).unwrap()
}

/// A build that changes only the constructor of an object another one is made from is another claim, in the version
/// after and in the version before: neither reuses the rewrite's proof, and each is refuted. Before the fix the
/// closure was rooted at `Wrap`'s constructor alone, so both reused `verified`.
#[test]
fn an_inner_objects_constructor_in_either_version_is_part_of_a_regression_claim() {
    let before = wrapped("inner-before", "v", "w.in.v + w.k");
    let same = wrapped("inner-same", "v", "w.k + w.in.v");
    let cache = fresh("inner-cache");
    let proved = regression(&before, &same, &cache, "inner-run-same");
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);
    let again = regression(&before, &same, &cache, "inner-run-again");
    assert!(again.reuse.is_some(), "an unchanged rerun is an exact hit: {}", again.output);

    let after_changed = wrapped("inner-after-changed", "v + 1", "w.k + w.in.v");
    let o = regression(&before, &after_changed, &cache, "inner-run-after");
    assert!(o.reuse.is_none(), "another inner constructor after is another claim: {}", o.output);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);

    let before_changed = wrapped("inner-before-changed", "v + 1", "w.in.v + w.k");
    let o = regression(&before_changed, &same, &cache, "inner-run-before");
    assert!(o.reuse.is_none(), "another inner constructor before is another claim: {}", o.output);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
}

/// A counter whose `add` is the setup call of a construction plan (`prove --plan`), for the planned property cache.
const COUNTER: &str = r#"package counters;

public class Counter {
    private final int step;
    private int count;

    public Counter(int step) {
        if (step < 1) {
            throw new IllegalArgumentException("step below 1");
        }
        this.step = step;
    }

    public void add(int n) {
        if (n < 0 || n > 4) {
            throw new IllegalArgumentException("n out of range");
        }
        count += n * step;
    }

    public int count() {
        return count;
    }
}
"#;

/// The plan of `this`, a `Counter(int step)`, followed by `add(setup.0.n)` when `setup` is true.
fn counter_plan(setup: bool) -> jvmcontract::construction::Plans {
    let calls = if setup { r#"{"method": "add(I)V", "args": [{"kind": "leaf", "path": "setup.0.n", "type": "int"}]}"# } else { "" };
    let plan = format!(
        r#"{{"nodes": [{{"id": 0, "class": "counters.Counter", "maker": {{"kind": "constructor", "descriptor": "(I)V"}}, "args": [{{"kind": "leaf", "path": "this.step", "type": "int"}}]}}],
        "roots": [{{"name": "this", "value": {{"kind": "node", "id": 0}}}}], "setup": [{calls}],
        "bounds": {{"nodes": 1, "max_array_length": 0, "setup_calls": {}}}}}"#,
        u8::from(setup)
    );
    jvmcontract::construction::Plans { before: serde_json::from_str(&plan).unwrap(), after: serde_json::from_str(&plan).unwrap() }
}

/// `prove --cache --plan`: a property of the states a setup call reaches is stored, and its exact rerun is reused,
/// marked so in the outcome (`reuse`); an edit of the setup method alone is another claim, proved again and refuted
/// with the whole history, whose rerun reuses the refutation with that history; and a plan without the setup call is
/// another claim too. A result that can't be stored says so in the outcome's output.
#[test]
fn a_planned_property_is_cached_and_an_edit_of_its_setup_method_alone_is_proved_again() {
    let classes = compile_text("planned-counter", &[("counters/Counter.java", COUNTER)]);
    let edited = compile_text("planned-counter-edited", &[("counters/Counter.java", &COUNTER.replace("count += n * step;", "count += n == 4 ? n * step + 1 : n * step;"))]);
    let cache = fresh("planned-cache");
    let run = |classes: &Path, setup: bool, cache: &Path, name: &str| {
        let mut o = options(classes, "counters.Counter#count", "result <= 4 * this.step && result >= 0", cache, name);
        o.assume = Some("this.step < 1000".into());
        o.plan = Some(counter_plan(setup));
        property::run(&o).unwrap_or_else(|e| panic!("{name}: {e}"))
    };
    let exact = |o: &property::Outcome| matches!(&o.reuse, Some(jvmcontract::spec::cache::Reuse::Exact { .. }));

    let cold = run(&classes, true, &cache, "planned-cold");
    assert_eq!(cold.verdict, Verdict::Verified, "{}", cold.output);
    assert!(cold.reuse.is_none() && !cold.output.contains(REUSED), "{}", cold.output);
    assert_eq!(entries(&cache), 1, "the verified result is stored");
    let rerun = run(&classes, true, &cache, "planned-rerun");
    assert_eq!(rerun.verdict, Verdict::Verified, "{}", rerun.output);
    assert!(exact(&rerun) && rerun.output.contains(REUSED) && rerun.search.is_none(), "the exact rerun is reused: {}", rerun.output);
    assert_eq!(serde_json::to_value(&rerun.stated).unwrap(), serde_json::to_value(&cold.stated).unwrap());

    // The setup method's edit alone: `add(4)` counts one more, so a history reaches a state the property excludes.
    let refuted = run(&edited, true, &cache, "planned-edited");
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    assert!(refuted.reuse.is_none() && !refuted.output.contains(REUSED), "another setup method is another claim: {}", refuted.output);
    let c = refuted.counterexample.as_ref().unwrap();
    assert!(c.input.contains("after the setup this.add(setup.0.n=4)"), "the whole history: {}", c.input);
    assert_eq!(entries(&cache), 2, "the refutation is stored: its witness fails the harness");
    let again = run(&edited, true, &cache, "planned-edited-again");
    assert_eq!(again.verdict, Verdict::Violation, "{}", again.output);
    assert!(exact(&again) && again.output.contains("failed the stored harness again"), "{}", again.output);
    let history = |o: &property::Outcome| serde_json::to_value(&o.counterexample.as_ref().unwrap().call.setup).unwrap();
    assert_eq!(history(&again), history(&refuted), "the reused refutation keeps its history");
    assert_eq!(history(&again)[0]["arguments"][0]["value"], 4);

    // The constructor-only plan is another claim: proved, not reused.
    let constructed = run(&edited, false, &cache, "planned-constructed");
    assert_eq!(constructed.verdict, Verdict::Verified, "count is 0 right after construction: {}", constructed.output);
    assert!(constructed.reuse.is_none(), "{}", constructed.output);
    assert_eq!(entries(&cache), 3);

    // A cache that can't store says so in the result's own output, not on the standard error.
    let blocked = tmp("planned-blocked-cache");
    let _ = std::fs::remove_dir_all(&blocked);
    let _ = std::fs::remove_file(&blocked);
    std::fs::create_dir_all(blocked.parent().unwrap()).unwrap();
    std::fs::write(&blocked, "not a directory").unwrap();
    let unstored = run(&classes, false, &blocked, "planned-unstored");
    assert_eq!(unstored.verdict, Verdict::Verified, "a failure to store never changes the verdict: {}", unstored.output);
    assert!(unstored.output.contains("note: the property result is not stored in the proof cache"), "{}", unstored.output);
}
