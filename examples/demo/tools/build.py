#!/usr/bin/env python3
"""Run the formal verification examples in examples/demo/ and render them.

Each example folder holds what a person writes: example.json (the change, its risk, the expected verdict) and
change.patch. This script applies the patch to a temporary copy of the repo, runs the real verifier named by the
example's approach, and writes what it produced next to them:

  result.json          verdict, counterexamples, before/after excerpts, contract diff (examples/demo/schema/result.schema.json)
  result.sarif         the verifier's SARIF report, with repo-relative paths
  verifier-output.txt  the verifier's console output
  statement.java       for symbolic proofs: the generated statement the prover checked
  README.md            the example, rendered for reading

and then examples/README.md (the table of contents) and examples/demo/index.json.
It exits 1 if any verdict differs from the example's expected verdict, so the examples also test the verifiers.

Approaches (the ids are those of examples/approaches.md):
  B8   behavioural contracts: every input of a finite domain, executed      (verify)
  B9   regression verification: old and new bytecode compared symbolically  (equivalence; JBMC)
  B10  capability contracts: what a module's bytecode can reach             (verify)
  B11  property proofs: a stated property of one method, on every input     (prove; JBMC)
  D1   protocol model checking: the system in TLA+, driven by a contract    (spec; TLC)

Four subject applications. Box Office (examples/demo/apps/boxoffice, examples 001 to 012) is a Gradle build verified
by the Java proof of concept in examples/demo/tools/contracts. Quorum (examples/demo/apps/quorum, examples 013 to 022),
Crosscut (examples/demo/apps/crosscut, examples 023 to 033) and Mica (examples/demo/apps/mica, examples 034 onwards) are
plain javac, verified by the Rust tool in lib/ (jvmcontract). The app is chosen by the example's subject file.

Usage: python3 examples/demo/tools/build.py [ID ...]
Needs Java 25 on PATH or JAVA_HOME; JBMC for B9 and B11; TLC (tla2tools.jar in ~/tools, or TLA2TOOLS_JAR) for D1;
cargo (or a built lib/target/release/jvmcontract, or JVMCONTRACT pointing at one) for the javac apps. No Docker.
"""

import atexit
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
EXAMPLES = REPO / "examples/demo"
BUILD_ROOT = "examples/demo/apps/boxoffice"  # the Gradle build the Box Office examples patch
VERIFIER = "examples/demo/tools/contracts"
COPY = [BUILD_ROOT, VERIFIER]
# The javac builds verified by the Rust tool in lib/: the app's root, the main class that runs its tests, and its
# TLA+ model for D1 (defined below).
TOOL_APPS = {
    "quorum": {"root": "examples/demo/apps/quorum", "tests": "net.terminalvalue.quorum.Tests"},
    "crosscut": {"root": "examples/demo/apps/crosscut", "tests": "net.terminalvalue.crosscut.Tests"},
    "mica": {"root": "examples/demo/apps/mica", "tests": "net.terminalvalue.mica.Tests"},
}
IGNORE = shutil.ignore_patterns("build", ".gradle", ".kotlin", "*.class")

VERDICT_LABEL = {
    "violation": "✗ Violation",
    "verified": "✓ Verified",
    "unverifiable": "⚠ Unverifiable",
}

# Per-approach caches, filled on first use and removed at exit.
SCRATCH = Path(tempfile.mkdtemp(prefix="examples-"))
atexit.register(shutil.rmtree, SCRATCH, True)
BEFORE_CLASSES = {}


def main(argv):
    wanted = set(argv)
    folders = sorted(p for p in EXAMPLES.iterdir() if p.is_dir() and re.match(r"^\d{3}-", p.name))
    failures = []
    for folder in folders:
        if wanted and folder.name[:3] not in wanted:
            continue
        example = load_example(folder)
        print(f"{folder.name}: running ({example['approach']['id']})", flush=True)
        result = run(folder, example)
        (folder / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        validate(result, "result.schema.json", folder / "result.json")
        (folder / "README.md").write_text(render_example(folder, example, result))
        status = "as expected" if result["matchesExpected"] else f"EXPECTED {example['expected']['verdict'].upper()}"
        print(f"{folder.name}: {result['verdict']} ({status})")
        if not result["matchesExpected"]:
            failures.append(folder.name)
    render_index(folders)
    if failures:
        print("Verdicts differ from expectations: " + ", ".join(failures))
        return 1
    return 0


def load_example(folder):
    example = json.loads((folder / "example.json").read_text())
    validate(example, "example.schema.json", folder / "example.json")
    if example["id"] != folder.name[:3]:
        sys.exit(f"{folder}: id {example['id']} does not match the folder name")
    if example["approach"]["id"] not in RUNNERS[app_of(example)]:
        sys.exit(f"{folder}: no runner for approach {example['approach']['id']} on {app_of(example)}")
    return example


def app_of(example):
    """Which subject application the example changes: 'boxoffice' or a javac app, by its subject file."""
    file = example["subject"]["file"]
    for app, config in TOOL_APPS.items():
        if file.startswith(config["root"] + "/"):
            return app
    if file.startswith(BUILD_ROOT + "/"):
        return "boxoffice"
    sys.exit(f"{file}: not under {BUILD_ROOT} or " + ", ".join(c["root"] for c in TOOL_APPS.values()))


def validate(document, schema_name, path):
    try:
        import jsonschema
    except ImportError:
        return  # optional: the schemas are still the documentation of the format
    schema = json.loads((EXAMPLES / "schema" / schema_name).read_text())
    try:
        jsonschema.validate(document, schema)
    except jsonschema.ValidationError as e:
        sys.exit(f"{path}: {e.message}")


# Running


def run(folder, example):
    """Applies the patch to a copy of the repo, runs the module's tests and the approach's verifier, and collects
    everything into the result dictionary. The approach-specific part is the runner; the rest is shared."""
    patch = (folder / example["change"]["patch"]).read_text()
    before, after = excerpts(patch, example["subject"]["file"])
    app = app_of(example)
    module = module_of(example["subject"]["file"]) if app == "boxoffice" else app
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for part in COPY if app == "boxoffice" else [TOOL_APPS[app]["root"]]:
            shutil.copytree(REPO / part, tmp / part, ignore=IGNORE)
        subprocess.run(["git", "apply", "-p1", "-"], input=patch, text=True, cwd=tmp, check=True)

        if app == "boxoffice":
            build = tmp / BUILD_ROOT
            tests = gradle(build, f":{module}:test", check=False, allow_empty=True)
            existing_tests = {"task": f":{module}:test", "passed": tests.returncode == 0,
                              "failures": failures(build / module / "build/test-results/test")}
        else:
            existing_tests = tool_tests(app, tmp)

        result = {
            "verdict": None,
            "verdictLabel": None,
            "matchesExpected": None,
            "existingTests": existing_tests,
            "before": before,
            "after": after,
            "casesTotal": None,
            "domain": None,
            "counterexamples": [],
            "purityViolations": [],
            "trustedCalls": [],
            "contractDiff": None,
            "proof": None,
            "problem": None,
            "statement": None,
            "trace": None,
            "statesExplored": None,
            "invariant": None,
            "property": None,
            "stateMachine": None,
            "sarif": "result.sarif",
            "output": "verifier-output.txt",
        }
        RUNNERS[app][example["approach"]["id"]](folder, example, tmp, module, result)
    result["matchesExpected"] = result["verdict"] == example["expected"]["verdict"]
    return result


def update_contracts(build, module, result):
    """For an intended change: regenerates the module's contracts and records the diff a reviewer would approve."""
    contract_dir = build / module / "src/contract"
    old = {f.name: f.read_text() for f in contract_dir.glob("*.contract")}
    gradle(build, f":{module}:updateContracts")
    result["contractDiff"] = "".join(
        "".join(difflib.unified_diff(
            old.get(f.name, "").splitlines(True), f.read_text().splitlines(True),
            f"a/{BUILD_ROOT}/{module}/src/contract/{f.name}",
            f"b/{BUILD_ROOT}/{module}/src/contract/{f.name}"))
        for f in sorted(contract_dir.glob("*.contract")))


def run_contracts(folder, example, tmp, module, result):
    """B8 and B10: the module's behavioural and capability contracts, verified by the Gradle build of the patched
    copy. The two share a verifier and a Gradle task; they differ in what the output lists."""
    build = tmp / BUILD_ROOT
    if example["change"]["behaviourChangeIntended"]:
        update_contracts(build, module, result)

    proc = gradle(build, f":{module}:verifyContracts", check=False)
    output = proc.stdout.replace(str(tmp) + "/", "")
    write_evidence(folder, output, build / module / "build/reports/contracts/contracts.sarif")

    verdict = "verified" if proc.returncode == 0 else (
        "unverifiable" if "cannot be verified" in output else "violation")
    cases = cases_total(output)
    changes = capability_changes(output)
    result.update({
        "verdict": verdict,
        "casesTotal": cases,
        "counterexamples": counterexamples(output) + changes,
        "purityViolations": purity_violations(output),
        "trustedCalls": trusted_calls(output),
    })
    if example["approach"]["id"] == "B10":
        m = re.search(r"\((\d+) classes, (\d+) methods, (\d+) capability uses, (\d+) libraries\)", output)
        result["domain"] = f"{m.group(1)} classes, {m.group(2)} methods" if m else None
        result["verdictLabel"] = {
            "violation": f"{VERDICT_LABEL[verdict]}: {len(changes)} capability change{'s' if len(changes) != 1 else ''}",
            "verified": f"{VERDICT_LABEL[verdict]}: capabilities unchanged",
            "unverifiable": VERDICT_LABEL[verdict],
        }[verdict]
        return
    result["verdictLabel"] = {
        "violation": f"{VERDICT_LABEL[verdict]}: {len(result['counterexamples'])} of {cases} cases changed",
        "verified": f"{VERDICT_LABEL[verdict]}: all {cases} cases match",
        "unverifiable": VERDICT_LABEL[verdict],
    }[verdict]


def run_equivalence(folder, example, tmp, module, result):
    """B9: the old and new bytecode of one method, proved equivalent (outside the intended inputs) by JBMC."""
    build = tmp / BUILD_ROOT
    gradle(build, f":{module}:compileJava")
    after = build / module / "build/classes/java/main"
    work = tmp / "equivalence"
    report = tmp / "report"
    command = [java(), "-cp", verifier_jar(), "net.terminalvalue.contracts.Main", "equivalence",
               "--before", str(before_classes(module)), "--after", str(after),
               "--target", example["subject"]["symbol"],
               "--work", str(work), "--report", str(report), "--base", str(tmp),
               "--sources", str(build / module / "src/main/java")]
    intended = example["change"].get("intendedInputs")
    if intended:
        command += ["--unchanged-unless", intended]
    proc = subprocess.run(command, text=True, capture_output=True)
    output = (proc.stdout + proc.stderr).replace(str(tmp) + "/", "")
    write_evidence(folder, output, report / "equivalence.sarif")
    statement = work / "harness/EquivalenceHarness.java"
    if statement.exists():
        shutil.copy(statement, folder / "statement.java")
        result["statement"] = "statement.java"

    verdict = "verified" if proc.returncode == 0 else (
        "unverifiable" if "cannot be verified" in output else "violation")
    m = re.search(r"domain (.+?)\)$", output, re.M) or re.search(r"over (.+?) in [\d.]+ s", output)
    proof = re.search(r"^  \((.*)\)$", output, re.M) or re.search(r"\((JBMC .*)\)$", output, re.M)
    result.update({
        "verdict": verdict,
        "domain": m.group(1) if m else None,
        "counterexamples": counterexamples(output),
        "proof": proof.group(1) if proof else None,
        "problem": problem(output),
    })
    result["verdictLabel"] = {
        "violation": f"{VERDICT_LABEL[verdict]}: counterexample found",
        "verified": f"{VERDICT_LABEL[verdict]}: equivalent on every input" + (" outside the declared change" if intended else ""),
        "unverifiable": VERDICT_LABEL[verdict],
    }[verdict]


SPEC = "spec"  # the TLA+ model, inside BUILD_ROOT
CONTRACT_FILE = "ticketing-domain/src/contract/OrderLifecycle.decide.contract"

# The Java operation each TLA+ action models, for the trace.
ACTIONS = {
    "Initial predicate": "the initial state",
    "Hold": "`HoldService.hold`: a customer holds seats",
    "PlaceOrder": "`OrderService.place`: an order is placed and a charge is queued",
    "Cancel": "`OrderService.cancel`",
    "RelayCommand": "`OutboxRelay` (ticketing) publishes to `payments.commands`",
    "HandleCommand": "`PaymentCommandHandler.handle`: the payment service charges or refunds",
    "RelayEvent": "`OutboxRelay` (payments) publishes to `payments.events`",
    "HandleEvent": "`PaymentEventHandler.handle`: ticketing applies the payment outcome",
    "Sweep": "`HoldService.releaseExpiredHolds`",
    "Tick": "the clock advances",
}

INVARIANTS = {
    "NoDoubleSale": "two confirmed orders never share a seat",
    "ConfirmedOrdersOwnTheirSeats": "a confirmed order owns every seat it was placed for",
    "SoldSeatsHaveConfirmedOrders": "a sold seat belongs to a confirmed order",
    "NoMoneyStranded": "captured money is held for a confirmed order, is being refunded, or its capture event is still on its way",
    "NothingDeadLettered": "no record is dead-lettered",
    "AgreementAtQuiescence": "when nothing is in flight, both services agree on every order",
    "TypeOK": "every variable has a value of its type",
}


def run_tlc(folder, example, tmp, module, result):
    """D1: the TLA+ model of the services, checked by TLC. The state machine in the model is generated from the
    behavioural contract of the (patched) code, so a change to OrderLifecycle reaches the model through its proof."""
    build = tmp / BUILD_ROOT
    if example["change"]["behaviourChangeIntended"]:
        update_contracts(build, "ticketing-domain", result)
    spec = build / SPEC
    subprocess.run([sys.executable, str(EXAMPLES / "tools/tla/contract_to_tla.py"),
                    str(build / CONTRACT_FILE), str(spec / "OrderLifecycleContract.tla")], check=True, capture_output=True)
    library = EXAMPLES / "tools/tla/standard-modules"
    try:
        # One worker, so that the trace TLC reports is the same on every run.
        proc = subprocess.run(tlc(library) + ["-workers", "1", "-deadlock", "-cleanup", "BoxOffice.tla"],
                              cwd=spec, text=True, capture_output=True, timeout=1800)
        raw = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        raw = "Error: TLC did not finish within 30 minutes"
    output = "\n".join(l for l in raw.replace(str(tmp) + "/", "").replace(str(REPO) + "/", "").splitlines() if not l.startswith("Progress("))
    (folder / "verifier-output.txt").write_text(output + "\n")

    violated = re.search(r"^Error: Invariant (\w+) is violated", output, re.M)
    states = re.search(r"(\d+) states generated, (\d+) distinct states found", output)
    depth = re.search(r"depth of the complete state graph search is (\d+)", output)
    seconds = re.search(r"Finished in (\d+)s", output)
    if "No error has been found" in output:
        verdict = "verified"
    elif violated:
        verdict = "violation"
    else:
        verdict = "unverifiable"
    trace = parse_trace(output) if violated else None
    model = ", ".join(re.findall(r"^\s+(\w+ = .+)$", (spec / "BoxOffice.cfg").read_text(), re.M))
    sarif_line = result["after"]["startLine"]
    findings = []
    if verdict != "verified":
        message = (f"Invariant {violated.group(1)} of {SPEC}/BoxOffice.tla is violated after {len(trace)} steps"
                   if violated else "TLC produced no verdict: " + output.strip().splitlines()[-1])
        findings.append({"ruleId": "invariant-violated" if violated else "unverifiable", "level": "error",
                         "message": {"text": message},
                         "locations": [{"physicalLocation": {"artifactLocation": {"uri": example["subject"]["file"]},
                                                             "region": {"startLine": sarif_line}}}]})
    sarif = {"version": "2.1.0", "$schema": "https://json.schemastore.org/sarif-2.1.0.json", "runs": [{
        "tool": {"driver": {"name": "tlc", "rules": [
            {"id": "invariant-violated", "shortDescription": {"text": "TLC found a behaviour of the model that violates an invariant."}},
            {"id": "unverifiable", "shortDescription": {"text": "TLC could not check the model."}}]}},
        "results": findings}]}
    (folder / "result.sarif").write_text(json.dumps(sarif, indent=2, ensure_ascii=False) + "\n")

    result.update({
        "verdict": verdict,
        "trace": trace,
        "statesExplored": int(states.group(2)) if states else None,
        "invariant": violated.group(1) if violated else None,
        "domain": model,
        "proof": (f"TLC {tlc_version(output)} explored {int(states.group(2)):,} distinct states"
                  f"{' to depth ' + depth.group(1) if depth else ''}"
                  f"{' in ' + seconds.group(1) + ' s' if seconds else ''}, for the model {model}") if states else None,
        "problem": None if verdict != "unverifiable" else output.strip().splitlines()[-1],
    })
    result["verdictLabel"] = {
        "violation": f"{VERDICT_LABEL[verdict]}: {violated.group(1) if violated else ''}, {len(trace or [])}-step trace",
        "verified": f"{VERDICT_LABEL[verdict]}: all invariants hold in {int(states.group(2)):,} states" if states else VERDICT_LABEL[verdict],
        "unverifiable": VERDICT_LABEL[verdict],
    }[verdict]


def tlc(library):
    """The TLC command line. TLA-Library makes it parse the committed standard modules, not temporary copies."""
    jar = os.environ.get("TLA2TOOLS_JAR") or str(Path.home() / "tools/tla2tools.jar")
    if Path(jar).exists():
        return [java(), "-XX:+UseParallelGC", f"-DTLA-Library={library}", "-cp", jar, "tlc2.TLC"]
    if shutil.which("tlc"):
        return ["tlc"]
    sys.exit("TLC not found: install tla2tools.jar in ~/tools or set TLA2TOOLS_JAR")


def tlc_version(output):
    m = re.search(r"TLC2 Version (\S+)", output)
    return m.group(1) if m else ""


def parse_trace(output):
    """TLC's counterexample as a list of steps, each with the action and the variables it changed."""
    body = output.split("The behavior up to this point is:", 1)[1]
    steps = []
    previous = {}
    parts = re.split(r"^State (\d+): <([^>]*)>\n", body, flags=re.M)
    for i in range(1, len(parts) - 2, 3):
        number, header, text = parts[i], parts[i + 1], parts[i + 2]
        action = header.split(" line ")[0].strip()
        values = {}
        for assignment in re.split(r"^/\\ ", text.strip().split("\n\n")[0], flags=re.M):
            if "=" not in assignment:
                continue
            name, value = assignment.split(" = ", 1)
            values[name.strip()] = re.sub(r"\s+", " ", value).strip()
        changed = {k: v for k, v in values.items() if previous.get(k) != v}
        steps.append({"step": int(number), "action": action, "changes": changed})
        previous = values
    return steps


# The javac apps (Quorum, Crosscut, Mica), verified by the Rust tool in lib/.


def jvmcontract():
    """The jvmcontract executable: $JVMCONTRACT, or the release build of lib/, built with cargo if missing."""
    if "jvmcontract" in BEFORE_CLASSES:
        return BEFORE_CLASSES["jvmcontract"]
    exe = Path(os.environ["JVMCONTRACT"]) if os.environ.get("JVMCONTRACT") else REPO / "lib/target/release/jvmcontract"
    if not os.environ.get("JVMCONTRACT"):
        cargo = shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo")
        if Path(cargo).exists():
            proc = subprocess.run([cargo, "build", "--release", "--manifest-path", str(REPO / "lib/Cargo.toml")],
                                  text=True, capture_output=True)
            if proc.returncode != 0:
                sys.exit(f"cargo build failed:\n{proc.stderr}")
    if not exe.exists():
        sys.exit(f"jvmcontract not found at {exe}: build lib/ with cargo, or set JVMCONTRACT")
    BEFORE_CLASSES["jvmcontract"] = str(exe)
    return str(exe)


def javac(out, sources, classpath=None):
    out.mkdir(parents=True, exist_ok=True)
    command = [str(Path(java()).parent / "javac") if os.environ.get("JAVA_HOME") else "javac",
               "-parameters", "-g", "-proc:none", "-d", str(out)]
    if classpath:
        command += ["-cp", str(classpath)]
    proc = subprocess.run(command + [str(s) for s in sources], text=True, capture_output=True)
    if proc.returncode != 0:
        sys.exit(f"javac failed:\n{proc.stderr}")


def tool_compile(app, root):
    """Compiles the app's module under root (a copy of the repo) into its build dir: main and test classes."""
    build = root / TOOL_APPS[app]["root"]
    main, test = build / "build/main", build / "build/test"
    javac(main, sorted((build / "src/main/java").rglob("*.java")))
    javac(test, sorted((build / "src/test/java").rglob("*.java")), classpath=main)
    return main, test


def tool_tests(app, root):
    """Runs the module's tests (plain static methods, no framework) and reports which failed."""
    main, test = tool_compile(app, root)
    runner = TOOL_APPS[app]["tests"]
    proc = subprocess.run([java(), "-ea", "-cp", f"{main}{os.pathsep}{test}", runner], text=True, capture_output=True)
    failing = sorted(re.findall(r"^FAIL (\S+):", proc.stdout, re.M))
    if proc.returncode != 0 and not failing:
        sys.exit(f"the tests did not run:\n{proc.stdout}\n{proc.stderr}")
    return {"task": f"java -ea {runner}", "passed": proc.returncode == 0, "failures": failing}


def tool_before_classes(app):
    """The module's classes compiled from the unpatched repo, built once per run."""
    if app not in BEFORE_CLASSES:
        root = SCRATCH / f"before-{app}"
        part = TOOL_APPS[app]["root"]
        shutil.copytree(REPO / part, root / part, ignore=IGNORE)
        BEFORE_CLASSES[app] = tool_compile(app, root)[0]
    return BEFORE_CLASSES[app]


def tool(app, root, *args, anchored=True):
    """Runs jvmcontract on the patched copy, with findings anchored relative to the copy's root."""
    build = root / TOOL_APPS[app]["root"]
    anchor = ["--sources", str(build / "src/main/java"), "--base", str(root)] if anchored else []
    proc = subprocess.run([jvmcontract(), *args, *anchor], text=True, capture_output=True, cwd=build)
    output = (proc.stdout + proc.stderr).replace(str(root) + "/", "")
    if proc.returncode == 2:
        sys.exit(f"jvmcontract failed:\n{output}")
    return proc, output


def tool_update_contracts(app, root, result):
    """For an intended change: regenerates the module's contracts and records the diff a reviewer would approve."""
    part = TOOL_APPS[app]["root"]
    build = root / part
    contract_dir = build / "src/contract"
    old = {f.name: f.read_text() for f in contract_dir.glob("*.contract")}
    tool(app, root, "update", "--contracts", "src/contract", "--classes", str(build / "build/main"), "--module", app)
    result["contractDiff"] = "".join(
        "".join(difflib.unified_diff(
            old.get(f.name, "").splitlines(True), f.read_text().splitlines(True),
            f"a/{part}/src/contract/{f.name}", f"b/{part}/src/contract/{f.name}"))
        for f in sorted(contract_dir.glob("*.contract")))


def tool_state_machine(app, root, symbol):
    """The state machine the patched code implements, as Mermaid, when the symbol's contract is one."""
    build = root / TOOL_APPS[app]["root"]
    proc = subprocess.run([jvmcontract(), "derive", symbol, "--classes", str(build / "build/main")],
                          text=True, capture_output=True)
    if proc.returncode != 0:
        return None
    contract = build / "build/derived.contract"
    contract.write_text(proc.stdout)
    proc = subprocess.run([jvmcontract(), "statemachine", str(contract), "--format", "mermaid"],
                          text=True, capture_output=True)
    return proc.stdout if proc.returncode == 0 else None


def run_tool_contracts(folder, example, root, module, result):
    """B8 and B10 on a javac app: `jvmcontract verify` over the module's contracts directory."""
    app = app_of(example)
    build = root / TOOL_APPS[app]["root"]
    if example["change"]["behaviourChangeIntended"]:
        tool_update_contracts(app, root, result)
    proc, output = tool(app, root, "verify", "--contracts", "src/contract", "--classes", str(build / "build/main"),
                        "--module", module, "--report", str(build / "build/reports"))
    write_evidence(folder, output, build / "build/reports/contracts.sarif")
    verdict = "verified" if proc.returncode == 0 else ("unverifiable" if "cannot be verified" in output else "violation")
    cases = cases_total(output, example["subject"]["symbol"])
    changes = capability_changes(output)
    result.update({
        "verdict": verdict,
        "casesTotal": cases,
        "counterexamples": counterexamples(output) + changes,
        "purityViolations": purity_violations(output),
        "trustedCalls": trusted_calls(output),
    })
    if example["approach"]["id"] == "B10":
        m = re.search(r"\((\d+) classes, (\d+) methods, (\d+) capability uses, (\d+) libraries\)", output)
        result["domain"] = f"{m.group(1)} classes, {m.group(2)} methods" if m else None
        result["verdictLabel"] = {
            "violation": f"{VERDICT_LABEL[verdict]}: {len(changes)} capability change{'s' if len(changes) != 1 else ''}",
            "verified": f"{VERDICT_LABEL[verdict]}: capabilities unchanged",
            "unverifiable": VERDICT_LABEL[verdict],
        }[verdict]
        return
    result["stateMachine"] = tool_state_machine(app, root, example["subject"]["symbol"])
    result["verdictLabel"] = {
        "violation": f"{VERDICT_LABEL[verdict]}: {len(result['counterexamples'])} of {cases} cases changed",
        "verified": f"{VERDICT_LABEL[verdict]}: all {cases} cases match",
        "unverifiable": VERDICT_LABEL[verdict],
    }[verdict]


def finish_symbolic(folder, example, result, output, work, harness, verdict_labels):
    """What B9 and B11 share: the statement, the domain, the proof line and the verdict label."""
    statement = work / "harness" / harness
    if statement.exists():
        shutil.copy(statement, folder / "statement.java")
        result["statement"] = "statement.java"
    m = re.search(r"domain (.+?)\)$", output, re.M) or re.search(r"over (.+?) in [\d.]+ s", output)
    proof = re.search(r"^  \((.*)\)$", output, re.M) or re.search(r"\((JBMC .*)\)$", output, re.M)
    result.update({"domain": m.group(1) if m else None, "proof": proof.group(1) if proof else None, "problem": problem(output)})
    result["verdictLabel"] = verdict_labels[result["verdict"]]


def run_tool_equivalence(folder, example, root, module, result):
    """B9 on a javac app: `jvmcontract equivalence` between the unpatched and the patched classes."""
    app = app_of(example)
    build = root / TOOL_APPS[app]["root"]
    work = build / "build/equivalence"
    command = ["equivalence", "--before", str(tool_before_classes(app)), "--after", str(build / "build/main"),
               "--target", example["subject"]["symbol"], "--work", str(work), "--report", str(build / "build/reports")]
    intended = example["change"].get("intendedInputs")
    if intended:
        command += ["--unchanged-unless", intended]
    proc, output = tool(app, root, *command)
    write_evidence(folder, output, build / "build/reports/equivalence.sarif")
    result["verdict"] = "verified" if proc.returncode == 0 else ("unverifiable" if "cannot be verified" in output else "violation")
    result["counterexamples"] = counterexamples(output)
    finish_symbolic(folder, example, result, output, work, "EquivalenceHarness.java", {
        "violation": f"{VERDICT_LABEL['violation']}: counterexample found",
        "verified": f"{VERDICT_LABEL['verified']}: equivalent on every input" + (" outside the declared change" if intended else ""),
        "unverifiable": VERDICT_LABEL["unverifiable"],
    })


def run_tool_property(folder, example, root, module, result):
    """B11 on a javac app: `jvmcontract prove` of the symbol's property in the module's properties file."""
    app = app_of(example)
    build = root / TOOL_APPS[app]["root"]
    work = build / "build/property"
    proc, output = tool(app, root, "prove", example["subject"]["symbol"], "--properties", "src/contract/properties.contract",
                        "--classes", str(build / "build/main"), "--work", str(work), "--report", str(build / "build/reports"))
    write_evidence(folder, output, build / "build/reports/property.sarif")
    result["verdict"] = "verified" if proc.returncode == 0 else ("unverifiable" if "cannot be verified" in output else "violation")
    m = (re.search(r"(?:satisfies `(.*)`|returns) on every input(?: where (.*?))?((?:, and throws .*?)*) \(JBMC", output)
         or re.search(r"violated: (?:`(.*)`|returns)(?: where (.*?))?((?:, and throws .*?)*):$", output, re.M))
    throws = [t for t in m.group(3).split(", and throws ") if t] if m else []
    result["property"] = {"assert": m.group(1), "assume": m.group(2), **({"throws": throws} if throws else {})} if m else None
    witness = re.search(r"^  (\S.*)\n    outcome: (.*)$(?:\n    expected: (.*)$)?", output, re.M)
    if witness:
        result["counterexamples"] = [{"input": witness.group(1), "contract": m.group(1) if m else None, "actual": witness.group(2),
                                      **({"expected": witness.group(3)} if witness.group(3) else {})}]
    finish_symbolic(folder, example, result, output, work, "PropertyHarness.java", {
        "violation": f"{VERDICT_LABEL['violation']}: counterexample found",
        "verified": f"{VERDICT_LABEL['verified']}: property holds on every input",
        "unverifiable": VERDICT_LABEL["unverifiable"],
    })


TWOPC = {
    "spec": "spec/TwoPhaseCommit.tla",
    "cfg": "spec/TwoPhaseCommit.cfg",
    "label": "three participants",
    "configurations": [
        {"cfg": "spec/TwoPhaseCommitInductive.cfg", "label": "the inductive step",
         "what": "that the invariant `Inductive` is inductive: TLC starts from every state the invariant admits, reachable or not, "
                 "rather than from the initial state, takes one step, and checks the invariant again, conjunct by conjunct. "
                 "No counterexample is a proof of atomicity by induction, for any run of the protocol however long; a "
                 "counterexample is one step from a state that need not be reachable",
         "initial": "a state the invariant `Inductive` admits, which need not be reachable",
         "startsAnywhere": True},
    ],
    "contract": "src/contract/Coordinator.decide.contract",
    "operator": "spec/CoordinatorContract.tla",
    "symbol": "net.terminalvalue.quorum.twopc.Coordinator#decide",
    "parts": "the participants, the coordinator and the votes in flight",
    "initial": "every participant working, no vote counted, no decision",
    "actions": {
        "Initial predicate": "the initial state",
        "Vote": "`Participant.prepare`: a participant votes yes (and holds its locks) or no (and aborts)",
        "ParticipantTimeout": "`Participant.timeout`: a participant that has not voted gives up on its own",
        "Learn": "`Participant.learn`: a participant applies the coordinator's decision",
        "ReceiveVote": "`Coordinator.onVote`: the coordinator counts a vote and decides on the tally",
        "CoordinatorTimeout": "`Coordinator.onTimeout`: the collection timer fires with votes missing",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "Atomicity": "once the coordinator or any participant has committed, no participant has aborted",
        "CommitFollowsTheCoordinator": "a participant commits only on the coordinator's decision, and only after voting yes",
        "VotesInFlightAreUncounted": "a vote on its way to the coordinator has not been counted, and a participant votes once",
        "DecisionMatchesThePhase": "what the coordinator broadcast is what its phase says",
        "ParticipantsAgreeWithTheirVotes": "a working participant has not voted, a prepared one voted yes, a no voter has aborted, "
                                           "and a yes voter that aborted did so on the coordinator's say-so",
        "CommitNeedsEveryVote": "the coordinator commits only once every vote is counted and yes",
        "EveryParticipantDecides": "every participant eventually commits or aborts, under the fairness the model assumes: "
                                   "participants vote or give up, the coordinator counts every vote and fires its timer while votes are missing, "
                                   "and participants apply a decision once made",
        "ImplementsTransactionCommit": "every behaviour of the protocol, seen through the participants' states, is one transaction commit "
                                       "(Lamport and Gray's TCommit) allows: a participant commits only once every participant is prepared or "
                                       "committed, and aborts only while none has committed",
    },
    "machine": "The coordinator's decision rule inside the model is generated from the behavioural contract of "
               "the patched code, so the model checks the decisions the coordinator really makes.",
}

RAFT = {
    "spec": "spec/RaftElection.tla",
    "cfg": "spec/RaftElection.cfg",
    "label": "three servers",
    # The same model under two more configurations, run after the first; the README reports all three.
    "configurations": [
        {"cfg": "spec/RaftElectionInductive.cfg", "label": "the inductive step",
         "what": "that the invariant `Inductive` is inductive: TLC starts from every state the invariant admits, reachable or not, "
                 "rather than from the initial state, takes one step, and checks the invariant again, conjunct by conjunct. "
                 "No counterexample is a proof of election safety by induction, for any run of the cluster however long; a "
                 "counterexample is one step from a state that need not be reachable",
         "initial": "a state the invariant `Inductive` admits, which need not be reachable",
         "startsAnywhere": True},
        {"cfg": "spec/RaftElectionFour.cfg", "label": "four servers",
         "what": "every run with four servers, a cluster in which a candidate can hold a vote besides its own and still be short "
                 "of a majority, which three servers never show; under a symmetry set, so that of the states that differ only "
                 "by the servers' names TLC explores one"},
        {"cfg": "spec/RaftElectionLive.cfg", "label": "fairness",
         "what": "the two liveness properties, under the fairness conditions `Fairness`: a server whose timer nothing resets "
                 "times out, a candidate asks for the votes it lacks, a leader sends its heartbeats. A counterexample is a run "
                 "that goes on forever without satisfying a property: a prefix, then a state or a cycle the system never leaves"},
    ],
    "contract": "src/contract/RoleMachine.decide.contract",
    "operator": "spec/RoleMachineContract.tla",
    "symbol": "net.terminalvalue.quorum.raft.RoleMachine#decide",
    "parts": "the servers, their terms and votes, and the RPCs between them",
    "initial": "every server a follower in term 0, no vote cast, no vote held",
    "actions": {
        "Initial predicate": "the initial state",
        "Timeout": "`Server.onElectionTimeout`: a server's election timer fires, and the server acts on the role machine's decision",
        "Canvass": "`Server.requestVote`: a candidate asks one server for its vote and gets the answer; the request and the reply "
                   "each go through the role machine, then the vote rule on the voter and the tally on the candidate",
        "Heartbeat": "`Server.appendEntries`: a leader sends one server a heartbeat and gets the answer; the server adopts a newer "
                     "term or yields to the leader of its own, and a stale leader is rejected and steps down",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "ElectionSafety": "at most one leader per term",
        "KernelNeverThrows": "no timeout or RPC any reachable state allows makes the role machine throw: the IllegalStateException "
                             "the Java reserves for an input it holds impossible never fires",
        "LeaderHasAMajority": "a leader holds the votes of a majority of the servers, its own among them",
        "TermsNeverDecrease": "a term never goes backwards on any server, in any step",
        "LeadersNeverCampaign": "a leader never becomes a candidate: it leaves office as the follower of a newer term, or by "
                                "stepping down, never by starting an election against itself; a property of steps, which no "
                                "invariant can state",
        # The conjuncts of the inductive invariant, which the inductive step checks one by one.
        "VotesAreBound": "a vote in a tally was cast in the tally's term: the voter is still in that term and voted for the "
                         "tally's owner, or has since moved to a newer term",
        "TalliesOfATermAreDisjoint": "no server's vote is in two tallies of one term",
        "CampaignersVoteForThemselves": "a candidate or leader voted for itself in its term, and holds its own vote",
        "TalliesHoldTheirOwnersVote": "a tally is empty, or holds its owner's vote and its owner voted for itself",
        "TermZeroIsQuiet": "nothing happens in term 0: a timer that fires starts term 1",
        "Inductive": "the conjunction of the invariants above, closed under every step of the system",
        # The liveness properties, checked under fairness.
        "ALeaderIsElected": "a run that stays within the term budget elects a leader: with no leader every server's timer "
                            "keeps firing, and each firing starts a term, so a run in which the terms stop and no leader "
                            "comes is a cluster that has stopped trying",
        "StaleLeadersStepDown": "a leader whose term the cluster has left steps down: its heartbeat to a server with a newer "
                                "term, or that server's request for a vote, tells it",
    },
    "machine": "The servers' role machine inside the model is generated from the behavioural contract of the patched "
               "code, so the model checks the role transitions the servers really make.",
}

IDEMPOTENCY = {
    "spec": "spec/IdempotentReceiver.tla",
    "cfg": "spec/IdempotentReceiver.cfg",
    "contract": "src/contract/IdempotentReceiver.decide.contract",
    "operator": "spec/IdempotentReceiverContract.tla",
    "symbol": "net.terminalvalue.crosscut.idempotency.IdempotentReceiver#decide",
    "parts": "the client's attempts, the receiver, and the attempts in flight and executing",
    "initial": "no record for the key, nothing sent, nothing executing, no response",
    "actions": {
        "Initial predicate": "the initial state",
        "Send": "`IdempotentClient.send`: the client sends the request, or retries it without waiting for an answer",
        "Receive": "`IdempotencyFilter.doFilter`: the receiver looks the key up, decides, and applies the decision in one transaction",
        "Finish": "`IdempotencyFilter.onCompleted`: an execution produced a result, which the receiver stores and returns",
        "Fail": "`IdempotencyFilter.onFailure`: an execution died without a result",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "OneExecutionAtATime": "no two attempts under one key execute at the same time",
        "AtMostOnce": "once an execution has produced a result, no attempt is executing and none ever will",
        "ReplayedResponsesExist": "a client is never answered with a stored response that does not exist",
    },
    "machine": "The receiver's decision rule inside the model is generated from the behavioural contract of "
               "the patched code, so the model checks the decisions the receiver really makes.",
}

CLASSINIT = {
    "spec": "spec/ClassInit.tla",
    "cfg": "spec/ClassInit.cfg",
    "contract": "src/contract/ClassInitialization.decide.contract",
    "operator": "spec/ClassInitContract.tla",
    "symbol": "net.terminalvalue.mica.init.ClassInitialization#decide",
    "parts": "the threads, the class's initialization state and its recorded initializer",
    "initial": "the class uninitialized, no initializer recorded, every thread idle",
    "deadlock": True,
    "actions": {
        "Initial predicate": "the initial state",
        "Request": "`Runtime.initialize`: a thread needs the class, takes the initialization lock and acts on the decision",
        "Recurse": "`Runtime.initialize` from inside `<clinit>`: the initializer touches its own class",
        "Complete": "`Runtime.initialized`: `<clinit>` returned; the waiters are woken and the thread uses the class",
        "Fail": "`Runtime.initializationFailed`: `<clinit>` threw; the waiters are woken and the thread gets the error",
        "Terminating": "every thread is done with the class",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "UsedOnlyWhenInitialized": "a thread uses the class only once it is initialized",
        "InitializedAtMostOnce": "the initializer runs at most once",
        "OneInitializer": "only the recorded initializer runs the initializer",
        "Deadlock": "a state in which no thread can move",
    },
    "machine": "The runtime's decision rule inside the model is generated from the behavioural contract of "
               "the patched code, so the model checks the decisions the runtime really makes.",
}

# The TLA+ models of each javac app, each built around the state machine of one symbol.
TOOL_MODELS = {"quorum": [TWOPC, RAFT], "crosscut": [IDEMPOTENCY], "mica": [CLASSINIT]}


def model_of(example):
    """The model a D1 example is checked against: the one of its app built around the example's symbol."""
    app = app_of(example)
    if app == "boxoffice":
        return MODELS["boxoffice"]
    for model in TOOL_MODELS[app]:
        if model["symbol"] == example["subject"]["symbol"]:
            return model
    sys.exit(f"{example['id']}: no TLA+ model of {app} is built around {example['subject']['symbol']}")


def tlc_run(build, model_files, cfg, root):
    """One run of TLC on a model under a configuration, through the tool: its parsed JSON, plus the configuration's
    bounds (`domain`) and whether it lists temporal properties."""
    deadlock = ["--deadlock"] if model_files.get("deadlock") else []
    config = [] if cfg == model_files["cfg"] else ["--config", cfg]
    proc = subprocess.run([jvmcontract(), "tlc", model_files["spec"], "--json", *deadlock, *config, "--library", str(EXAMPLES / "tools/tla/standard-modules")],
                          text=True, capture_output=True, cwd=build)
    if proc.returncode == 2:
        sys.exit(f"jvmcontract tlc failed:\n{proc.stderr}")
    run = json.loads(proc.stdout)
    run["output"] = run["output"].replace(str(root) + "/", "").replace(str(REPO) + "/", "")
    text = (build / cfg).read_text()
    run["domain"] = ", ".join(re.findall(r"^\s+(\w+ = .+)$", text, re.M))
    run["properties"] = bool(re.search(r"^PROPERTIES|^PROPERTY", text, re.M))
    run["deadlockChecked"] = bool(deadlock)
    # How a temporal counterexample goes on after its last step: TLC's counterexample for a liveness property is
    # infinite, a prefix and then either stuttering or a loop back into the prefix.
    run["forever"] = None
    if run["verdict"] == "violation" and run.get("kind") == "temporal":
        run["forever"] = (f"returns to step {run['lasso']} and repeats steps {run['lasso']} to {len(run['trace'])} forever"
                          if run.get("lasso") else "stays in that state forever")
    return run


def tlc_label(run):
    """The one-line verdict of a TLC run, as the README's tables show it."""
    verdict = run["verdict"]
    states = run.get("distinct_states")
    if verdict == "violation":
        if len(run["trace"]) == 1:
            return f"{VERDICT_LABEL[verdict]}: {run.get('invariant') or ''}, violated by a starting state"
        return (f"{VERDICT_LABEL[verdict]}: {'deadlock' if run.get('deadlock') else run.get('invariant') or ''}, "
                f"{len(run['trace'])}-step trace{' then forever' if run.get('kind') == 'temporal' else ''}")
    if verdict == "verified" and states is not None:
        return (f"{VERDICT_LABEL[verdict]}: all invariants{' and properties' if run['properties'] else ''} hold in {states:,} states"
                f"{', no deadlock' if run['deadlockChecked'] else ''}")
    return VERDICT_LABEL[verdict]


def tlc_proof(run):
    return (f"{run['version']} explored {run['distinct_states']:,} distinct states"
            f"{' to depth ' + str(run['depth']) if run.get('depth') is not None else ''}"
            f"{' in ' + str(run['seconds']) + ' s' if run.get('seconds') is not None else ''}, for the model {run['domain']}") if run.get("distinct_states") is not None else None


def tlc_configurations(model_files):
    """The configurations a model is checked under: the one of its `.cfg`, then any it lists under `configurations`."""
    primary = {"cfg": model_files["cfg"], "label": model_files.get("label", "the model"), "initial": model_files["initial"],
               "what": "every run from the initial state, every interleaving within the configuration's bounds"}
    return [primary] + [{**c, "initial": c.get("initial", model_files["initial"])} for c in model_files.get("configurations", [])]


def run_tool_tlc(folder, example, root, module, result):
    """D1 on a javac app: the operator regenerated from the (patched) contract, then TLC through the tool, once per
    configuration of the model. The headline, which decides the verdict, is the first configuration that finds a
    violation (or that TLC cannot check), else the first."""
    app = app_of(example)
    build = root / TOOL_APPS[app]["root"]
    model_files = model_of(example)
    if example["change"]["behaviourChangeIntended"]:
        tool_update_contracts(app, root, result)
    tool(app, root, "tla", model_files["contract"], model_files["operator"], anchored=False)
    configurations = tlc_configurations(model_files)
    runs = [(c, tlc_run(build, model_files, c["cfg"], root)) for c in configurations]
    several = len(runs) > 1
    headline = next(((c, r) for c, r in runs if r["verdict"] == "violation"), None) \
        or next(((c, r) for c, r in runs if r["verdict"] == "unverifiable"), None) or runs[0]
    configuration, tlc_result = headline
    if several:
        output = "".join(f"== {c['label']}: {c['cfg']} ==\n{r['output'].rstrip(chr(10))}\n\n" for c, r in runs)
    else:
        output = tlc_result["output"]
    (folder / "verifier-output.txt").write_text(output.rstrip("\n") + "\n")
    verdict = tlc_result["verdict"]
    kind = tlc_result.get("kind")
    trace = [{"step": s["step"], "action": s["action"], "changes": s["changes"]} for s in tlc_result["trace"]] if verdict == "violation" else None
    findings = []
    for c, r in runs:
        if r["verdict"] == "verified":
            continue
        where = f"{model_files['spec']} ({c['label']})" if several else model_files["spec"]
        steps = len(r["trace"])
        if r["verdict"] == "violation" and r.get("deadlock"):
            message = f"{where} deadlocks after {steps} steps: no action is enabled"
        elif r["verdict"] == "violation" and r.get("kind") == "temporal":
            message = f"Temporal property {r['invariant']} of {where} is violated: after {steps} steps the system {r['forever']}"
        elif r["verdict"] == "violation" and r.get("kind") == "action":
            message = f"Action property {r['invariant']} of {where} is violated after {steps} steps"
        elif r["verdict"] == "violation" and steps == 1:
            message = f"Invariant {r['invariant']} of {where} is violated by a starting state"
        elif r["verdict"] == "violation":
            message = f"Invariant {r['invariant']} of {where} is violated after {steps} steps"
        else:
            message = f"TLC produced no verdict for {where}: " + (r.get("problem") or "unknown")
        findings.append({"ruleId": "invariant-violated" if r["verdict"] == "violation" else "unverifiable", "level": "error",
                         "message": {"text": message},
                         "locations": [{"physicalLocation": {"artifactLocation": {"uri": example["subject"]["file"]},
                                                             "region": {"startLine": result["after"]["startLine"]}}}]})
    sarif = {"version": "2.1.0", "$schema": "https://json.schemastore.org/sarif-2.1.0.json", "runs": [{
        "tool": {"driver": {"name": "jvmcontract tlc", "rules": [
            {"id": "invariant-violated", "shortDescription": {"text": "TLC found a behaviour of the model that violates an invariant or a temporal property, or ends in a deadlock."}},
            {"id": "unverifiable", "shortDescription": {"text": "TLC could not check the model."}}]}},
        "results": findings}]}
    (folder / "result.sarif").write_text(json.dumps(sarif, indent=2, ensure_ascii=False) + "\n")
    states = tlc_result.get("distinct_states")
    result.update({
        "verdict": verdict,
        "trace": trace,
        "statesExplored": states,
        "invariant": tlc_result.get("invariant"),
        "violationKind": kind,
        "forever": tlc_result["forever"],
        "domain": tlc_result["domain"],
        "stateMachine": tool_state_machine(app, root, model_files["symbol"]),
        "proof": "; ".join(f"{c['label']}: {tlc_proof(r)}" for c, r in runs if tlc_proof(r)) if several else tlc_proof(tlc_result),
        "problem": tlc_result.get("problem") if verdict == "unverifiable" else None,
    })
    if several:
        result["configurations"] = [{
            "label": c["label"], "cfg": c["cfg"], "verdict": r["verdict"], "summary": tlc_label(r), "domain": r["domain"],
            "invariant": r.get("invariant"), "violationKind": r.get("kind"), "statesExplored": r.get("distinct_states"),
            "trace": [{"step": s["step"], "action": s["action"], "changes": s["changes"]} for s in r["trace"]] if r["verdict"] == "violation" else None,
            "forever": r["forever"],
        } for c, r in runs]
    label = tlc_label(tlc_result)
    if several and verdict == "violation" and configuration is not configurations[0]:
        label += f" ({configuration['label']})"
    elif several and verdict == "verified":
        label += f", and under {len(runs) - 1} more configuration{'s' if len(runs) > 2 else ''}"
    result["verdictLabel"] = label


TOOL_RUNNERS = {"B8": run_tool_contracts, "B9": run_tool_equivalence, "B10": run_tool_contracts,
                "B11": run_tool_property, "D1": run_tool_tlc}
RUNNERS = {
    "boxoffice": {"B8": run_contracts, "B9": run_equivalence, "B10": run_contracts, "D1": run_tlc},
    **{app: TOOL_RUNNERS for app in TOOL_APPS},
}


def before_classes(module):
    """The module's classes compiled from the unpatched repo, built once per run."""
    if module not in BEFORE_CLASSES:
        tmp = SCRATCH / f"before-{module}"
        for part in COPY:
            shutil.copytree(REPO / part, tmp / part, ignore=IGNORE)
        gradle(tmp / BUILD_ROOT, f":{module}:compileJava")
        BEFORE_CLASSES[module] = tmp / BUILD_ROOT / module / "build/classes/java/main"
    return BEFORE_CLASSES[module]


def verifier_jar():
    """The verifier, built from examples/demo/tools/contracts (also an included build of the Box Office Gradle project)."""
    jar = REPO / VERIFIER / "build/libs/contract-verifier-0.1.0.jar"
    if "verifier" not in BEFORE_CLASSES:
        gradle(REPO / BUILD_ROOT, "jar", "-p", str(REPO / VERIFIER))
        BEFORE_CLASSES["verifier"] = jar
    return str(jar)


def java():
    home = os.environ.get("JAVA_HOME")
    return str(Path(home) / "bin/java") if home else "java"


def gradle(build, task, *extra, check=True, allow_empty=False):
    proc = subprocess.run(["./gradlew", "-q", *extra, task], cwd=build, text=True, capture_output=True)
    if check and proc.returncode != 0:
        sys.exit(f"{task} failed:\n{proc.stdout}\n{proc.stderr}")
    if proc.returncode != 0 and not proc.stdout.strip() and not allow_empty:
        sys.exit(f"{task} failed before the verifier ran:\n{proc.stderr}")
    return proc


def write_evidence(folder, output, sarif_path):
    """Writes the verifier's console output and its SARIF report, with the report's paths made repo-relative."""
    (folder / "verifier-output.txt").write_text(output)
    sarif = json.loads(sarif_path.read_text()) if sarif_path.exists() else {
        "version": "2.1.0", "runs": [{"tool": {"driver": {"name": "unknown"}}, "results": []}]}
    for run_ in sarif["runs"]:
        for res in run_["results"]:
            for loc in res.get("locations", []):
                art = loc["physicalLocation"]["artifactLocation"]
                if not art["uri"].startswith("examples/"):
                    art["uri"] = f"{BUILD_ROOT}/{art['uri']}"  # the Java tool anchors to the Gradle module
    (folder / "result.sarif").write_text(json.dumps(sarif, indent=2, ensure_ascii=False) + "\n")


def failures(results_dir):
    """Failing tests in a JUnit XML results directory, as Class.method."""
    import xml.etree.ElementTree as ET
    found = set()
    for xml in results_dir.glob("*.xml"):
        for case in ET.parse(xml).getroot().iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                found.add(f"{case.get('classname').rsplit('.', 1)[-1]}.{case.get('name').removesuffix('()')}")
    return sorted(found)


def module_of(file):
    rest = file.removeprefix(BUILD_ROOT + "/")
    return rest.split("/")[0]


# Parsing the verifiers' output


def cases_total(output, symbol=None):
    """The number of cases in the symbol's contract, from the output line that names it (a module with several
    contracts prints one line each), or the first count printed."""
    lines = [l for l in output.splitlines() if symbol is None or symbol in l] or output.splitlines()
    for line in lines:
        m = re.search(r" of (\d+) cases", line) or re.search(r"\((\d+) cases,", line)
        if m:
            return int(m.group(1))
    return None


def trusted_calls(output):
    m = re.search(r"trusting (.*)\)$", output, re.M)
    return [c.strip() for c in m.group(1).split(",")] if m else []


def purity_violations(output):
    m = re.search(r"not provably pure:\n((?:  .*\n)+)", output)
    return [line.strip() for line in m.group(1).splitlines()] if m else []


def problem(output):
    m = re.search(r"cannot be verified: (.*)", output, re.S)
    return m.group(1).strip() if m else None


def capability_changes(output):
    """Added and removed capability uses (B10), as counterexample rows: the capability is the input."""
    found = []
    for m in re.finditer(r"^  (added|removed) (\w+): (.*)$", output, re.M):
        kind, capability, use = m.groups()
        found.append({"input": capability, "contract": None if kind == "added" else use,
                      "actual": use if kind == "added" else None})
    return found


def counterexamples(output):
    """Changed cases, from either verifier: `contract:/actual:` pairs (B8) or `before:/after:` pairs (B9)."""
    found = []
    pattern = re.compile(
        r"^  (\S.*)\n(?:    (?:contract|before): +(.*)\n    (?:actual|after): +(.*)|    added:    (.*)|    removed: .*\(was (.*)\))$",
        re.M)
    for m in pattern.finditer(output):
        if m.group(2) is not None:
            found.append({"input": m.group(1), "contract": m.group(2), "actual": m.group(3)})
        elif m.group(4) is not None:
            found.append({"input": m.group(1), "contract": None, "actual": m.group(4)})
        else:
            found.append({"input": m.group(1), "contract": m.group(5), "actual": None})
    return found


def excerpts(patch, subject_file):
    """The before and after sides of the patch's hunks in the subject file, with their context lines."""
    file = None
    sides = {"before": [], "after": []}
    starts = {}
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            file = line[len("+++ b/"):]
        elif file != subject_file:
            continue
        elif line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)", line)
            starts.setdefault("before", int(m.group(1)))
            starts.setdefault("after", int(m.group(2)))
            if sides["before"]:
                sides["before"].append("    // ...")
                sides["after"].append("    // ...")
        elif line.startswith("-") and not line.startswith("---"):
            sides["before"].append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            sides["after"].append(line[1:])
        elif line.startswith(" "):
            sides["before"].append(line[1:])
            sides["after"].append(line[1:])
    if not starts:
        sys.exit(f"the patch does not change the subject file {subject_file}")
    return tuple(
        {"file": subject_file, "startLine": starts[side], "code": dedent(sides[side])} for side in ("before", "after"))


def dedent(lines):
    indent = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
    return "\n".join(l[indent:] for l in lines) + "\n"


# Rendering


def render_example(folder, ex, res):
    file_name = Path(ex["subject"]["file"]).name
    source_link = f"../../../{ex['subject']['file']}"
    symbol = ex["subject"]["symbol"].rsplit(".", 1)[-1]
    change = ex["change"]
    lines = [
        "<!-- Generated by examples/demo/tools/build.py from example.json and the verifier's output. Edit example.json. -->",
        f"# {ex['id']} · {ex['title']}",
        "",
        "[← All examples](../README.md)",
        "",
        "| Verdict | Categories | Severity if shipped | Change | Verified unit | Approach |",
        "|---|---|---|---|---|---|",
        f"| **{res['verdictLabel']}** | {', '.join(ex['categories'])} | {ex['severity']} "
        f"| {change['kind']}, behaviour change {'intended' if change['behaviourChangeIntended'] else 'not intended'} "
        f"| [`{symbol}`]({source_link}) "
        f"| [{ex['approach']['id']}: {ex['approach']['name']}](../../../{ex['approach']['tool']}/README.md) |",
        "",
        f"> {ex['summary']}",
        "",
        "## The change",
        "",
        change["description"],
        "",
    ]
    if change.get("intendedInputs"):
        lines += [
            f"The developer declares which inputs the change is meant to affect: `{change['intendedInputs']}`. "
            "The verifier proves that every other input behaves as before, or shows one that does not.",
            "",
        ]
    lines += [
        f"**Before** ([`{file_name}`]({source_link}), line {res['before']['startLine']}):",
        "",
        "```java",
        res["before"]["code"].rstrip("\n"),
        "```",
        "",
        "**After:**",
        "",
        "```java",
        res["after"]["code"].rstrip("\n"),
        "```",
        "",
        "<details><summary>Patch</summary>",
        "",
        "```diff",
        (folder / change["patch"]).read_text().rstrip("\n"),
        "```",
        "",
        "</details>",
        "",
        "## What the verifier found",
        "",
    ]
    lines += FINDINGS[ex["approach"]["id"]](ex, res)
    if res.get("stateMachine"):
        lines += [
            "",
            "The state machine the patched code implements, drawn from its derived contract (`jvmcontract statemachine`); "
            "a state with no way in or no way out is marked:",
            "",
            "```mermaid",
            res["stateMachine"].rstrip("\n"),
            "```",
        ]
    lines += [
        "",
        "## Would the existing tests have caught it?",
        "",
        tests_text(res),
        "",
        "## Why it matters",
        "",
        ex["risk"],
        "",
        "## Why the verdict is right",
        "",
        ex["explanation"],
        "",
        "## What to do",
        "",
        ex["resolution"],
        "",
        "## Evidence",
        "",
    ]
    if res["trustedCalls"]:
        lines += [
            "The proof trusted these JDK APIs to be pure: " + ", ".join(f"`{c}`" for c in res["trustedCalls"]) + ".",
            "",
        ]
    if res.get("proof"):
        lines += [f"How the verdict was reached: {res['proof']}.", ""]
    lines += details("Verifier output", "text", (folder / res["output"]).read_text())
    if res.get("statement"):
        lines += details("The statement the prover checked (generated harness)", "java",
                         (folder / res["statement"]).read_text())
    lines += details("SARIF report (as uploaded to GitHub code scanning or SonarQube)", "json",
                     (folder / res["sarif"]).read_text())
    if ex.get("provenance"):
        lines += [f"**Provenance:** {ex['provenance']}", ""]
    for ref in ex.get("references", []):
        lines += [f"- [{ref['title']}]({ref['url']})"]
    lines += [
        "## Reproduce",
        "",
        "```bash",
        f"python3 examples/demo/tools/build.py {ex['id']}",
        "```",
        "",
        "This applies `change.patch` to a temporary copy of the repo, runs the verifier on it, and rewrites this page.",
        "",
    ]
    return "\n".join(lines)


def findings_contracts(ex, res):
    if res["verdict"] == "violation":
        out = [
            f"The behaviour changed for {len(res['counterexamples'])} of the {res['casesTotal']} possible inputs. "
            "Each row is a concrete input that shows the difference:",
            "",
            "| Input | The contract says | The code now does |",
            "|---|---|---|",
        ]
        for c in res["counterexamples"]:
            out.append(f"| {code(c['input'])} | {code(c['contract']) if c['contract'] else '*(new input)*'} "
                       f"| {code(c['actual']) if c['actual'] else '*(input removed)*'} |")
        return out
    if res["verdict"] == "unverifiable":
        return ["The verifier refused to produce a verdict, because the method is no longer provably pure:", ""] + [
            f"- {code(v)}" for v in res["purityViolations"]]
    out = [f"All {res['casesTotal']} possible inputs give the same outcome as the contract."]
    if res["contractDiff"]:
        out += [
            "",
            "Because the change was intended, the developer regenerated the contract. "
            "This diff is what the reviewer approves:",
            "",
            "```diff",
            res["contractDiff"].rstrip("\n"),
            "```",
        ]
    else:
        out += ["", "The contract file is unchanged, so the pull request contains code changes only."]
    return out


def findings_equivalence(ex, res):
    intended = ex["change"].get("intendedInputs")
    domain = res.get("domain") or "all inputs"
    if res["verdict"] == "violation":
        out = [
            "The two versions disagree. The prover found this input"
            + (" outside the declared change" if intended else "")
            + ", and the generator replayed it on the JVM against both versions:",
            "",
            "| Input | Before | After |",
            "|---|---|---|",
        ]
        for c in res["counterexamples"]:
            out.append(f"| {code(c['input'])} | {code(c['contract'])} | {code(c['actual'])} |")
        out += ["", f"One disagreeing input is enough to fail the build. The domain is `{domain}`; the search tries "
                    "small values first so that the witness is readable, and would have covered all of it."]
        return out
    if res["verdict"] == "unverifiable":
        return ["The verifier refused to produce a verdict:", "", f"- {code(res['problem'] or 'unknown')}"]
    return [
        f"For every input{' where `' + intended + '` is false' if intended else ''}, the new code returns what the "
        "old code returned, or throws what it threw.",
        "",
        f"This is a proof over the whole domain ({domain}), not a sample. JBMC turned the statement into a "
        "satisfiability problem over the bytecode of both versions and showed that it has no solution: no input "
        "exists on which they differ.",
    ]


def findings_capabilities(ex, res):
    if res["verdict"] == "violation":
        out = [
            f"The module's bytecode now reaches {len(res['counterexamples'])} capabilit"
            f"{'y' if len(res['counterexamples']) == 1 else 'ies'} differently from its contract:",
            "",
            "| Capability | The contract lists | The bytecode now has |",
            "|---|---|---|",
        ]
        for c in res["counterexamples"]:
            out.append(f"| {code(c['input'])} | {code(c['contract']) if c['contract'] else '*(nothing)*'} "
                       f"| {code(c['actual']) if c['actual'] else '*(removed)*'} |")
        out += ["", "Every call from the module's compiled code to a JDK entry point of a capability is listed, "
                    "with the method that makes it, so the finding points at the exact call site."]
        return out
    if res["verdict"] == "unverifiable":
        return ["The verifier refused to produce a verdict:", "", f"- {code(res['problem'] or 'unknown')}"]
    out = [f"The capability contract is unchanged: the module ({res['domain']}) reaches exactly the JDK capabilities "
           "and libraries it did before."]
    if res["contractDiff"]:
        out += ["", "Because the change was intended, the developer regenerated the contracts. This diff is what the "
                    "reviewer approves:", "", "```diff", res["contractDiff"].rstrip("\n"), "```"]
    return out


def findings_property(ex, res):
    prop = res.get("property") or {}
    assume = prop.get("assume")
    throws = prop.get("throws") or []
    domain = res.get("domain") or "all inputs"
    where = f" on every input where `{assume}` holds" if assume else " on every input"
    clauses = "".join(f", and throws `{t.split(' when ', 1)[0]}` exactly when `{t.split(' when ', 1)[1]}`" for t in throws)
    holds = f"`{prop['assert']}` holds" if prop.get("assert") else "the method returns"
    if res["verdict"] == "violation":
        with_expected = any(c.get("expected") for c in res["counterexamples"])
        out = [
            (f"The property does not hold: that {holds}{where}{clauses}." if throws
             else f"The property `{prop.get('assert')}` does not hold{where}.")
            + " The prover found this input, and the tool replayed it on the method to show what it does:",
            "",
            "| Input | The method's outcome |" + (" What the property requires |" if with_expected else ""),
            "|---|---|" + ("---|" if with_expected else ""),
        ]
        for c in res["counterexamples"]:
            out.append(f"| {code(c['input'])} | {code(c['actual'])} |" + (f" {c.get('expected') or 'the assertion'} |" if with_expected else ""))
        out += ["", f"One input is enough to fail the build. The domain is `{domain}`; the search tries small values "
                    "first so that the witness is readable, and would have covered all of it."]
        return out
    if res["verdict"] == "unverifiable":
        return ["The verifier refused to produce a verdict:", "", f"- {code(res['problem'] or 'unknown')}"]
    return [
        (f"The method returns without throwing and `{prop.get('assert')}` holds{where}{clauses}." if prop.get("assert")
         else f"The method returns without throwing{where}{clauses}."),
        "",
        f"This is a proof over the whole domain ({domain}), not a sample. JBMC turned the statement into a "
        "satisfiability problem over the bytecode and showed that it has no solution: no input violates the property.",
    ]


MODELS = {
    "boxoffice": {
        "parts": "the two customers, the two services, Kafka and the clock",
        "initial": "every seat available, no holds, orders or payments, every queue empty, the clock at 0",
        "actions": ACTIONS,
        "invariants": INVARIANTS,
        "machine": "The order state machine inside the model is generated from the behavioural contract of the "
                   "patched code, so the model checks the decisions the services really make.",
    },
}


def tlc_trace_lines(model, trace, initial, starts_anywhere=False):
    """A counterexample as a numbered list: each step one action of one part of the system."""
    out = []
    for step in trace:
        what = model["actions"].get(step["action"], step["action"])
        changes = ", ".join(f"`{k} = {v}`" for k, v in step["changes"].items()) or "*(no change)*"
        if step["step"] == 1 and not starts_anywhere:
            out.append(f"{step['step']}. **Initial state**: {initial}.")
        elif step["step"] == 1:
            out.append(f"{step['step']}. **Starting state**, {initial}: {changes}")
        else:
            out.append(f"{step['step']}. **{step['action']}**, {what}. {changes}")
    return out


def findings_tlc(ex, res):
    model = model_of(ex)
    configurations = {c["label"]: c for c in tlc_configurations(model)}
    runs = res.get("configurations") or []
    several = len(runs) > 1
    headline = next((r for r in runs if r["verdict"] == res["verdict"] and r["invariant"] == res.get("invariant")), None) if several else None
    configuration = configurations[headline["label"]] if headline else configurations[next(iter(configurations))]
    out = []
    if several:
        out += [f"The model is checked under {len(runs)} configurations, and the verdict is the first that fails:", "",
                "| Configuration | What it checks | Model | Result |", "|---|---|---|---|"]
        for run in runs:
            out.append(f"| {run['label']} (`{run['cfg']}`) | {configurations[run['label']]['what']} | {run['domain']} | {run['summary']} |")
        out.append("")
    under = f" under {configuration['label']}" if several else ""
    if res["verdict"] == "violation":
        inv = res["invariant"]
        kind = res.get("violationKind")
        steps = len(res["trace"])
        if inv == "Deadlock":
            found = (f"TLC found a run of the system{under}, {steps} steps long, after which no action of any part is "
                     f"enabled: a **deadlock**, {model['invariants'].get(inv, 'every part waits for another')}.")
        elif kind == "temporal":
            found = (f"TLC found a run of the system{under} that violates the temporal property **{inv}** ({model['invariants'].get(inv, inv)}): "
                     f"after the {steps} steps below, the system {res['forever']}, and the property never comes true. "
                     "The run respects every fairness condition the model assumes; the parts that could act, do.")
        elif kind == "action":
            found = (f"TLC found a run of the system{under}, {steps} steps long, whose last step violates the action property "
                     f"**{inv}** ({model['invariants'].get(inv, inv)}).")
        elif steps == 1:
            found = (f"TLC found a state{under} that violates the invariant **{inv}** ({model['invariants'].get(inv, inv)}) "
                     "before any step is taken: the invariant the check starts from does not imply it. The state:")
        else:
            found = (f"TLC found a run of the system{under}, {steps} steps long, that violates the invariant "
                     f"**{inv}** ({model['invariants'].get(inv, inv)}).")
        out += [found + (" Each step is one action of one part of the system:" if steps > 1 else ""), ""]
        out += tlc_trace_lines(model, res["trace"], configuration["initial"], configuration.get("startsAnywhere", False))
        out += ["", f"The model is small ({res['domain']}), which is what keeps the trace readable. TLC explored every "
                    f"interleaving of {model['parts']} within those bounds."]
        for run in runs:
            if run["verdict"] != "violation" or run is headline:
                continue
            c = configurations[run["label"]]
            inv = run["invariant"]
            what = {"temporal": "temporal property", "action": "action property"}.get(run["violationKind"], "invariant")
            if inv == res["invariant"] and run["trace"] == res["trace"] and run["forever"] == res["forever"]:
                out += ["", f"Under {run['label']} TLC found the same run, and reported it the same way."]
                continue
            out += ["", f"<details><summary>The counterexample under {run['label']}: {what} <b>{inv}</b>, "
                        f"{'a starting state' if len(run['trace']) == 1 else str(len(run['trace'])) + ' steps'}</summary>", "",
                    f"{what.capitalize()} **{inv}**: {model['invariants'].get(inv, inv)}."
                    + (f" After the last step the system {run['forever']}." if run["forever"] else ""), ""]
            out += tlc_trace_lines(model, run["trace"], c["initial"], c.get("startsAnywhere", False))
            out += ["", "</details>"]
        return out
    if res["verdict"] == "unverifiable":
        return out + ["TLC produced no verdict:", "", f"- {code(res['problem'] or 'unknown')}"]
    checked = "Every invariant holds in every reachable state of the model"
    if "then forever" in res["verdictLabel"] or " and properties " in res["verdictLabel"]:
        checked = ("Every invariant holds in every reachable state of the model, and every temporal property holds of every "
                   "behaviour, the infinite ones included")
    out += [
        f"{checked}{under}: {res['statesExplored']:,} distinct states, "
        f"which is every interleaving of {model['parts']} within the model's bounds ({res['domain']}).",
        "",
        model["machine"],
    ]
    if several:
        out += ["", "The other configurations hold too, as the table says: " + "; ".join(
            f"{run['label']}, {run['statesExplored']:,} states" for run in runs[1:] if run.get("statesExplored") is not None) + "."]
    return out


FINDINGS = {"B8": findings_contracts, "B9": findings_equivalence, "B10": findings_capabilities,
            "B11": findings_property, "D1": findings_tlc}


def tests_text(res):
    t = res["existingTests"]
    if t["passed"]:
        verdict = "No: every existing unit test passes" if res["verdict"] != "verified" else "Every existing unit test passes, as it should"
        return f"{verdict} (`{t['task']}`, run against the patched code)."
    names = ", ".join(f"`{f}`" for f in t["failures"]) or "a test"
    return (f"Yes, in this repo: {names} fails (`{t['task']}`). That test was written for this property. "
            "The contract needed no one to anticipate it.")


def tests_cell(res):
    t = res["existingTests"]
    if res["verdict"] == "verified":
        return "pass"
    return "caught" if not t["passed"] else "**missed**"


def details(summary, lang, text):
    return [f"<details><summary>{summary}</summary>", "", f"```{lang}", text.rstrip("\n"), "```", "", "</details>", ""]


def code(text):
    return "`" + text.replace("|", "\\|") + "`"


def render_index(folders):
    rows = []
    index = []
    for folder in folders:
        ex = json.loads((folder / "example.json").read_text())
        result_file = folder / "result.json"
        res = json.loads(result_file.read_text()) if result_file.exists() else None
        verdict = res.get("verdictLabel", VERDICT_LABEL[res["verdict"]]) if res else "not run"
        rows.append(f"| {ex['id']} | [{ex['title']}]({folder.name}/README.md) | {ex['approach']['id']} | {verdict} "
                    f"| {tests_cell(res) if res else ''} "
                    f"| {', '.join(ex['categories'])} | {ex['severity']} | {ex['change']['kind']} |")
        index.append({
            "id": ex["id"], "path": folder.name, "title": ex["title"], "summary": ex["summary"],
            "categories": ex["categories"], "severity": ex["severity"], "changeKind": ex["change"]["kind"],
            "symbol": ex["subject"]["symbol"], "approach": ex["approach"]["id"],
            "verdict": res["verdict"] if res else None,
            "existingTestsPassed": res["existingTests"]["passed"] if res else None,
        })
    readme = (EXAMPLES / "README.md").read_text()
    begin, end = "<!-- examples:begin (generated by examples/demo/tools/build.py) -->", "<!-- examples:end -->"
    table = "\n".join([begin,
                       "| # | Example | Approach | Verdict | Existing tests | Categories | Severity if shipped | Change |",
                       "|---|---|---|---|---|---|---|---|", *rows, end])
    readme = re.sub(re.escape(begin) + ".*?" + re.escape(end), lambda _: table, readme, flags=re.S)
    (EXAMPLES / "README.md").write_text(readme)
    (EXAMPLES / "index.json").write_text(json.dumps(
        {"schema": "examples-index/v1", "examples": index}, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
