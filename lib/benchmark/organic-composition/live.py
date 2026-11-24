"""Run the frozen original-entry tracer with an additional case-specific JDI observer."""
import base64
from functools import cache
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from freeze import files
from plan_run import HERE, JDK, ROOT
from prepare import sha
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_inventory, change_plan, runtime_jar, upgrade_claims, upgrade_replay


def frozen_cold(archive):
    """Check the recorded executable and live runner inputs without rebuilding an unused checker."""
    pin = json.loads((HERE / "freeze.json").read_bytes())
    if (pin["files"] != {str(p): sha(ROOT / p) for p in files()} or pin["jdk"] != change_inventory.jdk_binding(JDK)
            or pin["runnerIdentity"] != change_plan.runner_identity()):
        raise ValueError("different frozen runner or JDK")
    with zipfile.ZipFile(archive) as original:
        plan = json.loads(original.read("cold.json"))
    if (plan["executionState"] != "complete" or plan["tools"] !=
            {"comparator": pin["checkerSha256"], "jvmRunner": pin["runnerIdentity"]}):
        raise ValueError("different frozen public plan or executable")
    return plan


def compile_tracer(case, work, jars):
    original = upgrade_replay.TRACER.read_text()
    source = original
    hooks = {
        "        if (type.name().equals(owner)) {": "        CaseFrames.install(vm, type);\n        if (type.name().equals(owner)) {",
        "            watched.add(owner);": "            watched.add(owner);\n            watched.addAll(CaseFrames.watched());",
        "                        String id = raised.thread()": "                        CaseFrames.thrown(raised);\n                        String id = raised.thread()",
        '                        if (purpose.equals("checked")': '                        if (purpose.startsWith("case/")) { CaseFrames.hit(point, purpose.substring(5)); continue; }\n                        if (purpose.equals("checked")',
        '"-Xmx384m -Duser.timezone=UTC -Duser.language=en -Duser.country=US "': '"-Xmx384m -Duser.timezone=" + System.getProperty("case.zone", "UTC") + " -Duser.language=en -Duser.country=US "'}
    for old, new in hooks.items():
        if original.count(old) != 1:
            raise ValueError("frozen JDI hook changed")
        source = source.replace(old, new)
    tracer = work / "UpgradeTrace.java"
    tracer.write_text(source)
    classes = work / "classes"
    classes.mkdir()
    subprocess.run([JDK / "bin/javac", "-g", "-proc:none", "-encoding", "UTF-8", "-cp", os.pathsep.join(map(str, jars)),
                    "-d", classes, tracer, Path(__file__).with_name("FrameValues.java"), case / "CaseFrames.java", case / "UpgradeProbe.java",
                    upgrade_replay.LAUNCHER, upgrade_replay.LOOKUP], check=True)
    return classes, {"frozenTrace": sha(upgrade_replay.TRACER), "extendedTrace": sha(tracer),
                     "frameValues": sha(Path(__file__).with_name("FrameValues.java")), "caseFrames": sha(case / "CaseFrames.java")}


@cache
def public_sites(classes, probe_sha, entry):
    bytecode = upgrade_claims.disassemble(JDK, [classes], "UpgradeProbe", 10)
    owner, method, desc = runtime_jar.parse_target(entry)
    sites = [str(pc) for m, pc, target in upgrade_claims.invocation_sites(bytecode, "UpgradeProbe")
             if m == ("observe", "([Ljava/lang/String;)Ljava/lang/String;") and target == (owner.replace(".", "/"), method, desc)]
    if not sites:
        raise ValueError("the supplied observer has no direct call to the original entry")
    return ",".join(sites)


def observe(classes, jars, entry, args, output, config, *, zone="UTC", exceptions=""):
    output.mkdir()
    sites = public_sites(classes, sha(classes / "UpgradeProbe.class"), entry)
    encoded = [base64.b64encode(a.encode("utf-16-be")).decode() for a in args]
    command = [JDK / "bin/java", "-Dcase.config=" + str(config), "-Dcase.zone=" + zone, "-cp", classes, "UpgradeTrace",
               entry, JDK, output, os.pathsep.join(map(str, [classes, *jars])), sites, "UpgradeProbe", exceptions, *encoded]
    run = subprocess.run(command, capture_output=True, text=True, timeout=55)
    marks = [line.split("\t")[1:] for line in run.stderr.splitlines() if line.startswith("CASE\t")]
    if run.returncode:
        raise ValueError(run.stderr.split("Exception in thread \"main\" ")[-1].splitlines()[0])
    value = upgrade_replay.typed_outcome((output / "observation.txt").read_text().splitlines())
    call, = [line.split(" ", 1)[1] for line in run.stderr.splitlines() if line.startswith("UPGRADE-CALL-SITE ")]
    return value, marks, call, upgrade_replay.class_origins(run.stdout)


def member_site(jar, site):
    entry, offset, code, pool = site
    owner, method, desc = runtime_jar.parse_target(entry)
    data = runtime_jar.read_class(jar, owner.replace(".", "/"))
    resolved = runtime_jar.member_at_code_index(data, method, desc, int(offset), code_sha256=code, pool_sha256=pool)
    if not resolved:
        raise ValueError("original bytecode differs at " + entry)
    return resolved
