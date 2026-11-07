//! The heap stream's interface (`llm-dlc/loops/foundations-heap.md`): a regression check over object inputs, under a
//! [`CanonicalClaim`]'s domain, observations and correspondence. Owned by that stream; until it does its part, every
//! call returns [`Unsupported`] naming it.

use std::path::Path;

use super::{Accounted, CanonicalClaim, Correspondence, Observation, ObservationState, Outcome, Part, Unsupported, Verdict};
use crate::harness::{field_steps, Corresponds, FieldEquation, RecordType};

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
/// unresolved, as it is when no JVM has run the witness too (step H4). A construction that needs more input objects than a version's bound leaves the result unresolved
/// rather than proving something outside the claim. Claims about effects (an environment model) are the
/// observations stream's, and refused.
pub fn check(claim: &CanonicalClaim, before: &Path, after: &Path) -> Result<Outcome, Unsupported> {
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
    let mut options = crate::equivalence::Options::new(before, after, subject);
    options.engine = crate::Engine::Native;
    options.gaps = if strict { crate::bmc::gaps::GapMode::Strict } else { crate::bmc::gaps::GapMode::Assume };
    options.unwind = claim.bounds.unwind;
    options.max_array_length = claim.bounds.max_array_length;
    options.timeout_seconds = DEADLINE_SECONDS;
    options.correspondence = claim.correspondence.clone();
    let required = &claim.contract.required;
    let unresolved_all = |domain: String, problem: String| Outcome {
        verdict: Verdict::Unresolved,
        domain,
        accounting: required.iter().map(|r| Accounted { observation: r.clone(), state: ObservationState::Unresolved }).collect(),
        witness: None,
        problem: Some(problem),
    };
    let checked = match crate::equivalence::run(&options) {
        Ok(o) => o,
        Err(e) => return Ok(unresolved_all(String::new(), format!("the check could not run: {e}"))),
    };
    let domain = checked.domain.clone().unwrap_or_default();
    let Some(stated) = &checked.stated else {
        // Refused before a statement: a named gap of the check.
        return Err(unsupported(checked.problem.unwrap_or_else(|| "refused".into())));
    };
    if let (Some(bounds), Some((old, new))) = (claim.domain.as_ref().map(|d| &d.bounds), stated.domain.input_objects) {
        for (version, needed, bound) in [("previous", old, bounds.before.input_objects), ("new", new, bounds.after.input_objects)] {
            if needed > bound {
                return Ok(unresolved_all(domain, format!("the {version} version's inputs are made of {needed} objects, more than the claim's bound of {bound}: the check would be about inputs outside the claim")));
            }
        }
    }
    let compared = compared_observations(stated);
    let is_compared = |id: &str| compared.iter().any(|c| same_id(c, id));
    match checked.verdict {
        crate::Verdict::Verified if checked.vacuous.is_some() => Ok(unresolved_all(domain, format!("vacuous: {}", checked.vacuous.unwrap_or_default()))),
        crate::Verdict::Verified => {
            let accounting: Vec<Accounted> = required.iter().map(|r| Accounted { observation: r.clone(), state: if is_compared(r) { ObservationState::Preserved } else { ObservationState::Unresolved } }).collect();
            let missing: Vec<&str> = accounting.iter().filter(|a| a.state == ObservationState::Unresolved).map(|a| a.observation.as_str()).collect();
            let (verdict, problem) = if missing.is_empty() { (Verdict::Verified, None) } else { (Verdict::Unresolved, Some(format!("the check does not compare {}", missing.join(", ")))) };
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
            let refuted: Vec<&String> = required.iter().filter(|r| cx.differs.iter().any(|d| same_id(d, r))).collect();
            let accounting: Vec<Accounted> = required.iter().map(|r| Accounted { observation: r.clone(), state: if refuted.contains(&r) { ObservationState::Refuted } else { ObservationState::Unresolved } }).collect();
            if refuted.is_empty() {
                let differs = if cx.differs.is_empty() { "observations the check does not tell apart".to_string() } else { cx.differs.join(", ") };
                return Ok(Outcome { verdict: Verdict::Unresolved, domain, accounting, witness: Some(witness), problem: Some(format!("the versions differ only in {differs}, which the claim does not require")) });
            }
            Ok(Outcome { verdict: Verdict::Refuted, domain, accounting, witness: Some(witness), problem: None })
        }
        crate::Verdict::Unverifiable => Ok(unresolved_all(domain, checked.problem.unwrap_or_else(|| "no verdict".into()))),
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

/// The observations a regression statement compares, by id: the result and the exception always (a void method's
/// result is nothing, alike in both), each array parameter, each object parameter's fields by path (`field:q.cents`,
/// under a correspondence the previous version's paths), and each identity relation.
fn compared_observations(stated: &crate::statement::Statement) -> Vec<String> {
    let o = &stated.observations;
    let mut out = vec![Observation::Result.id(), Observation::Exception.id()];
    out.extend(o.arrays.iter().map(|a| Observation::ArrayParameter { parameter: a.clone() }.id()));
    for object in &o.objects {
        let Some((name, rest)) = object.split_once(": ") else { continue };
        let paths: Vec<String> = match rest.strip_prefix("under the correspondence, ") {
            Some(equations) => equations.split(", ").filter_map(|e| e.split(" == ").next()?.strip_prefix(&format!("old.{name}.")).map(str::to_string)).collect(),
            None => rest.split(", ").map(str::to_string).collect(),
        };
        out.extend(paths.iter().map(|p| Observation::FieldPath { path: format!("{name}.{p}") }.id()));
        out.push(Observation::FieldPath { path: name.to_string() }.id());
    }
    out.extend(o.identities.iter().filter_map(|i| i.split_once(" == ")).map(|(x, y)| Observation::Identity { left: x.into(), right: y.into() }.id()));
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

/// The roots the correspondence's input equations are about, `q` for `old.q.cents == new.q.amount.cents`, with
/// each equation that is not one between two paths named as a gap.
pub(crate) fn roots(correspondence: &Correspondence) -> Result<Vec<(String, String, bool)>, String> {
    let mut out = Vec::new();
    for e in &correspondence.inputs {
        match (path_of(&e.old, "old"), path_of(&e.new, "new")) {
            (Some((old_root, old_path)), Some((new_root, new_path))) => out.push((old_root.to_string(), new_root.to_string(), old_path.is_empty() && new_path.is_empty())),
            _ => return Err(format!("the correspondence's input equation {} == {} is not one between two paths: only equations between a field path of the previous version's input and one of the new version's are supported yet", e.old, e.new)),
        }
    }
    Ok(out)
}

/// How the previous version's object for the parameter `old_name` (the new version's `new_name`) is made from the
/// new one's and compared with it, by the correspondence's input equations about it (H5's narrow case): each an
/// equation between a primitive field path of each, every leaf of the previous version's construction given by
/// one naming a leaf of the new one's, and every primitive field of the previous version's object in one, so that
/// none of the observations it was held to leaves the count. None when no equation is about it; `Err` names what is
/// not supported.
pub(crate) fn relate(correspondence: &Correspondence, old_name: &str, new_name: &str, new: &RecordType, old: &RecordType) -> Option<Result<Corresponds, String>> {
    let (Some(fields), Some(old_fields)) = (&new.fields, &old.fields) else { return None };
    let mut equations = Vec::new();
    for e in &correspondence.inputs {
        let (Some((old_root, old_path)), Some((new_root, new_path))) = (path_of(&e.old, "old"), path_of(&e.new, "new")) else { continue };
        if old_root != old_name {
            continue;
        }
        let text = format!("{} == {}", e.old, e.new);
        if new_root != new_name {
            return Some(Err(format!("the correspondence's input equation {text} relates the previous version's {old_name} to the new version's {new_root}; only equations between the two versions' same parameter are supported yet")));
        }
        let old_field = field_steps(old_fields, old_path).map(|(_, t)| t);
        let new_field = field_steps(fields, new_path).map(|(_, t)| t);
        match (old_field, new_field) {
            (Some(t), Some(u)) if t == u && t.is_primitive() => equations.push(FieldEquation { old: old_path.to_string(), new: new_path.to_string(), ty: t }),
            (Some(t), Some(u)) => return Some(Err(format!("the correspondence's input equation {text} relates a field of type {} to one of type {}; only equations between primitive fields of the same type are supported yet", t.java_name(), u.java_name()))),
            (None, _) => return Some(Err(format!("the correspondence's input equation {text} names {old_path}, which is not a primitive field path of the previous version's {} ({})", old.simple_name(), old_fields.paths().iter().map(|(p, _)| p.as_str()).collect::<Vec<_>>().join(", ")))),
            (_, None) => return Some(Err(format!("the correspondence's input equation {text} names {new_path}, which is not a primitive field path of the new version's {} ({})", new.simple_name(), fields.paths().iter().map(|(p, _)| p.as_str()).collect::<Vec<_>>().join(", ")))),
        }
    }
    if equations.is_empty() {
        return None;
    }
    if let Some((missing, _)) = old_fields.paths().into_iter().find(|(p, _)| !equations.iter().any(|e| e.old == *p)) {
        return Some(Err(format!("the previous version's {old_name}.{missing} is in no equation of the correspondence: what it held would leave the observations uncounted")));
    }
    let mut leaves = Vec::new();
    for (leaf, t) in &old.components {
        let given = equations.iter().find(|e| e.old == *leaf).and_then(|e| new.components.iter().position(|(c, u)| *c == e.new && u == t));
        match given {
            Some(i) => leaves.push(i),
            None => {
                let new_leaves = new.components.iter().map(|(c, _)| c.as_str()).collect::<Vec<_>>().join(", ");
                return Some(Err(format!("the previous version's {} is made from {old_name}.{leaf}, which no equation of the correspondence gives as a leaf of the new version's construction ({new_leaves}): only a correspondence that names how each of the previous version's constructor arguments is made from the new one's is supported yet", old.describe())));
            }
        }
    }
    Some(Ok(Corresponds { leaves, equations }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::classfile::Type;
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

    #[test]
    fn the_previous_object_is_made_from_the_leaves_its_equations_name() {
        let (new, old) = quotes();
        let c = correspondence(&[("old.q.cents", "new.q.amount.cents"), ("old.q.quantity", "new.q.quantity")]);
        let related = relate(&c, "q", "q", &new, &old).expect("about q").expect("supported");
        // The previous constructor takes (quantity, cents): the new leaves are (amount.cents, quantity).
        assert_eq!(related.leaves, vec![1, 0]);
        assert_eq!(related.equations[0], FieldEquation { old: "cents".into(), new: "amount.cents".into(), ty: Type::Long });
        assert!(relate(&c, "p", "p", &new, &old).is_none(), "no equation is about p");
    }

    #[test]
    fn what_the_narrow_case_does_not_cover_is_named() {
        let (new, old) = quotes();
        let gap = |pairs: &[(&str, &str)]| relate(&correspondence(pairs), "q", "q", &new, &old).expect("about q").expect_err("a gap");
        assert!(gap(&[("old.q.cents", "new.q.amount.cents")]).contains("q.quantity is in no equation"));
        assert!(gap(&[("old.q.cents", "new.q.quantity"), ("old.q.quantity", "new.q.quantity")]).contains("of type long to one of type int"));
        assert!(gap(&[("old.q.cents", "new.q.price"), ("old.q.quantity", "new.q.quantity")]).contains("not a primitive field path of the new version's Quote"));
        assert!(roots(&correspondence(&[("old.q.cents", "new.q.amount.cents + 1")])).unwrap_err().contains("not one between two paths"));
    }
}
