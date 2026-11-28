#!/usr/bin/env python3
"""Tests of jobs/script_inventory.py, and of the inventory it wrote (verification/scripts.json).

  python3 jobs/test_script_inventory.py

The two controls the cleanup must not break are read from the repository as it is: every script of
verification/triage/ is run by a committed job, and the merged-PR qualification test loads the campaign's own
audit.py and qualify.py by putting their folder on the import path.
"""

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import script_inventory as inventory  # noqa: E402

sys.path.append(str(ROOT / "lib/tools"))
from cost_tier import cost  # noqa: E402


class TheInventoryAsCommitted(unittest.TestCase):
    def test_every_script_under_verification_has_a_row_and_no_row_is_of_a_script_that_is_gone(self):
        listed = {row["script"] for row in json.loads((ROOT / "verification/scripts.json").read_text())["scripts"]}
        there = set(inventory.scripts(inventory.tracked(ROOT)))
        self.assertEqual(there, listed, "a script was added or removed under verification/: run `python3 jobs/script_inventory.py --write`, "
                                        "read its row, and commit verification/scripts.md and verification/scripts.json with the change")

    def test_every_row_has_one_of_the_classes_and_the_totals_add_up(self):
        document = json.loads((ROOT / "verification/scripts.json").read_text())
        self.assertEqual({row["class"] for row in document["scripts"]} - set(inventory.CLASSES), set())
        self.assertEqual((document["totals"]["unit"], sum(document["totals"]["byClass"].values())), ("scripts", document["totals"]["of"]))


class TheTwoControls(unittest.TestCase):
    def test_every_script_of_the_triage_folder_is_run_by_a_committed_job(self):
        names = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "verification/triage").glob("*.sh"))
        self.assertEqual(len(names), 5)
        ran = inventory.job_callers(ROOT, names)
        self.assertEqual([name for name in names if not ran[name]], [])
        # A script whose only callers are committed jobs stays where their commands find it: it is not an orphan.
        self.assertEqual(inventory.classify(names[0], ran[names[0]], {"tests": [], "code": [], "pages": [], "records": []})[0], "historical-only tool")
        # And that is what the committed inventory says of each, or better.
        rows = {row["script"]: row for row in json.loads((ROOT / "verification/scripts.json").read_text())["scripts"]}
        self.assertEqual([name for name in names if rows[name]["class"] == "orphan candidate" or not rows[name]["jobs"]], [])

    def test_a_test_that_puts_a_campaigns_folder_on_the_import_path_is_a_caller_of_what_it_imports(self):
        names = ["verification/merged-pr-links/audit.py", "verification/merged-pr-links/qualify.py"]
        callers = inventory.text_callers(ROOT, ["verification/test_merged_pr_qualification.py"], names)
        for name in names:
            self.assertEqual(callers[name]["tests"], ["verification/test_merged_pr_qualification.py"], name)
            self.assertEqual(inventory.classify(name, [], callers[name])[0], "supported campaign replay")


class AClass(unittest.TestCase):
    def test_follows_from_who_calls(self):
        none = {"tests": [], "code": [], "pages": [], "records": []}
        self.assertEqual(inventory.classify("verification/x/tool.py", [], none)[0], "orphan candidate")
        self.assertEqual(inventory.classify("verification/x/tool.py", [], {**none, "pages": ["verification/x/README.md"]})[0], "supported campaign replay")
        # A run's record shows the script was used and keeps nothing usable: historical, never supported.
        for record in ("verification/findings.md", "llm-dlc/loops/some-brief-results.md"):
            kind, why = inventory.classify("verification/x/tool.py", [], {**none, "records": [record]})
            self.assertEqual((kind, "record" in why), ("historical-only tool", True), record)
        ran = [{"job": "20260101-000000-j", "status": "passed", "sourceCommit": "abc"}]
        self.assertEqual(inventory.classify("verification/x/tool.py", ran, none)[0], "historical-only tool")
        self.assertEqual(inventory.replay_check(ran, none), {"kind": "job", "by": "20260101-000000-j", "at": "abc"})
        self.assertEqual(inventory.replay_check(ran, {**none, "tests": ["verification/x/test_tool.py"]})["kind"], "test")
        self.assertEqual(inventory.replay_check([{**ran[0], "status": "failed"}], none)["kind"], "none")
        self.assertEqual(inventory.classify("verification/x/test_tool.py", [], none)[0], "test")
        self.assertEqual(inventory.classify("verification/pipeline.py", [], none)[0], "compatibility entry point")
        self.assertEqual(inventory.classify("verification/layout.py", [], none)[0], "shared runner code")

    def test_is_no_stronger_than_the_callers_that_give_it(self):
        row = lambda script, kind="supported campaign replay", **more: {
            "script": script, "class": kind, "why": "", "jobs": 0, "tests": [], "code": [], "pagesCount": 0, "recordsCount": 0, **more}
        rows = inventory.settle([
            row("v/used.py", pagesCount=1), row("v/helper.py", code=["v/used.py"]), row("v/deep.py", code=["v/helper.py"]),
            row("v/outside.py", code=["examples/tools/build.py"]),
            row("v/old.py", "historical-only tool", jobs=2), row("v/old_helper.py", code=["v/old.py"]), row("v/old_ran.py", code=["v/old.py"], jobs=1),
            row("v/lost.py", "orphan candidate"), row("v/lost_helper.py", code=["v/lost.py"]),
            row("v/ring_a.py", code=["v/ring_b.py"]), row("v/ring_b.py", code=["v/ring_a.py"]),
        ])
        self.assertEqual({r["script"][2:-3]: r["class"].split()[0] for r in rows}, {
            "used": "supported", "helper": "supported", "deep": "supported", "outside": "supported",
            "old": "historical-only", "old_helper": "historical-only", "old_ran": "historical-only",
            "lost": "orphan", "lost_helper": "orphan", "ring_a": "orphan", "ring_b": "orphan"})
        why = {r["script"][2:-3]: r["why"] for r in rows}
        self.assertEqual((why["old_helper"], why["lost_helper"]), ("nothing but historical tools call it: it stays with them", "only orphan candidates call it"))
        self.assertIn("committed jobs ran it", why["old_ran"])

    def test_a_page_names_a_script_on_one_line_and_a_program_may_build_its_path_from_parts(self):
        names = ["verification/x/audit.py", "verification/y/audit.py"]
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write = lambda path, text: ((root / path).parent.mkdir(parents=True, exist_ok=True), (root / path).write_text(text))
            write("docs/far.md", "The campaign x is described here.\n\nElsewhere, some audit.py reads a tree.\n")
            write("docs/near.md", "Run `audit.py` of the campaign `y` to check it.\n")
            write("verification/x/README.md", "`audit.py` checks this folder.\n")
            write("tools/builds.py", "import os\nTOOL = os.path.join('verification', 'y', 'audit.py')\n")
            write("llm-dlc/loops/a-brief-results.md", "The run used verification/x/audit.py once.\n")
            callers = inventory.text_callers(root, ["docs/far.md", "docs/near.md", "verification/x/README.md", "tools/builds.py",
                                                    "llm-dlc/loops/a-brief-results.md"], names)
        self.assertEqual(callers["verification/x/audit.py"], {"tests": [], "code": [], "pages": ["verification/x/README.md"],
                                                              "records": ["llm-dlc/loops/a-brief-results.md"]})
        self.assertEqual(callers["verification/y/audit.py"], {"tests": [], "code": ["tools/builds.py"], "pages": ["docs/near.md"], "records": []})

    def test_a_job_calls_a_script_by_its_path_or_from_the_folder_its_step_runs_in(self):
        names = ["verification/x/tool.py", "verification/y/tool.py"]
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            jobs = Path(d) / "verification/jobs"
            jobs.mkdir(parents=True)
            (Path(d) / "verification/results").mkdir()
            spec = lambda n, **step: (jobs / f"2026010{n}-000000-j.json").write_text(json.dumps({"id": f"2026010{n}-000000-j", "steps": [step]}))
            spec(1, run="python3 verification/x/tool.py --all")
            spec(2, run="python3 tool.py", cwd="verification/y")
            spec(3, run="cd verification/y && python3 tool.py")
            spec(4, run="python3 tool.py")                                   # which one? neither is claimed
            ran = inventory.job_callers(Path(d), names)
            self.assertEqual({name: [j["job"][:8] for j in rows] for name, rows in ran.items()},
                             {"verification/x/tool.py": ["20260101"], "verification/y/tool.py": ["20260102", "20260103"]})


if __name__ == "__main__":
    unittest.main()
