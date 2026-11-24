"""Retain the frozen checker's original charset refusal when it happens before JSON reporting."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from register import CASE, sha
from plan_run import JDK, OUTPUT, ROOT


def main():
    checker = os.environ.get("JVMCONTRACT", str(ROOT / "lib/target/release/jvmcontract"))
    owner = "org.apache.commons.io.Charsets"
    reason = ("jvmcontract: --observed-initializer " + owner + ": its code reads the default charset "
              "(java.nio.charset.Charset.defaultCharset), which the observation cannot bind")
    result = {}
    for side in ("old", "new"):
        jar, = json.loads((CASE / side / "prepared.json").read_bytes())["classpath"]
        if sha(Path(jar["file"])) != jar["sha256"]:
            raise ValueError("changed original JAR")
        rows = []
        with tempfile.TemporaryDirectory(prefix="original-charset-") as work:
            subprocess.run([JDK / "bin/javac", "-g", "-parameters", "-encoding", "UTF-8", "-proc:none",
                            "-classpath", jar["file"], "-d", work, CASE / "UpgradeProbe.java"], check=True)
            for label, runtime in (("ordinary", []), ("controlled-process", ["--observed-runtime",
                    '{"emptyEnvironment":true,"processors":2,"rootWorkingDirectory":true}'])):
                cmd = [checker, "prove", "--classes", work, "UpgradeProbe#rewind()Z", "--classpath", jar["file"],
                       "--engine", "native", "--assert", "result == true", "--unwind", "16", "--json",
                       "--observed-initializer", owner, *runtime]
                proc = subprocess.run(cmd, env=os.environ | {"JAVA_HOME": str(JDK), "PATH": str(JDK / "bin") + ":" + os.environ["PATH"]},
                                      capture_output=True, text=True, timeout=115)
                if proc.stdout.strip() or proc.returncode == 0 or proc.stderr.strip() != reason:
                    raise ValueError("unexpected startup disposition: " + proc.stderr[-500:])
                rows.append({"process": label, "exit": proc.returncode, "stderr": reason, "stage": "before native execution",
                             "originalEntry": "UpgradeProbe#rewind()Z", "jar": jar["sha256"], "runtimeArguments": runtime})
        result[side] = rows
    dest = ROOT / OUTPUT / "io/observed-frontier.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + "\n")
    print("Both original charset initializers refused the default-charset dependency in both process profiles.")


if __name__ == "__main__":
    main()
