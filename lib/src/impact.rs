//! Change impact (`llm-dlc/loops/foundations-summaries.md`, S3): for a set of claims and a change from one build to
//! another, which claims the change invalidates, and why.
//!
//! A claim here is a method a proof was about, as a `build.py` run names it (`target`, with `previousSymbol` or
//! `beforeTarget` when the change renamed it). Its code is what the proof cache's key digests of one version
//! ([`crate::closure::version_digest`]): the closures of its *roots*, the target and the canonical constructor of
//! every record its inputs are made with (the receiver, for an instance method of a record, and each record
//! parameter). The report says, per claim:
//!
//! - **invalidated**: the code differs, with each part of the closures that did ([`PartChange`]): a method's body, a
//!   class's declaration, the set of classes a virtual call may dispatch to, a configuration file, a name the class
//!   path didn't or now does have. A target that is gone from the second build is invalidated too.
//! - **unchanged**: every root's closure is the same, so a cached result for the claim is still hit on its code (the
//!   rest of its key, the tools and the settings, is not the change's to say).
//! - **unresolved**: the claim names no method of the first build (or of either), so it says nothing about this
//!   change.
//!
//! The verdict is the version digest's, the same function the cache key uses, so an unchanged claim's key has the
//! same code part. The reasons are the parts that differ between the union of the roots' closures in each build.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::classfile::{MemberRef, Type};
use crate::classpath::ClassPath;
use crate::closure::{self, Closure, Configuration, PartChange};
use crate::Error;

/// One claim the report is asked about.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Claim {
    /// How the report names it: the claim's id, its example's, or its target.
    pub id: String,
    /// `pkg.Class#method`, or `pkg.Class#method(int, long[])`: the method in the second build.
    pub target: String,
    /// The same method in the first build, when the change renamed or moved it.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub before_target: Option<String>,
}

impl Claim {
    pub fn new(target: &str) -> Claim {
        Claim { id: target.to_string(), target: target.to_string(), before_target: None }
    }

    fn before(&self) -> &str {
        self.before_target.as_deref().unwrap_or(&self.target)
    }
}

/// What the change does to one claim.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case", tag = "status")]
pub enum Verdict {
    Unchanged,
    Invalidated {
        /// The parts that differ, in part order.
        changes: Vec<PartChange>,
        /// Why, when no part says it: the target is gone, or the roots differ.
        #[serde(default, skip_serializing_if = "Option::is_none")]
        reason: Option<String>,
    },
    Unresolved { reason: String },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ClaimImpact {
    #[serde(flatten)]
    pub claim: Claim,
    #[serde(flatten)]
    pub verdict: Verdict,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Report {
    pub claims: Vec<ClaimImpact>,
}

/// The claims a JSON file names: an array of claims, or one, or a report of this command (`claims`). Each is an
/// object with a `target`, at its top or under `statement`, `claim` or `claim.statement` (so `build.py`'s
/// `claim.json`, its `--plan` output and a result with its claim record all serve), with an optional
/// `beforeTarget` or `previousSymbol` beside it, and an optional `id` or `example`.
pub fn claims_from_json(value: &Value) -> Result<Vec<Claim>, Error> {
    let items: Vec<&Value> = match value {
        Value::Array(items) => items.iter().collect(),
        Value::Object(o) => match o.get("claims") {
            Some(Value::Array(items)) => items.iter().collect(),
            _ => vec![value],
        },
        _ => return Err(Error::new("a claims file is a JSON array of claims, or one claim")),
    };
    items.iter().enumerate().map(|(i, item)| claim_from_json(item).ok_or_else(|| Error::new(format!("claim {} names no target", i + 1)))).collect()
}

fn claim_from_json(item: &Value) -> Option<Claim> {
    let text = |v: &Value, key: &str| v.get(key).and_then(Value::as_str).map(str::to_string);
    let places = [Some(item), item.get("statement"), item.get("claim"), item.get("claim").and_then(|c| c.get("statement"))];
    let place = places.into_iter().flatten().find(|p| text(p, "target").is_some())?;
    let target = text(place, "target")?;
    let before_target = text(place, "beforeTarget").or_else(|| text(place, "previousSymbol")).filter(|b| *b != target);
    let id = text(item, "example").or_else(|| text(item, "id")).or_else(|| item.get("claim").and_then(|c| text(c, "example"))).unwrap_or_else(|| target.clone());
    Some(Claim { id, target, before_target })
}

/// The roots of a claim on `target` in the build `cp`: the method, and the canonical constructor of each record its
/// inputs are made with.
pub fn roots(cp: &ClassPath, target: &str) -> Result<Vec<MemberRef>, String> {
    let (class, _) = crate::verifier::parse_target(target).ok_or("a target is <class>#<method>")?;
    let file = cp.application(&class).map_err(|e| e.to_string())?.ok_or_else(|| format!("no class {}", class.replace('/', ".")))?;
    let method = crate::verifier::select_method(&file, target)?;
    let mut roots = vec![MemberRef::new(&class, &method.name, &method.descriptor)];
    let mut inputs = Vec::new();
    if !method.is_static() {
        inputs.push(class.clone());
    }
    for p in method.parsed_descriptor().map_err(|e| e.to_string())?.params {
        if let Type::Object(c) = p {
            inputs.push(c);
        }
    }
    for name in inputs {
        let Ok(Some(record)) = cp.application(&name) else { continue };
        if !record.is_record() {
            continue;
        }
        let components = record.record_components().map_err(|e| e.to_string())?;
        let init = MemberRef::new(&name, "<init>", &format!("({})V", components.iter().map(|c| c.descriptor.as_str()).collect::<String>()));
        if !roots.contains(&init) {
            roots.push(init);
        }
    }
    Ok(roots)
}

/// The report for `claims`, from the build `before` to the build `after`, each with its application files.
pub fn impact(before: &ClassPath, after: &ClassPath, before_configuration: &Configuration, after_configuration: &Configuration, claims: &[Claim]) -> Report {
    let before_roots: Vec<Result<Vec<MemberRef>, String>> = claims.iter().map(|c| roots(before, c.before())).collect();
    let after_roots: Vec<Result<Vec<MemberRef>, String>> = claims.iter().map(|c| roots(after, &c.target)).collect();
    let before_closures = closures_of(before, before_configuration, &before_roots);
    let after_closures = closures_of(after, after_configuration, &after_roots);
    let claims = claims
        .iter()
        .enumerate()
        .map(|(i, claim)| {
            let verdict = match (&before_roots[i], &after_roots[i]) {
                (Err(b), Err(a)) => Verdict::Unresolved { reason: format!("{} is in neither build: {b}; {a}", claim.before()) },
                (Err(b), Ok(_)) => Verdict::Unresolved { reason: format!("{} is not in the first build: {b}", claim.before()) },
                (Ok(_), Err(a)) => Verdict::Invalidated { changes: Vec::new(), reason: Some(format!("{} is gone from the second build: {a}", claim.target)) },
                (Ok(br), Ok(ar)) => compare(&before_closures[i], &after_closures[i], br, ar),
            };
            ClaimImpact { claim: claim.clone(), verdict }
        })
        .collect();
    Report { claims }
}

/// The closures of every claim's roots in one build, in one walk; empty for a claim whose roots didn't resolve.
fn closures_of(cp: &ClassPath, configuration: &Configuration, roots: &[Result<Vec<MemberRef>, String>]) -> Vec<Vec<Closure>> {
    let all: Vec<MemberRef> = roots.iter().flat_map(|r| r.iter().flatten().cloned()).collect();
    let mut computed = closure::closures(cp, &all, configuration).into_iter();
    roots.iter().map(|r| r.as_ref().map_or(Vec::new(), |r| computed.by_ref().take(r.len()).collect())).collect()
}

fn compare(before: &[Closure], after: &[Closure], before_roots: &[MemberRef], after_roots: &[MemberRef]) -> Verdict {
    if closure::digest_of_version(before) == closure::digest_of_version(after) {
        return Verdict::Unchanged;
    }
    let union = |closures: &[Closure]| Closure { root: String::new(), parts: closures.iter().flat_map(|c| c.parts.clone()).collect::<BTreeMap<_, _>>() };
    let changes = union(before).changes(&union(after));
    let reason = changes.is_empty().then(|| {
        let ids = |roots: &[MemberRef]| roots.iter().map(closure::method_id).collect::<Vec<_>>().join(", ");
        format!("the roots differ: {} in the first build, {} in the second", ids(before_roots), ids(after_roots))
    });
    Verdict::Invalidated { changes, reason }
}

impl Report {
    pub fn invalidated(&self) -> usize {
        self.claims.iter().filter(|c| matches!(c.verdict, Verdict::Invalidated { .. })).count()
    }

    /// One line per claim, its changed parts under it, and a count.
    pub fn render(&self) -> String {
        let mut out = String::new();
        let mut counts = [0usize; 3];
        for c in &self.claims {
            let name = if c.claim.id == c.claim.target { c.claim.target.clone() } else { format!("{} ({})", c.claim.id, c.claim.target) };
            let renamed = c.claim.before_target.as_ref().map(|b| format!(", {b} before")).unwrap_or_default();
            match &c.verdict {
                Verdict::Unchanged => {
                    counts[1] += 1;
                    out.push_str(&format!("unchanged    {name}{renamed}\n"));
                }
                Verdict::Invalidated { changes, reason } => {
                    counts[0] += 1;
                    out.push_str(&format!("invalidated  {name}{renamed}\n"));
                    for change in changes {
                        let (how, part) = match change {
                            PartChange::Added { part } => ("added", part),
                            PartChange::Removed { part } => ("removed", part),
                            PartChange::Changed { part } => ("changed", part),
                        };
                        out.push_str(&format!("    {how} {part}\n"));
                    }
                    if let Some(reason) = reason {
                        out.push_str(&format!("    {reason}\n"));
                    }
                }
                Verdict::Unresolved { reason } => {
                    counts[2] += 1;
                    out.push_str(&format!("unresolved   {name}{renamed}: {reason}\n"));
                }
            }
        }
        out.push_str(&format!("{} claims: {} invalidated, {} unchanged, {} unresolved\n", self.claims.len(), counts[0], counts[1], counts[2]));
        out
    }
}
