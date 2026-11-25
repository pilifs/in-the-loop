"""Reconstitute the signed deployments and register original JVM observations of the second draw."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import zipfile

import packets
from scaffold_first import HERE, JDK, JVM_FLAGS, OUTPUT, compile_java, compressed, digest, javaenv, observe, read, save, scratch

OUT = OUTPUT / "successor"
AREA = Path.home() / ".cache/in-the-loop/beyond-jbmc/scaffold-first-successor-panel"
REFS = HERE / "successor"
SLOTS = [f"{n:02}" for n in range(1, 17)]


def draw():
    lock = read(OUT / "selection.json")
    documents = {}
    for name, field in (("portable-population", "populationSha256"), ("screening", "screeningSha256"), ("sealed", "sealedSha256")):
        data = gzip.decompress((OUT / "draw" / (name + ".json.gz")).read_bytes())
        if hashlib.sha256(data).hexdigest() != lock[field]:
            raise ValueError("committed draw differs from the selection")
        documents[name] = json.loads(data)
    sealed = documents["sealed"]
    if (sealed["populationSha256"] != lock["populationSha256"] or sealed["screeningSha256"] != lock["screeningSha256"]
            or hashlib.sha256(bytes.fromhex(sealed["seed"])).hexdigest() != lock["seedSha256"]
            or sealed["selectionProgramSha256"] != lock["selectionProgramSha256"]):
        raise ValueError("sealed selection does not bind the original seed, program or indexes")
    return sealed["pairs"]


def deployments(slots):
    selected = draw()
    population = read(AREA / "acquisition-population.json")
    with scratch(prefix="successor-deployments-") as temporary:
        for slot in slots:
            row = selected[int(slot) - 1]
            graphs = {}
            for index, side in enumerate(("old", "new")):
                suite = row["suites"][index]
                release = population["releases"][suite]
                if release["signedSha256"] != read(OUT / "selection.json")["signedIndex"][suite]:
                    raise ValueError("release index differs from the frozen draw")
                index_area = AREA if (AREA / suite / "InRelease").is_file() else packets.AREA
                graphs[side] = packets.graph(row, side, population["releases"], Path(temporary) / slot / side,
                                             area=AREA, index_area=index_area, available_only=True)
            save(OUT / "deployments" / (slot + ".json.gz"), graphs)
            print(slot, [(len(g["classpath"]), len(g["unavailablePackages"])) for g in graphs.values()], flush=True)


def packet(slot, dest):
    """Write the exact previously recorded classpaths, even if more packages are in the archive now."""
    graphs = compressed(OUT / "deployments" / (slot + ".json.gz"))
    inputs = {}
    for side, graph in graphs.items():
        files = graph["classpath"]
        directory = dest / side
        directory.mkdir(parents=True)
        by_package = {}
        for i, row in enumerate(files):
            if row["path"] != f"{side}/{i:03}.jar":
                raise ValueError("invalid provider position")
            by_package.setdefault(row["package"], []).append(row)
        for name, rows in by_package.items():
            wanted = graph["packages"][name]["sha256"]
            archive = AREA / (wanted + ".deb")
            if digest(archive) != wanted:
                raise ValueError("released package bytes differ")
            jars, _ = packets.archive_jars(archive)
            for row in rows:
                h, data, _ = jars[row["source"]]
                if h != row["sha256"]:
                    raise ValueError("original JAR bytes differ")
                (dest / row["path"]).write_bytes(data)
        inputs[side] = [{k: r[k] for k in ("path", "sha256")} for r in files]
    save(dest / "inputs.json", inputs)
    return inputs


def source_evidence(row, spec):
    evidence = []
    for item in spec["basis"]:
        archive_side = "before" if item["side"] == "old" else "after"
        source = row[archive_side]["sourceEntry"]
        matches = []
        for h, size, filename in source["files"]:
            if ".orig." not in filename:
                continue
            archive = AREA / (h + ".orig")
            if digest(archive) != h or archive.stat().st_size != int(size):
                raise ValueError("different released source archive")
            with tarfile.open(archive, "r|*") as tar:
                for member in tar:
                    nested = item.get("nestedArchiveSuffix")
                    if not member.isfile() or member.size > 2 ** 21 or not member.name.endswith(nested or item["memberSuffix"]):
                        continue
                    data = tar.extractfile(member).read()
                    members = [(member.name, data)]
                    if nested:
                        with zipfile.ZipFile(io.BytesIO(data)) as z:
                            members = [(member.name + "!/" + e.filename, z.read(e)) for e in z.infolist()
                                       if e.filename.endswith(item["memberSuffix"]) and e.file_size <= 2 ** 21]
                    for name, content in members:
                        if item["text"].encode() in content:
                            matches.append({**item, "member": name, "memberSha256": hashlib.sha256(content).hexdigest(),
                                            "published": source["directory"] + "/" + filename, "archiveSha256": h})
        if len(matches) != 1:
            raise ValueError(f'{item["side"]} {item["memberSuffix"]} has {len(matches)} matching source members')
        evidence.extend(matches)
    return evidence


def contract(spec):
    lo, hi = spec["bounds"]
    e = spec["expected"]
    return f"""    public static boolean admitted(int n) {{ return n >= {lo} && n <= {hi}; }}
    public static long oldExpected(int n) {{ return {e["beforeExpression"]}; }}
    public static long newExpected(int n) {{ return {e["afterExpression"]}; }}
    public static long controlExpected(int n) {{ return {e["controlExpression"]}; }}
"""


def pair_source(spec):
    return "public final class ReferencePair {\n" + contract(spec) + """
    public static boolean primary(int n) {
        if (!admitted(n)) return true;
        try {
            long old = before.ReferenceAPI.primary(n), current = ReferenceAPI.primary(n);
            return old == oldExpected(n) && current == newExpected(n);
        } catch (Exception unexpected) { throw new IllegalStateException(unexpected); }
    }
    public static boolean control(int n) {
        if (!admitted(n)) return true;
        try {
            long old = before.ReferenceAPI.control(n), current = ReferenceAPI.control(n);
            return old == controlExpected(n) && current == controlExpected(n);
        } catch (Exception unexpected) { throw new IllegalStateException(unexpected); }
    }
    public static boolean inverse(int n) { return !admitted(n) || !primary(n); }
}
"""


def expected_rows(spec, work):
    src = work / "Expected.java"
    src.write_text("public class Expected {\n" + contract(spec) + """
    public static void main(String[] args) {
        for (String word : args) {
            int n = Integer.parseInt(word);
            if (!admitted(n)) throw new AssertionError("sample outside declaration");
            System.out.println(n + " " + oldExpected(n) + " " + newExpected(n) + " " + controlExpected(n));
        }
    }
}
""")
    classes = work / "oracle"
    compile_java([src], classes, [], javaenv())
    text = subprocess.check_output([JDK / "bin/java", *JVM_FLAGS, "-cp", classes, "Expected", *map(str, spec["seeds"])], text=True)
    return [list(map(int, line.split())) for line in text.splitlines()]


def scaffold(slot, row, work, launcher):
    folder = REFS / slot
    spec = read(folder / "reference.json")
    src = folder / "ReferenceAPI.java"
    work.mkdir()
    cp = packet(slot, work / "packet")
    receipt = {"slot": slot, "artifact": row["artifact"], "versions": row["versions"], "project": row["project"],
               "stratum": row["stratum"], "question": digest(folder / "reference.json"), "callerSource": digest(src),
               "deployment": digest(OUT / "deployments" / (slot + ".json.gz")), "jdkModulesSha256": digest(JDK / "lib/modules"),
               "jvmFlags": JVM_FLAGS, "seeds": spec["seeds"], "sides": {}, "solverStarted": False}
    pair = folder / "ReferencePair.java"
    pair.write_text(pair_source(spec))
    receipt["pairSource"] = digest(pair)
    receipt["expectedRows"] = rows = expected_rows(spec, work)
    receipt["basis"] = source_evidence(row, spec)
    jars = {s: [work / "packet" / r["path"] for r in cp[s]] for s in ("old", "new")}
    classes = work / "caller"
    classes.mkdir()
    javac = subprocess.run([JDK / "bin/javac", "-source", "8", "-target", "8", "-Xlint:-options", "-parameters", "-g",
                            "-proc:none", "-cp", os.pathsep.join(map(str, jars["old"])), "-d", classes, src],
                           env=javaenv(), text=True, capture_output=True, timeout=45)
    if javac.returncode:
        receipt["firstScaffoldStop"] = "compiling the caller against the original older release"
        receipt["diagnostic"] = javac.stderr.replace(str(folder), "$REFERENCE").replace(str(work), "$WORK")[:2200]
    else:
        receipt["callerClasses"] = {p.relative_to(classes).as_posix(): digest(p) for p in sorted(classes.rglob("*.class"))}
        receipt["firstScaffoldStop"] = None
        for index, side in enumerate(("old", "new")):
            receipt["sides"][side] = trials = {}
            for mode in ("direct", "record"):
                got = observe(work / (side + "-" + mode), launcher, classes, jars[side], mode, spec["seeds"])
                trials[mode] = got
                wanted = [[r[0], r[index+1], r[3]] for r in rows]
                stop = None
                if got["exit"] != 0:
                    stop = "original JVM startup or public invocation"
                    got["failure"] = got["failure"].replace(str(work), "$WORK")
                elif got["rows"] != wanted:
                    stop = "original observations disagree with the source-based expected result"
                if stop and receipt["firstScaffoldStop"] is None:
                    receipt["firstScaffoldStop"] = f"{side} {mode}: {stop}"
    dest = OUT / "scaffolds" / (slot + ".json.gz")
    if dest.is_file():
        earlier = compressed(dest)
        if earlier.get("firstScaffoldStop"):
            # Keep the first real diagnostic when a signed provider or a corrected caller resolves it.
            receipt["earlierStops"] = list(earlier.get("earlierStops", []))
            record = {k: earlier[k] for k in ("firstScaffoldStop", "deployment", "callerSource", "question")}
            record["diagnostic"] = earlier.get("diagnostic") or {s: {m: (q.get("failure") or q["rows"]) for m,q in v.items()} for s,v in earlier["sides"].items()}
            if record not in receipt["earlierStops"]:
                receipt["earlierStops"].append(record)
        elif earlier.get("earlierStops"):
            receipt["earlierStops"] = earlier["earlierStops"]
    save(dest, receipt)
    print(slot, receipt["firstScaffoldStop"] or "registered on both original releases", flush=True)


def alternative_graphs(slot, work, repos):
    record = compressed(OUT / "alternative" / (slot + ".json.gz"))
    base = OUT / "scaffolds" / (slot + ".json.gz")
    # A later complete distribution launch can replace the preliminary scaffold. Match the
    # shared question and consumer independently of that launch's dependency receipt.
    src = REFS / slot / "ReferenceAPI.java"
    if (record["question"] != digest(REFS / slot / "reference.json") or record["consumer"] != digest(src)
            or record["jdkModulesSha256"] != digest(JDK / "lib/modules")
            or record["expectedRows"] != compressed(base)["expectedRows"] or record["jvmFlags"] != JVM_FLAGS):
        raise ValueError("alternative launch has a different question, runtime or caller")
    inputs = packet(slot, work / "distribution")
    cp = {}
    for side in ("old", "new"):
        cp[side] = []
        for row in record["sides"][side]["orderedClasspath"]:
            if "maven" in row:
                group, name, version = row["maven"].split(":")
                rel = Path(group.replace(".", "/")) / name / version / f"{name}-{version}.jar"
                file = next((r / rel for r in repos if (r / rel).is_file() and digest(r / rel) == row["sha256"]), None)
                if file is None:
                    raise ValueError("supply the pinned Maven artifact with --maven-repo: " + row["maven"])
            else:
                provider = next((p for p in inputs[side] if p["sha256"] == row["sha256"]), None)
                if provider is None:
                    raise ValueError("recorded release JAR absent from the package")
                file = work / "distribution" / provider["path"]
            cp[side].append(file)
    return record, cp


def check_alternative(slot, work, launcher, repos):
    record, cp = alternative_graphs(slot, work, repos)
    src = REFS / slot / "ReferenceAPI.java"
    spec = read(REFS / slot / "reference.json")
    classes = work / "caller"
    compile_java([src], classes, cp["old"], javaenv())
    if digest(classes / "ReferenceAPI.class") != record["callerSha256"]:
        raise ValueError("compiled consumer differs")
    for side in ("old", "new"):
        for mode in ("direct", "record"):
            actual = observe(work / (side + mode), launcher, classes, cp[side], mode, spec["seeds"])
            if actual != record["sides"][side][mode]:
                raise ValueError(f"{slot} {side} {mode}: different original JVM observations or loader bindings")
    print(slot, "all four alternative launches reproduced", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("deployments", "scaffold", "check-alternative"))
    ap.add_argument("slots", nargs="*", metavar="SLOT")
    ap.add_argument("--maven-repo", type=Path, action="append", default=[], help="local Maven repository used for alternative launches")
    args = ap.parse_args()
    slots = args.slots or (["03", "08", "16"] if args.action == "check-alternative" else SLOTS)
    if any(s not in SLOTS for s in slots):
        ap.error("select slots 01 through 16")
    if args.action == "deployments":
        deployments(slots)
        return
    selected = draw()
    with scratch(prefix="successor-originals-") as temp:
        work = Path(temp)
        launcher = work / "launcher"
        launcher.mkdir()
        subprocess.run([JDK / "bin/javac", "-proc:none", "-d", launcher, HERE / "LoaderObservations.java"], check=True)
        for slot in slots:
            if args.action == "check-alternative":
                check_alternative(slot, work / slot, launcher, args.maven_repo)
            else:
                scaffold(slot, selected[int(slot)-1], work / slot, launcher)


if __name__ == "__main__":
    main()
