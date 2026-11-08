//! A value parameter of a regression check (Phase 5 step 1 of `llm-dlc/loops/application-core.md`, the values
//! stream's interface request for V1): a String crosses the whole proof boundary. The own checker makes it of at
//! most the stated bound's code units, the witness is read and rebuilt by the values adapter's rules, replayed in
//! the interpreter and on a JVM, the statement states the bound and the model, and the cache keys both.
//!
//! Each capability's four things: a correct case and a planted defect (the frozen `Codes#vip` of the quote
//! fixture), a named unsupported boundary (JBMC, a property's String, a String result), and cached evidence that
//! moves with the bound.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::equivalence::{self, Confirmed};
use jvmcontract::spec::cache::Reuse;
use jvmcontract::statement::ParameterKind;
use jvmcontract::{property, values, Engine, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";

fn tmp(name: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("value-parameters").join(name);
    let _ = std::fs::remove_dir_all(&dir);
    dir
}

fn javac(out: &Path, files: &[PathBuf]) {
    let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(out).args(files).status().expect("the test needs javac");
    assert!(status.success(), "{} compiles", out.display());
}

/// The quote fixture's `Codes`, as `before`, `after` and the `wrong-prefix` defect build it.
fn codes(build: &str) -> PathBuf {
    static ROOT: OnceLock<PathBuf> = OnceLock::new();
    let root = ROOT.get_or_init(|| {
        let root = tmp("codes");
        let quote = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/application-core/quote");
        for (name, source) in [("before", "before"), ("after", "after"), ("wrong-prefix", "defects/wrong-prefix")] {
            javac(&root.join(name), &[quote.join(source).join("quotes/Codes.java")]);
        }
        root
    });
    root.join(build)
}

/// Two versions of a small class of String methods, `before` and `after`.
fn strings() -> &'static Path {
    static ROOT: OnceLock<PathBuf> = OnceLock::new();
    ROOT.get_or_init(|| {
        let root = tmp("strings");
        for (name, lone) in [("before", "false"), ("after", "s.length() == 1 && s.charAt(0) == '\\uDBFF'")] {
            let source = root.join("src").join(name).join("s/Text.java");
            std::fs::create_dir_all(source.parent().unwrap()).unwrap();
            std::fs::write(&source, format!("package s;\npublic final class Text {{\n    public static boolean lone(String s) {{ return {lone}; }}\n    public static String echo(String s) {{ return s; }}\n    public static int size(String s) {{ return s.length(); }}\n}}\n")).unwrap();
            javac(&root.join(name), &[source]);
        }
        root
    })
}

fn options(before: &Path, after: &Path, target: &str, work: &str) -> equivalence::Options {
    let mut o = equivalence::Options::new(before, after, target);
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.work = Some(tmp(work));
    o
}

/// The rewrite of `Codes#vip` with `length` and `charAt` is proved over every String of at most 8 code units, and
/// the shorter prefix is refuted on a witness that depends on content, replayed in the interpreter and on a JVM,
/// and typed in the shared witness form. The statement states the value domain, its bound and the String model.
#[test]
fn a_string_parameter_is_proved_and_its_defect_refuted_on_a_witness_replayed_on_a_jvm() {
    let proved = equivalence::run(&options(&codes("before"), &codes("after"), "quotes.Codes#vip", "vip-after")).unwrap();
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);
    assert!(proved.output.contains("code: String of ≤ 8 code units, not null"), "{}", proved.output);
    let stated = proved.stated.as_ref().expect("a statement");
    let code = &stated.domain.parameters[0];
    assert_eq!((code.kind, code.max_length, code.null), (ParameterKind::Value, Some(8), false));
    assert_eq!(stated.bounds.max_value_length, Some(8));
    assert_eq!(stated.models.values, vec![values::string_model()]);

    let refuted = equivalence::run(&options(&codes("before"), &codes("wrong-prefix"), "quotes.Codes#vip", "vip-wrong-prefix")).unwrap();
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    assert!(refuted.replay.as_ref().is_some_and(|r| r.reproduced), "{}", refuted.output);
    let c = refuted.counterexample.as_ref().expect("a witness");
    assert_eq!(c.jvm.as_deref(), Some(jvm_release().as_str()), "run on a JVM: {}", refuted.output);
    let value = c.inputs[0].value.clone().expect("the String's value");
    let witness: jvmcontract::spec::plans::WitnessValue = serde_json::from_value(value).expect("the shared witness form");
    let jvmcontract::spec::plans::WitnessValue::String { units } = witness else { panic!("a String: {c:?}") };
    // `before` wants "VIP", the defect only "VI": a witness starts with "VI" and isn't "VIP…".
    assert!(units.starts_with(&[86, 73]) && units.get(2) != Some(&80), "{units:?}");
    assert!(c.input.starts_with("vip(code=\"VI"), "{}", c.input);
}

fn jvm_release() -> String {
    let out = Command::new("java").arg("-XshowSettings:properties").arg("-version").output().expect("java runs");
    let text = String::from_utf8_lossy(&out.stderr).into_owned();
    text.lines().find_map(|l| l.trim().strip_prefix("java.version = ").map(str::to_string)).expect("java.version")
}

/// A witness's code units cross to the JVM and back as they are: a lone high surrogate, which no well-formed text
/// holds, is the witness `after`'s new branch needs, rendered by its escape, and the JVM's harness fails on it too.
#[test]
fn a_witness_with_an_isolated_surrogate_replays_on_the_jvm_unit_for_unit() {
    let root = strings();
    let o = equivalence::run(&options(&root.join("before"), &root.join("after"), "s.Text#lone", "lone")).unwrap();
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.jvm.is_some(), "run on a JVM: {}", o.output);
    let value = c.inputs[0].value.clone().unwrap();
    let units: Vec<u16> = serde_json::from_value(value["units"].clone()).unwrap();
    assert_eq!(units, vec![0xdbff]);
    assert_eq!(c.input, "lone(s=\"\\udbff\")");
}

/// What the wiring leaves out is refused by name, never decided otherwise: JBMC, whose Strings are its own model
/// (`--engine jbmc` refused, and under `--confirm` not asked); a property over a String, whose expressions can't
/// read one; and a String result, which the harness compares with `Objects.equals`, a gap the own checker refuses.
#[test]
fn a_string_parameter_is_the_own_checkers_alone_and_what_is_left_out_is_named() {
    let mut jbmc = options(&codes("before"), &codes("after"), "quotes.Codes#vip", "vip-jbmc");
    jbmc.engine = Engine::Jbmc;
    let o = equivalence::run(&jbmc).unwrap();
    assert_eq!(o.verdict, Verdict::Unverifiable);
    assert!(o.problem.as_deref().unwrap_or_default().contains("JBMC's Strings are its own model"), "{}", o.output);

    let mut confirm = options(&codes("before"), &codes("after"), "quotes.Codes#vip", "vip-confirm");
    confirm.engine = Engine::Auto;
    confirm.confirm = true;
    let o = equivalence::run(&confirm).unwrap();
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let c = o.search.as_ref().and_then(|s| s.confirmation.as_ref()).expect("a confirmation record");
    assert_eq!(c.status, Confirmed::NotAsked, "{c:?}");
    assert!(c.reason.as_deref().unwrap_or_default().contains("a String parameter"), "{c:?}");

    let mut p = property::Options::new(&[codes("after")], "quotes.Codes#vip");
    p.engine = Engine::Native;
    p.jbmc = NO_JBMC.into();
    p.work = Some(tmp("vip-property"));
    let o = property::run(&p).unwrap();
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("java.lang.String"), "{}", o.output);

    let root = strings();
    let mut echo = options(&root.join("before"), &root.join("after"), "s.Text#echo", "echo");
    echo.shared_callees = false;
    let o = equivalence::run(&echo).unwrap();
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("java.util.Objects.equals"), "{}", o.output);
}

/// A String claim's cached evidence: an exact rerun reuses the proof, and the same claim under another bound is
/// another key, proved again.
#[test]
fn a_string_parameters_cached_evidence_moves_with_its_bound() {
    let root = strings();
    let cache = tmp("cache");
    let run = |bound: u32, work: &str| {
        let mut o = options(&root.join("before"), &root.join("after"), "s.Text#size", work);
        o.shared_callees = false;
        o.cache = Some(cache.clone());
        o.max_array_length = bound;
        equivalence::run(&o).unwrap()
    };
    let key = |o: &equivalence::Outcome| match &o.reuse {
        Some(Reuse::Exact { key, .. }) => Some(key.clone()),
        _ => None,
    };
    let cold = run(8, "size-cold");
    assert_eq!(cold.verdict, Verdict::Verified, "{}", cold.output);
    assert!(key(&cold).is_none(), "{}", cold.output);
    let rerun = run(8, "size-rerun");
    assert_eq!(rerun.verdict, Verdict::Verified);
    let hit = key(&rerun).unwrap_or_else(|| panic!("an exact hit: {}", rerun.output));
    let narrower = run(5, "size-narrower");
    assert_eq!(narrower.verdict, Verdict::Verified);
    assert!(key(&narrower).is_none(), "another bound is another claim: {}", narrower.output);
    assert_eq!(key(&run(5, "size-narrower-rerun")).is_some_and(|k| k != hit), true, "and has a key of its own");
}
