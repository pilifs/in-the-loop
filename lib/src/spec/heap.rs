//! The heap stream's interface (`llm-dlc/loops/foundations-heap.md`): a regression check over object inputs, under a
//! [`CanonicalClaim`]'s domain, observations and correspondence. Owned by that stream; until it does its part, every
//! call returns [`Unsupported`] naming it.

use std::path::Path;

use super::{Accounted, CanonicalClaim, Correspondence, Observation, ObservationState, Outcome, Part, Unsupported, Verdict};
use crate::harness::{field_steps, Computed, Corresponds, FieldEquation, Piece, Read, RecordType, Source};

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
/// correspondence's output relations is compared under it rather than for equality, so it stays unresolved until a
/// person approves the change in the contract. An input equation that computes a field of an input the contract anchors
/// (identity), rather than naming the field that holds it, is refused unless a person stated it in the input's
/// derivation ([`anchored`]). A construction that needs more input objects than a version's bound leaves the result unresolved
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
    if let Some(gap) = claim.correspondence.as_ref().and_then(|c| anchored(c, &claim.contract)) {
        return Err(unsupported(gap));
    }
    let mut options = crate::equivalence::Options::new(before, after, subject);
    options.engine = crate::Engine::Native;
    options.gaps = if strict { crate::bmc::gaps::GapMode::Strict } else { crate::bmc::gaps::GapMode::Assume };
    options.unwind = claim.bounds.unwind;
    options.max_array_length = claim.bounds.max_array_length;
    options.timeout_seconds = DEADLINE_SECONDS;
    options.correspondence = claim.correspondence.clone();
    // The domain's parameters that may be null or one object (step H2); a field of an input object that may be
    // null or shared is not made yet.
    if let Some(d) = &claim.domain {
        if let Some(path) = d.nullable.iter().chain(d.may_alias.iter().flat_map(|(a, b)| [a, b])).find(|p| p.contains('.')) {
            return Err(unsupported(format!("the domain's {path} is a field path: only parameters may be null or one object yet, a field being whatever its object's constructor makes it")));
        }
        options.nullable = d.nullable.clone();
        options.may_alias = d.may_alias.clone();
    }
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
    // A required observation an output relation compares in place of equality is held to something else than the
    // contract says: only a person's approved change makes that the claim. Without one it is unresolved, whatever
    // the check finds, so that no relation can make a difference disappear (`old.result == new.result - 1`) or
    // stand in for one.
    let related: Vec<&str> = claim.correspondence.iter().flat_map(|c| &c.outputs).map(|r| r.observation.as_str()).collect();
    let approved = |id: &str| claim.contract.approved_changes.iter().any(|a| same_id(&a.observation, id));
    let unapproved = |id: &str| related.iter().any(|r| same_id(r, id)) && !approved(id);
    match checked.verdict {
        crate::Verdict::Verified if checked.vacuous.is_some() => Ok(unresolved_all(domain, format!("vacuous: {}", checked.vacuous.unwrap_or_default()))),
        crate::Verdict::Verified => {
            let state = |r: &str| match () {
                _ if !is_compared(r) || unapproved(r) => ObservationState::Unresolved,
                _ if related.iter().any(|x| same_id(x, r)) => ObservationState::ChangedWithApproval,
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
            let refuted: Vec<&String> = required.iter().filter(|r| cx.differs.iter().any(|d| same_id(d, r)) && !unapproved(r)).collect();
            let accounting: Vec<Accounted> = required.iter().map(|r| Accounted { observation: r.clone(), state: if refuted.contains(&r) { ObservationState::Refuted } else { ObservationState::Unresolved } }).collect();
            if refuted.is_empty() {
                if let Some(r) = required.iter().find(|r| unapproved(r) && cx.differs.iter().any(|d| same_id(d, r))) {
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

/// The roots the correspondence's input equations are about, `q` for `old.q.cents == new.q.amount.cents`, and
/// whether the equation relates the two as a whole, with each equation not supported named as a gap. The previous
/// version's side is a field path; the new one's a field path, or an expression over field paths of one parameter
/// (H5's rest), `new.p.dollars * 100 + new.p.cents`.
pub(crate) fn roots(correspondence: &Correspondence) -> Result<Vec<(String, String, bool)>, String> {
    let mut out = Vec::new();
    for e in &correspondence.inputs {
        let Some((old_root, old_path)) = path_of(&e.old, "old") else {
            return Err(format!("the correspondence's input equation {} == {} does not have a field path of the previous version's input on its old side: only equations that give one, from a path or an expression over the new version's, are supported yet", e.old, e.new));
        };
        match path_of(&e.new, "new") {
            Some((new_root, new_path)) => out.push((old_root.to_string(), new_root.to_string(), old_path.is_empty() && new_path.is_empty())),
            None => out.push((old_root.to_string(), expression_root(e)?, false)),
        }
    }
    Ok(out)
}

/// The one parameter an expression on the new side reads, `p` for `new.p.dollars * 100 + new.p.cents`.
fn expression_root(e: &super::Equation) -> Result<String, String> {
    let pieces = new_pieces(&e.new).map_err(|why| format!("the correspondence's input equation {} == {} {why}", e.old, e.new))?;
    let mut roots: Vec<&str> = pieces.iter().filter_map(|p| p.as_ref().err().map(|(root, _)| root.as_str())).collect();
    roots.dedup();
    match roots.as_slice() {
        [root] => Ok(root.to_string()),
        [] => Err(format!("the correspondence's input equation {} == {} reads nothing of the new version's input: an equation gives the previous version's field from the new one's", e.old, e.new)),
        _ => Err(format!("the correspondence's input equation {} == {} reads several of the new version's parameters ({}): only an expression over one parameter's fields is supported yet", e.old, e.new, roots.join(", "))),
    }
}

/// The new side of an input equation as pieces: text as written (`Ok`), and each read of a field path of the new
/// version's input (`Err((root, path))`, `new.p.dollars` as `("p", "dollars")`). A read of the previous version's
/// input, or of a parameter as a whole, is refused.
fn new_pieces(text: &str) -> Result<Vec<Result<String, (String, String)>>, String> {
    let chars: Vec<char> = text.chars().collect();
    let identifier = |c: char| c.is_alphanumeric() || c == '_';
    let mut out: Vec<Result<String, (String, String)>> = Vec::new();
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
                if word == "old" {
                    return Err("reads the previous version's input: the new side is over the new version's".into());
                }
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
                if steps.len() < 2 {
                    return Err(format!("reads new.{} as a whole: only its primitive field paths are read", steps.join(".")));
                }
                if !plain.is_empty() {
                    out.push(Ok(std::mem::take(&mut plain)));
                }
                out.push(Err((steps[0].clone(), steps[1..].join("."))));
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
    path_of(&e.new, "new").is_none()
}

/// The correspondence's output relation as a result relation of the regression check (`--results-agree-when`'s
/// form): a boolean over `old.result` (the previous version's result), `new.result` (the new one's) and the new
/// version's parameters, `new.n` or `n`, which becomes one over `previous`, `result` and `n`. An object result is
/// in it by its field paths, `old.result.cents == new.result.amount.cents`. None without output relations; `Err`
/// names an output relation not supported yet: one about another observation than the result, several about it,
/// or one that reads the previous version's parameters.
pub(crate) fn output_relation(correspondence: &Correspondence) -> Result<Option<String>, String> {
    let result = Observation::Result.id();
    if let Some(r) = correspondence.outputs.iter().find(|r| r.observation != result) {
        return Err(format!("the correspondence's output relation for {} ({}) is not supported yet: only one for the result, over old.result, new.result and the new version's parameters", r.observation, r.holds));
    }
    let mut relations = correspondence.outputs.iter();
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
                    _ => return Err(format!("the correspondence's output relation {} reads old.{name}: an output relation over the previous version's parameters is not supported yet, only over old.result, new.result and the new version's parameters", relation.holds)),
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
/// object in one, so that none of the observations it was held to leaves the count. None when no equation is about
/// it; `Err` names what is not supported.
pub(crate) fn relate(correspondence: &Correspondence, old_name: &str, new_name: &str, new: &RecordType, old: &RecordType) -> Option<Result<Corresponds, String>> {
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
        if let Some((new_root, new_path)) = path_of(&e.new, "new") {
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
                Err((root, path)) => {
                    if root != new_name {
                        return Some(Err(format!("the correspondence's input equation {text} reads the new version's {root}, which is not the parameter in {old_name}'s place; only an expression over the same parameter's fields is supported yet")));
                    }
                    let Some((_, ty)) = field_steps(fields, &path).filter(|(_, ty)| ty.is_primitive()) else {
                        return Some(Err(format!("the correspondence's input equation {text} reads {path}, which is not a primitive field path of the new version's {} ({})", new.simple_name(), paths_of(fields))));
                    };
                    let Some(leaf) = new.components.iter().position(|(c, u)| *c == path && *u == ty) else {
                        return Some(Err(format!("the correspondence's input equation {text} reads {path}, which is not a leaf of the new version's construction ({}): an expression gives the previous version's argument from the new one's arguments", leaves_of())));
                    };
                    let at = match computed.reads.iter().position(|r| r.path == path) {
                        Some(at) => at,
                        None => {
                            computed.reads.push(Read { path, ty, leaf });
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
        assert_eq!(related.leaves, vec![Source::Leaf(1), Source::Leaf(0)]);
        assert_eq!(related.equations[0], FieldEquation { old: "cents".into(), new: "amount.cents".into(), ty: Type::Long, computed: None });
        assert!(relate(&c, "p", "p", &new, &old).is_none(), "no equation is about p");
    }

    #[test]
    fn what_the_narrow_case_does_not_cover_is_named() {
        let (new, old) = quotes();
        let gap = |pairs: &[(&str, &str)]| relate(&correspondence(pairs), "q", "q", &new, &old).expect("about q").expect_err("a gap");
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
        assert_eq!(roots(&c).unwrap(), vec![("p".to_string(), "p".to_string(), false)]);
        let related = relate(&c, "p", "p", &new, &old).expect("about p").expect("supported");
        let Source::Computed(e) = &related.leaves[0] else { panic!("computed: {related:?}") };
        assert_eq!(e.reads.iter().map(|r| (r.path.as_str(), r.leaf)).collect::<Vec<_>>(), vec![("dollars", 0), ("cents", 1)]);
        assert_eq!(e.eval(&[crate::interp::Value::Long(3), crate::interp::Value::Int(25)]).unwrap(), crate::interp::Value::Long(325));
        assert_eq!(related.equations[0].text("p", "p"), "old.p.cents == new.p.dollars * 100 + new.p.cents");
        assert_eq!(related.equations[0].new, "dollars * 100 + cents");
        // A path read twice is one read.
        let twice = relate(&correspondence(&[("old.p.cents", "new.p.cents + new.p.cents + new.p.dollars")]), "p", "p", &new, &old).unwrap().unwrap();
        let Source::Computed(e) = &twice.leaves[0] else { panic!() };
        assert_eq!(e.reads.len(), 2);
    }

    #[test]
    fn an_expression_the_harness_cannot_compute_is_named() {
        let (new, old) = prices();
        let gap = |old_side: &str, new_side: &str| {
            let c = correspondence(&[(old_side, new_side)]);
            match roots(&c) {
                Err(e) => e,
                Ok(_) => relate(&c, "p", "p", &new, &old).expect("about p").expect_err("a gap"),
            }
        };
        assert!(gap("old.p.cents", "new.p.dollars * 100 + old.p.cents").contains("reads the previous version's input"));
        assert!(gap("old.p.cents", "new.p.dollars + new.q.cents").contains("reads several of the new version's parameters (p, q)"));
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
    fn an_output_relation_becomes_one_between_previous_and_result() {
        let with = |outputs: &[(&str, &str)]| Correspondence { inputs: Vec::new(), outputs: outputs.iter().map(|(o, h)| super::super::Relation { observation: (*o).into(), holds: (*h).into() }).collect() };
        assert_eq!(output_relation(&with(&[])).unwrap(), None);
        assert_eq!(output_relation(&with(&[("result", "old.result == new.result.amount.cents && new.n > 0")])).unwrap().as_deref(), Some("previous == result.amount.cents && n > 0"));
        // A word that only ends in old, a member after a dot, and a bare parameter are left alone.
        assert_eq!(output_relation(&with(&[("result", "Math.abs(old.result - new.result.cents) <= gold.length")])).unwrap().as_deref(), Some("Math.abs(previous - result.cents) <= gold.length"));
        assert!(output_relation(&with(&[("field:q.cents", "old.q.cents == new.q.amount.cents")])).unwrap_err().contains("only one for the result"));
        assert!(output_relation(&with(&[("result", "old.result == new.result"), ("result", "true")])).unwrap_err().contains("several output relations"));
        assert!(output_relation(&with(&[("result", "old.result == old.q.cents")])).unwrap_err().contains("reads old.q"));
    }
}
