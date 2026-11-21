#!/usr/bin/env python3
"""Tests for vm_inventory.py: that a folder sealed once is not sealed again until it changes, and that nothing is
sealed in a dry run. Made-up files in a temporary directory. Run: python3 llm-dlc/tools/test_vm_inventory.py"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import artifacts
import vm_inventory


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
