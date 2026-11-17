//! Stand-ins for library methods, sampled on a JVM (`prove --stand-in`, `src/stand_in.rs`). The fixture
//! (`tests/fixtures/stand-ins/si`) has a reflective property writer, `Wrapper.set`, which the own checker does not
//! run, and a stand-in that writes the lookup out for one bean. Each test holds one rule: a stand-in the samples bear
//! out decides what it covers and says so, a refutation through it replays on a JVM, a receiver of a subclass or a
//! bean it hands back runs the method as written, and a stand-in the samples contradict, or that samples nothing, or
//! that has a public method standing in for nothing, is refused before the run.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::{property, Engine, Verdict};

fn has(tool: &str) -> bool {
    Command::new(tool).arg("-version").output().is_ok()
}

/// The fixture, compiled: `None` without a JDK.
fn classes() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/stand-ins/si");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("stand-in-classes");
        let _ = std::fs::remove_dir_all(&out);
        let files: Vec<PathBuf> = std::fs::read_dir(&sources).unwrap().map(|e| e.unwrap().path()).filter(|p| p.extension().is_some_and(|e| e == "java")).collect();
        let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(&out).args(files).status().expect("javac runs");
        assert!(status.success(), "the fixture compiles");
        Some(out)
    })
    .as_deref()
}

/// A check of `si.Use#entry` under strict gaps, with the stand-ins given.
fn check(classes: &Path, entry: &str, assume: Option<&str>, stand_ins: &[&str], work: &str) -> Result<property::Outcome, jvmcontract::Error> {
    let mut o = property::Options::new(&[classes.to_path_buf()], &format!("si.Use#{entry}"));
    o.engine = Engine::Native;
    o.jbmc = "/nonexistent/jbmc".into();
    o.assert = Some("result == 0".into());
    o.assume = assume.map(String::from);
    o.stand_ins = stand_ins.iter().map(|s| s.to_string()).collect();
    o.work = Some(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("stand-ins").join(work));
    property::run(&o)
}

/// What a result says it rests on.
fn rests_on(out: &property::Outcome) -> Vec<String> {
    out.stated.as_ref().map(|s| s.assumptions.iter().map(|a| a.text.clone()).collect()).unwrap_or_default()
}

/// The stand-in decides what the method alone leaves undecided, and the result names it, sampled and not proved; a
/// refutation through it is a witness a JVM replays on the method as written.
#[test]
fn a_stand_in_decides_what_its_samples_bear_out_and_says_so() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let without = check(classes, "ageAfter", Some("name.length() != 3"), &[], "without").unwrap();
    assert_eq!(without.verdict, Verdict::Unverifiable, "{}", without.output);
    let proved = check(classes, "ageAfter", Some("name.length() != 3"), &["si.WrapperStandIn"], "proved").unwrap();
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);
    let named = rests_on(&proved);
    assert!(named.iter().any(|a| a.contains("si.WrapperStandIn.set stands in for si.Wrapper.set") && a.contains("288 samples") && a.contains("not proved")), "{named:?}");
    let refuted = check(classes, "ageAfter", None, &["si.WrapperStandIn"], "refuted").unwrap();
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    assert!(refuted.output.contains("run on a JVM"), "the witness is replayed: {}", refuted.output);
}

/// A receiver of a subclass is not one the stand-in covers, and a bean it does not cover is handed back to the
/// method: both run the method as written, and stop at its gap as without the stand-in.
#[test]
fn a_stand_in_covers_only_a_receiver_of_exactly_its_class_and_what_it_does_not_hand_back() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    for entry in ["ageAfterLoud", "otherAfter"] {
        let out = check(classes, entry, Some("name.length() != 3"), &["si.WrapperStandIn"], entry).unwrap();
        assert_eq!(out.verdict, Verdict::Unverifiable, "{entry}: {}", out.output);
        assert!(out.output.contains("si.Wrapper.set"), "{entry} stops in the method as written: {}", out.output);
    }
}

/// A stand-in is refused before the run where its samples show it differs from the method (it forgets that "Age"
/// writes age), where its sampler samples nothing, and where a public static method of it stands in for nothing.
#[test]
fn a_stand_in_its_samples_do_not_bear_out_is_refused() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    for (stand_in, said) in [
        ("si.WrongStandIn", "on name=Age value=32 the method gives threw=none age=32"),
        ("si.SilentStandIn", "printed no sample"),
        ("si.HelperStandIn", "twice(Lsi/Bean;I)I stands in for no method"),
    ] {
        let error = check(classes, "ageAfter", None, &[stand_in], stand_in).err().unwrap_or_else(|| panic!("{stand_in} is taken"));
        assert!(error.to_string().contains(said), "{stand_in}: {error}");
    }
}
