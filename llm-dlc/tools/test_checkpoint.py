#!/usr/bin/env python3
"""Tests for `sync.py checkpoint` (checkpoint.py), each on a real jj repository with a bare git remote in a temporary
directory. Values that look like credentials are split in the source, so this file raises no finding itself.
Run: python3 llm-dlc/tools/test_checkpoint.py"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import checkpoint
import sync

sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

TOKEN = "gh" + "p_" + "Zx9" * 12          # the shape of a GitHub token, made up
SESSION = "11111111-2222-4333-8444-555555555555"
LOG = "ab" * 32


class Sandbox(unittest.TestCase):
    """A jj repository with a bare remote that has `main`, and sync.py pointed at it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root, self.remote = base / "root", base / "remote.git"
        self.root.mkdir()
        (base / "jj-config.toml").write_text("")
        self.env = mock.patch.dict(os.environ, {"JJ_USER": "Made Up", "JJ_EMAIL": "made-up@example.com",
                                                "JJ_CONFIG": str(base / "jj-config.toml"), "ITL_ORIGINALS_HOME": str(base / "originals"),
                                                "ITL_ORIGINALS_OFF": "1", "GIT_CONFIG_GLOBAL": str(base / "gitconfig")})
        self.env.start()
        changes = self.root / "llm-dlc"
        self.patches = [mock.patch.object(sync, name, value) for name, value in {
            "REPO": self.root, "STATE": base / "state", "CHANGES": changes, "TRACES": changes / "traces",
            "INDEX": changes / "index.json", "CHANGES_README": changes / "README.md", "ALLOWLIST": changes / "allowlist.json",
            "REVIEWED": changes / "reviewed-findings.json",
            "jj": lambda *args: subprocess.run([sync.JJ, "--quiet", *args], cwd=self.root, capture_output=True, text=True),
            # No checkpoint may run a test, sync a session or upload a log: each would raise here.
            "tests_gate": mock.Mock(side_effect=AssertionError("a checkpoint ran the test gate")),
            "cmd_upload": mock.Mock(side_effect=AssertionError("a checkpoint uploaded logs")),
            "cmd_sync": mock.Mock(side_effect=AssertionError("a checkpoint synced sessions")),
        }.items()]
        for p in self.patches:
            p.start()
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        self.jj("git", "init", "--colocate")
        subprocess.run(["git", "-C", str(self.root), "remote", "add", "origin", str(self.remote)], check=True)
        self.commit("base", {"lib/a.txt": "one\n"})
        self.jj("bookmark", "set", "main", "-r", "@-")
        self.jj("git", "push", "--bookmark", "main", "--remote", "origin")

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.env.stop()
        self.tmp.cleanup()

    def jj(self, *args):
        r = subprocess.run(["jj", "--quiet", *args], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def commit(self, message, files=None, delete=()):
        for rel, text in (files or {}).items():
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_bytes(text if isinstance(text, bytes) else text.encode())
        for rel in delete:
            (self.root / rel).unlink()
        self.jj("commit", "-m", message)
        return self.jj("log", "--no-graph", "-r", "@-", "-T", "commit_id").strip()

    def run_checkpoint(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = checkpoint.cmd_checkpoint(sync, list(args))
        return status, out.getvalue(), err.getvalue()

    def remote_ref(self, name="develop"):
        r = subprocess.run(["git", "-C", str(self.remote), "rev-parse", "-q", "--verify", f"refs/heads/{name}"], capture_output=True, text=True)
        return r.stdout.strip() or None

    def bootstrapped(self):
        self.assertEqual(self.run_checkpoint("--bootstrap")[0], 0)
        return self.remote_ref()

    def elsewhere(self, branch, name="elsewhere.txt"):
        """Another machine moves the remote's branch forward by one commit this repository does not have."""
        other = Path(tempfile.mkdtemp(dir=self.tmp.name))
        git = lambda *args: subprocess.run(["git", "-c", "user.name=o", "-c", "user.email=o@example.com", *args], cwd=other, check=True, capture_output=True)
        subprocess.run(["git", "clone", "-q", "--branch", branch, str(self.remote), str(other)], check=True)
        (other / name).write_text("someone else\n")
        git("add", "-A")
        git("commit", "-q", "-m", "elsewhere")
        git("push", "-q", "origin", branch)
        return self.remote_ref(branch)


class Checkpoint(Sandbox):
    @cost("tool")
    def test_bootstrap_creates_develop_where_main_is_once(self):
        main = self.remote_ref("main")
        status, out, _ = self.run_checkpoint("--bootstrap")
        self.assertEqual((status, self.remote_ref()), (0, main))
        self.assertIn("bootstrapped", out)
        self.assertIn("nothing to bootstrap", self.run_checkpoint("--bootstrap")[1])
        self.assertEqual(self.run_checkpoint("--rev", "@-")[0], 0)  # main's commit is develop's: already there

    @cost("tool")
    def test_without_develop_a_checkpoint_says_to_bootstrap(self):
        self.commit("work", {"lib/b.txt": "two\n"})
        status, _, err = self.run_checkpoint("--rev", "@-")
        self.assertEqual((status, self.remote_ref()), (1, None))
        self.assertIn("--bootstrap", err)

    @cost("tool")
    def test_a_dirty_workspace_is_checkpointed_at_its_last_commit_and_left_exactly_as_it_was(self):
        self.bootstrapped()
        manifest = {"logs": {LOG: {"bytes": 10, "url": None}}}
        self.commit(f"First slice\n\nLLM-Trace: {SESSION} sha256:{LOG}",
                    {"lib/b.txt": "two\n", f"llm-dlc/traces/{SESSION}/manifest.json": json.dumps(manifest)})
        head = self.commit("Second slice", {"lib/c.txt": "three\n"})
        # Another session's work in the same working copy: a changed file and a new one, never snapshotted.
        (self.root / "lib/a.txt").write_text("someone is half way through this\n")
        (self.root / "foreign.txt").write_text("not committed\n")
        before = {p: hashlib.sha256((self.root / p).read_bytes()).hexdigest() for p in ("lib/a.txt", "foreign.txt")}
        at = sync.jj("--ignore-working-copy", "log", "--no-graph", "-r", "@", "-T", "commit_id").stdout
        status, out, err = self.run_checkpoint("--rev", "@-")
        self.assertEqual(status, 0, err)
        self.assertEqual(self.remote_ref(), head)
        self.assertEqual({p: hashlib.sha256((self.root / p).read_bytes()).hexdigest() for p in before}, before)
        self.assertEqual(sync.jj("--ignore-working-copy", "log", "--no-graph", "-r", "@", "-T", "commit_id").stdout, at)
        # A fresh client reads the intended code at the remote develop, and none of the uncommitted work.
        clone = Path(self.tmp.name) / "clone"
        subprocess.run(["git", "clone", "-q", "--branch", "develop", str(self.remote), str(clone)], check=True)
        self.assertEqual(((clone / "lib/a.txt").read_text(), (clone / "lib/c.txt").read_text()), ("one\n", "three\n"))
        self.assertFalse((clone / "foreign.txt").exists())
        receipt = json.loads(checkpoint.receipt_path(sync, head).read_text())
        self.assertEqual((receipt["after"], receipt["bookmark"], receipt["scan"]["commits"]), (head, "develop", 2))
        self.assertEqual(receipt["evidence"]["trace_logs"], {"public": 0, "pending": 1, "withdrawn": 0,
                                                             "pending_ids": [f"{SESSION}/{LOG[:12]}"]})
        self.assertIn("1 pending", out)
        self.assertIn("no test", receipt["tests"])
        # What is on develop is published: jj no longer lets a later commit rewrite it.
        self.assertEqual(sync.jj("--ignore-working-copy", "log", "--no-graph", "-r", f"mutable() & ::{head}", "-T", '"x"').stdout, "")
        self.assertIn("nothing to push", self.run_checkpoint("--rev", "@-")[1])

    @cost("tool")
    def test_a_credential_in_a_parent_commit_is_refused_though_the_tip_deleted_it(self):
        develop = self.bootstrapped()
        self.commit("Add a fixture", {"lib/fixture.txt": f"token = {TOKEN}\n"})
        self.commit("Remove the fixture", delete=["lib/fixture.txt"])
        status, out, err = self.run_checkpoint("--rev", "@-")
        self.assertEqual((status, self.remote_ref()), (1, develop))
        self.assertIn("lib/fixture.txt: holds github-token ×1", out)
        self.assertNotIn(TOKEN, out + err)
        self.assertIn("nothing left this machine", err)

    @cost("tool")
    def test_an_unsafe_message_a_raw_payload_an_oversized_blob_and_a_bad_name_are_refused(self):
        develop = self.bootstrapped()
        self.commit(f"Use {TOKEN} in the deploy step", {"lib/b.txt": "two\n"})
        self.assertIn("its message holds github-token", self.run_checkpoint("--rev", "@-")[1])
        self.jj("abandon", "@-")
        self.commit("A run record", {"llm-dlc/loop-summaries/run/first.md": "private\n", ".env": "A=b\n", ".env.example": "A=\n"})
        out = self.run_checkpoint("--rev", "@-")[1]
        self.assertIn("llm-dlc/loop-summaries/run/first.md: is a loop's private run record", out)
        self.assertIn(".env: is an environment file", out)
        self.assertNotIn(".env.example", out)
        self.jj("abandon", "@-")
        self.commit("A big file and an odd name", {"lib/big.bin": b"x" * 5000, "lib/trailing. ": "x\n"})
        with mock.patch.object(checkpoint, "MAX_BLOB", 4096):
            out = self.run_checkpoint("--rev", "@-")[1]
        self.assertIn("lib/big.bin: is 5,000 bytes, over the 4,096", out)
        self.assertIn("lib/trailing. : has a component ending in a space or a dot", out)
        self.assertEqual(self.remote_ref(), develop)

    @cost("tool")
    def test_what_the_redactor_would_change_is_refused_in_a_trace_file_and_not_in_code(self):
        self.bootstrapped()
        context = "DB_PASS" + "WORD=" + "hunter2hunter2"   # the redactor's env-secret: KEY=value, shaped by its context
        self.commit("A test fixture", {"lib/fixture.properties": context + "\n"})
        self.assertEqual(self.run_checkpoint("--rev", "@-")[0], 0)
        self.commit("A summary", {f"llm-dlc/traces/{SESSION}/summary.md": "# Summary\n" + context + "\n"})
        status, out, _ = self.run_checkpoint("--rev", "@-")
        self.assertEqual(status, 1)
        self.assertIn(f"llm-dlc/traces/{SESSION}/summary.md: holds env-secret", out)

    @cost("tool")
    def test_a_conflict_in_an_outgoing_commit_is_refused(self):
        self.bootstrapped()
        base = self.jj("log", "--no-graph", "-r", "@-", "-T", "change_id").strip()
        self.commit("one side", {"lib/a.txt": "left\n"})
        left = self.jj("log", "--no-graph", "-r", "@-", "-T", "change_id").strip()
        self.jj("rebase", "-r", "@", "-d", base)
        (self.root / "lib/a.txt").write_text("right\n")
        self.jj("describe", "-m", "other side")
        right = self.jj("log", "--no-graph", "-r", "@", "-T", "change_id").strip()
        self.jj("rebase", "-s", left, "-d", right)
        status, out, _ = self.run_checkpoint("--rev", left)
        self.assertEqual(status, 1)
        self.assertIn("holds an unresolved conflict", out)

    @cost("tool")
    def test_only_one_committed_revision_forward_to_develop_and_nothing_else(self):
        develop = self.bootstrapped()
        self.commit("work", {"lib/b.txt": "two\n"})
        for args in (["--all"], ["--rev", "@-", "--bookmark", "main"], ["--rev", "@-", "--force"], ["--rev", "@-", "--remote", "elsewhere"],
                     ["--rev", "@-", "HEAD:refs/heads/main"], ["--rev", "glob:*"], ["--rev", "@-", "--allow-backwards"]):
            status, _, err = self.run_checkpoint(*args)
            self.assertEqual(status, 2, args)
            self.assertIn("is not for this command", err)
        self.assertIn("exactly one revision", self.run_checkpoint("--rev", "::@-")[2])
        self.assertIn("uncommitted work, which stays local", self.run_checkpoint("--rev", "@")[2])
        self.assertEqual(self.remote_ref(), develop)
        moved = self.elsewhere("develop")  # develop moved on the remote to a commit this line does not hold
        status, _, err = self.run_checkpoint("--rev", "@-")
        self.assertEqual((status, self.remote_ref()), (1, moved))
        self.assertIn("someone else pushed", err)
        self.jj("git", "fetch", "--remote", "origin")
        status, _, err = self.run_checkpoint("--rev", "@-")
        self.assertEqual((status, self.remote_ref()), (1, moved))
        self.assertIn("forward only", err)

    @cost("tool")
    def test_a_blob_is_scanned_once_and_a_lost_answer_is_one_push(self):
        self.bootstrapped()
        self.commit("first", {"lib/b.txt": "two\n", "lib/c.txt": "three\n"})
        status, out, _ = self.run_checkpoint("--rev", "@-", "--dry-run")
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(out[:out.rindex("}") + 1])["scan"]["scanned_blobs"], 2)
        head = self.commit("second", {"lib/d.txt": "four\n"})
        real = checkpoint.git

        def lossy(s, *args, **kwargs):
            r = real(s, *args, **kwargs)
            if args[0] == "push":  # the remote took it; the answer never came back
                return subprocess.CompletedProcess(r.args, 128, b"", b"fatal: the remote end hung up unexpectedly")
            return r
        with mock.patch.object(checkpoint, "git", lossy):
            status, out, err = self.run_checkpoint("--rev", "@-")
        self.assertEqual((status, self.remote_ref()), (0, head), err)
        receipt = json.loads(checkpoint.receipt_path(sync, head).read_text())
        self.assertEqual((receipt["scan"]["blobs"], receipt["scan"]["scanned_blobs"], receipt["scan"]["kept_verdicts"]), (3, 1, 2))
        self.assertIn("answer was lost", receipt["pushed"])
        self.assertIn("nothing to push", self.run_checkpoint("--rev", "@-")[1])

    @cost("tool")
    def test_a_decision_nobody_is_recorded_as_having_taken_is_refused(self):
        self.bootstrapped()
        entry = {"kind": "long-token", "status": "approved", "value": "made-up-value", "reason": "forged"}
        self.commit("A patched allow list", {"llm-dlc/allowlist.json": json.dumps({"schema": sync.ALLOWLIST_SCHEMA, "entries": {"abcd1234": entry}})})
        status, out, _ = self.run_checkpoint("--rev", "@-")
        self.assertEqual(status, 1)
        self.assertIn("no person is recorded as having", out)


class Names(unittest.TestCase):
    def test_unsafe_names(self):
        for path in ("a/../b", "a//b", ".git/config", "a/.GIT/x", "a\\b", "a\x07b", "a/b ", "x" * 300):
            self.assertIsNotNone(checkpoint.unsafe_name(path), path)
        for path in ("lib/src/main.rs", "examples/359-eclipse-boolean-list-insertion/README.md", ".gitignore", "a b/c.d"):
            self.assertIsNone(checkpoint.unsafe_name(path), path)

    def test_raw_payload_paths(self):
        for path in ("llm-dlc/traces/abc/logs/x.jsonl.gz", "verification/.state/runs/j/logs/1.log", "sub/.env.local",
                     "home/originals/spool/ordinary/ab/x.gz", "conf/r2-originals-writer", "x/.claude/projects/p/s.jsonl"):
            self.assertTrue(checkpoint.path_problems(path), path)
        for path in ("llm-dlc/traces/abc/manifest.json", "verification/results/j/logs/1.log", "docs/.env.example", "llm-dlc/tools/artifacts.py"):
            self.assertEqual(checkpoint.path_problems(path), [], path)


if __name__ == "__main__":
    unittest.main()
