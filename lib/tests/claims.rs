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
    for method in ["indexOfString", "indexOfChar", "lastIndexOfPoint", "substring", "endsWith", "lower", "builder", "deleteClamps", "longBuilder"] {
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
    for method in ["lambda", "streams", "chars", "range", "mapped", "optional"] {
        proved(classes, &format!("claims.L#{method}"), 3);
    }
}

#[test]
fn a_glob_stated_with_the_regex_library_matches_as_the_matcher_written_out() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    for method in ["parts", "constant", "exact", "ignoringCase", "caseRanges"] {
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
    for method in ["utf8", "named", "equal", "copied", "parsed", "appended", "digits", "excluded"] {
        proved(classes, &format!("claims.B#{method}"), 3);
    }
    for method in ["shaped", "anchored"] {
        proved(classes, &format!("claims.B#{method}"), 9);
    }
    let sampled = Command::new("java").arg("-cp").arg(classes).args(["claims.Samples", "20000"]).output().expect("java runs");
    assert!(sampled.status.success(), "{}", String::from_utf8_lossy(&sampled.stderr));
    assert_eq!(String::from_utf8_lossy(&sampled.stdout).trim(), "all hold on 20000 samples");
    // What the models do not say stays the JDK's call: another charset's object, a digit outside ASCII.
    for (method, why) in [("latin", "reads static field java.nio.charset.StandardCharsets.ISO_8859_1"), ("latinNamed", "java.lang.String.getBytes"), ("unicodeDigits", "jdk-static-method:java.lang.Integer.parseInt(Ljava/lang/String;)I")] {
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

/// The one gap example 286's fixed protected-state task meets on its real path under the frozen claim (job
/// 20261117-222610; the example's `records/refusals/fixed-protected-state-mutation-beside-route.json`):
/// `field.toLowerCase()` in `DataBinder.isAllowed` of a String with a unit outside ASCII, which the checker leaves
/// the JDK's call (`lib/src/bmc/strings.rs`). `claims.C#loweredToAge` is the decision that call serves, true for
/// every String on a JVM: no code point outside ASCII lowers to `a`, `g` or `e` under any locale of the table (the
/// fixture's `main` sweeps them all). Over ASCII Strings it is proved, under the locale assumption. The gap is closed
/// when the first check below is proved, with no assumption beyond the locale's: then rerun 286's task at bound 8.
#[test]
fn lowering_outside_ascii_is_the_one_gap_286s_fixed_protected_state_task_stops_at() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let swept = Command::new("java").args(["-XX:-UsePerfData", "-cp"]).arg(classes).arg("claims.C").output().expect("java runs");
    assert!(swept.status.success(), "{}", String::from_utf8_lossy(&swept.stderr));
    assert_eq!(String::from_utf8_lossy(&swept.stdout).trim(), "no code point outside ASCII lowers to a, g or e");
    let o = run(&options(classes, "claims.C#loweredToAge", 3, "C-loweredToAge"));
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.output.contains("jdk-reference-method:java.lang.String.toLowerCase()Ljava/lang/String;"), "{}", o.output);
    let mut ascii = options(classes, "claims.C#loweredToAge", 3, "C-loweredToAge-ascii");
    ascii.assume = Some("s.chars().allMatch(c -> c < 128)".into());
    let o = run(&ascii);
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.map(|s| s.assumptions).unwrap_or_default();
    assert!(stated.iter().any(|a| a.text == jvmcontract::bmc::strings::LOCALE_ASSUMPTION), "{stated:?}");
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
}

/// A line logged at WARNING as Spring's logging adapter logs one (example 287's encoder, for a stored hash that is
/// empty or not bcrypt's) returns normally under the default logging configuration, which the result states. What
/// would make logging observable stops the proof where it is set up: a level, a filter or a handler set on a
/// logger, and a record that writes elsewhere when the handler formats it. On a JVM each of those four returns false
/// or throws, where a model that took logging for granted would prove it true.
#[test]
fn a_line_logged_at_warning_returns_normally_and_what_would_make_logging_observable_stops_the_proof() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    for method in ["loud", "warned", "nulls"] {
        let o = run(&options(classes, &format!("claims.Logged#{method}"), 3, &format!("Logged-{method}")));
        assert_eq!(o.verdict, Verdict::Verified, "{method}: {}", o.output);
        let stated = o.stated.as_ref().expect("a statement");
        if method != "nulls" {
            assert!(stated.assumptions.iter().any(|a| a.text.contains("true for INFO, WARNING and SEVERE")), "{method}: {:?}", stated.assumptions);
        }
        if method == "warned" {
            assert!(stated.assumptions.iter().any(|a| a.text.contains("no logger has a filter, a handler of its own or a resource bundle")), "{:?}", stated.assumptions);
        }
    }
    for (method, stop) in [
        ("off", "java.util.logging.Level.OFF"),
        ("described", "java.lang.String.valueOf(Ljava/lang/Object;)Ljava/lang/String;"),
        ("counted", "java.util.logging.Logger.log(Ljava/util/logging/LogRecord;)V"),
        ("levelled", "java.util.logging.Logger.setLevel"),
        ("filtered", "java.util.logging.Logger.setFilter"),
        ("handled", "java.util.logging.Handler.<init>"),
    ] {
        let o = run(&options(classes, &format!("claims.Logged#{method}"), 3, &format!("Logged-{method}")));
        assert_eq!(o.verdict, Verdict::Unverifiable, "{method}: {}", o.output);
        assert!(o.output.contains(stop), "{method}: {}", o.output);
    }
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
/// iterator, the list `Arrays.asList` makes of an array, a class by its name with its initialization, whether one class is below another, and the thread's
/// context class loader, each against its definition on every input of the bound.
#[test]
fn registrations_in_order_and_classes_by_name_are_the_definitions_written_out() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    for method in ["ints", "numbered", "ordered", "failsFast", "listed", "emptied", "loaded", "erroneous", "assignable"] {
        proved(classes, &format!("claims.M#{method}"), 3);
    }
    let o = run(&options(classes, "claims.M#threaded", 3, "threaded"));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().expect("a statement");
    assert!(stated.assumptions.iter().any(|a| a.text.contains("whose context class loader is the class loader of the check's class path")), "{:?}", stated.assumptions);
}

/// An initializer the checker does not run (`claims.Tables`: an `IdentityHashMap` and a load factor) is a gap,
/// and with `--observed-initializer` the state a JVM left: what the observation holds is read as the JVM has it,
/// the result says what it rests on, and a field it holds no value of is refused by name. A class it initialized
/// that holds a lambda (`claims.Hooked`) is bound as it is alone, whatever address the JVM put in the lambda's name.
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
    // An initializer that initializes a class holding a lambda: the lambda's hidden class is named alike in the
    // observation and in the run of that class alone, though the JVM's address in its name is not.
    let hooked = run(&observing("claims.Hooking#hooked", "hooked", "claims.Hooked"));
    assert_eq!(hooked.verdict, Verdict::Verified, "{}", hooked.output);
    let mut cached = observing("claims.M#observed", "cached", "claims.Tables");
    cached.cache = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("claims").join("no-cache"));
    assert!(property::run(&cached).unwrap_err().to_string().contains("--observed-initializer with --cache"));
}

/// An observation made with a relative `--work`, from a directory other than the class path's: the observer's JVM
/// runs in the work folder, so the log of its class initializations, and the path the observer is given to read it,
/// must not be taken relative to that folder (job `20261117-181750`: "Invalid -Xlog option", no observation).
#[test]
fn an_observed_initializer_is_observed_with_a_relative_work_folder() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let here = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("claims").join("relative-work");
    let _ = std::fs::remove_dir_all(&here);
    std::fs::create_dir_all(&here).unwrap();
    let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract"))
        .current_dir(&here)
        .args(["prove", "claims.M#observed", "--observed-initializer", "claims.Tables", "--engine", "native", "--jbmc", NO_JBMC, "--max-array-length", "3", "--details", "--work", "work/observed", "--classes"])
        .arg(classes)
        .output()
        .unwrap();
    let said = String::from_utf8_lossy(&out.stdout).to_string() + &String::from_utf8_lossy(&out.stderr);
    assert!(said.starts_with("✓") && said.contains("the class initializer of claims.Tables was not run by the checker"), "{said}");
    assert!(here.join("work/observed/observed/claims.Tables.init.log").is_file(), "the log is in the work folder: {said}");
}

#[test]
fn utf16_encoding_preserves_code_units_and_rejects_invalid_points_before_writing() {
    jvmcontract::tool_tier!();
    use jvmcontract::interp::{Machine, Value};
    let Some(classes) = classes() else { return };
    assert!(Command::new("java").arg("-cp").arg(classes).arg("claims.UnicodePoints").status().unwrap().success());
    for method in ["encoding", "block"] {
        proved(classes, &format!("claims.UnicodePoints#{method}"), 3);
    }
    let cp = jvmcontract::witness::classpath([classes]).unwrap();
    let mut interpreter = Machine::new(&cp);
    for c in [-1, 0, 0xd800, 0xdc00, 0xffff, 0x10000, 0x2070e, 0x10ffff, 0x110000] {
        assert_eq!(interpreter.call_static("claims/UnicodePoints", "encoding", "(I)Z", vec![Value::Int(c)]).unwrap(), Some(Value::Int(1)));
    }
}

#[test]
fn enum_order_checks_the_declaring_class_on_the_jvm_in_proof_and_in_replay() {
    jvmcontract::tool_tier!();
    use jvmcontract::interp::{Machine, Value};
    let Some(classes) = classes() else { return };
    assert!(Command::new("java").arg("-cp").arg(classes).arg("claims.EnumOrder").status().unwrap().success());
    proved(classes, "claims.EnumOrder#order", 3);
    let cp = jvmcontract::witness::classpath([classes]).unwrap();
    let mut interpreter = Machine::new(&cp);
    for pick in [0, 1] {
        assert_eq!(interpreter.call_static("claims/EnumOrder", "order", "(Z)Z", vec![Value::Int(pick)]).unwrap(), Some(Value::Int(1)));
    }
}

#[test]
fn a_single_threaded_registry_preserves_aliases_values_and_null_exceptions() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let model = "java.util.concurrent.ConcurrentHashMap";
    for key in ["true", "false"] {
        assert!(Command::new("java").arg("-cp").arg(classes).args(["claims.Registries", key]).status().unwrap().success());
    }
    let check = |method: &str, observe: bool, select: bool| {
        let mut o = options(classes, &format!("claims.Registries#{method}"), 3, &format!("registry-{method}-{select}"));
        if observe { o.observed_initializers.push("claims.Registries$State".into()); }
        if select { o.requested_models.push(model.into()); }
        run(&o)
    };
    let held = check("register", true, true);
    assert_eq!(held.verdict, Verdict::Verified, "{}", held.output);
    let assumptions = &held.stated.unwrap().assumptions;
    for text in ["the class initializer of claims.Registries", "single-threaded ConcurrentHashMap"] {
        assert!(assumptions.iter().any(|a| a.text.contains(text)), "{assumptions:?}");
    }
    let capacity = check("nullsAndCapacity", false, true);
    assert_eq!(capacity.verdict, Verdict::Verified, "{}", capacity.output);
    for (method, observed, selected, reason) in [
        ("register", true, false, "needs --model"),
        ("readPopulated", true, true, "an object of java.util.concurrent.ConcurrentHashMap"),
        ("nonStringKey", false, true, "outside the single-threaded String-key model"),
    ] {
        let out = check(method, observed, selected);
        assert_eq!(out.verdict, Verdict::Unverifiable, "{}", out.output);
        assert!(out.output.contains(reason), "{}", out.output);
    }
}

/// The lists a registry collects its matchers in (`claims.M`, example 290). `java.util.ArrayList` is the JDK's,
/// each of its calls a gap, until a check asks for the model (`--model java.util.ArrayList`): then the model is
/// its definition written out on every input of the bound, the result says what it rests on, and a method the
/// model does not keep is still the JDK call it names. `Arrays.copyOf` of an array of references, which the model
/// grows by, is modelled for every check, and so is a `ConcurrentHashMap` made empty, the cache a matcher's
/// constructor makes and these paths never ask.
#[test]
fn an_array_list_is_the_jdks_until_a_check_asks_for_the_model_which_is_its_definition_written_out() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let unasked = run(&options(classes, "claims.M#collected", 3, "collected-unasked"));
    assert_eq!(unasked.verdict, Verdict::Unverifiable, "{}", unasked.output);
    assert!(unasked.output.contains("jdk-constructor:java.util.ArrayList.<init>(I)V"), "{}", unasked.output);

    let asking = |target: &str, work: &str, model: &str| {
        let mut o = options(classes, target, 3, work);
        o.requested_models = vec![model.to_string()];
        o
    };
    for method in ["collected", "filled", "appended", "swept", "removed"] {
        let o = run(&asking(&format!("claims.M#{method}"), &format!("M-{method}"), "java.util.ArrayList"));
        assert_eq!(o.verdict, Verdict::Verified, "{method}: {}", o.output);
        let stated = o.stated.as_ref().expect("a statement");
        assert!(stated.assumptions.iter().any(|a| a.text.starts_with("java.util.ArrayList is the tool's model of the class wherever the check runs it (--model), not the JDK's code")), "{method}: {:?}", stated.assumptions);
    }
    proved(classes, "claims.M#recopied", 3);
    proved(classes, "claims.M#cached", 3);
    // A check that asks for the model and runs none of it does not rest on it.
    let unused = run(&asking("claims.M#recopied", "M-recopied-asking", "java.util.ArrayList"));
    assert_eq!(unused.verdict, Verdict::Verified, "{}", unused.output);
    assert!(!unused.stated.as_ref().expect("a statement").assumptions.iter().any(|a| a.text.contains("the tool's model of the class")), "{}", unused.output);

    // `Boolean.TRUE` and `Boolean.FALSE`, which a list's owner may store (Spring's `PropertyValue`): one object each;
    // what one says is the JDK's call.
    proved(classes, "claims.M#truths", 3);
    let told = run(&options(classes, "claims.M#truthTold", 3, "M-truthTold"));
    assert_eq!(told.verdict, Verdict::Unverifiable, "{}", told.output);
    assert!(told.output.contains("java.lang.Boolean.booleanValue()Z"), "{}", told.output);

    // A String's class, as Spring's `ClassUtils.getDescriptiveType` names a value (example 286): the literal of
    // `String`, its type name its name, and no proxy class; `Proxy.isProxyClass(null)` throws.
    proved(classes, "claims.M#typed", 3);
    proved(classes, "claims.M#unproxied", 1);

    let left_out = run(&asking("claims.M#contained", "M-contained", "java.util.ArrayList"));
    assert_eq!(left_out.verdict, Verdict::Unverifiable, "{}", left_out.output);
    assert!(left_out.output.contains("java.util.ArrayList.contains(Ljava/lang/Object;)Z"), "{}", left_out.output);

    let none = property::run(&asking("claims.M#swept", "M-none", "java.util.Vector")).unwrap_err().to_string();
    assert!(none.contains("--model java.util.Vector: no model on request of that class; there is one of java.util.ArrayList, java.util.ArrayDeque, java.util.HashSet, java.util.LinkedHashSet, java.util.StringJoiner, java.beans.PropertyChangeEvent"), "{none}");
    let mut cached = asking("claims.M#swept", "M-cached", "java.util.ArrayList");
    cached.cache = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("claims").join("no-cache"));
    assert!(property::run(&cached).unwrap_err().to_string().contains("--model with --cache"));
}

/// A stack of `java.util.ArrayDeque`, as Spring's `AbstractErrors` keeps its nested paths (`claims.Deques`, example
/// 286): the JDK's, its constructor a gap, until a check asks for the model (`--model java.util.ArrayDeque`); then
/// the model is the definition written out on every input of the bound, and a method it does not keep (`offer`) is
/// still the JDK call it names. The same methods hold on a JVM, over sampled inputs, on the JDK's deque.
#[test]
fn an_array_deque_is_the_jdks_until_a_check_asks_for_the_model_which_is_its_definition_written_out() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let sampled = Command::new("java").arg("-cp").arg(classes).args(["claims.Deques", "5000"]).output().expect("java runs");
    assert_eq!(String::from_utf8_lossy(&sampled.stdout).trim(), "ok", "{}", String::from_utf8_lossy(&sampled.stderr));

    let unasked = run(&options(classes, "claims.Deques#stacked", 3, "Deques-unasked"));
    assert_eq!(unasked.verdict, Verdict::Unverifiable, "{}", unasked.output);
    assert!(unasked.output.contains("java.util.ArrayDeque.<init>()V"), "{}", unasked.output);

    let asking = |method: &str| {
        let mut o = options(classes, &format!("claims.Deques#{method}"), 3, &format!("Deques-{method}"));
        o.requested_models = vec!["java.util.ArrayDeque".to_string()];
        o
    };
    for method in ["stacked", "refused", "cleared"] {
        let o = run(&asking(method));
        assert_eq!(o.verdict, Verdict::Verified, "{method}: {}", o.output);
        let stated = o.stated.as_ref().expect("a statement");
        assert!(stated.assumptions.iter().any(|a| a.text.starts_with("java.util.ArrayDeque is the tool's model of the class wherever the check runs it (--model)")), "{method}: {:?}", stated.assumptions);
    }
    let left_out = run(&asking("offered"));
    assert_eq!(left_out.verdict, Verdict::Unverifiable, "{}", left_out.output);
    assert!(left_out.output.contains("java.util.Deque.offer(Ljava/lang/Object;)Z") || left_out.output.contains("java.util.ArrayDeque.offer(Ljava/lang/Object;)Z"), "{}", left_out.output);
}

/// A `java.beans.PropertyChangeEvent`, as Spring's bean wrapper makes one for a value it cannot convert
/// (`claims.Events`, example 286): the JDK's, its constructor a gap, until a check asks for the model (`--model
/// java.beans.PropertyChangeEvent`, which runs the model of `java.util.EventObject` with it); then the model is the
/// definition written out on every input of the bound, and `toString`, which it does not keep, is still the JDK call
/// it names. The same methods hold on a JVM, over sampled inputs, on the JDK's event.
#[test]
fn a_property_change_event_is_the_jdks_until_a_check_asks_for_the_model_which_is_its_definition_written_out() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let sampled = Command::new("java").arg("-cp").arg(classes).args(["claims.Events", "5000"]).output().expect("java runs");
    assert_eq!(String::from_utf8_lossy(&sampled.stdout).trim(), "ok", "{}", String::from_utf8_lossy(&sampled.stderr));

    let unasked = run(&options(classes, "claims.Events#made", 3, "Events-unasked"));
    assert_eq!(unasked.verdict, Verdict::Unverifiable, "{}", unasked.output);
    assert!(unasked.output.contains("java.beans.PropertyChangeEvent.<init>(Ljava/lang/Object;Ljava/lang/String;Ljava/lang/Object;Ljava/lang/Object;)V"), "{}", unasked.output);

    let asking = |method: &str| {
        let mut o = options(classes, &format!("claims.Events#{method}"), 3, &format!("Events-{method}"));
        o.requested_models = vec!["java.beans.PropertyChangeEvent".to_string()];
        o
    };
    let o = run(&asking("made"));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().expect("a statement");
    assert!(stated.assumptions.iter().any(|a| a.text.starts_with("java.beans.PropertyChangeEvent is the tool's model of the class wherever the check runs it (--model)")), "{:?}", stated.assumptions);
    let left_out = run(&asking("described"));
    assert_eq!(left_out.verdict, Verdict::Unverifiable, "{}", left_out.output);
    assert!(left_out.output.contains("java.beans.PropertyChangeEvent.toString()"), "{}", left_out.output);

}

/// A `java.util.HashSet` of names, as Spring's `AbstractBindingResult` records suppressed fields (`claims.Sets`,
/// example 286): the JDK's until a check asks for the model (`--model java.util.HashSet`), then the keys of the
/// `HashMap` model, which is the definition written out over `equals` on every input of the bound; `remove`, which
/// it does not keep, is still the JDK call it names. The same methods hold on a JVM over sampled names.
#[test]
fn a_hash_set_is_the_jdks_until_a_check_asks_for_the_model_which_is_its_definition_written_out() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let sampled = Command::new("java").arg("-cp").arg(classes).args(["claims.Sets", "5000"]).output().expect("java runs");
    assert_eq!(String::from_utf8_lossy(&sampled.stdout).trim(), "ok", "{}", String::from_utf8_lossy(&sampled.stderr));

    let unasked = run(&options(classes, "claims.Sets#added", 2, "Sets-unasked"));
    assert_eq!(unasked.verdict, Verdict::Unverifiable, "{}", unasked.output);
    assert!(unasked.output.contains("java.util.HashSet.<init>()V"), "{}", unasked.output);

    let asking = |method: &str| {
        let mut o = options(classes, &format!("claims.Sets#{method}"), 2, &format!("Sets-{method}"));
        o.requested_models = vec!["java.util.HashSet".to_string()];
        o
    };
    let o = run(&asking("added"));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().expect("a statement");
    assert!(stated.assumptions.iter().any(|a| a.text.starts_with("java.util.HashSet is the tool's model of the class wherever the check runs it (--model)")), "{:?}", stated.assumptions);
    let left_out = run(&asking("removed"));
    assert_eq!(left_out.verdict, Verdict::Unverifiable, "{}", left_out.output);
    assert!(left_out.output.contains("remove(Ljava/lang/Object;)Z"), "{}", left_out.output);
}

/// A `java.util.LinkedHashSet` of names, as Spring's `DefaultMessageCodesResolver` collects a binding error's message
/// codes (`claims.LinkedSets`, example 286): the JDK's until a check asks for the model (`--model
/// java.util.LinkedHashSet`, which runs the `HashSet` model above it too), then the definition written out over
/// `equals` on every input of the bound, the elements in the order first added; `iterator`, which it does not keep,
/// is still the JDK call it names. The same methods hold on a JVM over sampled names.
#[test]
fn a_linked_hash_set_is_the_jdks_until_a_check_asks_for_the_model_which_is_its_definition_written_out() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let sampled = Command::new("java").arg("-XX:-UsePerfData").arg("-cp").arg(classes).args(["claims.LinkedSets", "5000"]).output().expect("java runs");
    assert_eq!(String::from_utf8_lossy(&sampled.stdout).trim(), "ok", "{}", String::from_utf8_lossy(&sampled.stderr));

    let unasked = run(&options(classes, "claims.LinkedSets#ordered", 2, "LinkedSets-unasked"));
    assert_eq!(unasked.verdict, Verdict::Unverifiable, "{}", unasked.output);
    assert!(unasked.output.contains("java.util.LinkedHashSet.<init>()V"), "{}", unasked.output);

    let asking = |method: &str| {
        let mut o = options(classes, &format!("claims.LinkedSets#{method}"), 3, &format!("LinkedSets-{method}"));
        o.requested_models = vec!["java.util.LinkedHashSet".to_string()];
        o
    };
    let o = run(&asking("ordered"));
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let stated = o.stated.as_ref().expect("a statement");
    for model in ["java.util.LinkedHashSet", "java.util.HashSet"] {
        assert!(stated.assumptions.iter().any(|a| a.text.starts_with(&format!("{model} is the tool's model of the class wherever the check runs it (--model)"))), "{model}: {:?}", stated.assumptions);
    }
    let left_out = run(&asking("iterated"));
    assert_eq!(left_out.verdict, Verdict::Unverifiable, "{}", left_out.output);
    assert!(left_out.output.contains("iterator()Ljava/util/Iterator;"), "{}", left_out.output);
}

/// A `java.util.StringJoiner`, as Spring's `DefaultMessageCodesResolver.Format.toDelimitedString` joins a message
/// code (`claims.Joiners`, example 286): the JDK's until a check asks for the model (`--model
/// java.util.StringJoiner`), then the definition written out over `charAt` on every input of the bound; an empty
/// join, which the model leaves to the JDK's `new String()`, is still that JDK call. The same methods hold on a JVM
/// over sampled Strings.
#[test]
fn a_string_joiner_is_the_jdks_until_a_check_asks_for_the_model_which_is_its_definition_written_out() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let sampled = Command::new("java").arg("-XX:-UsePerfData").arg("-cp").arg(classes).args(["claims.Joiners", "5000"]).output().expect("java runs");
    assert_eq!(String::from_utf8_lossy(&sampled.stdout).trim(), "ok", "{}", String::from_utf8_lossy(&sampled.stderr));

    let unasked = run(&options(classes, "claims.Joiners#addedNull", 2, "Joiners-unasked"));
    assert_eq!(unasked.verdict, Verdict::Unverifiable, "{}", unasked.output);
    assert!(unasked.output.contains("java.util.StringJoiner.<init>(Ljava/lang/CharSequence;)V"), "{}", unasked.output);

    let asking = |method: &str| {
        let mut o = options(classes, &format!("claims.Joiners#{method}"), 2, &format!("Joiners-{method}"));
        o.requested_models = vec!["java.util.StringJoiner".to_string()];
        o
    };
    for method in ["joined", "addedNull"] {
        let o = run(&asking(method));
        assert_eq!(o.verdict, Verdict::Verified, "{method}: {}", o.output);
        let stated = o.stated.as_ref().expect("a statement");
        assert!(stated.assumptions.iter().any(|a| a.text.starts_with("java.util.StringJoiner is the tool's model of the class wherever the check runs it (--model)")), "{method}: {:?}", stated.assumptions);
    }
    let left_out = run(&asking("empty"));
    assert_eq!(left_out.verdict, Verdict::Unverifiable, "{}", left_out.output);
    assert!(left_out.output.contains("java.lang.String.<init>()V"), "{}", left_out.output);
}

/// `Class.isArray()` of a class literal, as Spring's `ObjectUtils.isArray` asks it of a rejected value's class
/// (`claims.Arrayed`, example 286): whether the literal names an array class. On a class the engine holds no literal
/// of, it and `isAssignableFrom` stay the JDK calls they are, and under `--gaps assume` too, since no assumption makes
/// up a primitive result: the run is refused by name, where a JVM answers true.
#[test]
fn a_class_literal_says_whether_it_is_an_array_class_and_another_class_is_the_jdks_to_say() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let jvm = Command::new("java").arg("-XX:-UsePerfData").arg("-cp").arg(classes).arg("claims.Arrayed").output().expect("java runs");
    assert_eq!(String::from_utf8_lossy(&jvm.stdout).trim(), "true true true", "{}", String::from_utf8_lossy(&jvm.stderr));
    proved(classes, "claims.Arrayed#arrayed", 2);
    for (method, call) in [("ofAnArray", "java.lang.Class.isArray()"), ("assignableOfAnArray", "java.lang.Class.isAssignableFrom(java.lang.Class)")] {
        // Under strict the run stops at the array's `getClass()`; under assume that gives a Class the engine holds
        // no literal of, and the run stops at the call on it.
        for (mode, stop) in [(jvmcontract::bmc::gaps::GapMode::Strict, "java.lang.Object.getClass()"), (jvmcontract::bmc::gaps::GapMode::Assume, call)] {
            let mut o = options(classes, &format!("claims.Arrayed#{method}"), 1, &format!("Arrayed-{method}-{mode:?}"));
            o.gaps = mode;
            let o = run(&o);
            assert_eq!(o.verdict, Verdict::Unverifiable, "{method} {mode:?}: {}", o.output);
            assert!(o.output.contains(stop), "{method} {mode:?}: {}", o.output);
        }
    }
}

/// An exception's message and cause, kept from the JDK's constructor that set them (`lib/src/bmc/throwables.rs`,
/// `claims.Thrown`, example 286's binding error): `getMessage`, `getCause`, `getLocalizedMessage` (an application's
/// `getMessage` runs in its place), `toString`, `getClass()`, and a builder's `StringBuilder(int)` and
/// `append(Object)`, each proved as `Throwable`'s Javadoc gives it and true on a JVM. What the engine does not know
/// stays the JDK's, each where a JVM breaks the statement: an application's `fillInStackTrace()`, which the JVM runs
/// inside the constructor, is refused by name; a JDK constructor that does more than pass its arguments up
/// (`UnknownFormatConversionException(null)` throws) is the gap it is, as are `toString()` where the class overrides
/// it or the message, and `append` of such an exception.
#[test]
fn an_exceptions_message_and_cause_are_kept_from_the_jdks_constructor() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let jvm = Command::new("java").arg("-XX:-UsePerfData").arg("-cp").arg(classes).arg("claims.Thrown").output().expect("java runs");
    assert_eq!(
        String::from_utf8_lossy(&jvm.stdout).trim(),
        "kept=true true shown=true true nested=true appended=true countsNothing=false nullConversion=false shownAppended=false nestedShown=false",
        "{}",
        String::from_utf8_lossy(&jvm.stderr)
    );
    for method in ["kept", "shown", "nested", "appended"] {
        proved(classes, &format!("claims.Thrown#{method}"), 3);
    }
    for (method, why) in [
        ("countsNothing", "whose claims.Thrown$Counting.fillInStackTrace() the JVM runs inside the constructor"),
        ("nullConversion", "java.util.UnknownFormatConversionException.<init>"),
        ("shownAppended", "java.lang.StringBuilder.append(Ljava/lang/Object;)"),
        ("nestedShown", "jdk-reference-method:claims.Thrown$Nested.toString()"),
    ] {
        let o = run(&options(classes, &format!("claims.Thrown#{method}"), 1, &format!("Thrown-{method}")));
        assert_eq!(o.verdict, Verdict::Unverifiable, "{method}: {}", o.output);
        assert!(o.output.contains(why), "{method}: {}", o.output);
    }
}

/// Under `--gaps assume` a JDK call that returns an object returns one of its declared class or of any below it
/// (`claims.Cloned`: `Object.clone()` of a `Cloned` is one). The engine does not know which, so a virtual call on it
/// (the class's override runs on a JVM) and a type test the declared class does not settle are refused by name, and
/// what the declared class settles is proved. `tests/rule_countermodels.rs` has the challenge stream's cases.
#[test]
fn an_object_a_jdk_call_returns_under_assume_is_of_a_class_the_engine_does_not_know() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let jvm = Command::new("java").arg("-cp").arg(classes).arg("claims.Cloned").output().expect("java runs");
    assert_eq!(String::from_utf8_lossy(&jvm.stdout).trim(), "printsNothing=false notCloneable=false anObject=true", "{}", String::from_utf8_lossy(&jvm.stderr));
    let assumed = |method: &str| {
        let mut o = options(classes, &format!("claims.Cloned#{method}"), 2, &format!("Cloned-{method}"));
        o.gaps = jvmcontract::bmc::gaps::GapMode::Assume;
        run(&o)
    };
    for (method, why) in [("printsNothing", "a call of java.lang.Object.toString()"), ("notCloneable", "an instanceof java.lang.Cloneable")] {
        let o = assumed(method);
        assert_eq!(o.verdict, Verdict::Unverifiable, "{method}: {}", o.output);
        assert!(o.output.contains(why) && o.output.contains("may be of any class below that one"), "{method}: {}", o.output);
    }
    let o = assumed("anObject");
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
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

    // A method that counts in a static field (which it reads first, to add one), writes one, or compares its
    // arguments by identity, is no method a summary states.
    for (target, why) in [("claims.Glob#counted", "reads the static field claims.Glob.calls"), ("claims.Glob#marked", "writes a static field"), ("claims.Glob#unlessSame", "compares an object it was given by identity")] {
        let o = run(&claim(&format!("any-{}", &target[12..]), lemma_file(&format!("{}.contract", &target[12..]), target, "result == result")));
        assert_eq!(o.verdict, Verdict::Unverifiable, "{target}: {}", o.output);
        assert!(o.problem.as_deref().unwrap_or_default().contains(why), "{target}: {}", o.output);
    }
}

fn lemmas(name: &str, text: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("claims").join("lemmas");
    std::fs::create_dir_all(&dir).unwrap();
    let file = dir.join(name);
    std::fs::write(&file, text).unwrap();
    file
}

/// The countermodels of `claims.Effects`: each property below is false on a JVM (`Effects.main`), so a `Verified`
/// here is a false proof.
#[test]
fn a_proof_by_induction_is_not_of_a_method_whose_calls_of_itself_write_or_throw() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    // The hypothesis states a result: a call it stands in for must leave nothing else behind. `counting(1)` is 2.
    let mut counting = options(classes, "claims.Effects#counting", 3, "effects-counting");
    counting.assume = Some("n >= 0 && n <= 3".into());
    counting.assert = Some("result == 1".into());
    counting.decreases = Some("n".into());
    let o = run(&counting);
    assert_ne!(o.verdict, Verdict::Verified, "{}", o.output);
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("writes a static field"), "{}", o.output);

    // The hypothesis returns: where the property says a call throws, it does not stand in for the call.
    // `throwing(1)` throws, and the property says it returns 1.
    let mut throwing = options(classes, "claims.Effects#throwing", 3, "effects-throwing");
    throwing.assume = Some("n >= 0 && n <= 3".into());
    throwing.assert = Some("result == n".into());
    throwing.throws = vec!["java.lang.IllegalStateException when n == 0".into()];
    throwing.decreases = Some("n".into());
    let o = run(&throwing);
    assert_ne!(o.verdict, Verdict::Verified, "{}", o.output);
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("the induction does not go through"), "{}", o.output);

    // A throws clause no call of the method by itself meets leaves the induction as it was.
    let mut checked = options(classes, "claims.Effects#checked", 3, "effects-checked");
    checked.assume = Some("n <= 3".into());
    checked.assert = Some("result == n".into());
    checked.throws = vec!["java.lang.IllegalArgumentException when n < 0".into()];
    checked.decreases = Some("n".into());
    let o = run(&checked);
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);

    // What the method reads is no obstacle to its own induction: its calls of itself are made in the state of the
    // call under proof, which nothing it runs may write. (A summary of it would be refused: the test below.)
    let mut depth = options(classes, "claims.Effects#depth", 3, "effects-depth");
    depth.assume = Some("n >= 0 && n <= 3".into());
    depth.assert = Some("result == n".into());
    depth.decreases = Some("n".into());
    let o = run(&depth);
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let mut as_lemma = options(classes, "claims.Effects#setThenLevel", 3, "effects-depth-lemma");
    as_lemma.assert = Some("result == v".into());
    as_lemma.lemmas = Some(lemmas("depth.contract", "claims.Effects#depth\n  assume: n >= 0 && n <= 3\n  assert: result == n\n  decreases: n\n"));
    let o = run(&as_lemma);
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("reads the static field claims.Effects.level"), "{}", o.output);
}

#[test]
fn a_summary_is_not_of_a_method_that_reads_what_a_caller_can_change() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    // Each getter returns 0 from the state its lemma is proved in, and the caller writes before it calls.
    for (caller, getter, why) in [
        ("setThenLevel", "level", "reads the static field claims.Effects.level"),
        ("setThenLevelIndirectly", "levelIndirectly", "reads the static field claims.Effects.level"),
        ("setThenFirst", "first", "reads the static field claims.Effects.table"),
        ("setThenFixedFirst", "fixedFirst", "reads an array that was there before the call"),
    ] {
        let mut o = options(classes, &format!("claims.Effects#{caller}"), 3, &format!("effects-{caller}"));
        o.assert = Some("result == 0".into());
        o.lemmas = Some(lemmas(&format!("{getter}.contract"), &format!("claims.Effects#{getter}\n  assert: result == 0\n")));
        let o = run(&o);
        assert_ne!(o.verdict, Verdict::Verified, "{caller}: {}", o.output);
        assert_eq!(o.verdict, Verdict::Unverifiable, "{caller}: {}", o.output);
        let problem = o.problem.as_deref().unwrap_or_default();
        assert!(problem.contains(why) && problem.contains("which a caller can change before it calls"), "{caller}: {}", o.output);
    }

    // The lemma's own words are read again at every call the summary stands in for, in the state of that call:
    // `zero()` returns 0 and the field is 0 where the lemma is proved, so "the result is the field" holds there,
    // and after the caller's write it would make the call return what was written.
    let mut worded = options(classes, "claims.Effects#setThenZero", 3, "effects-worded");
    worded.assert = Some("result == v".into());
    worded.lemmas = Some(lemmas("zero.contract", "claims.Effects#zero\n  assert: result == claims.Effects.level()\n"));
    let o = run(&worded);
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("in its assumption or its assertion, reads the static field claims.Effects.level"), "{}", o.output);

    // The default locale is such a state too: the lemma holds where no default was set, and the caller sets one.
    let mut turkish = options(classes, "claims.Effects#turkishThenLowers", 3, "effects-turkish");
    turkish.assert = Some("result".into());
    turkish.lemmas = Some(lemmas("lowers.contract", "claims.Effects#lowersToI\n  assume: text.equals(\"I\")\n  assert: result\n"));
    let o = run(&turkish);
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("reads the default locale"), "{}", o.output);
    // Without the lemma the checker runs the call in the state the caller left, and refutes the claim.
    turkish.lemmas = None;
    turkish.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("claims").join("effects-turkish-run"));
    let o = run(&turkish);
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);

    // A final static field of a primitive is written by its class's initializer alone: a summary may read it.
    let mut limit = options(classes, "claims.Effects#twiceLimit", 3, "effects-limit");
    limit.assert = Some("result == 14".into());
    limit.lemmas = Some(lemmas("limit.contract", "claims.Effects#limit\n  assert: result == 7\n"));
    let o = run(&limit);
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    assert!(o.output.contains("lemma: ✓ claims.Effects#limit"), "{}", o.output);
}

/// A write set (`prove --writes`) on the beans of `claims.Frames`, the state stream's first effect contract: "the
/// setter writes `displayName` and nothing else". The frame is part of the assertion, so the adversarial setter's
/// write of `admin` is refuted with a witness the JVM replays; its honest twin, and a setter that puts the field
/// back, meet it. Without the write set the same check says nothing of `admin`.
#[test]
fn a_write_set_tells_the_setter_that_writes_a_protected_field_from_its_honest_twin() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let framed = |bean: &str, writes: &[&str], tag: &str| {
        let mut o = options(classes, &format!("claims.Frames${bean}#setDisplayName"), 8, &format!("frames-{tag}"));
        o.writes = Some(writes.iter().map(|w| w.to_string()).collect());
        run(&o)
    };
    let adversarial = framed("Adversarial", &["this.displayName"], "adversarial");
    assert_eq!(adversarial.verdict, Verdict::Violation, "{}", adversarial.output);
    // What was checked is the frame, conjoined to the assertion (none here).
    assert_eq!(adversarial.assert.as_deref(), Some("this.admin == \\old(this.admin)"), "{}", adversarial.output);
    assert!(adversarial.output.contains("frame: setDisplayName writes this.displayName; after the call, this.admin == \\old(this.admin)"), "{}", adversarial.output);
    assert!(adversarial.output.contains("violated: `this.admin == \\old(this.admin)`"), "{}", adversarial.output);
    assert_eq!(adversarial.replay.as_ref().map(|r| (r.by.as_str(), r.reproduced)), Some(("jvm", true)), "{}", adversarial.output);
    for bean in ["Honest", "Restoring"] {
        let o = framed(bean, &["this.displayName"], bean);
        assert_eq!(o.verdict, Verdict::Verified, "{bean}: {}", o.output);
    }
    // Named, the protected field is the setter's to write.
    let both = framed("Adversarial", &["this.displayName", "this.admin"], "adversarial-both");
    assert_eq!(both.verdict, Verdict::Verified, "{}", both.output);
    // With no write set the check states nothing about what the setter leaves.
    let mut plain = options(classes, "claims.Frames$Adversarial#setDisplayName", 8, "frames-plain");
    plain.assert = Some("true".into());
    assert_eq!(run(&plain).verdict, Verdict::Verified);
    // A reference is kept by identity: a String of the same content is another object, and a write.
    let copying = framed("Copying", &["this.displayName"], "copying");
    assert_eq!(copying.verdict, Verdict::Violation, "{}", copying.output);
    assert!(copying.output.contains("violated: `this.title == \\old(this.title)`"), "{}", copying.output);
    assert_eq!(copying.replay.as_ref().map(|r| (r.by.as_str(), r.reproduced)), Some(("jvm", true)), "{}", copying.output);
}

/// The side conditions of a write set: the harness reads the inputs' fields after the call and nothing else, so the
/// own checker refuses inside the call a write to anything else that was there before it, each by name, and a
/// write set that names no field is refused. Each setter here
/// writes what `Frames.main` shows on a JVM, so a `Verified` would be a false proof.
#[test]
fn a_write_set_refuses_every_write_its_frame_does_not_read() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let framed = |bean: &str, writes: &[&str], tag: &str| {
        let mut o = options(classes, &format!("claims.Frames${bean}#setDisplayName"), 3, &format!("frames-{tag}"));
        o.writes = Some(writes.iter().map(|w| w.to_string()).collect());
        run(&o)
    };
    for (bean, writes, why) in [
        ("Remembering", &["this.displayName"][..], "writes a static field, outside its write set"),
        ("Auditing", &["this.displayName"][..], "initializes the class claims.Frames, outside its write set"),
        ("Counting", &["this.displayName"][..], "writes a field of an object made before it was called and none of its inputs, outside its write set"),
        // The field is named, the object behind it is not.
        ("Counting", &["this.displayName", "this.audit"][..], "writes a field of an object made before it was called and none of its inputs"),
        ("Filling", &["this.displayName"][..], "stores into an array made before it was called and none of its inputs"),
    ] {
        let o = framed(bean, writes, &format!("{bean}-{}", writes.len()));
        assert_ne!(o.verdict, Verdict::Verified, "{bean}: {}", o.output);
        assert_eq!(o.verdict, Verdict::Unverifiable, "{bean}: {}", o.output);
        assert!(o.problem.as_deref().unwrap_or_default().contains(why), "{bean}: {}", o.output);
    }
    // The frame is of locations, over inputs that may be one object: `link` writes `other.admin`, which it names, and
    // its own name where `other` is itself, which a check of two distinct accounts would not see.
    let mut linking = options(classes, "claims.Frames$Linking#link", 3, "frames-linking");
    linking.writes = Some(vec!["other.admin".into()]);
    let linking = run(&linking);
    assert_eq!(linking.verdict, Verdict::Violation, "{}", linking.output);
    assert!(linking.output.contains("violated: `this.displayName == \\old(this.displayName) && (this == other || this.admin == \\old(this.admin)) && other.displayName == \\old(other.displayName)`"), "{}", linking.output);
    assert!(linking.output.contains("this and other may be the same object"), "{}", linking.output);
    assert_eq!(linking.replay.as_ref().map(|r| (r.by.as_str(), r.reproduced)), Some(("jvm", true)), "{}", linking.output);
    let unknown = framed("Honest", &["this.name"], "unknown");
    assert!(unknown.problem.as_deref().unwrap_or_default().contains("this.name is no field of the receiver or an object parameter; a write set names some of this.displayName, this.admin"), "{}", unknown.output);
}

/// What the write-set tests call writes are writes on a JVM.
#[test]
fn the_frame_countermodels_are_what_a_jvm_says_they_are() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let out = Command::new("java").arg("-cp").arg(classes).arg("claims.Frames").output().expect("java runs");
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert_eq!(
        String::from_utf8_lossy(&out.stdout).trim(),
        "adversarial.admin=true honest.admin=false restoring.admin=false copying.title.same=false copying.title.equal=true lastName=x audit.writes=1 counting.audit.same=true held.writes=1 seen[0]=1 rename.admin=true honest.rename=true lengthy.admin=true promoted.admin=true matched.admin=true sneaky.admin=true trusted.admin=true linked.name=self remapping.extras.same=false stashing.extras.size=1 mapped.rename=true peeked.rename=false"
    );
}

/// An effect contract of `bean`'s setter: it writes `displayName` and leaves it the name it is given, plus `more`.
fn effect_contract(bean: &str, more: &str) -> PathBuf {
    lemmas(&format!("effect-{bean}.contract"), &format!("claims.Frames${bean}#setDisplayName\n  writes: this.displayName\n  assert: this.displayName == name\n{more}"))
}

/// The application-level statement through an allowed field name (`claims.Frames`, the state stream's step 5): a
/// rename makes no account an admin. The honest setter's effect contract is proved and stands in for its call; the
/// adversarial setter's is refuted, so the check that would rest on it is refused, and without it the statement is
/// refuted by a rename to `admin:`, which replays.
#[test]
fn an_effect_contract_stands_in_for_the_honest_setter_and_the_adversarial_one_is_refuted() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let app = |entry: &str, assertion: &str, contract: Option<PathBuf>, tag: &str| {
        let mut o = options(classes, &format!("claims.Frames#{entry}"), 8, &format!("effects-{tag}"));
        o.assert = Some(assertion.into());
        o.lemmas = contract;
        run(&o)
    };
    let honest = app("honestRename", "result", Some(effect_contract("Honest", "")), "honest");
    assert_eq!(honest.verdict, Verdict::Verified, "{}", honest.output);
    assert!(honest.output.contains("effect: ✓ claims.Frames$Honest#setDisplayName satisfies `(this.displayName == name) && this.admin == \\old(this.admin)`, and writes this.displayName and nothing else that was there before the call"), "{}", honest.output);
    let stated = honest.stated.as_ref().expect("a statement");
    assert!(stated.assumptions.iter().any(|a| a.text == "the effect contract of claims.Frames$Honest.setDisplayName(Ljava/lang/String;)V, proved beside this check"), "the contract stood in for the call: {:?}", stated.assumptions);
    let refuted = app("adminAfterRename", "!result", Some(effect_contract("Adversarial", "")), "adversarial");
    assert_eq!(refuted.verdict, Verdict::Unverifiable, "{}", refuted.output);
    assert!(refuted.problem.as_deref().unwrap_or_default().contains("the effect contract of claims.Frames$Adversarial#setDisplayName") && refuted.output.contains("effect: ✗ Property of claims.Frames$Adversarial#setDisplayName violated"), "{}", refuted.output);
    let app_level = app("adminAfterRename", "!result", None, "adversarial-app");
    assert_eq!(app_level.verdict, Verdict::Violation, "{}", app_level.output);
    assert_eq!(app_level.replay.as_ref().map(|r| r.reproduced), Some(true), "{}", app_level.output);
    assert!(app_level.output.contains("adminAfterRename(name=\"admin:\")"), "{}", app_level.output);
    // A contract over an object parameter of a nested class (`Frames$Honest mentee`), which the stub names as javac
    // takes it, stands in for a call with an argument of exactly that class.
    let mentor = lemmas("effect-mentor.contract", "claims.Frames$Mentor#adopt\n  writes: mentee.displayName\n  assert: mentee.displayName == name\n");
    let adopted = app("adoptedRename", "result", Some(mentor), "mentor");
    assert_eq!(adopted.verdict, Verdict::Verified, "{}", adopted.output);
    let stated = adopted.stated.as_ref().expect("a statement");
    assert!(stated.assumptions.iter().any(|a| a.text.starts_with("the effect contract of claims.Frames$Mentor.adopt(")), "the contract stood in for the call: {:?}", stated.assumptions);
    // A written String field the assertion gives no parameter: the stub has no object to give it.
    let copying = lemmas("effect-copying.contract", "claims.Frames$Copying#setDisplayName\n  writes: this.displayName, this.title\n  assert: this.displayName == name\n");
    let o = app("honestRename", "result", Some(copying), "copying");
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("this.title is written and the assertion gives it no parameter's value"), "{}", o.output);
}

/// The side conditions of an effect contract's use: each setter here grants admin on a JVM (`Frames.main`), through
/// what the contract's proof did not cover: a name longer than its bound, a field of the receiver a caller set, a
/// static field, the identity of a literal, a subclass's hook. A `Verified` would be a false proof; each was one with
/// its rule switched off.
#[test]
fn an_effect_contract_is_not_used_where_the_call_is_outside_what_it_was_proved_of() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let app = |entry: &str, bean: &str, more: &str| {
        let mut o = options(classes, &format!("claims.Frames#{entry}"), 8, &format!("effects-{bean}"));
        o.assert = Some("!result".into());
        o.lemmas = Some(effect_contract(bean, more));
        run(&o)
    };
    // Proved within three units, it is used there, and a longer name runs the setter as written.
    let lengthy = app("lengthyAdminAfterRename", "Lengthy", "  arrays: 3\n");
    assert_eq!(lengthy.verdict, Verdict::Violation, "{}", lengthy.output);
    assert_eq!(lengthy.replay.as_ref().map(|r| (r.by.as_str(), r.reproduced)), Some(("jvm", true)), "{}", lengthy.output);
    // The base's setter, run on a subclass's object, calls the subclass's hook.
    let sneaky = app("sneakyAfterRename", "Base", "");
    assert_eq!(sneaky.verdict, Verdict::Violation, "{}", sneaky.output);
    assert_eq!(sneaky.replay.as_ref().map(|r| (r.by.as_str(), r.reproduced)), Some(("jvm", true)), "{}", sneaky.output);
    for (entry, bean, why) in [
        ("promotedAfterRename", "Promoting", "reads the field role of an object that was there before the call"),
        ("trustedAfterRename", "Trusting", "reads the static field claims.Frames$Switch.trusting"),
        ("matchedAfterRename", "Matching", "compares an object that was there before the call by identity"),
    ] {
        let o = app(entry, bean, "");
        assert_eq!(o.verdict, Verdict::Unverifiable, "{bean}: {}", o.output);
        let problem = o.problem.as_deref().unwrap_or_default();
        assert!(problem.contains("is not proved") && problem.contains(why) && problem.contains("it is not a method an effect contract can stand in for"), "{bean}: {}", o.output);
    }
}

/// What the two tests above call false is false on a JVM: the fixture says what each method returns there.
#[test]
fn the_countermodels_are_what_a_jvm_says_they_are() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let out = Command::new("java").arg("-cp").arg(classes).arg("claims.Effects").output().expect("java runs");
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert_eq!(
        String::from_utf8_lossy(&out.stdout).trim(),
        "counting(1)=2 throwing(1)=IllegalStateException checked(2)=2 depth(3)=3 setThenLevel(7)=7 setThenLevelIndirectly(8)=8 setThenFirst(9)=9 setThenFixedFirst(10)=10 twiceLimit()=14 lowersToI(I)=true turkishThenLowers()=false"
    );
}

/// A field of a type the check makes no object of (`java.util.Map extras` in `claims.Frames`, as example 286's
/// `ProtectedBean.someMap`): under a write set it is framed by identity, where any other check refuses it as before.
/// So a setter of such a bean has a write set and an effect contract: the honest one is proved and stands in for its
/// call, one that puts another map in the field is refuted with a witness a JVM replays, one that puts into the map
/// is refused for that write, and the contract of one that reads the map is refused for that read. Each refuted or
/// refused bean does on a JVM what `Frames.main` shows.
#[test]
fn a_write_set_frames_a_field_of_a_type_the_check_makes_no_object_of_by_identity() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let framed = |bean: &str, tag: &str| {
        let mut o = options(classes, &format!("claims.Frames${bean}#setDisplayName"), 3, &format!("frames-map-{tag}"));
        o.writes = Some(vec!["this.displayName".into()]);
        run(&o)
    };
    let mapped = framed("Mapped", "mapped");
    assert_eq!(mapped.verdict, Verdict::Verified, "{}", mapped.output);
    assert_eq!(mapped.assert.as_deref(), Some("this.admin == \\old(this.admin) && this.extras == \\old(this.extras)"), "{}", mapped.output);
    let remapping = framed("Remapping", "remapping");
    assert_eq!(remapping.verdict, Verdict::Violation, "{}", remapping.output);
    assert!(remapping.output.contains("violated: `this.extras == \\old(this.extras)`"), "{}", remapping.output);
    assert_eq!(remapping.replay.as_ref().map(|r| (r.by.as_str(), r.reproduced)), Some(("jvm", true)), "{}", remapping.output);
    let stashing = framed("Stashing", "stashing");
    assert_eq!(stashing.verdict, Verdict::Unverifiable, "{}", stashing.output);
    assert!(stashing.problem.as_deref().unwrap_or_default().contains("writes a field of an object made before it was called and none of its inputs"), "{}", stashing.output);
    // Without a write set the field is refused by name, as before.
    let mut plain = options(classes, "claims.Frames$Mapped#setDisplayName", 3, "frames-map-plain");
    plain.assert = Some("this.displayName == name".into());
    let plain = run(&plain);
    assert_eq!(plain.verdict, Verdict::Unverifiable, "{}", plain.output);
    assert!(plain.problem.as_deref().unwrap_or_default().contains("the field extras of claims.Frames$Mapped has type java.util.Map"), "{}", plain.output);
    // The effect contract at a call: proved, and named among what the result rests on.
    let app = |entry: &str, bean: &str| {
        let mut o = options(classes, &format!("claims.Frames#{entry}"), 3, &format!("effects-map-{bean}"));
        o.assert = Some("result".into());
        o.lemmas = Some(effect_contract(bean, ""));
        run(&o)
    };
    let renamed = app("mappedRename", "Mapped");
    assert_eq!(renamed.verdict, Verdict::Verified, "{}", renamed.output);
    let stated = renamed.stated.as_ref().expect("a statement");
    assert!(stated.assumptions.iter().any(|a| a.text == "the effect contract of claims.Frames$Mapped.setDisplayName(Ljava/lang/String;)V, proved beside this check"), "the contract stood in for the call: {:?}", stated.assumptions);
    // The map is a field of the receiver, which the contract's proof does not read: a caller filled it.
    let peeked = app("peekedRename", "Peeking");
    assert_eq!(peeked.verdict, Verdict::Unverifiable, "{}", peeked.output);
    assert!(peeked.problem.as_deref().unwrap_or_default().contains("the effect contract of claims.Frames$Peeking#setDisplayName"), "{}", peeked.output);
    assert!(peeked.output.contains("extras"), "the refusal names the read: {}", peeked.output);
}
