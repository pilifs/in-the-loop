//! Argument, record and result mappings for the method pairs [`super::methods`] matches (step A3 of
//! `llm-dlc/loops/foundations-alignment.md`), under the comparison's preservation contract, which they may never
//! weaken. Static, like the rest of the module: every mapping is a proposal, with its evidence unchecked, until a
//! regression proof settles it.
//!
//! **Inputs.** Each old input (the receiver `this` first for an instance method, then the parameters) is given as an
//! expression over the new inputs, the form `--before-arguments` takes.
//! - An input the contract fixes (an external input with the identity derivation; for a standalone method, a
//!   parameter both versions have with the same name and type, wherever it now stands) is *anchored*: its mapping is
//!   that same input, and nothing else is ever proposed for it. A derivation a person stated is used as stated. No
//!   arithmetic is ever proposed: candidates are names, field paths, a cast between integral types, and a record
//!   built with its canonical constructor, so the offset mapping of the main brief (`before.c = after.c + 1`) can't
//!   arise.
//! - Any other input is *internal*, and its candidates come from the new inputs that aren't anchored: the parameters,
//!   the components of a record parameter (`p.c`), and the receiver's components or fields (`this.f`), ranked by
//!   name (the same, or one contained in the other: `batchStart` and `start`), type, and position. An old record whose
//!   components changed is built from the new inputs component by component (`new Backoff(this.baseMillis,
//!   this.capMillis)`). An old object that is not a record and whose fields changed is left to field correspondence
//!   (A4).
//! - A new input no candidate uses is left free: the claim covers every value of it, and restricting it (a scope) is
//!   a person's decision.
//!
//! **The result**, from a small catalogue: equal (the contract's comparison); equal after a widening (`int` to
//! `long`); equal after a known conversion (a value wrapped in a one-component record, or unwrapped from one); a
//! record that gained components, compared on the old ones (each old observation is still compared, the new
//! component is one the old version doesn't have); or a changed meaning, a `boolean` against a comparison of the new
//! integral result with zero, which is a person's decision: it is put as a question, every candidate listed.
//!
//! **Collapse.** Candidates that are the same expression (up to spacing) are one. Collapsing candidates that differ
//! in form but give every external input the same old-side value needs a proof, and is the regression check's.
//!
//! **Accounting.** Every observation the old version is held to is listed with how the mapping compares it; a
//! mapping can't remove one, and one whose relation is a person's decision stays unresolved until approved.

use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};

use super::{symbol, Build, Change, MethodReport, HINTS_VERSION};
use crate::classfile::{ClassFile, Method, Type};
use crate::spec::{Correspondence, Derivation, Evidence, ExternalInput, Hint, HintContent, Hints, Intent, Observation, PreservationContract, Source};

/// At most this many complete correspondences are written per method pair, best first.
pub const ALTERNATIVES: usize = 12;

/// What fixes an old input's meaning.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Anchor {
    /// The contract fixes it: an external input both versions take from the same value.
    Anchored,
    /// An internal representation: inference may propose how the two relate.
    Internal,
}

/// One candidate expression, and the static facts it rests on.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Choice {
    pub expression: String,
    /// Higher is stronger; candidates are ranked by it.
    pub score: u32,
    pub why: String,
}

/// How one old input is made from the new inputs.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct InputMapping {
    /// `this`, or the old parameter's name.
    pub old: String,
    pub anchor: Anchor,
    /// Best first. None: no candidate, and the pair has no complete mapping.
    pub candidates: Vec<Choice>,
    /// Whether the first is proposed on its own: it is alone, or ahead of the second. Otherwise it is a question.
    pub leads: bool,
}

/// How the results relate, from the catalogue.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ResultKind {
    /// The same type and shape: compared by equality, as the contract says. No relation is proposed.
    Equal,
    /// An integral result widened (`int` to `long`): the old value compared with the new one.
    Widened,
    /// A value wrapped in a one-component record, or unwrapped from one: the old value compared with the component.
    Converted,
    /// A record result that gained components: each old component compared with the same-named new one.
    Components,
    /// What the result means changed: a person's decision, put as a question.
    Changed,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ResultMapping {
    pub kind: ResultKind,
    /// `--results-agree-when` expressions over `previous` and `result`, best first; none for [`ResultKind::Equal`],
    /// or for a changed result the catalogue has nothing for.
    pub candidates: Vec<Choice>,
    /// Whether the tool may propose it on its own (`false`: only a person can decide it).
    pub inferred: bool,
}

/// An observation the old version is held to, and how the mapping compares it.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Kept {
    pub observation: String,
    pub how: String,
}

/// The mapping of one old method onto one new one.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Mapping {
    pub before: String,
    pub after: String,
    /// The contract the mapping is under: the one given, or for a standalone method the one its two signatures imply.
    pub contract: PreservationContract,
    /// No external contract was given: the anchors are only the shared parameter names, and a proved mapping shows
    /// that a relation holds, not that it is the one intended.
    pub standalone: bool,
    pub inputs: Vec<InputMapping>,
    /// New inputs that no candidate uses: left free.
    pub free: Vec<String>,
    pub result: ResultMapping,
    /// Every observation of the contract, with how it is compared.
    pub accounting: Vec<Kept>,
    /// What this step can't relate, and whose work it is.
    pub unsupported: Vec<String>,
    /// The complete mappings, best first ([`ALTERNATIVES`] at most): one alone is a proposal, several a question.
    pub proposals: Vec<Proposal>,
}

/// One complete mapping: an expression for each old input, and the result relation, with the flags they amount to.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Proposal {
    pub arguments: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub relation: Option<String>,
    pub flags: Flags,
}

/// The flags of one complete mapping, as `jvmcontract equivalence` takes them, the tool's defaults left out.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Flags {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub before_target: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub before_arguments: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub results_agree_when: Option<String>,
}

impl Mapping {
    /// Every input has a candidate.
    pub fn complete(&self) -> bool {
        self.unsupported.is_empty() && self.inputs.iter().all(|i| !i.candidates.is_empty())
    }

    /// The complete mappings, best first, at most [`ALTERNATIVES`]: one choice per input and one for the result,
    /// the leading ones alone where they lead, ordered by the sum of their places.
    fn alternatives(&self) -> Vec<(Vec<String>, Option<String>)> {
        if !self.complete() {
            return Vec::new();
        }
        let mut combos: Vec<(u32, Vec<String>)> = vec![(0, Vec::new())];
        for input in &self.inputs {
            let options: Vec<&Choice> = if input.leads { vec![&input.candidates[0]] } else { input.candidates.iter().collect() };
            combos = combos
                .iter()
                .flat_map(|(rank, chosen)| options.iter().enumerate().map(move |(i, c)| (rank + i as u32, chosen.iter().cloned().chain([c.expression.clone()]).collect::<Vec<_>>())))
                .take(ALTERNATIVES * 4)
                .collect();
        }
        let results: Vec<Option<String>> = if self.result.candidates.is_empty() {
            vec![None]
        } else if self.result.inferred && self.result.candidates.len() == 1 {
            vec![Some(self.result.candidates[0].expression.clone())]
        } else {
            self.result.candidates.iter().map(|c| Some(c.expression.clone())).collect()
        };
        let mut out: Vec<(u32, Vec<String>, Option<String>)> =
            combos.iter().flat_map(|(rank, args)| results.iter().enumerate().map(move |(i, r)| (rank + i as u32, args.clone(), r.clone()))).collect();
        out.sort_by_key(|(rank, ..)| *rank);
        out.truncate(ALTERNATIVES);
        out.into_iter().map(|(_, a, r)| (a, r)).collect()
    }

    /// The old inputs' names, in `--before-arguments` order.
    pub fn old_inputs(&self) -> Vec<String> {
        self.inputs.iter().map(|i| i.old.clone()).collect()
    }

    fn flags(&self, arguments: &[String], relation: Option<&str>, new_inputs: &[String]) -> Flags {
        Flags {
            before_target: (self.before != self.after).then(|| self.before.clone()),
            before_arguments: (arguments != new_inputs).then(|| arguments.join(", ")),
            results_agree_when: relation.map(str::to_string),
        }
    }

    /// Whether the mapping is the tool's default: the same method, every input to itself by position, the results
    /// compared by equality. It needs no hint.
    pub fn is_default(&self) -> bool {
        matches!(self.proposals.as_slice(), [p] if p.flags == Flags { before_target: None, before_arguments: None, results_agree_when: None })
    }
}

/// One version's view of a method: its inputs and result, and the shapes of the classes they are.
struct Side<'b> {
    build: &'b Build,
    class: &'b ClassFile,
    method: &'b Method,
    params: Vec<(String, Type)>,
    ret: Type,
}

impl<'b> Side<'b> {
    fn new(build: &'b Build, class: &'b ClassFile, method: &'b Method) -> Option<Side<'b>> {
        let d = method.parsed_descriptor().ok()?;
        let names = method.parameter_names(&class.pool);
        let params = d.params.iter().enumerate().map(|(i, t)| (names.get(i).cloned().unwrap_or_else(|| format!("arg{i}")), t.clone())).collect();
        Some(Side { build, class, method, params, ret: d.ret })
    }

    fn receiver(&self) -> Option<Type> {
        (!self.method.is_static()).then(|| Type::object(&self.class.name))
    }

    /// The inputs in `--before-arguments` order: `this` first for an instance method.
    fn inputs(&self) -> Vec<(String, Type)> {
        self.receiver().map(|t| ("this".to_string(), t)).into_iter().chain(self.params.iter().cloned()).collect()
    }
}

/// A class's shape in a build: its record components, or for another class its instance fields.
#[derive(Debug, Clone, PartialEq, Eq)]
struct Shape {
    record: bool,
    simple: String,
    members: Vec<(String, Type)>,
}

fn shape(build: &Build, t: &Type) -> Option<Shape> {
    let class = build.classes.get(t.class_name()?)?;
    let simple = t.simple_name();
    if class.is_record() {
        let members = class.record_components().ok()?.into_iter().map(|c| Some((c.name, Type::parse(&c.descriptor).ok()?))).collect::<Option<Vec<_>>>()?;
        Some(Shape { record: true, simple, members })
    } else {
        let members = class.fields.iter().filter(|f| !f.is_static()).map(|f| Some((f.name.clone(), Type::parse(&f.descriptor).ok()?))).collect::<Option<Vec<_>>>()?;
        Some(Shape { record: false, simple, members })
    }
}

/// A primitive value the new version receives: a parameter, a component of a record parameter, or a component or
/// field of the receiver.
#[derive(Debug, Clone)]
struct Leaf {
    path: String,
    /// Its own name: the parameter's, or the component's.
    name: String,
    ty: Type,
    /// The parameter's position, for a parameter itself.
    position: Option<usize>,
}

fn leaves(side: &Side) -> Vec<Leaf> {
    let mut out = Vec::new();
    let members = |owner: &str, t: &Type, out: &mut Vec<Leaf>| {
        if let Some(s) = shape(side.build, t) {
            for (name, ty) in s.members.into_iter().filter(|(_, ty)| ty.is_primitive()) {
                out.push(Leaf { path: format!("{owner}.{name}"), name, ty, position: None });
            }
        }
    };
    if let Some(t) = side.receiver() {
        members("this", &t, &mut out);
    }
    for (i, (name, t)) in side.params.iter().enumerate() {
        if t.is_primitive() {
            out.push(Leaf { path: name.clone(), name: name.clone(), ty: t.clone(), position: Some(i) });
        } else {
            members(name, t, &mut out);
        }
    }
    out
}

/// The integral types by width, for widening: `byte` < `short` < `int` < `long`, and `char` < `int`.
fn widens(from: &Type, to: &Type) -> bool {
    use Type::*;
    matches!((from, to), (Byte, Short | Int | Long) | (Short, Int | Long) | (Char, Int | Long) | (Int, Long))
}

fn integral(t: &Type) -> bool {
    matches!(t, Type::Byte | Type::Short | Type::Char | Type::Int | Type::Long)
}

/// Whether two names are related: one is the other with a word before or after it (`batchStart` and `start`,
/// `size` and `sizeLimit`), compared without case.
fn related(a: &str, b: &str) -> bool {
    let (a, b) = (a.to_lowercase(), b.to_lowercase());
    a != b && a.len() >= 2 && b.len() >= 2 && (a.ends_with(&b) || b.ends_with(&a) || a.starts_with(&b) || b.starts_with(&a))
}

/// The candidates for an old primitive input (`name`, `ty`, at `position` among the old parameters) among the new
/// leaves no anchored input took, best first.
fn primitive_candidates(name: &str, ty: &Type, position: Option<usize>, leaves: &[Leaf], taken: &BTreeSet<String>) -> Vec<Choice> {
    let mut out = Vec::new();
    for leaf in leaves.iter().filter(|l| !taken.contains(&l.path)) {
        let same_name = leaf.name == name;
        let near = related(&leaf.name, name);
        let place = u32::from(position.is_some() && position == leaf.position);
        let (score, how, expression) = if &leaf.ty == ty {
            match (same_name, near) {
                (true, _) => (3, "the same name and type", leaf.path.clone()),
                (_, true) => (2, "a related name, the same type", leaf.path.clone()),
                _ => (1, "the same type", leaf.path.clone()),
            }
        } else if (same_name || near) && widens(&leaf.ty, ty) {
            (if same_name { 2 } else { 1 }, "a related name, widened to the old type", leaf.path.clone())
        } else if (same_name || near) && widens(ty, &leaf.ty) {
            (1, "a related name, narrowed to the old type: a new value outside it is compared as the cast leaves it", format!("({}) {}", ty.java_name(), leaf.path))
        } else {
            continue;
        };
        let why = format!("{how}{}: {}", if place == 1 { ", the same position" } else { "" }, leaf.path);
        out.push(Choice { expression, score: score + place, why });
    }
    rank(out)
}

/// Sorted best first, with candidates that are the same expression (up to spacing) collapsed into the first.
fn rank(mut choices: Vec<Choice>) -> Vec<Choice> {
    choices.sort_by(|a, b| b.score.cmp(&a.score).then_with(|| a.expression.cmp(&b.expression)));
    let mut seen = BTreeSet::new();
    choices.retain(|c| seen.insert(c.expression.split_whitespace().collect::<String>()));
    choices
}

/// Whether the first candidate leads: it is alone with at least two points, or ahead of the second. A lone match on
/// type alone is a question.
fn leads(choices: &[Choice]) -> bool {
    match choices {
        [] => false,
        [only] => only.score >= 2,
        [first, second, ..] => first.score >= 2 && first.score > second.score,
    }
}

/// The contract a standalone method's two signatures imply: every input both take under the same name and type
/// (the receiver when its class keeps its name and shape) is external, with the identity derivation; the result, if
/// any, and the exception are required, and each array parameter both versions take.
fn implied_contract(old: &Side, new: &Side) -> PreservationContract {
    let new_inputs = new.inputs();
    let inputs = old
        .inputs()
        .into_iter()
        .filter(|(name, t)| new_inputs.iter().any(|(n, u)| n == name && u == t) && same_shape(old.build, new.build, t))
        .map(|(name, t)| ExternalInput { name, ty: t.java_name(), derivation: Derivation::Identity })
        .collect();
    let mut required = Vec::new();
    if old.ret != Type::Void {
        required.push(Observation::Result.id());
    }
    required.push(Observation::Exception.id());
    for (name, t) in &old.params {
        if matches!(t, Type::Array(_)) && new_inputs.iter().any(|(n, u)| n == name && u == t) {
            required.push(Observation::ArrayParameter { parameter: name.clone() }.id());
        }
    }
    PreservationContract { subject: symbol(new.class, new.method), inputs, required, approved_changes: Vec::new() }
}

/// A type means the same in both builds: a primitive or array, a class neither build declares, or one with the same
/// shape in both.
fn same_shape(before: &Build, after: &Build, t: &Type) -> bool {
    match (shape(before, t), shape(after, t)) {
        (None, None) => true,
        (Some(a), Some(b)) => a == b,
        _ => false,
    }
}

/// The mapping of `old` onto `new` under `contract`, or under the one their signatures imply when none is given.
fn map(before: &Build, after: &Build, (bc, bm): (&ClassFile, &Method), (ac, am): (&ClassFile, &Method), contract: Option<&PreservationContract>) -> Option<Mapping> {
    let (old, new) = (Side::new(before, bc, bm)?, Side::new(after, ac, am)?);
    let standalone = contract.is_none();
    let contract = contract.cloned().unwrap_or_else(|| implied_contract(&old, &new));
    let new_leaves = leaves(&new);
    let new_inputs = new.inputs();
    let mut unsupported = Vec::new();
    let mut taken: BTreeSet<String> = BTreeSet::new();
    let mut inputs: Vec<Option<InputMapping>> = vec![None; old.inputs().len()];
    // Anchored inputs first: their mapping is fixed, and the new inputs they take are no one else's.
    for (i, (name, t)) in old.inputs().iter().enumerate() {
        let Some(external) = contract.inputs.iter().find(|e| &e.name == name) else { continue };
        let expression = match &external.derivation {
            Derivation::Stated { expression } => expression.clone(),
            Derivation::Identity if new_inputs.iter().any(|(n, _)| n == name) => name.clone(),
            Derivation::Identity => {
                unsupported.push(format!("the contract fixes {name} to itself, and the new version has no input {name}"));
                continue;
            }
        };
        let identity = expression == *name;
        if identity {
            taken.insert(name.clone());
            taken.extend(new_leaves.iter().filter(|l| l.path.starts_with(&format!("{name}."))).map(|l| l.path.clone()));
            if t.is_reference() && !same_shape(before, after, t) {
                unsupported.push(format!("{name} is fixed to itself, and its class {} changed shape: relating its fields is field correspondence (A4)", t.java_name()));
            }
        }
        let why = if identity { format!("fixed by the contract: the same {} {name}", external.ty) } else { format!("fixed by the contract: {name} is {expression}, as a person stated") };
        inputs[i] = Some(InputMapping { old: name.clone(), anchor: Anchor::Anchored, candidates: vec![Choice { expression, score: 3, why }], leads: true });
    }
    // Then the internal ones, from what is left.
    for (i, (name, t)) in old.inputs().iter().enumerate() {
        if inputs[i].is_some() {
            continue;
        }
        let position = (name != "this").then(|| i - usize::from(old.receiver().is_some()));
        let candidates = if t.is_primitive() {
            primitive_candidates(name, t, position, &new_leaves, &taken)
        } else {
            match shape(before, t) {
                Some(s) if s.record && s.members.iter().all(|(_, ty)| ty.is_primitive()) => built(&s, &new_leaves, &taken),
                Some(s) => {
                    unsupported.push(format!("{name}'s class {} changed and is not a record of primitives: relating its fields is field correspondence (A4)", s.simple));
                    Vec::new()
                }
                None => {
                    unsupported.push(format!("{name} is a {} the new version doesn't take: no candidate", t.java_name()));
                    Vec::new()
                }
            }
        };
        let lead = leads(&candidates);
        inputs[i] = Some(InputMapping { old: name.clone(), anchor: Anchor::Internal, candidates, leads: lead });
    }
    let inputs: Vec<InputMapping> = inputs.into_iter().flatten().collect();
    let used: BTreeSet<String> = inputs
        .iter()
        .filter(|i| i.leads)
        .flat_map(|i| new_leaves.iter().filter(|l| mentions(&i.candidates[0].expression, &l.path)).map(|l| l.path.clone()).collect::<Vec<_>>())
        .collect();
    let complete = unsupported.is_empty() && inputs.iter().all(|i| !i.candidates.is_empty());
    let free = if complete { new_leaves.iter().map(|l| l.path.clone()).filter(|p| !used.contains(p) && !taken.contains(p)).collect() } else { Vec::new() };
    let result = result_mapping(&old, &new);
    let accounting = contract
        .required
        .iter()
        .map(|o| Kept {
            observation: o.clone(),
            how: if o == "result" {
                match result.kind {
                    ResultKind::Equal => "equality, as the contract says".into(),
                    ResultKind::Changed => "unresolved: how the results relate is a person's decision".into(),
                    _ => format!("{}, which compares every old value", result.candidates.first().map(|c| c.expression.as_str()).unwrap_or("equality")),
                }
            } else {
                "equality, as the contract says".into()
            },
        })
        .collect();
    let mut mapping = Mapping { before: symbol(bc, bm), after: symbol(ac, am), standalone, contract, inputs, free, result, accounting, unsupported, proposals: Vec::new() };
    let names: Vec<String> = new_inputs.into_iter().map(|(n, _)| n).collect();
    mapping.proposals = mapping.alternatives().into_iter().map(|(arguments, relation)| {
        let flags = mapping.flags(&arguments, relation.as_deref(), &names);
        Proposal { arguments, relation, flags }
    }).collect();
    Some(mapping)
}

/// Whether an expression mentions a path as a whole (`this.start` in `new B(this.start, n)`, not in `this.startAt`).
fn mentions(expression: &str, path: &str) -> bool {
    expression.match_indices(path).any(|(i, _)| {
        let before = expression[..i].chars().next_back();
        let after = expression[i + path.len()..].chars().next();
        !before.is_some_and(|c| c.is_alphanumeric() || c == '_' || c == '.') && !after.is_some_and(|c| c.is_alphanumeric() || c == '_' || c == '.')
    })
}

/// An old record built with its canonical constructor from the new inputs, component by component: one candidate
/// when every component has a leading candidate, else the combinations of their candidates, best first, or none
/// when a component has no candidate.
fn built(old: &Shape, leaves: &[Leaf], taken: &BTreeSet<String>) -> Vec<Choice> {
    let mut combos: Vec<(u32, Vec<String>, Vec<String>)> = vec![(0, Vec::new(), Vec::new())];
    for (name, t) in &old.members {
        let candidates = primitive_candidates(name, t, None, leaves, taken);
        if candidates.is_empty() {
            return Vec::new();
        }
        let options: Vec<&Choice> = if leads(&candidates) { vec![&candidates[0]] } else { candidates.iter().collect() };
        combos = combos
            .iter()
            .flat_map(|(score, args, why)| {
                options.iter().map(move |c| (score + c.score, args.iter().cloned().chain([c.expression.clone()]).collect(), why.iter().cloned().chain([format!("{name}: {}", c.why)]).collect()))
            })
            .take(ALTERNATIVES)
            .collect();
    }
    rank(
        combos
            .into_iter()
            .map(|(score, args, why)| Choice {
                expression: format!("new {}({})", old.simple, args.join(", ")),
                score: score / old.members.len().max(1) as u32,
                why: format!("the old record {} built with its constructor from the new inputs ({})", old.simple, why.join("; ")),
            })
            .collect(),
    )
}

/// The result relation, from the catalogue.
fn result_mapping(old: &Side, new: &Side) -> ResultMapping {
    let one = |kind, expression: String, why: &str| ResultMapping { kind, candidates: vec![Choice { expression, score: 3, why: why.into() }], inferred: true };
    let (a, b) = (&old.ret, &new.ret);
    let (sa, sb) = (shape(old.build, a), shape(new.build, b));
    if a == b && sa == sb {
        return ResultMapping { kind: ResultKind::Equal, candidates: Vec::new(), inferred: true };
    }
    if widens(a, b) {
        return one(ResultKind::Widened, "previous == result".into(), "the result widened: the old value compared with the new one");
    }
    match (&sa, &sb) {
        (None, Some(s)) if a.is_primitive() && s.record && s.members.len() == 1 && &s.members[0].1 == a => {
            return one(ResultKind::Converted, format!("previous == result.{}", s.members[0].0), "the value wrapped in a one-component record: compared with its component");
        }
        (Some(s), None) if b.is_primitive() && s.record && s.members.len() == 1 && &s.members[0].1 == b => {
            return one(ResultKind::Converted, format!("previous.{} == result", s.members[0].0), "the value unwrapped from a one-component record: its component compared with it");
        }
        (Some(s), Some(t)) if s.record && t.record && s.members.iter().all(|m| t.members.contains(m)) => {
            let holds = s.members.iter().map(|(c, _)| format!("previous.{c} == result.{c}")).collect::<Vec<_>>().join(" && ");
            let added: Vec<&str> = t.members.iter().filter(|m| !s.members.contains(m)).map(|(c, _)| c.as_str()).collect();
            let why = format!("the record result gained {}: each old component compared with the same-named new one", added.join(", "));
            return one(ResultKind::Components, holds, &why);
        }
        _ => {}
    }
    let candidates = if *a == Type::Boolean && integral(b) {
        ["<=", "<", "==", "!=", ">", ">="]
            .iter()
            .map(|op| Choice { expression: format!("previous == (result {op} 0)"), score: 1, why: format!("the old boolean against `result {op} 0`") })
            .collect()
    } else {
        Vec::new()
    };
    ResultMapping { kind: ResultKind::Changed, candidates, inferred: false }
}

fn find<'b>(build: &'b Build, wanted: &str) -> Option<(&'b ClassFile, &'b Method)> {
    build.methods().find(|(c, m)| symbol(c, m) == wanted)
}

/// The mappings of every method pair the report matches: the method that kept its signature, the leading candidate
/// of one that is gone, or every candidate where none leads. Constructors are left to field correspondence.
pub fn mappings(before: &Build, after: &Build, report: &MethodReport, contract: Option<&PreservationContract>) -> Vec<Mapping> {
    let mut out = Vec::new();
    for m in &report.methods {
        let Some(old) = find(before, &m.before) else { continue };
        if old.1.is_constructor() {
            continue;
        }
        let pairs = match (m.change, m.leading()) {
            (Change::Changed, _) | (_, Some(_)) => &m.candidates[..1],
            _ => &m.candidates[..],
        };
        for c in pairs {
            let Some(new) = find(after, &c.after) else { continue };
            let wanted = contract.filter(|k| k.subject == c.after || k.subject == m.before);
            out.extend(map(before, after, old, new, wanted));
        }
    }
    out
}

/// The mappings as hints: for each pair whose mapping isn't the tool's default, one correspondence per complete
/// proposal, ranked where there are several, each inferred, proposed and unchecked.
pub fn mapping_hints(mappings: &[Mapping]) -> Hints {
    let mut entries = Vec::new();
    for m in mappings.iter().filter(|m| !m.is_default()) {
        let alone = m.proposals.len() == 1;
        for (i, p) in m.proposals.iter().enumerate() {
            let correspondence = Correspondence::from_flags(&m.old_inputs(), Some(&p.arguments), p.relation.as_deref());
            let mut why: Vec<String> = Vec::new();
            if m.before != m.after {
                why.push(format!("against {}", m.before));
            }
            for (input, chosen) in m.inputs.iter().zip(&p.arguments) {
                let c = input.candidates.iter().find(|c| &c.expression == chosen).expect("chosen among them");
                let anchor = match input.anchor {
                    Anchor::Anchored => "anchored",
                    Anchor::Internal => "internal",
                };
                why.push(format!("{} ({anchor}): {}", input.old, c.why));
            }
            if let Some(r) = &p.relation {
                let c = m.result.candidates.iter().find(|c| &c.expression == r).expect("chosen among them");
                why.push(format!("result: {}{}", c.why, if m.result.inferred { "" } else { "; what the result means changed, so this is a person's decision" }));
            }
            if !m.free.is_empty() {
                why.push(format!("left free: {}", m.free.join(", ")));
            }
            if m.standalone {
                why.push("standalone: nothing external fixes what the inputs mean, so a proof would show that this relation holds, not that it is the one intended".into());
            }
            why.push(format!("flags: {}", serde_json::to_string(&p.flags).expect("serializable")));
            entries.push(Hint {
                subject: m.after.clone(),
                content: HintContent::Correspondence { correspondence },
                source: Source::Inferred,
                intent: Intent::Proposed,
                evidence: Evidence::Unchecked,
                rank: (!alone).then_some(i as u32 + 1),
                why,
            });
        }
    }
    Hints { version: HINTS_VERSION, entries }
}

/// The mappings as text, one pair per paragraph.
pub fn render(mappings: &[Mapping]) -> String {
    let mut out = String::new();
    for m in mappings {
        out.push_str(&format!("mapping   {} -> {}{}\n", m.before, m.after, if m.standalone { " (standalone: no external anchor)" } else { "" }));
        for i in &m.inputs {
            let anchor = match i.anchor {
                Anchor::Anchored => "anchored",
                Anchor::Internal => "internal",
            };
            match (i.candidates.as_slice(), i.leads) {
                ([], _) => out.push_str(&format!("  {} ({anchor}): no candidate\n", i.old)),
                ([c, ..], true) => out.push_str(&format!("  {} ({anchor}) = {}: {}\n", i.old, c.expression, c.why)),
                (cs, false) => out.push_str(&format!("  {} ({anchor}), a question: {}\n", i.old, cs.iter().map(|c| c.expression.as_str()).collect::<Vec<_>>().join(" | "))),
            }
        }
        if !m.free.is_empty() {
            out.push_str(&format!("  left free: {}\n", m.free.join(", ")));
        }
        let r = &m.result;
        match (r.kind, r.candidates.as_slice()) {
            (ResultKind::Equal, _) => out.push_str("  result: equal, as the contract says\n"),
            (ResultKind::Changed, []) => out.push_str("  result: changed, and no catalogue relation fits: a person's decision\n"),
            (ResultKind::Changed, cs) => out.push_str(&format!("  result: changed, a person's decision: {}\n", cs.iter().map(|c| c.expression.as_str()).collect::<Vec<_>>().join(" | "))),
            (_, cs) => out.push_str(&format!("  result: {}: {}\n", cs[0].expression, cs[0].why)),
        }
        for u in &m.unsupported {
            out.push_str(&format!("  not related here: {u}\n"));
        }
    }
    out
}
