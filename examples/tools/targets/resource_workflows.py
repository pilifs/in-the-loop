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

from targets import change_evidence, change_inventory, entry_discovery, runtime_jar, runtime_jdk, upgrade_replay

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
    body = (f'if (Boolean.getBoolean("entry.resource.trace")) System.out.println("RESOURCE-ENTRY\\t" + '
            f'{owner.replace("$", ".")}.class.getClassLoader().getClass().getName() + "\\t" + '
            f'{owner.replace("$", ".")}.class.getProtectionDomain().getCodeSource().getLocation());\n' + body)
    return TEMPLATE.read_text().replace("INVOCATION", body).replace("RESOURCE_NAMES", ", ".join(map(json.dumps, names)))


def compile_observer(work, probe, files, jdk):
    work.mkdir()
    runner = work / "ReadLookup.java"
    runner.write_text(CALLER)
    args = [jdk / "bin/javac", "-J-XX:-UsePerfData", "-proc:none", "-g", "-cp", os.pathsep.join(map(str, files)),
            "-d", work, runner, probe]
    subprocess.run(args, check=True, capture_output=True, timeout=30)


def physical(work, compiled, jdk, files, inputs, *, trace=None):
    cp = os.pathsep.join(map(str, [compiled, *files]))
    cmd = [jdk / "bin/java", "-Xmx256m", "-XX:-UsePerfData", "-Duser.language=en", "-Duser.country=US",
           "-Duser.timezone=UTC", "-Djava.io.tmpdir=" + str(work), "-cp", cp, "ReadLookup", *inputs]
    if trace is not None:
        cmd.insert(1, "-Dentry.resource.trace=true")
    proc = subprocess.run(cmd, cwd=work, text=True, capture_output=True, timeout=25,
                          env={"HOME": str(work), "PATH": str(jdk / "bin") + ":/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC"})
    rows = [s[7:] for s in proc.stdout.splitlines() if s.startswith("LOOKUP ")]
    if proc.returncode or len(rows) != 1:
        raise ValueError("original caller did not return a unique observation: " + proc.stderr[-600:])
    if trace is not None:
        for line in proc.stdout.splitlines():
            if line.startswith(("RESOURCE-ENTRY\t", "RESOURCE-REQUEST\t", "RESOURCE-ORIGIN\t")):
                trace.append(line.split("\t"))
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
                        trace = []
                        value = physical(work, work / "populated", jdk, files, args, trace=trace)
                        expected = expectation(target[2], queries[side], names, args)
                        trials.append({"args": args, "actual": value, "expected": expected, "lookupTrace": trace})
            record["stage"] = "original JVM controls passed" if all(r["actual"] == r["expected"] for v in record["physical"].values() for r in v) else "registered prediction refuted on an original JVM"
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        record["firstScaffoldStop"] = str(error)
    change_evidence.write_json(dest / "scaffold.json", record)
    return record


def discover(before, after, jdk, dest):
    paths, packet, views, graphs = {}, {}, {}, {}
    feature = int(runtime_jdk.identity(jdk)["feature"])
    dest.mkdir(parents=True, exist_ok=False)
    index = entry_discovery.Index()
    image = change_inventory.jdk_binding(jdk)
    selected = {}
    for side, file in (("old", before), ("new", after)):
        files, launch = change_inventory.resolve(file, jdk, image, {}, kind="production", layout_cache=dest / "deployment-layouts", index=index)
        hashes = [p["sha256"] for p in launch["classpath"]]
        paths[side], packet[side], graphs[side] = files, hashes, launch
        views[side] = view = index.view(files, hashes, feature)
        found = selected[side] = {}
        for owner, (_, definition) in view.winners.items():
            if b"getResources" not in definition.data or not runtime_jar.class_flags(definition.data) & 1:
                continue
            for (method, descriptor), (flags, calls) in definition.methods().items():
                if flags & 9 == 9 and descriptor in SHAPES and ENUMERATE in calls:
                    dotted = owner.replace("/", ".")
                    found[dotted + "#" + method + descriptor] = (dotted, method, SHAPES[descriptor])
    rows = []
    for i, name in enumerate(sorted(selected["old"].keys() | selected["new"].keys())):
        sides = [s for s in selected if name in selected[s]]
        row = {"entry": name, "origins": {s: views[s].origins(name.split("#")[0].replace(".", "/")) for s in sides}}
        unresolved = {s: graphs[s]["manifestClassPath"]["unresolved"] for s in sides if graphs[s]["manifestClassPath"]["unresolved"]}
        if len(sides) == 1 or unresolved:
            owner, method, descriptor = runtime_jar.parse_target(name)
            internal = runtime_jar.internal(owner)
            declarations = {}
            for side, view in views.items():
                winning = view.winners.get(internal)
                members = winning[1].methods() if winning else {}
                declarations[side] = [{"descriptor": desc, **entry_discovery.access(flags)}
                                      for (n, desc), (flags, _) in sorted(members.items()) if n == method]
            row.update(stage="open", declarationsBySide=declarations,
                       firstScaffoldStop=unresolved or f"exact descriptor {descriptor} present only on {sides[0]}")

        else:
            child = f"candidate-{i + 1}"
            result = discover_entry(name, selected["old"][name], paths, jdk, dest / child)
            row.update(directory=child, stage=result["stage"], firstScaffoldStop=result.get("firstScaffoldStop"))
        rows.append(row)
    report = {"inputs": packet, "graphs": graphs, "coverage": index.coverage(), "jdkRelease": upgrade_replay.sha(jdk / "release"),
              "jdkImage": image, "candidates": rows, "firstScaffoldStop": None if rows else
              "no common public static resource-enumerating method of a supported shape"}
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
