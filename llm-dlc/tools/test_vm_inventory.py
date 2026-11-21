#!/usr/bin/env python3
"""Tests for vm_inventory.py: that a folder sealed once is not sealed again until it changes, and that nothing is
sealed in a dry run. Made-up files in a temporary directory. Run: python3 llm-dlc/tools/test_vm_inventory.py"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import artifacts
import vm_inventory
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402


class Protect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {"ITL_ORIGINALS_HOME": str(self.dir / "home"), "ITL_ORIGINALS_RESERVE": "0"})
        self.env.start()
        os.environ.pop("ITL_ORIGINALS_OFF", None)
        self.folder = self.dir / "run"
        (self.folder / "logs").mkdir(parents=True)
        (self.folder / "logs/1-run.log").write_text("made up\n")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def occurrences(self) -> int:
        archive = artifacts.Archive()
        try:
            return archive.db.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0]
        finally:
            archive.close()

    def test_a_folder_is_sealed_once_and_again_only_when_it_changes(self):
        for expected in (1, 1):
            protector = vm_inventory.Protector(dry=False)
            protector.tree("runs", "runs:ws:made-up", self.folder, "job-run", "verification/results/made-up", job="made-up")
            protector.archive.close()
            self.assertEqual(self.occurrences(), expected)
        self.assertEqual(protector.tally["runs unchanged"], 1)
        (self.folder / vm_inventory.SEALED_MARK).write_text("{}")  # the mark itself is no change
        protector = vm_inventory.Protector(dry=False)
        protector.tree("runs", "runs:ws:made-up", self.folder, "job-run", "verification/results/made-up", job="made-up")
        protector.archive.close()
        self.assertEqual(self.occurrences(), 1)
        (self.folder / "logs/2-more.log").write_text("later\n")
        protector = vm_inventory.Protector(dry=False)
        protector.tree("runs", "runs:ws:made-up", self.folder, "job-run", "verification/results/made-up", job="made-up")
        protector.archive.close()
        self.assertEqual((self.occurrences(), protector.tally["runs sealed"]), (2, 1))

    def test_a_dry_run_seals_nothing_and_counts_what_it_would(self):
        protector = vm_inventory.Protector(dry=True)
        protector.tree("runs", "runs:ws:made-up", self.folder, "job-run", "verification/results/made-up")
        self.assertEqual((protector.tally["runs to seal"], protector.tally["runs bytes"]), (1, 8))
        self.assertFalse((self.dir / "home/journal.sqlite").exists())

    @cost("tool")
    def test_what_was_set_aside_is_sealed_restricted_and_a_work_directory_as_what_it_holds_beyond_its_commit(self):
        sys.path.insert(0, str(vm_inventory.REPO / "verification"))
        import capture  # noqa: F401  (vm_inventory imports it by name from the checkout it is patched to below)
        repo = self.dir / "repo"
        git = lambda *argv: subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *argv],
                                           cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
        (repo / "src").mkdir(parents=True)
        (repo / "src/Kept.java").write_text("class Kept {}\n")
        git("init", "-q")
        git("add", ".")
        git("commit", "-q", "-m", "made up")
        commit = git("rev-parse", "HEAD")
        aside = repo / "verification/.state/set-aside/20260101-a-made-up-reason"
        for job, named in (("job-with-a-result", True), ("job-nothing-names", False)):
            work = aside / "work" / job
            (work / "src").mkdir(parents=True)
            (work / "src/Kept.java").write_text("class Kept {}\n")       # as the commit has it: left out
            (work / "src/Made.java").write_text("class Made {}\n")       # what the job made
            (work / "lib/target/release").mkdir(parents=True)
            (work / "lib/target/release/binary").write_bytes(b"\x00" * 64)  # build output: left out
            (aside / "runs" / job / "logs").mkdir(parents=True)
            (aside / "runs" / job / "logs/0-run.log").write_text("a made-up line with a host name\n")
            if named:
                (aside / "results" / job).mkdir(parents=True)
                (aside / "results" / job / "result.json").write_text(json.dumps({"sourceCommit": commit}))
        with mock.patch.object(vm_inventory, "REPO", repo):
            dry = vm_inventory.Protector(dry=True)
            dry.set_aside([repo])
            self.assertEqual((dry.tally["set-aside folders to seal"], dry.tally["set-aside workdirs to seal"]), (1, 1))
            self.assertFalse((self.dir / "home/journal.sqlite").exists())
            for expected in (2, 2):                                       # again: nothing is sealed twice
                protector = vm_inventory.Protector(dry=False)
                protector.set_aside([repo])
                protector.archive.close()
                self.assertEqual(self.occurrences(), expected)
        self.assertEqual(protector.tally["set-aside workdirs with no result to name their commit (left, not sealed)"], 1)
        self.assertEqual((protector.tally["set-aside folders unchanged"], protector.tally["set-aside workdirs unchanged"]), (1, 1))
        archive = artifacts.Archive()
        try:
            rows = {kind: (access, source, size) for kind, access, source, size in
                    archive.db.execute("SELECT kind, access, source, raw_bytes FROM occurrences")}
        finally:
            archive.close()
        log, made = len("a made-up line with a host name\n"), len("class Made {}\n")
        self.assertEqual(rows["set-aside"][0], "restricted")                 # both jobs' runs and the one result; no work/
        self.assertEqual(rows["set-aside"][2], 2 * log + len(json.dumps({"sourceCommit": commit})))
        self.assertEqual((rows["job-workdir"][0], commit in rows["job-workdir"][1]), ("restricted", True))
        self.assertEqual(rows["job-workdir"][2], made)                       # not what the commit holds, nor what a build makes
        self.assertTrue((aside / "work/job-with-a-result/src/Made.java").is_file())  # nothing set aside is moved or removed

    def test_only_this_repositorys_transcript_folders_are_named(self):
        with mock.patch.object(vm_inventory, "default_root", lambda: Path("/home/made-up/code/project")), \
                mock.patch.object(Path, "home", lambda: self.dir):
            base = self.dir / ".claude/projects"
            for name in ("-home-made-up-code-project", "-home-made-up-code-project-stream-a", "-home-made-up-code-projectile",
                         "-home-made-up-code-other"):
                (base / name).mkdir(parents=True)
            self.assertEqual([p.name for p in vm_inventory.claude_projects()],
                             ["-home-made-up-code-project", "-home-made-up-code-project-stream-a"])


if __name__ == "__main__":
    unittest.main()
