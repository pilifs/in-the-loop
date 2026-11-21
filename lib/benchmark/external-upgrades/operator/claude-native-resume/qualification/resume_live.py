import argparse
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

here = Path(__file__).resolve().parent
op = Path.cwd() / "lib/benchmark/external-upgrades/operator"
sys.path.insert(0, str(op))
sys.path.insert(0, str(op / "claude-alternate/qualification"))
import control  # noqa: E402
import isolation  # noqa: E402
import probe  # noqa: E402
import live  # noqa: E402

MODELS = ("claude-fable-5-2", "claude-opus-5-5")
tool = "mcp__neutral_case__case_command"
start_prompt = 'Public synthetic transport test. Use the case_command MCP tool exactly once with {"argv":["python3","/case/work/observe_public_case.py"]}. Keep its result for this session.'
continue_prompt = "Continue this exact same conversation. From the preceding successful tool result, answer with only its nonce, the old integer and the new integer. Do not call a tool or invent values."
opts = {
    "claudeMdExcludes": ["**/CLAUDE.md", "**/CLAUDE.local.md", "**/AGENTS.md", "**/.claude/rules/**"],
    "autoMemoryEnabled": False,
    "disableAllHooks": True,
}


def sh_measure(root, product, pair, cpid, model, session, mode, prompt, state, nonce, foreign, cli):
    cp = root / "shadow"
    isolation.fresh_case(cp, pair, cpid)
    w = cp / "work"
    source = w / "public/lib/benchmark/external-upgrades/operator"
    source.mkdir(parents=True)
    shutil.copy2(cli, w / "claude")
    libs = w / "runtime-libs"
    libs.mkdir()
    for n in ("librt.so.1", "libpthread.so.0", "libdl.so.2"):
        shutil.copy2(Path("/usr/lib/x86_64-linux-gnu") / n, libs / n)
    for n in ("mcp_server.py", "control.py", "isolation.py"):
        shutil.copy2(op / n, source / n)
    shutil.copy2(here / "shadow_guest.py", w / "shadow_guest.py")
    (w / "mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "neutral_case": {
                        "type": "stdio",
                        "command": "/usr/bin/python3",
                        "args": [
                            "/case/work/public/lib/benchmark/external-upgrades/operator/mcp_server.py",
                            "--product",
                            "/none",
                            "--case",
                            "/none",
                        ],
                    }
                }
            }
        )
    )
    (w / "measure.json").write_text(
        json.dumps(
            {
                "model": model,
                "session": session,
                "mode": mode,
                "prompt": prompt,
                "nonce": nonce,
                "foreign": foreign,
                "options": opts,
            }
        )
    )
    prior = None
    before = None
    if mode == "--resume":
        ps = list(state.rglob(session + ".jsonl"))
        assert len(ps) == 1
        prior = ps[0]
        assert (
            prior.is_file()
            and not prior.is_symlink()
            and prior.resolve().is_relative_to(state.resolve())
        )
        before = live.sha(prior)
        dest = w / "state" / prior.relative_to(state)
        dest.parent.mkdir(parents=True)
        shutil.copyfile(prior, dest)
    msg = control.execute(
        product,
        cp,
        {
            "type": "function_call",
            "name": "case_command",
            "arguments": json.dumps({"argv": ["python3", "/case/work/shadow_guest.py"]}),
        },
        timeout=35,
    )
    assert msg["exit"] == 0, msg["output"][:190]
    d = json.loads(msg["output"])
    (root / "shadow-summary.json").write_text(json.dumps(d, indent=2) + "\n")
    assert (
        d["tools"] == [tool]
        and d["model"] == model
        and d["effort"] == "high"
        and d["initialOrNewPromptPresent"]
        and not d["restoresForeignNonce"]
        and d["restoresOwnResult"] == (mode == "--resume")
    )
    d["originalUnchanged"] = prior is None or live.sha(prior) == before
    d["privateTranscriptSha256"] = before
    d["reservedInputAndOutput"] = d["wireBytes"] + 8192 + 1024
    return d


def authcheck(env, cli):
    r = subprocess.run(
        [cli, "auth", "status", "--json"],
        env=env,
        cwd="/srv",
        capture_output=True,
        text=True,
        timeout=8,
    )
    try:
        j = json.loads(r.stdout)
        return {
            "exit": r.returncode,
            "loggedIn": j.get("loggedIn"),
            "authMethod": j.get("authMethod"),
        }
    except Exception:
        return {"exit": r.returncode, "loggedIn": False, "authMethod": None}


def child(model, mode, sid, prompt, env, mcp, cli, audit, case, nonce, foreign, budget):
    argv = [
        str(cli),
        "-p",
        "--model",
        model,
        "--effort",
        "high",
        "--restricted",
        "--tools",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        str(mcp),
        "--disable-slash-commands",
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        tool,
        "--max-turns",
        "1",
        "--max-budget-usd",
        str(budget),
        "--settings",
        json.dumps(opts),
        "--output-format",
        "stream-json",
        "--verbose",
        mode,
        sid,
        "--",
        prompt,
    ]
    start = time.monotonic()
    at = dt.datetime.now(dt.timezone.utc).isoformat()
    q = subprocess.Popen(
        argv,
        env=env,
        cwd="/srv",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    expired = False
    try:
        out, err = q.communicate(timeout=110)
    except subprocess.TimeoutExpired:
        expired = True
        os.killpg(q.pid, signal.SIGKILL)
        out, err = q.communicate()
    elapsed = round(time.monotonic() - start, 3)
    events = []
    for line in out.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    init = next((e for e in events if e.get("subtype") == "init" and e.get("type") == "system"), {})
    finish = next((e for e in reversed(events) if e.get("type") == "result"), {})
    txt = str(finish.get("result", ""))
    used = finish.get("modelUsage") or {}
    u = finish.get("usage") or {}
    calls = [json.loads(line) for line in audit.read_text().splitlines()] if audit.exists() else []
    reason = live.known_reason(
        txt + " " + str(finish.get("errors")) + " " + err.decode(errors="replace")
    )
    names = [
        b.get("name")
        for e in events
        if e.get("type") == "assistant"
        for b in e.get("message", {}).get("content", [])
        if b.get("type") == "tool_use"
    ]
    obspath = case / "work/model-tool-result.json"
    obs = json.loads(obspath.read_bytes()) if obspath.is_file() else {}
    cost = finish.get("total_cost_usd")
    tokens = {
        k: u.get(k)
        for k in (
            "input_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
            "output_tokens",
        )
    }
    rec = {
        "mode": mode,
        "model": model,
        "startedUtc": at,
        "seconds": elapsed,
        "deadlineSeconds": 120,
        "budgetUsd": budget,
        "costUsd": cost,
        "tokens": tokens,
        "modelsUsed": list(used),
        "cliExit": q.returncode,
        "cliDisposition": finish.get("subtype"),
        "accountRefusal": reason if reason not in ("client turn limit",) else None,
        "sessionMatched": init.get("session_id") == sid,
        "roleSessionSha256": hashlib.sha256(sid.encode()).hexdigest(),
        "timedOut": expired,
        "tools": init.get("tools"),
        "modelToolCalls": names,
        "brokerCalls": calls,
        "old": obs.get("old"),
        "new": obs.get("new"),
        "checker": obs.get("checker"),
        "returnedOwnNonce": nonce in txt,
        "returnedForeignNonce": any(x in txt for x in foreign),
        "returnedBothResults": len(re.findall(r"(?<![a-z0-9])42(?![a-z0-9])", txt.lower())) >= 2,
    }
    first = mode == "--session-id"
    rec["qualified"] = bool(
        not expired
        and rec["sessionMatched"]
        and set(used) == {model}
        and init.get("model") == model
        and init.get("tools") == [tool]
        and cost is not None
        and cost <= budget
        and not rec["returnedForeignNonce"]
        and (
            (
                first
                and len(calls) == 1
                and calls[0]["exit"] == 0
                and calls[0]["exactRequestedCommand"]
                and names == [tool]
                and obs.get("nonce") == nonce
                and obs.get("old") == obs.get("new") == 42
                and finish.get("subtype") == "error_max_turns"
            )
            or (
                not first
                and q.returncode == 0
                and finish.get("subtype") == "success"
                and not names
                and not calls
                and rec["returnedOwnNonce"]
                and rec["returnedBothResults"]
            )
        )
    )
    return rec


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--product", type=Path, required=True)
    args.add_argument("--control-product", type=Path, required=True)
    args.add_argument("--scratch", type=Path, required=True)
    args.add_argument("--output", type=Path, required=True)
    a = args.parse_args()
    root = a.scratch.resolve()
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    pair, _ = probe.packet(root)
    cpid = live.sha(pair / "pair.json")
    cli = Path(shutil.which("claude")).resolve()
    pin = json.loads((op.parent / "v0.json").read_bytes())
    record = {
        "schema": "external-upgrade-first-party-native-resume-smoke/v1",
        "disclosedSynthetic": True,
        "sourceRevision": pin["revision"],
        "checkerSha256": pin["sha256"]["jvmcontract"],
        "cliSha256": live.sha(cli),
        "release": cpid,
        "productRoot": live.sha(a.product / "manifest.json"),
        "calls": [],
        "roles": {},
    }
    print("first-party resume smoke started", flush=True)
    nonces = {role: secrets.token_hex(12) for role in MODELS}
    for model in MODELS:
        sub = root / model
        sub.mkdir()
        state = sub / "private-role-state"
        state.mkdir(mode=0o700)
        case = sub / "case"
        isolation.fresh_case(case, pair, cpid)
        nonce = nonces[model]
        foreign = [v for k, v in nonces.items() if k != model]
        sid = str(uuid.uuid4())
        (case / "work/challenge").write_text(nonce + "\n")
        shutil.copy2(
            op / "claude-alternate/qualification/live_subject.py",
            case / "work/observe_public_case.py",
        )
        env = {
            k: os.environ[k]
            for k in ("HOME", "USER", "LOGNAME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS")
            if k in os.environ
        }
        env.update(
            {
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "LANG": "C.UTF-8",
                "TZ": "UTC",
                "CLAUDE_CONFIG_DIR": str(state),
                "CLAUDE_SECURESTORAGE_CONFIG_DIR": "",
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                "DISABLE_TELEMETRY": "1",
                "DISABLE_ERROR_REPORTING": "1",
                "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
                "ENABLE_TOOL_SEARCH": "false",
                "CLAUDE_CODE_MAX_RETRIES": "0",
                "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "1024",
            }
        )
        account = authcheck(env, cli)
        record["roles"][model] = {"officialCredentialStatus": account}
        if account.get("loggedIn") is not True or account.get("authMethod") != "claude.ai":
            record["stopped"] = (
                "The normal first-party credential service was not available from the private config."
            )
            a.output.write_text(json.dumps(record, indent=2) + "\n")
            break
        for mode, prompt, phase in [
            ("--session-id", start_prompt, "initial"),
            ("--resume", continue_prompt, "resume"),
        ]:
            step = sub / phase
            step.mkdir()
            tmp = step / "tmp"
            tmp.mkdir()
            env["TMPDIR"] = str(tmp)
            audit = step / "broker.jsonl"
            mcp = step / "mcp.json"
            mcp.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "neutral_case": {
                                "type": "stdio",
                                "command": "/usr/bin/python3",
                                "args": [
                                    str(op / "claude-alternate/qualification/live_broker.py"),
                                    "--baseline",
                                    str(op),
                                    "--product",
                                    str(a.product),
                                    "--case",
                                    str(case),
                                    "--audit",
                                    str(audit),
                                ],
                            }
                        }
                    }
                )
            )
            shadow = sh_measure(
                step,
                a.control_product,
                pair,
                cpid,
                model,
                sid,
                mode,
                prompt,
                state,
                nonce,
                foreign,
                cli,
            )
            spent = sum(x["costUsd"] or 0 for x in record["calls"])
            budget = min(0.75, round(2.98 - spent, 4))
            assert budget > 0
            out = child(model, mode, sid, prompt, env, mcp, cli, audit, case, nonce, foreign, budget)
            out["preauthorization"] = shadow
            out["actualChargedTokens"] = sum(
                out["tokens"][k] or 0
                for k in ("input_tokens", "cache_creation_input_tokens", "output_tokens")
            )
            out["withinReservation"] = out["actualChargedTokens"] <= shadow["reservedInputAndOutput"]
            record["calls"].append(out)
            record["totalClientEstimatedUsd"] = sum(x["costUsd"] or 0 for x in record["calls"])
            a.output.write_text(json.dumps(record, indent=2) + "\n")
            print(
                model,
                phase,
                "qualified",
                out["qualified"],
                "reason",
                out["accountRefusal"],
                "cost",
                out["costUsd"],
                "seconds",
                out["seconds"],
                flush=True,
            )
            if not out["qualified"] or not out["withinReservation"]:
                record["stopped"] = "An original request did not qualify; no retry or fallback."
                break
        record["roles"][model]["caseCredentialsFileAbsent"] = not (
            state / ".credentials.json"
        ).exists()
        record["roles"][model]["privateStateMode"] = oct(state.stat().st_mode & 0o777)
        record["roles"][model]["currentCaseTranscriptsCount"] = len(list(state.rglob(sid + ".jsonl")))
        if record.get("stopped"):
            break
    record["qualified"] = (
        len(record["calls"]) == 4
        and all(x["qualified"] and x["withinReservation"] for x in record["calls"])
        and record["totalClientEstimatedUsd"] < 3
    )
    a.output.write_text(json.dumps(record, indent=2) + "\n")
