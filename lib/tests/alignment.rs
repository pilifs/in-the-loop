//! Method correspondence between two builds (`jvmcontract align`, step A2 of
//! `llm-dlc/loops/foundations-alignment.md`), on small pairs of versions compiled here with javac, and on the
//! foundations fixture's kernel.

use std::path::{Path, PathBuf};
use std::process::Command;

use jvmcontract::alignment::mappings::{Anchor, Mapping, ResultKind};
use jvmcontract::alignment::proofs::{self, Attempt, MappingProof, Settings, Settled, Tried};
use jvmcontract::alignment::{self, Alignment, Basis, Build, Change, MethodReport};
use jvmcontract::spec::{Correspondence, Derivation, Equation, Evidence, ExternalInput, Hint, HintContent, Hints, Intent, PreservationContract, Relation, Source};

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
    let asked = alignment::questions::questions(&alignment::method_hints(&report), Some(Path::new("h.json")));
    let [q] = asked.as_slice() else { panic!("{}", alignment::questions::render(&asked, &[])) };
    assert_eq!((q.kind.as_str(), q.subject.as_str()), ("method", "A#f"));
    assert!(q.decide.starts_with("which new method takes the place of A#f: 2 candidates"), "{}", q.decide);
    assert!(q.answers.iter().all(|a| a.means[0].contains("takes its place")));
    assert_eq!(q.answers[1].approve, "jvmcontract approve --hints h.json --kind method --subject 'A#f' --rank 2");
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
    // Its code is unchanged, but it takes and returns a Quote, whose shape changed: itself, as reshaped.
    let reshaped = entry(&report, "shop.Pricing#withQuantity");
    assert_eq!((reshaped.change, reshaped.candidates[0].after.as_str()), (Change::Reshaped, "shop.Pricing#withQuantity"), "{}", alignment::render(&report));
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
        ask: None,
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
    // The question: both inputs, and what each candidate makes them.
    let asked = alignment::questions::questions(&hints, None);
    let [q] = asked.as_slice() else { panic!("{}", alignment::questions::render(&asked, &[])) };
    assert!(q.decide.starts_with("(against C#span) what the old x is made from: 2 candidates, none ahead (this.p | this.q); what the old y is made from"), "{}", q.decide);
    assert!(q.answers.iter().any(|a| a.means == ["x = this.p", "y = this.q", "new inputs left free: none"]), "{}", alignment::questions::render(&asked, &[]));
    assert!(q.answers.iter().any(|a| a.means == ["x = this.p", "y = this.p", "new inputs left free: this.q"]), "what each leaves free: {}", alignment::questions::render(&asked, &[]));
    assert_eq!(q.answers.len(), m.proposals.len());
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
fn a_value_object_the_constructor_makes_is_related_inside_it() {
    let before = [("Q.java", "final class Q { long cents; Q(long cents) { this.cents = cents; } static long f(Q q) { return q.cents; } }")];
    let wrapped = [
        ("M.java", "record M(long cents) {}"),
        ("Q.java", "final class Q { M amount; Q(long cents) { this.amount = new M(cents); } static long f(Q q) { return q.amount.cents(); } }"),
    ];
    // Two levels down: the value object's own constructor makes another.
    let nested = [
        ("C.java", "record C(long v) {}"),
        ("M.java", "final class M { C c; M(long cents) { this.c = new C(cents); } }"),
        ("Q.java", "final class Q { M amount; Q(long cents) { this.amount = new M(cents); } static long f(Q q) { return q.amount.c.v(); } }"),
    ];
    for (name, after, path) in [("fields-wrapped", &wrapped[..], "new.q.amount.cents"), ("fields-nested", &nested[..], "new.q.amount.c.v")] {
        let Some(a) = aligned(name, &before, after, None) else { return };
        let f = mapping(&a, "Q#f");
        assert!(f.unsupported.is_empty(), "{name}: {}", alignment::mappings::render(&a.mappings));
        assert_eq!(f.proposals.len(), 1, "{name}");
        assert_eq!(f.proposals[0].fields, vec![equation("old.q.cents", path)], "{name}");
        assert_eq!(correspondences(&alignment::hints(&a), "Q#f"), vec![&Correspondence { inputs: vec![equation("old.q.cents", path)], outputs: Vec::new() }]);
    }
    // And the other way: the old version kept the value object, the new one the primitive.
    let Some(a) = aligned("fields-unwrapped", &wrapped, &before, None) else { return };
    let f = mapping(&a, "Q#f");
    assert_eq!(f.proposals.iter().map(|p| p.fields.clone()).collect::<Vec<_>>(), vec![vec![equation("old.q.amount.cents", "new.q.cents")]], "{}", alignment::mappings::render(&a.mappings));
}

#[test]
fn a_field_whose_own_class_changed_shape_is_related_through_that_class() {
    // `Q` keeps its fields; the `L` it holds changed. The shape compared is deep, so `Q` changed with it.
    let before = [
        ("L.java", "final class L { long cents; L(long cents) { this.cents = cents; } }"),
        ("Q.java", "final class Q { L line; Q(L line) { this.line = line; } static long f(Q q) { return q.line.cents; } }"),
    ];
    let after = [
        ("M.java", "record M(long cents) {}"),
        ("L.java", "final class L { M amount; int tag; L(long cents) { this.amount = new M(cents); } }"),
        ("Q.java", "final class Q { L line; Q(L line) { this.line = line; } static long f(Q q) { return q.line.amount.cents(); } }"),
    ];
    let Some(a) = aligned("fields-nested-class", &before, &after, None) else { return };
    let f = mapping(&a, "Q#f");
    assert!(f.unsupported.is_empty(), "{}", alignment::mappings::render(&a.mappings));
    assert_eq!(f.inputs[0].anchor, alignment::mappings::Anchor::Internal, "q's class changed inside, so the signatures don't anchor it");
    let fc = f.inputs[0].fields.as_ref().expect("q is related field by field");
    assert_eq!(fc.free, vec!["line.tag".to_string()], "the inner class's new field is left free, at its path");
    assert!(fc.constructors.iter().any(|(o, _)| o.starts_with("L#")), "the inner class's constructors are named: {:?}", fc.constructors);
    assert_eq!(f.proposals.len(), 1);
    assert_eq!(f.proposals[0].fields, vec![equation("old.q.line.cents", "new.q.line.amount.cents")]);
    assert_eq!(correspondences(&alignment::hints(&a), "Q#f"), vec![&Correspondence { inputs: vec![equation("old.q.line.cents", "new.q.line.amount.cents")], outputs: Vec::new() }]);
    // An inner class that can't be related leaves the outer one unrelated, with the inner gap named.
    let shifted = [
        ("L.java", "final class L { long cents; int pad; L(long cents) { this.cents = cents + 1; } }"),
        ("Q.java", "final class Q { L line; Q(L line) { this.line = line; } static long f(Q q) { return q.line.cents - 1; } }"),
    ];
    let Some(a) = aligned("fields-nested-shifted", &before, &shifted, None) else { return };
    let f = mapping(&a, "Q#f");
    assert!(f.proposals.is_empty() && f.inputs[0].fields.is_none(), "{}", alignment::mappings::render(&a.mappings));
    assert!(f.unsupported.iter().any(|u| u.contains("line is set from line") && u.contains("cents")), "{:?}", f.unsupported);
    // A class that holds its own class is a relation over a chain of objects, not field paths: named, not followed.
    let chain = |value: &str, set: &str, read: &str| format!("final class N {{ {value}; N next; N(long v, N next) {{ this.{set}; this.next = next; }} static long f(N n) {{ return n.{read}; }} }}");
    let (old_chain, new_chain) = (chain("long v", "v = v", "v"), chain("M val", "val = new M(v)", "val.v()"));
    let Some(a) = aligned("fields-chain", &[("N.java", &old_chain)], &[("M.java", "record M(long v) {}"), ("N.java", &new_chain)], None) else { return };
    let f = mapping(&a, "N#f");
    assert!(f.proposals.is_empty(), "{}", alignment::mappings::render(&a.mappings));
    assert!(f.unsupported.iter().any(|u| u.contains("holding its own class")), "{:?}", f.unsupported);
}

#[test]
fn a_result_whose_class_changed_shape_is_compared_field_by_field() {
    let before = [("Q.java", "final class Q { long cents; int quantity; Q(long cents, int quantity) { this.cents = cents; this.quantity = quantity; } static Q make(long cents, int quantity) { return new Q(cents, quantity); } }")];
    let after = [
        ("M.java", "record M(long cents) {}"),
        ("Q.java", "final class Q { M amount; int quantity; int tag; Q(long cents, int quantity) { this.amount = new M(cents); this.quantity = quantity; } static Q make(long cents, int quantity) { Q q = new Q(cents, quantity); return q; } }"),
    ];
    let Some(a) = aligned("result-fields", &before, &after, None) else { return };
    let m = mapping(&a, "Q#make");
    assert_eq!(m.result.kind, ResultKind::Fields, "{}", alignment::mappings::render(&a.mappings));
    let relation = "previous.cents == result.amount.cents && previous.quantity == result.quantity";
    assert_eq!(expressions_of(&m.result.candidates), vec![relation]);
    assert!(m.result.inferred, "relating a representation is not a change of meaning");
    assert!(m.result.candidates[0].why.contains("tag"), "the new field is named as not compared: {}", m.result.candidates[0].why);
    let kept = m.accounting.iter().find(|k| k.observation == "result").expect("the result is accounted for");
    assert!(kept.how.contains("compares every old value"), "{}", kept.how);
    assert_eq!(m.proposals.len(), 1);
    assert_eq!(m.proposals[0].relation.as_deref(), Some(relation));
    let hints = alignment::hints(&a);
    let c = correspondences(&hints, "Q#make");
    assert_eq!(c.len(), 1);
    assert_eq!(c[0].outputs, vec![Relation { observation: "result".into(), holds: "old.result.cents == new.result.amount.cents && old.result.quantity == new.result.quantity".into() }]);
    // The regression check can't observe an object result: the proof is the heap stream's, and none is attempted.
    let Some(p) = proved("result-fields-prove", &before, &after, None) else { return };
    let attempts = &proof(&p, "Q#make").attempts;
    assert!(!attempts.is_empty() && attempts.iter().all(|t| matches!(&t.tried, Tried::NotTried { why } if why.contains("heap")) && matches!(t.evidence, Evidence::Unknown { .. })), "{}", proofs::render(&p.proofs));
    // A field the result's constructor shifts, or one that is a reference, leaves the result a person's decision,
    // with the gap named: no relation is proposed that would hide the shift or compare object ids across runs.
    let shifted = [("Q.java", "final class Q { long cents; int quantity; int pad; Q(long cents, int quantity) { this.cents = cents + 1; this.quantity = quantity; } static Q make(long cents, int quantity) { Q q = new Q(cents, quantity); return q; } }")];
    let tagged = |held: &str, set: &str| format!("final class Q {{ {held}; String tag; Q(long cents, String tag) {{ this.{set}; this.tag = tag; }} static Q make(long cents, String tag) {{ return new Q(cents, tag); }} }}");
    let (old_tagged, new_tagged) = (tagged("long cents", "cents = cents"), tagged("M amount", "amount = new M(cents)").replace("return new Q(cents, tag);", "Q q = new Q(cents, tag); return q;"));
    for (name, before, after, gap) in [
        ("result-shifted", before.to_vec(), shifted.to_vec(), "cents"),
        ("result-reference", vec![("Q.java", old_tagged.as_str())], vec![("M.java", "record M(long cents) {}"), ("Q.java", new_tagged.as_str())], "java.lang.String"),
    ] {
        let Some(a) = aligned(name, &before, &after, None) else { return };
        let m = mapping(&a, "Q#make");
        assert_eq!(m.result.kind, ResultKind::Changed, "{name}: {}", alignment::mappings::render(&a.mappings));
        assert!(m.result.candidates.is_empty() && !m.result.inferred, "{name}");
        assert!(m.result.gaps.iter().any(|g| g.contains(gap)), "{name}: the gap is named: {:?}", m.result.gaps);
        assert!(alignment::mappings::render(&a.mappings).contains(gap), "{name}: and shown");
    }
}

#[test]
fn code_that_did_not_change_over_a_class_that_did_is_mapped_through_the_class() {
    let (Some(before), Some(after)) = (kernel("reshaped", "before"), kernel("reshaped", "after")) else { return };
    let a = alignment::align(&Build::load(&before).unwrap(), &Build::load(&after).unwrap(), Some(&kernel_contract()));
    let change = |s: &str| a.methods.methods.iter().find(|m| m.before == s).map(|m| (m.change, m.leading().map(|c| c.after.clone())));
    // The same code, but it takes or returns a Quote, whose shape changed: mapped onto itself, not counted unchanged.
    for s in ["shop.Pricing#withQuantity", "shop.Quote#quantity"] {
        assert_eq!(change(s), Some((Change::Reshaped, Some(s.to_string()))), "{}", alignment::render(&a.methods));
    }
    // Code that is the same over classes that kept their shape is still unchanged.
    assert_eq!(change("shop.Pricing#<init>"), None);
    assert!(a.methods.unchanged >= 1);
    assert!(alignment::render(&a.methods).contains("reshaped  shop.Pricing#withQuantity"));
    let q = vec![equation("old.q.cents", "new.q.amount.cents"), equation("old.q.quantity", "new.q.quantity")];
    let m = mapping(&a, "shop.Pricing#withQuantity");
    assert!(m.standalone && m.unsupported.is_empty() && m.free.is_empty(), "{}", alignment::mappings::render(&a.mappings));
    assert_eq!(m.inputs.iter().map(|i| (i.old.as_str(), i.anchor)).collect::<Vec<_>>(), vec![("q", Anchor::Internal), ("quantity", Anchor::Anchored)]);
    assert_eq!(m.result.kind, ResultKind::Fields);
    let relation = "previous.cents == result.amount.cents && previous.quantity == result.quantity";
    assert_eq!((m.proposals.len(), m.proposals[0].fields.clone(), m.proposals[0].relation.as_deref()), (1, q.clone(), Some(relation)));
    let hints = alignment::hints(&a);
    let want = Correspondence {
        inputs: q.into_iter().chain([equation("old.quantity", "new.quantity")]).collect(),
        outputs: vec![Relation { observation: "result".into(), holds: "old.result.cents == new.result.amount.cents && old.result.quantity == new.result.quantity".into() }],
    };
    assert_eq!(correspondences(&hints, "shop.Pricing#withQuantity"), vec![&want]);
    // The receiver's class changed: `this` is internal and related field by field, and the int result is equal.
    let m = mapping(&a, "shop.Quote#quantity");
    assert_eq!((m.inputs[0].anchor, m.result.kind), (Anchor::Internal, ResultKind::Equal), "{}", alignment::mappings::render(&a.mappings));
    assert_eq!(m.proposals.iter().map(|p| p.fields.clone()).collect::<Vec<_>>(), vec![vec![equation("old.this.cents", "new.this.amount.cents"), equation("old.this.quantity", "new.this.quantity")]]);
    // The same code over a class whose constructor now shifts what it stores: named, and nothing proposed.
    let shifted = |stored: &str| format!("final class Q {{ long cents; {} Q(long cents) {{ this.cents = {stored}; }} static Q same(Q q) {{ return q; }} }}", if stored == "cents" { "" } else { "int pad;" });
    let (old, new) = (shifted("cents"), shifted("cents + 1"));
    let Some(a) = aligned("reshaped-shifted", &[("Q.java", old.as_str())], &[("Q.java", new.as_str())], None) else { return };
    let m = mapping(&a, "Q#same");
    assert!(m.proposals.is_empty() && m.unsupported.iter().any(|u| u.contains("cents")), "{}", alignment::mappings::render(&a.mappings));
    assert!(correspondences(&alignment::hints(&a), "Q#same").is_empty());
}

fn expressions_of(choices: &[alignment::mappings::Choice]) -> Vec<&str> {
    choices.iter().map(|c| c.expression.as_str()).collect()
}

#[test]
fn a_constructor_that_shifts_what_it_stores_or_stores_a_constant_is_never_related() {
    let before = [("Q.java", "final class Q { long cents; Q(long cents) { this.cents = cents; } static long f(Q q) { return q.cents; } }")];
    // The field-level offset: the stored value is shifted, so `old.q.cents == new.q.cents` would hide it, and
    // `old.q.cents == new.q.cents - 1` is never proposed.
    let shifted = [("Q.java", "final class Q { long cents; int pad; Q(long cents) { this.cents = cents + 1; } static long f(Q q) { return q.cents - 1; } }")];
    // A value made inside the argument list is computed too, not passed straight.
    let computed = [
        ("M.java", "record M(long cents) {}"),
        ("Q.java", "final class Q { M amount; Q(long cents) { this.amount = new M(cents * 2); } static long f(Q q) { return q.amount.cents() / 2; } }"),
    ];
    for (name, after, gap) in [("fields-shifted", &shifted[..], "cents"), ("fields-computed", &computed[..], "cents")] {
        let Some(a) = aligned(name, &before, after, None) else { return };
        let f = mapping(&a, "Q#f");
        assert!(f.proposals.is_empty() && f.inputs[0].fields.is_none(), "{name}: {}", alignment::mappings::render(&a.mappings));
        assert!(f.unsupported.iter().any(|u| u.contains(gap)), "{name}: the gap is named: {:?}", f.unsupported);
        assert!(correspondences(&alignment::hints(&a), "Q#f").is_empty());
    }
    // An old value object holding a constant its constructor sets: nothing in the new object is known to match it.
    let constant = [
        ("M.java", "final class M { long cents; int scale; M(long cents) { this.cents = cents; this.scale = 2; } }"),
        ("Q.java", "final class Q { M amount; Q(long cents) { this.amount = new M(cents); } static long f(Q q) { return q.amount.cents * q.amount.scale; } }"),
    ];
    let Some(a) = aligned("fields-constant", &constant, &before, None) else { return };
    let f = mapping(&a, "Q#f");
    assert!(f.proposals.is_empty(), "{}", alignment::mappings::render(&a.mappings));
    assert!(f.unsupported.iter().any(|u| u.contains("amount.scale")), "the constant is named: {:?}", f.unsupported);
}

#[test]
fn a_method_moved_into_the_value_object_takes_it_in_place_of_the_old_object() {
    let (Some(before), Some(after)) = (kernel("moved", "before"), kernel("moved", "after")) else { return };
    let a = alignment::align(&Build::load(&before).unwrap(), &Build::load(&after).unwrap(), Some(&kernel_contract()));
    let cents = mapping(&a, "shop.Quote#cents");
    assert_eq!(cents.after, "shop.Money#cents");
    assert!(cents.unsupported.is_empty(), "{}", alignment::mappings::render(&a.mappings));
    let fc = cents.inputs[0].fields.as_ref().expect("the receiver is related field by field");
    assert_eq!((fc.within.as_deref(), fc.unread.clone()), (Some("amount"), vec!["quantity".to_string()]), "the Money stands for the new Quote's amount, and quantity is never read");
    assert_eq!(cents.proposals.len(), 1);
    assert_eq!(cents.proposals[0].fields, vec![equation("old.this.cents", "new.this.cents")]);
    let hints = alignment::hints(&a);
    assert_eq!(correspondences(&hints, "shop.Money#cents"), vec![&Correspondence { inputs: vec![equation("old.this.cents", "new.this.cents")], outputs: Vec::new() }]);
    let why = &hints.entries.iter().find(|h| h.subject == "shop.Money#cents").unwrap().why;
    assert!(why.iter().any(|w| w.contains("never reads") && w.contains("quantity")), "{why:?}");
}

#[test]
fn a_moved_method_that_reads_what_the_value_object_does_not_keep_is_not_related() {
    let before = [("Q.java", "final class Q { long cents; int n; Q(long cents, int n) { this.cents = cents; this.n = n; } long cents() { return n > 0 ? cents : 0; } }")];
    let after = [
        ("M.java", "record M(long cents) {}"),
        ("Q.java", "final class Q { M amount; int n; Q(M amount, int n) { this.amount = amount; this.n = n; } }"),
    ];
    let Some(a) = aligned("moved-reads-more", &before, &after, None) else { return };
    let cents = mapping(&a, "Q#cents");
    assert_eq!(cents.after, "M#cents", "{}", alignment::mappings::render(&a.mappings));
    assert!(cents.proposals.is_empty() && cents.inputs[0].fields.is_none());
    assert!(cents.unsupported.iter().any(|u| u.contains("n is the new Q's own field n")), "{:?}", cents.unsupported);
}

// Step A3's second half: each proposal checked by the regression proof, by the tool's own checker on methods small
// enough to take well under a second each.

fn proved(name: &str, before: &[(&str, &str)], after: &[(&str, &str)], contract: Option<&PreservationContract>) -> Option<Alignment> {
    if !has_javac() {
        return None;
    }
    let dir = scratch(name);
    let (b, a) = (compile(&dir, "before", before), compile(&dir, "after", after));
    let mut out = alignment::align(&Build::load(&b).unwrap(), &Build::load(&a).unwrap(), contract);
    let settings = Settings { engine: jvmcontract::Engine::Native, timeout_seconds: 120, ..Settings::default() };
    alignment::prove(&mut out, &b, &a, None, &settings).unwrap();
    Some(out)
}

fn proof<'a>(alignment: &'a Alignment, before: &str) -> &'a MappingProof {
    alignment.proofs.iter().find(|p| p.before == before).unwrap_or_else(|| panic!("no proof for {before}: {}", proofs::render(&alignment.proofs)))
}

#[test]
fn the_offset_defect_is_refuted_and_no_mapping_hides_it() {
    let before = [("A.java", "public class A { static long price(long c) { return c; } }")];
    let after = [("A.java", "public class A { static long price(long c) { return c + 1; } }")];
    let Some(a) = proved("prove-offset", &before, &after, None) else { return };
    let p = proof(&a, "A#price");
    assert_eq!(p.settled, Settled::NoneProved, "{}", proofs::render(&a.proofs));
    assert_eq!(p.attempts.len(), 1, "the anchored input has one mapping, itself");
    assert!(matches!(p.attempts[0].tried, Tried::Refuted { .. }), "{:?}", p.attempts[0].tried);
    assert!(matches!(p.attempts[0].evidence, Evidence::Refuted { .. }));
    assert!(p.summary.contains("no mapping proved") && p.summary.contains("refuted by"), "{}", p.summary);
}

#[test]
fn of_a_question_on_type_alone_the_proof_keeps_the_mapping_that_holds() {
    let Some(a) = proved(
        "prove-untied",
        &[("C.java", "public class C { static long span(long x, long y) { return y - x; } }")],
        &[("C.java", "public class C { }"), ("P.java", "public record P(long p, long q) { long span() { return q - p; } }")],
        None,
    ) else {
        return;
    };
    let (m, p) = (mapping(&a, "C#span"), proof(&a, "C#span"));
    let Settled::Proved { proposal, equivalent, note } = &p.settled else { panic!("{}", proofs::render(&a.proofs)) };
    assert_eq!(m.proposals[*proposal].arguments, ["this.p", "this.q"]);
    assert!(equivalent.is_empty());
    assert!(note.as_deref().is_some_and(|n| n.contains("unconfirmed")), "standalone: {note:?}");
    assert!(p.attempts.iter().filter(|t| t.proposal != *proposal).all(|t| matches!(t.tried, Tried::Refuted { .. })), "{}", proofs::render(&a.proofs));
    let hints = alignment::hints(&a);
    let evidence: Vec<&Evidence> = hints.entries.iter().filter(|h| h.subject == "P#span").map(|h| &h.evidence).collect();
    assert_eq!(evidence.iter().filter(|e| matches!(e, Evidence::Proved { .. })).count(), 1, "{evidence:?}");
    assert!(hints.entries.iter().filter(|h| h.subject == "P#span").all(|h| h.intent == Intent::Proposed), "a proof sets the evidence, never the intent");
    assert!(alignment::questions::questions(&hints, None).iter().all(|q| q.subject != "P#span"), "the proof settled the question on type alone");
}

#[test]
fn mappings_a_proof_cannot_tell_apart_are_one_candidate() {
    // A sum: the components in either order give the same result, so both mappings are proved, and the contract
    // can't tell them apart.
    let Some(a) = proved(
        "prove-collapse",
        &[("C.java", "public class C { static long sum(long x, long y) { return x + y; } }")],
        &[("C.java", "public class C { }"), ("P.java", "public record P(long p, long q) { long sum() { return p + q; } }")],
        None,
    ) else {
        return;
    };
    let p = proof(&a, "C#sum");
    let Settled::Proved { proposal, equivalent, .. } = &p.settled else { panic!("{}", proofs::render(&a.proofs)) };
    assert_eq!(equivalent.len(), 1, "{}", proofs::render(&a.proofs));
    let m = mapping(&a, "C#sum");
    let mut both = vec![m.proposals[*proposal].arguments.join(", "), m.proposals[equivalent[0]].arguments.join(", ")];
    both.sort();
    assert_eq!(both, ["this.p, this.q", "this.q, this.p"]);
    let hints = alignment::hints(&a);
    let mine: Vec<&Hint> = hints.entries.iter().filter(|h| h.subject == "P#sum").collect();
    assert_eq!(mine.len(), m.proposals.len() - 1, "the collapsed one is left out");
    let kept = mine.iter().find(|h| matches!(h.evidence, Evidence::Proved { .. })).expect("the proved one");
    assert!(kept.why.iter().any(|w| w.contains("one candidate with it")), "{:?}", kept.why);
}

#[test]
fn several_proved_relations_for_a_changed_result_are_a_question() {
    // The new result is 0 or 1: `result > 0` and `result != 0` both hold, and only a person can say which is meant.
    let Some(a) = proved(
        "prove-asked",
        &[("A.java", "public class A { static boolean positive(int n) { return n > 0; } }")],
        &[("A.java", "public class A { static int positive(int n) { return n > 0 ? 1 : 0; } }")],
        None,
    ) else {
        return;
    };
    let (m, p) = (mapping(&a, "A#positive"), proof(&a, "A#positive"));
    let Settled::Asked { proved } = &p.settled else { panic!("{}", proofs::render(&a.proofs)) };
    let mut relations: Vec<&str> = proved.iter().map(|&i| m.proposals[i].relation.as_deref().unwrap()).collect();
    relations.sort();
    assert_eq!(relations, ["previous == (result != 0)", "previous == (result > 0)"], "{}", proofs::render(&a.proofs));
    // Put as a question: every candidate with what it means and its evidence, a counterexample under each refuted one.
    let hints = alignment::hints(&a);
    let asked = alignment::questions::questions(&hints, None);
    let q = asked.iter().find(|q| q.subject == "A#positive").expect("asked");
    assert!(q.decide.contains("which of the 2 relations proved is intended"), "{}", q.decide);
    assert_eq!(q.answers.len(), m.proposals.len(), "{}", alignment::questions::render(&asked, &[]));
    assert!(q.answers.iter().all(|a| a.means.iter().any(|w| w.starts_with("result: previous == (result ")) && a.approve.contains("--subject 'A#positive' --rank")));
    assert_eq!(q.answers.iter().filter(|a| matches!(a.evidence, Evidence::Proved { .. })).count(), 2);
    assert!(q.answers.iter().filter(|a| !matches!(a.evidence, Evidence::Proved { .. })).all(|a| matches!(&a.evidence, Evidence::Refuted { witness, .. } if witness.contains("positive("))), "{}", alignment::questions::render(&asked, &[]));
}

#[test]
fn the_outcome_rules_count_no_vacuous_proof_and_name_a_person_s_decision() {
    let Some(a) = aligned(
        "settle",
        &[("A.java", "public class A { static boolean expired(long left) { return left <= 0; } }")],
        &[("A.java", "public class A { static long expired(long left) { return left; } }")],
        Some(&PreservationContract {
            subject: "A#expired".into(),
            inputs: vec![ExternalInput { name: "left".into(), ty: "long".into(), derivation: Derivation::Identity }],
            required: vec!["result".into(), "exception".into()],
            approved_changes: Vec::new(),
        }),
    ) else {
        return;
    };
    let m = mapping(&a, "A#expired");
    let attempt = |i: usize, tried: Tried| Attempt { proposal: i, flags: m.proposals[i].flags.clone(), evidence: proofs::evidence(&tried, "k"), tried };
    let vacuous = Tried::Vacuous { why: "no input reaches the calls".into() };
    let refuted = Tried::Refuted { input: "expired(left=0)".into(), before: "true".into(), after: "0".into() };
    let (settled, summary) = proofs::settle(m, &[attempt(0, vacuous.clone()), attempt(1, refuted)]);
    assert_eq!(settled, Settled::NoneProved);
    assert!(summary.contains("#1 vacuous") && summary.contains("#2 refuted by expired(left=0)"), "{summary}");
    assert!(matches!(proofs::evidence(&vacuous, "k"), Evidence::Unknown { .. }), "a vacuous proof is no evidence");
    let (settled, summary) = proofs::settle(m, &[attempt(0, Tried::Proved), attempt(1, Tried::Unknown { why: "out of time".into() })]);
    let Settled::Proved { proposal: 0, note: Some(note), .. } = &settled else { panic!("{settled:?}") };
    assert!(note.contains("a person's decision") && !m.standalone, "{note}");
    assert!(summary.contains("intent still proposed"), "{summary}");
}

// Step A5: the question, well put.

/// The kernel compiled without debug information or parameter names, so every name is `argN` and its fields are
/// matched on type alone.
fn bare_kernel(test: &str, version: &str) -> Option<PathBuf> {
    if !has_javac() {
        return None;
    }
    let src = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/foundations").join(version).join("shop");
    let files: Vec<PathBuf> = ["Pricing.java", "Quote.java", "Money.java"].iter().map(|f| src.join(f)).filter(|p| p.exists()).collect();
    let out = scratch(&format!("bare-{test}-{version}"));
    let status = Command::new("javac").args(["-proc:none", "-d"]).arg(&out).args(&files).status().expect("javac runs");
    assert!(status.success());
    Some(out)
}

#[test]
fn a_lone_candidate_on_type_alone_is_asked_and_what_it_reaches_is_not_called_free() {
    let (Some(b), Some(a)) = (bare_kernel("lone", "before"), bare_kernel("lone", "after")) else { return };
    let aligned = alignment::align(&Build::load(&b).unwrap(), &Build::load(&a).unwrap(), None);
    let total = mapping(&aligned, "shop.Pricing#total");
    let fc = total.inputs[0].fields.as_ref().expect("related field by field");
    let cents = fc.fields.iter().find(|f| f.old == "cents").unwrap();
    assert!(!cents.leads && cents.candidates.len() == 1, "on type alone: {}", alignment::mappings::render(&aligned.mappings));
    assert_eq!(total.proposals.len(), 1);
    // What only the question's candidate reaches is not free, and not called so.
    assert!(fc.free.is_empty() && fc.open == ["amount"], "{fc:?}");
    let hints = alignment::hints(&aligned);
    let h = hints.entries.iter().find(|h| h.subject == "shop.Pricing#total" && matches!(h.content, HintContent::Correspondence { .. })).unwrap();
    assert!(!h.why.iter().any(|w| w.contains("no equation reaches")), "{:?}", h.why);
    let with = mapping(&aligned, "shop.Pricing#withQuantity");
    assert!(!with.result.candidates[0].why.contains("not compared"), "{}", with.result.candidates[0].why);
    // One proposal, but a question: ranked, with what to decide and what approving it means.
    assert_eq!(h.rank, Some(1));
    let ask = h.ask.as_ref().expect("asked");
    assert!(ask.decide.starts_with("which new value the old arg0.cents is: its one candidate, amount.cents, is not sure enough to propose on its own"), "{}", ask.decide);
    assert_eq!(ask.means, ["old.arg0.cents == new.arg0.amount.cents", "new fields of shop.Quote left uncompared: none"]);
    let asked = alignment::questions::questions(&hints, None);
    let subjects: Vec<&str> = asked.iter().map(|q| q.subject.as_str()).collect();
    assert_eq!(subjects, ["shop.Pricing#total", "shop.Pricing#withQuantity", "shop.Quote#quantity"], "{}", alignment::questions::render(&asked, &[]));
    let with_ask = &asked[1];
    assert!(with_ask.decide.contains("which new value the old result's cents is compared with"), "{}", with_ask.decide);
    assert!(with_ask.answers[0].means.iter().any(|m| m == "result: previous.cents == result.amount.cents && previous.quantity == result.quantity"), "{:?}", with_ask.answers[0].means);
    // With names, nothing in the kernel is a person's decision.
    let (Some(nb), Some(na)) = (kernel("lone-named", "before"), kernel("lone-named", "after")) else { return };
    let named = alignment::align(&Build::load(&nb).unwrap(), &Build::load(&na).unwrap(), None);
    let none = alignment::questions::questions(&alignment::hints(&named), None);
    assert!(none.is_empty(), "{}", alignment::questions::render(&none, &[]));
}

#[test]
fn approving_sets_the_intent_only_and_a_file_whose_decisions_are_approved_asks_nothing() {
    let (Some(b), Some(a)) = (bare_kernel("approve", "before"), bare_kernel("approve", "after")) else { return };
    let path = scratch("approve-hints").join("hints.json");
    let run = |args: &[&str]| Command::new(env!("CARGO_BIN_EXE_jvmcontract")).args(args).output().unwrap();
    let align = || {
        let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).args(["align", "--before"]).arg(&b).arg("--after").arg(&a).arg("--hints").arg(&path).output().unwrap();
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).to_string()
    };
    let text = align();
    assert!(text.contains("question  shop.Pricing#total (correspondence): decide which new value the old arg0.cents is"), "{text}");
    assert!(text.contains("3 questions for a person"), "{text}");
    let line = format!("jvmcontract approve --hints {} --kind correspondence --subject 'shop.Pricing#total' --rank 1", path.display());
    assert!(text.contains(&line), "the one line that approves it: {text}");
    let before = alignment::read_hints(&path).unwrap();
    let proposed = before.entries.iter().find(|h| h.subject == "shop.Pricing#total" && matches!(h.content, HintContent::Correspondence { .. })).unwrap().clone();

    let p = path.to_str().unwrap();
    let out = run(&["approve", "--hints", p, "--kind", "correspondence", "--subject", "shop.Pricing#total", "--rank", "1"]);
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    assert!(String::from_utf8_lossy(&out.stdout).contains("intent approved; evidence unchecked"), "{}", String::from_utf8_lossy(&out.stdout));
    let after = alignment::read_hints(&path).unwrap();
    let approved = after.entries.iter().find(|h| h.subject == "shop.Pricing#total" && matches!(h.content, HintContent::Correspondence { .. })).unwrap();
    assert_eq!(approved, &Hint { intent: Intent::Approved, ..proposed }, "only the intent changes: the evidence is still unchecked");
    assert_eq!(after.entries.len(), before.entries.len());

    // A second approval of a decided subject, a subject with no proposal, and an unnamed choice among several are refused.
    assert!(!run(&["approve", "--hints", p, "--kind", "correspondence", "--subject", "shop.Pricing#total", "--rank", "1"]).status.success());
    assert!(!run(&["approve", "--hints", p, "--kind", "correspondence", "--subject", "shop.Nothing#here"]).status.success());

    // A rerun keeps the approval, and no longer asks about it.
    let text = align();
    assert!(!text.contains("question  shop.Pricing#total") && text.contains("2 questions for a person"), "{text}");
    for subject in ["shop.Pricing#withQuantity", "shop.Quote#quantity"] {
        assert!(run(&["approve", "--hints", p, "--kind", "correspondence", "--subject", subject, "--rank", "1"]).status.success());
    }
    let text = align();
    assert!(text.contains("questions: none"), "every decision approved: {text}");
    let hints = alignment::read_hints(&path).unwrap();
    assert_eq!(hints.entries.iter().filter(|h| h.intent == Intent::Approved).count(), 3);
    assert!(hints.entries.iter().all(|h| h.evidence == Evidence::Unchecked), "approving proves nothing");
    // Approved is not proved: each is listed, with its evidence, and not asked.
    assert!(text.contains("approved  shop.Pricing#total (correspondence): not proved under the current claim key; evidence unchecked"), "{text}");
    assert!(text.contains("questions: none; 3 of 3 decisions a person made are not proved under the current claim key"), "{text}");
}

#[test]
fn an_approved_relation_s_evidence_comes_from_a_proof_under_the_current_claim_key_and_goes_stale() {
    if !has_javac() {
        return;
    }
    let dir = scratch("approve-evidence");
    let b = compile(&dir, "before", &[("C.java", "public class C { static long span(long x, long y) { return y - x; } }")]);
    let a = compile(&dir, "after", &[("C.java", "public class C { }"), ("P.java", "public record P(long p, long q) { long span() { return q - p; } }")]);
    let path = dir.join("hints.json");
    let align = |after: &Path, extra: &[&str]| {
        let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).args(["align", "--before"]).arg(&b).arg("--after").arg(after).arg("--hints").arg(&path).args(extra).output().unwrap();
        assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
        String::from_utf8_lossy(&out.stdout).to_string()
    };
    let span = |hints: &Hints| hints.entries.iter().filter(|h| h.subject == "P#span" && matches!(h.content, HintContent::Correspondence { .. })).cloned().collect::<Vec<Hint>>();
    let native = ["--engine", "native", "--timeout", "120"];

    // Static: the two orders tie on type alone, a question. A person approves the one that holds, before any proof.
    let text = align(&a, &native);
    assert!(text.contains("question  P#span (correspondence)"), "{text}");
    let right = span(&alignment::read_hints(&path).unwrap()).into_iter().find(|h| h.ask.as_ref().is_some_and(|k| k.means.iter().any(|m| m == "x = this.p") && k.means.iter().any(|m| m == "y = this.q"))).expect("the order that holds");
    let rank = right.rank.unwrap().to_string();
    let out = Command::new(env!("CARGO_BIN_EXE_jvmcontract")).args(["approve", "--hints"]).arg(&path).args(["--kind", "correspondence", "--subject", "P#span", "--rank", &rank]).output().unwrap();
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    let text = align(&a, &native);
    assert!(!text.contains("question  P#span") && text.contains("approved  P#span (correspondence): not proved under the current claim key; evidence unchecked"), "{text}");

    // A proof gives the approved relation its evidence, under the current claim key; nothing is listed for it.
    let text = align(&a, &["--prove", "--engine", "native", "--timeout", "120"]);
    let approved = span(&alignment::read_hints(&path).unwrap());
    let [approved] = approved.as_slice() else { panic!("the person chose: {approved:?}") };
    let Evidence::Proved { claim_key } = approved.evidence.clone() else { panic!("{:?}\n{text}", approved.evidence) };
    assert_eq!(approved.intent, Intent::Approved);
    assert!(!text.contains("approved  P#span") && text.ends_with("questions: none; 1 decision a person made, proved under the current claim key\n"), "approved and proved asks nothing and lists nothing: {text}");
    // A static rerun under the same settings keeps it: the claim key is the same.
    align(&a, &native);
    assert_eq!(span(&alignment::read_hints(&path).unwrap())[0].evidence, Evidence::Proved { claim_key: claim_key.clone() });
    // Under other settings the key differs, and the proof is no evidence for it: stale, and listed.
    let text = align(&a, &["--engine", "native", "--timeout", "120", "--unwind", "8"]);
    assert_eq!(span(&alignment::read_hints(&path).unwrap())[0].evidence, Evidence::Stale { claim_key: claim_key.clone() });
    assert!(text.contains("approved  P#span (correspondence): not proved under the current claim key; evidence stale"), "{text}");
    // A proof under the current key makes it proved again; then a change to the new build makes it stale.
    align(&a, &["--prove", "--engine", "native", "--timeout", "120"]);
    assert_eq!(span(&alignment::read_hints(&path).unwrap())[0].evidence, Evidence::Proved { claim_key: claim_key.clone() });
    let changed = compile(&dir, "after-changed", &[("C.java", "public class C { }"), ("P.java", "public record P(long p, long q) { long span() { return -(p - q); } }")]);
    align(&changed, &native);
    assert_eq!(span(&alignment::read_hints(&path).unwrap())[0].evidence, Evidence::Stale { claim_key: claim_key.clone() }, "a change to either version");
    // And a proof under the changed build's key: proved for a new key.
    align(&changed, &["--prove", "--engine", "native", "--timeout", "120"]);
    let Evidence::Proved { claim_key: again } = span(&alignment::read_hints(&path).unwrap())[0].evidence.clone() else { panic!() };
    assert_ne!(again, claim_key);
}

#[test]
fn an_approved_relation_a_proof_refutes_is_listed_with_its_counterexample() {
    let Some(a) = proved(
        "approve-refuted",
        &[("C.java", "public class C { static long span(long x, long y) { return y - x; } }")],
        &[("C.java", "public class C { }"), ("P.java", "public record P(long p, long q) { long span() { return q - p; } }")],
        None,
    ) else {
        return;
    };
    let static_hints = alignment::mapping_hints(&a.mappings);
    let wrong = static_hints.entries.iter().find(|h| h.subject == "P#span" && h.ask.as_ref().is_some_and(|k| k.means.iter().any(|m| m == "x = this.q") && k.means.iter().any(|m| m == "y = this.p"))).expect("the order that doesn't hold");
    let (mine, _) = alignment::questions::approve(static_hints.clone(), "correspondence", "P#span", wrong.rank).unwrap();
    let settings = Settings { engine: jvmcontract::Engine::Native, timeout_seconds: 120, ..Settings::default() };
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("alignment").join("approve-refuted");
    let now = alignment::evidence::current(&a, &proofs::Keys::new(&dir.join("before"), &dir.join("after")).unwrap(), &settings);
    let merged = alignment::evidence::refresh(alignment::merge_hints(mine, alignment::hints(&a)), &now);
    let approved = merged.entries.iter().find(|h| h.subject == "P#span" && h.intent == Intent::Approved).unwrap();
    assert!(matches!(&approved.evidence, Evidence::Refuted { witness, .. } if witness.contains("span(")), "{:?}", approved.evidence);
    let decisions = alignment::questions::decisions(&merged);
    let text = alignment::questions::render(&alignment::questions::questions(&merged, None), &decisions);
    assert!(text.contains("approved  P#span (correspondence): not proved under the current claim key; evidence refuted for whole-builds:sha256:"), "{text}");
    assert!(text.contains("counterexample"), "{text}");
    // A method correspondence has no proof of its own: an approved one takes its pair's, proved when a mapping is.
    let methods = alignment::method_hints(&a.methods);
    let rank = methods.entries.iter().find(|h| h.subject == "C#span").expect("a method hint").rank;
    let (methods, _) = alignment::questions::approve(methods, "method", "C#span", rank).unwrap();
    let methods = alignment::evidence::refresh(methods, &now);
    let method = methods.entries.iter().find(|h| h.subject == "C#span" && h.intent == Intent::Approved).unwrap();
    assert!(matches!(method.evidence, Evidence::Proved { .. }), "{:?}", method.evidence);
    // A relation the run doesn't propose at all has no current key: its proof is stale.
    let gone = Hint { content: HintContent::Correspondence { correspondence: Correspondence { inputs: Vec::new(), outputs: Vec::new() } }, evidence: Evidence::Proved { claim_key: "k".into() }, ..approved.clone() };
    let refreshed = alignment::evidence::refresh(Hints { version: alignment::HINTS_VERSION, entries: vec![gone] }, &now);
    assert_eq!(refreshed.entries[0].evidence, Evidence::Stale { claim_key: "k".into() });
}

#[test]
fn approve_needs_a_rank_among_several() {
    let hint = |rank| Hint {
        subject: "A#f".into(),
        content: HintContent::Method { before: "A#f".into(), after: format!("A#g{rank}") },
        source: Source::Inferred,
        intent: Intent::Proposed,
        evidence: Evidence::Unchecked,
        rank: Some(rank),
        why: Vec::new(),
        ask: None,
    };
    let hints = Hints { version: alignment::HINTS_VERSION, entries: vec![hint(1), hint(2)] };
    let e = alignment::questions::approve(hints.clone(), "method", "A#f", None).unwrap_err();
    assert!(e.0.contains("name one with --rank (1, 2)"), "{}", e.0);
    assert!(alignment::questions::approve(hints.clone(), "method", "A#f", Some(3)).is_err());
    assert!(alignment::questions::approve(hints.clone(), "correspondence", "A#f", Some(1)).is_err(), "the kind is part of what is approved");
    let (out, chosen) = alignment::questions::approve(hints, "method", "A#f", Some(2)).unwrap();
    assert_eq!(out.entries, vec![chosen.clone()], "the others are dropped: the person chose");
    assert_eq!((chosen.intent, chosen.rank), (Intent::Approved, Some(2)));
}
