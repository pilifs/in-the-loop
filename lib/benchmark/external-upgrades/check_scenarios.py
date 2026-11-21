"""Run the original-classpath finite observations for selected engineering corpus cases."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import hashlib
import sys

from engineering import HERE, ROOT, resolved_operand, digest, read, git, preparation_root


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case", action="append", required=True)
    ap.add_argument("--preparations", required=True, type=Path)
    ap.add_argument("--maven-cache", required=True, type=Path)
    ap.add_argument("--repositories", type=Path, help="original Git repositories for source-derived fixtures")
    ap.add_argument("--complete", type=Path, action="append", default=[],
                    help="prefer these full Maven modules when both sides are available, in option order")
    ap.add_argument("--variant", choices=("operational",), help="run a declared additional observation for the original case")
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    cases = {c["id"]: c for c in read(HERE / "corpus.json")["cases"]}
    args.output.mkdir(parents=True, exist_ok=True)
    for key in args.case:
        started = time.monotonic()
        original = cases[key]
        directory = HERE / "scenarios" / key
        if args.variant:
            directory = directory / args.variant
        out = args.output / (key + ".json")
        if out.exists():
            raise ValueError(f"existing result for {key}")
        if not (directory / "scope.json").is_file():
            out.write_text(json.dumps({"status": "open", "entry": original["entry"], "revisions": original["revisions"],
                "reason": "No finite caller observation is registered for this scope.",
                "elapsedSeconds": round(time.monotonic() - started, 3)}, indent=2) + "\n")
            print(key, "open", flush=True)
            continue
        jdk = ("8.0.512.0+9-tem" if original["origin"].startswith("CompSuite") or key == "ea-async-27"
               else "21.0.13.0+9-tem")
        cmd = [sys.executable, str(ROOT / "examples/tools/build.py"), "--review-upgrade",
               "--spec", str(directory / "scope.json"), "--probe", str(directory / "UpgradeProbe.java"),
               "--jdk", str(Path.home() / ".sdkman/candidates/java" / jdk), "--output", str(out)]
        prep = preparation_root(args.preparations, args.complete, key)
        try:
            for side in ("old", "new"):
                manifest = prep/key/side/"prepared.json"
                if manifest.is_file():
                    value = read(manifest).get("subjectJdk")
                    if value in ("Temurin 8", "8.0.512.0+9-tem"):
                        jdk = "8.0.512.0+9-tem"
                    elif value == "21.0.13.0+9-tem":
                        jdk = value
                    break
            cmd[cmd.index("--jdk")+1] = str(Path.home()/".sdkman/candidates/java"/jdk)
            for side, flag in (("old", "--before"), ("new", "--after")):
                cmd += [flag, str(prep / key / side / "prepared.json"),
                        "--" + side + "-dependency", digest(resolved_operand(args.maven_cache, original, side)[0])]
            with tempfile.TemporaryDirectory(prefix="upstream-fixtures-") as temp:
                scope = read(directory / "scope.json")
                if args.variant:
                    source = scope["originalCallerSource"]
                    repositories = read(args.repositories or args.preparations.parent / "repos.json")
                    for revision in original["revisions"].values():
                        data = git(repositories[key], "show", revision + ":" + source["path"])
                        if hashlib.sha256(data).hexdigest() != source["sha256"]:
                            raise ValueError("the additional caller's source differs from the registered original")
                companions = scope.get("runtimeCompanions", [])
                if companions:
                    for side, flag in (("old","--before"), ("new","--after")):
                        position = cmd.index(flag)+1
                        document = read(cmd[position])
                        for companion in companions:
                            path = (args.maven_cache/companion["mavenPath"]).resolve()
                            if not path.is_relative_to(args.maven_cache.resolve()) or digest(path)!=companion["sha256"]:
                                raise ValueError("the original runtime companion differs from its registered digest")
                            if not any(row["sha256"]==companion["sha256"] for row in document["classpath"]):
                                document["classpath"].append({"file":str(path),"sha256":companion["sha256"]})
                        qualified = Path(temp)/(side+"-prepared.json")
                        qualified.write_text(json.dumps(document))
                        cmd[position] = str(qualified)
                fixtures = scope.get("fixtures", [])
                if fixtures:
                    repos = read(args.repositories or (args.preparations.parent / "repos.json"))
                    for fixture in fixtures:
                        source = fixture["source"]
                        old, new = (git(repos[key], "show", original["revisions"][side]+":"+source) for side in ("old","new"))
                        if old != new or hashlib.sha256(old).hexdigest() != fixture["sha256"]:
                            raise ValueError("the original paired fixture bytes differ from the input lock")
                        dest = Path(temp) / fixture["file"]
                        if not dest.resolve().is_relative_to(Path(temp).resolve()):
                            raise ValueError("fixture path leaves the supplied input directory")
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(old)
                    cmd += ["--fixtures", temp]
                proc = subprocess.run(cmd, cwd=ROOT, check=False)
            if proc.returncode and not out.is_file():
                raise ValueError(f"workflow exited {proc.returncode} before writing a case report")
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            out.write_text(json.dumps({"status": "open", "reason": str(exc),
                                       "elapsedSeconds": round(time.monotonic() - started, 3)}, indent=2) + "\n")
        print(key, read(out)["status"], flush=True)


if __name__ == "__main__":
    main()
