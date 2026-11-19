# Brief: a pilot of Codex and Claude Code on one brief

**Status of the brief**: written 2026-11-18 for the first runs of a brief whose streams are carried by Codex, by
Claude Code, or by one each ([Claude Code or Codex](../README.md#claude-code-or-codex)). It builds nothing that is
kept: what a run of it commits is on a line of its own, in a disposable workspace, and is abandoned afterwards.

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh), run as two streams, [a](codex-pilot-a.md) and
[b](codex-pilot-b.md), with `brief_run.py start codex-pilot --agent CLIENT [--stream-agent STREAM=CLIENT]`. Its
work is deliberately trivial, the shape of [rehearsal.md](rehearsal.md). What it rehearses is the run: the same
instructions reaching either client, a worker that commits, is compacted between its cycles, resumes its own
session and stops; a stream that stops blocked and is run again at the watcher's word through its inbox; and the
watcher's merge of each stream.

**Before each run**: give the three briefs fresh `- session:` ids (`python3 -c 'import uuid; print(uuid.uuid4())'`)
and put their Progress back to `Nothing yet.` and `working`, in the disposable workspace the run is started from.
A session belongs to the client that began it.

## Direction

- Everything it writes goes under `llm-dlc/loops/codex-pilot-out/`. Touch nothing else in the repository but the
  streams' `## Progress`.
- Keep it small: each piece of work is a few lines of text. Don't improve on the task.

## Where it starts from

Nothing: `llm-dlc/loops/codex-pilot-out/` does not exist.

## How to work through it

The [standing rules](brief-template.md#standing-rules) apply, with these differences, which hold for every session
of a run:

- **No test run and no verification job.** Nothing here is code the tests read. Don't run the default test run or
  `test_costs.py run --changed`, and don't queue a job.
- **Verification mode: separate.** No job is submitted.
- One step per cycle, committed on its own with `python3 llm-dlc/tools/sync.py commit --only llm-dlc/loops -m ...
  -m ...`, as `CLAUDE.md` says a commit is made.
- **A note's format**: a first line `# Note NAME`, a line `keyword: WORD` with one lower-case word, a line
  `instructions: PHRASE` (below), and at most ten lines in all.
- **The `instructions:` line** shows which instructions reached the session that wrote the note. Its phrase is
  the first four words of the sentence in `CLAUDE.md` that begins "The version control system is", followed by a
  semicolon and the name of the script `CLAUDE.md` says to run when jj says the working copy is stale. Take both
  from the `CLAUDE.md` you were given, not from a search of the repository.

## The plan

- **Stream a** writes `codex-pilot-out/a.md` in two cycles, choosing its own keyword.
- **Stream b** writes `codex-pilot-out/b.md`, whose second piece needs a's keyword, which reaches it only through
  its inbox: see its brief.
- **The merges**: the watcher merges each stream into the line the run was started from as it finishes
  (`brief_run.py merge`), which records it below and sets the status to `done` once both are merged.

## Done when

| Phase | Criterion |
|---|---|
| Streams | `a.md` and `b.md` have the format above, each with the same `instructions:` line, and `b.md` quotes a's keyword |
| Merges | both streams are merged, and this brief's status is `done` |

## Deferred: not in this loop

Everything else.

## Decisions

Settled by the user on 2026-11-18 (brief 00, "Run Codex and Claude Code from the same loop instructions"): the
pilot runs in fresh workspaces, and its commits are abandoned afterwards.

## Progress

- Nothing yet.
- Status: working

## Loop settings

- session: 54607fbe-265d-4a35-a0f3-7f96135cfd58
- model: claude-opus-5-5
- effort: medium
- streams: a, b
- verification: separate
- new-window: no

## Loop until

The brief has no loop of its own: its status is set by the watcher's merges. Keep the last line of Progress a
status: `working`, `done`, or `blocked: ...` with what needs the user.
