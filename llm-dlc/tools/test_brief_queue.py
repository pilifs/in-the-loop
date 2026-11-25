#!/usr/bin/env python3
"""Tests for the brief queue (brief_queue.py): its own rules in process, and two briefs taken through the whole
handover for real, setup phase included, in test_single_run.py's made-up jj repository with its stand-in `claude`.
Run: python3 llm-dlc/tools/test_brief_queue.py
No model is called and nothing touches this repository, ~/.claude or ~/.cache: the commits, the develop checkpoint
and the archive's custody states are stand-ins, and HOME points into the test's own folder."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import brief_queue
import test_single_run

sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

TOOLS = Path(__file__).resolve().parent
NOTES = "## Setup Agent Notes\n\n- Everything the brief names is cached under ~/.cache/in-the-loop/made-up.\n"


class TheQueuesRules(unittest.TestCase):
    def test_a_briefs_front_matter_and_settings_override_the_defaults_and_nothing_unknown_passes(self):
        text = "---\nqueue.setup: none\nqueue.session: new\ntitle: kept for the reader\n---\n# A brief\n"
        self.assertEqual(brief_queue.front_matter(text), {"setup": "none", "session": "new"})
        self.assertEqual(brief_queue.front_matter("# A brief\n---\nqueue.setup: none\n---\n"), {}, "only at the very top")
        self.assertEqual(brief_queue.settings(["cycles=3", "model = x"]), {"cycles": "3", "model": "x"})
        with self.assertRaisesRegex(brief_queue.Problem, "KEY=VALUE"):
            brief_queue.settings(["cycles"])
        with self.assertRaisesRegex(brief_queue.Problem, "unknown setting"):
            brief_queue.checked({"modle": "x"})
        with self.assertRaisesRegex(brief_queue.Problem, "a count"):
            brief_queue.checked({"cycles": "many"})
        self.assertEqual(brief_queue.checked({"run": "x"}, allow_run=True), {"run": "x"})
        data = {"defaults": {"effort": "high"}, "entries": []}
        s = brief_queue.effective(data, {"settings": {"setup": "none"}})
        self.assertEqual((s["setup"], s["effort"], s["client"]), ("none", "high", "codex"))
        self.assertEqual(brief_queue.steps_of(s), brief_queue.STEPS_DOMAIN)
        self.assertEqual(brief_queue.steps_of(brief_queue.DEFAULTS), brief_queue.STEPS_SETUP + brief_queue.STEPS_DOMAIN)

    def test_a_brief_is_named_for_its_file_and_placed_where_it_is_asked(self):
        self.assertEqual(brief_queue.name_for(Path("jbmc-Java-semantics-gap-brief.md"), set()), "jbmc-java-semantics-gap")
        self.assertEqual(brief_queue.name_for(Path("x-brief.md"), {"x"}), "x-2")
        entries = [{"name": "a", "state": "domain"}, {"name": "b", "state": "queued"}]
        brief_queue.placed(entries, {"name": "c", "state": "queued"}, "first", None)
        self.assertEqual([e["name"] for e in entries], ["a", "c", "b"], "first means before every brief still waiting")
        brief_queue.placed(entries, {"name": "d", "state": "queued"}, "after", "c")
        brief_queue.placed(entries, {"name": "e", "state": "queued"}, "before", "a")
        brief_queue.placed(entries, {"name": "f", "state": "queued"}, None, None)
        self.assertEqual([e["name"] for e in entries], ["e", "a", "c", "d", "b", "f"])
        with self.assertRaisesRegex(brief_queue.Problem, "no brief z"):
            brief_queue.placed(entries, {"name": "g"}, "after", "z")

    def test_the_inbox_is_taken_in_the_order_its_briefs_were_put_there_and_the_log_names_the_session(self):
        # 2026-11-24: by name alone, "beyond-…" added after "trusted-kernel-…" would have run before it
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "originals").mkdir()
            for i, name in enumerate(("trusted-kernel-brief.md", "beyond-jbmc-brief.md", "a-copy-brief.md")):
                original = folder / "originals" / name
                original.write_text(f"# {name}\n")
                path = folder / name
                if name.startswith("a-copy"):
                    shutil.copy(original, path)
                else:
                    path.symlink_to(original)  # a link's own time counts, not its target's
                os.utime(path, (1000 + i, 1000 + i), follow_symlinks=False)
            os.utime(folder / "originals" / "trusted-kernel-brief.md", (5000, 5000))  # an edit to the original
            self.assertEqual([p.name for p in brief_queue.inbox_briefs(folder)],
                             ["trusted-kernel-brief.md", "beyond-jbmc-brief.md", "a-copy-brief.md"])
        clean = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")}
        with mock.patch.object(brief_queue.single_run, "person_at_terminal", lambda: False):
            with mock.patch.dict(os.environ, {**clean, "CLAUDE_CODE_SESSION_ID": "6c5c7798-made-up"}, clear=True):
                self.assertEqual(brief_queue.who(), "Claude Code session 6c5c7798-made-up")
            with mock.patch.dict(os.environ, {**clean, "CODEX_THREAD_ID": "thread-made-up"}, clear=True):
                self.assertEqual(brief_queue.who(), "Codex thread thread-made-up")
            with mock.patch.dict(os.environ, clean, clear=True):
                self.assertEqual(brief_queue.who(), "a session")
        with mock.patch.object(brief_queue.single_run, "person_at_terminal", lambda: True):
            self.assertEqual(brief_queue.who(), "a person, at their terminal")

    def test_a_list_of_pull_requests_is_told_from_a_brief_and_becomes_a_generation_entry(self):
        listed = ("# Pull requests\n\n- [Merged PR #14732](https://github.com/apache/lucene/pull/14732)\n"
                  "2. <https://github.com/google/guava/pull/7784>\nhttps://github.com/Apache/Lucene/pull/14732/files\n")
        self.assertTrue(brief_queue.is_pull_request_list(listed))
        self.assertEqual(brief_queue.pull_requests(listed), ["apache/lucene#14732", "google/guava#7784"], "in order, each once")
        self.assertFalse(brief_queue.is_pull_request_list("# A brief\n\nIt fixes https://github.com/a/b/pull/1 and more.\n"),
                         "a brief that mentions a pull request in a sentence is a brief")
        self.assertFalse(brief_queue.is_pull_request_list("# Only a heading\n"))
        self.assertEqual(brief_queue.steps_of({**brief_queue.DEFAULTS, "generate": "gpt-6.2-astra"}),
                         brief_queue.STEPS_GENERATE + ("checkpoint",), "its brief is queued as an entry of its own")
        with tempfile.TemporaryDirectory() as tmp:
            root, analysis = Path(tmp) / "checkout", Path(tmp) / "analysis"
            analysis.mkdir()
            (analysis / "prs.md").write_text(listed)
            data = {"defaults": {}, "entries": []}
            entry = brief_queue.make_entry(root, data, analysis / "prs.md")
            self.assertEqual((entry["name"], entry["settings"]["generate"], entry["copy"], entry["brief"], entry["pullRequests"]),
                             ("prs", "gpt-6.2-astra", "llm-dlc/loops/prs.md", "llm-dlc/loops/prs-brief.md",
                              ["apache/lucene#14732", "google/guava#7784"]))
            self.assertEqual(Path(entry["beside"]).expanduser(), analysis / "prs-brief.md")
            self.assertEqual((root / "llm-dlc/loops/prs.md").read_text(), listed, "the list's copy, unchanged")
            (analysis / "brief.md").write_text("# A brief\n")
            with self.assertRaisesRegex(brief_queue.Problem, "names no GitHub pull request"):
                brief_queue.make_entry(root, data, analysis / "brief.md", over={"generate": "gpt-6.2-astra"})
            self.assertNotIn("brief", brief_queue.make_entry(root, data, analysis / "brief.md"), "a brief is a brief")
            (analysis / "more.md").write_text(listed)
            (analysis / "more-brief.md").write_text("# Someone's own brief\n")
            with self.assertRaisesRegex(brief_queue.Problem, "would overwrite it"):
                brief_queue.make_entry(root, data, analysis / "more.md")

    def test_cleanup_clears_a_failed_jobs_folder_only_once_its_originals_are_in_the_archive(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp}):
            root, home = Path(tmp) / "checkout", Path(tmp) / ".cache/in-the-loop"
            folders = {}
            for job, where in (("sealed", home / "work/sealed"), ("unsealed", home / "work/unsealed"),
                               ("elsewhere", Path(tmp) / "elsewhere"), ("passed", None)):
                result = root / "verification/results/2026/11/23" / job / "result.json"
                result.parent.mkdir(parents=True)
                if where:
                    (where / "build").mkdir(parents=True)
                    (where / "build/out.bin").write_bytes(b"x" * 4096)
                    folders[job] = where
                result.write_text(json.dumps({"status": "failed", **({"workdir": str(where)} if where else {})}))
            states = {"sealed": ["remote_verified", "remote_verified"], "unsealed": ["remote_verified", "locally_sealed"],
                      "elsewhere": ["remote_verified"]}
            with mock.patch.object(brief_queue, "artifact_states", lambda r, job: states.get(job, [])):
                out = brief_queue.cleanup(root)
            self.assertEqual((out["cleared"], out["keptNotYetSealed"]), (1, 2))
            self.assertFalse(folders["sealed"].exists())
            self.assertTrue(folders["unsealed"].exists() and folders["elsewhere"].exists())


class TheHandover(unittest.TestCase):
    """Two briefs, from the inbox and from `add`, run one after the other through `next`."""
    setUp_runs = test_single_run.SingleRunTest.setUp
    jj = test_single_run.SingleRunTest.jj
    end = test_single_run.SingleRunTest.end
    tool = test_single_run.SingleRunTest.tool
    wait = test_single_run.SingleRunTest.wait
    calls = test_single_run.SingleRunTest.calls
    prompts = test_single_run.SingleRunTest.prompts
    run_dir = test_single_run.SingleRunTest.run_dir

    def setUp(self):
        self.setUp_runs()
        loops = self.root / "llm-dlc/loops"
        loops.mkdir(parents=True)
        for name in ("setup-agent-template.md", "domain-prompt-aspirational.md"):
            shutil.copy(TOOLS.parent / "loops" / name, loops / name)
        # A stand-in sync.py for what a landing asks of it: a merge is committed with its message, and the rest
        # (the decisions check, regenerating trace files, adopting logs) has nothing to do here.
        (self.root / "llm-dlc/tools/sync.py").write_text(
            "import subprocess, sys\n"
            "args = sys.argv[1:]\n"
            "if args[:1] == ['commit']:\n"
            "    sys.exit(subprocess.run(['jj', '--quiet', 'commit', '-m', args[args.index('-m') + 1]]).returncode)\n")
        self.jj("describe", "-m", "The templates")
        self.jj("new")
        self.home, self.inbox = self.tmp / "home", self.tmp / "inbox"
        self.home.mkdir()
        self.inbox.mkdir()
        self.analysis = self.home / "code/scripts/analysis"
        self.analysis.mkdir(parents=True)
        self.checkpoints = []
        patches = [mock.patch.dict(os.environ, {"HOME": str(self.home), "BRIEF_QUEUE_INBOX": str(self.inbox),
                                                "STANDIN_MODES": "commit"}),
                   mock.patch.object(brief_queue, "commit", self.commit),
                   mock.patch.object(brief_queue, "checkpoint", lambda root: self.checkpoints.append(1) or {"checkpoint": "made up"}),
                   mock.patch.object(brief_queue, "artifact_states", lambda root, job: [])]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def commit(self, root, paths, title, body):
        paths = brief_queue.changed(root, paths)
        if paths:
            self.jj("commit", "-m", title, "--", *paths)

    def queue(self, *args, ok=True):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = brief_queue.main([str(a) for a in args], root=self.root)
        if ok:
            self.assertEqual(status, 0, err.getvalue() + out.getvalue())
        return status, out.getvalue(), err.getvalue()

    def data(self, *args):
        return json.loads(self.queue(*args)[1])

    def finish(self, run):
        """The run's cycle has ended: the watcher stops it, as at a run's end."""
        self.wait(run)
        self.tool("answer", run, "stop", "--reason", "Its outcome is reached.")
        self.wait(run, kind="ended")

    @cost("tool")
    def test_two_briefs_run_one_after_the_other_with_setup_notes_landing_and_a_checkpoint_between(self):
        (self.inbox / "made-up-thing-brief.md").write_text("# The made-up thing\n\nIt should work.\n")
        (self.analysis / "other.md").write_text("---\nqueue.setup: none\n---\n# The other thing\n")
        self.data("defaults", "client=claude", "model=claude-fable-5-2", "effort=high", "memory=none", "workspace=ws",
                  "session=new")
        self.assertEqual(self.data("inbox")["added"], ["made-up-thing"])
        self.assertEqual(self.data("inbox")["added"], [], "a brief comes in from the inbox once")
        added = self.data("add", self.analysis / "other.md", "cycles=2")
        self.assertEqual((added["name"], added["copy"], added["settings"]), ("other", "llm-dlc/loops/other.md",
                                                                             {"setup": "none", "cycles": "2"}))
        self.assertIn("is on the queue already", self.queue("add", self.analysis / "other.md", ok=False)[2])
        self.assertIn("unknown setting", self.queue("add", self.inbox / "made-up-thing-brief.md", "modle=x", ok=False)[2])
        self.data("move", "other", "--first")
        self.assertEqual([r["name"] for r in self.data("status", "--json")["queue"]], ["other", "made-up-thing"])
        self.assertTrue((self.root / "llm-dlc/loops/made-up-thing-brief.md").is_file())

        # 1. `other` has no setup phase: its domain run starts at once, with the template's texts.
        out = self.data("next")
        self.assertEqual((out["brief"], out["started"]), ("other", "other"))
        self.assertIn("started", self.queue("move", "other", "--after", "made-up-thing", ok=False)[2])
        self.assertEqual(self.data("next")["underWay"], "other", "while the run is under way, nothing is handed over")
        self.finish("other")
        stopped = self.data("next")
        self.assertEqual(stopped["stopped"], "other")
        self.assertIn("--finished", stopped["next"])
        first = [p for p in self.prompts() if p.startswith("Review")][0]
        self.assertTrue(first.startswith("Review and implement `~/code/scripts/analysis/other.md`."), first[:90])
        self.assertIn("The brief for this work is `llm-dlc/loops/other.md`.", first)

        # 2. Finished: landed, checkpointed, and the next brief's setup run started, in one call.
        out = self.data("next", "--finished")
        self.assertEqual(out.get("done"), ["other"], out)
        self.assertEqual(out["steps"], ["other: domain-land", "other: checkpoint", "other: cleanup"])
        self.assertEqual((out["brief"], out["started"]), ("made-up-thing", "made-up-thing-setup"))
        self.assertIn("yours to decide", out["forTheUser"][0])
        self.assertEqual(len(self.checkpoints), 1)
        landed = json.loads((self.run_dir("other") / "watch.json").read_text())["landed"].split()[0]
        self.assertTrue(self.jj("log", "-r", f"{landed} & ::ws@-", "--no-graph", "-T", "commit_id"),
                        "the setup run starts from the line with the landed brief")

        # 3. The setup agent writes its record in the workspace; `next --finished` lands it, puts the notes into both
        #    copies of the brief, and starts the domain run from the line that has them.
        self.finish("made-up-thing-setup")
        folder = test_single_run.single_run.brief_run.workspaces(self.root)["ws"]
        (folder / "llm-dlc/loops/made-up-thing-brief-setup.md").write_text("# Setup\n\nDetail.\n\n" + NOTES)
        subprocess.run(["jj", "--quiet", "commit", "-m", "The setup record"], cwd=folder, check=True, capture_output=True)
        out = self.data("next", "--finished")
        self.assertEqual(out["steps"], ["made-up-thing: setup-land", "made-up-thing: notes"])
        self.assertEqual(out["started"], "made-up-thing")
        for copy in (self.root / "llm-dlc/loops/made-up-thing-brief.md", self.inbox / "made-up-thing-brief.md"):
            self.assertTrue(copy.read_text().endswith(NOTES), copy)
        self.assertTrue((folder / "llm-dlc/loops/made-up-thing-brief.md").read_text().endswith(NOTES),
                        "the domain run starts from the line with the notes")
        self.assertEqual(json.loads((self.run_dir("made-up-thing") / "watch.json").read_text())["workspace"], "ws")

        # 4. The last brief ends: the queue is empty, and the report and the log say what happened.
        self.finish("made-up-thing")
        out = self.data("next", "--finished")
        self.assertEqual((out["done"], out["next"]), (["made-up-thing"], "the queue is empty: nothing to start"))
        self.assertEqual(len(self.checkpoints), 2)
        report = self.data("report", "--json")
        self.assertEqual([(r["name"], r["state"], [x["run"] for x in r["runs"]]) for r in report],
                         [("other", "done", ["other"]), ("made-up-thing", "done", ["made-up-thing-setup", "made-up-thing"])])
        actions = [json.loads(line)["action"] for line in (self.root / brief_queue.LOG).read_text().splitlines()]
        self.assertEqual(actions, ["defaults", "add", "add", "move", "start", "done", "start", "notes", "start", "done"])
        self.assertEqual(brief_queue.changed(self.root, [brief_queue.LOG]), [], "the log is committed with the queue's commits")

    @cost("tool")
    def test_a_list_of_pull_requests_is_written_into_a_brief_in_a_session_of_its_own_and_the_brief_queued_at_the_end(self):
        loops = self.root / "llm-dlc/loops"
        for name in ("brief-generation-template.md", "brief-generation-handoff.md"):
            shutil.copy(TOOLS.parent / "loops" / name, loops / name)
        self.jj("commit", "-m", "The generation templates")
        (self.analysis / "prs.md").write_text("- [PR](https://github.com/made/up/pull/1)\n- [PR](https://github.com/other/thing/pull/22)\n")
        (self.analysis / "waiting.md").write_text("---\nqueue.setup: none\n---\n# A brief already waiting\n")
        # Claude Code stands in for Codex here, at an effort it has: the run's settings are what is tested.
        self.data("defaults", "client=claude", "model=claude-fable-5-2", "effort=high", "memory=none", "workspace=ws",
                  "session=new", "generateClient=claude", "generateEffort=high")
        added = self.data("add", self.analysis / "prs.md", "generate=claude-fable-5-2")
        self.assertEqual((added["name"], added["copy"], added["brief"], added["pullRequests"]),
                         ("prs", "llm-dlc/loops/prs.md", "llm-dlc/loops/prs-brief.md", ["made/up#1", "other/thing#22"]))
        self.data("add", self.analysis / "waiting.md")
        self.assertIn("prs.md (2 pull requests) -> llm-dlc/loops/prs-brief.md", self.queue("list")[1])

        # 1. The brief author starts in a session of its own, compacting at 600k, with the template's texts.
        out = self.data("next")
        self.assertEqual((out["brief"], out["started"]), ("prs", "prs-generate"))
        run = json.loads((self.run_dir("prs-generate") / "watch.json").read_text())
        self.assertEqual((run["compactAt"], run["generate"]["output"]), ("600k", "llm-dlc/loops/prs-brief.md"))
        self.wait("prs-generate")
        self.assertTrue(self.prompts()[0].startswith("You are the BRIEF AUTHOR for the pull requests listed in `llm-dlc/loops/prs.md`."))
        args = self.calls()[0]["args"]
        self.assertEqual(args[args.index("--autocompact") + 1], "600k")
        queue = json.loads((self.root / brief_queue.QUEUE).read_text())
        self.assertEqual(queue["lastGenerateSession"], run["session"])
        self.assertIsNone(queue.get("lastSession"), "the domain runs' session is another")

        # 2. A brief that leaves out a pull request is refused, and its landing is undone in the queue's record.
        self.tool("answer", "prs-generate", "stop", "--reason", "It says the brief is complete.")
        self.wait("prs-generate", kind="ended")
        folder = test_single_run.single_run.brief_run.workspaces(self.root)["ws"]
        written = folder / "llm-dlc/loops/prs-brief.md"
        written.write_text("# Made-up behaviour\n\n## made/up#1\n\nhttps://github.com/made/up/pull/1\n")
        subprocess.run(["jj", "--quiet", "commit", "-m", "The brief, part of it"], cwd=folder, check=True, capture_output=True)
        out = self.data("next", "--finished")
        self.assertEqual(out["failedAt"], "brief")
        self.assertIn("does not name 1 of the list's pull requests by URL (other/thing#22)", out["problem"])
        self.assertIn("single_run.py generate prs-generate", out["problem"])
        self.assertFalse((self.analysis / "prs-brief.md").exists())

        # 3. Continued, it writes the rest; landed again and checked, the brief is queued at the end and runs as any.
        self.tool("generate", "prs-generate")
        self.finish("prs-generate")
        written.write_text(written.read_text() + "\n## other/thing#22\n\nhttps://github.com/other/thing/pull/22\n")
        subprocess.run(["jj", "--quiet", "commit", "-m", "The brief, whole"], cwd=folder, check=True, capture_output=True)
        out = self.data("next", "--finished")
        self.assertEqual(out["steps"], ["prs: generate-land", "prs: brief", "prs: checkpoint"], out)
        self.assertEqual((out["done"], out["queued"]), (["prs"], ["prs-brief"]))
        self.assertIn("queued at the end as prs-brief", out["forTheUser"][0])
        self.assertEqual((self.analysis / "prs-brief.md").read_text(), (self.root / "llm-dlc/loops/prs-brief.md").read_text())
        rows = self.data("status", "--json")["queue"]
        self.assertEqual([(r["name"], r["state"]) for r in rows], [("prs", "done"), ("waiting", "domain"), ("prs-brief", "queued")])
        self.assertEqual((rows[2]["source"], rows[2]["generatedBy"]), ("~/code/scripts/analysis/prs-brief.md", "prs"))
        self.assertEqual(out["started"], "waiting", "the brief already waiting goes first")
        self.finish("waiting")
        out = self.data("next", "--finished")
        self.assertEqual(out.get("started"), "prs-brief-setup", f"then the generated brief's setup phase, as for any brief: {out}")
        setup = json.loads((self.run_dir("prs-brief-setup") / "watch.json").read_text())
        self.assertEqual(setup["setup"]["brief"], "llm-dlc/loops/prs-brief.md")
        actions = [json.loads(line)["action"] for line in (self.root / brief_queue.LOG).read_text().splitlines()]
        self.assertEqual(actions[:4], ["defaults", "add", "add", "start"])
        self.assertIn("brief", actions)

    @cost("tool")
    def test_a_step_that_fails_is_named_and_the_next_call_carries_on_from_it(self):
        (self.analysis / "thing.md").write_text("# A thing\n")
        self.data("defaults", "client=claude", "model=claude-fable-5-2", "effort=high", "memory=none", "setup=none",
                  "prompt=missing")
        self.data("add", self.analysis / "thing.md")
        out = self.data("next")
        self.assertEqual((out["failedAt"], out["brief"]), ("domain-start", "thing"))
        self.assertIn("no prompt template llm-dlc/loops/domain-prompt-missing.md", out["problem"])
        self.assertIn("PROBLEM domain-start", self.queue("list")[1])
        self.data("set", "thing", "prompt=aspirational")
        out = self.data("next")
        self.assertEqual(out["started"], "thing")
        self.assertNotIn("PROBLEM", self.queue("list")[1])
        self.assertIn("under way", self.queue("remove", "thing", ok=False)[2])
        self.assertIn("not a session id", self.queue("defaults", "--last-session", "nope", ok=False)[2])
        self.assertEqual(self.data("defaults", "--last-session", test_single_run.PARENT)["lastSession"], test_single_run.PARENT)


if __name__ == "__main__":
    unittest.main()
