"""workflow_refusal.py: a rerun of a task an observed gap blocks passes only at the refusal its packet recorded, and
the 19 open packets of VF-027 and the 2 of VF-028 state exactly what their jobs observed, under the claims as they are
now; example 285's four, closed by the receipts that decided its claims, keep what was observed and block nothing."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent.parent
ROOT = EXAMPLES.parent
sys.path.insert(0, str(HERE.parent))
from targets import sidecar, workflow, workflow_handoff, workflow_refusal  # noqa: E402

TEXT = "parameter request has type X, which is outside the objects a property check makes"
CLOSURES = ("before and after have different dependency closures, and jvmcontract's equivalence takes one classpath "
            "for both")


def prediction(stage="verifier", text=TEXT, key="k1"):
    return {"packet": "records/refusals/t.json", "kind": "input-construction", "finding": "VF-027", "stage": stage,
            "text": text, "claimKey": key}


def receipt(status="unresolved", execution="completed", problem=TEXT, path="receipts/t/a"):
    return {"path": path, "status": status, "execution": execution, "problem": problem, "claim": "c"}


class JudgeTest(unittest.TestCase):
    def test_the_recorded_refusal_on_the_same_claim_passes(self):
        ok, how = workflow_refusal.judge(prediction(), "k1", 1, ["x: task t: unresolved (completed; NOT AS EXPECTED "
                                                                   "(refuted)), receipt receipts/t/a/result.json"],
                                         [receipt()])
        self.assertTrue(ok, how)
        ok, how = workflow_refusal.judge(prediction("run-verifier", CLOSURES), "k1", 1,
                                         [f"285-x: not-executed (task t: unsupported: run-verifier: {CLOSURES})"], [])
        self.assertTrue(ok, how)

    def test_anything_else_fails_with_what_differed(self):
        cases = {
            "a verdict": (prediction(), "k1", 1, [receipt(status="refuted")], "concludes refuted"),
            "an established verdict": (prediction(), "k1", 0, [receipt(status="established")], "exited 0"),
            "another refusal": (prediction(), "k1", 1, [receipt(problem="the receiver ...")], "another refusal"),
            "a killed attempt": (prediction(), "k1", 1, [receipt(execution="killed")], "is killed"),
            "no receipt": (prediction(), "k1", 1, [], "0 new receipts"),
            "two receipts": (prediction(), "k1", 1, [receipt(), receipt(path="receipts/t/b")], "2 new receipts"),
            "a changed claim": (prediction(), "k2", 1, [receipt()], "claim key is k2"),
            "a crash": (prediction(), "k1", 2, [receipt()], "exited 2"),
            "a run where the route refused nothing": (prediction("run-verifier", CLOSURES), "k1", 1, [receipt()],
                                                      "the verifier ran"),
        }
        for name, (p, key, code, receipts, words) in cases.items():
            with self.subTest(name):
                ok, how = workflow_refusal.judge(p, key, code, [], receipts)
                self.assertFalse(ok)
                self.assertIn(words, how)
        ok, how = workflow_refusal.judge(prediction("run-verifier", CLOSURES), "k1", 1,
                                         ["285-x: not-executed (task t: the task doesn't plan)"], [])
        self.assertFalse(ok)
        self.assertIn("another reason", how)


class PredictionsTest(unittest.TestCase):
    def target(self, packet="records/refusals/t.json", observed=True):
        return {"handoff": {"blockers": [{"kind": "input-construction", "observed": observed, "task": "t",
                                          "summary": "s", "packet": packet, "finding": "VF-027"}]}}

    def test_an_observed_blocker_whose_packet_states_a_refusal_predicts_it_and_nothing_else_does(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "records/refusals").mkdir(parents=True)
            path = folder / "records/refusals/t.json"
            path.write_text(json.dumps({"refusal": {"stage": "verifier", "text": TEXT}, "claimKey": "k1"}))
            [p] = workflow_refusal.predictions(folder, self.target(), "t")
            self.assertEqual((p["stage"], p["text"], p["claimKey"], p["finding"]), ("verifier", TEXT, "k1", "VF-027"))
            self.assertEqual(workflow_refusal.predictions(folder, self.target(), "other"), [])
            self.assertEqual(workflow_refusal.predictions(folder, self.target(observed=False), "t"), [])
            path.write_text(json.dumps({"diagnostic": []}))
            self.assertEqual(workflow_refusal.predictions(folder, self.target(), "t"), [])
            for bad in ({"refusal": {"stage": "proof", "text": TEXT}, "claimKey": "k1"},
                        {"refusal": {"stage": "verifier", "text": ""}, "claimKey": "k1"},
                        {"refusal": {"stage": "verifier", "text": TEXT}}):
                with self.subTest(bad=bad):
                    path.write_text(json.dumps(bad))
                    with self.assertRaises(workflow_refusal.PredictionError):
                        workflow_refusal.predictions(folder, self.target(), "t")


def load(number):
    folder = next(EXAMPLES.glob(f"{number}-*"))
    example = json.loads((folder / "example.json").read_text())
    return folder, example, sidecar.load(folder, example)


class CheckTest(unittest.TestCase):
    def test_a_rerun_of_286s_preservation_passes_only_at_its_recorded_closure_refusal(self):
        folder, example, target = load("286")
        line = f"{folder.name}: not-executed (task preservation: unsupported: run-verifier: the task can't be " \
               f"attempted as stated: {CLOSURES})"
        ok, said = workflow_refusal.check(folder, example, target, "preservation", lambda: (1, [line]))
        self.assertTrue(ok, said)
        self.assertTrue(said.startswith(f"{folder.name}: task preservation: refused as predicted (VF-027; "
                                        "run-verifier; records/refusals/preservation.json)"), said)
        ok, said = workflow_refusal.check(folder, example, target, "preservation", lambda: (0, ["as expected"]))
        self.assertFalse(ok)
        self.assertIn("NOT AS PREDICTED", said)

    def test_a_rerun_of_286s_vulnerable_security_reads_the_one_receipt_it_wrote(self):
        folder, example, target = load("286")
        packet = json.loads((folder / "records/refusals/vulnerable-security.json").read_text())
        before = workflow_refusal.receipt_dirs(folder, "vulnerable-security")
        new = {"path": "receipts/vulnerable-security/new", "status": "unresolved", "execution": "completed",
               "problem": packet["refusal"]["text"], "claim": "c"}
        with mock.patch.object(workflow_refusal, "receipt_dirs", side_effect=[before, before | {"new"}]), \
                mock.patch.object(workflow_refusal, "read_receipt", return_value=new):
            ok, said = workflow_refusal.check(folder, example, target, "vulnerable-security", lambda: (1, []))
        self.assertTrue(ok, said)
        with mock.patch.object(workflow_refusal, "receipt_dirs", side_effect=[before, before | {"new"}]), \
                mock.patch.object(workflow_refusal, "read_receipt", return_value={**new, "status": "refuted"}):
            ok, said = workflow_refusal.check(folder, example, target, "vulnerable-security", lambda: (1, []))
        self.assertFalse(ok)
        self.assertIn("a verdict, not the refusal", said)


# VF-027's tasks still blocked, each with the job that observed its refusal (the user's decision of 2026-11-15):
# 19 of its 23, example 285's four being closed (CLOSED, below).
VF027 = {
    "286": ("vulnerable-security", "fixed-security", "mutant-security", "vulnerable-protected-state-mutation",
            "fixed-protected-state-mutation", "preservation"),
    "287": ("vulnerable-security", "fixed-security", "mutant-security", "vulnerable-guard", "fixed-guard",
            "preservation"),
    "305": ("finite-outcome-before", "finite-outcome-after", "preservation", "mutant-preservation"),
    "306": ("preservation", "mutant-preservation"),
    "105": ("confined-change",),
}
# VF-028's 2 tasks, recorded the same way (example 307's native attempts, collected after VF-027 closed).
VF028 = {"307": ("preservation", "mutant-preservation")}
OBSERVED = [("VF-027", VF027), ("VF-028", VF028)]
# Closed gaps: each task's unchanged claim, rerun with the extended checker, decided by a receipt as expected.
CLOSED = {"285": {"vulnerable-security": "refuted", "fixed-security": "established", "mutant-security": "refuted",
                  "preservation": "established"}}


class Vf027PacketsTest(unittest.TestCase):
    def test_each_of_the_21_tasks_is_blocked_by_its_observed_refusal_as_its_job_recorded_it(self):
        count = 0
        for finding, number, tasks in ((f, n, ts) for f, rows in OBSERVED for n, ts in rows.items()):
            folder, example, target = load(number)
            for task in tasks:
                with self.subTest(example=number, task=task):
                    count += 1
                    [p] = workflow_refusal.predictions(folder, target, task)
                    self.assertEqual(p["finding"], finding)
                    packet = json.loads((folder / p["packet"]).read_text())
                    plan = workflow.plan_task(folder, example, target, task)
                    self.assertEqual(packet["claimKey"], plan.claim["key"], "the claim changed since the job")
                    seen = packet["observed"]
                    log = ROOT / seen["log"]
                    self.assertEqual(workflow.file_sha256(log), seen["logSha256"])
                    job = json.loads((ROOT / seen["result"]).read_text())
                    self.assertEqual(job["steps"][0]["run"], f"python3 examples/tools/build.py {number} --task {task}")
                    self.assertEqual(job["status"], "failed")
                    if p["stage"] == "verifier":
                        out = ROOT / seen["verifierOutput"]
                        self.assertEqual(workflow.file_sha256(out), seen["verifierOutputSha256"])
                        self.assertIn(f"cannot be verified: {p['text']}", out.read_text())
                        raw = json.loads((ROOT / seen["receipt"]).read_text())
                        self.assertEqual((raw["conclusion"]["status"], raw["evidence"]["problem"]),
                                         ("unresolved", p["text"]))
                    else:
                        self.assertIsNone(seen["receipt"])
                        self.assertIn(p["text"], seen["line"])
                        self.assertIn(seen["line"], log.read_text())
                    readiness = workflow.task_readiness(folder, example, target, task)
                    self.assertEqual(readiness["summary"], "blocked")
                    t = next(x for x in target["tasks"] if x["id"] == task)
                    self.assertIn(t.get("expected"), ("established", "refuted"), "the expectation is unchanged")
        self.assertEqual(count, 21)

    def test_each_blocked_tasks_handoff_next_is_its_refusal_check_with_its_gap_id_and_closure_test(self):
        """Item 1 of the user's review of 2026-11-15: an ordinary attempt (pipeline.py submit) at a task an observed
        refusal blocks ends NOT AS EXPECTED, so the handoff's next is the check that reruns the refusal, naming the
        gap id of the inventory and its closure test."""
        count = 0
        for number, tasks in ((n, ts) for _, rows in OBSERVED for n, ts in rows.items()):
            folder, example, target = load(number)
            for task in tasks:
                with self.subTest(example=number, task=task):
                    count += 1
                    value = workflow_handoff.packet(folder, example, target, task)
                    self.assertEqual(value["next"],
                                     f"python3 examples/tools/targets/workflow_refusal.py {number} {task}")
                    [p] = workflow_refusal.predictions(folder, target, task)
                    [gap] = [g for g in value["gaps"] if (g.get("packet") or {}).get("file") == p["packet"]]
                    [gap_id] = workflow_handoff.gap_ids(gap)
                    reason = value["nextReason"]
                    self.assertIn(gap_id, reason)
                    self.assertIn("examples/gap-inventory.md", reason)
                    self.assertIn(gap["packet"]["closure"]["check"], reason)
                    self.assertIn(value["plan"]["claim"]["key"], reason)
                    self.assertNotIn("pipeline.py submit", value["next"])
        self.assertEqual(count, 21)

    def test_a_closed_gap_blocks_nothing_and_its_packet_names_the_receipt_that_decided_the_claim(self):
        """A gap closes by its packet's own test (workflow_handoff.py): the unchanged claim rerun on the same
        artifacts with the extended checker, its receipt deciding it as expected, not vacuous. Then the sidecar lists
        no blocker for the task, nothing predicts a refusal, the task is executable with that receipt current, and the
        packet keeps the refusal as observed, with `closed` naming the job and the receipt."""
        for number, tasks in CLOSED.items():
            folder, example, target = load(number)
            self.assertEqual(target["handoff"]["blockers"], [])
            for task, status in tasks.items():
                with self.subTest(example=number, task=task):
                    self.assertEqual(workflow_refusal.predictions(folder, target, task), [])
                    self.assertEqual(next(t for t in target["tasks"] if t["id"] == task)["expected"], status)
                    packet = json.loads((folder / "records/refusals" / f"{task}.json").read_text())
                    plan = workflow.plan_task(folder, example, target, task)
                    self.assertEqual(packet["claimKey"], plan.claim["key"], "the claim is the one that was refused")
                    self.assertTrue(packet["refusal"]["text"])
                    closed = packet["closed"]
                    self.assertEqual(json.loads((ROOT / closed["result"]).read_text())["status"], "passed")
                    receipt = json.loads((folder / closed["receipt"]).read_text())
                    conclusion = receipt["conclusion"]
                    self.assertEqual((conclusion["status"], conclusion["expectation"], conclusion["vacuous"]),
                                     (status, "yes", False))
                    self.assertEqual(closed["status"], status)
                    self.assertEqual(receipt["claim"]["statement"]["claim"]["key"], packet["claimKey"])
                    self.assertEqual(receipt["attempt"]["engine"], "native")
                    value = workflow_handoff.packet(folder, example, target, task)
                    self.assertEqual(value["readiness"]["summary"], "executable")
                    self.assertEqual(value["gaps"], [])
                    self.assertIn(closed["receipt"], [r["path"] for r in value["receipts"]])
                    self.assertNotIn("workflow_refusal.py", value["next"])

    def test_the_inventory_ranks_the_five_observed_causes(self):
        rows = [load(n) for n in (*VF027, *VF028)]
        observed = {g["gap"]: g for g in workflow_handoff.inventory(rows)["gaps"] if g["observed"]}
        self.assertEqual(set(observed), {
            "input-construction:interface-parameter", "input-construction:receiver-of-several-constructors",
            "input-construction:string-parameter", "verifier-interface:two-dependency-closures",
            "jdk-constructor:java.lang.StringBuilder.<init>()V"})
        self.assertEqual(sum(g["blockedObligations"] for g in observed.values()), 21)
        self.assertEqual(observed["input-construction:string-parameter"]["blockedObligations"], 5)


if __name__ == "__main__":
    unittest.main()
