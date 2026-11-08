//! `jvmcontract compare`: two builds of an application, compared as the foundations loop's joint run does it
//! (`llm-dlc/loops/foundations.md`, Phase 5), with nothing written by hand.
//!
//! 1. **The entry points.** Each build's observation spec ([`crate::spec::observe::entry_points`]), the two compared
//!    into obligations that account for every old observation ([`crate::spec::observe::compare`]), and each old entry
//!    point with a counterpart checked under the claim its own spec makes, effects included
//!    ([`crate::effects::check_builds`]). The external inputs are anchored by the specs: no mapping is involved.
//! 2. **The kernel.** Every changed method pair alignment matches ([`crate::alignment::align`]), the entry points'
//!    handlers apart, checked by the heap engine ([`crate::spec::heap::check_with`]) under the correspondence
//!    alignment proposes for it and the contract its two signatures imply, with the identity relations a Java API
//!    returning one of its object parameters is held to. Its inputs are made by their constructors, or by the domain a
//!    person declares for the subject (`compare --domains`, [`Options::domains`]): a construction plan with its setup
//!    calls, say, passed to the check as it is, its label and bounds included. A subject with several proposals, or one a person must
//!    decide, is not checked: it is a question. The proposal's evidence is the proof's, under its claim key; its intent
//!    stays proposed, and a standalone method's proved relation is not an approved refactor.
//! 3. **Reuse.** With a cache directory, every proof runs under the proof cache: an unchanged rerun is an exact hit,
//!    the entry points' effect-trace proofs ([`crate::effects::check_with`], keyed on the rewritten builds, recording
//!    stubs included) as the kernel's checks, and a changed pure helper is proved once and taken as one function in
//!    its callers.
//! 4. **Effort.** Every decision a person made, by category, and every question the run leaves for one. The inputs of
//!    a person's this run takes are a declared environment (`compare --environment`), each modelled call in it an
//!    environment assumption a person made, and the declared domains (`compare --domains`), each a domain restriction
//!    a person made. What it asks, it lists.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use serde::Serialize;

use crate::alignment::{self, Build};
use crate::effects::EntryCheck;
use crate::spec::cache::Reuse;
use crate::spec::observe::{Change, Obligation};
use crate::spec::{
    heap, CanonicalClaim, ClaimBounds, Correspondence, Evidence, Hint, HintContent, ObjectDomain, Observation, Outcome, Part, ToolIdentity, Unsupported,
    Verdict, VersionDigests,
};

/// What `compare` takes.
#[derive(Debug, Clone)]
pub struct Options {
    pub before: PathBuf,
    pub after: PathBuf,
    /// The proof cache's directory, for every proof: the entry points' effect traces and the kernel's checks; none
    /// runs them without it.
    pub cache: Option<PathBuf>,
    pub bounds: ClaimBounds,
    /// The modelled calls a person declares (`compare --environment`), each with its model
    /// ([`crate::environment::declared`]): every entry point's effect check takes them in place of its spec's calls,
    /// and each counts as one of the person's environment assumptions in the effort report.
    pub environment: Vec<crate::spec::ModeledCall>,
    /// The domains a person declares, by kernel subject (the new method, `pkg.Class#method`, as the report names it;
    /// `compare --domains`, [`load_domains`]): the subject's claim has that domain in place of the constructor domain,
    /// and its check takes it as it is ([`crate::spec::heap::check_with`]: a construction plan, its classes, bounds and
    /// label). Each counts as one of the person's domain restrictions. A domain for a subject the run doesn't check
    /// (an unchanged method, an entry point's handler, a name alignment doesn't match) is refused before any proof,
    /// never left unread.
    pub domains: BTreeMap<String, ObjectDomain>,
}

/// Reads `compare --domains FILE`: a JSON object from each kernel subject to its domain, as a claim states one
/// (`{"pkg.Class#method": {"classes": [...], "bounds": ..., "made_by": {"kind": "planned", ...}, "label": ...}}`). A
/// field a domain doesn't have is refused, and so is a plan [`crate::construction::check_plans`] refuses.
pub fn load_domains(path: &Path) -> Result<BTreeMap<String, ObjectDomain>, Unsupported> {
    let fail = |e: String| unsupported(format!("--domains {}: {e}", path.display()));
    let text = std::fs::read_to_string(path).map_err(|e| fail(e.to_string()))?;
    let domains: BTreeMap<String, ObjectDomain> = serde_json::from_str(&text).map_err(|e| fail(e.to_string()))?;
    for (subject, domain) in &domains {
        if !subject.contains('#') {
            return Err(fail(format!("{subject} is not a method, pkg.Class#method")));
        }
        if let crate::spec::Construction::Planned { before, after } = &domain.made_by {
            crate::construction::check_plans(before, after).map_err(|u| fail(format!("{subject}'s plan: {u}")))?;
        }
    }
    Ok(domains)
}

/// The categories of a person's decisions, every one counted, so that effort can't hide by moving category.
pub const CATEGORIES: &[&str] = &["mapping", "approved exclusion", "domain restriction", "observation change", "environment assumption"];

/// What `compare` found.
#[derive(Debug, Clone, Serialize)]
pub struct Report {
    pub before: String,
    pub after: String,
    /// Every old entry point's observations, each as one obligation.
    pub obligations: Vec<Obligation>,
    /// Each old entry point, checked against its counterpart.
    pub entries: Vec<EntryCheck>,
    /// Each changed kernel method pair.
    pub kernel: Vec<KernelCheck>,
    pub effort: Effort,
}

/// One changed method pair of the kernel, checked under alignment's proposal.
#[derive(Debug, Clone, Serialize)]
pub struct KernelCheck {
    /// The new method, `pkg.Class#method`.
    pub subject: String,
    /// The old method it is matched with.
    pub before: String,
    /// No external contract anchors its inputs: under an inferred correspondence, a proved relation holds, and
    /// whether it is the intended one is unconfirmed.
    pub standalone: bool,
    /// The claim it was checked under.
    pub claim: CanonicalClaim,
    /// The correspondence alignment proposed, with the evidence the check gave it; none where the classes have the
    /// same shape.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hint: Option<Hint>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub outcome: Option<Outcome>,
    /// Why it wasn't checked, or the check's named gap.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unsupported: Option<String>,
    /// The stored result that was the result: an exact hit.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reuse: Option<Reuse>,
    /// The changed helpers proved on their own and taken as one function in this check.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub callees: Vec<Reuse>,
}

/// What a person did and what is left for one.
#[derive(Debug, Clone, Default, Serialize)]
pub struct Effort {
    /// Decisions a person made, by category: every category of [`CATEGORIES`], zero included.
    pub decisions: BTreeMap<String, usize>,
    /// The decisions the run leaves for a person, by category: the result is unresolved where one is.
    pub questions: Vec<Question>,
    /// What the verdicts rest on that no person decided: the environment models' restrictions and the recording
    /// stubs. Assumed, not approved.
    pub assumed: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Question {
    pub category: String,
    pub subject: String,
    pub decide: String,
}

fn unsupported(what: impl Into<String>) -> Unsupported {
    Unsupported::new(Part::Alignment, what)
}

/// Compares the two builds: see the module's documentation.
pub fn run(options: &Options) -> Result<Report, Unsupported> {
    let (before, after) = (options.before.as_path(), options.after.as_path());
    let old = crate::spec::observe::entry_points(before)?;
    let new = crate::spec::observe::entry_points(after)?;
    let obligations = crate::spec::observe::compare(&old, &new)?;
    let handlers: Vec<&str> = old.iter().chain(new.iter()).map(|s| s.handler.as_str()).collect();

    let load = |dir: &Path| Build::load(dir).map_err(|e| unsupported(format!("reading the build {}: {e}", dir.display())));
    let (b, a) = (load(before)?, load(after)?);
    let aligned = alignment::align(&b, &a, None);
    let hints = alignment::hints(&aligned);
    let pairs: Vec<&alignment::mappings::Mapping> = aligned.mappings.iter().filter(|m| !handlers.contains(&m.after.as_str()) && !handlers.contains(&m.before.as_str())).collect();
    // A declared domain is read by the check of its subject, or the run is refused: never a domain stated and unread.
    if let Some(subject) = options.domains.keys().find(|s| !pairs.iter().any(|m| &m.after == *s)) {
        let subjects: Vec<&str> = pairs.iter().map(|m| m.after.as_str()).collect();
        let why = if handlers.contains(&subject.as_str()) { "it is an entry point's handler, which its observation spec's claim checks".to_string() } else { format!("the kernel's changed method pairs are {}", if subjects.is_empty() { "none".to_string() } else { subjects.join(", ") }) };
        return Err(unsupported(format!("--domains declares a domain for {subject}, which this run checks no kernel claim of ({why}): a domain no check reads is refused")));
    }
    let entries = crate::effects::check_builds(before, after, &[], None, options.bounds.clone(), options.cache.as_deref(), &options.environment)?;
    let mut kernel = Vec::new();
    for m in pairs {
        kernel.push(check_kernel(m, &hints.entries, &b, options));
    }

    let mut effort = Effort { decisions: CATEGORIES.iter().map(|c| (c.to_string(), 0)).collect(), ..Default::default() };
    // Each modelled call a person declares is a decision of theirs: what the dependency may answer.
    *effort.decisions.get_mut("environment assumption").expect("a category") += options.environment.len();
    // Each declared domain is one too: which inputs the subject's claim is about.
    *effort.decisions.get_mut("domain restriction").expect("a category") += options.domains.len();
    for o in &obligations {
        let decide = match o.change {
            Change::Removed => format!("{} is gone from the new build: approve its {} as removed, or it stays unresolved", o.entry, o.observation),
            Change::Changed => format!("{}'s {} changed shape ({}): approve the change, or prove it never shows", o.entry, o.observation, o.differences.join("; ")),
            _ => continue,
        };
        effort.questions.push(Question { category: "observation change".into(), subject: o.entry.clone(), decide });
    }
    for k in &kernel {
        if let Some(ask) = k.hint.as_ref().and_then(|h| h.ask.as_ref()) {
            effort.questions.push(Question { category: "mapping".into(), subject: k.subject.clone(), decide: ask.decide.clone() });
        }
    }
    for c in entries.iter().filter_map(|e| e.checked.as_ref()) {
        for a in &c.assumptions {
            if !effort.assumed.contains(a) {
                effort.assumed.push(a.clone());
            }
        }
    }
    Ok(Report { before: before.display().to_string(), after: after.display().to_string(), obligations, entries, kernel, effort })
}

/// The observations a Java API method is held to: the result and the exception, and the identity relation of the
/// result with each object parameter of the result's class, compared within each version (a caller that gets back
/// the object it passed can tell it from a copy).
fn kernel_observations(m: &alignment::mappings::Mapping, b: &Build) -> Vec<Observation> {
    let mut out = vec![Observation::Result, Observation::Exception];
    for name in same_class_as_result(b, &m.before) {
        out.push(Observation::Identity { left: "result".into(), right: name });
    }
    out
}

/// The object parameters of `target` (`pkg.Class#method`) in `b` whose class is its result's, by name.
fn same_class_as_result(b: &Build, target: &str) -> Vec<String> {
    let Some((class, method)) = crate::verifier::parse_target(target) else { return Vec::new() };
    let Some(file) = b.classes.get(&class) else { return Vec::new() };
    let Some(m) = file.methods.iter().find(|x| x.name == method) else { return Vec::new() };
    let Ok(descriptor) = m.parsed_descriptor() else { return Vec::new() };
    if !matches!(descriptor.ret, crate::classfile::Type::Object(_)) {
        return Vec::new();
    }
    m.parameter_names(&file.pool).into_iter().zip(&descriptor.params).filter(|(_, t)| **t == descriptor.ret).map(|(n, _)| n).collect()
}

fn check_kernel(m: &alignment::mappings::Mapping, hints: &[Hint], b: &Build, options: &Options) -> KernelCheck {
    let observations = kernel_observations(m, b);
    let mut contract = m.contract.clone();
    contract.required = observations.iter().map(Observation::id).collect();
    let proposals: Vec<&Hint> = hints.iter().filter(|h| h.subject == m.after && matches!(h.content, HintContent::Correspondence { .. })).collect();
    let correspondence: Option<Correspondence> = proposals.first().and_then(|h| match &h.content {
        HintContent::Correspondence { correspondence } => Some(correspondence.clone()),
        _ => None,
    });
    let claim = CanonicalClaim {
        contract,
        closures: VersionDigests { before: "digested by the proof cache".into(), after: "digested by the proof cache".into() },
        domain: options.domains.get(&m.after).cloned(),
        observations,
        correspondence: correspondence.clone(),
        environment: None,
        bounds: options.bounds.clone(),
        assumptions: Vec::new(),
        tools: ToolIdentity { models: "digested by the proof cache".into(), jdk: "the default JDK".into(), checker: "native strict".into(), binary: "digested by the proof cache".into() },
    };
    let mut k = KernelCheck {
        subject: m.after.clone(),
        before: m.before.clone(),
        standalone: m.standalone,
        claim,
        hint: proposals.first().map(|h| (*h).clone()),
        outcome: None,
        unsupported: None,
        reuse: None,
        callees: Vec::new(),
    };
    if !m.complete() {
        let gaps = if m.unsupported.is_empty() { vec!["an input has no candidate".to_string()] } else { m.unsupported.clone() };
        k.unsupported = Some(format!("mapping {} onto {}: {}", m.before, m.after, gaps.join("; ")));
        return k;
    }
    if proposals.len() > 1 || proposals.first().is_some_and(|h| h.ask.is_some()) {
        k.unsupported = Some(format!("{} correspondences proposed for {}: a person decides which, and nothing is checked until then", proposals.len(), m.after));
        return k;
    }
    let mut reused = heap::Reused::default();
    match heap::check_with(&k.claim, &options.before, &options.after, options.cache.as_deref(), &mut reused) {
        Ok(outcome) => {
            if let (Some(hint), Some(key)) = (k.hint.as_mut(), reused.key.as_ref()) {
                hint.evidence = match outcome.verdict {
                    Verdict::Verified => Evidence::Proved { claim_key: key.0.clone() },
                    Verdict::Refuted => Evidence::Refuted { claim_key: key.0.clone(), witness: outcome.witness.clone().unwrap_or_default() },
                    Verdict::Unresolved => Evidence::Unknown { why: outcome.problem.clone().unwrap_or_default() },
                };
            }
            k.outcome = Some(outcome);
            k.reuse = reused.exact;
            k.callees = reused.callees;
        }
        Err(u) => k.unsupported = Some(u.what),
    }
    k
}

/// The SARIF findings of a report: an `effects-changed` per refuted entry point, as `effects --report` writes them,
/// and a `behaviour-changed` per refuted kernel pair, its witness the message, anchored at the new method's class
/// when its source is under one of `sources` (the path made relative to `base`).
pub fn findings(report: &Report, sources: &[PathBuf], base: Option<&Path>) -> Vec<crate::sarif::Finding> {
    let mut out = crate::effects::findings(&report.entries, sources, base);
    for k in &report.kernel {
        let Some(o) = k.outcome.as_ref().filter(|o| o.verdict == Verdict::Refuted) else { continue };
        let class = k.subject.split_once('#').map(|(class, _)| class.replace('.', "/")).unwrap_or_default();
        let file = crate::sarif::source_file(&class, sources);
        let uri = file.map(|f| base.map(|b| crate::sarif::relative_uri(b, &f)).unwrap_or_else(|| f.display().to_string()));
        let message = format!("{} no longer preserves what {} did under the correspondence alignment proposed: {}", k.subject, k.before, o.witness.as_deref().unwrap_or("a counterexample"));
        out.push(crate::sarif::Finding::new("behaviour-changed", message, uri, 1));
    }
    out
}

fn verdict_word(v: Verdict) -> &'static str {
    match v {
        Verdict::Verified => "verified",
        Verdict::Refuted => "refuted",
        Verdict::Unresolved => "unresolved",
    }
}

fn state_word(s: crate::spec::ObservationState) -> &'static str {
    use crate::spec::ObservationState::*;
    match s {
        Preserved => "preserved",
        ChangedWithApproval => "changed with approval",
        Unresolved => "unresolved",
        Refuted => "refuted",
    }
}

/// The text `jvmcontract compare` prints: the entry points as `jvmcontract effects` prints them, then each kernel
/// pair with its claim's correspondence, verdict, accounting, domain and reuse, then the obligations' count and the
/// effort.
pub fn render(report: &Report) -> String {
    let mut s = String::new();
    s.push_str(&format!("comparing {} with {}\n\nThe entry points (no mapping: their inputs are anchored by the observation specs)\n\n", report.before, report.after));
    s.push_str(&crate::effects::render_checks(&report.entries));
    s.push_str("\nThe kernel (each changed method pair alignment matched, under its proposal)\n\n");
    let mut counts = [0usize; 4];
    for k in &report.kernel {
        let pair = if k.before == k.subject { k.subject.clone() } else { format!("{} (was {})", k.subject, k.before) };
        let Some(o) = &k.outcome else {
            counts[3] += 1;
            s.push_str(&format!("{pair}: unsupported: {}\n", k.unsupported.as_deref().unwrap_or("")));
            continue;
        };
        counts[match o.verdict {
            Verdict::Verified => 0,
            Verdict::Refuted => 1,
            Verdict::Unresolved => 2,
        }] += 1;
        s.push_str(&format!("{pair}: {}", verdict_word(o.verdict)));
        if k.standalone && k.hint.is_some() && o.verdict == Verdict::Verified {
            s.push_str(" (no external contract anchors its inputs: the relation is proved, and whether it is the intended one is unconfirmed)");
        }
        s.push('\n');
        if let Some(h) = &k.hint {
            if let HintContent::Correspondence { correspondence } = &h.content {
                let mut eq: Vec<String> = correspondence.inputs.iter().map(|e| format!("{} == {}", e.old, e.new)).collect();
                eq.extend(correspondence.outputs.iter().map(|r| format!("{}: {}", r.observation, r.holds)));
                let evidence = match &h.evidence {
                    Evidence::Proved { claim_key } => format!("proved for {claim_key}"),
                    Evidence::Refuted { claim_key, .. } => format!("refuted for {claim_key}"),
                    Evidence::Unknown { .. } => "unknown".into(),
                    Evidence::Stale { claim_key } => format!("stale, was for {claim_key}"),
                    Evidence::Unchecked => "unchecked".into(),
                };
                let source = format!("{:?}, {:?}", h.source, h.intent).to_lowercase();
                s.push_str(&format!("  correspondence ({source}; {evidence}): {}\n", eq.join(", ")));
            }
        }
        let accounting: Vec<String> = o.accounting.iter().map(|a| format!("{} {}", a.observation, state_word(a.state))).collect();
        s.push_str(&format!("  observations: {}\n", accounting.join(", ")));
        if let Some(w) = &o.witness {
            s.push_str(&format!("  witness: {w}\n"));
        }
        if let Some(p) = &o.problem {
            s.push_str(&format!("  why: {p}\n"));
        }
        if !o.domain.is_empty() {
            s.push_str(&format!("  domain: {}\n", o.domain));
        }
        match &k.reuse {
            Some(Reuse::Exact { key, from }) => s.push_str(&format!("  reused: the stored result of the same claim ({}), from {from}\n", key.0)),
            Some(Reuse::Callee { .. }) | None => {}
        }
        for c in &k.callees {
            if let Reuse::Callee { callee, key } = c {
                s.push_str(&format!("  reused: {callee}, changed, proved equivalent by a check of its own ({}), one function in both versions\n", key.0));
            }
        }
    }
    s.push_str(&format!("\nkernel: {} verified, {} refuted, {} unresolved, {} unsupported\n", counts[0], counts[1], counts[2], counts[3]));
    let mut by_change: BTreeMap<String, usize> = BTreeMap::new();
    for o in &report.obligations {
        *by_change.entry(format!("{:?}", o.change).to_lowercase()).or_default() += 1;
    }
    s.push_str(&format!("obligations: {} ({})\n", report.obligations.len(), by_change.iter().map(|(c, n)| format!("{n} {c}")).collect::<Vec<_>>().join(", ")));
    let e = &report.effort;
    s.push_str(&format!("\nEffort: decisions a person made: {}\n", e.decisions.iter().map(|(c, n)| format!("{c} {n}")).collect::<Vec<_>>().join(", ")));
    if e.questions.is_empty() {
        s.push_str("questions for a person: none\n");
    } else {
        s.push_str(&format!("questions for a person: {}\n", e.questions.len()));
        for q in &e.questions {
            s.push_str(&format!("  - {} ({}): {}\n", q.subject, q.category, q.decide));
        }
    }
    if !e.assumed.is_empty() {
        s.push_str("assumed, not decided by anyone:\n");
        for a in &e.assumed {
            s.push_str(&format!("  - {a}\n"));
        }
    }
    s
}

impl Report {
    /// Whether everything compared was verified: every entry point and kernel pair, and no question left.
    pub fn all_verified(&self) -> bool {
        self.entries.iter().all(|c| c.checked.as_ref().is_some_and(|k| k.outcome.verdict == Verdict::Verified))
            && self.kernel.iter().all(|k| k.outcome.as_ref().is_some_and(|o| o.verdict == Verdict::Verified))
            && self.effort.questions.is_empty()
    }
}
