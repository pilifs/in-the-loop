#!/usr/bin/env python3
"""Tests for watch.py, the watcher's tools: the sessions it starts, what it waits for, its summary and what it
changes from one summary to the next, and the user's requests it keeps for the loop.
Run: python3 llm-dlc/tools/test_watch.py
Everything is made up: a temporary checkout, a stand-in `claude` on PATH that records how it was called, a job queue
that is a file, and events written as the loop writes them. No model is called and no loop is started."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import conductor
import watch

REPO = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

STANDIN = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["STANDIN_LOG"], "a") as f:
    f.write(json.dumps({"args": args, "cwd": os.getcwd(), "connectors": os.environ.get("ENABLE_CLAUDEAI_MCP_SERVERS")}) + "\n")
print(json.dumps({"type": "assistant", "message": {"content": [{"type":"tool_use","name":"Bash"}]}}))
ok = os.environ.get("STANDIN_FAIL") != "1"
print(json.dumps({"type": "result", "subtype": "success" if ok else "error_during_execution", "session_id": "made-up",
                  "result": "The stand-in's report: three changes, ordered 902 900 901."}))
sys.exit(0 if ok else 1)
'''
PIPELINE = ("import json, os\n"
            "print(open(os.environ['STANDIN_QUEUE']).read() if os.path.exists(os.environ['STANDIN_QUEUE']) else "
            "json.dumps({'pending': [], 'running': [], 'finished, not collected': [], 'collected': []}))\n")
NOW = 1_800_000_000.0


def queue(pending=(), running=(), finished=(), collected=()):
    return json.dumps({"pending": list(pending), "running": list(running), "finished, not collected": list(finished),
                       "collected": list(collected)})


class Made(unittest.TestCase):
    """A made-up checkout with a run directory, a queue, and a stand-in claude."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.root = self.tmp / "checkout"
        (self.root / "verification").mkdir(parents=True)
        (self.root / "verification/pipeline.py").write_text(PIPELINE)
        (self.root / "examples").mkdir()
        self.run = watch.Run(self.root)
        self.queue, self.log = self.tmp / "queue.json", self.tmp / "standin.jsonl"
        bin = self.tmp / "bin"
        bin.mkdir()
        (bin / "claude").write_text(STANDIN)
        (bin / "claude").chmod(0o755)
        env = {"PATH": f"{bin}:{os.environ['PATH']}", "STANDIN_LOG": str(self.log), "STANDIN_QUEUE": str(self.queue),
               "CLAUDE_CONFIG_DIR": str(self.tmp / "config"), "IN_THE_LOOP_MODE": "development"}
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)

    def call(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            status = watch.main(["--root", str(self.root), *[str(a) for a in argv]])
        return status, out.getvalue()

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def loop(self, *examples, pid=None):
        """A proof loop's run.json, as prove-loop.sh writes it; by default one whose process is this test's."""
        self.run.dir.mkdir(parents=True, exist_ok=True)
        (self.run.dir / "run.json").write_text(json.dumps(
            {"session": "made-up", "pid": pid or os.getpid(), "examples": list(examples), "ended": None,
             "started": conductor.now()}))

    def note(self, kind, **fields):
        return conductor.append_event(self.run.dir, type=kind, **fields)


@cost("tool")
class StageTest(Made):
    def flag(self, call, name):
        return call["args"][call["args"].index(name) + 1]

    def test_the_evaluation_runs_in_the_fixed_session_on_fable_at_medium_effort(self):
        status, out = self.call("stage", "evaluate", "Evaluate these changes")
        self.assertEqual(status, 0)
        self.assertIn("three changes, ordered 902 900 901", out)
        first = self.calls()[0]
        session = self.call("session")[1].strip()
        self.assertEqual((self.flag(first, "--model"), self.flag(first, "--effort"), self.flag(first, "--session-id")),
                         ("claude-fable-5-2", "medium", session))
        self.assertEqual((self.flag(first, "-p"), first["cwd"]), ("Evaluate these changes", str(self.root)))
        watch.transcript(self.root, session).parent.mkdir(parents=True)
        watch.transcript(self.root, session).write_text("{}\n")
        self.call("stage", "evaluate", "The user's answers")
        self.assertEqual(self.flag(self.calls()[1], "--resume"), session, "a later turn continues the same session")
        self.assertEqual((self.run.dir / "stage-evaluate.jsonl").read_text().count('"type": "result"'), 2)

    def test_the_setup_runs_in_a_session_of_its_own_on_opus_at_high_effort(self):
        self.call("stage", "setup", "Set the examples up")
        only = self.calls()[0]
        self.assertEqual((self.flag(only, "--model"), self.flag(only, "--effort")), ("claude-opus-5-5", "high"))
        self.assertNotIn("--session-id", only["args"])
        self.assertNotIn("--resume", only["args"])
        self.assertEqual(self.run.read()["stages"]["setup"]["ok"], True)

    def test_in_a_runtime_checkout_a_stage_starts_clean_and_in_a_development_one_as_a_plain_claude(self):
        self.call("stage", "setup", "Set the examples up")
        with mock.patch.dict(os.environ, {"IN_THE_LOOP_MODE": "runtime"}):
            self.call("stage", "setup", "Set the examples up")
        plain, clean = self.calls()
        self.assertNotIn("--strict-mcp-config", plain["args"])
        self.assertEqual((self.flag(clean, "--setting-sources"), clean["connectors"]), ("project,local", "false"))
        self.assertIn("--strict-mcp-config", clean["args"])

    def test_a_stage_that_fails_says_so_by_its_status(self):
        with mock.patch.dict(os.environ, {"STANDIN_FAIL": "1"}):
            self.assertEqual(self.call("stage", "setup", "Set the examples up")[0], 1)
        self.assertEqual(self.run.read()["stages"]["setup"]["ok"], False)

    def test_the_fixed_session_is_kept_until_a_new_one_is_asked_for(self):
        first = self.call("session")[1]
        self.assertEqual(self.call("session")[1], first)
        self.assertNotEqual(self.call("session", "--new")[1], first)


class SummaryTest(Made):
    def state(self, **over):
        base = {"time": NOW, "started": NOW - 3900, "session": "made-up",
                "examples": ["900", "901", "902"], "items": {"900": "finished", "901": "under way"}, "item": "901",
                "cycle": 3, "itemCycle": 2, "cycleStarted": NOW - 1500,
                "turn": {"toolCalls": 41, "lastOutput": NOW - 120},
                "claims": {"900": {"fixed": "established"}, "901": {"fixed": None, "kept": "established"}, "902": {}},
                "exampleState": {"900": "decided", "901": "prepared", "902": "prepared"}, "head": "kkkkkkkk",
                "jobs": {"pending": ["20260101-000002-example-901-kept"], "running": [], "finished": [],
                         "collected": {"20260101-000001-example-900-fixed": "passed"}},
                "unfinished": {"901": ["20260101-000002-example-901-kept"]}, "loopAlive": True, "ended": None,
                "verification": 4242, "mergeQueue": [], "asked": None}
        return {**base, **over}

    def test_the_first_summary_says_where_everything_stands(self):
        text = watch.render(self.state(), None, self.root)
        self.assertIn("1 h 05 min into the run · the first summary", text)
        self.assertIn("**Loop:** cycle 3, on example 901, its cycle 2, 25 min in, 41 tool calls so far, last output 2 min ago", text)
        self.assertIn("**Examples:** 1 of 3 done (900) · not started: 902", text)
        self.assertIn("**Example 901:** prepared: 1 no answer yet, 1 established; 1 of its verification jobs not in yet", text)
        self.assertIn("**Verification jobs:** 0 running, 1 queued, 0 finished and not collected, 1 collected", text)

    def test_what_changed_since_the_last_summary_comes_first(self):
        last = watch.snapshot(self.state(time=NOW - 600, cycle=2, items={"900": "under way"},
                                         claims={"900": {"fixed": None}, "901": {"fixed": None, "kept": None}, "902": {}},
                                         jobs={"pending": [], "running": [], "finished": [], "collected": {}}))
        text = watch.render(self.state(), last, self.root)
        changed = text.split("**Changed**")[1].split("**Loop:**")[0]
        for line in ("- example 900: under way → finished", "- example 901 started",
                     "- example 900, claim fixed: no answer → established", "- example 901, claim kept: no answer → established",
                     "- job 20260101-000001-example-900-fixed is in: passed", "- job 20260101-000002-example-901-kept was queued",
                     "- the loop is on cycle 3 (it was on 2)"):
            self.assertIn(line, changed)
        self.assertLess(text.index("**Changed**"), text.index("**Loop:**"))
        self.assertIn("10 min since the last summary", text)

    def test_nothing_changed_is_said_in_one_line(self):
        s = self.state()
        self.assertIn("**Changed**\n- nothing\n", watch.render(s, watch.snapshot(s), self.root))

    def test_what_needs_attention_is_listed(self):
        s = self.state(turn={"toolCalls": 41, "lastOutput": NOW - 1800}, verification=None,
                       mergeQueue=["a-made-up-workspace"], asked={"n": 7, "type": "cycle"},
                       jobs={"pending": ["20260101-000002-example-901-kept"], "running": [], "finished": [],
                             "collected": {"20260101-000003-example-901-fixed": "failed"}})
        last = watch.snapshot(self.state())
        needs = watch.render(s, last, self.root).split("**Needs attention**")[1]
        for line in ("the loop is waiting for an answer to its cycle question (event 7)",
                     "the session has written nothing for 30 min", "no verification loop is running",
                     "job 20260101-000003-example-901-fixed came back failed",
                     "queued to merge at the next change of example: a-made-up-workspace"):
            self.assertIn(line, needs)
        self.assertIn("**Needs attention**\n- nothing", watch.render(self.state(), last, self.root))

    def test_an_example_waiting_on_its_proof_is_listed_with_its_jobs_out(self):
        s = self.state(items={"900": "waiting", "901": "under way"}, unfinished={"900": ["a", "b"]})
        self.assertIn("0 of 3 done · waiting on a proof: 900 (2 jobs out) · not started: 902", watch.render(s, None, self.root))

    def test_the_repositorys_template_is_the_one_used(self):
        (self.root / "llm-dlc").mkdir()
        (self.root / watch.TEMPLATE).write_text("What the page is.\n<!-- template -->\nOn {item}: {example}\n")
        self.assertEqual(watch.render(self.state(), None, self.root), "On 901: prepared: 1 no answer yet, 1 established; "
                         "1 of its verification jobs not in yet")
        shipped = (REPO / watch.TEMPLATE).read_text().split("<!-- template -->")[1].strip("\n")
        self.assertEqual(shipped, watch.DEFAULT_TEMPLATE.strip("\n"), "the page and the fallback say the same")


@cost("tool")
class StateTest(Made):
    def test_the_state_is_read_from_the_loops_events_and_the_queue(self):
        self.loop("901", "902")
        self.queue.write_text(queue(pending=["20260101-000002-example-901-kept  Example 901: kept  (2 CPU)"],
                                    collected=["20260101-000001-example-901-fixed  Example 901: fixed  [passed]"]))
        self.note("cycle-start", cycle=1, item="901", itemCycle=1, turn=str(self.tmp / "no-such-turn"))
        self.note("item", item="901", state="waiting", cycle=1)
        self.note("cycle-start", cycle=2, item="902", itemCycle=1, turn=str(self.tmp / "no-such-turn"))
        s = watch.state(self.run)
        self.assertEqual((s["items"], s["item"], s["cycle"]), ({"901": "waiting", "902": "under way"}, "902", 2))
        self.assertEqual((s["jobs"]["pending"], s["jobs"]["collected"]),
                         (["20260101-000002-example-901-kept"], {"20260101-000001-example-901-fixed": "passed"}))
        self.assertEqual(list(s["unfinished"]), ["901"])
        self.assertTrue(s["loopAlive"])
        status, out = self.call("summary")
        self.assertIn("waiting on a proof: 901 (1 jobs out)", out)
        self.assertEqual(self.run.read()["lastSummary"]["cycle"], 2)


@cost("tool")
class WaitTest(Made):
    def setUp(self):
        super().setUp()
        self.loop("901", "902")
        self.run.update(lastSummary={"time": time.time(), "items": {}, "claims": {}, "head": None, "cycle": None,
                                     "jobs": {"pending": [], "running": [], "finished": [], "collected": {}}})

    def test_a_question_of_the_loops_comes_with_how_to_answer_it_and_where_the_example_stands(self):
        self.note("cycle", needsVerdict=True, answers=["finished", "continue", "waiting"], deadline=time.time() + 300,
                  cycle=1, item="901", itemCycle=1)
        self.queue.write_text(queue(pending=["20260101-000002-example-901-kept  Example 901: kept  (2 CPU)"]))
        status, out = self.call("wait", "--timeout", 0)
        thing = json.loads(out)
        self.assertEqual((status, thing["kind"], thing["event"]["type"]), (0, "question", "cycle"))
        self.assertIn("decide llm-dlc/loop-summaries/prove-change 1 finished|continue|waiting --reason", thing["answer"])
        self.assertEqual(thing["assessment"]["jobsNotIn"], 1)

    def test_a_proof_that_has_come_in_is_announced_once(self):
        self.note("item", item="901", state="waiting", cycle=1)
        self.queue.write_text(queue(pending=["20260101-000002-example-901-kept  Example 901: kept  (2 CPU)"]))
        self.assertEqual(self.call("wait", "--timeout", 0)[0], 3, "its job is still out")
        self.queue.write_text(queue(collected=["20260101-000002-example-901-kept  Example 901: kept  [passed]"]))
        status, out = self.call("wait", "--timeout", 0)
        self.assertEqual((status, json.loads(out)["kind"], json.loads(out)["item"]), (0, "proof", "901"))
        self.assertEqual(self.call("wait", "--timeout", 0)[0], 3)

    def test_a_summary_comes_when_the_interval_has_passed(self):
        self.assertEqual(self.call("wait", "--timeout", 0)[0], 3)
        status, out = self.call("wait", "--timeout", 0, "--interval", 0)
        self.assertEqual(status, 0)
        self.assertIn("**Changed**", out)
        self.call("interval", 0)
        self.assertIn("**Changed**", self.call("wait", "--timeout", 0)[1])

    def test_the_loops_end_is_told_once(self):
        self.note("ended", status=0)
        status, out = self.call("wait", "--timeout", 0)
        self.assertEqual((status, json.loads(out)["kind"]), (0, "ended"))
        self.assertEqual(self.call("wait", "--timeout", 0)[0], 3)

    def test_proof_blocks_until_an_examples_jobs_are_in(self):
        self.queue.write_text(queue(pending=["20260101-000002-example-901-kept  Example 901: kept  (2 CPU)"]))
        status, out = self.call("proof", "901", "--timeout", 0)
        self.assertEqual((status, json.loads(out)["jobs"]), (3, "not in yet"))
        self.queue.write_text(queue())
        status, out = self.call("proof", "901", "--timeout", 5)
        self.assertEqual((status, json.loads(out)["jobs"]), (0, "in"))


@cost("tool")
class RequestsTest(Made):
    def test_stop_after_leaves_the_loop_its_command(self):
        self.call("stop-after", "example")
        self.call("stop-after", "never")
        self.assertEqual((self.run.dir / conductor.COMMANDS).read_text(), "item\ninf\n")

    @cost("tool")
    def test_a_workspace_is_queued_to_merge_only_if_it_exists_and_taken_off_when_done(self):
        subprocess.run(["jj", "--quiet", "git", "init", str(self.root)], check=True, capture_output=True,
                       env={**os.environ, "JJ_CONFIG": os.devnull, "JJ_USER": "Made Up", "JJ_EMAIL": "made@up.invalid"})
        with mock.patch.dict(os.environ, {"JJ_CONFIG": os.devnull}):
            self.assertEqual(self.call("merge", "add", "no-such-workspace")[0], 2)
            self.assertEqual(self.call("merge", "add", "default")[0], 0)
            self.assertEqual(watch.merge_queue(self.run), ["default"])
            self.assertIn("nothing", self.call("merge", "done", "default")[1])

    @cost("tool")
    def test_the_verification_loop_is_started_once_and_asked_to_end_after_the_job_under_way(self):
        subprocess.run(["jj", "--quiet", "git", "init", str(self.root)], check=True, capture_output=True,
                       env={**os.environ, "JJ_CONFIG": os.devnull, "JJ_USER": "Made Up", "JJ_EMAIL": "made@up.invalid"})
        tools = self.root / "llm-dlc/tools"
        tools.mkdir(parents=True)
        (tools / "verification-loop.sh").write_text(  # a stand-in: it runs until it is asked to stop, as the loop does
            "#!/usr/bin/env bash\ntrap 'echo asked to stop; exit 0' USR1\necho started\nwhile :; do sleep 0.1; done\n")
        (tools / "verification-loop.sh").chmod(0o755)
        self.assertIn("not running", self.call("verification", "status")[1])
        self.assertIn("started the verification loop", self.call("verification", "start")[1])
        pid = self.run.read()["verification"]["pid"]
        self.addCleanup(lambda: watch.alive(pid) and os.kill(pid, 9))
        self.assertIn(f"running (pid {pid}), started by this run", self.call("verification", "status")[1])
        self.assertIn("already running", self.call("verification", "start")[1])
        self.assertEqual(self.run.read()["verification"]["pid"], pid, "a second start leaves the first alone")
        self.assertIn("asked the verification loop", self.call("verification", "stop")[1])
        until = time.time() + 10
        while "asked to stop" not in (self.run.dir / "verification.log").read_text() and time.time() < until:
            time.sleep(0.05)
        self.assertEqual((self.run.dir / "verification.log").read_text(), "started\nasked to stop\n")

    def test_loop_starts_the_proof_loop_detached_in_the_fixed_session_and_refuses_a_second(self):
        tools = self.root / "llm-dlc/tools"
        tools.mkdir(parents=True)
        (tools / "prove-loop.sh").write_text('#!/usr/bin/env bash\necho "$@" >"$STANDIN_LOG.loop"\n')
        (tools / "prove-loop.sh").chmod(0o755)
        status, out = self.call("loop", "--memory", "12G", "902", "900")
        self.assertEqual(status, 0)
        session = self.call("session")[1].strip()
        log = Path(str(self.log) + ".loop")
        until = time.time() + 10
        while not log.exists() and time.time() < until:
            time.sleep(0.05)
        self.assertEqual(log.read_text().strip(), f"--session {session} --memory 12G 902 900")
        self.loop("902", "900")  # a run under way, as prove-loop.sh records it
        self.assertEqual(self.call("loop", "902")[0], 1)


if __name__ == "__main__":
    unittest.main()
