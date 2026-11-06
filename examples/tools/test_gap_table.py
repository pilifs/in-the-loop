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


if __name__ == "__main__":
    unittest.main()
