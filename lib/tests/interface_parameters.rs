//! A parameter of an interface type (`jvmcontract::given`): a property check gives it an implementation that answers
//! the accessors the target may call, each with one value, and reads an interface's object, a parameter or the
//! result, through its accessors, a String by `equals` against a literal. The fixture is the shape of example 285
//! (`WebMvcTags.method(HttpServletRequest)`): a request's method made a metric tag's value, raw in one method and
//! through an enum's map of names (filled by its class initializer) in another, the tag an interface whose
//! implementation checks its arguments with `Objects.requireNonNull`, and a class initializer that compiles a regular
//! expression the method never uses. Each part has a proof, a planted defect replayed on a JVM, and a named
//! boundary.

use std::path::PathBuf;
use std::process::Command;

use jvmcontract::bmc::gaps::GapMode;
use jvmcontract::{property, Engine, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";

fn tmp(part: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("interface-parameters").join(part)
}

const SOURCES: &[(&str, &str)] = &[
    ("Named", "public interface Named {\n    String getName();\n}\n"),
    (
        "Request",
        "public interface Request extends Named {\n    String getMethod();\n    int getPort();\n    String getHeader(String name);\n    default boolean isGet() {\n        return \"GET\".equals(getMethod());\n    }\n}\n",
    ),
    (
        "Tag",
        "public interface Tag {\n    String getKey();\n    String getValue();\n    static Tag of(String key, String value) {\n        return new ImmutableTag(key, value);\n    }\n}\n",
    ),
    (
        "ImmutableTag",
        "final class ImmutableTag implements Tag {\n    private final String key;\n    private final String value;\n    ImmutableTag(String key, String value) {\n        this.key = java.util.Objects.requireNonNull(key);\n        this.value = java.util.Objects.requireNonNull(value);\n    }\n    public String getKey() {\n        return key;\n    }\n    public String getValue() {\n        return value;\n    }\n}\n",
    ),
    (
        "Verb",
        "import java.util.HashMap;\nimport java.util.Map;\npublic enum Verb {\n    GET, PUT;\n    private static final Map<String, Verb> mappings = new HashMap<>(4);\n    static {\n        for (Verb verb : values()) {\n            mappings.put(verb.name(), verb);\n        }\n    }\n    public static Verb resolve(String method) {\n        return method != null ? mappings.get(method) : null;\n    }\n}\n",
    ),
    (
        "Tags",
        "import java.util.regex.Pattern;\npublic final class Tags {\n    private static final Tag UNKNOWN = Tag.of(\"method\", \"UNKNOWN\");\n    private static final Pattern SLASHES = Pattern.compile(\"//+\");\n    public static Tag raw(Request request) {\n        return request != null ? Tag.of(\"method\", request.getMethod()) : UNKNOWN;\n    }\n    public static Tag bounded(Request request) {\n        if (request != null) {\n            Verb verb = Verb.resolve(request.getMethod());\n            if (verb != null) {\n                return Tag.of(\"method\", verb.name());\n            }\n        }\n        return UNKNOWN;\n    }\n    public static Tag header(Request request) {\n        return Tag.of(\"header\", request.getHeader(\"x\"));\n    }\n    public static int port(Request request) {\n        return request.isGet() ? request.getPort() : 80;\n    }\n    public static int portOf(Request request) {\n        return request.getPort();\n    }\n    public static int none(Request request) {\n        return request == null ? 0 : 1;\n    }\n}\n",
    ),
    ("Lookup", "interface Lookup {\n    Verb find(String method);\n}\n"),
    ("Exact", "final class Exact implements Lookup {\n    public Verb find(String method) {\n        return Verb.resolve(method);\n    }\n}\n"),
    ("Fuzzy", "final class Fuzzy implements Lookup {\n    public Verb find(String method) {\n        return method.length() * 0.5 > 1.0 ? Verb.GET : null;\n    }\n}\n"),
    (
        "Defaults",
        "public final class Defaults {\n    static final Lookup LOOKUP = new Exact();\n    static final Verb VERB = LOOKUP.find(\"GET\");\n    public static Tag tag(Request request) {\n        return request == null ? Tag.of(\"method\", VERB.name()) : Tags.bounded(request);\n    }\n}\n",
    ),
    (
        "Routes",
        "import java.util.regex.Pattern;\npublic final class Routes {\n    private static final Pattern VARIABLE = Pattern.compile(\"\\\\{[^/]+?\\\\}\");\n    public static int port(Request request) {\n        return request.getPort();\n    }\n}\n",
    ),
];

/// The fixture's classes, compiled once for the tests of this file, which run in parallel.
fn classes() -> PathBuf {
    static CLASSES: std::sync::OnceLock<PathBuf> = std::sync::OnceLock::new();
    CLASSES
        .get_or_init(|| {
            let root = tmp("fixture");
            let _ = std::fs::remove_dir_all(&root);
            let src = root.join("src/web");
            std::fs::create_dir_all(&src).unwrap();
            let mut files = Vec::new();
            for (name, text) in SOURCES {
                let file = src.join(format!("{name}.java"));
                std::fs::write(&file, format!("package web;\n{text}")).unwrap();
                files.push(file);
            }
            let out = root.join("classes");
            let status = Command::new("javac").args(["-g", "-proc:none", "-nowarn", "-d"]).arg(&out).args(&files).status().expect("the tests need javac");
            assert!(status.success(), "the fixture compiles");
            out
        })
        .clone()
}

/// A property check of `web.{target}` by the own checker under strict gaps, with Strings of at most 4 code units.
fn options(name: &str, target: &str, assert: &str) -> property::Options {
    let mut options = property::Options::new(&[classes()], &format!("web.{target}"));
    options.engine = Engine::Native;
    options.gaps = GapMode::Strict;
    options.jbmc = NO_JBMC.into();
    options.max_array_length = 4;
    options.assert = Some(assert.into());
    let work = tmp(&format!("work-{name}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    options
}

fn check(name: &str, target: &str, assert: &str, with: impl FnOnce(&mut property::Options)) -> property::Outcome {
    let mut options = options(name, target, assert);
    with(&mut options);
    property::run(&options).unwrap()
}

/// The claim of example 285 over the fixture's two verbs: a tag of key `method` whose value is one of the known ones.
const BOUNDED: &str = "result != null && result.getKey().equals(\"method\") && (result.getValue().equals(\"GET\") || result.getValue().equals(\"PUT\") || result.getValue().equals(\"UNKNOWN\"))";

const METHOD_ONLY: &str = "request: an implementation of Request that answers getMethod() (a String of ≤ 4 code units, not null) with one value on every call, and no other abstract method";

/// The bounded-label claim. The method that resolves the request's method through the enum's map is proved for every
/// request, null included: the map is the one the enum's initializer filled, and the tag's `requireNonNull` and the
/// initializer's `Pattern.compile` run as written. The method that passes the request's method on is refuted, on the
/// empty method, and so is the bounded one once the claim forgets a verb, on that verb: each witness is the given
/// implementation by what its accessor answers, run on a JVM. Under an assumption on the accessor, the raw method is
/// proved, and the assumption is seen to admit an input. Before, a parameter of an interface type was refused by
/// name, and an expression had no String to read.
#[test]
fn a_property_over_an_interface_parameter_is_proved_and_refuted_through_its_accessors() {
    jvmcontract::tool_tier!();
    let nullable = |o: &mut property::Options| o.nullable = vec!["request".into()];

    let o = check("bounded", "Tags#bounded", BOUNDED, nullable);
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert_eq!(o.domain.as_deref(), Some(format!("{METHOD_ONLY}, or null").as_str()), "{}", o.output);

    let o = check("raw", "Tags#raw", BOUNDED, nullable);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.output.contains("raw(request=Request{getMethod()=\"\"})\n    outcome: ImmutableTag{key=\"method\", value=\"\"}\n"), "{}", o.output);
    assert!(o.output.contains("replayed in the interpreter and run on a JVM"), "{}", o.output);
    // As data: the parameter is its interface by what each accessor answers, and the statement says that the
    // property is about the implementation given, and the String model and bound it ran under.
    let witness = serde_json::to_value(&o.counterexample).unwrap();
    assert_eq!(witness["call"]["arguments"][0], serde_json::json!({"name": "request", "type": "web.Request", "components": [{"name": "getMethod()", "type": "java.lang.String", "value": {"kind": "string", "units": []}, "from": "request.getMethod"}]}), "{witness}");
    let stated = serde_json::to_value(&o.stated).unwrap();
    assert_eq!(stated["domain"]["parameters"][0]["type"], "web.Request", "{stated}");
    assert_eq!(stated["domain"]["parameters"][0]["components"], serde_json::json!(["getMethod(): java.lang.String"]), "{stated}");
    assert_eq!(stated["assumptions"][0], serde_json::json!({"kind": "environment", "text": "request is an implementation of web.Request the check gives: getMethod() returns one value, the same on every call, and throws nothing, and it answers no other abstract method; an implementation that answers a call another way (a value that changes between calls, an exception) is outside the property", "basis": "harness"}), "{stated}");
    assert_eq!(stated["bounds"]["max_value_length"], 4, "{stated}");
    assert!(stated["models"]["values"][0]["source"].as_str().is_some_and(|m| m.starts_with(jvmcontract::values::STRING_MODEL)), "{stated}");

    let o = check("forgotten", "Tags#bounded", "result.getValue().equals(\"GET\") || result.getValue().equals(\"UNKNOWN\")", |_| ());
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.output.contains("bounded(request=Request{getMethod()=\"PUT\"})\n    outcome: ImmutableTag{key=\"method\", value=\"PUT\"}\n"), "{}", o.output);
    assert_eq!(o.domain.as_deref(), Some(METHOD_ONLY), "{}", o.output);

    let o = check("assumed", "Tags#raw", BOUNDED, |o| o.assume = Some("request.getMethod().equals(\"GET\") || request.getMethod().equals(\"PUT\")".into()));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.vacuous.is_none() && o.output.contains("  not vacuous: raw(request=Request{getMethod()=\""), "{}", o.output);
}

/// The implementation answers the accessors the target may call, and those alone: the interface's default method
/// runs as written over the accessor it calls, two accessors are two inputs, and a target that calls none is given
/// an implementation that answers nothing, or null.
#[test]
fn the_given_implementation_answers_the_accessors_the_target_may_call() {
    jvmcontract::tool_tier!();
    let o = check("port", "Tags#port", "result == 80 || (request.getMethod().equals(\"GET\") && result == request.getPort())", |_| ());
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert_eq!(o.domain.as_deref(), Some("request: an implementation of Request that answers getMethod() (a String of ≤ 4 code units, not null) and getPort() (an int), each with one value on every call, and no other abstract method"), "{}", o.output);

    let o = check("port-80", "Tags#port", "result == 80", |_| ());
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.output.contains("port(request=Request{getMethod()=\"GET\", getPort()=0})\n    outcome: 0\n"), "{}", o.output);
    assert!(o.output.contains("run on a JVM"), "{}", o.output);

    let o = check("none", "Tags#none", "result == 1", |o| o.nullable = vec!["request".into()]);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.output.contains("none(request=null)\n    outcome: 0\n"), "{}", o.output);
    assert_eq!(o.domain.as_deref(), Some("request: an implementation of Request that answers none of its abstract methods, or null"), "{}", o.output);
}

/// What the implementation doesn't answer is named, never passed over. A call of an abstract method that takes an
/// argument is a gap the strict checker refuses by name; an expression reads the accessors the implementation
/// answers, and is told which when it asks for a default method, an accessor the target doesn't call or a field;
/// and a class initializer that compiles a regular expression with a reluctant quantifier is the JDK call it is, a
/// named gap, where the plain `//+` of the other class is none. That the other checker is not given an implementation is
/// `a_domain_jbmc_is_not_given_is_refused_by_name`'s, in `tests/conformance.rs`.
#[test]
fn what_a_given_implementation_does_not_answer_is_refused_by_name() {
    jvmcontract::tool_tier!();
    let refused = |name: &str, target: &str, assert: &str, with: &dyn Fn(&mut property::Options), words: &str| {
        let o = check(name, target, assert, with);
        assert_eq!(o.verdict, Verdict::Unverifiable, "{name}: {}", o.output);
        assert!(o.problem.as_deref().unwrap_or_default().contains(words), "{name}: {}", o.output);
    };
    refused("header", "Tags#header", "result != null", &|_| (), "web.Request.getHeader(java.lang.String) at web.Tags.header");
    refused("default-method", "Tags#port", "result == 80 || request.isGet()", &|_| (), "web.Request has no isGet() the expressions can read; they can read getMethod(), getPort()");
    refused("uncalled", "Tags#portOf", "result == 80 || request.getName().equals(\"\")", &|_| (), "web.Request has no getName() the expressions can read; they can read getPort()");
    refused("field", "Tags#portOf", "request.port == result", &|_| (), "web.Request has no port the expressions can read; they can read getPort()");
    refused("regex", "Routes#port", "result == request.getPort()", &|_| (), "java.util.regex.Pattern.compile(java.lang.String)");
}

/// The gap scan follows a virtual or interface call into the classes of the objects it has seen made, and no other
/// (rapid type analysis), and classifies the call once it has seen them all. A class initializer that calls an
/// interface method on the one implementation it makes runs, though another implementation, never made, does
/// floating-point arithmetic the checker has none of: the claim over it is proved under strict gaps. The scan walks
/// the enum's map through the `HashMap` model, counts the map's calls as the model's, and reports as gaps only what
/// the model's key comparison may reach on a key that is no String; the plain regular expression is no gap, the one
/// with a reluctant quantifier is. Before, a call was followed into every class below its owner: the fixed release of
/// example 285 reached every `Map` of its libraries from `HttpMethod`'s initializer, which was judged outside the
/// fragment for what one of them does, and the scan took over two minutes.
#[test]
fn the_scan_follows_a_call_into_the_classes_of_the_objects_made() {
    jvmcontract::tool_tier!();
    use jvmcontract::bmc::gaps;
    let o = check("defaults", "Defaults#tag", BOUNDED, |o| o.nullable = vec!["request".into()]);
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);

    let mut cp = jvmcontract::classpath::ClassPath::new();
    cp.add(&classes()).unwrap();
    let cp = cp.with_default_jdk();
    let scan = |target: &str| gaps::scan(&cp, &gaps::roots(&cp, &[format!("web.{target}")]).unwrap()).unwrap();
    let defaults = scan("Defaults#tag");
    assert!(defaults.refused.is_empty(), "{:?}", defaults.refused);
    assert!(defaults.methods.iter().any(|m| m.starts_with("web.Exact.find")) && !defaults.methods.iter().any(|m| m.starts_with("web.Fuzzy")), "{:?}", defaults.methods);
    assert!(defaults.methods.iter().any(|m| m.starts_with("java.util.HashMap.put")) && defaults.methods.iter().any(|m| m.starts_with("java.util.HashMap.get")), "{:?}", defaults.methods);
    assert!(defaults.exact.keys().any(|k| k == "java.util.Map.get(Ljava/lang/Object;)Ljava/lang/Object; (on the map model)"), "{:?}", defaults.exact);
    assert!(defaults.exact.contains_key("java.util.regex.Pattern.compile") && defaults.exact.contains_key("java.util.Objects.requireNonNull"), "{:?}", defaults.exact);
    let ids = |s: &gaps::Scan| s.gaps.keys().map(|g| g.id(None)).collect::<Vec<_>>();
    assert_eq!(ids(&defaults), ["jdk-primitive-method:java.lang.Object.equals(Ljava/lang/Object;)Z", "jdk-primitive-method:java.lang.Object.hashCode()I"], "what a key that is no String may reach");
    // The calls a target may make on the interface it is given an implementation of.
    let calls = |target: &str| gaps::calls_on_given(&cp, &gaps::roots(&cp, &[format!("web.{target}")]).unwrap(), "web/Request").unwrap().into_iter().map(|(name, descriptor)| format!("{name}{descriptor}")).collect::<Vec<_>>();
    assert_eq!(calls("Tags#port"), ["getMethod()Ljava/lang/String;", "getPort()I", "isGet()Z"]);
    assert_eq!(calls("Tags#header"), ["getHeader(Ljava/lang/String;)Ljava/lang/String;"]);
    assert!(calls("Tags#none").is_empty());
    // A regular expression with a reluctant quantifier is the JDK call it names: one with a class alone is none since
    // example 287 (`bmc::regex::compiles_constant`, shown in `tests/claims.rs`).
    assert!(ids(&scan("Routes#port")).contains(&"jdk-static-method:java.util.regex.Pattern.compile(Ljava/lang/String;)Ljava/util/regex/Pattern;".to_string()));
}
