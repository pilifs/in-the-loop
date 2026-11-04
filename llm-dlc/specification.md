# LLM traces

Every Claude Code session in this repo is published alongside the code it produced.
The aim is to make sharing LLM traces normal: a reader can see the code, the prompts,
the model's reasoning, and every tool call that led to each commit.

This page is the specification. [`llm-dlc/README.md`](README.md) has the procedure that agents follow, and the index of sessions.

## Layout

```
llm-dlc/index.json                                        checked in; one row per session
llm-dlc/traces/README.md                                  checked in; every session added up
llm-dlc/traces/metrics.json                               checked in; every session added up, as data
llm-dlc/pricing.json                                      checked in; list prices, written by hand
llm-dlc/allowlist.json                                    checked in; false positives by value, proposed and approved
llm-dlc/reviewed-findings.json                            checked in; false positives a person reviewed, by hash
llm-dlc/traces-readme-template.md                         checked in; the template for that README
llm-dlc/summary-template.md                               checked in; the template for summary.md
llm-dlc/session-notes/<session-id>.md                     checked in; optional, written by hand
llm-dlc/traces/<session-id>/manifest.json                 checked in
llm-dlc/traces/<session-id>/summary.md                    checked in
llm-dlc/traces/<session-id>/metrics.json                  checked in
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

## Metrics

`metrics.json` holds what a chart needs, so nobody has to parse a log to draw one. `sync.py` writes it on every commit and push, using `tools/metrics.py`, next to the summary it belongs to. Like the manifest it is derived data, and changing its schema is cheap.

It is a function of three inputs and nothing else: the session's current log, its manifest, and `llm-dlc/pricing.json`. So it contains no clock, and `check` rebuilds it and fails if it differs. `check` also fails if its token totals differ from the manifest's, which are counted by separate code, and warns about a model with no price. Free text (prompts, tool labels, error heads) is cut to 200 characters and redacted again after the cut, and the file is scanned like the summary. The file is JSON with one table row per line, so a commit's diff is the rows it added.

**Session file** (`llm-trace-metrics/v1`):

| Field | Content |
|---|---|
| `source`, `pricing_as_of` | The log the file was built from, and the price list used |
| `totals` | Prompts, commands, commits, compactions, subagents, tool errors, peak context, and the usage block below |
| `after_last_commit` | The usage block for work no commit points at yet |
| `time` | `elapsed_ms`, `agent_ms`, `model_ms`, `tool_ms`, `busy_ms`, `compaction_ms`, `paused_ms` (see *Time*) |
| `reported` | What Claude Code itself counted, or null (see *Cost*) |
| `by_model`, `by_effort`, `by_tool`, `by_bash_family`, `by_cache_cause` | Group totals, most expensive or most used first |
| `windows[]` | One row per context window: span, prompts, peak context, usage |
| `compactions[]` | `ts`, `line`, `window` (the one it starts), `trigger`, `pre_tokens`, `post_tokens`, `ms` |
| `pauses[]` | Gaps of 30 minutes or more between records: `start`, `end`, `ms`, `after_prompt` |
| `commits[]` | Oldest first: `change_id`, `summary`, log sizes, `ts`, and the prompts, agent time and usage since the commit before |
| `prompts[]` | Each thing that started work: `kind` (`human`, `command`, `task_notification`), `text`, `chars`, `window`, `commit`, its usage, models and time |
| `calls[]` | Each model call: `seq`, `agent`, `line`, `start`, `end`, `window`, `prompt`, `commit`, `model`, `effort`, `stop_reason`, `context_tokens`, usage, `thinking_ms`, `tools` |
| `tools[]` | Each tool call: `seq`, `agent`, `line`, `name`, `call`, `prompt`, `commit`, `start`, `end`, `ms`, `status` (`ok`, `error`, `no_result`), `error_kind`, `result_chars`, `family` (the program, for Bash), `label`, `error` |
| `cache_events[]` | Each large cache write and why it happened (see *Cache events*) |

The **usage block** is the same everywhere: `api_calls`, `tool_calls`, `input_tokens`, `output_tokens`, `thinking_tokens` (part of the output), `cache_read_tokens`, `cache_write_tokens` (which is `cache_write_5m_tokens` plus `cache_write_1h_tokens`), `usd`, `uncached_usd` and `unpriced_calls`. A row's numbers add up: the usage of `prompts[]`, of `windows[]`, and of `commits[]` plus `after_last_commit` each equal `totals`.

**Rollup** (`llm-dlc/traces/metrics.json`, `llm-trace-metrics-rollup/v1`): the same totals, time and groups over all sessions, plus `by_day`, `sessions[]` and `commits[]`, where a commit that several sessions worked on is one row naming each of them. It is a function of the session files and the manifests. It leaves out the per-call tables, so a page can load it alone.

**How rows connect.** `prompt`, `commit`, `window`, `call` and `seq` are indexes into the tables of the same file. `line` is the line of the session's log, counted from 1, so any row can be found in the log. A commit's log is a prefix of the session's log and redaction works line by line, so the line count of that log says which calls came before the commit, even when the two logs were made under different redaction policies. A commit whose log was withdrawn has no line count and shows no work; that work moves to the next commit. Subagent rows have an `agent` id. Their `line` is in the subagent's own log, and they are placed in a prompt by time.

**Cost.** `usd` is tokens times the list price, and `uncached_usd` is what the same calls would cost if nothing were cached. Both are estimates of list price, not a bill: fast mode and web search are not priced. Logs leave out some calls, namely compactions and Haiku side calls, so the sum of `calls[]` is lower than the real cost. Claude Code writes its own count in a `cost-state` record when a session stops, and `reported` keeps the last one: `usd`, per-model usage, `api_ms`, `tool_ms`, lines changed, and `unattributed_usd`, the part of that cost that no call in the log explains. A session that has not stopped yet has no `reported`.

**Time.** `agent_ms` is the span from a prompt to the last record of its turn, summed over prompts. `model_ms` is the time covered by at least one model call, from the request to the last block of the response. `tool_ms` is the same for tool calls, and `busy_ms` for either. These are unions because tool calls run in parallel, so a sum would count overlapping time twice. `tool_ms` comes from timestamps, so it includes time spent waiting for a person to approve a call; `reported.tool_ms` does not.

**Cache events.** A call starts an event if it read under half of the previous call's context, which means the cached prefix was lost, or if it wrote 20,000 tokens or more with the prefix intact. `cause` is the first of these that applies, and `also` lists the others:

| Cause | Meaning |
|---|---|
| `session_start` | The first call of a session or subagent |
| `compaction` | A compaction came between this call and the last |
| `model_switch` | The model changed; caches belong to one model |
| `cache_expired` | The last call started longer ago than the TTL: an hour once the session has written a 1-hour entry, otherwise 5 minutes |
| `effort_change` | The effort level changed |
| `unexplained` | The prefix was lost and the log does not say why |
| `large_input` | One large input, such as a skill or a big tool result. `after_tools` names what the previous call ran, `later_calls` counts the calls in the window that read it again, and `reread_usd` is what those reads cost |

`tokens` is the size of the write, `write_usd` its cost, and `excess_usd` what it cost above reading the same tokens from the cache.

## Workflow

`.claude/settings.json` runs two hooks, and `sync.py` does the rest:

- **End of a turn or session** (`Stop`, `SessionEnd`, `sync.py hook`): sends finished turns to Langfuse (`http://localhost:3000`), if it is configured and running, and leaves the repo alone; without a configuration it reads nothing. It reads the transcript from a cursor kept with the session's Langfuse state in `~/.local/state/llm-traces/`: the start of the first turn not yet sent, used only while the bytes before it have the SHA-256 it recorded under the same rules and tools, so a turn costs about what that turn added. A transcript that was replaced or cut, or any under `LLM_TRACES_FULL=1`, is read whole, from the log `sync` last made of it where that still applies. Nothing depends on this: a transcript stays on disk until a commit or push records it.
- **After a shell command** (`PostToolUse`, `sync.py hook-commit`): if the command was a plain `jj commit`, `jj new` or `git commit`, traces the new commit as below.
- **On a commit** (`sync.py commit`): syncs each session whose inputs or outputs changed since it was last synced, which always includes the one committing (named by Claude Code in `CLAUDE_CODE_SESSION_ID`, besides any whose transcript changed in the last 10 minutes); a session left alone is one that syncing again would not change (see [Local caches](#local-caches)). For each, it redacts what the transcript gained since the last commit, stores a new log snapshot, rewrites the manifest, the summary, the metrics, the index and the overview (each file only if its content changed, and the files over all sessions once, after the last session), stamps the `LLM-Trace` lines, and deletes logs that nothing points at. Earlier changes made in a session get a line only if they lack one. After `jj new` it runs `check` on the result, with the caches below, so the check costs what the commit added rather than the whole history: it prints errors and warnings, counts the notes, and fails if there is an error, though the commit stands. A plain `jj commit` traced by the hook is not checked. A commit does not contact Langfuse: the end-of-turn hook sends finished turns, and `sync.py langfuse SID...` sends those of a session whose hook ran while Langfuse was down, from its stored log.
- **On a push** (`sync.py push`): does the same, stamping `@` for every session with log that no commit points at, runs `check`, uploads the logs, runs `check` again, and freezes `@` as a *Record session traces* commit. It makes that commit only if a log or upload is new, so a repeated push changes nothing. The first `check` runs before anything is uploaded, and the upload itself refuses a log in which the current redaction rules would still change something, so a leak that the rules know about cannot reach the CDN. The second `check` reads the files on disk, so before `jj git push` a last gate reads the revisions the push would move bookmarks to (those named by `--bookmark`, `-r`, `-c` or `--all`, otherwise every bookmark ahead of the remote ones) from git: each must hold, byte for byte, the trace files that `check` read (manifests, summaries, metrics, session notes, the index, the overview, the rollup and the two review lists), and no other file where those live, such as a log; and every `LLM-Trace` line of a commit that the push makes public must name a log whose manifest records its URL, or that was withdrawn. Otherwise nothing is pushed. It costs one `git ls-tree` per revision and a hash of each of those files.
- **One at a time** (`Operation` in `sync.py`): every command that writes (`sync`, `commit`, `push`, `upload`, `unpublish`, `stamp`, `allow`, `review`, `init`, and the commit hook) holds an exclusive lock on the repository while it runs; `check` and `scan` hold it shared, so they never read a sync half done. A command that finds it held says which command holds it and waits; the commit hook waits at most 15 s and otherwise leaves the commit to the next sync, which stamps it anyway. The Stop hook takes no lock: it writes only its own cursor. Before each step that an interruption would leave half done, the command writes it to a journal, and clears it after: the commit hook's switch of the working copy to the commit it records, a commit's describe-to-`jj new`, a sync's sessions and global files, and a push's stages. A command that is killed leaves the journal behind, and the next writing command recovers it before it starts: it puts the working copy back if it is still on the recorded commit, rebuilds the global files, and names what an interrupted commit or push left to be run again. SIGTERM and SIGHUP (a hook's 60 s timeout, a closed terminal) unwind like Ctrl-C, so the working copy is put back at once. The lock is `flock`, released by the kernel when its holder dies, and it, the journal and the holder's name are local, in `~/.local/state/llm-traces/locks/`, keyed by the repository's path. Taking the lock costs about 0.1 ms, and the first journaled step one `jj op log` call (about 11 ms), which the journal records so `jj op log` can show what an interrupted command did.

```bash
python3 llm-dlc/tools/sync.py init      # once per clone: jj file-size limit and the two aliases below
jj trace-commit -m "Summary line" -m "Body"   # finish @; its message and its manifest point at the same log
jj trace-push --bookmark main          # record outstanding traces, upload, check, push; leaves @ empty
python3 llm-dlc/tools/sync.py check     # verify hashes, trailers and redaction
python3 llm-dlc/tools/sync.py check --full  # the same, trusting no cached result (LLM_TRACES_FULL=1 for sync and push too)
python3 llm-dlc/tools/sync.py scan      # preview a publish: what was redacted, what to look at (writes nothing)
python3 llm-dlc/tools/sync.py sync --all  # backfill every session of this repo (plain `sync`: only those that changed)
python3 llm-dlc/tools/sync.py perf      # where the last commands' time went (LLM_TRACES_PERF=1 prints it as each ends)
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
  It handles four logs at once (`LLM_TRACES_UPLOAD_JOBS`), so that the CDN reads overlap, and runs one wrangler put at a time (`LLM_TRACES_PUT_JOBS`), since every wrangler process shares one OAuth login. Before a put it verifies the stored `.gz` file against the log's name and scans the log, through the caches `check` keeps (by the `.gz` bytes, then by content), so a log `check` has just scanned is not scanned again; `LLM_TRACES_FULL=1` reads and scans everything. Each URL goes into its manifest as soon as the CDN serves the log, so an interrupted push keeps what it verified.
  `~/.local/state/llm-traces/uploads.json` is the upload record, local to the machine: each log a push started to upload, as *attempted* (written before the put, so the object may be in R2) or *verified* (the CDN served its content afterwards). A log not in it was never attempted from there. The next push names the logs an interrupted one may have uploaded; the manifests and the CDN still decide what is uploaded, and `unpublish` removes the log's entry.
  `jj trace-push` runs the upload before pushing, and its last gate refuses to push a commit that points at a log with no recorded URL, so no pushed commit points at a log nobody else can fetch.
- **`sync.py check --remote`** downloads every recorded upload again and checks its hash.
- **`sync.py unpublish <sid> <sha256> [--reason TEXT]`** takes a log down, for example after a redaction miss: it deletes the R2 object, purges the URL from every edge cache, and removes the URL from the manifest. With a reason, the log is *withdrawn*: the local copy is deleted too, the manifest records the reason under `logs[<sha256>].withdrawn`, the summary lists it under *Notes*, and `check` reports the commits that still point at it as a note rather than an error. The content is gone; the hash in the trailers still identifies what it was.
  Purging needs a Cloudflare API token that wrangler's login cannot grant. Create one with the permissions *Zone → Zone → Read* and *Zone → Cache Purge → Purge* for the zone only, and save it as `~/.config/llm-traces/cloudflare-token` (mode 600). Redaction removes the token from logs.

Deploying the Worker: `cd llm-dlc/infra/cdn && npx wrangler deploy`. Wrangler 4.149 uploads the script, then fails with error 10007 before it creates the route.
The route (`terminalvalue.net/raw-traces/*` → `raw-traces`) was created through the zone's Workers Routes API and already exists, so redeploys only need the script upload.

**History note.** Redaction policy 4 (2026-10-31) added the hostname, Windows account names, account identifiers inside strings, third-party emails, wrangler's tokens and the broader credential formats above, after a review found the Anthropic organization UUID, the hostname and a third-party email in the logs of the first session. Those logs are policy 3 and stay as they were published; `check` reports what the current rules find in them. The findings were reviewed the same day and judged innocuous, so the maintainer accepted them: these 13 logs are listed in `ACCEPTED_LOGS` in `sync.py`, `check` reports them as a note that needs no action, and withdrawing them is not worth the trouble. The answer is more thorough review before publishing from now on, not cleaning up what is already out.

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

Every rule leaves its own output alone, so redaction is idempotent and `check` can run the same rules over a finished log: anything they would still change is reported as `unredacted`, and the upload refuses such a log. A policy change therefore also audits the logs that are already published: what the new rules find in them is reported as a warning, not an error, because the only remedy is `unpublish --reason` and whether a finding is worth that is a person's call. Once a person has decided to keep a log up, its hash goes in `ACCEPTED_LOGS` and the warning becomes a note. Acceptance is by hash, so a later policy that flags other published logs warns about them.

The rules live in `tools/redaction_rules.py`, which ends with a stamp: a hash of the file above it and the date the rules were last applied to everything. A transcript or log older than that date counts as checked, so `check`, `scan`, `review` and `sync` don't scan it again. `sync` reuses the log it stored, and any findings in that file are no longer reported, which `check` says in a note. Editing the rules voids the date, so every file is scanned until `sync.py stamp` has rescanned them and recorded a new one. It refuses while errors are open, because they would stop being reported. An open warning does not hold it up: it is added to the allow list as a proposal (without its value), and `check` warns about the proposal until a person approves or drops it. An edit that changes no result, such as a speed-up, keeps the old date instead: `sync.py stamp --equivalent` compares the edited rules with the stamped ones committed at `@-` on every distinct line of every transcript, stored log and published file (redaction, and findings before and after redaction), and writes the new hash with the old date only if nothing differs. The date then still says which files have been checked, because the edited rules would have found the same in them. `upload` still scans each log it sends, as the last check before a log goes public, but takes the result from the scan cache when `check` has already scanned exactly that content under the same rules. A log older than the stamp, which `check` leaves out, is scanned here all the same.

`check` reports three levels. An `ERROR` must be fixed and fails the command. A `warn` is for a person to judge and does not fail it. A `note` needs no action, and is grouped per session rather than printed per log.

**Reviewed false positives.** A finding that a person has judged harmless would otherwise come back with every new log snapshot, so `llm-dlc/reviewed-findings.json` records it. An entry covers one kind and one exact value, named by a hash, with the reason, who decided and when. The same value is then left out of `check`, `scan`, `push` and the upload refusal wherever it appears, including in future logs, and a different value of the same kind is still raised. `check` notes how many findings it left out, and fails if an entry has no reason, no author or no date. This works for errors as well as warnings, except for `local-secret` and `account-id`: a match there is this machine's secret or account by construction, so no entry can waive it. `ACCEPTED_LOGS` is different: it accepts whole published logs whatever they contain, and is kept for the 13 logs reviewed that way.

```bash
python3 llm-dlc/tools/sync.py review                               # open findings, masked, with ids
python3 llm-dlc/tools/sync.py review accept <id>... --reason "why"  # a person, at a terminal
```

Listing is open to anyone. Accepting is a person's decision: the command shows the real value, asks for a typed confirmation, and refuses a shell with no terminal or one that Claude Code started. The project settings also deny agents direct edits to the list. These stop an agent acting by accident, not one set on getting round them, so the record that counts is the file's history: the list is published, and each change to it is in a commit with its session. The first four entries were authorized in chat by the maintainer on 2026-10-31, before the command existed, and say so.

**The allow list.** Accepting by id means finding the value again, which takes a scan of every file newer than the stamp, and a class of false positives (version numbers that look like addresses) used to be settled by a new rule, which voids the stamp and rescans everything. `llm-dlc/allowlist.json` settles them by value instead, without touching the rules. An agent that judges a finding a likely false positive proposes it by id, with a reason; the proposal holds the kind and the masked value, never the real one. A person approves proposals at a terminal: the command shows each real value with its count and where it occurs, asks for one typed confirmation for all of them, and writes the value into the entry. Values come from a cache of the last scan's findings (`~/.local/state/llm-traces/finding-values.json`, readable by its owner only), so neither proposing nor approving scans unless an id is not in it. Approved values are left out the same way as reviewed ones, and since the list is data, not rules, the stamp stays valid. A person can also add a value before anything finds it.

```bash
python3 llm-dlc/tools/sync.py allow                                       # entries: approved values, proposals masked
python3 llm-dlc/tools/sync.py allow propose <id>... --reason "why"         # anyone, an agent included
python3 llm-dlc/tools/sync.py allow approve [<id>...]                      # a person, at a terminal
python3 llm-dlc/tools/sync.py allow add <value> --kind <kind> --reason "why"  # a person, at a terminal
python3 llm-dlc/tools/sync.py allow drop <id>...                           # remove entries
```

The list is published with its values, so it takes only the kinds that the redactor leaves in a log and that are published anyway once accepted: `public-ip`, `ipv6`, `mac-address`, `other-home-dir`, `auth-header` and `long-token`. A finding of a kind the redactor removes would be published by the list itself, so it goes through `review accept`, which keeps only a hash. `check` warns while proposals wait for a person, and fails if a proposal holds a value, an approved entry's id does not match its kind and value, the rules would not find the value as that kind, or the value holds something the redactor removes.

Not everything can be a rule. **Read a log before you upload it.** `sync.py scan` previews what a push would publish for each session: the redaction markers by kind, and *warnings* about things no rule removes and a person should judge: public IP addresses, home directories of other users, authorization and cookie headers, long mixed-case tokens of unknown format. A four-part version number looks like an IP address, so one is skipped only when its surroundings say it is a version, such as `openjdk version`, `java.base@`, or an SDK listing row; `root@<ip>` still warns. `check` prints the same warnings for logs that are not yet uploaded, and `push` prints them for each log as it goes up. Output is masked, because it lands in the transcript of the session that runs it.

The agent itself is a common leak vector: while building or testing a redactor it tends to grep its own transcript, or to paste a real identifier into a test. Use made-up values in tests, and keep raw transcripts and `~/.claude.json` out of tool output.

## Local caches

Four files in `~/.local/state/llm-traces/` keep `commit`, `check`, `scan`, `review` and `stamp` from repeating work, and never change what they produce or report:

- **`transcript-cache.json`**: for each transcript, how many bytes of it were redacted into which stored log. Redaction works line by line, and a cut right after a newline byte divides the transcript, its decoded text and its lines at the same place, so the log of a longer transcript is the stored log's first part followed by the redaction of what was appended. That part is reused only if the transcript's first bytes still have the recorded SHA-256 and the stored log still holds the content its name says; an unfinished last line is redacted on its own each time.
- **`scan-cache.json`**: for each stored log, by the SHA-256 of what it holds (computed by `check` as it reads it, not taken from its name), what scanning it found: per kind, finding ids, masked values and counts. `check` scans a new snapshot only past the end of the longest earlier log of its session that is a prefix of it, and adds the counts. Reviewed false positives and the allow list are applied afterwards, as for a fresh scan, so deciding on a finding needs no rescan.
- **`check-cache.json`**: what `check` worked out from content besides scanning, each under the SHA-256 of exactly the content it came from. For a stored snapshot, keyed by the SHA-256 of its `.gz` bytes: the SHA-256 and length of what they decompress to, which decompression always gives the same way, so a snapshot read before is verified against its name without being decompressed again, and one whose bytes changed in any way is decompressed and hashed afresh. For a log, keyed by its content: the SHA-256 of its first n bytes for the lengths of earlier logs, for the prefix check. For a session's `metrics.json`, keyed by the content of its logs, its manifest, the file itself and `pricing.json`: whether the file is what they give.
- **`sync-cache.json`**: for each session, its state right after it was last synced: the size, modification time and inode of its transcript and subagent transcripts (taken before they were read, so any later write shows), the SHA-256 of its manifest, summary, metrics and note, the names of its stored logs, its status, and every change that the sync stamps or lists for it: those carrying its `LLM-Trace` line and the mutable ones authored within two minutes of its span (each with its description, emptiness, whether it is `@`, and its git SHA once immutable), read for all sessions in one `jj log`. A sync without session names skips a session whose state is the recorded one, since syncing it again would write the same files and descriptions; anything else, including a sync during a publish, which records git SHAs, means it is synced. `sync --all` syncs every session.

Every entry sits under a fingerprint of everything besides the content that decides its result: the source of `redaction_rules.py` and `redactor.py`, the Python version, and this machine's redaction literals (only their hash is stored). `redactor.py` holds the redactor, these caches and the helpers they use, and imports nothing from `sync.py` or `metrics.py` (a test keeps it so), so the rest of `sync.py` cannot change a redacted log, a scan or a verified snapshot, and an edit to it keeps those three caches. What depends on more adds a digest of the source of `sync.py` and `metrics.py`: `sync-cache.json`, whose fingerprint also covers the summary template, `pricing.json`, the reviewed findings, the allow list and the repo's remote URL; the key of each `metrics.json` entry in `check-cache.json`; and the end-of-turn hook's cursor. A different fingerprint empties the cache, so an edit to the rules or `redactor.py`, or a new literal, means one full pass. None of them holds a finding's value or any log content. `--full` on `sync`, `check`, `scan`, `review` or `stamp`, or `LLM_TRACES_FULL=1` for any command, trusts no cached result and records fresh ones: the full audit.

`scan`, `review` (with `review show`, `review accept` and `allow`) and `stamp` read the same caches. A transcript is redacted only from where the log `sync` last stored for it ends, by the transcript cache, which they read but never save, since the log they make is not stored; that log, each stored log not yet uploaded and each session file is then looked up in the scan cache by the SHA-256 of what it holds, and scanned only if it is not there, or only past an earlier log of the session that is a prefix of it. A stored log is named by its `.gz` bytes through the check cache, as in `check`. What they scan is added to the scan cache, and `check` later drops what it does not need. Reviewed and allowed findings are applied afterwards, so the results are those of reading everything, which `--full` does. Since the scan cache holds no values, a command that needs a finding's real value (`review show`, `review accept`, `allow propose` and `allow approve`) takes it from what this run scanned or from `finding-values.json`, checked against the finding's id, and reads everything again if one is not known there.
