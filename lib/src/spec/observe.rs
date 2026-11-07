//! The observations stream's interface (`llm-dlc/loops/foundations-observations.md`): an observation spec per Spring
//! entry point, two builds' specs compared into obligations, and the effect log the harness compares. Owned by that
//! stream; until it does its part, every call returns [`Unsupported`] naming it.

use std::path::Path;

use serde::{Deserialize, Serialize};

use super::{CanonicalClaim, EnvironmentModel, ExternalInput, Observation, Outcome, Part, Unsupported};
pub use crate::reach::{Placement, SiteKind};

/// An entry point and what a consumer observes of it, from [`crate::observations`]. The fields after `unresolved`
/// say how the analysis found the ones before: how each input is bound, the status of each outcome, each effect's
/// call site.
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
    #[serde(default)]
    pub kind: EntryKind,
    /// The annotation or route that makes it an entry point, as declared: `POST /quotes (consumes application/json)`.
    #[serde(default)]
    pub declared: String,
    /// How each input is bound, in the order of `inputs`.
    #[serde(default)]
    pub bindings: Vec<Binding>,
    /// The response's Java type (the body of a route), when the handler returns something.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub response: Option<String>,
    /// A route's status for each outcome: a normal return, then each exception it may throw.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub statuses: Vec<StatusOutcome>,
    /// Each call site that gives an effect (reads included, which are modeled calls but not observations).
    #[serde(default)]
    pub effects: Vec<EffectSite>,
    /// Which identity relations count at this boundary, and why.
    #[serde(default)]
    pub identity: String,
    /// What the environment model assumes, in words: these are the result's assumptions.
    #[serde(default)]
    pub assumptions: Vec<String>,
    /// The handler's first source line, when compiled with line numbers.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_line: Option<u16>,
    /// The handler as `Class.method(Types)`.
    #[serde(default)]
    pub method: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum EntryKind {
    #[default]
    Route,
    Listener,
    Schedule,
    /// An application-event listener.
    Event,
}

/// How an external input reaches the handler.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Binding {
    /// The input's name, as in `inputs`.
    pub input: String,
    pub source: BindingSource,
    /// The type the value is decoded into, dotted.
    pub wire_type: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum BindingSource {
    RequestParameter,
    PathVariable,
    Header,
    Cookie,
    MatrixVariable,
    Body,
    Part,
    ModelAttribute,
    /// A message's payload.
    Payload,
    /// An application event.
    Event,
}

impl BindingSource {
    pub fn words(self) -> &'static str {
        match self {
            BindingSource::RequestParameter => "request parameter",
            BindingSource::PathVariable => "path variable",
            BindingSource::Header => "header",
            BindingSource::Cookie => "cookie",
            BindingSource::MatrixVariable => "matrix variable",
            BindingSource::Body => "request body",
            BindingSource::Part => "request part",
            BindingSource::ModelAttribute => "model attribute",
            BindingSource::Payload => "payload",
            BindingSource::Event => "event",
        }
    }
}

/// What a route answers with for one outcome.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StatusOutcome {
    /// `returns`, or the exception thrown (`NotFoundException`).
    pub outcome: String,
    /// The status code, when the analysis can tell.
    pub status: Option<u16>,
    /// What decides it: `@ExceptionHandler ApiErrors.notFound`, `the default`.
    pub by: String,
}

/// One call site that gives an effect.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EffectSite {
    pub kind: SiteKind,
    /// What it is of or to: a document, a topic, a route.
    pub target: String,
    /// The modeled call, `owner#name(descriptor)`: the effect observation's id is `effect:` and this.
    pub call: String,
    /// The paths its payload is snapshotted at, at the call.
    pub payload: Vec<String>,
    pub placement: Placement,
    /// Where the call is, as `Class.method(Types)`.
    pub in_method: String,
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
    let fail = |e: crate::Error| Unsupported::new(Part::Observations, format!("reading the classes under {}: {e}", build.display()));
    let mut cp = crate::classpath::ClassPath::new();
    cp.add(build).map_err(fail)?;
    let local: std::collections::BTreeSet<String> = cp.application_class_names().map_err(fail)?.into_iter().collect();
    let cp = cp.with_default_jdk();
    crate::observations::analyse(&cp, Some(&local)).map_err(fail)
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
