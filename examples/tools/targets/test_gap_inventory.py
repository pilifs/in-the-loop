"""examples/gap-inventory.md, Phase 5 step 4's v1 gap inventory: the committed page is workflow_handoff.py's rendering
of the tree as it is, every observed gap is ranked with a reproducer that reruns it, an owner module and a closure
test, the predictions stay apart and unranked against them, and find.py --gap finds a gap's examples by its id."""

import contextlib
import io
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent.parent
ROOT = EXAMPLES.parent
sys.path.insert(0, str(HERE.parent))
from targets import sidecar, workflow, workflow_handoff  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[3] / "lib/tools"))
from cost_tier import cost  # noqa: E402

PAGE = EXAMPLES / "gap-inventory.md"
RANKED = [
    # (gap, distinct families, blocked obligations): observed first, then families, then obligations. Until
    # 2026-11-15 two-dependency-closures was first (3 families, 4 obligations) and interface-parameter blocked 7:
    # example 285's four tasks left both when their receipts decided the unchanged claims (its packets' `closed`).
    # Until 2026-11-16 string-parameter blocked 5: example 287's two guard tasks left it the same way.
    ("input-construction:receiver-of-several-constructors", 2, 8),
    ("input-construction:string-parameter", 2, 3),
    ("verifier-interface:two-dependency-closures", 2, 3),
    ("jdk-static-method:java.util.ServiceLoader.load(Ljava/lang/Class;)Ljava/util/ServiceLoader;", 1, 5),
    ("input-construction:interface-parameter", 1, 4),
    ("jdk-constructor:java.lang.StringBuilder.<init>()V", 1, 1),
]


def rows():
    out = []
    for folder in sorted(p.parent for p in EXAMPLES.glob("*/example.json")):
        example = json.loads((folder / "example.json").read_text())
        if example.get("target"):
            target = sidecar.load(folder, example)
            if target is not None:
                out.append((folder, example, target))
    return out


class GapInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows()
        cls.value = workflow_handoff.inventory(cls.rows)

    def test_the_committed_page_is_the_rendering_of_the_tree(self):
        folders = {e["id"]: f.name for f, e, _ in self.rows}
        self.assertEqual(PAGE.read_text(), workflow_handoff.inventory_markdown(self.value, folders),
                         "regenerate it with the router: python3 examples/tools/build.py --index-only")

    def test_index_only_and_render_only_rewrite_the_page_with_the_router(self):
        """Review item 2 of 2026-11-15: the page moves with the index, so build.py's two modes that rewrite the router
        rewrite it too. Every write is captured, so nothing in the tree changes."""
        import build
        wanted = workflow_handoff.inventory_markdown(self.value, {e["id"]: f.name for f, e, _ in self.rows})
        page = build.EXAMPLES / "gap-inventory.md"
        for argv in (["--index-only"], ["--render-only", "285"]):
            with self.subTest(argv=argv):
                written = {}
                with mock.patch.object(Path, "write_text", autospec=True,
                                       side_effect=lambda path, text, *a, **k: written.__setitem__(path, text)), \
                        contextlib.redirect_stdout(io.StringIO()):
                    build.main(argv)
                self.assertIn(build.EXAMPLES / "index.json", written, "the router itself")
                self.assertEqual(written.get(page), wanted)

    def test_the_observed_gaps_are_ranked_by_families_then_blocked_obligations(self):
        observed = [g for g in self.value["gaps"] if g["observed"]]
        self.assertEqual([(g["gap"], len(g["families"]), g["blockedObligations"]) for g in observed], RANKED)
        self.assertEqual([g["rank"] for g in observed], list(range(1, len(RANKED) + 1)))
        self.assertEqual(sum(g["blockedObligations"] for g in observed), 24)
        predicted = [g for g in self.value["gaps"] if not g["observed"]]
        self.assertTrue(predicted)
        self.assertTrue(all(g["rank"] > len(RANKED) and g["blockedObligations"] == 0 for g in predicted))

    def test_each_observed_gap_has_a_rerunnable_reproducer_an_owner_and_a_closure_test(self):
        for g in self.value["gaps"]:
            if not g["observed"]:
                self.assertIsNone(g["reproducer"], g["gap"])
                continue
            with self.subTest(gap=g["gap"]):
                r = g["reproducer"]
                self.assertIsNotNone(r)
                self.assertEqual(r["check"], f"python3 examples/tools/targets/workflow_refusal.py {r['example']} "
                                             f"{r['task']}")
                self.assertIn((r["example"], r["task"], r["claim"]),
                              {(o["example"], o["task"], o["claim"]) for o in g["obligations"] if o["observed"]})
                folder = next(EXAMPLES.glob(f"{r['example']}-*"))
                packet = json.loads((folder / r["packet"]).read_text())
                self.assertEqual((packet["observed"]["job"], packet["claimKey"]), (r["job"], r["claim"]))
                self.assertTrue((ROOT / "verification/results" / r["job"]).is_dir(), r["job"])
                self.assertTrue(r["semantics"])
                self.assertIn(f"the unchanged claim {r['claim']} rerun", r["closure"])
                self.assertTrue(g["modules"])
                seconds = [o.get("seconds") for o in g["obligations"] if o["observed"] and o.get("check")]
                known = [s for s in seconds if s is not None]
                if known:
                    self.assertEqual(r["seconds"], min(known), "the smallest recorded attempt")

    @cost("tool")
    def test_find_gap_takes_a_gap_id_or_its_part_before_a_colon(self):
        def found(gap):
            out = subprocess.run([sys.executable, str(EXAMPLES / "tools/find.py"), "--json", "--limit", "50",
                                  "--gap", gap], capture_output=True, text=True, check=True).stdout
            return sorted(e["id"] for e in json.loads(out))

        expected = {g["gap"]: sorted({o["example"] for o in g["obligations"] if o["observed"]})
                    for g in self.value["gaps"] if g["observed"]}
        for gap, examples in expected.items():
            with self.subTest(gap=gap):
                self.assertEqual(found(gap), examples)
        self.assertEqual(found("jdk-constructor"), ["105"])
        self.assertEqual(found("input-construction:string"), [], "a part matches only up to a colon")


STALE = "Predicted, not observed (no verifier has run on this packet)"
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class DatedPredictionTest(unittest.TestCase):
    """Review item 3 of 2026-11-15: 285-287's prediction summaries, written by the negative stream on 2026-11-14 before
    any verifier ran (seven of the ten said so), keep their text, dated, with a later dated line pointing to the
    observed blockers and this page. A summary is also a predicted group's id on the page, so its text never changes.
    285's two left the sidecar on 2026-11-15, when its four proof tasks were decided by their receipts: a prediction
    about a task whose claim is decided is no hypothesis any more. 286's and 287's eight stay, five of them saying so."""

    @classmethod
    def setUpClass(cls):
        cls.rows = rows()
        cls.stale = [(f, e, t, b) for f, e, t in cls.rows for b in t.get("handoff", {}).get("blockers", [])
                     if not b["observed"] and e["id"] in ("285", "286", "287")]

    def test_the_summaries_keep_their_text(self):
        self.assertEqual(len(self.stale), 8)
        self.assertEqual(sorted(e["id"] for _, e, _, b in self.stale if b["summary"].startswith(STALE)),
                         ["286", "286", "286", "286", "287"])

    def test_each_is_dated_and_points_to_its_observed_blockers_and_the_page(self):
        for folder, example, target, b in self.stale:
            with self.subTest(example=example["id"], task=b.get("task"), summary=b["summary"][len(STALE):][:50]):
                self.assertRegex(b.get("recorded", ""), DATE, "the date the summary was written")
                self.assertEqual(b["recorded"], "2026-11-14")
                note = b.get("note", "")
                date = note.split(":", 1)[0]
                self.assertRegex(date, DATE, "the note opens with its own date")
                self.assertGreater(date, b["recorded"])
                self.assertIn("examples/gap-inventory.md", note)
                observed = [o for o in target["handoff"]["blockers"] if o["observed"] and o.get("packet")
                            and (b.get("task") is None or o.get("task") == b["task"])]
                self.assertTrue(observed, "a later attempt of the task it covers was refused first")
                for o in observed:
                    self.assertIn(o["packet"], note, "names each observed blocker of the task it covers")
                    self.assertTrue((folder / o["packet"]).is_file())

    def test_the_handoff_and_the_page_carry_the_date(self):
        page = PAGE.read_text()
        for folder, example, target, b in self.stale:
            with self.subTest(example=example["id"], task=b.get("task")):
                tasks = [t for t in target["tasks"] if b.get("task") in (None, t["id"])]
                gaps = [g for t in tasks
                        for g in workflow_handoff.packet(folder, example, target, t["id"])["gaps"]
                        if g["summary"] == b["summary"]]
                self.assertTrue(gaps)
                for g in gaps:
                    self.assertEqual((g.get("recorded"), g.get("note")), (b["recorded"], b["note"]))
                cut = workflow_handoff.cell(workflow_handoff.first_sentence(b["summary"]))
                self.assertIn(f"(recorded {b['recorded']}) {cut}", page)

    def test_the_readmes_predicted_sections_are_dated_and_point_to_the_page(self):
        for folder in sorted({f for f, _, _, _ in self.stale}):
            with self.subTest(folder=folder.name):
                text = (folder / "README.md").read_text()
                section = text.split("## Predicted blockers", 1)[1].split("\n## ", 1)[0]
                self.assertIn("2026-11-14", section)
                self.assertIn("gap-inventory.md", section)
                self.assertIn("(#observed-blockers)", section)


CLOSURES = "verifier-interface:two-dependency-closures"
CLOSURE_TASKS = [("286", "preservation"), ("287", "preservation"), ("306", "preservation")]


class VerifierInterfaceKindTest(unittest.TestCase):
    """Review item 4 of 2026-11-15: the four preservation tasks stopped because jvmcontract's equivalence took one
    --classpath for both sides, so a pair with two dependency closures couldn't be given to it as stated. Nothing about
    the inputs is missing, so the gap is no input construction: it has a kind of its own, verifier-interface, a
    capability kind (the scaffold is sound, the task is blocked), owned by the verifier's command line.

    Since 2026-11-15 equivalence takes --before-classpath and the route passes it, and 285's preservation is decided
    by its receipt (its packet says `closed`). The other three are recorded as they were observed until each one's
    unchanged claim is rerun: the refusal is gone for them too, and what else each needs its attempt will say."""

    @classmethod
    def setUpClass(cls):
        cls.rows = {e["id"]: (f, e, t) for f, e, t in rows()}

    def test_the_schema_and_the_workflow_know_the_kind(self):
        schema = json.loads((EXAMPLES / "schema/target.schema.json").read_text())
        kind = schema["properties"]["handoff"]["properties"]["blockers"]["items"]["properties"]["kind"]
        self.assertIn("verifier-interface", kind["enum"])
        self.assertIn("verifier-interface", kind["description"])
        self.assertIn("verifier-interface", workflow.CAPABILITY_KINDS)
        self.assertIn("--classpath", workflow_handoff.KIND_MODULES["verifier-interface"])

    def test_the_packets_and_the_sidecars_are_reclassified(self):
        for n, task in CLOSURE_TASKS:
            with self.subTest(example=n):
                folder, example, target = self.rows[n]
                packet = json.loads((folder / "records/refusals" / f"{task}.json").read_text())
                self.assertEqual([d["id"] for d in packet["diagnostic"]], [CLOSURES])
                self.assertIn("dependency closures", packet["refusal"]["text"])
                b = next(b for b in target["handoff"]["blockers"]
                         if b.get("packet") == f"records/refusals/{task}.json")
                self.assertEqual((b["kind"], b["observed"]), ("verifier-interface", True))
                self.assertRegex(b.get("note", ""), r"^\d{4}-\d{2}-\d{2}: .*input-construction")
                self.assertEqual(workflow.task_readiness(folder, example, target, task)["summary"], "blocked")

    def test_no_other_observed_gap_says_dependency_closures_and_the_inventory_groups_the_three(self):
        value = workflow_handoff.inventory(list(self.rows.values()))
        g = next(g for g in value["gaps"] if g["gap"] == CLOSURES)
        self.assertEqual((g["kind"], g["class"], g["observed"]), ("verifier-interface", "capability", True))
        self.assertEqual(sorted((o["example"], o["task"]) for o in g["obligations"]), CLOSURE_TASKS)
        self.assertIn("--classpath", " ".join(g["modules"]))
        for other in value["gaps"]:
            if other["gap"] != CLOSURES:
                self.assertNotIn("two-dependency-closures", other["gap"])
                self.assertNotIn("dependency closures", other.get("semantics") or "")


if __name__ == "__main__":
    unittest.main()
