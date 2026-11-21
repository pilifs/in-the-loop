"""Synthetic scheduler/scorecard integration. No account, proof, source fetch or live model is used."""

import argparse
import json
import os
from pathlib import Path
import shutil
import time
from types import SimpleNamespace
from unittest.mock import patch

import reporting
import resume_meter
import run_case as worker
import runner_core as core
import isolation
import identity
import probe  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--product", required=True, type=Path)
    parser.add_argument("--shadow-product", required=True, type=Path)
    args = parser.parse_args()
    root = args.scratch.resolve()
    root.mkdir(parents=True, exist_ok=False)
    pair, _ = probe.packet(root)
    profile = core.json_file(identity.PROFILE)
    pin = isolation.digest(identity.PROFILE)
    resources = {"cpu": 4, "memoryBytes": 16 * 1024**3, "swapBytes": 0}
    mono = time.time()
    results = {}
    assert isolation.canonical(identity.environment({}, resources)) == isolation.canonical(
        identity.environment({}, {**resources, "cpu": 4.0})
    )

    def make(label, age=0, origin=False):
        return SimpleNamespace(
            case_id=None,
            release=pair,
            pair_sha256=isolation.digest(pair / "pair.json"),
            product=args.product.resolve(),
            shadow_product=args.shadow_product.resolve(),
            launch_lock=identity.DEFAULT_LAUNCH,
            launch_sha256=None,
            cohort="disclosed",
            dependencies=None,
            dependency_sha256=None,
            case_dir=root / label,
            reports=root / (label + "-reports"),
            received_at=core.utc(mono - age),
            human_minutes=0,
            assisted_local_source_bridge=False,
            github="https://github.com/example/neutral" if origin else None,
            before="1" * 40 if origin else None,
            after="2" * 40 if origin else None,
            claude=Path(shutil.which("claude")).resolve(),
        )

    for label, age, expected in [
        ("unsupported", 0, "original-intake"),
        ("expired", 7300, "time-budget"),
    ]:
        a = make(label, age)
        first = worker.run(a, profile, pin, resources)
        assert (
            first["disposition"] == expected
            and first["route"] == "unavailable"
            and first["profile_sha256"] == pin
            and first["product_sha256"] == core.json_file(identity.DEFAULT_LAUNCH)["product_sha256"]
            and first["environment_verified"]
            and first["environment_sha256"] != first["staged_root_sha256"]
            and first["launch_lock_sha256"] == isolation.digest(identity.DEFAULT_LAUNCH)
        )
        firstsha = reporting.store(a.case_dir / "first-report.json", a.reports)
        again = worker.run(a, profile, pin, resources)
        assert (
            again == first
            and reporting.store(a.case_dir / "first-report.json", a.reports) == firstsha
        )
        assert reporting.scorecard.check_operator(first) >= age
        results[label] = expected
    # This scripted stage double only tests role separation, ordering and the durable controller. The archive carries a separate real V0 proof.
    a = make("four-stages", age=915, origin=True)
    seen = []
    proposal = {
        "schema": "prove-plan/v1",
        "request": "public synthetic task",
        "order": ["001"],
        "examples": [
            {
                "id": "001",
                "review": "designed",
                "entry": {"target": "neutral.Counter#increment", "invocation": "route"},
                "controls": {"positive": [], "negative": [], "mutation": []},
                "validation": [],
                "done": [],
                "property": "integer increment",
            }
        ],
    }

    def stages(stage, case, params, ledger, prof, origin, note, validate):
        seen.append(stage)
        ledger.phase(stage)
        work = case / "work"
        if stage == "plan":
            result = proposal
            (work / "planner-notes").write_text("private current-case notes")
        elif stage == "review":
            assert (
                not (work / "planner-notes").exists()
                and json.loads((work / "plan.json").read_text()) == proposal
            )
            result = {"decision": "approve", "reason": "synthetic test"}
        elif stage == "setup":
            assert (work / "planner-notes").exists() and (work / "review.json").is_file()
            result = {"tasks": ["toy"], "subjectJdk": "21"}
        else:
            return (
                "Upgrade synthetic\nCaller-visible behavior value returned\nResult Open. Synthetic test.\nScope one synthetic case\nReview action inspect original inputs.",
                "",
            )
        text = json.dumps(result)
        return validate(text), text

    def write(_product, case, path, text, _ledger):
        dest = case / "work" / Path(path).name
        dest.write_text(text)

    with (
        patch.object(worker, "role_stage", stages),
        patch.object(worker, "qualified_tasks", return_value=[]),
        patch.object(worker, "write_inside", write),
        patch.object(worker, "read_inside", return_value=""),
    ):
        four = worker.run(a, profile, pin, resources)
    assert seen == ["plan", "review", "setup", "proof"], (seen, four["maintainer_report"])
    assert four["checkpoint"]["stage"] == "queued" and four["checkpoint_15m"].startswith(
        "At 15 minutes"
    )
    reporting.scorecard.check_operator(four)
    results["independentStages"] = seen
    results["lateCheckpoint"] = four["checkpoint"]["stage"]
    # Metering honors native cache creation and output (including reasoning); reads are tracked separately. Unknown requests remain reserved on recovery.
    a = make("reserve")
    data = {
        "receivedAt": a.received_at,
        "case_id": "synthetic-only",
        "humanMinutes": 0,
        "pairSha256": a.pair_sha256,
    }
    ledger = core.Ledger(a.case_dir, data, profile, pin)
    try:
        charge = resume_meter.reserve(ledger, {"wireBytes": 1000})
        ledger.settle(
            {
                "stage": "plan",
                "tokens": {
                    "input_tokens": 3,
                    "cache_creation_input_tokens": 4,
                    "cache_read_input_tokens": 100,
                    "output_tokens": 5,
                },
                "estimatedUsd": 0.01,
                "seconds": 0,
            }
        )
        assert ledger.data["chargedTokens"] == 12 and ledger.data["cachedInputTokens"] == 100
        ledger.data["chargedTokens"] = 249999
        try:
            resume_meter.reserve(ledger, {"wireBytes": 1000})
        except core.Stopped as e:
            assert e.code == "token-budget"
        else:
            raise AssertionError("unaffordable request admitted")
        ledger.data["chargedTokens"] = 12
        actual = {}
        for stage in ("plan", "review", "setup", "proof"):
            role_case = root / ("reviewer-0" if stage == "review" else "subject")
            selected = profile["roles"][stage]["model"]
            state, ident, prior = resume_meter.binding(ledger, stage, role_case, selected)
            actual[stage] = ident
            assert state.stat().st_mode & 0o777 == 0o700 and prior is None
            assert resume_meter.binding(ledger, stage, role_case, selected)[1] == ident
        assert len(set(actual.values())) == 4
        results["nativeRoleIdentitiesDistinct"] = True
        results["tokenCeiling"] = 250000
        results["oneRequestReservation"] = charge
    finally:
        ledger.close()
    # A synthetic second build changes the product lock and workflow only. Its operator and measured OS/JDK must compare equal.
    alt = root / "synthetic-second-build"
    shutil.copytree(args.product / "root", alt / "root", symlinks=True, copy_function=os.link)
    engine = alt / "root/opt/product-pin.json"
    updated = core.json_file(engine)
    updated["revision"] = "c" * 40
    core.atomic(engine, updated)
    runtime = alt / "root/opt/product/llm-dlc/runtime.md"
    old = runtime.read_bytes()
    runtime.unlink()
    runtime.write_bytes(old + b"\nSynthetic product-only test revision.\n")
    manifest = isolation.tree(alt / "root")
    (alt / "manifest.json").write_bytes(isolation.canonical(manifest))
    alt_lock = root / "synthetic-launch.json"
    alt_sha = identity.make_launch("V1-Synthetic", alt, alt_lock)
    a = make("different-build")
    a.product, a.launch_lock, a.launch_sha256 = alt, alt_lock, alt_sha
    other = worker.run(a, profile, pin, resources)
    assert other["environment_verified"] and other["build"] == "V1-Synthetic"
    assert all(other[k] == four[k] for k in ("profile_sha256", "environment_sha256"))
    assert all(
        other[k] != four[k] for k in ("launch_lock_sha256", "product_sha256", "staged_root_sha256")
    )
    assert other["disposition"] == "original-intake" and other["output_tokens"] == 0
    reporting.store(a.case_dir / "first-report.json", a.reports)
    for changed in ("opt/jdks/21-tem/bin/java", "usr/bin/python3"):
        modified = dict(manifest)
        modified[changed] = {**manifest[changed], "sha256": "0" * 64}
        assert (
            isolation.hashed(isolation.canonical(identity.environment(modified, resources)))
            != other["environment_sha256"]
        )
    assert (
        isolation.hashed(isolation.canonical(identity.environment(manifest, {**resources, "cpu": 3})))
        != other["environment_sha256"]
    )
    results["matchedBuildComparison"] = {
        "same": ["profile_sha256", "environment_sha256"],
        "different": ["product_sha256", "launch_lock_sha256", "staged_root_sha256"],
        "jdkOsAndResourceDriftDetected": True,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
