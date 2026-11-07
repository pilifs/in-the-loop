//! The observations stream's interface (`llm-dlc/loops/foundations-observations.md`): an observation spec per Spring
//! entry point, two builds' specs compared into obligations, and the effect log the harness compares. Owned by that
//! stream; until it does its part, every call returns [`Unsupported`] naming it.

use std::path::Path;

use serde::{Deserialize, Serialize};

use super::{CanonicalClaim, EnvironmentModel, ExternalInput, Observation, Outcome, Part, Unsupported};

/// An entry point and what a consumer observes of it.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EntryPointSpec {
    /// A stable id: `POST /quotes`, `kafka quotes`, `schedule PT1M`.
    pub id: String,
    /// The handler, as `pkg.Class#method`.
    pub handler: String,
    /// Its external inputs: these are its preservation contract's.
    pub inputs: Vec<ExternalInput>,
    pub observations: Vec<Observation>,
    /// The environment its effects run in.
    pub environment: EnvironmentModel,
    /// What the analysis couldn't see, named; never dropped.
    #[serde(default)]
    pub unresolved: Vec<String>,
}

/// One obligation between two builds' entry points.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Obligation {
    /// The entry point's id, in the old build (or the new one, for a new entry point).
    pub entry: String,
    pub observation: String,
    pub change: Change,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Change {
    /// To be proved preserved.
    Preserved,
    Changed,
    New,
    Removed,
    Unresolved,
}

/// How a harness records the effects of one entry point: the stubs' calls, what each snapshots, and the bound.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EffectLogPlan {
    pub entry: String,
    pub environment: EnvironmentModel,
}

/// The entry points of the application whose classes are under `build`.
pub fn entry_points(build: &Path) -> Result<Vec<EntryPointSpec>, Unsupported> {
    let _ = build;
    Err(Unsupported::new(Part::Observations, "observation specs (O1)"))
}

/// The obligations between two builds' entry points; every old observation is accounted for.
pub fn compare(before: &[EntryPointSpec], after: &[EntryPointSpec]) -> Result<Vec<Obligation>, Unsupported> {
    let _ = (before, after);
    Err(Unsupported::new(Part::Observations, "comparing two builds' specs (O2)"))
}

/// The effect-log hook: how the harness records and compares the effects of `spec`'s entry point.
pub fn effect_log(spec: &EntryPointSpec) -> Result<EffectLogPlan, Unsupported> {
    let _ = spec;
    Err(Unsupported::new(Part::Observations, "recording stubs and the effect log (O3)"))
}

/// Discharges an entry point's obligations: proves that `claim`'s observations of the entry point `old` in the
/// classes under `before` are preserved by `new` under `after`, effects included, under the claim's environment
/// model. A refuted [`Outcome`] carries a witness replayed under the modeled dependencies.
pub fn check(claim: &CanonicalClaim, old: &EntryPointSpec, new: &EntryPointSpec, before: &Path, after: &Path) -> Result<Outcome, Unsupported> {
    let _ = (claim, old, new, before, after);
    Err(Unsupported::new(Part::Observations, "discharging an entry point's obligations (O3)"))
}
