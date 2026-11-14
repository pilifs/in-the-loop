#!/usr/bin/env python3
"""Tests for integration.py, the rolling integration line (stream-conductor.md, Design 1 and plan step 3).

All on made-up data: a real jj repository in a temporary directory, with a default workspace (where the
decision record, the inboxes and the report are), two stream workspaces and the integration workspace.
"""
from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import decisions
import inbox
import integration
import streams_status
from test_inbox import brief

TOOLS = Path(__file__).resolve().parent
STREAMS = [("a", "made-up-a"), ("b", "made-up-b")]

# A stand-in for sync.py regenerate: generated.txt lists the session files, and is rewritten from them.
FAKE_SYNC = textwrap.dedent('''\
    import subprocess, sys
    from pathlib import Path
    if sys.argv[1:] != ["regenerate"]:
        sys.exit(2)
    listed = subprocess.run(["jj", "resolve", "--list"], capture_output=True, text=True).stdout
    Path("generated.txt").write_text("".join(sorted(p.name + "\\n" for p in Path("sessions").glob("*"))))
    if "generated.txt" in listed:
        print("regenerated: generated.txt")
''')
# The brief's integration script: the merged tree's tests, and a file it leaves behind, as builds do.
CHECK = "echo built > junk.log\npython3 -m unittest discover -s tests -t . 2>&1\n"


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "root"
        self.env = mock.patch.dict(os.environ, {"JJ_USER": "Made Up", "JJ_EMAIL": "made-up@example.com",
                                                "JJ_CONFIG": str(base / "jj-config.toml")})
        self.env.start()
        (base / "jj-config.toml").write_text("")
        files = {
            ".gitignore": "llm-dlc/loop-summaries/\n",
            "llm-dlc/loops/made-up.md": "# Brief: made up\n",
            "llm-dlc/tools/sync.py": FAKE_SYNC,
            "check.sh": CHECK,
            "lib/__init__.py": "",
            "lib/parse.py": "def parse(text):\n    return text.split(',')\n",
            "lib/shared.txt": "one\n",
            "tests/__init__.py": "",
            "tests/test_parse.py": "import unittest\nfrom lib.parse import parse\n\n\nclass T(unittest.TestCase):\n"
                                   "    def test_it(self):\n        self.assertTrue(parse('x,y'))\n",
            "sessions/base": "",
            "generated.txt": "base\n",
        }
        for s in ("a", "b"):
            files[f"llm-dlc/loops/made-up-{s}.md"] = brief(s, ["- made up: started."])
        for path, text in files.items():
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text(text)
        self.jj(self.root, "git", "init", "--colocate")
        self.jj(self.root, "commit", "-m", "base: a made-up brief, two streams and an integration script")
        self.ws = {}
        for s in ("a", "b", "integration"):
            self.ws[s] = base / f"made-up-{s}"
            self.jj(self.root, "workspace", "add", "--name", f"made-up-{s}", "-r", "@-", str(self.ws[s]))
        self.report = self.root / "llm-dlc" / "loop-summaries" / "made-up-integration.md"
        self.decisions = self.root / "llm-dlc" / "decisions"
        self.folder = self.root / "llm-dlc" / "loop-summaries"
        self.minute = 0

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def jj(self, where: Path, *args: str) -> str:
        r = subprocess.run(["jj", *args], cwd=where, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def commit(self, s: str, files: dict[str, str], message: str) -> None:
        """Stream s's cycle: its files, and a session file with the generated file it changes, committed."""
        files = {f"sessions/{s}{self.minute}": "", "generated.txt": f"{s}{self.minute}\n", **files}
        for path, text in files.items():
            (self.ws[s] / path).parent.mkdir(parents=True, exist_ok=True)
            (self.ws[s] / path).write_text(text)
        self.jj(self.ws[s], "commit", "-m", message)

    def integrate(self) -> dict:
        self.minute += 1
        return integration.run("made-up", self.ws["integration"], STREAMS, ["bash", "check.sh"], self.report,
                               root=self.root, stamp=f"2026-11-14T22:{self.minute:02d}:00Z")

    def items(self, s: str) -> list[dict]:
        return inbox.fold(inbox.read(f"made-up-{s}", self.folder))

    def record(self) -> dict[str, dict]:
        return decisions.fold(decisions.read("made-up", self.decisions))

    def line(self) -> str | None:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = integration.main(["line", "made-up"], root=self.root)
        return out.getvalue().strip() if code == 0 else None

    def test_the_line_commits_what_passes_and_triages_what_fails(self):
        self.assertIsNone(self.line())
        # 1. Both streams commit, so the generated file conflicts: regenerated, the script passes, and the
        #    merge is committed on the line, without what the script wrote.
        self.commit("a", {"lib/extra.py": "X = 1\n"}, "a: an extra module")
        self.commit("b", {"docs.txt": "b's notes\n"}, "b: notes")
        out = self.integrate()
        self.assertEqual(out["result"], "passed", self.report.read_text())
        first = out["commit"]
        self.assertEqual(self.line(), first)
        report = self.report.read_text()
        self.assertIn("- Regenerated, as generated trace files in conflict: generated.txt", report)
        self.assertIn(f"- Result: passed (exit 0), committed on the integration line as {first}", report)
        self.assertRegex(streams_status.render("made-up", self.tmp.name, 0, [], integration=self.report),
                         r"│ integration passed \S+ ago")
        tree = self.jj(self.root, "file", "list", "-r", first)
        self.assertIn("lib/extra.py", tree)
        self.assertIn("docs.txt", tree)
        self.assertNotIn("junk.log", tree)
        self.assertNotIn("__pycache__", tree)
        self.assertEqual(self.jj(self.root, "file", "show", "-r", first, "generated.txt"), "a0\nb0\nbase\n")
        description = self.jj(self.root, "log", "--no-graph", "-r", first, "-T", "description")
        self.assertIn("Integration-Line: made-up\n", description)
        self.assertRegex(description, r"Integration-Head: a [0-9a-f]{40}\nIntegration-Head: b [0-9a-f]{40}")
        self.assertFalse(self.decisions.exists())
        self.assertEqual(self.items("a") + self.items("b"), [])

        # 2. a changes parse() and b starts calling it the old way: each passes alone, the merge fails. The
        #    traceback names both sides' files, so it is a disagreement: an open decision and a queued item each.
        self.commit("a", {"lib/parse.py": "def parse(text):\n    key, value = text.split('=')\n"
                                          "    return {key: value}\n",
                          "tests/test_parse.py": "import unittest\nfrom lib.parse import parse\n\n\n"
                                                 "class T(unittest.TestCase):\n    def test_it(self):\n"
                                                 "        self.assertEqual(parse('x=y'), {'x': 'y'})\n"},
                    "a: parse() reads key=value")
        self.commit("b", {"app/__init__.py": "", "app/report.py": "from lib.parse import parse\n\n\n"
                                                                  "def report():\n    return parse('x,y')\n",
                          "tests/test_report.py": "import unittest\nfrom app.report import report\n\n\n"
                                                  "class T(unittest.TestCase):\n    def test_it(self):\n"
                                                  "        self.assertTrue(report())\n"},
                    "b: a report")
        out = self.integrate()
        self.assertEqual(out["result"], "failed", self.report.read_text())
        self.assertEqual(out["streams"], ["a", "b"])
        self.assertEqual(out["files"], ["app/report.py", "lib/parse.py", "tests/test_report.py"])
        d1 = out["decision"]
        self.assertEqual(d1, "made-up-D001")
        d = self.record()[d1]
        self.assertEqual((d["state"], d["asked"]["by"]), ("open", "integration"))
        self.assertEqual(d["asked"]["question"], "The changes of a (lib/parse.py) and b (app/report.py, "
                         "tests/test_report.py) don't work together: the integration script fails on the merge of "
                         "every stream's latest commit (exit 1). How do they meet?")
        self.assertEqual([o["id"] for o in d["options"]], ["a-stands", "b-stands", "rule", "settled"])
        self.assertEqual(d["options"][0]["consequences"],
                         "b (app/report.py, tests/test_report.py) changes its side to fit a's; a changes nothing")
        self.assertEqual(d["context"]["files"], out["files"])
        for s in ("a", "b"):
            [item] = self.items(s)
            self.assertEqual((item["about"], item["from"]["decisions"]), ("queued", [d1]))
            self.assertIn(f"until {d1} says how your side and {'b' if s == 'a' else 'a'}'s meet", item["do"])
            self.assertIn("lib/parse.py", item["detail"])
        self.assertEqual([a["stream"] for a in d["applied"]["inbox"]], ["made-up-a", "made-up-b"])
        self.assertEqual(self.line(), first, "a failing merge is not committed")
        self.assertEqual(self.jj(self.ws["integration"], "log", "--no-graph", "-r", "@", "-T", "description"), "")
        report = self.report.read_text()
        self.assertIn("- Result: failed (exit 1), not committed", report)
        self.assertIn(f"- Decision: {d1}, open", report)
        self.assertIn("ValueError", report)
        self.assertRegex(streams_status.render("made-up", self.tmp.name, 0, [], integration=self.report),
                         r"integration failed \S+ ago")

        # 3. b commits something else and the same failure shows: nothing new is sent.
        self.commit("b", {"docs.txt": "more notes\n"}, "b: more notes")
        out = self.integrate()
        self.assertEqual((out["result"], out["decision"], out["items"]), ("failed", d1, []))
        self.assertIn("- The same failure as at", self.report.read_text())
        self.assertEqual(len(self.items("a") + self.items("b")), 2)

        # 4. b adapts on its own: the merge passes, onto the line's previous merge, and D001 is settled,
        #    each side told it may go on.
        self.commit("b", {"app/report.py": "from lib.parse import parse\n\n\ndef report():\n"
                                           "    return parse('x=y')\n"}, "b: report() uses key=value")
        out = self.integrate()
        self.assertEqual(out["result"], "passed", self.report.read_text())
        second = out["commit"]
        self.assertEqual(out["settled"], [d1])
        self.assertEqual(self.line(), second)
        parents = self.jj(self.root, "log", "--no-graph", "-r", f"{second}-", "-T", 'change_id.short(8) ++ "\\n"')
        self.assertIn(first, parents.split(), "each passing merge has the previous one as a parent")
        d = self.record()[d1]
        self.assertEqual((d["state"], d["decision"]["option"], d["decision"]["by"], d["review"]["state"]),
                         ("decided", "settled", "conductor", "unreviewed"))
        self.assertEqual((d["decision"]["confidence"]["level"], d["decision"]["recovery"]["class"]), ("high", "cheap"))
        self.assertIn(second, d["applied"]["commits"])
        for s in ("a", "b"):
            self.assertEqual([i["about"] for i in self.items(s)], ["queued", "unblocked"])
        self.assertIn(f"- Settled, as the merge passes: {d1}", self.report.read_text())
        self.assertEqual(decisions.problems(self.decisions), [])

        # 5. Both streams change the same source file: a textual conflict, so the script isn't run.
        self.commit("a", {"lib/shared.txt": "one, as a has it\n"}, "a: shared")
        self.commit("b", {"lib/shared.txt": "one, as b has it\n"}, "b: shared")
        out = self.integrate()
        self.assertEqual((out["result"], out["files"], out["streams"]), ("conflict", ["lib/shared.txt"], ["a", "b"]))
        d2 = out["decision"]
        self.assertEqual(d2, "made-up-D002")
        self.assertEqual(self.record()[d2]["asked"]["question"],
                         "The streams a and b both changed lib/shared.txt, and their changes to it conflict when "
                         "merged: how do they meet?")
        report = self.report.read_text()
        self.assertIn("- Result: conflict in 1 file, not committed; the script was not run.", report)
        self.assertNotIn("## Output", report)
        self.assertEqual([i["about"] for i in self.items("b")], ["queued", "unblocked", "queued"])

        # 6. b takes a's side of the file, but adds a test of its own that fails: that is b's alone, a failure
        #    item for b, and no decision. D002 stays open: nothing passed.
        self.commit("b", {"lib/shared.txt": "one, as a has it\n",
                          "tests/test_b.py": "import unittest\n\n\nclass B(unittest.TestCase):\n"
                                             "    def test_b(self):\n        self.fail('b is not done')\n"},
                    "b: takes a's shared, and a new test")
        out = self.integrate()
        self.assertEqual((out["result"], out["streams"], out["files"], out["decision"]),
                         ("failed", ["b"], ["tests/test_b.py"], None))
        last = self.items("b")[-1]
        self.assertEqual((last["about"], last["from"]["decisions"]), ("failure", []))
        self.assertEqual(last["do"], "The merge of every stream's latest commit fails the integration script "
                                     "(exit 1) in tests/test_b.py, which only your changes touch: fix it in your "
                                     "next cycle. The output is in llm-dlc/loop-summaries/made-up-integration.md.")
        self.assertEqual([i["about"] for i in self.items("a")], ["queued", "unblocked", "queued"])
        self.assertEqual(self.record()[d2]["state"], "open")
        self.assertEqual(decisions.problems(self.decisions), [])

    def test_unchanged_heads_and_a_missing_workspace(self):
        self.commit("a", {"lib/extra.py": "X = 1\n"}, "a: an extra module")
        self.assertEqual(self.integrate()["result"], "passed")
        out = self.integrate()
        self.assertEqual(out["result"], "unchanged")
        self.assertIn("- Result: unchanged (", self.report.read_text())
        out = integration.run("made-up", self.ws["integration"], STREAMS + [("c", "made-up-c")], ["true"],
                              self.report, root=self.root)
        self.assertEqual(out["result"], "error")
        self.assertIn("- Result: error (the stream c's workspace made-up-c", self.report.read_text())


class Attribution(unittest.TestCase):
    def test_files_the_output_names(self):
        where = Path("/made/up/ws")
        candidates = {"app/report.py", "lib/parse.py", "src/main/java/x/Foo.java", "docs/notes.txt", "a/same.py",
                      "b/same.py"}
        output = textwrap.dedent('''\
            Traceback (most recent call last):
              File "/made/up/ws/app/report.py", line 5, in report
            ./lib/parse.py:2: ValueError
                at x.Foo.run(Foo.java:12)
            same.py: two candidates end in this name
            notes.txt is named, but so is untracked.py
        ''')
        self.assertEqual(integration.named_files(output, where, candidates),
                         {"app/report.py", "lib/parse.py", "src/main/java/x/Foo.java", "a/same.py", "b/same.py",
                          "docs/notes.txt"})
        self.assertEqual(integration.named_files("all fine", where, candidates), set())

    def test_excerpt_keeps_the_lines_naming_the_files(self):
        output = "\n".join([f"line {n}" for n in range(30)] + ["  File \"x/lib/parse.py\", line 2"])
        self.assertEqual(integration.excerpt(output, ["lib/parse.py"]), '  File "x/lib/parse.py", line 2')
        self.assertEqual(integration.excerpt(output, []).splitlines()[0], "line 19")


class RunStreams(unittest.TestCase):
    def test_run_streams_calls_the_line_with_its_scope_around_the_script_only(self):
        text = (TOOLS / "run-streams.sh").read_text()
        body = text[text.index("integrate_once() {"):text.index("\n}\n", text.index("integrate_once() {"))]
        self.assertIn('python3 "$ROOT/llm-dlc/tools/integration.py" run --name "$(basename "$BRIEF" .md)"', body)
        self.assertRegex(body, r'-- systemd-run --user --scope [^\n]*\\\n[^\n]*\\\n\s*timeout 3600 '
                               r'"\$INTEGRATION_DIR/\$INTEGRATION"')
        self.assertNotIn("jj new", body, "the merge is integration.py's now")


if __name__ == "__main__":
    unittest.main()
