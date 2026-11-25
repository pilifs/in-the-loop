"""Qualify control and counterexample observations at original JVM method entries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import public_comparison, upgrade_replay


ENTRIES = {
    "409": ("M07-jackson-dataformats-text", "csv/src/main/java",
            "tools.jackson.dataformat.csv.CsvParser#nextToken()Ltools/jackson/core/JsonToken;"),
    "411": ("M09-avro", "lang/java/idl/src/main/java",
            "org.apache.avro.idl.IdlUtils#writeIdlSchema(Ljava/io/Writer;Lorg/apache/avro/Schema;)V"),
    "412": ("M10-ical4j", "src/main/java",
            "net.fortuna.ical4j.model.ComponentGroup#calculateRecurrenceSet(Lnet/fortuna/ical4j/model/Period;)Ljava/util/List;"),
    "419": ("M17-jOOL", "jOOL/src/main/java", "org.jooq.lambda.WindowImpl#lastValue()Ljava/util/Optional;"),
    "425": ("L03-picocli", "src/main/java",
            "picocli.CommandLine$Model$CommandSpec#aliases([Ljava/lang/String;)Lpicocli/CommandLine$Model$CommandSpec;"),
    "429": ("L07-jgrapht", "jgrapht-core/src/main/java",
            "org.jgrapht.alg.shortestpath.BaseKDisjointShortestPathsAlgorithm#getPaths(Ljava/lang/Object;Ljava/lang/Object;I)Ljava/util/List;"),
    "430": ("L08-commons-statistics", "commons-statistics-distribution/src/main/java",
            "org.apache.commons.statistics.distribution.CauchyDistribution#inverseCumulativeProbability(D)D"),
}


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2) + "\n")


def qualify(number, output, only=None):
    folder, = (ROOT / "examples").glob(number + "-*")
    spec = public_comparison.read(folder / "comparison.json")
    runtime = public_comparison.read(folder / "runtime.json")
    physical = public_comparison.read(folder / "observations.json")
    source = folder / "caller/PublicCaller.java"
    if (physical["inputs"]["caller/PublicCaller.java"] != upgrade_replay.sha(source)
            or physical["runtimeSha256"] != upgrade_replay.sha(folder / "runtime.json")
            or physical["comparisonSha256"] != upgrade_replay.sha(folder / "comparison.json")):
        raise ValueError("physical receipt differs from the registered caller or deployment")
    cache = Path(os.environ.get("PUBLIC_COMPARISON_CACHE", Path.home() / ".cache/in-the-loop" / runtime["cache"]))
    jdk = Path(os.environ.get("PUBLIC_COMPARISON_JDK", Path.home() / ".sdkman/candidates/java" / runtime["jdk"]))
    if upgrade_replay.sha(jdk / "release") != runtime["jdkReleaseSha256"]:
        raise ValueError("registered JVM differs")
    project, roots, entry = ENTRIES[number]
    output.mkdir(parents=True, exist_ok=True)
    for variant, deployment in runtime["deployments"].items():
        measured = {(r["side"], r["id"]): r["outcome"] for r in physical["deployments"][variant]["observations"]}
        questions = [r for r in spec["questions"] if r["role"] in ("Control", "Challenge")
                     and (only is None or r["role"] == only)]
        with tempfile.TemporaryDirectory(prefix="qualified-public-") as t:
            work = Path(t)
            manifests, deps = [], []
            for side in public_comparison.SIDES:
                pin = spec["revisions"][side]
                checkout = cache / "worktrees" / (project + "-" + side)
                source_path = "jOOL-java-8/src/main/java" if variant == "jool-java-8" else roots
                tree = subprocess.check_output(["git", "-C", checkout, "ls-tree", "-rz", pin, "--", source_path])
                if not tree:
                    raise ValueError("missing original sources at " + pin)
                cp = [{"file": str(cache / name), "sha256": runtime["sha256"][name]}
                      for name in deployment["classpath"][side]]
                manifest = work / (side + ".json")
                write(manifest, {"commit": pin, "sourceSha256": hashlib.sha256(tree).hexdigest(), "classpath": cp})
                manifests.append(manifest)
                deps.append(cp[0]["sha256"])
            scope = {"entry": entry, "probeClass": "UpgradeProbe",
                     "invocationVia": "PublicCaller#observe([Ljava/lang/String;)Ljava/lang/String;",
                     "observer": "Same public observer as the physical receipt, with an original-method breakpoint.",
                     "basis": "Cross-check the previously measured typed returns on both revisions against two independent debugger trials.",
                     "fixtures": [{"kind":"java", "class":"PublicCaller", "file":source.name, "sha256":upgrade_replay.sha(source)}],
                     "cases": [{"args": r["args"], "expected": measured["parent", r["id"]]} for r in questions]}
            scope_path = work / "scope.json"
            write(scope_path, scope)
            report = upgrade_replay.evaluate(scope_path, *manifests, Path(__file__).with_name("UpgradeProbe.java"),
                    jdk, deps, 180, fixtures=source.parent, application_change=True)
            file = output / (number + "-" + variant + ".json")
            write(file, report)
            if report["status"] not in ("preserved", "changed"):
                raise ValueError(f"{number} {variant}: {report.get('reason', 'qualified replay open')}")
            for side, label in (("parent", "old"), ("fix", "new")):
                for q, trial in zip(questions, report["sides"][label]["trials"], strict=True):
                    if trial["qualifiedMethodEntries"] != 2 or trial["observations"] != [measured[side, q["id"]]] * 2:
                        raise ValueError(f"{number} {side}: original entry or its observation differs for {q['id']}")
            print(number, variant, entry, len(questions) * 4, "qualified JVM trials", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("examples", nargs="+", choices=ENTRIES)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--only", choices=("Control", "Challenge"))
    args = parser.parse_args()
    for example in args.examples:
        qualify(example, args.output, args.only)
