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
//! **What the key can be**, so far: a primitive integral or boolean argument (`arg0`). A String key needs the values
//! stream's adapter, a field path (`arg1.code`) or an object's identity the objects stream's construction plan;
//! both are refused by name until then. The result: one normal return of an integral or boolean primitive. A thrown
//! result is E2's, a DTO E3's, and a value of an adapter's domain the values stream's.

use std::path::Path;

use crate::classfile::{MethodDescriptor, Type};
use crate::spec::plans::{CallModel, Coupling, ModelledResult, Occurrence, Returned};
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
    /// The type of the result.
    pub ret: Type,
    /// The most calls of it one trace may make.
    pub bound: u32,
    /// A per-call choice ([`Occurrence::PerCall`]): each entry answers one call per trace, so a result is a function of
    /// the key and its occurrence. Otherwise a query: the first entry of the key answers every call of it.
    pub per_call: bool,
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

    /// The check's inputs the table is: for each entry its key's components, then its result; then the default.
    pub fn inputs(&self) -> Vec<Type> {
        let mut out = Vec::new();
        for _ in 0..self.entries() {
            out.extend(self.key.iter().map(|(_, t)| t.clone()));
            out.push(self.ret.clone());
        }
        out.push(self.ret.clone());
        out
    }

    /// The names of [`Lowered::inputs`], as a proof or a search names them: `rates.rate[0].arg0`, `rates.rate[0]`,
    /// ..., `rates.rate.default`.
    pub fn input_names(&self) -> Vec<String> {
        let mut out = Vec::new();
        for e in 0..self.entries() {
            out.extend(self.key_names().iter().map(|k| format!("{}[{e}].{k}", self.id)));
            out.push(format!("{}[{e}]", self.id));
        }
        out.push(format!("{}.default", self.id));
        out
    }

    /// What the result rests on, in words.
    pub fn assumption(&self, call: &str) -> String {
        let (id, key, ty, bound) = (&self.id, self.key_names().join(", "), self.ret.java_name(), self.bound);
        if self.per_call {
            format!("{call} is a generated stub in both builds, answering from the environment model {id}: a declared nondeterministic operation, chosen per call: any {ty} for each call, the same choice in both builds for the same ({key}) and the same occurrence of it in the trace, so calls with equal keys may get different results and calls with different keys are never coupled by position; at most {bound} calls of it in a trace, one more leaves the result unresolved")
        } else {
            format!("{call} is a generated stub in both builds, answering from the environment model {id}: a deterministic read-only query of one declared snapshot, the same function in both builds, of ({key}) only: calls with equal keys get equal results and calls with different keys independent ones, never by position; any {ty} for any key; at most {bound} calls of it in a trace, one more leaves the result unresolved")
        }
    }

    /// What a stub returns, in the effect-log plan's words.
    pub fn returns(&self) -> String {
        let (id, key, ty) = (&self.id, self.key_names().join(", "), self.ret.java_name());
        if self.per_call {
            format!("any {ty} chosen per call, the same in both builds for the same ({key}) and occurrence of it ({id})")
        } else {
            format!("any {ty} that is a function of ({key}), the same in both builds ({id})")
        }
    }

    /// The part of the domain the model's answers are, in words.
    pub fn domain(&self, call: &str) -> String {
        let (id, key, ty, bound) = (&self.id, self.key_names().join(", "), self.ret.java_name(), self.bound);
        if self.per_call {
            format!("{call} ({id}): any {ty} per call, chosen alike for the same ({key}) and occurrence of it, within {bound} calls of it per trace")
        } else {
            format!("{call} ({id}): any function of ({key}) to {ty}, within {bound} calls of it per trace")
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
        if !integral(t) {
            let why = match t {
                Type::Object(c) if c == "java/lang/String" => format!("the key {path} is a String: a String key waits for the values stream's adapter"),
                Type::Float | Type::Double => format!("the key {path} is a {}: floating point is out of this wave", t.java_name()),
                _ => format!("the key {path} is a {}: an object key waits for the objects stream's construction plan", t.java_name()),
            };
            return Err(refused(call, why));
        }
        key.push((p, t.clone()));
    }
    let mut ret = None;
    for result in &model.results {
        match result {
            ModelledResult::Throws { class } => return Err(refused(call, format!("a modelled failure (throws {class}): modelled failures are the environment stream's E2, not built yet"))),
            ModelledResult::Returns { value } => {
                let t = match value {
                    Returned::Primitive { ty } => ty,
                    Returned::Void => return Err(refused(call, "a void result: a call that returns nothing needs no model of its results, its recording stub is the model")),
                    Returned::Object { .. } => return Err(refused(call, "a DTO response made by a construction plan: the environment stream's E3, not built yet")),
                    Returned::Adapted { .. } => return Err(refused(call, "a value of an adapter's domain: it waits for the values stream's adapter")),
                };
                if ret.is_some() {
                    return Err(refused(call, "two normal results: a call returns one type"));
                }
                if &descriptor.ret.java_name() != t {
                    return Err(refused(call, format!("a result of type {t}, where the call returns {}", descriptor.ret.java_name())));
                }
                if !integral(&descriptor.ret) {
                    return Err(refused(call, format!("a result of type {t}: a modelled result is an integral or boolean primitive so far")));
                }
                ret = Some(descriptor.ret.clone());
            }
        }
    }
    let Some(ret) = ret else { return Err(refused(call, "no permitted result")) };
    if let Some(o) = call.outcomes.iter().find(|o| *o != "returns") {
        return Err(refused(call, format!("the call's outcomes name {o}, which the model's results don't: a modelled failure is a result of the model (E2)")));
    }
    Ok(Lowered { id: model.id.clone(), key, ret, bound: model.bound, per_call })
}

/// Checks that the effect check can make `call`'s stubs give the results `model` says, under its coupling and
/// bound ([`lower`]). Called by the effect check (`effects`) for every modelled call with a model.
pub fn check_model(call: &ModeledCall, model: &CallModel) -> Result<(), Unsupported> {
    lower(call, model).map(|_| ())
}

/// Checks a method's claim whose environment models its dependencies' outcomes (the acceptance contract's Q:
/// `quotes.QuoteService#quote` under a modelled `Rates.rate` and a recorded `Events.send`) between the builds
/// `before` and `after`. The entry point of rows E1 and E2 (`tests/application_core.rs`). Its receiver and request
/// are made by the objects stream's construction plan, and its code is a String of the values stream's adapter:
/// until both are integrated, it is refused.
pub fn check(claim: &crate::spec::CanonicalClaim, before: &Path, after: &Path) -> Result<crate::spec::Outcome, Unsupported> {
    let _ = (before, after);
    Err(Unsupported::new(Part::Environment, format!("a claim of {} under an environment model of its dependencies' outcomes: its receiver and request need the objects stream's construction plan and its code the values stream's String adapter, so the environment stream builds it after integration (llm-dlc/loops/application-core-environment.md)", claim.contract.subject)))
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

    #[test]
    fn what_the_check_does_not_encode_yet_is_refused_by_name() {
        let refusal = |c: &str, m: CallModel| lower(&call(c, &m), &m).unwrap_err();
        let mut script = query(&["arg0"], "long", 2);
        script.coupling = Coupling::Choice { policy: Occurrence::Script { results: vec![0, 0] } };
        let cases = [
            (refusal(RATE, script), "occurrence `script`"),
            (refusal(RATE, CallModel { results: vec![ModelledResult::Throws { class: "shop.Unavailable".into() }], ..query(&["arg0"], "long", 1) }), "E2"),
            (refusal(RATE, query(&["this"], "long", 1)), "the receiver's identity"),
            (refusal(RATE, query(&["arg0.code"], "long", 1)), "field path"),
            (refusal("shop/Rates#rate(Ljava/lang/String;)J", query(&["arg0"], "long", 1)), "values stream's adapter"),
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
        let model = query(&["arg0"], "long", 1);
        let failing = ModeledCall { outcomes: vec!["returns".into(), "shop.Unavailable".into()], ..call(RATE, &model) };
        assert!(lower(&failing, &model).unwrap_err().what.contains("outcomes name shop.Unavailable"));
    }

    #[test]
    fn a_declared_environment_is_loaded_and_checked() {
        let model = query(&["arg0"], "long", 2);
        let file = std::env::temp_dir().join(format!("environment-{}.json", std::process::id()));
        std::fs::write(&file, serde_json::to_string(&[call(RATE, &model)]).unwrap()).unwrap();
        assert_eq!(load(&file).unwrap().len(), 1);
        std::fs::write(&file, serde_json::to_string(&[call("shop/Rates#rate(Ljava/lang/String;)J", &model)]).unwrap()).unwrap();
        assert!(load(&file).unwrap_err().what.contains("values stream's adapter"));
        std::fs::write(&file, serde_json::to_string(&[ModeledCall { model: None, ..call(RATE, &model) }]).unwrap()).unwrap();
        assert!(load(&file).unwrap_err().what.contains("has no model"));
        let _ = std::fs::remove_file(&file);
    }
}
