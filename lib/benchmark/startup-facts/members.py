"""Original ThreeTen overlap histories and positive and negative uses of a reflected Method."""
import argparse
import base64
import json
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from charset import compile_to, command, java, sha, ENV, IO, OBSERVER, ROOT, startup_facts

LOOKUP = "getUnicodeLocaleType"
DESCRIPTOR = "(Ljava/lang/String;)Ljava/lang/String;"


def qualify(work):
    rows = []
    receipts = work / "receipts"
    tools = work / "recorder"
    compile_to(tools, [OBSERVER / "ObservedInitializer.java", OBSERVER / "StartupTrace.java"])
    case = IO.parent / "threeten"
    workflows = json.loads((case / "workflows.json").read_bytes())["workflows"]
    for side in ("old", "new"):
        deployment = json.loads((case / side / "prepared.json").read_bytes())
        artifact, = deployment["classpath"]
        jar = Path(artifact["file"])
        assert sha(jar.read_bytes()) == artifact["sha256"]
        classes = work / side
        compile_to(classes, [case / "UpgradeProbe.java", ROOT / "examples/tools/targets/java/UpgradeObservation.java"], jar)
        cp = os.pathsep.join(map(str, (classes, jar)))
        cmd = command("UpgradeProbe#overlap", "result == true", classes, jar)
        run = startup_facts.recover(cmd, work / (side + "-property"), receipts=receipts, env=ENV)
        assert run["receiptId"] and run["retry"] == "unverifiable", run
        assert "LOCALE_METHOD" in run["initializerStop"] and "LOCALE_METHOD" not in run["remaining"], run
        receipt = json.loads((receipts / (run["receiptId"] + ".json")).read_bytes())
        compare, = receipt["alone"]
        original = next(f for f in receipt["capture"]["fields"] if f["field"].endswith("#LOCALE_METHOD"))
        independent, = compare["capture"]["fields"]
        assert original["member"] == independent["member"] and original["arity"] == 1
        member = original["member"]
        assert (member["owner"], member["name"], member["descriptor"], member["loader"]) == ("java/util/Locale", LOOKUP, DESCRIPTOR, "bootstrap")
        observations = []
        with ZipFile(jar) as packaged:
            tzdb = sha(packaged.read("org/threeten/bp/TZDB.dat"))
        for flow in workflows:
            cases = json.loads((case / flow["scope"]).read_bytes())["cases"]
            changes = flow.get("intent")
            fixes = {v["input"]:v["expectedNew"] for v in changes["allowedChanges"]} if isinstance(changes, dict) else {}
            for i, registered in enumerate(cases):
                args = [base64.b64encode(s.encode("utf-16-be")).decode() for s in registered["args"]]
                expected = fixes.get(i, registered["expected"]) if side == "new" else registered["expected"]
                sample = f'{side}-{flow["id"]}-{i}'
                values = []
                path = work / (sample + ".events.json")
                for traced in (False, True):
                    output = work / (sample + str(traced) + ".out")
                    opts = ["-Duser.timezone=UTC", "-Duser.language=en", "-Duser.country=US", "-Dupgrade.observation.file=" + str(output), "-cp", cp]
                    main = ["UpgradeObservation", "UpgradeProbe", *args]
                    java(["-cp", tools, "StartupTrace", path, "UpgradeProbe#observe([Ljava/lang/String;)Ljava/lang/String;", "--methods",
                          *opts, "--main", *main] if traced else [*opts, *main], "C.UTF-8")
                    line = output.read_text().strip().removeprefix("UPGRADE-OBSERVATION return ")
                    values.append(base64.b64decode(line, validate=True).decode("utf-16-be"))
                assert values == [expected["return"]]*2, values
                events = json.loads(path.read_bytes())["events"]
                uses = [e for e in events if e.get("member") and e["member"].get("name") == LOOKUP]
                assert any(e["operation"].startswith("getMethod(") for e in uses)
                assert not any(e["operation"].startswith("invoke(") for e in uses)
                observations.append({"input": registered["args"], "original": values[0], "debuggerParity": True,
                                     "memberLookups":sum(e["operation"].startswith("getMethod(") for e in uses), "memberInvocations":0})
        rows.append({"revision":deployment["commit"],"side":side,"jar":artifact["sha256"],"tzdbSha256":tzdb,
                     "claim":run,"publicHistories":observations})
        print(side, run["remaining"], flush=True)
    return rows


def controls(work):
    fixture = ROOT / "lib/tests/fixtures/observed-countermodels/app/oc/MemberStartup.java"
    classes = work / "control-classes"
    compile_to(classes, [fixture])
    rows = []
    for index, (suffix, operation, predicate, expected) in enumerate([
        ("", "arity()I", "result == 1", "verified"),
        ("", "aliases()Z", "result", "verified"),
        ("$Missing", "absent()Z", "result", "verified"),
        ("$Opened", "count()I", "result == 1", "accessible override"),
        ("", "invoked()Z", "result", "unsupported invoke"),
    ]):
        root = "oc.MemberStartup" + suffix
        cmd = command(root + "#" + operation, predicate, classes)
        direct = ["--observed-initializer", root, "--observed-runtime", '{"reflectiveMembers":true}']
        here = work / ("control-" + str(index))
        code, outcome, diagnostic = startup_facts.run_step(cmd, direct, here, ENV)
        if expected == "verified":
            assert code == 0 and outcome["verdict"] == expected, (diagnostic,outcome)
            receipt, = (here / "startup-receipts").glob("*.json")
            record = json.loads(receipt.read_bytes())
            if operation == "arity()I":
                assert any(a.get("id","").startswith("startup-method:") for a in outcome["stated"]["assumptions"])
            elif operation == "aliases()Z":
                ids = {f["field"].split("#")[-1]: f["alias"] for f in record["capture"]["fields"]}
                assert ids["FIRST"] == ids["ALIAS"] != ids["COPY"], ids
            else:
                assert any(e.get("threw") == "java.lang.NoSuchMethodException" for e in record["capture"]["events"])
        elif expected == "unsupported invoke":
            assert code and outcome["verdict"] == "unverifiable" and expected in outcome["problem"], (diagnostic, outcome)
        else:
            assert code and expected in diagnostic and not list((here / "startup-receipts").glob("*.json")), diagnostic
        rows.append({"operation":operation, "expectation":expected,"disposition":outcome["verdict"] if outcome else diagnostic.strip()})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="qualify-members-") as tmp:
        work = Path(tmp)
        doc = {"rows":qualify(work),"controls":controls(work),"caseSpecificStartupProbes":0}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(args.output,"w",compression=ZIP_DEFLATED) as archive:
            archive.writestr("scorecard.json",json.dumps(doc,indent=2)+"\n")
            for path in (work/"receipts").glob("*.json"): archive.write(path,"receipts/"+path.name)
    print("2 original deployments and 12 original histories; reflective metadata and alias controls passed")


if __name__ == "__main__":
    main()
