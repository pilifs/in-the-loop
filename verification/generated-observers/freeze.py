"""Freeze the deterministic producer and its policy before offering it any retrospective input."""
from pathlib import Path
import sys
import zipfile

import campaign
from targets import observer_generation, upgrade_replay

TRANSFER = ["J14", "09", "06", "466", "484"]


def freeze(destination):
    files = [p for p in (campaign.ROOT / "examples/tools/targets").glob("*.py") if not p.name.startswith("test_")]
    files += [observer_generation.observer_recipes.TEMPLATE, campaign.ROOT / "examples/tools/scaffold_example.py"]
    archive = destination / "operator-source.zip"
    campaign.pack(campaign.ROOT, files, archive)
    campaign.write(destination / "freeze.json", {"schema": "public-observer-transfer-freeze/v1",
        "development": ["458","445","J16","J19","io","J06","J10","J17"], "transfer": TRANSFER,
        "candidateBudget":observer_generation.observer_recipes.CANDIDATE_BUDGET,"model":None,
        "generator":observer_generation.identity(),"sourceArchiveSha256":upgrade_replay.sha(archive),
        "permitted":["ordered pinned production artifacts","JDK","changed selectors","supplied public entry",
                     "reviewed input meanings, fields, side bounds and assumptions","production public declarations"],
        "withheld":["historical callers and case-specific generator scripts","upstream tests","helper tables",
                    "actual outcomes and receipts","retrospective basis","evaluator predictions"],
        "operator":"fresh process under Landlock; evaluator sentinel read must fail",
        "interpretation":"Retrospective registrations were disclosed in the brief. Fresh PR-to-prediction discovery was not measured."})


if __name__=="__main__":
    freeze(Path(sys.argv[1]) if len(sys.argv)>1 else campaign.HERE)
