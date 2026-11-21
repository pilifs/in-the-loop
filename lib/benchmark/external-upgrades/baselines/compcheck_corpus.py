"""Run the stock CompCheck CLI on the original engineering cases with published call-site inputs."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

import compcheck_aws
import maven_mirror
import public_ci


CORPUS = Path(__file__).resolve().parents[1] / "corpus.json"
SITES = {"compsuite-i-38": ("c4-4", "c4-5", "c4-6"), "compsuite-i-4": ("c6-2", "c6-3"),
         "compsuite-i-29": ("c3-1",), "compsuite-i-36": ("c4-1", "c4-2", "c4-3")}


def treatment(root, args, case, site, remove, sockets):
    compcheck_aws.extract_checked(args.archive, compcheck_aws.TOOL_ARCHIVE, root)
    tool = next(root.glob("CompCheck-*"))
    rows = json.loads((tool/"check/callsites.json").read_text())
    point = next(r for r in rows if r["id"] == site)
    subject = case["revisions"]["old"]
    client, api, caller = point["client"], point["API"], point["caller"]
    if (point["sha"],point["lib"],point["version"]) != (subject,case["dependency"],case["versions"]["old"]):
        raise ValueError("wrong upstream call site or dependency")
    knowledge = tool/"knowledge/knowledge.json"
    compcheck_aws.verify(knowledge,compcheck_aws.FULL_KNOWLEDGE)
    entries=json.loads(knowledge.read_text())
    incident = [r for r in entries if r["client"]==client and r["lib"]==case["dependency"]
                and r["new_version"]==case["versions"]["new"] and case["versions"]["old"] in r["versions"]
                and r["test"]==case["namedTest"]]
    if remove:
        entries=[r for r in entries if r not in incident]
        knowledge.write_text(json.dumps(entries,indent=2)+"\n")
    source=tool/"check/_downloads"/client
    source.parent.mkdir(exist_ok=True)
    subprocess.run(["git","-c","core.hooksPath=/dev/null","clone","-q","--no-checkout","--no-hardlinks",
                    str(args.repository),str(source)],check=True)
    subprocess.run(["git","-C",str(source),"-c","core.hooksPath=/dev/null","checkout","-q","--detach",subject],check=True)
    owner = caller.split("(")[0].rsplit(".",1)[0].split("$")[0].split(".")[-1]
    candidates = sorted(source.rglob(owner+".java"))
    line = None
    for path in candidates:
        text = path.read_text(errors="replace").splitlines()
        position = int(point["line"])-1
        if 0 <= position < len(text) and "/test/" not in path.as_posix():
            line = text[position].strip()
            break
    if line is None:
        raise ValueError("the stock caller source line is unavailable")
    work, scratch = root/"work", root/"scratch"
    (work/"home").mkdir(parents=True); (scratch/"jvm").mkdir(parents=True)
    context=tool/"check/context"/site/"context.json"
    if (source/"target/classes").exists() or context.exists():
        raise ValueError("stock treatment already contains build products or a context")
    start=time.monotonic()
    with (work/"tool.log").open("wb") as log:
        cmd=public_ci.namespace(tool,work,scratch,sockets,args.maven,args.jdk)
        try:status=subprocess.run([*cmd,"--stock-compcheck",site],stdout=log,stderr=subprocess.STDOUT,timeout=args.seconds).returncode
        except subprocess.TimeoutExpired:status=124
    output=(work/"tool.log").read_text(errors="replace")
    matched=tool/"check/matching/relax_prim_poly-0.7.json"
    tests={}
    for side in ("old","new"):
        file=tool/"check/_test_logs"/site/(side+".log")
        if file.is_file():
            counts=re.findall(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+)",file.read_text(errors="replace"))
            tests[side]={"logSha256":compcheck_aws.sha(file),"testAndFailureCounts":counts}
    return {"site":site,"caller":caller,"api":api,"line":point["line"],"sourceLine":line,"revision":subject,
            "treatment":"leave original incident out" if remove else "stock full knowledge",
            "knowledgeRows":len(entries),"originalIncidentRows":[r["id"] for r in incident],"applicableApiRows":sum(r["API"]==api for r in entries),
            "exit":status,"seconds":round(time.monotonic()-start,3),"compiledClientClasses":len(list((source/"target/classes").rglob("*.class"))),
            "contextSha256":compcheck_aws.sha(context) if context.exists() else None,
            "matched":json.loads(matched.read_text()).get(site) if matched.exists() else None,"generatedTests":tests,
            "stages":[v for v in ("Call site found","Call site not found","Processing CFG file","API CALL SITE MATCH!",
                                  "API CALL SITE NOT MATCH","TypeError","BUILD FAILURE") if v in output],
            "logSha256":compcheck_aws.sha(work/"tool.log")}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case",choices=sorted(SITES),required=True)
    for key in ("archive","repositories","maven-cache","output"):ap.add_argument("--"+key,type=Path,required=True)
    ap.add_argument("--maven",type=Path,default=Path.home()/".cache/in-the-loop/external-upgrades/ci-tools/apache-maven-3.6.3")
    ap.add_argument("--jdk",type=Path,default=Path.home()/".sdkman/candidates/java/8.0.512.0+9-tem")
    ap.add_argument("--seconds",type=int,default=360)
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    case=next(c for c in json.loads(CORPUS.read_text())["cases"] if c["id"]==args.case)
    args.repository=Path(json.loads(args.repositories.read_text())[args.case])
    results=[]
    with tempfile.TemporaryDirectory() as tmp:
        area=Path(tmp);sock=area/"sockets";sock.mkdir()
        with maven_mirror.serve(args.maven_cache,sock,4*1024**3):
            for site in SITES[args.case]:
                for remove in (False,True):
                    with tempfile.TemporaryDirectory(dir=area) as local:
                        result=treatment(Path(local),args,case,site,remove,sock)
                    results.append(result)
                    (args.output/"treatments.json").write_text(json.dumps(results,indent=2)+"\n")
                    print(site,result["treatment"],result["exit"],result["matched"],flush=True)
                    if not result["originalIncidentRows"]:
                        result["leaveOriginalIncidentOut"] = "identical knowledge input: no record of this original incident"
                        (args.output/"treatments.json").write_text(json.dumps(results,indent=2)+"\n")
                        break


if __name__=="__main__":
    main()
