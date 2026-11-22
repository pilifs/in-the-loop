"""Prove the Jackson feed loop starting at the unused parser returned by its original public factory."""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from companions import HERE, ROOT, PROFILE, SHA, document, hash_bytes, invocation, materialize, proof, runtime_jdk, selected_class
from public_run import read
from targets import route, runtime_jar, sidecar
from window_experiments import replace_once

FOLDER = ROOT / "examples/365-jackson-async-token-offsets"
SOURCE = FOLDER / "adapter/campaign/AsyncTokens.java"
BASE_JOB = "20261122-133607-prove-the-name-validation-consumer-on-fo"
START = "campaign.ReadyParser"
CLASSES = ["StreamReadConstraints", "io.ContentReference", "io.IOContext", "json.JsonReadContext",
           "json.async.NonBlockingJsonParser", "sym.ByteQuadsCanonicalizer", "util.BufferRecycler",
           "util.JacksonFeatureSet", "util.ReadConstrainedTextBuffer", "util.TextBuffer"]
RUNTIME = dict(PROFILE, captureObjects=["com.fasterxml.jackson.core." + name for name in CLASSES])
TRACE = [3, 1, 1, 9, 2, 5, 4, 5, 6, 3, 1]
GUARD = "code >= 0 && code < 128"


def ready_source():
    source = replace_once(SOURCE.read_text(), "class AsyncTokens", "class ReadyTokens")
    return replace_once(source, "new JsonFactory().createNonBlockingByteArrayParser()", "ReadyParser.INSTANCE")


def schedule_source():
    arms = [f"            case {code}: return ReadyTrace.closing({code});" for code in range(128)]
    return "\n".join(["package campaign;", "public final class WindowSchedules {",
                      "    public static int closing(int code) throws java.io.IOException {",
                      "        switch (code) {", *arms, "            default: return -1;", "        }", "    }", "}", ""])


def qualify_schedule(body):
    """Bind every switch key to its own literal argument, the called method, and the default rejection."""
    _, methods, _ = runtime_jar._declarations(body, with_code=True)
    access, code, catches = methods["closing", "(I)I"]
    if (runtime_jar.this_class(body) != "campaign/WindowSchedules" or access != 9 or catches
            or set(methods) != {("<init>", "()V"), ("closing", "(I)I")} or code[:4] != b"\x1a\xaa\x00\x00"):
        raise ValueError("different selector dispatch")
    default, lo, hi = struct.unpack_from(">iii", code, 4)
    if (lo, hi) != (0, 127) or code[1 + default:] != b"\x02\xac":
        raise ValueError("different switch domain or default")
    offsets = struct.unpack_from(">128i", code, 16)
    digest = hash_bytes(code)
    pool = hash_bytes(body[10:runtime_jar._pool(body)[1]])
    for key, (start, end) in enumerate(zip(offsets, (*offsets[1:], default), strict=True)):
        literal = bytes([3 + key]) if key <= 5 else bytes([0x10, key])
        block = code[1 + start:1 + end]
        if len(block) != len(literal) + 4 or not block.startswith(literal + b"\xb8") or block[-1] != 0xac:
            raise ValueError(f"wrong constant or return for selector {key}")
        call = runtime_jar.member_at_code_index(body, "closing", "(I)I", 1 + start + len(literal),
                                                code_sha256=digest, pool_sha256=pool)
        if not call or (call["owner"], call["name"], call["descriptor"]) != ("campaign.ReadyTrace", "closing", "(I)I"):
            raise ValueError(f"wrong observer for selector {key}")
    return digest


def correspondence(lines, ordinary, table, side):
    """Check all eleven observations against the ordinary JVM and the independent two-revision law."""
    if len(lines) != len(ordinary) or len(lines) != len(table) or len(lines) != 128:
        raise ValueError("incomplete selector coverage")
    matches = 0
    for code, (line, original, row) in enumerate(zip(lines, ordinary, table, strict=True)):
        selector, values = line.split("\t")
        trace = json.loads(values)
        frozen = row["expected"]["offsets"]
        padding = code >> 5
        expected = TRACE.copy()
        if side == "parent":
            expected[7] += padding
        if (str(code) != selector or original["id"] != row["id"] or row["id"] != code
                or row["input"] != {"cuts": code & 31, "padding": padding} or original["input"] != row["input"]
                or trace != original["direct"]["offsets"]["trace"] or trace != expected
                or frozen != {"trace": TRACE, "matchesUnpadded": True}
                or original["direct"]["tokens"] != row["expected"]["tokens"]
                or row["expected"]["tokens"] != [3, 9, 4, 3, 1]
                or original["direct"]["offsets"]["matchesUnpadded"] != (trace == TRACE)
                or original["adapter"] != {"offsets": int(trace == TRACE), "tokens": 1}):
            raise ValueError(f"selector {code} disagrees with the ordinary JVM or the independent trace")
        matches += trace == TRACE
    return {"schedules": len(table), "matchingOffsets": matches, "matchingTokensAndEof": len(table)}


def queries(side):
    return {"grid": ("campaign.WindowSchedules#closing", GUARD, "result == 5 + (code >> 5)" if side == "parent" else "result == 5"),
            "padded": ("campaign.ReadyTokens#offsets", "code == 32", "result == 1")}


def replay_native_input(raw, out, work):
    outcome, = read(raw)
    inputs = outcome["counterexample"]["inputs"]
    if inputs != [{"name": "code", "type": "int", "value": 32}]:
        raise ValueError("different native witness for the padded one-feed claim")
    supplied = out / "candidate.json"
    document(supplied, {"inputs": inputs, "sourceReceiptSha256": SHA(raw)})
    example = read(FOLDER / "example.json")
    review = route.review_witness(FOLDER, example, sidecar.load(FOLDER, example), "offsets-parent", supplied, work)
    if not isinstance(review, dict) or review["status"] != "witness-reproduced":
        raise ValueError(f"ordinary offsets-parent replay failed: {review}")
    return {"claimKey": review["claimKey"], "file": review["path"], "sha256": SHA(FOLDER / review["path"])}


def run(side, out, physical_only):
    jdk = Path(runtime_jdk.home("21"))
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="jackson-ready-") as tmp:
        work = Path(tmp)
        jars, binding = materialize(FOLDER, side, work)
        classes = work / "classes"
        classes.mkdir()
        paths = [classes, *jars]
        cp = os.pathsep.join(map(str, paths))
        env = dict(os.environ, JAVA_HOME=str(jdk), JVMCONTRACT_JAR_RELEASE="21", PATH=str(jdk / "bin") + os.pathsep + os.defpath)
        tokens = out / "ReadyTokens.java"
        tokens.write_text(ready_source())
        schedules = work / "WindowSchedules.java"
        schedules.write_text(schedule_source())
        subprocess.run([jdk / "bin/javac", "-proc:none", "-g", "-parameters", "-cp", cp, "-d", classes,
                        tokens, schedules, HERE / "ReadyTrace.java", HERE / "ReadyParser.java"], check=True, env=env)
        bytecode = (classes / "campaign/WindowSchedules.class").read_bytes()
        (out / "WindowSchedules.jvm-bytecode").write_bytes(bytecode)
        method_hash = qualify_schedule(bytecode)
        physical = invocation([jdk / "bin/java", "-Xverify:all", "-cp", cp, "campaign.ReadyTrace", *paths],
                              "physical", out, work, env)
        if physical["exit"]:
            raise ValueError(f"actual parser at factory return failed: {out / physical['stderr']}")
        reference, = FOLDER.glob(f"records/opening-bound/replay/*/records/control-{side}-jdk21.stdout")
        table = FOLDER / "controls/table.json"
        counts = correspondence((out / physical["stdout"]).read_text().splitlines(),
                                [json.loads(s) for s in reference.read_text().splitlines()], read(table)["cases"], side)
        parser = "com/fasterxml/jackson/core/json/async/NonBlockingUtf8JsonParserBase.class"
        index, entry, target = selected_class(jars, parser)
        report = {"side": side, "binding": binding, "jdkModules": SHA(jdk / "lib/modules"), "runtime": RUNTIME,
                  "target": {"jar": binding["orderedJars"][index], "entry": entry, "classSha256": hash_bytes(target)},
                  "originalAdapterSha256": SHA(SOURCE), "companionSourceSha256": SHA(tokens),
                  "classHashes": {p.stem: SHA(p) for p in sorted((classes / "campaign").glob("*.class"))},
                  "selectorCodeSha256": method_hash, "oracleSha256": SHA(table),
                  "ordinary": str(reference.relative_to(ROOT)), "ordinarySha256": SHA(reference),
                  "physical": physical, "counts": counts}
        if not physical_only:
            checker = Path(os.environ["JVMCONTRACT"]).resolve()
            previous = read(ROOT / "verification/results" / BASE_JOB / "result.json")
            baseline = checker.parent.parent / previous["jvmcontract"]["libTree"] / "jvmcontract"
            old_digest = read(ROOT / "verification/java-domain-proof/name-validation/367/fix/measurement.json")["checker"]
            if SHA(baseline) != old_digest:
                raise ValueError("different baseline checker")
            for stage, exe, source in [("baseline", baseline, previous["sourceCommit"]),
                                       ("followup", checker, os.environ["VERIFY_SOURCE_COMMIT"])]:
                results = {}
                report[stage] = {"checker": SHA(exe), "source": source, "proofs": results}
                for label, (method, guard, assertion) in queries(side).items():
                    result = proof(exe, classes, jars, work, env, out, method, stage + "-" + label,
                                   guard, assertion, [START], profile=RUNTIME)
                    results[label] = result
                    document(out / "measurement.json", report)
                    if side == "parent" and stage == "followup" and label == "padded" and result["verdict"] == "violation":
                        report["originalWitness"] = replay_native_input(out / result["stdout"], out, work / "original")
        document(out / "measurement.json", report)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--side", choices=("parent", "fix"))
    cli.add_argument("--physical-only", action="store_true")
    args = cli.parse_args()
    for side in (args.side,) if args.side else ("parent", "fix"):
        run(side, args.output.resolve() / side, args.physical_only)
