"""Run the original-classpath finite observations for selected engineering corpus cases."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from engineering import HERE, ROOT, dependency_file, digest, read


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case", action="append", required=True)
    ap.add_argument("--preparations", required=True, type=Path)
    ap.add_argument("--maven-cache", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    cases = {c["id"]: c for c in read(HERE / "corpus.json")["cases"]}
    args.output.mkdir(parents=True, exist_ok=True)
    for key in args.case:
        original = cases[key]
        directory = HERE / "scenarios" / key
        out = args.output / (key + ".json")
        if out.exists():
            raise ValueError(f"existing result for {key}")
        jdk = ("8.0.512.0+9-tem" if original["origin"].startswith("CompSuite") or key == "ea-async-27"
               else "21.0.13.0+9-tem")
        cmd = [sys.executable, str(ROOT / "examples/tools/build.py"), "--review-upgrade",
               "--spec", str(directory / "scope.json"), "--probe", str(directory / "UpgradeProbe.java"),
               "--jdk", str(Path.home() / ".sdkman/candidates/java" / jdk), "--output", str(out)]
        try:
            for side, flag in (("old", "--before"), ("new", "--after")):
                cmd += [flag, str(args.preparations / key / side / "prepared.json"),
                        "--" + side + "-dependency", digest(args.maven_cache / dependency_file(original, side))]
            proc = subprocess.run(cmd, cwd=ROOT, check=False)
            if proc.returncode and not out.is_file():
                raise ValueError(f"workflow exited {proc.returncode} before writing a case report")
        except (ValueError, OSError) as exc:
            out.write_text(json.dumps({"status": "open", "reason": str(exc)}, indent=2) + "\n")
        print(key, read(out)["status"], flush=True)


if __name__ == "__main__":
    main()
