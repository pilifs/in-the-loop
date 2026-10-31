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
   This holds for a plain `jj commit` or `git commit` too, because a hook reopens the new commit and syncs into it. If `@` already holds trace files, the hook leaves the commit for the next sync, which stamps it with a newer log, and `check` notes that.
4. The tools never change a pushed (immutable) commit. A change gets its `LLM-Trace` line once, when it is committed.
5. `@` stays empty unless someone is working: only `commit` and `push` write tracked trace files, and `push` writes nothing after it pushes.
   So a pushed manifest does not know its own commit's SHA. The next commit records it.

A log's bytes depend on the redaction rules, so `manifest.redaction_policy` records the version.
A new policy produces new log IDs. Logs that commits already point at are kept.

## Manifest fields

| Field | Content |
|---|---|
| `schema` | `llm-trace-manifest/v1` |
| `session_id`, `status` | `open` if the transcript changed in the last 10 minutes when last synced, otherwise `ended` |
| `title`, `first_prompt`, `client`, `models` | What the session was and what ran it. `client` is `{tool, version}`, for example `claude-code` |
| `started`, `ended`, `duration_seconds` | Time span |
| `stats` | Turns, API calls, tool calls and errors, compactions, peak context tokens, and token usage (input, output, cache read, cache write) |
| `tools` | Count of calls per tool |
| `files_touched` | Files written by Edit and Write (repo-relative) |
| `context_windows[]` | The same stats for each window between compactions |
| `log` | The current log: `sha256`, `bytes`, `lines`, `gzip_bytes` and the local `path` |
| `subagents[]` | For each subagent: its stats and its own `log` |
| `commits[]` | Oldest first: `change_id`, `commit_id`, `immutable`, `summary` (null until described), `body` (the message without its summary line and trailers), `log_sha256` |
| `logs` | Every log still referenced (the current one, subagent logs, and each log a commit points at), keyed by `sha256`: `bytes`, `lines`, `gzip_bytes`, `url` once uploaded, and `withdrawn` (the reason) if it was taken down after publication |
| `redaction_policy`, `generator` | How the files were produced |

The manifest is derived data. It is rebuilt from the transcript on every sync, and `summarize()` runs on the redacted entries, so it can also be rebuilt from a published log. Changing its schema is cheap; the identifiers above are not.

## Workflow

`.claude/settings.json` runs two hooks, and `sync.py` does the rest:

- **End of a turn or session** (`Stop`, `SessionEnd`, `sync.py hook`): sends finished turns to Langfuse (`http://localhost:3000`), if it is running, and leaves the repo alone. Nothing depends on this: a transcript stays on disk until a commit or push records it.
- **After a shell command** (`PostToolUse`, `sync.py hook-commit`): if the command was a plain `jj commit`, `jj new` or `git commit`, traces the new commit as below.
- **On a commit** (`sync.py commit`): redacts each transcript, stores a new log snapshot, rewrites the manifest, the summary, the index and the overview, stamps the `LLM-Trace` lines, and deletes logs that nothing points at. Earlier changes made in a session get a line only if they lack one.
- **On a push** (`sync.py push`): does the same, stamping `@` for every session with log that no commit points at, runs `check`, uploads the logs, runs `check` again, and freezes `@` as a *Record session traces* commit. It makes that commit only if a log or upload is new, so a repeated push changes nothing. The first `check` runs before anything is uploaded, and the upload itself refuses a log in which the current redaction rules would still change something, so a leak that the rules know about cannot reach the CDN.

```bash
python3 llm-dlc/tools/sync.py init      # once per clone: jj file-size limit and the two aliases below
jj trace-commit -m "Summary line" -m "Body"   # finish @; its message and its manifest point at the same log
jj trace-push --bookmark main          # record outstanding traces, upload, check, push; leaves @ empty
python3 llm-dlc/tools/sync.py check     # verify hashes, trailers and redaction
python3 llm-dlc/tools/sync.py scan      # preview a publish: what was redacted, what to look at (writes nothing)
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
- **`sync.py unpublish <sid> <sha256> [--reason TEXT]`** takes a log down, for example after a redaction miss: it deletes the R2 object, purges the URL from every edge cache, and removes the URL from the manifest. With a reason, the log is *withdrawn*: the local copy is deleted too, the manifest records the reason under `logs[<sha256>].withdrawn`, the summary lists it under *Notes*, and `check` reports the commits that still point at it as a note rather than an error. The content is gone; the hash in the trailers still identifies what it was.
  Purging needs a Cloudflare API token that wrangler's login cannot grant. Create one with the permissions *Zone → Zone → Read* and *Zone → Cache Purge → Purge* for the zone only, and save it as `~/.config/llm-traces/cloudflare-token` (mode 600). Redaction removes the token from logs.

Deploying the Worker: `cd llm-dlc/infra/cdn && npx wrangler deploy`. Wrangler 4.149 uploads the script, then fails with error 10007 before it creates the route.
The route (`terminalvalue.net/raw-traces/*` → `raw-traces`) was created through the zone's Workers Routes API and already exists, so redeploys only need the script upload.

**History note.** Redaction policy 4 (2026-10-31) added the hostname, Windows account names, account identifiers inside strings, third-party emails, wrangler's tokens and the broader credential formats above, after a review found the Anthropic organization UUID, the hostname and a third-party email in the logs of the first session. Those logs are policy 3 and stay as they were published; `check` reports what the current rules find in them. The findings were reviewed the same day and judged innocuous, so the maintainer accepted them: the `check` notes on these logs are warnings that need no action, and withdrawing the logs is not worth the trouble. The answer is more thorough review before publishing from now on, not cleaning up what is already out.

The first three commits were made before this layout and redaction policy 3 existed. On 2026-10-24, before anyone had cloned the repo, they were rewritten so that every commit resolves to a log: their logs were regenerated from the same transcript prefixes under the current policy, their `LLM-Trace` lines updated, and the author email switched to a GitHub noreply address. The rewrite itself is in this session's log. The traces moved from `traces/` to `changes/traces/` later the same day; the identifiers and URLs did not change.
On 2026-10-30 they moved again, to `llm-dlc/traces/`, when the repo was split into `examples/` and `llm-dlc/`. Before the repo was shared, the `LLM-Trace-Summary` lines of earlier commits were rewritten to the new path, so those commits have new git SHAs. Their change IDs, trees, log IDs and CDN URLs did not change. Manifests inside older trees can still name the earlier SHAs; the change ID is the stable key.

## Redaction

Traces are published, so `sync.py` redacts every JSON string, including keys, before hashing. This is redaction policy 4:

- **This machine.** Your home directory becomes `~`, your username becomes `user`, your hostname becomes `host`, and Windows account names in `/mnt/<drive>/Users/<name>` and `<drive>:\Users\<name>` paths become `user`. Your git, jj and Claude account emails (including the part before the `@`, in any letter case) become `user@example.com`.
- **Your accounts.** The identifiers Claude Code records (`organizationUuid`, `accountUuid`, `userID`) are removed wherever they occur: under those keys in the transcript, and inside strings, such as a transcript or `~/.claude.json` echoed by a tool. The opaque `signature` of thinking blocks is dropped.
- **Local secrets.** The secret values in `llm-dlc/infra/langfuse/.env` and the Basic auth header built from them, the Cloudflare token in `~/.config/llm-traces/cloudflare-token`, and wrangler's OAuth tokens in `~/.config/.wrangler/config/default.toml` are removed. Plain URLs in `.env`, such as `NEXTAUTH_URL`, are left alone.
- **Everyone else's email.** Every other email address becomes `[REDACTED:email]`, except addresses that are public by design or placeholders: GitHub noreply addresses, `noreply@anthropic.com`, `git@github.com`, and the `example.com`, `langfuse.local` and `localhost` domains.
- **Credential formats.** Anthropic, OpenAI-style `sk-`, Langfuse, GitHub, GitLab, AWS, Google, Slack, npm, Hugging Face, Stripe and SendGrid keys, Slack and Discord webhooks, JWTs, private keys, bearer and Basic authorization headers, passwords in URLs (`scheme://user:password@host`) and in `curl -u`, and the value of any `KEY=VALUE` or `"key": "value"` pair whose key says it is a secret (`PASSWORD`, `SECRET`, `TOKEN`, `API_KEY`, `_AUTH` and the like). Templates such as `${VAR}` or `<placeholder>`, expressions, paths, flags, and values shorter than 8 characters are left.
- **Your own list.** Extra literals in `~/.config/llm-traces/redact.txt` are applied, one per line, as `literal` or `literal => replacement`.

Every rule leaves its own output alone, so redaction is idempotent and `check` can run the same rules over a finished log: anything they would still change is reported as `unredacted`, and the upload refuses such a log. A policy change therefore also audits the logs that are already published: what the new rules find in them is reported as a note, not an error, because the only remedy is `unpublish --reason` and whether a finding is worth that is a person's call.

Not everything can be a rule. **Read a log before you upload it.** `sync.py scan` previews what a push would publish for each session: the redaction markers by kind, and *warnings* about things no rule removes and a person should judge: public IP addresses, home directories of other users, authorization and cookie headers, long mixed-case tokens of unknown format. `check` prints the same warnings for logs that are not yet uploaded, and `push` prints them for each log as it goes up. Output is masked, because it lands in the transcript of the session that runs it.

The agent itself is a common leak vector: while building or testing a redactor it tends to grep its own transcript, or to paste a real identifier into a test. Use made-up values in tests, and keep raw transcripts and `~/.claude.json` out of tool output.
