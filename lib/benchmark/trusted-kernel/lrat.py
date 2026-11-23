"""Bind LRAT evidence to a single observed incremental solve. Never use clauses from later calls."""
import argparse
import gzip
import json
import os
from pathlib import Path
import shutil
import statistics
import tempfile

from prepare import HERE, digest
from replay import measured

CACHE = Path.home()/".cache/in-the-loop/trusted-kernel/src"
CADICAL=Path(os.environ.get("KERNEL_CADICAL", CACHE/"cadical-1.9.5/build/cadical"))
CAKE=Path(os.environ.get("KERNEL_CAKE", CACHE/"cake_lpr-033aad53/cake_lpr"))


def queries(raw):
    clauses=[]
    called=None
    header=False
    for line in raw.decode("ascii").splitlines():
        if line.startswith("c answer "):
            if called is None: raise ValueError("answer without a solve")
            answer=line.split()[2]
            if answer not in {"sat","unsat","unknown"}: raise ValueError("unknown answer token")
            yield tuple(clauses),called,answer
            called=None
        elif line.startswith("c") or not line:
            continue
        elif line=="p inccnf" and not header:
            header=True
        else:
            if not header or called is not None: raise ValueError("interleaved or headerless formula")
            fields=line.split()
            solve=fields[0]=="a"
            lits=[int(s) for s in fields[int(solve):]]
            if not lits or lits[-1]!=0 or 0 in lits[:-1]: raise ValueError("unterminated clause or assumption")
            if solve: called=tuple(lits[:-1])
            else: clauses.append(tuple(lits[:-1]))
    if called is not None or not header: raise ValueError("incomplete transcript")


def dimacs(clauses, assumptions):
    rows=(*clauses,*((a,) for a in assumptions))
    maximum=max((abs(v) for row in rows for v in row),default=0)
    return (f"p cnf {maximum} {len(rows)}\n"+"".join(" ".join(map(str,(*row,0)))+"\n" for row in rows)).encode()


def checked(cnf, proof, want, directory):
    r=measured([CAKE,str(cnf),str(proof)],directory)
    verified="s VERIFIED UNSAT" in r["stdout"].splitlines()
    if r["exit"]!=0 or verified!=want: raise ValueError(r)
    return r


def run(src,out,recheck):
    capture=json.loads((src/"capture.json").read_text())
    family="336/first-8-release" if any(t["answers"]["unsat"] for t in capture["336/first-8-release"]) else "held/prefix-sums"
    sub="first" if family.startswith("336") else "fallback"
    total=sum(t["answers"]["unsat"] for t in capture[family])
    if total<1: raise ValueError("no observed UNSAT call")
    if not recheck: out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work=Path(tmp)
        selected=None
        for trace in capture[family]:
            raw=gzip.decompress((src/sub/trace["file"]).read_bytes())
            if digest(raw)!=trace["sha256"]: raise ValueError("transcript digest")
            for index,(clauses,assumptions,ans) in enumerate(queries(raw),1):
                if ans=="unsat":
                    selected=(trace,index,clauses,assumptions)
                    break
            if selected: break
        trace,index,clauses,assumptions=selected
        cnf=work/"query.cnf"
        proof=work/"query.lrat"
        cnf.write_bytes(dimacs(clauses,assumptions))
        version=measured([CADICAL,"--version"],work)["stdout"]
        if version!="1.9.5": raise ValueError("expected CaDiCaL 1.9.5")
        if recheck:
            receipt=json.loads((out/"result.json").read_text())
            if (digest(cnf.read_bytes())!=receipt["cnfSha256"] or
                cnf.read_bytes()!=gzip.decompress((out/"query.cnf.gz").read_bytes()) or
                digest(CAKE.read_bytes())!=receipt["checkerSha256"] or
                trace["sha256"]!=receipt["transcriptSha256"] or index!=receipt["queryOneBased"]):
                raise ValueError("formula, source, query or checker differs")
            proof.write_bytes(gzip.decompress((out/"query.lrat.gz").read_bytes()))
            if digest(proof.read_bytes())!=receipt["proofSha256"]: raise ValueError("proof digest")
        else:
            gen=measured([CADICAL,"--lrat","--no-binary",str(cnf),str(proof)],work)
            if gen["exit"]!=20 or "s UNSATISFIABLE" not in gen["stdout"].splitlines(): raise ValueError(gen)
        runs=[checked(cnf,proof,True,work) for _ in range(3)]
        # Removing every derivation, including the empty-clause conclusion, is a damaged proof.
        damaged=work/"damaged.lrat"
        damaged.write_bytes(b"1 1 0 0\n")
        bad=checked(cnf,damaged,False,work)
        sat=work/"sat.cnf"
        sat.write_text("p cnf 1 1\n1 0\n")   # x=true witnesses satisfiability
        satcheck=checked(sat,proof,False,work)
        if not recheck:
            for path in (cnf,proof):
                (out/(path.name+".gz")).write_bytes(gzip.compress(path.read_bytes(),mtime=0))
            summary={"workload":family,"trace":sub+"/"+trace["file"],"transcriptSha256":trace["sha256"],
                "queryOneBased":index,"precedingClauses":len(clauses),"assumptions":assumptions,
                "observedUnsat":total,"certified":1,"cnfSha256":digest(cnf.read_bytes()),"cnfBytes":cnf.stat().st_size,
                "proofSha256":digest(proof.read_bytes()),"proofBytes":proof.stat().st_size,
                "generatorVersion":version,"generatorSha256":digest(CADICAL.read_bytes()),"checkerRevision":"033aad53",
                "checkerSha256":digest(CAKE.read_bytes()),"generation":gen,"checks":runs,
                "medianCheckPeakKiB":statistics.median(r["peakKiB"] for r in runs),
                "damaged":bad,"knownSat":satcheck}
            (out/"result.json").write_text(json.dumps(summary,indent=2)+"\n")
        print(f"{family} query {index}: VERIFIED UNSAT. Damaged and known-SAT controls rejected. 1/{total} observed UNSAT.")


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capture",type=Path,default=HERE/"evidence/sat")
    ap.add_argument("--out",type=Path,default=HERE/"evidence/lrat")
    ap.add_argument("--check",action="store_true")
    args=ap.parse_args()
    run(args.capture,args.out,args.check)
