//! A claim's expressions compiled by javac, where the tool's own expression compiler doesn't take them.
//!
//! The harness's expressions are Java, and [`crate::harness::expr`] compiles the part of Java it has: arithmetic,
//! arrays, field paths, an interface's accessors. An expression with a lambda, a stream or a call into a library
//! (`java.util.Arrays.stream(patterns).anyMatch(p -> p.equals(field))`) is still Java: it is written into a class
//! of one static boolean method per expression ([`crate::harness::expr::claim_source`]), over the names the
//! expression may read, and javac compiles it against the check's class path. The harness calls that method where
//! it would have evaluated the expression, and the checker runs it as the bytecode it is, like the target's: what
//! it can't run is a gap or a refusal there, by name. Nothing about the expression is the tool's reading of it.
//!
//! The class also holds what a proof by induction or a checked summary adds ([`crate::summary`]): Java the tool
//! writes, compiled with the expressions.

use std::path::{Path, PathBuf};

use crate::harness::expr::{claim_source, CLAIM_CLASS};
use crate::harness::Param;

/// Writes [`CLAIM_CLASS`] with `methods` (each a name, the names it may read and its expression) and `members`
/// (further members, as Java: [`crate::summary`]'s) into `dir` and compiles it there against `classpath`.
/// Returns the compiler's version (`javac 25.0.5`); the error is javac's own diagnostic, or why it did not run.
pub fn compile(dir: &Path, classpath: &[PathBuf], methods: &[(&str, &[Param], &str)], members: &str, java_home: Option<&Path>) -> Result<String, String> {
    let home = match java_home {
        Some(h) => h.to_path_buf(),
        None => crate::jimage::JImage::find_java_home().ok_or("no JDK to compile it with (set JAVA_HOME)")?,
    };
    let javac = home.join("bin").join("javac");
    std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    let source = dir.join(format!("{CLAIM_CLASS}.java"));
    std::fs::write(&source, claim_source(methods, members)).map_err(|e| e.to_string())?;
    let mut sources = vec![source];
    // The members call the checker's intrinsics, which javac needs a class of; the checker answers the calls
    // itself, so the class is compiled beside the claim and not kept.
    let intrinsics = dir.join("intrinsics");
    if !members.is_empty() {
        let package = intrinsics.join("jvmcontract");
        std::fs::create_dir_all(&package).map_err(|e| e.to_string())?;
        std::fs::write(package.join("GapIntrinsics.java"), crate::summary::INTRINSICS_SOURCE).map_err(|e| e.to_string())?;
        sources.push(package.join("GapIntrinsics.java"));
    }
    let cp = std::env::join_paths(classpath.iter()).map_err(|e| e.to_string())?;
    let run = std::process::Command::new(&javac).args(["-proc:none", "-Xlint:none", "-nowarn", "-g", "-cp"]).arg(&cp).arg("-d").arg(dir).args(&sources).output().map_err(|e| format!("{}: {e}", javac.display()))?;
    let _ = std::fs::remove_dir_all(&intrinsics);
    let _ = std::fs::remove_dir_all(dir.join("jvmcontract"));
    if !run.status.success() {
        let said = String::from_utf8_lossy(&run.stderr);
        // javac's first diagnostic, without the generated file's path.
        let first = said.lines().find(|l| l.contains("error:")).map(|l| l.split("error:").nth(1).unwrap_or(l).trim().to_string()).unwrap_or_else(|| said.trim().to_string());
        return Err(first);
    }
    let version = std::process::Command::new(&javac).arg("-version").output().ok().map(|o| format!("{}{}", String::from_utf8_lossy(&o.stdout), String::from_utf8_lossy(&o.stderr)).trim().to_string()).filter(|v| !v.is_empty()).unwrap_or_else(|| "javac".into());
    Ok(version)
}
