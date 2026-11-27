"""Replay the three disclosed M regressions and retain each original side's prediction scope."""
import json
from pathlib import Path
import sys
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/"examples/tools"))
from targets import public_comparison,upgrade_replay


def main():
    rows=[]
    with zipfile.ZipFile(HERE/"historical-adverse.zip","w",zipfile.ZIP_DEFLATED) as archive:
        for number,expected in ((446,["fix"]),(448,["fix"]),(451,["parent","fix"])):
            folder,=(ROOT/"examples").glob(str(number)+"-*")
            comparison=json.loads((folder/"comparison.json").read_bytes())
            challenge,=[q for q in comparison["questions"] if q["role"]=="Challenge"]
            data=public_comparison.replay(folder,authored=True)
            measured=[r for r in data["deployments"]["pins"]["observations"] if r["id"]==challenge["id"]]
            refuted=[r["side"] for r in measured if r["prediction"]=="refuted"]
            if set(challenge["expected"])!=set(expected) or refuted!=expected:
                raise ValueError("original adverse side scope or disposition changed")
            rows.append({"example":number,"id":challenge["id"],"entry":comparison["entry"],"requiredSides":expected,
                         "refuted":refuted,"outcomes":measured,"comparisonSha256":data["comparisonSha256"],
                         "originalReceiptSha256":upgrade_replay.sha(folder/"observations.json")})
            archive.writestr(str(number)+".json",json.dumps(data,indent=2)+"\n")
        archive.writestr("score.json",json.dumps({"scope":"authored historical comparison","questions":rows},indent=2)+"\n")
    print("All three fixed-side predictions refuted. The polygon prediction was also refuted on the parent.")


if __name__=="__main__":
    main()
