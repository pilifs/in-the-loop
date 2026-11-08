//! The effect log of an entry point, and the check that discharges its obligations (O3 of
//! `llm-dlc/loops/foundations-observations.md`, behind [`crate::spec::observe::effect_log`] and
//! [`crate::spec::observe::check`]). The contract is deliberately narrow: *the ordered trace of modeled boundary-call
//! attempts, with the response and the supported failure outcome, is preserved under an explicit environment model.*
//!
//! How it is checked, in both builds alike:
//! - **Recording stubs.** Every call site of a modeled call (the spec's environment model, reads included) is
//!   rewritten into an `invokestatic` of a generated stub ([`crate::shared::redirect_calls`], which moves no
//!   offset). A stub of an observed effect appends one attempt to a log: which call, and a snapshot of its payload
//!   paths read at the call (`topic`, `data.total`), never a reference read later. Where the call sites pass
//!   payloads of several classes (a retry and a dead letter through one `send`), each path is read through the class
//!   the payload is, a path that class lacks is snapshotted as absent, and the class itself is snapshotted as one
//!   more path (`data.class`), so payloads of two classes never compare equal. A stub gives back nothing, or
//!   its type's default, which the caller must drop: a call whose result the handler uses needs a modeled return
//!   value, and without a model of its results ([`crate::environment`]) it is refused.
//! - **Modelled results.** A call with a model of its results (a [`crate::spec::plans::CallModel`], declared in
//!   the claim's environment or with `--environment`) answers from it instead: a deterministic read-only query's
//!   table of keys and results, with a default, among the check's inputs after the handler's, the same for both
//!   builds, so that its answers are one function of the key for both and never coupled by a call's position
//!   (the coupling policy is [`crate::environment`]'s). Under a per-call choice each entry answers one call per
//!   trace, so the n-th call of a key gets the n-th entry of that key in both builds. One more call of it than its
//!   bound marks the log past its bound. A witness names the table it chose, and the JVM replays it under the same stubs. The call on the
//!   model's owner that the analysis can't follow (an interface nothing implements) is the one the model answers;
//!   every other call on that owner is a stub that marks the log.
//! - **DTO responses** (E3). A model whose normal result is a DTO answers with an object its stub makes by the
//!   class's constructor from the leaves of the chosen entry, or null, under the model's identity policy: a new
//!   object for every call (fresh), or one per entry for the trace (stable). The witness names each answer
//!   (`gives a new Offer(unitCents=3, minimumUnits=1)`, `gives null`), and the JVM replays it under the same stubs.
//!   The class is checked by the objects stream's construction plan in both builds, and a build that uses a response
//!   beyond reading its fields is refused by name ([`crate::environment::check_response`]).
//! - **A method made by its plan** ([`check_planned`], the quote family's E1 and E2 rows). An ordinary method's
//!   claim, its receiver and parameters made by its planned domain ([`crate::construction::flat_roots`]), is
//!   checked the same way: the generated method takes the plan's flat inputs (a String among them, the values
//!   stream's), makes each root by its constructor with every dependency null, and calls the method, a
//!   constructor's exception being the outcome as the call's is. A payload String is snapshotted by its content
//!   (its length, then its code units), and a modelled call's String key compared by content, each within the
//!   claim's String bound; past it, the log is unresolved.
//! - **One environment for both.** The two builds get the same stubs, in the same order, from one model: the union
//!   of the claim's and both specs' modeled calls. Every call returns normally, unless its model of its results
//!   declares failures, and the result says which may fail.
//! - **Modelled failures.** A model's failures are outcomes of its table's entries, beside the normal result: a
//!   stub whose answer's outcome is `k` throws a new instance of the `k`-th class, checked or not, made by its
//!   constructor without arguments. What escapes the handler is its outcome, by class, like any of its own
//!   exceptions. A failure carries its class and nothing a dependency would give it, so a build whose handlers read
//!   more of a caught one (its message, its cause, or by handing it on) is refused by name ([`Part::Environment`]).
//!   A witness names each chosen outcome (`(arg0=3) throws java.io.IOException`), and the JVM replays it.
//! - **The handler, made the same way.** A generated static method in the handler's package makes the handler with
//!   its one constructor, every dependency `null` (reached only through the stubs; an application class among them
//!   is refused, since it would be null too), calls it on the entry point's inputs, and returns the log: the outcome (a normal
//!   return, or which exception class), the response, the attempts in order. The existing regression harness
//!   ([`crate::equivalence`], as a new caller) proves the two builds' logs equal, element by element.
//! - **Bounds visible.** An attempt past the trace bound, a payload value a snapshot can't hold (a string that is no
//!   literal of either build), a handler its constructor won't make, a call on a dependency that the model doesn't
//!   have, or a `NullPointerException` out of the handler (a dependency left null, called through a supertype such
//!   as `Object.hashCode`, looks like any other call) marks the log unresolved, differently in each build, so such
//!   an input can never be part of a proof; a counterexample on it is reported as unresolved, never as a shorter
//!   trace.
//! - **Replayed under the modeled dependencies.** A counterexample is run again on a real JVM: the harness on the
//!   witness, then each build's log on its own, decoded into the attempts each made. It is a run under the stubs,
//!   not against a broker or a store.
//! - **Under the proof cache, when given one** ([`check_with`]). The proof is a regression check of the two rewritten
//!   builds, keyed as any is ([`crate::proof_cache`]): their closures from the generated entry method, so the stubs
//!   and the environment model they encode are in the key. A stored refutation's witness is replayed on a JVM again.
//!   A reuse names the run it came from by the builds that run was given, of which the proof's were copies.

use std::collections::BTreeSet;
use std::path::{Path, PathBuf};

use crate::classfile::writer::{ClassWriter, CodeBuilder, FieldWriter, MethodWriter};
use crate::classfile::{flags, ClassFile, Cond, Constant, Insn, Kind, MemberRef, MethodDescriptor, Type};
use crate::classpath::ClassPath;
use crate::interp::Value;
use crate::jbmc::Argument;
use crate::shared::Invoke;
use crate::spec::observe::{Change, EffectLogPlan, EntryPointSpec, RecordingStub};
use crate::spec::{Accounted, CanonicalClaim, ClaimBounds, EnvironmentModel, ModeledCall, Observation, ObservationState, Outcome, Part, PreservationContract, ToolIdentity, Unsupported, VersionDigests, Verdict};
use serde::Serialize;

/// The generated classes, in the handler's package so that what it reaches package-privately stays reachable.
const ENTRY: &str = "JvmcontractEffects";
const STUBS: &str = "JvmcontractStubs";
const METHOD: &str = "observe";
/// The log's first words: the outcome, the response, the attempts recorded, the unresolved mark.
const HEADER: usize = 4;
/// The unresolved mark's bits.
const PAST_BOUND: i64 = 1;
const UNSNAPSHOTTED: i64 = 2;
const UNMADE: i64 = 4;
const UNMODELED: i64 = 8;
const NULL_THROWN: i64 = 16;
const PAST_MODEL_BOUND: i64 = 32;
const UNMADE_RESPONSE: i64 = 64;
const KEY_PAST_BOUND: i64 = 128;
/// The unresolved mark's bits, below the build's tag, which sits above them (`tag * TAG`) so that the two builds'
/// marks differ and neither reads as a bit it didn't set.
const MARK_BITS: i64 = 0xff;
const TAG: i64 = 256;

/// What a check of an entry point established, with what it rests on and what each build did on a witness.
#[derive(Debug, Clone, Serialize)]
pub struct Checked {
    pub outcome: Outcome,
    /// Why the result is unresolved, when it is.
    pub reason: Option<String>,
    /// What the verdict rests on: the stubs, the environment model's restriction, how the handler is made.
    pub assumptions: Vec<String>,
    /// How the verdict was reached: the regression proof's line.
    pub proof: Option<String>,
    /// What each build did on the witness, replayed on the JVM, for a refutation (or an unresolved witness).
    pub before: Option<Trace>,
    pub after: Option<Trace>,
    /// The claim key of the effect-trace proof, when it ran under the proof cache: the closures of both rewritten
    /// builds, the recording stubs and the generated entry method included.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub key: Option<crate::spec::cache::ClaimKey>,
    /// The stored result that was the proof's: an exact hit of the same key.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reuse: Option<crate::spec::cache::Reuse>,
}

/// One build's log on one input, decoded.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Trace {
    /// `returns 1000`, `throws java.lang.IllegalArgumentException`.
    pub outcome: String,
    /// The outcome's index: 0 a normal return, else the exception class's among the model's.
    pub kind: i64,
    pub result: i64,
    /// Each attempt, in order: the call's index in the model, and its rendering.
    pub attempts: Vec<(usize, Vec<i64>, String)>,
    /// What left the log unresolved, in words.
    pub unresolved: Vec<String>,
}

impl Trace {
    pub fn words(&self) -> String {
        let attempts = if self.attempts.is_empty() { "attempts no modeled call".to_string() } else { format!("attempts {}", self.attempts.iter().map(|a| a.2.clone()).collect::<Vec<_>>().join(", then ")) };
        let mut s = format!("{} and {attempts}", self.outcome);
        if !self.unresolved.is_empty() {
            s.push_str(&format!(" (unresolved: {})", self.unresolved.join("; ")));
        }
        s
    }
}

/// The model both builds run under: the modeled calls in log order, which of them are observed (with the payload
/// paths their stubs snapshot), the bound, the exception classes the outcome tells apart, and the string literals a
/// snapshot can name.
#[derive(Debug, Clone)]
struct Model {
    calls: Vec<String>,
    /// For each call, the payload paths when it is an observed effect, `None` for a read.
    observed: Vec<Option<Vec<String>>>,
    bound: usize,
    exceptions: Vec<String>,
    literals: Vec<String>,
    /// The payload classes the call sites of either build pass, which a `.class` path's snapshot names by index.
    classes: Vec<String>,
    /// For each call, its model's table when its results are modelled ([`crate::environment::Lowered`]): the
    /// stub answers from it, and the table is among the check's inputs, the same for both builds.
    models: Vec<Option<crate::environment::Lowered>>,
    /// The check's String bound in code units (the claim's `max_array_length`): the longest String key a modelled
    /// call's table holds, and under `content`, the longest payload String a snapshot holds.
    string_bound: usize,
    /// Whether a payload String is snapshotted by its content (a planned subject, whose Strings are inputs), rather
    /// than as the literal it is.
    content: bool,
}

impl Model {
    /// The most payload paths one call snapshots.
    fn paths(&self) -> usize {
        self.observed.iter().flatten().map(Vec::len).max().unwrap_or(0)
    }

    /// The log words per attempt: the call (with the snapshot's null bits), then one per payload path; under
    /// `content`, then a block of `string_bound` words per path, which holds a String path's code units (its own
    /// word holding its length).
    fn width(&self) -> usize {
        1 + self.paths() + if self.content { self.paths() * self.string_bound } else { 0 }
    }

    /// The word of attempt `at`'s log where path `j`'s String block starts, under `content`.
    fn block(&self, j: usize) -> usize {
        1 + self.paths() + j * self.string_bound
    }

    /// The check's inputs after the handler's: every modelled call's table, in call order.
    fn environment_inputs(&self) -> Vec<Type> {
        self.models.iter().flatten().flat_map(crate::environment::Lowered::inputs).collect()
    }

    /// The environment a witness chose, in words, from the values of [`Model::environment_inputs`]: each modelled
    /// call's answers by key (`gives 3`, `throws java.io.IOException`, `returns`), then its default. A query's entry shadowed by an earlier one of the same key is left
    /// out; a per-call choice lists a key's answers in the order of its occurrences.
    fn environment_words(&self, values: &[Argument]) -> String {
        let scalar = |a: Option<&Argument>, t: &Type| match (a, t) {
            (Some(Argument::Scalar(Value::Int(v))), Type::Boolean) => (*v != 0).to_string(),
            (Some(Argument::Scalar(Value::Int(v))), Type::Char) => format!("{:?}", char::from_u32(*v as u32 & 0xffff).unwrap_or('?')),
            (Some(Argument::Scalar(Value::Long(v))), _) => v.to_string(),
            (Some(Argument::Scalar(Value::Int(v))), _) => v.to_string(),
            (Some(Argument::String(units)), _) => crate::witness::string_literal(units),
            _ => "?".into(),
        };
        let mut at = 0;
        let mut out = Vec::new();
        for (call, m) in self.calls.iter().zip(&self.models) {
            let Some(m) = m else { continue };
            let names = m.key_names();
            // Each key once, in the order of its first entry, with its answers.
            let mut answers: Vec<(Vec<String>, Vec<String>)> = Vec::new();
            // An answer, from its value and its outcome: a throw of the outcome's class, or the value.
            let give = |at: &mut usize| -> String {
                let value = if let Some(r) = &m.response {
                    let null = r.nullable && {
                        *at += 1;
                        !matches!(values.get(*at - 1), Some(Argument::Scalar(Value::Int(0))))
                    };
                    let leaves: Vec<String> = r.leaves.iter().map(|(n, t)| {
                        *at += 1;
                        format!("{n}={}", scalar(values.get(*at - 1), t))
                    }).collect();
                    if null {
                        "gives null".to_string()
                    } else if r.stable {
                        format!("gives {}({}), one object for every call of that key", r.simple(), leaves.join(", "))
                    } else {
                        format!("gives a new {}({})", r.simple(), leaves.join(", "))
                    }
                } else if m.ret == Type::Void {
                    "returns".to_string()
                } else {
                    *at += 1;
                    format!("gives {}", scalar(values.get(*at - 1), &m.ret))
                };
                if m.throws.is_empty() {
                    return value;
                }
                *at += 1;
                let outcome = match values.get(*at - 1) {
                    Some(Argument::Scalar(Value::Int(v))) => i64::from(*v),
                    _ => 0,
                };
                match m.thrown(outcome) {
                    Some(class) => format!("throws {}", class.replace('/', ".")),
                    None => value,
                }
            };
            for _ in 0..m.entries() {
                let key: Vec<String> = m.key.iter().enumerate().map(|(c, (_, t))| scalar(values.get(at + c), t)).collect();
                at += m.key.len();
                let result = give(&mut at);
                match answers.iter_mut().find(|(k, _)| *k == key) {
                    Some((_, rs)) => {
                        if m.per_call {
                            rs.push(result);
                        }
                    }
                    None => answers.push((key, vec![result])),
                }
            }
            let default = give(&mut at);
            let answers: Vec<String> = answers.iter().map(|(key, rs)| format!("({}) {}", names.iter().zip(key).map(|(n, v)| format!("{n}={v}")).collect::<Vec<_>>().join(", "), rs.join(", then "))).collect();
            let rest = if m.per_call { "any other key or later call of one" } else { "any other key" };
            out.push(format!("{} ({}): {}, {rest} {default}", short(call), m.id, answers.join(", ")));
        }
        out.join("; ")
    }
}

/// The effect-log plan of an entry point: its environment model and the stubs that record it.
pub fn plan(spec: &EntryPointSpec) -> Result<EffectLogPlan, Unsupported> {
    let environment = spec.environment.clone();
    let stubs = environment
        .calls
        .iter()
        .map(|c| {
            let snapshot = spec.observations.iter().find_map(|o| match o {
                Observation::Effect { call, payload } if call == &c.call => Some(payload.clone()),
                _ => None,
            });
            let lowered = c.model.as_ref().and_then(|m| crate::environment::lower(c, m).ok());
            let returns = match split_call(&c.call).and_then(|(_, _, d)| MethodDescriptor::parse(&d).ok()).map(|d| d.ret) {
                _ if lowered.is_some() => lowered.as_ref().unwrap().returns(),
                Some(Type::Void) => "nothing".to_string(),
                Some(t) if t.is_primitive() => format!("{} 0, which the caller must drop", t.java_name()),
                _ => "null, which the caller must drop".to_string(),
            };
            RecordingStub { call: c.call.clone(), snapshot: snapshot.unwrap_or_default(), returns }
        })
        .collect();
    let handler = spec.handler.split('#').next().unwrap_or(&spec.handler).rsplit('.').next().unwrap_or("").to_string();
    Ok(EffectLogPlan { entry: spec.id.clone(), assumptions: assumptions(&environment, &handler), environment, stubs })
}

fn assumptions(environment: &EnvironmentModel, handler: &str) -> Vec<String> {
    let mut out: Vec<String> = environment
        .calls
        .iter()
        .map(|c| match c.model.as_ref().and_then(|m| crate::environment::lower(c, m).ok()) {
            Some(m) => m.assumption(&short(&c.call)),
            None => format!("{} is a recording stub in both builds: a recorded attempt is the call attempted, with its payload snapshotted at the call, not a delivery or a commit", short(&c.call)),
        })
        .collect();
    let failing: Vec<String> = environment.calls.iter().filter(|c| c.model.as_ref().and_then(|m| crate::environment::lower(c, m).ok()).is_some_and(|m| !m.throws.is_empty())).map(|c| short(&c.call)).collect();
    if failing.is_empty() && !environment.calls.is_empty() {
        out.push("every modeled call returns normally, the environment model's only outcome: a failure of a store, broker or client is outside the claim".into());
    } else if !failing.is_empty() {
        out.push(format!("only {} may fail, and only as its model says: each failure a new instance of its class, made by its constructor without arguments, with no message, cause or stack the dependency would give, which no handler of either build reads; every other modeled call returns normally", failing.join(" and ")));
    }
    if !handler.is_empty() {
        out.push(format!("{handler} is made by its constructor with every dependency null and every other argument zero, in both builds: its dependencies are reached only through the modeled calls, and configuration it would be given is the type's default"));
    }
    out.push("a payload string is snapshotted as the literal it is, among those of either build; any other string leaves the result unresolved".into());
    out.push(format!("at most {} attempts are recorded, exactly in order; one more leaves the result unresolved", environment.trace_bound));
    out
}

fn short(call: &str) -> String {
    match split_call(call) {
        Some((owner, name, _)) => format!("{}.{name}", owner.rsplit('/').next().unwrap_or(&owner)),
        None => call.to_string(),
    }
}

/// `owner#name(descriptor)` into its parts.
fn split_call(call: &str) -> Option<(String, String, String)> {
    let (owner, rest) = call.split_once('#')?;
    let paren = rest.find('(')?;
    Some((owner.to_string(), rest[..paren].to_string(), rest[paren..].to_string()))
}

fn unsupported(what: impl Into<String>) -> Unsupported {
    Unsupported::new(Part::Observations, what)
}

/// Discharges the obligations of the entry point `old` (in the classes under `before`) against `new` (under
/// `after`): see the module's documentation.
pub fn check(claim: &CanonicalClaim, old: &EntryPointSpec, new: &EntryPointSpec, before: &Path, after: &Path) -> Result<Checked, Unsupported> {
    check_with(claim, old, new, before, after, None)
}

/// [`check`], with the effect-trace proof under the proof cache in `cache` ([`crate::proof_cache`]) when one is given.
/// The proof is a regression check of the two rewritten builds, so its claim key digests their closures from the
/// generated entry method: the handler and what it reaches, the recording stubs, and so the environment model the
/// stubs encode (the modeled calls in log order, the payload paths each snapshots, the trace bound, the exception
/// classes the outcome tells apart and the string literals a snapshot can name). A change to any of them is a
/// different key. Everything else in the result (the specs' unresolved parts, the external inputs, the status
/// mapping) is worked out again on every run, hit or not, and a stored refutation is replayed on a JVM as a new one is.
pub fn check_with(claim: &CanonicalClaim, old: &EntryPointSpec, new: &EntryPointSpec, before: &Path, after: &Path, cache: Option<&Path>) -> Result<Checked, Unsupported> {
    let work = crate::tla::tempfile_path("jvmcontract-effects");
    let checked = check_in(&work, claim, old, new, before, after, cache, None);
    let _ = std::fs::remove_dir_all(&work);
    checked
}

/// The effect check of a claim about an ordinary method (`pkg.Class#method`, the quote family's E1 and E2 rows of
/// `llm-dlc/loops/application-core-acceptance.md`), whose receiver and parameters its planned domain makes
/// ([`crate::construction::flat_roots`]: each by its constructor from flat inputs, a String among them of the
/// values stream's adapter, and each dependency null, reached only through the environment model's stubs). The
/// entry method takes the plan's flat inputs and the environment's tables, makes the roots, calls the method, and
/// returns its log, which [`check_with`]'s check compares as it does a handler's: the outcome by class, the result,
/// and the attempts at the observed calls in order, each payload String snapshotted by its content within the
/// claim's String bound. A String key of a modelled call is compared by its content too. A payload path of a call
/// that takes one argument is read from that argument (`code` of `send(QuoteEvent event)` is `event.code`).
///
/// The domain is enforced as the regression check's gate does: its classes are the plan's, its nullable and
/// may-alias choices are the plan's own (none, here), and a version whose plan makes more input objects than its
/// bound, or whose code may make more objects in one call than its allocation bound, leaves the result unresolved.
/// What the plan doesn't make here (an object inside another, a null or shared root, a factory, a setup sequence,
/// a String or array bound other than the claim's) is refused by name. Under the proof cache when `cache` is given,
/// as [`check_with`] is.
pub fn check_planned(claim: &CanonicalClaim, before: &Path, after: &Path, cache: Option<&Path>) -> Result<Checked, Unsupported> {
    let work = crate::tla::tempfile_path("jvmcontract-effects");
    let checked = check_planned_in(&work, claim, before, after, cache);
    let _ = std::fs::remove_dir_all(&work);
    checked
}

fn check_planned_in(work: &Path, claim: &CanonicalClaim, before: &Path, after: &Path, cache: Option<&Path>) -> Result<Checked, Unsupported> {
    let gap = |what: String| Unsupported::new(Part::Environment, what);
    let subject = &claim.contract.subject;
    let (class_dotted, method_name) = subject.split_once('#').ok_or_else(|| gap(format!("{subject} is not a method, pkg.Class#method")))?;
    let class_name = class_dotted.replace('.', "/");
    let Some(environment) = claim.environment.as_ref() else {
        return Err(gap(format!("a claim of {subject} without an environment model: a regression claim, which spec::heap checks")));
    };
    let Some(domain) = claim.domain.as_ref() else { return Err(gap(format!("a claim of {subject} without a domain: the effect check makes a method's inputs by a construction plan"))) };
    let crate::spec::Construction::Planned { before: plan_before, after: plan_after } = &domain.made_by else {
        return Err(gap(format!("a domain made {}: the effect check makes a method's inputs by a construction plan", match &domain.made_by {
            crate::spec::Construction::Constructors { .. } => "by the constructors a regression check finds",
            crate::spec::Construction::FieldByField => "field by field",
            crate::spec::Construction::Invariant { .. } => "of invariants",
            crate::spec::Construction::Planned { .. } => "by a plan",
        })));
    };
    if !domain.nullable.is_empty() || !domain.may_alias.is_empty() {
        return Err(Unsupported::new(Part::Objects, "a planned domain's nullable and may_alias: the plan's nodes say which inputs may be null or one object"));
    }
    if claim.correspondence.is_some() {
        return Err(gap("a correspondence in an effect claim: both builds are given the same inputs and the same environment".into()));
    }
    if !matches!(claim.tools.checker.as_str(), "native strict" | "native") {
        return Err(gap(format!("the checker {}: the effect check runs on the own checker", claim.tools.checker)));
    }
    if let Some(o) = claim.observations.iter().find(|o| !matches!(o, Observation::Result | Observation::Exception | Observation::Effect { .. })) {
        return Err(gap(format!("the observation {}: the effect check compares the outcome, the result and the attempts at the observed calls", o.id())));
    }
    let (before_cp, _) = class_path(before)?;
    let (after_cp, _) = class_path(after)?;
    let bound = claim.bounds.max_array_length;
    // Each build's method, its inputs' names (`this` first), and its roots as the plan makes them.
    let roots = |cp: &ClassPath, plan: &crate::spec::plans::ConstructionPlan, build: &str| -> Result<Vec<crate::construction::Flat>, Unsupported> {
        let class = cp.application(&class_name).ok().flatten().ok_or_else(|| gap(format!("the {build} build has no class {class_dotted}")))?;
        let candidates: Vec<_> = class.methods.iter().filter(|m| m.name == method_name && !m.is_synthetic() && !m.is_bridge()).collect();
        let [method] = candidates.as_slice() else { return Err(gap(format!("{subject} names {} methods in the {build} build", candidates.len()))) };
        let names: Vec<String> = (!method.is_static()).then(|| "this".to_string()).into_iter().chain(method.parameter_names(&class.pool)).collect();
        crate::construction::flat_roots(cp, plan, &names, bound).map_err(|u| Unsupported::new(u.part, format!("the {build} build: {}", u.what)))
    };
    let made_before = roots(&before_cp, plan_before, "old")?;
    let made_after = roots(&after_cp, plan_after, "new")?;
    let inputs = |made: &[crate::construction::Flat]| made.iter().flat_map(|r| r.inputs().map(|(p, t)| (p.to_string(), t.clone()))).collect::<Vec<_>>();
    if inputs(&made_before) != inputs(&made_after) {
        let words = |made: &[crate::construction::Flat]| inputs(made).iter().map(|(p, t)| format!("{p}: {}", t.java_name())).collect::<Vec<_>>().join(", ");
        return Err(Unsupported::new(Part::Objects, format!("the plans' inputs differ: ({}) before, ({}) now; both builds are given the same inputs", words(&made_before), words(&made_after))));
    }
    // The domain gate: its classes are the ones the plans make.
    let made_classes: BTreeSet<String> = made_before.iter().chain(&made_after).map(|r| r.class.replace('/', ".")).collect();
    let stated: BTreeSet<String> = domain.classes.iter().cloned().collect();
    if made_classes != stated {
        return Err(gap(format!("the domain's classes ({}) aren't the ones its plans make ({})", stated.into_iter().collect::<Vec<_>>().join(", "), made_classes.into_iter().collect::<Vec<_>>().join(", "))));
    }
    let required = claim.contract.required.clone();
    let restrictions = if plan_after.restrictions.is_empty() { String::new() } else { format!(" ({})", plan_after.restrictions.join("; ")) };
    let flat = inputs(&made_after);
    let models: Vec<String> = environment.calls.iter().filter_map(|c| c.model.as_ref().and_then(|m| crate::environment::lower(c, m).ok()).map(|m| m.domain(&short(&c.call)))).collect();
    let mut words = format!("{}{restrictions}: {}", domain.label, flat.iter().map(|(p, t)| format!("{p}: {}", t.java_name())).collect::<Vec<_>>().join(" × "));
    if !models.is_empty() {
        words.push_str(&format!(" × the environment's answers, one for both builds: {}", models.join("; ")));
    }
    let unresolved = |problem: String| Checked {
        outcome: Outcome { verdict: Verdict::Unresolved, domain: words.clone(), accounting: required.iter().map(|r| Accounted { observation: r.clone(), state: ObservationState::Unresolved }).collect(), witness: None, problem: Some(problem.clone()) },
        reason: Some(problem),
        assumptions: Vec::new(),
        proof: None,
        before: None,
        after: None,
        key: None,
        reuse: None,
    };
    // The domain's bounds, as the regression check's gate counts them: the input objects the plan makes, and what
    // each version's code makes in one call.
    for (version, build, made, bounds) in [("previous", before, &made_before, &domain.bounds.before), ("new", after, &made_after, &domain.bounds.after)] {
        if made.len() as u32 > bounds.input_objects {
            return Ok(unresolved(format!("the {version} version's inputs are made of {} objects, more than the claim's bound of {}: the check would be about inputs outside the claim", made.len(), bounds.input_objects)));
        }
        let problem = match crate::spec::heap::allocations(build, subject) {
            Ok(Some(n)) if n <= bounds.allocations => continue,
            Ok(Some(n)) => format!("the {version} version's code may make {n} objects in one call, more than the claim's allocation bound of {}: the check would be about calls outside the claim", bounds.allocations),
            Ok(None) => format!("the {version} version's code makes objects in a loop or a recursion, which no number bounds, and the claim's allocation bound is {}: the check would be about calls outside the claim", bounds.allocations),
            Err(e) => format!("the {version} version's allocations could not be counted against the claim's allocation bound of {}: {e}", bounds.allocations),
        };
        return Ok(unresolved(problem));
    }
    // The observed calls' payload paths, each from a parameter of the call: a path of a call of one argument that
    // names none is read from that argument.
    let parameter_names = |call: &str| -> Vec<String> {
        let Some((owner, name, d)) = split_call(call) else { return Vec::new() };
        let count = MethodDescriptor::parse(&d).map(|d| d.params.len()).unwrap_or(0);
        let named = [&after_cp, &before_cp].into_iter().find_map(|cp| cp.application(&owner).ok().flatten().and_then(|c| c.method(&name, &d).map(|m| m.parameter_names(&c.pool))));
        named.filter(|n| n.len() == count).unwrap_or_else(|| (0..count).map(|i| format!("arg{i}")).collect())
    };
    let observations: Vec<Observation> = claim.observations.iter().map(|o| match o {
        Observation::Effect { call, payload } => {
            let names = parameter_names(call);
            let payload = payload.iter().map(|p| {
                let first = p.split('.').next().unwrap_or(p);
                if names.len() == 1 && !names.iter().any(|n| n == first) { format!("{}.{p}", names[0]) } else { p.clone() }
            }).collect();
            Observation::Effect { call: call.clone(), payload }
        }
        other => other.clone(),
    }).collect();
    let sites: Vec<crate::spec::observe::EffectSite> = observations.iter().filter_map(|o| match o {
        Observation::Effect { call, payload } => {
            let d = split_call(call).and_then(|(_, _, d)| MethodDescriptor::parse(&d).ok())?;
            let arguments = parameter_names(call).into_iter().zip(&d.params).map(|(name, t)| crate::spec::observe::CallArgument { name, class: t.class_name().map(str::to_string) }).collect();
            Some(crate::spec::observe::EffectSite { kind: crate::spec::observe::SiteKind::Call, target: short(call), call: call.clone(), payload: payload.clone(), placement: crate::spec::observe::Placement::Outside, in_method: subject.clone(), arguments })
        }
        _ => None,
    }).collect();
    let spec = EntryPointSpec {
        id: subject.clone(),
        handler: subject.clone(),
        inputs: claim.contract.inputs.clone(),
        observations: observations.clone(),
        environment: environment.clone(),
        unresolved: Vec::new(),
        kind: Default::default(),
        declared: String::new(),
        bindings: Vec::new(),
        response: None,
        statuses: Vec::new(),
        effects: sites,
        identity: String::new(),
        assumptions: Vec::new(),
        source_line: None,
        method: String::new(),
    };
    let mut assumptions = vec![format!(
        "{} made by the plan's constructors from the inputs, the same in both builds, each dependency null in both and reached only through the modelled calls' stubs; a constructor's exception is the outcome, as the call's is",
        made_after.iter().map(|r| format!("{} a {}", r.root, r.class.rsplit('/').next().unwrap_or(&r.class))).collect::<Vec<_>>().join(", ")
    )];
    if flat.iter().any(|(_, t)| crate::values::is_string(t)) {
        assumptions.push(format!("a String input is the values stream's String of at most {bound} UTF-16 code units, any content, never null"));
    }
    assumptions.push(format!("a payload string is snapshotted by its content, at most {bound} code units; a longer one leaves the result unresolved"));
    if environment.calls.iter().filter_map(|c| c.model.as_ref().and_then(|m| crate::environment::lower(c, m).ok())).any(|m| m.key.iter().any(|(_, t)| crate::values::is_string(t))) {
        assumptions.push(format!("a String key is compared by its content; one of more than {bound} code units, which the environment's table holds no key of, leaves the result unresolved"));
    }
    let planned = Planned { before: made_before, after: made_after, names: flat.iter().map(|(p, _)| p.clone()).collect(), domain: words.clone(), assumptions };
    let claim = CanonicalClaim { observations, ..claim.clone() };
    check_in(work, &claim, &spec, &spec, before, after, cache, Some(&planned))
}

/// The claim an entry point's own spec holds a new build to: its inputs, every observation it has, its environment
/// model (the trace bound replaced when `trace_bound` is given), and `bounds`. No change is approved. The closures and
/// the tools are named, not digested: that is the cache's (`spec::cache::key`), and this check doesn't consult it.
pub fn claim_for(spec: &EntryPointSpec, trace_bound: Option<u32>, bounds: ClaimBounds) -> CanonicalClaim {
    let mut environment = spec.environment.clone();
    if let Some(bound) = trace_bound {
        environment.trace_bound = bound;
    }
    let assumptions = assumptions(&environment, spec.handler.split('#').next().unwrap_or("").rsplit('.').next().unwrap_or(""));
    CanonicalClaim {
        contract: PreservationContract { subject: spec.id.clone(), inputs: spec.inputs.clone(), required: spec.observations.iter().map(Observation::id).collect(), approved_changes: Vec::new() },
        closures: VersionDigests { before: "not digested".into(), after: "not digested".into() },
        domain: None,
        observations: spec.observations.clone(),
        correspondence: None,
        environment: Some(environment),
        bounds,
        assumptions,
        tools: ToolIdentity { models: "not digested".into(), jdk: "the default JDK".into(), checker: "native strict".into(), binary: "not digested".into() },
    }
}

/// `claim` with the modelled calls a person declared (`--environment`) in its environment model: each replaces the
/// call of the same name, model and outcomes, or is added after the others. The assumptions follow.
pub fn with_environment(mut claim: CanonicalClaim, declared: &[ModeledCall], handler: &str) -> CanonicalClaim {
    if declared.is_empty() {
        return claim;
    }
    let Some(environment) = claim.environment.as_mut() else { return claim };
    for d in declared {
        match environment.calls.iter_mut().find(|c| c.call == d.call) {
            Some(c) => *c = d.clone(),
            None => environment.calls.push(d.clone()),
        }
    }
    claim.assumptions = assumptions(environment, handler.split('#').next().unwrap_or("").rsplit('.').next().unwrap_or(""));
    claim
}

/// One entry point of the old build, checked against its counterpart in the new one.
#[derive(Debug, Clone, Serialize)]
pub struct EntryCheck {
    pub entry: String,
    /// The old build's handler (`Class#method`) and the line it starts at, which a report anchors to.
    pub handler: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_line: Option<u16>,
    /// The counterpart's id, when it differs (a path variable renamed).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub new_entry: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub checked: Option<Checked>,
    /// Why the narrow case can't check it, when it can't (string or object inputs, a used result, modeled failures).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unsupported: Option<String>,
}

/// The SARIF findings of `checks`: one `effects-changed` per refuted entry point, its witness the message, anchored
/// at the old build's handler when its source is under one of `sources` (the path made relative to `base`).
pub fn findings(checks: &[EntryCheck], sources: &[PathBuf], base: Option<&Path>) -> Vec<crate::sarif::Finding> {
    checks
        .iter()
        .filter_map(|c| {
            let checked = c.checked.as_ref()?;
            if checked.outcome.verdict != Verdict::Refuted {
                return None;
            }
            let class = c.handler.split_once('#').map(|(class, _)| class.replace('.', "/")).unwrap_or_default();
            let file = crate::sarif::source_file(&class, sources);
            let uri = file.map(|f| base.map(|b| crate::sarif::relative_uri(b, &f)).unwrap_or_else(|| f.display().to_string()));
            let message = format!("{} no longer preserves its trace of modeled boundary calls: {}", c.entry, checked.outcome.witness.as_deref().unwrap_or("a counterexample"));
            Some(crate::sarif::Finding::new("effects-changed", message, uri, c.source_line.map(u32::from).unwrap_or(1)))
        })
        .collect()
}

/// Every entry point of the classes under `before` (or those of `only`, by id), each checked against its
/// counterpart under `after`, matched as `observations --against` matches them, under the claim its own spec makes
/// ([`claim_for`]). An entry point with no counterpart is unresolved; one the narrow case can't model is reported
/// as unsupported, and the others are still checked. With `cache`, each proof runs under the proof cache
/// ([`check_with`]).
pub fn check_builds(before: &Path, after: &Path, only: &[String], trace_bound: Option<u32>, bounds: ClaimBounds, cache: Option<&Path>, environment: &[ModeledCall]) -> Result<Vec<EntryCheck>, Unsupported> {
    // The modelled calls a person declares (`--environment`): the environment stream's (E1–E3). Until it builds
    // their models, they are refused before any entry point is checked.
    crate::environment::declared(environment)?;
    let old = crate::spec::observe::entry_points(before)?;
    let new = crate::spec::observe::entry_points(after)?;
    for id in only {
        if !old.iter().any(|s| &s.id == id) {
            return Err(unsupported(format!("no entry point {id} in {}; it has {}", before.display(), old.iter().map(|s| s.id.as_str()).collect::<Vec<_>>().join(", "))));
        }
    }
    let obligations = crate::observations::compare(&old, &new);
    let mut out = Vec::new();
    for spec in old.iter().filter(|s| only.is_empty() || only.contains(&s.id)) {
        let claim = with_environment(claim_for(spec, trace_bound, bounds.clone()), environment, &spec.handler);
        let matched = obligations.iter().find(|o| o.entry == spec.id && o.change != Change::Removed && o.change != Change::New).map(|o| o.new_entry.clone().unwrap_or_else(|| spec.id.clone()));
        let counterpart = matched.as_ref().and_then(|id| new.iter().find(|s| &s.id == id));
        let new_entry = matched.clone().filter(|id| id != &spec.id);
        let Some(counterpart) = counterpart else {
            let domain = domain_of(spec, claim.environment.as_ref().unwrap_or(&spec.environment));
            let checked = Checked {
                outcome: Outcome { verdict: Verdict::Unresolved, domain, accounting: claim.contract.required.iter().map(|r| Accounted { observation: r.clone(), state: ObservationState::Unresolved }).collect(), witness: None, problem: Some(format!("{} has no counterpart in {}: removed, renamed, or not told apart from another", spec.id, after.display())) },
                reason: Some(format!("{} has no counterpart in {}: removed, renamed, or not told apart from another", spec.id, after.display())),
                assumptions: claim.assumptions.clone(),
                proof: None,
                before: None,
                after: None,
                key: None,
                reuse: None,
            };
            out.push(EntryCheck { entry: spec.id.clone(), handler: spec.handler.clone(), source_line: spec.source_line, new_entry, checked: Some(checked), unsupported: None });
            continue;
        };
        match check_with(&claim, spec, counterpart, before, after, cache) {
            Ok(checked) => out.push(EntryCheck { entry: spec.id.clone(), handler: spec.handler.clone(), source_line: spec.source_line, new_entry, checked: Some(checked), unsupported: None }),
            Err(u) => out.push(EntryCheck { entry: spec.id.clone(), handler: spec.handler.clone(), source_line: spec.source_line, new_entry, checked: None, unsupported: Some(u.what.clone()) }),
        }
    }
    Ok(out)
}

/// The text `jvmcontract effects` prints: per entry point its verdict, what each required observation became, the
/// proof or the witness (with each build's attempts) or why it is unresolved, the domain and the assumptions; then
/// the count.
pub fn render_checks(checks: &[EntryCheck]) -> String {
    let mut s = String::new();
    let mut counts = [0usize; 4];
    for c in checks {
        let name = match &c.new_entry {
            Some(n) => format!("{} (now {n})", c.entry),
            None => c.entry.clone(),
        };
        let Some(k) = &c.checked else {
            counts[3] += 1;
            s.push_str(&format!("{name}: unsupported: {}\n", c.unsupported.as_deref().unwrap_or("")));
            continue;
        };
        let verdict = match k.outcome.verdict {
            Verdict::Verified => {
                counts[0] += 1;
                "verified"
            }
            Verdict::Refuted => {
                counts[1] += 1;
                "refuted"
            }
            Verdict::Unresolved => {
                counts[2] += 1;
                "unresolved"
            }
        };
        s.push_str(&format!("{name}: {verdict}\n"));
        let accounting = k
            .outcome
            .accounting
            .iter()
            .map(|a| {
                let id = a.observation.strip_prefix("effect:").map(short).unwrap_or_else(|| a.observation.clone());
                let state = match a.state {
                    ObservationState::Preserved => "preserved",
                    ObservationState::ChangedWithApproval => "changed with approval",
                    ObservationState::Unresolved => "unresolved",
                    ObservationState::Refuted => "refuted",
                };
                format!("{id} {state}")
            })
            .collect::<Vec<_>>()
            .join(", ");
        s.push_str(&format!("  observations: {accounting}\n"));
        if let Some(r) = &k.reason {
            s.push_str(&format!("  why: {r}\n"));
        }
        if let Some(w) = &k.outcome.witness {
            s.push_str(&format!("  witness: {w}\n"));
        } else if let (Some(b), Some(a)) = (&k.before, &k.after) {
            s.push_str(&format!("  the old build: {}\n  the new build: {}\n", b.words(), a.words()));
        }
        if let Some(p) = &k.proof {
            s.push_str(&format!("  {}: {p}\n", if k.outcome.verdict == Verdict::Verified { "proof" } else { "search" }));
        }
        s.push_str(&format!("  domain: {}\n", k.outcome.domain));
        if let Some(crate::spec::cache::Reuse::Exact { key, from }) = &k.reuse {
            s.push_str(&format!("  reused: an exact hit of the same claim ({}), from {from}: nothing was proved again\n", key.0));
        }
        for a in &k.assumptions {
            s.push_str(&format!("  assumes: {a}\n"));
        }
    }
    s.push_str(&format!("{} entry points: {} verified, {} refuted, {} unresolved, {} unsupported\n", checks.len(), counts[0], counts[1], counts[2], counts[3]));
    s
}

fn domain_of(spec: &EntryPointSpec, environment: &EnvironmentModel) -> String {
    let domain = spec.inputs.iter().map(|i| format!("{}: {}", i.name, i.ty)).collect::<Vec<_>>().join(" × ");
    let mut s = format!("{} (the request's inputs, the same in both builds)", if domain.is_empty() { "no inputs".to_string() } else { domain });
    let models: Vec<String> = environment.calls.iter().filter_map(|c| c.model.as_ref().and_then(|m| crate::environment::lower(c, m).ok()).map(|m| m.domain(&short(&c.call)))).collect();
    if !models.is_empty() {
        s.push_str(&format!(" × the environment's answers, one for both builds: {}", models.join("; ")));
    }
    s
}

/// A planned subject's inputs, for [`check_in`]: each build's roots as the effect check makes them
/// ([`crate::construction::flat_roots`]), the names of their flat inputs in order, and what the result is about.
struct Planned {
    before: Vec<crate::construction::Flat>,
    after: Vec<crate::construction::Flat>,
    names: Vec<String>,
    domain: String,
    assumptions: Vec<String>,
}

/// [`check`], with the builds, the proof and the JVM run under `work`.
#[allow(clippy::too_many_arguments)] // the parts of one check
fn check_in(work: &Path, claim: &CanonicalClaim, old: &EntryPointSpec, new: &EntryPointSpec, before: &Path, after: &Path, cache: Option<&Path>, planned: Option<&Planned>) -> Result<Checked, Unsupported> {
    let required = claim.contract.required.clone();
    let environment = claim.environment.clone().unwrap_or_else(|| old.environment.clone());
    let handler = old.handler.split('#').next().unwrap_or("").rsplit('.').next().unwrap_or("").to_string();
    let assumed = match planned {
        Some(p) => {
            let mut a: Vec<String> = assumptions(&environment, "").into_iter().filter(|a| !a.starts_with("a payload string is snapshotted as the literal")).collect();
            a.extend(p.assumptions.iter().cloned());
            a
        }
        None => assumptions(&environment, &handler),
    };
    let domain = match planned {
        Some(p) => p.domain.clone(),
        None => domain_of(old, &environment),
    };
    let unresolved = |reason: String| Checked {
        outcome: Outcome { verdict: Verdict::Unresolved, domain: domain.clone(), accounting: required.iter().map(|r| Accounted { observation: r.clone(), state: ObservationState::Unresolved }).collect(), witness: None, problem: Some(reason.clone()) },
        reason: Some(reason),
        assumptions: assumed.clone(),
        proof: None,
        before: None,
        after: None,
        key: None,
        reuse: None,
    };
    let (before_cp, before_local) = class_path(before)?;
    let (after_cp, after_local) = class_path(after)?;
    // A call the walk can't follow on the owner of a modelled call is the call the model answers: every call on
    // that owner is redirected, to the model's stub or to one that marks the log unresolved where it is reached.
    // The analysis names the owner by its simple name, so only one that names one class of either build.
    let answered = |u: &str| {
        environment.calls.iter().filter(|c| c.model.is_some()).filter_map(|c| split_call(&c.call)).any(|(owner, _, _)| {
            let simple = owner.rsplit('/').next().unwrap_or(&owner).to_string();
            let named: BTreeSet<&String> = before_local.iter().chain(&after_local).filter(|l| l.rsplit('/').next() == Some(simple.as_str())).collect();
            named.len() == 1 && named.contains(&owner) && u.starts_with(&format!("a call the walk can't follow: {simple}.")) && u.ends_with(": nothing followed implements it")
        })
    };
    let unseen: Vec<String> = old.unresolved.iter().filter(|u| !answered(u)).map(|u| format!("the old build: {u}")).chain(new.unresolved.iter().filter(|u| !answered(u)).map(|u| format!("the new build: {u}"))).collect();
    if !unseen.is_empty() {
        return Ok(unresolved(format!("what the analysis can't see stays unresolved: {}", unseen.join("; "))));
    }
    let obligations = crate::observations::compare(std::slice::from_ref(old), std::slice::from_ref(new));
    let static_change = |id: &str| obligations.iter().find(|o| o.observation == id && o.entry == old.id).map(|o| o.change);
    if let Some(o) = obligations.iter().find(|o| o.observation == "inputs" && o.change != Change::Preserved) {
        return Ok(unresolved(format!("the external inputs differ ({}), and the contract fixes them: {}", o.differences.join("; "), o.needs)));
    }
    if static_change("result") == Some(Change::Removed) {
        return Ok(unresolved(format!("{} has no counterpart in the new build", old.id)));
    }
    for c in environment.calls.iter() {
        if let Some(model) = &c.model {
            crate::environment::check_model(c, model)?;
        } else if let Some(o) = c.outcomes.iter().find(|o| *o != "returns") {
            return Err(unsupported(format!("a modeled outcome other than a normal return ({o} of {}) with no model of the call's results: a modelled failure is a result of its model (crate::environment)", short(&c.call))));
        }
    }
    let lowered = |call: &str| -> Option<crate::environment::Lowered> {
        let c = environment.calls.iter().find(|c| c.call == call)?;
        crate::environment::lower(c, c.model.as_ref()?).ok()
    };
    // The modelled failures: each a Throwable both builds have, made by a constructor without arguments, and a
    // caught one read for nothing but its class.
    let thrown: Vec<String> = environment.calls.iter().filter_map(|c| lowered(&c.call)).flat_map(|m| m.throws).collect::<BTreeSet<_>>().into_iter().collect();
    for class in &thrown {
        for (cp, build) in [(&before_cp, "old"), (&after_cp, "new")] {
            failure_class(cp, class).map_err(|why| Unsupported::new(Part::Environment, format!("the modelled failure {} in the {build} build: {why}", class.replace('/', "."))))?;
        }
    }
    if !thrown.is_empty() {
        for (dir, cp, build) in [(before, &before_cp, "old"), (after, &after_cp, "new")] {
            inspections(dir, cp, &thrown).map_err(|why| Unsupported::new(Part::Environment, format!("the {build} build {why}")))?;
        }
    }
    // The DTO responses (E3): each class made by the objects stream's plan in both builds, and data: no build calls
    // a method of one or writes its field.
    let responses: Vec<(String, crate::environment::Response)> = environment.calls.iter().filter_map(|c| lowered(&c.call).and_then(|m| m.response).map(|r| (c.call.clone(), r))).collect();
    for (call, r) in &responses {
        for (dir, cp, build) in [(before, &before_cp, "old"), (after, &after_cp, "new")] {
            crate::environment::check_response(cp, r).map_err(|why| Unsupported::new(Part::Environment, format!("a DTO response of {}, a {}, in the {build} build: {why}", short(call), r.class.replace('/', "."))))?;
            response_uses(dir, r).map_err(|why| Unsupported::new(Part::Environment, format!("a DTO response of {}: the {build} build {why}", short(call))))?;
        }
    }

    // The model: the claim's calls, then any either spec has besides.
    let mut calls: Vec<String> = environment.calls.iter().map(|c| c.call.clone()).collect();
    for s in [old, new] {
        for c in &s.environment.calls {
            if !calls.contains(&c.call) {
                calls.push(c.call.clone());
            }
        }
    }
    let mut observed: Vec<Option<Vec<String>>> = calls
        .iter()
        .map(|call| {
            [&claim.observations, &old.observations, &new.observations].into_iter().find_map(|obs| {
                obs.iter().find_map(|o| match o {
                    Observation::Effect { call: c, payload } if c == call => Some(payload.clone()),
                    _ => None,
                })
            })
        })
        .collect();
    // Where the call sites of either build pass an argument of more than one class, the class is observed too: a
    // `.class` path after the spec's, the same in both builds.
    let mut classes = BTreeSet::new();
    for (call, paths) in calls.iter().zip(observed.iter_mut()) {
        let Some(paths) = paths else { continue };
        let sites: Vec<_> = [old, new].into_iter().flat_map(|s| s.effects.iter().filter(|e| &e.call == call)).collect();
        let Some(first) = sites.first() else { continue };
        for (k, argument) in first.arguments.iter().enumerate() {
            let passed: BTreeSet<&String> = sites.iter().filter_map(|e| e.arguments.get(k).and_then(|a| a.class.as_ref())).collect();
            classes.extend(passed.iter().map(|c| c.to_string()));
            let class_path = format!("{}.class", argument.name);
            if passed.len() > 1 && paths.iter().any(|p| p.starts_with(&format!("{}.", argument.name))) && !paths.contains(&class_path) {
                paths.push(class_path);
            }
        }
    }
    let mut exceptions: Vec<(usize, String)> = Vec::new();
    for (cp, local) in [(&before_cp, &before_local), (&after_cp, &after_local)] {
        for name in local.iter().chain(&thrown) {
            if cp.superclasses(name).iter().any(|s| s == "java/lang/Throwable") && !exceptions.iter().any(|(_, n)| n == name) {
                exceptions.push((cp.superclasses(name).len(), name.clone()));
            }
        }
    }
    exceptions.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));
    let mut exceptions: Vec<String> = exceptions.into_iter().map(|(_, n)| n).collect();
    exceptions.extend(crate::harness::EXCEPTIONS.iter().map(|s| s.to_string()));
    let mut literals = BTreeSet::new();
    for dir in [before, after] {
        for (_, bytes) in class_files(dir).map_err(|e| unsupported(format!("reading {}: {e}", dir.display())))? {
            if let Ok(class) = ClassFile::parse(&bytes) {
                for c in class.pool.entries() {
                    if let Constant::String { string_index } = c {
                        if let Ok(s) = class.pool.utf8(*string_index) {
                            literals.insert(s.to_string());
                        }
                    }
                }
            }
        }
    }
    let models = calls.iter().map(|c| lowered(c)).collect();
    let model = Model { calls, observed, bound: environment.trace_bound as usize, exceptions, literals: literals.into_iter().collect(), classes: classes.into_iter().collect(), models, string_bound: claim.bounds.max_array_length as usize, content: planned.is_some() };

    let _ = std::fs::remove_dir_all(work);
    let old_version = prepare(old, &before_cp, &before_local, before, &work.join("before"), &model, 1, planned.map(|p| p.before.as_slice()))?;
    let new_version = prepare(new, &after_cp, &after_local, after, &work.join("after"), &model, 2, planned.map(|p| p.after.as_slice()))?;

    let mut options = crate::equivalence::Options::new(&work.join("before"), &work.join("after"), &new_version.target);
    if old_version.target != new_version.target {
        options.before_target = Some(old_version.target.clone());
    }
    options.engine = crate::Engine::Native;
    options.work = Some(work.join("check"));
    options.unwind = claim.bounds.unwind;
    options.max_array_length = claim.bounds.max_array_length;
    options.timeout_seconds = 300;
    options.cache = cache.map(Path::to_path_buf);
    options.copied_from = Some((before.to_path_buf(), after.to_path_buf()));
    let mark = crate::proof_cache::key_mark();
    let result = crate::equivalence::run(&options).map_err(|e| unsupported(format!("the effect-trace proof of {}: {e}", old.id)))?;
    let key = cache.and_then(|_| crate::proof_cache::key_since(&new_version.target, mark));
    let reuse = result.reuse.clone().filter(|r| matches!(r, crate::spec::cache::Reuse::Exact { .. }));
    // Every result below carries the proof's key and its reuse, an unresolved one included.
    let unresolved = |reason: String| Checked { key: key.clone(), reuse: reuse.clone(), ..unresolved(reason) };
    let input_names: Vec<String> = match planned {
        Some(p) => p.names.clone(),
        None => old.inputs.iter().map(|i| i.name.clone()).collect(),
    };
    let names: Vec<String> = input_names.iter().cloned().chain(model.models.iter().flatten().flat_map(crate::environment::Lowered::input_names)).collect();
    let proof = result.proof.as_deref().map(|p| with_names(p, &names));
    match result.verdict {
        crate::Verdict::Verified => {
            if let Some(v) = &result.vacuous {
                return Ok(Checked { proof, ..unresolved(format!("the proof is vacuous: {v}")) });
            }
            let mut reasons = Vec::new();
            let accounting = required
                .iter()
                .map(|id| {
                    let state = match id.as_str() {
                        "result" | "exception" => ObservationState::Preserved,
                        _ if id.starts_with("effect:") && model.calls.iter().any(|c| id == &format!("effect:{c}")) => ObservationState::Preserved,
                        "status" => match static_change("status") {
                            Some(Change::Preserved) => ObservationState::Preserved,
                            _ if claim.contract.approved_changes.iter().any(|a| a.observation == "status") => ObservationState::ChangedWithApproval,
                            other => {
                                reasons.push(format!("the status mapping is {} between the builds, and no person approved it", other.map(|c| format!("{c:?}").to_lowercase()).unwrap_or_else(|| "unknown".into())));
                                ObservationState::Unresolved
                            }
                        },
                        _ => {
                            reasons.push(format!("{id} is no observation the effect trace compares"));
                            ObservationState::Unresolved
                        }
                    };
                    Accounted { observation: id.clone(), state }
                })
                .collect::<Vec<_>>();
            let verdict = if reasons.is_empty() { Verdict::Verified } else { Verdict::Unresolved };
            let reason = if reasons.is_empty() { None } else { Some(reasons.join("; ")) };
            Ok(Checked { outcome: Outcome { verdict, domain, accounting, witness: None, problem: reason.clone() }, reason, assumptions: assumed, proof, before: None, after: None, key, reuse })
        }
        crate::Verdict::Unverifiable => Ok(Checked { proof, ..unresolved(format!("the effect-trace proof gave no verdict: {}", result.problem.clone().unwrap_or_default())) }),
        crate::Verdict::Violation => {
            let Some(cex) = &result.counterexample else { return Ok(unresolved("a violation without a counterexample".into())) };
            let arguments: Vec<Argument> = cex.inputs.iter().zip(&new_version.params).map(|(t, ty)| argument(t.value.as_ref(), ty)).collect::<Option<_>>().ok_or_else(|| unsupported("a witness value the JVM run can't pass"))?;
            let shown = input_names
                .iter()
                .zip(&arguments)
                .zip(&new_version.params)
                .map(|((name, a), t)| format!("{name}={}", shown_value(a, t)))
                .collect::<Vec<_>>()
                .join(", ");
            let check_dir = work.join("check");
            let entries = vec![check_dir.join("harness"), work.join("after"), check_dir.join("before-classes")];
            let mut slots = Vec::new();
            let mut slot = 0u16;
            for t in &new_version.params {
                slots.push(slot);
                slot += if matches!(t, Type::Long | Type::Double) { 2 } else { 1 };
            }
            let ret = Type::Array(Box::new(Type::Long));
            let calls = vec![
                crate::jvm_witness::DirectCall { owner: format!("before/{}", old_version.entry), name: METHOD.into(), descriptor: old_version.descriptor.clone(), ret: ret.clone() },
                crate::jvm_witness::DirectCall { owner: new_version.entry.clone(), name: METHOD.into(), descriptor: new_version.descriptor.clone(), ret },
            ];
            let run = match crate::jvm_witness::run(&work.join("jvm"), crate::harness::CLASS, &new_version.params, &slots, &arguments, &calls, &entries) {
                Ok(run) => run,
                Err(e) => return Ok(Checked { proof, ..unresolved(format!("the witness {shown} could not be replayed on a JVM: {e}")) }),
            };
            let logs: Vec<Option<Vec<i64>>> = run.calls.iter().map(|r| r.result_array.as_ref().map(|a| a.iter().map(|v| match v { Value::Long(x) => *x, Value::Int(x) => i64::from(*x), _ => 0 }).collect())).collect();
            let (Some(Some(b)), Some(Some(a))) = (logs.first(), logs.get(1)) else {
                return Ok(Checked { proof, ..unresolved(format!("the witness {shown} ran on the JVM, but a build's log didn't come back: {}", run.calls.iter().map(|r| r.outcome.clone()).collect::<Vec<_>>().join("; "))) });
            };
            let strings: BTreeSet<(usize, usize)> = old_version.strings.union(&new_version.strings).copied().collect();
            let (tb, ta) = (decode(b, &model, &strings), decode(a, &model, &strings));
            if run.check != crate::jvm_witness::Check::Refuted || tb == ta {
                return Ok(Checked { proof, before: Some(tb), after: Some(ta), ..unresolved(format!("the checker's witness {shown} doesn't replay on the JVM ({:?})", run.check)) });
            }
            if !tb.unresolved.is_empty() || !ta.unresolved.is_empty() {
                return Ok(Checked { proof, before: Some(tb.clone()), after: Some(ta.clone()), ..unresolved(format!("on {shown}, a bound or a snapshot is reached: the old build {}; the new one {}", tb.words(), ta.words())) });
            }
            let mut refuted: BTreeSet<String> = BTreeSet::new();
            // The status of each build's outcome, by its own mapping: a normal return's, or the thrown class's.
            let status_of = |s: &EntryPointSpec, t: &Trace| -> Option<u16> {
                let key = if t.kind == 0 { "returns".to_string() } else { model.exceptions.get(t.kind as usize - 1).map(|e| e.rsplit('/').next().unwrap_or(e).to_string()).unwrap_or_default() };
                s.statuses.iter().find(|x| x.outcome == key && x.when.is_empty()).and_then(|x| x.status)
            };
            if tb.kind != ta.kind {
                refuted.insert("exception".into());
            } else if tb.kind == 0 && tb.result != ta.result {
                refuted.insert("result".into());
            }
            if status_of(old, &tb) != status_of(new, &ta) {
                refuted.insert("status".into());
            }
            let mut effect_differs = false;
            for (i, call) in model.calls.iter().enumerate() {
                let of = |t: &Trace| t.attempts.iter().filter(|x| x.0 == i).map(|x| x.1.clone()).collect::<Vec<_>>();
                if of(&tb) != of(&ta) {
                    refuted.insert(format!("effect:{call}"));
                    effect_differs = true;
                }
            }
            if !effect_differs && tb.attempts != ta.attempts {
                for i in tb.attempts.iter().chain(&ta.attempts).map(|x| x.0) {
                    refuted.insert(format!("effect:{}", model.calls[i]));
                }
            }
            let accounting = required.iter().map(|id| Accounted { observation: id.clone(), state: if refuted.contains(id) { ObservationState::Refuted } else { ObservationState::Unresolved } }).collect();
            let stubs = model.calls.iter().map(|c| short(c)).collect::<Vec<_>>().join(", ");
            let chosen = model.environment_words(arguments.get(input_names.len()..).unwrap_or_default());
            let (under, how) = if chosen.is_empty() {
                (String::new(), "each returning normally")
            } else {
                (format!(" under the environment {chosen}"), "the modelled calls answering from that environment, the others returning normally")
            };
            let witness = format!(
                "{} on {shown}{under}: the old build {}; the new one {}. Replayed on a JVM (JDK {}) under the modeled dependencies (generated stubs for {stubs}, {how}), not against real infrastructure",
                old.id,
                tb.words(),
                ta.words(),
                run.jdk
            );
            Ok(Checked { outcome: Outcome { verdict: Verdict::Refuted, domain, accounting, witness: Some(witness), problem: None }, reason: None, assumptions: assumed, proof, before: Some(tb), after: Some(ta), key, reuse })
        }
    }
}

/// Why `class` can't be a modelled failure in a build of class path `cp`, if it can't: it is a Throwable the build
/// has, with a public constructor without arguments, the one its stub makes it with.
fn failure_class(cp: &ClassPath, class: &str) -> Result<(), String> {
    let file = cp.load(class).ok().flatten().map(|l| l.class).ok_or("no such class")?;
    if !cp.superclasses(class).iter().any(|s| s == "java/lang/Throwable") {
        return Err("it is no Throwable".into());
    }
    if file.is_interface() || file.access & flags::ABSTRACT != 0 {
        return Err("it is abstract: a stub can't make one".into());
    }
    match file.methods.iter().find(|m| m.name == "<init>" && m.descriptor == "()V") {
        Some(m) if m.is_public() => Ok(()),
        _ => Err("it has no public constructor without arguments: the stub makes a failure with none, so that it carries no message or cause the dependency wouldn't give".into()),
    }
}

/// Throwable's methods that read what a modelled failure doesn't carry: its message, cause, stack and suppressed
/// exceptions, or a string of them.
const INSPECTIONS: &[&str] = &["getMessage", "getLocalizedMessage", "getCause", "toString", "getStackTrace", "printStackTrace", "getSuppressed"];

/// Why a build (its classes under `dir`, class path `cp`) reads more of a caught modelled failure (of the classes
/// `thrown`) than its class, if it does. Every handler that may catch one (a catch of one of its classes or a
/// superclass, or a `finally`) is checked where it keeps what it caught: each read of that local (within its scope,
/// when the class says) must rethrow it, test its class or test it for null. Anything else, a call on it or handing
/// it to a call, a field or a return, may read its message or cause, which the model doesn't give, and is refused,
/// never answered with an invented one.
fn inspections(dir: &Path, cp: &ClassPath, thrown: &[String]) -> Result<(), String> {
    let catches = |catch: &Option<String>| match catch {
        None => true,
        Some(c) => thrown.iter().any(|t| t == c || cp.superclasses(t).contains(c)),
    };
    for (_, bytes) in class_files(dir).map_err(|e| format!("can't be read: {e}"))? {
        let Ok(class) = ClassFile::parse(&bytes) else { continue };
        for m in &class.methods {
            let Some(code) = &m.code else { continue };
            let handlers: Vec<_> = code.exception_table.iter().filter(|h| catches(&h.catch_type)).collect();
            if handlers.is_empty() {
                continue;
            }
            let insns = code.instructions().map_err(|e| format!("can't be read: {e}"))?;
            let at = |pc: u32| insns.iter().position(|(p, _)| *p == pc);
            let place = format!("{}.{}", class.name.replace('/', "."), m.name);
            for h in handlers {
                let caught = h.catch_type.as_deref().map(|c| c.replace('/', ".")).unwrap_or_else(|| "any throwable (a finally)".into());
                let Some(start) = at(u32::from(h.handler_pc)) else { continue };
                let slot = match &insns[start].1 {
                    Insn::Pop => continue,
                    Insn::Store(Kind::Ref, n) => *n,
                    other => return Err(format!("catches {caught} in {place} and uses it at once ({other:?}): what it reads of a modelled failure isn't followed, so it is refused")),
                };
                // The local's scope: from its local variable entry when the class has one, else the whole method.
                let after = insns.get(start + 1).map_or(u32::MAX, |(p, _)| *p);
                let scope = code.local_variables.iter().find(|v| v.index == slot && u32::from(v.start_pc) <= after && after <= u32::from(v.start_pc) + u32::from(v.length)).map(|v| (u32::from(v.start_pc), u32::from(v.start_pc) + u32::from(v.length)));
                for (k, (pc, insn)) in insns.iter().enumerate() {
                    if *insn != Insn::Load(Kind::Ref, slot) || scope.is_some_and(|(from, to)| *pc < from || *pc >= to) {
                        continue;
                    }
                    let next = insns.get(k + 1).map(|(_, i)| i);
                    let fine = match next {
                        Some(Insn::AThrow | Insn::InstanceOf(_) | Insn::IfNull(_) | Insn::IfNonNull(_)) => true,
                        Some(Insn::InvokeVirtual(i)) => class.pool.member(*i).is_ok_and(|r| r.name == "getClass" && r.descriptor == "()Ljava/lang/Class;"),
                        _ => false,
                    };
                    if fine {
                        continue;
                    }
                    let what = match next {
                        Some(Insn::InvokeVirtual(i) | Insn::InvokeInterface(i)) => match class.pool.member(*i) {
                            Ok(r) if INSPECTIONS.contains(&r.name.as_str()) => format!("reads its {} ({}.{})", if r.name == "getCause" { "cause" } else if r.name.contains("Stack") { "stack" } else if r.name == "getSuppressed" { "suppressed exceptions" } else { "message" }, r.owner.replace('/', "."), r.name),
                            Ok(r) => format!("calls {}.{} on it", r.owner.replace('/', "."), r.name),
                            Err(_) => "calls a method on it".into(),
                        },
                        Some(other) => format!("hands it on ({other:?})"),
                        None => "hands it on".into(),
                    };
                    return Err(format!("catches {caught} in {place} and {what}: a modelled failure carries its class and no message or cause, so reading any more of it is refused, never answered with an invented one"));
                }
            }
        }
    }
    Ok(())
}

/// Why a build of `dir` uses the DTO response `r` beyond its data, if it does (E3): a call of a method on its class
/// but its constructor, or a write of its field outside its constructors. The stubs make it from the leaves the
/// environment chose, and nothing else of it is modelled: what a method of it would do, or whether a later
/// response would see a write, is refused, never assumed.
fn response_uses(dir: &Path, r: &crate::environment::Response) -> Result<(), String> {
    for (_, bytes) in class_files(dir).map_err(|e| format!("can't be read: {e}"))? {
        let Ok(class) = ClassFile::parse(&bytes) else { continue };
        for m in &class.methods {
            let Some(code) = &m.code else { continue };
            let place = format!("{}.{}", class.name.replace('/', "."), m.name);
            let insns = code.instructions().map_err(|e| format!("can't be read: {e}"))?;
            // A method that handles the response: it is given one, or names its class.
            let named = format!("L{};", r.class);
            let handles = m.descriptor.contains(&named)
                || insns.iter().any(|(_, insn)| match insn {
                    Insn::InvokeVirtual(i) | Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) | Insn::InvokeInterface(i) | Insn::GetField(i) | Insn::PutField(i) => class.pool.member(*i).is_ok_and(|x| x.owner == r.class || x.descriptor.contains(&named)),
                    _ => false,
                });
            for (_, insn) in insns {
                let (index, write) = match insn {
                    Insn::InvokeVirtual(i) | Insn::InvokeSpecial(i) | Insn::InvokeStatic(i) | Insn::InvokeInterface(i) => (i, false),
                    Insn::PutField(i) => (i, true),
                    _ => continue,
                };
                let Ok(member) = class.pool.member(index) else { continue };
                // Object's methods that depend on an object's identity, called where a response is handled: javac
                // names them on Object, so their receiver isn't followed, and on a response they give nothing the
                // model gives.
                if handles && member.owner == "java/lang/Object" && ["hashCode", "toString", "wait", "notify", "notifyAll"].contains(&member.name.as_str()) {
                    return Err(format!("calls java.lang.Object.{} in {place}, which handles a DTO response: on a response it gives no data the model gives, and its receiver isn't followed, so it is refused", member.name));
                }
                if member.owner != r.class {
                    continue;
                }
                if write && !(class.name == r.class && m.is_constructor()) {
                    return Err(format!("writes its field {} in {place}: a DTO response is the dependency's data, and whether a later response sees a write is a state contract this model isn't", member.name));
                }
                if !write && member.name != "<init>" {
                    return Err(format!("calls {}.{} on it in {place}: a DTO response is data, and no method of it beside its constructor is modelled", r.class.replace('/', "."), member.name));
                }
            }
        }
    }
    Ok(())
}

/// `text` with the generated method's parameter names (`arg0`, `arg1`) replaced by the entry point's inputs'.
fn with_names(text: &str, names: &[String]) -> String {
    let mut out = String::new();
    let mut rest = text;
    while let Some(at) = rest.find("arg") {
        let (head, tail) = rest.split_at(at);
        out.push_str(head);
        let digits: String = tail[3..].chars().take_while(char::is_ascii_digit).collect();
        let starts_word = !head.chars().last().is_some_and(|c| c.is_alphanumeric() || c == '_');
        match digits.parse::<usize>().ok().and_then(|i| names.get(i)).filter(|_| starts_word) {
            Some(name) => out.push_str(name),
            None => out.push_str(&tail[..3 + digits.len()]),
        }
        rest = &tail[3 + digits.len()..];
    }
    out.push_str(rest);
    out
}

/// A witness's typed value (`witness::exact_argument`'s form) as the JVM run passes it: a scalar, an array of
/// them, a String by its code units, or the same array or String as an earlier input.
fn argument(value: Option<&serde_json::Value>, t: &Type) -> Option<Argument> {
    let v = value?;
    if let Some(i) = v.get("same").and_then(serde_json::Value::as_u64) {
        return Some(Argument::Same(i as usize));
    }
    if crate::values::is_string(t) {
        return match serde_json::from_value::<crate::spec::plans::WitnessValue>(v.clone()).ok()? {
            crate::spec::plans::WitnessValue::String { units } => Some(Argument::String(units)),
            _ => None,
        };
    }
    if let (Type::Array(element), Some(items)) = (t, v.as_array()) {
        return items.iter().map(|x| match argument(Some(x), element)? {
            Argument::Scalar(v) => Some(v),
            _ => None,
        }).collect::<Option<Vec<_>>>().map(Argument::Array);
    }
    let n = v.as_i64().or_else(|| v.as_str().and_then(|s| s.parse().ok())).or_else(|| v.as_bool().map(i64::from))?;
    Some(Argument::Scalar(match t {
        Type::Long => Value::Long(n),
        _ => Value::Int(n as i32),
    }))
}

/// An input's value as a witness shows it: a number, a boolean, a Java String literal, an array's elements.
fn shown_value(a: &Argument, t: &Type) -> String {
    let scalar = |v: &Value, t: &Type| match (v, t) {
        (Value::Int(v), Type::Boolean) => (*v != 0).to_string(),
        (Value::Long(v), _) => v.to_string(),
        (Value::Int(v), _) => v.to_string(),
        _ => "?".into(),
    };
    match (a, t) {
        (Argument::Scalar(v), t) => scalar(v, t),
        (Argument::String(units), _) => crate::witness::string_literal(units),
        (Argument::Array(items), Type::Array(element)) => format!("{{{}}}", items.iter().map(|v| scalar(v, element)).collect::<Vec<_>>().join(", ")),
        (Argument::Same(i), _) => format!("the same as input {i}"),
        _ => "?".into(),
    }
}

/// One build's log decoded; `strings` are the (call, path) pairs whose snapshot is a string, held as the index of
/// its literal.
fn decode(log: &[i64], model: &Model, strings: &BTreeSet<(usize, usize)>) -> Trace {
    let word = |i: usize| log.get(i).copied().unwrap_or(0);
    let kind = word(0);
    let result = word(1);
    let outcome = match kind {
        0 => format!("returns {result}"),
        k if (k as usize) <= model.exceptions.len() => format!("throws {}", model.exceptions[k as usize - 1].replace('/', ".")),
        _ => "throws another throwable".to_string(),
    };
    let width = model.width();
    let mut attempts = Vec::new();
    for n in 0..word(2).max(0) as usize {
        let at = HEADER + n * width;
        let head = word(at);
        let call = ((head & 0xff) - 1).max(0) as usize;
        let nulls = head >> 8;
        let paths = model.observed.get(call).cloned().flatten().unwrap_or_default();
        let values: Vec<i64> = (0..paths.len()).map(|j| word(at + 1 + j)).collect();
        let shown = paths
            .iter()
            .zip(&values)
            .enumerate()
            .map(|(j, (p, v))| {
                let value = if nulls & (1 << j) != 0 {
                    // A path the payload's class lacks is absent; a payload that is null is null throughout.
                    let class_path = p.split_once('.').map(|(a, _)| format!("{a}.class"));
                    let class_null = class_path.as_ref().and_then(|c| paths.iter().position(|q| q == c)).map(|k| nulls & (1 << k) != 0);
                    if !p.ends_with(".class") && class_null == Some(false) { "absent".to_string() } else { "null".to_string() }
                } else if p.ends_with(".class") {
                    model.classes.get((*v as usize).wrapping_sub(1)).map(|c| c.replace('/', ".")).unwrap_or_else(|| v.to_string())
                } else if !strings.contains(&(call, j)) {
                    v.to_string()
                } else if model.content {
                    let units: Vec<u16> = (0..(*v).clamp(0, model.string_bound as i64) as usize).map(|u| word(at + model.block(j) + u) as u16).collect();
                    crate::witness::string_literal(&units)
                } else {
                    model.literals.get((*v as usize).wrapping_sub(1)).map(|s| format!("{s:?}")).unwrap_or_else(|| v.to_string())
                };
                format!("{p}={value}")
            })
            .collect::<Vec<_>>()
            .join(", ");
        let mut key = vec![nulls];
        key.extend(&values);
        if model.content {
            key.extend((model.block(0)..width).map(|k| word(at + k)));
        }
        attempts.push((call, key, format!("{}({shown})", short(&model.calls[call]))));
    }
    let mark = word(3) & MARK_BITS;
    let mut unresolved = Vec::new();
    if mark & PAST_BOUND != 0 {
        unresolved.push(format!("more attempts than the trace bound, {}", model.bound));
    }
    if mark & UNSNAPSHOTTED != 0 {
        if model.content {
            unresolved.push(format!("a payload value no snapshot holds (a string of more than {} code units, or an object of another class than the call site's)", model.string_bound));
        } else {
            unresolved.push("a payload value no snapshot holds (a string that is no literal of either build, or an object of another class than the call site's)".into());
        }
    }
    if mark & UNMADE != 0 {
        unresolved.push("the handler's constructor threw on the null dependencies".into());
    }
    if mark & KEY_PAST_BOUND != 0 {
        unresolved.push(format!("a modelled call keyed by a string of more than {} code units, which the environment's table holds no key of", model.string_bound));
    }
    if mark & UNMODELED != 0 {
        unresolved.push("a call on a dependency that the environment model doesn't model".into());
    }
    if mark & NULL_THROWN != 0 {
        unresolved.push("a NullPointerException, which a dependency left null may have caused (a call on it through a supertype, Object.hashCode say)".into());
    }
    if mark & UNMADE_RESPONSE != 0 {
        unresolved.push("a response its constructor wouldn't make from the environment's leaves, which no dependency gives".into());
    }
    if mark & PAST_MODEL_BOUND != 0 {
        let models: Vec<String> = model.models.iter().flatten().map(|m| format!("{} than its bound, {}", m.id, m.bound)).collect();
        unresolved.push(format!("more calls of {}", models.join(", or of ")));
    }
    Trace { outcome, kind, result, attempts, unresolved }
}

fn class_path(dir: &Path) -> Result<(ClassPath, Vec<String>), Unsupported> {
    let fail = |e: crate::Error| unsupported(format!("reading the classes under {}: {e}", dir.display()));
    let mut cp = ClassPath::new();
    cp.add(dir).map_err(fail)?;
    let local = cp.application_class_names().map_err(fail)?;
    Ok((cp.with_default_jdk(), local))
}

/// Every class file under `dir`, with its path relative to it.
fn class_files(dir: &Path) -> std::io::Result<Vec<(PathBuf, Vec<u8>)>> {
    let mut out = Vec::new();
    let mut dirs = vec![dir.to_path_buf()];
    while let Some(d) = dirs.pop() {
        for entry in std::fs::read_dir(&d)? {
            let path = entry?.path();
            if path.is_dir() {
                dirs.push(path);
            } else if path.extension().is_some_and(|e| e == "class") {
                let bytes = std::fs::read(&path)?;
                out.push((path.strip_prefix(dir).unwrap_or(&path).to_path_buf(), bytes));
            }
        }
    }
    out.sort();
    Ok(out)
}

/// A build made ready for the check: its classes with the stubs in place, and the generated method's name.
struct Prepared {
    /// `pkg.JvmcontractEffects#observe`.
    target: String,
    /// The generated class's internal name.
    entry: String,
    descriptor: String,
    params: Vec<Type>,
    /// The (call, path) pairs whose snapshot is a string.
    strings: BTreeSet<(usize, usize)>,
}

/// How a stub reads one payload path.
#[derive(Debug, Clone)]
struct Read {
    /// The call's parameter it starts from.
    param: usize,
    /// For each class the call sites pass that has the path, each step into an object: the class it must be, and
    /// how its property is read. Empty for a primitive parameter or a `.class` path.
    chains: Vec<Vec<(String, Access)>>,
    leaf: Leaf,
    /// Whether the call sites pass several classes, so that an argument of none of the chains' classes has no such
    /// path (snapshotted as absent) rather than being one the stub can't read.
    several: bool,
}

#[derive(Debug, Clone)]
enum Access {
    Method { name: String, descriptor: String },
    Field { name: String, descriptor: String },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Leaf {
    Int,
    Long,
    Str,
    /// The argument's class, as its index in [`Model::classes`] plus one.
    Class,
}

fn package_of(internal: &str) -> &str {
    internal.rsplit_once('/').map(|(p, _)| p).unwrap_or("")
}

fn in_package(package: &str, simple: &str) -> String {
    if package.is_empty() { simple.to_string() } else { format!("{package}/{simple}") }
}

/// Writes `spec`'s build into `out` with the stubs in place, and the generated method that runs the handler and
/// returns its log; `tag` tells the builds' unresolved marks apart. Under a plan (`planned`, its roots in the
/// method's order, `this` first for an instance method), the method's receiver and parameters are made by it
/// ([`crate::construction::flat_roots`]), and the entry's inputs are its flat inputs.
#[allow(clippy::too_many_arguments)] // the parts of one build's preparation
fn prepare(spec: &EntryPointSpec, cp: &ClassPath, local: &[String], build: &Path, out: &Path, model: &Model, tag: i64, planned: Option<&[crate::construction::Flat]>) -> Result<Prepared, Unsupported> {
    let (class_dotted, method_name) = spec.handler.split_once('#').ok_or_else(|| unsupported(format!("a handler that isn't Class#method: {}", spec.handler)))?;
    let class_name = class_dotted.replace('.', "/");
    let class = cp.application(&class_name).ok().flatten().ok_or_else(|| unsupported(format!("no class {class_dotted} under {}", build.display())))?;
    let candidates: Vec<_> = class.methods.iter().filter(|m| m.name == method_name && !m.is_synthetic() && !m.is_bridge()).collect();
    let [method] = candidates.as_slice() else { return Err(unsupported(format!("{} names {} methods", spec.handler, candidates.len()))) };
    if let Some(roots) = planned {
        return prepare_planned(spec, cp, local, build, out, model, tag, roots, &class_name, method);
    }
    if method.is_static() {
        return Err(unsupported(format!("{} is static: a handler is an instance method", spec.handler)));
    }
    let descriptor = method.parsed_descriptor().map_err(|e| unsupported(e.to_string()))?;
    if descriptor.params.len() != spec.inputs.len() {
        return Err(unsupported(format!("{} takes {} parameters, of which {} are external inputs: a parameter the framework supplies isn't modeled", spec.handler, descriptor.params.len(), spec.inputs.len())));
    }
    if let Some(t) = descriptor.params.iter().find(|t| !t.is_primitive() || matches!(t, Type::Float | Type::Double)) {
        return Err(unsupported(format!("an input of type {}: the effect trace takes integral inputs (object inputs wait for the heap stream)", t.java_name())));
    }
    if !(descriptor.ret.is_primitive() || descriptor.ret == Type::Void) || matches!(descriptor.ret, Type::Float | Type::Double) {
        return Err(unsupported(format!("a response of type {}: the effect trace compares an integral response", descriptor.ret.java_name())));
    }
    let constructors: Vec<_> = class.methods.iter().filter(|m| m.is_constructor() && !m.is_synthetic()).collect();
    let [constructor] = constructors.as_slice() else { return Err(unsupported(format!("{class_dotted} has {} constructors: the handler is made by its one constructor", constructors.len()))) };
    let ctor = constructor.parsed_descriptor().map_err(|e| unsupported(e.to_string()))?;
    // The dependencies, null in both builds: the constructor's object parameters, and the fields the framework
    // injects. An application class among them would be null too, and is refused: making it needs its own
    // constructor. Of a framework type or an application interface (a repository), only modeled calls are stubs; any
    // other call on one marks the log unresolved where it is reached.
    let injected = |f: &crate::classfile::Field| f.annotations(&class.pool).unwrap_or_default().iter().any(|a| matches!(a.type_name.trim_end_matches(';').rsplit(['.', '/']).next(), Some("Autowired" | "Inject" | "Resource")));
    let mut dependencies = BTreeSet::new();
    let field_types = class.fields.iter().filter(|f| !f.is_static()).filter_map(|f| Type::parse(&f.descriptor).ok().and_then(|t| t.class_name().map(|c| (c.to_string(), injected(f)))));
    for (c, must_be_made) in ctor.params.iter().filter_map(|t| t.class_name().map(|c| (c.to_string(), true))).chain(field_types) {
        if c.starts_with("java/") {
            continue;
        }
        let interface = cp.application(&c).ok().flatten().map(|cf| cf.is_interface());
        match interface {
            Some(false) if must_be_made => return Err(unsupported(format!("{class_dotted} is given an application {} it would get null: a handler whose application dependencies must be made comes after the narrow case", c.replace('/', ".")))),
            Some(false) => {}
            _ => {
                dependencies.insert(c);
            }
        }
    }
    rewrite(spec, cp, local, build, out, model, tag, dependencies, &class_name, method_name, method, &descriptor, Some((constructor, &ctor)), None)
}

/// [`prepare`] under a plan: the method's receiver and parameters are its roots, each made by its constructor.
#[allow(clippy::too_many_arguments)] // the parts of one build's preparation
fn prepare_planned(spec: &EntryPointSpec, cp: &ClassPath, local: &[String], build: &Path, out: &Path, model: &Model, tag: i64, roots: &[crate::construction::Flat], class_name: &str, method: &crate::classfile::Method) -> Result<Prepared, Unsupported> {
    let descriptor = method.parsed_descriptor().map_err(|e| unsupported(e.to_string()))?;
    let instance = !method.is_static();
    let receiver = roots.first().filter(|r| r.root == "this");
    if instance != receiver.is_some() || receiver.is_some_and(|r| r.class != class_name) {
        return Err(unsupported(format!("{}: the plan's receiver this is a root of an instance method, of its class", spec.handler)));
    }
    let parameters: Vec<Type> = roots.iter().skip(usize::from(instance)).map(|r| Type::Object(r.class.clone())).collect();
    if parameters != descriptor.params {
        return Err(unsupported(format!("{} takes ({}), and the plan's roots make ({})", spec.handler, descriptor.params.iter().map(Type::java_name).collect::<Vec<_>>().join(", "), parameters.iter().map(Type::java_name).collect::<Vec<_>>().join(", "))));
    }
    if !(descriptor.ret.is_primitive() || descriptor.ret == Type::Void) || matches!(descriptor.ret, Type::Float | Type::Double) {
        return Err(unsupported(format!("a result of type {}: the effect trace compares an integral result", descriptor.ret.java_name())));
    }
    let dependencies: BTreeSet<String> = roots.iter().flat_map(|r| &r.args).filter_map(|a| match a {
        crate::construction::FlatArg::Dependency { class } => Some(class.clone()),
        _ => None,
    }).collect();
    rewrite(spec, cp, local, build, out, model, tag, dependencies, class_name, &method.name, method, &descriptor, None, Some((roots, instance)))
}

/// The rest of [`prepare`]: the build rewritten with its stubs, and the entry method.
#[allow(clippy::too_many_arguments)] // the parts of one build's preparation
fn rewrite(spec: &EntryPointSpec, cp: &ClassPath, local: &[String], build: &Path, out: &Path, model: &Model, tag: i64, mut dependencies: BTreeSet<String>, class_name: &str, method_name: &str, method: &crate::classfile::Method, descriptor: &MethodDescriptor, handler: Option<(&crate::classfile::Method, &MethodDescriptor)>, planned: Option<(&[crate::construction::Flat], bool)>) -> Result<Prepared, Unsupported> {
    for call in &model.calls {
        if let Some((owner, _, _)) = split_call(call) {
            dependencies.insert(owner);
        }
    }
    let package = package_of(class_name).to_string();
    let entry = in_package(&package, ENTRY);
    let stubs = in_package(&package, STUBS);
    if local.contains(&entry) || local.contains(&stubs) {
        return Err(unsupported(format!("the build has a class {entry} or {stubs} already")));
    }

    // The stubs' reads, from this build's call sites.
    let mut reads: Vec<Option<Vec<Read>>> = Vec::new();
    let mut strings = BTreeSet::new();
    for (i, call) in model.calls.iter().enumerate() {
        let Some(paths) = &model.observed[i] else {
            reads.push(None);
            continue;
        };
        let sites: Vec<_> = spec.effects.iter().filter(|e| &e.call == call).collect();
        if sites.is_empty() {
            reads.push(Some(Vec::new()));
            continue;
        }
        let (_, _, d) = split_call(call).ok_or_else(|| unsupported(format!("a modeled call that isn't owner#name(descriptor): {call}")))?;
        let d = MethodDescriptor::parse(&d).map_err(|e| unsupported(e.to_string()))?;
        let mut rs = Vec::new();
        for (j, path) in paths.iter().enumerate() {
            let read = read_path(cp, &package, &sites, &d, path, &model.classes)?;
            if read.leaf == Leaf::Str {
                strings.insert((i, j));
            }
            rs.push(read);
        }
        if rs.len() > 24 {
            return Err(unsupported(format!("{} snapshots {} paths: a stub holds at most 24", short(call), rs.len())));
        }
        reads.push(Some(rs));
    }

    // The build, with every call site of a modeled call redirected to its stub, and every other call on a
    // dependency to one that marks the log.
    let mut unmodeled: Vec<(Invoke, MemberRef)> = Vec::new();
    for (rel, bytes) in class_files(build).map_err(|e| unsupported(format!("reading {}: {e}", build.display())))? {
        let parsed = ClassFile::parse(&bytes).map_err(|e| unsupported(format!("{}: {e}", rel.display())))?;
        for m in &parsed.methods {
            let Some(code) = &m.code else { continue };
            let insns = code.instructions().map_err(|e| unsupported(e.to_string()))?;
            for (k, (_, insn)) in insns.iter().enumerate() {
                let index = match insn {
                    Insn::InvokeVirtual(i) | Insn::InvokeInterface(i) | Insn::InvokeStatic(i) | Insn::InvokeSpecial(i) => *i,
                    _ => continue,
                };
                let Ok(member) = parsed.pool.member(index) else { continue };
                let call = format!("{}#{}{}", member.owner, member.name, member.descriptor);
                if let Some(i) = model.calls.iter().position(|c| *c == call) {
                    let ret = MethodDescriptor::parse(&member.descriptor).map(|d| d.ret).unwrap_or(Type::Void);
                    let dropped = matches!(insns.get(k + 1), Some((_, Insn::Pop | Insn::Pop2)));
                    // A modelled result may be used: the stub answers from the environment model.
                    if ret != Type::Void && !dropped && model.models[i].is_none() {
                        return Err(unsupported(format!("{}.{} uses the result of {}: a modeled return value comes after the narrow case", parsed.name.replace('/', "."), m.name, short(&call))));
                    }
                } else if dependencies.contains(&member.owner) && !matches!(insn, Insn::InvokeSpecial(_)) {
                    let invoke = if matches!(insn, Insn::InvokeStatic(_)) { Invoke::Static } else { Invoke::Virtual };
                    if !unmodeled.iter().any(|(i, m)| *i == invoke && *m == member) {
                        unmodeled.push((invoke, member));
                    }
                }
            }
        }
        let lookup = |invoke: Invoke, m: &MemberRef| -> Option<MemberRef> {
            let call = format!("{}#{}{}", m.owner, m.name, m.descriptor);
            let descriptor = match invoke {
                Invoke::Static => m.descriptor.clone(),
                Invoke::Virtual | Invoke::Interface => format!("(Ljava/lang/Object;{}", &m.descriptor[1..]),
                Invoke::Special => return None,
            };
            if let Some(i) = model.calls.iter().position(|c| *c == call) {
                return Some(MemberRef::new(&stubs, &format!("e{i}"), &descriptor));
            }
            let kind = if invoke == Invoke::Static { Invoke::Static } else { Invoke::Virtual };
            let k = unmodeled.iter().position(|(i, u)| *i == kind && u == m)?;
            Some(MemberRef::new(&stubs, &format!("u{k}"), &descriptor))
        };
        let patched = crate::shared::redirect_calls(&bytes, &lookup).map_err(|e| unsupported(format!("{}: {e}", rel.display())))?;
        let target = out.join(&rel);
        if let Some(parent) = target.parent() {
            std::fs::create_dir_all(parent).map_err(|e| unsupported(e.to_string()))?;
        }
        std::fs::write(&target, patched.unwrap_or(bytes)).map_err(|e| unsupported(e.to_string()))?;
    }

    let package_dir = if package.is_empty() { out.to_path_buf() } else { out.join(&package) };
    std::fs::create_dir_all(&package_dir).map_err(|e| unsupported(e.to_string()))?;
    std::fs::write(out.join(format!("{stubs}.class")), stubs_class(&stubs, model, &reads, &unmodeled)).map_err(|e| unsupported(e.to_string()))?;
    let present: Vec<bool> = model.exceptions.iter().map(|e| if e.starts_with("java/") { true } else { local.contains(e) }).collect();
    // The entry method's parameters: the handler's inputs, then the environment model's tables.
    let mut params: Vec<Type> = match planned {
        Some((roots, _)) => roots.iter().flat_map(|r| r.inputs().map(|(_, t)| t.clone())).collect(),
        None => descriptor.params.clone(),
    };
    params.extend(model.environment_inputs());
    let entry_descriptor = format!("({})[J", params.iter().map(Type::descriptor).collect::<String>());
    let no_constructor = MethodDescriptor { params: Vec::new(), ret: Type::Void };
    let (ctor_descriptor, ctor) = match handler {
        Some((constructor, ctor)) => (constructor.descriptor.as_str(), ctor),
        None => ("()V", &no_constructor),
    };
    std::fs::write(out.join(format!("{entry}.class")), entry_class(&entry, &stubs, class_name, method_name, &method.descriptor, descriptor, ctor_descriptor, ctor, model, &present, tag, planned)).map_err(|e| unsupported(e.to_string()))?;
    Ok(Prepared { target: format!("{}#{METHOD}", entry.replace('/', ".")), entry, descriptor: entry_descriptor, params, strings })
}

/// How a stub of `call` (descriptor `d`) reads `path` at the call sites `sites`; `known` are the payload classes a
/// `.class` path names.
fn read_path(cp: &ClassPath, package: &str, sites: &[&crate::spec::observe::EffectSite], d: &MethodDescriptor, path: &str, known: &[String]) -> Result<Read, Unsupported> {
    let segments: Vec<&str> = path.split('.').collect();
    let names = &sites[0].arguments;
    let param = names.iter().position(|a| a.name == segments[0]).ok_or_else(|| unsupported(format!("the payload path {path} starts at no parameter of the call")))?;
    let declared = d.params.get(param).cloned().ok_or_else(|| unsupported(format!("the payload path {path}: no parameter {param}")))?;
    let classes: BTreeSet<Option<String>> = sites.iter().map(|s| s.arguments.get(param).and_then(|a| a.class.clone())).collect();
    if classes.contains(&None) && segments.len() > 1 {
        return Err(unsupported(format!("the payload path {path}: the walk can't tell the class of the argument passed")));
    }
    let several = classes.len() > 1;
    // `class` is no Java identifier, so no record component or getter is named so.
    if segments.len() == 2 && segments[1] == "class" {
        if known.is_empty() {
            return Err(unsupported(format!("the payload path {path}: no class to tell apart")));
        }
        return Ok(Read { param, chains: Vec::new(), leaf: Leaf::Class, several });
    }
    let mut chains = Vec::new();
    let mut ty = declared.clone();
    if segments.len() > 1 {
        let mut leaf_type: Option<Type> = None;
        for start in classes.iter().flatten() {
            let mut current = start.clone();
            let mut hops = Vec::new();
            let mut reached = None;
            for (k, field) in segments[1..].iter().enumerate() {
                let Some((access, t)) = property(cp, package, &current, field) else {
                    if several && k == 0 {
                        break; // this class has no such path: absent, when the payload is one of it
                    }
                    return Err(unsupported(format!("the payload path {path}: {} has no property {field} a stub in {} can read (a record component, a public getter or a public field)", current.replace('/', "."), package.replace('/', "."))));
                };
                hops.push((current.clone(), access));
                if k + 2 < segments.len() {
                    current = t.class_name().map(str::to_string).ok_or_else(|| unsupported(format!("the payload path {path} steps into a {}", t.java_name())))?;
                }
                reached = Some(t);
            }
            let Some(t) = reached.filter(|_| hops.len() == segments.len() - 1) else { continue };
            if leaf_type.as_ref().is_some_and(|l| *l != t) {
                return Err(unsupported(format!("the payload path {path} is a {} in one class passed and a {} in another", leaf_type.unwrap().java_name(), t.java_name())));
            }
            leaf_type = Some(t);
            chains.push(hops);
        }
        ty = leaf_type.ok_or_else(|| unsupported(format!("the payload path {path}: no class the call sites pass has it")))?;
    }
    let leaf = match &ty {
        Type::Long => Leaf::Long,
        Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int => Leaf::Int,
        Type::Object(c) if c == "java/lang/String" => Leaf::Str,
        other => return Err(unsupported(format!("the payload path {path} is a {}: a stub snapshots integral values and literal strings", other.java_name()))),
    };
    Ok(Read { param, chains, leaf, several })
}

/// How a stub in `package` reads `field` of `class`: a record's accessor, a public getter, or a public field.
fn property(cp: &ClassPath, package: &str, class: &str, field: &str) -> Option<(Access, Type)> {
    let mut owner = class.to_string();
    loop {
        let c = cp.application(&owner).ok().flatten()?;
        let visible = c.access & flags::PUBLIC != 0 || package_of(&c.name) == package;
        if let Some(f) = c.fields.iter().find(|f| f.name == field && !f.is_static()) {
            if !visible {
                return None;
            }
            let t = Type::parse(&f.descriptor).ok()?;
            let accessor = format!("(){}", f.descriptor);
            let cap = format!("{}{}", field[..1].to_uppercase(), &field[1..]);
            let names = if c.is_record() { vec![field.to_string()] } else { vec![format!("get{cap}"), format!("is{cap}"), field.to_string()] };
            for n in names {
                if let Some(m) = c.method(&n, &accessor) {
                    if !m.is_static() && (m.is_public() || (package_of(&c.name) == package && !m.is_private())) {
                        return Some((Access::Method { name: n, descriptor: accessor }, t));
                    }
                }
            }
            if f.access & flags::PUBLIC != 0 || (package_of(&c.name) == package && f.access & flags::PRIVATE == 0) {
                return Some((Access::Field { name: field.to_string(), descriptor: f.descriptor.clone() }, t));
            }
            return None;
        }
        owner = c.super_class.clone()?;
    }
}

/// The stubs: the log (`LOG`, `N` attempts, `U` the unresolved mark), and `e{i}` for each modeled call.
fn stubs_class(name: &str, model: &Model, reads: &[Option<Vec<Read>>], unmodeled: &[(Invoke, MemberRef)]) -> Vec<u8> {
    let mut w = ClassWriter::new(name);
    w.access = flags::PUBLIC | flags::FINAL | flags::SUPER;
    for (f, d) in [("LOG", "[J"), ("N", "I"), ("U", "I")] {
        w.fields.push(FieldWriter { access: flags::PUBLIC | flags::STATIC, name: f.into(), descriptor: d.into() });
    }
    for (i, m) in model.models.iter().enumerate() {
        let Some(m) = m else { continue };
        w.fields.push(FieldWriter { access: flags::PUBLIC | flags::STATIC, name: format!("c{i}"), descriptor: "I".into() });
        for (f, t) in table_fields(i, m).into_iter().chain(kept_fields(i, m)) {
            w.fields.push(FieldWriter { access: flags::PUBLIC | flags::STATIC, name: f, descriptor: t.descriptor() });
        }
        for f in used_fields(i, m) {
            w.fields.push(FieldWriter { access: flags::PUBLIC | flags::STATIC, name: f, descriptor: "I".into() });
        }
    }
    let width = model.width() as i32;
    for (i, call) in model.calls.iter().enumerate() {
        let Some((_, _, d)) = split_call(call) else { continue };
        let Ok(descriptor) = MethodDescriptor::parse(&d) else { continue };
        // Every stub takes the receiver first; a static call's stub is only reached for a static call, whose
        // descriptor it keeps, so both forms are written.
        for receiver in [true, false] {
            let mut code = CodeBuilder::new();
            let mut slots = Vec::new();
            let mut slot = if receiver { 1u16 } else { 0 };
            for t in &descriptor.params {
                slots.push(slot);
                slot += if matches!(t, Type::Long | Type::Double) { 2 } else { 1 };
            }
            code.max_locals = slot;
            let (n, log, at, mask, value, tmp, arg, len) = (slot, slot + 1, slot + 2, slot + 3, slot + 4, slot + 6, slot + 7, slot + 8);
            // A DTO response's `new`, `dup` and leaves.
            let response = model.models.get(i).and_then(Option::as_ref).and_then(|m| m.response.as_ref()).map_or(0, |r| 3 + r.leaves.iter().map(|(_, t)| t.slots()).sum::<u16>());
            code.max_stack = 8.max(response);
            let done = code.label();
            if let Some(Some(rs)) = reads.get(i) {
                let n_ref = w.pool.field_ref(name, "N", "I");
                let u_ref = w.pool.field_ref(name, "U", "I");
                let log_ref = w.pool.field_ref(name, "LOG", "[J");
                let room = code.label();
                code.op_u16(0xb2, n_ref);
                code.store(Kind::Int, n);
                code.load(Kind::Int, n);
                code.iconst(model.bound as i32);
                code.if_icmp(Cond::Lt, room);
                code.op_u16(0xb2, u_ref);
                code.iconst(PAST_BOUND as i32);
                code.op(0x80); // ior
                code.op_u16(0xb3, u_ref);
                code.goto(done);
                code.bind(room);
                code.op_u16(0xb2, log_ref);
                code.store(Kind::Ref, log);
                code.load(Kind::Int, n);
                code.iconst(width);
                code.op(0x68); // imul
                code.iconst(HEADER as i32);
                code.op(0x60); // iadd
                code.store(Kind::Int, at);
                code.iconst(0);
                code.store(Kind::Int, mask);
                for (j, r) in rs.iter().enumerate() {
                    let (null, unresolved, store) = (code.label(), code.label(), code.label());
                    let t = &descriptor.params[r.param];
                    code.load(kind_of(t), slots[r.param]);
                    if r.leaf == Leaf::Class {
                        code.store(Kind::Ref, arg);
                        code.load(Kind::Ref, arg);
                        code.if_null(null);
                        for (k, class) in model.classes.iter().enumerate() {
                            let next = code.label();
                            code.load(Kind::Ref, arg);
                            let c = w.pool.class(class);
                            code.op_u16(0xc1, c); // instanceof
                            code.if_zero(Cond::Eq, next);
                            let v = w.pool.long(k as i64 + 1);
                            code.ldc2(v);
                            code.store(Kind::Long, value);
                            code.goto(store);
                            code.bind(next);
                        }
                        code.goto(unresolved);
                    } else if r.chains.is_empty() {
                        snapshot_leaf(&mut code, &mut w, model, r.leaf, (value, tmp), (store, null, unresolved), (log, at, len, j));
                    } else {
                        // The argument is one of the chains' classes, or (with several classes passed) a payload
                        // without this path, or one the stub can't read.
                        code.store(Kind::Ref, arg);
                        code.load(Kind::Ref, arg);
                        code.if_null(null);
                        for chain in &r.chains {
                            let next = code.label();
                            for (h, (class, access)) in chain.iter().enumerate() {
                                let c = w.pool.class(class);
                                if h == 0 {
                                    code.load(Kind::Ref, arg);
                                    code.op_u16(0xc1, c); // instanceof
                                    code.if_zero(Cond::Eq, next);
                                    code.load(Kind::Ref, arg);
                                } else {
                                    code.store(Kind::Ref, tmp);
                                    code.load(Kind::Ref, tmp);
                                    code.if_null(null);
                                    code.load(Kind::Ref, tmp);
                                    code.op_u16(0xc1, c);
                                    code.if_zero(Cond::Eq, unresolved);
                                    code.load(Kind::Ref, tmp);
                                }
                                code.op_u16(0xc0, c); // checkcast
                                match access {
                                    Access::Method { name: m, descriptor: md } => {
                                        let r = w.pool.method_ref(class, m, md);
                                        code.op_u16(0xb6, r);
                                    }
                                    Access::Field { name: f, descriptor: fd } => {
                                        let r = w.pool.field_ref(class, f, fd);
                                        code.op_u16(0xb4, r);
                                    }
                                }
                            }
                            snapshot_leaf(&mut code, &mut w, model, r.leaf, (value, tmp), (store, null, unresolved), (log, at, len, j));
                            code.bind(next);
                        }
                        code.goto(if r.several { null } else { unresolved });
                    }
                    code.bind(null);
                    code.load(Kind::Int, mask);
                    code.iconst(1 << j);
                    code.op(0x80); // ior
                    code.store(Kind::Int, mask);
                    code.op(0x09); // lconst_0
                    code.store(Kind::Long, value);
                    code.goto(store);
                    code.bind(unresolved);
                    code.op_u16(0xb2, u_ref);
                    code.iconst(UNSNAPSHOTTED as i32);
                    code.op(0x80);
                    code.op_u16(0xb3, u_ref);
                    code.op(0x09);
                    code.store(Kind::Long, value);
                    code.bind(store);
                    code.load(Kind::Ref, log);
                    code.load(Kind::Int, at);
                    code.iconst(1 + j as i32);
                    code.op(0x60);
                    code.load(Kind::Long, value);
                    code.op(0x50); // lastore
                }
                // The attempt's first word: the call, and the null bits above it.
                code.load(Kind::Ref, log);
                code.load(Kind::Int, at);
                code.load(Kind::Int, mask);
                code.op(0x85);
                code.iconst(8);
                code.op(0x79); // lshl
                let id = w.pool.long(i as i64 + 1);
                code.ldc2(id);
                code.op(0x81); // lor
                code.op(0x50);
                code.load(Kind::Int, n);
                code.iconst(1);
                code.op(0x60);
                code.op_u16(0xb3, n_ref);
            }
            code.bind(done);
            match model.models.get(i).and_then(Option::as_ref) {
                Some(m) => answer(&mut code, &mut w, name, i, m, &slots, &descriptor.params, model.string_bound),
                None => return_default(&mut code, &descriptor.ret),
            }
            let stub_descriptor = if receiver { format!("(Ljava/lang/Object;{}", &d[1..]) } else { d.clone() };
            w.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: format!("e{i}"), descriptor: stub_descriptor, code: Some(code) });
        }
    }
    // A call on a dependency that the model doesn't have: it marks the log, so no proof covers an input that
    // reaches it.
    let u_ref = w.pool.field_ref(name, "U", "I");
    for (k, (invoke, m)) in unmodeled.iter().enumerate() {
        let Ok(descriptor) = MethodDescriptor::parse(&m.descriptor) else { continue };
        let stub_descriptor = if *invoke == Invoke::Static { m.descriptor.clone() } else { format!("(Ljava/lang/Object;{}", &m.descriptor[1..]) };
        let mut code = CodeBuilder::new();
        code.max_locals = 1 + descriptor.params.iter().map(|t| if matches!(t, Type::Long | Type::Double) { 2 } else { 1 }).sum::<u16>();
        code.max_stack = 4;
        code.op_u16(0xb2, u_ref);
        code.iconst(UNMODELED as i32);
        code.op(0x80);
        code.op_u16(0xb3, u_ref);
        return_default(&mut code, &descriptor.ret);
        w.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: format!("u{k}"), descriptor: stub_descriptor, code: Some(code) });
    }
    w.to_bytes()
}

/// The static fields of the stubs class that hold call `i`'s table, in the order of
/// [`crate::environment::Lowered::inputs`]: each entry's key components (`k{i}_{e}_{c}`), result (`v{i}_{e}`, unless
/// the call returns nothing) and outcome (`o{i}_{e}`, when the model has failures), then the default's (`d{i}`,
/// `od{i}`).
fn table_fields(i: usize, m: &crate::environment::Lowered) -> Vec<(String, Type)> {
    let answer = |out: &mut Vec<(String, Type)>, value: String, outcome: String| {
        if let Some(r) = &m.response {
            out.extend(response_fields(&value, r));
        } else if m.ret != Type::Void {
            out.push((value, m.ret.clone()));
        }
        if !m.throws.is_empty() {
            out.push((outcome, Type::Int));
        }
    };
    let mut out = Vec::new();
    for e in 0..m.entries() {
        for (c, (_, t)) in m.key.iter().enumerate() {
            out.push((format!("k{i}_{e}_{c}"), t.clone()));
        }
        answer(&mut out, format!("v{i}_{e}"), format!("o{i}_{e}"));
    }
    answer(&mut out, format!("d{i}"), format!("od{i}"));
    out
}

/// The fields of a DTO answer named `value` (E3): its null flag (`{value}_n`), when it may be null, then its leaves
/// (`{value}_0`, ...), in the order of [`crate::environment::Lowered::inputs`].
fn response_fields(value: &str, r: &crate::environment::Response) -> Vec<(String, Type)> {
    let mut out = Vec::new();
    if r.nullable {
        out.push((format!("{value}_n"), Type::Int));
    }
    out.extend(r.leaves.iter().enumerate().map(|(c, (_, t))| (format!("{value}_{c}"), t.clone())));
    out
}

/// The static fields of the stubs class that keep the object each of call `i`'s answers made (`v{i}_{e}_r`,
/// `d{i}_r`), under a stable identity: none otherwise. The entry method clears them, so they last one trace.
fn kept_fields(i: usize, m: &crate::environment::Lowered) -> Vec<(String, Type)> {
    let Some(r) = m.response.as_ref().filter(|r| r.stable) else { return Vec::new() };
    (0..m.entries()).map(|e| format!("v{i}_{e}_r")).chain(std::iter::once(format!("d{i}_r"))).map(|f| (f, Type::Object(r.class.clone()))).collect()
}

/// The static fields of the stubs class that mark which of call `i`'s entries this trace used (`w{i}_{e}`), for a
/// per-call choice; none for a query.
fn used_fields(i: usize, m: &crate::environment::Lowered) -> Vec<String> {
    if m.per_call { (0..m.entries()).map(|e| format!("w{i}_{e}")).collect() } else { Vec::new() }
}

/// Answers a modelled call from its table: one more call than the model's bound marks the log past its bound;
/// otherwise the answer of the first entry whose key is the call's (for a per-call choice, the first such entry
/// this trace hasn't used, which it then marks used), or the default. An answer whose outcome is `k` throws a new
/// instance of the model's `k`-th failure, made by its constructor without arguments; any other outcome returns
/// the answer's value. A String key component is compared by its content (`String.equals`, the table's key never
/// null), and one longer than `string_bound` marks the log, since the table holds no such key: keyed as the
/// default, two such keys would be coupled. `slots` are the call's parameters'.
#[allow(clippy::too_many_arguments)] // the parts of one generated stub
fn answer(code: &mut CodeBuilder, w: &mut ClassWriter, stubs: &str, i: usize, m: &crate::environment::Lowered, slots: &[u16], params: &[Type], string_bound: usize) {
    let calls_ref = w.pool.field_ref(stubs, &format!("c{i}"), "I");
    let u_ref = w.pool.field_ref(stubs, "U", "I");
    for (p, t) in &m.key {
        if !crate::values::is_string(t) {
            continue;
        }
        let keyed = code.label();
        code.load(Kind::Ref, slots[*p]);
        code.if_null(keyed);
        code.load(Kind::Ref, slots[*p]);
        let length = w.pool.method_ref("java/lang/String", "length", "()I");
        code.op_u16(0xb6, length);
        code.iconst(string_bound as i32);
        code.if_icmp(Cond::Le, keyed);
        code.op_u16(0xb2, u_ref);
        code.iconst(KEY_PAST_BOUND as i32);
        code.op(0x80); // ior
        code.op_u16(0xb3, u_ref);
        return_default(code, &m.ret);
        code.bind(keyed);
    }
    let within = code.label();
    code.op_u16(0xb2, calls_ref);
    code.iconst(m.bound as i32);
    code.if_icmp(Cond::Lt, within);
    code.op_u16(0xb2, u_ref);
    code.iconst(PAST_MODEL_BOUND as i32);
    code.op(0x80); // ior
    code.op_u16(0xb3, u_ref);
    return_default(code, &m.ret);
    code.bind(within);
    code.op_u16(0xb2, calls_ref);
    code.iconst(1);
    code.op(0x60); // iadd
    code.op_u16(0xb3, calls_ref);
    let ret = (m.ret != Type::Void).then(|| kind_of(&m.ret));
    // The answer `value`/`outcome` names: its failures thrown by outcome, then its value returned.
    let give = |code: &mut CodeBuilder, w: &mut ClassWriter, value: &str, outcome: &str| {
        if !m.throws.is_empty() {
            let o = w.pool.field_ref(stubs, outcome, "I");
            for (k, class) in m.throws.iter().enumerate() {
                let other = code.label();
                code.op_u16(0xb2, o);
                code.iconst(k as i32 + 1);
                code.if_icmp(Cond::Ne, other);
                let c = w.pool.class(class);
                code.op_u16(0xbb, c); // new
                code.op(0x59); // dup
                let init = w.pool.method_ref(class, "<init>", "()V");
                code.op_u16(0xb7, init);
                code.op(0xbf); // athrow
                code.bind(other);
            }
        }
        if let Some(r) = &m.response {
            make_response(code, w, stubs, value, r);
            return;
        }
        if m.ret != Type::Void {
            let v = w.pool.field_ref(stubs, value, &m.ret.descriptor());
            code.op_u16(0xb2, v);
        }
        code.return_(ret);
    };
    for e in 0..m.entries() {
        let next = code.label();
        let used = m.per_call.then(|| w.pool.field_ref(stubs, &format!("w{i}_{e}"), "I"));
        if let Some(used) = used {
            code.op_u16(0xb2, used);
            code.if_zero(Cond::Ne, next);
        }
        for (c, (p, t)) in m.key.iter().enumerate() {
            let k = w.pool.field_ref(stubs, &format!("k{i}_{e}_{c}"), &t.descriptor());
            if crate::values::is_string(t) {
                code.op_u16(0xb2, k);
                code.load(Kind::Ref, slots[*p]);
                let equals = w.pool.method_ref("java/lang/String", "equals", "(Ljava/lang/Object;)Z");
                code.op_u16(0xb6, equals);
                code.if_zero(Cond::Eq, next);
                continue;
            }
            code.load(kind_of(&params[*p]), slots[*p]);
            code.op_u16(0xb2, k);
            if *t == Type::Long {
                code.op(0x94); // lcmp
                code.if_zero(Cond::Ne, next);
            } else {
                code.if_icmp(Cond::Ne, next);
            }
        }
        if let Some(used) = used {
            code.iconst(1);
            code.op_u16(0xb3, used);
        }
        give(code, w, &format!("v{i}_{e}"), &format!("o{i}_{e}"));
        code.bind(next);
    }
    give(code, w, &format!("d{i}"), &format!("od{i}"));
}

/// Returns the DTO answer named `value` (E3): null when its null flag is set, under a stable identity the object
/// this trace already made for it, else a new object of its class made by its constructor from its leaves (kept,
/// under a stable identity). A constructor that throws on the leaves makes no response the dependency gives: the
/// log is marked, and the stub returns null, never the constructor's exception as the dependency's.
fn make_response(code: &mut CodeBuilder, w: &mut ClassWriter, stubs: &str, value: &str, r: &crate::environment::Response) {
    let fields = response_fields(value, r);
    let mut leaves = fields.iter();
    if r.nullable {
        let (flag, _) = leaves.next().expect("a null flag");
        let made = code.label();
        let f = w.pool.field_ref(stubs, flag, "I");
        code.op_u16(0xb2, f);
        code.if_zero(Cond::Eq, made);
        code.op(0x01); // aconst_null
        code.return_(Some(Kind::Ref));
        code.bind(made);
    }
    let class_descriptor = Type::Object(r.class.clone()).descriptor();
    let kept = r.stable.then(|| w.pool.field_ref(stubs, &format!("{value}_r"), &class_descriptor));
    if let Some(kept) = kept {
        let fresh = code.label();
        code.op_u16(0xb2, kept);
        code.op(0x59); // dup
        code.if_null(fresh);
        code.return_(Some(Kind::Ref));
        code.bind(fresh);
        code.op(0x57); // pop
    }
    let (start, end, unmade) = (code.label(), code.label(), code.label());
    code.bind(start);
    let c = w.pool.class(&r.class);
    code.op_u16(0xbb, c); // new
    code.op(0x59); // dup
    for (f, t) in leaves {
        let f = w.pool.field_ref(stubs, f, &t.descriptor());
        code.op_u16(0xb2, f);
    }
    let init = w.pool.method_ref(&r.class, "<init>", &r.descriptor);
    code.op_u16(0xb7, init);
    code.bind(end);
    if let Some(kept) = kept {
        code.op(0x59);
        code.op_u16(0xb3, kept);
    }
    code.return_(Some(Kind::Ref));
    code.bind(unmade);
    code.op(0x57); // pop the exception
    let u_ref = w.pool.field_ref(stubs, "U", "I");
    code.op_u16(0xb2, u_ref);
    code.iconst(UNMADE_RESPONSE as i32);
    code.op(0x80); // ior
    code.op_u16(0xb3, u_ref);
    code.op(0x01);
    code.return_(Some(Kind::Ref));
    code.handler(start, end, unmade, None);
}

/// Takes the leaf value on the stack into `value` (a long) and jumps to `store`: an integral value widened, a string
/// as the index of its literal plus one (null to `null`, another string to `unresolved`). Under the model's
/// `content`, a string is its length, its code units written into path `j`'s block of the attempt at `at` of `log`
/// (`len` a local for its length); one longer than the String bound goes to `unresolved`.
#[allow(clippy::too_many_arguments)] // the parts of one snapshot
fn snapshot_leaf(code: &mut CodeBuilder, w: &mut ClassWriter, model: &Model, leaf: Leaf, (value, tmp): (u16, u16), (store, null, unresolved): (crate::classfile::writer::Label, crate::classfile::writer::Label, crate::classfile::writer::Label), (log, at, len, j): (u16, u16, u16, usize)) {
    match leaf {
        Leaf::Str if model.content => {
            code.store(Kind::Ref, tmp);
            code.load(Kind::Ref, tmp);
            code.if_null(null);
            code.load(Kind::Ref, tmp);
            let length = w.pool.method_ref("java/lang/String", "length", "()I");
            code.op_u16(0xb6, length);
            code.store(Kind::Int, len);
            code.load(Kind::Int, len);
            code.iconst(model.string_bound as i32);
            code.if_icmp(Cond::Gt, unresolved);
            let char_at = w.pool.method_ref("java/lang/String", "charAt", "(I)C");
            for u in 0..model.string_bound {
                let skip = code.label();
                code.load(Kind::Int, len);
                code.iconst(u as i32);
                code.if_icmp(Cond::Le, skip);
                code.load(Kind::Ref, log);
                code.load(Kind::Int, at);
                code.iconst((model.block(j) + u) as i32);
                code.op(0x60); // iadd
                code.load(Kind::Ref, tmp);
                code.iconst(u as i32);
                code.op_u16(0xb6, char_at);
                code.op(0x85); // i2l
                code.op(0x50); // lastore
                code.bind(skip);
            }
            code.load(Kind::Int, len);
            code.op(0x85); // i2l
            code.store(Kind::Long, value);
            code.goto(store);
        }
        Leaf::Int => {
            code.op(0x85); // i2l
            code.store(Kind::Long, value);
            code.goto(store);
        }
        Leaf::Long => {
            code.store(Kind::Long, value);
            code.goto(store);
        }
        Leaf::Str => {
            code.store(Kind::Ref, tmp);
            code.load(Kind::Ref, tmp);
            code.if_null(null);
            for (k, lit) in model.literals.iter().enumerate() {
                let next = code.label();
                code.load(Kind::Ref, tmp);
                let s = w.pool.string(lit);
                code.ldc(s);
                code.if_acmpne(next);
                let v = w.pool.long(k as i64 + 1);
                code.ldc2(v);
                code.store(Kind::Long, value);
                code.goto(store);
                code.bind(next);
            }
            code.goto(unresolved);
        }
        Leaf::Class => unreachable!("a class is snapshotted by its own instanceof chain"),
    }
}

/// Returns the default of `ret`: nothing, zero, or null.
fn return_default(code: &mut CodeBuilder, ret: &Type) {
    match ret {
        Type::Void => code.return_(None),
        Type::Long => {
            code.op(0x09); // lconst_0
            code.return_(Some(Kind::Long));
        }
        Type::Float => {
            code.op(0x0b); // fconst_0
            code.return_(Some(Kind::Float));
        }
        Type::Double => {
            code.op(0x0e); // dconst_0
            code.return_(Some(Kind::Double));
        }
        t if t.is_primitive() => {
            code.iconst(0);
            code.return_(Some(Kind::Int));
        }
        _ => {
            code.op(0x01); // aconst_null
            code.return_(Some(Kind::Ref));
        }
    }
}

fn kind_of(t: &Type) -> Kind {
    match t {
        Type::Long => Kind::Long,
        Type::Float => Kind::Float,
        Type::Double => Kind::Double,
        t if t.is_primitive() => Kind::Int,
        _ => Kind::Ref,
    }
}

/// The generated `observe`: makes the handler, calls it on the inputs, and returns the log, cut to what it holds.
/// Under a plan (`planned`), its inputs are the plan's flat inputs, and it makes each root by its constructor from
/// them, a dependency null, inside the call's handler, so that a constructor's exception is the outcome as the
/// call's is: an input only one build's constructors accept is a difference.
#[allow(clippy::too_many_arguments)] // the parts of one generated method
fn entry_class(name: &str, stubs: &str, handler: &str, method: &str, method_descriptor: &str, descriptor: &MethodDescriptor, ctor_descriptor: &str, ctor: &MethodDescriptor, model: &Model, present: &[bool], tag: i64, planned: Option<(&[crate::construction::Flat], bool)>) -> Vec<u8> {
    let mut w = ClassWriter::new(name);
    w.access = flags::PUBLIC | flags::FINAL | flags::SUPER;
    let mut code = CodeBuilder::new();
    let mut slot = 0u16;
    let mut slots = Vec::new();
    let environment = model.environment_inputs();
    let inputs: Vec<Type> = match planned {
        Some((roots, _)) => roots.iter().flat_map(|r| r.inputs().map(|(_, t)| t.clone())).collect(),
        None => descriptor.params.clone(),
    };
    for t in inputs.iter().chain(&environment) {
        slots.push(slot);
        slot += if matches!(t, Type::Long | Type::Double) { 2 } else { 1 };
    }
    code.max_locals = slot;
    let made_stack = planned.map_or(0, |(roots, _)| roots.iter().map(|r| 2 + r.args.iter().map(|a| match a { crate::construction::FlatArg::Input { ty, .. } => ty.slots(), _ => 1 }).sum::<u16>()).max().unwrap_or(0));
    code.max_stack = 12.max(made_stack + 2);
    let (log, h, thrown, result, cut) = (slot, slot + 1, slot + 2, slot + 3, slot + 5);
    // Under a plan, each root's object, in order.
    let objects = slot + 6;
    let width = model.width();
    let capacity = HEADER + model.bound * width;
    let log_ref = w.pool.field_ref(stubs, "LOG", "[J");
    let n_ref = w.pool.field_ref(stubs, "N", "I");
    let u_ref = w.pool.field_ref(stubs, "U", "I");
    code.iconst(capacity as i32);
    code.op_u8(0xbc, 11); // newarray long
    code.store(Kind::Ref, log);
    code.load(Kind::Ref, log);
    code.op_u16(0xb3, log_ref);
    code.iconst(0);
    code.op_u16(0xb3, n_ref);
    code.iconst(0);
    code.op_u16(0xb3, u_ref);
    // The environment model's tables, from the inputs after the handler's, and each model's count of calls.
    let mut at = inputs.len();
    for (i, m) in model.models.iter().enumerate() {
        let Some(m) = m else { continue };
        let calls_ref = w.pool.field_ref(stubs, &format!("c{i}"), "I");
        code.iconst(0);
        code.op_u16(0xb3, calls_ref);
        for (name, t) in table_fields(i, m) {
            let f = w.pool.field_ref(stubs, &name, &t.descriptor());
            code.load(kind_of(&t), slots[at]);
            code.op_u16(0xb3, f);
            at += 1;
        }
        for name in used_fields(i, m) {
            let f = w.pool.field_ref(stubs, &name, "I");
            code.iconst(0);
            code.op_u16(0xb3, f);
        }
        for (name, t) in kept_fields(i, m) {
            let f = w.pool.field_ref(stubs, &name, &t.descriptor());
            code.op(0x01); // aconst_null
            code.op_u16(0xb3, f);
        }
    }
    let set = |code: &mut CodeBuilder, w: &mut ClassWriter, index: i32, value: i64| {
        code.load(Kind::Ref, log);
        code.iconst(index);
        let v = w.pool.long(value);
        code.ldc2(v);
        code.op(0x50);
    };

    let (make_start, make_end, unmade, call_start, call_end, threw, finish) = (code.label(), code.label(), code.label(), code.label(), code.label(), code.label(), code.label());
    if let Some((roots, instance)) = planned {
        // The plan's roots, each made by its constructor from the flat inputs, then the call: one region, whose
        // exceptions are the outcome.
        code.bind(call_start);
        let mut input = 0;
        for (k, r) in roots.iter().enumerate() {
            let class = w.pool.class(&r.class);
            code.op_u16(0xbb, class); // new
            code.op(0x59); // dup
            for a in &r.args {
                match a {
                    crate::construction::FlatArg::Input { ty, .. } => {
                        code.load(kind_of(ty), slots[input]);
                        input += 1;
                    }
                    crate::construction::FlatArg::Dependency { .. } => code.op(0x01), // aconst_null
                }
            }
            let init = w.pool.method_ref(&r.class, "<init>", &r.descriptor);
            code.op_u16(0xb7, init);
            code.store(Kind::Ref, objects + k as u16);
        }
        for k in 0..roots.len() {
            code.load(Kind::Ref, objects + k as u16);
        }
        if instance {
            let m = w.pool.method_ref(handler, method, method_descriptor);
            code.op_u16(0xb6, m);
        } else {
            let m = w.pool.method_ref(handler, method, method_descriptor);
            code.op_u16(0xb8, m);
        }
    } else {
    // The handler, made by its constructor with null dependencies.
    code.bind(make_start);
    let class = w.pool.class(handler);
    code.op_u16(0xbb, class); // new
    code.op(0x59); // dup
    for t in &ctor.params {
        match t {
            Type::Long => code.op(0x09),
            Type::Float => code.op(0x0b),
            Type::Double => code.op(0x0e),
            t if t.is_primitive() => code.iconst(0),
            _ => code.op(0x01),
        }
    }
    let init = w.pool.method_ref(handler, "<init>", ctor_descriptor);
    code.op_u16(0xb7, init);
    code.store(Kind::Ref, h);
    code.bind(make_end);
    code.goto(call_start);
    code.bind(unmade);
    code.op(0x57); // pop
    set(&mut code, &mut w, 3, tag * TAG + UNMADE);
    code.load(Kind::Ref, log);
    code.return_(Some(Kind::Ref));
    code.handler(make_start, make_end, unmade, None);

    // The call, its response or the class of what it threw.
    code.bind(call_start);
    code.load(Kind::Ref, h);
    for (t, s) in descriptor.params.iter().zip(&slots) {
        code.load(kind_of(t), *s);
    }
    let m = w.pool.method_ref(handler, method, method_descriptor);
    code.op_u16(0xb6, m);
    }
    match &descriptor.ret {
        Type::Void => code.op(0x09),
        Type::Long => {}
        _ => code.op(0x85),
    }
    code.store(Kind::Long, result);
    code.load(Kind::Ref, log);
    code.iconst(1);
    code.load(Kind::Long, result);
    code.op(0x50);
    code.bind(call_end);
    code.goto(finish);
    code.bind(threw);
    code.store(Kind::Ref, thrown);
    // A NullPointerException may come from a dependency left null, called through a supertype the stubs can't
    // tell from any other call: it marks the log.
    let npe_done = code.label();
    code.load(Kind::Ref, thrown);
    let npe = w.pool.class("java/lang/NullPointerException");
    code.op_u16(0xc1, npe);
    code.if_zero(Cond::Eq, npe_done);
    code.op_u16(0xb2, u_ref);
    code.iconst(NULL_THROWN as i32);
    code.op(0x80);
    code.op_u16(0xb3, u_ref);
    code.bind(npe_done);
    for (k, e) in model.exceptions.iter().enumerate() {
        if !present[k] {
            continue;
        }
        let next = code.label();
        code.load(Kind::Ref, thrown);
        let c = w.pool.class(e);
        code.op_u16(0xc1, c);
        code.if_zero(Cond::Eq, next);
        set(&mut code, &mut w, 0, k as i64 + 1);
        code.goto(finish);
        code.bind(next);
    }
    set(&mut code, &mut w, 0, model.exceptions.len() as i64 + 1);
    code.handler(call_start, call_end, threw, None);

    // The attempts and the unresolved mark, then the log cut to the attempts recorded.
    code.bind(finish);
    code.load(Kind::Ref, log);
    code.iconst(2);
    code.op_u16(0xb2, n_ref);
    code.op(0x85);
    code.op(0x50);
    let marked = code.label();
    code.op_u16(0xb2, u_ref);
    code.if_zero(Cond::Eq, marked);
    code.load(Kind::Ref, log);
    code.iconst(3);
    code.op_u16(0xb2, u_ref);
    code.op(0x85);
    let t = w.pool.long(tag * TAG);
    code.ldc2(t);
    code.op(0x61); // ladd
    code.op(0x50);
    code.bind(marked);
    for n in 0..=model.bound {
        let next = code.label();
        code.op_u16(0xb2, n_ref);
        code.iconst(n as i32);
        code.if_icmp(Cond::Ne, next);
        let len = HEADER + n * width;
        code.iconst(len as i32);
        code.op_u8(0xbc, 11);
        code.store(Kind::Ref, cut);
        for i in 0..len {
            code.load(Kind::Ref, cut);
            code.iconst(i as i32);
            code.load(Kind::Ref, log);
            code.iconst(i as i32);
            code.op(0x2f); // laload
            code.op(0x50);
        }
        code.load(Kind::Ref, cut);
        code.return_(Some(Kind::Ref));
        code.bind(next);
    }
    code.load(Kind::Ref, log);
    code.return_(Some(Kind::Ref));
    let entry_descriptor = format!("({})[J", inputs.iter().chain(&environment).map(Type::descriptor).collect::<String>());
    w.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: METHOD.into(), descriptor: entry_descriptor, code: Some(code) });
    w.to_bytes()
}
