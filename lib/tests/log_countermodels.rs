//! Countermodels of logging a record "confined to itself", past the preservation stream's `lqkwokqq` (2026-11-17),
//! which refuses an `athrow` in the record's classes because the default handler's `catch (Exception)` lets anything
//! else out of `log`. A JVM raises an `Error` with no `athrow`: an array no JVM makes (`Huge`) and a recursion without
//! end (`Deep`), each in the record's `getMessage()`. The fixtures are `tests/fixtures/log-countermodels/lh`; this
//! test holds them to what a JVM says, and the checker's side is in the fixtures' README for the preservation stream.

use std::path::PathBuf;
use std::process::Command;

fn has(tool: &str) -> bool {
    Command::new(tool).arg("-version").output().is_ok()
}

/// On a JVM, `log` does not return for either record: the caller's `catch (Throwable)` gives 0.
#[test]
fn each_records_error_leaves_log_on_a_jvm() {
    jvmcontract::tool_tier!();
    if !has("javac") || !has("java") {
        return;
    }
    let sources = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/log-countermodels/lh");
    let out = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("log-countermodels-classes");
    let _ = std::fs::remove_dir_all(&out);
    let mut files: Vec<PathBuf> = std::fs::read_dir(&sources).unwrap().map(|e| e.unwrap().path()).collect();
    files.sort();
    let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "--release", "21", "-d"]).arg(&out).args(&files).status().expect("javac runs");
    assert!(status.success(), "the fixture compiles");
    let o = Command::new("java").env_remove("JAVA_TOOL_OPTIONS").args(["-Xmx64m", "-Xss512k", "-cp"]).arg(&out).arg("lh.M").output().expect("java runs");
    assert!(o.status.success(), "{}", String::from_utf8_lossy(&o.stderr));
    assert_eq!(String::from_utf8_lossy(&o.stdout).trim(), "huge=0 deep=0");
}
