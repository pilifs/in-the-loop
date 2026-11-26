"""Qualify an ordered deployment against a non-initializing JVM lookup and the native resolver."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit

from targets import class_binding, entry_discovery, runtime_jar, runtime_jdk, upgrade_replay
from targets.change_inventory import digest


def request(entry):
    if "#" not in entry:
        return {"class": entry}
    owner, name, descriptor = runtime_jar.parse_target(entry)
    if not descriptor:
        raise ValueError(f"an exact descriptor is required for {entry}")
    return {"class": owner, "method": name, "descriptor": descriptor}


def observe(jdk, compiled, files, queries):
    cp = os.pathsep.join(map(str, [compiled, *files]))
    lines = ["\t".join(q.get(k, "") for k in ("class", "method", "descriptor")) for q in queries]
    env = {"PATH": str(jdk / "bin") + ":/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC"}
    result = subprocess.run([jdk / "bin/java", "-Xmx128m", "-XX:-UsePerfData", "-cp", cp,
                             "UpgradeClassLookup", "--entries"], cwd=compiled, env=env, text=True,
                            input="\n".join(lines) + "\n", capture_output=True, check=True, timeout=60)
    observations = []
    for line in result.stdout.splitlines():
        if not line.startswith("ENTRY\t"):
            continue
        _, owner, name, desc, status, origin, member, sha, defining, implementation, kind, initiating = line.split("\t")
        observations.append({"owner": owner, "method": name, "descriptor": desc, "status": status,
                             "codeSource": origin, "physicalEntry": member, "sha256": sha,
                             "definingLoader": defining, "declaringClass": implementation, "invocation": kind,
                             "initiatingLoader": initiating})
    if [(o["owner"], o["method"], o["descriptor"]) for o in observations] != [
            (q["class"], q.get("method", ""), q.get("descriptor", "")) for q in queries]:
        raise ValueError("the original JVM did not answer every requested selector in order")
    return observations


def qualify(checker, graphs, entries, *, measurements=None):
    """One JVM per named launch and one checker batch per JDK (separate observed MR bindings as needed)."""
    records, groups = {}, {}
    if measurements is None:
        measurements = {}
    measurements.update(jvmProbes=0, checkerBatches=0)
    with tempfile.TemporaryDirectory(prefix="entry-bind-") as tmp:
        root = Path(tmp)
        for side, (files, launch, jdk) in graphs.items():
            selectors = sorted(set(entries[side]))
            records[side] = {}
            if not selectors:
                continue
            for entry in selectors:
                records[side][entry] = {
                    "schema": "java-entry-binding/v1", "revision": launch.get("commit"), "side": side,
                    "profile": launch["kind"], "graph": launch["key"], "entry": entry, "status": "open"}
            unresolved = launch.get("manifestClassPath", {}).get("unresolved", [])
            if unresolved:
                for record in records[side].values():
                    record["firstOpenDependency"] = unresolved[0]
                continue
            compiled = root / digest(str(jdk))[:16]
            if not compiled.exists():
                compiled.mkdir()
                subprocess.run([jdk / "bin/javac", "-proc:none", "-d", compiled, upgrade_replay.LOOKUP],
                               cwd=compiled, check=True, capture_output=True, timeout=30)
            queries = [request(e) for e in selectors]
            measurements["jvmProbes"] += 1
            observations = observe(jdk, compiled, files, queries)
            for entry, seen in zip(selectors, observations, strict=True):
                records[side][entry]["jvm"] = seen
            groups.setdefault(jdk, {})[side] = {"classpath": list(map(str, files)), "classes": queries}
        for jdk, batch in groups.items():
            feature = int(runtime_jdk.identity(jdk)["feature"])
            env = {**os.environ, "JAVA_HOME": str(jdk), "JVMCONTRACT_JAR_RELEASE": str(feature)}
            env.pop("JVMCONTRACT_CLASS_OBSERVATIONS", None)
            measurements["checkerBatches"] += 1
            answers, release = class_binding.ask(checker, env, root, batch)
            if release is not None and release != feature:
                raise ValueError("checker selected a different JDK release")
            for side, response in answers.items():
                files, launch, _ = graphs[side]
                pairs = list(records[side].items())
                # Folded multi-release manifests may require the observed class digest. Each side owns its own file.
                if any("refused" in b and b["refused"]["code"] == "ambiguous-manifest"
                       for b in response["bindings"]):
                    observed = {r["jvm"]["owner"]: r["jvm"]["sha256"] for _, r in pairs if r["jvm"]["status"] == "bound"}
                    pin = root / ("observations-" + digest(side)[:12] + ".json")
                    pin.write_text(json.dumps({"feature": feature, "classes": observed}))
                    measurements["checkerBatches"] += 1
                    retry, _ = class_binding.ask(checker, {**env, "JVMCONTRACT_CLASS_OBSERVATIONS": str(pin)},
                                                 root, {side: batch[side]})
                    response = retry[side]
                for (entry, record), selected in zip(pairs, response["bindings"], strict=True):
                    seen = record["jvm"]
                    record["checker"] = selected
                    if "method" in selected and selected["method"].get("access") is not None:
                        record["declarationFlags"] = entry_discovery.access(selected["method"]["access"])
                    owner = seen["owner"]
                    if seen["status"] != "bound":
                        problem = f"{side}: JVM public lookup of {entry}: {seen['status']}"
                    else:
                        source = Path(unquote(urlsplit(seen["codeSource"]).path))
                        problem = class_binding.disagreement(owner, selected, source, seen["sha256"])
                        if not problem and selected["entry"] != seen["physicalEntry"]:
                            problem = f"{side}: JVM selected {seen['physicalEntry']}, checker selected {selected['entry']}"
                        if not problem and seen["method"] and not selected["method"]["declared"]:
                            problem = f"{side}: {entry} resolves to {seen['declaringClass']}; checker requires a declared method"
                        if not problem:
                            index = selected["index"]
                            if index >= len(files) or files[index] != source:
                                problem = f"{side}: observed code source is outside the ordered launch"
                            else:
                                record.update(status="bound", providerIndex=index, provider=str(files[index]),
                                              artifactSha256=launch["classpath"][index]["sha256"],
                                              physicalEntry=seen["physicalEntry"], classSha256=seen["sha256"])
                    if problem:
                        record["firstOpenDependency"] = problem
    return records
