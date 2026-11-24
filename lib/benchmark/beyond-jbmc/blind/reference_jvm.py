"""Exercise a proposed reference on both unmodified JVM graphs before sealing the independent questions."""
import argparse
import json
from pathlib import Path
from evaluate_panel import matched_namespace, BASE, REFS, scratch, verify, digest, encoded
from references import DOCKET


def exercise(slot):
    if DOCKET.exists():
        raise ValueError("the reference docket is already closed")
    checker,_=verify()
    ref=REFS/slot
    pair=BASE/slot/"packet"
    with scratch(prefix="reference-physical-") as tmp:
        out=Path(tmp)
        rc=matched_namespace(pair,ref,out,checker,True)
        file=out/"worker.json"
        record=json.loads(file.read_bytes()) if file.exists() else {"status":"isolated JVM failed"}
        data={**record,"exit":rc,"packetSha256":digest(pair/"inputs.json"),
              "sourceSha256":{p.name:digest(p) for p in ref.glob("*.java")}}
        if data["status"]!="original JVM control passed":
            for f in ("process.log","physical.stderr"):
                if (out/f).exists():data[f]=(out/f).read_text(errors="replace")[-1800:]
        (ref/"original-jvm.json").write_bytes(encoded(data))
        print(slot,data["status"],data.get("originalJvm",{}).get("rows",[]),flush=True)


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("slots",nargs="+",choices=[f"{i:02}" for i in range(1,17)])
    for slot in cli.parse_args().slots:exercise(slot)
