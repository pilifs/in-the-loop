"""Replay the later Q23 factory and the released APIs and providers related to four Q cases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
sys.path.insert(0, str(HERE.parent / "upstream"))
from targets import public_comparison as compare
from recheck import jars_for

LATER = "64861cb395e415bf1452d30f54f8e2c0ecc9cb46"
RELEASE_VARIANTS = (
    ("public-parameter-delegate", 511, "milestone-parameters", "PublicCaller",
     "org.springframework.beans.factory.annotation.ParameterResolutionDelegate", ("qualified", "extension", "containing")),
    ("relocated-jitter", 535, "current-retry", "PublicCaller",
     "org.springframework.resilience.retry.AbstractRetryInterceptor", ("oversized", "small", "duration")),
    ("message-id-replies", 531, "released-jms", "PublicCaller",
     "org.springframework.jms.core.JmsTemplate", ("owned", "temporary", "repeat")),
    ("application-id-replies", 531, "released-jms", "PublicCaller",
     "org.springframework.jms.core.JmsTemplate", ("owned", "temporary", "repeat")),
    ("reported-servlet", 524, "reported-servlet", "ServletEvents",
     "org.springframework.http.converter.json.AbstractJackson2HttpMessageConverter", ("pretty", "compact")),
    ("fixed-servlet", 524, "fixed-servlet", "ServletEvents",
     "org.springframework.http.converter.json.AbstractJackson2HttpMessageConverter", ("pretty", "compact")),
)


def context(number):
    folder, = (ROOT / "examples").glob(f"{number}-*")
    runtime = compare.read(folder / "runtime.json")
    original = compare.read(folder / "observations.json")
    sha = compare.upgrade_replay.sha
    if (original["inputs"]["caller/PublicCaller.java"] != sha(folder / "caller/PublicCaller.java")
            or original["comparisonSha256"] != sha(folder / "comparison.json")
            or original["runtimeSha256"] != sha(folder / "runtime.json")
            or original["launcherSha256"] != sha(compare.upgrade_replay.LAUNCHER)):
        raise ValueError(f"{number}: original caller, questions, or runtime differ from the measured comparison")
    jdk = Path.home() / ".sdkman/candidates/java" / runtime["jdk"]
    if sha(jdk / "release") != runtime["jdkReleaseSha256"]:
        raise ValueError(f"{number}: registered JDK differs")
    return folder, jdk, runtime


def trials(jdk, classpath, providers, caller, histories, work):
    results = {}
    for arg in histories:
        trial = work / arg
        trial.mkdir(parents=True)
        results[arg] = compare.observe(jdk, os.pathsep.join(map(str, classpath)), trial, caller, [arg], providers, label=arg)
    return results


def later_factory(work, cache):
    folder, jdk, runtime = context(530)
    spec = compare.read(folder / "comparison.json")
    physical = compare.read(folder / "observations.json")["deployments"]["pins"]
    landing = spec["revisions"]["fix"]
    git = ["git", "-C", cache / "worktrees/Q23-later"]
    header = subprocess.check_output([*git, "cat-file", "commit", LATER]).split(b"\n\n", 1)[0]
    parents = [l[7:].decode() for l in header.splitlines() if l.startswith(b"parent ")]
    if parents != ["5710c4720b8509e83b61ab891001af81b5e53a82"]:
        raise ValueError("maintainer revision differs from the setup's original commit header")
    owner = "org.springframework.web.service.invoker.HttpServiceProxyFactory"
    source = "spring-web/src/main/java/" + owner.replace(".", "/") + ".java"
    changed = subprocess.check_output([*git, "diff", "--name-only", landing, LATER, "--", "*/src/main/**"], text=True).splitlines()
    if changed != [source]:
        raise ValueError("follow-up changes more production sources than the registered factory")
    cp = compare.classpath(cache, runtime, runtime["deployments"]["pins"], "fix", work)
    caller = work / "caller"
    compare.compile_java(jdk, cp, caller, [compare.upgrade_replay.LAUNCHER, folder / "caller/PublicCaller.java"])
    if compare.class_digests(caller) != physical["callerClasses"]:
        raise ValueError("different historical service caller")
    args = [q["args"][0] for q in spec["questions"]]
    expected = dict(zip(args, [r["outcome"] for r in physical["observations"] if r["side"] == "fix"], strict=True))
    result = {"laterParent": parents[0]}
    for side, revision in (("landing", landing), ("later", LATER)):
        root = work / side
        root.mkdir()
        java = root / Path(source).name
        java.write_bytes(subprocess.check_output([*git, "show", f"{revision}:{source}"]))
        classes = root / "classes"
        compare.compile_java(jdk, cp, classes, [java], ["--release", "17", "-parameters", "-implicit:none"])
        owners = (owner, owner + "$Builder")
        listing = {c: subprocess.check_output([jdk / "bin/javap", "-c", "-p", "-classpath", classes, c]) for c in owners}
        copies = [listing[c].count(b"java/util/List.copyOf:") for c in owners]
        measured = trials(jdk, [caller, classes, cp], dict.fromkeys(owners, classes), "PublicCaller", args, root)
        if measured != expected:
            raise ValueError(f"{side}: changed advice or request processor behavior")
        result[side] = {"revision": revision, "sourceSha256": compare.upgrade_replay.sha(java),
                        "classes": compare.class_digests(classes), "copyOfCallsInFactoryAndBuilder": copies, "histories": measured}
    before = result["landing"]["copyOfCallsInFactoryAndBuilder"]
    after = result["later"]["copyOfCallsInFactoryAndBuilder"]
    if after != [before[0] + 2, before[1] - 2]:
        raise ValueError("both defensive copies must move from the builder into the factory")
    return result


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"variant no longer identifies one source fragment: {old}")
    return source.replace(old, new)


def measure(fetch=False):
    cache = Path.home() / ".cache/in-the-loop/spring-pr-links-q01-q30"
    release = compare.read(HERE / "release-inputs.json")
    extra = compare.read(HERE / "followup-inputs.json")
    sets = dict(extra["sets"])
    sets["released-jms"] = release["projects"]["531"]["versions"]["7.0.4"]
    keys = set(k for items in sets.values() for k in items)
    jars = jars_for({"modules": [], "dependencies": keys}, cache.with_name(release["cache"]), fetch,
                    {**release["sha256"], **extra["sha256"]}, cache)
    result = {"inputsSha256": compare.upgrade_replay.sha(HERE / "followup-inputs.json"),
              "releaseInputsSha256": compare.upgrade_replay.sha(HERE / "release-inputs.json"), "releases": {}}
    with tempfile.TemporaryDirectory(prefix="spring-q-followups-") as tmp:
        work = Path(tmp)
        result["laterFactory"] = later_factory(work / "factory", cache)
        for name, number, dependencies, class_name, provider, args in RELEASE_VARIANTS:
            folder, jdk, runtime = context(number)
            root = work / name
            root.mkdir()
            source = (folder / "caller/PublicCaller.java").read_text()
            if number == 511:
                # Compile the unchanged external calls on the parent first, including its Jupiter control.
                parent = compare.classpath(cache, runtime, runtime["deployments"]["pins"], "parent", root)
                check = subprocess.run([jdk / "bin/javac", "-proc:none", "-XDrawDiagnostics", "-cp", parent,
                                        "-d", root, folder / "caller/PublicCaller.java"], text=True, capture_output=True)
                inaccessible = "compiler.err.not.def.public.cant.access" in check.stderr
                if check.returncode == 0 or "AutowireUtils" not in check.stderr or not inaccessible:
                    raise ValueError("original parent did not specifically reject the external access")
                result["parentParameterCompilation"] = sorted(set(re.findall(r"compiler\.err\.[\w.]+", check.stderr)))
                source = source.replace("org.springframework.beans.factory.support.AutowireUtils", provider)
                source = source.replace("AutowireUtils.", "ParameterResolutionDelegate.")
            elif number == 535:
                source = replace_once(source, "import org.springframework.aop.retry.*;", "import org.springframework.resilience.retry.*;")
            elif number == 531:
                source = replace_once(source, "ctx.createProducer().send(target,", """ctx.createProducer().setJMSCorrelationID(
                                            request.getJMSCorrelationID() == null ? request.getJMSMessageID() : request.getJMSCorrelationID()).send(target,""")
                if name == "application-id-replies":
                    source = replace_once(source, "session -> session.createTextMessage(body);", """session -> {
                        TextMessage request = session.createTextMessage(body);
                        request.setJMSCorrelationID("request-" + body);
                        return request;
                    };""")
            else:
                source = (HERE / "ServletEvents.java").read_text()
            java = root / (class_name + ".java")
            java.write_text(source)
            ordered = sets[dependencies]
            cp = [jars[key] for key in ordered]
            # Match the actual provider by class entry. Some dependencies contain both Spring
            # and test infrastructure and the first classpath item need not own this API.
            entry = provider.replace(".", "/") + ".class"
            owners = []
            for key in ordered:
                with zipfile.ZipFile(jars[key]) as archive:
                    if entry in archive.namelist():
                        owners.append(key)
            if len(owners) != 1:
                raise ValueError(f"{name}: missing or ambiguous original provider")
            classes = root / "classes"
            compare.compile_java(jdk, os.pathsep.join(map(str, cp)), classes, [compare.upgrade_replay.LAUNCHER, java])
            measured = trials(jdk, [classes, *cp], {provider: jars[owners[0]]}, class_name, args, root)
            if class_name == "ServletEvents":
                both = {"return": "200:[A/one, B/two]"}
                expected = {"compact": both, "pretty": {"return": "200:[invalid, invalid]"} if name == "reported-servlet" else both}
            else:
                original = compare.read(folder / "observations.json")["deployments"]["pins"]["observations"]
                by_id = {row["id"]: row["outcome"] for row in original if row["side"] == "fix"}
                questions = compare.read(folder / "comparison.json")["questions"]
                expected = {question["args"][0]: by_id[question["id"]] for question in questions}
            if measured != expected:
                raise ValueError(f"{name}: released fixture returned {measured}, expected {expected}")
            result["releases"][name] = {
                "sourceSha256": hashlib.sha256(source.encode()).hexdigest(), "provider": owners[0],
                "jdkReleaseSha256": runtime["jdkReleaseSha256"], "classes": compare.class_digests(classes),
                "histories": measured}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="download missing locked Maven artifacts")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = measure(args.fetch)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    elif result != compare.read(HERE / "followup-observations.json"):
        raise SystemExit("follow-up observations differ")
    for name, measurement in result["releases"].items():
        print(name, measurement["histories"])
