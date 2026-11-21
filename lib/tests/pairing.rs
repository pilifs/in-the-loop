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

/// A missing receiver stays open. A declared checked exception can be compared through the paired harness.
#[test]
fn what_a_property_of_the_pair_does_not_take_is_refused_by_name() {
    jvmcontract::tool_tier!();
    let f = fixture();
    let instance = equivalence::run(&options(&f.entries.0, &f.entries.1, "app.Entry#instance", "refused-instance")).unwrap();
    assert_eq!(instance.verdict, Verdict::Unverifiable, "{}", instance.output);
    assert!(instance.output.contains("which takes a static method"), "{}", instance.output);
    let declared = equivalence::run(&options(&f.entries.0, &f.entries.1, "app.Entry#checked", "declared-checked")).unwrap();
    assert_eq!(declared.verdict, Verdict::Verified, "{}", declared.output);
}

/// A checked exception participates in the actual outcome, including a different concrete subclass.
#[test]
fn a_declared_checked_exception_is_compared_on_its_throwing_and_returning_paths() {
    jvmcontract::tool_tier!();
    let unit = |error: &str| format!(r#"package app;
public class Checked {{
    public static int read(int n) throws java.io.IOException {{
        if (n == 0) throw new {error}();
        return n;
    }}
    public static void main(String[] args) throws java.io.IOException {{
        try {{ read(0); }} catch (java.io.IOException e) {{ System.out.println(e.getClass().getName()); }}
        System.out.println(read(1));
    }}
}}"#);
    let before = compile("checked-old", &[("app/Checked.java", unit("java.io.IOException"))], &[]);
    let after = compile("checked-new", &[("app/Checked.java", unit("java.io.EOFException"))], &[]);
    let mut pair = equivalence::Options::new(&before, &after, "app.Checked#read");
    pair.engine = Engine::Native;
    pair.jbmc = NO_JBMC.into();
    pair.assume = Some("n >= 0 && n <= 1".into());
    pair.shared_callees = false;
    pair.work = Some(tmp("checked-exception-comparison"));
    let changed = equivalence::run(&pair).unwrap();
    assert_eq!(changed.verdict, Verdict::Violation, "{}", changed.output);
    assert!(changed.output.contains("agree(n=0)"), "{}", changed.output);
    for (classes, exception) in [(&before, "java.io.IOException"), (&after, "java.io.EOFException")] {
        let replay = Command::new("java").arg("-cp").arg(classes).arg("app.Checked").output().unwrap();
        assert!(replay.status.success());
        assert_eq!(String::from_utf8(replay.stdout).unwrap(), format!("{exception}\n1\n"));
    }
    pair.assume = Some("n == 1".into());
    pair.work = Some(tmp("checked-return-comparison"));
    let preserved = equivalence::run(&pair).unwrap();
    assert_eq!(preserved.verdict, Verdict::Verified, "{}", preserved.output);
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
    // The checker can also run this initializer: its identity map has only put and size.
    let unobserved = pair((&entries.0, &with), (&entries.1, &without), "probe-unobserved", false);
    assert_eq!(unobserved.verdict, Verdict::Verified, "{}", unobserved.output);

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
/// `run` takes an `Object` it does not use, a parameter of a type a call taken as one function of both versions may
/// not have (`bmc/ties.rs`, [`ONCES`]): so the loop runs, and its ties are what these test.
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
        "package app.{variant};\npublic final class Mix {{\n    static int K = 31;\n{helper}    public static int digest(int x) {{\n        {check}\n        int[] t = new int[{length}];\n        {before}\n        int acc = run(t, {second}, x, null);\n        {after}\n        return acc + t[x & 127];\n    }}\n    private static int run(int[] a, int[] b, int x, Object kept) {{\n        int acc = x;\n        for (int r = 0; r < 100; r++) {{\n            if (r >= 50) {{\n                acc = {step} + b[(acc >>> 3) & 255];\n                a[acc & 255] ^= acc;\n            }} else {{\n                acc = acc * 31 + r;\n            }}\n        }}\n        return acc;\n    }}\n}}\n"
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

/// A call taken as one function of both versions (`bmc/ties.rs`): `run`, a static method with a loop that both
/// versions share, called with an array, is not run; its outcome is a function of its inputs, the same for both
/// versions' calls where their inputs are equal. Each variant but `same` is a countermodel, a pair of versions that
/// differ on a JVM and that the rule would prove to agree without one of its side conditions: `callee` changes a
/// helper `run` calls (the code compared), `cells` one cell of the array (the inputs compared), `alias` passes the
/// array as both arguments on one side only and returns what `run` does (which inputs are one object), `mutable` a static field `run` reads (the
/// static fields among the inputs), `thrown` catches the exception `run` throws on one side only (the exceptions
/// among the outcomes), `written` reads the cell `run` writes before the call on one side (what the call writes
/// among the outcomes), `clock` reads the clock in `run` (the JDK methods a callee may call), and `init` makes the
/// call on one side only, whatever it ends with, where `run` initializes a class whose initializer reads a static
/// field the caller changes after the call (the classes a call reads the state of are initialized). With that side condition taken out, each
/// was proved to agree (checked by hand, 2026-11-17).
const ONCES: [&str; 9] = ["same", "callee", "cells", "alias", "mutable", "thrown", "written", "clock", "init"];

fn once(variant: &str, old: bool) -> String {
    let step = match variant {
        "mutable" => "acc * K",
        "callee" => "step(acc)",
        _ => "acc * 31",
    };
    let helper = if variant == "callee" { format!("    private static int step(int acc) {{ return acc * {}; }}\n", if old { 31 } else { 33 }) } else { String::new() };
    let clock = if variant == "clock" { " ^ (int) System.nanoTime()" } else { "" };
    let table = if variant == "init" { " + Table.X" } else { "" };
    let throwing = if variant == "thrown" { "if (x == 7) { throw new IllegalArgumentException(); }" } else { "" };
    let before = match variant {
        "cells" => format!("t[7] = {};", if old { 1 } else { 2 }),
        "mutable" => format!("K = {};", if old { 31 } else { 33 }),
        _ => String::new(),
    };
    let second = if variant == "alias" && !old { "t.clone()" } else { "t" };
    let call = format!("run(t, {second}, x)");
    let body = match (variant, old) {
        ("thrown", _) => format!("int acc;\n        try {{ acc = {call}; }} catch ({} e) {{ acc = -1; }}\n        return acc + t[x & 15];", if old { "IllegalArgumentException" } else { "IllegalStateException" }),
        ("written", false) => format!("int kept = t[x & 15];\n        int acc = {call};\n        return acc + kept;"),
        ("alias", _) => format!("return {call};"),
        ("init", true) => format!("try {{ {call}; }} catch (Throwable e) {{ }}\n        K = 2;\n        return Table.X;"),
        ("init", false) => "K = 2;\n        return Table.X;".to_string(),
        _ => format!("int acc = {call};\n        return acc + t[x & 15];"),
    };
    let check = if old { "" } else { "if (x == 12345) { throw new IllegalArgumentException(); }" };
    format!(
        "package app.{variant};\npublic final class Once {{\n    static int K = 31;\n    static final class Table {{ static int X = K; }}\n{helper}    public static int digest(int x) {{\n        {check}\n        int[] t = new int[16];\n        {before}\n        {body}\n    }}\n    static int run(int[] a, int[] b, int x) {{\n        {throwing}\n        int acc = x;\n        for (int r = 0; r < 4; r++) {{\n            acc = {step} + b[(acc >>> 3) & 15]{clock}{table};\n            a[acc & 15] ^= acc;\n        }}\n        a[x & 15] ^= acc | 1;\n        return acc;\n    }}\n}}\n"
    )
}

/// Every variant, the previous versions in one folder and the new ones in another.
fn onces() -> &'static (PathBuf, PathBuf) {
    static ONCED: std::sync::OnceLock<(PathBuf, PathBuf)> = std::sync::OnceLock::new();
    ONCED.get_or_init(|| {
        let paths: Vec<String> = ONCES.iter().map(|v| format!("app/{v}/Once.java")).collect();
        let sources = |old: bool| paths.iter().zip(ONCES).map(|(p, v)| (p.as_str(), once(v, old))).collect::<Vec<_>>();
        (compile("onces-old", &sources(true), &[]), compile("onces-new", &sources(false), &[]))
    })
}

fn onced(variant: &str) -> equivalence::Outcome {
    onced_with(variant, true)
}

/// `shared_callees`: false as `--no-shared-callees` makes it.
fn onced_with(variant: &str, shared_callees: bool) -> equivalence::Outcome {
    let (old, new) = onces();
    let mut o = equivalence::Options::new(old, new, &format!("app.{variant}.Once#digest"));
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.assume = Some("x != 12345".into());
    o.shared_callees = shared_callees;
    o.work = Some(tmp(&format!("once-{variant}{}", if shared_callees { "" } else { "-as-written" })));
    equivalence::run(&o).unwrap()
}

#[test]
fn a_call_both_versions_share_is_one_function_of_its_inputs() {
    jvmcontract::tool_tier!();
    let o = onced("same");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let native = o.search.as_ref().and_then(|s| s.native.as_ref()).expect("the own checker's account");
    assert!(native.calls_as_one_function >= 2 && native.calls_related >= 1, "{native:?}");
    assert!(o.output.contains("taken as one function of both"), "{}", o.output);
    let stated = o.pair.as_ref().and_then(|p| p.stated.as_ref()).expect("the pair's statement");
    assert!(stated.assumptions.iter().any(|a| a.text.starts_with("each call of app.same.Once.run taken as one function of both versions")), "{:?}", stated.assumptions);
}

/// `--no-shared-callees` proves each callee as written, as its help says: no call is taken as one function of both
/// versions, and the outcome states no such assumption.
#[test]
fn no_shared_callees_takes_no_call_as_one_function() {
    jvmcontract::tool_tier!();
    let o = onced_with("same", false);
    let native = o.search.as_ref().and_then(|s| s.native.as_ref()).expect("the own checker's account");
    assert_eq!(native.calls_as_one_function, 0, "{native:?}");
    assert!(!o.output.contains("taken as one function of both"), "{}", o.output);
}

/// The countermodels are pairs of versions a JVM tells apart, on one of the first 64 inputs (each version in a JVM
/// of its own, as the pair starts each fresh), and `same` is not.
#[test]
fn each_onces_countermodel_differs_on_a_jvm() {
    jvmcontract::tool_tier!();
    let (old, new) = onces();
    let runner = "public class Run {\n    public static void main(String[] variants) throws Exception {\n        for (String v : variants) {\n            StringBuilder out = new StringBuilder();\n            for (int x = 0; x < 64; x++) {\n                Object r;\n                try { r = Class.forName(\"app.\" + v + \".Once\").getMethod(\"digest\", int.class).invoke(null, x); }\n                catch (java.lang.reflect.InvocationTargetException e) { r = e.getCause().getClass().getName(); }\n                out.append(r).append(',');\n            }\n            System.out.println(v + \" \" + out);\n        }\n    }\n}\n";
    let run_dir = compile("onces-runner", &[("Run.java", runner.to_string())], &[]);
    let outputs = |version: &Path| {
        let cp = format!("{}:{}", run_dir.display(), version.display());
        let out = Command::new("java").args(["-cp", &cp, "Run"]).args(ONCES).output().expect("java runs");
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).lines().map(String::from).collect::<Vec<_>>()
    };
    let (before, after) = (outputs(old), outputs(new));
    for (i, v) in ONCES.iter().enumerate() {
        assert_eq!(before[i] == after[i], *v == "same", "{v}: {} | {}", before[i], after[i]);
    }
}

#[test]
fn no_call_is_one_function_of_two_versions_that_may_differ() {
    jvmcontract::tool_tier!();
    let proved: Vec<&str> = ONCES[1..].iter().copied().filter(|v| onced(v).verdict == Verdict::Verified).collect();
    assert!(proved.is_empty(), "proved to agree, though a JVM tells them apart: {proved:?}");
}

/// A call of an instance method taken as one function of both versions (`bmc/ties.rs`), as bcrypt's `crypt_raw` is
/// in example 287: `run`, a method with a loop that both versions share, is called on a receiver `digest` makes just
/// before and never reads again, writes the receiver's fields, and returns an array it makes of a length its code
/// gives (`new byte[8]`). Each variant but `same` is a countermodel, a pair of versions that differ on a JVM and that
/// the rule would prove to agree without one of its side conditions: `kept` reads the field `run` wrote through
/// the local that holds the receiver, on one side only (the receiver is read by no live local after the call),
/// `held` through a static field (nor by a static field or another object), `caught` in a handler of the exception
/// `run` throws (a handler is a way on from the call), `field` gives the receiver another field value on each side
/// (the receiver's fields are among the inputs), `returned` returns the array argument it was given rather than one
/// it made, and one side writes that argument after the call (the result is an array the call made), and `table`
/// reads the static array `run` writes, before the call on one side and after it on the other (an array a static
/// field holds is among what the call writes, where its code takes the field other than to copy it). With that side
/// condition taken out, each was proved to agree (a temporary switch, removed, 2026-11-17).
const KEYED: [&str; 7] = ["same", "kept", "held", "caught", "field", "returned", "table"];

fn keyed(variant: &str, old: bool) -> String {
    let check = if old { "" } else { "if (x == 12345) { throw new IllegalArgumentException(); }" };
    let before = match variant {
        "field" => format!("c.seed = {};", if old { 1 } else { 2 }),
        "held" if old => "Holder.HELD = c;".to_string(),
        _ => String::new(),
    };
    let call = "byte[] r = c.run(t, u, x);";
    let body = match (variant, old) {
        ("kept", true) => format!("{call}\n        return c.state;"),
        ("kept", false) | ("held", false) => format!("{call}\n        return 0;"),
        ("held", true) => format!("{call}\n        return Holder.HELD.state;"),
        ("caught", _) => format!("try {{\n            {call}\n            return r[x & 7];\n        }} catch (IllegalArgumentException e) {{\n            return {};\n        }}", if old { "c.state" } else { "0" }),
        ("returned", true) => format!("{call}\n        u[0] = 9;\n        return r[0];"),
        ("returned", false) => format!("{call}\n        return r[0];"),
        ("table", true) => "int k = T[x & 7];\n        c.run(t, u, x);\n        return k;".to_string(),
        ("table", false) => "c.run(t, u, x);\n        return T[x & 7];".to_string(),
        _ => format!("{call}\n        return r[x & 7] + t[x & 15];"),
    };
    let throwing = if variant == "caught" { "if (x == 7) { throw new IllegalArgumentException(); }" } else { "" };
    let table = if variant == "table" { "T[acc & 7] ^= acc;" } else { "" };
    let made = if variant == "returned" { "b[0] = (byte) acc;\n        return b;" } else { "byte[] out = new byte[8];\n        for (int i = 0; i < 8; i++) {\n            out[i] = (byte) box[i];\n        }\n        return out;" };
    format!(
        "package app.{variant};\npublic final class Keyed {{\n    static final int[] T = new int[8];\n    int seed;\n    int state;\n    int[] box;\n    public static int digest(int x) {{\n        {check}\n        int[] t = new int[16];\n        byte[] u = new byte[8];\n        Keyed c = new Keyed();\n        {before}\n        {body}\n    }}\n    byte[] run(int[] a, byte[] b, int x) {{\n        box = new int[8];\n        int acc = x + seed;\n        for (int i = 0; i < 40; i++) {{\n            acc = acc * 31 + a[(acc >>> 3) & 15];\n            box[i & 7] ^= acc;\n            a[acc & 15] ^= acc;\n            {table}\n        }}\n        state = acc | 1;\n        {throwing}\n        {made}\n    }}\n}}\nfinal class Holder {{\n    static Keyed HELD;\n}}\n"
    )
}

/// Every variant, the previous versions in one folder and the new ones in another.
fn keyeds() -> &'static (PathBuf, PathBuf) {
    static KEYEDS: std::sync::OnceLock<(PathBuf, PathBuf)> = std::sync::OnceLock::new();
    KEYEDS.get_or_init(|| {
        let paths: Vec<String> = KEYED.iter().map(|v| format!("app/{v}/Keyed.java")).collect();
        let sources = |old: bool| paths.iter().zip(KEYED).map(|(p, v)| (p.as_str(), keyed(v, old))).collect::<Vec<_>>();
        (compile("keyed-old", &sources(true), &[]), compile("keyed-new", &sources(false), &[]))
    })
}

fn keyed_check(variant: &str) -> equivalence::Outcome {
    let (old, new) = keyeds();
    let mut o = equivalence::Options::new(old, new, &format!("app.{variant}.Keyed#digest"));
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.assume = Some("x != 12345".into());
    o.work = Some(tmp(&format!("keyed-{variant}")));
    equivalence::run(&o).unwrap()
}

#[test]
fn a_call_on_a_receiver_no_one_reads_after_is_one_function_of_its_inputs() {
    jvmcontract::tool_tier!();
    let o = keyed_check("same");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let native = o.search.as_ref().and_then(|s| s.native.as_ref()).expect("the own checker's account");
    assert!(native.calls_as_one_function >= 2 && native.calls_related >= 1 && native.loops.is_empty(), "{native:?}");
    let stated = o.pair.as_ref().and_then(|p| p.stated.as_ref()).expect("the pair's statement");
    assert!(stated.assumptions.iter().any(|a| a.text.starts_with("each call of app.same.Keyed.run taken as one function of both versions")), "{:?}", stated.assumptions);
}

/// The countermodels are pairs of versions a JVM tells apart, on one of the first 64 inputs (each version in a JVM
/// of its own, as the pair starts each fresh), and `same` is not.
#[test]
fn each_keyed_countermodel_differs_on_a_jvm() {
    jvmcontract::tool_tier!();
    let (old, new) = keyeds();
    let runner = "public class Run {\n    public static void main(String[] variants) throws Exception {\n        for (String v : variants) {\n            StringBuilder out = new StringBuilder();\n            for (int x = 0; x < 64; x++) {\n                Object r;\n                try { r = Class.forName(\"app.\" + v + \".Keyed\").getMethod(\"digest\", int.class).invoke(null, x); }\n                catch (java.lang.reflect.InvocationTargetException e) { r = e.getCause().getClass().getName(); }\n                out.append(r).append(',');\n            }\n            System.out.println(v + \" \" + out);\n        }\n    }\n}\n";
    let run_dir = compile("keyed-runner", &[("Run.java", runner.to_string())], &[]);
    let outputs = |version: &Path| {
        let cp = format!("{}:{}", run_dir.display(), version.display());
        let out = Command::new("java").args(["-cp", &cp, "Run"]).args(KEYED).output().expect("java runs");
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).lines().map(String::from).collect::<Vec<_>>()
    };
    let (before, after) = (outputs(old), outputs(new));
    for (i, v) in KEYED.iter().enumerate() {
        assert_eq!(before[i] == after[i], *v == "same", "{v}: {} | {}", before[i], after[i]);
    }
}

#[test]
fn no_call_on_a_receiver_is_one_function_of_two_versions_that_may_differ() {
    jvmcontract::tool_tier!();
    let proved: Vec<&str> = KEYED[1..].iter().copied().filter(|v| keyed_check(v).verdict == Verdict::Verified).collect();
    assert!(proved.is_empty(), "proved to agree, though a JVM tells them apart: {proved:?}");
}

/// A String result of a call taken as one function of both versions (`bmc/ties.rs`): `name`, a method with a loop
/// that both versions share, returns a String it makes from an array it fills, or null past 1. In `same` both versions test the result
/// for null, and are proved to agree with the calls taken. In `nulled` only the previous version does, so the two
/// differ past 1. A result taken as never null would prove them to agree (checked against the rule before its
/// result could be null, 2026-11-18).
const NAMED: [&str; 2] = ["same", "nulled"];

fn named(variant: &str, old: bool) -> String {
    let check = if old { "" } else { "if (k == 12345) { throw new IllegalArgumentException(); }" };
    let body = if variant == "nulled" && !old { "return 0;" } else { "return s == null ? 1 : 0;" };
    format!(
        "package app.{variant};\npublic final class Named {{\n    public static int digest(int k) {{\n        {check}\n        String s = name(k);\n        {body}\n    }}\n    static String name(int k) {{\n        char[] c = new char[3];\n        for (int i = 0; i < 3; i++) {{\n            c[i] = 'x';\n        }}\n        return k > 1 ? null : new String(c);\n    }}\n}}\n"
    )
}

fn named_check(variant: &str) -> equivalence::Outcome {
    static NAMEDS: std::sync::OnceLock<(PathBuf, PathBuf)> = std::sync::OnceLock::new();
    let (old, new) = NAMEDS.get_or_init(|| {
        let paths: Vec<String> = NAMED.iter().map(|v| format!("app/{v}/Named.java")).collect();
        let sources = |old: bool| paths.iter().zip(NAMED).map(|(p, v)| (p.as_str(), named(v, old))).collect::<Vec<_>>();
        (compile("named-old", &sources(true), &[]), compile("named-new", &sources(false), &[]))
    });
    let mut o = equivalence::Options::new(old, new, &format!("app.{variant}.Named#digest"));
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.assume = Some("k != 12345".into());
    o.work = Some(tmp(&format!("named-{variant}")));
    equivalence::run(&o).unwrap()
}

#[test]
fn a_string_a_call_taken_as_one_function_returns_may_be_null() {
    jvmcontract::tool_tier!();
    let same = named_check("same");
    assert_eq!(same.verdict, Verdict::Verified, "{}", same.output);
    let native = same.search.as_ref().and_then(|s| s.native.as_ref()).expect("the own checker's account");
    assert!(native.calls_as_one_function >= 2 && native.calls_related >= 1, "{native:?}");
    let nulled = named_check("nulled");
    assert_ne!(nulled.verdict, Verdict::Verified, "the previous version returns 1 past 1 and the new one 0: {}", nulled.output);
}

/// What a call taken as one function of both versions (`bmc/ties.rs`) may keep: `keep`, a method both versions
/// share, runs a loop of `k` rounds, and `digest` answers an `OutOfMemoryError` from it with -1 in the previous
/// version and -2 in the new one. Each array it makes is of a constant length, at most 65536, so the check at the
/// call passes. In `same` each round's array is dropped at the end of the round, so no heap runs out and the versions
/// agree. Each other variant keeps what every round makes, so that a large `k` fills any heap: `rows` in an array of
/// references, `nodes` in a list of objects of the application's own class, `grown` by `String.concat`, `built` by
/// `StringBuilder.append`, `joined` by `a + b`, and `chained` as the causes of a chain of exceptions. An
/// `OutOfMemoryError` is not among the call's outcomes, so the rule would prove each of the first five pairs to agree
/// without the side condition that refuses it in `shared::one_function` (each switched off in turn, 2026-11-18;
/// I029). `chained` is refused by the reach, since a `Throwable` given to the JDK is no sealed type.
const KEPT: [&str; 7] = ["same", "rows", "nodes", "grown", "built", "joined", "chained"];

fn kept(variant: &str, old: bool) -> String {
    let body = match variant {
        "rows" => "Object[] kept = new Object[16384];\n        for (int i = 0; i < k && i < 16384; i++) {\n            kept[i] = new long[65536];\n            acc++;\n        }",
        "nodes" => "Node head = null;\n        for (int i = 0; i < k; i++) {\n            Node n = new Node();\n            n.next = head;\n            n.cells = new long[65536];\n            head = n;\n            acc++;\n        }",
        "grown" => "String s = \"x\";\n        for (int i = 0; i < k; i++) {\n            s = s.concat(s);\n        }\n        acc = s.length();",
        "built" => "StringBuilder b = new StringBuilder(\"x\");\n        for (int i = 0; i < k; i++) {\n            b.append(b.toString());\n        }\n        acc = b.length();",
        "joined" => "String s = \"x\";\n        for (int i = 0; i < k; i++) {\n            s = s + s;\n        }\n        acc = s.length();",
        "chained" => "RuntimeException e = null;\n        for (int i = 0; i < k; i++) {\n            e = new RuntimeException(\"round\", e);\n            acc++;\n        }",
        _ => "for (int i = 0; i < k && i < 64; i++) {\n            long[] t = new long[65536];\n            t[i] = i;\n            acc += (int) t[i];\n        }",
    };
    format!(
        "package app.{variant};\npublic final class Kept {{\n    public static int digest(int k) {{\n        try {{\n            return keep(k);\n        }} catch (OutOfMemoryError e) {{\n            return {};\n        }}\n    }}\n    static final class Node {{\n        Node next;\n        long[] cells;\n    }}\n    static int keep(int k) {{\n        int acc = 0;\n        {body}\n        return acc;\n    }}\n}}\n",
        if old { -1 } else { -2 }
    )
}

/// Every variant, the previous versions in one folder and the new ones in another.
fn kepts() -> &'static (PathBuf, PathBuf) {
    static KEPTS: std::sync::OnceLock<(PathBuf, PathBuf)> = std::sync::OnceLock::new();
    KEPTS.get_or_init(|| {
        let paths: Vec<String> = KEPT.iter().map(|v| format!("app/{v}/Kept.java")).collect();
        let sources = |old: bool| paths.iter().zip(KEPT).map(|(p, v)| (p.as_str(), kept(v, old))).collect::<Vec<_>>();
        (compile("kept-old", &sources(true), &[]), compile("kept-new", &sources(false), &[]))
    })
}

fn kept_check(variant: &str) -> equivalence::Outcome {
    let (old, new) = kepts();
    let mut o = equivalence::Options::new(old, new, &format!("app.{variant}.Kept#digest"));
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.assume = Some("k >= 0".into());
    o.work = Some(tmp(&format!("kept-{variant}")));
    equivalence::run(&o).unwrap()
}

#[test]
fn a_call_that_keeps_nothing_a_loop_makes_is_one_function_of_its_inputs() {
    jvmcontract::tool_tier!();
    let o = kept_check("same");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let native = o.search.as_ref().and_then(|s| s.native.as_ref()).expect("the own checker's account");
    assert!(native.calls_as_one_function >= 2 && native.calls_related >= 1, "{native:?}");
}

/// The countermodels are pairs of versions a JVM tells apart at a `k` past what a 32 MiB heap holds (each version
/// in a JVM of its own), and `same` is not.
#[test]
fn each_kept_countermodel_differs_on_a_jvm() {
    jvmcontract::tool_tier!();
    let (old, new) = kepts();
    let runner = "public class Run {\n    public static void main(String[] variants) throws Exception {\n        for (String v : variants) {\n            Object r;\n            try { r = Class.forName(\"app.\" + v + \".Kept\").getMethod(\"digest\", int.class).invoke(null, 1 << 30); }\n            catch (java.lang.reflect.InvocationTargetException e) { r = e.getCause().getClass().getName(); }\n            System.out.println(v + \" \" + r);\n        }\n    }\n}\n";
    let run_dir = compile("kept-runner", &[("Run.java", runner.to_string())], &[]);
    let outputs = |version: &Path| {
        let cp = format!("{}:{}", run_dir.display(), version.display());
        let out = Command::new("java").args(["-Xmx32m", "-cp", &cp, "Run"]).args(KEPT).output().expect("java runs");
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).lines().map(String::from).collect::<Vec<_>>()
    };
    let (before, after) = (outputs(old), outputs(new));
    for (i, v) in KEPT.iter().enumerate() {
        assert_eq!(before[i] == after[i], *v == "same", "{v}: {} | {}", before[i], after[i]);
    }
}

#[test]
fn no_call_keeps_what_a_loop_makes_past_its_outcome() {
    jvmcontract::tool_tier!();
    let proved: Vec<&str> = KEPT[1..].iter().copied().filter(|v| kept_check(v).verdict == Verdict::Verified).collect();
    assert!(proved.is_empty(), "proved to agree, though a JVM tells them apart: {proved:?}");
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
/// (checked by hand, 2026-11-17). `rounds` and `inner` take an `Object` they do not use, so that their calls are not
/// taken as one function of both versions ([`ONCES`]) and their loops run: `inner`'s argument is an array whose
/// cells hold any values past `rounds`' first loop, which the rule takes by the name of its content.
#[test]
fn two_versions_summarize_a_loop_at_its_entry_alike_on_every_fork() {
    jvmcontract::tool_tier!();
    let source = |old: bool| {
        let check = if old { "" } else { "if (x == 12345) { throw new IllegalArgumentException(); }" };
        format!(
            "package app.nested;\npublic final class Mix {{\n    public static int digest(int x) {{\n        {check}\n        int[] t = new int[256];\n        int acc = rounds(t, x, null);\n        if (acc > 0) {{\n            return acc + t[x & 127];\n        }}\n        return acc - t[x & 63];\n    }}\n    private static int rounds(int[] t, int acc, Object kept) {{\n        for (int i = 0; i < 100; i++) {{\n            acc = acc * 7 + t[(acc >>> 5) & 255];\n            t[i & 255] ^= acc;\n        }}\n        for (int r = 0; r < 40; r++) {{\n            acc = inner(t, acc, null);\n        }}\n        return acc;\n    }}\n    private static int inner(int[] t, int acc, Object kept) {{\n        for (int i = 0; i < 100; i++) {{\n            acc = acc * 31 + t[(acc >>> 3) & 255];\n            t[acc & 255] ^= acc;\n        }}\n        return acc;\n    }}\n}}\n"
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

/// The code two versions are taken to share, with nothing to prove, is the code a call runs: a class's initializer
/// runs on the first use of the class, so it is part of it. Here the target and the empty method it calls are the
/// same in both versions, and the class of that method sets, as it is initialized, the static field the target
/// reads: 31 against 33. Before, the target was "identical in both versions; nothing to prove" (checked by hand,
/// 2026-11-17); on a JVM `value(1)` is 31 against 33.
#[test]
fn a_class_initializer_the_code_runs_is_part_of_the_code_compared() {
    jvmcontract::tool_tier!();
    let source = |k: i32| {
        vec![
            ("app/late/Entry.java", "package app.late;\npublic final class Entry {\n    static int K = 31;\n    public static int value(int x) {\n        Late.touch();\n        return K * x;\n    }\n}\n".to_string()),
            ("app/late/Late.java", format!("package app.late;\nfinal class Late {{\n    static {{ Entry.K = {k}; }}\n    static void touch() {{}}\n}}\n")),
        ]
    };
    let old = compile("late-old", &source(31), &[]);
    let new = compile("late-new", &source(33), &[]);
    let mut o = equivalence::Options::new(&old, &new, "app.late.Entry#value");
    o.jbmc = NO_JBMC.into();
    o.work = Some(tmp("late"));
    let o = equivalence::run(&o).unwrap();
    assert!(o.verdict != Verdict::Verified && !o.output.contains("nothing to prove"), "{}", o.output);
}

/// The same for a JDK method the code reaches given an application object: `String.valueOf(Object)` calls the
/// object's `toString`, whose private helper is what the versions change ("aa" against "a"). Before, the JDK's static
/// method was taken to run no application code, and the target was "identical in both versions; nothing to prove"
/// (checked by hand, 2026-11-17); on a JVM `shown(1)` is 2 against 1.
#[test]
fn a_jdk_method_given_an_application_object_leaves_the_code_compared_open() {
    jvmcontract::tool_tier!();
    let source = |text: &str| {
        vec![
            ("app/shown/Entry.java", "package app.shown;\npublic final class Entry {\n    public static int shown(int x) {\n        return String.valueOf(new Shown(x)).length();\n    }\n}\n".to_string()),
            ("app/shown/Shown.java", format!("package app.shown;\nfinal class Shown {{\n    private final int x;\n    Shown(int x) {{ this.x = x; }}\n    @Override public String toString() {{ return text(); }}\n    private String text() {{ return x > 0 ? \"{text}\" : \"\"; }}\n}}\n")),
        ]
    };
    let old = compile("shown-old", &source("aa"), &[]);
    let new = compile("shown-new", &source("a"), &[]);
    let mut o = equivalence::Options::new(&old, &new, "app.shown.Entry#shown");
    o.jbmc = NO_JBMC.into();
    o.work = Some(tmp("shown"));
    let o = equivalence::run(&o).unwrap();
    assert!(o.verdict != Verdict::Verified && !o.output.contains("nothing to prove"), "{}", o.output);
}

/// The same through a JDK class whose own code the comparison follows (`Integer`, [`jvmcontract::shared`]):
/// `Integer.parseInt(CharSequence, int, int, int)` calls `charAt` of the object it is given, here the application's.
/// The two versions differ only in that object's private helper. Before 2026-11-17 a call into a followed JDK class
/// was not checked as other JDK calls are, and the target was "identical in both versions; nothing to prove"
/// (checked by hand); on a JVM `parsed(1)` is 22 against 11.
#[test]
fn a_followed_jdk_method_given_an_application_object_leaves_the_code_compared_open() {
    jvmcontract::tool_tier!();
    let source = |digit: char| {
        vec![
            ("app/digits/Entry.java", "package app.digits;\npublic final class Entry {\n    public static int parsed(int x) {\n        return Integer.parseInt(new Digits(x), 0, 2, 10);\n    }\n}\n".to_string()),
            ("app/digits/Digits.java", format!("package app.digits;\nfinal class Digits implements CharSequence {{\n    private final int x;\n    Digits(int x) {{ this.x = x; }}\n    public int length() {{ return 2; }}\n    public char charAt(int i) {{ return digit(); }}\n    private char digit() {{ return x > 0 ? '{digit}' : '0'; }}\n    public CharSequence subSequence(int a, int b) {{ return this; }}\n    @Override public String toString() {{ return \"\"; }}\n}}\n")),
        ]
    };
    let old = compile("digits-old", &source('2'), &[]);
    let new = compile("digits-new", &source('1'), &[]);
    let mut o = equivalence::Options::new(&old, &new, "app.digits.Entry#parsed");
    o.jbmc = NO_JBMC.into();
    o.work = Some(tmp("digits"));
    let o = equivalence::run(&o).unwrap();
    assert!(o.verdict != Verdict::Verified && !o.output.contains("nothing to prove"), "{}", o.output);
}
