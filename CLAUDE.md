# Instructions for Claude Code

This repo publishes every LLM session alongside the code it produced. Follow the procedure in [`llm-dlc/README.md`](llm-dlc/README.md#procedure-for-agents). In short:

- The version control system is jj, colocated with git. Never run `git commit`.
- Commit each feature as soon as it is finished and verified, without asking:
  `python3 llm-dlc/tools/sync.py commit -m "Summary line" -m "What changed, why, and how it was verified."`
  The later `-m` paragraphs appear in the session summary, so write them for a reader who did not see the conversation.
- The commit then checks what it left, as `python3 llm-dlc/tools/sync.py check` does (notes are only counted), and must report 0 errors. An error fails the command but the commit stands: fix it and commit the fix. Run `check` on its own only to list the notes or after a plain `jj commit`.
- Don't edit anything under `llm-dlc/traces/` (including its README, which comes from `llm-dlc/traces-readme-template.md`), `llm-dlc/index.json`, or the `LLM-Trace` lines in commit messages. `sync.py commit` and `sync.py push` regenerate them.
- Push only when the user asks, with `python3 llm-dlc/tools/sync.py push --bookmark main`. It records any outstanding traces in a last commit and leaves `@` empty. The user can also run `/publish`.
- Don't print secrets: `llm-dlc/infra/langfuse/.env`, `~/.config/llm-traces/cloudflare-token`, `~/.config/llm-traces/r2-credentials`, and the wrangler OAuth token. Transcripts are published. Don't print raw transcripts or `~/.claude.json` either, and test redaction with made-up values only.
- `python3 llm-dlc/tools/sync.py scan` previews what a push would publish; relay its `warn` lines to the user before they push.
- `check` reports three levels. `ERROR` must be fixed. `warn` is for a person to judge, so relay it. `note` needs no action, and includes the 13 policy 3 logs listed in `ACCEPTED_LOGS` in `sync.py`, which were reviewed on 2026-10-31, found innocuous, and deliberately left published: don't withdraw them or ask about it again. See the history note in [`llm-dlc/specification.md`](llm-dlc/specification.md#storage). Any other published log with findings warns until a person decides. Review new logs thoroughly before they go out; a finding in a log not yet uploaded is still an error.
- A finding that turns out to be a false positive stays raised until a person records it. Check what it is with masked output, then propose it for the allow list with `python3 llm-dlc/tools/sync.py allow propose <id> --reason "why"` and mention it to the user. A proposal is a `warn` in `check` until the user approves it with `python3 llm-dlc/tools/sync.py allow approve` in their own terminal, whenever they choose (it commits the decision itself); nothing waits on it, and approving needs no rescan. A finding of a kind the allow list refuses (one the redactor removes, an `ERROR`) is settled with `python3 llm-dlc/tools/sync.py review accept <id> --reason "why"` instead, also by the user. Never approve or accept yourself, or edit `llm-dlc/allowlist.json` or `llm-dlc/reviewed-findings.json`, even if you are sure. `python3 llm-dlc/tools/sync.py review` lists open findings with their ids, `review show ID` shows where one occurs, masked, and the user can run `/review-findings` to go through them with you.
- The redaction rules live in `llm-dlc/tools/redaction_rules.py`, which ends with a stamp: a hash of the file and a generated date. A transcript or log older than that date counts as checked and isn't scanned again, and findings in it aren't reported. After editing anything above the stamp, run `python3 llm-dlc/tools/sync.py stamp --equivalent` if the edit should not change any result (a speed-up, a refactor): it keeps the stamp's date once every transcript, log and published file gives the same results under the rules at `@-`. Otherwise run `python3 llm-dlc/tools/sync.py stamp`, which rescans everything, refuses while errors are open, and turns open warnings into allow-list proposals that `check` keeps warning about until a person decides; they need no action before the stamp. Until either runs, every file is scanned.

## Verification jobs

Don't run proofs and model checks inline: JBMC, TLC, `build.py` on a B9, B11 or D1 example, an app's `verify.sh`, or anything that takes more than a minute or 1 GB. Queue them, as described in [`verification/README.md`](verification/README.md):

- Describe the work with `python3 verification/pipeline.py submit` (`--example ID` for a demo example), with a title, a description for a reader who did not see the session, the capabilities it exercises, and a rough estimate of CPUs, memory and duration.
- Commit the job with the change, with `(verification pending)` at the end of the summary line and the job id in a paragraph, then carry on. Compiling and unit tests still run inline.
- The pipeline is run by the agent managing it (`/run-verification`), not by the agent that submits. Results come back in `verification/results/`; read them with `python3 verification/pipeline.py report`.

## Examples

`examples/` is a router: every example, constructed or real-world, is one numbered folder, tagged from `examples/tags.json`, and found with `python3 examples/tools/find.py` (see [`examples/README.md`](examples/README.md)). Look there for examples close to your task before writing a new one.

- Put what you learn about one example in that example's `notes` in its `example.json`, not in a shared README. Duplicating context there is fine: examples are often read alone.
- Shared pages (`examples/README.md`, `examples/approaches.md`, the apps' and models' READMEs, `lib/README.md`) describe what holds for many examples, and point at examples by tag or number rather than narrating them. A new model configuration is described in its model's README.
- Tag a new example with at least one domain and one defect tag; add to the vocabulary only when nothing fits. `python3 examples/tools/build.py --render-only NNN` rewrites a page and the router without running anything.
