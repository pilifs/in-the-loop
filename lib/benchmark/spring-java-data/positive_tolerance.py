"""Check Commons Lang's first match at a positive, exactly representable tolerance."""
import argparse
from collections import Counter
from fractions import Fraction
import gzip
from itertools import product
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

from measure import HERE, ROOT, SETUP, digest, read, write
from targets import class_binding, runtime_jdk

sys.path.insert(0, str(HERE.parent / "java-domain-proof"))
from companions import invocation, proof

FOLDER = ROOT / "examples/373-commons-lang-nan-search"
SOURCES = FOLDER / "companions"
LOADED = ROOT / "examples/tools/targets/java/LoadedClasses.java"
ENTRY = "datawork.ToleranceSearch"
SUBJECT = "org.apache.commons.lang3.ArrayUtils"
METHOD = ENTRY + "#agrees"
GUARD = "center >= -1 && center <= 1"
BOUNDS = (256, 16384)
STARTS = (-(2**31), -1, 0, 1, 2, 3, 2**31 - 1)
CLASSPATH = ["classes", "original.jar"]
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
    """Validate the stated domain as well as the verdict of the symbolic query."""
    stated = raw_outcome["stated"]
    params = [(p["name"], p["type"]) for p in stated["domain"]["parameters"]]
    ordinary = [{"kind": "precondition", "text": GUARD, "basis": "stated"},
                {"kind": "initialization", "text": "every JDK class is initialized already, its static initializer having run and thrown nothing",
                 "basis": "engine"}]
    if (raw_outcome["target"] != METHOD or raw_outcome["assume"] != GUARD or raw_outcome["assert"] != "result == 1"
            or stated["checker"]["engine"] != "native" or stated["gap_mode"] != "strict"
            or params != [("first", "long"), ("second", "long"), ("start", "int"), ("center", "int")]
            or stated["assumptions"] != ordinary or stated["observations"]["exceptions"] != "none may be thrown"
            or stated["checker"]["fallback"] is not None
            or raw_outcome["verdict"] != "verified" or raw_outcome["problem"]
            or stated["vacuity"]["status"] != "non-vacuous"
            or stated["bounds"] != {"complete": True, "unwind": BOUNDS[0], "max_array_length": None}
            or raw_outcome["search"]["max_array_length"] != BOUNDS[1]):
        raise ValueError("missing ordinary strict proof of the four-argument tolerance claim")


def run(side, dest, physical_only):
    dest.mkdir(parents=True, exist_ok=True)
    jdk = Path(runtime_jdk.home("21"))
    env = dict(os.environ, JAVA_HOME=str(jdk), JVMCONTRACT_JAR_RELEASE="21", PATH=str(jdk / "bin") + os.pathsep + os.defpath)
    build = read(FOLDER / f"records/setup/build-{side}.json")
    artifact, = build["artifacts"]
    prior = read(ROOT / "verification/spring-java-data/exact-classpaths/classes.json")["373"][side]
    subject = prior["classes"][SUBJECT]
    java = runtime_jdk.release(jdk)["JAVA_RUNTIME_VERSION"]
    if (java != prior["jdk"]["JAVA_RUNTIME_VERSION"] or build["recipe"]["commit"] != prior["commit"]
            or artifact["sha256"] != subject["jarSha256"]):
        raise ValueError("the companion does not use the original JVM and historical module")
    with tempfile.TemporaryDirectory(prefix="positive-tolerance-") as tmp:
        work = Path(tmp)
        classes, jar = [work / name for name in CLASSPATH]
        classes.mkdir()
        shutil.copyfile(SETUP / f"artifacts/commons-lang-1589-{side}.jar", jar)
        if digest(jar) != artifact["sha256"]:
            raise ValueError("historical JAR digest mismatch")
        sources = [SOURCES / "ToleranceSearch.java", SOURCES / "ToleranceReplay.java", LOADED]
        subprocess.run([jdk / "bin/javac", "--release", "21", "-parameters", "-proc:none", "-cp", jar, "-d", classes, *sources], check=True)
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
        report = {"commit": prior["commit"], "jdk": java, "classpath": CLASSPATH,
                  "jarSha256": digest(jar), "sources": {s.name: digest(s) for s in sources},
                  "classes": {name: sha for name, _, _, _, sha in bindings}, "jvm": physical,
                  "words": [f"{w:016x}" for w in words()], "starts": list(STARTS), "grid": check_grid(grid),
                  "observationsSha256": digest(grid)}
        if not physical_only:
            checker = Path(os.environ["JVMCONTRACT"]).resolve()
            requests = [{"class": n, "method": m, "descriptor": d} for n, m, d, _, _ in bindings]
            answer, release = class_binding.ask(checker, env, work, {side: {"classpath": [str(classes), str(jar)], "classes": requests}})
            if release != 21:
                raise ValueError("different bytecode release")
            for bound, (name, _, _, provider, sha) in zip(answer[side]["bindings"], bindings, strict=True):
                problem = class_binding.disagreement(name, bound, str(provider), sha)
                if problem:
                    raise ValueError(problem)
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
