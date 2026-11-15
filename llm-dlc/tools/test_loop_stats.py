#!/usr/bin/env python3
"""Tests for loop_stats.py, and for how sync.py writes and checks what it gives, on made-up sessions,
records and jobs. Run: python3 llm-dlc/tools/test_loop_stats.py"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import loop_stats
import metrics
import redactor
import sync

PRICING = {"as_of": "2000-01-01", "models": {
    "m-a": {"input": 10, "output": 50, "cache_read": 1, "cache_write_5m": 12.5, "cache_write_1h": 20},
    "m-b": {"input": 1, "output": 5, "cache_read": 0.1, "cache_write_5m": 1.25, "cache_write_1h": 2}}}
SID = "0f0f0f0f-1111-4222-8333-444455556666"
OTHER = "0e0e0e0e-1111-4222-8333-444455556666"
THIRD = "0d0d0d0d-1111-4222-8333-444455556666"
TEMPLATE = "Formally prove made-up example {} as elegantly and efficiently as possible"
BRIEF_TEXT = "Work on the brief in `llm-dlc/loops/%s.md`. Read it in full now, even if you have read it before."
DECIDE = "Cycle %d of the feature loop is committed. Before the next cycle starts, decide whether the loop should go on."
SUMMARY = "The feature loop is ending after %d cycle(s). Summarize the work this run committed."
FORK = "This conversation goes on as one of the parallel streams it planned: the loop of the brief."
STATUS = "You decided that the loop stops after this cycle, but the status line still says `working`."


class MadeUpRedactor(sync.Redactor):
    """sync's Redactor with no literals of this machine's."""

    def __init__(self):
        redactor.Redactor.__init__(self, ([], "qzuser"), {})


def at(minute, second=0):
    """A transcript's time, `minute` minutes after 10:00 UTC on a made-up day."""
    return f"2026-11-20T{10 + minute // 60:02d}:{minute % 60:02d}:{second:02d}.000Z"


def stamp(minute, second=0):
    """The same moment as feature-loop.sh writes it in a record."""
    return f"2026-11-20 {10 + minute // 60:02d}:{minute % 60:02d}:{second:02d}"


def usd(output):
    return round(output * 50 / 1e6, 6)  # m-a's price for tokens written; the made-up calls read nothing


class Transcript:
    """A made-up session: prompts with one model call each, compactions, and the commits its manifest lists."""

    def __init__(self, sid=SID):
        self.sid, self.entries, self.commits, self.logs = sid, [], [], {}

    def say(self, minute, text, output=1000, model="m-a", context=0):
        self.entries.append({"type": "user", "timestamp": at(minute), "message": {"content": text}})
        self.entries.append({"type": "assistant", "timestamp": at(minute, 30), "effort": "high", "message": {
            "id": f"call-{len(self.entries)}", "model": model, "content": [],
            "usage": {"input_tokens": 0, "output_tokens": output, "cache_read_input_tokens": context,
                      "cache_creation_input_tokens": 0}}})
        return self

    def command(self, minute, text):
        self.entries.append({"type": "user", "timestamp": at(minute, 40), "message": {"content": text}})
        return self

    def compact(self, minute, pre=900):
        self.command(minute, "/compact")
        self.entries.append({"type": "system", "subtype": "compact_boundary", "timestamp": at(minute, 50),
                             "compactMetadata": {"trigger": "manual", "preTokens": pre, "postTokens": 90, "durationMs": 5000}})
        return self

    def commit(self, summary, body=""):
        sha = f"log-{len(self.commits)}"
        self.commits.append({"change_id": chr(ord("k") + len(self.commits)) * 32, "summary": summary, "body": body,
                             "log_sha256": sha})
        self.logs[sha] = {"lines": len(self.entries)}
        return self

    def cycle(self, minute, text, summary="Made-up change", body="", output=1000, decide=None, compact=True):
        """One cycle as the script runs it: the instruction, a commit, the decision turn, the compact."""
        self.say(minute, text, output)
        if summary:
            self.commit(summary, body)
        if decide:
            self.say(minute + 1, DECIDE % decide, 10)
        if compact:
            self.compact(minute + 2)
        return self

    def session(self):
        manifest = {"session_id": self.sid, "started": self.entries[0]["timestamp"], "log": {"sha256": "x"},
                    "commits": self.commits, "logs": self.logs}
        return manifest, metrics.session(manifest, self.entries, [], PRICING, lambda s: s)


def record(loop, sid, start, lines=(), end=None, instruction=None, items=None, brief=False, fork=None, cap="no limit on"):
    """A run record as feature-loop.sh writes one. `lines` is (cycle, minute, item, decision) per commit."""
    out = [f"# Feature loop: {loop}", "",
           f"Started {stamp(start)} UTC, {cap} cycles, session {sid}, m-a at high effort, after change {'k' * 32}.", "",
           f"> {instruction or (BRIEF_TEXT % loop if brief else TEMPLATE)}", ""]
    if items:
        out += [f"Each cycle puts the next item in place of {{}}: {' '.join(items[0])} (the list: {' '.join(items[1])}).", ""]
    if brief:
        out += [f"Brief `llm-dlc/loops/{loop}.md` at sha256 {'ab' * 32}.", ""]
    out += ["## Commits", ""]
    if fork:
        out += [f"Session {sid} was forked from session {fork}.", ""]
    for n, minute, item, decision in lines:
        out.append(f"- cycle {n}, {f'item {item}, ' if item else ''}{stamp(minute, 35)}, `{'k' * 12}`: Made-up change {n}")
        if decision:
            out.append(f"  - decided to {decision}: made-up reasons")
    if end:
        out += ["", end]
    return "\n".join(out) + "\n"


def job(job_id, minute, session=None, status=None, supersedes=None, cpu=10.0):
    row = {"id": job_id, "at": at(minute, 10).replace(".000Z", "+00:00"), "session": session, "supersedes": supersedes,
           "examples": []}
    if status:
        row.update(status=status, wall_seconds=cpu * 2, cpu_seconds=cpu, peak_memory_bytes=1000)
    return row


def stats(sessions, records=(), jobs=()):
    return loop_stats.loops([s.session() for s in sessions], list(records), list(jobs), PRICING)


def one(rows, **where):
    found = [r for r in rows if all(r[k] == v for k, v in where.items())]
    assert len(found) == 1, (where, len(found))
    return found[0]


class Records(unittest.TestCase):
    def test_a_record_is_read_as_the_script_writes_it(self):
        text = record("made-up", SID, 0, [(1, 5, "285", None), (2, 9, "286", "stop")], items=(["285", "286"], ["285", "286", "287"]),
                      end=f"Ended {stamp(12)} after 2 cycle(s): no items left.", cap="2")
        r = loop_stats.parse_record("2026-11-20-100000-made-up", text)
        self.assertEqual((r["loop"], r["session_id"], r["model"], r["effort"], r["cap"]), ("made-up", SID, "m-a", "high", 2))
        self.assertEqual(r["started"], metrics._ms(at(0)))
        self.assertEqual((r["run_items"], r["all_items"]), (["285", "286"], ["285", "286", "287"]))
        self.assertEqual(r["prefix"], "Formally prove made-up example ")
        self.assertEqual({n: (c["item"], c["decision"]) for n, c in r["cycles"].items()}, {1: ("285", None), 2: ("286", "stop")})
        self.assertEqual((r["end"]["outcome"], r["end"]["reason"], r["end"]["at"]),
                         ("ended", "no items left", metrics._ms(at(12))))
        self.assertIsNone(r["brief"])
        self.assertIsNone(loop_stats.parse_record("made-up-integration", "# Integration check\n\nNot a run.\n"))

    def test_how_a_run_ended_is_told_by_the_scripts_words(self):
        for line, outcome, reason in (
                ("Ended {t} after 3 cycle(s): the session decided the work was done.", "ended", "work done"),
                ("Ended {t} after 3 cycle(s): the session decided to stop; the brief says done.", "ended", "work done"),
                ("Ended {t} after 3 cycle(s): the session decided to stop; the brief says waiting on jobs 2026-made-up.",
                 "ended", "waiting on jobs"),
                ("Ended {t} after 3 cycle(s): the session decided to stop; the brief says blocked: made up.", "ended", "blocked"),
                ("Ended {t} after 3 cycle(s).", "ended", "cycle count reached"),
                ("Stopped {t}: cycle 2 (item 286) made no commit; session made-up needs attention.", "stopped", "no commit"),
                ("Stopped {t}: the brief changed before cycle 8; restart the loop to work from the new one.", "stopped", "brief changed"),
                ("Stopped {t}: after cycle 6 the session gave no clear LOOP: continue or LOOP: stop.", "stopped", "unclear decision"),
                ("Stopped {t} after 1 cycle(s): the session decided to stop, but the brief's status still says working.",
                 "stopped", "status left working"),
                ("Interrupted {t} during cycle 2.", "interrupted", "interrupted")):
            r = loop_stats.parse_record("made-up", record("made-up", SID, 0, brief=True, end=line.format(t=stamp(30))))
            self.assertEqual((r["end"]["outcome"], r["end"]["reason"]), (outcome, reason), line)
        self.assertIsNone(loop_stats.parse_record("made-up", record("made-up", SID, 0, brief=True))["end"])

    def test_a_numeric_zone_is_placed_and_a_named_one_is_read_as_utc_and_flagged(self):
        utc = record("made-up", SID, 0, brief=True)
        ahead = loop_stats.parse_record("made-up", utc.replace(" UTC,", " +0100,"))
        self.assertEqual(ahead["started"], metrics._ms(at(0)) - 3_600_000)
        self.assertTrue(ahead["zone_known"])
        named = loop_stats.parse_record("made-up", utc.replace(" UTC,", " CET,"))
        self.assertEqual(named["started"], metrics._ms(at(0)))
        self.assertFalse(named["zone_known"])


class TemplatedMoonshot(unittest.TestCase):
    """Three cycles of a templated moonshot: two commit, the third does not and stops the loop; then a
    second run takes the item again."""

    def setUp(self):
        t = Transcript()
        t.cycle(1, TEMPLATE.replace("{}", "285"), "Prove made-up 285", "Queued as job-named.", output=2000)
        t.say(4, "<task-notification>made-up</task-notification>", 100)  # a background task of cycle 1 reports late
        t.cycle(10, TEMPLATE.replace("{}", "286"), "Prove made-up 286", output=3000)
        t.cycle(20, TEMPLATE.replace("{}", "287"), None, output=500, compact=False)
        t.say(40, "What went wrong with 287?", 700)  # a person, after the loop stopped
        t.cycle(60, TEMPLATE.replace("{}", "287"), "Prove made-up 287", output=4000)
        t.say(64, SUMMARY % 1, 50)
        self.transcript = t
        items = ["285", "286", "287", "288"]
        self.records = [
            ("2026-11-20-100030-prove-made-up", record(
                "prove-made-up", SID, 0, [(1, 1, "285", None), (2, 10, "286", None)], items=(items, items),
                end=f"Stopped {stamp(21)}: cycle 3 (item 287) made no commit; session {SID} needs attention.")),
            ("2026-11-20-105930-prove-made-up", record(
                "prove-made-up", SID, 59, [(1, 60, "287", None)], items=(items[2:3], items), cap="1",
                end=f"Ended {stamp(65)} after 1 cycle(s).")),
        ]
        self.jobs = [job("job-own", 1, SID, "passed"), job("job-named", 1, None, "failed", cpu=5.0),
                     job("job-named-again", 30, None, "passed", supersedes="job-named", cpu=7.0),
                     job("job-unnamed", 1, None, "passed"), job("job-of-another", 1, OTHER, "passed"),
                     job("job-waiting", 60, SID)]
        self.doc = stats([t], self.records, self.jobs)

    def test_each_cycle_takes_its_item_and_its_own_prompts(self):
        cycles = self.doc["cycles"]
        self.assertEqual([(c["run"][11:17], c["cycle"], c["item"], c["outcome"]) for c in cycles],
                         [("100030", 1, "285", "commit"), ("100030", 2, "286", "commit"), ("100030", 3, "287", "no commit"),
                          ("105930", 1, "287", "commit")])
        first = cycles[0]
        self.assertEqual(first["usd"], usd(2000 + 100))          # the instruction and the late notification
        self.assertEqual((first["turns"], first["compactions"], first["context_tokens"]), (2, 1, 900))
        self.assertEqual(first["started"], at(1))
        self.assertEqual(cycles[2]["usd"], usd(500))
        self.assertEqual(cycles[2]["commits"], 0)
        self.assertTrue(all(c["category"] == "moonshot" for c in cycles))

    def test_a_persons_prompt_between_runs_is_nobodys(self):
        runs = self.doc["runs"]
        self.assertEqual([(r["kind"], r["source"], r["cycles"], r["cycles_committed"], r["outcome"], r["reason"]) for r in runs],
                         [("templated moonshot", "record", 3, 2, "stopped", "no commit"),
                          ("templated moonshot", "record", 1, 1, "ended", "cycle count reached")])
        self.assertEqual(runs[0]["usd"], usd(2000 + 100 + 3000 + 500))
        self.assertEqual(runs[1]["usd"], usd(4000 + 50))          # with the closing summary
        self.assertEqual(runs[1]["overhead_usd"], usd(50))
        self.assertEqual(self.doc["totals"]["usd"], usd(2000 + 100 + 3000 + 500 + 4000 + 50))  # not the person's 700
        self.assertEqual(runs[0]["record"], f"{SID}/runs/2026-11-20-100030-prove-made-up.md")
        self.assertEqual((runs[0]["model"], runs[0]["effort"]), ("m-a", "high"))

    def test_an_item_adds_up_its_attempts(self):
        items = {i["item"]: i for i in self.doc["items"]}
        self.assertEqual([(k, i["status"], i["attempts"]) for k, i in items.items()],
                         [("285", "done", 1), ("286", "done", 1), ("287", "done", 2), ("288", "pending", 0)])
        self.assertEqual(items["287"]["usd"], usd(500 + 4000))
        self.assertEqual(len(items["287"]["runs"]), 2)
        loop = one(self.doc["loops"], loop="prove-made-up")
        self.assertEqual((loop["kind"], loop["items"], loop["items_done"], loop["runs"], loop["cycles"]),
                         ("templated moonshot", 4, 3, 2, 4))
        self.assertEqual(loop["instruction"], TEMPLATE)

    def test_a_job_belongs_to_the_cycle_that_submitted_it(self):
        jobs = {j["job"]: j for j in self.doc["jobs"]}
        self.assertEqual(set(jobs), {"job-own", "job-named", "job-waiting"})  # not the unnamed one, nor another session's
        self.assertEqual((jobs["job-own"]["cycle"], jobs["job-own"]["item"], jobs["job-own"]["status"]), (1, "285", "passed"))
        rerun = jobs["job-named"]  # its last attempt is the verdict, and both attempts are what it took
        self.assertEqual((rerun["status"], rerun["final"], rerun["attempts"], rerun["cpu_seconds"]),
                         ("passed", "job-named-again", 2, 12.0))
        self.assertEqual(jobs["job-waiting"]["status"], "pending")
        items = {i["item"]: i for i in self.doc["items"]}
        self.assertEqual([items[k]["proof"] for k in ("285", "286", "287", "288")], ["passed", "no job", "pending", "no job"])
        self.assertEqual(self.doc["cycles"][0]["job_cpu_seconds"], 22.0)
        self.assertEqual(self.doc["totals"]["jobs_known"], 5)

    def test_a_failed_job_fails_the_items_proof(self):
        doc = stats([self.transcript], self.records, [job("job-own", 1, SID, "failed"), job("job-too", 1, SID, "passed")])
        self.assertEqual(one(doc["items"], item="285")["proof"], "failed")

    def test_the_page_and_the_data_are_the_same_every_time(self):
        again = stats([self.transcript], reversed(self.records), reversed(self.jobs))
        self.assertEqual(metrics.dumps(self.doc), metrics.dumps(again))
        page = loop_stats.page(self.doc)
        self.assertEqual(page, loop_stats.page(again))
        for part in ("### Items of `prove-made-up`", "| 288 | pending |", "3 of 4 items done", "*no commit*",
                     f"]({SID}/runs/2026-11-20-100030-prove-made-up.md)", "no commit (stopped)"):
            self.assertIn(part, page)
        json.loads(metrics.dumps(self.doc))

    def test_a_record_whose_session_has_no_metrics_yet_counts_its_commits_and_no_cost(self):
        records = [(name, text.replace(SID, OTHER)) for name, text in self.records]
        doc = stats([Transcript().say(0, "Nothing to do with a loop", 10)], records)
        self.assertEqual(doc["totals"]["records_without_session"], [name for name, _ in records])
        self.assertEqual(doc["runs"], [])
        behind = Transcript(OTHER).say(-5, "A prompt from before the loop", 10)  # traced, but not as far as the runs
        doc = stats([behind], records)
        run = doc["runs"][0]
        self.assertEqual((run["measured"], run["cycles"], run["cycles_committed"], run["usd"]), (False, 2, 2, 0.0))
        self.assertIn("Not measured yet", loop_stats.page(doc))


class Briefs(unittest.TestCase):
    def test_a_run_with_a_record_owns_the_scripts_turns_as_overhead(self):
        t = Transcript()
        t.say(0, FORK, 20)
        t.cycle(1, BRIEF_TEXT % "made-up-alpha", output=1000, decide=1)
        t.say(5, BRIEF_TEXT % "made-up-alpha", 2000).commit("Made-up change 2")
        t.say(6, DECIDE % 2, 10).say(7, STATUS, 30).commit("Record the status").compact(8)
        t.say(9, SUMMARY % 2, 40)
        text = record("made-up-alpha", SID, 0, [(1, 1, None, "continue"), (2, 5, None, "stop")], brief=True, fork=OTHER,
                      end=f"Ended {stamp(10)} after 2 cycle(s): the session decided to stop; the brief says done.")
        parent = Transcript(OTHER).cycle(20, BRIEF_TEXT % "made-up", decide=1).say(23, SUMMARY % 1, 40)
        doc = stats([t, parent], [("2026-11-20-100000-made-up-alpha", text)])
        run = one(doc["runs"], loop="made-up-alpha")
        self.assertEqual((run["kind"], run["stream_of"], run["category"], run["forked_from"]),
                         ("brief stream", "made-up", "brief", OTHER))
        self.assertEqual(run["usd"], usd(20 + 1000 + 10 + 2000 + 10 + 30 + 40))
        self.assertEqual(run["overhead_usd"], usd(20 + 10 + 10 + 30 + 40))
        self.assertEqual([(c["decision"], c["commits"], c["overhead_usd"]) for c in doc["cycles"] if c["run"] == run["run"]],
                         [("continue", 1, usd(10)), ("stop", 2, usd(10 + 30))])
        merge = one(doc["runs"], loop="made-up")
        self.assertEqual((merge["kind"], merge["source"], merge["outcome"], merge["reason"]),
                         ("brief", "transcript", "ended", "summarized"))
        page = loop_stats.page(doc)
        self.assertIn("stream `made-up-alpha`", page)
        self.assertIn("*with its streams*", page)

    def test_before_records_a_run_is_read_from_the_prompts(self):
        t = Transcript()
        t.say(0, "Plan the made-up loop with me", 300)
        t.cycle(1, BRIEF_TEXT % "made-up", decide=1).cycle(5, BRIEF_TEXT % "made-up", decide=2)
        t.say(9, SUMMARY % 2, 40)
        t.cycle(11, BRIEF_TEXT % "made-up", decide=1)                 # at once, but the script counts from 1 again
        t.cycle(15, BRIEF_TEXT % "made-up", decide=2)
        t.cycle(60, BRIEF_TEXT % "made-up", decide=None)              # half an hour of nothing: a new run
        t.say(64, "Continue", 900).commit("Finished by hand")          # a person ends it, and is not counted
        t.cycle(70, loop_stats.EARLY_MOONSHOTS["tla"], "A made-up spec")
        t.cycle(74, loop_stats.EARLY_MOONSHOTS["tla"], None, compact=False)
        doc = stats([t])
        self.assertEqual([(r["loop"], r["kind"], r["source"], r["cycles"], r["cycles_committed"], r["outcome"]) for r in doc["runs"]],
                         [("made-up", "brief", "transcript", 2, 2, "ended"), ("made-up", "brief", "transcript", 2, 2, "unrecorded"),
                          ("made-up", "brief", "transcript", 1, 1, "unrecorded"), ("tla", "moonshot", "transcript", 2, 1, "unrecorded")])
        self.assertEqual(doc["runs"][0]["run"], "2026-11-20-100100-made-up")
        self.assertEqual(doc["totals"]["usd"], usd(5 * 1000 + 4 * 10 + 40 + 2 * 1000))
        self.assertEqual([c["category"] for c in doc["categories"]], ["moonshot", "brief"])
        self.assertEqual(one(doc["loops"], loop="tla")["instruction"], loop_stats.EARLY_MOONSHOTS["tla"])

    def test_a_record_with_no_end_owns_prompts_until_a_person_types_or_the_next_run_starts(self):
        t = Transcript()
        t.cycle(1, BRIEF_TEXT % "made-up", decide=1).say(5, BRIEF_TEXT % "made-up", 2000)     # killed in cycle 2
        t.say(20, "Why did the made-up loop die?", 700)
        t.cycle(31, BRIEF_TEXT % "made-up", decide=1)                                         # and never ended either
        records = [("2026-11-20-100000-made-up", record("made-up", SID, 0, [(1, 1, None, "continue")], brief=True)),
                   ("2026-11-20-103000-made-up", record("made-up", SID, 30, [(1, 31, None, "continue")], brief=True))]
        doc = stats([t], records)
        self.assertEqual([(r["cycles"], r["cycles_committed"], r["outcome"], r["reason"], r["usd"]) for r in doc["runs"]],
                         [(2, 1, "unrecorded", "no end recorded", usd(1000 + 10 + 2000)),
                          (1, 1, "unrecorded", "no end recorded", usd(1000 + 10))])
        self.assertEqual(doc["runs"][0]["ended"], at(5, 30))

    def test_a_prompt_typed_into_a_running_loops_session_counts_in_the_run_and_is_reported(self):
        t = Transcript().cycle(1, BRIEF_TEXT % "made-up", decide=1, compact=False)
        t.say(3, "How is the made-up loop doing?", 200).compact(4).say(5, SUMMARY % 1, 40)
        doc = stats([t], [("2026-11-20-100000-made-up", record(
            "made-up", SID, 0, [(1, 1, None, "stop")], brief=True,
            end=f"Ended {stamp(6)} after 1 cycle(s): the session decided the work was done."))])
        run = doc["runs"][0]
        self.assertEqual((run["interjections"], run["usd"]), (1, usd(1000 + 10 + 200 + 40)))
        self.assertIn("Other prompts", loop_stats.page(doc))


class Verification(unittest.TestCase):
    def test_a_session_of_nothing_but_run_verification_is_one_run_of_the_verification_loop(self):
        loop = Transcript(OTHER)
        loop.entries.append({"type": "user", "timestamp": at(0), "message": {"content": "/run-verification"}})
        loop.entries.append({"type": "assistant", "timestamp": at(3), "effort": "medium", "message": {
            "id": "made-up", "model": "m-b", "content": [],
            "usage": {"input_tokens": 0, "output_tokens": 1000, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}})
        loop.commit("Collect made-up results").say(5, "<task-notification>made-up</task-notification>", 100, model="m-b")
        by_hand = Transcript(THIRD).say(0, "Is the queue empty?", 100).command(1, "/run-verification")
        doc = stats([loop, by_hand])
        self.assertEqual([(r["loop"], r["kind"], r["category"], r["source"], r["session_id"], r["commits"], r["cycles"])
                          for r in doc["runs"]], [("verification", "verification loop", "verification", "session", OTHER, 1, 0)])
        self.assertEqual(doc["runs"][0]["usd"], round(1100 * 5 / 1e6, 6))
        self.assertEqual(doc["runs"][0]["overhead_usd"], 0)
        self.assertIn("1 runs from 2026-11-20", loop_stats.page(doc))


class InSync(unittest.TestCase):
    """sync.py writes loops.json and loops.md from the files in the repo, and `check` holds them to that."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        repo = Path(self.tmp.name)
        llm = repo / "llm-dlc"
        pricing = llm / "pricing.json"
        self.patches = [mock.patch.object(sync, name, value) for name, value in (
            ("REPO", repo), ("TRACES", llm / "traces"), ("INDEX", llm / "index.json"), ("PRICING", pricing),
            ("TRACES_README", llm / "traces" / "README.md"), ("METRICS_ROLLUP", llm / "traces" / "metrics.json"),
            ("REVIEWED", llm / "reviewed.json"), ("ALLOWLIST", llm / "allowlist.json"))]
        self.patches.append(mock.patch.object(sync, "render_traces_readme", return_value="made-up overview\n"))
        for p in self.patches:
            p.start()
        t = Transcript().cycle(1, TEMPLATE.replace("{}", "285"), "Prove made-up 285")
        manifest, doc = t.session()
        manifest["schema"] = sync.SCHEMA
        folder = sync.TRACES / SID
        (folder / "runs").mkdir(parents=True)
        pricing.write_text(json.dumps(PRICING))
        (folder / "manifest.json").write_text(json.dumps(manifest))
        (folder / "metrics.json").write_text(metrics.dumps(doc))
        (folder / "runs" / "2026-11-20-100000-prove-made-up.md").write_text(record(
            "prove-made-up", SID, 0, [(1, 1, "285", None)], items=(["285"], ["285", "286"]), cap="1",
            end=f"Ended {stamp(5)} after 1 cycle(s)."))
        jobs = repo / "verification" / "jobs"
        jobs.mkdir(parents=True)
        (jobs / "job-made-up.json").write_text(json.dumps({"id": "job-made-up", "links": {"examples": ["285"]},
                                                           "submitted": {"at": at(1, 10), "session": SID}}))
        (jobs / "not-a-job.json").write_text("{ not JSON")
        result = repo / "verification" / "results" / "job-made-up"
        result.mkdir(parents=True)
        (result / "result.json").write_text(json.dumps({"status": "passed", "wallSeconds": 9.0, "usage": {
            "wallSeconds": 8.0, "cpuSeconds": 6.5, "peakMemoryBytes": 4096}}))
        self.manifests = sync.all_manifests()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def stale(self):
        return [e for e in sync.check_global_files(self.manifests, MadeUpRedactor()) if "loops." in e]

    def test_the_jobs_are_read_with_their_results(self):
        self.assertEqual(sync.verification_jobs(), [{
            "id": "job-made-up", "at": at(1, 10), "session": SID, "supersedes": None, "examples": ["285"],
            "status": "passed", "wall_seconds": 8.0, "cpu_seconds": 6.5, "peak_memory_bytes": 4096}])

    def test_the_two_files_are_rendered_from_the_repo_and_checked_against_it(self):
        data, page = sync.render_loops(self.manifests)
        doc = json.loads(data)
        self.assertEqual(doc["schema"], loop_stats.SCHEMA)
        self.assertEqual([(i["item"], i["status"], i["proof"]) for i in doc["items"]],
                         [("285", "done", "passed"), ("286", "pending", "no job")])
        self.assertEqual(len(self.stale()), 2, "missing files are not reported")
        sync.loops_data_path().write_text(data)
        sync.loops_page_path().write_text(page)
        self.assertEqual(self.stale(), [])
        self.assertLessEqual({"llm-dlc/traces/loops.json", "llm-dlc/traces/loops.md"}, set(sync.checked_files(self.manifests)))
        (sync.REPO / "verification" / "results" / "job-made-up" / "result.json").write_text(json.dumps({"status": "failed"}))
        self.assertEqual(len(self.stale()), 2, "a job's new result does not make the files stale")

    def test_statistics_that_cannot_be_computed_stop_nothing_and_check_warns(self):
        self.assertEqual(sync.loops_warnings(), [])
        with mock.patch.object(loop_stats, "loops", side_effect=TypeError("made-up failure")):
            data, page = sync.render_loops(self.manifests)
            sync.loops_data_path().write_text(data)
            sync.loops_page_path().write_text(page)
            self.assertEqual(self.stale(), [], "the report of a failure is what the inputs give, so it is not stale")
            warnings = sync.loops_warnings()
        self.assertEqual(json.loads(data), {"schema": loop_stats.SCHEMA, "error": "TypeError: made-up failure"})
        self.assertIn("TypeError: made-up failure", page)
        self.assertEqual(len(warnings), 1)
        self.assertIn("TypeError: made-up failure", warnings[0])
        self.assertEqual(len(self.stale()), 2, "once it can be computed again, the report is stale")


if __name__ == "__main__":
    unittest.main()
