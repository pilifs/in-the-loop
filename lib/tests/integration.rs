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
    let json = serde_json::to_value(&outcome).unwrap();
    assert!(outcome.output.contains("✗ Behaviour of fixtures.Pricing#total changed:"), "{}", outcome.output);
    let witness = outcome.counterexample.unwrap();
    assert_ne!(witness.before, witness.after);
    assert!(witness.input.starts_with("total(priceCents="), "{}", witness.input);
    assert!(std::fs::read_to_string(outcome.work.join("report/equivalence.sarif")).unwrap().contains("behaviour-changed"));
    assert!(outcome.statement.unwrap().exists());
    // How the verdict was reached is data as well as the proof line: JBMC's run, and the witness replayed in the
    // tool's own interpreter (not on a JVM), where it reproduced.
    let search = outcome.search.expect("the checker run");
    assert_eq!((search.engine.as_str(), search.unwind, search.native.is_none()), ("jbmc", 16, true));
    assert!(search.checker.starts_with("JBMC"), "{}", search.checker);
    assert!(search.stage.is_some(), "a small witness is found in a bounded range first");
    let replay = outcome.replay.expect("the witness's replay");
    assert_eq!((replay.by.as_str(), replay.reproduced), ("interpreter", true));
    assert_eq!((json["replay"]["by"].as_str(), json["search"]["engine"].as_str()), (Some("interpreter"), Some("jbmc")), "{json}");
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
    let before = "package fixtures;\npublic final class Shares {\n    static int twice(int x) { return x * 2; }\n    public static long split(long total, int seats, int fee) { return twice(fee); }\n}\n";
    let after = before.replace("return twice(fee);", "return twice(fee - 1) + 2;");
    let (Some(before), Some(after)) = (compile_shares("twice", before), compile_shares("twice-shifted", &after)) else { return };
    let outcome = shares_run(&before, &after, "shares-fallback");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert!(outcome.shared.is_empty(), "{}", outcome.output);
    assert!(outcome.output.contains("note: the counterexample found with Shares.twice taken as one function in both versions does not reproduce once computed as written; proving with the callees' bytecode"), "{}", outcome.output);
    assert!(outcome.work.join("jbmc.log").exists(), "the proof over all inputs ran again as written");
}

/// A callee of a few instructions without a loop, a multiplication, a division or a remainder is computed as
/// written in both versions: as one function it would give the two versions' calls on different arguments
/// unrelated results, a counterexample that never reproduces, and a second run.
#[test]
fn a_small_callee_is_computed_as_written_rather_than_shared() {
    if !has("jbmc") {
        eprintln!("jbmc not found; skipping");
        return;
    }
    let before = "package fixtures;\npublic final class Shares {\n    static int twice(int x) { return x + x; }\n    public static long split(long total, int seats, int fee) { return twice(fee); }\n}\n";
    let after = before.replace("return twice(fee);", "return twice(fee - 1) + 2;");
    let (Some(before), Some(after)) = (compile_shares("sum", before), compile_shares("sum-shifted", &after)) else { return };
    let outcome = shares_run(&before, &after, "shares-small");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert!(outcome.shared.is_empty(), "{}", outcome.output);
    assert!(!outcome.output.contains("note:"), "{}", outcome.output);
    assert!(!outcome.work.join("jbmc-shared.log").exists(), "no run with a stub");
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
    let search = native.search.as_ref().expect("the checker run");
    assert_eq!((search.engine.as_str(), search.stage.as_deref(), search.fallback.as_deref()), ("native", Some("[0:20]"), None));
    let stats = search.native.as_ref().expect("the own checker's numbers");
    assert!(stats.paths > 0 && stats.solver_calls > 0, "{stats:?}");
    assert_eq!(c.input, n.input);
    assert!(native.replay.as_ref().is_some_and(|r| r.by == "interpreter" && r.reproduced));
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
    let layout = jvmcontract::harness::Layout::plain(&["a".into(), "n".into()], &[jvmcontract::classfile::Type::Array(Box::new(jvmcontract::classfile::Type::Int)), jvmcontract::classfile::Type::Int]);
    let harness = jvmcontract::harness::generate("fixtures/Buffers", "prefix", &layout, &jvmcontract::classfile::Type::Array(Box::new(jvmcontract::classfile::Type::Int)), None, 8, None).unwrap();
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
    assert!(proved.output.contains("over a: int[] of length ≤ 8, not null × n: int × v: int"), "{}", proved.output);
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
    // The checker run is recorded with its settings; a proof replays nothing.
    let search = proved.search.as_ref().unwrap();
    assert_eq!((search.engine.as_str(), search.unwind, search.stage.as_deref()), ("jbmc", 16, None), "{search:?}");
    assert!(search.checker.starts_with("JBMC "), "{search:?}");
    assert!(proved.replay.is_none());
    assert!(proved.statement.unwrap().exists());

    let refuted = prove("fixtures.Laws#roundedHalf", Some("n > 0"), Some("2 * result > n"), "rounded-half").unwrap();
    assert_eq!(refuted.verdict, Verdict::Violation, "{}", refuted.output);
    let witness = refuted.counterexample.unwrap();
    assert_eq!(witness.input, "roundedHalf(n=2)", "the smallest even cluster");
    assert_eq!(witness.outcome, "1");
    // The witness was replayed in the interpreter, where the property fails on it too.
    let replay = refuted.replay.as_ref().unwrap();
    assert_eq!((replay.by.as_str(), replay.reproduced), ("interpreter", true));
    assert_eq!(refuted.search.as_ref().unwrap().stage.as_deref(), Some("[0:20]"), "{}", refuted.output);
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
    // The clause as given, and as checked with the exception named in full.
    assert_eq!(declared.throws, ["IllegalArgumentException when n <= 0"]);
    assert_eq!(declared.throws_checked, ["java.lang.IllegalArgumentException when n <= 0"]);
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
    // Typed, the char is its code unit, and the call names the method as in its class file.
    assert_eq!(witness.inputs[0].ty, "char");
    assert!(witness.inputs[0].value.as_ref().and_then(serde_json::Value::as_u64).is_some_and(|unit| unit >= 128), "{:?}", witness.inputs);
    assert_eq!((witness.call.class.as_str(), witness.call.method.as_str(), witness.call.descriptor.as_str(), witness.call.is_static), ("fixtures.Models", "hexDigit", "(C)I", true));
    assert_eq!(witness.call.arguments[0].value, witness.inputs[0].value);
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
        assert_eq!(native.search.as_ref().map(|s| s.engine.as_str()), Some("native"), "{}", native.output);
        assert!(native.search.as_ref().unwrap().native.is_some(), "the own checker's numbers are kept");
        assert_eq!(jbmc.search.as_ref().map(|s| s.engine.as_str()), Some("jbmc"), "{}", jbmc.output);
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
    // Arrays of primitives are in the engine's fragment: under `auto` it proves the search over the symbolic
    // array itself, with the quantifiers' loops, and without the sortedness assumption it finds an unsorted
    // table the search misses a key in, replayed and shrunk like JBMC's witness.
    let correct = "(result == -1 && (\\forall int i; 0 <= i && i < sorted.length; sorted[i] != key)) || (result >= 0 && result < sorted.length && sorted[result] == key)";
    let auto = prove_engine("fixtures.Search#find", Some("(\\forall int i; 0 < i && i < sorted.length; sorted[i - 1] < sorted[i])"), Some(correct), &[], Engine::Auto, "agree-arrays");
    assert_eq!(auto.verdict, Verdict::Verified, "{}", auto.output);
    assert!(auto.output.contains("jvmcontract's own checker (CaDiCaL)"), "{}", auto.output);
    assert!(!auto.output.contains("note: the tool's own checker gave no verdict"), "{}", auto.output);
    let jbmc = prove_engine("fixtures.Search#find", Some("(\\forall int i; 0 < i && i < sorted.length; sorted[i - 1] < sorted[i])"), Some(correct), &[], Engine::Jbmc, "agree-arrays");
    assert_eq!(jbmc.verdict, Verdict::Verified, "{}", jbmc.output);
    let native_only = prove_engine("fixtures.Search#find", None, Some(correct), &[], Engine::Native, "agree-arrays");
    assert_eq!(native_only.verdict, Verdict::Violation, "{}", native_only.output);
    let unsorted = native_only.counterexample.unwrap();
    assert!(unsorted.input.contains("sorted=["), "{}", unsorted.input);
    let jbmc_only = prove_engine("fixtures.Search#find", None, Some(correct), &[], Engine::Jbmc, "agree-arrays");
    assert_eq!(jbmc_only.verdict, Verdict::Violation, "{}", jbmc_only.output);

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
    // The witness typed: a long as an exact decimal string, an int as a number, both versions' calls of (JI)J.
    let json = serde_json::to_value(&witness).unwrap();
    assert_eq!(json["inputs"][0]["type"], "long");
    assert!(json["inputs"][0]["value"].as_str().is_some_and(|v| v.parse::<i64>().is_ok()), "{json}");
    assert!(json["inputs"][1]["value"].is_i64(), "{json}");
    assert_eq!((json["call"]["descriptor"].as_str(), json["previous_call"]["descriptor"].as_str(), json["previous_call"]["classes"].as_str()), (Some("(JI)J"), Some("(JI)J"), Some("before")));
    assert_eq!(json["call"]["arguments"][0]["value"], json["inputs"][0]["value"]);
    let proved = run(&tier, Some("seats >= 6"), Engine::Native, "tier");
    assert_eq!(proved.verdict, Verdict::Verified, "{}", proved.output);
    assert!(proved.vacuous.is_none() && !proved.output.contains("vacuously"), "{}", proved.output);
    assert_eq!(run(&tier, None, Engine::Native, "tier-unscoped").verdict, Verdict::Violation);

    // A scope every input satisfies leaves the proof nothing to cover, which the tool says: the verdict is still
    // verified, so that the statement is not a false alarm, and the line is for the reviewer.
    let vacuous = run(&tier, Some("seats >= 6 || seats < 6"), Engine::Native, "tier-vacuous");
    assert_eq!(vacuous.verdict, Verdict::Verified, "{}", vacuous.output);
    assert!(vacuous.output.contains("\n  vacuously: no input in the domain reaches the calls, every one being among the intended inputs (--unchanged-unless)"), "{}", vacuous.output);
    assert!(vacuous.vacuous.is_some());
    // The same for an assumption no input satisfies.
    let empty = prove_engine("fixtures.Laws#majority", Some("n > 0 && n <= 0"), Some("2L * result > n"), &[], Engine::Native, "majority-vacuous");
    assert_eq!(empty.verdict, Verdict::Verified, "{}", empty.output);
    assert!(empty.output.contains("\n  vacuously: no input in the domain reaches the calls, every one failing the assumption (--assume)"), "{}", empty.output);
    let plain = prove_engine("fixtures.Laws#majority", Some("n > 0"), Some("2L * result > n && result <= n"), &[], Engine::Native, "majority-native");
    assert_eq!(plain.verdict, Verdict::Verified, "{}", plain.output);
    assert!(plain.vacuous.is_none() && !plain.output.contains("vacuously"), "{}", plain.output);
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

/// An exponential backoff as a record: the delay before an attempt doubles from the base up to the cap, by a loop
/// that stops at the cap. The compact constructor keeps the components where the doubling cannot overflow.
const BACKOFF_LOOP: &str = r#"package fixtures;
public record Backoff(long baseMillis, long capMillis) {
    public Backoff {
        if (baseMillis <= 0 || capMillis < baseMillis || capMillis > 86_400_000L) { throw new IllegalArgumentException("base and cap"); }
    }
    public long delayMillis(int attempt) {
        long delay = baseMillis;
        for (int i = 0; i < attempt && delay < capMillis; i++) { delay = Math.min(capMillis, delay * 2); }
        return delay;
    }
}
"#;

/// The loop replaced by a shift, which wraps at 64 and overflows before that.
const BACKOFF_SHIFT: &str = r#"package fixtures;
public record Backoff(long baseMillis, long capMillis) {
    public Backoff {
        if (baseMillis <= 0 || capMillis < baseMillis || capMillis > 86_400_000L) { throw new IllegalArgumentException("base and cap"); }
    }
    public long delayMillis(int attempt) {
        return Math.min(capMillis, baseMillis << attempt);
    }
}
"#;

/// The loop replaced by a shift kept short of overflow, which is the loop's value.
const BACKOFF_CLOSED: &str = r#"package fixtures;
public record Backoff(long baseMillis, long capMillis) {
    public Backoff {
        if (baseMillis <= 0 || capMillis < baseMillis || capMillis > 86_400_000L) { throw new IllegalArgumentException("base and cap"); }
    }
    public long delayMillis(int attempt) {
        if (attempt <= 0) { return baseMillis; }
        int shift = Math.min(attempt, Long.numberOfLeadingZeros(baseMillis) - 1);
        return Math.min(capMillis, baseMillis << shift);
    }
}
"#;

/// A token bucket's state as a record, credited with the tokens earned since the last refill, as the next state.
const BUCKET_BEFORE: &str = r#"package fixtures;
public record Bucket(long tokens, long lastNanos) {
    public Bucket credited(long earned, long nowNanos, long capacity) {
        return new Bucket(Math.min(capacity, tokens + earned), nowNanos);
    }
}
"#;

fn compile_record(name: &str, class: &str, source: &str) -> Option<PathBuf> {
    compile_writers(name, class, source)
}

fn record_run(before: &Path, after: &Path, target: &str, scope: Option<&str>, name: &str) -> equivalence::Outcome {
    let mut options = equivalence::Options::new(before, after, target);
    let work = target_tmp().join(format!("equivalence-{name}"));
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    options.timeout_seconds = 120;
    options.unwind = 32;
    options.unchanged_unless = scope.map(str::to_string);
    equivalence::run(&options).unwrap()
}

/// A batch commit as a static method over the batch's start and size, before the two were gathered into a record.
const BATCH_STATIC: &str = r#"package fixtures;
public final class BatchCommit {
    private BatchCommit() {}
    public static final int NONE_FAILED = -1;
    public static long offsetToCommit(long batchStart, int batchSize, int failedIndex) {
        if (batchStart < 0 || batchSize <= 0 || failedIndex < NONE_FAILED || failedIndex >= batchSize) {
            throw new IllegalArgumentException("bad batch");
        }
        return failedIndex == NONE_FAILED ? batchStart + batchSize : batchStart + failedIndex;
    }
}
"#;

/// The same as the record's method, the guard on the batch moved into the constructor and the one on the index kept.
const BATCH_RECORD: &str = r#"package fixtures;
public record Batch(long start, int size) {
    public static final int NONE_FAILED = -1;
    public Batch {
        if (start < 0 || size <= 0) {
            throw new IllegalArgumentException("bad batch");
        }
    }
    public long offsetToCommit(int failedIndex) {
        if (failedIndex < NONE_FAILED || failedIndex >= size) {
            throw new IllegalArgumentException("bad index");
        }
        return failedIndex == NONE_FAILED ? start + size : start + failedIndex;
    }
}
"#;

/// The record as a parameter of the static method instead.
const BATCH_PARAMETER: &str = r#"package fixtures;
public final class BatchCommit {
    private BatchCommit() {}
    public static final int NONE_FAILED = -1;
    public record Batch(long start, int size) {
        public Batch {
            if (start < 0 || size <= 0) {
                throw new IllegalArgumentException("bad batch");
            }
        }
    }
    public static long offsetToCommit(Batch batch, int failedIndex) {
        if (failedIndex < NONE_FAILED || failedIndex >= batch.size()) {
            throw new IllegalArgumentException("bad index");
        }
        return failedIndex == NONE_FAILED ? batch.start() + batch.size() : batch.start() + failedIndex;
    }
}
"#;

/// A static method that became the record's method is related to its previous version by expressions over the
/// components: the record is built in the new version only, and the previous version gets the components.
#[test]
fn a_static_method_that_became_a_records_method_is_related_by_the_components() {
    if !has("jbmc") {
        return;
    }
    let (Some(before), Some(after)) = (compile_record("batch-static", "BatchCommit", BATCH_STATIC), compile_record("batch-record", "Batch", BATCH_RECORD)) else { return };
    let outcome = related_run(&before, &after, "fixtures.Batch#offsetToCommit", Some("fixtures.BatchCommit#offsetToCommit"), Some("this.start, this.size, failedIndex"), None, None, "batch-related");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert_eq!(outcome.domain.as_deref(), Some("this: Batch(start: long, size: int) × failedIndex: int"));
    assert!(outcome.output.starts_with("✓ fixtures.Batch#offsetToCommit behaves as the previous fixtures.BatchCommit#offsetToCommit(this.start, this.size, failedIndex) on every input ("), "{}", outcome.output);
    let statement = std::fs::read_to_string(outcome.statement.unwrap()).unwrap();
    assert!(statement.contains("fixtures.Batch this_after; // the previous version takes the components"), "{statement}");
    assert!(statement.contains("try { a = before.fixtures.BatchCommit.offsetToCommit(batchStart_, batchSize_, failedIndex_); }"), "{statement}");
    // Without the expressions, the tool says what to give.
    let refused = related_run(&before, &after, "fixtures.Batch#offsetToCommit", Some("fixtures.BatchCommit#offsetToCommit"), None, None, None, "batch-unrelated");
    assert_eq!(refused.verdict, Verdict::Unverifiable, "{}", refused.output);
    assert!(refused.output.contains("give the previous version's arguments as expressions over the record's components and the parameters with --before-arguments, such as \"this.start, this.size, failedIndex\""), "{}", refused.output);
    // The record as a parameter of a static method, the same way.
    let parameter = compile_record("batch-parameter", "BatchCommit", BATCH_PARAMETER).unwrap();
    let outcome = related_run(&before, &parameter, "fixtures.BatchCommit#offsetToCommit", None, Some("batch.start, batch.size, failedIndex"), None, None, "batch-parameter");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert_eq!(outcome.domain.as_deref(), Some("batch: Batch(start: long, size: int) × failedIndex: int"));
}

/// The guard moved into the record's constructor without the part about the failed index, which is no component:
/// the previous version throws where the new one commits past the batch.
#[test]
fn a_check_lost_in_the_move_to_a_record_is_found_on_the_components() {
    if !has("jbmc") {
        return;
    }
    let unchecked = BATCH_RECORD.replace("        if (failedIndex < NONE_FAILED || failedIndex >= size) {\n            throw new IllegalArgumentException(\"bad index\");\n        }\n", "");
    assert_ne!(unchecked, BATCH_RECORD);
    let (Some(before), Some(after)) = (compile_record("batch-static-b", "BatchCommit", BATCH_STATIC), compile_record("batch-unchecked", "Batch", &unchecked)) else { return };
    let outcome = related_run(&before, &after, "fixtures.Batch#offsetToCommit", Some("fixtures.BatchCommit#offsetToCommit"), Some("this.start, this.size, failedIndex"), None, None, "batch-unchecked");
    assert_eq!(outcome.verdict, Verdict::Violation, "{}", outcome.output);
    let witness = outcome.counterexample.unwrap();
    assert_eq!(witness.input, "offsetToCommit(this=Batch[start=0, size=1], failedIndex=1), previously offsetToCommit(batchStart=0, batchSize=1, failedIndex=1)", "{}", outcome.output);
    // The witness as data: the new version's call on a record built from its components, and the previous
    // version's on the values the expressions computed, each argument naming its expression.
    let call = serde_json::to_value(&witness.call).unwrap();
    assert_eq!(call["class"], "fixtures.Batch");
    assert_eq!((call["descriptor"].as_str(), call["static"].as_bool(), call["classes"].as_str()), (Some("(I)J"), Some(false), Some("after")));
    assert_eq!(call["receiver"]["components"], serde_json::json!([{"name": "start", "type": "long", "value": "0", "from": "this.start"}, {"name": "size", "type": "int", "value": 1, "from": "this.size"}]));
    let previous = serde_json::to_value(witness.previous_call.as_ref().expect("the previous version's call")).unwrap();
    assert_eq!((previous["class"].as_str(), previous["descriptor"].as_str(), previous["static"].as_bool(), previous["classes"].as_str()), (Some("fixtures.BatchCommit"), Some("(JII)J"), Some(true), Some("before")));
    assert_eq!(previous["arguments"].as_array().unwrap().iter().map(|a| (a["name"].as_str().unwrap(), a["from"].as_str().unwrap())).collect::<Vec<_>>(), [("batchStart", "this.start"), ("batchSize", "this.size"), ("failedIndex", "failedIndex")]);
    assert_eq!(witness.inputs.iter().map(|t| t.name.as_str()).collect::<Vec<_>>(), ["this.start", "this.size", "failedIndex"]);
    assert!(witness.before.starts_with("throws IllegalArgumentException"), "{}", outcome.output);
    assert_eq!(witness.after, "1", "{}", outcome.output);
}

/// A window of ints, as a record with a method.
const WINDOW_RECORD: &str = r#"package fixtures;
public record Window(int lo, int hi) {
    public Window {
        if (lo > hi) {
            throw new IllegalArgumentException("empty window");
        }
    }
    public int clamp(int x) {
        return x < lo ? lo : x > hi ? hi : x;
    }
    public boolean contains(int x) {
        return lo <= x && x < hi;
    }
}
"#;

/// The same record with a component added, its methods as they were.
const WINDOW_STEPPED: &str = r#"package fixtures;
public record Window(int lo, int hi, int step) {
    public Window {
        if (lo > hi || step <= 0) {
            throw new IllegalArgumentException("empty window or no step");
        }
    }
    public int clamp(int x) {
        return x < lo ? lo : x > hi ? hi : x;
    }
    public boolean contains(int x) {
        return lo <= x && x < hi;
    }
}
"#;

/// The record's methods made static, the window's bounds as parameters: `clamp` as it was, `contains` with the
/// upper bound now inside.
const WINDOW_STATIC: &str = r#"package fixtures;
public final class Windows {
    private Windows() {}
    public static int clamp(int lo, int hi, int x) {
        if (lo > hi) {
            throw new IllegalArgumentException("empty window");
        }
        return x < lo ? lo : x > hi ? hi : x;
    }
    public static boolean contains(int lo, int hi, int x) {
        return lo <= x && x <= hi;
    }
}
"#;

/// A record that gained a component is related to its previous version by building the previous record from the
/// new components, with a constructor call first among the expressions of --before-arguments.
#[test]
fn a_record_that_gained_a_component_is_related_by_building_the_previous_record() {
    if !has("jbmc") {
        return;
    }
    let (Some(before), Some(after)) = (compile_record("window-record", "Window", WINDOW_RECORD), compile_record("window-stepped", "Window", WINDOW_STEPPED)) else { return };
    let outcome = related_run(&before, &after, "fixtures.Window#clamp", None, Some("new Window(this.lo, this.hi), x"), None, None, "window-stepped");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert_eq!(outcome.domain.as_deref(), Some("this: Window(lo: int, hi: int, step: int) × x: int"));
    assert!(outcome.output.starts_with("✓ fixtures.Window#clamp behaves as the previous clamp(x) on new Window(this.lo, this.hi) on every input ("), "{}", outcome.output);
    let statement = std::fs::read_to_string(outcome.statement.unwrap()).unwrap();
    assert!(statement.contains("before.fixtures.Window this_ = new before.fixtures.Window(this_lo, this_hi); int x_ = x;"), "{statement}");
    assert!(statement.contains("try { a = this_.clamp(x_); }"), "{statement}");
    assert!(statement.contains("try { b = this_after.clamp(x); }"), "{statement}");
    // Without the expressions, the tool says what to give; with the wrong number of components, too.
    let refused = related_run(&before, &after, "fixtures.Window#clamp", None, None, None, None, "window-stepped-unrelated");
    assert_eq!(refused.verdict, Verdict::Unverifiable, "{}", refused.output);
    assert!(refused.output.contains("the receiver's components changed: Window(lo: int, hi: int) before, Window(lo: int, hi: int, step: int) now; build the previous version's receiver from the new components with --before-arguments, such as \"new Window(this.lo, this.hi), x\""), "{}", refused.output);
    let refused = related_run(&before, &after, "fixtures.Window#clamp", None, Some("new Window(this.lo), x"), None, None, "window-stepped-short");
    assert_eq!(refused.verdict, Verdict::Unverifiable, "{}", refused.output);
    assert!(refused.output.contains("Window has 2 components, 1 given; build it as new Window(lo, hi)"), "{}", refused.output);
}

/// A record's method made static is related to its previous version by building the receiver it had from the
/// new parameters; a bound that moved with it is found.
#[test]
fn a_records_method_made_static_is_related_by_building_its_receiver() {
    if !has("jbmc") {
        return;
    }
    let (Some(before), Some(after)) = (compile_record("window-record-before", "Window", WINDOW_RECORD), compile_record("window-static", "Windows", WINDOW_STATIC)) else { return };
    let outcome = related_run(&before, &after, "fixtures.Windows#clamp", Some("fixtures.Window#clamp"), Some("new Window(lo, hi), x"), None, None, "window-static");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert_eq!(outcome.domain.as_deref(), Some("lo: int × hi: int × x: int"));
    assert!(outcome.output.starts_with("✓ fixtures.Windows#clamp behaves as the previous fixtures.Window#clamp(x) on new Window(lo, hi) on every input ("), "{}", outcome.output);
    let refused = related_run(&before, &after, "fixtures.Windows#clamp", Some("fixtures.Window#clamp"), None, None, None, "window-static-unrelated");
    assert_eq!(refused.verdict, Verdict::Unverifiable, "{}", refused.output);
    assert!(refused.output.contains("the previous version is a method of the record Window and the new one a static method; build its receiver from the new parameters with --before-arguments, such as \"new Window(lo, hi), x\""), "{}", refused.output);
    let refused = related_run(&before, &after, "fixtures.Windows#clamp", Some("fixtures.Window#clamp"), Some("lo, hi, x"), None, None, "window-static-flat");
    assert_eq!(refused.verdict, Verdict::Unverifiable, "{}", refused.output);
    assert!(refused.output.contains("the previous version is a method of the record Window; build its receiver from the new parameters as the first argument, new Window(lo, hi)"), "{}", refused.output);
    let outcome = related_run(&before, &after, "fixtures.Windows#contains", Some("fixtures.Window#contains"), Some("new Window(lo, hi), x"), None, None, "window-static-contains");
    assert_eq!(outcome.verdict, Verdict::Violation, "{}", outcome.output);
    let witness = outcome.counterexample.unwrap();
    assert_eq!(witness.input, "contains(lo=0, hi=0, x=0), previously contains(this=Window[lo=0, hi=0], x=0)", "{}", outcome.output);
    // The previous version's receiver, built by the expression, is a record of the values it computed.
    let previous = witness.previous_call.as_ref().expect("the previous version's call");
    assert_eq!((previous.class.as_str(), previous.is_static), ("fixtures.Window", false));
    let receiver = previous.receiver.as_ref().expect("the receiver built");
    assert_eq!(receiver.ty, "fixtures.Window");
    assert_eq!(receiver.components.as_ref().unwrap().iter().map(|c| c.from.as_deref().unwrap()).collect::<Vec<_>>(), ["lo", "hi"]);
    assert!(witness.call.receiver.is_none() && witness.call.is_static);
    assert_eq!(witness.before, "false", "{}", outcome.output);
    assert_eq!(witness.after, "true", "{}", outcome.output);
}

/// A method of a record whose components are primitive is proved on the components: the harness builds the
/// record in both versions, skips what a constructor rejects, and calls the method on it.
#[test]
fn a_method_of_a_record_is_proved_on_its_components() {
    if !has("jbmc") {
        return;
    }
    let (Some(before), Some(after)) = (compile_record("backoff-loop", "Backoff", BACKOFF_LOOP), compile_record("backoff-closed", "Backoff", BACKOFF_CLOSED)) else { return };
    let outcome = record_run(&before, &after, "fixtures.Backoff#delayMillis", None, "backoff-closed");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert_eq!(outcome.domain.as_deref(), Some("this: Backoff(baseMillis: long, capMillis: long) × attempt: int"));
    assert!(outcome.output.contains("✓ fixtures.Backoff#delayMillis behaves as before on every input ("), "{}", outcome.output);
    let statement = std::fs::read_to_string(outcome.statement.unwrap()).unwrap();
    assert!(statement.contains("public static void check(long this_baseMillis, long this_capMillis, int attempt)"), "{statement}");
    assert!(statement.contains("try { this_before = new before.fixtures.Backoff(this_baseMillis, this_capMillis); this_after = new fixtures.Backoff(this_baseMillis, this_capMillis); } catch (Throwable t) { return; }"), "{statement}");
    assert!(statement.contains("try { a = this_before.delayMillis(attempt); }"), "{statement}");
}

/// The loop replaced by a shift: the shift wraps at 64 and overflows before that, which the components show.
#[test]
fn a_shift_that_overflows_is_found_on_the_records_components() {
    if !has("jbmc") {
        return;
    }
    let (Some(before), Some(after)) = (compile_record("backoff-loop-b", "Backoff", BACKOFF_LOOP), compile_record("backoff-shift", "Backoff", BACKOFF_SHIFT)) else { return };
    let outcome = record_run(&before, &after, "fixtures.Backoff#delayMillis", None, "backoff-shift");
    assert_eq!(outcome.verdict, Verdict::Violation, "{}", outcome.output);
    let witness = outcome.counterexample.unwrap();
    assert!(witness.input.starts_with("delayMillis(this=Backoff[baseMillis="), "{}", outcome.output);
    assert_ne!(witness.before, witness.after, "{}", outcome.output);
    assert_eq!(witness.values.len(), 3, "{:?}", witness.values);
    assert!(outcome.output.contains("✗ Behaviour of fixtures.Backoff#delayMillis changed:"), "{}", outcome.output);
    // The same record in both versions: the previous version's call builds its own record from the same inputs.
    let previous = witness.previous_call.as_ref().expect("the previous version's call");
    assert_eq!((previous.classes.as_str(), previous.descriptor.as_str()), ("before", witness.call.descriptor.as_str()));
    assert_eq!(previous.receiver, witness.call.receiver);
    assert_eq!(witness.inputs.iter().map(|t| t.ty.as_str()).collect::<Vec<_>>(), ["long", "long", "int"]);
    // Below 63 attempts from a base of one millisecond, the shift stays within a long and agrees with the loop: a
    // scope names the receiver's components as the method does, or as this.component.
    let scoped = record_run(&before, &after, "fixtures.Backoff#delayMillis", Some("attempt < 0 || attempt > 62 || this.baseMillis != 1"), "backoff-shift-scoped");
    assert_eq!(scoped.verdict, Verdict::Verified, "{}", scoped.output);
    assert!(scoped.output.contains(" where !(attempt < 0 || attempt > 62 || this.baseMillis != 1) ("), "{}", scoped.output);
}

/// A record result is compared component by component, in the fields of the record of each version.
#[test]
fn a_record_result_is_compared_component_by_component() {
    if !has("jbmc") {
        return;
    }
    let equal = BUCKET_BEFORE.replace("Math.min(capacity, tokens + earned)", "tokens + earned > capacity ? capacity : tokens + earned");
    let forgetful = BUCKET_BEFORE.replace("new Bucket(Math.min(capacity, tokens + earned), nowNanos)", "new Bucket(Math.min(capacity, tokens + earned), lastNanos)");
    let (Some(before), Some(after), Some(wrong)) = (compile_record("bucket-before", "Bucket", BUCKET_BEFORE), compile_record("bucket-equal", "Bucket", &equal), compile_record("bucket-forgetful", "Bucket", &forgetful)) else { return };
    let outcome = record_run(&before, &after, "fixtures.Bucket#credited", None, "bucket-equal");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert_eq!(outcome.domain.as_deref(), Some("this: Bucket(tokens: long, lastNanos: long) × earned: long × nowNanos: long × capacity: long"));
    let statement = std::fs::read_to_string(outcome.statement.unwrap()).unwrap();
    assert!(statement.contains("(ea != 0 || (a == null ? b == null : b != null && a.tokens == b.tokens && a.lastNanos == b.lastNanos))"), "{statement}");
    let outcome = record_run(&before, &wrong, "fixtures.Bucket#credited", None, "bucket-forgetful");
    assert_eq!(outcome.verdict, Verdict::Violation, "{}", outcome.output);
    let witness = outcome.counterexample.unwrap();
    assert!(witness.input.starts_with("credited(this=Bucket[tokens="), "{}", outcome.output);
    assert!(witness.before.starts_with("Bucket[tokens=") && witness.after.starts_with("Bucket[tokens="), "{}", outcome.output);
    assert_ne!(witness.before, witness.after, "{}", outcome.output);
}

/// The same bucket counting its refills in a third component.
const BUCKET_COUNTED: &str = r#"package fixtures;
public record Bucket(long tokens, long lastNanos, int refills) {
    public Bucket credited(long earned, long nowNanos, long capacity) {
        return new Bucket(Math.min(capacity, tokens + earned), nowNanos, refills + 1);
    }
}
"#;

/// The tokens after a credit alone, before the state was gathered into a record.
const BUCKET_TOKENS_STATIC: &str = r#"package fixtures;
public final class Bucket {
    private Bucket() {}
    public static long credited(long tokens, long lastNanos, long earned, long nowNanos, long capacity) {
        return Math.min(capacity, tokens + earned);
    }
}
"#;

/// A record result that gained a component is related to the record it was by a relation over the components of
/// both, `previous.c` and `result.c`; a result that became a record, to the value it was.
#[test]
fn a_record_result_of_other_components_is_related_by_a_relation_over_them() {
    if !has("jbmc") {
        return;
    }
    let forgetful = BUCKET_COUNTED.replace("nowNanos, refills + 1)", "lastNanos, refills + 1)");
    let (Some(before), Some(after), Some(wrong), Some(tokens_only)) = (compile_record("bucket-before-r", "Bucket", BUCKET_BEFORE), compile_record("bucket-counted", "Bucket", BUCKET_COUNTED), compile_record("bucket-counted-forgetful", "Bucket", &forgetful), compile_record("bucket-tokens-static", "Bucket", BUCKET_TOKENS_STATIC)) else { return };
    let arguments = Some("new Bucket(this.tokens, this.lastNanos), earned, nowNanos, capacity");
    let relation = Some("previous.tokens == result.tokens && previous.lastNanos == result.lastNanos");
    let outcome = related_run(&before, &after, "fixtures.Bucket#credited", None, arguments, relation, None, "bucket-counted");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    assert_eq!(outcome.domain.as_deref(), Some("this: Bucket(tokens: long, lastNanos: long, refills: int) × earned: long × nowNanos: long × capacity: long"));
    assert!(outcome.output.contains(", the results related by previous.tokens == result.tokens && previous.lastNanos == result.lastNanos"), "{}", outcome.output);
    let statement = std::fs::read_to_string(outcome.statement.unwrap()).unwrap();
    assert!(statement.contains("before.fixtures.Bucket previous = a; fixtures.Bucket result = b;"), "{statement}");
    assert!(statement.contains("(ea != 0 || (previous.tokens() == result.tokens() && previous.lastNanos() == result.lastNanos()))"), "{statement}");
    // Without the relation, the tool says what to give.
    let refused = related_run(&before, &after, "fixtures.Bucket#credited", None, arguments, None, None, "bucket-counted-unrelated");
    assert_eq!(refused.verdict, Verdict::Unverifiable, "{}", refused.output);
    assert!(refused.output.contains("the result's components changed: Bucket(tokens: long, lastNanos: long) before, Bucket(tokens: long, lastNanos: long, refills: int) now; say how the results are related with --results-agree-when, a boolean expression over the new parameters and the results' components previous.c and result.c, such as \"previous.tokens == result.tokens && previous.lastNanos == result.lastNanos\""), "{}", refused.output);
    // A version that keeps the old time breaks the relation; the replays are the records.
    let outcome = related_run(&before, &wrong, "fixtures.Bucket#credited", None, arguments, relation, None, "bucket-counted-forgetful");
    assert_eq!(outcome.verdict, Verdict::Violation, "{}", outcome.output);
    let witness = outcome.counterexample.unwrap();
    assert!(witness.input.starts_with("credited(this=Bucket[tokens="), "{}", outcome.output);
    assert!(witness.before.starts_with("Bucket[tokens=") && witness.after.starts_with("Bucket[tokens="), "{}", outcome.output);
    assert!(outcome.output.contains("the results are not related by previous.tokens == result.tokens && previous.lastNanos == result.lastNanos"), "{}", outcome.output);
    // The tokens alone, before the state was a record: the previous value is one component of the new result.
    let outcome = related_run(&tokens_only, &before, "fixtures.Bucket#credited", None, Some("this.tokens, this.lastNanos, earned, nowNanos, capacity"), Some("previous == result.tokens"), None, "bucket-became-record");
    assert_eq!(outcome.verdict, Verdict::Verified, "{}", outcome.output);
    let statement = std::fs::read_to_string(outcome.statement.unwrap()).unwrap();
    assert!(statement.contains("long previous = a; fixtures.Bucket result = b;"), "{statement}");
    let refused = related_run(&tokens_only, &before, "fixtures.Bucket#credited", None, Some("this.tokens, this.lastNanos, earned, nowNanos, capacity"), None, None, "bucket-became-record-unrelated");
    assert_eq!(refused.verdict, Verdict::Unverifiable, "{}", refused.output);
    assert!(refused.output.contains("the previous version returns long and the new one the record Bucket(tokens: long, lastNanos: long); say how the results are related with --results-agree-when, a boolean expression over the new parameters, previous and the result's components result.c, such as \"previous == result.tokens\""), "{}", refused.output);
}

/// A method identical in both versions is still proved when the record's constructor changed, since the harness
/// builds the receiver through it: a constructor that clamps the cap changes what the method returns.
#[test]
fn a_record_whose_constructor_changed_is_not_identical() {
    if !has("jbmc") {
        return;
    }
    let clamped = BACKOFF_LOOP.replace("throw new IllegalArgumentException(\"base and cap\"); }", "throw new IllegalArgumentException(\"base and cap\"); }\n        capMillis = Math.min(capMillis, 1000L);");
    let (Some(before), Some(after)) = (compile_record("backoff-loop-c", "Backoff", BACKOFF_LOOP), compile_record("backoff-clamped", "Backoff", &clamped)) else { return };
    let outcome = record_run(&before, &after, "fixtures.Backoff#delayMillis", None, "backoff-clamped");
    assert_eq!(outcome.verdict, Verdict::Violation, "{}", outcome.output);
    assert!(!outcome.output.contains("nothing to prove"), "{}", outcome.output);
    let witness = outcome.counterexample.unwrap();
    assert!(witness.input.starts_with("delayMillis(this=Backoff[baseMillis="), "{}", outcome.output);
    let unchanged = record_run(&before, &compile_record("backoff-loop-d", "Backoff", BACKOFF_LOOP).unwrap(), "fixtures.Backoff#delayMillis", None, "backoff-same");
    assert_eq!(unchanged.verdict, Verdict::Verified, "{}", unchanged.output);
    assert!(unchanged.output.contains("nothing to prove"), "{}", unchanged.output);
}

const GAPS: &str = r#"
package fixtures;

public class Gaps {
    static class A { int x; }
    static class B extends A { int x; }
    static class Table {
        static final int[] PRIMES = { 2, 3, 5 };
        static int first() { return 7; }
    }
    record Point(int x, int y) {}

    public static int capacity(int n) { new java.util.ArrayList<Object>(n); return 1; }
    public static int nullMonitor(int n) { synchronized ((Object) null) { return 1; } }
    public static int randomBytes(byte[] out) { new java.util.Random(1).nextBytes(out); return out.length; }
    public static int hiding(int n) { B b = new B(); b.x = n; ((A) b).x = 2; return b.x; }
    public static boolean sameLiteral(int n) { String s = "a"; String t = "a"; return s == t; }
    public static int initialised(int n) { return Table.first() + n; }
    public static String described(Point p) { return "at " + p; }
    public static int exact(int n) {
        if (n < 0) throw new IllegalArgumentException("negative: " + n);
        return new Point(n, n).x() + Math.addExact(n, 1);
    }
    public static int firstByte(byte[] out) { if (out.length == 0) return 0; new java.util.Random(1).nextBytes(out); return out[0]; }
    public static int bits(int n) { return 32 - Integer.numberOfLeadingZeros(n); }
    public static int roll(int sides) { return new java.util.Random(7).nextInt(sides) + 1; }
}
"#;

/// The gap scan (step 1a of llm-dlc/loops/sound-verdicts.md) names each construct the tool's own checker
/// approximates: a JDK constructor that may throw (a review's reproducer), a `void` JDK mutator of an argument
/// array, and a class initializer; it counts the JDK calls the engine reproduces exactly (an exception's
/// constructor, `Record.<init>`, `Math.addExact`) as no gap, and a monitor (step 1b), a hidden field and a literal
/// compared by reference (step 1c), which the engine implements, as none either.
#[test]
fn the_gap_scan_names_what_the_own_checker_approximates() {
    let dir = target_tmp().join("gaps-src");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("Gaps.java"), GAPS).unwrap();
    let Some(classes) = compile("gaps", &[dir.join("Gaps.java")]) else { return };
    let cp = jvmcontract::witness::classpath([classes.as_path()]).unwrap().with_models(true);
    let scan = |method: &str| {
        let targets = vec![format!("fixtures.Gaps#{method}")];
        let roots = jvmcontract::bmc::gaps::roots(&cp, &targets).unwrap();
        let s = jvmcontract::bmc::gaps::scan(&cp, &roots).unwrap();
        let ids: Vec<String> = s.records().into_iter().map(|g| g.id.split('@').next().unwrap().to_string()).collect();
        (ids, s)
    };
    let (ids, s) = scan("capacity");
    assert_eq!(ids, ["jdk-constructor:java.util.ArrayList.<init>(I)V"]);
    assert_eq!(s.records()[0].sites, ["fixtures.Gaps.capacity:13"]);
    let (ids, _) = scan("nullMonitor");
    assert!(ids.is_empty(), "{ids:?}");
    let (ids, _) = scan("randomBytes");
    assert_eq!(ids, ["jdk-constructor:java.util.Random.<init>(J)V", "jdk-void-method:java.util.Random.nextBytes([B)V"]);
    // A hidden field is a second field, and a literal is one object, as on the JVM (step 1c): neither is a gap.
    let (ids, _) = scan("hiding");
    assert!(ids.is_empty(), "{ids:?}");
    let (ids, _) = scan("sameLiteral");
    assert!(ids.is_empty(), "{ids:?}");
    let (ids, s) = scan("initialised");
    assert_eq!(ids, ["class-initializer:fixtures.Gaps$Table.<clinit>()V"]);
    assert!(s.refused.is_empty(), "{:?}", s.refused);
    // javac from JDK 19 on converts the object with `String.valueOf` before the concatenation, which the engine
    // refuses; the bytecode of JDK 9 to 18 passes the object itself, a `string-conversion` gap.
    let (ids, s) = scan("described");
    assert_eq!(ids, ["jdk-static-method:java.lang.String.valueOf(Ljava/lang/Object;)Ljava/lang/String;"]);
    assert!(s.refused.is_empty(), "{:?}", s.refused);
    // A call whose value the proof reads (step 3c): a static JDK method the engine does not model, and a JDK
    // method returning a primitive.
    let (ids, _) = scan("bits");
    assert_eq!(ids, ["jdk-static-method:java.lang.Integer.numberOfLeadingZeros(I)I"]);
    let (ids, _) = scan("roll");
    assert_eq!(ids, ["jdk-constructor:java.util.Random.<init>(J)V", "jdk-primitive-method:java.util.Random.nextInt(I)I"]);
    let (ids, s) = scan("exact");
    assert!(ids.is_empty(), "{ids:?}");
    let exact: Vec<&String> = s.exact.keys().collect();
    assert_eq!(exact, ["java.lang.IllegalArgumentException.<init>(Ljava/lang/String;)V", "java.lang.Math.addExact", "java.lang.Record.<init>()V"]);
    // A gap of the JDK names the JDK's version, so that a contract for it says what it was checked against.
    let (_, s) = scan("capacity");
    if let Some(jdk) = &s.jdk {
        assert_eq!(s.records()[0].id, format!("jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-{jdk}"));
    }
}

/// Step 1b of llm-dlc/loops/sound-verdicts.md: the tool's own checker meets the gaps as it runs. Under `--gaps strict`
/// (the default) a claim the JVM refutes through a JDK call the engine does not implement is never `Verified`: the
/// constructor `new ArrayList<>(n)` (a review's reproducer, which throws for a negative `n`) and a `void` JDK mutator
/// of an argument array (`Random.nextBytes`) are refused by name, on the native engine and under `--engine auto`,
/// which does not hand them to JBMC; `synchronized (null)` (the other reproducer) is a violation, as on the JVM.
/// Under `--gaps assume` the approximation is kept, and the verdict names each gap it assumed.
#[test]
fn a_gap_is_refused_by_name_under_strict_and_named_as_an_assumption_under_assume() {
    use jvmcontract::bmc::gaps::{GapMode, GapTreatment};
    use jvmcontract::Engine;
    let dir = target_tmp().join("gaps-engine-src");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("Gaps.java"), GAPS).unwrap();
    let Some(classes) = compile("gaps-engine", &[dir.join("Gaps.java")]) else { return };
    // The JVM refutes each claim below: what a `Verified` would have hidden.
    if has("java") {
        let probe = "public class Probe { public static void main(String[] a) {\n"
            .to_string()
            + "try { System.out.println(fixtures.Gaps.capacity(-1)); } catch (Throwable t) { System.out.println(t.getClass().getName()); }\n"
            + "try { System.out.println(fixtures.Gaps.nullMonitor(0)); } catch (Throwable t) { System.out.println(t.getClass().getName()); }\n"
            + "System.out.println(fixtures.Gaps.firstByte(new byte[1])); } }\n";
        std::fs::write(dir.join("Probe.java"), probe).unwrap();
        let status = Command::new("javac").args(["-proc:none", "-cp"]).arg(&classes).arg("-d").arg(&classes).arg(dir.join("Probe.java")).status().expect("javac runs");
        assert!(status.success());
        let run = Command::new("java").arg("-cp").arg(&classes).arg("Probe").output().expect("java runs");
        let lines = String::from_utf8_lossy(&run.stdout).lines().map(str::to_string).collect::<Vec<_>>();
        assert_eq!(lines[..2], ["java.lang.IllegalArgumentException", "java.lang.NullPointerException"], "{lines:?}");
        assert_ne!(lines[2], "0", "Random(1) fills the array, so its first byte is not the 0 it held");
    }
    let prove = |method: &str, assert: &str, engine: Engine, gaps: GapMode| {
        let mut options = property::Options::new(std::slice::from_ref(&classes), &format!("fixtures.Gaps#{method}"));
        options.assert = Some(assert.into());
        options.engine = engine;
        options.gaps = gaps;
        let work = target_tmp().join(format!("property-gaps-{method}-{engine:?}-{gaps:?}"));
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        property::run(&options).unwrap()
    };
    let ids = |o: &property::Outcome, treatment: GapTreatment| -> Vec<String> {
        let search = o.search.as_ref().expect("a checker ran");
        assert_eq!(search.engine, "native", "{}", o.output);
        assert!(search.gaps.iter().all(|g| g.treatment == Some(treatment)), "{:?}", search.gaps);
        search.gaps.iter().map(|g| g.id.split('@').next().unwrap().to_string()).collect()
    };
    for engine in [Engine::Native, Engine::Auto] {
        let o = prove("capacity", "result == 1", engine, GapMode::Strict);
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        assert_eq!(ids(&o, GapTreatment::Refused), ["jdk-constructor:java.util.ArrayList.<init>(I)V"]);
        assert!(o.problem.as_deref().unwrap().contains("refused it (--gaps strict): jdk-constructor:java.util.ArrayList.<init>(I)V"), "{}", o.output);
        assert!(o.search.as_ref().unwrap().fallback.is_none(), "JBMC is not asked: {}", o.output);
        assert_eq!(o.output.contains("so JBMC is not asked"), engine == Engine::Auto, "{}", o.output);
        // The path ends at the first gap it reaches, so the mutator after the constructor is never met.
        let o = prove("firstByte", "out.length == 0 || result == \\old(out[0])", engine, GapMode::Strict);
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        assert_eq!(ids(&o, GapTreatment::Refused), ["jdk-constructor:java.util.Random.<init>(J)V"]);
        let o = prove("nullMonitor", "result == 1", engine, GapMode::Strict);
        assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
        assert_eq!(o.counterexample.as_ref().unwrap().outcome, "throws NullPointerException", "{}", o.output);

        let o = prove("capacity", "result == 1", engine, GapMode::Assume);
        assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
        assert_eq!(ids(&o, GapTreatment::Assumed), ["jdk-constructor:java.util.ArrayList.<init>(I)V"]);
        assert!(o.output.contains(" on every input, assuming 1 behaviour the tool's own checker does not implement (--gaps assume) ("), "{}", o.output);
        assert!(o.output.contains("\n  assumed: jdk-constructor:java.util.ArrayList.<init>(I)V"), "{}", o.output);
        assert!(o.output.contains("java.util.ArrayList.<init>(int) constructs the object and does nothing else"), "{}", o.output);
        let o = prove("firstByte", "out.length == 0 || result == \\old(out[0])", engine, GapMode::Assume);
        assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
        assert_eq!(ids(&o, GapTreatment::Assumed), ["jdk-constructor:java.util.Random.<init>(J)V", "jdk-void-method:java.util.Random.nextBytes([B)V"]);
        assert!(o.output.contains("assuming 2 behaviours"), "{}", o.output);
        let o = prove("nullMonitor", "result == 1", engine, GapMode::Assume);
        assert_eq!(o.verdict, Verdict::Violation, "a monitor is no gap: {}", o.output);

        // A JDK method whose value the proof reads has no assume form: refused under assume too, and JBMC, which
        // stubs java.util.Random, is not asked; the constructor before it is assumed.
        let o = prove("roll", "result >= 1", engine, GapMode::Assume);
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        let search = o.search.as_ref().expect("a checker ran");
        assert_eq!(search.engine, "native", "{}", o.output);
        let treated: Vec<(String, Option<GapTreatment>)> = search.gaps.iter().map(|g| (g.id.split('@').next().unwrap().to_string(), g.treatment)).collect();
        assert_eq!(treated, [("jdk-constructor:java.util.Random.<init>(J)V".to_string(), Some(GapTreatment::Assumed)), ("jdk-primitive-method:java.util.Random.nextInt(I)I".to_string(), Some(GapTreatment::Refused))], "{}", o.output);
        let problem = o.problem.as_deref().unwrap();
        assert!(problem.contains("refused it (--gaps assume): jdk-primitive-method:java.util.Random.nextInt(I)I@") && problem.contains("It has no approximation under --gaps assume, since its value could only be made up: only a contract closes it (--gaps advised)"), "{}", o.output);
        assert!(!problem.contains("Random.<init>"), "the assumed constructor is not among the refused: {problem}");
        assert_eq!(o.output.contains("so JBMC is not asked"), engine == Engine::Auto, "{}", o.output);
    }
    // A static JDK method the engine does not model, in either mode (JBMC, which has java.lang.Integer's
    // bytecode, would be asked under auto, and is not run inline).
    for gaps in [GapMode::Strict, GapMode::Assume] {
        let o = prove("bits", "result >= 0 && result <= 32", Engine::Native, gaps);
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        assert_eq!(ids(&o, GapTreatment::Refused), ["jdk-static-method:java.lang.Integer.numberOfLeadingZeros(I)I"]);
        assert!(o.problem.as_deref().unwrap().contains("only a contract closes it"), "{}", o.output);
    }
    // A regression proof meets them the same way: a JDK constructor added to a method that returns 1.
    let (Some(before), Some(after)) = (
        compile_writers("sized-before", "Sized", "package fixtures; public class Sized { public static int capacity(int n) { return 1; } }"),
        compile_writers("sized-after", "Sized", "package fixtures; public class Sized { public static int capacity(int n) { new java.util.ArrayList<Object>(n); return 1; } }"),
    ) else {
        return;
    };
    for (gaps, verdict) in [(GapMode::Strict, Verdict::Unverifiable), (GapMode::Assume, Verdict::Verified)] {
        let mut options = equivalence::Options::new(&before, &after, "fixtures.Sized#capacity");
        options.engine = Engine::Native;
        options.gaps = gaps;
        let work = target_tmp().join(format!("equivalence-sized-{gaps:?}"));
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        let o = equivalence::run(&options).unwrap();
        assert_eq!(o.verdict, verdict, "{}", o.output);
        let search = o.search.as_ref().expect("a checker ran");
        assert_eq!(search.gap_mode, Some(gaps));
        assert_eq!(search.gaps.iter().map(|g| g.id.split('@').next().unwrap()).collect::<Vec<_>>(), ["jdk-constructor:java.util.ArrayList.<init>(I)V"], "{}", o.output);
        if gaps == GapMode::Assume {
            assert!(o.output.contains("assuming 1 behaviour the tool's own checker does not implement"), "{}", o.output);
        }
    }
}

/// Step 3a of llm-dlc/loops/sound-verdicts.md: under `--gaps advised` a proof that reaches a gap with no contract
/// stops before anything is solved, and returns each gap the harness reaches (not only the first a path meets)
/// with what a contract for it must state and a template; a proof that reaches none is strict.
#[test]
fn advised_stops_before_solving_with_each_gap_and_what_its_contract_states() {
    use jvmcontract::advice::Part;
    use jvmcontract::bmc::gaps::GapMode;
    use jvmcontract::Engine;
    let dir = target_tmp().join("gaps-advised-src");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("Gaps.java"), GAPS).unwrap();
    let Some(classes) = compile("gaps-advised", &[dir.join("Gaps.java")]) else { return };
    let prove = |method: &str, assert: &str, engine: Engine| {
        let mut options = property::Options::new(std::slice::from_ref(&classes), &format!("fixtures.Gaps#{method}"));
        options.assert = Some(assert.into());
        options.engine = engine;
        options.gaps = GapMode::Advised;
        let work = target_tmp().join(format!("property-advised-{method}-{engine:?}"));
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        property::run(&options)
    };
    let ids = |a: &jvmcontract::advice::Advice| -> Vec<String> { a.gaps.iter().map(|g| g.id.split('@').next().unwrap().to_string()).collect() };
    for engine in [Engine::Native, Engine::Auto] {
        let o = prove("capacity", "result == 1", engine).unwrap();
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        assert!(o.search.is_none(), "nothing was solved: {}", o.output);
        assert!(!o.work.join("bmc.log").exists(), "the own checker did not run");
        assert!(!o.output.contains("JBMC"), "nor JBMC: {}", o.output);
        assert_eq!(o.findings[0].rule_id, "gaps-need-contracts");
        let a = o.advice.as_ref().expect("advice");
        assert_eq!(a.status, "contracts-needed");
        assert_eq!(a.claim.kind, "property");
        assert_eq!(a.claim.text, "satisfies `result == 1` on every input");
        assert!(a.claim.harness.exists());
        assert_eq!(ids(a), ["jdk-constructor:java.util.ArrayList.<init>(I)V"]);
        let g = &a.gaps[0];
        assert_eq!((g.owner.as_str(), g.name.as_str(), g.descriptor.as_str(), g.returns.as_str()), ("java.util.ArrayList", "<init>", "(I)V", "void"));
        assert_eq!(g.parameters.iter().map(|p| p.ty.as_str()).collect::<Vec<_>>(), ["int"]);
        assert!(g.sites[0].starts_with("fixtures.Gaps.capacity:"), "{:?}", g.sites);
        assert_eq!(g.assumed, "constructs the object and does nothing else: it throws nothing and keeps nothing of its arguments");
        assert!(g.must_state.iter().any(|o| o.part == Part::Exceptions));
        assert_eq!(std::fs::read_to_string(&a.template_file).unwrap(), a.template);
        assert!(a.template.contains(&format!("\n{}\n  # java.util.ArrayList.<init>(int) is a JDK constructor", g.id)), "{}", a.template);
        assert!(o.problem.as_deref().unwrap().starts_with("the proof reaches 1 gap of the tool's own checker with no contract (--gaps advised), so nothing was solved: jdk-constructor:java.util.ArrayList.<init>(I)V@"), "{}", o.output);
        assert!(o.output.contains("\n  gap jdk-constructor:java.util.ArrayList.<init>(I)V@") && o.output.contains("\nkind: gap-contracts\n"), "{}", o.output);
        let stated = o.stated.as_ref().unwrap();
        assert_eq!(stated.gap_mode, Some(GapMode::Advised));
        assert_eq!(stated.checker.engine, "none");
        let json = serde_json::to_value(&o).unwrap();
        assert_eq!(json["advice"]["gaps"][0]["must_state"][0]["part"], "exceptions", "{json}");

        // Every gap the harness reaches, where strict ends the path at the first.
        let o = prove("firstByte", "out.length == 0 || result == \\old(out[0])", engine).unwrap();
        let a = o.advice.as_ref().expect("advice");
        assert_eq!(ids(a), ["jdk-constructor:java.util.Random.<init>(J)V", "jdk-void-method:java.util.Random.nextBytes([B)V"]);
        assert!(a.gaps[1].must_state.iter().any(|o| o.part == Part::Arguments), "nextBytes changes its array: {:?}", a.gaps[1].must_state);
        assert!(o.problem.as_deref().unwrap().contains("reaches 2 gaps"), "{}", o.output);

        // No gap: the run is strict's.
        let o = prove("nullMonitor", "result == 1", engine).unwrap();
        assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
        assert!(o.advice.is_none());
        assert_eq!(o.search.as_ref().unwrap().gap_mode, Some(GapMode::Advised));
    }
    let e = prove("capacity", "result == 1", Engine::Jbmc).unwrap_err();
    assert!(e.to_string().contains("--gaps advised needs --engine native or auto"), "{e}");

    // A regression proof the same way.
    let (Some(before), Some(after)) = (
        compile_writers("advised-sized-before", "Sized", "package fixtures; public class Sized { public static int capacity(int n) { return 1; } }"),
        compile_writers("advised-sized-after", "Sized", "package fixtures; public class Sized { public static int capacity(int n) { new java.util.ArrayList<Object>(n); return 1; } }"),
    ) else {
        return;
    };
    let mut options = equivalence::Options::new(&before, &after, "fixtures.Sized#capacity");
    options.engine = Engine::Native;
    options.gaps = GapMode::Advised;
    let work = target_tmp().join("equivalence-advised-sized");
    let _ = std::fs::remove_dir_all(&work);
    options.work = Some(work);
    let o = equivalence::run(&options).unwrap();
    assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
    assert!(o.search.is_none(), "{}", o.output);
    let a = o.advice.as_ref().expect("advice");
    assert_eq!(a.claim.kind, "regression");
    assert_eq!(a.claim.text, "behaves as before on every input");
    assert_eq!(ids(a), ["jdk-constructor:java.util.ArrayList.<init>(I)V"]);
    assert!(a.gaps[0].sites.iter().all(|s| s.starts_with("fixtures.Sized.capacity:")), "the new version's call, not the previous one's: {:?}", a.gaps[0].sites);
}

const CONTRACTED: &str = r#"
package fixtures;

public class Contracted {
    static class Table {
        static final int[] PRIMES = { 2, 3, 5 };
        static int first() { return 7; }
    }

    public static int capacity(int n) { new java.util.ArrayList<Object>(n); return 1; }
    public static int firstByte(byte[] out) { if (out.length == 0) return 0; new java.util.Random(1).nextBytes(out); return out[0]; }
    public static int filled(byte[] out) { new java.util.Random(1).nextBytes(out); return out.length; }
    public static boolean chained(int n) { StringBuilder b = new StringBuilder(); return b.append(n) == b; }
    public static boolean named(int n) { StringBuilder b = new StringBuilder(); return b.append("n") == b && n == n; }
    public static int initialised(int n) { return Table.first() + n; }
    public static int bits(int n) { return 32 - Integer.numberOfLeadingZeros(n); }
    public static int roll(int sides) { return new java.util.Random(7).nextInt(sides) + 1; }
}
"#;

/// Steps 3b and 3c of llm-dlc/loops/sound-verdicts.md: under `--gaps advised` with `--contracts`, the tool's own
/// checker applies each contract at its call in place of the gap: the exceptions it states are thrown where their
/// conditions hold, an array it modifies takes any values, a reference result is the object the contract names,
/// and an initializer that throws nothing is taken to have run. Each contract is first tested on a real JVM: one
/// the JVM refutes is refused with its counterexamples, and its gap goes back to the agent; one it cannot test is
/// trusted. A verdict says it rests on each contract, at its level. A contract the engine cannot apply is refused
/// with the reason and its gap stays open; an input outside a contract's `assume:` meets the gap.
#[test]
fn a_contract_closes_its_gap_and_the_verdict_rests_on_it() {
    use jvmcontract::bmc::gaps::{GapMode, GapTreatment};
    use jvmcontract::Engine;
    let dir = target_tmp().join("contracts-src");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("Contracted.java"), CONTRACTED).unwrap();
    let Some(classes) = compile("contracts", &[dir.join("Contracted.java")]) else { return };
    let jdk = jvmcontract::bmc::gaps::jdk_release().map(|v| format!("@jdk-{v}")).unwrap_or_default();
    let block = |id: &str, body: &str| format!("\n{id}{}\n{body}  written-by: the test\n", if id.starts_with("jdk-") { jdk.as_str() } else { "" });
    let capacity = "jdk-constructor:java.util.ArrayList.<init>(I)V";
    let throwing = block(capacity, "  call: java.util.ArrayList.<init>(int capacity)\n  throws: IllegalArgumentException when capacity < 0\n  modifies: nothing\n");
    let silent = block(capacity, "  call: java.util.ArrayList.<init>(int capacity)\n  modifies: nothing\n");
    let random = block("jdk-constructor:java.util.Random.<init>(J)V", "  call: java.util.Random.<init>(long seed)\n  modifies: nothing\n");
    let fill = block("jdk-void-method:java.util.Random.nextBytes([B)V", "  call: java.util.Random.nextBytes(byte[] bytes)\n  modifies: this, bytes\n");
    let builder = block("jdk-constructor:java.lang.StringBuilder.<init>()V", "  call: java.lang.StringBuilder.<init>()\n  modifies: nothing\n");
    let append = |result: &str| block("jdk-reference-method:java.lang.StringBuilder.append(I)Ljava/lang/StringBuilder;", &format!("  call: java.lang.StringBuilder.append(int i) -> java.lang.StringBuilder\n  assert: {result}\n  modifies: this\n"));
    let table = block("class-initializer:fixtures.Contracted$Table.<clinit>()V", "  call: fixtures.Contracted$Table.<clinit>()\n  modifies: nothing\n");
    let prove = |name: &str, method: &str, assert: &str, throws: &[&str], blocks: &[&str], engine: Engine| {
        let file = dir.join(format!("{name}.contracts"));
        std::fs::write(&file, format!("kind: gap-contracts\n{}", blocks.concat())).unwrap();
        let mut options = property::Options::new(std::slice::from_ref(&classes), &format!("fixtures.Contracted#{method}"));
        options.assert = Some(assert.into());
        options.throws = throws.iter().map(|t| t.to_string()).collect();
        options.engine = engine;
        options.gaps = GapMode::Advised;
        options.contracts = Some(file);
        let work = target_tmp().join(format!("property-contracts-{name}-{engine:?}"));
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        property::run(&options)
    };
    let contracts = |o: &property::Outcome| -> Vec<String> {
        let search = o.search.as_ref().expect("a checker ran");
        search.gaps.iter().filter(|g| g.treatment == Some(GapTreatment::Contract)).map(|g| g.id.split('@').next().unwrap().to_string()).collect()
    };
    for engine in [Engine::Native, Engine::Auto] {
        // The review's reproducer: with the contract the JVM's behaviour has, the negative capacity is found and
        // the interpreter reproduces it; with one that throws nothing, a `Verified` that rests on it, by name.
        let o = prove("throwing", "capacity", "result == 1", &[], &[&throwing], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
        let c = o.counterexample.as_ref().unwrap();
        assert_eq!(c.outcome, "throws IllegalArgumentException(\"Illegal Capacity: -1\")", "the JVM's own message, in the interpreter: {}", o.output);
        assert_eq!(c.input, "capacity(n=-1)", "{}", o.output);
        assert!(o.replay.as_ref().unwrap().reproduced, "{}", o.output);
        assert!(o.advice.is_none() && o.search.as_ref().unwrap().fallback.is_none(), "{}", o.output);
        let o = prove("throwing-declared", "capacity", "result == 1", &["IllegalArgumentException when n < 0"], &[&throwing], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
        assert!(o.output.contains(", relying on 1 contract for gaps of the tool's own checker, 1 tested (--gaps advised) ("), "{}", o.output);
        assert!(o.output.contains(&format!("\n  contract: {capacity}{jdk} at fixtures.Contracted.capacity:")), "{}", o.output);
        assert!(o.output.contains(": throws java.lang.IllegalArgumentException when capacity < 0; modifies nothing (written by the test; tested on "), "{}", o.output);
        assert!(o.output.contains(" (seed 1), ") && o.output.contains(", none refuting it)"), "{}", o.output);
        assert_eq!(contracts(&o), [capacity]);
        let stated = o.stated.as_ref().unwrap();
        let a = stated.assumptions.iter().find(|a| a.kind == jvmcontract::statement::AssumptionKind::Contract).expect("the contract is an assumption");
        assert_eq!(a.basis, jvmcontract::statement::Basis::Tested);
        assert_eq!(a.id.as_deref(), Some(format!("{capacity}{jdk}").as_str()));
        let json = serde_json::to_value(&o).unwrap();
        let contract = &json["search"]["gaps"][0]["contract"];
        assert_eq!(contract["evidence"], "tested", "{json}");
        assert_eq!(contract["testing"]["seed"], 1, "{json}");
        let testing = &contract["testing"];
        assert!(testing["inputs"].as_u64().unwrap() >= 100, "{json}");
        assert!(testing["thrown"][0].as_u64().unwrap() > 0 && testing["returned"].as_u64().unwrap() > 0, "both sides of the clause are tested: {json}");
        assert!(testing.get("counterexamples").is_none(), "{json}");

        // The acceptance of 3c: "`new ArrayList<>(n)` doesn't throw" is rejected by the JVM at n = -1, with its
        // counterexamples, and the gap goes back to the agent; the corrected contract is tested, above, and gives
        // the review's reproducer its verdict, the violation at the top.
        let o = prove("silent", "capacity", "result == 1", &[], &[&silent], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        assert!(o.search.is_none(), "nothing was solved: {}", o.output);
        let a = o.advice.as_ref().unwrap();
        let refused = a.gaps[0].refused_contract.as_deref().unwrap();
        assert!(refused.starts_with("a JVM refutes it: on capacity=-1 the JVM's call throws java.lang.IllegalArgumentException: Illegal Capacity: -1, where the contract says it returns normally ("), "{refused}");
        assert!(refused.contains(" inputs refute it, on JDK ") && refused.contains(", seed 1) ("), "{refused}");
        assert!(a.gaps[0].counterexamples.len() > 1 && a.gaps[0].counterexamples.iter().all(|c| c.input.starts_with("capacity=-")), "{:?}", a.gaps[0].counterexamples);
        assert!(o.output.contains("is refused, and its gap stays open: a JVM refutes it: on capacity=-1 "), "{}", o.output);
        assert!(o.output.contains("\n      also on capacity=-"), "{}", o.output);
        let json = serde_json::to_value(&o).unwrap();
        assert_eq!(json["advice"]["gaps"][0]["counterexamples"][0]["observed"], "throws java.lang.IllegalArgumentException: Illegal Capacity: -1", "{json}");

        // A contract the JVM cannot test, a parameter being a String it makes no values of, is trusted, and says
        // why; the verdict counts both levels.
        let named = block("jdk-reference-method:java.lang.StringBuilder.append(Ljava/lang/String;)Ljava/lang/StringBuilder;", "  call: java.lang.StringBuilder.append(java.lang.String s) -> java.lang.StringBuilder\n  assert: result == this\n  modifies: this\n");
        let o = prove("named", "named", "result", &[], &[&builder, &named], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
        assert!(o.output.contains(", relying on 2 contracts for gaps of the tool's own checker, 1 tested, 1 trusted (--gaps advised) ("), "{}", o.output);
        assert!(o.output.contains("(written by the test; trusted: no JVM test, since parameter s is a java.lang.String, which the test makes no values of)"), "{}", o.output);
        assert!(o.output.contains("(written by the test; tested on 1 input on JDK "), "a constructor of no arguments has one input: {}", o.output);

        // Outside a contract's `assume:` the gap is open, and refused.
        let narrow = block(capacity, "  call: java.util.ArrayList.<init>(int capacity)\n  assume: capacity >= 0\n  modifies: nothing\n");
        let o = prove("narrow", "capacity", "result == 1", &[], &[&narrow], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        assert!(o.problem.as_deref().unwrap().contains(&format!("refused it (--gaps advised): {capacity}")), "{}", o.output);
        assert!(o.problem.as_deref().unwrap().contains("fixtures.Contracted.capacity:"), "met at the call, not in the contract's method: {}", o.output);

        // An array the call modifies takes any values: what the harness read before the call is gone. The witness
        // is one of the values the contract admits, not necessarily the one Random(1) writes, and the interpreter
        // cannot run Random to tell, so it is no verdict.
        let o = prove("firstByte", "firstByte", "out.length == 0 || result == \\old(out[0])", &[], &[&random, &fill], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        assert!(o.problem.as_deref().unwrap().contains("the witness is one the contracts admit"), "{}", o.output);
        assert_eq!(contracts(&o), ["jdk-constructor:java.util.Random.<init>(J)V", "jdk-void-method:java.util.Random.nextBytes([B)V"], "{}", o.output);
        let o = prove("filled", "filled", "result == out.length", &[], &[&random, &fill], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
        assert!(o.output.contains("relying on 2 contracts for gaps of the tool's own checker, 2 tested"), "{}", o.output);
        // Neither is proved: each call has an object whose state the checker does not keep.
        let json = serde_json::to_value(&o).unwrap();
        for g in json["search"]["gaps"].as_array().unwrap() {
            assert!(g["contract"]["unproved"].as_str().unwrap().starts_with("only a static method's contract is proved against the JDK's bytecode"), "{json}");
        }
        assert!(o.output.contains(", each called on new java.util.Random(), none refuting it)"), "{}", o.output);
        // What the JVM shows of an array: a contract that leaves it out of `modifies:`, or asserts what the call
        // does not leave in it, is refuted.
        let unmodified = block("jdk-void-method:java.util.Random.nextBytes([B)V", "  call: java.util.Random.nextBytes(byte[] bytes)\n  modifies: this\n");
        let o = prove("unmodified", "filled", "result == out.length", &[], &[&random, &unmodified], engine).unwrap();
        let refused = o.advice.as_ref().map(|a| a.gaps[0].refused_contract.clone().unwrap()).unwrap_or_default();
        assert!(refused.contains("the JVM's call changes bytes, where the contract says it leaves bytes as it was, `modifies:` not naming it"), "{}", o.output);
        let zeroes = block("jdk-void-method:java.util.Random.nextBytes([B)V", "  call: java.util.Random.nextBytes(byte[] bytes)\n  assert: (\\forall int i; 0 <= i && i < bytes.length; bytes[i] == 0)\n  modifies: this, bytes\n");
        let o = prove("zeroes", "filled", "result == out.length", &[], &[&random, &zeroes], engine).unwrap();
        let refused = o.advice.as_ref().map(|a| a.gaps[0].refused_contract.clone().unwrap()).unwrap_or_default();
        assert!(refused.contains("the JVM's call returns with it false, where the contract says it returns with `assert: (\\forall int i; 0 <= i && i < bytes.length; bytes[i] == 0)` holding"), "{}", o.output);

        // A reference result is the object the contract names.
        let o = prove("chained", "chained", "result", &[], &[&builder, &append("result == this")], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
        // A contract that says otherwise than the JDK's call: 3b found it only because its witness did not
        // reproduce in the interpreter; the JVM refutes it before any solving.
        let o = prove("chained-fresh", "chained", "result", &[], &[&builder, &append("\\fresh(result)")], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        let refused = o.advice.as_ref().map(|a| a.gaps[0].refused_contract.clone().unwrap()).unwrap_or_default();
        assert!(refused.starts_with("a JVM refutes it: on i=0 the JVM's call returns the object it is called on, where the contract says it returns a new object"), "{}", o.output);

        // An initializer that throws nothing has run.
        let o = prove("table", "initialised", "result == n + 7", &[], &[&table], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
        assert_eq!(contracts(&o), ["class-initializer:fixtures.Contracted$Table.<clinit>()V"]);

        // A contract the engine cannot apply is refused with the reason, and its gap goes back to the agent.
        let todo = block(capacity, "  call: java.util.ArrayList.<init>(int capacity)\n  throws: TODO when TODO\n  modifies: nothing\n");
        let o = prove("todo", "capacity", "result == 1", &[], &[&todo], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        assert!(o.search.is_none(), "nothing was solved: {}", o.output);
        assert!(o.output.contains(&format!("note: the contract for {capacity}{jdk} (")) && o.output.contains("is refused, and its gap stays open: `throws:` still says TODO"), "{}", o.output);
        let a = o.advice.as_ref().unwrap();
        assert!(a.gaps[0].refused_contract.as_deref().unwrap().starts_with("`throws:` still says TODO ("), "{:?}", a.gaps[0]);
        assert!(o.output.contains("\n    its contract is refused: `throws:` still says TODO"), "{}", o.output);
        // One gap closed, one still open: the advice says which.
        let o = prove("half", "firstByte", "out.length == 0 || result == \\old(out[0])", &[], &[&random], engine).unwrap();
        let a = o.advice.as_ref().unwrap();
        assert_eq!(a.closed, [format!("jdk-constructor:java.util.Random.<init>(J)V{jdk}")]);
        assert_eq!(a.gaps.iter().map(|g| g.id.split('@').next().unwrap()).collect::<Vec<_>>(), ["jdk-void-method:java.util.Random.nextBytes([B)V"]);
        assert!(!a.template.contains("Random.<init>"), "the template is of the gaps still open: {}", a.template);

        // A primitive result is any value `assert:` admits, which the JVM test holds the JDK's call to: a static
        // JDK method, and an instance method on a receiver the test builds.
        let random7 = block("jdk-constructor:java.util.Random.<init>(J)V", "  call: java.util.Random.<init>(long seed)\n  modifies: nothing\n");
        let next = |assert: &str| block("jdk-primitive-method:java.util.Random.nextInt(I)I", &format!("  call: java.util.Random.nextInt(int bound) -> int\n  throws: IllegalArgumentException when bound <= 0\n  assert: {assert}\n  modifies: this\n"));
        let nlz = |assert: &str| block("jdk-static-method:java.lang.Integer.numberOfLeadingZeros(I)I", &format!("  call: java.lang.Integer.numberOfLeadingZeros(int i) -> int\n  assert: {assert}\n  modifies: nothing\n"));
        let exact = nlz("0 <= result && result <= 32 && (i == 0) == (result == 32) && (i < 0) == (result == 0)");
        let o = prove("bits", "bits", "result >= 0 && result <= 32", &[], &[&exact], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
        assert_eq!(contracts(&o), ["jdk-static-method:java.lang.Integer.numberOfLeadingZeros(I)I"]);
        // The method is static, of primitives, and in the checker's fragment: its contract is proved against the
        // JDK's own bytecode of java.lang.Integer, and tested on the JVM besides.
        assert!(o.output.contains("relying on 1 contract for gaps of the tool's own checker, 1 proved (--gaps advised)"), "{}", o.output);
        assert!(o.output.contains("proved on every input against the bytecode of java.lang.Integer in JDK ") && o.output.contains("; tested on "), "{}", o.output);
        let stated = o.stated.as_ref().unwrap();
        let a = stated.assumptions.iter().find(|a| a.kind == jvmcontract::statement::AssumptionKind::Contract).expect("the contract is an assumption");
        assert_eq!(a.basis, jvmcontract::statement::Basis::Proved);
        let json = serde_json::to_value(&o).unwrap();
        let contract = &json["search"]["gaps"][0]["contract"];
        assert_eq!(contract["evidence"], "proved", "{json}");
        assert_eq!(contract["proof"]["class"], "java.lang.Integer", "{json}");
        assert!(contract["proof"]["digest"].as_str().unwrap().starts_with("sha256:") && contract["proof"]["paths"].as_u64().unwrap() > 1, "{json}");
        assert_eq!(contract["proof"]["unwind"], 16, "{json}");
        assert!(contract["testing"]["inputs"].as_u64().unwrap() > 100 && contract.get("unproved").is_none(), "{json}");
        // A contract wrong only where neither the boundary values nor the random ones look: the proof finds the
        // input, and the JVM, run on it too, refutes the contract there.
        let o = prove("bits-wrong-far", "bits", "result >= 0 && result <= 32", &[], &[&nlz("0 <= result && result <= 32 && (i != 777777 || result == 0)")], engine).unwrap();
        let refused = o.advice.as_ref().map(|a| a.gaps[0].refused_contract.clone().unwrap()).unwrap_or_default();
        assert!(refused.starts_with("a JVM refutes it: on i=777777 the JVM's call returns 12, where the contract says it returns with "), "{}", o.output);
        assert!(refused.contains("(1 of "), "the proof's witness alone refutes it: {}", o.output);
        // A violation through it, which the interpreter, running the JDK's own bytecode, reproduces.
        let o = prove("bits-violated", "bits", "result < 32", &[], &[&exact], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
        assert_eq!(o.counterexample.as_ref().unwrap().outcome, "32", "{}", o.output);
        assert!(o.replay.as_ref().unwrap().reproduced, "{}", o.output);
        // The JVM refutes a bound the call does not keep, with the value it returned.
        let o = prove("bits-wrong", "bits", "result >= 0 && result <= 32", &[], &[&nlz("0 <= result && result < 32")], engine).unwrap();
        let refused = o.advice.as_ref().map(|a| a.gaps[0].refused_contract.clone().unwrap()).unwrap_or_default();
        assert!(refused.starts_with("a JVM refutes it: on i=0 the JVM's call returns 32, where the contract says it returns with `assert: 0 <= result && result < 32` holding (1 of "), "{}", o.output);

        let o = prove("roll", "roll", "result >= 1 && result <= sides", &["IllegalArgumentException when sides <= 0"], &[&random7, &next("0 <= result && result < bound")], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
        assert!(o.output.contains("relying on 2 contracts for gaps of the tool's own checker, 2 tested"), "{}", o.output);
        // Neither is proved: each call has an object whose state the checker does not keep.
        let json = serde_json::to_value(&o).unwrap();
        for g in json["search"]["gaps"].as_array().unwrap() {
            assert!(g["contract"]["unproved"].as_str().unwrap().starts_with("only a static method's contract is proved against the JDK's bytecode"), "{json}");
        }
        assert!(o.output.contains("throws java.lang.IllegalArgumentException when bound <= 0; then 0 <= result && result < bound; modifies this (written by the test; tested on ") && o.output.contains(", each called on new java.util.Random(), none refuting it)"), "{}", o.output);
        // A witness through the contract is one the contract admits: the interpreter cannot run Random to show
        // the JVM's, so there is no verdict.
        let o = prove("roll-violated", "roll", "result >= 1 && result < sides", &["IllegalArgumentException when sides <= 0"], &[&random7, &next("0 <= result && result < bound")], engine).unwrap();
        assert_eq!(o.verdict, Verdict::Unverifiable, "{}", o.output);
        assert!(o.problem.as_deref().unwrap().contains("goes through the contracts for jdk-constructor:java.util.Random.<init>(J)V") && o.problem.as_deref().unwrap().contains("the interpreter cannot run the method on it to confirm it"), "{}", o.output);
        assert!(!o.replay.as_ref().unwrap().reproduced, "{}", o.output);
        let o = prove("roll-wrong", "roll", "result >= 1 && result <= sides", &["IllegalArgumentException when sides <= 0"], &[&random7, &next("0 < result && result < bound")], engine).unwrap();
        let refused = o.advice.as_ref().map(|a| a.gaps[0].refused_contract.clone().unwrap()).unwrap_or_default();
        assert!(refused.starts_with("a JVM refutes it: on bound=1 the JVM's call returns 0, where the contract says it returns with `assert: 0 < result && result < bound` holding"), "{}", o.output);
    }
    let mut options = property::Options::new(std::slice::from_ref(&classes), "fixtures.Contracted#capacity");
    options.assert = Some("result == 1".into());
    options.engine = Engine::Native;
    options.contracts = Some(dir.join("throwing.contracts"));
    let e = property::run(&options).unwrap_err();
    assert!(e.to_string().contains("--contracts needs --gaps advised"), "{e}");

    // A regression proof the same way: the constructor added throws on a negative capacity, as its contract says.
    let (Some(before), Some(after)) = (
        compile_writers("contracts-sized-before", "Sized", "package fixtures; public class Sized { public static int capacity(int n) { return 1; } }"),
        compile_writers("contracts-sized-after", "Sized", "package fixtures; public class Sized { public static int capacity(int n) { new java.util.ArrayList<Object>(n); return 1; } }"),
    ) else {
        return;
    };
    for (name, verdict) in [("throwing", Verdict::Violation), ("silent", Verdict::Unverifiable)] {
        let mut options = equivalence::Options::new(&before, &after, "fixtures.Sized#capacity");
        options.engine = Engine::Native;
        options.gaps = GapMode::Advised;
        options.contracts = Some(dir.join(format!("{name}.contracts")));
        let work = target_tmp().join(format!("equivalence-contracts-{name}"));
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        let o = equivalence::run(&options).unwrap();
        assert_eq!(o.verdict, verdict, "{}", o.output);
        if verdict == Verdict::Verified {
            assert!(o.output.contains("relying on 1 contract"), "{}", o.output);
        }
    }
}

const IDENTITY: &str = r#"
package fixtures;

public class Identity {
    static class A { int x; }
    static class B extends A { int x; }
    static class Other { static String a() { return "a"; } }
    static class Boom {
        static final int[] TABLE = table();
        static int[] table() { throw new IllegalStateException("no table"); }
        static int value(int n) { return n; }
    }
    static class Base {
        static final int[] TABLE = table();
        static int[] table() { throw new IllegalStateException("no base table"); }
    }
    static class Derived extends Base { static int value(int n) { return n; } }
    static class Quiet {
        static final int[] TABLE = { 1, 2 };
        static int value(int n) { return n; }
    }

    public static int hiding(int n) { B b = new B(); b.x = n; ((A) b).x = 2; return b.x; }
    public static int hidden(int n) { B b = new B(); b.x = n; ((A) b).x = 2; return ((A) b).x; }
    public static boolean sameLiteral(int n) { String s = "a"; return s == Other.a(); }
    public static boolean otherLiteral(int n) { String s = "a"; String t = "b"; return s == t; }
    public static boolean sameClass(int n) { Class<?> c = Identity.class; return c == Identity.class; }
    public static int boom(int n) { return Boom.value(n); }
    public static int inherited(int n) { return Derived.value(n); }
    public static int quiet(int n) { return Quiet.value(n); }
}
"#;

/// Step 1c of llm-dlc/loops/sound-verdicts.md: identity and initialization, against a real JVM. A field a subclass
/// declares again is a second field, and every load of a string or class literal is one object, so the tool's own
/// checker and the interpreter that replays its witnesses agree with the JVM on each claim below; before, both kept
/// one field per name, and the engine made each literal a new object, so a claim the JVM refutes was `Verified`.
/// A class whose initializer the engine does not run is a `class-initializer` gap: refused by name under strict
/// (the JVM throws `ExceptionInInitializerError` from it), named as an assumption under assume, and under
/// `--engine auto` handed to JBMC, which runs initializers.
#[test]
fn identity_and_initialization_agree_with_the_jvm() {
    use jvmcontract::bmc::gaps::{GapMode, GapTreatment};
    use jvmcontract::Engine;
    let dir = target_tmp().join("identity-src");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("Identity.java"), IDENTITY).unwrap();
    let Some(classes) = compile("identity", &[dir.join("Identity.java")]) else { return };
    if has("java") {
        let probe = "public class Probe { public static void main(String[] a) {\n".to_string()
            + "System.out.println(fixtures.Identity.hiding(5));\n"
            + "System.out.println(fixtures.Identity.hidden(5));\n"
            + "System.out.println(fixtures.Identity.sameLiteral(0));\n"
            + "System.out.println(fixtures.Identity.otherLiteral(0));\n"
            + "System.out.println(fixtures.Identity.sameClass(0));\n"
            + "try { System.out.println(fixtures.Identity.boom(3)); } catch (Throwable t) { System.out.println(t.getClass().getName()); }\n"
            + "try { System.out.println(fixtures.Identity.inherited(3)); } catch (Throwable t) { System.out.println(t.getClass().getName()); }\n"
            + "System.out.println(fixtures.Identity.quiet(3)); } }\n";
        std::fs::write(dir.join("Probe.java"), probe).unwrap();
        let status = Command::new("javac").args(["-proc:none", "-cp"]).arg(&classes).arg("-d").arg(&classes).arg(dir.join("Probe.java")).status().expect("javac runs");
        assert!(status.success());
        let run = Command::new("java").arg("-cp").arg(&classes).arg("Probe").output().expect("java runs");
        let lines = String::from_utf8_lossy(&run.stdout).lines().map(str::to_string).collect::<Vec<_>>();
        assert_eq!(lines, ["5", "2", "true", "false", "true", "java.lang.ExceptionInInitializerError", "java.lang.ExceptionInInitializerError", "3"]);
    }
    let prove = |method: &str, assert: &str, engine: Engine, gaps: GapMode| {
        let mut options = property::Options::new(std::slice::from_ref(&classes), &format!("fixtures.Identity#{method}"));
        options.assert = Some(assert.into());
        options.engine = engine;
        options.gaps = gaps;
        let work = target_tmp().join(format!("property-identity-{method}-{}-{engine:?}-{gaps:?}", assert.len()));
        let _ = std::fs::remove_dir_all(&work);
        options.work = Some(work);
        property::run(&options).unwrap()
    };
    // What the JVM says holds is verified, and what it refutes is a violation whose witness the interpreter
    // replays; in either mode, since none of these is a gap.
    for gaps in [GapMode::Strict, GapMode::Assume] {
        for (method, holds, refuted) in [("hiding", "result == n", "result == 2"), ("hidden", "result == 2", "result == n"), ("sameLiteral", "result", "!result"), ("otherLiteral", "!result", "result"), ("sameClass", "result", "!result")] {
            let o = prove(method, holds, Engine::Native, gaps);
            assert_eq!(o.verdict, Verdict::Verified, "{method}: {}", o.output);
            assert!(o.search.as_ref().unwrap().gaps.is_empty(), "{method}: {}", o.output);
            let o = prove(method, refuted, Engine::Native, gaps);
            assert_eq!(o.verdict, Verdict::Violation, "{method}: {}", o.output);
        }
    }
    let ids = |o: &property::Outcome| -> Vec<String> { o.search.as_ref().expect("a checker ran").gaps.iter().map(|g| g.id.clone()).collect() };
    // An initializer the engine does not run: refused by name, the superclass's for a subclass, and refused even
    // where it would have thrown nothing (what strictness costs).
    for (method, id) in [("boom", "class-initializer:fixtures.Identity$Boom.<clinit>()V"), ("inherited", "class-initializer:fixtures.Identity$Base.<clinit>()V"), ("quiet", "class-initializer:fixtures.Identity$Quiet.<clinit>()V")] {
        let o = prove(method, "result == n", Engine::Native, GapMode::Strict);
        assert_eq!(o.verdict, Verdict::Unverifiable, "{method}: {}", o.output);
        assert_eq!(ids(&o), [id], "{method}: {}", o.output);
        assert!(o.problem.as_deref().unwrap().contains(&format!("refused it (--gaps strict): {id}")), "{method}: {}", o.output);
        let o = prove(method, "result == n", Engine::Native, GapMode::Assume);
        assert_eq!(o.verdict, Verdict::Verified, "{method}: {}", o.output);
        assert_eq!(ids(&o), [id], "{method}: {}", o.output);
        assert_eq!(o.search.as_ref().unwrap().gaps[0].treatment, Some(GapTreatment::Assumed));
        assert!(o.output.contains("has run already, and threw nothing"), "{method}: {}", o.output);
    }
    // JBMC runs initializers, so `--engine auto` asks it, and it finds the error the JVM throws.
    if has("jbmc") {
        let o = prove("boom", "result == n", Engine::Auto, GapMode::Strict);
        assert_eq!(o.verdict, Verdict::Violation, "{}", o.output);
        assert_eq!(o.search.as_ref().unwrap().engine, "jbmc", "{}", o.output);
        assert!(o.counterexample.as_ref().unwrap().outcome.contains("ExceptionInInitializerError"), "{}", o.output);
        let o = prove("quiet", "result == n", Engine::Auto, GapMode::Strict);
        assert_eq!(o.verdict, Verdict::Verified, "{}", o.output);
    }
}
