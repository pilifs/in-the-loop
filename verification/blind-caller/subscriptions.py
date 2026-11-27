"""Labelled two-subscription scheduler hop over the two original public reactive deployments."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import parquet_trace as trace
sys.path.insert(0,str(trace.HERE.parent/"generated-observers"))
import campaign
from targets import public_histories, upgrade_replay

OWNER = "trial/SubscriptionHistory"
TICKET = "L"+OWNER+"$Ticket;"
SOURCE = "Lreactor/core/publisher/FluxSink;"
TASK = "L"+OWNER+"$Delivery;"
TAPS = {
    "subscribe":("reactor/core/publisher/Flux#subscribe(Lorg/reactivestreams/Subscriber;)V","1"),
    "register":(OWNER+"#registered("+TICKET+SOURCE+")V","0 1"),
    "dispatch":(OWNER+"#dispatch("+TICKET+SOURCE+TASK+")V","0 1 2"),
    "queue":("java/util/concurrent/ThreadPoolExecutor#execute(Ljava/lang/Runnable;)V","1"),
    "run":(OWNER+"$Delivery#run()V",""),
    "deliver":(OWNER+"#deliver("+TICKET+SOURCE+"Ljava/lang/String;Z)V","0 1"),
    "cancel":("reactor/core/publisher/BaseSubscriber#cancel()V",""),
}


def check(side,root,*,require=True,archive=None):
    jdk = campaign.prepare("466",root)
    manifest = campaign.read(root/(side+".json"))
    rows = manifest["classpath"]
    reg = campaign.read(campaign.HERE/"registrations/466.json")
    changed = {s.split("#")[0].replace(".","/")+"#"+s.split("#")[1] for s in reg["changed"]}
    source = trace.HERE/"spring/SubscriptionHistory.java"
    tests = root/"classes"
    tests.mkdir()
    cp = os.pathsep.join(r["file"] for r in rows)
    subprocess.run([jdk/"bin/javac","-g","-proc:none","-cp",cp,"-d",tests,source],check=True,capture_output=True)
    agent = root/"history.so"
    subprocess.run(["g++","-std=c++17","-O2","-fPIC","-shared","-I"+str(jdk/"include"),"-I"+str(jdk/"include/linux"),trace.AGENT,"-o",agent],check=True)
    logs = root/"trace"
    logs.mkdir()
    config = root/"handoff.tsv"
    config.write_text("directory\t"+str(logs)+"\nlimit\t16384\n"+"".join("prefix\t"+p+"\n" for p in
        ("trial/","org/springframework/","reactor/core/publisher/"))+"test\t"+OWNER+"\n"+
        "".join("changed\t"+s+"\n" for s in sorted(changed))+
        "".join("tap\t"+role+" "+target+" "+slots+"\n" for role,(target,slots) in TAPS.items()))
    command = [jdk/"bin/java","-Xmx384m","-Duser.timezone=UTC","-cp",str(tests)+os.pathsep+cp,"trial.SubscriptionHistory"]
    plain = subprocess.run(command,check=True,text=True,capture_output=True,timeout=30).stdout.splitlines()
    traced = subprocess.run(command,env={**os.environ,"JAVA_TOOL_OPTIONS":"-agentpath:"+str(agent)+"="+str(config)
                +" -Xlog:class+load=info:file="+str(logs/"%p.loads")},check=True,text=True,capture_output=True,timeout=50).stdout.splitlines()
    public = [line for line in plain if line.startswith(("A ","B ","unrelated "))]
    first = ("A [event(same,null), error(org.springframework.web.reactive.function.client.WebClientResponseException,java.lang.NumberFormatException)]"
             if side=="old" else "A [event(same,null), event(last,null), complete]")
    if plain != traced or public != [first,"B [event(same,null), cancel]","unrelated [event(same,null), complete]"]:
        raise ValueError("plain and traced originals must reproduce the complete public signal histories: "+str(public))
    path, = logs.glob("*.events")
    fork = public_histories.read_fork(path,rows,tests,"labelled subscription",manifest["commit"],manifest["jdkReleaseSha256"],17)
    decl = {k:v[0] for k,v in TAPS.items()}
    with zipfile.ZipFile(jdk/"jmods/java.base.jmod") as boot:
        for role, method in decl.items():
            owner = method.partition("#")[0]
            matches = [c for c in fork["classes"].values() if c["owner"]==owner]
            if len(matches)!=1:
                raise ValueError("no unique loaded handoff owner for "+role)
            binding, = matches
            if owner.startswith("java/"):
                if binding["definingLoader"]!=0 or hashlib.sha256(boot.read("classes/"+owner+".class")).hexdigest()!=binding["classSha256"]:
                    raise ValueError("worker executor differs from the original JDK")
            elif not (binding["upstreamTest"] if owner.startswith("trial/") else binding["originalProvider"]):
                raise ValueError("unbound subscription action "+role)
    measured = public_histories.handoffs(fork,decl,changed)
    accepted = [h for h in measured["hits"] if h["status"]=="attributed"]
    unrelated = [h for h in measured["hits"] if h["status"]=="unattributed"]
    print(side,public,"registered",len(measured["registered"]),"attributed",len(accepted),"unattributed",len(unrelated),flush=True)
    if require and (fork["stop"] or len(measured["registered"]) != 3 or len({h["ticket"] for h in accepted}) != 2
            or len({h["worker"] for h in measured["hits"]}) != 1 or not unrelated or not measured["cancelled"]):
        raise ValueError("incomplete original subscription or detached worker evidence")
    if not accepted:
        return measured
    withheld = accepted[0]["task"]
    reduced = public_histories.handoffs(fork,decl,changed,withhold={withheld})
    if (any(h["status"]=="attributed" and h["task"]==withheld for h in reduced["hits"])
            or [h for h in measured["hits"] if h["task"]!=withheld] != [h for h in reduced["hits"] if h["task"]!=withheld]):
        raise ValueError("unlinked tasks received causal credit or an independent task lost its edge")
    fork.pop("sequence")
    campaign.write(root/"subscriptions.json",{"scope":"labelled local scheduler hop on original libraries","plain":plain,"traced":traced,
                   "publicClassSha256":upgrade_replay.sha(tests/"trial/SubscriptionHistory.class"),"sourceSha256":upgrade_replay.sha(source),
                   "jdk":str(jdk),"orderedDeployment":manifest,"declarations":decl,"changed":sorted(changed),"fork":fork,
                   "qualification":measured,"removedQueueEvidence":{"task":withheld,"result":reduced}})
    campaign.pack(root,[root/"subscriptions.json",config,*logs.iterdir()],archive or trace.HERE/("subscriptions-"+side+".zip"))
    return measured


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("side",choices=("old","new"))
    args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix="original-subscriptions-") as tmp:
        check(args.side,Path(tmp))
