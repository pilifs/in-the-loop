//! The tool's part of a canonical claim (`llm-dlc/loops/foundations-summaries.md`, S2): the identities a cached result
//! rests on besides the code ([`crate::spec::ToolIdentity`]). Each is a digest of what is read, not a version
//! number, so that a rebuilt binary, another JDK build of the same release, or a changed model is a different claim.
//! An identity that can't be computed is empty, which makes the claim uncacheable ([`crate::spec::cache::key`]).
//!
//! | Part | What is digested |
//! |---|---|
//! | `binary` | the bytes of the running executable ([`std::env::current_exe`]): the checker, its models and its contract library are compiled into it |
//! | `jdk` | the JDK's whole `release` file (version, vendor, build), whose classes the own checker reads |
//! | `models` | the tool's models of JDK classes, as [`crate::statement::Models`] digests them, or `none` when unused |
//! | `checker` | the checker and every setting that can change its verdict, as the caller words them |
//!
//! The code itself is each version's closure ([`crate::closure::version_digest`]).

use std::sync::OnceLock;

use crate::digest::sha256_hex;
use crate::spec::ToolIdentity;

/// `sha256:` and the digest of the running executable's bytes; empty when it can't be read. Read once per process.
pub fn binary() -> String {
    static BINARY: OnceLock<String> = OnceLock::new();
    BINARY
        .get_or_init(|| {
            let bytes = std::env::current_exe().and_then(std::fs::read);
            bytes.map(|b| format!("sha256:{}", sha256_hex(&b))).unwrap_or_default()
        })
        .clone()
}

/// `sha256:` and the digest of the JDK's `release` file; empty when no JDK is found.
pub fn jdk() -> String {
    static JDK: OnceLock<String> = OnceLock::new();
    JDK.get_or_init(|| {
        let release = crate::jimage::JImage::find_java_home().and_then(|home| std::fs::read(home.join("release")).ok());
        release.map(|b| format!("sha256:{}", sha256_hex(&b))).unwrap_or_default()
    })
    .clone()
}

/// The models' digest when they are used, `none` otherwise.
pub fn models(used: bool) -> String {
    if used {
        crate::statement::models(true).digest.unwrap_or_default()
    } else {
        "none".into()
    }
}

/// The tool identity of a check with the models `used` or not, by the checker `checker` (its engine and every
/// setting that can change a verdict, worded by the caller).
pub fn tools(models_used: bool, checker: &str) -> ToolIdentity {
    ToolIdentity { models: models(models_used), jdk: jdk(), checker: checker.to_string(), binary: binary() }
}
