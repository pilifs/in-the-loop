#!/usr/bin/env python3
"""inbox.py on made-up streams: the only-what-to-act-on rule it holds the conductor to, the link to the
decision record, the inbox a stream reads, the sentence feature-loop.sh adds, and a two-stream fixture
run in a real jj repository (a default workspace and one per stream) where each stream acknowledges, or
reports, what it was sent through its committed Progress."""

import contextlib
import io
import itertools
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import decisions
import inbox
from test_decisions import decided

TOOLS = Path(__file__).resolve().parent
RUN = "2026-11-14T20:00:00Z"


def brief(stream: str, progress: list[str]) -> str:
    return "\n".join([f"# Brief: made-up stream {stream}", "", "## Direction", "", "Made up.", "",
                      "## Progress", "", *progress, "- Status: working", "",
                      "## Loop settings", "", f"- workspace: made-up-{stream}", ""])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.root = self.base_dir / "root"
        (self.root / "llm-dlc" / "loops").mkdir(parents=True)
        for s in ("a", "b"):
            (self.root / "llm-dlc" / "loops" / f"made-up-{s}.md").write_text(brief(s, ["- made up: started."]))
        self.folder = self.root / "llm-dlc" / "loop-summaries"
        self.decisions = self.root / "llm-dlc" / "decisions"
        clock = (f"2026-11-14T21:{m:02d}:{s:02d}Z" for m, s in itertools.product(range(60), range(60)))
        self.clock = mock.patch.object(decisions, "now", lambda: next(clock))
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        self.tmp.cleanup()

    def record(self, data) -> None:
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = decisions.main(["record", "made-up", "--run", RUN], root=self.decisions,
                                  stdin=io.StringIO(json.dumps(data)))
        self.assertEqual(code, 0, err.getvalue())

    def run_cli(self, *argv, repo=None) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = inbox.main(list(argv), repo=repo or self.root)
        return code, out.getvalue(), err.getvalue()

    def send(self, stream, kind, do, *extra, repo=None) -> str:
        code, out, err = self.run_cli("send", f"made-up-{stream}", "--kind", kind, "--do", do, *extra, repo=repo)
        self.assertEqual(code, 0, err)
        return re.search(r"sent (\S+)", out)[1]

    def items(self, stream) -> list[dict]:
        return inbox.fold(inbox.read(f"made-up-{stream}", self.folder))

    def applied(self, i) -> list[dict]:
        return decisions.fold(decisions.read("made-up", self.decisions))[i]["applied"]["inbox"]


class Rules(Base):
    """What may be sent, without jj: send reads only the briefs and the decision record."""

    def setUp(self):
        super().setUp()
        # Outside a jj repo, the default workspace is the repo itself.
        self.default = mock.patch.object(inbox, "default_root", lambda repo=None: self.root)
        self.default.start()

    def tearDown(self):
        self.default.stop()
        super().tearDown()

    def test_the_sentence_names_the_default_workspaces_inbox_the_acknowledgement_and_the_precedence(self):
        s = inbox.instruction("made-up-a")
        self.assertIn("`$(jj workspace root --name default)/llm-dlc/loop-summaries/made-up-a-inbox.md`", s)
        self.assertIn("acknowledge each by its id in this cycle's Progress update", s)
        self.assertIn("below your brief and the user's decisions", s)
        self.assertIn("contradicts the brief is reported in Progress, by its id, not obeyed", s)
        self.assertEqual(s.count(". "), 0, "one sentence")
        self.assertEqual(self.run_cli("instruction", "made-up-a")[1].strip(), s)

    def test_feature_loop_adds_the_sentence_to_every_brief_cycles_instruction(self):
        script = (TOOLS / "feature-loop.sh").read_text()
        block = script[script.index('if [[ -n "$BRIEF" ]]; then\n  BRIEF_HASH'):]
        block = block[:block.index("\nfi\n")]
        self.assertIn('INSTRUCTION="$INSTRUCTION $(python3 llm-dlc/tools/inbox.py instruction "$PROMPT")" || exit 1',
                      block)

    def test_only_what_a_stream_acts_on_is_sent_and_a_refusal_writes_nothing(self):
        refusals = [
            (["made-up-a", "--kind", "upkeep", "--do", "Nothing: the report file was renamed.", "--commit", "c1"],
             "stay out of its inbox"),
            (["made-up-a", "--kind", "failure", "--do", " ", "--commit", "c1"], "says what the stream is to do"),
            (["made-up-a", "--kind", "unblocked", "--do", "Go on with A3."], "neither a decision nor a commit"),
            (["made-up-c", "--kind", "unblocked", "--do", "Go on.", "--commit", "c1"], "no stream brief"),
        ]
        for argv, why in refusals:
            with self.subTest(why):
                code, _, err = self.run_cli("send", *argv)
                self.assertEqual(code, 1)
                self.assertIn(why, err)
        self.assertFalse(self.folder.exists())

    def test_a_decision_must_be_in_the_state_the_kind_needs(self):
        self.record([decided(), {**decided(), "state": "open", "decision": None}])
        code, _, err = self.run_cli("send", "made-up-a", "--kind", "interface", "--do", "Adapt.", "--decision", "D002")
        self.assertEqual(code, 1)
        self.assertIn("made-up-D002 is open: an item of kind interface names a decision that is decided", err)
        code, _, err = self.run_cli("send", "made-up-a", "--kind", "queued", "--do", "Go on.", "--decision", "D001")
        self.assertIn("made-up-D001 is decided", err)
        code, _, err = self.run_cli("send", "made-up-a", "--kind", "overturned", "--do", "Undo.", "--decision", "D001")
        self.assertIn("names the decision that replaced the overturned one", err)
        self.assertEqual(self.applied("made-up-D001"), [])
        item = self.send("a", "queued", "Go on with A4 while the user answers.", "--decision", "D002")
        self.assertEqual(self.applied("made-up-D002"), [{"stream": "made-up-a", "item": item}])

    def test_an_item_for_a_decision_is_added_to_its_applied_inbox_and_the_record_stays_clean(self):
        self.record(decided())
        a = self.send("a", "interface", "parse() returns a Result; adapt load() to it.", "--decision", "D001")
        b = self.send("b", "interface", "Call parse() and handle its Result.", "--decision", "made-up-D001",
                      "--commit", "c0ffee12")
        self.assertEqual((a, b), ("made-up-a-I001", "made-up-b-I001"))
        self.assertEqual(self.applied("made-up-D001"), [{"stream": "made-up-a", "item": a},
                                                        {"stream": "made-up-b", "item": b}])
        self.assertEqual(decisions.problems(self.decisions), [])
        self.assertIn("made-up-b inbox `made-up-b-I001`", decisions.view_path("made-up", self.decisions).read_text())
        self.assertEqual(self.items("b")[0]["from"], {"decisions": ["made-up-D001"], "commits": ["c0ffee12"]})
        self.assertEqual(self.send("a", "unblocked", "Go on with A3.", "--commit", "c1"), "made-up-a-I002")

    def test_the_inbox_shows_open_items_in_full_and_acknowledged_ones_on_a_line(self):
        self.send("a", "failure", "Fix load(): the merged tree's test_load fails.", "--commit", "c1",
                  "--detail", "AssertionError in test_load.py:12, after b's parse() change.")
        self.send("a", "unblocked", "Go on with A3.", "--commit", "c2")
        inbox.append("made-up-a", self.folder, [{"kind": "ack", "id": "made-up-a-I002", "seq": 0, "at": RUN,
                                                 "commit": "abcd1234", "said": "made-up-a-I002: going on with A3."}])
        text = inbox.inbox_path("made-up-a", self.folder).read_text()
        self.assertIn("## Open (1)", text)
        self.assertIn("### made-up-a-I001: an integration failure in your code", text)
        self.assertIn("**Do:** Fix load(): the merged tree's test_load fails.", text)
        self.assertIn("AssertionError in test_load.py:12", text)
        self.assertIn("from commit `c1`", text)
        self.assertIn("- `made-up-a-I002` (unblocked, sent 2026-11-14 21:00:01 UTC): acknowledged in `abcd1234`: "
                      "made-up-a-I002: going on with A3.", text)
        self.assertIn("**Precedence:** your brief, then the user's decisions, then these messages.", text)
        self.assertLess(text.index("## Open"), text.index("## Acknowledged"))

    def test_the_lines_are_checked(self):
        lines = [{"kind": "item", "id": "made-up-b-I001", "seq": 1, "at": RUN, "about": "news", "do": "",
                  "from": {}},
                 {"kind": "ack", "id": "made-up-a-I009", "seq": 3, "at": RUN, "commit": "x"}]
        found = inbox.line_problems("made-up-a", lines)
        for expected in ["line 1: 'made-up-b-I001' is not an item id of this inbox",
                         "line 1: kind of item 'news' is not one a stream acts on",
                         "line 1: no `do`", "line 1: names neither a decision nor a commit",
                         "line 2: seq is 3, not 2", "line 2: acknowledges made-up-a-I009, which was not sent"]:
            self.assertTrue(any(expected in p for p in found), f"{expected!r} not in {found}")


@unittest.skipUnless(shutil.which("jj"), "needs jj")
class TwoStreams(Base):
    """A fixture run: a default workspace where the conductor sends, and two streams in their own workspaces
    that read their inbox through the sentence's path and acknowledge in committed Progress."""

    def setUp(self):
        super().setUp()
        self.env = mock.patch.dict(os.environ, {"JJ_USER": "Made Up", "JJ_EMAIL": "made-up@example.com",
                                                "JJ_CONFIG": str(self.base_dir / "jj-config.toml")})
        self.env.start()
        (self.base_dir / "jj-config.toml").write_text("")
        (self.root / ".gitignore").write_text("llm-dlc/loop-summaries/\n")
        self.jj(self.root, "git", "init", "--colocate")
        self.jj(self.root, "commit", "-m", "base: two made-up stream briefs")
        self.ws = {}
        for s in ("a", "b"):
            self.ws[s] = self.base_dir / f"made-up-{s}"
            self.jj(self.root, "workspace", "add", "--name", f"made-up-{s}", "-r", "@-", str(self.ws[s]))

    def tearDown(self):
        self.env.stop()
        super().tearDown()

    def jj(self, where: Path, *args: str) -> str:
        r = subprocess.run(["jj", *args], cwd=where, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def stream_commits(self, s: str, progress: list[str]) -> str:
        """Stream s's cycle: its Progress updated, committed in its own workspace, as feature-loop.sh leaves it."""
        (self.ws[s] / "llm-dlc" / "loops" / f"made-up-{s}.md").write_text(brief(s, ["- made up: started.", *progress]))
        self.jj(self.ws[s], "commit", "-m", f"stream {s}: a cycle")
        return self.jj(self.ws[s], "log", "--no-graph", "-r", "@-", "-T", "change_id.short(8)").strip()

    def open_ids(self, s: str) -> list[str]:
        return [i["id"] for i in self.items(s) if not i["ack"]]

    def read_as_stream(self, s: str) -> str:
        """The inbox, found as the stream's session would: the sentence's path, run by a shell in its workspace."""
        path = re.search(r"`([^`]+-inbox\.md)`", inbox.instruction(f"made-up-{s}"))[1]
        found = subprocess.run(["bash", "-c", f'echo "{path}"'], cwd=self.ws[s], capture_output=True, text=True)
        return Path(found.stdout.strip()).read_text()

    def test_two_streams_are_sent_only_what_they_act_on_and_acknowledge_it_in_progress(self):
        # The integration line finds a's load() and b's parse() disagree; the conductor decides how they meet.
        self.record(decided())
        ia = self.send("a", "interface", "parse() returns a Result: adapt load() to it.", "--decision", "D001")
        ib = self.send("b", "interface", "Keep parse() returning a Result; a adapts.", "--decision", "D001",
                       repo=self.ws["b"])  # sent from a stream's workspace, it still lands in the default one
        self.assertTrue(inbox.inbox_path("made-up-b", self.folder).exists())
        self.assertFalse((self.ws["b"] / "llm-dlc" / "loop-summaries").exists())
        # Upkeep changes nothing for either stream: no kind fits, nothing is sent.
        self.record({**decided(), "asked": {"by": "conductor", "question": "Where does the report go?"}})
        self.assertEqual(self.run_cli("send", "made-up-a", "--kind", "upkeep", "--do", "None.", "--decision",
                                      "D002")[0], 1)
        self.assertEqual(self.applied("made-up-D002"), [])
        # Each stream finds its own inbox through the sentence, and only its own item in it.
        seen = {s: self.read_as_stream(s) for s in ("a", "b")}
        self.assertIn(ia, seen["a"])
        self.assertNotIn(ib, seen["a"])
        self.assertIn(ib, seen["b"])
        # a acknowledges in its next commit; b commits a cycle that doesn't mention its item.
        ca = self.stream_commits("a", [f"- 2026-11-14, load() adapted to parse()'s Result ({ia})."])
        self.stream_commits("b", ["- 2026-11-14, B2 done."])
        code, out, _ = self.run_cli("collect")
        self.assertEqual(code, 0)
        self.assertIn(f"made-up-a: 1 acknowledged now ({ia}), 0 open", out)
        self.assertIn("made-up-b: 0 acknowledged now, 1 open", out)
        ack = self.items("a")[0]["ack"]
        self.assertEqual((ack["commit"], ack["said"]), (ca, f"2026-11-14, load() adapted to parse()'s Result ({ia})."))
        self.assertIn("## Open (0)", self.read_as_stream("a"))
        self.assertEqual(self.run_cli("list", "--open")[1].split("\t")[0], ib)
        # An uncommitted Progress edit is not an acknowledgement: only a commit's Progress counts.
        (self.ws["b"] / "llm-dlc" / "loops" / "made-up-b.md").write_text(brief("b", [f"- {ib}: noted."]))
        self.jj(self.ws["b"], "status")  # snapshotted into b's working copy, still not committed
        self.run_cli("collect", "made-up-b")
        self.assertEqual(self.open_ids("b"), [ib])
        # The user overturns D001; the conductor supersedes it and tells both streams, with the undo.
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(decisions.main(["review", "overturn", "D001", "--note", "a's Result stays internal"],
                                            root=self.decisions), 0)
        self.record([{**decided(option="b", by="user"), "supersedes": "made-up-D001"},
                     {"id": "made-up-D001", "state": "superseded"}])
        oa = self.send("a", "overturned", "Undo the load() adapter; parse() goes back to raising.",
                       "--decision", "D003", "--decision", "D001", "--commit", ca)
        ob = self.send("b", "overturned", "parse() raises again: drop the Result.", "--decision", "D003")
        self.assertEqual(self.applied("made-up-D001")[-1], {"stream": "made-up-a", "item": oa})
        self.assertEqual(self.applied("made-up-D003"), [{"stream": "made-up-a", "item": oa},
                                                        {"stream": "made-up-b", "item": ob}])
        self.assertEqual(decisions.problems(self.decisions), [])
        # b reports its stale item as contradicting its brief and takes the new one; a takes its undo.
        self.stream_commits("b", [f"- {ib}: reported, not obeyed: the brief has b own parse(), and {ob} replaces it.",
                                  f"- 2026-11-14, parse() raises again ({ob})."])
        self.stream_commits("a", [f"- 2026-11-14, the load() adapter undone ({oa})."])
        self.run_cli("collect")
        self.assertEqual((self.open_ids("a"), self.open_ids("b")), ([], []))
        self.assertTrue(self.items("b")[0]["ack"]["said"].startswith(f"{ib}: reported, not obeyed"))
        self.assertEqual(inbox.line_problems("made-up-b", inbox.read("made-up-b", self.folder)), [])
        # Collecting again finds nothing new.
        self.assertIn("made-up-a: 0 acknowledged now, 0 open", self.run_cli("collect")[1])


if __name__ == "__main__":
    unittest.main()
