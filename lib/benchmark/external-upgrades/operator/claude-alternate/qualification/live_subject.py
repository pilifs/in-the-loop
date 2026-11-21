"""Observe the same public synthetic compiled client on both revisions. Write a private case result."""

import hashlib
import json
from pathlib import Path
import subprocess

work = Path("/case/work")
packet = Path("/case/packet")
java = work / "Check.java"
java.write_text(
    "public final class Check {public static void main(String[] args) { System.out.print(neutral.Counter.increment(41)); }}"
)
values = {}
for side in ("old", "new"):
    target = work / (side + "-classes")
    target.mkdir()
    subprocess.run(
        [
            "javac",
            "-d",
            str(target),
            str(java),
            str(packet / side / "src/main/java/neutral/Counter.java"),
        ],
        check=True,
    )
    values[side] = int(subprocess.check_output(["java", "-cp", str(target), "Check"], text=True))
with Path("/usr/bin/jvmcontract").open("rb") as f:
    sha = hashlib.file_digest(f, "sha256").hexdigest()
result = {
    "nonce": (work / "challenge").read_text().strip(),
    "case_id": json.loads((packet / "pair.json").read_bytes())["case_id"],
    "old": values["old"],
    "new": values["new"],
    "checker": sha,
}
(work / "model-tool-result.json").write_text(json.dumps(result) + "\n")
print(json.dumps(result))
