//! A regression check made as a property of the pair of versions (`jvmcontract::pairing`): the shape of example
//! 288's `preservation`, Spring Framework 6.1.13 against 6.1.14 through an adapter that takes a `String[]` and sets
//! the default locale. One generated method calls both versions, each on its own library and its own copy of an
//! array, and the property check proves that it returns true on every input of the assumption outside the allowed
//! change, or refutes it on a witness run on a JVM.

use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::{equivalence, Engine, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";

fn tmp(part: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("pairing").join(part)
}

/// A deny list that lower-cases both sides: under the default locale, or under the root locale.
fn deny(lower: &str) -> String {
    format!("package lib;\npublic final class Deny {{\n    public static boolean denied(String[] names, String field) {{\n        if (names == null) {{\n            return false;\n        }}\n        for (String name : names) {{\n            if (name != null && name{lower}.equals(field{lower})) {{\n                return true;\n            }}\n        }}\n        return false;\n    }}\n}}\n")
}

/// The entry: the default locale from a table (the root locale, Turkish), then the library's decision. `{0}` is
/// what it does to the array it was given, after reading it.
fn entry(after: &str) -> String {
    format!("package app;\nimport java.util.Locale;\npublic final class Entry {{\n    static final Locale[] LOCALES = {{Locale.ROOT, Locale.forLanguageTag(\"tr-TR\")}};\n    public static boolean allowed(int locale, String[] names, String field) {{\n        Locale.setDefault(LOCALES[locale]);\n        boolean denied = lib.Deny.denied(names, field);\n{after}        return !denied;\n    }}\n    public boolean instance(String[] names) {{\n        return names == null;\n    }}\n    public static boolean checked(String[] names) throws java.io.IOException {{\n        return names == null;\n    }}\n}}\n")
}

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
    javac.args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out);
    if !classpath.is_empty() {
        javac.arg("-cp").arg(classpath.iter().map(|p| p.display().to_string()).collect::<Vec<_>>().join(":"));
    }
    assert!(javac.args(&files).status().expect("the tests need javac").success(), "{name} compiles");
    out
}

struct Fixture {
    /// The library that reads the default locale, and the one that reads the root locale.
    libraries: (PathBuf, PathBuf),
    /// The entry compiled against each.
    entries: (PathBuf, PathBuf),
}

fn fixture() -> &'static Fixture {
    static FIXTURE: std::sync::OnceLock<Fixture> = std::sync::OnceLock::new();
    FIXTURE.get_or_init(|| {
        let one = compile("library-1", &[("lib/Deny.java", deny(".toLowerCase()"))], &[]);
        let two = compile("library-2", &[("lib/Deny.java", deny(".toLowerCase(java.util.Locale.ROOT)"))], &[]);
        let entries = (compile("entry-1", &[("app/Entry.java", entry(""))], &[&one]), compile("entry-2", &[("app/Entry.java", entry(""))], &[&two]));
        Fixture { libraries: (one, two), entries }
    })
}

const ASCII: &str = "locale >= 0 && locale < 2 && field != null && field.chars().allMatch(c -> c < 128) && (names == null || java.util.Arrays.stream(names).allMatch(n -> n == null || n.chars().allMatch(c -> c < 128)))";
/// Where a Turkish default lowers a capital I otherwise than the root locale does.
const DOTLESS: &str = "locale == 1 && (field.indexOf('I') >= 0 || (names != null && java.util.Arrays.stream(names).anyMatch(n -> n != null && n.indexOf('I') >= 0)))";

fn options(before: &Path, after: &Path, target: &str, work: &str) -> equivalence::Options {
    let f = fixture();
    let mut o = equivalence::Options::new(before, after, target);
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.classpath = vec![f.libraries.1.clone()];
    o.before_classpath = Some(vec![f.libraries.0.clone()]);
    o.max_array_length = 2;
    o.nullable = vec!["names".into()];
    o.work = Some(tmp(work));
    o
}

/// The release pair's shape: a `String[]` that may be null, a domain and an allowed change that javac compiles, each
/// version on its own library. Outside the allowed change the versions agree; with no change allowed they differ
/// under the Turkish locale, on a witness run on a JVM.
#[test]
fn two_versions_over_a_string_array_agree_outside_the_allowed_change_and_differ_with_none() {
    jvmcontract::tool_tier!();
    let f = fixture();
    let mut preserved = options(&f.entries.0, &f.entries.1, "app.Entry#allowed", "preserved");
    preserved.assume = Some(ASCII.into());
    preserved.unchanged_unless = Some(DOTLESS.into());
    let o = equivalence::run(&preserved).unwrap();
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.output.contains("checked as a property of the pair of versions") && o.output.contains("each on its own dependency closure") && o.output.contains("the two versions agree on every input where"), "{}", o.output);
    assert!(o.output.contains("String[] of length ≤ 2, or null, each element a String of ≤ 2 code units of its own or null"), "{}", o.output);
    let java = std::fs::read_to_string(o.statement.as_ref().expect("the pair's class")).unwrap();
    assert!(java.contains("a = before.app.Entry.allowed(locale, names == null ? null : names.clone(), field);"), "{java}");

    let mut changed = options(&f.entries.0, &f.entries.1, "app.Entry#allowed", "changed");
    changed.assume = Some(ASCII.into());
    let o = equivalence::run(&changed).unwrap();
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.output.contains("the two versions differ on allowed(locale=1") && o.output.contains("run on a JVM"), "{}", o.output);
    let witness = o.pair.as_ref().and_then(|p| p.counterexample.as_ref()).expect("the pair's counterexample");
    assert!(witness.input.contains("locale=1") && witness.input.contains('I'), "{}", witness.input);

    // Any locale index, and a field that may be null: an index outside the table and a null field throw in both
    // versions, each in one category, and the versions agree there.
    let mut everywhere = options(&f.entries.1, &f.entries.1, "app.Entry#allowed", "everywhere");
    everywhere.before_classpath = Some(vec![f.libraries.1.clone()]);
    everywhere.nullable.push("field".into());
    everywhere.assume = Some("(field == null || field.chars().allMatch(c -> c < 128)) && (names == null || java.util.Arrays.stream(names).allMatch(n -> n == null || n.chars().allMatch(c -> c < 128)))".into());
    let o = equivalence::run(&everywhere).unwrap();
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
}

/// Each version is given its own copy of an array: a previous version that writes into the array it was given does
/// not change what the next one reads.
#[test]
fn each_version_is_given_its_own_copy_of_an_array() {
    jvmcontract::tool_tier!();
    let f = fixture();
    let clears = compile("entry-clears", &[("app/Entry.java", entry("        if (names != null && names.length > 0) {\n            names[0] = field;\n        }\n"))], &[&f.libraries.1]);
    let mut o = options(&clears, &f.entries.1, "app.Entry#allowed", "copies");
    o.before_classpath = Some(vec![f.libraries.1.clone()]);
    o.assume = Some(ASCII.into());
    let o = equivalence::run(&o).unwrap();
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
}

/// What the pair's property does not take is refused by name: an instance method, a method that declares checked
/// exceptions (JBMC's refusal is a unit test of `pairing::refusal`).
#[test]
fn what_a_property_of_the_pair_does_not_take_is_refused_by_name() {
    jvmcontract::tool_tier!();
    let f = fixture();
    for (target, why) in [("app.Entry#instance", "which takes a static method"), ("app.Entry#checked", "declares checked exceptions")] {
        let o = equivalence::run(&options(&f.entries.0, &f.entries.1, target, &format!("refused-{}", &target[10..]))).unwrap();
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        assert!(o.output.contains(why), "{}", o.output);
    }
}

/// A library that asks about its surroundings by name: whether the class path has `lib.Extra`, its own class's
/// name, and a table its initializer builds through a map the checker does not run. `extra` says whether this
/// version has `lib.Extra`, and `base` is what its table adds.
fn probe(extra: bool, base: u32) -> Vec<(&'static str, String)> {
    let made = if extra { "    static Object made() {\n        return new Extra();\n    }\n" } else { "" };
    let mut sources = vec![(
        "lib/Probe.java",
        format!("package lib;\npublic final class Probe {{\n    static final java.util.IdentityHashMap<Object, Object> TABLE = new java.util.IdentityHashMap<>();\n    static final int BASE;\n    static {{\n        TABLE.put(\"a\", \"b\");\n        BASE = TABLE.size() + {base};\n    }}\n{made}    static boolean has(String name) {{\n        try {{\n            Class.forName(name);\n            return true;\n        }}\n        catch (ClassNotFoundException e) {{\n            return false;\n        }}\n    }}\n    public static int answer(int k) {{\n        return (has(\"lib.Extra\") ? 100 : 0) + Probe.class.getName().length() + BASE + k;\n    }}\n}}\n"),
    )];
    if extra {
        sources.push(("lib/Extra.java", "package lib;\npublic final class Extra {\n}\n".to_string()));
    }
    sources
}

/// What the previous version's code asks by a name it computes is answered as on its own class path: a class by
/// its name is the previous version's own (and none that only the new version has), a class's name is its own and
/// not the copy's, and an initializer to observe is observed in each version on that version's class path. The two
/// versions here return the same number only if all three hold: one finds `lib.Extra` and adds 100 for it, the
/// other's table adds the 100, and both add the nine letters of `lib.Probe`.
#[test]
fn the_previous_versions_questions_by_name_are_answered_on_its_own_class_path() {
    jvmcontract::tool_tier!();
    let with = compile("probe-with", &probe(true, 0), &[]);
    let without = compile("probe-without", &probe(false, 100), &[]);
    let entry = "package app;\npublic final class Entry {\n    public static int answer(int k) {\n        return lib.Probe.answer(k);\n    }\n}\n".to_string();
    let entries = (compile("probe-entry-with", &[("app/Entry.java", entry.clone())], &[&with]), compile("probe-entry-without", &[("app/Entry.java", entry)], &[&without]));
    let pair = |before: (&Path, &Path), after: (&Path, &Path), work: &str, observed: bool| {
        let mut o = equivalence::Options::new(before.0, after.0, "app.Entry#answer");
        o.engine = Engine::Native;
        o.jbmc = NO_JBMC.into();
        o.classpath = vec![after.1.to_path_buf()];
        o.before_classpath = Some(vec![before.1.to_path_buf()]);
        o.assume = Some("k >= 0 && k < 4".into());
        o.work = Some(tmp(work));
        if observed {
            o.observed_initializers = vec!["lib.Probe".into()];
        }
        equivalence::run(&o).unwrap()
    };
    // The initializer is a gap until it is observed.
    let unobserved = pair((&entries.0, &with), (&entries.1, &without), "probe-unobserved", false);
    assert_eq!(unobserved.verdict, Verdict::Unverifiable, "{}", unobserved.output);

    for (before, after, work) in [((&entries.0, &with), (&entries.1, &without), "probe-had"), ((&entries.1, &without), (&entries.0, &with), "probe-has")] {
        let o = pair((before.0.as_path(), before.1.as_path()), (after.0.as_path(), after.1.as_path()), work, true);
        assert_eq!(o.verdict, Verdict::Verified, "{work}: {}", o.output);
        let stated = o.pair.as_ref().and_then(|p| p.stated.as_ref()).expect("the pair's statement");
        let rests_on = |start: &str, part: &str| stated.assumptions.iter().any(|a| a.text.starts_with(start) && a.text.contains(part));
        assert!(rests_on("the class initializer of before.lib.Probe was not run by the checker", "on the previous version's class path, where it is lib.Probe"), "{work}: {:?}", stated.assumptions);
        assert!(rests_on("the class initializer of lib.Probe was not run by the checker", "on the check's class path"), "{work}: {:?}", stated.assumptions);
    }

    // The options are the pair's property's: a check the harness makes refuses them, and so does a class neither
    // version has.
    let mut plain = equivalence::Options::new(&entries.0, &entries.0, "app.Entry#answer");
    plain.engine = Engine::Native;
    plain.jbmc = NO_JBMC.into();
    plain.classpath = vec![with.clone()];
    plain.work = Some(tmp("probe-plain"));
    plain.observed_initializers = vec!["lib.Probe".into()];
    let o = equivalence::run(&plain).unwrap();
    assert!(o.verdict == Verdict::Unverifiable && o.output.contains("--observed-initializer and --model are for a regression check made as a property of the pair of versions"), "{}", o.output);
    plain.assume = Some("k >= 0".into());
    plain.observed_initializers = vec!["lib.Absent".into()];
    let o = equivalence::run(&plain).unwrap();
    assert!(o.verdict == Verdict::Unverifiable && o.output.contains("--observed-initializer lib.Absent: neither version's class path has the class"), "{}", o.output);
}
