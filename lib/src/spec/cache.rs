//! The summaries stream's interface (`llm-dlc/loops/foundations-summaries.md`): the claim key, and the proof cache
//! keyed by it. Owned by that stream.
//!
//! **The key** is a projection of a [`CanonicalClaim`], written canonically (object keys sorted, no whitespace) and
//! digested with SHA-256 under a version line ([`PROJECTION`]). The projection knows every field of the claim by its
//! path ([`KNOWN`]); a field it doesn't know makes the claim uncacheable, so that a field another stream adds to the
//! claim can't be silently left out of the key. The typed interfaces of [`super::plans`] a claim carries ([`TYPED`])
//! are digested whole, once they read back as their strict types. A part that was never computed (an empty closure digest or tool
//! identity) makes it uncacheable too. Nothing that depends on the result or the run is in the claim to begin with.
//!
//! **The cache** is a local directory, never committed (decision 3 of `foundations.md`): one JSON file per key,
//! `claims/HH/HEX.json`, holding a [`ResultRecord`] and, beside it, the check's own report of the result for a reuse
//! to give back ([`store_detail`]). Only verified and refuted results are stored, a refuted one with
//! the witness its reuse replays; an unresolved one is never stored. An entry that can't be read, names another key,
//! or holds what is never stored is a miss.

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use super::{CanonicalClaim, Outcome, Part, Unsupported, Verdict};
use crate::digest::sha256_hex;

/// The digest of a [`CanonicalClaim`]: equal exactly when every part that decides the result is equal.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct ClaimKey(pub String);

/// A stored result: its claim's key, the outcome, and where it came from.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ResultRecord {
    pub key: ClaimKey,
    pub outcome: Outcome,
    /// The run that produced it: commit, configuration and time.
    pub provenance: String,
}

/// How a result was reused, when it was.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "kind")]
pub enum Reuse {
    /// The same claim key: the stored result is the result, from the run `from`.
    Exact { key: ClaimKey, from: String },
    /// A callee's proved equivalence used as a shared stub, with that proof's key.
    Callee { callee: String, key: ClaimKey },
}

/// The first line of every digested claim: a change to what the projection covers changes it, so that no key made
/// before such a change can name a claim after it.
pub const PROJECTION: &str = "jvmcontract canonical claim, projection 1";

/// Every field of a claim the projection knows, as a path from the claim's root, `[]` standing for an array's
/// elements. A variant's fields are listed under the field that holds it; its `kind` is digested with them.
pub const KNOWN: &[&str] = &[
    "contract",
    "contract.subject",
    "contract.inputs",
    "contract.inputs[].name",
    "contract.inputs[].type",
    "contract.inputs[].derivation",
    "contract.inputs[].derivation.kind",
    "contract.inputs[].derivation.expression",
    "contract.required",
    "contract.approved_changes",
    "contract.approved_changes[].observation",
    "contract.approved_changes[].text",
    "closures",
    "closures.before",
    "closures.after",
    "domain",
    "domain.classes",
    "domain.bounds",
    "domain.bounds.before",
    "domain.bounds.before.input_objects",
    "domain.bounds.before.allocations",
    "domain.bounds.after",
    "domain.bounds.after.input_objects",
    "domain.bounds.after.allocations",
    "domain.nullable",
    "domain.may_alias",
    "domain.made_by",
    "domain.made_by.kind",
    "domain.made_by.calls",
    "domain.made_by.invariants",
    "domain.label",
    "observations",
    "observations[].kind",
    "observations[].parameter",
    "observations[].path",
    "observations[].left",
    "observations[].right",
    "observations[].call",
    "observations[].payload",
    "correspondence",
    "correspondence.inputs",
    "correspondence.inputs[].old",
    "correspondence.inputs[].new",
    "correspondence.outputs",
    "correspondence.outputs[].observation",
    "correspondence.outputs[].holds",
    "environment",
    "environment.calls",
    "environment.calls[].call",
    "environment.calls[].outcomes",
    "environment.trace_bound",
    "environment.order",
    "bounds",
    "bounds.unwind",
    "bounds.max_array_length",
    "assumptions",
    "tools",
    "tools.models",
    "tools.jdk",
    "tools.checker",
    "tools.binary",
];

/// The parts of a claim that are typed interfaces of [`super::plans`], digested whole: each must read back as its
/// type exactly, and those types refuse every field and variant they don't declare. A field added to one of them is
/// in the digest with the rest of it, never left out; a field the type doesn't declare makes the claim uncacheable.
/// The application-core streams' (`llm-dlc/loops/application-core.md`): a planned domain's plan for each version,
/// its setup sequence included, and a modelled call's model, its results and their bound included.
pub const TYPED: &[(&str, &str)] = &[
    ("domain.made_by.before", "construction plan"),
    ("domain.made_by.after", "construction plan"),
    ("environment.calls[].model", "call model"),
];

/// `v`, read as the typed interface `interface` of [`TYPED`] and written back, or why it doesn't read back exactly.
fn typed(interface: &str, v: &Value) -> Result<(), String> {
    fn exact<T: serde::de::DeserializeOwned + Serialize>(v: &Value) -> Result<(), String> {
        let read: T = serde_json::from_value(v.clone()).map_err(|e| e.to_string())?;
        let back = serde_json::to_value(&read).map_err(|e| e.to_string())?;
        if &back == v { Ok(()) } else { Err("it does not read back as written".into()) }
    }
    match interface {
        "construction plan" => exact::<super::plans::ConstructionPlan>(v),
        "call model" => exact::<super::plans::CallModel>(v),
        other => Err(format!("no typed interface is called {other}")),
    }
}

/// The parts of a claim that are computed from the builds and the tool, which a claim must have before it has a key.
const COMPUTED: &[&str] = &["closures.before", "closures.after", "tools.models", "tools.jdk", "tools.checker", "tools.binary"];

fn uncacheable(why: impl std::fmt::Display) -> Unsupported {
    Unsupported::new(Part::Summaries, format!("the claim is uncacheable: {why}"))
}

/// The claim as the key digests it: every field checked against [`KNOWN`], and every computed part present. The
/// claim's own JSON, since nothing in it is left out; an error names the first field the projection doesn't know.
pub fn projection(claim: &Value) -> Result<Value, Unsupported> {
    fn walk(v: &Value, path: &str) -> Result<(), Unsupported> {
        match v {
            Value::Object(map) => {
                for (k, child) in map {
                    let p = if path.is_empty() { k.clone() } else { format!("{path}.{k}") };
                    if let Some((_, interface)) = TYPED.iter().find(|(path, _)| *path == p) {
                        typed(interface, child).map_err(|e| uncacheable(format!("its {p} is not a {interface} the key's projection knows: {e}")))?;
                        continue;
                    }
                    if !KNOWN.contains(&p.as_str()) {
                        return Err(uncacheable(format!("its field {p} is not one the key's projection knows (lib/src/spec/cache.rs)")));
                    }
                    walk(child, &p)?;
                }
                Ok(())
            }
            Value::Array(items) => items.iter().try_for_each(|item| walk(item, &format!("{path}[]"))),
            _ => Ok(()),
        }
    }
    walk(claim, "")?;
    for path in COMPUTED {
        let mut v = claim;
        for k in path.split('.') {
            v = v.get(k).unwrap_or(&Value::Null);
        }
        if v.as_str().is_none_or(|s| s.trim().is_empty()) {
            return Err(uncacheable(format!("{path} was not computed")));
        }
    }
    Ok(claim.clone())
}

/// `v` written canonically: object keys in byte order, no whitespace, strings and numbers as JSON writes them.
pub fn canonical(v: &Value) -> String {
    fn write(v: &Value, out: &mut String) {
        match v {
            Value::Object(map) => {
                let mut keys: Vec<&String> = map.keys().collect();
                keys.sort();
                out.push('{');
                for (i, k) in keys.into_iter().enumerate() {
                    if i > 0 {
                        out.push(',');
                    }
                    out.push_str(&Value::String(k.clone()).to_string());
                    out.push(':');
                    write(&map[k], out);
                }
                out.push('}');
            }
            Value::Array(items) => {
                out.push('[');
                for (i, item) in items.iter().enumerate() {
                    if i > 0 {
                        out.push(',');
                    }
                    write(item, out);
                }
                out.push(']');
            }
            other => out.push_str(&other.to_string()),
        }
    }
    let mut out = String::new();
    write(v, &mut out);
    out
}

/// The key of a prepared claim: `sha256:` and the digest of [`PROJECTION`] and the claim's canonical form. A part the
/// projection doesn't know, or one not computed, makes the claim uncacheable (an error), never a key that leaves it
/// out.
pub fn key(claim: &CanonicalClaim) -> Result<ClaimKey, Unsupported> {
    let value = serde_json::to_value(claim).map_err(|e| uncacheable(format!("it does not serialize: {e}")))?;
    let projected = projection(&value)?;
    Ok(ClaimKey(format!("sha256:{}", sha256_hex(format!("{PROJECTION}\n{}", canonical(&projected)).as_bytes()))))
}

/// Where the record of `key` is kept under `dir`.
fn entry(dir: &Path, key: &ClaimKey) -> Result<PathBuf, Unsupported> {
    let hex = key.0.strip_prefix("sha256:").filter(|h| h.len() == 64 && h.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)));
    let hex = hex.ok_or_else(|| Unsupported::new(Part::Summaries, format!("not a claim key: {}", key.0)))?;
    Ok(dir.join("claims").join(&hex[..2]).join(format!("{hex}.json")))
}

/// Why a record may not be stored or reused, if it may not: an unresolved result, or a refutation without a witness
/// to replay.
fn unstorable(outcome: &Outcome) -> Option<&'static str> {
    match outcome.verdict {
        Verdict::Unresolved => Some("an unresolved result is never stored"),
        Verdict::Refuted if outcome.witness.as_deref().is_none_or(|w| w.trim().is_empty()) => Some("a refuted result is stored only with the witness its reuse replays"),
        _ => None,
    }
}

/// What a cache file holds: the record, and beside it the check's own report of the result, for a reuse to give
/// back as the command that made it reported it (a regression proof's is [`crate::proof_cache`]'s).
#[derive(Serialize, Deserialize)]
struct Entry {
    #[serde(flatten)]
    record: ResultRecord,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    detail: Option<Value>,
}

/// The stored result for a key, in the cache directory `dir`; none on a miss. An entry that can't be read, is for
/// another key, or holds a result that is never stored is a miss.
pub fn lookup(dir: &Path, key: &ClaimKey) -> Result<Option<ResultRecord>, Unsupported> {
    Ok(lookup_detail(dir, key)?.map(|(record, _)| record))
}

/// [`lookup`], with the report stored beside the record, if any.
pub fn lookup_detail(dir: &Path, key: &ClaimKey) -> Result<Option<(ResultRecord, Option<Value>)>, Unsupported> {
    let path = entry(dir, key)?;
    let Ok(text) = std::fs::read_to_string(&path) else { return Ok(None) };
    let Ok(Entry { record, detail }) = serde_json::from_str::<Entry>(&text) else { return Ok(None) };
    if record.key != *key || unstorable(&record.outcome).is_some() {
        return Ok(None);
    }
    Ok(Some((record, detail)))
}

/// Stores a verified or refuted result; an unresolved one is never stored (an error says so). Written to a
/// temporary file first and renamed, so a reader never sees half a record.
pub fn store(dir: &Path, record: &ResultRecord) -> Result<(), Unsupported> {
    store_detail(dir, record, None)
}

/// [`store`], with the check's own report of the result beside the record.
pub fn store_detail(dir: &Path, record: &ResultRecord, detail: Option<Value>) -> Result<(), Unsupported> {
    if let Some(why) = unstorable(&record.outcome) {
        return Err(Unsupported::new(Part::Summaries, why));
    }
    let path = entry(dir, &record.key)?;
    let failed = |e: std::io::Error| Unsupported::new(Part::Summaries, format!("the cache could not store {}: {e}", path.display()));
    std::fs::create_dir_all(path.parent().expect("an entry is in a folder")).map_err(failed)?;
    let entry = Entry { record: record.clone(), detail };
    let text = serde_json::to_string_pretty(&entry).map_err(|e| Unsupported::new(Part::Summaries, format!("the record does not serialize: {e}")))?;
    let temporary = path.with_extension(format!("tmp-{}", std::process::id()));
    std::fs::write(&temporary, text).map_err(failed)?;
    std::fs::rename(&temporary, &path).map_err(failed)
}

/// The callee evidence a check of `subject` (`pkg.Class#method`) between the classes under `before` and `after` reuses:
/// pure helpers whose own equivalence proof is in the cache under `dir`, shared in both versions (S4).
///
/// It plans `subject`'s check as `equivalence --engine native --cache DIR` does, without running it: each changed pure
/// helper of the narrow kind [`crate::shared`] describes is proved (or found in the cache) as a check of its own, and
/// the ones proved equivalent on every input are the evidence the check would reuse, each named `pkg.Class#method`
/// with its proof's claim key.
pub fn callee_reuse(dir: &Path, subject: &str, before: &Path, after: &Path) -> Result<Vec<Reuse>, Unsupported> {
    let failed = |e: String| Unsupported::new(Part::Summaries, format!("{subject}'s callees could not be planned: {e}"));
    let cp = |dir: &Path| -> Result<crate::classpath::ClassPath, Unsupported> {
        let mut cp = crate::classpath::ClassPath::new();
        cp.add(dir).map_err(|e| failed(e.to_string()))?;
        Ok(cp.with_default_jdk())
    };
    let (before_cp, after_cp) = (cp(before)?, cp(after)?);
    let method = |cp: &crate::classpath::ClassPath| -> Result<crate::classfile::MemberRef, Unsupported> {
        let (class, _) = crate::verifier::parse_target(subject).ok_or_else(|| failed("a subject is <class>#<method>".into()))?;
        let file = cp.application(&class).map_err(|e| failed(e.to_string()))?.ok_or_else(|| failed(format!("no class {class}")))?;
        let m = crate::verifier::select_method(&file, subject).map_err(failed)?;
        Ok(crate::classfile::MemberRef::new(&class, &m.name, &m.descriptor))
    };
    let (before_target, target) = (method(&before_cp)?, method(&after_cp)?);
    let mut options = crate::equivalence::Options::new(before, after, subject);
    options.engine = crate::Engine::Native;
    options.cache = Some(dir.to_path_buf());
    options.timeout_seconds = 120;
    let work = crate::tla::tempfile_path("jvmcontract-callee-reuse");
    let mut helpers = crate::proof_cache::Helpers::new(&options, &work);
    let plan = crate::shared::plan_with(&before_cp, &after_cp, &before_target, &target, true, &mut |c| helpers.prove(c));
    let _ = std::fs::remove_dir_all(&work);
    Ok(plan
        .callees
        .iter()
        .filter_map(|c| c.proved.as_ref().map(|p| Reuse::Callee { callee: format!("{}#{}", c.owner.replace('/', "."), c.name), key: ClaimKey(p.key.clone()) }))
        .collect())
}
