"""Check the five linked native retries and three public reviews of the midnight witness in one collected job."""

import argparse
import json
import os
from pathlib import Path
import sys

FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER.parent / "tools"))
from targets.claim_history import recorded_evidence


def check(folder, job):
    _, journals = recorded_evidence(folder.parent.parent, folder)
    required = json.loads((folder / "milestones.json").read_text())["milestones"][0]["required"]
    expected_inputs = json.loads((folder / "records/midnight-witness.json").read_text())["inputs"]

    def attempt(task, strategy):
        matches = [(run, folder / path) for run, path in journals[task].values()
                   if run.get("job") == job and run["strategy"]["engine"] == strategy]
        if len(matches) != 1:
            raise ValueError(f"{task} has {len(matches)} {strategy} executions in {job}")
        return matches[0]

    for claim in required:
        task = claim["task"]
        run, path = attempt(task, "native")
        old = journals[task][run["retryOf"]][0]
        if (run["claimKey"] != claim["claimKey"] or run["revisions"] != claim["revisions"]
                or run["bindingId"] != old["bindingId"] or run["retryBinding"] != old["bindingId"]
                or run["claimKey"] != old["claimKey"] or run["revisions"] != old["revisions"]
                or run["budget"] != old["budget"] or old["strategy"] != run["strategy"]
                or run["lastCompletedStage"] != "receipt-published"):
            raise ValueError(f"{task} did not retry the same frozen obligation and budget")
        result, = json.loads((path.parent / run["checkerEvidence"]).read_text())["outcomes"]
        gaps = result["search"]["gaps"]
        if (run["strategy"]["gaps"] != "strict" or result["verdict"] != "unverifiable" or len(gaps) != 1
                or gaps[0]["call"] != "java.util.ServiceLoader.load(java.lang.Class)"
                or not all(s.endswith("org.threeten.bp.chrono.Chronology.<clinit>:148") for s in gaps[0]["sites"])
                or not gaps[0]["sites"]):
            raise ValueError(f"{task} reached a different strict outcome: {result.get('problem') or result['verdict']}")
        print(f"{task}: {old['id']} -> {run['id']}, {gaps[0]['call']} in {gaps[0]['sites'][0]}")

    for task, revision, value in [("clock-parent", "parent", 1), ("clock-fix", "fix", 0), ("same-day", "parent", None)]:
        run, path = attempt(task, "jvm")
        replay = json.loads((path.parent / run["replayEvidence"]).read_text())
        side = replay["sides"][revision]
        comparisons = json.loads((path.parent / "correspondence.json").read_text())
        if (replay["inputs"] != expected_inputs or replay["claimKey"] != run["claimKey"]
                or replay["entry"] != "civil.Hours#completeHours(II)J"
                or {c["revision"] for c in comparisons} != set(run["revisions"])
                or any(c["cases"] != 36864 or c["disagreements"] != 0 for c in comparisons)):
            raise ValueError(f"{task} lacks the pinned input or complete adapter correspondence")
        if value is None:
            if side["admitted"] or not replay["reason"].startswith("domain mismatch:"):
                raise ValueError("the midnight witness entered the same-day domain")
        elif not side["admitted"] or side["values"] != [value, None] or side["satisfies"] != (value == 0):
            raise ValueError(f"{task} returned different JVM observations")
        if replay["reproduced"] != (task == "clock-parent"):
            raise ValueError(f"{task} gave the wrong witness disposition")
        print(f"{task}: {run['id']}, {run['status']}, {side.get('values', 'outside the domain')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", default=os.getenv("VERIFY_JOB_ID"), required=not os.getenv("VERIFY_JOB_ID"))
    check(FOLDER, parser.parse_args().job)
