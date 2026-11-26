"""Inventory both deployments before looking at any historical outcome."""

import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zipfile

from targets import deployment_graph, runtime_jar, runtime_jdk, upgrade_replay


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


def manifest_classpath(files, feature):
    """Compatibility view for a launch whose declared files already occupy their deployment locations."""
    document = {"classpath": [{"file": str(file.absolute()), "sha256": file_digest(file)} for file in files]}
    _, _, graph = deployment_graph.resolve(document, Path.cwd(), feature, file_digest)
    return graph["manifestClassPath"]


def absences_hold(paths):
    for path in paths:
        try:
            os.stat(path)
        except (FileNotFoundError, NotADirectoryError):
            continue
        except OSError:
            pass
        return False
    return True


def changed_inputs(launches):
    expected = {}
    for launch in launches:
        for row in launch["classpath"]:
            expected[row["file"]] = row["sha256"]
            expected[row["originalFile"]] = row["sha256"]
        for row in launch.get("environmentFiles", []):
            expected[row["file"]] = row["sha256"]
    changed = []
    for name, sha in expected.items():
        try:
            if file_digest(Path(name)) == sha:
                continue
        except OSError:
            pass
        changed.append(name)
    return changed


def resolve(path, jdk, image, environment, *, kind, layout_cache=None, index=None):
    document = json.loads(path.read_text())
    feature = int(runtime_jdk.identity(jdk)["feature"])
    files, entries, graph = deployment_graph.resolve(document, path.parent, feature, file_digest, layout_cache=layout_cache, index=index)
    if pin := document.get("jdkReleaseSha256"):
        if upgrade_replay.sha(jdk / "release") != pin:
            raise ValueError(f"the JDK differs from the prepared {kind} launch")
    external = []
    for item in document.get("environmentFiles", []):
        file = (path.parent / item["file"]).resolve()
        actual = file_digest(file)
        if actual != item["sha256"]:
            raise ValueError(f"{kind} environment file differs at {file.name}")
        external.append({"file": str(file), "sha256": actual})
    binding = {"kind": kind, "jdk": image, "classpath": entries, "environment": environment, **graph}
    if "jvmFlags" in document:
        flags = document["jvmFlags"]
        if not isinstance(flags, list) or any(not isinstance(f, str) or not re.fullmatch(
                r"-(?:ea|da|XX:-UsePerfData|Xmx[1-9][0-9]*[mMgG]|D(?:user\.(?:timezone|country|language)|file\.encoding|java\.awt\.headless)=[A-Za-z0-9_./+-]+)", f)
                for f in flags):
            raise ValueError("unsupported original JVM profile flag")
        binding["jvmFlags"] = flags
    if external:
        binding["environmentFiles"] = external
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


def instructions(body):
    """Yield instruction boundaries, including aligned switch tables and widened locals."""
    pc = 0
    while pc < len(body):
        op = body[pc]
        if op in (0xaa, 0xab):
            base = (pc + 4) & ~3
            if op == 0xaa:
                low, high = struct.unpack_from(">ii", body, base+4)
                if high < low:
                    raise ValueError("invalid tableswitch")
                end = base + 12 + 4*(high-low+1)
            else:
                count, = struct.unpack_from(">i", body, base+4)
                if count < 0:
                    raise ValueError("invalid lookupswitch")
                end = base + 8 + 8*count
        elif op == 0xc4:
            end = pc + (6 if body[pc+1] == 0x84 else 4)
        else:
            end = pc + INSTRUCTION_BYTES[op]
        if end > len(body):
            raise ValueError("truncated instruction in application inventory")
        yield pc, op
        pc = end


def invocation_inventory(data):
    """Read resolved calls from instruction boundaries in the selected class file."""
    pool, declarations, _ = runtime_jar._declarations(data, with_code=True)
    for (method, descriptor), (flags, body, _) in declarations.items():
        if method.startswith("<") or flags & (0x0040 | 0x1000):
            continue
        calls = set()
        for pc, op in instructions(body or b""):
            if 0xb6 <= op <= 0xb9:
                index = int.from_bytes(body[pc+1:pc+3], "big")
                tag, ref = pool[index]
                if tag not in (10, 11):
                    raise ValueError("invalid method reference in application inventory")
                calls.add(runtime_jar._member_ref(pool, ref))
        yield method, descriptor, flags, sorted(calls)


# JVM instructions with inline operands. Switch and wide are variable length.
INSTRUCTION_BYTES = [1] * 256
for width, opcodes in (
        (2, (0x10, 0x12, *range(0x15, 0x1a), *range(0x36, 0x3b), 0xa9, 0xbc)),
        (3, (0x11, 0x13, 0x14, 0x84, *range(0x99, 0xa9), *range(0xb2, 0xb9),
             0xbb, 0xbd, 0xc0, 0xc1, 0xc6, 0xc7)),
        (4, (0xc5,)), (5, (0xb9, 0xba, 0xc8, 0xc9))):
    for opcode in opcodes:
        INSTRUCTION_BYTES[opcode] = width


def deployment(files, jdk):
    from targets import entry_discovery
    index = entry_discovery.Index()
    view = index.view(files, [file_digest(f) for f in files], int(runtime_jdk.identity(jdk)["feature"]))
    classes, methods = {}, {}
    for owner, (_, definition) in view.winners.items():
        classes[owner] = definition.sha
        for (name, desc), (flags, calls) in definition.methods().items():
            methods[owner, name, desc] = {"calls": calls, "public": bool(flags & 5), "classSha256": definition.sha}
    implicit = [file.name for file in files if deployment_graph.manifest(file, int(runtime_jdk.identity(jdk)["feature"]))[0]]
    return classes, view.resources, methods, implicit


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
        discovered = bool(why)
        if entry in declared:
            why.add("declared workflow")
        if why:
            roots.append({"entry": entry, "basis": sorted(why), "independentlyDiscovered": discovered, "sides": sides,
                          "disposition": "planned" if entry in declared else "open",
                          "reason": "finite caller observation supplied" if entry in declared
                          else "receiver, domain and intended observation have not been supplied"})
    return {"method": "Public operations and transitive calls within each compiled client, on either deployment.",
            "unknownEdges": "Virtual dispatch, initialization, reflection, resources and calls through dependencies can reach other code. Exact reuse binds the whole declared launch.",
            "changedClasses": sorted(changed), "changedResources": resources,
            "implicitClasspaths": {"old": old[3], "new": new[3]}, "candidates": roots,
            "discoveryMisses": sorted(declared - {r["entry"] for r in roots if r["independentlyDiscovered"]})}


def framework_inventory(checker, paths, jdks):
    """Use the application's existing comparator on each client's own ordered deployment."""
    def observations(side, *args):
        jdk = jdks[side]
        env = {**os.environ, "JAVA_HOME": str(jdk), "JVMCONTRACT_JAR_RELEASE": runtime_jdk.identity(jdk)["feature"]}
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
