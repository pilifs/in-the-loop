#!/usr/bin/env python3
"""Tests for a single agent's run: single_run.py, the watcher's tools, and feature-loop.sh's `single-agent` loop,
run for real in a made-up jj repository with a stand-in `claude` on PATH that records how it was called and plays
a session: it commits, does nothing, forks, or waits to be told to go on.
Run: python3 llm-dlc/tools/test_single_run.py
No model is called and nothing touches this repository or ~/.claude: the loop's scripts are copied into a
temporary directory, and CLAUDE_CONFIG_DIR points beside it."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import conductor
import decisions
import loop_stats
import single_run

TOOLS = Path(__file__).resolve().parent
sys.path.append(str(TOOLS.parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

PARENT = "0f0f0f0f-1111-4222-8333-444455556666"
PROMPT = "Make the made-up thing work, and say when it does."
CONTINUE = "Go on with the made-up thing."

# The stand-in: one invocation is one turn. It appends its arguments to $STANDIN_LOG and prints stream-json.
STANDIN = r'''#!/usr/bin/env python3
import json, os, re, subprocess, sys, time
from pathlib import Path

args = sys.argv[1:]
value = lambda flag: args[args.index(flag) + 1] if flag in args else None
prompt = value("-p")
projects = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / re.sub(r"[^A-Za-z0-9]", "-", os.getcwd())
emit = lambda event: print(json.dumps(event), flush=True)
call = {"args": args, "cwd": os.getcwd()}
log = Path(os.environ["STANDIN_LOG"])
work = prompt != "/compact" and not prompt.startswith(("The feature loop is ending", "This conversation goes on"))
turns = sum(1 for line in log.read_text().splitlines() if json.loads(line).get("work")) if log.exists() else 0
modes = os.environ.get("STANDIN_MODES", "commit").split(",")
mode = modes[min(turns, len(modes) - 1)]
session = value("--session-id") or value("--resume")
if "--fork-session" in args:
    call["parentVisible"] = (projects / (value("--resume") + ".jsonl")).is_file()
if work:
    call["work"] = True
    if mode == "wait":
        until = time.time() + 30
        while time.time() < until and not Path(os.environ["STANDIN_GO"]).exists():
            time.sleep(0.1)
    if mode in ("commit", "wait", "stale"):
        Path("work.txt").write_text("turn %d at %s\n" % (turns + 1, time.time()))
        subprocess.run(["jj", "--quiet", "describe", "-m", "Made-up work, turn %d" % (turns + 1)], check=True)
        subprocess.run(["jj", "--quiet", "new"], check=True)
    if mode == "stale":
        # another session, in a workspace of its own, puts a commit under this turn's at the same moment: the
        # files this workspace should have change, and jj here refuses every command until it is brought up to date
        other = Path(os.environ["STANDIN_OTHER"])
        if not other.exists():
            subprocess.run(["jj", "--quiet", "workspace", "add", "--name", "other", "-r", "default@--", str(other)], check=True)
        (other / "other.txt").write_text("another session's file\n")
        subprocess.run(["jj", "--quiet", "describe", "-m", "Another session's commit"], cwd=other, check=True)
        subprocess.run(["jj", "--quiet", "rebase", "-s", "default@-", "-d", "other@"], cwd=other, check=True)
    elif mode == "leave":
        Path("left.txt").write_text("not committed\n")
projects.mkdir(parents=True, exist_ok=True)
with open(projects / (session + ".jsonl"), "a") as f:
    f.write("{}\n")
# what the session's shell sees of the run that started it
call["run"] = sorted(k for k in os.environ if k.startswith(("RUN_STREAMS_", "FEATURE_LOOP_", "LOOP_WATCH_", "PROVE_LOOP_"))
                     or k == "LOOP_CONDUCTOR")
with open(log, "a") as f:
    f.write(json.dumps(call) + "\n")
emit({"type": "result", "subtype": "success", "result": "the stand-in's report of turn %d (%s)" % (turns + 1, mode),
      "num_turns": 1, "duration_ms": 1, "total_cost_usd": 0.5 * (turns + 1), "session_id": session})
'''


@cost("tool")
class SingleRunTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.root = self.tmp / "checkout"
        tools = self.root / "llm-dlc/tools"
        tools.mkdir(parents=True)
        for name in ("feature-loop.sh", "loop-common.sh", "conductor.py", "agent_client.py", "unstale.py"):
            shutil.copy(TOOLS / name, tools / name)
        (self.root / ".gitignore").write_text("llm-dlc/loop-summaries/\n")
        # the checkout's instructions, which a Codex run is checked to be given whole before it starts
        (self.root / "CLAUDE.md").write_text("".join(f"- A made-up rule of this checkout, number {i}, long enough to be a marker.\n" for i in range(8)))
        (self.root / "notes").mkdir()
        (self.root / "notes/brief.md").write_text("# The made-up thing\n\nIt should work.\n")
        bin = self.tmp / "bin"
        bin.mkdir()
        (bin / "claude").write_text(STANDIN)
        (bin / "claude").chmod(0o755)
        self.config = self.tmp / "claude-config"
        (self.config / "projects/-somewhere-else").mkdir(parents=True)
        (self.config / "projects/-somewhere-else" / f"{PARENT}.jsonl").write_text("{}\n")
        self.log, self.go = self.tmp / "standin.jsonl", self.tmp / "go"
        env = {"PATH": f"{bin}:{os.environ['PATH']}", "CLAUDE_CONFIG_DIR": str(self.config), "STANDIN_LOG": str(self.log),
               "STANDIN_GO": str(self.go), "XDG_STATE_HOME": str(self.tmp / "state"), "XDG_CACHE_HOME": str(self.tmp / "cache"), "XDG_RUNTIME_DIR": str(self.tmp),
               "JJ_USER": "Made Up", "JJ_EMAIL": "made@up.invalid", "JJ_CONFIG": os.devnull}
        patched = mock.patch.dict(os.environ, env)
        patched.start()
        self.addCleanup(patched.stop)
        # Run inside a loop, the tests would otherwise inherit its run.
        for key in [k for k in os.environ if k.startswith(("RUN_STREAMS_", "FEATURE_LOOP_", "STANDIN_MODES"))] + ["LOOP_CONDUCTOR", "TMUX", "TMUX_PANE", "IN_THE_LOOP_MODE"]:
            os.environ.pop(key, None)
        self.jj("git", "init", str(self.root), cwd=self.tmp)
        self.jj("describe", "-m", "The made-up checkout")
        self.jj("new")
        self.addCleanup(self.end)

    def jj(self, *args, cwd=None):
        return subprocess.run(["jj", "--quiet", *args], cwd=cwd or self.root, check=True, capture_output=True, text=True).stdout

    def end(self):
        """No loop outlives its test."""
        for path in (self.root / "llm-dlc/loop-summaries").glob("single-*/watch.json"):
            pid = (json.loads(path.read_text()).get("loop") or {}).get("pid")
            if pid and single_run.watch.alive(pid):
                with contextlib.suppress(OSError):
                    os.killpg(int(pid), 9)

    def tool(self, *args, ok=True):
        """A command of single_run.py on the made-up checkout: (exit status, what it printed, what it said was wrong)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = single_run.main([str(a) for a in args], root=self.root)
        if ok:
            self.assertEqual(status, 0, err.getvalue() + out.getvalue())
        return status, out.getvalue(), err.getvalue()

    def start(self, *args, name="thing", modes="commit", wait=30, **env):
        with mock.patch.dict(os.environ, {"STANDIN_MODES": modes, **env}):
            return json.loads(self.tool("start", name, "--memory", "none", "--no-verification", "--verdict-wait", wait, *args)[1])

    def wait(self, name="thing", kind=None):
        """What `wait` gives next, as data. With `kind`, the next thing of that kind."""
        until = time.time() + 90
        while time.time() < until:
            thing = json.loads(self.tool("wait", name, "--timeout", 60, ok=False)[1])
            if kind is None or thing.get("kind") == kind:
                return thing
            self.assertNotIn(thing.get("kind"), ("ended", "not-running"), thing)
        self.fail(f"no {kind} came")

    def under_way(self, name="thing", cycle=1):
        """Wait until the loop has started this cycle: its turn is then the stand-in's, which may be waiting."""
        until = time.time() + 60
        while time.time() < until:
            if any(e.get("type") == "cycle-start" and e.get("cycle") == cycle for e in conductor.read_events(self.run_dir(name))):
                return
            time.sleep(0.1)
        self.fail(f"cycle {cycle} did not start")

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def prompts(self):
        return [c["args"][c["args"].index("-p") + 1] for c in self.calls()]

    def record(self, name="thing", folder=None):
        return sorted(((folder or self.root) / "llm-dlc/loop-summaries").glob(f"*-single-{name}.md"))[-1].read_text()

    def run_dir(self, name="thing"):
        return self.root / "llm-dlc/loop-summaries" / f"single-{name}"

    @cost("tool")
    def test_the_first_cycle_takes_the_prompt_every_later_one_the_continue_message_and_the_watcher_ends_the_run(self):
        started = self.start("--prompt", PROMPT, "--continue", CONTINUE)
        self.assertEqual((started["firstCycleTakes"], started["continueMessage"], started["newSession"]), ("the prompt", CONTINUE, True))
        first = self.wait()
        self.assertEqual((first["kind"], first["event"]["type"], first["cycle"]["cycle"]), ("question", "run", 1))
        self.assertIn("the stand-in's report of turn 1", first["cycle"]["report"])
        self.assertEqual(len(first["cycle"]["commits"]), 1)
        self.assertIn("Made-up work, turn 1", first["cycle"]["commits"][0])
        self.assertEqual((first["cycle"]["nextCycleTakes"], first["cycle"]["cost"]), (CONTINUE, 0.5))
        self.assertIn("single_run.py answer thing continue|stop", first["answer"])
        self.tool("answer", "thing", "continue", "--reason", "The thing does not work yet.")
        second = self.wait()
        self.assertEqual((second["event"]["type"], second["cycle"]["cycle"]), ("run", 2))
        self.assertEqual(second["cycle"]["cost"], 0.5, "the session's running total, less what it was at the question before")
        self.tool("answer", "thing", "stop", "--reason", "The thing works.")
        ended = self.wait(kind="ended")
        self.assertEqual((ended["event"]["status"], ended["state"]["running"]), (0, False))
        self.assertEqual(len(ended["state"]["commits"]), 2)
        self.assertEqual(self.prompts()[:4], [PROMPT, "/compact", CONTINUE, "/compact"])
        self.assertTrue(self.prompts()[4].startswith("The feature loop is ending after 2 cycle(s)"))
        session = started["session"]
        self.assertIn("--session-id", self.calls()[0]["args"])
        self.assertEqual([c["args"][c["args"].index("--resume") + 1] for c in self.calls()[1:]], [session] * 4)
        text = self.record()
        self.assertIn(f"> {PROMPT}", text)
        self.assertIn(f"> {CONTINUE}", text)
        self.assertIn("decided to continue: the watcher: The thing does not work yet.", text)
        self.assertRegex(text, r"Ended \S+ \S+ after 2 cycle\(s\): the run was ended there \(the watcher: The thing works\.\)")
        # each answer is a decision the user can review
        made = decisions.fold(decisions.read("single-thing", self.root / "llm-dlc/decisions")).values()
        self.assertEqual(sorted((d["decision"]["option"], d["decision"]["rationale"]) for d in made),
                         [("continue", "The thing does not work yet."), ("stop", "The thing works.")])
        self.assertTrue(all("single-agent run" in d["asked"]["question"] for d in made))
        self.assertEqual(json.loads(self.tool("wait", "thing", "--timeout", 1)[1])["kind"], "not-running")
        # the agent's shell holds nothing of the loop or the run: a test it ran of these scripts would ask the real watcher
        self.assertEqual([c["run"] for c in self.calls()], [[]] * len(self.calls()))

    @cost("tool")
    def test_a_message_a_person_sets_while_a_cycle_runs_is_what_the_next_cycle_takes_and_a_watcher_sets_none(self):
        self.start("--prompt", PROMPT, modes="wait,commit")
        self.assertEqual(json.loads(self.tool("message", "thing")[1])["continueMessage"], single_run.DEFAULT_CONTINUE)
        self.under_way()
        # from a session's shell, the watcher's included: refused, and the message stays as it is
        status, _, err = self.tool("message", "thing", "Do something else.", ok=False)
        self.assertEqual(status, 1)
        self.assertIn("a person's to change, from their own terminal", err)
        self.assertIn("end it", err)
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), mock.patch.object(sys.stdin, "isatty", lambda: True, create=True):
            self.assertFalse(single_run.person_at_terminal())
        with mock.patch.object(single_run, "person_at_terminal", lambda: True):
            said = self.tool("message", "thing", "Now the tests.")[1]
        self.assertIn("is not interrupted", said)
        self.go.write_text("go\n")
        first = self.wait()
        self.assertEqual(first["cycle"]["nextCycleTakes"], "Now the tests.")
        self.assertIn("never yours", first["cycle"]["hint"])
        self.assertNotIn("--message", first["answer"])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):  # an answer carries no message
            single_run.main(["answer", "thing", "continue", "--reason", "Half is left.", "--message", "Mine."], root=self.root)
        self.tool("answer", "thing", "continue", "--reason", "The tests are left.")
        self.wait()
        self.tool("answer", "thing", "stop", "--reason", "Done.")
        self.wait(kind="ended")
        work = [p for p in self.prompts() if p != "/compact" and not p.startswith("The feature loop is ending")]
        self.assertEqual(work, [PROMPT, "Now the tests."])
        self.assertIn("from cycle 2 the continue message is: Now the tests.", self.record())
        history = json.loads(self.tool("message", "thing")[1])["history"]
        self.assertEqual([(h["text"], h["set"]) for h in history],
                         [(single_run.DEFAULT_CONTINUE, "at the start"), ("Now the tests.", "by a person, from their terminal")])
        # nor does a restart change it: the run goes on with the message as it stands
        status, _, err = self.tool("start", "thing", "--continue", "Mine.", "--memory", "none", ok=False)
        self.assertEqual(status, 1)
        self.assertIn("a person changes from their own terminal", err)

    @cost("tool")
    def test_a_brief_is_named_after_the_text_of_every_cycle_and_nothing_else_is_added(self):
        self.jj("describe", "-m", "The brief")
        self.jj("new")
        started = self.start("--prompt", PROMPT, "--continue", CONTINUE, "--brief", self.root / "notes/brief.md", "--cycles", 2)
        self.assertEqual((started["brief"], started["cycles"]), ("notes/brief.md", 2))
        self.wait()
        self.tool("answer", "thing", "continue", "--reason", "More to do.")
        ended = self.wait(kind="ended")  # the second cycle is the count's last: nothing is asked after it
        self.assertEqual(ended["event"]["status"], 0)
        named = "\n\nThe brief for this work is `notes/brief.md`. Read it in full first, even if you have read it before: what you remember of it may be a summary."
        work = [p for p in self.prompts() if p != "/compact" and not p.startswith("The feature loop is ending")]
        self.assertEqual(work, [PROMPT + named, CONTINUE + named])
        self.assertRegex(self.record(), r"Ended \S+ \S+ after 2 cycle\(s\)\.")

    @cost("tool")
    def test_a_cycle_with_no_commit_is_the_watchers_to_judge_and_may_go_on(self):
        self.start("--prompt", PROMPT, "--continue", CONTINUE, modes="leave,commit")
        first = self.wait()
        self.assertEqual((first["cycle"]["commits"], first["cycle"]["uncommitted"]), ([], ["left.txt"]))
        self.assertIn("made no commit", first["cycle"]["hint"])
        self.assertIn("left files uncommitted", first["cycle"]["hint"])
        self.tool("answer", "thing", "continue", "--reason", "It says it will commit next.", "--confidence", "medium")
        second = self.wait()
        self.assertEqual((second["cycle"]["cycle"], len(second["cycle"]["commits"])), (2, 1))
        self.assertNotIn("made no commit", second["cycle"]["hint"])
        self.tool("answer", "thing", "stop", "--reason", "Committed.")
        self.assertEqual(self.wait(kind="ended")["event"]["status"], 0)
        text = self.record()
        self.assertRegex(text, r"- cycle 1, \S+ \S+: no commit\n  - decided to continue: the watcher: It says it will commit next\.")
        made = decisions.fold(decisions.read("single-thing", self.root / "llm-dlc/decisions")).values()
        self.assertEqual(sorted(d["decision"]["confidence"]["level"] for d in made), ["high", "medium"])

    @cost("tool")
    def test_a_cycle_with_no_commit_and_no_verdict_ends_the_run_before_its_compact(self):
        self.start("--prompt", PROMPT, "--continue", CONTINUE, modes="idle", wait=2)
        # nobody answers: the loop's wait runs out, and a cycle with no commit and no verdict is a session to look at
        until = time.time() + 60
        while time.time() < until and single_run.Run(self.root, "thing").running():
            time.sleep(0.2)
        ended = self.wait(kind="ended")
        self.assertEqual(ended["event"]["status"], 1)
        self.assertRegex(self.record(), r"Stopped \S+ \S+: cycle 1 made no commit, and no verdict came from the watcher")
        self.assertEqual(self.prompts(), [PROMPT], "stopped before the compact: the session keeps its context")
        status, _, err = self.tool("answer", "thing", "stop", "--reason", "Too late.", ok=False)
        self.assertEqual(status, 1)
        self.assertIn("no question", err)

    @cost("tool")
    def test_with_no_watcher_a_run_that_commits_goes_on_and_ends_after_as_many_cycles_unanswered_as_it_is_given(self):
        self.start("--prompt", PROMPT, "--continue", CONTINUE, wait=1, FEATURE_LOOP_UNWATCHED="2")
        until = time.time() + 90
        while time.time() < until and single_run.Run(self.root, "thing").running():
            time.sleep(0.3)
        state = json.loads(self.tool("status", "thing")[1])
        self.assertEqual((state["running"], state["status"], len(state["commits"])), (False, 0, 2))
        text = self.record()
        self.assertIn("decided to continue: no verdict came from the watcher in 1s, and the cycle committed", text)
        self.assertIn("the run was ended there (no verdict came from the watcher after 2 cycle(s) in a row", text)
        self.assertEqual(self.wait(kind="ended")["event"]["status"], 0)

    @cost("tool")
    def test_a_run_that_has_stopped_is_continued_in_its_session_and_a_stop_ends_it_after_the_cycle_under_way(self):
        started = self.start("--prompt", PROMPT, "--continue", CONTINUE, modes="wait")
        self.under_way()
        self.assertEqual(self.tool("start", "thing")[1].split(":")[0], "the run thing is already under way (pid %d)" % started["pid"])
        self.assertIn("ends after its cycle under way", self.tool("stop", "thing")[1])
        self.go.write_text("go\n")
        ended = self.wait(kind="ended")  # with no question: the stop was applied before one was asked
        self.assertEqual((ended["event"]["status"], len(ended["state"]["commits"])), (0, 1))
        self.assertEqual([e["type"] for e in conductor.read_events(self.run_dir())], ["cycle-start", "ended"])
        status, _, err = self.tool("start", "thing", "--fork", PARENT, ok=False)
        self.assertEqual(status, 1)
        self.assertIn("has its session", err)
        again = self.start(modes="commit")
        self.assertEqual((again["session"], again["firstCycleTakes"], again["newSession"]), (started["session"], "the continue message", False))
        self.wait()
        self.tool("answer", "thing", "stop", "--reason", "Enough.")
        ended = self.wait(kind="ended")
        self.assertEqual((ended["state"]["legs"], len(ended["state"]["commits"])), (2, 2))
        work = [c for c in self.calls() if c.get("work")]
        self.assertEqual([c["args"][c["args"].index("-p") + 1] for c in work], [PROMPT, CONTINUE])
        self.assertIn("--resume", work[1]["args"])

    @cost("tool")
    def test_a_run_in_a_workspace_of_its_own_is_made_from_the_lines_last_commit_and_landed_afterwards(self):
        (self.root / "notes/later.md").write_text("not committed\n")
        status, _, err = self.tool("start", "thing", "--prompt", PROMPT, "--workspace", "apart", "--brief", self.root / "notes/later.md",
                                   "--memory", "none", ok=False)
        self.assertEqual(status, 1)
        self.assertIn("is not committed as it stands", err)
        (self.root / "notes/later.md").unlink()
        self.jj("describe", "-m", "The brief")
        self.jj("new")
        started = self.start("--prompt", PROMPT, "--workspace", "apart", "--brief", "notes/brief.md")
        folder = self.tmp / "checkout-apart"
        self.assertEqual((started["folder"], started["workspace"], started["brief"]), (str(folder), "apart", "notes/brief.md"))
        self.assertIn("workspaceMade", started)
        first = self.wait()
        self.assertEqual(len(first["cycle"]["commits"]), 1)
        self.assertEqual(self.tool("land", "thing", ok=False)[0], 1, "not while the run is under way")
        self.tool("answer", "thing", "stop", "--reason", "Done.")
        self.wait(kind="ended")
        self.assertTrue(all(c["cwd"] == str(folder) for c in self.calls()))
        self.assertFalse((self.root / "work.txt").exists())
        self.assertIn("Made-up work, turn 1", self.record(folder=folder))
        landed = json.loads(self.tool("land", "thing")[1])
        self.assertIn("moved forward", landed["landed"])
        self.assertTrue((self.root / "work.txt").exists())
        self.assertIn("Made-up work, turn 1", self.jj("log", "--no-graph", "-r", "@-", "-T", "description"))

    @cost("tool")
    def test_a_fork_starts_the_run_from_a_copy_of_another_session_which_is_left_as_it_was(self):
        started = self.start("--prompt", PROMPT, "--fork", PARENT)
        self.assertEqual(started["forkOf"], PARENT)
        self.wait()
        self.tool("answer", "thing", "stop", "--reason", "Done.")
        self.wait(kind="ended")
        fork, first = self.calls()[:2]
        self.assertTrue(fork["parentVisible"])
        self.assertEqual(fork["args"][fork["args"].index("--resume") + 1], PARENT)
        self.assertEqual(fork["args"][fork["args"].index("--session-id") + 1], started["session"])
        self.assertEqual(fork["args"][fork["args"].index("--tools") + 1], "")
        self.assertTrue(fork["args"][fork["args"].index("-p") + 1].startswith(loop_stats.FORK_SINGLE))
        self.assertEqual((first["args"][first["args"].index("-p") + 1], first["args"][first["args"].index("--resume") + 1]),
                         (PROMPT, started["session"]))
        project = self.config / "projects" / str(self.root).replace("/", "-").replace(".", "-")
        self.assertFalse((project / f"{PARENT}.jsonl").exists(), "the parent's copy is removed after the one turn")
        self.assertIn(f"was forked from session {PARENT}", self.record())

    def codex(self, **more):
        self.codex_log = self.tmp / "codex.jsonl"
        return {"AGENT_CLIENT_CODEX": str(TOOLS / "codex_standin.py"), "CODEX_STANDIN_STATE": str(self.tmp / "codex"),
                "CODEX_STANDIN_LOG": str(self.codex_log), **more}

    def codex_calls(self):
        """What the stand-in was run for, the check of the instructions before the run (`debug prompt-input`) left out."""
        return [json.loads(line)["argv"][0] for line in self.codex_log.read_text().splitlines() if json.loads(line)["argv"][0] != "debug"]

    @cost("tool")
    def test_a_working_copy_another_session_left_stale_after_a_turn_is_recovered_and_the_run_goes_on(self):
        # 2026-11-23 21:15: a turn ended well, jj then said "The working copy is stale", and the run ended with
        # status 1 before its verdict.
        self.start("--prompt", PROMPT, "--continue", CONTINUE, modes="stale,commit", STANDIN_OTHER=str(self.tmp / "other"))
        first = self.wait()
        self.assertEqual(first["cycle"]["cycle"], 1)
        self.assertIn("Made-up work, turn 1", " ".join(first["cycle"]["commits"]))
        log = (self.run_dir() / "loop.log").read_text()
        self.assertIn("the working copy is stale", log)
        self.assertIn("ran jj workspace update-stale", log)
        self.tool("answer", "thing", "continue", "--reason", "It goes on.")
        second = self.wait()
        self.assertEqual(second["cycle"]["cycle"], 2)
        self.tool("answer", "thing", "stop", "--reason", "Done.")
        self.assertEqual(self.wait(kind="ended")["event"]["status"], 0)
        self.assertRegex(self.record(), r"- \S+ \S+: the working copy was stale after another session's jj operation, "
                                        r"and unstale\.py recovered it")
        self.assertEqual((self.root / "other.txt").read_text(), "another session's file\n")

    @cost("tool")
    def test_a_stale_working_copy_that_unstale_cannot_recover_still_ends_the_run_for_a_person(self):
        (self.root / "llm-dlc/tools/unstale.py").write_text("import sys\nprint('two copies with edits of their own')\nsys.exit(1)\n")
        self.start("--prompt", PROMPT, "--continue", CONTINUE, modes="stale", STANDIN_OTHER=str(self.tmp / "other"))
        ended = self.wait(kind="ended")
        self.assertEqual(ended["event"]["status"], 1)
        log = (self.run_dir() / "loop.log").read_text()
        self.assertIn("two copies with edits of their own", log)
        self.assertIn("unstale.py could not recover the working copy; it needs a person", log)

    @cost("tool")
    def test_a_last_cycle_whose_turn_failed_ends_the_run_needing_attention_and_not_as_done(self):
        # One cycle, so no question is put to the watcher and the count ends the run: before 2026-11-19 a turn that
        # had failed there was logged, compacted over and summarized, and the run ended with status 0.
        self.start("--prompt", PROMPT, "--client", "codex", "--cycles", 1, **self.codex(CODEX_STANDIN_MODES="fail"))
        ended = self.wait(kind="ended")
        self.assertEqual((ended["event"]["status"], ended["state"]["running"]), (1, False))
        self.assertIn("a turn or a compaction did not end well", ended["event"]["note"])
        text = self.record()
        self.assertRegex(text, r"Stopped \S+ \S+: the turn of cycle 1 did not end well: the client reported error_\w+: "
                               r".*usage limit.*; session \S+ needs attention\.")
        self.assertNotIn("Ended ", text)
        self.assertEqual(self.codex_calls(), ["exec"])  # no compaction and no summary over a turn that failed
        # a turn that was cut off leaves no result at all, and is no cycle's work either
        self.start("--prompt", PROMPT, "--client", "codex", "--cycles", 1, name="cut", **self.codex(CODEX_STANDIN_MODES="truncated",
                   CODEX_STANDIN_STATE=str(self.tmp / "codex-cut")))
        ended = self.wait("cut", kind="ended")
        self.assertEqual(ended["event"]["status"], 1)
        self.assertRegex(self.record("cut"), r"Stopped \S+ \S+: the turn of cycle 1 did not end well: the client ")

    @cost("tool")
    def test_a_compaction_that_fails_is_not_a_normal_end_and_a_turn_that_ends_well_with_no_commit_still_is(self):
        self.start("--prompt", PROMPT, "--client", "codex", "--cycles", 1,
                   **self.codex(CODEX_STANDIN_MODES="commit", CODEX_STANDIN_COMPACT="fail"))
        ended = self.wait(kind="ended")
        self.assertEqual(ended["event"]["status"], 1)
        text = self.record()
        self.assertRegex(text, r"Stopped \S+ \S+: the compaction after cycle 1 did not end well: .*; session \S+ needs attention\.")
        self.assertIn("Made-up work by the stand-in, turn 1", text)  # the cycle's commit is in the record
        self.assertIn("## Summary", text)                             # and the run that was ending gets its summary
        # the count's last cycle ended well and made no commit: the run ends as it always did
        self.start("--prompt", PROMPT, "--client", "codex", "--cycles", 1, name="quiet",
                   **self.codex(CODEX_STANDIN_MODES="idle", CODEX_STANDIN_STATE=str(self.tmp / "codex-quiet")))
        ended = self.wait("quiet", kind="ended")
        self.assertEqual(ended["event"]["status"], 0)
        self.assertRegex(self.record("quiet"), r"- cycle 1, \S+ \S+: no commit\n(.|\n)*Ended \S+ \S+ after 1 cycle\(s\)\.")

    @cost("tool")
    def test_a_restart_keeps_the_leg_befores_limits_and_says_so(self):
        started = self.start("--prompt", PROMPT, "--cycles", 1)
        self.assertNotIn("keptFromTheLegBefore", started)
        self.assertEqual(self.wait(kind="ended")["event"]["status"], 0)
        # a bare restart: the count of cycles and the queue left alone are the leg before's, not the defaults
        with mock.patch.dict(os.environ, {"STANDIN_MODES": "commit"}):
            again = json.loads(self.tool("start", "thing", "--memory", "none", "--verdict-wait", 30)[1])
        self.assertEqual((again["cycles"], again["verificationQueue"]), (1, "off"))
        self.assertEqual(len(again["keptFromTheLegBefore"]), 2)
        self.assertIn("--cycles 0 removes the limit", again["keptFromTheLegBefore"][0])
        self.assertIn("--verification turns it on", again["keptFromTheLegBefore"][1])
        self.assertEqual(self.wait(kind="ended")["event"]["status"], 0)  # one cycle more, and it ended by its count
        self.assertRegex(self.record(), r"Ended \S+ \S+ after 1 cycle\(s\)\.")
        # a limit given anew is the leg's own, and 0 removes it
        with mock.patch.dict(os.environ, {"STANDIN_MODES": "commit", "STANDIN_GO": str(self.go)}):
            free = json.loads(self.tool("start", "thing", "--memory", "none", "--verdict-wait", 30, "--cycles", 0, "--no-verification")[1])
        self.assertEqual((free["cycles"], "keptFromTheLegBefore" in free), ("no limit", False))
        self.tool("stop", "thing", "--now")

    @cost("tool")
    def test_a_codex_run_starts_only_with_the_checkouts_instructions_and_restarts_only_with_its_thread(self):
        codex = self.codex(CODEX_STANDIN_MODES="commit")
        # what Codex reads first when it is there: the run would be given other instructions than this checkout's
        (self.root / "AGENTS.md").write_text("Other instructions.\n")
        with mock.patch.dict(os.environ, codex):
            status, _, err = self.tool("start", "thing", "--prompt", PROMPT, "--client", "codex", "--memory", "none", "--no-verification", ok=False)
        self.assertEqual(status, 1)
        self.assertIn("AGENTS.md shadows CLAUDE.md", err)
        self.assertFalse((self.run_dir() / "watch.json").exists() and json.loads((self.run_dir() / "watch.json").read_text()).get("loop"))
        (self.root / "AGENTS.md").unlink()
        started = self.start("--prompt", PROMPT, "--client", "codex", "--cycles", 1, **codex)
        self.assertEqual(self.wait(kind="ended")["event"]["status"], 0)
        binding = self.root / "llm-dlc/loop-summaries/agent-sessions" / f"{started['session']}.json"
        thread = json.loads(binding.read_text())["thread"]
        # the folder no longer says which thread the run had: a new one would be told to go on with work it never saw
        kept = binding.read_text()
        binding.unlink()
        with mock.patch.dict(os.environ, codex):
            status, _, err = self.tool("start", "thing", "--memory", "none", ok=False)
        self.assertEqual(status, 1)
        self.assertIn(f"had a Codex thread ({thread})", err)
        self.assertEqual(self.codex_calls().count("exec"), 2)  # the one cycle and its summary: nothing since
        binding.write_text(kept)
        with mock.patch.dict(os.environ, codex):
            again = json.loads(self.tool("start", "thing", "--memory", "none")[1])
        self.assertEqual((again["cycles"], again["firstCycleTakes"]), (1, "the continue message"))
        self.assertEqual(self.wait(kind="ended")["event"]["status"], 0)

    @cost("tool")
    def test_a_run_given_to_codex_takes_the_same_texts_keeps_its_own_thread_and_compacts_between_cycles(self):
        codex_log = self.tmp / "codex.jsonl"
        codex = {"AGENT_CLIENT_CODEX": str(TOOLS / "codex_standin.py"), "CODEX_STANDIN_STATE": str(self.tmp / "codex"),
                 "CODEX_STANDIN_LOG": str(codex_log), "CODEX_STANDIN_MODES": "commit"}
        started = self.start("--prompt", PROMPT, "--continue", CONTINUE, "--client", "codex", "--model", "claude-opus-5-5", **codex)
        self.assertEqual((started["client"], started["model"], started["runs"], started["effort"]),
                         ("codex", "claude-opus-5-5", "gpt-6.2-sol", "high"))
        first = self.wait()
        self.assertEqual((first["kind"], first["event"]["type"], first["cycle"]["cycle"]), ("question", "run", 1))
        self.assertIn(f"the stand-in's report of turn 1 (commit); it was told: {PROMPT}", first["cycle"]["report"])
        self.assertEqual(len(first["cycle"]["commits"]), 1)
        self.assertIn("Made-up work by the stand-in, turn 1", first["cycle"]["commits"][0])
        self.assertIsNone(first["cycle"]["cost"])  # Codex reports tokens: the dollars are not known, and not nought
        self.assertIsNone(json.loads(self.tool("status", "thing")[1])["spent"])  # nor is the run's spend
        self.tool("answer", "thing", "continue", "--reason", "The thing does not work yet.")
        second = self.wait(kind="question")
        self.assertEqual(second["cycle"]["cycle"], 2)
        self.assertIn(f"report of turn 2 (commit); it was told: {CONTINUE}", second["cycle"]["report"])
        self.tool("answer", "thing", "stop", "--reason", "The thing works.")
        self.assertEqual(self.wait(kind="ended")["kind"], "ended")
        calls = [json.loads(line) for line in codex_log.read_text().splitlines()]
        # before anything of the run: the check that Codex is given the checkout's instructions in the agent's folder
        self.assertEqual(calls[0]["argv"][:2], ["debug", "prompt-input"])
        calls = calls[1:]
        work = [c["argv"] for c in calls if c["argv"][0] == "exec"]
        # the first turn starts a thread with the user's prompt, word for word, on the model that stands for Opus 5.5
        self.assertNotIn("resume", work[0])
        self.assertEqual((work[0][-1], work[0][work[0].index("-m") + 1]), (PROMPT, "gpt-6.2-sol"))
        self.assertIn('model_reasoning_effort="high"', work[0])
        thread = json.loads((self.root / "llm-dlc/loop-summaries/agent-sessions" / f"{started['session']}.json").read_text())["thread"]
        # between the cycles the thread is compacted by the client, not sent the word /compact
        self.assertEqual([c["argv"][0] for c in calls][:3], ["exec", "app-server", "exec"])
        self.assertEqual((self.tmp / "codex" / "compacted").read_text().split()[0], thread)
        self.assertNotIn("/compact", [argv[-1] for argv in work])
        # every later turn resumes that thread, and the second cycle takes the continue message as it is
        self.assertTrue(all(argv[1] == "resume" and argv[-2] == thread for argv in work[1:]))
        self.assertEqual(work[1][-1], CONTINUE)
        # nothing of the run or of the session that started it reaches the worker, and Claude Code ran no turn
        self.assertEqual([(c["identity"], c["run"]) for c in calls], [([], [])] * len(calls))
        self.assertEqual(self.calls(), [])
        text = self.record()
        self.assertIn("The session's turns are carried by codex, which runs gpt-6.2-sol for the claude-opus-5-5 this loop asks for.", text)
        # and names the thread Codex gave the session, under which its trace is: the statistics and the published
        # record find the run by it (loop_stats.record_session)
        self.assertIn(f"Codex thread {thread} carries session {started['session']}.", text)
        self.assertEqual(loop_stats.record_session(text), thread)
        self.assertRegex(text, r"Ended \S+ \S+ after 2 cycle\(s\): the run was ended there \(the watcher: The thing works\.\)")
        self.assertEqual(json.loads(self.tool("status", "thing")[1])["client"], "codex")
        # a run keeps its client, and a Codex session is not a fork of a Claude Code conversation
        status, _, err = self.tool("start", "thing", "--client", "claude", ok=False)
        self.assertEqual(status, 1)
        self.assertIn("keeps the client it started with", err)
        status, _, err = self.tool("start", "other", "--prompt", PROMPT, "--client", "codex", "--fork", PARENT, ok=False)
        self.assertIn("cannot start as a fork", err)
        status, _, err = self.tool("start", "other", "--prompt", PROMPT, "--client", "codex", "--model", "claude-sonnet-5-5", ok=False)
        self.assertIn("no Codex model stands for claude-sonnet-5-5", err)

    @cost("tool")
    def test_a_setup_phase_runs_the_templates_texts_on_opus_and_puts_its_notes_into_every_copy_of_the_brief(self):
        (self.root / "llm-dlc/loops").mkdir(parents=True)
        shutil.copy(TOOLS.parent / "loops/setup-agent-template.md", self.root / "llm-dlc/loops/setup-agent-template.md")
        for args, why in ((("setup", "prep"), "for a brief: --brief FILE"),
                          (("setup", "prep", "--brief", "notes/brief.md", "--prompt", PROMPT), "texts are llm-dlc/loops/setup-agent-template.md's"),
                          (("notes", "prep"), "is not a setup run")):
            status, _, err = self.tool(*args, ok=False)
            self.assertEqual(status, 1, args)
            self.assertIn(why, err, args)
        with mock.patch.dict(os.environ, {"STANDIN_MODES": "commit"}):
            started = json.loads(self.tool("setup", "prep", "--brief", self.root / "notes/brief.md", "--memory", "none",
                                           "--no-verification", "--verdict-wait", 30)[1])
        self.assertEqual((started["client"], started["model"], started["effort"]), ("claude", "claude-opus-5-5", "high"))
        self.assertEqual(started["setup"], {"brief": "notes/brief.md", "record": "llm-dlc/loops/brief-setup.md"})
        self.wait("prep")
        first = self.prompts()[0]
        self.assertTrue(first.startswith("You are the SETUP AGENT for `notes/brief.md`."), first[:80])
        self.assertIn("`llm-dlc/loops/brief-setup.md`", first)
        self.assertNotIn("{", first)
        self.assertIn("claude-opus-5-5", self.calls()[0]["args"])
        self.assertTrue((self.run_dir("prep") / "continue.md").read_text().startswith("Continue as the SETUP AGENT"))
        self.tool("answer", "prep", "stop", "--reason", "Only its jobs are left.")
        self.wait("prep", kind="ended")
        status, _, err = self.tool("setup", "prep", "--record", "elsewhere.md", ok=False)  # continued, never re-set up
        self.assertIn("only continues it", err)
        status, _, err = self.tool("notes", "prep", ok=False)
        self.assertIn("has not written it", err)
        record = self.root / "llm-dlc/loops/brief-setup.md"
        record.write_text("# Setup\n\nDetail.\n\n## Setup Agent Notes\n\n- Everything is cached.\n")
        original = self.tmp / "original-brief.md"
        original.write_text("# The made-up thing\n\nIt should work.\n")
        out = json.loads(self.tool("notes", "prep", "--to", original)[1])
        self.assertEqual(out["changed"], [str(self.root / "notes/brief.md"), str(original)])
        self.assertEqual(out["next"], "commit notes/brief.md with `sync.py commit --only`")
        for path in (self.root / "notes/brief.md", original):
            self.assertEqual(path.read_text(), "# The made-up thing\n\nIt should work.\n\n## Setup Agent Notes\n\n- Everything is cached.\n")
        self.assertEqual(json.loads(self.tool("notes", "prep", "--to", original)[1])["changed"], [], "a second time changes nothing")
        record.write_text("# Setup\n\n## Setup Agent Notes\n\n- Now verified too.\n")
        self.tool("notes", "prep")
        self.assertIn("- Now verified too.", (self.root / "notes/brief.md").read_text())
        self.assertNotIn("Everything is cached", (self.root / "notes/brief.md").read_text(), "replaced, not added again")

    @cost("tool")
    def test_a_generation_phase_runs_the_brief_author_on_astra_at_ultra_compacting_at_600k(self):
        (self.root / "llm-dlc/loops").mkdir(parents=True)
        for name in ("brief-generation-template.md", "brief-generation-handoff.md"):
            shutil.copy(TOOLS.parent / "loops" / name, self.root / "llm-dlc/loops" / name)
        (self.root / "notes/prs.md").write_text("- [PR](https://github.com/made/up/pull/1)\n")
        for args, why in ((("generate", "gen"), "--input FILE --output FILE"),
                          (("generate", "gen", "--input", "notes/prs.md", "--output", "x.txt"), "a Markdown file in the checkout"),
                          (("generate", "gen", "--input", "notes/prs.md", "--output", "/elsewhere/b.md"), "written in the checkout"),
                          (("generate", "gen", "--input", "notes/prs.md", "--output", "b.md", "--prompt", PROMPT),
                           "texts are llm-dlc/loops/brief-generation-template.md's"),
                          (("generate", "gen", "--input", "notes/prs.md", "--output", "b.md", "--compact-at", "lots"),
                           "--compact-at: not a count of tokens")):
            status, _, err = self.tool(*args, ok=False)
            self.assertEqual(status, 1, args)
            self.assertIn(why, err, args)
        with mock.patch.dict(os.environ, self.codex(CODEX_STANDIN_MODES="commit")):
            started = json.loads(self.tool("generate", "gen", "--input", "notes/prs.md", "--output", "llm-dlc/loops/prs-brief.md",
                                           "--memory", "none", "--no-verification", "--verdict-wait", 30)[1])
            self.assertEqual((started["client"], started["model"], started["effort"], started["compactAt"]),
                             ("codex", "gpt-6.2-astra", "ultra", "600k"))
            self.assertEqual(started["generate"], {"input": "notes/prs.md", "output": "llm-dlc/loops/prs-brief.md",
                                                   "record": "llm-dlc/loops/prs-brief-generation.md"})
            self.assertIsNone(started["brief"], "the brief does not exist yet: the texts name the handoff")
            self.wait("gen")
            self.tool("answer", "gen", "stop", "--reason", "The brief is complete.")
            self.wait("gen", kind="ended")
        work = [json.loads(line)["argv"] for line in self.codex_log.read_text().splitlines()]
        work = [argv for argv in work if argv[0] == "exec"]
        self.assertIn('model_reasoning_effort="ultra"', work[0])
        self.assertIn("model_auto_compact_token_limit=600000", work[0])
        first = work[0][-1]
        self.assertTrue(first.startswith("You are the BRIEF AUTHOR for the pull requests listed in `notes/prs.md`."), first[:90])
        for named in ("`llm-dlc/loops/brief-generation-handoff.md`", "`llm-dlc/loops/prs-brief.md`",
                      "`llm-dlc/loops/prs-brief-generation.md`", "The brief is complete"):
            self.assertIn(named, first)
        self.assertNotIn("{", first)
        self.assertTrue((self.run_dir("gen") / "continue.md").read_text().startswith("Continue writing the brief `llm-dlc/loops/prs-brief.md`"))
        status, _, err = self.tool("generate", "gen", "--input", "notes/prs.md", ok=False)  # continued, never re-generated
        self.assertIn("only continues it", err)
        status, _, err = self.tool("generate", "thing2", "--input", "notes/prs.md", "--output", "b.md", "--client", "claude", ok=False)
        self.assertIn("Codex's alone", err, "a Claude Code brief author is given an effort of its own")

    @cost("tool")
    def test_what_cannot_start_says_why_and_starts_nothing(self):
        for args, why in ((("start", "thing"), "needs its first text"),
                          (("start", "Thing", "--prompt", PROMPT), "lower-case letters"),
                          (("start", "thing", "--prompt", PROMPT, "--prompt-file", "x"), "not both"),
                          (("start", "thing", "--prompt", " "), "the text is empty"),
                          (("start", "thing", "--prompt", PROMPT, "--session", PARENT, "--fork", PARENT), "give one of them"),
                          (("start", "thing", "--prompt", PROMPT, "--session", PARENT), "no session"),
                          (("start", "thing", "--prompt", PROMPT, "--fork", PARENT.replace("0", "1")), "no transcript"),
                          (("start", "thing", "--prompt", PROMPT, "--brief", "nowhere.md"), "no brief at"),
                          (("start", "thing", "--prompt", PROMPT, "--cycles", "-1"), "1 or more"),
                          (("status", "thing"), "no run thing here"),
                          (("message", "thing"), "no run thing here")):
            status, _, err = self.tool(*args, "--memory", "none", ok=False) if args[0] == "start" else self.tool(*args, ok=False)
            self.assertEqual(status, 1, args)
            self.assertIn(why, err, args)
        self.assertFalse(self.run_dir().exists())
        self.assertEqual(self.calls(), [])
        self.assertEqual(json.loads(self.tool("list")[1]), [])


class TheRecordAndTheSummary(unittest.TestCase):
    RECORD = """# Feature loop: single-thing

Started 2026-11-18 10:00:00 UTC, no limit on cycles, session 0f0f0f0f-1111-4222-8333-444455556666, claude-fable-5-2 at high effort, after change abc.

> Make the made-up thing work.

Every later cycle takes the run's continue message as it stands when the cycle starts, and after each cycle a watcher outside the session decides whether there is another. The message at the start:

> Go on.

## Commits

- cycle 1, 2026-11-18 10:10:00, `abcdefgh`: Made-up work
  - decided to continue: the watcher: more to do
- cycle 2, 2026-11-18 10:20:00: no commit
  - decided to stop: the watcher: it decided the work was done

Ended 2026-11-18 10:21:00 after 2 cycle(s): the run was ended there (the watcher: it decided the work was done).
"""

    def test_the_loop_statistics_read_a_runs_record_and_count_every_text_it_sent_as_a_cycle(self):
        record = loop_stats.parse_record("2026-11-18-100000-single-thing", self.RECORD)
        self.assertTrue(record["single"])
        self.assertEqual((record["loop"], record["instruction"]), ("single-thing", "Make the made-up thing work."))
        self.assertEqual((record["cycles"][1]["decision"], sorted(record["cycles"])), ("continue", [1]))
        self.assertEqual(record["end"]["reason"], "watcher ended it", "not what the watcher's own words happen to say")
        other = self.RECORD.replace("Every later cycle takes the run's continue message", "Each cycle takes")
        self.assertFalse(loop_stats.parse_record("x", other)["single"])
        self.assertEqual(loop_stats._role({"kind": "prompt", "text": loop_stats.FORK_SINGLE + ": you are now"}), ("fork", None))

    def test_a_summary_says_where_the_cycle_the_commits_the_spend_and_the_queue_stand(self):
        s = {"name": "thing", "running": True, "elapsed": "1 h 05 min",
             "cycle": {"cycle": 3, "began": conductor.now(), "state": "running", "toolCalls": 41, "lastOutput": "2 min ago"},
             "question": None, "commits": ["abcd1234 One", "efgh5678 Two"], "spent": 12.5, "cycleCosts": {"1.1": 5.0, "1.2": 7.5},
             "jobs": {"pending": 1, "running": 0, "finished": 0}, "messagesSet": 2, "messageSet": "2026-11-18T10:22:00Z",
             "continueMessage": "Now the\ntests."}
        text = single_run.summary(s)
        self.assertIn("single-agent run thing · 1 h 05 min", text)
        self.assertIn("- cycle 3 running, 0 min in: 41 tool calls, last output 2 min ago", text)
        self.assertIn("- commits this run: 2, the last: efgh5678 Two", text)
        self.assertIn("- spend: $12.50 over 2 cycle(s) that have ended", text)
        self.assertIn("- verification queue: 1 pending, 0 running, 0 back and not collected", text)
        self.assertIn("- the continue message was last set 2026-11-18T10:22:00Z: Now the tests.", text)
        quiet = single_run.summary({**s, "running": False, "cycle": None, "commits": [], "cycleCosts": {}, "messagesSet": 1,
                                    "jobs": {"pending": 0, "running": 0, "finished": 0}, "question": {"type": "run", "n": 4}})
        self.assertIn("· not running", quiet)
        self.assertIn("a question is open (run, event 4)", quiet)
        self.assertNotIn("spend", quiet)

    def test_a_text_comes_from_the_command_line_or_a_file_and_a_run_has_a_plain_name(self):
        self.assertEqual(single_run.text_of("  Go on. \n", None, "--continue"), "Go on.\n")
        self.assertIsNone(single_run.text_of(None, None, "--continue"))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "text.md").write_text("Two\nlines.\n\n")
            self.assertEqual(single_run.text_of(None, str(Path(tmp) / "text.md"), "--prompt-file"), "Two\nlines.\n")
            with self.assertRaisesRegex(single_run.Problem, "can't be read"):
                single_run.text_of(None, str(Path(tmp) / "none.md"), "--prompt-file")
            run = single_run.Run(Path(tmp), "a-run-2")
            self.assertEqual((run.loop, run.dir), ("single-a-run-2", Path(tmp) / "llm-dlc/loop-summaries/single-a-run-2"))
            self.assertTrue(single_run.set_message(run, "One.\n", "at the start"))
            self.assertFalse(single_run.set_message(run, "One.\n", "again"))
            self.assertEqual([m["text"] for m in single_run.messages(run)], ["One."])
        for bad in ("", "Has Capitals", "has space", "-leading", "x" * 49, "a/b"):
            with self.assertRaises(single_run.Problem):
                single_run.Run(Path("/nowhere"), bad)



class TheSetupPhase(unittest.TestCase):
    TEMPLATE = (TOOLS.parent / "loops/setup-agent-template.md").read_text()

    def test_the_template_gives_two_texts_with_the_brief_and_the_record_filled_in(self):
        record = single_run.setup_record("llm-dlc/loops/spring-briefs.md")
        self.assertEqual(record, "llm-dlc/loops/spring-briefs-setup.md")
        first, cont = single_run.setup_texts(self.TEMPLATE, "llm-dlc/loops/spring-briefs.md", record)
        self.assertTrue(first.startswith("You are the SETUP AGENT for `llm-dlc/loops/spring-briefs.md`."))
        self.assertTrue(cont.startswith("Continue as the SETUP AGENT for `llm-dlc/loops/spring-briefs.md`."))
        for text in (first, cont):
            self.assertNotIn("{", text)
            self.assertIn("`llm-dlc/loops/spring-briefs-setup.md`", text)
            self.assertIn(single_run.SETUP_NOTES, text)
        self.assertNotIn("# Setup agent template", first, "the template's explanation is not a text")
        self.assertIn("Do not look for a way around it", first)
        with self.assertRaisesRegex(single_run.Problem, "needs two sections"):
            single_run.setup_texts("## First text\n\nOnly one.\n", "b.md", "r.md")

    def test_the_notes_are_their_section_alone_and_go_into_a_brief_once(self):
        record = "# Setup\n\n## Revisions\n\nx\n\n## Setup Agent Notes\n\n- ready\n\n### Gaps\n\n- one\n\n## Afterwards\n\ny\n"
        notes = single_run.notes_of(record)
        self.assertEqual(notes, "## Setup Agent Notes\n\n- ready\n\n### Gaps\n\n- one")
        self.assertIsNone(single_run.notes_of("# Setup\n\n## Setup agent notes, lower case\n"))
        brief = "# Brief\n\nBody.\n\n[link]: https://example.invalid\n"
        once = single_run.with_notes(brief, notes)
        self.assertEqual(once, brief.rstrip() + "\n\n" + notes + "\n")
        self.assertEqual(single_run.with_notes(once, notes), once)
        again = single_run.with_notes(once, notes.replace("ready", "all ready"))
        self.assertEqual(again.count(single_run.SETUP_NOTES), 1)
        self.assertIn("- all ready", again)

class TheGenerationPhase(unittest.TestCase):
    TEMPLATE = (TOOLS.parent / "loops/brief-generation-template.md").read_text()

    def test_the_template_gives_two_texts_with_the_input_the_brief_the_record_and_the_handoff_filled_in(self):
        self.assertEqual(single_run.generation_record("llm-dlc/loops/prs-brief.md"), "llm-dlc/loops/prs-brief-generation.md")
        fills = {"input": "`in.md`", "output": "`out.md`", "record": "`rec.md`", "handoff": f"`{single_run.GENERATE_HANDOFF}`"}
        first, cont = single_run.template_texts(self.TEMPLATE, fills, single_run.GENERATE_TEMPLATE)
        for text in (first, cont):
            self.assertNotIn("{", text)
            for value in fills.values():
                self.assertIn(value, text)
        self.assertNotIn("# Brief generation template", first, "the template's explanation is not a text")
        self.assertIn("Setup Agent Notes", first, "the author leaves the setup notes to the setup agent")
        self.assertTrue((TOOLS.parent / "loops/brief-generation-handoff.md").read_text().startswith(
            "# Generate a verification brief from a Java pull request"), "the user's handoff, as they wrote it")
        with self.assertRaisesRegex(single_run.Problem, "brief-generation-template.md needs two sections"):
            single_run.template_texts("## First text\n\nOnly one.\n", fills, single_run.GENERATE_TEMPLATE)
        self.assertEqual(single_run.setup_texts("## First text\n\nFor {brief}, {record}.\n\n## Continue message\n\nOn {brief}.\n",
                                                "b.md", "r.md"), ("For `b.md`, r.md.\n", "On `b.md`.\n"),
                         "the setup texts are filled as before")


if __name__ == "__main__":
    unittest.main()
