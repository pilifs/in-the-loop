//! Alignment inference between two builds (`llm-dlc/loops/foundations-alignment.md`): which method of the new build
//! corresponds to each method of the old one that changed or is gone (step A2). Static: it reads the two builds'
//! class files and proves nothing. Every correspondence it finds is a proposal, with its evidence unchecked, written
//! to the hints file of [`crate::spec`] for a proof or a person to settle.
//!
//! A method of the old build that the new build declares with the same class, name and descriptor corresponds to
//! that method, and to no other: its callers reach it by that name, so nothing else is proposed for it. Unchanged
//! (the same code, constant pool references resolved), it needs no hint at all; changed, it gets one, to itself.
//! For a method that is gone, every method new in the new build (one the old build doesn't declare) of the same kind
//! (constructor or not) is a candidate when something ties the two: the same name, in its class or another one; the
//! same body shape; a similar body; a caller in common; or, in the same class, the same parameters. Each tie adds to
//! a score, and the candidates are ranked by it ([`Candidate::score`]). The first *leads* when it scores at least
//! [`LEAD`] and is alone or [`LEAD`] ahead of the second. Where none leads, the choice is a person's, not the tool's.
//!
//! For each pair matched, [`mappings`](mod@mappings) relates the arguments, records and result under the comparison's
//! preservation contract (step A3): anchored inputs fixed to themselves, internal ones and the result proposed from a
//! small catalogue. An object whose class changed shape is related field by field ([`fields`], step A4), from how
//! each version's constructors route their parameters into fields. What is left a person's decision is put as a
//! question ([`questions`], step A5), with each candidate, what approving it would mean, and the line that approves
//! it; approving sets the intent state only, and on each rerun a decision's evidence is brought up to date with the
//! current claim key ([`evidence`]): a proof's, kept, or stale.
//!
//! What this does not do: relate fields a constructor computes, or a class holding its own class; prove anything (a
//! regression proof settles a proposal's evidence); match loops or other control flow (deferred); or match one old method to several
//! new ones (an inlined or split method gets the closest one, or none).

use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::classfile::{flags, ClassFile, Insn, Method};
use crate::spec::{Ask, Evidence, Hint, HintContent, Hints, Intent, Source};
use crate::Error;

pub mod fields;
pub mod proofs;
pub mod mappings;
pub mod questions;
pub mod evidence;
pub use mappings::{mapping_hints, mappings, Mapping};

/// How far ahead of the second the first candidate must be to lead, and the least score with which even a candidate
/// that has no rival leads: one weak tie is a question, not a proposal.
pub const LEAD: u32 = 3;
/// At most this many candidates are kept per method, best first.
pub const CANDIDATES: usize = 5;
/// The hints file's format version, [`Hints::version`].
pub const HINTS_VERSION: u32 = 1;

/// The application classes of one build, by internal name: every class file under a directory.
pub struct Build {
    pub classes: BTreeMap<String, ClassFile>,
}

impl Build {
    pub fn load(dir: &Path) -> Result<Build, Error> {
        if !dir.is_dir() {
            return Err(Error::new(format!("{} is not a directory of class files", dir.display())));
        }
        let mut classes = BTreeMap::new();
        let mut stack = vec![dir.to_path_buf()];
        while let Some(d) = stack.pop() {
            for entry in std::fs::read_dir(&d)? {
                let path = entry?.path();
                if path.is_dir() {
                    stack.push(path);
                } else if path.extension().is_some_and(|e| e == "class") {
                    let class = ClassFile::parse(&std::fs::read(&path)?).map_err(|e| Error::new(format!("{}: {}", path.display(), e.0)))?;
                    if class.name != "module-info" {
                        classes.insert(class.name.clone(), class);
                    }
                }
            }
        }
        Ok(Build { classes })
    }

    /// The methods alignment matches: every method of every class but class initializers, synthetic methods (lambda
    /// bodies, accessors the compiler made) and bridges.
    fn methods(&self) -> impl Iterator<Item = (&ClassFile, &Method)> {
        self.classes.values().flat_map(|c| c.methods.iter().filter(|m| matched(m)).map(move |m| (c, m)))
    }

    fn declares(&self, owner: &str, name: &str, descriptor: &str) -> Option<(&ClassFile, &Method)> {
        let class = self.classes.get(owner)?;
        class.methods.iter().find(|m| m.name == name && m.descriptor == descriptor && matched(m)).map(|m| (class, m))
    }

    /// Who calls each method, as `owner#name` of the caller.
    fn callers(&self) -> BTreeMap<(String, String, String), BTreeSet<String>> {
        let mut out: BTreeMap<(String, String, String), BTreeSet<String>> = BTreeMap::new();
        for (class, method) in self.methods() {
            let Some(code) = &method.code else { continue };
            let Ok(insns) = code.instructions() else { continue };
            for (_, insn) in &insns {
                if let Some(i) = insn.invoke_index() {
                    if let Ok(m) = class.pool.member(i) {
                        out.entry((m.owner, m.name, m.descriptor)).or_default().insert(format!("{}#{}", class.name, method.name));
                    }
                }
            }
        }
        out
    }
}

fn matched(m: &Method) -> bool {
    !m.is_synthetic() && !m.is_bridge() && !m.is_class_initializer()
}

/// What happened to an old method.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Change {
    /// The new build declares it (same class, name and descriptor) with different code or access flags.
    Changed,
    /// The new build doesn't declare it.
    Vanished,
    /// The new build declares it with the same code and access flags, but a class it takes or returns (its receiver's
    /// class, a parameter's or the result's) changed shape between the builds: the same code over different objects,
    /// mapped like a changed method, its objects related field by field.
    Reshaped,
}

/// One static fact tying an old method to a candidate.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind")]
pub enum Basis {
    /// The same class, name and descriptor: the method itself.
    SameNameAndDescriptor,
    /// The same name in the same class, its signature changed.
    SameNameSameClass,
    /// The same name in another class.
    SameNameMoved,
    /// The same descriptor.
    SameDescriptor,
    /// The same parameter types in the same order, the return type changed.
    SameParameters,
    /// The same parameter types in another order.
    SameParameterTypes,
    /// The same return type.
    SameReturnType,
    /// The same code once references to the method's own class and to the method itself are set aside.
    SameBodyShape,
    /// Instructions in common, as a percentage of both bodies (twice the longest common subsequence of their
    /// instruction kinds over their lengths together).
    SimilarBody { percent: u32 },
    /// Callers of the old method in the old build that call the candidate in the new one.
    SameCallers { shared: usize, before: usize },
    /// The old method's class is gone from the new build.
    OldClassGone,
    /// The candidate's class is new in the new build.
    NewClass,
}

impl Basis {
    /// What this fact adds to a candidate's score.
    pub fn weight(&self) -> u32 {
        match self {
            Basis::SameNameAndDescriptor => 10,
            Basis::SameNameSameClass => 6,
            Basis::SameNameMoved => 4,
            Basis::SameDescriptor => 2,
            Basis::SameParameters => 2,
            Basis::SameParameterTypes | Basis::SameReturnType => 1,
            Basis::SameBodyShape => 4,
            Basis::SimilarBody { percent } => percent / 25,
            Basis::SameCallers { shared, before } => 2 + u32::from(shared == before),
            Basis::OldClassGone | Basis::NewClass => 1,
        }
    }

    pub fn describe(&self) -> String {
        match self {
            Basis::SameNameAndDescriptor => "the same name and descriptor".into(),
            Basis::SameNameSameClass => "the same name in the same class (a constructor of it, for a constructor), its signature changed".into(),
            Basis::SameNameMoved => "the same name, in another class".into(),
            Basis::SameDescriptor => "the same descriptor".into(),
            Basis::SameParameters => "the same parameters, its return type changed".into(),
            Basis::SameParameterTypes => "the same parameter types, reordered".into(),
            Basis::SameReturnType => "the same return type".into(),
            Basis::SameBodyShape => "the same body shape".into(),
            Basis::SimilarBody { percent } => format!("a similar body ({percent}% of its instructions in common)"),
            Basis::SameCallers { shared, before } => format!("{shared} of its {before} callers call it"),
            Basis::OldClassGone => "the old class is gone".into(),
            Basis::NewClass => "in a new class".into(),
        }
    }
}

/// A new method that may correspond to an old one.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Candidate {
    /// Its symbol, `pkg.Class#name`, with the parameter types when the name is overloaded in its class.
    pub after: String,
    /// The sum of its facts' weights ([`Basis::weight`]).
    pub score: u32,
    pub basis: Vec<Basis>,
}

/// One old method that changed, is gone, or kept its code over a class that changed shape, and its candidates, best
/// first.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MethodMatch {
    pub before: String,
    pub change: Change,
    pub candidates: Vec<Candidate>,
    /// Whether the first candidate leads: it scores at least [`LEAD`], and is alone or [`LEAD`] ahead of the second.
    pub leads: bool,
}

impl MethodMatch {
    pub fn leading(&self) -> Option<&Candidate> {
        self.leads.then(|| &self.candidates[0])
    }
}

/// The method correspondence of two builds.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MethodReport {
    /// The old methods that changed, are gone, or kept their code over a class that changed shape, in the old build's
    /// order.
    pub methods: Vec<MethodMatch>,
    /// How many old methods are unchanged: the same code, over classes that kept their shape.
    pub unchanged: usize,
    /// The new build's methods that are new and that no old method's candidates lead to.
    pub added: Vec<String>,
}

/// Matches the old build's changed and vanished methods with the new build's.
pub fn methods(before: &Build, after: &Build) -> MethodReport {
    let new: Vec<(&ClassFile, &Method)> = after.methods().filter(|(c, m)| before.declares(&c.name, &m.name, &m.descriptor).is_none()).collect();
    let (callers_before, callers_after) = (before.callers(), after.callers());
    let mut report = MethodReport { methods: Vec::new(), unchanged: 0, added: Vec::new() };
    let mut led: BTreeSet<String> = BTreeSet::new();
    for (bc, bm) in before.methods() {
        let old = symbol(bc, bm);
        if let Some((ac, am)) = after.declares(&bc.name, &bm.name, &bm.descriptor) {
            let same_code = bm.access == am.access && tokens(bc, bm, true) == tokens(ac, am, true);
            if same_code && !reshaped(before, after, bc, bm) {
                report.unchanged += 1;
            } else {
                let after = symbol(ac, am);
                led.insert(after.clone());
                let change = if same_code { Change::Reshaped } else { Change::Changed };
                report.methods.push(MethodMatch { before: old, change, candidates: vec![Candidate { after, score: Basis::SameNameAndDescriptor.weight(), basis: vec![Basis::SameNameAndDescriptor] }], leads: true });
            }
            continue;
        }
        let key = (bc.name.clone(), bm.name.clone(), bm.descriptor.clone());
        let old_callers = callers_before.get(&key).cloned().unwrap_or_default();
        let mut candidates: Vec<Candidate> = new
            .iter()
            .filter(|(_, am)| am.is_constructor() == bm.is_constructor())
            .filter_map(|(ac, am)| {
                let new_callers = callers_after.get(&(ac.name.clone(), am.name.clone(), am.descriptor.clone()));
                let basis = basis(before, after, (bc, bm), (ac, am), &old_callers, new_callers)?;
                Some(Candidate { after: symbol(ac, am), score: basis.iter().map(Basis::weight).sum(), basis })
            })
            .collect();
        candidates.sort_by(|a, b| b.score.cmp(&a.score).then_with(|| a.after.cmp(&b.after)));
        candidates.truncate(CANDIDATES);
        let leads = match candidates.as_slice() {
            [] => false,
            [only] => only.score >= LEAD,
            [first, second, ..] => first.score >= LEAD && first.score >= second.score + LEAD,
        };
        if leads {
            led.insert(candidates[0].after.clone());
        }
        report.methods.push(MethodMatch { before: old, change: Change::Vanished, candidates, leads });
    }
    report.added = new.iter().map(|(c, m)| symbol(c, m)).filter(|s| !led.contains(s)).collect();
    report
}

/// Whether a class the old method takes or returns (its receiver's, a parameter's, the result's) changed shape between
/// the builds, as [`mappings::same_shape`] has it: deeply, so a class holding one that changed counts too.
fn reshaped(before: &Build, after: &Build, class: &ClassFile, method: &Method) -> bool {
    let Ok(d) = method.parsed_descriptor() else { return false };
    let receiver = (!method.is_static()).then(|| crate::classfile::Type::object(&class.name));
    let changed = receiver.iter().chain(&d.params).chain([&d.ret]).any(|t| t.is_reference() && !mappings::same_shape(before, after, t));
    changed
}

/// The facts tying an old method to a new one, or `None` when nothing does: a candidate needs the same name, the
/// same body shape, a body at least half the same, a caller in common, or the same parameters in the same class.
fn basis(before: &Build, after: &Build, (bc, bm): (&ClassFile, &Method), (ac, am): (&ClassFile, &Method), old_callers: &BTreeSet<String>, new_callers: Option<&BTreeSet<String>>) -> Option<Vec<Basis>> {
    let mut out = Vec::new();
    // Constructors share a name, `<init>`, which says something only within a class.
    let same_name = bm.name == am.name && (!bm.is_constructor() || bc.name == ac.name);
    if same_name && bc.name == ac.name {
        out.push(Basis::SameNameSameClass);
    } else if same_name {
        out.push(Basis::SameNameMoved);
    }
    let (Ok(bd), Ok(ad)) = (bm.parsed_descriptor(), am.parsed_descriptor()) else { return None };
    if bm.descriptor == am.descriptor {
        out.push(Basis::SameDescriptor);
    } else {
        let sorted = |d: &crate::classfile::MethodDescriptor| {
            let mut v: Vec<String> = d.params.iter().map(|t| t.descriptor()).collect();
            v.sort();
            v
        };
        if bd.params == ad.params {
            out.push(Basis::SameParameters);
        } else if bd.params.len() > 1 && sorted(&bd) == sorted(&ad) {
            out.push(Basis::SameParameterTypes);
        }
        if bd.ret == ad.ret && !bm.is_constructor() {
            out.push(Basis::SameReturnType);
        }
    }
    let shape = bm.code.is_some() && tokens(bc, bm, true) == tokens(ac, am, true);
    if shape {
        out.push(Basis::SameBodyShape);
    }
    let percent = match (tokens(bc, bm, false), tokens(ac, am, false)) {
        (Some(a), Some(b)) if !shape && !a.is_empty() && !b.is_empty() => similarity(&a, &b),
        _ => 0,
    };
    if percent >= 50 {
        out.push(Basis::SimilarBody { percent });
    }
    let shared = new_callers.map_or(0, |n| old_callers.intersection(n).count());
    if shared > 0 {
        out.push(Basis::SameCallers { shared, before: old_callers.len() });
    }
    // Within one class, the same parameters (or the same descriptor) are a tie as well: a method renamed with its
    // signature kept, or with only its result changed.
    let same_parameters = bc.name == ac.name && bd.params == ad.params;
    if !(same_name || shape || percent >= 50 || shared > 0 || same_parameters) {
        return None;
    }
    if !after.classes.contains_key(&bc.name) {
        out.push(Basis::OldClassGone);
    }
    if !before.classes.contains_key(&ac.name) {
        out.push(Basis::NewClass);
    }
    Some(out)
}

/// A method's symbol: `pkg.Class#name`, or `pkg.Class#name(int, long)` when its class declares the name more than
/// once, as `--target` and `--before-target` take it.
pub fn symbol(class: &ClassFile, method: &Method) -> String {
    let base = format!("{}#{}", class.name.replace('/', "."), method.name);
    if class.methods.iter().filter(|m| m.name == method.name && matched(m)).count() > 1 {
        let params = method.parsed_descriptor().map(|d| d.params.iter().map(|t| t.java_name()).collect::<Vec<_>>().join(", ")).unwrap_or_default();
        format!("{base}({params})")
    } else {
        base
    }
}

/// A method's code as one string per instruction, constant pool references resolved, references to its own class
/// and to itself set aside, so that two class files compare by what they say. Exact, it keeps local variable slots,
/// branch offsets and field and method names: equal tokens are the same code. Coarse, it keeps only each
/// instruction's kind and the types it works on, for [`similarity`]. `None` when the code can't be decoded; an
/// abstract or native method has no instructions.
fn tokens(class: &ClassFile, method: &Method, exact: bool) -> Option<Vec<String>> {
    let Some(code) = &method.code else { return Some(vec![format!("no code {:x}", method.access & (flags::ABSTRACT | flags::NATIVE))]) };
    let pool = &class.pool;
    let own = |name: &str| if name == class.name { "<own>".to_string() } else { name.to_string() };
    let mut out = Vec::new();
    for (_, insn) in code.instructions().ok()? {
        let name = format!("{insn:?}");
        let kind = name.split(['(', ' ']).next().unwrap_or(&name).to_string();
        out.push(match &insn {
            Insn::Ldc(i) => format!("ldc {:?}", pool.loadable(*i).ok()?),
            Insn::GetStatic(i) | Insn::PutStatic(i) | Insn::GetField(i) | Insn::PutField(i) => {
                let m = pool.member(*i).ok()?;
                if exact {
                    format!("{kind} {}.{}:{}", own(&m.owner), m.name, m.descriptor)
                } else {
                    format!("{kind} {}", m.descriptor)
                }
            }
            Insn::InvokeVirtual(i) | Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) | Insn::InvokeInterface(i) => {
                let m = pool.member(*i).ok()?;
                let itself = m.owner == class.name && m.name == method.name && m.descriptor == method.descriptor;
                match (itself, exact) {
                    (true, _) => format!("{kind} <itself>"),
                    (false, true) => format!("{kind} {}.{}{}", own(&m.owner), m.name, m.descriptor),
                    (false, false) => format!("{kind} {}", m.name),
                }
            }
            Insn::New(i) | Insn::ANewArray(i) | Insn::CheckCast(i) | Insn::InstanceOf(i) => format!("{kind} {}", own(pool.class_name(*i).ok()?)),
            Insn::MultiANewArray(i, dims) => format!("{kind} {} {dims}", own(pool.class_name(*i).ok()?)),
            Insn::InvokeDynamic(i) => {
                let (b, name, descriptor) = pool.invoke_dynamic(*i).ok()?;
                if exact {
                    let bootstraps = class.bootstrap_methods().ok()?;
                    format!("{kind} {name}{descriptor} {:?}", bootstraps.get(b as usize)?)
                } else {
                    format!("{kind} {name}")
                }
            }
            Insn::Load(k, _) | Insn::Store(k, _) if !exact => format!("{kind} {k:?}"),
            Insn::If(c, _) | Insn::IfICmp(c, _) if !exact => format!("{kind} {c:?}"),
            Insn::IfACmp(..) | Insn::IfNull(_) | Insn::IfNonNull(_) | Insn::Goto(_) | Insn::IInc(..) | Insn::TableSwitch { .. } | Insn::LookupSwitch { .. } if !exact => kind,
            _ => name,
        });
    }
    if exact {
        out.extend(code.exception_table.iter().map(|h| format!("{h:?}")));
    }
    Some(out)
}

/// Twice the longest common subsequence of two token lists over their lengths together, as a percentage. Long
/// bodies are compared as multisets of tokens instead, which is cheaper and never lower.
fn similarity(a: &[String], b: &[String]) -> u32 {
    let common = if a.len() * b.len() <= 4_000_000 {
        let mut row = vec![0usize; b.len() + 1];
        for x in a {
            let mut diagonal = 0;
            for (j, y) in b.iter().enumerate() {
                let up = row[j + 1];
                row[j + 1] = if x == y { diagonal + 1 } else { row[j + 1].max(row[j]) };
                diagonal = up;
            }
        }
        row[b.len()]
    } else {
        let mut bag: BTreeMap<&String, usize> = BTreeMap::new();
        for x in a {
            *bag.entry(x).or_default() += 1;
        }
        b.iter().filter(|y| bag.get_mut(y).is_some_and(|n| *n > 0 && { *n -= 1; true })).count()
    };
    (200 * common / (a.len() + b.len())) as u32
}

/// The report's correspondences as hints: one per candidate, ranked, each inferred, proposed and unchecked.
pub fn method_hints(report: &MethodReport) -> Hints {
    let mut entries = Vec::new();
    for m in &report.methods {
        let alone = m.candidates.len() == 1;
        // A vanished method none of whose candidates leads is a person's choice.
        let decide = (m.change == Change::Vanished && !m.leads && !m.candidates.is_empty()).then(|| {
            format!("which new method takes the place of {}: {} candidate{}, none sure enough to propose on its own", m.before, m.candidates.len(), if alone { "" } else { "s" })
        });
        for (i, c) in m.candidates.iter().enumerate() {
            let mut why: Vec<String> = c.basis.iter().map(Basis::describe).collect();
            why.push(format!("score {}{}", c.score, if i == 0 && m.leads && !alone { ", leading" } else { "" }));
            entries.push(Hint {
                subject: m.before.clone(),
                content: HintContent::Method { before: m.before.clone(), after: c.after.clone() },
                source: Source::Inferred,
                intent: Intent::Proposed,
                evidence: Evidence::Unchecked,
                rank: (!alone || decide.is_some()).then_some(i as u32 + 1),
                ask: decide.as_ref().map(|d| Ask { decide: d.clone(), means: vec![format!("{} takes its place, and is compared against it (score {}: {})", c.after, c.score, c.basis.iter().map(Basis::describe).collect::<Vec<_>>().join("; "))] }),
                why,
            });
        }
    }
    Hints { version: HINTS_VERSION, entries }
}

/// Whether a hint is the tool's proposal, which a later run replaces, rather than a person's (stated or approved),
/// which no run touches.
pub(crate) fn tool_proposal(h: &Hint) -> bool {
    h.source == Source::Inferred && h.intent == Intent::Proposed
}

/// `existing` with its proposals replaced by `proposed`'s. Every hint a person stated or approved is kept as it is,
/// and no proposal is added for a subject a person has already decided, for that kind of hint (a method, a
/// correspondence, an observation change).
pub fn merge_hints(existing: Hints, proposed: Hints) -> Hints {
    let kind = |h: &Hint| std::mem::discriminant(&h.content);
    let decided: Vec<(std::mem::Discriminant<HintContent>, String)> = existing.entries.iter().filter(|h| !tool_proposal(h)).map(|h| (kind(h), h.subject.clone())).collect();
    let mut entries: Vec<Hint> = existing.entries.into_iter().filter(|h| !tool_proposal(h)).collect();
    entries.extend(proposed.entries.into_iter().filter(|h| !decided.contains(&(kind(h), h.subject.clone()))));
    Hints { version: HINTS_VERSION, entries }
}

/// What `jvmcontract align` reports: the method correspondence, and the mappings of the pairs it matched.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Alignment {
    #[serde(flatten)]
    pub methods: MethodReport,
    pub mappings: Vec<Mapping>,
    /// What the regression proofs showed, for the pairs `--prove` checked ([`proofs`]); none for a static run.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub proofs: Vec<proofs::MappingProof>,
}

/// Aligns two builds: their methods, then each pair's mapping, under `contract` for the pair it names (every other
/// pair under the contract its signatures imply).
pub fn align(before: &Build, after: &Build, contract: Option<&crate::spec::PreservationContract>) -> Alignment {
    let report = methods(before, after);
    let mappings = mappings::mappings(before, after, &report, contract);
    Alignment { methods: report, mappings, proofs: Vec::new() }
}

/// Checks the proposals of the pairs whose new method is `subject` (every pair when `None`) by the regression proof,
/// between the class directories `before` and `after` the alignment was made from ([`proofs`]). A pair with no
/// complete mapping has nothing to prove.
pub fn prove(alignment: &mut Alignment, before: &Path, after: &Path, subject: Option<&str>, settings: &proofs::Settings) -> Result<(), Error> {
    let keys = proofs::Keys::new(before, after)?;
    let wanted = |m: &&Mapping| subject.is_none_or(|s| m.after == s || m.after.split('(').next() == Some(s)) && !m.proposals.is_empty();
    alignment.proofs = alignment.mappings.iter().filter(wanted).map(|m| proofs::prove(before, after, &keys, m, settings)).collect();
    Ok(())
}

/// Every hint an alignment proposes: the methods', then the mappings'.
pub fn hints(alignment: &Alignment) -> Hints {
    let mut out = method_hints(&alignment.methods);
    out.entries.extend(mappings::checked_hints(&alignment.mappings, &alignment.proofs).entries);
    out
}

/// Reads a hints file; an empty one when it doesn't exist.
pub fn read_hints(path: &Path) -> Result<Hints, Error> {
    if !path.exists() {
        return Ok(Hints { version: HINTS_VERSION, entries: Vec::new() });
    }
    let hints: Hints = serde_json::from_str(&std::fs::read_to_string(path)?).map_err(|e| Error::new(format!("{}: not a hints file: {e}", path.display())))?;
    if hints.version != HINTS_VERSION {
        return Err(Error::new(format!("{}: hints file version {}, this tool writes {HINTS_VERSION}", path.display(), hints.version)));
    }
    Ok(hints)
}

pub fn write_hints(path: &Path, hints: &Hints) -> Result<(), Error> {
    std::fs::write(path, serde_json::to_string_pretty(hints).expect("serializable") + "\n")?;
    Ok(())
}

/// The report as text, one old method per paragraph.
pub fn render(report: &MethodReport) -> String {
    let mut out = String::new();
    for m in &report.methods {
        match (m.change, m.candidates.as_slice()) {
            (Change::Changed, _) => out.push_str(&format!("changed   {}: itself, the same name and descriptor\n", m.before)),
            (Change::Reshaped, _) => out.push_str(&format!("reshaped  {}: itself, its code unchanged, over a class that changed shape\n", m.before)),
            (Change::Vanished, []) => out.push_str(&format!("vanished  {}: no candidate\n", m.before)),
            (Change::Vanished, candidates) => {
                let verdict = if m.leads { "" } else { " (none leads: a person's choice)" };
                out.push_str(&format!("vanished  {}{verdict}\n", m.before));
                for (i, c) in candidates.iter().enumerate() {
                    let lead = if i == 0 && m.leads { "  leads" } else { "" };
                    out.push_str(&format!("  {}. {}  score {}{lead}: {}\n", i + 1, c.after, c.score, c.basis.iter().map(Basis::describe).collect::<Vec<_>>().join("; ")));
                }
            }
        }
    }
    for added in &report.added {
        out.push_str(&format!("new       {added}\n"));
    }
    let vanished: Vec<&MethodMatch> = report.methods.iter().filter(|m| m.change == Change::Vanished).collect();
    out.push_str(&format!(
        "{} changed, {} reshaped, {} vanished ({} with a leading candidate, {} without, {} with none), {} unchanged, {} new methods no candidate leads to\n",
        report.methods.iter().filter(|m| m.change == Change::Changed).count(),
        report.methods.iter().filter(|m| m.change == Change::Reshaped).count(),
        vanished.len(),
        vanished.iter().filter(|m| m.leads).count(),
        vanished.iter().filter(|m| !m.leads && !m.candidates.is_empty()).count(),
        vanished.iter().filter(|m| m.candidates.is_empty()).count(),
        report.unchanged,
        report.added.len()
    ));
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn strings(s: &[&str]) -> Vec<String> {
        s.iter().map(|x| x.to_string()).collect()
    }

    #[test]
    fn similarity_counts_instructions_in_order() {
        assert_eq!(similarity(&strings(&["a", "b", "c"]), &strings(&["a", "b", "c"])), 100);
        assert_eq!(similarity(&strings(&["a", "b", "c", "d"]), &strings(&["a", "c"])), 66);
        assert_eq!(similarity(&strings(&["a"]), &strings(&["b"])), 0);
    }

    fn hint(subject: &str, after: &str, source: Source, intent: Intent) -> Hint {
        Hint { subject: subject.into(), content: HintContent::Method { before: subject.into(), after: after.into() }, source, intent, evidence: Evidence::Unchecked, rank: None, why: Vec::new(), ask: None }
    }

    #[test]
    fn a_new_run_replaces_proposals_and_keeps_what_a_person_decided() {
        let existing = Hints {
            version: HINTS_VERSION,
            entries: vec![hint("a.A#f", "a.A#g", Source::Inferred, Intent::Proposed), hint("a.A#h", "a.B#h", Source::Inferred, Intent::Approved), hint("a.A#k", "a.A#m", Source::Stated, Intent::Proposed)],
        };
        let proposed = Hints {
            version: HINTS_VERSION,
            entries: vec![hint("a.A#f", "a.A#f2", Source::Inferred, Intent::Proposed), hint("a.A#h", "a.A#h2", Source::Inferred, Intent::Proposed), hint("a.A#k", "a.A#k2", Source::Inferred, Intent::Proposed)],
        };
        let merged = merge_hints(existing, proposed);
        let pairs: Vec<(&str, &str)> = merged
            .entries
            .iter()
            .map(|h| match &h.content {
                HintContent::Method { before, after } => (before.as_str(), after.as_str()),
                _ => unreachable!(),
            })
            .collect();
        assert_eq!(pairs, vec![("a.A#h", "a.B#h"), ("a.A#k", "a.A#m"), ("a.A#f", "a.A#f2")]);
    }
}
