#!/usr/bin/env python3
"""Tests for the proof loop: prove-loop.sh, feature-loop.sh's prove-change moonshot and the conductor hand-off in
loop-common.sh, run for real in a made-up jj repository with a stand-in `claude` on PATH that records how it was
called and plays a session: it forks, compacts, commits, compacts itself without a commit, or does nothing.
Run: python3 llm-dlc/tools/test_prove_loop.py
No model is called and nothing touches this repository or ~/.claude: the scripts are copied into a temporary
directory, and CLAUDE_CONFIG_DIR points beside it."""
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

REPO = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO / "lib/tools"))
from cost_tier import cost  # noqa: E402

import conductor  # noqa: E402
import watch  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

PARENT = "0f0f0f0f-1111-4222-8333-444455556666"
INSTRUCTION = "Formally prove example 901 as elegantly and efficiently as possible"

# The stand-in: one invocation is one turn. It appends its arguments to $STANDIN_LOG and prints stream-json.
STANDIN = r'''#!/usr/bin/env python3
import json, os, re, subprocess, sys, time
from pathlib import Path

args = sys.argv[1:]
value = lambda flag: args[args.index(flag) + 1] if flag in args else None
prompt, mode = value("-p"), os.environ.get("STANDIN_MODE", "commit")
projects = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / re.sub(r"[^A-Za-z0-9]", "-", os.getcwd())
emit = lambda event: print(json.dumps(event), flush=True)
call = {"args": args, "cwd": os.getcwd()}

def commit():
    Path("proof.txt").write_text("proved at %s\n" % time.time())
    subprocess.run(["jj", "--quiet", "describe", "-m", "Prove " + prompt.split(" as ")[0].split("prove ")[-1]], check=True)
    subprocess.run(["jj", "--quiet", "new"], check=True)

if prompt.startswith("You judge"):
    # The loop's own judge: its answers come one per call from $STANDIN_JUDGE (the last one repeats).
    answers = os.environ.get("STANDIN_JUDGE", "finished").split(",")
    count = Path(os.environ["STANDIN_LOG"] + ".judged")
    n = int(count.read_text()) if count.exists() else 0
    count.write_text(str(n + 1))
    with open(os.environ["STANDIN_LOG"] + ".judge", "a") as f:
        f.write(json.dumps(call) + "\n")
    print("The stand-in judge has read the report.\nITEM: " + answers[min(n, len(answers) - 1)])
    sys.exit(0)
if "--fork-session" in args:
    call["parentVisible"] = (projects / (value("--resume") + ".jsonl")).is_file()
    projects.mkdir(parents=True, exist_ok=True)
    (projects / (value("--session-id") + ".jsonl")).write_text("{}\n")
elif prompt.startswith("Formally prove example"):
    if mode == "commit":
        commit()
    elif mode == "compact":
        emit({"type": "system", "subtype": "compact_boundary", "compact_metadata": {"trigger": "auto", "pre_tokens": 600000}})
        until = time.time() + float(os.environ.get("STANDIN_WAIT", 20))
        while time.time() < until and not Path(os.environ["STANDIN_GO"]).exists():
            time.sleep(0.1)
        if Path(os.environ["STANDIN_GO"]).exists():
            commit()
with open(os.environ["STANDIN_LOG"], "a") as f:
    f.write(json.dumps(call) + "\n")
emit({"type": "result", "subtype": "success", "result": "the stand-in's reply", "num_turns": 1, "duration_ms": 1,
      "total_cost_usd": 0})
'''


@cost("tool")
class ProveLoopTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.root = self.tmp / "checkout"
        tools = self.root / "llm-dlc/tools"
        tools.mkdir(parents=True)
        for name in ("prove-loop.sh", "feature-loop.sh", "loop-common.sh", "conductor.py"):
            shutil.copy(REPO / "llm-dlc/tools" / name, tools / name)
        (self.root / "examples/901-a-made-up-change").mkdir(parents=True)
        (self.root / "examples/901-a-made-up-change/example.json").write_text("{}\n")
        (self.root / ".gitignore").write_text("llm-dlc/loop-summaries/\n")
        # The queue, as conductor.py reads it: the jobs not in yet are the lines of a file the test writes.
        (self.root / "verification").mkdir()
        shutil.copy(REPO / "verification/layout.py", self.root / "verification/layout.py")  # where conductor.py finds a job's file
        (self.root / "verification/pipeline.py").write_text(
            "import json, os\nrows = open(os.environ['STANDIN_JOBS']).read().split('\\n') if os.path.exists(os.environ['STANDIN_JOBS']) else []\n"
            "print(json.dumps({'pending': [r for r in rows if r], 'running': [], 'finished, not collected': []}))\n")
        bin = self.tmp / "bin"
        bin.mkdir()
        (bin / "claude").write_text(STANDIN)
        (bin / "claude").chmod(0o755)
        self.config = self.tmp / "claude-config"
        (self.config / "projects/-somewhere-else").mkdir(parents=True)
        (self.config / "projects/-somewhere-else" / f"{PARENT}.jsonl").write_text("{}\n")
        self.log, self.go, self.jobs = self.tmp / "standin.jsonl", self.tmp / "go", self.tmp / "jobs"
        self.env = {**os.environ, "PATH": f"{bin}:{os.environ['PATH']}", "CLAUDE_CONFIG_DIR": str(self.config),
                    "STANDIN_LOG": str(self.log), "STANDIN_GO": str(self.go), "STANDIN_JOBS": str(self.jobs),
                    "FEATURE_LOOP_UNCAPPED": "1", "FEATURE_LOOP_JUDGE_WAIT": "1", "FEATURE_LOOP_EXAMPLE_WAIT": "1",
                    "FEATURE_LOOP_PROOF_POLL": "1",
                    "JJ_USER": "Made Up", "JJ_EMAIL": "made@up.invalid", "JJ_CONFIG": os.devnull}
        for name in ("FEATURE_LOOP_SESSION", "FEATURE_LOOP_ITEMS", "FEATURE_LOOP_MODEL", "FEATURE_LOOP_EFFORT",
                     "FEATURE_LOOP_AUTOCOMPACT", "FEATURE_LOOP_MEMORY_MAX", "FEATURE_LOOP_STOP_ON_COMPACT",
                     "FEATURE_LOOP_CONDUCTOR_WAIT", "LOOP_CONDUCTOR", "IN_THE_LOOP_MODE", "FEATURE_LOOP_ITEM_JUDGE",
                     "FEATURE_LOOP_ITEM_CYCLES", "FEATURE_LOOP_CONTINUE_WHILE_PROVING", "FEATURE_LOOP_COPY",
                     "PROVE_LOOP_COPY", "STANDIN_JUDGE", "FEATURE_LOOP_INSTRUCTION", "FEATURE_LOOP_RECORD_AS"):
            self.env.pop(name, None)
        subprocess.run(["jj", "--quiet", "git", "init", str(self.root)], env=self.env, check=True, capture_output=True)
        subprocess.run(["jj", "--quiet", "describe", "-m", "The made-up checkout"], cwd=self.root, env=self.env, check=True)
        subprocess.run(["jj", "--quiet", "new"], cwd=self.root, env=self.env, check=True)
        self.run_dir = self.root / "llm-dlc/loop-summaries/prove-change"

    def loop(self, *args, mode="commit", **env):
        return subprocess.run([str(self.root / "llm-dlc/tools/prove-loop.sh"), "--no-verification", *args],
                              env={**self.env, "STANDIN_MODE": mode, **env}, capture_output=True, text=True, timeout=120)

    def calls(self):
        """The turns of the loop's session, in order. The loop's judge is a session of its own: judged()."""
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def judged(self):
        log = Path(str(self.log) + ".judge")
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def events(self, kind):
        return [e for e in conductor.read_events(self.run_dir) if e.get("type") == kind]

    def record(self):
        return sorted((self.root / "llm-dlc/loop-summaries").glob("*-prove-change.md"))[-1].read_text()

    def decide_when_asked(self, verdict, reason):
        """Answer the loop's first question from another thread, as a conductor waiting on it would."""
        def answer():
            until = time.time() + 60
            while time.time() < until:
                event = conductor.pending(self.run_dir)
                if event is not None and event.get("needsVerdict"):
                    self.asked = event
                    conductor.cmd_decide(self.run_dir, event["n"], verdict, reason)
                    if verdict == "continue":
                        self.go.write_text("go\n")
                    return
                time.sleep(0.1)
        thread = threading.Thread(target=answer, daemon=True)
        thread.start()
        return thread

    @cost("tool")
    def test_the_session_is_forked_compacted_and_given_the_one_line_instruction(self):
        r = self.loop("--fork", PARENT, "901")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        fork, compact, cycle, after, summary = self.calls()  # the loop compacts after each cycle, as every loop
        state = json.loads((self.run_dir / "run.json").read_text())
        session = state["session"]
        self.assertEqual((state["forkedFrom"], state["examples"], state["status"]), (PARENT, ["901"], 0))
        # The fork: from the parent, into the new session, without tools, with the parent's transcript within reach.
        self.assertEqual((fork["args"][fork["args"].index("--resume") + 1], fork["args"][fork["args"].index("--session-id") + 1]),
                         (PARENT, session))
        self.assertIn("--fork-session", fork["args"])
        self.assertEqual(fork["args"][fork["args"].index("--tools") + 1], "")
        self.assertTrue(fork["parentVisible"])
        here = self.config / "projects" / str(self.root).replace("/", "-").replace(".", "-").replace("_", "-")
        self.assertFalse((here / f"{PARENT}.jsonl").exists())  # the copy is gone, and the parent's own file is not
        self.assertTrue((self.config / "projects/-somewhere-else" / f"{PARENT}.jsonl").exists())
        # Then the compact, then the instruction and nothing else, each in the fork, on Fable 5.2 at high effort.
        self.assertTrue(compact["args"][compact["args"].index("-p") + 1].startswith("/compact "))
        self.assertEqual(cycle["args"][cycle["args"].index("-p") + 1], INSTRUCTION)
        for call in (compact, cycle, after, summary):
            self.assertEqual(call["args"][call["args"].index("--resume") + 1], session)
            self.assertEqual((call["args"][call["args"].index("--model") + 1], call["args"][call["args"].index("--effort") + 1]),
                             ("claude-fable-5-2", "high"))
            self.assertEqual(call["cwd"], str(self.root))
        self.assertEqual(cycle["args"][cycle["args"].index("--autocompact") + 1], "600k")
        self.assertIn("- cycle 1, item 901, ", self.record())
        self.assertEqual(conductor.read_events(self.run_dir)[-1]["type"], "ended")

    @cost("tool")
    def test_without_a_fork_the_loop_starts_a_session_of_its_own(self):
        r = self.loop("901")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cycle = self.calls()[0]
        self.assertEqual(cycle["args"][cycle["args"].index("-p") + 1], INSTRUCTION)
        self.assertIn("--session-id", cycle["args"])  # a new session, made by its first turn
        self.assertIsNone(json.loads((self.run_dir / "run.json").read_text())["forkedFrom"])

    @cost("tool")
    def test_a_compaction_with_no_commit_goes_on_when_the_conductor_says_so(self):
        thread = self.decide_when_asked("continue", "two test files green since the cycle began")
        r = self.loop("901", mode="compact")
        thread.join(5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.asked["cycle"], self.asked["item"], self.asked["tokens"]), ("1", "901", 600000))
        self.assertTrue(self.asked["transcript"].endswith(".jsonl"))
        record = self.record()
        self.assertIn("- cycle 1, item 901, ", record)
        self.assertIn("  - compacted with no commit at 600000 tokens; the conductor let the turn go on: two test files "
                      "green since the cycle began", record)

    @cost("tool")
    def test_a_compaction_with_no_commit_ends_the_loop_when_the_conductor_says_stop(self):
        thread = self.decide_when_asked("stop", "the same assertion has failed five times")
        r = self.loop("901", mode="compact")
        thread.join(5)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("compacted with no commit at 600000 tokens, and the conductor said stop: the same assertion has "
                      "failed five times; session", self.record())
        ended = conductor.read_events(self.run_dir)[-1]
        self.assertEqual((ended["type"], ended["status"]), ("ended", 1))

    @cost("tool")
    def test_without_a_verdict_in_time_the_turn_goes_on(self):
        def later():  # the stand-in commits once the question's deadline is behind it
            until = time.time() + 60
            while time.time() < until:
                asked = [e for e in conductor.read_events(self.run_dir) if e.get("needsVerdict")]
                if asked and time.time() > asked[0]["deadline"] + 1.5:
                    self.go.write_text("go\n")
                    return
                time.sleep(0.1)
        thread = threading.Thread(target=later, daemon=True)
        thread.start()
        r = self.loop("901", mode="compact", FEATURE_LOOP_CONDUCTOR_WAIT="1")
        thread.join(5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("  - compacted with no commit at 600000 tokens; no verdict came from the conductor in 1 s, and the "
                      "turn went on", self.record())

    @cost("tool")
    def test_without_a_verdict_in_time_the_rule_stops_the_loop_where_it_is_on(self):
        r = self.loop("901", mode="compact", FEATURE_LOOP_CONDUCTOR_WAIT="1", FEATURE_LOOP_STOP_ON_COMPACT="1")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("compacted with no commit at 600000 tokens, and no verdict came from the conductor in 1 s", self.record())

    def moonshot(self, **env):
        """feature-loop.sh by itself: no conductor."""
        return subprocess.run([str(self.root / "llm-dlc/tools/feature-loop.sh"), "prove-change"], cwd=self.root,
                              env={**self.env, "FEATURE_LOOP_ITEMS": "901", "STANDIN_MODE": "compact", "STANDIN_WAIT": "1", **env},
                              capture_output=True, text=True, timeout=120)

    @cost("tool")
    def test_with_no_conductor_a_compaction_with_no_commit_is_only_logged(self):
        r = self.moonshot()
        self.assertIn("compacted (auto) at 600000 tokens", r.stdout)
        record = self.record()
        self.assertIn("cycle 1 (item 901) made no commit", record)  # the turn ran to its own end, a second later
        self.assertNotIn("compacted with no commit", record)

    @cost("tool")
    def test_with_no_conductor_the_rule_stops_the_loop_only_where_it_is_on(self):
        r = self.moonshot(FEATURE_LOOP_STOP_ON_COMPACT="1", STANDIN_WAIT="20")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("cycle 1 (item 901) compacted with no commit at 600000 tokens; session", self.record())

    @cost("tool")
    def test_a_turn_that_ends_by_itself_takes_its_question_back(self):
        self.go.write_text("go\n")  # the stand-in commits straight after it compacts: nobody answers, nobody needs to
        r = self.loop("901", mode="compact")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        (asked,), (withdrawn,), (ended,) = self.events("compaction"), self.events("withdrawn"), self.events("ended")
        self.assertEqual((asked["needsVerdict"], withdrawn["type"], withdrawn["event"], ended["status"]),
                         (True, "withdrawn", asked["n"], 0))
        self.assertNotIn("conductor", self.record())

    @cost("tool")
    def test_a_cycle_that_makes_no_commit_stops_the_loop(self):
        r = self.loop("901", mode="nothing")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("cycle 1 (item 901) made no commit", self.record())

    def more_examples(self, *numbers):
        for number in numbers:
            (self.root / f"examples/{number}-another-made-up-change").mkdir()
            (self.root / f"examples/{number}-another-made-up-change/example.json").write_text("{}\n")

    def instructions(self):
        prompts = [call["args"][call["args"].index("-p") + 1] for call in self.calls()]
        return [p for p in prompts if p.startswith("Formally prove example")]

    @cost("tool")
    def test_several_examples_are_proved_one_per_cycle_in_the_order_given_in_one_session(self):
        self.more_examples("900", "902")
        r = self.loop("902", "900", "901")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.instructions(), [INSTRUCTION.replace("901", n) for n in ("902", "900", "901")])
        state = json.loads((self.run_dir / "run.json").read_text())
        self.assertEqual((state["examples"], state["status"]), (["902", "900", "901"], 0))
        sessions = {call["args"][call["args"].index(flag) + 1] for call in self.calls()
                    for flag in ("--resume", "--session-id") if flag in call["args"]}
        self.assertEqual(sessions, {state["session"]})
        record = self.record()
        self.assertLess(record.index("cycle 1, item 902"), record.index("cycle 2, item 900"))
        self.assertIn("cycle 3, item 901", record)

    @cost("tool")
    def test_a_cycle_with_no_commit_leaves_the_examples_after_it_untouched(self):
        self.more_examples("902")
        r = self.loop("901", "902", mode="nothing")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(self.instructions(), [INSTRUCTION])
        self.assertEqual(conductor.read_events(self.run_dir)[-1]["status"], 1)

    def runtime(self):
        """Make the made-up checkout one that can start clean sessions, and return the environment of a runtime one."""
        for name in ("mode.py", "claude_setup.py"):
            shutil.copy(REPO / "llm-dlc/tools" / name, self.root / "llm-dlc/tools" / name)
        return {"IN_THE_LOOP_MODE": "runtime"}

    @cost("tool")
    def test_in_a_runtime_checkout_every_session_of_the_loop_starts_clean(self):
        r = self.loop("--fork", PARENT, "901", **self.runtime())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self.calls()
        self.assertEqual(len(calls), 5)  # fork, compact, cycle, the compact after it, summary
        for call in calls:
            self.assertEqual(call["args"][call["args"].index("--setting-sources") + 1], "project,local", call["args"])
            self.assertEqual(call["args"].count("--setting-sources"), 1)
            self.assertIn("--strict-mcp-config", call["args"])
            excluded = json.loads(call["args"][call["args"].index("--settings") + 1])["claudeMdExcludes"]
            self.assertIn(str(self.config / "CLAUDE.md"), excluded)
        self.assertIn("sessions start clean", r.stdout)

    @cost("tool")
    def test_no_isolation_and_a_development_checkout_start_the_sessions_as_a_plain_claude(self):
        for args, env in ((["--no-isolation"], self.runtime()), ([], {})):
            self.log.unlink(missing_ok=True)
            r = self.loop(*args, "--fork", PARENT, "901", **env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            fork, *others = self.calls()
            self.assertEqual(fork["args"][fork["args"].index("--setting-sources") + 1], "user")
            for call in others:
                self.assertNotIn("--setting-sources", call["args"])
                self.assertNotIn("--strict-mcp-config", call["args"])

    def answer(self, *verdicts):
        """Answer the loop's questions of the kinds named, in turn, from another thread, as a watcher would:
        ("cycle", "continue", "why"), ... Each is answered as it is asked; later questions of a kind get none."""
        todo = list(verdicts)
        self.answered = []

        def run():
            until = time.time() + 90
            while todo and time.time() < until:
                event = conductor.pending(self.run_dir)
                if event is not None and event.get("needsVerdict") and event["type"] == todo[0][0]:
                    kind, verdict, reason = todo.pop(0)
                    conductor.cmd_decide(self.run_dir, event["n"], verdict, reason)
                    self.answered.append(event)
                time.sleep(0.05)
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    @cost("tool")
    def test_the_watcher_is_asked_after_each_cycle_and_its_verdict_keeps_or_ends_the_example(self):
        thread = self.answer(("cycle", "continue", "one claim still has no answer"), ("cycle", "finished", "every claim has its answer"))
        r = self.loop("901", FEATURE_LOOP_JUDGE_WAIT="30")
        thread.join(5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.instructions(), [INSTRUCTION, INSTRUCTION])
        first, second = self.answered
        self.assertEqual((first["item"], first["itemCycle"], second["itemCycle"], first["answers"]),
                         ("901", 1, 2, ["finished", "continue", "waiting"]))
        record = self.record()
        self.assertIn("  - item 901 continues: the conductor: one claim still has no answer", record)
        self.assertIn("  - item 901 finished: the conductor: every claim has its answer", record)
        self.assertEqual(self.judged(), [], "the watcher answered, so the loop's own judge was not asked")
        self.assertEqual([e["state"] for e in self.events("item")], ["continue", "finished"])

    @cost("tool")
    def test_without_a_watchers_verdict_the_loops_own_judge_answers(self):
        r = self.loop("901", STANDIN_JUDGE="continue,finished")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.instructions(), [INSTRUCTION, INSTRUCTION])
        judge = self.judged()[0]["args"]
        self.assertIn("ITEM: finished, ITEM: continue or ITEM: waiting", judge[judge.index("-p") + 1])
        self.assertEqual((judge[judge.index("--model") + 1], judge[judge.index("--setting-sources") + 1]),
                         ("claude-sonnet-5-5", "user"))
        self.assertIn("  - item 901 continues: The stand-in judge has read the report.", self.record())

    @cost("tool")
    def test_an_example_that_waits_on_its_proof_lets_the_next_one_start_and_is_taken_up_again_when_it_is_in(self):
        self.more_examples("902", "903")
        self.jobs.write_text("20260101-000000-example-901-the-final-proof  Example 901: the final proof\n")

        def proof_comes_in():  # while 902 is under way
            until = time.time() + 60
            while time.time() < until and len(self.instructions()) < 2:
                time.sleep(0.05)
            self.jobs.write_text("")
        thread = threading.Thread(target=proof_comes_in, daemon=True)
        thread.start()
        r = self.loop("901", "902", "903", STANDIN_JUDGE="waiting,finished")
        thread.join(5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.instructions(), [INSTRUCTION.replace("901", n) for n in ("901", "902", "901", "903")])
        record = self.record()
        for line in ("  - item 901 waiting: ", "  - item 901 taken up again: its verification jobs are in",
                     "- cycle 3, item 901, ", "- cycle 4, item 903, "):
            self.assertIn(line, record)
        self.assertEqual([(e["item"], e["state"]) for e in self.events("item")],
                         [("901", "waiting"), ("902", "finished"), ("901", "resumed"), ("901", "finished"), ("903", "finished")])
        # The watcher's tool reads the same run: what the loop wrote is what its summary is made from.
        with mock.patch.dict(os.environ, {"STANDIN_JOBS": str(self.jobs), "JJ_CONFIG": os.devnull}):
            state = watch.state(watch.Run(self.root))
        self.assertEqual((state["examples"], state["items"], state["item"], state["cycle"], state["ended"]["status"]),
                         (["901", "902", "903"], {"901": "finished", "902": "finished", "903": "finished"}, None, 4, 0))
        summary = watch.render(state, None, self.root)
        self.assertIn("**Examples:** 3 of 3 done (901 902 903)", summary)
        self.assertIn("the loop has ended (status 0)", summary)

    @cost("tool")
    def test_when_only_waiting_examples_are_left_the_loop_waits_for_the_first_proof(self):
        self.jobs.write_text("20260101-000000-example-901-the-final-proof  Example 901: the final proof\n")

        def proof_comes_in():
            until = time.time() + 60
            while time.time() < until and not self.events("proofs"):
                time.sleep(0.05)
            time.sleep(1.5)
            self.jobs.write_text("")
        thread = threading.Thread(target=proof_comes_in, daemon=True)
        thread.start()
        r = self.loop("901", STANDIN_JUDGE="waiting,finished")
        thread.join(5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.instructions(), [INSTRUCTION, INSTRUCTION])
        self.assertIn("the items left only wait on verification jobs (901)", r.stdout)
        self.assertEqual(self.events("proofs")[0]["waiting"], "901")

    @cost("tool")
    def test_waiting_with_no_job_left_to_wait_for_is_another_cycle(self):
        r = self.loop("901", STANDIN_JUDGE="waiting,finished")  # the queue is empty
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.instructions(), [INSTRUCTION, INSTRUCTION])
        self.assertIn("its verification jobs are in already", self.record())

    @cost("tool")
    def test_wait_for_proofs_keeps_the_loop_on_the_example(self):
        self.more_examples("902")
        self.jobs.write_text("20260101-000000-example-901-the-final-proof  Example 901: the final proof\n")
        thread = self.answer(("cycle", "continue", "its proof is still running"), ("cycle", "finished", "done"))
        r = self.loop("--wait-for-proofs", "--cycles", "2", "901", "902", FEATURE_LOOP_JUDGE_WAIT="30", STANDIN_JUDGE="waiting")
        thread.join(5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.instructions(), [INSTRUCTION, INSTRUCTION])
        self.assertEqual(self.answered[0]["answers"], ["finished", "continue"], "waiting is not an answer here")

    @cost("tool")
    def test_between_two_examples_the_watcher_may_stop_the_loop(self):
        self.more_examples("902")
        thread = self.answer(("example", "stop", "the user asked to stop after this example"))
        r = self.loop("901", "902", FEATURE_LOOP_EXAMPLE_WAIT="30")
        thread.join(5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.instructions(), [INSTRUCTION])
        asked = self.answered[0]
        self.assertEqual((asked["item"], asked["left"], asked["answers"]), ("901", "finished", ["continue", "stop"]))
        record = self.record()
        self.assertIn("  - the conductor stops the loop after item 901: the user asked to stop after this example", record)
        self.assertIn("stopped once item 901 was finished, as asked", record)

    @cost("tool")
    def test_between_two_examples_the_loop_waits_longer_while_a_workspace_is_queued_to_merge(self):
        self.more_examples("902")
        self.run_dir.mkdir(parents=True)
        (self.run_dir / "merge-queue").write_text("a-made-up-workspace\n")
        thread = self.answer(("example", "continue", "merged a-made-up-workspace"))
        r = self.loop("901", "902", FEATURE_LOOP_MERGE_WAIT="30")  # FEATURE_LOOP_EXAMPLE_WAIT is 1 s here
        thread.join(5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self.instructions()), 2)
        self.assertIn("with a workspace queued to merge: waiting up to 30s", r.stdout)
        self.assertIn("  - between items, the conductor: merged a-made-up-workspace", self.record())
        self.assertEqual(len(self.events("example")), 1, "nothing is asked after the last example")

    @cost("tool")
    def test_a_command_left_for_the_loop_is_applied_as_if_typed(self):
        self.more_examples("902")
        self.run_dir.mkdir(parents=True)

        def leave():  # once the loop has cleared the last run's state and started
            until = time.time() + 60
            while time.time() < until and not self.events("cycle-start"):
                time.sleep(0.05)
            conductor.cmd_command(self.run_dir, "item")
        thread = threading.Thread(target=leave, daemon=True)
        thread.start()
        r = self.loop("901", "902")
        thread.join(5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.instructions(), [INSTRUCTION])
        self.assertIn("stopped once item 901 was finished, as asked", self.record())

    @cost("tool")
    def test_an_example_added_while_the_loop_runs_is_taken_after_the_ones_it_has(self):
        # watch.py add: an example a setup prepared in its own workspace while the loop proved, merged since
        self.more_examples("902")
        self.run_dir.mkdir(parents=True)

        def leave():
            until = time.time() + 60
            while time.time() < until and not self.events("cycle-start"):
                time.sleep(0.05)
            conductor.cmd_command(self.run_dir, "add 902 901")
        thread = threading.Thread(target=leave, daemon=True)
        thread.start()
        r = self.loop("901")
        thread.join(5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.instructions(), [INSTRUCTION, INSTRUCTION.replace("901", "902")])
        self.assertIn("item 901: the loop has it already", r.stdout + r.stderr)
        self.assertIn("  - item 902 added to the list", self.record())

    @cost("tool")
    def test_session_continues_the_session_that_evaluated_the_changes(self):
        fixed = "1a1a1a1a-2222-4333-8444-555566667777"
        here = self.config / "projects" / str(self.root).replace("/", "-").replace(".", "-").replace("_", "-")
        here.mkdir(parents=True)
        (here / f"{fixed}.jsonl").write_text("{}\n")
        r = self.loop("--session", fixed, "901")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self.calls()
        self.assertFalse(any("--fork-session" in c["args"] for c in calls))
        for call in calls:
            self.assertEqual(call["args"][call["args"].index("--resume") + 1], fixed)
        state = json.loads((self.run_dir / "run.json").read_text())
        self.assertEqual((state["session"], state["forkedFrom"]), (fixed, None))
        both = self.loop("--session", fixed, "--fork", PARENT, "901")
        self.assertEqual(both.returncode, 2)

    @cost("tool")
    def test_the_loops_text_may_be_the_users_with_the_examples_number_in_it(self):
        self.more_examples("902")
        text = "Formally prove example {} and say which lemma carried the proof"
        r = self.loop("--instruction", text, "901", "902")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.instructions(), [text.replace("{}", n) for n in ("901", "902")])
        self.assertIn("> " + text, self.record(), "the record keeps the text, which the statistics read")
        self.assertEqual(json.loads((self.run_dir / "run.json").read_text())["instruction"], text)

    @cost("tool")
    def test_a_run_may_be_filed_under_another_loops_name_whose_list_it_continues(self):
        summaries = self.root / "llm-dlc/loop-summaries"
        summaries.mkdir(parents=True, exist_ok=True)
        (summaries / "2026-01-01-000000-prove-examples.md").write_text(
            "# Feature loop: prove-examples\n\n## Commits\n\n- cycle 1, item 901, 2026-01-01 01:00:00, `abc`: done\n")
        r = self.loop("--record-as", "prove-examples", "901")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.instructions(), [INSTRUCTION],
                         "an example the request names is taken, whatever that loop's earlier records say of it")
        records = sorted(p.name for p in summaries.glob("*.md"))
        self.assertEqual([n.split("-", 4)[-1] for n in records], ["prove-examples.md", "prove-examples.md"], records)
        self.assertIn("# Feature loop: prove-examples", (summaries / records[-1]).read_text())
        state = json.loads((self.run_dir / "run.json").read_text())
        self.assertEqual(state["recordAs"], "prove-examples")
        self.assertTrue(conductor.read_events(self.run_dir)[-1]["record"].endswith("-prove-examples.md"), "the run's own state stays in prove-change/")
        self.assertEqual(self.loop("--record-as", "Not A Name", "901").returncode, 2)

    @cost("tool")
    def test_a_text_that_does_not_name_the_example_starts_nothing(self):
        r = self.loop("--instruction", "Prove the example as elegantly as possible", "901")
        self.assertEqual(r.returncode, 2)
        self.assertIn("{}", r.stderr)
        self.assertEqual(self.calls(), [])

    def capped(self, held: str):
        """feature-loop.sh with its memory cap, against stand-ins for systemctl and systemd-run: the loop's scope is
        active, and holds one process running `held`. systemd-run records what it was given and exits."""
        bin, cgroup = self.tmp / "bin", self.tmp / "cgroup" / "scope"
        cgroup.mkdir(parents=True, exist_ok=True)
        (bin / "systemctl").write_text(textwrap.dedent(f"""\
            #!/usr/bin/env bash
            echo "$*" >>{self.tmp}/systemctl.log
            case "$2" in
              is-active) [[ ! -e {self.tmp}/stopped ]] ;;
              show) echo /scope ;;
              stop) touch {self.tmp}/stopped ;;
            esac
        """))
        (bin / "systemd-run").write_text(f"#!/usr/bin/env bash\necho \"$*\" >{self.tmp}/systemd-run.log\n")
        for name in ("systemctl", "systemd-run"):
            (bin / name).chmod(0o755)
        left = subprocess.Popen(["bash", "-c", held], cwd=self.tmp)
        self.addCleanup(lambda: (left.kill(), left.wait()))
        (cgroup / "cgroup.procs").write_text(f"{left.pid}\n")
        env = {k: v for k, v in self.env.items() if k != "FEATURE_LOOP_UNCAPPED"}
        return subprocess.run([str(self.root / "llm-dlc/tools/feature-loop.sh"), "prove-change"], cwd=self.root,
                              env={**env, "FEATURE_LOOP_ITEMS": "901", "FEATURE_LOOP_MEMORY_MAX": "64M",
                                   "FEATURE_LOOP_CGROUP_ROOT": str(self.tmp / "cgroup")},
                              capture_output=True, text=True, timeout=60)

    @cost("tool")
    def test_a_scope_holding_only_what_an_ended_loop_left_is_stopped_and_one_at_work_is_not(self):
        # A daemon the last leg left (2026-11-26: a dirmngr held a setup's scope for eight hours): stopped, and on.
        r = self.capped("exec -a 'dirmngr --daemon' sleep 60")
        self.assertIn("holds only what an ended loop left (1 process(es)): stopping it before the loop starts", r.stdout + r.stderr)
        self.assertIn("--user stop feature-loop-prove-change.scope", (self.tmp / "systemctl.log").read_text())
        self.assertIn("--unit=feature-loop-prove-change", (self.tmp / "systemd-run.log").read_text())
        # A loop at work (it runs from a private copy, feature-loop.XXXXXX): refused, and the scope is left alone.
        (self.tmp / "stopped").unlink()
        (self.tmp / "systemd-run.log").unlink()
        r = self.capped("exec -a 'bash /made/up/feature-loop.Ab12Cd single-agent' sleep 60")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("is a loop or an agent at work", r.stdout + r.stderr)
        self.assertFalse((self.tmp / "stopped").exists())
        self.assertFalse((self.tmp / "systemd-run.log").exists())

    @cost("tool")
    def test_a_loop_started_inside_another_loops_scope_is_refused(self):
        cgroup = self.tmp / "cgroup"
        cgroup.write_text("0::/user.slice/user@1001.service/app.slice/feature-loop-single-made-up-outer.scope\n")
        env = {k: v for k, v in self.env.items() if k not in ("FEATURE_LOOP_UNCAPPED", "IN_THE_LOOP_NESTED_RUN")}
        r = subprocess.run([str(self.root / "llm-dlc/tools/feature-loop.sh"), "prove-change"], cwd=self.root,
                           env={**env, "FEATURE_LOOP_ITEMS": "901", "FEATURE_LOOP_CGROUP_FILE": str(cgroup)},
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("would start inside the running loop feature-loop-single-made-up-outer.scope", r.stdout + r.stderr)
        self.assertEqual(self.calls(), [])  # no client was started

    @cost("tool")
    def test_the_loop_runs_from_a_copy_of_its_scripts(self):
        marker = self.tmp / "ran-the-new-text"
        script = self.root / "llm-dlc/tools/feature-loop.sh"

        def rewrite():  # what a merge between two examples may do
            until = time.time() + 60
            while time.time() < until and not self.events("cycle-start"):
                time.sleep(0.05)
            script.write_text(f"#!/usr/bin/env bash\ntouch {marker}\nexit 7\n" + script.read_text())
        thread = threading.Thread(target=rewrite, daemon=True)
        thread.start()
        self.more_examples("902")
        r = self.loop("901", "902")
        thread.join(5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self.instructions()), 2)
        self.assertFalse(marker.exists())

    @cost("tool")
    def test_an_example_that_is_not_there_starts_nothing(self):
        r = self.loop("902")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no example 902", r.stderr)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
