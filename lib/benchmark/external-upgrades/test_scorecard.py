import json
from pathlib import Path
import sys
import tempfile
import unittest

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scorecard as sc


DIGEST = "1" * 64


def operator(case="u01", build="V0"):
    return {"case_id": case, "build": build, "input_sha256": DIGEST, "product_sha256": DIGEST,
            "environment_sha256": DIGEST, "route": "exhaustive-jvm", "evidence": [],
            "primary_claim": "returned sequence", "observer": "client return", "domain": "two calls", "scope": "UTC",
            "artifacts": {"old": ["2" * 64], "new": ["3" * 64]},
            "intake_utc": "2020-01-01T00:00:00Z", "finished_utc": "2020-01-01T00:01:00Z",
            "first_actionable_utc": "2020-01-01T00:00:30Z", "checkpoint_15m": "completed",
            "cache": "cold", "cpu_limit": 4, "memory_gib": 16, "human_minutes": 0,
            "uncached_input_tokens": 120, "output_tokens": 10, "cached_input_tokens": 0, "compute_usd": None,
            "assisted": False, "review_action": "retain the original check",
            "maintainer_report": "\n".join(s + " observed" for s in sc.LABELS)}


class UpgradeScoringTest(unittest.TestCase):
    def test_first_report_keeps_its_evidence_and_rejects_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = b"independent JVM output\n"
            (root / "proof.txt").write_bytes(evidence)
            doc = operator()
            doc["evidence"] = [{"file": "proof.txt", "sha256": sc.sha(evidence)}]
            source = root / "input.json"
            source.write_text(json.dumps(doc))
            case = {"case_id": doc["case_id"], "input_sha256": DIGEST}
            sealed = root / "reports"
            first = sc.seal_report(source, sealed)
            with self.assertRaisesRegex(ValueError, "already sealed"):
                sc.seal_report(source, sealed)
            _, recorded, seconds, _ = sc.read_first(sealed, "V0", case, sc.timestamp(doc["intake_utc"]), DIGEST)
            self.assertEqual((recorded, seconds), (first, 60))
            (sealed / "V0/u01/evidence/proof.txt").write_bytes(b"unrelated")
            with self.assertRaisesRegex(ValueError, "digest differs"):
                sc.read_first(sealed, "V0", case, sc.timestamp(doc["intake_utc"]), DIGEST)

    def test_signed_roster_has_fixed_denominators_and_cannot_be_used_as_a_grade(self):
        rows = [{"case_id": f"case{i}", "input_sha256": DIGEST, "reference_sha256": DIGEST,
                 "stratum": "change" if i < 12 else "preservation"} for i in range(24)]
        roster = {"phase": "main", "cases": rows, "locked_utc": "2020-01-01T00:00:00Z"}
        key = Ed25519PrivateKey.generate()
        signature = key.sign(b"upgrade-roster-v1\0" + sc.canonical(roster)).hex()
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "signed-roster.json"
            file.write_text(json.dumps({"payload": roster, "signatureHex": signature}))
            self.assertEqual(sc.roster(sc.verified_document(file, key.public_key(), "upgrade-roster-v1")), rows)
            with self.assertRaises(InvalidSignature):
                sc.verified_document(file, key.public_key(), "upgrade-adjudication-v1")
        with self.assertRaisesRegex(ValueError, "denominator"):
            sc.roster({**roster, "cases": rows[:-1]})

    def test_paired_gain_requires_matched_conditions_and_separate_capability_evidence(self):
        row = {"case_id": "u01", "family": "new", "stratum": "change", "seconds": 12, "cache": "cold",
               "cpuLimit": 4, "memoryGiB": 16, "environmentSha256": DIGEST, "improvedCapability": None}
        before = {"phase": "transfer", "productSha256": DIGEST, "cases": [{**row, "credit": False}]}
        after = {"phase": "transfer", "productSha256": "2" * 64, "cases": [{**row, "credit": True}]}
        paired = sc.paired([before, after])
        self.assertEqual(paired["byFamily"]["new"]["v1Only"], 1)
        self.assertIsNone(paired["cases"][0]["transferableRepair"])
        after["cases"][0]["cache"] = "warm"
        with self.assertRaisesRegex(ValueError, "conditions differ"):
            sc.paired([before, after])

    def test_twenty_four_first_reports_count_claims_once_and_keep_the_pilot_gate(self):
        key = Ed25519PrivateKey.generate()
        cases, reports = [], {}
        sealed_at = sc.timestamp("2020-01-01T01:00:00Z")
        budget = {"wallSeconds": 7200, "humanReviewMinutes": 15, "uncachedInputPlusOutputTokens": 250000,
                  "cpus": 4, "memoryGiB": 16}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "V0").mkdir()
            for i in range(24):
                cid = f"case{i}"
                changed = i < 12
                correct = i % 12 < 8
                cases.append({"case_id": cid, "stratum": "change" if changed else "preservation",
                              "input_sha256": DIGEST, "reference_sha256": DIGEST})
                doc = operator(cid)
                doc["route"] = "jvm-witness" if changed else "exhaustive-jvm"
                reports[cid] = doc, DIGEST, 60, sealed_at
                judgement = {"relevant": correct, "scope_supported": True, "original_domain": True,
                             "contradicted": False, "unresolved_contradiction": False, "false_alert": False,
                             "incremental_over_ci": False, "replayed": changed, "nonvacuous": not changed}
                grades = [{"reviewer": who, "reason": "covered the caller domain", "action": "keep original test",
                           "judgement": judgement} for who in ("curator", "second reviewer")]
                result = {"case_id": cid, "report_sha256": DIGEST, "reference_sha256": DIGEST,
                          "reference_signature_hex": key.sign(sc.SIGNATURE_CONTEXT + bytes.fromhex(DIGEST)).hex(),
                          "revealed_utc": "2020-01-01T01:01:00Z", "reviews": grades, "decision": judgement,
                          "ci_result": "observed", "action_grade": "appropriate", "primary_reason": "wrong observer"}
                signature = key.sign(b"upgrade-adjudication-v1\0" + sc.canonical(result)).hex()
                (root / "V0" / (cid + ".json")).write_text(json.dumps({"payload": result, "signatureHex": signature}))
            roster = {"phase": "main", "cases": cases, "locked_utc": "2019-12-31T00:00:00Z"}
            scored = sc.score(roster, reports, root, "V0", DIGEST, budget, sealed_at, key.public_key())
            self.assertEqual((scored["denominator"], scored["relevantChange"], scored["relevantPreservation"]),
                             (24, 8, 8))
            self.assertTrue(scored["pilotGate"])
            reports["case0"][0]["assisted"] = True
            self.assertFalse(sc.score(roster, reports, root, "V0", DIGEST, budget, sealed_at, key.public_key())["pilotGate"])
            with self.assertRaisesRegex(ValueError, "before the last first report"):
                sc.score(roster, reports, root, "V0", DIGEST, budget, sc.timestamp("2020-01-02T00:00:00Z"),
                         key.public_key())


if __name__ == "__main__":
    unittest.main()
