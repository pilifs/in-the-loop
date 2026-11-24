"""Verify the setup builds and bind each ordered production graph to its tracked source tree."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

from plan_run import HERE, JDK

SETUP = Path.home()/".cache/in-the-loop/organic-composition-ff"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def prepare(case):
    folder = HERE/case
    pin = json.loads((folder/"upstream.json").read_bytes())
    built = {name: checksum for checksum, name in
             (line.split() for line in (SETUP/"logs/artifacts.sha256").read_text().splitlines())}
    for side in ("old","new"):
        subject = pin[side]
        tree = SETUP/"worktrees"/subject["worktree"]
        def git(*flags):
            return subprocess.check_output(["git","-C",tree,*flags])
        rev = git("rev-parse","HEAD").decode().strip()
        if rev != subject["commit"]:
            raise ValueError("upstream revision differs for "+side)
        git("diff","--quiet","HEAD","--",*pin["sourceRoots"])
        names = git("ls-tree","-r","-z","--name-only",rev,"--",*pin["sourceRoots"]).split(b"\0")
        sources = [(name.decode(),sha(tree/name.decode())) for name in names if name]
        if not sources:
            raise ValueError("no production source")
        files = [SETUP/"artifacts"/subject["jar"],*(SETUP/n for n in subject.get("dependencies",[]))]
        rows = [{"file":str(file),"sha256":sha(file)} for file in files]
        if rows[0]["sha256"] != built[subject["jar"]]:
            raise ValueError("production bytes differ from setup build")
        resources = {}
        with zipfile.ZipFile(files[0]) as jar:
            for name in pin.get("resources",[]):
                resources[name] = hashlib.sha256(jar.read(name)).hexdigest()
        doc = {"commit":rev,"tree":git("rev-parse","HEAD^{tree}").decode().strip(),
               "scope":pin["scope"], "sourceRoots":pin["sourceRoots"], "sourceFiles":len(sources),
               "sourceSha256":hashlib.sha256(json.dumps(sources,separators=(",",":")).encode()).hexdigest(),
               "jdkReleaseSha256":sha(JDK/"release"), "classpath":rows,"resources":resources}
        (folder/side).mkdir(exist_ok=True)
        (folder/side/"prepared.json").write_text(json.dumps(doc,indent=2)+"\n")

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case")
    prepare(parser.parse_args().case)
