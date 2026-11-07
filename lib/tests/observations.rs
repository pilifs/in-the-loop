//! Observation specs (`jvmcontract observations`, `lib/src/observations.rs`) on the joint example of the foundations
//! loop (`lib/tests/fixtures/foundations/`), checked field by field, and on every entry point of Box Office
//! (`examples/apps/boxoffice/`), checked against golden text and the facts read off its source.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::{Mutex, OnceLock};

use jvmcontract::spec::observe::{self, BindingSource, EntryKind, EntryPointSpec, Placement, SiteKind};
use jvmcontract::spec::{Derivation, Observation, OrderPolicy};

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
    assert_eq!(statuses, [("returns", None), ("IllegalStateException", Some(500)), ("ConflictException", Some(409)), ("NotFoundException", Some(404))]);
    assert!(place.statuses[0].by.contains("ResponseEntity"), "a status the handler builds is unknown, and says why");
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
