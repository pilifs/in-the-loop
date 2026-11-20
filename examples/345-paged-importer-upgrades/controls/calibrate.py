"""Run the same compiled application on all four independently built dependency pairs."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

EXAMPLE = Path(__file__).resolve().parents[1]
TOOLS = EXAMPLE.parent / "tools"
sys.path.insert(0, str(TOOLS))
from targets import finite_oracle, runtime_jdk, runtime_maven

DEPENDENCIES = {
    "commons-io:commons-io:2.22.0": "2b9a7b1f726fb86216dbd2c8321eabe0221dbd5b1be81c18e1cb53811b104758",
    "commons-codec:commons-codec:1.22.0": "d164fe79f262c32d9b18a0b5b2d317d1c27653d5e98fd2b998c24bf901c72ce4",
}
EXPECTED = {
    "parent-parent": [48, 40, 68],
    "fix-parent": [0, 40, 40],
    "parent-fix": [48, 0, 48],
    "fix-fix": [0, 0, 0],
}


def measure(work):
    library = EXAMPLE / "records/builds"
    out = EXAMPLE / "records/matrix"
    out.mkdir(parents=True, exist_ok=True)
    home = runtime_jdk.home("21")
    if home is None:
        raise ValueError("the matrix requires JDK 21")
    java, javac = Path(home) / "bin/java", Path(home) / "bin/javac"
    cache = runtime_maven.Cache()
    recipes = json.loads((EXAMPLE / "controls/libraries.json").read_text())
    jars = {}
    for name, recipe in recipes.items():
        if "build" not in recipe:
            continue
        record = json.loads((library / (name + ".json")).read_text())
        if (
            record["recipe"] != {k: v for k, v in recipe.items() if k != "sha256"}
            or record["build"]["checkout"]["commit"] != recipe["commit"]
        ):
            raise ValueError(f"{name}: mismatched build recipe or checkout")
        [original] = [item for item in record["artifacts"] if item["role"] == "original"]
        if original["sha256"] != recipe["sha256"]:
            raise ValueError(f"{name}: the selected JAR differs from the declared upstream product")
        if (
            runtime_maven.sha256_of(library / record["resolutionFile"])
            != record["build"]["toolchain"]["resolution"]["sha256"]
        ):
            raise ValueError(f"{name}: stale dependency resolution inventory")
        deps = {d["coordinates"]: d["sha256"] for d in record["artifacts"] if d["role"] == "dependency"}
        if deps != (DEPENDENCIES if name.startswith("csv-") else {}):
            raise ValueError(f"{name}: unexpected Maven dependencies: {deps}")
        jars[name] = work / (name + ".jar")
        ok, reason = cache.restore(original["sha256"], jars[name])
        if not ok:
            raise ValueError(f"{name}: {reason}; repeat the recorded upstream build")
    for name, (coordinates, digest) in zip(("io-api", "codec"), DEPENDENCIES.items()):
        jars[name] = work / (name + ".jar")
        item = runtime_maven.check_item({"coordinates": coordinates, "sha256": digest}, "dependency")
        runtime_maven.acquire(item, jars[name], cache)
    classes = work / "classes"
    classes.mkdir()
    sources = sorted(p for root in ("client", "adapter", "driver") for p in (EXAMPLE / root).rglob("*.java"))
    helpers = TOOLS / "targets/java"
    compile_cp = [jars[key] for key in ("csv-fix", "io-api", "codec")]
    subprocess.run(
        [
            javac,
            "--release",
            "21",
            "-encoding",
            "UTF-8",
            "-parameters",
            "-g",
            "-implicit:none",
            "-cp",
            os.pathsep.join(map(str, compile_cp)),
            "-d",
            classes,
            *sources,
            helpers / "org/intheloop/controls/Grid.java",
            helpers / "LoadedClasses.java",
        ],
        check=True,
    )
    table = finite_oracle.Table(EXAMPLE / "controls/table.json")
    report = {
        "jdk": runtime_jdk.identity(home),
        "compileClasspath": [runtime_maven.sha256_of(j) for j in compile_cp],
        "clientClasses": {
            p.name: runtime_maven.sha256_of(p) for p in sorted(classes.glob("importer/PageImporter*.class"))
        },
        "configurations": {},
    }
    for cell, expected in EXPECTED.items():
        io, csv = cell.split("-")
        selected = [jars["io-" + io], jars["csv-" + csv], jars["codec"]]
        cp = os.pathsep.join(map(str, [classes, *selected]))
        names = [
            "org.apache.commons.io.input.BOMInputStream",
            "org.apache.commons.csv.CSVParser",
            "org.apache.commons.codec.binary.Base64",
        ]
        origins = subprocess.check_output([java, "-cp", cp, "LoadedClasses", work, *names], text=True)
        rows = origins.splitlines()
        if len(rows) != len(names):
            raise ValueError("incomplete list of loaded classes")
        for line, name, jar in zip(rows, names, selected):
            with zipfile.ZipFile(jar) as archive:
                digest = hashlib.sha256(archive.read(name.replace(".", "/") + ".class")).hexdigest()
            if line.split("\t") != [name, jar.name, digest]:
                raise ValueError(f"{cell}: JVM loaded a different {name}")
        raw = subprocess.check_output([java, "-cp", cp, "importer.ImportCases"])
        observations = [json.loads(line) for line in raw.splitlines()]
        mismatch = {key: 0 for key in table.fields}
        controls = 0
        for case, row in table.observations(observations):
            control = not case["input"]["preview"] and case["input"]["start"] == 1
            controls += control
            for key, field in table.fields.items():
                correct = finite_oracle.agrees(row["direct"][key], case["expected"][key], field)
                if row["adapter"][key] != int(correct) or (control and not correct):
                    raise ValueError(
                        f"{cell} input {case['id']}: {key} correspondence or positive control failed"
                    )
                mismatch[key] += not correct
        if (
            len(observations) != 96
            or controls != 24
            or [mismatch[k] for k in ("bytes", "count", "page")] != expected
        ):
            raise ValueError(f"{cell}: unexpected matrix {mismatch}")
        (out / (cell + ".jsonl")).write_bytes(raw)
        report["configurations"][cell] = {
            "inputs": 96,
            "positiveControls": controls,
            "mismatches": mismatch,
            "runtimeClasspath": [runtime_maven.sha256_of(jar) for jar in selected],
            "loaded": rows,
            "stdoutSha256": hashlib.sha256(raw).hexdigest(),
            "example": next(row for row in observations if row["id"] == 6),
        }
        print(cell, mismatch, flush=True)
    (out / "matrix.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="csv-matrix-") as directory:
        measure(Path(directory))
