//! The heap stream's interface (`llm-dlc/loops/foundations-heap.md`): a regression check over object inputs, under a
//! [`CanonicalClaim`]'s domain, observations and correspondence. Owned by that stream; until it does its part, every
//! call returns [`Unsupported`] naming it.

use std::path::Path;

use super::{Accounted, CanonicalClaim, Correspondence, Observation, ObservationState, Outcome, Part, Unsupported, Verdict};
use crate::harness::{field_steps, Computed, Corresponds, FieldEquation, FieldRelation, IdentityRelation, Piece, Read, RecordType, RelationRead, Source};
use crate::classfile::Type;

/// How long one check may take: the joint example's are small.
const DEADLINE_SECONDS: u64 = 300;

/// Checks the claim of `subject` (`pkg.Class#method`) between the classes under `before` and `after`, each a class
/// directory or jar. A refuted [`Outcome`] carries a witness that replays on the JVM with the objects' identities.
///
/// The check is the native regression check (`jvmcontract regress --engine native`, strict) under the claim's
/// bounds and correspondence: an object parameter made by its constructor in both versions, the previous version's
/// made from the new one's leaves as the correspondence's input equations say where the two shapes differ (step H5's
/// narrow case), and its results and objects compared under the same equations. Each required observation is
/// accounted for: preserved by a proof that compared it; refuted where the replayed witness differs in it; and
/// otherwise unresolved, as is every observation the check does not compare, so that none leaves the count. A
/// witness that differs only in observations the claim does not require refutes nothing, and the result is
/// unresolved, as it is when no JVM has run the witness too (step H4). A required observation under one of the
/// correspondence's output relations (the result's, a parameter's field's as the call leaves it, or an identity relation's) is compared
/// under it rather than for equality, so it stays unresolved until a person approves the change in the contract. An input equation that computes a field of an input the contract anchors
/// (identity), rather than naming the field that holds it, is refused unless a person stated it in the input's
/// derivation ([`anchored`]). A construction that needs more input objects than a version's bound leaves the result unresolved
/// rather than proving something outside the claim, and so does code that may make more objects in one call than a
/// version's allocation bound ([`allocations`]). A contract input that isn't one of the subject's parameters
/// ([`foreign_inputs`]) is refused, since the claim would anchor nothing the method receives. So is a domain whose
/// constructors or classes aren't the ones the check makes its inputs with, or that is made otherwise than by
/// constructors ([`made_with`], the domain gate), before any proof. Claims about effects (an environment model) are the
/// observations stream's, and refused.
pub fn check(claim: &CanonicalClaim, before: &Path, after: &Path) -> Result<Outcome, Unsupported> {
    check_with(claim, before, after, None, &mut Reused::default())
}

/// What a check under the proof cache reused, from [`check_with`].
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Reused {
    /// The claim key the check was prepared under, when the cache was used and the claim was cacheable.
    pub key: Option<super::cache::ClaimKey>,
    /// The stored result was the result: the same claim key, from an earlier run.
    pub exact: Option<super::cache::Reuse>,
    /// Changed pure helpers proved equivalent by a check of their own and taken as one function in both versions
    /// in this check, each with its proof's claim key.
    pub callees: Vec<super::cache::Reuse>,
}

/// [`check`], under the proof cache in `cache` when one is given (`equivalence --cache`): the stored result of the
/// same claim is the result, a verified or refuted one is stored, and each changed pure helper is proved first and
/// shared. What was reused is written to `reused`.
pub fn check_with(claim: &CanonicalClaim, before: &Path, after: &Path, cache: Option<&Path>, reused: &mut Reused) -> Result<Outcome, Unsupported> {
    let unsupported = |what: String| Unsupported::new(Part::Heap, what);
    let subject = &claim.contract.subject;
    if !subject.contains('#') {
        return Err(unsupported(format!("{subject} is not a method, pkg.Class#method: an entry point's claim is the observations stream's")));
    }
    if claim.environment.is_some() {
        return Err(unsupported("a claim with an environment model of boundary calls is the observations stream's".into()));
    }
    if let Some(o) = claim.observations.iter().find(|o| matches!(o, Observation::Effect { .. } | Observation::Status)) {
        return Err(unsupported(format!("the observation {} is an entry point's", o.id())));
    }
    let strict = match claim.tools.checker.as_str() {
        "native strict" | "native" => true,
        other => return Err(unsupported(format!("the checker {other}: the heap stream's checks run on the own checker, strict"))),
    };
    if let Some(gap) = claim.correspondence.as_ref().and_then(|c| anchored(c, &claim.contract)) {
        return Err(unsupported(gap));
    }
    // The domain gate: a domain made otherwise than by constructors is refused here, and one whose constructors or
    // classes aren't the check's by `equivalence::run` once its layout is built ([`made_with`]), before any proof.
    if let Some(d) = claim.domain.as_ref().filter(|d| !matches!(d.made_by, super::Construction::Constructors { .. })) {
        let part = if matches!(d.made_by, super::Construction::Planned { .. }) { Part::Objects } else { Part::Heap };
        return Err(Unsupported::new(part, unbuilt(&d.made_by)));
    }
    let mut options = crate::equivalence::Options::new(before, after, subject);
    options.engine = crate::Engine::Native;
    options.gaps = if strict { crate::bmc::gaps::GapMode::Strict } else { crate::bmc::gaps::GapMode::Assume };
    options.unwind = claim.bounds.unwind;
    options.max_array_length = claim.bounds.max_array_length;
    options.timeout_seconds = DEADLINE_SECONDS;
    options.correspondence = claim.correspondence.clone();
    options.cache = cache.map(Path::to_path_buf);
    // The domain's parameters that may be null or one object (step H2); a field of an input object that may be
    // null or shared is not made yet.
    if let Some(d) = &claim.domain {
        if let Some(path) = d.nullable.iter().chain(d.may_alias.iter().flat_map(|(a, b)| [a, b])).find(|p| p.contains('.')) {
            return Err(unsupported(format!("the domain's {path} is a field path: only parameters may be null or one object yet, a field being whatever its object's constructor makes it")));
        }
        options.nullable = d.nullable.clone();
        options.may_alias = d.may_alias.clone();
        options.object_domain = Some(d.clone());
    }
    let required = &claim.contract.required;
    let unresolved_all = |domain: String, problem: String| Outcome {
        verdict: Verdict::Unresolved,
        domain,
        accounting: required.iter().map(|r| Accounted { observation: r.clone(), state: ObservationState::Unresolved }).collect(),
        witness: None,
        problem: Some(problem),
    };
    let mark = crate::proof_cache::key_mark();
    let checked = match crate::equivalence::run(&options) {
        Ok(o) => o,
        Err(e) => return Ok(unresolved_all(String::new(), format!("the check could not run: {e}"))),
    };
    reused.key = cache.and_then(|_| crate::proof_cache::key_since(subject, mark));
    reused.exact = checked.reuse.clone().filter(|r| matches!(r, super::cache::Reuse::Exact { .. }));
    reused.callees = checked.stated.iter().flat_map(|s| &s.assumptions).filter(|a| a.basis == crate::statement::Basis::Proved).filter_map(|a| {
        let key = a.id.clone()?;
        let callee = a.text.split('(').next()?.trim().to_string();
        Some(super::cache::Reuse::Callee { callee, key: super::cache::ClaimKey(key) })
    }).collect();
    let domain = checked.domain.clone().unwrap_or_default();
    let Some(stated) = &checked.stated else {
        // Refused before a statement: a named gap of the check.
        return Err(unsupported(checked.problem.unwrap_or_else(|| "refused".into())));
    };
    if let Some(gap) = foreign_inputs(&claim.contract, &stated.domain.parameters) {
        return Err(unsupported(gap));
    }
    if let (Some(bounds), Some((old, new))) = (claim.domain.as_ref().map(|d| &d.bounds), stated.domain.input_objects) {
        for (version, needed, bound) in [("previous", old, bounds.before.input_objects), ("new", new, bounds.after.input_objects)] {
            if needed > bound {
                return Ok(unresolved_all(domain, format!("the {version} version's inputs are made of {needed} objects, more than the claim's bound of {bound}: the check would be about inputs outside the claim")));
            }
        }
    }
    // The allocation bound, against what each version's code makes in one call: the own checker follows every
    // allocation within the unwinding bound, so a claim that bounds them is checked here, not by the proof.
    if let Some(bounds) = claim.domain.as_ref().map(|d| &d.bounds) {
        for (version, build, bound) in [("previous", before, bounds.before.allocations), ("new", after, bounds.after.allocations)] {
            let problem = match allocations(build, subject) {
                Ok(Some(made)) if made <= bound => continue,
                Ok(Some(made)) => format!("the {version} version's code may make {made} objects in one call, more than the claim's allocation bound of {bound}: the check would be about calls outside the claim"),
                Ok(None) => format!("the {version} version's code makes objects in a loop or a recursion, which no number bounds, and the claim's allocation bound is {bound}: the check would be about calls outside the claim"),
                Err(e) => format!("the {version} version's allocations could not be counted against the claim's allocation bound of {bound}: {e}"),
            };
            return Ok(unresolved_all(domain, problem));
        }
    }
    let compared = compared_observations(stated);
    let is_compared = |id: &str| compared.iter().any(|c| same_id(c, id));
    // A required observation an output relation compares in place of equality is held to something else than the
    // contract says: only a person's approved change makes that the claim. Without one it is unresolved, whatever
    // the check finds, so that no relation can make a difference disappear (`old.result == new.result - 1`) or
    // stand in for one.
    // A relation for a field path (H5's rest) bears on every required observation of a path at or under it, or
    // above it, and is approved by a change of its path or one above it.
    let related: Vec<&str> = claim.correspondence.iter().flat_map(|c| &c.outputs).map(|r| r.observation.as_str()).collect();
    let approved = |relation: &str| claim.contract.approved_changes.iter().any(|a| within(relation, &a.observation));
    let unapproved = |id: &str| related.iter().any(|r| overlaps(r, id) && !approved(r));
    match checked.verdict {
        crate::Verdict::Verified if checked.vacuous.is_some() => Ok(unresolved_all(domain, format!("vacuous: {}", checked.vacuous.unwrap_or_default()))),
        crate::Verdict::Verified => {
            let state = |r: &str| match () {
                _ if !is_compared(r) || unapproved(r) => ObservationState::Unresolved,
                _ if related.iter().any(|x| overlaps(x, r)) => ObservationState::ChangedWithApproval,
                _ => ObservationState::Preserved,
            };
            let accounting: Vec<Accounted> = required.iter().map(|r| Accounted { observation: r.clone(), state: state(r) }).collect();
            let unrelated: Vec<&str> = accounting.iter().filter(|a| a.state == ObservationState::Unresolved && !unapproved(&a.observation)).map(|a| a.observation.as_str()).collect();
            let relating: Vec<&str> = required.iter().map(String::as_str).filter(|r| unapproved(r)).collect();
            let mut problems = Vec::new();
            if !unrelated.is_empty() {
                problems.push(format!("the check does not compare {}", unrelated.join(", ")));
            }
            if !relating.is_empty() {
                problems.push(format!("the correspondence's output relation compares {} in place of equality, which the preservation contract requires and no person approved as changed", relating.join(", ")));
            }
            let (verdict, problem) = if problems.is_empty() { (Verdict::Verified, None) } else { (Verdict::Unresolved, Some(problems.join("; "))) };
            Ok(Outcome { verdict, domain, accounting, witness: None, problem })
        }
        crate::Verdict::Violation => {
            let Some(cx) = &checked.counterexample else { return Ok(unresolved_all(domain, "a refutation without a counterexample".into())) };
            let witness = format!("{}: before, {}; after, {}", cx.input, cx.before, cx.after);
            // Over objects, a witness the interpreter replays is reported once a JVM has run it too (step H4).
            if cx.jvm.is_none() {
                let how = checked.proof.clone().unwrap_or_default();
                return Ok(Outcome { verdict: Verdict::Unresolved, domain, accounting: required.iter().map(|r| Accounted { observation: r.clone(), state: ObservationState::Unresolved }).collect(), witness: Some(witness), problem: Some(format!("the witness replays in the interpreter but was not confirmed on a JVM ({how})")) });
            }
            let refuted: Vec<&String> = required.iter().filter(|r| cx.differs.iter().any(|d| within(d, r)) && !unapproved(r)).collect();
            let accounting: Vec<Accounted> = required.iter().map(|r| Accounted { observation: r.clone(), state: if refuted.contains(&r) { ObservationState::Refuted } else { ObservationState::Unresolved } }).collect();
            if refuted.is_empty() {
                if let Some(r) = required.iter().find(|r| unapproved(r) && cx.differs.iter().any(|d| overlaps(d, r))) {
                    return Ok(Outcome { verdict: Verdict::Unresolved, domain, accounting, witness: Some(witness), problem: Some(format!("the versions differ under the correspondence's output relation for {r}, which takes the place of the equality the preservation contract requires and which no person approved as changed")) });
                }
                let differs = if cx.differs.is_empty() { "observations the check does not tell apart".to_string() } else { cx.differs.join(", ") };
                return Ok(Outcome { verdict: Verdict::Unresolved, domain, accounting, witness: Some(witness), problem: Some(format!("the versions differ only in {differs}, which the claim does not require")) });
            }
            Ok(Outcome { verdict: Verdict::Refuted, domain, accounting, witness: Some(witness), problem: None })
        }
        crate::Verdict::Unverifiable => Ok(unresolved_all(domain, checked.problem.unwrap_or_else(|| "no verdict".into()))),
    }
}

/// Why the inputs `layout` makes are not the ones `domain` says, if they aren't (the domain gate, Phase 0 step 1 of
/// `llm-dlc/loops/application-core.md`). `equivalence::run` asks it once the layout is built, before any proof or
/// cache lookup, so that a claim about other inputs never runs as the constructor domain the check makes.
///
/// The domain's constructors are compared with the ones the harness calls, as a set for each version, and its
/// classes with the classes they make, over both versions. A constructor is written in the claim as
/// `before: shop.Quote(long cents, int quantity)`: the version, then the class and its parameters' types and names,
/// spacing aside. Each side must name exactly what the other does. A constructor the domain names and the check
/// doesn't call (a factory, another constructor) would leave its inputs out; one the check calls and the domain
/// doesn't name would bring others in. A domain not made by constructors is refused: no other construction is
/// built.
pub(crate) fn made_with(layout: &crate::harness::Layout, domain: &super::ObjectDomain) -> Option<String> {
    let calls = match &domain.made_by {
        super::Construction::Constructors { calls } => calls,
        other => return Some(unbuilt(other)),
    };
    let squeeze = |c: &str| {
        let spaced = c.split_whitespace().collect::<Vec<_>>().join(" ");
        spaced.replace(" (", "(").replace("( ", "(").replace(" )", ")").replace(" ,", ",").replace(", ", ",")
    };
    if let Some(c) = calls.iter().find(|c| !(c.trim_start().starts_with("before:") || c.trim_start().starts_with("after:"))) {
        return Some(format!("the domain's constructor {c} names no version: a claim writes each one under before: or after:, the version that makes its objects with it"));
    }
    let (made, classes) = layout.made_with();
    let claimed: Vec<String> = calls.iter().map(|c| squeeze(c)).collect();
    let makes: Vec<String> = made.iter().map(|c| squeeze(c)).collect();
    let mut problems = Vec::new();
    let unnamed: Vec<&String> = made.iter().zip(&makes).filter(|(_, m)| !claimed.contains(m)).map(|(c, _)| c).collect();
    if !unnamed.is_empty() {
        problems.push(format!("the check calls {}, which the domain doesn't name", unnamed.iter().map(|c| c.as_str()).collect::<Vec<_>>().join("; ")));
    }
    let uncalled: Vec<&String> = calls.iter().zip(&claimed).filter(|(_, c)| !makes.contains(c)).map(|(c, _)| c).collect();
    if !uncalled.is_empty() {
        problems.push(format!("the domain names {}, which the check doesn't call (only the constructors a parameter's class has are made yet: no factory, and no choice among constructors)", uncalled.iter().map(|c| c.trim()).collect::<Vec<_>>().join("; ")));
    }
    let foreign: Vec<&String> = classes.iter().filter(|k| !domain.classes.iter().any(|d| d.trim() == k.as_str())).collect();
    if !foreign.is_empty() {
        problems.push(format!("the check makes objects of {}, a class the domain doesn't name", foreign.iter().map(|k| k.as_str()).collect::<Vec<_>>().join(", ")));
    }
    let absent: Vec<&String> = domain.classes.iter().filter(|d| !classes.iter().any(|k| k == d.trim())).collect();
    if !absent.is_empty() {
        problems.push(format!("the domain names {}, a class the check makes no object of", absent.iter().map(|k| k.trim()).collect::<Vec<_>>().join(", ")));
    }
    if problems.is_empty() {
        return None;
    }
    let shown = |v: &[String]| if v.is_empty() { "nothing".to_string() } else { v.join("; ") };
    Some(format!(
        "the claim's domain says its inputs are made with {} (classes {}), and the check makes them with {} (classes {}): {}. A check of other inputs than the claim's would be about inputs outside it",
        shown(calls),
        shown(&domain.classes),
        shown(&made),
        shown(&classes),
        problems.join("; ")
    ))
}

/// The refusal of a domain made otherwise than by constructors, which no check builds yet.
fn unbuilt(made_by: &super::Construction) -> String {
    match made_by {
        super::Construction::Constructors { .. } => unreachable!("constructors are built"),
        super::Construction::FieldByField => "the domain is made field by field, which includes states no constructor makes; only a domain made by constructors is built, and a check over constructor-made objects would be about other inputs than the claim's".into(),
        super::Construction::Planned { .. } => "the domain is made by a construction plan, which the objects stream builds (llm-dlc/loops/application-core-objects.md); until it does, a check over the constructor domain would be about other inputs than the claim's".into(),
        super::Construction::Invariant { invariants } => format!("the domain is made of the states that satisfy the invariant{} {}, which no check builds; only a domain made by constructors is, and a check over constructor-made objects would be about other inputs than the claim's", if invariants.len() == 1 { "" } else { "s" }, invariants.join("; ")),
    }
}

/// The first input equation that computes a field of an input the preservation contract anchors, named: what an
/// external input means is fixed, both versions receiving the same one, and an equation that computes the previous
/// version's field from the new one's (`old.q.cents == new.q.amount.cents + 1`) may change what it means and so
/// hide a changed result. An equation between two paths only says where each version holds the same value. Under a
/// derivation a person stated, an equation that is one of its conjuncts is theirs, and stands; one about an input
/// the contract doesn't name (an internal one) is the correspondence's to state.
fn anchored(correspondence: &Correspondence, contract: &super::PreservationContract) -> Option<String> {
    let squeeze = |t: &str| t.chars().filter(|c| !c.is_whitespace()).collect::<String>();
    for e in correspondence.inputs.iter().filter(|e| is_computed(e)) {
        let Some((root, path)) = path_of(&e.old, "old") else { continue };
        let Some(input) = contract.inputs.iter().find(|i| i.name == root) else { continue };
        let text = format!("{} == {}", e.old.trim(), e.new.trim());
        match &input.derivation {
            super::Derivation::Identity => {
                return Some(format!("the correspondence's input equation {text} computes the previous version's {root}.{path} from the new one's, and the preservation contract anchors {root} (its derivation is identity): both versions receive the same {root}, and an equation that computes it may change what it means, so only equations between two paths relate an anchored input, or a derivation a person states"));
            }
            super::Derivation::Stated { expression } => {
                if !expression.split("&&").any(|part| squeeze(part) == squeeze(&text)) {
                    return Some(format!("the correspondence's input equation {text} computes the previous version's {root}.{path} from the new one's, which the derivation a person stated for {root} ({expression}) does not say: only an equation between two paths, or one the stated derivation has, relates an anchored input"));
                }
            }
        }
    }
    None
}

/// The contract's inputs that aren't the subject's own, named with the parameters it takes: a claim is about one
/// method's inputs, and the kernel claim's `q: shop.Quote` checked against `discount(long gross, int quantity)`
/// anchors nothing the method receives. Every external input must be one of the parameters (or the receiver,
/// `this`) by name and type; a parameter no input names is the correspondence's, as for a standalone pair.
fn foreign_inputs(contract: &super::PreservationContract, parameters: &[crate::statement::Parameter]) -> Option<String> {
    let foreign: Vec<String> = contract
        .inputs
        .iter()
        .filter(|i| !parameters.iter().any(|p| p.name == i.name && p.ty == i.ty))
        .map(|i| format!("{}: {}", i.name, i.ty))
        .collect();
    if foreign.is_empty() {
        return None;
    }
    let takes: Vec<String> = parameters.iter().map(|p| format!("{}: {}", p.name, p.ty)).collect();
    let takes = if takes.is_empty() { "no parameters".to_string() } else { takes.join(", ") };
    Some(format!(
        "the preservation contract's input{} {} {} not among {}'s parameters ({takes}): a claim anchors the inputs its subject receives",
        if foreign.len() == 1 { "" } else { "s" },
        foreign.join(", "),
        if foreign.len() == 1 { "is" } else { "are" },
        contract.subject
    ))
}

/// How many methods [`allocations`] follows before it gives up: the subjects of a claim with a domain are small.
const ALLOCATION_METHODS: usize = 10_000;

/// An upper bound on the objects one call of `subject` (`pkg.Class#method`) makes in the build at `build`, for the
/// claim's allocation bound ([`super::ObjectBounds::allocations`]): each `new`, array instruction and
/// `invokedynamic` (a lambda, a concatenated string) of the application code the call runs, once for each way a call
/// reaches it, taking the most of the subject's overloads and of the targets a virtual call may dispatch to. Every
/// one is counted, whichever branch it is on, so the bound is over every path at once. What a JDK method makes
/// (application code it calls back included), an exception the JVM throws, and what a class initializer makes are
/// not counted. `None` when something is made in a loop or a recursion, where no number the code states bounds it.
fn allocations(build: &Path, subject: &str) -> Result<Option<u32>, String> {
    let (class, name) = subject.split_once('#').ok_or_else(|| format!("{subject} is not pkg.Class#method"))?;
    let cp = crate::closure::build_class_path(&[build]).map_err(|e| e.to_string())?;
    let owner = class.replace('.', "/");
    let file = cp.application(&owner).map_err(|e| e.to_string())?.ok_or_else(|| format!("no class {class} in {}", build.display()))?;
    let mut count = Allocations { cp: &cp, classes: None, stack: Vec::new(), memo: std::collections::BTreeMap::new(), visits: 0, error: None };
    let mut most = Some(0);
    for m in file.methods.iter().filter(|m| m.name == name) {
        most = most_of(most, count.method(&crate::classfile::MemberRef::new(&owner, name, &m.descriptor)).0);
    }
    match count.error {
        Some(e) => Err(e),
        None => Ok(most),
    }
}

fn most_of(a: Option<u32>, b: Option<u32>) -> Option<u32> {
    Some(a?.max(b?))
}

/// The walk of [`allocations`]: each method's bound, by the method that declares it, once it is final.
struct Allocations<'a> {
    cp: &'a crate::classpath::ClassPath,
    classes: Option<std::collections::BTreeMap<String, std::rc::Rc<crate::classfile::ClassFile>>>,
    /// The methods being counted, outermost first: a call to one of them is a recursion.
    stack: Vec<crate::classfile::MemberRef>,
    memo: std::collections::BTreeMap<crate::classfile::MemberRef, Option<u32>>,
    visits: usize,
    error: Option<String>,
}

impl Allocations<'_> {
    /// The bound of one call of `reference`, and the outermost frame of the stack a recursion through it reaches,
    /// while that frame is still being counted. A method on a recursion that makes anything has no bound; one that
    /// makes nothing is 0, and is kept once the recursion's outermost frame is done.
    fn method(&mut self, reference: &crate::classfile::MemberRef) -> (Option<u32>, Option<usize>) {
        use crate::classfile::{Insn, MemberRef};
        let Some((class, method)) = self.cp.find_method(&reference.owner, &reference.name, &reference.descriptor) else { return (Some(0), None) };
        if !self.cp.is_application(&class.name) {
            return (Some(0), None);
        }
        let declared = MemberRef::new(&class.name, &reference.name, &reference.descriptor);
        if let Some(bound) = self.memo.get(&declared) {
            return (*bound, None);
        }
        if let Some(frame) = self.stack.iter().position(|m| *m == declared) {
            return (Some(0), Some(frame));
        }
        self.visits += 1;
        if self.visits > ALLOCATION_METHODS || self.error.is_some() {
            self.error.get_or_insert_with(|| format!("more than {ALLOCATION_METHODS} methods to follow"));
            return (None, None);
        }
        let Some(code) = &method.code else { return (Some(0), None) };
        let insns = match code.instructions() {
            Ok(i) => i,
            Err(e) => {
                self.error = Some(format!("{}'s code can't be read: {e}", crate::closure::method_id(&declared)));
                return (None, None);
            }
        };
        // A branch back to an earlier offset closes a loop over the offsets between.
        let loops: Vec<(u32, u32)> = insns.iter().flat_map(|(at, insn)| insn.targets().into_iter().filter(|t| t <= at).map(|t| (t, *at)).collect::<Vec<_>>()).collect();
        let index = self.stack.len();
        self.stack.push(declared.clone());
        let (mut total, mut reaches) = (Some(0u32), None::<usize>);
        for (at, insn) in &insns {
            let (made, frame) = match insn {
                Insn::New(_) | Insn::NewArray(_) | Insn::ANewArray(_) | Insn::MultiANewArray(..) | Insn::InvokeDynamic(_) => (Some(1), None),
                Insn::InvokeStatic(i) | Insn::InvokeSpecial(i) => match class.pool.member(*i) {
                    Ok(callee) if self.cp.is_application(&callee.owner) => self.method(&callee),
                    _ => (Some(0), None),
                },
                Insn::InvokeVirtual(i) | Insn::InvokeInterface(i) => match class.pool.member(*i) {
                    Ok(callee) if !callee.owner.starts_with('[') => {
                        let mut most = (Some(0), None::<usize>);
                        for target in self.dispatch_targets(&callee) {
                            let (made, frame) = self.method(&MemberRef::new(&target, &callee.name, &callee.descriptor));
                            most = (most_of(most.0, made), [most.1, frame].into_iter().flatten().min());
                        }
                        most
                    }
                    _ => (Some(0), None),
                },
                _ => (Some(0), None),
            };
            reaches = [reaches, frame].into_iter().flatten().min();
            total = match made {
                Some(0) => total,
                Some(n) if !loops.iter().any(|(from, to)| from <= at && at <= to) => total.map(|t| t.saturating_add(n)),
                _ => None,
            };
        }
        self.stack.pop();
        let recursive = reaches.is_some_and(|frame| frame <= index);
        if recursive && total != Some(0) {
            total = None;
        }
        match reaches {
            // The recursion goes on above this frame: what this one makes isn't final until that frame is done.
            Some(frame) if frame < index => (total, Some(frame)),
            _ => {
                self.memo.insert(declared, total);
                (total, None)
            }
        }
    }

    /// The application classes whose method a virtual or interface call of `callee` may run, as
    /// [`crate::closure`] follows them.
    fn dispatch_targets(&mut self, callee: &crate::classfile::MemberRef) -> Vec<String> {
        let cp = self.cp;
        let classes = self.classes.get_or_insert_with(|| cp.application_classes().unwrap_or_default());
        let owners = std::iter::once(callee.owner.clone()).chain(classes.iter().filter(|(_, c)| !c.is_interface() && !c.is_abstract()).map(|(n, _)| n.clone()));
        let mut targets: Vec<String> = owners
            .filter(|o| *o == callee.owner || cp.is_subtype(o, &callee.owner))
            .filter_map(|o| cp.find_method(&o, &callee.name, &callee.descriptor))
            .filter(|(declaring, m)| !m.is_abstract() && cp.is_application(&declaring.name))
            .map(|(declaring, _)| declaring.name.clone())
            .collect();
        targets.sort();
        targets.dedup();
        targets
    }
}

/// Whether two observation ids name the same observation: an identity relation either way round.
fn same_id(a: &str, b: &str) -> bool {
    if a == b {
        return true;
    }
    let swapped = |id: &str| id.strip_prefix("identity:").and_then(|r| r.split_once("==")).map(|(x, y)| format!("identity:{y}=={x}"));
    swapped(a).is_some_and(|s| s == b)
}

/// Whether the observation `a` is `b` or, for field paths, under it: `field:q.amount.cents` within `field:q`.
fn within(a: &str, b: &str) -> bool {
    same_id(a, b) || matches!((a.strip_prefix("field:"), b.strip_prefix("field:")), (Some(x), Some(y)) if under(x, y))
}

/// Whether two observations bear on each other: one within the other.
fn overlaps(a: &str, b: &str) -> bool {
    within(a, b) || within(b, a)
}

/// The observations a regression statement compares, by id: the result and the exception always (a void method's
/// result is nothing, alike in both), each array parameter, each object parameter's fields by path (`field:q.cents`,
/// under a correspondence the previous version's paths), and each identity relation, under an output relation or not.
fn compared_observations(stated: &crate::statement::Statement) -> Vec<String> {
    let o = &stated.observations;
    let mut out = vec![Observation::Result.id(), Observation::Exception.id()];
    out.extend(o.arrays.iter().map(|a| Observation::ArrayParameter { parameter: a.clone() }.id()));
    for object in &o.objects {
        let Some((name, rest)) = object.split_once(": ") else { continue };
        let paths: Vec<String> = match rest.strip_prefix("under the correspondence") {
            // The equations compared, then each path an output relation compares (`; q.cents under the output
            // relation …`), which counts as compared: how it is held to its relation is the accounting's.
            Some(compared) => {
                let mut parts = compared.split("; ");
                let equations = parts.next().unwrap_or_default().strip_prefix(", ").unwrap_or_default();
                let mut paths: Vec<String> = equations.split(", ").filter_map(|e| e.split(" == ").next()?.strip_prefix(&format!("old.{name}.")).map(str::to_string)).collect();
                paths.extend(parts.filter_map(|p| p.split_once(" under the output relation ")).filter_map(|(path, _)| path.strip_prefix(&format!("{name}.")).map(str::to_string)));
                paths
            }
            // The paths compared, then under a relation for some of them (H5's rest) each path it compares:
            // `price.cents; l.quantity under the output relation …`.
            None => rest
                .split("; ")
                .flat_map(|part| match part.split_once(" under the output relation ") {
                    Some((path, _)) => path.strip_prefix(&format!("{name}.")).map(str::to_string).into_iter().collect::<Vec<_>>(),
                    None => part.split(", ").filter(|p| !p.is_empty()).map(str::to_string).collect(),
                })
                .collect(),
        };
        out.extend(paths.iter().map(|p| Observation::FieldPath { path: format!("{name}.{p}") }.id()));
        out.push(Observation::FieldPath { path: name.to_string() }.id());
    }
    // `result == q`, or `result == q, under the output relation …`, which counts as compared as a field's does.
    let pair = |i: &str| i.split(", under the output relation ").next().unwrap_or(i).to_string();
    out.extend(o.identities.iter().map(|i| pair(i)).filter_map(|i| i.split_once(" == ").map(|(x, y)| Observation::Identity { left: x.into(), right: y.into() }.id())));
    out
}

/// One side of an equation as a root and a field path: `old.q.amount.cents` under `old` is `("q", "amount.cents")`;
/// none when it is not a path of identifiers under `side.`.
fn path_of<'a>(text: &'a str, side: &str) -> Option<(&'a str, &'a str)> {
    let rest = text.trim().strip_prefix(side)?.strip_prefix('.')?;
    let identifier = |w: &str| !w.is_empty() && w.chars().next().is_some_and(|c| c.is_alphabetic() || c == '_') && w.chars().all(|c| c.is_alphanumeric() || c == '_');
    if !rest.split('.').all(identifier) {
        return None;
    }
    Some(rest.split_once('.').unwrap_or((rest, "")))
}

/// The roots the correspondence's input equations are about, `q` for `old.q.cents == new.q.amount.cents`, and
/// whether the equation relates the two as a whole, with each equation not supported named as a gap. The previous
/// version's side is a field path; the new one's a field path, or an expression over field paths of object
/// parameters and the new version's primitive parameters (H5's rest), `new.p.dollars * 100 + new.p.cents`,
/// `new.l.price * new.n` or `new.l.price * new.o.count`. The new root is none for an expression that reads no field,
/// `new.n * 100`, which is about the parameter in the previous one's place, and so is one over several objects'
/// fields none of which has the previous root's name.
pub(crate) fn roots(correspondence: &Correspondence) -> Result<Vec<(String, Option<String>, bool)>, String> {
    let mut out = Vec::new();
    for e in &correspondence.inputs {
        let Some((old_root, old_path)) = path_of(&e.old, "old") else {
            return Err(format!("the correspondence's input equation {} == {} does not have a field path of the previous version's input on its old side: only equations that give one, from a path or an expression over the new version's, are supported yet", e.old, e.new));
        };
        match new_path(e) {
            Some((new_root, new_path)) => out.push((old_root.to_string(), Some(new_root.to_string()), old_path.is_empty() && new_path.is_empty())),
            None => out.push((old_root.to_string(), expression_root(e)?, false)),
        }
    }
    Ok(out)
}

/// The new side of an input equation as a root and a field path, where it is one: `new.q.amount.cents`, and
/// `new.q` for the previous version's `old.q`. A field given by a parameter as a whole, `old.q.count == new.n`, is
/// an expression that reads it.
fn new_path(e: &super::Equation) -> Option<(&str, &str)> {
    let old_whole = path_of(&e.old, "old").is_some_and(|(_, path)| path.is_empty());
    path_of(&e.new, "new").filter(|(_, path)| old_whole || !path.is_empty())
}

/// The one parameter whose fields an expression on the new side reads, `p` for `new.p.dollars * 100 + new.p.cents`
/// and for `new.p.price * new.n`, where `n` is a parameter it reads as a whole (a primitive, [`relate`] checks);
/// none where it reads parameters only as a whole. Of several whose fields it reads, `new.l.price * new.o.count`, the
/// one of the previous version's root's name, else none: the parameter in the previous one's place, [`relate`]
/// reading the others as the arguments they were made from.
fn expression_root(e: &super::Equation) -> Result<Option<String>, String> {
    let pieces = new_pieces(&e.new).map_err(|why| format!("the correspondence's input equation {} == {} {why}", e.old, e.new))?;
    let mut roots: Vec<&str> = pieces.iter().filter_map(|p| p.as_ref().err().filter(|(_, path)| !path.is_empty()).map(|(root, _)| root.as_str())).collect();
    roots.sort();
    roots.dedup();
    let reads = pieces.iter().any(Result::is_err);
    let old_root = path_of(&e.old, "old").map(|(root, _)| root);
    match roots.as_slice() {
        [root] => Ok(Some(root.to_string())),
        [] if reads => Ok(None),
        [] => Err(format!("the correspondence's input equation {} == {} reads nothing of the new version's input: an equation gives the previous version's field from the new one's", e.old, e.new)),
        // Several objects' fields (H5's rest): about the parameter of the previous one's name if it reads it, or
        // else the one in its place, the others read as the arguments they were made from.
        several => Ok(old_root.filter(|r| several.contains(r)).map(str::to_string)),
    }
}

/// The words refusing a read of the parameter `root` as a whole, `old.q` or `new.q`.
fn whole_read(previous: bool, root: &str) -> String {
    format!("reads {}.{root} as a whole: only its primitive field paths are read", if previous { "old" } else { "new" })
}

/// The new side of an input equation as pieces: text as written (`Ok`), and each read of a field path of the new
/// version's input (`Err((root, path))`, `new.p.dollars` as `("p", "dollars")`), or of a parameter as a whole
/// (`new.n` as `("n", "")`, which only a primitive parameter may be). A read of the previous version's input is
/// refused.
fn new_pieces(text: &str) -> Result<Vec<Result<String, (String, String)>>, String> {
    let mut out = Vec::new();
    for piece in pieces_of(text)? {
        match piece {
            Ok(plain) => out.push(Ok(plain)),
            Err((true, _, _)) => return Err("reads the previous version's input: the new side is over the new version's".into()),
            Err((false, root, path)) => out.push(Err((root, path))),
        }
    }
    Ok(out)
}

/// An expression over both versions as pieces: text as written (`Ok`), and each read of a field path
/// (`Err((previous, root, path))`, `old.q.cents` as `(true, "q", "cents")`), or of a parameter as a whole with an
/// empty path (`new.n` as `(false, "n", "")`), which its caller refuses unless it is a primitive it may read.
fn pieces_of(text: &str) -> Result<Vec<Result<String, (bool, String, String)>>, String> {
    let chars: Vec<char> = text.chars().collect();
    let identifier = |c: char| c.is_alphanumeric() || c == '_';
    let mut out: Vec<Result<String, (bool, String, String)>> = Vec::new();
    let mut plain = String::new();
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        let after_dot = plain.trim_end().ends_with('.');
        if (c.is_alphabetic() || c == '_') && !after_dot && (i == 0 || !identifier(chars[i - 1])) {
            let start = i;
            while i < chars.len() && identifier(chars[i]) {
                i += 1;
            }
            let word: String = chars[start..i].iter().collect();
            if (word == "old" || word == "new") && chars.get(i) == Some(&'.') {
                let mut steps = Vec::new();
                while chars.get(i) == Some(&'.') {
                    let next = i + 1;
                    let mut end = next;
                    while end < chars.len() && identifier(chars[end]) {
                        end += 1;
                    }
                    if end == next {
                        break;
                    }
                    steps.push(chars[next..end].iter().collect::<String>());
                    i = end;
                }
                if steps.is_empty() {
                    return Err(format!("reads {word}. alone: only field paths and parameters are read"));
                }
                if !plain.is_empty() {
                    out.push(Ok(std::mem::take(&mut plain)));
                }
                out.push(Err((word == "old", steps[0].clone(), steps[1..].join("."))));
                continue;
            }
            plain.push_str(&word);
            continue;
        }
        plain.push(c);
        i += 1;
    }
    if !plain.is_empty() {
        out.push(Ok(plain));
    }
    Ok(out)
}

/// Whether an input equation's new side is an expression rather than a field path: one that computes the previous
/// version's field from the new one's, which may change what an input means.
pub(crate) fn is_computed(e: &super::Equation) -> bool {
    new_path(e).is_none()
}

/// The correspondence's output relation as a result relation of the regression check (`--results-agree-when`'s
/// form): a boolean over `old.result` (the previous version's result), `new.result` (the new one's) and the new
/// version's parameters, `new.n` or `n`, which becomes one over `previous`, `result` and `n`. An object result is
/// in it by its field paths, `old.result.cents == new.result.amount.cents`. None without an output relation for
/// the result (those for a parameter's fields are [`relate`]'s, and those for an identity relation
/// [`identity_relations`]'); `Err` names an output relation not supported yet: one about another observation than the
/// result, a field path or an identity relation, or several about the result. It may read the previous version's
/// parameters (H5's rest), `old.n` and `old.q.cents`, which become `before$n` and `before$q.cents`
/// ([`crate::harness::BEFORE`]): the harness reads a primitive one as the new version's in its place, and an object's
/// field path as the call left the previous version's object.
pub(crate) fn output_relation(correspondence: &Correspondence) -> Result<Option<String>, String> {
    let result = Observation::Result.id();
    if let Some(r) = correspondence.outputs.iter().find(|r| r.observation != result && !r.observation.starts_with("field:") && !r.observation.starts_with("identity:")) {
        return Err(format!("the correspondence's output relation for {} ({}) is not supported yet: only one for the result, over old.result, new.result and the new version's parameters, ones for an object parameter's fields as the call leaves them, over old.p and new.p paths, and ones for an identity relation, over old.x == old.y and new.x == new.y", r.observation, r.holds));
    }
    // Those for a parameter's fields are compared with the parameter (relate), and those for an identity relation
    // with it (identity_relations).
    let mut relations = correspondence.outputs.iter().filter(|r| r.observation == result);
    let Some(relation) = relations.next() else { return Ok(None) };
    if relations.next().is_some() {
        return Err("the correspondence has several output relations for the result: state them as one, joined by &&".into());
    }
    let chars: Vec<char> = relation.holds.chars().collect();
    let identifier = |c: char| c.is_alphanumeric() || c == '_';
    let mut out = String::new();
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        let after_dot = out.trim_end().ends_with('.');
        if (c.is_alphabetic() || c == '_') && !after_dot && (i == 0 || !identifier(chars[i - 1])) {
            let start = i;
            while i < chars.len() && identifier(chars[i]) {
                i += 1;
            }
            let word: String = chars[start..i].iter().collect();
            if (word == "old" || word == "new") && chars.get(i) == Some(&'.') {
                let next = i + 1;
                let mut end = next;
                while end < chars.len() && identifier(chars[end]) {
                    end += 1;
                }
                let name: String = chars[next..end].iter().collect();
                match (word.as_str(), name.as_str()) {
                    ("old", "result") => out.push_str(crate::harness::PREVIOUS),
                    ("new", "result") => out.push_str(crate::harness::RESULT),
                    ("new", n) if !n.is_empty() => out.push_str(n),
                    // The previous version's parameter (H5's rest), which the harness resolves.
                    ("old", n) if !n.is_empty() => {
                        out.push_str(crate::harness::BEFORE);
                        out.push_str(n);
                    }
                    _ => return Err(format!("the correspondence's output relation {} reads {word}. without a name: it reads old.result, new.result and the two versions' parameters", relation.holds)),
                }
                i = end;
                continue;
            }
            out.push_str(&word);
            continue;
        }
        out.push(c);
        i += 1;
    }
    Ok(Some(out))
}

/// How the previous version's object for the parameter `old_name` (the new version's `new_name`) is made from the
/// new one's and compared with it, by the correspondence's input equations about it (H5): each between a primitive
/// field path of the previous version's object and one of the new one's, or an expression over the new one's
/// (`old.p.cents == new.p.dollars * 100 + new.p.cents`, H5's rest), every leaf of the previous version's
/// construction given by one naming leaves of the new one's, and every primitive field of the previous version's
/// object in one, so that none of the observations it was held to leaves the count. An expression may read the new
/// version's primitive parameters (`params`) and the field paths of its other object parameters (`objects`) that
/// are leaves of their construction, `new.l.price * new.o.count`, each the argument it was made from as the call got
/// it. None when no equation is about it; `Err` names what is not supported.
pub(crate) fn relate(correspondence: &Correspondence, old_name: &str, new_name: &str, new: &RecordType, old: &RecordType, params: &[(String, Type)], objects: &[(String, RecordType)]) -> Option<Result<Corresponds, String>> {
    let (Some(fields), Some(old_fields)) = (&new.fields, &old.fields) else { return None };
    let mut equations = Vec::new();
    let paths_of = |f: &crate::harness::Fields| f.paths().iter().map(|(p, _)| p.clone()).collect::<Vec<_>>().join(", ");
    let leaves_of = || new.components.iter().map(|(c, _)| c.as_str()).collect::<Vec<_>>().join(", ");
    for e in &correspondence.inputs {
        let Some((old_root, old_path)) = path_of(&e.old, "old") else { continue };
        if old_root != old_name {
            continue;
        }
        let text = format!("{} == {}", e.old, e.new);
        let old_field = field_steps(old_fields, old_path).map(|(_, t)| t);
        let Some(t) = old_field else {
            return Some(Err(format!("the correspondence's input equation {text} names {old_path}, which is not a primitive field path of the previous version's {} ({})", old.simple_name(), paths_of(old_fields))));
        };
        if let Some((new_root, new_path)) = new_path(e) {
            if new_root != new_name {
                return Some(Err(format!("the correspondence's input equation {text} relates the previous version's {old_name} to the new version's {new_root}; only equations between the two versions' same parameter are supported yet")));
            }
            match field_steps(fields, new_path).map(|(_, t)| t) {
                Some(u) if t == u && t.is_primitive() => equations.push(FieldEquation { old: old_path.to_string(), new: new_path.to_string(), ty: t, computed: None }),
                Some(u) => return Some(Err(format!("the correspondence's input equation {text} relates a field of type {} to one of type {}; only equations between primitive fields of the same type are supported yet", t.java_name(), u.java_name()))),
                None => return Some(Err(format!("the correspondence's input equation {text} names {new_path}, which is not a primitive field path of the new version's {} ({})", new.simple_name(), paths_of(fields)))),
            }
            continue;
        }
        // An expression over the new object's paths (H5's rest): each a primitive field path of it and a leaf of
        // its construction, so that it gives the previous leaf before the call and is compared after it.
        let pieces = match new_pieces(&e.new) {
            Ok(p) => p,
            Err(why) => return Some(Err(format!("the correspondence's input equation {text} {why}"))),
        };
        let mut computed = Computed { pieces: Vec::new(), reads: Vec::new(), ty: t.clone() };
        for piece in pieces {
            match piece {
                Ok(plain) => computed.pieces.push(Piece::Text(plain)),
                // A primitive parameter of the new version, read as a whole (H5's rest): the same before the call
                // and after it, so that it gives the previous leaf and is compared as the object's paths are.
                Err((root, path)) if path.is_empty() => {
                    let ty = match params.iter().find(|(n, _)| *n == root) {
                        Some((_, ty)) if matches!(ty, Type::Int | Type::Long | Type::Boolean | Type::Short | Type::Byte | Type::Char) => ty,
                        Some(_) => return Some(Err(format!("the correspondence's input equation {text} {}", whole_read(false, &root)))),
                        None if root == new_name => return Some(Err(format!("the correspondence's input equation {text} {}", whole_read(false, &root)))),
                        None => return Some(Err(format!("the correspondence's input equation {text} reads new.{root}, which is not a parameter of the new version ({})", params.iter().map(|(n, _)| n.as_str()).collect::<Vec<_>>().join(", ")))),
                    };
                    let at = match computed.reads.iter().position(|r| r.param && r.path == root) {
                        Some(at) => at,
                        None => {
                            computed.reads.push(Read { path: root, ty: ty.clone(), leaf: usize::MAX, param: true });
                            computed.reads.len() - 1
                        }
                    };
                    computed.pieces.push(Piece::Read(at));
                }
                // A field path of another object parameter of the new version (H5's rest): a leaf of its
                // construction, read as a primitive parameter is, the argument it was made from as the call got it,
                // its flat parameter `o.count` once the layout lays the parameters out.
                Err((root, path)) if root != new_name => {
                    let Some((_, other)) = objects.iter().find(|(n, r)| *n == root && r.is_made()) else {
                        return Some(Err(format!("the correspondence's input equation {text} reads the fields of the new version's {root}, which is not an object parameter of the new version made by its constructor ({}); only an expression over object parameters' fields and the primitive parameters is supported yet", objects.iter().filter(|(_, r)| r.is_made()).map(|(n, _)| n.as_str()).collect::<Vec<_>>().join(", "))));
                    };
                    let Some(other_fields) = &other.fields else { unreachable!("made") };
                    let Some((_, ty)) = field_steps(other_fields, &path).filter(|(_, ty)| ty.is_primitive()) else {
                        return Some(Err(format!("the correspondence's input equation {text} reads {root}.{path}, which is not a primitive field path of the new version's {} ({})", other.simple_name(), paths_of(other_fields))));
                    };
                    if !other.components.iter().any(|(c, u)| *c == path && *u == ty) {
                        return Some(Err(format!("the correspondence's input equation {text} reads {root}.{path}, which is not a leaf of the new version's construction of {root} ({}): another parameter's field is read as the argument it was made from", other.components.iter().map(|(c, _)| c.as_str()).collect::<Vec<_>>().join(", "))));
                    }
                    let flat = format!("{root}.{path}");
                    let at = match computed.reads.iter().position(|r| r.param && r.path == flat) {
                        Some(at) => at,
                        None => {
                            computed.reads.push(Read { path: flat, ty, leaf: usize::MAX, param: true });
                            computed.reads.len() - 1
                        }
                    };
                    computed.pieces.push(Piece::Read(at));
                }
                Err((_, path)) => {
                    let Some((_, ty)) = field_steps(fields, &path).filter(|(_, ty)| ty.is_primitive()) else {
                        return Some(Err(format!("the correspondence's input equation {text} reads {path}, which is not a primitive field path of the new version's {} ({})", new.simple_name(), paths_of(fields))));
                    };
                    let Some(leaf) = new.components.iter().position(|(c, u)| *c == path && *u == ty) else {
                        return Some(Err(format!("the correspondence's input equation {text} reads {path}, which is not a leaf of the new version's construction ({}): an expression gives the previous version's argument from the new one's arguments", leaves_of())));
                    };
                    let at = match computed.reads.iter().position(|r| !r.param && r.path == path) {
                        Some(at) => at,
                        None => {
                            computed.reads.push(Read { path, ty, leaf, param: false });
                            computed.reads.len() - 1
                        }
                    };
                    computed.pieces.push(Piece::Read(at));
                }
            }
        }
        if let Err(why) = computed.parse(&(0..computed.reads.len() as u16).map(|i| 2 * i).collect::<Vec<_>>()) {
            return Some(Err(format!("the correspondence's input equation {text} is not one the harness computes: {why}")));
        }
        let shown = computed.text(&|p| p.to_string());
        equations.push(FieldEquation { old: old_path.to_string(), new: shown.trim().to_string(), ty: t, computed: Some(computed) });
    }
    if equations.is_empty() {
        return None;
    }
    if let Some((missing, _)) = old_fields.paths().into_iter().find(|(p, _)| !equations.iter().any(|e| e.old == *p)) {
        return Some(Err(format!("the previous version's {old_name}.{missing} is in no equation of the correspondence: what it held would leave the observations uncounted")));
    }
    let mut leaves = Vec::new();
    for (leaf, t) in &old.components {
        let equation = equations.iter().find(|e| e.old == *leaf);
        let given = match equation.map(|e| (e, &e.computed)) {
            Some((e, Some(c))) if e.ty == *t => Some(Source::Computed(c.clone())),
            Some((e, None)) => new.components.iter().position(|(c, u)| *c == e.new && u == t).map(Source::Leaf),
            _ => None,
        };
        match given {
            Some(s) => leaves.push(s),
            None => {
                return Some(Err(format!("the previous version's {} is made from {old_name}.{leaf}, which no equation of the correspondence gives as a leaf of the new version's construction ({}), or an expression over them: only a correspondence that names how each of the previous version's constructor arguments is made from the new one's is supported yet", old.describe(), leaves_of())));
            }
        }
    }
    let relations = match field_relations(correspondence, old_name, new_name, new, old) {
        Ok(r) => r,
        Err(gap) => return Some(Err(gap)),
    };
    Some(Ok(Corresponds { leaves, equations, relations, same_shape: false }))
}

/// How the previous version's object for the parameter `old_name` (the new version's `new_name`) is compared with
/// the new one's where the two have the same shape and no input equation is about it, but the correspondence has
/// output relations for its fields (H5's rest): each relation in place of equality for its path, and every other
/// primitive field path compared for equality as without a correspondence, by implied equations that make the
/// previous object from the same leaves and are not assumed of the two as made. None when no output relation is
/// about it; `Err` names what is not supported.
pub(crate) fn relate_same_shape(correspondence: &Correspondence, old_name: &str, new_name: &str, new: &RecordType, old: &RecordType) -> Option<Result<Corresponds, String>> {
    let (Some(_), Some(old_fields)) = (&new.fields, &old.fields) else { return None };
    let whole = format!("field:{old_name}");
    if !correspondence.outputs.iter().any(|r| r.observation == whole || r.observation.strip_prefix(whole.as_str()).is_some_and(|rest| rest.starts_with('.'))) {
        return None;
    }
    let relations = match field_relations(correspondence, old_name, new_name, new, old) {
        Ok(r) => r,
        Err(gap) => return Some(Err(gap)),
    };
    // An array field is compared by its elements, which no equation between paths says.
    if let Some((path, _)) = old_fields.paths().into_iter().find(|(p, t)| !t.is_primitive() && !relations.iter().any(|r| r.covers(p))) {
        return Some(Err(format!("the correspondence's output relation for {old_name}'s fields leaves {old_name}.{path} to be compared for equality, and it is an array: an output relation for a field of a parameter of the same shape in both versions is supported yet only where its other fields are primitives or objects of them")));
    }
    let equations = old_fields.paths().into_iter().filter(|(_, t)| t.is_primitive()).map(|(p, ty)| FieldEquation { old: p.clone(), new: p, ty, computed: None }).collect();
    let leaves = (0..old.components.len()).map(Source::Leaf).collect();
    Some(Ok(Corresponds { leaves, equations, relations, same_shape: true }))
}

/// The correspondence's output relations for the parameter's fields as the calls leave them (H5's rest), each for
/// `field:{old_name}` or `field:{old_name}.path` (a previous version's path, primitive or an object's), a boolean
/// over primitive field paths of the parameter's two objects, `old.{old_name}.…` and `new.{new_name}.…`. `Err`
/// names one that is not supported.
fn field_relations(correspondence: &Correspondence, old_name: &str, new_name: &str, new: &RecordType, old: &RecordType) -> Result<Vec<FieldRelation>, String> {
    let (Some(fields), Some(old_fields)) = (&new.fields, &old.fields) else { return Ok(Vec::new()) };
    let paths_of = |f: &crate::harness::Fields| f.paths().iter().map(|(p, _)| p.clone()).collect::<Vec<_>>().join(", ");
    let whole = format!("field:{old_name}");
    let mut out: Vec<FieldRelation> = Vec::new();
    for r in &correspondence.outputs {
        let path = match r.observation.strip_prefix(whole.as_str()) {
            Some("") => "",
            Some(rest) if rest.starts_with('.') => &rest[1..],
            _ => continue,
        };
        let about = |why: String| format!("the correspondence's output relation for {} ({}) {why}", r.observation, r.holds);
        if !path.is_empty() && !old_fields.paths().iter().any(|(p, _)| p == path || p.strip_prefix(path).is_some_and(|rest| rest.starts_with('.'))) {
            return Err(about(format!("names {path}, which is not a field path of the previous version's {} ({})", old.simple_name(), paths_of(old_fields))));
        }
        if let Some(other) = out.iter().find(|o| o.covers(path) || under(&o.path, path)) {
            return Err(about(format!("overlaps the one for {}: state the relations for a path as one, joined by &&", other.observation(old_name))));
        }
        let mut relation = FieldRelation { path: path.to_string(), holds: r.holds.clone(), pieces: Vec::new(), reads: Vec::new() };
        for piece in pieces_of(&r.holds).map_err(&about)? {
            match piece {
                Ok(plain) => relation.pieces.push(Piece::Text(plain)),
                Err((previous, root, path)) if path.is_empty() => return Err(about(whole_read(previous, &root))),
                Err((previous, root, path)) => {
                    let (name, f, version) = if previous { (old_name, old_fields, "previous") } else { (new_name, fields, "new") };
                    if root != name {
                        return Err(about(format!("reads {}.{root}: an output relation for {old_name}'s fields reads only the two versions' {old_name}, as the call leaves it", if previous { "old" } else { "new" })));
                    }
                    let Some((_, ty)) = field_steps(f, &path).filter(|(_, ty)| ty.is_primitive()) else {
                        return Err(about(format!("reads {path}, which is not a primitive field path of the {version} version's {} ({})", if previous { old.simple_name() } else { new.simple_name() }, paths_of(f))));
                    };
                    let at = match relation.reads.iter().position(|x| x.previous == previous && x.path == path) {
                        Some(at) => at,
                        None => {
                            relation.reads.push(RelationRead { previous, path, ty });
                            relation.reads.len() - 1
                        }
                    };
                    relation.pieces.push(Piece::Read(at));
                }
            }
        }
        if let Err(why) = relation.parse(&(0..relation.reads.len() as u16).map(|i| 2 * i).collect::<Vec<_>>()) {
            return Err(about(format!("is not one the harness compares: {why}")));
        }
        out.push(relation);
    }
    Ok(out)
}

/// Whether the field path `path` is `prefix` or under it; every path is under the empty one.
fn under(path: &str, prefix: &str) -> bool {
    prefix.is_empty() || path == prefix || path.strip_prefix(prefix).is_some_and(|rest| rest.starts_with('.'))
}

/// The correspondence's output relations for identity relations (H5's rest), each for `identity:x==y`, one of the
/// relations the check observes (`pairs`, [`crate::harness::Layout::identity_pairs`]), and a boolean over whether it
/// holds in each version, written `old.x == old.y` and `new.x == new.y` (either way round, or with `!=` for its
/// negation): `new.result != new.q` says the new version always hands back another object. `Err` names one that is
/// not supported.
pub(crate) fn identity_relations(correspondence: &Correspondence, pairs: &[(String, String)]) -> Result<Vec<IdentityRelation>, String> {
    let mut out: Vec<IdentityRelation> = Vec::new();
    for r in correspondence.outputs.iter().filter(|r| r.observation.starts_with("identity:")) {
        let about = |why: String| format!("the correspondence's output relation for {} ({}) {why}", r.observation, r.holds);
        let Some((x, y)) = r.observation.strip_prefix("identity:").and_then(|p| p.split_once("==")).map(|(x, y)| (x.trim(), y.trim())) else {
            return Err(about("names no identity relation: write it identity:x==y".into()));
        };
        let observed = || if pairs.is_empty() { "none".to_string() } else { pairs.iter().map(|(a, b)| format!("{a} == {b}")).collect::<Vec<_>>().join(", ") };
        let Some(pair) = pairs.iter().find(|(a, b)| (a == x && b == y) || (a == y && b == x)) else {
            return Err(about(format!("names {x} == {y}, which is not an identity relation the check observes ({})", observed())));
        };
        if out.iter().any(|o| o.pair == *pair) {
            return Err(about(format!("is the second for {x} == {y}: state the relations for it as one, joined by &&")));
        }
        let mut relation = IdentityRelation { pair: pair.clone(), holds: r.holds.clone(), pieces: Vec::new(), reads: Vec::new() };
        let only = format!("an output relation for an identity relation reads only that relation in each version, old.{x} == old.{y} and new.{x} == new.{y}");
        let reference = |root: &str, path: &str| if path.is_empty() { root.to_string() } else { format!("{root}.{path}") };
        let mut pieces = pieces_of(&r.holds).map_err(&about)?.into_iter().peekable();
        while let Some(piece) = pieces.next() {
            let (previous, root, path) = match piece {
                Ok(plain) => {
                    relation.pieces.push(Piece::Text(plain));
                    continue;
                }
                Err(read) => read,
            };
            let left = reference(&root, &path);
            let shown = |previous: bool, what: &str| format!("{}.{what}", if previous { "old" } else { "new" });
            // A reference read is the relation's side: the comparison, then the other side, of the same version.
            let op = match pieces.next() {
                Some(Ok(t)) if matches!(t.trim(), "==" | "!=") => t.trim().to_string(),
                _ => return Err(about(format!("reads {} alone: {only}", shown(previous, &left)))),
            };
            let Some(Err((other_previous, other_root, other_path))) = pieces.next() else {
                return Err(about(format!("compares {} with no reference: {only}", shown(previous, &left))));
            };
            let right = reference(&other_root, &other_path);
            if other_previous != previous {
                return Err(about(format!("compares {} with {}: a reference is compared only with one of its own version, {only}", shown(previous, &left), shown(other_previous, &right))));
            }
            if !((left == pair.0 && right == pair.1) || (left == pair.1 && right == pair.0)) {
                return Err(about(format!("reads {} {op} {}: {only}", shown(previous, &left), shown(previous, &right))));
            }
            let at = match relation.reads.iter().position(|p| *p == previous) {
                Some(at) => at,
                None => {
                    relation.reads.push(previous);
                    relation.reads.len() - 1
                }
            };
            if op == "!=" {
                relation.pieces.push(Piece::Text("!".into()));
            }
            relation.pieces.push(Piece::Read(at));
        }
        if let Err(why) = relation.parse(&(0..relation.reads.len() as u16).map(|i| 2 * i).collect::<Vec<_>>()) {
            return Err(about(format!("is not one the harness compares: {why}")));
        }
        out.push(relation);
    }
    Ok(out)
}

/// The parameters the correspondence's output relations for fields are about: `q` for `field:q.cents`.
pub(crate) fn field_relation_roots(correspondence: &Correspondence) -> Vec<(String, &super::Relation)> {
    correspondence.outputs.iter().filter_map(|r| r.observation.strip_prefix("field:").map(|p| (p.split('.').next().unwrap_or(p).to_string(), r))).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::harness::{FieldKind, Fields};
    use crate::spec::Equation;

    fn quotes() -> (RecordType, RecordType) {
        let money = RecordType::made("shop/Money", vec![("cents".into(), Type::Long)], Vec::new(), Fields { class: "shop/Money".into(), fields: vec![("cents".into(), FieldKind::Value(Type::Long))] });
        let money_fields = money.fields.clone().unwrap();
        let new = RecordType::made("shop/Quote", vec![("amount".into(), Type::Object("shop/Money".into())), ("quantity".into(), Type::Int)], vec![money], Fields { class: "shop/Quote".into(), fields: vec![("amount".into(), FieldKind::Object(Box::new(money_fields))), ("quantity".into(), FieldKind::Value(Type::Int))] });
        let old = RecordType::made("shop/Quote", vec![("quantity".into(), Type::Int), ("cents".into(), Type::Long)], Vec::new(), Fields { class: "shop/Quote".into(), fields: vec![("cents".into(), FieldKind::Value(Type::Long)), ("quantity".into(), FieldKind::Value(Type::Int))] });
        (new, old)
    }

    fn correspondence(pairs: &[(&str, &str)]) -> Correspondence {
        Correspondence { inputs: pairs.iter().map(|(o, n)| Equation { old: (*o).into(), new: (*n).into() }).collect(), outputs: Vec::new() }
    }

    /// [`allocations`] over a small build: what each kind of code makes in one call, and where no number bounds it.
    #[test]
    fn the_allocations_of_one_call_are_counted_through_calls_and_unbounded_in_a_loop_or_a_recursion() {
        let javac = std::process::Command::new("javac").arg("-version").output().is_ok_and(|o| o.status.success());
        if !javac {
            assert!(std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1"), "javac not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip this test");
            return;
        }
        let dir = tempfile::tempdir().unwrap();
        let source = dir.path().join("A.java");
        std::fs::write(
            &source,
            r#"package p;
public class A {
    int v;
    A(int v) { if (v < 0) throw new IllegalArgumentException(); this.v = v; }
    static int pure(int x) { return x * 2 + 1; }
    static A one(int x) { return new A(x); }
    static A either(int x) { return x > 0 ? one(x) : new A(0); }
    static int[] arrays(int n) { int[] a = new int[n]; int[][] b = new int[2][2]; return a; }
    static int loopPure(int n) { int s = 0; for (int i = 0; i < n; i++) s += i; return s; }
    static int loopMakes(int n) { int s = 0; for (int i = 0; i < n; i++) s += new A(i).v; return s; }
    static int factorial(int n) { return n <= 1 ? 1 : n * factorial(n - 1); }
    static int countDown(int n) { return n <= 0 ? one(0).v : countDown(n - 1); }
    static boolean even(int n) { return n == 0 || odd(n - 1); }
    static boolean odd(int n) { return n != 0 && even(n - 1); }
    static boolean evenMakes(int n) { return n == 0 || oddMakes(n - 1); }
    static boolean oddMakes(int n) { new A(n); return n != 0 && evenMakes(n - 1); }
    int size() { return 0; }
    static int dispatch(A a) { return a.size(); }
}
class B extends A { B() { super(1); } int size() { return new A(2).v + new A(3).v; } }
"#,
        )
        .unwrap();
        let status = std::process::Command::new("javac").args(["-g", "-d"]).arg(dir.path()).arg(&source).status().unwrap();
        assert!(status.success(), "the fixture compiles");
        let made = |m: &str| allocations(dir.path(), &format!("p.A#{m}")).expect("counted");
        assert_eq!(made("pure"), Some(0), "nothing made");
        assert_eq!(made("one"), Some(2), "the object and the exception its constructor may throw");
        assert_eq!(made("either"), Some(4), "both branches, each through its constructor");
        assert_eq!(made("arrays"), Some(2), "an array instruction is one, however many arrays it makes inside the JVM");
        assert_eq!(made("loopPure"), Some(0), "a loop that makes nothing");
        assert_eq!(made("loopMakes"), None, "made in a loop");
        assert_eq!(made("factorial"), Some(0), "a recursion that makes nothing");
        assert_eq!(made("countDown"), None, "a recursion through a call that makes objects");
        assert_eq!(made("even"), Some(0), "a recursion through two methods that make nothing");
        assert_eq!(made("evenMakes"), None, "a recursion through another method that makes an object");
        assert_eq!(made("oddMakes"), None, "the same recursion from its other method");
        assert_eq!(made("dispatch"), Some(4), "the most of the targets the call may dispatch to: B's two objects, with their exceptions");
        assert!(allocations(dir.path(), "p.Missing#m").is_err(), "a class the build doesn't have is an error, not a bound");
    }

    #[test]
    fn the_previous_object_is_made_from_the_leaves_its_equations_name() {
        let (new, old) = quotes();
        let c = correspondence(&[("old.q.cents", "new.q.amount.cents"), ("old.q.quantity", "new.q.quantity")]);
        let related = relate(&c, "q", "q", &new, &old, &[], &[]).expect("about q").expect("supported");
        // The previous constructor takes (quantity, cents): the new leaves are (amount.cents, quantity).
        assert_eq!(related.leaves, vec![Source::Leaf(1), Source::Leaf(0)]);
        assert_eq!(related.equations[0], FieldEquation { old: "cents".into(), new: "amount.cents".into(), ty: Type::Long, computed: None });
        assert!(relate(&c, "p", "p", &new, &old, &[], &[]).is_none(), "no equation is about p");
    }

    #[test]
    fn what_the_narrow_case_does_not_cover_is_named() {
        let (new, old) = quotes();
        let gap = |pairs: &[(&str, &str)]| relate(&correspondence(pairs), "q", "q", &new, &old, &[], &[]).expect("about q").expect_err("a gap");
        assert!(gap(&[("old.q.cents", "new.q.amount.cents")]).contains("q.quantity is in no equation"));
        assert!(gap(&[("old.q.cents", "new.q.quantity"), ("old.q.quantity", "new.q.quantity")]).contains("of type long to one of type int"));
        assert!(gap(&[("old.q.cents", "new.q.price"), ("old.q.quantity", "new.q.quantity")]).contains("not a primitive field path of the new version's Quote"));
    }

    /// Two shapes of a price: `Price(long cents)` before, `Price(long dollars, int cents)` now.
    fn prices() -> (RecordType, RecordType) {
        let new = RecordType::made("p/Price", vec![("dollars".into(), Type::Long), ("cents".into(), Type::Int)], Vec::new(), Fields { class: "p/Price".into(), fields: vec![("dollars".into(), FieldKind::Value(Type::Long)), ("cents".into(), FieldKind::Value(Type::Int))] });
        let old = RecordType::made("p/Price", vec![("cents".into(), Type::Long)], Vec::new(), Fields { class: "p/Price".into(), fields: vec![("cents".into(), FieldKind::Value(Type::Long))] });
        (new, old)
    }

    #[test]
    fn an_expression_over_the_new_objects_leaves_gives_the_previous_leaf() {
        let (new, old) = prices();
        let c = correspondence(&[("old.p.cents", "new.p.dollars * 100 + new.p.cents")]);
        assert_eq!(roots(&c).unwrap(), vec![("p".to_string(), Some("p".to_string()), false)]);
        let related = relate(&c, "p", "p", &new, &old, &[], &[]).expect("about p").expect("supported");
        let Source::Computed(e) = &related.leaves[0] else { panic!("computed: {related:?}") };
        assert_eq!(e.reads.iter().map(|r| (r.path.as_str(), r.leaf)).collect::<Vec<_>>(), vec![("dollars", 0), ("cents", 1)]);
        assert_eq!(e.eval(&[crate::interp::Value::Long(3), crate::interp::Value::Int(25)]).unwrap(), crate::interp::Value::Long(325));
        assert_eq!(related.equations[0].text("p", "p"), "old.p.cents == new.p.dollars * 100 + new.p.cents");
        assert_eq!(related.equations[0].new, "dollars * 100 + cents");
        // A path read twice is one read.
        let twice = relate(&correspondence(&[("old.p.cents", "new.p.cents + new.p.cents + new.p.dollars")]), "p", "p", &new, &old, &[], &[]).unwrap().unwrap();
        let Source::Computed(e) = &twice.leaves[0] else { panic!() };
        assert_eq!(e.reads.len(), 2);
    }

    #[test]
    fn an_expression_may_read_the_new_versions_primitive_parameters_besides_the_objects_leaves() {
        let (new, old) = prices();
        let params = [("p".to_string(), Type::Object("p/Price".into())), ("n".to_string(), Type::Int), ("q".to_string(), Type::Object("p/Price".into())), ("f".to_string(), Type::Float)];
        let c = correspondence(&[("old.p.cents", "(new.p.dollars * 100 + new.p.cents) * new.n + new.n")]);
        assert_eq!(roots(&c).unwrap(), vec![("p".to_string(), Some("p".to_string()), false)]);
        let related = relate(&c, "p", "p", &new, &old, &params, &[]).expect("about p").expect("supported");
        let Source::Computed(e) = &related.leaves[0] else { panic!("computed: {related:?}") };
        // The parameter is read once, its flat index left to the layout.
        assert_eq!(e.reads.iter().map(|r| (r.path.as_str(), r.param)).collect::<Vec<_>>(), vec![("dollars", false), ("cents", false), ("n", true)]);
        assert!(related.equations[0].reads_parameters());
        assert_eq!(related.equations[0].text("p", "p"), "old.p.cents == (new.p.dollars * 100 + new.p.cents) * new.n + new.n");
        assert_eq!(related.equations[0].new_side("p_after"), "(p_after.dollars * 100 + p_after.cents) * n + n");
        use crate::interp::Value::{Int, Long};
        assert_eq!(e.eval(&[Long(3), Int(25), Int(2)]).unwrap(), Long(652));
        // Laid out, the parameter is the flat parameter of its name, after the object's leaves.
        let layout = crate::harness::Layout::new(None, &["p".into(), "n".into()], &[Type::Object("p/Price".into()), Type::Int], &[Some((new.clone(), Some(RecordType { corresponds: Some(related.clone()), ..old.clone() }))), None], (None, None));
        let crate::harness::Slot::Record { before: Some(previous), first, .. } = &layout.args[0] else { panic!() };
        assert_eq!(previous.leaves(*first), vec![crate::harness::Leaf::Computed(Computed { reads: e.reads.iter().cloned().map(|r| Read { leaf: if r.param { 2 } else { r.leaf }, ..r }).collect(), ..e.clone() }, vec![0, 1, 2])]);
        let gap = |new_side: &str| {
            let c = correspondence(&[("old.p.cents", new_side)]);
            match roots(&c) {
                Err(e) => e,
                Ok(_) => relate(&c, "p", "p", &new, &old, &params, &[]).expect("about p").expect_err("a gap"),
            }
        };
        assert!(gap("new.p.cents * new.m").contains("reads new.m, which is not a parameter of the new version (p, n, q, f)"));
        assert!(gap("new.p.cents * new.q").contains("reads new.q as a whole"));
        assert!(gap("new.p.cents + new.p").contains("reads new.p as a whole"));
        assert!(gap("new.p.cents * new.f").contains("reads new.f as a whole"));
        assert!(gap("new.p.cents + new.q.cents").contains("reads the fields of the new version's q, which is not an object parameter of the new version made by its constructor ()"));
        // An expression over parameters alone is about the parameter in the previous one's place, and so is the
        // parameter alone.
        for new_side in ["new.n * 100", "new.n"] {
            let c = correspondence(&[("old.p.cents", new_side)]);
            assert_eq!(roots(&c).unwrap(), vec![("p".to_string(), None, false)], "{new_side}");
            let related = relate(&c, "p", "p", &new, &old, &params, &[]).expect("about p").expect("supported");
            let Source::Computed(e) = &related.leaves[0] else { panic!("computed: {related:?}") };
            assert_eq!(e.reads.iter().map(|r| (r.path.as_str(), r.param)).collect::<Vec<_>>(), vec![("n", true)]);
        }
    }

    #[test]
    fn an_expression_may_read_another_object_parameters_leaves_as_the_arguments_it_was_made_from() {
        let (new, old) = prices();
        let order = RecordType::made("p/Order", vec![("count".into(), Type::Int)], Vec::new(), Fields { class: "p/Order".into(), fields: vec![("count".into(), FieldKind::Value(Type::Int)), ("seen".into(), FieldKind::Value(Type::Int))] });
        let params = [("p".to_string(), Type::Object("p/Price".into())), ("o".to_string(), Type::Object("p/Order".into()))];
        let objects = [("p".to_string(), new.clone()), ("o".to_string(), order.clone())];
        let c = correspondence(&[("old.p.cents", "(new.p.dollars * 100 + new.p.cents) * new.o.count")]);
        // About the parameter of the previous root's name; of several none of which has it, the one in its place.
        assert_eq!(roots(&c).unwrap(), vec![("p".to_string(), Some("p".to_string()), false)]);
        assert_eq!(roots(&correspondence(&[("old.r.cents", "new.p.cents * new.o.count")])).unwrap(), vec![("r".to_string(), None, false)]);
        let related = relate(&c, "p", "p", &new, &old, &params, &objects).expect("about p").expect("supported");
        let Source::Computed(e) = &related.leaves[0] else { panic!("computed: {related:?}") };
        assert_eq!(e.reads.iter().map(|r| (r.path.as_str(), r.param)).collect::<Vec<_>>(), vec![("dollars", false), ("cents", false), ("o.count", true)]);
        assert!(related.equations[0].reads_parameters());
        assert_eq!(related.equations[0].text("p", "p"), "old.p.cents == (new.p.dollars * 100 + new.p.cents) * new.o.count");
        assert_eq!(related.equations[0].new_side("p_after"), "(p_after.dollars * 100 + p_after.cents) * o_count");
        // Laid out, the read is the order's leaf, after the price's.
        let layout = crate::harness::Layout::new(None, &["p".into(), "o".into()], &[Type::Object("p/Price".into()), Type::Object("p/Order".into())], &[Some((new.clone(), Some(RecordType { corresponds: Some(related.clone()), ..old.clone() }))), Some((order.clone(), Some(order.clone())))], (None, None));
        let crate::harness::Slot::Record { before: Some(previous), first, .. } = &layout.args[0] else { panic!() };
        assert_eq!(previous.leaves(*first), vec![crate::harness::Leaf::Computed(Computed { reads: e.reads.iter().cloned().map(|r| Read { leaf: if r.param { 2 } else { r.leaf }, ..r }).collect(), ..e.clone() }, vec![0, 1, 2])]);
        let gap = |new_side: &str| relate(&correspondence(&[("old.p.cents", new_side)]), "p", "p", &new, &old, &params, &objects).expect("about p").expect_err("a gap");
        assert!(gap("new.p.cents * new.o.size").contains("reads o.size, which is not a primitive field path of the new version's Order (count, seen)"));
        assert!(gap("new.p.cents * new.o.seen").contains("reads o.seen, which is not a leaf of the new version's construction of o (count)"));
        assert!(gap("new.p.cents * new.r.count").contains("reads the fields of the new version's r, which is not an object parameter of the new version made by its constructor (p, o)"));
    }

    #[test]
    fn an_expression_the_harness_cannot_compute_is_named() {
        let (new, old) = prices();
        let gap = |old_side: &str, new_side: &str| {
            let c = correspondence(&[(old_side, new_side)]);
            match roots(&c) {
                Err(e) => e,
                Ok(_) => relate(&c, "p", "p", &new, &old, &[], &[]).expect("about p").expect_err("a gap"),
            }
        };
        assert!(gap("old.p.cents", "new.p.dollars * 100 + old.p.cents").contains("reads the previous version's input"));
        assert!(gap("old.p.cents", "new.p.dollars + new.q.cents").contains("reads the fields of the new version's q, which is not an object parameter"));
        assert!(gap("old.p.cents", "100").contains("reads nothing of the new version's input"));
        assert!(gap("old.p.cents", "new.p * 2").contains("reads new.p as a whole"));
        assert!(gap("old.p.cents + 1", "new.p.cents").contains("does not have a field path of the previous version's input"));
        assert!(gap("old.p.cents", "new.p.euros * 100").contains("reads euros, which is not a primitive field path"));
        assert!(gap("old.p.cents", "new.p.dollars > 0").contains("is a boolean, and the field it gives is long"), "{}", gap("old.p.cents", "new.p.dollars > 0"));
    }

    #[test]
    fn an_equation_that_computes_an_anchored_input_is_refused_unless_a_person_stated_it() {
        use super::super::{Derivation, ExternalInput, PreservationContract};
        let contract = |derivation: Derivation| PreservationContract { subject: "p.Prices#total".into(), inputs: vec![ExternalInput { name: "p".into(), ty: "p.Price".into(), derivation }], required: vec!["result".into()], approved_changes: Vec::new() };
        let offset = correspondence(&[("old.p.cents", "new.p.dollars * 100 + new.p.cents + 1")]);
        let gap = anchored(&offset, &contract(Derivation::Identity)).expect("refused");
        assert!(gap.contains("the preservation contract anchors p (its derivation is identity)"), "{gap}");
        // Paths alone only say where each version holds the same value.
        assert_eq!(anchored(&correspondence(&[("old.p.cents", "new.p.cents")]), &contract(Derivation::Identity)), None);
        // A person's stated derivation has the equation, written any way: it stands; another is refused.
        let stated = Derivation::Stated { expression: "old.p.cents==new.p.dollars*100 + new.p.cents + 1".into() };
        assert_eq!(anchored(&offset, &contract(stated.clone())), None);
        let other = correspondence(&[("old.p.cents", "new.p.dollars * 100")]);
        assert!(anchored(&other, &contract(stated)).expect("refused").contains("does not say"));
        // An input the contract doesn't name is internal, and the correspondence's to state.
        let internal = correspondence(&[("old.r.cents", "new.r.dollars * 100")]);
        assert_eq!(anchored(&internal, &contract(Derivation::Identity)), None);
    }

    #[test]
    fn an_output_relation_for_a_field_takes_the_place_of_the_equations_about_its_path() {
        let (new, old) = prices();
        let mut c = correspondence(&[("old.p.cents", "new.p.dollars * 100 + new.p.cents")]);
        let holds = "new.p.dollars * 100 + new.p.cents - old.p.cents >= 0 && new.p.dollars * 100 + new.p.cents - old.p.cents < 100";
        c.outputs.push(super::super::Relation { observation: "field:p.cents".into(), holds: holds.into() });
        let related = relate(&c, "p", "p", &new, &old, &[], &[]).expect("about p").expect("supported");
        let [r] = related.relations.as_slice() else { panic!("one relation: {related:?}") };
        assert_eq!((r.path.as_str(), r.observation("p")), ("cents", "field:p.cents".to_string()));
        assert_eq!(r.reads.iter().map(|x| (x.previous, x.path.as_str())).collect::<Vec<_>>(), vec![(false, "dollars"), (false, "cents"), (true, "cents")]);
        // The equation still makes the previous object; after the calls the relation is compared in its place.
        assert_eq!(related.equations.len(), 1);
        assert!(related.compared_equations().is_empty());
        use crate::interp::Value::{Int, Long};
        assert!(r.eval(&[Long(3), Int(0), Long(250)]).unwrap(), "300 is 250 rounded up to a dollar");
        assert!(!r.eval(&[Long(4), Int(0), Long(250)]).unwrap());
        assert!(r.covers("cents") && !r.covers("centsx"));
        // Refused by name.
        let gap = |observation: &str, holds: &str| {
            let mut c = correspondence(&[("old.p.cents", "new.p.dollars * 100 + new.p.cents")]);
            c.outputs.push(super::super::Relation { observation: observation.into(), holds: holds.into() });
            relate(&c, "p", "p", &new, &old, &[], &[]).expect("about p").expect_err("a gap")
        };
        assert!(gap("field:p.euros", "true").contains("names euros, which is not a field path of the previous version's Price"));
        assert!(gap("field:p.cents", "new.p.dollars").contains("is not a boolean"));
        assert!(gap("field:p.cents", "old.q.cents == new.p.cents").contains("reads old.q"));
        assert!(gap("field:p.cents", "old.p.dollars == 0").contains("reads dollars, which is not a primitive field path of the previous version's Price"));
        assert!(gap("field:p.cents", "old.p == new.p").contains("reads old.p as a whole"));
        let mut both = correspondence(&[("old.p.cents", "new.p.dollars * 100 + new.p.cents")]);
        for o in ["field:p", "field:p.cents"] {
            both.outputs.push(super::super::Relation { observation: o.into(), holds: "true".into() });
        }
        assert!(relate(&both, "p", "p", &new, &old, &[], &[]).unwrap().unwrap_err().contains("overlaps the one for field:p"));
        // About another parameter: not p's.
        let mut other = correspondence(&[("old.p.cents", "new.p.dollars * 100 + new.p.cents")]);
        other.outputs.push(super::super::Relation { observation: "field:pp.cents".into(), holds: "true".into() });
        assert!(relate(&other, "p", "p", &new, &old, &[], &[]).unwrap().unwrap().relations.is_empty());
        assert_eq!(field_relation_roots(&other).iter().map(|(root, _)| root.as_str()).collect::<Vec<_>>(), ["pp"]);
    }

    #[test]
    fn a_parameter_of_the_same_shape_takes_relations_for_its_fields_and_keeps_equality_for_the_rest() {
        let money_fields = Fields { class: "m/Money".into(), fields: vec![("cents".into(), FieldKind::Value(Type::Long))] };
        let money = RecordType::made("m/Money", vec![("cents".into(), Type::Long)], Vec::new(), money_fields.clone());
        let line_of = |extra: Option<(&str, FieldKind)>| {
            let mut fields = vec![("price".to_string(), FieldKind::Object(Box::new(money_fields.clone()))), ("quantity".to_string(), FieldKind::Value(Type::Int))];
            fields.extend(extra.map(|(n, k)| (n.to_string(), k)));
            RecordType::made("m/Line", vec![("price".into(), Type::Object("m/Money".into())), ("quantity".into(), Type::Int)], vec![money.clone()], Fields { class: "m/Line".into(), fields })
        };
        let line = line_of(None);
        let mut c = correspondence(&[]);
        assert!(relate_same_shape(&c, "l", "l", &line, &line).is_none(), "no relation is about l");
        c.outputs.push(super::super::Relation { observation: "field:l.quantity".into(), holds: "new.l.quantity == old.l.quantity + 1".into() });
        let related = relate_same_shape(&c, "l", "l", &line, &line).expect("about l").expect("supported");
        assert!(related.same_shape);
        // Every primitive path in an implied equation, the leaves the same, and the relation in place of quantity's.
        assert_eq!(related.equations.iter().map(|e| (e.old.as_str(), e.new.as_str())).collect::<Vec<_>>(), [("price.cents", "price.cents"), ("quantity", "quantity")]);
        assert_eq!(related.leaves, [Source::Leaf(0), Source::Leaf(1)]);
        assert_eq!(related.compared_equations().iter().map(|e| e.old.as_str()).collect::<Vec<_>>(), ["price.cents"]);
        assert_eq!(related.relations.len(), 1);
        // Another parameter's relation is not l's; an array left to equality and an unknown path are refused.
        let mut other = correspondence(&[]);
        other.outputs.push(super::super::Relation { observation: "field:ll.quantity".into(), holds: "true".into() });
        assert!(relate_same_shape(&other, "l", "l", &line, &line).is_none());
        let tagged = line_of(Some(("marks", FieldKind::Array(Type::Array(Box::new(Type::Int))))));
        assert!(relate_same_shape(&c, "l", "l", &tagged, &tagged).unwrap().unwrap_err().contains("leaves l.marks to be compared for equality, and it is an array"));
        let mut whole = correspondence(&[]);
        whole.outputs.push(super::super::Relation { observation: "field:l".into(), holds: "true".into() });
        assert!(relate_same_shape(&whole, "l", "l", &tagged, &tagged).unwrap().is_ok(), "a relation for the whole object covers the array");
        let mut unknown = correspondence(&[]);
        unknown.outputs.push(super::super::Relation { observation: "field:l.count".into(), holds: "true".into() });
        assert!(relate_same_shape(&unknown, "l", "l", &line, &line).unwrap().unwrap_err().contains("names count, which is not a field path"));
    }

    #[test]
    fn a_relation_for_a_field_path_bears_on_the_observations_at_under_and_above_it() {
        assert!(within("field:q.amount.cents", "field:q") && !within("field:q", "field:q.amount.cents"));
        assert!(overlaps("field:q", "field:q.cents") && !overlaps("field:q.cents", "field:q.centsx") && !overlaps("field:q", "field:qq"));
        assert!(within("identity:q==result", "identity:result==q") && !within("result", "field:result"));
    }

    #[test]
    fn an_output_relation_for_an_identity_relation_reads_it_in_each_version() {
        let with = |observation: &str, holds: &str| Correspondence { inputs: Vec::new(), outputs: vec![super::super::Relation { observation: observation.into(), holds: holds.into() }] };
        let pairs = vec![("result".to_string(), "q".to_string()), ("result.amount".to_string(), "q.amount".to_string())];
        // Named either way round, read either way round, and negated with !=.
        let r = identity_relations(&with("identity:q==result", "old.result == old.q && new.q != new.result"), &pairs).unwrap();
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].pair, ("result".to_string(), "q".to_string()));
        assert_eq!(r[0].observation(), "identity:result==q");
        assert_eq!(r[0].reads, vec![true, false]);
        assert_eq!(r[0].text(&|previous| format!("{}", if previous { "OLD" } else { "NEW" })), "OLD && !NEW");
        assert!(r[0].eval(true, false).unwrap() && !r[0].eval(true, true).unwrap() && !r[0].eval(false, false).unwrap());
        // "Holds before iff it holds now", written out, and a relation of nested references.
        let iff = identity_relations(&with("identity:result.amount==q.amount", "(old.result.amount == old.q.amount) == (new.result.amount == new.q.amount)"), &pairs).unwrap();
        assert!(iff[0].eval(true, true).unwrap() && iff[0].eval(false, false).unwrap() && !iff[0].eval(true, false).unwrap());
        // Other output relations are someone else's.
        assert!(identity_relations(&with("result", "true"), &pairs).unwrap().is_empty());
        // Refused by name.
        let gap = |observation: &str, holds: &str| identity_relations(&with(observation, holds), &pairs).unwrap_err();
        assert!(gap("identity:result==l", "true").contains("names result == l, which is not an identity relation the check observes (result == q, result.amount == q.amount)"));
        assert!(gap("identity:result==q", "old.result.amount == old.q.amount").contains("reads old.result.amount == old.q.amount: an output relation for an identity relation reads only that relation in each version"));
        assert!(gap("identity:result==q", "old.result == new.q").contains("compares old.result with new.q: a reference is compared only with one of its own version"));
        assert!(gap("identity:result==q", "new.result").contains("reads new.result alone"));
        assert!(gap("identity:result==q", "old.q.quantity > 0").contains("reads old.q.quantity alone"));
        assert!(gap("identity:result==q", "1 + (new.result == new.q)").contains("is not one the harness compares"));
        assert!(gap("identity:result", "true").contains("names no identity relation"));
        let twice = Correspondence { inputs: Vec::new(), outputs: vec![super::super::Relation { observation: "identity:result==q".into(), holds: "true".into() }, super::super::Relation { observation: "identity:q==result".into(), holds: "true".into() }] };
        assert!(identity_relations(&twice, &pairs).unwrap_err().contains("is the second for q == result"));
    }

    #[test]
    fn an_output_relation_becomes_one_between_previous_and_result() {
        let with = |outputs: &[(&str, &str)]| Correspondence { inputs: Vec::new(), outputs: outputs.iter().map(|(o, h)| super::super::Relation { observation: (*o).into(), holds: (*h).into() }).collect() };
        assert_eq!(output_relation(&with(&[])).unwrap(), None);
        assert_eq!(output_relation(&with(&[("result", "old.result == new.result.amount.cents && new.n > 0")])).unwrap().as_deref(), Some("previous == result.amount.cents && n > 0"));
        // A word that only ends in old, a member after a dot, and a bare parameter are left alone.
        assert_eq!(output_relation(&with(&[("result", "Math.abs(old.result - new.result.cents) <= gold.length")])).unwrap().as_deref(), Some("Math.abs(previous - result.cents) <= gold.length"));
        // One for a parameter's field is the parameter's (relate), one for an identity relation the relation's
        // (identity_relations); one for an array parameter isn't supported.
        assert_eq!(output_relation(&with(&[("field:q.cents", "old.q.cents == new.q.amount.cents")])).unwrap(), None);
        assert_eq!(output_relation(&with(&[("identity:result==q", "new.result != new.q")])).unwrap(), None);
        assert!(output_relation(&with(&[("array:a", "true")])).unwrap_err().contains("only one for the result"));
        assert!(output_relation(&with(&[("result", "old.result == new.result"), ("result", "true")])).unwrap_err().contains("several output relations"));
        // The previous version's parameters (H5's rest), for the harness to resolve.
        assert_eq!(output_relation(&with(&[("result", "new.result.cents == old.q.cents * old.n")])).unwrap().as_deref(), Some("result.cents == before$q.cents * before$n"));
        assert!(output_relation(&with(&[("result", "old. == 1")])).unwrap_err().contains("reads old. without a name"));
    }
}
