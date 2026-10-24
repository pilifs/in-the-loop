# LLM traces

Every Claude Code session in this repo is published with the code it produced.
The aim is to make sharing LLM traces normal: a reader can see the code, the prompts,
the model's reasoning, and every tool call that led to each change.

## What gets recorded

| Where | What |
|---|---|
| `traces/sessions/<session-id>.jsonl` | The full Claude Code transcript, redacted: prompts, responses, tool calls and results, raw API request records. `.jsonl.gz` above 45 MB. |
| `traces/sessions/<session-id>/subagents/*.jsonl` | Transcripts of subagents spawned by that session |
| `traces/manifest.json` | One record per session: file, SHA-256, title, time span, client version, models, turns, token usage, and the jj changes it touched |
| jj change descriptions | One `LLM-Trace: <session-id>` trailer per session that touched the change |
| Local Langfuse (`http://localhost:3000`) | The same sessions as browsable traces: one trace per turn, with generation and tool spans, grouped by session ID |

The **session ID is the primary key** everywhere: it names the trace file, keys the manifest,
appears in the jj trailer, and serves as the Langfuse session ID.

```
jj change ──LLM-Trace: <sid>──▶ traces/manifest.json["sessions"][<sid>] ──file──▶ traces/sessions/<sid>.jsonl
          ◀──jj_changes[]───────                                       ──langfuse.session_id──▶ Langfuse session
```

## How it works

`.claude/settings.json` runs `tools/traces/sync.py hook` on every `Stop`, which fires at the end of each turn, and on `SessionEnd`. The hook:

1. Redacts the session transcript, together with any subagent transcripts, and writes it into `traces/sessions/`.
2. Records the current jj change (`@`) in the manifest. It then adds an `LLM-Trace` trailer to each mutable change listed for each session (`relink`).
3. Exports newly completed turns to Langfuse over OTLP. If Langfuse is down, it retries those turns on the next hook.

The trace file is written into the working copy, so a change contains the transcript that produced it.
The hook never fails a session. Its errors go to `~/.local/state/llm-traces/hook.log`.

## Redaction

Traces are published, so `sync.py` redacts every JSON string, including keys, before writing:

- your home directory becomes `~`, your username becomes `user`, and your git, jj and Claude account emails become `user@example.com`
- values of the secrets in `infra/langfuse/.env` are removed
- common token formats are removed: Anthropic, Langfuse, GitHub, AWS and Slack tokens, private keys, and bearer tokens
- extra literals in `~/.config/llm-traces/redact.txt` are applied, one per line, as `literal` or `literal => replacement`

`sync.py check` re-scans every published file for these, and also verifies hashes and trailers.
**Read a trace before you push it.** Redaction catches identifiers and known token formats, not everything you might paste into a prompt.

## Commands

```bash
infra/langfuse/up.sh                       # start Langfuse; first run generates .env with keys and an admin login
python3 tools/traces/sync.py sync --all    # backfill every session of this repo from ~/.claude/projects
python3 tools/traces/sync.py relink        # restore trailers after rewriting descriptions
python3 tools/traces/sync.py check         # verify before pushing; non-zero exit on problems
jj log -r 'description(glob:"*LLM-Trace:*")'   # changes that have traces
```

## Conventions

- Write the summary line of a jj description as usual. Leave the `LLM-Trace:` trailers in place, and if you remove one by accident, `relink` puts it back.
- `cleanupPeriodDays` is raised in `.claude/settings.json`, so Claude Code keeps raw transcripts locally for 10 years instead of 30 days.
- Repo config: `jj config set --repo snapshot.max-new-file-size 100MiB`. jj ignores new files over 1 MiB by default, and trace files are larger. The hook passes this flag itself, but your own `jj` commands need the repo config.
