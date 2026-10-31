# Instructions for Claude Code

This repo publishes every LLM session alongside the code it produced. Follow the procedure in [`llm-dlc/README.md`](llm-dlc/README.md#procedure-for-agents). In short:

- The version control system is jj, colocated with git. Never run `git commit`.
- Commit each feature as soon as it is finished and verified, without asking:
  `python3 llm-dlc/tools/sync.py commit -m "Summary line" -m "What changed, why, and how it was verified."`
  The later `-m` paragraphs appear in the session summary, so write them for a reader who did not see the conversation.
- Then run `python3 llm-dlc/tools/sync.py check`, which must report 0 errors.
- Don't edit anything under `llm-dlc/traces/` (including its README, which comes from `llm-dlc/traces-readme-template.md`), `llm-dlc/index.json`, or the `LLM-Trace` lines in commit messages. `sync.py commit` and `sync.py push` regenerate them.
- Push only when the user asks, with `python3 llm-dlc/tools/sync.py push --bookmark main`. It records any outstanding traces in a last commit and leaves `@` empty. The user can also run `/publish`.
- Don't print secrets: `llm-dlc/infra/langfuse/.env`, `~/.config/llm-traces/cloudflare-token`, and the wrangler OAuth token. Transcripts are published. Don't print raw transcripts or `~/.claude.json` either, and test redaction with made-up values only.
- `python3 llm-dlc/tools/sync.py scan` previews what a push would publish; relay its `warn` lines to the user before they push.
- `check` reports three levels. `ERROR` must be fixed. `warn` is for a person to judge, so relay it. `note` needs no action, and includes the 13 policy 3 logs listed in `ACCEPTED_LOGS` in `sync.py`, which were reviewed on 2026-10-31, found innocuous, and deliberately left published: don't withdraw them or ask about it again. See the history note in [`llm-dlc/specification.md`](llm-dlc/specification.md#storage). Any other published log with findings warns until a person decides. Review new logs thoroughly before they go out; a finding in a log not yet uploaded is still an error.
