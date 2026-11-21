"""Run the public driver-selection check on the two original rxjava-jdbc classpaths and an unmatched URL."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
TARGET = ROOT / "examples/348-rxjava-jdbc-generated-keys/target.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maven-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jdk", type=Path, default=Path.home()/".sdkman/candidates/java/8.0.512.0+9-tem")
    args = parser.parse_args()
    target = json.loads(TARGET.read_text())
    test = ROOT / "examples/348-rxjava-jdbc-generated-keys/independent/Observe.java"
    url = "jdbc:h2:mem:calibration;DB_CLOSE_DELAY=-1"
    if '"' + url + '"' not in test.read_text():
        raise ValueError("the URL differs from the original calibration")
    with tempfile.TemporaryDirectory(prefix="h2-driver-inputs-") as temp:
        for side in ("old", "new"):
            artifacts = [a for a in target["preparation"]["artifacts"] if a["revision"] == side]
            rows = [{"file": str((args.maven_cache / a["url"].split("/maven2/")[1]).resolve()), "sha256": a["sha256"]}
                    for a in artifacts]
            operand, = [a["sha256"] for a in artifacts if a["coordinates"].startswith("com.h2database:h2:")]
            manifest = Path(temp)/(side+".json")
            manifest.write_text(json.dumps({"classpath": rows}))
            for name, request, expected in (("original", url, "selected"), ("unmatched", "jdbc:unregistered:control", "none")):
                path = args.output / side / (name+".json")
                subprocess.run([sys.executable, str(ROOT/"examples/tools/build.py"), "--inspect-jdbc-driver",
                                "--prepared", str(manifest), "--dependency", operand, "--jdk", str(args.jdk),
                                "--url", request, "--output", str(path)], check=True)
                result = json.loads(path.read_text())
                selection = result["driver"]["selection"]
                if (result["classpath"] != [r["sha256"] for r in rows] or selection["outcome"] != expected
                        or result["urlSha256"] != hashlib.sha256(request.encode()).hexdigest()):
                    raise ValueError("unexpected JDBC selection or classpath")
                if expected == "selected" and (selection["name"] != "org.h2.Driver" or selection["jarSha256"] != operand):
                    raise ValueError("the selected driver did not come from the original H2 version")
                if expected == "none" and selection["sqlState"] != "08001":
                    raise ValueError("the unrecognized URL had another failure")


if __name__ == "__main__":
    main()
