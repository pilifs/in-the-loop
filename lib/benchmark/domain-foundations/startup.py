"""Profile original startup bytecode on a fresh JVM, then disassemble the selected class files offline."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import unquote, urlparse
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import runtime_jar, runtime_jdk, runtime_maven

# Each row names one entry into a fresh JVM. Additions to the classpath and the caller's
# mutation are challenge controls. They cannot establish a fact at original scope.
PROFILES = {
    "355": [
        ("roots", "roots", {}),
        ("one-cpu", "roots", {"cpus": 1}),
        ("four-cpu-directory", "roots", {"cpus": 4, "directory": "scratch"}),
        ("extra-mapred-site", "roots", {"resource": True}),
        ("direct", "direct", {}), ("factory", "factory", {}), ("schema-observer", "schema", {}),
        ("fresh-reducers", "reducers", {}), ("site-reducers", "reducers", {"resource": True}),
        ("overlay-reducers", "reducers", {"mode": "overlay"}),
        ("initializer-ok", "initializer-control", {}),
        ("initializer-throws", "initializer-control", {"mode": "throws"}),
    ],
    "360": [
        ("node-lf", "node", {}), ("node-crlf", "node", {"separator": "\r\n", "cpus": 1}),
        ("node-empty", "node", {"separator": "", "directory": "scratch"}),
        ("node-absent", "node", {"mode": "absent"}),
        ("separator-lf", "separator", {}), ("separator-crlf", "separator", {"separator": "\r\n"}),
        ("separator-absent", "separator", {"mode": "absent"}),
    ],
}


def document(path, value):
    data = (json.dumps(value, indent=None if path.suffix == ".gz" else 2, sort_keys=True) + "\n").encode()
    path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == ".gz" else data)


def materialize(folder, side, work):
    spec = json.loads((folder / "target.json").read_text())
    path = folder / spec["preparation"]["capturedBuilds"][side]
    record = json.loads(path.read_text())
    if record["recipe"]["commit"] != spec["history"]["revisions"][side]["commit"]:
        raise ValueError("the pinned build identifies a different revision")
    cp = []
    for i, item in enumerate(record["artifacts"]):
        h = item["sha256"]
        jar = runtime_maven.Cache().path(h)
        if runtime_maven.sha256_of(jar) != h:
            raise ValueError("a selected JAR differs from its captured build")
        # The class loader needs ordinary JAR names. Hashes and ordering come from Maven.
        link = work / f"{i:03}.jar"
        link.symlink_to(jar)
        cp.append(link)
    return cp, {"revision": record["recipe"]["commit"], "build": str(path.relative_to(ROOT)),
                "buildSha256": runtime_maven.sha256_of(path), "orderedJars": [a["sha256"] for a in record["artifacts"]]}


def launcher(cmd, cwd, env=None):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=120)
    if r.returncode:
        raise ValueError(f"{Path(cmd[0]).name} exited {r.returncode}: {r.stderr.decode(errors='replace')[-1500:]}")
    return r.stdout


def fields(path):
    events = Counter()
    statuses = {}
    for line in path.read_text().splitlines():
        cells = line.split("\t")
        if cells[1] == "status":
            # Hidden class runtime suffixes vary across processes; their bytes cannot be
            # identified with a JAR entry. Keep them explicitly outside bytecode coverage.
            name = re.sub(r"[./]0x[0-9a-fA-F]+;", "/<hidden>;", cells[2])
            statuses.setdefault(cells[0], {}).setdefault(name, set()).add(int(cells[3]))
        else:
            if len(cells) != 9:
                raise ValueError("malformed JVMTI field event")
            name = re.sub(r"[./]0x[0-9a-fA-F]+;", "/<hidden>;", line)
            events[name] += 1
    return events, {phase: {name: sorted(bits) for name, bits in names.items()} for phase, names in statuses.items()}


def inspect_classes(cp, releases, initialized, compiled, jdk, work):
    destination = work / "selected"
    destination.mkdir()
    names, origins = set(initialized), {}
    for i, jar in enumerate(cp):
        with zipfile.ZipFile(jar) as z:
            entries = runtime_jar.effective_entries(z, 21)
            for name in sorted(names & {key[:-6] for key in entries if key.endswith(".class")}):
                entry = entries[name + ".class"]
                if releases.get(name) != jar.resolve() and releases.get(name) != jar:
                    raise ValueError("selected class origin disagrees with the JVM: " + name)
                data = z.read(entry)
                dest = destination / (name + ".class")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                origins[name] = {"jarIndex": i, "entry": entry.filename, "sha256": hashlib.sha256(data).hexdigest()}
                names.remove(name)
    table = launcher([jdk / "bin/java", "-Djava.io.tmpdir=" + str(work), "-cp", compiled,
                      "foundation.Inventory", destination], work).decode().splitlines()
    return {"selected": origins, "outsideSelectedJars": sorted(names), "bytecode": table}


def check_observations(number, side, action, options, rows):
    if options.get("mode") in ("absent", "throws"):
        cause = "NullPointerException" if options["mode"] == "absent" else "IllegalStateException"
        # Node can wrap the erroneous enum in another initializer. The originating cause
        # and the sticky initialization failure on a second attempt are observable.
        return (len(rows) == 2 and all(key == "exception" for key, _ in rows)
                and "java.lang.ExceptionInInitializerError" in rows[0][1]
                and rows[0][1].endswith("java.lang." + cause)
                and rows[1][1].startswith("java.lang.NoClassDefFoundError"))
    data = dict(rows)
    if action == "roots":
        return rows == [["initialized", name] for name in (
            "org.apache.avro.Schema", "org.apache.hadoop.io.BytesWritable", "org.apache.hadoop.mapred.JobConf",
            "org.apache.hadoop.security.Credentials")]
    if action == "schema":
        return data == {"type": "BYTES", "same": "true"}
    if action == "reducers":
        if options.get("mode") == "overlay":
            return data.get("exception", "").endswith("java.lang.NumberFormatException")
        return data == {"reducers": "1"}
    if action == "separator":
        return data == {"separatorUnits": ",".join(str(ord(c)) for c in options.get("separator", "\n"))}
    if action == "initializer-control":
        return data == {"remaining": "1"}
    if number == "360":
        values = "1,1" if side == "fix" else "0,1"
        return data == {"postorder": values, "terminal": values, "preorder": "1,1"}
    prefix = ",".join(["1"] * 21)
    bounds = ",".join(str(int(side == "fix" or length == capacity))
                      for capacity in range(6) for length in range(capacity + 1))
    return data == ({"directLimit": bounds} if action == "direct" else
                    {"bounds": bounds, "prefix": prefix, "rejected": bounds})


def profile(number, side, output):
    folder, = (ROOT / "examples").glob(number + "-*")
    subject, tool = (Path(runtime_jdk.home(version)) for version in ("21", "25"))
    if runtime_jdk.release(subject)["JAVA_VERSION"] != "21.0.13":
        raise ValueError("the campaign requires the original Temurin 21.0.13 subject")
    result = output / side
    result.mkdir(parents=True, exist_ok=True)
    begin = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="domain-startup-") as temp:
        work = Path(temp)
        cp, provenance = materialize(folder, side, work)
        compiled, extra = work / "classes", work / "resource"
        compiled.mkdir()
        extra.mkdir()
        (extra / "mapred-site.xml").write_text("<configuration><property><name>mapreduce.job.reduces</name>"
                                               "<value>invalid</value></property></configuration>\n")
        join = os.pathsep.join
        launcher([subject / "bin/javac", "-J-Djava.io.tmpdir="+temp, "-cp", join(map(str, cp)),
                  "-d", compiled, HERE / "StartupProfile.java", *sorted((folder / "adapter").rglob("*.java"))], work)
        launcher([tool / "bin/javac", "-J-Djava.io.tmpdir="+temp, "-d", compiled, HERE / "Inventory.java"], work)
        agent = work / "fields.so"
        launcher(["cc", "-Wall", "-Wextra", "-Werror", "-std=c11", "-O2", "-fPIC", "-shared",
                  "-I" + str(subject / "include"), "-I" + str(subject / "include/linux"), HERE / "FieldEvents.c",
                  "-o", agent], work)
        provenance.update(subject=runtime_jdk.release(subject)["JAVA_RUNTIME_VERSION"],
                          modulesSha256=runtime_maven.sha256_of(subject / "lib/modules"),
                          jvmSha256=runtime_maven.sha256_of(subject / "lib/server/libjvm.so"),
                          disassembler=runtime_jdk.release(tool)["JAVA_RUNTIME_VERSION"],
                          sources={s: runtime_maven.sha256_of(HERE / s) for s in
                                   ("StartupProfile.java", "FieldEvents.c", "Inventory.java", "startup.py")})
        profiles, watches, initialized, releases = {}, {}, set(), {}
        for label, action, options in PROFILES[number]:
            base = [subject / "bin/java", "-Djava.io.tmpdir=" + temp,
                    "-XX:ActiveProcessorCount=" + str(options.get("cpus", 2))]
            if "separator" in options:
                base.append("-Dline.separator=" + options["separator"])
            cp_arg = join(map(str, [compiled, *([extra] if options.get("resource") else []), *cp]))
            args = [action, options.get("mode", "normal")]
            cwd = work if options.get("directory") else Path("/")
            plain = launcher([*base, "-cp", cp_arg, "foundation.StartupProfile", "plain", *args], cwd, {})
            events, loads = work / "fields.tsv", work / "loads.log"
            measured = launcher([*base, f"-Xlog:class+load=info:file={loads}:none",
                                f"-agentpath:{agent}={events}", "-cp", cp_arg, "foundation.StartupProfile", "record",
                                *args], cwd, {})
            if measured != plain:
                raise ValueError(f"{side} {label}: instrumented and ordinary JVM public answers differ")
            rows = [line.split("\t", 1) for line in plain.decode().splitlines()]
            if not rows or any(len(row) != 2 for row in rows):
                raise ValueError("a JVM did not return the expected observation format")
            counts, statuses = fields(events)
            watches[label] = {"fieldSites": sorted(counts), "classStatus": statuses}
            for names in statuses.values():
                initialized.update(name[1:-1] for name, bits in names.items() if any(v & (4 | 8) for v in bits))
            for line in loads.read_text().splitlines():
                name, sep, location = line.partition(" source: file:")
                if sep:
                    releases[name.replace(".", "/")] = Path(unquote(urlparse("file:" + location).path)).resolve()
            profiles[label] = {"entry": action, "settings": {"processors": 2, "environment": "empty", "directory": "/", **options},
                               "observations": rows, "instrumentedMatched": True, "fieldSites": len(counts),
                               "matchedExpectation": check_observations(number, side, action, options, rows),
                               "recordedFieldEvents": sum(counts.values())}
        inventory = inspect_classes(cp, releases, initialized, compiled, tool, work)
    paths = {"fieldEvents": result / "field-events.json.gz", "inventory": result / "static-inventory.json.gz"}
    document(paths["fieldEvents"], watches)
    document(paths["inventory"], inventory)
    document(result / "profiles.json", {"schema": "domain-startup-profile/v1", "example": number, "provenance": provenance,
             "profiles": profiles, "selectedClasses": len(inventory["selected"]), "wallSeconds": round(time.monotonic()-begin, 3),
             "tables": {k: {"file": p.name, "sha256": runtime_maven.sha256_of(p)} for k, p in paths.items()}})
    print(number, side, len(profiles), "paired JVM profiles,", len(inventory["selected"]), "selected classes", flush=True)
    failed = [name for name, row in profiles.items() if not row["matchedExpectation"]]
    if failed:
        raise ValueError("unexpected public observations, retained for review: " + ", ".join(failed))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("example", choices=PROFILES)
    ap.add_argument("--side", choices=("parent", "fix", "both"), default="both")
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    for side in ("parent", "fix") if a.side == "both" else (a.side,):
        profile(a.example, side, a.output)
