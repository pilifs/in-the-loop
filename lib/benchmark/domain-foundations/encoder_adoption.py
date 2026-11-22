"""Measure the Avro encoder's adoption of the heap-window certificate at its actual JVM call sites."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time

from buffer_fact import certify, dependencies, elapsed, execute, site_inputs, validate_producer
from results import Job
from startup import HERE, document, runtime_jdk, runtime_maven


def run(output):
    jdk = Path(runtime_jdk.home("21"))
    checker = Path(os.environ["JVMCONTRACT"]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="encoder-adoption-") as tmp:
        area=Path(tmp)
        env={"JAVA_HOME":str(jdk),"PATH":str(jdk/"bin")+os.pathsep+os.defpath,"TMPDIR":tmp,
             "LANG":"C","LC_ALL":"C","TZ":"UTC","JVMCONTRACT_JAR_RELEASE":"21"}
        costs, sites = {}, {}
        producer=output/"wide-wrap.json"
        for route, number in (("disabled","362"),("clean","355"),("reuse","362")):
            start=time.monotonic()
            work=area/route
            for folder in ("proof","trace"): (work/folder).mkdir(parents=True)
            compiler=[jdk/"bin/javac","-J-Djava.io.tmpdir="+tmp]
            _, build=execute([*compiler,"-parameters","-g","-d",work/"proof",HERE/"BufferRange.java"],work,env)
            _, trace=execute([*compiler,"-d",work/"trace",HERE/"BufferSites.java"],work,env)
            at=time.monotonic()
            if route=="reuse":
                validate_producer(producer,key,dependencies(work,jdk,checker,20),"wrap")
                proof=None
            else:
                fresh,proof=certify(work,jdk,checker,env,producer if route=="clean" else output/"disabled-wrap.json","wrap",20)
                if route=="clean": key=fresh
            validation=elapsed(at)
            rows={side:site_inputs(number,side,work,jdk,env,20) for side in ("parent","fix")}
            sites[route]=rows
            costs[route]={"sourceExample":number,"proofExecutions":int(proof is not None),"setupSeconds":build["seconds"]+trace["seconds"],
                "proofOrValidationSeconds":validation,"siteSeconds":sum(r["cost"]["seconds"] for r in rows.values()),
                "totalSeconds":elapsed(start),"peakRssBytes":max(build["peakRssBytes"],trace["peakRssBytes"],
                    (proof or {}).get("peakRssBytes",0),*(r["cost"]["peakRssBytes"] for r in rows.values()))}
        for side in ("parent","fix"):
            if sites["disabled"][side]["sites"] != sites["reuse"][side]["sites"]:
                raise ValueError("the two encoder routes reached different original call sites")
        # The old six-byte fact cannot cover a 20-byte backing array, even if the logical view is shorter.
        wrong=dependencies(work,jdk,checker,6)
        try: validate_producer(producer,key,wrong,"wrap")
        except ValueError: pass
        else: raise ValueError("proof reused across different bounds")
        historical=Job("20261121-234701-qualify-bounded-heap-buffer-facts-across")
        historical_path,=[p for p in historical.files if p.match("buffer-adoption/clean-wrap.json")]
        original=historical.output(historical_path)
        old=json.loads(original.read_bytes())
        old_key=historical.files[historical_path]["sha256"]
        validate_producer(original,old_key,old["dependencies"],"wrap")
        try: validate_producer(original,old_key,{**old["dependencies"],"maxArrayLength":20},"wrap")
        except ValueError: pass
        else: raise ValueError("six-byte proof admitted for a wider caller")
        if wrong==old["dependencies"]: raise ValueError("expected the historical checker to differ")
        _, setup=execute([*compiler,"-g","-parameters","-d",work/"proof",HERE/"ReadOnlyRange.java"],work,env)
        _, read=certify(work,jdk,checker,env,output/"read-only.json","readOnly",20,"ReadOnlyRange")
        document(output/"sites.json",sites)
        small=[row["input"] for row in sites["reuse"]["fix"]["sites"] if row["call"]=="wrap" and row["capacity"]<=6]
        if len(small)!=8: raise ValueError("different pilot-bound coverage")
        document(output/"measurement.json",{"routes":costs,"originalCertificateSha256":runtime_maven.sha256_of(original),
            "originalBound":6,"selectorsWithinOriginalBound":small,"qualifiedBound":20,"changedBound":"declined",
            "historicalSixAtTwenty":"declined","checkerSha256":runtime_maven.sha256_of(checker),
            "wideCertificateSha256":key,"readOnlySetup":setup,"readOnlyProof":read,"sitesSha256":runtime_maven.sha256_of(output/"sites.json"),
            "agentMinutes":None})
        print(json.dumps(costs))
if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output",type=Path,required=True)
    run(ap.parse_args().output.resolve())
