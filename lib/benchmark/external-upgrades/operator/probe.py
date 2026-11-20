"""Exercise the actual isolated tool surface with a synthetic, known-answer neutral packet."""

import argparse
import json
from pathlib import Path
import secrets

import isolation
import control

SYNTHETIC = Path(__file__).resolve().parent / "synthetic"


def packet(root):
    pair = root / "issued-pair"
    pair.mkdir()
    label = secrets.token_hex(16)
    data = {"case_id": "synthetic-only"}
    for side, body in [("old", "return n + 1;"), ("new", "return 1 + n;")]:
        base = pair / side
        directory = base / "src/main/java/neutral"
        directory.mkdir(parents=True)
        (directory / "Counter.java").write_text(
            "package neutral; public final class Counter { public static int increment(int n) { "
            + body
            + " } }\n"
        )
        (base / "pom.xml").write_text(
            "<project><modelVersion>4.0.0</modelVersion><groupId>neutral</groupId><artifactId>counter</artifactId><version>1.0</version></project>\n"
        )
        (base / "allowed-canary.txt").write_text(label)
        data[side] = {"tree_sha256": isolation.hashed(isolation.canonical(isolation.tree(base)))}
    (pair / "pair.json").write_bytes(isolation.canonical(data) + b"\n")
    return pair, label


def tool(product, case, argv):
    item = {"type": "function_call", "name": "case_command", "arguments": json.dumps({"argv": argv})}
    result = control.execute(product, case, item)
    if result["exit"]:
        raise ValueError(
            f"synthetic case command exited {result['exit']}: {result['output'][-1200:]}"
        )
    return result["output"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", required=True, type=Path)
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--native",
        action="store_true",
        help="run the one native synthetic equivalence under the repository probe cap",
    )
    parser.add_argument("--with-dependencies", action="store_true")
    args = parser.parse_args()
    root = args.scratch.resolve()
    root.mkdir(parents=True, exist_ok=False)
    pair, label = packet(root)
    case = root / "case"
    manifest = isolation.digest(pair / "pair.json")
    if args.with_dependencies:
        published = root / "released-dependencies"
        published.mkdir()
        asset = published / "sample.txt"
        asset.write_text("synthetic allowed dependency")
        (published / "withheld.txt").write_text("synthetic unlisted dependency")
        ordered = {
            "case_id": "synthetic-only",
            "artifacts": [{"side": "both", "path": asset.name, "sha256": isolation.digest(asset)}],
        }
        listing = published / "release.json"
        listing.write_text(json.dumps(ordered) + "\n")
        isolation.fresh_case(case, pair, manifest, listing, isolation.digest(listing))
    else:
        isolation.fresh_case(case, pair, manifest)
    # Host canaries are fresh synthetic files. Their locations are passed to the guest, their contents are not.
    outside = {}
    for name in (
        "sibling-packet",
        "curator-reference",
        "historical-transcript",
        "hidden-test",
        "knowledge-base",
        "prior-report",
    ):
        file = root / "outside" / name / "private.txt"
        file.parent.mkdir(parents=True)
        file.write_text(secrets.token_hex(24))
        outside[name] = str(file)
    outside.update(
        {
            "host-repository": str(isolation.REPO / "CLAUDE.md"),
            "host-docker": "/var/run/docker.sock",
            "host-config": "/home/operator/.codex/auth.json",
        }
    )
    check = json.loads(
        tool(
            args.product,
            case,
            [
                "python3",
                "-c",
                (SYNTHETIC / "guest_checks.py").read_text(),
                label,
                json.dumps(outside),
            ],
        )
    )
    if not (
        all(check["outsideBlocked"].values())
        and all(check["readOnly"].values())
        and all(v for k, v in check.items() if k not in ("outsideBlocked", "readOnly"))
    ):
        raise ValueError(json.dumps(check))
    version = tool(args.product, case, ["jvmcontract", "--version"]).strip()
    # The model can generate files only in this private case area. No curator-supplied property enters a scored packet.
    names = [
        "example.json",
        "target.json",
        "claims/preserve.json",
        "controls/oracle.py",
        "driver/Read.java",
    ]
    files = {name: (SYNTHETIC / name).read_text() for name in names}
    tool(
        args.product,
        case,
        ["python3", "-c", (SYNTHETIC / "setup_case.py").read_text(), json.dumps(files)],
    )
    proof = "/opt/product/examples/tools/build.py"
    plan = json.loads(
        tool(args.product, case, ["python3", proof, "--plan", "001", "--task", "preserve"])
    )[0]
    if not plan["executable"]:
        raise ValueError(f"neutral task failed to plan: {plan['notExecuted']}")
    show = tool(
        args.product,
        case,
        [
            "python3",
            "/opt/product/examples/tools/targets/workflow_handoff.py",
            "handoff",
            "001",
            "--markdown",
        ],
    )
    if "preserve" not in show:
        raise ValueError("V0 handoff missing synthetic task")
    # Compile/run both input sides inside the guest on the actual pinned JDK. The checker invocation itself is captured separately.
    jvm_observations = tool(args.product, case, ["python3", "-c", (SYNTHETIC / "jvm.py").read_text()])
    if json.loads(jvm_observations) != [42, 42]:
        raise ValueError("wrong JVM observations")
    other = root / "second-case"
    isolation.fresh_case(other, pair, manifest)
    fresh = (
        tool(
            args.product,
            other,
            [
                "python3",
                "-c",
                "from pathlib import Path;print(not Path('/case/work/positive-write').exists() and not any(Path('/opt/product/examples/001-case').iterdir()) and not any(Path('/case/work/cache').iterdir()))",
            ],
        ).strip()
        == "True"
    )
    if not fresh:
        raise ValueError("case storage or proof cache reused")
    pin = json.loads(isolation.PIN.read_text())
    result = {
        "schema": "external-upgrade-blind-synthetic/v1",
        "syntheticOnly": True,
        "revision": pin["revision"],
        "checkerSha256": pin["sha256"]["jvmcontract"],
        "checkerVersion": version,
        "rootSha256": isolation.digest(args.product / "manifest.json"),
        "neutralPacketSha256": manifest,
        "caseChecks": check,
        "freshSecondCase": fresh,
        "v0PlanExecutable": True,
        "v0Handoff": True,
        "jvmReturnValues": json.loads(jvm_observations),
        "liveModelInvocations": 0,
    }
    refused = []
    for name in ("web_search", "file_search", "host_shell", "collaboration"):
        try:
            control.classify({"type": "function_call", "name": name, "arguments": "{}"})
        except ValueError:
            refused.append(name)
    if len(refused) != 4:
        raise ValueError("unregistered tool accepted")
    result["rejectedUnregisteredTools"] = refused
    if args.with_dependencies:
        result["dependencyRelease"] = json.loads(
            tool(
                args.product, case, ["python3", "-c", (SYNTHETIC / "read_dependency.py").read_text()]
            )
        )
        if not all(result["dependencyRelease"].values()):
            raise ValueError("dependency release boundary failed")
    if args.native:
        result["nativeCommandOutput"] = tool(
            args.product, case, ["python3", proof, "001", "--task", "preserve"]
        ).strip()
        verdict = tool(
            args.product,
            case,
            [
                "python3",
                "-c",
                "import json,pathlib; p=next(pathlib.Path('/opt/product/examples/001-case/receipts/preserve').glob('*/result.json'));r=json.loads(p.read_bytes());print(json.dumps({'status':r['conclusion']['status'],'checker':r['attempt']['tools']['jvmcontract'],'engine':r['attempt']['engine']}))",
            ],
        )
        result["nativeVerification"] = json.loads(verdict)
        if result["nativeVerification"] != {
            "status": "established",
            "checker": pin["sha256"]["jvmcontract"],
            "engine": "native",
        }:
            raise ValueError("synthetic native receipt did not bind the expected V0 checker")
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
