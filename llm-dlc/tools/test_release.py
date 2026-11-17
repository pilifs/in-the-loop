#!/usr/bin/env python3
"""Tests for a release and the bootstrap that installs one: the digest of a tree, the search for the commit a pin
names, and install, status and update of a runtime checkout, from a made-up repository in a temporary directory
(plugins/in-the-loop/skills/prove-java-change/bootstrap.py, llm-dlc/tools/release.py).
Run: python3 llm-dlc/tools/test_release.py
The tool-tier tests run git and jj; nothing reaches the network or this repository."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO / "lib/tools"))
from cost_tier import cost  # noqa: E402

import release  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

bootstrap = release.bootstrap()
ENV = {**os.environ, "GIT_AUTHOR_NAME": "Made Up", "GIT_AUTHOR_EMAIL": "made@up.invalid", "GIT_COMMITTER_NAME": "Made Up",
       "GIT_COMMITTER_EMAIL": "made@up.invalid", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
       "JJ_USER": "Made Up", "JJ_EMAIL": "made@up.invalid"}
for name in ("IN_THE_LOOP_HOME", "IN_THE_LOOP_REPOSITORY", "IN_THE_LOOP_REF", "IN_THE_LOOP_MODE"):
    ENV.pop(name, None)


class UnitTest(unittest.TestCase):
    def test_the_next_version_raises_the_patch_number(self):
        self.assertEqual(release.next_version("0.4.9"), "0.4.10")
        with self.assertRaises(SystemExit):
            release.next_version("0.4")

    def test_what_is_left_out_of_a_digest(self):
        left = lambda p: bootstrap.left_out(p, bootstrap.EXCLUDED)
        self.assertTrue(left("plugins/in-the-loop/skills/prove-java-change/release.json"))
        self.assertTrue(left("llm-dlc/traces/README.md") and left("llm-dlc/traces/a/b/manifest.json"))
        self.assertTrue(left("llm-dlc/index.json") and left("llm-dlc/README.md"))
        self.assertFalse(left("llm-dlc/runtime.md") or left("llm-dlc/traces-readme-template.md")
                         or left("plugins/in-the-loop/skills/prove-java-change/SKILL.md") or left("llm-dlc/tools/sync.py"))

    def test_a_pin_of_another_schema_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            pin = Path(tmp) / "release.json"
            pin.write_text(json.dumps({"schema": "something-else/v1", "version": "1.0.0", "digest": "00"}))
            with self.assertRaises(bootstrap.Problem):
                bootstrap.load_pin(pin)


@cost("tool")
class GateTest(unittest.TestCase):
    """A release needs a passed default test run for the commit it is cut on; the gate itself is stood in for."""

    def gate(self, code, skipped=None):
        import contextlib
        import io
        from unittest import mock
        answer = mock.Mock(returncode=code, stdout="the default run passed for @-: JOB at abc\n", stderr="no passed default run covers @-\n")
        with mock.patch.object(release.subprocess, "run", return_value=answer) as run, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            return release.tests_gate(skipped), run, err.getvalue()

    def test_a_release_is_refused_without_a_passed_default_run_and_cut_with_one(self):
        refusal, run, _ = self.gate(1)
        self.assertIn("no passed default run covers @-", refusal)
        self.assertIn("required before a release", refusal)
        self.assertEqual(run.call_args.args[0][-3:], ["gate", "--rev", "@-"], "the commit a release is cut on")
        self.assertIsNone(self.gate(0)[0])

    def test_only_a_stated_reason_skips_the_gate_and_it_is_said(self):
        refusal, run, err = self.gate(1, skipped="the user: a docs-only release")
        self.assertIsNone(refusal)
        run.assert_not_called()
        self.assertIn("without a passed default test run, as asked: the user: a docs-only release", err)

    def test_cut_stops_at_the_gate_before_it_writes_anything(self):
        from unittest import mock
        with mock.patch.object(release.mode, "mode", return_value="development"), \
                mock.patch.object(release, "uncommitted", return_value=[]), \
                mock.patch.object(release, "tests_gate", return_value="no release cut: made up"), \
                mock.patch.object(release, "write_json") as write:
            with self.assertRaises(SystemExit) as stopped:
                release.cut(None, None)
        self.assertEqual(str(stopped.exception), "no release cut: made up")
        write.assert_not_called()


class ReleaseTest(unittest.TestCase):
    """A made-up repository with the skill in it, released and installed."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.origin = self.tmp / "origin"
        self.skill = self.origin / bootstrap.SKILL_PATH
        self.skill.mkdir(parents=True)
        shutil.copy(REPO / bootstrap.SKILL_PATH / "bootstrap.py", self.skill / "bootstrap.py")
        (self.skill / "SKILL.md").write_text("the skill, made up\n")
        (self.origin / "llm-dlc/tools").mkdir(parents=True)
        (self.origin / "llm-dlc/tools/sync.py").write_text("# stands in for sync.py\n")
        (self.origin / "llm-dlc/traces").mkdir()
        (self.origin / "llm-dlc/traces/README.md").write_text("generated\n")
        (self.origin / ".gitignore").write_text(bootstrap.MARKER + "\n")
        (self.origin / "lib.txt").write_text("the library, version one\n")
        self.git("init", "-q", "-b", "main")
        self.release("1.0.0")
        self.home = self.tmp / "home"

    def git(self, *args, cwd=None):
        r = subprocess.run(["git", *args], cwd=cwd or self.origin, env=ENV, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def release(self, version, spoil=False):
        """Cut a release as release.py does: everything committed, then the pin from that tree, in a commit of its
        own content. `spoil` changes a file in the release commit after the digest was taken."""
        before = self.commit(f"work towards {version}")
        digest, files = bootstrap.tree_digest(self.origin, before)
        (self.skill / "release.json").write_text(json.dumps({
            "schema": bootstrap.PIN_SCHEMA, "version": version, "digest": digest, "files": files,
            "excluded": list(bootstrap.EXCLUDED), "repository": str(self.origin), "ref": "main"}))
        (self.origin / "llm-dlc/traces/README.md").write_text(f"generated again for {version}\n")  # as sync.py would
        if spoil:
            (self.origin / "lib.txt").write_text("changed after the digest was taken\n")
        return self.commit(f"Release {version}")

    def installed_skill(self):
        """The skill as a plugin installed outside any checkout: a copy of the repository's, at its current commit."""
        plugin = self.tmp / "plugin"
        if plugin.exists():
            shutil.rmtree(plugin)
        shutil.copytree(self.skill, plugin)
        return plugin

    def run_bootstrap(self, plugin, *args, **env):
        r = subprocess.run([sys.executable, str(plugin / "bootstrap.py"), *args], capture_output=True, text=True,
                           env={**ENV, "IN_THE_LOOP_HOME": str(self.home), **env})
        try:
            return r.returncode, json.loads(r.stdout)
        except ValueError:
            self.fail(f"bootstrap {args} printed no JSON: {r.stdout!r} {r.stderr!r}")

    @cost("tool")
    def test_a_digest_is_of_the_content_alone(self):
        head = self.git("rev-parse", "HEAD")
        digest, files = bootstrap.tree_digest(self.origin, head)
        self.git("commit", "-q", "--allow-empty", "-m", "another message, the same tree")
        self.assertEqual(bootstrap.tree_digest(self.origin, self.git("rev-parse", "HEAD")), (digest, files))
        (self.origin / "llm-dlc/traces/README.md").write_text("regenerated\n")
        (self.skill / "release.json").write_text("{}")
        self.assertEqual(bootstrap.tree_digest(self.origin, self.commit("only files left out"))[0], digest)
        (self.origin / "lib.txt").write_text("the library, version two\n")
        changed = bootstrap.tree_digest(self.origin, self.commit("a file changed"))[0]
        self.assertNotEqual(changed, digest)
        os.chmod(self.origin / "lib.txt", 0o755)
        self.assertNotEqual(bootstrap.tree_digest(self.origin, self.commit("a mode changed"))[0], changed)
        self.assertEqual(files, 5)  # .gitignore, lib.txt, sync.py, SKILL.md, bootstrap.py

    @cost("tool")
    def test_a_release_is_the_commit_that_carries_the_pin_and_hashes_to_it(self):
        released = self.git("rev-parse", "HEAD")
        (self.origin / "lib.txt").write_text("work after the release\n")
        tip = self.commit("later work")
        pin = bootstrap.load_pin(self.skill / "release.json")
        self.assertEqual(bootstrap.find_release(self.origin, pin, tip), (released, []))
        commit, seen = bootstrap.find_release(self.origin, {**pin, "version": "9.9.9"}, tip)
        self.assertIsNone(commit)
        self.assertIn("is release 1.0.0", seen[0])

    @cost("tool")
    def test_a_commit_changed_after_its_digest_was_taken_is_no_release(self):
        tip = self.release("1.0.1", spoil=True)
        pin = bootstrap.load_pin(self.skill / "release.json")
        commit, seen = bootstrap.find_release(self.origin, pin, tip)
        self.assertIsNone(commit)
        self.assertIn("something changed in the commit after the release was cut", seen[0])

    @cost("tool")
    def test_install_stands_on_the_pinned_release_and_marks_the_checkout(self):
        released = self.git("rev-parse", "HEAD")
        plugin = self.installed_skill()
        (self.origin / "lib.txt").write_text("work after the release, in no release\n")
        self.commit("later work")
        self.assertEqual(self.run_bootstrap(plugin, "status")[1]["state"], "absent")
        status, out = self.run_bootstrap(plugin, "install")
        self.assertEqual((status, out["state"], out["mode"], out["blockers"]), (0, "current", "runtime", []))
        self.assertEqual(out["installed"]["commit"], released)
        self.assertEqual((self.home / "lib.txt").read_text(), "the library, version one\n")  # the release, not the tip
        marker = json.loads((self.home / bootstrap.MARKER).read_text())
        self.assertEqual((marker["schema"], marker["version"]), (bootstrap.MARKER_SCHEMA, "1.0.0"))
        self.assertEqual(self.git("status", "--porcelain", cwd=self.home), "")  # the marker is ignored, never committed
        self.assertEqual(self.run_bootstrap(plugin, "install")[1]["state"], "failed")  # not over a checkout

    @cost("tool")
    def test_a_skill_that_is_not_the_release_s_blocks(self):
        plugin = self.installed_skill()
        self.run_bootstrap(plugin, "install")
        (plugin / "SKILL.md").write_text("edited after it was installed\n")
        out = self.run_bootstrap(plugin, "status")[1]
        self.assertEqual(out["state"], "broken")
        self.assertIn("SKILL.md: differs from the release's", out["blockers"][0])

    @cost("tool")
    def test_a_release_that_is_not_in_the_repository_installs_nothing(self):
        plugin = self.installed_skill()
        pin = json.loads((plugin / "release.json").read_text())
        (plugin / "release.json").write_text(json.dumps({**pin, "version": "2.0.0"}))
        status, out = self.run_bootstrap(plugin, "install")
        self.assertEqual((status, out["state"]), (1, "failed"))
        self.assertIn("release 2.0.0", out["problem"])
        self.assertFalse(self.home.exists())

    @cost("tool")
    def test_update_moves_the_local_work_onto_the_next_release(self):
        self.run_bootstrap(self.installed_skill(), "install")
        (self.home / "examples").mkdir()
        (self.home / "examples/901.txt").write_text("the user's example\n")
        jj = lambda *args: subprocess.run(["jj", "--quiet", "-R", str(self.home), *args], env=ENV, capture_output=True,
                                          text=True)
        self.assertEqual(jj("describe", "-m", "Example 901").returncode, 0)
        self.assertEqual(jj("new").returncode, 0)
        (self.origin / "lib.txt").write_text("the library, version two\n")
        released = self.release("1.1.0")
        plugin = self.installed_skill()
        before = self.run_bootstrap(plugin, "status")[1]
        self.assertEqual((before["state"], before["installed"]["version"]), ("outdated", "1.0.0"))
        status, out = self.run_bootstrap(plugin, "update")
        self.assertEqual((status, out["state"], out["installed"]["commit"]), (0, "current", released))
        self.assertEqual(out["updated"]["conflicts"], [])
        self.assertEqual((self.home / "lib.txt").read_text(), "the library, version two\n")
        self.assertEqual((self.home / "examples/901.txt").read_text(), "the user's example\n")
        self.assertEqual(len(out["localCommits"]), 1)
        self.assertIn("Example 901", out["localCommits"][0])

    @cost("tool")
    def test_inside_a_development_checkout_there_is_nothing_to_install(self):
        status, out = self.run_bootstrap(self.skill, "status")  # the skill run from the repository itself
        self.assertEqual((status, out["state"], out["home"]), (0, "development", str(self.origin)))
        self.assertEqual(self.run_bootstrap(self.skill, "install")[1]["state"], "failed")


if __name__ == "__main__":
    unittest.main()
