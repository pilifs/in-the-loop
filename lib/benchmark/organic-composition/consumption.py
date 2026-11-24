"""Withhold one accepted premise while preserving the entire original public observation."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import zipfile
from freeze import verify
from plan_run import HERE, ROOT, OUTPUT
sys.path.insert(0,str(ROOT/"examples/tools"))
from targets import change_evidence, change_plan

CASES={"threeten":"transfer-baseline","poi":"first","phone":"first","icu":"first","url-only":"first"}


def examine(case,label):
    _,workflows=change_plan.frozen_workflows(HERE/case/"checked-workflows.json")
    with zipfile.ZipFile(ROOT/OUTPUT/case/label/"plans.zip") as z:
        plan=json.loads(z.read("cold.json"));rows=[]
        for node in plan["claims"]:
            if not node.get("derivation") or node["status"]!="established":
                continue
            row,_,_,scope=workflows[node["id"]]
            raw=z.read(node["receipt"]["path"])
            if hashlib.sha256(raw).hexdigest()!=node["receipt"]["sha256"]:raise ValueError("unbound cold receipt")
            original=json.loads(raw)
            if change_evidence.compose(scope,original,row["intent"])["status"]!="established":
                raise ValueError("original checked evidence no longer qualifies")
            for side in ("old","new"):
                for field in ("startupArguments","applications","proofKey"):
                    altered=copy.deepcopy(original)
                    trial=altered["sides"][side]["trials"][0]
                    saved=copy.deepcopy(trial["observations"])
                    a=trial["checkedApplications"][0]
                    if field=="proofKey":a[field]="substituted"
                    else:a[field]=[]
                    invalid=change_evidence.compose(scope,altered,row["intent"])
                    if invalid["status"]!="open" or trial["observations"]!=saved:
                        raise ValueError("the unchanged public observation passed with a missing premise")
                    rows.append({"claim":node["id"],"side":side,"input":0,"withheldOrSubstituted":field,
                                 "result":invalid["status"],"publicValues":saved,"originalReceipt":node["receipt"]["sha256"]})
        return rows

if __name__=="__main__":
    verify()
    cases=sys.argv[1:] or list(CASES)
    out={case:examine(case,CASES[case]) for case in cases}
    target=ROOT/OUTPUT/"consumption.json"
    target.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n")
    print({k:len(rows) for k,rows in out.items()})
