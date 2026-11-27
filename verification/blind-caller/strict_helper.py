"""Qualify the six original Math.min applications and their finite public scopes independently."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"generated-observers"))
import campaign
import controls
from targets import change_helpers, upgrade_replay


def run(work):
    source = campaign.HERE/"receipts/io-helper.zip"
    with zipfile.ZipFile(source) as z:
        for name in z.namelist():
            if name.startswith("bundle/"):
                z.extract(name,work)
        historical = json.loads(z.read("helper-controls.json"))
    bundle = work/"bundle"
    jdk = campaign.prepare("io",work)
    table = campaign.read(bundle/"complete-table.json")
    env = {**os.environ,"JAVA_HOME":str(jdk),"PATH":str(jdk/"bin")+":/usr/bin:/bin"}
    rows = {}
    for variant, expected in historical["variants"].items():
        name = variant+"-workflows.json"
        actual = controls.app(work,bundle,jdk,bundle/name,work/(variant+".json"))
        rows[variant] = {}
        for claim in actual["claims"]:
            if claim["status"] != expected[claim["id"]]["status"]:
                raise ValueError(variant+" changed the historical finite outcome: "+str(claim.get("reason")))
            receipt = campaign.read(work/claim["receipt"]["path"])
            detail = {}
            for side, proof in receipt.get("helperProofs",{}).items():
                if variant == "complete":
                    if (proof["basis"] != "strict native lemma" or not change_helpers.accepted(proof["proof"],table)
                            or proof["runtimeBinding"]["resource"] != "jrt:/java.base/java/lang/Math.class"):
                        raise ValueError("a complete helper lost its actual bootstrap binding or native uses")
                    if {tuple(u["args"]) for u in proof["nativeSubstitutions"]} != {tuple(r["args"]) for r in table["rows"]}:
                        raise ValueError("the native query omitted a used helper row")
                trials = receipt.get("sides",{}).get(side,{}).get("trials",[])
                detail[side] = {"nativeUses":proof.get("nativeSubstitutions",[]),"binding":proof.get("runtimeBinding"),
                                "basis":proof.get("basis"),"publicSubstitutions":sum(len(t["checkedApplications"][0]["applications"])
                                  for t in trials if t.get("checkedApplications"))}
            rows[variant][claim["id"]] = {"status":claim["status"],"sides":detail,"reason":claim.get("reason")}
    for name, expected in (("rewinds",(14,20)),("preservation",(10,10))):
        measured = rows["complete"][name]["sides"]
        if tuple(measured[s]["publicSubstitutions"] for s in ("old","new")) != expected:
            raise ValueError("original public use count changed: "+name)
    # A proved lemma may be supplied to a caller that never uses it. Keep that negative independent of the JDI one.
    unused = work/"unused"
    unused.mkdir()
    c = unused/"CheckedHelperUse.java"
    c.write_text("public class CheckedHelperUse { public static boolean check(int choice) { return choice >= 0; } }")
    data,_=change_helpers.original_class("java.lang.Math",[],jdk)
    contract,_,_=change_helpers.declaration(table,data)
    (unused/"helper.contract").write_text(contract)
    classes = unused/"classes"
    classes.mkdir()
    subprocess.run([jdk/"bin/javac","-g","-parameters","-d",classes,c,change_helpers.RUNTIME_READER],check=True)
    boot = unused/"boot"
    subprocess.run([jdk/"bin/java","-cp",classes,"RuntimeHelperBytes","java.lang.Math",boot],check=True,capture_output=True)
    checker = Path(os.environ.get("JVMCONTRACT",campaign.ROOT/"lib/target/release/jvmcontract"))
    proof = json.loads(subprocess.check_output([checker,"prove","--classes",classes,"--classpath",boot,"CheckedHelperUse#check",
                     "--assume","choice >= 0 && choice < 6","--assert","result == true","--engine","native","--gaps","strict",
                     "--lemmas",unused/"helper.contract","--json"],env=env))
    if proof[0]["verdict"] != "verified" or change_helpers.accepted(proof,table):
        raise ValueError("an unused lemma obtained consumption credit")
    campaign.write(work/"qualification.json",{"original":upgrade_replay.sha(source),"variants":rows,
                   "unusedNative":{"verdict":proof[0]["verdict"],"uses":change_helpers.summary_uses(proof,table["entry"])}})
    campaign.pack(work,[*work.glob("*.json"),*work.glob("receipts/*.json"),unused/"helper.contract",c],HERE/"strict-helper.zip")
    print("Six strict native substitutions with sites and tuples, both original public questions and all rejection controls")


if __name__=="__main__":
    with tempfile.TemporaryDirectory(prefix="strict-boot-helper-") as scratch:
        run(Path(scratch))
