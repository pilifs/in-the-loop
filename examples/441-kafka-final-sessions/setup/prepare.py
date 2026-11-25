"""Rebuild Kafka's omitted test-driver JAR from each exact pin, on the locked Streams classpath."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile, ZipInfo

FOLDER = Path(__file__).resolve().parents[1]
MODULE = "streams/test-utils/src/main/java"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(cache, output):
    runtime = json.loads((FOLDER / "runtime.json").read_text())
    revisions = json.loads((FOLDER / "comparison.json").read_text())["revisions"]
    jdk = Path.home() / ".sdkman/candidates/java/17.0.21.0+9-tem"
    output.mkdir(parents=True, exist_ok=True)
    for side, pin in revisions.items():
        git = ["git", "-C", cache / f"worktrees/L19-kafka-{side}"]
        names = subprocess.check_output([*git, "ls-tree", "-r", "--name-only", pin, "--", MODULE], text=True)
        cp = (cache / f"artifacts/L19-kafka-{side}.streams-test-utils-runtime-classpath.txt").read_text().strip()
        for file in map(Path, cp.split(os.pathsep)):
            if sha(file) != runtime["sha256"][str(file.relative_to(cache))]:
                raise ValueError(f"changed compilation dependency {file.name}")
        with tempfile.TemporaryDirectory(prefix="kafka-driver-") as t:
            work = Path(t)
            classes = work / "classes"
            classes.mkdir()
            sources = []
            for name in names.splitlines():
                if name.endswith(".java"):
                    file = work / Path(name).relative_to(MODULE)
                    file.parent.mkdir(parents=True, exist_ok=True)
                    file.write_bytes(subprocess.check_output([*git, "show", f"{pin}:{name}"]))
                    sources.append(file)
            subprocess.run([jdk/"bin/javac", "--release", "8", "-g", "-proc:none", "-cp", cp,
                            "-d", classes, *sources], check=True)
            if not (classes/"org/apache/kafka/streams/TopologyTestDriver.class").is_file():
                raise ValueError("missing compiled TopologyTestDriver")
            target = output / f"L19-kafka-{side}-test-driver.jar"
            with tempfile.NamedTemporaryFile(dir=output) as tmp:
                with ZipFile(tmp.name, "w") as jar:
                    for file in sorted(classes.rglob("*.class")):
                        jar.writestr(ZipInfo(file.relative_to(classes).as_posix()), file.read_bytes())
                digest = sha(Path(tmp.name))
                try:
                    os.link(tmp.name, target)
                except FileExistsError:
                    if sha(target) != digest: raise ValueError(f"{target.name} contains another build")
                print(side, pin, digest, target.name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=Path.home()/".cache/in-the-loop/merged-pr-links-l01-l20")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    prepare(args.cache, args.output or args.cache/"artifacts")
