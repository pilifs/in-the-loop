"""Measure the same two public callers with their helper inlined or proved as a bounded lemma."""

import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / "examples/tools"))
sys.path.insert(0, str(ROOT / "lib/benchmark"))
from targets import route, runtime, runtime_jar
from run import measure


def benchmark(binary, output):
    example = json.loads((FOLDER/"example.json").read_text())
    target = json.loads((FOLDER/"target.json").read_text())
    records, preparations = [], {}
    with tempfile.TemporaryDirectory(prefix="tiling-reuse-") as tmp:
        work = Path(tmp)
        shared = {}
        for rev in ("recursive", "base-change"):
            for caller in ("exact", "parity"):
                plan = route.resolve(FOLDER, example, target, caller+"-"+rev)
                start = time.monotonic()
                p = route.prepare_revision(plan, rev, work/"prepared"/(caller+"-"+rev), shared)
                if p.stage != "artifacts-ready":
                    raise ValueError(p.diagnostic)
                cold = time.monotonic() - start
                start = time.monotonic()
                again = route.prepare_revision(plan, rev, work/"warm"/(caller+"-"+rev), shared)
                warm = time.monotonic() - start
                if p.artifacts != again.artifacts:
                    raise ValueError("warm preparation changed the bytes")
                where = runtime._preparation_dir(p)
                jar = where/p.source["target"]["loadedFrom"]
                import hashlib
                classes = {c: hashlib.sha256(runtime_jar.read_class(jar,c)).hexdigest()
                           for c in ("tiling/Floor","tiling/Ways","tiling/Oracle")}
                preparations[plan.task] = {"classes": classes, "jar": runtime.sha256(jar), "coldSeconds": round(cold,4), "warmSeconds": round(warm,4)}
                if not p.toolchain["jdk"]:
                    raise ValueError("missing compiler identity")
                for strategy in ("inline", "checked-lemma", "exact-cache"):
                    # A fresh store per caller and strategy, then exactly the same store for the warm run.
                    cache = work/"cache"/(caller+"-"+strategy)
                    for phase in ("cold", "warm"):
                        name = "-".join([rev,caller,strategy,phase])
                        argv = [str(binary),"prove","tiling.Floor#"+caller,"--classes",str(jar),"--engine","native","--gaps","strict",
                                "--assume",plan.claim["assume"],"--assert",plan.claim["assert"],"--unwind","24",
                                "--max-array-length","0","--timeout","25","--work",str(work/name),"--json"]
                        if strategy == "checked-lemma":
                            argv += ["--lemmas", str(FOLDER/"claims/helper.contract")]
                        if strategy == "exact-cache":
                            argv += ["--cache", str(cache)]
                        jdk = Path(runtime.runtime_jdk.home("21"))
                        measured = measure(["env","JAVA_HOME="+str(jdk),"PATH="+str(jdk/"bin")+":"+os.environ["PATH"],*argv], 110)
                        raw = measured["stdout"]
                        try:
                            [answer] = json.loads(raw)
                        except (ValueError, TypeError):
                            raise ValueError(f"{name} did not return one checker record: {measured['stderr'][-500:]}")
                        # Preserve the checker's original JSON and every phase before comparison.
                        (output/(name+".json")).write_text(raw)
                        search = answer.get("search") or {}
                        record = {key: value for key,value in measured.items() if key not in ("stdout","stderr")}
                        record.update(revision=rev, caller=caller, strategy=strategy, phase=phase,
                                      cacheCondition=(("previous helper bytes in store" if rev=="base-change" and phase=="cold" else phase)
                                                      if strategy=="exact-cache" else "no proof store, fresh process on prepared bytes"),
                                      claim=plan.claim["key"], bounds=plan.claim["bounds"], deadline=25, verdict=answer["verdict"],
                                      firstBlocker=answer.get("problem"), reuse=answer.get("reuse"), phases=search.get("phases"),
                                      searchSeconds=search.get("seconds"), raw=name+".json", sha256=runtime.sha256(output/(name+".json")))
                        records.append(record)
        if preparations["exact-recursive"]["classes"]["tiling/Floor"] != preparations["exact-base-change"]["classes"]["tiling/Floor"]:
            raise ValueError("the changed helper also changed the caller bytes")
        if preparations["exact-recursive"]["classes"]["tiling/Ways"] == preparations["exact-base-change"]["classes"]["tiling/Ways"]:
            raise ValueError("the invalidation control did not change helper bytes")
    return {"host":platform.node(),"checkerSha256":runtime.sha256(binary),"solver":os.environ.get("JVMCONTRACT_SOLVER","default"),
            "jdk":runtime.runtime_jdk.identity(runtime.runtime_jdk.home("21"))["version"],
            "cachePolicy":"Fresh native process and work directory each time. Only exact-cache uses a proof store. The repeat uses prepared bytes and, when enabled, the same proof store. OS page cache was uncontrolled.",
            "lemmaSha256":runtime.sha256(FOLDER/"claims/helper.contract"),"preparations":preparations,"runs":records}


if __name__=="__main__":
    directory=FOLDER/"records/reuse"
    directory.mkdir(parents=True,exist_ok=True)
    report=benchmark(Path(os.environ["JVMCONTRACT"]).resolve(),directory)
    (directory/"comparison.json").write_text(json.dumps(report,indent=2)+"\n")
    for row in report["runs"]:print(row["revision"],row["caller"],row["strategy"],row["phase"],row["verdict"],row["seconds"])
