"""Rebuild the claims that combine ordinary proofs with classpath resources or JVM launch settings."""
import hashlib
import re
from pathlib import Path

import converter_interfaces as converters
import factory_stream as stream
import fluent_launch as launch
import fluent_lines as lines
from measure import ROOT, read, digest as sha
from startup_results import metadata_cases, rel, require
from targets import runtime_jar


def stream_result(job, cases, graphs, checker, earlier):
    sides = {}
    for side, graph in graphs.items():
        base = stream.DEST.relative_to(ROOT) / side
        record = job.output(base / "measurement.json")
        data = read(record)
        provider, = earlier[side]["resources"]
        payload = job.output(base / "entry.bin").read_bytes()
        caller = job.output(base / "FactoryStream.jvm-bytecode")
        entry = job.output(base / "FactoryStreamWitness.jvm-bytecode")
        jvm = job.output(base / "jvm.stdout")
        require(data["job"] == job.record["id"] and data["source"] == job.record["sourceCommit"]
                and data["libTree"] == job.record["jvmcontract"]["libTree"] and data["jdk"] == graph["jdk"]
                and data["classpath"] == graph["orderedJars"][1:] and data["provider"] == provider
                and len(payload) == data["bytes"] == 161 and hashlib.sha256(payload).hexdigest() == provider["entrySha256"]
                and job.output(base / "FactoryStreamWitness.java").read_text() == stream.witness(payload)
                and data["sourceSha256"] == sha(stream.SOURCE) and data["callerSha256"] == sha(caller)
                and data["entryClassSha256"] == sha(entry) and runtime_jar.this_class(caller.read_bytes()) == "springwork/FactoryStream"
                and runtime_jar.this_class(entry.read_bytes()) == "springwork/FactoryStreamWitness"
                and jvm.read_bytes() == b"1\n" and sha(jvm) == data["jvmSha256"], "different factory-stream graph, bytes or control")
        proof = data["result"]
        rawfile = job.output(base / proof["stdout"])
        raw, = read(rawfile)
        stated = raw["stated"]
        qualified = cases["368"]["claims"]["beans-" + side]["tableSelectors"]
        # Some binder graphs stop before the stream is opened. The resource provider and
        # digests can still be qualified directly from their frozen, ordered input JARs.
        resources = [a for a in stated["assumptions"] if "stock JAR handler" in a["text"]]
        provider_index = next(i for i, b in enumerate(data["classpath"]) if b["sha256"] == provider["jarSha256"])
        require(len(resources) == 1 and resources[0]["text"].endswith(f"[{provider_index + 2}:{provider['entrySha256']}]")
                and data["checkerSha256"] == checker
                and all(a["basis"] == "engine" and not a.get("id", "").startswith("observed-initializer:")
                        and (a in qualified["assumptions"] or a in resources) for a in stated["assumptions"]),
                "unqualified resource provider or assumption")
        require(sha(rawfile) == proof["stdoutSha256"] and proof["states"] == {} and proof["observedRoots"] == []
                and proof["target"] == raw["target"] == stream.TARGET and proof["assumptions"] == stated["assumptions"]
                and raw["assert"] == proof["assertion"] == "result == 1" and raw["assume"] is None and not raw["throws"]
                and raw["verdict"] == proof["verdict"] == "verified" and not raw["problem"] and not raw["counterexample"]
                and not proof["exit"] and stated["checker"]["engine"] == "native" and stated["checker"]["fallback"] is None
                and stated["gap_mode"] == "strict" and stated["vacuity"]["status"] == "non-vacuous"
                and not stated["domain"]["parameters"] and not stated["domain"]["shared_arrays"]
                and stated["observations"]["exceptions"] == "none may be thrown"
                and stated["bounds"] == {"unwind": stream.BOUNDS[0], "max_array_length": None, "complete": True}
                and raw["search"]["max_array_length"] == stream.BOUNDS[1], "different or incomplete factory-stream proof")
        sides[side] = {"record": rel(record), "receipt": rel(rawfile), "bytes": len(payload),
                       "entrySha256": provider["entrySha256"], "providerSha256": provider["jarSha256"]}
    return sides


def launches(job, producer, graph, guarded):
    base = launch.DEST.relative_to(ROOT)
    path = job.output(base / "measurement.json")
    data = read(path)
    original = lines.DEST.relative_to(ROOT)
    basis = read(producer.output(original / "measurement.json"))
    bound = producer.output(original / "FluentLines.jvm-bytecode")
    launch.guard(bound.read_bytes())
    proof_digest = sha(producer.output(original / "cases.tar.gz"))
    observers, = {b["sha256"] for b in basis["bindings"] if b["class"] == "springwork.RoleChecks"}
    original_observers = job.output(base / "RoleChecks.jvm-bytecode")
    launch.observers(original_observers.read_bytes())
    entry = job.output(base / "FluentLaunch.jvm-bytecode")
    require(data["job"] == job.record["id"] and data["source"] == job.record["sourceCommit"]
            and data["producer"] == producer.record["id"] == launch.PRODUCER and guarded["checked"] == 32
            and data["classpath"] == graph["orderedJars"][1:] and data["jdk"] == graph["jdk"]
            and set(data["runtimeSha256"]) == set(launch.VM_FILES)
            and all(re.fullmatch("[0-9a-f]{64}", d) for d in data["runtimeSha256"].values())
            and data["checkerSha256"] == guarded["checkerSha256"] and data["guardSha256"] == sha(bound)
            and data["observersSha256"] == observers == sha(original_observers) and data["casesSha256"] == proof_digest
            and data["sourceSha256"] == sha(launch.SOURCE) and data["launchClassSha256"] == sha(entry)
            and runtime_jar.this_class(entry.read_bytes()) == "springwork/FluentLaunch"
            and data["environment"] == launch.ENV and set(data["profiles"]) == set(lines.PROFILES),
            "different executable, original callers, guard or native proof family")
    for profile, sep in lines.PROFILES.items():
        item = data["profiles"][profile]
        raw = job.output(base / (profile + ".stdout"))
        active = sep in ("\n", "\r\n")
        require(item == {"vmOptions": [] if profile == "default" else ["-Dline.separator=" + sep],
                         "initialUnits": list(map(ord, sep)), "guardActive": active,
                         "nativeCoverage": 32 if active else 0, "stdoutSha256": sha(raw)}
                and raw.read_bytes().decode("ascii").splitlines() == launch.rows(sep),
                "different JVM launch, inactive premise or inconsistent public rows")
    return {"record": rel(path), "guardedProof": rel(producer.folder / "result.json"),
            "entrySequence": ["springwork.RoleChecks#fluentNames(I)I", "springwork.RoleChecks#fluentDecision(I)I"],
            "scope": "The guarded caller invokes the two public observers in order after testing the startup separator.",
            "profiles": data["profiles"]}


def converter_inputs(job, cases, graphs):
    sides = {}
    definitions = None
    for side, graph in graphs.items():
        base = converters.DEST.relative_to(ROOT) / side
        record = job.output(base / "measurement.json")
        data = read(record)
        physical = job.output(base / "jvm.stdout")
        require(data["job"] == job.record["id"] and data["source"] == job.record["sourceCommit"]
                and data["jdk"] == graph["jdk"] and data["classpath"] == graph["orderedJars"][1:]
                and data["sourceSha256"] == sha(converters.SOURCE) and data["jvmSha256"] == sha(physical)
                and physical.read_bytes().decode("ascii").splitlines() == converters.ROWS
                and set(data["definitions"]) == set(converters.CLASSES), "different formatter reflection witness")
        core, = [jar for jar in data["classpath"] if jar["path"].endswith("/spring-core-5.2.0.RELEASE.jar")]
        for name, info in data["definitions"].items():
            require(info["entry"] == name.replace(".", "/") + ".class" and info["provider"] == core["path"]
                    and info["jarSha256"] == core["sha256"] and re.fullmatch("[0-9a-f]{64}", info["classSha256"]),
                    "different class provider for the registered converter")
        require(definitions is None or data["definitions"] == definitions, "different converter classes on the formatter graphs")
        definitions = data["definitions"]
        for method in ("annotated", "preservation"):
            primary = cases["374"]["claims"][method + "-" + side]["tableSelectors"]
            require(primary["blockedSelector"] == 0 and "java.lang.Class.getGenericInterfaces" in primary["firstBlocker"],
                    "the first unresolved formatter call differs from the measured input")
        sides[side] = {"record": rel(record), "factory": converters.FACTORY, "interfaces": converters.ROWS[1:3],
                       "resolvedArguments": ["java.lang.Number", "java.lang.Number"], "registeredOnJvm": True}
    return sides


def measured_deployments(job, producer, cases, earlier):
    require(job.record["status"] == "passed" and producer.record["status"] == "passed", "incomplete Spring deployment controls")
    graphs = read(ROOT / "verification/spring-java-data/exact-classpaths/classes.json")
    checker = read(job.output(stream.DEST.relative_to(ROOT) / "release/measurement.json"))["checkerSha256"]
    require(re.fullmatch("[0-9a-f]{64}", checker), "unbound native checker")
    names = metadata_cases(job, cases["372"], graphs["372"], checker, ordinary_startup=True)
    require(all(row["lookupProviderSha256"] == earlier["metadataWithClassUtils"][side]["lookupProviderSha256"]
                for side, row in names.items()), "different ClassUtils provider across the ordinary and captured routes")
    return {"factoryStreams": stream_result(job, cases, graphs["368"], checker, earlier["factoryResources"]),
            "fluentLaunches": launches(job, producer, graphs["370"]["landed"], earlier["fluentLineSeparators"]),
            "ordinaryMetadata": names,
            "formatterInterfaces": converter_inputs(job, cases, graphs["374"])}
