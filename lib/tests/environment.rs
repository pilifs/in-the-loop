//! The environment stream's E1 (`llm-dlc/loops/application-core-environment.md`): an entry point that consumes a
//! primitive a dependency returns, checked by the effect check (`lib/src/effects.rs`) under a declared environment
//! model of that dependency (`lib/src/environment.rs`, `spec::plans::CallModel`). The model is a deterministic
//! read-only query: both builds see one function of the key, so a correct rewrite proves, a wrong key or an ignored
//! result is refuted with the environment that shows it, replayed on a JVM under the generated stubs, and calls are
//! never coupled by their position.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::{Mutex, OnceLock};

use jvmcontract::effects::{self, Checked};
use jvmcontract::spec::observe::{self, EntryPointSpec};
use jvmcontract::spec::plans::{CallModel, Coupling, ModelledResult, Returned};
use jvmcontract::spec::{CanonicalClaim, ClaimBounds, ModeledCall, ObservationState, Verdict};

const RATE: &str = "rates/Rates#rate(I)J";
const SEND: &str = "effect:org/springframework/kafka/core/KafkaTemplate#send(Ljava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;";

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

/// The controller of every build: a rate the application's `Rates` returns for the request's code, and an event
/// sent through Kafka; `body` is the handler's.
fn controller(body: &str) -> String {
    format!(
        r#"package rates;

import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class PriceController {{
    private final Rates rates;
    private final KafkaTemplate<String, PriceEvent> kafka;

    public PriceController(Rates rates, KafkaTemplate<String, PriceEvent> kafka) {{
        this.rates = rates;
        this.kafka = kafka;
    }}

    @PostMapping("/price")
    public long price(@RequestParam int code, @RequestParam int quantity) {{
{body}
    }}
}}
"#
    )
}

const RATES: &str = "package rates;\n\n/** A read-only rate table: the dependency the environment models. */\npublic interface Rates {\n    long rate(int code);\n}\n";
const EVENT: &str = "package rates;\n\n/** What the prices topic carries. */\npublic record PriceEvent(int code, long total) {}\n";

/// `name`'s build, its handler `body`, compiled once. None without javac and java.
fn build(name: &str, body: &str) -> Option<PathBuf> {
    static SPRING: OnceLock<Option<PathBuf>> = OnceLock::new();
    static BUILDING: Mutex<()> = Mutex::new(());
    let _one_at_a_time = BUILDING.lock().unwrap_or_else(|e| e.into_inner());
    let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("environment");
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
        let src = out.join("sources").join(name).join("rates");
        std::fs::create_dir_all(&src).unwrap();
        std::fs::write(src.join("PriceController.java"), controller(body)).unwrap();
        std::fs::write(src.join("Rates.java"), RATES).unwrap();
        std::fs::write(src.join("PriceEvent.java"), EVENT).unwrap();
        javac(&dir, Some(spring), &[src.join("PriceController.java"), src.join("Rates.java"), src.join("PriceEvent.java")]);
    }
    Some(dir)
}

const BEFORE: &str = "        long total = rates.rate(code) * quantity;\n        if (total > 0) kafka.send(\"prices\", new PriceEvent(code, total));\n        return total;";

fn spec(dir: &Path) -> EntryPointSpec {
    observe::entry_points(dir).expect("the fixture's classes read").into_iter().find(|s| s.id == "POST /price").expect("POST /price")
}

/// `Rates.rate` as a deterministic read-only query of its code, `bound` calls per trace.
fn query(bound: u32) -> ModeledCall {
    let model = CallModel { id: "rates.rate".into(), key: vec!["arg0".into()], coupling: Coupling::Query, results: vec![ModelledResult::Returns { value: Returned::Primitive { ty: "long".into() } }], bound };
    ModeledCall { call: RATE.into(), outcomes: vec!["returns".into()], model: Some(model) }
}

/// The claim `before`'s spec makes, with `Rates.rate` modelled.
fn claim(before: &Path, model: &ModeledCall) -> CanonicalClaim {
    let s = spec(before);
    effects::with_environment(effects::claim_for(&s, None, ClaimBounds { unwind: 8, max_array_length: 4 }), std::slice::from_ref(model), &s.handler)
}

/// `before` checked against `after` (handler bodies), `Rates.rate` modelled as `model`.
fn check(name: &str, before: &str, after: &str, model: &ModeledCall) -> Option<Checked> {
    let b = build(&format!("{name}-before"), before)?;
    let a = build(name, after)?;
    Some(effects::check(&claim(&b, model), &spec(&b), &spec(&a), &b, &a).unwrap_or_else(|u| panic!("{name}: {u}")))
}

fn state(c: &Checked, id: &str) -> ObservationState {
    c.outcome.accounting.iter().find(|a| a.observation == id).unwrap_or_else(|| panic!("{id} isn't accounted for: {:?}", c.outcome.accounting)).state
}

#[test]
fn a_handler_that_uses_a_modelled_rate_proves_its_rewrite() {
    let after = "        long rate = rates.rate(code);\n        long total = quantity * rate;\n        if (total <= 0) return total;\n        kafka.send(\"prices\", new PriceEvent(code, total));\n        return total;";
    let Some(c) = check("rewrite", BEFORE, after, &query(1)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Verified, "{c:?}");
    assert_eq!(state(&c, "result"), ObservationState::Preserved);
    assert_eq!(state(&c, SEND), ObservationState::Preserved);
    assert!(c.assumptions.iter().any(|a| a.contains("Rates.rate is a generated stub in both builds") && a.contains("never by position") && a.contains("at most 1 calls")), "{:?}", c.assumptions);
    assert!(c.outcome.domain.contains("the environment's answers, one for both builds: Rates.rate (rates.rate): any function of (arg0) to long"), "{}", c.outcome.domain);
}

#[test]
fn a_wrong_query_key_is_refuted_under_the_environment_that_shows_it() {
    let wrong = "        long total = rates.rate(code + 1) * quantity;\n        if (total > 0) kafka.send(\"prices\", new PriceEvent(code, total));\n        return total;";
    let Some(c) = check("wrong-key", BEFORE, wrong, &query(1)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Refuted, "{c:?}");
    assert_eq!(state(&c, "result"), ObservationState::Refuted);
    let witness = c.outcome.witness.as_deref().unwrap();
    assert!(witness.contains("under the environment Rates.rate (rates.rate): (arg0="), "{witness}");
    assert!(witness.contains("Replayed on a JVM") && witness.contains("the modelled calls answering from that environment"), "{witness}");
    let (b, a) = (c.before.as_ref().unwrap(), c.after.as_ref().unwrap());
    assert_ne!(b.result, a.result, "the replay shows the two answers: {witness}");
}

#[test]
fn an_ignored_result_is_refuted() {
    let ignored = "        rates.rate(code);\n        long total = 100L * quantity;\n        if (total > 0) kafka.send(\"prices\", new PriceEvent(code, total));\n        return total;";
    let Some(c) = check("ignored", BEFORE, ignored, &query(1)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Refuted, "{c:?}");
    assert_eq!(state(&c, "result"), ObservationState::Refuted);
}

#[test]
fn an_event_sent_on_the_wrong_branch_of_a_rate_is_refuted_in_the_trace() {
    let branch = "        long total = rates.rate(code) * quantity;\n        if (total >= 0) kafka.send(\"prices\", new PriceEvent(code, total));\n        return total;";
    let Some(c) = check("wrong-branch", BEFORE, branch, &query(1)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Refuted, "{c:?}");
    assert_eq!(state(&c, SEND), ObservationState::Refuted);
}

/// Different keys asked for in the other order get their own answers: not coupled by the call's position.
#[test]
fn keys_asked_for_in_another_order_get_their_own_answers() {
    let before = "        return rates.rate(code) - rates.rate(quantity);";
    let swapped = "        long b = rates.rate(quantity);\n        long a = rates.rate(code);\n        return a - b;";
    let Some(c) = check("swapped", before, swapped, &query(2)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Verified, "{c:?}");
    // And the answers are those of the keys: the difference the other way round is refuted.
    let reversed = "        return rates.rate(quantity) - rates.rate(code);";
    let Some(c) = check("reversed", before, reversed, &query(2)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Refuted, "{c:?}");
}

/// Equal keys get equal answers, in one build and across the two.
#[test]
fn repeated_reads_of_one_key_are_functionally_consistent() {
    let before = "        return rates.rate(code) * 2;";
    let twice = "        return rates.rate(code) + rates.rate(code);";
    let Some(c) = check("twice", before, twice, &query(2)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Verified, "{c:?}");
}

/// One more call than the model's bound leaves the result unresolved, never a proof on a shorter trace.
#[test]
fn a_call_past_the_models_bound_is_unresolved() {
    let before = "        return rates.rate(code) * 2;";
    let twice = "        return rates.rate(code) + rates.rate(code);";
    let Some(c) = check("past-bound", before, twice, &query(1)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Unresolved, "{c:?}");
    let reason = c.reason.as_deref().unwrap_or_default();
    assert!(reason.contains("the new one returns 0 and attempts no modeled call (unresolved: more calls of rates.rate than its bound, 1)"), "{reason}");
}

/// Each build's unresolved mark says only what happened in it: the old build past the model's bound, and nothing
/// else (its tag is no mark of its own).
#[test]
fn the_old_builds_unresolved_mark_says_only_what_happened_in_it() {
    let twice = "        return rates.rate(code) + rates.rate(code);";
    let once = "        return rates.rate(code) * 2;";
    let Some(c) = check("past-bound-old", twice, once, &query(1)) else { return };
    assert_eq!(c.outcome.verdict, Verdict::Unresolved, "{c:?}");
    let old = c.before.as_ref().expect("the old build's trace");
    assert_eq!(old.unresolved, ["more calls of rates.rate than its bound, 1"], "{c:?}");
    assert!(c.after.as_ref().unwrap().unresolved.is_empty(), "{c:?}");
}

/// Without a model, the call the handler uses stays what the analysis can't see: a null dependency is no proof of
/// anything. Declared without one, its used result is refused by name.
#[test]
fn without_a_model_a_used_result_is_never_proved() {
    let Some(b) = build("unmodelled-before", BEFORE) else { return };
    let s = spec(&b);
    let plain = effects::claim_for(&s, None, ClaimBounds { unwind: 8, max_array_length: 4 });
    let c = effects::check(&plain, &s, &s, &b, &b).unwrap();
    assert_eq!(c.outcome.verdict, Verdict::Unresolved, "{c:?}");
    assert!(c.reason.as_deref().unwrap().contains("Rates.rate in PriceController.price(int, int): nothing followed implements it"), "{:?}", c.reason);
    let mut call = query(1);
    call.model = None;
    let declared = effects::with_environment(plain, &[call], &s.handler);
    let c = effects::check(&declared, &s, &s, &b, &b).unwrap();
    assert_eq!(c.outcome.verdict, Verdict::Unresolved, "a call declared without a model answers nothing: {c:?}");
}

/// The model is in the proof's claim key: an unchanged rerun is an exact hit, a stored refutation is replayed on a
/// JVM again, and another bound is a miss under another key.
#[test]
fn the_environment_model_is_in_the_claim_key_of_the_cached_proof() {
    use jvmcontract::spec::cache::Reuse;
    let after = "        long rate = rates.rate(code);\n        long total = quantity * rate;\n        if (total <= 0) return total;\n        kafka.send(\"prices\", new PriceEvent(code, total));\n        return total;";
    let wrong = "        long total = rates.rate(code + 1) * quantity;\n        if (total > 0) kafka.send(\"prices\", new PriceEvent(code, total));\n        return total;";
    let (Some(b), Some(a), Some(w)) = (build("cached-before", BEFORE), build("cached", after), build("cached-wrong", wrong)) else { return };
    let cache = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("environment-cache");
    let _ = std::fs::remove_dir_all(&cache);
    let run = |dir: &Path, model: &ModeledCall| effects::check_with(&claim(&b, model), &spec(&b), &spec(dir), &b, dir, Some(&cache)).unwrap();
    let cold = run(&a, &query(1));
    assert_eq!(cold.outcome.verdict, Verdict::Verified, "{cold:?}");
    let key = cold.key.clone().expect("the proof ran under a claim key");
    let warm = run(&a, &query(1));
    assert!(matches!(&warm.reuse, Some(Reuse::Exact { key: k, .. }) if *k == key), "an unchanged rerun is an exact hit: {warm:?}");
    let wider = run(&a, &query(2));
    assert_eq!(wider.outcome.verdict, Verdict::Verified, "{wider:?}");
    assert!(wider.reuse.is_none() && wider.key.as_ref().is_some_and(|k| *k != key), "another bound is another claim: {:?}", wider.key);
    let refuted = run(&w, &query(1));
    assert_eq!(refuted.outcome.verdict, Verdict::Refuted, "{refuted:?}");
    let again = run(&w, &query(1));
    assert!(matches!(again.reuse, Some(Reuse::Exact { .. })), "{again:?}");
    assert_eq!(again.outcome.verdict, Verdict::Refuted);
    assert!(again.outcome.witness.as_deref().is_some_and(|x| x.contains("Replayed on a JVM") && x.contains("under the environment Rates.rate")), "a reused refutation is replayed again: {:?}", again.outcome.witness);
}


/// `effects --environment FILE`: the declared model replaces the spec's call, and the command checks under it.
#[test]
fn the_command_checks_under_a_declared_environment() {
    let wrong = "        long total = rates.rate(code + 1) * quantity;\n        if (total > 0) kafka.send(\"prices\", new PriceEvent(code, total));\n        return total;";
    let (Some(b), Some(w)) = (build("command-before", BEFORE), build("command-wrong", wrong)) else { return };
    let file = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("environment-rates.json");
    std::fs::write(&file, serde_json::to_string(&[query(1)]).unwrap()).unwrap();
    let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).arg("effects").arg(&b).arg(&w).arg("--environment").arg(&file).output().unwrap();
    let text = String::from_utf8_lossy(&out.stdout);
    assert!(text.contains("POST /price: refuted") && text.contains("under the environment Rates.rate (rates.rate)"), "{text}{}", String::from_utf8_lossy(&out.stderr));
    let same = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).arg("effects").arg(&b).arg(&b).arg("--environment").arg(&file).output().unwrap();
    let text = String::from_utf8_lossy(&same.stdout);
    assert!(text.contains("POST /price: verified"), "{text}");
    // Without it, the used rate is what the analysis can't see.
    let plain = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).arg("effects").arg(&b).arg(&w).output().unwrap();
    assert!(String::from_utf8_lossy(&plain.stdout).contains("POST /price: unresolved"), "{}", String::from_utf8_lossy(&plain.stdout));
}
