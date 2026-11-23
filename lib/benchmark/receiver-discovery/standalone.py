"""Run the opening controls with the pinned standalone JBMC and keep all completeness obligations."""

import argparse
import gzip
import json
from pathlib import Path
import subprocess
import tempfile

from callers import ASSETS, JDK, RESULTS, sha
from qualification import compile_original, write

PACKAGE = ASSETS / "jbmc/ubuntu-22.04"
BINARY = PACKAGE / "bin/jbmc"
MODELS = PACKAGE / "lib/core-models.jar"


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    if (
        sha(BINARY) != "2cf572542163ad3926d0030f4594e4697fcd09a0c60b62dc58901ca3aa18065c"
        or sha(MODELS) != "2a05026b3ab948ebb4820ccc2fc01040b96e226dc1f58a3be36dfe0c15ed14de"
    ):
        raise ValueError("standalone comparator identity")
    specs = [
        ("raw", "stock", "Checkout", "raw", 9, False),
        ("factory", "stock", "Checkout", "viaFactory", 9, False),
        ("alias-blind", "stock", "Checkout", "assumesDistinct", 9, False),
        ("caught-occurrence", "original", "SafetySites", "caught", 9, False),
        ("caught-exception", "original", "SafetySites", "caught", 9, True),
        ("helper-caught", "helper", "SafetySites", "caught", 9, True),
        ("helper-wrong", "helper", "SafetySites", "caughtMutant", 9, True),
        ("short", "original", "SafetySites", "loop", 3, True),
        ("complete", "original", "SafetySites", "loop", 9, True),
    ]
    out = RESULTS / "qualification/standalone"
    out.mkdir(parents=True, exist_ok=True)
    data = {}
    with tempfile.TemporaryDirectory() as r:
        tmp = Path(r)
        cp = {
            key: compile_original(
                "397" if key == "stock" else "398", "original" if key == "stock" else key, tmp / key
            )[0]
            for key in ("stock", "original", "helper")
        }
        for key, variant, owner, method, unwind, throw in specs:
            flags = [
                "--function",
                owner + "." + method,
                "--unwind",
                str(unwind),
                "--unwinding-assertions",
                "--max-nondet-array-length",
                "3",
                "--max-nondet-tree-depth",
                "4",
                "--no-refine-strings",
                "--trace",
                "--json-ui",
            ]
            if throw:
                flags.append("--throw-runtime-exceptions")
            run = subprocess.run(
                [BINARY, owner, "-cp", str(cp[variant]) + ":" + str(MODELS), *flags],
                capture_output=True,
                timeout=90,
            )
            if run.returncode not in (0, 10):
                raise ValueError((key, run.returncode, run.stderr[-300:]))
            doc = json.loads(run.stdout)
            props = [p for block in doc for p in block.get("result", [])]
            if not props:
                raise ValueError(key + " has no property output")
            path = out / (key + ".json.gz")
            path.write_bytes(gzip.compress(run.stdout, mtime=0))
            rows = [
                {k: p.get(k) for k in ("property", "description", "status", "sourceLocation")} for p in props
            ]
            user = [
                p
                for p in rows
                if p["property"].startswith("java::" + owner + "." + method + ":")
                and (p["sourceLocation"] or {}).get("propertyClass") == "assertion"
            ]
            if not user:
                raise ValueError(key + " has no bound user assertion")
            failed = [p["property"] for p in rows if p["status"] != "SUCCESS"]
            data[key] = {
                "flags": flags,
                "classSha256": sha(cp[variant] / (owner + ".class")),
                "exit": run.returncode,
                "userAssertions": user,
                "otherFailures": failed,
                "rawSha256": sha(path),
                "propertyCount": len(rows),
            }
            print(key, [(r["property"], r["status"]) for r in user], failed, flush=True)
    if (
        not data["raw"]["otherFailures"]
        or data["factory"]["otherFailures"]
        or not data["alias-blind"]["otherFailures"]
        or not any("unwind" in s for s in data["short"]["otherFailures"])
        or data["complete"]["otherFailures"]
    ):
        raise ValueError("comparator control disagreement")
    write(
        out / "measurement.json",
        {
            "jbmcSha256": sha(BINARY),
            "coreModelSha256": sha(MODELS),
            "subjectJdk": sha(JDK / "lib/modules"),
            "cases": data,
        },
    )


if __name__ == "__main__":
    main()
