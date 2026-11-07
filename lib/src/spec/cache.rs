//! The summaries stream's interface (`llm-dlc/loops/foundations-summaries.md`): the claim key, and the proof cache
//! keyed by it. Owned by that stream; until it does its part, every call returns [`Unsupported`] naming it.

use std::path::Path;

use serde::{Deserialize, Serialize};

use super::{CanonicalClaim, Outcome, Part, Unsupported};

/// The digest of a [`CanonicalClaim`]: equal exactly when every part that decides the result is equal.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct ClaimKey(pub String);

/// A stored result: its claim's key, the outcome, and where it came from.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ResultRecord {
    pub key: ClaimKey,
    pub outcome: Outcome,
    /// The run that produced it: commit, configuration and time.
    pub provenance: String,
}

/// How a result was reused, when it was.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind")]
pub enum Reuse {
    /// The same claim key: the stored result is the result.
    Exact { from: String },
    /// A callee's proved equivalence used as a shared stub, with that proof's key.
    Callee { callee: String, key: ClaimKey },
}

/// The key of a prepared claim. A part the projection doesn't know makes the claim uncacheable (an error), never a
/// key that leaves it out.
pub fn key(claim: &CanonicalClaim) -> Result<ClaimKey, Unsupported> {
    let _ = claim;
    Err(Unsupported::new(Part::Summaries, "claim keys (S1–S2)"))
}

/// The stored result for a key, in the cache directory `dir`; none on a miss.
pub fn lookup(dir: &Path, key: &ClaimKey) -> Result<Option<ResultRecord>, Unsupported> {
    let _ = (dir, key);
    Err(Unsupported::new(Part::Summaries, "the proof cache (S2)"))
}

/// Stores a verified or refuted result; an unresolved one is never stored.
pub fn store(dir: &Path, record: &ResultRecord) -> Result<(), Unsupported> {
    let _ = (dir, record);
    Err(Unsupported::new(Part::Summaries, "the proof cache (S2)"))
}

/// The callee evidence a check of `subject` (`pkg.Class#method`) between the classes under `before` and `after` reuses:
/// pure helpers whose own equivalence proof is in the cache under `dir`, shared in both versions (S4).
pub fn callee_reuse(dir: &Path, subject: &str, before: &Path, after: &Path) -> Result<Vec<Reuse>, Unsupported> {
    let _ = (dir, subject, before, after);
    Err(Unsupported::new(Part::Summaries, "shared helpers proved equivalent (S4)"))
}
