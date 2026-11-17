#!/usr/bin/env python3
"""Tests for brief_run.py, the watcher's tools for a brief's run, and for what run-streams.sh does for it: the
streams a brief names, the question it asks about a loop that ended blocked, and a run with no fork.
Run: python3 llm-dlc/tools/test_brief_run.py
Everything is made up: a real jj repository in a temporary directory with copies of the scripts, a stand-in
`claude` on PATH, a stand-in feature-loop.sh that sets a brief's status and commits, and a stand-in sync.py. No
model is called."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import brief_run
import conductor
import decisions
import doctor
import watch

TOOLS = Path(__file__).resolve().parent
sys.path.append(str(TOOLS.parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

COPIED = ("run-streams.sh", "loop-common.sh", "streams_status.py", "run_records.py", "conductor.py", "decisions.py",
          "mode.py")

# sync.py's stand-in: generated.txt lists the session files, as the trace files list sessions; `commit` commits.
FAKE_SYNC = textwrap.dedent('''\
    import subprocess, sys
    from pathlib import Path
    Path("generated.txt").write_text("".join(sorted(p.name + "\\n" for p in Path("sessions").glob("*"))))
    if sys.argv[1] == "commit":
        sys.exit(subprocess.run(["jj", "commit", "-m", sys.argv[3]]).returncode)
''')

# feature-loop.sh's stand-in: each run of a brief takes the next status of the list in STATUSES/BRIEF-NAME (the
# last one again when the list is used up), writes it into the brief and commits, and notes that it ran.
FAKE_LOOP = textwrap.dedent('''\
    #!/usr/bin/env bash
    cd "$(dirname "$0")/../.." || exit 1
    name=$(basename "$1" .md)
    echo "$name $PWD" >>"$STATUSES/runs"
    n=$(grep -c "^$name " "$STATUSES/runs")
    status=$(sed -n "${n}p" "$STATUSES/$name"); [[ -n "$status" ]] || status=$(tail -n 1 "$STATUSES/$name")
    sed -i "s/^- Status: .*/- Status: $status/" "$1"
    echo "cycle 1"
    jj commit -m "$name: $status" >/dev/null 2>&1
''')

CLAUDE = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, subprocess, sys
    with open(os.environ["STANDIN_LOG"], "a") as f:
        f.write(json.dumps({"args": sys.argv[1:], "cwd": os.getcwd()}) + "\\n")
    if os.environ.get("STANDIN_COMMITS") == "1":
        open("lib-foundation.txt", "w").write("shared\\n")
        open("sessions/foundation", "w").write("")
        open("generated.txt", "w").write("base\\nfoundation\\n")
        subprocess.run(["jj", "commit", "-m", "the foundation: a shared piece"], check=True, capture_output=True)
    print(json.dumps({"type": "result", "subtype": "success", "total_cost_usd": 1.5, "result": "Built the shared piece."}))
''')


def brief(streams: list[str] = (), workspace: str | None = None, status: str | None = "working", extra: list[str] = (),
          session: int | None = None) -> str:
    session = session if session is not None else sum(map(ord, workspace or "main"))
    return "\n".join(["# Brief: made up", "", "## Progress", "", "- made up: started.",
                      *([f"- Status: {status}"] if status else []), "", "## Loop settings", "",
                      *([f"- session: 00000000-0000-4000-8000-{session:012d}"] if session else []), "- verification: separate",
                      *([f"- streams: {', '.join(streams)}"] if streams else []),
                      *([f"- workspace: {workspace}"] if workspace else []), *extra, ""])


class Fixture(unittest.TestCase):
    STREAMS = ("a", "b")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "root"
        self.statuses = base / "statuses"
        self.statuses.mkdir()
        (base / "bin").mkdir()
        (base / "bin" / "claude").write_text(CLAUDE)
        (base / "bin" / "claude").chmod(0o755)
        (base / "jj-config.toml").write_text("")
        self.log = base / "claude.jsonl"
        env = {"JJ_USER": "Made Up", "JJ_EMAIL": "made-up@example.com", "JJ_CONFIG": str(base / "jj-config.toml"),
               "PATH": f"{base / 'bin'}:{os.environ['PATH']}", "STANDIN_LOG": str(self.log), "STATUSES": str(self.statuses),
               "CLAUDE_CONFIG_DIR": str(base / "claude")}
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()
        for key in ("TMUX", "TMUX_PANE"):
            os.environ.pop(key, None)
        files = {".gitignore": "llm-dlc/loop-summaries/\nverification/pipeline.local.toml\n", "llm-dlc/tools/sync.py": FAKE_SYNC, "sessions/base": "",
                 "generated.txt": "base\n", "lib.txt": "one\n",
                 "llm-dlc/loops/made-up.md": brief(self.STREAMS)}
        for s in self.STREAMS:
            files[f"llm-dlc/loops/made-up-{s}.md"] = brief(workspace=f"made-up-{s}")
        for path, text in files.items():
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text(text)
        for name in COPIED:
            shutil.copy(TOOLS / name, self.root / "llm-dlc" / "tools" / name)
        loop = self.root / "llm-dlc" / "tools" / "feature-loop.sh"
        loop.write_text(FAKE_LOOP)
        loop.chmod(0o755)
        self.jj(self.root, "git", "init", "--colocate")
        self.jj(self.root, "commit", "-m", "base: a made-up brief and its streams")
        self.dir = self.root / "llm-dlc" / "loop-summaries" / "run-streams-made-up"

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

    def run_tool(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = brief_run.main(list(args), root=self.root)
        return code, out.getvalue(), err.getvalue()

    def run_of(self) -> brief_run.Run:
        return brief_run.Run(self.root, "made-up")

    def plan(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([str(self.root / "llm-dlc/tools/run-streams.sh"), "--plan", *args], capture_output=True, text=True)

    def streams(self, *statuses_by_loop: tuple[str, list[str]], **env) -> subprocess.Popen:
        for name, statuses in statuses_by_loop:
            (self.statuses / name).write_text("".join(s + "\n" for s in statuses))
        return subprocess.Popen([str(self.root / "llm-dlc/tools/run-streams.sh"), "made-up"], cwd=self.root,
                                env={**os.environ, "RUN_STREAMS_POLL": "1", "RUN_STREAMS_STATUS_EVERY": "1", **env},
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def runs(self) -> list[str]:
        return [line.split()[0] for line in (self.statuses / "runs").read_text().splitlines()]


class TheStreamsABriefNames(Fixture):
    @cost("tool")
    def test_a_brief_names_its_streams_and_each_has_its_brief_beside_it(self):
        r = self.plan("made-up")
        self.assertEqual(r.stdout.splitlines(), ["name: made-up", "brief: llm-dlc/loops/made-up.md",
                                                 "stream: a llm-dlc/loops/made-up-a.md", "stream: b llm-dlc/loops/made-up-b.md"])
        self.assertEqual(self.plan("llm-dlc/loops/made-up.md").stdout, r.stdout)  # by file as by name

    @cost("tool")
    def test_a_brief_that_names_none_has_no_streams(self):
        self.write("llm-dlc/loops/alone.md", brief())
        self.assertEqual(self.plan("alone").stdout.splitlines(), ["name: alone", "brief: llm-dlc/loops/alone.md"])

    @cost("tool")
    def test_the_briefs_older_than_the_setting_keep_their_streams(self):
        self.write("llm-dlc/loops/engine-priorities.md", "# Brief: older\n")
        self.write("llm-dlc/loops/cleanup.md", "# Brief: older\n")
        self.assertIn("stream: jbmc llm-dlc/loops/engine-priorities-jbmc.md", self.plan("engines").stdout)
        self.assertEqual(self.plan("llm-dlc/loops/engine-priorities.md").stdout.splitlines()[0], "name: engines")
        self.assertEqual([line.split()[1] for line in self.plan("cleanup").stdout.splitlines()[2:]], ["native", "jbmc", "examples"])

    @cost("tool")
    def test_a_brief_that_is_not_there_and_a_stream_named_as_the_runs_own_parts_are_refused(self):
        self.assertEqual(self.plan("absent").returncode, 2)
        self.write("llm-dlc/loops/bad.md", brief(["a", "merge"]))
        r = self.plan("bad")
        self.assertEqual(r.returncode, 2)
        self.assertIn("'merge'", r.stderr)


class BeforeTheRun(Fixture):
    @cost("tool")
    def test_a_brief_ready_to_run_has_nothing_in_its_way_and_says_where_each_stream_will_work(self):
        code, out, _ = self.run_tool("preflight", "made-up")
        check = json.loads(out)
        self.assertEqual((code, check["blocking"]), (0, []))
        self.assertEqual([(s["label"], s["workspace"], s["exists"], s["status"]) for s in check["streams"]],
                         [("a", "made-up-a", False, "working"), ("b", "made-up-b", False, "working")])
        self.assertEqual(check["streams"][0]["folder"], str(self.root.parent / "root-made-up-a"))

    @cost("tool")
    def test_what_run_streams_would_stop_at_is_found_before_anything_starts(self):
        self.write("llm-dlc/loops/made-up-a.md", brief(workspace="made-up-b"))  # the other stream's workspace
        (self.root / "llm-dlc/loops/made-up-b.md").write_text(brief(workspace="made-up-b", status=None))
        code, out, _ = self.run_tool("preflight", "made-up")
        blocking = " | ".join(json.loads(out)["blocking"])
        self.assertEqual(code, 1)
        self.assertIn("made-up-b.md names workspace made-up-b, which a has", blocking)
        self.write("llm-dlc/loops/made-up-a.md", brief(workspace="made-up-a"))
        (self.root.parent / "root-made-up-a").mkdir()  # a forgotten workspace's folder
        blocking = " | ".join(json.loads(self.run_tool("preflight", "made-up")[1])["blocking"])
        self.assertIn("root-made-up-a already exists, but no jj workspace is at it", blocking)
        self.assertIn("made-up-b.md has no `- Status:` line", blocking)

    @cost("tool")
    def test_each_loop_needs_a_session_of_its_own(self):
        self.write("llm-dlc/loops/made-up-a.md", brief(workspace="made-up-a", session=0))
        self.write("llm-dlc/loops/made-up-b.md", brief(workspace="made-up-b", session=sum(map(ord, "main"))))
        blocking = " | ".join(json.loads(self.run_tool("preflight", "made-up")[1])["blocking"])
        self.assertIn("made-up-a.md has no `- session: UUID`", blocking)
        self.assertIn("made-up-b.md names the session of llm-dlc/loops/made-up.md", blocking)

    @cost("tool")
    def test_a_loop_at_work_in_the_default_workspace_blocks_and_one_elsewhere_does_not(self):
        copy = Path(self.tmp.name) / "feature-loop.AbC123"  # as feature-loop.sh runs: from a private copy of itself
        copy.write_text("#!/usr/bin/env bash\nsleep 30\n")
        copy.chmod(0o755)
        for cwd, blocks in ((self.root, True), (Path(self.tmp.name), False)):
            p = subprocess.Popen(["bash", str(copy), "prove-change"], cwd=cwd)
            try:
                time.sleep(0.3)
                blocking = " | ".join(json.loads(self.run_tool("preflight", "made-up")[1])["blocking"])
                self.assertEqual("a loop is at work in the default workspace" in blocking, blocks, blocking)
            finally:
                p.kill()
                p.wait()

    @cost("tool")
    def test_a_stream_without_its_brief_blocks(self):
        (self.root / "llm-dlc/loops/made-up-b.md").unlink()
        self.assertIn("the stream b has no brief", " ".join(json.loads(self.run_tool("preflight", "made-up")[1])["blocking"]))

    @cost("tool")
    def test_the_runner_is_left_what_the_loops_do_not_take(self):
        machine = {"memory": 105 * doctor.GIB, "cpus": 30}
        with mock.patch.object(doctor, "machine", lambda: machine):
            self.assertEqual({k: brief_run.runner_budget(4, True)[k] for k in ("memory", "cpus", "workers")},
                             {"memory": "38G", "cpus": 18, "workers": 9})  # verification/README.md's streams row
            self.assertEqual(brief_run.runner_budget(0, False)["memory"], "80G")  # a brief with no streams is one loop
            self.assertEqual(brief_run.runner_budget(2, False)["cpus"], 24)

    @cost("tool")
    def test_a_budget_over_what_is_left_is_lowered_for_the_run_and_put_back_after_it(self):
        local = self.root / brief_run.LOCAL
        local.parent.mkdir()
        local.write_text('# a comment\n[runner]\nmachine_name = "vm"\nworkers = 13\ncpus = 26  # of 30\nmemory = "80G"\n[other]\nmemory = "1G"\n')
        with mock.patch.object(doctor, "machine", lambda: {"memory": 105 * doctor.GIB, "cpus": 30}):
            self.assertIn("memory 80G > 68G", " ".join(json.loads(self.run_tool("preflight", "made-up")[1])["notes"]))
            self.run_tool("budget", "made-up", "--apply")
            self.assertEqual(local.read_text(), '# a comment\n[runner]\nmachine_name = "vm"\nworkers = 12\ncpus = 24  # of 30\n'
                                                'memory = "68G"\n[other]\nmemory = "1G"\n')
            self.assertEqual(json.loads(self.run_tool("preflight", "made-up")[1])["notes"], [])
            self.run_tool("budget", "made-up", "--apply")  # a second time keeps the values of before the run
            self.run_tool("budget", "made-up", "--restore")
        self.assertIn('workers = 13\ncpus = 26  # of 30\nmemory = "80G"\n[other]', local.read_text())


class TheFoundation(Fixture):
    def foundation(self, *args: str, commits: bool = True) -> tuple[int, dict]:
        with mock.patch.dict(os.environ, {"STANDIN_COMMITS": "1" if commits else "0"}):
            code, out, err = self.run_tool("foundation", "made-up", "--memory", "none", *args)
        self.assertTrue(out, err)
        return code, json.loads(out)

    @cost("tool")
    def test_it_is_one_fable_session_in_a_workspace_of_its_own_given_the_users_words(self):
        code, out = self.foundation()
        call = json.loads(self.log.read_text().splitlines()[0])
        folder = self.root.parent / "root-made-up-foundation"
        self.assertEqual((code, call["cwd"]), (0, str(folder)))
        args = call["args"]
        self.assertEqual((args[args.index("--model") + 1], args[args.index("--effort") + 1]), ("claude-fable-5-2", "high"))
        self.assertIn(brief_run.FOUNDATION_PROMPT, args[1])
        self.assertTrue(args[1].startswith("The brief is `llm-dlc/loops/made-up.md`, with its streams' briefs beside it "
                                           "(`llm-dlc/loops/made-up-a.md`, `llm-dlc/loops/made-up-b.md`)."))
        self.assertEqual(args[args.index("--session-id") + 1], out["session"])
        self.assertEqual((out["ok"], out["committed"], out["uncommitted"], out["cost"]), (True, True, [], 1.5))
        self.assertIn("the foundation: a shared piece", out["commit"])
        self.assertIn("brief_run.py land made-up", out["next"])
        self.assertFalse((self.root / "lib-foundation.txt").exists())  # nothing of it is in the default workspace yet

    @cost("tool")
    def test_a_session_that_committed_nothing_is_said_so_and_a_second_run_keeps_the_session(self):
        _, first = self.foundation(commits=False)
        self.assertEqual((first["committed"], first["attempt"]), (False, 1))
        self.assertIn("committed nothing", first["next"])
        _, second = self.foundation(commits=False)
        self.assertEqual((second["session"], second["attempt"]), (first["session"], 2))

    @cost("tool")
    def test_its_commits_move_the_line_forward_when_the_line_has_not_moved(self):
        self.foundation()
        (self.root / "theirs.txt").write_text("another session's, uncommitted\n")
        code, out, err = self.run_tool("land", "made-up")
        self.assertEqual(code, 0, err)
        self.assertIn("moved forward", json.loads(out)["landed"])
        self.assertEqual((self.root / "lib-foundation.txt").read_text(), "shared\n")
        self.assertIn("the foundation: a shared piece", self.jj(self.root, "log", "--no-graph", "-r", "@-", "-T", "description"))
        self.assertIn("theirs.txt", self.jj(self.root, "diff", "-r", "@", "--name-only"))  # still uncommitted, on top
        self.assertIn("nothing to land", json.loads(self.run_tool("land", "made-up")[1])["landed"])
        self.assertTrue(json.loads(self.run_tool("preflight", "made-up")[1])["foundation"]["landed"])

    @cost("tool")
    def test_a_line_that_moved_takes_them_by_a_merge_with_the_generated_files_regenerated(self):
        self.foundation()
        self.write("sessions/collector", "")
        self.write("generated.txt", "base\ncollector\n", message="the line moves: a result is collected")
        code, out, err = self.run_tool("land", "made-up")
        self.assertEqual(code, 0, err)
        self.assertIn("merged", json.loads(out)["landed"])
        self.assertEqual((self.root / "generated.txt").read_text(), "base\ncollector\nfoundation\n")
        self.assertIn("Merge the foundation of the made-up run", self.jj(self.root, "log", "--no-graph", "-r", "@-", "-T", "description"))
        self.assertEqual(self.jj(self.root, "diff", "-r", "@", "--name-only"), "")

    @cost("tool")
    def test_a_merge_that_conflicts_in_real_work_is_taken_back(self):
        self.foundation()
        self.write("lib-foundation.txt", "the line's own\n", message="the line adds the same file")
        before = self.jj(self.root, "log", "--no-graph", "-r", "@-", "-T", "commit_id")
        code, _, err = self.run_tool("land", "made-up")
        self.assertEqual(code, 1)
        self.assertIn("conflicts in lib-foundation.txt: taken back", err)
        self.assertEqual(self.jj(self.root, "log", "--no-graph", "-r", "@-", "-T", "commit_id"), before)
        self.assertEqual((self.root / "lib-foundation.txt").read_text(), "the line's own\n")
        self.assertEqual(self.jj(self.root, "log", "--no-graph", "-r", "heads(all()) & conflicts()", "-T", "commit_id"), "")

    @cost("tool")
    def test_a_merge_waits_for_another_sessions_uncommitted_files(self):
        self.foundation()
        self.write("lib.txt", "two\n", message="the line moves")
        (self.root / "theirs.txt").write_text("uncommitted\n")
        code, _, err = self.run_tool("land", "made-up")
        self.assertEqual(code, 1)
        self.assertIn("uncommitted changes (theirs.txt)", err)


class Watching(Fixture):
    def started(self, pid: int | None = None, ago: float = 0) -> brief_run.Run:
        run = self.run_of()
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - ago))
        run.update(run={"pid": pid or os.getpid(), "started": stamp})
        return run

    def wait(self, *args: str) -> tuple[int, str]:
        code, out, _ = self.run_tool("wait", "made-up", "--timeout", "0", *args)
        return code, out

    @cost("tool")
    def test_nothing_is_returned_before_there_is_a_run_and_while_it_is_quiet(self):
        self.assertEqual(self.wait()[0], 3)
        self.started()
        self.assertEqual(json.loads(self.wait()[1])["kind"], "nothing")

    @cost("tool")
    def test_a_loop_that_ended_blocked_is_a_question_with_how_to_answer_and_its_inbox(self):
        self.started()
        conductor.append_event(self.dir, type="blocked", needsVerdict=True, answers=["rerun", "leave"],
                               deadline=time.time() + 60, loop="a", brief="llm-dlc/loops/made-up-a.md", status="blocked: an answer")
        thing = json.loads(self.wait()[1])
        self.assertEqual((thing["kind"], thing["event"]["loop"]), ("question", "a"))
        self.assertIn("decide llm-dlc/loop-summaries/run-streams-made-up 1 rerun|leave", thing["answer"])
        self.assertIn("inbox.py list made-up-a --open", thing["inbox"])
        self.assertEqual(conductor.cmd_decide(self.dir, 1, "rerun", "its answer is in its inbox"), 0)
        recorded = decisions.fold(decisions.read("run-streams-made-up", self.root / "llm-dlc" / "decisions"))
        self.assertEqual([(d["decision"]["option"], d["decision"]["recovery"]["class"]) for d in recorded.values()], [("rerun", "cheap")])
        self.assertEqual(json.loads(self.wait()[1])["kind"], "nothing")

    @cost("tool")
    def test_a_summary_comes_at_the_interval_and_says_what_moved_since_the_last(self):
        self.started(ago=4000)
        (self.dir / "a.phase").write_text("running\n")
        (self.dir / "a.cycle").write_text("3\n")
        (self.dir / "a.cost").write_text("2.50\n")
        code, out = self.wait()
        self.assertEqual(code, 0)
        self.assertRegex(out.splitlines()[0], r"^### .* UTC · 1 h 0\d min into the run of llm-dlc/loops/made-up.md · \$2.50$")
        self.assertIn("- **a**: working; cycle 3, 0 commits, $2.50; at ", out)
        self.assertIn("- **merge**: working; cycle -, 0 commits, $0.00", out)
        self.assertEqual(json.loads(self.wait()[1])["kind"], "nothing")  # the next one is an interval away
        self.run_tool("interval", "made-up", "0")
        self.assertNotIn("; at ", self.wait()[1].split("**merge**")[0].split("**a**")[1])  # a's head has not moved

    @cost("tool")
    def test_an_integration_check_that_stopped_passing_and_an_open_decision_are_each_told_once(self):
        run = self.started()
        run.report.parent.mkdir(parents=True, exist_ok=True)
        run.report.write_text("# Integration check\n\n- Result: failed (the script)\n")
        thing = json.loads(self.wait()[1])
        self.assertEqual((thing["kind"], thing["read"]), ("attention", "llm-dlc/loop-summaries/made-up-integration.md"))
        self.assertEqual(json.loads(self.wait()[1])["kind"], "nothing")
        with mock.patch.object(brief_run, "open_decisions", lambda run: ["made-up-D001"]):
            self.assertIn("made-up-D001 is open", json.loads(self.wait()[1])["what"])
            self.assertEqual(json.loads(self.wait()[1])["kind"], "nothing")

    @cost("tool")
    def test_a_run_that_ended_is_told_once_with_where_every_loop_stands(self):
        p = subprocess.Popen(["true"])
        p.wait()
        self.started(pid=p.pid)
        thing = json.loads(self.wait()[1])
        self.assertEqual((thing["kind"], [r["loop"] for r in thing["state"]["loops"]]), ("ended", ["a", "b", "merge"]))
        self.assertEqual(json.loads(self.wait()[1])["kind"], "nothing")


class ARunOfStreams(Fixture):
    """run-streams.sh itself, over stand-in loops: the streams it reads from the brief, none of them forked."""

    @cost("tool")
    def test_a_blocked_stream_is_run_again_when_the_watcher_says_so_and_the_merge_follows(self):
        p = self.streams(("made-up-a", ["blocked: an answer from b", "done"]), ("made-up-b", ["done"]), ("made-up", ["done"]),
                         RUN_STREAMS_WATCHER=str(self.dir), RUN_STREAMS_BLOCKED_WAIT="60")
        until = time.time() + 60
        while (event := conductor.pending(self.dir)) is None and time.time() < until and p.poll() is None:
            time.sleep(0.2)
        self.assertIsNotNone(event, p.stdout.read() if p.poll() is not None else "no question was asked")
        self.assertEqual((event["type"], event["loop"], event["status"], event["brief"]),
                         ("blocked", "a", "blocked: an answer from b", "llm-dlc/loops/made-up-a.md"))
        self.assertNotIn("made-up", self.runs())  # the merge has not started while the question is open
        conductor.cmd_decide(self.dir, event["n"], "rerun", "b answered: the item is in a's inbox")
        out, _ = p.communicate(timeout=120)
        self.assertEqual(p.returncode, 0, out)
        self.assertEqual(sorted(self.runs()), ["made-up", "made-up-a", "made-up-a", "made-up-b"])
        self.assertEqual(self.runs()[-1], "made-up")
        self.assertIn("the streams fork no session", out)
        self.assertNotIn("compacting", out)

    @cost("tool")
    def test_without_an_answer_or_a_watcher_a_blocked_stream_is_left_for_the_merge(self):
        p = self.streams(("made-up-a", ["blocked: an answer"]), ("made-up-b", ["done"]), ("made-up", ["done"]),
                         RUN_STREAMS_WATCHER=str(self.dir), RUN_STREAMS_BLOCKED_WAIT="1")
        out, _ = p.communicate(timeout=120)
        self.assertEqual(p.returncode, 0, out)
        self.assertEqual(sorted(self.runs()), ["made-up", "made-up-a", "made-up-b"])
        (self.statuses / "runs").unlink()
        self.write("llm-dlc/loops/made-up.md", brief(self.STREAMS))  # the brief's own loop is to run again
        p = self.streams(("made-up", ["done"]))  # no watcher: nothing is asked, and finished streams are not run again
        out, _ = p.communicate(timeout=120)
        self.assertEqual((p.returncode, self.runs()), (0, ["made-up"]), out)
        self.assertNotIn("asking the watcher", out)

    @cost("tool")
    def test_a_brief_with_no_streams_is_run_as_its_own_loop(self):
        self.write("llm-dlc/loops/made-up.md", brief(), message="the brief names no streams")
        p = self.streams(("made-up", ["done"]))
        out, _ = p.communicate(timeout=120)
        self.assertEqual((p.returncode, self.runs()), (0, ["made-up"]), out)
        self.assertIn("the brief names no streams: its own loop is the run", out)

    @cost("tool")
    def test_the_watcher_starts_the_run_detached_and_is_told_when_it_ends(self):
        for name, statuses in (("made-up-a", ["done"]), ("made-up-b", ["done"]), ("made-up", ["done"])):
            (self.statuses / name).write_text("".join(s + "\n" for s in statuses))
        with mock.patch.dict(os.environ, {"RUN_STREAMS_POLL": "1", "RUN_STREAMS_STATUS_EVERY": "1"}):
            code, out, err = self.run_tool("start", "made-up")
        self.assertEqual(code, 0, err)
        run = self.run_of()
        pid = run.read()["run"]["pid"]
        self.assertIn("already under way", self.run_tool("start", "made-up")[1])
        until = time.time() + 120
        while watch.alive(pid) and time.time() < until:
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
            time.sleep(0.2)
        code, out, _ = self.run_tool("wait", "made-up", "--timeout", "0")
        thing = json.loads(out)
        self.assertEqual(thing["kind"], "ended", (self.dir / "streams.log").read_text())
        self.assertEqual({r["loop"]: r["status"] for r in thing["state"]["loops"]}, {"a": "done", "b": "done", "merge": "done"})
        self.assertEqual(sorted(self.runs()), ["made-up", "made-up-a", "made-up-b"])


if __name__ == "__main__":
    unittest.main()
