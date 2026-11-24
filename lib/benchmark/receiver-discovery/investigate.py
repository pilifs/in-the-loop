"""Investigate one digest-bound physical JVM check or branch on a supplied public history."""

import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zipfile

from callers import JDK, sha

HERE = Path(__file__).resolve().parent
EXPORTS = [
    s
    for pkg in ("asm", "asm.tree")
    for s in ("--add-exports", "java.base/jdk.internal.org.objectweb." + pkg + "=ALL-UNNAMED")
]
TYPES = dict(Z="boolean", B="byte", C="char", S="short", I="int", J="long", F="float", D="double")
STATE = "org.intheloop.observation.SiteState"
BITS = {"occurrence": 2, "escape": 32, "taken": 4, "fallthrough": 8, "absence": 1, "return-equals": 64}
EXCEPTIONS = {
    "division-by-zero": "java.lang.ArithmeticException",
    "null": "java.lang.NullPointerException",
    "bounds": "java.lang.ArrayIndexOutOfBoundsException",
    "array-store": "java.lang.ArrayStoreException",
    "cast": "java.lang.ClassCastException",
    "negative-array-size": "java.lang.NegativeArraySizeException",
}


def command(argv, **kwargs):
    return subprocess.check_output(list(map(str, argv)), text=True, **kwargs)


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def compiler(tmp):
    dest = tmp / "tools"
    dest.mkdir(exist_ok=True)
    command(
        [
            JDK / "bin/javac",
            *EXPORTS,
            "-g",
            "-parameters",
            "-proc:none",
            "-d",
            dest,
            *sorted((HERE / "java").glob("*.java")),
        ]
    )
    return dest


def inventory(checker, cp, target):
    options = [flag for path in cp for flag in ("--classes", path)]
    return json.loads(
        command(
            [checker, "sites", target, *options],
            env=dict(os.environ, JAVA_HOME=str(JDK), JVMCONTRACT_JAR_RELEASE="21"),
        )
    )


def class_bytes(binding):
    path, entry = Path(binding["provider"]), binding["entry"]
    if path.is_dir():
        return (path / entry).read_bytes()
    if path.is_file() and path.suffix == ".class":
        return path.read_bytes()
    with zipfile.ZipFile(path) as jar:
        return jar.read(entry)


def wrappers(entry, bit):
    owner = entry["owner"].replace("/", ".").replace("$", ".")
    args = entry["descriptor"].split(")")[0][1:]
    if any(t not in TYPES for t in args):
        raise ValueError("selected entry needs a public primitive-argument history")
    params = ", ".join(f"{TYPES[t]} arg{i}" for i, t in enumerate(args))
    values = ", ".join(f"arg{i}" for i in range(len(args)))
    return f"""public final class SelectedSiteQuery {{
    static int events({params}) {{
        {STATE}.flags = 0;
        try {{ {owner}.{entry['method']}({values}); }} catch (Throwable ended) {{ }}
        return {STATE}.flags;
    }}
    public static boolean complete({params}) {{ return (events({values}) & 16) == 0; }}
    public static boolean absent({params}) {{ return (events({values}) & 1) == 0; }}
    public static boolean safe({params}) {{ return (events({values}) & {bit}) == 0; }}
}}
"""


def native(checker, cp, method, assume, unwind, max_array, seconds, work):
    env = dict(
        os.environ,
        JAVA_HOME=str(JDK),
        JVMCONTRACT_JAR_RELEASE="21",
        PATH=str(JDK / "bin") + os.pathsep + os.environ["PATH"],
    )
    argv = [
        checker,
        "prove",
        method,
        "--classes",
        cp[0],
        "--classpath",
        os.pathsep.join(map(str, cp[1:])),
        "--engine",
        "native",
        "--gaps",
        "strict",
        "--assert",
        "result",
        "--unwind",
        str(unwind),
        "--max-array-length",
        str(max_array),
        "--timeout",
        str(seconds),
        "--work",
        work,
        "--json",
    ]
    if assume:
        argv += ["--assume", assume]
    run = subprocess.run(argv, env=env, text=True, capture_output=True, timeout=seconds + 30)
    try:
        (row,) = json.loads(run.stdout)
    except (ValueError, TypeError) as e:
        raise ValueError(f"{method}: checker exited {run.returncode}: {run.stderr[-1000:]}") from e
    if (
        row["target"] != method
        or row["assert"] != "result"
        or row["assume"] != assume
        or row["verdict"] not in ("verified", "violation", "unverifiable")
    ):
        raise ValueError("native response does not identify the selected query")
    stated = row.get("stated") or {}
    if row["verdict"] == "verified" and (stated.get("vacuity") or {}).get("status") != "non-vacuous":
        raise ValueError("native proof has no non-vacuity evidence")
    return row


def original(tools, cp, subject, site, entry, values):
    runtime = os.pathsep.join(map(str, [tools, *cp]))
    lines = command(
        [
            JDK / "bin/java",
            "-cp",
            tools,
            "OriginalSite",
            runtime,
            subject["owner"].replace("/", "."),
            subject["method"],
            subject["descriptor"],
            str(site["pc"]),
            site["kind"],
            entry["owner"].replace("/", "."),
            entry["method"],
            entry["descriptor"],
            *values,
        ],
        timeout=45,
    ).splitlines()
    if "class " + subject["binding"]["sha256"] not in lines or not any(
        s.startswith(("returned ", "escaped ")) for s in lines
    ):
        raise ValueError("original JVM identity or terminal observation missing")
    return lines


def witness_args(row):
    c = row.get("counterexample") or {}
    inputs = c.get("inputs", c.get("witness", {}).get("inputs"))
    if inputs is None:
        raise ValueError("native violation lacks a typed witness")
    values = []
    for arg in inputs:
        value = arg["value"]
        if arg["type"] in ("float", "double"):
            value = (
                value.removeprefix("bits:0x")
                if isinstance(value, str) and value.startswith("bits:0x")
                else struct.pack(">f" if arg["type"] == "float" else ">d", float(value)).hex()
            )
        elif arg["type"] == "char" and isinstance(value, str) and len(value) == 1:
            value = ord(value)
        values.append(str(value).lower())
    return values


def investigate(
    checker,
    cp,
    entry_name,
    target,
    pin,
    pc,
    kind,
    policy,
    assume,
    unwind,
    max_array,
    seconds,
    out,
    tmp,
    tools,
    equals=None,
):
    if not 0 <= unwind <= 2147483647:
        raise ValueError("unwind outside Java int range")
    if (
        policy in ("taken", "fallthrough")
        and kind != "branch"
        or policy in ("escape", "occurrence")
        and kind not in EXCEPTIONS
    ):
        raise ValueError("selected policy does not apply to that instruction kind")
    if (policy == "return-equals") != (equals is not None) or equals is not None and kind != "return":
        raise ValueError("return-equals requires an int return and an expected value")
    subject, entry = (inventory(checker, cp, name) for name in (target, entry_name))
    if subject["binding"]["sha256"] != pin:
        raise ValueError("class digest differs from the selected original")
    (site,) = [s for s in subject["sites"] if s["pc"] == pc and s["kind"] == kind]
    if site["selection"] != "supported":
        raise ValueError(site["selection"])
    out.mkdir(parents=True, exist_ok=True)
    work = tmp / "projection"
    work.mkdir()
    selected = work / (subject["owner"] + ".class")
    bound = tmp / "bound.class"
    bound.write_bytes(class_bytes(subject["binding"]))
    if sha(bound) != pin:
        raise ValueError("selected bytes changed on disk")
    runtime = os.pathsep.join(map(str, [tools, *cp]))
    command(
        [
            JDK / "bin/java",
            *EXPORTS,
            "-cp",
            runtime,
            "ProjectSite",
            bound,
            pin,
            subject["owner"],
            subject["method"],
            subject["descriptor"],
            site["ordinal"],
            site["opcode"],
            kind,
            unwind,
            selected,
            *([] if equals is None else [equals]),
        ]
    )
    src = tmp / "SelectedSiteQuery.java"
    src.write_text(wrappers(entry, BITS[policy]))
    reserved = {"SelectedSiteQuery.class", *(p.relative_to(tools).as_posix() for p in tools.rglob("*.class"))}
    for provider in cp:
        if provider.is_dir():
            overlap = {name for name in reserved if (provider / name).is_file()}
        else:
            with zipfile.ZipFile(provider) as archive:
                overlap = reserved.intersection(archive.namelist())
        if overlap:
            raise ValueError(f"observer would shadow an input class: {sorted(overlap)}")
    command([JDK / "bin/javac", "-g", "-parameters", "-proc:none", "-cp", runtime, "-d", work, src])
    queries = {}
    for method in ("complete", "absent", "safe"):
        row = native(
            checker,
            [work, tools, *cp],
            "SelectedSiteQuery#" + method,
            assume,
            unwind,
            max_array,
            seconds,
            tmp / method,
        )
        queries[method] = row
    evidence = {
        "schema": "physical-site-investigation/v1",
        "entry": {k: entry[k] for k in ("owner", "method", "descriptor", "binding")},
        "subject": {k: subject[k] for k in ("owner", "method", "descriptor", "binding")},
        "site": site,
        "policy": policy,
        "boundary": "selected method activation",
        "assume": assume,
        "unwind": unwind,
        "maxArrayLength": max_array,
        "checkerSha256": sha(checker),
        "projectionSha256": sha(selected),
        "wrapperSha256": sha(work / "SelectedSiteQuery.class"),
        "expectedReturn": equals,
        "queries": queries,
        "originalJvm": {},
    }
    for method, row in queries.items():
        if row["verdict"] == "violation":
            values = witness_args(row)
            lines = original(tools, cp, subject, site, entry, values)
            hit = any(s.startswith("hit ") for s in lines)
            if method == "absent" and not hit:
                raise ValueError("the independent original execution missed the selected PC")
            if method == "safe":
                if policy == "absence":
                    reproduced = hit
                elif policy == "return-equals":
                    reproduced = any(
                        s.startswith("return-value ") and s != f"return-value {equals}" for s in lines
                    )
                elif policy in ("taken", "fallthrough"):
                    dest = site["branchTargets"][0] if policy == "taken" else site["followingPc"]
                    reproduced = any(s.startswith("next ") and s.endswith("@" + str(dest)) for s in lines)
                else:
                    raised = [s for s in lines if s.startswith("raised " + EXCEPTIONS[kind] + " caught ")]
                    same = (
                        subject["owner"].replace("/", ".")
                        + "#"
                        + subject["method"]
                        + subject["descriptor"]
                        + "@"
                    )
                    reproduced = (
                        bool(raised)
                        if policy == "occurrence"
                        else any(not s.split(" caught ", 1)[1].startswith(same) for s in raised)
                    )
                if not hit or not reproduced:
                    raise ValueError("native site event was not confirmed on the original JVM: " + str(lines))
            evidence["originalJvm"][method] = {"inputs": values, "events": lines}
    complete, absent, safe = (queries[k]["verdict"] for k in ("complete", "absent", "safe"))
    evidence["reachability"] = {"verified": "unreachable", "violation": "reached", "unverifiable": "unknown"}[
        absent
    ]
    evidence["disposition"] = (
        "incomplete"
        if complete != "verified"
        else (
            "unreachable"
            if absent == "verified"
            else (
                "refuted"
                if safe == "violation"
                else "established" if absent == "violation" and safe == "verified" else "unresolved"
            )
        )
    )
    write(out / "result.json", evidence)
    print(target, pc, kind, policy, evidence["reachability"], evidence["disposition"], flush=True)
    return evidence


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checker", type=Path, default=os.environ.get("JVMCONTRACT", shutil.which("jvmcontract")))
    p.add_argument("--classes", type=Path, required=True, action="append")
    for field in ("entry", "target", "sha256", "kind"):
        p.add_argument("--" + field, required=True)
    p.add_argument("--policy", choices=BITS, required=True)
    p.add_argument("--pc", type=int, required=True)
    p.add_argument("--assume")
    p.add_argument("--equals", type=int)
    p.add_argument("--unwind", type=int, required=True)
    p.add_argument("--max-array-length", type=int, required=True)
    p.add_argument("--seconds", type=int, default=60)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        investigate(
            a.checker.resolve(),
            list(map(Path.resolve, a.classes)),
            a.entry,
            a.target,
            a.sha256,
            a.pc,
            a.kind,
            a.policy,
            a.assume,
            a.unwind,
            a.max_array_length,
            a.seconds,
            a.output,
            tmp,
            compiler(tmp),
            a.equals,
        )
