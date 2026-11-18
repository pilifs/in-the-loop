#!/usr/bin/env python3
"""Tests for agent_client.py, the client boundary of a loop's turn, over a stand-in for Codex (codex_standin.py):
what a turn is started with, the stream it prints, the binding of a loop's session to Codex's thread, how each
way a turn can end is told, compaction through the app server, and the check that Codex is given this checkout's
instructions. Run: python3 llm-dlc/tools/test_agent_client.py"""
from __future__ import annotations

import json
import os
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
        compacted = t({"type": "item.completed", "item": {"type": "context_compaction"}}, "s")
        self.assertEqual((compacted[0]["subtype"], compacted[0]["compact_metadata"]["trigger"]), ("compact_boundary", "auto"))


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
        code, events, err = self.turn("Do the first piece.", CLAUDE_CODE_SESSION_ID="11111111-1111-4111-8111-111111111111", CLAUDECODE="1")
        self.assertEqual(code, 0, err)
        argv = self.calls()[0]["argv"]
        self.assertEqual(argv[:2], ["exec", "--json"])
        self.assertNotIn("resume", argv)
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-6.2-sol")  # Sol 6.2 for the brief's Opus 5.5
        self.assertIn('model_reasoning_effort="high"', argv)  # never the machine's own default
        self.assertIn('project_doc_fallback_filenames=["CLAUDE.md"]', argv)
        # the workspace-write sandbox, and nobody is there to answer a request to leave it: Codex's own review does
        for setting in ('sandbox_mode="workspace-write"', 'approval_policy="on-request"', 'approvals_reviewer="auto_review"'):
            self.assertIn(setting, argv)
        self.assertEqual((argv[argv.index("-C") + 1], argv[-1]), (str(self.cwd), "Do the first piece."))
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
        attempts = sorted(p.name for p in (self.base / "state" / "attempts" / self.session).glob("*.jsonl"))
        self.assertEqual([a[:4] for a in attempts], ["001-", "002-"])
        self.assertEqual(self.client("exists", "--client", "codex", "--session", self.session, "--cwd", str(self.cwd))[0], 0)
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
        code, events, _ = self.turn(CODEX_STANDIN_MODES="compacts")
        self.assertEqual(code, 0)
        boundary = [e for e in events if e.get("subtype") == "compact_boundary"]
        self.assertEqual([b["compact_metadata"]["trigger"] for b in boundary], ["auto"])

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

    def test_this_checkouts_own_skills_are_linked_and_its_user_only_skills_say_so_for_codex(self):
        root = TOOLS.parents[1]
        problems: list[str] = []
        found = agent_client.skills(root, "", problems, [])
        self.assertEqual(problems, [])
        self.assertEqual(sorted(name for name, s in found.items() if s["userOnly"]), ["publish", "review-findings"])
        self.assertTrue(all(s["linked"] for s in found.values()), found)
        self.assertFalse(any((root / name).exists() for name in agent_client.SHADOWS), "an AGENTS.md would shadow CLAUDE.md for Codex")


if __name__ == "__main__":
    unittest.main()
