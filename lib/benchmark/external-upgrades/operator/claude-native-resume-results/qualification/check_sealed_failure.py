"""Collect a real failed native shadow with a generated wrong tool ID, using no authenticated model."""

import argparse
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
AMENDMENT = HERE.parent
BASE = (AMENDMENT.parent / "claude-native-resume").resolve()
sys.path[:0] = [str(AMENDMENT), str(BASE)]
import launch  # noqa: E402
import runner_core as core  # noqa: E402
import resume_meter as meter  # noqa: E402
import identity  # noqa: E402
import native_result  # noqa: E402
import observation  # noqa: E402
import reporting  # noqa: E402
import isolation  # noqa: E402
import probe  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("stock-fixture", "product", "amended-shadow", "scratch"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    assert launch.original.memory_cpu() == identity.CAPS
    root = a.scratch.resolve()
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    pair, _ = probe.packet(root)
    args = SimpleNamespace(
        release=pair,
        case_id=None,
        pair_sha256=isolation.digest(pair / "pair.json"),
        dependencies=None,
        dependency_sha256=None,
        case_dir=root / "private",
        reports=root / "firsts",
        cohort="disclosed",
        received_at=core.utc(time.time()),
        human_minutes=0,
        assisted_local_source_bridge=False,
        github="https://github.com/example/public-synthetic",
        before="a" * 40,
        after="b" * 40,
        product=a.product.resolve(),
        shadow_product=a.amended_shadow.resolve(),
        launch_lock=AMENDMENT / "v0-launch.json",
        launch_sha256=isolation.digest(AMENDMENT / "v0-launch.json"),
        claude=Path(shutil.which("claude")).resolve(),
    )
    origin = a.stock_fixture.resolve()
    assert (
        core.json_file(origin / "synthetic.json")["shape"] == "control"
        and core.json_file(origin / "synthetic.json")["model"] == "claude-fable-5-2"
    )
    old_state = origin / "state"
    source = next((old_state / "projects").glob("*/*.jsonl"))
    session = source.stem
    seed_copy = meter.copy_current

    def wrong_tool_id(stage, case, params, ledger, profile, base, note, validator):
        assert stage == "plan"
        ledger.phase(stage)
        target = ledger.root / "synthetic-role/config"
        seed_copy(source, old_state, session, target)
        correct_id = native_result.digest(b"toolu_public_2_2")
        bound = {
            "lastToolResultIdSha256": correct_id,
            "trustedToolIdSha256": correct_id,
            "outcomeSha256": "a" * 64,
            "lastVisibleBlockSha256": "b" * 64,
            "transcriptSha256": isolation.digest(meter.transcript(target, session)),
        }
        core.atomic(target.parent / "last-request.json", bound)
        wrong = {**bound, "lastToolResultIdSha256": "0" * 64}
        meter.measure(
            ledger, "claude-fable-5-2", target, session, wrong, "Continue this public synthetic case."
        )
        raise AssertionError("invalid tool ID passed")

    pin = isolation.digest(AMENDMENT / "profile.json")
    profile = launch.shared()
    identity.DEFAULT_LAUNCH = args.launch_lock
    observation.hook()
    with patch.object(launch.original, "role_stage", wrong_tool_id):
        doc = launch.original.run(args, profile, pin, launch.original.memory_cpu())
    assert (
        doc["disposition"] == "shadow-meter" and doc["output_tokens"] == 0 and doc["compute_usd"] == 0
    )
    seal = reporting.store(args.case_dir / "first-report.json", args.reports)
    final = args.reports / "V0" / doc["case_id"]
    item = next(e for e in doc["evidence"] if e["file"] == "last-restore-check.json")
    file = reporting.scorecard.evidence_file(final / "evidence", item)
    retained = json.loads(file.read_bytes())
    assert (
        retained == doc["terminal_shadow"]
        and retained["priorToolResultIdRestored"] is False
        and retained["accepted"] is False
        and retained["stop"] == "shadow-meter"
    )
    assert set(retained) <= set(observation.FLAGS) | {"accepted", "next_request", "stop"}
    assert (
        retained["sessionMatched"]
        and retained["fakeKeyOnly"]
        and retained["model"] == "claude-fable-5-2"
        and retained["effort"] == "high"
    )
    print(
        json.dumps(
            {
                "setup": "generated public history, deliberately wrong tool ID, actual CGroup and credentialless stock request, no payable request",
                "reportSha256": seal,
                "retainedFlagsSha256": isolation.digest(file),
                "retainedFlags": retained,
                "profileSha256": pin,
                "launchLockSha256": args.launch_sha256,
                "paidUsd": doc["compute_usd"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
