"""First-use JAR resources and the two JDK Properties.load APIs on registered originals and controls."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from charset import compile_to, JDK, OBSERVER, ROOT, sha
from targets import property_reads

HERE=Path(__file__).resolve().parent
RESOURCE="org/apache/batik/util/resources/XMLResourceDescriptor.properties"
PARSER="org.apache.batik.css.parser.Parser"


def files(work, tools, classes):
    source=work/"input.properties"
    base=(b"# original comment\nliteral=\xc3\xa9\nescaped=\\u4e2d\ncontinued=first\\\n  second\nduplicate=old\nduplicate=winner\n")
    rows=[]
    for label, data in (("base",base),("comment",base.replace(b"original comment",b"changed comment")),
            ("winning",base.replace(b"winner",b"new")),("malformed",base+b"broken=\\u12G4\n"),("missing",None)):
        if data is None: source.unlink()
        else: source.write_bytes(data)
        for api in ("stream","reader"):
            manifest={"jdk":str(JDK),"classpath":[str(classes)],"cwd":str(work),"files":[source.name],
                      "main":["FilePropertiesHistory",source.name,api],"boundary":"FilePropertiesHistory#read(Ljava/lang/String;Z)Ljava/lang/String;"}
            receipt,out=property_reads.capture(manifest,tools,work/(label+"-"+api))
            actual=out.decode().strip()
            ops=receipt["events"]
            if label=="missing":
                assert actual=="open java.io.FileNotFoundException" and [e["operation"] for e in ops]==["open"],(actual,ops)
            else:
                load,=[e for e in ops if e["operation"]=="load"]
                if label=="malformed":
                    assert actual=="load java.lang.IllegalArgumentException" and load["threw"]=="java.lang.IllegalArgumentException",ops
                else:
                    expect={"literal":"é" if api=="reader" else "Ã©","escaped":"中","continued":"firstsecond","duplicate":"new" if label=="winning" else "winner"}
                    assert actual=="".join(k+"="+v.encode("utf-16-be").hex()+"|" for k,v in expect.items())+"absent=missing|",actual
                    assert load["eof"] and load["parsedEntries"]==4 and sum(e["operation"]=="getProperty" for e in ops)==5
            rows.append({"case":label,"api":api,"public":actual,"receipt":receipt})
    for api in ("reader","stream"):
        baseline,comment,winning=[next(r for r in rows if r["api"]==api and r["case"]==key) for key in ("base","comment","winning")]
        assert baseline["receipt"]["selected"]!=comment["receipt"]["selected"]
        assert baseline["public"]==comment["public"]!=winning["public"]
        assert baseline["receipt"]["events"][0]["parsedSha256"]==comment["receipt"]["events"][0]["parsedSha256"]
        assert baseline["receipt"]["events"][0]["parsedSha256"]!=winning["receipt"]["events"][0]["parsedSha256"]
    return {"rows":rows,"qualification":"observed JDK parsing and exact readbacks; no symbolic claim"}


def batik(work, tools, classes):
    packet=Path.home()/".cache/in-the-loop/beyond-jbmc/panel/evaluation/04/packet"
    prepared=json.loads((packet/"inputs.json").read_bytes())
    rows=[]
    for side in ("old","new"):
        originals=[packet/item["path"] for item in prepared[side]]
        assert [property_reads.identity(p) for p in originals]==[item["sha256"] for item in prepared[side]]
        mutable=work/(side+"-selected.jar")
        changed=work/(side+"-changed.jar")
        with ZipFile(originals[0]) as src, ZipFile(changed,"w") as dst:
            for entry in src.infolist():
                data=src.read(entry)
                if entry.filename==RESOURCE:
                    assert PARSER.encode() in data
                    data=data.replace(PARSER.encode(),b"fixture.ChangedParser")
                dst.writestr(entry,data)
        for mode in ("ordinary","changed","warm","fresh","setter"):
            if mode in ("warm","fresh"):
                providers=[mutable,*originals[1:]]
                replacement=work/(side+"-next.jar")
                def prepare():
                    shutil.copyfile(originals[0],mutable)
                    shutil.copyfile(changed,replacement)
            else:
                providers=[changed if mode=="changed" else originals[0],*originals[1:]]
                replacement="unused"
                prepare=None
            manifest={"jdk":str(JDK),"classpath":[str(classes)],"resourceClasspath":list(map(str,providers)),"cwd":str(work),
                      "main":["BatikPropertyHistory",mode,str(replacement),*map(str,providers)],
                      "boundary":"BatikPropertyHistory#sample()Ljava/lang/String;"}
            if prepare:
                manifest["labelledReplacement"]={"path":str(mutable),"beforeSha256":property_reads.identity(originals[0]),"afterSha256":property_reads.identity(changed)}
            receipt,out=property_reads.capture(manifest,tools,work/(side+mode),prepare=prepare)
            expected="fixture.ExplicitParser" if mode=="setter" else "fixture.ChangedParser" if mode in ("changed","fresh") else PARSER
            assert out.decode().splitlines()==(["primed="+PARSER] if prepare else [])+["value="+expected],out
            events=receipt["events"]
            if mode in ("warm","setter"):
                assert not events,events
            else:
                assert [e["operation"] for e in events]==["lookup","load","getProperty"],events
                assert events[1]["eof"] and receipt["selected"][0]["matchingProviders"]==2 and events[2]["valueSha256"]==sha(expected.encode("utf-16-be"))
                assert events[2]["keySha256"]==sha("org.w3c.css.sac.driver".encode("utf-16-be"))
            rows.append({"revision":side,"history":mode,"public":out.decode().splitlines(),"receipt":receipt})
    return {"rows":rows,"pngQuestion":{"status":"open","blocker":"both registered conjuncts reached incomplete unwinding in HashMap.resize",
                  "evidence":"verification/beyond-jbmc/scaffold-first/RESULTS.md"},"caseSpecificInputs":"A public getter, setter and labelled JAR replacement in isolated loaders."}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("case",choices=("file","batik"));ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="qualified-properties-") as tmp:
        work=Path(tmp);tools=work/"tools";classes=work/"classes"
        compile_to(tools,sorted(OBSERVER.glob("*.java")))
        compile_to(classes,[HERE/"FilePropertiesHistory.java",HERE/"BatikPropertyHistory.java"])
        report=(files if args.case=="file" else batik)(work,tools,classes)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(args.output,"w",compression=ZIP_DEFLATED) as archive: archive.writestr("scorecard.json",json.dumps(report,indent=2)+"\n")
        print(args.case,len(report["rows"]),"qualified paired original histories",flush=True)


if __name__=="__main__":main()
