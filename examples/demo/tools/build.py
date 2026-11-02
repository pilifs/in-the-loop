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
        status = "as expected" if result["matchesExpected"] else \
            f"EXPECTED {example['expected']['verdict'].upper()}{' VACUOUSLY' if example['expected'].get('vacuous') else ''}"
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
            "coverage": None,
            "sarif": "result.sarif",
            "output": "verifier-output.txt",
        }
        RUNNERS[app][example["approach"]["id"]](folder, example, tmp, module, result)
    # A model-checking verdict that rests on no row the change alters is vacuous, which the example must expect too.
    vacuous = bool((result.get("coverage") or {}).get("vacuous"))
    result["matchesExpected"] = result["verdict"] == example["expected"]["verdict"] and vacuous == example["expected"].get("vacuous", False)
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


def tool_traces(app, root, traces):
    """Records the runs a trace configuration checks: the module's trace writer, a test-side main class, run on the
    patched classes, writes the recorded runs as a TLA+ module the trace specification extends."""
    build = root / TOOL_APPS[app]["root"]
    main, test = build / "build/main", build / "build/test"
    proc = subprocess.run([java(), "-cp", f"{main}{os.pathsep}{test}", traces["writer"]], text=True, capture_output=True)
    if proc.returncode != 0:
        sys.exit(f"the trace writer {traces['writer']} failed:\n{proc.stdout}\n{proc.stderr}")
    (build / traces["module"]).write_text(proc.stdout)


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
    # A method may have several properties; the one that failed is the one to report, if any did.
    m = (re.search(r"violated: (?:`(.*)`|returns)(?: where (.*?))?((?:, and throws .*?)*):$", output, re.M)
         or re.search(r"(?:satisfies `(.*)`|returns) on every input(?: where (.*?))?((?:, and throws .*?)*) \(JBMC", output))
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
        {"cfg": "spec/TwoPhaseCommitCrash.cfg", "label": "crashes",
         "what": "every run from the initial state in which the coordinator may crash, twice at most: between steps, or "
                 "after logging a phase change and before the broadcast goes out, and restart on the recovery rule, generated "
                 "from `Recovery#decide`; the same invariants and temporal properties, under the added fairness condition that "
                 "a crashed coordinator restarts"},
        {"cfg": "spec/TwoPhaseCommitCrashInductive.cfg", "label": "the inductive step with crashes",
         "what": "that the invariant `Inductive` is closed under a crash and a restart as well: TLC starts from every state the "
                 "invariant admits, the coordinator up or down, takes one step, and checks the invariant again",
         "initial": "a state the invariant `Inductive` admits, the coordinator up or down, which need not be reachable",
         "startsAnywhere": True},
        {"cfg": "spec/TwoPhaseCommitParticipantCrash.cfg", "label": "participant crashes",
         "what": "every run from the initial state in which a participant may crash, once, between steps or after logging "
                 "a vote and before sending it, and restart on the participant's rule, generated from `Participant#decide`, "
                 "while the coordinator may crash once as well; the same invariants and temporal properties, under the added "
                 "fairness condition that a crashed participant restarts"},
        {"cfg": "spec/TwoPhaseCommitParticipantCrashInductive.cfg", "label": "the inductive step with participant crashes",
         "what": "that the invariant `Inductive` is closed under a participant's crash and restart as well: TLC starts from "
                 "every state the invariant admits, each process up or down, takes one step, and checks the invariant again",
         "initial": "a state the invariant `Inductive` admits, each process up or down, which need not be reachable",
         "startsAnywhere": True},
        {"cfg": "spec/TwoPhaseCommitTrace.cfg", "spec": "spec/TwoPhaseCommitTrace.tla", "label": "the recorded runs",
         "what": "the Java nodes against the model: the coordinator node, its log and its broadcast, and the participant "
                 "nodes, their logs and their votes, run through eleven scripted scenarios with crashes of either process "
                 "injected after a given I/O operation, the state after each step recorded in the model's variables "
                 "(`TwoPhaseCommitTraces.tla`, regenerated from the patched classes); TLC walks each recorded run and checks "
                 "that it starts in the model's initial state and that every step is a step of the model's next-state "
                 "relation. A step the model has no action for is one the glue took that the model's verdicts do not cover",
         "initial": "the model's initial state as the nodes recorded it",
         "explored": "TLC walked the recorded runs, one recorded state after the other, and held each step to the "
                     "model's next-state relation `Next`: the check covers the scripted runs and no others, which is what "
                     "the model's own configurations are for.",
         "recorded": True, "coverage": False,
         "traces": {"writer": "net.terminalvalue.quorum.twopc.Traces", "module": "spec/TwoPhaseCommitTraces.tla"}},
    ],
    "traced": ["net.terminalvalue.quorum.twopc.CoordinatorNode#act", "net.terminalvalue.quorum.twopc.CoordinatorNode#onVote",
               "net.terminalvalue.quorum.twopc.CoordinatorNode#recover", "net.terminalvalue.quorum.twopc.ParticipantNode#act",
               "net.terminalvalue.quorum.twopc.ParticipantNode#giveUp", "net.terminalvalue.quorum.twopc.ParticipantNode#learn",
               "net.terminalvalue.quorum.twopc.ParticipantNode#prepare", "net.terminalvalue.quorum.twopc.ParticipantNode#recover"],
    "contract": "src/contract/Coordinator.decide.contract",
    "operator": "spec/CoordinatorContract.tla",
    "symbol": "net.terminalvalue.quorum.twopc.Coordinator#decide",
    "operators": [{"contract": "src/contract/Recovery.decide.contract", "operator": "spec/RecoveryContract.tla",
                   "symbol": "net.terminalvalue.quorum.twopc.Recovery#decide"},
                  {"contract": "src/contract/Participant.decide.contract", "operator": "spec/ParticipantContract.tla",
                   "symbol": "net.terminalvalue.quorum.twopc.Participant#decide"}],
    "parts": "the participants, the coordinator and the votes in flight",
    "initial": "every participant working, no vote counted, no decision, every process up",
    "actions": {
        "Initial predicate": "the initial state",
        "Vote": "`Participant.prepare`: a participant votes yes (and holds its locks) or no (and aborts), as its rule decides; "
                "it logs the state before it sends the vote, and a crash can fall between the two",
        "ParticipantTimeout": "`Participant.timeout`: a participant that has not voted gives up on its own",
        "Learn": "`Participant.learn`: a participant applies the coordinator's decision",
        "ParticipantCrash": "a participant crashes between steps: it loses nothing it logged, and takes no step until it restarts",
        "ParticipantRecover": "`Participant.recover`: a participant restarts with the state it logged and acts on its rule's "
                              "decision: on the committed rule, a prepared one holds its locks and waits, one that had not voted aborts",
        "ReceiveVote": "`Coordinator.onVote`: the coordinator counts a vote and decides on the tally",
        "CoordinatorTimeout": "`Coordinator.onTimeout`: the collection timer fires with votes missing",
        "Crash": "the coordinator crashes between steps: it loses nothing it logged, and takes no step until it restarts",
        "Recover": "`Recovery.decide`: the coordinator restarts with the phase it logged and acts on the recovery rule's "
                   "decision, which a crash can cut short like any other",
        "TraceNext": "the next state the nodes recorded, after the step the comment in `TwoPhaseCommitTraces.tla` names",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "Atomicity": "once the coordinator or any participant has committed, no participant has aborted",
        "CommitFollowsTheCoordinator": "a participant commits only on the coordinator's decision, and only after voting yes",
        "VotesInFlightAreUncounted": "a vote on its way to the coordinator has not been counted, and a participant votes once",
        "DecisionMatchesThePhase": "what the coordinator broadcast, if anything, is what its phase says: a crash can fall "
                                   "between the logged phase change and the broadcast",
        "BroadcastOnceUp": "a coordinator that is up and decided has its decision out, broadcast when it decided or on restarting",
        "DownOnlyAfterACrash": "the coordinator is down only after a crash",
        "ParticipantsDownOnlyAfterACrash": "participants are down only after crashes: no more of them than have crashed",
        "ParticipantsAgreeWithTheirVotes": "a working participant has not voted, a prepared one voted yes unless a crash took the "
                                           "vote after the state was logged, a no voter has aborted, and a yes voter that aborted "
                                           "did so on the coordinator's say-so",
        "CommitNeedsEveryVote": "the coordinator commits only once every vote is counted and yes",
        "EveryParticipantDecides": "every participant eventually commits or aborts, under the fairness the model assumes: "
                                   "participants vote or give up, the coordinator counts every vote and fires its timer while votes are missing, "
                                   "participants apply a decision once made, and a crashed process restarts",
        "ImplementsTransactionCommit": "every behaviour of the protocol, seen through the participants' states, is one transaction commit "
                                       "(Lamport and Gray's TCommit) allows: a participant commits only once every participant is prepared or "
                                       "committed, and aborts only while none has committed",
        "StartsAtTheInitialState": "the first state of a recorded run is the model's initial state",
        "EveryStepIsOneOfTheModel": "every step the nodes recorded is a step of the model's next-state relation: an action of "
                                    "one part, or a step that changes nothing. A step the model has no action for is one "
                                    "the glue around the rules took, which the model's verdicts do not cover",
    },
    "machine": "The coordinator's decision rule, its recovery rule and the participant's rule inside the model are generated "
               "from the behavioural contracts of the patched code, so the model checks the decisions the processes really "
               "make: the coordinator's on a vote, a timeout and a restart, and a participant's when asked to prepare, when "
               "it gives up, when it reads the decision and when it restarts.",
}

RAFT = {
    "spec": "spec/RaftElection.tla",
    "cfg": "spec/RaftElection.cfg",
    "label": "three servers",
    # The same model under six more configurations, run after the first; the README reports all seven.
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
        {"cfg": "spec/RaftElectionLogs.cfg", "label": "a server left behind",
         "what": "the election restriction: one server holds the log a deposed leader of term 1 left behind, three entries of "
                 "its term, while the other two hold an entry of term 2 that a majority holds and is therefore committed, so "
                 "that the longer log is the one behind; every run with these logs, which nothing changes, under the invariant "
                 "`LeaderCompleteness` besides the usual ones"},
        {"cfg": "spec/RaftElectionDelayed.cfg", "label": "delayed replies",
         "what": "every run of three servers and two terms in which the reply to a vote request is a step of its own, which "
                 "the candidate may take after it has timed out into a newer term, stepped down, or won; the one-step RPC "
                 "of the other configurations never hands the role machine a reply from an older term than the server's "
                 "own, and this one does, under the usual invariants and action properties"},
        {"cfg": "spec/RaftElectionHistory.cfg", "label": "history",
         "what": "every run of three servers and three terms with the two history variables recording, `elected`, every "
                 "term a server has led, and `voted`, every vote cast, under the two invariants that are about a run rather "
                 "than a state: at most one leader elected per term and at most one vote per server per term, as the paper "
                 "states them. The state invariants of the other configurations hold in a run in which a term's leader steps "
                 "down and the term then elects another; these do not"},
    ],
    "contract": "src/contract/RoleMachine.decide.contract",
    "operator": "spec/RoleMachineContract.tla",
    "symbol": "net.terminalvalue.quorum.raft.RoleMachine#decide",
    # The model's second generated operator: the vote rule, brought in as an instance.
    "operators": [{"contract": "src/contract/VoteRule.decide.contract", "operator": "spec/VoteRuleContract.tla",
                   "symbol": "net.terminalvalue.quorum.raft.VoteRule#decide"}],
    "parts": "the servers, their terms and votes, and the RPCs between them",
    "initial": "every server a follower in term 0, no vote cast, no vote held",
    "actions": {
        "Initial predicate": "the initial state",
        "Timeout": "`Server.onElectionTimeout`: a server's election timer fires, and the server acts on the role machine's decision",
        "Canvass": "`Server.requestVote`: a candidate asks one server for its vote and gets the answer; the request and the reply "
                   "each go through the role machine, then the vote rule on the voter, given its ballot and the candidate's "
                   "term and log against its own, and the tally on the candidate",
        "Ask": "`Server.requestVote`, the request alone: a candidate asks one server for its vote, which the voter decides "
               "as in `Canvass`, and the reply waits on the wire with the term the voter answered in",
        "Answer": "`Server.onVote`: the candidate takes a reply that waited; its term goes through the role machine as it "
                  "compares with the candidate's term now, a granted vote of the current term goes into the tally, and the "
                  "tally through the role machine",
        "Heartbeat": "`Server.appendEntries`: a leader sends one server a heartbeat and gets the answer; the server adopts a newer "
                     "term or yields to the leader of its own, and a stale leader is rejected and steps down",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "ElectionSafety": "at most one leader per term",
        "KernelNeverThrows": "no timeout or RPC any reachable state allows makes the role machine or the vote rule throw: the "
                             "IllegalStateException the Java reserves for an input it holds impossible never fires",
        "LeaderHasAMajority": "a leader holds the votes of a majority of the servers, its own among them",
        "LeaderCompleteness": "a leader's log holds every committed entry, an entry being committed once a majority of the "
                              "servers hold it; the election restriction is what makes it so, a voter granting only a "
                              "candidate whose log is at least as up to date as its own",
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
    "machine": "The servers' role machine and vote rule inside the model are generated from the behavioural contracts of "
               "the patched code, so the model checks the role transitions the servers really make and the votes they "
               "really grant.",
}

REPLICATION = {
    "spec": "spec/RaftReplication.tla",
    "cfg": "spec/RaftReplication.cfg",
    "label": "three terms, two entries",
    # The same model under two more configurations, run after the first; the README reports all three.
    "configurations": [
        {"cfg": "spec/RaftReplicationFigureEight.cfg", "label": "figure 8",
         "what": "every run of three servers over four terms with one entry per leader's log, the budget of figure 8 of the "
                 "paper: a leader of term 1 appends an entry it never gets to replicate, a leader of term 2 appends its own "
                 "at the same index, the first comes back as the leader of term 3 and replicates its entry of term 1 to a "
                 "majority, and the second, whose last entry is from the later term, can still be elected in term 4 "
                 "without it; three terms cannot show this, and the same invariants and action properties are checked"},
        {"cfg": "spec/RaftReplicationLive.cfg", "label": "fairness",
         "what": "the three liveness properties, under the fairness conditions `Fairness`: a server whose timer nothing "
                 "resets times out, a candidate asks for the votes it lacks, a leader sends every follower its next entry or "
                 "a heartbeat and marks committed what the commit rule lets it; nothing is assumed of the clients, so the "
                 "properties hold whether or not a request comes. Three servers, three terms and one entry per leader, without the symmetry "
                 "set, since TLC's liveness checking is unsound under one. A counterexample is a run that goes on forever "
                 "without satisfying a property: a prefix, then a state or a cycle the system never leaves"},
    ],
    "contract": "src/contract/AppendRule.decide.contract",
    "operator": "spec/AppendRuleContract.tla",
    "symbol": "net.terminalvalue.quorum.raft.AppendRule#decide",
    # The model's other generated operators: the commit rule, the role machine and the vote rule, brought in as instances.
    "operators": [{"contract": "src/contract/CommitRule.decide.contract", "operator": "spec/CommitRuleContract.tla",
                   "symbol": "net.terminalvalue.quorum.raft.CommitRule#decide"},
                  {"contract": "src/contract/RoleMachine.decide.contract", "operator": "spec/RoleMachineContract.tla",
                   "symbol": "net.terminalvalue.quorum.raft.RoleMachine#decide"},
                  {"contract": "src/contract/VoteRule.decide.contract", "operator": "spec/VoteRuleContract.tla",
                   "symbol": "net.terminalvalue.quorum.raft.VoteRule#decide"}],
    "parts": "the servers, their terms, votes and logs, and the AppendEntries RPCs between them",
    "initial": "every server a follower in term 0 with an empty log, no vote cast, nothing committed",
    "actions": {
        "Initial predicate": "the initial state",
        "Timeout": "`Server.onElectionTimeout`: a server's election timer fires, and the server acts on the role machine's decision",
        "Canvass": "`Server.requestVote`: a candidate asks one server for its vote and gets the answer; the request and the reply "
                   "each go through the role machine, then the vote rule on the voter, given its ballot and the candidate's "
                   "term and log against its own, and the tally on the candidate",
        "ClientRequest": "`Server.onClientRequest`: a leader appends an entry of its term to its own log",
        "Replicate": "`Server.appendEntries`: a leader sends one server the entry at that server's next index, or a heartbeat "
                     "if it is caught up, with the entry before it and the leader's commit index, and gets the answer; the "
                     "request goes through the role machine, then the append rule on the follower's log as it stands against "
                     "the leader's, and the reply through the role machine on the leader, which moves the server's next and "
                     "match indices forward on success and backs the next index up by one on a refusal",
        "AdvanceCommit": "`Server.advanceCommitIndex`: a leader asks the commit rule about an entry it has not marked "
                         "committed, given the entry's term against its own and whether a majority of the servers hold it, and "
                         "marks it committed on a transition, and with it everything before it",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "KernelNeverThrows": "no timeout or RPC any reachable state allows makes the role machine, the vote rule, the append "
                             "rule or the commit rule throw: the IllegalStateException the commit rule reserves for an entry "
                             "from a term after the leader's never fires",
        "ElectionSafety": "at most one leader per term",
        "LogMatching": "if two logs hold an entry of the same term at the same index, they are the same through that index "
                       "(figure 3 of the paper); the append rule's consistency check is what makes it so",
        "LeaderCompleteness": "a leader holds every entry a server of its term or an earlier one knows committed (figure 3 of "
                              "the paper); the election restriction and the commit rule together are what make it so",
        "StateMachineSafety": "no two servers have committed different entries at one index (figure 3 of the paper)",
        "CommittedEntriesNeverChange": "a committed entry is never overwritten and a commit index never goes backwards, in "
                                       "any step: once a server has applied an entry, that entry stays at its index for good",
        "TermsNeverDecrease": "a term never goes backwards on any server, in any step",
        "LeaderAppendOnly": "a leader never truncates or overwrites its own entries, in any step (figure 3 of the paper)",
        # The liveness properties, checked under fairness, of the runs that stay within the term budget.
        "FollowersCatchUp": "every entry in a leader's log reaches every follower: from some point on, each follower's log "
                            "holds the leader's as a prefix, in every run that stays within the term budget",
        "FollowersLearnCommits": "every follower learns what the leader has committed: from some point on, all commit "
                                 "indices agree, in every run that stays within the term budget",
        "OwnEntriesAreCommitted": "an entry a leader appended in its term is committed, unless the leader is deposed first, in "
                                  "every run that stays within the term budget; nothing is claimed of an entry from an "
                                  "earlier term, which the commit rule commits only along with a later entry of the "
                                  "leader's own",
    },
    "machine": "The follower's append rule, the leader's commit rule, the role machine and the vote rule inside the model are "
               "generated from the behavioural contracts of the patched code, so the model checks the entries the followers "
               "really take, the commits the leaders really make, and the roles and votes behind them.",
}

IDEMPOTENCY = {
    "spec": "spec/IdempotentReceiver.tla",
    "cfg": "spec/IdempotentReceiver.cfg",
    "label": "the record never expires",
    "configurations": [
        {"cfg": "spec/IdempotentReceiverExpiring.cfg", "label": "expiring record",
         "what": "the same invariants, with the record's time to live allowed to pass at any point: the sweeper asks the "
                 "receiver what to do with the record and applies the decision, and a release ends the record's lifetime, "
                 "so `AtMostOnce` counts the results since the last release. The model has no clock, so the sweeper's clock "
                 "has measured the record's age and nothing else, in particular not whether an execution is still running"},
    ],
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
        "Expire": "`IdempotencySweeper.sweep`: the record's time to live passed; the sweeper asks the receiver what to do "
                  "with the record and applies the decision",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "OneExecutionAtATime": "no two attempts under one key execute at the same time",
        "AtMostOnce": "once an execution has produced a result, no attempt is executing and none ever will, for as long as "
                      "the record lives (in the configuration where it never expires, at most once outright)",
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

BREAKER = {
    "spec": "spec/CircuitBreaker.tla",
    "cfg": "spec/CircuitBreaker.cfg",
    "label": "two calls in flight",
    "configurations": [
        {"cfg": "spec/CircuitBreakerLive.cfg", "label": "fairness",
         "what": "the three liveness properties, under the fairness conditions `Fairness`: the caller keeps calling, every "
                 "permitted call completes, the clock ticks, and nothing is assumed of the dependency. A counterexample is a "
                 "run that goes on forever without satisfying a property: a prefix, then a state or a cycle the system never leaves"},
    ],
    "contract": "src/contract/CircuitBreaker.decide.contract",
    "operator": "spec/CircuitBreakerContract.tla",
    "symbol": "net.terminalvalue.crosscut.resilience.CircuitBreaker#decide",
    "parts": "the caller, the owner of the breaker with its window, its probes and its wait, the dependency and the clock",
    "initial": "the breaker closed, the window empty, no call in flight, no wait running, the dependency up or down",
    "actions": {
        "Initial predicate": "the initial state",
        "Request": "`CircuitBreaker.tryAcquirePermission`: a caller asks for a call; the owner reports whether the wait has "
                   "elapsed and applies the decision, which lets the call through, starts a new metrics generation, or starts the wait",
        "Complete": "`CircuitBreaker.onResult`, for a call of the current generation: the owner records the outcome, judges "
                    "the window, and applies the decision",
        "CompleteStale": "`CircuitBreaker.onResult`, for a call from an earlier generation: its outcome is dropped",
        "Tick": "the clock advances: one tick less of the open state's wait",
        "DependencyFlips": "the dependency goes down, or comes back",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "NoCallBeforeTheWait": "an open breaker lets nothing through until its wait has elapsed",
        "OpenShieldsTheDependency": "while open, the dependency receives no call of the current generation: everything in "
                                    "flight was permitted before the breaker opened",
        "ClosedOnlyAfterEveryProbe": "half-open closes only once every permitted probe has completed",
        "ProbesAreLimited": "half-open lets at most the permitted number of probes through before it decides",
        "ClosedOnlyBelowTheThreshold": "a closed breaker never sits on a complete window whose failure rate is at the threshold",
        # The liveness properties, checked under fairness.
        "AnOpenBreakerProbesAgain": "an open breaker does not stay open: its wait elapses, and the next call is let through as a probe",
        "ARecoveredDependencyIsUsed": "a dependency that comes back for good is used again: from some point on the breaker is "
                                      "closed and stays so",
        "ADeadDependencyIsLeftAlone": "a dependency that is down for good gets the wait between its probes: the breaker opens "
                                      "again and again, so that no round of probes is followed by another without a wait",
    },
    "machine": "The breaker's decision rule inside the model is generated from the behavioural contract of the patched code, "
               "so the model checks the transitions the breaker really makes; the owner's part, the window, the probe cap and "
               "the wait, is written in the model and applies whatever the rule returns.",
}

# The TLA+ models of each javac app, each built around the state machine of one symbol.
TOOL_MODELS = {"quorum": [TWOPC, RAFT, REPLICATION], "crosscut": [IDEMPOTENCY, BREAKER], "mica": [CLASSINIT]}


def model_of(example):
    """The model a D1 example is checked against: the one of its app built around the example's symbol."""
    app = app_of(example)
    if app == "boxoffice":
        return MODELS["boxoffice"]
    for model in TOOL_MODELS[app]:
        if example["subject"]["symbol"] in [model["symbol"]] + [o["symbol"] for o in model.get("operators", [])] \
                + model.get("traced", []):
            return model
    sys.exit(f"{example['id']}: no TLA+ model of {app} is built around {example['subject']['symbol']}")


def tlc_run(build, model_files, configuration, root):
    """One run of TLC on a model under a configuration, through the tool: its parsed JSON, plus the configuration's
    bounds (`domain`) and whether it lists temporal properties. A configuration may name a `spec` of its own, a
    module that extends the model (the trace specification does), and may turn `coverage` off: TLC attributes no
    coverage to a next-state relation it evaluates as an action property."""
    cfg = configuration["cfg"]
    deadlock = ["--deadlock"] if model_files.get("deadlock") else []
    config = [] if cfg == model_files["cfg"] else ["--config", cfg]
    coverage = ["--coverage"] if configuration.get("coverage", True) else []
    proc = subprocess.run([jvmcontract(), "tlc", configuration.get("spec", model_files["spec"]), "--json", *coverage, *deadlock, *config,
                           "--library", str(EXAMPLES / "tools/tla/standard-modules")], text=True, capture_output=True, cwd=build)
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


def contract_rows(text):
    """A contract's cases and their outcomes, by case."""
    return dict(re.findall(r"^(\w+\(.*\))\s+=> (.*)$", text, re.M))


def tlc_coverage(configurations, runs, before, after):
    """What the verdict rests on: for each configuration, how many rows of each generated operator a step of the
    model took (TLC's coverage, read back by the tool); the rows the change altered, with the configurations whose
    runs take them; and whether the verdict is vacuous, which it is when every run finishes and none from an initial
    state takes any altered row that decides. The inductive step starts from every state the invariant admits, not
    from a run, so it does not count: it only says the invariant held one step on. A run that stops at a
    counterexample has explored a part of the model and its counts are left out; the verdict then rests on the
    counterexample. Rows that throw are meant never to be taken, so they do not make a verdict vacuous: whether a
    run could take one is for an invariant over the model's events to say. Rows with a null argument are not in
    the model, which never passes null."""
    # The reason an outcome records is not in the model, so a row that changes only in its reason has not changed.
    in_the_model = lambda outcome: re.sub(r'^(Unchanged|Rejected)\[.*\]$', r'\1', outcome) if outcome else outcome
    changed, nulls = [], 0
    for contract, rows in after.items():
        for case, outcome in rows.items():
            was = before.get(contract, {}).get(case)
            if in_the_model(was) == in_the_model(outcome):
                continue
            if re.search(r"\(null, |, null\)", case):
                nulls += 1
            else:
                changed.append({"case": case, "before": was, "after": outcome})
    reached = {}
    per_configuration = []
    for c, r in zip(configurations, runs):
        finished = r["verdict"] == "verified"
        operators = []
        for op in (r.get("coverage") or []) if finished else []:
            taken = [row["case"] for row in op["rows"] if row["taken"]]
            operators.append({"symbol": op["symbol"], "reached": len(taken), "total": len(op["rows"]),
                              "never": [f"{row['case']} => {row['outcome']}" for row in op["rows"] if not row["taken"]]})
            for case in taken:
                reached.setdefault(case, []).append(c["label"])
        per_configuration.append({"label": c["label"], "fromRuns": not c.get("startsAnywhere", False), "finished": finished,
                                  "counted": c.get("coverage", True), "operators": operators})
    from_runs = {c["label"] for c in configurations if not c.get("startsAnywhere", False)}
    for row in changed:
        row["takenUnder"] = reached.get(row["case"], [])
    deciding = [row for row in changed if not row["after"].startswith("throws ")]
    vacuous = bool(deciding) and all(c["finished"] for c in per_configuration) \
        and not any(set(row["takenUnder"]) & from_runs for row in deciding)
    return {"configurations": per_configuration, "changedRows": changed, "nullRows": nulls, "vacuous": vacuous}


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
    generated = [model_files, *model_files.get("operators", [])]
    rows_before = {g["contract"]: contract_rows((build / g["contract"]).read_text()) for g in generated}
    if example["change"]["behaviourChangeIntended"]:
        tool_update_contracts(app, root, result)
    rows_after = {g["contract"]: contract_rows((build / g["contract"]).read_text()) for g in generated}
    for g in generated:
        tool(app, root, "tla", g["contract"], g["operator"], anchored=False)
    configurations = tlc_configurations(model_files)
    for c in configurations:
        if c.get("traces"):
            tool_traces(app, root, c["traces"])
    runs = [(c, tlc_run(build, model_files, c, root)) for c in configurations]
    result["coverage"] = tlc_coverage(configurations, [r for _, r in runs], rows_before, rows_after)
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
        "stateMachine": tool_state_machine(app, root, example["subject"]["symbol"]),
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
    changed = len(result["coverage"]["changedRows"])
    if verdict == "verified" and result["coverage"]["vacuous"]:
        label = f"{VERDICT_LABEL[verdict]}, vacuously: no run takes the {changed} row{'s' if changed != 1 else ''} the change alters"
    elif several and verdict == "violation" and configuration is not configurations[0]:
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


def tlc_trace_lines(model, trace, initial, starts_anywhere=False, recorded=False):
    """A counterexample as a numbered list: each step one action of one part of the system, or, for a recorded run
    held to the model, the next state the implementation recorded."""
    out = []
    for step in trace:
        what = model["actions"].get(step["action"], step["action"])
        bookkeeping = {"run", "step", "scenario"} if recorded else set()
        changes = ", ".join(f"`{k} = {v}`" for k, v in step["changes"].items() if k not in bookkeeping) or "*(no change)*"
        if step["step"] == 1 and recorded:
            out.append(f"{step['step']}. **Start of the recorded run** `{step['changes'].get('scenario', '')}`, {initial}: {changes}")
        elif step["step"] == 1 and not starts_anywhere:
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
        each = " Each step is one action of one part of the system:"
        if configuration.get("recorded"):
            each = " Each step is the next state the implementation recorded:"
        out += [found + (each if steps > 1 else ""), ""]
        out += tlc_trace_lines(model, res["trace"], configuration["initial"], configuration.get("startsAnywhere", False),
                               configuration.get("recorded", False))
        out += ["", configuration.get("explored") or
                    f"The model is small ({res['domain']}), which is what keeps the trace readable. TLC explored every "
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
            out += tlc_trace_lines(model, run["trace"], c["initial"], c.get("startsAnywhere", False), c.get("recorded", False))
            out += ["", "</details>"]
        return out + coverage_lines(res)
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
    return out + coverage_lines(res)


def coverage_lines(res):
    """What the verdict rests on: the rows of the generated operators a step of the model takes under each
    configuration, the rows the change alters and which runs take them, and the rows no step takes."""
    cov = res.get("coverage")
    # A configuration that counts no coverage (the recorded runs: TLC attributes none to an action property) is left out.
    configs = [c for c in (cov or {}).get("configurations", []) if c.get("counted", True) and (c["operators"] or not c["finished"])]
    finished = [c for c in configs if c["finished"] and c["operators"]]
    if not cov or not finished:
        return []
    short = lambda symbol: "`" + symbol.rsplit(".", 1)[-1] + "`"
    out = ["", "**What the verdict rests on.** TLC counted how often a step of the model took each row of the generated "
               "operators. A row no step takes is one the model says nothing about, whatever the verdict."]
    operators = finished[0]["operators"]
    if len(configs) > 1:
        out += ["", "| Configuration | " + " | ".join(f"Rows of {short(op['symbol'])} taken" for op in operators) + " |",
                "|---|" + "---|" * len(operators)]
        for c in configs:
            note = "" if c["fromRuns"] else " (from the states the invariant admits, not from a run)"
            cells = [f"{op['reached']} of {op['total']}" for op in c["operators"]] if c["finished"] else ["stopped at the counterexample"] * len(operators)
            out.append(f"| {c['label']}{note} | " + " | ".join(cells) + " |")
    else:
        out += ["", "Rows taken: " + "; ".join(f"{op['reached']} of {op['total']} of {short(op['symbol'])}" for op in operators) + "."]
    changed = cov["changedRows"]
    stopped = [c["label"] for c in configs if not c["finished"]]
    if changed:
        from_runs = {c["label"] for c in configs if c["fromRuns"]}
        nulls = f", and {cov['nullRows']} with a null argument, which the model leaves out" if cov.get("nullRows") else ""
        out += ["", f"The change alters {len(changed)} row{'s' if len(changed) != 1 else ''} of the contract{nulls}:", ""]
        for row in changed:
            under = row["takenUnder"]
            taken = f"taken under {', '.join(under)}" if under else ("taken by no run that finished" if stopped else "taken by no run")
            out.append(f"- {code(row['case'])}: {code(row['before']) if row['before'] else 'a new row'} → {code(row['after'])}, {taken}")
        deciding = [row for row in changed if not row["after"].startswith("throws ")]
        throwing = len(changed) - len(deciding)
        by_a_run = [row for row in deciding if set(row["takenUnder"]) & from_runs]
        only_admitted = [row for row in deciding if row["takenUnder"] and not set(row["takenUnder"]) & from_runs]
        if stopped:
            out += ["", f"The run under {', '.join(stopped)} stopped at its counterexample, the steps above, and its counts are left out: "
                        "the verdict rests on the counterexample."]
        elif cov["vacuous"]:
            why = (" Only the inductive step takes " + ("them" if len(only_admitted) == len(deciding) else f"{len(only_admitted)} of them")
                   + ", from states the invariant admits rather than from a run; that it found nothing says the invariant held one step on, no more."
                   if only_admitted else "")
            out += ["", f"**No run of the model takes any of them.**{why} The verdict is about the model as it was, and says nothing about the change."]
        elif not deciding:
            out += ["", f"{'All' if throwing > 1 else 'The one'} row{'s' if throwing > 1 else ''} the change alters throw{'' if throwing > 1 else 's'}, "
                        "and no run takes them: that is what a row that throws asks. Whether no run can is for an invariant over the model's "
                        "events to say, not for coverage, which counts the steps taken."]
        elif len(by_a_run) == len(deciding):
            out += ["", "Runs of the model take every row the change alters" + (f" that decides; the {throwing} that throw are taken by no run, as they must not be" if throwing else "") + ": the verdict rests on the change."]
        else:
            out += ["", f"Runs of the model take {len(by_a_run)} of the {len(deciding)} rows the change alters{' that decide' if throwing else ''}; "
                        "the verdict rests on those, and says nothing about the others."]
    primary = finished[0]
    never = [(op["symbol"], op["never"]) for op in primary["operators"] if op["never"]]
    if never:
        out += ["", f"<details><summary>Rows no step takes under {primary['label']}</summary>", ""]
        for symbol, rows in never:
            out += [f"`{symbol}`:", "", "```", *rows, "```", ""]
        out += ["</details>"]
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
