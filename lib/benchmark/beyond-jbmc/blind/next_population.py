"""Prepare a disjoint prospective population without revealing candidate identities to the development session."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys

import scaffold_first
import seal_panel

SUITES = ("bionic", "focal", "jammy", "noble", "resolute")
EXPOSURE_REVISION = "6a07afe4a9dc54d8e6f208329c2b1e29f2badf45"


def prior_text():
    root = scaffold_first.HERE.parents[3]
    listing = subprocess.check_output(["git", "ls-tree", "-rlz", EXPOSURE_REVISION,
        "--", "examples", "llm-dlc/loops", "verification/findings.md", "lib/benchmark"], cwd=root)
    wanted = []
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        header, path = entry.split(b"\t", 1)
        _, kind, oid, length = header.split()
        p = Path(os.fsdecode(path))
        if kind != b"blob":
            continue
        if (p.match("examples/*/*.json") or p.match("llm-dlc/loops/*.md") or str(p) == "verification/findings.md"
            or (p.is_relative_to("lib/benchmark") and not p.is_relative_to("lib/benchmark/beyond-jbmc")
                and p.suffix in (".json", ".md", ".py") and int(length) <= 7_000_000)):
            wanted.append(oid)
    bulk = subprocess.check_output(["git", "cat-file", "--batch"], input=b"\n".join(wanted) + b"\n", cwd=root)
    contents = []
    at = 0
    for oid in wanted:
        end = bulk.index(b"\n", at)
        actual, kind, length = bulk[at:end].split()
        if actual != oid or kind != b"blob":
            raise ValueError("exposure tree changed")
        at = end + 1
        contents.append(bulk[at:at + int(length)].decode("utf-8", "replace").lower())
        at += int(length) + 1
    return "\n".join(contents)


def private_prepare(area):
    selected = scaffold_first.read(scaffold_first.HERE / "draw/roster.json")["pairs"]
    prior_projects, prior_sources = {r["project"] for r in selected}, {r["source"] for r in selected}
    base = Path.home() / ".cache/in-the-loop/beyond-jbmc/panel"
    past = scaffold_first.read(base / "population.json")
    if seal_panel.sha((base / "population.json").read_bytes()) != scaffold_first.compressed(
            scaffold_first.HERE / "draw/sealed.json.gz")["populationSha256"]:
        raise ValueError("prior signed index record changed")
    releases = {}
    for suite in SUITES:
        if suite in past["releases"]:
            release = past["releases"][suite]
            if any(scaffold_first.digest(Path(r["path"])) != r["sha256"] for r in release["indexes"].values()):
                raise ValueError("changed historical index")
        else:
            release = seal_panel.index(area, suite)
        releases[suite] = release
    exposure = prior_text()
    # Use the original eligibility and screening implementation with the prospective dates and prior exposure fixed above.
    seal_panel.SUITES = SUITES
    seal_panel.index = lambda _area, suite: releases[suite]
    seal_panel.exposure_text = lambda: exposure
    seal_panel.pool(area)
    doc = scaffold_first.read(area / "population.json")
    original_size = len(doc["eligible"])
    doc["eligible"] = [r for r in doc["eligible"] if r["project"] not in prior_projects and r["source"] not in prior_sources]
    # The private copy has paths for acquisition. This portable digest binds the same signed bytes on another host.
    portable = {**doc, "releases": {s: {**m, "indexes": {k: v["sha256"] for k, v in m["indexes"].items()}}
                                      for s, m in releases.items()}}
    seal_panel.save(area / "acquisition-population.json", seal_panel.encode(doc))
    seal_panel.save(area / "population.json", seal_panel.encode(portable))
    seal_panel.save(area / "portable-population.json", seal_panel.encode(portable))
    seed = area / "seed"
    if not seed.exists():
        with seed.open("xb") as f:
            f.write(os.urandom(32))
    if len(seed.read_bytes()) != 32:
        raise ValueError("incomplete seed")
    for file in base.iterdir():
        if file.suffix in (".deb", ".orig") and len(file.stem) == 64 and not (area / file.name).exists():
            (area / file.name).symlink_to(file)
    return {"stage": "population and seed committed before screening", "exposureRevision": EXPOSURE_REVISION,
            "priorSelectionSha256": scaffold_first.digest(scaffold_first.HERE / "draw/roster.json"),
            "policySha256": scaffold_first.digest(scaffold_first.DEST / "successor-freeze.json"),
            "selectionProgramSha256": scaffold_first.digest(Path(seal_panel.__file__)),
            "populationSha256": scaffold_first.digest(area / "portable-population.json"), "seedSha256": scaffold_first.digest(seed),
            "signedIndex": {s: m["signedSha256"] for s, m in releases.items()},
            "removedPriorPairs": original_size - len(doc["eligible"]),
            "strata": {s: {"pairs": sum(r["stratum"] == s for r in doc["eligible"]),
                          "projects": len({r["project"] for r in doc["eligible"] if r["stratum"] == s})} for s in seal_panel.STRATA}}


class MissingArchive(Exception):
    pass


def private_screen(area, limit, offline):
    commitment = scaffold_first.read(area / "readiness.json")
    if (commitment["policySha256"] != scaffold_first.digest(scaffold_first.DEST / "successor-freeze.json")
            or commitment["seedSha256"] != scaffold_first.digest(area / "seed")
            or commitment["populationSha256"] != scaffold_first.digest(area / "portable-population.json")):
        raise ValueError("prospective commitment changed")
    # All package-specific diagnostics go to the private log. Keep temporary results, exclusions and the original seed on retry.
    blocked = None
    if offline:
        online_fetch = seal_panel.fetch
        def local_fetch(root, relative, dest, expected=None):
            if not dest.exists():
                seal_panel.save(area / "needed-archive.json", seal_panel.encode({"path": relative, "sha256": expected}))
                raise MissingArchive("published binary package" if relative.endswith(".deb") else "published source archive")
            online_fetch(root, relative, dest, expected)
        seal_panel.fetch = local_fetch
    try:
        sealed = seal_panel.draw(area, limit)
    except MissingArchive as error:
        blocked, sealed = str(error), None
    screened = scaffold_first.read(area / "screening.json") if (area / "screening.json").exists() else {}
    return {**commitment, "stage": "sealed" if sealed else "screening", "sealedSha256": sealed,
            "firstScaffoldStop": ("signed " + blocked + " unavailable locally") if blocked else None,
            "screened": len(screened), "excludedByStatus": dict(Counter(str((r or {}).get("status", "no common API"))
                       for r in screened.values() if not r or r.get("excluded"))),
            "screeningSha256": scaffold_first.digest(area / "screening.json") if screened else None}


def private_inventory(area):
    state = scaffold_first.read(area / "screen-status.json")
    population = scaffold_first.read(area / "portable-population.json")
    screened = scaffold_first.read(area / "screening.json")
    seed = (area / "seed").read_bytes()
    records = []
    for pair in population["eligible"]:
        key = seal_panel.sha(seed + seal_panel.encode(("record", pair["artifact"], pair["versions"], pair["suites"])))
        if key not in screened:
            continue
        evidence = screened[key]
        row = {"candidate": key, "stratum": pair["stratum"], "publicEntryRegistered": False,
               "unchangedControlRegistered": False, "originalReleasesExecuted": False, "solverStarted": False}
        if evidence and not evidence.get("excluded"):
            row["releases"] = {}
            for endpoint, label in (("before", "old"), ("after", "new")):
                source = pair[endpoint]
                package = area / (source["SHA256"] + ".deb")
                if scaffold_first.digest(package) != source["SHA256"]:
                    raise ValueError("different screened package")
                jars, _ = seal_panel.inspect_deb(package)
                h, api = jars[evidence[label + "Jar"]]
                if h != evidence[label + "Sha256"] or evidence["eligibilityExample"] not in api:
                    raise ValueError("signed release does not contain the selected original public entry")
                archives = {}
                for checksum, _, name in source["sourceEntry"]["files"]:
                    if ".orig" in name:
                        f = area / (checksum + ".orig")
                        archives[name] = {"sha256": checksum, "available": f.is_file() and scaffold_first.digest(f) == checksum}
                row["releases"][label] = {"packageSha256": source["SHA256"], "jarSha256": h, "sourceArchives": archives}
            row["firstScaffoldStop"] = "The release JARs qualified. The independent public question, caller and both-release startup still need registration."
        else:
            row["firstScaffoldStop"] = "binary eligibility failed before reference investigation"
        records.append(row)
    if len(records) != len(screened):
        raise ValueError("screening journal and portable population do not cover the same submissions")
    target = area / "candidate-intake.json"
    seal_panel.save(target, seal_panel.encode(records))
    complete = [r for r in records if "releases" in r]
    return {**state, "eligiblePairs": len(population["eligible"]), "eligibleProjects": len({r["project"] for r in population["eligible"]}),
            "binaryQualified": len(complete), "reverifiedReleasedJars": 2 * len(complete),
            "bothSourceArchivesPresent": sum(all(s["sourceArchives"] and all(a["available"] for a in s["sourceArchives"].values())
                                                for s in r["releases"].values()) for r in complete),
            "intakeSha256": scaffold_first.digest(target), "selectionComplete": bool(state["sealedSha256"]), "scoredPairs": 0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("prepare", "screen", "inventory"))
    ap.add_argument("--private", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=4)
    ap.add_argument("--offline", action="store_true", help="screen using already acquired and verified bytes only")
    ap.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    area = args.private.resolve()
    area.mkdir(mode=0o700, exist_ok=True, parents=True)
    filename = {"prepare": "readiness.json", "screen": "screen-status.json", "inventory": "intake-status.json"}[args.action]
    if args.inside:
        if args.action == "inventory":
            info = private_inventory(area)
        elif args.action == "prepare":
            info = private_prepare(area)
        else:
            info = private_screen(area, args.limit, args.offline)
        scaffold_first.save(area / filename, info)
        return
    with (area / ("private-" + args.action + ".log")).open("ab") as log:
        command = [sys.executable, "-B", __file__, args.action, "--private", str(area), "--limit", str(args.limit), "--inside"]
        if args.offline:
            command.append("--offline")
        code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT).returncode
    if code:
        sys.exit("private acquisition or eligibility check stopped; identities and diagnostics retained privately")
    print(json.dumps(scaffold_first.read(area / filename), sort_keys=True))


if __name__ == "__main__":
    main()
