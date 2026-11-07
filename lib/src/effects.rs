//! The effect log of an entry point, and the check that discharges its obligations (O3 of
//! `llm-dlc/loops/foundations-observations.md`, behind [`crate::spec::observe::effect_log`] and
//! [`crate::spec::observe::check`]). The contract is deliberately narrow: *the ordered trace of modeled boundary-call
//! attempts, with the response and the supported failure outcome, is preserved under an explicit environment model.*
//!
//! How it is checked, in both builds alike:
//! - **Recording stubs.** Every call site of a modeled call (the spec's environment model, reads included) is
//!   rewritten into an `invokestatic` of a generated stub ([`crate::shared::redirect_calls`], which moves no
//!   offset). A stub of an observed effect appends one attempt to a log: which call, and a snapshot of its payload
//!   paths read at the call (`topic`, `data.total`), never a reference read later. A stub gives back nothing, or
//!   its type's default, which the caller must drop: a call whose result the handler uses needs a modeled return
//!   value, which this narrow case doesn't model, and is refused.
//! - **One environment for both.** The two builds get the same stubs, in the same order, from one model: the union
//!   of the claim's and both specs' modeled calls. Every call returns normally, the only outcome the model allows
//!   so far, and the result says so.
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
}

impl Model {
    /// The log words per attempt: the call (with the snapshot's null bits), then one per payload path.
    fn width(&self) -> usize {
        1 + self.observed.iter().flatten().map(Vec::len).max().unwrap_or(0)
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
            let returns = match split_call(&c.call).and_then(|(_, _, d)| MethodDescriptor::parse(&d).ok()).map(|d| d.ret) {
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
        .map(|c| format!("{} is a recording stub in both builds: a recorded attempt is the call attempted, with its payload snapshotted at the call, not a delivery or a commit", short(&c.call)))
        .collect();
    let failures: Vec<&ModeledCall> = environment.calls.iter().filter(|c| c.outcomes.iter().any(|o| o != "returns")).collect();
    if failures.is_empty() && !environment.calls.is_empty() {
        out.push("every modeled call returns normally, the environment model's only outcome: a failure of a store, broker or client is outside the claim".into());
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
    let work = crate::tla::tempfile_path("jvmcontract-effects");
    let checked = check_in(&work, claim, old, new, before, after);
    let _ = std::fs::remove_dir_all(&work);
    checked
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

/// One entry point of the old build, checked against its counterpart in the new one.
#[derive(Debug, Clone, Serialize)]
pub struct EntryCheck {
    pub entry: String,
    /// The counterpart's id, when it differs (a path variable renamed).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub new_entry: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub checked: Option<Checked>,
    /// Why the narrow case can't check it, when it can't (string or object inputs, a used result, modeled failures).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unsupported: Option<String>,
}

/// Every entry point of the classes under `before` (or those of `only`, by id), each checked against its
/// counterpart under `after`, matched as `observations --against` matches them, under the claim its own spec makes
/// ([`claim_for`]). An entry point with no counterpart is unresolved; one the narrow case can't model is reported
/// as unsupported, and the others are still checked.
pub fn check_builds(before: &Path, after: &Path, only: &[String], trace_bound: Option<u32>, bounds: ClaimBounds) -> Result<Vec<EntryCheck>, Unsupported> {
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
        let claim = claim_for(spec, trace_bound, bounds.clone());
        let matched = obligations.iter().find(|o| o.entry == spec.id && o.change != Change::Removed && o.change != Change::New).map(|o| o.new_entry.clone().unwrap_or_else(|| spec.id.clone()));
        let counterpart = matched.as_ref().and_then(|id| new.iter().find(|s| &s.id == id));
        let new_entry = matched.clone().filter(|id| id != &spec.id);
        let Some(counterpart) = counterpart else {
            let domain = domain_of(spec);
            let checked = Checked {
                outcome: Outcome { verdict: Verdict::Unresolved, domain, accounting: claim.contract.required.iter().map(|r| Accounted { observation: r.clone(), state: ObservationState::Unresolved }).collect(), witness: None },
                reason: Some(format!("{} has no counterpart in {}: removed, renamed, or not told apart from another", spec.id, after.display())),
                assumptions: claim.assumptions.clone(),
                proof: None,
                before: None,
                after: None,
            };
            out.push(EntryCheck { entry: spec.id.clone(), new_entry, checked: Some(checked), unsupported: None });
            continue;
        };
        match check(&claim, spec, counterpart, before, after) {
            Ok(checked) => out.push(EntryCheck { entry: spec.id.clone(), new_entry, checked: Some(checked), unsupported: None }),
            Err(u) => out.push(EntryCheck { entry: spec.id.clone(), new_entry, checked: None, unsupported: Some(u.what.clone()) }),
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
        for a in &k.assumptions {
            s.push_str(&format!("  assumes: {a}\n"));
        }
    }
    s.push_str(&format!("{} entry points: {} verified, {} refuted, {} unresolved, {} unsupported\n", checks.len(), counts[0], counts[1], counts[2], counts[3]));
    s
}

fn domain_of(spec: &EntryPointSpec) -> String {
    let domain = spec.inputs.iter().map(|i| format!("{}: {}", i.name, i.ty)).collect::<Vec<_>>().join(" × ");
    format!("{} (the request's inputs, the same in both builds)", if domain.is_empty() { "no inputs".to_string() } else { domain })
}

/// [`check`], with the builds, the proof and the JVM run under `work`.
fn check_in(work: &Path, claim: &CanonicalClaim, old: &EntryPointSpec, new: &EntryPointSpec, before: &Path, after: &Path) -> Result<Checked, Unsupported> {
    let required = claim.contract.required.clone();
    let environment = claim.environment.clone().unwrap_or_else(|| old.environment.clone());
    let handler = old.handler.split('#').next().unwrap_or("").rsplit('.').next().unwrap_or("").to_string();
    let assumed = assumptions(&environment, &handler);
    let domain = domain_of(old);
    let unresolved = |reason: String| Checked {
        outcome: Outcome { verdict: Verdict::Unresolved, domain: domain.clone(), accounting: required.iter().map(|r| Accounted { observation: r.clone(), state: ObservationState::Unresolved }).collect(), witness: None },
        reason: Some(reason),
        assumptions: assumed.clone(),
        proof: None,
        before: None,
        after: None,
    };
    let unseen: Vec<String> = old.unresolved.iter().map(|u| format!("the old build: {u}")).chain(new.unresolved.iter().map(|u| format!("the new build: {u}"))).collect();
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
        if let Some(o) = c.outcomes.iter().find(|o| *o != "returns") {
            return Err(unsupported(format!("a modeled outcome other than a normal return ({o} of {}): modeled failures come after the narrow case", short(&c.call))));
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
    let observed: Vec<Option<Vec<String>>> = calls
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
    let (before_cp, before_local) = class_path(before)?;
    let (after_cp, after_local) = class_path(after)?;
    let mut exceptions: Vec<(usize, String)> = Vec::new();
    for (cp, local) in [(&before_cp, &before_local), (&after_cp, &after_local)] {
        for name in local {
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
    let model = Model { calls, observed, bound: environment.trace_bound as usize, exceptions, literals: literals.into_iter().collect() };

    let _ = std::fs::remove_dir_all(work);
    let old_version = prepare(old, &before_cp, &before_local, before, &work.join("before"), &model, 1)?;
    let new_version = prepare(new, &after_cp, &after_local, after, &work.join("after"), &model, 2)?;

    let mut options = crate::equivalence::Options::new(&work.join("before"), &work.join("after"), &new_version.target);
    if old_version.target != new_version.target {
        options.before_target = Some(old_version.target.clone());
    }
    options.engine = crate::Engine::Native;
    options.work = Some(work.join("check"));
    options.unwind = claim.bounds.unwind;
    options.max_array_length = claim.bounds.max_array_length;
    options.timeout_seconds = 300;
    let result = crate::equivalence::run(&options).map_err(|e| unsupported(format!("the effect-trace proof of {}: {e}", old.id)))?;
    let names: Vec<String> = old.inputs.iter().map(|i| i.name.clone()).collect();
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
            Ok(Checked { outcome: Outcome { verdict, domain, accounting, witness: None }, reason: if reasons.is_empty() { None } else { Some(reasons.join("; ")) }, assumptions: assumed, proof, before: None, after: None })
        }
        crate::Verdict::Unverifiable => Ok(Checked { proof, ..unresolved(format!("the effect-trace proof gave no verdict: {}", result.problem.clone().unwrap_or_default())) }),
        crate::Verdict::Violation => {
            let Some(cex) = &result.counterexample else { return Ok(unresolved("a violation without a counterexample".into())) };
            let arguments: Vec<Argument> = cex.inputs.iter().zip(&new_version.params).map(|(t, ty)| argument(t.value.as_ref(), ty)).collect::<Option<_>>().ok_or_else(|| unsupported("a witness value the JVM run can't pass"))?;
            let shown = old.inputs.iter().zip(&arguments).map(|(i, a)| format!("{}={}", i.name, match a { Argument::Scalar(Value::Long(v)) => v.to_string(), Argument::Scalar(Value::Int(v)) => v.to_string(), _ => "?".into() })).collect::<Vec<_>>().join(", ");
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
            let witness = format!(
                "{} on {shown}: the old build {}; the new one {}. Replayed on a JVM (JDK {}) under the modeled dependencies (recording stubs for {stubs}, each returning normally), not against real infrastructure",
                old.id,
                tb.words(),
                ta.words(),
                run.jdk
            );
            Ok(Checked { outcome: Outcome { verdict: Verdict::Refuted, domain, accounting, witness: Some(witness) }, reason: None, assumptions: assumed, proof, before: Some(tb), after: Some(ta) })
        }
    }
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

fn argument(value: Option<&serde_json::Value>, t: &Type) -> Option<Argument> {
    let v = value?;
    let n = v.as_i64().or_else(|| v.as_str().and_then(|s| s.parse().ok())).or_else(|| v.as_bool().map(i64::from))?;
    Some(Argument::Scalar(match t {
        Type::Long => Value::Long(n),
        _ => Value::Int(n as i32),
    }))
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
                    "null".to_string()
                } else if !strings.contains(&(call, j)) {
                    v.to_string()
                } else {
                    model.literals.get((*v as usize).wrapping_sub(1)).map(|s| format!("{s:?}")).unwrap_or_else(|| v.to_string())
                };
                format!("{p}={value}")
            })
            .collect::<Vec<_>>()
            .join(", ");
        let mut key = vec![nulls];
        key.extend(&values);
        attempts.push((call, key, format!("{}({shown})", short(&model.calls[call]))));
    }
    let mark = word(3) & 0x1f;
    let mut unresolved = Vec::new();
    if mark & PAST_BOUND != 0 {
        unresolved.push(format!("more attempts than the trace bound, {}", model.bound));
    }
    if mark & UNSNAPSHOTTED != 0 {
        unresolved.push("a payload value no snapshot holds (a string that is no literal of either build, or an object of another class than the call site's)".into());
    }
    if mark & UNMADE != 0 {
        unresolved.push("the handler's constructor threw on the null dependencies".into());
    }
    if mark & UNMODELED != 0 {
        unresolved.push("a call on a dependency that the environment model doesn't model".into());
    }
    if mark & NULL_THROWN != 0 {
        unresolved.push("a NullPointerException, which a dependency left null may have caused (a call on it through a supertype, Object.hashCode say)".into());
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
    /// Each step into an object: the class it must be, and how its property is read.
    hops: Vec<(String, Access)>,
    leaf: Leaf,
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
}

fn package_of(internal: &str) -> &str {
    internal.rsplit_once('/').map(|(p, _)| p).unwrap_or("")
}

fn in_package(package: &str, simple: &str) -> String {
    if package.is_empty() { simple.to_string() } else { format!("{package}/{simple}") }
}

/// Writes `spec`'s build into `out` with the stubs in place, and the generated method that runs the handler and
/// returns its log; `tag` tells the builds' unresolved marks apart.
fn prepare(spec: &EntryPointSpec, cp: &ClassPath, local: &[String], build: &Path, out: &Path, model: &Model, tag: i64) -> Result<Prepared, Unsupported> {
    let (class_dotted, method_name) = spec.handler.split_once('#').ok_or_else(|| unsupported(format!("a handler that isn't Class#method: {}", spec.handler)))?;
    let class_name = class_dotted.replace('.', "/");
    let class = cp.application(&class_name).ok().flatten().ok_or_else(|| unsupported(format!("no class {class_dotted} under {}", build.display())))?;
    let candidates: Vec<_> = class.methods.iter().filter(|m| m.name == method_name && !m.is_synthetic() && !m.is_bridge()).collect();
    let [method] = candidates.as_slice() else { return Err(unsupported(format!("{} names {} methods", spec.handler, candidates.len()))) };
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
    for call in &model.calls {
        if let Some((owner, _, _)) = split_call(call) {
            dependencies.insert(owner);
        }
    }
    let package = package_of(&class_name).to_string();
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
            let read = read_path(cp, &package, &sites, &d, path)?;
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
                if model.calls.contains(&call) {
                    let ret = MethodDescriptor::parse(&member.descriptor).map(|d| d.ret).unwrap_or(Type::Void);
                    let dropped = matches!(insns.get(k + 1), Some((_, Insn::Pop | Insn::Pop2)));
                    if ret != Type::Void && !dropped {
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
    let entry_descriptor = format!("({})[J", descriptor.params.iter().map(Type::descriptor).collect::<String>());
    std::fs::write(out.join(format!("{entry}.class")), entry_class(&entry, &stubs, &class_name, method_name, &method.descriptor, &descriptor, &constructor.descriptor, &ctor, model, &present, tag)).map_err(|e| unsupported(e.to_string()))?;
    Ok(Prepared { target: format!("{}#{METHOD}", entry.replace('/', ".")), entry, descriptor: entry_descriptor, params: descriptor.params.clone(), strings })
}

/// How a stub of `call` (descriptor `d`) reads `path` at the call sites `sites`.
fn read_path(cp: &ClassPath, package: &str, sites: &[&crate::spec::observe::EffectSite], d: &MethodDescriptor, path: &str) -> Result<Read, Unsupported> {
    let segments: Vec<&str> = path.split('.').collect();
    let names = &sites[0].arguments;
    let param = names.iter().position(|a| a.name == segments[0]).ok_or_else(|| unsupported(format!("the payload path {path} starts at no parameter of the call")))?;
    let declared = d.params.get(param).cloned().ok_or_else(|| unsupported(format!("the payload path {path}: no parameter {param}")))?;
    let classes: BTreeSet<Option<String>> = sites.iter().map(|s| s.arguments.get(param).and_then(|a| a.class.clone())).collect();
    let mut hops = Vec::new();
    let mut ty = declared.clone();
    if segments.len() > 1 {
        let mut current = match classes.iter().collect::<Vec<_>>().as_slice() {
            [Some(c)] => c.clone(),
            [None] => return Err(unsupported(format!("the payload path {path}: the walk can't tell the class of the argument passed"))),
            _ => return Err(unsupported(format!("the payload path {path}: the call sites pass {} classes of argument, and a stub reads one", classes.len()))),
        };
        for (k, field) in segments[1..].iter().enumerate() {
            let (access, t) = property(cp, package, &current, field).ok_or_else(|| unsupported(format!("the payload path {path}: {} has no property {field} a stub in {} can read (a record component, a public getter or a public field)", current.replace('/', "."), package.replace('/', "."))))?;
            hops.push((current.clone(), access));
            ty = t.clone();
            if k + 2 < segments.len() {
                current = t.class_name().map(str::to_string).ok_or_else(|| unsupported(format!("the payload path {path} steps into a {}", t.java_name())))?;
            }
        }
    }
    let leaf = match &ty {
        Type::Long => Leaf::Long,
        Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int => Leaf::Int,
        Type::Object(c) if c == "java/lang/String" => Leaf::Str,
        other => return Err(unsupported(format!("the payload path {path} is a {}: a stub snapshots integral values and literal strings", other.java_name()))),
    };
    Ok(Read { param, hops, leaf })
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
            let (n, log, at, mask, value, tmp) = (slot, slot + 1, slot + 2, slot + 3, slot + 4, slot + 6);
            code.max_stack = 8;
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
                    for (class, access) in &r.hops {
                        code.store(Kind::Ref, tmp);
                        code.load(Kind::Ref, tmp);
                        code.if_null(null);
                        code.load(Kind::Ref, tmp);
                        let c = w.pool.class(class);
                        code.op_u16(0xc1, c); // instanceof
                        code.if_zero(Cond::Eq, unresolved);
                        code.load(Kind::Ref, tmp);
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
                    match r.leaf {
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
            return_default(&mut code, &descriptor.ret);
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
#[allow(clippy::too_many_arguments)] // the parts of one generated method
fn entry_class(name: &str, stubs: &str, handler: &str, method: &str, method_descriptor: &str, descriptor: &MethodDescriptor, ctor_descriptor: &str, ctor: &MethodDescriptor, model: &Model, present: &[bool], tag: i64) -> Vec<u8> {
    let mut w = ClassWriter::new(name);
    w.access = flags::PUBLIC | flags::FINAL | flags::SUPER;
    let mut code = CodeBuilder::new();
    let mut slot = 0u16;
    let mut slots = Vec::new();
    for t in &descriptor.params {
        slots.push(slot);
        slot += if matches!(t, Type::Long | Type::Double) { 2 } else { 1 };
    }
    code.max_locals = slot;
    code.max_stack = 12;
    let (log, h, thrown, result, cut) = (slot, slot + 1, slot + 2, slot + 3, slot + 5);
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
    let set = |code: &mut CodeBuilder, w: &mut ClassWriter, index: i32, value: i64| {
        code.load(Kind::Ref, log);
        code.iconst(index);
        let v = w.pool.long(value);
        code.ldc2(v);
        code.op(0x50);
    };

    // The handler, made by its constructor with null dependencies.
    let (make_start, make_end, unmade, call_start, call_end, threw, finish) = (code.label(), code.label(), code.label(), code.label(), code.label(), code.label(), code.label());
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
    set(&mut code, &mut w, 3, tag * 16 + UNMADE);
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
    let t = w.pool.long(tag * 16);
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
    let entry_descriptor = format!("({})[J", descriptor.params.iter().map(Type::descriptor).collect::<String>());
    w.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: METHOD.into(), descriptor: entry_descriptor, code: Some(code) });
    w.to_bytes()
}
