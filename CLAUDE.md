# Instructions for Claude Code

This repo publishes every LLM session alongside the code it produced. Follow the procedure in [`llm-dlc/README.md`](llm-dlc/README.md#procedure-for-agents). In short:

- The version control system is jj, colocated with git. Never run `git commit`.
- Commit each feature as soon as it is finished and verified, without asking:
  `python3 llm-dlc/tools/sync.py commit -m "Summary line" -m "What changed, why, and how it was verified."`
  The later `-m` paragraphs appear in the session summary, so write them for a reader who did not see the conversation.
- Then run `python3 llm-dlc/tools/sync.py check`, which must report 0 errors.
- Don't edit anything under `llm-dlc/traces/`, `llm-dlc/index.json`, or the `LLM-Trace` lines in commit messages. The Stop hook regenerates them every turn.
- Push only when the user asks, using `jj bookmark set main -r @-` and then `python3 llm-dlc/tools/sync.py push --bookmark main`.
- Don't print secrets: `llm-dlc/infra/langfuse/.env`, `~/.config/llm-traces/cloudflare-token`, and the wrangler OAuth token. Transcripts are published.
