# Brief: make sync.py fast

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh):
`llm-dlc/tools/feature-loop.sh llm-dlc/loops/sync-performance.md`, in the session and with the
model set under [Loop settings](#loop-settings).
The loop runs until the session judges, by [Loop until](#loop-until), that the rest is not
worth another cycle.

**Session: `5dfbc1bc-4bd7-4b48-a637-44ff84065b6b`.** All work on this brief so far was done in
that session, and further work in this area resumes it (`claude --resume
5dfbc1bc-4bd7-4b48-a637-44ff84065b6b`, or the loop, which reads it from
[Loop settings](#loop-settings)) rather than starting a new one.

`sync.py commit` and `check` have become the slowest part of the development loop: a commit
took 35.5 s, the check after it 50.5 s, and a later combined commit and check 118.1 s. The
review below, an outside review of `sync.py` at `d60616a` (2026-11-02), found why and proposes
an order of work. Carry it out.

## How to work through it

- **One changeset per cycle**, in the order of [the plan](#the-plan), each committed on its
  own with what it saves. The first one adds the instrumentation; use it to measure every
  later change, before and after, and put the numbers in the commit message.
- **Check each claim against the code first.** The review read `d60616a`; `sync.py` has
  changed since, including an allow list for false positives. A finding that no longer holds
  is noted in the commit message, not fixed.
- **Nothing gets weaker.** Redaction, leak detection, the checks on published logs and the
  publication contract in [`specification.md`](../specification.md) keep every guarantee they
  give today. A cache that could let an unscanned or changed log through is a defect, not a
  speed-up. Keep a full, cache-free audit available (`sync --all`, `check --full` or similar).
- **Published bytes stay identical.** Log content, hashes and identifiers of existing
  snapshots must not change. Already stored snapshots are never rewritten.
- **Tests:** `llm-dlc/tools/test_review.py`, `test_metrics.py` and `test_performance.py`, plus new ones for each
  change. The redactor is tested with made-up values only (CLAUDE.md).
- **Process docs move with the behaviour.** If commit comes to validate what it needs so that
  a separate `check` is no longer needed after each feature, update CLAUDE.md,
  [`README.md`](../README.md#procedure-for-agents) and the specification in the same commit.
- **Don't push**, upload, or run anything that talks to R2 or Langfuse. Push paths are tested
  against stubs.
- **Defer what needs the user, explicitly.** Anything that needs new credentials or accounts
  (an R2 API token for an SDK client, for instance), a paid or external service, a change to
  what is published or how, or a decision only the user can make (a new storage format, a
  default that trades safety for speed) is not done and not guessed at. Do the parts that
  don't need it, behind a switch that is off where it must be, and end the commit message
  with a **Deferred for the user** paragraph: what is needed, why, and what it would unlock.
  Don't stop the loop over it while other work remains.
- **Go is out of scope**, and stays so by decision (see [Decisions](#decisions)): no port.

## Keep the loop running

The loop should run for as many cycles as there is useful work. A cycle stops it only by
ending without a commit, by a decision reply without a clear last line, or by an edit to this
brief outside [Progress](#progress). So:

- **End every cycle with a commit.** If the planned piece is blocked, commit the largest part
  that isn't: the measurements, the tests, the groundwork behind a switch that is off. Record
  the rest under **Deferred for the user**. Never end a cycle with only a question.
- **Don't pause for minor questions.** When the brief and CLAUDE.md leave a choice open, take
  the conservative option that keeps every guarantee, say in the commit message what you chose
  and why, and go on. Only what [Defer what needs the user](#how-to-work-through-it) lists is
  deferred, and deferring never stops the loop.
- **A denied command is information, not a stop.** Don't retry it unchanged. Work out what it
  would have done that it shouldn't (a network call, a write outside the repo), change the
  approach, and carry on.
- **No side effects that reach the network** from commit, sync or check: no Langfuse, no R2,
  no CDN, not even from a detached process. The Stop hook sends Langfuse its turns.
- **Rules edits keep their stamp** when they change no result: run
  `python3 llm-dlc/tools/sync.py stamp --equivalent`, which compares them with the stamped rules
  at `@-` on every transcript, log and published file. Use a plain `stamp` only for a change in
  what the rules find or redact. An open warning doesn't block either one. It becomes an
  allow-list proposal, which the user settles whenever they choose.
- **Findings in your own log are not a stop either.** Build made-up test values at run time
  (`"203.0." + "113.7"`) so the transcript holds none. If one gets in anyway, propose it with
  `sync.py allow propose ID --reason ...` and go on. A warning needs nothing from you.
- **Long runs go in the background.** A full check, a stamp or a benchmark can take minutes:
  run it in the background and wait for it, rather than letting a tool timeout end the turn.
- **Keep [Progress](#progress) current; leave the rest of the brief alone.** Update Progress
  in the commit that does the work: what changed, the numbers, what comes next.
  `feature-loop.sh` ignores edits to that section. An edit anywhere else stops the loop, so put
  corrections to the rest in the commit message instead.
- **In the decision turn,** end with exactly `LOOP: continue` or `LOOP: stop`, on its own last
  line. When in doubt, continue.

## Progress

Each run counts only its own commits, so work done in earlier runs is listed here. Numbers are
from the commit messages, measured on this machine (8 cores) against the same state before and
after. The full story of each step is in its commit message and in
[`performance.md`](../performance.md).

| Command | Before the brief | After step 3f |
|---|---|---|
| `commit` after a feature, its check included | 35–118 s | about 2–3 s |
| `check`, warm | 105–126 s | about 1 s |
| `check --full` (no caches) | 112 s | 18 s |
| `scan --full` (no caches) | 160 s | 11.6 s |
| Stop hook, one new turn on the 94 MB transcript | 41.8 s | 0.24 s |

- **First changeset: done**, commit `rxowqurq` (2026-11-03). It added instrumentation
  (`sync.py perf`, `~/.local/state/llm-traces/perf.jsonl`, `LLM_TRACES_PERF=1`), the
  email-regex fix (`email_spans`) and an exact hint for `env-secret`. It also made check
  decompress each snapshot once and check prefixes by digest, made snapshot sizes come from
  memory with gzip level 6, rebuilt the global outputs once per sync, wrote generated files
  only when they change, took Langfuse out of commit and sync entirely, and added
  `stamp --equivalent`. Measured, old against new on the same state: check 126 s to 107 s
  (5.46 GB to 2.47 GB decompressed), sync 78 s to 62 s, push's work 230 s to 212 s. Scanning,
  not decompression, is about 85% of check's CPU.
- **Second changeset: done** (2026-11-03), commits `zwzolxqo` to `xxspoytu`.
  - **2a** `zwzolxqo`: a transcript cache (incremental redaction) and a scan cache (results by
    content sha, ids and masks only) in `~/.local/state/llm-traces`. commit 62 s to 5 s, warm
    check 105 s to 15 s.
  - **2b** `qpqnrsym`: a check cache (snapshots verified once by their `.gz` bytes, prefix
    digests, metrics by inputs); every trailer's manifest read by one `git cat-file --batch`.
    Warm check 14.7 s to 0.9 s, identical output.
  - **2c** `sqkxtqkv`: a sync cache of each session's state, so commit syncs only sessions
    whose inputs or outputs changed; `CLAUDE_CODE_SESSION_ID` marks the running session as
    current. Warm commit 5.1 s to 0.7 s. One question deferred (see below).
  - **2d** `myxozvtm`: commit runs the check itself after `jj new` (an error fails the command,
    the commit stands); CLAUDE.md, the README, the specification and the run-verification skill
    no longer ask for a separate check. Warm commit with its check 2.2 s.
  - **2e** `qylspmov`: push's publication gate verifies the exact revision it publishes (trace
    files by blob id, a URL or withdrawal for every trailer it makes public) before
    `jj git push`. 0.2 s. (Its message says 63 files hashed; it was 66.)
  - **2f** `xysnulzx`: scan, review, stamp and allow read the caches, verifying every cached
    value by id; `--full` bypasses them. review 150 s to 0.9 s, scan 147 s to 0.9 s.
  - **2g** `xxspoytu`: the Stop hook keeps a cursor at the first turn not yet sent to
    Langfuse. One new turn 41.8 s to 0.24 s on the 94 MB transcript, byte-identical requests.
- **Third changeset: done** (2026-11-03), commits `pnstmxpx` to `pvuopzzv`.
  - **3a** `pnstmxpx`: push uploads up to 4 logs at once (1 wrangler put at a time by
    default; `LLM_TRACES_UPLOAD_JOBS`, `LLM_TRACES_PUT_JOBS`), reuses check's scans, and keeps
    a durable `uploads.json` record (attempted, verified). Temporary files are written
    atomically. Upload stage against stubs 45 s to 26.5 s, 10 s with 4 puts.
  - **3b** `onlpmumx`: one lock per repository serializes the writing commands, and a journal
    lets the next operation recover an interrupted one. 0.1 ms for the lock.
  - **3c** `rsnlowwp`: the code that decides results moved to `llm-dlc/tools/redactor.py`,
    so an edit to `sync.py` keeps the redaction, scan and snapshot caches. After a `sync.py`
    edit: sync 70 s to 6.2 s, check 105 s to 3.4 s.
  - **3d** `zumuuyqr`: the Go recommendation in [`performance.md`](../performance.md), with
    the profiling harness `llm-dlc/tools/profile_rules.py`: don't port, fix the cold scan in
    Python. Background preparation measured at 0.6 s at most: not done.
  - **3e** `urolzzuy`: cold scans and redaction run in one process per CPU
    (`LLM_TRACES_PROCESSES=1` for serial). check --full 112 s to 32.5 s, scan --full 160 s to
    32 s, sync --full 71 s to 17.9 s, identical output.
  - **3f** `pvuopzzv`: per-line gates in `redaction_rules.py` skip each rule on lines that
    cannot hold its match; `stamp --equivalent` runs in a pool. check --full 32.5 s to 18 s,
    scan --full 32 s to 11.6 s; the stamp kept its 2026-11-01 date (86,318 lines identical).
- **The run ended** after 3f: the cold paths are below the 30 s that `performance.md` set for
  looking further, and gains have flattened.

**Waiting on the user:**

- **Parallel wrangler puts or an R2 API token** (from 3a): the user will confirm. With
  either, raise `LLM_TRACES_PUT_JOBS` (or add an S3-compatible client); the upload stage goes
  from about 26 s to about 10 s.
- **Which session a commit treats as current** (from 2c): any session whose transcript
  changed in the last 10 minutes (`LIVE_SECONDS`) is treated as current, besides the one in
  `CLAUDE_CODE_SESSION_ID`, so its trailer is stamped on `@`. Narrowing that to the committing
  session changes which commits carry which sessions' traces, which is a change in what is
  published.

**What's left without the user:** small. The `env-secret` gate and rule (about 2.6 s and
2.3 s of CPU on the largest log) and `long-token` (about 1.5 s), all on paths that run only
after a rules edit.

## Decisions

- **No Go port** (user, 2026-11-03). `performance.md` measured that the cost was in the
  Python's algorithms, not the language, and the fixed Python is under the threshold. Revisit
  only if a profile shows a cost Python can't remove.
- **No chunked storage** (user, 2026-11-03). Logs stay full `.jsonl.gz` snapshots; the
  storage format and the download contract don't change. The idea is kept below, under
  [The architecture to move toward](#the-architecture-to-move-toward), only as the review's
  finding.

## What the evidence shows

From the checked-in manifests at the time of the review:

| Data represented in the manifests | Amount |
|---|---|
| Sessions | 12 |
| Retained snapshot entries | 119 |
| Session-to-commit references | 141 |
| Latest main-session logs, uncompressed | 111.7 MB |
| All retained snapshots, uncompressed | 1.264 GB |
| Largest latest session log | 59.0 MB |

The historical snapshots contain many overlapping prefixes. That is reasonable for immutable
trace references, but repeatedly processing all of them becomes expensive.

## 1. A normal commit does far more work than it needs to

`cmd_commit()` calls `cmd_sync([])`, and empty arguments mean "all transcripts", like
`--all`. Committing one feature synchronizes every session in the Claude project directory:
each passes through log loading and redaction, parsing, commit linkage, summaries, metrics,
artifact writes and possibly Langfuse export.

Ordinary commits should operate on an explicit session, or on the sessions whose inputs
changed. Different inputs affect different outputs:

| Changed input | Work that should become necessary |
|---|---|
| Transcript or subagent transcript | Update its redacted log, statistics, summary and metrics |
| Commit description or commit identity | Update affected commit metadata and summaries |
| Session note or summary template | Render affected summaries |
| Pricing | Recalculate affected cost metrics |
| Redaction rules or local redaction configuration | Invalidate affected redaction and validation results |
| Nothing relevant | Reuse previous results |

Recording the immutable Git SHA of an older change should not require redacting that
session's conversation again. Keep `sync --all` as the explicit rebuild. The common path
should scale with the work just completed.

`cmd_sync()` also treats every transcript modified within ten minutes as `current=live`. An
explicit session identity is more reliable as agent concurrency grows.

**Move global aggregation outside the session loop.** Every call to `process()` invokes
`write_index()`, which reads all manifests, updates the global index and README, and
regenerates the global metrics, so an all-session sync rebuilds the global outputs once per
session. Do it once at the end of the operation, and write generated files only when their
contents differ. (The rollup itself measured about 14 ms offline: a scaling fix, not the
cause of the minute-scale delays.)

## 2. Full checks repeatedly decompress the same history

The largest repeated-work issue. `cmd_check()`:

1. decompresses every available historical snapshot and hashes it;
2. applies the redaction-stamp shortcut *after* that decompression and hashing;
3. decompresses each session's current log again for metrics;
4. decompresses each commit's referenced log again for prefix comparisons;
5. reconstructs metrics and checks historical commit trees.

The prefix-check comprehension builds a set, but duplicate references still run `load_log()`
before the set removes them. With every snapshot present locally, one full check would
decompress about:

| Work within one full check | Uncompressed bytes |
|---|---|
| Initial historical-snapshot loop | 1.264 GB |
| Current-log reloads | 0.112 GB |
| Per-commit prefix reloads | 1.377 GB |
| Subagent reloads for metrics | 0.0015 GB |
| **Total** | **about 2.75 GB** |

Push runs the full check twice: about 5.5 GB of decompression before synchronization and
upload. (An estimate from the code and manifests, not a measured profile.)

What to do:

- **Process each unique snapshot once per operation.** Reuse its verified digest, actual
  length, scan result and any parsing needed downstream. Keep memory bounded: caching whole
  uncompressed archives is a different problem.
- **Don't reread old snapshots to check prefixes.** After validating an old snapshot, keep its
  digest and uncompressed length. Stream the current log once, copying the running SHA-256
  state at each old length, and compare those prefix digests with the validated ones.
- **Separate routine validation from a full audit.** Ordinary commit and check validate
  changed artifacts and their dependencies; a full audit recomputes everything without
  trusting cached results.
- **Reuse results across the two push barriers.** After uploading, still validate upload
  receipts, modified manifests, generated rollups and the final commit/tree relationship, but
  unchanged immutable logs need no second complete scan because their URLs were recorded.
  Make the checks precise about their dependencies; deleting the second check would lose
  protection against changes made during publication.

## 3. A reproducible regex hotspot

The email pattern starts with an unanchored, variable-length local part,
`[A-Za-z0-9._%+\-]+@`. On a long run of those characters with no valid address, the regex
retries from each starting position: quadratic. It runs in both redaction and leak detection.
32,000 `a` characters with no `@` took about 0.96 s for the email substitution; checking for
`@` first took microseconds and gave identical output.

- Immediate fix: `if "@" in text: text = EMAIL_RE.sub(...)`, and the same guard in leak
  detection.
- Fuller fix, since a long non-email run followed by an unrelated `@` still hits it: match only
  from the start of a maximal local-part run (with careful equivalence testing), or scan around
  `@` positions and validate bounded candidate components.
- **Don't truncate large strings or exempt them from scanning.** Those are the strings that
  may hold tool output and credentials.
- Editing the rules means re-stamping them. A pure speed-up keeps its date with
  `sync.py stamp --equivalent` (see [Keep the loop running](#keep-the-loop-running)).

## 4. Historical Git/jj queries are too granular

`cmd_check()` walks all traced commits and, for every trailer, runs up to three `jj file show`
commands to find the manifest under its current or historical path. `link_commits()` runs
several `jj log` queries per session and individual `jj describe` operations. Each costs a
subprocess plus repository work, and jj snapshots the working copy at the start of each
command (`--ignore-working-copy` avoids that, at the price of possibly stale reads, so use it
only for bounded historical reads with explicit snapshot points around operations that need
current files).

- Read commit descriptions and trailers once, into an operation-level index.
- Cache historical manifest validation by **Git commit SHA and session**, not jj change id:
  a change id survives rewrites, so it cannot show that a particular tree and description
  were checked.
- Refresh mutable state only after operations that rewrite it.
- Use a read-only jj invocation for historical lookups where appropriate.
- Consider `git cat-file --batch` for historical manifest blobs.

## 5. Snapshot creation has a redundant round trip

`store_log()` already holds the uncompressed bytes. It hashes and compresses them, then calls
`log_info()`, which rereads and decompresses the file for its byte and line counts. Take them
from the input: `len(data)`, `data.count(b"\n")`, `path.stat().st_size`. Keep integrity
verification as a deliberate check, not a side effect of measuring sizes.

**Choose the compression level explicitly.** `gzip.compress(data, mtime=0)` uses the
interpreter's default (9 up to Python 3.14, 6 in newer documentation). On one 3 MB synthetic
log, level 1 compressed about 5.5x faster than 9 for about 7% more bytes; benchmark 1, 3 and 6
on representative logs. Identifiers hash the uncompressed content, so a new level for new
snapshots keeps their identifiers; never rewrite a stored snapshot.

## 6. Uploads and telemetry need separate execution paths

**Uploads.** For a wanted log with no URL in its manifest, `upload_log()` downloads through
the CDN to see whether matching content exists, otherwise decompresses and scans the local
file, starts a Node/Wrangler process for that object, and downloads through the CDN again to
verify the uncompressed hash. The loop is serial. Use a reusable R2 client (S3-compatible API)
with bounded concurrency, starting at about four objects. Keep a durable upload record that
tells "never attempted", "may have succeeded" and "verified through the CDN" apart. **Keep the
post-upload content verification**: a HEAD or ETag is not evidence that the CDN serves bytes
whose uncompressed SHA-256 matches the trailer, which the storage contract requires.

**Langfuse.** (Done in the first changeset: commit and sync no longer contact Langfuse at all,
by the user's decision. What follows is the review's original finding.) `process()` calls
`export_langfuse()` synchronously, and each request can wait
up to 15 s, so an outage makes one commit wait repeatedly. Use a durable local telemetry queue
with background retries. The Stop hook also reads and redacts the whole transcript before
checking whether Langfuse is configured or anything remains to export: check configuration
first and keep a completed-turn cursor.

## The architecture to move toward

An incremental preparation pipeline with one coordinator for repository changes.

- **Local preparation can happen while the agent works.** It processes complete appended
  records, keeps an unfinished trailing line, and detects a replaced or truncated source. The
  redactor is deterministic and line-local, which supports this. At commit time, freeze an
  exact input boundary and finalize the artifacts; at push time, publish the exact validated
  objects and verify the revision being pushed. Uploads still happen only as part of a push
  the user asked for.
- **Cache the complete inputs to each result.** `Rules._seen` already caches per-line scans.
  A validation cache across phases and commands must key on the exact content digest, the
  scanner/redactor version, the effective local redaction configuration (machine-specific
  literals and configuration outside `redaction_rules.py`; keep those fingerprints local), the
  reviewed-finding and allow-list decisions, and the generator, template and pricing versions.
- **Cache the actual result and its severity**, not a boolean: the checker reports some prefix
  and trailer/tree discrepancies as notes, for legacy behaviour and policy changes. Newly
  generated commits get the stronger consistency guarantees.
- **Serialize repository mutations.** Don't parallelize `process()` as it stands: it mutates
  shared jj state and related files, uses fixed temporary file names, cleans up snapshots, and
  the commit hook temporarily switches the working revision. One coordinator for jj mutations,
  manifest finalization, global outputs and garbage collection; parallelize only independent
  immutable preparation and uploads. Unique temporary files, atomic replacement and a small
  durable journal make interrupted operations recoverable. A repository lock and an operation
  context are enough at first; SQLite and a persistent worker when durable queues are needed.
- **Full snapshots remain a long-term limit** (not pursued, by decision: see
  [Decisions](#decisions)). Each commit still creates and uploads a complete `.jsonl.gz`. Immutable chunks plus a snapshot manifest of their ordered identities and a
  full-stream digest would let old chunks be reused, but that changes the storage format and
  download contract: a later migration, preserving every historically referenced object.

## On Go

Decided (see [Decisions](#decisions)): no port. The review's reasoning follows.

Optimize the Python first and let the profile decide how much to port. A direct translation
keeps the historical scans, subprocess counts and serial network work. An incremental Go
coordinator suits streaming, concurrent workers and cancellation, but needs a careful
migration. Two traps if it comes to that: the rules use lookahead and lookbehind, which Go's
`regexp` lacks (it does guarantee linear time; word-boundary and character-class behaviour
differ too), and Go's `encoding/json` sorts keys and escapes HTML characters, while the logs
rely on Python's insertion order and compact `ensure_ascii=False` output. Equivalent JSON is
not equivalent trace content: hashes and prefixes would change. Preserve the serialization
exactly, or version the format and keep old referenced blobs, with differential tests over
Unicode, escaping, nested JSON strings, malformed records, key order and redaction decisions.

## The plan

**First: immediate improvements and instrumentation.**

- Fix the email-regex hotspot.
- Compute snapshot sizes from the bytes in memory.
- Rebuild global outputs once per operation.
- Write generated files only when they change.
- Deduplicate snapshot loads and reuse validation context within a command.
- Take synchronous Langfuse requests out of commit.
- Record per-phase wall time, CPU time, bytes processed, cache hits, subprocess counts and
  network requests.

Measure an unchanged run, a small new feature in a long session, and a push with outstanding
objects (against stubs), to tell CPU work from repository and network latency.

**Second: make routine commit and check incremental.**

- Explicit session identity and dependency-aware invalidation.
- Cached historical checks keyed by immutable content and actual Git commit identity.
- Shared or batched historical object reads.
- Incremental prefix validation.
- A separate full-audit mode.
- A final publication gate that validates the exact resulting revision.
- Commit performs the incremental validation it needs, so agents no longer run a full-history
  `check` after every feature; the documented procedure changes with it.

**Third: persistent preparation and publication workers.** A durable local state store,
background incremental preparation, concurrent SDK uploads and a single repository
coordinator; then a measured recommendation on Go.

## Done when

Finishing one small feature does work proportional to that feature's new trace data and the
metadata it affects, with little dependence on how many earlier sessions exist, and the
numbers in the commit messages show it.

## Loop settings

The session is fixed: further work on this brief resumes it.

- session: 5dfbc1bc-4bd7-4b48-a637-44ff84065b6b
- model: claude-opus-5-5

## Loop until

Go on while a cycle can still realize a substantial part of the reasonably attainable value
of this brief. The user prefers the loop to run as long as possible, so when in doubt, continue. Stop when most of it has been realized: the remaining items are small or
speculative next to what is done, measured gains have flattened, or what is left needs the
user's input (credentials, accounts, external services, decisions) and has been recorded as
deferred. Don't go on to polish, and don't stop while a clear, measurable improvement that
needs nothing from the user is still open.
