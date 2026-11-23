"""Check the released long[][] method itself, then the exact metadata of its mismatch."""
import argparse
import os
from pathlib import Path
import tempfile

from measure import EVIDENCE, JDK, ROOT, Claim, Subject, classpath, command, compile_sources, digest, integrated, javaenv, library_paths, write
from campaign import wire

OWNER = "org.apache.commons.math3.util.MathArrays"
ENTRY = OWNER + "#checkRectangular([[J)V"
BOTH = "in != null && in.length == 2 && in[0] != null && in[1] != null"
EXCEPTION = "org.apache.commons.math3.exception.DimensionMismatchException"
DIRECT = [
    ("equal-width", BOTH + " && in[0].length == in[1].length", []),
    ("singleton-null", "in != null && in.length == 1 && in[0] == null", []),
    ("unequal-width", BOTH + " && in[0].length != in[1].length", [EXCEPTION + " when true"]),
]


def main(destination):
    folder, = (ROOT / "examples").glob("394-*")
    jars = library_paths(folder, "rows")
    jar, = [p for p in jars if p.name.startswith("commons-math3-")]
    env = javaenv()
    checker = Path(env["JVMCONTRACT"]).resolve()
    report = {"source": env.get("VERIFY_SOURCE_COMMIT"), "job": env.get("VERIFY_JOB_ID"), "checker": digest(checker),
              "jbmcMemoryMiB": int(env.get("JVMCONTRACT_JBMC_MEMORY_MB", "4096")), "jar": jar.name, "jarSha256": digest(jar), "entry": ENTRY, "direct": {}, "metadata": {}}
    with tempfile.TemporaryDirectory(prefix="matrix-transfer-") as name:
        work = Path(name)
        for key, guard, throws in DIRECT:
            runs = {}
            for engine in ("native", "jbmc"):
                raw = destination / key / engine
                raw.mkdir(parents=True, exist_ok=True)
                args = [checker, "prove", ENTRY, "--classes", jar, "--assume", guard, "--assert", "true", "--nullable", "in",
                        "--max-array-length", "2", "--unwind", "7", "--gaps", "strict", "--timeout", "120",
                        "--engine", engine, "--jbmc-staging", "staged", "--work", work / (key + engine), "--json"]
                for signal in throws: args.extend(["--throws", signal])
                code, out, err, secs = command(args, env, 170)
                (raw / "stdout.json").write_bytes(out)
                (raw / "stderr.txt").write_bytes(err)
                parsed = wire.decode(out.decode(), "prove")
                if not parsed.ok or len(parsed.outcomes) != 1: raise ValueError(f"{key}/{engine}: process error {code}")
                row, = parsed.outcomes
                if row["target"] != ENTRY or row.get("assume") != guard or row["assert"] != "true" or row["throws"] != throws:
                    raise ValueError("the public target or guard changed")
                if row["verdict"] == "verified":
                    stated = row["stated"]
                    if row["search"]["engine"] != engine or stated["checker"].get("fallback") or stated["gap_mode"] != "strict" or not stated["bounds"]["complete"] or stated["vacuity"]["status"] != "non-vacuous":
                        raise ValueError(f"{key}/{engine}: unconditional scope or reachability missing")
                if engine == "native" and row["verdict"] != "verified": raise ValueError(f"{key}: {row.get('problem')}")
                runs[engine] = {"verdict": row["verdict"], "firstUnproved": row.get("problem"), "seconds": secs,
                                "stdoutSha256": digest(raw / "stdout.json"), "guard": guard, "throws": throws}
            report["direct"][key] = runs
        classes = work / "metadata"
        source = folder / "controls/MatrixMetadata.java"
        compile_sources([source], classes, [jar], env)
        report["metadataClassSha256"] = digest(classes / "MatrixMetadata.class")
        code, out, err, _ = command([JDK / "bin/java", "-XX:-UsePerfData", "-ea", "-cp", classpath([classes, jar]), "MatrixMetadata"], env)
        if code or not out.startswith(b"16 two-row shapes; all 6 mismatches"): raise ValueError(err.decode() or out.decode())
        report["originalJvmMetadata"] = out.decode().strip()
        for method in ("correct", "swapped"):
            claim = Claim(method, "long[][] matrix", nullable="matrix", fails=((),) if method == "swapped" else ())
            subject = Subject(394, "MatrixMetadata", "rows", (claim,), 2, 7)
            results = {}
            for engine in ("native", "jbmc"):
                raw = destination / method / engine
                raw.mkdir(parents=True, exist_ok=True)
                scratch = work / (method + engine)
                scratch.mkdir()
                row = integrated(subject, claim, engine, scratch, raw, [classes, jar], env)
                if engine == "native" and row["disposition"] != "correct": raise ValueError(f"{method}: {row}")
                results[engine] = row
            report["metadata"][method] = results
    write(destination / "measurement.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=EVIDENCE / "matrix")
    main(parser.parse_args().output)
