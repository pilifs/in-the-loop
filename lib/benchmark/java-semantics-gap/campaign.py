"""Compile the original caller once per graph and compare strict engines on the identical class files."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

from historical import ROOT, HERE, benchmark, digest
from subjects import CLAIMS

CACHE = Path.home() / ".cache/in-the-loop/jbmc-java-semantics-gap"
JDK = Path.home() / ".sdkman/candidates/java/21.0.13.0+9-tem"
GRAPHS = json.loads((HERE / "classpaths.json").read_bytes())
sys.path.insert(0, str(ROOT / "lib/python"))
import jvmcontract_io as wire


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def command(argv, env, limit=120):
    started = time.monotonic()
    try:
        p = subprocess.run(list(map(str, argv)), capture_output=True, env=env, timeout=limit)
        return p.returncode, p.stdout, p.stderr, round(time.monotonic()-started, 3)
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or b"", e.stderr or b"", round(time.monotonic()-started, 3)


def compile_java(sources, output, cp, env):
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([JDK/"bin/javac", "-source", "8", "-target", "8", "-Xlint:-options", "-parameters", "-g",
                    "-proc:none", "-classpath", os.pathsep.join(map(str, cp)), "-d", output, *sources], env=env, check=True)


def javaenv():
    return dict(os.environ, JAVA_HOME=str(JDK), JVMCONTRACT_JAR_RELEASE="21",
                PATH=str(JDK/"bin") + os.pathsep + os.environ["PATH"])


def java_source(path, content):
    path.write_text(content + "\n")
    return path


def jvm_controls(subject, work, cp, env):
    lines = []
    for claim in subject.claims:
        for result, cases in ((True, claim.holds), (False, claim.fails)):
            for args in cases:
                call = f"{subject.owner}.{claim.method}({', '.join(args)})"
                lines.append(f'if ({call} != {str(result).lower()}) throw new AssertionError("{claim.method}");')
    if subject.owner == "MonitorIdentity":
        lines.append('if (MonitorIdentity.workerFirst()) throw new AssertionError("mixed worker-first schedule");')
    java = java_source(work/"OriginalChecks.java", "class OriginalChecks {public static void main(String[] a) throws Exception {\n"
                       + "\n".join(lines) + f'\nSystem.out.println("{len(lines)} original checks passed");' + "}}")
    dest = work/"original"
    compile_java([java], dest, cp, env)
    checked = subprocess.run([JDK/"bin/java", "-ea", "-cp", os.pathsep.join(map(str,[dest,*cp])), "OriginalChecks"],
                             check=True, capture_output=True, text=True, env=env, timeout=40)
    if checked.stdout.strip() != f"{len(lines)} original checks passed":
        raise ValueError("incomplete original JVM replay")
    return {"checks": len(lines), "sourceSha256": digest(java), "stdout": checked.stdout.strip()}


def replay_literal(typ, value):
    if typ == "boolean" and type(value) is bool:
        return str(value).lower()
    if typ == "char" and isinstance(value, str) and len(value) == 1:
        return f"(char){ord(value)}"
    if typ in ("int","long","char") and type(value) in (str,int):
        n = int(value)
        if typ == "char": return f"(char){n}"
        return str(n) + ("L" if typ == "long" else "")
    if value is None and (typ == "String" or typ.endswith("[]")):
        return "null"
    if typ == "String" and isinstance(value, str):
        units = value.encode("utf-16-be", errors="surrogatepass")
        return "new String(new char[]{" + ",".join(f"(char){int.from_bytes(units[i:i+2], 'big')}"
                for i in range(0,len(units),2)) + "})"
    raise ValueError(f"no exact JVM reconstruction for {typ}")


def replay_witness(subject, claim, data, work, cp, env):
    args = data.get("counterexample", {}).get("inputs")
    if args is None:
        return {"outcome": "missing inputs"}
    params = [p.strip().split() for p in claim.parameters.split(",") if p.strip()]
    if len(args) != len(params):
        return {"outcome": "different parameter list"}
    try:
        literals = [replay_literal(p[0], a["value"]) for p,a in zip(params,args)]
    except (ValueError, TypeError, KeyError):
        return {"outcome": "input reconstruction unsupported"}
    declared = "\n".join(f"{typ} {name} = {literal};" for (typ,name),literal in zip(params,literals))
    guard = claim.guard or "true"
    call = f"{subject.owner}.{claim.method}({', '.join(p[1] for p in params)})"
    source = java_source(work/"OriginalWitness.java", "class OriginalWitness {public static void main(String[] a) throws Exception {\n"
                         + declared + f'\nif (!({guard})) throw new IllegalArgumentException("outside guard");\n'
                         + f'System.out.println({call} ? "held" : "refuted");' + "}}")
    dest = work/"witness"
    compile_java([source], dest, cp, env)
    code, out, err, _ = command([JDK/"bin/java","-ea","-cp",os.pathsep.join(map(str,[dest,*cp])),"OriginalWitness"], env, 20)
    return {"outcome":out.decode().strip() if code == 0 else "replay failed", "inputs":args,
            "sourceSha256":digest(source), "exit":code, "diagnostic":err.decode(errors="replace").strip()}


def integrated(subject, claim, engine, work, raw, cp, env):
    title = subject.owner + "#" + claim.method
    checker = Path(env["JVMCONTRACT"]).resolve()
    argv = [checker,"prove","--classes",cp[0],title,"--assert","result","--engine",engine,"--gaps","strict",
            "--timeout","120","--unwind",str(subject.unwind),"--max-array-length",str(subject.bound),
            "--jbmc-staging","staged","--jbmc",shutil.which("jbmc"),"--work",work/"proof","--json"]
    if claim.guard: argv += ["--assume",claim.guard]
    if claim.nullable: argv += ["--nullable",claim.nullable]
    for jar in cp[1:]: argv += ["--classes",jar]
    code, out, err, secs = command(argv, env, 170)
    (raw/"stdout.json").write_bytes(out)
    (raw/"stderr.txt").write_bytes(err)
    record = {"engine":engine,"exit":code,"seconds":secs,"expected":"violation" if claim.fails or claim.method=="mixed" else "verified"}
    data = wire.decode(out.decode(errors="replace"), "prove")
    if not data.ok or len(data.outcomes) != 1:
        msg = (err or out).decode(errors="replace").strip()
        if code != 124 and (code != 2 or not msg):
            raise ValueError(f"{title}: unreadable prover result at exit {code}: {msg[:180]}")
        return dict(record, verdict="unverifiable", disposition="timeout" if code == 124 else "frontend refusal", firstUnproved=msg[:1500])
    row, = data.outcomes
    classification = benchmark.classify({"kind":"property","expected":record["expected"]},row,
                {"killed":code==124,"exit":code,"stdout":out.decode(errors="replace"),"stderr":err.decode(errors="replace")})
    record.update(verdict=classification["verdict"], disposition=classification["class"], firstUnproved=classification.get("problem",""))
    if record["verdict"] in ("verified","violation"):
        stated = row["stated"]
        if (row["target"] != title or row["assert"] != "result" or (row.get("assume") or "") != claim.guard
                or stated["gap_mode"] != "strict" or row["search"]["engine"] != engine
                or classification["assumed"] or classification["contracts"] or stated["checker"].get("fallback")):
            raise ValueError(f"{title}: mismatched statement or engine")
        record["stated"] = stated
        if record["verdict"] == "verified" and (not stated["bounds"]["complete"]
                or stated["vacuity"]["status"] == "vacuous"):
            record["disposition"] = "incomplete bound or vacuous"
        if record["verdict"] == "violation":
            record["jvmReplay"] = replay_witness(subject,claim,row,work,cp,env)
            if record["jvmReplay"]["outcome"] != "refuted":
                record["disposition"] = "unconfirmed witness"
    return record


def measure(key, phase, engines, output, method=None):
    subject = CLAIMS[key]
    records = GRAPHS[subject.graph]
    jars = [CACHE/r["path"] for r in records]
    if any(digest(j) != r["sha256"] for j,r in zip(jars,records)):
        raise ValueError(f"{key}: the original ordered classpath changed")
    source, = (ROOT/"examples").glob(f"{subject.example}-*/adapter/**/{subject.owner}.java")
    folder, = (ROOT/"examples").glob(f"{subject.example}-*")
    target = json.loads((folder/"target.json").read_bytes())
    frozen = {t["target"]: t for t in target["tasks"] if t["revision"] == key}
    if set(frozen) != {subject.owner + "#" + c.method for c in subject.claims}:
        raise ValueError(f"{key}: numbered example and campaign disagree on the entries")
    specs = {}
    for claim in subject.claims:
        task = frozen[subject.owner + "#" + claim.method]
        file = folder/task["claim"]
        spec = json.loads(file.read_bytes())
        if (spec["assert"] != "result" or spec.get("assume", "") != claim.guard
                or spec.get("nullable", []) != ([claim.nullable] if claim.nullable else [])
                or spec["bounds"] != {"unwind":subject.unwind,"maxArrayLength":subject.bound}
                or task["expected"] != ("refuted" if claim.fails or claim.method=="mixed" else "established")):
            raise ValueError(f"{key}: changed scope of {claim.method}")
        specs[claim.method] = digest(file)
    with tempfile.TemporaryDirectory(prefix="semantics-subject-") as tmp:
        work = Path(tmp)
        env = javaenv()
        classes = work/"classes"
        compile_java([source], classes, jars, env)
        cp = [classes, *jars]
        report = {"subject":key,"phase":phase,"source":os.environ.get("VERIFY_SOURCE_COMMIT"),
                  "job":os.environ.get("VERIFY_JOB_ID"), "adapterSha256":digest(source),
                  "classes":{p.name:digest(p) for p in sorted(classes.glob("*.class"))},
                  "classpath":["adapter",*records],"jdk":(JDK/"release").read_text().splitlines(),
                  "jvmSha256":digest(JDK/"bin/java"),"modulesSha256":digest(JDK/"lib/modules"),
                  "scope":asdict(subject), "claimsSha256":specs, "originalJvm":jvm_controls(subject,work,cp,env),"runs":[]}
        if engines:
            report["checkerSha256"] = digest(Path(env["JVMCONTRACT"]))
            report["libTree"] = env.get("JVMCONTRACT_LIB_TREE")
            report["jbmcSha256"] = digest(shutil.which("jbmc"))
            report["packagedModelsSha256"] = digest("/usr/lib/core-models.jar")
        dest = output / phase / key
        dest.mkdir(parents=True, exist_ok=True)
        for claim in subject.claims:
            if method and claim.method != method: continue
            for engine in engines:
                name = f"{claim.method}-{engine}"
                scratch = work/name
                scratch.mkdir()
                raw = work/"raw"/name
                raw.mkdir(parents=True)
                result = integrated(subject,claim,engine,scratch,raw,cp,env)
                report["runs"].append(dict(method=claim.method,**result))
                print(key,name,result["disposition"],result["seconds"],flush=True)
        if engines:
            with tarfile.open(dest/"raw.tar.gz","w:gz") as archive:
                archive.add(work/"raw",arcname="raw")
            report["rawSha256"] = digest(dest/"raw.tar.gz")
        write(dest/"measurement.json",report)
        return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=("opening","final","jvm"))
    p.add_argument("subjects",nargs="+",choices=CLAIMS)
    p.add_argument("--engines", default="native,jbmc",choices=("native,jbmc","native","jbmc"))
    p.add_argument("--output",type=Path,default=ROOT/"verification/java-semantics-gap")
    p.add_argument("--method")
    a = p.parse_args()
    for subject_key in a.subjects:
        measure(subject_key,a.phase,[] if a.phase=="jvm" else a.engines.split(","),a.output.resolve(),a.method)
