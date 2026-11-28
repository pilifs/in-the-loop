#!/usr/bin/env python3
"""Tests for layout.py: one job id, two places it may be kept, and readers that take both.
Run: python3 verification/test_layout.py"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import layout

OLD = "20261106-first-made-up-job"
NEW = "20261121-105825-a-made-up-job"
ODD = "made-up-without-a-date"


class Paths(unittest.TestCase):
    def test_a_job_id_names_its_shard_by_the_day_it_begins_with(self):
        self.assertEqual(layout.shard(NEW), "2026/11/21")
        self.assertEqual(layout.shard(ODD), "undated")
        self.assertEqual(layout.shard("20261341-not-a-day"), "undated")
        self.assertEqual(layout.shard("20261121"), "undated")  # a date and nothing after it is not an id's prefix
        self.assertEqual(layout.job_rel(NEW), f"verification/jobs/{NEW}.json")
        self.assertEqual(layout.job_rel(NEW, "shards"), f"verification/jobs/2026/11/21/{NEW}.json")
        self.assertEqual(layout.result_rel(ODD, "shards"), f"verification/results/undated/{ODD}")

    def test_a_path_in_either_layout_names_its_job_and_nothing_else_does(self):
        self.assertEqual(layout.job_id_of(f"verification/jobs/{OLD}.json"), OLD)
        self.assertEqual(layout.job_id_of(f"verification/jobs/2026/11/21/{NEW}.json"), NEW)
        self.assertEqual(layout.job_id_of(f"verification/jobs/undated/{ODD}.json"), ODD)
        for path in (f"verification/jobs/2026/11/22/{NEW}.json",      # the wrong day's shard
                     f"verification/jobs/2026/{NEW}.json", "verification/priorities.json", f"verification/results/{OLD}/result.json",
                     f"verification/jobs/{OLD}.json.bak", f"examples/x/verification/jobs/{OLD}.json"):
            self.assertIsNone(layout.job_id_of(path), path)
        self.assertEqual(layout.result_id_of(f"verification/results/{OLD}/result.json"), (OLD, "result.json"))
        self.assertEqual(layout.result_id_of(f"verification/results/2026/11/21/{NEW}/logs/1-run.log"), (NEW, "logs/1-run.log"))
        self.assertEqual(layout.result_id_of(f"verification/results/undated/{ODD}/outputs/a/b.json"), (ODD, "outputs/a/b.json"))
        for path in (f"verification/results/2026/11/21/{NEW}", "verification/results/2026/11/21", f"verification/results/2026/12/01/{NEW}/result.json",
                     f"verification/jobs/{OLD}.json", "verification/results/index.json"):
            self.assertIsNone(layout.result_id_of(path), path)

    def test_the_results_a_commits_tree_records_are_found_in_both_layouts(self):
        listing = [f"verification/results/{OLD}/result.json", f"verification/results/{OLD}/logs/1-run.log",
                   f"verification/results/2026/11/21/{NEW}/result.json", f"verification/results/2026/11/21/{NEW}/outputs/result.json",
                   f"verification/results/undated/{ODD}/logs/result.json", "verification/findings.md"]
        self.assertEqual(layout.recorded(listing), {OLD, NEW})


class Tree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def job(self, job_id, layout_="flat", text="{}"):
        path = self.root / layout.job_rel(job_id, layout_)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def result(self, job_id, layout_="flat", text="{}"):
        path = self.root / layout.result_rel(job_id, layout_)
        path.mkdir(parents=True, exist_ok=True)
        (path / "result.json").write_text(text)
        return path

    def test_readers_find_a_job_and_its_result_wherever_they_are(self):
        self.assertEqual((layout.jobs(self.root), layout.results(self.root), layout.find_job(self.root, OLD)), ({}, {}, None))
        old, new, odd = self.job(OLD), self.job(NEW, "shards"), self.job(ODD, "shards")
        done_old, done_new = self.result(OLD), self.result(NEW, "shards")
        (self.root / layout.result_rel(ODD, "shards")).mkdir(parents=True)  # a folder with no result.json is not a result
        self.assertEqual(layout.jobs(self.root), {OLD: old, NEW: new, ODD: odd})
        self.assertEqual(layout.results(self.root), {OLD: done_old, NEW: done_new})
        self.assertEqual((layout.find_job(self.root, NEW), layout.find_result(self.root, NEW)), (new, done_new))
        self.assertEqual((layout.find_job(self.root, OLD), layout.find_result(self.root, OLD)), (old, done_old))
        self.assertIsNone(layout.find_result(self.root, ODD))
        self.assertEqual(list(layout.jobs(self.root)), sorted([OLD, NEW, ODD]))

    def test_a_new_job_goes_where_the_layout_says_and_nothing_that_exists_moves(self):
        with mock.patch.dict(os.environ, {"VERIFY_LAYOUT": ""}):      # with no override, layout.WRITE decides
            self.assertEqual(layout.new_job(self.root, NEW), self.root / layout.job_rel(NEW, layout.WRITE))
        with mock.patch.dict(os.environ, {"VERIFY_LAYOUT": "flat"}):
            self.assertEqual(layout.new_job(self.root, NEW), self.root / layout.job_rel(NEW))
        with mock.patch.dict(os.environ, {"VERIFY_LAYOUT": "shards"}):
            self.assertEqual(layout.new_job(self.root, NEW), self.root / layout.job_rel(NEW, "shards"))
            old = self.job(OLD)                      # a job written flat stays flat, and its result goes beside it
            self.assertEqual(layout.new_job(self.root, OLD), old)
            self.assertEqual(layout.new_result(self.root, OLD), self.root / layout.result_rel(OLD))
            self.assertEqual(layout.new_result(self.root, NEW), self.root / layout.result_rel(NEW, "shards"))
        with mock.patch.dict(os.environ, {"VERIFY_LAYOUT": "flat"}):
            new = self.job(NEW, "shards")            # and a sharded one stays sharded, whatever new jobs take now
            self.assertEqual(layout.new_job(self.root, NEW), new)
            self.assertEqual(layout.new_result(self.root, NEW), self.root / layout.result_rel(NEW, "shards"))
            done = self.result(NEW, "shards")
            self.assertEqual(layout.new_result(self.root, NEW), done)

    def test_identical_duplicates_resolve_to_the_flat_copy_and_differing_ones_are_reported(self):
        flat, _ = self.job(NEW, text='{"id": 1}'), self.job(NEW, "shards", text='{"id": 1}')
        done, _ = self.result(NEW, text='{"status": "passed"}'), self.result(NEW, "shards", text='{"status": "passed"}')
        self.assertEqual((layout.jobs(self.root), layout.results(self.root)), ({NEW: flat}, {NEW: done}))
        self.assertEqual((layout.find_job(self.root, NEW), layout.find_result(self.root, NEW)), (flat, done))
        self.assertEqual(layout.conflicts(self.root), [])
        self.job(NEW, "shards", text='{"id": 2}')
        self.result(NEW, "shards", text='{"status": "failed"}')
        problems = layout.conflicts(self.root)
        self.assertEqual(len(problems), 2)
        self.assertIn(f"job {NEW}: verification/jobs/{NEW}.json and verification/jobs/2026/11/21/{NEW}.json differ", problems[0])
        self.assertIn(f"result {NEW}:", problems[1])
        self.assertEqual(layout.find_job(self.root, NEW), flat)  # still one answer, the same one every time

    def test_a_new_result_whose_receipt_lists_thousands_of_files_is_reported_and_an_older_one_is_not(self):
        import json
        many = json.dumps({"outputs": [{"path": f"examples/901-made-up/records/cases/p{i}/native.json", "sha256": "0" * 64}
                                       for i in range(3000)]})
        self.assertGreater(len(many), layout.RECEIPT_BYTES)
        self.result(NEW, text=many)                                             # collected before the rule: left alone
        self.result("20261122-000001-a-small-made-up-job", text='{"outputs": []}')
        self.assertEqual(layout.heavy_receipts(self.root), [])
        self.result("20261122-000002-a-made-up-job-of-loose-cases", "shards", text=many)
        self.result("20261203-000003-a-made-up-job-with-a-long-text", text=json.dumps({"summary": "x" * layout.RECEIPT_BYTES}))
        self.result(ODD, "shards", text=many)                                   # no day in its id: no rule to hold it to
        first, second = layout.heavy_receipts(self.root)
        self.assertEqual(first, f"verification result 20261122-000002-a-made-up-job-of-loose-cases: result.json is {len(many):,} bytes "
                                f"(over 262,144), listing 3,000 output files: a job that writes many small files keeps them as one "
                                f"pack (examples/tools/targets/case_pack.py)")
        self.assertRegex(second, r"^verification result 20261203-000003-a-made-up-job-with-a-long-text: result.json is [\d,]+ bytes \(over 262,144\)$")
        # a result a person reviewed is a note instead of a warning, and only while it is there
        reviewed = {"20261122-000002-a-made-up-job-of-loose-cases": "made-up review", "20261124-000009-not-here": "gone"}
        self.assertEqual(layout.heavy_receipts(self.root, reviewed), [second])
        self.assertEqual(layout.reviewed_heavy_receipts(self.root, reviewed),
                         ["verification result 20261122-000002-a-made-up-job-of-loose-cases: result.json over 262,144 bytes, "
                          "reviewed and left whole (made-up review)"])


if __name__ == "__main__":
    unittest.main()
