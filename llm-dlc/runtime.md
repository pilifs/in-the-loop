# Runtime mode

This repository runs in one of two modes. `python3 llm-dlc/tools/mode.py` prints which.

| | Development | Runtime |
|---|---|---|
| What it is | the repository as its authors work in it | a released copy on a user's machine, set up by the `/prove-java-change` skill |
| How it is told | no marker | `.in-the-loop-runtime.json` at the root, written by the skill's bootstrap, gitignored |
| A commit | carries its session's trace ([`README.md`](README.md)) | plain, with an `In-The-Loop-Runtime: VERSION sha256:DIGEST` trailer naming the release it was made on |
| Transcripts | redacted, summarized, published with a push | never read |
| A push | `sync.py push`, when the user asks | none: the work stays on the machine, except a contribution the user agrees to |
| Langfuse, the CDN, the allow list, the redaction rules | in use | off |
| Verification pipeline, loops, tests, examples | the same in both | the same in both |

The commands are the same in both modes, so an agent follows one procedure: [`tools/mode.py`](tools/mode.py) decides
what `sync.py commit`, `sync.py check` and the hooks in `.claude/settings.json` do. This page is the runtime side.

## Procedure for agents in a runtime checkout

It replaces [`README.md`'s procedure](README.md#procedure-for-agents) and the trace rules of `CLAUDE.md`. Everything
else in `CLAUDE.md` holds: verification jobs are queued, tests have tiers, examples keep their notes.

- **Commit each feature when it is done**, as in development, with the same command:
  `python3 llm-dlc/tools/sync.py commit -m "Summary line" -m "What changed, why, and how it was verified."`
  It writes the message with the release's trailer and starts a new change. A plain `jj commit` is as good; never
  `git commit`.
- **Nothing is published.** `sync.py push`, `upload`, `scan`, `review`, `allow`, `stamp` and `langfuse` refuse to run,
  and the hooks do nothing. Don't push to any remote. The one exception is a contribution upstream, after the user
  agrees to it.
- **A new example takes a number from 900 to 999**, which no release uses, so that an update never brings an example
  with the same number. A contribution renumbers it.
- **The work is the user's.** It lives as commits on top of the release commit, and an update moves them onto the next
  release. Don't rewrite or abandon the release commit or anything below it.
