"""Compare a finite set of caller observations on two checked, ordered original JVM classpaths.

The supplied Java observer constructs the real receiver and returns the caller-visible string
or a reviewed encoding of its result. The declared cases carry independent expected observations.
If a JVM throws before the selected method, report the escaping exception and its live call stack
on fresh replays of both revisions. The selected method's result stays open.
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

from targets import runtime_jar, runtime_jdk, upgrade_claims, upgrade_linkage


LAUNCHER = Path(__file__).with_name("java") / "UpgradeObservation.java"
TRACER = LAUNCHER.with_name("UpgradeTrace.java")
LOOKUP = LAUNCHER.with_name("UpgradeClassLookup.java")
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
    binding = {"commit": doc["commit"], "sourceSha256": doc["sourceSha256"],
            "callerClassSha256": hashlib.sha256(data).hexdigest(), "classpath": hashes, "dependency": dependency,
            "preparation": doc.get("scope"), "compiledClasses": doc.get("compiledClasses"), "resources": doc.get("resources")}
    for key in ("operandScope", "declaredDependencyScope", "modulePomSha256"):
        if key in doc:
            binding[key] = doc[key]
    if "frameworkFixtures" in doc:
        fixture = doc["frameworkFixtures"]
        count = fixture["runtimeCount"]
        if (type(count) is not int or not 1 < count < len(files) or dependency not in hashes[1:count]
                or hashes[count] != fixture["testClassesSha256"] or hashes[count] in hashes[:count]
                or doc.get("operandScope") != "runtime" or not doc.get("modulePomSha256")):
            raise ValueError("framework fixtures must follow the original production runtime and operand")
        binding["frameworkFixtures"] = fixture
    return files, files[hashes.index(dependency)], binding


def class_origins(text):
    loaded = {}
    for line in text.splitlines():
        if m := LOAD.match(line):
            name, url = (m[1], m[2]) if m[1] else (m[3], m[4])
            loaded.setdefault(name, set()).add(Path(unquote(urlsplit(url).path)).resolve())
    return loaded


def typed_outcome(records):
    messages = [line[len(MARK):] for line in records if line.startswith(MARK)]
    if len(messages) != 1:
        raise ValueError("the scenario did not produce exactly one return or exception")
    kind, _, value = messages[0].partition(" ")
    if kind == "return":
        return {"return": None if value == "-" else base64.b64decode(value,validate=True).decode("utf-16-be","surrogatepass")}
    if kind == "throw" and value:
        return {"throws": value}
    raise ValueError("unknown observation record")


def parse_output(text, caller, original, dependency, observation_text=None, *, escape=None):
    loaded = class_origins(text)
    if loaded.get(caller.split("#")[0]) != {original}:
        raise ValueError("the JVM did not load the declared caller from the selected original client JAR")
    records = (observation_text if observation_text is not None else text).splitlines()
    outcome = typed_outcome(records)
    if "throws" in outcome and (not escape or escape["entry"] != caller or escape["throws"] != outcome["throws"]):
        raise ValueError("exception occurred outside the declared original caller")
    return outcome, sorted(name for name, origins in loaded.items() if origins == {dependency})


def throw_evidence(debugger_marks, loaded, files, artifact_hashes, dependency, records):
    """Bind the JVM's live throw stack to unambiguous files on this side's ordered classpath."""
    evidence = {"causes": [s.removeprefix("UPGRADE-CAUSE ") for s in records if s.startswith("UPGRADE-CAUSE ")],
                "frames": [], "observerCodeIndex": None}
    last_message = next((s.removeprefix("UPGRADE-LAST-CAUSE ") for s in records if s.startswith("UPGRADE-LAST-CAUSE ")), "-")
    if last_message != "-":
        evidence["lastCauseMessage"] = base64.b64decode(last_message, validate=True).decode("utf-16-be", "surrogatepass")[:500]
    stacks = [s.removeprefix("UPGRADE-THROW-STACK ") for s in debugger_marks if s.startswith("UPGRADE-THROW-STACK ")]
    if len(stacks) != 1:
        return evidence
    events = []
    for line in base64.b64decode(stacks[0], validate=True).decode("utf-8").splitlines():
        if line == "truncated":
            return evidence
        if line == "event":
            events.append({"frames": [], "observerCodeIndex": None})
            continue
        fields = line.split("\t")
        if fields[0] == "observer":
            events[-1]["observerCodeIndex"] = int(fields[1])
            continue
        if fields[0] == "escape":
            events[-1]["escapingMember"] = fields[1]
            continue
        entry, code_index, source_line = fields
        origins = loaded.get(entry.partition("#")[0], set())
        if len(origins) != 1:
            continue
        jar = next(iter(origins))
        if jar not in files:
            continue
        index = files.index(jar)
        events[-1]["frames"].append({"entry": entry, "codeIndex": int(code_index), "sourceLine": int(source_line),
                                     "artifact": "client" if index == 0 else "upgrade" if jar == dependency else "classpath",
                                     "classpathIndex": index, "jarSha256": artifact_hashes[index]})
    if events:
        for event in events:
            for frame in event["frames"]:
                if frame["artifact"] == "client" and frame["entry"] == event.get("escapingMember"):
                    evidence["escapingInvocation"] = {**frame, "observerCodeIndex": event["observerCodeIndex"]}
        # Keep the last attributed throw and show any subsequent propagation of the
        # identical object after those frames unwound. A replacement gets its own stack.
        attributed = [i for i, event in enumerate(events)
                      if any(f["artifact"] in ("client", "upgrade") for f in event["frames"])]
        selected = attributed[-1] if attributed else len(events) - 1
        evidence.update(events[selected])
        evidence["subsequentRethrows"] = events[selected + 1:]
    return evidence


def compare_before_entry(sides, domain):
    comparisons = []
    for old, new, case in zip(sides["old"]["trials"], sides["new"]["trials"], domain):
        if "beforeEntry" not in old and "beforeEntry" not in new:
            continue
        result = {"input": old["input"], "status": "unqualified"}
        observed = new.get("beforeEntry", [])
        if old.get("repeatableBeforeEntry") and new.get("repeatableBeforeEntry"):
            result["status"] = "stopped before entry on both revisions"
        elif (new.get("repeatableBeforeEntry") and observed[0]["observerCodeIndex"] is not None
              and any(f["artifact"] in ("client", "upgrade") for f in observed[0]["frames"])
              and old["qualifiedMethodEntries"] == 2 and old["observations"] == [case["expected"]] * 2
              and old["loadedUpgradeOnEachReplay"] and new["loadedUpgradeOnEachReplay"]):
            result.update(status="reproduced earlier failure", before=case["expected"], after={"throws": observed[0]["throws"]})
        comparisons.append(result)
    return comparisons


def run_observation(run_dir, launch, subject_cp, sites, main, encoded, trace_exception, env, resources,
                    deadline, working_directory):
    run_dir.mkdir()
    cwd = run_dir / working_directory
    cwd.mkdir(exist_ok=True)
    for original, relative_file in resources:
        destination = run_dir / "fixtures" / relative_file
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(original.read_bytes())
    command = [*launch, str(run_dir), subject_cp, sites, main, trace_exception, *encoded]
    with subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True) as child:
        try:
            stdout, stderr = child.communicate(timeout=max(0.01, deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
            raise
    if child.returncode:
        raise ValueError(f"JVM exit {child.returncode}: {stderr.decode(errors='replace')[-500:]}")
    observation = run_dir / "observation.txt"
    if not observation.is_file():
        raise ValueError("the application stopped before producing its observation")
    classes = stdout.decode(errors="replace") + "\n" + (run_dir / "child.stderr").read_text(errors="replace")
    return classes, stderr.decode(errors="replace").splitlines(), observation.read_text(encoding="utf-8")


def evaluate(specfile, before, after, probe, jdk, dependencies, timeout, *, fixtures=None, progress=None):
    spec = json.loads(specfile.read_text())
    working_directory = spec.get("workingDirectory", ".")
    if working_directory not in (".", "fixtures"):
        raise ValueError("the observation must run in its fresh trial or fixtures directory")
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
    operand_scope = spec.get("operandScope", "runtime")
    if operand_scope not in ("runtime", "provided", "test"):
        raise ValueError("unknown dependency environment in the caller scope")
    for side, (_, _, binding) in prepared.items():
        if binding.get("operandScope", "runtime") != operand_scope or (operand_scope != "runtime" and
                (binding.get("declaredDependencyScope") != operand_scope or
                 not re.fullmatch("[0-9a-f]{64}", binding.get("modulePomSha256") or ""))):
            raise ValueError(f"{side} preparation does not establish the declared {operand_scope} dependency environment")
    if prepared["old"][2]["sourceSha256"] != prepared["new"][2]["sourceSha256"]:
        raise ValueError("the selected caller source differs between dependency revisions")
    for _, _, binding in prepared.values():
        if ("frameworkFixtures" in binding) != spec.get("withTestFixtures", False):
            raise ValueError("the caller scope and preparation disagree about original test fixtures")
    if dependencies[0] == dependencies[1]:
        raise ValueError("the dependency digests identify the same bytes")
    report = {} if progress is None else progress
    identity = runtime_jdk.identity(jdk)
    report.update({"entry":caller,"observer":spec["observer"],"domainBasis":spec["basis"],"cases":domain,"operandScope":operand_scope,
              "probeSha256":sha(probe),"launcherSha256":sha(LAUNCHER),"tracerSha256":sha(TRACER),"lookupSha256":sha(LOOKUP),"jdk":identity["release"],
              "sides":{s:v[2] for s,v in prepared.items()},"status":"open"})
    if "originalCallerSource" in spec:
        report["originalCallerSource"] = spec["originalCallerSource"]
    owner, method, descriptor = runtime_jar.parse_target(caller)
    start=time.monotonic()
    with tempfile.TemporaryDirectory(prefix="upgrade-case-") as t:
        temp=Path(t)
        env={"PATH":str(jdk/"bin")+":/usr/bin:/bin","HOME":t,"LANG":"C.UTF-8","LC_ALL":"C.UTF-8","TZ":"UTC","TMPDIR":t}
        cp=lambda files:os.pathsep.join(str(x) for x in files)
        output = temp / "probe"
        output.mkdir()
        supplied = []
        fixture_classes = set()
        resources = []
        services = []
        for item in spec.get("fixtures", []):
            if fixtures is None:
                raise ValueError("the original caller fixture directory is missing")
            root = Path(fixtures).resolve()
            file = (root / item["file"]).resolve()
            if not file.is_relative_to(root) or not file.is_file() or sha(file) != item["sha256"]:
                raise ValueError("the fixture differs from its original input: " + item["file"])
            if item["kind"] == "java" and re.fullmatch(r"[\w$]+(?:\.[\w$]+)*", item["class"]):
                supplied.append(file)
                fixture_classes.add(item["class"].replace(".", "/"))
            elif item["kind"] == "service" and re.fullmatch(r"META-INF/services/(?:[A-Za-z_$][\w$]*\.)*[A-Za-z_$][\w$]*", item["file"]):
                services.append((file, output / item["file"]))
            elif item["kind"] == "resource":
                resources.append((file, Path(item["file"])))
            else:
                raise ValueError("unsupported caller fixture kind")
        for source, dest in services:
            providers = [line.split("#")[0].strip() for line in source.read_text().splitlines()]
            named_providers = {name.replace(".", "/") for name in providers if name}
            if not named_providers or not named_providers.issubset(fixture_classes):
                raise ValueError("the service descriptor must name the supplied original Java providers")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(source.read_bytes())
        report["originalFixtures"] = spec.get("fixtures", [])
        report["runtimeCompanions"] = spec.get("runtimeCompanions", [])
        for side, (_, _, bound) in prepared.items():
            if any(c["sha256"] not in bound["classpath"] for c in report["runtimeCompanions"]):
                raise ValueError(f"{side} is missing a declared runtime companion")
        tools = [jdk/"lib/tools.jar"] if (jdk/"lib/tools.jar").is_file() else []
        proc=subprocess.run([str(jdk/"bin/javac"),"-J-Djava.io.tmpdir="+t,"-proc:none","-g","-encoding","UTF-8",
                             "-classpath",cp([*prepared["old"][0],*tools]),"-d",str(output),str(LAUNCHER),str(TRACER),str(LOOKUP),str(probe),*map(str,supplied)],
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
        if any(helper_class(f) not in ("UpgradeObservation", "UpgradeTrace", "UpgradeClassLookup") and helper_class(f).split("$")[0] not in {main.replace(".","/"), *fixture_classes} for f in compiled):
            raise ValueError("the observer compiler produced an unrelated class")
        via = spec.get("invocationVia", "")
        direct = via or caller
        declared_owner, declared_method, declared_descriptor = runtime_jar.parse_target(direct)
        operand = (runtime_jar.internal(declared_owner), declared_method, declared_descriptor)
        probe_owner = main.replace(".", "/")
        code = upgrade_claims.disassemble(jdk, [output], probe_owner, max(0.01, timeout-(time.monotonic()-start)))
        sites = [pc for member, pc, ref in upgrade_claims.invocation_sites(code, probe_owner)
                 if member == ("observe", "([Ljava/lang/String;)Ljava/lang/String;") and ref == operand]
        if not sites:
            raise ValueError("observe() must directly invoke the declared method or its specified synchronous caller")
        report["observerInvocation"] = {"declaration": direct, "codeIndices": sites}
        report["workingDirectory"] = working_directory
        site_argument = ",".join(map(str, sites))
        report["originalInvocation"] = caller
        report["invocationVia"] = via or None
        report["probeClasses"]={helper_class(f):sha(f) for f in compiled}
        launch = [str(jdk/"bin/java"), "-Xmx96m", "-Djava.io.tmpdir="+t, "-cp", cp([output,*tools]),
                  "UpgradeTrace", caller, str(jdk)]
        first_early = None
        old_loaded = {}
        for side,(files,dependency,side_record) in prepared.items():
            if any(runtime_jar.read_class(jar,name) is not None for jar in files for name in report["probeClasses"]):
                raise ValueError("observer classes shadow an input artifact")
            records=[]
            side_record["trials"] = records
            operand_classes=set()
            subject_cp = cp([output, *files])
            for index,case in enumerate(domain):
                trials=[]
                trial_record = {"input": index, "qualifiedMethodEntries": 0, "observations": trials}
                records.append(trial_record)
                early = []
                loaded_each_time = True
                enc=["-" if x is None else base64.b64encode(x.encode("utf-16-be","surrogatepass")).decode() for x in case["args"]]
                def run(directory, trace_exception):
                    return run_observation(directory, launch, subject_cp, site_argument, main, enc, trace_exception,
                                           env, resources, start+timeout, working_directory)

                for trial in range(2):
                    run_dir = temp / f"{side}-{index}-{trial}"
                    report["stoppedAt"] = {"side": side, "input": index, "repetition": trial+1}
                    previous = early or trials
                    trace_exception = previous[0].get("throws", "") if previous else ""
                    child_output, marks, observation_text = run(run_dir, trace_exception)
                    detail = next((line[len("UPGRADE-DETAIL "):] for line in observation_text.splitlines()
                                   if line.startswith("UPGRADE-DETAIL ")), "")
                    if detail:
                        detail = base64.b64decode(detail, validate=True).decode("utf-16-be", "surrogatepass")
                        report["stoppedAt"]["exception"] = detail[:750]
                    if "UPGRADE-HIT " + caller not in marks:
                        outcome = typed_outcome(observation_text.splitlines())
                        if "throws" not in outcome:
                            raise ValueError(f"{side} input {index}: the original caller method was never entered. {detail}")
                        if not trace_exception:
                            # Re-execute with exception events limited to the escaping type. Ordinary
                            # successful checks pay no cost for tracing library-internal exceptions.
                            run_dir = temp / f"{side}-{index}-{trial}-throw"
                            child_output, marks, observation_text = run(run_dir, outcome["throws"])
                        if (typed_outcome(observation_text.splitlines()) != outcome or "UPGRADE-HIT " + caller in marks
                                or (trace_exception and trace_exception != outcome["throws"])):
                            raise ValueError(f"{side} input {index}: inconsistent failure before the original caller")
                        loaded = class_origins(child_output)
                        classes = [name for name, origins in loaded.items() if origins == {dependency}]
                        operand_classes.update(classes)
                        loaded_each_time = loaded_each_time and bool(classes)
                        evidence = throw_evidence(marks, loaded, files, side_record["classpath"],
                                                  dependency, observation_text.splitlines())
                        early.append({**outcome, **evidence})
                        trial_record["beforeEntry"] = early
                        if first_early is None:
                            first_early = dict(report["stoppedAt"])
                        continue
                    outcome = typed_outcome(observation_text.splitlines())
                    escape = None
                    if "throws" in outcome:
                        if not trace_exception:
                            child_output, marks, observation_text = run(temp / f"{side}-{index}-{trial}-escape", outcome["throws"])
                        if typed_outcome(observation_text.splitlines()) != outcome or "UPGRADE-HIT " + caller not in marks:
                            raise ValueError(f"{side} input {index}: inconsistent exception across original caller replays")
                        evidence = throw_evidence(marks, class_origins(child_output), files, side_record["classpath"],
                                                  dependency, observation_text.splitlines())
                        escape = evidence.get("escapingInvocation")
                        if escape:
                            escape["throws"] = outcome["throws"]
                            trial_record.setdefault("escapingExceptions", []).append(escape)
                    site_marks = [line.removeprefix("UPGRADE-CALL-SITE ") for line in marks
                                  if line.startswith("UPGRADE-CALL-SITE ")]
                    if len(site_marks) != 1:
                        raise ValueError("the debugger did not report one live observer call site")
                    pc, dispatched = site_marks[0].split("\t", 1)
                    if int(pc) not in sites or "#" not in dispatched:
                        raise ValueError("the live caller does not match the declared observer instruction")
                    trial_record.setdefault("entryInvocations", []).append(
                        {"observerCodeIndex": int(pc), "dispatchedTo": dispatched})
                    trial_record["qualifiedMethodEntries"] += 1
                    observation,classes=parse_output(child_output,caller,files[0],dependency,observation_text,escape=escape)
                    trials.append(observation)
                    operand_classes.update(classes)
                    loaded_each_time = loaded_each_time and bool(classes)
                    if side == "old":
                        if trial == 0:
                            old_loaded[index] = set(classes)
                        elif index in old_loaded:
                            old_loaded[index].intersection_update(classes)
                trial_record["loadedUpgradeOnEachReplay"] = loaded_each_time
                if early:
                    trial_record["repeatableBeforeEntry"] = len(early) == 2 and early[0] == early[1]
                elif trials[0]!=trials[1]:
                    raise ValueError(f"{side} input {index} gave different observations in fresh JVMs")

            if not operand_classes and all("beforeEntry" not in row for row in records):
                raise ValueError(f"{side} did not load any class from the upgraded artifact")
            side_record.update(trials=records,loadedDependencyClasses=sorted(operand_classes))
        if first_early is not None:
            report["stoppedAt"] = first_early
            report["reason"] = (f"{first_early['side']} input {first_early['input']}: the original caller method was never entered. "
                                + first_early.get("exception", ""))
            report["beforeEntryComparison"] = compare_before_entry(report["sides"], domain)
            upgrade_linkage.diagnose(report, prepared, old_loaded, int(identity["feature"]), jdk, output,
                                     temp, env, start+timeout)
            report["elapsedSeconds"] = round(time.monotonic()-start, 3)
            return report
        report.pop("stoppedAt", None)
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
    ap.add_argument("--fixtures", type=Path)
    a=ap.parse_args(argv)
    result = {}
    started = time.monotonic()
    try:
        result=evaluate(a.spec,a.before,a.after,a.probe,a.jdk,(a.old_dependency,a.new_dependency),a.seconds,
                        fixtures=a.fixtures, progress=result)
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as e:
        detail = result.get("stoppedAt",{}).get("exception")
        reason = str(e) + (". " + detail if detail and detail not in str(e) else "")
        result.update(status="open",reason=reason,entry=json.loads(a.spec.read_text()).get("entry"),
                      specSha256=sha(a.spec),probeSha256=sha(a.probe))
    result["elapsedSeconds"] = round(time.monotonic() - started, 3)
    result["specSha256"] = sha(a.spec)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(result["status"],result.get("reason",result.get("entry","")))
    return 0 if result["status"] in ("changed","preserved") else 1
