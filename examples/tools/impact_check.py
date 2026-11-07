#!/usr/bin/env python3
"""Checks `jvmcontract impact` on the recorded examples' own before and after builds (S3 of
llm-dlc/loops/foundations-summaries.md).

For each app built with javac (Crosscut, Quorum, Mica), the claims are those a build.py run over its B9 and B11
examples checks: one per example, on its subject method as the unpatched code names it (`previousSymbol` for a
renamed one, else `target`). For each such example, the first build is the unpatched app and the second the app with
the example's patch, and `impact` is asked about all of the app's claims, the example's own as renamed by its patch.

The report is judged against facts read here from the class files, independently of the tool's closure walk:
- the changed classes: those whose class file differs between the two builds, or is in one only (javac writes the
  same bytes for the same source);
- a claim's reach: every application class its target's class refers to (constant-pool classes and the class names
  in descriptors and signatures), and every subclass or implementor of one (a call may dispatch to it), closed
  transitively, in either build. It holds every class the claim's proof can read, and more.

A report passes when:
1. the example's own claim is invalidated (its patch changes its code), or unresolved and its method is not in the
   unpatched build;
2. every part an invalidated claim names lies in a changed class (a method or class part, a missing name), or is a
   dispatch set while a class in its reach changed; a target gone from the second build is gone from its class file;
3. a claim whose reach holds no changed class is unchanged (or unresolved);
4. a claim is unresolved only when the first build has no method of that name.

What a closure adds over the reach (a claim whose reach changed but whose closure didn't, since its method doesn't
call the changed one) is counted, not judged.

Usage: python3 examples/tools/impact_check.py [--jvmcontract PATH] [--out FILE] [--jobs N] [ID ...]
It exits 1 when a report fails a rule, 0 otherwise. The jvmcontract binary is --jvmcontract, $JVMCONTRACT, or
lib/target/release/jvmcontract.
"""

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402  (plan(), TOOL_APPS, IGNORE)

REPO = build.REPO
DESCRIPTOR_CLASS = re.compile(r"L([\w/$]+);")


def parse_class(data):
    """The class's name, superclass, interfaces, the class names it refers to, and its method names."""
    u2 = lambda p: struct.unpack_from(">H", data, p)[0]
    u4 = lambda p: struct.unpack_from(">I", data, p)[0]
    count, pos, cp, i = u2(8), 10, {}, 1
    while i < count:
        tag = data[pos]
        pos += 1
        if tag == 1:
            n = u2(pos)
            cp[i] = ("utf8", data[pos + 2:pos + 2 + n].decode("utf-8", "replace"))
            pos += 2 + n
        elif tag == 7:
            cp[i] = ("class", u2(pos))
            pos += 2
        elif tag in (5, 6):
            pos += 8
            i += 1
        elif tag in (3, 4, 9, 10, 11, 12, 17, 18):
            pos += 4
        elif tag == 15:
            pos += 3
        elif tag in (8, 16, 19, 20):
            pos += 2
        else:
            raise ValueError(f"constant pool tag {tag}")
        i += 1
    utf8 = lambda k: cp[k][1]
    name_of = lambda k: utf8(cp[k][1]) if k else None
    this, super_, n_interfaces = u2(pos + 2), u2(pos + 4), u2(pos + 6)
    interfaces = [name_of(u2(pos + 8 + 2 * j)) for j in range(n_interfaces)]
    pos += 8 + 2 * n_interfaces

    def members(pos):
        """The names of the fields or methods at `pos` (their count, then each), and the position after them."""
        names, n = [], u2(pos)
        pos += 2
        for _ in range(n):  # access, name, descriptor, attribute count, attributes
            names.append(utf8(u2(pos + 2)))
            attributes, pos = u2(pos + 6), pos + 8
            for _ in range(attributes):
                pos += 6 + u4(pos + 2)
        return names, pos

    _, pos = members(pos)
    methods, _ = members(pos)
    refs = set()
    for kind, value in cp.values():
        if kind == "class":
            name = utf8(value)
            refs.update(DESCRIPTOR_CLASS.findall(name) if name.startswith("[") else [name])
        else:
            refs.update(DESCRIPTOR_CLASS.findall(value))
    return {"name": name_of(this), "super": name_of(super_), "interfaces": interfaces, "refs": refs, "methods": set(methods)}


def read_build(classes):
    out = {}
    for f in Path(classes).rglob("*.class"):
        data = f.read_bytes()
        c = parse_class(data)
        c["bytes"] = data
        out[c["name"]] = c
    return out


def reach(classes, start):
    """`start` and every application class it refers to or that extends or implements one, transitively."""
    children = {}
    for c in classes.values():
        for parent in [c["super"], *c["interfaces"]]:
            children.setdefault(parent, set()).add(c["name"])
    seen, todo = set(), [start]
    while todo:
        name = todo.pop()
        if name in seen or name not in classes:
            continue
        seen.add(name)
        todo.extend(classes[name]["refs"] | children.get(name, set()))
    return seen


def class_and_method(target):
    """`pkg.C#m(int)` as (`pkg/C`, `m`)."""
    cls, method = target.split("#", 1)
    return cls.replace(".", "/"), method.split("(", 1)[0].strip()


def part_class(part):
    """The class a method, class or missing part names: `method pkg/C.m(I)I` and `class pkg/C` give `pkg/C`."""
    kind, rest = part.split(" ", 1)
    if kind == "class":
        return rest
    if kind in ("method", "dispatch") or (kind == "missing" and "(" in rest):
        return rest.split("(", 1)[0].rsplit(".", 1)[0]
    return rest


def compile_app(app, root, out):
    sources = sorted((root / build.TOOL_APPS[app]["root"] / "src/main/java").rglob("*.java"))
    out.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(["javac", "-parameters", "-g", "-proc:none", "-d", str(out), *map(str, sources)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"javac failed in {root}:\n{proc.stderr}")


def copy_app(app, dest):
    part = build.TOOL_APPS[app]["root"]
    shutil.copytree(REPO / part, dest / part, ignore=build.IGNORE)


def apply_patch(patch, cwd):
    """As build.py's apply_patch: git kept from a repository above the copy, so it can't skip the files."""
    env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(Path(cwd).resolve().parent))
    proc = subprocess.run(["git", "apply", "-p1", "--verbose", "-"], input=patch, cwd=cwd, env=env, capture_output=True, text=True)
    if proc.returncode != 0 or "Skipped patch" in proc.stderr:
        raise RuntimeError(f"the patch did not apply in {cwd}:\n{proc.stderr}")


def judge(example, plans, base, after, report):
    """The rules' failures for one example's report, and what it counted."""
    failures, counts = [], {"invalidated": 0, "unchanged": 0, "unresolved": 0, "unchangedWithReachChanged": 0}
    changed = {n for n in set(base) | set(after) if (base.get(n) or {}).get("bytes") != (after.get(n) or {}).get("bytes")}
    by_id = {c["id"]: c for c in report["claims"]}
    for p in plans:
        x = p["example"]
        c = by_id.get(x)
        if c is None:
            failures.append(f"claim {x} is missing from the report")
            continue
        status = c["status"]
        counts[status] += 1
        before_target = c.get("beforeTarget") or c["target"]
        bcls, bmethod = class_and_method(before_target)
        acls, amethod = class_and_method(c["target"])
        reached = reach(base, bcls) | reach(after, acls)
        touched = reached & changed
        if x == example and status == "unchanged":
            failures.append(f"its own claim {x} is unchanged, though the patch changes {sorted(changed) or 'no class'}")
        if status == "unresolved":
            if bcls in base and bmethod in base[bcls]["methods"]:
                failures.append(f"claim {x} is unresolved, but {before_target} has a method {bmethod}: {c['reason']}")
        elif status == "unchanged":
            if touched:
                counts["unchangedWithReachChanged"] += 1
        else:
            if not touched and not c.get("reason"):
                failures.append(f"claim {x} is invalidated, but no class in its reach changed")
            for ch in c.get("changes", []):
                part, kind = ch["part"], ch["part"].split(" ", 1)[0]
                if kind == "config":
                    failures.append(f"claim {x} names {part}, and these apps have no configuration")
                elif kind == "dispatch":
                    if not touched:
                        failures.append(f"claim {x} names {part}, and no class in its reach changed")
                elif part_class(part) not in changed:
                    failures.append(f"claim {x} names {ch['change']} {part}, and {part_class(part)} did not change")
            if c.get("reason") and "gone from the second build" in c["reason"]:
                if acls in after and amethod in after[acls]["methods"]:
                    failures.append(f"claim {x} is said to be gone, but {acls} has a method {amethod}")
    return failures, counts, sorted(changed)


def run_example(example, app, plans, base_classes, base_build, tool, work):
    plan = next(p for p in plans if p["example"] == example)
    folder = next(REPO.glob(f"examples/{example}-*"))
    meta = json.loads((folder / "example.json").read_text())
    root = work / f"after-{example}"
    copy_app(app, root)
    apply_patch((folder / meta["change"]["patch"]).read_text(), root)
    classes = work / f"after-{example}-classes"
    compile_app(app, root, classes)
    claims = []
    for p in plans:
        base_name = p["claim"].get("previousSymbol") or p["claim"]["target"]
        target = p["claim"]["target"] if p["example"] == example else base_name
        claims.append({"id": p["example"], "target": target, "beforeTarget": base_name})
    claims_file = work / f"claims-{example}.json"
    claims_file.write_text(json.dumps(claims, indent=1))
    proc = subprocess.run([tool, "impact", "--before", str(base_classes), "--after", str(classes), "--claims", str(claims_file), "--json"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"jvmcontract impact failed for {example}:\n{proc.stderr}")
    report = json.loads(proc.stdout)
    failures, counts, changed = judge(example, plans, base_build, read_build(classes), report)
    own = next(c for c in report["claims"] if c["id"] == example)
    return {"example": example, "app": app, "changedClasses": changed, "counts": counts, "failures": failures,
            "own": own, "invalidated": [c["id"] for c in report["claims"] if c["status"] == "invalidated"]}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--jvmcontract", default=os.environ.get("JVMCONTRACT") or str(REPO / "lib/target/release/jvmcontract"))
    ap.add_argument("--out", type=Path)
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args(argv)
    if not Path(args.jvmcontract).exists():
        sys.exit(f"jvmcontract not found at {args.jvmcontract}: build lib/ with cargo, or pass --jvmcontract")
    examples = []  # every B9 and B11 example on a javac app
    for f in sorted(REPO.glob("examples/[0-9]*/example.json")):
        e = json.loads(f.read_text())
        if e["approach"]["id"] in ("B9", "B11") and e["subject"].get("system") in ("Crosscut", "Quorum", "Mica"):
            examples.append(e["id"])
    plans = [build.plan(json.loads(next(REPO.glob(f"examples/{i}-*/example.json")).read_text())) for i in examples]
    plans = [p for p in plans if p["executable"] and p["app"] in build.TOOL_APPS]
    wanted = set(args.ids) or {p["example"] for p in plans}
    results = []
    with tempfile.TemporaryDirectory(prefix="impact-check-") as tmp:
        work = Path(tmp)
        bases = {}
        for app in sorted({p["app"] for p in plans}):
            copy_app(app, work / f"base-{app}")
            compile_app(app, work / f"base-{app}", work / f"base-{app}-classes")
            bases[app] = (work / f"base-{app}-classes", read_build(work / f"base-{app}-classes"))
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = []
            for p in plans:
                if p["example"] not in wanted:
                    continue
                app_plans = [q for q in plans if q["app"] == p["app"]]
                futures.append(pool.submit(run_example, p["example"], p["app"], app_plans, *bases[p["app"]], args.jvmcontract, work))
            for f in futures:
                try:
                    results.append(f.result())
                except Exception as e:  # one example's failure to build is reported, not fatal to the others
                    results.append({"example": "?", "failures": [str(e)]})
    failed = [r for r in results if r["failures"]]
    print("| Example | App | Changed classes | Own claim | Invalidated claims | Unchanged (reach changed) | Unresolved |")
    print("|---|---|---|---|---|---|---|")
    for r in results:
        if "counts" not in r:
            print(f"| {r['example']} | | | error | | | |")
            continue
        own = r["own"]["status"] + (f" ({len(r['own'].get('changes', []))} parts)" if r["own"]["status"] == "invalidated" else "")
        c = r["counts"]
        print(f"| {r['example']} | {r['app']} | {len(r['changedClasses'])} | {own} | {', '.join(r['invalidated'])} | "
              f"{c['unchanged']} ({c['unchangedWithReachChanged']}) | {c['unresolved']} |")
    total = {k: sum(r.get("counts", {}).get(k, 0) for r in results) for k in ("invalidated", "unchanged", "unresolved", "unchangedWithReachChanged")}
    print(f"\n{len(results)} examples, {len(failed)} failing a rule; over all reports, {total['invalidated']} claims invalidated, "
          f"{total['unchanged']} unchanged ({total['unchangedWithReachChanged']} of them with a changed class in reach), "
          f"{total['unresolved']} unresolved.")
    for r in failed:
        for f in r["failures"]:
            print(f"FAIL {r['example']}: {f}")
    if args.out:
        args.out.write_text(json.dumps({"results": results, "totals": total}, indent=1) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
