"""Unmask and replay the historical Parquet observations after the original public nominations were sealed."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/"examples/tools"))
from targets import upgrade_replay


def main():
    first=json.loads((HERE/"first-nominations.json").read_bytes())
    historical=ROOT/"verification/classpath-entry-discovery/parquet-observations.json"
    with tempfile.TemporaryDirectory(prefix="reveal-public-histories-") as temp:
        out=Path(temp)/"physical.json"
        subprocess.run([sys.executable,ROOT/"lib/benchmark/classpath-entry-discovery/parquet_score.py",out],check=True)
        actual=json.loads(out.read_bytes())
        if actual != json.loads(historical.read_bytes()):
            raise ValueError("the original or reversed deployment observations changed")
    original=[r for r in actual if r["profile"]=="original"]
    if len(original)!=10 or len(actual)!=20:
        raise ValueError("the historical profile or direction is missing")
    entries=sorted({r["entry"] for r in original})
    ranks={r["entry"]:r for r in first["candidates"]}
    scores=[{"entry":entry,"staticRank":next(r["firstUnaidedRank"] for r in original if r["entry"]==entry),
             "firstOriginalTestRank":ranks.get(entry,{}).get("rank"),
             "sides":ranks.get(entry,{}).get("sides",[]),"publicObservations":[r for r in original if r["entry"]==entry]}
            for entry in entries]
    with zipfile.ZipFile(HERE/"parquet-physical.zip","w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("original-and-reversed.json",json.dumps(actual,indent=2)+"\n")
        z.writestr("first-score.json",json.dumps({"firstNominationsSha256":upgrade_replay.sha(HERE/"first-nominations.json"),
                     "historicalSha256":upgrade_replay.sha(historical),"scores":scores},indent=2)+"\n")
    print("ten original and ten reversed outcomes reproduced; scored two independently nominated public operations")


if __name__=="__main__":
    main()
