"""Replay an original Configuration caller with a live property as part of its process prestate."""

import argparse
import os
from pathlib import Path
import tempfile

from callers import EXTERNAL, JDK, RESULTS, ROOT, read, sha, upgrade
from configuration import prepare
from investigate import class_bytes, command, compiler, inventory, native, write
from process_states import methods


HERE = Path(__file__).resolve().parent
OUT = RESULTS / "recovery"
HOLDER = "org.apache.commons.configuration2.interpol.ConfigurationInterpolator$DefaultPrefixLookupsHolder"


def java(classes, cls, *args):
    return command([JDK / "bin/java", "-ea", "-Xverify:all", "-cp", os.pathsep.join(map(str, classes)),
                    cls, *args], timeout=35).splitlines()


def compile_to(directory, cp, *sources):
    command([JDK / "bin/javac", "-proc:none", "-g", "-encoding", "UTF-8", "-cp",
             os.pathsep.join(map(str, cp)), "-d", directory, *sources])


def identities():
    return {
        "job": os.environ["VERIFY_JOB_ID"], "source": os.environ["VERIFY_SOURCE_COMMIT"],
        "jdk": {name: sha(JDK / path) for name, path in
                (("release", "release"), ("java", "bin/java"), ("modules", "lib/modules"))},
    }


def live_table():
    with tempfile.TemporaryDirectory() as directory:
        dest = Path(directory)
        source = HERE / "history/LiveProperties.java"
        compile_to(dest, [dest], source)
        checks = java([dest], "LiveProperties")
        if len(checks) != 15 or len(set(checks)) != len(checks):
            raise ValueError("live property table census is incomplete")
        OUT.mkdir(parents=True, exist_ok=True)
        write(OUT / "live-table.json", {
            **identities(), "prestate": "fresh single-threaded JVM, original standard Properties and absent private key",
            "sourceSha256": sha(source), "observerClassSha256": sha(dest / "LiveProperties.class"),
            "initializerClassSha256": sha(dest / "LiveProperties$Saved.class"), "observations": checks,
        })


def property_reads(checker, cp, temp):
    holder = inventory(checker, cp, HOLDER + "#<clinit>")
    artifact = temp / "Holder.class"
    artifact.write_bytes(class_bytes(holder["binding"]))
    if sha(artifact) != holder["binding"]["sha256"]:
        raise ValueError("holder binding differs")
    bytecode, _ = methods(JDK / "bin/javap", artifact)
    init = bytecode["<clinit>", "()V"]["code"]
    (read_table,) = [i.pc for i in init if i.member == "Method java/lang/System.getProperties:()Ljava/util/Properties;"]
    (constructor,) = [v["code"] for (name, desc), v in bytecode.items()
                      if name.endswith("$DefaultPrefixLookupsHolder") and desc == "(Ljava/util/Properties;)V"]
    reads = {}
    keys = set()
    for literal, invocation in zip(constructor, constructor[1:]):
        for member, signature in (("containsKey", "(Ljava/lang/Object;)Z"), ("getProperty", "(Ljava/lang/String;)Ljava/lang/String;")):
            if invocation.member == "Method java/util/Properties." + member + ":" + signature:
                if not literal.member.startswith("String ") or member in reads:
                    raise ValueError("expected a unique named lookup on the holder's table")
                keys.add(literal.member.removeprefix("String "))
                reads[member] = invocation.pc
    if len(keys) != 1 or set(reads) != {"containsKey", "getProperty"}:
        raise ValueError("initializer property binding is ambiguous")
    return {"classSha256": sha(artifact), "getPropertiesPc": read_table, "key": keys.pop(), "reads": reads}


def observed(cp, pins, property_key, profile, operation, *args):
    lines = java(cp, "ConfigurationPrestate", profile, property_key, operation, HOLDER, *args)
    fields = [line.split("\t", 1) for line in lines]
    for name, digest in pins.items():
        if [name, digest] not in fields:
            raise ValueError(("different original class", name))
    table = dict(fields[:len(pins) + 2])
    if table["own"] != str(profile == "own-invalid").lower() or table["lookup"] != ("null" if profile == "default" else "_"):
        raise ValueError(("wrong property prestate", profile, table))
    remaining = fields[len(pins) + 2:]
    if operation == "predicate":
        if remaining not in ([["matched", "true"]], [["matched", "false"]]):
            raise ValueError(("missing caller return", remaining))
        return remaining[0][1] == "true"
    calls = []
    for tag, value in remaining:
        if tag == "call" and value == str(len(calls) + 1):
            calls.append({})
        elif tag in ("null", "value"):
            calls[-1]["return"] = None if tag == "null" else value
        elif tag in ("cause", "frame"):
            calls[-1].setdefault(tag, []).append(value)
        else:
            raise ValueError(("unexpected JVM observation", tag, value))
    if len(calls) != 2:
        raise ValueError("missing first or repeated call")
    return calls


def run_case(case):
    checker = Path(os.environ["JVMCONTRACT"]).resolve()
    out = OUT / case
    out.mkdir(parents=True, exist_ok=True)
    scope = read(RESULTS / "scope.json")
    pin = scope["registeredCallers"][case]
    reference = read(ROOT / pin["reference"])
    report = {**identities(), "checkerSha256": sha(checker), "originalSourceReceiptSha256": pin["sha256"],
              "scope": "The frozen finite selector predicate at ordinary single-threaded public startup. The process admits System.setProperty before first use; all other settings retain the stock JVM defaults.",
              "controls": {"default": "standard table, key absent", "own-invalid": "standard table, key set to _",
                           "inherited-invalid": "child Properties with no own entries, parent key set to _"},
              "cases": pin["cases"], "registered": upgrade(case, out, scope), "sides": {}}
    for side in ("old", "new"):
        with tempfile.TemporaryDirectory() as dirname:
            temp = Path(dirname)
            cp, _ = prepare(case, side, temp, scope)
            # The historical observer was compiled with debug metadata, the selector with -parameters as well.
            source = EXTERNAL / "scenarios" / case / "UpgradeProbe.java"
            if sha(source) != reference["probeSha256"]:
                raise ValueError("registered original probe source differs")
            compile_to(cp[0], cp, source, HERE / "history/ConfigurationPrestate.java")
            binding = property_reads(checker, cp, temp)
            pins = {"UpgradeProbe": reference["probeClasses"]["UpgradeProbe"],
                    "UpgradeCallerClaim": reference["nativeCaller"]["adapterClassSha256"], HOLDER: binding["classSha256"]}
            profiles = {}
            for profile in report["controls"]:
                rows = []
                for i, item in enumerate(pin["cases"]):
                    matched = observed(cp, pins, binding["key"], profile, "predicate", str(i))
                    calls = observed(cp, pins, binding["key"], profile, "observe", *item["args"])
                    if profile == "own-invalid":
                        if (matched or calls[0].get("cause", [])[:2] != ["java.lang.ExceptionInInitializerError", "java.lang.IllegalArgumentException"]
                                or calls[1].get("cause", [])[:1] != ["java.lang.NoClassDefFoundError"]
                                or HOLDER + ".parseLookups" not in calls[0].get("frame", [])):
                            raise ValueError((case, side, i, profile, matched, calls))
                    elif not matched or calls != [item["expected"], item["expected"]]:
                        raise ValueError((case, side, i, profile, matched, calls))
                    rows.append({"selector": i, "predicate": matched, "originalCalls": calls})
                profiles[profile] = rows
            trees = inventory(checker, cp, "ConfigurationIsolation#unchanged")
            tools = compiler(temp)
            orders = {}
            for order in ["false", "true"]:
                rows = java([tools, *cp], "org.intheloop.observation.CallOnce", "ConfigurationIsolation",
                            "ConfigurationIsolation", "unchanged", "(Z)Z", order)
                if rows != ["class " + trees["binding"]["sha256"], "returned true"]:
                    raise ValueError(("tree isolation", order, rows))
                orders[order] = rows[-1]
            isolation = native(checker, cp, "ConfigurationIsolation#unchanged", None, 64, 128, 60, temp / "trees")
            report["sides"][side] = {
                "commit": pin["sides"][side]["commit"], "classpath": pin["sides"][side]["orderedClasspathSha256"],
                "classBindings": pins, "property": binding, "profiles": profiles,
                "ordinary": {"status": "refuted", "route": "original JVM in an admitted process prestate",
                             "witness": {"profile": "own-invalid", "selector": 0}},
                "trees": {"checker": isolation["verdict"], "firstOutstanding": isolation["problem"],
                          "jvmBothReadOrders": orders, "classSha256": trees["binding"]["sha256"]},
            }
    report["receiptPackSha256"] = sha(out / "receipts.tar.gz")
    write(out / "measurement.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=["live", "commons-configuration-565", "commons-configuration-601"])
    args = parser.parse_args()
    if args.case == "live":
        live_table()
    else:
        run_case(args.case)
