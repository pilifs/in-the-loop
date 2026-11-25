"""Measure previously selected public candidates in a neutral namespace when impact ranking changes."""
import json
import os
from pathlib import Path

import auto_upgrade as operator


def main():
    pair, scratch, raw = Path("/inputs"), Path("/scratch"), Path("/output")
    jdk, checker = Path("/opt/jdk"), Path("/opt/checker")
    doc = json.loads((pair / "inputs.json").read_bytes())
    graphs, roots = [], []
    for side in ("old", "new"):
        files = [pair / item["path"] for item in doc[side]]
        if any(operator.digest(f.read_bytes()) != r["sha256"] for f, r in zip(files, doc[side])):
            raise ValueError("different locked deployment")
        graphs.append(files)
        root = scratch / side
        operator.extract(files[0], root)
        roots.append(root)
    env = dict(os.environ, JAVA_HOME=str(jdk), JVMCONTRACT_JAR_RELEASE="21")
    helpers = scratch / "helpers"
    helpers.mkdir()
    code, _ = operator.run([jdk / "bin/javac", "-proc:none", "-d", helpers, operator.HERE / "ArtifactProbe.java"],
                           scratch, 40, raw / "helper.out", env)
    if code:
        raise ValueError("original physical probe failed to compile")
    rows, repeats = [], []
    for i, candidate in enumerate(json.loads(Path("/locked.json").read_bytes())):
        work = scratch / f"case{i}"
        out = raw / f"case{i}"
        row = operator.exercise(candidate, graphs, roots, work, out, checker, jdk, env)
        rows.append(row)
        if row["status"] == "measured":
            code, data = operator.run(row["argv"], work, 150, out / "warm.json", env)
            parsed = operator.wire.decode(data.decode(errors="replace"), "equivalence")
            verdict = parsed.outcomes[0].get("verdict") if parsed.ok and len(parsed.outcomes) == 1 else None
            repeats.append({"candidate": candidate["id"], "exit": code, "verdict": verdict, "sameVerdict": verdict == row["verdict"]})
    operator.save(raw / "locked-report.json", {"runs": rows, "warm": repeats})


if __name__ == "__main__":
    main()
