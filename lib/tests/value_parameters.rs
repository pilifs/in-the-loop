//! A value parameter of a regression check (Phase 5 step 1 of `llm-dlc/loops/application-core.md`, the values
//! stream's interface request for V1): a String crosses the whole proof boundary. The own checker makes it of at
//! most the stated bound's code units, the witness is read and rebuilt by the values adapter's rules, replayed in
//! the interpreter and on a JVM, the statement states the bound and the model, and the cache keys both.
//!
//! Each capability's four things: a correct case and a planted defect (the frozen `Codes#vip` of the quote
//! fixture), a named unsupported boundary (JBMC, a property's String, a String result), and cached evidence that
//! moves with the bound.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::equivalence::{self, Confirmed};
use jvmcontract::spec::cache::Reuse;
use jvmcontract::statement::ParameterKind;
use jvmcontract::{property, values, Engine, Verdict};

const NO_JBMC: &str = "/nonexistent/jbmc";

fn tmp(name: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("value-parameters").join(name);
    let _ = std::fs::remove_dir_all(&dir);
    dir
}

fn javac(out: &Path, files: &[PathBuf]) {
    let status = Command::new("javac").args(["-g", "-parameters", "-proc:none", "-nowarn", "-d"]).arg(out).args(files).status().expect("the test needs javac");
    assert!(status.success(), "{} compiles", out.display());
}

/// The quote fixture's `Codes`, as `before`, `after` and the `wrong-prefix` defect build it.
fn codes(build: &str) -> PathBuf {
    static ROOT: OnceLock<PathBuf> = OnceLock::new();
    let root = ROOT.get_or_init(|| {
        let root = tmp("codes");
        let quote = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/application-core/quote");
        for (name, source) in [("before", "before"), ("after", "after"), ("wrong-prefix", "defects/wrong-prefix")] {
            javac(&root.join(name), &[quote.join(source).join("quotes/Codes.java")]);
        }
        root
    });
    root.join(build)
}

/// Two versions of a small class of String methods, `before` and `after`.
fn strings() -> &'static Path {
    static ROOT: OnceLock<PathBuf> = OnceLock::new();
    ROOT.get_or_init(|| {
        let root = tmp("strings");
        for (name, lone) in [("before", "false"), ("after", "s.length() == 1 && s.charAt(0) == '\\uDBFF'")] {
            let source = root.join("src").join(name).join("s/Text.java");
            std::fs::create_dir_all(source.parent().unwrap()).unwrap();
            std::fs::write(&source, format!("package s;\npublic final class Text {{\n    public static boolean lone(String s) {{ return {lone}; }}\n    public static String echo(String s) {{ return s; }}\n    public static int size(String s) {{ return s.length(); }}\n}}\n")).unwrap();
            javac(&root.join(name), &[source]);
        }
        root
    })
}

fn options(before: &Path, after: &Path, target: &str, work: &str) -> equivalence::Options {
    let mut o = equivalence::Options::new(before, after, target);
    o.engine = Engine::Native;
    o.jbmc = NO_JBMC.into();
    o.work = Some(tmp(work));
    o
}

/// The rewrite of `Codes#vip` with `length` and `charAt` is proved over every String of at most 8 code units, and
/// the shorter prefix is refuted on a witness that depends on content, replayed in the interpreter and on a JVM,
/// and typed in the shared witness form. The statement states the value domain, its bound and the String model.
#[test]
fn a_string_parameter_is_proved_and_its_defect_refuted_on_a_witness_replayed_on_a_jvm() {
    let proved = equivalence::run(&options(&codes("before"), &codes("after"), "quotes.Codes#vip", "vip-after")).unwrap();
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);
    assert!(proved.output.contains("code: String of ≤ 8 code units, not null"), "{}", proved.output);
    let stated = proved.stated.as_ref().expect("a statement");
    let code = &stated.domain.parameters[0];
    assert_eq!((code.kind, code.max_length, code.null), (ParameterKind::Value, Some(8), false));
    assert_eq!(stated.bounds.max_value_length, Some(8));
    assert_eq!(stated.models.values, vec![values::string_model()]);

    let refuted = equivalence::run(&options(&codes("before"), &codes("wrong-prefix"), "quotes.Codes#vip", "vip-wrong-prefix")).unwrap();
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    assert!(refuted.replay.as_ref().is_some_and(|r| r.reproduced), "{}", refuted.output);
    let c = refuted.counterexample.as_ref().expect("a witness");
    assert_eq!(c.jvm.as_deref(), Some(jvm_release().as_str()), "run on a JVM: {}", refuted.output);
    let value = c.inputs[0].value.clone().expect("the String's value");
    let witness: jvmcontract::spec::plans::WitnessValue = serde_json::from_value(value).expect("the shared witness form");
    let jvmcontract::spec::plans::WitnessValue::String { units } = witness else { panic!("a String: {c:?}") };
    // `before` wants "VIP", the defect only "VI": a witness starts with "VI" and isn't "VIP…".
    assert!(units.starts_with(&[86, 73]) && units.get(2) != Some(&80), "{units:?}");
    assert!(c.input.starts_with("vip(code=\"VI"), "{}", c.input);
}

fn jvm_release() -> String {
    let out = Command::new("java").arg("-XshowSettings:properties").arg("-version").output().expect("java runs");
    let text = String::from_utf8_lossy(&out.stderr).into_owned();
    text.lines().find_map(|l| l.trim().strip_prefix("java.version = ").map(str::to_string)).expect("java.version")
}

/// A witness's code units cross to the JVM and back as they are: a lone high surrogate, which no well-formed text
/// holds, is the witness `after`'s new branch needs, rendered by its escape, and the JVM's harness fails on it too.
#[test]
fn a_witness_with_an_isolated_surrogate_replays_on_the_jvm_unit_for_unit() {
    let root = strings();
    let o = equivalence::run(&options(&root.join("before"), &root.join("after"), "s.Text#lone", "lone")).unwrap();
    assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
    let c = o.counterexample.as_ref().unwrap();
    assert!(c.jvm.is_some(), "run on a JVM: {}", o.output);
    let value = c.inputs[0].value.clone().unwrap();
    let units: Vec<u16> = serde_json::from_value(value["units"].clone()).unwrap();
    assert_eq!(units, vec![0xdbff]);
    assert_eq!(c.input, "lone(s=\"\\udbff\")");
}

/// What the wiring leaves out is refused by name, never decided otherwise: JBMC, whose Strings are its own model
/// (`--engine jbmc` refused, and under `--confirm` not asked); a property over a String, whose expressions can't
/// read one; and a String result, which the harness compares with `Objects.equals`, a gap the own checker refuses.
#[test]
fn a_string_parameter_is_the_own_checkers_alone_and_what_is_left_out_is_named() {
    let mut jbmc = options(&codes("before"), &codes("after"), "quotes.Codes#vip", "vip-jbmc");
    jbmc.engine = Engine::Jbmc;
    let o = equivalence::run(&jbmc).unwrap();
    assert_eq!(o.verdict, Verdict::Unverifiable);
    assert!(o.problem.as_deref().unwrap_or_default().contains("JBMC's Strings are its own model"), "{}", o.output);

    let mut confirm = options(&codes("before"), &codes("after"), "quotes.Codes#vip", "vip-confirm");
    confirm.engine = Engine::Auto;
    confirm.confirm = true;
    let o = equivalence::run(&confirm).unwrap();
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let c = o.search.as_ref().and_then(|s| s.confirmation.as_ref()).expect("a confirmation record");
    assert_eq!(c.status, Confirmed::NotAsked, "{c:?}");
    assert!(c.reason.as_deref().unwrap_or_default().contains("a String parameter"), "{c:?}");

    let mut p = property::Options::new(&[codes("after")], "quotes.Codes#vip");
    p.engine = Engine::Native;
    p.jbmc = NO_JBMC.into();
    p.work = Some(tmp("vip-property"));
    let o = property::run(&p).unwrap();
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("java.lang.String"), "{}", o.output);

    let root = strings();
    let mut echo = options(&root.join("before"), &root.join("after"), "s.Text#echo", "echo");
    echo.shared_callees = false;
    let o = equivalence::run(&echo).unwrap();
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("java.util.Objects.equals"), "{}", o.output);
}

/// A String claim's cached evidence: an exact rerun reuses the proof, and the same claim under another bound is
/// another key, proved again.
#[test]
fn a_string_parameters_cached_evidence_moves_with_its_bound() {
    let root = strings();
    let cache = tmp("cache");
    let run = |bound: u32, work: &str| {
        let mut o = options(&root.join("before"), &root.join("after"), "s.Text#size", work);
        o.shared_callees = false;
        o.cache = Some(cache.clone());
        o.max_array_length = bound;
        equivalence::run(&o).unwrap()
    };
    let key = |o: &equivalence::Outcome| match &o.reuse {
        Some(Reuse::Exact { key, .. }) => Some(key.clone()),
        _ => None,
    };
    let cold = run(8, "size-cold");
    assert_eq!(cold.verdict, Verdict::Verified, "{}", cold.output);
    assert!(key(&cold).is_none(), "{}", cold.output);
    let rerun = run(8, "size-rerun");
    assert_eq!(rerun.verdict, Verdict::Verified);
    let hit = key(&rerun).unwrap_or_else(|| panic!("an exact hit: {}", rerun.output));
    let narrower = run(5, "size-narrower");
    assert_eq!(narrower.verdict, Verdict::Verified);
    assert!(key(&narrower).is_none(), "another bound is another claim: {}", narrower.output);
    assert_eq!(key(&run(5, "size-narrower-rerun")).is_some_and(|k| k != hit), true, "and has a key of its own");
}

/// The basket fixture's `Basket` and `Line`, as `before`, `after` and three defects build them.
fn basket(build: &str) -> PathBuf {
    static ROOT: OnceLock<PathBuf> = OnceLock::new();
    let root = ROOT.get_or_init(|| {
        let root = tmp("basket");
        let fixture = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/application-core/basket");
        for name in ["before", "after", "duplicate-skipped", "alias-blind", "copied-first"] {
            let (base, overlay) = match name {
                "before" | "after" => (fixture.join(name), None),
                defect => (fixture.join("after"), Some(fixture.join("defects").join(defect))),
            };
            let line = base.join("basket/Line.java");
            let kernels = overlay.map(|o| o.join("basket/Basket.java")).unwrap_or_else(|| base.join("basket/Basket.java"));
            javac(&root.join(name), &[line, kernels]);
        }
        root
    });
    root.join(build)
}

fn basket_options(build: &str, target: &str, work: &str) -> equivalence::Options {
    let mut o = options(&basket("before"), &basket(build), target, work);
    o.max_array_length = 3;
    o
}

/// A list parameter's elements (V2): a rewrite that walks the list by index proved over every `List.of` of at most 3
/// lines, any two of them one object; the defect that counts a line given twice once, and the one that reads two
/// lines before clearing either, each refuted on a witness whose elements are one object, replayed in the
/// interpreter and on a JVM. The witness's list is the shared form's list of plan nodes, and the statement states
/// the value domain, its bound and the list model.
#[test]
fn a_list_parameter_is_proved_and_its_defects_refuted_on_witnesses_of_one_object_twice() {
    let proved = equivalence::run(&basket_options("after", "basket.Basket#total", "total-after")).unwrap();
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);
    assert!(proved.output.contains("lines: an immutable List.of of ≤ 3 elements, not null, each a Line made by its constructor"), "{}", proved.output);
    let stated = proved.stated.as_ref().expect("a statement");
    let lines = &stated.domain.parameters[0];
    assert_eq!((lines.kind, lines.max_length, lines.null, lines.ty.as_str()), (ParameterKind::Value, Some(3), false, "java.util.List<basket.Line>"));
    assert_eq!(stated.bounds.max_value_length, Some(3));
    assert_eq!(stated.models.values, vec![values::list_model()]);
    assert_eq!(stated.domain.input_objects, Some((4, 4)), "three lines and the list made in each version");

    for (build, target, before, after) in [("duplicate-skipped", "basket.Basket#total", "2", "1"), ("alias-blind", "basket.Basket#clearAll", "1", "2")] {
        let o = equivalence::run(&basket_options(build, target, &format!("{build}-refuted"))).unwrap();
        assert_eq!(o.verdict, Verdict::Violation, "{build}: {}", o.output);
        assert!(o.replay.as_ref().is_some_and(|r| r.reproduced), "{build}: {}", o.output);
        let c = o.counterexample.as_ref().expect("a witness");
        assert_eq!(c.jvm.as_deref(), Some(jvm_release().as_str()), "{build} run on a JVM: {}", o.output);
        // One line given twice: the second element is the first's object.
        assert!(c.input.contains("the same object as lines[0]"), "{build}: {}", c.input);
        assert!(o.output.contains(&format!("before: {before}")) && o.output.contains(&format!("after:  {after}")), "{build}: {}", o.output);
        let list = &c.call.arguments[0];
        let witness: jvmcontract::spec::plans::WitnessValue = serde_json::from_value(list.value.clone().expect("the list's value")).expect("the shared witness form");
        let jvmcontract::spec::plans::WitnessValue::List { elements } = witness else { panic!("a list: {list:?}") };
        assert!(elements.len() >= 2 && elements[0] == elements[1], "{build}: {elements:?}");
        assert_eq!(list.components.as_ref().map(Vec::len), Some(3), "{build}: the three objects the elements are picked among");
    }
}

/// Kernels over lists the adapter doesn't take, or takes only part of: a raw list, a wildcard's, one of elements
/// that hold an array, and two whose result may be an element, one of the element class (`firstOf`, compared for
/// identity with each element) and one of `Object` (`anyOf`, which the check doesn't follow).
fn kernels() -> &'static Path {
    static ROOT: OnceLock<PathBuf> = OnceLock::new();
    ROOT.get_or_init(|| {
        let root = tmp("kernels");
        for (name, item) in [("before", "this.n = n;"), ("after", "this.n = n;"), ("after-item", "int m = n;\n        this.n = m;")] {
            let src = root.join("src").join(name).join("l");
            std::fs::create_dir_all(&src).unwrap();
            std::fs::write(src.join("Item.java"), format!("package l;\npublic final class Item {{\n    int n;\n    public Item(int n) {{\n        {item}\n    }}\n}}\n")).unwrap();
            std::fs::write(src.join("Box.java"), "package l;\npublic final class Box {\n    int[] cells;\n    public Box(int n) {\n        cells = new int[] {n};\n    }\n}\n").unwrap();
            std::fs::write(src.join("Kernels.java"), "package l;\nimport java.util.List;\npublic final class Kernels {\n    public static int count(List<Item> xs) { int c = 0; for (Item x : xs) { c += x.n; } return c; }\n    @SuppressWarnings(\"rawtypes\") public static int raw(List xs) { return xs.size(); }\n    public static int wild(List<? extends Item> xs) { return xs.size(); }\n    public static int boxes(List<Box> xs) { return xs.size(); }\n    public static Item firstOf(List<Item> xs) { return xs.isEmpty() ? null : xs.get(0); }\n    public static Object anyOf(List<Item> xs) { return xs.isEmpty() ? null : xs.get(0); }\n}\n").unwrap();
            javac(&root.join(name), &[src.join("Item.java"), src.join("Box.java"), src.join("Kernels.java")]);
        }
        root
    })
}

fn kernel_options(after: &str, target: &str, work: &str) -> equivalence::Options {
    let root = kernels();
    let mut o = options(&root.join("before"), &root.join(after), target, work);
    o.max_array_length = 3;
    o.shared_callees = false;
    o
}

/// What the list wiring leaves out is refused by name, never decided otherwise: JBMC, which runs the list models its
/// own way (`--engine jbmc` refused, and under `--confirm` not asked); a list a property's harness would make; a raw
/// list, a wildcard's and one whose elements hold an array, whose elements the adapter can't make or whose
/// references aren't observed; and a result that may be one of the elements but isn't followed into its fields
/// (an `Object`), whose identity with them couldn't be observed.
#[test]
fn a_list_parameter_is_the_own_checkers_alone_and_what_is_left_out_is_named() {
    let mut jbmc = basket_options("after", "basket.Basket#total", "total-jbmc");
    jbmc.engine = Engine::Jbmc;
    let o = equivalence::run(&jbmc).unwrap();
    assert_eq!(o.verdict, Verdict::Unverifiable);
    assert!(o.problem.as_deref().unwrap_or_default().contains("JBMC runs the list models its own way"), "{}", o.output);

    let mut confirm = basket_options("after", "basket.Basket#total", "total-confirm");
    confirm.engine = Engine::Auto;
    confirm.confirm = true;
    let o = equivalence::run(&confirm).unwrap();
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let c = o.search.as_ref().and_then(|s| s.confirmation.as_ref()).expect("a confirmation record");
    assert_eq!(c.status, Confirmed::NotAsked, "{c:?}");
    assert!(c.reason.as_deref().unwrap_or_default().contains("a list parameter"), "{c:?}");

    let mut p = property::Options::new(&[basket("after")], "basket.Basket#total");
    p.engine = Engine::Native;
    p.jbmc = NO_JBMC.into();
    p.work = Some(tmp("total-property"));
    let o = property::run(&p).unwrap();
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.problem.as_deref().unwrap_or_default().contains("java.util.List"), "{}", o.output);

    for (target, words) in [("raw", "a raw List"), ("wild", "not a wildcard"), ("boxes", "a field of an array or an object"), ("anyOf", "an identity it couldn't observe")] {
        let o = equivalence::run(&kernel_options("after", &format!("l.Kernels#{target}"), target)).unwrap();
        assert_eq!(o.verdict, Verdict::Unverifiable, "{target}: {}", o.output);
        assert!(o.problem.as_deref().unwrap_or_default().contains(words), "{target}: {}", o.output);
    }
}

/// A list claim's cached evidence: an exact rerun reuses the proof; the same claim under another bound is another
/// key, and so is one whose elements' constructor was edited, though it means the same, since the constructor is
/// among the claim's roots.
#[test]
fn a_list_parameters_cached_evidence_moves_with_its_bound_and_its_elements_constructor() {
    let cache = tmp("list-cache");
    let run = |after: &str, bound: u32, work: &str| {
        let mut o = kernel_options(after, "l.Kernels#count", work);
        o.cache = Some(cache.clone());
        o.max_array_length = bound;
        equivalence::run(&o).unwrap()
    };
    let key = |o: &equivalence::Outcome| match &o.reuse {
        Some(Reuse::Exact { key, .. }) => Some(key.clone()),
        _ => None,
    };
    let cold = run("after", 3, "count-cold");
    assert_eq!(cold.verdict, Verdict::Verified, "{}", cold.output);
    assert!(key(&cold).is_none(), "{}", cold.output);
    let hit = key(&run("after", 3, "count-rerun")).expect("an exact hit");
    let narrower = run("after", 2, "count-narrower");
    assert_eq!(narrower.verdict, Verdict::Verified);
    assert!(key(&narrower).is_none(), "another bound is another claim: {}", narrower.output);
    let edited = run("after-item", 3, "count-edited");
    assert_eq!(edited.verdict, Verdict::Verified, "{}", edited.output);
    assert!(key(&edited).is_none(), "an edited element constructor is another claim: {}", edited.output);
    assert!(key(&run("after-item", 3, "count-edited-rerun")).is_some_and(|k| k != hit), "and has a key of its own");
}

/// A frozen basket claim (`tests/fixtures/application-core/golden/`), to be changed by a test.
fn basket_claim(name: &str) -> jvmcontract::spec::CanonicalClaim {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join(format!("tests/fixtures/application-core/golden/{name}.json"));
    serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap()
}

/// Each version's plan of a claim, to be changed by a test.
fn plans(claim: &mut jvmcontract::spec::CanonicalClaim) -> [&mut jvmcontract::spec::plans::ConstructionPlan; 2] {
    let Some(jvmcontract::spec::Construction::Planned { before, after }) = claim.domain.as_mut().map(|d| &mut d.made_by) else { panic!("a planned domain") };
    [before, after]
}

/// The list domain of a plan's root `lines`, to be changed by a test.
fn list_domain(plan: &mut jvmcontract::spec::plans::ConstructionPlan) -> &mut jvmcontract::spec::plans::ValueDomain {
    match &mut plan.roots[0].value {
        jvmcontract::spec::plans::PlanValue::Adapted { domain, .. } => domain,
        other => panic!("an adapted root: {other:?}"),
    }
}

/// A planned domain's adapted list root (V2, through the domain gate): the claim's own bound of 3 lines, not the
/// check's array bound of 4, and the result compared with each of the list's objects for identity, so that
/// `identity:result==lines[0]` is preserved by the rewrite and refuted where the result is a copy of the first line
/// (under the frozen `basket-first-claim` with each version's allocation bound raised to the copy's 2 objects, the
/// `Line` and the exception its constructor may throw), on a witness replayed on a JVM. A kernel returning the
/// element class without a plan is proved with the same identities stated.
#[test]
fn a_planned_list_root_has_its_own_bound_and_the_results_identity_with_its_elements_is_observed() {
    let mut claim = basket_claim("basket-first-claim");
    let bounds = &mut claim.domain.as_mut().unwrap().bounds;
    bounds.before.allocations = 2;
    bounds.after.allocations = 2;
    let check = |claim: &jvmcontract::spec::CanonicalClaim, build: &str| jvmcontract::spec::heap::check(claim, &basket("before"), &basket(build)).unwrap();
    let proved = check(&claim, "after");
    assert_eq!(proved.verdict, jvmcontract::spec::Verdict::Verified, "{proved:?}");
    assert!(proved.domain.contains("lines: an immutable List.of of ≤ 3 elements"), "the plan's bound, not the check's 4: {}", proved.domain);
    let state = |o: &jvmcontract::spec::Outcome, id: &str| o.accounting.iter().find(|a| a.observation == id).map(|a| a.state);
    assert_eq!(state(&proved, "identity:result==lines[0]"), Some(jvmcontract::spec::ObservationState::Preserved), "{proved:?}");

    let copied = check(&claim, "copied-first");
    assert_eq!(copied.verdict, jvmcontract::spec::Verdict::Refuted, "{copied:?}");
    assert_eq!(state(&copied, "identity:result==lines[0]"), Some(jvmcontract::spec::ObservationState::Refuted), "{copied:?}");
    assert_eq!(state(&copied, "result"), Some(jvmcontract::spec::ObservationState::Unresolved), "the copy's fields are the first line's: {copied:?}");
    assert!(copied.witness.as_deref().is_some_and(|w| w.contains("lines=List.of(")), "{copied:?}");

    // Under the frozen bound of 0, the copy's code is outside the claim: unresolved, never refuted or proved.
    let frozen = check(&basket_claim("basket-first-claim"), "copied-first");
    assert_eq!(frozen.verdict, jvmcontract::spec::Verdict::Unresolved, "{frozen:?}");

    let o = equivalence::run(&kernel_options("after", "l.Kernels#firstOf", "first-of")).unwrap();
    assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    let identities = &o.stated.as_ref().expect("a statement").observations.identities;
    assert_eq!(identities, &["result == xs[0]", "result == xs.m1", "result == xs.m2"], "{}", o.output);
}

/// What a planned list root leaves out is refused by name before any check, never run as another domain: a list
/// that may be null, an adapted String root, a list stated under another model or a stronger level than the
/// tool's, a list of more than the adapter's 10, roots that differ between the versions, and elements of another
/// class than the parameter's.
#[test]
fn a_planned_list_roots_unsupported_forms_are_refused_by_name() {
    let refused = |what: &str, change: &dyn Fn(&mut jvmcontract::spec::CanonicalClaim), words: &str| {
        let mut claim = basket_claim("basket-total-claim");
        change(&mut claim);
        let u = jvmcontract::spec::heap::check(&claim, &basket("before"), &basket("after")).expect_err(what);
        assert!(u.what.contains(words), "{what}: {u}");
    };
    fn both(c: &mut jvmcontract::spec::CanonicalClaim, f: &dyn Fn(&mut jvmcontract::spec::plans::ValueDomain)) {
        for p in plans(c) {
            f(list_domain(p));
        }
    }
    refused("a null list", &|c| both(c, &|d| d.nullable = true), "a list that may be null");
    refused("a String root", &|c| both(c, &|d| d.kind = jvmcontract::spec::plans::ValueKind::String), "an adapted String root");
    refused("another model", &|c| both(c, &|d| d.model.source = "an earlier list model".into()), "evidence of another model's semantics isn't this one's");
    refused("a stronger level", &|c| both(c, &|d| d.model.level = jvmcontract::spec::plans::EvidenceLevel::Proved), "never borrows a stronger level");
    refused("too long", &|c| both(c, &|d| d.max_length = 11), "of at most 10");
    refused("roots that differ", &|c| list_domain(plans(c)[0]).max_length = 2, "both versions are given the same list");
    refused(
        "another element class",
        &|c| both(c, &|d| d.kind = jvmcontract::spec::plans::ValueKind::List { element: jvmcontract::spec::plans::ElementKind::Object { class: "basket.Basket".into() } }),
        "a plan's elements are of the parameter's element class",
    );
}

/// A planned list claim's cached evidence: an exact rerun reuses it, and the same claim with its list bounded at 2
/// is another key.
#[test]
fn a_planned_list_claims_cached_evidence_moves_with_the_lists_bound() {
    let cache = tmp("planned-list-cache");
    let run = |claim: &jvmcontract::spec::CanonicalClaim| {
        let mut reused = jvmcontract::spec::heap::Reused::default();
        let o = jvmcontract::spec::heap::check_with(claim, &basket("before"), &basket("after"), Some(&cache), &mut reused).unwrap();
        assert_eq!(o.verdict, jvmcontract::spec::Verdict::Verified, "{o:?}");
        reused
    };
    let claim = basket_claim("basket-total-claim");
    let cold = run(&claim);
    assert!(cold.key.is_some() && cold.exact.is_none(), "{cold:?}");
    let rerun = run(&claim);
    assert!(rerun.exact.is_some(), "an exact hit: {rerun:?}");
    let mut shorter = claim.clone();
    for p in plans(&mut shorter) {
        list_domain(p).max_length = 2;
    }
    let other = run(&shorter);
    assert!(other.exact.is_none() && other.key.is_some() && other.key != cold.key, "another bound is another claim: {other:?}");
}
