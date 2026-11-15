#!/usr/bin/env python3
"""Review item 5 of llm-dlc/loops/example-targets.md (the user's review, 2026-11-15): a target receipt bundles the raw
streams. Ingestion copies each record's stdout and stderr and the runner's record (controls.json, verifier.json) into
the receipt's records/, each hashed and capped in size, with records/streams.json saying what each copy is, and a
not-started record says why it didn't start (287's guard tasks, whose adapter doesn't call their target).

On a copy of Phase 0's fixture, with the fixture's controls run for real by runtime.run_controls on JDK 21 and 25
(skipped without both); the verifier record of the proof task is constructed, as no proof runs inline.

  cd examples/tools/targets && python3 -m unittest -q test_receipt_streams
"""

import dataclasses
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from targets import interfaces, runtime, runtime_jdk, workflow, workflow_ingest  # noqa: E402

FIXTURES = HERE / "fixtures"


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ReceiptStreamsTest(unittest.TestCase):
    def setUp(self):
        if not {"21", "25"} <= set(runtime_jdk.homes()):
            self.skipTest(f"JDKs 21 and 25 are not both under {runtime_jdk.CANDIDATES}")
        self.dir = Path(tempfile.mkdtemp(prefix="test-receipt-streams-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.folder = self.dir / "999-fixture"
        shutil.copytree(FIXTURES, self.folder, ignore=shutil.ignore_patterns("__pycache__", "records", "results"))
        self.example = json.loads((self.folder / "example.json").read_text())
        self.target = json.loads((self.folder / "target.json").read_text())
        self.attempt = self.dir / "attempt"

    def plan(self, task):
        plan = workflow.plan_task(self.folder, self.example, self.target, task)
        self.assertIsInstance(plan, interfaces.TaskPlan, getattr(plan, "reason", plan))
        return plan

    def prepared(self, plan):
        out = {r: runtime.prepare(plan, r, self.attempt / "prepare" / r) for r in plan.revisions}
        for p in out.values():
            self.assertEqual(p.stage, "artifacts-ready", p.diagnostic)
        return out

    def published(self, plan, prepared, records):
        receipt = workflow.ingest(plan, prepared, records, self.folder / plan.outputs["receipts"])
        self.assertIsInstance(receipt, interfaces.Receipt, getattr(receipt, "reason", receipt))
        where = (self.folder / receipt.path).parent
        import result_format
        document = result_format.view(json.loads((where / "result.json").read_text()))
        return where, document

    def bundled(self, where, document):
        return {a["path"]: a for a in document["bundle"]["artifacts"]}

    def test_a_replay_receipt_bundles_each_controls_streams_and_controls_json_hashed(self):
        plan = self.plan("replay")
        prepared = self.prepared(plan)
        records = runtime.run_controls(plan, prepared, self.attempt / "controls")
        self.assertEqual({r.status for r in records}, {"exited"})
        for r in records:
            self.assertEqual((r.directory, r.record, r.reason), (str(self.attempt), "controls/controls.json", None))
        where, document = self.published(plan, prepared, records)
        bundle = self.bundled(where, document)
        streams = json.loads((where / "records/streams.json").read_text())["streams"]
        self.assertIn("records/streams.json", bundle)
        stages = document["attempt"]["stages"]
        self.assertEqual(len(stages), len(records))
        for stage, r in zip(stages, records):
            for name in ("stdout", "stderr"):
                original = (self.attempt / getattr(r, name)).read_bytes()
                kept = stage[name]
                self.assertTrue(kept.startswith("records/"), f"{stage['name']}'s {name} is not bundled: {kept}")
                self.assertIn(kept, bundle)
                self.assertEqual((where / kept).read_bytes(), original)
                entry = next(s for s in streams if s["kept"] == kept)
                self.assertEqual((entry["source"], entry["stage"], entry["stream"]), (getattr(r, name), stage["name"], name))
                self.assertEqual((entry["bytes"], entry["sha256"], entry["truncated"]),
                                 (len(original), sha(original), False))
            self.assertNotIn("reason", stage, "an exited record has no reason not to have started")
        self.assertGreater(sum(len((where / s["stdout"]).read_bytes()) for s in stages), 0)
        controls = (self.attempt / "controls/controls.json").read_bytes()
        self.assertEqual((where / "records/controls.json").read_bytes(), controls)
        entry = next(s for s in streams if s["kept"] == "records/controls.json")
        self.assertEqual((entry["source"], entry["stream"], entry["sha256"]), ("controls/controls.json", "record",
                                                                                sha(controls)))
        # The attempt's directory is a temporary path: it is how ingestion finds the files, never part of the receipt.
        for name in ("result.json", "records/execution.json", "records/streams.json"):
            self.assertNotIn(str(self.attempt), (where / name).read_text(), name)
        self.assertEqual(document["matchesExpected"], True, document["verdictLabel"])

    def test_a_not_started_control_states_why_in_the_receipt(self):
        source = self.folder / "gate/adapter/fixture/adapter/GateAdapter.java"
        source.write_text(source.read_text().replace("return Gate.allowed(code);", "return code != 65 && code != 97;")
                          .replace("import fixture.Gate;\n", ""))
        plan = self.plan("fixed-security")
        prepared = self.prepared(plan)
        self.assertIs(prepared["after"].source["target"]["adapterCallsTarget"], False)
        controls = runtime.run_controls(plan, prepared, self.attempt / "controls")
        self.assertEqual({r.status for r in controls}, {"not-started"})
        for r in controls:
            self.assertIn("doesn't call the task's target", r.reason)
            self.assertIn(r.reason, (self.attempt / r.stderr).read_text())
        verifier_dir = self.attempt / "verifier"
        verifier_dir.mkdir()
        (verifier_dir / "verifier.stdout").write_text("")
        (verifier_dir / "verifier.stderr").write_text("runtime: not started: the test's verifier\n")
        verifier = interfaces.ExecutionRecord(
            kind="verifier", revision="after", argv=(), status="not-started", exitCode=None, seconds=0.0,
            stdout="verifier/verifier.stdout", stderr="verifier/verifier.stderr", identities={"jvmcontract": "0" * 64},
            directory=str(self.attempt), reason="the test's verifier")
        where, document = self.published(plan, prepared, (*controls, verifier))
        stages = document["attempt"]["stages"]
        for stage, r in zip(stages, controls):
            self.assertEqual(stage["status"], "not-started")
            self.assertEqual(stage["reason"], r.reason)
            self.assertIn(r.reason, (where / stage["stderr"]).read_text())
        self.assertEqual(stages[-1]["reason"], "the test's verifier")
        self.assertIn("the test's verifier", document["execution"]["reason"])
        logged = json.loads((where / "records/controls.json").read_text())["records"]
        self.assertTrue(all("doesn't call the task's target" in e["log"]["problem"] for e in logged))
        entries = json.loads((where / "records/execution.json").read_text())["records"]
        self.assertEqual([e["reason"] for e in entries], [r.reason for r in (*controls, verifier)])
        self.assertTrue(all("directory" not in e for e in entries), "the attempt's directory stays out of the receipt")

    def test_a_stream_over_the_cap_is_kept_truncated_with_the_whole_streams_size_and_hash(self):
        plan = self.plan("replay")
        prepared = self.prepared(plan)
        records = runtime.run_controls(plan, prepared, self.attempt / "controls")
        with mock.patch.object(workflow_ingest, "STREAM_CAP", 40):
            where, document = self.published(plan, prepared, records)
        streams = json.loads((where / "records/streams.json").read_text())
        self.assertEqual(streams["cap"], 40)
        for entry in streams["streams"]:
            whole = (self.attempt / entry["source"]).read_bytes()
            kept = (where / entry["kept"]).read_bytes()
            self.assertEqual(kept, whole[:40])
            self.assertEqual((entry["bytes"], entry["sha256"], entry["keptBytes"], entry["truncated"]),
                             (len(whole), sha(whole), len(kept), len(whole) > 40))
        self.assertTrue(any(e["truncated"] for e in streams["streams"]))

    def test_a_record_naming_no_directory_or_a_missing_stream_bundles_nothing_and_says_why(self):
        plan = self.plan("replay")
        prepared = self.prepared(plan)
        records = runtime.run_controls(plan, prepared, self.attempt / "controls")
        (self.attempt / records[0].stderr).unlink()
        changed = (dataclasses.replace(records[0]), dataclasses.replace(records[1], directory=None), *records[2:])
        where, document = self.published(plan, prepared, changed)
        streams = json.loads((where / "records/streams.json").read_text())["streams"]
        stages = document["attempt"]["stages"]
        self.assertEqual(stages[0]["stderr"], records[0].stderr, "a missing stream keeps its path, not bundled")
        self.assertEqual((stages[1]["stdout"], stages[1]["stderr"]), (records[1].stdout, records[1].stderr))
        missing = next(s for s in streams if s["source"] == records[0].stderr)
        self.assertEqual(missing["kept"], None)
        self.assertIn("no such file", missing["why"])
        unnamed = [s for s in streams if s["stage"] == stages[1]["name"]]
        self.assertEqual([(s["kept"], s["why"]) for s in unnamed],
                         [(None, workflow_ingest.NO_DIRECTORY)] * 2)
        self.assertTrue(stages[2]["stdout"].startswith("records/"))
        # The check a job runs on a real receipt says which streams are missing, and exits 1.
        import receipt_streams
        lines, found = receipt_streams.problems(where)
        self.assertEqual(len(found), 3, found)
        self.assertIn(workflow_ingest.NO_DIRECTORY, " ".join(found))
        self.assertIn("no such file", " ".join(found))

    def test_the_jobs_check_passes_on_a_bundled_receipt_and_reads_a_not_started_reason(self):
        import contextlib
        import io
        import receipt_streams
        plan = self.plan("replay")
        prepared = self.prepared(plan)
        where, _ = self.published(plan, prepared, runtime.run_controls(plan, prepared, self.attempt / "controls"))

        def check(*argv):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = receipt_streams.main(list(argv))
            return code, out.getvalue()

        code, said = check(str(where))
        self.assertEqual(code, 0, said)
        self.assertIn("records/controls.json", said)
        self.assertEqual(check(str(self.folder), "replay"), (code, said), "the task's latest receipt")
        self.assertEqual(check(str(where), "--reason", "anything")[0], 1, "no stage is not-started")
        (where / "records/streams.json").unlink()
        self.assertEqual(check(str(where))[0], 1)


if __name__ == "__main__":
    unittest.main()
