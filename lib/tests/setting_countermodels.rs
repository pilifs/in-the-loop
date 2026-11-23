//! Countermodels of an observed initializer bound to the settings it read, past the evidence stream's `mmnoqopr` and
//! `vqquvmnm` (2026-11-17). The binding states the default locale and time zone and each system property the class
//! path's code read by name, and refuses a class whose code names `System.getenv`. Each initializer here reads a
//! setting that none of that sees, so the observed state is one a JVM under other settings does not have: a property
//! read through a method reference `Optional` calls (the read's caller is a JDK frame) or as the value
//! `Properties.putIfAbsent` returns where the property is set, an environment variable through a method handle looked
//! up by name, and three settings the JDK took at startup (the processors it may use, the working directory, the
//! default charset). The fixtures are `tests/fixtures/setting-countermodels` and this test holds them to a JVM; the
//! checker's side, the proofs it should not make, is in the fixtures' README for the stream that binds an observation
//! (domain-advances-evidence).

use std::path::PathBuf;
use std::process::Command;
use std::sync::OnceLock;

fn has(tool: &str) -> bool {
    Command::new(tool).arg("-version").output().is_ok()
}

/// The fixtures, compiled: `None` without a JDK.
fn classes() -> Option<&'static PathBuf> {
    static OUT: OnceLock<Option<PathBuf>> = OnceLock::new();
    OUT.get_or_init(|| {
        if !has("javac") || !has("java") {
            return None;
        }
        let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/setting-countermodels/sc");
        let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("setting-countermodels-classes");
        let _ = std::fs::remove_dir_all(&out);
        let mut files: Vec<PathBuf> = std::fs::read_dir(&sources).unwrap().map(|e| e.unwrap().path()).filter(|p| p.extension().is_some_and(|e| e == "java")).collect();
        files.sort();
        let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "--release", "21", "-d"]).arg(&out).args(&files).status().expect("javac runs");
        assert!(status.success(), "the fixtures compile");
        Some(out)
    })
    .as_ref()
}

/// Each entry point on a JVM under the setting its class was observed with in the README, and under another: the
/// value is the setting's, so a proof of the first value holds for no JVM under the second, whatever the result
/// states of the observation.
#[test]
fn each_initializer_gives_what_its_setting_says_on_a_jvm() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let run = |entry: &str, options: &str, env: &[(&str, &str)]| {
        let mut java = Command::new("java");
        java.env_remove("JAVA_TOOL_OPTIONS").env_remove("SC_VALUE").env("JAVA_TOOL_OPTIONS", options);
        for (k, v) in env {
            java.env(k, v);
        }
        let out = java.arg("-cp").arg(classes).args(["sc.M", entry]).output().expect("java runs");
        assert!(out.status.success(), "{entry}: {}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).trim().to_string()
    };
    for (entry, observed, other) in [
        ("mapped", ("-Dsc.value=xyz", &[][..], 3), ("", &[][..], 6)),
        ("kept", ("-Dsc.value=xyz", &[][..], 3), ("", &[][..], 6)),
        ("looked", ("", &[("SC_VALUE", "xyz")][..], 3), ("", &[][..], 6)),
        ("counted", ("-XX:ActiveProcessorCount=3", &[][..], 3), ("-XX:ActiveProcessorCount=5", &[][..], 5)),
        ("rooted", ("-Duser.dir=/abc", &[][..], 4), ("-Duser.dir=/abcdef", &[][..], 7)),
        ("encoded", ("-Dfile.encoding=COMPAT", &[("LC_ALL", "C")][..], 1), ("", &[("LC_ALL", "C")][..], 2)),
    ] {
        for (options, env, expected) in [observed, other] {
            assert_eq!(run(entry, options, env), format!("{entry}={expected}"), "{entry} under {options:?} {env:?}");
        }
    }
}

fn check_refusal(entry: &str, class: &str, value: i32, options: &str, env: &[(&str, &str)], setting: &str) {
    let Some(classes) = classes() else { return };
    let mut cli = Command::new(env!("CARGO_BIN_EXE_jvmcontract"));
    cli.env_remove("SC_VALUE").env("JAVA_TOOL_OPTIONS", options);
    for (k, v) in env {
        cli.env(k, v);
    }
    let out = cli.args(["prove", &format!("sc.M#{entry}"), "--assert", &format!("result == {value}"),
                        "--observed-initializer", class, "--engine", "native", "--jbmc", "/nonexistent/jbmc", "--classes"])
        .arg(classes).arg("--classpath").arg(classes)
        .arg("--work").arg(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("setting-countermodels").join(entry))
        .output().expect("jvmcontract runs");
    let report = String::from_utf8_lossy(&out.stderr).to_string() + &String::from_utf8_lossy(&out.stdout);
    assert!(!out.status.success() && report.contains(setting) && report.contains("the observation cannot bind"), "{entry}: {report}");
}

#[test]
fn indirect_setting_reads_refuse_the_observed_initializer() {
    jvmcontract::tool_tier!();
    check_refusal("mapped", "sc.Mapped", 3, "-Dsc.value=xyz", &[], "system property through a method handle");
    check_refusal("kept", "sc.Kept", 3, "-Dsc.value=xyz", &[], "system property through a map update");
    check_refusal("looked", "sc.Looked", 3, "", &[("SC_VALUE", "xyz")], "dynamically looked-up member");
}

#[test]
fn an_empty_observer_environment_and_processor_count_are_explicit_and_independent() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return };
    let original = Command::new("java").arg("-XX:ActiveProcessorCount=3").env("SC_VALUE", "fixture-only")
        .arg("-cp").arg(classes).args(["sc.M", "process"]).output().unwrap();
    assert_eq!(String::from_utf8_lossy(&original.stdout).trim(), "process=3");
    let run = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).env("SC_VALUE", "fixture-only")
        .args(["prove", "sc.M#process", "--engine", "native", "--assert", "result == 102", "--observed-initializer", "sc.M$ProcessSettings",
            "--observed-runtime", r#"{"processors":2,"emptyEnvironment":true}"#, "--classes"]).arg(classes)
        .args(["--json", "--work"]).arg(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("setting-countermodels/empty-pinned"))
        .output().unwrap();
    assert!(run.status.success(), "{}", String::from_utf8_lossy(&run.stderr));
    let result: serde_json::Value = serde_json::from_slice(&run.stdout).unwrap();
    assert_eq!(result[0]["verdict"], "verified");
    assert!(result[0]["stated"]["assumptions"].as_array().unwrap().iter().any(|a| a["text"].as_str()
        .is_some_and(|s| s.contains("empty process environment") && s.contains("-XX:ActiveProcessorCount=2"))));
    assert!(!String::from_utf8_lossy(&run.stdout).contains("fixture-only"));
    check_refusal("process", "sc.M$ProcessSettings", 3, "-XX:ActiveProcessorCount=3", &[("SC_VALUE", "fixture-only")], "environment");
}

#[test]
fn startup_setting_reads_refuse_the_observed_initializer() {
    jvmcontract::tool_tier!();
    check_refusal("counted", "sc.Counted", 3, "", &[], "JVM resource configuration");
    check_refusal("rooted", "sc.Rooted", 4, "-Duser.dir=/abc", &[], "JVM working directory");
    check_refusal("encoded", "sc.Encoded", 1, "-Dfile.encoding=COMPAT", &[("LC_ALL", "C")], "default charset");
    let Some(classes) = classes() else { return };
    let mut ids = Vec::new();
    for count in [3, 5] {
        let flag = format!("-XX:ActiveProcessorCount={count}");
        let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).env("JAVA_TOOL_OPTIONS", &flag)
            .args(["prove", "sc.M#counted", "--assert", &format!("result == {count}"), "--observed-initializer", "sc.Counted",
                "--engine", "native", "--classes"]).arg(classes).args(["--json", "--work"])
            .arg(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("setting-countermodels").join(format!("pinned-{count}")))
            .output().unwrap();
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        let result: serde_json::Value = serde_json::from_slice(&out.stdout).unwrap();
        assert_eq!(result[0]["verdict"], "verified");
        let assumption = result[0]["stated"]["assumptions"].as_array().unwrap().iter()
            .find(|a| a["text"].as_str().unwrap_or("").contains(&flag)).expect("the statement binds the processor count");
        ids.push(assumption["id"].as_str().unwrap().to_string());
    }
    assert_ne!(ids[0], ids[1]);
}

#[test]
fn startup_witness_search_requires_a_failed_original_jvm_harness() {
    jvmcontract::tool_tier!();
    let Some(classes) = classes() else { return; };
    let run = |method: &str| {
        let result = Command::new(env!("CARGO_BIN_EXE_jvmcontract"))
            .args(["prove", &format!("sc.WitnessSettings#{method}"), "--engine", "native", "--gaps", "strict",
                   "--assert", "result", "--search-startup-witness", "--json", "--classes"])
            .arg(classes)
            .arg("--work").arg(PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("setting-countermodels").join(method))
            .env_remove("_JAVA_OPTIONS").env_remove("JAVA_TOOL_OPTIONS").env_remove("JDK_JAVA_OPTIONS")
            .output().expect("checker runs");
        let json: serde_json::Value = serde_json::from_slice(&result.stdout).expect("JSON property outcome");
        json[0].clone()
    };
    let witness = run("failsOnBoth");
    assert_eq!(witness["verdict"], "violation", "{witness}");
    assert_eq!(witness["counterexample"]["inputs"][0]["value"], 7);
    assert_eq!(witness["replay"]["by"], "jvm");
    assert_eq!(witness["replay"]["reproduced"], true);
    for method in ["failsOnlyInProposal", "holdsOnlyInProposal"] {
        let open = run(method);
        assert_eq!(open["verdict"], "unverifiable", "{method}: {open}");
        assert!(open["problem"].as_str().unwrap().contains("System.getProperty"));
    }
}
