#!/usr/bin/env python3
"""The runtime stream's vertical slices (R5 and R2 of llm-dlc/loops/example-targets-runtime.md): a small upstream
method taken through acquisition, preparation, a driver in its own JVM per revision and JDK, and the raw execution
records handed to workflow's ingestion interface. Two cases, each a folder of its own with a sidecar, an adapter, a
driver and a Javadoc-derived oracle:
- `simplematch` (runtime_simplematch/, R5): `PatternMatchUtils.simpleMatch(String, String)` from the published
  spring-core 5.3.18 and 5.3.19 JARs, each pinned by sha256 with its one compile dependency;
- `numbers` (runtime_numbers/, R2's upstream-build route): `ArithmeticUtils.pow(int, int)` from apache/commons-numbers
  at example 105's two pinned commits, each fetched from github.com and built by its own Maven on JDK 11. A pipeline
  job: an upstream build is never run inline.
- `simplematch-mutant` (runtime_simplematch's `mutant-replay` task, a constructed mutant on the published-artifact route):
  5.3.19 against a copy of its JAR whose PatternMatchUtils is recompiled from the v5.3.19 commit's source, patched so
  a "*xxx" pattern matches anywhere. A pipeline job: it checks out spring-framework's commit from github.com.

    python3 examples/tools/targets/runtime_slice.py ATTEMPT [--offline] [--case simplematch|numbers|simplematch-mutant]

ATTEMPT is a new directory, laid out as route.py lays out an attempt (prepare/<revision>, controls). The case folder
is copied to ATTEMPT/case first and planned from there, so its receipts go where route.py puts them, under the
example's folder (`receipts/<task>`), without writing into the repository's copy.
--offline uses only what the acquisition cache already holds (the plan's `network: false`; an upstream build needs
the network). Exit 0 when every revision is artifacts-ready, every control exited with complete observations, the
oracle's disagreements on each revision are exactly the case's expected ones (none for simplematch; for numbers, before
at pow(-2, 31) alone and after none; for simplematch-mutant, the mutant at the three probes its suffix branch decides
and 5.3.19 none), and JDK 21 and 25 agree on each revision; 1 otherwise. ATTEMPT/slice.json says
what happened.

Two stand-ins, both until the workflow stream's work is merged: `plan()` turns the sidecar into the TaskPlan that
workflow's `plan_task` (W1, still Phase 0's stub) is asked under Progress to produce for a published revision, and the
records are handed to `workflow.ingest` as route.py hands them, which answers Unsupported until W2. Reading the oracle
here is the slice's own check of its conformance controls: no claim is decided, and ingestion is what will judge
records in the route.
"""

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if __name__ == "__main__":
    sys.path.insert(0, str(HERE.parent))
from targets import interfaces, runtime, workflow  # noqa: E402
from targets.interfaces import Unsupported  # noqa: E402

FOLDER = HERE / "runtime_simplematch"
EXAMPLE = "315"  # reserved by the runtime stream (315-319) for this slice; the folder is not in the router
# Each case: its folder, the number its plan uses (the runtime stream's 315-319; neither folder is in the router), and
# the probes on which each revision is expected to disagree with the oracle (the history's recorded change).
CASES = {
    "simplematch": {"folder": FOLDER, "example": EXAMPLE, "expected": {}},
    "numbers": {"folder": HERE / "runtime_numbers", "example": "316", "expected": {"before": [[-2, 31]]}},
    # the sidecar's constructed mutant of 5.3.19 against 5.3.19 itself; the disagreements are the ones a model of
    # the patched method predicts on the oracle's probes (a note: the job's replay is the evidence)
    "simplematch-mutant": {"folder": FOLDER, "example": EXAMPLE, "task": "mutant-replay",
                           "expected": {"mutant": [["*bc", "bcx"], ["a*c*e", "abced"], ["*a*b", "acba"]]}},
}


def plan(folder=FOLDER, task="replay", network=True, example=EXAMPLE):
    """The TaskPlan of `task` from the sidecar in `folder`, in the shape workflow's W1 `artifact_sources` gives on its
    branch. A published revision's entry carries its commit and tag, and its `preparation.artifacts` items as
    `published`, in order (the original JAR, then its dependencies), with the keys of a lone item copied up; an
    upstream-build revision's carries its commit, its recorded parent and the recipe's `build`."""
    folder = Path(folder)
    target = json.loads((folder / "target.json").read_text())
    t = next(x for x in target["tasks"] if x["id"] == task)
    history, prep = target["history"], target["preparation"]
    if t.get("pair"):
        pair = next(p for p in history.get("pairs", []) if p["name"] == t["pair"])
        revisions = (pair["before"], pair["after"])
    else:
        revisions = (t["revision"],)
    artifacts = []
    for name in revisions:
        revision = history["revisions"][name]
        if "mutant" in revision:  # W1: the base's commit (and published JARs) under `mutant.base`, nothing of its own
            m = revision["mutant"]
            base = {"revision": m["base"], "commit": history["revisions"][m["base"]]["commit"]}
            if prep["route"] == "published-artifact":
                base["published"] = [{k: a[k] for k in ("coordinates", "url", "sha256") if k in a}
                                     for a in prep.get("artifacts", []) if a["revision"] == m["base"]]
            entry = {"revision": name, "route": prep["route"], "repository": history["repository"],
                     "mutant": {"base": base, "patch": {"path": m["patch"], "sha256": m["sha256"]},
                                "description": m["description"]}}
            if prep["route"] == "upstream-build":
                entry["build"] = prep["build"]
            entry.update(adapters=list(prep.get("adapters", [])), jdks=list(prep.get("jdks", [])))
            artifacts.append(entry)
            continue
        items = [{k: a[k] for k in ("coordinates", "url", "sha256") if k in a}
                 for a in prep.get("artifacts", []) if a["revision"] == name]
        entry = {"revision": name, "route": prep["route"], "repository": history["repository"],
                 "commit": revision.get("commit"), **{k: revision[k] for k in ("tag", "release") if k in revision}}
        if prep["route"] == "published-artifact":
            entry.update(published=items, **(items[0] if len(items) == 1 else {}))
        if prep["route"] == "upstream-build":
            entry.update(build=prep["build"], **({"parent": revision["parent"]} if "parent" in revision else {}))
        entry.update(adapters=list(prep.get("adapters", [])), jdks=list(prep.get("jdks", [])))
        artifacts.append(entry)
    return interfaces.TaskPlan(
        example=example, task=task, kind=t["kind"], relation=t["relation"], target=t["target"], revisions=revisions,
        claim={"task": task, "notes": list(t.get("notes", []))}, prerequisites=tuple(t.get("requires", ())),
        artifacts=tuple(artifacts), tools={"required": ["java", "javac"], "optional": []}, engine=t.get("engine"),
        gaps=t.get("gaps"), expected=t.get("expected"), outputs={"receipts": f"receipts/{task}"}, folder=str(folder),
        network=network)


def _oracle(path):
    spec = importlib.util.spec_from_file_location("runtime_slice_oracle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case_copy(folder, dest):
    """A copy of the case folder `folder` at `dest` (new), links kept as links and no byte caches, to plan from: the
    lock hashes every selected file, and ingestion publishes receipts under the plan's folder, as route.run asks it
    to (the integration report of 2026-11-14 17:13), so a run never writes into the repository's case folder."""
    shutil.copytree(folder, dest, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "receipts"))
    return Path(dest)


def receipts(p):
    """Where route.run has ingestion publish an attempt's receipt: under the example's folder."""
    return Path(p.folder) / p.outputs.get("receipts", f"receipts/{p.task}")


def run(attempt, network=True, folder=None, case="simplematch"):
    """The slice of `case` (its own folder, unless `folder` names another) in a new directory `attempt`: a summary
    dict (also attempt/slice.json), with `ok`."""
    attempt = Path(attempt)
    attempt.mkdir(parents=True, exist_ok=False)
    spec = CASES[case]
    source = Path(folder) if folder else spec["folder"]
    folder = case_copy(source, attempt / "case")
    p = plan(folder, task=spec.get("task", "replay"), network=network, example=spec["example"])
    prepared, preparations = {}, []
    for revision in p.revisions:
        r = runtime.prepare(p, revision, attempt / "prepare" / revision)
        if isinstance(r, Unsupported):
            preparations.append({"revision": revision, "unsupported": r.describe()})
            continue
        prepared[revision] = r
        preparations.append({"revision": revision, "stage": r.stage, "commit": r.commit,
                             "failedStage": r.failedStage, "diagnostic": r.diagnostic,
                             "blocker": r.blocker,
                             "classpath": [{"path": a.path, "role": a.role, "sha256": a.sha256, "origin": a.origin}
                                           for a in r.artifacts if a.path in r.classpath],
                             "target": r.source.get("target"), "checkout": r.source.get("checkout"),
                             "built": r.source.get("built"), "mutant": r.source.get("mutant"),
                             "mutantBuild": r.toolchain.get("mutant"),
                             "upstream": {k: v for k, v in (r.toolchain.get("upstream") or {}).items()
                                          if k in ("jdk", "maven", "wrapper", "argv", "resolution")}})
    records = runtime.run_controls(p, prepared, attempt / "controls")
    if isinstance(records, Unsupported):
        records_out, records = [{"unsupported": records.describe()}], ()
    else:
        records_out = []
    oracle = _oracle(Path(folder) / "oracle.py")
    by_revision = {}
    for record in records:
        entry = {"revision": record.revision, "jdk": record.identities.get("jdkFeature") or record.identities.get("feature"),
                 "status": record.status, "exitCode": record.exitCode,
                 "observations": None if record.observations is None else len(record.observations),
                 "replay": record.identities.get("replay"), "stdout": record.stdout}
        if record.observations is not None:
            try:
                entry["problems"] = [[probe, why] for probe, why in
                                     oracle.check([json.dumps(o) for o in record.observations])]
            except (ValueError, KeyError) as e:
                entry["problems"] = None
                entry["unreadable"] = str(e)
            by_revision.setdefault(record.revision, []).append(
                [(json.dumps(o["input"]), o["outcome"], o.get("value"), o.get("exception")) for o in record.observations])
        records_out.append(entry)
    agreement = {r: all(obs == runs[0] for obs in runs[1:]) for r, runs in by_revision.items()}
    # The call route.py makes once the controls have run (a replay task runs no verifier).
    receipt = workflow.ingest(p, prepared, tuple(records), receipts(p))
    ingestion = {"records": len(records), "result": receipt.describe() if isinstance(receipt, Unsupported)
                 else interfaces.to_dict(receipt)}
    expected_records = sum(len(a.get("jdks") or [None]) for a in p.artifacts)
    expected = {r: sorted(json.dumps(x) for x in spec["expected"].get(r, [])) for r in p.revisions}
    ok = (all(x.get("stage") == "artifacts-ready" for x in preparations)
          and len(records_out) == expected_records
          and all(x.get("status") == "exited" and x.get("exitCode") == 0 and x.get("problems") is not None
                  and sorted(json.dumps(probe) for probe, _ in x["problems"]) == expected[x["revision"]]
                  for x in records_out)
          and all(agreement.get(r) for r in p.revisions))
    titles = {"simplematch": "runtime R5: PatternMatchUtils.simpleMatch, published spring-core",
              "numbers": "runtime R2: ArithmeticUtils.pow, commons-numbers built from its pinned commits",
              "simplematch-mutant": "runtime R2: a constructed mutant of published spring-core 5.3.19's simpleMatch"}
    summary = {"slice": titles[case], "case": case, "caseFolder": {"from": str(source), "copy": str(folder)}, "ok": ok, "expectedProblems": expected,
               "network": network, "plan": p.as_dict(), "preparations": preparations, "records": records_out,
               "jdksAgree": agreement, "ingestion": ingestion,
               "reading": "the oracle's reading is the slice's conformance check, not a claim's result; ingestion "
                          "judges records in the route"}
    (attempt / "slice.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("attempt", type=Path)
    parser.add_argument("--offline", action="store_true", help="use only the acquisition cache")
    parser.add_argument("--case", choices=sorted(CASES), default="simplematch")
    args = parser.parse_args(argv)
    summary = run(args.attempt, network=not args.offline, case=args.case)
    for x in summary["preparations"]:
        print(f"prepare {x['revision']}: {x.get('stage') or x.get('unsupported')}"
              + (f" ({x['failedStage']}: {x['diagnostic']})" if x.get("failedStage") else ""))
    for x in summary["records"]:
        print(f"control {x.get('revision')} jdk{x.get('jdk')}: {x.get('status')} exit {x.get('exitCode')}, "
              f"{x.get('observations')} observations, oracle problems {x.get('problems')}")
    print(f"expected disagreements: {summary['expectedProblems']}")
    print(f"JDKs agree: {summary['jdksAgree']}; ingestion got {summary['ingestion']['records']} records: "
          f"{summary['ingestion']['result']}")
    print("ok" if summary["ok"] else "NOT ok", f"({args.attempt / 'slice.json'})")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
