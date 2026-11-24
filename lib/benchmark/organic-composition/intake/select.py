"""Apply the committed URL-only intake policy. Only the selected URL is emitted."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
PRIOR=ROOT/"lib/benchmark/beyond-jbmc"
API="https://api.github.com"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def membership():
    private=Path.home()/".cache/in-the-loop/beyond-jbmc/panel/sealed.json"
    raw=private.read_bytes()
    if digest(raw)!=(PRIOR/"panel.sha256").read_text().split()[0]:raise ValueError("blind panel commitment mismatch")
    panel=json.loads(raw)["pairs"]
    aliases={"github.com/stleary/json-java","stleary.github.io","libjson-java-org","libandroid-json-org-java"}
    sealed=any({r["project"].lower(),r["source"].lower(),r["artifact"].lower()} & aliases for r in panel)
    casebook=(PRIOR/"casebook.json").read_text().lower()
    disclosed=any(v in casebook for v in ("stleary/json-java","org.json:json","\"org.json\""))
    with gzip.open(ROOT/"verification/beyond-jbmc/closing/shadow-comparison/matrix.json.gz") as f:
        shadow=json.load(f)["rows"]
    historical=any(r["entry"].startswith("org.json.") or "stleary/json-java" in r["id"].lower() for r in shadow)
    return {"sealedProjectOverlap":sealed,"disclosedProjectOverlap":disclosed,"historicalClientOverlap":historical,
            "sealedCommitment":digest(raw),"disclosedCasebookSha256":digest((PRIOR/"casebook.json").read_bytes())}


def get(path):
    req=urllib.request.Request(API+path,headers={"Accept":"application/vnd.github+json","User-Agent":"in-the-loop-java-verification"})
    with urllib.request.urlopen(req,timeout=30) as response:
        return json.load(response)


def draw():
    policy=json.loads((HERE/"policy.json").read_bytes()); overlap=membership()
    if any(overlap[k] for k in ("sealedProjectOverlap","disclosedProjectOverlap","historicalClientOverlap")):
        raise ValueError("selected project overlaps an exclusion")
    repo=policy["project"]; candidates=[];page=1
    while True:
        params=urllib.parse.urlencode({"q":policy["populationQuery"],"sort":"created","order":"asc","per_page":100,"page":page})
        answer=get("/search/issues?"+params)
        if answer["incomplete_results"]:raise ValueError("incomplete candidate result")
        candidates.extend((a["number"],a["title"]) for a in answer["items"])
        if len(candidates)>=answer["total_count"]:break
        if not answer["items"] or page>=10:raise ValueError("candidate query exceeds reproducible limit")
        page+=1
    examples="\n".join(p.read_text(errors="replace").lower() for p in (ROOT/"examples").glob("*/example.json"))
    screened=[]; selected=None
    for number,title in sorted(candidates):
        words=set(re.findall(r"[a-z]+",title.lower()))
        if not words.intersection(policy["includeTitleWords"]) or words.intersection(policy["excludeTitleWords"]):
            continue
        url=f"https://github.com/{repo}/pull/{number}"
        if re.search(re.escape(url.lower())+r"(?!\d)",examples):
            screened.append([number,"previous example"]);continue
        files=[];page=1
        while True:
            records=get(f"/repos/{repo}/pulls/{number}/files?per_page=100&page={page}")
            files.extend(r["filename"] for r in records)
            if len(records)<100:break
            page+=1
        if not any(Path(n).name=="JSONArray.java" and "test" not in n.lower() for n in files) or not any(n.endswith(".java") and "test" in n.lower() for n in files):
            screened.append([number,"production or test filename missing"]);continue
        selected={"url":url,"number":number};screened.append([number,"selected"]);break
    report={"policySha256":digest((HERE/"policy.json").read_bytes()),"exclusions":overlap,
            "populationSize":len(candidates),"populationDigest":digest(json.dumps(sorted(candidates),ensure_ascii=False).encode()),
            "screened":screened,"selected":selected,"intakeExposure":"PR titles and changed filenames were filtered by the program; no patches, test content, PR descriptions or comments were emitted."}
    output=ROOT/"verification/organic-composition/url-intake/draw.json";output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists() and json.loads(output.read_bytes())!=report:raise ValueError("draw differs from recorded result")
    output.write_text(json.dumps(report,indent=2)+"\n")
    print(selected["url"] if selected else "empty draw")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--draw",action="store_true");a=parser.parse_args()
    if a.draw:draw()
    else:print(json.dumps(membership(),sort_keys=True))
