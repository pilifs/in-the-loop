"""Qualify the first three investigation cases on frozen input classes and original JVM witnesses."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from callers import ROOT, RESULTS, JDK, read, sha
from investigate import command, compiler, inventory, investigate, native, original, witness_args, write

HERE = Path(__file__).resolve().parent
FIXTURES = {n: next((ROOT / "examples").glob(n + "-*")) for n in ("397", "398", "366")}
PINS = HERE / "selections.json"


def compile_original(n, variant, folder):
    folder.mkdir(parents=True, exist_ok=True)
    command(
        [
            JDK / "bin/javac",
            "-proc:none",
            "-parameters",
            "-g",
            "-d",
            folder,
            *sorted((FIXTURES[n] / variant).glob("*.java")),
        ]
    )
    return [folder]


def csv(side, where):
    sys.path.insert(0, str(ROOT / "examples/tools"))
    from targets import route, runtime

    folder = FIXTURES["366"]
    plan = route.resolve(
        folder, read(folder / "example.json"), read(folder / "target.json"), "fields-" + side
    )
    ready = route.prepare_revision(plan, side, where, {})
    entries = runtime._checked(where, ready)
    cp = [where / a.path for role in ("adapter", "original", "dependency") for a in entries if a.role == role]
    if not cp:
        raise ValueError("no prepared CSV classpath")
    return cp


def bind(checker):
    data = {}
    with tempfile.TemporaryDirectory() as temp:
        tmp = Path(temp)
        for key in ("original", "guard", "helper", "stock", "csv-parent", "csv-fix"):
            if key.startswith("csv"):
                cp = csv(key[4:], tmp / key)
                members = ["campaign.DelimitedFields#matches"]
            else:
                cp = compile_original(
                    "397" if key == "stock" else "398", "original" if key == "stock" else key, tmp / key
                )
                members = ["Checkout$Stock#take"] if key == "stock" else ["SafetySites#run"]
                if key == "helper":
                    members.append("SafetySites#divide")
            data[key] = {}
            for m in members:
                inv = inventory(checker, cp, m)
                data[key][m] = {
                    "sha256": inv["binding"]["sha256"],
                    "method": inv["method"],
                    "descriptor": inv["descriptor"],
                    "sites": inv["sites"],
                }
    return data


def construct(checker, receiver, observer, cp, dest):
    args = [s for p in cp for s in ("--classes", p)]
    return json.loads(
        command(
            [checker, "construct", receiver, "--observer", observer, "--output", dest, *args],
            env=dict(os.environ, JAVA_HOME=str(JDK), JVMCONTRACT_JAR_RELEASE="21"),
        )
    )


def jvm_call(tools, cp, subject, entry, vals):
    name, method = entry["entry"].split("#")
    return command(
        [
            JDK / "bin/java",
            "-ea",
            "-Xverify:all",
            "-cp",
            os.pathsep.join(map(str, [tools, *cp])),
            "org.intheloop.observation.CallOnce",
            subject,
            name,
            method,
            entry["descriptor"],
            *vals,
        ]
    ).splitlines()


def stock(checker, out, tmp, tools):
    cp = compile_original("397", "original", tmp / "original")
    expected = {
        "nonnegative": "verified",
        "taken": "verified",
        "aliasLaw": "verified",
        "unchanged": "violation",
        "shared": "violation",
        "distinct": "violation",
    }
    report = {"classes": {p.name: sha(p) for p in sorted(cp[0].glob("*.class"))}, "claims": {}}
    for name, want in expected.items():
        drv = tmp / ("generated-" + name)
        plans = construct(checker, "Checkout$Pair", "InventoryChecks#" + name, cp, drv)
        if len(plans["plans"]) != 1 or plans["missed"]:
            raise ValueError("stock producer inventory changed")
        (plan,) = plans["plans"]
        item = {"construction": plans}
        for lane, paths, target in [
            ("automatic", [drv, *cp], plan["entry"]),
            ("supplied", cp, "FactoryClaims#" + name),
        ]:
            if lane == "supplied" and name in ("shared", "distinct"):
                continue
            result = native(checker, paths, target, None, 9, 8, 60, tmp / (lane + name))
            if result["verdict"] != want:
                raise ValueError((name, lane, result["verdict"], result["problem"]))
            item[lane] = result
            if want == "violation":
                args = witness_args(result)
                replay = jvm_call(
                    tools, paths, "Checkout$Pair", {"entry": target, "descriptor": plan["descriptor"]}, args
                )
                if replay != ["class " + report["classes"]["Checkout$Pair.class"], "returned false"]:
                    raise ValueError((target, args, replay))
                item[lane + "Witness"] = {
                    "inputs": args,
                    "steps": [plan["producer"], plans["observer"]],
                    "jvm": replay,
                }
        report["claims"][name] = item
    env = dict(os.environ, JAVA_HOME=str(JDK), JVMCONTRACT_JAR_RELEASE="21")
    ran = command([JDK / "bin/java", "-ea", "-cp", cp[0], "Checkout"], env=env)
    if "Shared backup changed from 1 to 0" not in ran:
        raise ValueError(ran)
    report["boundaryJvm"] = ran.strip()
    # Select the guard of Stock.take from a discovered producer; the evaluator supplies no construction.
    gen = tmp / "site-history"
    p = construct(checker, "Checkout$Pair", "InventoryChecks#taken", cp, gen)["plans"][0]
    info = read(PINS)["stock"]["Checkout$Stock#take"]
    guard = next(s for s in info["sites"] if s["kind"] == "branch")
    directory = tmp / "stock-query"
    directory.mkdir()
    receipt = investigate(
        checker,
        [gen, *cp],
        p["entry"],
        "Checkout$Stock#take",
        info["sha256"],
        guard["pc"],
        "branch",
        "taken",
        None,
        9,
        8,
        60,
        out / "selected",
        directory,
        tools,
    )
    if receipt["disposition"] != "refuted":
        raise ValueError(receipt["disposition"])
    return report


def sites(checker, out, tmp, tools):
    pins = read(PINS)
    # Each row names the original site, entry domain, policy, bound and expected first disposition.
    rows = [
        (
            "divide-occurs",
            "original",
            "dividing",
            "run",
            19,
            "division-by-zero",
            "occurrence",
            None,
            9,
            None,
            "refuted",
        ),
        (
            "divide-escapes",
            "original",
            "dividing",
            "run",
            19,
            "division-by-zero",
            "escape",
            None,
            9,
            None,
            "established",
        ),
        (
            "array-escapes",
            "original",
            "indexing",
            "run",
            44,
            "bounds",
            "escape",
            "arg0 >= 0 && arg0 <= 2",
            9,
            None,
            "refuted",
        ),
        ("dead", "original", "guarded", "run", 54, "null", "occurrence", None, 9, None, "unreachable"),
        ("widened", "guard", "guarded", "run", 54, "null", "occurrence", None, 9, None, "refuted"),
        ("short-sum", "original", "summing", "run", 77, "return", "return-equals", None, 3, 21, "incomplete"),
        ("sum", "original", "summing", "run", 77, "return", "return-equals", None, 9, 21, "established"),
        ("wrong-sum", "original", "summing", "run", 77, "return", "return-equals", None, 9, 22, "refuted"),
        (
            "helper-escapes",
            "helper",
            "dividing",
            "divide",
            3,
            "division-by-zero",
            "escape",
            None,
            9,
            None,
            "refuted",
        ),
    ]
    results = {}
    cps = {v: compile_original("398", v, tmp / v) for v in ("original", "guard", "helper")}
    failures = []
    for key, variant, entry, method, pc, kind, policy, assume, unwind, equals, want in rows:
        target = "SafetySites#" + method
        directory = tmp / key
        directory.mkdir()
        r = investigate(
            checker,
            cps[variant],
            "SafetyClaims#" + entry,
            target,
            pins[variant][target]["sha256"],
            pc,
            kind,
            policy,
            assume,
            unwind,
            8,
            60,
            out / key,
            directory,
            tools,
            equals,
        )
        results[key] = dict(expected=want, actual=r["disposition"], binding=r["subject"]["binding"]["sha256"])
        if r["disposition"] != want:
            failures.append(key)
    write(out / "checks.json", results)
    if failures:
        raise ValueError(failures)
    return results


def csv_sites(checker, out, tmp, tools):
    results = {}
    for version in ("parent", "fix"):
        cp = csv(version, tmp / version)
        member = "campaign.DelimitedFields#matches"
        pin = read(PINS)["csv-" + version][member]["sha256"]
        checks = {}
        for label, pc in (("count", 62), ("field", 103), ("exhaustion", 133)):
            key = version + "-" + label
            directory = tmp / key
            directory.mkdir()
            q = investigate(
                checker,
                cp,
                "campaign.DelimitedFields#fields",
                member,
                pin,
                pc,
                "branch",
                "fallthrough",
                "arg0 >= 0 && arg0 < 14",
                128,
                16384,
                90,
                out / key,
                directory,
                tools,
            )
            inv = inventory(checker, cp, member)
            entry = inventory(checker, cp, "campaign.DelimitedFields#fields")
            selected = next(s for s in inv["sites"] if s["pc"] == pc and s["kind"] == "branch")
            # Code 3 selects a||b||. The full finite domain identifies exactly which other paths ran this test.
            traces = {str(i): original(tools, cp, inv, selected, entry, [str(i)]) for i in range(14)}
            reached = [int(i) for i, lines in traces.items() if any(l.startswith("hit ") for l in lines)]
            wrong = [
                int(i)
                for i, lines in traces.items()
                if any(
                    l.startswith("next ") and l.endswith("@" + str(selected["followingPc"])) for l in lines
                )
            ]
            if (3 in reached) != (version == "fix" or label == "count"):
                raise ValueError((key, reached))
            expected = "refuted" if wrong else "established" if reached else "unreachable"
            if q["disposition"] != expected:
                raise ValueError((key, q["disposition"], expected))
            checks[label] = {
                "pc": pc,
                "disposition": expected,
                "reachedSelectors": reached,
                "violatingSelectors": wrong,
                "originalJvm": traces,
            }
        results[version] = checks
    return results


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("lane", choices=("bind", "stock", "sites", "csv"))
    p.add_argument("--checker", type=Path, default=os.environ.get("JVMCONTRACT"))
    p.add_argument("--output", type=Path, help="receipt directory for a local repeat")
    args = p.parse_args()
    checker = args.checker.resolve()
    if args.lane == "bind":
        write(PINS, bind(checker))
    else:
        out = args.output or RESULTS / "qualification" / args.lane
        out.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as temp:
            tmp = Path(temp)
            result = {
                "checkerSha256": sha(checker),
                "source": os.environ.get("VERIFY_SOURCE_COMMIT"),
                "job": os.environ.get("VERIFY_JOB_ID"),
                "jdk": command([JDK / "bin/java", "--version"]).splitlines()[0],
                "result": {"stock": stock, "sites": sites, "csv": csv_sites}[args.lane](
                    checker, out, tmp, compiler(tmp)
                ),
            }
            write(out / "measurement.json", result)
