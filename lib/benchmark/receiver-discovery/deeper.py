"""Run original-scope native, standalone, JVM and schedule controls for the deeper receiver cases."""

import argparse
from collections import Counter
import gzip
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from callers import ASSETS, JDK, ROOT, RESULTS, read, sha
from investigate import command, native, witness_args, write
from qualification import construct
from standalone import BINARY, MODELS

HERE = Path(__file__).resolve().parent
TYPES = {
    "hex": ("400", "HexClient", "guava-33.4.8-jre"),
    "float": ("401", "FloatHistory", "commons-lang3-3.17.0"),
    "schedule": ("402", "Duty", None),
}
DIGESTS = {
    "hex": "f3d7f57f67fd622f4d468dfdd692b3a5e3909246c28017ac3263405f0fe617ed",
    "float": "6ee731df5c8e5a2976a1ca023b6bb320ea8d3539fbe64c8a1d5cb765127c33b4",
}


def build(case, tmp):
    number, owner, release = TYPES[case]
    (home,) = (ROOT / "examples").glob(number + "-*")
    jars = (
        [
            Path(p)
            for p in (ASSETS / "releases" / release / "classpath.txt").read_text().strip().split(os.pathsep)
        ]
        if release
        else []
    )
    if release and sha(jars[0]) != DIGESTS[case]:
        raise ValueError("release binding: " + case)
    dest = tmp / "classes"
    dest.mkdir()
    command(
        [
            JDK / "bin/javac",
            "--release",
            "8",
            "-g",
            "-parameters",
            "-proc:none",
            "-cp",
            os.pathsep.join(map(str, jars)),
            "-d",
            dest,
            *sorted((home / "original").glob("*.java")),
        ]
    )
    cp = [dest, *jars]
    drivers = tmp / "driver"
    drivers.mkdir()
    command(
        [
            JDK / "bin/javac",
            "-parameters",
            "-g",
            "-proc:none",
            "-cp",
            os.pathsep.join(map(str, cp)),
            "-d",
            drivers,
            *sorted((home / "evaluation").glob("*.java")),
            HERE / "java/CallOnce.java",
        ]
    )
    return home, cp, drivers


def physical(case, cp, drivers):
    if case == "schedule":
        return None
    main = "HexCensus" if case == "hex" else "FloatCensus"
    out = command(
        [JDK / "bin/java", "-ea", "-Xverify:all", "-cp", os.pathsep.join(map(str, [drivers, *cp])), main],
        timeout=90,
    )
    want = (
        "131072 minimum-failures 1 composition [83136, 53862, 208, 51]"
        if case == "hex"
        else "100081 pairs; x=3f800001 y=3f800000 original=34000000 translated=00000000"
    )
    if want not in out:
        raise ValueError(out)
    return out.splitlines()


def string_value(i):
    units = i.get("units", []) if isinstance(i, dict) else None
    if units is not None:
        return ",".join(str(u) for u in units)
    if i is None:
        return "null"
    b = i.encode("utf-16-be", "surrogatepass")
    return ",".join(str(int.from_bytes(b[j : j + 2], "big")) for j in range(0, len(b), 2))


def original_call(cp, drivers, owner, name, row):
    ins = row["counterexample"]["inputs"]
    if any(p["type"] in ("String", "java.lang.String") for p in ins):
        arg = string_value(ins[0]["value"])
        result = command(
            [
                JDK / "bin/java",
                "-ea",
                "-Xverify:all",
                "-cp",
                os.pathsep.join(map(str, [drivers, *cp])),
                "StringReplay",
                owner,
                name,
                arg,
            ]
        ).splitlines()
        shown = [arg]
    else:
        shown = witness_args(row)
        call = row["counterexample"]["call"]
        result = command(
            [
                JDK / "bin/java",
                "-ea",
                "-Xverify:all",
                "-cp",
                os.pathsep.join(map(str, [drivers, *cp])),
                "org.intheloop.observation.CallOnce",
                owner,
                owner,
                name,
                call["descriptor"],
                *shown,
            ]
        ).splitlines()
    if "returned false" not in result and not any(s.startswith("escaped ") for s in result):
        raise ValueError(("native witness disagrees on the original", owner, name, result))
    return {"arguments": shown, "jvm": result}


def native_cases(case, cp, drivers, tmp, checker, stage):
    owner = TYPES[case][1]
    methods = {
        "hex": [
            ("nullReturns", 9, 132),
            ("boxedValue", 9, 132),
            ("rejectsMinimum", 9, 132),
            ("directReached", 9, 132),
            ("composition", 6, 132),
            ("earlyKey", 6, 132),
            ("dropSign", 6, 132),
            ("nullShape", 6, 132),
        ],
        "float": [(s, 8, 16) for s in ("exact", "translated", "afterReturn", "adjacent", "rounded")],
        "schedule": [(s, 8, 6) for s in ("atomic", "split", "atomicTerminal", "splitTerminal")],
    }[case]
    rows = {}
    for name, bound, unwind in methods:
        r = native(checker, cp, owner + "#" + name, None, unwind, bound, 120, tmp / ("native-" + name))
        rows[name] = {
            "verdict": r["verdict"],
            "firstUnproved": r["problem"],
            "receipt": r,
            "bounds": {"unwind": unwind, "maxArrayLength": bound},
        }
        if r["verdict"] == "violation":
            rows[name]["originalReplay"] = original_call(cp, drivers, owner, name, r)
        print(case, name, r["verdict"], str(r["problem"] or "")[:220], flush=True)
    if case == "float":
        generated = tmp / "generated"
        env = dict(os.environ, JAVA_HOME=str(JDK), JVMCONTRACT_JAR_RELEASE="21")
        plans = json.loads(
            command(
                [
                    checker,
                    "construct",
                    "org.apache.commons.lang3.mutable.MutableFloat",
                    "--observer",
                    "FloatHistory#exactOn",
                    "--output",
                    generated,
                    "--classes",
                    cp[0],
                    "--classpath",
                    os.pathsep.join(map(str, cp[1:])),
                    "--fresh-observer-inputs",
                ],
                env=env,
            )
        )
        (history,) = [p for p in plans["plans"] if p["producer"].endswith("MutableFloat#<init>(F)V")]
        if history["descriptor"] != "(FF)Z":
            raise ValueError("the history couples its operands")
        row = native(
            checker, [generated, *cp], history["entry"], None, 16, 8, 120, tmp / "native-constructed"
        )
        rows["constructed"] = {
            "discovery": plans,
            "selected": history,
            "verdict": row["verdict"],
            "firstUnproved": row["problem"],
            "receipt": row,
        }
    return rows


def comparator(case, cp, drivers, tmp, out):
    if (
        sha(BINARY) != "2cf572542163ad3926d0030f4594e4697fcd09a0c60b62dc58901ca3aa18065c"
        or sha(MODELS) != "2a05026b3ab948ebb4820ccc2fc01040b96e226dc1f58a3be36dfe0c15ed14de"
    ):
        raise ValueError("JBMC binding")
    # The assertion wrapper belongs to this case only. Its public arguments are those of the requested property.
    owner = TYPES[case][1]
    method_names = {
        "hex": {
            "hexNull": "nullReturns",
            "hexBoxed": "boxedValue",
            "hexMinimum": "rejectsMinimum",
            "hexReach": "directReached",
        },
        "float": {"exact": "exact", "translated": "translated", "floatReach": "afterReturn"},
    }.get(case, {})
    if method_names:
        formals, actuals = ("String s", "s") if case == "hex" else ("float x,float y", "x,y")
        src = tmp / "DeepAssertions.java"
        text = "public final class DeepAssertions {\n" + "".join(
            f"public static void {m}({formals}) {{assert {owner}.{fn}({actuals});}}\n"
            for m, fn in method_names.items()
        )
        if case == "hex":
            text += 'public static void tilde() {assert com.google.common.primitives.Ints.tryParse("7ffffff~",16)==null;}\n'
        src.write_text(text + "}\n")
        command(
            [
                JDK / "bin/javac",
                "--release",
                "8",
                "-parameters",
                "-g",
                "-cp",
                os.pathsep.join(map(str, cp)),
                "-d",
                drivers,
                src,
            ]
        )
    rows = {}
    methods = {
        "hex": ["hexNull", "hexBoxed", "hexMinimum", "hexReach", "tilde"],
        "float": ["exact", "translated", "floatReach"],
        "schedule": ["atomic", "split", "atomicTerminal", "splitTerminal"],
    }[case]
    for profile in (["packaged", "jdk-arrays"] if case == "hex" else ["packaged"]):
        overlay = ASSETS / "jdk/temurin-21.0.13/classes"
        extra = [overlay] if profile == "jdk-arrays" else []
        if extra and (
            sha(overlay / "java/util/Arrays.class")
            != "4a41d89cb79284298b95303a66b3738955d22694f9b34016d87241d9ae8193ab"
            or list(overlay.rglob("*.class")) != [overlay / "java/util/Arrays.class"]
        ):
            raise ValueError("Arrays overlay is not the original single class")
        for name in methods:
            entry = "Duty" if case == "schedule" else "DeepAssertions"
            flags = [
                "--function",
                entry + "." + name,
                "--unwind",
                str(6 if case == "schedule" else 11),
                "--unwinding-assertions",
                "--throw-runtime-exceptions",
                "--max-nondet-array-length",
                "10",
                "--max-nondet-string-length",
                "9",
                "--trace",
                "--json-ui",
            ]
            if case == "hex":
                flags += [
                    "--unwindset",
                    "java::com.google.common.primitives.Longs$AsciiDigits.<clinit>:()V.1:27,java::java.util.Arrays.fill:([BB)V.0:129",
                ]
            if case == "schedule":
                flags += ["--java-threading"]
            try:
                run = subprocess.run(
                    [BINARY, entry, "-cp", os.pathsep.join(map(str, [drivers, *cp, *extra, MODELS])), *flags],
                    capture_output=True,
                    timeout=150,
                )
            except subprocess.TimeoutExpired:
                rows[profile + "/" + name] = {"status": "timeout", "flags": flags}
                continue
            if run.returncode not in (0, 10):
                raise ValueError((name, run.returncode, run.stderr[-400:], run.stdout[-200:]))
            doc = json.loads(run.stdout)
            props = [p for part in doc for p in part.get("result", [])]
            if not props:
                raise ValueError("missing property report")
            raw = out / (profile + "-" + name + ".json.gz")
            raw.write_bytes(gzip.compress(run.stdout, mtime=0))
            selected = [
                p
                for p in props
                if (p.get("sourceLocation") or {}).get("propertyClass") == "assertion"
                and (
                    (entry == "Duty" and "Duty$Board.commit" in p["property"])
                    or p["property"].startswith("java::" + entry + "." + name + ":")
                )
            ]
            row = {
                "flags": flags,
                "exit": run.returncode,
                "properties": len(props),
                "user": [(p["property"], p["status"]) for p in selected],
                "otherFailures": [
                    (p["property"], p["status"])
                    for p in props
                    if p not in selected and p["status"] != "SUCCESS"
                ],
                "rawSha256": sha(raw),
                "overlay": {str(p.relative_to(overlay)): sha(p) for d in extra for p in d.rglob("*.class")},
            }
            rows[profile + "/" + name] = row
            print(case, profile, name, row["user"], row["otherFailures"][:3], flush=True)
    return rows


def schedule(cp, drivers):
    argv = [
        JDK / "bin/java",
        "-ea",
        "-Xverify:all",
        "-cp",
        os.pathsep.join(map(str, [drivers, *cp])),
        "ScheduleSearch",
    ]
    result = {}
    for split in (False, True):
        mode = "split" if split else "atomic"
        # This enumerator consumes only the protocol. The JVM search consumes actual waiting operations.
        counts = Counter()
        oracle = {}
        for perm in sorted(set(itertools.permutations(([0, 0, 1, 1, 2, 2] if split else [0, 1, 2])))):
            mask = 7
            seen = {}
            commits = 0
            for actor in perm:
                if not split or actor not in seen:
                    decision = bool(mask & (1 << ((actor + 1) % 3)))
                    if split:
                        seen[actor] = decision
                        continue
                else:
                    decision = seen[actor]
                commits += 1
                if decision:
                    mask &= ~(1 << actor)
            oracle["".join(map(str, perm))] = mask
            counts[mask == 0] += 1
        for force in (False, True):
            args = [*argv, mode, str(force).lower()]
            lines = command(args, timeout=90).splitlines()
            measured = {}
            for line in lines:
                order, mask, commits, failures, events = line.split(" ", 4)
                if (
                    order in measured
                    or int(commits) != 3
                    or int(mask) != oracle[order]
                    or int(failures) != int(force or int(mask) == 0)
                ):
                    raise ValueError(line)
                measured[order] = {"mask": int(mask), "failures": int(failures), "events": events.split(";")}
            if measured.keys() != oracle.keys():
                raise ValueError("incomplete schedule coverage")
            failing = next((k for k, v in measured.items() if v["failures"]), None)
            repeated = command([*args, failing], timeout=30).strip() if failing else None
            if repeated and repeated not in lines:
                raise ValueError("fresh schedule replay differs")
            result[mode + ("-terminal" if force else "")] = {
                "orders": len(oracle),
                "zero": counts[True],
                "nonzero": counts[False],
                "histories": measured,
                "witness": failing,
                "freshReplay": repeated,
            }
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("case", choices=TYPES)
    ap.add_argument("route", choices=("native", "standalone", "schedules"))
    ap.add_argument("--stage", default="opening")
    args = ap.parse_args()
    dest = RESULTS / "deeper" / args.stage / args.case / args.route
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        home, cp, drivers = build(args.case, tmp)
        checker = Path(os.environ["JVMCONTRACT"]).resolve() if args.route == "native" else None
        data = {
            "schema": "receiver-deep-case/v1",
            "job": os.environ["VERIFY_JOB_ID"],
            "source": os.environ["VERIFY_SOURCE_COMMIT"],
            "classes": {p.relative_to(cp[0]).as_posix(): sha(p) for p in cp[0].rglob("*.class")},
            "jars": [{"name": p.name, "sha256": sha(p)} for p in cp[1:]],
            "jdkModules": sha(JDK / "lib/modules"),
            "originalJvm": physical(args.case, cp, drivers),
        }
        if args.route == "native":
            data.update(
                checker=sha(checker), results=native_cases(args.case, cp, drivers, tmp, checker, args.stage)
            )
        elif args.route == "standalone":
            data.update(
                jbmc=sha(BINARY),
                coreModels=sha(MODELS),
                results=comparator(args.case, cp, drivers, tmp, dest),
            )
        else:
            data["results"] = schedule(cp, drivers)
        write(dest / "measurement.json", data)
