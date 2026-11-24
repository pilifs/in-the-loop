"""W01/W02/W04 on separate original JVMs and a two-definition symbolic caller."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from history import HERE, ROOT, OUTPUT, JBMC, MODELS, benchmark, digest, encoded
from stock_history import RELOCATOR, classpath, stock_run

sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import runtime_jar
from campaign import JDK, javaenv, compile_java
import jvmcontract_io

CACHE = Path.home() / ".cache/in-the-loop/beyond-jbmc/releases"
VERSIONS = ("8.11.0", "9.0.0")
JARS = ("5069436519426486f74a84a77763895ec9ace807929dc931ab36760893cb8267",
        "f03aa0afc676ac80d111189c235974e6f4c628182e511aeb7e58b01db577c91a")
INT = [("int", "v")]
CASES = {"oldOld": ("W01", INT), "oldNew": ("W01", INT), "newOld": ("W01", INT), "newNew": ("W01", INT),
         "wrongIdentity": ("W01", INT), "writeFrame": ("W02", [("byte[]", "entry"), ("int", "offset"), ("int", "index"), ("int", "value")]),
         "readFrame": ("W02", [("byte[]", "entry"), ("int", "offset"), ("int", "index")]),
         "varOldNew": ("W04", INT), "varNewOld": ("W04", INT)}


def prepare(work):
    env = javaenv()
    jars = [CACHE / ("lucene-core-" + v) / "lib" / f"lucene-core-{v}.jar" for v in VERSIONS]
    if tuple(map(digest, jars)) != JARS:
        raise ValueError("Lucene release artifact drift")
    if digest(JDK / "lib/modules") != "a5fd7c311fbd96adcbd43757dbb94461e14df353b6ae9f5c029c45805a39782c":
        raise ValueError("subject JDK drift")
    src = HERE / "wire"
    caller, previous, claims = [work / n for n in ("caller", "old", "claims")]
    compile_java([src / "WireAPI.java", src / "WirePair.java"], caller, [jars[0]], env)
    old = work / "to-relocate"
    old.mkdir()
    shutil.copyfile(caller / "WireAPI.class", old / "WireAPI.class")
    entries = {}
    with zipfile.ZipFile(jars[0]) as z:
        for logical, item in runtime_jar.effective_entries(z, 21).items():
            if not logical.endswith(".class") or logical == "module-info.class" or logical.startswith("META-INF/"):
                continue
            file = old / logical
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(z.read(item))
            entries[logical] = item.filename
    tools = work / "tools"
    tools.mkdir()
    subprocess.run([JDK / "bin/javac", "-d", tools, RELOCATOR, HERE / "java/PairClasses.java"], check=True, env=env)
    subprocess.run([JDK / "bin/java", "-cp", tools, "net.terminalvalue.contracts.PairClasses", old, previous], check=True, env=env)
    cp = [claims, caller, previous, jars[1]]
    compile_java([src / "WireClaims.java", src / "WireControls.java"], claims, cp[1:], env)
    adapter = work / "WireAssertions.java"
    methods = []
    for name, (_, params) in CASES.items():
        decl = ", ".join(t + " " + n for t,n in params)
        args = ", ".join(n for _, n in params)
        guard = "if (entry == null || entry.length > 8 || offset < 0 || offset > entry.length-4 || index < 0 || index >= entry.length) return;" if name.endswith("Frame") else ""
        methods += [f"public static void {name}({decl}) throws Exception {{ {guard} assert WireClaims.{name}({args}); }}",
                    f"public static void {name}Reach({decl}) throws Exception {{ {guard} WireClaims.{name}({args}); assert false; }}"]
    adapter.write_text("public final class WireAssertions {\n" + "\n".join(methods) + "\n}\n")
    compile_java([adapter], claims, cp, env)
    return env, jars, cp, {"jarSha256": dict(zip(VERSIONS, JARS)), "jdkModulesSha256": digest(JDK/"lib/modules"),
                           "callerSha256": digest(caller/"WireAPI.class"), "relocatedCallerSha256": digest(previous/"before/WireAPI.class"),
                           "claimsSha256": digest(claims/"WireClaims.class"), "stockClassSha256": digest(claims/"WireAssertions.class"),
                           "effectiveOldEntryMapSha256": hashlib.sha256(encoded(entries)).hexdigest(),
                           "relocatorSha256": digest(RELOCATOR)}


def physical(work, env, jars, cp):
    java = str(JDK / "bin/java")
    calls, rows = [], []
    def invoke(argv):
        p = subprocess.run(argv, capture_output=True, text=True, env=env, check=True, timeout=25)
        calls.append({"argv": list(map(str, argv)), "exit": p.returncode, "stdout": p.stdout.strip()})
        return p.stdout.strip()
    for writer, v in enumerate(VERSIONS):
        frame = work / ("frame-" + v)
        invoke([java, "-cp", classpath([cp[1], jars[writer]]), "WirePair", "write", frame])
        data = frame.read_bytes().hex(" ")
        if data != ("33 01 02 03 04 55", "33 04 03 02 01 55")[writer]:
            raise ValueError("unexpected wire bytes")
        for reader, w in enumerate(VERSIONS):
            observed = invoke([java, "-cp", classpath([cp[1], jars[reader]]), "WirePair", "read", frame])
            if observed != ("01020304" if writer == reader else "04030201"):
                raise ValueError("incorrect mixed-version observation")
            rows.append({"writer":v, "reader":w, "frame":data, "readInt":observed, "writeEnd":5, "readEnd":5})
    for flag in ("-da", "-ea"):
        invoke([java, flag, "-cp", classpath(cp), "WireControls"])
    return {"calls": calls, "observations": rows}


def replay_classes(work, env):
    src = HERE / "wire"
    sources = []
    for side, prefix in enumerate(("before", "current")):
        folder = work / "replay-source" / prefix
        folder.mkdir(parents=True)
        file = folder / "WireAPI.java"
        methods = []
        for operation in ("write", "read", "writeVInt", "readVInt"):
            writing = operation.startswith("write")
            ret, call = ("int", "write") if writing else ("long", "read")
            param, arg = (", int value", ", value") if writing else ("", "")
            methods.append(f"public static {ret} {operation}(byte[] b, int off{param}) throws java.io.IOException {{ "
                           f'try {{ return witness.OriginalWire.{call}({side}, "{operation}", b, off{arg}).{ret}Value(); }} '
                           "catch (RuntimeException | java.io.IOException e) { throw e; } "
                           "catch (Exception e) { throw new IllegalStateException(e); } }")
        file.write_text(("package before;\n" if side == 0 else "") + "public class WireAPI {\n" + "\n".join(methods) + "\n}\n")
        sources.append(file)
    dest = work / "original-replay"
    dest.mkdir()
    subprocess.run([JDK/"bin/javac", "-parameters", "-g", "-proc:none", "-d", dest, *sources,
                    src/"ReplayWire.java", src/"OriginalWire.java", src/"WireClaims.java", benchmark.RUNNER_SOURCE], env=env, check=True)
    return dest


def replay(dest, env, jars, caller, name, tokens):
    result = []
    for flag in ("-da", "-ea"):
        cmd = [str(JDK/"bin/java"), flag, "-cp", str(dest), "ReplayWire", str(caller), *map(str, jars), name, tokens]
        p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=20)
        result.append({"argv": cmd, "exit": p.returncode, "outcome": p.stdout.strip(), "stderr": p.stderr.strip()})
    return result


def measure(work, env, jars, cp, out):
    checker = str(Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")).resolve())
    rows = []
    original = replay_classes(work, env)
    with zipfile.ZipFile(out / "executions.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name, (cid, params) in CASES.items():
            row = {"case": cid, "method": name, "expected": "violation" if name == "wrongIdentity" else "verified"}
            for engine in ("native", "jbmc"):
                cmd = [checker, "prove", "WireClaims#" + name, "--classes", str(cp[0]), "--classpath", classpath(cp[1:]),
                       "--engine", engine, "--gaps", "strict", "--assert", "result", "--timeout", "120", "--unwind", "16",
                       "--max-array-length", "8", "--json", "--work", str(work / name / engine)]
                if engine == "jbmc": cmd += ["--jbmc-staging", "staged", "--jbmc", str(JBMC)]
                entry = benchmark.measure(cmd, 240)
                raw = entry["stdout"]
                result = jvmcontract_io.decode(raw, "prove")
                record = {k: v for k, v in entry.items() if k not in ("stdout", "stderr")}
                if result.ok and len(result.outcomes) == 1:
                    data = result.outcomes[0]
                    record.update({k: data[k] for k in ("verdict","problem","counterexample","stated") if k in data})
                    if data.get("verdict") == "violation":
                        tokens = benchmark.witness_arguments(data)
                        if tokens is not None:
                            record["jvmReplay"] = replay(original, env, jars, cp[1], name, tokens)
                for stream in ("stdout","stderr"):
                    archive.writestr(f"{name}/{engine}/{stream}", entry[stream])
                archive.writestr(f"{name}/{engine}/argv.json", encoded(cmd))
                row[engine] = record
            row["stock"] = {entry: stock_run("WireAssertions", m, cp, params, archive, f"{name}/stock/{entry}")
                            for entry, m in (("target",name),("reach",name+"Reach"))}
            stock = row["stock"]["target"]
            if "arguments" in stock:
                tokens = ";".join(benchmark.token(v, chars=False) for v in stock["arguments"])
                stock["jvmReplay"] = replay(original, env, jars, cp[1], name, tokens)
            print(cid, name, row["native"].get("verdict"), row["jbmc"].get("verdict"), row["stock"]["target"]["status"], flush=True)
            rows.append(row)
    return {"rows": rows, "jvmcontractSha256": digest(Path(checker)), "jbmcSha256": digest(JBMC),
            "coreModelsSha256": digest(MODELS), "rawSha256": digest(out / "executions.zip"),
            "job": os.environ.get("VERIFY_JOB_ID"), "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT")}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=("physical", "opening", "closing"))
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    out = args.output or OUTPUT / args.phase / "wire"
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lucene-wire-") as tmp:
        work = Path(tmp)
        env, jars, cp, record = prepare(work)
        os.environ.update({k: env[k] for k in ("JAVA_HOME", "PATH", "JVMCONTRACT_JAR_RELEASE")})
        record["originalJvm"] = physical(work, env, jars, cp)
        for r in record["originalJvm"]["observations"]:
            print(r["writer"], r["reader"], r["frame"], r["readInt"])
        if args.phase != "physical":
            record.update(measure(work, env, jars, cp, out))
            (out / "results.json.gz").write_bytes(gzip.compress(encoded(record), mtime=0))
        else:
            (out / "receipt.json").write_bytes(encoded(record))


if __name__ == "__main__":
    main()
