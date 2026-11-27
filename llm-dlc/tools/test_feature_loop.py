#!/usr/bin/env python3
"""Tests for feature-loop.sh by itself, the loop under a run: what it does when a session compacts with no commit,
how it treats its systemd scope, that it runs from a copy of its script, and what it refuses.
Run: python3 llm-dlc/tools/test_feature_loop.py
The script is run for real in a made-up jj repository, with a stand-in `claude` on PATH that plays a session: it
commits, or it compacts and waits to be told to go on. No model is called and nothing touches this repository or
~/.claude. test_single_run.py tests the same script through single_run.py, the tool that starts it."""
from __future__ import annotations

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

import conductor

TOOLS = Path(__file__).resolve().parent
sys.path.append(str(TOOLS.parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

FIRST = "Do the made-up work, and say when it is done."
CONTINUE = "Go on with the made-up work."

# The stand-in: one invocation is one turn. It appends its arguments to $STANDIN_LOG and prints stream-json.
STANDIN = r'''#!/usr/bin/env python3
import json, os, subprocess, sys, time
from pathlib import Path

args = sys.argv[1:]
prompt, mode = args[args.index("-p") + 1], os.environ.get("STANDIN_MODE", "commit")
emit = lambda event: print(json.dumps(event), flush=True)

def commit():
    Path("work.txt").write_text("done at %s\n" % time.time())
    subprocess.run(["jj", "--quiet", "describe", "-m", "Do a piece of the made-up work"], check=True)
    subprocess.run(["jj", "--quiet", "new"], check=True)

if prompt.startswith(("Do the made-up work", "Go on with the made-up work")):
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
    f.write(json.dumps({"args": args, "cwd": os.getcwd()}) + "\n")
emit({"type": "result", "subtype": "success", "result": "the stand-in's reply", "num_turns": 1, "duration_ms": 1,
      "total_cost_usd": 0})
'''


@cost("tool")
class TheLoop(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.root = self.tmp / "checkout"
        tools = self.root / "llm-dlc/tools"
        tools.mkdir(parents=True)
        for name in ("feature-loop.sh", "loop-common.sh", "conductor.py"):
            shutil.copy(TOOLS / name, tools / name)
        (self.root / ".gitignore").write_text("llm-dlc/loop-summaries/\n")
        bin = self.tmp / "bin"
        bin.mkdir()
        (bin / "claude").write_text(STANDIN)
        (bin / "claude").chmod(0o755)
        self.log, self.go = self.tmp / "standin.jsonl", self.tmp / "go"
        self.run_dir = self.root / "llm-dlc/loop-summaries/single-made-up"
        self.run_dir.mkdir(parents=True)
        (self.run_dir / "first.md").write_text(FIRST + "\n")
        (self.run_dir / "continue.md").write_text(CONTINUE + "\n")
        # Run inside a loop, the tests would otherwise inherit its run.
        mine = {k: v for k, v in os.environ.items()
                if not k.startswith(("FEATURE_LOOP_", "LOOP_WATCH_", "RUN_STREAMS_", "PROVE_LOOP_")) and k != "IN_THE_LOOP_MODE"}
        self.env = {**mine, "PATH": f"{bin}:{os.environ['PATH']}", "CLAUDE_CONFIG_DIR": str(self.tmp / "claude-config"),
                    "STANDIN_LOG": str(self.log), "STANDIN_GO": str(self.go), "XDG_RUNTIME_DIR": str(self.tmp),
                    "LOOP_CONDUCTOR": str(self.run_dir), "FEATURE_LOOP_RECORD_AS": "single-made-up",
                    "FEATURE_LOOP_FIRST": str(self.run_dir / "first.md"), "FEATURE_LOOP_CONTINUE": str(self.run_dir / "continue.md"),
                    "FEATURE_LOOP_UNCAPPED": "1", "FEATURE_LOOP_JUDGE_WAIT": "1",
                    "JJ_USER": "Made Up", "JJ_EMAIL": "made@up.invalid", "JJ_CONFIG": os.devnull}
        subprocess.run(["jj", "--quiet", "git", "init", str(self.root)], env=self.env, check=True, capture_output=True)
        subprocess.run(["jj", "--quiet", "describe", "-m", "The made-up checkout"], cwd=self.root, env=self.env, check=True)
        subprocess.run(["jj", "--quiet", "new"], cwd=self.root, env=self.env, check=True)

    def loop(self, *args, mode="commit", without=(), **env):
        kept = {k: v for k, v in self.env.items() if k not in without}
        return subprocess.run([str(self.root / "llm-dlc/tools/feature-loop.sh"), *(args or ("single-agent", "1"))], cwd=self.root,
                              env={**kept, "STANDIN_MODE": mode, **env}, capture_output=True, text=True, timeout=120)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def texts(self):
        """The texts the session's work turns were given, in order."""
        given = [c["args"][c["args"].index("-p") + 1] for c in self.calls()]
        return [t for t in given if t.startswith(("Do the", "Go on"))]

    def events(self, kind):
        return [e for e in conductor.read_events(self.run_dir) if e.get("type") == kind]

    def record(self):
        return sorted((self.root / "llm-dlc/loop-summaries").glob("*-single-made-up.md"))[-1].read_text()

    def decide_when_asked(self, verdict, reason):
        """Answer the loop's first question from another thread, as a watcher waiting on it would."""
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
    def test_a_compaction_with_no_commit_goes_on_when_the_watcher_says_so(self):
        thread = self.decide_when_asked("continue", "two test files green since the cycle began")
        r = self.loop(mode="compact")
        thread.join(5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.asked["type"], self.asked["cycle"], self.asked["tokens"]), ("compaction", "1", 600000))
        self.assertIsNone(self.asked.get("item"))
        self.assertTrue(self.asked["transcript"].endswith(".jsonl"))
        record = self.record()
        self.assertIn("- cycle 1, ", record)
        self.assertIn("  - compacted with no commit at 600000 tokens; the conductor let the turn go on: two test files "
                      "green since the cycle began", record)

    @cost("tool")
    def test_a_compaction_with_no_commit_ends_the_loop_when_the_watcher_says_stop(self):
        thread = self.decide_when_asked("stop", "the same assertion has failed five times")
        r = self.loop(mode="compact")
        thread.join(5)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("compacted with no commit at 600000 tokens, and the conductor said stop: the same assertion has "
                      "failed five times; session", self.record())
        self.assertEqual(self.calls(), [])  # the turn was ended there, and no compact or summary followed it

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
        r = self.loop(mode="compact", FEATURE_LOOP_CONDUCTOR_WAIT="1")
        thread.join(5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("  - compacted with no commit at 600000 tokens; no verdict came from the conductor in 1 s, and the "
                      "turn went on", self.record())

    @cost("tool")
    def test_without_a_verdict_in_time_the_rule_stops_the_loop_where_it_is_on(self):
        r = self.loop(mode="compact", FEATURE_LOOP_CONDUCTOR_WAIT="1", FEATURE_LOOP_STOP_ON_COMPACT="1")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("compacted with no commit at 600000 tokens, and no verdict came from the conductor in 1 s", self.record())

    @cost("tool")
    def test_a_turn_that_ends_by_itself_takes_its_question_back(self):
        self.go.write_text("go\n")  # the stand-in commits straight after it compacts: nobody answers, nobody needs to
        r = self.loop(mode="compact")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        (asked,), (withdrawn,) = self.events("compaction"), self.events("withdrawn")
        self.assertEqual((asked["needsVerdict"], withdrawn["event"]), (True, asked["n"]))
        self.assertNotIn("conductor", self.record())

    def capped(self, held: str):
        """The loop started where it must contain itself, with stand-ins for systemd: the scope of its name is
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
        return self.loop(without=("FEATURE_LOOP_UNCAPPED",), FEATURE_LOOP_MEMORY_MAX="64M",
                         FEATURE_LOOP_CGROUP_ROOT=str(self.tmp / "cgroup"))

    @cost("tool")
    def test_a_scope_holding_only_what_an_ended_loop_left_is_stopped_and_one_at_work_is_not(self):
        # A daemon the last leg left (2026-11-26: a dirmngr held a setup's scope for eight hours): stopped, and on.
        r = self.capped("exec -a 'dirmngr --daemon' sleep 60")
        self.assertIn("holds only what an ended loop left (1 process(es)): stopping it before the loop starts", r.stdout + r.stderr)
        self.assertIn("--user stop feature-loop-single-made-up.scope", (self.tmp / "systemctl.log").read_text())
        self.assertIn("--unit=feature-loop-single-made-up", (self.tmp / "systemd-run.log").read_text())
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
        cgroup = self.tmp / "cgroup-file"
        cgroup.write_text("0::/user.slice/user@1001.service/app.slice/feature-loop-single-made-up-outer.scope\n")
        r = self.loop(without=("FEATURE_LOOP_UNCAPPED", "IN_THE_LOOP_NESTED_RUN"), FEATURE_LOOP_CGROUP_FILE=str(cgroup))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("would start inside the running loop feature-loop-single-made-up-outer.scope", r.stdout + r.stderr)
        self.assertEqual(self.calls(), [])  # no client was started

    @cost("tool")
    def test_the_loop_runs_from_a_copy_of_its_script(self):
        marker = self.tmp / "ran-the-new-text"
        script = self.root / "llm-dlc/tools/feature-loop.sh"

        def rewrite():  # what a landing between two cycles may do
            until = time.time() + 60
            while time.time() < until and not self.events("cycle-start"):
                time.sleep(0.05)
            script.write_text(f"#!/usr/bin/env bash\ntouch {marker}\nexit 7\n" + script.read_text())
        thread = threading.Thread(target=rewrite, daemon=True)
        thread.start()
        r = self.loop("single-agent", "2")
        thread.join(5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.texts(), [FIRST, CONTINUE])  # the second cycle ran, on the text the run began with
        self.assertFalse(marker.exists())

    @cost("tool")
    def test_a_kind_of_loop_that_is_retired_and_a_run_without_its_caller_start_nothing(self):
        for kind in ("features", "prove-change", "llm-dlc/loops/made-up.md"):
            r = self.loop(kind)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn(f"'{kind}' is not a loop this script runs any more", r.stderr)
            self.assertIn("llm-dlc/retired.md", r.stderr)
        r = self.loop(without=("FEATURE_LOOP_FIRST",))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("single-agent takes its run from FEATURE_LOOP_FIRST; start it with llm-dlc/tools/single_run.py", r.stderr)
        self.assertEqual(self.loop("single-agent", "soon").returncode, 2)  # a count that is no count
        self.assertEqual(self.calls(), [])
        self.assertEqual(list((self.root / "llm-dlc/loop-summaries").glob("*.md")), [])  # and no record of a run


if __name__ == "__main__":
    unittest.main()
