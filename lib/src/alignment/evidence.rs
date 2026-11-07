//! The evidence of a person's decision on a rerun (step A5 of `llm-dlc/loops/foundations-alignment.md`). Approving
//! sets the intent only: the evidence still comes from a proof under the current claim key, and goes stale when either
//! version changes. So every run with a hints file checks each hint a person approved or stated against what the run
//! knows now:
//! - a proof this run made of the same relation gives it that proof's evidence, under the current key;
//! - otherwise, evidence proved or refuted under a claim key that the current builds, flags and settings no longer give
//!   is `stale`, and evidence whose key they still give is kept;
//! - a relation this run doesn't propose at all has no current key, so its proved or refuted evidence is stale too.
//!
//! A method correspondence has no proof of its own: its evidence is its pair's, proved when one of the pair's mappings
//! is, under that mapping's key. Unchecked and unknown evidence names no key and stays as it is until a proof, as does
//! a hint of a kind no proof here checks (an observation change).

use super::proofs::{Keys, Settings, Settled, Tried};
use super::{Alignment, tool_proposal};
use crate::spec::{Evidence, HintContent, Hints};

/// What a run knows now of one relation it can propose.
#[derive(Debug, Clone, PartialEq)]
pub struct Now {
    pub subject: String,
    pub content: HintContent,
    /// Its claim keys under the current builds and settings: a correspondence's own, or for a method each of its
    /// pair's mappings'.
    pub keys: Vec<String>,
    /// The evidence this run's proof of it gave, if it made one.
    pub proof: Option<Evidence>,
}

/// Every relation `alignment` proposes, collapsed by a proof or not, with its current claim keys and the evidence of
/// any proof this run made.
pub fn current(alignment: &Alignment, keys: &Keys, settings: &Settings) -> Vec<Now> {
    let mut out = Vec::new();
    for m in &alignment.mappings {
        let proof = alignment.proofs.iter().find(|p| p.before == m.before && p.after == m.after);
        let tried = |i: usize| proof.and_then(|p| p.attempts.iter().find(|a| a.proposal == i)).filter(|a| !matches!(a.tried, Tried::NotTried { .. }));
        let mut pair = Vec::new();
        for (i, p) in m.proposals.iter().enumerate() {
            let key = keys.key(&m.after, &p.flags, settings);
            out.push(Now { subject: m.after.clone(), content: HintContent::Correspondence { correspondence: m.correspondence(p) }, keys: vec![key.clone()], proof: tried(i).map(|a| a.evidence.clone()) });
            pair.push(key);
        }
        let method = proof.filter(|p| p.attempts.iter().any(|a| !matches!(a.tried, Tried::NotTried { .. }))).map(|p| match &p.settled {
            Settled::Proved { proposal, .. } => tried(*proposal).map(|a| a.evidence.clone()).expect("a proved proposal was tried"),
            Settled::Asked { proved, .. } => tried(proved[0]).map(|a| a.evidence.clone()).expect("a proved proposal was tried"),
            Settled::NoneProved => Evidence::Unknown { why: format!("no mapping of the pair proved: {}", p.summary) },
        });
        out.push(Now { subject: m.before.clone(), content: HintContent::Method { before: m.before.clone(), after: m.after.clone() }, keys: pair, proof: method });
    }
    out
}

/// `hints` with the evidence of every hint a person approved or stated brought up to date by `now`, by the rules
/// above. The tool's own proposals are left as they are: a run writes them fresh.
pub fn refresh(hints: Hints, now: &[Now]) -> Hints {
    let entries = hints
        .entries
        .into_iter()
        .map(|mut h| {
            if tool_proposal(&h) || matches!(h.content, HintContent::ObservationChange { .. }) {
                return h;
            }
            let found = now.iter().find(|n| n.subject == h.subject && n.content == h.content);
            h.evidence = match (found, h.evidence) {
                (Some(Now { proof: Some(e), .. }), _) => e.clone(),
                (found, Evidence::Proved { claim_key } | Evidence::Refuted { claim_key, .. }) if !found.is_some_and(|n| n.keys.contains(&claim_key)) => Evidence::Stale { claim_key },
                (_, e) => e,
            };
            h
        })
        .collect();
    Hints { version: hints.version, entries }
}
