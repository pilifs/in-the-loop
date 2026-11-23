"""Recheck Commons Lang #1635 on the frozen adapter and each original production jar."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile

from campaign import JDK, ROOT, command, compile_java, digest, integrated, javaenv, measure as measure_subject, write
from direct_arrays import check_run, unchanged_inputs
from historical import GROUPS, measure as measure_history
from subjects import CLAIMS, Claim, Subject, unary

sys.path.insert(0, str(ROOT / "lib/benchmark/spring-java-data"))
from measure import measure, read, seed
from public_selectors import run as selectors
from targets import recipes, route, runtime, sidecar

FOLDER = ROOT / "examples/375-commons-lang-decimal-precision"
PHASE = "decimal-transfer"
DEST = ROOT / "verification/java-semantics-gap" / PHASE
EXPECTED = {"precise-parent": "refuted", "preserved-parent": "established",
            "precise-landed": "established", "preserved-landed": "established"}


def ordinary():
    measure("375", PHASE, 120, [])
    selectors("375", 0, [], PHASE + "-selectors", 120)
    for tag in (PHASE, PHASE + "-selectors"):
        report = read(FOLDER / "records" / tag / "run.json")
        actual = {k: v["status"] for k, v in report["tasks"].items()}
        if actual != EXPECTED:
            raise ValueError(f"{tag}: {actual}")
        print(tag, actual, flush=True)


def exact_classes(work, cp, env, rev):
    source = FOLDER / "controls/DecimalRuntime.java"
    classes = work / "runtime-classes"
    compile_java([source], classes, cp, env)
    rc, out, err, _ = command([JDK / "bin/java", "-ea", "-cp", os.pathsep.join(map(str, [classes, *cp])),
                               "DecimalRuntime"], env)
    observations = [line.split("\t") for line in out.decode().splitlines()]
    expected = []
    for case in read(FOLDER / "controls/table.json")["cases"]:
        text, short, _ = case["input"]
        _, coefficient, scale = case["expected"]["precise"]
        (kind, value), error = case["expected"]["preserved"]
        # Both positive long spellings have the same old Float as 0.1; the negative one flips its sign bit.
        old = 0x3dcccccd - ((1 << 31) if text.startswith("-") else 0)
        exact = f"java.math.BigDecimal {coefficient} {scale}" if rev == "landed" else f"java.lang.Float {old}"
        expected.append([str(case["id"]), text, exact, short, f"java.lang.{kind} {value}", error])
    if rc or observations != expected:
        raise ValueError(f"{rev}: different original-JVM runtime classes or values: {observations}, {err[:120]}")
    return {"sourceSha256": digest(source), "classSha256": digest(classes / "DecimalRuntime.class"),
            "stdoutSha256": hashlib.sha256(out).hexdigest(), "rows": observations}


def paired():
    seed(FOLDER)
    example = read(FOLDER / "example.json")
    target = sidecar.load(FOLDER, example)
    env = javaenv()
    binary = Path(env["JVMCONTRACT"]).resolve()
    summary = {"job": env["VERIFY_JOB_ID"], "source": env["VERIFY_SOURCE_COMMIT"],
               "checkerSha256": digest(binary), "libTree": env["JVMCONTRACT_LIB_TREE"],
               "jdkModulesSha256": digest(JDK / "lib/modules"), "javaSha256": digest(JDK / "bin/java"),
               "jbmcSha256": digest(shutil.which("jbmc")), "coreModelsSha256": digest("/usr/lib/core-models.jar"),
               "staging": "staged", "secondsPerClaim": 120, "tasks": {}, "originalJvm": {}}
    with tempfile.TemporaryDirectory(prefix="decimal-transfer-") as tmp:
        work = Path(tmp)
        for rev in ("parent", "landed"):
            plan = route.resolve(FOLDER, example, target, "precise-" + rev)
            prepared = route.prepare_revision(plan, rev, work / rev, None)
            if getattr(prepared, "stage", None) != "artifacts-ready":
                raise ValueError(f"{rev}: original artifacts unavailable")
            where = runtime._preparation_dir(prepared)
            built = {rev: (where, prepared, runtime._checked(where, prepared))}
            for task, expected in EXPECTED.items():
                if not task.endswith("-" + rev):
                    continue
                plan = route.resolve(FOLDER, example, target, task)
                invocation = recipes.translate(plan).bind(plan, binary, built, "paired", 120)
                graph = invocation.classpaths[rev]
                cp = [where / item["path"] for item in graph]
                if [digest(p) for p in cp] != [item["sha256"] for item in graph]:
                    raise ValueError(f"{task}: changed input graph")
                if rev not in summary["originalJvm"]:
                    summary["originalJvm"][rev] = exact_classes(work / rev, cp, env, rev)
                method = plan.claim["property"]
                bounds = plan.claim["bounds"]
                domain = unary(0, 1, 2)
                claim = Claim(method, "int code", plan.claim["assume"],
                              holds=domain if expected == "established" else (),
                              fails=domain if expected == "refuted" else ())
                subject = Subject(375, "datawork.Decimals", rev, (claim,), bounds["maxArrayLength"], bounds["unwind"])
                if invocation.entry != f"{subject.owner}#{method}(I)I" or plan.claim["assert"] != "result == 1":
                    raise ValueError(f"{task}: different entry or assertion")
                results = {}
                for engine in ("native", "jbmc"):
                    scratch = work / task / engine
                    scratch.mkdir(parents=True)
                    raw = DEST / "paired" / task / engine
                    raw.mkdir(parents=True, exist_ok=True)
                    row = integrated(subject, claim, engine, scratch, raw, cp, env, plan.claim["assert"])
                    if engine == "native" and row["disposition"] != "correct":
                        raise ValueError(f"{task}: {row}")
                    row["stdoutSha256"] = digest(raw / "stdout.json")
                    row["stderrSha256"] = digest(raw / "stderr.txt")
                    results[engine] = row
                    print(task, engine, row["disposition"], row["seconds"], flush=True)
                summary["tasks"][task] = {"claimKey": plan.claim["key"], "entry": invocation.entry, "bounds": bounds,
                        "assume": claim.guard, "assert": plan.claim["assert"], "classpath": graph, "runs": results}
    write(DEST / "paired/measurement.json", summary)


def callers():
    for key in CLAIMS:
        report = measure_subject(key, "callers", ["native", "jbmc"], DEST)
        unchanged_inputs(key, report)
        for row in report["runs"]:
            if row["engine"] != "native":
                continue
            if key == "monitors":
                if row["verdict"] != "unverifiable" or "java.lang.Thread.<init>" not in row["firstUnproved"]:
                    raise ValueError(f"{key}: review the changed monitor outcome")
            else:
                check_run(row)


def history():
    for group in GROUPS:
        measure_history(PHASE + "/historical", group)
        report = read(DEST / "historical" / (group + ".json"))
        if any(r["class"] != "correct" for r in report["runs"] if r["engine"] == "native"):
            raise ValueError(f"{group}: historical native regression")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    routes = {"ordinary": ordinary, "paired": paired, "callers": callers, "history": history}
    parser.add_argument("route", choices=routes)
    routes[parser.parse_args().route]()
