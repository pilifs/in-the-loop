#!/usr/bin/env python3
"""Tests of jobs/audit.py and jobs/records.py: the reconciliation of the job pipeline's records.

A small made-up corpus in a throwaway git repository, clean and then with one fault at a time, and the corpus this
repository had at the revision the migration to a generic pipeline started from (`fixtures/`).

  python3 jobs/test_audit.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit  # noqa: E402
import records  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402

layout = records.layout
PINNED = "b52a084f5d11fbf34f82d7a8cce1ea39938afdd3"  # develop when the brief for the generic pipeline was written


class Corpus:
    """A git repository holding job records written by hand: two flat jobs, two under their day, and the indexes."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="audit-test-"))
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.dir, check=True)
        self.receipts = {}
        self.add("20261120-101010-flat-one", flat=True)
        self.add("20261120-111111-flat-two", flat=True, status="failed")
        self.add("20261123-121212-day-one", status="failed", kept=["made/kept.txt"])
        self.add("20261123-131313-day-two")
        self.index()
        self.commit("the corpus")

    def spec(self, job_id):
        return {"schema": "verification-job/v1", "id": job_id, "title": f"Job {job_id[16:]}", "description": "A made-up job of the audit's tests.",
                "capabilities": ["test"], "resources": {}, "steps": [{"name": "s", "run": "true"}],
                "submitted": {"at": "2026-11-20T10:10:10+00:00", "session": "0000"}}

    def add(self, job_id, flat=False, status="passed", kept=(), result_flat=None):
        spec = self.spec(job_id)
        spec_path = self.dir / layout.job_rel(job_id, "flat" if flat else "shards")
        self.write(spec_path, spec)
        folder = self.dir / layout.result_rel(job_id, "flat" if (flat if result_flat is None else result_flat) else "shards")
        receipt = {"schema": "verification-result/v1", "id": job_id, "title": spec["title"], "status": status,
                   "summary": f"{status}: 1 step", "attention": [] if status == "passed" else ["step 1 (s) exited 1, expected 0"],
                   "job": {"path": spec_path.relative_to(self.dir).as_posix(), "sha256": records.spec_digest(spec), "spec": spec},
                   "sourceCommit": "0" * 40, "startedAt": "2026-11-20T10:10:11+00:00", "finishedAt": f"2026-11-20T10:{job_id[11:13]}:12+00:00",
                   "runner": {"host": "made-up"}, "limits": {}, "estimate": {}, "usage": {"wallSeconds": 1.0, "peakMemoryBytes": 1},
                   "environment": {}, "steps": [{"index": 1, "name": "s", "run": "true", "status": status, "log": {"path": "logs/1-s.log"}}],
                   "outputs": [{"path": k, "change": "added", "bytes": 5, "sha256": "x"} for k in kept],
                   "collected": {"at": "2026-11-20T10:20:00+00:00", "applied": [], "conflicts": [], "kept": list(kept), "why": None}}
        self.write(folder / "result.json", receipt)
        (folder / "logs").mkdir(parents=True, exist_ok=True)
        (folder / "logs/1-s.log").write_text("done\n")
        for k in kept:
            (folder / "outputs" / k).parent.mkdir(parents=True, exist_ok=True)
            (folder / "outputs" / k).write_text("kept\n")
        self.receipts[job_id] = ((folder / "result.json").relative_to(self.dir).as_posix(), receipt)
        return folder

    def write(self, path, document):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2) + "\n")

    def index(self):
        for path, document in records.index_documents(self.receipts).items():
            self.write(self.dir / path, document)

    def commit(self, message):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@example.invalid")
        git = lambda *a: subprocess.run(["git", *a], cwd=self.dir, env=env, check=True, capture_output=True, text=True).stdout.strip()
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", message)
        return git("rev-parse", "HEAD")

    def audit(self, rev="HEAD", state=None):
        return audit.Audit(self.dir, rev).run(state)

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def kinds(found):
    return sorted(f["kind"] for f in found)


class AMadeUpCorpus(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus()
        self.addCleanup(self.corpus.close)

    def test_a_clean_corpus_has_no_discrepancy_and_its_counts_are_the_records(self):
        report = self.corpus.audit()
        self.assertEqual(report["discrepancies"], [])
        census = report["census"]
        self.assertEqual(census["ids"] | {"sha256": None}, {"specs": 4, "receipts": 4, "indexed": 4, "indexRows": 4, "all": 4,
                                                            "inEverySet": 4, "sha256": None})
        self.assertEqual(census["outcomes"], {"failed": 2, "passed": 2})
        self.assertEqual(census["days"]["2026/11/23"], {"rows": 2, "failed": 1, "passed": 1})
        self.assertEqual((census["layouts"]["flatSpecs"], census["layouts"]["specsByDay"]), (2, 2))
        # Nothing of these made-up receipts names an attempt or a run, and the audit says so once each, not 4 times.
        self.assertEqual(kinds(report["gaps"]), ["no-attempt-identity", "no-originating-run"])
        self.assertEqual(report["gaps"][0]["count"], 4)

    def test_a_working_copy_is_read_as_it_stands_and_a_revision_from_git_alone(self):
        folder = self.corpus.add("20261123-141414-not-committed")
        self.corpus.index()
        self.assertEqual(self.corpus.audit()["census"]["ids"]["receipts"], 4)          # HEAD does not have it
        self.assertEqual(self.corpus.audit(rev=None)["census"]["ids"]["receipts"], 5)  # the working copy does
        shutil.rmtree(folder)
        self.assertEqual(kinds(self.corpus.audit(rev=None)["discrepancies"]), ["index-orphan-row"])

    def test_one_id_with_two_specifications_that_differ_is_a_discrepancy_and_identical_ones_a_note(self):
        job_id = "20261120-101010-flat-one"
        twin = self.corpus.dir / layout.job_rel(job_id, "shards")
        twin.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.corpus.dir / layout.job_rel(job_id), twin)
        self.corpus.commit("the same job twice")
        report = self.corpus.audit()
        self.assertEqual((kinds(report["discrepancies"]), kinds(report["notes"])), ([], ["duplicate-spec-identical"]))
        self.corpus.write(twin, {**self.corpus.spec(job_id), "steps": [{"run": "false"}]})
        self.corpus.commit("and differently")
        found = self.corpus.audit()["discrepancies"]
        self.assertEqual(kinds(found), ["duplicate-identity"])
        self.assertEqual(found[0]["paths"], [layout.job_rel(job_id), layout.job_rel(job_id, "shards")])

    def test_a_specification_that_is_not_json_is_named_with_its_path_and_its_revision(self):
        path = self.corpus.dir / layout.job_rel("20261123-121212-day-one", "shards")
        path.write_text("{ cut off")
        commit = self.corpus.commit("a damaged job")
        found = self.corpus.audit()["discrepancies"]
        self.assertEqual(kinds(found), ["malformed-spec"])
        self.assertEqual((found[0]["path"], found[0]["at"]), (layout.job_rel("20261123-121212-day-one", "shards"), commit[:12]))

    def test_a_receipt_with_no_job_and_a_job_edited_after_it_ran_are_discrepancies(self):
        (self.corpus.dir / layout.job_rel("20261120-101010-flat-one")).unlink()
        edited = self.corpus.dir / layout.job_rel("20261120-111111-flat-two")
        self.corpus.write(edited, {**json.loads(edited.read_text()), "steps": [{"run": "echo other"}]})
        self.corpus.commit("a job removed, a job edited")
        found = {f["kind"]: f["id"] for f in self.corpus.audit()["discrepancies"]}
        self.assertEqual(found, {"receipt-without-spec": "20261120-101010-flat-one", "spec-drift": "20261120-111111-flat-two"})

    def test_an_index_that_is_stale_short_or_long_is_told_from_the_receipts(self):
        base = self.corpus.dir / layout.RESULTS
        flat = json.loads((base / "index.json").read_text())
        flat["results"][0]["status"] = "passed" if flat["results"][0]["status"] == "failed" else "failed"   # stale
        flat["results"].append({**flat["results"][1], "id": "20261120-000000-never-ran"})                  # a row for no receipt
        self.corpus.write(base / "index.json", flat)
        day = json.loads((base / "2026/11/23/index.json").read_text())
        gone = day["results"].pop()                                                                          # a receipt with no row
        self.corpus.write(base / "2026/11/23/index.json", day)
        self.corpus.commit("indexes by hand")
        found = {f["kind"]: f for f in self.corpus.audit()["discrepancies"]}
        self.assertEqual(sorted(found), ["index-missing-row", "index-orphan-row", "index-stale-row"])
        self.assertEqual(found["index-missing-row"]["id"], gone["id"])
        self.assertEqual(found["index-orphan-row"]["id"], "20261120-000000-never-ran")
        self.assertIn("status differ", found["index-stale-row"]["detail"])
        self.assertIn("the receipt", found["index-stale-row"]["detail"])

    def test_a_kept_output_the_commit_left_out_is_a_gap_with_its_reason(self):
        folder = self.corpus.dir / layout.result_rel("20261123-121212-day-one", "shards")
        (folder / "outputs/made/kept.txt").unlink()
        (folder / "logs/1-s.log").unlink()
        self.corpus.commit("an output and a log left out")
        report = self.corpus.audit()
        self.assertEqual(report["discrepancies"], [])
        missing = [g for g in report["gaps"] if g["kind"] == "artifact-not-committed"]
        self.assertEqual(sorted((g["what"], g["reason"]) for g in missing), [("kept output", "unexplained"), ("log", "unexplained")])
        self.assertTrue(all("no original of it was sealed" in g["detail"] for g in missing))

    def test_a_result_that_is_not_beside_its_job_is_found_by_id_and_noted(self):
        self.corpus.add("20261122-151515-flat-job-dated-result", flat=True, result_flat=False)
        self.corpus.index()
        self.corpus.commit("a flat job with its result under its day")
        report = self.corpus.audit()
        self.assertEqual(report["discrepancies"], [])
        self.assertEqual([(n["kind"], n["id"]) for n in report["notes"]], [("mixed-layout", "20261122-151515-flat-job-dated-result")])
        self.assertEqual(report["census"]["layouts"]["mixed"], ["20261122-151515-flat-job-dated-result"])
        self.assertEqual(report["census"]["ids"]["inEverySet"], 5)

    def test_a_batchs_rows_are_joined_with_the_jobs_both_ways(self):
        """Expected rows against committed specifications: a row whose job is gone, a job the map does not list (a
        resubmission committed without its map), and a job of a batch that has no map are each a discrepancy."""
        work = "ab" * 32
        ids = {"R1": "20261124-101010-b-r1", "R2": "20261124-101011-b-r2", "R2b": "20261124-121212-b-r2-again", "R3": "20261124-101012-b-r3"}
        for row, job_id in ids.items():
            spec = {**self.corpus.spec(job_id), "schema": "itl-job/v2", "batch": {"id": "made-up", "row": row[:2], "work": work}}
            self.corpus.write(self.corpus.dir / layout.job_rel(job_id, "shards"), spec)
        entry = lambda *jobs: {"current": jobs[-1], "work": work, "history": [{"job": j, "work": work, "why": "submitted"} for j in jobs]}
        document = {"schema": "itl-job-batch-map/v1", "batch": "made-up", "created": "2026-11-24T10:10:10+00:00",
                    "rows": {"R1": entry(ids["R1"]), "R2": entry(ids["R2"], ids["R2b"]), "R3": entry(ids["R3"])}}
        self.corpus.write(self.corpus.dir / "verification/batches/made-up.json", document)
        self.corpus.commit("a batch of three rows, one resubmitted")
        report = self.corpus.audit()
        self.assertEqual([d for d in report["discrepancies"] if d["kind"].startswith(("batch", "malformed-batch"))], [])
        self.assertEqual(report["batches"], {"made-up": {"rows": 3, "jobs": 4, "withdrawn": 0}})
        # One fault at a time.
        document["rows"]["R2"] = entry(ids["R2"])                       # the resubmission's map was not committed
        self.corpus.write(self.corpus.dir / "verification/batches/made-up.json", document)
        found = [d for d in self.corpus.audit(rev=None)["discrepancies"] if d["kind"].startswith("batch")]
        self.assertEqual([(d["kind"], d["id"], d["row"]) for d in found], [("batch-job-unlisted", ids["R2b"], "R2")])
        document["rows"]["R2"] = entry(ids["R2"], ids["R2b"])
        document["rows"]["R4"] = entry("20261124-101013-b-r4")           # a row whose job nobody wrote
        self.corpus.write(self.corpus.dir / "verification/batches/made-up.json", document)
        found = [d for d in self.corpus.audit(rev=None)["discrepancies"] if d["kind"].startswith("batch")]
        self.assertEqual([(d["kind"], d["id"], d["row"]) for d in found], [("batch-row-without-spec", "20261124-101013-b-r4", "R4")])
        (self.corpus.dir / "verification/batches/made-up.json").unlink()
        found = [d for d in self.corpus.audit(rev=None)["discrepancies"] if d["kind"].startswith("batch")]
        self.assertEqual(sorted({d["kind"] for d in found}), ["batch-map-missing"])
        self.assertEqual(len(found), 4)

    def test_an_output_called_result_json_is_not_a_receipt(self):
        """2,897 files of the real corpus are called result.json and 1,906 are receipts: the rest are kept outputs."""
        folder = self.corpus.dir / layout.result_rel("20261123-121212-day-one", "shards")
        (folder / "outputs/examples/007-x").mkdir(parents=True)
        (folder / "outputs/examples/007-x/result.json").write_text('{"verdict": "verified"}\n')
        self.corpus.commit("an example's result.json among the kept outputs")
        report = self.corpus.audit()
        self.assertEqual((report["census"]["ids"]["receipts"], report["discrepancies"]), (4, []))

    def test_what_the_runner_holds_is_joined_to_the_working_copy(self):
        state = self.corpus.dir / "verification/.state"
        (state / "claims").mkdir(parents=True)
        (state / "claims/20261120-999999-no-such-job").write_text('{"pid": 1, "host": "h"}')
        (state / "results/20261123-131313-day-two").mkdir(parents=True)
        (state / "results/20261123-131313-day-two/result.json").write_text('{"status": "passed"}')
        (state / "results/20261120-888888-half-written").mkdir(parents=True)
        (state / "results/20261120-888888-half-written/result.json").write_text("{")
        (state / "uncaptured/20261120-101010-flat-one-20261120T101500Z").mkdir(parents=True)
        report = self.corpus.audit(rev=None, state=state)
        self.assertEqual(kinds(report["discrepancies"]), ["claim-without-spec", "malformed-staged-result"])
        self.assertEqual(kinds(report["notes"]), ["staged-and-collected"])
        self.assertIn("result-set-aside-unsealed", kinds(report["gaps"]))
        self.assertEqual([s["id"] for s in report["live"]["staged"]], ["20261123-131313-day-two"])
        self.assertTrue(report["snapshot"]["views"]["live"]["available"])
        self.assertFalse(self.corpus.audit()["snapshot"]["views"]["live"]["available"])   # a revision has no live view

    @cost("tool")
    def test_a_manifest_is_the_revisions_git_ids_and_a_moved_or_rewritten_record_differs_from_it(self):
        first = self.corpus.commit("as it is")
        path = self.corpus.dir / "manifest.jsonl.gz"
        document = audit.manifest(self.corpus.dir, first)
        audit.write_manifest(document, path)
        self.assertEqual((document["jobs"], document["files"]), (4, 4 + 4 * 2 + 1))   # a spec, a receipt and a log each, one kept output
        row = document["rows"][0]
        tree = subprocess.run(["git", "rev-parse", f"{first}:{row['results'][0]['path']}"], cwd=self.corpus.dir, capture_output=True, text=True).stdout.strip()
        self.assertEqual(row["results"][0]["tree"], tree)
        self.assertEqual(audit.verify_manifest(self.corpus.dir, path), [])
        once = path.read_bytes()
        audit.write_manifest(audit.manifest(self.corpus.dir, first), path)
        self.assertEqual(path.read_bytes(), once)                                    # the same revision, the same bytes
        # A new job changes no row: the manifest still holds at the later revision.
        self.corpus.add("20261123-161616-later")
        self.corpus.index()
        later = self.corpus.commit("one more job")
        self.assertEqual(audit.verify_manifest(self.corpus.dir, path, later), [])
        # A specification moved to the other layout, and a log rewritten in a result folder: each is named.
        moved = "20261120-101010-flat-one"
        (self.corpus.dir / layout.job_rel(moved, "shards")).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(self.corpus.dir / layout.job_rel(moved), self.corpus.dir / layout.job_rel(moved, "shards"))
        (self.corpus.dir / layout.result_rel("20261123-131313-day-two", "shards") / "logs/1-s.log").write_text("rewritten\n")
        (self.corpus.dir / layout.job_rel("20261120-111111-flat-two")).unlink()
        shutil.rmtree(self.corpus.dir / layout.result_rel("20261120-111111-flat-two"))
        after = self.corpus.commit("a move, a rewrite, a removal")
        problems = audit.verify_manifest(self.corpus.dir, path, after)
        self.assertEqual(len(problems), 3)
        self.assertTrue(any(p.startswith(f"{moved}: its specification was {layout.job_rel(moved)}") for p in problems))
        self.assertTrue(any(p.startswith("20261123-131313-day-two: its result folder was") for p in problems))
        self.assertTrue(any(p.startswith("20261120-111111-flat-two: in the manifest, and not at") for p in problems))

    @cost("tool")
    def test_the_command_exits_1_on_a_discrepancy_and_on_a_census_that_moved(self):
        run = lambda *args: subprocess.run([sys.executable, str(HERE / "audit.py"), "--root", str(self.corpus.dir), *args],
                                           capture_output=True, text=True)
        census = self.corpus.dir.parent / f"{self.corpus.dir.name}-census.json"
        self.addCleanup(census.unlink, missing_ok=True)
        census.write_text(run("--rev", "HEAD", "--census").stdout)
        self.assertEqual(run("--rev", "HEAD", "--expect", str(census)).returncode, 0)
        self.corpus.add("20261123-171717-one-more", status="failed")
        self.corpus.index()
        self.corpus.commit("one more")
        moved = run("--rev", "HEAD", "--expect", str(census))
        self.assertEqual(moved.returncode, 1)
        self.assertIn("the census differs", moved.stderr)
        (self.corpus.dir / layout.RESULTS / "index.json").write_text('{"results": "none"}')
        self.corpus.commit("a damaged index")
        damaged = run("--rev", "HEAD")
        self.assertEqual(damaged.returncode, 1)
        self.assertIn("malformed-index", damaged.stdout)


class TheCorpusOfThisRepository(unittest.TestCase):
    """The records as they were at the pinned revision: the baseline every later view is compared with."""

    @classmethod
    def setUpClass(cls):
        cls.root = HERE.parent
        there = subprocess.run(["git", "cat-file", "-e", f"{PINNED}^{{commit}}"], cwd=cls.root, capture_output=True)
        if there.returncode != 0:
            raise unittest.SkipTest(f"{PINNED[:12]} is not in this clone")
        cls.census = json.loads((HERE / "fixtures/census-b52a084f5d11.json").read_text())

    @cost("tool")
    def test_the_pinned_corpus_reconciles_to_its_frozen_census(self):
        report = audit.Audit(self.root, PINNED).run()
        self.assertEqual(report["discrepancies"], [])
        self.assertEqual(report["census"], self.census)
        ids = report["census"]["ids"]
        self.assertEqual((ids["specs"], ids["receipts"], ids["indexed"], ids["indexRows"], ids["inEverySet"]), (1906,) * 5)
        self.assertEqual(report["census"]["outcomes"], {"error": 17, "failed": 420, "passed": 1469})
        self.assertEqual(report["census"]["days"]["2026/11/27"], {"rows": 172, "error": 5, "failed": 62, "passed": 105})
        self.assertEqual(len(report["census"]["layouts"]["mixed"]), 3)   # flat specifications of 2026-11-22, dated results

    @cost("tool")
    def test_no_record_of_the_pinned_corpus_moved_changed_or_went(self):
        """Every specification, receipt and result folder the manifest names is at the checked-out commit with the
        same git ids: a migration that moved a pending job, or rewrote a receipt, shows here."""
        manifest = HERE / "fixtures/manifest-b52a084f5d11.jsonl.gz"
        self.assertEqual(audit.verify_manifest(self.root, manifest), [])
        head = records.head(self.root)
        self.assertEqual(audit.verify_manifest(self.root, manifest, head), [])

    @cost("tool")
    def test_the_committed_indexes_are_byte_for_byte_what_the_receipts_give(self):
        """`collect` writes the indexes with the function the audit recomputes them with, and at the pinned revision
        that function gives each of the seven index files back to the byte."""
        check = audit.Audit(self.root, PINNED)
        check.read_specs()
        check.read_receipts()
        committed = check.snapshot.read(check.snapshot.indexes())
        recomputed = records.index_documents(check.receipts)
        self.assertEqual(sorted(recomputed), sorted(committed))
        self.assertEqual(len(committed), 7)
        for path, document in recomputed.items():
            self.assertEqual((json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode(), committed[path], path)

    @cost("tool")
    def test_a_preparation_failure_has_two_times_and_each_has_its_scope(self):
        """The job failed while its checker was being built: 41 s went by, and its requested steps took none."""
        snapshot = records.Snapshot(self.root, PINNED)
        job_id = "20261127-054106-trace-individually-approved-ordinary-ups"
        path = snapshot.receipts()[job_id][0]
        receipt = json.loads(snapshot.read([path])[path])
        self.assertEqual((receipt["wallSeconds"] > 40, receipt["usage"]["wallSeconds"]), (True, 0))
        self.assertEqual([(s["index"], s["status"]) for s in receipt["steps"] if s["status"] != "skipped"][0][0], 0)
        self.assertEqual(records.index_entry(receipt, "x")["wallSeconds"], 0)


if __name__ == "__main__":
    unittest.main()
