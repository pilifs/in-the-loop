"""Keep the frozen parser loops and qualify the effect of changing only their input setup."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from companions import HERE, ROOT, SHA, materialize, proof, runtime_jdk
from public_run import measure, read, write


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("the frozen input setup changed")
    return source.replace(old, new)


def experiment(number, side, cap, out, physical_only):
    folder, = (ROOT / "examples").glob(number + "-*")
    jackson = number == "365"
    original = "AsyncTokens" if jackson else "DelimitedFields"
    companion = "DirectTokens" if jackson else "CappedFields"
    out.mkdir(parents=True, exist_ok=True)
    source = (folder / "adapter/campaign" / (original+".java")).read_text()
    driver = (folder / "driver/campaign/Cases.java").read_text().replace(original, companion)
    source = replace_once(source, "class "+original, "class "+companion)
    if jackson:
        source = replace_once(source, "new JsonFactory().createNonBlockingByteArrayParser()", "DirectParser.create()")
    else:
        source = replace_once(source, "new StringReader(source)", f"new CappedReader(source, {cap})")
        driver = replace_once(driver, "new StringReader(text)", f"new CappedReader(text, {cap})")
    # Keep the exact compiled companion inputs alongside each measurement.
    (out/(companion+".java")).write_text(source)
    (out/"Cases.java").write_text(driver)
    jdk = Path(runtime_jdk.home("21"))
    env = dict(os.environ, JAVA_HOME=str(jdk), JVMCONTRACT_JAR_RELEASE="21",
               PATH=str(jdk/"bin")+os.pathsep+os.defpath)
    with tempfile.TemporaryDirectory(prefix="parser-windows-") as tmp:
        work = Path(tmp)
        jars, binding = materialize(folder, side, work)
        classes = work / "classes"; classes.mkdir()
        cp = os.pathsep.join(map(str,[classes,*jars]))
        support = HERE / ("DirectParser.java" if jackson else "CappedReader.java")
        subprocess.run([jdk/"bin/javac","-g","-parameters","-cp",cp,"-d",classes, out/(companion+".java"),
                        out/"Cases.java",support,ROOT/"examples/tools/targets/java/org/intheloop/controls/Grid.java"],
                       cwd=work, env=env, check=True)
        physical = measure([jdk/"bin/java","-cp",cp,"campaign.Cases",side],out/"controls.stdout",
                           stderr=out/"controls.stderr",cwd=work,env=env)
        if physical["exit"]:
            raise ValueError(f"{number}/{side}: the physical companion failed, see {out}")
        rows = [json.loads(s) for s in (out/"controls.stdout").read_text().splitlines()]
        table = read(folder/"controls/table.json")["cases"]
        receipt, = folder.glob(f"records/opening-*/replay/*/records/control-{side}-jdk21.stdout")
        reference = [json.loads(s) for s in receipt.read_text().splitlines()]
        if len(rows) != len(table) or len(rows) != len(reference):
            raise ValueError("incomplete correspondence")
        fields = list(table[0]["expected"])
        differences = {f:[] for f in fields}
        changed = {f:[] for f in fields}
        for r, t, ordinary in zip(rows,table,reference,strict=True):
            if r["id"] != t["id"] or r["input"] != t["input"] or ordinary["id"] != t["id"]:
                raise ValueError("companion changed the physical input")
            for f in fields:
                holds = r["direct"][f] == t["expected"][f]
                if r["adapter"][f] != int(holds):
                    raise ValueError("direct JVM observation differs from the adapted result")
                if not holds:
                    differences[f].append(r["id"])
                if r["direct"][f] != ordinary["direct"][f]:
                    changed[f].append(r["id"])
        if jackson and any(changed.values()):
            raise ValueError("the separately constructed parser changed the observed trace")
        result = {"example":number,"side":side,"cap":cap,"binding":binding,"rows":len(table),
                  "ordinaryReceipt":str(receipt.relative_to(ROOT)),"ordinarySha256":SHA(receipt),
                  "differencesFromOracle":differences,"differencesFromOriginalCaller":changed,
                  "compiledSource":SHA(out/(companion+".java")),"support":SHA(support),"proofs":{}}
        write(out/"experiment.json",result)
        if physical_only:
            return
        checker = Path(os.environ["JVMCONTRACT"]).resolve()
        result.update(checker=SHA(checker),source=os.environ["VERIFY_SOURCE_COMMIT"])
        queries = [(f"campaign.{companion}#{f}", f, read(folder/"claims"/(f+".json"))["assume"],
                    read(folder/"claims"/(f+".json"))["bounds"]) for f in fields]
        if jackson:
            queries.append(("campaign.DirectParser#oneRefill", "one-refill", "padding >= 0 && padding < 4", queries[0][3]))
        elif cap == 1:
            queries.append(("campaign.CappedReader#contract","short-read-contract","cap >= 1 && cap <= 3",
                            {"unwind":16,"maxArrayLength":16}))
        for entry,label,guard,bounds in queries:
            result["proofs"][label] = proof(checker,classes,jars,work,env,out,entry,label,guard,
                                            bounds=(bounds["unwind"],bounds["maxArrayLength"]))
            write(out/"experiment.json",result)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("number",choices=("365","366"))
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--physical-only",action="store_true")
    args=p.parse_args()
    for side in ("parent","fix"):
        for cap in ([None] if args.number=="365" else [1,2,3]):
            out=args.output.resolve()/side
            experiment(args.number,side,cap,out if cap is None else out/str(cap),args.physical_only)
