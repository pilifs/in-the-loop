"""Tests of the solver comparison's tables and checks: python3 -m unittest lib/solvers/test_compare.py (from the repo
root). Nothing here runs a check or a solver; the comparison itself is a pipeline job."""

import sys
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare  # noqa: E402


def results(checks, replays, solvers=("cadical", "bitwuzla")):
    return {
        "environment": {"commit": "0123456789abcdef", "host": "h", "machine": "x86_64", "cpu": "c", "cpus": 1, "date": "d", "jvmcontract": "jvmcontract 0.1.0", "java": "java 25", "bitwuzla": {"path": "/b/libbitwuzla.so", "sha256": "ab" * 32}},
        "settings": {"mode": "strict", "unwind": 16, "maxArrayLength": 8, "repeat": 2, "solvers": list(solvers), "cases": ["held/reverse"]},
        "cases": [{"id": "held/reverse", "group": 3, "workload": "array-mutation", "kind": "regression", "expected": "verified"}],
        "checks": checks,
        "replays": replays,
    }


def check(solver, verdict="verified", seconds=1.0, run=1):
    return {"case": "held/reverse", "solver": solver, "run": run, "verdict": verdict, "class": "correct" if verdict == "verified" else "false-alarm",
            "seconds": seconds, "peakMB": 40.0, "stats": {"solver_calls": 115, "clauses": 59707, "solving_seconds": seconds / 2}, "signature": f"{solver} 1.0"}


def replay(solver, contradictions=0, seconds=0.5, run=1):
    return {"case": "held/reverse", "transcript": "1-1.icnf", "solver": solver, "run": run, "exit": 0, "seconds": seconds, "solving": seconds / 2,
            "calls": 115, "clauses": 59707, "contradictions": contradictions}


class CompareTest(unittest.TestCase):
    def test_a_job_records_the_runners_commit_since_its_tree_has_no_git(self):
        # Jobs -224616 and -230455 ran in the runner's exported tree, where git finds nothing: their tables say `at ?`.
        with unittest.mock.patch.dict(compare.os.environ, {"VERIFY_SOURCE_COMMIT": "bbb3062e89b4"}):
            self.assertEqual(compare.source_commit(), "bbb3062e89b4")

    def test_the_five_workloads_are_the_benchmarks_cases(self):
        run = compare.benchmark()
        ids = {c["id"] for c in run.load_cases({2, 3, 4})}
        self.assertTrue(set(compare.CASES) <= ids, set(compare.CASES) - ids)

    def test_agreeing_solvers_and_replays_are_no_problem_and_the_tables_give_medians(self):
        r = results([check("cadical", seconds=1.0), check("cadical", seconds=3.0, run=2), check("bitwuzla", seconds=5.0)],
                    [replay("cadical"), replay("bitwuzla", seconds=2.0)])
        self.assertEqual(compare.problems(r), [])
        table = compare.render(r)
        self.assertIn("| held/reverse | cadical | verified | 2.000 (1.000–3.000) | 115 | 59707 | 1.000 (0.500–1.500) | 40 |", table)
        self.assertIn("| held/reverse | 1-1.icnf | 115 | 59707 | bitwuzla | 2.000 | 1.000 | 0 |", table)
        self.assertIn("- bitwuzla 1.0", table)
        self.assertIn("None: every decisive verdict", table)
        self.assertIn("Nothing: every check gave a verdict", table)

    def test_a_wrong_verdict_a_disagreement_and_a_contradiction_are_problems(self):
        r = results([check("cadical"), check("bitwuzla", verdict="violation")], [replay("bitwuzla", contradictions=2), {"case": "held/reverse", "transcript": "1-1.icnf", "solver": "cadical", "run": 1, "exit": 2, "problem": "no such file"}])
        found = compare.problems(r)
        self.assertEqual(len(found), 4, found)
        self.assertTrue(any("expected verified" in p for p in found))
        self.assertTrue(any("verdicts differ" in p for p in found))
        self.assertTrue(any("2 contradictions" in p for p in found))
        self.assertTrue(any("the replay failed" in p for p in found))
        self.assertIn("| held/reverse | 1-1.icnf | – | – | cadical | – | – | failed |", compare.render(r))

    def test_another_solver_out_of_time_is_not_decided_but_cadical_out_of_time_is_a_problem(self):
        slow = dict(check("bitwuzla", verdict="unverifiable"), reason="out of time")
        late = dict(replay("bitwuzla"), undecided=3)
        r = results([check("cadical"), slow], [late])
        self.assertEqual(compare.problems(r), [])
        self.assertEqual(len(compare.undecided(r)), 2, compare.undecided(r))
        self.assertIn("out of time", compare.render(r))
        r = results([dict(check("cadical", verdict="unverifiable"), reason="out of time")], [])
        self.assertEqual(len(compare.problems(r)), 1)


if __name__ == "__main__":
    unittest.main()
