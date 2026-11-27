"""Separate original Spring test coverage, the same-thread product call, and the labelled scheduler hop."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import parquet_trace as trace
sys.path.insert(0, str(trace.HERE.parent / "generated-observers"))
import campaign
from targets import change_inventory, public_histories, runtime_jar, upgrade_replay

OWNER = "org/springframework/http/codec/ServerSentEventHttpMessageReaderTests"
READER = "org/springframework/http/codec/ServerSentEventHttpMessageReader"
SOURCE = "spring-web/src/test/java/" + OWNER + ".java"


def actual_caller():
    archive = trace.HERE / "466-development.zip"
    witnessed = {"old": [], "new": []}
    with zipfile.ZipFile(archive) as source:
        for name in source.namelist():
            if not name.startswith("receipts/") or not name.endswith(".json"):
                continue
            receipt = json.loads(source.read(name))
            for side, data in receipt["sides"].items():
                for trial in data["trials"]:
                    for repetition, events in enumerate(trial["changedWithinHistory"]):
                        for hit in events:
                            stack = hit["stack"]
                            if not (stack[0].startswith(READER.replace("/",".")+"#buildEvent(") and
                                    any(s.startswith("reactor.core.publisher.Flux#blockLast(") for s in stack) and
                                    any(s.startswith("UpgradeProbe#observe(") for s in stack) and
                                    not any("#bodyToFlux(" in s for s in stack)):
                                continue
                            caller = trial["entryInvocations"][repetition]
                            witnessed[side].append({"input":trial["input"],"repeat":repetition,"publicCall":caller,
                                "laterStack":stack,"artifactSha256":hit["artifactSha256"],"receipt":name})
        if not all(witnessed.values()):
            raise ValueError("the original caller did not demonstrate the later same-thread operation on each side")
    return {"source":upgrade_replay.sha(archive),"sides":witnessed}


def original(work, side, role, test_source, classes, jdk, agent):
    base = Path.home() / ".cache/in-the-loop/spring-pr-links-o01-o20"
    cp = (base/("artifacts/O09-"+role)/"spring-web.testRuntimeClasspath.txt").read_text().strip()
    files = [Path(p) for p in cp.split(os.pathsep)]
    if len(files) != 202:
        raise ValueError("original Spring test classpath changed")
    graph = [{"file":str(p), "sha256":change_inventory.file_digest(p)} for p in files]
    manifest = campaign.read(work / (side+".json"))
    outer = "org/springframework/web/reactive/function/client/WebClient$ResponseSpec"
    expected = campaign.read(campaign.HERE/"registrations/466.json")
    changed = [x.partition("#")[0].replace(".","/")+"#"+x.partition("#")[2] for x in expected["changed"]]
    launcher = trace.SETUP / "releases/junit6-console/lib/junit-platform-console-standalone-6.1.2.jar"
    command = [jdk/"bin/java", "-Xmx384m", "-jar", launcher, "execute", "--disable-banner", "--disable-ansi-colors",
               "--details=summary", "--class-path", str(classes)+os.pathsep+cp, "--select-class", OWNER.replace("/",".")]
    directory = work / side
    directory.mkdir()
    logs = directory / "traced"
    logs.mkdir()
    config = directory / "coverage.tsv"
    config.write_text("directory\t"+str(logs)+"\nlimit\t65536\ntest\t"+OWNER+"\nprefix\torg/springframework/\n"
                      +"public\tbodyToFlux(Lorg/springframework/core/ParameterizedTypeReference;)Lreactor/core/publisher/Flux;\n"
                      +"".join("changed\t"+x+"\n" for x in changed))
    outcomes = []
    test_cp_sha = upgrade_replay.sha(launcher)
    for mode in ("plain","traced"):
        reports = directory / (mode+"-junit")
        env = dict(os.environ)
        if mode == "traced":
            env["JAVA_TOOL_OPTIONS"] = "-agentpath:"+str(agent)+"="+str(config)+" -Xlog:class+load=info:file="+str(logs/"%p.loads")
        run = subprocess.run([*command, "--reports-dir", reports], cwd=directory, env=env, capture_output=True, text=True, timeout=60)
        if run.returncode not in (0,1):
            raise ValueError("original Spring test launcher failed: "+run.stderr[-500:])
        (directory/(mode+".log")).write_text(run.stdout+run.stderr)
        outcomes.append(trace.test_rows(reports))
    if outcomes[0] != outcomes[1] or len(outcomes[0]) != 14 or sum(bool(r[2]) for r in outcomes[0]) != int(side=="old"):
        raise ValueError("original Spring per-test outcomes differ between plain and traced launches")
    raw, = logs.glob("*.events")
    fork = public_histories.read_fork(raw,graph,classes,"spring-web",manifest["commit"],manifest["jdkReleaseSha256"],17)
    original_bodies = {}
    for owner in {method.partition("#")[0] for method in changed}:
        for artifact in manifest["classpath"]:
            data = runtime_jar.effective_class(artifact["file"],owner,17)
            if data:
                original_bodies[owner] = hashlib.sha256(data).hexdigest()
                break
    hits = []
    for row in fork.pop("sequence"):
        if row[0] != "hit":
            continue
        frames = [public_histories.method_frame(frame) for frame in row[4:]]
        body = frames[0]
        key = str(body["loader"])+":"+body["member"].partition("#")[0]
        definition = fork["classes"][key]
        if (body["member"] not in changed or not definition["originalProvider"] or
                definition["classSha256"] != original_bodies.get(definition["owner"])):
            raise ValueError("upstream body was not bound to the original spring-web deployment")
        hits.append({"body":body,"testInvocation":row[2],"outerOnStack":any(f["member"].startswith(outer+"#bodyToFlux(")
                         or "#bodyToFlux(" in f["member"] for f in frames)})
    if fork["stop"] or not hits:
        raise ValueError("the original test launch provided no complete body coverage")
    return {"revision":manifest["commit"],"jdkReleaseSha256":manifest["jdkReleaseSha256"],"orderedTestDeployment":graph,
            "testSourceSha256":upgrade_replay.sha(test_source),"testBytecode":upgrade_replay.sha(classes/(OWNER+".class")),
            "launcherSha256":test_cp_sha,"outcomes":outcomes[0],"plainTracedParity":True,
            "numberedProductionClassDigests":original_bodies,"bodyHits":len(hits),"publicEntryOnBodyStack":sum(h["outerOnStack"] for h in hits),"fork":fork}


def run(work):
    jdk = campaign.prepare("466",work)
    agent=work/"coverage.so"
    subprocess.run(["g++","-std=c++17","-O2","-shared","-fPIC","-I"+str(jdk/"include"),"-I"+str(jdk/"include/linux"),
                    trace.AGENT,"-o",agent],check=True)
    tree = Path.home()/".cache/in-the-loop/spring-pr-links-o01-o20/worktrees/O09-fix"
    fixed = campaign.read(work/"new.json")["commit"]
    source = work/"ServerSentEventHttpMessageReaderTests.java"
    source.write_bytes(subprocess.check_output(["git","-C",tree,"show",fixed+":"+SOURCE]))
    answers={"sameThread":actual_caller(),"originalTest":{}}
    base=Path.home()/".cache/in-the-loop/spring-pr-links-o01-o20/artifacts"
    for side, role in (("old","parent"),("new","fix")):
        cp=(base/("O09-"+role)/"spring-web.testRuntimeClasspath.txt").read_text().strip()
        classes=work/(side+"-tests")
        classes.mkdir()
        subprocess.run([jdk/"bin/javac","-proc:none","-g","-parameters","--release","17","-cp",cp,"-d",classes,source],check=True)
        answers["originalTest"][side]=original(work,side,role,source,classes,jdk,agent)
    campaign.write(work/"coverage.json",answers)
    files=[work/"coverage.json",source,*work.glob("*-tests/**/*.class"),*work.glob("*/coverage.tsv"),
           *work.glob("*/*.log"),*work.glob("*/traced/*"),*work.glob("*/*-junit/*.xml")]
    campaign.pack(work,files,trace.HERE/"spring-upstream.zip")
    print({s:(v["bodyHits"],v["publicEntryOnBodyStack"]) for s,v in answers["originalTest"].items()})


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="original-spring-test-") as scratch:
        run(Path(scratch))
