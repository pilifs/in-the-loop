//! The environment stream's module (`llm-dlc/loops/application-core-environment.md`): modelled dependency outcomes
//! ([`CallModel`]): consumed primitive returns, modelled failures, and constructor-made nullable DTOs, under one
//! declared environment for both versions. Registered by Phase 0 of `llm-dlc/loops/application-core.md`, so that
//! the stream starts without editing a shared file. The effect check (`effects`) encodes what [`lower`] accepts; any
//! other model is refused by name, never checked as a normal return.
//!
//! # The coupling policy
//!
//! A model says what the results of a call are a function of, and how they are related across calls and across the
//! two versions. The two couplings are different models of a dependency, not two encodings of one:
//!
//! - **A deterministic read-only query** ([`Coupling::Query`], built). The dependency answers from one declared
//!   snapshot that neither version writes. Its result is a function of the call's key (the `key` paths, in order)
//!   and of nothing else: the same function in both versions, and for every call of either. So two calls with equal
//!   keys get equal results, in one version or across the two, and two calls with different keys get independent
//!   results, whatever their positions: a version that asks for another key, or asks in another order, is checked
//!   against what that key's answer is, never handed the answer the other version got at the same position. The
//!   function is any function: the check covers every snapshot, with no assumption about how results of different
//!   keys relate. Stateless: a read after a write of the same store needs a contract for its state transitions,
//!   which this isn't, and a method's name is never taken for one.
//! - **A declared nondeterministic or fallible operation** ([`Coupling::Choice`]). Each call chooses among the
//!   permitted results, so two calls with equal keys may get different results, in one version or across the two.
//!   What makes it one environment for both versions is its occurrence policy:
//!   - **per call** ([`Occurrence::PerCall`], built): the choice is a function of the call's key and of the
//!     occurrence of that key in the trace (the first call of `arg0 = 3`, the second, ...), the same function in
//!     both versions. So the n-th call of a key in one version gets what the n-th call of the same key gets in the
//!     other, whatever their positions among other keys' calls: a version that reads a key once more than the other
//!     is checked against an independent answer, never handed the first one again, and different keys are never
//!     coupled by position;
//!   - **a finite script** ([`Occurrence::Script`]): the brief's optional work, refused by name.
//!
//! **How a query is encoded** ([`Lowered`]). Both versions get the same symbolic table of `2 × bound` entries, each
//! a key and its result, and one default result: a call's result is the first entry's whose key equals the call's,
//! or the default. The table is part of the check's inputs, the same for both versions, so it is a function and the
//! same one. It is complete within the bound: each version makes at most `bound` calls of the model in a trace
//! (one more leaves the result unresolved, never a shorter trace), so the two together ask for at most `2 × bound`
//! keys, and any function on those keys is one choice of the table. And it is sound: every choice of the table is a
//! function of the key, so a counterexample is one environment, which the witness names and the JVM replays under
//! the generated stubs.
//!
//! **How a per-call choice is encoded**: the same table, each entry used once per trace. A call's result is the first
//! entry's whose key equals the call's and that no earlier call of this trace used, or the default. So the n-th call
//! of a key takes the n-th entry of that key, in both versions alike: the result is a function of the key and its
//! occurrence. Complete within the bound: the two versions' calls are at most `2 × bound` pairs of a key and an
//! occurrence, and a key's occurrences up to n are all among them, so any function on the pairs is a table that
//! lists each key's answers in the order of its occurrences. Sound: every table is such a function.
//!
//! **Modelled failures** ([`ModelledResult::Throws`]): a model may give, beside its one normal result, a bounded
//! list of exception classes, checked ones (`java.io.IOException`) included. Each entry of the table, and the
//! default, then also holds an outcome: 0 (or any value but those below) the normal result, `k` a throw of the
//! `k`-th class. So which outcome a call gets is part of the same function of the key (and, under a per-call choice,
//! of its occurrence) as its value, for both versions alike: a version that drops a catch, or emits on the wrong
//! branch of one, is checked against the same failure. The exception is made by its class's constructor without
//! arguments: it carries its class, and no message, cause or stack the dependency would give. So a caller that
//! reads anything of a caught modelled exception but its class (its message, its cause, or by handing it to code
//! that may) is refused by the effect check, never given an invented one. A call that returns nothing may be
//! modelled this way too: its only choice is whether it fails.
//!
//! **What the key can be**, so far: a primitive integral or boolean argument (`arg0`), or a String argument, the
//! values stream's String: its table keys are Strings of at most the check's String bound (the claim's
//! `max_array_length`), any content, never null, and the stub compares a call's key with them by content
//! (`String.equals`). A call keyed by a longer String marks the log unresolved, since no entry holds such a key and
//! answering it as the default would couple two such keys. A field path (`arg1.code`) or an object's identity is
//! refused by name. The normal result: an integral or boolean primitive, nothing beside a modelled failure, or a
//! DTO. A value of an adapter's domain is refused, once its domain resolves under this tool's models
//! (`values::resolve`): no stub makes one.
//!
//! **A method's claim** ([`check`], the quote family's E1 and E2 rows): an ordinary method whose receiver and
//! parameters its planned domain makes, each dependency the model stands for null and answered by the stubs, is
//! checked by the effect check's planned entry ([`crate::effects::check_planned`]).
//!
//! **DTO responses** (E3, [`Returned::Object`], [`Response`]): the normal result may be an object of an application
//! class, made by the one node of a construction plan (the objects stream's, [`crate::construction::root`]) by the
//! constructor it names, from primitive leaves named by their path from the plan's root (`result.unitCents`), or
//! null where the model says `nullable`. Each answer of the table is then its null flag and its leaves, a function
//! of the key like any answer. Its identity is the model's, never assumed: under a **fresh** identity every call
//! that gets an answer gets a new object; under a **stable** one, every call that gets the same entry's answer gets
//! the same object, within a trace (a query only: under a per-call choice no entry answers twice). The class must be
//! data ([`check_response`]): instance fields of primitive types, no static field, no method beside its
//! constructors; and no build may call a method on it, write its field, or call Object's identity-dependent methods
//! where it handles one (the effect check's inspection). An object inside a DTO, an array or String field, a
//! factory, a dependency or a setup call in its plan are refused by name. A response its constructor won't make from
//! the chosen leaves marks the log unresolved: it is no response the dependency gives, never the constructor's
//! exception passed off as the dependency's.

use std::path::Path;

use crate::classfile::{MethodDescriptor, Type};
use crate::spec::plans::{CallModel, ConstructionPlan, Coupling, Identity, Maker, ModelledResult, Occurrence, PlanValue, Returned};
use crate::spec::{ModeledCall, Part, Unsupported};

/// The most calls of one model a trace may make that the effect check encodes: the table has twice as many
/// entries, each compared with every call.
pub const MAX_BOUND: u32 = 8;

/// A call's model as the effect check encodes it: a table of keys and results, read as a query or a per-call choice.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Lowered {
    /// The model's stable id, the same in both versions.
    pub id: String,
    /// The key's components, in order: the call's parameter each is (0 for `arg0`), and its type.
    pub key: Vec<(usize, Type)>,
    /// The type of the normal result: an integral or boolean primitive, or void beside a modelled failure.
    pub ret: Type,
    /// The exception classes a call may throw instead (internal names), in the model's order: the outcome `k`
    /// throws the `k`-th, from 1.
    pub throws: Vec<String>,
    /// The most calls of it one trace may make.
    pub bound: u32,
    /// A per-call choice ([`Occurrence::PerCall`]): each entry answers one call per trace, so a result is a function of
    /// the key and its occurrence. Otherwise a query: the first entry of the key answers every call of it.
    pub per_call: bool,
    /// When the normal result is a DTO (E3), how its stub makes it; `ret` is then its class.
    pub response: Option<Response>,
}

/// A DTO response (E3, [`Returned::Object`]): an object of an application class made by the one node of its
/// construction plan, by the constructor the node names, from primitive leaves, or null when the model allows it.
/// Each entry of the table holds the answer's leaves (and its null flag); a fresh identity makes a new object for
/// every call that gets the answer, a stable one the same object for every call that gets that entry's answer,
/// within a trace. The class is checked in each build by the objects stream's plan ([`check_response`]).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Response {
    /// The class, an internal name (`offers/Offer`).
    pub class: String,
    /// The constructor's descriptor (`(JI)V`).
    pub descriptor: String,
    /// The plan's root (`result`), the name its leaves are paths from.
    pub root: String,
    /// The constructor's arguments, in order: each leaf's name below the root (`unitCents`) and its type.
    pub leaves: Vec<(String, Type)>,
    /// Whether an answer may be null instead.
    pub nullable: bool,
    /// [`Identity::Stable`]: one object per entry, the same for every call it answers.
    pub stable: bool,
    /// The plan the class is checked under in each build.
    pub plan: ConstructionPlan,
}

impl Response {
    /// The class as Java names it, without its package: `Offer`.
    pub fn simple(&self) -> &str {
        self.class.rsplit('/').next().unwrap_or(&self.class)
    }

    /// How it is made, in words.
    fn words(&self) -> String {
        let class = self.class.replace('/', ".");
        let leaves = self.leaves.iter().map(|(n, _)| n.as_str()).collect::<Vec<_>>().join(", ");
        let made = format!("{class} made by its constructor {} from the leaves ({leaves})", self.descriptor);
        let identity = if self.stable { format!("one {made} per answer, the same object for every call that gets that entry's answer") } else { format!("a new {made} for every call") };
        if self.nullable { format!("{identity}, or null") } else { identity }
    }
}

impl Lowered {
    /// The table's entries: enough for two traces of `bound` calls each, every key different.
    pub fn entries(&self) -> usize {
        2 * self.bound as usize
    }

    /// The key's components named as the model names them: `arg0`.
    pub fn key_names(&self) -> Vec<String> {
        self.key.iter().map(|(p, _)| format!("arg{p}")).collect()
    }

    /// The answer's inputs, in order: its value, unless the call returns nothing, then its outcome, when the model
    /// has failures.
    fn answer_inputs(&self) -> Vec<Type> {
        let mut out = Vec::new();
        if let Some(r) = &self.response {
            if r.nullable {
                out.push(Type::Int);
            }
            out.extend(r.leaves.iter().map(|(_, t)| t.clone()));
        } else if self.ret != Type::Void {
            out.push(self.ret.clone());
        }
        if !self.throws.is_empty() {
            out.push(Type::Int);
        }
        out
    }

    /// The check's inputs the table is: for each entry its key's components, then its answer (value, outcome);
    /// then the default answer.
    pub fn inputs(&self) -> Vec<Type> {
        let mut out = Vec::new();
        for _ in 0..self.entries() {
            out.extend(self.key.iter().map(|(_, t)| t.clone()));
            out.extend(self.answer_inputs());
        }
        out.extend(self.answer_inputs());
        out
    }

    /// The names of [`Lowered::inputs`], as a proof or a search names them: `rates.rate[0].arg0`, `rates.rate[0]`,
    /// `rates.rate[0].outcome`, ..., `rates.rate.default`, `rates.rate.default.outcome`. A DTO's answer is its null
    /// flag and its leaves: `offers.find[0].null`, `offers.find[0].unitCents`.
    pub fn input_names(&self) -> Vec<String> {
        let answer = |at: String| {
            let mut out = Vec::new();
            if let Some(r) = &self.response {
                if r.nullable {
                    out.push(format!("{at}.null"));
                }
                out.extend(r.leaves.iter().map(|(n, _)| format!("{at}.{n}")));
            } else if self.ret != Type::Void {
                out.push(at.clone());
            }
            if !self.throws.is_empty() {
                out.push(format!("{at}.outcome"));
            }
            out
        };
        let mut out = Vec::new();
        for e in 0..self.entries() {
            out.extend(self.key_names().iter().map(|k| format!("{}[{e}].{k}", self.id)));
            out.extend(answer(format!("{}[{e}]", self.id)));
        }
        out.extend(answer(format!("{}.default", self.id)));
        out
    }

    /// The class an outcome throws (internal name), or `None` for the normal result.
    pub fn thrown(&self, outcome: i64) -> Option<&str> {
        usize::try_from(outcome).ok().filter(|k| (1..=self.throws.len()).contains(k)).map(|k| self.throws[k - 1].as_str())
    }

    /// The outcomes, in words: `any long, or a throw of java.io.IOException (...)`; without `any`, as the codomain
    /// of a function (`long, or a throw of ...`).
    fn outcomes(&self, any: bool) -> String {
        let normal = match (&self.ret, any) {
            _ if self.response.is_some() => self.response.as_ref().unwrap().words(),
            (Type::Void, _) => "a normal return".to_string(),
            (t, true) => format!("any {}", t.java_name()),
            (t, false) => t.java_name(),
        };
        if self.throws.is_empty() {
            return normal;
        }
        let thrown: Vec<String> = self.throws.iter().map(|c| c.replace('/', ".")).collect();
        format!("{normal}, or a throw of {} (made with no arguments: its class, and no message or cause)", thrown.join(" or "))
    }

    /// What the result rests on, in words.
    pub fn assumption(&self, call: &str) -> String {
        let (id, key, ty, bound) = (&self.id, self.key_names().join(", "), self.outcomes(true), self.bound);
        if self.per_call {
            format!("{call} is a generated stub in both builds, answering from the environment model {id}: a declared nondeterministic operation, chosen per call: {ty} for each call, the same choice in both builds for the same ({key}) and the same occurrence of it in the trace, so calls with equal keys may get different results and calls with different keys are never coupled by position; at most {bound} calls of it in a trace, one more leaves the result unresolved")
        } else {
            format!("{call} is a generated stub in both builds, answering from the environment model {id}: a deterministic read-only query of one declared snapshot, the same function in both builds, of ({key}) only: calls with equal keys get equal results and calls with different keys independent ones, never by position; {ty} for any key; at most {bound} calls of it in a trace, one more leaves the result unresolved")
        }
    }

    /// What a stub returns, in the effect-log plan's words.
    pub fn returns(&self) -> String {
        let (id, key, ty) = (&self.id, self.key_names().join(", "), self.outcomes(true));
        if self.per_call {
            format!("{ty}, chosen per call, the same in both builds for the same ({key}) and occurrence of it ({id})")
        } else {
            format!("{ty}, as a function of ({key}), the same in both builds ({id})")
        }
    }

    /// The part of the domain the model's answers are, in words.
    pub fn domain(&self, call: &str) -> String {
        let (id, key, bound) = (&self.id, self.key_names().join(", "), self.bound);
        if self.per_call {
            format!("{call} ({id}): {} per call, chosen alike for the same ({key}) and occurrence of it, within {bound} calls of it per trace", self.outcomes(true))
        } else {
            format!("{call} ({id}): any function of ({key}) to {}, within {bound} calls of it per trace", self.outcomes(false))
        }
    }
}

fn short(call: &ModeledCall) -> String {
    call.call.split('(').next().unwrap_or(&call.call).replace('/', ".")
}

fn refused(call: &ModeledCall, what: impl std::fmt::Display) -> Unsupported {
    Unsupported::new(Part::Environment, format!("a modelled call's model of its results ({}): {what}", short(call)))
}

fn integral(t: &Type) -> bool {
    matches!(t, Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int | Type::Long)
}

/// The model of `call` as the effect check encodes it, or what it doesn't take yet, named.
pub fn lower(call: &ModeledCall, model: &CallModel) -> Result<Lowered, Unsupported> {
    let descriptor = call.call.split_once('#').and_then(|(_, rest)| rest.find('(').map(|p| rest[p..].to_string())).and_then(|d| MethodDescriptor::parse(&d).ok()).ok_or_else(|| refused(call, "the call isn't owner#name(descriptor)"))?;
    if model.id.trim().is_empty() {
        return Err(refused(call, "a model needs a stable id, the same in both versions"));
    }
    let per_call = match &model.coupling {
        Coupling::Query => false,
        Coupling::Choice { policy: Occurrence::PerCall } => true,
        Coupling::Choice { policy: Occurrence::Script { .. } } => return Err(refused(call, "a finite script of responses (occurrence `script`): the brief's optional work, not built; a per-call choice or a query is checked")),
    };
    if model.bound == 0 || model.bound > MAX_BOUND {
        return Err(refused(call, format!("a bound of {} calls per trace: the check encodes 1 to {MAX_BOUND}", model.bound)));
    }
    let mut key = Vec::new();
    for path in &model.key {
        let p = path.strip_prefix("arg").and_then(|n| n.parse::<usize>().ok().filter(|_| n.chars().all(|c| c.is_ascii_digit())));
        let Some(p) = p else {
            let why = if path == "this" {
                "the receiver's identity as a key: every dependency is one stub here, so it would key nothing, and an object's identity is the objects stream's construction plan's".to_string()
            } else if path.contains('.') {
                format!("the key {path}, read through an object: a field path waits for the objects stream's construction plan")
            } else {
                format!("the key {path} is no argument path (arg0, arg1, ...)")
            };
            return Err(refused(call, why));
        };
        let Some(t) = descriptor.params.get(p) else { return Err(refused(call, format!("the key {path}: the call has {} parameters", descriptor.params.len()))) };
        if key.iter().any(|(q, _)| *q == p) {
            return Err(refused(call, format!("the key names {path} twice")));
        }
        // A String key (the values stream's String, bounded by the check's String bound): the stub compares it by
        // content, and one longer than the bound marks the log unresolved, never keyed as the default.
        if !integral(t) && !crate::values::is_string(t) {
            let why = match t {
                Type::Float | Type::Double => format!("the key {path} is a {}: floating point is out of this wave", t.java_name()),
                _ => format!("the key {path} is a {}: an object key waits for the objects stream's construction plan", t.java_name()),
            };
            return Err(refused(call, why));
        }
        key.push((p, t.clone()));
    }
    let mut ret = None;
    let mut response = None;
    let mut throws: Vec<String> = Vec::new();
    for result in &model.results {
        match result {
            ModelledResult::Throws { class } => {
                let class = class.trim().replace('.', "/");
                if class.is_empty() {
                    return Err(refused(call, "a modelled failure with no class"));
                }
                if class == "java/lang/NullPointerException" {
                    return Err(refused(call, "a modelled NullPointerException: the check can't tell it from a dependency left null, which marks the log unresolved"));
                }
                if throws.contains(&class) {
                    return Err(refused(call, format!("the failure {} twice", class.replace('/', "."))));
                }
                throws.push(class);
            }
            ModelledResult::Returns { value } => {
                let t = match value {
                    Returned::Primitive { ty } => ty.as_str(),
                    Returned::Void => "void",
                    Returned::Object { plan, nullable, identity } => {
                        if ret.is_some() {
                            return Err(refused(call, "two normal results: a call returns one value of one type"));
                        }
                        let r = dto(call, plan, *nullable, *identity, per_call)?;
                        if descriptor.ret != Type::Object(r.class.clone()) {
                            return Err(refused(call, format!("a DTO response, a {}, where the call returns {}", r.class.replace('/', "."), descriptor.ret.java_name())));
                        }
                        ret = Some(descriptor.ret.clone());
                        response = Some(r);
                        continue;
                    }
                    Returned::Adapted { domain } => {
                        // Resolved first, so that a response stated under another model is refused for that.
                        crate::values::resolve(domain).map_err(|u| refused(call, format!("its result: {}", u.what)))?;
                        return Err(refused(call, "a response of an adapter's domain (a String, a list): the effect check's stubs return a primitive so far, and none makes an adapter's value"));
                    }
                };
                if ret.is_some() {
                    return Err(refused(call, "two normal results: a call returns one value of one type"));
                }
                if descriptor.ret.java_name() != t {
                    return Err(refused(call, format!("a result of type {t}, where the call returns {}", descriptor.ret.java_name())));
                }
                if !integral(&descriptor.ret) && descriptor.ret != Type::Void {
                    return Err(refused(call, format!("a result of type {t}: a modelled result is an integral or boolean primitive so far")));
                }
                ret = Some(descriptor.ret.clone());
            }
        }
    }
    let Some(ret) = ret else {
        return Err(refused(call, if throws.is_empty() { "no permitted result" } else { "only failures: a call that always fails isn't modelled; give it its normal result beside them" }));
    };
    if ret == Type::Void && throws.is_empty() {
        return Err(refused(call, "a void result and no failure: a call that returns nothing and never fails needs no model of its results, its recording stub is the model"));
    }
    if let Some(o) = call.outcomes.iter().find(|o| *o != "returns" && !throws.contains(&o.replace('.', "/"))) {
        return Err(refused(call, format!("the call's outcomes name {o}, which the model's results don't: a modelled failure is a result of the model")));
    }
    Ok(Lowered { id: model.id.clone(), key, ret, throws, bound: model.bound, per_call, response })
}

/// A primitive Java type by its name, integral or boolean.
fn integral_named(name: &str) -> Option<Type> {
    Some(match name {
        "boolean" => Type::Boolean,
        "byte" => Type::Byte,
        "char" => Type::Char,
        "short" => Type::Short,
        "int" => Type::Int,
        "long" => Type::Long,
        _ => return None,
    })
}

/// A DTO response's plan as its stub makes it (E3): one node, made by a constructor, of primitive leaves named by
/// their path from the plan's one root; anything more is refused by name. Its class is checked against a build by
/// [`check_response`].
fn dto(call: &ModeledCall, plan: &ConstructionPlan, nullable: bool, identity: Identity, per_call: bool) -> Result<Response, Unsupported> {
    let no = |what: String| refused(call, format!("a DTO response: {what}"));
    if let Some(problem) = plan.shape_problem() {
        return Err(no(format!("its plan {problem}")));
    }
    if identity == Identity::Stable && per_call {
        return Err(no("a stable identity under a per-call choice: each entry answers one call, so no object is ever given twice; a fresh identity is the same claim, said plainly".into()));
    }
    let [root] = plan.roots.as_slice() else { return Err(no(format!("a plan of {} roots: a response is one root, the object returned", plan.roots.len()))) };
    let PlanValue::Node { id, nullable: may_be_null, same_as } = &root.value else { return Err(no(format!("the plan's root {} is no node: a response's root is the object made", root.name))) };
    if *may_be_null || !same_as.is_empty() {
        return Err(no("a root that may be null or the same as another: whether the response may be null is the model's own `nullable`".into()));
    }
    if !plan.setup.is_empty() {
        return Err(no("a setup sequence: a response is made by its constructor alone, as data".into()));
    }
    let [node] = plan.nodes.as_slice() else { return Err(no(format!("a plan of {} nodes: the first DTO is one object of primitive fields, and an object inside one waits for a later case", plan.nodes.len()))) };
    if node.id != *id {
        return Err(no(format!("the plan's root is node {id}, which it doesn't have")));
    }
    let Maker::Constructor { descriptor } = &node.maker else { return Err(no("a factory maker: a response is made by its class's constructor".into())) };
    let mut leaves = Vec::new();
    for arg in &node.args {
        match arg {
            PlanValue::Leaf { path, ty } => {
                let Some(name) = path.strip_prefix(&format!("{}.", root.name)).filter(|n| !n.is_empty() && !n.contains('.')) else {
                    return Err(no(format!("the leaf {path}: a leaf of the response is named by its path from the root, {}.NAME", root.name)));
                };
                let t = integral_named(ty).ok_or_else(|| no(format!("the leaf {path} of type {ty}: a response's leaves are integral or boolean primitives")))?;
                leaves.push((name.to_string(), t));
            }
            PlanValue::Array { path, .. } => return Err(no(format!("an array, {path}: the first DTO's fields are primitive"))),
            PlanValue::Adapted { path, .. } => return Err(no(format!("a value of an adapter's domain, {path}: a String field of a response comes later, through the values stream's adapter, and the stubs make primitive leaves so far"))),
            PlanValue::Dependency { path, .. } => return Err(no(format!("a dependency, {path}: a DTO carries data, not a client object with callbacks"))),
            PlanValue::Node { .. } => return Err(no("an object inside it: the first DTO is one object of primitive fields".into())),
        }
    }
    Ok(Response { class: node.class.replace('.', "/"), descriptor: descriptor.clone(), root: root.name.clone(), leaves, nullable, stable: identity == Identity::Stable, plan: plan.clone() })
}

/// Checks a DTO response's class in a build of class path `cp` (E3): the objects stream's construction plan makes it
/// ([`crate::construction::root`]: a concrete class extending `Object`, the named constructor, no side effect
/// outside the object, its fields followed), its leaves are the constructor's parameters in order, and the class is
/// data: instance fields of primitive types only, no static field, no method beside its constructors. A caller's
/// use of it beyond reading its fields is the effect check's to refuse.
pub fn check_response(cp: &crate::classpath::ClassPath, r: &Response) -> Result<(), String> {
    let class = r.class.replace('/', ".");
    let cf = cp.application(&r.class).ok().flatten().ok_or_else(|| format!("{class} is no application class of the build"))?;
    for f in &cf.fields {
        let t = Type::parse(&f.descriptor).map_err(|e| format!("its field {}: {e}", f.name))?;
        if f.is_static() {
            return Err(format!("{class} has a static field {}: a DTO is data, and state shared by every response isn't modelled", f.name));
        }
        if !t.is_primitive() {
            return Err(format!("{class} has a field {} of type {}: a DTO response's fields are primitive, so no object, and no cycle, is reached from it", f.name, t.java_name()));
        }
    }
    if let Some(m) = cf.methods.iter().find(|m| !m.is_constructor() && !m.is_synthetic()) {
        return Err(format!("{class} has a method {}: a DTO response is data, and no method of it beside its constructor is modelled", m.name));
    }
    let made = crate::construction::root(cp, &r.plan, &r.root).map_err(|u| u.what)?;
    let Some(crate::construction::Rooted::Object(record)) = made else { return Err(format!("its plan makes no object at {}", r.root)) };
    if record.components != r.leaves {
        let words = |ls: &[(String, Type)]| ls.iter().map(|(n, t)| format!("{} {n}", t.java_name())).collect::<Vec<_>>().join(", ");
        return Err(format!("its constructor's leaves are ({}), and the model gives ({})", words(&record.components), words(&r.leaves)));
    }
    Ok(())
}

/// Checks that the effect check can make `call`'s stubs give the results `model` says, under its coupling and
/// bound ([`lower`]). Called by the effect check (`effects`) for every modelled call with a model.
pub fn check_model(call: &ModeledCall, model: &CallModel) -> Result<(), Unsupported> {
    lower(call, model).map(|_| ())
}

/// Checks a method's claim whose environment models its dependencies' outcomes (the acceptance contract's Q:
/// `quotes.QuoteService#quote` under a modelled `Rates.rate` and a recorded `Events.send`) between the builds
/// `before` and `after`. The entry point of rows E1 and E2 (`tests/application_core.rs`). Its receiver and request
/// are made by its construction plan, its code is a String of the values stream's adapter, and the effect check
/// compares the two builds' logs under one environment ([`crate::effects::check_planned`], which says how).
pub fn check(claim: &crate::spec::CanonicalClaim, before: &Path, after: &Path) -> Result<crate::spec::Outcome, Unsupported> {
    crate::effects::check_planned(claim, before, after, None).map(|c| c.outcome)
}

/// Reads `--environment FILE` of `effects` and `compare`: the modelled calls a person declares, as a JSON list of
/// [`ModeledCall`], each with its model; checked by [`check_model`].
pub fn load(path: &Path) -> Result<Vec<ModeledCall>, Unsupported> {
    let text = std::fs::read_to_string(path).map_err(|e| Unsupported::new(Part::Environment, format!("--environment {}: {e}", path.display())))?;
    let calls: Vec<ModeledCall> = serde_json::from_str(&text).map_err(|e| Unsupported::new(Part::Environment, format!("--environment {}: {e}", path.display())))?;
    declared(&calls).map_err(|u| Unsupported::new(Part::Environment, format!("--environment {}: {}", path.display(), u.what)))?;
    Ok(calls)
}

/// Checks the modelled calls a person declares (`--environment`, `compare::Options::environment`): each has a model
/// [`check_model`] accepts. Called by `effects::check_builds` before any entry point is checked.
pub fn declared(calls: &[ModeledCall]) -> Result<(), Unsupported> {
    for call in calls {
        match &call.model {
            Some(model) => check_model(call, model)?,
            None => return Err(Unsupported::new(Part::Environment, format!("the call {} has no model; one with none is the entry point's own, from its spec", call.call))),
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::spec::plans::{Occurrence, ModelledResult, Returned};

    const RATE: &str = "shop/Rates#rate(I)J";

    fn query(key: &[&str], ty: &str, bound: u32) -> CallModel {
        CallModel { id: "rates".into(), key: key.iter().map(|k| k.to_string()).collect(), coupling: Coupling::Query, results: vec![ModelledResult::Returns { value: Returned::Primitive { ty: ty.into() } }], bound }
    }

    fn call(call: &str, model: &CallModel) -> ModeledCall {
        ModeledCall { call: call.into(), outcomes: vec!["returns".into()], model: Some(model.clone()) }
    }

    #[test]
    fn a_query_of_a_primitive_key_is_lowered_to_a_table_of_twice_its_bound() {
        let model = query(&["arg0"], "long", 2);
        let lowered = lower(&call(RATE, &model), &model).unwrap();
        assert_eq!(lowered.key, vec![(0, Type::Int)]);
        assert_eq!(lowered.ret, Type::Long);
        assert_eq!(lowered.entries(), 4);
        // Four entries of a key and a result, then the default.
        assert_eq!(lowered.inputs(), [Type::Int, Type::Long, Type::Int, Type::Long, Type::Int, Type::Long, Type::Int, Type::Long, Type::Long]);
        assert!(lowered.assumption("Rates.rate").contains("never by position"));
        assert_eq!(lowered.input_names()[..3], ["rates[0].arg0", "rates[0]", "rates[1].arg0"]);
        assert_eq!(lowered.input_names().last().unwrap(), "rates.default");
        let model = query(&["arg1", "arg0"], "boolean", 1);
        let lowered = lower(&call("shop/Stock#has(JI)Z", &model), &model).unwrap();
        assert_eq!(lowered.key, vec![(1, Type::Int), (0, Type::Long)]);
        assert_eq!(lowered.inputs(), [Type::Int, Type::Long, Type::Boolean, Type::Int, Type::Long, Type::Boolean, Type::Boolean]);
        assert!(!lowered.per_call);
    }

    #[test]
    fn a_per_call_choice_is_lowered_to_the_same_table_each_entry_used_once() {
        let mut model = query(&["arg0"], "long", 2);
        model.coupling = Coupling::Choice { policy: Occurrence::PerCall };
        let lowered = lower(&call(RATE, &model), &model).unwrap();
        assert!(lowered.per_call);
        assert_eq!(lowered.entries(), 4);
        assert_eq!(lowered.inputs().len(), 9);
        let words = lowered.assumption("Rates.rate");
        assert!(words.contains("chosen per call") && words.contains("same occurrence of it") && words.contains("never coupled by position"), "{words}");
        assert!(lowered.domain("Rates.rate").contains("any long per call, chosen alike for the same (arg0) and occurrence of it"));
    }

    /// `Rates.rate` as a query that returns a long or throws one of `classes`.
    fn failing(classes: &[&str]) -> CallModel {
        let mut model = query(&["arg0"], "long", 2);
        model.results.extend(classes.iter().map(|c| ModelledResult::Throws { class: c.to_string() }));
        model
    }

    #[test]
    fn a_modelled_failure_adds_an_outcome_to_each_entry_and_the_default() {
        let model = failing(&["java.io.IOException", "shop/Unavailable"]);
        let declared = ModeledCall { outcomes: vec!["returns".into(), "java.io.IOException".into()], ..call(RATE, &model) };
        let lowered = lower(&declared, &model).unwrap();
        assert_eq!(lowered.throws, ["java/io/IOException", "shop/Unavailable"]);
        // Each entry: its key, its value, its outcome; then the default's value and outcome.
        assert_eq!(lowered.inputs().len(), 4 * 3 + 2);
        assert_eq!(lowered.input_names()[..3], ["rates[0].arg0", "rates[0]", "rates[0].outcome"]);
        assert_eq!(lowered.input_names()[12..], ["rates.default", "rates.default.outcome"]);
        assert_eq!((lowered.thrown(0), lowered.thrown(1), lowered.thrown(2), lowered.thrown(3), lowered.thrown(-1)), (None, Some("java/io/IOException"), Some("shop/Unavailable"), None, None));
        let words = lowered.assumption("Rates.rate");
        assert!(words.contains("any long, or a throw of java.io.IOException or shop.Unavailable (made with no arguments: its class, and no message or cause)"), "{words}");
        // A call that returns nothing may be modelled by its failures alone: only the outcome is chosen.
        let mut send = CallModel { results: vec![ModelledResult::Returns { value: Returned::Void }, ModelledResult::Throws { class: "java.io.IOException".into() }], ..query(&["arg0"], "void", 1) };
        send.coupling = Coupling::Choice { policy: Occurrence::PerCall };
        let lowered = lower(&call("shop/Events#send(I)V", &send), &send).unwrap();
        assert_eq!(lowered.inputs(), [Type::Int, Type::Int, Type::Int, Type::Int, Type::Int]);
        assert_eq!(lowered.input_names()[..2], ["rates[0].arg0", "rates[0].outcome"]);
        assert!(lowered.returns().starts_with("a normal return, or a throw of java.io.IOException"), "{}", lowered.returns());
    }

    #[test]
    fn what_the_check_does_not_encode_yet_is_refused_by_name() {
        let refusal = |c: &str, m: CallModel| lower(&call(c, &m), &m).unwrap_err();
        let mut script = query(&["arg0"], "long", 2);
        script.coupling = Coupling::Choice { policy: Occurrence::Script { results: vec![0, 0] } };
        let cases = [
            (refusal(RATE, script), "occurrence `script`"),
            (refusal(RATE, CallModel { results: vec![ModelledResult::Throws { class: "shop.Unavailable".into() }], ..query(&["arg0"], "long", 1) }), "only failures"),
            (refusal(RATE, failing(&["java.lang.NullPointerException"])), "can't tell it from a dependency left null"),
            (refusal(RATE, failing(&["shop.Unavailable", "shop/Unavailable"])), "twice"),
            (refusal(RATE, query(&["this"], "long", 1)), "the receiver's identity"),
            (refusal(RATE, query(&["arg0.code"], "long", 1)), "field path"),
            (refusal(RATE, query(&["arg0"], "int", 1)), "where the call returns long"),
            (refusal(RATE, query(&["arg0"], "long", 0)), "1 to 8"),
            (refusal(RATE, query(&["arg0"], "long", 9)), "1 to 8"),
            (refusal(RATE, query(&["arg0", "arg0"], "long", 1)), "twice"),
            (refusal(RATE, query(&["arg2"], "long", 1)), "1 parameters"),
            (refusal("shop/Rates#rate(I)D", query(&["arg0"], "double", 1)), "integral or boolean"),
            (refusal("shop/Events#send(I)V", CallModel { results: vec![ModelledResult::Returns { value: Returned::Void }], ..query(&["arg0"], "void", 1) }), "its recording stub is the model"),
        ];
        for (gap, words) in cases {
            assert_eq!(gap.part, Part::Environment);
            assert!(gap.what.contains(words) && gap.what.starts_with("a modelled call's model of its results ("), "{words}: {gap}");
        }
        // A String key is the values stream's String, compared by its content in the stub.
        let keyed = query(&["arg0"], "long", 1);
        let lowered = lower(&call("shop/Rates#rate(Ljava/lang/String;)J", &keyed), &keyed).expect("a String key is encoded");
        assert_eq!(lowered.key, vec![(0, Type::Object("java/lang/String".into()))]);
        let model = query(&["arg0"], "long", 1);
        let undeclared = ModeledCall { outcomes: vec!["returns".into(), "shop.Unavailable".into()], ..call(RATE, &model) };
        assert!(lower(&undeclared, &model).unwrap_err().what.contains("outcomes name shop.Unavailable"));
    }

    #[test]
    fn a_declared_environment_is_loaded_and_checked() {
        let model = query(&["arg0"], "long", 2);
        let file = std::env::temp_dir().join(format!("environment-{}.json", std::process::id()));
        std::fs::write(&file, serde_json::to_string(&[call(RATE, &model)]).unwrap()).unwrap();
        assert_eq!(load(&file).unwrap().len(), 1);
        let double = query(&["arg0"], "double", 2);
        std::fs::write(&file, serde_json::to_string(&[call("shop/Rates#rate(I)D", &double)]).unwrap()).unwrap();
        assert!(load(&file).unwrap_err().what.contains("integral or boolean"));
        std::fs::write(&file, serde_json::to_string(&[ModeledCall { model: None, ..call(RATE, &model) }]).unwrap()).unwrap();
        assert!(load(&file).unwrap_err().what.contains("has no model"));
        let _ = std::fs::remove_file(&file);
    }
}
