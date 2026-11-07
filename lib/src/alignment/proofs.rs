//! Each proposal checked by the regression proof (the second half of step A3 of
//! `llm-dlc/loops/foundations-alignment.md`): `align --prove` runs [`crate::equivalence`] as a caller on every
//! complete mapping of a pair, with the flags it amounts to, and settles the pair by what the proofs show.
//!
//! **One attempt per proposal.** A proof that is vacuous (no input reaches the calls) proves nothing, and counts as
//! no proof. A proposal with field equations (A4) has no flag form, and isn't tried here: its proof is the heap
//! stream's correspondence check.
//!
//! **Collapse by proof.** Two proved proposals with the same result relation are one candidate: under the contract,
//! each makes the old version's observations a function of the new version's on every input of the claim (the
//! catalogue's relations all fix `previous` from `result`), so the two give the old version the same observations
//! everywhere the claim covers, and nothing a consumer sees tells them apart. The first by rank stands for them.
//!
//! **The outcome.**
//! - One candidate proved: its evidence is "proved for claim key K", and its intent is still proposed. For a
//!   standalone method (no external anchor) the relation is proved, and whether it is the intended one is
//!   unconfirmed; where the result's meaning changed, the relation is still a person's decision.
//! - Several, with different relations: a question, each with its proof.
//! - None: every mapping tried, with its counterexample or why it has no verdict, so a person can see whether the
//!   change is a bug or the mapping is missing.
//!
//! **The claim key** is provisional: a digest of the tool's binary, every class file of both builds, the flags and
//! the proof's settings. Any change to either build makes it stale. It is coarser than the canonical claim key of the
//! proof cache (`spec::cache::key`), which replaces it once that is implemented.

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use super::mappings::{Flags, Mapping, ResultKind};
use crate::bmc::gaps::GapMode;
use crate::equivalence;
use crate::spec::Evidence;
use crate::{Engine, Error, Verdict};

/// How every proof of a run is made: the settings `jvmcontract equivalence` takes, and the scope a person declared.
#[derive(Debug, Clone, Serialize)]
pub struct Settings {
    pub engine: Engine,
    pub gaps: GapMode,
    pub unwind: u32,
    pub max_array_length: u32,
    #[serde(skip)]
    pub timeout_seconds: u64,
    #[serde(skip)]
    pub jbmc: String,
    /// The inputs the change is declared to affect (`--unchanged-unless`): a person's decision, part of the claim.
    pub unchanged_unless: Option<String>,
    #[serde(skip)]
    pub work: Option<PathBuf>,
}

impl Default for Settings {
    fn default() -> Settings {
        Settings { engine: Engine::Jbmc, gaps: GapMode::Strict, unwind: 16, max_array_length: 8, timeout_seconds: 600, jbmc: "jbmc".into(), unchanged_unless: None, work: None }
    }
}

/// What one proof of one proposal showed.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "verdict")]
pub enum Tried {
    /// Proved, and not vacuous.
    Proved,
    /// Verified, but no input reaches the calls: no evidence.
    Vacuous { why: String },
    /// A replayed counterexample.
    Refuted { input: String, before: String, after: String },
    /// No verdict: refused, out of time, or the check couldn't be set up.
    Unknown { why: String },
    /// Not tried: the proposal has no flag form.
    NotTried { why: String },
}

/// One proposal's proof.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Attempt {
    /// Its index in [`Mapping::proposals`].
    pub proposal: usize,
    pub flags: Flags,
    pub tried: Tried,
    pub evidence: Evidence,
}

/// How a pair stands after its proofs.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "outcome")]
pub enum Settled {
    /// One candidate after collapsing, proved: `proposal` stands for itself and for the `equivalent` ones.
    Proved { proposal: usize, equivalent: Vec<usize>, note: Option<String> },
    /// Several candidates proved with different relations: a person's choice.
    Asked { proved: Vec<usize> },
    /// No proposal proved.
    NoneProved,
}

/// The proofs of one pair's proposals, and what they settle.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MappingProof {
    pub before: String,
    pub after: String,
    pub attempts: Vec<Attempt>,
    pub settled: Settled,
    /// One line for a person: what was proved, asked, or refuted.
    pub summary: String,
}

/// The digest of every class file under `dir`, by path relative to it, sorted.
fn tree_digest(dir: &Path) -> Result<String, Error> {
    let mut files = Vec::new();
    let mut stack = vec![dir.to_path_buf()];
    while let Some(d) = stack.pop() {
        for entry in std::fs::read_dir(&d)? {
            let path = entry?.path();
            if path.is_dir() {
                stack.push(path);
            } else if path.extension().is_some_and(|e| e == "class") {
                files.push(path);
            }
        }
    }
    files.sort();
    let mut all = Vec::new();
    for f in files {
        all.extend(f.strip_prefix(dir).unwrap_or(&f).to_string_lossy().as_bytes());
        all.push(0);
        all.extend(crate::digest::sha256_hex(&std::fs::read(&f)?).as_bytes());
        all.push(b'\n');
    }
    Ok(crate::digest::sha256_hex(&all))
}

/// The provisional claim key of one proof: the tool, both builds, the pair, the flags and the settings.
pub struct Keys {
    tool: String,
    before: String,
    after: String,
}

impl Keys {
    pub fn new(before: &Path, after: &Path) -> Result<Keys, Error> {
        let tool = std::env::current_exe().ok().and_then(|p| std::fs::read(p).ok()).map(|b| crate::digest::sha256_hex(&b)).unwrap_or_else(|| "unknown".into());
        Ok(Keys { tool, before: tree_digest(before)?, after: tree_digest(after)? })
    }

    pub fn key(&self, target: &str, flags: &Flags, settings: &Settings) -> String {
        let text = serde_json::json!({ "tool": self.tool, "before": self.before, "after": self.after, "target": target, "flags": flags, "settings": settings });
        format!("whole-builds:sha256:{}", crate::digest::sha256_hex(text.to_string().as_bytes()))
    }
}

/// Proves one proposal's flags with the regression check, as its caller.
fn attempt(before: &Path, after: &Path, target: &str, flags: &Flags, settings: &Settings, index: usize) -> Tried {
    let mut o = equivalence::Options::new(before, after, target);
    o.unchanged_unless = settings.unchanged_unless.clone();
    o.unwind = settings.unwind;
    o.max_array_length = settings.max_array_length;
    o.timeout_seconds = settings.timeout_seconds;
    o.jbmc = settings.jbmc.clone();
    o.engine = settings.engine;
    o.gaps = settings.gaps;
    o.work = settings.work.as_ref().map(|w| w.join(format!("{}-{}", target.replace(['#', '.', '(', ')', ',', ' '], "_"), index + 1)));
    o.before_target = flags.before_target.clone();
    o.before_arguments = flags.before_arguments.clone();
    o.results_agree_when = flags.results_agree_when.clone();
    match equivalence::run(&o) {
        Err(e) => Tried::Unknown { why: e.0 },
        Ok(out) => match (out.verdict, out.vacuous, out.counterexample) {
            (Verdict::Verified, Some(why), _) => Tried::Vacuous { why },
            (Verdict::Verified, None, _) => Tried::Proved,
            (Verdict::Violation, _, Some(c)) => Tried::Refuted { input: c.input, before: c.before, after: c.after },
            (Verdict::Violation, _, None) => Tried::Unknown { why: "a violation without a counterexample".into() },
            (Verdict::Unverifiable, ..) => Tried::Unknown { why: out.problem.unwrap_or_else(|| "no verdict".into()) },
        },
    }
}

/// The evidence a proof gives, under `key`.
pub fn evidence(tried: &Tried, key: &str) -> Evidence {
    match tried {
        Tried::Proved => Evidence::Proved { claim_key: key.to_string() },
        Tried::Refuted { input, before, after } => Evidence::Refuted { claim_key: key.to_string(), witness: format!("{input}: before {before}, after {after}") },
        Tried::Vacuous { why } => Evidence::Unknown { why: format!("vacuous: {why}") },
        Tried::Unknown { why } | Tried::NotTried { why } => Evidence::Unknown { why: why.clone() },
    }
}

/// Whether two relations are the same, up to spacing.
fn same(a: Option<&str>, b: Option<&str>) -> bool {
    let squash = |s: Option<&str>| s.map(|s| s.split_whitespace().collect::<String>());
    squash(a) == squash(b)
}

/// What a pair's proofs settle: collapse by proof, then the outcome rules. Pure, so it is tested on its own.
pub fn settle(mapping: &Mapping, attempts: &[Attempt]) -> (Settled, String) {
    let proved: Vec<usize> = attempts.iter().filter(|a| a.tried == Tried::Proved).map(|a| a.proposal).collect();
    let mut groups: Vec<Vec<usize>> = Vec::new();
    for &p in &proved {
        let relation = mapping.proposals[p].relation.as_deref();
        match groups.iter_mut().find(|g| same(mapping.proposals[g[0]].relation.as_deref(), relation)) {
            Some(g) => g.push(p),
            None => groups.push(vec![p]),
        }
    }
    let pair = format!("{} -> {}", mapping.before, mapping.after);
    match groups.as_slice() {
        [] => {
            let tried: Vec<String> = attempts
                .iter()
                .map(|a| match &a.tried {
                    Tried::Refuted { input, before, after } => format!("#{} refuted by {input} (before {before}, after {after})", a.proposal + 1),
                    Tried::Vacuous { why } => format!("#{} vacuous ({why})", a.proposal + 1),
                    Tried::Unknown { why } | Tried::NotTried { why } => format!("#{} no verdict ({why})", a.proposal + 1),
                    Tried::Proved => unreachable!(),
                })
                .collect();
            (Settled::NoneProved, format!("{pair}: no mapping proved, {} tried: {}", attempts.len(), tried.join("; ")))
        }
        [group] => {
            let (first, rest) = (group[0], group[1..].to_vec());
            let note = if mapping.standalone {
                Some("standalone: this relation is proved; whether it is the intended one is unconfirmed".to_string())
            } else if mapping.result.kind == ResultKind::Changed {
                Some("what the result means changed: the relation is proved, and approving it is a person's decision".to_string())
            } else {
                None
            };
            let collapsed = if rest.is_empty() { String::new() } else { format!(", with {} equivalent under the contract", rest.iter().map(|p| format!("#{}", p + 1)).collect::<Vec<_>>().join(", ")) };
            let summary = format!("{pair}: #{} proved{collapsed}, intent still proposed{}", first + 1, note.as_ref().map(|n| format!(" ({n})")).unwrap_or_default());
            (Settled::Proved { proposal: first, equivalent: rest, note }, summary)
        }
        many => {
            let firsts: Vec<usize> = many.iter().map(|g| g[0]).collect();
            let shown: Vec<String> = firsts.iter().map(|&p| format!("#{} ({})", p + 1, mapping.proposals[p].relation.as_deref().unwrap_or("equal"))).collect();
            (Settled::Asked { proved: firsts }, format!("{pair}: {} relations proved, a person's choice: {}", many.len(), shown.join(", ")))
        }
    }
}

/// Proves every proposal of `mapping` between the class directories `before` and `after`.
pub fn prove(before: &Path, after: &Path, keys: &Keys, mapping: &Mapping, settings: &Settings) -> MappingProof {
    let attempts: Vec<Attempt> = mapping
        .proposals
        .iter()
        .enumerate()
        .map(|(i, p)| {
            let tried = if !p.fields.is_empty() {
                Tried::NotTried { why: "its field equations have no flag form: the correspondence proof is the heap stream's".into() }
            } else if mapping.result.kind == ResultKind::Fields {
                Tried::NotTried { why: "its result is an object compared field by field, which the regression check can't observe: the proof is the heap stream's".into() }
            } else {
                attempt(before, after, &mapping.after, &p.flags, settings, i)
            };
            let evidence = evidence(&tried, &keys.key(&mapping.after, &p.flags, settings));
            Attempt { proposal: i, flags: p.flags.clone(), tried, evidence }
        })
        .collect();
    let (settled, summary) = settle(mapping, &attempts);
    MappingProof { before: mapping.before.clone(), after: mapping.after.clone(), attempts, settled, summary }
}

/// The proofs as text, one pair per line, with each attempt under it.
pub fn render(proofs: &[MappingProof]) -> String {
    let mut out = String::new();
    for p in proofs {
        out.push_str(&format!("proof     {}\n", p.summary));
        for a in &p.attempts {
            let what = match &a.tried {
                Tried::Proved => "proved".to_string(),
                Tried::Vacuous { why } => format!("vacuous: {why}"),
                Tried::Refuted { input, before, after } => format!("refuted: {input}, before {before}, after {after}"),
                Tried::Unknown { why } => format!("no verdict: {why}"),
                Tried::NotTried { why } => format!("not tried: {why}"),
            };
            out.push_str(&format!("  #{} {}: {what}\n", a.proposal + 1, serde_json::to_string(&a.flags).expect("serializable")));
        }
    }
    out
}
