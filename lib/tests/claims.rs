//! Claims written in Java beyond the tool's own expression compiler, and what the own checker needs to run them:
//! String and `String[]` parameters, the String and StringBuilder methods a library's string code calls, lambdas
//! and the stream models, `java.util.regex` as far as a claim states a glob or a hash's shape with it, text as
//! bytes and digits, proofs by induction and checked summaries (`lib/src/claim.rs`, `lib/src/summary.rs`,
//! `lib/src/bmc/strings.rs`, `lib/src/bmc/regex.rs`, `lib/src/bmc/bytes.rs`).
//!
//! Each fixture method under `tests/fixtures/claims` returns whether the JDK's answer is the one a definition
//! written out over `charAt` gives, so a proof of `result` is a proof that the model and the definition agree on
//! every input of the bound; the same methods hold on a JVM by sampling, which `claims.Samples` does for the
//! methods of `B` (`lib/README.md`).

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::property::{self, Outcome};
use jvmcontract::{Engine, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";

fn has(program: &str) -> bool {
    let found = Command::new(program).arg("--version").output().map(|o| o.status.success()).unwrap_or(false);
    if !found {
        let skip = std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1");
        assert!(skip, "{program} not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip the tests that need it");
    }
    found
}

/// The fixtures, compiled once with their parameter names.
fn classes() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/claims/claims");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("claims-classes");
        let _ = std::fs::remove_dir_all(&out);
        std::fs::create_dir_all(&out).unwrap();
        let mut files: Vec<PathBuf> = std::fs::read_dir(&sources).unwrap().map(|e| e.unwrap().path()).filter(|p| p.extension().is_some_and(|e| e == "java")).collect();
        files.sort();
        let status = Command::new("javac").args(["-g", "-proc:none", "-d"]).arg(&out).args(files).status().expect("javac runs");
        assert!(status.success(), "the claims fixtures compile");
        Some(out)
    })
    .as_deref()
}

fn options(classes: &Path, target: &str, bound: u32, work: &str) -> property::Options {
    let mut o = property::Options::new(&[classes.to_path_buf()], target);
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.max_array_length = bound;
    o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("claims").join(work));
    o
}

fn run(o: &property::Options) -> Outcome {
    property::run(o).unwrap()
}

fn proved(classes: &Path, target: &str, bound: u32) {
    let o = run(&options(classes, target, bound, &target.replace(['.', '#'], "-")));
    assert_eq!(o.verdict, Verdict::Verified, "{target}: {}", o.output);
}

#[test]
fn the_string_and_builder_methods_are_the_definitions_written_out_over_char_at() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    for method in ["indexOfString", "indexOfChar", "substring", "endsWith", "lower", "builder", "deleteClamps"] {
        proved(classes, &format!("claims.T#{method}"), 3);
    }
    proved(classes, "claims.S#ends", 3);
    // `toLowerCase` reads the default locale: the proof says which it takes for granted.
    let o = run(&options(classes, "claims.T#lower", 2, "lower-stated"));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().expect("a statement");
    assert!(stated.assumptions.iter().any(|a| a.text.contains("the default locale's language is not Turkish, Azeri or Lithuanian")), "{:?}", stated.assumptions);
    // A method of a builder the engine has no model of is the JDK call it was: refused under strict, and under
    // assume the builder's content is no longer the engine's to read, whatever the gap is assumed to do.
    let mut assumed = options(classes, "claims.T#reversed", 2, "reversed-assumed");
    assumed.gaps = jvmcontract::bmc::gaps::GapMode::Assume;
    for (o, why) in [(run(&options(classes, "claims.T#reversed", 2, "reversed")), "java.lang.StringBuilder.reverse()"), (run(&assumed), "on a builder made or changed by a call the engine does not model")] {
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        assert!(o.output.contains(why), "{}", o.output);
    }
}

#[test]
fn a_string_array_parameter_is_strings_of_their_own_or_null_and_a_witness_runs_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let mut o = options(classes, "claims.S#count", 2, "count");
    o.assert = Some("result == 0".into());
    let o = run(&o);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let witness = o.counterexample.as_ref().expect("a witness");
    assert!(witness.input.contains("\"\""), "an array with an empty String: {}", witness.input);
    assert!(o.domain.as_deref().unwrap_or_default().contains("a: String[] of length ≤ 2, not null, each element a String of ≤ 2 code units of its own or null"), "{:?}", o.domain);
}

#[test]
fn lambdas_method_references_and_the_stream_models_run_as_the_loops_they_stand_for() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    for method in ["lambda", "streams", "chars", "range", "mapped"] {
        proved(classes, &format!("claims.L#{method}"), 3);
    }
}

#[test]
fn a_glob_stated_with_the_regex_library_matches_as_the_matcher_written_out() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    for method in ["parts", "constant", "exact", "ignoringCase"] {
        proved(classes, &format!("claims.R#{method}"), 3);
    }
}

/// What a password check does with a hash's text (`lib/src/bmc/bytes.rs`, the constant regexes of
/// `lib/src/bmc/regex.rs`, a builder's appends): each model is its definition written out, on every input of the
/// bound, and each definition is the JDK's method on a JVM, on samples.
#[test]
fn text_as_bytes_and_digits_and_a_hashs_shape_are_the_definitions_written_out() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    for method in ["utf8", "equal", "copied", "parsed", "appended", "digits", "excluded"] {
        proved(classes, &format!("claims.B#{method}"), 3);
    }
    for method in ["shaped", "anchored"] {
        proved(classes, &format!("claims.B#{method}"), 9);
    }
    let sampled = Command::new("java").arg("-cp").arg(classes).args(["claims.Samples", "20000"]).output().expect("java runs");
    assert!(sampled.status.success(), "{}", String::from_utf8_lossy(&sampled.stderr));
    assert_eq!(String::from_utf8_lossy(&sampled.stdout).trim(), "all hold on 20000 samples");
    // What the models do not say stays the JDK's call: another charset's object, a digit outside ASCII.
    for (method, why) in [("latin", "reads static field java.nio.charset.StandardCharsets.ISO_8859_1"), ("unicodeDigits", "jdk-static-method:java.lang.Integer.parseInt(Ljava/lang/String;)I")] {
        let o = run(&options(classes, &format!("claims.B#{method}"), 3, method));
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        assert!(o.output.contains(why), "{}", o.output);
    }
}

/// Lower-casing under a locale that is an input (`lib/src/bmc/locale.rs`): the default locale a path sets is state,
/// a Locale picked from a table at a computed index is a choice among its cells and splits no path, and Turkish and
/// Azeri lower `I` to the dotless i. Each model is its definition written out, on every index and every ASCII String
/// of the bound, and each definition is the JDK's on a JVM, on samples (`Samples`, with the bytes' definitions).
/// What the model does not say is refused by name.
#[test]
fn lower_casing_under_a_locale_that_is_an_input_is_the_definition_written_out() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    for method in ["given", "underTheDefault", "nulls", "itself"] {
        let o = run(&options(classes, &format!("claims.C#{method}"), 3, &format!("C-{method}")));
        assert_eq!(o.verdict, Verdict::Verified, "{method}: {}", o.output);
        // The locale is read from what the path set: nothing is assumed of the JVM's own default.
        let assumed = o.stated.as_ref().is_some_and(|s| s.assumptions.iter().any(|a| a.text.contains("the default locale's language is not Turkish")));
        assert!(!assumed, "{method}: {:?}", o.stated.map(|s| s.assumptions));
    }
    // A wrong claim is refuted on a Turkish or Azeri locale, and the witness is run on a JVM.
    let mut wrong = options(classes, "claims.C#given", 3, "C-given-wrong");
    wrong.assume = Some("k >= 0 && k < 8".into());
    wrong.assert = Some("result && (!s.equals(\"I\") || s.toLowerCase(claims.C.LOCALES[k]).equals(\"i\"))".into());
    let o = run(&wrong);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.output.contains("run on a JVM") && ["k=2", "k=3", "k=6"].iter().any(|k| o.output.contains(k)), "{}", o.output);
    // Whether two Locales are one object is refused by name; a Locale another constructor made is one the engine
    // knows nothing of, and with that constructor assumed, `toLowerCase()` under it is the JDK's call, a gap.
    let o = run(&options(classes, "claims.C#identical", 3, "C-identical"));
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.output.contains("a comparison of two Locale objects by reference"), "{}", o.output);
    for (method, gap) in [("underAnUnknownDefault", "jdk-constructor:java.util.Locale.<init>(Ljava/lang/String;)V"), ("outsideAscii", "jdk-reference-method:java.lang.String.toLowerCase(Ljava/util/Locale;)Ljava/lang/String;")] {
        let o = run(&options(classes, &format!("claims.C#{method}"), 3, &format!("C-{method}")));
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        assert!(o.output.contains(gap), "{}", o.output);
    }
    let mut assumed = options(classes, "claims.C#underAnUnknownDefault", 3, "C-unknown-assumed");
    assumed.gaps = jvmcontract::bmc::gaps::GapMode::Assume;
    let o = run(&assumed);
    assert!(o.output.contains("java.lang.String.toLowerCase()") && o.output.contains("java.util.Locale.<init>"), "{}", o.output);
}

/// A protective pattern that is an input (`Engine::literal_then_any` in `lib/src/bmc/regex.rs`): characters that
/// stand for themselves followed by `.*`, under each combination of `CASE_INSENSITIVE` and `DOTALL`, either chosen by
/// an input, on any String, line terminators and surrogates included. Each model is its definition written out, on
/// every input of the bound, and each definition is the JDK's on a JVM, on samples (`Samples`). The rule is taken
/// only where the solver shows the pattern to be of the family: any other pattern, and any other flag, is the
/// JDK's call, refused by name. With it, what such a claim asks besides: whether an ASCII char is a letter, and
/// that a logger logs nothing below `INFO`, which the run states as an assumption.
#[test]
fn a_literal_followed_by_any_that_is_an_input_matches_as_the_definition_written_out() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    for method in ["exact", "exactDotall", "folded", "foldedDotall", "chosen", "constant"] {
        let o = run(&options(classes, &format!("claims.P#{method}"), 4, &format!("P-{method}")));
        assert_eq!(o.verdict, Verdict::Verified, "{method}: {}", o.output);
    }
    // A wrong claim is refuted on a line terminator after the literal, and the witness is run on a JVM.
    let mut wrong = options(classes, "claims.P#exact", 4, "P-exact-wrong");
    wrong.assume = Some("p.equals(\"/a.*\")".into());
    wrong.assert = Some("result && (!s.startsWith(\"/a\") || java.util.regex.Pattern.compile(p, 0).matcher(s).matches())".into());
    let o = run(&wrong);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.output.contains("run on a JVM"), "{}", o.output);
    for method in ["anyPattern", "anyBeforeTheDot", "anotherFlag"] {
        let o = run(&options(classes, &format!("claims.P#{method}"), 4, &format!("P-{method}")));
        assert_eq!(o.verdict, Verdict::Unverifiable, "{method}: {}", o.output);
        assert!(o.output.contains("jdk-static-method:java.util.regex.Pattern.compile(Ljava/lang/String;I)Ljava/util/regex/Pattern;"), "{method}: {}", o.output);
    }
    let o = run(&options(classes, "claims.P#dotInside", 4, "P-dotInside"));
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.output.contains("jdk-primitive-method:java.lang.String.matches(Ljava/lang/String;)Z"), "{}", o.output);
    proved(classes, "claims.P#letter", 3);
    let o = run(&options(classes, "claims.P#letterOutsideAscii", 3, "P-letterOutsideAscii"));
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.output.contains("jdk-static-method:java.lang.Character.isLetter(C)Z"), "{}", o.output);
    let o = run(&options(classes, "claims.P#quiet", 3, "P-quiet"));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().expect("a statement");
    assert!(stated.assumptions.iter().any(|a| a.text.contains("nothing below INFO is logged")), "{:?}", stated.assumptions);
    let o = run(&options(classes, "claims.P#loud", 3, "P-loud"));
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.output.contains("java.util.logging.Level.INFO"), "{}", o.output);
}

/// A throws clause's condition is Java as the assumption and the assertion are: one over a String's bytes is
/// compiled by javac, proved, and a wrong one refuted on a witness the harness fails on a JVM.
#[test]
fn a_throws_clause_over_a_strings_bytes_is_compiled_by_javac_and_checked() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let bytes = "s.getBytes(java.nio.charset.StandardCharsets.UTF_8).length";
    let mut o = options(classes, "claims.B#guarded", 3, "guarded");
    o.assert = Some("result <= 2".into());
    o.throws = vec![format!("java.lang.IllegalArgumentException when {bytes} > 2")];
    let o = run(&o);
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.output.contains(&format!("throws java.lang.IllegalArgumentException when {bytes} > 2")), "{}", o.output);
    let mut wrong = options(classes, "claims.B#guarded", 3, "guarded-wrong");
    wrong.assert = Some("true".into());
    wrong.throws = vec![format!("java.lang.IllegalArgumentException when {bytes} > 3")];
    let o = run(&wrong);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    assert!(o.output.contains("run on a JVM"), "{}", o.output);
}

/// What a library asks of the JVM before anything else, as far as Spring Security's encoder does: a String's own
/// What a registry that looks through a servlet context's registrations asks of the JDK (`claims.M`, example 290):
/// a stream over an int array, a number in a name, a `LinkedHashMap`'s values in order with their fail-fast
/// iterator, a class by its name with its initialization, whether one class is below another, and the thread's
/// context class loader, each against its definition on every input of the bound.
#[test]
fn registrations_in_order_and_classes_by_name_are_the_definitions_written_out() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    for method in ["ints", "numbered", "ordered", "failsFast", "loaded", "erroneous", "assignable"] {
        proved(classes, &format!("claims.M#{method}"), 3);
    }
    let o = run(&options(classes, "claims.M#threaded", 3, "threaded"));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().expect("a statement");
    assert!(stated.assumptions.iter().any(|a| a.text.contains("whose context class loader is the class loader of the check's class path")), "{:?}", stated.assumptions);
}

/// An initializer the checker does not run (`claims.Tables`: an `IdentityHashMap` and a load factor) is a gap,
/// and with `--observed-initializer` the state a JVM left: what the observation holds is read as the JVM has it,
/// the result says what it rests on, and a field it holds no value of is refused by name.
#[test]
fn an_observed_initializer_gives_the_state_a_jvm_left_and_the_result_says_so() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let unobserved = run(&options(classes, "claims.M#observed", 3, "unobserved"));
    assert_eq!(unobserved.verdict, Verdict::Unverifiable, "{}", unobserved.output);
    assert!(unobserved.output.contains("class-initializer:claims.Tables.<clinit>()V"), "{}", unobserved.output);

    let observing = |target: &str, work: &str, class: &str| {
        let mut o = options(classes, target, 3, work);
        o.observed_initializers = vec![class.to_string()];
        o
    };
    let o = run(&observing("claims.M#observed", "observed", "claims.Tables"));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().expect("a statement");
    let rests_on = "the class initializer of claims.Tables was not run by the checker: its static state is the one a JVM (JDK ";
    assert!(stated.assumptions.iter().any(|a| a.text.starts_with(rests_on) && a.text.contains("it is taken to leave that state in every run")), "{:?}", stated.assumptions);

    let unheld = run(&observing("claims.M#unheld", "unheld", "claims.Tables"));
    assert_eq!(unheld.verdict, Verdict::Unverifiable, "{}", unheld.output);
    assert!(unheld.output.contains("reads the static field claims.Tables.WRAPPERS, which the class's observed initializer left as an object of java.util.IdentityHashMap"), "{}", unheld.output);

    // A class of a JDK package on the class path: the JDK's to the checker, and its statics no check's to read,
    // unless its initializer is observed, which a class below it then waits for.
    let taken_for_the_jdks = run(&options(classes, "claims.M#served", 3, "served-unobserved"));
    assert_eq!(taken_for_the_jdks.verdict, Verdict::Unverifiable, "{}", taken_for_the_jdks.output);
    let served = run(&observing("claims.M#served", "served", "javax.claims.Library"));
    assert_eq!(served.verdict, Verdict::Verified, "{}", served.output);
    assert!(served.stated.as_ref().expect("a statement").assumptions.iter().any(|a| a.text.starts_with("the class initializer of javax.claims.Library was not run by the checker")), "{}", served.output);

    // An initializer that throws on the JVM, and a class the class path does not have, are no observation.
    let threw = property::run(&observing("claims.M#thrown", "thrown", "claims.Fails")).unwrap_err().to_string();
    assert!(threw.contains("--observed-initializer claims.Fails: on the JVM the class's initialization threw java.lang.IllegalStateException"), "{threw}");
    let absent = property::run(&observing("claims.M#thrown", "absent", "claims.Absent")).unwrap_err().to_string();
    assert!(absent.contains("--observed-initializer claims.Absent") && absent.contains("java.lang.ClassNotFoundException"), "{absent}");
    let mut cached = observing("claims.M#observed", "cached", "claims.Tables");
    cached.cache = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("claims").join("no-cache"));
    assert!(property::run(&cached).unwrap_err().to_string().contains("--observed-initializer with --cache"));
}

/// `toString()`, the class of an object the run made, and an initializer that keeps a method reference for the
/// logging library the class path has (the reference it does not keep is never called, and is not walked).
#[test]
fn an_objects_class_a_strings_to_string_and_an_initializer_that_keeps_a_method_reference_run() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    proved(classes, "claims.B#itself", 3);
    let o = run(&options(classes, "claims.B#adapted", 3, "adapted"));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().expect("a statement");
    assert!(stated.assumptions.iter().any(|a| a.text.contains("the classes of the check's class path are loaded by one class loader")), "{:?}", stated.assumptions);
}

#[test]
fn an_expression_the_tools_compiler_does_not_take_is_compiled_by_javac_and_run_as_bytecode() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    // A stream, lambdas and a library call in the assumption and the assertion.
    let mut holds = options(classes, "claims.S#count", 2, "count-javac");
    holds.assume = Some("java.util.Arrays.stream(a).noneMatch(s -> s != null && s.isEmpty())".into());
    holds.assert = Some("result == 0 && java.util.Arrays.stream(a).allMatch(s -> s == null || s.length() > 0)".into());
    let o = run(&holds);
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.output.contains("compiled them as they are written"), "{}", o.output);
    assert!(o.output.contains("not vacuous"), "the probe has the claim's class too: {}", o.output);
    // The statement a reader is shown keeps the expressions as given.
    let statement = std::fs::read_to_string(o.statement.as_ref().unwrap()).unwrap();
    assert!(statement.contains("noneMatch(s -> s != null && s.isEmpty())"), "{statement}");

    let mut fails = options(classes, "claims.S#count", 2, "count-javac-refuted");
    fails.assert = Some("java.util.Arrays.stream(a).allMatch(s -> s == null) || result > 0".into());
    let o = run(&fails);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    // The tool's evaluator does not read an assertion javac compiled: the witness is run in the harness on a JVM,
    // where Java's own libraries say that the assertion fails on it.
    assert!(o.output.contains("run on a JVM") && o.output.contains("where the harness fails on it too"), "{}", o.output);
    assert!(o.replay.as_ref().is_some_and(|r| r.by == "jvm" && r.reproduced), "{:?}", o.replay);

    // What neither compiler takes is refused with javac's own diagnostic.
    let mut wrong = options(classes, "claims.S#count", 2, "count-javac-wrong");
    wrong.assert = Some("java.util.Arrays.stream(a).noSuchMethod()".into());
    let o = run(&wrong);
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("javac does not take the expressions as Java either"), "{}", o.output);
}

const GLOB: &str = "result == java.util.regex.Pattern.compile(String.join(\".*\", java.util.Arrays.stream(pattern.split(\"\\\\*\", -1)).map(java.util.regex.Pattern::quote).toArray(String[]::new)), java.util.regex.Pattern.DOTALL).matcher(text).matches()";
const ASCII: &str = "pattern.chars().allMatch(c -> c < 128) && text.chars().allMatch(c -> c < 128)";

#[test]
fn a_method_that_calls_itself_is_proved_by_induction_on_a_measure_that_decreases() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let mut by_induction = options(classes, "claims.Glob#matches", 3, "glob-induction");
    by_induction.assume = Some(ASCII.into());
    by_induction.assert = Some(GLOB.into());
    by_induction.decreases = Some("pattern.length()".into());
    let o = run(&by_induction);
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.output.contains("by induction on `pattern.length()`"), "{}", o.output);

    // A measure the calls do not decrease proves nothing: the first call of `*` keeps the text.
    let mut no_measure = by_induction.clone();
    no_measure.decreases = Some("text.length()".into());
    no_measure.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("claims").join("glob-no-measure"));
    let o = run(&no_measure);
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("the induction does not go through"), "{}", o.output);

    // A hypothesis that says more than the method does is refuted, not assumed.
    let mut wrong = by_induction.clone();
    wrong.assert = Some("result == pattern.equals(text)".into());
    wrong.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("claims").join("glob-wrong"));
    let o = run(&wrong);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
}

fn lemma_file(name: &str, target: &str, assertion: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("claims").join("lemmas");
    std::fs::create_dir_all(&dir).unwrap();
    let file = dir.join(name);
    std::fs::write(&file, format!("# a lemma\n{target}\n  assume: {ASCII}\n  assert: {assertion}\n  decreases: pattern.length()\n")).unwrap();
    file
}

#[test]
fn a_lemma_is_proved_first_and_its_summary_stands_in_for_the_calls_of_its_method() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let claim = |work: &str, lemmas: PathBuf| {
        let mut o = options(classes, "claims.Glob#any", 3, work);
        o.assume = Some("field.chars().allMatch(c -> c < 128) && java.util.Arrays.stream(patterns).allMatch(p -> p == null || p.chars().allMatch(c -> c < 128))".into());
        o.assert = Some("result == claims.Glob.anyByRegex(patterns, field)".into());
        o.lemmas = Some(lemmas);
        o
    };
    let o = run(&claim("any-lemma", lemma_file("glob.contract", "claims.Glob#matches", GLOB)));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.output.contains("lemma: ✓ claims.Glob#matches"), "the lemma's own proof is shown: {}", o.output);
    assert!(o.output.contains("note: lemma, proved above by induction on `pattern.length()`"), "{}", o.output);
    let stated = o.stated.as_ref().expect("a statement");
    assert!(stated.assumptions.iter().any(|a| a.text.contains("claims.Glob#matches satisfies") && a.text.contains("proved beside this check")), "{:?}", stated.assumptions);

    // A lemma that is not true is refuted, and the check that would rest on it is refused.
    let o = run(&claim("any-false-lemma", lemma_file("false.contract", "claims.Glob#matches", "result == pattern.equals(text)")));
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("is not proved"), "{}", o.output);

    // A method that writes a static field, or compares its arguments by identity, is no method a summary states.
    for (target, why) in [("claims.Glob#counted", "writes a static field"), ("claims.Glob#unlessSame", "compares an object it was given by identity")] {
        let o = run(&claim(&format!("any-{}", &target[12..]), lemma_file(&format!("{}.contract", &target[12..]), target, "result == result")));
        assert_eq!(o.verdict, Verdict::Unverifiable, "{target}: {}", o.output);
        assert!(o.problem.as_deref().unwrap_or_default().contains(why), "{target}: {}", o.output);
    }
}
