"""Run the direct CLI diagnostic after reproduce.py on the unchanged full consumer JARs."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True, help="completed full-source JVM reproduction")
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--checker", type=Path, required=True)
    parser.add_argument("--jdk", type=Path, required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[1]
    work, inputs, checker, jdk = (path.resolve() for path in (args.work, args.inputs, args.checker, args.jdk))
    claim = json.loads((folder / "claims/escape-csv.json").read_text())
    output = work / "native-probe"
    output.mkdir()
    binding = {}
    for side in ("old", "new"):
        jar = work / side / "client.jar"
        classes = work / side / "client.classes"
        with zipfile.ZipFile(jar) as archive:
            members = {n for n in archive.namelist() if n.endswith(".class")}
            local = {p.relative_to(classes).as_posix() for p in classes.rglob("*.class")}
            if members != local or any(archive.read(n) != (classes / n).read_bytes() for n in members):
                raise ValueError(f"{side} class directory differs from the JVM replay JAR")
        binding[side] = {"clientJarSha256": hashlib.sha256(jar.read_bytes()).hexdigest(), "classes": len(members)}
    argv = [str(checker), "equivalence", "--before", str(work / "old/client.classes"),
            "--after", str(work / "new/client.classes"), "--before-classpath", str(inputs / "commons-lang3-3.16.0.jar"),
            "--classpath", str(inputs / "commons-lang3-3.17.0.jar"), "--target", "org.apache.commons.text.StringEscapeUtils#escapeCsv",
            "--assume", claim["assume"], "--engine", "native", "--gaps", "strict", "--unwind", str(claim["bounds"]["unwind"]),
            "--max-array-length", str(claim["bounds"]["maxArrayLength"]), "--timeout", "30", "--work", str(output / "work"),
            "--report", str(output / "report"), "--json"]
    env = {**os.environ, "JAVA_HOME": str(jdk), "PATH": f"{jdk}/bin:{os.environ['PATH']}", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC"}
    started = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    clock = time.monotonic()
    with (output / "checker.json").open("w") as out, (output / "checker.stderr").open("w") as err:
        result = subprocess.run(argv, env=env, stdout=out, stderr=err, timeout=290)
    elapsed = round(time.monotonic() - clock, 3)
    report = {
        "startedUtc": started, "elapsedSeconds": elapsed, "exit": result.returncode,
        "command": [a.replace(str(work), "$WORK").replace(str(inputs), "$INPUTS").replace(str(checker), "$CHECKER") for a in argv],
        "checkerSha256": hashlib.sha256(checker.read_bytes()).hexdigest(), "classes": binding,
        "jdkReleaseSha256": hashlib.sha256((jdk / "release").read_bytes()).hexdigest(),
        "stdoutSha256": hashlib.sha256((output / "checker.json").read_bytes()).hexdigest(),
        "stderr": (output / "checker.stderr").read_text(),
    }
    (output / "run.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"original direct CLI exit {result.returncode} after {elapsed:.3f} s")


if __name__ == "__main__":
    main()
