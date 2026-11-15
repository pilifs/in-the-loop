#!/usr/bin/env python3
"""Tests for streams_status.py, on made-up loop output. Run: python3 llm-dlc/tools/test_streams_status.py"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import streams_status
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

HERE = Path(__file__).resolve().parent

OUTPUT = """[2000-01-01 10:00:00] cycle 1, no limit: the loop runs until stopped
[2000-01-01 10:20:00] says: working on H1
[2000-01-01 10:40:00] turn done: success, 80 steps, 40.0 min, $3.25
[2000-01-01 10:41:00] cycle 1: asking whether to go on
[2000-01-01 10:42:00] turn done: success, 2 steps, 0.5 min, $3.35
[2000-01-01 10:43:00] cycle 2
a line that isn't UTF-8: \xff
"""

# The same session resumed after a restart of run-streams.sh: its totals go on from 3.35.
RESUMED = """[2000-01-01 11:00:00] cycle 2, no limit: the loop runs until stopped
[2000-01-01 11:30:00] turn done: success, 60 steps, 30.0 min, $5.10
[2000-01-01 11:31:00] turn done: success, 2 steps, 0.5 min, $5.20
"""

# A stream forked from the planning session, whose total was $28.30 then.
FORKED = """[2000-01-01 10:00:00] starting session 0000 as a fork of 1111
[2000-01-01 10:01:00] turn done: success, 1 steps, 0.2 min, $28.32
[2000-01-01 10:02:00] cycle 1, no limit: the loop runs until stopped
[2000-01-01 10:40:00] turn done: success, 80 steps, 38.0 min, $31.07
[2000-01-01 10:41:00] turn done: success, 2 steps, 0.5 min, $31.12
"""

BRIEF = """# Stream brief

## Progress

- Did something.
- Status: `working`

## Loop settings

- Status: not this one
"""


class Tag(unittest.TestCase):
    @cost("tool")
    def test_prefixes_every_line_and_keeps_the_state(self):
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run([sys.executable, str(HERE / "streams_status.py"), "tag", "heap", d],
                                  input=OUTPUT.encode("latin-1"), capture_output=True, check=True)
            lines = proc.stdout.decode("latin-1").splitlines()
            self.assertEqual(len(lines), len(OUTPUT.splitlines()))
            self.assertTrue(all(line.startswith("[heap] ") for line in lines))
            self.assertAlmostEqual(streams_status.spend(d, "heap"), 3.35)
            self.assertEqual((Path(d) / "heap.cost").read_text(), "3.25\n3.35\n")
            self.assertEqual((Path(d) / "heap.cycle").read_text().strip(), "2")
            self.assertTrue((Path(d) / "heap.last").read_text().strip().isdigit())

    def tagged(self, d, *outputs):
        for output in outputs:
            subprocess.run([sys.executable, str(HERE / "streams_status.py"), "tag", "heap", d],
                           input=output.encode("latin-1"), capture_output=True, check=True)
        return streams_status.spend(d, "heap")

    @cost("tool")
    def test_each_figure_is_the_sessions_total_so_far_so_spend_is_its_rise(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertAlmostEqual(self.tagged(d, OUTPUT, RESUMED), 5.20)

    @cost("tool")
    def test_a_forks_first_figure_is_its_parents_total_not_spend(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertAlmostEqual(self.tagged(d, FORKED), 2.80)
            self.assertEqual((Path(d) / "heap.cost").read_text().split()[:2], ["=28.32", "31.07"])

    @cost("tool")
    def test_a_figure_below_the_last_starts_a_new_session_counted_whole(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertAlmostEqual(self.tagged(d, FORKED, OUTPUT), 2.80 + 3.35)


class Render(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.state = root / "state"
        self.state.mkdir()
        self.ws = root / "ws"
        (self.ws / "llm-dlc" / "loops").mkdir(parents=True)
        (self.ws / "llm-dlc" / "loop-summaries").mkdir(parents=True)
        (self.ws / "llm-dlc" / "loops" / "x-heap.md").write_text(BRIEF)
        for n, name in enumerate(["2000-01-01-100000-x-heap.md", "2000-01-02-100000-x-heap.md"]):
            (self.ws / "llm-dlc" / "loop-summaries" / name).write_text(
                "# Run\n\n- cycle 1, 2000-01-01 10:40:00, `abc`: first\n" + ("- cycle 2, x, `d`: second\n" if n else ""))
        (self.ws / "llm-dlc" / "loop-summaries" / "2000-01-01-100000-x-native.md").write_text("- cycle 1, x, `e`: other\n")
        (self.state / "heap.cost").write_text("3.25\n3.35\n")
        (self.state / "heap.cycle").write_text("2\n")
        (self.state / "heap.last").write_text("1000\n")

    def tearDown(self):
        self.tmp.cleanup()

    def line(self, phase, **kw):
        (self.state / "heap.phase").write_text(phase + "\n")
        return streams_status.render("x", self.state, 0, [("heap", self.ws, "llm-dlc/loops/x-heap.md")], now=1150, **kw)

    def test_a_running_loop_shows_cycle_commits_spend_its_status_and_idle_time(self):
        self.assertEqual(self.line("running"), "x 19m $3.35 │ heap c2 3✓ $3.35 working 2m")

    def test_a_finished_loop_shows_its_phase_and_no_idle_time(self):
        self.assertEqual(self.line("finished: done"), "x 19m $3.35 │ heap c2 3✓ $3.35 done")

    def test_a_loop_with_no_phase_is_left_out_but_its_spend_counts(self):
        line = streams_status.render("x", self.state, 0, [("heap", self.ws, "llm-dlc/loops/x-heap.md")], now=1150)
        self.assertEqual(line, "x 19m $3.35")

    def test_the_integration_result(self):
        report = Path(self.tmp.name) / "x-integration.md"
        report.write_text("# Integration check\n\n- Result: passed (exit 0)\n")
        self.assertRegex(self.line("running", integration=report), r"^x 19m \$3.35 │ integration passed \S+ ago │ heap ")

    def test_ages(self):
        self.assertEqual([streams_status.age(s) for s in (5, 125, 3 * 3600 + 120, 2 * 86400 + 3600)],
                         ["5s", "2m", "3h02m", "2d01h"])


if __name__ == "__main__":
    unittest.main()
