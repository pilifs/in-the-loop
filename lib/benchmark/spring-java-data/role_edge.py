"""Replay the omitted Spring hierarchy edge or measure its paired native decisions."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

from measure import ROOT, digest, write
from historical_companion import bind, prepare_graph
import checker_output
from targets import runtime

FOLDER = ROOT / "examples/370-spring-role-hierarchy"
SOURCE = FOLDER / "companions/HierarchyEdge.java"
CALLER = "springwork.HierarchyEdge"
BOUNDS = (256, 16384)
EXPECTED = ["ROLE_ 5", "CUSTOM_PREFIX_ 5"]


def qualify(raw, method):
    packet = checker_output.wire.decode(raw.decode(), "prove")
    if not packet.ok or len(packet.outcomes) != 1:
        raise ValueError("missing hierarchy decision outcome")
    outcome, = packet.outcomes
    stated = outcome["stated"]
    assumptions = stated["assumptions"]
    if (outcome["target"] != f"{CALLER}#{method}()" or outcome["assert"] != "result == 5"
            or outcome.get("assume") is not None or outcome["verdict"] != "verified" or outcome["problem"]
            or outcome["counterexample"] or stated["domain"]["parameters"] or stated["domain"]["shared_arrays"]
            or stated["checker"]["engine"] != "native" or stated["checker"]["fallback"] is not None
            or stated["gap_mode"] != "strict" or stated["vacuity"]["status"] != "non-vacuous"
            or stated["observations"]["exceptions"] != "none may be thrown" or outcome["throws"]
            or stated["bounds"] != {"complete": True, "max_array_length": None, "unwind": BOUNDS[0]}
            or outcome["search"]["max_array_length"] != BOUNDS[1] or outcome["search"]["properties"] != 1
            or any(a["basis"] != "engine" for a in assumptions)):
        raise ValueError(f"different ordinary public decision or scope for {method}")
    return assumptions


def measure(side, replay, checker):
    with tempfile.TemporaryDirectory(prefix="spring-role-edge-") as scratch:
        work = Path(scratch)
        jdk, original, paths, bound = prepare_graph(FOLDER, side, "legacy-decision-" + side, work)
        classes = work / "classes"
        classes.mkdir()
        classpath = os.pathsep.join(map(str, paths[1:]))
        subprocess.run([jdk / "bin/javac", "-J-XX:-UsePerfData", "--release", "21", "-proc:none",
                        "-cp", classpath, "-d", classes, SOURCE], check=True)
        observed = subprocess.check_output([jdk / "bin/java", "-XX:-UsePerfData", "-cp", str(classes) + os.pathsep + classpath, CALLER])
        output = observed.decode().splitlines()
        if output != EXPECTED:
            raise ValueError(f"{side} original JVM returned {output}")
        print(side, *output, sep=" | ")
        if replay:
            return
        dest = FOLDER / "records/edge-control" / side
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "jvm.stdout").write_bytes(observed)
        env = runtime._verifier_env({"home": str(jdk)})
        env["JVMCONTRACT_JAR_RELEASE"] = "21"
        caller = classes / "springwork/HierarchyEdge.class"
        (dest / "HierarchyEdge.jvm-bytecode").write_bytes(caller.read_bytes())
        bindings = [(CALLER, m, "()I", classes, digest(caller)) for m in ("role", "custom")]
        for name, info in original["classes"].items():
            jar = next(path for path, stamp in zip(paths, bound, strict=True) if stamp["sha256"] == info["jarSha256"])
            bindings.append((name, None, None, jar, info["classSha256"]))
        report = {"job": os.environ["VERIFY_JOB_ID"], "source": os.environ["VERIFY_SOURCE_COMMIT"],
                  "revision": original["commit"], "jdk": original["jdk"], "classpath": bound[1:],
                  "callerSource": digest(SOURCE), "callerClass": digest(caller),
                  "bindings": bind(checker, env, work, side, bindings, classpath=[classes, *paths[1:]]),
                  "checkerSha256": digest(checker), "libTree": os.environ["JVMCONTRACT_LIB_TREE"], "jvm": output, "proofs": {}}
        for method in ("role", "custom"):
            argv = [checker, "prove", f"{CALLER}#{method}()", "--classes", classes]
            for path in paths[1:]:
                argv.extend(["--classpath", path])
            argv += ["--assert", "result == 5", "--engine", "native", "--gaps", "strict", "--unwind", str(BOUNDS[0]),
                     "--max-array-length", str(BOUNDS[1]), "--timeout", "60", "--work", work / method, "--json"]
            raw = dest / (method + ".json")
            with raw.open("wb") as stream:
                subprocess.run(argv, stdout=stream, env=env, timeout=75, check=True)
            report["proofs"][method] = {"sha256": digest(raw), "assumptions": qualify(raw.read_bytes(), method)}
        write(dest / "measurement.json", report)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--replay", action="store_true", help="run both original JVMs")
    args = cli.parse_args()
    checker = None if args.replay else Path(os.environ["JVMCONTRACT"]).resolve(strict=True)
    for revision in ("before", "landed"):
        measure(revision, args.replay, checker)
