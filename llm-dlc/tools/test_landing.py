#!/usr/bin/env python3
"""Tests for landing.py: a workspace's commits brought to the default line, an idle workspace moved onto the line,
and a merge tried without being made. Run: python3 llm-dlc/tools/test_landing.py
Everything is made up: a jj repository in a temporary directory with a workspace beside it, and a stand-in for
sync.py whose one generated file, llm-dlc/index.json, lists the session files as the trace files list sessions."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import landing
import run_common

TOOLS = Path(__file__).resolve().parent
sys.path.append(str(TOOLS.parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

# sync.py's stand-in: llm-dlc/index.json (one of the files it generates) lists the session files, as the trace files
# list sessions; `commit` commits.
FAKE_SYNC = textwrap.dedent('''\
    import os, subprocess, sys
    from pathlib import Path
    if sys.argv[1] == "adopt-logs":
        open(os.environ["STATUSES"] + "/adopted", "a").write(os.getcwd() + "\\n")
        sys.exit(0)
    if sys.argv[1] == "decisions":  # asked of a workspace's line before it is landed
        open(os.environ["STATUSES"] + "/decisions-asked", "a").write(" ".join(sys.argv[2:]) + "\\n")
        if os.environ.get("STANDIN_DECISIONS"):
            print(os.environ["STANDIN_DECISIONS"])
            sys.exit(1)
        sys.exit(0)
    Path("llm-dlc/index.json").write_text("".join(sorted(p.name + "\\n" for p in Path("sessions").glob("*"))))
    if os.environ.get("STANDIN_LATE") == "1":  # another session writes into the working copy meanwhile
        Path("verification").mkdir(exist_ok=True)
        Path("verification/late.txt").write_text("a result collected during the merge\\n")
    if sys.argv[1] == "commit":
        args = sys.argv[2:]
        paths = args[1:args.index("-m")] if args[0] == "--only" else []
        message = args[args.index("-m") + 1]
        sys.exit(subprocess.run(["jj", "commit", "-m", message, *paths]).returncode)
''')
MESSAGE = ("Merge the run made-up into the line", "Its agent worked in a workspace of its own while this line moved on.")


class Fixture(unittest.TestCase):
    """A made-up checkout: a jj repository with sync.py's stand-in, and the directory of a run named made-up."""
    FILES: dict[str, str] = {}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.root = base / "root"
        self.statuses = base / "statuses"
        self.statuses.mkdir()
        (base / "jj-config.toml").write_text("")
        env = {"JJ_USER": "Made Up", "JJ_EMAIL": "made-up@example.com", "JJ_CONFIG": str(base / "jj-config.toml"),
               "STATUSES": str(self.statuses), "XDG_STATE_HOME": str(base / "state")}
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()
        for key in ("STANDIN_DECISIONS", "STANDIN_LATE"):
            os.environ.pop(key, None)
        files = {".gitignore": "llm-dlc/loop-summaries/\n", "llm-dlc/tools/sync.py": FAKE_SYNC, "sessions/base": "",
                 "llm-dlc/index.json": "base\n", "lib.txt": "one\n", **self.FILES}
        for path, text in files.items():
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text(text)
        self.jj(self.root, "git", "init", "--colocate")
        self.jj(self.root, "commit", "-m", "base: a made-up checkout")
        self.run = run_common.Run(self.root, self.root / "llm-dlc" / "loop-summaries" / "single-made-up")
        self.run.name = "made-up"

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def jj(self, where: Path, *args: str) -> str:
        r = subprocess.run(["jj", *args], cwd=where, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def write(self, path: str, text: str, where: Path | None = None, message: str | None = None) -> None:
        where = where or self.root
        (where / path).parent.mkdir(parents=True, exist_ok=True)
        (where / path).write_text(text)
        if message:
            self.jj(where, "commit", "-m", message)

    def workspace(self, name: str = "ws") -> Path:
        folder = self.root.parent / f"root-{name}"
        self.jj(self.root, "workspace", "add", "--name", name, "-r", "@-", str(folder))
        return folder

    def work(self, name: str = "ws") -> Path:
        """A workspace with one commit of work in it, as a run's agent leaves one: a file of its own, its session's
        file, and the generated index that names the session."""
        folder = self.workspace(name)
        self.write("lib-work.txt", "shared\n", folder)
        self.write("sessions/work", "", folder)
        self.write("llm-dlc/index.json", "base\nwork\n", folder, "the run's work: a shared piece")
        return folder

    def head(self, template: str = "commit_id") -> str:
        return self.jj(self.root, "log", "--no-graph", "-r", "@-", "-T", template)


@cost("tool")
class Landing(Fixture):
    @cost("tool")
    def test_its_commits_move_the_line_forward_when_the_line_has_not_moved(self):
        folder = self.work()
        (self.root / "theirs.txt").write_text("another session's, uncommitted\n")
        out = landing.land(self.run, "ws", MESSAGE)
        self.assertIn("moved forward", out["landed"])
        self.assertIn("the run's work: a shared piece", out["commit"])
        self.assertEqual((self.root / "lib-work.txt").read_text(), "shared\n")
        self.assertIn("the run's work: a shared piece", self.head("description"))
        self.assertIn("theirs.txt", self.jj(self.root, "diff", "-r", "@", "--name-only"))  # still uncommitted, on top
        self.assertEqual((self.statuses / "adopted").read_text(), f"{self.root}\n")  # the line took the logs it now names
        self.assertIn("nothing to land", landing.land(self.run, "ws", MESSAGE)["landed"])
        self.assertTrue(landing.merged_in(self.root, "ws"))
        self.assertTrue(folder.is_dir())  # the workspace is left as it was

    @cost("tool")
    def test_a_line_that_moved_takes_them_by_a_merge_with_the_generated_files_regenerated(self):
        self.work()
        self.write("sessions/collector", "")
        self.write("llm-dlc/index.json", "base\ncollector\n", message="the line moves: a result is collected")
        out = landing.land(self.run, "ws", MESSAGE)
        self.assertIn("merged", out["landed"])
        self.assertEqual((self.root / "llm-dlc/index.json").read_text(), "base\ncollector\nwork\n")
        self.assertIn(MESSAGE[0], self.head("description"))
        self.assertEqual(self.jj(self.root, "diff", "-r", "@", "--name-only"), "")

    @cost("tool")
    def test_a_merge_made_without_words_of_its_own_names_the_workspace(self):
        self.work()
        self.write("lib.txt", "two\n", message="the line moves")
        self.assertIn("merged", landing.land(self.run, "ws")["landed"])
        self.assertIn("Merge the workspace ws into the line", self.head("description"))

    @cost("tool")
    def test_a_line_that_changes_what_only_a_person_decides_is_not_landed(self):
        self.work()
        with mock.patch.dict(os.environ, {"STANDIN_DECISIONS": "allowlist.json: abcd1234 (public-ip) is a decision in the file that no person took"}):
            with self.assertRaises(run_common.Problem) as refused:
                landing.land(self.run, "ws", MESSAGE)
        self.assertIn("is not landed: it changes what only a person decides", str(refused.exception))
        self.assertIn("abcd1234 (public-ip)", str(refused.exception))
        self.assertFalse((self.root / "lib-work.txt").exists())  # the line is where it was
        asked = (self.statuses / "decisions-asked").read_text().split()
        self.assertEqual((asked[0], asked[1]), ("--at", "ws@-"))  # the workspace's last commit, before any merge
        landing.land(self.run, "ws", MESSAGE)  # settled by a person: it lands
        self.assertTrue((self.root / "lib-work.txt").exists())

    @cost("tool")
    def test_what_another_session_wrote_during_the_merge_stays_uncommitted(self):
        self.work()
        self.write("lib.txt", "two\n", message="the line moves")
        with mock.patch.dict(os.environ, {"STANDIN_LATE": "1"}):
            out = landing.land(self.run, "ws", MESSAGE)
        self.assertEqual(out["leftUncommitted"], ["verification/late.txt"])
        self.assertNotIn("verification/late.txt", self.jj(self.root, "diff", "-r", "@-", "--name-only"))
        self.assertEqual(self.jj(self.root, "diff", "-r", "@", "--name-only").split(), ["verification/late.txt"])
        self.assertTrue((self.root / "verification/late.txt").exists())

    @cost("tool")
    def test_a_merge_that_conflicts_in_real_work_is_taken_back(self):
        self.work()
        self.write("lib-work.txt", "the line's own\n", message="the line adds the same file")
        before = self.head()
        with self.assertRaises(run_common.Problem) as refused:
            landing.land(self.run, "ws", MESSAGE)
        self.assertIn("conflicts in lib-work.txt: taken back", str(refused.exception))
        self.assertEqual(self.head(), before)
        self.assertEqual((self.root / "lib-work.txt").read_text(), "the line's own\n")
        self.assertEqual(self.jj(self.root, "log", "--no-graph", "-r", "heads(all()) & conflicts()", "-T", "commit_id"), "")

    @cost("tool")
    def test_a_merge_waits_for_another_sessions_uncommitted_files_and_for_the_workspaces_own(self):
        folder = self.work()
        self.write("lib.txt", "two\n", message="the line moves")
        (self.root / "theirs.txt").write_text("uncommitted\n")
        with self.assertRaises(run_common.Problem) as refused:
            landing.land(self.run, "ws", MESSAGE)
        self.assertIn("uncommitted changes (theirs.txt)", str(refused.exception))
        (self.root / "theirs.txt").unlink()
        self.write("unfinished.txt", "the agent's, not committed\n", folder)
        self.jj(folder, "status")  # jj has seen it
        with self.assertRaises(run_common.Problem) as refused:
            landing.land(self.run, "ws", MESSAGE)
        self.assertIn("the workspace ws has uncommitted changes (unfinished.txt)", str(refused.exception))
        self.assertIn("merged", landing.land(self.run, "ws", MESSAGE, at_work=True)["landed"])  # its session is still at work
        self.assertEqual((folder / "unfinished.txt").read_text(), "the agent's, not committed\n")

    @cost("tool")
    def test_trace_output_left_uncommitted_neither_holds_a_merge_back_nor_comes_along(self):
        self.work()
        self.write("lib.txt", "two\n", message="the line moves")
        self.write("llm-dlc/index.json", "stale\n")  # what a sync.py run left here, nobody's work
        self.write("llm-dlc/traces/sessions/made-up/summary.md", "a summary\n")
        self.jj(self.root, "describe", "-m", "Record session traces")
        out = landing.land(self.run, "ws", MESSAGE)
        self.assertIn("merged", out["landed"])
        self.assertEqual(sorted(out["dropped"]), ["llm-dlc/index.json", "llm-dlc/traces/sessions/made-up/summary.md"])
        self.assertEqual((self.root / "llm-dlc/index.json").read_text(), "base\nwork\n")  # written again
        self.assertEqual(self.jj(self.root, "diff", "-r", "@", "--name-only"), "")
        self.assertEqual(self.jj(self.root, "log", "--no-graph", "-r", 'heads(all()) & description("Record session traces")',
                                 "-T", "change_id"), "")  # the working copy it emptied is not left behind

    @cost("tool")
    def test_a_move_forward_drops_trace_output_and_is_taken_back_when_anothers_files_conflict(self):
        self.work()
        before = self.head()
        self.write("llm-dlc/traces/loops.md", "stale\n")
        self.write("lib-work.txt", "another session's, uncommitted\n")  # the run added it too
        with self.assertRaises(run_common.Problem) as refused:
            landing.land(self.run, "ws", MESSAGE)
        self.assertIn("conflict with ws's line in lib-work.txt: the line is left where it was", str(refused.exception))
        self.assertEqual(self.head(), before)
        self.assertEqual((self.root / "lib-work.txt").read_text(), "another session's, uncommitted\n")
        (self.root / "lib-work.txt").unlink()
        out = landing.land(self.run, "ws", MESSAGE)
        self.assertIn("moved forward", out["landed"])
        self.assertNotIn("dropped", out)  # dropped the first time
        self.assertFalse((self.root / "llm-dlc/traces/loops.md").exists())
        self.assertEqual((self.root / "lib-work.txt").read_text(), "shared\n")

    @cost("tool")
    def test_of_llm_dlc_readme_only_a_change_to_its_session_table_is_trace_output(self):
        table = f"# Changes\n\n{landing.INDEX_BEGIN}\n| a session |\n{landing.INDEX_END}\n\nWritten by people.\n"
        self.write("llm-dlc/README.md", table, message="the page with its table")
        self.write("llm-dlc/README.md", table.replace("| a session |", "| a session |\n| another |"))
        self.assertTrue(landing.regenerable(self.root, "llm-dlc/README.md"))
        self.write("llm-dlc/README.md", table.replace("Written by people.", "Edited by a session."))
        self.assertFalse(landing.regenerable(self.root, "llm-dlc/README.md"))
        self.assertTrue(landing.regenerable(self.root, "llm-dlc/decisions/made-up.md"))
        self.assertFalse(landing.regenerable(self.root, "llm-dlc/decisions/made-up.jsonl"))
        self.assertFalse(landing.regenerable(self.root, "llm-dlc/loops/made-up.md"))


@cost("tool")
class OntoTheLine(Fixture):
    @cost("tool")
    def test_an_idle_workspace_is_moved_to_the_lines_last_commit(self):
        self.assertEqual(landing.onto_line(self.root, "later"), "made by the run's start")  # no such workspace yet
        folder = self.workspace()
        self.assertEqual(landing.onto_line(self.root, "ws"), "on the line already")
        self.write("lib.txt", "two\n", message="the line moves")
        self.write("llm-dlc/index.json", "stale\n", folder)  # trace output a sync.py run left in the workspace
        self.jj(folder, "status")
        self.assertTrue(landing.onto_line(self.root, "ws").startswith("moved onto "))
        self.assertEqual((folder / "lib.txt").read_text(), "two\n")
        self.assertEqual((folder / "llm-dlc/index.json").read_text(), "base\n")

    @cost("tool")
    def test_a_workspace_with_work_the_line_lacks_or_uncommitted_files_is_not_moved(self):
        folder = self.work()
        self.write("lib.txt", "two\n", message="the line moves")
        with self.assertRaises(run_common.Problem) as refused:
            landing.onto_line(self.root, "ws")
        self.assertIn("has commits the line lacks: land its run first", str(refused.exception))
        landing.land(self.run, "ws", MESSAGE)
        self.write("unfinished.txt", "not committed\n", folder)
        self.jj(folder, "status")
        with self.assertRaises(run_common.Problem) as refused:
            landing.onto_line(self.root, "ws")
        self.assertIn("has uncommitted files (unfinished.txt)", str(refused.exception))


@cost("tool")
class ATrialMerge(Fixture):
    @cost("tool")
    def test_it_names_the_files_two_lines_meet_in_and_changes_nothing(self):
        a, b = self.workspace("a"), self.workspace("b")
        self.write("llm-dlc/index.json", "base\na\n", a)
        self.write("lib.txt", "a's\n", a, "a: the shared file")
        self.write("llm-dlc/index.json", "base\nb\n", b)
        self.write("lib.txt", "b's\n", b, "b: the shared file")
        self.write("left.txt", "not committed\n", b)
        self.write("other.txt", "the line's own\n", message="the line moves, elsewhere")
        every = lambda: self.jj(self.root, "log", "--no-graph", "-r", "all()", "-T", 'commit_id ++ "\\n"')
        before = every()
        self.assertEqual(sorted(landing.trial_merge(self.root, "a@-", "b@-")), ["lib.txt", "llm-dlc/index.json"])
        self.assertEqual(landing.trial_merge(self.root, "@-", "a@-"), [])  # lines that do not meet
        self.assertEqual(every(), before)
        self.assertEqual((b / "left.txt").read_text(), "not committed\n")
        self.assertTrue(landing.generated("llm-dlc/index.json") and not landing.generated("lib.txt"))


class TheSyncLock(unittest.TestCase):
    def test_it_is_the_lock_sync_py_takes_on_the_repository(self):
        sys.path.insert(0, str(TOOLS))
        import sync
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(sync.STATE.parent)}):
            self.assertEqual(landing.sync_lock_path(sync.REPO), sync.Operation("check").lock_path)


if __name__ == "__main__":
    unittest.main()
