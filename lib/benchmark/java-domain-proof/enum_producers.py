"""Check the earlier reader's byte decoder with its Utf8 startup recorded, and resolve enum pairs directly."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

from companions import HERE, ROOT, SHA, document, invocation, materialize, proof, runtime_jdk


def run(out, physical_only):
    folder, = (ROOT / "examples").glob("364-*")
    jdk = Path(runtime_jdk.home("21"))
    for side in ("parent","fix"):
        dest=out/side
        dest.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="enum-producers-") as tmp:
            work=Path(tmp); jars,binding=materialize(folder,side,work)
            classes=work/"classes";classes.mkdir()
            cp=os.pathsep.join(map(str,[classes,*jars]))
            env=dict(os.environ,JAVA_HOME=str(jdk),JVMCONTRACT_JAR_RELEASE="21",PATH=str(jdk/"bin")+os.pathsep+os.defpath)
            subprocess.run([jdk/"bin/javac","-J-Djava.io.tmpdir="+tmp,"-g","-parameters","-d",classes,"-cp",cp,
                            HERE/"EnumActions.java",HERE/"ReaderFacts.java"],cwd=work,env=env,check=True)
            jvm=invocation([jdk/"bin/java","-Djava.io.tmpdir="+tmp,"-cp",cp,"campaign.EnumActions",side],
                           "physical",dest,work,env)
            if jvm["exit"]:
                raise ValueError(f"{side}: enum actions differ on the original JVM")
            if physical_only:
                continue
            checker=Path(os.environ["JVMCONTRACT"]).resolve()
            report={"revision":binding["revision"],"binding":binding,"checker":SHA(checker),
                    "source":os.environ["VERIFY_SOURCE_COMMIT"],"jvm":jvm,"proofs":{}}
            for label,method,guard,roots in [
                ("one-byte-utf8","campaign.ReaderFacts#oneByte","wire >= 0 && wire <= 2",["org.apache.avro.util.Utf8"]),
                ("enum-ordinary","campaign.EnumActions#renamed","code >= 0 && code < 4",[]),
                ("enum-recorded","campaign.EnumActions#renamed","code >= 0 && code < 4",["org.apache.avro.Schema","org.apache.avro.generic.GenericData"]),
                ("different-recorded","campaign.EnumActions#rejected","code >= 0 && code < 4",["org.apache.avro.Schema","org.apache.avro.generic.GenericData"])]:
                report["proofs"][label]=proof(checker,classes,jars,work,env,dest,method,label,guard,roots=roots)
                document(dest/"measurement.json",report)


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--physical-only",action="store_true")
    a=p.parse_args()
    run(a.output.resolve(),a.physical_only)
