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

import changes
import conductor
import decisions
import watch
from test_changes import PROOFS, Checkout

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

    def test_an_existing_session_can_be_taken_as_the_fixed_one(self):
        earlier = "0f0f0f0f-made-up-moonshot-session"
        with self.assertRaises(SystemExit, msg="a session with no transcript here is refused"):
            self.call("session", "--use", earlier)
        watch.transcript(self.root, earlier).parent.mkdir(parents=True)
        watch.transcript(self.root, earlier).write_text("{}\n")
        self.assertEqual(self.call("session", "--use", earlier)[1].strip(), earlier)
        self.assertEqual(self.call("session")[1].strip(), earlier)


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


class PreflightTest(Checkout):
    """Examples that are already prepared, checked before a loop takes them: copies of the made-up target fixture."""

    def check(self, *numbers):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            status = watch.main(["--root", str(self.root), "preflight", *numbers])
        found = json.loads(out.getvalue())
        return status, found, {e["id"]: e for e in found["examples"]}

    def test_prepared_examples_pass_in_the_order_given_and_a_decided_one_is_left_out_of_the_loop(self):
        self.example("901")
        self.example("900", answers={**PROOFS, "regex-probe": "refuted"})
        self.example("902", answers=PROOFS)
        status, found, _ = self.check("902", "900", "901", "902")
        self.assertEqual((status, found["ok"], found["toProve"], found["decided"]), (0, True, ["902", "901"], ["900"]))

    def test_a_missing_artifact_and_a_fault_in_the_form_are_told_apart(self):
        self.example("900", replays=False)
        (self.example("901") / "target.json").write_text("{ not JSON")
        self.example("902")
        status, found, by = self.check("900", "901", "902")
        self.assertEqual((status, found["ok"], found["toProve"]), (1, False, ["902"]))
        self.assertTrue(by["900"]["artifacts"] and not by["900"]["form"], by["900"])
        self.assertTrue(by["901"]["form"] and not by["901"]["artifacts"], by["901"])
        self.assertTrue(by["902"]["ok"])

    def test_an_example_that_is_not_there_is_said_apart_since_nothing_can_put_it_right(self):
        self.example("900")
        status, found, by = self.check("900", "950")
        self.assertEqual((status, found["absent"], by["950"]["ok"]), (2, ["950"], False))

    def test_a_catalog_entry_is_to_set_up_and_one_still_lacking_after_its_setup_is_left_out(self):
        self.example("900")
        self.catalog_entry("901")
        self.example("902", replays=False)
        status, found, by = self.check("900", "901")
        self.assertEqual((status, found["toSetUp"], found["toRepair"], found["toProve"]), (1, ["901"], [], ["900"]))
        self.assertEqual([g["kind"] for g in by["901"]["catalogue"]], [changes.CATALOGUE])
        status, found, _ = self.check("--after-setup", "901", "900", "901")
        self.assertEqual((status, found["ok"], found["leftOut"], found["toSetUp"], found["toProve"]),
                         (0, True, ["901"], [], ["900"]), "the others go on without it")
        status, found, _ = self.check("--after-setup", "901", "900", "901", "902")
        self.assertEqual((status, found["leftOut"], found["toRepair"]), (1, ["901"], ["902"]),
                         "an example that was prepared and lacks something still stops the run")
        self.assertEqual(self.check("--after-setup", "950", "900", "950")[0], 2, "one that is not there is never left out")

    def test_claims_lists_each_claim_once_with_the_answer_expected_on_each_revision(self):
        self.example("900")
        self.catalog_entry("901")
        found = {e["id"]: e for e in watch.claims(watch.Run(self.root), ["900", "901"])}
        by_file = {c["file"]: c for c in found["900"]["claims"]}
        self.assertEqual(sorted(by_file), ["claims/gate-preservation.json", "claims/gate-security.json", "claims/regex-probe.json"])
        self.assertEqual([(t["task"], t["expected"]) for t in by_file["claims/gate-security.json"]["tasks"]],
                         [("vulnerable-security", "refuted"), ("fixed-security", "established"), ("mutant-security", "refuted")])
        self.assertTrue(all(c["statement"] for c in by_file.values()), "each in its claim file's own words")
        self.assertEqual((found["901"]["state"], found["901"]["claims"]), ("catalogued", []))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(watch.main(["--root", str(self.root), "claims", "900", "901"]), 0)
        self.assertIn(by_file["claims/gate-security.json"]["statement"], out.getvalue())
        self.assertIn("expected established on after (task fixed-security)", out.getvalue())
        self.assertIn("No claim: the example is catalogued.", out.getvalue())

    def test_claims_the_watcher_accepts_with_the_user_away_are_decisions_flagged_for_their_review(self):
        self.example("900")
        self.catalog_entry("901")
        run, err = watch.Run(self.root), io.StringIO()
        with mock.patch.dict(os.environ, {"IN_THE_LOOP_MODE": "development"}), contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(err):
                self.assertEqual(watch.main(["--root", str(self.root), "claims", "900", "901", "--accept", "as the advisory says"]), 1)
            self.assertIn("901: it states no claim", err.getvalue())
            self.assertFalse((self.root / "llm-dlc/decisions").exists(), "one example that can't be accepted, and none is")
            self.assertEqual(watch.main(["--root", str(self.root), "claims", "900", "--accept", "as the advisory says"]), 0)
        (line,) = decisions.fold(decisions.read("prove-change", self.root / "llm-dlc/decisions")).values()
        self.assertEqual((line["decision"]["option"], line["decision"]["by"], line["decision"]["rationale"]),
                         ("accept", "conductor", "as the advisory says"))
        self.assertEqual(line["review"], {"state": "flagged", "why": "costly"}, "the hours go to these claims: the user reads them")
        folder = next((run.root / "examples").glob("900-*")).relative_to(run.root)
        self.assertEqual(line["context"]["files"], [f"{folder}/claims/{c}.json" for c in ("gate-preservation", "gate-security", "regex-probe")])
        self.assertIn("example 900", line["asked"]["question"])

    def test_an_example_json_that_breaks_its_schema_is_a_fault_in_the_form(self):
        folder = self.example("900")
        (self.root / "examples/schema").mkdir()
        (self.root / "examples/schema/example.schema.json").write_text((REPO / "examples/schema/example.schema.json").read_text())
        self.assertEqual(self.check("900")[0], 0, "the fixture's example.json is valid")
        example = json.loads((folder / "example.json").read_text())
        del example["title"]
        (folder / "example.json").write_text(json.dumps(example))
        status, _, by = self.check("900")
        self.assertEqual(status, 1)
        self.assertTrue(any("title" in g["what"] for g in by["900"]["form"]), by["900"])

    def test_an_example_without_a_sidecar_passes_with_a_note(self):
        folder = self.example("900")
        (folder / "target.json").unlink()
        example = json.loads((folder / "example.json").read_text())
        example.pop("target", None)
        (folder / "example.json").write_text(json.dumps(example))
        status, found, by = self.check("900")
        self.assertEqual((status, found["toProve"], by["900"]["state"]), (0, ["900"], "unknown"))
        self.assertIn("no target sidecar", by["900"]["note"])


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
        self.assertEqual({"verdict", "next", "besideRoute", "blocked"} - thing["assessment"].keys(), set(),
                         "the example's own word on its outcome, and which claims were answered beside the route or stop at a gap")

    def test_the_summary_says_which_answers_the_user_overturned_or_is_asked_to_review(self):
        for n, confidence in ((1, "high"), (2, "medium")):
            self.note("cycle", needsVerdict=True, answers=["finished", "continue", "waiting"], deadline=time.time() + 300,
                      cycle=n, item="901", itemCycle=n)
            with contextlib.redirect_stdout(io.StringIO()):
                conductor.cmd_decide(self.run.dir, n, "continue", "a claim is open", confidence)
        records = self.root / "llm-dlc/decisions"
        with contextlib.redirect_stdout(io.StringIO()):
            decisions.main(["review", "overturn", "prove-change-D001", "--note", "it was finished"], root=records)
        found = watch.state(self.run)["decisions"]
        self.assertEqual(found, {"record": "prove-change", "flagged": 1, "unreviewed": 0, "overturned": ["prove-change-D001"]})
        out = self.call("summary")[1]
        self.assertIn("the user overturned prove-change-D001", out)
        self.assertIn("1 of the watcher's answers are flagged", out)

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
        window = subprocess.Popen(["bash", "-c", "sleep 30; : llm-dlc/tools/verification-loop.sh ended"], cwd=self.root)
        self.addCleanup(window.wait)
        self.addCleanup(window.kill)
        self.assertIn("not running", self.call("verification", "status")[1],
                      "a shell that only mentions the script, as the window a loop ended in does, is not the loop")
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
        log.unlink()
        given = ["--memory", "12G", "--record-as", "prove-examples", "--wait-for-proofs", "--instruction", "Prove {} briefly", "902"]
        self.assertEqual(self.call("loop", *given)[0], 0)
        until = time.time() + 10
        while not log.exists() and time.time() < until:
            time.sleep(0.05)
        self.assertEqual(log.read_text().strip(), f"--session {session} " + " ".join(given), "every option beside its value")
        self.loop("902", "900")  # a run under way, as prove-loop.sh records it
        self.assertEqual(self.call("loop", "902")[0], 1)


if __name__ == "__main__":
    unittest.main()
