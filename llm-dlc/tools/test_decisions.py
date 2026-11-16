#!/usr/bin/env python3
"""decisions.py on made-up decision records: the conductor's writes and what it may decide alone, the
user's reviews and answers, an overturn after dependents grew, the view's order, and check's problems."""

import contextlib
import io
import itertools
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import decisions

NAME = "made-up"


def ask(question="Which way do the two interfaces meet?", by="runtime", **extra):
    return {"asked": {"by": by, "question": question},
            "options": [{"id": "a", "summary": "Runtime adapts", "consequences": "One file in runtime changes."},
                        {"id": "b", "summary": "Workflow adapts", "consequences": "Two files in workflow change."}],
            **extra}


def decision(option="a", level="high", recovery="cheap", by="conductor"):
    return {"option": option, "by": by, "rationale": "a follows the frozen interface; b would change it.",
            "confidence": {"level": level, "basis": "interfaces.py's PreparedTarget, as Phase 0 froze it"},
            "recovery": {"class": recovery, "undo": "Revert the adapter commit in runtime."}}


def decided(**kw):
    return ask(state="decided", decision=decision(**kw))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "decisions"
        clock = (f"2026-11-14T21:{m:02d}:{s:02d}Z" for m, s in itertools.product(range(60), range(60)))
        self.clock = mock.patch.object(decisions, "now", lambda: next(clock))
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        self.tmp.cleanup()

    def run_cli(self, *argv, stdin=None) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = decisions.main(list(argv), root=self.root,
                                  stdin=io.StringIO(json.dumps(stdin)) if stdin is not None else None)
        return code, out.getvalue(), err.getvalue()

    def record(self, data) -> str:
        code, out, err = self.run_cli("record", NAME, "--run", "2026-11-14T20:00:00Z", stdin=data)
        self.assertEqual(code, 0, err)
        return out

    def current(self) -> dict:
        return decisions.fold(decisions.read(NAME, self.root))

    def lines(self) -> list[str]:
        return decisions.record_path(NAME, self.root).read_text().splitlines()

    def assertClean(self):
        self.assertEqual(decisions.problems(self.root), [])


class Record(Base):
    # what the conductor may decide alone, and the review each starts with

    def test_the_action_table_sets_the_review_of_what_the_conductor_decides(self):
        self.record([decided(), decided(recovery="costly"), decided(level="medium")])
        reviews = {i: d["review"] for i, d in self.current().items()}
        self.assertEqual(reviews, {"made-up-D001": {"state": "unreviewed"},
                                   "made-up-D002": {"state": "flagged", "why": "costly"},
                                   "made-up-D003": {"state": "flagged", "why": "medium-confidence"}})
        self.assertClean()

    def test_what_is_not_the_conductors_to_decide_is_refused_and_nothing_is_written(self):
        for kw in ({"level": "low"}, {"level": "medium", "recovery": "costly"}, {"recovery": "irreversible"}):
            code, _, err = self.run_cli("record", NAME, stdin=decided(**kw))
            self.assertEqual(code, 1)
            self.assertIn("that is the user's", err)
        self.assertFalse(decisions.record_path(NAME, self.root).exists())

    def test_the_conductor_cannot_review_for_the_user(self):
        code, _, err = self.run_cli("record", NAME, stdin={**decided(), "review": {"state": "accepted"}})
        self.assertEqual(code, 1)
        self.assertIn("only the user reviews", err)
        code, _, err = self.run_cli("record", NAME, stdin={**decided(recovery="costly"), "review": {"state": "unreviewed"}})
        self.assertEqual(code, 1)
        self.assertIn("flagged for review, not left unreviewed", err)

    def test_a_decision_once_taken_is_superseded_not_changed(self):
        self.record(decided())
        code, _, err = self.run_cli("record", NAME, stdin={"id": "made-up-D001", "decision": {"option": "b"}})
        self.assertEqual(code, 1)
        self.assertIn("supersede it", err)

    # open questions and the user's answers

    def test_an_open_question_answered_by_the_user_is_decided_as_theirs(self):
        self.record(ask(blocks=["runtime"]))
        d = self.current()["made-up-D001"]
        self.assertEqual((d["state"], d["decision"], d["review"], d["blocks"]), ("open", None, None, ["runtime"]))
        code, _, err = self.run_cli("answer", "D001", "c")
        self.assertEqual(code, 1)
        self.assertIn("not one of made-up-D001's options", err)
        code, _, err = self.run_cli("record", NAME, stdin={"id": "made-up-D001", "state": "decided",
                                                           "decision": decision(option="b", by="user")})
        self.assertEqual(code, 1)
        self.assertIn("no answer from the user", err)
        self.assertEqual(self.run_cli("answer", "D001", "b", "--note", "keep runtime frozen")[0], 0)
        self.assertEqual(self.current()["made-up-D001"]["answer"]["option"], "b")
        self.assertIn("**Answered** `b` by the user", decisions.view_path(NAME, self.root).read_text())
        self.record({"id": "made-up-D001", "state": "decided", "decision": decision(option="b", by="user")})
        d = self.current()["made-up-D001"]
        self.assertEqual((d["state"], d["review"], d["blocks"]), ("decided", {"state": "accepted"}, []))
        self.assertClean()

    # the user's reviews

    def test_accepting_a_range_reviews_the_decided_and_skips_the_rest(self):
        self.record([decided(), ask(), decided(recovery="costly")])
        code, out, err = self.run_cli("review", "accept", "D001–D003")
        self.assertEqual(code, 0, err)
        self.assertIn("skipped made-up-D002: open", out)
        self.assertEqual({i: (d["review"] or {}).get("state") for i, d in self.current().items()},
                         {"made-up-D001": "accepted", "made-up-D002": None, "made-up-D003": "accepted"})
        self.assertClean()

    def test_an_overturn_needs_a_note(self):
        self.record(decided())
        code, _, err = self.run_cli("review", "overturn", "made-up-D001")
        self.assertEqual(code, 1)
        self.assertIn("--note", err)

    def test_a_short_id_needs_the_record_named_when_there_are_two(self):
        self.record(decided())
        self.run_cli("record", "other-run", stdin=decided())
        code, _, err = self.run_cli("review", "accept", "D001")
        self.assertEqual(code, 1)
        self.assertIn("say which record", err)
        self.assertEqual(self.run_cli("review", "accept", "D001", "--name", NAME)[0], 0)
        self.assertEqual(self.run_cli("review", "accept", "other-run-D001")[0], 0)

    # the whole flow: dependents grow, the user overturns, the conductor supersedes

    def test_an_overturn_after_dependents_grew_supersedes_it_and_tells_the_stream_how_to_undo(self):
        self.record(decided())
        self.assertEqual(self.run_cli("depend", "D001", "--commit", "aaaa", "--commit", "bbbb")[0], 0)
        self.assertEqual(self.current()["made-up-D001"]["review"]["state"], "unreviewed")
        code, out, _ = self.run_cli("depend", "D001", "--commit", "cccc")
        self.assertIn("review flagged", out)
        self.assertEqual(self.current()["made-up-D001"]["review"], {"state": "flagged", "why": "dependents-grown"})
        self.assertEqual(self.run_cli("review", "overturn", "D001", "--note", "workflow adapts instead")[0], 0)
        self.assertEqual(decisions.group(self.current()["made-up-D001"]), "overturned")
        # superseding alone would leave the old one decided: refused as one change, nothing written
        before = self.lines()
        code, _, err = self.run_cli("record", NAME, stdin={**decided(option="b", by="user"), "supersedes": "made-up-D001"})
        self.assertEqual(code, 1)
        self.assertIn("not superseded", err)
        self.assertEqual(self.lines(), before)
        undo = {"stream": "runtime", "item": "runtime-3: revert the adapter (aaaa, bbbb, cccc); workflow adapts"}
        self.record([{**decided(option="b", by="user"), "supersedes": "made-up-D001"},
                     {"id": "made-up-D001", "state": "superseded", "applied": {"inbox": [undo]}}])
        current = self.current()
        self.assertEqual(current["made-up-D001"]["state"], "superseded")
        self.assertEqual(current["made-up-D001"]["review"]["state"], "overturned")  # carried forward
        self.assertEqual(current["made-up-D001"]["decision"]["recovery"]["dependents"]["commits"],
                         ["aaaa", "bbbb", "cccc"])
        self.assertEqual((current["made-up-D002"]["review"], current["made-up-D002"]["supersedes"]),
                         ({"state": "accepted"}, "made-up-D001"))
        self.assertEqual([json.loads(line)["seq"] for line in self.lines()], list(range(1, 7)))
        view = decisions.view_path(NAME, self.root).read_text()
        self.assertIn("- made-up-D001 (superseded)", view)
        self.assertIn("- made-up-D002 (decided by the user)", view)
        self.assertClean()

    # the view

    def test_the_view_puts_flagged_first_then_open_then_unreviewed_then_overturned_then_settled(self):
        self.record([decided(), ask(), decided(recovery="costly"), decided(), decided()])
        self.run_cli("review", "accept", "D004")
        self.run_cli("review", "overturn", "D005", "--note", "the other way")
        view = decisions.view_path(NAME, self.root).read_text()
        headings = [line for line in view.splitlines() if line.startswith("## ")]
        self.assertEqual(headings, ["## Flagged for review", "## Open: waiting for the user",
                                    "## Decided, not reviewed yet", "## Overturned, waiting for the conductor",
                                    "## Settled"])
        order = [line.split(":")[0].removeprefix("### ") for line in view.splitlines() if line.startswith("### ")]
        self.assertEqual(order, ["made-up-D003", "made-up-D002", "made-up-D001", "made-up-D005"])
        self.assertIn("- made-up-D004 (accepted)", view)
        self.assertIn("**5 decision(s):** 1 flagged, 1 open, 1 unreviewed, 1 overturned, 1 settled", view)
        self.assertEqual(self.run_cli("counts")[1].strip(), "made-up: 1 open, 1 flagged, 1 unreviewed, 1 overturned")
        code, out, _ = self.run_cli("list", "--group", "flagged,unreviewed", "--markdown")
        self.assertEqual([line.split("**")[1] for line in out.splitlines()], ["made-up-D003", "made-up-D001"])
        self.assertIn("(flagged (costly))", out)

    def test_past_the_threshold_an_unreviewed_decision_shows_flagged_before_it_is_recorded(self):
        self.record(decided())
        line = json.loads(self.lines()[0])
        line["decision"]["recovery"]["dependents"]["jobs"] = ["20261114-210000"]
        line["seq"], line["at"] = 2, "2026-11-14T22:00:00Z"
        with decisions.record_path(NAME, self.root).open("a") as f:
            f.write(json.dumps(line) + "\n")
        d = self.current()["made-up-D001"]
        self.assertEqual(d["review"]["state"], "unreviewed")
        self.assertEqual(decisions.effective_review(d), {"state": "flagged", "why": "dependents-grown"})
        self.assertEqual(decisions.group(d), "flagged")

    # check

    def test_check_reports_what_the_schema_cannot(self):
        self.record([decided(), ask()])
        path, view = decisions.record_path(NAME, self.root), decisions.view_path(NAME, self.root)
        lines = [json.loads(line) for line in self.lines()]
        lines[1]["seq"] = 5
        lines.append({"kind": "review", "id": "made-up-D009", "seq": 3, "at": "2026-11-14T23:00:00Z", "by": "user",
                      "state": "accepted"})
        lines.append({**lines[0], "seq": 4, "state": "superseded"})
        path.write_text("".join(json.dumps(line) + "\n" for line in lines))
        (self.root / "orphan.md").write_text("# nothing\n")
        found = "\n".join(decisions.problems(self.root))
        self.assertIn("line 2: seq is 5, not its line number 2", found)
        self.assertIn("line 3: the user's review names made-up-D009, which has no decision line before it", found)
        self.assertIn("made-up-D001 is superseded, but no decision supersedes it", found)
        self.assertIn("made-up.md does not match made-up.jsonl", found)
        self.assertIn("orphan.md has no record orphan.jsonl", found)
        view.write_text(decisions.render(NAME, lines))
        self.assertNotIn("does not match", "\n".join(decisions.problems(self.root)))

    def test_a_line_the_schema_refuses_is_reported_by_field(self):
        self.record(decided())
        line = json.loads(self.lines()[0])
        line["decision"]["recovery"]["class"] = "cheapish"
        del line["asked"]["question"]
        line["extra"] = 1
        found = decisions.schema_errors(line)
        self.assertEqual(sorted(found), ['asked: question is missing', 'decision.recovery.class: must be one of '
                                         '"cheap", "costly", "irreversible"', 'the line: extra is not a field'])

    def test_a_record_with_conflict_markers_is_reported_and_its_view_left_alone(self):
        self.record(decided())
        path, view = decisions.record_path(NAME, self.root), decisions.view_path(NAME, self.root)
        before = view.read_text()
        path.write_text(path.read_text() + "<<<<<<< conflict 1 of 1\n")
        self.assertEqual(decisions.render_all(self.root), [])
        self.assertEqual(view.read_text(), before)
        self.assertIn("line 2: not JSON", "\n".join(decisions.problems(self.root)))


@unittest.skipUnless(__import__("importlib").util.find_spec("jsonschema"), "needs jsonschema")
class SchemaAgreesWithJsonschema(Base):
    """The validator in decisions.py reads the same schema.json as jsonschema, on the lines the tests write."""

    def test_both_accept_every_line_and_refuse_the_same_broken_ones(self):
        import jsonschema
        validator = jsonschema.Draft202012Validator(decisions.schema())
        validator.check_schema(decisions.schema())
        self.record([decided(), ask(), decided(recovery="costly", level="high")])
        self.run_cli("review", "accept", "D001")
        self.run_cli("answer", "D002", "a")
        good = [json.loads(line) for line in self.lines()]
        broken = [{**good[0], "state": "maybe"}, {**good[0], "seq": 0}, {**good[3], "by": "conductor"},
                  {**good[4], "option": "Not An Id"}, {k: v for k, v in good[1].items() if k != "options"},
                  {**good[0], "decision": {**good[0]["decision"], "by": "someone"}}, {**good[0], "id": "D001"},
                  {**good[2], "review": {"state": "flagged", "why": "bored"}}, {"kind": "decision"}, {}]
        for line in good:
            self.assertEqual((list(validator.iter_errors(line)), decisions.schema_errors(line)), ([], []), line)
        for line in broken:
            self.assertTrue(list(validator.iter_errors(line)), line)
            self.assertTrue(decisions.schema_errors(line), line)


if __name__ == "__main__":
    unittest.main()
