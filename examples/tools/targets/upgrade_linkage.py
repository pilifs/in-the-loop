"""Corroborate a caller's missing-class exception against both original JVM classpaths."""

import hashlib
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import unquote, urlsplit
import zipfile

from targets import runtime_jar


def inspect_side(name, prepared, feature, jdk, helpers, temp, env, deadline):
    files, operand, binding = prepared
    proc = subprocess.run([str(jdk/"bin/java"), "-Xmx64m", "-Djava.io.tmpdir="+str(temp),
                           "-classpath", os.pathsep.join(map(str, [helpers, *files])), "UpgradeClassLookup", name],
                          cwd=temp, env=env, capture_output=True, text=True, check=True,
                          timeout=max(0.01, deadline - time.monotonic()))
    marks = [s.removeprefix("UPGRADE-LOOKUP ") for s in proc.stdout.splitlines() if s.startswith("UPGRADE-LOOKUP ")]
    if len(marks) != 1:
        raise ValueError("the fresh JVM did not report exactly one class lookup")
    state, _, origin = marks[0].partition(" ")
    lookup = {"outcome": state}
    if state == "found" and origin.startswith("file:"):
        path = Path(unquote(urlsplit(origin).path)).resolve()
        if path in files:
            lookup["classpathIndex"] = files.index(path)
            lookup["jarSha256"] = binding["classpath"][files.index(path)]
    if state == "linkage":
        lookup["error"] = origin
    target = name.replace(".", "/")
    providers, users = [], []
    for index, jar in enumerate(files):
        with zipfile.ZipFile(jar) as archive:
            entries = runtime_jar.effective_entries(archive, feature)
            entry = entries.get(target+".class")
            if entry is not None:
                data = archive.read(entry)
                if runtime_jar.this_class(data) != target:
                    raise ValueError("a provider entry declares a different class")
                providers.append({"classpathIndex": index, "jarSha256": binding["classpath"][index],
                                  "classSha256": hashlib.sha256(data).hexdigest()})
            if jar == operand:
                for filename, member in sorted(entries.items()):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("missing-class inspection reached the case deadline")
                    if not filename.endswith(".class") or filename.startswith("META-INF/") or filename == target+".class":
                        continue
                    data = archive.read(member)
                    if target.encode("ascii") not in data:
                        continue
                    refs = runtime_jar.type_references(data, target)
                    if refs["kinds"]:
                        users.append({"class": filename[:-6].replace("/", "."), **refs,
                                      "classSha256": hashlib.sha256(data).hexdigest()})
        if time.monotonic() >= deadline:
            raise TimeoutError("missing-class inspection reached the case deadline")
    return {"lookup": lookup, "providers": providers, "referringClassesInUpgrade": users}


def diagnose(report, prepared, old_loaded, feature, jdk, helpers, temp, env, deadline):
    evidence = {}
    for row in report["beforeEntryComparison"]:
        index = row["input"]
        before, after = (report["sides"][s]["trials"][index] for s in ("old", "new"))
        if (not after.get("repeatableBeforeEntry") or
                before["qualifiedMethodEntries"] != 2 or before["observations"] != [report["cases"][index]["expected"]] * 2):
            continue
        failure = after["beforeEntry"][0]
        if failure["causes"][-1:] != ["java.lang.ClassNotFoundException"]:
            continue
        name = failure.get("lastCauseMessage", "")
        if "/" in name and "." not in name:
            name = name.replace("/", ".")
        if not re.fullmatch(r"(?:[A-Za-z_$][\w$]*\.)*[A-Za-z_$][\w$]*", name, re.ASCII):
            continue
        if name not in evidence:
            try:
                evidence[name] = {s: inspect_side(name, values, feature, jdk, helpers, temp, env, deadline)
                                  for s, values in prepared.items()}
            except (ValueError, OSError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
                evidence[name] = {"open": str(exc)}
        binding = evidence[name]
        if "open" in binding:
            continue
        old, new = binding["old"], binding["new"]
        if new["lookup"]["outcome"] != "missing" or new["providers"]:
            continue
        if (old["lookup"].get("jarSha256") == report["sides"]["old"]["dependency"] and old["providers"]
                and name in old_loaded[index]):
            relationship = "old upgraded artifact supplied the missing class"
        elif (after["loadedUpgradeOnEachReplay"] and old["lookup"]["outcome"] == "missing" and not old["providers"]
              and not old["referringClassesInUpgrade"] and new["referringClassesInUpgrade"]):
            relationship = "new upgraded artifact references a class absent on both classpaths"
        else:
            continue
        # Some VM-generated linkage errors yield no debugger throw event. Independent
        # lookups can establish class availability while the originating frame stays open.
        row["missingClass"] = {"name": name, "relationship": relationship,
                               "loadedFromOldUpgradeOnBothCallerReplays": name in old_loaded[index],
                               "matchedThrowEvent": failure["observerCodeIndex"] is not None}
    if evidence:
        report["missingClassEvidence"] = evidence
