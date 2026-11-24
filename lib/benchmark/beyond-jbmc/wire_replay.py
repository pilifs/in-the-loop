"""Replay claims and literal stock/integrated counterexamples using two original class loaders."""
import argparse
import gzip
import json
from pathlib import Path

from history import scratch, OUTPUT, benchmark, digest, encoded
from wire_campaign import CASES, prepare, replay_classes, replay


def audit(source, output):
    report = json.loads(gzip.decompress(source.read_bytes()))
    rows = report["rows"]
    if [r["method"] for r in rows] != list(CASES):
        raise ValueError("incomplete wire report")
    audits = []
    with scratch(prefix="wire-adjudication-") as tmp:
        work=Path(tmp)
        env,jars,cp,identity=prepare(work)
        for key in ("jarSha256","jdkModulesSha256","callerSha256","relocatedCallerSha256","claimsSha256"):
            if report[key] != identity[key]:
                raise ValueError("wire binding drift: "+key)
        original=replay_classes(work,env)
        for row in rows:
            for engine in ("native","jbmc","stock"):
                data=row[engine]["target"] if engine=="stock" else row[engine]
                if engine=="stock":
                    if data["status"]!="FAILURE": continue
                    tokens=";".join(benchmark.token(v,chars=False) for v in data["arguments"]) if "arguments" in data else None
                else:
                    if data.get("verdict")!="violation": continue
                    tokens=benchmark.witness_arguments(data)
                checked=replay(original,env,jars,cp[1],row["method"],tokens) if tokens is not None else []
                audits.append({"method":row["method"],"case":row["case"],"engine":engine,"tokens":tokens,"originalJvm":checked})
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(encoded({"sourceSha256":digest(source),"job":report["job"],"rows":audits}))
    print([(r["method"],r["engine"],[v["outcome"] for v in r["originalJvm"]]) for r in audits])


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source",type=Path)
    p.add_argument("output",type=Path)
    a=p.parse_args()
    audit(a.source,a.output)
