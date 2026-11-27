#!/usr/bin/env python3
"""Tests for agent_client.py, the client boundary of a loop's turn, over a stand-in for Codex (codex_standin.py):
what a turn is started with, the stream it prints, the binding of a loop's session to Codex's thread, how each
way a turn can end is told, compaction through the app server, and the check that Codex is given this checkout's
instructions. Run: python3 llm-dlc/tools/test_agent_client.py"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import agent_client  # noqa: E402

sys.path.append(str(TOOLS.parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402

STANDIN = TOOLS / "codex_standin.py"


class Resolving(unittest.TestCase):
    """Which model a client runs for the model a brief names."""

    def test_the_operators_equivalences_give_codex_its_model_and_claude_keeps_its_own(self):
        self.assertEqual(agent_client.resolve("codex", "claude-fable-5-2"), "gpt-6.2-astra")
        self.assertEqual(agent_client.resolve("codex", "claude-opus-5-5"), "gpt-6.2-sol")
        self.assertEqual(agent_client.resolve("codex", "gpt-6.1-terra"), "gpt-6.1-terra")
        self.assertEqual(agent_client.resolve("claude", "claude-opus-5-5"), "claude-opus-5-5")

    def test_a_model_nobody_mapped_is_refused_before_a_turn_and_says_what_is_mapped(self):
        for model in ("claude-sonnet-5-5", "claude-fable-5-1"):
            with self.assertRaises(agent_client.Problem) as e:
                agent_client.resolve("codex", model)
            self.assertIn("claude-fable-5-2, claude-opus-5-5", str(e.exception))
        with self.assertRaises(agent_client.Problem):
            agent_client.resolve("claude", "gpt-6.2-sol")
        with self.assertRaises(agent_client.Problem):
            agent_client.resolve("gemini", "claude-opus-5-5")

    def test_a_plan_carries_the_effort_asked_for_and_what_the_model_stands_for(self):
        self.assertEqual(agent_client.plan("codex", "claude-opus-5-5", "high"),
                         {"client": "codex", "model": "gpt-6.2-sol", "effort": "high", "for": "claude-opus-5-5"})
        self.assertEqual(agent_client.plan("claude", "claude-opus-5-5", "low"), {"client": "claude", "model": "claude-opus-5-5", "effort": "low"})
        with self.assertRaises(agent_client.Problem):
            agent_client.plan("codex", "claude-opus-5-5", "extreme")

    def test_codex_token_counts_are_given_under_the_keys_the_loops_read(self):
        self.assertEqual(agent_client.usage_of({"input_tokens": 1000, "cached_input_tokens": 600, "cache_write_input_tokens": 5,
                                                "output_tokens": 40, "reasoning_output_tokens": 7}),
                         {"input_tokens": 400, "cache_read_input_tokens": 600, "cache_creation_input_tokens": 5,
                          "output_tokens": 40, "reasoning_output_tokens": 7})

    def test_a_turns_tokens_are_the_rise_of_the_threads_total_and_a_count_that_fell_is_the_turns(self):
        first = {"input_tokens": 1000, "cached_input_tokens": 600, "cache_write_input_tokens": 0, "output_tokens": 40, "reasoning_output_tokens": 7}
        later = {"input_tokens": 2500, "cached_input_tokens": 1900, "cache_write_input_tokens": 0, "output_tokens": 90, "reasoning_output_tokens": 7}
        self.assertEqual(agent_client.turn_tokens(first, None), (first, first))
        own, total = agent_client.turn_tokens(later, first)
        self.assertEqual((own["input_tokens"], own["cached_input_tokens"], own["output_tokens"], total), (1500, 1300, 50, later))
        self.assertEqual(agent_client.turn_tokens(first, later)[0], first)

    def test_an_event_of_codex_becomes_what_the_loops_read_and_most_become_nothing(self):
        t = agent_client.translate
        self.assertEqual(t({"type": "turn.started"}, "s"), [])
        self.assertEqual(t({"type": "item.completed", "item": {"type": "reasoning", "text": "thinking"}}, "s"), [])
        said = t({"type": "item.completed", "item": {"type": "agent_message", "text": "Done."}}, "s")
        self.assertEqual(said[0]["message"]["content"], [{"type": "text", "text": "Done."}])
        ran = t({"type": "item.started", "item": {"id": "i1", "type": "command_execution", "command": "ls"}}, "s")
        self.assertEqual((ran[0]["message"]["content"][0]["name"], ran[0]["message"]["content"][0]["input"]), ("Bash", {"command": "ls"}))
        self.assertEqual(t({"type": "item.completed", "item": {"id": "i1", "type": "command_execution", "command": "ls"}}, "s"), [])
        patched = t({"type": "item.completed", "item": {"type": "file_change", "changes": [{"path": "a.py"}, {"path": "b.py"}]}}, "s")
        self.assertEqual(patched[0]["message"]["content"][0]["input"]["file_path"], "a.py, b.py")
        # a compaction is no event of the stream (CLI 0.169 prints none): it is read from the thread's log
        self.assertEqual(t({"type": "item.completed", "item": {"type": "context_compaction"}}, "s"), [])

    def test_a_compaction_is_read_from_the_threads_log_once_and_only_if_it_is_this_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "rollout-x.jsonl"
            line = lambda stamp, size: json.dumps({"timestamp": stamp, "type": "compacted", "payload": {
                "latest_token_usage_record": {"usage": {"total_tokens": size}}}}) + "\n"
            log.write_text(line("2000-01-01T00:00:00.000Z", 1))  # an earlier turn's, already in the log
            with mock.patch.object(agent_client, "rollout_of", return_value=log):
                seen = agent_client.Compactions("made-up-thread")
                self.assertEqual(seen.new("s"), [])
                with open(log, "a") as f:
                    f.write(json.dumps({"timestamp": "2999-01-01T00:00:00.000Z", "type": "response_item",
                                        "payload": {"text": 'a tool printed "compacted"'}}) + "\n")
                    f.write(line("2999-01-01T00:00:01.000Z", 500000) + line("2999-01-01T00:00:02.000Z", 2)[:40])  # the last half written
                self.assertEqual([(e["subtype"], e["session_id"], e["compact_metadata"]) for e in seen.new("s")],
                                 [("compact_boundary", "s", {"trigger": "auto", "pre_tokens": 500000})])
                self.assertEqual(seen.new("s"), [])
                with open(log, "a") as f:
                    f.write(line("2999-01-01T00:00:02.000Z", 2)[40:])
                self.assertEqual([e["compact_metadata"]["pre_tokens"] for e in seen.new("s")], [2])
            # a thread with no log yet (a new one's first moments, or a client that keeps none here): nothing, and no error
            with mock.patch.object(agent_client, "rollout_of", return_value=None):
                self.assertEqual(agent_client.Compactions(None).new("s"), [])


class TheBriefAuthorsSettings(unittest.TestCase):
    """The brief author's run (single_run.py generate): Codex Astra at ultra effort, compacting at 600k tokens."""

    def test_ultra_is_an_effort_of_codex_alone(self):
        self.assertEqual(agent_client.plan("codex", "gpt-6.2-astra", "ultra")["effort"], "ultra")
        with self.assertRaisesRegex(agent_client.Problem, "Codex's alone"):
            agent_client.plan("claude", "claude-fable-5-2", "ultra")
        with self.assertRaisesRegex(agent_client.Problem, "not an effort"):
            agent_client.plan("codex", "gpt-6.2-astra", "mega")

    def test_a_compaction_point_is_read_as_a_person_writes_it_and_given_with_every_turn(self):
        self.assertEqual([agent_client.tokens(v) for v in ("600k", "600000", "0.6M", "1M", None, "")],
                         [600000, 600000, 600000, 1000000, None, None])
        for bad in ("lots", "600 tokens", "12"):
            with self.assertRaises(agent_client.Problem, msg=bad):
                agent_client.tokens(bad)
        cwd = Path(tempfile.gettempdir())
        first = agent_client.codex_argv("gpt-6.2-astra", "ultra", Path("last.md"), None, cwd, "auto", "x", 600000)
        resumed = agent_client.codex_argv("gpt-6.2-astra", "ultra", Path("last.md"), "thread-1", cwd, "auto", "x", 600000)
        for argv in (first, resumed):  # `exec resume` keeps no setting of the turn before
            self.assertIn("model_auto_compact_token_limit=600000", argv)
            self.assertIn('model_reasoning_effort="ultra"', argv)
        plain = agent_client.codex_argv("gpt-6.2-astra", "max", Path("last.md"), None, cwd, "auto", "x")
        self.assertEqual([x for x in plain if "auto_compact" in x], [], "without one, the machine's own setting stands")


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.cwd = self.base / "work"
        self.cwd.mkdir()
        self.log = self.base / "codex.jsonl"
        self.session = str(uuid.uuid4())
        self.env = {**{k: v for k, v in os.environ.items() if k not in agent_client.PARENT_MARKERS},
                    "AGENT_CLIENT_CODEX": str(STANDIN), "AGENT_CLIENT_STATE": str(self.base / "state"),
                    "XDG_CACHE_HOME": str(self.base / "cache"),
                    "CODEX_STANDIN_STATE": str(self.base / "codex"), "CODEX_STANDIN_LOG": str(self.log)}

    def tearDown(self):
        self.tmp.cleanup()

    def client(self, *args: str, **env) -> tuple[int, list[dict], str]:
        r = subprocess.run([sys.executable, str(TOOLS / "agent_client.py"), *args], cwd=self.cwd, env={**self.env, **env},
                           capture_output=True, text=True, timeout=60)
        return r.returncode, [json.loads(line) for line in r.stdout.splitlines() if line.startswith("{")], r.stderr

    def turn(self, prompt: str = "Do the next piece.", **env) -> tuple[int, list[dict], str]:
        return self.client("run", "--client", "codex", "--session", self.session, "--model", "claude-opus-5-5",
                           "--effort", "high", "--cwd", str(self.cwd), prompt, **env)

    def calls(self) -> list[dict]:
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def binding(self) -> dict | None:
        with mock.patch.dict(os.environ, {"AGENT_CLIENT_STATE": self.env["AGENT_CLIENT_STATE"]}):
            return agent_client.binding(self.session, self.cwd)


class ATurn(Fixture):
    @cost("tool")
    def test_the_first_turn_starts_a_thread_with_the_model_the_effort_and_the_checkouts_instructions(self):
        code, events, err = self.turn("Do the first piece.", CLAUDE_CODE_SESSION_ID="11111111-1111-4111-8111-111111111111", CLAUDECODE="1",
                                      RUN_STREAMS_WATCHER="the-watcher", LOOP_CONDUCTOR="made-up", FEATURE_LOOP_RECORD_AS="made-up",
                                      TMPDIR="/tmp")
        self.assertEqual(code, 0, err)
        argv = self.calls()[0]["argv"]
        self.assertEqual(argv[:2], ["exec", "--json"])
        self.assertNotIn("resume", argv)
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-6.2-sol")  # Sol 6.2 for the brief's Opus 5.5
        self.assertIn('model_reasoning_effort="high"', argv)  # never the machine's own default
        self.assertIn('project_doc_fallback_filenames=["CLAUDE.md"]', argv)
        # the workspace-write sandbox, and nobody is there to answer a request to leave it: Codex's own review does
        # with the network open in it, as a Claude Code worker has it (the user's word, 2026-11-19)
        for setting in ('sandbox_mode="workspace-write"', 'approval_policy="on-request"', 'approvals_reviewer="auto_review"',
                        "sandbox_workspace_write.network_access=true"):
            self.assertIn(setting, argv)
        self.assertEqual((argv[argv.index("-C") + 1], argv[-1]), (str(self.cwd), "Do the first piece."))
        # a rehearsal's own settings come after them, and a role that only reads is given neither the network nor a way out
        given = agent_client.codex_argv("gpt-6.2-sol", "low", Path("last.md"), None, self.cwd, "auto", "x")
        self.assertNotIn("model_auto_compact_token_limit=40000", given)
        with mock.patch.dict(os.environ, {"AGENT_CLIENT_CODEX_SETTINGS": "model_auto_compact_token_limit=40000\n"}):
            given = agent_client.codex_argv("gpt-6.2-sol", "low", Path("last.md"), None, self.cwd, "auto", "x")
        self.assertGreater(given.index("model_auto_compact_token_limit=40000"), given.index("sandbox_workspace_write.network_access=true"))
        reading = agent_client.codex_argv("gpt-6.2-sol", "low", Path("last.md"), None, self.cwd, "read-only", "x")
        self.assertEqual([x for x in reading if "network_access" in x or "approvals_reviewer" in x], [])
        # the stream is the one the loops read from Claude Code
        self.assertEqual([e["type"] for e in events], ["system", "assistant", "assistant", "assistant", "result"])
        self.assertEqual((events[0]["subtype"], events[0]["session_id"], events[0]["client"]), ("init", self.session, "codex"))
        self.assertEqual(events[2]["message"]["content"][0]["name"], "Bash")
        result = events[-1]
        self.assertEqual((result["subtype"], result["is_error"], result["session_id"]), ("success", False, self.session))
        self.assertIn("the stand-in's report of turn 1 (ok); it was told: Do the first piece.", result["result"])
        self.assertIsNone(result["total_cost_usd"])  # tokens are known, dollars are not
        self.assertEqual((result["usage"]["input_tokens"], result["usage"]["cache_read_input_tokens"]), (400, 600))
        # the session is bound to the thread Codex named, and the watcher that started it is kept, not passed on
        bound = self.binding()
        self.assertEqual((bound["client"], bound["thread"], bound["model"], bound["effort"], bound["attempts"]),
                         ("codex", events[0]["thread_id"], "gpt-6.2-sol", "high", 1))
        self.assertEqual(bound["parent"], {"client": "claude", "session": "11111111-1111-4111-8111-111111111111"})
        self.assertEqual(self.calls()[0]["identity"], [])
        # nor is anything of the run that started it, and its temporary files have a folder of the session's own, on disk
        self.assertEqual(self.calls()[0]["run"], [])
        self.assertEqual(self.calls()[0]["tmp"], str(self.base / "cache/in-the-loop/agent-tmp" / self.session))
        self.assertTrue(Path(self.calls()[0]["tmp"]).is_dir())
        self.assertTrue(Path(result["attempt"]).is_file())
        given = json.loads(Path(result["attempt"]).with_suffix(".given.json").read_text())
        self.assertEqual(given["prompt"], {"sha256": __import__("hashlib").sha256(b"Do the first piece.").hexdigest(), "chars": 19})

    @cost("tool")
    def test_a_later_turn_resumes_that_exact_thread_and_each_attempt_keeps_its_own_files(self):
        self.turn()
        thread = self.binding()["thread"]
        code, events, err = self.turn("Go on.")
        self.assertEqual(code, 0, err)
        argv = self.calls()[1]["argv"]
        self.assertEqual(argv[:3], ["exec", "resume", "--json"])
        self.assertEqual(argv[-2:], [thread, "Go on."])
        self.assertNotIn("-C", argv)  # a resumed thread keeps its folder
        # and not its sandbox or its approvals: a resumed turn that is not given them again is read-only
        for setting in ('sandbox_mode="workspace-write"', 'approval_policy="on-request"', 'approvals_reviewer="auto_review"'):
            self.assertIn(setting, argv)
        self.assertEqual([a for a in argv if "sandbox_mode" in a or "approv" in a],
                         [a for a in self.calls()[0]["argv"] if "sandbox_mode" in a or "approv" in a])
        self.assertEqual(self.calls()[1]["cwd"], str(self.cwd))
        self.assertIn("report of turn 2", events[-1]["result"])
        self.assertEqual((self.binding()["thread"], self.binding()["attempts"]), (thread, 2))
        # Codex reports the thread's running total when a turn ends: the turn's own tokens are the rise
        usage = events[-1]["usage"]
        self.assertEqual((usage["input_tokens"], usage["cache_read_input_tokens"], usage["output_tokens"]), (400, 600, 40))
        self.assertEqual((self.binding()["tokens"]["input_tokens"], self.binding()["tokens"]["output_tokens"]), (2000, 80))
        attempts = sorted(p.name for p in (self.base / "state" / "attempts" / self.session).glob("*.jsonl"))
        self.assertEqual([a[:4] for a in attempts], ["001-", "002-"])
        self.assertEqual(self.client("exists", "--client", "codex", "--session", self.session, "--cwd", str(self.cwd))[0], 0)
        r = subprocess.run([sys.executable, str(TOOLS / "agent_client.py"), "thread", "--session", self.session, "--cwd", str(self.cwd)],
                           env=self.env, capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, thread))  # what a loop writes into its record
        self.assertEqual(self.client("thread", "--session", str(uuid.uuid4()), "--cwd", str(self.cwd))[0], 1)
        self.assertEqual(self.client("exists", "--client", "codex", "--session", str(uuid.uuid4()), "--cwd", str(self.cwd))[0], 1)

    @cost("tool")
    def test_a_client_that_resumes_another_thread_ends_the_turn_and_changes_nothing(self):
        self.turn()
        before = self.binding()
        code, events, err = self.turn(CODEX_STANDIN_MODES="ok,mismatch")
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["subtype"], "error_mismatched_thread")
        self.assertIn(f"is bound to {before['thread']}", events[-1]["result"])
        self.assertEqual(self.binding()["thread"], before["thread"])

    @cost("tool")
    def test_a_turn_that_fails_says_what_the_client_said_and_leaves_its_attempt_to_read(self):
        code, events, err = self.turn(CODEX_STANDIN_MODES="fail")
        self.assertNotEqual(code, 0)
        result = events[-1]
        self.assertEqual((result["subtype"], result["is_error"]), ("error_during_execution", True))
        self.assertIn("usage limit", result["result"])
        self.assertIn("usage limit", err)
        self.assertIn("turn.failed", Path(result["attempt"]).read_text())
        self.assertIsNotNone(self.binding())  # the thread exists: the next turn resumes it

    @cost("tool")
    def test_a_stream_that_ends_with_no_result_is_an_error_whatever_the_exit_status(self):
        code, events, err = self.turn(CODEX_STANDIN_MODES="truncated")
        self.assertNotEqual(code, 0)
        self.assertEqual(events[-1]["subtype"], "error_no_result")
        self.assertIn("no result", err)
        self.assertEqual([e["type"] for e in events], ["system", "result"])  # the broken lines are not the stream's
        self.assertIn("not an event at all", Path(events[-1]["attempt"]).read_text())  # but they are kept

    @cost("tool")
    def test_a_turn_that_is_stopped_takes_the_client_with_it_and_says_it_was_cancelled(self):
        p = subprocess.Popen([sys.executable, str(TOOLS / "agent_client.py"), "run", "--client", "codex", "--session", self.session,
                              "--model", "claude-opus-5-5", "--effort", "high", "--cwd", str(self.cwd), "Wait."],
                             cwd=self.cwd, env={**self.env, "CODEX_STANDIN_MODES": "hang"}, stdout=subprocess.PIPE, text=True)
        self.assertEqual(json.loads(p.stdout.readline())["subtype"], "init")  # the thread is started and bound
        p.send_signal(signal.SIGTERM)
        out, _ = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 128 + signal.SIGTERM)
        self.assertEqual(json.loads(out.splitlines()[-1])["subtype"], "error_cancelled")
        time.sleep(0.2)
        self.assertEqual(subprocess.run(["pgrep", "-f", str(self.base / "codex")], capture_output=True).stdout, b"")
        self.assertIsNotNone(self.binding())

    @cost("tool")
    def test_a_thread_that_compacts_itself_in_a_turn_is_told_as_claude_codes_is(self):
        # Codex prints nothing for it: the adapter reads it from the thread's log, with the context's size
        home = str(self.base / "codex-home")
        code, events, _ = self.turn(CODEX_STANDIN_MODES="compacts", CODEX_HOME=home, AGENT_CLIENT_HOOKS="off")
        self.assertEqual(code, 0)
        boundary = [e for e in events if e.get("subtype") == "compact_boundary"]
        self.assertEqual([(b["compact_metadata"]["trigger"], b["compact_metadata"]["pre_tokens"]) for b in boundary], [("auto", 123456)])
        self.assertLess(events.index(boundary[0]), len(events) - 1)  # in the turn, before its result
        # the next turn of the thread does not tell of that one again, and tells of its own
        code, events, _ = self.turn("Go on.", CODEX_HOME=home, AGENT_CLIENT_HOOKS="off")
        self.assertEqual((code, [e for e in events if e.get("subtype") == "compact_boundary"]), (0, []))
        code, events, _ = self.turn("Go on.", CODEX_STANDIN_MODES="compacts", CODEX_HOME=home, AGENT_CLIENT_HOOKS="off")
        self.assertEqual(len([e for e in events if e.get("subtype") == "compact_boundary"]), 1)

    @cost("tool")
    def test_a_session_keeps_its_client_and_a_turn_needs_a_text_and_a_session_id(self):
        self.assertEqual(self.client("run", "--client", "claude", "--session", self.session, "--model", "claude-opus-5-5",
                                     "--effort", "high", "x")[0], 2)
        self.assertEqual(self.turn("   ")[0], 2)
        self.assertEqual(self.client("run", "--client", "codex", "--session", "not-an-id", "--model", "claude-opus-5-5",
                                     "--effort", "high", "x")[0], 2)
        code, _, err = self.client("run", "--client", "codex", "--session", self.session, "--model", "claude-sonnet-5-5",
                                   "--effort", "high", "x")
        self.assertEqual(code, 2)
        self.assertIn("no Codex model stands for claude-sonnet-5-5", err)
        self.assertEqual(self.calls(), [])


class AfterATurn(Fixture):
    """What the checkout's hooks do for a session is done by the adapter for a turn it ran: a fresh workspace is
    not a project Codex trusts, so its own hooks are not loaded there."""

    def setUp(self):
        super().setUp()
        tools = self.cwd / "llm-dlc" / "tools"
        tools.mkdir(parents=True)
        self.hooks = self.base / "hooks.jsonl"
        # sync.py's stand-in: it writes down which hook it was run as, what it was given and for which session
        (tools / "sync.py").write_text(
            "import json, os, sys\n"
            f"open({str(self.hooks)!r}, 'a').write(json.dumps({{'hook': sys.argv[1], 'payload': json.load(sys.stdin), 'cwd': os.getcwd(),\n"
            "    'thread': os.environ.get('CODEX_THREAD_ID'), 'claude': os.environ.get('CLAUDE_CODE_SESSION_ID')}) + '\\n')\n")
        self.env["CODEX_HOME"] = str(self.base / "codex-home")
        subprocess.run(["jj", "--quiet", "git", "init", str(self.cwd)], check=True, capture_output=True,
                       env={**self.env, "JJ_USER": "Made Up", "JJ_EMAIL": "made@up.invalid", "JJ_CONFIG": os.devnull})

    def ran(self) -> list[dict]:
        return [json.loads(line) for line in self.hooks.read_text().splitlines()] if self.hooks.exists() else []

    @cost("tool")
    def test_the_end_of_a_turn_runs_the_stop_hook_with_the_payload_codex_gives_one(self):
        code, events, err = self.turn(CLAUDE_CODE_SESSION_ID="11111111-1111-4111-8111-111111111111", JJ_CONFIG=os.devnull)
        self.assertEqual(code, 0, err)
        thread = self.binding()["thread"]
        (ran,) = self.ran()
        self.assertEqual((ran["hook"], ran["payload"]["hook_event_name"], ran["payload"]["session_id"], ran["thread"], ran["claude"]),
                         ("hook", "Stop", thread, thread, None))
        self.assertEqual(Path(ran["payload"]["transcript_path"]).name, f"rollout-2026-01-01T00-00-00-{thread}.jsonl")
        self.assertEqual(Path(ran["cwd"]), self.cwd)
        self.assertEqual(events[-1]["subtype"], "success")  # the hooks come before the result: the turn is over when they are
        self.assertFalse(Path(events[-1]["attempt"]).with_suffix(".hooks.log").exists())  # a hook with nothing to say leaves no file

    @cost("tool")
    def test_a_commit_made_without_sync_gets_the_commit_hook_and_a_hook_that_fails_stops_nothing(self):
        env = {"JJ_USER": "Made Up", "JJ_EMAIL": "made@up.invalid", "JJ_CONFIG": os.devnull}
        code, events, err = self.turn(CODEX_STANDIN_MODES="commit", **env)
        self.assertEqual(code, 0, err)
        self.assertEqual([(r["hook"], r["payload"]["hook_event_name"]) for r in self.ran()], [("hook-commit", "PostToolUse"), ("hook", "Stop")])
        self.assertIn("jj commit", self.ran()[0]["payload"]["tool_input"]["command"])
        self.assertEqual(self.ran()[0]["payload"]["tool_name"], "Bash")
        # a hook that fails is written beside the attempt, and the turn's result is its own
        (self.cwd / "llm-dlc/tools/sync.py").write_text("import sys\nprint('made-up failure', file=sys.stderr)\nsys.exit(3)\n")
        code, events, err = self.turn("Go on.", **env)
        self.assertEqual((code, events[-1]["subtype"]), (0, "success"))
        self.assertIn("made-up failure", Path(events[-1]["attempt"]).with_suffix(".hooks.log").read_text())
        # and with the hooks turned off, or no log of the thread to give them, nothing is run
        self.hooks.unlink()
        (self.cwd / "llm-dlc/tools/sync.py").write_text("raise SystemExit('not to be run')\n")
        self.assertEqual(self.turn("Go on.", AGENT_CLIENT_HOOKS="off", **env)[0], 0)
        self.assertFalse(Path(self.turn("Go on.", AGENT_CLIENT_HOOKS="off", **env)[1][-1]["attempt"]).with_suffix(".hooks.log").exists())


class HookFiles(unittest.TestCase):
    def test_codex_is_given_the_two_hook_commands_claude_code_is(self):
        repo = TOOLS.parent.parent
        claude = json.loads((repo / ".claude" / "settings.json").read_text())["hooks"]
        codex = json.loads((repo / ".codex" / "hooks.json").read_text())["hooks"]
        ends = lambda hooks, event: [h["command"].rsplit("sync.py", 1)[1] for group in hooks[event] for h in group["hooks"]]
        self.assertEqual((ends(codex, "Stop"), ends(codex, "PostToolUse")), (ends(claude, "Stop"), ends(claude, "PostToolUse")))
        self.assertEqual(ends(codex, "PostToolUse"), ['" hook-commit'])
        self.assertEqual([g["matcher"] for g in codex["PostToolUse"]], ["^Bash$"])  # a shell command, as Codex names the tool
        # the adapter reads a command as the hook does, so the two never disagree on what a plain commit is
        import sync
        self.assertEqual(agent_client.PLAIN_COMMIT.pattern, sync.PLAIN_COMMIT.pattern)


class Compacting(Fixture):
    @cost("tool")
    def test_a_compaction_is_asked_of_the_app_server_for_the_sessions_thread_and_waited_for(self):
        self.turn()
        thread = self.binding()["thread"]
        code, events, err = self.client("compact", "--client", "codex", "--session", self.session, "--cwd", str(self.cwd))
        self.assertEqual(code, 0, err)
        self.assertEqual(self.calls()[1]["argv"], ["app-server"])
        self.assertEqual((self.base / "codex" / "compacted").read_text().split(), [thread])
        self.assertEqual([(e["type"], e.get("subtype")) for e in events],
                         [("system", "init"), ("system", "compact_boundary"), ("result", "success")])
        self.assertEqual(events[1]["compact_metadata"]["trigger"], "manual")  # the loop asked: it is not a stuck session's
        self.assertIn("compacted", self.binding())
        # the thread goes on afterwards
        self.assertIn("report of turn 2", self.turn("Go on.")[1][-1]["result"])

    @cost("tool")
    def test_a_compaction_that_is_refused_or_has_no_thread_says_so(self):
        code, _, err = self.client("compact", "--client", "codex", "--session", self.session, "--cwd", str(self.cwd))
        self.assertEqual(code, 2)
        self.assertIn("no Codex thread", err)
        self.turn()
        code, events, err = self.client("compact", "--client", "codex", "--session", self.session, "--cwd", str(self.cwd),
                                        CODEX_STANDIN_COMPACT="fail")
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["subtype"], "error_during_execution")
        self.assertIn("not confirmed", err)


class TheInstructions(Fixture):
    """Whether Codex is given the checkout's own CLAUDE.md: rendered by the client, compared here, never printed."""

    def check(self, **env) -> tuple[int, dict]:
        code, _, _ = 0, None, None
        r = subprocess.run([sys.executable, str(TOOLS / "agent_client.py"), "instructions", "--client", "codex", "--cwd", str(self.cwd)],
                           cwd=self.cwd, env={**self.env, **env}, capture_output=True, text=True, timeout=60)
        return r.returncode, json.loads(r.stdout)

    def write_instructions(self, lines: int = 12) -> str:
        text = "\n".join(f"- A made-up rule of this checkout, number {i}, long enough to be a marker." for i in range(lines)) + "\n"
        (self.cwd / "CLAUDE.md").write_text(text)
        return text

    @cost("tool")
    def test_the_live_file_is_found_in_what_the_client_would_be_given(self):
        self.write_instructions()
        code, out = self.check()
        self.assertEqual((code, out["problems"], out["delivered"]), (0, [], {"first": True, "last": True}))
        self.assertEqual(out["sources"][0]["path"], str(self.cwd / "CLAUDE.md"))
        self.assertEqual(len(out["sources"][0]["sha256"]), 64)
        self.assertIn("RUN_STREAMS_*", out["environment"]["removed"])
        # a file of notes the instructions point at is one more source, and one they do not name is a problem
        (self.cwd / "llm-dlc").mkdir()
        (self.cwd / "llm-dlc/operating-notes.md").write_text("# Notes\n")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("llm-dlc/operating-notes.md is there and CLAUDE.md does not name it", out["problems"][0])
        with open(self.cwd / "CLAUDE.md", "a") as f:
            f.write("- Before a merge or a test run, read llm-dlc/operating-notes.md, which holds the rules of practice.\n")
        code, out = self.check()
        self.assertEqual((code, [Path(x["path"]).name for x in out["sources"]]), (0, ["CLAUDE.md", "operating-notes.md"]))
        self.assertNotIn("made-up rule", json.dumps(out))  # digests and pass or fail, never the text

    @cost("tool")
    def test_a_file_that_shadows_it_a_client_that_skips_it_and_one_too_long_are_each_a_problem(self):
        text = self.write_instructions()
        (self.cwd / "AGENTS.md").write_text("another set of instructions\n")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("AGENTS.md shadows CLAUDE.md", out["problems"][0])
        (self.cwd / "AGENTS.md").unlink()
        cut = self.base / "cut.txt"
        cut.write_text(text[: len(text) // 2])  # the client's prompt holds the start and not the end
        code, out = self.check(CODEX_STANDIN_PROMPT=str(cut))
        self.assertEqual((code, out["delivered"]), (1, {"first": True, "last": False}))
        self.assertIn("does not hold CLAUDE.md's last line", out["problems"][0])
        self.write_instructions(lines=600)
        code, out = self.check()
        self.assertIn("over Codex's budget", " ".join(out["problems"]))
        (self.cwd / "CLAUDE.md").unlink()
        self.assertEqual(self.check()[0], 1)

    @cost("tool")
    def test_each_skill_is_one_source_both_clients_reach_and_a_user_only_skill_is_so_for_both(self):
        self.write_instructions()
        for name, head in (("work", ""), ("publish", "disable-model-invocation: true\n")):
            (self.cwd / ".claude/skills" / name).mkdir(parents=True)
            (self.cwd / ".claude/skills" / name / "SKILL.md").write_text(f"---\nname: {name}\n{head}---\n\n# {name}\n")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(sorted(p.split(" has no")[0] for p in out["problems"] if "no relative link" in p), ["the skill publish", "the skill work"])
        self.assertIn("the skill publish is for the user alone to start in SKILL.md, and its agents/openai.yaml says otherwise",
                      " ".join(out["problems"]))
        (self.cwd / ".agents/skills").mkdir(parents=True)
        for name in ("work", "publish"):
            os.symlink(f"../../.claude/skills/{name}", self.cwd / ".agents/skills" / name)
        (self.cwd / ".claude/skills/publish/agents").mkdir()
        (self.cwd / ".claude/skills/publish/agents/openai.yaml").write_text("policy:\n  allow_implicit_invocation: false\n")
        code, out = self.check()
        self.assertEqual((code, out["problems"]), (0, []))
        self.assertEqual(out["skills"], {"publish": {"linked": True, "userOnly": True}, "work": {"linked": True, "userOnly": False}})
        self.assertEqual(len(out["sources"]), 3)  # the instructions and each skill, by path and digest
        # where the client's prompt lists its skills, a user-only one must not be among them
        listed = self.base / "listed.txt"
        listed.write_text((self.cwd / "CLAUDE.md").read_text() + "- work: x (file: r1/work/SKILL.md)\n- publish: y (file: r1/publish/SKILL.md)\n")
        code, out = self.check(CODEX_STANDIN_PROMPT=str(listed))
        self.assertEqual(code, 1)
        self.assertIn("the skill publish is offered to Codex's work turns", out["problems"][0])

    def test_a_skill_may_be_the_users_alone_in_codex_only_when_it_says_so(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        skill = root / ".claude/skills/run"
        (skill / "agents").mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: run\n---\n\n# run\n")
        (root / ".agents/skills").mkdir(parents=True)
        os.symlink("../../.claude/skills/run", root / ".agents/skills/run")
        (skill / "agents/openai.yaml").write_text("policy:\n  allow_implicit_invocation: false\n")
        problems: list[str] = []
        agent_client.skills(root, "", problems, [])
        self.assertIn("the two clients would differ", " ".join(problems))  # an undeclared difference is a problem
        (skill / "agents/openai.yaml").write_text("# person-only-for-codex: a watcher reloads it\npolicy:\n  allow_implicit_invocation: false\n")
        problems = []
        found = agent_client.skills(root, "- run: x (file: r1/run/SKILL.md)\n", problems, [])
        self.assertEqual(found["run"].get("codexUserOnly"), True)
        self.assertIn("the skill run is offered to Codex's work turns", " ".join(problems))  # listed: Codex would offer it
        problems = []
        agent_client.skills(root, "- other: x (file: r1/other/SKILL.md)\n", problems, [])
        self.assertEqual(problems, [])

    def test_this_checkouts_own_skills_are_linked_and_its_user_only_skills_say_so_for_codex(self):
        root = TOOLS.parents[1]
        problems: list[str] = []
        found = agent_client.skills(root, "", problems, [])
        self.assertEqual(problems, [])
        self.assertEqual(sorted(name for name, s in found.items() if s["userOnly"]), ["publish", "review-findings"])
        # The run skills are the user's alone to start in Codex (VF-045); Claude Code keeps model invocation.
        self.assertEqual(sorted(name for name, s in found.items() if s.get("codexUserOnly")), ["multi-agent-brief", "prove-java-change", "single-agent-run"])
        self.assertTrue(all(s["linked"] for s in found.values()), found)
        self.assertFalse(any((root / name).exists() for name in agent_client.SHADOWS), "an AGENTS.md would shadow CLAUDE.md for Codex")


if __name__ == "__main__":
    unittest.main()
