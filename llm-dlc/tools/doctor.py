#!/usr/bin/env python3
"""Can this machine prove a Java change with this repository? The quantitative assessment of step 1 of
/prove-java-change (llm-dlc/runtime.md), and as useful in a development checkout.

    python3 llm-dlc/tools/doctor.py           a table: each check, what was found, what is wanted
    python3 llm-dlc/tools/doctor.py --json    the same as data, with the budget it proposes for this machine

Exit 0 when nothing blocks, 1 when something does. Three levels:

  blocking  a proof can't run here until it is fixed: a hardware limit, an operating system the tools have never
            run on, or a tool every proof needs. A hardware limit is blocking by itself: no setup removes it.
  limits    the machine works, with less: a proof route, an engine or a safeguard is unavailable, and the check
            says which.
  ok        as wanted.

What is wanted is what the repository's own tools call for, and each check names where that comes from. The
hardware minimums are the smallest machine the repository has been worked on (an 8-core laptop with 9 GB, in
verification/README.md), less a margin, so a machine below them is one nothing here has ever run on.

The budget is a proposal for verification/pipeline.local.toml and the loop's memory cap, shared out as
verification/README.md describes: a reserve for the person and the operating system, one loop's cap, and the rest
to the verification runner. It is arithmetic, for whoever sets the machine up to adjust.

Standard library only, and nothing is installed or changed: it only looks.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GIB = 1 << 30
# The smallest machine: below these nothing has run (blocking); below the comfortable ones a long proof is slow or
# may be deferred for memory (limits).
MIN_MEMORY, COMFORTABLE_MEMORY = 8 * GIB, 16 * GIB
MIN_CPUS, COMFORTABLE_CPUS = 2, 4
MIN_DISK, COMFORTABLE_DISK = 10 * GIB, 25 * GIB  # a jvmcontract build alone is about 7.5 GiB of lib/target
JDK_CANDIDATES = Path(os.environ.get("TARGETS_JDK_CANDIDATES", Path.home() / ".sdkman/candidates/java"))


def out(*argv: str, timeout: int = 30) -> str | None:
    """A command's first line of output, or None when it is missing, fails or says nothing."""
    if not shutil.which(argv[0]):
        return None
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = [line for line in (r.stdout + r.stderr).splitlines() if line.strip()]
    return lines[0].strip() if r.returncode == 0 and lines else None


def numbers(text: str | None) -> tuple[int, ...]:
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    return tuple(int(g or 0) for g in m.groups()) if m else ()


def check(id: str, group: str, found, wanted: str, level: str, why: str, fix: str = "") -> dict:
    return {"id": id, "group": group, "found": found, "wanted": wanted, "level": level, "why": why,
            **({"fix": fix} if fix and level != "ok" else {})}


def meminfo() -> dict[str, int]:
    values = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, rest = line.partition(":")
            values[key] = int(rest.split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return values


def machine() -> dict:
    memory = meminfo()
    try:
        cpus = len(os.sched_getaffinity(0))
    except AttributeError:
        cpus = os.cpu_count() or 0
    try:
        release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
    except OSError:
        release = {}
    try:
        wsl = "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        wsl = False
    return {"system": platform.system(), "architecture": platform.machine(), "cpus": cpus,
            "os": release.get("PRETTY_NAME", "").strip('"') or platform.platform(), "wsl": wsl,
            "memory": memory.get("MemTotal", 0), "memoryAvailable": memory.get("MemAvailable", 0),
            "swap": memory.get("SwapTotal", 0), "diskFree": shutil.disk_usage(REPO).free, "diskAt": str(REPO)}


def gib(n: int) -> str:
    return f"{n / GIB:.1f} GiB"


def hardware(m: dict) -> list[dict]:
    def sized(id, found, minimum, comfortable, show, why, less):
        level = "blocking" if found < minimum else "limits" if found < comfortable else "ok"
        return check(id, "hardware", show(found), f"at least {show(minimum)}; {show(comfortable)} or more to be "
                     f"comfortable", level, why + (f" {less}" if level == "limits" else ""))
    return [
        check("os", "hardware", m["os"] + (" (WSL)" if m["wsl"] else ""), "Linux",
              "ok" if m["system"] == "Linux" else "blocking",
              "the loops and the verification runner read /proc and cap memory with systemd; they have run on Ubuntu "
              "24.04 and 26.04 only, on a machine, a VM and WSL2 (examples/setup/README.md)"),
        check("architecture", "hardware", m["architecture"], "x86_64 or aarch64",
              "ok" if m["architecture"] in ("x86_64", "aarch64", "arm64") else "limits",
              "the two the toolchain installer and the recorded results cover"),
        sized("memory", m["memory"], MIN_MEMORY, COMFORTABLE_MEMORY, gib,
              "a session's loop is capped at 3.5 GiB and a proof job at up to 4 GiB by default, side by side "
              "(verification/README.md).", "A job that asks for more than the runner's share is deferred, not run."),
        sized("cpus", m["cpus"], MIN_CPUS, COMFORTABLE_CPUS, lambda n: f"{n} CPUs",
              "a session, a build and a proof run at once, and anything on a JVM wants 2.",
              "Proofs run one at a time."),
        sized("disk", m["diskFree"], MIN_DISK, COMFORTABLE_DISK, gib,
              f"free space where the checkout is ({m['diskAt']}): the jvmcontract build, the JDKs and each target's "
              f"dependencies.", "A larger target's dependencies may not fit."),
    ]


def jdk_homes() -> dict[str, str]:
    """{feature: home} of the JDKs under sdkman, as examples/tools/targets/runtime_jdk.py finds them."""
    found = {}
    if JDK_CANDIDATES.is_dir():
        for entry in sorted(JDK_CANDIDATES.iterdir()):
            release = entry / "release"
            if entry.name == "current" or entry.is_symlink() or not (entry / "bin/java").is_file() or not release.is_file():
                continue
            m = re.search(r'^JAVA_VERSION="?([0-9._]+)', release.read_text(errors="replace"), re.M)
            if m:
                parts = m[1].split(".")
                feature = parts[1] if parts[0] == "1" and len(parts) > 1 else parts[0]
                key = (entry.name.endswith("-tem"), numbers(m[1]))  # a Temurin build first, then the newest
                if feature not in found or key > found[feature][0]:
                    found[feature] = (key, str(entry))
    return {feature: home for feature, (_, home) in found.items()}


def tools() -> list[dict]:
    checks = []

    def tool(id, found, wanted, level_when_missing, why, fix, ok=None):
        good = bool(found) if ok is None else ok
        checks.append(check(id, "tools", found or "not found", wanted, "ok" if good else level_when_missing, why, fix))

    python = sys.version_info
    tool("python3", platform.python_version(), "3.11 or later", "blocking",
         "every tool here is Python on the standard library; the pipeline reads its settings with tomllib",
         "install Python 3.11 or later", ok=python >= (3, 11))
    try:
        import importlib.metadata
        import jsonschema  # noqa: F401
        found = "jsonschema " + importlib.metadata.version("jsonschema")
    except Exception:
        found = None
    tool("jsonschema", found, "the Python module", "blocking",
         "a result that can't be checked against its schema is not published (examples/README.md)",
         "apt install python3-jsonschema, or pip install --user jsonschema")
    tool("git", out("git", "--version"), "any", "blocking", "targets are fetched by commit", "install git")
    tool("jj", out("jj", "--version"), "any recent", "blocking",
         "the checkout is a jj repository, and every commit and the job queue go through it",
         "examples/setup/ubuntu/install.sh devtools, or a release binary from github.com/jj-vcs/jj into ~/.local/bin")
    java = out("java", "-version")
    tool("java", java, "25 on PATH", "blocking", "the examples and the JBMC models are built for Java 25",
         "examples/setup/ubuntu/install.sh jvm (SDKMAN, Temurin 25 as the default)", ok=numbers(java)[:1] == (25,))
    tool("javac", out("javac", "-version"), "25 on PATH", "blocking", "adapters, drivers and source slices are compiled",
         "a JDK, not a JRE: examples/setup/ubuntu/install.sh jvm", ok=numbers(out("javac", "-version"))[:1] == (25,))
    homes = jdk_homes()
    tool("jdks", ", ".join(f"{f} ({Path(h).name})" for f, h in sorted(homes.items(), key=lambda kv: int(kv[0]))) or None,
         f"21 and 25 under {JDK_CANDIDATES}", "limits",
         "a target's controls run on each JDK its sidecar names, by its home under sdkman, 21 and 25 as a rule; "
         "without them a replay task can't run. A target built by its own build needs the JDK that build supports",
         "sdk install java <version>-tem for each", ok={"21", "25"} <= set(homes))
    cargo = out("cargo", "--version")
    tool("cargo", cargo, "Rust 1.82 or later", "blocking",
         "jvmcontract, the verifier, is built from lib/ on this machine",
         "examples/setup/ubuntu/install.sh devtools (rustup)", ok=numbers(cargo) >= (1, 82))
    tool("jbmc", out("jbmc", "--version"), "6.x", "limits",
         "the tool's own checker needs none, but a proof under the jbmc or auto engine does, and so does every "
         "obligation the own checker refuses", "the CBMC .deb from github.com/diffblue/cbmc (install.sh's system "
         "component; needs sudo)")
    tool("z3", out("z3", "--version"), "any", "limits",
         "a JBMC run that relates products its SAT solver can't (the same operands in another order, or under a "
         "condition) is proved by Z3 on JBMC's formula with congruence lemmas; without it such a run ends without "
         "a verdict at its time limit (lib/README.md, VF-018)",
         "apt install z3 (install.sh's system component), or a release from github.com/Z3Prover/z3 into ~/.local/bin")
    helped = ""
    if shutil.which("claude"):
        try:
            helped = subprocess.run(["claude", "--help"], capture_output=True, text=True, timeout=60).stdout
        except (OSError, subprocess.TimeoutExpired):
            pass
    flags = [f for f in ("--fork-session", "--session-id", "--autocompact", "--effort") if f not in helped]
    tool("claude", out("claude", "--version"), "Claude Code with --fork-session, --session-id, --autocompact and --effort",
         "blocking", "a run is a loop of headless sessions, which may start as a fork of this one (llm-dlc/tools/feature-loop.sh)",
         "update Claude Code" + (f": this one lacks {', '.join(flags)}" if helped and flags else ""),
         ok=bool(helped) and not flags)
    systemd = None
    if shutil.which("systemd-run"):
        try:
            probe = subprocess.run(["systemd-run", "--user", "--scope", "--quiet", "--collect", "-p", "MemoryMax=64M",
                                    "-p", "MemorySwapMax=0", "true"], capture_output=True, timeout=30)
            systemd = "user scopes work" if probe.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            pass
    tool("systemd", systemd, "systemd-run --user --scope", "limits",
         "the loop and every proof step run in a scope with a hard memory cap, so a proof that runs away is killed "
         "alone; without it nothing is capped (the runner's isolation `none`), and the loop will not start unless "
         "told to run uncapped", "on WSL: [boot] systemd=true in /etc/wsl.conf, then wsl --shutdown")
    tool("maven", out("mvn", "-v"), "any", "limits",
         "only a target prepared by its own Maven build (the upstream-build route) needs it",
         "examples/setup/ubuntu/install.sh jvm")
    tool("gh", out("gh", "--version"), "any, signed in", "limits",
         "only step 4, a pull request back to the repository, needs it", "install gh, then gh auth login")
    tool("tmux", out("tmux", "-V"), "any", "limits",
         "the loop outlives the session that started it when it runs in a tmux window; without it, it runs as a "
         "background task of that session", "install tmux")
    return checks


def budget(m: dict) -> dict:
    """The memory and CPUs shared out as verification/README.md describes: a reserve never handed out, one loop's
    cap, and the rest to the runner. Whole GiB, rounded down."""
    total, cpus = m["memory"] // GIB, m["cpus"]
    reserve = max(2, round(total * 0.12))
    loop = 12 if total >= 48 else 6 if total >= 24 else 3.5
    runner = max(0, int(total - reserve - loop))
    runner_cpus = max(1, cpus - (2 if cpus >= 8 else 1) - (2 if cpus >= 6 else 1))
    workers = max(1, min(runner_cpus // 2, runner // 4))
    return {"reserve": f"{reserve}G", "loopMemory": f"{loop:g}G",
            "runner": {"memory": f"{runner}G", "cpus": runner_cpus, "workers": workers,
                       "job_memory_max": f"{max(1, min(runner, max(4, runner // 2)))}G",
                       "build_memory": f"{max(2, min(8, runner // 4))}G"},
            "note": "FEATURE_LOOP_MEMORY_MAX for the loop, and [runner] in verification/pipeline.local.toml (not "
                    "committed) for the rest; nothing swaps, so the three must fit in the machine together"}


def assess() -> dict:
    m = machine()
    checks = hardware(m) + tools()
    return {"machine": m, "checks": checks, "budget": budget(m),
            "blocking": [c["id"] for c in checks if c["level"] == "blocking"],
            "limits": [c["id"] for c in checks if c["level"] == "limits"]}


def main(argv: list[str]) -> int:
    if argv not in ([], ["--json"]):
        print("usage: doctor.py [--json]", file=sys.stderr)
        return 2
    report = assess()
    if argv:
        print(json.dumps(report, indent=1))
    else:
        for group in ("hardware", "tools"):
            print(group)
            for c in (c for c in report["checks"] if c["group"] == group):
                print(f"  {c['level']:<8}  {c['id']:<12} {c['found']}" + ("" if c["level"] == "ok" else
                      f"\n            wanted: {c['wanted']}\n            {c['why']}" + (f"\n            fix: {c['fix']}" if c.get("fix") else "")))
        b, r = report["budget"], report["budget"]["runner"]
        print(f"budget\n  reserve {b['reserve']}, loop {b['loopMemory']}, runner {r['memory']} and {r['cpus']} CPUs "
              f"({r['workers']} workers, {r['job_memory_max']} a job at most)")
        print(f"{len(report['blocking'])} blocking, {len(report['limits'])} limiting"
              + (": " + ", ".join(report["blocking"]) if report["blocking"] else ""))
    return 1 if report["blocking"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
