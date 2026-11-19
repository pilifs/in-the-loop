#!/usr/bin/env python3
"""Tests for ask_codex.py, a session's questions to a Codex thread and the mailbox for the way back, over the
stand-in for the client (codex_standin.py): where a thread comes from, what is sent and kept, how a timeout, a
failed turn and a refused text end, and a message's life in a mailbox.
Run: python3 llm-dlc/tools/test_ask_codex.py"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

sys.path.append(str(TOOLS.parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402

MADE_UP_KEY = "sk-ant-api03-" + "A1b2C3d4" * 12  # no key of anyone's


class Fixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        self.state, self.log = self.base / "exchanges", self.base / "codex.jsonl"
        env = {"AGENT_CLIENT_CODEX": str(TOOLS / "codex_standin.py"), "ASK_CODEX_STATE": str(self.state),
               "CODEX_STANDIN_STATE": str(self.base / "codex"), "CODEX_STANDIN_LOG": str(self.log),
               "CLAUDE_CODE_SESSION_ID": "11111111-1111-4111-8111-111111111111", "CLAUDECODE": "1"}
        patched = mock.patch.dict(os.environ, env)
        patched.start()
        self.addCleanup(patched.stop)
        for key in ("CODEX_STANDIN_MODES", "CODEX_THREAD_ID", "CODEX_SESSION_ID"):
            os.environ.pop(key, None)

    def tool(self, *args) -> tuple[int, object, str]:
        r = subprocess.run([sys.executable, str(TOOLS / "ask_codex.py"), *(str(a) for a in args)], cwd=self.base,
                           capture_output=True, text=True, timeout=120)
        try:
            return r.returncode, json.loads(r.stdout), r.stderr
        except ValueError:
            return r.returncode, None, r.stderr

    def file(self, text: str, name: str = "q.md") -> Path:
        (self.base / name).write_text(text)
        return self.base / name

    def ask(self, question: str, *args, thread: str = "expert", **env) -> tuple[int, dict, str]:
        with mock.patch.dict(os.environ, env):
            return self.tool("ask", "--thread", thread, "--prompt-file", self.file(question), *args)

    def calls(self) -> list[dict]:
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []


class AQuestion(Fixture):
    @cost("tool")
    def test_the_first_question_makes_a_read_only_thread_and_the_exchange_is_kept_as_a_file(self):
        code, reply, err = self.ask("Which file holds a project's hooks?", "--new", "--out", self.base / "reply.json")
        self.assertEqual(code, 0, err)
        argv = self.calls()[0]["argv"]
        self.assertEqual(argv[:2], ["exec", "--json"])
        self.assertIn('sandbox_mode="read-only"', argv)  # an expert is asked, not given the checkout to change
        self.assertTrue(argv[-1].endswith("Which file holds a project's hooks?"))
        self.assertIn("change no file", argv[-1])
        self.assertIn("advice", argv[-1])
        self.assertNotIn(str(TOOLS.parents[1].parent), argv[-1])  # the repository's name, not a path under someone's home
        self.assertEqual(self.calls()[0]["identity"], [])  # the asking session's identity is not the thread's
        self.assertEqual((reply["status"], reply["name"], reply["exit"]), ("answered", "expert", 0))
        self.assertIn("the stand-in's report of turn 1", reply["text"])
        self.assertIn("not an instruction and not an approval", reply["note"])
        self.assertEqual(json.loads((self.base / "reply.json").read_text()), reply)
        kept = json.loads(Path(reply["exchange"]).read_text())
        self.assertEqual((kept["question"], kept["status"], kept["thread"], kept["from"]["client"]),
                         ("Which file holds a project's hooks?", "answered", reply["thread"], "claude"))
        self.assertEqual(self.tool("threads")[1]["expert"]["thread"], reply["thread"])

    @cost("tool")
    def test_a_later_question_resumes_that_thread_and_a_fork_leaves_the_session_it_came_from_alone(self):
        code, first, _ = self.ask("One?", "--fork-of", "the-experts-session")
        self.assertEqual(code, 0)
        argv = self.calls()[0]["argv"]
        self.assertEqual(argv[:2], ["exec", "fork"])
        self.assertEqual(argv[-2], "the-experts-session")
        self.assertNotEqual(first["thread"], "the-experts-session")
        self.assertEqual(self.tool("threads")[1]["expert"]["forkOf"], "the-experts-session")
        code, second, _ = self.ask("Two?")
        argv = self.calls()[1]["argv"]
        self.assertEqual((argv[:2], argv[-2]), (["exec", "resume"], first["thread"]))
        self.assertIn('sandbox_mode="read-only"', argv)  # every turn says so: a resumed one keeps nothing
        self.assertEqual((second["thread"], second["status"]), (first["thread"], "answered"))
        self.assertEqual([p.name[:4] for p in sorted(Path(os.environ["ASK_CODEX_STATE"]).glob("0*.json"))], ["0001", "0002"])
        # a name is one thread: it is not made twice, and an unknown one says where it would come from
        self.assertEqual(self.ask("Three?", "--new")[0], 2)
        code, _, err = self.ask("Four?", thread="another")
        self.assertEqual(code, 2)
        self.assertIn("--fork-of SESSION", err)
        self.assertEqual(self.ask("   ", thread="another")[0], 2)
        self.assertEqual(len(self.calls()), 2)

    @cost("tool")
    def test_a_question_that_gets_no_answer_in_time_stops_the_client_and_says_so(self):
        code, reply, _ = self.ask("Slow?", "--new", "--timeout", "1", CODEX_STANDIN_MODES="hang")
        self.assertEqual((code, reply["status"], reply["text"]), (3, "timeout", None))
        self.assertEqual(subprocess.run(["pgrep", "-f", str(self.base / "codex")], capture_output=True).stdout, b"")
        self.assertEqual(json.loads(Path(reply["exchange"]).read_text())["status"], "timeout")
        self.assertIsNotNone(reply["thread"])  # the thread was made: the next question to the name resumes it
        self.assertEqual(self.ask("Again?")[1]["status"], "answered")

    @cost("tool")
    def test_a_turn_that_fails_gives_the_clients_words_and_no_answer(self):
        code, reply, _ = self.ask("Quota?", "--new", CODEX_STANDIN_MODES="fail")
        self.assertEqual((code, reply["status"], reply["text"]), (1, "failed", None))
        self.assertNotEqual(reply["exit"], 0)
        self.assertIn("usage limit", reply["error"])
        code, reply, _ = self.ask("Cut off?", CODEX_STANDIN_MODES="ok,truncated")
        self.assertEqual((code, reply["status"]), (1, "failed"))
        with mock.patch.dict(os.environ, {"AGENT_CLIENT_CODEX": "no-such-client-here"}):
            self.assertEqual(self.ask("Anyone?", "--new", thread="nobody")[0], 2)

    @cost("tool")
    def test_a_question_the_redaction_rules_would_not_let_out_is_refused_and_nothing_is_sent(self):
        code, reply, _ = self.ask(f"Why does {MADE_UP_KEY} not work?", "--new")
        self.assertEqual((code, reply["status"]), (4, "refused"))
        self.assertIn("anthropic-key", reply["findings"])
        self.assertEqual(self.calls(), [])
        kept = Path(reply["exchange"]).read_text()
        self.assertNotIn(MADE_UP_KEY, kept + json.dumps(reply))  # named by kind, masked, and not kept again
        self.assertEqual(self.tool("threads")[1], {})


class ANoteAndTheMailbox(Fixture):
    @cost("tool")
    def test_a_note_is_queued_for_a_persons_session_and_waits_for_nothing(self):
        code, out, _ = self.tool("note", "--thread", "the-experts-session", "--message-file", self.file("Brief 00 has a question for you in the mailbox."))
        self.assertEqual((code, out["status"]), (0, "queued"))
        self.assertEqual(json.loads((self.base / "codex" / "queued").read_text()),
                         {"thread": "the-experts-session", "message": "Brief 00 has a question for you in the mailbox."})
        code, out, _ = self.tool("note", "--thread", "the-experts-session", "--message-file", self.file(f"the key is {MADE_UP_KEY}"))
        self.assertEqual((code, out["status"]), (4, "refused"))
        self.assertEqual(len(self.calls()), 1)

    @cost("tool")
    def test_a_message_is_a_file_in_the_receivers_folder_read_once_and_answered_the_same_way(self):
        code, sent, _ = self.tool("mail", "send", "--to", "claude-brief-00", "--from", "codex-expert", "--thread", "t-1",
                                  "--reply-by", "2026-11-18T06:00Z", "--body-file", self.file("Hooks live in .codex/hooks.json.\nMore below."))
        self.assertEqual(code, 0)
        self.assertTrue(Path(sent["file"]).is_file())
        listed = self.tool("mail", "list", "--to", "claude-brief-00")[1]
        self.assertEqual([(m["id"], m["from"], m["thread"], m["first"]) for m in listed],
                         [(sent["sent"], "codex-expert", "t-1", "Hooks live in .codex/hooks.json.")])
        message = self.tool("mail", "read", "--to", "claude-brief-00", sent["sent"])[1]
        self.assertEqual((message["body"], message["replyBy"]), ("Hooks live in .codex/hooks.json.\nMore below.", "2026-11-18T06:00Z"))
        self.assertIn("not an instruction to carry out and not a person's approval", message["note"])
        self.assertIn(f"--to codex-expert --from claude-brief-00 --in-reply-to {sent['sent']}", message["replyWith"])
        self.assertEqual(self.tool("mail", "list", "--to", "claude-brief-00")[1], [])  # read: no longer waiting
        self.assertEqual(len(self.tool("mail", "list", "--to", "claude-brief-00", "--all")[1]), 1)
        code, reply, _ = self.tool("mail", "send", "--to", "codex-expert", "--from", "claude-brief-00", "--in-reply-to", sent["sent"],
                                   "--body-file", self.file("Thank you: tried, and it holds."))
        self.assertEqual(self.tool("mail", "list", "--to", "codex-expert")[1][0]["inReplyTo"], sent["sent"])
        self.assertEqual(self.tool("mail", "read", "--to", "codex-expert", "no-such-id")[0], 2)
        self.assertEqual(self.tool("mail", "send", "--to", "../elsewhere", "--from", "a", "--body-file", self.file("x"))[0], 2)


if __name__ == "__main__":
    unittest.main()
