"""Check source-identity intake on the disclosed H2 packet, varying only its repository locator."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from pinned_task import HERE, ROOT, check_files

sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import route, sidecar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", type=Path, required=True, help="local clone with both disclosed rxjava-jdbc tags")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = ROOT / "examples/348-rxjava-jdbc-generated-keys"
    example = json.loads((source / "example.json").read_text())
    original = json.loads((source / "target.json").read_text())
    frozen = json.loads((HERE / "v0.json").read_text())
    evidence = {"schema": "external-upgrade-source-intake/v1", "case": "open-rxjava", "product": frozen["revision"],
                "protectedFiles": check_files(frozen), "sources": {}, "variants": {},
                "scope": "Disclosed source locator diagnostic. Both variants retain the same original POM, caller, "
                         "artifact pins, claim and revisions. No scored pair or source-bridge result is inferred."}
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        packet = work / source.name
        packet.mkdir()
        for directory in ("claims", "adapter", "driver", "controls"):
            shutil.copytree(source / directory, packet / directory)
        neutral = work / "neutral-pair"
        for side in ("old", "new"):
            revision = original["history"]["revisions"][side]["commit"]
            inputs = {}
            for name in ("pom.xml", example["subject"]["file"]):
                data = subprocess.check_output(["git", "-C", str(args.subject), "show", f"{revision}:{name}"])
                file = neutral / side / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(data)
                inputs[name] = hashlib.sha256(data).hexdigest()
            evidence["sources"][side] = {"revision": revision, "sha256": inputs}
        for label, location in (("github", original["history"]["repository"]), ("neutralLocal", neutral.as_uri())):
            metadata = {**original, "history": {**original["history"], "repository": location}}
            (packet / "target.json").write_text(json.dumps(metadata))
            try:
                target = sidecar.load(packet, example)
                plan = route.resolve(packet, example, target, "generated-keys")
                evidence["variants"][label] = {"accepted": True, "claimKey": plan.claim["key"]}
            except sidecar.SidecarError as exc:
                evidence["variants"][label] = {"accepted": False, "firstBlocker": str(exc).replace(temp, "$CASE")}
    with args.out.open("x") as dest:
        json.dump(evidence, dest, indent=2)
        dest.write("\n")
    print(evidence["variants"])


if __name__ == "__main__":
    main()
