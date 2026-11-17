# Brief: a rehearsal of /run-brief

**Status of the brief**: written 2026-11-17 for a first run of `/run-brief` with real sessions; approved by the user
on 2026-11-17 as a rehearsal. It builds nothing that is kept: what it commits is abandoned or removed afterwards.

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh), run as two streams, [a](rehearsal-a.md) and
[b](rehearsal-b.md), through `/run-brief rehearsal` ([`llm-dlc/README.md`](../README.md#a-briefs-run)). Its work is
deliberately trivial. What it rehearses is the run itself: the foundation stage and its landing, the hand-off to the
streams' inboxes, a stream that stops blocked and is run again at the watcher's word, and the watcher's merge of
each stream the moment it is finished.

## Direction

- Everything it writes goes under `llm-dlc/loops/rehearsal-out/`. Touch nothing else in the repository but this
  brief's and the streams' `## Progress`.
- Keep it small: each piece of work is a few lines of text. Don't improve on the task.

## Where it starts from

Nothing: `llm-dlc/loops/rehearsal-out/` does not exist.

## How to work through it

The [standing rules](brief-template.md#standing-rules) apply, with these differences, which hold for every session
of this run, the foundation's included:

- **No test run and no verification job.** Nothing here is code the tests read. Don't run the default test run, and
  don't queue one: check a note with `python3 llm-dlc/loops/rehearsal-out/check.py FILE` once that script exists.
- **Verification mode: separate.** No job is submitted.
- One step per cycle, committed on its own with `sync.py commit --only llm-dlc/loops`.

## The plan

Both streams write a note in one format, so the format and its checker are what they share:

- **Shared, before the streams** (the foundation's, if it sees fit): `llm-dlc/loops/rehearsal-out/check.py`, a
  script of a few lines that exits 0 for a note that has a first line `# Note NAME`, a line `keyword: WORD` with
  one lower-case word, and at most ten lines, and says what is wrong otherwise; and a sentence in this section
  saying it is there.
- **Stream a** writes `rehearsal-out/a.md`, choosing its own keyword.
- **Stream b** writes `rehearsal-out/b.md`, whose second piece needs a's keyword: see its brief.
- **The merges**: the watcher merges each stream into the default line as it finishes (`brief_run.py merge`),
  which records it below and sets the status to `done` once both are merged. There is no merge loop, and no
  index of the notes: the first rehearsal's merge loop wrote one, on 2026-11-17.

## Done when

| Phase | Criterion |
|---|---|
| Streams | `a.md` and `b.md` pass `check.py`, and `b.md` quotes a's keyword |
| Merges | both streams are merged into the default line, and this brief's status is `done` |

## Deferred: not in this loop

Everything else.

## Decisions

Settled by the user on 2026-11-17: this is a rehearsal, started by them from their watcher session, and its commits
may be abandoned afterwards.

## Progress

- Nothing yet.
- Status: working

## Loop settings

- session: 51ddbf03-2050-49a0-947e-ef6204d62dc0
- model: claude-sonnet-5-5
- effort: medium
- streams: a, b
- verification: separate
- new-window: no

## Loop until

The brief has no loop of its own: its status is set by the watcher's merges. Keep the last line of Progress a
status: `working`, `done`, or `blocked: ...` with what needs the user.
