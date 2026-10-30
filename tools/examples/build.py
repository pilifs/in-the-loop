#!/usr/bin/env python3
"""Run the formal verification examples in examples/ and render them.

Each example folder holds what a person writes: example.json (the change, its risk, the expected verdict) and
change.patch. This script applies the patch to a temporary copy of the repo, runs the real verifier, and writes
what it produced next to them:

  result.json          verdict, counterexamples, before/after excerpts, contract diff (examples/schema/result.schema.json)
  result.sarif         the verifier's SARIF report, with repo-relative paths
  verifier-output.txt  the verifier's console output
  README.md            the example, rendered for reading

and then examples/README.md (the table of contents) and examples/index.json.
It exits 1 if any verdict differs from the example's expected verdict, so the examples also test the verifier.

Usage: python3 tools/examples/build.py [ID ...]      (Java 25 on PATH or JAVA_HOME; no Docker needed)
"""

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
BUILD_ROOT = "apps/boxoffice"  # the Gradle build the examples patch
COPY = ["apps/boxoffice", "tools/contracts"]
IGNORE = shutil.ignore_patterns("build", ".gradle", ".kotlin", "*.class")

VERDICT_LABEL = {
    "violation": "✗ Violation",
    "verified": "✓ Verified",
    "unverifiable": "⚠ Unverifiable",
}


def main(argv):
    wanted = set(argv)
    folders = sorted(p for p in EXAMPLES.iterdir() if p.is_dir() and re.match(r"^\d{3}-", p.name))
    failures = []
    for folder in folders:
        if wanted and folder.name[:3] not in wanted:
            continue
        example = load_example(folder)
        print(f"{folder.name}: running", flush=True)
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
    patch = (folder / example["change"]["patch"]).read_text()
    before, after = excerpts(patch)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for part in COPY:
            shutil.copytree(REPO / part, tmp / part, ignore=IGNORE)
        subprocess.run(["git", "apply", "-p1", "-"], input=patch, text=True, cwd=tmp, check=True)

        build = tmp / BUILD_ROOT
        module = module_of(example["subject"]["file"])
        contract_diff = None
        if example["change"]["behaviourChangeIntended"]:
            contract_dir = build / module / "src/contract"
            old = {f.name: f.read_text() for f in contract_dir.glob("*.contract")}
            gradle(build, f":{module}:updateContracts")
            contract_diff = "".join(
                "".join(difflib.unified_diff(
                    old.get(f.name, "").splitlines(True), f.read_text().splitlines(True),
                    f"a/{BUILD_ROOT}/{module}/src/contract/{f.name}",
                    f"b/{BUILD_ROOT}/{module}/src/contract/{f.name}"))
                for f in sorted(contract_dir.glob("*.contract")))

        tests = gradle(build, f":{module}:test", check=False, allow_empty=True)
        failing_tests = failures(build / module / "build/test-results/test")
        proc = gradle(build, f":{module}:verifyContracts", check=False)
        output = proc.stdout.replace(str(tmp) + "/", "")
        sarif = json.loads((build / module / "build/reports/contracts/contracts.sarif").read_text())

    for run_ in sarif["runs"]:
        for res in run_["results"]:
            for loc in res.get("locations", []):
                art = loc["physicalLocation"]["artifactLocation"]
                art["uri"] = f"{BUILD_ROOT}/{art['uri']}"
    (folder / "result.sarif").write_text(json.dumps(sarif, indent=2, ensure_ascii=False) + "\n")
    (folder / "verifier-output.txt").write_text(output)

    verdict = "verified" if proc.returncode == 0 else (
        "unverifiable" if "cannot be verified" in output else "violation")
    return {
        "verdict": verdict,
        "matchesExpected": verdict == example["expected"]["verdict"],
        "existingTests": {
            "task": f":{module}:test",
            "passed": tests.returncode == 0,
            "failures": failing_tests,
        },
        "before": before,
        "after": after,
        "casesTotal": cases_total(output),
        "counterexamples": counterexamples(output),
        "purityViolations": purity_violations(output),
        "trustedCalls": trusted_calls(output),
        "contractDiff": contract_diff,
        "sarif": "result.sarif",
        "output": "verifier-output.txt",
    }


def gradle(build, task, check=True, allow_empty=False):
    proc = subprocess.run(["./gradlew", "-q", task], cwd=build, text=True, capture_output=True)
    if check and proc.returncode != 0:
        sys.exit(f"{task} failed:\n{proc.stdout}\n{proc.stderr}")
    if proc.returncode != 0 and not proc.stdout.strip() and not allow_empty:
        sys.exit(f"{task} failed before the verifier ran:\n{proc.stderr}")
    return proc


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


# Parsing the verifier's output


def cases_total(output):
    m = re.search(r"\((\d+) cases,", output) or re.search(r" of (\d+) cases", output)
    return int(m.group(1)) if m else None


def trusted_calls(output):
    m = re.search(r"trusting (.*)\)$", output, re.M)
    return [c.strip() for c in m.group(1).split(",")] if m else []


def purity_violations(output):
    m = re.search(r"not provably pure:\n((?:  .*\n)+)", output)
    return [line.strip() for line in m.group(1).splitlines()] if m else []


def counterexamples(output):
    found = []
    pattern = re.compile(
        r"^  (\S.*)\n(?:    contract: (.*)\n    actual:   (.*)|    added:    (.*)|    removed: .*\(was (.*)\))$", re.M)
    for m in pattern.finditer(output):
        if m.group(2) is not None:
            found.append({"input": m.group(1), "contract": m.group(2), "actual": m.group(3)})
        elif m.group(4) is not None:
            found.append({"input": m.group(1), "contract": None, "actual": m.group(4)})
        else:
            found.append({"input": m.group(1), "contract": m.group(5), "actual": None})
    return found


def excerpts(patch):
    """The before and after sides of the patch's hunks, with their context lines."""
    file = None
    sides = {"before": [], "after": []}
    starts = {}
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            file = line[len("+++ b/"):]
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
    return tuple(
        {"file": file, "startLine": starts[side], "code": dedent(sides[side])} for side in ("before", "after"))


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
        "<!-- Generated by tools/examples/build.py from example.json and the verifier's output. Edit example.json. -->",
        f"# {ex['id']} · {ex['title']}",
        "",
        "[← All examples](../README.md)",
        "",
        "| Verdict | Categories | Severity if shipped | Change | Verified unit | Approach |",
        "|---|---|---|---|---|---|",
        f"| **{verdict_text(res)}** | {', '.join(ex['categories'])} | {ex['severity']} "
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
    lines += findings(res)
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
    lines += details("Verifier output", "text", (folder / res["output"]).read_text())
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
        f"python3 tools/examples/build.py {ex['id']}",
        "```",
        "",
        "This applies `change.patch` to a temporary copy of the repo, runs the verifier on it, and rewrites this page.",
        "",
    ]
    return "\n".join(lines)


def verdict_text(res):
    label = VERDICT_LABEL[res["verdict"]]
    if res["verdict"] == "violation":
        return f"{label}: {len(res['counterexamples'])} of {res['casesTotal']} cases changed"
    if res["verdict"] == "verified" and res["casesTotal"]:
        return f"{label}: all {res['casesTotal']} cases match"
    return label


def findings(res):
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
        verdict = verdict_text(res) if res else "not run"
        rows.append(f"| {ex['id']} | [{ex['title']}]({folder.name}/README.md) | {verdict} "
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
    begin, end = "<!-- examples:begin (generated by tools/examples/build.py) -->", "<!-- examples:end -->"
    table = "\n".join([begin,
                       "| # | Example | Verdict | Existing tests | Categories | Severity if shipped | Change |",
                       "|---|---|---|---|---|---|---|", *rows, end])
    readme = re.sub(re.escape(begin) + ".*?" + re.escape(end), lambda _: table, readme, flags=re.S)
    (EXAMPLES / "README.md").write_text(readme)
    (EXAMPLES / "index.json").write_text(json.dumps(
        {"schema": "examples-index/v1", "examples": index}, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
