"""Qualify factory startup and the existential witness for two unrestricted role claims."""
from pathlib import Path

import factory_startup as factories
import fluent_witness as fluent
from measure import ROOT, digest, read
from startup_results import rel, require
from targets import runtime_jar


def same_run(job, data, graph, checker):
    require(job.record["status"] == "passed" and data["job"] == job.record["id"]
            and data["source"] == job.record["sourceCommit"] and data["libTree"] == job.record["jvmcontract"]["libTree"]
            and data["checkerSha256"] == checker and data["classpath"] == graph["orderedJars"][1:]
            and data["jdk"] == graph["jdk"], "different managed source, native checker, JDK or ordered artifacts")


def native_record(job, base, result, target):
    raw_file = job.output(base / result["stdout"])
    require(result["exit"] == 0 and result["verdict"] == "verified" and result["blocker"] is None
            and result["target"] == target and result["guard"] is None and result["assertion"] == "result == 1"
            and result["bounds"] == [256, 16384] and not result["states"] and not result["observedRoots"]
            and digest(raw_file) == result["stdoutSha256"], "different proof target, roots or raw output")
    return raw_file


def binding(binary, provider, class_sha, method=None, descriptor=None):
    return {"class": binary, "provider": provider, "entry": binary.replace(".", "/") + ".class",
            "sha256": class_sha, "method": method, "descriptor": descriptor}


def factory_record(job, kind, side, graph, primary, prior):
    folder, simple, _, _ = factories.subject(kind)
    base = folder.relative_to(ROOT) / "records/factory-startup" / side
    record = job.output(base / "measurement.json")
    data = read(record)
    same_run(job, data, graph, primary["checkerSha256"])
    name = "springwork." + simple
    classes = {simple, simple + "$1"} if kind == "filename" else {simple, simple + "$Checked", simple + "$Registry"}
    require(data["sourceSha256"] == digest(folder / "companions" / (simple + ".java"))
            and set(data["callerClasses"]) == classes, "different factory observer source or class set")
    for cls, sha in data["callerClasses"].items():
        file = job.output(base / (cls + ".jvm-bytecode"))
        require(digest(file) == sha and runtime_jar.this_class(file.read_bytes()) == "springwork/" + cls,
                "different factory observer bytecode")
    actual = job.output(base / "jvm.stdout")
    require(digest(actual) == data["jvmSha256"], "different original JVM observation")
    providers = dict(graph["classes"])
    target = name + "#check()"
    proof = data["result"]
    raw = native_record(job, base, proof, target)
    assumptions = proof["assumptions"]
    factories.native(raw.read_bytes(), target, assumptions)
    summary = {"record": rel(record), "receipt": rel(raw), "originalJVM": rel(actual)}
    allowed = list(primary["assumptions"])
    if kind == "filename":
        check, first, size, path_hash = actual.read_text().split()
        require((check, first, size) == ("1", "161", "161") and path_hash == data["canonicalURLPathSha256"]
                and len(bytes.fromhex(path_hash)) == 32, "different refill counts or lexical JAR path")
        provider_index, = [i for i, jar in enumerate(data["classpath"]) if jar["sha256"] == prior["providerSha256"]]
        path_text = f"the ordinary Unix application loader resolves this JAR entry at the same canonical URL path as the checker (UTF-8 SHA-256 {path_hash})"
        urls = [a for a in assumptions if "stock JAR handler" in a["text"]]
        require(len(urls) == 1 and urls[0]["text"].endswith(f"[{provider_index + 2}:{prior['entrySha256']}]")
                and any(a["text"] == path_text for a in assumptions), "different native path or resource bytes")
        allowed.extend([urls[0], {"basis": "engine", "kind": "library", "text": path_text}])
        summary.update(filename="spring.factories", canonicalURLPathSha256=path_hash, bytes=int(size),
                       originalFirstRead=int(first), fixedRefillCaps=[1, int(size)], entrySha256=prior["entrySha256"])
    else:
        require(actual.read_bytes() == b"1\n" and data["canonicalURLPathSha256"] is None, "different first converter or return")
        # The prior physical JVM traced the factory and the actual call to the superclass on the same core JAR.
        providers.update(read(ROOT / prior["record"])["definitions"])
        summary.update(factory=factories.converters.FACTORY, rawType="ConverterFactory", arguments=["Number", "Number"],
                       registrationReturned=True, physicalRegistration=prior["record"])
    require(all(a in allowed for a in assumptions), "unexpected assumption in the factory proof")
    expected = [binding(name, "classes", data["callerClasses"][simple], "check", "()I")]
    for binary, info in providers.items():
        jar, = [j for j in data["classpath"] if j["sha256"] == info["jarSha256"]]
        expected.append(binding(binary, Path(jar["path"]).name, info["classSha256"]))
    require(data["bindings"] == expected, "different checker-selected factory, application or typed observer")
    return summary


def fluent_evidence(job, graphs, claims, launch_record, guarded_record):
    base = fluent.DEST.relative_to(ROOT)
    record = job.output(base / "measurement.json")
    data = read(record)
    same_run(job, data, graphs["370"]["landed"], claims["fluent-names-landed"]["factorySelectors"]["checkerSha256"])
    old_launch = read(ROOT / launch_record["record"])
    old_guard = read(ROOT / guarded_record["record"])
    caller = job.output(base / "FluentWitness.jvm-bytecode")
    fluent.qualify_caller(caller.read_bytes())
    require(data["runtimeSha256"] == old_launch["runtimeSha256"] and data["environment"] == old_launch["environment"] == fluent.launch.ENV
            and data["sourceSha256"] == digest(fluent.SOURCE) and data["selector"] == 1 and data["startupUnits"] == [124]
            and set(data["claims"]) == set(fluent.METHODS) and set(data["profiles"]) == set(fluent.lines.PROFILES),
            "different public witness, launch or selector")
    expected = [binding(fluent.CALLER, "classes", digest(caller), method, "()I") for method in fluent.METHODS]
    expected.extend(b for b in old_guard["bindings"] if b["class"] != fluent.lines.CALLER)
    require(data["bindings"] == expected, "different original observers or public role hierarchy")

    independent = {}
    for profile, sep in fluent.lines.PROFILES.items():
        raw = job.output(base / (profile + ".stdout"))
        require(digest(raw) == data["profiles"][profile] and raw.read_bytes() == ("\n".join(fluent.rows(sep)) + "\n").encode()
                and old_launch["profiles"][profile]["vmOptions"] == ([] if profile == "default" else ["-Dline.separator=" + sep]),
                "different startup, names or manager decision")
        for method in fluent.METHODS:
            key = profile + "-" + method
            raw = job.output(base / (key + ".stdout"))
            expected_row = [int(sep != "|"), *map(ord, sep)]
            require(raw.read_bytes() == (" ".join(map(str, expected_row)) + "\n").encode(),
                    "fresh JVM did not execute the reported counterexample and startup in one process")
            independent[key] = digest(raw)
    require(data["independentReplays"] == independent, "incomplete fresh JVM replays")
    results = {}
    for method, original in fluent.METHODS.items():
        task = f"fluent-{method}-landed"
        row = claims[task]
        # The normal selector route validates the compiled admission and constant-call bytecode.
        direct = row["factorySelectors"]
        admitted = read(ROOT / direct["receipt"])["admitted"]
        require(row["entry"] == f"springwork.RoleChecks#{original}(I)I" and row["opening"]["binding"]["classSha256"]
                == next(b["sha256"] for b in data["bindings"] if b["method"] == original)
                and row["guard"] == "code >= 0 && code < 32" and admitted == list(range(32)) and 1 in admitted
                and row["primary"] and row["revision"] == "landed", "different original fluent claim or inadmissible input")
        replay_name = fluent.replay_name(method)
        require(job.output(base / (replay_name + ".java")).read_text() == fluent.fresh_replay(method), "different fresh JVM caller")
        fluent.qualify_replay(job.output(base / (replay_name + ".jvm-bytecode")).read_bytes(), method)
        result = data["claims"][method]
        raw = native_record(job, base, result, f"{fluent.CALLER}#{method}()")
        fluent.qualify_proof(raw.read_bytes(), method, old_guard["proofs"][1]["assumptions"])
        require(result["assumptions"] == old_guard["proofs"][1]["assumptions"], "different fluent witness assumptions")
        results[task] = {"status": "refuted", "claimKey": row["opening"]["claimKey"], "record": rel(record),
                         "nativeImplication": rel(raw), "originalEntry": row["entry"], "selector": 1,
                         "startupUnits": [124], "vmOptions": ["-Dline.separator=|"], "originalResult": 0,
                         "freshJVMReplay": rel(job.output(base / ("pipe-" + method + ".stdout")))}
    return {"record": rel(record), "selector": 1, "startupUnits": [124], "witnesses": results}


def measurements(job, cases, controls):
    graphs = read(ROOT / "verification/spring-java-data/exact-classpaths/classes.json")
    previous = controls["classTableControls"]
    result = {}
    for kind, number, name, prior_key in [("filename", "368", "beans-", "factoryStreams"),
                                          ("signature", "374", "annotated-", "formatterInterfaces")]:
        result[kind] = {side: factory_record(job, kind, side, graph, cases[number]["claims"][name + side]["factorySelectors"],
                                             previous[prior_key][side]) for side, graph in graphs[number].items()}
    result["fluent"] = fluent_evidence(job, graphs, cases["370"]["claims"], previous["fluentLaunches"],
                                       controls["startupControls"]["fluentLineSeparators"])
    return result


# Independently read from the checksummed framework JARs on both graphs.
CORE_CLASSES = {
    "properties": ("088f67674011e84609024dd189023e22a8fef3204f644a446ec2a5826ca31d72",),
    "purge": ("451dab5285706eefdf115e8941fe70d8c48d05287307e111002dd05ecbbde299",),
}
NESTED_OBSERVERS = {"properties": ["$1"], "purge": ["$Observed", "$Observed$1"], "scalars": ["$PrefixComplete", "$Registry"]}


def cache_control(job, folder, kind, side, graph, primary, prior):
    simple, observation, originals = factories.OBSERVERS[kind]
    base = folder.relative_to(ROOT) / "records" / kind / side
    record = job.output(base / "measurement.json")
    data = read(record)
    same_run(job, data, graph, primary["checkerSha256"])
    generated = [simple, *(simple + suffix for suffix in NESTED_OBSERVERS[kind])]
    require(data["sourceSha256"] == digest(folder / "companions" / (simple + ".java"))
            and set(data["callerClasses"]) == set(generated), "different refill or purge observer")
    for cls in generated:
        raw = job.output(base / (cls + ".jvm-bytecode"))
        require(digest(raw) == data["callerClasses"][cls] and runtime_jar.this_class(raw.read_bytes()) == "springwork/" + cls,
                "different compiled observer")
    caller = "springwork." + simple
    expected = [binding(caller, "classes", data["callerClasses"][simple], "check", "()I")]
    for binary, info in graph["classes"].items():
        jar, = [j for j in data["classpath"] if j["sha256"] == info["jarSha256"]]
        expected.append(binding(binary, Path(jar["path"]).name, info["classSha256"]))
    core, = [p for j in data["classpath"]
             if (p := Path(j["path"]).name).removeprefix("combined-").startswith("spring-core")]
    if kind == "scalars":
        defs = read(factories.converters.DEST / side / "measurement.json")["definitions"]
        hashes = [defs[b]["classSha256"] for b in originals]
    else:
        hashes = CORE_CLASSES[kind]
    expected.extend(binding(b, core, h) for b, h in zip(originals, hashes, strict=True))
    require(data["bindings"] == expected, "different core implementation or native entry")
    stdout = job.output(base / "jvm.stdout")
    require(digest(stdout) == data["jvmSha256"], "changed original JVM result")
    proof = data["result"]
    target = caller + "#check()"
    raw = job.output(base / "native.stdout")
    require(proof["stdout"] == "native.stdout" and proof["stderr"] == "native.stderr"
            and digest(job.output(base / "native.stderr")) == proof["stderrSha256"]
            and proof["target"] == target and proof["assertion"] == "result == 1" and proof["guard"] is None
            and proof["bounds"] == [256, 16384] and not proof["observedRoots"] and not proof["states"]
            and digest(raw) == proof["stdoutSha256"], "changed native assertion, inputs or result")
    assumptions = proof["assumptions"]
    status = factories.native(raw.read_bytes(), target, assumptions, exit_code=proof["exit"], timed_prefix=kind == "scalars")
    row, = read(raw)
    require(row["problem"] == proof["blocker"] and row["verdict"] == proof["verdict"], "different native disposition")
    summary = {"status": status, "record": rel(record), "receipt": rel(raw), "originalJVM": rel(stdout)}
    previous = read(folder / "records/factory-startup" / side / "measurement.json")["result"]["assumptions"]
    allowed = list(previous)
    if kind == "properties":
        data_hash = data["canonicalURLPathSha256"]
        require(isinstance(data_hash, str) and len(bytes.fromhex(data_hash)) == 32, "invalid resource URL digest")
        expected_stdout = observation.rstrip() + b" " + data_hash.encode() + b"\n"
        url = f"the ordinary Unix application loader resolves this JAR entry at the same canonical URL path as the checker (UTF-8 SHA-256 {data_hash})"
        expected_path = {"basis": "engine", "kind": "library", "text": url}
        resource = prior["factoryStreams"][side]
        index, = [i for i, jar in enumerate(data["classpath"]) if jar["sha256"] == resource["providerSha256"]]
        resource_scope = [a for a in assumptions if "stock JAR handler" in a["text"]]
        require(expected_path in assumptions and len(resource_scope) == 1
                and resource_scope[0]["text"].endswith(f"resources (classpath index and entry SHA-256) are [{index + 2}:{resource['entrySha256']}]"),
                "different native resource or canonical JAR path")
        allowed = [a for a in previous if "canonical URL path" not in a["text"]]
        allowed.append(expected_path)
        summary.update(resourceBytes=161, oneToThreeReadPartitions=12881, factoryKeys=1, beanInfoFactories=0)
    else:
        require(data["canonicalURLPathSha256"] is None, "unexpected resource path on a formatter proof")
        expected_stdout = observation
        if kind == "purge":
            allowed = [a for a in previous if a["kind"] == "initialization"]
            summary.update(retainedSize=1, releasedSize=0)
        else:
            summary.update(nativeTargetCompletedFactories=2, jvmCompletedBeforeEnumConverter=10)
            if status == "open":
                summary.update(firstBlocker=row["problem"], recordedGaps=row["search"].get("gaps", []),
                               exploredPaths=row["search"]["native"]["paths"], deadlineSeconds=row["search"]["deadline_seconds"])
    require(stdout.read_bytes() == expected_stdout and sorted(allowed, key=lambda a: a["text"]) == assumptions,
            "unexpected original JVM result or additional assumption")
    return summary


def refill_measurements(job, cases, prior):
    """Bind the properties and cache observations to their original classes and ordinary native receipts."""
    graphs = read(ROOT / "verification/spring-java-data/exact-classpaths/classes.json")
    summaries = {}
    for kind in factories.OBSERVERS:
        folder, _, name, sides = factories.subject(kind)
        number = folder.name.split("-", 1)[0]
        claims = cases[number]["claims"]
        summaries[kind] = {side: cache_control(job, folder, kind, side, graphs[number][side],
                                               claims[name + side]["refillSelectors"], prior) for side in sides}
    return summaries
