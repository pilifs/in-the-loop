//! The reuse stream's module (`llm-dlc/loops/application-core-reuse.md`): the native property cache (R1), as a
//! projection of the canonical claim into the existing proof store, and summaries of read-only heap helpers
//! ([`Summary`], R2) a changed caller reuses where it discharges their applicability. Registered by Phase 0 of
//! `llm-dlc/loops/application-core.md`, so that the stream starts without editing a shared file. Until the stream
//! builds a part, its entry point returns [`Unsupported`] naming it, or reuses nothing.

use crate::spec::plans::Summary;
use crate::spec::{Part, Unsupported};

/// The proof store's result for a property check, under `--cache` of `prove`: `Ok(None)` for a miss, after which
/// the check runs and [`property_store`] stores what it found. Called by `property::run` before its proof.
pub fn property_lookup(options: &crate::property::Options) -> Result<Option<crate::property::Outcome>, Unsupported> {
    let _ = options;
    Err(Unsupported::new(Part::Reuse, "a proof cache for property checks (prove --cache): the reuse stream builds it (llm-dlc/loops/application-core-reuse.md)"))
}

/// Stores a property check's verified or refuted result under its claim key. Called by `property::run` after its
/// proof, under `--cache`, only once [`property_lookup`] has missed.
pub fn property_store(options: &crate::property::Options, outcome: &crate::property::Outcome) -> Result<(), Unsupported> {
    let _ = (options, outcome);
    Err(Unsupported::new(Part::Reuse, "a proof cache for property checks (prove --cache): the reuse stream builds it (llm-dlc/loops/application-core-reuse.md)"))
}

/// The summaries of `helper` (`pkg.Class#name(descriptor)`) a caller may apply, each still to be discharged at the
/// call site on the actual pre-call state. None until the stream builds them: a caller keeps the helper's body.
pub fn summaries(helper: &str) -> Vec<Summary> {
    let _ = helper;
    Vec::new()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_property_cache_is_refused_by_name_and_no_summary_is_offered_until_the_stream_builds_them() {
        let options = crate::property::Options::new(&[std::path::PathBuf::from("classes")], "shop.Pricing#fee");
        let gap = property_lookup(&options).unwrap_err();
        assert_eq!(gap.part, Part::Reuse);
        assert!(gap.what.contains("prove --cache"), "{gap}");
        assert!(summaries("shop.Pricing#fee(I)J").is_empty());
    }
}
