"""Record or check the toolchain used by an external-upgrade product run."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
PINNED_PATHS = (
    "lib/Cargo.lock", "lib/Cargo.toml", "lib/src", "lib/models", "lib/solvers",
    "examples/tools", "examples/schema", "llm-dlc/runtime.md", "llm-dlc/tools",
    "llm-dlc/prove-plan-template.md", "llm-dlc/prove-plan.schema.json",
    ".agents/skills/prove-java-change", ".claude/skills/prove-java-change",
)
PROMPT = (
    "Identify which behavior of this application could change for its caller. Check the most "
    "consequential preservation or change claim you can justify with the pinned verifier. "
    "Record the result as open at the first unsupported operation."
)


def output(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_manifest(revision):
    listing = subprocess.check_output(["git", "ls-tree", "-rz", revision, "--", *PINNED_PATHS], cwd=ROOT)
    entries = {}
    for record in listing.split(b"\0"):
        if record:
            header, path = record.split(b"\t", 1)
            mode, kind, blob = header.decode().split()
            if kind != "blob":
                raise ValueError("unexpected non-file product entry " + path.decode())
            entries[path.decode()] = [mode, blob]
    return (json.dumps({"revision": revision, "files": entries}, separators=(",", ":")) + "\n").encode()


def snapshot(args, revision):
    revision = output("git", "rev-parse", "--verify", f"{revision}^{{commit}}")
    changed = output("git", "diff", "--name-only", revision, "--", *PINNED_PATHS)
    extra = output("git", "ls-files", "--others", "--exclude-standard", "--", *PINNED_PATHS)
    if changed or extra:
        raise ValueError("product inputs differ from the revision: " + ", ".join((changed + "\n" + extra).split()))
    objects = {name: output("git", "rev-parse", f"{revision}:{name}") for name in PINNED_PATHS}
    binaries = {"jvmcontract": args.checker, "jbmc": shutil.which("jbmc"), "z3": shutil.which("z3")}
    binaries.update({name: args.jdk / name for name in ("release", "bin/java", "bin/javac",
                                                        "lib/server/libjvm.so", "lib/modules")})
    bitwuzla = args.bitwuzla / "lib/x86_64-linux-gnu"
    for so in ("libbitwuzla.so.0", "libbitwuzlabv.so", "libbitwuzlabb.so", "libbitwuzlals.so"):
        binaries[so] = bitwuzla / so
    if any(value is None for value in binaries.values()):
        raise ValueError("jbmc and z3 are required on PATH")
    return {
        "schema": "external-upgrade-product/v1", "revision": revision, "gitObjects": objects,
        "sourceManifestSha256": hashlib.sha256(source_manifest(revision)).hexdigest(),
        "sha256": {name: digest(path) for name, path in binaries.items()},
        "architecture": platform.machine(),
        "build": ["cargo", "build", "--offline", "--locked", "--manifest-path", "lib/Cargo.toml",
                  "--profile", "test-fast", "--bin", "jvmcontract"],
        "rustc": output("rustc", "--version"), "cargo": output("cargo", "--version"),
        "checkerVersion": output(str(args.checker), "--version"),
        "jbmcVersion": output("jbmc", "--version"), "z3Version": output("z3", "--version"),
        "plannerAndProver": {"model": "gpt-6.2-astra", "effort": "high"},
        "preparation": {"model": "gpt-6.2-sol", "effort": "high"},
        "neutralPrompt": PROMPT, "promptSha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "native": {"engine": "native", "gaps": "strict", "solver": "bitwuzla-words"},
        "workflow": ["llm-dlc/runtime.md", "python3 examples/tools/build.py --plan NNN --task TASK",
                     "python3 examples/tools/build.py NNN --task TASK",
                     "python3 examples/tools/targets/workflow_handoff.py handoff NNN --markdown",
                     "python3 verification/pipeline.py report --format json"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--record", metavar="REV")
    action.add_argument("--check", type=Path, metavar="LOCK")
    parser.add_argument("--checker", type=Path, default=ROOT / "lib/target/test-fast/jvmcontract")
    parser.add_argument("--jdk", type=Path, default=Path(os.environ.get(
        "JVMCONTRACT_VERIFIER_JDK", Path.home() / ".sdkman/candidates/java/21.0.13.0+9-tem")))
    parser.add_argument("--bitwuzla", type=Path, default=Path.home() / "tools/bitwuzla/current")
    args = parser.parse_args()
    try:
        recorded = json.loads(args.check.read_text()) if args.check else None
        actual = snapshot(args, recorded["revision"] if args.check else args.record)
        if recorded is None:
            print(json.dumps(actual, indent=2))
        elif recorded != actual:
            different = sorted(key for key in recorded.keys() | actual.keys() if recorded.get(key) != actual.get(key))
            raise ValueError("product lock differs in " + ", ".join(different))
        else:
            print(f"Verified product {actual['revision']} and {len(actual['sha256'])} tool and JDK digests")
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
