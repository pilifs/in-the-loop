"""Give the resource-workflow generator neutral JARs only; qualify its preregistered public calls separately."""
import argparse
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from packets import BASE
from scaffold_first import DEST, HERE, JDK, digest, read, save, scratch
from history import ROOT

TARGETS = ROOT / "examples/tools/targets"
OUT = DEST / "resource-discovery"


def tool_files():
    pending = ["resource_workflows"]
    modules = set()
    while pending:
        name = pending.pop()
        if name in modules:
            continue
        modules.add(name)
        for node in ast.walk(ast.parse((TARGETS / (name + ".py")).read_bytes())):
            if isinstance(node, ast.ImportFrom) and node.module == "targets":
                pending.extend(alias.name for alias in node.names if (TARGETS / (alias.name + ".py")).is_file())
    return [*(TARGETS / (name + ".py") for name in sorted(modules)), TARGETS / "java/ResourceObserver.java.template"]


def manifests(slot, work, *, neutral):
    packet = BASE / slot / "packet"
    spec = read(packet / "inputs.json")
    roster = next(p for p in read(HERE / "draw/roster.json")["pairs"] if p["slot"] == slot)
    for index, (side, rows) in enumerate(spec.items()):
        if rows[0]["sha256"] != roster[side] or any(
                r != {"path": f"{side}/{i:03d}.jar", "sha256": digest(packet / r["path"])} for i, r in enumerate(rows)):
            raise ValueError("different ordered release graph")
        base = Path("/inputs") if neutral else packet
        save(work / (side + ".json"), {"commit": roster["versions"][0 if side == "old" else 1],
             "sourceSha256": None, "scope": "pinned original binary distribution",
             "classpath": [{"file": str(base / r["path"]), "sha256": r["sha256"]} for r in rows]})
    return packet


def discover(slot):
    with scratch(prefix="resource-operator-") as tmp:
        work = Path(tmp)
        packet = manifests(slot, work, neutral=True)
        out, temp = work / "out", work / "temp"
        out.mkdir()
        temp.mkdir()
        cmd = ["bwrap", "--die-with-parent", "--new-session", "--unshare-user", "--unshare-pid", "--unshare-net",
               "--unshare-ipc", "--unshare-uts", "--clearenv", "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
               "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64", "--dev", "/dev", "--proc", "/proc",
               "--remount-ro", "/proc", "--tmpfs", "/tmp", "--dir", "/etc", "--ro-bind", "/etc/ld.so.cache", "/etc/ld.so.cache",
               "--ro-bind", str(packet), "/inputs", "--ro-bind", str(JDK), "/opt/jdk", "--bind", str(temp), "/scratch",
               "--bind", str(out), "/output", "--setenv", "PATH", "/opt/jdk/bin:/usr/bin:/bin",
               "--setenv", "TMPDIR", "/scratch", "--setenv", "HOME", "/scratch", "--setenv", "LANG", "C.UTF-8",
               "--setenv", "TZ", "UTC", "--chdir", "/scratch"]
        for side in ("old", "new"):
            # The discovery process receives only the ordered paths and digests, without the package label or registration.
            manifest = work / (side + ".json")
            save(manifest, {"classpath": read(manifest)["classpath"]})
            cmd += ["--ro-bind", str(manifest), "/" + side + ".json"]
        files = tool_files()
        for file in files:
            cmd += ["--ro-bind", str(file), "/tool/targets/" + str(file.relative_to(TARGETS))]
        cmd += ["/usr/bin/python3", "-I", "-B", "-c",
                "import sys; sys.path.insert(0,'/tool'); from targets.resource_workflows import main; sys.exit(main(sys.argv[1:]))",
                "--before", "/old.json", "--after", "/new.json", "--jdk", "/opt/jdk", "--output", "/output/result"]
        subprocess.run(cmd, check=True)
        result = read(out / "result/discovery.json")
        result.update(operatorFiles={str(f.relative_to(TARGETS)): digest(f) for f in files},
                      inputPacketSha256=digest(packet / "inputs.json"), access="ordered JARs, JDK, generator; isolated network and home")
        save(out / "result/discovery.json", result)
        shutil.copytree(out / "result", OUT / slot)


def solve(slot):
    scope = OUT / slot
    discovery = read(scope / "discovery.json")
    with scratch(prefix="generated-resource-plans-") as tmp:
        work = Path(tmp)
        packet = manifests(slot, work, neutral=False)
        if digest(packet / "inputs.json") != discovery["inputPacketSha256"]:
            raise ValueError("different discovery inputs")
        checker = Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")).resolve()
        for row in discovery["candidates"]:
            case = scope / row["directory"]
            scaffold = read(case / "scaffold.json")
            reg = read(case / "registration.json")
            if scaffold["stage"] != "original JVM controls passed" or reg["stage"] != "registered before populated JVM trials":
                raise ValueError("generated public caller did not qualify")
            workflow = case / "workflows.json"
            if digest(workflow) != reg["workflowsSha256"] or digest(case / "UpgradeProbe.java") != reg["probeSha256"]:
                raise ValueError("registered workflow changed")
            if any(digest(case / (name + ".json")) != h for name, h in reg["scopeSha256"].items()):
                raise ValueError("registered domain changed")
            out = DEST / "resource-plans" / slot / row["directory"]
            out.mkdir(parents=True, exist_ok=True)
            summary = {}
            with zipfile.ZipFile(out / "plans.zip", "w", zipfile.ZIP_DEFLATED) as archive:
                saved = set()
                for mode in ("cold", "warm", "clean", "wrong"):
                    wf = workflow
                    if mode == "wrong":
                        w = read(workflow)
                        for entry in w["workflows"]:
                            entry.update(scope=str(case / entry["scope"]), probe=str(case / entry["probe"]))
                        w["workflows"][0]["intent"] = {"allowedChanges": [{"input": 0, "expectedNew": {"return": "wrong registered result"}}]}
                        wf = work / "wrong-workflows.json"
                        save(wf, w)
                    path = work / (mode + ".json")
                    cmd = [sys.executable, ROOT / "examples/tools/build.py", "--change-plan", "application", "--run",
                           "--before", work / "old.json", "--after", work / "new.json", "--jdk", JDK, "--checker", checker,
                           "--workflows", wf, "--seconds", "360", "--output", path, "--cache", work / ("empty" if mode == "clean" else "cache")]
                    if mode == "warm":
                        cmd += ["--previous", work / "cold.json"]
                    subprocess.run(cmd, check=True, cwd=ROOT)
                    doc = read(path)
                    expected = ["refuted" if mode == "wrong" else "established", "established"]
                    claims = doc["claims"]
                    if [c["status"] for c in claims] != expected:
                        raise ValueError(str([(c["id"], c["status"], c.get("firstOpenDependency"), c.get("reason")) for c in claims]))
                    archive.write(path, path.name)
                    for receipt in sorted((work / "receipts").glob("*.json")):
                        if receipt.name not in saved:
                            archive.write(receipt, "receipts/" + receipt.name)
                            saved.add(receipt.name)
                    summary[mode] = [{"id": c["id"], "status": c["status"], "actions": c["execution"], "inputs": len(c["domain"]),
                                      "witness": c.get("witness"), "receipt": c["receipt"]} for c in claims]
                    print(slot, mode, expected, flush=True)
            save(out / "summary.json", {"job": os.environ.get("VERIFY_JOB_ID"), "source": os.environ.get("VERIFY_SOURCE_COMMIT"),
                 "entry": row["entry"], "registered": digest(case / "registration.json"), "checkerSha256": digest(checker),
                 "archiveSha256": digest(out / "plans.zip"), "runs": summary})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("discover", "solve"))
    p.add_argument("slots", nargs="+")
    args = p.parse_args()
    for slot in args.slots:
        (discover if args.action == "discover" else solve)(slot)
