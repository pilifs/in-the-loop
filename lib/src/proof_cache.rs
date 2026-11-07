//! The tool's part of a canonical claim (`llm-dlc/loops/foundations-summaries.md`, S2): the identities a cached result
//! rests on besides the code ([`crate::spec::ToolIdentity`]). Each is a digest of what is read, not a version
//! number, so that a rebuilt binary, another JDK build of the same release, or a changed model is a different claim.
//! An identity that can't be computed is empty, which makes the claim uncacheable ([`crate::spec::cache::key`]).
//!
//! | Part | What is digested |
//! |---|---|
//! | `binary` | the bytes of the running executable ([`std::env::current_exe`]): the checker, its models and its contract library are compiled into it |
//! | `jdk` | the JDK's whole `release` file (version, vendor, build), whose classes the own checker reads |
//! | `models` | the tool's models of JDK classes, as [`crate::statement::Models`] digests them, or `none` when unused |
//! | `checker` | the checker and every setting that can change its verdict, as the caller words them |
//!
//! The code itself is each version's closure ([`crate::closure::version_digest`]).
//!
//! **A regression proof's use of the cache** ([`Regression`]): `equivalence::run_check` makes one call once its claim
//! is prepared (the harness generated, the shared callees planned) and one once the result is known. The claim is
//! built from what the check is about: the preservation contract (the target and its parameters, derived by identity
//! or by `--before-arguments`), the observations, the correspondence the flags state, the bounds, the assumptions
//! (the statement's own, its domain, the shared callees, the harness's digest), each version's closure from the
//! target and every record constructor its inputs are made with, and the tools with every setting that can change
//! a verdict. Only a check by the own checker (`--engine native`) is cacheable for now: JBMC's own identity is not
//! yet part of the key, so a claim JBMC may decide is uncacheable rather than keyed without it. The deadline is not
//! in the claim: it decides only whether a verdict is reached, and an unresolved result is never stored.
//!
//! A verified hit gives back the stored result, marked as an exact reuse ([`Reuse::Exact`]) with the run it came
//! from; no checker runs. A refuted hit first replays the stored witness in the harness, in the interpreter, on both
//! versions as they are now: only a witness that reproduces is the result, and one that doesn't is a miss. A
//! refutation is stored only when its witness, read back as stored, reproduces in the interpreter (one confirmed
//! only on a JVM is not stored). Every use of the cache is a note in the output; a failure to store one never
//! changes the verdict.
//!
//! **A changed helper's proof, reused in its caller** ([`Helpers`], S4): with `--cache` and `--engine native`, a
//! changed pure helper of the narrow kind [`crate::shared`] describes is proved first, as a regression check of its
//! own (the same builds, bounds and settings, the helper as the target, nothing restricting its inputs), on demand
//! and within a share of the caller's time, or found in the cache under that check's key. A proof that covers every
//! input, with no assumption beyond the checker's own, makes the helper one stub in both versions of the caller's
//! proof, and the caller's statement gains an assumption of kind `callee` and basis `proved` whose id is the helper
//! proof's claim key. That assumption is part of the caller's own claim, so the caller's key changes with the
//! helper proof's. The dependencies are acyclic: a helper is never proved within its own proof, directly or through
//! others (the checks in progress on this thread are a stack, and a helper on it stays as written), and through the
//! cache no cycle can form, since a claim's key digests the keys of the helper proofs it rests on.

use std::cell::RefCell;
use std::fmt::Write as _;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::classfile::{MemberRef, Type};
use crate::classpath::ClassPath;
use crate::digest::sha256_hex;
use crate::equivalence::{Counterexample, Options, Outcome, Replay};
use crate::harness::{self, BeforeMethod, Layout, Slot};
use crate::jbmc::Argument;
use crate::sarif::{self, Finding};
use crate::spec::cache::{self, ClaimKey, ResultRecord, Reuse};
use crate::spec::{Accounted, CanonicalClaim, ClaimBounds, Correspondence, Derivation, ExternalInput, Observation, ObservationState, Part, PreservationContract, ToolIdentity, Unsupported, VersionDigests};
use crate::statement::{Assumption, AssumptionKind, Basis, Domain, Observations, Statement};
use crate::{witness, Error, Verdict};

/// `sha256:` and the digest of the running executable's bytes; empty when it can't be read. Read once per process.
pub fn binary() -> String {
    static BINARY: OnceLock<String> = OnceLock::new();
    BINARY
        .get_or_init(|| {
            let bytes = std::env::current_exe().and_then(std::fs::read);
            bytes.map(|b| format!("sha256:{}", sha256_hex(&b))).unwrap_or_default()
        })
        .clone()
}

/// `sha256:` and the digest of the JDK's `release` file; empty when no JDK is found.
pub fn jdk() -> String {
    static JDK: OnceLock<String> = OnceLock::new();
    JDK.get_or_init(|| {
        let release = crate::jimage::JImage::find_java_home().and_then(|home| std::fs::read(home.join("release")).ok());
        release.map(|b| format!("sha256:{}", sha256_hex(&b))).unwrap_or_default()
    })
    .clone()
}

/// The models' digest when they are used, `none` otherwise.
pub fn models(used: bool) -> String {
    if used {
        crate::statement::models(true).digest.unwrap_or_default()
    } else {
        "none".into()
    }
}

/// The tool identity of a check with the models `used` or not, by the checker `checker` (its engine and every
/// setting that can change a verdict, worded by the caller).
pub fn tools(models_used: bool, checker: &str) -> ToolIdentity {
    ToolIdentity { models: models(models_used), jdk: jdk(), checker: checker.to_string(), binary: binary() }
}

/// What a reused result is shown with, as the check would show its own: the domain as the proof line writes it, the
/// harness's source, the work directory, the previous version's call, and where findings are anchored.
pub struct Shown<'a> {
    pub domain: &'a str,
    pub statement: &'a Path,
    pub work: &'a Path,
    pub previous: Option<&'a str>,
    pub uri: Option<&'a str>,
    pub line: u32,
}

/// A regression proof's claim as `equivalence::run_check` has prepared it, for the cache's one call there.
pub struct Regression<'a> {
    pub options: &'a Options,
    /// Each version's classes with the class path and the JDK, as the shared callees are planned on.
    pub before_cp: &'a ClassPath,
    pub after_cp: &'a ClassPath,
    /// The previous version's method and the new one's.
    pub before_target: MemberRef,
    pub target: MemberRef,
    pub layout: &'a Layout,
    pub previous: Option<&'a BeforeMethod>,
    pub before_parameters: &'a [String],
    pub domain: &'a Domain,
    pub observations: &'a Observations,
    pub assumptions: &'a [Assumption],
    /// The callees taken as one function in both versions, as planned.
    pub shared: &'a [String],
    /// Where the harness is, and the previous version relocated: what a stored witness is replayed on.
    pub harness: &'a Path,
    pub before_classes: &'a Path,
    pub shown: Shown<'a>,
}

/// A check's place in the cache, once its claim has a key: what the result is stored under, and how a witness is
/// replayed. Inert when the check has no cache or its claim is uncacheable.
pub struct Entry {
    place: Option<Place>,
}

struct Place {
    dir: PathBuf,
    key: ClaimKey,
    /// The class path the harness replays a witness on: the harness, both versions, the class path.
    replay: Vec<PathBuf>,
    models: bool,
    /// The harness's parameters, which a witness gives values for.
    types: Vec<Type>,
    domain: String,
    required: Vec<String>,
    provenance: String,
    /// The note the lookup left in the output, which a reuse of the result shouldn't repeat.
    note: String,
}

/// What is stored beside a regression proof's record, for a reuse to give the result back as the check reported it.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Stored {
    pub output: String,
    pub proof: Option<String>,
    #[serde(default)]
    pub vacuous: Option<String>,
    #[serde(default)]
    pub shared: Vec<String>,
    pub statement: Statement,
    /// The statement's gap mode, by name: its type doesn't deserialize.
    #[serde(default)]
    pub gap_mode: Option<String>,
    #[serde(default)]
    pub findings: Vec<StoredFinding>,
    #[serde(default)]
    pub counterexample: Option<StoredCounterexample>,
}

/// A [`Finding`] as stored.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoredFinding {
    pub rule_id: String,
    pub message: String,
}

/// A [`Counterexample`] as stored: as it serializes, read back.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoredCounterexample {
    pub input: String,
    pub before: String,
    pub after: String,
    pub values: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub found: Option<String>,
    pub shrink_runs: u32,
    pub inputs: Vec<StoredTyped>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub found_inputs: Option<Vec<StoredTyped>>,
    pub call: StoredCall,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub previous_call: Option<StoredCall>,
}

/// A [`witness::Typed`] as stored.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoredTyped {
    pub name: String,
    #[serde(rename = "type")]
    pub ty: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub value: Option<Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub components: Option<Vec<StoredTyped>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub from: Option<String>,
}

/// A [`witness::Call`] as stored.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoredCall {
    pub class: String,
    pub class_file: String,
    pub classes: String,
    pub method: String,
    pub descriptor: String,
    #[serde(rename = "static")]
    pub is_static: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub receiver: Option<StoredTyped>,
    pub arguments: Vec<StoredTyped>,
}

impl From<StoredTyped> for witness::Typed {
    fn from(t: StoredTyped) -> witness::Typed {
        witness::Typed { name: t.name, ty: t.ty, value: t.value, components: t.components.map(|c| c.into_iter().map(Into::into).collect()), from: t.from }
    }
}

impl From<StoredCall> for witness::Call {
    fn from(c: StoredCall) -> witness::Call {
        witness::Call { class: c.class, class_file: c.class_file, classes: c.classes, method: c.method, descriptor: c.descriptor, is_static: c.is_static, receiver: c.receiver.map(Into::into), arguments: c.arguments.into_iter().map(Into::into).collect() }
    }
}

impl From<StoredCounterexample> for Counterexample {
    fn from(c: StoredCounterexample) -> Counterexample {
        Counterexample {
            input: c.input,
            before: c.before,
            after: c.after,
            values: c.values,
            found: c.found,
            shrink_runs: c.shrink_runs,
            inputs: c.inputs.into_iter().map(Into::into).collect(),
            found_inputs: c.found_inputs.map(|f| f.into_iter().map(Into::into).collect()),
            call: c.call.into(),
            previous_call: c.previous_call.map(Into::into),
        }
    }
}

fn uncacheable(why: impl std::fmt::Display) -> Unsupported {
    Unsupported::new(Part::Summaries, format!("the claim is uncacheable: {why}"))
}

/// The arguments a stored witness gives, the harness's parameters `types` in order: none when it doesn't read back
/// as one value of each.
pub fn witness_arguments(types: &[Type], witness: &str) -> Option<Vec<Argument>> {
    fn scalar(v: &Value, t: &Type) -> Option<crate::interp::Value> {
        let raw = match v {
            Value::Bool(b) => b.to_string(),
            Value::Number(n) => n.to_string(),
            Value::String(s) => s.clone(),
            _ => return None,
        };
        crate::jbmc::parse_value(t, &raw).ok()
    }
    let inputs: Vec<StoredTyped> = serde_json::from_str(witness).ok()?;
    if inputs.len() != types.len() {
        return None;
    }
    inputs
        .iter()
        .zip(types)
        // A null argument is stored as `"value": null`, which reads back as no value.
        .map(|(input, t)| match (t, input.value.as_ref().unwrap_or(&Value::Null)) {
            (Type::Array(_), Value::Null) => Some(Argument::Null),
            (Type::Array(element), Value::Array(items)) => items.iter().map(|x| scalar(x, element)).collect::<Option<Vec<_>>>().map(Argument::Array),
            (_, v) => scalar(v, t).map(Argument::Scalar),
        })
        .collect()
}

/// `text`'s comma-separated parts, outside parentheses.
fn split_top_level(text: &str) -> Vec<String> {
    let (mut parts, mut depth, mut current) = (Vec::new(), 0i32, String::new());
    for c in text.chars() {
        match c {
            '(' | '[' | '{' => depth += 1,
            ')' | ']' | '}' => depth -= 1,
            ',' if depth == 0 => {
                parts.push(current.trim().to_string());
                current.clear();
                continue;
            }
            _ => {}
        }
        current.push(c);
    }
    parts.push(current.trim().to_string());
    parts
}

/// `2026-11-07T12:00:00Z`, now.
fn utc_now() -> String {
    let secs = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_secs() as i64).unwrap_or(0);
    let (days, rest) = (secs.div_euclid(86_400), secs.rem_euclid(86_400));
    // Howard Hinnant's civil_from_days.
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = yoe + era * 400 + i64::from(month <= 2);
    format!("{year:04}-{month:02}-{day:02}T{:02}:{:02}:{:02}Z", rest / 3600, rest / 60 % 60, rest % 60)
}

impl<'a> Regression<'a> {
    /// The canonical claim of the check, or why it is uncacheable.
    pub fn claim(&self) -> Result<CanonicalClaim, Unsupported> {
        let o = self.options;
        if o.engine != crate::Engine::Native {
            return Err(uncacheable("JBMC may decide it (--engine jbmc or auto), and JBMC's own identity is not yet part of the key; the cache is used with --engine native"));
        }
        // Each version's roots: the method compared, and every constructor its inputs are made with.
        let init = |class: &str, r: &harness::RecordType| MemberRef::new(class.strip_prefix("before/").unwrap_or(class), "<init>", &r.constructor());
        let mut after_roots = vec![self.target.clone()];
        let mut before_roots = vec![self.before_target.clone()];
        for slot in self.layout.records() {
            if let Slot::Record { record, before, .. } = slot {
                after_roots.push(init(&record.class, record));
                let b = before.as_ref().unwrap_or(record);
                before_roots.push(init(&b.class, b));
            }
        }
        if let Some(p) = self.previous {
            for r in p.receiver.iter().chain(p.records.iter().flatten()) {
                before_roots.push(init(&r.class, r));
            }
        }
        let digest = |cp: &ClassPath, roots: &[MemberRef]| -> Result<String, Unsupported> {
            let configuration = crate::closure::Configuration::read(cp, &[]).map_err(|e| uncacheable(format!("its configuration could not be read: {e}")))?;
            Ok(crate::closure::version_digest(cp, roots, &configuration))
        };
        let closures = VersionDigests { before: digest(self.before_cp, &before_roots)?, after: digest(self.after_cp, &after_roots)? };

        let mut observations = vec![Observation::Result, Observation::Exception];
        observations.extend(self.observations.arrays.iter().map(|a| Observation::ArrayParameter { parameter: a.clone() }));
        let derivation = match &o.before_arguments {
            Some(a) => Derivation::Stated { expression: a.clone() },
            None => Derivation::Identity,
        };
        let contract = PreservationContract {
            subject: o.target.clone(),
            inputs: self.domain.parameters.iter().map(|p| ExternalInput { name: p.name.clone(), ty: p.ty.clone(), derivation: derivation.clone() }).collect(),
            required: observations.iter().map(Observation::id).collect(),
            approved_changes: Vec::new(),
        };
        let before_arguments = o.before_arguments.as_deref().map(split_top_level);
        let correspondence = Correspondence::from_flags(self.before_parameters, before_arguments.as_deref(), o.results_agree_when.as_deref());

        fn json<T: Serialize>(v: &T) -> String {
            serde_json::to_string(v).unwrap_or_default()
        }
        let mut assumptions: Vec<String> = self.assumptions.iter().map(json).collect();
        assumptions.push(format!("domain: {}", json(self.domain)));
        assumptions.push(format!("observed: {}", json(self.observations)));
        assumptions.push(format!("before target: {}", self.options.before_target.as_deref().unwrap_or("the target's")));
        assumptions.push(format!("shared callees: {}", if o.shared_callees { format!("on, {}", if self.shared.is_empty() { "none planned".to_string() } else { self.shared.join(", ") }) } else { "off".into() }));
        let harness_file = self.harness.join(format!("{}.class", harness::CLASS));
        let harness_bytes = std::fs::read(&harness_file).map_err(|e| uncacheable(format!("its harness {} could not be read: {e}", harness_file.display())))?;
        assumptions.push(format!("harness: sha256:{}", sha256_hex(&harness_bytes)));

        let contracts = match &o.contracts {
            Some(p) => format!("sha256:{}", sha256_hex(&std::fs::read(p).map_err(|e| uncacheable(format!("its contracts {} could not be read: {e}", p.display())))?)),
            None => "none".into(),
        };
        let sat = serde_json::to_string(&crate::statement::native_sat()).unwrap_or_default();
        let checker = format!(
            "engine native; gaps {}; contracts {contracts}; contract library {}; max trust {}; solver {sat}; shrink {}; java home {}",
            o.gaps.name(),
            if o.contract_library { "on" } else { "off" },
            o.max_trust.map(|n| n.to_string()).unwrap_or_else(|| "any".into()),
            if o.shrink { "on" } else { "off" },
            o.java_home.as_ref().map(|h| h.display().to_string()).unwrap_or_else(|| "found".into()),
        );
        Ok(CanonicalClaim {
            contract,
            closures,
            domain: None,
            observations,
            correspondence: Some(correspondence),
            environment: None,
            bounds: ClaimBounds { unwind: o.unwind, max_array_length: o.max_array_length },
            assumptions,
            tools: tools(o.models, &checker),
        })
    }

    /// The cache's one call once the claim is prepared: the check's entry, and the stored result when it is the
    /// result. Notes in `out` say what the cache did.
    pub fn lookup(self, out: &mut String) -> Result<(Entry, Option<Outcome>), Error> {
        let inert = Entry { place: None };
        let Some(dir) = self.options.cache.clone() else { return Ok((inert, None)) };
        let key = match self.claim().and_then(|c| cache::key(&c)) {
            Ok(k) => k,
            Err(u) => {
                let _ = writeln!(out, "note: the proof cache is not used: {}", u.what);
                return Ok((inert, None));
            }
        };
        KEYS.with(|k| k.borrow_mut().push((self.options.target.clone(), key.clone())));
        let mut replay = vec![self.harness.to_path_buf(), self.options.after.clone(), self.before_classes.to_path_buf()];
        replay.extend(self.options.classpath.iter().cloned());
        let provenance = format!(
            "jvmcontract {} ({}), --engine native, at {}, on {} and {}",
            env!("CARGO_PKG_VERSION"),
            binary().get(..19).unwrap_or("unknown binary"),
            utc_now(),
            self.options.before.display(),
            self.options.after.display()
        );
        let required = [Observation::Result, Observation::Exception].iter().map(Observation::id).chain(self.observations.arrays.iter().map(|a| Observation::ArrayParameter { parameter: a.clone() }.id())).collect();
        let mut place = Place { dir, key, replay, models: self.options.models, types: self.layout.types(), domain: self.shown.domain.to_string(), required, provenance, note: String::new() };
        let found = match cache::lookup_detail(&place.dir, &place.key) {
            Ok(found) => found,
            Err(u) => {
                let _ = writeln!(out, "note: the proof cache is not used: {}", u.what);
                return Ok((inert, None));
            }
        };
        let before = out.len();
        let hit = match found {
            None => {
                let _ = writeln!(out, "note: the proof cache has no result for this claim ({}); proving", place.key.0);
                None
            }
            Some((record, detail)) => self.reuse(&place, record, detail, out)?,
        };
        place.note = out[before..].to_string();
        Ok((Entry { place: Some(place) }, hit))
    }

    /// The stored result as this check's, or none (a miss, with a note) when it can't be.
    fn reuse(&self, place: &Place, record: ResultRecord, detail: Option<Value>, out: &mut String) -> Result<Option<Outcome>, Error> {
        let key = &place.key.0;
        let Some(stored) = detail.and_then(|d| serde_json::from_value::<Stored>(d).ok()) else {
            let _ = writeln!(out, "note: the proof cache's entry for this claim ({key}) has no report this tool can read; proving again");
            return Ok(None);
        };
        let (verdict, counterexample, replay, how) = match record.outcome.verdict {
            crate::spec::Verdict::Verified => (Verdict::Verified, None, None, "nothing was proved again".to_string()),
            crate::spec::Verdict::Refuted => {
                let reproduces = record.outcome.witness.as_deref().and_then(|w| witness_arguments(&place.types, w)).is_some_and(|arguments| place.reproduces(&arguments));
                let Some(c) = stored.counterexample.clone().filter(|_| reproduces) else {
                    let _ = writeln!(out, "note: the proof cache's refutation of this claim ({key}) has a witness that no longer reproduces in the interpreter; proving again");
                    return Ok(None);
                };
                (Verdict::Violation, Some(Counterexample::from(c)), Some(Replay { by: "interpreter".into(), reproduced: true }), "its witness replayed again on both versions in the interpreter, and reproduces".to_string())
            }
            crate::spec::Verdict::Unresolved => return Ok(None),
        };
        let o = self.options;
        let findings: Vec<Finding> = stored.findings.iter().map(|f| Finding::new(&f.rule_id, f.message.clone(), self.shown.uri.map(str::to_string), self.shown.line)).collect();
        if let Some(report) = &o.report {
            sarif::write(&report.join("equivalence.sarif"), &findings)?;
        }
        let mut statement = stored.statement;
        statement.gap_mode = stored.gap_mode.as_deref().and_then(|g| g.parse().ok());
        let output = format!("{}note: reused from the proof cache: an exact hit of claim {key}, the result of {}; {how}\n", stored.output, record.provenance);
        Ok(Some(Outcome {
            verdict,
            target: o.target.clone(),
            domain: Some(self.shown.domain.to_string()),
            counterexample,
            proof: stored.proof.map(|p| format!("reused from the proof cache (claim {key}, {}): {p}", record.provenance)),
            problem: None,
            statement: Some(self.shown.statement.to_path_buf()),
            findings,
            output,
            work: self.shown.work.to_path_buf(),
            shared: stored.shared,
            previous: self.shown.previous.map(str::to_string),
            relation: o.results_agree_when.clone(),
            vacuous: stored.vacuous,
            search: None,
            replay,
            stated: Some(statement),
            advice: None,
            reuse: Some(Reuse::Exact { key: place.key.clone(), from: record.provenance }),
        }))
    }
}

impl Place {
    /// Whether the harness, run in the interpreter on `arguments`, refutes the statement: both versions as they are
    /// now disagree there.
    fn reproduces(&self, arguments: &[Argument]) -> bool {
        let Ok(cp) = witness::classpath(self.replay.iter().map(PathBuf::as_path)) else { return false };
        witness::fails_in_harness(&cp.with_models(self.models), harness::CLASS, &self.types, arguments) == Some(true)
    }
}

impl Entry {
    /// The cache's one call once the result is known: a verified result is stored, and a refuted one whose
    /// witness, read back as stored, reproduces; anything else is not. A note in the outcome's output says which.
    pub fn store(&self, outcome: &mut Outcome) {
        let Some(place) = &self.place else { return };
        let note = |outcome: &mut Outcome, text: String| {
            let _ = writeln!(outcome.output, "note: {text}");
        };
        let (verdict, witness) = match outcome.verdict {
            Verdict::Verified => (crate::spec::Verdict::Verified, None),
            Verdict::Violation => {
                let witness = outcome.counterexample.as_ref().and_then(|c| serde_json::to_string(&c.inputs).ok());
                let reproduces = witness.as_deref().and_then(|w| witness_arguments(&place.types, w)).is_some_and(|arguments| place.reproduces(&arguments));
                if !reproduces {
                    note(outcome, "the refutation is not stored in the proof cache: its witness, read back as stored, does not reproduce in the interpreter".into());
                    return;
                }
                (crate::spec::Verdict::Refuted, witness)
            }
            Verdict::Unverifiable => return,
        };
        let Some(statement) = outcome.stated.clone() else { return };
        let counterexample = outcome.counterexample.as_ref().map(|c| serde_json::to_value(c).ok().and_then(|v| serde_json::from_value::<StoredCounterexample>(v).ok()));
        if let Some(None) = counterexample {
            note(outcome, "the result is not stored in the proof cache: its counterexample does not read back".into());
            return;
        }
        let stored = Stored {
            output: outcome.output.replacen(&place.note, "", 1),
            proof: outcome.proof.clone(),
            vacuous: outcome.vacuous.clone(),
            shared: outcome.shared.clone(),
            gap_mode: statement.gap_mode.map(|g| g.name().to_string()),
            statement,
            findings: outcome.findings.iter().map(|f| StoredFinding { rule_id: f.rule_id.clone(), message: f.message.clone() }).collect(),
            counterexample: counterexample.flatten(),
        };
        // What is stored must read back, or a reuse could not give it.
        let detail = serde_json::to_value(&stored).ok().filter(|v| serde_json::from_value::<Stored>(v.clone()).is_ok());
        let Some(detail) = detail else {
            note(outcome, "the result is not stored in the proof cache: its report does not read back".into());
            return;
        };
        let state = if verdict == crate::spec::Verdict::Verified { ObservationState::Preserved } else { ObservationState::Unresolved };
        let record = ResultRecord {
            key: place.key.clone(),
            outcome: crate::spec::Outcome { verdict, domain: place.domain.clone(), accounting: place.required.iter().map(|o| Accounted { observation: o.clone(), state }).collect(), witness },
            provenance: place.provenance.clone(),
        };
        match cache::store_detail(&place.dir, &record, Some(detail)) {
            Ok(()) => note(outcome, format!("stored in the proof cache as claim {}", place.key.0)),
            Err(u) => note(outcome, format!("the result is not stored in the proof cache: {}", u.what)),
        }
    }
}

thread_local! {
    /// The checks in progress on this thread whose changed helpers may be proved, innermost last, by target: a
    /// helper on it is not proved again within its own proof.
    static PROVING: RefCell<Vec<String>> = const { RefCell::new(Vec::new()) };
    /// The claim key each check on this thread got once prepared, by target, latest last: how a helper's check,
    /// run by [`Helpers`], names the claim it proved.
    static KEYS: RefCell<Vec<(String, ClaimKey)>> = const { RefCell::new(Vec::new()) };
}

/// At most this share of a caller's time goes to proving its changed helpers; what they take comes out of it.
const HELPER_SHARE: u32 = 2;

/// A regression check's changed helpers, proved first (S4): the provider [`crate::shared::plan_with`] asks, and what
/// the caller's claim and output gain from it.
pub struct Helpers<'a> {
    options: &'a Options,
    work: PathBuf,
    budget: Duration,
    spent: Duration,
    assumptions: Vec<Assumption>,
    /// The note per helper asked about, for the caller's output.
    pub notes: String,
}

impl<'a> Helpers<'a> {
    /// The helpers of the check `options` describes, worked on under `work`.
    pub fn new(options: &'a Options, work: &Path) -> Helpers<'a> {
        Helpers { options, work: work.join("helpers"), budget: Duration::from_secs(options.timeout_seconds) / HELPER_SHARE, spent: Duration::ZERO, assumptions: Vec::new(), notes: String::new() }
    }

    /// Whether this check proves its changed helpers: it is cacheable (`--cache`, `--engine native`), and shares
    /// callees at all.
    fn active(&self) -> bool {
        self.options.cache.is_some() && self.options.engine == crate::Engine::Native && self.options.shared_callees
    }

    /// The caller's time left once its helpers are proved: `total` less what they took.
    pub fn remaining(&self, total: Duration) -> Duration {
        total.saturating_sub(self.spent)
    }

    /// The assumptions the caller's claim gains: one per helper proved, of kind `callee`, basis `proved`, with the
    /// helper proof's claim key as its id.
    pub fn assumptions(&self) -> &[Assumption] {
        &self.assumptions
    }

    /// The proof of `callee`'s two versions' equivalence, from the cache or proved now; `None`, with a note, when
    /// there is none to use.
    pub fn prove(&mut self, callee: &MemberRef) -> Option<crate::shared::Proved> {
        if !self.active() {
            return None;
        }
        let target = crate::shared::target_of(callee);
        let name = format!("{}.{}", callee.owner.rsplit('/').next().unwrap_or(&callee.owner), callee.name);
        let mut note = |why: String| {
            let _ = writeln!(self.notes, "note: {name}, changed, stays as written in both versions: {why}");
        };
        let caller = self.options.target.clone();
        let names_callee = |t: &String| crate::verifier::parse_target(t).is_some_and(|(c, m)| c == callee.owner && m == callee.name);
        let cycle = names_callee(&caller) || PROVING.with(|p| p.borrow().iter().any(names_callee));
        if cycle {
            note("its proof would rest on the proof it is used in".into());
            return None;
        }
        let left = self.budget.saturating_sub(self.spent);
        if left < Duration::from_secs(1) {
            note("no time is left for its proof".into());
            return None;
        }
        let mut helper = self.options.clone();
        helper.target = target.clone();
        helper.before_target = None;
        helper.before_arguments = None;
        helper.results_agree_when = None;
        helper.unchanged_unless = None;
        helper.report = None;
        helper.confirm = false;
        helper.timeout_seconds = left.as_secs().max(1);
        helper.work = Some(self.work.join(format!("{}.{}", callee.owner.replace('/', "."), callee.name)));
        let started = Instant::now();
        PROVING.with(|p| p.borrow_mut().push(caller.clone()));
        let outcome = crate::equivalence::run(&helper);
        PROVING.with(|p| p.borrow_mut().pop());
        self.spent += started.elapsed();
        let outcome = match outcome {
            Ok(o) => o,
            Err(e) => {
                note(format!("its check failed: {e}"));
                return None;
            }
        };
        let key = KEYS.with(|k| k.borrow().iter().rev().find(|(t, _)| *t == target).map(|(_, key)| key.clone()));
        if let Err(why) = applicable(&outcome) {
            note(why);
            return None;
        }
        let Some(key) = key else {
            note("its claim has no key".into());
            return None;
        };
        let dir = self.options.cache.as_ref().expect("active");
        let record = match cache::lookup(dir, &key) {
            Ok(Some(r)) if r.outcome.verdict == crate::spec::Verdict::Verified => r,
            _ => {
                note(format!("its proof is not in the proof cache (claim {})", key.0));
                return None;
            }
        };
        let how = match &outcome.reuse {
            Some(Reuse::Exact { .. }) => "found in the proof cache",
            _ => "proved now and stored in the proof cache",
        };
        let params = crate::classfile::MethodDescriptor::parse(&callee.descriptor).map(|d| d.params.iter().map(Type::java_name).collect::<Vec<_>>().join(", ")).unwrap_or_default();
        let _ = writeln!(self.notes, "note: {name}, changed: its two versions have the same outcome, result or exception, on every input, {how} (claim {}); one function in both versions", key.0);
        self.assumptions.push(Assumption {
            kind: AssumptionKind::Callee,
            text: format!(
                "{name}({params}), changed, is one function in both versions: a regression proof of its own (claim {}) shows its two versions give the same result or throw the same exception on every input of its parameter types, so every call in either version is in that proof's domain",
                key.0
            ),
            basis: Basis::Proved,
            id: Some(key.0.clone()),
        });
        Some(crate::shared::Proved { key: key.0, from: record.provenance })
    }
}

/// Whether a helper's own check is a proof one stub may stand on at every call: verified, over every execution
/// within its bounds, and resting on nothing that narrows its inputs (only the checker's own assumptions, and the
/// proofs of the helpers it shared in turn).
pub fn applicable(outcome: &Outcome) -> Result<(), String> {
    if outcome.verdict != Verdict::Verified {
        let why = outcome.problem.as_deref().map(|p| format!(": {p}")).unwrap_or_default();
        return Err(match outcome.verdict {
            Verdict::Violation => format!("its two versions differ{}", outcome.counterexample.as_ref().map(|c| format!(", at {}", c.input)).unwrap_or_default()),
            _ => format!("its proof gave no verdict{why}"),
        });
    }
    let Some(stated) = &outcome.stated else { return Err("its proof states nothing".into()) };
    if !stated.bounds.complete {
        return Err("its proof did not cover every execution within its bounds".into());
    }
    let narrowing: Vec<&Assumption> = stated.assumptions.iter().filter(|a| !matches!(a.kind, AssumptionKind::Initialization | AssumptionKind::Callee)).collect();
    if let Some(a) = narrowing.first() {
        return Err(format!("its proof rests on an assumption a call would have to be checked against: {}", a.text));
    }
    Ok(())
}

/// The caller's statement once its result is known: the `callee` assumptions of helpers its proof did not end up
/// using (the proof ran again with the callees as written) are dropped, since the result doesn't rest on them.
pub fn keep_used(statement: &mut Statement, callees: &[crate::shared::Callee], used: &[String]) {
    let names = crate::shared::names(callees);
    let unused: Vec<&str> = names.iter().zip(callees).filter(|(n, _)| !used.contains(n)).filter_map(|(_, c)| c.proved.as_ref().map(|p| p.key.as_str())).collect();
    statement.assumptions.retain(|a| !(a.kind == AssumptionKind::Callee && a.id.as_deref().is_some_and(|id| unused.contains(&id))));
}
