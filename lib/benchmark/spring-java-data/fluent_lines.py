"""Check the original fluent claims under each platform line ending and replay a custom delimiter."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

from historical_companion import bind, prepare_graph
from measure import ROOT, digest, read, write
from role_edge import FOLDER
from targets import native_selectors, runtime

CALLER = "springwork.FluentLines"
SOURCE = FOLDER / "companions/FluentLines.java"
DEST = FOLDER / "records/fluent-lines"
BOUNDS = {"unwind": 256, "maxArrayLength": 16384}
PROFILES = {"default": "\n", "crlf": "\r\n", "pipe": "|"}


def expected(separator):
    rows = ["separator" + "".join(f" {ord(ch)}" for ch in separator)]
    for code in range(32):
        mask = code % 16
        names = decision = True
        if separator == "|":
            # Joining lines with '|' yields A > B|B > C|B > D| (with each role prefixed).
            # A reaches foreign names. B reaches no new recognized name. Only a direct D grants.
            names = not mask & 1 and (not mask & 2 or mask & 12 == 12)
            decision = bool(mask & 8) == bool(mask & 11)
        rows.append(f"{code} {int(names)} {int(decision)} 1")
    return rows


def qualify(raw, case):
    out = native_selectors.checker_output.wire.decode(raw.decode(), "prove")
    if not out.ok or len(out.outcomes) != 1:
        raise ValueError("missing fluent selector proof")
    row, = out.outcomes
    target = f"{native_selectors.PACKAGE}.Calls#{native_selectors.case_name(case)}()"
    if (native_selectors.disposition(row, target, BOUNDS, 0) != ("established", None)
            or row.get("problem") or row.get("counterexample") or row["throws"]
            or row["stated"]["checker"]["fallback"] is not None
            or any(a["basis"] != "engine" for a in row["stated"]["assumptions"])):
        raise ValueError(f"incomplete or differently scoped fluent proof for input {case}")
    return row["stated"]["assumptions"]


def measure(replay=False):
    with tempfile.TemporaryDirectory(prefix="fluent-lines-") as scratch:
        work = Path(scratch)
        jdk, graph, paths, bound = prepare_graph(FOLDER, "landed", "fluent-names-landed", work)
        jars = paths[1:]
        classes = work / "classes"
        classes.mkdir()
        cp = os.pathsep.join(map(str, [classes, *jars]))
        subprocess.run([jdk / "bin/javac", "--release", "21", "-proc:none", "-cp", cp, "-d", classes, SOURCE], check=True)
        env = runtime._verifier_env({"home": str(jdk)})
        env["JVMCONTRACT_JAR_RELEASE"] = "21"
        observed = {}
        for profile, sep in PROFILES.items():
            options = [] if profile == "default" else ["-Dline.separator=" + sep]
            raw = subprocess.check_output([jdk / "bin/java", *options, "-cp", cp, CALLER], env=env)
            if raw.decode().splitlines() != expected(sep):
                raise ValueError(f"different public outcomes or separator on {profile} JVM")
            observed[profile] = raw
        print("32 original reachable-name and manager comparisons on each of LF, CRLF and pipe", flush=True)
        if replay:
            return
        DEST.mkdir(parents=True, exist_ok=True)
        checker = Path(os.environ["JVMCONTRACT"])
        for profile, raw in observed.items():
            (DEST / (profile + ".stdout")).write_bytes(raw)
        caller = classes / "springwork/FluentLines.class"
        (DEST / "FluentLines.jvm-bytecode").write_bytes(caller.read_bytes())
        calls = native_selectors.compiled_calls(jdk, work / "wrappers", CALLER, "check", 0, 31, [classes,*jars], classes)
        (DEST / "Calls.jvm-bytecode").write_bytes(calls.read_bytes())
        bindings = [(CALLER, "check", "(I)I", classes, digest(caller))]
        prior = read(FOLDER / "records/opening/run.json")
        for task, method in [("fluent-names-landed", "fluentNames"), ("fluent-decision-landed", "fluentDecision")]:
            receipt = read(FOLDER / prior["tasks"][task]["receipt"])
            packet = receipt["attempt"]
            attempt = read(FOLDER / "receipts" / task / "executions" / packet["id"] / "attempt.json")
            entry = attempt["checker"]["entryBindings"]["landed"]
            bindings.append(("springwork.RoleChecks", method, "(I)I", next(j for j in jars if j.name == entry["loadedFrom"]), entry["classSha256"]))
        for name, info in graph["classes"].items():
            jar = next(j for j, stamp in zip(paths, bound, strict=True) if stamp["sha256"] == info["jarSha256"])
            bindings.append((name, None, None, jar, info["classSha256"]))
        report = {"job": os.environ["VERIFY_JOB_ID"], "source": os.environ["VERIFY_SOURCE_COMMIT"],
                  "libTree": os.environ["JVMCONTRACT_LIB_TREE"], "checkerSha256": digest(checker),
                  "classpath": bound[1:], "jdk": graph["jdk"], "sourceSha256": digest(SOURCE),
                  "bindings": bind(checker, env, work, "landed", bindings, classpath=[classes,*jars]),
                  "callerSha256": digest(caller), "callsSha256": digest(calls),
                  "physical": {k: hashlib.sha256(v).hexdigest() for k,v in observed.items()}, "proofs": []}
        with tarfile.open(DEST / "cases.tar.gz", "w:gz") as archive:
            for case in range(32):
                dest = work / "raw" / str(case)
                row = native_selectors.native_case(str(checker), {"home": str(jdk)}, jars, classes, case, BOUNDS,
                                                   60, work / f"proof-{case}", dest)
                if row["status"] != "established":
                    raise ValueError(f"fluent input {case}: {row.get('firstBlocker', row['status'])}")
                raw = dest / "native.json"
                assumptions = qualify(raw.read_bytes(), case)
                if assumptions != row["assumptions"] or digest(raw) != row["rawSha256"]:
                    raise ValueError("different native parameters or file")
                archive.add(raw, arcname=f"cases/{case}/native.json")
                report["proofs"].append(row)
        write(DEST / "measurement.json", report)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--replay", action="store_true")
    measure(cli.parse_args().replay)
