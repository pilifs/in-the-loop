//! Method correspondence between two builds (`jvmcontract align`, step A2 of
//! `llm-dlc/loops/foundations-alignment.md`), on small pairs of versions compiled here with javac, and on the
//! foundations fixture's kernel.

use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::alignment::mappings::{Anchor, Mapping, ResultKind};
use jvmcontract::alignment::{self, Alignment, Basis, Build, Change, MethodReport};
use jvmcontract::spec::{Correspondence, Derivation, Equation, Evidence, ExternalInput, Hint, HintContent, Hints, Intent, PreservationContract, Source};

fn has_javac() -> bool {
    let found = Command::new("javac").arg("-version").output().is_ok();
    if !found {
        let skip = std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1");
        assert!(skip, "javac not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip the tests that need it");
    }
    found
}

fn scratch(name: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("alignment").join(name);
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

/// Compiles `sources` (file name, text) into `dir/version` and returns that directory.
fn compile(dir: &Path, version: &str, sources: &[(&str, &str)]) -> PathBuf {
    let src = dir.join(format!("{version}-src"));
    std::fs::create_dir_all(&src).unwrap();
    let files: Vec<PathBuf> = sources
        .iter()
        .map(|(name, text)| {
            let path = src.join(name);
            std::fs::write(&path, text).unwrap();
            path
        })
        .collect();
    compile_files(&dir.join(version), &files)
}

fn compile_files(out: &Path, files: &[PathBuf]) -> PathBuf {
    std::fs::create_dir_all(out).unwrap();
    let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-d"]).arg(out).args(files).status().expect("javac runs");
    assert!(status.success(), "compiles into {}", out.display());
    out.to_path_buf()
}

fn align(name: &str, before: &[(&str, &str)], after: &[(&str, &str)]) -> Option<MethodReport> {
    if !has_javac() {
        return None;
    }
    let dir = scratch(name);
    let (b, a) = (compile(&dir, "before", before), compile(&dir, "after", after));
    Some(alignment::methods(&Build::load(&b).unwrap(), &Build::load(&a).unwrap()))
}

fn entry<'r>(report: &'r MethodReport, before: &str) -> &'r alignment::MethodMatch {
    report.methods.iter().find(|m| m.before == before).unwrap_or_else(|| panic!("no entry for {before}: {}", alignment::render(report)))
}

#[test]
fn a_renamed_method_with_the_same_body_leads() {
    let Some(report) = align(
        "renamed",
        &[("A.java", "public class A { static int f(int x) { return x * 3 + 1; } static int keep(int y) { return y; } }")],
        &[("A.java", "public class A { static int g(int x) { return x * 3 + 1; } static int keep(int y) { return y; } }")],
    ) else {
        return;
    };
    let m = entry(&report, "A#f");
    assert_eq!(m.change, Change::Vanished);
    assert!(m.leads, "{}", alignment::render(&report));
    assert_eq!(m.candidates[0].after, "A#g");
    assert!(m.candidates[0].basis.contains(&Basis::SameBodyShape));
    assert!(!report.methods.iter().any(|m| m.before == "A#keep"), "an unchanged method gets no entry");
}

#[test]
fn a_method_moved_to_a_new_class_leads_and_its_callers_say_so() {
    let Some(report) = align(
        "moved",
        &[
            ("U.java", "public class U { static long twice(long v) { return v + v; } }"),
            ("C.java", "public class C { static long use(long v) { return U.twice(v) - 1; } }"),
        ],
        &[
            ("V.java", "public class V { static long twice(long v) { return v + v; } }"),
            ("C.java", "public class C { static long use(long v) { return V.twice(v) - 1; } }"),
        ],
    ) else {
        return;
    };
    let m = entry(&report, "U#twice");
    assert!(m.leads, "{}", alignment::render(&report));
    let c = &m.candidates[0];
    assert_eq!(c.after, "V#twice");
    for b in [Basis::SameNameMoved, Basis::SameBodyShape, Basis::OldClassGone, Basis::NewClass, Basis::SameCallers { shared: 1, before: 1 }] {
        assert!(c.basis.contains(&b), "{b:?} in {:?}", c.basis);
    }
    let caller = entry(&report, "C#use");
    assert_eq!((caller.change, caller.candidates.len(), caller.candidates[0].after.as_str()), (Change::Changed, 1, "C#use"), "a changed method keeps its name and nothing else is proposed");
}

#[test]
fn two_equally_good_candidates_are_a_question() {
    let Some(report) = align(
        "ambiguous",
        &[("A.java", "public class A { static int f(int x) { return x + 1; } }")],
        &[("A.java", "public class A { static int g(int x) { return x + 2; } static int h(int x) { return x + 3; } }")],
    ) else {
        return;
    };
    let m = entry(&report, "A#f");
    assert_eq!(m.candidates.len(), 2, "{}", alignment::render(&report));
    assert!(!m.leads, "neither leads: {}", alignment::render(&report));
    assert!(m.leading().is_none());
}

#[test]
fn a_lone_weak_candidate_is_a_question_too() {
    // Only the parameters tie them: the body and the result type both changed, and nothing calls either.
    let Some(report) = align(
        "weak",
        &[("A.java", "public class A { static boolean done(long a, long b) { return a >= b; } }")],
        &[("A.java", "public class A { static long left(long a, long b) { long d = b - a; return d < 0 ? 0 : d / 1000; } }")],
    ) else {
        return;
    };
    let m = entry(&report, "A#done");
    assert_eq!(m.candidates.len(), 1, "{}", alignment::render(&report));
    assert!(m.candidates[0].basis.contains(&Basis::SameParameters));
    assert!(m.candidates[0].score < alignment::LEAD && !m.leads, "{}", alignment::render(&report));
}

#[test]
fn an_overloaded_name_is_written_with_its_parameter_types() {
    let Some(report) = align(
        "overloads",
        &[("A.java", "public class A { static int f(int x) { return x; } static int f(long x) { return (int) x; } }")],
        &[("A.java", "public class A { static int f(int x) { return x + 1; } static int f(long x) { return (int) x; } }")],
    ) else {
        return;
    };
    assert_eq!(report.methods.iter().map(|m| m.before.as_str()).collect::<Vec<_>>(), vec!["A#f(int)"]);
}

/// The foundations fixture's kernel (without its controller, which needs the Spring stand-ins): an amount that became
/// a value object. Compiled into a directory of the test's own (`test`), since the tests run in parallel.
fn kernel(test: &str, version: &str) -> Option<PathBuf> {
    if !has_javac() {
        return None;
    }
    let src = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/foundations").join(version).join("shop");
    let files: Vec<PathBuf> = ["Pricing.java", "Quote.java", "Money.java"].iter().map(|f| src.join(f)).filter(|p| p.exists()).collect();
    Some(compile_files(&scratch(&format!("kernel-{test}-{version}")), &files))
}

#[test]
fn the_kernel_keeps_its_methods_and_its_constructor_takes_the_value_object() {
    let (Some(before), Some(after)) = (kernel("methods", "before"), kernel("methods", "after")) else { return };
    let report = alignment::methods(&Build::load(&before).unwrap(), &Build::load(&after).unwrap());
    for kept in ["shop.Pricing#total", "shop.Pricing#discount"] {
        let m = entry(&report, kept);
        assert_eq!((m.change, m.candidates.len(), m.candidates[0].after.as_str()), (Change::Changed, 1, kept));
    }
    assert!(!report.methods.iter().any(|m| m.before == "shop.Pricing#withQuantity"), "unchanged: {}", alignment::render(&report));
    let init = entry(&report, "shop.Quote#<init>");
    assert!(init.leads, "{}", alignment::render(&report));
    assert_eq!(init.candidates[0].after, "shop.Quote#<init>");
    let hints = alignment::method_hints(&report);
    assert!(hints.entries.iter().all(|h| h.source == Source::Inferred && h.intent == Intent::Proposed && h.evidence == Evidence::Unchecked));
}

#[test]
fn the_command_writes_hints_and_keeps_what_a_person_approved() {
    let (Some(before), Some(after)) = (kernel("command", "before"), kernel("command", "after")) else { return };
    let path = scratch("hints").join("hints.json");
    let approved = Hint {
        subject: "shop.Quote#cents".into(),
        content: HintContent::Method { before: "shop.Quote#cents".into(), after: "shop.Quote#amount".into() },
        source: Source::Inferred,
        intent: Intent::Approved,
        evidence: Evidence::Unchecked,
        rank: None,
        why: Vec::new(),
    };
    alignment::write_hints(&path, &Hints { version: alignment::HINTS_VERSION, entries: vec![approved.clone()] }).unwrap();
    let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).args(["align", "--before"]).arg(&before).arg("--after").arg(&after).arg("--hints").arg(&path).output().unwrap();
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    let text = String::from_utf8_lossy(&out.stdout);
    assert!(text.contains("vanished  shop.Quote#<init>"), "{text}");
    let hints = alignment::read_hints(&path).unwrap();
    assert_eq!(hints.entries[0], approved, "the approved hint is kept first, as it was");
    assert!(!hints.entries[1..].iter().any(|h| h.subject == "shop.Quote#cents"), "no proposal for a subject a person decided");
    assert!(hints.entries.iter().any(|h| matches!(&h.content, HintContent::Method { before, after } if before == "shop.Quote#<init>" && after == "shop.Quote#<init>")));
    let again = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).args(["align", "--before"]).arg(&before).arg("--after").arg(&after).arg("--hints").arg(&path).output().unwrap();
    assert!(again.status.success());
    assert_eq!(alignment::read_hints(&path).unwrap(), hints, "a second run replaces its own proposals with the same ones");
}

// Step A3: argument, record and result mappings under the contract.

fn aligned(name: &str, before: &[(&str, &str)], after: &[(&str, &str)], contract: Option<&PreservationContract>) -> Option<Alignment> {
    if !has_javac() {
        return None;
    }
    let dir = scratch(name);
    let (b, a) = (compile(&dir, "before", before), compile(&dir, "after", after));
    Some(alignment::align(&Build::load(&b).unwrap(), &Build::load(&a).unwrap(), contract))
}

fn mapping<'a>(alignment: &'a Alignment, before: &str) -> &'a Mapping {
    alignment.mappings.iter().find(|m| m.before == before).unwrap_or_else(|| panic!("no mapping for {before}: {}", alignment::mappings::render(&alignment.mappings)))
}

/// Every candidate expression of a mapping, inputs and result.
fn expressions(m: &Mapping) -> Vec<&str> {
    m.inputs.iter().flat_map(|i| i.candidates.iter()).chain(&m.result.candidates).map(|c| c.expression.as_str()).collect()
}

#[test]
fn the_offset_mapping_is_never_proposed_for_an_anchored_input() {
    // The main brief's case: `price(c)` returns `c`, then `c + 1`. `before.c = after.c + 1` would make the results
    // agree; the input is anchored, so its mapping is `c` and nothing else, and the pair needs no hint.
    let before = [("A.java", "public class A { static long price(long c) { return c; } }")];
    let after = [("A.java", "public class A { static long price(long c) { return c + 1; } }")];
    let contract = PreservationContract {
        subject: "A#price".into(),
        inputs: vec![ExternalInput { name: "c".into(), ty: "long".into(), derivation: Derivation::Identity }],
        required: vec!["result".into(), "exception".into()],
        approved_changes: Vec::new(),
    };
    for (name, given) in [("offset", None), ("offset-contract", Some(&contract))] {
        let Some(a) = aligned(name, &before, &after, given) else { return };
        let m = mapping(&a, "A#price");
        assert_eq!(m.standalone, given.is_none());
        assert_eq!((m.inputs.len(), m.inputs[0].anchor, m.inputs[0].candidates.len(), m.inputs[0].candidates[0].expression.as_str()), (1, Anchor::Anchored, 1, "c"));
        assert!(expressions(m).iter().all(|e| !e.contains('+') && !e.contains('-')), "{:?}", expressions(m));
        assert!(m.is_default(), "the default mapping: {:?}", m.proposals);
        assert!(alignment::mapping_hints(&a.mappings).entries.is_empty());
    }
}

#[test]
fn a_stated_derivation_is_used_as_a_person_stated_it() {
    let Some(a) = aligned(
        "stated",
        &[("A.java", "public class A { static long price(long c) { return c; } }")],
        &[("A.java", "public class A { static long price(long c) { return c - 1; } }")],
        Some(&PreservationContract {
            subject: "A#price".into(),
            inputs: vec![ExternalInput { name: "c".into(), ty: "long".into(), derivation: Derivation::Stated { expression: "c - 1".into() } }],
            required: vec!["result".into(), "exception".into()],
            approved_changes: Vec::new(),
        }),
    ) else {
        return;
    };
    let m = mapping(&a, "A#price");
    assert_eq!(m.proposals.len(), 1);
    assert_eq!(m.proposals[0].flags.before_arguments.as_deref(), Some("c - 1"));
    assert!(m.inputs[0].candidates[0].why.contains("as a person stated"));
}

#[test]
fn reordered_parameters_keep_their_names() {
    let Some(a) = aligned(
        "reordered",
        &[("A.java", "public class A { static long f(long a, int b) { return a * b; } }")],
        &[("A.java", "public class A { static long f(int b, long a) { return b * a; } }")],
        None,
    ) else {
        return;
    };
    // The descriptor changed, so the old method is gone and the new one leads by name.
    let m = mapping(&a, "A#f");
    assert!(m.inputs.iter().all(|i| i.anchor == Anchor::Anchored));
    assert_eq!(m.proposals.len(), 1);
    assert_eq!(m.proposals[0].flags.before_arguments.as_deref(), Some("a, b"));
    let hints = alignment::mapping_hints(&a.mappings);
    let HintContent::Correspondence { correspondence } = &hints.entries[0].content else { panic!() };
    assert_eq!(correspondence.inputs.iter().map(|e| (e.old.as_str(), e.new.as_str())).collect::<Vec<_>>(), vec![("old.a", "new.a"), ("old.b", "new.b")]);
    assert!(hints.entries.iter().all(|h| h.source == Source::Inferred && h.intent == Intent::Proposed && h.evidence == Evidence::Unchecked));
}

#[test]
fn parameters_gathered_into_a_record_are_its_components() {
    // Introduce parameter object, as in example 128: the start and size become a record, the method moves into it.
    let Some(a) = aligned(
        "gathered",
        &[("C.java", "public class C { static long offset(long batchStart, int batchSize, int failedIndex) { return batchStart + Math.min(batchSize, failedIndex); } }")],
        &[("C.java", "public class C { }"), ("Batch.java", "public record Batch(long start, int size) { long offset(int failedIndex) { return start + Math.min(size, failedIndex); } }")],
        None,
    ) else {
        return;
    };
    let m = mapping(&a, "C#offset");
    assert_eq!(m.after, "Batch#offset");
    assert_eq!(m.inputs.iter().map(|i| (i.old.as_str(), i.anchor)).collect::<Vec<_>>(), vec![("batchStart", Anchor::Internal), ("batchSize", Anchor::Internal), ("failedIndex", Anchor::Anchored)]);
    assert!(m.inputs.iter().all(|i| i.leads), "{}", alignment::mappings::render(&a.mappings));
    let flags = &m.proposals[0].flags;
    assert_eq!((flags.before_target.as_deref(), flags.before_arguments.as_deref()), (Some("C#offset"), Some("this.start, this.size, failedIndex")));
    assert!(m.free.is_empty());
}

#[test]
fn a_record_that_gained_a_component_is_built_from_the_old_ones_and_the_new_one_left_free() {
    // As in example 130: the receiver gained a component the old version has no counterpart for.
    let Some(a) = aligned(
        "gained",
        &[("B.java", "public record B(long base, long cap) { long delay(int attempt) { return Math.min(cap, base << attempt); } }")],
        &[("B.java", "public record B(long base, long cap, int factor) { long delay(int attempt) { return Math.min(cap, base * factor * attempt); } }")],
        None,
    ) else {
        return;
    };
    let m = mapping(&a, "B#delay");
    assert_eq!(m.inputs[0].anchor, Anchor::Internal);
    assert_eq!(m.proposals.len(), 1);
    assert_eq!(m.proposals[0].flags.before_arguments.as_deref(), Some("new B(this.base, this.cap), attempt"));
    assert_eq!(m.free, vec!["this.factor"]);
}

#[test]
fn two_inputs_only_their_type_ties_are_a_question() {
    let Some(a) = aligned(
        "untied",
        &[("C.java", "public class C { static long span(long x, long y) { return y - x; } }")],
        &[("C.java", "public class C { }"), ("P.java", "public record P(long p, long q) { long span() { return q - p; } }")],
        None,
    ) else {
        return;
    };
    let m = mapping(&a, "C#span");
    assert!(m.inputs.iter().all(|i| !i.leads && i.candidates.len() == 2), "{}", alignment::mappings::render(&a.mappings));
    assert!(m.proposals.len() > 1);
    let hints = alignment::mapping_hints(&a.mappings);
    assert_eq!(hints.entries.iter().map(|h| h.rank).collect::<Vec<_>>(), (1..=m.proposals.len() as u32).map(Some).collect::<Vec<_>>());
}

#[test]
fn the_result_relations_come_from_the_catalogue() {
    let Some(a) = aligned(
        "results",
        &[
            ("W.java", "public record W(long start, long count) { W counted(long now) { return new W(start, count + 1); } }"),
            ("A.java", "public class A { static int widened(int x) { return x; } static long wrapped(long x) { return x; } static boolean expired(long left) { return left <= 0; } }"),
        ],
        &[
            ("W.java", "public record W(long start, long count, long previous) { W counted(long now) { return new W(start, count + 1, previous); } }"),
            ("M.java", "public record M(long cents) {}"),
            ("A.java", "public class A { static long widened(int x) { return x; } static M wrapped(long x) { return new M(x); } static long expired(long left) { return left; } }"),
        ],
        None,
    ) else {
        return;
    };
    let relation = |before: &str| {
        let m = mapping(&a, before);
        (m.result.kind, m.result.inferred, m.result.candidates.iter().map(|c| c.expression.clone()).collect::<Vec<_>>())
    };
    assert_eq!(relation("W#counted"), (ResultKind::Components, true, vec!["previous.start == result.start && previous.count == result.count".to_string()]));
    assert_eq!(relation("A#widened"), (ResultKind::Widened, true, vec!["previous == result".to_string()]));
    assert_eq!(relation("A#wrapped"), (ResultKind::Converted, true, vec!["previous == result.cents".to_string()]));
    let (kind, inferred, candidates) = relation("A#expired");
    assert_eq!((kind, inferred, candidates.len()), (ResultKind::Changed, false, 6));
    assert!(candidates.contains(&"previous == (result <= 0)".to_string()));
    // A changed result is a question even with every input fixed, and its observation stays in the count, unresolved.
    let m = mapping(&a, "A#expired");
    assert_eq!(m.proposals.len(), 6);
    let result = m.accounting.iter().find(|k| k.observation == "result").expect("still counted");
    assert!(result.how.starts_with("unresolved"), "{}", result.how);
    for m in &a.mappings {
        assert_eq!(m.accounting.iter().map(|k| k.observation.clone()).collect::<Vec<_>>(), m.contract.required, "every required observation is accounted for");
    }
}

// Step A4's narrow case: field correspondence, from how each version's constructors route their parameters.

fn kernel_contract() -> PreservationContract {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/foundations/golden/kernel-contract.json");
    serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap()
}

fn equation(old: &str, new: &str) -> Equation {
    Equation { old: old.into(), new: new.into() }
}

fn correspondences<'h>(hints: &'h Hints, subject: &str) -> Vec<&'h Correspondence> {
    hints
        .entries
        .iter()
        .filter(|h| h.subject == subject)
        .filter_map(|h| match &h.content {
            HintContent::Correspondence { correspondence } => Some(correspondence),
            _ => None,
        })
        .collect()
}

#[test]
fn the_kernel_s_quote_is_related_field_by_field_from_its_constructors() {
    let (Some(before), Some(after)) = (kernel("fields", "before"), kernel("fields", "after")) else { return };
    let (b, a) = (Build::load(&before).unwrap(), Build::load(&after).unwrap());
    let contract = kernel_contract();
    let want = vec![equation("old.q.cents", "new.q.amount.cents"), equation("old.q.quantity", "new.q.quantity")];
    let aligned = alignment::align(&b, &a, Some(&contract));
    let total = mapping(&aligned, "shop.Pricing#total");
    assert!(total.unsupported.is_empty() && total.free.is_empty(), "{}", alignment::mappings::render(&aligned.mappings));
    assert_eq!((total.inputs[0].anchor, total.proposals.len()), (Anchor::Anchored, 1), "q is the input the contract fixes, and one relation is proposed");
    assert_eq!(total.proposals[0].fields, want);
    let golden = Correspondence { inputs: want.clone(), outputs: Vec::new() };
    assert_eq!(correspondences(&alignment::hints(&aligned), "shop.Pricing#total"), vec![&golden]);
    let proposed = jvmcontract::spec::align::propose(&contract, &before, &after).expect("the subject's mapping is complete");
    assert_eq!(correspondences(&proposed, "shop.Pricing#total"), vec![&golden]);
    assert!(proposed.entries.iter().all(|h| h.intent == Intent::Proposed && h.evidence == Evidence::Unchecked));
    // Standalone, q is internal (its class changed shape, so nothing external fixes it), and the relation the same.
    let standalone = alignment::align(&b, &a, None);
    let total = mapping(&standalone, "shop.Pricing#total");
    assert_eq!((total.inputs[0].anchor, total.proposals[0].fields.clone()), (Anchor::Internal, want));
}

#[test]
fn a_renamed_field_is_related_by_its_constructor_and_a_new_one_left_free() {
    let before = [("P.java", "final class P { long cents; int n; P(long cents, int n) { this.cents = cents; this.n = n; } static long f(P p) { return p.cents * p.n; } }")];
    let after = [(
        "P.java",
        "final class P { long priceCents; int n; int extra; P(long priceCents, int n, int extra) { this.priceCents = priceCents; this.n = n; this.extra = extra; } static long f(P p) { return p.priceCents * p.n; } }",
    )];
    let Some(a) = aligned("fields-renamed", &before, &after, None) else { return };
    let f = mapping(&a, "P#f");
    let fc = f.inputs[0].fields.as_ref().unwrap_or_else(|| panic!("{}", alignment::mappings::render(&a.mappings)));
    assert_eq!(fc.free, vec!["extra"], "a new field no old one reaches is left free");
    assert_eq!(f.proposals.len(), 1);
    assert_eq!(f.proposals[0].fields, vec![equation("old.p.cents", "new.p.priceCents"), equation("old.p.n", "new.p.n")]);
}

#[test]
fn a_constructor_that_computes_or_shifts_what_it_stores_is_never_related() {
    let before = [("Q.java", "final class Q { long cents; Q(long cents) { this.cents = cents; } static long f(Q q) { return q.cents; } }")];
    let wrapped = [
        ("M.java", "record M(long cents) {}"),
        ("Q.java", "final class Q { M amount; Q(long cents) { this.amount = new M(cents); } static long f(Q q) { return q.amount.cents(); } }"),
    ];
    // The field-level offset: the stored value is shifted, so `old.q.cents == new.q.cents` would hide it, and
    // `old.q.cents == new.q.cents - 1` is never proposed.
    let shifted = [("Q.java", "final class Q { long cents; int pad; Q(long cents) { this.cents = cents + 1; } static long f(Q q) { return q.cents - 1; } }")];
    for (name, after) in [("fields-wrapped", &wrapped[..]), ("fields-shifted", &shifted[..])] {
        let Some(a) = aligned(name, &before, after, None) else { return };
        let f = mapping(&a, "Q#f");
        assert!(f.proposals.is_empty() && f.inputs[0].fields.is_none(), "{name}: {}", alignment::mappings::render(&a.mappings));
        assert!(f.unsupported.iter().any(|u| u.contains("cents")), "{name}: the gap is named: {:?}", f.unsupported);
        assert!(correspondences(&alignment::hints(&a), "Q#f").is_empty());
    }
}
