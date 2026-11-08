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

/// A receiver outside what a check makes is refused by name: a dependency among its constructor's arguments is
/// the stream's to build, and several constructors are a choice no plain check makes.
#[test]
fn o1_a_receiver_outside_the_construction_is_refused_by_name() {
    let dependency = compile("dependency", &[
        ("deps/Clock.java", "package deps;\npublic interface Clock { long now(); }\n"),
        ("deps/Timer.java", "package deps;\npublic class Timer {\n    private final long start;\n    private final Clock clock;\n    public Timer(long start, Clock clock) { this.start = start; this.clock = clock; }\n    public long since(long t) { return t - start; }\n}\n"),
    ]);
    let o = regression("dependency", &dependency, &dependency, "deps.Timer#since");
    assert_eq!(o.verdict, Verdict::Unverifiable);
    let problem = o.problem.unwrap();
    assert!(problem.contains("the objects stream builds it") && problem.contains("deps.Clock is an interface"), "{problem}");
    let o = prove("dependency", &dependency, "deps.Timer#since", None, "true");
    assert!(o.problem.as_deref().unwrap_or_default().contains("the objects stream builds it"), "{}", o.output);

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

/// The reproducer of a finding for the reuse stream (`proof_cache.rs` is its file): the regression cache's key
/// roots each version's closure at a made object's own constructor, not at the inner objects' constructors, which
/// the harness calls apart. A rewrite of `get` is verified and stored; a build that also changes `Inner`'s
/// constructor, so that `get` gives one more, then reuses that proof. Ignored until the key covers every
/// constructor the harness calls (`RecordType::constructors`); it must pass then.
#[test]
#[ignore = "an unsound cache hit: the reuse stream's fix in proof_cache.rs (the objects stream's Progress, 2026-11-08)"]
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
