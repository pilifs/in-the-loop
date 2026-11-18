# Brief: codex-pilot, stream a

A stream of [codex-pilot.md](codex-pilot.md), which is the instruction: read it in full first, its
"How to work through it" above all (no test run, no verification job, commits with `--only llm-dlc/loops`, the
note's format and its `instructions:` line).

## Your work

1. Write `llm-dlc/loops/codex-pilot-out/a.md` in the format the main brief gives: first line `# Note a`, a line
   `keyword: WORD` with a lower-case word of your own choosing (not one a reader could guess: pick something
   unusual), the `instructions:` line, and one sentence saying which cycle wrote it. Commit it. That is the whole
   of the first cycle: leave the status `working`.
2. In a second cycle, add one more sentence to the note saying the first cycle's commit (its change id), commit,
   and set the status to `done`.

You own `llm-dlc/loops/codex-pilot-out/a.md` and this brief's Progress, and nothing else.

## Progress

- Nothing yet.
- Status: working

## Loop settings

- session: f8be8b91-ae07-4c34-a7a6-da69a4568246
- model: claude-opus-5-5
- effort: medium
- workspace: codex-pilot-a

## Loop until

Until both pieces of your work are committed, each in a cycle of its own (`done`). Keep the last line of Progress
a status.
