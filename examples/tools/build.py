#!/usr/bin/env python3
"""Run the formal verification examples in examples/ and render them.

Each example folder holds what a person writes: example.json (the change, its risk, the expected verdict) and
change.patch. This script applies the patch to a temporary copy of the repo, runs the real verifier named by the
example's approach, and writes what it produced next to them:

  result.json          verdict, counterexamples, before/after excerpts, contract diff (examples/schema/result.schema.json)
  result.sarif         the verifier's SARIF report, with repo-relative paths
  verifier-output.txt  the verifier's console output
  statement.java       for symbolic proofs: the generated statement the prover checked
  README.md            the example, rendered for reading

and then examples/README.md (the table of contents) and examples/index.json.
It exits 1 if any verdict differs from the example's expected verdict, so the examples also test the verifiers.

Approaches (the ids are those of examples/approaches.md):
  B8   behavioural contracts: every input of a finite domain, executed      (examples/tools/contracts, verify)
  B9   regression verification: old and new bytecode compared symbolically  (examples/tools/contracts, equivalence; JBMC)
  B10  capability contracts: what a module's bytecode can reach             (examples/tools/contracts, verify)
  D1   protocol model checking: the services, Kafka and the clock in TLA+   (examples/apps/boxoffice/spec; TLC)

Usage: python3 examples/tools/build.py [ID ...]
Needs Java 25 on PATH or JAVA_HOME; JBMC for B9; TLC (tla2tools.jar in ~/tools, or TLA2TOOLS_JAR) for D1. No Docker.
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

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"
BUILD_ROOT = "examples/apps/boxoffice"  # the Gradle build the examples patch
VERIFIER = "examples/tools/contracts"
COPY = [BUILD_ROOT, VERIFIER]
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
    if example["approach"]["id"] not in RUNNERS:
        sys.exit(f"{folder}: no runner for approach {example['approach']['id']}")
    return example


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
    module = module_of(example["subject"]["file"])
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for part in COPY:
            shutil.copytree(REPO / part, tmp / part, ignore=IGNORE)
        subprocess.run(["git", "apply", "-p1", "-"], input=patch, text=True, cwd=tmp, check=True)
        build = tmp / BUILD_ROOT

        tests = gradle(build, f":{module}:test", check=False, allow_empty=True)
        failing_tests = failures(build / module / "build/test-results/test")

        result = {
            "verdict": None,
            "verdictLabel": None,
            "matchesExpected": None,
            "existingTests": {"task": f":{module}:test", "passed": tests.returncode == 0, "failures": failing_tests},
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
            "sarif": "result.sarif",
            "output": "verifier-output.txt",
        }
        RUNNERS[example["approach"]["id"]](folder, example, tmp, module, result)
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
    try:
        # One worker, so that the trace TLC reports is the same on every run.
        proc = subprocess.run(tlc() + ["-workers", "1", "-deadlock", "-cleanup", "BoxOffice.tla"],
                              cwd=spec, text=True, capture_output=True, timeout=1800)
        raw = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        raw = "Error: TLC did not finish within 30 minutes"
    output = "\n".join(l for l in raw.replace(str(tmp) + "/", "").splitlines() if not l.startswith("Progress("))
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


def tlc():
    jar = os.environ.get("TLA2TOOLS_JAR") or str(Path.home() / "tools/tla2tools.jar")
    if Path(jar).exists():
        return [java(), "-XX:+UseParallelGC", "-cp", jar, "tlc2.TLC"]
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


RUNNERS = {"B8": run_contracts, "B9": run_equivalence, "B10": run_contracts, "D1": run_tlc}


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
    """The verifier, built from examples/tools/contracts (also an included build of the Box Office Gradle project)."""
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
                    art["uri"] = f"{BUILD_ROOT}/{art['uri']}"
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


def cases_total(output):
    m = re.search(r"\((\d+) cases,", output) or re.search(r" of (\d+) cases", output)
    return int(m.group(1)) if m else None


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
    source_link = f"../../{ex['subject']['file']}"
    symbol = ex["subject"]["symbol"].rsplit(".", 1)[-1]
    change = ex["change"]
    lines = [
        "<!-- Generated by examples/tools/build.py from example.json and the verifier's output. Edit example.json. -->",
        f"# {ex['id']} · {ex['title']}",
        "",
        "[← All examples](../README.md)",
        "",
        "| Verdict | Categories | Severity if shipped | Change | Verified unit | Approach |",
        "|---|---|---|---|---|---|",
        f"| **{res['verdictLabel']}** | {', '.join(ex['categories'])} | {ex['severity']} "
        f"| {change['kind']}, behaviour change {'intended' if change['behaviourChangeIntended'] else 'not intended'} "
        f"| [`{symbol}`]({source_link}) "
        f"| [{ex['approach']['id']}: {ex['approach']['name']}](../../{ex['approach']['tool']}/README.md) |",
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
        f"python3 examples/tools/build.py {ex['id']}",
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


def findings_tlc(ex, res):
    if res["verdict"] == "violation":
        inv = res["invariant"]
        out = [
            f"TLC found a run of the system, {len(res['trace'])} steps long, that violates the invariant "
            f"**{inv}** ({INVARIANTS.get(inv, inv)}). Each step is one transaction of one service, or the clock:",
            "",
        ]
        for step in res["trace"]:
            what = ACTIONS.get(step["action"], step["action"])
            if step["step"] == 1:
                out.append(f"{step['step']}. **Initial state**: every seat available, no holds, orders or payments, "
                           "every queue empty, the clock at 0.")
                continue
            changes = ", ".join(f"`{k} = {v}`" for k, v in step["changes"].items()) or "*(no change)*"
            out.append(f"{step['step']}. **{step['action']}**, {what}. {changes}")
        out += ["", f"The model is small ({res['domain']}), which is what keeps the trace readable. TLC explored every "
                    "interleaving of the two customers, the two services, Kafka and the clock within those bounds."]
        return out
    if res["verdict"] == "unverifiable":
        return ["TLC produced no verdict:", "", f"- {code(res['problem'] or 'unknown')}"]
    return [
        f"Every invariant holds in every reachable state of the model: {res['statesExplored']:,} distinct states, "
        "which is every interleaving of the customers, the two services, Kafka and the clock within the model's "
        f"bounds ({res['domain']}).",
        "",
        "The order state machine inside the model is generated from the behavioural contract of the patched code, "
        "so the model checks the decisions the services really make.",
    ]


FINDINGS = {"B8": findings_contracts, "B9": findings_equivalence, "B10": findings_capabilities, "D1": findings_tlc}


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
    begin, end = "<!-- examples:begin (generated by examples/tools/build.py) -->", "<!-- examples:end -->"
    table = "\n".join([begin,
                       "| # | Example | Approach | Verdict | Existing tests | Categories | Severity if shipped | Change |",
                       "|---|---|---|---|---|---|---|---|", *rows, end])
    readme = re.sub(re.escape(begin) + ".*?" + re.escape(end), lambda _: table, readme, flags=re.S)
    (EXAMPLES / "README.md").write_text(readme)
    (EXAMPLES / "index.json").write_text(json.dumps(
        {"schema": "examples-index/v1", "examples": index}, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
