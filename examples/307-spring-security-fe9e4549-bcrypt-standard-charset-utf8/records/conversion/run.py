#!/usr/bin/env python3
"""Run ConversionDifferential on a JDK and record what it found with that runtime's identity.

    python3 -I run.py JAVA_HOME [JAVA_HOME ...] [--threads N] [--no-pairs] [--out DIR]

For each JDK: compiles ConversionDifferential.java with its javac, runs it (the two-unit part on N threads, 4 by
default; about four minutes), and writes DIR/jdk-<java.version>.json: the program's own object, and under
`runtime` the SHA-256 of the runtime image (lib/modules) and of the `release` file, and the bytecode of
String.getBytes(String), String.getBytes(Charset) and String.lookupCharset(String) as that JDK's javap prints it.
The bytecode is why the two overloads agree on OpenJDK: each ends in the one private `encode(Charset, byte,
byte[])`, and the named one differs by the lookup before it. The run is the check that the lookup of "UTF-8" gives
the object the other overload is passed, and that `encode` is what lib/src/bmc/bytes.rs says of it.

A second run with `-Dfile.encoding=COMPAT` under LC_ALL=C (a default charset that is not UTF-8 on 18 and later,
which the output states as `defaultCharset`) shows the two conversions do not depend on the default: it is
DIR/jdk-<java.version>-compat.json, without the two-unit part.

Exit 0 when no String differed on any JDK.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
METHODS = ("public byte[] getBytes(java.lang.String)", "public byte[] getBytes(java.nio.charset.Charset)", "private static java.nio.charset.Charset lookupCharset(java.lang.String)")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def bytecode(home):
    """The three methods' code, as javap prints it, with constant-pool indices taken out."""
    text = subprocess.run([str(home / "bin/javap"), "-p", "-c", "java.lang.String"], check=True, capture_output=True, text=True).stdout
    out = {}
    for block in re.split(r"\n(?=  \S)", text):
        head = block.strip().split("\n")[0]
        for m in METHODS:
            if head.startswith(m):
                out[m] = [re.sub(r"\s+", " ", re.sub(r"#\d+(, *\d+)?", "", line)).strip() for line in block.strip().split("\n")[1:] if line.strip()]
    missing = [m for m in METHODS if m not in out]
    if missing:
        sys.exit(f"{home}: javap shows no {missing}")
    return out


def run(home, classes, extra, env, threads):
    done = subprocess.run([str(home / "bin/java"), f"-Djava.util.concurrent.ForkJoinPool.common.parallelism={max(threads - 1, 1)}", *extra[0], "-cp", str(classes),
                           "ConversionDifferential", *extra[1]], capture_output=True, text=True, env=env)
    if done.returncode not in (0, 1) or not done.stdout.strip():
        sys.exit(f"{home}: the run failed ({done.returncode}): {done.stderr[-2000:]}")
    return json.loads(done.stdout), done.returncode


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("homes", nargs="+", type=Path)
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--no-pairs", action="store_true", help="leave out the Strings of two units (for a quick look; the record says twoUnits 0)")
    p.add_argument("--out", type=Path, default=HERE)
    args = p.parse_args()
    source = HERE / "ConversionDifferential.java"
    failed = False
    for home in args.homes:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([str(home / "bin/javac"), "-d", tmp, str(source)], check=True)
            runtime = {"modulesSha256": sha256(home / "lib/modules"), "releaseSha256": sha256(home / "release"),
                       "release": (home / "release").read_text().strip().split("\n"), "stringBytecode": bytecode(home)}
            for suffix, extra, env in (("", ([], ["--no-pairs"] if args.no_pairs else []), dict(os.environ)),
                                       ("-compat", (["-Dfile.encoding=COMPAT"], ["--no-pairs"]), dict(os.environ, LC_ALL="C", LANG="C"))):
                result, code = run(home, tmp, extra, env, args.threads)
                failed |= code != 0
                record = {"schema": "conversion-differential/v1", "source": {"file": source.name, "sha256": sha256(source)},
                          "options": extra[0] + extra[1] + (["LC_ALL=C"] if suffix else []), "runtime": runtime, "result": result}
                path = args.out / f"jdk-{result['java.version']}{suffix}.json"
                path.write_text(json.dumps(record, indent=1) + "\n")
                print(f"{path.name}: tried {result['tried']['total']}, differed {result['differed']}, default charset {result['defaultCharset']}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
