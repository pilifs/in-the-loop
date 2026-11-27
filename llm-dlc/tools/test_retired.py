#!/usr/bin/env python3
"""Tests for retired.py: the register of what the repository retired (llm-dlc/retired.md), the rule that a live
file naming something retired points at it, and the one dated line a historical page or a finding gets.
Run: python3 llm-dlc/tools/test_retired.py"""
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


class Fixture(unittest.TestCase):
    """A made-up repository: the register above, and whatever a test puts beside it."""

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


class TheRegister(Fixture):
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

    def test_the_jobs_pipelines_folder_is_live_code_and_pages(self):
        """The neutral pipeline (jobs/) is instructions and code agents act on, whatever its depth: a page or a
        workload adapter there that sends a reader to a retired command is reported like any other live file."""
        self.put("jobs/README.md", "Submit with `old_run.py submit`.\n")
        self.put("jobs/pipeline.py", '"""The queue."""\n')
        self.put("jobs/workloads/resolution.py", '"""Resolves a task, as old-run did for a stream."""\n')
        self.put("jobs/fixtures/notes.txt", "old_run.py\n")  # neither code nor a page
        rows = retired.scan(self.root, retired.register(self.root))
        self.assertEqual([(r["file"], r["names"]) for r in rows],
                         [("jobs/README.md", ["old_run.py"]), ("jobs/workloads/resolution.py", ["old-run"])])

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


class ARetiredFolder(Fixture):
    def setUp(self):
        super().setUp()
        self.put("llm-dlc/retired.md", REGISTER.replace("- **Files:** `llm-dlc/tools/old_run.py`",
                                                         "- **Files:** `llm-dlc/tools/old_run.py`, `old-plugin/`"))
        self.found = retired.register(self.root)

    def test_a_folder_that_keeps_only_a_cache_python_left_behind_is_gone(self):
        # what jj leaves when a change removes a folder a checkout once imported a module from
        self.put("old-plugin/skills/old/__pycache__/bootstrap.cpython-314.pyc", "\x00")
        (self.root / "old-plugin/empty").mkdir()
        self.assertEqual(retired.still_here(self.root, self.found), [])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(retired.main(["check"], root=self.root), 0)

    def test_a_folder_with_a_file_of_its_own_is_still_here(self):
        self.put("old-plugin/skills/old/__pycache__/bootstrap.cpython-314.pyc", "\x00")
        self.put("old-plugin/skills/old/SKILL.md", "# Old\n")
        self.assertEqual(retired.still_here(self.root, self.found), [{"entry": "old-run", "file": "old-plugin/"}])
        (self.root / "old-plugin/skills/old/SKILL.md").unlink()
        self.assertEqual(retired.still_here(self.root, self.found), [])
        (self.root / "old-plugin/link").symlink_to("nowhere")  # a link counts, whatever it points at
        self.assertEqual(retired.still_here(self.root, self.found), [{"entry": "old-run", "file": "old-plugin/"}])


class HistoricalPages(Fixture):
    def setUp(self):
        super().setUp()
        self.put("llm-dlc/loops/old-brief.md", "# Brief: an old one\n\nRun it with old_run.py.\n")
        self.put("llm-dlc/loops/quiet.md", "# Brief: one that names nothing retired\n")
        self.put("llm-dlc/loops/brief-generation-template.md", "As old_run.py did (llm-dlc/retired.md).\n")  # live: the other rule
        self.put("llm-dlc/loops/the-users-brief.md", "# The user's\n\nThey wrote old_run.py here.\n")
        self.put("llm-dlc/loops/queue.jsonl", '{"copy": "llm-dlc/loops/the-users-brief.md"}\n')  # the queue's copy: a record
        self.put("verification/findings.md",
                 "# Findings\n\n## Open\n\n### VF-002: about the old run\n\n- **Status**: open.\n- It ran `old-run` with old_run.py.\n\n"
                 "### VF-001: about something else\n\n- **Status**: open.\n\n## Notes\n\nold_run.py, named outside every entry.\n")
        self.found = retired.register(self.root)

    def test_a_historical_page_and_a_finding_that_name_something_retired_lack_one_dated_line(self):
        rows = retired.scan_historical(self.root, self.found)
        self.assertEqual([(r["file"], r.get("entry"), r["names"]) for r in rows],
                         [("llm-dlc/loops/old-brief.md", None, ["old_run.py"]),
                          ("verification/findings.md", "VF-002", ["old-run", "old_run.py"])])
        self.assertEqual(rows[0]["line"],
                         "> **Retired (2026-11-27, change `kkkkllll`):** this page names `old_run.py`, which is no longer in the "
                         "repository. See [`llm-dlc/retired.md#old-run`](../retired.md#old-run) for what replaced it and the last "
                         "commit that has it.")
        self.assertIn("this entry names `old-run` and `old_run.py`, which are no longer in the repository. See "
                      "[`llm-dlc/retired.md#old-run`](../llm-dlc/retired.md#old-run) for what replaced them", rows[1]["line"])
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            self.assertEqual(retired.main(["check"], root=self.root), 1)
            self.assertEqual(retired.main(["banners"], root=self.root), 1)  # it only lists them
        self.assertIn("llm-dlc/loops/old-brief.md: names old_run.py without the line", said.getvalue())
        self.assertIn("verification/findings.md VF-002: names old-run, old_run.py without the line", said.getvalue())

    def test_the_lines_are_written_once_at_a_pages_top_and_under_a_findings_heading_and_a_record_is_left_alone(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(retired.main(["banners", "--write"], root=self.root), 0)
            self.assertEqual(retired.main(["check"], root=self.root), 0)
            self.assertEqual(retired.main(["banners", "--write"], root=self.root), 0)  # nothing is left to write
        page = (self.root / "llm-dlc/loops/old-brief.md").read_text()
        self.assertTrue(page.startswith("> **Retired (2026-11-27, change `kkkkllll`):** this page names"), page)
        self.assertTrue(page.endswith("\n\n# Brief: an old one\n\nRun it with old_run.py.\n"), page)  # its text is as it was
        self.assertEqual(page.count("**Retired"), 1)
        findings = (self.root / "verification/findings.md").read_text()
        self.assertIn("### VF-002: about the old run\n\n- **Retired (2026-11-27, change `kkkkllll`):** this entry names", findings)
        self.assertEqual(findings.count("**Retired"), 1)  # VF-001 names nothing, and the notes are no entry
        for name, text in (("the-users-brief.md", "# The user's\n\nThey wrote old_run.py here.\n"),
                           ("quiet.md", "# Brief: one that names nothing retired\n"),
                           ("brief-generation-template.md", "As old_run.py did (llm-dlc/retired.md).\n")):
            self.assertEqual((self.root / "llm-dlc/loops" / name).read_text(), text)

    def test_a_line_names_every_change_that_removed_what_the_page_names(self):
        more = self.found + [{"name": "other", "status": "retired", "names": ["other.sh"], "files": [],
                              "fields": {"Removed in": "change `mmmmnnnnoooo` (2026-12-01)"}}]
        owner, _ = retired.retired_names(more)
        line = retired.line_for(["old_run.py", "other.sh"], owner, "../retired.md", "page")
        self.assertIn("(2026-11-27, 2026-12-01, changes `kkkkllll` and `mmmmnnnn`)", line)
        self.assertIn("[`llm-dlc/retired.md#old-run`](../retired.md#old-run) and [`llm-dlc/retired.md#other`](../retired.md#other)", line)


class TheRepository(unittest.TestCase):
    def test_no_live_file_sends_a_reader_to_something_retired(self):
        found = retired.register(retired.REPO)
        self.assertEqual(retired.problems(found), [])
        self.assertEqual(retired.still_here(retired.REPO, found), [])
        rows = retired.scan(retired.REPO, found)
        self.assertEqual(rows, [], "\n" + "\n".join(f"{r['file']}:{r['line']}: {', '.join(r['names'])}" for r in rows[:40]))

    def test_every_historical_page_and_finding_that_names_something_retired_has_its_line(self):
        rows = retired.scan_historical(retired.REPO, retired.register(retired.REPO))
        self.assertEqual(rows, [], "\n" + "\n".join(f"{r['file']} {r.get('entry') or ''}: {', '.join(r['names'])}" for r in rows[:40])
                         + "\npython3 llm-dlc/tools/retired.py banners --write adds them")


if __name__ == "__main__":
    unittest.main()
