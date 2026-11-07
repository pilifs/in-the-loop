//! Each proposal checked by the regression proof (the second half of step A3 of
//! `llm-dlc/loops/foundations-alignment.md`): `align --prove` runs [`crate::equivalence`] as a caller on every
//! complete mapping of a pair, with the flags it amounts to, and settles the pair by what the proofs show.
//!
//! **One attempt per proposal.** A proof that is vacuous (no input reaches the calls) proves nothing, and counts as
//! no proof. A proposal with field equations (A4) has no flag form, and isn't tried here: its proof is the heap
//! stream's correspondence check.
//!
//! **Collapse by proof.** Two proved proposals are one candidate when they give the old version the same observations
//! on every input of the claim, so that nothing a consumer sees tells them apart:
//! - with the same result relation: each makes the old version's observations a function of the new version's (the
//!   catalogue's relations all fix `previous` from `result`), the same function for both;
//! - with the same input mapping: the old version gets the same inputs from each, so it gives the same observations;
//!   the two relations both hold on every one of them, and differ only on new results no input of the claim produces.
//!   Where the old result is a `boolean`, such a result is found by evaluating both relations (`harness::expr`), and
//!   named: `previous == (result > 0)` and `previous == (result != 0)` differ at `-1`, which no input gives;
//! - and so on transitively, since "the same observations on every input" is an equivalence.
//!
//! The first by rank stands for them.
//!
//! **The outcome.**
//! - One candidate proved: its evidence is "proved for claim key K", and its intent is still proposed. For a
//!   standalone method (no external anchor) the relation is proved, and whether it is the intended one is
//!   unconfirmed; where the result's meaning changed, the relation is still a person's decision. What tells its
//!   collapsed relations apart is said with it.
//! - Several, with different input mappings and different relations: a question, each with its proof. An input that
//!   separates two of them is the counterexample of a refuted proposal that takes the inputs of one and the relation
//!   of the other: there the first gives the old version an observation the second's relation doesn't admit, while
//!   the second holds, so the two give the old version different observations. It is named where such a proposal was
//!   tried.
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
use crate::classfile::Type;
use crate::equivalence;
use crate::harness::expr;
use crate::interp::Value;
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
    /// One candidate after collapsing, proved: `proposal` stands for itself and for the `equivalent` ones. `apart`
    /// says what tells an equivalent one with another relation apart from it: a new result no input produces.
    Proved {
        proposal: usize,
        equivalent: Vec<usize>,
        note: Option<String>,
        #[serde(default, skip_serializing_if = "Vec::is_empty")]
        apart: Vec<String>,
    },
    /// Several candidates proved with different input mappings and different relations: a person's choice. `apart`
    /// names an input that separates two of them, where one was found.
    Asked {
        proved: Vec<usize>,
        #[serde(default, skip_serializing_if = "Vec::is_empty")]
        apart: Vec<String>,
    },
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

/// Whether two proposals give the old version the same inputs: the same expressions and the same field equations.
fn same_inputs(mapping: &Mapping, p: usize, q: usize) -> bool {
    let (a, b) = (&mapping.proposals[p], &mapping.proposals[q]);
    a.arguments == b.arguments && a.fields == b.fields
}

/// The type a JVM descriptor names, for the scalar types the expression language has.
fn scalar(descriptor: &str) -> Option<Type> {
    Type::parse(descriptor).ok().filter(|t| expr::ty_of(t).is_some())
}

/// The values tried for a scalar of type `t`: every value of a `boolean`, and for an integral type the values around
/// zero and the extremes.
fn samples(t: &Type) -> Vec<Value> {
    match expr::ty_of(t) {
        Some(expr::Ty::Boolean) => vec![Value::Int(0), Value::Int(1)],
        Some(expr::Ty::Int) => [0, 1, -1, 2, -2, i32::MIN, i32::MAX].into_iter().map(Value::Int).collect(),
        Some(expr::Ty::Long) => [0, 1, -1, 2, -2, i64::MIN, i64::MAX].into_iter().map(Value::Long).collect(),
        None => Vec::new(),
    }
}

fn shown(v: &Value, t: &Type) -> String {
    match (v, t) {
        (Value::Int(0), Type::Boolean) => "false".into(),
        (Value::Int(_), Type::Boolean) => "true".into(),
        (Value::Int(i), _) => i.to_string(),
        (Value::Long(l), _) => l.to_string(),
        (v, _) => format!("{v:?}"),
    }
}

/// What tells two result relations apart that both hold on every input of the claim, with the old version given the
/// same observations by each: a new result at which no old result satisfies both, so that no input of the claim
/// produces it. Found by evaluating the two over every old `boolean` and the sampled new results; `None` for another
/// old type (its values can't all be tried) or a relation over a record.
pub fn apart(mapping: &Mapping, a: &str, b: &str) -> Option<String> {
    let (old, new) = mapping.result.returns.as_ref()?;
    let (old, new) = (scalar(old).filter(|t| *t == Type::Boolean)?, scalar(new)?);
    let params = [expr::Param { name: "previous".into(), ty: old.clone(), slot: 0 }, expr::Param { name: "result".into(), ty: new.clone(), slot: old.slots() }];
    let (ea, eb) = (expr::parse(a, &params).ok()?, expr::parse(b, &params).ok()?);
    let holds = |e: &expr::Expr, previous: &Value, result: &Value| {
        let mut locals = vec![Value::Int(0); usize::from(old.slots() + new.slots())];
        locals[0] = *previous;
        locals[usize::from(old.slots())] = *result;
        matches!(expr::eval(e, &locals), Ok(Value::Int(1)))
    };
    let olds = samples(&old);
    samples(&new).into_iter().find_map(|r| {
        let (wa, wb): (Vec<&Value>, Vec<&Value>) = (olds.iter().filter(|p| holds(&ea, p, &r)).collect(), olds.iter().filter(|p| holds(&eb, p, &r)).collect());
        let list = |w: &[&Value]| if w.is_empty() { "none".to_string() } else { w.iter().map(|v| shown(v, &old)).collect::<Vec<_>>().join(" or ") };
        (!wa.iter().any(|v| wb.contains(v))).then(|| {
            format!("`{a}` and `{b}` both hold on every input of the claim, and differ only on new results no input of it produces: at {}, the first admits an old result of {} and the second {}", shown(&r, &new), list(&wa), list(&wb))
        })
    })
}

/// An input that separates two proved proposals `p` and `q` of different groups: the counterexample of a refuted
/// proposal with the inputs of one and the relation of the other.
fn separating(mapping: &Mapping, attempts: &[Attempt], p: usize, q: usize) -> Option<String> {
    let relation = |i: usize| mapping.proposals[i].relation.as_deref();
    [(p, q), (q, p)].into_iter().find_map(|(x, y)| {
        attempts.iter().find_map(|a| match &a.tried {
            Tried::Refuted { input, before, after } if same_inputs(mapping, a.proposal, x) && same(relation(a.proposal), relation(y)) => Some(format!(
                "#{} and #{} give the old version different observations on {input}: with #{}'s inputs it gives {before} where the new version gives {after}, which #{}'s relation doesn't admit, and #{} holds there (#{} tried both together and was refuted)",
                p + 1, q + 1, x + 1, y + 1, y + 1, a.proposal + 1
            )),
            _ => None,
        })
    })
}

/// What a pair's proofs settle: collapse by proof, then the outcome rules. Pure, so it is tested on its own.
pub fn settle(mapping: &Mapping, attempts: &[Attempt]) -> (Settled, String) {
    let proved: Vec<usize> = attempts.iter().filter(|a| a.tried == Tried::Proved).map(|a| a.proposal).collect();
    let relation = |i: usize| mapping.proposals[i].relation.as_deref();
    let alike = |p: usize, q: usize| same(relation(p), relation(q)) || same_inputs(mapping, p, q);
    let mut groups: Vec<Vec<usize>> = Vec::new();
    for &p in &proved {
        let (joined, rest): (Vec<Vec<usize>>, Vec<Vec<usize>>) = std::mem::take(&mut groups).into_iter().partition(|g| g.iter().any(|&q| alike(p, q)));
        let mut group: Vec<usize> = joined.into_iter().flatten().chain([p]).collect();
        group.sort();
        groups = rest;
        groups.push(group);
    }
    groups.sort_by_key(|g| g[0]);
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
            // Each other relation in the group once, with what tells it apart from the first's.
            let mut others: Vec<&str> = Vec::new();
            for &e in &rest {
                if let Some(r) = relation(e).filter(|r| !same(Some(r), relation(first)) && !others.iter().any(|o| same(Some(o), Some(r)))) {
                    others.push(r);
                }
            }
            let apart: Vec<String> = others
                .iter()
                .map(|r| match relation(first).and_then(|f| apart(mapping, f, r)) {
                    Some(why) => why,
                    None => format!("`{}` and `{r}` both hold on every input of the claim, with the same old inputs, so they give the old version the same observations; no new result that tells them apart was found", relation(first).unwrap_or("equal")),
                })
                .collect();
            let collapsed = if rest.is_empty() { String::new() } else { format!(", with {} equivalent under the contract", rest.iter().map(|p| format!("#{}", p + 1)).collect::<Vec<_>>().join(", ")) };
            let summary = format!("{pair}: #{} proved{collapsed}, intent still proposed{}", first + 1, note.as_ref().map(|n| format!(" ({n})")).unwrap_or_default());
            (Settled::Proved { proposal: first, equivalent: rest, note, apart }, summary)
        }
        many => {
            let firsts: Vec<usize> = many.iter().map(|g| g[0]).collect();
            let mut apart = Vec::new();
            for (i, gi) in many.iter().enumerate() {
                for gj in &many[i + 1..] {
                    if let Some(s) = gi.iter().flat_map(|&p| gj.iter().map(move |&q| (p, q))).find_map(|(p, q)| separating(mapping, attempts, p, q)) {
                        apart.push(s);
                    }
                }
            }
            let shown: Vec<String> = firsts.iter().map(|&p| format!("#{} ({})", p + 1, relation(p).unwrap_or("equal"))).collect();
            (Settled::Asked { proved: firsts, apart }, format!("{pair}: {} relations proved, a person's choice: {}", many.len(), shown.join(", ")))
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
