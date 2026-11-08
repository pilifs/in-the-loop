//! A receiver whose constructor takes dependencies (Phase 5 of `llm-dlc/loops/application-core.md`): each
//! dependency, an application interface, is passed null by the regression check (`equivalence`, so also the heap
//! check of a planned claim) and the property check (`prove`), which hold only of a target that never reaches one
//! (`construction::dependency_reached`); one that does is refused by name, before any proof or cache lookup. The
//! quote family's `QuoteService#fee` is such a target (`tests/application_core_joint.rs`). Each part has a correct
//! case, a planted defect replayed on a JVM, a named boundary, and its cached evidence invalidated.

use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::spec::cache::Reuse;
use jvmcontract::{equivalence, property, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";

fn tmp(part: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("dependencies").join(part)
}

/// Compiles `sources` (path under the package root, Java text) into a fresh directory named `name`.
fn compile(name: &str, sources: &[(&str, String)]) -> PathBuf {
    let root = tmp(name);
    let _ = std::fs::remove_dir_all(&root);
    let src = root.join("src");
    let mut files = Vec::new();
    for (path, text) in sources {
        let file = src.join(path);
        std::fs::create_dir_all(file.parent().unwrap()).unwrap();
        std::fs::write(&file, text).unwrap();
        files.push(file);
    }
    let out = root.join("classes");
    let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out).args(&files).status().expect("the tests need javac");
    assert!(status.success(), "{name} compiles");
    out
}

const CLOCK: &str = "package deps;\npublic interface Clock { long now(); }\n";

/// A timer with a start and a clock it was given; `body` is `since`'s body, a package-private helper as the quote
/// service's `fee` is, and `extra` more members.
fn timer(name: &str, body: &str, extra: &str) -> PathBuf {
    let timer = format!(
        "package deps;\npublic class Timer {{\n    private final long start;\n    private final Clock clock;\n    public Timer(long start, Clock clock) {{ this.start = start; this.clock = clock; }}\n    long since(long t) {{\n        {body}\n    }}\n{extra}}}\n"
    );
    compile(name, &[("deps/Clock.java", CLOCK.to_string()), ("deps/Timer.java", timer)])
}

fn options(name: &str, before: &Path, after: &Path, target: &str) -> equivalence::Options {
    let mut options = equivalence::Options::new(before, after, target);
    options.engine = jvmcontract::Engine::Native;
    options.jbmc = NO_JBMC.into();
    let work = tmp(&format!("work-{name}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    options
}

fn regression(name: &str, before: &Path, after: &Path, target: &str) -> equivalence::Outcome {
    equivalence::run(&options(name, before, after, target)).unwrap()
}

fn prove(name: &str, classes: &Path, target: &str, assume: Option<&str>, assert: &str) -> property::Outcome {
    let mut options = property::Options::new(&[classes.to_path_buf()], target);
    options.engine = jvmcontract::Engine::Native;
    options.jbmc = NO_JBMC.into();
    options.assume = assume.map(str::to_string);
    options.assert = Some(assert.into());
    let work = tmp(&format!("work-{name}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    property::run(&options).unwrap()
}

/// The correct case and the defect: a rewrite of `since` that never reaches the clock is proved over every start,
/// the clock passed null, and the domain says so; an off-by-one is refuted, and its witness, whose receiver is
/// made with the null clock, is run on a JVM, which can call the package-private target. The property check makes
/// the same receiver.
#[test]
fn a_target_that_never_reaches_its_dependencies_is_checked_with_each_null() {
    let before = timer("before", "return t - start;", "");
    let after = timer("after", "long d = t;\n        d -= start;\n        return d;", "");
    let o = regression("rewrite", &before, &after, "deps.Timer#since");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let domain = o.domain.clone().unwrap_or_default();
    assert!(domain.contains("clock: null, a dependency of deps.Clock"), "the domain names the null dependency: {domain}");

    let defect = timer("off-by-one", "return t - start + 1;", "");
    let o = regression("off-by-one", &before, &defect, "deps.Timer#since");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.input.contains("new Timer(") && c.input.contains(", null)"), "the witness makes the receiver with a null clock: {}", c.input);
    let replay = o.replay.as_ref().expect("replayed");
    assert!(replay.reproduced, "{}", o.output);
    assert!(o.output.contains("run on a JVM") && o.output.contains("where the harness fails on it too"), "an object made by its constructor is run on a JVM, which calls the package-private target: {}", o.output);

    let o = prove("property", &after, "deps.Timer#since", Some("t >= this.start && this.start >= 0"), "result >= 0");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let o = prove("property-defect", &defect, "deps.Timer#since", Some("t >= this.start && this.start >= 0"), "result == t - this.start");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
}

/// The named boundary: a target that calls a method on a dependency, reads the field that holds it, or hands it on
/// to a helper that does is refused by name in either version and in the property check, since a null stands for
/// no object a run could have; so is a dependency that is no interface, and a plan whose dependency is misnamed.
#[test]
fn a_target_that_reaches_a_dependency_is_refused_by_name() {
    let before = timer("boundary-before", "return t - start;", "");
    let calls = timer("calls", "return clock.now() - start;", "");
    let o = regression("calls", &before, &calls, "deps.Timer#since");
    assert_eq!(o.verdict, Verdict::Unverifiable);
    let problem = o.problem.unwrap_or_default();
    assert!(problem.contains("in the new version") && problem.contains("this.clock, a deps.Clock") && problem.contains("deps.Clock.now"), "{problem}");
    let o = regression("calls-before", &calls, &before, "deps.Timer#since");
    assert!(o.problem.as_deref().unwrap_or_default().contains("in the previous version"), "{}", o.output);

    let tests = timer("tests", "return clock == null ? t - start : 0;", "");
    let o = regression("tests", &before, &tests, "deps.Timer#since");
    assert!(o.problem.as_deref().unwrap_or_default().contains("uses the field deps.Timer.clock, which holds the dependency this.clock"), "{}", o.output);

    let handed = timer("handed", "return read(clock) - start;", "    static long read(Clock c) { return c.now(); }\n");
    let o = regression("handed", &before, &handed, "deps.Timer#since");
    assert!(o.problem.as_deref().unwrap_or_default().contains("reaches"), "{}", o.output);

    let o = prove("calls-property", &calls, "deps.Timer#since", None, "true");
    assert_eq!(o.verdict, Verdict::Unverifiable);
    assert!(o.problem.as_deref().unwrap_or_default().contains("this.clock, a deps.Clock"), "{}", o.output);

    let abstract_clock = compile("abstract", &[
        ("deps/Clock.java", "package deps;\npublic abstract class Clock { public abstract long now(); }\n".into()),
        ("deps/Timer.java", "package deps;\npublic class Timer {\n    private final long start;\n    private final Clock clock;\n    public Timer(long start, Clock clock) { this.start = start; this.clock = clock; }\n    long since(long t) { return t - start; }\n}\n".into()),
    ]);
    let o = regression("abstract", &abstract_clock, &abstract_clock, "deps.Timer#since");
    assert!(o.problem.as_deref().unwrap_or_default().contains("deps.Clock is abstract"), "{}", o.output);

    // A plan names each dependency by its path from the root, as a leaf.
    let plan = |path: &str, class: &str| -> jvmcontract::construction::Plans {
        let one = serde_json::json!({
            "nodes": [{"id": 0, "class": "deps.Timer", "maker": {"kind": "constructor", "descriptor": "(JLdeps/Clock;)V"}, "args": [
                {"kind": "leaf", "path": "this.start", "type": "long"},
                {"kind": "dependency", "path": path, "class": class}
            ]}],
            "roots": [{"name": "this", "value": {"kind": "node", "id": 0}}],
            "restrictions": ["the clock is a dependency, passed null"],
            "bounds": {"nodes": 1, "max_array_length": 4, "setup_calls": 0}
        });
        serde_json::from_value(serde_json::json!({"before": one, "after": one})).unwrap()
    };
    let after = timer("plan-after", "long d = t;\n        d -= start;\n        return d;", "");
    let mut o = options("plan", &before, &after, "deps.Timer#since");
    o.plan = Some(plan("this.clock", "deps.Clock"));
    let verified = equivalence::run(&o).unwrap();
    assert_eq!(verified.verdict, Verdict::Verified, "{}", verified.output);
    let mut o = options("plan-misnamed", &before, &after, "deps.Timer#since");
    o.plan = Some(plan("this.watch", "deps.Clock"));
    let refused = equivalence::run(&o).unwrap();
    assert!(refused.problem.as_deref().unwrap_or_default().contains("which the check names this.clock"), "{}", refused.output);
    let mut o = options("plan-not-interface", &before, &after, "deps.Timer#since");
    o.plan = Some(plan("this.clock", "deps.Timer"));
    let refused = equivalence::run(&o).unwrap();
    assert!(refused.problem.as_deref().unwrap_or_default().contains("the constructor takes a deps.Clock"), "{}", refused.output);
}

/// The cached evidence: a proof over the null clock is reused by its exact rerun; a build whose target now reaches
/// the clock is refused before the lookup, never answered by the stored proof; and an edit of the constructor,
/// which stores the clock, is another claim, proved again.
#[test]
fn a_cached_proof_over_a_null_dependency_is_never_reused_once_the_target_reaches_it() {
    let cache = tmp("cache");
    let _ = std::fs::remove_dir_all(&cache);
    let before = timer("cache-before", "return t - start;", "");
    let after = timer("cache-after", "long d = t;\n        d -= start;\n        return d;", "");
    let run = |name: &str, after: &Path| {
        let mut o = options(name, &before, after, "deps.Timer#since");
        o.cache = Some(cache.clone());
        equivalence::run(&o).unwrap()
    };
    let cold = run("cache-cold", &after);
    assert_eq!(cold.verdict, Verdict::Verified, "{}", cold.output);
    assert!(cold.reuse.is_none(), "{:?}", cold.reuse);
    let rerun = run("cache-rerun", &after);
    assert_eq!(rerun.verdict, Verdict::Verified, "{}", rerun.output);
    let Some(Reuse::Exact { key, .. }) = &rerun.reuse else { panic!("the exact rerun is the stored proof: {:?}", rerun.reuse) };

    let reaches = timer("cache-reaches", "long d = t;\n        d -= start;\n        return d + (clock == null ? 0 : 1);", "");
    let o = run("cache-reaches", &reaches);
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.reuse.is_none() && o.problem.as_deref().unwrap_or_default().contains("reaches a dependency"), "{}", o.output);

    let edited = compile("cache-edited", &[
        ("deps/Clock.java", CLOCK.to_string()),
        ("deps/Timer.java", "package deps;\npublic class Timer {\n    private final long start;\n    private final Clock clock;\n    public Timer(long start, Clock clock) { this.start = start; this.clock = null; }\n    long since(long t) {\n        long d = t;\n        d -= start;\n        return d;\n    }\n}\n".into()),
    ]);
    let o = run("cache-edited", &edited);
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    match &o.reuse {
        None => {}
        Some(Reuse::Exact { key: k, .. }) => assert_ne!(k, key, "an edit of the constructor is another claim"),
        Some(other) => panic!("{other:?}"),
    }
    assert!(o.reuse.is_none(), "an edit of the constructor alone is proved again: {:?}", o.reuse);
}
