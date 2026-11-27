"""Challenge revision and loader admission independently of final public values."""
import argparse
import json
from pathlib import Path
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from charset import IO, SMALL, compile_to, command, ENV, sha, startup_facts


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path,required=True);args=ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="startup-binding-") as tmp:
        work=Path(tmp);receipts=work/"receipts"
        classes=work/"small";compile_to(classes,sorted(SMALL.glob("*.java")))
        cmd=command("sc.M#encoded()I","result == 1",classes)
        first=startup_facts.recover(cmd,work/"first","C",receipts=receipts,env=ENV,revision="release-A")
        assert first["retry"]=="verified",first
        root=first["root"];id_=first["receiptId"]
        saved=json.loads((receipts/(id_+".json")).read_bytes())
        assert saved["loader"]=={"defining":"jdk.internal.loader.ClassLoaders$AppClassLoader","parent":"jdk.internal.loader.ClassLoaders$PlatformClassLoader","system":True}
        def crossed(label,cmd,root,other,expected):
            runtime={"charsetLocale":"C","startupRevision":other,"expectedCharsetReceipt":expected,"charsetReceiptDirectory":str(receipts)}
            code,_,reason=startup_facts.run_step(cmd,["--observed-initializer",root,"--observed-runtime",json.dumps(runtime)],work/label,ENV)
            assert code and "binding changed" in reason,reason
            return reason.strip()
        logical=crossed("same-bytes-other-revision",cmd,root,"release-B",id_)
        old,new=[json.loads((IO/k/"prepared.json").read_bytes()) for k in ("old","new")]
        for v in [old,new]:assert sha(Path(v["classpath"][0]["file"]).read_bytes())==v["classpath"][0]["sha256"]
        original=work/"original";compile_to(original,[IO/"UpgradeProbe.java"],old["classpath"][0]["file"])
        def check(v):
            return command("UpgradeProbe#rewind()Z","result == true",original,v["classpath"][0]["file"])
        io=startup_facts.recover(check(old),work/"old","C",receipts=receipts,env=ENV,revision=old["commit"])
        assert io["receiptId"] and io["executed"]==[],io
        reversed_side=crossed("other-original",check(new),io["root"],new["commit"],io["receiptId"])
        result={"sameOriginalBytesDifferentRevision":logical,"otherCommonsIoDeployment":reversed_side,"loader":saved["loader"],
                "smallReceipt":id_,"ioReceipt":io["receiptId"],"oldCommit":old["commit"],"fixCommit":new["commit"]}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(args.output,"w",compression=ZIP_DEFLATED) as z:
            z.writestr("scorecard.json",json.dumps(result,indent=2)+"\n")
            for p in receipts.glob("*.json"):z.write(p,"receipts/"+p.name)
        print("both crossed revision receipts were rejected")


if __name__=="__main__":main()
