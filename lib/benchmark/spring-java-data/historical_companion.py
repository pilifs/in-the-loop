"""Bind a companion caller to one original JAR and check the scope of its native proof."""
import os
from pathlib import Path
import shutil
import subprocess

from measure import ROOT, digest, read
from targets import class_binding, runtime_jdk

CLASSPATH = ["classes", "original.jar"]
LOADED = ROOT / "examples/tools/targets/java/LoadedClasses.java"


def prepare(folder, side, work, original, sources):
    number = folder.name.split("-", 1)[0]
    prior = read(ROOT / "verification/spring-java-data/exact-classpaths/classes.json")[number][side]
    build = read(folder / f"records/setup/build-{side}.json")
    artifact, = build["artifacts"]
    jdk = Path(runtime_jdk.home("21"))
    java = runtime_jdk.release(jdk)["JAVA_RUNTIME_VERSION"]
    classes, jar = [work / name for name in CLASSPATH]
    shutil.copyfile(original, jar)
    if (java != prior["jdk"]["JAVA_RUNTIME_VERSION"] or build["recipe"]["commit"] != prior["commit"]
            or digest(jar) != artifact["sha256"] or prior["orderedJars"][-1]["sha256"] != artifact["sha256"]):
        raise ValueError("the companion requires the original JVM and historical module")
    classes.mkdir()
    subprocess.run([jdk / "bin/javac", "-J-XX:-UsePerfData", f"-J-Djava.io.tmpdir={work}",
                    "--release", "21", "-parameters", "-proc:none",
                    "-cp", jar, "-d", classes, *sources], check=True)
    env = dict(os.environ, JAVA_HOME=str(jdk), JVMCONTRACT_JAR_RELEASE="21",
               PATH=str(jdk / "bin") + os.pathsep + os.defpath)
    return jdk, env, classes, jar, prior


def bind(checker, env, work, side, bindings):
    requests = [{"class": name, "method": method, "descriptor": desc} for name, method, desc, _, _ in bindings]
    paths = [str(work / entry) for entry in CLASSPATH]
    answer, release = class_binding.ask(checker, env, work, {side: {"classpath": paths, "classes": requests}})
    if release != 21:
        raise ValueError("different bytecode release")
    selected = []
    for bound, (name, method, desc, provider, sha) in zip(answer[side]["bindings"], bindings, strict=True):
        problem = class_binding.disagreement(name, bound, str(provider), sha)
        if problem:
            raise ValueError(problem)
        if method and (not bound["method"]["declared"] or bound["method"]["descriptor"] != desc):
            raise ValueError(f"{name}.{method}: the entry is missing from the selected class")
        selected.append({"class": name, "provider": Path(bound["provider"]).name, "entry": bound["entry"],
                         "sha256": bound["sha256"], "method": method, "descriptor": desc})
    return selected


def check_ordinary(outcome, method, parameters, guard, bounds):
    stated = outcome["stated"]
    params = [{"name": name, "type": kind, "kind": "primitive", "null": False} for name, kind in parameters]
    assumptions = [{"kind": "precondition", "text": guard, "basis": "stated"}] if guard else []
    assumptions.append({"kind": "initialization", "basis": "engine", "text":
                        "every JDK class is initialized already, its static initializer having run and thrown nothing"})
    if (outcome["target"] != method or outcome["assume"] != guard or outcome["assert"] != "result == 1"
            or stated["domain"]["parameters"] != params or stated["domain"]["shared_arrays"]
            or stated["assumptions"] != assumptions or outcome["throws"]
            or stated["observations"]["exceptions"] != "none may be thrown"
            or stated["checker"]["engine"] != "native" or stated["checker"]["fallback"] is not None
            or stated["gap_mode"] != "strict" or stated["vacuity"]["status"] != "non-vacuous"
            or outcome["verdict"] != "verified" or outcome["problem"] or outcome["counterexample"]
            or stated["bounds"] != {"complete": True, "unwind": bounds[0], "max_array_length": None}
            or outcome["search"]["max_array_length"] != bounds[1] or outcome["search"]["unwind"] != bounds[0]
            or outcome["search"]["engine"] != "native" or outcome["search"]["gap_mode"] != "strict"):
        raise ValueError(f"missing complete ordinary strict proof of {method} over its declared scalar domain")
