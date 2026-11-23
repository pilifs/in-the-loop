"""Extract the frozen release entries and compile the scalar fixture with the chosen JDK."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
GUAVA = "com/google/common/primitives/"
JAR_SHA = "f3d7f57f67fd622f4d468dfdd692b3a5e3909246c28017ac3263405f0fe617ed"
HASHES = {
    "Ints": "ae581f721521c93250639d17348c5b7215f3591a1bb433fb63985caa4364edbb",
    "IntsMethodsForWeb": "a31b977048c2bc8257a8371ab2c89e9026e0c52507746c09e34a47ad94217bd6",
    "Longs": "b8c75a5f24b89f0a6a263bd56b4e4e9f4c53bd7a1e8e2fc9ad4975113f4396d9",
}
ENVIRONMENT = "initialized-verified-jvm-v1"
SCALAR = "scalar-equality-v1"
INDEX = "least-index-frame-total-v1"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def request(theorem, owner, sha, entry, companion, support=None):
    lines = ["request 1", "theorem " + theorem, "environment " + ENVIRONMENT, f"class {owner} {sha}",
             "entry " + entry, "companion " + companion]
    if support:
        lines.append("support " + support)
    return "\n".join(lines) + "\n"


def main():
    jar = Path(os.environ.get("GUAVA_JAR", Path.home() / ".cache/in-the-loop/targets/sha256" / JAR_SHA))
    if not jar.is_file():
        jar = Path.home() / ".cache/in-the-loop/trusted-kernel/releases/guava-33.4.8-jre/lib/guava-33.4.8-jre.jar"
    if digest(jar.read_bytes()) != JAR_SHA:
        raise ValueError("release JAR differs from the frozen request")
    with zipfile.ZipFile(jar) as archive:
        for name, sha in HASHES.items():
            data = archive.read(GUAVA + name + ".class")
            if digest(data) != sha:
                raise ValueError(f"{name} differs from its historical record")
            (HERE / "inputs" / (name + ".bin")).write_bytes(data)
        (HERE / "inputs/Guava-LICENSE").write_bytes(archive.read("META-INF/LICENSE"))
    for name, elem in [("Ints", "I"), ("Longs", "J")]:
        sup = GUAVA + "IntsMethodsForWeb " + HASHES["IntsMethodsForWeb"] if name == "Ints" else None
        body = request(INDEX, GUAVA + name, HASHES[name], f"indexOf ([{elem}{elem})I",
                       f"indexOf ([{elem}{elem}II)I", sup)
        (HERE / "requests" / (name + ".request")).write_text(body)
    with tempfile.TemporaryDirectory() as tmp:
        jdk = Path(os.environ.get("JAVA21_HOME", Path.home() / ".sdkman/candidates/java/21.0.13.0+9-tem"))
        subprocess.run([jdk / "bin/javac", "-g:none", "-proc:none", "--release", "21", "-d", tmp,
                        HERE / "java/Scalar.java"], check=True)
        data = (Path(tmp) / "fixtures/Scalar.class").read_bytes()
    (HERE / "inputs/Scalar.bin").write_bytes(data)
    for method in ("add", "shifted"):
        (HERE / "requests" / (method + ".request")).write_text(
            request(SCALAR, "fixtures/Scalar", digest(data), "multiply (I)I", method + " (I)I"))


if __name__ == "__main__":
    main()
