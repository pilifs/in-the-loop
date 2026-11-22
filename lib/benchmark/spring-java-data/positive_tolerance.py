"""Check Commons Lang's first match at a positive, exactly representable tolerance."""
import argparse
from collections import Counter
from fractions import Fraction
import gzip
from itertools import product
import math
import os
from pathlib import Path
import struct
import sys
import tempfile

from historical_companion import CLASSPATH, LOADED, bind, check_ordinary, prepare
from measure import HERE, ROOT, SETUP, digest, read, write

sys.path.insert(0, str(HERE.parent / "java-domain-proof"))
from companions import invocation, proof

FOLDER = ROOT / "examples/373-commons-lang-nan-search"
SOURCES = FOLDER / "companions"
ENTRY = "datawork.ToleranceSearch"
SUBJECT = "org.apache.commons.lang3.ArrayUtils"
METHOD = ENTRY + "#agrees"
GUARD = "center >= -1 && center <= 1"
BOUNDS = (256, 16384)
STARTS = (-(2**31), -1, 0, 1, 2, 3, 2**31 - 1)
# Big-endian Java DataOutput: public index, post-call raw words, native-adapter return.
ROW = struct.Struct(">iQQB")


def raw(number):
    return int.from_bytes(struct.pack(">d", number), "big")


def words():
    values = {raw(x) for x in (-math.inf, -0.5, -0.0, 0.0, 0.5, math.inf)}
    for end in (-0.75, -0.25, 0.25, 0.75):
        values.update(raw(x) for x in (math.nextafter(end, -math.inf), end, math.nextafter(end, math.inf)))
    for sign in (0, 1 << 63):
        values.update(sign | x for x in (1, 0x000fffffffffffff, 0x0010000000000000, 0x7fefffffffffffff))
    values.update((0x7ff8000000000001, 0xfff8000000000011, 0x7ff0000000000021, 0xfff0000000000041))
    return sorted(values)


def cells():
    """Expected post-call bits and exact rational values, independently of the Java guard."""
    result = {}
    for source in words():
        value, = struct.unpack(">d", source.to_bytes(8, "big"))
        bits = source | (1 << 51) if math.isnan(value) else source
        result[source] = bits, Fraction.from_float(value) if math.isfinite(value) else None
    return result


def check_grid(path):
    samples = cells()
    outcomes = Counter()
    controls = Counter()
    with gzip.open(path, "rb") as packed:
        records = ROW.iter_unpack(packed.read())
    domain = product((-1, 0, 1), samples, samples, STARTS)
    quarter = Fraction(1, 4)
    for (center, first, second, start), (found, after_a, after_b, agrees) in zip(domain, records, strict=True):
        bits_a, a = samples[first]
        bits_b, b = samples[second]
        lo, hi = Fraction(center, 2) - quarter, Fraction(center, 2) + quarter
        candidates = [(i, x) for i, x in enumerate((a, b)) if i >= start and x is not None and lo <= x <= hi]
        expected = candidates[0][0] if candidates else -1
        if (found, after_a, after_b, agrees) != (expected, bits_a, bits_b, 1):
            raise ValueError(f"wrong tolerance result at center {center}/2, 0x{first:016x}, 0x{second:016x}, start {start}")
        outcomes[found] += 1
        if candidates:
            controls["excludeLower"] += found != next((i for i, x in candidates if x > lo), -1)
            controls["excludeUpper"] += found != next((i for i, x in candidates if x < hi), -1)
            controls["lastMatch"] += found != candidates[-1][0]
    if set(outcomes) != {-1, 0, 1} or not all(controls[key] for key in ("excludeLower", "excludeUpper", "lastMatch")):
        raise ValueError("the finite grid did not exercise both boundaries and first-match order")
    return {"cases": sum(outcomes.values()), "indices": {str(i): outcomes[i] for i in (-1, 0, 1)},
            "controlDifferences": dict(controls)}


def check_native(raw_outcome):
    check_ordinary(raw_outcome, METHOD, [("first", "long"), ("second", "long"), ("start", "int"), ("center", "int")],
                   GUARD, BOUNDS)


def run(side, dest, physical_only):
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="positive-tolerance-") as tmp:
        work = Path(tmp)
        sources = [SOURCES / "ToleranceSearch.java", SOURCES / "ToleranceReplay.java", LOADED]
        jdk, env, classes, jar, prior = prepare(FOLDER, side, work, SETUP / f"artifacts/commons-lang-1589-{side}.jar", sources)
        subject = prior["classes"][SUBJECT]
        if subject["jarSha256"] != digest(jar):
            raise ValueError("different historical ArrayUtils provider")
        observer = digest(classes / "datawork/ToleranceSearch.class")
        cp = os.pathsep.join(map(str, (classes, jar)))
        grid = dest / "observations.bin.gz"
        physical = invocation([jdk / "bin/java", "-Xmx128m", "-cp", cp, "ToleranceReplay", work, grid,
                               ",".join(map(str, STARTS)), *(f"{w:016x}" for w in words())], "jvm", dest, work, env)
        bindings = [(ENTRY, "agrees", "(JJII)I", classes, observer),
                    (SUBJECT, "indexOf", "([DDID)I", jar, subject["classSha256"])]
        expected = [f"{name}\t{provider.name}\t{sha}" for name, _, _, provider, sha in bindings]
        if physical["exit"] or (dest / physical["stdout"]).read_text().splitlines() != expected:
            raise ValueError("the public JVM did not load the two expected classes")
        report = {"commit": prior["commit"], "jdk": prior["jdk"]["JAVA_RUNTIME_VERSION"], "classpath": CLASSPATH,
                  "jarSha256": digest(jar), "sources": {s.name: digest(s) for s in sources},
                  "classes": {name: sha for name, _, _, _, sha in bindings}, "jvm": physical,
                  "words": [f"{w:016x}" for w in words()], "starts": list(STARTS), "grid": check_grid(grid),
                  "observationsSha256": digest(grid)}
        if not physical_only:
            checker = Path(os.environ["JVMCONTRACT"]).resolve()
            bind(checker, env, work, side, bindings)
            report.update(checkerSha256=digest(checker), source=os.environ.get("VERIFY_SOURCE_COMMIT"),
                          libTree=os.environ.get("JVMCONTRACT_LIB_TREE"), job=os.environ.get("VERIFY_JOB_ID"))
            report["native"] = proof(checker, classes, [jar], work, env, dest, METHOD, "ordinary", GUARD, bounds=BOUNDS)
        write(dest / "measurement.json", report)
        if not physical_only:
            print(side, report["grid"], report["native"]["verdict"], report["native"]["blocker"], flush=True)
            outcome, = read(dest / report["native"]["stdout"])
            check_native(outcome)
        else:
            print(side, report["grid"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--side", choices=("parent", "landed"))
    parser.add_argument("--physical-only", action="store_true")
    args = parser.parse_args()
    for side in [args.side] if args.side else ["parent", "landed"]:
        run(side, args.output.resolve() / side, args.physical_only)
