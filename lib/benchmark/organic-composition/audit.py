"""Requalify archived public observations, lemma use and incremental/clean agreement."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from plan_run import HERE, ROOT, OUTPUT


def recheck(case, label):
    public = ROOT/OUTPUT/case/label
    freeze = json.loads((HERE/"freeze.json").read_bytes())
    summary = json.loads((public/"summary.json").read_bytes())
    archive = public/"plans.zip"
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=summary["sha256"]:
        raise ValueError("plan archive checksum mismatch")
    reports = {}
    with zipfile.ZipFile(archive) as z:
        for name in summary["runs"]:
            if name=="planned":
                continue
            plan = json.loads(z.read(name+".json"))
            if (plan["tools"]!={"jvmRunner":freeze["runnerIdentity"],"comparator":freeze["checkerSha256"]}
                    or plan["executionState"]!="complete"):
                raise ValueError("implementation or execution state differs from freeze at "+name)
            rows = {}
            for node in plan["claims"]:
                ref = node.get("receipt")
                if not ref:
                    rows[node["id"]]={"status":node["status"],"blocker":node["firstOpenDependency"]}
                    continue
                raw = z.read(ref["path"])
                if hashlib.sha256(raw).hexdigest()!=ref["sha256"]:
                    raise ValueError("incorrect original receipt digest")
                record = json.loads(raw)
                sides = {}
                for side,binding in record["sides"].items():
                    proof = record.get("helperProofs",{}).get(side)
                    trials=[]
                    for t in binding.get("trials",[]):
                        apps=t.get("checkedApplications",[])
                        if node.get("derivation") and node["status"]=="established":
                            if (not proof or binding.get("requiredHelperProof")!=proof["key"] or len(apps)!=2
                                    or any(a["proofKey"]!=proof["key"] or not a["applications"]
                                           or not a["startupArguments"] for a in apps)):
                                raise ValueError("qualified original input has no consumed helper premise")
                        trials.append({"input":t["input"],"entries":t["qualifiedMethodEntries"],
                                       "calls":t.get("entryInvocations",[]),"values":t["observations"],
                                       "checkedApplications":apps})
                    sides[side]={"classpath":binding["classpath"],"callerClassSha256":binding["callerClassSha256"],
                                 "proofKey":proof["key"] if proof else None,"proofBasis":proof.get("basis") if proof else None,
                                 "trials":trials}
                rows[node["id"]]={"status":node["status"],"claim":node["claimKey"],"execution":node["executionKey"],
                                  "witness":node["witness"],"children":node["children"],"sides":sides}
            reports[name]=rows
    pairs=[("cold","warm"),("cold","clean"),("unrelated-warm","unrelated-clean"),
           ("wrong-warm","wrong-clean"),("resource-warm","resource-clean")]
    checked=[]
    for left,right in pairs:
        if left in reports and right in reports:
            if reports[left]!=reports[right]:
                raise ValueError(f"qualified inputs or accepted dependencies differ on {left}/{right}")
            checked.append([left,right])
    print(case,label,"matched original observations, proof identities, applied values and startup witnesses:",checked)

if __name__=="__main__":
    recheck(*sys.argv[1:])
