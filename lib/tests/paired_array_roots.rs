use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::{equivalence, Engine, Verdict};
use serde_json::{json, Value};

fn example() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().join("examples/197-shared-int-array-poststates")
}

fn classes() -> Option<&'static [PathBuf; 2]> {
    static BUILDS: OnceLock<Option<[PathBuf; 2]>> = OnceLock::new();
    BUILDS.get_or_init(|| {
        if Command::new("javac").arg("-version").output().is_err() { return None; }
        Some(["baseline", "alternative"].map(|version| {
            let dir = Path::new(env!("CARGO_TARGET_TMPDIR")).join("paired-roots").join(version);
            let source = example().join(version).join("arrays/Update.java");
            assert!(Command::new("javac").args(["-proc:none", "-parameters", "-g", "--release", "21", "-d"]).arg(&dir).arg(source).status().unwrap().success());
            dir
        }))
    }).as_ref()
}

fn check(claim: &str) -> Option<equivalence::Outcome> {
    let [before, after] = classes()?;
    let bytes = std::fs::read(example().join("claims").join(format!("{claim}.json"))).unwrap();
    let frozen: Value = serde_json::from_slice(&bytes).unwrap();
    let mut options = equivalence::Options::new(before, after, "arrays.Update#apply");
    options.engine = Engine::Native;
    options.jbmc = "/nonexistent/jbmc".into();
    options.timeout_seconds = 6;
    options.max_array_length = frozen["bounds"]["maxArrayLength"].as_u64().unwrap() as u32;
    options.unwind = frozen["bounds"]["unwind"].as_u64().unwrap() as u32;
    options.assume = Some(frozen["assume"].as_str().unwrap().into());
    options.nullable = serde_json::from_value(frozen["nullable"].clone()).unwrap();
    options.may_alias = vec![("left".into(), "right".into())];
    options.selected_observations = serde_json::from_value(frozen["observations"].clone()).unwrap();
    let outcome = equivalence::run(&options).unwrap();
    let statement = outcome.stated.as_ref().unwrap();
    assert_eq!(statement.spec.as_ref().unwrap().observations, options.selected_observations);
    assert_eq!(statement.domain.may_alias, [options.nullable]);
    let check = mapping(&outcome.work, after, &outcome.work.join("pair"), claim);
    assert!(check.status.success(), "{}", String::from_utf8_lossy(&check.stderr));
    let expected = match claim { "return-only" => "71 0", "right-root" => "71 3", "both-roots" => "71 21", _ => unreachable!() };
    assert_eq!(String::from_utf8_lossy(&check.stdout).trim(), expected);
    Some(outcome)
}

fn mapping(work: &Path, after: &Path, pair: &Path, claim: &str) -> std::process::Output {
    let cp = std::env::join_paths([pair, after, &work.join("before-classes")]).unwrap();
    Command::new("java").arg("-cp").arg(cp).arg(example().join("controls/CheckMapping.java")).arg(claim).output().unwrap()
}

#[test]
fn return_only_agrees_for_nullable_shared_or_distinct_arrays() {
    jvmcontract::tool_tier!();
    let Some(result) = check("return-only") else { return };
    assert_eq!(result.verdict, Verdict::Verified, "{}", result.output);
    assert!(result.vacuous.is_none());
}

#[test]
fn the_right_root_witness_replays_the_shared_array_and_reports_its_cells() {
    jvmcontract::tool_tier!();
    let Some(result) = check("right-root") else { return };
    assert_eq!(result.verdict, Verdict::Violation, "{}", result.output);
    let witness = result.counterexample.unwrap();
    assert_eq!(witness.inputs[1].value, Some(json!({"same": 0})));
    assert_eq!(witness.differs, ["array:right"]);
    assert_eq!(witness.replay_observations[0].id(), "array:right");
    assert!(witness.before.starts_with("array:right=[1"), "{}", witness.before);
    assert!(witness.after.starts_with("array:right=[0"), "{}", witness.after);
    assert!(result.replay.is_some_and(|r| r.by == "jvm" && r.reproduced));
}

#[test]
fn the_both_root_witness_observes_each_requested_projection_on_the_jvm() {
    jvmcontract::tool_tier!();
    let Some(result) = check("both-roots") else { return };
    assert_eq!(result.verdict, Verdict::Violation, "{}", result.output);
    let witness = result.counterexample.unwrap();
    assert_eq!(witness.replay_observations.iter().map(|o| o.id()).collect::<Vec<_>>(), ["array:left", "array:right"]);
    assert!(witness.differs.iter().any(|s| s == "array:left"));
    assert!(result.replay.is_some_and(|r| r.by == "jvm" && r.reproduced));
}

#[test]
fn a_cloned_alias_dropped_comparison_or_swapped_observer_fails_the_finite_check() {
    jvmcontract::tool_tier!();
    let Some(result) = check("right-root") else { return };
    let after = &classes().unwrap()[1];
    let original = std::fs::read_to_string(result.statement.as_ref().unwrap()).unwrap();
    let compare = "return sameCells(a1, b1);";
    let mutations = [
        original.replace("? a0 : data", "? a0.clone() : data").replace("? b0 : data", "? b0.clone() : data"),
        original.replace(compare, "return true;"),
        original.replace(compare, "return sameCells(a0, b0);"),
    ];
    for (index, mutant) in mutations.into_iter().enumerate() {
        assert_ne!(mutant, original);
        let dir = result.work.join(format!("control-{index}"));
        std::fs::create_dir(&dir).unwrap();
        let source = dir.join("RegressionPair.java");
        std::fs::write(&source, mutant).unwrap();
        let cp = std::env::join_paths([after, &result.work.join("before-classes")]).unwrap();
        assert!(Command::new("javac").args(["-proc:none", "-cp"]).arg(cp).arg("-d").arg(&dir).arg(source).status().unwrap().success());
        let observed = mapping(&result.work, after, &dir, "right-root");
        assert!(!observed.status.success() && String::from_utf8_lossy(&observed.stderr).contains("AssertionError"), "{observed:?}");
    }
}
