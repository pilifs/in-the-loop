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


def access(flags):
    return {"access": flags, "public": bool(flags & 1), "static": bool(flags & 8),
            "synthetic": bool(flags & 0x1000), "bridge": bool(flags & 0x40)}


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
        self.manifests = []
        self.has_jar_index = False
        def add(name, data):
            if name.upper() == "META-INF/MANIFEST.MF" and not file.is_dir():
                self.manifests.append(data)
                if name == "META-INF/MANIFEST.MF":
                    self.multi = runtime_jar.multi_release(data)
            if name.upper() == "META-INF/INDEX.LIST" and not file.is_dir():
                self.has_jar_index = True
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

    def artifact(self, file, sha):
        if sha not in self.artifacts:
            self.artifacts[sha] = Artifact(file)
        return self.artifacts[sha]

    def view(self, files, hashes, feature):
        winners, physical, resources = {}, defaultdict(list), defaultdict(list)
        for i, (file, sha) in enumerate(zip(files, hashes, strict=True)):
            artifact = self.artifact(file, sha)
            for owner, defs in artifact.classes.items():
                physical[owner].extend((i, d) for d in defs)
                eligible = [d for d in defs if artifact.eligible(d.release, feature)]
                if eligible and owner not in winners:
                    winners[owner] = (i, max(eligible, key=lambda d: d.release))
            for name, versions in artifact.resources.items():
                eligible = [v for v in versions if artifact.eligible(v[0], feature)]
                if eligible:
                    resources[name].append(max(eligible)[1])
        return View(winners, physical, resources, hashes, files)

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
    files: list

    def origins(self, owner, member=None):
        winner = self.winners.get(owner)
        origins = []
        for index, definition in self.physical.get(owner, []):
            selected = bool(winner and winner[0] == index and winner[1] is definition)
            reason = ("effective class in the first provider" if selected else
                      "another provider wins" if winner and winner[0] < index else
                      "physical variant is not effective on this JDK")
            origins.append({"index": index, "provider": str(self.files[index]), "artifactSha256": self.hashes[index], "entry": definition.entry,
                            "classSha256": definition.sha, "release": definition.release or None,
                            "selected": selected, "reason": reason})
            if member is not None:
                methods = definition.methods()
                flags = methods[member][0] if member in methods else None
                origins[-1]["member"] = {"name": member[0], "descriptor": member[1], "declared": flags is not None,
                                         "overloads": sorted(desc for name,desc in methods if name == member[0]),
                                         **(access(flags) if flags is not None else {})}
        return origins


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
                                "sides": {s: {"bodyDigest": fp[0], **access(item[1].methods()[name, desc][0])}
                                          for s, fp, item in (("old", a, before), ("new", b, after)) if fp}})
        if before and after and before[1].sha != after[1].sha and (
                not differences or any(f[1] for f in [*old_methods.values(), *new_methods.values()])):
            class_only.append(owner)
        physical_changes = []
        left = {(i, d.entry):d for i, d in old.physical.get(owner, ())}
        right = {(i, d.entry):d for i, d in new.physical.get(owner, ())}
        for slot in sorted(left.keys() | right.keys()):
            a, b = left.get(slot), right.get(slot)
            if a and b and a.sha == b.sha:
                continue
            # Winners are detailed above. Preserve selector-level evidence for changes confined to a shadow.
            if (a is None or before and a is before[1]) and (b is None or after and b is after[1]):
                continue
            sides = [(s, definition, fingerprints(definition)) for s,definition in (("old",a),("new",b)) if definition]
            signatures = sorted(set().union(*(fp.keys() for _,_,fp in sides)))
            selectors = []
            for key in signatures:
                versions = {s: {"bodyDigest": fp[key][0], **access(d.methods()[key][0])} for s,d,fp in sides if key in fp}
                if len(versions) != 2 or versions["old"] != versions["new"]:
                    selectors.append({"entry": entry_name((owner,*key)), "sides": versions})
            physical_changes.append({"index": slot[0], "physicalEntry": slot[1], "selectors": selectors})
        rows.append({"owner": owner, "old": old.origins(owner), "new": new.origins(owner), "selectors": differences,
                     "otherPhysicalChanges": physical_changes,
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


def construction(view, owner):
    definition = view.winners[owner][1]
    constructors = [entry_name((owner, name, desc)) for (name, desc), (flags, _) in definition.methods().items()
                    if name == "<init>" and flags & 1]
    result = ")L" + owner + ";"
    factories = []
    for name, (_, candidate) in view.winners.items():
        if result.encode() not in candidate.data or not runtime_jar.class_flags(candidate.data) & 1:
            continue
        for (method, descriptor), (flags, _) in candidate.methods().items():
            if flags & 9 == 9 and descriptor.endswith(result):
                factories.append(entry_name((name, method, descriptor)))
    return {"publicConstructors": sorted(constructors), "publicFactories": sorted(factories),
            "evidence": "declared return type; construction and receiver still need a caller"}


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
    receiver_routes = {}
    for row in retained:
        owner, method, _ = runtime_jar.parse_target(row["entry"])
        for side, details in row["sides"].items():
            if details["access"] & 8 or method == "<init>":
                continue
            key = side, owner
            if key not in receiver_routes:
                receiver_routes[key] = construction(views[side], runtime_jar.internal(owner))
            details["construction"] = receiver_routes[key]
    missing = sorted(set(declared) - ranking.keys())
    retained.extend({"entry": e, "sides": {}, "independentlyDiscovered": False,
                     "basis": ["supplied public question"]} for e in missing)
    question = None
    if not declared and len(ordered) > 1:
        first, second = (r["entry"] for r in ordered[:2])
        question = (f"Should the claim observe {first} or {second}?" if len(ordered) == 2 else
                    f"Which of the {len(ordered)} public observations is intended, including {first} and {second}?")
    return {"method": "Exact changed bytecode declarations and reverse invocation references on the effective owners",
            "inputMode": "changed selectors supplied" if changed else "binary-only", "changedDefinitions": rows,
            "changedClasses": [r["owner"] for r in rows if r["effectiveBytesChanged"]], "classLevelCandidates": class_only,
            "changedResources": sorted(k for k in old.resources.keys() | new.resources.keys() if old.resources.get(k) != new.resources.get(k)),
            "candidates": retained, "candidateCount": len(ordered), "displayLimit": limit, "truncated": len(ordered) > limit,
            "classesExaminedForCalls": scanned, "discoveryMisses": missing,
            "intentQuestion": question,
            "unknownEdges": "Static chains describe symbolic calls. Virtual dispatch, initialization, reflection, factory state and resource lookups require an original caller."}
