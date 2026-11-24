"""Adjudicate the 187 original questions from fresh captures. No checker runs here."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import re
import statistics
import subprocess

from history import scratch, HERE, JDK, OUTPUT, benchmark, check_pin, digest, encoded, population
from stock_history import adapters, classpath


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def primary(row):
    if row["class"] == "correct":
        if row["verdict"] == "verified": return "proved"
        if row["verdict"] == "violation" and row.get("witnessOnTheJvm","").startswith("refuted"): return "refuted"
        return "unconfirmed witness"
    if row.get("reason") == "out of time": return "timeout"
    if row["class"] == "unsupported": return row.get("reason","unknown")
    return row["class"]


def stock_disposition(r, contrary):
    t, control = r["target"], r["reach"]
    replay = t.get("jvmReplay", {})
    answer = replay.get("stdout") if replay.get("exit") == 0 else None
    if t["status"] == "FAILURE":
        if answer in ("observation=0", "observation=-1"):
            external = t.get("independentJvm")
            if external and "\trefuted" not in external:
                return "disputed"
            return "refuted" if r["expected"] == "violation" else "disputed"
        if answer in ("observation=1", "observation=-2"): return "incorrect refutation"
        if answer == "observation=2": return "domain mismatch"
        return "unconfirmed witness"
    if t["status"] != "SUCCESS": return t["status"]
    if contrary:
        return "incorrect proof" if contrary["observation"] in ("observation=0","observation=-1") else "disputed"
    if any("unwind" in p["property"].lower() for p in t["otherFailures"]): return "incomplete unwinding"
    if t["otherFailures"] or t["exit"] != 0: return "other failed property"
    if control["status"] != "FAILURE": return "post-call control did not fail"
    c = control.get("jvmReplay", {})
    if c.get("exit") != 0 or c.get("stdout") not in ("observation=0", "observation=1"):
        return "post-call input unconfirmed on JVM"
    return "proved" if r["expected"] == "verified" else "disputed"


def check_contrary(h, stock):
    # A published expectation alone is insufficient for calling a universal assertion incorrect.
    candidates = [r for r in stock if r["target"]["status"] == "SUCCESS" and r["expected"] == "violation"]
    if not candidates: return {}
    out = {}
    cases, _ = population()
    corpus = (HERE.parents[1] / "tests/conformance.rs").read_text()
    fixtures = {name: re.findall(r'\("([^"]*)",\s*', body)
                for name, body in re.findall(r'Case::new\("([^"]+)",\s*&\[(.*?)\]\)', corpus, re.S)}
    with scratch(prefix="stock-adjudication-") as tmp:
        build = Path(tmp)
        _, source = check_pin(build)
        prepared, _, helper = adapters(build,cases,source)
        cp_by_id = {c["id"]:(name,cp) for c,name,params,java,cp in prepared}
        for r in candidates:
            cid = r["case"]
            name, cp = cp_by_id[cid]
            trials = [(e, h[cid,e]["witness"]) for e in ("native","jbmc") if primary(h[cid,e]) == "refuted"]
            if cid.startswith("conformance/"):
                trials.extend(("original conformance calls", args) for args in fixtures.get(cid.split("/")[1], ()))
            for origin, args in trials:
                cmd = [str(JDK/"bin/java"), "-ea", "-cp", classpath([helper,*cp]), "StockReplay", name, args]
                result = subprocess.run(cmd,text=True,capture_output=True,timeout=20,check=True)
                observation = result.stdout.strip()
                if observation in ("observation=0","observation=-1"):
                    out[cid] = {"inputSource":origin,"arguments":args,"observation":observation,"argv":cmd}
                    break
    return out


def make(phase, base, dest):
    cases, pins = population()
    archived = {r["id"]:r["archived"] for r in pins}
    h = load(base/"historical/results.json.gz")
    stock = load(base/"stock/results.json.gz")
    if h["manifestSha256"] != digest(HERE/"historical/manifest.json") or stock["frozenSha256"] != json.loads((HERE/"historical/manifest.json").read_bytes())["archive"]["sha256"]:
        raise ValueError("results refer to another cohort")
    for sub, result, field in [("historical",h,"rawExecutionsSha256"),("stock",stock,"archiveSha256")]:
        if digest(base/sub/"executions.zip") != result[field]: raise ValueError("execution capture differs")
    rs = {(r["case"], r["engine"]):r for r in h["runs"]}
    jobs = [h["environment"]["job"], stock["job"]]
    ids = [c["id"] for c in cases]
    if (len(h["runs"]) != 374 or len(rs) != 374 or [c["id"] for c in h["cases"]] != ids
            or [r["case"] for r in stock["rows"]] != ids):
        raise ValueError("incomplete or reordered population")
    contrary = check_contrary(rs,stock["rows"])
    rows = []
    paired = {e:Counter() for e in ("integrated","stock","either")}
    totals = {e:Counter() for e in ("native","integrated","stock")}
    costs = {e:[] for e in ("integrated","stock")}
    cost_fields = ("seconds","cpuSeconds","peakMB")
    complete = ("proved","refuted")
    for c,s in zip(cases,stock["rows"]):
        cid = c["id"]
        row = {"case":cid,"expected":c["expected"],"historical":archived[cid]}
        for key, name in (("native","native"),("jbmc","integrated")):
            r=rs[cid,key]
            row[name] = {k:r[k] for k in ("verdict","class","reason","problem","witness","witnessOnTheJvm",*cost_fields) if k in r}
            row[name]["decision"] = primary(r)
        t = s["target"]
        row["stock"] = {"verdict":t["status"],"assertion":(t.get("target") or {}).get("property"),"postCall":s["reach"]["status"],
                        "otherFailures":t.get("otherFailures"),"traceArguments":t.get("arguments"),"jvmReplay":t.get("jvmReplay"),
                        "independentJvm":t.get("independentJvm"),"contraryOriginalJvm":contrary.get(cid),
                        "decision":stock_disposition(s,contrary.get(cid)),**{k:t[k] for k in cost_fields}}
        for e in totals: totals[e][row[e]["decision"]]+=1
        n = row["native"]["decision"] in complete
        for e in paired:
            j = any(row[x]["decision"] in complete for x in (("integrated","stock") if e=="either" else (e,)))
            key = ("both" if j else "native-only") if n else ("comparator-only" if j else "neither")
            paired[e][key] += 1
            if e in costs and n and j: costs[e].append((row["native"], row[e]))
        rows.append(row)
    dest.mkdir(parents=True,exist_ok=True)
    report={"phase":phase,"jobs":jobs,"matched":paired,"counts":totals,"rows":rows,
            "inputReportDigests":{p:digest(base/p/"results.json.gz") for p in ("stock","historical")}}
    (dest/"matrix.json.gz").write_bytes(gzip.compress(encoded(report),mtime=0))
    md=[f"# Historical 187 at {phase}", "", "The programs and statements match the original November 7 inputs. Every stock target and post-call control used the packaged Ubuntu 24.04 JBMC 6.11.0 model JAR. Proof credit requires complete reported properties and a failing post-call control with its normal-return input reproduced on the JVM. A target refutation requires that its own input reproduce the failure on the original JVM. A stock proof contradicted on its own public caller is recorded as incorrect.", "",
        "| Native against | Both | Native only | Comparator only | Neither |", "|---|---:|---:|---:|---:|"]
    for e, counts in paired.items():
        md.append(f"| {e} | " + " | ".join(str(counts[k]) for k in ("both","native-only","comparator-only","neither")) + " |")
    md.extend(["","| Disposition | Strict native | Integrated staged | Standalone stock |","|---|---:|---:|---:|"])
    for k in sorted(set().union(*totals.values())):
        md.append(f"| {k} | " + " | ".join(str(counts[k]) for counts in totals.values()) + " |")
    md.extend(["","| Matched correct pairs | Count | Median wall s, native / comparator | Median CPU s | Median peak MiB |",
               "|---|---:|---:|---:|---:|"])
    for e, pairs in costs.items():
        md.append(f"| {e} | {len(pairs)} | " + " | ".join(
            " / ".join(f"{statistics.median(pair[i][k] for pair in pairs):.3f}" for i in (0,1)) if pairs else "—"
            for k in cost_fields) + " |")
    md.extend(["","Costs cover the target checker processes, including children. The stock reach control and JVM adjudication are additional work. The full 187 rows retain capped times and incomplete reports. Proof caches were disabled. Host page cache state was unmeasured. [Row-level outcomes and disagreements](matrix.json.gz)"])
    (dest/"RESULTS.md").write_text("\n".join(md)+"\n")
    print(phase,dict(paired),dict(totals))


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("phase",choices=["opening","closing"])
    ap.add_argument("--inputs",type=Path)
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    make(args.phase,args.inputs or OUTPUT/args.phase,args.output or OUTPUT/args.phase/"comparison")
