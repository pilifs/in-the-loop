"""Bind the valid-range mirror theorem and the all-bounds JVM counterexample to Commons Lang 3.17.0."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

from controls import JDK
from frozen_range import long_kernel
from prepare import HERE, digest, request
from replay import LEAN, contained, fresh_rust

OWNER = "org/apache/commons/lang3/ArrayUtils"
JAR = Path.home() / ".cache/in-the-loop/receiver-construction/releases/commons-lang3-3.17.0/lib/commons-lang3-3.17.0.jar"
JAR_SHA = "6ee731df5c8e5a2976a1ca023b6bb320ea8d3539fbe64c8a1d5cb765127c33b4"
CLASS_SHA = "f21e4f7f69b2d98bed01748bd5b711b47458007ee762d07f1e4c4c32147bc8cc"
MATH_SHA = "f01ef790ce8af52b262c5f717f0e3db201863b9deb834915787ef31ed744d170"
LEAN_SHA = "db7f559d05795e7af52e42bc966c90240a39dcb9712161c54c97afa546e20c00"


def qualify(tmp):
    if digest(JAR.read_bytes()) != JAR_SHA or digest((LEAN / "bin/lean").read_bytes()) != LEAN_SHA:
        raise ValueError("release JAR or Lean executable differs")
    with zipfile.ZipFile(JAR) as jar:
        artifact = jar.read(OWNER + ".class")
    if digest(artifact) != CLASS_SHA:
        raise ValueError("ArrayUtils class differs")
    source = HERE / "java/ReverseRelease.java"
    java_flags = ["--add-modules", "jdk.jdeps", "--add-exports", "jdk.jdeps/com.sun.tools.classfile=ALL-UNNAMED"]
    subprocess.run([JDK / "bin/javac", *java_flags, "-proc:none", "-cp", JAR, "-d", tmp, source], check=True)
    physical = subprocess.check_output([JDK / "bin/java", "-Xverify:all", *java_flags, "-cp",
                                        os.pathsep.join(map(str, (tmp, JAR))), "ReverseRelease"], text=True)
    fields = dict(line.split(" ", 1) for line in physical.splitlines())
    if (fields.keys() != {"ArrayUtils", "Math", "reverse", "call7", "call14", "max", "min", "grid", "witness", "controls"}
            or fields["ArrayUtils"] != CLASS_SHA or fields["Math"] != MATH_SHA
            or fields["call7"] != "java/lang/Math.max(II)I" or fields["call14"] != "java/lang/Math.min(II)I"
            or fields["grid"] != "40525 3640 6652 2005 1641 121"
            or not fields["witness"].startswith("java.lang.ArrayIndexOutOfBoundsException")
            or not fields["witness"].endswith("heap=[]")):
        raise ValueError(physical)

    # Freeze the Rust answer independently of the Lean theorem. Its original request format
    # can name one companion. The Lean route additionally checks both resolved Math bodies.
    binary = long_kernel(tmp / "jdk-checker")
    req, hints, cls = (tmp / x for x in ("external.request", "hints.cert", "ArrayUtils.class"))
    req.write_text(request("range-reverse-mirror-v1", OWNER, CLASS_SHA, "reverse ([III)V", "reverse ([III)V"))
    hints.write_text("certificate 1\nrequest " + digest(req.read_bytes()) + "\nhints mirror\n")
    cls.write_bytes(artifact)
    before = fresh_rust(binary, req, hints, cls)
    if before["exit"] != 3 or before["stdout"] != "unsupported external theorem":
        raise ValueError(before)

    # Specialize reverseValid to the three code attributes read from the deployed classes.
    # The mathematics applies to an arbitrary entry heap and every valid pair of signed indices.
    terms = [str(list(bytes.fromhex(fields[key]))) for key in ("reverse", "max", "min")]
    theory = (HERE / "Reverse.lean").read_text()
    lemma = """
open ArrayReverse
theorem loadedReverse (old : Heap α) (lo hi n : Int)
    (bounds : 0 ≤ lo ∧ lo ≤ hi ∧ hi ≤ n ∧ n ≤ 2147483647) :
    ∃ out, execute CODE MAXIMUM MINIMUM old lo hi n = some out ∧
      ∀ k, out k = frame old lo hi k :=
  reverseValid CODE MAXIMUM MINIMUM (by decide) old lo hi n bounds
#print axioms loadedReverse
"""
    for name, term in zip(("CODE", "MAXIMUM", "MINIMUM"), terms, strict=True):
        lemma = lemma.replace(name, term)
    work = tmp / "lean"
    work.mkdir()
    module = work / "Loaded.lean"
    module.write_text(theory + lemma)
    checked = contained([str(LEAN / "bin/lean"), module.name], work, [LEAN, "/usr/lib", "/lib64", "/dev/urandom"])
    prefix = "'loadedReverse' depends on axioms: ["
    line = checked["stdout"]
    axioms = line[len(prefix):-1].split(", ") if line.startswith(prefix) and line.endswith("]") else []
    if checked["exit"] or not axioms or not set(axioms) <= {"propext", "Classical.choice", "Quot.sound"}:
        raise ValueError(checked)
    return {"schema": "release-reverse-qualification/v1", "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"),
            "key": "commons-lang3-3.17.0/ArrayUtils.reverse([III)V", "jarSha256": JAR_SHA,
            "classes": {OWNER: CLASS_SHA, "java/lang/Math": MATH_SHA}, "methods": fields,
            "frozenRust": {"request": req.read_text(), "checkerSha256": digest(binary.read_bytes()), **before},
            "lean": {"sha256": LEAN_SHA, "sourceSha256": digest(theory.encode()),
                     "loadedModuleSha256": digest(module.read_bytes()), **checked},
            "jvm": {"sourceSha256": digest(source.read_bytes()), "observerSha256": digest((tmp / "ReverseRelease.class").read_bytes()),
                    "normal": 40525, "exactExceptions": 3640, "valid": 6652},
            "validRange": "Mirror and unchanged outside frame in the byte-bound two-cursor model, assuming verified initialized classes and the stated JVM instruction semantics.",
            "allSignedBounds": "Refuted on the original JVM at length zero, start 0, end Integer.MIN_VALUE. The decrement at PC 18 wraps and the load at PC 30 throws before a store."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    dest = parser.parse_args().output
    with tempfile.TemporaryDirectory() as directory:
        evidence = qualify(Path(directory))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(evidence, indent=2) + "\n")
    print(evidence["key"], evidence["lean"]["stdout"], evidence["jvm"]["exactExceptions"])
