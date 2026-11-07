//! Observation specs (`jvmcontract observations`, `lib/src/observations.rs`) on the joint example of the foundations
//! loop (`lib/tests/fixtures/foundations/`): what a consumer of each entry point observes, checked field by field.

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
