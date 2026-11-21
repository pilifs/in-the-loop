"""Run the installed first-party CLI against a loopback-only synthetic provider and a separate real case broker."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path

operator = Path(__file__).resolve().parents[2]
workspace = operator.parents[3]
sys.path.insert(0, str(operator))
import control  # noqa: E402
import isolation  # noqa: E402
import probe  # noqa: E402

here = Path(__file__).resolve().parent


def marker():
    return "synthetic-" + secrets.token_hex(20)


def run_role(model, product, root, cli, profile):
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    host_private = root / "private"
    host_private.mkdir()
    masks = {
        k: marker()
        for k in (
            "projectInstructions",
            "homeInstructions",
            "userInstructions",
            "priorTranscript",
            "controlPrivate",
            "curatorReference",
            "otherCase",
            "globalMemory",
            "agentsInstructions",
            "localRules",
            "unlistedMcp",
            "userHook",
            "mcpInternalPath",
            "controlTempPath",
            "homePath",
        )
    }
    masks["actualHostRepository"] = str(workspace)
    masks["actualHostScratch"] = str(root.parent)
    paths = {}
    for cat in ("curatorReference", "priorTranscript", "otherCase"):
        f = host_private / cat
        f.write_text(masks[cat])
        paths[cat] = str(f)
    paths["controlPrivate"] = "/case/work/control-only/withheld.txt"
    # Each tool-side case has its own source release, independent of the client's control-side working directory.
    subject_release = root / "subject-release"
    subject_release.mkdir()
    pair, expected = probe.packet(subject_release)
    (pair / "old/negative-canaries.json").write_text(json.dumps(paths))
    m = json.loads((pair / "pair.json").read_bytes())
    m["old"]["tree_sha256"] = isolation.hashed(isolation.canonical(isolation.tree(pair / "old")))
    (pair / "pair.json").write_bytes(isolation.canonical(m) + b"\n")
    subject = root / "subject"
    isolation.fresh_case(subject, pair, isolation.digest(pair / "pair.json"))
    control_release = root / "control-release"
    control_release.mkdir()
    cpair, _ = probe.packet(control_release)
    cp = root / "controller"
    isolation.fresh_case(cp, cpair, isolation.digest(cpair / "pair.json"))
    work = cp / "work"
    bridge = work / "broker"
    bridge.mkdir()
    shutil.copy2(cli, work / "claude")
    libs = work / "runtime-libs"
    libs.mkdir()
    for name in ("librt.so.1", "libpthread.so.0", "libdl.so.2"):
        source = Path("/usr/lib/x86_64-linux-gnu") / name
        shutil.copy2(source, libs / name)
    (work / "subject_cmd.py").write_bytes((here / "subject_cmd.py").read_bytes())
    (work / "guest.py").write_bytes((here / "fabricated-resume.py").read_bytes())
    code = work / "public/lib/benchmark/external-upgrades/operator"
    code.mkdir(parents=True)
    for name in ("control.py", "isolation.py", "mcp_server.py"):
        shutil.copyfile(operator / name, code / name)
    shutil.copyfile(here / "relay.py", code / "relay.py")
    nonce = marker()
    prompt = json.loads((workspace / "lib/benchmark/external-upgrades/v0.json").read_bytes())[
        "neutralPrompt"
    ]
    (work / "test-settings.json").write_text(
        json.dumps(
            {
                "model": model,
                "profile": profile,
                "nonce": nonce,
                "prompt": prompt,
                "expectedRead": expected,
                "sentinels": masks,
            }
        )
    )
    calls = []
    server = socket.socket(socket.AF_UNIX)
    fd = os.open(bridge, os.O_RDONLY | os.O_DIRECTORY)
    server.bind(f"/proc/self/fd/{fd}/socket")
    os.close(fd)
    server.listen(8)
    server.settimeout(0.1)
    done = threading.Event()

    def serve():
        while not done.is_set():
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                stream = conn.makefile("rwb")
                raw = stream.readline(512 * 1024)
                item = json.loads(raw)
                calls.append(
                    {
                        "name": item.get("name"),
                        "argumentsSha256": hashlib.sha256(
                            item.get("arguments", "").encode()
                        ).hexdigest(),
                    }
                )
                try:
                    result = control.execute(product, subject, item, timeout=20)
                except Exception as exc:
                    result = {"exit": 1, "output": "Broker error " + type(exc).__name__}
                stream.write(json.dumps(result).encode() + b"\n")
                stream.flush()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        out = control.execute(
            product,
            cp,
            {
                "type": "function_call",
                "name": "case_command",
                "arguments": json.dumps({"argv": ["python3", "/case/work/guest.py"]}),
            },
            timeout=47,
        )
    finally:
        done.set()
        server.close()
        thread.join(timeout=2)
    if out["exit"] != 0:
        raise ValueError("synthetic guest failed: " + out["output"][-900:])
    record = json.loads(out["output"])
    record["brokerCalls"] = calls
    record["caseReleaseSha256"] = isolation.digest(pair / "pair.json")
    record["observedToolWrite"] = (subject / "work/role-canary.txt").is_file() and (
        subject / "work/role-canary.txt"
    ).read_text() == nonce
    record["noCrossWriteOnControlSide"] = not (work / "role-canary.txt").exists()
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument(
        "--profile",
        choices=["safe", "restricted", "exclude", "qualified", "single"],
        default="safe",
    )
    parser.add_argument("--role", choices=["claude-fable-5-2", "claude-opus-5-5"], action="append")
    a = parser.parse_args()
    cli = Path(shutil.which("claude")).resolve()
    out = {
        "cliSha256": isolation.digest(cli),
        "cliVersion": subprocess.check_output([cli, "--version"], text=True).strip(),
        "roles": {},
    }
    for model in a.role or ["claude-fable-5-2", "claude-opus-5-5"]:
        record = run_role(model, a.product, a.scratch / model, cli, a.profile)
        out["roles"][model] = record
        a.output.write_text(json.dumps(out, indent=2) + "\n")
        print(
            model,
            "exit",
            record["exit"],
            "requests",
            len(record["requests"]),
            "tools",
            record["initialToolSet"],
            "responses",
            record["toolResponses"],
            "broker",
            len(record["brokerCalls"]),
            "diagnostic",
            record.get("cliDiagnostic", ""),
            flush=True,
        )
