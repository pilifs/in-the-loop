# Brief: rehearsal, stream b

A stream of [rehearsal.md](rehearsal.md), which is the instruction: read it in full first, its
"How to work through it" above all (no test run, no verification job, commits with `--only llm-dlc/loops`).

## Your work

1. Write `llm-dlc/loops/rehearsal-out/b.md` in the format the main brief gives: first line `# Note b`, a line
   `keyword: WORD` with a lower-case word of your own, and one sentence saying which cycle wrote it. Check it with
   `check.py` and commit.
2. Add a line `a says: WORD` quoting the keyword stream a chose. **You cannot see stream a's workspace, and you
   must not guess the word or look for it in another workspace or in jj's history.** It reaches you only through
   your inbox. If your inbox has no item that gives it, this piece is blocked: set the status to
   `blocked: needs the keyword stream a chose in its note (rehearsal-out/a.md); the watcher can read it from a's
   workspace once a has committed it` and stop. When an item gives it, add the line, acknowledge the item, check
   the note, commit, and set the status to `done`.

You own `llm-dlc/loops/rehearsal-out/b.md` and this brief's Progress, and nothing else.

## Progress

- Nothing yet.
- Status: working

## Loop settings

- session: 63ab3275-dd2b-44b5-901a-fec8eb1c3c72
- model: claude-sonnet-5-5
- effort: medium
- workspace: rehearsal-b

## Loop until

Until both pieces of your work are committed (`done`), or the second is blocked as it says (`blocked: ...`). Keep
the last line of Progress a status.
