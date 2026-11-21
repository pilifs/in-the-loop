//! The proof output contract: what `jvmcontract prove --json` and `jvmcontract equivalence --json` print, and what
//! the process exit says beside it. The command line is one caller; `lib/python/jvmcontract_io.py` is the reader.
//!
//! - `prove --json` prints an array with one object for each property, in the order they were declared.
//! - `equivalence --json` prints one object.
//! - Every object is the outcome ([`crate::property::Outcome`], [`crate::equivalence::Outcome`]) with
//!   `wire_version` beside its fields. Output from before the field counts as version 0. A field added to an outcome
//!   that an older reader may ignore keeps the version; a field whose meaning changes, or one a reader must not
//!   ignore, takes the next.
//! - The process exits with 0 when every outcome is verified, with 1 when any is a violation or unverifiable (the
//!   maximum over the rows of a run, [`exit_code`]), and with 2 when the tool failed and printed no outcome.
//!
//! The two commands keep their own payloads. ([`crate::wire`] is another thing: the wire types of application
//! contracts.)

use serde::{Deserialize, Serialize};

/// The version new output carries.
pub const VERSION: u8 = 1;

/// An outcome as it is printed: its own fields, with the version beside them.
#[derive(Serialize)]
pub struct Versioned<'a, T> {
    pub wire_version: u8,
    #[serde(flatten)]
    pub outcome: &'a T,
}

/// `outcome` as this version of the contract prints it.
pub fn versioned<T>(outcome: &T) -> Versioned<'_, T> {
    Versioned { wire_version: VERSION, outcome }
}

/// What `prove --json` prints: every property's outcome, in the order given.
pub fn prove_json(outcomes: &[crate::property::Outcome]) -> String {
    serde_json::to_string_pretty(&outcomes.iter().map(versioned).collect::<Vec<_>>()).expect("serializable")
}

/// What `equivalence --json` prints: the one outcome.
pub fn equivalence_json(outcome: &crate::equivalence::Outcome) -> String {
    serde_json::to_string_pretty(&versioned(outcome)).expect("serializable")
}

/// The exit of a run with these verdicts: the maximum of each row's own ([`crate::Verdict::exit_code`]), so one
/// refuted or unresolved property among verified ones exits with 1 and the verified rows keep their results.
pub fn exit_code(verdicts: impl IntoIterator<Item = crate::Verdict>) -> i32 {
    verdicts.into_iter().map(crate::Verdict::exit_code).max().unwrap_or(0)
}

/// What a regression check did with one changed helper it offered for a proof of its own
/// ([`crate::proof_cache::Helpers`]), as data: an outcome's `helpers`, in the order they were asked about. The note
/// in the outcome's `output` is rendered from this ([`HelperDecision::note`]), so no reader has to parse it.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HelperDecision {
    pub callee: HelperCallee,
    pub action: HelperAction,
    /// The claim key of the proof the action rests on: the helper's own regression proof ([`HelperAction::Shared`])
    /// or the proof of its summary ([`HelperAction::SummaryApplied`]). None when the helper keeps its code.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub key: Option<String>,
    /// Whether that proof was found in the proof cache or made in this run.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source: Option<ProofSource>,
    /// Of a summary: what it reads, and the facts a call must satisfy for it to apply there. With facts the summary
    /// is conditional: a call where they don't hold keeps the helper's body.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub summary: Option<AppliedSummary>,
    /// Why the helper keeps its code.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reason: Option<HelperReason>,
    /// What its own check, or its summary, took; none when neither was started.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub seconds: Option<f64>,
}

/// The helper a decision is about, as the new version declares it.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HelperCallee {
    /// The declaring class, dotted (`quotes.QuoteService`).
    pub class: String,
    pub method: String,
    pub descriptor: String,
}

impl HelperCallee {
    /// `Class.method`, the name an outcome's `shared` and the notes use.
    pub fn name(&self) -> String {
        format!("{}.{}", self.class.rsplit('.').next().unwrap_or(&self.class), self.method)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum HelperAction {
    /// Its two versions were proved to agree on every input of its parameter types, by a regression proof of its
    /// own: one function in both versions, at every call.
    Shared,
    /// Its summary, proved over the fields it reads, is applied at each call in both versions.
    SummaryApplied,
    /// No proof of its own to use: it stays as written in both versions, and the caller's proof runs through it.
    StaysAsWritten,
    /// No summary to use: it keeps its body in both versions.
    KeepsBody,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ProofSource {
    Cache,
    ProvedNow,
}

impl ProofSource {
    pub fn of(found: bool) -> ProofSource {
        if found { ProofSource::Cache } else { ProofSource::ProvedNow }
    }

    fn words(self) -> &'static str {
        match self {
            ProofSource::Cache => "found in the proof cache",
            ProofSource::ProvedNow => "proved now and stored in the proof cache",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AppliedSummary {
    pub reads: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub facts: Vec<String>,
}

/// Why a helper keeps its code: a code a reader can decide by, and the tool's own words for a person.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HelperReason {
    pub code: ReasonCode,
    pub text: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ReasonCode {
    /// Its proof would rest on the proof it is used in.
    Cycle,
    /// None of the caller's time is left for it.
    NoTime,
    /// Its own check ended in an error.
    CheckFailed,
    /// Its own check ended, but in no result a caller may rest on (not verified, or resting on what a call would
    /// have to be checked against).
    NotApplicable,
    /// Its proof is not in the proof cache under a key the caller can name.
    NotStored,
    /// It has no summary: the summary's proof failed, or the helper is outside what a summary covers.
    NoSummary,
}

impl HelperDecision {
    /// The lines the outcome's `output` carries for this decision: what its check or summary took, when one ran,
    /// then the decision in words.
    pub fn note(&self) -> String {
        let name = self.callee.name();
        let mut out = String::new();
        let summary = matches!(self.action, HelperAction::SummaryApplied | HelperAction::KeepsBody);
        if let Some(seconds) = self.seconds {
            out.push_str(&if summary { format!("note: {name}'s summary took {seconds:.3} s\n") } else { format!("note: {name}'s own check took {seconds:.3} s\n") });
        }
        let key = self.key.as_deref().unwrap_or("");
        let how = self.source.map(ProofSource::words).unwrap_or("");
        let why = self.reason.as_ref().map(|r| r.text.as_str()).unwrap_or("");
        out.push_str(&match self.action {
            HelperAction::Shared => format!("note: {name}, changed: its two versions have the same outcome, result or exception, on every input, {how} (claim {key}); one function in both versions\n"),
            HelperAction::StaysAsWritten => format!("note: {name}, changed, stays as written in both versions: {why}\n"),
            HelperAction::KeepsBody => format!("note: {name}, changed, keeps its body in both versions: {why}\n"),
            HelperAction::SummaryApplied => {
                let (reads, facts) = self.summary.as_ref().map(|s| (s.reads.join(", "), s.facts.join(" and "))).unwrap_or_default();
                format!(
                    "note: {name}, changed, is applied by its summary at each call in both versions: its two versions, lifted over the fields it reads ({reads}), have the same outcome on every value of them and of its arguments{}, {how} (claim {key}); each call reads them from its actual receiver{}\n",
                    if facts.is_empty() { String::new() } else { format!(" where {facts}") },
                    if facts.is_empty() { "" } else { ", and a call where they don't hold keeps the helper's body" }
                )
            }
        });
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn callee() -> HelperCallee {
        HelperCallee { class: "quotes.QuoteService".into(), method: "fee".into(), descriptor: "(I)J".into() }
    }

    #[test]
    fn an_outcome_is_printed_with_the_version_beside_its_own_fields() {
        #[derive(Serialize)]
        struct Row { verdict: &'static str, output: &'static str }
        let value = serde_json::to_value(versioned(&Row { verdict: "verified", output: "" })).unwrap();
        assert_eq!(value, serde_json::json!({ "wire_version": 1, "verdict": "verified", "output": "" }));
    }

    #[test]
    fn a_run_exits_with_the_worst_of_its_rows() {
        use crate::Verdict::*;
        assert_eq!(exit_code([]), 0);
        assert_eq!(exit_code([Verified, Verified]), 0);
        assert_eq!(exit_code([Verified, Violation, Verified]), 1);
        assert_eq!(exit_code([Verified, Unverifiable]), 1);
    }

    #[test]
    fn a_helper_decision_reads_back_and_its_note_is_made_from_it() {
        let shared = HelperDecision { callee: callee(), action: HelperAction::Shared, key: Some("sha256:ab".into()), source: Some(ProofSource::Cache), summary: None, reason: None, seconds: Some(0.25) };
        assert_eq!(shared.note(), "note: QuoteService.fee's own check took 0.250 s\nnote: QuoteService.fee, changed: its two versions have the same outcome, result or exception, on every input, found in the proof cache (claim sha256:ab); one function in both versions\n");
        let value = serde_json::to_value(&shared).unwrap();
        assert_eq!(value, serde_json::json!({ "callee": { "class": "quotes.QuoteService", "method": "fee", "descriptor": "(I)J" }, "action": "shared", "key": "sha256:ab", "source": "cache", "seconds": 0.25 }));
        assert_eq!(serde_json::from_value::<HelperDecision>(value).unwrap(), shared);

        let conditional = HelperDecision { callee: callee(), action: HelperAction::SummaryApplied, key: Some("sha256:cd".into()), source: Some(ProofSource::ProvedNow), summary: Some(AppliedSummary { reads: vec!["this.feeCents".into(), "arg0".into()], facts: vec!["this.feeCents >= 0".into()] }), reason: None, seconds: None };
        assert_eq!(conditional.note(), "note: QuoteService.fee, changed, is applied by its summary at each call in both versions: its two versions, lifted over the fields it reads (this.feeCents, arg0), have the same outcome on every value of them and of its arguments where this.feeCents >= 0, proved now and stored in the proof cache (claim sha256:cd); each call reads them from its actual receiver, and a call where they don't hold keeps the helper's body\n");

        let kept = HelperDecision { callee: callee(), action: HelperAction::KeepsBody, key: None, source: None, summary: None, reason: Some(HelperReason { code: ReasonCode::NoSummary, text: "its two versions differ".into() }), seconds: Some(1.0) };
        assert_eq!(kept.note(), "note: QuoteService.fee's summary took 1.000 s\nnote: QuoteService.fee, changed, keeps its body in both versions: its two versions differ\n");
        assert_eq!(serde_json::to_value(&kept).unwrap()["reason"], serde_json::json!({ "code": "no-summary", "text": "its two versions differ" }));
    }
}
