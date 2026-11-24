"""Relate each actual original resource open to the regional data in the two built JARs."""
import hashlib
import json
from pathlib import Path
import zipfile

CASE=Path(__file__).resolve().parent
OUT=CASE.parents[3]/"verification/organic-composition/phone"
PREFIX="com/google/i18n/phonenumbers/data/"


def inspect(side):
    d=json.loads((CASE/side/"prepared.json").read_bytes());p=Path(d["classpath"][0]["file"])
    if hashlib.sha256(p.read_bytes()).hexdigest()!=d["classpath"][0]["sha256"]:raise ValueError("wrong production JAR")
    with zipfile.ZipFile(p) as z:
        return {name:hashlib.sha256(z.read(name)).hexdigest() for name in z.namelist()
                if not name.endswith("/") and (name.startswith(PREFIX) or name.endswith(".class"))}


def main():
    maps={s:inspect(s) for s in ("old","new")}
    changed=sorted(n for n in maps["old"].keys()|maps["new"].keys() if maps["old"].get(n)!=maps["new"].get(n))
    if changed!=["com/google/i18n/phonenumbers/AsYouTypeFormatter.class"]:
        raise ValueError("unexpected change among production classes or metadata")
    rows=[]
    with zipfile.ZipFile(OUT/"first/plans.zip") as z:
        plan=json.loads(z.read("cold.json"))
        for n in plan["claims"]:
            if not n.get("derivation"):continue
            data=z.read(n["receipt"]["path"])
            if hashlib.sha256(data).hexdigest()!=n["receipt"]["sha256"]: raise ValueError("unbound original receipt")
            record=json.loads(data)
            for side,b in record["sides"].items():
                for t in b.get("trials",[]):
                    region=n["domain"][t["input"]]["args"][0];file=PREFIX+"PhoneNumberMetadataProto_"+region
                    applications=t.get("checkedApplications",[])
                    for a in applications:
                        if a["resources"]!=[{"entry":file,"jar":b["classpath"][0],"sha256":maps[side][file]}]:
                            raise ValueError("wrong selected regional resource")
                    rows.append({"side":side,"region":region,"case":n["id"],"trialsWithSelectedResource":len(applications),
                                 "entry":file,"sha256":maps[side][file],
                                 "substitutions":sum(len(a["applications"]) for a in applications),"status":n["status"]})
    (OUT/"metadata.json").write_text(json.dumps({"changedClasses":changed,"identicalProductionDataFiles":sum(n.startswith(PREFIX) for n in maps["old"]),
                      "identicalRegionalMetadataFiles":sum(n.startswith(PREFIX+"PhoneNumberMetadataProto_") for n in maps["old"]),"rows":rows},indent=2)+"\n")

if __name__=="__main__":main()
