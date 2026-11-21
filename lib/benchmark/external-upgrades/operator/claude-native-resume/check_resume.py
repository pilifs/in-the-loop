"""Uncredentialed native continuation checks using only the explicitly named synthetic role-state directory."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from signals import signal as visible_signal
import runner_core as core
import resume_meter as meter
import isolation


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--fixture-state",
        type=Path,
        required=True,
        help="fresh disclosed synthetic qualification output only",
    )
    p.add_argument("--shadow-product", required=True, type=Path)
    p.add_argument("--scratch", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    root = a.scratch.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    receipt = {}
    opts = core.json_file(core.HERE.parent / "claude-alternate/v0-claude.json")["explicitSettings"]
    f = a.fixture_state.resolve()
    assert core.json_file(f / "issued-pair/pair.json")["case_id"] == "synthetic-only"
    for model in ["claude-fable-5-2", "claude-opus-5-5"]:
        state = f / model / "private-role-state"
        files = list((state / "projects").glob("*/*.jsonl"))
        assert len(files) == 1
        tr = files[0]
        sid = tr.stem
        observed = core.json_file(f / model / "case/work/model-tool-result.json")
        assert observed["old"] == observed["new"] == 42 and observed["case_id"] == "synthetic-only"
        binding = {
            "transcriptSha256": isolation.digest(tr),
            "lastVisibleBlockSha256": visible_signal(json.dumps(observed)),
        }
        budget = SimpleNamespace(
            root=root / model,
            shadow_product=a.shadow_product.resolve(),
            profile={"oneRequest": {"maxOutputTokens": 2048}, "explicitSettings": opts},
            require_time=lambda: None,
            left=lambda: 60,
        )
        budget.root.mkdir()
        item = meter.measure(
            budget,
            model,
            state,
            sid,
            binding,
            "Continue the same disclosed synthetic role. Return the result from the earlier case tool.",
        )
        assert (
            item["priorAssistantMessages"] >= 2
            and item["priorSignalRestored"]
            and item["sourceTranscriptSha256"] == binding["transcriptSha256"]
        )
        receipt[model] = item
    a.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: {
                    "previousResultBound": v["priorSignalRestored"],
                    "wireBytes": v["wireBytes"],
                    "priorMessages": v["priorAssistantMessages"],
                }
                for k, v in receipt.items()
            }
        )
    )


if __name__ == "__main__":
    main()
