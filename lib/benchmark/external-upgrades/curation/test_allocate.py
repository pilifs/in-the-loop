import dataclasses
from datetime import timedelta
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parent))
import allocate as al
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from cost_tier import cost
sys.path.append(str(Path(__file__).resolve().parents[4] / "lib/tools"))
from cost_tier import cost  # noqa: E402


SEED = bytes(range(32))
DATE = al.screen.utc("2020-01-01T00:00:00Z")


def example():
    ids = sorted([f"compsuite:i-{10000 + i}" for i in range(16)], key=lambda sid: al.screen.rank(SEED, sid))
    changes, routines, searches = [], [], {}
    for i, sid in enumerate(ids):
        if i < 12:
            family = f"represented-{i // 2}"
        elif i < 14:
            family = f"represented-{i - 12}"
        else:
            family = f"new-{i}"
        client = f"synthetic/client-{i}"
        change = al.Case(sid, "change", client, family, "1.0", "1.1", f"c{i}", f"ci{i}", DATE, "minor", "single")
        rid = f"github:{client}#7"
        routine = al.Case(rid, "preservation", client, family if i else "other-main-family",
                          "2.0", "2.1", f"r{i}", f"ri{i}", DATE + timedelta(days=0 if i else 3), "minor", "single")
        changes.append(change)
        routines.append(routine)
        searches[sid] = [rid]
    # The nearest tier-three PR for the earliest main anchor is the only match for a transfer case.
    searches[ids[0]].append(routines[-1].stable_id)
    return changes, routines, searches


def solve(changes, routines, searches):
    cases = {c.stable_id: c for c in changes + routines}
    return al.allocate(cases, al.ranked_pairs(cases, searches, SEED))


def write_docket(root):
    def write(name, value):
        body = al.canonical(value)
        (root / name).write_bytes(body)
        return {"file": name, "sha256": al.digest(body)}

    key = Ed25519PrivateKey.generate()
    commitment = write("commitment.json", {"seed_sha256": al.digest(SEED),
                                           "signer_ed25519_raw_hex": key.public_key().public_bytes_raw().hex()})
    (root / "test.seed").write_bytes(SEED)
    (root / "test.key").write_bytes(key.private_bytes_raw())
    (root / "test.encryption").write_bytes(bytes(range(32, 64)))
    packet = root / "source"
    packet.mkdir()
    evidence = write("screening-ledger.json", {"description": "Entire synthetic discovery frame."})
    changes, routines, searches = example()
    doc = {"changes": [], "routines": [],
           "audit": {"before_v0_scoring": True, "ranked_review_complete": True, "ledger": evidence},
           "searches": [{"anchor": sid, "routine_ids": items, "evidence": evidence, "complete": True}
                        for sid, items in searches.items()]}
    for i, case in enumerate(changes + routines):
        label = f"synthetic-{i}"
        name = f"{label}.sealed"
        (packet / "identity.json").write_bytes(al.canonical({"stable_id": case.stable_id}))
        receipt = al.seal_reference.seal(SimpleNamespace(
            folder=packet, output=root / name, signing_key=root / "test.key", encryption_key=root / "test.encryption",
            commitment=root / commitment["file"], packet_id=label))
        decision = write(f"{label}.decision", {"stable_id": case.stable_id, "stratum": case.stratum,
                                               "packet_id": label,
                                               "signed_envelope_sha256": receipt["signed_envelope_sha256"]})
        row = dataclasses.asdict(case)
        change = row.pop("stratum") == "change"
        row["changed_at" if change else "merged_at"] = row.pop("date").isoformat()
        row.update(review="qualified", reference_audited=True, evidence=decision,
                   reference={"file": name, "sha256": al.digest((root / name).read_bytes())})
        doc["changes" if change else "routines"].append(row)
    return doc


class AllocateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The three allocation tests exercise the real SMT executable through the public API.
        version = subprocess.check_output(["z3", "-version"], text=True)
        if not version.startswith("Z3 version "):
            raise RuntimeError("The cohort allocation tests require the Z3 command-line solver.")

    @cost("tool")
    def test_earliest_feasible_main_match_reserves_the_only_transfer_routine(self):
        changes, routines, searches = example()
        cases = {c.stable_id: c for c in changes + routines}
        ordered = al.ranked_pairs(cases, searches, SEED)
        self.assertEqual(ordered[0].routine, routines[-1])
        counts, chosen = al.allocate(cases, ordered)
        self.assertEqual((counts["main_pairs"], counts["reserve_pairs"]), (12, 4))
        self.assertEqual([p.change for p in chosen[0]], changes[:12])
        self.assertEqual(chosen[0][0].routine, routines[0])
        self.assertEqual(chosen[1][-1].routine, routines[-1])
        self.assertEqual(counts["reserve"], {s: {"same": 2, "new": 2} for s in al.STRATA})
        al.validate_selection(chosen)
        reordered = dict(reversed(list(cases.items())))
        self.assertEqual(al.ranked_pairs(reordered, dict(reversed(list(searches.items()))), SEED), ordered)

        # All sixteen pairs can still be matched if the first anchor takes this *extra* PR.
        # Doing so represents the only new family for two changes whose client is already in the 24.
        for i in (0, 2, 14, 15):
            changes[i] = dataclasses.replace(changes[i], client="synthetic/shared-client")
        for i in (14, 15):
            changes[i] = dataclasses.replace(changes[i], family="required-new-family")
            routines[i] = dataclasses.replace(routines[i], family="required-new-family")
        extra = dataclasses.replace(routines[-1], stable_id="github:synthetic/extra#88",
                                    client="synthetic/extra", trigger="extra", incident="extra-incident")
        searches[changes[0].stable_id] = [routines[0].stable_id, extra.stable_id]
        routines.append(extra)
        cases = {c.stable_id: c for c in changes + routines}
        ordered = al.ranked_pairs(cases, searches, SEED)
        self.assertEqual(ordered[0].routine, extra)
        counts, chosen = al.allocate(cases, ordered)
        self.assertEqual(chosen[0][0].routine, routines[0])
        self.assertNotIn(extra, [p.routine for p in chosen[0] + chosen[1]])
        al.validate_selection(chosen)

    @cost("tool")
    def test_shared_incident_and_duplicate_trigger_cannot_cross_cohorts(self):
        changes, routines, searches = example()
        originals = routines[-1]
        for replacement in (
            dataclasses.replace(originals, incident=changes[0].incident),
            dataclasses.replace(originals, client=changes[0].client, family=changes[0].family,
                                old_version=changes[0].old_version, new_version=changes[0].new_version,
                                trigger=changes[0].trigger),
        ):
            with self.subTest():
                counts, chosen = solve(changes, [*routines[:-1], replacement], searches)
                self.assertIsNone(chosen)
                self.assertEqual(counts["main_pairs"], 12)
                self.assertLess(counts["reserve_pairs"], 4)

    @cost("tool")
    def test_private_output_binds_the_input_and_withholds_provisional_or_short_rosters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = write_docket(root)
            docket, seed, commitment = root / "docket.json", root / "test.seed", root / "commitment.json"

            def attempt(name):
                docket.write_bytes(al.canonical(doc))
                summary = al.run(docket, seed, commitment, root / name)
                result = json.loads((root / name).read_bytes())
                self.assertEqual(result["docket_sha256"], al.digest(docket.read_bytes()))
                self.assertNotIn("synthetic", json.dumps(summary))
                return summary, result

            summary, result = attempt("complete")
            self.assertEqual(summary["status"], "ready-to-seal")
            self.assertEqual(result["main_sha256"], al.digest(al.canonical(result["main"])))
            self.assertEqual(result["transfer_sha256"], al.digest(al.canonical(result["transfer"])))
            doc["searches"][0]["complete"] = False
            summary, result = attempt("incomplete-search")
            self.assertEqual(summary["status"], "audit-pending")
            self.assertEqual(summary["audit_outstanding"]["incomplete_searches"], 1)
            self.assertNotIn("main", result)
            doc["changes"][-1]["review"] = "pending"
            summary, result = attempt("incomplete-evidence")
            self.assertEqual(summary["status"], "shortfall")
            self.assertEqual(summary["audit_outstanding"]["pending_ranked_reviews"], 1)
            self.assertNotIn("transfer", result)
            restored = doc["changes"][-1]
            restored["review"] = "qualified"
            doc["searches"][-1]["routine_ids"] = []
            summary, _ = attempt("unmatched")
            self.assertEqual(summary["qualified_changes_without_eligible_match"], 1)


class EligibilityTest(unittest.TestCase):
    def test_matching_window_tiers_and_registry_order(self):
        changes, routines, _ = example()
        c, r = changes[1], routines[1]
        self.assertEqual(al.match(c, r).tier, 1)
        self.assertEqual(al.match(c, dataclasses.replace(r, client="synthetic/another")).tier, 2)
        self.assertEqual(al.match(c, dataclasses.replace(r, family="another")).tier, 3)
        self.assertIsNone(al.match(c, dataclasses.replace(r, family="another", build="reactor")))
        self.assertIsNone(al.match(c, dataclasses.replace(r, family="another", version_step="patch")))
        self.assertIsNotNone(al.match(c, dataclasses.replace(r, date=c.date - timedelta(days=365))))
        self.assertIsNone(al.match(c, dataclasses.replace(r, date=c.date + timedelta(days=365, microseconds=1))))
        self.assertIsNone(al.match(dataclasses.replace(c, date=al.CUTOFF),
                                   dataclasses.replace(r, date=al.CUTOFF + timedelta(microseconds=1))))
        bump = dataclasses.replace(c, stable_id="bump:" + "a" * 40)
        tied = dataclasses.replace(r, stable_id="github:synthetic/another#11")
        candidates = {x.stable_id: x for x in (c, bump, r, tied)}
        ids = [r.stable_id, tied.stable_id]
        ordered = al.ranked_pairs(candidates, {bump.stable_id: ids, c.stable_id: ids}, SEED)
        self.assertEqual([p.change for p in ordered], [c, c, bump, bump])
        self.assertEqual([p.routine.stable_id for p in ordered[:2]], sorted(ids, key=lambda s: al.screen.rank(SEED, s)))

    def test_swapped_valid_signed_packets_cannot_replace_the_reviewed_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = write_docket(root)
            a, b = doc["changes"][:2]
            a["reference"], b["reference"] = b["reference"], a["reference"]
            with self.assertRaisesRegex(ValueError, "signed reference differs"):
                al.read_docket(root, doc, root / "commitment.json")


if __name__ == "__main__":
    unittest.main()
