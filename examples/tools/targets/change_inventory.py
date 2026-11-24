"""Inventory both deployments before looking at any historical outcome."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

from targets import runtime_jar, runtime_jdk, upgrade_claims, upgrade_replay


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def file_digest(path):
    if path.is_dir():
        return digest([(p.relative_to(path).as_posix(), upgrade_replay.sha(p))
                       for p in sorted(path.rglob("*")) if p.is_file()])
    return upgrade_replay.sha(path)


def jdk_binding(jdk):
    # The launcher, VM, boot classes, compiler, timezone data and security configuration
    # all participate. JDK 8 keeps the runtime under jre, modular JDKs under lib.
    roots = ["bin", "conf", "lib", "jre", "release"]
    contents = {name: file_digest(jdk / name) for name in roots if (jdk / name).exists()}
    if not ((jdk / "jre/lib/rt.jar").is_file() or (jdk / "lib/modules").is_file()):
        raise ValueError(f"{jdk} has no supported runtime image")
    return {"release": runtime_jdk.identity(jdk)["release"], "image": digest(contents)}


def resolve(path, jdk, image, environment, *, kind):
    document = json.loads(path.read_text())
    files, entries = [], []
    for entry in document["classpath"]:
        file = (path.parent / entry["file"]).resolve()
        actual = file_digest(file)
        if actual != entry["sha256"]:
            raise ValueError(f"{kind} classpath differs at {file.name}")
        files.append(file)
        entries.append({"name": file.name, "sha256": actual})
    if not files:
        raise ValueError(f"empty {kind} classpath")
    if pin := document.get("jdkReleaseSha256"):
        if upgrade_replay.sha(jdk / "release") != pin:
            raise ValueError(f"the JDK differs from the prepared {kind} launch")
    binding = {"kind": kind, "jdk": image, "classpath": entries, "environment": environment}
    return files, {**binding, "key": digest(binding), "commit": document.get("commit"),
                   "sourceSha256": document.get("sourceSha256"), "preparation": document.get("scope")}


def entries(path, feature):
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file():
                yield child.relative_to(path).as_posix(), child.read_bytes()
    else:
        with zipfile.ZipFile(path) as jar:
            for name, info in runtime_jar.effective_entries(jar, feature).items():
                if not name.startswith("META-INF/versions/"):
                    yield name, jar.read(info)


def deployment(files, jdk):
    feature = int(runtime_jdk.identity(jdk)["feature"])
    classes, resources, methods = {}, {}, {}
    implicit = []
    for position, file in enumerate(files):
        for name, data in entries(file, feature):
            sha = hashlib.sha256(data).hexdigest()
            if name == "META-INF/MANIFEST.MF":
                main = data.replace(b"\r\n", b"\n").split(b"\n\n", 1)[0].replace(b"\n ", b"")
                if any(line.lower().startswith(b"class-path:") and line.partition(b":")[2].strip()
                       for line in main.splitlines()):
                    implicit.append(file.name)
            if not name.endswith(".class"):
                # getResources and ServiceLoader can observe all providers in order.
                resources.setdefault(name, []).append(sha)
                continue
            if name.endswith("module-info.class") or name.startswith("META-INF/"):
                continue
            owner = name[:-6]
            classes.setdefault(owner, sha)
            if position:
                continue
            listing = upgrade_claims.disassemble(jdk, files, owner, 30)
            calls = upgrade_claims.calls_in_methods(listing, owner)
            for method, descriptor in runtime_jar.methods(data):
                flags = runtime_jar.method_flags(data, method, descriptor)
                if method.startswith("<") or flags & (0x0040 | 0x1000):
                    continue
                member = (owner, method, descriptor)
                methods[member] = {"calls": sorted(set(calls.get((method, descriptor), []))),
                                   "public": bool(flags & (0x0001 | 0x0004)), "classSha256": sha}
    return classes, resources, methods, implicit


def entry_name(member):
    owner, method, descriptor = member
    return owner.replace("/", ".") + "#" + method + descriptor


def reach(root, methods):
    visited, frontier, boundary = set(), [root], set()
    while frontier:
        member = frontier.pop()
        if member in visited:
            continue
        visited.add(member)
        for called in methods[member]["calls"]:
            if called in methods:
                frontier.append(called)
            else:
                boundary.add(called)
    return visited, boundary


def inventory(old, new, declared):
    changed = {name for name in old[0].keys() | new[0].keys() if old[0].get(name) != new[0].get(name)}
    resources = sorted(k for k in old[1].keys() | new[1].keys() if old[1].get(k) != new[1].get(k))
    roots = []
    for member in sorted(old[2].keys() | new[2].keys()):
        entry = entry_name(member)
        why, sides = set(), {}
        for side, snapshot in (("old", old), ("new", new)):
            if member not in snapshot[2]:
                continue
            local, boundary = reach(member, snapshot[2])
            direct = sorted(entry_name(c) for c in boundary if c[0] in changed)
            dependencies = sorted(entry_name(c) for c in boundary if c[0] in snapshot[0])
            sides[side] = {"callerClassSha256": snapshot[2][member]["classSha256"],
                           "changedBoundaryCalls": direct, "dependencyCalls": dependencies}
            if direct or any(m[0] in changed for m in local):
                why.add("reachable changed class")
            if snapshot[2][member]["public"]:
                why.add("public or protected consumer operation")
            if dependencies:
                why.add("consumer reaches a runtime dependency")
        if len(sides) == 1:
            why.add("added or removed declaration")
        if entry in declared:
            why.add("declared workflow")
        if why:
            roots.append({"entry": entry, "basis": sorted(why), "sides": sides,
                          "disposition": "planned" if entry in declared else "open",
                          "reason": "finite caller observation supplied" if entry in declared
                          else "receiver, domain and intended observation have not been supplied"})
    return {"method": "Public operations and transitive calls within each compiled client, on either deployment.",
            "unknownEdges": "Virtual dispatch, initialization, reflection, resources and calls through dependencies can reach other code. Exact reuse binds the whole declared launch.",
            "changedClasses": sorted(changed), "changedResources": resources,
            "implicitClasspaths": {"old": old[3], "new": new[3]}, "candidates": roots,
            "discoveryMisses": sorted(declared - {r["entry"] for r in roots})}


def framework_inventory(checker, paths, jdk):
    """Use the application's existing comparator on each client's own ordered deployment."""
    env = {**os.environ, "JAVA_HOME": str(jdk), "JVMCONTRACT_JAR_RELEASE": runtime_jdk.identity(jdk)["feature"]}
    def observations(side, *args):
        files = paths[side]
        argv = [checker, "observations", "--json", files[0]]
        for dependency in files[1:]:
            argv.extend(["--classpath", dependency])
        return json.loads(subprocess.check_output([*argv, *args], env=env, text=True, timeout=60))

    with tempfile.TemporaryDirectory(prefix="change-observations-") as temporary:
        old, new = observations("old"), observations("new")
        before = Path(temporary) / "old.json"
        before.write_text(json.dumps(old))
        obligations = observations("new", "--against", before)
    return {"old": old, "new": new,
            "obligations": [{"obligation": o, "disposition": "open",
                             "reason": "entry comparison identifies an observation to check"} for o in obligations]}
