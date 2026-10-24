# LLM traces

Every Claude Code session in this repo is published alongside the code it produced.
The aim is to make sharing LLM traces normal: a reader can see the code, the prompts,
the model's reasoning, and every tool call that led to each commit.

## Layout

```
traces/<session-id>/manifest.json                 checked in
traces/<session-id>/logs/<sha256>.jsonl.gz        gitignored; uploaded to blob storage
```

- **Manifest:** describes one session, meaning one context window plus any windows after a compaction.
  It holds high-level stats and points at the log.
- **Log:** the full redacted transcript (prompts, responses, thinking, tool calls and results, and raw API request records), stored gzipped.
  Subagent transcripts are separate logs in the same folder, listed under `subagents`.

## Identifiers

These are the stable part of the design. Everything else may change.

| Identifier | Definition | Properties |
|---|---|---|
| **Session ID** | The UUID that Claude Code assigns to a session | Names the folder and is the Langfuse session ID |
| **Log ID** | `sha256` of the **uncompressed** redacted JSONL | Content-addressed: the file `<sha256>.jsonl.gz` never changes. A new state of the transcript is a new file. Any blob store keyed by the hash can serve it. |
| **Commit → trace** | One message line per session: `LLM-Trace: <session-id> sha256:<log-sha256>` | Standard git trailer syntax: `git interpret-trailers --parse` reads it |
| **Trace → commits** | `manifest.commits[]`: each entry has a jj `change_id` (survives rewrites), plus `commit_id` (the git SHA) once the commit is immutable | Derived from the commit trailers on every sync, so the two directions agree |

**Invariants**, which `sync.py check` verifies:

1. Every `sha256:` in a commit message names a log whose content hashes to that value.
2. A log that a commit points at contains the whole conversation up to that commit.
   Logs are append-only: a later log of the same session starts with the exact bytes of every earlier one.
3. For a commit made with `jj trace-commit`, the `manifest.json` inside that commit's tree has the same `log.sha256` as the commit message.
   A plain `jj commit` gets its `LLM-Trace` line at the end of the next turn, pointing at a newer log, which `check` notes.
4. The hook never changes a pushed (immutable) commit. A change other than `@` gets its `LLM-Trace` line once. Only `@` is re-stamped each turn, together with its manifest.

A log's bytes depend on the redaction rules, so `manifest.redaction_policy` records the version.
A new policy produces new log IDs. Logs that commits already point at are kept.

## Manifest fields

| Field | Content |
|---|---|
| `schema` | `llm-trace-manifest/v1` |
| `session_id`, `status` | `open` while the session runs, `ended` after `SessionEnd` |
| `title`, `first_prompt`, `client`, `models` | What the session was and what ran it |
| `started`, `ended`, `duration_seconds` | Time span |
| `stats` | Turns, API calls, tool calls and errors, compactions, peak context tokens, and token usage (input, output, cache read, cache write) |
| `tools` | Count of calls per tool |
| `files_touched` | Files written by Edit and Write (repo-relative) |
| `context_windows[]` | The same stats for each window between compactions |
| `log` | `sha256`, `bytes`, `lines`, local `path`, `gzip_sha256`, `gzip_bytes`, and `locations` (upload URLs, empty for now) |
| `subagents[]` | For each subagent: its stats and its own `log` |
| `commits[]` | `change_id`, `commit_id`, `immutable`, `summary`, `log_sha256` |
| `langfuse`, `redaction_policy`, `generator` | Where to browse the session, and how the files were produced |

## Workflow

`.claude/settings.json` runs `tools/traces/sync.py hook` at the end of every turn (`Stop`) and when a session ends (`SessionEnd`). The hook:

1. Redacts the transcript, stores a new log snapshot, and rewrites the manifest.
2. Updates the `LLM-Trace` lines in jj. The current change (`@`) always points at the latest log. Earlier changes made in this session get a line only if they lack one.
3. Deletes logs that neither the manifest nor any commit points at.
4. Sends finished turns to Langfuse (`http://localhost:3000`), if it is running.

```bash
python3 tools/traces/sync.py init      # once per clone: jj file-size limit and the two aliases below
jj trace-commit -m "Summary line"      # finish @; its message and its manifest point at the same log
jj trace-push --bookmark main          # sync, check, push, then record the new git SHAs
python3 tools/traces/sync.py check     # verify hashes, trailers and redaction
python3 tools/traces/sync.py sync --all  # backfill every session of this repo
jj log -r 'description(substring:"LLM-Trace:")'   # changes that have traces
```

Plain `jj commit` and `jj describe` also work. The hook adds the `LLM-Trace` line on the next turn.

## Storage

Logs are gitignored because they are large: about 3 MB raw and 0.7 MB gzipped per hour of session.
Because they are content-addressed, the storage backend can change without touching any identifier.
For example: GitHub release assets, a Hugging Face dataset, S3 or R2, or Git LFS.
Upload URLs go in `log.locations`. Until a log is uploaded, `check` requires it to exist locally.

The first commit (`qxqvplms`) predates this layout. Its log is checked into that commit under `traces/sessions/`, and its message line has no `sha256:`. `check` reports it as a legacy note.

## Redaction

Traces are published, so `sync.py` redacts every JSON string, including keys, before hashing:

- your home directory becomes `~`, your username becomes `user`, and your git, jj and Claude account emails (including the part before the `@`) become `user@example.com`
- the secret values in `infra/langfuse/.env` are removed
- common token formats are removed: Anthropic, Langfuse, GitHub, AWS and Slack tokens, private keys, and bearer tokens
- extra literals in `~/.config/llm-traces/redact.txt` are applied, one per line, as `literal` or `literal => replacement`

**Read a log before you upload it.** Redaction catches identifiers and known token formats, not everything you might paste into a prompt.
