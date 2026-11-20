"""Claim-level handoffs on the two historical packets, through the public command."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE.parents[2] / "lib/tools"))
from cost_tier import cost
sys.path.append(str(Path(__file__).resolve().parents[3] / "lib/tools"))
from cost_tier import cost  # noqa: E402


def handoff(*args):
    result = subprocess.run([sys.executable, str(HERE / "workflow_handoff.py"), "handoff", *args],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


class ClaimHistoryTest(unittest.TestCase):
    @cost("tool")
    def test_exhaustive_routes_keep_the_native_diagnostic_and_the_interrupted_history(self):
        history = handoff("315", "--claim", "claims/round-trip.json", "--revision", "fix")
        self.assertEqual(history["coverage"]["exhaustiveJvm"], {"established": 1, "refuted": 0, "open": 0, "disputed": 0})
        proofs = history["claims"][0]["subjects"][0]["finiteJvm"]
        self.assertTrue(any(r["retryOf"] and any(p["batch"] == r["retryOf"] for p in proofs) for r in proofs))
        parser = handoff("315", "--claim", "claims/parse.json", "--revision", "parent")["claims"][0]["subjects"][0]
        self.assertEqual(parser["overallConclusion"], "refuted")
        self.assertTrue(any("Matcher.group" in (e.get("firstBlocker") or "") for e in parser["executions"]))
        sys.path.insert(0, str(HERE.parent))
        from targets.claim_history import disposition
        self.assertEqual(disposition({"ineligible", "open", "refuted"}), "refuted")
        self.assertEqual(disposition({"established", "refuted"}), "disputed")

    @cost("tool")
    def test_286_groups_shared_claims_and_keeps_the_subjects_and_replays(self):
        history = handoff("286")
        claims = {c["file"]: c for c in history["claims"]}
        decision = claims["claims/disallowed-field-denied-ignoring-case.json"]
        subjects = {s["task"]: s for s in decision["subjects"]}
        self.assertEqual([subjects[t]["revisions"] for t in ("vulnerable-security", "fixed-security", "mutant-security")],
                         [["vulnerable-release"], ["fixed-release"], ["mutant"]])
        self.assertTrue({"claims/permitted-fields-preserved.json", "claims/protected-age-not-mutated.json"} <= claims.keys())
        self.assertTrue({"replay", "mutant-replay"} <= {r["task"] for r in history["replays"]})
        selected = handoff("286", "--claim", decision["claimKey"], "--revision", "fixed-release")
        self.assertEqual([s["task"] for c in selected["claims"] for s in c["subjects"]], ["fixed-security"])
        original = handoff("286", "fixed-security")
        self.assertEqual({r["path"] for r in subjects["fixed-security"]["receipts"]},
                         {r["path"] for r in original["receipts"] + original["staleReceipts"]})

    @cost("tool")
    def test_288_trials_link_back_to_the_open_frozen_claim(self):
        history = handoff("288", "--claim", "claims/permitted-fields-preserved.json")
        task = history["claims"][0]["subjects"][0]
        probe = next(p for p in task["historicalProbes"] if p["date"] == "2026-11-18")
        runs = {r["id"]: r for r in probe["runs"]}
        trial = runs["shared-lemma-4"]
        self.assertEqual((runs[trial["baseline"]]["seconds"], trial["seconds"]), (42, 46))
        self.assertEqual((trial["relatedApplications"], trial["applications"]), (154, 309))
        for bound in (5, 6):
            row = runs[f"bound-{bound}"]
            self.assertEqual((row["budgetSeconds"], row["secondsToVerdict"], row["reportedVerdict"]),
                             (150, None, "unresolved"))
        self.assertIn("bound-8", probe["retryCondition"])
        self.assertFalse(any(e.get("route") == "historical-probe" for e in task["evidence"]))
        source = probe["source"]
        self.assertIn(source["entry"], (HERE.parents[2] / source["path"]).read_text())


if __name__ == "__main__":
    unittest.main()
