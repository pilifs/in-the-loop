"""Reopen disclosed reference registrations on both unmodified releases before any checker work."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
from collections import Counter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from history import OUTPUT, digest, encoded, scratch
from packets import BASE
from release_cases import JDK, compile_java, javaenv
from stock_history import classpath

DEST = OUTPUT / "scaffold-first"
DOCKET = HERE / "references.json"
JVM_FLAGS = ["-ea", "-Xmx512m", "-XX:-UsePerfData", "-Djava.awt.headless=true",
             "-Duser.language=en", "-Duser.country=US", "-Duser.timezone=UTC", "-Dfile.encoding=UTF-8"]


def read(path):
    return json.loads(path.read_bytes())


def compressed(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(encoded(value), mtime=0) if path.suffix == ".gz" else encoded(value))


def registered(slot):
    row = next(item for item in read(DOCKET)["pairs"] if item["slot"] == slot)
    folder = HERE / "references" / slot
    packet_dir = BASE / slot / "packet"
    for filename, expected in {**row["sources"], "reference.json": row["referenceSha256"],
                               "original-jvm.json": row["physicalSha256"]}.items():
        if digest(folder / filename) != expected:
            raise ValueError(f"{slot}: changed locked input {filename}")
    spec = read(folder / "reference.json")
    if spec != row["reference"] or digest(packet_dir / "inputs.json") != row["packetSha256"]:
        raise ValueError(f"{slot}: changed question or binary packet")
    packet = read(packet_dir / "inputs.json")
    graphs = {}
    for side in ("old", "new"):
        files = []
        for i, entry in enumerate(packet[side]):
            name = f"{side}/{i:03d}.jar"
            path = packet_dir / name
            if entry != {"path": name, "sha256": digest(path)}:
                raise ValueError(f"{slot}: changed ordered provider {name}")
            files.append(path)
        graphs[side] = files
    return row, folder, spec, packet, graphs


def bindings(events, files, caller):
    """Attach actual bytes to the defining provider, in particular to each resource enumeration item."""
    classes, resources = {}, []
    archives = {}
    providers = [caller, *files]
    try:
        for kind, *fields in events:
            if kind == "class":
                name, index = fields
                classes[name] = int(index)
                continue
            event = {"operation": kind, "name": fields[0]}
            if kind in ("resource", "element"):
                origin = fields[-1]
                event["origin"] = origin
                if "!/" in origin:
                    index, member = origin.split("!/", 1)
                    file = providers[int(index)]
                    if file.is_dir():
                        data = (file / member).read_bytes()
                    else:
                        if file not in archives:
                            archives[file] = zipfile.ZipFile(file)
                        data = archives[file].read(member)
                    event["sha256"] = hashlib.sha256(data).hexdigest()
            if kind in ("end", "element"):
                event["index"] = int(fields[1])
            resources.append(event)
        return {"classProviders": classes, "resourceLookups": resources}
    finally:
        for archive in archives.values():
            archive.close()


def observe(work, launcher, caller, files, mode, seeds):
    work.mkdir()
    deploy = classpath([caller, *files])
    cp = classpath([launcher, caller, *files]) if mode == "direct" else str(launcher)
    args = [JDK / "bin/java", *JVM_FLAGS, "-Djava.io.tmpdir=" + str(work), "-cp", cp,
            "LoaderObservations", mode, work / "events.tsv", deploy, *map(str, seeds)]
    proc = subprocess.run(args, cwd=work, capture_output=True, text=True, timeout=45,
                          env={"HOME": str(work), "PATH": str(JDK / "bin") + ":/usr/bin:/bin",
                               "LANG": "C.UTF-8", "TZ": "UTC", "TMPDIR": str(work)})
    path = work / "events.tsv"
    events = [line.split("\t") for line in path.read_text().splitlines()] if path.exists() else []
    rows = [list(map(int, fields[1:])) for fields in events if fields[0] == "row"]
    result = {"exit": proc.returncode, "rows": rows}
    if mode == "record":
        result.update(bindings([e for e in events if e[0] != "row"], files, caller))
    if proc.returncode:
        result["failure"] = proc.stderr.replace(str(work), "$WORK")[-1800:]
    return result


def prepare(slot, directory, launcher, profile, frozen):
    row, ref, spec, packet, graphs = registered(slot)
    original = read(ref / "original-jvm.json")["originalJvm"]
    seeds = spec["seeds"]
    if not original["accepted"] or [r["n"] for r in original["rows"]] != seeds:
        raise ValueError(f"{slot}: missing original physical controls")
    work = directory / slot
    work.mkdir()
    caller = work / "caller"
    compile_java([ref / "ReferenceAPI.java"], caller, graphs["old"], javaenv())
    if digest(caller / "ReferenceAPI.class") != original["callerSha256"]:
        raise ValueError(f"{slot}: caller differs from the locked original")
    record = {"slot": slot, "artifact": row["artifact"], "registration": spec, "docketSha256": digest(DOCKET),
              "callerSha256": original["callerSha256"], "sources": row["sources"], "packetSha256": row["packetSha256"],
              "classpath": packet, "profile": profile, "priorPhysicalSha256": row["physicalSha256"],
              "automaticScaffolding": {k: frozen["automatic"][k] for k in ("namedEntriesSelected", "anyPublicReach",
                  "referenceReached", "primaryObservationDiscovered", "primaryDecided", "reason", "missingCallerCapability")},
              "suppliedRegistration": "locked before the frozen matched solver and reused after disclosure",
              "sides": {}, "firstScaffoldStop": None}
    for side, files in graphs.items():
        expected = [[r["n"], r[side], r[side + "Control"]] for r in original["rows"]]
        runs = {}
        for mode in ("direct", "record"):
            result = observe(work / (side + "-" + mode), launcher, caller, files, mode, seeds)
            runs[mode] = result
            if result["exit"] or result["rows"] != expected:
                record["firstScaffoldStop"] = record["firstScaffoldStop"] or {
                    "side": side, "phase": mode, "expected": expected, "actual": result["rows"],
                    "failure": result.get("failure", "observation differs from the registered JVM")}
        record["sides"][side] = runs
    save(DEST / "scaffolds" / (slot + ".json.gz"), record)
    print(slot, row["artifact"], "scaffolding stopped" if record["firstScaffoldStop"] else "both deployments qualified", flush=True)


def index(frozen):
    counts = {"selectedPathReached": Counter(), "noSelectedPathReached": Counter()}
    records = []
    for slot in sorted(frozen):
        path = DEST / "scaffolds" / (slot + ".json.gz")
        item = compressed(path)
        prior = item["automaticScaffolding"]
        counts["selectedPathReached" if prior["anyPublicReach"] else "noSelectedPathReached"][prior["missingCallerCapability"]] += 1
        for side, modes in item["sides"].items():
            trace = modes["record"]
            if trace["classProviders"].get("ReferenceAPI") != 0 or any(
                    not 0 <= i <= len(item["classpath"][side]) for i in trace["classProviders"].values()):
                raise ValueError(f"{slot}: unbound caller or class provider")
        records.append({"slot": slot, "project": item["artifact"], "question": item["registration"]["question"],
                        "control": item["registration"]["control"], "entries": item["registration"]["entries"],
                        "registeredBeforeSolving": True, "automatic": prior, "suppliedScaffoldStop": item["firstScaffoldStop"],
                        "physicalInputsPerSide": len(item["registration"]["seeds"]),
                        "priorMatchedPrimary": frozen[slot]["matched"]["primary"], "receiptSha256": digest(path)})
    save(DEST / "index.json", {"basis": "Previously disclosed panel. Direct and loader-observed JVM runs precede all follow-up checkers.",
                               "docketSha256": digest(DOCKET), "firstMissingCapabilityByAutomaticReach": counts, "projects": records})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slots", nargs="*")
    ap.add_argument("--index", action="store_true")
    args = ap.parse_args()
    frozen = {p["slot"]: p for p in compressed(OUTPUT / "blind-comparison/matrix.json.gz")["projects"]}
    if args.index:
        index(frozen)
        return
    lock = read(HERE.parent / "freeze.json")
    profile = {"jdkReleaseSha256": digest(JDK / "release"), "jdkModulesSha256": digest(JDK / "lib/modules"),
               "javacSha256": digest(JDK / "bin/javac"), "launcherSha256": digest(HERE / "LoaderObservations.java"),
               "jvmFlags": JVM_FLAGS, "systemProperties": "fresh JVM for each release and mode, temporary directory per run",
               "classLoaders": "direct system loader, then an independent URLClassLoader with platform parent and matching thread context loader",
               "origins": "0 is the unchanged compiled caller, 1 onward are the ordered original release JARs"}
    if profile["jdkModulesSha256"] != lock["jdkModulesSha256"] or profile["javacSha256"] != lock["jdkJavacSha256"]:
        raise ValueError("different historical JDK")
    with scratch(prefix="scaffold-first-") as tmp:
        work = Path(tmp)
        launcher = work / "launcher"
        subprocess.run([JDK / "bin/javac", "-proc:none", "-d", launcher, HERE / "LoaderObservations.java"], check=True)
        for slot in args.slots or sorted(frozen):
            prepare(slot, work, launcher, profile, frozen[slot])


if __name__ == "__main__":
    main()
