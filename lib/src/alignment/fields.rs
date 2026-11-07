//! Field correspondence (step A4 of `llm-dlc/loops/foundations-alignment.md`): for a class both builds declare
//! whose fields changed (renamed, wrapped in a value object), an equation for each old field, giving it as a path
//! into the new object (`cents` is `amount.cents`). Static, like the rest of the module: a proposal with its
//! evidence unchecked, which only a regression proof under it settles.
//!
//! **From constructors.** The objects a comparison takes are made by constructors (the main brief's decision 2), so
//! the equations come from how each version's constructors route their parameters into fields:
//! - Each version's constructor is read for the fields it sets straight from a parameter (`this.f = p`, once, the
//!   parameter never reassigned), or to a new object made from parameters passed straight
//!   (`this.amount = new Money(cents)`), whose own constructor is read the same way, to three levels: the
//!   parameter is stored at `amount.cents`. A constructor that delegates with `this(...)` or calls a method of its
//!   own class routes nothing: what it sets is not read here. A field of an object it makes that is set any other
//!   way (a constant, `new Money(cents * 2)`) is not set from a parameter, and is named.
//! - The old constructor is paired with the new one the method correspondence matched to it ([`super::methods`]),
//!   and each old parameter is given as an expression over the new parameters by the same rules as a method's
//!   internal inputs (`super::mappings`): the same or a related name, the type, the position, a record component,
//!   an integral cast. Never arithmetic, so no equation can shift a value.
//! - An old path set from old parameter `p`, which maps to `q.c` over the new parameters, where the new constructor
//!   stores `q` at `g`, is the new object's `g.c`. Old paths go inside objects too: an old `new Money(cents)`
//!   against a new primitive field is `old.amount.cents == new.cents`.
//!
//! **A method moved into the value object** ([`within`]): when the new method takes an object of the class a field
//! `g` of the new class holds (`Quote#cents` became `Money#cents`, and the new `Quote` keeps a `Money` in `amount`),
//! and the old method does nothing with its object but read fields the class's correspondence puts inside `g`, the
//! new object stands for the new `Quote`'s `g`: `old.this.cents == new.this.cents`. The old fields it never reads
//! are named, and no equation relates them; they don't reach its result.
//!
//! The equations relate internal state only: the object they describe is still the one input the contract names,
//! made from the same constructor arguments on both sides. A field no constructor sets from a parameter, or whose
//! new counterpart is set any other way, is named as unsupported, and no partial correspondence is proposed for it.
//! Several candidates for a field are a question, as for a method's input.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};

use super::mappings::{find, leads, param_leaves, primitive_candidates, rank, same_shape, Choice};
use super::{symbol, Build, MethodReport};
use crate::classfile::{ClassFile, Insn, Kind, Method, MethodDescriptor, Type};

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
    /// For a method moved into a value object: the field of the new class that holds the object the new method
    /// takes in the old one's place, which the equations' paths start inside ([`within`]).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub within: Option<String>,
    /// The old fields the old method never reads, so no equation relates them ([`within`]).
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub unread: Vec<String>,
}

impl FieldCorrespondence {
    /// Every old field has a candidate, and nothing is unsupported.
    pub fn complete(&self) -> bool {
        self.unsupported.is_empty() && !self.fields.is_empty() && self.fields.iter().all(|f| !f.candidates.is_empty())
    }
}

/// How a constructor sets one field.
#[derive(Debug, Clone, PartialEq, Eq)]
enum Route {
    /// Straight from the parameter at this index.
    Parameter(usize),
    /// To a new object, `new C(p, q, ...)`, of the class `class` (internal name), made with the constructor
    /// `descriptor` from parameters passed straight: the parameter index of each argument.
    Construct { class: String, descriptor: String, args: Vec<usize> },
    /// Any other way: computed, set twice, or from a parameter that was reassigned.
    Other,
}

/// How deep [`stored`] follows objects a constructor makes: a field's value object, and one inside it.
const DEPTH: usize = 3;

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
                    (Some(Insn::Load(Kind::Ref, 0)), Some(Insn::Load(_, s))) if !reassigned.contains(s) => slots.get(s).copied().map(Route::Parameter),
                    _ => constructed(class, &insns[..k], &slots, &reassigned),
                };
                let route = match (out.contains_key(&m.name), direct) {
                    (false, Some(r)) => r,
                    _ => Route::Other,
                };
                out.insert(m.name, route);
            }
            _ => {}
        }
    }
    Some(out)
}

/// The value a `putfield` stores, when the instructions before it are `aload_0; new C; dup; <a parameter loaded
/// straight, per argument>; invokespecial C.<init>`: a new object made from parameters only, nothing computed.
fn constructed(class: &ClassFile, before: &[Insn], slots: &BTreeMap<u16, usize>, reassigned: &BTreeSet<u16>) -> Option<Route> {
    let (Insn::InvokeSpecial(i), rest) = before.split_last()? else { return None };
    let m = class.pool.member(*i).ok()?;
    if m.name != "<init>" || m.owner == class.name {
        return None;
    }
    let n = MethodDescriptor::parse(&m.descriptor).ok()?.params.len();
    let (rest, loads) = rest.split_at(rest.len().checked_sub(n)?);
    let args = loads
        .iter()
        .map(|insn| match insn {
            Insn::Load(_, s) if !reassigned.contains(s) => slots.get(s).copied(),
            _ => None,
        })
        .collect::<Option<Vec<usize>>>()?;
    match rest {
        [.., Insn::Load(Kind::Ref, 0), Insn::New(c), Insn::Dup] if class.pool.class_name(*c).ok()? == m.owner => Some(Route::Construct { class: m.owner, descriptor: m.descriptor, args }),
        _ => None,
    }
}

/// Where a constructor of `class` stores its parameters: each a path into the object it makes (`amount.cents`) and
/// the parameter's index, following the objects it makes with `new C(...)` of a class of `build` into what their
/// own constructors store, to [`DEPTH`] levels. Paths it sets any other way, or into an object it doesn't follow,
/// are in the second list. `None` when a constructor on the way sets its fields through a call.
fn stored(build: &Build, class: &ClassFile, ctor: &Method, depth: usize) -> Option<(Vec<(String, usize)>, Vec<String>)> {
    let (mut paths, mut other) = (Vec::new(), Vec::new());
    for (field, route) in routing(class, ctor)? {
        match route {
            Route::Parameter(i) => paths.push((field, i)),
            Route::Construct { class: inner, descriptor, args } if depth > 1 => {
                let Some((c, m)) = build.declares(&inner, "<init>", &descriptor) else {
                    other.push(format!("{field} (a new {}, not a class of the build)", Type::object(&inner).java_name()));
                    continue;
                };
                let (inner_paths, inner_other) = stored(build, c, m, depth - 1)?;
                // A field of the inner object that its constructor never sets keeps its default: not a parameter.
                let set: BTreeSet<&str> = inner_paths.iter().map(|(p, _)| p.as_str()).chain(inner_other.iter().map(String::as_str)).map(|p| p.split(['.', ' ']).next().unwrap_or_default()).collect();
                let unset: Vec<String> = fields(c).into_iter().filter(|(n, _)| !set.contains(n.as_str())).map(|(n, _)| format!("{field}.{n} (never set by {})", symbol(c, m))).collect();
                paths.extend(inner_paths.into_iter().map(|(p, j)| (format!("{field}.{p}"), args[j])));
                other.extend(inner_other.into_iter().map(|p| format!("{field}.{p}")));
                other.extend(unset);
            }
            _ => other.push(field),
        }
    }
    Some((paths, other))
}

/// The instance fields of a class, in declaration order.
fn fields(class: &ClassFile) -> Vec<(String, Type)> {
    class.fields.iter().filter(|f| !f.is_static()).filter_map(|f| Some((f.name.clone(), Type::parse(&f.descriptor).ok()?))).collect()
}

/// An expression over the new constructor's parameters, rewritten over the new object: the parameter it starts with
/// replaced by each path the constructor stores it at ([`stored`]). Empty when it stores it nowhere straight.
fn over_paths(expression: &str, params: &[(String, Type)], stored: &[(String, usize)]) -> Vec<String> {
    let (cast, path) = match expression.strip_prefix('(').and_then(|r| r.split_once(") ")) {
        Some((t, rest)) => (Some(t), rest),
        None => (None, expression),
    };
    let (head, rest) = path.split_once('.').map_or((path, None), |(h, r)| (h, Some(r)));
    let Some(index) = params.iter().position(|(n, _)| n == head) else { return Vec::new() };
    stored
        .iter()
        .filter(|(_, i)| *i == index)
        .map(|(at, _)| {
            let path = rest.map_or(at.clone(), |r| format!("{at}.{r}"));
            cast.map_or(path.clone(), |t| format!("({t}) {path}"))
        })
        .collect()
}

/// A path with its cast, if any, taken off: `amount.cents` of `(int) amount.cents`.
fn uncast(expression: &str) -> &str {
    expression.rsplit(") ").next().unwrap_or_default()
}

/// The field correspondence of the class `name` (internal name), when both builds declare it and its shape changed;
/// `None` otherwise.
pub fn correspondence(before: &Build, after: &Build, report: &MethodReport, name: &str) -> Option<FieldCorrespondence> {
    let (old, new) = (before.classes.get(name)?, after.classes.get(name)?);
    let t = Type::object(name);
    if same_shape(before, after, &t) {
        return None;
    }
    let mut out = FieldCorrespondence { class: t.java_name(), constructors: Vec::new(), fields: Vec::new(), free: Vec::new(), unsupported: Vec::new(), within: None, unread: Vec::new() };
    // Each old path a constructor stores a parameter at, with its candidates, in the order first met.
    let mut candidates: Vec<(String, Vec<Choice>)> = Vec::new();
    let (mut old_other, mut new_stored): (Vec<String>, BTreeSet<String>) = (Vec::new(), BTreeSet::new());
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
        let (Some((old_paths, other)), Some((new_paths, _))) = (stored(before, old, ctor, DEPTH), stored(after, new, new_ctor, DEPTH)) else {
            out.unsupported.push(format!("{before_symbol} or {after_symbol} sets its fields through a call: not read here"));
            continue;
        };
        let (Some(old_params), Some(new_params)) = (parameters(old, ctor), parameters(new, new_ctor)) else { continue };
        let leaves = param_leaves(after, &new_params);
        out.constructors.push((before_symbol.clone(), after_symbol.clone()));
        old_other.extend(other);
        new_stored.extend(new_paths.iter().map(|(p, _)| p.clone()));
        for (path, i) in old_paths {
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
                out.unsupported.push(format!("{path} is set from {pname}, a {} whose shape changed too: nested field correspondence is not done yet", pty.java_name()));
                continue;
            };
            let rewritten: Vec<Choice> = options
                .iter()
                .flat_map(|c| {
                    over_paths(&c.expression, &new_params, &new_paths).into_iter().map(|at| {
                        let why = format!("{before_symbol} sets {path} from its parameter {pname}; {after_symbol} takes it as {} ({}) and stores it at {}", c.expression, c.why, uncast(&at));
                        Choice { expression: at, score: c.score, why }
                    })
                })
                .collect();
            match candidates.iter_mut().find(|(p, _)| *p == path) {
                Some((_, found)) => found.extend(rewritten),
                None => candidates.push((path, rewritten)),
            }
        }
    }
    // One mapping per old path, by the declaration order of the field it starts at.
    for (field, _) in fields(old) {
        let mine: Vec<(String, Vec<Choice>)> = candidates.iter().filter(|(p, _)| *p == field || p.starts_with(&format!("{field}."))).cloned().collect();
        if mine.is_empty() {
            out.unsupported.push(format!("no constructor sets {field} from a parameter that the new constructor stores in a field"));
            out.fields.push(FieldMapping { old: field, candidates: Vec::new(), leads: false });
            continue;
        }
        for (path, found) in mine {
            let found = rank(found);
            if found.is_empty() {
                out.unsupported.push(format!("no constructor sets {path} from a parameter that the new constructor stores in a field"));
            }
            let lead = leads(&found);
            out.fields.push(FieldMapping { old: path, candidates: found, leads: lead });
        }
    }
    // What an old object holds that no constructor sets from a parameter (inside an object it makes) can't be related.
    for other in old_other {
        let at = other.split(' ').next().unwrap_or_default();
        if at.contains('.') && !out.fields.iter().any(|f| f.old == at) {
            out.unsupported.push(format!("{other}: not set from a parameter, so not related"));
        }
    }
    out.unsupported.dedup();
    let reached: BTreeSet<&str> = out.fields.iter().filter(|f| f.leads).map(|f| uncast(&f.candidates[0].expression)).collect();
    let head = |p: &str| p.split('.').next().unwrap_or_default().to_string();
    let heads: BTreeSet<String> = reached.iter().map(|p| head(p)).collect();
    out.free = fields(new).into_iter().map(|(n, _)| n).filter(|n| !heads.contains(n)).collect();
    // Inside an object the new constructor makes, a path no old one reaches is free too.
    out.free.extend(new_stored.into_iter().filter(|p| p.contains('.') && heads.contains(&head(p)) && !reached.iter().any(|r| r == p || r.starts_with(&format!("{p}.")))));
    Some(out)
}

/// The fields of the object in local `slot`, of class `owner` (internal name), that a method reads, when reading
/// them (`aload; getfield`) is all it does with it: no call on it, nothing stored over it, not passed on or
/// returned. `None` otherwise.
pub fn reads(class: &ClassFile, method: &Method, owner: &str, slot: u16) -> Option<BTreeSet<String>> {
    let insns: Vec<Insn> = method.code.as_ref()?.instructions().ok()?.into_iter().map(|(_, i)| i).collect();
    let mut out = BTreeSet::new();
    for (k, insn) in insns.iter().enumerate() {
        match insn {
            Insn::Store(_, s) if *s == slot => return None,
            Insn::Load(Kind::Ref, s) if *s == slot => match insns.get(k + 1) {
                Some(Insn::GetField(i)) => {
                    let m = class.pool.member(*i).ok()?;
                    if m.owner != owner {
                        return None;
                    }
                    out.insert(m.name);
                }
                _ => return None,
            },
            _ => {}
        }
    }
    Some(out)
}

/// A method moved into the value object its class now keeps (`Quote#cents` to `Money#cents`): for an old input of
/// the class `name` (internal name), whose shape changed, of which the old method reads the fields `read` and
/// nothing else, the field `g` of the new class that every field read is kept inside, `g`'s class (internal name),
/// and the fields read as paths into it. An object of that class, taken by the new method, stands for the new
/// object's `g`: `old.cents == new.amount.cents` in the class becomes `old.this.cents == new.this.cents` for the
/// pair. The fields the old method doesn't read are named, and no equation relates them. `Err` says why not.
pub fn within(before: &Build, after: &Build, report: &MethodReport, name: &str, read: &BTreeSet<String>) -> Result<(String, String, FieldCorrespondence), String> {
    let fc = correspondence(before, after, report, name).ok_or_else(|| "its shape is unchanged".to_string())?;
    if !fc.unsupported.is_empty() {
        return Err(format!("its fields can't all be related: {}", fc.unsupported.join("; ")));
    }
    if read.is_empty() {
        return Err("the old method reads none of its fields".into());
    }
    let mut held: Option<String> = None;
    let mut fields = Vec::new();
    for f in fc.fields.iter().filter(|f| read.contains(&f.old)) {
        if !f.leads {
            return Err(format!("{} has several candidates in the new {}: a question about the class first", f.old, fc.class));
        }
        let c = &f.candidates[0];
        let (cast, path) = match c.expression.strip_prefix('(').and_then(|r| r.split_once(") ")) {
            Some((t, rest)) => (Some(t), rest),
            None => (None, c.expression.as_str()),
        };
        let Some((g, rest)) = path.split_once('.') else {
            return Err(format!("{} is the new {}'s own field {path}, not inside one it keeps", f.old, fc.class));
        };
        if held.as_deref().is_some_and(|h| h != g) {
            return Err(format!("the fields it reads are kept in different fields of the new {}: {} and {g}", fc.class, held.unwrap_or_default()));
        }
        held = Some(g.to_string());
        let expression = cast.map_or(rest.to_string(), |t| format!("({t}) {rest}"));
        fields.push(FieldMapping { old: f.old.clone(), candidates: vec![Choice { expression, score: c.score, why: format!("{}; the new {} keeps {g}, and {rest} is inside it", c.why, fc.class) }], leads: true });
    }
    if let Some(f) = read.iter().find(|f| !fields.iter().any(|m| &m.old == *f)) {
        return Err(format!("it reads {f}, an object the new {} keeps in another shape: not related here", fc.class));
    }
    let g = held.expect("a field was read");
    let class = after.classes.get(name).and_then(|c| c.fields.iter().find(|f| f.name == g)).and_then(|f| Type::parse(&f.descriptor).ok()).and_then(|t| t.class_name().map(str::to_string));
    let Some(class) = class else {
        return Err(format!("the new {}'s field {g} is not an object", fc.class));
    };
    let unread = before.classes.get(name).map(fields_of).unwrap_or_default().into_iter().filter(|f| !read.contains(f)).collect();
    let out = FieldCorrespondence { class: fc.class, constructors: fc.constructors, fields, free: Vec::new(), unsupported: Vec::new(), within: Some(g.clone()), unread };
    Ok((g, class, out))
}

fn fields_of(class: &ClassFile) -> Vec<String> {
    fields(class).into_iter().map(|(n, _)| n).collect()
}
