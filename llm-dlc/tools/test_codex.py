"""Tests for codex_rollout.py: Codex sessions read as Claude Code transcripts by sync.py and metrics.py.

    python3 -B llm-dlc/tools/test_codex.py
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import codex_rollout  # noqa: E402
import metrics  # noqa: E402
import sync  # noqa: E402

SID = "01a1e105-6241-7d73-87f2-e2b54e6fe96d"
TURN = "01a1e105-0000-7000-8000-000000000001"


def rollout(cwd: str = "/repo") -> list[dict]:
    """A one-turn rollout: a prompt, a tool call that runs a command and a patch, then the answer."""
    usage1 = {"input_tokens": 1000, "cached_input_tokens": 800, "cache_write_input_tokens": 0,
              "output_tokens": 50, "reasoning_output_tokens": 10, "total_tokens": 1050}
    usage2 = {"input_tokens": 1200, "cached_input_tokens": 1000, "cache_write_input_tokens": 0,
              "output_tokens": 20, "reasoning_output_tokens": 0, "total_tokens": 1220}
    return [
        {"timestamp": "2026-11-15T21:00:00.000Z", "type": "session_meta",
         "payload": {"id": SID, "cwd": cwd, "cli_version": "0.169.0", "creator_user_id": "user-MadeUp0123456789MadeUp01"}},
        {"timestamp": "2026-11-15T21:00:00.100Z", "type": "event_msg", "payload": {"type": "task_started", "turn_id": TURN}},
        {"timestamp": "2026-11-15T21:00:00.200Z", "type": "turn_context", "payload": {"turn_id": TURN, "model": "gpt-6.1-sol"}},
        {"timestamp": "2026-11-15T21:00:00.300Z", "type": "response_item",
         "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "<environment_context/>"}]}},
        {"timestamp": "2026-11-15T21:00:00.400Z", "type": "event_msg", "payload": {"type": "item_completed", "turn_id": TURN,
         "item": {"type": "UserMessage", "content": [{"type": "text", "text": "Add greet.py"}]}}},
        {"timestamp": "2026-11-15T21:00:02.000Z", "type": "response_item",
         "payload": {"type": "custom_tool_call", "call_id": "call_1", "name": "exec", "input": "await tools.exec_command({cmd: 'ls'})"}},
        {"timestamp": "2026-11-15T21:00:02.010Z", "type": "token_usage_record",
         "payload": {"response_id": "resp_1", "usage": usage1}},
        {"timestamp": "2026-11-15T21:00:03.000Z", "type": "event_msg", "payload": {"type": "item_completed", "turn_id": TURN,
         "item": {"type": "CommandExecution", "id": "exec-1", "command": ["/bin/bash", "-lc", "ls"], "exit_code": 2,
                  "status": "failed", "aggregated_output": "ls: cannot access"},
         "started_at_ms": 1794776402500, "completed_at_ms": 1794776403000}},
        {"timestamp": "2026-11-15T21:00:03.500Z", "type": "event_msg", "payload": {"type": "item_completed", "turn_id": TURN,
         "item": {"type": "FileChange", "id": "exec-2", "status": "completed", "stdout": "Success.",
                  "changes": {"/repo/greet.py": {"type": "add"}, "/repo/b.py": {"type": "update"}}},
         "started_at_ms": 1794776403400, "completed_at_ms": 1794776403500}},
        {"timestamp": "2026-11-15T21:00:04.000Z", "type": "response_item",
         "payload": {"type": "custom_tool_call_output", "call_id": "call_1", "output": [{"type": "input_text", "text": "Script completed"}]}},
        {"timestamp": "2026-11-15T21:00:05.000Z", "type": "response_item",
         "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Done."}]}},
        {"timestamp": "2026-11-15T21:00:05.010Z", "type": "token_usage_record",
         "payload": {"response_id": "resp_2", "usage": usage2}},
        {"timestamp": "2026-11-15T21:00:05.100Z", "type": "event_msg", "payload": {"type": "task_complete", "turn_id": TURN}},
    ]


class View(unittest.TestCase):
    def setUp(self):
        self.raw = rollout()
        self.view = codex_rollout.claude_view(self.raw)

    def test_one_entry_per_line(self):
        self.assertEqual(len(self.view), len(self.raw))
        self.assertTrue(codex_rollout.looks_like_rollout(self.raw))
        self.assertTrue(codex_rollout.looks_like_view(self.view))

    def test_only_the_users_message_is_a_prompt(self):
        prompts = [e for e in self.view if sync.is_prompt(e)]
        self.assertEqual([sync.text_of(e["message"]) for e in prompts], ["Add greet.py"])

    def test_summary(self):
        s = sync.summarize(self.view, "/repo")
        self.assertEqual(s["client"], {"tool": "codex", "version": "0.169.0"})
        self.assertEqual(s["models"], ["gpt-6.1-sol"])
        self.assertEqual(s["stats"]["turns"], 1)
        self.assertEqual(s["stats"]["api_calls"], 2)
        self.assertEqual(s["stats"]["tool_calls"], 3)  # the exec cell, the command and the patch it ran
        self.assertEqual(s["stats"]["tool_errors"], 1)  # the command's exit 2
        self.assertEqual(s["tools"], {"Bash": 1, "apply_patch": 1, "exec": 1})
        self.assertEqual(s["files_touched"], ["b.py", "greet.py"])
        # OpenAI's input includes the cached tokens; Claude's keys keep them apart
        self.assertEqual(s["stats"]["usage"], {"input_tokens": 400, "cache_read_input_tokens": 1800,
                                               "cache_creation_input_tokens": 0, "output_tokens": 70})

    def test_metrics_see_calls_and_tools_with_their_results(self):
        t = metrics.read_transcript(self.view, None, lambda s: s)
        self.assertEqual([c["model"] for c in t["calls"]], ["gpt-6.1-sol", "gpt-6.1-sol"])
        self.assertEqual(t["calls"][0]["thinking_tokens"], 10)
        by_name = {x["name"]: x for x in t["tools"]}
        self.assertEqual(by_name["Bash"]["status"], "error")
        self.assertEqual(by_name["Bash"]["ms"], 500)
        self.assertEqual(by_name["Bash"]["family"], "ls")
        self.assertEqual(by_name["apply_patch"]["status"], "ok")
        self.assertEqual(by_name["exec"]["status"], "ok")
        self.assertEqual(len(t["prompts"]), 1)

    def test_a_model_call_starts_when_the_model_was_handed_the_turn(self):
        # A response's items are written together when it ends: the call began at the prompt, and the next one at
        # the tool call's output, so the model's share of the time is the wait for it and not a few milliseconds.
        t = metrics.read_transcript(self.view, None, lambda s: s)
        self.assertEqual([(c["start"][17:23], c["end"][17:23]) for c in t["calls"]], [("00.400", "03.400"), ("04.000", "05.010")])
        prompt = metrics.session({"session_id": SID}, self.view, [], {"models": {}}, lambda s: s)["prompts"][0]
        self.assertEqual((prompt["model_ms"], prompt["agent_ms"]), (3000 + 1010, 4610))
        # a command or a patch that a tool call ran has its own times, and no call's start
        self.assertEqual([("requestStart" in e) for e in self.view if e.get("type") == "assistant"
                          and any("codexResult" in b for b in e["message"]["content"])], [False, False])


class Finding(unittest.TestCase):
    def test_session_ids_and_repo_filter(self):
        with tempfile.TemporaryDirectory() as d:
            day = Path(d) / "sessions" / "2026" / "11" / "15"
            day.mkdir(parents=True)
            for name, cwd in ((f"rollout-2026-11-15T21-00-00-{SID}.jsonl", "/repo/sub"),
                              ("rollout-2026-11-15T21-01-00-01a1e105-6241-7d73-87f2-e2b54e6fe96e.jsonl", "/repository")):
                (day / name).write_text("\n".join(json.dumps(e) for e in rollout(cwd)) + "\n")
            old, codex_rollout.SESSIONS = codex_rollout.SESSIONS, Path(d) / "sessions"
            try:
                found = codex_rollout.rollouts_in(Path("/repo"))
            finally:
                codex_rollout.SESSIONS = old
        self.assertEqual([codex_rollout.session_id(p) for p in found], [SID])
        self.assertEqual(codex_rollout.session_id(Path("0a31eedb-0668-4cb5-8ee4-63d018293f2f.jsonl")),
                         "0a31eedb-0668-4cb5-8ee4-63d018293f2f")


    def test_a_thread_that_was_only_asked_a_question_is_not_a_session_of_the_checkout(self):
        asked = "01a1e105-6241-7d73-87f2-e2b54e6fe96e"
        with tempfile.TemporaryDirectory() as d:
            day = Path(d) / "sessions" / "2026" / "11" / "15"
            day.mkdir(parents=True)
            for sid in (SID, asked):
                (day / f"rollout-2026-11-15T21-00-00-{sid}.jsonl").write_text("\n".join(json.dumps(e) for e in rollout("/repo")) + "\n")
            (Path(d) / "threads.json").write_text(json.dumps({"expert": {"thread": asked, "forkOf": "someone-elses-session"}}))
            old = codex_rollout.SESSIONS, sync.REPO, sync._ASKED, os.environ.get("ASK_CODEX_STATE")
            codex_rollout.SESSIONS, sync.REPO, sync._ASKED, os.environ["ASK_CODEX_STATE"] = Path(d) / "sessions", Path("/repo"), None, d
            try:
                found = [sync.sid_of(p) for p in sync.session_transcripts() if codex_rollout.is_rollout(p)]
                self.assertEqual(sync.sid_of(sync.transcript_of(SID)), SID)
                self.assertFalse(codex_rollout.is_rollout(sync.transcript_of(asked)))
            finally:
                codex_rollout.SESSIONS, sync.REPO, sync._ASKED = old[:3]
                os.environ.pop("ASK_CODEX_STATE") if old[3] is None else os.environ.update(ASK_CODEX_STATE=old[3])
        self.assertEqual(found, [SID])


class Redaction(unittest.TestCase):
    def test_codex_account_identifiers(self):
        out = sync.Redactor()("\n".join(json.dumps(e) for e in rollout()) + "\n").decode()
        self.assertNotIn("user-MadeUp0123456789MadeUp01", out)
        self.assertIn('"creator_user_id":"[REDACTED:account-id]"', out)

    def test_account_usage(self):
        r = sync.Redactor()
        line = json.dumps({"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 5}},
                                                            "rate_limits": {"plan_type": "pro", "credits": {"balance": "62500.0"}}}})
        out = r(line + "\n").decode()
        self.assertNotIn("62500", out)
        self.assertIn('"rate_limits":"[REDACTED:account-usage]"', out)
        self.assertIn('"input_tokens":5', out)
        self.assertEqual(r(out).decode(), out)
        self.assertTrue(r.hits_of_line(line)[0])  # check flags it where a log still has it
        self.assertFalse(r.hits_of_line(out.strip())[0])

    def test_encrypted_reasoning(self):
        r = sync.Redactor()
        blob = "gAAAAABmadeUpCiphertext" + "QUJD" * 40          # made up: the shape of a Fernet token, no real bytes
        lines = [{"type": "response_item", "payload": {"type": "reasoning", "summary": [], "encrypted_content": blob}},
                 {"type": "response_item", "payload": {"type": "message", "content": [{"type": "encrypted_content", "encrypted_content": blob}]}},
                 {"type": "compacted", "payload": {"replacement_history": [{"type": "compaction", "encrypted_content": blob}]}},
                 {"type": "response_item", "payload": {"type": "reasoning", "encrypted_content": None}}]
        for e in lines:
            line = json.dumps(e)
            out = r(line + "\n").decode()
            self.assertNotIn(blob, out)
            self.assertEqual(r(out).decode(), out)                   # idempotent
            self.assertFalse(r.hits_of_line(out.strip())[0])
            if blob in line:
                self.assertIn('"encrypted_content":"[REDACTED:encrypted-reasoning]"', out)
                self.assertFalse(r.hits_of_line(line)[0])            # a log stored before policy 6 is not an error
        self.assertIn('"encrypted_content":null', r(json.dumps(lines[-1]) + "\n").decode())  # only strings go

    def test_encrypted_reasoning_in_text(self):
        r = sync.Redactor()
        blob = "gAAAAABmadeUpCiphertext" + "QUJD" * 40 + "=="     # made up: the shape of a Fernet token, no real bytes
        texts = [f"python3 - <<'EOF'\nx = '{blob}'\nEOF", f"payload {blob}.", f'{{"encrypted_content":"{blob}"}}']
        for text in texts:
            line = json.dumps({"type": "response_item", "payload": {"type": "function_call", "arguments": text}})
            out = r(line + "\n").decode()
            self.assertNotIn("gAAAAABmadeUp", out)
            self.assertIn("[REDACTED:encrypted-reasoning]", out)
            self.assertEqual(r(out).decode(), out)                   # idempotent
            self.assertFalse(r.hits_of_line(out.strip())[1])         # no long-token warning left
            self.assertFalse(r.hits_of_line(line)[0])                # a log stored before policy 7 is not an error
        for kept in ("gAAAAAshort", "xgAAAAA" + "QUJD" * 20, "the word gAAAAA alone"):
            self.assertEqual(r.string(kept), kept)                   # too short, or inside a longer word


if __name__ == "__main__":
    unittest.main()
