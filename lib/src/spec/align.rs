//! The alignment stream's interface (`llm-dlc/loops/foundations-alignment.md`): candidate correspondences between two
//! builds, under a preservation contract they can't weaken. Owned by that stream; until it does its part, every call
//! returns [`Unsupported`] naming it.

use std::path::Path;

use super::{Hints, Part, PreservationContract, Unsupported};

/// Candidate method correspondences and internal mappings for `contract`'s subject between the classes under
/// `before` and `after`, as proposed hints with unchecked evidence. Never a hint that changes an external input's
/// meaning or drops a required observation.
pub fn propose(contract: &PreservationContract, before: &Path, after: &Path) -> Result<Hints, Unsupported> {
    let _ = (contract, before, after);
    Err(Unsupported::new(Part::Alignment, "inferring correspondences (A2–A4)"))
}
