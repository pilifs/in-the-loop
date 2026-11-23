"""Compile rebound controls from the published source JAR, and observe their real JVM behavior."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
from prepare import HERE, GUAVA, HASHES, JAR_SHA, INDEX, digest, request

RELEASE = Path(
    os.environ.get(
        "KERNEL_GUAVA_DIR", Path.home() / ".cache/in-the-loop/trusted-kernel/releases/guava-33.4.8-jre"
    )
)
JDK = Path(os.environ.get("JAVA21_HOME", Path.home() / ".sdkman/candidates/java/21.0.13.0+9-tem"))
SOURCE_SHA = "9d3c6aad893daac9d4812eb9fa4c3f7956a9f2e472eb7df2fea0e467fed7e766"
# name, input and expected public observations. A non-returning JVM only supplies a timeout observation.
INPUTS = {
    "Ints": (7, [7, 7], 0, [7, 7]),
    "Longs": (4294967296, [0, 4294967296], 1, [0, 4294967296]),
    "last": (7, [7, 7], 1, [7, 7]),
    "start": (7, [7], -1, [7]),
    "miss": (7, [], 0, []),
    "frame": (7, [7], 0, [0]),
    "stuck": (8, [7], None, None),
    "layout": (7, [7, 7], 0, [7, 7]),
    "narrow": (4294967296, [0, 4294967296], 0, [0, 4294967296]),
}


def owner_of(case):
    return "Longs" if case in ("Longs", "narrow") else "Ints"


def compile_variant(case, out):
    name = owner_of(case)
    path = RELEASE / "sources/guava-33.4.8-jre-sources.jar"
    if digest(path.read_bytes()) != SOURCE_SHA:
        raise ValueError("Guava source JAR digest")
    with zipfile.ZipFile(path) as z:
        text = z.read(GUAVA + name + ".java").decode()
    primitive = "int" if name == "Ints" else "long"
    start = text.index(f"  public static int indexOf({primitive}[] array, {primitive} target)")
    end = text.index("\n  }", text.index("  private static int indexOf(", start)) + 4
    method = text[start:end]
    if case == "last":
        method = (
            method.replace("    for (int i", "    int result = -1;\n    for (int i")
            .replace("return i;", "result = i;")
            .replace("return -1;", "return result;")
        )
    else:
        changes = {
            "start": ("target, 0, array.length", "target, 1, array.length"),
            "miss": ("return -1;", "return 0;"),
            "frame": ("return i;", "int result = i;\n        array[i] = 0;\n        return result;"),
            "stuck": ("i++)", "i += 0)"),
            "layout": (
                "return indexOf(array, target, 0, array.length);",
                "int limit = array.length;\n    return indexOf(array, target, 0, limit);",
            ),
            "narrow": ("array[i] == target", "(int) array[i] == (int) target"),
        }
        before, after = changes[case]
        if method.count(before) != 1:
            raise ValueError("source control changed")
        method = method.replace(before, after)
    if method == text[start:end]:
        raise ValueError("no change in public/helper pair")
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        java = tmp / (name + ".java")
        java.write_text(text[:start] + method + text[end:])
        subprocess.run(
            [
                JDK / "bin/javac",
                "--release",
                "8",
                "-proc:none",
                "-Xlint:-options",
                "-g",
                "-parameters",
                "-classpath",
                str(RELEASE / "lib/*"),
                "-d",
                tmp,
                java,
            ],
            check=True,
        )
        data = (tmp / (GUAVA + name + ".class")).read_bytes()
    out.write_bytes(data)
    return {
        "sourceJarSha256": SOURCE_SHA,
        "sourceClassSha256": digest(text.encode()),
        "reboundSourceSha256": digest((text[:start] + method + text[end:]).encode()),
        "changedMethods": method,
    }


def prepare(case, out):
    out.mkdir(parents=True, exist_ok=True)
    name = owner_of(case)
    artifact = out / "artifact.bin"
    req = out / "external.request"
    if case in ("Ints", "Longs"):
        shutil.copyfile(HERE / "inputs" / (name + ".bin"), artifact)
        shutil.copyfile(HERE / "requests" / (name + ".request"), req)
        source = {"releaseJarSha256": JAR_SHA}
    else:
        source = compile_variant(case, artifact)
        elem = "I" if name == "Ints" else "J"
        sup = GUAVA + "IntsMethodsForWeb " + HASHES["IntsMethodsForWeb"] if name == "Ints" else None
        req.write_text(
            request(
                INDEX,
                GUAVA + name,
                digest(artifact.read_bytes()),
                f"indexOf ([{elem}{elem})I",
                f"indexOf ([{elem}{elem}II)I",
                sup,
            )
        )
    support = [HERE / "inputs/IntsMethodsForWeb.bin"] if name == "Ints" else []
    return req, artifact, support, source


def cells_arg(values):
    return ",".join(map(str, values)) or "-"


def observe(case, artifact, classes):
    name = owner_of(case)
    path = classes / (GUAVA + name + ".class")
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(artifact, path)
    target, values, expected, after = INPUTS[case]
    cmd = [
        JDK / "bin/java",
        "-Xverify:all",
        "-cp",
        str(classes) + os.pathsep + str(RELEASE / "lib/*"),
        "Observe",
        name,
        str(target),
        cells_arg(values),
    ]
    with subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        try:
            out, err = proc.communicate(timeout=2 if expected is None else 15)
            timeout = False
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
            timeout = True
    lines = out.splitlines()
    if not lines or lines[0] != "entered " + digest(artifact.read_bytes()):
        raise ValueError((case, out, err))
    if expected is None:
        if not timeout or len(lines) != 1:
            raise ValueError("no-progress control unexpectedly returned")
    elif timeout or proc.returncode or lines[1:] != [f"return {expected}", "heap " + str(after)]:
        raise ValueError((case, out, err))
    return {
        "input": values,
        "target": target,
        "stdout": lines,
        "timedOut": timeout,
        "return": expected,
        "heapAtReturn": after,
    }
