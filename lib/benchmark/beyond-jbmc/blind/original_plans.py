"""Register and qualify the disclosed finite public observations on the two unrenamed release graphs."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from scaffold_first import (DEST, HERE, JDK, compile_java, compressed, digest, javaenv, read,
                            registered, save, scratch)
from history import ROOT, encoded
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_plan, runtime_jar

PROBE = HERE / "original/UpgradeProbe.java"
CHANNELS = ("primary", "control")


def caller_jar(work, source, files):
    classes = work / "caller"
    compile_java([source], classes, files, javaenv())
    jar = work / "reference-caller.jar"
    with zipfile.ZipFile(jar, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(classes.rglob("*.class")):
            name = file.relative_to(classes).as_posix()
            info = zipfile.ZipInfo(name)
            archive.writestr(info, file.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    return jar, digest(classes / "ReferenceAPI.class")


def predictions(work, spec):
    """Evaluate the locked numeric oracle without a release or a public caller on its classpath."""
    expressions = spec["expected"]
    source = work / "LockedExpectation.java"
    source.write_text(
        "public class LockedExpectation { public static void main(String[] args) {\n"
        "for (String arg : args) { int n = Integer.parseInt(arg);\n"
        + "".join("long " + k + " = " + expressions[k + "Expression"] + ";\n" for k in ("before", "after", "control"))
        + 'System.out.println(n + "\\t" + before + "\\t" + after + "\\t" + control); } } }\n')
    directory = work / "expected"
    compile_java([source], directory, [], javaenv())
    data = subprocess.check_output([JDK / "bin/java", "-XX:-UsePerfData", "-cp", directory, "LockedExpectation",
                                    *map(str, spec["seeds"])], text=True)
    return [list(map(int, line.split("\t"))) for line in data.splitlines()]


def prepare(slot, work):
    row, ref, spec, packet, graphs = registered(slot)
    scaffold_path = DEST / "scaffolds" / (slot + ".json.gz")
    scaffold = compressed(scaffold_path)
    if scaffold["firstScaffoldStop"] or scaffold["packetSha256"] != row["packetSha256"]:
        raise ValueError("the ordinary original JVMs must qualify before measurement")
    jar, caller_hash = caller_jar(work, ref / "ReferenceAPI.java", graphs["old"])
    if caller_hash != scaffold["callerSha256"]:
        raise ValueError("compiled caller differs from physical investigation")
    expected = predictions(work, spec)
    entries = read(HERE / "public-entries.json")[slot]
    deployments = {}
    selected = compressed(HERE / "draw/sealed.json.gz")["pairs"][int(slot) - 1]
    if selected["artifact"] != row["artifact"]:
        raise ValueError("reference and sealed release pair differ")
    for side, before_after in (("old", 1), ("new", 2)):
        if [[r[0], r[before_after], r[3]] for r in expected] != scaffold["sides"][side]["direct"]["rows"]:
            raise ValueError("independent prediction disagrees with original caller")
        files = graphs[side]
        declarations = {}
        for entry in entries:
            owner, method, descriptor = runtime_jar.parse_target(entry)
            data = runtime_jar.read_class(files[0], runtime_jar.internal(owner))
            if not data or (method, descriptor) not in runtime_jar.methods(data):
                raise ValueError(f"{slot} {side}: missing registered original method {entry}")
            declarations[entry] = hashlib.sha256(data).hexdigest()
        endpoint = selected["before" if side == "old" else "after"]
        if selected["eligibility"][side + "Sha256"] != packet[side][0]["sha256"]:
            raise ValueError("selected library differs from the first deployment JAR")
        source_files = endpoint["sourceEntry"]["files"]
        deployments[side] = {"releaseDebSha256": endpoint["SHA256"], "sourceFiles": source_files, "declaringClasses": declarations,
                             "orderedClasspathSha256": [item["sha256"] for item in packet[side]]}
        manifest = {"commit": selected["suites"][before_after - 1] + "/" + endpoint["Version"],
                    "sourceSha256": hashlib.sha256(encoded(source_files)).hexdigest(),
                    "scope": "Original signed distribution classpath, followed by the locked observation caller",
                    "jdkReleaseSha256": scaffold["profile"]["jdkReleaseSha256"],
                    "classpath": [{"file": str(file), "sha256": item["sha256"]} for file, item in zip(files, packet[side], strict=True)]
                                 + [{"file": str(jar), "sha256": digest(jar)}]}
        save(work / (side + ".json"), manifest)
    questions = []
    for i, channel in enumerate(CHANNELS):
        cases = [{"args": [channel, str(p[0])], "expected": {"return": str(p[1] if i == 0 else p[3])}} for p in expected]
        changes = [{"input": j, "expectedNew": {"return": str(p[2])}} for j, p in enumerate(expected) if i == 0 and p[1] != p[2]]
        entry = entries[min(i, len(entries) - 1)]
        scope = {"probeClass": "UpgradeProbe", "entry": entry, "invocationVia": f"ReferenceAPI#{channel}(I)J",
                 "observer": spec["question" if i == 0 else "control"], "basis": spec["domain"], "cases": cases}
        questions.append({"scope": scope, "intent": {"allowedChanges": changes} if changes else "preserve"})
    return {"slot": slot, "artifact": row["artifact"], "callerJarSha256": digest(jar), "probeSha256": digest(PROBE),
            "scaffoldSha256": digest(scaffold_path), "referenceSha256": row["referenceSha256"], "deployments": deployments,
            "questions": questions, "oracle": spec["expected"], "domain": spec["bounds"], "inputs": spec["seeds"],
            "fullRegisteredDomain": spec["bounds"] is not None and spec["seeds"] == list(range(spec["bounds"][0], spec["bounds"][1] + 1))}


def materialize(work, record, wrong=False):
    workflows = []
    for channel, question in zip(CHANNELS, record["questions"], strict=True):
        scope = question["scope"]
        intent = question["intent"]
        if wrong and channel == "primary":
            # The original finite values are signed longs, so this cannot be the actual return.
            intent = {"allowedChanges": [{"input": 0, "expectedNew": {"return": "deliberately wrong"}}]}
        save(work / (channel + ".json"), scope)
        workflows.append({"id": channel, "cohort": "registered" if channel == "primary" else "control",
                          "scope": channel + ".json", "probe": str(PROBE), "intent": intent,
                          "deterministicUnderAssumptions": True, "assumptions": [
                              "The listed finite inputs, original binaries, ordered local providers and released caller are fixed.",
                              "Fresh ordinary JVM startup, UTC, US locale, local scratch, and the class and resource bindings in the scaffold."]})
    file = work / "workflows.json"
    save(file, {"schema": "caller-workflows/v1", "change": record["artifact"] + " disclosed original caller", "workflows": workflows})
    change_plan.frozen_workflows(file)
    return file


def run(slot, label, modes, register_only):
    registration = DEST / "registrations" / (slot + ".json")
    with scratch(prefix="original-release-plan-") as tmp:
        work = Path(tmp)
        record = prepare(slot, work)
        workflows = materialize(work, record)
        if register_only:
            save(registration, record)
            print(slot, "registered two public entries and their independent expectations", flush=True)
            return
        if read(registration) != record:
            raise ValueError("the current preparation differs from the preregistration")
        out = DEST / "original-plans" / label / slot
        out.mkdir(parents=True, exist_ok=True)
        checker = Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")).resolve()
        archive = out / "plans.zip"
        summary = {}
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
            archived = set()
            for mode in modes:
                workflows = materialize(work, record, wrong=mode == "wrong")
                path = work / (mode + ".json")
                command = [sys.executable, ROOT / "examples/tools/build.py", "--change-plan", "application",
                           "--before", work / "old.json", "--after", work / "new.json", "--jdk", JDK,
                           "--workflows", workflows, "--checker", checker, "--run", "--seconds", "300",
                           "--cache", work / ("clean-cache" if mode == "clean" else "cache"), "--output", path]
                if mode == "warm":
                    command += ["--previous", work / "cold.json"]
                subprocess.run(command, check=True, cwd=ROOT)
                plan = read(path)
                if plan["executionState"] != "complete" or [r["id"] for r in plan["claims"]] != list(CHANNELS):
                    raise ValueError("incomplete original plan")
                zipped.write(path, mode + ".json")
                summary[mode] = []
                for claim in plan["claims"]:
                    row = {k: claim.get(k) for k in ("id", "status", "firstOpenDependency", "reason", "execution", "receipt")}
                    if row["receipt"]:
                        receipt = work / row["receipt"]["path"]
                        if digest(receipt) != row["receipt"]["sha256"]:
                            raise ValueError("bad evidence digest")
                        evidence = read(receipt)
                        row["qualifiedEntries"] = {side: sum(t["qualifiedMethodEntries"] for t in d.get("trials", []))
                                                   for side, d in evidence.get("sides", {}).items()}
                    summary[mode].append(row)
                for receipt in sorted((work / "receipts").glob("*.json")):
                    if receipt.name not in archived:
                        zipped.write(receipt, "receipts/" + receipt.name)
                        archived.add(receipt.name)
                print(slot, mode, [(r["id"], r["status"], r["firstOpenDependency"]) for r in summary[mode]], flush=True)
        save(out / "summary.json", {"registrationSha256": digest(registration), "phase": label,
             "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"), "job": os.environ.get("VERIFY_JOB_ID"),
             "runner": change_plan.runner_identity(), "checkerSha256": digest(checker), "archiveSha256": digest(archive),
             "fullRegisteredDomain": record["fullRegisteredDomain"], "runs": summary})


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slots", nargs="+")
    ap.add_argument("--register", action="store_true")
    ap.add_argument("--label", default="first")
    ap.add_argument("--modes", nargs="+", choices=("cold", "warm", "clean", "wrong"), default=["cold"])
    a = ap.parse_args()
    for slot in a.slots:
        run(slot, a.label, a.modes, a.register)
