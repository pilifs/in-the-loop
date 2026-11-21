#!/usr/bin/env python3
"""Tests for artifacts.py, the private archive of original outputs: capture into the spool, the journal across
crashes, the uploader against a store that fails the ways a network does, and reads from a fresh cache with
nothing but the store. Every value here is made up. Run: python3 llm-dlc/tools/test_artifacts.py"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import artifacts
from artifacts import Archive, DirStore, Reader, StoreError, Unavailable


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {
            "ITL_ORIGINALS_HOME": str(self.dir / "home"), "ITL_ORIGINALS_CACHE": str(self.dir / "cache"),
            "ITL_ORIGINALS_STORE": f"dir:{self.dir / 'store'}", "ITL_ORIGINALS_RESERVE": "0"})
        self.env.start()
        os.environ.pop("ITL_ORIGINALS_OFF", None)
        self.archive = Archive()
        self.stores = {a: DirStore(self.dir / "store", b) for a, b in artifacts.BUCKETS.items()}

    def tearDown(self):
        self.archive.close()
        self.env.stop()
        self.tmp.cleanup()

    def tree(self, name="work", files=None) -> Path:
        root = self.dir / name
        for rel, data in (files or {"logs/1-run.log": b"line\n" * 10, "outputs/a.json": b"{}\n", "empty": b""}).items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(data)
        return root

    def upload(self):
        return self.archive.upload(stores=self.stores)

    def state(self, occurrence: str) -> str:
        return self.archive.db.execute("SELECT state FROM occurrences WHERE id=?", (occurrence,)).fetchone()[0]

    def fresh_reader(self, name="elsewhere", **kwargs) -> Reader:
        """A reader on another machine: an empty cache, no journal, only the store."""
        return Reader(cache=self.dir / name, **kwargs)

    def restored(self, base: Path) -> dict[str, bytes]:
        return {p.relative_to(base).as_posix(): p.read_bytes() for p in sorted(base.rglob("*")) if p.is_file() and not p.is_symlink()}


class Capture(Case):
    def test_a_tree_is_sealed_with_every_member_in_its_inventory(self):
        root = self.tree(files={"a/x.txt": b"x" * 10, "a/empty": b"", "b/bin": bytes(range(256)) * 4})
        os.symlink("x.txt", root / "a/link")
        os.chmod(root / "b/bin", 0o755)
        (root / "hollow").mkdir()
        record = self.archive.capture(root, "job-outputs", "verification/results/made-up/outputs", job="made-up", attempt=1)
        self.assertEqual(record["status"], "complete")
        self.assertEqual(record["access"], "ordinary")
        self.assertEqual(record["raw"]["bytes"], 10 + 1024)
        manifest = json.loads(gzip.decompress(self.archive.object_path("ordinary", record["inventory"]["sha256"], "gzip").read_bytes()))
        by = {m["path"]: m for m in manifest["members"]}
        self.assertEqual(sorted(by), ["a", "a/empty", "a/link", "a/x.txt", "b", "b/bin", "hollow"])
        self.assertEqual(by["a/empty"], {"path": "a/empty", "type": "file", "mode": by["a/empty"]["mode"], "bytes": 0,
                                         "sha256": sha(b""), "parts": []})
        self.assertEqual(by["a/link"], {"path": "a/link", "type": "symlink", "target": "x.txt"})
        self.assertEqual(by["hollow"]["type"], "dir")
        self.assertEqual(by["b/bin"]["mode"], "755")
        self.assertEqual(by["b/bin"]["sha256"], sha(bytes(range(256)) * 4))
        self.assertEqual(record["inventory"]["members"], 7)
        self.assertEqual(self.state(record["id"]), "locally_sealed")

    def test_the_same_path_captured_twice_is_two_occurrences_and_each_keeps_its_bytes(self):
        root = self.tree(files={"result.json": b'{"attempt": 1}\n'})
        first = self.archive.capture(root / "result.json", "job-result", "verification/results/j/result.json", job="j", attempt=1)
        (root / "result.json").write_bytes(b'{"attempt": 2}\n')  # the retry reuses the path
        second = self.archive.capture(root / "result.json", "job-result", "verification/results/j/result.json", job="j", attempt=2)
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual([first["raw"]["sha256"], second["raw"]["sha256"]], [sha(b'{"attempt": 1}\n'), sha(b'{"attempt": 2}\n')])
        self.upload()
        reader = self.fresh_reader()
        for record, data in ((first, b'{"attempt": 1}\n'), (second, b'{"attempt": 2}\n')):
            out = self.dir / f"out-{record['attempt']}"
            reader.fetch(record["id"], out)
            self.assertEqual((out / "verification/results/j/result.json").read_bytes(), data)

    def test_identical_bytes_are_stored_once_and_reported_as_separate_occurrences(self):
        a = self.archive.capture(self.tree("one", {"log": b"same\n" * 300000}), "job-logs", "one", job="a", attempt=1)
        b = self.archive.capture(self.tree("two", {"log": b"same\n" * 300000}), "job-logs", "two", job="b", attempt=1)
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(self.archive.db.execute("SELECT COUNT(*) FROM objects WHERE role='part'").fetchone()[0], 1)
        self.assertEqual(self.archive.db.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0], 2)

    def test_an_interrupted_producer_is_sealed_as_partial_with_what_never_materialized(self):
        root = self.tree(files={"logs/1-build.log": b"built\n"})
        record = self.archive.capture(root, "job-logs", "j/logs", job="j", attempt=1,
                                      expected=["logs/1-build.log", "logs/2-prove.log", "outputs"])
        self.assertEqual(record["status"], "partial")
        self.assertEqual(record["absent"], ["logs/2-prove.log", "outputs"])
        gone = self.archive.capture(self.dir / "never-made", "job-outputs", "j/outputs", job="j", attempt=1)
        self.assertEqual((gone["status"], gone["gap"]["lost"], self.state(gone["id"])), ("missing", False, "missing_input"))

    def test_an_unclassified_kind_goes_to_restricted_custody(self):
        record = self.archive.capture(self.tree(), "something-new", "new/thing")
        self.assertEqual(record["access"], "restricted")
        self.assertTrue(list((self.dir / "home/spool/restricted").rglob("*.gz")))
        self.assertFalse((self.dir / "home/spool/ordinary").exists())

    def test_a_large_file_is_stored_in_parts_and_small_ones_in_bounded_packs(self):
        with mock.patch.object(artifacts, "PART_MAX", 3 << 20), mock.patch.object(artifacts, "PACK_MAX", 4096):
            big = os.urandom(7 << 20) + b"tail"
            small = {f"cases/p{i}/native.json": json.dumps({"case": i}).encode() * 40 for i in range(40)}
            root = self.tree(files={"big.bin": big, **small})
            record = self.archive.capture(root, "selector-cases", "examples/x/records/cases", run="r")
        roles = dict(self.archive.db.execute("SELECT role, COUNT(*) FROM objects GROUP BY role").fetchall())
        self.assertEqual(roles["part"], 3)  # 7 MiB and a tail, in parts of at most 3 MiB
        self.assertGreater(roles["pack"], 1)
        self.assertLessEqual(self.archive.db.execute("SELECT MAX(raw_bytes) FROM objects WHERE role='pack'").fetchone()[0], 4096 + 1024)
        self.upload()
        out = self.dir / "out"
        self.fresh_reader().fetch(record["id"], out, flat=True)
        self.assertEqual(self.restored(out), {"big.bin": big, **small})

    def test_a_capture_that_would_fill_the_disk_seals_nothing_and_says_to_keep_the_source(self):
        root = self.tree()
        with mock.patch.dict(os.environ, {"ITL_ORIGINALS_RESERVE": str(1 << 60)}):
            with self.assertRaises(artifacts.SpoolFull):
                self.archive.capture(root, "job-logs", "j/logs", job="j")
        self.assertEqual(self.archive.db.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0], 0)
        self.assertEqual(list((self.dir / "home/spool").rglob("*.gz")), [])
        self.assertTrue((root / "logs/1-run.log").exists())

    def test_switched_off_it_does_nothing(self):
        with mock.patch.dict(os.environ, {"ITL_ORIGINALS_OFF": "1"}):
            self.assertIsNone(self.archive.capture(self.tree(), "job-logs", "j/logs"))
            self.assertIsNone(self.archive.missing("job-logs", "j/logs", "made up"))
        self.assertEqual(self.archive.db.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0], 0)

    def test_attempts_are_numbered_per_job(self):
        self.assertEqual([self.archive.begin_attempt("j"), self.archive.begin_attempt("j"), self.archive.begin_attempt("k")], [1, 2, 1])


class Streams(Case):
    def test_an_append_only_file_is_sealed_as_segments_and_any_past_prefix_restores(self):
        path = self.dir / "session.jsonl"
        path.write_bytes(b"one\n")
        first = self.archive.capture_stream(path, "session/s1", "session-transcript", "sessions/s1.jsonl", session="s1")
        self.assertIsNone(self.archive.capture_stream(path, "session/s1", "session-transcript", "sessions/s1.jsonl", session="s1"))
        with open(path, "ab") as f:
            f.write(b"two\n" * 400000)
        second = self.archive.capture_stream(path, "session/s1", "session-transcript", "sessions/s1.jsonl", session="s1")
        with open(path, "ab") as f:
            f.write(b"three\n")
        third = self.archive.capture_stream(path, "session/s1", "session-transcript", "sessions/s1.jsonl", session="s1")
        self.assertEqual(second["stream"]["offset"], 4)
        self.assertEqual(second["stream"]["predecessor"], first["id"])
        self.assertEqual(third["stream"]["prefix_sha256"], sha(path.read_bytes()))
        self.assertEqual(third["raw"]["bytes"], 6)
        self.assertEqual({first["access"], third["access"]}, {"restricted"})
        # the restricted archive is the watcher's: read here with the journal's own copies
        self.upload()
        reader = self.fresh_reader()
        with self.assertRaises(Unavailable) as refused:
            reader.fetch(second["id"], self.dir / "out", prefix=True)
        self.assertIn("restricted", str(refused.exception))

    def test_a_past_prefix_of_an_ordinary_stream_restores_exactly(self):
        path = self.dir / "run.log"
        versions = []
        for chunk in (b"alpha\n", b"beta\n" * 250000, b"gamma\n"):
            with open(path, "ab") as f:
                f.write(chunk)
            versions.append((self.archive.capture_stream(path, "log/run", "job-logs", "runs/run.log", run="r"), path.read_bytes()))
        self.upload()
        reader = self.fresh_reader()
        for i, (record, data) in enumerate(versions):
            out = self.dir / f"out{i}"
            done = reader.fetch(record["id"], out, prefix=True)
            self.assertEqual((out / "runs/run.log").read_bytes(), data)
            self.assertEqual(done["segments"], i + 1)

    def test_truncation_and_replacement_start_a_new_generation_and_keep_the_old(self):
        path = self.dir / "run.log"
        path.write_bytes(b"first version\n")
        old = self.archive.capture_stream(path, "log/run", "job-logs", "runs/run.log")
        path.write_bytes(b"short\n")
        cut = self.archive.capture_stream(path, "log/run", "job-logs", "runs/run.log")
        path.write_bytes(b"other bytes of the same length or more\n")
        swapped = self.archive.capture_stream(path, "log/run", "job-logs", "runs/run.log")
        self.assertEqual([old["stream"]["generation"], cut["stream"]["generation"], swapped["stream"]["generation"]], [1, 2, 3])
        self.assertEqual(cut["stream"]["why"], "truncated")
        self.assertIn("replaced", swapped["stream"]["why"])
        self.assertEqual([cut["stream"]["offset"], swapped["stream"]["predecessor"]], [0, None])
        self.upload()
        out = self.dir / "out"
        self.fresh_reader().fetch(old["id"], out, prefix=True)
        self.assertEqual((out / "runs/run.log").read_bytes(), b"first version\n")


class Transcripts(Case):
    def test_a_synced_session_is_sealed_as_streams_and_a_file_outside_a_clients_store_is_not(self):
        import sync
        home = self.dir / "user"
        folder = home / ".claude/projects/-made-up-project"
        (folder / "s1/subagents").mkdir(parents=True)
        (folder / "s1.jsonl").write_bytes(b'{"turn": 1}\n')
        (folder / "s1/subagents/agent-a.jsonl").write_bytes(b'{"sub": 1}\n')
        stray = self.dir / "copy.jsonl"
        stray.write_bytes(b'{"turn": 1}\n')
        with mock.patch.object(Path, "home", lambda: home), mock.patch.dict(os.environ, {"ITL_ORIGINALS_UPLOAD": "manual"}):
            self.assertEqual(artifacts.transcript_key(folder / "s1.jsonl"), "claude/-made-up-project/s1.jsonl")
            self.assertIsNone(artifacts.transcript_key(stray))
            sync.seal_transcripts([folder / "s1.jsonl", stray])
            sync.seal_transcripts([folder / "s1.jsonl"])  # nothing gained: nothing sealed
            with open(folder / "s1.jsonl", "ab") as f:
                f.write(b'{"turn": 2}\n')
            sync.seal_transcripts([folder / "s1.jsonl"])
        rows = self.archive.rows()
        self.assertEqual([(r["kind"], r["access"], r["session"], r["stream"]["key"], r["stream"]["offset"]) for r in rows], [
            ("session-transcript", "restricted", "s1", "claude/-made-up-project/s1.jsonl", 0),
            ("session-transcript", "restricted", "s1", "claude/-made-up-project/s1/subagents/agent-a.jsonl", 0),
            ("session-transcript", "restricted", "s1", "claude/-made-up-project/s1.jsonl", 12)])

    def test_a_workspaces_run_records_are_sealed_file_by_file_as_they_grow_and_a_tests_folder_is_not(self):
        import sync
        folder = self.dir / "made-up-workspace/llm-dlc/loop-summaries"
        (folder / "single-made-up").mkdir(parents=True)
        (folder / "2026-01-01-000000-made-up.md").write_text("cycle 1\n")
        (folder / "single-made-up/events.jsonl").write_text('{"n": 1}\n')
        with mock.patch.dict(os.environ, {"ITL_ORIGINALS_UPLOAD": "manual"}):
            with mock.patch.object(sync, "LOOP_SUMMARIES", folder):       # as a test of sync points it: not this checkout's
                self.assertEqual(sync.seal_run_records(), 0)
            self.assertEqual(self.archive.rows(), [])
            self.assertEqual(sync.seal_run_records(folder), 2)
            with mock.patch.object(artifacts.Archive, "capture_stream", side_effect=AssertionError("opened an unchanged file")):
                self.assertEqual(sync.seal_run_records(folder), 0)        # same sizes and times: no file is read
            with open(folder / "single-made-up/events.jsonl", "a") as f:
                f.write('{"n": 2}\n')
            (folder / "2026-01-01-000000-made-up.md").write_text("cycle 1, rewritten\n")
            self.assertEqual(sync.seal_run_records(folder), 2)
        rows = [(r["kind"], r["access"], r["logical"], r["stream"]["key"], r["stream"]["generation"], r["stream"]["offset"])
                for r in self.archive.rows()]
        md, events = "2026-01-01-000000-made-up.md", "single-made-up/events.jsonl"
        self.assertEqual(rows, [
            ("run-record", "restricted", f"llm-dlc/loop-summaries/{md}", f"run-records/made-up-workspace/{md}", 1, 0),
            ("run-record", "restricted", f"llm-dlc/loop-summaries/{events}", f"run-records/made-up-workspace/{events}", 1, 0),
            ("run-record", "restricted", f"llm-dlc/loop-summaries/{md}", f"run-records/made-up-workspace/{md}", 2, 0),       # rewritten: whole again
            ("run-record", "restricted", f"llm-dlc/loop-summaries/{events}", f"run-records/made-up-workspace/{events}", 1, 9)])  # appended: the gain
        with mock.patch.object(artifacts, "home", side_effect=RuntimeError("made up")), mock.patch.object(sync, "log") as said:
            self.assertEqual(sync.seal_run_records(folder), 0)            # and it never fails a sync
        self.assertIn("made up", said.call_args[0][0])

    def test_sealing_never_fails_a_sync(self):
        import sync
        with mock.patch.object(artifacts, "transcript_key", side_effect=RuntimeError("made up")), mock.patch.object(sync, "log") as said:
            sync.seal_transcripts([self.dir / "anything.jsonl"])
        self.assertIn("made up", said.call_args[0][0])


class Crashes(Case):
    def test_killed_after_the_intake_record_and_before_the_journal_the_occurrence_is_recovered(self):
        root = self.tree()
        with mock.patch.object(Archive, "_journal", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.archive.capture(root, "job-logs", "j/logs", job="j", attempt=1)
        self.assertEqual(self.archive.db.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0], 0)
        again = Archive()  # the next process
        self.assertEqual(again.recover()["occurrences"], 1)
        self.assertEqual(again.recover()["occurrences"], 0)
        row = again.db.execute("SELECT * FROM occurrences").fetchone()
        self.assertEqual((row["state"], row["job"]), ("locally_sealed", "j"))
        again.upload(stores=self.stores)
        out = self.dir / "out"
        self.fresh_reader().fetch(row["id"], out)
        self.assertEqual(self.restored(out / "j/logs"), self.restored(root))
        again.close()

    def test_killed_before_the_intake_record_nothing_is_acknowledged_and_sealed_files_are_found(self):
        root = self.tree(files={"big": os.urandom(2 << 20)})
        with mock.patch.object(artifacts, "write_durably", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.archive.capture(root, "job-logs", "j/logs", job="j", attempt=1)
        found = self.archive.recover()
        self.assertEqual((found["occurrences"], found["damaged"]), (0, []))
        self.assertGreaterEqual(found["orphans"], 1)  # sealed, named by no record: kept, and uploaded like any other
        self.assertEqual(self.archive.db.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0], 0)
        retried = self.archive.capture(root, "job-logs", "j/logs", job="j", attempt=1)  # the producer still has its source
        self.upload()
        self.assertEqual(self.state(retried["id"]), "remote_verified")

    def test_a_damaged_sealed_file_is_reported_and_never_registered(self):
        path = self.dir / "home/spool/ordinary/ab" / ("ab" + "0" * 62 + ".gz")
        path.parent.mkdir(parents=True)
        path.write_bytes(b"not gzip at all")
        found = self.archive.recover()
        self.assertEqual((found["orphans"], found["damaged"]), (0, [str(path)]))


class Uploads(Case):
    def one(self, **kwargs):
        return self.archive.capture(self.tree(files={"log": os.urandom(2 << 20), "small": b"s\n"}), "job-logs", "j/logs", job="j", attempt=1, **kwargs)

    def test_verified_only_after_the_stores_bytes_are_read_back(self):
        record = self.one()
        done = self.upload()
        self.assertEqual(done["objects"], {"remote_verified": 3})  # the part, the pack and the inventory
        self.assertEqual((done["receipts"], done["intents"]), (1, 1))
        self.assertEqual(self.state(record["id"]), "remote_verified")
        self.assertTrue(self.archive.releasable(record["id"]))
        receipt = json.loads((self.dir / "store" / artifacts.BUCKETS["ordinary"] / "occurrences" / artifacts.id_date(record["id"])
                              / f"{record['id']}.json").read_text())
        self.assertEqual(receipt["custody"]["state"], "remote_verified")
        self.assertEqual(receipt["custody"]["objects"], 3)
        self.assertEqual(self.upload()["objects"], {})  # nothing left to do

    def test_store_offline_everything_stays_sealed_and_local_only_then_goes_through(self):
        record = self.one()
        self.stores["ordinary"].faults["put"] = True
        done = self.upload()
        self.assertTrue(done["errors"])
        self.assertFalse(self.archive.releasable(record["id"]))
        status = self.archive.status()
        self.assertIn("on this machine only", status["exposure"])
        self.assertEqual(self.archive.rows(id=record["id"])[0]["custody"]["state"], "retryable_error")
        self.stores["ordinary"].faults.clear()
        self.archive.db.execute("UPDATE objects SET next_try=0")  # the backoff has passed
        self.upload()
        self.assertEqual(self.state(record["id"]), "remote_verified")
        self.assertGreaterEqual(self.archive.status()["objects"]["remote_verified"]["retries"], 1)

    def test_put_accepted_and_the_answer_lost_then_one_outcome_after_restart(self):
        record = self.one()
        self.stores["ordinary"].faults["put-after"] = lambda key: key.startswith("objects/")
        self.upload()
        self.assertEqual(self.state(record["id"]), "retryable_error")
        self.stores["ordinary"].faults.clear()
        again = Archive()  # a restart: the object is in the store, the journal says the attempt may have landed
        again.db.execute("UPDATE objects SET next_try=0")
        again.upload(stores=self.stores)
        self.assertEqual(again.db.execute("SELECT state, COUNT(*) FROM occurrences GROUP BY state").fetchall()[0][:], ("remote_verified", 1))
        receipts = list((self.dir / "store" / artifacts.BUCKETS["ordinary"] / "occurrences").rglob("*.json"))
        self.assertEqual(len(receipts), 1)
        again.close()

    def test_killed_after_the_put_and_before_the_receipt(self):
        record = self.one()
        with mock.patch.object(Archive, "_finalize", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.upload()
        self.assertNotEqual(self.state(record["id"]), "remote_verified")
        self.assertFalse(self.archive.releasable(record["id"]))
        with self.assertRaises(Unavailable) as pending:
            self.fresh_reader().fetch(record["id"], self.dir / "out")
        self.assertIn("pending", str(pending.exception))
        self.upload()
        self.assertEqual(self.state(record["id"]), "remote_verified")

    def test_a_lease_left_by_a_killed_worker_is_taken_up_once_it_runs_out(self):
        record = self.one()
        self.assertEqual(len(self.archive._lease(10)), 3)  # a worker took them and died
        other = Archive()
        self.assertEqual(other._lease(10), [])  # still leased: a second worker leaves them alone
        other.db.execute("UPDATE objects SET lease_until=0")
        other.upload(stores=self.stores)
        self.assertEqual(self.state(record["id"]), "remote_verified")
        self.assertEqual(other.db.execute("SELECT MAX(attempts) FROM objects").fetchone()[0], 2)
        other.close()

    def test_two_workers_uploading_the_same_object_agree(self):
        record = self.one()
        rows = self.archive.db.execute("SELECT * FROM objects").fetchall()
        other = Archive()
        for r in rows:  # both put every object, whatever the journal says of leases
            self.assertEqual(self.archive.upload_object(r, self.stores["ordinary"]), "remote_verified")
            self.assertEqual(other.upload_object(r, self.stores["ordinary"]), "remote_verified")
        self.upload()
        self.assertEqual(self.state(record["id"]), "remote_verified")
        other.close()

    def test_other_bytes_under_the_same_key_are_an_integrity_failure_never_a_success(self):
        record = self.one()
        part = self.archive.db.execute("SELECT * FROM objects WHERE role='part'").fetchone()
        key = self.dir / "store" / artifacts.BUCKETS["ordinary"] / artifacts.object_key(part["digest"], part["encoding"])
        key.parent.mkdir(parents=True)
        key.write_bytes(os.urandom(64))  # someone else's bytes, under this object's name
        done = self.upload()
        self.assertEqual(done["objects"].get("integrity_failure"), 1)
        self.assertEqual(self.state(record["id"]), "integrity_failure")
        self.assertFalse(self.archive.releasable(record["id"]))
        self.assertTrue(self.archive.object_path("ordinary", part["digest"], part["encoding"]).exists())  # still pinned here
        self.assertEqual(list((self.dir / "store").rglob("occurrences/**/*.json")), [])
        self.assertEqual(self.archive.status()["errors"][0]["state"], "integrity_failure")

    def test_a_truncated_object_in_the_store_is_not_verified(self):
        self.one()
        part = self.archive.db.execute("SELECT * FROM objects WHERE role='part'").fetchone()
        stored = self.archive.object_path("ordinary", part["digest"], part["encoding"]).read_bytes()
        key = self.dir / "store" / artifacts.BUCKETS["ordinary"] / artifacts.object_key(part["digest"], part["encoding"])
        key.parent.mkdir(parents=True)
        key.write_bytes(stored[:len(stored) // 2])
        self.assertEqual(artifacts.read_verified(self.stores["ordinary"], artifacts.object_key(part["digest"], part["encoding"]),
                                                 part["digest"], part["encoding"], part["raw_bytes"]), "mismatch")

    def test_many_occurrences_go_up_on_several_threads_and_a_drain_stops_when_nothing_is_left(self):
        made = [self.archive.capture(self.tree(f"t{i}", {"log": os.urandom(1 << 20) + bytes([i]), "small": b"s%d\n" % i}),
                                     "job-logs", f"j{i}/logs", job=f"j{i}", attempt=1) for i in range(12)]
        with mock.patch.object(artifacts, "store_for", lambda access, role="reader": self.stores[access]):
            total = self.archive.drain(workers=4)
        self.assertEqual((total["objects"], total["receipts"], total["intents"], total["errors"]),
                         ({"remote_verified": 36}, 12, 12, []))
        self.assertEqual(total["passes"], 2)  # the second found nothing to do
        self.assertEqual({self.state(m["id"]) for m in made}, {"remote_verified"})
        self.assertEqual(self.archive.db.execute("SELECT MAX(attempts) FROM objects").fetchone()[0], 1)  # each object put once

    def test_a_second_uploader_leaves_the_spool_to_the_first(self):
        import fcntl
        with open(self.dir / "home/uploader.lock", "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            self.assertIsNone(Archive().drain())

    def test_a_kick_is_refused_when_uploads_are_manual_or_capture_is_off(self):
        with mock.patch.dict(os.environ, {"ITL_ORIGINALS_UPLOAD": "manual"}):
            self.assertFalse(artifacts.kick())
        with mock.patch.dict(os.environ, {"ITL_ORIGINALS_OFF": "1"}):
            self.assertFalse(artifacts.kick())

    def test_a_gap_is_recorded_remotely_and_read_as_missing(self):
        gap = self.archive.missing("job-logs", "old/logs/3-prove.log", "shortened before capture existed", lost=True, job="old",
                                   derivatives=[{"what": "head and tail", "where": "verification/results/old/logs/3-prove.log", "sha256": "0" * 64}])
        self.upload()
        self.assertEqual(self.upload()["receipts"], 0)  # written once
        reader = self.fresh_reader()
        listed = reader.find(job="old")
        self.assertEqual([(d["custody"]["state"], d["gap"]["lost"]) for d in listed], [("missing_input", True)])
        with self.assertRaises(Unavailable) as none:
            reader.fetch(gap["id"], self.dir / "out")
        self.assertIn("shortened before capture existed", str(none.exception))


class Reads(Case):
    def verified(self, files=None, **meta):
        root = self.tree(files=files)
        record = self.archive.capture(root, "job-outputs", "verification/results/j/outputs", **{"job": "j", "attempt": 1, **meta})
        self.upload()
        return root, record

    def test_a_fresh_machine_lists_and_restores_from_the_store_alone_then_reads_offline(self):
        nested = {"a/b/c/deep.txt": b"deep\n", "bin/blob": bytes(range(256)) * 9000, "empty": b"", "conflict.orig": b"<<<<<<<\n"}
        root, record = self.verified(nested, run="run-7", source={"commit": "c0ffee" * 6 + "abcd"})
        pending = self.archive.capture(self.tree("later"), "job-logs", "verification/results/k/logs", job="k", attempt=1, run="run-7")
        self.archive.upload(limit=0, stores=self.stores)  # its intent only: nothing verified yet
        reader = self.fresh_reader()
        listed = {d["id"]: d["custody"]["state"] for d in reader.find(run="run-7")}
        self.assertEqual(listed, {record["id"]: "remote_verified", pending["id"]: "pending"})
        self.assertEqual([d["id"] for d in reader.find(source="c0ffee")], [record["id"]])
        self.assertEqual([d["id"] for d in reader.find(digest=record["inventory"]["sha256"])], [record["id"]])
        out = self.dir / "out"
        done = reader.fetch(record["id"], out)
        self.assertEqual(self.restored(out / "verification/results/j/outputs"), nested)
        self.assertEqual((done["files"], done["bytes"]), (4, sum(len(v) for v in nested.values())))
        offline = Reader(cache=self.dir / "elsewhere", offline=True)  # the same cache, no network
        with mock.patch.object(artifacts, "store_for", side_effect=AssertionError("offline reads ask no store")):
            again = self.dir / "again"
            offline.fetch(record["id"], again)
            self.assertEqual(self.restored(again / "verification/results/j/outputs"), nested)
            self.assertEqual([d["id"] for d in offline.find(job="j")], [record["id"]])
        with self.assertRaises(Unavailable):
            Reader(cache=self.dir / "empty", offline=True).fetch(record["id"], self.dir / "none")

    def test_a_damaged_or_missing_object_makes_the_occurrence_unavailable_not_wrong(self):
        root, record = self.verified({"big": os.urandom(2 << 20)})
        part = self.archive.db.execute("SELECT * FROM objects WHERE role='part'").fetchone()
        key = self.dir / "store" / artifacts.BUCKETS["ordinary"] / artifacts.object_key(part["digest"], part["encoding"])
        saved = key.read_bytes()
        key.write_bytes(saved[:-9] + b"corrupted")
        with self.assertRaises(Unavailable) as damaged:
            self.fresh_reader("one").fetch(record["id"], self.dir / "out1")
        self.assertIn("damaged", str(damaged.exception))
        self.assertFalse((self.dir / "out1/verification/results/j/outputs/big").exists())
        key.unlink()
        with self.assertRaises(Unavailable) as missing:
            self.fresh_reader("two").fetch(record["id"], self.dir / "out2")
        self.assertIn("missing", str(missing.exception))
        key.write_bytes(saved)
        self.fresh_reader("three").fetch(record["id"], self.dir / "out3")

    def test_a_cache_damaged_after_it_was_verified_is_caught_on_the_next_read(self):
        root, record = self.verified({"big": os.urandom(2 << 20)})
        reader = self.fresh_reader()
        reader.fetch(record["id"], self.dir / "out")
        cached = max((p for p in (self.dir / "elsewhere/objects").rglob("*") if p.is_file()), key=lambda p: p.stat().st_size)
        cached.write_bytes(b"x" * cached.stat().st_size)
        with self.assertRaises(Unavailable):
            Reader(cache=self.dir / "elsewhere", offline=True).fetch(record["id"], self.dir / "out2")

    def test_a_manifest_with_escaping_or_ambiguous_members_is_refused(self):
        for members in ([{"path": "../up", "type": "file"}], [{"path": "/abs", "type": "file"}],
                        [{"path": "a", "type": "file"}, {"path": "a", "type": "file"}],
                        [{"path": "a", "type": "file"}, {"path": "a/b", "type": "file"}],
                        [{"path": "a//b", "type": "file"}], [{"path": "a/./b", "type": "file"}]):
            with self.assertRaises(artifacts.ManifestError, msg=members):
                artifacts.check_members(members)
        self.assertFalse(artifacts.link_is_safe("a/link", "../../etc/passwd"))
        self.assertFalse(artifacts.link_is_safe("link", "/etc/passwd"))
        self.assertTrue(artifacts.link_is_safe("a/link", "../b/file"))

    def test_an_unsafe_link_is_recorded_and_never_made(self):
        root = self.tree(files={"a/file": b"f\n"})
        os.symlink("/etc/hostname", root / "a/out")
        os.symlink("file", root / "a/in")
        record = self.archive.capture(root, "job-outputs", "j/outputs", job="j", attempt=1)
        self.upload()
        out = self.dir / "out"
        done = self.fresh_reader().fetch(record["id"], out)
        self.assertEqual(done["unsafe_links"], ["a/out"])
        self.assertFalse((out / "j/outputs/a/out").is_symlink())
        self.assertEqual(os.readlink(out / "j/outputs/a/in"), "file")

    def test_a_reader_cannot_write_and_reading_changes_nothing_in_the_store(self):
        root, record = self.verified()
        before = sorted((p.relative_to(self.dir).as_posix(), p.stat().st_mtime_ns) for p in (self.dir / "store").rglob("*") if p.is_file())
        reader = self.fresh_reader()
        with self.assertRaises(StoreError):
            reader.store("ordinary").put_if_absent("occurrences/forged.json", root / "empty")
        reader.fetch(record["id"], self.dir / "out")
        after = sorted((p.relative_to(self.dir).as_posix(), p.stat().st_mtime_ns) for p in (self.dir / "store").rglob("*") if p.is_file())
        self.assertEqual(before, after)
        self.assertFalse(hasattr(reader.store("ordinary"), "delete"))  # nothing here can delete from the store

    def test_the_ordinary_archive_says_only_that_a_restricted_occurrence_exists(self):
        path = self.dir / "transcript.jsonl"
        path.write_bytes(b'{"made-up": "private text"}\n')
        record = self.archive.capture(path, "session-transcript", "sessions/made-up-name.jsonl", session="s1")
        self.upload()
        ordinary = self.dir / "store" / artifacts.BUCKETS["ordinary"]
        stub = json.loads(next(ordinary.rglob("restricted/occurrences/**/*.json")).read_text())
        self.assertNotIn("logical", stub)
        self.assertNotIn("inventory", stub)
        self.assertEqual((stub["id"], stub["access"], stub["custody"]["state"]), (record["id"], "restricted", "remote_verified"))
        self.assertEqual([p for p in ordinary.rglob("objects/**/*") if p.is_file()], [])  # no restricted byte in the ordinary bucket
        self.assertNotIn(b"private text", b"".join(p.read_bytes() for p in ordinary.rglob("*") if p.is_file()))
        listed = self.fresh_reader().find(session="s1")
        self.assertEqual([(d["id"], d["access"], d.get("logical")) for d in listed], [(record["id"], "restricted", None)])
        facts = artifacts.analyze(record["id"], "made-up purpose: count the lines", self.archive)
        self.assertEqual((facts["bytes"], facts["files"]), (len(path.read_bytes()), 1))
        self.assertNotIn("private", json.dumps(facts))
        logged = self.archive.db.execute("SELECT detail FROM events WHERE event='private analysis'").fetchall()
        self.assertEqual([r[0] for r in logged], ["made-up purpose: count the lines"])
        with self.assertRaises(Unavailable):
            artifacts.analyze(record["id"], "  ", self.archive)
        # On a machine that never held it (an empty journal and spool), the same facts come from the store alone,
        # and the read is logged there too; nothing of it is left in a cache.
        elsewhere = artifacts.Archive(self.dir / "another-machine")
        self.addCleanup(elsewhere.close)
        remote = artifacts.analyze(record["id"], "made-up purpose: from the store", elsewhere)
        self.assertEqual((remote["read_from"], facts["read_from"]), ("the store", "this machine"))
        same = ("id", "kind", "access", "bytes", "members", "inventory_sha256", "raw_sha256", "files", "largest_file_bytes", "suffixes")
        self.assertEqual({k: remote[k] for k in same}, {k: facts[k] for k in same})
        self.assertEqual(remote["state"], "remote_verified")
        self.assertNotIn("private", json.dumps(remote))
        self.assertNotIn("made-up-name", json.dumps(remote))
        self.assertEqual(elsewhere.db.execute("SELECT detail FROM events WHERE event='private analysis'").fetchone()[0],
                         "made-up purpose: from the store")
        self.assertEqual([p for p in (self.dir / "another-machine").rglob("*") if p.is_file() and b"private text" in p.read_bytes()], [])
        with self.assertRaisesRegex(Unavailable, "neither in this machine's journal nor verified in the store"):
            artifacts.analyze("20261121T000000Z-0000000000000000", "made-up purpose", elsewhere)

    def test_with_the_store_unreachable_a_list_still_shows_what_this_machine_knows(self):
        record = self.archive.capture(self.tree(), "job-logs", "j/logs", job="j", attempt=1)
        with mock.patch.object(artifacts, "store_for", side_effect=Unavailable("no route")):
            reader = Reader(cache=self.dir / "c", journal=self.archive)
            listed = reader.find(job="j")
        self.assertEqual([(d["id"], d["custody"]["state"]) for d in listed], [(record["id"], "pending")])
        self.assertIn("local only", listed[0]["custody"]["note"])
        self.assertEqual(reader.remote_error, "no route")


class Signing(unittest.TestCase):
    def test_the_signature_agrees_with_the_trace_uploaders(self):
        """The same request signed by sync.py's R2Client and by R2Store: one contract, two callers."""
        import sync
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as tmp:
            credential = Path(tmp) / "made-up"
            credential.write_text("account_id=" + "ab" * 16 + "\naccess_key_id=MADEUPKEY\nsecret_access_key=made-up-secret\nbuckets=b\n")
            store = artifacts.R2Store(credential, "b")
            at = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
            payload = hashlib.sha256(b"body").hexdigest()
            with mock.patch.object(artifacts, "now", lambda: at):
                mine, query = store._signed("PUT", "/b/key", {}, {"content-type": "application/gzip"}, payload)
            theirs = sync.R2Client("ab" * 16, "MADEUPKEY", "made-up-secret").signed_headers(
                "PUT", "/b/key", {"content-type": "application/gzip"}, payload, at)
            self.assertEqual(mine["Authorization"], theirs["Authorization"])
            self.assertEqual(query, "")
            with self.assertRaises(StoreError):
                artifacts.R2Store(credential, "another-bucket")


if __name__ == "__main__":
    unittest.main()
