"""Use the measured native-resume scheduler with its narrowly versioned stock-result extension."""

import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BASE = (HERE.parent / "claude-native-resume").resolve()
sys.path.insert(0, str(BASE))
import runner_core as core  # noqa: E402
import isolation  # noqa: E402
import identity  # noqa: E402
import observation  # noqa: E402

MODULE = importlib.util.spec_from_file_location("original_native_resume_case", BASE / "run_case.py")
original = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(original)


def shared():
    desc = core.json_file(HERE / "profile.json")
    base = BASE / "claude-native-resume.json"
    if isolation.digest(base) != desc["baseProfileSha256"]:
        raise ValueError("the frozen parent operator changed")
    for name, pin in desc["implementationSha256"].items():
        if isolation.digest(HERE / name) != pin:
            raise ValueError("the issued operator amendment differs")
    p = core.json_file(base)
    for name, pin in p["runnerSha256"].items():
        if isolation.digest(BASE / name) != pin:
            raise ValueError("the frozen base implementation differs")
    for name, key in (
        ("isolation.py", "caseBoundarySha256"),
        ("control.py", "caseCommandSha256"),
        ("mcp_server.py", "mcpSha256"),
    ):
        if isolation.digest(BASE.parent / name) != p["historicalGateSources"][key]:
            raise ValueError("the base guest boundary or case command differs")
    return {**p, "shadow": {**p["shadow"], "toolRootSha256": desc["shadowRootSha256"]}}


def main():
    effective = shared()
    identity.PROFILE = HERE / "profile.json"
    identity.DEFAULT_LAUNCH = HERE / "v0-launch.json"
    if sys.argv[1:2] == ["freeze-launch"]:
        parser = argparse.ArgumentParser()
        parser.add_argument("--build", required=True)
        parser.add_argument("--product", required=True, type=Path)
        parser.add_argument("--output", required=True, type=Path)
        args = parser.parse_args(sys.argv[2:])
        print(identity.make_launch(args.build, args.product, args.output))
        return 0
    if (
        "--scope-active" not in sys.argv
        and "--help" not in sys.argv
        and original.memory_cpu() != identity.CAPS
    ):
        return subprocess.run(
            [
                "systemd-run",
                "--user",
                "--scope",
                "-q",
                "-p",
                "CPUQuota=400%",
                "-p",
                "MemoryMax=16G",
                "-p",
                "MemorySwapMax=0",
                sys.executable,
                str(Path(__file__).resolve()),
                *sys.argv[1:],
                "--scope-active",
            ]
        ).returncode
    observation.hook()
    run = original.run

    def adapted(a, descriptor, profile_sha, resources):
        return run(a, effective, profile_sha, resources)

    original.run = adapted
    return original.main()


if __name__ == "__main__":
    raise SystemExit(main())
