"""Require the same upstream commits and caller source bytes as Run 6 before re-screening receivers."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXTERNAL = HERE.parent / "external-upgrades"
sys.path.insert(0, str(EXTERNAL))
from engineering import source_side, write


def restore(work, output):
    source = work / "sources"
    subprocess.run([sys.executable, EXTERNAL / "corpus_sources.py", source], check=True)
    repos = json.loads((source / "repos.json").read_text())
    corpus = json.loads((EXTERNAL / "corpus.json").read_text())["cases"]
    checked = {}
    for case in corpus:
        repo = Path(repos[case["id"]])
        checked[case["id"]] = {"sourceSha256": case["sourceSha256"],
            "revisions": {side: source_side(case, side, repo) for side in ("old", "new")}}
    write(output, {"cases": checked, "total": len(checked)})


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    restore(args.work, args.output)
