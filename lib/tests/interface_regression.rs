//! A regression check over a parameter of an interface type, between two versions that each have a dependency
//! closure of their own (`--before-classpath`): the shape of example 285's `preservation`, Spring Boot 2.7.17
//! against 2.7.18, each with its own micrometer and Spring Framework. Both versions are given an implementation of
//! the interface made from the same accessor values (`jvmcontract::given`), their results, of an interface type, are
//! compared through its accessors, a String by content, and the previous version's whole closure is relocated, so
//! that a library class the two closures hold differently is each version's own.

use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::{equivalence, Engine, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";

fn tmp(part: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("interface-regression").join(part)
}

const REQUEST: &str = "package web;\npublic interface Request {\n    String getMethod();\n    int getPort();\n}\n";
const TAG: &str = "package web;\npublic interface Tag {\n    String getKey();\n    String getValue();\n    static Tag of(String key, String value) {\n        return new ImmutableTag(key, value);\n    }\n}\n";
/// The tag of the previous closure, and the next one's, which checks its arguments: other bytes under one name.
const TAG_1: &str = "package web;\nfinal class ImmutableTag implements Tag {\n    private final String key;\n    private final String value;\n    ImmutableTag(String key, String value) {\n        this.key = key;\n        this.value = value;\n    }\n    public String getKey() {\n        return key;\n    }\n    public String getValue() {\n        return value;\n    }\n}\n";
const TAG_2: &str = "package web;\nfinal class ImmutableTag implements Tag {\n    private final String key;\n    private final String value;\n    ImmutableTag(String key, String value) {\n        this.key = java.util.Objects.requireNonNull(key);\n        this.value = java.util.Objects.requireNonNull(value);\n    }\n    public String getKey() {\n        return key;\n    }\n    public String getValue() {\n        return value;\n    }\n}\n";
/// Only the next closure has the enum the fix resolves a method through.
const VERB: &str = "package web;\nimport java.util.HashMap;\nimport java.util.Map;\npublic enum Verb {\n    GET, PUT;\n    private static final Map<String, Verb> mappings = new HashMap<>(4);\n    static {\n        for (Verb verb : values()) {\n            mappings.put(verb.name(), verb);\n        }\n    }\n    public static Verb resolve(String method) {\n        return method != null ? mappings.get(method) : null;\n    }\n}\n";

fn tags(body: &str) -> String {
    format!("package app;\nimport web.Request;\nimport web.Tag;\npublic final class Tags {{\n    private static final Tag UNKNOWN = Tag.of(\"method\", \"UNKNOWN\");\n    public static Tag method(Request request) {{\n{body}        return UNKNOWN;\n    }}\n}}\n")
}

const RAW: &str = "        if (request != null) {\n            return Tag.of(\"method\", request.getMethod());\n        }\n";
const BOUNDED: &str = "        if (request != null) {\n            web.Verb verb = web.Verb.resolve(request.getMethod());\n            if (verb != null) {\n                return Tag.of(\"method\", verb.name());\n            }\n        }\n";
const ALWAYS_UNKNOWN: &str = "";
const PORT_TOO: &str = "        if (request != null) {\n            web.Verb verb = web.Verb.resolve(request.getMethod());\n            if (verb != null) {\n                return Tag.of(\"method\", request.getPort() == 81 ? \"ALT\" : verb.name());\n            }\n        }\n";

/// Compiles `sources` (path, text) into `tmp(name)/classes`, against `classpath`.
fn compile(name: &str, sources: &[(&str, String)], classpath: &[&Path]) -> PathBuf {
    let root = tmp(name);
    let _ = std::fs::remove_dir_all(&root);
    let mut files = Vec::new();
    for (path, text) in sources {
        let file = root.join("src").join(path);
        std::fs::create_dir_all(file.parent().unwrap()).unwrap();
        std::fs::write(&file, text).unwrap();
        files.push(file);
    }
    let out = root.join("classes");
    let mut javac = Command::new("javac");
    javac.args(["-g", "-proc:none", "-nowarn", "-d"]).arg(&out);
    if !classpath.is_empty() {
        javac.arg("-cp").arg(classpath.iter().map(|p| p.display().to_string()).collect::<Vec<_>>().join(":"));
    }
    assert!(javac.args(&files).status().expect("the tests need javac").success(), "{name} compiles");
    out
}

struct Fixture {
    /// The previous closure and the next one.
    libraries: (PathBuf, PathBuf),
    raw: PathBuf,
}

fn fixture() -> &'static Fixture {
    static FIXTURE: std::sync::OnceLock<Fixture> = std::sync::OnceLock::new();
    FIXTURE.get_or_init(|| {
        let one = compile("library-1", &[("web/Request.java", REQUEST.into()), ("web/Tag.java", TAG.into()), ("web/ImmutableTag.java", TAG_1.into())], &[]);
        let two = compile("library-2", &[("web/Request.java", REQUEST.into()), ("web/Tag.java", TAG.into()), ("web/ImmutableTag.java", TAG_2.into()), ("web/Verb.java", VERB.into())], &[]);
        let raw = compile("raw", &[("app/Tags.java", tags(RAW))], &[&one]);
        Fixture { libraries: (one, two), raw }
    })
}

/// The next version of `Tags`, compiled against the next closure.
fn next(name: &str, body: &str) -> PathBuf {
    compile(name, &[("app/Tags.java", tags(body))], &[&fixture().libraries.1])
}

fn options(name: &str, after: &Path) -> equivalence::Options {
    let f = fixture();
    let mut options = equivalence::Options::new(&f.raw, after, "app.Tags#method");
    options.classpath = vec![f.libraries.1.clone()];
    options.before_classpath = Some(vec![f.libraries.0.clone()]);
    options.engine = Engine::Native;
    options.jbmc = NO_JBMC.into();
    options.max_array_length = 4;
    options.nullable = vec!["request".into()];
    let work = tmp(&format!("work-{name}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    options
}

/// The allowed change of example 285's `preservation`, over the fixture's two verbs.
const UNLESS: &str = "request != null && !(request.getMethod().equals(\"GET\") || request.getMethod().equals(\"PUT\"))";

/// The fix against the release before it, each with its own closure. Outside the declared change (a request whose
/// method is no known verb) the two give the same tag, by key and value, for every request and for null: proved.
/// With no change declared the fix is refuted on a method that is no verb, each version's tag shown and the witness
/// run on a JVM; a version that labels every request UNKNOWN is refuted on a known verb, inside what was to be
/// preserved, as is one that reads a second accessor the previous version never called. Before, the check refused
/// an interface parameter by name, and two closures could not be given at all. The previous version's libraries are
/// relocated with it, those it names and no others, so the two tags, of two classes of one name, are each version's.
#[test]
fn a_fix_over_an_interface_parameter_is_preserved_outside_its_declared_change_across_two_closures() {
    jvmcontract::tool_tier!();
    let bounded = next("bounded", BOUNDED);

    let mut o = options("preserved", &bounded);
    o.unchanged_unless = Some(UNLESS.into());
    let proved = equivalence::run(&o).unwrap();
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);
    assert!(proved.domain.as_deref().unwrap_or_default().contains("request: an implementation of Request that answers getMethod() (a String of ≤ 4 code units, not null) with one value on every call, and no other abstract method, or null"), "{}", proved.output);
    // The statement says what the claim is about: the implementation given, the declared change as Java reads it,
    // and the results compared through the interface's accessors.
    let stated = serde_json::to_string(&proved.stated).unwrap();
    for words in [
        "request is an implementation of web.Request the check gives: getMethod() returns one value, the same on every call, and throws nothing, and it answers no other abstract method; both versions are given one of the same values",
        "an input on which the expression throws (a call on a null object) is not among them either, and the versions are compared on it",
        "the result, a Tag compared through its accessors, whatever class each version's object is of (getKey(), getValue()), two nulls agreeing",
    ] {
        assert!(stated.contains(words), "{words}: {stated}");
    }

    let refuted = equivalence::run(&options("undeclared", &bounded)).unwrap();
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    assert!(refuted.output.contains("method(request=Request{getMethod()=\"\"})"), "{}", refuted.output);
    assert!(refuted.output.contains("ImmutableTag{key=\"method\", value=\"\"}") && refuted.output.contains("ImmutableTag{key=\"method\", value=\"UNKNOWN\"}"), "{}", refuted.output);
    assert!(refuted.replay.as_ref().is_some_and(|r| r.reproduced), "{}", refuted.output);

    let mut o = options("always-unknown", &next("always-unknown", ALWAYS_UNKNOWN));
    o.unchanged_unless = Some(UNLESS.into());
    let refuted = equivalence::run(&o).unwrap();
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    assert!(refuted.output.contains("getMethod()=\"GET\"") || refuted.output.contains("getMethod()=\"PUT\""), "{}", refuted.output);
    assert!(refuted.replay.as_ref().is_some_and(|r| r.reproduced), "{}", refuted.output);

    let mut o = options("port-too", &next("port-too", PORT_TOO));
    o.unchanged_unless = Some(UNLESS.into());
    let refuted = equivalence::run(&o).unwrap();
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    assert!(refuted.output.contains("getPort()=81"), "{}", refuted.output);
    assert!(refuted.domain.as_deref().unwrap_or_default().contains("answers getMethod() (a String of ≤ 4 code units, not null) and getPort() (an int), each with one value on every call"), "{}", refuted.output);

    // A previous version that names a class only the new closure has finds no such class, as on its own class
    // path: it never runs on the new version's.
    let mut o = options("absent", &bounded);
    o.before = bounded.clone();
    o.unchanged_unless = Some(UNLESS.into());
    let absent = equivalence::run(&o).unwrap();
    assert_ne!(absent.verdict, Verdict::Verified, "{}", absent.output);
    assert!(absent.output.contains("before.web.Verb"), "{}", absent.output);

    // The previous version's copy of each library class it names, and of nothing else: `Verb` is the new closure's.
    let relocated = |class: &str| tmp("work-preserved").join("before-classes/before").join(format!("{class}.class")).exists();
    assert!(relocated("app/Tags") && relocated("web/Request") && relocated("web/Tag") && relocated("web/ImmutableTag") && !relocated("web/Verb"));
}

/// A method of each boundary below, beside the tag's: a result read through no accessor alone, and a second
/// parameter made by its constructor.
const MORE: &str = "    public static web.Chain chain(Request request) {\n        return null;\n    }\n    public static Tag limited(Request request, web.Limit limit) {\n        return method(request);\n    }\n";
const CHAIN: &str = "package web;\npublic interface Chain {\n    String getKey();\n    Chain next();\n}\n";
const LIMIT: &str = "package web;\npublic final class Limit {\n    private final int max;\n    public Limit(int max) {\n        this.max = max;\n    }\n    public int max() {\n        return max;\n    }\n}\n";
/// As the fix, but a null request is labelled NONE: a change on an input the declared change may or may not name.
const NULL_IS_NONE: &str = "        if (request == null) {\n            return Tag.of(\"method\", \"NONE\");\n        }\n        web.Verb verb = web.Verb.resolve(request.getMethod());\n        if (verb != null) {\n            return Tag.of(\"method\", verb.name());\n        }\n";

/// One version whole in one directory, its library with it: no class path beside the builds.
fn whole(name: &str, body: &str, tag: &str, verb: bool) -> PathBuf {
    let mut sources = vec![("web/Request.java", REQUEST.to_string()), ("web/Tag.java", TAG.into()), ("web/ImmutableTag.java", tag.into()), ("web/Chain.java", CHAIN.into()), ("web/Limit.java", LIMIT.into())];
    if verb {
        sources.push(("web/Verb.java", VERB.into()));
    }
    sources.push(("app/Tags.java", tags(body).replacen("    public static Tag method", &format!("{MORE}    public static Tag method"), 1)));
    compile(name, &sources, &[])
}

fn whole_options(name: &str, before: &Path, after: &Path, target: &str) -> equivalence::Options {
    let mut options = equivalence::Options::new(before, after, target);
    options.engine = Engine::Native;
    options.jbmc = NO_JBMC.into();
    options.max_array_length = 4;
    options.nullable = vec!["request".into()];
    let work = tmp(&format!("work-{name}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    options
}

/// The same claim where each version's build holds its own interfaces, with no class path beside them, and the
/// named boundaries. A declared change is read as Java reads it: on a null request `request.getMethod()` throws, so
/// the input is not one the change is meant for, and a version that labels it otherwise is refuted there; declared
/// (`request == null || ...`), it is proved. A result of an interface with an abstract method that is no accessor
/// is refused by name, since what that method answers would not be compared; so is a declared change that reads
/// the given object beside an object made by its constructor, a previous method under another name, and an
/// accessor the previous version's interface doesn't have.
#[test]
fn a_regression_check_over_an_interface_parameter_names_what_it_is_not_given() {
    jvmcontract::tool_tier!();
    let raw = whole("whole-raw", RAW, TAG_1, false);
    let bounded = whole("whole-bounded", BOUNDED, TAG_2, true);
    let mut o = whole_options("whole", &raw, &bounded, "app.Tags#method");
    o.unchanged_unless = Some(UNLESS.into());
    let proved = equivalence::run(&o).unwrap();
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);

    let none = whole("whole-null-is-none", NULL_IS_NONE, TAG_2, true);
    let unless = "!(request.getMethod().equals(\"GET\") || request.getMethod().equals(\"PUT\"))";
    let mut o = whole_options("throws", &raw, &none, "app.Tags#method");
    o.unchanged_unless = Some(unless.into());
    let refuted = equivalence::run(&o).unwrap();
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    assert!(refuted.output.contains("method(request=null)") && refuted.output.contains("value=\"NONE\""), "{}", refuted.output);
    let mut o = whole_options("null-declared", &raw, &none, "app.Tags#method");
    o.unchanged_unless = Some(format!("request == null || {unless}"));
    let proved = equivalence::run(&o).unwrap();
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);

    let refused = |name: &str, target: &str, change: &dyn Fn(&mut equivalence::Options), words: &str| {
        let mut o = whole_options(name, &raw, &bounded, target);
        change(&mut o);
        let outcome = equivalence::run(&o).unwrap();
        assert_eq!(outcome.verdict, Verdict::Unverifiable, "{name}: {}", outcome.output);
        assert!(outcome.output.contains(words), "{name}: {}", outcome.output);
    };
    refused("chain", "app.Tags#chain", &|_| {}, "web.Chain is an interface each version has its own copy of, so two results are compared through its accessors, and its abstract method next(): web.Chain is none");
    refused("limited", "app.Tags#limited", &|o| o.unchanged_unless = Some("request != null".into()), "--unchanged-unless reads an object the check gives an implementation of (request), and limit is an object or a record made by its constructor");
    refused("renamed", "app.Tags#method", &|o| o.before_target = Some("app.Tags#limited".into()), "parameter request is of the interface web.Request: an interface parameter with --before-target");

    // A previous closure whose interface lacks an accessor the new version calls.
    let narrow = compile("library-0", &[("web/Request.java", REQUEST.replace("    int getPort();\n", "")), ("web/Tag.java", TAG.into()), ("web/ImmutableTag.java", TAG_1.into())], &[]);
    let raw = compile("raw-0", &[("app/Tags.java", tags(RAW))], &[&narrow]);
    let mut o = options("narrow", &next("port-too-narrow", PORT_TOO));
    o.before = raw;
    o.before_classpath = Some(vec![narrow]);
    let outcome = equivalence::run(&o).unwrap();
    assert_eq!(outcome.verdict, Verdict::Unverifiable, "{}", outcome.output);
    assert!(outcome.output.contains("whose accessor getPort() the previous version's web.Request doesn't have"), "{}", outcome.output);
}
