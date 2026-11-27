"""Reconcile the Spring Boot brief, original build records and numbered public callers."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import public_comparison

BRIEF = ROOT / "llm-dlc/loops/spring-boot-merged-pr-links-s01-s50-brief.md"
SETUP = BRIEF.with_name(BRIEF.stem + "-setup.md")
SIDES = ("parent", "fix")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory():
    """Take the case order, revision identities and all five claim columns from the brief."""
    setup = SETUP.read_text()
    cases = {}
    for section in BRIEF.read_text().split("\n## "):
        header = re.match(r"spring-projects/spring-boot#(\d+) · Spring Boot #\1 — (.+)", section)
        if not header:
            continue
        label = f"S{len(cases) + 1:02}"
        number, title = header.groups()
        pins = re.search(r"Before `([0-9a-f]{40})`, after `([0-9a-f]{40})`", section)
        require(pins and all(f"`{pin}`" in setup for pin in pins.groups()), label + " revision mismatch")
        questions = {}
        for line in section.splitlines():
            if line.startswith("| spring-projects/spring-boot#"):
                identifier, history, prediction, basis, refutation = (part.strip() for part in line.strip("|").split(" | "))
                key, role = identifier.split(" · ")
                require(key == f"spring-projects/spring-boot#{number}.{len(questions) + 1}", label + " claim ID")
                questions[key] = dict(role=role, history=history, prediction=prediction, basis=basis, refutation=refutation)
        require([q["role"] for q in questions.values()] == ["Intent", "Control", "Challenge"], label + " roles")
        builds = {}
        for side, pin in zip(SIDES, pins.groups()):
            require(re.search(rf"^\| {label} \| #{number} \| {side} \| `{pin}`", setup, re.M), label + " build revision")
            row = re.search(rf"^\| {label} \| {side} \| ([^|]+) \|", setup, re.M)
            if row:
                builds[side] = dict(re.findall(r"`([^`]+\.jar)` `([0-9a-f]{64})`", row[1]))
        if label != "S16":
            require(all(builds.get(side) for side in SIDES), label + " missing original artifacts")
        cases[label] = dict(pr=int(number), title=title, revisions=dict(zip(SIDES, pins.groups())),
                            questions=questions, builds=builds)
    require(len(cases) == 50 and len({c["pr"] for c in cases.values()}) == 50, "incomplete Spring Boot cohort")
    return cases


def observations(folder, case, replay):
    plan = public_comparison.comparison_plan(folder)
    spec = public_comparison.read(folder / "comparison.json")
    runtime = public_comparison.read(folder / "runtime.json")
    require(spec["revisions"] == case["revisions"], folder.name + " revision mismatch")
    require(spec["source"] == f"https://github.com/spring-projects/spring-boot/pull/{case['pr']}", folder.name + " PR")
    require(len(set(plan["questions"])) == len(plan["questions"]), folder.name + " duplicate claim")
    for q in spec["questions"]:
        require(all(q[k] == v for k, v in case["questions"][q["id"]].items()), q["id"] + " differs from brief")
    result = public_comparison.replay(folder, authored=True) if replay else public_comparison.read(folder / "observations.json")
    require(result["comparisonSha256"] == digest(folder / "comparison.json") and
            result["runtimeSha256"] == digest(folder / "runtime.json"), folder.name + " stale registrations")
    require(result["launcherSha256"] == digest(public_comparison.upgrade_replay.LAUNCHER), folder.name + " launcher")
    for name, sha in result["inputs"].items():
        require(digest(folder / name) == sha, folder.name + " input mismatch " + name)
    require(set(runtime["deployments"]) == set(result["deployments"]) == {"pins"}, folder.name + " deployment")
    deploy = runtime["deployments"]["pins"]
    require(deploy.get("compileAgainst") == "parent" and not deploy.get("compilePerSide"), folder.name + " compile side")
    for side in SIDES:
        cp = deploy["classpath"][side]
        for index in set(deploy["providers"].values()):
            path = cp[index]
            require(runtime["sha256"][path] == case["builds"][side][Path(path).name], folder.name + " original provider")
    evidence = result["deployments"]["pins"]
    require("PublicCaller.class" in evidence["callerClasses"], folder.name + " compiled caller")
    rows = {(r["id"], r["side"]): r for r in evidence["observations"]}
    expected_keys = {(q["id"], s) for q in spec["questions"] for s in SIDES if s not in q.get("omit", {})}
    require(len(rows) == len(evidence["observations"]) and set(rows) == expected_keys, folder.name + " incomplete observations")
    summaries = {}
    for q in spec["questions"]:
        results = {}
        for side in SIDES:
            if (q["id"], side) not in rows:
                continue
            row = rows[q["id"], side]
            prediction = q["expected"].get(side)
            verdict = "observed only" if prediction is None else (
                "matched" if public_comparison.agrees(prediction, row["outcome"]) else "refuted")
            require(row["prediction"] == verdict, q["id"] + " verdict differs")
            results[side] = dict(outcome=row["outcome"], verdict=verdict)
        summaries[q["id"]] = results
    return summaries


def audit(replay=False):
    cases = inventory()
    counts = Counter()
    rows = []
    for case_id, case in cases.items():
        number = int(case_id[1:]) + 587
        folders = list((ROOT / "examples").glob(f"{number}-*/comparison.json"))
        require(len(folders) <= 1, f"duplicate example {number}")
        qids = list(case["questions"])
        row = dict(case=case_id, pr=case["pr"], revisions=case["revisions"], questions=qids)
        measured = {}
        if folders:
            folder = folders[0].parent
            measured = observations(folder, case, replay)
            row.update(example=folder.name, observations=measured)
        row["unmeasured"] = [q for q in qids if q not in measured]
        counts["registeredClaims"] += len(qids)
        counts["casesWithPublicCallers"] += bool(measured)
        counts["twoSidedPublicClaims"] += sum(set(r) == set(SIDES) for r in measured.values())
        counts["unmeasuredClaims"] += len(row["unmeasured"])
        for r in measured.values():
            counts["jvmObservations"] += len(r)
            for side, evidence in r.items():
                counts[f"{side} {evidence['verdict']}"] += 1
        rows.append(row)
    return {"schema": "spring-boot-public-audit/v1", "cases": rows, "totals": dict(counts)}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replay", action="store_true", help="also run the numbered callers on their original JVM deployments")
    p.add_argument("--record", action="store_true", help="write the audit computed from the current evidence")
    args = p.parse_args()
    data = audit(args.replay)
    output = HERE / "audit.json"
    if args.record:
        output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    else:
        require(data == json.loads(output.read_text()), "committed audit differs")
    print(json.dumps(data["totals"], sort_keys=True))
