"""Qualify equal public values with different first-use histories on the original JVM."""
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

from charset import ENV, JDK, command, compile_to, startup_facts


def control(work):
    root = "FirstUseControl$Early"
    classes = work / "classes"
    compile_to(classes, [Path(__file__).with_name("FirstUseControl.java")])
    agent = work / "prime.jar"
    with ZipFile(agent, "w") as archive:
        archive.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\r\nPremain-Class: FirstUseControl\r\n\r\n")
        archive.write(classes / "FirstUseControl.class", "FirstUseControl.class")
    env = {k:v for k,v in ENV.items() if k not in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS")}
    cmd = command(root + "#arity()I", "result == 0", classes)
    runtime = ["--observed-initializer", root, "--observed-runtime", json.dumps({"reflectiveMembers":True})]
    evidence = {}
    for label, selected in (("cold", env), ("alreadyInitialized", dict(env, JAVA_TOOL_OPTIONS=f"-javaagent:{agent}={root}"))):
        public = subprocess.run([JDK/"bin/java","-cp",classes,"FirstUseControl"],env=selected,
                                capture_output=True, text=True, check=True, timeout=30).stdout.splitlines()
        assert public == ["public java.lang.String java.lang.String.trim()", "0"], public
        area = work / label
        code, outcome, reason = startup_facts.run_step(cmd, runtime, area, selected)
        receipts = [json.loads(p.read_bytes()) for p in (area/"startup-receipts").glob("*.json")]
        if label == "cold":
            assert code == 0 and outcome["verdict"] == "verified" and len(receipts)==1, (outcome, reason)
            record = receipts[0]
            boundary = record["startupBoundary"]
            assert boundary == {"alreadyInitializedApplication":[], "rootPreviouslyInitialized":False,"rootInitializedDuring":True}
            consumed = [a["id"] for a in outcome["stated"]["assumptions"] if a.get("id")]
            assert any(record["id"] in item for item in consumed), consumed
        else:
            assert code and not receipts and outcome is None and "fresh application prestate" in reason, (outcome, reason)
            record, = [json.loads(p.read_bytes()) for p in (area/"startup-diagnostics").glob("*.json")]
            boundary = record["startupBoundary"]
            assert (record["schema"]=="jvm-startup-prestate-refusal/v1" and record["usableAsPremise"] is False and
                    root in boundary["alreadyInitializedApplication"] and boundary["rootPreviouslyInitialized"] is True
                    and boundary["rootInitializedDuring"] is False), record
            consumed = []
        evidence[label] = {"originalMember":public[0], "originalPublicArity":int(public[1]), "record":record, "consumed":consumed,
                           "nativeVerdict":outcome["verdict"] if outcome else "refused"}
    return evidence
