"""Check cell and outer-list identity on both original Javaslang transpose implementations."""
import argparse
import gzip
import json
import math
import os
from pathlib import Path
import sys
import tempfile

from historical_companion import CLASSPATH, LOADED, bind, check_ordinary, prepare
from measure import HERE, ROOT, SETUP, digest, read, write
from providers import CLASSES

sys.path.insert(0, str(HERE.parent / "java-domain-proof"))
from companions import invocation, proof

FOLDER = ROOT / "examples/371-javaslang-matrix-transpose"
ENTRY = "datawork.MatrixReferences"
LOCAL = (ENTRY, ENTRY + "$Cell", "MatrixReplay", "LoadedClasses")
SOURCES = [FOLDER / "companions/MatrixReferences.java", FOLDER / "companions/MatrixReplay.java", LOADED]
METHODS = {"roundTrip": ([("choices", "int"), ("wide", "boolean")], None),
           "boundaries": ([("shape", "int"), ("choices", "int")], "shape >= 0 && shape < 5")}
SUBJECT = "javaslang.collection.List"
TRANSPOSE = "(Ljavaslang/collection/List;)Ljavaslang/collection/List;"
BOUNDS = (256, 16384)


def partitions(prefix=(), largest=0):
    """Zero names null. Name each new non-null identity in order of first occurrence."""
    if len(prefix) == 6:
        yield prefix
        return
    for label in range(largest + 2):
        yield from partitions((*prefix, label), max(largest, label))


def pack(labels):
    return sum(label << (3 * index) for index, label in enumerate(labels))


def rows(flat, width):
    return [list(flat[start:start + width]) for start in range(0, len(flat), width)]


def rectangle(labels, height):
    width = 6 // height
    source = rows(labels, width)
    transposed = [list(column) for column in zip(*source, strict=True)]
    copies = [[-1 if cell else 0 for cell in column] for column in transposed]
    reshaped = rows(labels, height)
    expected = ["rectangle", str(pack(labels)), str(height), json.dumps(source), json.dumps(transposed),
                json.dumps(source), json.dumps(source), "true", json.dumps(copies),
                json.dumps(reshaped), json.dumps(source), "1"]
    return expected, copies != transposed, reshaped != transposed


def boundary(shape, choice):
    source = ([], [[]], [[choice]], [[], []], [[], [], []])[shape]
    fast = shape < 3
    output = source if fast else []
    same = "true" if fast else "false"
    return ["boundary", str(shape), str(choice), json.dumps(source), json.dumps(output),
            json.dumps(output), same, same, "1"]


def check_grid(path, single=None):
    counts = {"partitions": 0, "rectangles": 0, "representedLabeledRectangles": 0, "boundaries": 0,
              "equalCopiesWithWrongReferences": 0, "invertibleReshapesWithWrongCoordinates": 0}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        def match(expected):
            if stream.readline().rstrip("\n").split("\t") != expected:
                raise ValueError(f"wrong matrix observations at {' '.join(expected[:3])}")

        for labels in partitions() if single is None else [single]:
            counts["partitions"] += 1
            # Each injection of the non-null labels into the seven physical objects is realizable.
            labelings = math.perm(7, len(set(labels) - {0}))
            for height in (2, 3):
                expected, copy_differs, reshape_differs = rectangle(labels, height)
                match(expected)
                counts["rectangles"] += 1
                counts["representedLabeledRectangles"] += labelings
                counts["equalCopiesWithWrongReferences"] += copy_differs
                counts["invertibleReshapesWithWrongCoordinates"] += reshape_differs
                if single is not None:
                    print(f"  {height}x{6 // height}  input {expected[3]}  transpose {expected[4]}  twice {expected[5]}")
                    print(f"       value-equal copies {expected[8]}  row-major reshape {expected[9]}")
        for shape in range(5):
            for choice in range(8):
                match(boundary(shape, choice))
                counts["boundaries"] += 1
        if stream.read(1):
            raise ValueError("unexpected trailing matrix observations")
    if single is None and (counts["partitions"] != 877 or counts["representedLabeledRectangles"] != 2 * 8**6):
        raise ValueError("incomplete null and alias partitions")
    return counts


def requests():
    return [(ENTRY, "roundTrip", "(IZ)I"), (ENTRY, "boundaries", "(II)I"), (SUBJECT, "transpose", TRANSPOSE),
            *((name, None, None) for name in (*LOCAL[1:], *CLASSES[371]) if name != SUBJECT)]


def check_native(label, outcome):
    params, guard = METHODS[label]
    check_ordinary(outcome, ENTRY + "#" + label, params, guard, BOUNDS)


def run(side, dest, single=None):
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="matrix-references-") as tmp:
        work = Path(tmp)
        jdk, env, classes, jar, prior = prepare(FOLDER, side, work, SETUP / f"artifacts/vavr-1829-{side}.jar", SOURCES)
        hashes = {name: digest(classes / (name.replace(".", "/") + ".class")) for name in LOCAL}
        for name in CLASSES[371]:
            subject = prior["classes"][name]
            if subject["jarSha256"] != prior["orderedJars"][-1]["sha256"]:
                raise ValueError(f"different historical provider of {name}")
            hashes[name] = subject["classSha256"]
        codes = work / "cases.txt"
        patterns = partitions() if single is None else [single]
        codes.write_text("".join(f"{pack(pattern)}\n" for pattern in patterns))
        grid = dest / "observations.tsv.gz"
        jvm = invocation([jdk / "bin/java", "-Xmx128m", "-XX:-UsePerfData", f"-Djava.io.tmpdir={work}",
                          "-cp", os.pathsep.join(map(str, (classes, jar))),
                          "MatrixReplay", codes, grid, work, *hashes], "jvm", dest, work, env)
        expected = [f"{name}\t{(classes if name in LOCAL else jar).name}\t{sha}" for name, sha in hashes.items()]
        if jvm["exit"] or (dest / jvm["stdout"]).read_text().splitlines() != expected:
            raise ValueError("the public JVM did not use the expected observer and original classes")
        counts = check_grid(grid, single)
        if single is not None:
            return

        checker = Path(os.environ["JVMCONTRACT"]).resolve()
        bindings = [(name, method, desc, classes if name in LOCAL else jar, hashes[name])
                    for name, method, desc in requests()]
        report = {"commit": prior["commit"], "jdk": prior["jdk"]["JAVA_RUNTIME_VERSION"], "classpath": CLASSPATH,
                  "jarSha256": digest(jar), "sources": {s.name: digest(s) for s in SOURCES}, "classes": hashes,
                  "jvm": jvm, "grid": counts, "observationsSha256": digest(grid), "checkerSha256": digest(checker),
                  "source": os.environ["VERIFY_SOURCE_COMMIT"], "job": os.environ["VERIFY_JOB_ID"],
                  "libTree": os.environ["JVMCONTRACT_LIB_TREE"], "checkerBindings": bind(checker, env, work, side, bindings),
                  "proofs": {}}
        for label, (_, guard) in METHODS.items():
            measured = proof(checker, classes, [jar], work, env, dest, ENTRY + "#" + label, label, guard, bounds=BOUNDS)
            report["proofs"][label] = measured
            write(dest / "measurement.json", report)
            print(side, label, measured["verdict"], measured["blocker"], flush=True)
            outcome, = read(dest / measured["stdout"])
            check_native(label, outcome)
        print(side, counts, flush=True)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path, help="directory for managed proofs and JVM records")
    mode.add_argument("--case", help="replay six row-major reference labels, each 0 (null) through 7")
    cli.add_argument("--side", choices=("parent", "landed"))
    args = cli.parse_args()
    if args.case is not None and (len(args.case) != 6 or any(c not in "01234567" for c in args.case)):
        cli.error("--case takes exactly six digits from 0 through 7")
    for side in [args.side] if args.side else ("parent", "landed"):
        if args.case is None:
            run(side, args.output.resolve() / side)
        else:
            print(side, flush=True)
            with tempfile.TemporaryDirectory(prefix="matrix-case-") as tmp:
                run(side, Path(tmp), tuple(map(int, args.case)))
