"""Warm, cold and independent clean runs around a replaced class at the same original path."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from charset import compile_to, command, ENV, JDK, SMALL, java, startup_facts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scratch = Path(os.environ.get("TMPDIR") or Path.home()/".cache/in-the-loop/agent-tmp")
    if scratch == Path("/tmp") or Path("/tmp") in scratch.parents:
        scratch = Path.home()/".cache/in-the-loop/agent-tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="startup-reuse-", dir=scratch) as temp:
        work = Path(temp)
        classes = {side: work/side for side in ("parent","fix")}
        for target in classes.values():
            compile_to(target, sorted(SMALL.glob("*.java")))
        file = classes["fix"]/"sc/Encoded.class"
        original = file.read_bytes()
        source = work/"Encoded.java"
        source.write_text((SMALL/"Encoded.java").read_text().replace('"é".getBytes()', '"x".getBytes()'))
        replacement = work/"replacement"
        compile_to(replacement, [source])
        changed = (replacement/"sc/Encoded.class").read_bytes()
        assert changed != original
        cache = work/"receipts"
        ids = {}
        rows = []
        for phase in ("baseline","changed","restored"):
            if phase != "baseline":
                staged = work/"new-class"
                staged.write_bytes(changed if phase=="changed" else original)
                os.replace(staged,file)
            for side,path in classes.items():
                cmd = command("sc.M#encoded()I","result == 2",path)
                expected = "violation" if phase=="changed" and side=="fix" else "verified"
                current = work/(phase+"-"+side)
                previous = work/(("changed" if phase=="restored" else "baseline")+"-"+side)
                invalidated = False
                if phase != "baseline":
                    incoming = startup_facts.recover(cmd,previous,"C.UTF-8",revision=side,receipts=cache,env=ENV,resume=True)
                    if side=="fix":
                        assert not incoming["receiptId"] and "binding changed" in incoming["remaining"], incoming
                        invalidated = True
                    else:
                        assert incoming["receiptId"]==ids["baseline",side] and incoming["recording"].startswith("reused trace")
                cold = startup_facts.recover(cmd,current,"C.UTF-8",revision=side,receipts=cache,env=ENV)
                warm = startup_facts.recover(cmd,current,"C.UTF-8",revision=side,receipts=cache,env=ENV,resume=True)
                clean = startup_facts.recover(cmd,work/(phase+"-"+side+"-empty"),"C.UTF-8",revision=side,env=ENV)
                ids[phase,side] = cold["receiptId"]
                assert cold["receiptId"] and all(r["receiptId"]==cold["receiptId"] and r["retry"]==expected for r in (cold,warm,clean))
                assert warm["recording"].startswith("reused trace") and clean["recording"]=="fresh JVM trace"
                physical = java(["-XX:-UsePerfData","-Dfile.encoding=COMPAT","-cp",path,"sc.M","encoded"],"C.UTF-8").decode().strip()
                assert physical==("encoded=1" if expected=="violation" else "encoded=2"),physical
                rows.append({"phase":phase,"side":side,"revision":side,"original":physical,"claim":cold["original"]["target"],
                             "predicate":"result == 2","verdict":expected,"receipt":cold["receiptId"],"cold":cold["recording"],
                             "warm":warm["recording"],"clean":clean["recording"],"previousRejected":invalidated,
                             "consumed":cold["consumed"],"proofVerdictsReused":0})
        for side in classes:
            assert ids["baseline",side]==ids["restored",side]
        assert ids["baseline","fix"]!=ids["changed","fix"]
        assert ids["baseline","parent"]==ids["changed","parent"]
        old_again=startup_facts.recover(command("sc.M#encoded()I","result == 2",classes["fix"]),work/"baseline-fix","C.UTF-8",
                                        revision="fix",receipts=cache,env=ENV,resume=True)
        assert old_again["receiptId"]==ids["baseline","fix"] and old_again["recording"].startswith("reused trace")
        cmd=command("sc.M#encoded()I","result == 2",classes["fix"])
        code,_,why=startup_facts.run_step(cmd,["--observed-initializer","sc.Encoded","--observed-runtime",'{"charsetLocale":"C.UTF-8"}',
                                              "--cache",str(work/"verdict-cache")],work/"cache-guard",ENV)
        assert code and "claim's key does not hold an observation" in why, why
        engine = cmd.index("--engine") + 1
        cmd[engine] = "jbmc"
        code,_,why=startup_facts.run_step(cmd,["--observed-initializer","sc.Encoded","--observed-runtime",'{"charsetLocale":"C.UTF-8"}'],
                                          work/"jbmc-boundary",ENV)
        assert code and "--engine native" in why, why
        report={"rows":rows,"restoredOriginalReceipt":old_again["receiptId"],"verdictCache":"refused by the original proof-cache guard",
                "jbmc":"the backend refused a native startup premise"}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(args.output,"w",compression=ZIP_DEFLATED) as z:
            z.writestr("scorecard.json",json.dumps(report,indent=2)+"\n")
            for p in cache.glob("*.json"):z.write(p,"receipts/"+p.name)
    print("both original sides replayed cold, warm and independently clean before, during and after class replacement")


if __name__=="__main__": main()
