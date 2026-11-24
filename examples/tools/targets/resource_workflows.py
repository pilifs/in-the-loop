"""Discover bounded resource-index workflows from two ordered Java deployments and register them before solving."""
import argparse
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from targets import change_evidence, change_inventory, runtime_jar, runtime_jdk, upgrade_replay

TEMPLATE = Path(__file__).with_name("java") / "ResourceObserver.java.template"
ENUMERATE = ("java/lang/ClassLoader", "getResources", "(Ljava/lang/String;)Ljava/util/Enumeration;")
CLASS = "Ljava/lang/Class;"
LOADER = "Ljava/lang/ClassLoader;"
SHAPES = {f"({CLASS}{LOADER})Ljava/util/Set;": "annotation names",
          f"({CLASS})Ljava/util/Iterator;": "service instances"}
CALLER = """public class ReadLookup {
    public static void main(String[] args) throws Exception {
        System.out.println("LOOKUP " + UpgradeProbe.observe(args));
    }
}"""


def candidates(jar, feature):
    selected = {}
    with zipfile.ZipFile(jar) as archive:
        for name, info in runtime_jar.effective_entries(archive, feature).items():
            if not name.endswith(".class") or name.startswith("META-INF/"):
                continue
            data = archive.read(info)
            if b"getResources" not in data or not runtime_jar.class_flags(data) & 1:
                continue
            owner = name[:-6].replace("/", ".")
            for method, descriptor, flags, calls in change_inventory.invocation_inventory(data):
                if descriptor in SHAPES and flags & 9 == 9 and ENUMERATE in calls:
                    selected[owner + "#" + method + descriptor] = (owner, method, SHAPES[descriptor])
    return selected


def source(target, names):
    owner, method, shape = target
    if not all(re.fullmatch(r"[a-zA-Z_$][\w$]*", part, re.ASCII) for part in [*owner.split("."), method]):
        raise ValueError("entry cannot be expressed as a Java source call")
    call = owner.replace("$", ".") + "." + method
    if shape == "annotation names":
        body = f"""Class<? extends java.lang.annotation.Annotation> marker = control ? Override.class : Deprecated.class;
            java.util.Set<?> entries = {call}(marker, loader);
            for (Object item : entries) found.add((String)item);"""
    else:
        body = f"""Class<?> marker = Class.forName((control ? Other.class : Marker.class).getName(), true, loader);
            java.util.Iterator<?> entries = {call}(marker);
            while (entries.hasNext()) {{
                Object item = entries.next();
                if (!marker.isInstance(item) || item.getClass().getClassLoader() != loader)
                    throw new IllegalStateException("provider does not implement the requested service in its defining loader");
                found.add(item.getClass().getName());
            }}"""
    return TEMPLATE.read_text().replace("INVOCATION", body).replace("RESOURCE_NAMES", ", ".join(map(json.dumps, names)))


def compile_observer(work, probe, files, jdk):
    work.mkdir()
    runner = work / "ReadLookup.java"
    runner.write_text(CALLER)
    args = [jdk / "bin/javac", "-J-XX:-UsePerfData", "-proc:none", "-g", "-cp", os.pathsep.join(map(str, files)),
            "-d", work, runner, probe]
    subprocess.run(args, check=True, capture_output=True, timeout=30)


def physical(work, compiled, jdk, files, inputs):
    cp = os.pathsep.join(map(str, [compiled, *files]))
    cmd = [jdk / "bin/java", "-Xmx256m", "-XX:-UsePerfData", "-Duser.language=en", "-Duser.country=US",
           "-Duser.timezone=UTC", "-Djava.io.tmpdir=" + str(work), "-cp", cp, "ReadLookup", *inputs]
    proc = subprocess.run(cmd, cwd=work, text=True, capture_output=True, timeout=25,
                          env={"HOME": str(work), "PATH": str(jdk / "bin") + ":/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC"})
    rows = [s[7:] for s in proc.stdout.splitlines() if s.startswith("LOOKUP ")]
    if proc.returncode or len(rows) != 1:
        raise ValueError("original caller did not return a unique observation: " + proc.stderr[-600:])
    return rows[0]


def expectation(shape, queries, names, args):
    control, mask = args[0] == "control", int(args[1])
    original, other = (("java.lang.Deprecated", "java.lang.Override") if shape == "annotation names"
                       else ("UpgradeProbe$Marker", "UpgradeProbe$Other"))
    found = []
    for i, resource in enumerate(names):
        if not control and resource in queries and mask & (1 << i):
            found += ["UpgradeProbe$First" if i % 2 == 0 else "UpgradeProbe$Last", "UpgradeProbe$Shared"]
            if len(names) == 1 and args[2] != "single":
                found.append("UpgradeProbe$Last")
    if shape == "annotation names":
        found = set(found)
    keys = [name.removesuffix(original) + other for name in queries] if control else queries
    return "|".join(keys) + "=" + ",".join(sorted(found))


def discover_entry(entry, target, graphs, jdk, dest):
    record = {"entry": entry, "shape": target[2], "stage": "discover resource keys on both originals"}
    dest.mkdir()
    probe = dest / "UpgradeProbe.java"
    workflows = []
    try:
        with tempfile.TemporaryDirectory(prefix="discover-resource-") as tmp:
            work = Path(tmp)
            probe.write_text(source(target, []))
            compile_observer(work / "empty", probe, graphs["old"], jdk)
            queries = {side: physical(work, work / "empty", jdk, files, ["discover", "0", "forward"]).split("|")
                       for side, files in graphs.items()}
            record["emptyLookups"] = queries
            names = sorted(set(queries["old"] + queries["new"]))
            suffix = "java.lang.Deprecated" if target[2] == "annotation names" else "UpgradeProbe$Marker"
            if (not 1 <= len(names) <= 4 or any(not re.fullmatch(r"META-INF/(?:[\w.-]+/)+" + re.escape(suffix), name)
                                                  or ".." in name.split("/") for name in names)):
                raise ValueError("empty original loaders did not expose a bounded set of marker-specific resource keys")
            probe.write_text(source(target, names))
            # Register every mask independently of the populated original classpaths' answers.
            for channel in ("primary", "control"):
                masks = range(1 << len(names)) if channel == "primary" else [0, (1 << len(names)) - 1]
                domain = [[channel, str(mask), order] for mask, order in itertools.product(masks, ("single", "forward", "reverse"))]
                before = [expectation(target[2], queries["old"], names, args) for args in domain]
                after = [expectation(target[2], queries["new"], names, args) for args in domain]
                change = [{"input": n, "expectedNew": {"return": b}} for n, (a, b) in enumerate(zip(before, after)) if a != b]
                scope = {"entry": entry, "probeClass": "UpgradeProbe",
                         "observer": "Actual resource requests and sorted class names or typed provider instances",
                         "basis": "Every registered location mask, one resource root and both orders of two roots. Populated resources contain known lines. An unrelated marker has no matching resource.",
                         "cases": [{"args": args, "expected": {"return": value}} for args, value in zip(domain, before)]}
                change_evidence.write_json(dest / (channel + ".json"), scope)
                workflows.append({"id": channel, "scope": channel + ".json", "probe": "UpgradeProbe.java",
                                  "intent": {"allowedChanges": change} if change else "preserve",
                                  "cohort": "registered" if channel == "primary" else "control",
                                  "deterministicUnderAssumptions": True, "assumptions": [
                                      "An isolated local loader owns the declared resource directories and fixture classes.",
                                      "Each invocation starts in a fresh process on its ordered releases and fixed JDK."]})
            change_evidence.write_json(dest / "workflows.json",
                                       {"schema": "caller-workflows/v1", "change": entry, "workflows": workflows})
            record.update(stage="registered before populated JVM trials", resources=names,
                          probeSha256=upgrade_replay.sha(probe), workflowsSha256=upgrade_replay.sha(dest / "workflows.json"),
                          scopeSha256={w["id"]: upgrade_replay.sha(dest / w["scope"]) for w in workflows})
            change_evidence.write_json(dest / "registration.json", record)
            compile_observer(work / "populated", probe, graphs["old"], jdk)
            record["physical"] = {}
            for side, files in graphs.items():
                trials = []
                record["physical"][side] = trials
                for w in workflows:
                    for case in json.loads((dest / w["scope"]).read_bytes())["cases"]:
                        args = case["args"]
                        value = physical(work, work / "populated", jdk, files, args)
                        expected = expectation(target[2], queries[side], names, args)
                        trials.append({"args": args, "actual": value, "expected": expected})
            record["stage"] = "original JVM controls passed" if all(r["actual"] == r["expected"] for v in record["physical"].values() for r in v) else "registered prediction refuted on an original JVM"
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        record["firstScaffoldStop"] = str(error)
    change_evidence.write_json(dest / "scaffold.json", record)
    return record


def discover(before, after, jdk, dest):
    paths, packet = {}, {}
    for side, file in (("old", before), ("new", after)):
        doc = json.loads(file.read_bytes())
        files, _, hashes = upgrade_replay.checked_classpath(file, doc, doc["classpath"][0]["sha256"])
        paths[side], packet[side] = files, hashes
    feature = int(runtime_jdk.identity(jdk)["feature"])
    old, new = (candidates(paths[s][0], feature) for s in ("old", "new"))
    dest.mkdir(parents=True, exist_ok=False)
    rows = []
    for i, name in enumerate(sorted(old.keys() & new.keys())):
        child = f"candidate-{i + 1}"
        row = discover_entry(name, old[name], paths, jdk, dest / child)
        rows.append({"directory": child, "entry": name, "stage": row["stage"], "firstScaffoldStop": row.get("firstScaffoldStop")})
    report = {"inputs": packet, "jdkRelease": upgrade_replay.sha(jdk / "release"),
              "jdkImage": change_inventory.jdk_binding(jdk), "candidates": rows,
              "firstScaffoldStop": None if rows else "no common public static resource-enumerating method of a supported shape"}
    change_evidence.write_json(dest / "discovery.json", report)
    return report


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("before", "after", "jdk", "output"):
        parser.add_argument("--" + arg, type=Path, required=True)
    args = parser.parse_args(argv)
    report = discover(args.before, args.after, args.jdk.resolve(), args.output.resolve())
    print(report["firstScaffoldStop"] or [(r["entry"], r["stage"]) for r in report["candidates"]])
    return 0
