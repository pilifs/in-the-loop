# LLM traces

Every Claude Code session in this repo is published alongside the code it produced.
The aim is to make sharing LLM traces normal: a reader can see the code, the prompts,
the model's reasoning, and every tool call that led to each commit.

This page is the specification. [`llm-dlc/README.md`](README.md) has the procedure that agents follow, and the index of sessions.

## Layout

```
llm-dlc/index.json                                        checked in; one row per session
llm-dlc/traces/README.md                                  checked in; every session added up
llm-dlc/traces-readme-template.md                         checked in; the template for that README
llm-dlc/summary-template.md                               checked in; the template for summary.md
llm-dlc/session-notes/<session-id>.md                     checked in; optional, written by hand
llm-dlc/traces/<session-id>/manifest.json                 checked in
llm-dlc/traces/<session-id>/summary.md                    checked in
llm-dlc/traces/<session-id>/logs/<sha256>.jsonl.gz        gitignored; uploaded to blob storage
```

- **Index:** the global manifest, a light list of every session with its title, time span, current log and the commits it made.
  It answers "which session made this commit" and "what happened in October" without opening every manifest.
  The same rows appear as a table in `llm-dlc/README.md`.
- **Traces overview:** `llm-dlc/traces/README.md`, totals and tables over all sessions: tokens, tools, commits and logs. It is rendered on every sync from the manifests and session notes alone, and `check` fails if it does not match them.
- **Session note:** a correction or context that the log and commits cannot give, such as work committed to another repo. It is written by hand, and appears as *Notes* near the top of `summary.md`.
- **Manifest:** the detailed metadata of one session, meaning one context window plus any windows after a compaction.
  It holds stats, the commits with their full messages, and every referenced log.
- **Summary:** the human-readable view of the session, rendered from `llm-dlc/summary-template.md`: each commit with the message the agent wrote, then each prompt with the final reply.
  It is in the same tree as the manifest, so the summary in a commit describes exactly the log that the commit points at.
- **Log:** the full redacted transcript (prompts, responses, thinking, tool calls and results, and raw API request records), stored gzipped.
  Subagent transcripts are separate logs in the same folder, listed under `subagents`.

Metadata is split this way, a small global index plus a detailed file per session, for two reasons.
A session's manifest changes on every turn of that session only, so separate sessions never edit the same detailed file.
The index is small and fully derived, so a merge conflict in it is resolved by running `sync.py sync`.

## Identifiers

These are the stable part of the design. Everything else may change.

| Identifier | Definition | Properties |
|---|---|---|
| **Session ID** | The UUID that Claude Code assigns to a session | Names the folder and is the Langfuse session ID |
| **Log ID** | `sha256` of the **uncompressed** redacted JSONL | Content-addressed: the file `<sha256>.jsonl.gz` never changes. A new state of the transcript is a new file. Any blob store keyed by the hash can serve it. |
| **Commit → trace** | One message line per session: `LLM-Trace: <session-id> sha256:<log-sha256>` | Standard git trailer syntax: `git interpret-trailers --parse` reads it |
| **Links** | Two lines above it: `LLM-Trace-Summary:` (the summary on GitHub, on the `main` branch) and `LLM-Trace-Log:` (the log on the CDN) | For readers only. Both are derived from the identifier line, and tools ignore them |
| **Trace → commits** | `manifest.commits[]`: each entry has a jj `change_id` (survives rewrites), plus `commit_id` (the git SHA) once the commit is immutable | Derived from the commit trailers on every sync, so the two directions agree |

**Invariants**, which `sync.py check` verifies:

1. Every `sha256:` in a commit message names a log whose content hashes to that value.
2. A log that a commit points at contains the whole conversation up to that commit.
   Logs are append-only: a later log of the same session starts with the exact bytes of every earlier one.
3. For a commit made with `jj trace-commit`, the `manifest.json` inside that commit's tree has the same `log.sha256` as the commit message.
   Older commits keep their manifest where the layout was at the time: `traces/<session-id>/manifest.json`, then `changes/traces/<session-id>/manifest.json`.
   A plain `jj commit` gets its `LLM-Trace` line at the end of the next turn, pointing at a newer log, which `check` notes.
4. The hook never changes a pushed (immutable) commit. A change other than `@` gets its `LLM-Trace` line once. Only `@` is re-stamped each turn, together with its manifest.

A log's bytes depend on the redaction rules, so `manifest.redaction_policy` records the version.
A new policy produces new log IDs. Logs that commits already point at are kept.

## Manifest fields

| Field | Content |
|---|---|
| `schema` | `llm-trace-manifest/v1` |
| `session_id`, `status` | `open` while the session runs, `ended` after `SessionEnd` |
| `title`, `first_prompt`, `client`, `models` | What the session was and what ran it. `client` is `{tool, version}`, for example `claude-code` |
| `started`, `ended`, `duration_seconds` | Time span |
| `stats` | Turns, API calls, tool calls and errors, compactions, peak context tokens, and token usage (input, output, cache read, cache write) |
| `tools` | Count of calls per tool |
| `files_touched` | Files written by Edit and Write (repo-relative) |
| `context_windows[]` | The same stats for each window between compactions |
| `log` | The current log: `sha256`, `bytes`, `lines`, `gzip_bytes` and the local `path` |
| `subagents[]` | For each subagent: its stats and its own `log` |
| `commits[]` | Oldest first: `change_id`, `commit_id`, `immutable`, `summary` (null until described), `body` (the message without its summary line and trailers), `log_sha256` |
| `logs` | Every log still referenced (the current one, subagent logs, and each log a commit points at), keyed by `sha256`: `bytes`, `lines`, `gzip_bytes`, and `url` once uploaded |
| `redaction_policy`, `generator` | How the files were produced |

The manifest is derived data. It is rebuilt from the transcript on every sync, and `summarize()` runs on the redacted entries, so it can also be rebuilt from a published log. Changing its schema is cheap; the identifiers above are not.

## Workflow

`.claude/settings.json` runs `llm-dlc/tools/sync.py hook` at the end of every turn (`Stop`) and when a session ends (`SessionEnd`). The hook:

1. Redacts the transcript, stores a new log snapshot, and rewrites the manifest, the summary and the index.
2. Updates the `LLM-Trace` lines in jj. The current change (`@`) always points at the latest log. Earlier changes made in this session get a line only if they lack one.
3. Deletes logs that neither the manifest nor any commit points at.
4. Sends finished turns to Langfuse (`http://localhost:3000`), if it is running.

```bash
python3 llm-dlc/tools/sync.py init      # once per clone: jj file-size limit and the two aliases below
jj trace-commit -m "Summary line" -m "Body"   # finish @; its message and its manifest point at the same log
jj trace-push --bookmark main          # sync, check, push, then record the new git SHAs
python3 llm-dlc/tools/sync.py check     # verify hashes, trailers and redaction
python3 llm-dlc/tools/sync.py sync --all  # backfill every session of this repo
jj log -r 'description(substring:"LLM-Trace:")'   # changes that have traces
```

Plain `jj commit` and `jj describe` also work. The hook adds the `LLM-Trace` lines on the next turn.

## Storage

Logs are gitignored in the repo and published on Cloudflare at a deterministic URL:

```
https://terminalvalue.net/raw-traces/<session-id>/<sha256>.jsonl.gz
```

so anyone can turn the `LLM-Trace:` line of a commit into a download, then check it:

```bash
curl -s https://terminalvalue.net/raw-traces/<sid>/<sha>.jsonl.gz | gunzip | sha256sum   # equals <sha>
```

- **R2 bucket `llm-traces`** holds the files. The object key is the URL path.
- **Worker `raw-traces`** ([`llm-dlc/infra/cdn/`](infra/cdn)) serves them on the route `terminalvalue.net/raw-traces/*`.
  It runs ahead of the Pages site on the same domain, so the site is unaffected and a site deploy cannot remove the logs.
  It is read-only (GET and HEAD only), rejects keys that are not `<uuid>/<64 hex>.jsonl.gz`, serves `application/gzip` without re-encoding, and caches each log at the edge forever (`immutable`).
- **`sync.py upload`** uploads only the logs that commits point at, plus subagent logs; it skips `@`, whose log changes every turn.
  After each upload it downloads the log again through the CDN, verifies its SHA-256, and only then records the URL in `manifest.logs[<sha256>].url`.
  `jj trace-push` runs the upload before pushing, so no pushed commit points at a log nobody else can fetch.
- **`sync.py check --remote`** downloads every recorded upload again and checks its hash.
- **`sync.py unpublish <sid> <sha256>`** takes a log down, for example after a redaction miss: it deletes the R2 object, purges the URL from every edge cache, and removes the URL from the manifest.
  Purging needs a Cloudflare API token that wrangler's login cannot grant. Create one with the permissions *Zone → Zone → Read* and *Zone → Cache Purge → Purge* for the zone only, and save it as `~/.config/llm-traces/cloudflare-token` (mode 600). Redaction removes the token from logs.

Deploying the Worker: `cd llm-dlc/infra/cdn && npx wrangler deploy`. Wrangler 4.149 uploads the script, then fails with error 10007 before it creates the route.
The route (`terminalvalue.net/raw-traces/*` → `raw-traces`) was created through the zone's Workers Routes API and already exists, so redeploys only need the script upload.

**History note.** The first three commits were made before this layout and redaction policy 3 existed. On 2026-10-24, before anyone had cloned the repo, they were rewritten so that every commit resolves to a log: their logs were regenerated from the same transcript prefixes under the current policy, their `LLM-Trace` lines updated, and the author email switched to a GitHub noreply address. The rewrite itself is in this session's log. The traces moved from `traces/` to `changes/traces/` later the same day; the identifiers and URLs did not change.
On 2026-10-30 they moved again, to `llm-dlc/traces/`, when the repo was split into `examples/` and `llm-dlc/`. Before the repo was shared, the `LLM-Trace-Summary` lines of earlier commits were rewritten to the new path, so those commits have new git SHAs. Their change IDs, trees, log IDs and CDN URLs did not change. Manifests inside older trees can still name the earlier SHAs; the change ID is the stable key.

## Redaction

Traces are published, so `sync.py` redacts every JSON string, including keys, before hashing:

- your home directory becomes `~`, your username becomes `user`, and your git, jj and Claude account emails (including the part before the `@`, in any letter case) become `user@example.com`. GitHub noreply addresses are public by design and are kept.
- account identifiers that Claude Code records in the transcript (`organizationUuid`, `accountUuid`) are removed, and the opaque `signature` of thinking blocks is dropped
- the secret values in `llm-dlc/infra/langfuse/.env` are removed
- common token formats are removed: Anthropic, Langfuse, GitHub, AWS and Slack tokens, private keys, and bearer tokens
- extra literals in `~/.config/llm-traces/redact.txt` are applied, one per line, as `literal` or `literal => replacement`

**Read a log before you upload it.** Redaction catches identifiers and known token formats, not everything you might paste into a prompt.
