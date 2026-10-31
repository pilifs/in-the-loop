#!/usr/bin/env python3
"""Tests for metrics.py, on made-up sessions. Run: python3 llm-dlc/tools/test_metrics.py"""
import json
import unittest

import metrics

PRICING = {"as_of": "2000-01-01", "models": {
    "m-a": {"input": 10, "output": 50, "cache_read": 1, "cache_write_5m": 12.5, "cache_write_1h": 20},
    "m-b": {"input": 1, "output": 5, "cache_read": 0.1, "cache_write_5m": 1.25, "cache_write_1h": 2}}}


def at(minute, second=0):
    return f"2000-01-01T{10 + minute // 60:02d}:{minute % 60:02d}:{second:02d}.000Z"


def prompt(ts, text):
    return {"type": "user", "timestamp": ts, "message": {"content": text}}


def usage(read=0, write=0, fresh=1, output=10, thinking=0, five=0):
    return {"input_tokens": fresh, "output_tokens": output, "cache_read_input_tokens": read,
            "cache_creation_input_tokens": write, "output_tokens_details": {"thinking_tokens": thinking},
            "cache_creation": {"ephemeral_5m_input_tokens": five, "ephemeral_1h_input_tokens": write - five}}


def reply(ts, mid, u, content=(), model="m-a", effort="low", **extra):
    return {"type": "assistant", "timestamp": ts, "effort": effort, **extra,
            "message": {"id": mid, "model": model, "usage": u, "content": list(content)}}


def tool(tid, name="Bash", **inp):
    return {"type": "tool_use", "id": tid, "name": name, "input": inp}


def result(ts, tid, text="done", error=False):
    return {"type": "user", "timestamp": ts, "toolUseResult": {},
            "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": text, "is_error": error}]}}


def compact(ts):
    return {"type": "system", "subtype": "compact_boundary", "timestamp": ts,
            "compactMetadata": {"trigger": "manual", "preTokens": 900, "postTokens": 90, "durationMs": 5000}}


def build(entries, commits=(), logs=None, subagents=()):
    manifest = {"session_id": "s", "log": {"sha256": "x"}, "commits": list(commits), "logs": logs or {}}
    return metrics.session(manifest, entries, list(subagents), PRICING, lambda s: s)


class Classify(unittest.TestCase):
    def test_only_work_opens_a_prompt(self):
        kinds = [metrics.prompt_kind(prompt(at(0), t)) for t in (
            "fix it", "/compact", "<command-name>/model</command-name>", "<local-command-stdout>x</local-command-stdout>",
            "<task-notification>x</task-notification>", "/home/x/file is broken",
            "<system-reminder>hi</system-reminder>", "<system-reminder>hi</system-reminder>real")]
        self.assertEqual([k and k[0] for k in kinds],
                         ["human", "command", "command", None, "task_notification", "human", None, "human"])
        self.assertIsNone(metrics.prompt_kind({**prompt(at(0), "x"), "isCompactSummary": True}))
        self.assertIsNone(metrics.prompt_kind({**prompt(at(0), "x"), "isMeta": True}))
        self.assertIsNone(metrics.prompt_kind(result(at(0), "t")))

    def test_bash_family(self):
        for command, family in (("cd a && FOO=1 sudo -n gradle build", "gradle"), ("(cd a; ./gradlew test)", "gradlew"),
                                ("for x in a; do echo; done", "shell"), ("cd a", "other"), ("/usr/bin/jj log | head", "jj")):
            self.assertEqual(metrics.bash_family(command), family, command)

    def test_error_kind(self):
        self.assertEqual(metrics.error_kind("Exit code 2\nboom"), "exit_code")
        self.assertEqual(metrics.error_kind("The user doesn't want to proceed"), "denied")
        self.assertEqual(metrics.error_kind("something else"), "other")


class Accounting(unittest.TestCase):
    def test_a_message_logged_per_block_counts_once(self):
        u = usage(write=1000, five=400, output=100, thinking=30)
        s = build([prompt(at(0), "go"), reply(at(0, 1), "a", u), reply(at(0, 2), "a", u)])
        t = s["totals"]
        self.assertEqual((t["api_calls"], t["output_tokens"], t["thinking_tokens"]), (1, 100, 30))
        self.assertEqual((t["cache_write_5m_tokens"], t["cache_write_1h_tokens"]), (400, 600))
        self.assertAlmostEqual(t["usd"], (10 + 100 * 50 + 400 * 12.5 + 600 * 20) / 1e6)
        self.assertAlmostEqual(t["uncached_usd"], (1001 * 10 + 100 * 50) / 1e6)

    def test_parallel_tools_are_not_counted_twice(self):
        s = build([prompt(at(0), "go"),
                   reply(at(0, 1), "a", usage(), [tool("t1"), tool("t2")]),
                   result(at(1, 1), "t1"), result(at(1, 1), "t2"),
                   reply(at(1, 2), "b", usage())])
        p = s["prompts"][0]
        self.assertEqual(sum(t["ms"] for t in s["tools"]), 120_000)
        self.assertEqual(p["tool_ms"], 60_000)
        self.assertEqual(p["agent_ms"], 62_000)

    def test_request_start_gives_model_time(self):
        s = build([prompt(at(0), "go"), {"type": "api-request", "id": "r", "timestamp": at(0, 1)},
                   reply(at(0, 31), "a", usage(), requestRef="r")])
        self.assertEqual(s["prompts"][0]["model_ms"], 30_000)

    def test_tool_outcomes(self):
        s = build([prompt(at(0), "go"), reply(at(0, 1), "a", usage(), [tool("t1", command="make"), tool("t2")]),
                   result(at(0, 2), "t1", "Exit code 1\nboom", error=True)])
        self.assertEqual([(t["status"], t["error_kind"], t["family"]) for t in s["tools"]],
                         [("error", "exit_code", "make"), ("no_result", None, None)])
        self.assertEqual(s["totals"]["tool_errors"], 1)

    def test_client_records_are_not_calls(self):
        s = build([prompt(at(0), "go"), reply(at(0, 1), "a", usage(), model="<synthetic>")])
        self.assertEqual(s["totals"]["api_calls"], 0)

    def test_reported_cost_shows_what_the_log_lacks(self):
        s = build([prompt(at(0), "go"), reply(at(0, 1), "a", usage(output=1000)),
                   {"type": "cost-state", "totalCostUSD": 0.5, "modelUsage": {}}])
        self.assertAlmostEqual(s["reported"]["unattributed_usd"], 0.5 - s["totals"]["usd"])

    def test_subagent_calls_count_but_not_their_wall_time(self):
        sub = [reply(at(0, 2), "x", usage(), [tool("st")]), result(at(0, 9), "st")]
        s = build([prompt(at(0), "go"), reply(at(0, 1), "a", usage())], subagents=[("agent1", sub)])
        self.assertEqual(s["totals"]["api_calls"], 2)
        self.assertEqual(s["prompts"][0]["api_calls"], 2)
        self.assertEqual(s["prompts"][0]["tool_ms"], 0)
        self.assertEqual(s["totals"]["subagents"], 1)


class Commits(unittest.TestCase):
    def test_a_log_line_count_cuts_the_session(self):
        entries = [prompt(at(0), "one"), reply(at(0, 1), "a", usage(output=1)),
                   prompt(at(1), "two"), reply(at(1, 1), "b", usage(output=2)),
                   prompt(at(2), "three"), reply(at(2, 1), "c", usage(output=4))]
        commits = [{"change_id": "c1", "summary": "First", "log_sha256": "l1"},
                   {"change_id": "c2", "summary": "Second", "log_sha256": "l2"}]
        logs = {"l1": {"lines": 2, "bytes": 1, "gzip_bytes": 1}, "l2": {"lines": 4, "bytes": 2, "gzip_bytes": 1}}
        s = build(entries, commits, logs)
        self.assertEqual([c["output_tokens"] for c in s["commits"]], [1, 2])
        self.assertEqual(s["commits"][1]["ts"], at(1, 1))
        self.assertEqual(s["after_last_commit"]["output_tokens"], 4)
        self.assertEqual([c["commit"] for c in s["calls"]], [0, 1, None])

    def test_a_withdrawn_log_has_no_place_but_does_not_break_the_rest(self):
        s = build([prompt(at(0), "go"), reply(at(0, 1), "a", usage())],
                  [{"change_id": "c1", "summary": "Gone", "log_sha256": "l1"}], {"l1": {"withdrawn": "leak"}})
        self.assertEqual(s["commits"][0]["api_calls"], 0)
        self.assertEqual(s["after_last_commit"]["api_calls"], 1)


class CacheEvents(unittest.TestCase):
    def causes(self, *entries):
        return [(e["cause"], e["also"]) for e in build([prompt(at(0), "go"), *entries])["cache_events"]]

    def test_each_cause(self):
        first = reply(at(0, 1), "a", usage(write=1000))
        self.assertEqual(self.causes(first, reply(at(1), "b", usage(read=1000, write=5))),
                         [("session_start", [])])
        self.assertEqual(self.causes(first, reply(at(1), "b", usage(read=1000, write=30_000))),
                         [("session_start", []), ("large_input", [])])
        self.assertEqual(self.causes(first, reply(at(1), "b", usage(write=1001), model="m-b"))[1],
                         ("model_switch", []))
        self.assertEqual(self.causes(first, reply(at(90), "b", usage(write=1001)))[1], ("cache_expired", []))
        self.assertEqual(self.causes(first, reply(at(1), "b", usage(write=1001), effort="high"))[1],
                         ("effort_change", []))
        self.assertEqual(self.causes(first, reply(at(1), "b", usage(write=1001)))[1], ("unexplained", []))

    def test_a_compaction_is_not_blamed_on_the_model_switch_beside_it(self):
        self.assertEqual(self.causes(reply(at(0, 1), "a", usage(write=1000)), compact(at(0, 30)),
                                     reply(at(1), "b", usage(write=99), model="m-b"))[1],
                         ("compaction", ["model_switch"]))

    def test_a_short_ttl_expires_sooner(self):
        short = reply(at(0, 1), "a", usage(write=1000, five=1000))
        self.assertEqual(self.causes(short, reply(at(9), "b", usage(write=1001)))[1], ("cache_expired", []))

    def test_a_large_input_is_paid_for_on_each_later_call(self):
        s = build([prompt(at(0), "go"), reply(at(0, 1), "a", usage(write=1000)),
                   reply(at(1), "b", usage(read=1000, write=30_000)),
                   reply(at(2), "c", usage(read=31_000)), reply(at(3), "d", usage(read=31_000))])
        e = s["cache_events"][1]
        self.assertEqual(e["later_calls"], 2)
        self.assertAlmostEqual(e["reread_usd"], 2 * 30_000 / 1e6)


class Output(unittest.TestCase):
    def test_text_is_cleaned_after_it_is_cut(self):
        seen = []
        s = metrics.session({"session_id": "s", "log": {}, "commits": []},
                            [prompt(at(0), "word " * 100)], [], PRICING, lambda t: seen.append(t) or "CLEAN")
        self.assertEqual(s["prompts"][0]["text"], "CLEAN")
        self.assertLessEqual(len(seen[0]), metrics.TEXT_LIMIT)

    def test_rows_get_a_line_each_and_stay_json(self):
        doc = {"schema": "x", "totals": {"a": 1}, "rows": [{"b": 1}, {"b": 2}], "none": []}
        text = metrics.dumps(doc)
        self.assertEqual(json.loads(text), doc)
        self.assertIn('    {"b":1},\n    {"b":2}\n', text)

    def test_rollup_merges_a_commit_across_sessions(self):
        commit = {"change_id": "c1", "summary": "Shared", "log_sha256": "l"}
        logs = {"l": {"lines": 2}}
        one = build([prompt(at(0), "a"), reply(at(0, 1), "a", usage(output=1))], [commit], logs)
        two = build([prompt(at(9), "b"), reply(at(9, 1), "b", usage(output=2))], [commit], logs)
        r = metrics.rollup([({"session_id": "s1"}, one), ({"session_id": "s2"}, two),
                            ({"session_id": "empty"}, build([]))], PRICING)
        self.assertEqual(r["totals"]["sessions"], 2)
        self.assertEqual(len(r["commits"]), 1)
        self.assertEqual((r["commits"][0]["sessions"], r["commits"][0]["output_tokens"]), (["s1", "s2"], 3))
        self.assertEqual(r["by_day"][0]["prompts"], 2)

    def test_an_unknown_model_is_flagged_not_priced_at_zero_silently(self):
        s = build([prompt(at(0), "go"), reply(at(0, 1), "a", usage(), model="m-new")])
        self.assertEqual(s["totals"]["unpriced_calls"], 1)
        self.assertIsNone(s["calls"][0]["usd"])

    def test_an_empty_log_gives_an_empty_file(self):
        s = build([])
        self.assertEqual((s["totals"]["api_calls"], s["time"]["elapsed_ms"]), (0, 0))
        self.assertEqual(len(s["windows"]), 1)


if __name__ == "__main__":
    unittest.main()
