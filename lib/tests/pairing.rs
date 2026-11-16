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
