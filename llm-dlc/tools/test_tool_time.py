#!/usr/bin/env python3
"""Tests for tool_time.py, on made-up logs. Run: python3 llm-dlc/tools/test_tool_time.py"""
import contextlib
import gzip
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import tool_time as tt

SID = "00000000-0000-4000-8000-000000000001"
SID2 = "00000000-0000-4000-8000-000000000002"


def at(second):
    return f"2000-01-01T10:{second // 60:02d}:{second % 60:02d}.000Z"


def prompt(second, text="go"):
    return {"type": "user", "timestamp": at(second), "message": {"content": text}}


def reply(second, mid, *tools):
    return {"type": "assistant", "timestamp": at(second),
            "message": {"id": mid, "model": "m", "usage": {"input_tokens": 1, "output_tokens": 1},
                        "content": list(tools)}}


def bash(tid, command, **extra):
    return {"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": command, **extra}}


def read(tid, path):
    return {"type": "tool_use", "id": tid, "name": "Read", "input": {"file_path": path}}


def result(second, tid, text="ok", tool_result=None):
    return {"type": "user", "timestamp": at(second), "toolUseResult": tool_result or {},
            "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": text}]}}


CARGO_OUTPUT = """\
   Compiling jvmcontract v0.1.0
    Finished `test` profile [unoptimized + debuginfo] target(s) in 1m 2.5s
     Running unittests src/lib.rs (target/debug/deps/jvmcontract-0123456789abcdef)
test result: ok. 258 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 3.00s
     Running tests/conformance.rs (target/debug/deps/conformance-0123456789abcdef)
test result: ok. 10 passed; 0 failed; 2 ignored; 0 measured; 0 filtered out; finished in 60.50s
   Doc-tests jvmcontract
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.10s
"""


class Classify(unittest.TestCase):
    def test_first_matching_category(self):
        cases = {
            "cd lib && CARGO_BUILD_JOBS=8 cargo test --release --test heap 2>&1 | tail": "cargo test",
            "bash llm-dlc/tools/cleanup-integration.sh > /tmp/i.log": "integration check",
            "cargo build --release && jbmc --classpath x Foo": "proof inline",
            "J=lib/target/release/jvmcontract; $J prove 'a.B#c' --classes build": "proof inline",
            "cargo build --release": "cargo build",
            "python3 examples/tools/test_build.py": "python tests",
            "python3 -m unittest discover -s verification": "python tests",
            "python3 lib/benchmark/run.py --engines native": "benchmark inline",
            "python3 examples/tools/build.py 052": "build.py",
            "python3 llm-dlc/tools/sync.py check": "sync.py",
            "cargo test && python3 llm-dlc/tools/sync.py commit -m x": "cargo test",
            "jj status": "other",
        }
        for command, category in cases.items():
            self.assertEqual(tt.classify("Bash", {"command": command}), category, command)
        self.assertEqual(tt.classify("AskUserQuestion", {}), "asking the user")
        self.assertEqual(tt.classify("Edit", {}), "other")


class Batches(unittest.TestCase):
    def test_parallel_calls_count_once_for_the_one_that_finished_last(self):
        entries = [prompt(0), reply(1, "m1", bash("a", "cargo test"), read("b", "/x")),
                   result(3, "b"), result(11, "a"),
                   reply(12, "m2", bash("c", "cargo test --test heap"), read("d", "/y")),
                   result(14, "c"), result(20, "d")]
        self.assertEqual(sorted(tt.batches(tt.read_calls(entries))),
                         [("cargo test", 10_000), ("other", 8_000)])

    def test_a_call_over_two_hours_is_left_out(self):
        entries = [prompt(0), reply(1, "m1", bash("a", "cargo test")), result(2, "a"),
                   {**result(0, "z"), "timestamp": "2000-01-01T13:00:00.000Z"}]
        entries.insert(3, reply(3, "m2", {"type": "tool_use", "id": "z", "name": "AskUserQuestion", "input": {}}))
        self.assertEqual(tt.batches(tt.read_calls(entries)), [("cargo test", 1_000)])

    def test_reading_a_background_commands_output_is_waiting_on_it(self):
        out = "/tmp/claude-1/proj/sid/tasks/bx1.output"
        entries = [prompt(0),
                   reply(1, "m1", bash("a", "cargo test --release", run_in_background=True)),
                   result(2, "a", f"Command running in background with ID: bx1. Output is being written to: {out}.",
                          {"backgroundTaskId": "bx1"}),
                   reply(3, "m2", bash("b", f"sleep 60; tail -5 {out}")), result(63, "b"),
                   reply(64, "m3", bash("c", "nohup cargo build > /tmp/build.log 2>&1 &")), result(65, "c"),
                   reply(66, "m4", bash("d", "until grep -q Finished /tmp/build.log; do sleep 5; done")),
                   result(96, "d"),
                   reply(97, "m5", read("e", "/tmp/other.log")), result(98, "e")]
        self.assertEqual(tt.batches(tt.read_calls(entries)),
                         [("cargo test", 1_000), ("waiting on background cargo test", 60_000),
                          ("cargo build", 1_000), ("waiting on background cargo build", 30_000), ("other", 1_000)])


class Cargo(unittest.TestCase):
    def test_timings_per_binary_and_compile(self):
        t = tt.cargo_timings("cargo test", CARGO_OUTPUT)
        self.assertEqual(t["compile_s"], 62.5)
        self.assertEqual(t["binaries"], [("src/lib.rs (unit)", 3.0), ("conformance.rs", 60.5),
                                         ("doc-tests jvmcontract", 0.1)])

    def test_totals_without_running_lines(self):
        line = "test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 9 filtered out; finished in 4.20s"
        self.assertEqual(tt.cargo_timings("cargo test --test heap 2>&1 | grep 'test result'", line)["binaries"],
                         [("heap.rs", 4.2)])
        self.assertEqual(tt.cargo_timings("for t in a b; do cargo test --test $t; done", f"values: {line}")["binaries"],
                         [("values.rs", 4.2)])
        self.assertEqual(tt.cargo_timings("cargo test --test a --test b", line)["binaries"], [(None, 4.2)])

    def test_full_suite(self):
        full = ["cargo test", "cd lib && cargo test -q 2>&1 | tail -30",
                "CARGO_BUILD_JOBS=8 cargo test --manifest-path lib/Cargo.toml",
                "cargo test -- --nocapture --test-threads 4", "cargo test -j 8 > /tmp/t.log; echo $?"]
        partial = ["cargo test --release", "cargo test --test heap", "cargo test --lib", "cargo test heap_",
                   "cargo test -- --ignored", "cargo test -- some_name", "cargo nextest run", "cargo build",
                   "cargo test && cargo test --test heap"]
        for command in full:
            self.assertTrue(tt.full_suite(command), command)
        for command in partial:
            self.assertFalse(tt.full_suite(command), command)


class Sessions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "llm-dlc" / "loops").mkdir(parents=True)
        (self.root / "llm-dlc" / "loop-summaries").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def brief(self, name, sid):
        (self.root / "llm-dlc" / "loops" / f"{name}.md").write_text(f"# Brief\n\n## Loop settings\n\n- session: {sid}\n")

    def store(self, sid, entries, stored=True, url=None):
        data = "".join(json.dumps(e) + "\n" for e in entries).encode()
        sha = hashlib.sha256(data).hexdigest()
        d = self.root / "llm-dlc" / "traces" / sid
        (d / "logs").mkdir(parents=True)
        path = d / "logs" / f"{sha}.jsonl.gz"
        if stored:
            path.write_bytes(gzip.compress(data))
        manifest = {"session_id": sid, "started": "2000-01-01T10:00:00.000Z",
                    "log": {"sha256": sha, "path": str(path.relative_to(self.root))},
                    "logs": {sha: {"url": url} if url else {}}}
        (d / "manifest.json").write_text(json.dumps(manifest))
        return data, sha

    def test_a_codex_sessions_commands_are_the_calls_and_the_tool_that_ran_them_is_not_counted_twice(self):
        def ran(second, end, mid, tid, command, output="ok"):
            block = {"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": command},
                     "codexResult": {"end": at(end), "content": output, "is_error": False}}
            return {"type": "assistant", "timestamp": at(second), "message": {"id": mid, "model": "m", "content": [block]}}

        wrapper = lambda tid: {"type": "tool_use", "id": tid, "name": "exec", "input": {"code": "await tools.exec_command(...)"}}
        entries = [
            prompt(0),
            reply(10, "r1", wrapper("w1")),           # the model's call of the tool
            ran(10, 70, "r1", "c1", "cd lib && cargo test --test heap", CARGO_OUTPUT),
            ran(10, 12, "r1", "c2", "jj status"),     # two commands of one call, side by side
            result(40, "w1", "still running"),        # the tool answers before the long command ends
            reply(80, "r2", wrapper("w2")),           # a call that ran no command: it stays a call
            result(85, "w2"),
        ]
        calls = tt.read_calls(entries)
        self.assertEqual(sorted((c["name"], c["category"], (c["end"] - c["start"]) // 1000) for c in calls),
                         [("Bash", "cargo test", 60), ("Bash", tt.OTHER, 2), ("exec", tt.OTHER, 5)])
        self.assertEqual(sorted(tt.batches(calls)), [("cargo test", 60_000), (tt.OTHER, 5_000)])
        cargo = tt.session_time(SID, entries)["cargo"]  # cargo's own timings are read from the command's kept output
        self.assertEqual((len(cargo), cargo[0]["ms"], cargo[0]["compile_s"], dict(cargo[0]["binaries"])["conformance.rs"]),
                         (1, 60_000, 62.5, 60.5))

    def test_a_codex_log_is_read_as_a_transcript_and_its_thread_stands_for_the_loops_session(self):
        thread = "00000000-0000-7000-8000-00000000000c"
        rollout = [
            {"timestamp": at(0), "type": "session_meta", "payload": {"id": thread, "cwd": "/repo", "cli_version": "0.0"}},
            {"timestamp": at(1), "type": "event_msg", "payload": {"type": "item_completed", "item": {
                "type": "UserMessage", "content": [{"type": "text", "text": "Work on the brief"}]}}},
            {"timestamp": at(5), "type": "response_item", "payload": {"type": "custom_tool_call", "call_id": "w1", "name": "exec",
                                                                    "input": "await tools.exec_command({cmd: 'cargo build'})"}},
            {"timestamp": at(5), "type": "token_usage_record", "payload": {"response_id": "r1", "usage": {"input_tokens": 1, "output_tokens": 1}}},
            {"timestamp": at(35), "type": "event_msg", "payload": {"type": "item_completed", "started_at_ms": 946720805000,
                                                                 "completed_at_ms": 946720835000, "item": {
                "type": "CommandExecution", "id": "c1", "command": ["/bin/bash", "-lc", "cd lib && cargo build"], "exit_code": 0,
                "aggregated_output": "Finished"}}},
            {"timestamp": at(36), "type": "response_item", "payload": {"type": "custom_tool_call_output", "call_id": "w1", "output": "Finished"}},
        ]
        data = "".join(json.dumps(e) + "\n" for e in rollout).encode()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "llm-dlc/loops").mkdir(parents=True)
            (root / "llm-dlc/loops/made-up.md").write_text(f"## Loop settings\n\n- session: {SID}\n")
            (root / "llm-dlc/loop-summaries").mkdir()
            (root / "llm-dlc/loop-summaries/2000-01-01-100000-made-up.md").write_text(
                f"# Feature loop: made-up\n\nStarted 2000-01-01 10:00:00 UTC, 1 cycles, session {SID}, m at high effort.\n\n"
                f"## Commits\n\nCodex thread {thread} carries session {SID}.\n\n")
            traces = root / "llm-dlc/traces" / thread
            (traces / "logs").mkdir(parents=True)
            sha = hashlib.sha256(data).hexdigest()
            (traces / "logs" / f"{sha}.jsonl.gz").write_bytes(gzip.compress(data))
            (traces / "manifest.json").write_text(json.dumps({"log": {"sha256": sha, "path": f"llm-dlc/traces/{thread}/logs/{sha}.jsonl.gz"}}))
            self.assertEqual(tt.discover(root), {SID: "made-up", thread: "made-up"})
            entries = tt.load_entries(root, thread, fetch=False)
        calls = tt.read_calls(entries)
        self.assertEqual([(c["name"], c["category"], c["end"] - c["start"]) for c in calls], [("Bash", "cargo build", 30_000)])

    def test_discover_and_loop_of(self):
        self.brief("foundations", "11111111-1111-4111-8111-111111111111")
        self.brief("foundations-heap", "22222222-2222-4222-8222-222222222222")
        self.brief("application-core", "33333333-3333-4333-8333-333333333333")
        (self.root / "llm-dlc" / "loops" / "foundations-review.md").write_text("# no session\n")
        (self.root / "llm-dlc" / "loop-summaries" / "2000-01-01-043425-application-core-objects.md").write_text(
            "# Feature loop\n\nStarted ..., session 44444444-4444-4444-8444-444444444444, m at high effort.\n")
        found = tt.discover(self.root)
        self.assertEqual(found["44444444-4444-4444-8444-444444444444"], "application-core-objects")
        briefs = set(found.values())
        self.assertEqual({tt.loop_of(b, briefs) for b in found.values()}, {"foundations", "application-core"})
        self.assertEqual(tt.loop_of("stub-reachability", briefs | {"stub-reachability"}), "stub-reachability")

    def test_report_end_to_end(self):
        self.brief("demo", SID)
        self.brief("demo-stream", SID2)
        self.store(SID, [prompt(0), reply(1, "m1", bash("a", "cargo test")), result(31, "a", CARGO_OUTPUT),
                         reply(32, "m2")])
        self.store(SID2, [prompt(0)], stored=False)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tt.main(["--root", str(self.root), "--format", "json"])
        doc = json.loads(out.getvalue())
        self.assertEqual(doc["missing"], [f"demo ({SID2[:8]})"])
        self.assertEqual((doc["sessions"], doc["active_ms"], doc["tool_ms"]), (1, 32_000, 30_000))
        self.assertEqual(doc["by_category"], [{"category": "cargo test", "ms": 30_000, "share": 1.0}])
        self.assertEqual(doc["by_loop"][0]["cargo_test_ms"], 30_000)
        cargo = doc["cargo_test"]
        self.assertEqual((cargo["calls"], cargo["timed_calls"], cargo["compile_s"]), (1, 1, 62.5))
        self.assertEqual(cargo["full_suite"]["calls"], 1)
        self.assertEqual(cargo["by_binary"][0]["binary"], "conformance.rs")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tt.main(["--root", str(self.root), "--loop", "other"])
        self.assertIn("0 sessions in 0 loops", out.getvalue())

    def test_fetch_checks_the_content_against_its_name(self):
        served = self.root / "served.jsonl.gz"
        data, sha = self.store(SID, [prompt(0)], stored=False, url=served.as_uri())
        cache = self.root / "cache"
        served.write_bytes(gzip.compress(data + b"{}\n"))
        with self.assertRaises(ValueError):
            tt.load_entries(self.root, SID, True, cache)
        self.assertIsNone(tt.load_entries(self.root, SID, False, cache))
        served.write_bytes(gzip.compress(data))
        self.assertEqual(len(tt.load_entries(self.root, SID, True, cache)), 1)
        self.assertTrue((cache / SID / f"{sha}.jsonl.gz").exists())
        served.unlink()
        self.assertEqual(len(tt.load_entries(self.root, SID, False, cache)), 1)


if __name__ == "__main__":
    unittest.main()
