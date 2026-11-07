//! Field correspondence (step A4 of `llm-dlc/loops/foundations-alignment.md`): for a class both builds declare
//! whose fields changed (renamed, wrapped in a value object), an equation for each old field, giving it as a path
//! into the new object (`cents` is `amount.cents`). Static, like the rest of the module: a proposal with its
//! evidence unchecked, which only a regression proof under it settles.
//!
//! **From constructors.** The objects a comparison takes are made by constructors (the main brief's decision 2), so
//! the equations come from how each version's constructors route their parameters into fields:
//! - Each version's constructor is read for the fields it sets straight from a parameter (`this.f = p`, once, the
//!   parameter never reassigned). A constructor that delegates with `this(...)` or calls a method of its own class
//!   routes nothing: what it sets is not read here.
//! - The old constructor is paired with the new one the method correspondence matched to it ([`super::methods`]),
//!   and each old parameter is given as an expression over the new parameters by the same rules as a method's
//!   internal inputs (`super::mappings`): the same or a related name, the type, the position, a record component,
//!   an integral cast. Never arithmetic, so no equation can shift a value.
//! - An old field set from old parameter `p`, which maps to `q.c` over the new parameters, where the new constructor
//!   sets field `g` from `q`, is the new object's `g.c`.
//!
//! The equations relate internal state only: the object they describe is still the one input the contract names,
//! made from the same constructor arguments on both sides. A field no constructor sets from a parameter, or whose
//! new counterpart is set any other way, is named as unsupported, and no partial correspondence is proposed for it.
//! Several candidates for a field are a question, as for a method's input.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};

use super::mappings::{find, leads, param_leaves, primitive_candidates, rank, same_shape, Choice};
use super::{symbol, Build, MethodReport};
use crate::classfile::{ClassFile, Insn, Kind, Method, Type};

/// How one old field is made from the new object: candidate paths into it, best first.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FieldMapping {
    /// The old field's name.
    pub old: String,
    /// Paths into the new object (`amount.cents`), or an integral cast of one (`(int) count`).
    pub candidates: Vec<Choice>,
    /// Whether the first is proposed on its own. Otherwise it is a question.
    pub leads: bool,
}

/// The field correspondence of one class whose shape changed.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FieldCorrespondence {
    /// The class, by its Java name.
    pub class: String,
    /// The constructor pairs the equations come from: old symbol, new symbol.
    pub constructors: Vec<(String, String)>,
    /// One per old instance field, in declaration order.
    pub fields: Vec<FieldMapping>,
    /// New fields no leading equation reaches.
    pub free: Vec<String>,
    /// What this step can't relate.
    pub unsupported: Vec<String>,
}

impl FieldCorrespondence {
    /// Every old field has a candidate, and nothing is unsupported.
    pub fn complete(&self) -> bool {
        self.unsupported.is_empty() && !self.fields.is_empty() && self.fields.iter().all(|f| !f.candidates.is_empty())
    }
}

/// How a constructor sets one field.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Route {
    /// Straight from the parameter at this index.
    Parameter(usize),
    /// Any other way: computed, set twice, or from a parameter that was reassigned.
    Other,
}

fn parameters(class: &ClassFile, method: &Method) -> Option<Vec<(String, Type)>> {
    let d = method.parsed_descriptor().ok()?;
    let names = method.parameter_names(&class.pool);
    Some(d.params.iter().enumerate().map(|(i, t)| (names.get(i).cloned().unwrap_or_else(|| format!("arg{i}")), t.clone())).collect())
}

/// The fields a constructor sets, and how; `None` when it delegates with `this(...)`, calls a method of its own
/// class (which may set fields too), or can't be decoded.
fn routing(class: &ClassFile, ctor: &Method) -> Option<BTreeMap<String, Route>> {
    let params = parameters(class, ctor)?;
    let mut slots: BTreeMap<u16, usize> = BTreeMap::new();
    let mut next = 1u16;
    for (i, (_, t)) in params.iter().enumerate() {
        slots.insert(next, i);
        next += t.slots();
    }
    let insns: Vec<Insn> = ctor.code.as_ref()?.instructions().ok()?.into_iter().map(|(_, i)| i).collect();
    let reassigned: BTreeSet<u16> = insns.iter().filter_map(|i| if let Insn::Store(_, s) = i { Some(*s) } else { None }).collect();
    let mut out: BTreeMap<String, Route> = BTreeMap::new();
    for (k, insn) in insns.iter().enumerate() {
        match insn {
            Insn::InvokeSpecial(i) | Insn::InvokeVirtual(i) | Insn::InvokeInterface(i) => {
                let m = class.pool.member(*i).ok()?;
                let super_init = m.name == "<init>" && m.owner != class.name;
                if m.owner == class.name && !super_init {
                    return None;
                }
            }
            Insn::PutField(i) => {
                let m = class.pool.member(*i).ok()?;
                if m.owner != class.name {
                    continue;
                }
                let direct = match (k.checked_sub(2).map(|j| &insns[j]), k.checked_sub(1).map(|j| &insns[j])) {
                    (Some(Insn::Load(Kind::Ref, 0)), Some(Insn::Load(_, s))) if !reassigned.contains(s) => slots.get(s).copied(),
                    _ => None,
                };
                let route = match (out.contains_key(&m.name), direct) {
                    (false, Some(p)) => Route::Parameter(p),
                    _ => Route::Other,
                };
                out.insert(m.name, route);
            }
            _ => {}
        }
    }
    Some(out)
}

/// The instance fields of a class, in declaration order.
fn fields(class: &ClassFile) -> Vec<(String, Type)> {
    class.fields.iter().filter(|f| !f.is_static()).filter_map(|f| Some((f.name.clone(), Type::parse(&f.descriptor).ok()?))).collect()
}

/// An expression over the new constructor's parameters, rewritten over the new object's fields: the parameter it
/// starts with replaced by the field the constructor sets from it, and that field. `None` when no field is set
/// straight from it.
fn over_fields(expression: &str, params: &[(String, Type)], routes: &BTreeMap<String, Route>) -> Option<(String, String)> {
    let (cast, path) = match expression.strip_prefix('(').and_then(|r| r.split_once(") ")) {
        Some((t, rest)) => (Some(t), rest),
        None => (None, expression),
    };
    let (head, rest) = path.split_once('.').map_or((path, None), |(h, r)| (h, Some(r)));
    let index = params.iter().position(|(n, _)| n == head)?;
    let field = routes.iter().find(|(_, r)| **r == Route::Parameter(index)).map(|(f, _)| f.clone())?;
    let path = rest.map_or(field.clone(), |r| format!("{field}.{r}"));
    Some((cast.map_or(path.clone(), |t| format!("({t}) {path}")), field))
}

/// The field correspondence of the class `name` (internal name), when both builds declare it and its shape changed;
/// `None` otherwise.
pub fn correspondence(before: &Build, after: &Build, report: &MethodReport, name: &str) -> Option<FieldCorrespondence> {
    let (old, new) = (before.classes.get(name)?, after.classes.get(name)?);
    let t = Type::object(name);
    if same_shape(before, after, &t) {
        return None;
    }
    let mut out = FieldCorrespondence { class: t.java_name(), constructors: Vec::new(), fields: Vec::new(), free: Vec::new(), unsupported: Vec::new() };
    let old_fields = fields(old);
    let mut candidates: BTreeMap<String, Vec<Choice>> = BTreeMap::new();
    for ctor in old.methods.iter().filter(|m| m.is_constructor() && !m.is_synthetic()) {
        let before_symbol = symbol(old, ctor);
        let paired = match after.declares(name, "<init>", &ctor.descriptor) {
            Some((_, m)) => Some(m),
            None => report.methods.iter().find(|m| m.before == before_symbol).and_then(|m| m.leading()).and_then(|c| find(after, &c.after)).map(|(_, m)| m),
        };
        let Some(new_ctor) = paired else {
            out.unsupported.push(format!("the constructor {before_symbol} has no leading counterpart in the new build"));
            continue;
        };
        let after_symbol = symbol(new, new_ctor);
        let (Some(old_routes), Some(new_routes)) = (routing(old, ctor), routing(new, new_ctor)) else {
            out.unsupported.push(format!("{before_symbol} or {after_symbol} sets its fields through a call: not read here"));
            continue;
        };
        let (Some(old_params), Some(new_params)) = (parameters(old, ctor), parameters(new, new_ctor)) else { continue };
        let leaves = param_leaves(after, &new_params);
        out.constructors.push((before_symbol.clone(), after_symbol.clone()));
        for (field, _) in &old_fields {
            let Some(&Route::Parameter(i)) = old_routes.get(field) else { continue };
            let (pname, pty) = &old_params[i];
            let options: Vec<Choice> = if pty.is_primitive() {
                primitive_candidates(pname, pty, Some(i), &leaves, &BTreeSet::new())
            } else if same_shape(before, after, pty) {
                new_params
                    .iter()
                    .filter(|(_, u)| u == pty)
                    .map(|(n, _)| if n == pname { Choice { expression: n.clone(), score: 3, why: format!("the same name and type: {n}") } } else { Choice { expression: n.clone(), score: 1, why: format!("the same type: {n}") } })
                    .collect()
            } else {
                out.unsupported.push(format!("{field} is set from {pname}, a {} whose shape changed too: nested field correspondence is not done yet", pty.java_name()));
                continue;
            };
            let rewritten = options.into_iter().filter_map(|c| {
                let (path, set) = over_fields(&c.expression, &new_params, &new_routes)?;
                let why = format!("{before_symbol} sets {field} from its parameter {pname}; {after_symbol} takes it as {} ({}) and sets {set} from it", c.expression, c.why);
                Some(Choice { expression: path, score: c.score, why })
            });
            candidates.entry(field.clone()).or_default().extend(rewritten);
        }
    }
    for (field, _) in &old_fields {
        let found = rank(candidates.remove(field).unwrap_or_default());
        if found.is_empty() {
            out.unsupported.push(format!("no constructor sets {field} from a parameter that the new constructor stores in a field"));
        }
        let lead = leads(&found);
        out.fields.push(FieldMapping { old: field.clone(), candidates: found, leads: lead });
    }
    let reached: BTreeSet<String> = out
        .fields
        .iter()
        .filter(|f| f.leads)
        .map(|f| f.candidates[0].expression.rsplit(") ").next().unwrap_or_default().split('.').next().unwrap_or_default().to_string())
        .collect();
    out.free = fields(new).into_iter().map(|(n, _)| n).filter(|n| !reached.contains(n)).collect();
    Some(out)
}
