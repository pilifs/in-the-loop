//! The reuse stream's module (`llm-dlc/loops/application-core-reuse.md`): the native property cache (R1), as a
//! projection of the canonical claim into the existing proof store, and summaries of read-only heap helpers
//! ([`Summary`], R2) a changed caller reuses where it discharges their applicability. Registered by Phase 0 of
//! `llm-dlc/loops/application-core.md`, so that the stream starts without editing a shared file.
//!
//! **The property cache** (R1, `prove --cache DIR`) is the regression proofs' store ([`crate::spec::cache`]), not a
//! second one: a property check's claim is a [`CanonicalClaim`] like a regression proof's, keyed by the same digest,
//! and stored in the same directory. `property::run` asks [`property_lookup`] before it prepares anything, and
//! [`property_store`] once it has a verdict. The claim ([`property_claim`]) projects:
//!
//! | Part of the claim | What it holds for a property |
//! |---|---|
//! | `contract` | the target, and its parameters by name and type as the class file has them (a property names them) |
//! | `closures.after` | the code: the closure of the target, of every constructor its object inputs, its result and its declared exceptions are made with, recursively, and of every maker and setup call of a construction plan ([`crate::closure`]); `closures.before` says a property has one version |
//! | `assumptions` | first, that it is a property claim, so that no regression claim can have its key; then the assumption, the assertion, the throws clauses as given, the semantics of `\old`, the choices of null and of one object, and the construction plan, each by name |
//! | `bounds` | the unwinding and array bounds; a plan's own bounds are in its JSON |
//! | `tools` | the binary, the JDK, the models, and the checker with every setting that can change a verdict |
//!
//! The harness is not digested: it is generated before any proof by the binary the key names, from the class files
//! the closure covers and the options the claim names, so that one key has one harness. A stored refutation is
//! stored with that harness, and replayed in it on the classes as they are now before it is used.
//!
//! Every field of [`crate::property::Options`] is named here ([`PROPERTY_OPTIONS`]), as projected or as not changing
//! a verdict; a field this module doesn't know, which another stream added, makes the check refused under `--cache`
//! rather than keyed without it. So does an engine other than the own checker (JBMC's own identity is not in the
//! key), and any part the key refuses. Without `--cache` nothing here runs.
//!
//! What is stored and reused follows the regression cache: a verified result, and a refuted one whose witness,
//! read back as stored, fails the harness in the interpreter; never an unresolved one. A verified hit gives back the
//! stored outcome as it was stated (its domain, bounds, assumptions and evidence), marked as a reuse in its output,
//! its proof line and its `reuse` field; no checker runs. A refuted hit is used only once its witness fails the stored harness again
//! on the current classes; otherwise it is a miss, and the check runs and stores its own result in its place.
//!
//! **Read-only heap helpers** (R2) are summarized from a proof of their own: [`footprint`] establishes a helper's read
//! footprint from its bytecode and lifts it over that footprint, and [`summarize`] proves the two versions' lifted
//! helpers equal and gives the [`Summary`] naming that proof. A changed caller checked under the proof cache and the
//! own checker reuses it ([`application`], through [`crate::proof_cache::Helpers`] and [`crate::shared`]): each call
//! of the helper in both versions goes to an adapter that reads the footprint from the actual receiver at that call
//! and calls the new version's lifted helper. The proof is of the lifted function, positional in the fields' values;
//! which field is which parameter is the summary's `reads`, established again from each version's bytecode whenever a
//! summary is made, so a claim that uses one carries the whole summary, not only its proof's key. A helper may read
//! the primitive arrays its receiver's fields hold, by length and element: the summary's facts bound them, and the
//! adapter keeps the body at a call outside them. [`summaries`], the
//! Phase 0 hook for a caller that asks by name, still offers none: a summary is made for a caller's own two builds.

use std::fmt::Write as _;
use std::path::{Path, PathBuf};
use std::time::Instant;

use serde::{Deserialize, Serialize};

use crate::classfile::{MemberRef, Type};
use crate::classpath::ClassPath;
use crate::digest::sha256_hex;
use crate::proof_cache::{StoredCall, StoredTyped};
use crate::property::{Counterexample, Options, Outcome};
use crate::sarif::Finding;
use crate::spec::cache::{self, ClaimKey, ResultRecord};
use crate::spec::plans::Summary;
use crate::spec::{Accounted, CanonicalClaim, ClaimBounds, Derivation, ExternalInput, Observation, ObservationState, Part, PreservationContract, Unsupported, VersionDigests};
use crate::{harness, witness, Verdict};

/// Every field of [`crate::property::Options`], with what the property claim does with it. A field not here makes a
/// check under `--cache` refused ([`check_fields`]).
pub const PROPERTY_OPTIONS: &[(&str, &str)] = &[
    ("classes", "the code: the closure read from them"),
    ("classpath", "the code: the closure read from them"),
    ("target", "the contract's subject"),
    ("assume", "an assumption of the claim"),
    ("assert", "an assumption of the claim"),
    ("throws", "an assumption of the claim"),
    ("work", "where the check works: no verdict depends on it"),
    ("report", "where findings are written: no verdict depends on it"),
    ("sources", "where findings are anchored: no verdict depends on it"),
    ("base", "where findings are anchored: no verdict depends on it"),
    ("unwind", "a bound of the claim"),
    ("max_array_length", "a bound of the claim"),
    ("shrink", "the checker's settings: it chooses the witness shown"),
    ("timeout_seconds", "only whether a verdict is reached, and an unresolved result is never stored"),
    ("jbmc", "JBMC's: the cache is used with --engine native only"),
    ("java_home", "the checker's settings"),
    ("models", "the tools' models, and the checker's settings"),
    ("refine_strings", "JBMC's: the cache is used with --engine native only"),
    ("sat_solver", "JBMC's: the cache is used with --engine native only, whose solver is the checker's settings"),
    ("jbmc_staging", "JBMC's: the cache is used with --engine native only"),
    ("engine", "the native engine only; the checker's settings"),
    ("gaps", "the checker's settings"),
    ("contracts", "the checker's settings, by the file's digest"),
    ("contract_library", "the checker's settings"),
    ("max_trust", "the checker's settings"),
    ("confirm", "the checker's settings"),
    ("nullable", "an assumption of the claim"),
    ("may_alias", "an assumption of the claim"),
    ("cache", "the store itself: no verdict depends on it"),
    ("plan", "an assumption of the claim: the construction plan, whole"),
];

/// The first assumption of every property claim: no regression claim has it, so the two never share a key.
pub const PROPERTY_CLAIM: &str = "claim: a property of one version (prove), not a regression between two";

/// What `\old` means in a property, as the harness generator gives it: part of the claim, so that a claim stated
/// under another meaning is another claim.
const OLD_STATE: &str = "old state: \\old(e) is e evaluated on the inputs before the call, its arrays and fields copied then";

fn uncacheable(why: impl std::fmt::Display) -> Unsupported {
    Unsupported::new(Part::Summaries, format!("the property claim is uncacheable: {why}"))
}

/// The names of the fields a `{:?}` of a struct gives at its top level: `Options { a: 1, b: [..] }` gives `a`, `b`.
fn top_level_fields(debug: &str) -> Vec<String> {
    let (mut fields, mut depth, mut quote, mut escaped, mut current, mut naming) = (Vec::new(), 0i32, None::<char>, false, String::new(), false);
    for c in debug.chars() {
        if let Some(q) = quote {
            if escaped {
                escaped = false;
            } else if c == '\\' {
                escaped = true;
            } else if c == q {
                quote = None;
            }
            continue;
        }
        match c {
            '"' | '\'' => quote = Some(c),
            '{' | '[' | '(' => {
                depth += 1;
                if depth == 1 {
                    naming = true;
                    current.clear();
                }
            }
            '}' | ']' | ')' => depth -= 1,
            ',' if depth == 1 => {
                naming = true;
                current.clear();
            }
            ':' if depth == 1 && naming => {
                fields.push(current.trim().to_string());
                naming = false;
            }
            _ if depth == 1 && naming => current.push(c),
            _ => {}
        }
    }
    fields
}

/// Refuses a struct whose `{:?}` names a field `known` doesn't: one added after this projection was written.
fn check_fields(debug: &str, known: &[(&str, &str)]) -> Result<(), Unsupported> {
    match top_level_fields(debug).into_iter().find(|f| !known.iter().any(|(k, _)| k == f)) {
        Some(f) => Err(uncacheable(format!("property::Options has a field, {f}, that the property projection doesn't know (lib/src/reuse.rs, PROPERTY_OPTIONS): a field added since must be projected or named as not changing a verdict"))),
        None => Ok(()),
    }
}

/// The class path a property check reads its classes from: its classes and class path, with the JDK.
fn class_path(options: &Options) -> Result<ClassPath, Unsupported> {
    witness::classpath(options.classes.iter().chain(&options.classpath).map(PathBuf::as_path)).map_err(|e| uncacheable(format!("its classes could not be read: {e}")))
}

/// The roots of `class`'s construction, added to `roots`: each of its constructors, and those of every application
/// class a constructor takes or a field holds, in turn. A class the build doesn't have is a root that names it
/// missing, so that adding it later changes the claim.
fn construction_roots(cp: &ClassPath, class: &str, seen: &mut Vec<String>, roots: &mut Vec<MemberRef>) {
    if seen.iter().any(|s| s == class) {
        return;
    }
    seen.push(class.to_string());
    let Ok(Some(file)) = cp.application(class) else {
        roots.push(MemberRef::new(class, "<init>", "()V"));
        return;
    };
    let mut next = Vec::new();
    for m in file.methods.iter().filter(|m| m.name == "<init>") {
        roots.push(MemberRef::new(class, "<init>", &m.descriptor));
        if let Ok(d) = m.parsed_descriptor() {
            next.extend(d.params);
        }
    }
    if !file.methods.iter().any(|m| m.name == "<init>") {
        // No constructor (an interface): its class part is still read, through its initializer or as missing.
        roots.push(MemberRef::new(class, "<clinit>", "()V"));
    }
    for f in file.fields.iter().filter(|f| !f.is_static()) {
        if let Ok(t) = Type::parse(&f.descriptor) {
            next.push(t);
        }
    }
    for t in next {
        if let Some(c) = application_class(cp, &t) {
            construction_roots(cp, &c, seen, roots);
        }
    }
}

/// The application class `t` is, or holds as its elements.
fn application_class(cp: &ClassPath, t: &Type) -> Option<String> {
    match t {
        Type::Object(c) if cp.is_application(c) => Some(c.clone()),
        Type::Array(e) => application_class(cp, e),
        _ => None,
    }
}

/// The class a throws clause's exception names, as the property check resolves it: in full, or by its simple name in
/// `java.lang` or the target's package. Both candidates of a simple name are roots, so that either appearing or
/// going changes the claim.
fn exception_candidates(clause: &str, package: &str) -> Vec<String> {
    let class = clause.split_whitespace().next().unwrap_or("").replace('.', "/");
    if class.contains('/') {
        vec![class]
    } else {
        vec![format!("java/lang/{class}"), format!("{package}{class}")]
    }
}

fn json<T: Serialize>(v: &T) -> String {
    serde_json::to_string(v).unwrap_or_default()
}

/// The canonical claim of the property check `options` describes, under the cache: `Ok(None)` when the check will
/// refuse it itself (no such class or method), so that there is nothing to key; an error when it is uncacheable.
pub fn property_claim(options: &Options) -> Result<Option<CanonicalClaim>, Unsupported> {
    check_fields(&format!("{options:?}"), PROPERTY_OPTIONS)?;
    if options.engine != crate::Engine::Native {
        return Err(uncacheable("JBMC may decide it (--engine jbmc or auto), and JBMC's own identity is not yet part of the key: use the cache with --engine native"));
    }
    let Some((class_internal, _)) = crate::verifier::parse_target(&options.target) else { return Ok(None) };
    let cp = class_path(options)?;
    let Ok(Some(class)) = cp.application(&class_internal) else { return Ok(None) };
    let Ok(method) = crate::verifier::select_method(&class, &options.target) else { return Ok(None) };
    let Ok(descriptor) = method.parsed_descriptor() else { return Ok(None) };

    // The inputs, as the property names them.
    let mut inputs = Vec::new();
    if !method.is_static() {
        inputs.push(ExternalInput { name: "this".into(), ty: class_internal.replace('/', "."), derivation: Derivation::Identity });
    }
    for (name, t) in method.parameter_names(&class.pool).iter().zip(&descriptor.params) {
        inputs.push(ExternalInput { name: name.clone(), ty: t.java_name(), derivation: Derivation::Identity });
    }

    // The code: the target, and everything its inputs, its result and its exceptions are made of.
    let mut roots = vec![MemberRef::new(&class_internal, &method.name, &method.descriptor)];
    let mut seen = Vec::new();
    let mut made = descriptor.params.clone();
    made.push(descriptor.ret.clone());
    if !method.is_static() {
        made.push(Type::Object(class_internal.clone()));
    }
    for t in &made {
        if let Some(c) = application_class(&cp, t) {
            construction_roots(&cp, &c, &mut seen, &mut roots);
        }
    }
    let package = class_internal.rsplit_once('/').map(|(p, _)| format!("{p}/")).unwrap_or_default();
    for clause in &options.throws {
        for c in exception_candidates(clause, &package) {
            if cp.is_application(&c) || !cp.exists(&c) {
                construction_roots(&cp, &c, &mut seen, &mut roots);
            }
        }
    }
    if let Some(plans) = &options.plan {
        for node in &plans.after.nodes {
            let owner = node.class.replace('.', "/");
            match &node.maker {
                crate::spec::plans::Maker::Constructor { descriptor } => roots.push(MemberRef::new(&owner, "<init>", descriptor)),
                crate::spec::plans::Maker::Factory { method } => {
                    let (name, desc) = method.split_once('(').map(|(n, d)| (n.to_string(), format!("({d}"))).unwrap_or((method.clone(), String::new()));
                    roots.push(MemberRef::new(&owner, &name, &desc));
                }
            }
            construction_roots(&cp, &owner, &mut seen, &mut roots);
        }
        for call in &plans.after.setup {
            let (name, desc) = call.method.split_once('(').map(|(n, d)| (n.to_string(), format!("({d}"))).unwrap_or((call.method.clone(), String::new()));
            roots.push(MemberRef::new(&class_internal, &name, &desc));
        }
    }
    let configuration = crate::closure::Configuration::read(&cp, &[]).map_err(|e| uncacheable(format!("its configuration could not be read: {e}")))?;
    let closures = VersionDigests { before: "none: a property claim is about one version".into(), after: crate::closure::version_digest(&cp, &roots, &configuration) };

    let observations = vec![Observation::Result, Observation::Exception];
    let contract = PreservationContract { subject: options.target.clone(), inputs, required: observations.iter().map(Observation::id).collect(), approved_changes: Vec::new() };
    let assumptions = vec![
        PROPERTY_CLAIM.to_string(),
        format!("assume: {}", json(&options.assume)),
        format!("assert: {}", json(&options.assert)),
        format!("throws: {}", json(&options.throws)),
        OLD_STATE.to_string(),
        format!("nullable: {}", json(&options.nullable)),
        format!("may alias: {}", json(&options.may_alias)),
        format!("construction plan: {}", options.plan.as_ref().map(json).unwrap_or_else(|| "none: parameters made as the check makes them".into())),
    ];
    let contracts = match &options.contracts {
        Some(p) => format!("sha256:{}", sha256_hex(&std::fs::read(p).map_err(|e| uncacheable(format!("its contracts {} could not be read: {e}", p.display())))?)),
        None => "none".into(),
    };
    let checker = format!(
        "engine native; property; gaps {}; contracts {contracts}; contract library {}; max trust {}; solver {}; shrink {}; confirm {}; java home {}",
        options.gaps.name(),
        if options.contract_library { "on" } else { "off" },
        options.max_trust.map(|n| n.to_string()).unwrap_or_else(|| "any".into()),
        json(&crate::statement::native_sat()),
        if options.shrink { "on" } else { "off" },
        if options.confirm { "on" } else { "off" },
        options.java_home.as_ref().map(|h| h.display().to_string()).unwrap_or_else(|| "found".into()),
    );
    Ok(Some(CanonicalClaim {
        contract,
        closures,
        domain: None,
        observations,
        correspondence: None,
        environment: None,
        bounds: ClaimBounds { unwind: options.unwind, max_array_length: options.max_array_length },
        assumptions,
        tools: crate::proof_cache::tools(options.models, &checker),
    }))
}

/// The key of the property check `options` describes, if it has one: [`property_claim`]'s, digested.
pub fn property_key(options: &Options) -> Result<Option<ClaimKey>, Unsupported> {
    property_claim(options)?.map(|c| cache::key(&c)).transpose()
}

/// What is stored beside a property check's record, for a reuse to give the outcome back as the check reported it,
/// with the harness a stored witness is replayed in.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct PropertyStored {
    output: String,
    domain: Option<String>,
    assert: Option<String>,
    throws_checked: Vec<String>,
    proof: Option<String>,
    #[serde(default)]
    vacuous: Option<String>,
    statement: crate::statement::Statement,
    /// The statement's gap mode, by name: its type doesn't deserialize.
    #[serde(default)]
    gap_mode: Option<String>,
    findings: Vec<crate::proof_cache::StoredFinding>,
    #[serde(default)]
    counterexample: Option<StoredPropertyCounterexample>,
    /// The harness class, in hex, and its source.
    harness: String,
    harness_source: String,
}

/// A property [`Counterexample`] as stored.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct StoredPropertyCounterexample {
    input: String,
    outcome: String,
    #[serde(default)]
    expected: Option<String>,
    values: Vec<String>,
    #[serde(default)]
    found: Option<String>,
    shrink_runs: u32,
    inputs: Vec<StoredTyped>,
    #[serde(default)]
    found_inputs: Option<Vec<StoredTyped>>,
    call: StoredCall,
}

impl StoredPropertyCounterexample {
    fn of(c: &Counterexample) -> Option<StoredPropertyCounterexample> {
        let typed = |t: &[witness::Typed]| serde_json::to_value(t).ok().and_then(|v| serde_json::from_value::<Vec<StoredTyped>>(v).ok());
        Some(StoredPropertyCounterexample {
            input: c.input.clone(),
            outcome: c.outcome.clone(),
            expected: c.expected.clone(),
            values: c.values.clone(),
            found: c.found.clone(),
            shrink_runs: c.shrink_runs,
            inputs: typed(&c.inputs)?,
            found_inputs: match &c.found_inputs {
                Some(f) => Some(typed(f)?),
                None => None,
            },
            call: serde_json::to_value(&c.call).ok().and_then(|v| serde_json::from_value(v).ok())?,
        })
    }

    fn counterexample(self) -> Counterexample {
        Counterexample {
            input: self.input,
            outcome: self.outcome,
            expected: self.expected,
            values: self.values,
            found: self.found,
            shrink_runs: self.shrink_runs,
            inputs: self.inputs.into_iter().map(Into::into).collect(),
            found_inputs: self.found_inputs.map(|f| f.into_iter().map(Into::into).collect()),
            call: self.call.into(),
        }
    }
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().fold(String::with_capacity(bytes.len() * 2), |mut s, b| {
        let _ = write!(s, "{b:02x}");
        s
    })
}

fn unhex(text: &str) -> Option<Vec<u8>> {
    (text.len() % 2 == 0).then_some(())?;
    (0..text.len()).step_by(2).map(|i| u8::from_str_radix(text.get(i..i + 2)?, 16).ok()).collect()
}

/// The parameters of the harness class `bytes`'s check method: what a witness gives values for.
fn harness_types(bytes: &[u8]) -> Option<Vec<Type>> {
    let file = crate::classfile::ClassFile::parse(bytes).ok()?;
    let m = file.methods.iter().find(|m| m.name == harness::METHOD)?;
    m.parsed_descriptor().ok().map(|d| d.params)
}

/// Whether the stored witness `inputs` fails the property harness in `harness_dir`, run in the interpreter on the
/// classes `options` names as they are now.
fn fails_in_harness(options: &Options, harness_dir: &Path, bytes: &[u8], inputs: &str) -> bool {
    let Some(types) = harness_types(bytes) else { return false };
    let Some(arguments) = crate::proof_cache::witness_arguments(&types, inputs) else { return false };
    let Ok(cp) = witness::classpath(std::iter::once(harness_dir).chain(options.classes.iter().chain(&options.classpath).map(PathBuf::as_path))) else { return false };
    witness::fails_in_harness(&cp.with_models(options.models), harness::PROPERTY_CLASS, &types, &arguments) == Some(true)
}

/// The proof store's result for a property check, under `--cache` of `prove`: `Ok(None)` for a miss, after which
/// the check runs and [`property_store`] stores what it found. Called by `property::run` before its proof. A claim
/// the key can't be made for refuses the check, by name, rather than run it as if uncached.
pub fn property_lookup(options: &Options) -> Result<Option<Outcome>, Unsupported> {
    let Some(dir) = &options.cache else { return Ok(None) };
    let started = Instant::now();
    let Some(key) = property_key(options)? else { return Ok(None) };
    let keyed = started.elapsed();
    let Some((record, detail)) = cache::lookup_detail(dir, &key)? else { return Ok(None) };
    let Some(stored) = detail.and_then(|d| serde_json::from_value::<PropertyStored>(d).ok()) else { return Ok(None) };
    let Some(bytes) = unhex(&stored.harness) else { return Ok(None) };
    let work = options.work.clone().unwrap_or_else(|| crate::tla::tempfile_path("jvmcontract-property"));
    let harness_dir = work.join("harness");
    let written = std::fs::create_dir_all(&harness_dir)
        .and_then(|_| std::fs::write(harness_dir.join(format!("{}.class", harness::PROPERTY_CLASS)), &bytes))
        .and_then(|_| std::fs::write(harness_dir.join(format!("{}.java", harness::PROPERTY_CLASS)), &stored.harness_source));
    if written.is_err() {
        return Ok(None);
    }
    let (verdict, counterexample, replay, how) = match record.outcome.verdict {
        crate::spec::Verdict::Verified => (Verdict::Verified, None, None, "nothing was proved again"),
        crate::spec::Verdict::Refuted => {
            let reproduces = record.outcome.witness.as_deref().is_some_and(|w| fails_in_harness(options, &harness_dir, &bytes, w));
            let Some(c) = stored.counterexample.clone().filter(|_| reproduces) else { return Ok(None) };
            (Verdict::Violation, Some(c.counterexample()), Some(crate::equivalence::Replay { by: "interpreter".into(), reproduced: true }), "its witness failed the stored harness again on the classes as they are now, in the interpreter")
        }
        crate::spec::Verdict::Unresolved => return Ok(None),
    };
    // Where findings are anchored is the check's own today, not the stored run's.
    let (uri, line) = anchor(options);
    let findings: Vec<Finding> = stored.findings.iter().map(|f| Finding::new(&f.rule_id, f.message.clone(), uri.clone(), line)).collect();
    if let Some(report) = &options.report {
        crate::sarif::write(&report.join("property.sarif"), &findings).map_err(|e| Unsupported::new(Part::Reuse, format!("the reused findings could not be written: {e}")))?;
    }
    let mut statement = stored.statement;
    statement.gap_mode = stored.gap_mode.as_deref().and_then(|g| g.parse().ok());
    let mut output = stored.output;
    let _ = writeln!(output, "note: reused from the proof cache: an exact hit of property claim {}, the result of {}; {how}", key.0, record.provenance);
    let _ = writeln!(output, "note: the proof cache took {:.3} s to compute this claim's key (its closure and the tools') and {:.3} s in all", keyed.as_secs_f64(), started.elapsed().as_secs_f64());
    Ok(Some(Outcome {
        verdict,
        target: options.target.clone(),
        domain: stored.domain,
        assume: options.assume.clone(),
        assert: stored.assert,
        throws: options.throws.clone(),
        throws_checked: stored.throws_checked,
        counterexample,
        proof: stored.proof.map(|p| format!("reused from the proof cache (property claim {}, {}): {p}", key.0, record.provenance)),
        problem: None,
        statement: Some(harness_dir.join(format!("{}.java", harness::PROPERTY_CLASS))),
        findings,
        output,
        work,
        vacuous: stored.vacuous,
        search: None,
        replay,
        stated: Some(statement),
        advice: None,
        refused: None,
        reuse: Some(cache::Reuse::Exact { key: key.clone(), from: record.provenance.clone() }),
    }))
}

/// Where the check anchors its findings: the target's source file, if found, and its method's first line.
fn anchor(options: &Options) -> (Option<String>, u32) {
    let Some((class_internal, _)) = crate::verifier::parse_target(&options.target) else { return (None, 1) };
    let uri = crate::sarif::source_file(&class_internal, &options.sources).map(|f| crate::sarif::relative_uri(&options.base, &f));
    let line = class_path(options).ok().and_then(|cp| cp.application(&class_internal).ok().flatten()).and_then(|c| crate::verifier::select_method(&c, &options.target).ok().and_then(|m| m.first_line())).map(u32::from).unwrap_or(1);
    (uri, line)
}

/// Stores a property check's verified or refuted result under its claim key. Called by `property::run` after its
/// proof, under `--cache`, only once [`property_lookup`] has missed. A refutation is stored only when its witness,
/// read back as stored, fails the check's own harness in the interpreter. A failure to store never changes the
/// verdict: a note in the outcome's output says why it wasn't stored, as the regression cache's does.
pub fn property_store(options: &Options, outcome: &mut Outcome) -> Result<(), Unsupported> {
    let Some(dir) = &options.cache else { return Ok(()) };
    if let Err(why) = store(dir, options, outcome) {
        let _ = writeln!(outcome.output, "note: the property result is not stored in the proof cache: {why}");
    }
    Ok(())
}

fn store(dir: &Path, options: &Options, outcome: &Outcome) -> Result<(), String> {
    let verdict = match outcome.verdict {
        Verdict::Verified => crate::spec::Verdict::Verified,
        Verdict::Violation => crate::spec::Verdict::Refuted,
        Verdict::Unverifiable => return Err("an unresolved result is never stored".into()),
    };
    if outcome.advice.is_some() {
        return Err("a run that stopped for advice is never stored".into());
    }
    let key = property_key(options).map_err(|u| u.what)?.ok_or("the claim has no key")?;
    let stated = outcome.stated.clone().ok_or("the outcome states nothing")?;
    let harness_dir = outcome.work.join("harness");
    let bytes = std::fs::read(harness_dir.join(format!("{}.class", harness::PROPERTY_CLASS))).map_err(|e| format!("its harness could not be read: {e}"))?;
    let source = std::fs::read_to_string(harness_dir.join(format!("{}.java", harness::PROPERTY_CLASS))).unwrap_or_default();
    let counterexample = match &outcome.counterexample {
        Some(c) => Some(StoredPropertyCounterexample::of(c).ok_or("its counterexample does not read back")?),
        None => None,
    };
    let witness = match verdict {
        crate::spec::Verdict::Refuted => {
            let c = counterexample.as_ref().ok_or("a refutation has no counterexample")?;
            let inputs = json(&c.inputs);
            if !fails_in_harness(options, &harness_dir, &bytes, &inputs) {
                return Err("its witness, read back as stored, does not fail the harness in the interpreter".into());
            }
            Some(inputs)
        }
        _ => None,
    };
    let stored = PropertyStored {
        output: outcome.output.clone(),
        domain: outcome.domain.clone(),
        assert: outcome.assert.clone(),
        throws_checked: outcome.throws_checked.clone(),
        proof: outcome.proof.clone(),
        vacuous: outcome.vacuous.clone(),
        gap_mode: stated.gap_mode.map(|g| g.name().to_string()),
        statement: stated,
        findings: outcome.findings.iter().map(|f| crate::proof_cache::StoredFinding { rule_id: f.rule_id.clone(), message: f.message.clone() }).collect(),
        counterexample,
        harness: hex(&bytes),
        harness_source: source,
    };
    let detail = serde_json::to_value(&stored).ok().filter(|v| serde_json::from_value::<PropertyStored>(v.clone()).is_ok()).ok_or("its report does not read back")?;
    let state = if verdict == crate::spec::Verdict::Verified { ObservationState::Preserved } else { ObservationState::Refuted };
    let record = ResultRecord {
        key,
        outcome: crate::spec::Outcome {
            verdict,
            domain: outcome.domain.clone().unwrap_or_default(),
            accounting: [Observation::Result, Observation::Exception].iter().map(|o| Accounted { observation: o.id(), state }).collect(),
            witness,
            problem: None,
        },
        provenance: format!("jvmcontract {} ({}), prove --engine native, at {}, on {}", env!("CARGO_PKG_VERSION"), crate::proof_cache::binary().get(..19).unwrap_or("unknown binary"), crate::proof_cache::utc_now(), options.classes.iter().map(|c| c.display().to_string()).collect::<Vec<_>>().join(", ")),
    };
    cache::store_detail(dir, &record, Some(detail)).map_err(|u| u.what)
}

pub mod footprint;
pub mod preparation;

/// R2: the summary of the read-only helper `helper` (an instance method, as a call names it, declared by the same
/// class in both versions of `options`), from a proof of its own: each version's footprint is established
/// ([`footprint::footprint`]), both are lifted over the fields either reads ([`footprint::lift`]), and the two lifted
/// helpers are proved to have the same result on every input under `options`' cache, engine, bounds and tools
/// ([`crate::proof_cache::lifted_proof`]), worked on under `work`. The summary names that proof's claim key, the
/// fields and arguments it reads, the proofs it rests on, and the domain it holds over: every value of those fields
/// and arguments, on any receiver of the class, whatever else it holds. Of primitive fields it needs no alias or null
/// fact: only the receiver is dereferenced, and a call on `null` throws before the helper runs. An array field's value
/// is its length and elements, and the proof's harness makes every array of at most the claim's array bound and no
/// `null` one, so the summary's `facts` say so (`this.tiers != null`, `this.tiers.length <= 8`). No alias fact is
/// needed of arrays either: the helper writes none, so whether two of them are one array changes nothing it reads.
///
/// Refused, by name: a helper either version doesn't establish a footprint for; a field one version reads that the
/// other's receiver doesn't declare alike (a change of layout, for which no representation adapter is established);
/// and a lifted proof that isn't a verified one in the cache, a refutation included (the summary is then not there,
/// and a caller keeps the helper's body).
pub fn summarize(options: &crate::equivalence::Options, helper: &MemberRef, work: &Path) -> Result<Summary, Unsupported> {
    summarized(options, helper, work).map(|s| s.summary)
}

/// What [`summarized`] establishes besides the summary: what a caller needs to apply it.
struct Summarized {
    summary: Summary,
    /// The cache record's provenance of the summary's proof, and whether that proof was an exact hit of the cache.
    from: String,
    found: bool,
    /// The new version's footprint, and the fields both versions' lifted helpers take.
    after: footprint::Footprint,
    /// Whether the previous version's helper is private.
    before_private: bool,
    fields: Vec<footprint::FieldRead>,
    lifted: footprint::Lifted,
}

fn summarized(options: &crate::equivalence::Options, helper: &MemberRef, work: &Path) -> Result<Summarized, Unsupported> {
    let refuse = |why: String| Unsupported::new(Part::Reuse, format!("{} has no read-only summary: {why}", footprint::helper_name(helper)));
    let class_path = |dir: &Path| -> Result<ClassPath, Unsupported> {
        let mut cp = ClassPath::new();
        cp.add(dir).map_err(|e| refuse(e.to_string()))?;
        for entry in options.classpath.iter().filter(|e| e.exists()) {
            cp.add(entry).map_err(|e| refuse(e.to_string()))?;
        }
        Ok(cp.with_default_jdk())
    };
    let (before_cp, after_cp) = (class_path(&options.before)?, class_path(&options.after)?);
    let before = footprint::footprint(&before_cp, helper)?;
    let after = footprint::footprint(&after_cp, helper)?;
    if before.helper != after.helper {
        return Err(refuse(format!("{} declares it before, {} after", before.helper.owner.replace('/', "."), after.helper.owner.replace('/', "."))));
    }
    let mut fields = before.fields.clone();
    fields.extend(after.fields.iter().filter(|f| !before.fields.contains(f)).cloned());
    fields.sort();
    for (version, cp) in [("before", &before_cp), ("after", &after_cp)] {
        for f in &fields {
            let instance = cp.resolve_field(&after.helper.owner, &f.name, &f.descriptor).filter(|d| *d == f.declared_by).and_then(|d| cp.load(&d).ok().flatten()).is_some_and(|l| l.class.fields.iter().any(|g| g.name == f.name && g.descriptor == f.descriptor && !g.is_static()));
            if !instance {
                return Err(refuse(format!(
                    "the version {version}'s receiver has no instance field {}.{} of type {} for the other version's read: its layout changed, and no representation adapter is established",
                    f.declared_by.replace('/', "."),
                    f.name,
                    f.ty().java_name()
                )));
            }
        }
    }
    let lifted_before = footprint::lift(&before_cp, &before, &fields)?;
    let lifted_after = footprint::lift(&after_cp, &after, &fields)?;
    let dir = work.join(format!("summary-{}-{}", helper.owner.replace('/', "."), helper.name));
    let _ = std::fs::remove_dir_all(&dir);
    for (from, to, lifted) in [(&options.before, dir.join("before"), &lifted_before), (&options.after, dir.join("after"), &lifted_after)] {
        copy_tree(from, &to).and_then(|_| {
            let file = to.join(format!("{}.class", lifted.method.owner));
            std::fs::create_dir_all(file.parent().expect("a class file has a directory"))?;
            std::fs::write(file, &lifted.bytes)
        })
        .map_err(|e| refuse(format!("its lifted classes can't be written: {e}")))?;
    }
    let (key, outcome, from) = crate::proof_cache::lifted_proof(options, &lifted_after.target(), &dir.join("before"), &dir.join("after"), &dir.join("proof")).map_err(&refuse)?;
    let depends_on = outcome.stated.iter().flat_map(|s| &s.assumptions).filter(|a| a.kind == crate::statement::AssumptionKind::Callee).filter_map(|a| a.id.clone()).collect();
    let read = |fp: &footprint::Footprint| fp.fields.iter().map(|f| f.name.as_str()).collect::<Vec<_>>().join(", ");
    let arrays: Vec<&footprint::FieldRead> = fields.iter().filter(|f| f.is_array()).collect();
    let summary = Summary {
        helper: footprint::helper_name(&after.helper),
        proof: key.0,
        reads: footprint::Footprint::reads(&fields, &after.params),
        facts: arrays.iter().flat_map(|f| [format!("this.{} != null", f.name), format!("this.{}.length <= {}", f.name, options.max_array_length)]).collect(),
        domain: format!(
            "every value of the fields it reads ({}) and of its arguments, on any receiver of {} whatever else it holds{}; read before: {}; read after: {}",
            if fields.is_empty() { "none".to_string() } else { fields.iter().map(|f| format!("this.{}", f.name)).collect::<Vec<_>>().join(", ") },
            after.helper.owner.replace('/', "."),
            if arrays.is_empty() {
                String::new()
            } else {
                format!(
                    ", an array field's value being its length and elements, for every array of at most {} elements (its facts): a call where one is null or longer keeps the helper's body",
                    options.max_array_length
                )
            },
            if before.fields.is_empty() { "no field".to_string() } else { read(&before) },
            if after.fields.is_empty() { "no field".to_string() } else { read(&after) },
        ),
        bounds: ClaimBounds { unwind: options.unwind, max_array_length: options.max_array_length },
        relation: crate::spec::plans::OutcomeRelation::Equal {},
        effects: crate::spec::plans::Effects::ReadOnly {},
        depends_on,
    };
    let found = matches!(outcome.reuse, Some(cache::Reuse::Exact { .. }));
    Ok(Summarized { summary, from, found, before_private: before.private, after, fields, lifted: lifted_after })
}

/// A helper's summary as a changed caller applies it at its calls (R2), under the tool's own checker: each call of
/// the helper, in either version, becomes a call of that version's adapter ([`footprint::adapters`]), which reads
/// the footprint's fields from the actual receiver at that call and calls the new version's lifted helper. Both
/// versions so call one function of the same values, which the checker's hashing makes one circuit per arguments,
/// as it does for a pure helper proved equivalent ([`crate::shared`]).
///
/// **Why a call is in the summary's domain.** The summary's proof shows the two versions' lifted helpers equal on
/// every value of the fields and arguments, so it needs nothing of a call beyond those values: no precondition, no
/// alias fact, and no state a constructor made. Its `facts`, an array field's being an array within the bound, are
/// checked by the adapter at each call on the receiver it has, and a call where one fails runs its version's helper
/// as written instead: outside its domain, the summary is not applied, and the body stays. The adapter reads them from the receiver
/// the call has, after whatever the caller did to it, and the footprint ([`footprint::footprint`], established again
/// for both versions here) shows they are all the helper reads. The previous version's adapter reads its own
/// version's layout, field by field, and passes the values on: the representation adapter is explicit, never a
/// method of the old layout redirected to code of the new.
#[derive(Debug, Clone)]
pub struct Application {
    pub summary: Summary,
    /// The cache record's provenance of the summary's proof, and whether that proof was an exact hit of the cache.
    pub from: String,
    pub found: bool,
    /// The helper as the new version declares it.
    pub helper: MemberRef,
    /// The new version's classes, whose calls of the helper go to its adapter.
    pub after: PathBuf,
    pub adapters: footprint::Adapters,
    /// The classes a check with it needs, by internal name: the lifted helper and the adapters.
    pub classes: Vec<(String, Vec<u8>)>,
}

thread_local! {
    /// The summaries checks on this thread made applications of, latest last, by their proofs' claim keys:
    /// how [`crate::shared::substitute`] finds what a helper the plan shares by a summary needs.
    static APPLIED: std::cell::RefCell<Vec<Application>> = const { std::cell::RefCell::new(Vec::new()) };
}

/// [`summarize`], with what a caller of `helper` under `options` needs to apply the summary at its calls; the
/// application is kept for [`applied`].
pub fn application(options: &crate::equivalence::Options, helper: &MemberRef, work: &Path) -> Result<Application, Unsupported> {
    let s = summarized(options, helper, work)?;
    let adapters = footprint::adapters(&s.after.helper, &s.after.params, &s.after.result, &s.fields, &s.lifted.method, "before", options.max_array_length, (s.before_private, s.after.private))?;
    let application = Application {
        classes: vec![(s.lifted.method.owner.clone(), s.lifted.bytes.clone()), (adapters.before.owner.clone(), adapters.before_bytes.clone()), (adapters.after.owner.clone(), adapters.after_bytes.clone())],
        summary: s.summary,
        from: s.from,
        found: s.found,
        helper: s.after.helper,
        after: options.after.clone(),
        adapters,
    };
    APPLIED.with(|a| a.borrow_mut().push(application.clone()));
    Ok(application)
}

/// The latest application made on this thread of the summary whose proof's claim key is `key`, for `helper` as the
/// new version declares it.
pub fn applied(key: &str, helper: &MemberRef) -> Option<Application> {
    APPLIED.with(|a| a.borrow().iter().rev().find(|x| x.summary.proof == key && x.helper == *helper).cloned())
}

/// Copies the files under `from` into `to`, keeping their paths.
fn copy_tree(from: &Path, to: &Path) -> std::io::Result<()> {
    std::fs::create_dir_all(to)?;
    for entry in std::fs::read_dir(from)? {
        let entry = entry?;
        let target = to.join(entry.file_name());
        if entry.file_type()?.is_dir() {
            copy_tree(&entry.path(), &target)?;
        } else {
            std::fs::copy(entry.path(), target)?;
        }
    }
    Ok(())
}

/// The summaries of `helper` (`pkg.Class#name(descriptor)`) a caller may apply, each still to be discharged at the
/// call site on the actual pre-call state. None until the stream builds them: a caller keeps the helper's body.
pub fn summaries(helper: &str) -> Vec<Summary> {
    let _ = helper;
    Vec::new()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn no_summary_is_offered_until_the_stream_builds_them() {
        assert!(summaries("shop.Pricing#fee(I)J").is_empty());
    }

    #[test]
    fn every_field_of_the_property_options_is_named_by_the_projection() {
        let options = Options::new(&[PathBuf::from("classes")], "shop.Pricing#fee");
        let fields = top_level_fields(&format!("{options:?}"));
        assert_eq!(fields.len(), PROPERTY_OPTIONS.len(), "{fields:?}");
        check_fields(&format!("{options:?}"), PROPERTY_OPTIONS).unwrap();
    }

    #[test]
    fn a_field_the_projection_does_not_know_makes_the_claim_uncacheable() {
        #[derive(Debug)]
        #[allow(dead_code)]
        struct Wider {
            target: String,
            receiver_history: Vec<(u32, String)>,
        }
        let debug = format!("{:?}", Wider { target: "a, b: {c}".into(), receiver_history: vec![(1, "x: y".into())] });
        assert_eq!(top_level_fields(&debug), ["target", "receiver_history"]);
        let refused = check_fields(&debug, PROPERTY_OPTIONS).unwrap_err();
        assert_eq!(refused.part, Part::Summaries);
        assert!(refused.what.contains("receiver_history"), "{refused}");
    }

    #[test]
    fn a_property_claim_needs_the_native_engine() {
        let mut options = Options::new(&[PathBuf::from("classes")], "shop.Pricing#fee");
        options.cache = Some(PathBuf::from("cache"));
        let refused = property_lookup(&options).unwrap_err();
        assert!(refused.what.contains("--engine native"), "{refused}");
    }

    #[test]
    fn hex_round_trips() {
        let bytes = [0u8, 1, 0xca, 0xfe, 0xff];
        assert_eq!(unhex(&hex(&bytes)).unwrap(), bytes);
        assert!(unhex("abc").is_none() && unhex("zz").is_none());
    }
}
