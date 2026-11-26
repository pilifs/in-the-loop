//! The selected class binding ([`jvmcontract::classpath::ClassPath::bind`]): which exact class file stands for a
//! class name on an ordered class path and a bound runtime, and when none does.
//!
//! The fixture is the one the design review used (`llm-dlc/loops/lib-architecture-fast-follow.md`, part 2): a JAR
//! with two implementations of `fixture.Gate.marker()I`, the base returning 1 and the Java 17 entry returning 17,
//! built with a manifest of each spelling. Two JARs that differ only in how `Multi-Release`'s value is spelled load
//! different classes on a JVM, so the manifest rule is held to the JVM's, spelling by spelling.

use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::class_bindings::{answer, Request};
use jvmcontract::classpath::{multi_release, ClassPath, MultiRelease, RefusalCode, SelectedBy};

const HEAD: &str = "Manifest-Version: 1.0\r\n";

/// Every spelling measured, with what the manifest rule says of it and what a JVM of 17, 21 and 25 was seen to load
/// (Temurin 17.0.21, 21.0.13, 25.0.5; `the_manifest_rule_is_the_jvms_on_every_spelling` runs the JVM at hand).
/// `None` for the JVM where the class does not load at all.
fn spellings() -> Vec<(&'static str, String, MultiRelease, Option<u32>)> {
    use MultiRelease::*;
    let main = |rest: &str| format!("{HEAD}{rest}");
    vec![
        ("one line", main("Multi-Release: true\r\n\r\n"), Enabled, Some(17)),
        ("the value folded", main("Multi-Release: tr\r\n ue\r\n\r\n"), Ambiguous, Some(1)),
        ("the value folded, the literal in an entry section", main("Multi-Release: tr\r\n ue\r\n\r\nName: fixture/Gate.class\r\nMulti-Release: true\r\n\r\n"), Enabled, Some(17)),
        ("the literal in an entry section only", main("\r\nName: fixture/Gate.class\r\nMulti-Release: true\r\n\r\n"), Disabled, Some(1)),
        ("lower-case name, upper-case value", main("multi-release: TRUE\r\n\r\n"), Enabled, Some(17)),
        ("a space after true", main("Multi-Release: true \r\n\r\n"), Disabled, Some(1)),
        ("two spaces before true", main("Multi-Release:  true\r\n\r\n"), Disabled, Some(1)),
        ("true, then false", main("Multi-Release: true\r\nMulti-Release: false\r\n\r\n"), Disabled, Some(1)),
        ("false, then true", main("Multi-Release: false\r\nMulti-Release: true\r\n\r\n"), Enabled, Some(17)),
        ("LF line ends", "Manifest-Version: 1.0\nMulti-Release: true\n\n".to_string(), Enabled, Some(17)),
        ("the name folded", main("Multi-Rel\r\n ease: true\r\n\r\n"), Ambiguous, None),
        ("no empty line at the end", main("Multi-Release: true\r\n"), Enabled, Some(17)),
        ("no line end at all", main("Multi-Release: true"), Disabled, Some(1)),
        ("the value yes", main("Multi-Release: yes\r\n\r\n"), Disabled, Some(1)),
        ("no attribute", main("\r\n"), Disabled, Some(1)),
    ]
}

#[test]
fn the_manifest_rule_reads_each_spelling_as_measured() {
    for (name, manifest, expected, loaded) in spellings() {
        let read = multi_release(manifest.as_bytes());
        assert_eq!(read, expected, "{name}");
        // The rule and the measurement say the same: enabled is the versioned entry, disabled the base one, and
        // the spellings readers differ on are exactly those where no JVM measured loaded the versioned entry
        // though the attribute, with its lines joined, reads true.
        match read {
            MultiRelease::Enabled => assert_eq!(loaded, Some(17), "{name}"),
            MultiRelease::Disabled => assert_eq!(loaded, Some(1), "{name}"),
            MultiRelease::Ambiguous => assert_ne!(loaded, Some(17), "{name}"),
        }
    }
}

fn tmp(name: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("class-bindings").join(name);
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

/// A ZIP of stored entries, written here so that a manifest's bytes are exactly the ones given (`jar` rewrites them).
fn zip(path: &Path, entries: &[(&str, &[u8])]) {
    fn crc32(data: &[u8]) -> u32 {
        let mut crc = !0u32;
        for &byte in data {
            crc ^= byte as u32;
            for _ in 0..8 {
                crc = if crc & 1 != 0 { (crc >> 1) ^ 0xEDB8_8320 } else { crc >> 1 };
            }
        }
        !crc
    }
    let (mut out, mut central) = (Vec::new(), Vec::new());
    for (name, data) in entries {
        let offset = out.len() as u32;
        let fixed = |out: &mut Vec<u8>| {
            out.extend([20u8, 0, 0, 0, 0, 0, 0, 0, 0x21, 0x5c]); // version, flags, stored, 00:00:00, 2026-01-01
            out.extend(crc32(data).to_le_bytes());
            out.extend((data.len() as u32).to_le_bytes());
            out.extend((data.len() as u32).to_le_bytes());
            out.extend((name.len() as u16).to_le_bytes());
            out.extend(0u16.to_le_bytes());
        };
        out.extend(0x0403_4b50u32.to_le_bytes());
        fixed(&mut out);
        out.extend(name.as_bytes());
        out.extend(*data);
        central.extend(0x0201_4b50u32.to_le_bytes());
        central.extend([20u8, 0]);
        fixed(&mut central);
        central.extend([0u8; 10]); // comment length, disk, internal and external attributes
        central.extend(offset.to_le_bytes());
        central.extend(name.as_bytes());
    }
    let start = out.len() as u32;
    out.extend(&central);
    out.extend(0x0605_4b50u32.to_le_bytes());
    out.extend([0u8; 4]);
    out.extend((entries.len() as u16).to_le_bytes());
    out.extend((entries.len() as u16).to_le_bytes());
    out.extend((central.len() as u32).to_le_bytes());
    out.extend(start.to_le_bytes());
    out.extend(0u16.to_le_bytes());
    std::fs::write(path, out).unwrap();
}

fn digest(bytes: &[u8]) -> String {
    jvmcontract::digest::sha256_hex(bytes)
}

/// A JAR at `dir/NAME.jar` holding `base` as `fixture/Gate.class` and `versioned` as its Java 17 entry.
fn jar(dir: &Path, name: &str, manifest: &str, base: &[u8], versioned: &[u8]) -> PathBuf {
    let path = dir.join(format!("{name}.jar"));
    zip(&path, &[("META-INF/MANIFEST.MF", manifest.as_bytes()), ("fixture/Gate.class", base), ("META-INF/versions/17/fixture/Gate.class", versioned)]);
    path
}

const GATE: &str = "fixture/Gate";

/// A class path of `entries` as a check bound to `release` sees it, with what a JVM was seen to load for the gate.
/// The binding reads no JDK here: the release is taken as bound, as the workflow binds it after checking the JDK.
fn class_path(entries: &[&Path], release: Option<u32>, seen: Option<&str>, dir: &Path) -> ClassPath {
    let _env = ENV.lock().unwrap_or_else(|e| e.into_inner());
    std::env::remove_var("JVMCONTRACT_JAR_RELEASE");
    std::env::remove_var("JVMCONTRACT_CLASS_OBSERVATIONS");
    if let Some(seen) = seen {
        let file = dir.join("observed.json");
        std::fs::write(&file, serde_json::json!({ "feature": release, "classes": { "fixture.Gate": seen } }).to_string()).unwrap();
        std::env::set_var("JVMCONTRACT_CLASS_OBSERVATIONS", &file);
    }
    let mut cp = ClassPath::new().bound_to(release);
    std::env::remove_var("JVMCONTRACT_CLASS_OBSERVATIONS");
    for entry in entries {
        cp.add(entry).unwrap();
    }
    cp
}

/// The process's environment is one: tests that set it take turns.
static ENV: std::sync::Mutex<()> = std::sync::Mutex::new(());

#[test]
fn an_ordinary_jar_binds_its_one_class_file_whatever_is_bound() {
    let dir = tmp("ordinary");
    let path = dir.join("plain.jar");
    zip(&path, &[("META-INF/MANIFEST.MF", HEAD.as_bytes()), ("fixture/Gate.class", b"only")]);
    for release in [None, Some(8), Some(21)] {
        let cp = class_path(&[&path], release, None, &dir);
        let binding = cp.bind(GATE).unwrap();
        assert_eq!((binding.class.as_str(), binding.index, binding.selected.entry.as_str(), binding.selected.sha256.as_str()), ("fixture.Gate", 0, "fixture/Gate.class", digest(b"only").as_str()));
        assert_eq!((binding.selected_by, binding.manifest, binding.bound_release), (SelectedBy::Rule, Some(MultiRelease::Disabled), release));
        assert_eq!(binding.candidates.len(), 1);
        assert!(binding.shadowed.is_empty() && cp.refused(GATE).is_none());
        assert_eq!(cp.application_bytes(GATE).unwrap().as_deref(), Some(&b"only"[..]));
    }
    // A directory binds the file under it.
    let classes = dir.join("classes");
    std::fs::create_dir_all(classes.join("fixture")).unwrap();
    std::fs::write(classes.join("fixture/Gate.class"), b"in a directory").unwrap();
    let binding = class_path(&[&classes], Some(21), None, &dir).bind(GATE).unwrap();
    assert_eq!((binding.selected.entry.as_str(), binding.manifest, binding.selected.sha256), ("fixture/Gate.class", None, digest(b"in a directory")));
    // And a class no entry holds is refused as missing, which is not a refusal to read one that is there.
    let missing = class_path(&[&path], Some(21), None, &dir);
    assert_eq!(missing.bind("fixture/Absent").unwrap_err().code, RefusalCode::MissingClass);
    assert!(missing.refused("fixture/Absent").is_none());
}

#[test]
fn a_multi_release_jar_binds_by_the_release_and_is_refused_without_one() {
    let dir = tmp("multi-release");
    let path = jar(&dir, "plain", &format!("{HEAD}Multi-Release: true\r\n\r\n"), b"base", b"for 17");
    for (release, entry, bytes) in [(Some(8), "fixture/Gate.class", &b"base"[..]), (Some(11), "fixture/Gate.class", b"base"), (Some(17), "META-INF/versions/17/fixture/Gate.class", b"for 17"), (Some(21), "META-INF/versions/17/fixture/Gate.class", b"for 17")] {
        let cp = class_path(&[&path], release, None, &dir);
        assert_eq!(cp.jbmc_multi_release_gap().is_some(), release >= Some(17));
        let binding = cp.bind(GATE).unwrap();
        assert_eq!((binding.selected.entry.as_str(), binding.selected.sha256.as_str(), binding.selected_by), (entry, digest(bytes).as_str(), SelectedBy::Rule), "{release:?}");
        assert_eq!(binding.candidates.iter().map(|c| (c.entry.as_str(), c.release)).collect::<Vec<_>>(), [("fixture/Gate.class", None), ("META-INF/versions/17/fixture/Gate.class", Some(17))]);
        assert_eq!(cp.application_bytes(GATE).unwrap().as_deref(), Some(bytes), "the checker reads the bytes the binding names");
    }
    let unbound = class_path(&[&path], None, None, &dir);
    let refused = unbound.bind(GATE).unwrap_err();
    assert_eq!(refused.code, RefusalCode::UnboundRelease);
    assert_eq!(refused.candidates.iter().map(|c| c.sha256.clone()).collect::<Vec<_>>(), [digest(b"base"), digest(b"for 17")], "both digests, with where each is");
    assert!(unbound.refused(GATE).is_some_and(|why| why.contains("fixture.Gate is a class of a multi-release JAR") && why.contains("for Java 17")));
    assert!(unbound.application_bytes(GATE).is_err());
    assert!(unbound.jbmc_multi_release_gap().is_some());
    let earlier = dir.join("ordinary.jar");
    zip(&earlier, &[("fixture/Gate.class", b"ordinary")]);
    assert!(class_path(&[&earlier, &path], Some(21), None, &dir).jbmc_multi_release_gap().is_none());
    assert!(class_path(&[&path, &earlier], Some(21), None, &dir).jbmc_multi_release_gap().is_some());

}

#[test]
fn what_a_jvm_was_seen_to_load_must_be_the_rules_bytes() {
    let dir = tmp("observed");
    let path = jar(&dir, "plain", &format!("{HEAD}Multi-Release: true\r\n\r\n"), b"base", b"for 17");
    let agreed = class_path(&[&path], Some(21), Some(&digest(b"for 17")), &dir);
    assert_eq!(agreed.bind(GATE).unwrap().selected_by, SelectedBy::RuleAndObservation);
    assert!(agreed.refused(GATE).is_none());
    // The JVM loaded the base class where the rule selects the versioned one: neither is taken.
    let differs = class_path(&[&path], Some(21), Some(&digest(b"base")), &dir);
    let refused = differs.bind(GATE).unwrap_err();
    assert_eq!(refused.code, RefusalCode::ObservationDiffers);
    assert_eq!((refused.selected.as_ref().map(|c| c.sha256.clone()), refused.observed.clone()), (Some(digest(b"for 17")), Some(digest(b"base"))));
    assert_eq!(refused.selected.as_ref().map(|c| (c.provider.clone(), c.entry.clone())), Some((path.display().to_string(), "META-INF/versions/17/fixture/Gate.class".to_string())));
    assert!(differs.application_bytes(GATE).is_err() && differs.load(GATE).is_err());
    // An ordinary class is held to an observation as well: other bytes than its one class file are a refusal.
    let ordinary = dir.join("ordinary.jar");
    zip(&ordinary, &[("fixture/Gate.class", b"only")]);
    assert!(class_path(&[&ordinary], Some(21), Some(&digest(b"only")), &dir).refused(GATE).is_none());
    assert_eq!(class_path(&[&ordinary], Some(21), Some(&digest(b"other")), &dir).bind(GATE).unwrap_err().code, RefusalCode::ObservationDiffers);
    // An observation made on another release than the bound one says nothing here.
    let _env = ENV.lock().unwrap_or_else(|e| e.into_inner());
    let file = dir.join("observed-17.json");
    std::fs::write(&file, serde_json::json!({ "feature": 17, "classes": { "fixture.Gate": digest(b"base") } }).to_string()).unwrap();
    std::env::set_var("JVMCONTRACT_CLASS_OBSERVATIONS", &file);
    let mut other = ClassPath::new().bound_to(Some(21));
    std::env::set_var("JVMCONTRACT_CLASS_OBSERVATIONS", dir.join("absent.json"));
    let mut unreadable = ClassPath::new().bound_to(Some(21));
    std::env::remove_var("JVMCONTRACT_CLASS_OBSERVATIONS");
    other.add(&path).unwrap();
    unreadable.add(&path).unwrap();
    assert_eq!(other.bind(GATE).unwrap().selected_by, SelectedBy::Rule);
    // A file of observations that cannot be read binds nothing: every class is refused, not read without it.
    assert_eq!(unreadable.bind(GATE).unwrap_err().code, RefusalCode::Unreadable);
    assert!(unreadable.refused(GATE).is_some_and(|why| why.contains("cannot be used")));
}

#[test]
fn a_manifest_readers_differ_on_binds_only_what_a_jvm_was_seen_to_load() {
    let dir = tmp("folded");
    let path = jar(&dir, "folded", &format!("{HEAD}Multi-Release: tr\r\n ue\r\n\r\n"), b"base", b"for 17");
    let alone = class_path(&[&path], Some(21), None, &dir);
    let refused = alone.bind(GATE).unwrap_err();
    assert_eq!(refused.code, RefusalCode::AmbiguousManifest);
    assert_eq!(refused.candidates.iter().map(|c| (c.entry.clone(), c.sha256.clone())).collect::<Vec<_>>(),
        [("fixture/Gate.class".to_string(), digest(b"base")), ("META-INF/versions/17/fixture/Gate.class".to_string(), digest(b"for 17"))]);
    assert!(alone.application_bytes(GATE).is_err(), "before, the versioned entry was read here, and a JVM of 21 loads the base one");
    for (seen, entry) in [(&b"base"[..], "fixture/Gate.class"), (b"for 17", "META-INF/versions/17/fixture/Gate.class")] {
        let cp = class_path(&[&path], Some(21), Some(&digest(seen)), &dir);
        let binding = cp.bind(GATE).unwrap();
        assert_eq!((binding.selected.entry.as_str(), binding.selected_by, binding.manifest), (entry, SelectedBy::Observation, Some(MultiRelease::Ambiguous)));
        assert_eq!(cp.application_bytes(GATE).unwrap().as_deref(), Some(seen), "the bytes read are the bytes observed");
    }
    assert_eq!(class_path(&[&path], Some(21), Some(&digest(b"neither")), &dir).bind(GATE).unwrap_err().code, RefusalCode::ObservationUnmatched);
    // With no release bound an observation is of no runtime the check is bound to.
    assert_eq!(class_path(&[&path], None, None, &dir).bind(GATE).unwrap_err().code, RefusalCode::UnboundRelease);
    // A class of that JAR with no versioned entry is read as any other.
    let mixed = dir.join("mixed.jar");
    zip(&mixed, &[("META-INF/MANIFEST.MF", format!("{HEAD}Multi-Release: tr\r\n ue\r\n\r\n").as_bytes()), ("fixture/Gate.class", b"base"), ("fixture/Plain.class", b"plain"), ("META-INF/versions/17/fixture/Gate.class", b"for 17")]);
    assert_eq!(class_path(&[&mixed], Some(21), None, &dir).bind("fixture/Plain").unwrap().selected.sha256, digest(b"plain"));
}

#[test]
fn the_first_entry_that_holds_a_class_provides_it_and_the_rest_are_named_as_shadowed() {
    let dir = tmp("order");
    let (first, second) = (dir.join("first.jar"), dir.join("second.jar"));
    zip(&first, &[("fixture/Gate.class", b"one")]);
    zip(&second, &[("fixture/Gate.class", b"two")]);
    for (order, bytes, other) in [([&first, &second], &b"one"[..], &b"two"[..]), ([&second, &first], b"two", b"one")] {
        let cp = class_path(&[order[0], order[1]], Some(21), None, &dir);
        let binding = cp.bind(GATE).unwrap();
        assert_eq!((binding.index, binding.selected.provider.as_str(), binding.selected.sha256.as_str()), (0, order[0].to_str().unwrap(), digest(bytes).as_str()));
        assert_eq!(binding.shadowed.iter().map(|c| (c.provider.clone(), c.sha256.clone())).collect::<Vec<_>>(), [(order[1].display().to_string(), digest(other))]);
        assert_eq!(cp.application_bytes(GATE).unwrap().as_deref(), Some(bytes));
    }
}

fn tool(name: &str) -> bool {
    Command::new(name).arg("-version").output().is_ok_and(|o| o.status.success())
}

/// The gate compiled twice (returning 1 for Java 8 and 17 for Java 17) and a caller of it, under `dir`.
fn compiled(dir: &Path) -> (Vec<u8>, Vec<u8>, PathBuf) {
    let build = |value: u32, release: &str| {
        let (src, out) = (dir.join(format!("src-{value}/fixture")), dir.join(format!("classes-{value}")));
        std::fs::create_dir_all(&src).unwrap();
        std::fs::write(src.join("Gate.java"), format!("package fixture;\npublic class Gate {{ public static int marker() {{ return {value}; }} public static int marker(int by) {{ return {value} * by; }} }}\n")).unwrap();
        let done = Command::new("javac").args(["--release", release, "-d"]).arg(&out).arg(src.join("Gate.java")).output().unwrap();
        assert!(done.status.success(), "{}", String::from_utf8_lossy(&done.stderr));
        (std::fs::read(out.join("fixture/Gate.class")).unwrap(), out)
    };
    let ((base, classes), (versioned, _)) = (build(1, "8"), build(17, "17"));
    let probe = dir.join("probe");
    std::fs::create_dir_all(&probe).unwrap();
    std::fs::write(probe.join("Call.java"), "public class Call { public static void main(String[] a) { System.out.println(fixture.Gate.marker()); } }\n").unwrap();
    let done = Command::new("javac").args(["--release", "8", "-cp"]).arg(&classes).arg("-d").arg(&probe).arg(probe.join("Call.java")).output().unwrap();
    assert!(done.status.success(), "{}", String::from_utf8_lossy(&done.stderr));
    (base, versioned, probe)
}

/// What the JVM on the PATH returns from the gate of `jar`: an ordinary call through the application class loader.
fn jvm_marker(jar: &Path, probe: &Path) -> Option<u32> {
    let cp = std::env::join_paths([jar, probe]).unwrap();
    let run = Command::new("java").arg("-cp").arg(cp).arg("Call").output().unwrap();
    String::from_utf8_lossy(&run.stdout).trim().parse().ok().filter(|_| run.status.success())
}

/// The rule against the JVM at hand, spelling by spelling: where the rule says enabled the JVM runs the versioned
/// class, where it says disabled the base one, and where readers differ the JVM does not run the versioned one.
/// And the binding bound to that JVM's release names the class file the JVM runs, wherever it names one.
#[test]
fn the_manifest_rule_is_the_jvms_on_every_spelling() {
    jvmcontract::tool_tier!();
    if !tool("javac") || !tool("java") {
        return;
    }
    let dir = tmp("jvm");
    let (base, versioned, probe) = compiled(&dir);
    let release = String::from_utf8_lossy(&Command::new("java").arg("-XshowSettings:properties").arg("-version").output().unwrap().stderr)
        .lines().find_map(|l| l.trim().strip_prefix("java.specification.version = ").and_then(|v| v.parse::<u32>().ok())).expect("the JVM's release");
    assert!(release >= 17, "the fixture's versioned entry is for Java 17, and the JVM on the PATH is {release}");
    for (n, (name, manifest, expected, measured)) in spellings().into_iter().enumerate() {
        let path = jar(&dir, &format!("spelling-{n}"), &manifest, &base, &versioned);
        let ran = jvm_marker(&path, &probe);
        assert_eq!(ran, measured, "{name}: the JVM of {release} and the ones measured");
        let cp = class_path(&[&path], Some(release), None, &dir);
        match (expected, cp.bind(GATE)) {
            (MultiRelease::Enabled, Ok(binding)) => assert_eq!((ran, binding.selected.sha256), (Some(17), digest(&versioned)), "{name}"),
            (MultiRelease::Disabled, Ok(binding)) => assert_eq!((ran, binding.selected.sha256), (Some(1), digest(&base)), "{name}"),
            (MultiRelease::Ambiguous, Err(refused)) => {
                assert_eq!(refused.code, RefusalCode::AmbiguousManifest, "{name}");
                assert_ne!(ran, Some(17), "{name}");
            }
            (expected, other) => panic!("{name}: {expected:?}, and the binding is {:?}", other.map(|b| b.selected.entry).map_err(|r| r.code)),
        }
    }
}

/// One request answers for every side and class: the selected entry and digest, whether the bound class file
/// declares the method asked about (an overload by its descriptor, a missing one with the overloads there are), a
/// refusal as data beside the bindings, and the entries that stand for a JAR's logical names.
#[test]
fn one_request_answers_for_every_side_with_the_method_and_the_logical_entries() {
    jvmcontract::tool_tier!();
    if !tool("javac") {
        return;
    }
    let dir = tmp("request");
    let (base, versioned, _) = compiled(&dir);
    let plain = jar(&dir, "plain", &format!("{HEAD}Multi-Release: true\r\n\r\n"), &base, &versioned);
    let folded = jar(&dir, "folded", &format!("{HEAD}Multi-Release: tr\r\n ue\r\n\r\n"), &base, &versioned);
    let request: Request = serde_json::from_value(serde_json::json!({ "sides": {
        "plain": { "classpath": [plain], "listEntries": [0], "classes": [
            { "class": "fixture.Gate", "method": "marker", "descriptor": "()I" },
            { "class": "fixture.Gate", "method": "marker", "descriptor": "(I)I" },
            { "class": "fixture.Gate", "method": "marker", "descriptor": "(J)I" },
            { "class": "fixture.Gate", "method": "marker" },
            { "class": "fixture.Gate", "method": "absent" },
            { "class": "fixture.Absent" } ] },
        "folded": { "classpath": [folded], "listEntries": [0], "classes": [{ "class": "fixture/Gate", "method": "marker", "descriptor": "()I" }] },
    } })).unwrap();
    let said = {
        let _env = ENV.lock().unwrap_or_else(|e| e.into_inner());
        std::env::remove_var("JVMCONTRACT_JAR_RELEASE");
        std::env::remove_var("JVMCONTRACT_CLASS_OBSERVATIONS");
        answer(&request).unwrap()
    };
    assert_eq!(said["schema"], "jvmcontract-class-bindings/v1");
    // No release is bound in this process, so the multi-release class is refused on both sides, as data.
    let bindings = said["sides"]["plain"]["bindings"].as_array().unwrap();
    assert_eq!(bindings.len(), 6);
    assert_eq!(bindings[0]["refused"]["code"], "unbound-release");
    assert_eq!(bindings[0]["refused"]["candidates"].as_array().unwrap().iter().map(|c| c["sha256"].as_str().unwrap().to_string()).collect::<Vec<_>>(), [digest(&base), digest(&versioned)]);
    assert_eq!(bindings[5]["refused"]["code"], "missing-class");
    assert_eq!(said["sides"]["folded"]["bindings"][0]["refused"]["code"], "unbound-release");
    assert_eq!(said["sides"]["plain"]["entries"]["0"]["manifest"], "enabled");
    assert_eq!(said["sides"]["folded"]["entries"]["0"]["manifest"], "ambiguous");
    assert_eq!(said["sides"]["plain"]["entries"]["0"]["entries"]["fixture/Gate.class"], "fixture/Gate.class", "unbound, a name stands for itself");

    // An ordinary JAR of the same class answers each question about its methods.
    let ordinary = dir.join("ordinary.jar");
    zip(&ordinary, &[("fixture/Gate.class", &base)]);
    let request: Request = serde_json::from_value(serde_json::json!({ "sides": { "only": { "classpath": [ordinary], "classes": [
        { "class": "fixture.Gate", "method": "marker", "descriptor": "()I" }, { "class": "fixture.Gate", "method": "marker", "descriptor": "(J)I" },
        { "class": "fixture.Gate", "method": "marker" }, { "class": "fixture.Gate", "method": "absent" }, { "class": "fixture.Gate" } ] } } })).unwrap();
    let said = answer(&request).unwrap();
    let bindings = said["sides"]["only"]["bindings"].as_array().unwrap();
    for binding in bindings {
        assert_eq!((binding["entry"].as_str(), binding["sha256"].as_str(), binding["selected_by"].as_str()), (Some("fixture/Gate.class"), Some(digest(&base).as_str()), Some("rule")));
    }
    let overloads = serde_json::json!(["()I", "(I)I"]);
    assert_eq!(bindings[0]["method"], serde_json::json!({ "name": "marker", "descriptor": "()I", "declared": true, "access": 9, "static": true, "overloads": overloads }));
    assert_eq!((&bindings[1]["method"]["declared"], &bindings[1]["method"]["overloads"]), (&serde_json::json!(false), &overloads), "a descriptor the class does not declare");
    assert_eq!((&bindings[2]["method"]["declared"], &bindings[2]["method"]["descriptor"]), (&serde_json::json!(false), &serde_json::Value::Null), "two overloads and no descriptor: none is chosen");
    assert_eq!((&bindings[3]["method"]["declared"], &bindings[3]["method"]["overloads"]), (&serde_json::json!(false), &serde_json::json!([])));
    assert!(bindings[4].get("method").is_none());
}
