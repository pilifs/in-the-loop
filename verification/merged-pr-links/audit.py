"""Check coverage of the merged-PR brief, source pins, input digests and every finite JVM prediction."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import public_comparison as comparison


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(replay=False):
    brief = ROOT / "llm-dlc/loops/organic-java-merged-pr-links-brief.md"
    setup = brief.with_name(brief.stem + "-setup.md").read_text()
    references = {}
    for section in brief.read_text().split("\n## "):
        link = re.search(r"https://github.com/([\w.-]+/[\w.-]+)/compare/([0-9a-f]{40})\.{3}([0-9a-f]{40})", section)
        if not link:
            continue
        repo, parent, fix = link.groups()
        questions = {}
        for line in section.splitlines():
            if line.startswith("| ") and " · " in line:
                label, history, prediction, basis, _ = [s.strip() for s in line.strip("|").split(" | ")]
                question, role = label.split(" · ")
                questions[question] = (role, history, prediction, basis)
        key = next(iter(questions)).rsplit(".", 1)[0]
        require(key not in references, f"duplicate case {key}")
        references[key] = ({"parent": parent, "fix": fix}, questions)
    folders = {}
    for folder in (ROOT / "examples").glob("[0-9][0-9][0-9]-*/comparison.json"):
        spec = comparison.read(folder)
        key = spec["questions"][0]["id"].rsplit(".", 1)[0]
        if key in references:
            require(key not in folders, f"duplicate example {key}")
            folders[key] = folder.parent
    require(set(references) == set(folders), f"uncovered cases {references.keys() - folders.keys()}")
    result = {"cases": [], "totals": {}}
    counters = Counter()
    for number, (case, (pins, questions)) in enumerate(references.items(), 1):
        folder = folders[case]
        prefix = f"{folder.name}: "
        plan = comparison.comparison_plan(folder)
        spec = comparison.read(folder / "comparison.json")
        runtime = comparison.read(folder / "runtime.json")
        recorded = comparison.read(folder / "observations.json")
        ex = comparison.read(folder / "example.json")
        repo, pr = case.split("#")
        require(spec["source"] == ex["source"]["url"] == f"https://github.com/{repo}/pull/{pr}", prefix + "source")
        require(plan["revisions"] == pins and plan["questions"] == list(questions), prefix + "pins or question order")
        require(recorded["schema"] == "public-observations/v1", prefix + "record format")
        for key, path in [("comparisonSha256", folder / "comparison.json"), ("runtimeSha256", folder / "runtime.json"),
                          ("launcherSha256", comparison.upgrade_replay.LAUNCHER)]:
            require(comparison.upgrade_replay.sha(path) == recorded[key], prefix + key)
        sources = sorted((folder / "caller").rglob("*.java"))
        fixtures = [p for p in (folder / "fixtures").rglob("*") if p.is_file()]
        require(recorded["inputs"] == {p.relative_to(folder).as_posix(): comparison.upgrade_replay.sha(p)
                                       for p in sources + fixtures}, prefix + "caller or fixtures")
        require(runtime["deployments"].keys() == recorded["deployments"].keys(), prefix + "deployment names")
        evidence = {q: {} for q in questions}
        used_files = set()
        setup_section = setup.split(f"\n### M{number:02} · ", 1)[1].split("\n### M", 1)[0]
        for variant, deployment in runtime["deployments"].items():
            result_rows = recorded["deployments"][variant]
            require("PublicCaller.class" in result_rows["callerClasses"], prefix + "compiled caller absent")
            for side, files in deployment["classpath"].items():
                used_files.update(files)
                require(len(files) == len(set(files)), prefix + "duplicate classpath entry")
                for f in files:
                    digest = runtime["sha256"][f]
                    require(re.fullmatch("[0-9a-f]{64}", digest), prefix + "artifact digest")
                    if f.startswith("artifacts/"):
                        require(digest in setup_section, prefix + f"{side} {f} absent from pin-build record")
                require(any(files[i].startswith("artifacts/") for i in deployment["providers"].values()),
                        prefix + "no pin-built provider")
            expected_keys = [(s, q["id"]) for s in comparison.SIDES for q in spec["questions"]
                             if s not in q.get("omit", {})]
            require([(r["side"], r["id"]) for r in result_rows["observations"]] == expected_keys,
                    prefix + "missing, duplicated or extra observations")
            for q in spec["questions"]:
                key = q["id"]
                require(tuple(q[k] for k in ("role", "history", "prediction", "basis")) == questions[key], prefix + key)
                by_side = {}
                for row in (r for r in result_rows["observations"] if r["id"] == key):
                    side, actual = row["side"], row["outcome"]
                    require(set(actual) in ({"throws"}, {"return"}), prefix + "ambiguous observation")
                    pred = q["expected"].get(side)
                    expected = ("observed only" if pred is None else
                                "matched" if comparison.agrees(pred, actual) else "refuted")
                    require(expected == row["prediction"], prefix + key + " decision disagrees with observation")
                    by_side[side] = {"prediction": expected, "outcome": actual}
                evidence[key][variant] = by_side
            counters["freshJvms"] += len(expected_keys)
            counters["deploymentPairs"] += 1
        require(used_files == runtime["sha256"].keys(), prefix + "unused or missing runtime digest")
        refuted = [key for key, variants in evidence.items()
                   if any(sides["fix"]["prediction"] == "refuted" for sides in variants.values())]
        paired = all(all("parent" in sides for sides in evidence[key].values()) for key in questions)
        intent = next(key for key, desc in questions.items() if desc[0] == "Intent")
        different = all("parent" in sides and sides["parent"]["outcome"] != sides["fix"]["outcome"]
                        for sides in evidence[intent].values())
        controls = [key for key, desc in questions.items() if desc[0] == "Control"]
        def matched_on_fix(key):
            return all(sides["fix"]["prediction"] == "matched" for sides in evidence[key].values())
        unchanged = sum(all(set(sides) == set(comparison.SIDES) and
                            sides["parent"]["outcome"] == sides["fix"]["outcome"] and
                            all(r["prediction"] == "matched" for r in sides.values())
                            for sides in evidence[key].values()) for key in controls)
        counters.update(cases=1, questions=len(questions), fixedRefutations=len(refuted),
                        fixedPredictionsMatched=sum(map(matched_on_fix, questions)), fixedIntentsMatched=int(matched_on_fix(intent)),
                        pairedIntentChanges=int(different), unchangedControls=unchanged,
                        omittedParentHistories=sum("parent" in q.get("omit", {}) for q in spec["questions"]))
        result["cases"].append({"example": ex["id"], "case": case, "observationsSha256": comparison.upgrade_replay.sha(folder / "observations.json"),
                                "deployments": list(runtime["deployments"]), "allHistoriesPaired": paired, "fixedRefutations": refuted})
        for receipt in sorted(Path(__file__).with_name("entry-receipts").glob(ex["id"] + "-*.json")):
            qualified = comparison.read(receipt)
            variant = receipt.stem.split("-", 1)[1]
            deployment = runtime["deployments"][variant]
            classes = recorded["deployments"][variant]["callerClasses"]
            require(qualified["probeSha256"] == comparison.upgrade_replay.sha(Path(__file__).with_name("UpgradeProbe.java"))
                    and qualified["probeClasses"]["PublicCaller"] == classes["PublicCaller.class"], prefix + "qualified caller")
            indexed = {tuple(q["args"]): q["id"] for q in spec["questions"]}
            for side, label in (("parent", "old"), ("fix", "new")):
                original = qualified["sides"][label]
                require(original["commit"] == pins[side] and
                        original["classpath"] == [runtime["sha256"][f] for f in deployment["classpath"][side]],
                        prefix + "qualified deployment")
                for case_input, trial in zip(qualified["cases"], original["trials"], strict=True):
                    q = indexed[tuple(case_input["args"])]
                    expected = evidence[q][variant][side]["outcome"]
                    require(trial["qualifiedMethodEntries"] == 2 and trial["observations"] == [expected] * 2,
                            prefix + "qualified entry or observation")
                    counters["retainedMethodEntryTrials"] += 2
        if replay:
            comparison.replay(folder)
    result["totals"] = dict(counters)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", action="store_true", help="also rebuild every caller and repeat the physical trials")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.replay)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["totals"], sort_keys=True))
