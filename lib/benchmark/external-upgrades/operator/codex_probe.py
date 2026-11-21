"""Use a fresh synthetic case to inspect normal Codex's actual request envelope without sending it to a model."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess

import control
import isolation
from probe import packet


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("product", "codex-bin", "scratch", "output"):
        p.add_argument("--" + arg, type=Path, required=True)
    args = p.parse_args()
    root = args.scratch.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    pair, _ = packet(root)
    case = root / "case"
    isolation.fresh_case(case, pair, isolation.digest(pair / "pair.json"))
    guest = case / "work/transport"
    bridge = guest / "public/lib/benchmark/external-upgrades/operator"
    bridge.mkdir(parents=True)
    for name in ("mcp_server.py", "control.py", "isolation.py"):
        shutil.copyfile(isolation.HERE / name, bridge / name)
    for program in ("codex", "codex-code-mode-host"):
        shutil.copy2(args.codex_bin / program, guest / program)
    payload = (isolation.HERE / "synthetic/catalog_guest.py").read_text()
    event = {
        "type": "function_call",
        "name": "case_command",
        "arguments": json.dumps({"argv": ["python3", "-c", payload]}),
    }
    result = control.execute(args.product, case, event, timeout=55)
    if result["exit"]:
        raise ValueError("synthetic stock-client capture failed: " + result["output"][-600:])
    # The authenticated operation here is only the documented local status command. Keep the boolean and login kind.
    cli = args.codex_bin / "codex"
    auth = subprocess.run([cli, "login", "status"], capture_output=True, text=True, timeout=10)
    text = (auth.stdout + auth.stderr).lower()
    logged = auth.returncode == 0 and "logged in" in text
    rows = json.loads(result["output"])
    pin = json.loads(isolation.PIN.read_bytes())
    if set(rows) != {"preparation", "plannerAndProver"} or any(
        v["model"] != pin[k]["model"] for k, v in rows.items()
    ):
        raise ValueError("stock client did not construct both pinned model requests")
    record = {
        "schema": "external-upgrade-stock-control-probe/v1",
        "codex": subprocess.check_output(
            [cli, "--version"], text=True, stderr=subprocess.DEVNULL
        ).strip(),
        "codexSha256": isolation.digest(cli),
        "controlSideAuthStatusExit": auth.returncode,
        "controlSideAuthenticated": logged,
        "authKind": "ChatGPT" if logged and "chatgpt" in text else "other-or-unavailable",
        "network": "loopback-only synthetic receiver; fresh model state with no credentials; each request rejected before inference",
        "stages": rows,
        "liveModelInvocations": 0,
        "scoredLaunchAdmitted": False,
    }
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
