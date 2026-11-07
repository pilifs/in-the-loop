//! The question, well put (step A5 of `llm-dlc/loops/foundations-alignment.md`): every decision in a hints file that
//! is a person's, with what to decide, each candidate with what approving it would mean and its evidence (the
//! counterexample, where a proof refuted it), and the one line that approves it.
//!
//! A question is a subject (of one kind of hint: a method, a correspondence) whose proposals carry an
//! [`Ask`](crate::spec::Ask): several candidates and none ahead, a lone one matched on type alone, a result whose
//! meaning changed, or what a proof left open. A subject with a hint a person approved or stated is decided and not
//! asked again, so a hints file whose decisions are all approved asks nothing.
//!
//! Approving sets the intent state only. The evidence stays what a proof under the current claim key showed, or
//! unchecked; a person can approve before a proof, and an approved relation can later be refuted. Each run with a
//! hints file brings a decision's evidence up to date ([`super::evidence`]), and a decision that isn't proved under
//! the current claim key is listed with its evidence ([`Decision`]): not asked again, since its intent is settled,
//! but not counted as proved either. A hints file whose decisions are all approved and proved asks nothing and lists
//! nothing.

use std::path::Path;

use serde::{Deserialize, Serialize};

use super::tool_proposal;
use crate::Error;
use crate::spec::{Evidence, Hint, HintContent, Hints, Intent, Source};

/// One decision that is a person's.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Question {
    /// The kind of hint the candidates are ([`kind`]).
    pub kind: String,
    pub subject: String,
    /// What to decide.
    pub decide: String,
    /// The candidates, best first.
    pub answers: Vec<Answer>,
}

/// One candidate answer.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Answer {
    pub rank: Option<u32>,
    /// What approving it would settle, part by part.
    pub means: Vec<String>,
    pub evidence: Evidence,
    /// The one line that approves it.
    pub approve: String,
}

/// A decision a person made: a method or correspondence hint they approved or stated, with its evidence now.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Decision {
    pub kind: String,
    pub subject: String,
    /// "approved", or "stated" for a hint a person wrote.
    pub by: String,
    pub evidence: Evidence,
}

impl Decision {
    /// Whether it is proved under the current claim key. After [`super::evidence::refresh`], evidence that is still
    /// `proved` is for a key the current builds and settings give.
    pub fn proved(&self) -> bool {
        matches!(self.evidence, Evidence::Proved { .. })
    }
}

/// The decisions in `hints` a person made, of the kinds a proof gives evidence for (methods and correspondences), in
/// file order.
pub fn decisions(hints: &Hints) -> Vec<Decision> {
    hints
        .entries
        .iter()
        .filter(|h| decided(h) && !matches!(h.content, HintContent::ObservationChange { .. }))
        .map(|h| Decision { kind: kind(&h.content).into(), subject: h.subject.clone(), by: if h.source == Source::Stated { "stated" } else { "approved" }.into(), evidence: h.evidence.clone() })
        .collect()
}

/// The kind of a hint, as `approve --kind` names it.
pub fn kind(content: &HintContent) -> &'static str {
    match content {
        HintContent::Method { .. } => "method",
        HintContent::Correspondence { .. } => "correspondence",
        HintContent::ObservationChange { .. } => "observation-change",
    }
}

/// Whether a hint was decided by a person: approved, or stated.
fn decided(h: &Hint) -> bool {
    !tool_proposal(h)
}

/// The decisions in `hints` that are still a person's, in the order their subjects first appear. `file` is the hints
/// file the approval lines name.
pub fn questions(hints: &Hints, file: Option<&Path>) -> Vec<Question> {
    let file = file.map(|f| f.display().to_string()).unwrap_or_else(|| "FILE".into());
    let mut out: Vec<Question> = Vec::new();
    for h in hints.entries.iter().filter(|h| tool_proposal(h)) {
        let Some(ask) = &h.ask else { continue };
        let k = kind(&h.content);
        if hints.entries.iter().any(|d| decided(d) && kind(&d.content) == k && d.subject == h.subject) {
            continue;
        }
        let rank = h.rank.map(|r| format!(" --rank {r}")).unwrap_or_default();
        let answer = Answer { rank: h.rank, means: ask.means.clone(), evidence: h.evidence.clone(), approve: format!("jvmcontract approve --hints {file} --kind {k} --subject '{}'{rank}", h.subject) };
        match out.iter_mut().find(|q| q.kind == k && q.subject == h.subject) {
            Some(q) => q.answers.push(answer),
            None => out.push(Question { kind: k.into(), subject: h.subject.clone(), decide: ask.decide.clone(), answers: vec![answer] }),
        }
    }
    out
}

/// `hints` with the tool's proposal of `kind` for `subject` at `rank` approved (the only one, when no rank is given),
/// and the subject's other proposals of that kind dropped: the person chose. Its evidence is left as it is.
pub fn approve(hints: Hints, kind_name: &str, subject: &str, rank: Option<u32>) -> Result<(Hints, Hint), Error> {
    let mine = |h: &Hint| kind(&h.content) == kind_name && h.subject == subject;
    let proposals: Vec<&Hint> = hints.entries.iter().filter(|h| mine(h) && tool_proposal(h)).collect();
    if proposals.is_empty() {
        return Err(Error::new(if hints.entries.iter().any(|h| mine(h)) {
            format!("{subject}: its {kind_name} is already decided by a person, and has no proposal left to approve")
        } else {
            format!("{subject}: no {kind_name} proposal for it in the hints file")
        }));
    }
    let chosen = match rank {
        Some(r) => proposals.iter().position(|h| h.rank == Some(r)).ok_or_else(|| Error::new(format!("{subject}: no {kind_name} proposal ranked {r}; the ranks are {}", ranks(&proposals))))?,
        None if proposals.len() == 1 => 0,
        None => return Err(Error::new(format!("{subject}: {} {kind_name} proposals, so name one with --rank ({})", proposals.len(), ranks(&proposals)))),
    };
    let mut approved = proposals[chosen].clone();
    approved.intent = Intent::Approved;
    let mut entries = Vec::new();
    let mut placed = false;
    for h in hints.entries {
        if mine(&h) && tool_proposal(&h) {
            if !placed {
                entries.push(approved.clone());
                placed = true;
            }
        } else {
            entries.push(h);
        }
    }
    Ok((Hints { version: hints.version, entries }, approved))
}

fn ranks(proposals: &[&Hint]) -> String {
    proposals.iter().map(|h| h.rank.map(|r| r.to_string()).unwrap_or_else(|| "none".into())).collect::<Vec<_>>().join(", ")
}

/// An evidence state in words.
pub fn describe(evidence: &Evidence) -> String {
    match evidence {
        Evidence::Unchecked => "unchecked: no proof yet".into(),
        Evidence::Proved { claim_key } => format!("proved for {claim_key}"),
        Evidence::Refuted { claim_key, witness } => format!("refuted for {claim_key}, counterexample {witness}"),
        Evidence::Unknown { why } => format!("unknown: {why}"),
        Evidence::Stale { claim_key } => format!("stale: proved or refuted for {claim_key}, which no longer matches either version"),
    }
}

/// The questions as text: each decision, its candidates with what they mean and their evidence, and the approval
/// lines; then each decision a person made that isn't proved under the current claim key; or that nothing is asked.
pub fn render(questions: &[Question], decisions: &[Decision]) -> String {
    let plural = |n: usize| if n == 1 { "" } else { "s" };
    let mut out = String::new();
    for q in questions {
        out.push_str(&format!("question  {} ({}): decide {}\n", q.subject, q.kind, q.decide));
        for a in &q.answers {
            out.push_str(&format!("  {}. {}\n", a.rank.map(|r| r.to_string()).unwrap_or_else(|| "-".into()), if a.means.is_empty() { "as proposed".into() } else { a.means.join("; ") }));
            out.push_str(&format!("     evidence: {}\n", describe(&a.evidence)));
            out.push_str(&format!("     approve:  {}\n", a.approve));
        }
    }
    let unproved: Vec<&Decision> = decisions.iter().filter(|d| !d.proved()).collect();
    for d in &unproved {
        out.push_str(&format!("{:<9} {} ({}): not proved under the current claim key; evidence {}\n", d.by, d.subject, d.kind, describe(&d.evidence)));
    }
    let unproved_line = match unproved.len() {
        0 => String::new(),
        n => format!("; {n} of {} decision{} a person made {} not proved under the current claim key (`align --prove` checks {})", decisions.len(), plural(decisions.len()), if n == 1 { "is" } else { "are" }, if n == 1 { "it" } else { "them" }),
    };
    out.push_str(&match (questions.len(), decisions.len(), unproved.len()) {
        (0, 0, _) => "questions: none, nothing here is a person's decision\n".to_string(),
        (0, n, 0) => format!("questions: none; {n} decision{} a person made, {}proved under the current claim key\n", plural(n), if n == 1 { "" } else { "each " }),
        (0, ..) => format!("questions: none{unproved_line}\n"),
        (q, ..) => format!("{q} question{} for a person; approving one sets its intent only, and its evidence still comes from a proof{unproved_line}\n", plural(q)),
    });
    out
}
