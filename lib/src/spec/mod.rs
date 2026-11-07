//! The shared IR of `llm-dlc/loops/foundations.md` (its Phase 0): the types the four streams of that brief meet at,
//! and the interfaces between them. Each stream owns one file here and implements its interface there; this file is
//! shared, and is changed by adding fields and variants, never by changing what one means.
//!
//! | Type | What it is | Filled by |
//! |---|---|---|
//! | [`PreservationContract`] | the external inputs of a comparison and the observations the old version is held to; inference may not change it | the signature, or an entry point's [`observe`] spec |
//! | [`ObjectDomain`] | the object part of an input domain: classes, bounds, nullability, aliasing, and how inputs are made | [`heap`] |
//! | [`Observation`] | one thing compared: a result, an exception, a field path, an identity relation within a version, an effect | [`heap`], [`observe`] |
//! | [`Correspondence`] | how old and new internal states relate, below the contract; `--before-arguments` and `--results-agree-when` are special cases ([`Correspondence::from_flags`]) | [`align`], or a person |
//! | [`Hints`] | candidate mappings, each with its source, intent state and evidence state | [`align`] |
//! | [`CanonicalClaim`] | the prepared claim whose parts decide a result, and nothing that depends on the result | every stream; digested by [`cache`] |
//! | [`Outcome`] | what a check established, with the observation accounting | [`heap`] |
//!
//! Until a stream has done its part, its interface returns [`Unsupported`] naming the stream, and the integration
//! contract's tests (`lib/tests/foundations.rs`) accept that and nothing else in its place.

pub mod align;
pub mod cache;
pub mod heap;
pub mod observe;

use serde::{Deserialize, Serialize};

/// Which stream of the brief a part belongs to.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Part {
    Heap,
    Summaries,
    Observations,
    Alignment,
}

/// The named result of an interface whose stream hasn't done its part yet, or of a case its part doesn't support.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Unsupported {
    pub part: Part,
    /// What isn't supported, in words.
    pub what: String,
}

impl Unsupported {
    pub fn new(part: Part, what: impl Into<String>) -> Self {
        Unsupported { part, what: what.into() }
    }
}

impl std::fmt::Display for Unsupported {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "unsupported ({:?}): {}", self.part, self.what)
    }
}

/// An external input of a comparison: a value both versions receive from the same logical request or call.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExternalInput {
    /// Its name at the boundary: a parameter (`cents`), a request parameter, a payload path.
    pub name: String,
    /// The Java type.
    #[serde(rename = "type")]
    pub ty: String,
    /// How the old version's input is derived from it: `identity` for an unchanged signature, else an expression a
    /// person stated. Never an inferred expression.
    pub derivation: Derivation,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind")]
pub enum Derivation {
    Identity,
    /// An expression over the new version's external inputs, stated by a person.
    Stated { expression: String },
}

/// The fixed part of a comparison: what the inputs mean outside, and what must be preserved.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PreservationContract {
    /// What is compared: `pkg.Class#method`, or an entry point (`POST /quotes`).
    pub subject: String,
    pub inputs: Vec<ExternalInput>,
    /// The observations the old version is held to, by id ([`Observation::id`]).
    pub required: Vec<String>,
    /// Observations a person approved as changed, by id, with what they approved.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub approved_changes: Vec<ApprovedChange>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ApprovedChange {
    pub observation: String,
    pub text: String,
}

/// The object part of an input domain.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ObjectDomain {
    /// The application classes an input object may have.
    pub classes: Vec<String>,
    /// How many input objects each version is given at most, and how many it may allocate.
    pub bounds: VersionBounds,
    /// Parameter or field paths that may be null; every other reference is not.
    #[serde(default)]
    pub nullable: Vec<String>,
    /// Pairs of parameter or field paths that may be the same object.
    #[serde(default)]
    pub may_alias: Vec<(String, String)>,
    pub made_by: Construction,
    /// The domain as a result states it: "objects made by these constructors, under these argument constraints".
    pub label: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct VersionBounds {
    pub before: ObjectBounds,
    pub after: ObjectBounds,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct ObjectBounds {
    /// Input objects, all parameters together.
    pub input_objects: u32,
    /// Objects the code may allocate in one call.
    pub allocations: u32,
}

/// How a domain's input objects are made.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind")]
pub enum Construction {
    /// By these constructors or factories, with symbolic arguments (decision 2 of the brief): every state is one the
    /// application can make, and no claim is made about states only later calls reach.
    Constructors { calls: Vec<String> },
    /// Field by field: states no constructor makes are included, as assumptions. Named, not built in this loop.
    FieldByField,
    /// States constrained by invariants. Named, not built in this loop.
    Invariant { invariants: Vec<String> },
}

/// One thing a comparison observes.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind")]
pub enum Observation {
    /// The value returned (by value for primitives; a reference result is observed through field paths).
    Result,
    /// The category of exception thrown.
    Exception,
    /// An array parameter's contents after the call.
    ArrayParameter { parameter: String },
    /// A field path into the result or a parameter after the call: `result.total.cents`, `q.quantity`.
    FieldPath { path: String },
    /// An identity relation within one version, compared as "holds in old iff in new": `result == q`.
    Identity { left: String, right: String },
    /// A modeled boundary-call attempt, in order, with the payload paths it snapshots at the call.
    Effect { call: String, payload: Vec<String> },
    /// An entry point's response status for each outcome.
    Status,
}

impl Observation {
    /// A stable id, used by contracts, accounting and hints.
    pub fn id(&self) -> String {
        match self {
            Observation::Result => "result".into(),
            Observation::Exception => "exception".into(),
            Observation::ArrayParameter { parameter } => format!("array:{parameter}"),
            Observation::FieldPath { path } => format!("field:{path}"),
            Observation::Identity { left, right } => format!("identity:{left}=={right}"),
            Observation::Effect { call, .. } => format!("effect:{call}"),
            Observation::Status => "status".into(),
        }
    }
}

/// The environment the two versions of an entry point run in: one model for both.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EnvironmentModel {
    /// The calls replaced by recording stubs, with the outcomes each may give: corresponding calls in the two
    /// versions get the same one.
    pub calls: Vec<ModeledCall>,
    /// The most effects a trace records; reaching it leaves the result unresolved.
    pub trace_bound: u32,
    /// Effects are compared in exact order (the only order policy in this loop).
    pub order: OrderPolicy,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ModeledCall {
    /// The call, as `owner#name(descriptor)`.
    pub call: String,
    /// The outcomes it may give: `returns`, or an exception class it may throw.
    pub outcomes: Vec<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum OrderPolicy {
    Exact,
}

/// How old and new internal states relate, below the preservation contract.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Correspondence {
    /// How the old version's internal input is made from the new one's: `old.cents == new.amount.cents`.
    pub inputs: Vec<Equation>,
    /// Boolean relations over `old.` and `new.` paths that must hold after the call, in place of equality for the
    /// observations they name.
    pub outputs: Vec<Relation>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Equation {
    /// A path into the old version's input: `old.cents`, or a parameter `old.n`.
    pub old: String,
    /// An expression over the new version's input: `new.amount.cents`.
    pub new: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Relation {
    /// The observation it replaces equality for, by id.
    pub observation: String,
    /// A boolean expression over `old.` and `new.`.
    pub holds: String,
}

impl Correspondence {
    /// The correspondence the existing flags state: `--before-arguments` gives the old version's argument `i` (named
    /// `old_parameters[i]`) as an expression over the new parameters, and `--results-agree-when` a relation over
    /// `previous` (the old result) and `result` (the new one), which becomes one over `old.result` and `new.result`.
    pub fn from_flags(old_parameters: &[String], before_arguments: Option<&[String]>, results_agree_when: Option<&str>) -> Correspondence {
        let inputs = match before_arguments {
            Some(exprs) => old_parameters
                .iter()
                .zip(exprs)
                .map(|(p, e)| Equation { old: format!("old.{p}"), new: rename_words(e, &[], "new.") })
                .collect(),
            None => old_parameters.iter().map(|p| Equation { old: format!("old.{p}"), new: format!("new.{p}") }).collect(),
        };
        let outputs = results_agree_when
            .map(|r| vec![Relation {
                observation: Observation::Result.id(),
                holds: rename_words(r, &[("previous", "old.result"), ("result", "new.result")], ""),
            }])
            .unwrap_or_default();
        Correspondence { inputs, outputs }
    }
}

/// Renames whole identifiers in an expression: the pairs given, and with a prefix every other identifier that starts
/// a path (not a number, not a member after a dot, not a Java keyword or literal, not a call like `Math.abs`).
fn rename_words(expr: &str, renames: &[(&str, &str)], prefix: &str) -> String {
    const KEEP: &[&str] = &["true", "false", "null", "new", "instanceof", "Math", "Integer", "Long"];
    let mut out = String::new();
    let chars: Vec<char> = expr.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        if c.is_alphabetic() || c == '_' {
            let start = i;
            while i < chars.len() && (chars[i].is_alphanumeric() || chars[i] == '_') {
                i += 1;
            }
            let word: String = chars[start..i].iter().collect();
            let after_dot = start > 0 && chars[start - 1] == '.';
            let is_call = i < chars.len() && chars[i] == '(';
            if after_dot || is_call || KEEP.contains(&word.as_str()) {
                out.push_str(&word);
            } else if let Some((_, to)) = renames.iter().find(|(from, _)| *from == word) {
                out.push_str(to);
            } else if !prefix.is_empty() {
                out.push_str(prefix);
                out.push_str(&word);
            } else {
                out.push_str(&word);
            }
        } else {
            out.push(c);
            i += 1;
        }
    }
    out
}

/// A machine-written file of candidate mappings, beside the build, never in the source tree.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Hints {
    pub version: u32,
    pub entries: Vec<Hint>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Hint {
    /// What the hint is about: the contract's subject.
    pub subject: String,
    pub content: HintContent,
    pub source: Source,
    pub intent: Intent,
    pub evidence: Evidence,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind")]
pub enum HintContent {
    /// Which new method corresponds to an old one.
    Method { before: String, after: String },
    Correspondence { correspondence: Correspondence },
    /// An observation a person may approve as changed.
    ObservationChange { observation: String, text: String },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Source {
    Inferred,
    Stated,
}

/// The intent state: whether a person approved it. Independent of the evidence.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Intent {
    Proposed,
    Approved,
}

/// The evidence state: what a check showed, and under which claim. Independent of the intent.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "state")]
pub enum Evidence {
    Unchecked,
    Proved { claim_key: String },
    Refuted { claim_key: String, witness: String },
    Unknown { why: String },
    /// Proved or refuted under a claim key that no longer matches either version.
    Stale { claim_key: String },
}

/// The prepared claim: everything that decides a result, after flags, hints, inferred mappings, models and generated
/// observations are resolved. Nothing that depends on the result or the run (verdict, vacuity, confirmation,
/// timings, ids, reuse) is part of it. The cache digests it; a result record is its key plus verdict, evidence and run
/// provenance.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CanonicalClaim {
    pub contract: PreservationContract,
    /// A digest of each version's code closure (`cache` defines what the closure covers).
    pub closures: VersionDigests,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub domain: Option<ObjectDomain>,
    pub observations: Vec<Observation>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub correspondence: Option<Correspondence>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub environment: Option<EnvironmentModel>,
    pub bounds: ClaimBounds,
    /// The assumptions with their contracts and stubs, as `Statement` words them.
    pub assumptions: Vec<String>,
    /// The digest of the JDK models, the JDK release, the checker and its configuration, the tool binary's digest.
    pub tools: ToolIdentity,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct VersionDigests {
    pub before: String,
    pub after: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ClaimBounds {
    pub unwind: u32,
    pub max_array_length: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ToolIdentity {
    pub models: String,
    pub jdk: String,
    pub checker: String,
    pub binary: String,
}

/// What a check established.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Outcome {
    pub verdict: Verdict,
    /// The domain's label, as the result states it.
    pub domain: String,
    /// Each required observation, and what became of it.
    pub accounting: Vec<Accounted>,
    /// A witness that replays, for a refutation.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub witness: Option<String>,
    /// Why the result is unresolved, or what a refutation's witness shows beyond the claim's observations.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub problem: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Verdict {
    Verified,
    Refuted,
    Unresolved,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Accounted {
    pub observation: String,
    pub state: ObservationState,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ObservationState {
    Preserved,
    ChangedWithApproval,
    Unresolved,
    Refuted,
}

/// What this loop adds to a [`crate::statement::Statement`]: none until a stream fills it.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StatementSpec {
    pub contract: PreservationContract,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub domain: Option<ObjectDomain>,
    pub observations: Vec<Observation>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub correspondence: Option<Correspondence>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_flags_are_a_special_case_of_a_correspondence() {
        let c = Correspondence::from_flags(&["a".into(), "b".into()], Some(&["b".into(), "a + 1".into()]), Some("previous == (result > 0)"));
        assert_eq!(c.inputs, vec![
            Equation { old: "old.a".into(), new: "new.b".into() },
            Equation { old: "old.b".into(), new: "new.a + 1".into() },
        ]);
        assert_eq!(c.outputs, vec![Relation { observation: "result".into(), holds: "old.result == (new.result > 0)".into() }]);
        let plain = Correspondence::from_flags(&["n".into()], None, None);
        assert_eq!(plain.inputs, vec![Equation { old: "old.n".into(), new: "new.n".into() }]);
        assert!(plain.outputs.is_empty());
    }

    #[test]
    fn record_components_and_calls_keep_their_names() {
        let c = Correspondence::from_flags(&["r".into()], Some(&["new R(this.a, p.b)".into()]), Some("Math.abs(previous.x - result.x) <= 1"));
        assert_eq!(c.inputs[0].new, "new R(new.this.a, new.p.b)");
        assert_eq!(c.outputs[0].holds, "Math.abs(old.result.x - new.result.x) <= 1");
    }

    #[test]
    fn observation_ids_are_stable() {
        let ids: Vec<String> = [
            Observation::Result,
            Observation::FieldPath { path: "result.total".into() },
            Observation::Identity { left: "result".into(), right: "q".into() },
            Observation::Effect { call: "kafka.send".into(), payload: vec!["total".into()] },
        ]
        .iter()
        .map(Observation::id)
        .collect();
        assert_eq!(ids, ["result", "field:result.total", "identity:result==q", "effect:kafka.send"]);
    }
}
