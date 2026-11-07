//! The alignment stream's interface (`llm-dlc/loops/foundations-alignment.md`): candidate correspondences between two
//! builds, under a preservation contract they can't weaken.

use std::path::Path;

use super::{Hints, Part, PreservationContract, Unsupported};
use crate::alignment::{self, Build};

/// Candidate method correspondences and internal mappings for `contract`'s subject between the classes under
/// `before` and `after`, as proposed hints with unchecked evidence. Never a hint that changes an external input's
/// meaning or drops a required observation.
///
/// Methods (A2), argument, record and result mappings (A3) and field correspondence (A4) are inferred by
/// [`alignment::align`]; every other method pair it matches is mapped under the contract its signatures imply. The
/// subject's own mapping must be complete: where it isn't (a class whose fields can't all be related, an input with
/// no candidate), the gap is returned as [`Unsupported`], naming it, rather than proposals without the relation the
/// subject needs. An unchanged subject needs no mapping, and gets none.
pub fn propose(contract: &PreservationContract, before: &Path, after: &Path) -> Result<Hints, Unsupported> {
    let load = |dir: &Path| Build::load(dir).map_err(|e| Unsupported::new(Part::Alignment, format!("reading the build {}: {e}", dir.display())));
    let (b, a) = (load(before)?, load(after)?);
    let aligned = alignment::align(&b, &a, Some(contract));
    if let Some(m) = aligned.mappings.iter().find(|m| m.after == contract.subject && !m.complete()) {
        let gaps = if m.unsupported.is_empty() { vec!["an input has no candidate".to_string()] } else { m.unsupported.clone() };
        return Err(Unsupported::new(Part::Alignment, format!("mapping {} onto {}: {}", m.before, m.after, gaps.join("; "))));
    }
    Ok(alignment::hints(&aligned))
}
