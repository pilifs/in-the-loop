//! The objects stream's own tests (`llm-dlc/loops/application-core-objects.md`), beside the shared contract
//! `tests/application_core.rs`. O1: an ordinary receiver, an object made by its constructor and named `this`,
//! through the regression check (`equivalence`) and the property check (`prove`), on the native engine with no
//! JBMC. Each capability has a correct case, a planted defect replayed, and a named unsupported boundary.

use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::{equivalence, property, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";

/// Compiles `sources` (path under the package root, Java text) into a fresh directory named `name`.
fn compile(name: &str, sources: &[(&str, &str)]) -> PathBuf {
    let root = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects").join(name);
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

fn regression(name: &str, before: &Path, after: &Path, target: &str) -> equivalence::Outcome {
    let mut options = equivalence::Options::new(before, after, target);
    options.engine = jvmcontract::Engine::Native;
    options.jbmc = NO_JBMC.into();
    let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work").join(name);
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    equivalence::run(&options).unwrap()
}

fn prove(name: &str, classes: &Path, target: &str, assume: Option<&str>, assert: &str) -> property::Outcome {
    let mut options = property::Options::new(&[classes.to_path_buf()], target);
    options.engine = jvmcontract::Engine::Native;
    options.jbmc = NO_JBMC.into();
    options.assume = assume.map(str::to_string);
    options.assert = Some(assert.into());
    let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work").join(name);
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    property::run(&options).unwrap()
}

const COUNTER: &str = r#"package counters;

/** A counter: an ordinary receiver of a primitive state, made by its constructor. */
public class Counter {
    private final int step;
    private int count;

    public Counter(int step) {
        if (step < 1) {
            throw new IllegalArgumentException("step below 1");
        }
        this.step = step;
    }

    /** Adds n steps, the setup-free mutation of the receiver. */
    public void add(int n) {
        if (n < 0 || n > 4) {
            throw new IllegalArgumentException("n out of range");
        }
        count += n * step;
    }

    /** The counter itself, for chaining: the caller keeps the same object. */
    public Counter self() {
        return this;
    }

    public int count() {
        return count;
    }
}
"#;

fn counter(name: &str, edit: impl Fn(&str) -> String) -> PathBuf {
    compile(name, &[("counters/Counter.java", &edit(COUNTER))])
}

/// The regression check makes an ordinary receiver by its constructor, compares its fields as the call leaves them,
/// and replays a difference on a JVM: a rewrite of `add` is verified, and one that adds a step too many once is
/// refuted on the receiver's field alone (a void method).
#[test]
fn o1_a_receivers_mutation_is_compared_and_replayed_on_a_jvm() {
    let before = counter("counter-before", |s| s.to_string());
    let after = counter("counter-after", |s| s.replace("count += n * step;", "for (int i = 0; i < n; i++) { count += step; }"));
    let o = regression("add-after", &before, &after, "counters.Counter#add");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.domain.as_deref().unwrap_or_default().contains("this: a Counter made by its constructor"), "the domain names the receiver: {:?}", o.domain);

    let defect = counter("counter-defect", |s| s.replace("count += n * step;", "count += n * step + (n == 3 ? 1 : 0);"));
    let o = regression("add-defect", &before, &defect, "counters.Counter#add");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let replay = o.replay.as_ref().expect("a replay");
    assert!(replay.reproduced, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.jvm.is_some(), "a witness over a constructor-made receiver is run on a JVM too, where the harness fails on it: {}", o.output);
    assert!(c.differs.iter().any(|d| d.starts_with("field:this")), "the receiver's field differs: {:?}", c.differs);
    assert!(c.call.receiver.is_some() && !c.call.is_static, "the witness's call is on its receiver: {:?}", c.call);
}

/// `this` is a named root of the identity relations: a method that hands back its receiver, rewritten to hand back
/// a copy, is refuted on `result == this` alone, the copy's fields being the same.
#[test]
fn o1_a_receiver_returned_as_a_copy_is_refuted_on_identity() {
    let before = counter("self-before", |s| s.to_string());
    let copy = counter("self-copy", |s| s.replace("        return this;\n", "        Counter c = new Counter(step);\n        c.count = count;\n        return c;\n"));
    let o = regression("self-copy", &before, &copy, "counters.Counter#self");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.differs.iter().any(|d| d.contains("identity") && d.contains("this")), "the identity of the result and the receiver differs: {:?}", c.differs);
    assert!(o.replay.as_ref().is_some_and(|r| r.reproduced), "{}", o.output);
    let same = counter("self-same", |s| s.replace("        return this;\n", "        Counter me = this;\n        return me;\n"));
    assert_eq!(regression("self-same", &before, &same, "counters.Counter#self").verdict, Verdict::Verified);
}

/// The property check calls an instance method on its receiver, whose fields the assumption and the assertion read
/// as `this.f`: a property of `count` right after construction is proved, and a false one refuted with a witness.
#[test]
fn o1_a_property_over_an_ordinary_receiver() {
    let classes = counter("property", |s| s.to_string());
    let o = prove("count-zero", &classes, "counters.Counter#count", None, "result == 0");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let o = prove("add-reads-this", &classes, "counters.Counter#self", Some("this.step > 1"), "result.step > 1 && result.count == 0");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let o = prove("count-step", &classes, "counters.Counter#add", Some("n >= 0 && n <= 4"), "this.count < 3 * this.step");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.input.contains("this="), "the witness names its receiver: {}", c.input);
}

/// A receiver outside what a check makes is refused by name: a dependency among its constructor's arguments that
/// the target reaches (one it never reaches is passed null since the merge, `tests/dependencies.rs`), and several
/// constructors, a choice no plain check makes.
#[test]
fn o1_a_receiver_outside_the_construction_is_refused_by_name() {
    let dependency = compile("dependency", &[
        ("deps/Clock.java", "package deps;\npublic interface Clock { long now(); }\n"),
        ("deps/Timer.java", "package deps;\npublic class Timer {\n    private final long start;\n    private final Clock clock;\n    public Timer(long start, Clock clock) { this.start = start; this.clock = clock; }\n    public long since(long t) { return t - start; }\n    public long elapsed() { return clock.now() - start; }\n}\n"),
    ]);
    let o = regression("dependency", &dependency, &dependency, "deps.Timer#since");
    assert_eq!(o.verdict, Verdict::Verified, "a dependency the target never reaches is passed null: {}", o.output);
    let o = regression("dependency", &dependency, &dependency, "deps.Timer#elapsed");
    assert_eq!(o.verdict, Verdict::Unverifiable);
    let problem = o.problem.unwrap();
    assert!(problem.contains("reaches a dependency") && problem.contains("this.clock, a deps.Clock"), "{problem}");
    let o = prove("dependency", &dependency, "deps.Timer#elapsed", None, "true");
    assert!(o.problem.as_deref().unwrap_or_default().contains("this.clock, a deps.Clock"), "{}", o.output);

    let several = counter("several", |s| s.replace("    /** Adds n steps", "    public Counter() {\n        this(1);\n    }\n\n    /** Adds n steps"));
    let o = regression("several", &several, &several, "counters.Counter#count");
    assert_eq!(o.verdict, Verdict::Unverifiable);
    let problem = o.problem.unwrap();
    assert!(problem.contains("has 2 constructors") && !problem.contains("builds it"), "{problem}");

    let plain = counter("before-arguments", |s| s.to_string());
    let mut options = equivalence::Options::new(&plain, &plain, "counters.Counter#add");
    options.engine = jvmcontract::Engine::Native;
    options.jbmc = NO_JBMC.into();
    options.before_arguments = Some("n".into());
    options.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work/before-arguments"));
    let o = equivalence::run(&options).unwrap();
    assert!(o.problem.as_deref().unwrap_or_default().contains("--before-arguments with a receiver made by its constructor"), "{}", o.output);
    let mut options = property::Options::new(&[plain.clone()], "counters.Counter#count");
    options.engine = jvmcontract::Engine::Native;
    options.jbmc = NO_JBMC.into();
    options.assert = Some("result >= 0".into());
    options.nullable = vec!["this".into()];
    options.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work/nullable-this"));
    let o = property::run(&options).unwrap();
    assert!(o.problem.as_deref().unwrap_or_default().contains("--nullable this: the receiver of an instance method is never null"), "{}", o.output);
}

/// The cached evidence of a check over an ordinary receiver is tied to the receiver's construction: an exact rerun
/// reuses the proof, and an edit of the receiver's constructor alone, the method compared unchanged, is a claim of
/// its own that the cache doesn't answer.
#[test]
fn o1_a_receivers_constructor_is_part_of_the_cached_claim() {
    let cache = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-cache");
    let _ = std::fs::remove_dir_all(&cache);
    let before = counter("cache-before", |s| s.to_string());
    let after = counter("cache-after", |s| s.replace("count += n * step;", "count = count + step * n;"));
    let edited = counter("cache-edited", |s| s.replace("count += n * step;", "count = count + step * n;").replace("        this.step = step;\n", "        this.step = step;\n        this.count = 0;\n"));
    let run = |name: &str, after: &Path| {
        let mut options = equivalence::Options::new(&before, after, "counters.Counter#add");
        options.engine = jvmcontract::Engine::Native;
        options.jbmc = NO_JBMC.into();
        options.cache = Some(cache.clone());
        let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work").join(name);
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        equivalence::run(&options).unwrap()
    };
    let cold = run("cache-cold", &after);
    assert_eq!(cold.verdict, Verdict::Verified, "{}", cold.output);
    assert!(cold.reuse.is_none());
    let rerun = run("cache-rerun", &after);
    assert_eq!(rerun.verdict, Verdict::Verified, "{}", rerun.output);
    assert!(rerun.reuse.is_some(), "the exact rerun reuses the proof: {}", rerun.output);
    let other = run("cache-edited", &edited);
    assert_eq!(other.verdict, Verdict::Verified, "{}", other.output);
    assert!(other.reuse.is_none(), "another constructor of the receiver is another claim: {}", other.output);
}

/// The regression cache's key roots each version's closure at every constructor the harness calls, the inner
/// objects' included (`Layout::construction_roots`), not only a made object's own. A rewrite of `get` is verified
/// and stored; a build that also changes `Inner`'s constructor, so that `get` gives one more, is another claim and
/// refuted. It reused the stored proof before the reuse stream's fix (`qssovxor`).
#[test]
fn an_inner_objects_constructor_is_part_of_the_cached_claim() {
    let cache = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-cache-inner");
    let _ = std::fs::remove_dir_all(&cache);
    let inner = |v: &str| format!("package boxes;\npublic class Inner {{\n    final int v;\n    public Inner(int v) {{ this.v = {v}; }}\n}}\n");
    let get = "package boxes;\npublic class Box {\n    public static int get(Wrap w) { return w.in.v + w.k; }\n}\n";
    let wrap = "package boxes;\npublic class Wrap {\n    final Inner in;\n    final int k;\n    public Wrap(Inner in, int k) { this.in = in; this.k = k; }\n}\n";
    let rewritten = get.replace("w.in.v + w.k", "w.k + w.in.v");
    let before = compile("inner-before", &[("boxes/Inner.java", &inner("v")), ("boxes/Wrap.java", wrap), ("boxes/Box.java", get)]);
    let same = compile("inner-same", &[("boxes/Inner.java", &inner("v")), ("boxes/Wrap.java", wrap), ("boxes/Box.java", &rewritten)]);
    let wrong = compile("inner-wrong", &[("boxes/Inner.java", &inner("v + 1")), ("boxes/Wrap.java", wrap), ("boxes/Box.java", &rewritten)]);
    let run = |name: &str, after: &Path| {
        let mut options = equivalence::Options::new(&before, after, "boxes.Box#get");
        options.engine = jvmcontract::Engine::Native;
        options.jbmc = NO_JBMC.into();
        options.cache = Some(cache.clone());
        let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work").join(name);
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        equivalence::run(&options).unwrap()
    };
    assert_eq!(run("inner-same", &same).verdict, Verdict::Verified);
    let o = run("inner-wrong", &wrong);
    assert!(o.reuse.is_none(), "another inner constructor is another claim: {}", o.output);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
}

/// O2's claim roots: a setup method is a root of the claim, as a constructor is. A rewrite of `count` after one
/// `add` is verified under `--cache`; a build that changes only the setup method `add`, so that a history of
/// `add(4)` counts one more, is another claim, never answered by the cache, and refuted with its history, which the
/// typed witness carries. The exact reruns of both are answered by the cache: the claim key roots the setup calls
/// (`harness::Layout::construction_roots`, in `proof_cache::Regression::claim`).
#[test]
fn o2_a_setup_methods_edit_alone_is_another_claim_never_reused() {
    let cache = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-cache-setup");
    let _ = std::fs::remove_dir_all(&cache);
    let before = counter("roots-before", |s| s.to_string());
    let rewrite = |s: &str| s.replace("        return count;\n", "        int c = count;\n        return c;\n");
    let after = counter("roots-after", rewrite);
    let edited = counter("roots-edited", |s| rewrite(s).replace("count += n * step;", "count += n == 4 ? n * step + 1 : n * step;"));
    let plan = counter_plan(&[ADD]);
    let run = |name: &str, after: &Path| {
        let mut options = equivalence::Options::new(&before, after, "counters.Counter#count");
        options.engine = jvmcontract::Engine::Native;
        options.jbmc = NO_JBMC.into();
        options.cache = Some(cache.clone());
        options.plan = Some(plans(&plan, &plan));
        let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work").join(name);
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        equivalence::run(&options).unwrap()
    };
    let cold = run("roots-cold", &after);
    assert_eq!(cold.verdict, Verdict::Verified, "{}", cold.output);
    let rerun = run("roots-rerun", &after);
    assert_eq!(rerun.verdict, Verdict::Verified, "{}", rerun.output);
    assert!(rerun.reuse.is_some(), "the exact rerun reuses the proof: {}", rerun.output);
    let o = run("roots-edited", &edited);
    assert!(o.reuse.is_none(), "another setup method is another claim: {}", o.output);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.input.contains("after the setup this.add(setup.0.n=4)"), "the whole history: {}", c.input);
    assert!(c.jvm.is_some(), "{}", o.output);
    // The typed witness carries the history: each setup call, its arguments typed and mapped to the inputs.
    let setup = |call: &jvmcontract::witness::Call| serde_json::to_value(&call.setup).unwrap();
    let history = setup(&c.call);
    assert_eq!(history[0]["method"], "add", "{history}");
    assert_eq!(history[0]["arguments"][0]["value"], 4, "{history}");
    assert_eq!(history[0]["arguments"][0]["from"], "setup.0.n", "{history}");
    assert_eq!(setup(c.previous_call.as_ref().unwrap()), history);
    // The refutation is reused once its witness reproduces, with the history it was stored with.
    let again = run("roots-edited-again", &edited);
    assert!(again.reuse.is_some(), "the exact rerun reuses the refutation: {}", again.output);
    assert_eq!(again.verdict, Verdict::Violation, "{}", again.output);
    assert_eq!(setup(&again.counterexample.as_ref().unwrap().call), history, "{}", again.output);
}

/// A build of the shared contract's throttle family (`tests/fixtures/application-core/throttle`): `before`,
/// `after`, or a defect overlaid on `after`.
fn throttle(build: &str) -> PathBuf {
    throttle_in(&format!("throttle-{build}"), build)
}

/// [`throttle`], compiled into a directory of its own (`name`), apart from another test's running at the same time.
fn throttle_in(name: &str, build: &str) -> PathBuf {
    let family = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/application-core/throttle");
    let base = family.join(if build == "before" { "before" } else { "after" });
    let overlay = family.join("defects").join(build);
    let file = if overlay.exists() { overlay } else { base }.join("throttle/Throttle.java");
    compile(name, &[("throttle/Throttle.java", &std::fs::read_to_string(file).unwrap())])
}

/// A frozen throttle claim. Its allocation bound is 1 in both versions: `allows` makes the
/// `IllegalArgumentException` it throws, which the domain gate counts, as `checked-claim` counts its own. The bound
/// is the target call's; the setup call's allocations aren't counted, since `setup_calls` bounds the history and its
/// outcomes are compared (the user's decision of 2026-11-08, which raised the frozen 0).
fn throttle_claim(name: &str) -> jvmcontract::spec::CanonicalClaim {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join(format!("tests/fixtures/application-core/golden/{name}.json"));
    let claim: jvmcontract::spec::CanonicalClaim = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    let bounds = &claim.domain.as_ref().unwrap().bounds;
    assert_eq!((bounds.before.allocations, bounds.after.allocations), (1, 1), "{name}: the exception allows throws is counted");
    claim
}

/// O3: a defect only a history reaches. `after-setup` is one unit short once a call of `take` has taken some: right
/// after construction (`used == 0`) it behaves as before, so the constructor-only claim verifies it, labelled for
/// that domain; under one setup call, it is refuted, and the witness is the whole history: the constructor, then
/// `take`, then `allows`, replayed on a JVM. `one-short` is refuted under both, the rewrite `after` verified under
/// both.
#[test]
fn o3_a_defect_only_a_history_reaches_is_refuted_with_the_whole_history_replayed() {
    use jvmcontract::spec::{heap, ObservationState, Verdict as Claimed};
    let before = throttle("before");
    let constructed = throttle_claim("throttle-constructed-claim");
    let setup = throttle_claim("throttle-setup-claim");
    for (build, constructed_verdict, setup_verdict) in [("after", Claimed::Verified, Claimed::Verified), ("after-setup", Claimed::Verified, Claimed::Refuted), ("one-short", Claimed::Refuted, Claimed::Refuted)] {
        let after = throttle(build);
        let zero = heap::check(&constructed, &before, &after).unwrap_or_else(|u| panic!("{build}, constructed: {u}"));
        assert_eq!(zero.verdict, constructed_verdict, "{build}, constructed: {zero:?}");
        assert!(zero.domain.contains("right after its constructor") && zero.domain.contains("no call before the target"), "{build}: the constructor-only scope is labelled: {}", zero.domain);
        assert!(!zero.domain.contains("setup"), "{build}: {}", zero.domain);
        let one = heap::check(&setup, &before, &after).unwrap_or_else(|u| panic!("{build}, setup: {u}"));
        assert_eq!(one.verdict, setup_verdict, "{build}, setup: {one:?}");
        assert!(one.domain.contains("this after the setup this.take(setup.0.n) × setup.0.n: int"), "{build}: the setup is the domain's: {}", one.domain);
        if setup_verdict == Claimed::Refuted {
            let witness = one.witness.as_deref().unwrap();
            assert!(witness.contains("allows(this=new Throttle(") && witness.contains("after the setup this.take(setup.0.n="), "{build}: the whole history: {witness}");
            assert!(one.accounting.iter().any(|a| a.observation == "result" && a.state == ObservationState::Refuted), "{build}: {one:?}");
        }
    }
    // Neither claim's key is the other's: the setup sequence is part of the claim, or the claim is uncacheable
    // (today the key's projection refuses a planned domain, which is the reuse stream's).
    if let (Ok(a), Ok(b)) = (jvmcontract::spec::cache::key(&constructed), jvmcontract::spec::cache::key(&setup)) {
        assert_ne!(a, b);
    }
}

/// Both versions' plans, from one plan's JSON for each.
fn plans(before: &str, after: &str) -> jvmcontract::construction::Plans {
    jvmcontract::construction::Plans { before: serde_json::from_str(before).unwrap(), after: serde_json::from_str(after).unwrap() }
}

/// A plan of the counter: `this`, a `Counter(int step)`, and the setup calls given (JSON, each `add(I)V` on its
/// leaf `setup.k.n`).
fn counter_plan(setup: &[&str]) -> String {
    let calls = setup.iter().map(|c| c.to_string()).collect::<Vec<_>>().join(", ");
    format!(r#"{{"nodes": [{{"id": 0, "class": "counters.Counter", "maker": {{"kind": "constructor", "descriptor": "(I)V"}}, "args": [{{"kind": "leaf", "path": "this.step", "type": "int"}}]}}],
        "roots": [{{"name": "this", "value": {{"kind": "node", "id": 0}}}}], "setup": [{calls}],
        "bounds": {{"nodes": 1, "max_array_length": 0, "setup_calls": {}}}}}"#, setup.len())
}

const ADD: &str = r#"{"method": "add(I)V", "args": [{"kind": "leaf", "path": "setup.0.n", "type": "int"}]}"#;

fn planned(name: &str, before: &Path, after: &Path, target: &str, plan: jvmcontract::construction::Plans) -> equivalence::Outcome {
    let mut options = equivalence::Options::new(before, after, target);
    options.engine = jvmcontract::Engine::Native;
    options.jbmc = NO_JBMC.into();
    options.plan = Some(plan);
    let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work").join(name);
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    equivalence::run(&options).unwrap()
}

const WINDOW: &str = r#"package windows;

/** A window of integers, of two constructors: a choice the plan makes, never a guess. */
public class Window {
    private final int lo;
    private final int hi;

    public Window(int lo, int hi) {
        if (lo > hi) {
            throw new IllegalArgumentException("lo above hi");
        }
        this.lo = lo;
        this.hi = hi;
    }

    public Window(int width) {
        this(0, width);
    }

    public boolean contains(int x) {
        return lo <= x && x <= hi;
    }
}
"#;

/// O1's selection: a class of two constructors is a named choice. Without a plan, the check refuses it; a plan
/// that names one by descriptor makes the receiver with it, a rewrite is verified and a defect refuted; a plan that
/// names a constructor the class doesn't have is refused with the ones it has.
#[test]
fn o1_a_plan_selects_one_of_several_constructors_by_descriptor() {
    let before = compile("window-before", &[("windows/Window.java", WINDOW)]);
    let after = compile("window-after", &[("windows/Window.java", &WINDOW.replace("return lo <= x && x <= hi;", "return !(x < lo || x > hi);"))]);
    let defect = compile("window-defect", &[("windows/Window.java", &WINDOW.replace("return lo <= x && x <= hi;", "return lo <= x && x < hi;"))]);
    let o = regression("window-unplanned", &before, &after, "windows.Window#contains");
    assert_eq!(o.verdict, Verdict::Unverifiable);
    assert!(o.problem.as_deref().unwrap_or_default().contains("has 2 constructors"), "{:?}", o.problem);
    let plan = |descriptor: &str, args: &str| format!(r#"{{"nodes": [{{"id": 0, "class": "windows.Window", "maker": {{"kind": "constructor", "descriptor": "{descriptor}"}}, "args": [{args}]}}],
        "roots": [{{"name": "this", "value": {{"kind": "node", "id": 0}}}}], "bounds": {{"nodes": 1, "max_array_length": 0, "setup_calls": 0}}}}"#);
    let two = plan("(II)V", r#"{"kind": "leaf", "path": "this.lo", "type": "int"}, {"kind": "leaf", "path": "this.hi", "type": "int"}"#);
    let o = planned("window-two", &before, &after, "windows.Window#contains", plans(&two, &two));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let o = planned("window-two-defect", &before, &defect, "windows.Window#contains", plans(&two, &two));
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.replay.as_ref().is_some_and(|r| r.reproduced) && o.counterexample.as_ref().is_some_and(|c| c.jvm.is_some()), "{}", o.output);
    // The one-argument constructor makes only windows from 0: the defect at hi is reachable there too.
    let one = plan("(I)V", r#"{"kind": "leaf", "path": "this.width", "type": "int"}"#);
    let o = planned("window-one-defect", &before, &defect, "windows.Window#contains", plans(&one, &one));
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.counterexample.as_ref().unwrap().input.contains("new Window("), "{}", o.output);
    // A constructor the class doesn't have, and a leaf misnamed, are refused by name.
    let none = plan("(J)V", r#"{"kind": "leaf", "path": "this.width", "type": "long"}"#);
    let o = planned("window-none", &before, &after, "windows.Window#contains", plans(&none, &none));
    assert!(o.problem.as_deref().unwrap_or_default().contains("has no constructor (J)V a caller can use; it has (II)V, (I)V"), "{:?}", o.problem);
    let misnamed = plan("(I)V", r#"{"kind": "leaf", "path": "this.w", "type": "int"}"#);
    let o = planned("window-misnamed", &before, &after, "windows.Window#contains", plans(&misnamed, &misnamed));
    assert!(o.problem.as_deref().unwrap_or_default().contains("which the check names this.width"), "{:?}", o.problem);
}

/// O3 through `equivalence --plan`: the setup sequence's outcomes are compared. A version whose setup call rejects an
/// input the other accepts differs on it, in the exception, and the input is never dropped: `add` takes n up to 5
/// in the new version, and `count` after `add(5)` is refuted, the history replayed on a JVM.
#[test]
fn o3_an_input_one_versions_setup_rejects_is_a_difference() {
    let before = counter("setup-before", |s| s.to_string());
    let wider = counter("setup-wider", |s| s.replace("n > 4", "n > 5"));
    let plan = counter_plan(&[ADD]);
    let o = planned("setup-wider", &before, &wider, "counters.Counter#count", plans(&plan, &plan));
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.input.contains("after the setup this.add(setup.0.n=5)"), "{}", c.input);
    assert!(c.differs.iter().any(|d| d == "exception"), "{:?}", c.differs);
    assert!(c.before.contains("in the setup call this.add"), "{}", c.before);
    assert!(c.jvm.is_some() && o.replay.as_ref().is_some_and(|r| r.reproduced), "{}", o.output);
    // The same rejection in both versions is the same outcome: a rewrite of add is verified over the history.
    let rewrite = counter("setup-rewrite", |s| s.replace("count += n * step;", "for (int i = 0; i < n; i++) { count += step; }"));
    let o = planned("setup-rewrite", &before, &rewrite, "counters.Counter#count", plans(&plan, &plan));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().unwrap();
    assert_eq!(stated.bounds.setup_calls, Some(1));
    assert!(stated.assumptions.iter().any(|a| a.kind == jvmcontract::statement::AssumptionKind::Setup), "{:?}", stated.assumptions);
    // Different setup sequences in the two plans are refused: both versions get the same history.
    let o = planned("setup-differ", &before, &rewrite, "counters.Counter#count", plans(&plan, &counter_plan(&[])));
    assert!(o.problem.as_deref().unwrap_or_default().contains("the setup sequences differ"), "{:?}", o.problem);
    // Three calls are past the sequence a plan may have.
    let three = counter_plan(&[ADD, &ADD.replace("setup.0.n", "setup.1.n"), &ADD.replace("setup.0.n", "setup.2.n")]);
    let o = planned("setup-three", &before, &rewrite, "counters.Counter#count", plans(&three, &three));
    assert!(o.problem.as_deref().unwrap_or_default().contains("at most 2"), "{:?}", o.problem);
}

/// O3 through `prove --plan`: a property of the state a setup call reaches. `count` is 0 right after construction,
/// and not after `add`, refuted with the history in the witness; a history whose call throws is outside the property.
#[test]
fn o3_a_property_over_the_states_a_setup_call_reaches() {
    let classes = counter("setup-property", |s| s.to_string());
    let with = |plan: &str, name: &str, assume: Option<&str>, assert: &str| {
        let mut options = property::Options::new(&[classes.clone()], "counters.Counter#count");
        options.engine = jvmcontract::Engine::Native;
        options.jbmc = NO_JBMC.into();
        options.assume = assume.map(str::to_string);
        options.assert = Some(assert.into());
        options.plan = Some(plans(plan, plan));
        let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work").join(name);
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        property::run(&options).unwrap()
    };
    let zero = counter_plan(&[]);
    let one = counter_plan(&[ADD]);
    assert_eq!(with(&zero, "prop-zero", None, "result == 0").verdict, Verdict::Verified);
    let o = with(&one, "prop-one", None, "result == 0");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.input.contains("after the setup this.add(setup.0.n="), "{}", c.input);
    // add rejects n above 4, so every state it reaches has count at most 4 steps (of a step small enough for 4
    // steps not to overflow; without the assumption the property is refuted on the overflow of 4 * this.step).
    let o = with(&one, "prop-bound", Some("this.step < 1000"), "result <= 4 * this.step && result >= 0");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
}

const BUFFER: &str = r#"package buffers;

/** A buffer over an int array its constructor takes: an ordinary receiver of a primitive-array constructor. */
public class Buffer {
    private final int[] data;

    public Buffer(int[] data) {
        if (data.length > 3) {
            throw new IllegalArgumentException("more than 3 values");
        }
        this.data = data.clone();
    }

    public int total() {
        int sum = 0;
        for (int i = 0; i < data.length; i++) {
            sum += data[i];
        }
        return sum;
    }

    public int size() {
        return data.length;
    }

    /** Raises the first value: a mutation of the receiver's own array. */
    public void bump() {
        if (data.length > 0) {
            data[0]++;
        }
    }
}
"#;

fn buffer(name: &str, edit: impl Fn(&str) -> String) -> PathBuf {
    compile(name, &[("buffers/Buffer.java", &edit(BUFFER))])
}

fn bounded(name: &str, before: &Path, after: &Path, target: &str, plan: Option<jvmcontract::construction::Plans>) -> equivalence::Outcome {
    let mut options = equivalence::Options::new(before, after, target);
    options.engine = jvmcontract::Engine::Native;
    options.jbmc = NO_JBMC.into();
    options.max_array_length = 4;
    options.plan = plan;
    let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work").join(name);
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    equivalence::run(&options).unwrap()
}

/// O1's arrays: a receiver whose constructor takes an int array is made with no adapter of the application's, its
/// array a bounded leaf (`this.data`), stated in the domain and the bounds. The two versions' arrays are apart: a
/// rewrite of a method that writes into the receiver's own array is verified, which it would not be if both
/// versions' objects were made from one array. A rewrite of `total` is verified and a defect refuted, replayed on a
/// JVM; a property over it is proved and a false one refuted.
#[test]
fn o1_a_receiver_of_a_primitive_array_constructor_needs_no_adapter() {
    let before = buffer("buffer-before", |s| s.to_string());
    let after = buffer("buffer-after", |s| s.replace("for (int i = 0; i < data.length; i++) {\n            sum += data[i];\n        }", "for (int v : data) {\n            sum += v;\n        }"));
    let o = bounded("buffer-total", &before, &after, "buffers.Buffer#total", None);
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let domain = o.domain.as_deref().unwrap_or_default();
    assert!(domain.contains("Buffer(data: int[])") && domain.contains("each array of its construction of length ≤ 4, not null"), "{domain}");
    assert_eq!(o.stated.as_ref().unwrap().bounds.max_array_length, Some(4));
    let defect = buffer("buffer-defect", |s| s.replace("sum += data[i];", "sum += i == 2 ? 0 : data[i];"));
    let o = bounded("buffer-total-defect", &before, &defect, "buffers.Buffer#total", None);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.input.contains("this=new Buffer(["), "{}", c.input);
    assert!(c.jvm.is_some() && o.replay.as_ref().is_some_and(|r| r.reproduced), "{}", o.output);
    // The receiver's own array, written by both versions: apart, so a rewrite of bump is verified.
    let rewrite = buffer("buffer-bump", |s| s.replace("data[0]++;", "data[0] = data[0] + 1;"));
    assert_eq!(bounded("buffer-bump", &before, &rewrite, "buffers.Buffer#bump", None).verdict, Verdict::Verified);
    // A property over the receiver made from its array: every array the constructor accepts has at most 3 values.
    // (The assertion can't read the array field itself yet: `this.data` is refused by name.)
    let o = prove("buffer-property", &before, "buffers.Buffer#size", None, "result <= 3");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let o = prove("buffer-property-field", &before, "buffers.Buffer#size", Some("this.data.length == 0"), "result == 0");
    assert!(o.problem.as_deref().unwrap_or_default().contains("does not read an object's array fields yet"), "{:?}", o.problem);
    let o = prove("buffer-property-false", &before, "buffers.Buffer#total", None, "result >= 0");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
}

/// O2's negative control: an array defensively copied before, and leaked after. The new constructor keeps the
/// caller's array, so `bump` writes into it: the caller's array as the call leaves it (`array:this.data`) differs,
/// though the receivers' fields agree. Refuted on that alone, and replayed on a JVM.
#[test]
fn o2_an_array_defensively_copied_before_but_leaked_after_is_refuted() {
    let before = buffer("leak-before", |s| s.to_string());
    let leaked = buffer("leak-after", |s| s.replace("this.data = data.clone();", "this.data = data;"));
    let o = bounded("leak-bump", &before, &leaked, "buffers.Buffer#bump", None);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.differs.iter().any(|d| d == "array:this.data"), "the caller's array differs: {:?}", c.differs);
    assert!(!c.differs.iter().any(|d| d.starts_with("field:")), "the receivers' fields agree: {:?}", c.differs);
    assert!(c.jvm.is_some() && o.replay.as_ref().is_some_and(|r| r.reproduced), "{}", o.output);
    // total reads the array and writes nothing: the leak is no difference to it.
    assert_eq!(bounded("leak-total", &before, &leaked, "buffers.Buffer#total", None).verdict, Verdict::Verified);
}

/// O1's arrays through a plan: `this`, a `Buffer([I)V` of the bounded array `this.data`. Its bound must be the
/// check's, and a null or a doubly used array is refused by name until it is built.
#[test]
fn o1_a_plans_array_leaf_is_the_constructors_argument() {
    let before = buffer("plan-buffer-before", |s| s.to_string());
    let defect = buffer("plan-buffer-defect", |s| s.replace("sum += data[i];", "sum += i == 2 ? 0 : data[i];"));
    let plan = |array: &str| format!(r#"{{"nodes": [{{"id": 0, "class": "buffers.Buffer", "maker": {{"kind": "constructor", "descriptor": "([I)V"}}, "args": [{array}]}}],
        "roots": [{{"name": "this", "value": {{"kind": "node", "id": 0}}}}], "bounds": {{"nodes": 1, "max_array_length": 8, "setup_calls": 0}}}}"#);
    let four = plan(r#"{"kind": "array", "path": "this.data", "element": "int", "max_length": 4}"#);
    let o = bounded("plan-buffer", &before, &defect, "buffers.Buffer#total", Some(plans(&four, &four)));
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.counterexample.as_ref().is_some_and(|c| c.jvm.is_some()), "{}", o.output);
    let eight = plan(r#"{"kind": "array", "path": "this.data", "element": "int", "max_length": 8}"#);
    let o = bounded("plan-buffer-eight", &before, &defect, "buffers.Buffer#total", Some(plans(&eight, &eight)));
    assert!(o.problem.as_deref().unwrap_or_default().contains("bounds the array this.data at 8 elements, and the check bounds every array at 4"), "{:?}", o.problem);
    let nullable = plan(r#"{"kind": "array", "path": "this.data", "element": "int", "max_length": 4, "nullable": true}"#);
    let o = bounded("plan-buffer-null", &before, &defect, "buffers.Buffer#total", Some(plans(&nullable, &nullable)));
    assert!(o.problem.as_deref().unwrap_or_default().contains("may be null") && o.problem.as_deref().unwrap_or_default().contains("the objects stream builds it"), "{:?}", o.problem);
}

const CELLS: &str = r#"package cells;

/** A mutable cell, made by its constructor. */
public class Cell {
    public int v;

    public Cell(int v) {
        this.v = v;
    }
}
"#;

const OPS: &str = r#"package cells;

/** Methods over two cells, whose results depend on whether the two are one object. */
public class Ops {
    /** Reads b, writes a, and reads b again: the second read sees the write where a and b are one object. */
    public static int twice(Cell a, Cell b) {
        int x = b.v;
        a.v = 7;
        return x + b.v;
    }

    /** Hands back the first cell. */
    public static Cell pick(Cell a, Cell b) {
        return a;
    }

    /** A cell's value, or 0 for none. */
    public static int value(Cell a) {
        return a == null ? 0 : a.v;
    }
}
"#;

fn cells(name: &str, edit: impl Fn(&str) -> String) -> PathBuf {
    compile(name, &[("cells/Cell.java", CELLS), ("cells/Ops.java", &edit(OPS))])
}

/// A plan of the roots `a` and `b`, two `Cell(int v)` nodes, `b`'s value given (JSON): `{"kind": "node", "id": 1}`
/// for an object of its own, `"id": 0` for one object with `a`, or a choice (`"same_as": [0]`, `"nullable": true`).
fn cell_plan(b: &str) -> String {
    let cell = |id: u32, path: &str| format!(r#"{{"id": {id}, "class": "cells.Cell", "maker": {{"kind": "constructor", "descriptor": "(I)V"}}, "args": [{{"kind": "leaf", "path": "{path}.v", "type": "int"}}]}}"#);
    let shared = b.contains(r#""id": 0"#);
    let nodes = if shared { cell(0, "a") } else { format!("{}, {}", cell(0, "a"), cell(1, "b")) };
    format!(r#"{{"nodes": [{nodes}], "roots": [{{"name": "a", "value": {{"kind": "node", "id": 0}}}}, {{"name": "b", "value": {b}}}],
        "bounds": {{"nodes": {}, "max_array_length": 0, "setup_calls": 0}}}}"#, if shared { 1 } else { 2 })
}

/// O2's negative control of two parameters that were one object becoming distinct: a rewrite of `twice` that keeps
/// the first read of `b` (right only where `a` and `b` are two objects) is verified over two nodes, and refuted
/// where the plan makes them one node, or lets them be one; the witness names the one object, and the JVM run of
/// the harness rebuilds it, so the difference reproduces there.
#[test]
fn o2_two_parameters_that_were_one_object_becoming_distinct_is_refuted() {
    let before = cells("cells-before", |s| s.to_string());
    let distinct = cells("cells-distinct", |s| s.replace("return x + b.v;", "return x + x;"));
    let own = cell_plan(r#"{"kind": "node", "id": 1}"#);
    let o = planned("twice-own", &before, &distinct, "cells.Ops#twice", plans(&own, &own));
    assert_eq!(o.verdict, Verdict::Verified, "two objects of their own: {}", o.output);

    let one = cell_plan(r#"{"kind": "node", "id": 0}"#);
    let o = planned("twice-one", &before, &distinct, "cells.Ops#twice", plans(&one, &one));
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.domain.as_deref().unwrap_or_default().contains("× b: the same object as a"), "the domain says the two are one: {:?}", o.domain);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.input.contains("b=the same object as a"), "the witness names the one object: {}", c.input);
    assert!(o.replay.as_ref().is_some_and(|r| r.reproduced), "{}", o.output);
    assert!(c.jvm.is_some(), "the witness is run on a JVM, which rebuilds the one object: {}", o.output);

    let may = cell_plan(r#"{"kind": "node", "id": 1, "same_as": [0]}"#);
    let o = planned("twice-may", &before, &distinct, "cells.Ops#twice", plans(&may, &may));
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.domain.as_deref().unwrap_or_default().contains("a and b may be the same object"), "{:?}", o.domain);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.input.contains("b=the same object as a"), "the choice that shows it is one object: {}", c.input);
    assert!(o.replay.as_ref().is_some_and(|r| r.reproduced) && c.jvm.is_some(), "{}", o.output);

    // The versions are given the same choices.
    let o = planned("twice-differ", &before, &distinct, "cells.Ops#twice", plans(&own, &one));
    assert!(o.problem.as_deref().unwrap_or_default().contains("choices of null and of one object differ"), "{:?}", o.problem);
}

/// The identities a plan makes are the ones compared: a rewrite of `pick` that hands back `b` is verified where the
/// plan makes `a` and `b` one node, and refuted on identity where they are two objects.
#[test]
fn o2_a_plans_shared_node_is_one_object_in_the_identity_relations() {
    let before = cells("pick-before", |s| s.to_string());
    let other = cells("pick-other", |s| s.replace("        return a;\n", "        return b;\n"));
    let one = cell_plan(r#"{"kind": "node", "id": 0}"#);
    let o = planned("pick-one", &before, &other, "cells.Ops#pick", plans(&one, &one));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let own = cell_plan(r#"{"kind": "node", "id": 1}"#);
    let o = planned("pick-own", &before, &other, "cells.Ops#pick", plans(&own, &own));
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.differs.iter().any(|d| d.contains("identity")), "the result's identity with a differs: {:?}", c.differs);
    assert!(o.replay.as_ref().is_some_and(|r| r.reproduced), "{}", o.output);
}

/// A plan's root that may be null: a rewrite of `value` that drops the null check is refuted on `a=null` where the
/// plan lets `a` be null, replayed, and verified where it doesn't.
#[test]
fn o2_a_plans_nullable_root_is_a_choice_of_null() {
    let before = cells("value-before", |s| s.to_string());
    let unchecked = cells("value-unchecked", |s| s.replace("return a == null ? 0 : a.v;", "return a.v;"));
    let plan = |a: &str| format!(r#"{{"nodes": [{{"id": 0, "class": "cells.Cell", "maker": {{"kind": "constructor", "descriptor": "(I)V"}}, "args": [{{"kind": "leaf", "path": "a.v", "type": "int"}}]}}],
        "roots": [{{"name": "a", "value": {a}}}], "bounds": {{"nodes": 1, "max_array_length": 0, "setup_calls": 0}}}}"#);
    let never = plan(r#"{"kind": "node", "id": 0}"#);
    assert_eq!(planned("value-never", &before, &unchecked, "cells.Ops#value", plans(&never, &never)).verdict, Verdict::Verified);
    let null = plan(r#"{"kind": "node", "id": 0, "nullable": true}"#);
    let o = planned("value-null", &before, &unchecked, "cells.Ops#value", plans(&null, &null));
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.domain.as_deref().unwrap_or_default().contains("or null"), "{:?}", o.domain);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.input.contains("a=null"), "{}", c.input);
    assert!(o.replay.as_ref().is_some_and(|r| r.reproduced) && c.jvm.is_some(), "{}", o.output);
}

/// The property check makes a plan's shared node one object too: `twice` on one cell of value 3 returns 10, which
/// holds over one node and is refuted over two.
#[test]
fn o2_a_property_over_a_plans_shared_node() {
    let classes = cells("cells-property", |s| s.to_string());
    let with = |plan: &str, name: &str| {
        let mut options = property::Options::new(&[classes.clone()], "cells.Ops#twice");
        options.engine = jvmcontract::Engine::Native;
        options.jbmc = NO_JBMC.into();
        options.assume = Some("b.v == 3".into());
        options.assert = Some("result == 10".into());
        options.plan = Some(plans(plan, plan));
        let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work").join(name);
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        property::run(&options).unwrap()
    };
    let o = with(&cell_plan(r#"{"kind": "node", "id": 0}"#), "twice-prop-one");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let o = with(&cell_plan(r#"{"kind": "node", "id": 1}"#), "twice-prop-own");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
}

/// O2's negative control of unsupported side effects in a constructor: an object whose constructor writes a static
/// field, itself or through a method it calls, is refused by name wherever a check would make it (a receiver, a
/// parameter, a plan's node, in either version), since the checks make each object from the classes' initial state
/// and so would check only the first one made. A setup call that writes one is refused the same way, its effect
/// being outside every observation. A constructor's call into the JDK with an effect (`System.out`) is refused by
/// the engine, as anywhere. A constructor that reads a constant and calls a method writing its own fields is
/// still made, and its check verified.
#[test]
fn o2_a_constructors_side_effect_outside_its_object_is_refused_by_name() {
    let counted = |s: &str| s.replace("    private int count;\n", "    private int count;\n    static int made;\n").replace("        this.step = step;\n", "        this.step = step;\n        made++;\n");
    let plain = counter("effect-plain", |s| s.to_string());
    let effect = counter("effect-static", counted);
    let refused = |o: &equivalence::Outcome, what: &str| {
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        let problem = o.problem.as_deref().unwrap_or_default();
        assert!(problem.contains("has a side effect outside the object it makes") && problem.contains(what), "{problem}");
    };
    // The receiver, in the previous version, the new one, and the property check.
    refused(&regression("effect-before", &effect, &plain, "counters.Counter#count"), "writes the static field counters.Counter.made");
    refused(&regression("effect-after", &plain, &effect, "counters.Counter#count"), "writes the static field counters.Counter.made");
    let o = prove("effect-prove", &effect, "counters.Counter#count", None, "result == 0");
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("writes the static field counters.Counter.made"), "{}", o.output);

    // A plan's node, and a setup call that writes a static field.
    let o = planned("effect-plan", &effect, &effect, "counters.Counter#count", plans(&counter_plan(&[]), &counter_plan(&[])));
    refused(&o, "node 0's constructor (I)V of counters.Counter");
    let adds = counter("effect-setup", |s| s.replace("    private int count;\n", "    private int count;\n    static int adds;\n").replace("        count += n * step;\n", "        count += n * step;\n        adds++;\n"));
    let o = planned("effect-setup", &adds, &adds, "counters.Counter#count", plans(&counter_plan(&[ADD]), &counter_plan(&[ADD])));
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("the setup call add(I)V has a side effect outside the receiver") && o.problem.as_deref().unwrap_or_default().contains("counters.Counter.adds"), "{:?}", o.problem);

    // A parameter's inner constructor writing a static field through a method it calls, in the previous version.
    let registry = "package cells;\n\npublic class Registry {\n    static int cells;\n\n    static void note() {\n        cells++;\n    }\n}\n";
    let noted = CELLS.replace("        this.v = v;\n", "        this.v = v;\n        Registry.note();\n");
    let before = compile("effect-cell", &[("cells/Cell.java", &noted), ("cells/Ops.java", OPS), ("cells/Registry.java", registry)]);
    let after = cells("effect-cell-plain", |s| s.to_string());
    let o = regression("effect-cell", &before, &after, "cells.Ops#value");
    refused(&o, "cells.Registry.note");
    assert!(o.problem.as_deref().unwrap_or_default().contains("in the previous version, parameter a"), "{:?}", o.problem);
    let o = prove("effect-cell", &before, "cells.Ops#value", None, "result == a.v");
    assert!(o.problem.as_deref().unwrap_or_default().contains("writes the static field cells.Registry.cells"), "{}", o.output);

    // A call into the JDK with an effect, refused by the engine.
    let printed = counter("effect-print", |s| s.replace("        this.step = step;\n", "        this.step = step;\n        System.out.println(step);\n"));
    let o = regression("effect-print", &printed, &plain, "counters.Counter#count");
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.output.contains("System.out"), "{}", o.output);

    // What isn't a side effect: a constant read, and a method writing the object's own field.
    let own = |s: &str| s.replace("    private int count;\n", "    private int count;\n    static final int START = 0;\n").replace("        this.step = step;\n", "        this.step = step;\n        reset();\n").replace("    public int count() {", "    private void reset() {\n        count = START;\n    }\n\n    public int count() {");
    let o = regression("effect-own", &counter("effect-own", own), &plain, "counters.Counter#count");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
}

/// O2's negative control of a narrower new constructor: an input the previous version's constructor admits and the
/// new one's rejects can't shrink the claim to the inputs both accept. The regression harness compares the two
/// versions' admission: an input only one version can build is a difference, on the exception, refuted with a
/// witness whose version that rejects it throws in its constructor, replayed in the interpreter and run on a JVM;
/// an input both reject is skipped, as before. Under an externally anchored claim (the frozen throttle's, `this`
/// anchored by identity) it is refuted where the claim requires the exception, and unresolved where it doesn't,
/// never verified.
#[test]
fn o2_a_narrower_new_constructor_under_an_anchored_domain_is_never_silently_intersected() {
    use jvmcontract::spec::{heap, ObservationState, Verdict as Claimed};
    use jvmcontract::statement::AssumptionKind;
    let before = counter("narrower-before", |s| s.to_string());
    // The receiver's constructor rejects step 1, which the previous version's accepts: a void target, a getter.
    let narrower = counter("narrower-after", |s| s.replace("if (step < 1) {", "if (step < 2) {"));
    for target in ["counters.Counter#count", "counters.Counter#add"] {
        let o = regression(&format!("narrower-{target}"), &before, &narrower, target);
        assert_eq!(o.verdict, Verdict::Violation, "{target}: {}", o.output);
        let c = o.counterexample.as_ref().unwrap();
        assert!(c.input.contains("new Counter(1)"), "{target}: the input only the previous version admits: {}", c.input);
        assert!(c.differs.iter().any(|d| d == "exception"), "{target}: {:?}", c.differs);
        assert!(c.after.contains("<the constructor") && c.after.contains("IllegalArgumentException"), "{target}: the new version rejects it in its constructor: {}", c.after);
        assert!(!c.before.contains("<the constructor"), "{target}: {}", c.before);
        assert!(c.jvm.is_some() && o.replay.as_ref().is_some_and(|r| r.reproduced), "{target}: {}", o.output);
    }
    // A wider one is a difference too: the previous version rejects step 0, the new one builds it.
    let wider = counter("wider-after", |s| s.replace("if (step < 1) {", "if (step < 0) {"));
    let o = regression("wider-count", &before, &wider, "counters.Counter#count");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.input.contains("new Counter(0)") && c.before.contains("<the constructor") && !c.after.contains("<the constructor"), "{} / {} / {}", c.input, c.before, c.after);
    // Constructors that reject the same inputs, written otherwise: verified, and the statement says that an input
    // both reject is skipped, and one only one version rejects would be a difference.
    let same = counter("same-admission", |s| s.replace("if (step < 1) {", "if (!(step > 0)) {"));
    let o = regression("same-admission", &before, &same, "counters.Counter#count");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let caveat = o.stated.as_ref().unwrap().assumptions.iter().find(|a| a.kind == AssumptionKind::Constructible).expect("the constructors' caveat");
    assert!(caveat.text.contains("an input both versions' constructors reject is skipped, and one that only one version's reject is a difference"), "{}", caveat.text);
    // A parameter's constructor, not the receiver's: the same, in a static method over a counter.
    let user = |name: &str, step: &str| compile(name, &[("counters/Counter.java", &COUNTER.replace("if (step < 1) {", step)), ("counters/Use.java", "package counters;\n\npublic class Use {\n    public static int twice(Counter c) {\n        c.add(1);\n        return c.count() * 2;\n    }\n}\n")]);
    let (b, a) = (user("narrower-param-before", "if (step < 1) {"), user("narrower-param-after", "if (step < 2) {"));
    let o = regression("narrower-param", &b, &a, "counters.Use#twice");
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.counterexample.as_ref().unwrap().differs.iter().any(|d| d == "exception"), "{}", o.output);

    // Under the frozen throttle claim, anchored: the new constructor rejects capacity 1.
    let throttle_before = throttle_in("narrowed-throttle-before", "before");
    let source = std::fs::read_to_string(Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/application-core/throttle/after/throttle/Throttle.java")).unwrap();
    assert!(source.contains("if (capacity < 1) {"), "the fixture's constructor check");
    let narrowed = compile("throttle-narrowed", &[("throttle/Throttle.java", &source.replace("if (capacity < 1) {", "if (capacity < 2) {"))]);
    let claim = throttle_claim("throttle-constructed-claim");
    let r = heap::check(&claim, &throttle_before, &narrowed).unwrap_or_else(|u| panic!("{u}"));
    assert_eq!(r.verdict, Claimed::Refuted, "{r:?}");
    assert!(r.accounting.iter().any(|a| a.observation == "exception" && a.state == ObservationState::Refuted), "{r:?}");
    assert!(r.witness.as_deref().unwrap_or_default().contains("new Throttle(1)"), "{r:?}");
    // The same claim without the exception among its required observations: unresolved, not verified.
    let mut lenient = claim.clone();
    lenient.contract.required.retain(|o| o != "exception");
    let r = heap::check(&lenient, &throttle_before, &narrowed).unwrap_or_else(|u| panic!("{u}"));
    assert_eq!(r.verdict, Claimed::Unresolved, "{r:?}");
    // The fixture's own rewrite, whose constructor admits the same capacities, is still verified.
    let r = heap::check(&claim, &throttle_before, &throttle_in("narrowed-throttle-after", "after")).unwrap_or_else(|u| panic!("{u}"));
    assert_eq!(r.verdict, Claimed::Verified, "{r:?}");
}

/// O2's shrinking: a shrunk witness is the same failure as the one found, never another the shrinker slid into.
/// Here the new constructor rejects step 1, which the previous version admits (a difference on the exception), and
/// the new `add` adds one more per call from step 3 (a difference on the receiver's field). A witness found at a
/// large step shrinks towards zero, and from step 3 the next candidate is step 1: under the harness alone that is
/// a counterexample too, of the other difference.
#[test]
fn o2_a_shrunk_witness_reproduces_the_same_failure() {
    let before = counter("same-failure-before", |s| s.to_string());
    let after = counter("same-failure-after", |s| s.replace("if (step < 1) {", "if (step < 2) {").replace("count += n * step;", "count += step >= 3 ? n * step + n : n * step;"));
    let run = |name: &str, shrink: bool| {
        let mut options = equivalence::Options::new(&before, &after, "counters.Counter#add");
        options.engine = jvmcontract::Engine::Native;
        options.jbmc = NO_JBMC.into();
        options.shrink = shrink;
        let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work").join(name);
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        equivalence::run(&options).unwrap()
    };
    let unshrunk = run("same-failure-unshrunk", false);
    assert_eq!(unshrunk.verdict, Verdict::Violation, "{}", unshrunk.output);
    let found = unshrunk.counterexample.as_ref().unwrap();
    assert!(!found.differs.iter().any(|d| d == "exception"), "the premise: the input found differs on the field, not the admission: {}", found.input);
    let o = run("same-failure", true);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert_eq!(c.found.as_deref(), Some(found.input.as_str()), "{}", o.output);
    assert!(c.jvm.is_some(), "the shrunk witness is run on a JVM: {}", o.output);
    assert_eq!(c.differs, found.differs, "the shrunk witness {} is another failure than the one found, {}: {}", c.input, found.input, o.output);
    assert!(c.input.contains("new Counter(3)"), "shrunk as far as the same failure goes: {}", c.input);

    // The property check: `add` throws at step 2, and adds one more per call from step 3. A violation of the
    // assertion found at a large step shrinks to step 3, never into the exception at step 2.
    let classes = counter("same-failure-property", |s| s.replace("count += n * step;", "if (step == 2) {\n            throw new IllegalStateException(\"two\");\n        }\n        count += step >= 3 ? n * step + n : n * step;"));
    let property = |name: &str, shrink: bool| {
        let mut options = property::Options::new(&[classes.clone()], "counters.Counter#add");
        options.engine = jvmcontract::Engine::Native;
        options.jbmc = NO_JBMC.into();
        options.assume = Some("n >= 0 && n <= 4".into());
        options.assert = Some("this.count == n * this.step".into());
        options.shrink = shrink;
        let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work").join(name);
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        property::run(&options).unwrap()
    };
    let unshrunk = property("same-failure-property-unshrunk", false);
    assert_eq!(unshrunk.verdict, Verdict::Violation, "{}", unshrunk.output);
    let found = unshrunk.counterexample.as_ref().unwrap();
    assert!(!found.outcome.contains("throws"), "the premise: the input found violates the assertion on a normal return: {}", found.outcome);
    let o = property("same-failure-property", true);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(!c.outcome.contains("throws") && c.input.contains("new Counter(3)"), "the same failure, shrunk: {} {}", c.input, c.outcome);
    assert_eq!(c.found.as_deref(), Some(found.input.as_str()), "{}", o.output);
    assert!(o.replay.as_ref().is_some_and(|r| r.by == "jvm" && r.reproduced), "{}", o.output);
}

const DIGITS: &str = r#"package digits;

/** A digit's value. Its edits below call `String.formatted`, which the interpreter cannot run. */
public class Digits {
    public static int value(int ch) {
        return ch - 48;
    }
}
"#;

/// `Digits` with `edit` before its return: `formats` throws, with a message `String.format` makes, where it was a
/// value; `same` reads the identity of a formatted string's `toString`, which the checker approximates under
/// `--gaps assume` as a new object, and which the JVM gives as the string itself, so that it changes nothing.
fn digits(name: &str, edit: &str) -> PathBuf {
    compile(name, &[("digits/Digits.java", &DIGITS.replace("        return ch - 48;", &format!("        {edit}\n        return ch - 48;")))])
}

const FORMATS: &str = "if (ch == 1655) { throw new IllegalArgumentException(\"not a digit\".formatted()); }";
const SAME: &str = "String a = \"x\".formatted(); if (ch == 1655 && a.toString() != a) { return -1; }";

/// A replay that cannot run one version is no reproduction (the main brief's Phase 0 finding on VF-015's step 4,
/// where an outcome the interpreter could not produce counted as a difference). The counterexample is run on a JVM,
/// the reference, as one through a contract is: a refutation where the harness fails there, with the JVM's
/// outcomes and their difference; none where the versions agree there. The same holds for a property's witness.
#[test]
fn o2_a_replay_that_cannot_run_one_version_is_no_reproduction() {
    let run = |name: &str, after: &Path| {
        let before = digits("unreplayed-before", "");
        let mut options = equivalence::Options::new(&before, after, "digits.Digits#value");
        options.engine = jvmcontract::Engine::Native;
        options.jbmc = NO_JBMC.into();
        options.gaps = jvmcontract::bmc::gaps::GapMode::Assume;
        let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work").join(name);
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        equivalence::run(&options).unwrap()
    };
    // A real difference: the new version throws where the previous one returned 1607.
    let o = run("unreplayed-formats", &digits("unreplayed-formats", FORMATS));
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.replay.as_ref().is_some_and(|r| r.by == "jvm" && r.reproduced), "reproduced on a JVM, not by the interpreter's half a replay: {:?}\n{}", o.replay, o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.jvm.is_some(), "{}", o.output);
    assert!(!c.after.contains("could not replay") && c.after.contains("IllegalArgumentException"), "the new version's outcome is the JVM's: {}", c.after);
    assert_eq!(c.differs, vec!["exception".to_string()], "{}", o.output);

    // No difference on a JVM: the checker's approximation of `toString` took the method down a path the JVM never
    // does. That was a refutation, `reproduced`, with the new version's outcome unknown.
    let o = run("unreplayed-same", &digits("unreplayed-same", SAME));
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.replay.as_ref().is_some_and(|r| !r.reproduced), "{:?}", o.replay);
    let problem = o.problem.as_deref().unwrap_or_default();
    assert!(problem.contains("cannot run the new version") && problem.contains("on a JVM"), "{problem}");

    // The property check: the method's own outcome, unknown to the interpreter, is the JVM's.
    let prove_on = |name: &str, classes: &Path| {
        let mut options = property::Options::new(&[classes.to_path_buf()], "digits.Digits#value");
        options.engine = jvmcontract::Engine::Native;
        options.jbmc = NO_JBMC.into();
        options.gaps = jvmcontract::bmc::gaps::GapMode::Assume;
        options.assert = Some("result == ch - 48".into());
        let work = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("application-core-objects-work").join(name);
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        property::run(&options).unwrap()
    };
    let o = prove_on("unreplayed-prove-formats", &digits("unreplayed-prove-formats", FORMATS));
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.replay.as_ref().is_some_and(|r| r.by == "jvm" && r.reproduced), "{:?}\n{}", o.replay, o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(!c.outcome.contains("could not replay") && c.outcome.contains("IllegalArgumentException"), "{}", c.outcome);
    let o = prove_on("unreplayed-prove-same", &digits("unreplayed-prove-same", SAME));
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.replay.as_ref().is_some_and(|r| !r.reproduced), "{:?}", o.replay);
}
