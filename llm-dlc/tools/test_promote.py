#!/usr/bin/env python3
"""Tests for `sync.py promote` (promote.py): the promotion as a transaction, on a real jj repository with a bare git
remote, a candidate workspace and a private archive on disk. The trace tools' own steps (check, upload, the index)
and the default run are stood in for: what is tested is which commits are frozen, what blocks, and when `main` and
`develop` move. Every value is made up. Run: python3 llm-dlc/tools/test_promote.py"""
from __future__ import annotations

import contextlib
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import artifacts
import checkpoint
import promote
import sync
from test_checkpoint import Sandbox

sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

SESSION = "11111111-2222-4333-8444-555555555555"
LOG_BYTES = b'{"made": "up"}\n'
LOG = hashlib.sha256(LOG_BYTES).hexdigest()
PASSED = {"tree": "c0ffee" * 6 + "c0ff", "commit": "0" * 40, "when": "2026-11-21T10:00:00+0000", "tally": "default tier: 9 of 9 passed"}


def paths(root: Path) -> dict:
    changes = root / "llm-dlc"
    return {"REPO": root, "CHANGES": changes, "TRACES": changes / "traces", "INDEX": changes / "index.json",
            "CHANGES_README": changes / "README.md", "ALLOWLIST": changes / "allowlist.json",
            "REVIEWED": changes / "reviewed-findings.json",
            "jj": lambda *args: subprocess.run([sync.JJ, "--quiet", *args], cwd=root, capture_output=True, text=True)}


class Promotion(Sandbox):
    def setUp(self):
        super().setUp()
        base = Path(self.tmp.name)
        self.candidate = base / "candidate"
        os.environ.pop("ITL_ORIGINALS_OFF", None)
        os.environ.update({"ITL_ORIGINALS_CACHE": str(base / "cache"), "ITL_ORIGINALS_STORE": f"dir:{base / 'store'}",
                           "ITL_ORIGINALS_RESERVE": "0", "ITL_ORIGINALS_UPLOAD": "manual", "ITL_PROMOTE_WORKSPACE": str(self.candidate)})
        self.covered, self.suite_passes, self.suite_runs, self.upload_fails, self.check_status = None, True, 0, False, 0
        mine = {"cmd_check": lambda *a, **k: self.check_status, "cmd_upload": self.fake_upload, "write_index": self.fake_index,
                "cmd_sync": lambda *a, **k: None,
                "publication_gate": lambda rev: [], "cmd_regenerate": lambda args: self.fake_index() or 0}
        self.mine = [mock.patch.object(sync, name, value) for name, value in mine.items()]
        self.mine += [mock.patch.object(promote, "run_inside", self.inside),
                      mock.patch.object(promote, "covering", lambda s, tree: self.covered),
                      mock.patch.object(promote, "run_default", self.fake_default_run)]
        for p in self.mine:
            p.start()
        self.commit("Ignore the logs", {".gitignore": "llm-dlc/traces/*/logs/\n"})
        self.assertEqual(self.run_checkpoint("--bootstrap")[0], 0)

    def tearDown(self):
        for p in reversed(self.mine):
            p.stop()
        super().tearDown()

    # ----- stand-ins for the candidate checkout's own tools

    def inside(self, s, candidate, path, skipped):
        with contextlib.ExitStack() as stack:
            for name, value in paths(candidate).items():
                stack.enter_context(mock.patch.object(sync, name, value))
            return promote.inside(sync, path, skipped)

    def fake_upload(self, include_at=False, full=False):
        failed = 0
        for sid, m in sync.all_manifests().items():
            for sha, info in (m.get("logs") or {}).items():
                if not info.get("url") and not info.get("withdrawn"):
                    if self.upload_fails or not sync.log_path(sid, sha).exists():
                        failed += 1
                        continue
                    info["url"] = f"https://cdn.example/{sid}/{sha}.jsonl.gz"
            sync.save_manifest(sid, m)
        return 1 if failed else 0

    def fake_index(self):
        rows = {sid: sorted(sha for sha, i in (m.get("logs") or {}).items() if i.get("url")) for sid, m in sync.all_manifests().items()}
        sync.INDEX.parent.mkdir(parents=True, exist_ok=True)
        sync.INDEX.write_text(json.dumps(rows, sort_keys=True) + "\n")

    def fake_default_run(self, s, log):
        self.suite_runs += 1
        log.write_text("made-up output of the default run\n")
        if self.suite_passes:
            self.covered = PASSED
        return 0 if self.suite_passes else 1

    # ----- helpers

    def traced(self, message, files, stored=True):
        """A commit with a session's trailer, its manifest in the tree and (unless not `stored`) its log in the
        workspace that made it, where git does not see it."""
        if stored:
            log = self.root / f"llm-dlc/traces/{SESSION}/logs/{LOG}.jsonl.gz"
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_bytes(gzip.compress(LOG_BYTES, mtime=0))
        manifest = {"schema": sync.SCHEMA, "session_id": SESSION, "logs": {LOG: {"bytes": len(LOG_BYTES), "url": None}}}
        return self.commit(f"{message}\n\nLLM-Trace: {SESSION} sha256:{LOG}",
                           {**files, f"llm-dlc/traces/{SESSION}/manifest.json": json.dumps(manifest)})

    def checkpointed(self, rev="@-"):
        status, _, err = self.run_checkpoint("--rev", rev)
        self.assertEqual(status, 0, err)
        return self.remote_ref()

    def run_promote(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = promote.cmd_promote(sync, list(args))
        return status, out.getvalue(), err.getvalue()

    def state(self, base, head):
        return json.loads(promote.state_path(sync, base, head).read_text())

    def show(self, rev, path):
        r = subprocess.run(["git", "-C", str(self.root), "show", f"{rev}:{path}"], capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None

    def parents(self, rev):
        return subprocess.run(["git", "-C", str(self.root), "rev-parse", f"{rev}^@"], capture_output=True, text=True).stdout.split()


class Promote(Promotion):
    @cost("tool")
    def test_a_promotion_freezes_develop_records_its_evidence_in_a_commit_of_its_own_and_moves_main(self):
        base = self.remote_ref("main")
        self.traced("First slice", {"lib/b.txt": "two\n"})
        self.commit("Second slice", {"lib/c.txt": "three\n"})
        head = self.checkpointed()
        (self.root / "lib/a.txt").write_text("someone is half way through this\n")  # the asking workspace is dirty
        self.covered = PASSED
        status, out, err = self.run_promote("--rev", "@-")
        self.assertEqual(status, 0, err + out)
        main = self.remote_ref("main")
        self.assertEqual(self.parents(main), [head])
        self.assertEqual(self.remote_ref("develop"), main)
        self.assertEqual((self.suite_runs, (self.root / "lib/a.txt").read_text()), (0, "someone is half way through this\n"))
        # The record is generated files only: the log's URL, the index, and one small summary.
        changed = subprocess.run(["git", "-C", str(self.root), "diff", "--name-only", head, main], capture_output=True, text=True).stdout.split()
        state = self.state(base, head)
        self.assertEqual(sorted(changed), sorted(["llm-dlc/index.json", f"llm-dlc/traces/{SESSION}/manifest.json", state["summary"]]))
        self.assertTrue(json.loads(self.show(main, f"llm-dlc/traces/{SESSION}/manifest.json"))["logs"][LOG]["url"])
        summary = json.loads(self.show(main, state["summary"]))
        self.assertEqual(promote.summary_problems(summary, len(self.show(main, state["summary"]))), [])
        self.assertEqual(summary["source"], {"base": base, "frozen": head, "frozen_tree": summary["source"]["frozen_tree"],
                                             "commits": 3, "source_commits": 3, "jobs": 0})
        self.assertEqual(summary["evidence"]["trace_logs"], {"public": 1, "withdrawn": 0})
        self.assertNotIn(main, self.show(main, state["summary"]))  # a commit cannot hold its own hash; the receipt does
        # The inventory, the gate's record and the receipt are in the private archive, the first two verified
        # before main moved; a reader with nothing but the store restores the inventory and finds every commit in it.
        self.assertEqual((state["stage"], state["main"]["after"], state["main"]["observed"], state["gate"]["covering_run"]),
                         ("promoted", main, main, PASSED))
        reader = artifacts.Reader(cache=Path(self.tmp.name) / "elsewhere")
        kinds = {d["kind"]: d for d in reader.find(remote_only=True, run=state["id"])}
        self.assertEqual({k: d["custody"]["state"] for k, d in kinds.items() if k != "promotion-receipt"},
                         {"promotion-inventory": "remote_verified", "promotion-gate": "remote_verified"})
        self.assertEqual(kinds["promotion-inventory"]["id"], summary["archive"]["occurrence"])
        reader.fetch(summary["archive"]["occurrence"], Path(self.tmp.name) / "restored")
        inventory = (Path(self.tmp.name) / "restored" / f"promotions/{state['id']}/inventory.json").read_bytes()
        self.assertEqual(hashlib.sha256(inventory).hexdigest(), summary["archive"]["sha256"])
        self.assertEqual([c["commit"] for c in json.loads(inventory)["commits"]][0], head)
        self.assertIn("Source changes, by finished change", out)
        self.assertIn("nothing to promote", self.run_promote("--rev", head)[1])

    @cost("tool")
    def test_a_failing_default_run_leaves_main_where_it_was_and_the_same_command_continues(self):
        base = self.remote_ref("main")
        self.traced("A slice", {"lib/b.txt": "two\n"})
        head = self.checkpointed()
        self.suite_passes = False
        status, _, err = self.run_promote("--rev", "@-")
        self.assertEqual((status, self.remote_ref("main"), self.remote_ref("develop"), self.suite_runs), (1, base, head, 1))
        self.assertIn("did not pass", err)
        state = self.state(base, head)
        self.assertEqual((state["stage"], state["gate"]["passed"], state["gate"]["exit"]), ("gate failed", False, 1))
        self.assertIn("did not pass", state["last_failure"]["reason"])
        candidate = state["candidate"]
        # Fixed (here: the suite passes now): the same promotion, the same record, one run more, and main moves.
        self.suite_passes = True
        status, out, err = self.run_promote("--rev", head)
        self.assertEqual((status, self.remote_ref("main"), self.suite_runs), (0, candidate, 2), err)
        after = self.state(base, head)
        self.assertEqual((after["id"], after["gate"]["ran_here"], "last_failure" in after), (state["id"], True, False))

    @cost("tool")
    def test_develop_moving_on_does_not_enlarge_the_frozen_set_and_takes_the_record_in_by_a_merge(self):
        base = self.remote_ref("main")
        self.traced("A slice", {"lib/b.txt": "two\n"})
        head = self.checkpointed()
        later = self.commit("Later work", {"lib/later.txt": "not part of this promotion\n"})
        self.checkpointed()
        self.covered = PASSED
        status, out, err = self.run_promote("--rev", head)
        self.assertEqual(status, 0, err + out)
        main, develop = self.remote_ref("main"), self.remote_ref("develop")
        self.assertEqual(self.parents(main), [head])
        self.assertIsNone(self.show(main, "lib/later.txt"))
        self.assertEqual(self.state(base, head)["commits"], 2)
        self.assertIn("1 commit(s) further on", out)
        self.assertEqual(sorted(self.parents(develop)), sorted([later, main]))
        self.assertEqual(self.show(develop, "lib/later.txt"), "not part of this promotion\n")
        self.assertTrue(json.loads(self.show(develop, f"llm-dlc/traces/{SESSION}/manifest.json"))["logs"][LOG]["url"])
        # The next promotion starts from the new main, and covers the later work and the merge alone.
        status, out, err = self.run_promote("--rev", develop, "--dry-run")
        self.assertEqual(status, 0, err)
        self.assertIn(f"{main[:12]} -> `develop` commit {develop[:12]}: 2 commit(s)", out)

    @cost("tool")
    def test_main_moving_refuses_the_promotion_until_the_line_takes_it_in(self):
        self.traced("A slice", {"lib/b.txt": "two\n"})
        head = self.checkpointed()
        self.covered = PASSED
        moved = self.elsewhere("main")  # another promotion, from another machine
        status, _, err = self.run_promote("--rev", head)
        self.assertEqual((status, self.remote_ref("main")), (1, moved))
        self.assertIn("fetch first", err)
        self.jj("git", "fetch", "--remote", "origin")
        status, _, err = self.run_promote("--rev", head)
        self.assertEqual((status, self.remote_ref("main")), (1, moved))
        self.assertIn("another promotion moved it", err)
        # It moves between the freeze and the push: the push itself is refused, and nothing is forced.
        self.jj("new", head, moved, "-m", "Merge main into the line")
        self.jj("new")
        merged = self.checkpointed()
        real = promote.gate_candidate

        def moving(s, state, skipped):
            real(s, state, skipped)
            self.moved_again = self.elsewhere("main", "again.txt")
        with mock.patch.object(promote, "gate_candidate", moving):
            status, _, err = self.run_promote("--rev", merged)
        self.assertEqual((status, self.remote_ref("main")), (1, self.moved_again))
        self.assertIn("not promoted", err)
        self.assertEqual(self.remote_ref("develop"), merged)

    @cost("tool")
    def test_a_lost_answer_and_a_kill_after_the_push_are_one_promotion(self):
        base = self.remote_ref("main")
        self.traced("A slice", {"lib/b.txt": "two\n"})
        head = self.checkpointed()
        self.covered = PASSED
        real = checkpoint.git

        def lossy(s, *args, **kwargs):
            r = real(s, *args, **kwargs)
            if args[0] == "push":  # the remote took it; the answer never came back
                return subprocess.CompletedProcess(r.args, 128, b"", b"fatal: the remote end hung up unexpectedly")
            return r
        with mock.patch.object(checkpoint, "git", lossy), \
                mock.patch.object(promote, "forward", side_effect=KeyboardInterrupt("killed after the push")):
            with self.assertRaises(KeyboardInterrupt):
                self.run_promote("--rev", head)
        main = self.remote_ref("main")
        state = self.state(base, head)
        self.assertEqual((self.parents(main), state["stage"], state["candidate"]), ([head], "pushed", main))
        self.assertIn("answer was lost", state["main"]["pushed"])
        # The same command again: no second record, no second push; the promotion's own end is written.
        status, out, err = self.run_promote("--rev", head)
        self.assertEqual((status, self.remote_ref("main"), self.remote_ref("develop")), (0, main, main), err)
        after = self.state(base, head)
        self.assertEqual((after["id"], after["stage"], after["candidate"]), (state["id"], "promoted", main))
        self.assertEqual(len(list(promote.promotions(sync).glob("*.json"))), 1)

    @cost("tool")
    def test_a_frozen_commit_whose_log_is_nowhere_is_named_and_blocks(self):
        base = self.remote_ref("main")
        self.traced("A slice", {"lib/b.txt": "two\n"}, stored=False)
        head = self.checkpointed()
        self.covered = PASSED
        status, out, _ = self.run_promote("--rev", head, "--dry-run")
        self.assertEqual(status, 0)
        self.assertIn(f"MISSING {SESSION}/{LOG[:12]}: commit {head[:12]} points at it", out)
        self.assertIn("1 thing(s) above would block", out)
        self.assertFalse(self.candidate.exists())  # a dry run builds nothing
        status, _, err = self.run_promote("--rev", head)
        self.assertEqual((status, self.remote_ref("main")), (1, base))
        self.assertIn("the receipt of 1 log(s) of the frozen commits is missing", err)
        self.assertIn("no workspace of this machine stores it", err)
        # The log turns up (its workspace is back): the same promotion goes through.
        log = self.root / f"llm-dlc/traces/{SESSION}/logs/{LOG}.jsonl.gz"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_bytes(gzip.compress(LOG_BYTES, mtime=0))
        status, _, err = self.run_promote("--rev", head)
        self.assertEqual(status, 0, err)
        self.assertEqual(self.parents(self.remote_ref("main")), [head])

    @cost("tool")
    def test_an_original_not_yet_verified_blocks_and_one_never_captured_is_a_disclosed_gap(self):
        base = self.remote_ref("main")
        result = lambda job: {f"verification/results/{job}/result.json": json.dumps({"id": job, "status": "passed"})}
        self.commit("Results", {**result("20261121-made-up-old"), **result("20261121-made-up-new"), "lib/b.txt": "two\n"})
        head = self.checkpointed()
        self.covered = PASSED
        work = Path(self.tmp.name) / "run"
        work.mkdir()
        (work / "1-run.log").write_text("the whole log\n")
        archive = artifacts.Archive()
        record = archive.capture(work, "job-run", "verification/results/20261121-made-up-new", job="20261121-made-up-new", attempt=1)
        archive.close()
        with mock.patch.object(artifacts, "store_for", side_effect=artifacts.Unavailable("the store does not answer")):
            status, _, err = self.run_promote("--rev", head)
        self.assertEqual((status, self.remote_ref("main")), (1, base), err)
        self.assertIn("not verified in the private archive", err)
        self.assertIn(record["id"], err)
        status, out, err = self.run_promote("--rev", head)  # it answers again: the pass settles what was pending
        self.assertEqual(status, 0, err)
        main = self.remote_ref("main")
        summary = json.loads(self.show(main, self.state(base, head)["summary"]))
        self.assertEqual(summary["evidence"]["originals"], {"by_kind": {"job-run": {"remote_verified": 1}}, "gaps": 1})
        self.assertIn("1 job(s) have no original in the archive", out)

    @cost("tool")
    def test_only_a_commit_of_develop_and_nothing_but_main(self):
        base = self.remote_ref("main")
        self.traced("A slice", {"lib/b.txt": "two\n"})
        for args in (["--rev", "@-", "--force"], ["--rev", "@-", "--bookmark", "develop"], ["--all"], ["--rev", "@-", "x:refs/heads/main"]):
            status, _, err = self.run_promote(*args)
            self.assertEqual(status, 2, args)
            self.assertIn("is not for this command", err)
        status, _, err = self.run_promote("--rev", "@-")  # committed, and not on develop
        self.assertEqual((status, self.remote_ref("main")), (1, base))
        self.assertIn("checkpoint it first", err)
        self.assertIn("uncommitted work", self.run_promote("--rev", "@")[2])
        self.assertFalse(self.candidate.exists())
        # The user's word alone promotes without a covering run, and the receipt says so.
        head = self.checkpointed()
        status, _, err = self.run_promote("--rev", head, "--skip-tests", "made-up reason")
        self.assertEqual((status, self.suite_runs), (0, 0), err)
        gate = self.state(base, head)["gate"]
        self.assertEqual((gate["skipped"], gate["covering_run"]), ("made-up reason", None))

    @cost("tool")
    def test_a_summary_over_its_budget_or_with_a_credentials_field_is_not_published(self):
        doc = {"schema": promote.SUMMARY_SCHEMA, "kind": "promotion", "id": "x", "source": {}, "evidence": {}, "archive": {},
               "disposition": "published", "policy": {}}
        self.assertEqual(promote.summary_problems(doc, 100), [])
        self.assertIn("over the", promote.summary_problems(doc, promote.SUMMARY_MAX + 1)[0])
        self.assertIn("holds `x-amz-signature`", promote.summary_problems({**doc, "archive": {"url": "https://h/o?X-Amz-Signature=0"}}, 100))
        self.assertIn("no `archive`", promote.summary_problems({k: v for k, v in doc.items() if k != "archive"}, 100))
        # In git such a file is refused at the checkpoint too, with the whole of the redactor's rules.
        self.commit("A bulky summary", {"llm-dlc/artifacts/2026/11/21/promotion-x.json": "x" * (promote.SUMMARY_MAX + 1)})
        status, out, _ = self.run_checkpoint("--rev", "@-")
        self.assertEqual(status, 1)
        self.assertIn("over what a publication summary may be", out)


if __name__ == "__main__":
    unittest.main()
