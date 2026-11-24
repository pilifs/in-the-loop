"""Recheck the disclosed Plexus witness and a held-out Codec class hierarchy on ordinary equivalence."""
import argparse
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from history import OUTPUT, ROOT, benchmark, digest, encoded, scratch
from release_cases import JDK, jars_for, javaenv
from stock_history import classpath
from auto_upgrade import extract
from packets import BASE

FIRST = OUTPUT / "blind/03/automatic/report.json.gz"
DIAGNOSIS = OUTPUT / "blind/03/identity-diagnostic/report.json"
CODEC_TYPE = "org.apache.commons.codec.digest.MurmurHash3$IncrementalHash32"
RUNNER = """public class ReadBoth {
    public static void main(String[] args) throws Exception {
        var method = Class.forName(args[0]).getMethod(args[1], boolean.class);
        for (boolean input : new boolean[]{false, true})
            System.out.println((String) method.invoke(null, input));
    }
}
"""


def plexus(work):
    first = json.loads(gzip.decompress(FIRST.read_bytes()))
    diagnosis = json.loads(DIAGNOSIS.read_bytes())
    original = diagnosis["originalWitness"]
    if original["firstReportSha256"] != digest(FIRST):
        raise ValueError("different first-pass report")
    row, = [r for r in first["runs"] if r.get("callerSha256") == original["callerSha256"]]
    if row["counterexample"] != original["alleged"] or row["originalReplayChanged"] is not False:
        raise ValueError("different frozen counterexample")
    packet = BASE / "03/packet"
    if digest(packet / "inputs.json") != first["packetSha256"]:
        raise ValueError("different artifact packet")
    spec = json.loads((packet / "inputs.json").read_bytes())
    graphs = []
    for side in ("old", "new"):
        jars = [packet / entry["path"] for entry in spec[side]]
        if any(entry != {"path": f"{side}/{i:03d}.jar", "sha256": digest(jar)}
               for i, (jar, entry) in enumerate(zip(jars, spec[side]))):
            raise ValueError("different ordered dependency closure")
        graphs.append(jars)
    source = work / "PublicCaller.java"
    source.write_text(row["source"])
    if digest(source) != diagnosis["sourceSha256"]:
        raise ValueError("different generated source")
    return source, graphs, row["callerSha256"], {"observe": diagnosis["originalJvm"]}


def codec():
    graphs = [jars_for("commons-codec-" + version) for version in ("1.13", "1.14")]
    names = [CODEC_TYPE, "[[L" + CODEC_TYPE + ";"]
    expected = {"name": [names, names],
                "hierarchy": [[CODEC_TYPE, "java.lang.Object"], [CODEC_TYPE, CODEC_TYPE + "x86"]],
                "lookup": [[CODEC_TYPE, "absent"], [CODEC_TYPE, CODEC_TYPE + "x86"]]}
    return HERE.parent / "extended/CodecNames.java", graphs, None, expected


def check(work, checker, roots, graphs, target, observed, warm):
    runs = []
    for temperature in (("cold", "warm") if warm else ("cold",)):
        cmd = [str(checker), "equivalence", "--before", str(roots[0]), "--after", str(roots[1])]
        for flag, jars in zip(("--before-classpath", "--classpath"), graphs):
            if jars[1:]:
                cmd.extend([flag, classpath(jars[1:])])
        cmd.extend(["--target", target, "--engine", "native", "--gaps", "strict", "--unwind", "16",
                    "--max-array-length", "8", "--timeout", "120", "--work", str(work / temperature),
                    "--cache", str(work / "cache"), "--json"])
        run = benchmark.measure(cmd, 180)
        result = benchmark.outcome_of({"kind": "regression"}, run["stdout"]) or {}
        changed = observed[0] != observed[1]
        expected = "violation" if changed else "verified"
        if run["killed"] or run["exit"] != int(changed) or result.get("verdict") != expected:
            raise ValueError(f"{target} {temperature}: expected {expected}, got {result.get('verdict')}: {result.get('problem')}")
        reused = (result.get("reuse") or {}).get("kind")
        if reused != ("exact" if temperature == "warm" else None):
            raise ValueError(f"{target} {temperature}: unexpected cache result {reused}")
        if changed:
            witness = result["counterexample"]
            value, = witness["inputs"]
            if value.get("type") != "boolean" or type(value["value"]) is not bool:
                raise ValueError("expected a typed Boolean witness")
            index = int(value["value"])
            pair = [side[index] for side in observed]
            if pair[0] == pair[1] or [json.loads(witness[k]) for k in ("before", "after")] != pair:
                raise ValueError("alleged difference does not reproduce on the original releases")
        runs.append(dict(temperature=temperature, argv=cmd, **run))
    return runs


def measure(subject, checker, warm):
    with scratch(prefix="original-class-names-") as tmp:
        work = Path(tmp)
        source, graphs, locked_caller, expected = plexus(work) if subject == "plexus" else codec()
        runner = work / "ReadBoth.java"
        runner.write_text(RUNNER)
        classes = work / "caller"
        classes.mkdir()
        subprocess.run([JDK / "bin/javac", "-proc:none", "-parameters", "-g", "-cp", classpath(graphs[0]),
                        "-d", classes, source, runner], check=True)
        caller = classes / (source.stem + ".class")
        if locked_caller and digest(caller) != locked_caller:
            raise ValueError("different compiled public caller")
        roots = []
        for side, jars in zip(("old", "new"), graphs):
            root = work / side
            extract(jars[0], root)
            (root / caller.name).write_bytes(caller.read_bytes())
            roots.append(root)
        results = {}
        for method, oracle in expected.items():
            actual = []
            commands = []
            for jars in graphs:
                cmd = [str(JDK / "bin/java"), "-XX:-UsePerfData", "-ea", "-cp", classpath([classes, *jars]),
                       "ReadBoth", source.stem, method]
                commands.append(cmd)
                actual.append(subprocess.check_output(cmd, text=True, timeout=30).splitlines())
            if actual != oracle:
                raise ValueError(f"{subject} {method}: unexpected observations on original JVMs: {actual}")
            target = f"{source.stem}#{method}"
            results[target] = {"jvmArgv": commands, "jvmBeforeAfter": actual,
                               "runs": check(work / method, checker, roots, graphs, target, actual, warm)}
        return {"sourceSha256": digest(source), "callerSha256": digest(caller),
                "classpath": [[{"jar": p.name, "sha256": digest(p)} for p in jars] for jars in graphs],
                "properties": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", choices=("plexus", "codec", "both"), default="both")
    parser.add_argument("--cold-only", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT / "followup/lookup-and-names.json.gz")
    args = parser.parse_args()
    os.environ.update(javaenv())
    checker = Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")).resolve()
    freeze = json.loads((HERE.parent / "freeze.json").read_bytes())
    if digest(JDK / "lib/modules") != freeze["jdkModulesSha256"] or digest(JDK / "bin/javac") != freeze["jdkJavacSha256"]:
        raise ValueError("the selected Java image has changed")
    subjects = ("plexus", "codec") if args.subject == "both" else (args.subject,)
    data = {"phase": "post-freeze disclosed follow-up", "job": os.environ.get("VERIFY_JOB_ID"),
            "checkerSha256": digest(checker), "frozenCheckerSha256": freeze["checkerSha256"],
            "firstReportSha256": digest(FIRST), "jdkModulesSha256": freeze["jdkModulesSha256"],
            "inputs": [False, True], "subjects": {s: measure(s, checker, not args.cold_only) for s in subjects}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gzip.compress(encoded(data), mtime=0))
    print("Checked the full Boolean domain on both original JVMs and strict native for", ", ".join(subjects))


if __name__ == "__main__":
    main()
