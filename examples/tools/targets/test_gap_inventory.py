"""examples/gap-inventory.md, Phase 5 step 4's v1 gap inventory: the committed page is workflow_handoff.py's rendering
of the tree as it is, every observed gap is ranked with a reproducer that reruns it, an owner module and a closure
test, the predictions stay apart and unranked against them, and find.py --gap finds a gap's examples by its id."""

import contextlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent.parent
ROOT = EXAMPLES.parent
sys.path.insert(0, str(HERE.parent))
from targets import sidecar, workflow_handoff  # noqa: E402

PAGE = EXAMPLES / "gap-inventory.md"
RANKED = [
    # (gap, distinct families, blocked obligations): observed first, then families, then obligations
    ("input-construction:two-dependency-closures", 3, 4),
    ("input-construction:receiver-of-several-constructors", 2, 8),
    ("input-construction:string-parameter", 2, 5),
    ("input-construction:interface-parameter", 1, 7),
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
        self.assertEqual(sum(g["blockedObligations"] for g in observed), 25)
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


if __name__ == "__main__":
    unittest.main()
