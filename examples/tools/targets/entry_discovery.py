"""Index the physical artifacts once, then rank exact public callers in each ordered JVM view."""
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import struct
import sys
import zipfile

from targets import class_binding, runtime_jar
from targets.change_inventory import entry_name, instructions


def selector(owner, name, descriptor):
    return tuple(map(sys.intern, (owner, name, descriptor)))


@dataclass(slots=True)
class Definition:
    entry: str
    sha: str
    release: int
    data: bytes
    declarations: object = None

    def methods(self):
        if self.declarations is None:
            pool, methods, _ = runtime_jar._declarations(self.data, with_code=True)
            self.declarations = {}
            for (name, desc), (flags, code, _) in methods.items():
                calls = set()
                for pc, op in instructions(code or b""):
                    if 0xb6 <= op <= 0xb9:
                        index = int.from_bytes(code[pc+1:pc+3], "big")
                        calls.add(selector(*runtime_jar._member_ref(pool, pool[index][1])))
                self.declarations[(sys.intern(name), sys.intern(desc))] = (flags, tuple(sorted(calls)))
        return self.declarations


def fingerprints(definition):
    """Instruction operands use resolved pool constants. Unmodelled bootstrap or handler changes stay class-level."""
    pool, methods, _ = runtime_jar._declarations(definition.data, with_code=True)
    resolved = {}
    def constant(i):
        if i not in resolved:
            tag, value = pool[i]
            if tag in (7, 8, 16, 19, 20):
                value = constant(value)
            elif tag in (9, 10, 11, 12):
                value = tuple(constant(k) for k in value)
            elif tag in (17, 18):
                value = (value[0], constant(value[1]))
            elif tag == 15:
                value = (value[0], constant(int.from_bytes(value[1:], "big")))
            resolved[i] = (tag, value)
        return resolved[i]
    output = {}
    for key, (flags, code, handlers) in methods.items():
        normalized, uncertain = [], bool(handlers)
        code = code or b""
        positions = [*instructions(code), (len(code), 0)]
        for (pc, op), (end, _) in zip(positions, positions[1:]):
            operand = code[pc+1:end]
            if op in (0x12, 0x13, 0x14, *range(0xb2, 0xbc), 0xbd, 0xc0, 0xc1, 0xc5):
                width = 1 if op == 0x12 else 2
                ref = constant(int.from_bytes(operand[:width], "big"))
                uncertain |= ref[0] in (17, 18)
                operand = (ref, operand[width:])
            normalized.append((op, operand))
        output[key] = (hashlib.sha256(repr((flags, normalized)).encode()).hexdigest(), uncertain)
    return output


class Artifact:
    def __init__(self, file):
        self.classes = defaultdict(list)
        self.resources = defaultdict(list)
        self.skipped = []
        self.multi = "disabled"
        def add(name, data):
            if name.upper() == "META-INF/MANIFEST.MF" and not file.is_dir():
                self.multi = runtime_jar.multi_release(data)
            variant = class_binding.VERSIONED.fullmatch(name) if not file.is_dir() else None
            logical = variant[2] if variant else name
            release = int(variant[1]) if variant else 0
            sha = hashlib.sha256(data).hexdigest()
            if not logical.endswith(".class"):
                self.resources[logical].append((release, sha))
            elif logical.endswith("module-info.class") or logical.startswith("META-INF/"):
                self.skipped.append((name, "module descriptor or non-loadable class name"))
            else:
                self.classes[sys.intern(logical[:-6])].append(Definition(name, sha, release, data))
        if file.is_dir():
            for child in sorted(file.rglob("*")):
                if child.is_file():
                    add(child.relative_to(file).as_posix(), child.read_bytes())
        else:
            with zipfile.ZipFile(file) as archive:
                for info in archive.infolist():
                    if not info.is_dir():
                        add(info.filename, archive.read(info))

    def eligible(self, release, feature):
        return release == 0 or self.multi == "enabled" and 9 <= release <= feature


class Index:
    def __init__(self):
        self.artifacts = {}

    def view(self, files, hashes, feature):
        winners, physical, resources = {}, defaultdict(list), defaultdict(list)
        for i, (file, sha) in enumerate(zip(files, hashes, strict=True)):
            if sha not in self.artifacts:
                self.artifacts[sha] = Artifact(file)
            artifact = self.artifacts[sha]
            for owner, defs in artifact.classes.items():
                physical[owner].extend((i, d) for d in defs)
                eligible = [d for d in defs if artifact.eligible(d.release, feature)]
                if eligible and owner not in winners:
                    winners[owner] = (i, max(eligible, key=lambda d: d.release))
            for name, versions in artifact.resources.items():
                eligible = [v for v in versions if artifact.eligible(v[0], feature)]
                if eligible:
                    resources[name].append(max(eligible)[1])
        return View(winners, physical, resources, hashes)

    def coverage(self):
        return {"archiveScans": len(self.artifacts), "artifacts": {
            sha: {"classes": len(a.classes), "physicalDefinitions": sum(map(len, a.classes.values())),
                  "skipped": a.skipped} for sha, a in self.artifacts.items()}}


@dataclass
class View:
    winners: dict
    physical: dict
    resources: dict
    hashes: list

    def origins(self, owner):
        winner = self.winners.get(owner)
        return [{"index": i, "artifactSha256": self.hashes[i], "entry": d.entry, "classSha256": d.sha,
                 "release": d.release or None, "selected": bool(winner and winner[0] == i and winner[1] is d)}
                for i, d in self.physical.get(owner, [])]


def changes(old, new):
    rows, targets, class_only = [], set(), []
    for owner in sorted(old.physical.keys() | new.physical.keys()):
        before, after = old.winners.get(owner), new.winners.get(owner)
        old_defs = [(i, d.entry, d.sha) for i, d in old.physical.get(owner, ())]
        new_defs = [(i, d.entry, d.sha) for i, d in new.physical.get(owner, ())]
        if old_defs == new_defs:
            continue
        old_methods = fingerprints(before[1]) if before else {}
        new_methods = fingerprints(after[1]) if after else {}
        differences = []
        for name, desc in sorted(old_methods.keys() | new_methods.keys()):
            a, b = old_methods.get((name, desc)), new_methods.get((name, desc))
            if a == b:
                continue
            member = selector(owner, name, desc)
            targets.add(member)
            differences.append({"entry": entry_name(member), "change": "added" if a is None else "removed" if b is None else "changed",
                                "sides": {s: {"bodyDigest": fp[0], "access": item[1].methods()[name, desc][0]}
                                          for s, fp, item in (("old", a, before), ("new", b, after)) if fp}})
        if before and after and before[1].sha != after[1].sha and (
                not differences or any(f[1] for f in [*old_methods.values(), *new_methods.values()])):
            class_only.append(owner)
        rows.append({"owner": owner, "old": old.origins(owner), "new": new.origins(owner), "selectors": differences,
                     "providerMoved": bool(before and after and before[0] != after[0]),
                     "effectiveBytesChanged": (before[1].sha if before else None) != (after[1].sha if after else None)})
    return rows, targets, class_only


def callers(view, targets):
    # Examine only classes whose constant pool can name a reachable owner. The exact opcode, owner and descriptor
    # must then match. This avoids building a graph of all unrelated methods on a large deployment.
    routes = {}
    frontier = {m: (m,) for m in targets if m[0] in view.winners and m[1:] in view.winners[m[0]][1].methods()}
    seen = set(frontier)
    reverse = defaultdict(set)
    scanned = set()
    while frontier:
        owners = {m[0] for m in frontier}
        encoded = [o.encode() for o in owners]
        for owner, (_, definition) in view.winners.items():
            if owner in scanned or not (owner in owners or any(name in definition.data for name in encoded)):
                continue
            scanned.add(owner)
            for (name, desc), (_, calls) in definition.methods().items():
                member = selector(owner, name, desc)
                for callee in calls:
                    reverse[callee].add(member)
        next_frontier = {}
        for member, chain in sorted(frontier.items()):
            definition = view.winners[member[0]][1]
            flags = definition.methods()[member[1:]][0]
            if flags & 1 and member[1] != "<clinit>" and runtime_jar.class_flags(definition.data) & 1:
                routes[member] = (chain, flags)
            for caller in sorted(reverse[member] - seen):
                next_frontier.setdefault(caller, (caller, *chain))
        frontier = next_frontier
        seen.update(frontier)
    return routes, len(scanned)


def discover(views, declared=(), changed=(), limit=64):
    old, new = views["old"], views["new"]
    rows, inferred, class_only = changes(old, new)
    targets = {selector(runtime_jar.internal(o), n, d) for o, n, d in map(runtime_jar.parse_target, changed)} if changed else inferred
    if any(m[2] is None for m in targets):
        raise ValueError("changed selectors need a full JVM descriptor")
    ranking = {}
    scanned = {}
    for side, view in views.items():
        routes, scanned[side] = callers(view, targets)
        for member, (chain, access) in routes.items():
            name = entry_name(member)
            candidate = ranking.setdefault(name, {"entry": name, "sides": {}, "independentlyDiscovered": True})
            candidate["sides"][side] = {"chain": list(map(entry_name, chain)), "access": access,
                                        "candidateOrigins": view.origins(member[0])}
    ordered = sorted(ranking.values(), key=lambda r: (min(len(s["chain"]) for s in r["sides"].values()),
                                                        -len(r["sides"]), r["entry"]))
    for rank, row in enumerate(ordered, 1):
        row["rank"] = rank
    retained = [r for i, r in enumerate(ordered) if i < limit or r["entry"] in declared]
    missing = sorted(set(declared) - ranking.keys())
    retained.extend({"entry": e, "sides": {}, "independentlyDiscovered": False,
                     "basis": ["supplied public question"]} for e in missing)
    return {"method": "Exact changed bytecode declarations and reverse invocation references on the effective owners",
            "inputMode": "changed selectors supplied" if changed else "binary-only", "changedDefinitions": rows,
            "changedClasses": [r["owner"] for r in rows if r["effectiveBytesChanged"]], "classLevelCandidates": class_only,
            "changedResources": sorted(k for k in old.resources.keys() | new.resources.keys() if old.resources.get(k) != new.resources.get(k)),
            "candidates": retained, "candidateCount": len(ordered), "displayLimit": limit, "truncated": len(ordered) > limit,
            "classesExaminedForCalls": scanned, "discoveryMisses": missing,
            "intentQuestion": "Which public result should this change preserve or alter?" if len(ordered) > 1 else None,
            "unknownEdges": "Static chains describe symbolic calls. Virtual dispatch, initialization, reflection, factory state and resource lookups require an original caller."}
