"""Use the same isolated operator on the disclosed broken/fixed corpus before the blind draw is opened."""
import argparse
import json
from pathlib import Path
import os
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from history import ROOT, OUTPUT, scratch, encoded
from run_operator import JDK, launch, sha


def input_pair(work):
    pair=work/"pair";pair.mkdir()
    manifest={}
    for side,version in (("old","broken"),("new","fixed")):
        original=ROOT/"lib/benchmark/src"/version
        classes=work/version;classes.mkdir()
        files=sorted(original.rglob("*.java"))
        subprocess.run([JDK/"bin/javac","-proc:none","-parameters","-g","-d",classes,*files],check=True)
        folder=pair/side;folder.mkdir()
        jar=folder/"000.jar"
        with zipfile.ZipFile(jar,"w",zipfile.ZIP_DEFLATED) as archive:
            for f in sorted(classes.rglob("*.class")):archive.write(f,f.relative_to(classes))
        manifest[side]=[{"path":side+"/000.jar","sha256":sha(jar)}]
    (pair/"inputs.json").write_bytes(encoded(manifest))
    return pair


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--discover-only",action="store_true");p.add_argument("--output",type=Path,default=OUTPUT/"calibration/artifact-only.json")
    a=p.parse_args()
    with scratch(prefix="operator-calibration-") as tmp:
        work=Path(tmp);pair=input_pair(work);checker=Path(os.environ.get("JVMCONTRACT",ROOT/"lib/target/release/jvmcontract"))
        try:report=launch(pair,work/"isolated",checker,discover=a.discover_only)
        except (OSError,ValueError):
            log=work/"isolated/operator.log"
            if log.exists():print(log.read_text(errors="replace")[-2000:],file=sys.stderr)
            raise
        if len(report["selected"])!=4 or not all(c["impact"]=="invalidated" for c in report["selected"]):
            raise ValueError("calibration did not discover four changed public declarations")
        if not a.discover_only and not any(r.get("verdict")=="violation" and r.get("originalReplayChanged") for r in report["runs"]):
            raise ValueError("calibration missed every known public divergence")
        print("selected",len(report["selected"]),"of",report["commonCandidates"],"public candidates")
        if not a.discover_only:
            for i,r in enumerate(report["runs"]):
                r["coldCost"]=json.loads((work/f"isolated/output/first/case{i}/native.json.cost.json").read_bytes())
                r["warmCost"]=json.loads((work/f"isolated/output/first/case{i}/warm.json.cost.json").read_bytes())
            a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(encoded(report))
