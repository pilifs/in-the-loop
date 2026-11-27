"""Qualify a registered file or local-JAR Properties.load history on its original JVM.

The manifest supplies jdk, classpath, main, boundary and cwd. resourceClasspath names
the loader's ordered JARs when it differs from the main classpath. files names ordinary
fixtures, including expected absences. No observed path grants permission to read a file.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile

from targets.startup_facts import write_report


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    if not path.exists():
        return None
    if path.is_file():
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    entries = [(p.relative_to(path).as_posix(), identity(p)) for p in sorted(path.rglob("*")) if p.is_file()]
    return sha(json.dumps(entries, separators=(",", ":")).encode())


def check_reads(events, providers, files, directory):
    """Bind only actual consumed bytes/code units, in the original loader and at the observed boundary."""
    selected = []
    for event in events:
        op = event["operation"]
        source = event if op == "lookup" else event.get("source", {})
        raw = None
        if source.get("api") == "Class.getResourceAsStream":
            if source["loaderClass"] not in ("java.net.URLClassLoader", "jdk.internal.loader.ClassLoaders$AppClassLoader"):
                raise ValueError("unqualified resource loader " + source["loaderClass"])
            if source.get("delegatesTo") != "jdk.internal.loader.ClassLoaders$PlatformClassLoader":
                raise ValueError("unbound parent resource delegation")
            requested = source["name"]
            name = requested[1:] if requested.startswith("/") else (source["owner"].rpartition(".")[0].replace(".", "/") + "/" + requested).lstrip("/")
            if any(part in ("", ".", "..") for part in name.split("/")) or "\\" in name:
                raise ValueError("unsupported noncanonical JAR resource name")
            matches = []
            for path in providers:
                if path.is_dir():
                    candidate = path / name
                    if candidate.resolve().is_relative_to(path) and candidate.is_file():
                        if candidate.stat().st_size > 1048576: raise ValueError("resource exceeds recording bound")
                        matches.append((path, candidate.read_bytes()))
                else:
                    with ZipFile(path) as jar:
                        entries = [i for i in jar.infolist() if i.filename == name]
                        if len(entries) > 1:
                            raise ValueError("duplicate entry in selected JAR")
                        if entries:
                            if entries[0].file_size > 1048576: raise ValueError("resource exceeds recording bound")
                            matches.append((path, jar.read(entries[0])))
            if not matches and op == "lookup" and event.get("present") is False:
                continue
            if not matches or source.get("entry") != name or Path(source.get("archive","")).resolve() != matches[0][0]:
                raise ValueError("resource origin differs from the registered loader order")
            raw = matches[0][1]
            selected.append({"entry":name,"selected":str(matches[0][0]),"sha256":sha(raw),"matchingProviders":len(matches)})
        elif source.get("api") == "FileInputStream" or op == "open":
            path = (directory / (source.get("path") if op != "open" else event["path"])).resolve()
            if path not in files:
                raise ValueError("original process accessed an unregistered file")
            if op == "open":
                if path.exists() or event["threw"] != "java.io.FileNotFoundException":
                    raise ValueError("file absence or failure differs")
                selected.append({"path":str(path),"present":False})
                continue
            if path.stat().st_size > 1048576:
                raise ValueError("fixture exceeds recording bound")
            raw = path.read_bytes()
            selected.append({"path":str(path),"present":True,"sha256":sha(raw)})
        if op == "load":
            if raw is None:
                raise ValueError("load lacks its original bound source")
            if event["descriptor"] == "(Ljava/io/InputStream;)V" and event["decoder"] == "ISO-8859-1":
                data = raw
                unit_bytes = 1
            elif event["descriptor"] == "(Ljava/io/Reader;)V" and event["decoder"] == "UTF-8":
                data = raw.decode("utf-8",errors="replace").encode("utf-16-be")
                unit_bytes = 2
            else:
                raise ValueError("unsupported parser or Reader decoder")
            size = event["units"] * unit_bytes
            if size > len(data) or event["consumedSha256"] != sha(data[:size]) or (event["threw"] is None or event["eof"]) and size != len(data):
                raise ValueError("bytes actually read differ from the bound source")
        elif op not in ("getProperty","lookup","open"):
            raise ValueError("unsupported properties operation " + op)
    return selected


def capture(manifest, tools, work, *, prepare=None):
    """An optional evaluator prelude restores a labelled fixture before each independent launch."""
    cwd=Path(manifest["cwd"]).resolve()
    jdk=Path(manifest["jdk"]).resolve()
    cp=[Path(p).resolve() for p in manifest["classpath"]]
    providers=[Path(p).resolve() for p in manifest.get("resourceClasspath",cp)]
    files=[(cwd/p).resolve() for p in manifest.get("files",[])]
    bound=list(dict.fromkeys([*cp,*providers,*files]))
    def identities():
        return [{"path":str(p),"sha256":identity(p)} for p in bound]
    work=Path(work);work.mkdir(parents=True,exist_ok=True)
    options=["-XX:-UsePerfData",*manifest.get("options",[]),"-cp",os.pathsep.join(map(str,cp))]
    subject=manifest["main"]
    results=[]
    for instrumented in (False,True):
        if prepare is not None: prepare()
        before=identities()
        command=[jdk/"bin/java",*options,*subject]
        if instrumented:
            trace=work/"reads.json"
            command=[jdk/"bin/java","-XX:-UsePerfData","-cp",tools,"StartupTrace",trace,manifest["boundary"],"--properties",*options,"--main",*subject]
        proc=subprocess.run(command,cwd=cwd,env=manifest.get("environment",{}),capture_output=True,timeout=90)
        if proc.returncode:
            raise ValueError("properties observation failed: "+proc.stderr.decode(errors="replace")[-1500:])
        after=identities()
        differences = [(a,b) for a,b in zip(before,after) if a!=b]
        replacement = manifest.get("labelledReplacement")
        if replacement:
            expected = [({"path":replacement["path"],"sha256":replacement["beforeSha256"]},
                         {"path":replacement["path"],"sha256":replacement["afterSha256"]})]
            if differences != expected:
                raise ValueError("labelled replacement did not change exactly the declared provider")
        elif differences:
            raise ValueError("declared source changed during the observation")
        results.append((before,after,proc.stdout))
    if results[0] != results[1]:
        raise ValueError("ordinary and instrumented inputs, final artifacts or public outputs differ")
    doc=json.loads(trace.read_bytes())
    if doc.get("schema")!="jvm-startup-trace/v1" or doc.get("boundary")!=manifest["boundary"]:
        raise ValueError("wrong properties read boundary")
    selected=check_reads(doc["events"],providers,files,cwd)
    result={"schema":"jvm-properties-read/v1","boundary":manifest["boundary"],"launch":manifest,
            "orderedArtifactsBefore":before,"orderedArtifactsAfter":after,
            "jdkReleaseSha256":identity(jdk/"release"),"jdkModulesSha256":identity(jdk/"lib/modules"),
            "recorderSha256":identity(Path(tools)/"PropertyLoadTrace.class"),"controllerSha256":identity(Path(tools)/"StartupTrace.class"),
            "ordinaryParity":True,"vmOptions":options,"publicOutputSha256":sha(results[0][2]),"selected":selected,"events":doc["events"],
            "scope":"this original execution and the recorded stream, parser and readback operations"}
    result["id"]=sha(json.dumps(result,sort_keys=True,separators=(",",":")).encode())
    return result,results[0][2]


def compile_recorder(jdk, where):
    src=Path(__file__).resolve().parents[3]/"lib/src/observed"
    where.mkdir()
    subprocess.run([Path(jdk)/"bin/javac","-encoding","UTF-8","-proc:none","-d",where,*sorted(src.glob("*.java"))],check=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("manifest",type=Path)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    manifest=json.loads(args.manifest.read_bytes())
    with tempfile.TemporaryDirectory(prefix="properties-read-") as tmp:
        where=Path(tmp)
        compile_recorder(manifest["jdk"],where/"recorder")
        receipt,_=capture(manifest,where/"recorder",where/"original")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    write_report(args.output,receipt)
    print(receipt["id"],len(receipt["events"]),"observed properties operations")


if __name__=="__main__":
    main()
