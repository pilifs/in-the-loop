//! End-to-end tests over Java fixtures compiled with `javac` at test time; some also need JBMC or TLC. A missing tool
//! fails the test that needs it, unless JVMCONTRACT_SKIP_MISSING_TOOLS=1 asks for the skip: a test that skips passes, so
//! a green run on a broken PATH would otherwise prove nothing.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::classpath::ClassPath;
use jvmcontract::contract::Contract;
use jvmcontract::verifier::{self, ContractsRun, Verifier};
use jvmcontract::{boundaries, capabilities, equivalence, property, tla, Verdict};

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

/// The Spring fixtures: stand-ins for the framework's annotation types, and beans that use them.
fn spring_fixtures() -> Option<&'static Path> {
    static DIR: OnceLock<Option<PathBuf>> = OnceLock::new();
    DIR.get_or_init(|| {
        let src = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/spring");
        let out = compile("spring", &java_files(&src))?;
        // One controller without `-parameters`: its bytecode has no MethodParameters attribute, as a framework sees it.
        let legacy = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/spring-legacy");
        let status = Command::new("javac").args(["-g", "-proc:none", "-cp"]).arg(&out).arg("-d").arg(&out).args(java_files(&legacy)).status().expect("javac runs");
        assert!(status.success(), "legacy fixtures compile");
        Some(out)
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
fn an_overloaded_method_is_named_by_its_parameter_types() {
    let Some(dir) = fixtures() else { return };
    let p = problem(dir, "fixtures.Overloads#pick");
    assert!(p.contains("found 2: pick(boolean), pick(fixtures.TrafficLight$Light); name one as pick(boolean)"), "{p}");
    assert_eq!(contract(dir, "fixtures.Overloads#pick(boolean)").cases.len(), 2);
    assert_eq!(contract(dir, "fixtures.Overloads#pick( Light )").cases.len(), 4);
    assert_eq!(contract(dir, "fixtures.Overloads#pick(fixtures.TrafficLight.Light)").cases.len(), 4);
    let p = problem(dir, "fixtures.Overloads#twice(long, int)");
    assert!(p.contains("no method twice(long, int); found twice(int), twice(long)"), "{p}");
    assert!(problem(dir, "fixtures.Overloads#twice(long)").contains("input domain is not finite"));
    assert_eq!(Contract::file_name("fixtures.Overloads#pick(fixtures.TrafficLight.Light)"), "Overloads.pick-Light.contract");
    assert_eq!(Contract::file_name("fixtures.Overloads#pick"), "Overloads.pick.contract");
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

const SHARES_BEFORE: &str = r#"package fixtures;
public final class Shares {
    static long perSeat(long total, int seats) {
        if (seats <= 0) throw new IllegalArgumentException("seats");
        return total / seats;
    }
    public static long split(long total, int seats, int fee) {
        return perSeat(total, seats) + fee;
    }
}
"#;

fn compile_shares(name: &str, source: &str) -> Option<PathBuf> {
    let dir = target_tmp().join(format!("shares-{name}"));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let file = dir.join("Shares.java");
    std::fs::write(&file, source).unwrap();
    compile(&format!("shares-{name}"), &[file])
}

fn shares_run(before: &Path, after: &Path, name: &str) -> equivalence::Outcome {
    let mut options = equivalence::Options::new(before, after, "fixtures.Shares#split");
    let work = target_tmp().join(format!("equivalence-{name}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work.clone());
    options.timeout_seconds = 120;
    equivalence::run(&options).unwrap()
}

/// Two copies of a 64-bit division, one per version, are more than the solver settles in minutes; as one function
/// in both versions, the helper costs nothing, and the proof is about how the two versions use it.
#[test]
fn a_callee_unchanged_in_both_versions_is_one_function_in_the_proof() {
    if !has("jbmc") {
        eprintln!("jbmc not found; skipping");
        return;
    }
    let after = SHARES_BEFORE.replace("return perSeat(total, seats) + fee;", "long share = perSeat(total, seats);\n        return fee + share;");
    let (Some(before), Some(after)) = (compile_shares("before-a", SHARES_BEFORE), compile_shares("reordered", &after)) else { return };
    let outcome = shares_run(&before, &after, "shares-shared");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert_eq!(outcome.shared, vec!["Shares.perSeat".to_string()]);
    assert!(outcome.proof.as_deref().unwrap().ends_with("; Shares.perSeat unchanged in both versions and taken as one function in both"), "{}", outcome.output);
    assert!(outcome.work.join("shared-classes").join("SharedCallees.class").exists());
    assert!(outcome.work.join("jbmc-shared.log").exists(), "the proof over all inputs ran with the stub");
}

/// The stub throws what the callee can throw, so a catch around the call in one version only is still a difference.
#[test]
fn a_catch_around_a_shared_callee_is_still_a_difference() {
    if !has("jbmc") {
        eprintln!("jbmc not found; skipping");
        return;
    }
    let caught = SHARES_BEFORE.replace("return perSeat(total, seats) + fee;", "try { return perSeat(total, seats) + fee; } catch (IllegalArgumentException e) { return -1; }");
    let (Some(before), Some(after)) = (compile_shares("caught", &caught), compile_shares("uncaught", SHARES_BEFORE)) else { return };
    let outcome = shares_run(&before, &after, "shares-caught");
    assert_eq!(outcome.verdict, Verdict::Violation, "{}", outcome.output);
    let witness = outcome.counterexample.unwrap();
    assert_eq!(witness.before, "-1", "{}", outcome.output);
    assert!(witness.after.starts_with("throws IllegalArgumentException"), "{}", outcome.output);
}

/// A counterexample that rests on the stub giving two calls unrelated results is no counterexample: the proof is
/// run again with the callee as written.
#[test]
fn a_counterexample_the_shared_callee_cannot_reproduce_falls_back_to_its_bytecode() {
    if !has("jbmc") {
        eprintln!("jbmc not found; skipping");
        return;
    }
    let before = "package fixtures;\npublic final class Shares {\n    static int twice(int x) { return x + x; }\n    public static long split(long total, int seats, int fee) { return twice(fee); }\n}\n";
    let after = before.replace("return twice(fee);", "return twice(fee - 1) + 2;");
    let (Some(before), Some(after)) = (compile_shares("twice", before), compile_shares("twice-shifted", &after)) else { return };
    let outcome = shares_run(&before, &after, "shares-fallback");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert!(outcome.shared.is_empty(), "{}", outcome.output);
    assert!(outcome.output.contains("note: the counterexample found with Shares.twice taken as one function in both versions does not reproduce once computed as written; proving with the callees' bytecode"), "{}", outcome.output);
    assert!(outcome.work.join("jbmc.log").exists(), "the proof over all inputs ran again as written");
}

/// Needs no JBMC: the two versions' bytecode is compared, and nothing differs.
#[test]
fn a_target_identical_in_both_versions_needs_no_proof() {
    let (Some(before), Some(after)) = (compile_shares("same-a", SHARES_BEFORE), compile_shares("same-b", SHARES_BEFORE)) else { return };
    let outcome = shares_run(&before, &after, "shares-identical");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert_eq!(outcome.proof.as_deref(), Some("its bytecode and that of the method it reaches are identical in both versions; nothing to prove"));
    assert!(outcome.output.starts_with("✓ fixtures.Shares#split behaves as before on every input (its bytecode"), "{}", outcome.output);
    assert!(!outcome.work.join("jbmc.log").exists());
    // The comparison itself: the target and the helper it calls, two methods, the same in both.
    let classpath = |dir: &Path| {
        let mut cp = ClassPath::new();
        cp.add(dir).unwrap();
        cp.with_default_jdk()
    };
    let plan = jvmcontract::shared::plan(&classpath(&before), &classpath(&after), &jvmcontract::classfile::MemberRef::new("fixtures/Shares", "split", "(JII)J"), &jvmcontract::classfile::MemberRef::new("fixtures/Shares", "split", "(JII)J"), true);
    assert_eq!(plan.identical, Some(2));
    let changed = compile_shares("same-c", &SHARES_BEFORE.replace("+ fee;", "+ fee + 1;")).unwrap();
    let plan = jvmcontract::shared::plan(&classpath(&before), &classpath(&changed), &jvmcontract::classfile::MemberRef::new("fixtures/Shares", "split", "(JII)J"), &jvmcontract::classfile::MemberRef::new("fixtures/Shares", "split", "(JII)J"), true);
    assert_eq!(plan.identical, None);
    assert_eq!(plan.callees.iter().map(|c| c.display()).collect::<Vec<_>>(), vec!["Shares.perSeat".to_string()]);
    assert_eq!(plan.callees[0].throws, vec!["java/lang/ArithmeticException".to_string(), "java/lang/IllegalArgumentException".to_string()]);
}

const WRITERS_BEFORE: &str = r#"package fixtures;
public final class Writers {
    public static int winner(long tsA, int nodeA, long tsB, int nodeB) {
        if (tsA != tsB) {
            return tsA > tsB ? 0 : 1;
        }
        return nodeA >= nodeB ? 0 : 1;
    }
}
"#;

/// The parameters grouped by kind, and the body a comparison chain.
const WRITERS_REORDERED: &str = r#"package fixtures;
public final class Writers {
    public static int winner(long tsA, long tsB, int nodeA, int nodeB) {
        int order = Long.compare(tsA, tsB);
        if (order == 0) {
            order = Integer.compare(nodeA, nodeB);
        }
        return order >= 0 ? 0 : 1;
    }
}
"#;

fn compile_writers(name: &str, class: &str, source: &str) -> Option<PathBuf> {
    let dir = target_tmp().join(format!("writers-{name}"));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let file = dir.join(format!("{class}.java"));
    std::fs::write(&file, source).unwrap();
    compile(&format!("writers-{name}"), &[file])
}

fn writers_run(before: &Path, after: &Path, target: &str, before_target: Option<&str>, before_arguments: Option<&str>, name: &str) -> equivalence::Outcome {
    related_run(before, after, target, before_target, before_arguments, None, None, name)
}

#[allow(clippy::too_many_arguments)]
fn related_run(before: &Path, after: &Path, target: &str, before_target: Option<&str>, before_arguments: Option<&str>, relation: Option<&str>, scope: Option<&str>, name: &str) -> equivalence::Outcome {
    let mut options = equivalence::Options::new(before, after, target);
    let work = target_tmp().join(format!("equivalence-{name}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    options.timeout_seconds = 120;
    options.before_target = before_target.map(str::to_string);
    options.before_arguments = before_arguments.map(str::to_string);
    options.results_agree_when = relation.map(str::to_string);
    options.unchanged_unless = scope.map(str::to_string);
    equivalence::run(&options).unwrap()
}

/// A cache's expire-after-write test, as a boolean.
const EXPIRY_BEFORE: &str = r#"package fixtures;
public final class Expiry {
    public static final long FOREVER = Long.MAX_VALUE;
    public static boolean isExpired(long writtenAtNanos, long ttlNanos, long nowNanos) {
        if (ttlNanos == FOREVER) { return false; }
        return nowNanos - writtenAtNanos >= ttlNanos;
    }
}
"#;

/// The same test as the time left, expired when none is.
const EXPIRY_REMAINING: &str = r#"package fixtures;
public final class Expiry {
    public static final long FOREVER = Long.MAX_VALUE;
    public static long remainingNanos(long writtenAtNanos, long ttlNanos, long nowNanos) {
        if (ttlNanos == FOREVER) { return FOREVER; }
        return ttlNanos - (nowNanos - writtenAtNanos);
    }
}
"#;

/// The time left in milliseconds, which rounds the last fraction of a millisecond down to none.
const EXPIRY_MILLIS: &str = r#"package fixtures;
public final class Expiry {
    public static final long FOREVER = Long.MAX_VALUE;
    public static long remainingMillis(long writtenAtNanos, long ttlNanos, long nowNanos) {
        if (ttlNanos == FOREVER) { return FOREVER; }
        return (ttlNanos - (nowNanos - writtenAtNanos)) / 1_000_000L;
    }
}
"#;

/// The precondition the cache guarantees: a write at or after the clock's zero, read at or after the write, with
/// a positive time to live; the relation between the versions is claimed on these inputs.
const EXPIRY_SCOPE: &str = "!(writtenAtNanos >= 0 && nowNanos >= writtenAtNanos && ttlNanos > 0)";

/// A result that changed its type or meaning is related to the previous one by a stated relation over both, which
/// takes the place of equality: a boolean that became a remaining time is expired exactly when none is left.
#[test]
fn a_boolean_that_became_a_remaining_time_is_proved_under_the_stated_relation() {
    if !has("jbmc") {
        return;
    }
    let (Some(before), Some(after)) = (compile_writers("expiry-before", "Expiry", EXPIRY_BEFORE), compile_writers("expiry-remaining", "Expiry", EXPIRY_REMAINING)) else { return };
    let outcome = related_run(&before, &after, "fixtures.Expiry#remainingNanos", Some("fixtures.Expiry#isExpired"), None, Some("previous == (result <= 0)"), Some(EXPIRY_SCOPE), "expiry-remaining");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert_eq!(outcome.relation.as_deref(), Some("previous == (result <= 0)"));
    assert!(
        outcome.output.starts_with("✓ fixtures.Expiry#remainingNanos agrees with the previous isExpired(writtenAtNanos, ttlNanos, nowNanos) on every input, the results related by previous == (result <= 0) where !(!(writtenAtNanos >= 0 && nowNanos >= writtenAtNanos && ttlNanos > 0)) (JBMC"),
        "{}",
        outcome.output
    );
    let statement = std::fs::read_to_string(outcome.statement.unwrap()).unwrap();
    assert!(statement.contains("boolean previous = a; long result = b;"), "{statement}");
    assert!(statement.contains("assert ea == eb && (ea != 0 || (previous == (result <= 0)));"), "{statement}");
}

#[test]
fn a_remaining_time_in_milliseconds_that_expires_entries_early_is_found_under_the_relation() {
    if !has("jbmc") {
        return;
    }
    let (Some(before), Some(after)) = (compile_writers("expiry-before-m", "Expiry", EXPIRY_BEFORE), compile_writers("expiry-millis", "Expiry", EXPIRY_MILLIS)) else { return };
    let outcome = related_run(&before, &after, "fixtures.Expiry#remainingMillis", Some("fixtures.Expiry#isExpired"), None, Some("previous == (result <= 0)"), Some(EXPIRY_SCOPE), "expiry-millis");
    assert_eq!(outcome.verdict, Verdict::Violation, "{}", outcome.output);
    let c = outcome.counterexample.as_ref().expect("counterexample");
    // Less than a millisecond to go: not expired, but no millisecond left.
    assert_eq!(c.input, "remainingMillis(writtenAtNanos=0, ttlNanos=1, nowNanos=0)", "{}", outcome.output);
    assert_eq!((c.before.as_str(), c.after.as_str()), ("false", "0"), "{}", outcome.output);
    assert!(outcome.output.contains("✗ fixtures.Expiry#remainingMillis differs from the previous isExpired(writtenAtNanos, ttlNanos, nowNanos) outside the intended inputs"), "{}", outcome.output);
    assert!(outcome.output.contains("\n    the results are not related by previous == (result <= 0)\n"), "{}", outcome.output);
    assert!(outcome.output.contains(" searching inputs in [0:20]"), "{}", outcome.output);
    // The tool's own checker looks in the same stages, so it reports the same input without the shrinker's help.
    let mut options = equivalence::Options::new(&before, &after, "fixtures.Expiry#remainingMillis");
    options.before_target = Some("fixtures.Expiry#isExpired".into());
    options.results_agree_when = Some("previous == (result <= 0)".into());
    options.unchanged_unless = Some(EXPIRY_SCOPE.into());
    options.engine = jvmcontract::Engine::Native;
    let work = target_tmp().join("equivalence-expiry-millis-native");
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    let native = equivalence::run(&options).unwrap();
    assert_eq!(native.verdict, Verdict::Violation, "{}", native.output);
    let n = native.counterexample.as_ref().expect("counterexample");
    assert_eq!(n.input, c.input, "{}", native.output);
    assert!(native.output.contains("found by jvmcontract's own checker (CaDiCaL) in "), "{}", native.output);
    assert!(native.output.contains(" searching inputs in [0:20]"), "{}", native.output);
}

#[test]
fn results_of_two_types_need_a_relation() {
    if !has("jbmc") {
        return;
    }
    let (Some(before), Some(after)) = (compile_writers("expiry-before-u", "Expiry", EXPIRY_BEFORE), compile_writers("expiry-unrelated", "Expiry", EXPIRY_REMAINING)) else { return };
    let outcome = related_run(&before, &after, "fixtures.Expiry#remainingNanos", Some("fixtures.Expiry#isExpired"), None, None, None, "expiry-unrelated");
    assert_eq!(outcome.verdict, Verdict::Unverifiable, "{}", outcome.output);
    assert!(outcome.output.contains("the previous version returns boolean and the new one long; say how the results are related with --results-agree-when"), "{}", outcome.output);
}

/// A signature change is a relation between the versions, not a difference: the previous version's arguments
/// are given as expressions over the new parameters, and the proof is of new(x) against old(f(x)).
#[test]
fn a_method_whose_parameters_were_reordered_is_proved_against_the_previous_order() {
    if !has("jbmc") {
        return;
    }
    let (Some(before), Some(after)) = (compile_writers("before-a", "Writers", WRITERS_BEFORE), compile_writers("reordered", "Writers", WRITERS_REORDERED)) else { return };
    let outcome = writers_run(&before, &after, "fixtures.Writers#winner", None, Some("tsA, nodeA, tsB, nodeB"), "writers-reordered");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert_eq!(outcome.previous.as_deref(), Some("winner(tsA, nodeA, tsB, nodeB)"));
    assert!(outcome.output.starts_with("✓ fixtures.Writers#winner behaves as the previous winner(tsA, nodeA, tsB, nodeB) on every input (JBMC"), "{}", outcome.output);
    let statement = std::fs::read_to_string(outcome.statement.unwrap()).unwrap();
    assert!(statement.contains("long tsA_ = tsA; int nodeA_ = nodeA; long tsB_ = tsB; int nodeB_ = nodeB;"), "{statement}");
    assert!(statement.contains("a = before.fixtures.Writers.winner(tsA_, nodeA_, tsB_, nodeB_);"), "{statement}");
}

#[test]
fn a_method_moved_and_renamed_is_proved_against_its_previous_name() {
    if !has("jbmc") {
        return;
    }
    let moved = WRITERS_REORDERED.replace("class Writers", "class Resolver").replace("int winner(", "int pick(");
    let (Some(before), Some(after)) = (compile_writers("before-b", "Writers", WRITERS_BEFORE), compile_writers("moved", "Resolver", &moved)) else { return };
    let outcome = writers_run(&before, &after, "fixtures.Resolver#pick", Some("fixtures.Writers#winner"), Some("tsA, nodeA, tsB, nodeB"), "writers-moved");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert_eq!(outcome.previous.as_deref(), Some("fixtures.Writers#winner(tsA, nodeA, tsB, nodeB)"));
    assert!(outcome.output.starts_with("✓ fixtures.Resolver#pick behaves as the previous fixtures.Writers#winner(tsA, nodeA, tsB, nodeB) on every input"), "{}", outcome.output);
}

/// The counterexample is shown as both versions received it: the new parameters, and the previous version's
/// arguments computed from them.
#[test]
fn a_rewrite_under_a_reordering_that_changes_a_tie_is_found() {
    if !has("jbmc") {
        return;
    }
    let tie = WRITERS_REORDERED.replace("order >= 0 ? 0 : 1", "order > 0 ? 0 : 1");
    let (Some(before), Some(after)) = (compile_writers("before-c", "Writers", WRITERS_BEFORE), compile_writers("tie", "Writers", &tie)) else { return };
    let outcome = writers_run(&before, &after, "fixtures.Writers#winner", None, Some("tsA, nodeA, tsB, nodeB"), "writers-tie");
    assert_eq!(outcome.verdict, Verdict::Violation, "{}", outcome.output);
    let witness = outcome.counterexample.unwrap();
    assert_eq!(witness.input, "winner(tsA=0, tsB=0, nodeA=0, nodeB=0), previously winner(tsA=0, nodeA=0, tsB=0, nodeB=0)", "{}", outcome.output);
    assert_eq!((witness.before.as_str(), witness.after.as_str()), ("0", "1"));
    assert!(outcome.output.contains("✗ fixtures.Writers#winner differs from the previous winner(tsA, nodeA, tsB, nodeB):"), "{}", outcome.output);
}

#[test]
fn the_previous_versions_parameters_must_be_mapped_when_they_differ() {
    let (Some(before), Some(after)) = (compile_writers("before-d", "Writers", WRITERS_BEFORE), compile_writers("unmapped", "Writers", WRITERS_REORDERED)) else { return };
    let outcome = writers_run(&before, &after, "fixtures.Writers#winner", None, None, "writers-unmapped");
    assert_eq!(outcome.verdict, Verdict::Unverifiable, "{}", outcome.output);
    assert_eq!(outcome.problem.as_deref(), Some("the previous version takes (long, int, long, int) and the new one (long, long, int, int); give the previous version's arguments as expressions over the new parameters with --before-arguments"));
    let renamed = writers_run(&before, &after, "fixtures.Writers#winner", Some("fixtures.Writers#pick"), None, "writers-unknown");
    assert_eq!(renamed.verdict, Verdict::Unverifiable, "{}", renamed.output);
    assert!(renamed.problem.as_deref().unwrap().starts_with("in the previous version, expected one method named pick, found 0"), "{}", renamed.output);
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
    let harness = jvmcontract::harness::generate("fixtures/Buffers", "prefix", &params, &jvmcontract::classfile::Type::Array(Box::new(jvmcontract::classfile::Type::Int)), None, 8, None).unwrap();
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
    // What JBMC found before shrinking depends on its solver (CaDiCaL lands on [-1] at once; MiniSAT on a longer array).
    assert!(witness.found.as_deref().is_none_or(|f| f.starts_with("evens(xs=[")), "{:?}", witness.found);
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
fn tlc_checks_temporal_properties_and_names_the_violated_one() {
    let spec = Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/apps/quorum/spec");
    if !spec.exists() {
        eprintln!("not inside the repository; skipping");
        return;
    }
    if tla::tlc_command(&tla::TlcOptions::new(&spec.join("TwoPhaseCommit.tla"))).is_err() {
        missing("TLC");
        eprintln!("TLC not found; skipping");
        return;
    }
    let work = target_tmp().join("spec-twopc");
    let _ = std::fs::remove_dir_all(&work);
    std::fs::create_dir_all(&work).unwrap();
    for entry in std::fs::read_dir(&spec).unwrap() {
        let path = entry.unwrap().path();
        if path.is_file() {
            std::fs::copy(&path, work.join(path.file_name().unwrap())).unwrap();
        }
    }
    let mut options = tla::TlcOptions::new(&work.join("TwoPhaseCommit.tla"));
    options.library = Some(Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples/tools/tla/standard-modules"));
    options.timeout_seconds = 600;
    // The committed coordinator: every participant eventually decides, and the protocol refines transaction commit.
    let result = tla::run_tlc(&options).unwrap();
    assert_eq!(result.verdict, Verdict::Verified, "{}", result.output);
    assert_eq!(result.properties, vec!["EveryParticipantDecides".to_string(), "ImplementsTransactionCommit".to_string()]);
    assert!(result.summary().starts_with("✓ every invariant and temporal property holds in 728 distinct states"), "{}", result.summary());
    // A coordinator that keeps collecting on a timeout when every vote so far is yes: a participant that gave up
    // before voting leaves the prepared ones waiting forever. TLC does not say which property fails; the runner
    // checks them one at a time and names it, and the trace ends in stuttering.
    let operator = work.join("CoordinatorContract.tla");
    let waiting = std::fs::read_to_string(&operator).unwrap().replace(
        "input = [kind |-> \"Timeout\", unanimousSoFar |-> TRUE] -> Transition(\"ABORTED\", <<\"SEND_ABORT\">>)",
        "input = [kind |-> \"Timeout\", unanimousSoFar |-> TRUE] -> Unchanged",
    );
    std::fs::write(&operator, waiting).unwrap();
    let result = tla::run_tlc(&options).unwrap();
    assert_eq!(result.verdict, Verdict::Violation, "{}", result.output);
    assert_eq!(result.kind, Some(tla::ViolationKind::Temporal));
    assert_eq!(result.invariant.as_deref(), Some("EveryParticipantDecides"));
    assert!(result.stuttering && result.lasso.is_none(), "{}", result.output);
    assert!(result.trace.len() >= 4 && result.trace.iter().any(|s| s.action == "ParticipantTimeout"), "{}", result.summary());
    assert!(result.output.contains("checked the temporal properties one at a time to name the violated one: EveryParticipantDecides"), "{}", result.output);
    assert!(result.summary().contains("is violated: after") && result.summary().contains("stays in that state forever"), "{}", result.summary());
    // No temporary configuration is left behind.
    assert!(std::fs::read_dir(&work).unwrap().all(|e| !e.unwrap().file_name().to_string_lossy().contains("EveryParticipantDecides")));
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

#[test]
fn the_interpreter_runs_the_models_where_the_jdk_is_modelled() {
    use jvmcontract::interp::{Fault, Machine, Value};
    let Some(classes) = fixtures() else { return };
    let mut cp = ClassPath::new();
    cp.add(classes).unwrap();
    let cp = cp.with_default_jdk();
    let mut m = Machine::new(&cp);
    let hex = |m: &mut Machine, ch: u32| m.call_static("fixtures/Models", "hexDigit", "(C)I", vec![Value::Int(ch as i32)]).unwrap();
    // Character.digit by the JDK's table: the Arabic-Indic zero and the fullwidth A are digits, as on a JVM.
    assert_eq!(hex(&mut m, 0x0660), Some(Value::Int(0)));
    assert_eq!(hex(&mut m, 0xFF21), Some(Value::Int(10)));
    assert_eq!(hex(&mut m, 'F' as u32), Some(Value::Int(15)));
    assert_eq!(hex(&mut m, 'g' as u32), Some(Value::Int(-1)));
    // A static initializer that reads StandardCharsets.UTF_8 runs, on the model's instance.
    let encoding = m.get_static("fixtures/Models", "ENCODING").unwrap();
    assert_eq!(m.str_of(encoding).as_deref(), Some("UTF-8"));
    let standard = |m: &mut Machine, first: char| m.call_static("fixtures/Models", "standard", "(C)Z", vec![Value::Int(first as i32)]).unwrap();
    assert_eq!(standard(&mut m, 'u'), Some(Value::Int(1)));
    assert_eq!(standard(&mut m, 'z'), Some(Value::Int(0)));
    let canonical = m.call_static("fixtures/Models", "canonical", "(C)Ljava/lang/String;", vec![Value::Int('u' as i32)]).unwrap().unwrap();
    assert_eq!(m.str_of(canonical).as_deref(), Some("UTF-8"), "an alias resolves to the canonical name");
    // forName of a name that is none of the six throws the modelled exception, an IllegalArgumentException.
    match m.call_static("fixtures/Models", "canonical", "(C)Ljava/lang/String;", vec![Value::Int('z' as i32)]) {
        Err(Fault::Throw(r)) => {
            let class = m.class_of(r);
            assert_eq!(class, "java/nio/charset/UnsupportedCharsetException");
            assert!(cp.is_subtype(&class, "java/lang/IllegalArgumentException"));
        }
        other => panic!("expected a throw, got {other:?}"),
    }
    assert_eq!(m.call_static("fixtures/Models", "boxed", "(I)I", vec![Value::Int(-7)]).unwrap(), Some(Value::Int(-7)), "boxing stays native");
    // Without the models, the static read is beyond the interpreter and the digit comes from its native.
    let mut off = ClassPath::new();
    off.add(classes).unwrap();
    let off = off.with_default_jdk().with_models(false);
    let mut m = Machine::new(&off);
    assert!(matches!(m.get_static("fixtures/Models", "ENCODING"), Err(Fault::Unsupported(_))));
}

#[test]
fn proofs_over_modelled_jdk_classes_are_decided_by_the_models() {
    // Models.<clinit> reads StandardCharsets.UTF_8, so every proof here also needs the charset models under JBMC.
    // Character.digit comes from the model: the property holds by the JDK's table, and the witness against the
    // stricter claim is a Unicode digit, which the interpreter replays on the same model.
    let Some(all) = prove("fixtures.Models#hexDigit", None, Some("result >= -1 && result <= 15"), "models-digit") else { return };
    assert_eq!(all.verdict, Verdict::Verified, "{}", all.output);
    let ascii = prove("fixtures.Models#hexDigit", None, Some("result == -1 || ch < 128"), "models-unicode").unwrap();
    assert_eq!(ascii.verdict, Verdict::Violation, "{}", ascii.output);
    let witness = ascii.counterexample.unwrap();
    assert!(witness.input.starts_with("hexDigit(ch="), "{}", witness.input);
    assert!(!witness.outcome.contains("could not replay"), "{}", witness.outcome);
    assert!(witness.values.iter().any(|v| !v.is_ascii()), "a digit beyond ASCII, such as the fullwidth zero: {:?}", witness.values);
    assert!(witness.outcome.contains("returns") || witness.outcome.chars().any(|c| c.is_ascii_digit()), "replayed on the model to its digit value: {}", witness.outcome);
    // Boxing: the JDK's Integer.valueOf reads the cache the tool models. Without the model JBMC indexes a
    // nondeterministic array, and the proof fails for a reason the interpreter cannot replay.
    let boxed = prove("fixtures.Models#boxed", None, Some("result == n"), "models-boxed").unwrap();
    assert_eq!(boxed.verdict, Verdict::Verified, "{}", boxed.output);
    let classes = fixtures().unwrap();
    let mut options = property::Options::new(&[classes.to_path_buf()], "fixtures.Models#boxed");
    options.assert = Some("result == n".into());
    options.models = false;
    let work = target_tmp().join("property-models-off");
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work.clone());
    let without = property::run(&options).unwrap();
    assert_ne!(without.verdict, Verdict::Verified, "{}", without.output);
    assert!(!work.join("models").exists(), "no models directory is written when they are off");
}

/// A property proof with the checker chosen.
fn prove_engine(target: &str, assume: Option<&str>, assert: Option<&str>, throws: &[&str], engine: jvmcontract::Engine, name: &str) -> property::Outcome {
    let classes = fixtures().unwrap();
    let mut options = property::Options::new(&[classes.to_path_buf()], target);
    options.assume = assume.map(str::to_string);
    options.assert = assert.map(str::to_string);
    options.throws = throws.iter().map(|t| t.to_string()).collect();
    options.engine = engine;
    let work = target_tmp().join(format!("property-{name}-{engine:?}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work.clone());
    property::run(&options).unwrap()
}

#[test]
fn the_tools_own_checker_agrees_with_jbmc_on_integer_proofs() {
    use jvmcontract::Engine;
    if !has("jbmc") {
        eprintln!("jbmc not found; skipping");
        return;
    }
    if fixtures().is_none() {
        return;
    }
    let cases: &[(&str, Option<&str>, Option<&str>, &[&str], Verdict)] = &[
        // In int arithmetic `2 * result` overflows near Integer.MAX_VALUE, which both checkers find; in long it holds.
        ("fixtures.Laws#majority", Some("n > 0"), Some("2 * result > n && result <= n"), &[], Verdict::Violation),
        ("fixtures.Laws#majority", Some("n > 0"), Some("2L * result > n && result <= n"), &[], Verdict::Verified),
        ("fixtures.Laws#majority", None, Some("2L * result > n"), &[], Verdict::Violation),
        ("fixtures.Laws#majority", None, Some("2L * result > n && result <= n"), &["java.lang.IllegalArgumentException when n <= 0"], Verdict::Verified),
        ("fixtures.Laws#maxOf", None, Some("result >= a && result >= b && (result == a || result == b)"), &[], Verdict::Verified),
        ("fixtures.Laws#roundedHalf", None, Some("2 * result >= n && 2 * result <= n + 1"), &[], Verdict::Violation),
        ("fixtures.Overloads#twice(long)", None, Some("result == 2 * x"), &[], Verdict::Verified),
        ("fixtures.Checks#protectedLength", Some("startPc >= 0 && endPc >= 0 && handlerPc >= 0 && codeLength >= 0 && startPc <= 65535 && endPc <= 65535 && handlerPc <= 65535 && codeLength <= 65535"), Some("result == endPc - startPc"), &["java.lang.ClassFormatError when startPc >= endPc || endPc >= codeLength || handlerPc >= codeLength"], Verdict::Violation),
    ];
    for (i, (target, assume, assert, throws, expected)) in cases.iter().enumerate() {
        let native = prove_engine(target, *assume, *assert, throws, Engine::Native, &format!("agree-{i}"));
        let jbmc = prove_engine(target, *assume, *assert, throws, Engine::Jbmc, &format!("agree-{i}"));
        assert_eq!(native.verdict, *expected, "native on {target}: {}", native.output);
        assert_eq!(jbmc.verdict, *expected, "JBMC on {target}: {}", jbmc.output);
        assert!(native.output.contains("jvmcontract's own checker (CaDiCaL)"), "{}", native.output);
        assert!(native.work.join("bmc.log").exists());
        if *expected == Verdict::Violation {
            // Both witnesses are replayed and shrunk by the interpreter, so the shrunk inputs agree where the
            // smallest failing input is unique.
            let (n, j) = (native.counterexample.unwrap(), jbmc.counterexample.unwrap());
            assert_eq!(n.outcome, j.outcome, "{} vs {}", n.input, j.input);
            if target.ends_with("majority") && assume.is_none() {
                assert_eq!(n.input, j.input);
            }
        }
    }
    // Arrays are outside the engine's fragment: under `auto` it says so and JBMC takes over.
    let correct = "(result == -1 && (\\forall int i; 0 <= i && i < sorted.length; sorted[i] != key)) || (result >= 0 && result < sorted.length && sorted[result] == key)";
    let auto = prove_engine("fixtures.Search#find", Some("(\\forall int i; 0 < i && i < sorted.length; sorted[i - 1] < sorted[i])"), Some(correct), &[], Engine::Auto, "agree-arrays");
    assert_eq!(auto.verdict, Verdict::Verified, "{}", auto.output);
    assert!(auto.output.contains("note: the tool's own checker gave no verdict (outside the fragment: a int[] parameter); JBMC"), "{}", auto.output);
    assert!(auto.output.contains("JBMC 6"), "{}", auto.output);
    let native_only = prove_engine("fixtures.Search#find", None, Some(correct), &[], Engine::Native, "agree-arrays");
    assert_eq!(native_only.verdict, Verdict::Unverifiable);
    assert!(native_only.problem.unwrap().contains("outside the fragment"));

    // A regression proof, both ways: the rounding refactor is refuted and the scoped tier change proved.
    let after_source = PRICING_BEFORE
        .replace("long total = Math.multiplyExact(priceCents, seats);", "long unit = seats >= 6 ? priceCents - priceCents / 10 : priceCents;")
        .replace("return seats >= 6 ? total - total / 10 : total;", "return Math.multiplyExact(unit, seats);");
    let tier = PRICING_BEFORE.replace("return seats >= 6 ? total - total / 10 : total;", "return seats >= 6 ? total - total / 5 : total;");
    let (before, rounds, tier) = (compile_pricing("before-n", PRICING_BEFORE).unwrap(), compile_pricing("rounds-n", &after_source).unwrap(), compile_pricing("tier-n", &tier).unwrap());
    let run = |after: &Path, scope: Option<&str>, engine: Engine, name: &str| {
        let mut options = equivalence::Options::new(&before, after, "fixtures.Pricing#total");
        options.unchanged_unless = scope.map(str::to_string);
        options.engine = engine;
        let work = target_tmp().join(format!("equivalence-{name}-{engine:?}"));
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        equivalence::run(&options).unwrap()
    };
    let refuted = run(&rounds, None, Engine::Native, "rounds");
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    assert!(refuted.output.contains("found by jvmcontract's own checker"), "{}", refuted.output);
    let witness = refuted.counterexample.unwrap();
    assert_ne!(witness.before, witness.after);
    let proved = run(&tier, Some("seats >= 6"), Engine::Native, "tier");
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);
    assert_eq!(run(&tier, None, Engine::Native, "tier-unscoped").verdict, Verdict::Violation);
}

#[test]
fn the_boundary_contract_lists_entry_points_advice_and_where_advice_does_not_apply() {
    let Some(dir) = spring_fixtures() else { return };
    let fixtures = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/spring");
    let mut cp = ClassPath::new();
    cp.add(dir).unwrap();
    cp.add(&fixtures.join("metadata")).unwrap();
    let cp = cp.with_default_jdk();
    let found = boundaries::analyse_in(&cp, None, None, &[fixtures.join("resources")]).unwrap();
    let text = found.render("spring");
    let has = |line: &str| assert!(text.contains(line), "expected {line:?} in:\n{text}");

    // Routes compose the class prefix, the verb and the conditions; the guards are their own lines.
    has("fixtures.spring.OrdersController: @RestController @RequestMapping(\"/orders\")");
    has("  POST /orders (consumes application/json) => Order place(@Valid @RequestBody Order request)");
    has("  GET /orders/{id} => Order get(@PathVariable String id, @RequestParam(required = false) @Min(1) Integer version)");
    has("  DELETE /orders/{id} => void purge(@PathVariable String id)\n    @PreAuthorize(\"hasRole('ADMIN')\")");
    has("  GET /orders/count, GET /orders/total, HEAD /orders/count, HEAD /orders/total => int count()");
    assert!(!text.contains("describe"), "a method without framework annotations is not a boundary");
    // Schedules, bean definitions and configuration keys.
    has("  @Scheduled(fixedDelayString = \"${orders.sweep:1s}\") => void sweep()");
    has("fixtures.spring.HoldSettings: @ConfigurationProperties(\"holds\")\n\n");
    has("  @Value(\"${orders.limit:5}\") int limit");
    // The places where the advice does not apply.
    has("  Order place(String holdId)\n    @Transactional\n    ! self-invocation from audited(String)");
    has("    ! self-invocation from placeAll(String, int): the call does not go through the proxy, so @Transactional does not apply to it");
    has("    ! self-invocation from a lambda in placeAll(String, int)");
    has("    ! commits on IOException: a checked exception is not a rollback cause unless rollbackFor names it");
    assert!(!text.contains("self-invocation from delegate"), "a call on another instance goes through its proxy");
    has("  void audited(String holdId)\n    @Transactional(propagation = Propagation.REQUIRES_NEW, rollbackFor = java.io.IOException.class)\n  void named");
    has("    @Transactional(rollbackForClassName = \"IOException\")\n    ! commits on InterruptedException");
    has("    ! @Transactional on a private method: the proxy cannot intercept it");
    has("    ! @Transactional on a static method: the proxy cannot intercept it");
    has("    ! @Transactional on a method of a final class: the CGLIB proxy cannot subclass it");
    has("    ! @Async returns Order: a result that is not a Future is lost, the caller gets null");
    has("  CompletableFuture<Order> computeLater(String id)\n    @Async\n  void warm()");
    has("    ! @Cacheable on a void method caches nothing");
    has("    ! @Scheduled method takes parameters: the scheduler cannot call it");
    has("    ! constraints on seats are not enforced: the method is not a request handler and the class is not @Validated");
    // Class-level advice applies to every public instance method, and @Validated enforces the constraints.
    has("fixtures.spring.Quotas: @Service @Validated @Transactional(readOnly = true)\n  int remaining(@Positive int tenant)\n    ! self-invocation from refill(int)");
    has("  int refill(int tenant)\n    @Timed(\"quotas.refill\")\n  int quiet(@Positive int tenant)\n    ! constraints on tenant are not enforced: method validation goes through the proxy, which intercepts public instance methods only\n\n");

    // The activation block: what enables each annotation family the module uses. The application class scans its
    // own package; a switch on the application class, on an imported configuration and on a nested class of an
    // auto-configuration each count; a provider on the class path enables @Valid; and a family nothing enables is
    // a `!` line naming the nearest miss (a configuration outside the scanned packages, a class that is not a
    // component, an auto-configuration whose condition fails).
    has("activation: fixtures.spring.App (@SpringBootApplication), scanning fixtures.spring\n");
    has("  @Scheduled: @EnableScheduling on fixtures.spring.App\n");
    has("  @Cacheable: @EnableCaching on fixtures.shared.SharedConfiguration, imported by App\n");
    has("  @Transactional: @EnableTransactionManagement on FakeTransactionAutoConfiguration.EnableTransactionManagementConfiguration, auto-configured\n");
    has("  @Valid: Bean Validation provider org.hibernate.validator.HibernateValidator in metadata\n");
    has("  @Validated: Bean Validation provider org.hibernate.validator.HibernateValidator in metadata; MethodValidationPostProcessor bean on FakeValidationAutoConfiguration, auto-configured\n");
    has("  @Async: nothing enables it\n    ! no @EnableAsync on a configuration in scope (fixtures.other.AsyncConfiguration has @EnableAsync, but is outside the scanned packages (fixtures.spring)): an @Async method runs on the caller's thread, which waits for it\n");
    has("  @PreAuthorize: nothing enables it\n    ! no @EnableMethodSecurity on a configuration in scope: every caller is authorized\n");
    has("  @KafkaListener: nothing enables it\n    ! no @EnableKafka on a configuration in scope (fixtures.spring.KafkaSwitch has @EnableKafka, but is not a component): the listener never receives a message\n");
    has("  @Timed: nothing enables it\n    ! no TimedAspect bean on a configuration in scope (FakeMetricsAutoConfiguration defines one, but org.aspectj.weaver.Advice is not on the class path): no timer is recorded\n");
    assert!(!text.contains("@Secured:"), "a family the module does not use has no line:\n{text}");
    assert!(!text.contains("int remaining(@Positive int tenant)\n    ! constraints"), "@Validated enforces the constraints on a public method");
    // Validation: a body's constraints run only under a @Valid, and only those of the groups asked for.
    has("  POST /notes => Note create(@RequestBody Note note)\n    ! constraints on Note are not checked: no @Valid on note\n");
    has("  POST /bookings => Booking book(@RequestBody Booking request)\n    ! constraints on Booking are not checked: no @Valid on request\n");
    has("  POST /bookings/check => Booking check(@Valid @RequestBody Booking request)\n    ! @Valid validates the Default group only: @NotBlank(groups = fixtures.spring.OnCreate.class) on Booking.code is not checked\n");
    has("  POST /bookings/create => Booking create(@Validated(fixtures.spring.OnCreate.class) @RequestBody Booking request)\n    ! @Validated(OnCreate.class) validates that group only: @Size(max = 10) on Booking.seats, @NotNull on Booking.rows, @NotBlank on Booking.labels and 2 more are not checked\n");
    assert!(!text.contains("helper"), "a static method is not under the class's advice");
    // The wire types: request and response bodies, listener payloads, Jackson-annotated types, and what they reach.
    has("wire fixtures.spring.Order: record\n  id: @NotBlank String\n  seats: @Min(1) int\n");
    assert!(!text.contains("\nfixtures.spring.Order:"), "a request type with only constraints is one block, the wire one");
    has("wire fixtures.spring.Note: class, snake_case names, ignores unknown properties\n  id: String?\n  count: int\n  extra: String?\n  author: @NotBlank String?\n  token: String?\n  url: String?\n  customer_name: String?\n  paid: boolean\n  open: Boolean?\n  note: String?\n  shapes: List<Shape>?\n  kind: Kind?\n  status: Status?\n  empty: Empty?\n  due: LocalDate?\n    @JsonFormat(pattern = \"yyyy-MM-dd\")\n");
    let wire = &text[text.find("\nwire ").expect("a wire section")..];
    assert!(!wire.contains("secret") && !wire.contains("internal") && !wire.contains("private"), "ignored and invisible members are not on the wire:\n{wire}");
    has("wire fixtures.spring.Kind: enum\n  SMALL as \"small\"\n  LARGE\n");
    has("wire fixtures.spring.Status: enum, written as int by code()\n  OK\n  FAILED\n");
    has("wire fixtures.spring.PaymentEvent: interface, \"type\" names the subtype\n  ! Voided is a permitted subtype that @JsonSubTypes does not list: it is written under the type id \"PaymentEvent$Voided\", which a reader of PaymentEvent rejects\n  subtype \"PaymentCaptured\" = PaymentEvent$Captured\n  subtype \"PaymentEvent$Declined\" = PaymentEvent$Declined\n  subtype \"PaymentEvent$Voided\" = PaymentEvent$Voided\n");
    has("wire fixtures.spring.PaymentEvent$Captured: record\n  type = \"PaymentCaptured\"\n  orderId: String\n  amountCents: long\n");
    has("wire fixtures.spring.PaymentEvent$Declined: record\n  ! the type id \"PaymentEvent$Declined\" is the class name: renaming or moving the class changes the wire format\n  type = \"PaymentEvent$Declined\"\n");
    has("wire fixtures.spring.PaymentEvent$Voided: record\n  type = \"PaymentEvent$Voided\"\n  orderId: String\n");
    has("wire fixtures.spring.Audit: interface, \"@class\" names the subtype's Java class\n  ! Java class names are the type ids");
    has("wire fixtures.spring.Shape: interface\n  ! no @JsonTypeInfo: a Shape is written as the properties of its runtime class, with no type id to read it back by\n");
    has("wire fixtures.spring.Empty: class\n  ! no properties: it is written as {}\n");
    has("wire fixtures.spring.NoteDocument: record\n  ! a persistence type (@Document) is on the wire");
    // The reach lines: what an entry point reads, writes, sends, calls and publishes, through a lambda run by a
    // helper, another bean, an interface's implementation, a repository's derived and annotated methods, and the
    // declarative and fluent HTTP clients; and the two places where that contradicts the method's contract.
    has("fixtures.spring.TasksController: @RestController\n  POST /tasks => String create(@RequestParam String title)\n    writes TaskDocument\n    sends tasks\n    publishes TaskCreated\n    ! publishes TaskCreated outside a transaction: TaskAudit.created and TaskAudit.creating are @TransactionalEventListeners, which do not run when no transaction commits (fallbackExecution is false)\n  GET /tasks/open => long open(@RequestParam String email)\n    reads TaskDocument\n    ! GET /tasks/open is also mapped to TaskSearchController.open: Spring refuses the duplicate, so the context does not start\n");
    has("  GET /tasks/{author}/archive => void archive(@PathVariable String author)\n    writes NoteDocument\n    sends notices\n    ! a GET that writes NoteDocument and sends notices: a safe method with side effects, so a retry, a prefetch or a crawler changes state\n");
    has("  GET /tasks/{id}/owner => String owner(@PathVariable String id)\n    reads NoteDocument\n    calls GET /profiles/{id}, GET /users/{id}\n    ! GET /tasks/{id}/owner matches the same requests as GET /tasks/{key}/owner on TaskSearchController.owner: neither is more specific, so every request that matches is ambiguous, a 500\n\n");
    // Request binding: a path variable the template does not have, an optional primitive, a name the compiler did not
    // record (LegacyController is compiled without -parameters), and two handlers on one route.
    has("  DELETE /tasks/{taskId} => void delete(@PathVariable String id)\n    reads NoteDocument\n    ! @PathVariable id matches no variable in /tasks/{taskId}: MissingPathVariableException, a 500 on every request\n  GET /tasks/page => long page(@RequestParam(required = false) int page)\n    ! @RequestParam(required = false) on int page: a primitive cannot be null, so a request without it fails with a 500 instead of a 400\n");
    has("fixtures.spring.legacy.LegacyController: @RestController\n  GET /legacy/{id} => String get(@PathVariable String id, @RequestParam(\"q\") String query, @RequestParam Map<String, String> all)\n    ! @PathVariable id: the parameter's name is not in the bytecode (no MethodParameters attribute: compile with -parameters, or name it in the annotation), and Spring 6.1 reads nothing else, so the request fails with a 500\n\n");
    // What each route throws and what each exception becomes: a handler's status (from its body, its annotation or
    // its builder), a @ResponseStatus on the exception, the status a ResponseStatusException carries, or a 500. A
    // catch that swallows hides the exception, one that rethrows passes it, one that wraps throws the wrapper; an
    // @Async callee throws on its own thread. An application exception nothing maps is a `!` line; a JDK one is not.
    has("fixtures.spring.FailuresController: @RestController @RequestMapping(\"/failures\")\n  GET /failures/{id} => String find(@PathVariable String id)\n    reads NoteDocument\n    throws MissingException (404 by ApiErrors.missing)\n  POST /failures/{id}/expiry => void expire(@PathVariable String id)\n    throws ExpiredException (500), IllegalArgumentException (400 by ApiErrors.invalid), StaleException (409 by its @ResponseStatus)\n    ! throws ExpiredException: no @ExceptionHandler takes it and it carries no @ResponseStatus, so the response is a 500\n  POST /failures/{id}/guarded => void guarded(@PathVariable String id)\n  POST /failures/{id}/retried => void retried(@PathVariable String id)\n    throws ExpiredException (500)\n    ! throws ExpiredException: no @ExceptionHandler takes it and it carries no @ResponseStatus, so the response is a 500\n  POST /failures/{id}/wrapped => void wrapped(@PathVariable String id)\n    throws IllegalStateException (503 by FailuresController.unavailable)\n  GET /failures/{id}/gone => String gone(@PathVariable String id)\n    throws ResponseStatusException (410)\n  GET /failures/{id}/pick => String pick(@PathVariable String id)\n    throws NoSuchElementException (500)\n  @ExceptionHandler(java.lang.IllegalStateException.class) => ResponseEntity<Void> unavailable(IllegalStateException e)\n\n");
    // A listener's throws line has no outcomes; two handlers for one type in an advice stop the context.
    has("fixtures.spring.FailureListener: @Component\n  @KafkaListener(topics = \"failures\") => void on(String id)\n    throws ExpiredException, IllegalArgumentException, StaleException\n\n");
    has("fixtures.spring.ApiErrors: @RestControllerAdvice\n  @ExceptionHandler => ProblemDetail missing(MissingException e)\n  @ExceptionHandler(java.lang.IllegalArgumentException.class) => void invalid()\n    @ResponseStatus(HttpStatus.BAD_REQUEST)\n  @ExceptionHandler => ResponseEntity<String> missingAgain(MissingException e)\n    ! @ExceptionHandler for MissingException twice in ApiErrors (missing and missingAgain): Spring refuses the ambiguity, so the context does not start\n\n");
    has("fixtures.spring.TaskSearchController: @RestController\n  GET /tasks/open => long open()\n    ! GET /tasks/open is also mapped to TasksController.open: Spring refuses the duplicate, so the context does not start\n  GET /tasks/{key}/owner => String owner(@PathVariable String key)\n    ! GET /tasks/{key}/owner matches the same requests as GET /tasks/{id}/owner on TasksController.owner: neither is more specific, so every request that matches is ambiguous, a 500\n\n");
    has("fixtures.spring.TaskFlow: @Service\n  long audit(String id)\n    @Transactional(readOnly = true)\n    reads notes\n    writes audit\n    ! @Transactional(readOnly = true) but writes audit: a read-only transaction drops or rejects writes\n");
    // Where each effect stands with respect to transactions: a send and a call inside a @Transactional method are
    // dual writes, reported by that method and not by the route that calls it; a lambda run by a helper through
    // TransactionTemplate is inside the transaction the route opens; an after-commit listener's write is never
    // committed, a before-commit one joins; an event published with no transaction never reaches its
    // @TransactionalEventListener.
    has("  void rename(String id, String title)\n    @Transactional\n    writes TaskDocument\n    sends tasks\n    calls POST /audit/{id}\n    ! a transaction that sends to tasks: the send is not part of the transaction, so a rollback leaves the message sent and a crash before the send leaves the commit unannounced\n    ! a transaction that calls POST /audit/{id}: the call is not part of the transaction, so a rollback does not undo it, and the transaction stays open for the round trip\n\n");
    has("  PUT /tasks/{id} => void rename(@PathVariable String id, @RequestParam String title)\n    writes TaskDocument\n    sends tasks\n    calls POST /audit/{id}\n  POST /tasks/{id}/close => String close(@PathVariable String id)\n    writes TaskDocument\n    sends tasks\n    ! a transaction that sends to tasks: the send is not part of the transaction, so a rollback leaves the message sent and a crash before the send leaves the commit unannounced\n  DELETE /tasks/{taskId}");
    has("fixtures.spring.TaskAudit: @Component\n  @TransactionalEventListener => void created(TaskCreated event)\n    writes audit\n    ! an AFTER_COMMIT listener that writes audit: the transaction has committed and nothing commits again, so a JPA or JDBC write here is never committed unless the method opens its own transaction (propagation = REQUIRES_NEW)\n  @TransactionalEventListener(phase = TransactionPhase.BEFORE_COMMIT) => void creating(TaskCreated event)\n    writes audit\n\n");
    // A handler that reaches nothing has no reach line; a GET that only reads is not a problem.
    has("  GET /orders/{id} => Order get(@PathVariable String id, @RequestParam(required = false) @Min(1) Integer version)\n  DELETE");
    assert!(!text.contains("! a GET that writes TaskDocument"), "a POST is not held to GET's safety:\n{text}");

    // The stored types: each document's shape under its stored names, and the query strings that name no field.
    has("stored fixtures.spring.CounterDocument: class, collection \"counterDocument\"\n  _id: String (id)\n  value: long\n  version: @Version Long\n  ! NotesStore.anywhere() queries \"nowhere\": not a field of any document in the module (CounterDocument, NoteDocument, TaskDocument), so the condition tests a field that is never set\n  ! NotesStore.bump(String) writes \"valeu\": not a field of CounterDocument (value?), so the update writes a field that nothing reads back\n\n");
    has("stored fixtures.spring.NoteDocument: record, collection \"notes\"\n  _id: String (id)\n  text: String\n  by: String (author)\n  createdAt: @Indexed Instant\n  labels: List<String>\n  ! @CompoundIndex on NoteDocument indexes \"created\": not a field of NoteDocument (createdAt?), so the index is on a field that is never set\n  ! @Query on NoteRepository.search(String) queries \"txet\": not a field of NoteDocument (text?), so the condition tests a field that is never set\n  ! NotesStore(MongoTemplate) indexes \"created\": not a field of NoteDocument (createdAt?), so the index is on a field that is never set\n  ! NotesStore.rename(String, String) queries \"txt\": not a field of NoteDocument (text?), so the condition tests a field that is never set\n  ! NotesStore.rename(String, String) writes \"views\": not a field of NoteDocument, so the update writes a field that nothing reads back\n\n");
    has("stored fixtures.spring.TaskDocument: record, collection \"tasks\"\n  _id: String (id)\n  title: String\n  assignee: Assignee\n  steps: List<Step>\n  due: Instant (dueAt)\n  createdAt: Instant\n  labels: Map<String, String>\n");
    has("  ! NotesStore.openTasksOf(String) queries \"assignee.mail\": \"mail\" is not a field of Assignee (email?), so the condition tests a field that is never set\n");
    has("  ! NotesStore.openTasksOf(String) queries \"assignee.email.domain\": \"assignee.email\" is a String, which has no fields, so the condition tests a field that is never set\n");
    has("  ! NotesStore.openTasksOf(String) sorts by \"titel\": not a field of TaskDocument (title?), so the sort orders by a field that is never set\n");
    has("  ! NotesStore.done() removes \"archived\": not a field of TaskDocument, so the update changes nothing\n");
    has("stored fixtures.spring.TaskDocument$Assignee: record, embedded\n  name: String\n  email: String\n");
    for fine in ["queries \"steps.done\"", "queries \"labels.team\"", "queries \"steps.0.label\"", "writes \"due\"", "writes \"steps.$.done\"", "queries \"by\"", "queries \"id\"", "queries \"author\"", "sorts by \"createdAt\"", "projects \"by\""] {
        assert!(!text.contains(fine), "a path through an embedded type, a map, a stored name or an id is a field, {fine:?} is not a problem:\n{text}");
    }
    has("wire fixtures.spring.Base: class\n  id: String\n");
    // The constraints on a wire type, with the ones that cannot run as written.
    has("wire fixtures.spring.Booking: record\n  seats: @Size(max = 10) int\n    ! @Size has no validator for int: the first validation throws UnexpectedTypeException\n  rows: @NotNull int\n    ! @NotNull on int can never fail: a primitive is never null\n  labels: List<@NotBlank String>\n  guest: Guest\n    ! constraints on Guest are not checked: no @Valid on guest\n  payer: @Valid Guest\n  party: List<@Valid Guest>\n  tier: @Min(1) Integer?\n  code: @NotBlank(groups = fixtures.spring.OnCreate.class) String\n\n");
    has("wire fixtures.spring.Guest: record\n  name: @NotBlank String\n");
    // The configuration keys: what the classes read, what the files set, what the metadata declares, cross-checked.
    has("configuration: application-prod.properties, application.yaml\n");
    has("  holds.max-seats: int = 8, 12 (prod)\n    @ConfigurationProperties(\"holds\") HoldSettings.maxSeats\n");
    has("  holds.ttl: Duration = \"2 minutes\"\n    @ConfigurationProperties(\"holds\") HoldSettings.ttl\n    ! \"2 minutes\" is not a Duration\n");
    has("  holds.region: Region = eu-west\n    @ConfigurationProperties(\"holds\") HoldSettings.region\n    ! \"eu-west\" is not a Region: one of EU, US\n");
    has("  holds.rows[]: List<String>\n    @ConfigurationProperties(\"holds\") HoldSettings.rows\n");
    has("  holds.rows[0]: String = A\n    under holds.rows[] (@ConfigurationProperties(\"holds\") HoldSettings.rows)\n");
    has("  holds.limits.*: Map<String, Integer>\n");
    has("  holds.limits.vip: Integer = 2\n    under holds.limits.* (@ConfigurationProperties(\"holds\") HoldSettings.limits)\n");
    has("  holds.alerts.enabled: boolean = yes\n    @ConfigurationProperties(\"holds\") HoldSettings$Alerts.enabled\n");
    has("  holds.alerts.channel: String\n    @ConfigurationProperties(\"holds\") HoldSettings$Alerts.channel\n");
    has("  holds.enabled: String = true\n    @ConditionalOnProperty(havingValue = \"true\") on Settings\n");
    has("  holds.max-seat = 6\n    ! nothing binds it: no class on the class path reads it and no configuration metadata declares it; nearest known key: holds.max-seats\n");
    has("  holds.retries: int, default many\n    @Value on Settings.retries, default many\n    ! the default \"many\" is not an int\n");
    has("  gateway.url: String = http://localhost:9000\n    Environment.getProperty in Settings.gateway(), default http://localhost\n");
    has("  gateway.limit: Integer = ten\n    Environment.getProperty in Settings.limit()\n    ! \"ten\" is not an Integer\n");
    has("  gateway.token: String\n    Environment.containsProperty in Settings.hasToken()\n");
    has("  orders.sweep: Duration, default 1s\n    @Scheduled in OrderService.sweep(), default 1s\n");
    has("  server.port: Integer = 8080, 80 (prod)\n    declared by ServerProperties\n");
    has("  spring.data.mongodb.uri = mongodb://localhost/test\n    ! deprecated since 4.0.0, no longer bound: use spring.mongodb.uri\n");
    has("  spring.kafka.producer.properties.enable.idempotence: String = true\n    under spring.kafka.producer.properties.*, declared by KafkaProperties$Producer\n");
    assert!(!text.contains("on-profile"), "the profile selector is not a key of the contract:\n{text}");
    assert_eq!((found.beans.len(), found.entry_points(), found.advised(), found.configuration_keys(), found.types.len(), found.stored.len(), found.problems()), (35, 39, 16, 21, 17, 5, 70), "{text}");

    // The file reads back as exactly the entries it was written from.
    assert_eq!(boundaries::parse(&text).unwrap(), found.entries());

    // As a contract: written by `update`, checked by `verify`, and a dropped guard is a violation anchored to the handler.
    let contracts = target_tmp().join("contracts-boundaries");
    let _ = std::fs::remove_dir_all(&contracts);
    let mut run = ContractsRun::new(&contracts);
    run.classes = vec![dir.to_path_buf()];
    run.classpath = vec![fixtures.join("metadata")];
    run.sources = vec![fixtures.clone()];
    run.resources = vec![fixtures.join("resources")];
    run.base = Path::new(env!("CARGO_MANIFEST_DIR")).to_path_buf();
    run.module = "spring".into();
    run.add = vec!["boundaries".into()];
    run.update = true;
    let outcome = verifier::run(&run).unwrap();
    assert_eq!(outcome.exit_code, 0, "{}", outcome.output);
    let file = contracts.join("boundaries.contract");
    assert_eq!(std::fs::read_to_string(&file).unwrap(), text);

    run.update = false;
    run.add.clear();
    let outcome = verifier::run(&run).unwrap();
    assert_eq!(outcome.exit_code, 0, "{}", outcome.output);
    assert!(outcome.output.contains("matches its boundary contract (35 beans, 39 entry points, 16 advised methods, 21 configuration keys, 17 wire types, 5 stored types, 70 problems)"), "{}", outcome.output);

    let edited = text.replace("    @PreAuthorize(\"hasRole('ADMIN')\")\n", "").replace("    ! @Cacheable on a void method caches nothing\n", "").replace("  amountCents: long\n", "  amount: long\n").replace("  due: Instant (dueAt)\n", "  dueAt: Instant\n");
    std::fs::write(&file, edited).unwrap();
    let outcome = verifier::run(&run).unwrap();
    assert_eq!(outcome.exit_code, 1, "{}", outcome.output);
    assert!(outcome.output.contains("  added fixtures.spring.OrderService: void warm(): ! @Cacheable on a void method caches nothing"), "{}", outcome.output);
    assert!(outcome.output.contains("  added fixtures.spring.OrdersController: DELETE /orders/{id} => void purge(@PathVariable String id): @PreAuthorize(\"hasRole('ADMIN')\")"), "{}", outcome.output);
    assert!(outcome.output.contains("  added wire fixtures.spring.PaymentEvent$Captured: amountCents: long\n") && outcome.output.contains("  removed wire fixtures.spring.PaymentEvent$Captured: amount: long\n"), "{}", outcome.output);
    assert!(outcome.output.contains("  added stored fixtures.spring.TaskDocument: due: Instant (dueAt)\n") && outcome.output.contains("  removed stored fixtures.spring.TaskDocument: dueAt: Instant\n"), "{}", outcome.output);
    let finding = outcome.findings.iter().find(|f| f.rule_id == "boundaries-changed").expect("a finding");
    assert_eq!(finding.uri.as_deref(), Some("tests/fixtures/spring/fixtures/spring/OrderService.java"));
    assert!(finding.line > 1, "anchored to the member's line, found {}", finding.line);

    // A configuration change alone: the finding is anchored to the line of the application file.
    std::fs::write(&file, text.replace("  server.port: Integer = 8080, 80 (prod)\n", "  server.port: Integer = 8080\n")).unwrap();
    let outcome = verifier::run(&run).unwrap();
    assert_eq!(outcome.exit_code, 1, "{}", outcome.output);
    assert!(outcome.output.contains("  added configuration: server.port: Integer = 8080, 80 (prod)\n"), "{}", outcome.output);
    let finding = outcome.findings.iter().find(|f| f.rule_id == "boundaries-changed").expect("a finding");
    assert_eq!((finding.uri.as_deref(), finding.line), (Some("tests/fixtures/spring/resources/application.yaml"), 17));
}
