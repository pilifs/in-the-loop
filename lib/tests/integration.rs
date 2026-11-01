//! End-to-end tests over Java fixtures compiled with `javac` at test time; some also need JBMC or TLC. A missing tool
//! fails the test that needs it, unless JVMCONTRACT_SKIP_MISSING_TOOLS=1 asks for the skip: a test that skips passes, so
//! a green run on a broken PATH would otherwise prove nothing.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::classpath::ClassPath;
use jvmcontract::contract::Contract;
use jvmcontract::verifier::{self, ContractsRun, Verifier};
use jvmcontract::{capabilities, equivalence, property, tla, Verdict};

fn has(program: &str) -> bool {
    let found = Command::new(program).arg("--version").output().map(|o| o.status.success()).unwrap_or(false);
    if !found {
        missing(program);
    }
    found
}

/// Fails the test, unless skipping was asked for. A test that gets past this has to return without checking anything.
fn missing(tool: &str) {
    let skip = std::env::var("JVMCONTRACT_SKIP_MISSING_TOOLS").is_ok_and(|v| v == "1");
    assert!(skip, "{tool} not found: put it on the PATH, or set JVMCONTRACT_SKIP_MISSING_TOOLS=1 to skip the tests that need it");
}

fn target_tmp() -> PathBuf {
    PathBuf::from(env!("CARGO_TARGET_TMPDIR"))
}

/// Compiles Java sources into a directory under the target folder, once per source set.
fn compile(name: &str, sources: &[PathBuf]) -> Option<PathBuf> {
    if !has("javac") {
        eprintln!("javac not found; skipping");
        return None;
    }
    let out = target_tmp().join(format!("classes-{name}"));
    let _ = std::fs::remove_dir_all(&out);
    std::fs::create_dir_all(&out).unwrap();
    let status = Command::new("javac")
        .args(["-parameters", "-g", "-proc:none", "-d"])
        .arg(&out)
        .args(sources)
        .status()
        .expect("javac runs");
    assert!(status.success(), "fixtures compile");
    Some(out)
}

fn java_files(dir: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    for entry in std::fs::read_dir(dir).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            out.extend(java_files(&path));
        } else if path.extension().is_some_and(|e| e == "java") {
            out.push(path);
        }
    }
    out.sort();
    out
}

fn fixtures() -> Option<&'static Path> {
    static DIR: OnceLock<Option<PathBuf>> = OnceLock::new();
    DIR.get_or_init(|| {
        let src = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/java");
        compile("fixtures", &java_files(&src))
    })
    .as_deref()
}

fn classpath(dir: &Path) -> ClassPath {
    let mut cp = ClassPath::new();
    cp.add(dir).unwrap();
    cp.with_default_jdk()
}

fn derive(dir: &Path, target: &str) -> verifier::Derivation {
    Verifier::new(&classpath(dir)).derive(target)
}

fn contract(dir: &Path, target: &str) -> Contract {
    let d = derive(dir, target);
    assert!(d.problem.is_none(), "{target}: {:?}", d.problem);
    d.contract.unwrap()
}

fn problem(dir: &Path, target: &str) -> String {
    let d = derive(dir, target);
    d.problem.unwrap_or_else(|| panic!("{target} should be refused"))
}

#[test]
fn a_pure_finite_method_gets_a_complete_contract() {
    let Some(dir) = fixtures() else { return };
    let c = contract(dir, "fixtures.TrafficLight#step");
    // Light: 3 + null; Command: Next, Hold(false), Hold(true), null.
    assert_eq!(c.cases.len(), 16);
    assert_eq!(c.domain.as_deref(), Some("Light (4) × Command (4) = 16 cases"));
    assert_eq!(c.outcome("step(RED, Next[])"), Some("GREEN"));
    assert_eq!(c.outcome("step(RED, Hold[flashing=true])"), Some("AMBER"));
    assert_eq!(c.outcome("step(RED, Hold[flashing=false])"), Some("RED"));
    assert_eq!(c.outcome("step(RED, null)"), Some("throws NullPointerException"));
    assert_eq!(c.outcome("step(null, Next[])"), Some("throws NullPointerException"));
    let d = derive(dir, "fixtures.TrafficLight#step");
    let purity = d.purity.unwrap();
    assert!(purity.trusted.contains("java.lang.runtime.SwitchBootstraps.typeSwitch"), "{:?}", purity.trusted);
    assert!(d.line > 1, "the derivation carries the method's first line");
}

#[test]
fn impure_or_unbounded_methods_are_refused_with_the_reason() {
    let Some(dir) = fixtures() else { return };
    assert!(problem(dir, "fixtures.TrafficLight#counting").contains("writes static field"));
    assert!(problem(dir, "fixtures.TrafficLight#night").contains("java.lang.System.nanoTime, which is not known to be pure"));
    assert!(problem(dir, "fixtures.TrafficLight#sensed").contains("open to implementations outside the analysed code"));
    assert!(problem(dir, "fixtures.TrafficLight#doubled").contains("input domain is not finite"));
    assert!(problem(dir, "fixtures.Nothing#f").contains("class not found"));
    assert!(problem(dir, "fixtures.TrafficLight#missing").contains("found 0"));
}

#[test]
fn the_interpreter_models_strings_records_switches_lambdas_and_exceptions() {
    let Some(dir) = fixtures() else { return };
    let c = contract(dir, "fixtures.Features#quote");
    assert_eq!(c.cases.len(), 7); // 3 tiers × 2 rush + null
    assert_eq!(c.outcome("quote(Order[tier=BASIC, rush=false])"), Some("Quote[label=\"basic\", cents=1000, tiers=[BASIC]]"));
    assert_eq!(c.outcome("quote(Order[tier=PRO, rush=true])"), Some("Quote[label=\"pro-rush\", cents=5250, tiers=[PRO]]"));
    assert_eq!(c.outcome("quote(null)"), Some("throws NullPointerException"));

    let c = contract(dir, "fixtures.Features#describe");
    assert_eq!(c.outcome("describe(Circle[big=true])"), Some("\"big circle\""));
    assert_eq!(c.outcome("describe(Square[tier=BASIC])"), Some("\"basic square\""));
    assert_eq!(c.outcome("describe(Square[tier=PRO])"), Some("\"square+square+square\""));
    assert_eq!(c.outcome("describe(null)"), Some("throws NullPointerException"));

    let c = contract(dir, "fixtures.Features#lambdas");
    assert_eq!(c.outcome("lambdas(PLUS)"), Some("43"));

    let c = contract(dir, "fixtures.Features#maybe");
    assert_eq!(c.outcome("maybe(BASIC)"), Some("<java.util.Optional>"));
    assert_eq!(c.outcome("maybe(PRO)"), Some("<java.util.Optional>"));

    let c = contract(dir, "fixtures.Features#throwsWithMessage");
    assert_eq!(c.outcome("throwsWithMessage(PRO)"), Some("throws IllegalStateException(\"pro: 2\")"));
    assert_eq!(c.outcome("throwsWithMessage(PLUS)"), Some("1"));

    let c = contract(dir, "fixtures.Features#sum");
    assert_eq!(c.outcome("sum(PRO)"), Some("5"));
    assert_eq!(c.outcome("sum(null)"), Some("throws NullPointerException"));

    let c = contract(dir, "fixtures.Features#same");
    assert_eq!(c.outcome("same(Order[tier=BASIC, rush=false], Order[tier=BASIC, rush=false])"), Some("true"));
    assert_eq!(c.outcome("same(Order[tier=BASIC, rush=false], Order[tier=BASIC, rush=true])"), Some("false"));
    assert_eq!(c.outcome("same(null, null)"), Some("throws NullPointerException"));

    let c = contract(dir, "fixtures.Features#ratio");
    assert_eq!(c.outcome("ratio(PLUS, BASIC)"), Some("throws ArithmeticException(\"/ by zero\")"));
    assert_eq!(c.outcome("ratio(PRO, PLUS)"), Some("200"));
}

#[test]
fn an_instance_method_of_an_enum_takes_the_receiver_as_its_domain() {
    let Some(dir) = fixtures() else { return };
    let c = contract(dir, "fixtures.Features$Tier#discount");
    assert_eq!(c.domain.as_deref(), Some("this: Tier (3) = 3 cases"));
    assert_eq!(c.outcome("PRO.discount()"), Some("25"));
}

#[test]
fn the_effect_monitor_catches_writes_the_static_analysis_misses() {
    let Some(dir) = fixtures() else { return };
    let p = problem(dir, "fixtures.Features#impure");
    assert!(p.contains("not pure: the method writes an array element of an object that existed before the call"), "{p}");
}

#[test]
fn unbounded_recursion_is_refused_not_run_forever() {
    let Some(dir) = fixtures() else { return };
    let p = problem(dir, "fixtures.Features#loops");
    assert!(p.contains("did not finish"), "{p}");
}

#[test]
fn capability_contracts_list_each_entry_point_with_its_call_site() {
    let Some(dir) = fixtures() else { return };
    let report = capabilities::analyse(&[dir.to_path_buf()]).unwrap();
    let entries = report.entries();
    assert!(entries.contains("reflection: fixtures.Capable.loadByName calls java.lang.Class.forName"), "{entries:?}");
    assert!(entries.contains("reflection: fixtures.Capable.loadByName calls java.lang.Class.getDeclaredConstructor"));
    assert!(entries.contains("clock: fixtures.Capable.stamp calls java.time.Instant.now"));
    assert!(entries.contains("randomness: fixtures.Capable.stamp calls java.util.UUID.randomUUID"));
    assert!(entries.contains("environment: fixtures.Capable.home calls java.lang.System.getenv"));
    assert!(entries.contains("clock: fixtures.TrafficLight.night calls java.lang.System.nanoTime"));
    assert!(!entries.iter().any(|e| e.contains("Capable.pure")), "Math.abs is not a capability");
    assert!(report.libraries.is_empty());
    assert!(report.uses["reflection"].iter().all(|u| u.line > 0), "call sites carry their line number");
    let text = report.render("fixtures");
    assert!(text.contains("network: none"));
    assert_eq!(capabilities::parse(&text).unwrap(), entries);
}

#[test]
fn update_then_verify_passes_and_detects_drift_with_sarif() {
    let Some(dir) = fixtures() else { return };
    let contracts = target_tmp().join("contracts-flow");
    let _ = std::fs::remove_dir_all(&contracts);
    let mut run = ContractsRun::new(&contracts);
    run.classes = vec![dir.to_path_buf()];
    run.sources = vec![Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/java")];
    run.base = Path::new(env!("CARGO_MANIFEST_DIR")).to_path_buf();
    run.module = "fixtures".into();
    run.add = vec!["fixtures.TrafficLight#step".into(), "capabilities".into(), "api".into()];
    run.update = true;
    let outcome = verifier::run(&run).unwrap();
    assert_eq!(outcome.exit_code, 0, "{}", outcome.output);
    assert!(contracts.join("TrafficLight.step.contract").exists());
    assert!(contracts.join("capabilities.contract").exists());
    assert!(contracts.join("api.contract").exists());

    run.update = false;
    run.add.clear();
    run.report = Some(contracts.join("report"));
    let outcome = verifier::run(&run).unwrap();
    assert_eq!(outcome.exit_code, 0, "{}", outcome.output);
    assert!(outcome.output.contains("✓ fixtures.TrafficLight#step matches its contract (16 cases"), "{}", outcome.output);

    // Drift in the behaviour, a capability lost, and a public method gone.
    let file = contracts.join("TrafficLight.step.contract");
    std::fs::write(&file, std::fs::read_to_string(&file).unwrap().replace("=> GREEN", "=> AMBER")).unwrap();
    let caps = contracts.join("capabilities.contract");
    std::fs::write(&caps, std::fs::read_to_string(&caps).unwrap().replace("  fixtures.Capable.loadByName calls java.lang.Class.forName\n", "")).unwrap();
    let api = contracts.join("api.contract");
    std::fs::write(&api, std::fs::read_to_string(&api).unwrap().replace("  public static int pure(int)\n", "")).unwrap();
    let outcome = verifier::run(&run).unwrap();
    assert_eq!(outcome.exit_code, 1);
    assert!(outcome.output.contains("step(RED, Next[])\n    contract: AMBER\n    actual:   GREEN"), "{}", outcome.output);
    assert!(outcome.output.contains("added reflection: fixtures.Capable.loadByName calls java.lang.Class.forName"), "{}", outcome.output);
    assert!(outcome.output.contains("added fixtures.Capable: public static int pure(int)"), "{}", outcome.output);
    let sarif: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(contracts.join("report/contracts.sarif")).unwrap()).unwrap();
    let results = sarif["runs"][0]["results"].as_array().unwrap();
    let rules: Vec<&str> = results.iter().map(|r| r["ruleId"].as_str().unwrap()).collect();
    assert!(rules.contains(&"behaviour-changed") && rules.contains(&"capability-changed") && rules.contains(&"api-changed"), "{rules:?}");
    let behaviour = results.iter().find(|r| r["ruleId"] == "behaviour-changed").unwrap();
    assert_eq!(behaviour["locations"][0]["physicalLocation"]["artifactLocation"]["uri"], "tests/fixtures/java/fixtures/TrafficLight.java");
    assert!(behaviour["locations"][0]["physicalLocation"]["region"]["startLine"].as_u64().unwrap() > 1);
    let capability = results.iter().find(|r| r["ruleId"] == "capability-changed").unwrap();
    assert_eq!(capability["locations"][0]["physicalLocation"]["artifactLocation"]["uri"], "tests/fixtures/java/fixtures/Capable.java");
}

const PRICING_BEFORE: &str = r#"package fixtures;
public final class Pricing {
    public static long total(long priceCents, int seats) {
        if (priceCents < 0 || seats < 0) throw new IllegalArgumentException("negative");
        long total = Math.multiplyExact(priceCents, seats);
        return seats >= 6 ? total - total / 10 : total;
    }
}
"#;

fn compile_pricing(name: &str, source: &str) -> Option<PathBuf> {
    let dir = target_tmp().join(format!("pricing-{name}"));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let file = dir.join("Pricing.java");
    std::fs::write(&file, source).unwrap();
    compile(&format!("pricing-{name}"), &[file])
}

fn equivalence_run(before: &Path, after: &Path, scope: Option<&str>, name: &str) -> equivalence::Outcome {
    let mut options = equivalence::Options::new(before, after, "fixtures.Pricing#total");
    options.unchanged_unless = scope.map(str::to_string);
    let work = target_tmp().join(format!("equivalence-{name}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work.clone());
    options.report = Some(work.join("report"));
    equivalence::run(&options).unwrap()
}

#[test]
fn relocation_renames_the_class_and_its_references() {
    let Some(before) = compile_pricing("relocate", PRICING_BEFORE) else { return };
    let out = target_tmp().join("relocated");
    let _ = std::fs::remove_dir_all(&out);
    let moved = jvmcontract::relocate::directory(&before, &out, "before").unwrap();
    assert_eq!(moved.into_iter().collect::<Vec<_>>(), vec!["fixtures/Pricing".to_string()]);
    let bytes = std::fs::read(out.join("before/fixtures/Pricing.class")).unwrap();
    let class = jvmcontract::classfile::ClassFile::parse(&bytes).unwrap();
    assert_eq!(class.name, "before/fixtures/Pricing");
    // The relocated class runs in the interpreter under its new name.
    let mut cp = ClassPath::new();
    cp.add(&out).unwrap();
    let cp = cp.with_default_jdk();
    let mut m = jvmcontract::interp::Machine::new(&cp);
    let result = m.call_static("before/fixtures/Pricing", "total", "(JI)J", vec![jvmcontract::interp::Value::Long(10), jvmcontract::interp::Value::Int(6)]).unwrap();
    assert_eq!(result, Some(jvmcontract::interp::Value::Long(54)));
}

#[test]
fn a_rounding_refactor_is_refuted_with_a_replayed_counterexample() {
    if !has("jbmc") {
        eprintln!("jbmc not found; skipping");
        return;
    }
    let after_source = PRICING_BEFORE
        .replace("long total = Math.multiplyExact(priceCents, seats);", "long unit = seats >= 6 ? priceCents - priceCents / 10 : priceCents;")
        .replace("return seats >= 6 ? total - total / 10 : total;", "return Math.multiplyExact(unit, seats);");
    let (Some(before), Some(after)) = (compile_pricing("before-a", PRICING_BEFORE), compile_pricing("rounds", &after_source)) else { return };
    let outcome = equivalence_run(&before, &after, None, "rounds");
    assert_eq!(outcome.verdict, Verdict::Violation, "{}", outcome.output);
    assert!(outcome.output.contains("✗ Behaviour of fixtures.Pricing#total changed:"), "{}", outcome.output);
    let witness = outcome.counterexample.unwrap();
    assert_ne!(witness.before, witness.after);
    assert!(witness.input.starts_with("total(priceCents="), "{}", witness.input);
    assert!(std::fs::read_to_string(outcome.work.join("report/equivalence.sarif")).unwrap().contains("behaviour-changed"));
    assert!(outcome.statement.unwrap().exists());
}

#[test]
fn a_change_confined_to_its_declared_inputs_is_proved_and_refuted_without_the_declaration() {
    if !has("jbmc") {
        eprintln!("jbmc not found; skipping");
        return;
    }
    let tier = PRICING_BEFORE.replace("return seats >= 6 ? total - total / 10 : total;", "return seats >= 6 ? total - total / 5 : total;");
    let (Some(before), Some(after)) = (compile_pricing("before-b", PRICING_BEFORE), compile_pricing("tier", &tier)) else { return };
    let proved = equivalence_run(&before, &after, Some("seats >= 6"), "tier-scoped");
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);
    assert!(proved.output.contains("behaves as before on every input where !(seats >= 6)"), "{}", proved.output);
    let refuted = equivalence_run(&before, &after, None, "tier-unscoped");
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
}

const BUFFERS_BEFORE: &str = r#"package fixtures;
public final class Buffers {
    /** Writes v into the first n elements of a, or all of them, and returns how many it wrote. */
    public static int fill(int[] a, int n, int v) {
        int k = 0;
        for (int i = 0; i < a.length && k < n; i++) { a[i] = v; k++; }
        return k;
    }
    /** The first n elements of a, or all of them. */
    public static int[] prefix(int[] a, int n) {
        int[] r = new int[Math.max(0, Math.min(n, a.length))];
        for (int i = 0; i < r.length; i++) { r[i] = a[i]; }
        return r;
    }
}
"#;

fn compile_buffers(name: &str, source: &str) -> Option<PathBuf> {
    let dir = target_tmp().join(format!("buffers-{name}"));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let file = dir.join("Buffers.java");
    std::fs::write(&file, source).unwrap();
    compile(&format!("buffers-{name}"), &[file])
}

fn buffers_run(before: &Path, after: &Path, scope: Option<&str>, name: &str) -> equivalence::Outcome {
    let mut options = equivalence::Options::new(before, after, "fixtures.Buffers#fill");
    options.unchanged_unless = scope.map(str::to_string);
    let work = target_tmp().join(format!("equivalence-{name}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work.clone());
    equivalence::run(&options).unwrap()
}

#[test]
fn arrays_are_compared_in_regression_proofs_as_left_by_each_version() {
    // Comparing the result and the array each version leaves needs no JBMC: the harness class, run in the
    // interpreter, throws AssertionError exactly on the inputs where the versions differ.
    let shorter = BUFFERS_BEFORE.replace("int[] r = new int[Math.max(0, Math.min(n, a.length))];", "int[] r = new int[Math.max(0, Math.min(n, a.length) - 1)];");
    let (Some(before), Some(after)) = (compile_buffers("before", BUFFERS_BEFORE), compile_buffers("shorter", &shorter)) else { return };
    let relocated = target_tmp().join("buffers-relocated");
    let _ = std::fs::remove_dir_all(&relocated);
    jvmcontract::relocate::directory(&before, &relocated, "before").unwrap();
    let harness_dir = target_tmp().join("buffers-harness");
    let _ = std::fs::remove_dir_all(&harness_dir);
    std::fs::create_dir_all(&harness_dir).unwrap();
    let params = jvmcontract::harness::params(&["a".into(), "n".into()], &[jvmcontract::classfile::Type::Array(Box::new(jvmcontract::classfile::Type::Int)), jvmcontract::classfile::Type::Int]);
    let harness = jvmcontract::harness::generate("fixtures/Buffers", "prefix", &params, &jvmcontract::classfile::Type::Array(Box::new(jvmcontract::classfile::Type::Int)), None, 8).unwrap();
    std::fs::write(harness_dir.join("EquivalenceHarness.class"), &harness.bytes).unwrap();
    let cp = jvmcontract::witness::classpath([harness_dir.as_path(), after.as_path(), relocated.as_path()]).unwrap();
    let mut m = jvmcontract::interp::Machine::new(&cp);
    m.monitor = false;
    let mut check = |data: Vec<i32>, n: i32| -> bool {
        let _ = m.begin_case();
        let a = m.new_array_of(jvmcontract::classfile::Type::Int, data.into_iter().map(jvmcontract::interp::Value::Int).collect());
        match m.call_static("EquivalenceHarness", "check", "([II)V", vec![a, jvmcontract::interp::Value::Int(n)]) {
            Ok(_) => true,
            Err(jvmcontract::interp::Fault::Throw(r)) if m.class_of(r) == "java/lang/AssertionError" => false,
            Err(f) => panic!("{f:?}"),
        }
    };
    assert!(check(vec![], 0), "both return an empty array");
    assert!(check(vec![5, 6], -3), "both return an empty array for a negative count");
    assert!(!check(vec![5, 6], 2), "the version after returns one element fewer");

    if !has("jbmc") {
        eprintln!("jbmc not found; skipping");
        return;
    }
    // A rewrite that is equal on every array, count and value is proved so, with the copies in the statement.
    let clamped = BUFFERS_BEFORE.replace("int k = 0;\n        for (int i = 0; i < a.length && k < n; i++) { a[i] = v; k++; }\n        return k;", "int k = Math.max(0, Math.min(n, a.length));\n        for (int i = 0; i < k; i++) { a[i] = v; }\n        return k;");
    assert_ne!(clamped, BUFFERS_BEFORE);
    let Some(clamped) = compile_buffers("clamped", &clamped) else { return };
    let proved = buffers_run(&before, &clamped, None, "buffers-clamped");
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);
    assert!(proved.output.contains("over a: int[] of length ≤ 8 × n: int × v: int"), "{}", proved.output);
    let statement = std::fs::read_to_string(proved.statement.unwrap()).unwrap();
    assert!(statement.contains("int[] a_before = java.util.Arrays.copyOf(a, a.length);"), "{statement}");
    assert!(statement.contains("&& java.util.Arrays.equals(a, a_before);"), "{statement}");

    // A rewrite that returns a negative count differs on an input the shrinker brings down to the empty array.
    let unclamped = BUFFERS_BEFORE.replace("int k = 0;\n        for (int i = 0; i < a.length && k < n; i++) { a[i] = v; k++; }\n        return k;", "int k = Math.min(n, a.length);\n        for (int i = 0; i < k; i++) { a[i] = v; }\n        return k;");
    let Some(unclamped) = compile_buffers("unclamped", &unclamped) else { return };
    let refuted = buffers_run(&before, &unclamped, None, "buffers-unclamped");
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    let witness = refuted.counterexample.unwrap();
    assert_eq!(witness.input, "fill(a=[], n=-1, v=0)", "{}", refuted.output);
    assert_eq!((witness.before.as_str(), witness.after.as_str()), ("0", "-1"));

    // A rewrite that writes from the other end returns the same count and leaves a different array; declared as
    // changing only the arrays whose elements are not all v already (a quantifier in the scope), it is proved equal.
    let backwards = BUFFERS_BEFORE.replace("for (int i = 0; i < a.length && k < n; i++) { a[i] = v; k++; }", "for (int i = a.length - 1; i >= 0 && k < n; i--) { a[i] = v; k++; }");
    let Some(backwards) = compile_buffers("backwards", &backwards) else { return };
    let refuted = buffers_run(&before, &backwards, None, "buffers-backwards");
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    let witness = refuted.counterexample.unwrap();
    // On the shrunk witness one version changes the array and the other leaves it as it was.
    assert!(witness.before.contains(", leaving a=[") || witness.after.contains(", leaving a=["), "{}", refuted.output);
    assert_ne!(witness.before, witness.after);
    assert!(witness.found.is_some() && witness.shrink_runs > 0, "{}", refuted.output);
    assert!(refuted.output.contains("shrunk to the input above"), "{}", refuted.output);
    let scoped = buffers_run(&before, &backwards, Some("(\\exists int i; 0 <= i && i < a.length; a[i] != v)"), "buffers-backwards-scoped");
    assert_eq!(scoped.verdict, Verdict::Verified, "{}", scoped.output);
    assert!(scoped.output.contains("on every input where !((\\exists int i; 0 <= i && i < a.length; a[i] != v))"), "{}", scoped.output);
}

#[test]
fn a_reference_parameter_is_refused_by_the_symbolic_verifier() {
    let with_string = PRICING_BEFORE.replace("long priceCents, int seats", "String code, int seats").replace("priceCents < 0 || ", "").replace("Math.multiplyExact(priceCents, seats)", "seats");
    let Some(classes) = compile_pricing("string", &with_string) else { return };
    let outcome = equivalence_run(&classes, &classes, None, "string");
    assert_eq!(outcome.verdict, Verdict::Unverifiable);
    assert!(outcome.output.contains("cannot be verified: parameter code has type java.lang.String"), "{}", outcome.output);
}

fn prove(target: &str, assume: Option<&str>, assert: Option<&str>, name: &str) -> Option<property::Outcome> {
    prove_arrays(target, assume, assert, name, 8)
}

fn prove_arrays(target: &str, assume: Option<&str>, assert: Option<&str>, name: &str, max_array_length: u32) -> Option<property::Outcome> {
    prove_with(target, assume, assert, name, max_array_length, true)
}

fn prove_with(target: &str, assume: Option<&str>, assert: Option<&str>, name: &str, max_array_length: u32, shrink: bool) -> Option<property::Outcome> {
    prove_throws(target, assume, assert, &[], name, max_array_length, shrink)
}

fn prove_throws(target: &str, assume: Option<&str>, assert: Option<&str>, throws: &[&str], name: &str, max_array_length: u32, shrink: bool) -> Option<property::Outcome> {
    if !has("jbmc") {
        eprintln!("jbmc not found; skipping");
        return None;
    }
    let classes = fixtures()?;
    let mut options = property::Options::new(&[classes.to_path_buf()], target);
    options.assume = assume.map(str::to_string);
    options.assert = assert.map(str::to_string);
    options.throws = throws.iter().map(|t| t.to_string()).collect();
    options.max_array_length = max_array_length;
    options.shrink = shrink;
    let work = target_tmp().join(format!("property-{name}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work.clone());
    options.report = Some(work.join("report"));
    Some(property::run(&options).unwrap())
}

#[test]
fn a_postcondition_is_proved_over_every_input_and_refuted_with_a_witness() {
    // In int arithmetic `2 * result` overflows near Integer.MAX_VALUE, and the prover says so; the property is
    // stated in long arithmetic.
    let Some(overflow) = prove("fixtures.Laws#majority", Some("n > 0"), Some("2 * result > n"), "majority-overflow") else { return };
    assert_eq!(overflow.verdict, Verdict::Violation, "{}", overflow.output);
    assert!(overflow.counterexample.unwrap().values[0].parse::<i32>().unwrap() > i32::MAX / 2);
    let proved = prove("fixtures.Laws#majority", Some("n > 0"), Some("2L * result > n && result <= n"), "majority").unwrap();
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);
    assert!(proved.output.contains("✓ fixtures.Laws#majority satisfies `2L * result > n && result <= n` on every input where n > 0"), "{}", proved.output);
    assert!(proved.statement.unwrap().exists());

    let refuted = prove("fixtures.Laws#roundedHalf", Some("n > 0"), Some("2 * result > n"), "rounded-half").unwrap();
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    let witness = refuted.counterexample.unwrap();
    assert_eq!(witness.input, "roundedHalf(n=2)", "the smallest even cluster");
    assert_eq!(witness.outcome, "1");
    assert!(std::fs::read_to_string(refuted.work.join("report/property.sarif")).unwrap().contains("property-violated"));

    // Without the assumption, the exception on n <= 0 violates the property.
    let throws = prove("fixtures.Laws#majority", None, Some("2 * result > n"), "majority-throws").unwrap();
    assert_eq!(throws.verdict, Verdict::Violation, "{}", throws.output);
    assert!(throws.counterexample.unwrap().outcome.starts_with("throws IllegalArgumentException"), "{}", throws.output);
}

#[test]
fn old_reads_an_array_as_the_call_received_it() {
    // A reversal: every element after the call is the mirrored element before it.
    let Some(reversed) = prove_throws("fixtures.InPlace#reverse", None, Some("\\forall int i; 0 <= i && i < a.length; a[i] == \\old(a[a.length - 1 - i])"), &[], "reverse", 6, true) else { return };
    assert_eq!(reversed.verdict, Verdict::Verified, "{}", reversed.output);
    let statement = std::fs::read_to_string(reversed.statement.unwrap()).unwrap();
    assert!(statement.contains("\\old(a) is the array a as it was before the call"), "{statement}");

    // A frame condition: the elements before n are left alone. The method zeroes one too many.
    let frame = prove_throws("fixtures.InPlace#zeroFrom", Some("0 <= n && n <= a.length"), Some("\\forall int i; 0 <= i && i < n; a[i] == \\old(a[i])"), &[], "zero-from", 6, true).unwrap();
    assert_eq!(frame.verdict, Verdict::Violation, "{}", frame.output);
    let witness = frame.counterexample.unwrap();
    // The shrunk witness keeps the sign of the element JBMC found.
    assert!(witness.input == "zeroFrom(a=[1], n=1)" || witness.input == "zeroFrom(a=[-1], n=1)", "{}", frame.output);
    assert_eq!(witness.outcome, "void, leaving a=[0]");

    // A permutation that keeps each key with its value: sorted after, and every pair before is a pair after. The
    // unwinding bound is the arrays' bound plus one; the default sixteen costs minutes here.
    let mut options = property::Options::new(&[fixtures().unwrap().to_path_buf()], "fixtures.InPlace#sortPairs");
    options.assume = Some("keys.length == values.length".into());
    options.assert = Some("(\\forall int i; 0 < i && i < keys.length; keys[i - 1] <= keys[i]) && (\\forall int i; 0 <= i && i < keys.length; (\\exists int j; 0 <= j && j < keys.length; keys[j] == \\old(keys[i]) && values[j] == \\old(values[i])))".into());
    options.max_array_length = 3;
    options.unwind = 4;
    options.work = Some(target_tmp().join("property-sort-pairs"));
    let sorted = property::run(&options).unwrap();
    assert_eq!(sorted.verdict, Verdict::Verified, "{}", sorted.output);
    assert!(sorted.output.contains("loops unwound 4 times"), "{}", sorted.output);

    // \old belongs to the assertion.
    let misplaced = prove_throws("fixtures.InPlace#reverse", Some("\\old(a.length) > 0"), Some("true"), &[], "old-in-assume", 4, true).unwrap();
    assert_eq!(misplaced.verdict, Verdict::Unverifiable, "{}", misplaced.output);
    assert!(misplaced.output.contains("\\old is only meaningful in the assertion"), "{}", misplaced.output);
}

#[test]
fn throws_clauses_prove_the_exceptional_path() {
    // The exception on n <= 0 is declared, so the whole domain is covered: no assumption.
    let Some(declared) = prove_throws("fixtures.Laws#majority", None, Some("2L * result > n && result <= n"), &["IllegalArgumentException when n <= 0"], "majority-declared", 8, true) else { return };
    assert_eq!(declared.verdict, Verdict::Verified, "{}", declared.output);
    assert!(declared.output.contains("satisfies `2L * result > n && result <= n` on every input, and throws java.lang.IllegalArgumentException when n <= 0 (JBMC"), "{}", declared.output);
    let statement = std::fs::read_to_string(declared.statement.unwrap()).unwrap();
    assert!(statement.contains("if (n <= 0) { expected = 1; } // java.lang.IllegalArgumentException"), "{statement}");
    assert!(statement.contains("catch (java.lang.IllegalArgumentException t) { e = -1; }"), "{statement}");

    // A clause the method does not honour: it returns on n == 1 where the clause says it throws.
    let too_wide = prove_throws("fixtures.Laws#majority", None, Some("2L * result > n"), &["java.lang.IllegalArgumentException when n <= 1"], "majority-too-wide", 8, true).unwrap();
    assert_eq!(too_wide.verdict, Verdict::Violation, "{}", too_wide.output);
    let witness = too_wide.counterexample.unwrap();
    assert_eq!(witness.input, "majority(n=1)");
    assert_eq!(witness.outcome, "1");
    assert_eq!(witness.expected.as_deref(), Some("throws java.lang.IllegalArgumentException, since n <= 1"));
    assert!(too_wide.output.contains("violated: `2L * result > n`, and throws java.lang.IllegalArgumentException when n <= 1:\n  majority(n=1)\n    outcome: 1\n    expected: throws java.lang.IllegalArgumentException, since n <= 1"), "{}", too_wide.output);

    // A clause narrower than the method: it throws on n == 0 where no clause applies. A void method's property
    // can be its clauses alone.
    let too_narrow = prove_throws("fixtures.Checks#count", None, None, &["IllegalArgumentException when n < 0"], "count-too-narrow", 8, true).unwrap();
    assert_eq!(too_narrow.verdict, Verdict::Violation, "{}", too_narrow.output);
    let witness = too_narrow.counterexample.unwrap();
    assert_eq!(witness.input, "count(n=0)");
    assert!(witness.outcome.starts_with("throws IllegalArgumentException"), "{}", witness.outcome);
    assert_eq!(witness.expected.as_deref(), Some("a normal return: no throws clause applies to this input"));
    let exact = prove_throws("fixtures.Checks#count", None, None, &["IllegalArgumentException when n <= 0"], "count-exact", 8, true).unwrap();
    assert_eq!(exact.verdict, Verdict::Verified, "{}", exact.output);
    assert!(exact.output.contains("✓ fixtures.Checks#count returns on every input, and throws java.lang.IllegalArgumentException when n <= 0 (JBMC"), "{}", exact.output);
    assert!(too_narrow.output.contains("violated: returns, and throws java.lang.IllegalArgumentException when n < 0:"), "{}", too_narrow.output);

    // An exception JBMC has no model of is taken from the JDK image, with its superclass (LinkageError).
    let u2 = "0 <= startPc && startPc <= 65535 && 0 <= endPc && endPc <= 65535 && 0 <= handlerPc && handlerPc <= 65535 && 0 <= codeLength && codeLength <= 65535";
    let range = "ClassFormatError when startPc >= endPc || endPc > codeLength || handlerPc >= codeLength";
    let entry = prove_throws("fixtures.Checks#protectedLength", Some(u2), Some("result == endPc - startPc && result >= 1"), &[range], "entry", 8, true).unwrap();
    assert_eq!(entry.verdict, Verdict::Verified, "{}", entry.output);
    assert!(entry.work.join("jdk/java/lang/ClassFormatError.class").exists());
    assert!(entry.work.join("jdk/java/lang/LinkageError.class").exists());
    assert!(!entry.work.join("jdk/java/lang/Error.class").exists(), "JBMC models Error itself");
    let off_by_one = prove_throws("fixtures.Checks#protectedLength", Some(u2), Some("result == endPc - startPc"), &["java.lang.ClassFormatError when startPc >= endPc || endPc >= codeLength || handlerPc >= codeLength"], "entry-off-by-one", 8, true).unwrap();
    assert_eq!(off_by_one.verdict, Verdict::Violation, "{}", off_by_one.output);
    let witness = off_by_one.counterexample.unwrap();
    assert_eq!(witness.input, "protectedLength(startPc=0, endPc=1, handlerPc=0, codeLength=1)", "{}", off_by_one.output);
    assert_eq!(witness.outcome, "1");
    assert_eq!(witness.expected.as_deref(), Some("throws java.lang.ClassFormatError, since startPc >= endPc || endPc >= codeLength || handlerPc >= codeLength"));

    // Clauses are checked when the property is read.
    let unknown = prove_throws("fixtures.Checks#count", None, None, &["NoSuchError when n < 0"], "count-unknown", 8, true).unwrap();
    assert_eq!(unknown.verdict, Verdict::Unverifiable);
    assert!(unknown.problem.unwrap().contains("no class NoSuchError in java.lang or the target's package"));
    let not_throwable = prove_throws("fixtures.Checks#count", None, None, &["java.lang.String when n < 0"], "count-string", 8, true).unwrap();
    assert!(not_throwable.problem.unwrap().contains("is not a Throwable"));
}

#[test]
fn arrays_are_quantified_over_and_witnessed() {
    // Binary search is correct on every sorted array up to the bound: the key's index, or -1 when absent.
    let sorted = "(\\forall int i; 0 < i && i < sorted.length; sorted[i - 1] < sorted[i])";
    let correct = "(result == -1 && (\\forall int i; 0 <= i && i < sorted.length; sorted[i] != key)) || (result >= 0 && result < sorted.length && sorted[result] == key)";
    let Some(found) = prove("fixtures.Search#find", Some(sorted), Some(correct), "find") else { return };
    assert_eq!(found.verdict, Verdict::Verified, "{}", found.output);
    assert!(found.domain.as_deref().unwrap().contains("sorted: int[] of length ≤ 8"), "{:?}", found.domain);
    assert!(std::fs::read_to_string(found.statement.unwrap()).unwrap().contains("int[] sorted, int key"));

    // Without the sortedness assumption the search misses keys, and the witness is an array.
    let unsorted = prove("fixtures.Search#find", None, Some(correct), "find-unsorted").unwrap();
    assert_eq!(unsorted.verdict, Verdict::Violation, "{}", unsorted.output);
    let witness = unsorted.counterexample.unwrap();
    assert!(witness.values[0].starts_with('[') && witness.values[0].ends_with(']'), "{}", witness.input);
    assert!(witness.input.starts_with("find(sorted=["), "{}", witness.input);

    // An assertion that indexes out of bounds fails the property, and says so.
    let unguarded = prove("fixtures.Search#find", None, Some("sorted[result] == key"), "find-unguarded").unwrap();
    assert_eq!(unguarded.verdict, Verdict::Violation, "{}", unguarded.output);
    assert!(unguarded.counterexample.unwrap().outcome.contains("out of bounds"), "{}", unguarded.output);

    // An array result, quantified over; and a refutation in which the result array is shown.
    let sums = prove("fixtures.Search#prefixSums", Some("(\\forall int i; 0 <= i && i < xs.length; xs[i] >= 0)"), Some("result.length == xs.length && (\\forall int i; 0 < i && i < result.length; result[i] >= result[i - 1])"), "sums").unwrap();
    assert_eq!(sums.verdict, Verdict::Verified, "{}", sums.output);
    let negative = prove("fixtures.Search#prefixSums", None, Some("(\\forall int i; 0 < i && i < result.length; result[i] >= result[i - 1])"), "sums-negative").unwrap();
    assert_eq!(negative.verdict, Verdict::Violation, "{}", negative.output);
    assert!(negative.counterexample.unwrap().outcome.starts_with('['), "{}", negative.output);

    // An array parameter the method writes into is read after the call, in the harness and in the replay. (Eight
    // symbolic writes at symbolic positions take the SAT solver minutes; three take a second.)
    let replaced = prove_arrays("fixtures.Search#replace", Some("from != to"), Some("(\\forall int i; 0 <= i && i < xs.length; xs[i] != from)"), "replace", 3).unwrap();
    assert_eq!(replaced.verdict, Verdict::Verified, "{}", replaced.output);
    assert!(replaced.domain.as_deref().unwrap().contains("xs: int[] of length ≤ 3"), "{:?}", replaced.domain);
    let writes = prove("fixtures.Search#replace", Some("from != to"), Some("result == 0"), "replace-writes").unwrap();
    assert_eq!(writes.verdict, Verdict::Violation, "{}", writes.output);
    assert!(writes.counterexample.unwrap().outcome.contains("leaving xs=["), "{}", writes.output);

    let malformed = prove("fixtures.Search#find", None, Some("\\forall int i; i < sorted.length; sorted[i] != key"), "find-malformed").unwrap();
    assert_eq!(malformed.verdict, Verdict::Unverifiable);
    assert!(malformed.output.contains("must bound it below and above"), "{}", malformed.output);
}

#[test]
fn generalized_quantifiers_fold_and_counterexamples_shrink() {
    // The deepest point of a stack is the largest prefix sum, the empty prefix included: \max over \sum.
    let depth = "result == (\\max int k; 0 <= k && k <= deltas.length; (\\sum int i; 0 <= i && i < k; deltas[i]))";
    let Some(deepest) = prove("fixtures.Search#maxDepth", None, Some(depth), "max-depth") else { return };
    assert_eq!(deepest.verdict, Verdict::Verified, "{}", deepest.output);
    assert!(std::fs::read_to_string(deepest.statement.unwrap()).unwrap().contains("\\max and \\min are JML's quantifiers"));

    // A sum of longs, proved; a \sum over int elements is an int sum, which wraps as Java's does, and the witness
    // of the difference is shrunk to two elements that still overflow.
    let total = prove("fixtures.Search#total", None, Some("result == (\\sum int i; 0 <= i && i < xs.length; (long) xs[i])"), "total").unwrap();
    assert_eq!(total.verdict, Verdict::Verified, "{}", total.output);
    let narrow = prove("fixtures.Search#total", None, Some("result == (\\sum int i; 0 <= i && i < xs.length; xs[i])"), "total-narrow").unwrap();
    assert_eq!(narrow.verdict, Verdict::Violation, "{}", narrow.output);
    let witness = narrow.counterexample.unwrap();
    assert!(witness.found.is_some() && witness.shrink_runs > 0 && witness.shrink_runs < 4000, "{}", narrow.output);
    assert!(narrow.output.contains("shrunk to the input above in"), "{}", narrow.output);
    let xs: Vec<i64> = witness.values[0].trim_matches(['[', ']']).split(", ").map(|v| v.parse().unwrap()).collect();
    assert!(xs.len() <= 2 && xs.iter().sum::<i64>().abs() > i64::from(i32::MAX), "{}", witness.input);

    // A count: \num_of. The miscount is on a negative odd number, and the shrunk witness is the one nearest zero.
    let evens = prove("fixtures.Search#evens", None, Some("result == (\\num_of int i; 0 <= i && i < xs.length; xs[i] % 2 == 0)"), "evens").unwrap();
    assert_eq!(evens.verdict, Verdict::Violation, "{}", evens.output);
    let witness = evens.counterexample.unwrap();
    assert_eq!(witness.input, "evens(xs=[-1])", "{}", evens.output);
    assert_eq!(witness.outcome, "1");
    assert!(witness.found.as_deref().unwrap().starts_with("evens(xs=["), "{:?}", witness.found);
    let unshrunk = prove_with("fixtures.Search#evens", None, Some("result == (\\num_of int i; 0 <= i && i < xs.length; xs[i] % 2 == 0)"), "evens-unshrunk", 8, false).unwrap();
    let witness = unshrunk.counterexample.unwrap();
    assert!(witness.found.is_none() && witness.shrink_runs == 0 && !unshrunk.output.contains("shrunk"), "{}", unshrunk.output);

    // The scalar witnesses of the earlier tests shrink too: the smallest even cluster is found by shrinking from
    // whatever JBMC gave, and a witness of an exception is the smallest input that throws.
    let throws = prove("fixtures.Laws#majority", None, Some("2 * result > n"), "majority-throws-shrunk").unwrap();
    assert_eq!(throws.counterexample.unwrap().input, "majority(n=0)", "{}", throws.output);
}

#[test]
fn a_law_may_call_the_method_and_a_boolean_method_is_its_own_property() {
    let Some(law) = prove("fixtures.Laws#maxOf", None, Some("result == maxOf(b, a) && result >= a && result >= b && maxOf(result, a) == result"), "max-law") else { return };
    assert_eq!(law.verdict, Verdict::Verified, "{}", law.output);
    assert!(std::fs::read_to_string(law.statement.unwrap()).unwrap().contains("result == fixtures.Laws.maxOf(b, a)"));

    let strict = prove("fixtures.Laws#maxIsStrict", None, None, "max-strict").unwrap();
    assert_eq!(strict.verdict, Verdict::Violation, "{}", strict.output);
    assert_eq!(strict.assert.as_deref(), Some("result"));
    let witness = strict.counterexample.unwrap();
    assert_eq!(witness.values[0], witness.values[1], "the witness has a = b: {}", witness.input);
    assert_eq!(witness.outcome, "false");

    let malformed = prove("fixtures.Laws#maxOf", None, Some("result == maxOf(a)"), "max-malformed").unwrap();
    assert_eq!(malformed.verdict, Verdict::Unverifiable);
    assert!(malformed.output.contains("maxOf takes 2 arguments, 1 given"), "{}", malformed.output);
}

/// The Box Office domain module of this repository, when the crate sits inside it.
fn boxoffice_domain() -> Option<PathBuf> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/apps/boxoffice/ticketing-domain");
    if !root.exists() {
        eprintln!("not inside the java-formal-verification repository; skipping");
        return None;
    }
    static DIR: OnceLock<Option<PathBuf>> = OnceLock::new();
    DIR.get_or_init(|| compile("boxoffice-domain", &java_files(&root.join("src/main/java")))).clone()
}

#[test]
fn reproduces_the_contract_the_java_tool_committed_for_box_office() {
    let Some(dir) = boxoffice_domain() else { return };
    let committed = Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/apps/boxoffice/ticketing-domain/src/contract/OrderLifecycle.decide.contract");
    let expected = Contract::read(&committed).unwrap();
    let derived = contract(&dir, "net.terminalvalue.boxoffice.ticketing.domain.OrderLifecycle#decide");
    assert_eq!(derived.cases, expected.cases);
    assert_eq!(derived.domain, expected.domain);
    assert!(Contract::diff(&expected, &derived).is_empty());
    // The rendered file differs from the committed one only in its header comments.
    let strip = |s: &str| s.lines().filter(|l| !l.starts_with('#')).collect::<Vec<_>>().join("\n");
    assert_eq!(strip(&derived.render()), strip(&std::fs::read_to_string(&committed).unwrap()));

    let caps = capabilities::analyse(std::slice::from_ref(&dir)).unwrap();
    let committed_caps = Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/apps/boxoffice/ticketing-domain/src/contract/capabilities.contract");
    assert_eq!(caps.entries(), capabilities::read(&committed_caps).unwrap());
    assert_eq!(caps.classes, 15);
}

#[test]
fn generates_the_tla_operator_the_python_generator_wrote() {
    let committed = Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/apps/boxoffice/spec/OrderLifecycleContract.tla");
    let contract_file = Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/apps/boxoffice/ticketing-domain/src/contract/OrderLifecycle.decide.contract");
    if !committed.exists() {
        eprintln!("not inside the repository; skipping");
        return;
    }
    let contract = Contract::read(&contract_file).unwrap();
    let generated = tla::operator_module(&contract, "OrderLifecycleContract", None).unwrap();
    let strip = |s: &str| s.lines().filter(|l| !l.starts_with("\\*")).collect::<Vec<_>>().join("\n");
    assert_eq!(strip(&generated), strip(&std::fs::read_to_string(&committed).unwrap()));
}

#[test]
fn tlc_checks_the_box_office_model() {
    let spec = Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/apps/boxoffice/spec");
    if !spec.exists() {
        eprintln!("not inside the repository; skipping");
        return;
    }
    if tla::tlc_command(&tla::TlcOptions::new(&spec.join("BoxOffice.tla"))).is_err() {
        missing("TLC");
        eprintln!("TLC not found; skipping");
        return;
    }
    let work = target_tmp().join("spec");
    let _ = std::fs::remove_dir_all(&work);
    std::fs::create_dir_all(&work).unwrap();
    for entry in std::fs::read_dir(&spec).unwrap() {
        let path = entry.unwrap().path();
        if path.is_file() {
            std::fs::copy(&path, work.join(path.file_name().unwrap())).unwrap();
        }
    }
    let mut options = tla::TlcOptions::new(&work.join("BoxOffice.tla"));
    options.library = Some(Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/tools/tla/standard-modules"));
    options.timeout_seconds = 600;
    let result = tla::run_tlc(&options).unwrap();
    assert_eq!(result.verdict, Verdict::Verified, "{}", result.output);
    assert!(result.distinct_states.unwrap() > 1000);
}

#[test]
fn draws_the_state_machine_of_a_contract() {
    let Some(dir) = fixtures() else { return };
    let c = contract(dir, "fixtures.TrafficLight#step");
    // TrafficLight#step returns the next light directly, not a record: no `next` field, so it is not a machine.
    assert!(jvmcontract::statemachine::from_contract(&c, "next").is_err());
    let committed = Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/apps/boxoffice/ticketing-domain/src/contract/OrderLifecycle.decide.contract");
    if committed.exists() {
        let machine = jvmcontract::statemachine::from_contract(&Contract::read(&committed).unwrap(), "next").unwrap();
        assert_eq!(machine.states.len(), 5);
        assert_eq!(machine.terminal(), vec!["REFUNDED"]);
        assert_eq!(machine.unreachable(), vec!["PENDING_PAYMENT"]);
        assert!(machine.mermaid().contains("PENDING_PAYMENT --> CONFIRMED: PaymentCaptured[seatsStillHeld=true] → effects=[SELL_SEATS]"));
    }
}
