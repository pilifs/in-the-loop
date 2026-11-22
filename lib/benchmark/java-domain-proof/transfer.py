"""Price the Avro wrap proof at the Parquet public caller and check its read-only child view."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "domain-foundations"))
from buffer_fact import certify, dependencies, elapsed, execute, site_inputs, validate_producer
from results import Job
from startup import document, materialize, runtime_jdk, runtime_maven
from public_run import measure, native
from companions import proof

HISTORICAL = "20261122-050534-confirm-avro-encoder-adoption-on-the-fin"
CHILD_GUARD = ("start >= 5 && start < bytes.length && length >= 0 && length <= bytes.length - 1 - start "
               "&& index >= 0 && ((length == 0 && index == 0) || index < length)")
SHA = runtime_maven.sha256_of


def check_sites(raw, plain, side, previous_method):
    ordinary = {int(fields[0]): fields[1:] for line in plain.decode().splitlines() if (fields := line.split())}
    traces, answers = {}, {}
    for line in raw.decode().splitlines():
        fields = line.split("\t")
        if fields[0] == "ROW":
            code, outcome = map(int, fields[1:])
            if code in answers:
                raise ValueError("repeated public observation")
            answers[code] = outcome
        elif fields[0] == "SITE":
            code, offset, width, capacity, meta_offset, meta_width, meta_capacity, initial, end, pos, limit = map(int, fields[1:12])
            sites = fields[12:]
            if len(sites) != 4 or code in traces or sites[0] != sites[1]:
                raise ValueError("missing or ambiguous Parquet application site")
            # Slashes inside the JVM descriptor belong to its class names.
            target, bytecode, _pool = sites[0].split(">")[1].rsplit("/", 2)
            if (target, bytecode) != ("java.nio.ByteBuffer#wrap([BII)Ljava/nio/ByteBuffer;@0", previous_method):
                raise ValueError("the Parquet wrap differs from the Avro producer")
            left, right, index = code & 3, (code >> 2) & 3, (code >> 4) & 1
            pad = 25 if code >= 32 else 0
            expected_width = 15 + left + right
            selected = right if index else left
            if (offset, width, capacity, meta_offset, meta_width, meta_capacity) != (
                    pad, expected_width, pad+expected_width+1, pad, 3, pad+4):
                raise ValueError("the original wrap operands differ from the serialized wire layout")
            expected = pad + 5 + (5+left if index else 0)
            if (initial,end,pos,limit) != (expected,pad+width,expected+5,
                    expected+5+selected if side=="fix" else pad+width):
                raise ValueError("actual original buffer bounds differ")
            p = ordinary[code]
            if list(map(int,p[1:7])) != [1,capacity,initial,pos,limit,limit-pos] or p[7:] != ["true","false","java.nio.HeapByteBufferR"]:
                raise ValueError("plain JVM differs from its traced child")
            traces[code] = dict(input=code, backing=capacity, metadataBacking=meta_capacity, sourcePosition=initial,
                                sourceLimit=end, position=pos, limit=limit, wrapSite=sites[0],
                                publicSite=sites[2], duplicateSite=sites[3])
    if len(ordinary)!=64 or set(traces)!=set(range(64)) or answers!={k:int(v[0]) for k,v in ordinary.items()}:
        raise ValueError("incomplete public caller correspondence")
    expected = {code:int(side=="fix" or bool(code & 16)) for code in range(64)}
    if answers!=expected:
        raise ValueError("the traced public result disagrees with the historical failure")
    return [traces[k] for k in sorted(traces)]


def parquet(side, work, jdk, env, previous_method):
    folder, = (ROOT/"examples").glob("363-*")
    run = work/side
    run.mkdir()
    jars,binding=materialize(folder,side,run)
    classes=run/"classes";classes.mkdir()
    cp=os.pathsep.join(map(str,[classes,*jars]))
    _, build=execute([jdk/"bin/javac","-J-Djava.io.tmpdir="+str(run),"-parameters","-g","-cp",cp,"-d",classes,
                      folder/"adapter/campaign/NestedBinary.java",HERE/"SerializedBinary.java",HERE/"ParquetSites.java"],run,env)
    java=[jdk/"bin/java","-Xmx384m","-Djava.io.tmpdir="+str(run),"-cp",cp]
    plain, natural=execute([*java,"campaign.SerializedBinary"],run,env)
    traced, trace=execute([*java,"campaign.ParquetSites","trace",cp,str(run)],run,env)
    return {"binding":binding,"rows":check_sites(traced,plain,side,previous_method),
            "costs":{"compile":build,"plain":natural,"debugger":trace}}


def run(dest):
    jdk=Path(runtime_jdk.home("21")); checker=Path(os.environ["JVMCONTRACT"]).resolve()
    historical=Job(HISTORICAL)
    old=historical.single("encoder-adoption-final/wide-wrap.json")
    key=historical.files[next(p for p in historical.files if p.match("encoder-adoption-final/wide-wrap.json"))]["sha256"]
    old_identity=json.loads(old.read_bytes())["dependencies"]
    validate_producer(old,key,old_identity,"wrap")
    old_sites=json.loads(historical.single("encoder-adoption-final/sites.json").read_bytes())
    methods={r["targetMethodSha256"] for side in old_sites["reuse"].values() for r in side["sites"] if r["call"]=="wrap"}
    previous_method,=methods
    dest.mkdir(parents=True,exist_ok=True)
    routes={}; root=HERE.parent/"domain-foundations"
    folder, = (ROOT / "examples").glob("363-*")
    with tempfile.TemporaryDirectory(prefix="parquet-transfer-") as tmp:
        area=Path(tmp);env={**os.environ,"JAVA_HOME":str(jdk),"PATH":str(jdk/"bin")+os.pathsep+os.defpath,"TMPDIR":tmp,"JVMCONTRACT_JAR_RELEASE":"21"}
        for route in ("disabled","clean","reuse"):
            work=area/route;work.mkdir()
            (work/"proof").mkdir();(work/"trace").mkdir()
            begin=time.monotonic()
            _,setup=execute([jdk/"bin/javac","-J-Djava.io.tmpdir="+tmp,"-g","-parameters","-d",work/"proof",root/"BufferRange.java"],work,env)
            identity=dependencies(work,jdk,checker,20)
            at=time.monotonic()
            small = None
            if route=="reuse":
                validate_producer(certificate,certificate_key,identity,"wrap")
                small_key = certificate_key
            elif route=="clean":
                cert=dest/(route+"-20.json")
                checked,small=certify(work,jdk,checker,env,cert,"wrap",20)
                certificate,certificate_key=(old,key) if identity==old_identity else (cert,checked)
            validation=elapsed(at)
            if route=="clean":
                _,tracer=execute([jdk/"bin/javac","-J-Djava.io.tmpdir="+tmp,"-d",work/"trace",root/"BufferSites.java"],work,env)
                sites={side:site_inputs("362",side,work,jdk,env,20) for side in ("parent","fix")}
                costs=[tracer,*(s["cost"] for s in sites.values())]
                wide=None
            else:
                # Both routes prove the enlarged bound. The earlier proof covers only the smaller wraps.
                wide_key,wide=certify(work,jdk,checker,env,dest/(route+"-47.json"),"wrap",47)
                if route == "disabled":
                    # One fresh wide certificate covers both wraps. Charging this route
                    # for a redundant small proof would inflate any reported saving.
                    small_key = wide_key
                sites={s:parquet(s,work,jdk,env,previous_method) for s in ("parent","fix")}
                costs=[c for s in sites.values() for c in s["costs"].values()]
            routes[route]={"seconds":elapsed(begin),"setup":setup,"smallProof":small,"smallProofOrValidationSeconds":validation,
                           "wideProof":wide,"siteSeconds":sum(c["seconds"] for c in costs),
                           "peakRssBytes":max(c["peakRssBytes"] for c in [setup,*costs,*[x for x in (small,wide) if x]]),
                           "sites":sites}
            if route != "clean":
                # Bind the two actual rewrap calls separately. A small metadata wrap can
                # qualify for reuse even when the enclosing value requires the wider proof.
                routes[route]["applications"] = {
                    side: [{"input": r["input"],
                            "value": small_key if r["backing"] <= 20 else wide_key,
                            "metadata": small_key if r["metadataBacking"] <= 20 else wide_key}
                           for r in leg["rows"]] for side, leg in sites.items()}
                receipts = dest / route
                receipts.mkdir()
                public = native(folder, "extent-fix", [sys.executable, "examples/tools/build.py", "363"],
                                receipts, ["--checker-seconds", "60"])
                routes[route]["publicWorkflow"] = public
                routes[route]["endToEndSeconds"] = elapsed(begin)
            document(dest/"routes.json", routes)
        for side in ("parent","fix"):
            if routes["disabled"]["sites"][side]["rows"]!=routes["reuse"]["sites"][side]["rows"]:
                raise ValueError("the two downstream workflows used different public operands")
        fresh, reused = (routes[r]["publicWorkflow"] for r in ("disabled", "reuse"))
        fresh_result, reuse_result = (json.loads((dest / r / run["receipt"]).read_bytes())
                                      for r, run in (("disabled", fresh), ("reuse", reused)))
        if (fresh_result["claim"] != reuse_result["claim"] or fresh["status"] != reused["status"]
                or fresh_result["attempt"]["tools"] != reuse_result["attempt"]["tools"]):
            raise ValueError("the downstream public claim, verifier or decision changed between routes")
        for label,changed in (("bound",{"maxArrayLength":47}),("provider",{"jdkModules":"0"*64}),("observable",{"assert":"result == 0"})):
            try:validate_producer(certificate,certificate_key,{**identity,**changed},"wrap")
            except ValueError:pass
            else:raise ValueError("unsound reuse after changing "+label)
        _,compile_cost=execute([jdk/"bin/javac","-J-Djava.io.tmpdir="+tmp,"-g","-parameters","-d",work/"proof",HERE/"ReadOnlyChild.java"],work,env)
        child_path=dest/"read-only-child.native.json"
        child_cost=measure([checker,"prove","campaign.ReadOnlyChild#child","--classes",work/"proof","--engine","native",
                "--gaps","strict","--unwind","64","--max-array-length","47","--timeout","60","--assume",CHILD_GUARD,
                "--assert","result == 1","--json"],child_path,cwd=work,env=env,stderr=dest/"read-only-child.stderr")
        outcome,=json.loads(child_path.read_bytes());stated=outcome["stated"]
        if (outcome["target"]!="campaign.ReadOnlyChild#child" or outcome["assume"]!=CHILD_GUARD
            or outcome["assert"]!="result == 1" or stated["gap_mode"]!="strict"):
            raise ValueError("the read-only query differs from the requested statement")
        if outcome["verdict"]=="verified" and (outcome["problem"] or child_cost["exit"] or
            stated["bounds"]!={"unwind":64,"max_array_length":47,"complete":True} or stated["vacuity"]["status"]!="non-vacuous"
            or {a["kind"] for a in stated["assumptions"]}!={"precondition","initialization"}):
            raise ValueError("the read-only view proof did not qualify")
        rows=routes["reuse"]["sites"]["fix"]["rows"]
        document(dest/"measurement.json",{"routes":routes,"historicalCertificate":key,"source":os.environ["VERIFY_SOURCE_COMMIT"],
                 "directHistoricalReuse":identity==old_identity,"usedCertificate":certificate_key,"checkerSha256":SHA(checker),
                 "valueWrapsWithinTwenty":[r["input"] for r in rows if r["backing"]<=20],
                 "metadataWrapsWithinTwenty":[r["input"] for r in rows if r["metadataBacking"]<=20],
                 "maximumBacking":max(r["backing"] for r in rows),"invalidations":["bound","provider","observable"],
                 "readOnlyChild":{"verdict":outcome["verdict"],"firstBlocker":outcome["problem"],
                                  "proofSha256":SHA(child_path),"compile":compile_cost,"proof":child_cost},
                 "checkerImportsCertificate":False,
                 "scope":"Checked wrap facts used at measured Parquet call sites. The public native checker runs independently on each route.",
                 "agentMinutes":None})
        for side in ("parent", "fix"):
            leg = work / side
            jars = sorted(leg.glob("*.jar"))
            companion = dest / ("serialized-" + side)
            companion.mkdir()
            outcomes = {}
            for method in ("extent", "fresh"):
                outcomes[method] = proof(checker, leg/"classes", jars, leg, env, companion,
                                         "campaign.SerializedBinary#"+method, method,
                                         "code >= 0 && code < 64", bounds=(96,2048))
            document(companion/"measurement.json", {"binding":routes["reuse"]["sites"][side]["binding"],
                     "startup":"ordinary", "entry":"public Variant from independently constructed serialized bytes",
                     "checker":SHA(checker),"proofs":outcomes})
        print({k:v["seconds"] for k,v in routes.items()})


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,required=True)
    run(p.parse_args().output.resolve())
