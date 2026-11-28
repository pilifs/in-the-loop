#!/usr/bin/env python3
"""Run a command where the network is demonstrably off, and say how that was shown.

A build tool's own offline switch constrains that tool alone: a script beside it, or a nested tool that fetches
its own distribution, still reaches the network. Here the command gets a network namespace of its own with only a
loopback interface in it (bubblewrap, `bwrap --unshare-net`), so nothing it starts can connect anywhere, whatever
flag it was or was not given. The file system is the host's, unless the caller asks for a home of its own.

  python3 jobs/sandbox.py probe                       what this host can enforce, as JSON
  python3 jobs/sandbox.py run [--home DIR] -- CMD...  CMD with no network; exit 125 when that cannot be enforced

`probe` runs inside the same sandbox a command would get, and records what it saw there: the interfaces, the
answer to a connection to a public address by number, and the answer to a name lookup. That record is the evidence
a result keeps of the offline condition. It also says so plainly when the host cannot enforce it (no bubblewrap,
or user namespaces refused), since "offline" that nothing enforced is only a flag.

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REFUSED = 125      # the exit of `run` when the network could not be taken away: nothing was run
# What runs inside the sandbox to see what is there. A public address by number (no lookup involved), then a name.
PROBE = r"""
import json, os, socket
# The interfaces of this process's own network namespace, asked of the kernel: /sys/class/net is the host's
# mount and lists the host's interfaces whatever namespace reads it.
seen = {"interfaces": sorted(name for _, name in socket.if_nameindex())}
s = socket.socket()
s.settimeout(3)
try:
    s.connect(("1.1.1.1", 443))
    seen["connect"] = "connected"
except OSError as e:
    seen["connect"] = f"{type(e).__name__}: {e.strerror or e}"
finally:
    s.close()
try:
    socket.getaddrinfo("repo.maven.apache.org", 443)
    seen["lookup"] = "resolved"
except OSError as e:
    seen["lookup"] = f"{type(e).__name__}: {e.strerror or e}"
print(json.dumps(seen))
"""


def prefix(home: Path | None = None, binds: list[tuple[str, str, str]] | None = None) -> list[str] | None:
    """The command that puts whatever follows it in a network namespace of its own, or None where this host has no
    bubblewrap. `home` becomes the command's $HOME directory's content (the real home is not visible at that
    path); `binds` are (kind, source, destination) with kind `ro` or `rw`, laid over the host's file system."""
    bwrap = shutil.which("bwrap")
    if not bwrap:
        return None
    cmd = [bwrap, "--unshare-net", "--die-with-parent", "--dev-bind", "/", "/"]
    if home is not None:
        cmd += ["--bind", str(home), str(Path.home())]
    for kind, source, destination in binds or []:
        cmd += ["--ro-bind" if kind == "ro" else "--bind", str(source), str(destination)]
    return cmd + ["--"]


# What points a build tool at a cache, a home or options of its own, wherever the runner happens to have them set: a
# task that is to run on prepared inputs alone is not given them. It sets its own (a Gradle home under its work).
CACHE_VARIABLES = ("GRADLE_USER_HOME", "GRADLE_RO_DEP_CACHE", "GRADLE_OPTS", "MAVEN_OPTS", "MAVEN_ARGS", "MAVEN_HOME", "M2_HOME", "M2_REPO",
                   "JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS", "CARGO_HOME", "RUSTUP_HOME", "GOPATH", "GOMODCACHE", "GOCACHE",
                   "PIP_CACHE_DIR", "PIP_INDEX_URL", "PYTHONUSERBASE", "PYTHONPATH", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
                   "IVY_HOME", "SBT_OPTS", "COURSIER_CACHE", "YARN_CACHE_FOLDER")


def clean(env: dict, tmp: Path | None = None) -> dict:
    """An environment for a task that runs on prepared inputs alone: the caller's, without the variables that
    point a build tool at a cache or a home of its own, and with the temporary folder the sandbox gives it."""
    kept = {k: v for k, v in env.items() if k not in CACHE_VARIABLES and not k.lower().startswith("npm_config_")}
    if tmp is not None:
        kept["TMPDIR"] = str(tmp)
    return kept


def alone(box: Path, writable: list, readable: list) -> tuple[list[str] | None, Path]:
    """The command prefix for a task that is to see prepared inputs and nothing a machine has gathered since: no
    network, an empty home directory and an empty /tmp of its own (under `box`), `writable` folders (its work),
    and `readable` ones bound read-only (the prepared inputs, the bundle, the tools it declares it reads). What
    is under the real home is not there unless it is one of those: no ~/.m2, no ~/.gradle, no settings of the
    user's. The rest of the machine (/usr, /etc) is as it is. Returns the prefix and the /tmp folder's source."""
    home, tmp = Path(box) / "home", Path(box) / "tmp"
    home.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    binds = [("rw", str(tmp), "/tmp")] + [("rw", str(p), str(p)) for p in writable] + \
        [("ro", str(p), str(p)) for p in readable if Path(p).exists()]
    return prefix(home=home, binds=binds), tmp


def probe(home: Path | None = None) -> dict:
    """What a command would find in the sandbox: `enforced` only when the sandbox started, shows no interface
    but loopback, and refused both the connection and the lookup."""
    box = prefix(home)
    if box is None:
        return {"mode": "none", "enforced": False, "why": "bubblewrap (bwrap) is not installed: nothing here can take the network away"}
    try:
        proc = subprocess.run(box + [sys.executable, "-c", PROBE], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"mode": "none", "enforced": False, "why": f"the sandbox did not start: {type(e).__name__}: {e}"}
    if proc.returncode != 0:
        return {"mode": "none", "enforced": False,
                "why": f"the sandbox did not start (exit {proc.returncode}): {(proc.stderr or proc.stdout).strip()[-300:]}"}
    try:
        seen = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"mode": "none", "enforced": False, "why": "the probe inside the sandbox said nothing readable"}
    off = (seen.get("interfaces") in (["lo"], []) and seen.get("connect") != "connected" and seen.get("lookup") != "resolved")
    return {"mode": "none", "enforced": off, "how": "bwrap --unshare-net: a network namespace with a loopback interface alone",
            "probe": seen, **({} if off else {"why": "the sandbox started, and the probe inside it found an interface besides "
                                                    "loopback, a connection or a name lookup that worked"})}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sandbox.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("probe", help="what this host can enforce, and what a command would see")
    p.add_argument("--home", help="a folder to be the command's home directory")
    p = sub.add_parser("run", help="run a command with no network")
    p.add_argument("--home", help="a folder to be the command's home directory, in place of the real one")
    p.add_argument("--ro", action="append", default=[], metavar="SRC[:DEST]", help="lay SRC over DEST read-only; repeatable")
    p.add_argument("--rw", action="append", default=[], metavar="SRC[:DEST]", help="lay SRC over DEST writable; repeatable")
    p.add_argument("--evidence", help="write the probe's record to this file before the command runs")
    p.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    home = Path(args.home) if args.home else None
    if args.command == "probe":
        seen = probe(home)
        print(json.dumps(seen, indent=2))
        return 0 if seen["enforced"] else 1
    cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    if not cmd:
        parser.error("run: give the command after --")
    seen = probe(home)
    if args.evidence:
        Path(args.evidence).write_text(json.dumps(seen, indent=2) + "\n")
    if not seen["enforced"]:
        print(f"sandbox.py: the network cannot be taken away here, so nothing was run: {seen.get('why')}", file=sys.stderr)
        return REFUSED
    binds = [(kind, *(spec.split(":", 1) if ":" in spec else (spec, spec))) for kind, specs in (("ro", args.ro), ("rw", args.rw)) for spec in specs]
    os.execvp(prefix(home, binds)[0], prefix(home, binds) + cmd)


if __name__ == "__main__":
    sys.exit(main())
