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


def lookup(arguments, marker, files, jdk, helpers, temp, env, deadline):
    proc = subprocess.run([str(jdk/"bin/java"), "-Xmx64m", "-Djava.io.tmpdir="+str(temp),
                           "-classpath", os.pathsep.join(map(str, [helpers, *files])), "UpgradeClassLookup", *arguments],
                          cwd=temp, env=env, capture_output=True, text=True, check=True,
                          timeout=max(0.01, deadline - time.monotonic()))
    marks = [s[len(marker):] for s in proc.stdout.splitlines() if s.startswith(marker)]
    if len(marks) != 1:
        raise ValueError("the fresh JVM did not report exactly one lookup")
    return marks[0]


def file_binding(origin, files, binding):
    if origin.startswith("file:"):
        path = Path(unquote(urlsplit(origin).path)).resolve()
        if path in files:
            index = files.index(path)
            return {"classpathIndex": index, "jarSha256": binding["classpath"][index]}
    return {}


def inspect_side(name, prepared, feature, jdk, helpers, temp, env, deadline):
    files, operand, binding = prepared
    state, _, origin = lookup([name], "UPGRADE-LOOKUP ", files, jdk, helpers, temp, env, deadline).partition(" ")
    resolution = {"outcome": state}
    if state == "found":
        resolution.update(file_binding(origin, files, binding))
    if state == "linkage":
        resolution["error"] = origin
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
    return {"lookup": resolution, "providers": providers, "referringClassesInUpgrade": users}


MEMBER_ERRORS = {"java.lang.NoSuchFieldError", "java.lang.NoSuchMethodError", "java.lang.IncompatibleClassChangeError"}


def observed_member(failure, loaded, files, binding, feature):
    if not failure["causes"] or failure["causes"][-1] not in MEMBER_ERRORS:
        return
    event = failure if len(failure["causes"]) == 1 else failure.get("rootThrow", {})
    frame = event.get("throwLocation")
    if not frame:
        return
    owner, name, descriptor = runtime_jar.parse_target(frame["entry"])
    data = runtime_jar.effective_class(files[frame["classpathIndex"]], runtime_jar.internal(owner), feature)
    if data is None:
        return
    operand = runtime_jar.member_at_code_index(data, name, descriptor, frame["codeIndex"],
                code_sha256=frame.get("methodCodeSha256"), pool_sha256=frame.get("constantPoolSha256"))
    if not operand:
        return
    origins = loaded.get(operand["owner"], set())
    if len(origins) == 1 and next(iter(origins)) in files:
        index = files.index(next(iter(origins)))
        failure["memberInstruction"] = {**operand, "location": frame, "executingClassSha256": hashlib.sha256(data).hexdigest(),
                                        "ownerJarSha256": binding["classpath"][index]}


def compare_member(instruction, error, prepared, feature, jdk, helpers, temp, env, deadline):
    owner, name, desc, opcode = (instruction[k] for k in ("owner", "name", "descriptor", "opcode"))
    caller = runtime_jar.internal(instruction["location"]["entry"].partition("#")[0])
    sides = {}
    for side, (files, _, binding) in prepared.items():
        response = lookup([owner, name, desc, opcode], "UPGRADE-MEMBER ", files, jdk, helpers, temp, env, deadline)
        status, kind, origin = response.split(" ", 2)
        result = {"lookup": status, "ownerKind": kind, **file_binding(origin, files, binding)}
        if "jarSha256" not in result:
            return None
        # Use the executing class from the captured event on the new side, and classpath order on the old.
        candidates = [files[instruction["location"]["classpathIndex"]]] if side == "new" else files
        for jar in candidates:
            data = runtime_jar.effective_class(jar, caller, feature)
            if data is not None:
                result["executingClassSha256"] = hashlib.sha256(data).hexdigest()
                result["referenceKinds"] = runtime_jar.member_reference_kinds(data, (runtime_jar.internal(owner), name, desc))
                break
        sides[side] = result
    new = sides["new"]
    if (new["jarSha256"] != instruction["ownerJarSha256"] or new.get("executingClassSha256") != instruction["executingClassSha256"]
            or instruction["referenceKind"] not in new.get("referenceKinds", [])):
        return None
    if error == "java.lang.IncompatibleClassChangeError" and opcode == "invokeinterface" and new["ownerKind"] == "class":
        reason = "interface invocation resolved to a class"
    elif (new["lookup"] == "missing" and error == ("java.lang.NoSuchMethodError" if desc.startswith("(") else "java.lang.NoSuchFieldError")):
        reason = "the member at the throwing instruction is absent"
    else:
        return None
    return {"reason": reason, "instruction": instruction, "sides": sides}


def diagnose(report, prepared, old_loaded, feature, jdk, helpers, temp, env, deadline):
    evidence = {}
    members = {}
    for row in report["beforeEntryComparison"]:
        index = row["input"]
        before, after = (report["sides"][s]["trials"][index] for s in ("old", "new"))
        if (not after.get("repeatableBeforeEntry") or
                before["qualifiedMethodEntries"] != 2 or before["observations"] != [report["cases"][index]["expected"]] * 2):
            continue
        failure = after["beforeEntry"][0]
        instruction = failure.get("memberInstruction")
        if instruction:
            error = failure["causes"][-1]
            key = (instruction["location"]["entry"], instruction["location"]["codeIndex"], error)
            if key not in members:
                try:
                    members[key] = compare_member(instruction, error, prepared, feature, jdk, helpers, temp, env, deadline)
                except (ValueError, OSError, subprocess.SubprocessError, zipfile.BadZipFile):
                    members[key] = None
            if members[key]:
                row["memberLinkage"] = members[key]
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
