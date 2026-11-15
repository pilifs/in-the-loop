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
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO / "lib/tools"))
from cost_tier import cost  # noqa: E402

import conductor  # noqa: E402
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
    subprocess.run(["jj", "--quiet", "describe", "-m", "Prove example 901"], check=True)
    subprocess.run(["jj", "--quiet", "new"], check=True)

if "--fork-session" in args:
    call["parentVisible"] = (projects / (value("--resume") + ".jsonl")).is_file()
    projects.mkdir(parents=True, exist_ok=True)
    (projects / (value("--session-id") + ".jsonl")).write_text("{}\n")
elif prompt.startswith("Formally prove example"):
    if mode == "commit":
        commit()
    elif mode == "compact":
        emit({"type": "system", "subtype": "compact_boundary", "compact_metadata": {"trigger": "auto", "pre_tokens": 600000}})
        until = time.time() + 20
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
        bin = self.tmp / "bin"
        bin.mkdir()
        (bin / "claude").write_text(STANDIN)
        (bin / "claude").chmod(0o755)
        self.config = self.tmp / "claude-config"
        (self.config / "projects/-somewhere-else").mkdir(parents=True)
        (self.config / "projects/-somewhere-else" / f"{PARENT}.jsonl").write_text("{}\n")
        self.log, self.go = self.tmp / "standin.jsonl", self.tmp / "go"
        self.env = {**os.environ, "PATH": f"{bin}:{os.environ['PATH']}", "CLAUDE_CONFIG_DIR": str(self.config),
                    "STANDIN_LOG": str(self.log), "STANDIN_GO": str(self.go), "FEATURE_LOOP_UNCAPPED": "1",
                    "JJ_USER": "Made Up", "JJ_EMAIL": "made@up.invalid", "JJ_CONFIG": os.devnull}
        for name in ("FEATURE_LOOP_SESSION", "FEATURE_LOOP_ITEMS", "FEATURE_LOOP_MODEL", "FEATURE_LOOP_EFFORT",
                     "FEATURE_LOOP_AUTOCOMPACT", "FEATURE_LOOP_MEMORY_MAX", "LOOP_CONDUCTOR", "IN_THE_LOOP_MODE"):
            self.env.pop(name, None)
        subprocess.run(["jj", "--quiet", "git", "init", str(self.root)], env=self.env, check=True, capture_output=True)
        subprocess.run(["jj", "--quiet", "describe", "-m", "The made-up checkout"], cwd=self.root, env=self.env, check=True)
        subprocess.run(["jj", "--quiet", "new"], cwd=self.root, env=self.env, check=True)
        self.run_dir = self.root / "llm-dlc/loop-summaries/prove-change"

    def loop(self, *args, mode="commit", **env):
        return subprocess.run([str(self.root / "llm-dlc/tools/prove-loop.sh"), "--no-verification", *args],
                              env={**self.env, "STANDIN_MODE": mode, **env}, capture_output=True, text=True, timeout=120)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

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
    def test_without_a_verdict_in_time_the_rule_stops_the_loop(self):
        r = self.loop("901", mode="compact", FEATURE_LOOP_CONDUCTOR_WAIT="1")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("compacted with no commit at 600000 tokens, and no verdict came from the conductor in 1 s", self.record())

    @cost("tool")
    def test_a_turn_that_ends_by_itself_takes_its_question_back(self):
        self.go.write_text("go\n")  # the stand-in commits straight after it compacts: nobody answers, nobody needs to
        r = self.loop("901", mode="compact")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        asked, withdrawn, ended = conductor.read_events(self.run_dir)
        self.assertEqual((asked["needsVerdict"], withdrawn["type"], withdrawn["event"], ended["status"]),
                         (True, "withdrawn", asked["n"], 0))
        self.assertNotIn("conductor", self.record())

    @cost("tool")
    def test_a_cycle_that_makes_no_commit_stops_the_loop(self):
        r = self.loop("901", mode="nothing")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("cycle 1 (item 901) made no commit", self.record())

    @cost("tool")
    def test_an_example_that_is_not_there_starts_nothing(self):
        r = self.loop("902")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no example 902", r.stderr)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
