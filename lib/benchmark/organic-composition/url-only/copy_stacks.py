"""Attribute the frozen minimum substitutions to the public JSONArray copy path on original JVMs."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

CASE=Path(__file__).resolve().parent
sys.path.insert(0,str(CASE.parent))
from freeze import verify
from plan_run import ROOT, OUTPUT, JDK
sys.path.insert(0,str(ROOT/"examples/tools"))
from targets import change_helpers, runtime_jar, upgrade_claims, upgrade_replay


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    verify()
    target=ROOT/OUTPUT/"url-only"
    config=json.loads((CASE/"helper.json").read_bytes())
    workflows=json.loads((CASE/"workflows.json").read_bytes())["workflows"]
    raw=upgrade_replay.TRACER.read_text()
    needle="            hit.thread().forceEarlyReturn(returned);"
    if raw.count(needle)!=1:raise ValueError("the frozen substitution point changed")
    logged=raw.replace(needle,'''            List<String> callPath = new ArrayList<>();
            callPath.add(key);
            boolean targetBacking = false;
            for (int i = 0; i + 1 < frames.size(); i++) {
                StackFrame ensure = frames.get(i), bulk = frames.get(i + 1);
                if (!entry(ensure.location()).equals("java.util.ArrayList#ensureCapacity(I)V")
                     || !entry(bulk.location()).startsWith("org.json.JSONArray#addAll(Ljava/util/Collection;")) continue;
                ObjectReference owner = bulk.thisObject();
                Field field = owner.referenceType().fieldByName("myArrayList");
                Value backing = owner.getValue(field);
                if (!(backing instanceof ObjectReference) || !ensure.thisObject().equals(backing)) continue;
                for (StackFrame original : frames) {
                    if (entry(original.location()).equals("org.json.JSONArray#putAll(Ljava/util/Collection;)Lorg/json/JSONArray;")
                            && owner.equals(original.thisObject())) targetBacking = true;
                }
            }
            callPath.add("targetBacking=" + targetBacking);
            for (StackFrame frame : frames) {
                callPath.add(entry(frame.location()) + "@" + frame.location().codeIndex());
            }
            System.err.println("INTAKE-COPY-PATH " + encoded(String.join("\\n", callPath)));
'''+needle)
    result={"frozenTracer":sha(raw.encode()),"supplementaryTracer":sha(logged.encode()),"trials":[]}
    with zipfile.ZipFile(target/"first/plans.zip") as z, tempfile.TemporaryDirectory(prefix="json-public-copy-") as tmp:
        work=Path(tmp);classes=work/"classes";classes.mkdir()
        tracer=work/"UpgradeTrace.java";tracer.write_text(logged)
        old=json.loads((CASE/"old/prepared.json").read_bytes())
        subprocess.run([JDK/"bin/javac","-g","-parameters","-proc:none","-encoding","UTF-8","-cp",old["classpath"][0]["file"],
              "-d",classes,tracer,upgrade_replay.LOOKUP,upgrade_replay.LAUNCHER,CASE/"UpgradeProbe.java"],check=True)
        program=upgrade_claims.disassemble(JDK,[classes],"UpgradeProbe",15)
        plan=json.loads(z.read("cold.json"));nodes={r["id"]:r for r in plan["claims"]}
        for workflow in workflows:
            scope=json.loads((CASE/workflow["scope"]).read_bytes());node=nodes[workflow["id"]]
            payload=z.read(node["receipt"]["path"])
            if sha(payload)!=node["receipt"]["sha256"]:raise ValueError("unbound original cold receipt")
            record=json.loads(payload)
            owner,method,desc=runtime_jar.parse_target(scope["entry"])
            sites=[str(pc) for m,pc,ref in upgrade_claims.invocation_sites(program,"UpgradeProbe")
                   if m[0]=="observe" and ref==(runtime_jar.internal(owner),method,desc)]
            accepted={} if workflow["intent"]=="preserve" else {r["input"]:r["expectedNew"] for r in workflow["intent"]["allowedChanges"]}
            for side in ("old","new"):
                bound=json.loads((CASE/side/"prepared.json").read_bytes());files=[Path(r["file"]) for r in bound["classpath"]]
                if any(upgrade_replay.sha(f)!=r["sha256"] for f,r in zip(files,bound["classpath"],strict=True)):
                    raise ValueError("changed original deployment")
                proof=record.get("helperProofs",{}).get(side)
                if not proof or proof["action"]=="refused":
                    result["trials"].append({"workflow":node["id"],"side":side,"status":"missing frozen proof"})
                    continue
                table=change_helpers.trace_config(work/(node["id"]+"-"+side),config,proof)
                cp=os.pathsep.join([str(classes),*map(str,files)])
                for i,case in enumerate(scope["cases"]):
                    run=work/(node["id"]+"-"+side+str(i));run.mkdir()
                    encoded=[base64.b64encode(a.encode("utf-16-be")).decode() for a in case["args"]]
                    cmd=[JDK/"bin/java","-Dupgrade.checked.table="+str(table),"-cp",classes,"UpgradeTrace",scope["entry"],
                         JDK,run,cp,",".join(sites),"UpgradeProbe","",*encoded]
                    child=subprocess.run(cmd,capture_output=True,text=True,check=True,timeout=60)
                    marks=child.stderr.splitlines();value=upgrade_replay.typed_outcome((run/"observation.txt").read_text().splitlines())
                    expected=accepted.get(i,case["expected"]) if side=="new" else case["expected"]
                    if value!=expected:raise ValueError("supplementary observation differs from preregistration")
                    origins=upgrade_replay.class_origins(child.stdout)
                    app=change_helpers.applications(marks,origins,config,proof,files,case["args"])
                    if origins.get("org.json.JSONArray")!={files[0]}:raise ValueError("unexpected public class provider")
                    stacks=[base64.b64decode(line.split(" ",1)[1]).decode().splitlines() for line in marks if line.startswith("INTAKE-COPY-PATH ")]
                    if len(stacks)!=len(app["applications"]):raise ValueError("substitution/stack count differs")
                    public=[s for s in stacks if s[1]=="targetBacking=true" and any(f.startswith(scope["entry"]+"@") for f in s[2:])
                            and any(f.startswith("java.util.ArrayList#grow(") for f in s[2:])]
                    result["trials"].append({"workflow":node["id"],"side":side,"input":case["args"],"observation":value,
                          "proofKey":proof["key"],"allSubstitutions":len(stacks),"bulkGrowthSubstitutions":len(public),
                          "distinctPublicStacks":sorted({tuple(s) for s in public}),"status":"qualified" if public else "no bulk-growth stack"})
    (target/"copy-stacks.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(sum(t["status"]=="qualified" for t in result["trials"]),"/",len(result["trials"]),"public growth paths")

if __name__=="__main__":main()
