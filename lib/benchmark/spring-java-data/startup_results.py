"""Validate each startup control against frozen artifacts, compiled callers and individual JVM/native results."""
import hashlib
from pathlib import Path
import tarfile

import binding_resources as resources
import fluent_lines as lines
import metadata_lookup as metadata
from measure import ROOT, digest as sha, read
from targets import native_selectors


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rel(path):
    return path.relative_to(ROOT).as_posix()


def factory_resources(job, graphs):
    result = {}
    for side in ("release", "combined"):
        base = resources.FOLDER.relative_to(ROOT) / "records/factory-resources" / side
        data = read(job.output(base / "measurement.json"))
        stdout = job.output(base / "jvm.stdout")
        graph = graphs[side]
        require(data["job"] == job.record["id"] and data["source"] == job.record["sourceCommit"]
                and data["classpath"] == graph["orderedJars"][1:] and data["jdk"] == graph["jdk"]
                and data["sourceSha256"] == sha(resources.SOURCE) and data["jvmSha256"] == sha(stdout),
                "different factory resource graph or observing JVM")
        checked = data["resources"]
        expected_jar = "spring-aop.jar" if side == "release" else "combined-spring-aop.jar"
        require(len(checked) == 1 and checked[0]["jar"] == expected_jar and checked[0]["beanInfoFactory"] == "",
                "different Spring factory provider or BeanInfoFactory declaration")
        require([[r["jar"], r["entrySha256"], r["beanInfoFactory"]] for r in checked]
                == [row.split("\t") for row in stdout.read_text().splitlines()]
                and all(r["entry"] == resources.ENTRY and any(Path(j["path"]).name == r["jar"]
                        and j["sha256"] == r["jarSha256"] for j in data["classpath"]) for r in checked),
                "different ordered factory resources")
        result[side] = {"record": rel(job.output(base / "measurement.json")), "resources": checked}

    return result


def fluent_lines(job, case, graph):
    base = lines.DEST.relative_to(ROOT)
    data = read(job.output(base / "measurement.json"))
    caller = job.output(base / "FluentLines.jvm-bytecode")
    calls = job.output(base / "Calls.jvm-bytecode")
    require(data["job"] == job.record["id"] and data["source"] == job.record["sourceCommit"]
            and data["libTree"] == job.record["jvmcontract"]["libTree"]
            and data["jdk"] == graph["jdk"] and data["classpath"] == graph["orderedJars"][1:]
            and data["sourceSha256"] == sha(lines.SOURCE) and data["callerSha256"] == sha(caller)
            and data["callsSha256"] == sha(calls) and set(data["physical"]) == set(lines.PROFILES),
            "different historical fluent caller, JDK or graph")
    native_selectors.bytecode_selectors(calls.read_bytes(), "Calls", 0, 31, (lines.CALLER, "check", "(I)I"))
    expected_bindings = [(lines.CALLER, "classes", "check", "(I)I", sha(caller))]
    for task, method in (("fluent-names-landed", "fluentNames"), ("fluent-decision-landed", "fluentDecision")):
        binding = case["claims"][task]["opening"]["binding"]
        expected_bindings.append(("springwork.RoleChecks", binding["loadedFrom"], method, "(I)I", binding["classSha256"]))
    for name, info in graph["classes"].items():
        expected_bindings.append((name, Path(graph["orderedJars"][info["jarIndex"]]["path"]).name, None, None, info["classSha256"]))
    require([(b["class"], b["provider"], b["method"], b["descriptor"], b["sha256"]) for b in data["bindings"]] == expected_bindings,
            "different authority entry or provider")
    physical = {}
    for profile, separator in lines.PROFILES.items():
        stdout = job.output(base / (profile + ".stdout"))
        rows = stdout.read_text().splitlines()
        require(sha(stdout) == data["physical"][profile] and rows == lines.expected(separator),
                "different JVM separator or authority outcomes")
        cols = [list(map(int, row.split())) for row in rows[1:]]
        physical[profile] = {"receipt": rel(stdout), "reachableNamesAgree": sum(row[1] for row in cols),
                             "decisionsAgree": sum(row[2] for row in cols)}
    ordinary = case["claims"]["legacy-decision-landed"]["cacheSelectors"]["assumptions"]
    proofs = data["proofs"]
    expected = [f"cases/{i}/native.json" for i in range(32)]
    require([r["selector"] for r in proofs] == list(range(32)), "different fluent selector coverage")
    with tarfile.open(job.output(base / "cases.tar.gz")) as archive:
        require(archive.getnames() == expected, "missing or duplicate fluent proof")
        for i, (name, row) in enumerate(zip(expected, proofs, strict=True)):
            raw = archive.extractfile(name).read()
            target = f"{native_selectors.PACKAGE}.Calls#{native_selectors.case_name(i)}()"
            require(row["status"] == "established" and row["exit"] == 0 and row["target"] == target
                    and all(fact in ordinary for fact in row["assumptions"])
                    and row["rawSha256"] == hashlib.sha256(raw).hexdigest() and row["assumptions"] == lines.qualify(raw, i),
                    "different fluent selector, scope or raw verdict")
    return {"record": rel(job.output(base / "measurement.json")), "checked": len(proofs), "checkerSha256": data["checkerSha256"],
            "guard": "System.lineSeparator() equals LF or CRLF", "physical": physical}


def metadata_cases(job, case, graphs, checker):
    result = {}
    for side in ("parent", "landed"):
        base = metadata.DEST.relative_to(ROOT) / side
        data = read(job.output(base / "measurement.json"))
        stdout = job.output(base / "jvm.stdout")
        graph = graphs[side]
        require(data["job"] == job.record["id"] and data["source"] == job.record["sourceCommit"]
                and data["libTree"] == job.record["jvmcontract"]["libTree"] and data["checkerSha256"] == checker
                and data["sourceSha256"] == sha(metadata.OBSERVER)
                and data["classpath"] == graph["orderedJars"][1:] and data["jdk"] == graph["jdk"]
                and data["profile"] == metadata.SETTINGS and data["observedRoot"] == metadata.ROOT_CLASS
                and stdout.read_text().splitlines() == metadata.physical_rows(side) and sha(stdout) == data["jvmSha256"]
                and set(data["tasks"]) == {"components", "getters"}, "different scoped metadata run")
        provider = data["bindings"][-1]
        property_class = graph["classes"]["org.springframework.core.convert.Property"]
        original_core = Path(graph["orderedJars"][property_class["jarIndex"]]["path"]).name
        require(provider["class"] == metadata.ROOT_CLASS and provider["provider"] == original_core
                and provider["entry"] == metadata.ROOT_CLASS.replace(".", "/") + ".class" and provider["method"] is None,
                "different provider of the recorded initializer")
        binds = [(b["class"], b["provider"], b["method"], b["descriptor"], b["sha256"]) for b in data["bindings"][:-1]]
        expected_bindings = []
        for name, info in graph["classes"].items():
            jar = Path(graph["orderedJars"][info["jarIndex"]]["path"]).name
            for method in (["components", "getters"] if name == "springwork.Accessors" else [None]):
                expected_bindings.append((name, jar, method, "(I)I" if method else None, info["classSha256"]))
        require(binds == expected_bindings, "different historical Property or getter entry")
        rows = {}
        for method, task in data["tasks"].items():
            expected = case["claims"][method + "-" + side]
            assertion = read(metadata.FOLDER / "claims" / (method + ".json"))["assert"]
            ordinary = expected["cacheSelectors"]["assumptions"]
            wrappers = job.output(base / method / "Calls.jvm-bytecode")
            native_selectors.bytecode_selectors(wrappers.read_bytes(), "Calls", 0, 2, ("springwork.Accessors", method, "(I)I"))
            require(sha(wrappers) == task["callsSha256"] and set(task["selectors"]) == {"0", "1", "2"}
                    and expected["frozenInputs"] == 3, "different metadata selector coverage")
            selected = []
            for i in range(3):
                item = task["selectors"][str(i)]
                target = f"{native_selectors.PACKAGE}.Calls#{native_selectors.case_name(i)}()"
                rawfile = job.output(base / method / item["stdout"])
                raw, = read(rawfile)
                stated = raw["stated"]
                require(item["target"] == raw["target"] == target and item["verdict"] == raw["verdict"]
                        and raw.get("assume") is None and raw["assert"] == assertion == "result == 1"
                        and raw["problem"] == item["blocker"] and item["assumptions"] == stated["assumptions"]
                        and stated["checker"]["engine"] == "native" and stated["checker"]["fallback"] is None
                        and stated["gap_mode"] == "strict" and not stated["domain"]["parameters"] and not stated["domain"]["shared_arrays"]
                        and not raw["throws"] and stated["observations"]["exceptions"] == "none may be thrown"
                        and stated["bounds"]["unwind"] == expected["bounds"]["unwind"]
                        and raw["search"]["max_array_length"] == expected["bounds"]["maxArrayLength"]
                        and item["observedRoots"] == [metadata.ROOT_CLASS] and sha(rawfile) == item["stdoutSha256"],
                        "different scoped native metadata assertion or output")
                require(all(a in ordinary for a in stated["assumptions"] if not a.get("id", "").startswith("observed-initializer:")),
                        "unexpected assumption alongside the recorded ClassUtils initializer")
                facts = [a["id"].split(":") for a in stated["assumptions"] if a.get("id", "").startswith("observed-initializer:")]
                require(len(facts) == 1 and facts[0][1:3] == [metadata.ROOT_CLASS, provider["sha256"]]
                        and item["states"] == {metadata.ROOT_CLASS: facts[0][3]}, "different initialized class or captured state")
                physical_value = int(metadata.physical_rows(side)[i + (3 if method == "getters" else 0)].split("\t")[-1])
                verdict = raw["verdict"]
                if verdict == "verified":
                    require(item["exit"] == 0 and physical_value == 1 and stated["bounds"]["complete"]
                            and stated["vacuity"]["status"] == "non-vacuous" and not raw["problem"], "incomplete qualified proof")
                elif verdict == "violation":
                    replay = native_selectors.checker_output.wire.facts(raw)
                    require(replay["reproduced"] is True and replay["replayedBy"] == "jvm",
                            "the original metadata violation has no JVM replay")
                    require(item["exit"] == 1 and physical_value == 0 and raw["counterexample"]["inputs"] == []
                            and raw["counterexample"]["outcome"] == "0", "metadata witness disagrees with original JVM")
                else:
                    require(verdict == "unverifiable" and raw["problem"], "unqualified native metadata outcome")
                selected.append({"selector": i, "verdict": verdict, "jvmResult": physical_value,
                                 "firstBlocker": raw["problem"], "capturedStateSha256": facts[0][3], "receipt": rel(rawfile)})
            rows[method] = selected
        result[side] = {"record": rel(job.output(base / "measurement.json")),
                        "lookupProviderSha256": provider["sha256"], "tasks": rows}
    return result


def measured_controls(job, cases):
    require(job.record["status"] == "passed", "incomplete Spring startup controls")
    graphs = read(ROOT / "verification/spring-java-data/exact-classpaths/classes.json")
    fluent = fluent_lines(job, cases["370"], graphs["370"]["landed"])
    return {"factoryResources": factory_resources(job, graphs["368"]), "fluentLineSeparators": fluent,
            "metadataWithClassUtils": metadata_cases(job, cases["372"], graphs["372"], fluent["checkerSha256"])}
