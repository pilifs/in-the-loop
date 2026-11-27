"""Check the public packet, caller, fresh JVM qualification, oracle rescore and side-specific cache."""
import argparse
import difflib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT/"examples/tools"))
from targets import blind_measure, blind_prediction, change_evidence, change_plan, observer_generation, upgrade_replay


def read(path):
    return json.loads(path.read_bytes())


def packet(root, jdk):
    root.mkdir(exist_ok=True,parents=True)
    doc = {"url":"https://github.com/example/public-value/pull/1","title":"Return the updated value from sample",
           "description":"The public sample method exposes the configured value.","schema":"blind-public-packet/v1",
           "arm":"cold","productionDiff":"production.diff","productionSources":[],"jdk":str(jdk),
           "jdkReleaseSha256":upgrade_replay.sha(jdk/"release")}
    sources = []
    for side, result in (("old",1),("new",2)):
        directory = root/side
        directory.mkdir()
        src = directory/"PublicValue.java"
        text = "package trial;\npublic class PublicValue {\n  public static int sample(int x) { return " + str(result) + "; }\n}\n"
        src.write_text(text)
        subprocess.run([jdk/"bin/javac","-proc:none","-d",directory,src],check=True)
        file = directory/"subject.jar"
        with zipfile.ZipFile(file,"w") as z:
            z.writestr("trial/PublicValue.class",(directory/"trial/PublicValue.class").read_bytes())
        sha = upgrade_replay.sha(src)
        doc[side] = {"revision":sha,"classpath":[{"file":file.relative_to(root).as_posix(),"sha256":upgrade_replay.sha(file)}]}
        doc[side+"Revision"] = sha
        doc["productionSources"].append({"side":side,"file":src.relative_to(root).as_posix(),"visibleSha256":sha})
        sources.append(text.splitlines(keepends=True))
    (root/"production.diff").write_text("".join(difflib.unified_diff(*sources)))
    change_evidence.write_json(root/"packet.json",doc)
    return doc


def verify(root, work):
    sealed = work/"sealed"
    blind_prediction.main([str(root),str(sealed)])
    pred = read(sealed/"prediction.json")
    primary = pred["candidates"][pred["primary"]]
    assert primary["entry"] == "trial.PublicValue#sample(I)I" and "expected" in primary["prediction"]
    assert pred["subjectLaunches"] == 0 and len(pred["inspectedEntries"]) <= pred["candidateBudget"]
    cold = work/"cold"
    result = blind_measure.measure(root,sealed,cold)
    attempt, = result["measurements"]
    if attempt["status"] != "established":
        raise ValueError(str(attempt))
    target = cold/"deployment-1/candidate-1"
    bundle = target/"bundle"
    workflow = target/"plan.json"
    raw = read(cold/attempt["evidence"]["receipt"]["path"])
    for side, val in (("old","1"),("new","2")):
        assert all(json.loads(v["return"]) == [["return","java.lang.Integer",val]] for v in attempt["observations"][side])
        assert all(t["qualifiedMethodEntries"] == 2 and t["publicProjections"][0] == t["publicProjections"][1]
                   for t in raw["sides"][side]["trials"])
    oracle = work/"oracle.json"
    answers = []
    for relation in ("different-on-any-input","equal-on-all-inputs"):
        change_evidence.write_json(oracle,{"public-observation":{"pairedObservation":relation}})
        answers.append(observer_generation.rescore(workflow,bundle,oracle)["claims"][0])
    assert [a["status"] for a in answers] == ["established","refuted"]
    assert answers[0]["observationsSha256"] == answers[1]["observationsSha256"]
    change_evidence.write_json(work/"rescore.json",answers)
    # Use the same frozen caller and oracle on a replacement at the existing artifact path.
    jdk = Path(read(root/"packet.json")["jdk"])
    after = read(bundle/"new.json")
    artifact = Path(after["classpath"][0]["file"])
    saved = artifact.read_bytes()
    command = ["application","--before",str(bundle/"old.json"),"--jdk",str(jdk),"--supplied-only",
               "--workflows",str(bundle/"workflows.json"),"--run","--seconds","90"]
    def replay(label, manifest, cache):
        dest = work/(label+".json")
        if change_plan.main([*command,"--after",str(manifest),"--cache",str(cache),"--output",str(dest)]):
            raise ValueError("control replay failed at " + label)
        doc, = read(dest)["claims"]
        return {"status":doc["status"], "sides":{side:r["action"] for side,r in doc["execution"].items()},
                "raw":[{s:c[s] for s in ("old","new")} for c in doc["children"]]}
    results = {}
    cache = target.parent/"cache"
    results["warm"] = replay("warm",bundle/"new.json",cache)
    results["clean"] = replay("clean",bundle/"new.json",work/"empty-cache")
    assert results["warm"]["raw"] == results["clean"]["raw"]
    assert set(results["warm"]["sides"].values()) == {"reused"}
    try:
        src = root/"new/PublicValue.java"
        modified = work/"mutation"
        modified.mkdir()
        changed = modified/src.name
        changed.write_text(src.read_text().replace("return 2","return 3"))
        subprocess.run([jdk/"bin/javac","-g","-proc:none","-d",modified,changed],check=True)
        with zipfile.ZipFile(artifact,"w") as z:
            z.write(modified/"trial/PublicValue.class","trial/PublicValue.class")
        try:
            blind_measure.verified_review(root,sealed,cold)
        except ValueError as error:
            assert "artifact changed" in str(error)
        else:
            raise ValueError("changed original bytes yielded a stale watcher review")
        after["classpath"][0]["sha256"] = upgrade_replay.sha(artifact)
        manifest = modified/"new.json"
        change_evidence.write_json(manifest,after)
        results["replaced"] = replay("replaced",manifest,cache)
        assert results["replaced"]["status"] == "refuted" and results["replaced"]["sides"]["old"] == "reused"
        assert results["replaced"]["sides"]["new"] != "reused"
    finally:
        artifact.write_bytes(saved)
    results["restored"] = replay("restored",bundle/"new.json",cache)
    assert results["restored"]["raw"] == results["warm"]["raw"] and results["restored"]["status"] == "established"
    blind_measure.verified_review(root,sealed,cold)
    change_evidence.write_json(work/"cache-controls.json",results)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--make-packet",type=Path)
    parser.add_argument("--work",type=Path)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--jdk",type=Path,default=Path.home()/".sdkman/candidates/java/17.0.21.0+9-tem")
    args = parser.parse_args()
    if args.make_packet:
        packet(args.make_packet,args.jdk)
    else:
        with tempfile.TemporaryDirectory(prefix="blind-public-product-") as scratch:
            work = args.work or Path(scratch)
            work.mkdir(exist_ok=True,parents=True)
            packet(work/"packet",args.jdk)
            verify(work/"packet",work)
            if args.output:
                with zipfile.ZipFile(args.output,"w",zipfile.ZIP_DEFLATED) as z:
                    for p in sorted(work.rglob("*")):
                        if p.is_file() and "cache" not in p.parts and "empty-cache" not in p.parts and "deployment-layouts" not in p.parts:
                            z.write(p,p.relative_to(work))
            print("Public entry predicted and bound, compiled on the old API, both original scalars qualified, opposite rescoring verified")
