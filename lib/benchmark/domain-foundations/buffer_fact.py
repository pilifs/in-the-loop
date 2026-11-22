"""Certify an original JDK heap-window fact, then qualify its use at two historical Avro call sites."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from startup import HERE, ROOT, document, materialize, runtime_jdk, runtime_maven

GUARD = "start >= 0 && length >= 0 && start <= bytes.length && length <= bytes.length - start"
WRAP = "java.nio.ByteBuffer#wrap([BII)Ljava/nio/ByteBuffer;"
DECIMAL = "org.apache.avro.Conversions$DecimalConversion#fromBytes(Ljava/nio/ByteBuffer;Lorg/apache/avro/Schema;Lorg/apache/avro/LogicalType;)Ljava/math/BigDecimal;"
CALLER = {"355": "org.apache.avro.hadoop.io.AvroDatumConverterFactory$BytesWritableConverter#convert(Lorg/apache/hadoop/io/BytesWritable;)Ljava/nio/ByteBuffer;",
          "361": "organic.DecimalWindow#buffer(I)Ljava/nio/ByteBuffer;", "362": "organic.EncoderWindow#window(I)Ljava/nio/ByteBuffer;"}
ENCODER = "org.apache.avro.io.BufferedBinaryEncoder#writeFixed(Ljava/nio/ByteBuffer;)V"


def elapsed(start):
    return round(time.monotonic() - start, 6)


def execute(args, directory, env):
    """Record elapsed time, accumulated CPU time and the maximum RSS of this command and its waited-for children."""
    start = time.monotonic()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        p = subprocess.Popen(list(map(str, args)), cwd=directory, env=env, stdout=stdout, stderr=stderr)
        _, status, usage = os.wait4(p.pid, 0)
        p.returncode = os.waitstatus_to_exitcode(status)
        stdout.seek(0); stderr.seek(0)
        out = stdout.read()
        if p.returncode:
            raise ValueError(f"{Path(args[0]).name} exited {p.returncode}: " +
                             (stderr.read()[-800:] + out[-1200:]).decode(errors="replace"))
    return out, {"seconds": elapsed(start), "cpuSeconds": round(usage.ru_utime + usage.ru_stime, 6),
                 "peakRssBytes": usage.ru_maxrss * 1024}


def dependencies(work, jdk, checker, max_length=6, theorem="BufferRange"):
    return {"theoremClass": runtime_maven.sha256_of(work / "proof/foundation" / (theorem+".class")),
            "jdkModules": runtime_maven.sha256_of(jdk / "lib/modules"),
            "libjvm": runtime_maven.sha256_of(jdk / "lib/server/libjvm.so"),
            "jdkRelease": runtime_maven.sha256_of(jdk / "release"),
            "checkerSha256": runtime_maven.sha256_of(checker), "engine": "native", "gaps": "strict",
            "unwind": 64, "maxArrayLength": max_length, "guard": GUARD, "assert": "result == 1"}


def certify(work, jdk, checker, env, path, method, max_length=6, theorem="BufferRange"):
    identity = dependencies(work, jdk, checker, max_length, theorem)
    target = "foundation."+theorem+"#"+method
    argv = [checker, "prove", "--classes", work / "proof", target, "--engine", "native", "--gaps", "strict",
            "--unwind", "64", "--max-array-length", str(max_length), "--assume", GUARD, "--assert", identity["assert"], "--json"]
    raw, cost = execute(argv, work, env)
    row, = json.loads(raw)
    stated = row["stated"]
    if (row["target"] != target or row["verdict"] != "verified" or row["problem"]
            or row["assume"] != GUARD or row["assert"] != identity["assert"] or row["throws"]
            or stated["gap_mode"] != "strict" or stated["vacuity"]["status"] != "non-vacuous"
            or stated["bounds"] != {"unwind": 64, "max_array_length": max_length, "complete": True}
            or {a["kind"] for a in stated["assumptions"]} != {"initialization", "precondition"}):
        raise ValueError("producer did not establish the complete non-vacuous strict statement")
    raw_path = path.with_suffix(".native.json")
    raw_path.write_bytes(raw)
    document(path, {"schema": "heap-range-proof/v1", "method": method, "dependencies": identity,
                    "nativeReceipt": raw_path.name, "nativeSha256": hashlib.sha256(raw).hexdigest(), "cost": cost})
    return runtime_maven.sha256_of(path), cost


def validate_producer(path, expected_sha, identity, method):
    # expected_sha is retained by the producer in this run. Replaying the pilot builds
    # its own proof. A self-asserted hash read from a caller-supplied proof is insufficient.
    if runtime_maven.sha256_of(path) != expected_sha:
        raise ValueError("changed producer receipt")
    record = json.loads(path.read_text())
    if (record["schema"] != "heap-range-proof/v1" or record["method"] != method
            or record["dependencies"] != identity or record["nativeReceipt"] != path.with_suffix(".native.json").name
            or record["nativeSha256"] != runtime_maven.sha256_of(path.parent / record["nativeReceipt"])):
        raise ValueError("changed producer dependencies or proof")


def site_inputs(number, side, work, jdk, env, max_length=6):
    start = time.monotonic()
    folder, = (ROOT / "examples").glob(number + "-*")
    directory = work / (number + "-" + side)
    directory.mkdir()
    jars, binding = materialize(folder, side, directory)
    classes = directory / "classes"
    classes.mkdir()
    _, compile_cost = execute([jdk / "bin/javac", "-J-Djava.io.tmpdir=" + str(work), "-parameters", "-g", "-cp",
                               os.pathsep.join(map(str, jars)), "-d", classes, *sorted((folder/"adapter").rglob("*.java"))],
                              directory, env)
    cp = os.pathsep.join(map(str, [work/"trace", classes, *jars]))
    java = [jdk / "bin/java", "-XX:ActiveProcessorCount=2", "-Djava.io.tmpdir=" + str(work), "-cp", cp,
            "foundation.BufferSites"]
    plain, regular_cost = execute([*java, "calls", number], "/", env)
    traced, trace_cost = execute([*java, "trace", number, cp, work], "/", env)
    lines = traced.decode().splitlines()
    if [r for r in lines if r.startswith("ROW\t")] != plain.decode().splitlines():
        raise ValueError("public outcomes differ under observation")
    table = json.loads((folder / "controls/table.json").read_text())["cases"]
    sites, seen, outcomes = [], set(), {}
    for line in lines:
        cells = line.split("\t")
        if cells[0] == "ROW":
            index, result = map(int, cells[1:])
            if index in outcomes:
                raise ValueError("duplicate public outcome")
            outcomes[index] = result
            continue
        if len(cells) != 12 or cells[0] != "SITE":
            raise ValueError("unrecognized debugger output")
        _, row_id, kind, capacity, pos, size, caller, pc, caller_sha, pool_sha, target, target_sha = cells
        index = int(row_id)
        inp = table[index]["input"]
        if index != table[index]["id"] or (index, kind) in seen:
            raise ValueError("duplicate or mismatched selector")
        seen.add((index, kind))
        actual = tuple(map(int, (capacity, pos, size)))
        expected = ((inp["capacity"], 0, inp["capacity"] if side == "parent" else inp["length"]) if number == "355"
                    else (inp.get("capacity", 6), inp["start"], inp["width"]))
        if actual != expected or not (0 <= actual[1] <= actual[0] <= max_length and 0 <= actual[2] <= actual[0] - actual[1]):
            raise ValueError("the observed original caller does not satisfy the producer's domain")
        want = ((CALLER[number], WRAP) if kind == "wrap" else
                ("organic.EncoderWindow#cursor(I)I", ENCODER) if number == "362" else ("organic.DecimalWindow#cursor(I)I", DECIMAL))
        if (caller, target) != want:
            raise ValueError("unexpected call site or callee")
        sites.append({"input": index, "call": kind, "capacity": actual[0], "position": actual[1], "length": actual[2],
                      "caller": caller, "bci": int(pc), "methodSha256": caller_sha, "poolSha256": pool_sha,
                      "target": target, "targetMethodSha256": target_sha})
    kinds = {"355": ("wrap",), "361": ("wrap", "decimal"), "362": ("wrap", "encoder")}[number]
    if seen != {(r["id"], k) for r in table for k in kinds}:
        raise ValueError("incomplete original caller coverage")
    expected_outcomes = {r["id"]: int(side == "fix" or number == "355" and r["input"]["capacity"] == r["input"]["length"])
                         for r in table}
    if number == "362":
        expected_outcomes = {r["id"]: int(side == "fix" or not r["input"]["readOnly"] or r["input"]["width"] <= 16)
                             for r in table}
    if outcomes != expected_outcomes:
        raise ValueError("wrong public return or missing admitted input")
    return {"build": binding, "sites": sorted(sites, key=lambda r: (r["input"], r["call"])),
            "publicReturns": outcomes, "cost": {"seconds": elapsed(start),
            "peakRssBytes": max(r["peakRssBytes"] for r in (compile_cost, regular_cost, trace_cost)),
            "compile": compile_cost, "ordinary": regular_cost, "traced": trace_cost}}


def run(output):
    jdk = Path(runtime_jdk.home("21"))
    if runtime_jdk.release(jdk)["JAVA_VERSION"] != "21.0.13":
        raise ValueError("unexpected subject JDK")
    checker = Path(os.environ["JVMCONTRACT"]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bounded-buffer-") as tmp:
        work = Path(tmp)
        env = {"JAVA_HOME": str(jdk), "PATH": str(jdk/"bin") + os.pathsep + os.defpath,
               "LANG": "C", "LC_ALL": "C", "TZ": "UTC", "TMPDIR": tmp, "JVMCONTRACT_JAR_RELEASE": "21"}
        summary = {}
        all_sites = {}
        producer = output/"clean-wrap.json"
        for route, source in (("disabled", "361"), ("clean", "355"), ("reuse", "361")):
            start = time.monotonic()
            leg = work / route
            leg.mkdir()
            for name in ("proof", "trace"):
                (leg/name).mkdir()
            _, build = execute([jdk/"bin/javac", "-J-Djava.io.tmpdir="+tmp, "-g", "-parameters", "-d", leg/"proof",
                                HERE/"BufferRange.java"], leg, env)
            _, debug = execute([jdk/"bin/javac", "-J-Djava.io.tmpdir="+tmp, "-d", leg/"trace", HERE/"BufferSites.java"], leg, env)
            checked_at = time.monotonic()
            if route == "reuse":
                validate_producer(producer, trusted, dependencies(leg, jdk, checker), "wrap")
                proof_cost = None
            else:
                key, proof_cost = certify(leg, jdk, checker, env, producer if route == "clean" else output/"disabled-wrap.json", "wrap")
                if route == "clean":
                    trusted = key
            cert_seconds = elapsed(checked_at)
            sites = {side: site_inputs(source, side, leg, jdk, env) for side in ("parent", "fix")}
            for side, s in sites.items():
                all_sites[route + "/" + side] = s
            summary[route] = {"example": source, "proofExecutions": int(route != "reuse"), "producerSeconds": cert_seconds,
                              "setupSeconds": build["seconds"] + debug["seconds"], "validationSeconds": sum(x["cost"]["seconds"] for x in sites.values()),
                              "totalSeconds": elapsed(start), "peakRssBytes": max(build["peakRssBytes"], debug["peakRssBytes"],
                                  (proof_cost or {}).get("peakRssBytes", 0), *(s["cost"]["peakRssBytes"] for s in sites.values()))}
        if any(all_sites["disabled/"+s]["sites"] != all_sites["reuse/"+s]["sites"] for s in ("parent", "fix")):
            raise ValueError("the fresh and reused proofs covered different application sites")
        wraps = {site["targetMethodSha256"] for side in all_sites.values() for site in side["sites"] if site["call"] == "wrap"}
        if len(wraps) != 1:
            raise ValueError("the two historical callers invoked different JDK wrap bytecode")
        # A change outside the producer compiles alongside it. A changed initializer in
        # the selected producer compiles from the same file name and must invalidate it.
        extra = leg/"Unrelated.java"
        extra.write_text("final class Unrelated { static int value() { return 7; } }\n")
        execute([jdk/"bin/javac", "-d", leg/"proof", extra], leg, env)
        validate_producer(producer, trusted, dependencies(leg, jdk, checker), "wrap")
        _, duplicate_cost = certify(leg, jdk, checker, env, output/"duplicate.json", "duplicate")
        edited = leg/"BufferRange.java"
        original = (HERE/"BufferRange.java").read_text()
        edited.write_text(original.replace("public final class BufferRange {",
            'public final class BufferRange { static { if (Boolean.getBoolean("fixture.stop")) throw new IllegalStateException(); }'))
        execute([jdk/"bin/javac", "-parameters", "-g", "-d", leg/"proof", edited], leg, env)
        try:
            validate_producer(producer, trusted, dependencies(leg, jdk, checker), "wrap")
        except ValueError as e:
            refused = str(e)
        else:
            raise ValueError("stale producer was accepted")
    document(output/"sites.json", all_sites)
    document(output/"measurement.json", {"schema": "bounded-jdk-buffer-adoption/v1", "routes": summary,
        "producerSha256": trusted, "siteEvidenceSha256": runtime_maven.sha256_of(output/"sites.json"),
        "duplicateProof": duplicate_cost, "controls": {"unrelatedClass": "accepted", "changedInitializer": refused},
        "scope": "JDK heap window at observed original calls on the stated input grids; JVM startup and the decimal result retain their own obligations.",
        "agentMinutes": None})
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output.resolve())
