//! A String inside an object (Phase 5 of `llm-dlc/loops/application-core.md`, J1's O2: the quote request's code): a
//! constructor's String argument is a leaf of its construction, a value of the values stream's String adapter, of at
//! most the check's bound of code units (`--max-array-length`, or a plan's String bounded alike), never null, the one
//! object both versions are given; and a String field is compared by content (`String.equals`), null in both or the
//! same code units, never by identity. Each part has a correct case, a planted defect replayed on a JVM, a named
//! boundary, and its cached evidence invalidated.

use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::spec::cache::Reuse;
use jvmcontract::{equivalence, property, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";

fn tmp(part: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("object-strings").join(part)
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

/// A request of a code and a count, which rejects a null code as the quote request does; `extra` is more of its
/// constructor's body.
fn request(extra: &str) -> String {
    format!("package strs;\npublic final class Request {{\n    final String code;\n    final int count;\n    public Request(String code, int count) {{\n        if (code == null) {{ throw new IllegalArgumentException(\"a code\"); }}\n{extra}        this.code = code;\n        this.count = count;\n    }}\n}}\n")
}

/// A desk of a region, a String the receiver holds, with `members` as its methods.
fn desk(name: &str, members: &str) -> PathBuf {
    desk_with(name, members, "")
}

fn desk_with(name: &str, members: &str, request_extra: &str) -> PathBuf {
    let desk = format!("package strs;\npublic class Desk {{\n    private final String region;\n    private String last;\n    public Desk(String region) {{ this.region = region; this.last = \"\"; }}\n{members}}}\n");
    compile(name, &[("strs/Request.java", request(request_extra)), ("strs/Desk.java", desk)])
}

/// The methods of the previous version.
const BEFORE: &str = "    public int score(Request r) { return r.code.startsWith(\"V\") ? r.count * 2 : r.count; }\n    public boolean local(Request r) { return r.code.equals(region); }\n    public Request bumped(Request r) { return new Request(r.code, r.count + 1); }\n    public void note(Request r) { last = r.code; }\n";

fn options(name: &str, before: &Path, after: &Path, target: &str) -> equivalence::Options {
    let mut options = equivalence::Options::new(before, after, target);
    options.engine = jvmcontract::Engine::Native;
    options.jbmc = NO_JBMC.into();
    options.max_array_length = 3;
    let work = tmp(&format!("work-{name}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    options
}

fn regression(name: &str, before: &Path, after: &Path, target: &str) -> equivalence::Outcome {
    equivalence::run(&options(name, before, after, target)).unwrap()
}

/// The correct cases and the defects. A String a request is made from and a String the receiver is made from are
/// leaves of every content up to the bound: a rewrite of `startsWith` by `charAt`, `equals` turned round, a result
/// whose code is a concatenation (another object, the same content) and a field set to a copy of the code are each
/// proved. A wrong prefix, a result with another code and a field set to another String are refuted, each on what
/// it changes, the witness making the request with its String (`new Request("V", 0)`) and run on a JVM.
#[test]
fn a_string_inside_an_object_is_a_leaf_and_a_string_field_is_compared_by_content() {
    let before = desk("before", BEFORE);
    let after = desk("after", "    public int score(Request r) { return r.code.length() > 0 && r.code.charAt(0) == 'V' ? r.count * 2 : r.count; }\n    public boolean local(Request r) { return region.equals(r.code); }\n    public Request bumped(Request r) { return new Request(r.code + \"\", r.count + 1); }\n    public void note(Request r) { last = \"\" + r.code; }\n");
    for target in ["strs.Desk#score", "strs.Desk#local", "strs.Desk#bumped", "strs.Desk#note"] {
        let o = regression(&format!("rewrite-{target}"), &before, &after, target);
        assert_eq!(o.verdict, Verdict::Verified, "{target}: {}", o.output);
        let domain = o.domain.clone().unwrap_or_default();
        assert!(domain.contains("code: java.lang.String") && domain.contains("region: java.lang.String"), "{target}: the domain names both Strings: {domain}");
        assert!(domain.contains("each String of its construction of ≤ 3 code units, not null"), "{target}: the domain names the String bound: {domain}");
        let statement = o.stated.as_ref().expect("a statement");
        assert_eq!(statement.bounds.max_value_length, Some(3), "{target}: the String bound is stated");
        assert!(!statement.models.values.is_empty(), "{target}: the String model is stated");
    }

    let defect = desk("defect", "    public int score(Request r) { return r.code.startsWith(\"VI\") ? r.count * 2 : r.count; }\n    public boolean local(Request r) { return r.code.equals(region); }\n    public Request bumped(Request r) { return new Request(r.code.isEmpty() ? r.code : \"V\", r.count + 1); }\n    public void note(Request r) { last = r.code.isEmpty() ? \"\" : \"V\"; }\n");
    for (target, on) in [("strs.Desk#score", "result"), ("strs.Desk#bumped", "result"), ("strs.Desk#note", "this")] {
        let o = regression(&format!("defect-{target}"), &before, &defect, target);
        assert_eq!(o.verdict, Verdict::Violation, "{target}: {}", o.output);
        let c = o.counterexample.as_ref().unwrap();
        assert!(c.input.contains("new Request(\""), "{target}: the witness makes the request with its String: {}", c.input);
        assert!(c.differs.iter().any(|d| d == on || d.starts_with(&format!("field:{on}"))), "{target}: refuted on {on}: {:?}", c.differs);
        let replay = o.replay.as_ref().expect("replayed");
        assert!(replay.reproduced, "{target}: {}", o.output);
        assert!(o.output.contains("run on a JVM"), "{target}: an object made by its constructor is run on a JVM: {}", o.output);
    }
    // The field's content is shown, as the harness compares it.
    let o = regression("defect-shown", &before, &defect, "strs.Desk#bumped");
    assert!(o.output.contains("code=\""), "the result's code is shown by content: {}", o.output);
}

/// The named boundary: a property check makes no String inside an object; `--engine jbmc` is refused, since JBMC's
/// Strings are its own model; and a plan's String inside a node must be the String adapter's, never null, bounded as
/// the check bounds every String, and named by its path.
#[test]
fn a_string_inside_an_object_outside_the_regression_check_is_refused_by_name() {
    let before = desk("boundary-before", BEFORE);
    let mut p = property::Options::new(&[before.clone()], "strs.Desk#score");
    p.engine = jvmcontract::Engine::Native;
    p.jbmc = NO_JBMC.into();
    p.assert = Some("result >= 0 || result < 0".into());
    p.work = Some(tmp("work-property"));
    let o = property::run(&p).unwrap();
    assert_eq!(o.verdict, Verdict::Unverifiable);
    assert!(o.problem.as_deref().unwrap_or_default().contains("is a String inside an object"), "{}", o.output);

    let mut o = options("jbmc", &before, &before, "strs.Desk#score");
    o.engine = jvmcontract::Engine::Jbmc;
    let refused = equivalence::run(&o).unwrap();
    assert!(refused.problem.as_deref().unwrap_or_default().contains("takes a String"), "{}", refused.output);

    // A plan of the desk and the request: the region and the code each the String adapter's.
    let plan = |code: serde_json::Value| -> jvmcontract::construction::Plans {
        let string = |path: &str| serde_json::json!({"kind": "adapted", "path": path, "domain": {"kind": {"kind": "string"}, "nullable": false, "max_length": 3, "model": {"source": "the values stream's String model", "jdk": "computed by cache::key", "level": "modelled"}}});
        let one = serde_json::json!({
            "nodes": [
                {"id": 0, "class": "strs.Desk", "maker": {"kind": "constructor", "descriptor": "(Ljava/lang/String;)V"}, "args": [string("this.region")]},
                {"id": 1, "class": "strs.Request", "maker": {"kind": "constructor", "descriptor": "(Ljava/lang/String;I)V"}, "args": [code, {"kind": "leaf", "path": "r.count", "type": "int"}]}
            ],
            "roots": [{"name": "this", "value": {"kind": "node", "id": 0}}, {"name": "r", "value": {"kind": "node", "id": 1}}],
            "restrictions": ["the desk and the request made by their constructors"],
            "bounds": {"nodes": 2, "max_array_length": 3, "setup_calls": 0}
        });
        serde_json::from_value(serde_json::json!({"before": one, "after": one})).unwrap()
    };
    let string = |path: &str, nullable: bool, max_length: u32| serde_json::json!({"kind": "adapted", "path": path, "domain": {"kind": {"kind": "string"}, "nullable": nullable, "max_length": max_length, "model": {"source": "the values stream's String model", "jdk": "computed by cache::key", "level": "modelled"}}});
    let after = desk("plan-after", "    public int score(Request r) { return r.code.length() > 0 && r.code.charAt(0) == 'V' ? r.count * 2 : r.count; }\n");
    let defect = desk("plan-defect", "    public int score(Request r) { return r.code.startsWith(\"VI\") ? r.count * 2 : r.count; }\n");
    let planned = |name: &str, after: &Path, code: serde_json::Value| {
        let mut o = options(name, &before, after, "strs.Desk#score");
        o.plan = Some(plan(code));
        equivalence::run(&o).unwrap()
    };
    let o = planned("plan", &after, string("r.code", false, 3));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let o = planned("plan-defect", &defect, string("r.code", false, 3));
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.replay.as_ref().is_some_and(|r| r.reproduced), "{}", o.output);
    let o = planned("plan-bound", &after, string("r.code", false, 2));
    assert!(o.problem.as_deref().unwrap_or_default().contains("bounds the String r.code at 2 code units, and the check bounds every String at 3"), "{}", o.output);
    let o = planned("plan-null", &after, string("r.code", true, 3));
    assert!(o.problem.as_deref().unwrap_or_default().contains("a String that may be null"), "{}", o.output);
    let o = planned("plan-misnamed", &after, string("r.name", false, 3));
    assert!(o.problem.as_deref().unwrap_or_default().contains("which the check names r.code"), "{}", o.output);
    let list = serde_json::json!({"kind": "adapted", "path": "r.code", "domain": {"kind": {"kind": "list", "element": {"kind": "object", "class": "strs.Request"}}, "nullable": false, "max_length": 3, "model": {"source": "the values stream's List.of/List.copyOf model", "jdk": "computed by cache::key", "level": "modelled"}}});
    let o = planned("plan-list", &after, list);
    assert!(o.problem.as_deref().unwrap_or_default().contains("other than a String"), "{}", o.output);
}

/// The cached evidence: a proof over a String inside an object is reused by its exact rerun; under another String
/// bound it is another claim, proved again; and an edit of the constructor that takes the String is another claim.
#[test]
fn a_cached_proof_over_a_string_inside_an_object_is_tied_to_its_bound_and_its_constructor() {
    let cache = tmp("cache");
    let _ = std::fs::remove_dir_all(&cache);
    let before = desk("cache-before", BEFORE);
    let after = desk("cache-after", "    public int score(Request r) { return r.code.length() > 0 && r.code.charAt(0) == 'V' ? r.count * 2 : r.count; }\n");
    let run = |name: &str, after: &Path, bound: u32| {
        let mut o = options(name, &before, after, "strs.Desk#score");
        o.cache = Some(cache.clone());
        o.max_array_length = bound;
        equivalence::run(&o).unwrap()
    };
    let cold = run("cache-cold", &after, 3);
    assert_eq!(cold.verdict, Verdict::Verified, "{}", cold.output);
    assert!(cold.reuse.is_none(), "{:?}", cold.reuse);
    let rerun = run("cache-rerun", &after, 3);
    let Some(Reuse::Exact { key, .. }) = &rerun.reuse else { panic!("the exact rerun is the stored proof: {:?}", rerun.reuse) };
    let other_bound = run("cache-bound", &after, 2);
    assert_eq!(other_bound.verdict, Verdict::Verified, "{}", other_bound.output);
    assert!(other_bound.reuse.is_none(), "another String bound is another claim: {:?}", other_bound.reuse);
    let edited = desk_with("cache-edited", "    public int score(Request r) { return r.code.length() > 0 && r.code.charAt(0) == 'V' ? r.count * 2 : r.count; }\n", "        if (code.length() > 2) { throw new IllegalArgumentException(\"a short code\"); }\n");
    let o = run("cache-edited", &edited, 3);
    match &o.reuse {
        None => {}
        Some(Reuse::Exact { key: k, .. }) => panic!("an edit of the constructor that takes the String is another claim, never the stored proof {k:?} (first {key:?})"),
        Some(other) => panic!("{other:?}"),
    }
    // The edited constructor rejects a code the previous one admits: a difference on the exception.
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
}
