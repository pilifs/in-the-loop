"""Exercise planted false greens independently of the source and class digests that also reject edits."""
import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

import campaign
from controls import app
from targets import change_inventory, observer_generation, runtime_jar, upgrade_claims, upgrade_replay
import scaffold_example

read, write = campaign.read, campaign.write


def dynamic(bundle, jdk, directory, source, question, index, side):
    """Compile the planted candidate and run the same independent public projection check on its actual output."""
    record = read(bundle / "generation.json")
    recipe = record["recipe"]
    reg = read(bundle / "registration.json")
    manifest = read(bundle / (side + ".json"))
    files = [Path(row["file"]) for row in manifest["classpath"]]
    directory.mkdir()
    candidate = directory / "UpgradeProbe.java"
    candidate.write_text(source)
    old = [r["file"] for r in read(bundle / "old.json")["classpath"]]
    subprocess.run([jdk / "bin/javac", "-g", "-proc:none", "-cp", os.pathsep.join(old),
                    "-d", directory, upgrade_replay.LAUNCHER, upgrade_replay.TRACER, candidate], check=True,
                   capture_output=True, timeout=35)
    selector = recipe.get("invocationVia",reg["entry"])
    owner, method, desc = runtime_jar.parse_target(selector)
    sites = [pc for member,pc,ref in upgrade_claims.invocation_sites(
             upgrade_claims.disassemble(jdk, [directory], "UpgradeProbe", 15), "UpgradeProbe")
             if member == ("observe","([Ljava/lang/String;)Ljava/lang/String;") and ref == (runtime_jar.internal(owner),method,desc)]
    if not sites:
        raise ValueError("planted caller has no static public call")
    inputs = question["inputs"][index]
    encoded = [base64.b64encode(s.encode("utf-16-be")).decode() for s in observer_generation.arguments(inputs)]
    flags = ["-Dupgrade.observe.history=true"]
    if recipe["family"] == "typed numeric conversions":
        flags.append("-Dupgrade.observe.numeric=true")
    if "publicReader" in recipe:
        flags.append("-Dupgrade.observe.reader="+recipe["publicReader"])
    command = [str(jdk/"bin/java"), *flags, "-cp", str(directory), "UpgradeTrace", reg["entry"], str(jdk)]
    _, marks, obs = upgrade_replay.run_observation(directory/"trial", command,
        os.pathsep.join(map(str,[directory,*files])), ",".join(map(str,sites)), "UpgradeProbe", encoded, "",
        {"PATH": str(jdk/"bin")+":/usr/bin:/bin","HOME":str(directory),"TMPDIR":str(directory),"LANG":"C.UTF-8","TZ":"UTC"},
        [], time.monotonic()+35, ".")
    value = upgrade_replay.typed_outcome(obs.splitlines())
    result = {"sourceSha256":upgrade_replay.sha(candidate),"staticSites":sites,"raw":value,
              "marks":[m for m in marks if m.startswith(("UPGRADE-NUMBER ", "UPGRADE-PUBLIC-"))]}
    try:
        result["projection"] = observer_generation.correspondence(recipe, inputs, marks, value)
    except ValueError as e:
        result["refusal"] = str(e)
    return result


def altered_subject(work, jdk, bundle):
    manifest = read(bundle/"new.json")
    original = Path(manifest["classpath"][0]["file"])
    root = campaign.CACHE/"spring-pr-links-o01-o20/worktrees/O01-fix"
    if subprocess.check_output(["git","-C",root,"rev-parse","HEAD"], text=True).strip() != manifest["commit"]:
        raise ValueError("mutant base is not the registered fix")
    relative = "spring-core/src/main/java/org/springframework/util/NumberUtils.java"
    base = subprocess.check_output(["git","-C",root,"show",manifest["commit"]+":"+relative],text=True)
    sig = "public static <T extends Number> T parseNumber(String text, Class<T> targetClass) {"
    if base.count(sig) != 1:
        raise ValueError("changed mutation site")
    folder = work/"mutation"
    folder.mkdir()
    source = folder/"NumberUtils.java"
    source.write_text(base.replace(sig,sig+'\n        if ("+0x7f".equals(text)) text = "+0x7e";'))
    subprocess.run([jdk/"bin/javac","-g","-proc:none","-cp",os.pathsep.join(r["file"] for r in manifest["classpath"]),
                    "-d",folder,source],check=True,capture_output=True)
    member = "org/springframework/util/NumberUtils.class"
    output = folder/original.name
    with zipfile.ZipFile(original) as old, zipfile.ZipFile(output,"w") as new:
        for item in old.infolist():
            new.writestr(item, (folder/member).read_bytes() if item.filename==member else old.read(item))
    manifest["classpath"][0].update(file=str(output),sha256=upgrade_replay.sha(output))
    manifest.update(scope="diagnostic controlled mutation of the fixed public subject",commit=None)
    write(folder/"manifest.json",manifest)
    return folder/"manifest.json"


def numbered(study, number, work, jdk, bundle):
    """Invoke the numbered Stage 3 writer, as used by scaffold-only, against a fresh example folder."""
    root = work/"numbered"
    source = next((campaign.ROOT/"examples").glob(number+"-*"))
    example = root/"examples"/source.name
    example.mkdir(parents=True)
    shutil.copyfile(source/"example.json",example/"example.json")
    plan = work/"reviewed-plan.json"
    write(plan,{"schema":"prove-plan/v1","examples":[{"id":number,"review":"designed","tasks":[],"claimFiles":{},
        "preparedDeployments":{"before":str(work/"old.json"),"after":str(work/"new.json"),"jdk":str(jdk),
             "registration":str(campaign.HERE/"registrations"/(number+".json")),
             "predictions":str(campaign.HERE/"predictions"/(number+".json"))}}]})
    result = scaffold_example.scaffold(number,plan,True,root=root)
    if result["refused"] or result["leftForSetup"]:
        raise ValueError(str(result))
    built = example/"records/public-observer"
    identical = all(upgrade_replay.sha(built/name)==upgrade_replay.sha(bundle/name) for name in ("UpgradeProbe.java","caller.zip","registration.json","workflows.json"))
    if not identical:
        raise ValueError("numbered and isolated Stage 3 generated different callers")
    plan_report = example/"records/entry-bindings.json"
    campaign.run([sys.executable,campaign.ROOT/"examples/tools/build.py","--change-plan","application","--supplied-only",
                  "--before",built/"old.json","--after",built/"new.json","--jdk",jdk,"--workflows",built/"workflows.json",
                  "--previous",plan_report,"--run","--seconds","120","--cache",work/"cache","--output",work/"numbered-resume.json"])
    study["numberedStage3"] = {"generation":upgrade_replay.sha(built/"generation.json"),"sameCompiledBytes":identical,
        "planned":read(plan_report)["executionState"],"resumed":read(work/"numbered-resume.json")["executionState"],
        "claims":[n["status"] for n in read(work/"numbered-resume.json")["claims"]]}
    if set(study["numberedStage3"]["claims"]) != {"established"}:
        raise ValueError("numbered resume did not qualify the frozen questions")


def controls(number, work):
    campaign.exercise(number,work)
    bundle=work/"bundle"
    reg=read(bundle/"registration.json")
    source=(bundle/"UpgradeProbe.java").read_text()
    jdk=campaign.prepare(number,work)
    out={"case":number,"compiled":read(bundle/"generation.json")["compiled"]}
    if number in ("445","458"):
        numbered(out,number,work,jdk,bundle)
    q=reg["questions"][0]
    if number=="458":
        correct=campaign.HERE/"predictions/458.json"
        expected=read(correct)
        for value in expected[q["id"]]["new"][0]:
            value[2]="126"
        wrong=work/"wrong.json"
        write(wrong,expected)
        evaluations=[observer_generation.rescore(work/"cold.json",bundle,p) for p in (correct,wrong)]
        a,b=[r["claims"][0] for r in evaluations]
        out["oracleOnly"]={"before":a["status"],"after":b["status"],"raw":a["observationsSha256"],
               "sameRaw":a["observationsSha256"]==b["observationsSha256"],"witness":b["witness"]}
        if (a["status"],b["status"],out["oracleOnly"]["sameRaw"]) != ("established","refuted",True):
            raise ValueError("wrong fixed expectation survived")
        altered=altered_subject(work,jdk,bundle)
        changed=app(work,bundle,jdk,bundle/"workflows.json",work/"mutated.json",after=altered)
        c=changed["claims"][0]
        out["subjectMutation"]={"status":c["status"],"actual":c["children"][0]["new"],"compiled":c["observerProvenance"]["classes"],
                                "subject":read(altered)["classpath"][0]["sha256"]}
        if c["status"]!="refuted" or json.loads(c["children"][0]["new"]["return"]) != expected[q["id"]]["new"][0] or out["compiled"]!=c["observerProvenance"]["classes"]:
            raise ValueError("frozen caller failed to follow the subject")
        canned=source.replace("        StringBuilder result", '        observations.clear(); observations.add(row("return","java.lang.Integer","127")); observations.add(row("return","java.math.BigInteger","127"));\n        StringBuilder result')
        early=source.replace("Number value = ", 'if (data.containsKey("conversions")) throw new NumberFormatException();\n                Number value = ')
        out["genuine"]=dynamic(bundle,jdk,work/"genuine",source,q,0,"old")
        if "projection" not in out["genuine"]: raise ValueError("original numeric measurement lost correspondence")
        out["canned"]=dynamic(bundle,jdk,work/"canned",canned,q,0,"old")
        out["beforeEntry"]=dynamic(bundle,jdk,work/"early",early,q,0,"old")
        if out["beforeEntry"]["raw"] != out["genuine"]["raw"] or not all("refusal" in out[k] for k in ("canned","beforeEntry")):
            raise ValueError("planted projection obtained a verdict")
    elif number=="J16":
        owner=reg["entry"].split("#")[0]
        bad=source.replace("view.getEdgeWeight(edge)", "new "+owner+"<>(backing, e -> ((Number)data.get(\"viewWeight\")).doubleValue(), true, false).getEdgeWeight(edge)")
        # The unchanged values on this profile make the wrong receiver invisible to an output-only test.
        out["genuine"]=dynamic(bundle,jdk,work/"genuine",source,q,0,"new")
        if "projection" not in out["genuine"]: raise ValueError("original retained receiver lost correspondence")
        out["freshReceiver"]=dynamic(bundle,jdk,work/"wrong-receiver",bad,q,0,"new")
        if "refusal" not in out["freshReceiver"] or out["freshReceiver"]["raw"] != out["genuine"]["raw"]: raise ValueError("wrong receiver survived qualification")
    write(work/"qualification-controls.json",out)
    campaign.pack(work,[*work.glob("*.json"),*(work/"receipts").glob("*.json"),*(work/"bundle").glob("*")],
                  campaign.HERE/"receipts"/(number+"-controls.zip"))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number",choices=["458","445","J16"])
    a=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="generated-controls-") as tmp:
        controls(a.number,Path(tmp)/a.number)
