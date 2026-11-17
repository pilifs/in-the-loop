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

/// A proof of the pair says something only about an input outside the allowed change: `agree` returns true on one
/// inside it without calling either version. An allowed change that covers every assumed input (`true`) leaves a
/// proof that compares the versions on none, which the statement calls vacuous, though the property check's own
/// probe finds an input of the assumption; with the change the claim allows, the statement's witness is an assumed
/// input outside it, and the statement says which change it lies outside.
#[test]
fn a_pairs_proof_is_vacuous_when_the_allowed_change_covers_every_assumed_input() {
    jvmcontract::tool_tier!();
    let f = fixture();
    let mut everything = options(&f.entries.0, &f.entries.1, "app.Entry#allowed", "allowed-everything");
    everything.assume = Some(ASCII.into());
    everything.unchanged_unless = Some("true".into());
    let o = equivalence::run(&everything).unwrap();
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let vacuity = o.stated.as_ref().and_then(|s| s.vacuity.as_ref()).expect("a verified statement says whether it is vacuous");
    assert_eq!(vacuity.status, jvmcontract::statement::VacuityStatus::Vacuous, "{}", o.output);
    assert!(o.vacuous.as_deref().is_some_and(|r| r.contains("inside the allowed change `true`")), "{}", o.output);

    let mut preserved = options(&f.entries.0, &f.entries.1, "app.Entry#allowed", "allowed-dotless");
    preserved.assume = Some(ASCII.into());
    preserved.unchanged_unless = Some(DOTLESS.into());
    let o = equivalence::run(&preserved).unwrap();
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let vacuity = o.stated.as_ref().and_then(|s| s.vacuity.as_ref()).expect("a verified statement says whether it is vacuous");
    assert_eq!(vacuity.status, jvmcontract::statement::VacuityStatus::NonVacuous, "{}", o.output);
    assert_eq!(vacuity.outside.as_deref(), Some(DOTLESS), "{}", o.output);
    let witness = vacuity.witness.as_deref().expect("the witness");
    assert!(witness.starts_with("agree(") && (witness.contains("locale=0") || !witness.contains('I')), "{witness} is outside the Turkish capital I");
    assert!(o.vacuous.is_none(), "{}", o.output);
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

/// Example 287's relational failure in small, and what the tool's own checker's ties (`bmc/ties.rs`) take of it.
/// Both versions run one loop of a hundred rounds over a table of 256 words, past the bound: each side's state past
/// it is what an invariant allows, and two runs equal in fact were two free states in the formula, a counterexample
/// no run has. A state of one key (the same code, from the same state) is now one state on both sides. Each
/// variant but `same` is a countermodel, a pair of versions that differ on a JVM and whose loop the ties would make
/// agree without one side condition: `callee` changes a helper the loop calls, `cells` one cell of the table,
/// `alias` passes the table as both arrays on one side only, `mutable` a static field the loop reads, `shorter` the
/// table's length (an exception on one side), and `after` writes a cell past the loop on one side. Their
/// differences show past round 50, so the bound's sixteen rounds leave the two states the same but for what each
/// countermodel changes. With that side condition taken out each was proved to agree (checked by hand, 2026-11-17).
const MIXES: [&str; 7] = ["same", "callee", "cells", "alias", "mutable", "shorter", "after"];

fn mix(variant: &str, old: bool) -> String {
    let step = match (variant, old) {
        ("mutable", _) => "acc * K",
        ("callee", _) => "step(acc)",
        _ => "acc * 31",
    };
    let helper = if variant == "callee" { format!("    private static int step(int acc) {{ return acc * {}; }}\n", if old { 31 } else { 33 }) } else { String::new() };
    let length = if variant == "shorter" && !old { 255 } else { 256 };
    let before = match variant {
        "cells" => format!("t[7] = {};", if old { 1 } else { 2 }),
        "mutable" => format!("K = {};", if old { 31 } else { 33 }),
        _ => String::new(),
    };
    let second = if variant == "alias" && !old { "t.clone()" } else { "t" };
    let after = if variant == "after" && old { "t[x & 255] ^= 1;" } else { "" };
    let check = if old { "" } else { "if (x == 12345) { throw new IllegalArgumentException(); }" };
    format!(
        "package app.{variant};\npublic final class Mix {{\n    static int K = 31;\n{helper}    public static int digest(int x) {{\n        {check}\n        int[] t = new int[{length}];\n        {before}\n        int acc = run(t, {second}, x);\n        {after}\n        return acc + t[x & 127];\n    }}\n    private static int run(int[] a, int[] b, int x) {{\n        int acc = x;\n        for (int r = 0; r < 100; r++) {{\n            if (r >= 50) {{\n                acc = {step} + b[(acc >>> 3) & 255];\n                a[acc & 255] ^= acc;\n            }} else {{\n                acc = acc * 31 + r;\n            }}\n        }}\n        return acc;\n    }}\n}}\n"
    )
}

/// Every variant, the previous versions in one folder and the new ones in another.
fn mixes() -> &'static (PathBuf, PathBuf) {
    static MIXED: std::sync::OnceLock<(PathBuf, PathBuf)> = std::sync::OnceLock::new();
    MIXED.get_or_init(|| {
        let paths: Vec<String> = MIXES.iter().map(|v| format!("app/{v}/Mix.java")).collect();
        let sources = |old: bool| paths.iter().zip(MIXES).map(|(p, v)| (p.as_str(), mix(v, old))).collect::<Vec<_>>();
        (compile("mixes-old", &sources(true), &[]), compile("mixes-new", &sources(false), &[]))
    })
}

fn mixed(variant: &str) -> equivalence::Outcome {
    let (old, new) = mixes();
    let mut o = equivalence::Options::new(old, new, &format!("app.{variant}.Mix#digest"));
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.assume = Some("x != 12345".into());
    o.work = Some(tmp(&format!("mix-{variant}")));
    equivalence::run(&o).unwrap()
}

#[test]
fn two_runs_of_one_loop_past_the_bound_go_on_from_one_state() {
    jvmcontract::tool_tier!();
    let o = mixed("same");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.output.contains("covered by invariants") && o.output.contains("before.app.same.Mix.run at pc"), "{}", o.output);
    // The new version's loop starts from the state the previous version's did, and its summary is that one's,
    // not searched for again.
    let native = o.search.as_ref().and_then(|s| s.native.as_ref()).expect("the own checker's account");
    assert!(native.summaries_reused >= 1 && native.loops.iter().any(|l| l.starts_with("app.same.Mix.run at pc")), "{native:?}");
}

#[test]
fn no_state_past_a_loop_is_one_of_two_runs_that_may_differ() {
    jvmcontract::tool_tier!();
    let proved: Vec<&str> = MIXES[1..].iter().copied().filter(|v| mixed(v).verdict == Verdict::Verified).collect();
    assert!(proved.is_empty(), "proved to agree, though the versions differ on a JVM: {proved:?}");
}

/// The countermodels are pairs of versions a JVM tells apart, on one of the first 64 inputs, and `same` is not.
#[test]
fn each_mixes_countermodel_differs_on_a_jvm() {
    jvmcontract::tool_tier!();
    let (old, new) = mixes();
    let runner = "public class Run {\n    public static void main(String[] variants) throws Exception {\n        for (String v : variants) {\n            StringBuilder out = new StringBuilder();\n            for (int x = 0; x < 64; x++) {\n                Object r;\n                try { r = Class.forName(\"app.\" + v + \".Mix\").getMethod(\"digest\", int.class).invoke(null, x); }\n                catch (java.lang.reflect.InvocationTargetException e) { r = e.getCause().getClass().getName(); }\n                out.append(r).append(',');\n            }\n            System.out.println(v + \" \" + out);\n        }\n    }\n}\n";
    let run_dir = compile("mixes-runner", &[("Run.java", runner.to_string())], &[]);
    let outputs = |version: &Path| {
        let cp = format!("{}:{}", run_dir.display(), version.display());
        let out = Command::new("java").args(["-cp", &cp, "Run"]).args(MIXES).output().expect("java runs");
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).lines().map(String::from).collect::<Vec<_>>()
    };
    let (before, after) = (outputs(old), outputs(new));
    for (i, v) in MIXES.iter().enumerate() {
        assert_eq!(before[i] == after[i], *v == "same", "{v}: {} | {}", before[i], after[i]);
    }
}

/// A loop inside one past the bound is given its invariant at its entry once it was given one before (a key
/// schedule's loops, in each of a hash's rounds), and two versions' states tie only where both give it at the same
/// point. Here the previous version's run forks after its loops, and the new version runs once on each fork: on the
/// second, the inner loop had been summarized by the new version on the first fork, but not yet by the new
/// version's run on this one. Whether it is summarized at its entry is now this path's own history since its version
/// began, and the second fork is proved as the first is. When that was the check's history, the new version's
/// inner loop on the second fork started at its entry, the previous version's past the bound, and nothing tied
/// (checked by hand, 2026-11-17).
#[test]
fn two_versions_summarize_a_loop_at_its_entry_alike_on_every_fork() {
    jvmcontract::tool_tier!();
    let source = |old: bool| {
        let check = if old { "" } else { "if (x == 12345) { throw new IllegalArgumentException(); }" };
        format!(
            "package app.nested;\npublic final class Mix {{\n    public static int digest(int x) {{\n        {check}\n        int[] t = new int[256];\n        int acc = rounds(t, x);\n        if (acc > 0) {{\n            return acc + t[x & 127];\n        }}\n        return acc - t[x & 63];\n    }}\n    private static int rounds(int[] t, int acc) {{\n        for (int i = 0; i < 100; i++) {{\n            acc = acc * 7 + t[(acc >>> 5) & 255];\n            t[i & 255] ^= acc;\n        }}\n        for (int r = 0; r < 40; r++) {{\n            acc = inner(t, acc);\n        }}\n        return acc;\n    }}\n    private static int inner(int[] t, int acc) {{\n        for (int i = 0; i < 100; i++) {{\n            acc = acc * 31 + t[(acc >>> 3) & 255];\n            t[acc & 255] ^= acc;\n        }}\n        return acc;\n    }}\n}}\n"
        )
    };
    let old = compile("nested-old", &[("app/nested/Mix.java", source(true))], &[]);
    let new = compile("nested-new", &[("app/nested/Mix.java", source(false))], &[]);
    let mut o = equivalence::Options::new(&old, &new, "app.nested.Mix#digest");
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.assume = Some("x != 12345".into());
    o.work = Some(tmp("nested"));
    let o = equivalence::run(&o).unwrap();
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let native = o.search.as_ref().and_then(|s| s.native.as_ref()).expect("the own checker's account");
    assert!(native.loops.iter().any(|l| l.starts_with("app.nested.Mix.inner at pc")) && native.summaries_reused >= 2, "{native:?}");
}
