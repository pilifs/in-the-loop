"""Prepare one reviewed ordinary unit method per side on the applicable original test dependency graph."""
import argparse
from collections import Counter
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
import zipfile

from eligibility_inventory import BATCHES, CACHE, HERE, ROOT, digest, read, worktree, write
from functional_scope import risk, safe_test, categories
from packet_view import CODE_OR_COMMENT, PreparationStop, scan_jar, upstream_test_classes


MAX_ROOTS = 256
MAX_BYTES = 384 * 1024**2
JUNIT = re.compile(r"junit-(?:platform-(?:console(?:-standalone)?|launcher)|4\.)|testng-", re.I)
METHOD = re.compile(r"@(?:org\.junit\.(?:jupiter\.api\.)?)?Test\b(?:\s*\(\s*\))?\s+"
                    r"(?:(?:public|final)\s+)*void\s+(\w+)\s*\(\s*\)\s*(?:throws\s+[\w.,\s]+)?\{")
LIFECYCLE = re.compile(r"@(?:Before\w*|After\w*|RunWith|ExtendWith|Rule|ClassRule|Nested|TestInstance|ParameterizedTest|TestFactory|Enabled\w*|Disabled)\b")


def cp_lists(area, slot, side):
    folder = area / "artifacts" / f"{slot}-{side}"
    return sorted(p for p in folder.glob("**/*.txt") if "test" in p.name.lower() and "classpath" in p.name.lower()
                  and ".raw." not in p.name.lower())


def entries(path):
    return [Path(s) for s in path.read_text().strip().replace("\r", "").replace("\n", os.pathsep).split(os.pathsep) if s]


def choose_list(lists, path):
    modules = set(PurePosixPath(path).parts)
    named = [p for p in lists if p.name.split(".", 1)[0] in modules]
    if len(named) == 1:
        return named[0]
    return lists[0] if len(lists) == 1 else None


def nominations(src, path, category, source_stems):
    name = PurePosixPath(path)
    if name.suffix != ".java" or LIFECYCLE.search(src) or not safe_test(src.encode(), category):
        return []
    package = re.search(r"\bpackage\s+([\w.]+)\s*;", src)
    if not package or not re.search(r"\bclass\s+" + re.escape(name.stem) + r"\s*\{", src):
        return []
    if "org.junit.jupiter.api.Test" in src:
        framework = "JUnit Jupiter"
    elif "org.junit.Test" in src:
        framework = "JUnit 4"
    else:
        return []
    # Preserve character positions for matching balanced method bodies. Separately
    # review the original bytes, including literals, before selecting the unit method.
    masked = CODE_OR_COMMENT.sub(lambda m: " " * len(m[0]), src)
    result = []
    for item in METHOD.finditer(masked):
        depth = 1
        pos = item.end()
        while pos < len(masked) and depth:
            depth += (masked[pos] == "{") - (masked[pos] == "}")
            pos += 1
        body = src[item.start():pos]
        if depth or len(body) > 5000 or risk(body) or category not in categories(item[1] + " " + body):
            continue
        if not any(re.search(r"\b" + re.escape(stem) + r"\b", body) for stem in source_stems):
            continue
        result.append((package[1]+"."+name.stem, item[1], framework))
    return result


def original_graph(path, cache, original_cp, packet, known_tests):
    cp = entries(path)
    if not cp or len(cp) + 1 > MAX_ROOTS:
        raise PreparationStop("missing or over-budget original test runtime list")
    if any(not p.is_absolute() or not p.resolve().is_relative_to(cache.resolve()) or not p.is_file() or p.suffix != ".jar" for p in cp):
        raise PreparationStop("the original test runtime includes missing, external or unpackaged roots")
    if not any(JUNIT.search(p.name) for p in cp):
        raise PreparationStop("the retained original runtime lacks a recognized unit-test launcher")
    if sum(p.stat().st_size for p in cp) > MAX_BYTES:
        raise PreparationStop("the original test runtime exceeds the frozen dependency byte budget")
    if any(re.search(r"-(?:tests|test-fixtures)(?:[-.]|$)", p.name, re.I) for p in cp):
        raise PreparationStop("the runtime includes additional unreviewed upstream test fixtures")
    neutral = {item["sha256"]: item["file"] for d in (packet["old"], packet["new"]) for item in d["classpath"]}
    ordered, needed = [], {}
    for source in cp:
        checksum = digest(source)
        if checksum in neutral:
            rel = neutral[checksum]
        else:
            scan_jar(source, known_tests)
            rel = f"test-runtime/{digest(path)}/{checksum}.jar"
            needed[checksum] = source
        ordered.append({"file": rel, "sha256": checksum})
    if needed:
        graph = packet["_folder"] / "test-runtime" / digest(path)
        if not graph.exists():
            with tempfile.TemporaryDirectory(prefix="approved-test-originals-", dir=packet["_folder"].parent) as tmp:
                staged = Path(tmp) / "graph"
                staged.mkdir()
                for checksum, source in needed.items():
                    target = staged / (checksum+".jar")
                    shutil.copyfile(source, target)
                    if digest(target) != checksum:
                        raise PreparationStop("original test dependency changed during export")
                graph.parent.mkdir(exist_ok=True)
                staged.rename(graph)
    if original_cp[0]["sha256"] not in {r["sha256"] for r in ordered}:
        # These are dependency-configuration exports. The original subject output
        # precedes them in the test process, just after the freshly compiled unit test.
        ordered.insert(0, original_cp[0])
    return ordered


def add_trace_inputs(folder, packet, row, decision):
    area = CACHE / BATCHES[row["batch"]][3]
    tree = worktree(area, row["slot"], "fix")
    known_tests = upstream_test_classes(tree, row["pins"])
    stems = {PurePosixPath(s["file"]).stem for s in packet["productionSources"]}
    verified = dict(packet, _folder=folder)
    launches, states = [], {}
    for side, role in (("old", "parent"), ("new", "fix")):
        lists = cp_lists(area, row["slot"], role)
        state = {"approvedSourceFiles": 0, "approvedUnitMethods": 0, "recordedRuntimeLists": len(lists),
                 "sourceCompiled": False, "traceObserved": False}
        states[side] = state
        for item in (s for s in packet.get("upstreamTests", []) if s["side"] == side):
            file = folder / item["file"]
            original = item["file"].split("/", 2)[2]
            if item["sha256"] not in decision["approvedTests"][side] or digest(file) != item["sha256"]:
                raise ValueError("trace nomination does not match a reviewed test source")
            state["approvedSourceFiles"] += 1
            methods = nominations(file.read_text(errors="replace"), original, decision["functionalClass"], stems)
            state["approvedUnitMethods"] += len(methods)
            if not methods or any(x["side"] == side for x in launches):
                continue
            path = choose_list(lists, original)
            if not path:
                state["reason"] = "no unambiguous original test runtime for this source module"
                continue
            try:
                cp = original_graph(path, area, packet[side]["classpath"], verified, known_tests)
            except (PreparationStop, zipfile.BadZipFile):
                state["reason"] = "the complete original ordered test dependency graph could not be safely supplied"
                continue
            cls, method, framework = methods[0]
            launches.append({"side": side, "source": item["file"], "sha256": item["sha256"],
                             "sourceSha256": item["sha256"], "class": cls, "method": method, "framework": framework,
                             "classpath": cp, "originalClasspathListSha256": digest(path),
                             "compilation": "requires recompilation of this exact original selected source"})
            state["reason"] = "one original zero-argument method available for isolated compilation and tracing"
        state.setdefault("reason", "no affirmatively reviewed, independently launchable original unit method")
    packet["approvedTestLaunches"] = launches
    packet["testTraceAvailability"] = states


def trace_summary(folder, packet, output):
    """Rejoin emitted witnesses to the raw per-fork events, test bytecode and original class bytes."""
    sys.path.insert(0, str(ROOT / "examples/tools"))
    from targets import public_histories, runtime_jdk, runtime_jar
    result = read(output / "trace.json")
    if (result.get("schema") != "approved-original-unit-trace/v1" or result["url"] != packet["url"]
            or result["jdkReleaseSha256"] != packet["jdkReleaseSha256"]
            or result["artifacts"] != {s: [v["sha256"] for v in packet[s]["classpath"]] for s in ("old", "new")}):
        raise ValueError("upstream trace is not bound to this URL, original JDK and ordered classpaths")
    allowed = {(row["side"], row["class"]+"#"+row["method"]): row for row in packet["approvedTestLaunches"]}
    feature = int(runtime_jdk.feature(runtime_jdk.release(Path(packet["jdk"]))["JAVA_VERSION"]))
    counts = {"approved": len(allowed), "recompiledOriginalTests": 0, "parityRuns": 0,
              "boundTraceRuns": 0, "qualifiedWitnesses": 0, "plainOrTracedJVMs": 0, "workerStops": len(result.get("stops", []))}
    seen = set()
    for run in result["runs"]:
        side = run["side"]
        identity = (side, run["test"])
        selected = allowed.get(identity)
        if (not selected or identity in seen or run["sourceSha256"] != selected["sha256"]
                or run.get("plainParity") is not True or not run["outcomes"]["plain"]
                or run["outcomes"]["plain"] != run["outcomes"]["traced"]):
            raise ValueError("unexpected upstream method or missing plain-versus-traced parity")
        seen.add(identity)
        test_name = selected["class"].replace(".", "/")
        test_hash = run["compiledTestSet"].get(test_name+".class")
        if not test_hash or not re.fullmatch("[a-f0-9]{64}", test_hash) or not run["forks"]:
            raise ValueError("the selected original unit test has no compiled identity or fork record")
        derived = set()
        test_loaded = False
        with zipfile.ZipFile(output / (side+"-original-test.zip")) as archive:
            for fork in run["forks"]:
                name = PurePosixPath(fork["rawFile"])
                if (len(name.parts) != 1 or name.suffix != ".events" or fork["stop"] is not None
                        or fork["revision"] != packet[side+"Revision"] or fork["jdkReleaseSha256"] != packet["jdkReleaseSha256"]):
                    raise ValueError("upstream trace fork lost its original revision, JDK or stream boundary")
                events, loads, image = [archive.read(name.with_suffix(suffix).as_posix()) for suffix in (".events", ".loads", ".classes")]
                if [hashlib.sha256(v).hexdigest() for v in (events, loads, image)] != [
                        fork["rawSha256"], fork["loadOriginsSha256"], fork["classBytesSha256"]]:
                    raise ValueError("raw trace, class-load origins or defining bytes differ from the fork seal")
                seq = []
                for data in events.decode().splitlines():
                    fields = data.split("\t")
                    if fields[0] == "CLASS":
                        cls, start, size = fields[1:]
                        contents = image[int(start):int(start)+int(size)]
                        binding = fork["classes"][cls]
                        if len(contents) != int(size) or hashlib.sha256(contents).hexdigest() != binding["classSha256"]:
                            raise ValueError("traced original class bytes differ")
                        if binding["owner"] == test_name and binding["upstreamTest"] and binding["classSha256"] == test_hash:
                            test_loaded = True
                    elif fields[0].isdigit():
                        if int(fields[0]) != len(seq) + 1:
                            raise ValueError("noncontiguous original unit-test trace")
                        seq.append(fields[1:])
                if len(seq) != fork["events"]:
                    raise ValueError("upstream event count differs from original stream")
                for h in public_histories.witnesses(dict(fork, sequence=seq)):
                    owner, mark, sig = h["entry"].partition("#")
                    frame = h.get("frame") or h.get("publicCall") or {}
                    b = fork["classes"].get(str(frame.get("loader"))+":"+owner, {})
                    provider = b.get("originalProvider")
                    if not mark or not provider:
                        continue
                    idx = provider["providerIndex"]
                    cp = packet[side]["classpath"]
                    if type(idx) is not int or not 0 <= idx < len(cp) or cp[idx]["sha256"] != provider["artifactSha256"]:
                        raise ValueError("traced original provider index differs from the packet")
                    data = runtime_jar.effective_class(folder / cp[idx]["file"], owner, feature)
                    if not data or hashlib.sha256(data).hexdigest() != b["classSha256"]:
                        raise ValueError("traced original member is not defined by the bound release bytes")
                    derived.add((owner.replace("/", ".")+"#"+sig, h["changed"], h["relationship"], h["hitEvent"],
                                 frame["loader"], b["classSha256"], idx, cp[idx]["sha256"]))
        if not test_loaded:
            raise ValueError("the selected upstream test class did not load with its compiled digest")
        for witness in run["witnesses"]:
            key = tuple(witness[k] for k in ("entry", "changed", "relationship", "hitEvent", "loader", "classSha256", "providerIndex", "artifactSha256"))
            if key not in derived or witness["side"] != side or witness["test"] != selected["class"]+"#"+selected["method"]:
                raise ValueError("published public history lacks its scoped original upstream test witness")
        counts["recompiledOriginalTests"] += 1
        counts["parityRuns"] += 1
        counts["plainOrTracedJVMs"] += 2
        counts["boundTraceRuns"] += bool(run["witnesses"])
        counts["qualifiedWitnesses"] += len(run["witnesses"])
    return counts


def inventory(output):
    rows = [r for r in read(HERE / "eligibility.json")["rows"] if r["eligible"]]
    result = {}
    for row in rows:
        batch = row["batch"]
        count = result.setdefault(batch, Counter())
        count["eligible"] += 1
        area = CACHE / BATCHES[batch][3]
        sides = []
        for side in ("parent", "fix"):
            lists = cp_lists(area, row["slot"], side)
            graphs = [entries(p) for p in lists]
            all_present = [g for g in graphs if g and all(p.is_absolute() and p.exists() for p in g)]
            art = area / "artifacts" / f"{row['slot']}-{side}"
            compiled = any(any(n in str(p) for n in ("/classes/java/test/", "/classes/kotlin/test/", "/test-classes/"))
                           for p in art.rglob("*.class"))
            tree = worktree(area, row["slot"], side)
            compiled |= any(p.is_dir() and next(p.rglob("*.class"), None) is not None
                            for pattern in ("*/target/test-classes", "target/test-classes", "*/build/classes/java/test", "build/classes/java/test", "*/build/classes/kotlin/test")
                            for p in tree.glob(pattern))
            sides.append((bool(lists), bool(all_present), any(any(JUNIT.search(p.name) for p in g) for g in all_present), compiled))
        for i, k in enumerate(("bothRecordedTestRuntime", "bothListsWithExistingPaths", "bothRecognizedLauncher", "bothStandardCompiledTestTree")):
            count[k] += all(s[i] for s in sides)
    write(output, {"schema": "blind-original-test-availability/v1", "recordedAtPreregistration": False,
                   "scope": "Eligible population only. Source availability and a cached dependency list confer no test or trace result.",
                   "counts": result, "testBudget": {"perSideMethods": 1, "maxOriginalRoots": MAX_ROOTS, "maxDependencyBytes": MAX_BYTES}})
    print(dict(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    inventory(parser.parse_args().inventory)
