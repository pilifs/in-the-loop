"""Remeasure the 32 registered V3 caller questions with their historical artifacts and assistance."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from history import HERE, ROOT, OUTPUT, digest, encoded, scratch

sys.path.insert(0,str(HERE.parent/"receiver-discovery"))
from callers import ASSETS, prepared_inputs

EXTERNAL=HERE.parent/"external-upgrades"
PRIOR=ROOT/"verification/external-upgrades/corpus-runs/v3-final-native"


def run(group,just_check):
    directory=PRIOR/group/"current"
    old={p.stem:json.loads(p.read_bytes()) for p in sorted(directory.glob("*.json"))}
    if not old:raise ValueError("missing registered V3 group")
    with scratch(prefix="historical-shadow-") as tmp:
        area=prepared_inputs(Path(tmp)/"data",old)
        if just_check:
            print(group,len(old),"registered caller pairs, artifact checks completed")
            return
        output=OUTPUT/"closing/shadow"/group
        checker=Path(os.environ["JVMCONTRACT"]).resolve()
        cmd=[sys.executable,"-B",str(EXTERNAL/"engineering.py"),"--build","current","--checker",str(checker),
             "--repositories",str(area/"sources/repos.json"),"--work",str(area/"slices"),"--complete",str(area/"modules"),
             "--maven-cache",str(ASSETS/"receivers/maven-repository"),"--maven8",
             str(Path.home()/".cache/in-the-loop/external-upgrades/ci-tools/apache-maven-3.6.3/bin/mvn"),
             "--output",str(output)]
        for cid in old:cmd+=["--case",cid]
        subprocess.run(cmd,cwd=ROOT,check=True)
        manifest=[]
        for cid,old_row in old.items():
            f=output/"current"/(cid+".json")
            row=json.loads(f.read_bytes())
            if any(row[k]!=old_row[k] for k in ("id","entry","observer","revisions","sourceSha256")) or row["checkerSha256"]!=digest(checker):
                raise ValueError("historical question or checker changed: "+cid)
            bindings={s:row["sides"].get(s,{}).get("orderedSha256")==old_row["sides"].get(s,{}).get("orderedSha256")
                      for s in ("old","new")}
            manifest.append({"id":cid,"v3Result":old_row["result"],"v3Sha256":digest(directory/f.name),
                             "currentSha256":digest(f),"sameOrderedArtifacts":bindings,
                             "result":row["result"],"firstBlocker":row.get("firstBlocker")})
        (output/"comparison.json").write_bytes(encoded({"argv":cmd,"cases":manifest,"job":os.environ.get("VERIFY_JOB_ID")}))
        print(group,len(manifest),"historical primary rows")


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("groups",nargs="*")
    ap.add_argument("--check",action="store_true")
    a=ap.parse_args()
    groups=sorted(p.name for p in PRIOR.iterdir() if p.is_dir())
    if len(list(PRIOR.glob("*/current/*.json")))!=32:raise ValueError("wrong V3 denominator")
    for group in a.groups or groups:
        if group not in groups:ap.error("unknown V3 group")
        run(group,a.check)
