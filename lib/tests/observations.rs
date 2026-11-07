//! Observation specs (`jvmcontract observations`, `lib/src/observations.rs`) on the joint example of the foundations
//! loop (`lib/tests/fixtures/foundations/`), checked field by field, and on every entry point of Box Office
//! (`examples/apps/boxoffice/`), checked against golden text and the facts read off its source.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::{Mutex, OnceLock};

use jvmcontract::classpath::ClassPath;
use jvmcontract::observations::{analyse, compare, unaccounted, NOT_OBSERVED};
use jvmcontract::spec::observe::{self, Binding, BindingSource, Change, EntryKind, EntryPointSpec, Obligation, Placement, SiteKind, StatusOutcome};
use jvmcontract::spec::{Derivation, ExternalInput, Observation, OrderPolicy};

const SEND: &str = "org/springframework/kafka/core/KafkaTemplate#send(Ljava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;";

fn has_javac() -> bool {
    Command::new("javac").arg("-version").output().is_ok_and(|o| o.status.success())
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

/// The classes of `before`, `after`, or a defect overlaid on `after`, compiled once each.
fn build(name: &str) -> PathBuf {
    static SPRING: OnceLock<PathBuf> = OnceLock::new();
    static BUILDING: Mutex<()> = Mutex::new(());
    let _one_at_a_time = BUILDING.lock().unwrap_or_else(|e| e.into_inner());
    let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
    let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("observations");
    let spring = SPRING.get_or_init(|| {
        let _ = std::fs::remove_dir_all(&out);
        let dir = out.join("spring");
        javac(&dir, None, &java_files(&manifest.join("tests/fixtures/spring/org")));
        dir
    });
    let root = manifest.join("tests/fixtures/foundations");
    let dir = out.join(name);
    if !dir.exists() {
        let mut files = java_files(&root.join(if name == "before" { "before" } else { "after" }));
        if !matches!(name, "before" | "after") {
            let overlay_dir = root.join("defects").join(name);
            let overlay = java_files(&overlay_dir);
            let names: Vec<_> = overlay.iter().map(|p| p.file_name().unwrap().to_owned()).collect();
            files.retain(|p| !names.contains(&p.file_name().unwrap().to_owned()));
            files.extend(overlay);
        }
        javac(&dir, Some(spring), &files);
    }
    dir
}

fn specs(name: &str) -> Vec<EntryPointSpec> {
    observe::entry_points(&build(name)).expect("the fixture's classes read")
}

fn find<'a>(specs: &'a [EntryPointSpec], id: &str) -> &'a EntryPointSpec {
    specs.iter().find(|s| s.id == id).unwrap_or_else(|| panic!("no {id} among {:?}", specs.iter().map(|s| &s.id).collect::<Vec<_>>()))
}

#[test]
fn a_route_observes_its_response_status_and_event() {
    if !has_javac() {
        return;
    }
    let specs = specs("before");
    assert_eq!(specs.iter().map(|s| s.id.as_str()).collect::<Vec<_>>(), ["POST /quotes", "POST /quotes/text"]);
    let quotes = find(&specs, "POST /quotes");
    assert_eq!(quotes.kind, EntryKind::Route);
    assert_eq!(quotes.handler, "shop.QuotesController#quote");
    let inputs: Vec<(&str, &str)> = quotes.inputs.iter().map(|i| (i.name.as_str(), i.ty.as_str())).collect();
    assert_eq!(inputs, [("cents", "long"), ("quantity", "int")]);
    assert!(quotes.inputs.iter().all(|i| i.derivation == Derivation::Identity));
    assert!(quotes.bindings.iter().all(|b| b.source == BindingSource::RequestParameter));
    assert_eq!(quotes.response.as_deref(), Some("long"));
    assert_eq!(quotes.observations, vec![
        Observation::Result,
        Observation::Exception,
        Observation::Status,
        Observation::Effect { call: SEND.into(), payload: vec!["topic".into(), "data.total".into(), "data.quantity".into()] },
    ]);
    // The Quote constructor's guard reaches the boundary as a 500: nothing maps it.
    let statuses: Vec<(&str, Option<u16>)> = quotes.statuses.iter().map(|s| (s.outcome.as_str(), s.status)).collect();
    assert_eq!(statuses, [("returns", Some(200)), ("IllegalArgumentException", Some(500))]);
    assert_eq!(quotes.effects.len(), 1);
    let send = &quotes.effects[0];
    assert_eq!((send.kind, send.target.as_str(), send.placement), (SiteKind::Send, "quotes", Placement::Outside));
    assert_eq!(quotes.environment.calls.len(), 1);
    assert_eq!(quotes.environment.calls[0].call, SEND);
    assert_eq!(quotes.environment.calls[0].outcomes, ["returns"]);
    assert_eq!((quotes.environment.trace_bound, quotes.environment.order), (4, OrderPolicy::Exact));
    assert_eq!(quotes.assumptions.len(), 1, "the environment model's restriction to normal returns is stated");
    assert!(quotes.identity.starts_with("none"), "a serialized response counts no identity relations");
    assert!(quotes.unresolved.is_empty(), "{:?}", quotes.unresolved);
}

#[test]
fn what_the_analysis_cannot_see_stays_in_the_spec() {
    if !has_javac() {
        return;
    }
    let specs = specs("before");
    let text = find(&specs, "POST /quotes/text");
    assert_eq!(text.response.as_deref(), Some("String"));
    assert!(text.effects.is_empty());
    assert_eq!(text.unresolved.len(), 1);
    assert!(text.unresolved[0].contains("StringConcatFactory.makeConcatWithConstants") && text.unresolved[0].contains("string concatenation"), "{}", text.unresolved[0]);
}

#[test]
fn the_specs_are_the_same_for_the_refactor_and_say_where_the_defects_differ() {
    if !has_javac() {
        return;
    }
    let before = specs("before");
    // The refactor changes no boundary: the same ids, inputs, observations and effects (the method labels too).
    let strip = |s: &EntryPointSpec| {
        let mut s = s.clone();
        s.source_line = None;
        s
    };
    assert_eq!(before.iter().map(strip).collect::<Vec<_>>(), specs("after").iter().map(strip).collect::<Vec<_>>());
    // A dropped or duplicated event changes no spec: the spec says what to observe, and the trace (O3) differs.
    for defect in ["dropped-effect", "duplicated-effect"] {
        let quotes = find(&specs(defect), "POST /quotes").clone();
        assert_eq!(quotes.observations, find(&before, "POST /quotes").observations, "{defect}");
    }
    // A renamed route is another entry point.
    let renamed = specs("route-change");
    assert!(renamed.iter().all(|s| s.id != "POST /quotes"));
    assert_eq!(find(&renamed, "POST /quote").handler, "shop.QuotesController#quote");
}

#[test]
fn the_command_prints_the_specs_as_text_and_json() {
    if !has_javac() {
        return;
    }
    let dir = build("before");
    let bin = env!("CARGO_BIN_EXE_jvmcontract");
    let text = Command::new(bin).arg("observations").arg(&dir).output().unwrap();
    assert!(text.status.success());
    let text = String::from_utf8(text.stdout).unwrap();
    assert!(text.starts_with("POST /quotes => shop.QuotesController#quote\n"), "{text}");
    assert!(text.contains("  sends to quotes by KafkaTemplate.send, outside a transaction, in QuotesController.quote(long, int), snapshot of topic, data.total, data.quantity\n"), "{text}");
    assert!(text.contains("  unresolved: a dynamic call site"), "{text}");
    let json = Command::new(bin).arg("observations").arg("--json").arg(&dir).output().unwrap();
    assert!(json.status.success());
    let parsed: Vec<EntryPointSpec> = serde_json::from_slice(&json.stdout).unwrap();
    assert_eq!(parsed, specs("before"));
}

fn of<'a>(obligations: &'a [Obligation], entry: &str, observation: &str) -> &'a Obligation {
    let found: Vec<&Obligation> = obligations.iter().filter(|o| o.entry == entry && o.observation == observation).collect();
    assert_eq!(found.len(), 1, "one obligation for {entry} {observation}: {obligations:#?}");
    found[0]
}

fn changes(obligations: &[Obligation], entry: &str) -> Vec<(String, Change)> {
    obligations.iter().filter(|o| o.entry == entry).map(|o| (o.observation.clone(), o.change)).collect()
}

#[test]
fn two_builds_of_the_joint_example_compare_into_accounted_obligations() {
    if !has_javac() {
        return;
    }
    let before = specs("before");
    let effect = format!("effect:{SEND}");
    // The refactor, and the effect defects: the same shapes, so every observation is to be proved preserved. A
    // dropped or a duplicated event doesn't show here; the effect trace (O3) is what refutes it.
    for build in ["after", "dropped-effect", "duplicated-effect", "offset"] {
        let obligations = observe::compare(&before, &specs(build)).unwrap();
        assert!(unaccounted(&before, &obligations).is_empty(), "{build}");
        let want: Vec<(String, Change)> = ["result", "exception", "status", effect.as_str()].iter().map(|o| (o.to_string(), Change::Preserved)).collect();
        assert_eq!(changes(&obligations, "POST /quotes"), want, "{build}");
        assert!(of(&obligations, "POST /quotes", &effect).needs.contains("effect-trace proof"), "{build}");
        // The concatenation stays an obligation of its own, unresolved, beside the three to prove.
        let text = of(&obligations, "POST /quotes/text", "unresolved");
        assert_eq!(text.change, Change::Unresolved);
        assert!(text.differences.iter().any(|d| d.starts_with("before: ") && d.contains("string concatenation")), "{:?}", text.differences);
        assert!(obligations.iter().all(|o| o.new_entry.is_none() && o.change != Change::New), "{build}");
    }
    // A renamed route: the old entry point's observations are removed, the new one's new, and nothing is to prove.
    let obligations = observe::compare(&before, &specs("route-change")).unwrap();
    assert!(unaccounted(&before, &obligations).is_empty());
    assert!(changes(&obligations, "POST /quotes").iter().all(|(_, c)| *c == Change::Removed));
    assert_eq!(changes(&obligations, "POST /quotes").len(), 4);
    assert!(of(&obligations, "POST /quotes", "result").differences.iter().any(|d| d.contains("now serves POST /quote")));
    assert!(changes(&obligations, "POST /quote").iter().all(|(_, c)| *c == Change::New));
    assert!(of(&obligations, "POST /quote", "status").needs.contains("nothing to preserve"));
}

/// `POST /quotes` of the joint example's old build, to change by hand.
fn quotes() -> Option<EntryPointSpec> {
    has_javac().then(|| find(&specs("before"), "POST /quotes").clone())
}

#[test]
fn a_renamed_handler_or_path_variable_is_the_same_entry_point() {
    let Some(old) = quotes() else { return };
    let mut new = old.clone();
    new.handler = "shop.QuotesController#price".into();
    new.method = "QuotesController.price(long, int)".into();
    let obligations = compare(std::slice::from_ref(&old), &[new]);
    assert!(obligations.iter().all(|o| o.change == Change::Preserved && o.new_entry.is_none()), "{obligations:#?}");
    // A path variable renamed in the template: the client's path is the same, so is the entry point.
    let mut old = old;
    old.id = "GET /holds/{id}".into();
    let mut new = old.clone();
    new.id = "GET /holds/{holdId}".into();
    let obligations = compare(std::slice::from_ref(&old), &[new]);
    assert!(unaccounted(std::slice::from_ref(&old), &obligations).is_empty());
    assert!(obligations.iter().all(|o| o.change == Change::Preserved && o.new_entry.as_deref() == Some("GET /holds/{holdId}")), "{obligations:#?}");
}

#[test]
fn a_changed_shape_is_changed_not_preserved() {
    let Some(old) = quotes() else { return };
    let effect = format!("effect:{SEND}");
    let check = |new: EntryPointSpec, observation: &str, change: Change, says: &str| {
        let obligations = compare(std::slice::from_ref(&old), &[new]);
        assert!(unaccounted(std::slice::from_ref(&old), &obligations).is_empty(), "{obligations:#?}");
        let o = of(&obligations, "POST /quotes", observation);
        assert_eq!(o.change, change, "{o:#?}");
        assert!(o.differences.iter().any(|d| d.contains(says)), "'{says}' in {:?}", o.differences);
        o.clone()
    };
    // A status mapping: the guard's exception now answers 400.
    let mut new = old.clone();
    new.statuses[1] = StatusOutcome { outcome: "IllegalArgumentException".into(), status: Some(400), by: "@ExceptionHandler Errors.invalid".into(), when: Vec::new() };
    let o = check(new, "status", Change::Changed, "IllegalArgumentException: 500 (nothing maps it), now 400");
    assert!(o.needs.contains("approval"));
    // An outcome replaced by another with the same status is preserved, the difference left to the proof.
    let mut new = old.clone();
    new.statuses[1].outcome = "IllegalStateException".into();
    check(new, "status", Change::Preserved, "a new outcome IllegalStateException");
    // A status no exception was answered with before.
    let mut new = old.clone();
    new.statuses.push(StatusOutcome { outcome: "ConflictException".into(), status: Some(409), by: "@ExceptionHandler Errors.conflict".into(), when: Vec::new() });
    check(new, "status", Change::Changed, "the new build answers 409 for an exception it throws; no exception of the old build is answered 409");
    // A normal return whose status the analysis can't tell leaves it unresolved: it may be the one it was.
    let mut new = old.clone();
    new.statuses[0].status = None;
    check(new, "status", Change::Unresolved, "returns: 200 (the default), now unknown");
    let mut new = old.clone();
    new.statuses[0].status = None;
    new.statuses[1].status = Some(400);
    check(new, "status", Change::Changed, "IllegalArgumentException: 500 (nothing maps it), now 400");
    let mut both = old.clone();
    both.statuses[0].status = None;
    let obligations = compare(std::slice::from_ref(&both), std::slice::from_ref(&both));
    assert_eq!(of(&obligations, "POST /quotes", "status").change, Change::Unresolved);
    // The effect moved into a transaction.
    let mut new = old.clone();
    new.effects[0].placement = Placement::Inside;
    check(new, &effect, Change::Changed, "sends to quotes: outside a transaction, now inside its transaction");
    // Its payload's shape.
    let mut new = old.clone();
    let Observation::Effect { payload, .. } = &mut new.observations[3] else { panic!() };
    payload.retain(|p| p != "data.quantity");
    check(new, &effect, Change::Changed, "its payload no longer snapshots data.quantity");
    // To another topic.
    let mut new = old.clone();
    new.effects[0].target = "prices".into();
    check(new, &effect, Change::Changed, "the old build sends to quotes by it");
    // A second call site is the trace proof's to judge.
    let mut new = old.clone();
    new.effects.push(new.effects[0].clone());
    check(new, &effect, Change::Preserved, "1 call sites in the old build, 2 in the new");
    // The effect gone: removed, and a new one only the new build has.
    let mut new = old.clone();
    new.observations.truncate(3);
    new.effects.clear();
    check(new.clone(), &effect, Change::Removed, "doesn't observe it");
    let mut new = old.clone();
    new.observations.push(Observation::Effect { call: "org/example/Audit#record(Ljava/lang/Object;)V".into(), payload: vec!["event".into()] });
    let obligations = compare(std::slice::from_ref(&old), &[new]);
    assert_eq!(of(&obligations, "POST /quotes", "effect:org/example/Audit#record(Ljava/lang/Object;)V").change, Change::New);
    // The response's type, and a new input: the preservation contract's inputs aren't the tool's to map.
    let mut new = old.clone();
    new.response = Some("shop.Money".into());
    check(new, "result", Change::Changed, "the response was long, now shop.Money");
    let mut new = old.clone();
    new.inputs.push(ExternalInput { name: "Idempotency-Key".into(), ty: "String".into(), derivation: Derivation::Identity });
    new.bindings.push(Binding { input: "Idempotency-Key".into(), source: BindingSource::Header, wire_type: "java.lang.String".into(), shape: Vec::new() });
    let o = check(new, "inputs", Change::Changed, "a new input Idempotency-Key: String (header)");
    assert!(o.needs.contains("approved by a person"));
}

#[test]
fn entry_points_a_key_does_not_tell_apart_are_unresolved() {
    let Some(old) = quotes() else { return };
    // Two schedules with the same timing, before and after, and neither handler kept: which is which is a question.
    let schedule = |handler: &str| {
        let mut s = old.clone();
        s.kind = EntryKind::Schedule;
        s.handler = handler.into();
        s.id = format!("schedule fixedDelay = 1000 ({handler})");
        s
    };
    let before = [schedule("a.Jobs#sweep"), schedule("a.Jobs#flush")];
    let after = [schedule("a.Jobs#sweepHolds"), schedule("a.Jobs#flushOutbox")];
    let obligations = compare(&before, &after);
    assert!(unaccounted(&before, &obligations).is_empty());
    for s in &before {
        assert!(changes(&obligations, &s.id).iter().all(|(_, c)| *c == Change::Unresolved), "{obligations:#?}");
    }
    assert!(after.iter().all(|s| changes(&obligations, &s.id).iter().all(|(_, c)| *c == Change::New)));
    // With one handler kept, it pairs, and so does the other.
    let after = [schedule("a.Jobs#sweep"), schedule("a.Jobs#flushOutbox")];
    let obligations = compare(&before, &after);
    assert!(obligations.iter().all(|o| o.change == Change::Preserved), "{obligations:#?}");
}

#[test]
fn the_command_compares_against_an_earlier_builds_specs() {
    if !has_javac() {
        return;
    }
    let bin = env!("CARGO_BIN_EXE_jvmcontract");
    let old = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("observations").join("before.json");
    std::fs::write(&old, serde_json::to_string(&specs("before")).unwrap()).unwrap();
    let run = |args: &[&str]| {
        let out = Command::new(bin).arg("observations").arg(build("route-change")).arg("--against").arg(&old).args(args).output().unwrap();
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8(out.stdout).unwrap()
    };
    let text = run(&[]);
    assert!(text.starts_with(&format!("POST /quotes\n  removed: result, exception, status, effect:{SEND}\n    - no entry point of the new build is POST /quotes\n")), "{text}");
    assert!(text.contains("POST /quotes/text\n  preserved, to prove: result\n"), "{text}");
    assert!(text.contains("  unresolved: what the analysis can't see\n"), "{text}");
    assert!(text.ends_with(&format!("7 observations of 2 entry points: 3 to prove preserved, 0 changed and 4 removed (each preserved only with a person's approval), 0 unresolved; 4 new\n{NOT_OBSERVED}\n")), "{text}");
    let parsed: Vec<Obligation> = serde_json::from_str(&run(&["--json"])).unwrap();
    assert_eq!(parsed, observe::compare(&specs("before"), &specs("route-change")).unwrap());
}

/// Box Office's Spring modules, built by its own Gradle build (offline, no daemon) in a copy under the target folder,
/// as `examples/tools/build.py`'s B12 runner builds them: the copy's root, and the union of the modules' runtime class
/// paths (the extra jars change no spec). `None`, after `missing`, when the build can't run here.
fn boxoffice() -> Option<&'static (PathBuf, String)> {
    static BUILT: OnceLock<Option<(PathBuf, String)>> = OnceLock::new();
    BUILT
        .get_or_init(|| {
            let repo = Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
            let copy = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("observations-boxoffice");
            let _ = std::fs::remove_dir_all(&copy);
            for dir in ["examples/apps/boxoffice", "examples/tools/contracts"] {
                copy_tree(&repo.join(dir), &copy.join(dir));
            }
            let root = copy.join("examples/apps/boxoffice");
            let mut tasks = vec![":messaging:jar", ":contracts:jar", ":ticketing-domain:jar", ":ticketing-service:compileJava", ":payment-service:compileJava"];
            tasks.extend(MODULES.iter().map(|(m, _)| match *m {
                "ticketing-service" => ":ticketing-service:printRuntimeClasspath",
                "payment-service" => ":payment-service:printRuntimeClasspath",
                _ => ":messaging:printRuntimeClasspath",
            }));
            let out = Command::new(root.join("gradlew")).args(["-q", "--offline", "--no-daemon"]).args(&tasks).current_dir(&root).output();
            let Some(out) = out.ok().filter(|o| o.status.success()) else {
                missing("Box Office's Gradle build, offline (examples/apps/boxoffice/gradlew --offline)");
                return None;
            };
            let mut entries: Vec<String> = String::from_utf8_lossy(&out.stdout).lines().flat_map(|l| l.trim().split(':').map(str::to_string).collect::<Vec<_>>()).filter(|e| !e.is_empty()).collect();
            entries.sort();
            entries.dedup();
            Some((root, entries.join(":")))
        })
        .as_ref()
}

fn missing(what: &str) {
    let skip = std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1");
    assert!(skip, "{what} not available: set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip the tests that need it");
}

fn copy_tree(from: &Path, to: &Path) {
    std::fs::create_dir_all(to).unwrap();
    for entry in std::fs::read_dir(from).unwrap() {
        let entry = entry.unwrap();
        let name = entry.file_name();
        if matches!(name.to_str(), Some("build" | ".gradle" | ".kotlin")) {
            continue;
        }
        let path = entry.path();
        if path.is_dir() {
            copy_tree(&path, &to.join(&name));
        } else {
            std::fs::copy(&path, to.join(&name)).unwrap();
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                let mode = std::fs::metadata(&path).unwrap().permissions().mode();
                std::fs::set_permissions(to.join(&name), std::fs::Permissions::from_mode(mode)).unwrap();
            }
        }
    }
}

/// Box Office's modules with entry points, and the ids of their routes, listeners and schedules (the boundary
/// contracts' other entry points are `@Bean` definitions, which nothing outside calls).
const MODULES: [(&str, &[&str]); 3] = [
    ("ticketing-service", &[
        "GET /concerts/{id}", "GET /holds/{id}", "GET /orders/{id}", "POST /concerts", "POST /concerts/{id}/holds", "POST /orders",
        "POST /orders/{id}/cancellation", "kafka payments.events", "schedule fixedDelayString = \"${boxoffice.hold.sweep-interval:1s}\"",
    ]),
    ("payment-service", &["GET /payments", "GET /payments/{orderId}", "kafka payments.commands"]),
    ("messaging", &["schedule fixedDelayString = \"${boxoffice.outbox.poll-interval:100ms}\""]),
];

/// The module's specs from the command, as text and as JSON, the sibling modules followed (`--base`).
fn boxoffice_specs(module: &str) -> Option<(String, Vec<EntryPointSpec>)> {
    let (root, classpath) = boxoffice()?;
    let classes = root.join(module).join("build/classes/java/main");
    let run = |json: bool| {
        let mut cmd = Command::new(env!("CARGO_BIN_EXE_jvmcontract"));
        cmd.arg("observations");
        if json {
            cmd.arg("--json");
        }
        let out = cmd.arg(&classes).arg("--classpath").arg(classpath).arg("--base").arg(root).output().unwrap();
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8(out.stdout).unwrap()
    };
    Some((run(false), serde_json::from_str(&run(true)).unwrap()))
}

#[test]
fn every_box_office_entry_point_has_a_spec_that_matches_its_golden_text() {
    for (module, ids) in MODULES {
        let Some((text, specs)) = boxoffice_specs(module) else { return };
        assert_eq!(specs.iter().map(|s| s.id.as_str()).collect::<Vec<_>>(), ids, "{module}");
        let golden = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/boxoffice-observations").join(format!("{module}.txt"));
        if std::env::var("JVMCONTRACT_BLESS").is_ok_and(|v| v == "1") {
            std::fs::create_dir_all(golden.parent().unwrap()).unwrap();
            std::fs::write(&golden, &text).unwrap();
        }
        let recorded = std::fs::read_to_string(&golden).unwrap_or_default();
        assert!(recorded == text, "{} is not the specs as they are (run with JVMCONTRACT_BLESS=1 to write it, and read the diff against the source):\n{text}", golden.display());
        for spec in &specs {
            // A class literal is a type, not a payload value; an inherited library method (Enum.ordinal) is resolved.
            assert!(spec.effects.iter().all(|e| e.payload.iter().all(|p| !p.contains("entityClass"))), "{}: {:?}", spec.id, spec.effects);
            assert!(spec.unresolved.iter().all(|u| !u.contains("nothing followed implements it")), "{}: {:?}", spec.id, spec.unresolved);
            assert!(spec.environment.trace_bound as usize >= spec.effects.iter().filter(|e| e.kind != SiteKind::Read).count(), "{}", spec.id);
        }
        // Compared with itself, nothing is changed, removed or new: what isn't to prove is unresolved, and named.
        let obligations = compare(&specs, &specs);
        assert!(unaccounted(&specs, &obligations).is_empty(), "{module}");
        for o in &obligations {
            assert!(matches!(o.change, Change::Preserved | Change::Unresolved), "{module}: {o:#?}");
            assert!(o.change == Change::Preserved || !o.differences.is_empty(), "{module}: {o:#?}");
        }
    }
}

#[test]
fn box_office_specs_say_what_its_source_does() {
    let Some((_, ticketing)) = boxoffice_specs("ticketing-service") else { return };
    // POST /orders: the order and its payment command go into one transaction, through the outbox of the sibling
    // module `messaging`, which the walk follows; the statuses are ApiErrors' mappings and a 500 for the guard.
    let place = find(&ticketing, "POST /orders");
    assert_eq!(place.bindings.iter().map(|b| (b.input.as_str(), b.source)).collect::<Vec<_>>(), [("request", BindingSource::Body)]);
    let writes: Vec<(&str, Placement)> = place.effects.iter().filter(|e| e.kind == SiteKind::Write).map(|e| (e.target.as_str(), e.placement)).collect();
    assert_eq!(writes, [("OrderDocument", Placement::Inside), ("Outbox.Entry", Placement::Inside)]);
    let statuses: Vec<(&str, Option<u16>)> = place.statuses.iter().map(|s| (s.outcome.as_str(), s.status)).collect();
    assert_eq!(statuses, [("MethodArgumentNotValidException", Some(400)), ("returns", None), ("IllegalStateException", Some(500)), ("ConflictException", Some(409)), ("NotFoundException", Some(404))]);
    // A body that fails validation is answered 400 before the handler runs: by Spring's default, ApiErrors doesn't take it.
    assert_eq!(place.statuses[0].when, ["@NotBlank on PlaceOrder.holdId", "@NotBlank on PlaceOrder.paymentToken"]);
    assert!(place.statuses[0].by.starts_with("the framework's default"), "{:?}", place.statuses[0]);
    assert!(place.statuses[1].by.contains("ResponseEntity"), "a status the handler builds is unknown, and says why");
    assert_eq!(place.bindings[0].shape, ["PlaceOrder: record", "PlaceOrder: holdId: @NotBlank String", "PlaceOrder: paymentToken: @NotBlank String"]);
    // The hold route binds a path variable, a header and a body.
    let hold = find(&ticketing, "POST /concerts/{id}/holds");
    assert_eq!(hold.bindings.iter().map(|b| b.source).collect::<Vec<_>>(), [BindingSource::PathVariable, BindingSource::Header, BindingSource::Body]);
    // The payment events listener: the record is the payload; the inbox's dedup read and write are in the trace.
    let events = find(&ticketing, "kafka payments.events");
    assert_eq!(events.kind, EntryKind::Listener);
    assert_eq!(events.bindings[0].source, BindingSource::Payload);
    assert!(events.effects.iter().any(|e| e.kind == SiteKind::Write && e.target == "Inbox.Entry" && e.placement == Placement::Inside));
    assert!(!events.observations.contains(&Observation::Result), "a void listener returns nothing to observe");
    // The sweep is a schedule from configuration, named as unresolved.
    let sweep = find(&ticketing, "schedule fixedDelayString = \"${boxoffice.hold.sweep-interval:1s}\"");
    assert_eq!(sweep.kind, EntryKind::Schedule);
    assert!(sweep.unresolved.iter().any(|u| u.contains("comes from configuration")));

    let Some((_, messaging)) = boxoffice_specs("messaging") else { return };
    // The outbox relay sends to whatever topic the entry names: a computed target, named as unresolved.
    let relay = &messaging[0];
    let send = relay.effects.iter().find(|e| e.kind == SiteKind::Send).expect("the relay sends");
    assert_eq!((send.placement, send.payload.clone()), (Placement::Outside, vec!["topic".to_string(), "key".into(), "data".into()]));
    assert!(relay.unresolved.iter().any(|u| u.contains("KafkaTemplate.send") && u.contains("computed at run time")), "{:?}", relay.unresolved);
}

// Box Office examples 110–119: each example's change, applied to Box Office, compared with Box Office as it is, against
// what the example's recorded boundary diff says changed at the entry points.

const INSERT: &str = "effect:org/springframework/data/mongodb/core/MongoTemplate#insert(Ljava/lang/Object;)Ljava/lang/Object;";
const UPDATE_FIRST: &str = "effect:org/springframework/data/mongodb/core/MongoTemplate#updateFirst(Lorg/springframework/data/mongodb/core/query/Query;Lorg/springframework/data/mongodb/core/query/UpdateDefinition;Ljava/lang/Class;)Lcom/mongodb/client/result/UpdateResult;";
const UPDATE_MULTI: &str = "effect:org/springframework/data/mongodb/core/MongoTemplate#updateMulti(Lorg/springframework/data/mongodb/core/query/Query;Lorg/springframework/data/mongodb/core/query/UpdateDefinition;Ljava/lang/Class;)Lcom/mongodb/client/result/UpdateResult;";
const KAFKA_SEND: &str = "effect:org/springframework/kafka/core/KafkaTemplate#send(Ljava/lang/String;Ljava/lang/Object;Ljava/lang/Object;)Ljava/util/concurrent/CompletableFuture;";

/// Box Office's modules in the order they depend on each other: the first three are the jars of the others.
const BUILD_ORDER: [&str; 5] = ["contracts", "messaging", "ticketing-domain", "ticketing-service", "payment-service"];

/// The specs of Box Office's modules with entry points, with `patch` applied (none: as it is). The patched copy is
/// the sources alone; each module whose Java sources the patch changes is compiled again with javac, as its Gradle
/// build compiles it (`-parameters`), in dependency order, against the base build's class path with the recompiled
/// modules' classes in place of their jars. Every other module is as the base build left it. The walk follows the
/// sibling modules, as `observations --base` does. `None`, after `missing`, when the base build can't run here.
fn patched_specs(name: &str, patch: Option<&Path>) -> Option<BTreeMap<&'static str, Vec<EntryPointSpec>>> {
    let (root, classpath) = boxoffice()?;
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("observations-examples").join(name);
    let _ = std::fs::remove_dir_all(&dir);
    let sources = dir.join("examples/apps/boxoffice");
    let mut touched = Vec::new();
    if let Some(patch) = patch {
        copy_tree(&Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/apps/boxoffice"), &sources);
        let text = std::fs::read_to_string(patch).unwrap();
        let applied = Command::new("patch").args(["-p1", "--batch", "--silent", "--input"]).arg(patch).current_dir(&dir).status();
        let Ok(applied) = applied else {
            missing("patch (GNU patch)");
            return None;
        };
        assert!(applied.success(), "{} does not apply to examples/apps/boxoffice", patch.display());
        touched = BUILD_ORDER.iter().copied().filter(|m| text.lines().any(|l| l.starts_with(&format!("+++ b/examples/apps/boxoffice/{m}/src/main/java/")))).collect();
    }
    let classes = |m: &str| if touched.contains(&m) { dir.join(m).join("classes") } else { root.join(m).join("build/classes/java/main") };
    let mut entries: Vec<PathBuf> = std::env::split_paths(classpath).collect();
    for m in BUILD_ORDER {
        if touched.contains(&m) {
            for e in entries.iter_mut().filter(|e| e.starts_with(root.join(m))) {
                *e = classes(m);
            }
            let files = java_files(&sources.join(m).join("src/main/java"));
            let cp = std::env::join_paths(&entries).unwrap();
            let out = Command::new("javac").args(["-parameters", "-proc:none", "-nowarn", "-encoding", "UTF-8", "-d"]).arg(classes(m)).arg("-cp").arg(&cp).args(&files).output().unwrap();
            assert!(out.status.success(), "{name}: javac {m}: {}", String::from_utf8_lossy(&out.stderr));
        }
    }
    let siblings: Vec<&PathBuf> = entries.iter().filter(|e| e.starts_with(root) || e.starts_with(&dir)).collect();
    let mut out = BTreeMap::new();
    for (module, _) in MODULES {
        let mut cp = ClassPath::new();
        cp.add(&classes(module)).unwrap();
        let own: std::collections::BTreeSet<String> = cp.application_class_names().unwrap().into_iter().collect();
        let mut followed = own.clone();
        for e in &entries {
            cp.add(e).unwrap();
        }
        for e in &siblings {
            let mut sibling = ClassPath::new();
            sibling.add(e).unwrap();
            followed.extend(sibling.application_class_names().unwrap());
        }
        out.insert(module, analyse(&cp.with_default_jdk(), Some(&own), Some(&followed)).unwrap());
    }
    Some(out)
}

/// What each example's change does at the entry points, by its recorded boundary diff: every obligation that is not
/// preserved-to-prove or unresolved, as module, entry point, observation and change. Every other observation of
/// every module stays preserved-to-prove or unresolved.
const EXPECTED: [(&str, &[(&str, &str, &str, Change)]); 10] = [
    // An Idempotency-Key header added to POST /orders and @Valid dropped: a new input, and the 400 for a body that
    // fails validation gone.
    ("110", &[("ticketing-service", "POST /orders", "inputs", Change::Changed), ("ticketing-service", "POST /orders", "status", Change::Changed)]),
    // A new event with no @JsonSubTypes entry: its type id is inside the encoded string the outbox stores, a payload
    // value, which no entry-point spec observes statically (the boundary contract's wire block does). The effect
    // stays to prove, which needs the payload values.
    ("111", &[]),
    // A configuration key nothing reads: configuration values are not observed by an entry-point spec.
    ("112", &[]),
    // A nested Billing record without @Valid: the body's wire shape changes (with the unchecked constraints named),
    // and a body without billing is now answered 400.
    ("113", &[("ticketing-service", "POST /orders", "inputs", Changed), ("ticketing-service", "POST /orders", "status", Changed)]),
    // @Cacheable with no @EnableCaching: inert, so every read still happens, and a read is a modeled call, not an
    // observation. Nothing changes, which is right: the defect is a cache that doesn't work, not a regression.
    ("114", &[]),
    // A stored field renamed: the hold's insert snapshots another path. (The query strings that still name the old
    // field are reads, which the spec models as calls, not observations: the stored-types block checks them.)
    ("115", &[("ticketing-service", "POST /concerts/{id}/holds", INSERT, Changed)]),
    // GET /holds/{id} now writes the hold and its seats: two attempts the old trace never makes.
    ("116", &[("ticketing-service", "GET /holds/{id}", UPDATE_FIRST, New), ("ticketing-service", "GET /holds/{id}", UPDATE_MULTI, New)]),
    // The outbox write replaced by a send inside the order's transaction.
    ("117", &[("ticketing-service", "POST /orders", INSERT, Changed), ("ticketing-service", "POST /orders", KAFKA_SEND, New)]),
    // The route's variable renamed and the parameter not: a 500 on every request, so nothing the handler does shows.
    ("118", &[("ticketing-service", "GET /holds/{id}", "result", Changed), ("ticketing-service", "GET /holds/{id}", "exception", Changed), ("ticketing-service", "GET /holds/{id}", "status", Changed)]),
    // A new exception no handler maps in place of the ConflictException: the route's 409 is gone.
    ("119", &[("ticketing-service", "POST /orders", "status", Changed)]),
];
use Change::{Changed, New};

fn differences<'a>(obligations: &'a [Obligation], entry: &str, observation: &str) -> &'a [String] {
    &of(obligations, entry, observation).differences
}

fn has(lines: &[String], text: &str) -> bool {
    lines.iter().any(|l| l.contains(text))
}

#[test]
fn box_office_examples_compare_as_their_boundary_diffs_say() {
    let Some(base) = patched_specs("base", None) else { return };
    // The base as this test builds it is the base as the command analyses it.
    for (module, _) in MODULES {
        let Some((_, specs)) = boxoffice_specs(module) else { return };
        assert_eq!(base[module], specs, "{module}");
    }
    let examples = Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples");
    for (number, expected) in EXPECTED {
        let folder = std::fs::read_dir(&examples).unwrap().map(|e| e.unwrap().path()).find(|p| p.file_name().unwrap().to_string_lossy().starts_with(&format!("{number}-"))).unwrap();
        let Some(after) = patched_specs(number, Some(&folder.join("change.patch"))) else { return };
        let mut found = Vec::new();
        let mut all = BTreeMap::new();
        for (module, _) in MODULES {
            let obligations = compare(&base[module], &after[module]);
            assert!(unaccounted(&base[module], &obligations).is_empty(), "{number} {module}: {:?}", unaccounted(&base[module], &obligations));
            found.extend(obligations.iter().filter(|o| !matches!(o.change, Change::Preserved | Change::Unresolved)).map(|o| (module, o.entry.clone(), o.observation.clone(), o.change)));
            all.insert(module, obligations);
        }
        let want: Vec<(&str, String, String, Change)> = expected.iter().map(|(m, e, o, c)| (*m, e.to_string(), o.to_string(), *c)).collect();
        assert_eq!(found, want, "{number}: {:#?}", all);
        let t = &all["ticketing-service"];
        match number {
            "110" => {
                assert!(has(differences(t, "POST /orders", "inputs"), "a new input Idempotency-Key: String (header)"));
                assert!(has(differences(t, "POST /orders", "inputs"), "! constraints on PlaceOrder are not checked: no @Valid on request"));
                assert!(has(differences(t, "POST /orders", "status"), "the old build answers MethodArgumentNotValidException with 400"), "{t:#?}");
            }
            "111" | "112" | "114" => assert_eq!(base, after, "{number}: nothing an entry-point spec observes changed"),
            "113" => {
                assert!(has(differences(t, "POST /orders", "inputs"), "PlaceOrder: billing: ! constraints on Billing are not checked: no @Valid on billing"));
                assert!(has(differences(t, "POST /orders", "status"), "now also for a body that fails @NotNull on PlaceOrder.billing"), "{t:#?}");
            }
            "115" => {
                let d = differences(t, "POST /concerts/{id}/holds", INSERT);
                assert!(has(d, "no longer snapshots objectToSave.idempotencyKey") && has(d, "now also snapshots objectToSave.requestKey"), "{d:?}");
            }
            "116" => {
                let new = of(t, "GET /holds/{id}", UPDATE_FIRST);
                assert!(has(&new.differences, "writes HoldDocument, outside a transaction") && new.needs.contains("the old build's ordered trace has no such attempt"), "{new:#?}");
            }
            "117" => {
                let d = differences(t, "POST /orders", INSERT);
                assert!(has(d, "the old build writes Outbox.Entry by it (inside its transaction), the new one doesn't"), "{d:?}");
                assert!(has(d, "attempts instead, which the old one doesn't: it sends to payments.commands, inside its transaction"), "{d:?}");
            }
            "118" => {
                let result = of(t, "GET /holds/{id}", "result");
                assert_eq!(result.new_entry.as_deref(), Some("GET /holds/{holdId}"));
                assert!(result.differences[0].contains("answers every request before the handler runs, MissingPathVariableException with 500"), "{result:#?}");
            }
            "119" => assert!(has(differences(t, "POST /orders", "status"), "the old build answers 409 for an exception it throws; no exception of the new build is answered 409"), "{t:#?}"),
            _ => {}
        }
    }
}
