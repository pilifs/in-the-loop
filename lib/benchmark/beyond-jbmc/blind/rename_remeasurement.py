"""Repeat the frozen automatic portfolio with the successor checker, retaining the original draw and first pass."""
import argparse
import os
from pathlib import Path
import subprocess
import zipfile

from calibration import input_pair
from packets import BASE
from run_operator import CODE, JDK, ROOT, launch, sha
from scaffold_first import DEST, HERE, OUTPUT, compressed, encoded, read, registered, save, scratch


def calibration_packet(work, first):
    packet = input_pair(work)
    # ZIP dates and Unix modes are the only non-source inputs to the original four-class archives.
    for side, second in (("old", 38), ("new", 40)):
        file = packet / side / "000.jar"
        with zipfile.ZipFile(file) as archive:
            members = [(entry, archive.read(entry)) for entry in archive.infolist()]
        with zipfile.ZipFile(file, "w", zipfile.ZIP_DEFLATED) as archive:
            for info, data in members:
                info.date_time = (2026, 11, 24, 8, 39, second)
                info.external_attr = 0o100664 << 16
                archive.writestr(info, data)
        if sha(file) != first["inputs"][side][0]["sha256"]:
            raise ValueError("calibration deployment differs from the original bytes")
    (packet / "inputs.json").write_bytes(encoded(first["inputs"]))
    return packet


def observation_pair(pair):
    return [(r["namedEntryReached"], r["fields"]) for r in pair]


def compare(first, current, warm):
    if first["inputs"] != current["inputs"] or first["policy"] != current["policy"]:
        raise ValueError("operator scope changed")
    old = {r["candidate"]["id"]: r for r in first["runs"]}
    records = []
    for result in current["runs"]:
        name = result["candidate"]["id"]
        prior = old.pop(name)
        if prior.get("callerSha256") != result.get("callerSha256") or prior.get("source") != result.get("source"):
            raise ValueError("generated caller differs for " + name)
        samples = [observation_pair(p) for p in result["physical"]]
        same_physical = samples == [observation_pair(p) for p in prior["physical"]]
        differences = [i for i, ((old_hit, left), (new_hit, right)) in enumerate(samples)
                       if old_hit and new_hit and left[0] == right[0] and left[1:3] != right[1:3]]
        verdict = result.get("verdict")
        disagreement = ((verdict == "verified" and bool(differences)) or
                        (verdict == "violation" and result.get("originalReplayChanged") is False))
        records.append({"entry": name, "callerSha256": result.get("callerSha256"),
                        "oldStatus": prior["status"], "newStatus": result["status"], "oldVerdict": prior.get("verdict"),
                        "newVerdict": verdict, "oldWitnessReproduced": prior.get("originalReplayChanged"),
                        "newWitnessReproduced": result.get("originalReplayChanged"),
                        "sampleDifferences": differences, "samePhysicalTrials": same_physical,
                        "jvmDisagreement": disagreement, "problem": result.get("problem")})
    expected_warm = [r["entry"] for r in records if r["newStatus"] == "measured"]
    if old or [w["candidate"] for w in warm] != expected_warm or not all(w["sameVerdict"] for w in warm):
        raise ValueError("incomplete portfolio or cold/warm discrepancy")
    return records


def locked_candidates(work, pair, checker, missing):
    selected = work / "locked.json"
    selected.write_bytes(encoded(missing))
    raw, temp = work / "locked-outputs", work / "locked-scratch"
    raw.mkdir()
    temp.mkdir()
    guest = "/tool/lib/benchmark/beyond-jbmc/blind/repeat_locked.py"
    cmd = ["bwrap", "--die-with-parent", "--new-session", "--unshare-user", "--unshare-pid", "--unshare-net",
           "--unshare-ipc", "--unshare-uts", "--clearenv", "--ro-bind", "/usr", "/usr",
           "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
           "--dev", "/dev", "--proc", "/proc", "--remount-ro", "/proc", "--tmpfs", "/tmp", "--dir", "/etc",
           "--ro-bind", "/etc/ld.so.cache", "/etc/ld.so.cache", "--ro-bind", str(JDK), "/opt/jdk",
           "--ro-bind", str(checker), "/opt/checker", "--ro-bind", str(pair), "/inputs",
           "--ro-bind", str(selected), "/locked.json", "--bind", str(raw), "/output", "--bind", str(temp), "/scratch",
           "--setenv", "PATH", "/opt/jdk/bin:/usr/bin:/bin", "--setenv", "HOME", "/scratch",
           "--setenv", "TMPDIR", "/scratch", "--setenv", "LANG", "C.UTF-8", "--setenv", "TZ", "UTC", "--chdir", "/scratch"]
    for file in CODE:
        cmd += ["--ro-bind", str(ROOT / file), "/tool/" + file]
    cmd += ["--ro-bind", str(HERE / "repeat_locked.py"), guest, "/usr/bin/python3", "-B", guest]
    subprocess.run(cmd, check=True)
    return read(raw / "locked-report.json")


def run(slot, checker, policy):
    output = DEST / "remeasured" / slot
    output.mkdir(parents=True, exist_ok=True)
    with scratch(prefix="successor-portfolio-") as tmp:
        work = Path(tmp)
        if slot == "calibration":
            first_path = OUTPUT / "calibration/artifact-only.json"
            first = read(first_path)
            pair = calibration_packet(work, first)
        else:
            scaffold = compressed(DEST / "scaffolds" / (slot + ".json.gz"))
            if scaffold["firstScaffoldStop"]:
                raise ValueError("original reference scaffolding incomplete")
            locked, _, _, _, _ = registered(slot)
            first_path = OUTPUT / "blind" / slot / "automatic/report.json.gz"
            first = compressed(first_path)
            if first["packetSha256"] != locked["packetSha256"]:
                raise ValueError("different frozen deployment")
            pair = BASE / slot / "packet"
        current = launch(pair, work / "namespace", checker, policy)
        raw = work / "namespace/output/first"
        warm = read(raw / "warm.json")
        earlier = [r["id"] for r in first["selected"]]
        selected = [r["id"] for r in current["selected"]]
        missing = [r for r in first["selected"] if r["id"] not in selected]
        supplementary = locked_candidates(work, pair, checker, missing) if missing else {"runs": [], "warm": []}
        measured = {r["candidate"]["id"]: r for r in current["runs"] + supplementary["runs"]}
        warm_by_name = {r["candidate"]: r for r in warm + supplementary["warm"]}
        locked_warm = [warm_by_name[n] for n in earlier if n in warm_by_name]
        comparisons = compare(first, {**current, "runs": [measured[n] for n in earlier]}, locked_warm)
        archive = output / "executions.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for path in sorted(raw.rglob("*")):
                if path.is_file():
                    z.write(path, path.relative_to(raw))
            for path in sorted((work / "locked-outputs").rglob("*")):
                if path.is_file():
                    z.write(path, "locked/" + str(path.relative_to(work / "locked-outputs")))
        save(output / "comparison.json.gz",
             {"slot": slot, "phase": "post-disclosure repeat of the frozen artifact-only operator",
              "firstPassSha256": sha(first_path), "originalCheckerSha256": first["toolSha256"],
              "checkerSha256": current["toolSha256"], "originalPacket": first["inputs"],
              "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"), "job": os.environ.get("VERIFY_JOB_ID"),
              "selection": {"first": earlier, "successor": selected, "separateLockedReplay": [r["id"] for r in missing],
                            "oldImpactExit": first["impactExit"], "newImpactExit": current["impactExit"]},
              "comparisons": comparisons, "warm": locked_warm, "archiveSha256": sha(archive)})
        print(slot, len(comparisons), "locked candidates,", len(warm), "cold/warm comparisons", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slots", nargs="+")
    args = parser.parse_args()
    freeze = read(HERE.parent / "freeze.json")
    checker = Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")).resolve()
    if any(sha(ROOT / name) != freeze["operatorFiles"][name] for name in CODE) or sha(JDK / "bin/java") != freeze["jdkJavaSha256"]:
        raise ValueError("operator or JDK differs from the freeze")
    policy = {**freeze, "checkerSha256": sha(checker)}
    for slot in args.slots:
        run(slot, checker, policy)
