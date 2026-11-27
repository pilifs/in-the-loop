#!/usr/bin/env python3
"""Tests for retired.py: the register of what the repository retired (llm-dlc/retired.md), and the rule that a live
file naming something retired points at it. Run: python3 llm-dlc/tools/test_retired.py"""
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import retired

REGISTER = """# Retired

## Entries

### old-run

- **Status:** retired
- **What it was:** a run of several agents.
- **Replaced by:** `/orchestrate-run`.
- **Names:** `old-run`, `old_run.py`,
  `old-loop.sh fast`
- **Files:** `llm-dlc/tools/old_run.py`
- **Removed in:** change `kkkkllllmmmm` (2026-11-27)

### later-run

- **Status:** planned
- **What it was:** another.
- **Replaced by:** nothing yet.
- **Names:** `later.py`
- **Files:** none: it is kept
- **Removed in:** not yet
"""


class TheRegister(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.put("llm-dlc/retired.md", REGISTER)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name: str, text: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_an_entry_is_read_with_its_names_and_files_and_a_malformed_one_is_reported(self):
        found = retired.entries(REGISTER)
        self.assertEqual([e["name"] for e in found], ["old-run", "later-run"])
        self.assertEqual(found[0]["names"], ["old-run", "old_run.py", "old-loop.sh fast"])  # a value runs on over a line
        self.assertEqual(found[0]["files"], ["llm-dlc/tools/old_run.py"])
        self.assertEqual((found[1]["status"], found[1]["files"]), ("planned", []))
        self.assertEqual(retired.problems(found), [])
        broken = REGISTER.replace("- **Status:** retired", "- **Status:** gone").replace("change `kkkkllllmmmm`", "soon")
        said = retired.problems(retired.entries(broken))
        self.assertTrue(any("status 'gone'" in line for line in said), said)
        retired_without_a_change = REGISTER.replace("change `kkkkllllmmmm`", "soon")
        self.assertTrue(any("names no change" in line for line in retired.problems(retired.entries(retired_without_a_change))))
        with self.assertRaises(retired.Problem):
            retired.entries("# A page with no entries\n")

    def test_a_live_paragraph_that_names_something_retired_must_point_at_the_register(self):
        self.put("CLAUDE.md", "Start a run with `old_run.py start`.\n\n"
                              "The streams workflow (`old-run`) was retired: see llm-dlc/retired.md.\n\n"
                              "Nothing here.\n")
        self.put("llm-dlc/tools/new_run.py", '"""As old_run.py did, but for one agent."""\n\nimport os\n')
        self.put("llm-dlc/tools/test_old_run.py", "import unittest  # test_old_run.py and new-old-run are other names\n")
        self.put("llm-dlc/loops/some-brief.md", "Run it with old_run.py.\n")  # a historical page: not read here
        found = retired.register(self.root)
        rows = retired.scan(self.root, found)
        self.assertEqual([(r["file"], r["line"], r["names"]) for r in rows],
                         [("CLAUDE.md", 1, ["old_run.py"]), ("llm-dlc/tools/new_run.py", 1, ["old_run.py"])])
        self.assertEqual(rows[0]["entries"], ["old-run"])
        # the control: the same pages once each paragraph points at the register, or no longer names it
        self.put("CLAUDE.md", "Start a run with `new_run.py start` (`old_run.py` is retired: llm-dlc/retired.md).\n")
        self.put("llm-dlc/tools/new_run.py", '"""For one agent."""\n')
        self.assertEqual(retired.scan(self.root, found), [])

    def test_a_name_is_a_word_of_its_own_and_a_planned_entry_counts_only_when_asked(self):
        self.put("README.md", "Use `old-loop.sh   fast` or old-loop.sh slow.\n\nlater.py is still here.\n")
        found = retired.register(self.root)
        rows = retired.scan(self.root, found)
        self.assertEqual([(r["line"], r["names"]) for r in rows], [(1, ["old-loop.sh fast"])])  # `slow` was never retired
        self.assertEqual([(r["line"], r["names"]) for r in retired.scan(self.root, found, planned=True)],
                         [(1, ["old-loop.sh fast"]), (3, ["later.py"])])

    def test_a_retired_file_that_is_still_here_is_reported_and_the_generated_table_is_not_read(self):
        found = retired.register(self.root)
        self.assertEqual(retired.still_here(self.root, found), [])
        self.put("llm-dlc/tools/old_run.py", "pass\n")
        self.assertEqual(retired.still_here(self.root, found), [{"entry": "old-run", "file": "llm-dlc/tools/old_run.py"}])
        self.put("llm-dlc/README.md", "Intro.\n\n<!-- index:begin (generated) -->\n| a session that ran old_run.py |\n"
                                      "<!-- index:end -->\n\nAfter the table, old_run.py again.\n")
        rows = retired.scan(self.root, found)
        self.assertEqual([(r["file"], r["line"]) for r in rows if r["file"] == "llm-dlc/README.md"], [("llm-dlc/README.md", 7)])
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            self.assertEqual(retired.main(["check"], root=self.root), 1)
        self.assertIn("llm-dlc/tools/old_run.py: still here", said.getvalue())


class TheRepository(unittest.TestCase):
    def test_no_live_file_sends_a_reader_to_something_retired(self):
        found = retired.register(retired.REPO)
        self.assertEqual(retired.problems(found), [])
        self.assertEqual(retired.still_here(retired.REPO, found), [])
        rows = retired.scan(retired.REPO, found)
        self.assertEqual(rows, [], "\n" + "\n".join(f"{r['file']}:{r['line']}: {', '.join(r['names'])}" for r in rows[:40]))


if __name__ == "__main__":
    unittest.main()
