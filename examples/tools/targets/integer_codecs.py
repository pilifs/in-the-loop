"""Discover and scaffold a signed integer encoder/decoder from two ordered Java deployments."""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from targets import change_evidence, change_inventory, runtime_jar, runtime_jdk, upgrade_replay

SAMPLES = [0, 1, 2, 3, 31, 32, 127, 128, 2147483646, 2147483647]
RAW_CONTROLS = [-1, -2147483648]
# Operand bytes are interpreted only at instruction boundaries.
SCALAR = {0x1a, *range(0x02, 0x09), 0x10, 0x11, 0x60, 0x64, 0x74, 0x78, 0x7a, 0x7c, 0x7e, 0x80, 0x82, 0xac}


def roles(body, handlers):
    if not body or handlers or len(body) > 64:
        return set()
    ops = [op for _, op in change_inventory.instructions(body)]
    parts = set(ops)
    if ops[-1] != 0xac or not parts <= SCALAR or not {0x1a, 0x82} <= parts or not parts & {0x7a, 0x7c}:
        return set()
    return {name for name, op in (("encoder", 0x78), ("decoder", 0x7e)) if op in parts}


def inventory(jar, feature):
    found = {"encoder": {}, "decoder": {}}
    with zipfile.ZipFile(jar) as archive:
        for name, info in runtime_jar.effective_entries(archive, feature).items():
            if not name.endswith(".class") or name.startswith("META-INF/"):
                continue
            java = name[:-6].replace("/", ".")
            if not all(re.fullmatch(r"[a-zA-Z_$][\w$]*", p, re.ASCII) for p in java.split(".")):
                continue
            data = archive.read(info)
            if not runtime_jar.class_flags(data) & 1:
                continue
            for (method, desc), (flags, body, handlers) in runtime_jar._declarations(data, with_code=True)[1].items():
                if desc == "(I)I" and flags & 9 == 9 and not flags & 0x1040 and re.fullmatch(r"[a-zA-Z_$][\w$]*", method, re.ASCII):
                    for role in roles(body, handlers):
                        found[role][(java, method)] = hashlib.sha256(body).hexdigest()
    return found


def caller(encode, decode):
    def call(m):
        return m[0].replace("$", ".") + "." + m[1]
    return f"""public final class IntegerCodec {{
    public static int decode(int n) {{ return {call(decode)}(n); }}
    public static int roundTrip(int n) {{ return {call(encode)}(decode(n)); }}
    public static boolean primary(int n) {{
        return n < 0 || decode(n) == (n % 2 == 0 ? n / 2 : -1 - n / 2);
    }}
    public static boolean control(int n) {{ return n < 0 || roundTrip(n) == n; }}
    public static boolean inverse(int n) {{ return n < 0 || !primary(n); }}
    public static boolean unsigned(int n) {{
        long bits = Integer.toUnsignedLong(n);
        int signed = (int) (bits % 2 == 0 ? bits / 2 : -1 - bits / 2);
        return decode(n) == signed;
    }}
}}
"""


OBSERVER = """import java.nio.file.Path;
public final class ObserveCodec {
    public static void main(String[] args) throws Exception {
        for (int i = 1; i <= 2; i++) {
            Class<?> entry = Class.forName(args[i], false, IntegerCodec.class.getClassLoader());
            Path origin = Path.of(entry.getProtectionDomain().getCodeSource().getLocation().toURI());
            if (!origin.toRealPath().equals(Path.of(args[0]).toRealPath())) throw new AssertionError("different defining JAR");
        }
        for (int i = 3; i < args.length; i++) {
            int n = Integer.parseInt(args[i]);
            System.out.println(n + " " + IntegerCodec.decode(n) + " " + IntegerCodec.roundTrip(n));
        }
    }
}
"""


def scaffold(encode, decode, graphs, jdk, dest, identity):
    dest.mkdir()
    probe = dest / "IntegerCodec.java"
    probe.write_text(caller(encode, decode))
    expected = [[n, n // 2 if n % 2 == 0 else -1 - n // 2, n] for n in SAMPLES]
    registration = {"encoder": list(encode), "decoder": list(decode), "descriptor": "(I)I", "inputs": identity,
                    "callerSha256": upgrade_replay.sha(probe), "jdkModulesSha256": upgrade_replay.sha(jdk / "lib/modules") if (jdk / "lib/modules").is_file() else None,
                    "primary": "Decode each nonnegative Java int by parity and half its magnitude.",
                    "unchangedControl": "Encode the decoded value and recover the input on the same domain.",
                    "rawBitHypothesis": "Decode all 32-bit inputs as unsigned zigzag bit patterns.",
                    "boundaries": RAW_CONTROLS, "expectedSamples": expected}
    change_evidence.write_json(dest / "registration.json", registration)
    record = {"registrationSha256": upgrade_replay.sha(dest / "registration.json"), "sides": {}, "firstScaffoldStop": None}
    with tempfile.TemporaryDirectory(prefix="integer-codec-") as temporary:
        work = Path(temporary)
        runner = work / "ObserveCodec.java"
        runner.write_text(OBSERVER)
        classes = work / "classes"
        classes.mkdir()
        try:
            subprocess.run([jdk / "bin/javac", "-J-XX:-UsePerfData", "-proc:none", "-g", "-parameters", "-classpath",
                            os.pathsep.join(map(str, graphs["old"])), "-d", classes, runner, probe],
                           timeout=30, capture_output=True, check=True)
            record["callerClassSha256"] = upgrade_replay.sha(classes / "IntegerCodec.class")
            for side, jars in graphs.items():
                proc = subprocess.run([jdk / "bin/java", "-XX:-UsePerfData", "-Xmx256m", "-ea", "-cp",
                    os.pathsep.join(map(str, [classes, *jars])), "ObserveCodec", jars[0], encode[0], decode[0],
                    *map(str, SAMPLES + RAW_CONTROLS)], timeout=30, capture_output=True, text=True)
                rows = [list(map(int, line.split())) for line in proc.stdout.splitlines()] if not proc.returncode else []
                record["sides"][side] = {"exit": proc.returncode, "rows": rows,
                                         "failure": proc.stderr.replace(str(work), "$WORK")[-900:] if proc.returncode else None}
                if proc.returncode or [r[0] for r in rows] != SAMPLES + RAW_CONTROLS or rows[:len(expected)] != expected:
                    record["firstScaffoldStop"] = record["firstScaffoldStop"] or f"{side} original JVM or registered primary/control"
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            reason = getattr(error, "stderr", None) or str(error)
            if isinstance(reason, bytes):
                reason = reason.decode(errors="replace")
            record["firstScaffoldStop"] = reason.replace(str(work), "$WORK")[-900:]
    change_evidence.write_json(dest / "scaffold.json", record)
    return record


def discover(before, after, jdk, dest):
    graphs, inputs = {}, {}
    for side, path in (("old", before), ("new", after)):
        doc = json.loads(path.read_bytes())
        graphs[side], _, inputs[side] = upgrade_replay.checked_classpath(path, doc, doc["classpath"][0]["sha256"])
    feature = int(runtime_jdk.identity(jdk)["feature"])
    if feature < 11:
        raise ValueError("the original launch observer requires JDK 11 or newer")
    old, new = [inventory(graphs[s][0], feature) for s in ("old","new")]
    enc, dec = [sorted(old[r].keys() & new[r].keys()) for r in ("encoder", "decoder")]
    # Pair within a Java package. Prefer a shared owner, then a stable lexical order.
    choices = sorted(((a,b) for a,b in itertools.product(enc,dec) if a!=b and a[0].rpartition(".")[0] == b[0].rpartition(".")[0]),
                     key=lambda p: (p[0][0] != p[1][0], p))
    dest.mkdir(parents=True, exist_ok=False)
    rows = []
    for i, (encode, decode) in enumerate(choices[:8], 1):
        sub = f"candidate-{i}"
        methods = {side: {role: inv[role][key] for role,key in (("encoder", encode),("decoder", decode))}
                   for side,inv in (("old",old),("new",new))}
        state = scaffold(encode, decode, graphs, jdk, dest / sub, inputs)
        rows.append({"directory":sub,"encoder":encode,"decoder":decode,"methodBytes":methods,
                     "firstScaffoldStop":state["firstScaffoldStop"]})
    report = {"inputs":inputs, "candidateCount":len(choices), "measuredCandidates":rows, "candidateLimit":8,
              "firstScaffoldStop":None if choices else "no common public static encoder and decoder of a supported shape"}
    change_evidence.write_json(dest / "discovery.json", report)
    return report


def main(argv):
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("before", "after", "jdk", "output"):
        cli.add_argument("--" + name, type=Path, required=True)
    args = cli.parse_args(argv)
    result = discover(args.before, args.after, args.jdk.resolve(), args.output.resolve())
    print(result["firstScaffoldStop"] or result["measuredCandidates"])
    return 0
