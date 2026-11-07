"""Tests of examples/tools/gap_table.py on made-up results: python3 -m unittest examples/tools/test_gap_table.py"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gap_table  # noqa: E402

GAP = {"id": "jdk-static-method:java.util.List.of([Ljava/lang/Object;)Ljava/util/List;@jdk-25", "kind": "jdk-static-method", "checker": "jbmc"}
OWN = {"id": "jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-25", "kind": "jdk-constructor", "checker": None}


def evidence(gaps):
    return {"search": {"gapMode": "assume", "gaps": gaps}}


class GapTableTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="gap-table-"))

    def write(self, name, result):
        (self.dir / name).mkdir()
        (self.dir / name / "result.json").write_text(json.dumps(result))

    def test_each_obligation_is_a_row_and_only_an_established_one_with_a_gap_is_refused(self):
        self.write("071-props", {"format": 2, "conclusion": {"status": "refuted", "obligations": [
            {"status": "established", "evidence": evidence([GAP])},
            {"status": "refuted", "evidence": evidence([GAP])},
            {"status": "established", "evidence": evidence([])}]}})
        self.write("128-one", {"format": 2, "conclusion": {"status": "established"}, "evidence": evidence([OWN])})
        self.write("013-flat", {"verdict": "violation"})
        skipped = []
        rows = gap_table.table(self.dir, skipped=skipped)
        self.assertEqual([(r["example"], r["obligation"], r["strictWouldRefuse"]) for r in rows],
                         [("071", 0, True), ("071", 1, False), ("071", 2, False), ("128", 0, True)])
        self.assertEqual(rows[0]["gaps"], ["jdk-static-method:java.util.List.of([Ljava/lang/Object;)Ljava/util/List;"])
        self.assertEqual(rows[0]["gapModes"], ["assume"])
        self.assertEqual(skipped, ["013"], "a result without gap records is skipped, and said to be")
        # By checker: the own checker's gap has no checker field set.
        self.assertEqual([r["example"] for r in gap_table.table(self.dir, "jbmc") if r["gaps"]], ["071", "071"])
        self.assertEqual([r["example"] for r in gap_table.table(self.dir, "native") if r["gaps"]], ["128"])
        self.assertEqual([r["example"] for r in gap_table.table(self.dir, ids={"128"})], ["128"])

    def test_a_row_names_its_engine_its_expectation_and_why_it_has_no_verdict_and_two_tables_compare(self):
        defect = ("JBMC proved it, but runs 1 construct otherwise than the JVM (return-past-handler at p.D.f:7: "
                  "ArithmeticException), so the proof is refused under every --gaps mode")
        jbmc = {"engine": "jbmc", "checker": "JBMC 6.11.0", "gapMode": "strict"}
        self.write("120-jbmc", {"format": 2, "conclusion": {"status": "unresolved", "expectation": "no"},
                                "evidence": {"search": jbmc, "problem": defect}})
        self.write("121-jbmc", {"format": 2, "conclusion": {"status": "established", "expectation": "yes"},
                                "evidence": {"search": jbmc, "problem": "not shown: it has a verdict"}})
        rows = gap_table.table(self.dir)
        self.assertEqual([(r["engine"], r["checker"], r["expectation"], r["jbmcDefect"]) for r in rows],
                         [("jbmc", "JBMC 6.11.0", "no", True), ("jbmc", "JBMC 6.11.0", "yes", False)])
        self.assertEqual(rows[0]["problem"], defect)
        self.assertIsNone(rows[1]["problem"], "only an obligation with no verdict carries its problem")
        native = [dict(rows[0], status="refuted", engine="native", problem=None), dict(rows[1], engine="native")]
        self.assertEqual([(k, x["status"], y["status"]) for k, x, y in gap_table.compare(rows, native)],
                         [(("120", 0), "unresolved", "refuted")])
        self.assertEqual([(k, y) for k, x, y in gap_table.compare(rows, native[1:])], [(("120", 0), None)],
                         "an obligation only one table has is listed")
        a, b = self.dir / "a.json", self.dir / "b.json"
        a.write_text(json.dumps(rows))
        b.write_text(json.dumps(native))
        self.assertEqual(gap_table.main(["--compare", str(a), str(b)]), 0)

    def test_the_inventory_says_which_engine_decides_each_obligation_and_what_stops_the_other(self):
        def row(example, status, gaps=(), problem=None, index=0):
            return {"example": example, "obligation": index, "status": status, "gaps": list(gaps), "problem": problem}
        jbmc = [row("013", "refuted"), row("035", "refuted"), row("037", "unresolved", problem="JBMC proved it, but"),
                row("071", "unresolved", ["jdk-static-method:java.util.List.of([Ljava/lang/Object;)Ljava/util/List;"]),
                row("128", "established")]
        native = [row("013", "refuted"), row("035", "unresolved", problem="outside the fragment: a float parameter"),
                  row("037", "established"), row("071", "unresolved", problem="a loop was not fully unwound"),
                  row("128", "refuted")]
        self.assertEqual([(k[0], by, why) for k, _, _, by, why in gap_table.inventory(jbmc, native)], [
            ("013", "both", ""),
            ("035", "JBMC only", "own checker: outside the fragment: a float parameter"),
            ("037", "own checker only", "JBMC: JBMC proved it, but"),
            ("071", "neither", "JBMC: gap jdk-static-method:java.util.List.of; own checker: a loop was not fully unwound"),
            ("128", "conflict", ""),
        ])
        self.assertEqual(gap_table.inventory(jbmc[:1], [])[0][3:], ("JBMC only", "own checker: not run"))
        a, b = self.dir / "a.json", self.dir / "b.json"
        a.write_text(json.dumps(jbmc))
        b.write_text(json.dumps(native))
        self.assertEqual(gap_table.main(["--inventory", str(a), str(b)]), 1, "a conflict fails")
        b.write_text(json.dumps(native[:4]))
        self.assertEqual(gap_table.main(["--inventory", str(a), str(b)]), 0)


if __name__ == "__main__":
    unittest.main()
