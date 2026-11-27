"""Qualification on pinned originals. The recovery code never reads these evaluation oracles."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import startup_facts

JDK = Path.home() / ".sdkman/candidates/java/21.0.13.0+9-tem"
IO = ROOT / "lib/benchmark/organic-composition/io"
SMALL = ROOT / "lib/tests/fixtures/setting-countermodels/sc"
OBSERVER = ROOT / "lib/src/observed"
ENV = dict(os.environ, JAVA_HOME=str(JDK), PATH=str(JDK / "bin") + os.pathsep + os.environ["PATH"])
CHECKER = os.environ.get("JVMCONTRACT", str(ROOT / "lib/target/release/jvmcontract"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compile_to(where, sources, cp=None):
    where.mkdir()
    command = [JDK / "bin/javac", "-proc:none", "-g", "-encoding", "UTF-8", "-d", where]
    subprocess.run(command + (["-cp", cp] if cp else []) + list(sources), check=True)


def java(args, locale):
    env = {k: v for k, v in ENV.items() if k not in ("_JAVA_OPTIONS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS")}
    return subprocess.run([JDK / "bin/java", *args], env=dict(env, LC_ALL=locale, LANG=locale), check=True,
                          capture_output=True, timeout=45).stdout


def command(entry, assertion, classes, jar=None):
    return [CHECKER, "prove", entry, "--assert", assertion, "--classes", str(classes),
            *(["--classpath", str(jar)] if jar else []),
            "--engine", "native", "--gaps", "strict", "--unwind", "16", "--json"]


def validate(report):
    assert report["original"]["verdict"] == "unverifiable", report
    assert "reads the default charset" in report["initializerStop"] and report["receiptId"], report
    print(startup_facts.summary(report), flush=True)


def small(work):
    classes = work / "classes"
    compile_to(classes, sorted(SMALL.glob("*.java")))
    cmd = command("sc.M#encoded()I", "result == 2", classes)
    cache = work / "receipts"
    rows = []
    for locale, expected, verdict in [("C.UTF-8", 2, "verified"), ("C", 1, "violation")]:
        plain = [java(["-Dfile.encoding=COMPAT", "-cp", classes, "sc.M", "encoded"], locale).decode().strip() for _ in range(2)]
        assert plain == [f"encoded={expected}"] * 2
        run = work / locale
        first = startup_facts.recover(cmd, run, locale, receipts=cache, env=ENV)
        validate(first)
        assert first["retry"] == verdict and "startup-charset:" + first["receiptId"] in first["consumed"], first
        warm = startup_facts.recover(cmd, run, locale, resume=True, receipts=cache, env=ENV)
        validate(warm)
        assert warm["receiptId"] == first["receiptId"] and warm["retry"] == verdict
        assert warm["recording"].startswith("reused trace"), warm
        clean = startup_facts.recover(cmd, work / (locale + "-clean"), locale, env=ENV)
        assert clean["receiptId"] == first["receiptId"] and clean["retry"] == verdict, clean
        watch = [sys.executable, ROOT / "llm-dlc/tools/watch.py", "startup-facts"]
        reports = {}
        for label, r in (("normal", first), ("resumed", warm)):
            reports[label] = subprocess.check_output([*watch, run / r["attempt"] / "startup-report.json"], text=True).strip()
            assert reports[label] == startup_facts.summary(r)
        rows.append({"revision": sha((classes / "sc/Encoded.class").read_bytes()), "claim": first["original"]["target"],
                     "locale": locale, "scope": "conditional native, exact launch and literal", "untouched": plain,
                     "record": first, "resumed": warm["recording"], "emptyCache": clean["recording"], "watcher": reports})
    old = rows[0]["record"]["receiptId"]
    def retry(name, profile, id_, arguments=cmd):
        extra = ["--observed-initializer", "sc.Encoded", "--observed-runtime", json.dumps(
            {"charsetLocale": profile, "expectedCharsetReceipt": id_, "charsetReceiptDirectory": str(cache)})]
        return startup_facts.run_step(arguments, extra, work / name, ENV)
    code, _, reason = retry("cross-profile", "C", old)
    assert code and "binding changed" in reason, reason
    marker = classes / "fixture.properties"
    marker.write_text("selected=other\n")
    code, _, reason = retry("changed-deployment", "C.UTF-8", old)
    assert code and "binding changed" in reason, reason
    marker.unlink()
    code, outcome, reason = retry("restored", "C.UTF-8", old, command("sc.M#encoded()I", "result >= 1", classes))
    assert code == 0 and outcome["verdict"] == "verified" and "reused trace" in reason, reason
    saved = cache / (old + ".json")
    tampered = json.loads(saved.read_bytes())
    tampered["executed"][0]["canonical"] = "US-ASCII"
    original = saved.read_bytes()
    saved.write_text(json.dumps(tampered))
    code, _, reason = retry("tampered", "C.UTF-8", old)
    assert code and "digest" in reason, reason
    saved.write_bytes(original)
    return {"rows": rows, "controls": ["withheld on the original check", "cross-profile receipt", "same-path change",
        "restored input and new claim reusing only the recording", "altered event rejected"], "caseSpecificStartupProbes": 0}


def io(work):
    tools = work / "recorder"
    compile_to(tools, [OBSERVER / "ObservedInitializer.java", OBSERVER / "StartupTrace.java"])
    historical = json.loads((ROOT / "verification/organic-composition/io/charset-profiles.json").read_bytes())["profiles"]
    rows = []
    for side in ("old", "new"):
        manifest = json.loads((IO / side / "prepared.json").read_bytes())
        provider, = manifest["classpath"]
        jar = Path(provider["file"])
        assert sha(jar.read_bytes()) == provider["sha256"]
        classes = work / (side + "-classes")
        compile_to(classes, [IO / "UpgradeProbe.java", IO / "charset/CharsetPositions.java"], jar)
        cp = os.pathsep.join(map(str, [classes, jar]))
        cmd = command("UpgradeProbe#rewind()Z", "result == true", classes, jar)
        for locale in ("C.UTF-8", "C"):
            record = startup_facts.recover(cmd, work / (side + locale), locale, receipts=work / "receipts", env=ENV)
            validate(record)
            assert record["executed"] == [] and len(record["potentialReferences"]) >= 1, record
            assert not any(i.startswith("startup-charset:") for i in record["consumed"]), record
            assert record["remaining"] and "class-initializer:org.apache.commons.io.Charsets." not in record["remaining"], record
            for constructor in ("default", "explicit"):
                registered, = [r for r in historical if (r["side"], r["processLocale"], r["constructorCharset"]) == (side, locale, constructor)]
                main = ["CharsetPositions", "two-resets", constructor]
                options = ["-Dfile.encoding=COMPAT", "-Duser.timezone=UTC", "-cp", cp]
                plain = [java([*options, *main], locale) for _ in range(2)]
                tracefile = work / (side + locale + constructor + ".trace.json")
                traced = java(["-cp", tools, "StartupTrace", tracefile, "UpgradeProbe#observe([Ljava/lang/String;)Ljava/lang/String;",
                               *options, "--main", *main], locale)
                assert traced == plain[0] == plain[1], "full original and instrumented histories differ"
                fields, cycles = {}, []
                for line in traced.decode().splitlines():
                    key, value = line.split("\t", 1)
                    if key == "cycle":
                        before, count, read, reset = value.split("\t")
                        cycles.append({"before": before, "count": int(count), "afterRead": read, "afterReset": reset})
                    else:
                        fields[key] = value
                transitions = Counter(json.dumps(c, sort_keys=True) for c in cycles)
                historical_transitions = {json.dumps({k:v for k,v in c.items() if k != "countOfTransition"}, sort_keys=True): c["countOfTransition"]
                                          for c in registered["distinctTransitions"]}
                assert len(cycles) == registered["cycles"] and transitions == historical_transitions
                assert fields["default"] == record["profile"]["canonical"] == registered["actualDefault"]
                assert fields["encoder"] == registered["actualEncoder"] and fields["observation"] == registered["publicObservation"]
                assert fields["marked"] == registered["initialMark"] and Path(fields["source"]) == jar
                events = json.loads(tracefile.read_bytes())["events"]
                uses = [e for e in events if any("CharSequenceInputStream#<init>" in frame for frame in e["stack"])]
                assert bool(uses) == (constructor == "default"), events
                rows.append({"revision": manifest["commit"], "side": side, "locale": locale, "constructor": constructor,
                             "record": record, "encoder": fields["encoder"], "defaultCallsInConstructor": uses,
                             "initialMark": fields["marked"], "publicObservation": fields["observation"],
                             "cycles": len(cycles), "ordinaryRepeats": 2, "instrumentedParity": True})
    return {"rows": rows, "historicalTrialsReproduced": 16, "caseSpecificStartupProbes": 0,
            "publicCaller": "pre-existing registered UpgradeProbe; historical CharsetPositions used only by evaluator"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=("small", "io"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="qualify-startup-") as tmp:
        work = Path(tmp)
        evidence = (small if args.case == "small" else io)(work)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(args.output, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("scorecard.json", json.dumps(evidence, indent=2) + "\n")
            for receipt in sorted((work / "receipts").glob("*.json")):
                archive.write(receipt, "receipts/" + receipt.name)
    print(args.case, len(evidence["rows"]), "qualified rows", flush=True)


if __name__ == "__main__":
    main()
