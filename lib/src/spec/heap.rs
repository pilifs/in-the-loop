//! The heap stream's interface (`llm-dlc/loops/foundations-heap.md`): a regression check over object inputs, under a
//! [`CanonicalClaim`]'s domain, observations and correspondence. Owned by that stream; until it does its part, every
//! call returns [`Unsupported`] naming it.

use std::path::Path;

use super::{CanonicalClaim, Outcome, Part, Unsupported};

/// Checks the claim of `subject` (`pkg.Class#method`) between the classes under `before` and `after`, each a class
/// directory or jar. A refuted [`Outcome`] carries a witness that replays on the JVM with the objects' identities.
pub fn check(claim: &CanonicalClaim, before: &Path, after: &Path) -> Result<Outcome, Unsupported> {
    let _ = (claim, before, after);
    Err(Unsupported::new(Part::Heap, "regression checks over object inputs (H2–H5)"))
}
