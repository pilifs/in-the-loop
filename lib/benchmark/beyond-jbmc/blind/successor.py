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
from scaffold_first import HERE, JDK, OUTPUT, compile_java, compressed, digest, javaenv, observe, read, save, scratch

OUT = OUTPUT / "successor"
AREA = Path.home() / ".cache/in-the-loop/beyond-jbmc/scaffold-first-successor-panel"
REFS = HERE / "successor"
SLOTS = [f"{n:02}" for n in range(1, 17)]


def draw():
    lock = read(OUT / "selection.json")
    for name, field in (("portable-population", "populationSha256"), ("screening", "screeningSha256"), ("sealed", "sealedSha256")):
        data = gzip.decompress((OUT / "draw" / (name + ".json.gz")).read_bytes())
        if hashlib.sha256(data).hexdigest() != lock[field]:
            raise ValueError("committed draw differs from the selection")
    return json.loads(data)["pairs"]


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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("deployments",))
    ap.add_argument("slots", nargs="*", choices=SLOTS)
    args = ap.parse_args()
    deployments(args.slots or SLOTS)


if __name__ == "__main__":
    main()
