"""Measure the frozen public entries through the project CLI, standalone JBMC and the original JVM."""
import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "java-semantics-gap"))
from campaign import JDK, ROOT, command, digest, integrated, javaenv, replay_witness, write
from standalone import decode
from subjects import Claim, Subject
from jvm_disassembly import methods

CACHE = Path.home() / ".cache/in-the-loop/jbmc-fast-follow"
EVIDENCE = ROOT / "verification/jbmc-fast-follow"
FAMILIES = {"callbacks": 392, "numeric": 393, "rows": 394, "strings": 395, "queue": 396}
ORACLES = {"callbacks": ("LiftChecks", "Replay", "ChainTests"), "numeric": ("NodeAssertions", "RoundingBoundaries"),
           "rows": ("RaggedJvm", "MatrixJvm"), "strings": ("OrderGrid",), "queue": ("QueueGrid",)}
OPENING = {"source": "a273d0afc61725080795a6af9731e3decc9aab71",
           "checker": "e41539fd3d8b935a8165c0e70257e2bd8f898e3e50c2346b473880930b00be65"}
GRID = ROOT / "examples/tools/targets/java/org/intheloop/controls/Grid.java"
PUBLIC = {
    "strings": ["org.apache.commons.lang3.ObjectUtils", "com.google.common.collect.Ordering", "com.google.common.collect.NaturalOrdering"],
    "queue": ["org.apache.commons.collections4.queue.CircularFifoQueue", "org.apache.commons.lang3.ArrayFill"],
    "callbacks": ["com.google.common.primitives.Longs", "com.google.common.collect.ComparisonChain",
                  "org.apache.commons.lang3.math.NumberUtils"],
    "numeric": ["com.fasterxml.jackson.databind.node.LongNode", "com.fasterxml.jackson.databind.node.DoubleNode",
                "org.apache.commons.lang3.mutable.MutableLong"],
    "rows": ["org.apache.commons.lang3.ArrayUtils", "org.apache.commons.collections4.iterators.ObjectArrayIterator",
             "org.apache.commons.math3.util.MathArrays", "org.apache.commons.math3.exception.DimensionMismatchException"],
}


def load(path):
    return json.loads(path.read_bytes())


def classpath(paths):
    return os.pathsep.join(map(str, paths))


def compile_sources(sources, target, cp, env):
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run([JDK / "bin/javac", "-g", "-parameters", "-proc:none", "-classpath", classpath(cp),
                    "-d", target, *sources], check=True, env=env)


def library_paths(folder, family):
    catalog = load(folder / "controls/libraries.json")
    revision = load(folder / "target.json")["history"]["revisions"][family]
    if revision["compileLibraries"] != revision["runtimeLibraries"]:
        raise ValueError("different compiler and runtime classpaths")
    jars = []
    for name in revision["runtimeLibraries"]:
        item = catalog[name]
        group, artifact, version = item["coordinates"].split(":")
        jar = CACHE / "m2" / group.replace(".", "/") / artifact / version / f"{artifact}-{version}.jar"
        if digest(jar) != item["sha256"]:
            raise ValueError(f"{name}: different release artifact")
        jars.append(jar)
    return jars


def bindings(checker, family, cp, work, env):
    sys.path.insert(0, str(ROOT / "examples/tools"))
    from targets import class_binding
    helper = work / "binding"
    compile_sources([ROOT / "examples/tools/targets/java/LoadedClasses.java"], helper, [], env)
    names = [p.stem for p in sorted(cp[0].glob("*.class"))] + PUBLIC[family]
    output = subprocess.check_output([JDK / "bin/java", "-XX:-UsePerfData", "-cp", classpath([helper, *cp]), "LoadedClasses",
                                      work, *names], env=env, text=True)
    observed = {n: ((work / p).resolve(), sha) for n, p, sha in (line.split("\t") for line in output.splitlines())}
    result, release = class_binding.ask(checker, env, work, {"original": {"classpath": list(map(str, cp)),
                                             "classes": [{"class": n} for n in names]}})
    if release != 21 or set(observed) != set(names):
        raise ValueError("incomplete original class bindings")
    providers = {}
    for name, bound in zip(names, result["original"]["bindings"], strict=True):
        path, sha = observed[name]
        if class_binding.disagreement(name, bound, str(path), sha):
            raise ValueError(f"different original JVM and checker class for {name}")
        providers[name] = {"classpathIndex": cp.index(path), "entry": bound["entry"], "sha256": sha}
    return providers


def original(folder, family, work, jars, raw, env):
    adapter = work / "adapter"
    driver = work / "driver"
    compile_sources(sorted((folder / "adapter").glob("*.java")), adapter, jars, env)
    cp = [adapter, *jars]
    compile_sources([GRID, folder / "driver/Cases.java", *sorted((folder / "controls/jvm").glob("*.java"))],
                    driver, cp, env)
    observations = {}
    for main in ("Cases", *ORACLES[family]):
        code, out, err, seconds = command([JDK / "bin/java", "-XX:-UsePerfData", "-ea", "-cp", classpath([driver, *cp]), main], env, 45)
        if code != 0:
            raise ValueError(f"{main} failed: {err.decode()}")
        (raw / (main + ".stdout")).write_bytes(out)
        observations[main] = {"sha256": digest(raw / (main + ".stdout")), "seconds": seconds}
        if main == "Cases":
            actual = [json.loads(line) for line in out.splitlines()]
            expected = load(folder / "controls/original.json")["cases"]
            if [(v["id"], v["input"], v["direct"]) for v in actual] != [(v["id"], v["input"], v["expected"]) for v in expected]:
                raise ValueError("original JVM disagrees with the frozen observations")
            observations[main]["cases"] = len(actual)
    if family == "callbacks":
        for owner in ("Lift", "Chain"):
            dest = raw / (owner + ".javap")
            with dest.open("wb") as stream:
                subprocess.run([JDK / "bin/javap", "-v", "-p", adapter / (owner + ".class")], stdout=stream, check=True)
            listing = dest.read_text()
            descriptors = ["Longs.compare:(JJ)I", "LambdaMetafactory.metafactory"]
            descriptors += ["(II)J", "(Ljava/lang/Integer;Ljava/lang/Integer;)J", "NumberUtils.compare:(SS)I", "(SS)J"] if owner == "Lift" else ["(Ljava/lang/Object;Ljava/lang/Object;)I", "(Ljava/lang/Integer;Ljava/lang/Integer;)I"]
            if any(s not in listing for s in descriptors):
                raise ValueError(f"{owner}: wrong javac method-handle descriptors")
    return cp, driver, observations


def stock_scalar(typ, value):
    if typ == "boolean":
        return {"true": True, "false": False}[value["data"]]
    bits = value["binary"]
    if typ == "double":
        return repr(struct.unpack(">d", int(bits, 2).to_bytes(8, "big"))[0])
    n = int(bits, 2)
    return n - (1 << len(bits)) if bits[0] == "1" else n


def stock_check(subject, claim, item, profile, work, raw, cp, driver, binary, core, env):
    owner, method = subject.owner, claim.method
    params = [p.strip().split() for p in claim.parameters.split(",") if p.strip()]
    names = ", ".join(name for _, name in params)
    args = claim.parameters
    setup = ""
    if profile == "alias":
        args += ", boolean tie"
        setup = "if(tie && a != null && a.length == 2) a[1] = a[0];"
    target = item.get("standalone", "FollowAssertions.target") if profile != "alias" else "FollowAssertions.target"
    src = work / "FollowAssertions.java"
    call = f"{owner}.{method}({names})"
    src.write_text("class FollowAssertions {\n"
                   + f"public static void target({args}) {{ {setup} assert {call}; }}\n"
                   + f"public static void reached({args}) {{ {setup} if (!({item['reachGuard']})) return; {call}; assert false; }}\n}}\n")
    compiled = work / "assertions"
    compile_sources([src], compiled, cp, env)
    ordered = [compiled, driver, *cp]
    layers = {"comparator": ("Comparator", "31213c77d79b01f269b7e3ee1008a1cbe0ce11b4442d2401346de6ca80d8d095"),
              "arrays": ("Arrays", "4a41d89cb79284298b95303a66b3738955d22694f9b34016d87241d9ae8193ab")}
    selected = []
    if profile in layers:
        class_name, wanted = layers[profile]
        layer = work / "jdk-layer"
        rel = Path(f"java/util/{class_name}.class")
        (layer / rel).parent.mkdir(parents=True)
        shutil.copyfile(CACHE / "jdk/temurin-21.0.13/classes" / rel, layer / rel)
        if digest(layer / rel) != wanted:
            raise ValueError(f"different {class_name} class")
        selected.append("jdk:" + rel.as_posix())
        ordered.append(layer)
    flags = ["--unwind", "8" if subject.example in (392, 395, 396) else "7", "--unwinding-assertions",
             "--throw-runtime-exceptions", "--sat-solver", "cadical", "--trace", "--json-ui"]
    if subject.example == 395:
        flags += ["--java-assume-inputs-non-null", "--max-nondet-string-length", "2", "--max-nondet-array-length", "2"]
    if subject.example == 394:
        flags += ["--max-nondet-array-length", "2", "--max-nondet-tree-depth", "5"]
    results = {"flags": flags, "driverSha256": digest(compiled / "FollowAssertions.class"),
               "classpath": ["assertions", "drivers", "product", *[jar.name for jar in cp[1:]],
                             *selected, core.name]}
    for key, entry in [("target", target), ("reached", "FollowAssertions.reached")]:
        cls, name = entry.split(".")
        code, out, err, secs = command([binary, cls, "--function", entry, "-cp", classpath([*ordered, core]), *flags], env, 120)
        (raw / (key + ".json")).write_bytes(out)
        (raw / (key + ".stderr")).write_bytes(err)
        summary = decode(out, err, code, name, cls)
        summary.update(seconds=secs, entry=entry)
        if key == "target" and summary["status"] == "FAILURE" and all(p[0] != "String" and "[]" not in p[0] for p in params):
            inputs = []
            for typ, param in params:
                if param not in summary["inputs"]:
                    break
                inputs.append({"type": typ, "value": stock_scalar(typ, summary["inputs"][param])})
            if len(inputs) == len(params):
                summary["jvmReplay"] = replay_witness(subject, claim, {"counterexample": {"inputs": inputs}}, work, cp, env)
        # Full stock values (including heap traces) are in the raw property report.
        results[key] = summary
    return results


def measure(args):
    family = args.family
    folder, = (ROOT / "examples").glob(f"{FAMILIES[family]}-*")
    jars = library_paths(folder, family)
    if args.lane == "seed":
        sys.path.insert(0, str(ROOT / "examples/tools"))
        from targets.runtime_maven import Cache
        cache = Cache()
        for jar in jars:
            sha = digest(jar)
            if not cache.path(sha).is_file() or digest(cache.path(sha)) != sha:
                cache.store(jar, sha)
        return
    env = javaenv()
    binary = (CACHE / "jbmc/ubuntu-22.04/bin/jbmc") if family == "numeric" or args.lane == "packaged-22" else Path("/usr/bin/jbmc")
    core = binary.parent.parent / "lib/core-models.jar" if family == "numeric" or args.lane == "packaged-22" else Path("/usr/lib/core-models.jar")
    env["PATH"] = str(binary.parent) + os.pathsep + env["PATH"]
    checker = Path(env.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")).resolve()
    env["JVMCONTRACT"] = str(checker)
    target = load(folder / "target.json")
    tasks = {t["id"]: t for t in target["tasks"] if t["kind"] == "prove"}
    register = load(folder / "controls/comparison.json")
    if set(tasks) != {i["task"] for i in register}:
        raise ValueError("the example and comparison register differ")
    dest = args.output / args.phase / family / args.lane
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="jbmc-follow-") as tmp:
        work = Path(tmp)
        raw = work / "raw"
        raw.mkdir()
        cp, driver, physical = original(folder, family, work, jars, raw, env)
        report = {"phase": args.phase, "family": family, "lane": args.lane, "predecessor": OPENING,
                  "measuredSource": env.get("VERIFY_SOURCE_COMMIT"), "job": env.get("VERIFY_JOB_ID"),
                  "checkerSha256": digest(checker), "jbmcSha256": digest(binary), "coreModelsSha256": digest(core),
                  "jdkModulesSha256": digest(JDK / "lib/modules"), "javaSha256": digest(JDK / "bin/java"),
                  "jars": [{"name": j.name, "sha256": digest(j)} for j in jars],
                  "productClasses": {p.name: digest(p) for p in sorted(cp[0].glob("*.class"))},
                  "driverClasses": {p.relative_to(driver).as_posix(): digest(p) for p in sorted(driver.rglob("*.class"))},
                  "originalJvm": physical, "rows": []}
        descriptors = {}
        if args.phase in ("final", "successor"):
            report["classBindings"] = bindings(checker, family, cp, work, env)
        for item in register:
            task = tasks[item["task"]]
            owner, method = task["target"].split("#")
            spec = load(folder / task["claim"])
            if args.cohort and item["cohort"] not in args.cohort: continue
            if args.methods and method not in args.methods: continue
            if args.lane == "arrays" and item["cohort"] != "fill": continue
            if args.lane == "comparator" and owner != "Chain": continue
            if args.lane == "alias" and (owner != "RaggedProof" or method not in ("reversed", "distinct")): continue
            claim = Claim(method, item["parameters"], fails=((),) if task["expected"] == "refuted" else (),
                          nullable=next(iter(spec.get("nullable", [])), ""))
            subject = Subject(FAMILIES[family], owner, family, (claim,), spec["bounds"]["maxArrayLength"], spec["bounds"]["unwind"])
            row = dict(item, target=task["target"], expected=task["expected"], specSha256=digest(folder / task["claim"]), bounds=spec["bounds"])
            if args.phase in ("final", "successor"):
                if owner not in descriptors:
                    entries, dis = methods(JDK / "bin/javap", cp[0] / (owner + ".class"))
                    descriptors[owner] = entries
                    (raw / (owner + ".bytecode")).write_text(dis)
                descriptor, = [desc for name, desc in descriptors[owner] if name == method]
                row["descriptor"] = descriptor
            for lane in (("native", "jbmc") if args.lane == "paired" else (args.lane,)):
                if lane == "jvm": continue
                scratch = work / task["id"] / lane
                outputs = raw / task["id"] / lane
                scratch.mkdir(parents=True)
                outputs.mkdir(parents=True)
                if lane in ("native", "jbmc"):
                    result = integrated(subject, claim, lane, scratch, outputs, cp, env, record_process_errors=True)
                    input_dir = scratch / "proof/ragged-input"
                    if input_dir.is_dir():
                        sources = list(input_dir.glob("*.java"))
                        if len(sources) != 1:
                            raise ValueError("missing generated row-input source")
                        src, = sources
                        shutil.copyfile(src, outputs / src.name)
                        cls = src.with_suffix(".class")
                        result["rowInput"] = {"source": src.name, "sha256": digest(src),
                                              "classSha256": digest(cls) if cls.exists() else None}
                    if args.require and (result["disposition"] != "correct" or result.get("jvmReplay", {}).get("outcome", "refuted") != "refuted"):
                        raise ValueError(f"{task['target']} {lane}: {result}")
                    row[lane] = result
                else:
                    row[lane] = stock_check(subject, claim, item, lane, scratch, outputs, cp, driver, binary, core, env)
                print(task["target"], lane, row[lane].get("disposition", row[lane].get("target", {}).get("status")), flush=True)
            report["rows"].append(row)
        if not report["rows"]:
            raise ValueError("no registered statement matched")
        with tarfile.open(dest / "raw.tar.gz", "w:gz") as archive:
            archive.add(raw, arcname="raw")
        report["rawSha256"] = digest(dest / "raw.tar.gz")
        write(dest / "measurement.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase")
    parser.add_argument("family", choices=FAMILIES)
    parser.add_argument("lane", choices=("seed", "jvm", "paired", "native", "jbmc", "packaged", "packaged-22", "comparator", "arrays", "alias"))
    parser.add_argument("--cohort", nargs="+")
    parser.add_argument("--methods", nargs="+")
    parser.add_argument("--require", action="store_true", help="require every selected project verdict to qualify")
    parser.add_argument("--output", type=Path, default=EVIDENCE)
    measure(parser.parse_args())
