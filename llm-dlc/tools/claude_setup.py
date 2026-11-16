#!/usr/bin/env python3
"""What has Claude Code loaded besides this checkout and the /prove-java-change plugin? The check of the user's
Claude Code setup in step 1 of the skill (llm-dlc/runtime.md#what-claude-code-has-loaded).

    claude_setup.py check [--json]    the warning, what the session running this has loaded, whether the proof
                                      loop's own sessions start without it, and the command that starts a clean one
    claude_setup.py flags             the launch flags of a clean session, one per line (prove-loop.sh reads them)
    claude_setup.py launch [ARG ...]  start Claude Code in this checkout with those flags, on Fable 5.2 at high effort

A clean session loads this checkout (its CLAUDE.md, its settings and its skills) and nothing of the user's own
setup: no other plugin, no MCP server or claude.ai connector, no memory file of the user's or of a directory above,
no user skill, command, agent or hook. It is a matter of launch flags only (clean_flags()), so nothing in the user's
configuration is changed, and nothing has to be put back afterwards.

`check` asks Claude Code itself. It starts two one-word sessions on the smallest model, without tools and without a
transcript, and reads what each reports at start-up: one started the way the session running this was (its
directory and its own launch flags, from the process CLAUDE_PID names), one clean in this checkout. What the first
has and the second lacks is what the user's session has loaded. Beside that it lists what a start-up report does not
show: the memory files and the hooks that session reads, and settings an administrator manages, which no flag turns
off. The first probe starts the user's MCP servers and runs their session hooks once, as starting Claude Code does.

The list can fall short of what an interactive session holds: a non-interactive probe has been seen to report no
claude.ai connectors in a directory with a memory file of its own, where the interactive session had them. So the
plugins Claude Code's own listing calls enabled are added, and the skill adds what the session can see in its own
context. Nothing listed is ever wrong; something may be missing.

Exit 0 when the session is clean and a clean launch works here, 1 otherwise, and 2 in a development checkout, where
the check does not apply (its hooks would trace the probes). A session can't unload what it already
holds, so `check` changes nothing: it prints the one command that starts a clean session, which is `launch`.

Standard library only. It never prints a setting's value, only names and paths.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import mode  # llm-dlc/tools/mode.py

REPO = Path(__file__).resolve().parents[2]
PLUGIN = "in-the-loop"
MODEL, EFFORT = "claude-fable-5-2", "high"
WARNING = ("Warning: any extraneous context from external sources may lead to unexpected results. That is anything "
           "Claude Code has loaded besides this plugin: other plugins, MCP servers and connectors, memory files, "
           "skills, agents and hooks.")
# claude.ai connectors are not named by --strict-mcp-config's documentation, so they are turned off by name as well.
CLEAN_ENV = {"ENABLE_CLAUDEAI_MCP_SERVERS": "false"}
MANAGED = Path("/etc/claude-code")
# Launch flags that decide what a session loads, with whether a value follows (None: every argument up to the next
# flag). `check` repeats the ones the user's session was started with.
LOADING_FLAGS = {"--setting-sources": True, "--settings": True, "--plugin-dir": True, "--plugin-url": True,
                 "--agents": True, "--agent": True, "--mcp-config": None, "--strict-mcp-config": False,
                 "--safe-mode": False, "--bare": False, "--disable-slash-commands": False, "--restricted": False}
PROBE = "Reply with the single word ok."


def config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def memory_files(directory: Path) -> list[Path]:
    """The memory files Claude Code reads from one directory."""
    found = [p for p in (directory / "CLAUDE.md", directory / "CLAUDE.local.md", directory / ".claude" / "CLAUDE.md")
             if p.is_file()]
    rules = directory / ".claude" / "rules"
    return found + (sorted(rules.rglob("*.md")) if rules.is_dir() else [])


def user_memory() -> list[Path]:
    config = config_dir()
    found = [config / "CLAUDE.md"] if (config / "CLAUDE.md").is_file() else []
    return found + (sorted((config / "rules").rglob("*.md")) if (config / "rules").is_dir() else [])


def clean_flags(repo: Path = REPO) -> list[str]:
    """The launch flags of a clean session in `repo`. The settings sources leave the user's out (their plugins,
    hooks, skills and agents) and --strict-mcp-config leaves every MCP server out. The memory files of the user and
    of the directories above the checkout are excluded by path as well: Claude Code's documentation does not say
    the sources cover them, and it does document this setting."""
    config = config_dir()
    excluded = [str(config / "CLAUDE.md"), str(config / "rules" / "**")]
    for above in repo.resolve().parents:
        excluded += [str(p) for p in memory_files(above)]
    return ["--setting-sources", "project,local", "--strict-mcp-config",
            "--settings", json.dumps({"claudeMdExcludes": excluded}, separators=(",", ":"))]


def session() -> dict | None:
    """The Claude Code process this runs under: its arguments and the directory it was started in. None when it
    can't be told (no CLAUDE_PID, or no /proc)."""
    pid = os.environ.get("CLAUDE_PID", "")
    try:
        argv = Path(f"/proc/{int(pid)}/cmdline").read_bytes().decode(errors="replace").split("\0")
        cwd = os.readlink(f"/proc/{int(pid)}/cwd")
    except (ValueError, OSError):
        return None
    return {"argv": [a for a in argv if a], "cwd": cwd}


def loading_flags(argv: list[str]) -> list[str]:
    """The arguments of a launch that decide what it loads, as they were given."""
    kept, i = [], 1
    while i < len(argv):
        name, _, inline = argv[i].partition("=")
        i += 1
        if name not in LOADING_FLAGS:
            continue
        kept.append(argv[i - 1])
        takes = LOADING_FLAGS[name]
        if inline or takes is False:
            continue
        while i < len(argv) and not argv[i].startswith("--"):
            kept.append(argv[i])
            i += 1
            if takes is True:
                break
    return kept


def flag_value(flags: list[str], name: str) -> str | None:
    for i, flag in enumerate(flags):
        if flag == name and i + 1 < len(flags):
            return flags[i + 1]
        if flag.startswith(name + "="):
            return flag.split("=", 1)[1]
    return None


def probe(flags: list[str], cwd: str | Path, env: dict | None = None, timeout: int = 180) -> dict:
    """What a session started in `cwd` with `flags` reports at start-up: its `init` event, or {"error": why}. One
    word on the smallest model, then on the account's default when that one is not available."""
    base = ["claude", "-p", PROBE, "--tools", "", "--no-session-persistence", "--output-format", "stream-json",
            "--verbose", *flags]
    why = "claude printed no start-up report"
    for model in (["--model", "haiku"], []):
        try:
            r = subprocess.run(base + model, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True,
                               text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as e:
            return {"error": f"{type(e).__name__}: claude did not answer"}
        init = result = None
        for line in r.stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "system" and event.get("subtype") == "init":
                init = event
            elif event.get("type") == "result":
                result = event
        if init is not None and result is not None and result.get("subtype") == "success" and not result.get("is_error"):
            return init
        why = (f"the session did not answer ({(result or {}).get('subtype') or f'exit {r.returncode}'})"
               if init is not None else why)
    return {"error": why}


def loaded(init: dict) -> dict[str, set[str]]:
    """A start-up report as sets of names, by kind. Claude Code's built-in plugins are left out."""
    def names(key):
        return {x.get("name") if isinstance(x, dict) else x for x in init.get(key) or []} - {None}
    plugins = {p.get("name") for p in init.get("plugins") or [] if isinstance(p, dict) and p.get("path") != "builtin"}
    skills = names("skills")
    return {"mcp server": names("mcp_servers"), "plugin": plugins - {None}, "skill": skills, "agent": names("agents"),
            "command": names("slash_commands") - skills,
            "output style": {init["output_style"]} if init.get("output_style") else set()}


def own(kind: str, name: str) -> bool:
    """Is this the plugin's own? It is the one thing a session is meant to have."""
    return (kind == "plugin" and name == PLUGIN) or (kind in ("skill", "command") and name.startswith(PLUGIN + ":"))


def beyond(session_init: dict, clean_init: dict) -> list[dict]:
    """What the session's start-up report has that a clean one lacks, the plugin's own left out."""
    ours, clean = loaded(session_init), loaded(clean_init)
    return [{"kind": kind, "name": name, "from": "the session's start-up report"}
            for kind in ours for name in sorted(ours[kind] - clean[kind]) if not own(kind, name)]


def sources(flags: list[str]) -> set[str]:
    """The settings sources a launch reads: all three unless it says otherwise, none in safe or bare mode."""
    if "--safe-mode" in flags or "--bare" in flags:
        return set()
    given = flag_value(flags, "--setting-sources")
    return {"user", "project", "local"} if given is None else {s.strip() for s in given.split(",") if s.strip()}


def excluded_by(flags: list[str]) -> list[str]:
    try:
        settings = json.loads(flag_value(flags, "--settings") or "{}")
    except ValueError:
        return []
    patterns = settings.get("claudeMdExcludes") if isinstance(settings, dict) else None
    return [p for p in patterns or [] if isinstance(p, str)]


def inside(path: Path, repo: Path) -> bool:
    return path.resolve().is_relative_to(repo.resolve())


def on_disk(cwd: Path, flags: list[str], repo: Path = REPO) -> list[dict]:
    """What a session started in `cwd` with `flags` reads that its start-up report does not show: memory files and
    hooks. The checkout's own files are not extra, and neither is a file the launch excludes."""
    read, skip, config = sources(flags), excluded_by(flags), config_dir()
    if not read:
        return []
    memory = []
    if "user" in read:
        memory += user_memory()
    if "project" in read or "local" in read:
        for directory in (cwd, *cwd.parents):
            memory += [p for p in memory_files(directory)
                       if ("local" if p.name == "CLAUDE.local.md" else "project") in read]
    found = [{"kind": "memory file", "name": str(p), "from": "read when the session starts"}
             for p in memory if not inside(p, repo) and not any(fnmatch.fnmatch(str(p), pattern) for pattern in skip)]
    for source, path in (("user", config / "settings.json"), ("project", cwd / ".claude" / "settings.json"),
                         ("local", cwd / ".claude" / "settings.local.json")):
        if source not in read or inside(path, repo):
            continue
        try:
            hooks = json.loads(path.read_text()).get("hooks") or {}
        except (OSError, ValueError, AttributeError):
            continue
        if hooks:
            found.append({"kind": "hooks", "name": ", ".join(sorted(hooks)), "from": str(path)})
    return found


def enabled_plugins(cwd: Path, flags: list[str]) -> list[dict]:
    """The plugins Claude Code's own listing calls enabled for a session started in `cwd` with `flags`: a second
    source beside the start-up report, which a non-interactive probe can under-report."""
    read = sources(flags) | {"managed"}
    try:
        r = subprocess.run(["claude", "plugin", "list", "--json"], cwd=cwd, capture_output=True, text=True,
                           timeout=60, stdin=subprocess.DEVNULL)
        listed = json.loads(r.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []
    found = []
    for plugin in listed if isinstance(listed, list) else []:
        if not isinstance(plugin, dict) or not plugin.get("enabled") or plugin.get("scope") not in read:
            continue
        name = str(plugin.get("id") or "").split("@")[0]
        if name and not own("plugin", name):
            found.append({"kind": "plugin", "name": name, "from": f"enabled in {plugin['scope']} settings"})
    return found


def managed(directory: Path = MANAGED) -> list[dict]:
    """Settings an administrator manages on this machine. No launch flag turns them off."""
    files = [p for p in (directory / "managed-settings.json", directory / "managed-mcp.json") if p.is_file()]
    files += sorted((directory / "managed-settings.d").glob("*.json")) if (directory / "managed-settings.d").is_dir() else []
    return [{"kind": "managed settings", "name": str(p), "from": "this machine's administrator"} for p in files]


def check(repo: Path = REPO) -> dict:
    here = session()
    cwd = Path(here["cwd"]) if here else Path.cwd()
    flags = loading_flags(here["argv"]) if here else []
    clean = clean_flags(repo)
    with ThreadPoolExecutor(2) as pool:
        theirs = pool.submit(probe, flags, cwd)
        ours = pool.submit(probe, clean, repo, CLEAN_ENV)
        theirs, ours = theirs.result(), ours.result()
    policy = managed()
    out = {"warning": WARNING,
           "session": {"found": here is not None, "directory": str(cwd), "flags": flags, "error": theirs.get("error")},
           "loop": {"isolated": "error" not in ours, "error": ours.get("error"), "flags": clean, "remaining": []},
           "managed": policy,
           "relaunch": f"python3 {shlex.quote(str(repo / 'llm-dlc/tools/claude_setup.py'))} launch"}
    if "error" not in ours:
        left = loaded(ours)
        out["loop"]["remaining"] = [{"kind": kind, "name": name} for kind in ("mcp server", "plugin")
                                    for name in sorted(left[kind]) if not own(kind, name)]
    if "error" in theirs or "error" in ours:
        out["loaded"] = None  # not known: the comparison needs both reports
    else:
        out["loaded"] = beyond(theirs, ours)
        reported = {x["name"] for x in out["loaded"] if x["kind"] == "plugin"}
        out["loaded"] += [x for x in enabled_plugins(cwd, flags) if x["name"] not in reported]
        out["loaded"] += on_disk(cwd, flags, repo)
    out["clean"] = out["loaded"] == [] and out["loop"]["isolated"] and not out["loop"]["remaining"]
    return out


def report(found: dict) -> str:
    lines = [found["warning"], ""]
    where = found["session"]["directory"] + ("" if found["session"]["found"] else
                                             " (the session's own launch could not be read: taken as a plain `claude` here)")
    if found["loaded"] is None:
        why = found["session"]["error"] or found["loop"]["error"]
        lines.append(f"What this session has loaded could not be checked: {why}.")
    elif found["loaded"]:
        lines.append(f"This session ({where}) has loaded, besides this plugin:")
        lines += [f"  {x['kind']:<13} {x['name']}" for x in found["loaded"]]
    else:
        lines.append(f"This session ({where}) has loaded nothing besides this plugin and the checkout.")
    loop = found["loop"]
    if not loop["isolated"]:
        lines.append(f"The proof loop's sessions can't be started clean here: {loop['error']}. "
                     f"Started with `prove-loop.sh --no-isolation`, they load what a plain `claude` loads.")
    elif loop["remaining"]:
        lines.append("The proof loop's sessions start clean, except for what no flag turns off:")
        lines += [f"  {x['kind']:<13} {x['name']}" for x in loop["remaining"]]
    else:
        lines.append("The proof loop's sessions start clean: none of this reaches them.")
    if found["managed"]:
        lines.append("Managed settings apply to every session here and can't be turned off:")
        lines += [f"  {x['name']}" for x in found["managed"]]
    if not found["clean"] and loop["isolated"]:
        lines += ["", "A session can't unload what it already holds. To run the skill with none of it, start a clean "
                      "session with the command below and run the skill there, as /prove-java-change with the same "
                      "request:", f"  {found['relaunch']}",
                  "Continuing in this session is possible, and not recommended."]
    return "\n".join(lines)


def launch(args: list[str], repo: Path = REPO) -> None:
    command = ["claude", *clean_flags(repo)]
    if not any(a == "--model" or a.startswith("--model=") for a in args):
        command += ["--model", MODEL]
    if not any(a == "--effort" or a.startswith("--effort=") for a in args):
        command += ["--effort", EFFORT]
    os.chdir(repo)
    os.environ.update(CLEAN_ENV)
    os.execvp("claude", command + args)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["launch"]:  # everything after it is claude's
        launch(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("check").add_argument("--json", action="store_true")
    sub.add_parser("flags")
    sub.add_parser("launch")
    args = ap.parse_args(argv)
    if args.command == "flags":
        print("\n".join(clean_flags()))
        return 0
    if mode.mode(REPO) != "runtime":
        # A development checkout's hooks trace every session started in it, a probe included, and its authors'
        # setup is theirs to keep: the skill skips step 1 here.
        print("claude_setup.py check: this is a development checkout; the check is for a runtime one "
              "(llm-dlc/runtime.md)", file=sys.stderr)
        return 2
    found = check()
    print(json.dumps(found, indent=1) if args.json else report(found))
    return 0 if found["clean"] else 1


if __name__ == "__main__":
    sys.exit(main())
