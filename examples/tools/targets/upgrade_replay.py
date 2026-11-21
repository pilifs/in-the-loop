"""Compare a finite set of caller observations on two checked, ordered original JVM classpaths.

The supplied Java observer constructs the real receiver and returns the caller-visible string
or a reviewed encoding of its result. The declared cases carry independent expected observations.
"""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import unquote, urlsplit

from targets import runtime_jar, runtime_jdk, upgrade_claims


LAUNCHER = Path(__file__).with_name("java") / "UpgradeObservation.java"
TRACER = LAUNCHER.with_name("UpgradeTrace.java")
LOAD = re.compile(r"^(?:\[Loaded (\S+) from (file:[^\]]+)\]|.*?\[class,load\]\s+(\S+) source: (file:\S+))$")
MARK = "UPGRADE-OBSERVATION "


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_input(path, entry, dependency):
    doc = json.loads(path.read_text())
    files = []
    for item in doc["classpath"]:
        jar = (path.parent / item["file"]).resolve()
        if sha(jar) != item["sha256"]:
            raise ValueError(f"changed classpath artifact {jar.name}")
        files.append(jar)
    hashes = [row["sha256"] for row in doc["classpath"]]
    if not files or dependency not in hashes:
        raise ValueError("upgraded artifact missing from the ordered classpath")
    owner, method, descriptor = runtime_jar.parse_target(entry)
    data = runtime_jar.read_class(files[0], runtime_jar.internal(owner))
    if not data or (method, descriptor) not in runtime_jar.methods(data):
        raise ValueError("the selected method and descriptor must belong to the original client JAR")
    return files, files[hashes.index(dependency)], {"commit": doc["commit"], "sourceSha256": doc["sourceSha256"],
            "callerClassSha256": hashlib.sha256(data).hexdigest(), "classpath": hashes, "dependency": dependency}


def parse_output(text, caller, original, dependency):
    loaded = {}
    for line in text.splitlines():
        if m := LOAD.match(line):
            name, url = (m[1], m[2]) if m[1] else (m[3], m[4])
            loaded.setdefault(name, set()).add(Path(unquote(urlsplit(url).path)).resolve())
    if loaded.get(caller.split("#")[0]) != {original}:
        raise ValueError("the JVM did not load the declared caller from the selected original client JAR")
    operands = sorted(name for name, origins in loaded.items() if origins == {dependency})
    messages = [line[len(MARK):] for line in text.splitlines() if line.startswith(MARK)]
    if len(messages) != 1:
        raise ValueError("the scenario did not produce exactly one return or exception")
    kind, _, value = messages[0].partition(" ")
    if kind == "return":
        observation = {"return": None if value == "-" else base64.b64decode(value,validate=True).decode("utf-16-be","surrogatepass")}
    elif kind == "throw":
        if "UPGRADE-FRAME " + caller.split("(")[0] not in text.splitlines():
            raise ValueError("exception occurred outside the declared original caller")
        observation = {"throws": value}
    else:
        raise ValueError("unknown observation record")
    return observation, operands


def evaluate(specfile, before, after, probe, jdk, dependencies, timeout):
    spec = json.loads(specfile.read_text())
    domain = spec["cases"]
    if (not domain or len({tuple(c["args"]) for c in domain}) != len(domain)
            or any(not isinstance(c["args"],list) or any(x is not None and not isinstance(x,str) for x in c["args"]) for c in domain)):
        raise ValueError("the finite domain needs distinct lists of string or null arguments")
    for case in domain:
        expected = case["expected"]
        if (not isinstance(expected,dict) or set(expected) not in ({"return"},{"throws"}) or
                any(value is not None and not isinstance(value,str) for value in expected.values())):
            raise ValueError("every input needs an independently specified return or exception")
    caller = spec["entry"]
    prepared = {side: check_input(path, caller, digest) for side,path,digest in zip(("old","new"),(before,after),dependencies)}
    if prepared["old"][2]["sourceSha256"] != prepared["new"][2]["sourceSha256"]:
        raise ValueError("the selected caller source differs between dependency revisions")
    if dependencies[0] == dependencies[1]:
        raise ValueError("the dependency digests identify the same bytes")
    report = {"entry":caller,"observer":spec["observer"],"domainBasis":spec["basis"],"cases":domain,
              "probeSha256":sha(probe),"launcherSha256":sha(LAUNCHER),"tracerSha256":sha(TRACER),"jdk":runtime_jdk.identity(jdk)["release"],
              "sides":{s:v[2] for s,v in prepared.items()},"status":"open"}
    owner, method, descriptor = runtime_jar.parse_target(caller)
    start=time.monotonic()
    with tempfile.TemporaryDirectory(prefix="upgrade-case-") as t:
        temp=Path(t)
        env={"PATH":str(jdk/"bin")+":/usr/bin:/bin","HOME":t,"LANG":"C.UTF-8","LC_ALL":"C.UTF-8","TZ":"UTC","TMPDIR":t}
        cp=lambda files:os.pathsep.join(str(x) for x in files)
        output = temp / "probe"
        output.mkdir()
        tools = [jdk/"lib/tools.jar"] if (jdk/"lib/tools.jar").is_file() else []
        proc=subprocess.run([str(jdk/"bin/javac"),"-J-Djava.io.tmpdir="+t,"-proc:none","-g","-encoding","UTF-8",
                             "-classpath",cp([*prepared["old"][0],*tools]),"-d",str(output),str(LAUNCHER),str(TRACER),str(probe)],
                             cwd=temp,env=env,capture_output=True,text=True,timeout=timeout)
        if proc.returncode:
            raise ValueError("observer compilation: "+proc.stderr[-1800:])
        main=spec["probeClass"]
        if not re.fullmatch(r"(?:[A-Za-z_$][\w$]*\.)*UpgradeProbe",main):
            raise ValueError("the supplied observer must be named UpgradeProbe")
        probe_file=output/(main.replace(".","/")+".class")
        flags = runtime_jar.method_flags(probe_file.read_bytes(), "observe", "([Ljava/lang/String;)Ljava/lang/String;")
        if flags is None or flags & 0x0009 != 0x0009:
            raise ValueError("the observer must declare public static String observe(String[] args)")
        helper_class=lambda f:f.relative_to(output).as_posix()[:-6]
        compiled=sorted(output.rglob("*.class"))
        if any(helper_class(f) not in ("UpgradeObservation", "UpgradeTrace") and helper_class(f).split("$")[0] != main.replace(".","/") for f in compiled):
            raise ValueError("the observer compiler produced an unrelated class")
        refs=set().union(*(runtime_jar.references(f.read_bytes()) for f in compiled if helper_class(f) not in ("UpgradeObservation", "UpgradeTrace")))
        if (runtime_jar.internal(owner),method,descriptor) not in refs:
            raise ValueError("the compiled observer has no invocation reference to the declared original method")
        methods = upgrade_claims.listing(jdk, [output], main.replace(".", "/"), max(0.01, timeout-(time.monotonic()-start)))
        operand = (runtime_jar.internal(owner), method, descriptor)
        if operand not in methods.get(("observe", "([Ljava/lang/String;)Ljava/lang/String;"), []):
            raise ValueError("observe() must itself invoke the declared original method and descriptor")
        report["originalInvocation"] = owner + "#" + method + descriptor
        report["probeClasses"]={helper_class(f):sha(f) for f in compiled}
        for side,(files,dependency,side_record) in prepared.items():
            if any(runtime_jar.read_class(jar,name) is not None for jar in files for name in report["probeClasses"]):
                raise ValueError("observer classes shadow an input artifact")
            records=[]
            operand_classes=set()
            for index,case in enumerate(domain):
                trials=[]
                for trial in range(2):
                    run_dir = temp / f"{side}-{index}-{trial}"
                    run_dir.mkdir()
                    enc=["-" if x is None else base64.b64encode(x.encode("utf-16-be","surrogatepass")).decode() for x in case["args"]]
                    cmd=[str(jdk/"bin/java"), "-Xmx96m", "-Djava.io.tmpdir="+str(run_dir), "-cp",
                         cp([output,*tools]), "UpgradeTrace", caller, str(jdk), str(run_dir), cp([output,*files]), main,*enc]
                    with subprocess.Popen(cmd, cwd=run_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          start_new_session=True) as child:
                        try:
                            stdout, stderr = child.communicate(timeout=max(0.01, timeout-(time.monotonic()-start)))
                        except subprocess.TimeoutExpired:
                            os.killpg(child.pid, signal.SIGKILL)
                            child.communicate()
                            raise
                    if child.returncode:
                        raise ValueError(f"{side} input {index}: JVM exit {child.returncode}: {stderr.decode(errors='replace')[-500:]}")
                    if "UPGRADE-HIT " + caller not in stderr.decode(errors="replace").splitlines():
                        raise ValueError(f"{side} input {index}: the original caller method was never entered")
                    observation,classes=parse_output(stdout.decode(errors="replace"),caller,files[0],dependency)
                    trials.append(observation)
                    operand_classes.update(classes)
                if trials[0]!=trials[1]:
                    raise ValueError(f"{side} input {index} gave different observations in fresh JVMs")
                records.append({"input":index,"qualifiedMethodEntries":len(trials),"observations":trials})
            if not operand_classes:
                raise ValueError(f"{side} did not load any class from the upgraded artifact")
            side_record.update(trials=records,loadedDependencyClasses=sorted(operand_classes))
        old,new=(report["sides"][k]["trials"] for k in ("old","new"))
        differences=[i for i,(a,b) in enumerate(zip(old,new)) if a["observations"][0]!=b["observations"][0]]
        disagreements=[i for i,(a,c) in enumerate(zip(old,domain)) if a["observations"][0]!=c["expected"]]
        report.update(differences=differences,oldOracleDisagreements=disagreements,
                      status="open" if disagreements else "changed" if differences else "preserved",
                      elapsedSeconds=round(time.monotonic()-start,3))
    return report


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("spec","before","after","probe","jdk","output"):
        ap.add_argument("--"+name,type=Path,required=True)
    ap.add_argument("--old-dependency",required=True)
    ap.add_argument("--new-dependency",required=True)
    ap.add_argument("--seconds",type=int,default=120)
    a=ap.parse_args(argv)
    try:
        result=evaluate(a.spec,a.before,a.after,a.probe,a.jdk,(a.old_dependency,a.new_dependency),a.seconds)
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as e:
        result={"status":"open","reason":str(e),"entry":json.loads(a.spec.read_text()).get("entry"),
                "specSha256":sha(a.spec),"probeSha256":sha(a.probe)}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(result["status"],result.get("reason",result.get("entry","")))
    return 0 if result["status"] in ("changed","preserved") else 1
