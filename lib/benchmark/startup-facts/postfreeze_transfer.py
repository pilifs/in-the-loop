"""Repeat exactly the histories stopped by the first frozen transfer and retain the new producer identity."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from charset import JDK, OBSERVER, ROOT
from freeze import RECORD, files
from transfers import compile_java, configuration, spring, timing


def argv_control(work):
    classes = work / "arguments"
    sources = [*sorted(OBSERVER.glob("*.java")), Path(__file__).with_name("StartupArguments.java")]
    compile_java(JDK, classes, sources)
    inputs = ["", '{"values":["red","blue"]}', "two words", "a'b\"c", "line\none", "\ue000", "ends in a space "]
    expected = "".join(str(len(s)) + ":" + "".join(str(ord(c)) + "," for c in s) + "|" for s in inputs)
    subject = ["-XX:-UsePerfData", "-cp", str(classes)]
    main = ["StartupArguments", *inputs]
    trace = work / "arguments.json"
    environment = {"LANG":"C.UTF-8","LC_ALL":"C.UTF-8"}
    commands = [[*subject,*main], ["-XX:-UsePerfData","-cp",str(classes),"StartupTrace",str(trace),
                "StartupArguments#units([Ljava/lang/String;)Ljava/lang/String;",*subject,"--main",*main]]
    for command in commands:
        proc = subprocess.run([JDK/"bin/java",*command], env=environment, capture_output=True, timeout=30, check=True)
        if proc.stdout.decode().removesuffix("\n") != expected:
            raise ValueError("launcher changed one or more UTF-16 arguments")
    return {"arguments":len(inputs), "ordinaryAndInstrumented":"identical UTF-16 units", "projection":expected}


def validate_configuration(doc):
    for row in doc["rows"]:
        profiles = {p["launch"]:p["startup"] for p in row["profiles"]}
        if profiles["default"]["status"] != "observed":
            raise ValueError("ordinary Configuration holder did not complete: " + str(profiles["default"]))
        broken = profiles["own-invalid"]
        failure = broken.get("failure") or {}
        if (not broken.get("ordinaryParity") or broken["reusable"] or failure.get("normalReturn") is not False or
                not any(e["type"]=="java.lang.IllegalArgumentException" and "#parseLookups" in e["site"] for e in failure["exceptions"]) or
                not any(e.get("present") is True for e in failure["partialEvents"])):
            raise ValueError("missing failed Configuration read: " + str(broken))
        if "inherited defaults" not in profiles["inherited-invalid"]["reason"]:
            raise ValueError("inherited table did not retain its named refusal")


def validate_spring(doc):
    for row in doc["rows"]:
        if row["metadataRetry"] != "verified":
            raise ValueError(str(row["gap"]))
        capture = row["memberCapture"]["capture"]
        field, = capture["fields"]
        enumeration, = [e for e in capture["events"] if e["operation"].startswith("getDeclaredMethods(")]
        candidates = enumeration["members"]
        chosen, = [c for c in candidates if c["alias"] == field["alias"]]
        if (chosen["descriptor"] != field["member"]["descriptor"] or chosen["modifiers"] & 0x40 or
                not any(c["modifiers"] & 0x40 and c["alias"] != chosen["alias"] for c in candidates) or
                not any(i.startswith("startup-method:") for i in row["consumed"])):
            raise ValueError("returned array did not identify the non-bridge method used by the native checker")


def validate_timing(doc):
    missing = [r for r in doc["rows"] if r.get("profile")=="absent"]
    if len(missing) != 2: raise ValueError("missing either original JavaParser deployment")
    for row in missing:
        failed = row.get("failure") or {}
        if (not row.get("ordinaryParity") or row["reusable"] or failed.get("normalReturn") is not False or
                not any(e["type"]=="java.lang.NullPointerException" for e in failed["exceptions"]) or
                not any(e.get("present") is False for e in failed["partialEvents"])):
            raise ValueError("missing original null-property evidence: " + str(row))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case",choices=("configuration","spring","timing"))
    ap.add_argument("--output",type=Path,required=True)
    args = ap.parse_args()
    first = hashlib.sha256(RECORD.read_bytes()).hexdigest()
    first_archive = RECORD.parent / ("transfer-" + args.case + ".zip")
    collector = json.loads((RECORD.parent/"collector.json").read_bytes())
    expected = {Path(o["path"]).name:o["sha256"] for j in collector["jobs"] if j["status"]=="passed" for o in j["outputs"]}
    if hashlib.sha256(first_archive.read_bytes()).hexdigest() != expected[first_archive.name]:
        raise ValueError("first transfer archive differs from its collector receipt")
    with ZipFile(first_archive) as z:
        baseline=json.loads(z.read("scorecard.json"))
    if baseline["frozenProducer"] != first: raise ValueError("the first attempt used a different producer")
    current = hashlib.sha256(json.dumps(files(),sort_keys=True,separators=(",",":")).encode()).hexdigest()
    scratch = Path(os.environ.get("TMPDIR") or Path.home()/".cache/in-the-loop/agent-tmp")
    if scratch==Path("/tmp") or Path("/tmp") in scratch.parents:
        scratch=Path.home()/".cache/in-the-loop/agent-tmp"
    scratch.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="postfreeze-startup-",dir=scratch) as directory:
        work=Path(directory)
        measure,validate={"spring":(spring,validate_spring),"configuration":(configuration,validate_configuration),
                          "timing":(timing,validate_timing)}[args.case]
        result=measure(work)
        validate(result)
        for previous,current_row in zip(baseline["rows"],result["rows"],strict=True):
            if previous["revision"] != current_row["revision"]: raise ValueError("a transfer changed revision")
            if args.case=="configuration":
                for a,b in zip(previous["profiles"],current_row["profiles"],strict=True):
                    if a["cases"]!=b["cases"] or a["startup"]["ordinary"]!=b["startup"]["ordinary"]:
                        raise ValueError("the original configuration histories changed")
            elif args.case=="spring":
                if previous["public"]!=current_row["public"] or previous["observedDeclaringClassSha256"]!=current_row["observedDeclaringClassSha256"]:
                    raise ValueError("the original generic observations or declaration changed")
            elif previous.get("ordinary",previous.get("actual")) != current_row.get("ordinary",current_row.get("actual")):
                raise ValueError("the original timing observations changed")
        if args.case=="configuration":result["argumentControl"]=argv_control(work)
        result.update(attempt="post-freeze recovery",firstFrozenProducer=first,currentSourceDigest=current)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(args.output,"w",compression=ZIP_DEFLATED) as archive:
            archive.writestr("scorecard.json",json.dumps(result,indent=2)+"\n")
    print(args.case,"post-freeze observations qualified")


if __name__=="__main__":
    main()
