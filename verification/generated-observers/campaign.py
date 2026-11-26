"""Run the public product entry points on previously registered deployments and retain small, auditable receipts."""
import argparse
import gzip
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_evidence, change_inventory, observer_generation, upgrade_replay

write = change_evidence.write_json
read = lambda p: json.loads(p.read_bytes())
CACHE = Path.home() / ".cache/in-the-loop"
JDKS = Path.home() / ".sdkman/candidates/java"


def prepare(number, work):
    if number in {"06", "09"}:
        packet = CACHE / "generated-observers-and-callers/probes/successor/packets" / number
        graph = json.loads(gzip.decompress((ROOT / "verification/beyond-jbmc/successor/deployments" / (number + ".json.gz")).read_bytes()))
        jdk = JDKS / "21.0.13.0+9-tem"
        for side in ("old", "new"):
            rows = graph[side]["classpath"]
            pinned = [{"path": r["path"], "sha256": r["sha256"]} for r in rows]
            if pinned != read(packet / "inputs.json")[side]:
                raise ValueError("original packet differs from the signed distribution")
            write(work / (side + ".json"), {"classpath": [{"file": str(packet / r["path"]), "sha256": r["sha256"]} for r in rows],
                "jdkReleaseSha256":upgrade_replay.sha(jdk/"release"), "scope":"signed successor distribution graph",
                "jvmFlags":["-ea","-Xmx512m","-XX:-UsePerfData","-Djava.awt.headless=true","-Duser.language=en",
                            "-Duser.country=US","-Duser.timezone=UTC","-Dfile.encoding=UTF-8"]})
        return jdk
    if number.isdigit() and len(number) == 3:
        example = next((ROOT / "examples").glob(number + "-*"))
        runtime = read(example / "runtime.json")
        commits = read(example / "comparison.json")["revisions"]
        deploy = runtime["deployments"]["pins"]
        for side, original in (("old", "parent"), ("new", "fix")):
            cp = [{"file": str(CACHE / runtime["cache"] / p), "sha256": runtime["sha256"][p]}
                  for p in deploy["classpath"][original]]
            write(work / (side + ".json"), {"commit": commits[original], "classpath": cp,
                "jdkReleaseSha256": runtime["jdkReleaseSha256"], "scope": "original numbered public-comparison deployment"})
        return JDKS / runtime["jdk"]
    if number == "io":
        folder = ROOT / "lib/benchmark/organic-composition/io"
        for side in ("old", "new"):
            write(work / (side + ".json"), observer_generation.portable_manifest(folder / side / "prepared.json"))
        return JDKS / "21.0.13.0+9-tem"
    folder = ROOT / "verification/product-behaviour/cases" / number
    for side, manifest in read(folder / "bindings.json").items():
        for item in manifest["classpath"]:
            item["file"] = str(CACHE / "organic-pr-20" / item["file"])
        write(work / (side + ".json"), manifest)
    return JDKS / read(folder / "case.json").get("jdk", "21.0.13.0+9-tem")


def run(command):
    p = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True, text=True)
    if p.returncode:
        raise ValueError(f"{command[1]}: " + (p.stderr + p.stdout)[-2200:])


def isolated(reg, work, jdk, bundle, *, source_root=None):
    """Give javac and the deterministic producer read access only to the approved packet and product."""
    subjects = [work / "old.json", work / "new.json"]
    jars = {item["file"] for p in subjects for item in read(p)["classpath"]}
    tool = (source_root or ROOT) / "examples/tools"
    scratch = work / "operator"
    scratch.mkdir()
    marker = work / "evaluator-only"
    marker.write_text("must be inaccessible to the operator")
    rules = ["setpriv", "--no-new-privs", "--landlock-access", "fs"]
    def grant(access, paths):
        for p in paths:
            rules.extend(["--landlock-rule", f"path-beneath:{access}:{p}"])
    grant("execute,read-file,read-dir", ["/usr", jdk])
    grant("read-file,read-dir", ["/etc", "/proc", "/sys"])
    grant("read-dir", [tool, tool / "targets"])
    grant("read-file", ["/dev/urandom", "/dev/random", tool / "scaffold_example.py", *subjects, reg,
                        *sorted(jars), *(p for p in (tool / "targets").glob("*.py") if not p.name.startswith("test_")),
                        tool / "targets/java/GeneratedObservation.java.template"])
    grant("read-file,write-file", ["/dev/null"])
    grant("read-file,read-dir,write-file,make-dir,make-reg,truncate,remove-file,remove-dir,refer", [scratch])
    check = ('import runpy,sys; from pathlib import Path\n'
             'try: Path(sys.argv.pop(1)).read_bytes()\n'
             'except PermissionError: pass\n'
             'else: raise RuntimeError("operator can read evaluator material")\n'
             'sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name="__main__")')
    env = {"HOME": str(scratch), "TMPDIR": str(scratch), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
           "JAVA_TOOL_OPTIONS": "-XX:-UsePerfData -Djava.io.tmpdir=" + str(scratch)}
    cmd = [*rules, "--", "/usr/bin/python3", "-I", "-B", "-c", check, marker, tool / "scaffold_example.py",
                    "emit", "--before", subjects[0], "--after", subjects[1], "--jdk", jdk,
                    "--registration", reg, "--output", scratch / "bundle"]
    proc = subprocess.run(cmd, cwd=scratch, env=env, capture_output=True, text=True)
    emitted = scratch / "bundle/generation.json"
    if proc.returncode and (not emitted.is_file() or read(emitted)["status"] != "open"):
        raise ValueError("isolated generation failed: " + (proc.stderr + proc.stdout)[-1400:])
    (scratch / "bundle").rename(bundle)
    write(work / "operator-policy.json", {"isolation": "Landlock", "excludedMarkerRead": "PermissionError",
          "registration": upgrade_replay.sha(reg), "permittedArtifacts": sorted(jars),
          "predictionsVisible": False, "historicalCallerVisible": False, "generator": read(bundle/"generation.json")["generator"]})

def pack(root, extra, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w") as archive:
        for p in sorted({f for path in extra for f in (path.rglob("*") if path.is_dir() else [path]) if f.is_file()}):
            archive.writestr(zipfile.ZipInfo(p.relative_to(root).as_posix()), p.read_bytes(), zipfile.ZIP_DEFLATED)


def exercise(number, work, *, resume=True, frozen=False, clean=False):
    work.mkdir(parents=True, exist_ok=True)
    jdk = prepare(number, work)
    bundle = work / "bundle"
    reg = HERE / "registrations" / (number + ".json")
    predictions = HERE / "predictions" / (number + ".json")
    archive_name = number + ("-first" if frozen else "-clean" if clean else "") + ".zip"
    source = None
    if frozen:
        seal = read(HERE/"freeze.json")
        archive = HERE/"operator-source.zip"
        if number not in seal["transfer"] or upgrade_replay.sha(archive) != seal["sourceArchiveSha256"]:
            raise ValueError("unregistered transfer or changed frozen product")
        source = work/"frozen-product"
        with zipfile.ZipFile(archive) as z:
            z.extractall(source)
    isolated(reg, work, jdk, bundle, source_root=source)
    generation = read(bundle/"generation.json")
    if frozen and generation["generator"] != seal["generator"]:
        raise ValueError("operator source differs from the first-attempt freeze")
    if generation["status"] == "open":
        pack(work, [*bundle.glob("*"), *work.glob("*.json")], HERE/"receipts"/archive_name)
        print(number, generation["firstOpenDependency"], flush=True)
        if clean:
            raise ValueError("final measurement stopped before compilation")
        return
    cmd = [sys.executable, ROOT / "examples/tools/scaffold_example.py", "generate",
           "--before", work / "old.json", "--after", work / "new.json", "--jdk", jdk,
           "--registration", reg, "--predictions", predictions, "--output", bundle]
    run(cmd)
    base = [sys.executable, ROOT / "examples/tools/build.py", "--change-plan", "application", "--before", bundle / "old.json",
            "--after", bundle / "new.json", "--jdk", jdk, "--workflows", bundle / "workflows.json", "--supplied-only",
            "--seconds", "120", "--cache", work / "cache"]
    run([*base, "--output", work / "scaffold.json"])
    if resume:
        run([*base, "--previous", work / "scaffold.json", "--run", "--output", work / "cold.json"])
        run([*base, "--previous", work / "cold.json", "--run", "--output", work / "warm.json"])
        if clean:
            run([*base, "--cache", work / "empty-cache", "--run", "--output", work / "empty.json"])
    if resume and number == "J17":
        from controls import map_oracle
        map_oracle(work, jdk)
    results = [*bundle.glob("*"), *work.glob("*.json"), *(work / "receipts").glob("*.json")]
    pack(work, results, (HERE / "receipts" / archive_name) if resume else work / "scaffold-bundle.zip")
    if resume:
        summary = {p["id"]: p["status"] for p in read(work / "cold.json")["claims"]}
        print(number, summary, flush=True)
        if number in {"458", "445", "J06", "J10", "J16", "J17", "J19", "io"} and set(summary.values()) != {"established"}:
            raise ValueError("one or more frozen development predictions did not qualify: " + str(summary))
        cold = read(work/"cold.json")["claims"]
        for repeat in ["warm", *(["empty"] if clean else [])]:
            for a, b in zip(cold, read(work/(repeat+".json"))["claims"], strict=True):
                if (a["claimKey"], a["status"], a.get("children")) != (b["claimKey"], b["status"], b.get("children")):
                    raise ValueError(repeat + " and cold finite evidence differs")
        if clean:
            audit_finished(number, cold, work)


def audit_finished(number, nodes, work):
    exceptions = {"filtered-child-hypothesis":"refuted", "earlier-change":"open",
                  "spring-projects/spring-framework#37193.1":"open","spring-projects/spring-framework#37193.3":"refuted",
                  "spring-projects/spring-framework#36626.3":"refuted"}
    for node in nodes:
        if node["status"] != exceptions.get(node["id"],"established"):
            raise ValueError(number+" "+node["id"]+" disagrees with the independent adjudication: "+str(node.get("reason",node["status"])))
        evidence = read(work/node["receipt"]["path"])
        for side in ("old","new"):
            trials = evidence["sides"][side]["trials"]
            if len(trials) != len(node["domain"]) or any(len(t.get("publicProjections",[]))!=2 or
                    t["publicProjections"][0] != t["publicProjections"][1] for t in trials):
                raise ValueError("incomplete repeatable public field coverage: "+node["id"]+"/"+side)
        if node["id"] == "spring-projects/spring-framework#37193.1":
            prior = json.loads(node["children"][0]["old"]["return"])
            if prior != [[[], "error", "org.springframework.web.reactive.function.client.WebClientResponseException",
                           "java.lang.NumberFormatException"]]:
                raise ValueError("reactive baseline lost its actual outer exception or cause")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("numbers", nargs="+")
    parser.add_argument("--work", type=Path)
    parser.add_argument("--scaffold-only", action="store_true")
    parser.add_argument("--checked-helper", action="store_true")
    parser.add_argument("--frozen", action="store_true", help="use the immutable pre-transfer producer")
    parser.add_argument("--empty-cache", action="store_true", help="also repeat all qualified fields independently with an empty cache")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="generated-observers-") as tmp:
        for number in args.numbers:
            work = (args.work or Path(tmp)) / number
            exercise(number, work, resume=not args.scaffold_only, frozen=args.frozen, clean=args.empty_cache)
            if args.checked_helper:
                from controls import helper
                helper(work, work / "bundle", prepare(number, work))
                pack(work, [*work.glob("*.json"), *(work / "bundle").glob("*"), *(work / "receipts").glob("*.json")],
                     HERE / "receipts" / (number + "-helper.zip"))
