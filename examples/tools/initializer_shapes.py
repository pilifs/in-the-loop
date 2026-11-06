#!/usr/bin/env python3
"""Class initializers counted by shape: Phase 4b of llm-dlc/loops/engine-priorities.md.

Static, nothing proved. `jvmcontract gaps` classifies the `<clinit>` of every `class-initializer` gap it finds
(lib/src/bmc/gaps.rs, `initializer_shape`): `enum`, `throws`, `other-statics` (reads or writes another class's
static fields), `constants` (assigns its own static fields constants or literal tables only) or `other`. This
script runs that scan

- over the recorded examples the gap scan applies to (build.py's `gap_scan_problem`: B9 and B11 proofs on the javac
  apps), each from the method its proof calls, on the patched classes and, for a regression proof, the unpatched
  ones too, as `build.py --scan-gaps` does but without writing the examples' notes; and
- over each app as a whole: every method of every class of its main sources is a target, so every initializer that
  any of its code may run is counted. Box Office is its `ticketing-domain` module, the one part javac builds without
  the Gradle build's dependencies.

It prints the initializers by shape, and with --json the whole count. Needs Java on PATH and a built jvmcontract
($JVMCONTRACT, or lib/target/release/jvmcontract).

Usage: python3 examples/tools/initializer_shapes.py [--json] [--examples-only | --apps-only] [ID ...]
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402

# The apps' main sources javac compiles here, by name.
APP_SOURCES = {
    "mica": ["examples/apps/mica/src/main/java"],
    "crosscut": ["examples/apps/crosscut/src/main/java"],
    "quorum": ["examples/apps/quorum/src/main/java"],
    "boxoffice": ["examples/apps/boxoffice/ticketing-domain/src/main/java"],
}
SHAPES = ["enum", "throws", "other-statics", "constants", "other"]


def jvmcontract():
    exe = os.environ.get("JVMCONTRACT") or str(REPO / "lib/target/release/jvmcontract")
    if not Path(exe).exists():
        sys.exit(f"jvmcontract not found at {exe}: build lib/ with cargo, or set JVMCONTRACT")
    os.environ["JVMCONTRACT"] = exe  # build.py's scan uses it rather than building again
    return exe


def initializers(scan):
    """{class: initializer} of one `jvmcontract gaps --json` scan."""
    return {i["class"]: i for i in scan.get("initializers", [])}


def scan_examples(wanted):
    out = []
    folders = sorted(p for p in build.EXAMPLES.iterdir() if p.is_dir() and re.match(r"^\d{3}-", p.name))
    for folder in folders:
        if wanted and folder.name[:3] not in wanted:
            continue
        example = build.load_example(folder)
        if build.gap_scan_problem(example):
            continue
        scans = build.scan_gaps(folder, example)
        found = {}
        for scan in scans.values():
            found.update(initializers(scan))
        out.append({"id": example["id"], "app": build.app_of(example), "approach": example["approach"]["id"],
                    "engine": example["approach"].get("engine") or "jbmc", "initializers": sorted(found.values(), key=lambda i: i["class"])})
        print(f"{example['id']}: {len(found)} initializer(s)" + "".join(f"; {i['class']} {i['shape']}" for i in out[-1]["initializers"]),
              file=sys.stderr, flush=True)
    return out


PRIMITIVE = {"Z": "boolean", "B": "byte", "C": "char", "S": "short", "I": "int", "J": "long", "F": "float", "D": "double"}


def java_types(descriptor):
    """The parameter types of a method descriptor as Java names, erased: `(I[Ljava/lang/String;)V` gives
    `int, java.lang.String[]`."""
    params = descriptor[1:descriptor.index(")")]
    out, i = [], 0
    while i < len(params):
        dims = 0
        while params[i] == "[":
            dims, i = dims + 1, i + 1
        if params[i] == "L":
            end = params.index(";", i)
            name, i = params[i + 1:end].replace("/", "."), end + 1
        else:
            name, i = PRIMITIVE[params[i]], i + 1
        out.append(name + "[]" * dims)
    return out


def targets(classes):
    """Every method javac wrote, as `pkg.Class#name(types)` with erased types, skipping constructors (the scan
    starts from them anyway for an instance method's class), initializers and synthetic methods (a `$` in the
    name)."""
    out = []
    files = sorted(classes.rglob("*.class"))
    proc = subprocess.run(["javap", "-p", "-s", *map(str, files)], capture_output=True, text=True, check=True)
    current, name = None, None
    for line in proc.stdout.splitlines():
        head = re.match(r"^(?:[\w-]+ )*(?:class|interface|enum|record|@interface) ([\w$.]+)", line)
        if head:
            current, name = head.group(1).split("<")[0], None
            continue
        m = re.match(r"^\s+.*?([\w$]+)\(.*\)(?: throws .*)?;$", line)
        if m:
            name = m.group(1)
            continue
        d = re.match(r"^\s+descriptor: (\(.*)$", line)
        if d and name and current and "$" not in name and name != current.rsplit(".", 1)[-1]:
            out.append(f"{current}#{name}({', '.join(java_types(d.group(1)))})")
        if d:
            name = None
    return sorted(set(out))


def scan_apps():
    exe = jvmcontract()
    out = []
    with tempfile.TemporaryDirectory(prefix="initializer-shapes-") as tmp:
        for app, roots in APP_SOURCES.items():
            classes = Path(tmp) / app
            sources = sorted(str(p) for r in roots for p in (REPO / r).rglob("*.java"))
            subprocess.run(["javac", "-d", str(classes), *sources], check=True, capture_output=True, text=True)
            every = targets(classes)
            proc = subprocess.run([exe, "gaps", "--classes", str(classes), "--json", *[a for t in every for a in ("--target", t)]],
                                  capture_output=True, text=True)
            if proc.returncode != 0:
                sys.exit(f"jvmcontract gaps failed on {app}:\n{proc.stderr}")
            scan = json.loads(proc.stdout)
            declared = sum(1 for f in classes.rglob("*.class")
                           if "static {};" in subprocess.run(["javap", "-p", str(f)], capture_output=True, text=True).stdout)
            found = sorted(initializers(scan).values(), key=lambda i: i["class"])
            out.append({"app": app, "targets": len(every), "methods": scan["methods"], "declared": declared,
                        "initializers": found})
            print(f"{app}: {len(every)} targets, {scan['methods']} methods reached, {len(found)} of {declared} initializers",
                  file=sys.stderr, flush=True)
    return out


def by_shape(items):
    return Counter(i["shape"] for i in items)


def report(examples, apps):
    lines = []
    if examples is not None:
        distinct = {i["class"]: i for e in examples for i in e["initializers"]}
        reach = Counter()
        for e in examples:
            for shape in {i["shape"] for i in e["initializers"]}:
                reach[shape] += 1
        with_any = sum(1 for e in examples if e["initializers"])
        lines.append(f"Recorded examples: {len(examples)} scanned, {with_any} reach a class initializer, "
                     f"{len(distinct)} distinct initializers")
        counts = by_shape(distinct.values())
        for s in SHAPES:
            ids = sorted(e["id"] for e in examples if any(i["shape"] == s for i in e["initializers"]))
            lines.append(f"  {s}: {counts[s]} initializer(s), reached by {reach[s]} example(s){': ' + ', '.join(ids) if ids else ''}")
    if apps is not None:
        lines.append("Apps (every method a target):")
        for a in apps:
            counts = by_shape(a["initializers"])
            lines.append(f"  {a['app']}: {len(a['initializers'])} of {a['declared']} initializers reached; "
                         + ", ".join(f"{s} {counts[s]}" for s in SHAPES))
        total = by_shape([i for a in apps for i in a["initializers"]])
        lines.append("  all apps: " + ", ".join(f"{s} {total[s]}" for s in SHAPES))
        others = [i for a in apps for i in a["initializers"] if i["shape"] not in ("enum", "constants")]
        for i in others:
            lines.append(f"    {i['class']}: {i['shape']} ({', '.join(i['traits'])})")
    return "\n".join(lines)


def main(argv):
    as_json = "--json" in argv
    only = {a for a in argv if a in ("--examples-only", "--apps-only")}
    wanted = {a for a in argv if re.fullmatch(r"\d{3}", a)}
    jvmcontract()
    examples = None if "--apps-only" in only else scan_examples(wanted)
    apps = None if "--examples-only" in only or wanted else scan_apps()
    if as_json:
        print(json.dumps({"examples": examples, "apps": apps}, indent=2))
    else:
        print(report(examples, apps))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
