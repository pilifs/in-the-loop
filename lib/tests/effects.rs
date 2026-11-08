//! The effect trace of an entry point (`lib/src/effects.rs`, behind `observe::effect_log` and `observe::check`) on
//! the joint example of the foundations loop (`lib/tests/fixtures/foundations/`): the refactor proved, the dropped
//! and the duplicated event refuted by witnesses replayed on a JVM under the recording stubs, the bound visible,
//! and what the narrow case doesn't model refused by name.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::{Mutex, OnceLock};

use jvmcontract::effects::{self, Checked};
use jvmcontract::spec::observe::{self, EntryPointSpec};
use jvmcontract::spec::cache::{ClaimKey, Reuse};
use jvmcontract::spec::{CanonicalClaim, Observation, ObservationState, OrderPolicy, Verdict};

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

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/foundations")
}

/// The classes of `before`, `after`, a defect overlaid on `after`, or `after` with its controller replaced by
/// `controller` (Java source written under the name `name`), compiled once each. None without javac and java.
fn build_with(name: &str, controller: Option<&str>) -> Option<PathBuf> {
    static SPRING: OnceLock<Option<PathBuf>> = OnceLock::new();
    static BUILDING: Mutex<()> = Mutex::new(());
    let _one_at_a_time = BUILDING.lock().unwrap_or_else(|e| e.into_inner());
    let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("effects");
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
        let mut files = java_files(&root().join(if name == "before" { "before" } else { "after" }));
        let mut overlay = Vec::new();
        if let Some(source) = controller {
            let src = out.join("sources").join(name).join("shop");
            std::fs::create_dir_all(&src).unwrap();
            std::fs::write(src.join("QuotesController.java"), source).unwrap();
            overlay.push(src.join("QuotesController.java"));
        } else if !matches!(name, "before" | "after") {
            overlay = java_files(&root().join("defects").join(name));
        }
        let names: Vec<_> = overlay.iter().map(|p| p.file_name().unwrap().to_owned()).collect();
        files.retain(|p| !names.contains(&p.file_name().unwrap().to_owned()));
        files.extend(overlay);
        javac(&dir, Some(spring), &files);
    }
    Some(dir)
}

fn build(name: &str) -> Option<PathBuf> {
    build_with(name, None)
}

fn quotes(dir: &Path, id: &str) -> EntryPointSpec {
    observe::entry_points(dir).expect("the fixture's classes read").into_iter().find(|s| s.id == id).unwrap_or_else(|| panic!("no {id}"))
}

fn claim() -> CanonicalClaim {
    serde_json::from_str(&std::fs::read_to_string(root().join("golden/claim.json")).unwrap()).unwrap()
}

/// `POST /quotes` of `before` checked against the same entry point of `build`.
fn check(build_dir: &Path, claim: &CanonicalClaim) -> Checked {
    let before = build("before").unwrap();
    effects::check(claim, &quotes(&before, "POST /quotes"), &quotes(build_dir, "POST /quotes"), &before, build_dir).unwrap_or_else(|u| panic!("{u}"))
}

fn state(c: &Checked, id: &str) -> ObservationState {
    c.outcome.accounting.iter().find(|a| a.observation == id).unwrap_or_else(|| panic!("{id} isn't accounted for: {:?}", c.outcome.accounting)).state
}

#[test]
fn the_refactor_preserves_the_response_status_and_event_trace() {
    let Some(after) = build("after") else { return };
    let c = check(&after, &claim());
    assert_eq!(c.outcome.verdict, Verdict::Verified, "{c:?}");
    for id in ["result", "exception", "status", SEND] {
        assert_eq!(state(&c, id), ObservationState::Preserved, "{id}");
    }
    assert!(c.proof.as_deref().is_some_and(|p| p.contains("cents: long × quantity: int")), "a proof line over the inputs: {c:?}");
    assert!(c.outcome.domain.contains("cents: long × quantity: int"), "{}", c.outcome.domain);
    let said = c.assumptions.join("\n");
    for words in ["KafkaTemplate.send is a recording stub", "every modeled call returns normally", "QuotesController is made by its constructor", "at most 4 attempts"] {
        assert!(said.contains(words), "the assumptions say '{words}': {said}");
    }
}

#[test]
fn a_dropped_event_is_refuted_by_a_witness_replayed_on_the_jvm() {
    let Some(dropped) = build("dropped-effect") else { return };
    let c = check(&dropped, &claim());
    assert_eq!(c.outcome.verdict, Verdict::Refuted, "{c:?}");
    assert_eq!(state(&c, SEND), ObservationState::Refuted);
    assert_eq!(state(&c, "result"), ObservationState::Unresolved, "the same response, so not refuted, and not proved either");
    let (before, after) = (c.before.as_ref().unwrap(), c.after.as_ref().unwrap());
    assert_eq!(before.attempts.len(), 1, "{before:?}");
    assert!(after.attempts.is_empty(), "{after:?}");
    assert_eq!(before.outcome, after.outcome, "the same response");
    let witness = c.outcome.witness.as_deref().unwrap();
    assert!(witness.contains("Replayed on a JVM") && witness.contains("under the modeled dependencies"), "{witness}");
    assert!(witness.contains("send(topic=\"quotes\""), "the attempt with its snapshot: {witness}");
    let quantity: i64 = witness.split("quantity=").nth(1).unwrap().split(|ch: char| !ch.is_ascii_digit() && ch != '-').next().unwrap().parse().unwrap();
    assert!(quantity >= 100, "no event only for 100 items or more: {witness}");
}

#[test]
fn a_duplicated_event_is_refuted_in_exact_order() {
    let Some(duplicated) = build("duplicated-effect") else { return };
    let c = check(&duplicated, &claim());
    assert_eq!(c.outcome.verdict, Verdict::Refuted, "{c:?}");
    assert_eq!(state(&c, SEND), ObservationState::Refuted);
    let (before, after) = (c.before.as_ref().unwrap(), c.after.as_ref().unwrap());
    assert_eq!(before.attempts.len(), 1, "{before:?}");
    assert_eq!(after.attempts.len(), 2, "{after:?}");
    assert_eq!(after.attempts[0].2, after.attempts[1].2, "the same event twice");
    assert_eq!(before.attempts[0].2, after.attempts[0].2);
    assert!(c.outcome.witness.as_deref().unwrap().contains(", then "), "{:?}", c.outcome.witness);
}

#[test]
fn a_changed_total_is_refuted_in_the_response_and_the_event() {
    let Some(offset) = build("offset") else { return };
    let c = check(&offset, &claim());
    assert_eq!(c.outcome.verdict, Verdict::Refuted, "{c:?}");
    let (before, after) = (c.before.as_ref().unwrap(), c.after.as_ref().unwrap());
    assert_ne!(before.outcome, after.outcome);
    assert_eq!(state(&c, "result"), ObservationState::Refuted);
    if !before.attempts.is_empty() && !after.attempts.is_empty() {
        assert_eq!(state(&c, SEND), ObservationState::Refuted, "the event carries the total");
    }
}

#[test]
fn a_trace_past_its_bound_is_unresolved_not_shorter() {
    let Some(duplicated) = build("duplicated-effect") else { return };
    let mut claim = claim();
    claim.environment.as_mut().unwrap().trace_bound = 1;
    let c = check(&duplicated, &claim);
    assert_eq!(c.outcome.verdict, Verdict::Unresolved, "{c:?}");
    assert!(c.reason.as_deref().unwrap().contains("more attempts than the trace bound, 1"), "{:?}", c.reason);
    assert!(c.outcome.accounting.iter().all(|a| a.state == ObservationState::Unresolved));
    // The refactor makes at most one attempt, so the same bound proves it.
    let c = check(&build("after").unwrap(), &claim);
    assert_eq!(c.outcome.verdict, Verdict::Verified, "{c:?}");
}

/// `POST /quotes` of `before` checked against the same entry point of `build`, the proof under the proof cache in
/// `cache`.
fn check_cached(build_dir: &Path, claim: &CanonicalClaim, cache: &Path) -> Checked {
    let before = build("before").unwrap();
    effects::check_with(claim, &quotes(&before, "POST /quotes"), &quotes(build_dir, "POST /quotes"), &before, build_dir, Some(cache)).unwrap_or_else(|u| panic!("{u}"))
}

/// Whether `text` names the run on `before` and `after` by those paths, and no temporary directory of the check's.
fn names_builds(text: &str, before: &Path, after: &Path) -> bool {
    text.contains(&before.display().to_string()) && text.contains(&after.display().to_string()) && !text.contains("jvmcontract-effects")
}

fn exact(c: &Checked) -> Option<&ClaimKey> {
    match &c.reuse {
        Some(Reuse::Exact { key, .. }) => Some(key),
        _ => None,
    }
}

/// The stale-cache defect at the boundary: an entry point's effect-trace proof is reused exactly when its claim is
/// unchanged, and a change to the environment model, to what a recording stub snapshots, to the route's metadata or
/// to the handler's code is a miss. A stored refutation is a hit too, with its witness replayed on a JVM again.
#[test]
fn an_effect_proof_is_reused_exactly_when_its_claim_is_unchanged() {
    let Some(after) = build("after") else { return };
    let cache = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("effects-cache");
    let _ = std::fs::remove_dir_all(&cache);
    let cold = check_cached(&after, &claim(), &cache);
    assert_eq!(cold.outcome.verdict, Verdict::Verified, "{cold:?}");
    let key = cold.key.clone().expect("the proof ran under a claim key");
    assert!(cold.reuse.is_none(), "nothing to reuse on a cold cache");
    let warm = check_cached(&after, &claim(), &cache);
    assert_eq!(exact(&warm), Some(&key), "the unchanged rerun is an exact hit of the same claim: {warm:?}");
    assert_eq!((warm.outcome.verdict, &warm.outcome.accounting), (cold.outcome.verdict, &cold.outcome.accounting), "the reused result is the stored one");
    assert!(warm.proof.as_deref().is_some_and(|p| p.contains("reused from the proof cache")), "{:?}", warm.proof);
    assert_eq!(warm.assumptions, cold.assumptions, "a reused result rests on the same assumptions, and says them");
    // The run a reuse names is the one given these builds, not its rewritten copies in a temporary directory.
    let Some(Reuse::Exact { from, .. }) = &warm.reuse else { unreachable!() };
    let before = build("before").unwrap();
    assert!(names_builds(from, &before, &after), "the reuse names the builds the first run was given: {from}");
    assert!(warm.proof.as_deref().is_some_and(|p| names_builds(p, &before, &after)), "and so does the reused proof: {:?}", warm.proof);
    let text = effects::render_checks(&[effects::EntryCheck { entry: "POST /quotes".into(), handler: String::new(), source_line: None, new_entry: None, checked: Some(warm.clone()), unsupported: None }]);
    assert!(text.lines().any(|l| l.contains("reused:") && names_builds(l, &before, &after)), "the text says which run the result came from:\n{text}");

    // The environment model: one more attempt allowed is a different claim, although the verdict is the same.
    let mut bound = claim();
    bound.environment.as_mut().unwrap().trace_bound += 1;
    let c = check_cached(&after, &bound, &cache);
    assert_eq!(c.outcome.verdict, Verdict::Verified, "{c:?}");
    assert!(c.reuse.is_none() && c.key.as_ref().is_some_and(|k| *k != key), "a changed trace bound is a miss under another key: {:?}", c.key);

    // What a recording stub snapshots: the event's quantity no longer observed.
    let mut payload = claim();
    for o in &mut payload.observations {
        if let Observation::Effect { payload, .. } = o {
            payload.retain(|p| p != "data.quantity");
        }
    }
    let c = check_cached(&after, &payload, &cache);
    assert!(c.reuse.is_none() && c.key.as_ref().is_some_and(|k| *k != key), "a changed snapshot is a miss under another key: {:?}", c.key);

    // The route's metadata: the same code answering 201. A miss, and the changed status is no longer preserved.
    let created = controller("", "", "        if (total > 0) kafka.send(\"quotes\", new QuoteEvent(total, quantity));\n")
        .replace("    @PostMapping(\"/quotes\")\n", "    @PostMapping(\"/quotes\")\n    @ResponseStatus(HttpStatus.CREATED)\n")
        .replace("import org.springframework.web.bind.annotation.RestController;\n", "import org.springframework.web.bind.annotation.RestController;\nimport org.springframework.web.bind.annotation.ResponseStatus;\nimport org.springframework.http.HttpStatus;\n");
    let created = build_with("status-created", Some(&created)).unwrap();
    let c = check_cached(&created, &claim(), &cache);
    assert!(c.reuse.is_none() && c.key.as_ref().is_some_and(|k| *k != key), "a changed annotation is a miss: {:?}", c.key);
    assert_eq!(state(&c, "status"), ObservationState::Unresolved, "{c:?}");
    assert_eq!(c.outcome.verdict, Verdict::Unresolved, "{c:?}");

    // The handler's code: the dropped event is proved again, not the refactor's stored result, and refuted; a rerun
    // reuses the stored refutation, its witness replayed on a JVM again.
    let dropped = build("dropped-effect").unwrap();
    let first = check_cached(&dropped, &claim(), &cache);
    assert!(first.reuse.is_none(), "a changed handler is a miss");
    assert_eq!(first.outcome.verdict, Verdict::Refuted, "{first:?}");
    let again = check_cached(&dropped, &claim(), &cache);
    assert_eq!(exact(&again), first.key.as_ref(), "the rerun reuses the stored refutation: {again:?}");
    assert_eq!(again.outcome.verdict, Verdict::Refuted, "{again:?}");
    assert_eq!(state(&again, SEND), ObservationState::Refuted);
    assert!(again.outcome.witness.as_deref().is_some_and(|w| w.contains("Replayed on a JVM")), "{:?}", again.outcome.witness);
    assert_eq!(again.before, first.before, "the replay gives the old build's attempts again");
    assert_eq!(again.after, first.after, "and the new build's");
}

#[test]
fn what_the_analysis_cannot_see_is_unresolved() {
    let Some(after) = build("after") else { return };
    let before = build("before").unwrap();
    let mut claim = claim();
    claim.contract.subject = "POST /quotes/text".into();
    let c = effects::check(&claim, &quotes(&before, "POST /quotes/text"), &quotes(&after, "POST /quotes/text"), &before, &after).unwrap();
    assert_eq!(c.outcome.verdict, Verdict::Unresolved);
    assert!(c.reason.as_deref().unwrap().contains("string concatenation"), "{:?}", c.reason);
}

const USES_THE_RESULT: &str = r#"package shop;

import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class QuotesController {
    private final KafkaTemplate<String, QuoteEvent> kafka;

    public QuotesController(KafkaTemplate<String, QuoteEvent> kafka) {
        this.kafka = kafka;
    }

    @PostMapping("/quotes")
    public long quote(@RequestParam long cents, @RequestParam int quantity) {
        long total = Pricing.total(new Quote(new Money(cents), quantity));
        if (total > 0 && kafka.send("quotes", new QuoteEvent(total, quantity)) == null) return -1;
        return total;
    }
}
"#;

/// A modelled call's model (`spec::plans::CallModel`, the environment stream's) that the check doesn't encode is
/// refused by name, never checked as a normal return: here a void result of a call keyed by a String topic, which
/// returns an object (a String key is encoded since the merge's E1 and E2 rows).
#[test]
fn a_model_the_check_does_not_encode_is_refused_by_name() {
    use jvmcontract::spec::plans::{CallModel, Coupling, ModelledResult, Returned};
    let Some(after) = build("after") else { return };
    let before = build("before").unwrap();
    let mut claim = claim();
    let call = &mut claim.environment.as_mut().unwrap().calls[0];
    call.model = Some(CallModel { id: "send".into(), key: vec!["arg0".into()], coupling: Coupling::Query, results: vec![ModelledResult::Returns { value: Returned::Void }], bound: 4 });
    let err = effects::check(&claim, &quotes(&before, "POST /quotes"), &quotes(&after, "POST /quotes"), &before, &after).unwrap_err();
    assert_eq!(err.part, jvmcontract::spec::Part::Environment, "{err}");
    assert!(err.what.contains("modelled call's model") && err.what.contains("a result of type void, where the call returns java.lang.Object"), "{err}");
}

#[test]
fn a_handler_that_uses_a_modeled_calls_result_is_refused_by_name() {
    let Some(uses) = build_with("uses-the-result", Some(USES_THE_RESULT)) else { return };
    let before = build("before").unwrap();
    let err = effects::check(&claim(), &quotes(&before, "POST /quotes"), &quotes(&uses, "POST /quotes"), &before, &uses).unwrap_err();
    assert!(err.what.contains("uses the result of KafkaTemplate.send"), "{err}");
}

/// The refactor's controller with `extra` in place of its `if (total > 0) ...` line, and `fields` and `parameters`
/// added to its fields and its constructor's.
fn controller(fields: &str, parameters: &str, extra: &str) -> String {
    let after = std::fs::read_to_string(root().join("after/shop/QuotesController.java")).unwrap();
    let after = after.replace("    private final KafkaTemplate<String, QuoteEvent> kafka;\n", &format!("    private final KafkaTemplate<String, QuoteEvent> kafka;\n{fields}"));
    let after = after.replace("KafkaTemplate<String, QuoteEvent> kafka) {", &format!("KafkaTemplate<String, QuoteEvent> kafka{parameters}) {{"));
    after.replace("        if (total > 0) kafka.send(\"quotes\", new QuoteEvent(total, quantity));\n", extra)
}

/// A payload literal with an isolated surrogate is snapshotted as the very object the build loads, unit for unit:
/// the same topic in two builds is preserved, and one that differs only in its surrogate is refuted, naming each.
/// Before, the class reader read both as `"q\u{FFFD}"`, so the snapshot's own literal was neither object, and the
/// trace was unresolved either way.
#[test]
fn a_payload_literal_with_an_isolated_surrogate_is_snapshotted_unit_for_unit() {
    let send = |topic: &str| controller("", "", &format!("        if (total > 0) kafka.send(\"{topic}\", new QuoteEvent(total, quantity));\n"));
    let Some(high) = build_with("topic-high", Some(&send("q\\uDBFF"))) else { return };
    let Some(again) = build_with("topic-high-again", Some(&send("q\\uDBFF"))) else { return };
    let Some(other) = build_with("topic-other", Some(&send("q\\uDBFE"))) else { return };
    let compare = |a: &Path, b: &Path| effects::check(&claim(), &quotes(a, "POST /quotes"), &quotes(b, "POST /quotes"), a, b).unwrap_or_else(|u| panic!("{u}"));
    let same = compare(&high, &again);
    assert_eq!(same.outcome.verdict, Verdict::Verified, "{same:?}");
    assert_eq!(state(&same, SEND), ObservationState::Preserved);
    let changed = compare(&high, &other);
    assert_eq!(changed.outcome.verdict, Verdict::Refuted, "{changed:?}");
    assert_eq!(state(&changed, SEND), ObservationState::Refuted);
    let witness = changed.outcome.witness.as_deref().unwrap();
    assert!(witness.contains("Replayed on a JVM"), "{witness}");
    assert!(witness.contains("send(topic=\"q\\udbff\"") && witness.contains("send(topic=\"q\\udbfe\""), "each topic by its units: {witness}");
}

#[test]
fn a_null_dependency_called_through_a_supertype_leaves_the_result_unresolved_where_reached() {
    // javac names `kafka.hashCode()` `Object.hashCode`, which no stub can tell from any other call: the null
    // dependency throws, and the NullPointerException marks the log.
    let source = controller("", "", "        if (quantity == 3 && kafka.hashCode() == 0) return -1;\n        if (total > 0) kafka.send(\"quotes\", new QuoteEvent(total, quantity));\n");
    let Some(unmodeled) = build_with("unmodeled-call", Some(&source)) else { return };
    let c = check(&unmodeled, &claim());
    assert_eq!(c.outcome.verdict, Verdict::Unresolved, "{c:?}");
    assert!(c.reason.as_deref().unwrap().contains("a NullPointerException, which a dependency left null may have caused"), "{:?}", c.reason);
    assert!(c.reason.as_deref().unwrap().contains("quantity=3"), "only where it is reached: {:?}", c.reason);
}

#[test]
fn a_handler_given_an_application_object_is_refused_by_name() {
    let source = controller("    private final Quote seed;\n", ", Quote seed", "        if (total > 0) kafka.send(\"quotes\", new QuoteEvent(total, quantity));\n").replace("this.kafka = kafka;", "this.kafka = kafka;\n        this.seed = seed;");
    let Some(given) = build_with("given-a-quote", Some(&source)) else { return };
    let before = build("before").unwrap();
    let err = effects::check(&claim(), &quotes(&before, "POST /quotes"), &quotes(&given, "POST /quotes"), &before, &given).unwrap_err();
    assert!(err.what.contains("is given an application shop.Quote"), "{err}");
}

#[test]
fn the_effect_log_plan_names_its_stubs_and_assumptions() {
    let Some(after) = build("after") else { return };
    let plan = observe::effect_log(&quotes(&after, "POST /quotes")).unwrap();
    assert_eq!(plan.environment.order, OrderPolicy::Exact);
    assert_eq!(plan.stubs.len(), 1);
    assert_eq!(format!("effect:{}", plan.stubs[0].call), SEND);
    assert_eq!(plan.stubs[0].snapshot, ["topic", "data.total", "data.quantity"]);
    assert!(plan.stubs[0].returns.starts_with("null"), "{:?}", plan.stubs[0]);
    assert!(plan.assumptions.iter().any(|a| a.contains("not a delivery")), "{:?}", plan.assumptions);
}

#[test]
fn the_claim_a_spec_makes_is_the_joint_examples_claim() {
    let Some(before) = build("before") else { return };
    let golden = claim();
    let made = effects::claim_for(&quotes(&before, "POST /quotes"), None, golden.bounds.clone());
    assert_eq!(made.contract.subject, golden.contract.subject);
    assert_eq!(made.contract.inputs, golden.contract.inputs);
    assert_eq!(made.contract.required, golden.contract.required);
    assert!(made.contract.approved_changes.is_empty(), "nothing is approved by a claim made from the spec");
    assert_eq!(made.observations, golden.observations);
    assert_eq!(made.environment, golden.environment);
    let bounded = effects::claim_for(&quotes(&before, "POST /quotes"), Some(1), golden.bounds.clone());
    assert_eq!(bounded.environment.unwrap().trace_bound, 1);
}

/// `jvmcontract effects BEFORE AFTER ARGS`: its exit code and what it printed.
fn effects_command(before: &Path, after: &Path, args: &[&str]) -> (i32, String, String) {
    let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).arg("effects").arg(before).arg(after).args(args).output().expect("the command runs");
    (out.status.code().unwrap_or(-1), String::from_utf8_lossy(&out.stdout).into_owned(), String::from_utf8_lossy(&out.stderr).into_owned())
}

#[test]
fn the_command_checks_every_entry_point_of_two_builds() {
    let Some(after) = build("after") else { return };
    let before = build("before").unwrap();
    let (code, text, err) = effects_command(&before, &after, &[]);
    assert_eq!(code, 1, "one entry point is unresolved, so not every one is verified: {text}{err}");
    assert!(text.contains("POST /quotes: verified\n"), "{text}");
    assert!(text.contains("  observations: result preserved, exception preserved, status preserved, KafkaTemplate.send preserved\n"), "{text}");
    assert!(text.contains("  proof: ") && text.contains("over cents: long × quantity: int"), "{text}");
    assert!(text.contains("  assumes: KafkaTemplate.send is a recording stub"), "{text}");
    assert!(text.contains("POST /quotes/text: unresolved\n") && text.contains("string concatenation"), "{text}");
    assert!(text.ends_with("2 entry points: 1 verified, 0 refuted, 1 unresolved, 0 unsupported\n"), "{text}");

    let (code, text, _) = effects_command(&before, &after, &["--entry", "POST /quotes"]);
    assert_eq!(code, 0, "{text}");
    assert!(text.ends_with("1 entry points: 1 verified, 0 refuted, 0 unresolved, 0 unsupported\n"), "{text}");

    let (code, _, err) = effects_command(&before, &after, &["--entry", "GET /nothing"]);
    assert_eq!(code, 2, "an entry point the old build doesn't have is an error");
    assert!(err.contains("no entry point GET /nothing") && err.contains("POST /quotes"), "{err}");
}

#[test]
fn the_command_reports_a_refutation_with_both_builds_attempts() {
    let Some(duplicated) = build("duplicated-effect") else { return };
    let before = build("before").unwrap();
    let (code, text, err) = effects_command(&before, &duplicated, &["--entry", "POST /quotes"]);
    assert_eq!(code, 1, "{text}{err}");
    assert!(text.contains("POST /quotes: refuted\n"), "{text}");
    assert!(text.contains("KafkaTemplate.send refuted"), "{text}");
    assert!(text.contains("  witness: ") && text.contains(", then KafkaTemplate.send(topic=\"quotes\"") && text.contains("under the modeled dependencies"), "{text}");
    assert!(text.contains("  search: "), "a refutation's checker line is no proof: {text}");

    let (code, json, _) = effects_command(&before, &duplicated, &["--entry", "POST /quotes", "--trace-bound", "1", "--json"]);
    assert_eq!(code, 1);
    let checks: serde_json::Value = serde_json::from_str(&json).expect("JSON");
    let c = &checks[0]["checked"];
    assert_eq!(checks[0]["entry"], "POST /quotes");
    assert_eq!(c["outcome"]["verdict"], "unresolved", "past the bound given on the command line: {json}");
    assert!(c["reason"].as_str().unwrap().contains("more attempts than the trace bound, 1"), "{json}");
}

#[test]
fn the_command_reports_what_the_narrow_case_refuses_and_checks_the_rest() {
    let Some(uses) = build_with("uses-the-result", Some(USES_THE_RESULT)) else { return };
    let before = build("before").unwrap();
    let (code, text, err) = effects_command(&before, &uses, &[]);
    assert_eq!(code, 1, "{text}{err}");
    assert!(text.contains("POST /quotes: unsupported: ") && text.contains("uses the result of KafkaTemplate.send"), "{text}");
    assert!(text.ends_with("0 verified, 0 refuted, 1 unresolved, 1 unsupported\n"), "{text}");
}

/// A controller that sends two classes of payload through one `send`: `Bulk` (with the quantity) from ten items,
/// `Single` (without) below; `body` is the handler's body after the total is computed.
fn two_classes(body: &str) -> String {
    format!(
        r#"package shop;

import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class QuotesController {{
    public record Bulk(long total, int quantity) {{}}

    public record Single(long total) {{}}

    private final KafkaTemplate<String, Object> kafka;

    public QuotesController(KafkaTemplate<String, Object> kafka) {{
        this.kafka = kafka;
    }}

    @PostMapping("/quotes")
    public long quote(@RequestParam long cents, @RequestParam int quantity) {{
        long total = Pricing.total(new Quote(new Money(cents), quantity));
{body}        return total;
    }}
}}
"#
    )
}

const TWO_CLASSES: &str = "        if (quantity >= 10) kafka.send(\"quotes\", new Bulk(total, quantity));\n        else kafka.send(\"quotes\", new Single(total));\n";

#[test]
fn payloads_of_two_classes_through_one_call_are_snapshotted_each_through_its_own_class() {
    let Some(old) = build_with("two-classes", Some(&two_classes(TWO_CLASSES))) else { return };
    let reordered = "        if (quantity < 10) {\n            kafka.send(\"quotes\", new Single(total));\n            return total;\n        }\n        kafka.send(\"quotes\", new Bulk(total, quantity));\n";
    let new = build_with("two-classes-reordered", Some(&two_classes(reordered))).unwrap();
    let c = effects::check(&claim(), &quotes(&old, "POST /quotes"), &quotes(&new, "POST /quotes"), &old, &new).unwrap_or_else(|u| panic!("{u}"));
    assert_eq!(c.outcome.verdict, Verdict::Verified, "{c:?}");
    assert_eq!(state(&c, SEND), ObservationState::Preserved);

    // The same values in a payload of the other class: the class is observed, so the traces differ.
    let swapped = "        if (quantity >= 100) kafka.send(\"quotes\", new Single(total));\n        else if (quantity >= 10) kafka.send(\"quotes\", new Bulk(total, quantity));\n        else kafka.send(\"quotes\", new Single(total));\n";
    let new = build_with("two-classes-swapped", Some(&two_classes(swapped))).unwrap();
    let c = effects::check(&claim(), &quotes(&old, "POST /quotes"), &quotes(&new, "POST /quotes"), &old, &new).unwrap_or_else(|u| panic!("{u}"));
    assert_eq!(c.outcome.verdict, Verdict::Refuted, "{c:?}");
    let witness = c.outcome.witness.as_deref().unwrap();
    assert!(witness.contains("data.class=shop.QuotesController$Bulk") && witness.contains("data.class=shop.QuotesController$Single"), "{witness}");
    assert!(witness.contains("data.quantity=absent"), "a path the payload's class lacks is absent: {witness}");
    assert!(witness.contains("Replayed on a JVM") && witness.contains("under the modeled dependencies"), "{witness}");
}

#[test]
fn the_command_writes_a_sarif_finding_per_refuted_entry_point_anchored_at_its_handler() {
    let Some(duplicated) = build("duplicated-effect") else { return };
    let before = build("before").unwrap();
    let report = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("effects-report");
    let _ = std::fs::remove_dir_all(&report);
    let sources = root().join("before");
    let (code, text, err) = effects_command(&before, &duplicated, &["--report", report.to_str().unwrap(), "--sources", sources.to_str().unwrap(), "--base", root().to_str().unwrap()]);
    assert_eq!(code, 1, "{text}{err}");
    let sarif: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(report.join("effects.sarif")).unwrap()).unwrap();
    let results = sarif["runs"][0]["results"].as_array().unwrap();
    assert_eq!(results.len(), 1, "only the refuted entry point, not the unresolved one: {sarif}");
    assert_eq!(results[0]["ruleId"], "effects-changed");
    assert!(results[0]["message"]["text"].as_str().unwrap().starts_with("POST /quotes no longer preserves"), "{sarif}");
    assert_eq!(results[0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"], "before/shop/QuotesController.java");

    let (code, _, _) = effects_command(&before, &build("after").unwrap(), &["--entry", "POST /quotes", "--report", report.to_str().unwrap()]);
    assert_eq!(code, 0);
    let sarif: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(report.join("effects.sarif")).unwrap()).unwrap();
    assert_eq!(sarif["runs"][0]["results"].as_array().unwrap().len(), 0, "a verified run writes an empty report");
}
