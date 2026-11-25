"""Recheck the four contested public histories on Maven releases and frozen upstream branches."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import public_comparison, runtime_maven, upgrade_replay

LOCK = public_comparison.read(HERE / "inputs.json")
SETUP = Path.home() / ".cache/in-the-loop/merged-pr-links"
sha = upgrade_replay.sha


def jars_for(project, cache, fetch):
    keys = {m["artifact"] for m in project["modules"]}
    for field in ("dependencies", "headDependencies", "compileOnly"):
        keys.update(project.get(field, []))
    if "generator" in project:
        keys.add(project["generator"])
    jars = {}
    for key in sorted(keys):
        group, artifact, version, *classifier = key.split(":")
        name = "-".join([artifact, version, *classifier]) + ".jar"
        rel = Path(group.replace(".", "/")) / artifact / version / name
        dest = cache / "maven" / rel
        gradle = SETUP / "gradle-home/caches/modules-2/files-2.1" / group / artifact / version
        candidates = (dest, SETUP / "m2" / rel, Path.home() / ".m2/repository" / rel, *gradle.glob("*/" + name))
        found = next((p for p in candidates if p.is_file()), None)
        digest = LOCK["sha256"][key]
        if found is None:
            if not fetch:
                raise ValueError(f"missing {key}; --fetch retrieves the locked inputs")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
                download = Path(tmp) / name
                with urllib.request.urlopen(runtime_maven.CENTRAL + rel.as_posix(), timeout=40) as response:
                    with download.open("wb") as out:
                        shutil.copyfileobj(response, out)
                if sha(download) != digest:
                    raise ValueError(f"download differs from the lock: {key}")
                download.replace(dest)
            time.sleep(1)
            found = dest
        if sha(found) != digest:
            raise ValueError(f"{key} differs from its recorded SHA-256")
        jars[key] = found
    return jars


def source_tree(number, project, cache, work, fetch):
    repo = cache / number / "head"
    pin = project["commit"]
    git = ["git", "-c", "credential.helper=", "-C", repo]
    if not repo.is_dir() or subprocess.run(git + ["cat-file", "-e", pin + "^{commit}"],
                                            capture_output=True).returncode:
        if not fetch:
            raise ValueError(f"missing {project['repository']} at {pin}; use --fetch")
        repo.mkdir(parents=True, exist_ok=True)
        if not (repo / "HEAD").exists() and not (repo / ".git").exists():
            subprocess.run(git + ["init", "--bare", "--quiet"], check=True)
        subprocess.run(git + ["fetch", "--quiet", "--no-tags", "--depth=1",
                              f"https://github.com/{project['repository']}.git", f"{pin}:refs/campaign/{pin}"],
                       env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}, check=True, timeout=120)
        time.sleep(1)
    paths = [str(Path(m["path"]) / "src/main") for m in project["modules"]]
    if "generator" in project:
        paths.append("share/idl_grammar")
    if number == "409":
        paths.append("csv/pom.xml")
    archive = work / "source.tar"
    with archive.open("wb") as out:
        subprocess.run(git + ["archive", pin, "--", *paths], check=True, stdout=out)
    src = work / "source"
    with tarfile.open(archive) as items:
        items.extractall(src, filter="data")
    return src


def classpath(files):
    return os.pathsep.join(map(str, files))


def measure(jdk, classes, cp, histories, providers, work, label):
    outcomes = {}
    for question, observer, args in histories:
        with tempfile.TemporaryDirectory(dir=work) as trial:
            outcomes[question] = public_comparison.observe(
                jdk, classpath([classes, *cp]), Path(trial), observer, args, providers, label=f"{label} {question}")
    print(f"{label}: {len(outcomes)} public histories", flush=True)
    return {"classpath": [{"file": p.name, "sha256": sha(p)} for p in cp],
            "providers": {cls: p.name for cls, p in providers.items()}, "observations": outcomes}


def compile_java(jdk, sources, output, deps, target):
    output.mkdir(parents=True)
    subprocess.run([jdk / "bin/javac", "-J-Xmx384m", "-J-XX:-UsePerfData", "-g", "-proc:none",
                    "-encoding", "UTF-8", "--release", str(target), "-cp", classpath(deps) or str(output),
                    "-d", output, *sorted(sources)], check=True, timeout=90)


def build_module(module, src, work, jdk, deps, generator):
    name = module["name"]
    main = src / module["path"] / "src/main"
    sources = [p for p in (main / "java").rglob("*.java") if p.name != "module-info.java"]
    generated = work / name / "generated"
    if name == "csv":
        template = main / "java/tools/jackson/dataformat/csv/PackageVersion.java.in"
        version = ET.parse(main.parent.parent / "pom.xml").findtext("{*}parent/{*}version")
        data = template.read_text().replace("@projectversion@", version).replace("@package@", "tools.jackson.dataformat.csv")
        data = data.replace("@projectgroupid@", "tools.jackson.dataformat").replace("@projectartifactid@", "jackson-dataformat-csv")
        generated.mkdir(parents=True)
        (generated / "PackageVersion.java").write_text(data)
    elif name == "idl":
        grammar = src / "share/idl_grammar/org/apache/avro/idl/Idl.g4"
        subprocess.run([jdk / "bin/java", "-Xmx160m", "-jar", generator, "-Werror", "-package", "org.apache.avro.idl",
                        "-o", generated, "-Xexact-output-dir", grammar.name], cwd=grammar.parent, check=True, timeout=30)
    classes = work / name / "classes"
    compile_java(jdk, sources + list(generated.glob("*.java")), classes, deps, module["target"])
    resources = main / "resources"
    if resources.is_dir():
        shutil.copytree(resources, classes, dirs_exist_ok=True)
    jar = work / (name + ".jar")
    with zipfile.ZipFile(jar, "w") as out:
        for path in sorted(p for p in classes.rglob("*") if p.is_file()):
            out.writestr(zipfile.ZipInfo(path.relative_to(classes).as_posix()), path.read_bytes())
    return jar


def recheck(number, cache, fetch, original_wrapping=False):
    project = LOCK["projects"][number]
    folder, = public_comparison.EXAMPLES.glob(number + "-*")
    spec = public_comparison.read(folder / "comparison.json")
    registration = public_comparison.read(folder / "observations.json")
    caller = folder / "caller/PublicCaller.java"
    if (registration["inputs"]["caller/PublicCaller.java"] != sha(caller)
            or registration["launcherSha256"] != sha(upgrade_replay.LAUNCHER)
            or registration["runtimeSha256"] != sha(folder / "runtime.json")
            or registration["comparisonSha256"] != sha(folder / "comparison.json")):
        raise ValueError("historical registration, caller or launcher differs")
    jdk = Path(os.environ.get("PUBLIC_COMPARISON_JDK", Path.home() / ".sdkman/candidates/java" / LOCK["jdk"]))
    if sha(jdk / "release") != LOCK["jdkReleaseSha256"]:
        raise ValueError("JDK differs from the registered build")
    if original_wrapping:
        return original_jackson(folder, jdk)
    jars = jars_for(project, cache, fetch)
    support = [jars[k] for k in project["dependencies"]]
    head_support = [jars[k] for k in project.get("headDependencies", project["dependencies"])]
    sources = [caller, upgrade_replay.LAUNCHER]
    histories = [(q["id"], "PublicCaller", q["args"]) for q in spec["questions"]]
    if number == "409":
        sources.append(HERE / "JacksonWrapping.java")
        histories.extend((f"jackson-{s}", "JacksonWrapping", [s]) for s in ("wrapped", "tokens"))
    receipt = {"example": number, "repository": project["repository"], "branch": project["branch"],
               "commit": project["commit"], "release": project["release"], "jdkReleaseSha256": sha(jdk / "release"),
               "sources": {p.name: sha(p) for p in sources}, "variants": {}}
    with tempfile.TemporaryDirectory(prefix="merged-pr-head-") as tmp:
        work = Path(tmp)
        src = source_tree(number, project, cache, work, fetch)
        built, released = {}, {}
        extra = [jars[k] for k in project.get("compileOnly", [])]
        for module in project["modules"]:
            name = module["name"]
            # Only the IDL module needs another module built from this tree.
            local = [built["avro"]] if name == "idl" else []
            built[name] = build_module(module, src, work, jdk, local + head_support + extra, jars.get(project.get("generator")))
            released[name] = jars[module["artifact"]]
        for variant, names in project["variants"].items():
            classes = work / ("caller-" + variant)
            release_cp = [released[n] for n in names] + support
            compile_java(jdk, sources, classes, release_cp, 21)
            rows = {"callerClasses": {p.name: sha(p) for p in sorted(classes.glob("*.class"))}}
            receipt["variants"][variant] = rows
            for side, cp in (("release", release_cp), ("development", [built[n] for n in names] + head_support)):
                providers = {cls: cp[i] for cls, i in project["providers"].items()}
                rows[side] = measure(jdk, classes, cp, histories, providers, work, f"{number} {variant} {side}")
            historical = registration["deployments"][variant]["callerClasses"]
            if any(rows["callerClasses"].get(name) != digest for name, digest in historical.items()):
                raise ValueError(f"{number} {variant}: historical caller bytecode differs")
    return receipt


def original_jackson(folder, jdk):
    runtime = public_comparison.read(folder / "runtime.json")
    cache = Path(os.environ.get("PUBLIC_COMPARISON_CACHE", SETUP)).resolve()
    deploy = runtime["deployments"]["pinned"]
    histories = [("jackson-" + s, "JacksonWrapping", [s]) for s in ("wrapped", "tokens")]
    spec = public_comparison.read(folder / "comparison.json")
    sources = [HERE / "JacksonWrapping.java", upgrade_replay.LAUNCHER]
    result = {"revisions": spec["revisions"], "jdkReleaseSha256": sha(jdk / "release"),
              "sources": {p.name: sha(p) for p in sources}}
    with tempfile.TemporaryDirectory(prefix="merged-pr-wrapping-") as tmp:
        work = Path(tmp)
        paths = {s: [Path(p) for p in public_comparison.classpath(cache, runtime, deploy, s, work).split(os.pathsep)]
                 for s in public_comparison.SIDES}
        classes = work / "caller"
        compile_java(jdk, sources, classes, paths["fix"], 21)
        result["callerClasses"] = {p.name: sha(p) for p in sorted(classes.glob("*.class"))}
        for side, cp in paths.items():
            providers = {name: cp[i] for name, i in LOCK["projects"]["409"]["providers"].items()}
            result[side] = measure(jdk, classes, cp, histories, providers, work, "409 original " + side)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("examples", nargs="+", choices=LOCK["projects"])
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache/in-the-loop/merged-pr-links-followup")
    parser.add_argument("--fetch", action="store_true", help="retrieve missing locked sources and Maven artifacts")
    parser.add_argument("--record", action="store_true", help="write the complete fresh observations")
    parser.add_argument("--original-wrapping", action="store_true", help="run the two Jackson disambiguating controls on the historical setup")
    args = parser.parse_args()
    if args.original_wrapping and args.examples != ["409"]:
        parser.error("--original-wrapping applies to example 409 alone")
    for number in args.examples:
        result = recheck(number, args.cache.resolve(), args.fetch, args.original_wrapping)
        path = HERE / (number + ("-wrapping" if args.original_wrapping else "") + ".json")
        if args.record:
            path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        elif public_comparison.read(path) != result:
            raise SystemExit(f"{number}: the fresh receipt differs from {path.name}")
