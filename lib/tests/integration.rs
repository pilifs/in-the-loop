//! End-to-end tests over Java fixtures compiled with `javac` at test time. They are skipped (with a note) when no
//! JDK is on the path; the tests that need JBMC or TLC skip without those too.

use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

use jvmcontract::classpath::ClassPath;
use jvmcontract::contract::Contract;
use jvmcontract::verifier::{self, ContractsRun, Verifier};
use jvmcontract::{capabilities, equivalence, property, tla, Verdict};

fn has(program: &str) -> bool {
    Command::new(program).arg("--version").output().map(|o| o.status.success()).unwrap_or(false)
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

#[test]
fn a_reference_parameter_is_refused_by_the_symbolic_verifier() {
    let with_string = PRICING_BEFORE.replace("long priceCents, int seats", "String code, int seats").replace("priceCents < 0 || ", "").replace("Math.multiplyExact(priceCents, seats)", "seats");
    let Some(classes) = compile_pricing("string", &with_string) else { return };
    let outcome = equivalence_run(&classes, &classes, None, "string");
    assert_eq!(outcome.verdict, Verdict::Unverifiable);
    assert!(outcome.output.contains("cannot be verified: parameter code has type java.lang.String"), "{}", outcome.output);
}

fn prove(target: &str, assume: Option<&str>, assert: Option<&str>, name: &str) -> Option<property::Outcome> {
    if !has("jbmc") {
        eprintln!("jbmc not found; skipping");
        return None;
    }
    let classes = fixtures()?;
    let mut options = property::Options::new(&[classes.to_path_buf()], target);
    options.assume = assume.map(str::to_string);
    options.assert = assert.map(str::to_string);
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
    if !spec.exists() || tla::tlc_command(&tla::TlcOptions::new(&spec.join("BoxOffice.tla"))).is_err() {
        eprintln!("no spec or no TLC; skipping");
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
