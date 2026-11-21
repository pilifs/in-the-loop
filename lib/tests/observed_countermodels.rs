//! Countermodels of an observed class initializer (`jvmcontract::observed`, `--observed-initializer`) and of a class
//! file the tool reads where a JVM reads another. The fixtures are `tests/fixtures/observed-countermodels`: `app/oc`
//! (the entry points and the classes whose initializers are observed), a library `mr.Release` built into a
//! multi-release JAR from `base/` and `versioned/` (the class file for Java 17 on), and `shadow/`, a class path copy
//! of the JDK's `org.xml.sax.helpers.AttributesImpl`. `oc.M.main` runs one entry point on a JVM, and the first test
//! holds the fixtures to what a JVM says. The checker's side of the observed initializers, the proofs it should not
//! make, is in the fixtures' README; the evidence stream bound an observation to what it was observed on
//! (`jvmcontract::observed::On`), and the test after the two class files' holds that it is. The two class files are
//! refused here (`ClassPath::refused`), and the two tests before it hold that. The last test takes the challenge
//! stream's `ob` fixtures (`tests/fixtures/rule-countermodels/ob`): writes to a supertype's static state, and a
//! property, the time zone and the environment read where the first binding did not look. The one after it takes
//! the challenge stream's binding countermodels (`tests/fixtures/binding-countermodels/bc`, from `klqnuoxw`): writes
//! into a lambda or an object another class holds, and into the JDK's default locale.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::{equivalence, property, Engine, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";

fn has(tool: &str) -> bool {
    Command::new(tool).arg("--version").output().is_ok()
}

/// The entry points' classes and the multi-release JAR, compiled: `None` without a JDK.
struct Classes {
    app: PathBuf,
    jar: PathBuf,
    shadow: PathBuf,
}

fn classes() -> Option<&'static Classes> {
    static OUT: OnceLock<Option<Classes>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") || !has("jar") {
            return None;
        }
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/observed-countermodels");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("observed-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let javac = |dir: &str, release: &str, classpath: Option<&Path>| {
            let mut c = Command::new("javac");
            c.args(["-g", "-proc:none", "-nowarn", "-Xlint:-options", "--release", release, "-d"]).arg(out.join(dir));
            if let Some(cp) = classpath {
                c.arg("-cp").arg(cp);
            }
            assert!(c.args(walk(&sources.join(dir))).status().expect("javac runs").success(), "{dir} compiles");
            out.join(dir)
        };
        let base = javac("base", "11", None);
        let versioned = javac("versioned", "17", None);
        let jar = out.join("mr.jar");
        let made = Command::new("jar").arg("--create").arg("--file").arg(&jar).arg("-C").arg(&base).arg(".").args(["--release", "17", "-C"]).arg(&versioned).arg(".").status().expect("jar runs");
        assert!(made.success(), "the multi-release JAR is made");
        let shadow = out.join("sax.jar");
        let sax = javac("shadow", "8", None);
        assert!(Command::new("jar").arg("--create").arg("--file").arg(&shadow).arg("-C").arg(&sax).arg(".").status().expect("jar runs").success(), "the copy of the JDK's class is a JAR");
        let app = javac("app", "21", Some(&jar));
        Some(Classes { app, jar, shadow })
    })
    .as_ref()
}

fn walk(dir: &Path) -> Vec<PathBuf> {
    let mut files = Vec::new();
    for entry in std::fs::read_dir(dir).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            files.extend(walk(&path));
        } else if path.extension().is_some_and(|e| e == "java") {
            files.push(path);
        }
    }
    files.sort();
    files
}

/// What `oc.M` prints for each entry point, each in a JVM of its own: in English and with no `oc.value`, then the
/// two whose initializer reads the JVM's settings once more, in Turkish and with `-Doc.value=xyz`.
#[test]
fn each_entry_point_is_what_a_jvm_says_it_is() {
    jvmcontract::tool_tier!();
    let Some(c) = classes() else { return };
    let cp = std::env::join_paths([c.app.as_path(), c.jar.as_path(), c.shadow.as_path()]).unwrap();
    let run = |settings: &[&str], m: &str| {
        let out = Command::new("java").args(settings).arg("-cp").arg(&cp).args(["oc.M", m]).output().expect("java runs");
        assert!(out.status.success(), "{m}: {}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).trim().to_string()
    };
    let english = ["-Duser.language=en", "-Duser.country=US"];
    let all: Vec<String> = ["crossed", "lowered", "configured", "released", "releasedField", "shadowed"].iter().map(|m| run(&english, m)).collect();
    assert_eq!(all.join(" "), "crossed=1 lowered=105 configured=6 released=20 releasedField=2 shadowed=0");
    assert_eq!(run(&["-Duser.language=tr", "-Duser.country=TR"], "lowered"), "lowered=305");
    assert_eq!(run(&["-Doc.value=xyz"], "configured"), "configured=3");
}

fn work(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("observed-countermodels").join(name)
}

fn proving(target: &str, assert: &str, name: &str) -> property::Options {
    let c = classes().unwrap();
    let mut o = property::Options::new(&[c.app.clone()], target);
    o.classpath = vec![c.jar.clone(), c.shadow.clone()];
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.assert = Some(assert.into());
    o.work = Some(work(name));
    o
}

#[test]
fn jointly_initialized_statics_share_one_heap_before_the_entry_runs() {
    jvmcontract::tool_tier!();
    let Some(c) = classes() else { return };
    for (entry, claim, args, expected) in [
        ("shared", "result", vec![], "true"),
        ("touchedFirst", "!result", vec!["write"], "false"),
    ] {
        let jvm = Command::new("java").arg("-cp").arg(&c.app).arg("oc.JointStartup").args(args).output().unwrap();
        assert!(jvm.status.success());
        assert_eq!(String::from_utf8_lossy(&jvm.stdout).trim(), expected);
        let mut o = proving(&format!("oc.JointStartup#{entry}"), claim, entry);
        o.observed_initializers = vec!["oc.JointStartup$Root".into()];
        o.observed_runtime.preinitialize_together = true;
        let run = property::run(&o).unwrap();
        assert_eq!(run.verdict, Verdict::Verified, "{}", run.output);
        assert!(run.stated.unwrap().assumptions.iter().any(|a| a.text.contains("before the checked entry") && a.text.contains("oc.JointStartup$Store")));
    }
}

#[test]
fn a_joint_snapshot_refuses_opaque_reads_and_preserves_explicit_root_order() {
    jvmcontract::tool_tier!();
    if classes().is_none() { return }
    let mut o = proving("oc.JointStartup#readsOpaque", "result", "joint-opaque");
    o.observed_initializers = vec!["oc.JointStartup$Root".into()];
    o.observed_runtime.preinitialize_together = true;
    let opaque = property::run(&o).unwrap();
    assert_eq!(opaque.verdict, Verdict::Unverifiable, "{}", opaque.output);
    assert!(opaque.output.contains("Store.opaque") && opaque.output.contains("StringBuilder"), "{}", opaque.output);
    let mut states = Vec::new();
    for (roots, expected) in [(["Root", "Reader"], "result == 7"), (["Reader", "Root"], "result == 0")] {
        let mut o = proving("oc.JointStartup#recorded", expected, roots[0]);
        o.observed_initializers = roots.map(|n| format!("oc.JointStartup${n}")).to_vec();
        o.observed_runtime.preinitialize_together = true;
        let run = property::run(&o).unwrap();
        assert_eq!(run.verdict, Verdict::Verified, "{}", run.output);
        let statement = run.stated.unwrap();
        let ids: Vec<_> = statement.assumptions.iter().filter_map(|a| a.id.as_deref()).filter(|id| id.starts_with("observed-initializer:")).collect();
        assert_eq!(ids.len(), 2);
        assert_eq!(ids[0].rsplit(':').next(), ids[1].rsplit(':').next());
        states.push(ids[0].rsplit(':').next().unwrap().to_owned());
    }
    assert_ne!(states[0], states[1]);
}

#[test]
fn a_root_directory_observation_binds_lexical_file_resolution() {
    jvmcontract::tool_tier!();
    if classes().is_none() { return }
    let mut o = proving("oc.JointStartup#atRoot", "result", "root-cwd");
    o.observed_initializers = vec!["oc.JointStartup$Directory".into()];
    o.observed_runtime.root_working_directory = true;
    let run = property::run(&o).unwrap();
    assert_eq!(run.verdict, Verdict::Verified, "{}", run.output);
    assert!(run.stated.unwrap().assumptions.iter().any(|a| a.text.contains("absolute-path base both at the Unix root")));
    let mut c = proving("oc.JointStartup#canonical", "result", "root-canonical");
    c.observed_initializers = vec!["oc.JointStartup$Canonical".into()];
    c.observed_runtime.root_working_directory = true;
    assert!(property::run(&c).unwrap_err().to_string().contains("getCanonicalPath"));
}

#[test]
fn an_unobserved_reference_can_cross_an_application_constructor_until_inspected() {
    jvmcontract::tool_tier!();
    let Some(c) = classes() else { return };
    let jvm = Command::new("java").arg("-cp").arg(&c.app).args(["oc.JointStartup", "carry"]).output().unwrap();
    assert!(jvm.status.success());
    assert_eq!(String::from_utf8_lossy(&jvm.stdout).trim(), "true");
    for (method, verdict) in [("carried", Verdict::Verified), ("inspectsCarried", Verdict::Unverifiable)] {
        let mut o = proving(&format!("oc.JointStartup#{method}"), "result", method);
        o.observed_initializers = vec!["oc.JointStartup$Root".into()];
        o.observed_runtime.preinitialize_together = true;
        let run = property::run(&o).unwrap();
        assert_eq!(run.verdict, verdict, "{}", run.output);
        if verdict == Verdict::Unverifiable {
            assert!(run.output.contains("Store.opaque") && run.output.contains("inspectsCarried"), "{}", run.output);
        }
    }
}

#[test]
fn weak_registry_values_survive_collection_without_assuming_membership() {
    jvmcontract::tool_tier!();
    let Some(c) = classes() else { return };
    let jvm = Command::new("java").arg("-cp").arg(&c.app).arg("oc.WeakRegistries").output().unwrap();
    assert!(jvm.status.success(), "{}", String::from_utf8_lossy(&jvm.stderr));
    let check = |method: &str, assertion: &str| {
        let mut o = proving(&format!("oc.WeakRegistries#{method}"), assertion, method);
        o.observed_initializers = vec!["oc.WeakRegistries$State".into()];
        o.observed_runtime.preinitialize_together = true;
        o.observed_runtime.weak_map_values = true;
        property::run(&o).unwrap()
    };
    let held = check("register", "result");
    if held.verdict == Verdict::Unverifiable && held.output.contains("key callbacks have not been qualified") { return; }
    assert_eq!(held.verdict, Verdict::Verified, "{}", held.output);
    assert_eq!(check("register", "!result").verdict, Verdict::Violation);
    for (method, reason) in [("membership", "null-value invariant"), ("nonNullWrite", "null-value invariant"),
        ("nonNullStartup", "no referent"), ("callback", "hashCode or equals")] {
        let run = check(method, "result");
        assert_eq!(run.verdict, Verdict::Unverifiable, "{}", run.output);
        assert!(run.output.contains(reason), "{}", run.output);
    }
}

#[test]
fn selected_startup_receivers_keep_field_owners_cycles_and_lookup_aliases() {
    jvmcontract::tool_tier!();
    let Some(c) = classes() else { return };
    let jvm = Command::new("java").arg("-cp").arg(&c.app).arg("oc.PublishedLookup").output().unwrap();
    assert!(jvm.status.success(), "{}", String::from_utf8_lossy(&jvm.stderr));
    for (method, expected) in [("reads", None), ("unknownValue", Some("uncaptured reference")),
        ("mutation", Some("read-only lookup table"))] {
        let mut o = proving(&format!("oc.PublishedLookup#{method}"), "result", method);
        o.observed_initializers = vec!["oc.PublishedLookup$Root".into()];
        o.observed_runtime.preinitialize_together = true;
        o.observed_runtime.capture_objects = ["oc.PublishedLookup$Holder", "java.util.HashMap", "java.util.concurrent.atomic.AtomicReference"]
            .into_iter().map(str::to_owned).collect();
        let result = property::run(&o).unwrap();
        if let Some(reason) = expected {
            assert_eq!(result.verdict, Verdict::Unverifiable, "{}", result.output);
            assert!(result.output.contains(reason), "{}", result.output);
        } else {
            assert_eq!(result.verdict, Verdict::Verified, "{}", result.output);
        }
    }
}

#[test]
fn observed_enum_constants_keep_their_aliases_and_both_declaring_classes_fields() {
    jvmcontract::tool_tier!();
    let Some(c) = classes() else { return };
    let jvm = Command::new("java").arg("-cp").arg(&c.app).arg("oc.ObservedModes").output().unwrap();
    assert!(jvm.status.success());
    assert_eq!(String::from_utf8_lossy(&jvm.stdout).trim(), "true true true true");

    let observed = |entry, owner: &str, work| {
        let mut o = proving(entry, "result", work);
        o.observed_initializers = vec![owner.into()];
        property::run(&o).unwrap()
    };
    let own = observed("oc.ObservedModes#matches", "oc.ObservedModes", "enum-fields");
    assert_eq!(own.verdict, Verdict::Verified, "{}", own.output);
    assert!(own.stated.unwrap().assumptions.iter().any(|a| a.text.contains("oc.mode, not set")));
    let borrowed = observed("oc.ObservedModes$Borrower#matches", "oc.ObservedModes$Borrower", "foreign-enum");
    assert_eq!(borrowed.verdict, Verdict::Unverifiable, "{}", borrowed.output);
    assert!(borrowed.output.contains("COPIED") && borrowed.output.contains("no value"), "{}", borrowed.output);

    let cp = jvmcontract::classpath::ClassPath::new().with_default_jdk();
    if cp.load("java/lang/Enum").unwrap().unwrap().class.field("hash").is_some() {
        let hash = observed("oc.ObservedModes#stableHash", "oc.ObservedModes", "enum-hash");
        assert_eq!(hash.verdict, Verdict::Unverifiable, "{}", hash.output);
        assert!(hash.output.contains("java.lang.Enum.hash"), "{}", hash.output);
    }
}

/// A class a multi-release JAR holds a class file of for Java 17 on is the one a JVM 17+ runs: `mr.Release.get()`
/// is 20 there, not the base file's 1. The tool read only the base, and so proved `released() == 1` and
/// `releasedField() == 1`, found `released() == 20` violated on a witness whose outcome was 1, and, with the class's
/// initializer observed (on the JVM, the versioned file's: `a == 2`), proved `released() == 2`, the observation of
/// one class file given to another. Now the class is refused by name wherever it is read: no verdict on any of them,
/// and a pair whose previous version has its own copy of the JAR is an error that says why.
#[test]
fn a_class_a_multi_release_jar_holds_for_its_own_release_of_java_is_refused_not_read_as_its_base() {
    jvmcontract::tool_tier!();
    let Some(c) = classes() else { return };
    for (target, assert, name) in [("oc.M#released", "result == 1", "base"), ("oc.M#released", "result == 20", "versioned"), ("oc.M#releasedField", "result == 1", "field")] {
        let o = property::run(&proving(target, assert, name)).unwrap();
        assert_eq!(o.verdict, Verdict::Unverifiable, "{name}: {}", o.output);
    }
    let mut observing = proving("oc.M#released", "result == 2", "observed");
    observing.observed_initializers = vec!["mr.Release".into()];
    match property::run(&observing) {
        Ok(o) => assert_eq!(o.verdict, Verdict::Unverifiable, "observed: {}", o.output),
        Err(e) => assert!(e.to_string().contains("mr.Release"), "observed: {e}"),
    }

    let mut pair = equivalence::Options::new(&c.app, &c.app, "oc.M#released");
    pair.engine = Engine::Native;
    pair.jbmc = NO_JBMC.into();
    pair.classpath = vec![c.jar.clone()];
    pair.before_classpath = Some(vec![c.jar.clone()]);
    pair.work = Some(work("pair"));
    let refused = equivalence::run(&pair).unwrap_err().to_string();
    assert!(refused.contains("mr.Release is a class of a multi-release JAR") && refused.contains("for Java 17"), "{refused}");

    let mut cp = jvmcontract::classpath::ClassPath::new().with_default_jdk();
    cp.add(&c.jar).unwrap();
    cp.add(&c.shadow).unwrap();
    let said = cp.load("mr/Release").map(|_| ()).unwrap_err().to_string();
    assert!(said.contains("the tool reads only the base, so the class is refused"), "{said}");
    assert!(cp.application_classes().unwrap().contains_key("mr/Release"), "the walks that ask which classes there are still see it");
    if cp.has_jdk() {
        let said = cp.load("org/xml/sax/helpers/AttributesImpl").map(|_| ()).unwrap_err().to_string();
        assert!(said.contains("in the package org.xml.sax.helpers of the JDK's module java.xml, which a JVM loads from the module"), "{said}");
    }
    if let Some(home) = jvmcontract::jimage::JImage::find_java_home() {
        let release = std::fs::read_to_string(home.join("release")).unwrap();
        let feature = release.lines().find_map(|line| line.strip_prefix("JAVA_VERSION=")).unwrap()
            .trim_matches('"').split('.').next().unwrap();
        let bound = |claim: &str, dir: &str| Command::new(env!("CARGO_BIN_EXE_jvmcontract"))
            .env("JVMCONTRACT_JAR_RELEASE", feature).env("JAVA_HOME", &home)
            .args(["prove", "oc.M#released", "--assert", claim, "--engine", "native", "--jbmc", NO_JBMC, "--classes"])
            .arg(&c.app).arg("--classpath").arg(&c.jar).arg("--work").arg(work(dir)).output().unwrap();
        let actual = bound("result == 20", "pinned-release");
        assert!(actual.status.success(), "{}", String::from_utf8_lossy(&actual.stdout));
        let base = bound("result == 1", "pinned-base-control");
        assert!(!base.status.success(), "the pinned JVM loads the Java 17 implementation");
    }
}

/// A class path copy of a class of a package of the JDK's modules (`org.xml.sax.helpers.AttributesImpl`, as
/// xml-apis carries one) is never the one a JVM runs: `shadowed()` is 0 there. The tool read the entries before the
/// JDK, and so proved `shadowed() == 42` and found `shadowed() == 0` violated on a witness whose outcome was 42. Now
/// the copy is refused by name, and the class is the JDK's to the checker, a call into it a gap as anywhere else.
#[test]
fn a_class_path_copy_of_a_class_of_the_jdks_modules_is_refused_not_read() {
    jvmcontract::tool_tier!();
    if classes().is_none() {
        return;
    }
    for (assert, name) in [("result == 42", "shadow-copy"), ("result == 0", "shadow-jdk")] {
        let o = property::run(&proving("oc.M#shadowed", assert, name)).unwrap();
        assert_eq!(o.verdict, Verdict::Unverifiable, "{name}: {}", o.output);
        assert!(o.output.contains("org.xml.sax.helpers.AttributesImpl.<init>()"), "{name}: the JDK's constructor is the gap: {}", o.output);
    }
}

/// An observation is bound to what it was observed on: an initializer that writes another class's static is
/// refused or its write carried, and one observed in a Turkish JVM, or with a property set, is refused or the result
/// says so. On a JVM in English with no `oc.value`, crossed() is 1, lowered() 105 and configured() 6. The binding
/// refuses the first two (`oc.A` left `oc.B.x` 1 where `oc.B` alone has 0; the default locale `tr-TR` is one the
/// check takes the JVM's not to be) and states the property the third read, with its value.
#[test]
fn an_observed_initializer_is_bound_to_what_it_was_observed_on() {
    jvmcontract::tool_tier!();
    let Some(c) = classes() else { return };
    let mut crossed = proving("oc.M#crossed", "result == 0", "crossed");
    crossed.observed_initializers = vec!["oc.A".into()];
    let crossed_run = property::run(&crossed);
    let crossed_proved = matches!(crossed_run, Ok(ref o) if o.verdict == Verdict::Verified);
    // The observer's JVM takes its settings from the environment; JAVA_TOOL_OPTIONS stands for a machine whose
    // default locale is Turkish, or a launcher that sets a property.
    let cli = |settings: &str, target: &str, assert: &str, class: &str, name: &str| {
        let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract"))
            .env("JAVA_TOOL_OPTIONS", settings)
            .args(["prove", target, "--assert", assert, "--observed-initializer", class, "--engine", "native", "--jbmc", NO_JBMC, "--details", "--classes"])
            .arg(&c.app)
            .arg("--classpath")
            .arg(&c.jar)
            .arg("--work")
            .arg(work(name))
            .output()
            .unwrap();
        String::from_utf8_lossy(&out.stdout).to_string() + &String::from_utf8_lossy(&out.stderr)
    };
    let lowered = cli("-Duser.language=tr -Duser.country=TR", "oc.M#lowered", "result == 305", "oc.Lowered", "lowered");
    let configured = cli("-Doc.value=xyz", "oc.M#configured", "result == 3", "oc.Configured", "configured");
    let lowered_unbound = lowered.starts_with("✓") && !lowered.contains("default locale");
    let configured_unbound = configured.starts_with("✓") && !configured.contains("oc.value");
    assert!(!crossed_proved && !lowered_unbound && !configured_unbound, "crossed proved: {crossed_proved}\nlowered: {lowered}\nconfigured: {configured}");
    // And how: each refusal names what the observation was not bound to, and the property is stated with its value.
    let crossed_said = match crossed_run {
        Ok(o) => o.output,
        Err(e) => e.to_string(),
    };
    assert!(crossed_said.contains("initialized oc.B and left it other than it is initialized alone (its field x was 1 after it and is 0 alone)"), "{crossed_said}");
    assert!(lowered.contains("default locale is tr-TR"), "{lowered}");
    assert!(configured.contains("oc.value = \"xyz\""), "{configured}");
    for (zone, expected) in [("UTC", "true"), ("Asia/Tokyo", "false")] {
        let direct = Command::new("java").arg(format!("-Duser.timezone={zone}")).args(["-Duser.language=en", "-cp"]).arg(&c.app)
            .arg("oc.CalendarAmounts").output().unwrap();
        assert!(direct.status.success(), "{}", String::from_utf8_lossy(&direct.stderr));
        assert_eq!(String::from_utf8_lossy(&direct.stdout).trim(), expected);
        let proved = cli(&format!("-Duser.timezone={zone} -Duser.language=en -Duser.country=US"), "oc.CalendarAmounts#canonical", "result", "oc.CalendarAmounts", zone);
        if zone == "UTC" {
            assert!(proved.starts_with("✓") && proved.contains("fresh lenient AD Gregorian calendars"), "{proved}");
        } else {
            assert!(proved.contains("Calendar.getInstance") && !proved.starts_with("✓"), "{proved}");
        }
    }
    let partial = cli("-Duser.timezone=UTC -Duser.language=en -Duser.country=US", "oc.CalendarAmounts#partial", "result == 0", "oc.CalendarAmounts", "utc-partial");
    assert!(partial.contains("civil fields that were not all set") && !partial.starts_with("✓"), "{partial}");
}

/// The challenge stream's `ob` fixtures (`tests/fixtures/rule-countermodels/ob`, from `lqvlvwsm`), compiled: `None`
/// without a JDK.
fn ob() -> Option<&'static Path> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/rule-countermodels/ob");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("rule-countermodels-ob-classes");
        let _ = std::fs::remove_dir_all(&out);
        let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "--release", "21", "-d"]).arg(&out).args(walk(&sources)).status().expect("javac runs");
        assert!(status.success(), "the ob fixtures compile");
        Some(out)
    })
    .as_deref()
}

/// The checker's side of the challenge stream's `ob` countermodels (`tests/fixtures/rule-countermodels/README.md`,
/// for the evidence stream, `lzpqszyo`): an observation is bound to what it was observed on. An initializer that
/// wrote a supertype's static or a superinterface's array is refused or its write carried; one that read a property
/// through the `Properties` map, the default time zone or the environment is refused or the result says so. A JVM in
/// UTC with neither setting gives inherited() 1, filled() 5, bypassed() 6, zoned() 0, environ() 6 (the challenge
/// stream's `rule_countermodels.rs` holds the fixtures to that).
#[test]
fn an_observation_is_bound_to_its_writes_outside_the_class_and_to_every_setting_it_read() {
    jvmcontract::tool_tier!();
    let Some(classes) = ob() else { return };
    let work = |name: &str| PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("rule-countermodels").join(name);
    let mut wrong = Vec::new();
    let mut said = Vec::new();
    for (entry, class, assertion) in [("inherited", "ob.Derived", "result == 0"), ("filled", "ob.Filled", "result == 0")] {
        let mut o = property::Options::new(&[classes.to_path_buf()], &format!("ob.M#{entry}"));
        o.engine = Engine::Native;
        o.jbmc = NO_JBMC.into();
        o.assert = Some(assertion.into());
        o.observed_initializers = vec![class.into()];
        o.work = Some(work(entry));
        let run = property::run(&o);
        eprintln!("--- {entry}: {run:?}");
        if matches!(run, Ok(ref out) if out.verdict == Verdict::Verified) {
            wrong.push(entry.to_string());
        }
        said.push(match run {
            Ok(out) => out.output,
            Err(e) => e.to_string(),
        });
    }
    // The observer's JVM takes its settings from the environment: JAVA_TOOL_OPTIONS and OB_VALUE stand for a machine
    // or a launcher that sets them.
    let mut said_by_cli = Vec::new();
    for (entry, class, assertion, env, said) in [
        ("bypassed", "ob.Bypassed", "result == 3", ("JAVA_TOOL_OPTIONS", "-Dob.value=xyz"), "ob.value"),
        ("zoned", "ob.Zoned", "result == 9", ("JAVA_TOOL_OPTIONS", "-Duser.timezone=Asia/Tokyo"), "Asia/Tokyo"),
        ("environ", "ob.Environ", "result == 3", ("OB_VALUE", "xyz"), "OB_VALUE"),
    ] {
        let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract"))
            .env_remove("JAVA_TOOL_OPTIONS")
            .env_remove("OB_VALUE")
            .env(env.0, env.1)
            .args(["prove", &format!("ob.M#{entry}"), "--assert", assertion, "--observed-initializer", class, "--engine", "native", "--jbmc", NO_JBMC, "--details", "--classes"])
            .arg(classes)
            .arg("--classpath")
            .arg(classes)
            .arg("--work")
            .arg(work(entry))
            .output()
            .unwrap();
        let text = String::from_utf8_lossy(&out.stdout).to_string() + &String::from_utf8_lossy(&out.stderr);
        eprintln!("--- {entry}:\n{text}");
        if text.starts_with("✓") && !text.contains(said) {
            wrong.push(entry.to_string());
        }
        said_by_cli.push(text);
    }
    assert!(wrong.is_empty(), "proved from an observation that does not say what it rests on: {wrong:?}");
    // And how: the two writes are refused with the supertype's field, the map's read and the time zone are stated,
    // and the environment's read is refused by the call.
    assert!(said[0].contains("initialized ob.Base and left it other than it is initialized alone (its field x was 1 after it and is 0 alone)"), "{}", said[0]);
    assert!(said[1].contains("initialized ob.Table and left it other than it is initialized alone (an object its fields hold)"), "{}", said[1]);
    assert!(said_by_cli[0].starts_with("✓") && said_by_cli[0].contains("it read the system properties ob.value = \"xyz\""), "{}", said_by_cli[0]);
    assert!(said_by_cli[1].starts_with("✓") && said_by_cli[1].contains("default time zone Asia/Tokyo"), "{}", said_by_cli[1]);
    assert!(said_by_cli[2].contains("--observed-initializer ob.Environ: its code reads the environment (java.lang.System.getenv)"), "{}", said_by_cli[2]);
}

/// An initializer that writes beside its own class: into a lambda or an object another class holds, or the JDK's
/// default locale. Each is refused, or the write carried. On a JVM rehooked() is 5, boxed() 5 and relocaled() 305
/// (tests/binding_countermodels.rs). The challenge stream's test (`tests/fixtures/binding-countermodels/README.md`),
/// with how each is refused: Hooks' lambda and Boxes' Box by their descriptions, the locale by the setting.
#[test]
fn an_initializer_that_writes_beside_its_own_class_is_refused_or_carried() {
    jvmcontract::tool_tier!();
    if !has("javac") || !has("java") {
        return;
    }
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/binding-countermodels/bc");
    let classes = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("binding-countermodels-checked");
    let _ = std::fs::remove_dir_all(&classes);
    let sources: Vec<PathBuf> = std::fs::read_dir(&dir).unwrap().map(|e| e.unwrap().path()).filter(|p| p.extension().is_some_and(|e| e == "java")).collect();
    assert!(Command::new("javac").args(["-g", "-proc:none", "-nowarn", "--release", "21", "-d"]).arg(&classes).args(&sources).status().unwrap().success());
    let mut said = Vec::new();
    for (entry, assert, class) in [("bc.M#rehooked", "result == 1", "bc.Rehooked"), ("bc.M#boxed", "result == 0", "bc.Boxed"), ("bc.M#relocaled", "result == 105", "bc.Relocaled")] {
        let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract"))
            .env("JAVA_TOOL_OPTIONS", "-Duser.language=en -Duser.country=US")
            .args(["prove", entry, "--assert", assert, "--observed-initializer", class, "--engine", "native", "--jbmc", NO_JBMC, "--classes"])
            .arg(&classes)
            .arg("--work")
            .arg(work(class))
            .output()
            .unwrap();
        let stdout = String::from_utf8_lossy(&out.stdout);
        assert!(!stdout.starts_with("✓"), "{entry}: proved where a JVM says otherwise\n{stdout}");
        said.push(stdout.to_string() + &String::from_utf8_lossy(&out.stderr));
    }
    assert!(said[0].contains("initialized bc.Hooks and left it other than it is initialized alone (its field hook was an object of bc.Hooks$$Lambda (bc.Hooks$$Lambda calling bc/Hooks.lambda$install$"), "{}", said[0]);
    assert!(said[1].contains("initialized bc.Boxes and left it other than it is initialized alone (its field BOX was an object of bc.Box (bc.Box{value=Integer 5}) after it and is an object of bc.Box (bc.Box{value=Integer 0}) alone)"), "{}", said[1]);
    assert!(said[2].contains("its initialization changed the JDK's settings (the default locale, from en-US to tr;"), "{}", said[2]);
}
