"""Bind the shared operator and experimental environment independently of each tested product."""

import argparse
import json
from pathlib import Path
import platform
import re
import shutil

import runner_core as core
import isolation

HERE = Path(__file__).resolve().parent
PROFILE = HERE / "claude-native-resume.json"
DEFAULT_LAUNCH = HERE / "v0-launch.json"
CAPS = {"cpu": 4, "memoryBytes": 16 * 1024**3, "swapBytes": 0}
PRODUCT_TOOLS = {"usr/bin/jbmc", "usr/bin/jvmcontract", "usr/bin/z3"}


def product_owned(name):
    return (
        name == "opt/product-pin.json"
        or name.startswith(("opt/product/", "opt/solver/"))
        or name in PRODUCT_TOOLS
        or re.fullmatch(r"lib/x86_64-linux-gnu/libbitwuzla[^/]*", name) is not None
    )


def environment(manifest, resources):
    tool = Path(shutil.which("bwrap")).resolve()
    return {
        "schema": "external-upgrade-matched-environment/v1",
        "kernel": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "bubblewrapSha256": isolation.digest(tool),
        "namespaceImplementationSha256": isolation.digest(HERE.parent / "isolation.py"),
        "resourceLimits": {**resources, "cpu": float(resources["cpu"])},
        "guestTemporaryDirectory": "/case/work/tmp",
        "guestFiles": {k: v for k, v in manifest.items() if not product_owned(k)},
    }


def inspect_root(product, resources):
    manifest = json.loads((product / "manifest.json").read_bytes())
    actual = isolation.tree(product / "root")
    if (product / "manifest.json").read_bytes() != isolation.canonical(actual) or actual != manifest:
        raise ValueError("staged product differs from its complete frozen manifest")
    engine = product / "root/opt/product-pin.json"
    pin = core.json_file(engine)
    checked = manifest["usr/bin/jvmcontract"]["sha256"]
    if pin["sha256"]["jvmcontract"] != checked:
        raise ValueError("checker does not match the embedded product lock")
    env = environment(manifest, resources)
    return {
        "product_sha256": isolation.digest(engine),
        "staged_root_sha256": isolation.digest(product / "manifest.json"),
        "environment_sha256": isolation.hashed(isolation.canonical(env)),
        "revision": pin["revision"],
        "checker_sha256": checked,
        "source_manifest_sha256": pin["sourceManifestSha256"],
    }, env


def make_launch(build, product, output):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", build):
        raise ValueError("invalid build label")
    actual, _ = inspect_root(product, CAPS)
    if build == "V0" and actual["product_sha256"] != isolation.digest(HERE.parents[1] / "v0.json"):
        raise ValueError("V0 must use the existing frozen v0.json bytes")
    doc = {
        "schema": "external-upgrade-product-launch/v1",
        "build": build,
        "profile_sha256": isolation.digest(PROFILE),
        **actual,
    }
    if not core.exclusive(output, core.bytes_of(doc)):
        raise ValueError("the destination already contains a launch lock")
    return isolation.digest(output)


def load_launch(path, trusted_sha, profile_sha):
    if path.resolve() != DEFAULT_LAUNCH.resolve() and not trusted_sha:
        raise ValueError("an external build launch requires its independently issued --launch-sha256")
    digest = isolation.digest(path)
    if trusted_sha and digest != trusted_sha:
        raise ValueError("the build launch changed after release")
    doc = core.json_file(path)
    if (
        doc.get("schema") != "external-upgrade-product-launch/v1"
        or doc.get("profile_sha256") != profile_sha
        or not isinstance(doc.get("build"), str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", doc["build"])
    ):
        raise ValueError("the launch lock does not bind this operator profile and build")
    for key in (
        "product_sha256",
        "staged_root_sha256",
        "environment_sha256",
        "checker_sha256",
        "source_manifest_sha256",
    ):
        if not re.fullmatch(r"[0-9a-f]{64}", doc.get(key, "")):
            raise ValueError("incomplete frozen build identity")
    if doc["build"] == "V0" and doc["product_sha256"] != isolation.digest(
        HERE.parents[1] / "v0.json"
    ):
        raise ValueError("the V0 launch does not bind the original engine lock")
    return doc, digest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True)
    parser.add_argument("--product", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(make_launch(args.build, args.product, args.output))
