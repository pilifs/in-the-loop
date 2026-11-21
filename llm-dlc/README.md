# LLM development lifecycle

This folder is the meta example: how this repo is built with an LLM, in the open.
Every change is published together with the LLM session that made it.
For each commit you can read the message, a summary of the session, and the full transcript.

The formal verification work itself is in [`examples/`](../examples/README.md). This folder is about how it was made.
It also holds what [`/prove-java-change`](runtime.md) runs on apart from the verifier: the two modes of a checkout,
the proof loop, and the release and contribution tools.

## Layout

```
llm-dlc/
  README.md                         this file: the procedure, and an index of sessions
  specification.md                  the specification: identifiers, invariants, storage, redaction
  runtime.md                        runtime mode: a released copy on a user's machine, where none of the tracing applies
  operating-notes.md                rules of practice learned in earlier runs, each with its reason; CLAUDE.md points
                                    at it, so every agent reads it, whichever client runs it
  research-router.md                where an agent looks on the web for outside evidence, by question and by task
  performance.md                    where sync.py's time goes, measured, and why it stays in Python for now
  index.json                        every session and the commits it made (generated)
  pricing.json                      list prices per model, written by hand, used for the metrics
  allowlist.json                    false positives by value: proposed by an agent, approved by a person
  reviewed-findings.json            false positives a person reviewed, by hash, which `check` no longer raises
  summary-template.md               the template for each summary.md
  traces-readme-template.md         the template for traces/README.md
  watch-summary-template.md         the summary the watcher of a /prove-java-change run prints at intervals, filled in
                                    by tools/watch.py
  prove-plan-template.md            the plan stage 2 of /prove-java-change fills in and stage 3 turns into examples
  prove-plan.schema.json            the same plan as data (plan.json), the handoff stage 3 and the proof loop read
  session-notes/<session-id>.md     optional hand-written note, shown at the top of that session's summary
  traces/README.md                  every session added up: tokens, tools, commits, logs (generated)
  traces/metrics.json               every session added up as data, for charts (generated)
  traces/loops.md                   every loop added up: time, tokens and cost by category, loop, run, cycle and item (generated)
  traces/loops.json                 the same as data, with every cycle and the verification jobs it submitted (generated)
  traces/<session-id>/
    summary.md                      what was asked, what was done, what was committed (generated)
    manifest.json                   detailed metadata: stats, models, tokens, commits, logs (generated)
    metrics.json                    every prompt, model call and tool call as tables, with costs and causes (generated)
    runs/<record>.md                each feature-loop.sh run the session worked in: its record, redacted (generated)
    logs/<sha256>.jsonl.gz          redacted transcript snapshots (gitignored, published on the CDN)
  tools/sync.py                     the hook and commands that capture, redact, publish and check traces;
                                    test_review.py, test_performance.py, test_runs.py and test_workspaces.py test it,
                                    `sync.py perf` times it
  tools/mode.py                     which mode a checkout is in, development or runtime; test_mode.py tests it and what
                                    sync.py does in a runtime one
  tools/doctor.py                   whether a machine can prove a change here: hardware, operating system and tools, what
                                    blocks and what only limits, and a budget for it; test_doctor.py tests it
  tools/claude_setup.py             what a user's Claude Code session has loaded besides the plugin, and the flags and
                                    launch of a clean one, which the loops use in a runtime checkout
                                    (runtime.md#what-claude-code-has-loaded); test_claude_setup.py tests it
  tools/changes.py                  the examples a checkout holds for /prove-java-change, each unprepared, prepared or
                                    decided from its own folder, and the ones still to prove, in order
                                    (runtime.md#many-changes-and-preparing-without-proving); test_changes.py tests it
  tools/watch.py                    the watcher's tool: /prove-java-change is one session that starts the run's other
                                    sessions, each on its model and effort, starts the verification loop and the proof
                                    loop, prints a summary at intervals (watch-summary-template.md) and acts between
                                    cycles and examples (runtime.md#the-watcher); test_watch.py tests it
  tools/prove-loop.sh               proves examples in a moonshot loop that continues the session which evaluated
                                    them: stage 4 of /prove-java-change (runtime.md#the-proof-loop); test_prove_loop.py
                                    runs it, and the loop under it, against a stand-in claude
  tools/conductor.py                how a moonshot loop and the session outside it talk: the loop's questions (a
                                    compaction with no commit, a cycle's end, a change of example) and the verdicts
                                    (runtime.md#the-conductor); test_conductor.py tests it
  tools/contribute.py               what of a runtime checkout's work can go upstream as a pull request, and a check of
                                    a prepared one (runtime.md#contributing-back); test_contribute.py tests it
  tools/release.py                  cuts a release for /prove-java-change: one commit, pinned by the digest of its tree
                                    (runtime.md#releases); test_release.py tests it and the bootstrap that installs one
  tools/redaction_rules.py          what counts as sensitive, and the stamp that says which files have been checked
  tools/redactor.py                 the redactor and the local caches of its results, keyed on it and the rules alone
  tools/measure.py                  where a command's time goes, for `sync.py perf`
  tools/profile_rules.py            a cold scan's cost rule by rule, the measurements behind performance.md
  tools/metrics.py                  turns logs into the metrics tables; test_metrics.py tests it
  tools/tool_time.py                where loops' time went: blocked time by what the agent ran, by loop and by cargo test
                                    binary, from the redacted logs (`--fetch` for published ones not stored here);
                                    test_tool_time.py tests it
  tools/loop_stats.py               adds up the loops from the metrics tables, the run records and the verification jobs;
                                    test_loop_stats.py tests it
  tools/streams_status.py           the state and status bar of run-streams.sh; test_streams_status.py tests it
  tools/unstale.py                  puts a jj workspace right after another session's operation met its own (stale, or a
                                    second copy of the working-copy change); test_unstale.py tests it
  tools/brief_run.py                the watcher's tools for a brief's run (/multi-agent-brief): preflight, the foundation
                                    stage, start, wait, status, merge (in an order, or early), trial merges, a
                                    stream's rerun, helpers; test_brief_run.py tests it and run-streams.sh's part
  tools/single_run.py               the watcher's tools for a single agent's run (/single-agent-run): start, wait,
                                    answer, the continue message, stop, land; test_single_run.py tests it and
                                    feature-loop.sh's `single-agent` loop
  tools/agent_client.py             the client boundary of a loop's turn: starts, resumes and compacts a Codex turn and
                                    prints the stream the loops read from Claude Code; test_agent_client.py tests it
                                    over codex_standin.py, a stand-in for the client
  tools/ask_codex.py                one question to a Codex thread and its answer, kept as a file, and a file
                                    mailbox for messages between sessions of either client
  tools/codex_rollout.py            Codex sessions for sync.py: finds a checkout's rollouts and reads one as a
                                    Claude Code transcript; test_codex.py tests it
  decisions/<name>.jsonl            a run's decision record: what its conductor decided (a parallel run's conductor, or the
                                    watcher of a proof loop, whose record is prove-change), with the confidence, how hard it
                                    is to undo and the user's review, and the questions queued for the user (schema.json)
  decisions/<name>.md               the review view of that record: flagged first, then open, then unreviewed (generated)
  tools/decisions.py                writes and reads the records: the conductor's `record` and `depend`, the user's `review` and
                                    `answer`, `list`, `show`, `counts`; `sync.py` renders the views and `check` validates the
                                    records; test_decisions.py tests it (loops/stream-conductor.md, Design 3 and 4)
  tools/inbox.py                    a stream's inbox from the conductor, loop-summaries/NAME-STREAM-inbox.md (gitignored):
                                    sends only what the stream acts on, records it in the decision's `applied`, and
                                    collects the stream's acknowledgements from its committed Progress; feature-loop.sh
                                    points every cycle at it; test_inbox.py tests it (loops/stream-conductor.md, Design 2)
  tools/integration.py              the rolling integration line run-streams.sh keeps while streams run: merges every stream's
                                    latest commit in NAME-integration, commits each merge that passes the brief's script, and
                                    triages one that fails into an open decision and inbox items; test_integration.py tests
                                    it (loops/stream-conductor.md, Design 1)
  loops/                            briefs for feature-loop.sh: markdown instructions a loop works through
  loops/brief-template.md           the skeleton of a brief and the standing rules every brief starts with, the timebox included
  tools/feature-loop.sh             runs a moonshot or a brief unattended: instruction, commit, compact, repeat, then a summary
  tools/verification-loop.sh        keeps the verification queue empty: a fresh Sonnet session per run of /run-verification
  tools/loop-common.sh              what the two loops share: log lines and the live display of a session
  tools/prune_workspaces.py         lists jj workspaces no longer used and whether deleting each loses nothing (commits merged, every
                                    file, gitignored ones included, in history or the default workspace), and prints the --delete
                                    command for a person to run in their own terminal; test_prune_workspaces.py tests it
  infra/
    cdn/                            the Cloudflare Worker that serves the logs
    langfuse/                       an optional local Langfuse, for browsing traces
```

## Set up

Once per clone, after the toolchain (`devtools`, from [`examples/setup/ubuntu`](../examples/setup/ubuntu/install.sh)):

```bash
python3 llm-dlc/tools/sync.py init        # jj config and aliases, and the pinned wrangler
llm-dlc/infra/langfuse/up.sh              # optional: Langfuse on http://localhost:3000
```

## How a commit points at its session

Each commit message ends with three lines that point at all of this:

```
LLM-Trace-Summary: https://github.com/<owner>/<repo>/blob/main/llm-dlc/traces/<session-id>/summary.md
LLM-Trace-Log: https://terminalvalue.net/raw-traces/<session-id>/<sha256>.jsonl.gz
LLM-Trace: <session-id> sha256:<sha256>
```

The first two are links for readers. The last is the identifier: the SHA-256 of the uncompressed log at the moment of the commit, so the log can be verified.
[`specification.md`](specification.md) has the full specification: identifiers, invariants, storage and redaction.

## Procedure for agents

Claude Code runs this procedure in this repo. `CLAUDE.md` points here, and the hooks and permissions in `.claude/settings.json` let it run without prompts. Other agents should follow the same steps.

It is the procedure of a development checkout. In a runtime one, a released copy on a user's machine, [`runtime.md`](runtime.md) replaces it: the same `sync.py commit` makes a plain commit with an `In-The-Loop-Runtime` trailer, and nothing below about traces, redaction or pushing applies. A commit that carries that trailer here was contributed from such a checkout: no session of this repository made it, and `sync.py` never stamps one on it.

**What happens without you.** The repo changes only when something is committed or pushed, so it stays clean between commits. At the end of every turn, a hook only sends finished turns to Langfuse. If a commit is made with plain `jj commit` or `git commit`, a hook traces it straight after, as `sync.py commit` would have. Never edit the generated files or the trailer lines by hand.

**What you do: commit each feature when it is done.**

1. **Scope.** A feature is the smallest change that a reviewer can understand on its own and that leaves the repo working: a demo, a tool, a setup component, a fix, a doc section.
   Commit as soon as one is finished and verified, so `@` never mixes two features. Don't ask before committing.
   A session can make several commits. A feature that spans sessions gets a trailer from each session.
2. **Check what is in `@`:** `jj status` and `jj diff --stat`.
3. **Commit:**
   ```bash
   python3 llm-dlc/tools/sync.py commit -m "Add the bytecode verifier demo" -m "What changed and why, and how it was verified."
   ```
   Each `-m` is one paragraph. The first is the summary line: imperative, at most 72 characters.
   The later paragraphs become the feature's entry under *Changes* in `summary.md`, so write them for a reader who did not see the conversation: what changed, why, and how you verified it.
   Add `Co-Authored-By:` as the last paragraph if your harness asks for it. The trace lines are added after it.
   The command writes the message, syncs the manifest and summary so they match it, and starts a new empty change. `jj trace-commit` is the same command.
4. **Verify:** the command then runs the check of `sync.py check` on what it committed, counting the notes instead of listing them, and must report 0 errors. An error fails the command but leaves the commit in place: fix it and commit the fix. A separate `python3 llm-dlc/tools/sync.py check` is needed only to list the notes, or after a commit made with plain `jj commit`, which the hook traces but does not check.

**Push only when the user asks.** Pushing publishes the log, and a person should read it first; see *Redaction* in [`specification.md`](specification.md#redaction).
```bash
python3 llm-dlc/tools/sync.py scan                   # preview: what was redacted, what a person should look at
python3 llm-dlc/tools/sync.py push --bookmark main   # record outstanding traces, check, upload, check, verify the revision, push
```
`push` refuses to upload a log in which the redaction rules would still change something, and prints a `warn` line for anything they leave to judgment.
Before pushing, this records everything no commit points at yet in one last *Record session traces* commit: conversation after a session's last commit, and sessions with no commit of their own. It moves the bookmark there and leaves `@` empty. It refuses to run while `@` holds uncommitted work.
The user can run the same thing as `/publish`, which commits finished work first.

A session's last words cannot be in the log that a push from inside it publishes, because they come after it. They go out with the next push from any session, or at once if the user exits and runs the command from a terminal.

**Don't:**
- edit a generated `summary.md` to correct or explain a session; add `llm-dlc/session-notes/<session-id>.md` instead
- run `git commit`, which bypasses the jj change IDs that the manifests key on
- run `jj describe` on a pushed commit, or remove `LLM-Trace` lines from any message
- put secrets in prompts, files or command output; they would end up in a published log
- print a raw transcript, `~/.claude.json`, or a real identifier while working on the redactor; test it with made-up values
- mark a finding as a false positive yourself. Propose it instead with `sync.py allow propose ID --reason "why"`, tell the user what it is, and they run `sync.py allow approve` in their own terminal. A finding of a kind the redactor removes (an `ERROR`) can't go on the allow list: they run `sync.py review accept` for it

## Unattended loops

[`tools/feature-loop.sh`](tools/feature-loop.sh) resumes one Claude Code session and repeats the instruction you name, compacting the session after each commit. The simplest are moonshots, one-line instructions run by name, the loops of the repo's first days: `features` adds features and examples to jvmcontract, `tla` adds advanced TLA examples, `spring` makes jvmcontract more useful to expert Spring Boot developers (new models, solvers, examples or other features, built into the library itself where it can be), and `relational` makes relational verification more efficient and accurate, adding examples where appropriate. A templated moonshot goes through a list instead, putting one item at a time into its template: `prove-examples` gives each of examples 285 to 300 in turn to "Formally prove example {} as elegantly and efficiently as possible". An item keeps the next cycle, with the same instruction, until a judge outside the session finds it finished: after each commit a separate `claude -p` call (`FEATURE_LOOP_JUDGE_MODEL`, Sonnet 5.5 by default), with no tools and no session of its own, reads the cycle's final report and commit messages and answers `ITEM: finished` (the goal is met, or what is left needs a person), `ITEM: continue` (the session can still make real progress on it) or `ITEM: waiting` (all that is left waits on verification jobs still out: the loop leaves the item, starts the next, and returns to the earliest waiting one whose jobs are in whenever it changes item; `FEATURE_LOOP_CONTINUE_WHILE_PROVING=0` keeps the item instead), and the run's record keeps its reason under the commit. Nothing is added to the moonshot's own session. `FEATURE_LOOP_ITEM_CYCLES` caps the cycles an item may take in a run (no cap by default), and `FEATURE_LOOP_ITEM_JUDGE=0` gives each item exactly one cycle, as before 2026-11-16. Its session is its own, fixed in the script, on Fable 5.2 at high effort: the first run creates it and later runs resume it. An item counts as done once an earlier run's record lists a commit for it, unless the judge's last word on it there was that it continues, so a run starts at the first item not done and ends when the list does; a cycle that makes no commit stops the loop and leaves its item for the next run. `engines` is a name for the brief [`loops/engine-priorities.md`](loops/engine-priorities.md), run with that brief's own settings, and `engines-jbmc` and `engines-native` for its two streams, `loops/engine-priorities-jbmc.md` and `-native.md`. `foundations` is likewise [`loops/foundations.md`](loops/foundations.md), with `foundations-heap`, `-summaries`, `-observations` and `-alignment` for its four streams. `cleanup` is [`loops/cleanup.md`](loops/cleanup.md), which works through the open entries of `verification/findings.md`, with `cleanup-native`, `-jbmc` and `-examples` for its three streams. `application-core` is [`loops/application-core.md`](loops/application-core.md), which widens native change verification to ordinary service code (objects with state, bounded Strings and lists, dependency outcomes, proof reuse), with `application-core-objects`, `-values`, `-environment` and `-reuse` for its four streams and [`loops/application-core-acceptance.md`](loops/application-core-acceptance.md) as their acceptance contract. In place of a name you can give a markdown brief, such as [`loops/sync-performance.md`](loops/sync-performance.md) (make `sync.py` fast): every cycle tells the session to read the brief again in full and take the next piece of work it calls for, so the brief outlives each compact; a brief that changes while the loop runs stops it, and briefs live in `loops/`. A number after the name sets how many cycles to run; without one it runs until stopped. Instead of a number, or after it, you can give instructions for when the work is done, and the session decides when to stop: after each commit, before the compact, it gets one more turn to weigh them against what the run has done and ends its reply with `LOOP: continue` or `LOOP: stop`. A stop ends the loop like running out of cycles, summary included; a reply with neither stops it as needing attention, and the reasons it gave are in the run's record. A number given as well is still an upper limit. It also stops when a cycle makes no commit, because that may mean a person is needed, and it leaves that session uncompacted so its context is there to read. To continue a stopped loop, run the same command again: a brief's Loop settings fix the session, its Progress section says what is done, and each cycle first finishes and commits a change an interrupted cycle left in the working copy. Files another session left uncommitted there (the verification loop's results, say) are kept out of the loop's commits, as `/run-verification` keeps a feature session's out of its own.

Each run keeps a record in `llm-dlc/loop-summaries/`: the instruction, a line for each commit as it lands, so it survives a restart, and how the run ended. The folder is gitignored, because a record holds local paths. `sync.py` publishes each record instead as a copy redacted by the transcripts' rules, at `llm-dlc/traces/<session-id>/runs/<record>.md` beside the session its header names, and lists the runs in that session's `summary.md` (start, end, cycles, how it ended). A record still being written is published as it stands and again as it grows, since a run that is killed never writes its end. `check` scans the copies as it scans an unpublished log. Only the default workspace publishes them: `run-streams.sh` copies a stream's records into it from the stream's workspace, at its start, after each of the stream's runs and before the merge (`llm-dlc/tools/run_records.py`, which replaces a copy only with the record it is a start of). When the cycles run out, the loop asks the session for one more turn that only reports: a summary of the run's commits, the verification jobs still pending or failed, and the `sync.py check` warnings to judge before pushing. That summary goes at the end of the record.

**Loop statistics.** [`traces/loops.md`](traces/loops.md) adds up every loop, and [`traces/loops.json`](traces/loops.json) holds the same rows as data: moonshots, briefs with their streams, and the verification loop, each by loop, run and cycle, with time, tokens, cost at list price, commits, and the verification jobs each cycle submitted with what they came to. A templated moonshot also gets a row per item: how many cycles took it, what they cost, its commit, and whether its proof passed. `sync.py` writes both on every commit from files in the repo (the sessions' `metrics.json`, the published run records, `verification/jobs/` and `verification/results/`), with [`tools/loop_stats.py`](tools/loop_stats.py), and `check` fails when either is out of date. A record tells which of its session's prompts were the run's, so a record's times are UTC, like a transcript's. The loops with no published record (every run before 2026-11-06: the first four moonshots, `sync-performance`, `build-orchestration` and `sound-verdicts`) are read from their sessions' prompts instead, and marked so. So is `examples-by-hand`, the loop a person ran by hand on 2026-10-31, the evening before the script existed: three typed instructions, each followed by a commit and a typed `/compact`. It is counted with the moonshots under a kind of its own, `moonshot by hand`, and the page says so where it appears. [`specification.md`](specification.md#metrics) defines the tables.

A brief can carry its own instructions for when to stop under a `## Loop until` heading, which the loop uses when the command line gives none; a brief with neither runs until the session decides it is done. The loop resumes the session that has always run it, with Fable at high effort. A brief can name its own session, model, effort and memory cap under a `## Loop settings` heading (`- session: ID`, `- model: ID`, `- effort: LEVEL`, `- memory: SIZE`), and `FEATURE_LOOP_SESSION`, `FEATURE_LOOP_MODEL`, `FEATURE_LOOP_EFFORT` and `FEATURE_LOOP_MEMORY_MAX` override both. `FEATURE_LOOP_SESSION=new` starts a fresh session that the run's cycles share, and a session id with no transcript yet, such as one opened in Claude Code but never sent a message, is created by the loop's first turn.

It runs in a systemd scope capped at 3.5 GB (a brief's `- memory:` or `FEATURE_LOOP_MEMORY_MAX` changes that), so a proof that exhausts memory is killed alone and the session sees it fail. The scope is named after the loop, `feature-loop-NAME.scope` (`feature-loop-engine-priorities-jbmc.scope` for the brief `engine-priorities-jbmc.md`), so different loops can run at once. A loop won't start if less memory than its cap is available, or if its own scope is still active.

Loops can run in parallel on separate branches, each in its own [jj workspace](https://jj-vcs.github.io/jj/latest/working-copy/#workspaces): `jj workspace add --name NAME -r @- ../REPO-NAME` makes a directory with its own working copy, on a branch of its own from the latest commit, sharing the repository. Claude Code files a session under the directory it ran in, so each workspace's sessions and traces stay apart. A brief that sets `- workspace: NAME` runs only from that workspace's copy of the script, `$(jj workspace root --name NAME)/llm-dlc/tools/feature-loop.sh`, so its commits can't land on another branch. A brief that sets `- fork: SESSION` starts its session, the first time, as a fork of that one: the streams of a brief all begin from the conversation that planned them, in a turn with tools and hooks off, so the parent's transcript, copied into the workspace for the fork and removed after, is never published there. [`tools/run-streams.sh`](tools/run-streams.sh) `NAME` runs a brief's whole loop unattended from the default workspace, in one terminal, each line prefixed with its loop (a person starts it through a watcher, [`/multi-agent-brief`](#a-briefs-run), which adds a foundation stage before it and answers what it asks). It compacts the planning session once and adds the workspaces. Run inside tmux, it turns the mouse on so the wheel scrolls back through the output over ssh (or Ctrl-b `[`), moves to a new window with a 200,000-line history if the pane keeps fewer, which stays open with the output after the run, and keeps a status bar at the bottom of the pane: the run's age and spend, the integration check's last result, and per loop its cycle, commits, spend, status and time since its last output (`tools/streams_status.py`, with its state in `llm-dlc/loop-summaries/run-streams-NAME/`). A brief whose Loop settings name `- integration: SCRIPT` also gets a rolling integration line while its streams run ([`tools/integration.py`](tools/integration.py)): in a workspace of its own, `NAME-integration`, it merges every stream's latest commit whenever one moves (at most hourly) and runs the script on it. A merge that passes is committed there, on a line of merges each known to work (`integration.py line BRIEF` names the newest), never pushed and never on the default workspace's line. One that fails is left uncommitted and triaged by the files in conflict or named in the output: a stream whose changes alone are named gets a `failure` item in its inbox; two or more get an open question in the decision record on how their changes meet, and a `queued` item each, and once a merge passes again the question is closed as settled and each side is told it may go on. The report goes to `llm-dlc/loop-summaries/NAME-integration.md`, which the streams read every cycle. Each brief's instruction also ends with one sentence (`tools/inbox.py instruction`) pointing it at its inbox, `llm-dlc/loop-summaries/BRIEF-inbox.md` in the default workspace, where a conductor puts only what that stream has to act on, each item with an id the stream acknowledges in its Progress; the brief comes first, then the user's decisions, then the conductor's messages ([stream-conductor.md](loops/stream-conductor.md), Design 2). The trace files every commit regenerates conflict as soon as two streams have committed; the check settles those with the merged tree's `sync.py regenerate` before it runs the script, so only a conflict in real work stops it; `foundations` is the first, `cleanup` (`tools/cleanup-integration.sh`) the second, and `application-core` (`tools/application-core-integration.sh`) the third. A brief whose Loop settings say `- verification: separate` runs without the pipeline: `run-streams.sh` starts no verification loop and waits for no job, and its loops submit jobs and go on, leaving the results for a person to review after the run; a session may still await a quick job, submitted at a higher priority, within its cycle for a bounded time (`foundations` does this). It starts `verification-loop.sh` for the loops' jobs and runs every stream's loop side by side. Then it runs the brief's own loop, which merges the streams in a fresh session (the brief tells it where the streams' commits, Progress, run records, traces and jobs are), and stops. Each brief ends its Progress with a status line (`- Status: working`, `waiting on jobs ID ...`, `done` or `blocked: ...`): a loop waiting on jobs is run again once their results are collected, and one done or blocked is finished, so a person is needed only at the end. To run a session's loops on another machine, [`tools/transfer-session.sh`](tools/transfer-session.sh) `HOST SESSION`, run here after closing the session, does everything before `run-streams.sh`: it checks this repo is on top of the remote main, publishes, copies the transcript into HOST's project directory for the repo, moves the local transcript aside so the session goes on in one place only (a push republishes every session it finds, and would roll back one that went on elsewhere), and brings HOST's repo to the pushed main, refusing if it has work of its own not on main. The verification runner also runs jobs committed in other workspaces (see `verification/README.md`). Merging the branches is a loop's work of its own: [Streams](loops/engine-priorities.md#streams) in the engine-priorities brief is the first worked example, with the steps that keep the traces whole (recording each stream's last turns, copying its logs, and `sync.py regenerate` after the merge, which rewrites the generated trace files from the session files and lists any conflict left). `check` reads the commits in the history of `@` only: a commit another workspace's line holds is checked there, by its own `commit`, and here once it is merged.

`prove-change` is the templated moonshot behind `/prove-java-change`: the same instruction as `prove-examples`, over whichever examples [`tools/prove-loop.sh`](tools/prove-loop.sh) gives it, continuing the session that evaluated them. The skill's session, the watcher, conducts it from outside ([`runtime.md`](runtime.md#the-watcher)): it, not the loop's own judge, says after each cycle whether the example is finished, continues, or waits on its proof, in which case the loop starts the next example and returns when the proof is in; it is asked before the loop changes example, which is where it merges a workspace the user queued or stops; and where another moonshot only logs a compaction with no commit (or stops there, with `FEATURE_LOOP_STOP_ON_COMPACT=1`), this one asks and stops on its word. From 2026-11-16 every moonshot over examples is run this way, `prove-examples`' list included: `/prove-java-change 288 289 ...` in this repository.

```bash
llm-dlc/tools/feature-loop.sh tla 5
llm-dlc/tools/feature-loop.sh prove-examples 4
llm-dlc/tools/feature-loop.sh spring 8 "Stop once the throws lines cover reactive handlers, or when the next idea would be minor."
llm-dlc/tools/feature-loop.sh llm-dlc/loops/sync-performance.md
```

While it runs, it reads commands typed in its terminal, followed by Enter. It prints them when it starts and a reminder at each cycle:

| Command | Effect |
| --- | --- |
| `+N`, `-N` | run N more or N fewer cycles after the current one (`+` and `-` alone mean 1) |
| `=N`, `N` | run exactly N more cycles after the current one |
| `0`, `stop` | end after the current cycle |
| `item` | a templated moonshot: end once the item under way is finished, however many cycles that takes (a count typed after it replaces it) |
| `add X Y` | a templated moonshot, from its conductor only (`watch.py add`): take items X and Y after the ones it has, as for an example a setup prepared in its own workspace while the loop ran |
| `inf` | no limit |
| `?`, `help` | where the loop stands, or the list of commands |

A cycle under way always finishes, commit and compact included. When the count reaches 0 the loop exits 0. A turn that did not end well is not a cycle, whatever the count: when the client reports an error (a quota, an interruption, a failure of its own) or leaves no result at all, the loop stops there with status 1 and says in its record that the session needs attention, before any compaction or summary; so does a compaction that fails, after the summary when the run was ending anyway. A turn that ends well and commits nothing is judged as before (a loop on a brief stops; a single agent's run asks its watcher). Ctrl-C stops it at once, with exit status 130. Started without a terminal, it runs the number of cycles it was given.

It commits locally and pushes nothing. It has no spending limit.

[`tools/verification-loop.sh`](tools/verification-loop.sh) does the same for the [verification queue](../verification/README.md). Whenever jobs are queued that this machine can run, or results wait to be collected, it starts a new Claude Code session on Sonnet 5.5 running [`/run-verification`](../.claude/skills/run-verification/SKILL.md), which runs, collects, triages, resubmits and commits until the queue is clear. Each run gets a fresh context, since the work is mechanical. When the queue is clear it starts again when a job appears: at once when the job is announced (`pipeline.py nudge`, which `sync.py commit` runs for a commit that queues one), and by checking every minute (`VERIFICATION_LOOP_POLL` sets the seconds) for one that was not. A job committed while a run is under way joins that run ([who learns of a new job, and when](../verification/README.md#for-the-agent-managing-the-pipeline)).

```bash
llm-dlc/tools/verification-loop.sh
```

A run that leaves work behind, such as jobs it resubmitted, is followed by another, up to 4 in a row (`VERIFICATION_LOOP_RUNS`). A run that leaves exactly what it found isn't repeated: the loop waits until the queue changes, since what is left needs a person. Jobs too big for this machine, and jobs another runner holds, don't start a run. While it runs it reads `stop` (end after the run under way, or at once while waiting), `now` (check the queue at once) and `?` (show the queue) from its terminal, and prints them when it starts. It runs alongside the feature loop, whose scope the skill leaves memory for. It commits locally and pushes nothing.

### A brief's run

A brief is run on command by a watcher, as a proof run is: `/multi-agent-brief NAME`
([`.claude/skills/multi-agent-brief`](../.claude/skills/multi-agent-brief/SKILL.md)) in a Claude Code session on Opus 5.5 in the
default workspace, or the same asked in words of a session that is already open there, which then becomes the
watcher. The run's state is all in files, so a watcher that was compacted, or a new session, takes over a run
under way (`brief_run.py status NAME` first). The watcher does none of the brief's work. It runs
[`tools/brief_run.py`](tools/brief_run.py), in four stages:

1. **Preflight** (`brief_run.py preflight NAME`): what would start (the brief's streams, each one's workspace,
   session and status) and what `run-streams.sh` would otherwise stop at once it had started: a stream without a
   brief or a workspace, two streams naming one workspace, a forgotten workspace's folder in the way, a brief
   without a status line, another run already under way. It also says what is left for the verification runner
   beside this many loops, and `brief_run.py budget NAME --apply` lowers the runner's settings file (the machine's,
   `~/.config/in-the-loop/pipeline.local.toml`, unless the checkout's own sets a budget) to
   it for the run (`--restore` afterwards): a runner budgeted for one loop beside four would take the machine
   past its memory.
2. **The foundation** (`brief_run.py foundation NAME`): one session on Fable 5.2 at high effort, given the brief
   and its streams' briefs with the instruction to start the work itself, build whatever foundation it sees fit
   for the most benefit, and update the brief for the agents that take over after it. It runs before any stream exists, so it may edit the briefs, and
   what it commits is what every stream begins with: the interface two streams would otherwise each invent, the
   fixture each would build, the tool each would wait for. It works in a workspace of its own,
   `NAME-foundation`, in a scope with a loop's memory cap, so no other session's uncommitted files meet its
   commits (on 2026-11-16 the result collector committed a watcher's unfinished merge that shared its working
   copy). `brief_run.py land NAME` then brings its commits to the default workspace's line: moved forward when
   that line has not moved, else by a merge whose generated trace files are regenerated. A merge that conflicts
   in real work is taken back and reported. Landing also puts the session's closing report into each stream's
   inbox, as an item of kind `foundation` that the stream acknowledges in its Progress, so what was built for
   it is known to have reached it.
3. **The run** (`brief_run.py start NAME`): `run-streams.sh`, detached, with the run's directory as its watcher.
   The watcher blocks in `brief_run.py wait NAME`, which returns only what needs it: a stream that is finished,
   to merge (below), a loop that ended blocked (below), an integration check that stopped passing, a decision
   open for the user, results that came back (below), a summary every 30 minutes, and the end of the run.
4. **The report**: each loop's status, and whether it is merged, against the brief's `Done when`, what was deferred or is blocked on the
   user, the watcher's decisions still to review, the cost, and what is left on the machine.

**Each stream is merged the moment it is finished, by the watcher; there is no merge loop.** `run-streams.sh`
puts a finished stream to the watcher (`conductor.py`'s `merge` question, half an hour at most,
`RUN_STREAMS_MERGE_WAIT`), and the watcher runs `brief_run.py merge NAME STREAM` while the other streams go on.
It merges the stream's `@-` into the default workspace's line as `land` does (moved forward or merged, the
generated trace files regenerated, the session logs it names taken from the workspace that stores them; a merge
that conflicts in real work is taken back), takes the stream's inbox acknowledgements, answers `merged`, and
records the merge in the brief's Progress, whose status it sets to `done` once every stream is merged and says
done (`blocked: stream S: ...` when one was left blocked), in one commit with the decision. The watcher then runs
`default_run.py after-merge`, which runs the default test run when one is due (below). A conflict it can see through it resolves by hand, as the watcher of a
proof run does between examples ([`runtime.md`](runtime.md)), and the same command then records it; anything else
it answers `leave` and reports. A stream left blocked is put to it as well: what it committed is usually worth
having. Without a watcher nothing is merged, and the end of the run names the command for each stream. Until
2026-11-17 the brief's own loop ran once every stream was finished, to merge them and finish the work; in the
first rehearsal (`/run-brief rehearsal`, 2026-11-17) it took the streams for empty because their notes were not in
its working copy's files, and a finished stream sat waiting for the slowest one. A brief's own work after its
streams is now a brief of its own, run after them; a brief that names no streams still runs as its own loop.

**The watcher keeps the verification queue itself, and is the one session committing in the default working copy
while the run is under way.** With a watcher, `run-streams.sh` starts no verification loop. At each look at the
queue, `brief_run.py wait` collects the results that are back and commits them with the paths a commit of results
holds and nothing else (`pipeline.py collect`, `sync.py commit --only $(pipeline.py commit-paths)`), starts the
runner (`pipeline.py run`, no model) when jobs wait and none is at work, and records the inbox items the streams'
committed Progress acknowledges. Its merges and its collections take turns, by a lock. It returns to the watcher
only what needs it: results that came back, with the ones to triage in `attention` (a job that did not pass,
outputs not applied), which the watcher triages as the run-verification skill says. Before, a verification loop's
Sonnet sessions collected and committed in the same working copy as the watcher's merges, with nothing to keep
the two apart. A verification loop already running when the run starts keeps the queue as it did, and `wait`
leaves the results to it. Merging itself holds `sync.py`'s lock across its jj steps, and trace output left
uncommitted in the working copy (sync.py writes it on every run, for any session) neither holds a merge back
nor comes along: it is dropped and written again by the next `sync.py` run. In the first rehearsal it was there
after the foundation landed, and a second merge would have waited for a commit no session was going to make.

**When the streams' lines conflict, they are merged in an order.** Merging each stream the moment it is finished
assumes the merges don't interact. `brief_run.py trial NAME` finds out early: it merges every pair of the streams'
lines, and each with the default line, beside every working copy (a merge commit made with `jj new --no-edit`,
read and abandoned), and lists the files each pair conflicts in beyond the generated ones and the test inventory.
When a pair conflicts in real work, the watcher tells both streams and proposes an order to the user, set with
`brief_run.py order NAME STREAM ...`: `merge` then refuses a stream while one before it in the order has commits
the line lacks, and the held-back stream's question names what to merge first. A stream ahead in the order that
is still at work is merged as far as it has committed (`merge NAME STREAM --early`: what its session has not
committed stays with it, no question is answered, and the brief's status is left alone), so a finished stream
does not wait for a running one. In the `domain-advances` run (2026-11-17) two streams conflicted in one file, an
order was set by hand, and the stream held back had its merge question answered `leave` for four hours.

**A stream whose loop died is run again inside the run.** `brief_run.py rerun NAME STREAM` leaves a request in the
run's directory (`rerun/STREAM`), and `run-streams.sh` starts the stream's loop again once its own process there
has ended, however it ended, with its counts at nought, and puts it to the watcher to merge when it is finished;
after the run has ended, the same command starts the run again for that stream. Before any loop starts,
`run-streams.sh` stops a scope (`feature-loop-BRIEF.scope`) that holds only what an ended loop left: when the
kernel kills a session for memory, the tests it ran live on there, `feature-loop.sh` refuses to start beside them,
and that refusal counted as the stream's second failure, which left it blocked for the rest of the run (VF-037).
A scope with a loop at work in it, one started by hand, is left alone.

**Helpers take work no stream owns.** The watcher does none of the brief's work, so work that turns up without an
owner (a tool whose stream has finished, a repair the run needs now) went undone or was improvised. A helper is a
Claude Code session the user has open in a tmux pane and names, at the start (`/multi-agent-brief --helper "tmux 3" NAME`)
or at any time after; the first is for low-hanging work, and the user may add others with a role of their own (a
specialist on a larger model for one wall). `brief_run.py helper NAME add HELPER --at "tmux 3"` records it (a pane
at a shell prompt is refused: what is typed there would be run). `helper NAME task HELPER --title T --file F`
writes a narrow brief with a stream's standing rules around the watcher's text, puts the helper's workspace,
`NAME-HELPER`, at the default line's one last commit (never from a merge in progress), and types one line into the
pane that names the brief. The helper commits there and ends with `helper NAME done TASK --report-file F`; `wait`
returns the task with its report and commits, the watcher merges it (`helper NAME merge TASK`) and tells the
streams it concerns with an inbox item of kind `delivered`. Material from a session outside the run (another
tool's review, a note) comes in the same way: as new files only, merged by the watcher, and acknowledged by the
stream it is for.

**The watcher commits the run's decision record, the user's answers included.** `decisions.py answer` writes into
the default working copy, where only the watcher commits during a run; `wait` commits the record whenever it has
changed, under a message that says it holds both. Before 2026-11-18 only a merge did, and a user's answer went
into a commit of verification results under that commit's message.

**A loop's session is given nothing of the run.** `feature-loop.sh` drops its own and the run's variables
(`RUN_STREAMS_*`, `FEATURE_LOOP_*`, `LOOP_WATCH_*`, `PROVE_LOOP_*`, `LOOP_CONDUCTOR`) before it starts `claude`:
with `RUN_STREAMS_WATCHER` in its shell, a stream's test of these scripts put its made-up merge questions to the
real watcher (2026-11-17). The preflight also refuses a watcher whose own environment carries a run's variables.

**A stream no longer waits for the end of the run for an answer.** Without a watcher, a stream that stops
`blocked:` is finished, as it stands. With one, `run-streams.sh` asks before it counts the
stream as finished (`conductor.py`'s `blocked` question, half an hour at most, `RUN_STREAMS_BLOCKED_WAIT`): the
watcher settles what it can by Design 3 of [stream-conductor.md](loops/stream-conductor.md), sends the stream
the inbox item that says so, and answers `rerun`, and the stream goes on. Its answer is a decision in
`llm-dlc/decisions/run-streams-NAME.jsonl`, reviewed like any other. This is the attended watcher of that
brief's Design 8; a watcher that decides while nobody is there is not built.

**A run is stopped at a boundary** with `brief_run.py stop NAME`: each loop is told to end after its cycle under
way (the command line `feature-loop.sh` takes from its conductor directory), a loop waiting on jobs stops
waiting, nothing is run again and no stream is put to the watcher to merge. `start` continues. `stop --now` interrupts instead.

**Where the time went.** `run-streams.sh` logs each change of a loop's phase with its time, and a summary says
per loop how long it worked, waited on jobs, was blocked, and, for a stream, sat finished while another stream
still ran (merged at once, a finished stream no longer waits for the others, so this is only the time to its
merge). The second is what going on to the next piece while jobs run would save.

**Two sessions in one working copy.** The watcher's merges and the result collector both commit in the default
workspace (and a brief without streams runs its own loop there). `sync.py commit --only PATH ...` commits the named files and folders alone and leaves everything else
uncommitted where it is: the collector commits with the paths `pipeline.py commit-paths` names (its results,
the findings, the examples table, the outputs it applied), and a loop's cycle is told to name its own. A
collector in a workspace of its own was considered and not built: every reader of results (a stream waiting on
its jobs, the watcher, the push gate) reads them on the default line, so its commits would have to be landed
there one by one, which brings the shared working copy back.

**While the foundation runs**, `wait` says at each interval how long it has run, its tool calls, the command under
way and its last commit; its spend is known when it ends, and is then in every summary's total. **A blocked loop
is run again twice at most** (`RUN_STREAMS_RERUNS`); the third time it is left blocked without a question, and put to the watcher to merge.
**A workspace jj calls stale** is put right with [`tools/unstale.py`](tools/unstale.py), which keeps the edits
that `jj workspace update-stale` alone would take off the disk. [`loops/rehearsal.md`](loops/rehearsal.md) is a
throwaway brief of two streams that exercises all of this with real sessions for little money: its second
stream stops blocked on purpose, for a word only the watcher can pass on.

**Any brief runs.** `run-streams.sh NAME` takes a brief of `llm-dlc/loops/` by name or file and reads its
streams from the brief's Loop settings (`- streams: a, b`); a brief that names none is run as its own loop
alone. The five briefs older than the setting keep the lists the script used to hold. A stream brief's
`- fork:` is optional: without one, each stream starts a session of its own. `run-streams.sh --plan NAME`
prints what it read and starts nothing.

**What else got faster** (2026-11-16, from the runs of 2026-11-08 to 2026-11-16): a stream waiting on jobs is
checked every minute, not every five (`RUN_STREAMS_POLL`); and a loop runs the tests of what it changed before a
commit, not the whole default run ([brief-template.md](loops/brief-template.md), CLAUDE.md's Tests).

### A single agent's run

For an outcome well within one agent's reach, a brief with streams is more than the work needs.
`/single-agent-run [OPTION ...] <the starting prompt>`
([`.claude/skills/single-agent-run`](../.claude/skills/single-agent-run/SKILL.md)) runs one agent toward it with
one watcher outside, as the first loops here ran one instruction over and over, with two differences: a watcher
judges after each cycle whether there is another, and a person can change what the later cycles are told while
the run is under way. The watcher is a Claude Code session on Opus 5.5 in the checkout, or one already open there that is
asked in words; it does none of the work and runs [`tools/single_run.py`](tools/single_run.py), whose state is all
in files (`llm-dlc/loop-summaries/single-NAME/`), so another session can take a run over.

- **Two texts.** The first cycle is given the starting prompt, and every later one the run's **continue message**
  as it stands when that cycle starts (`--continue "TEXT"`, else a default that asks for the next piece, a
  commit, and a plain word when the outcome is reached or the rest needs the user). Both reach the agent word for
  word. `--brief FILE` adds one sentence after the text of every cycle that names the file and asks for it to be
  read in full, since after a compact the session's memory of it is a summary.
- **A cycle is a context window.** The loop is `feature-loop.sh single-agent`: the text, the agent's turn, the
  watcher's verdict, a compact. The session is new (Fable 5.2 at high effort, under a loop's memory cap), or
  continues one (`--session`), or starts as a fork of one, such as the conversation that planned the work
  (`--fork`). Within a turn the session compacts itself at 600k tokens, and a compaction with no commit since the
  cycle began is put to the watcher, as in a proof run.
- **After each cycle the watcher decides** (`single_run.py wait NAME`, then `answer NAME continue|stop --reason
  ...`): it is given the agent's report, the cycle's commits, what was left uncommitted and the queue, and
  judges them against the outcome. A cycle with no commit does not stop the loop by rule, as it does every other
  loop: it is the watcher's to read (the outcome reached, a question, or stuck). The loop waits 15 minutes for
  the verdict (`--verdict-wait`). Without one a cycle that committed is followed by another, a cycle that did
  not ends the run before its compact, and three cycles in a row without one end it: nothing else measures such
  a run. Each verdict is a decision in `llm-dlc/decisions/single-NAME.jsonl`.
- **A person steers, and the watcher never does.** The continue message is written for a long run and reviewed
  by whoever gives it. A person changes it between two cycles from their own terminal
  (`single_run.py message NAME --file FILE`, refused from a Claude Code session as `sync.py allow approve` is); a
  cycle under way is not interrupted, and the next one takes it. The run's record notes each change, and
  `messages.jsonl` keeps every message with its time. The watcher has no way to set it, with an answer or on a
  restart, and is told not to draft one unasked: when a run should not go on as the message reads, it answers
  `stop` and says why. The loop ending is preferred to a watcher steering.
- **Where the agent works.** In the checkout, or with `--workspace NAME` in a jj workspace of its own, made from
  the line's last commit, when the checkout is busy; `single_run.py land NAME` then brings its commits in as
  `brief_run.py land` does. The watcher keeps the verification queue as a brief's watcher does (it collects and
  commits results and starts the runner), unless another run's watcher keeps it or the checkout is not the default
  workspace. A run whose agent only waits on jobs is stopped, `single_run.py jobs NAME` waits for the queue, and
  `start NAME` continues the same session. That leg keeps the leg before's count of cycles and its setting of
  the queue unless it is given its own (`--cycles N`, 0 for none; `--verification`), and `start` prints what it
  kept. A Codex run is checked before it starts, as a brief's Codex streams are: that Codex is given the
  checkout's `CLAUDE.md` whole in the agent's folder, and at a restart that the thread the run had can still be
  found (a new thread would know nothing of the run).
- **Stopping and continuing.** `stop NAME` ends the run after the cycle under way, `stop NAME --now` interrupts it,
  and `start NAME` on a run that has ended continues its session, the first cycle taking the continue message as
  it stands (or a new `--prompt` of the user's). `cycles NAME +N` changes the count, as typed in a loop's terminal.

The loop statistics count such a run as a moonshot named `single-NAME`, each text it sent a cycle.

### Claude Code or Codex

A loop's session can be carried by Codex instead of Claude Code, chosen when the run starts: `single_run.py start
NAME --client codex`, `brief_run.py start NAME --agent codex` (every stream) or `--agent claude --stream-agent
b=codex` (a mixed run), `brief_run.py foundation NAME --agent codex`, a brief's own `- client: codex` setting, or
`FEATURE_LOOP_CLIENT=codex` for a loop run by hand. Everything else is the same: the briefs, the instruction of a
cycle, the commit check, the decision, the conductor's questions, the verification queue, the record.

- **One boundary.** [`tools/agent_client.py`](tools/agent_client.py) is the only place that knows Codex. It starts
  a turn with `codex exec --json`, resumes with `codex exec resume THREAD`, and prints **the stream the loops
  already read from Claude Code** (`init`, `assistant` text and tool calls, `compact_boundary`, one closing
  `result`), so the progress display, the compaction watch, a cycle's report and the cost accounting have one
  reader. Claude Code's turns are started as they always were.
- **Models are resolved once, at launch.** A brief keeps its model's name. The operator's equivalences give what
  Codex runs for it: Fable 5.2 is Astra 6.2 (`gpt-6.2-astra`), Opus 5.5 is Sol 6.2 (`gpt-6.2-sol`); a Codex model
  named outright is taken as it is. A model with no equivalent (Sonnet 5.5, Fable 5.1) is refused before a turn
  is spent, by the preflight and by the loop, which is how an unmapped role shows up. The effort is always passed
  on: the machine's own Codex default may be another. The item judge of a templated moonshot and the standalone
  verification loop stay on Claude Code.
- **Session identity.** A loop names its session by a UUID; Codex names its thread itself. The binding is a file
  of the workspace the loop runs in (`llm-dlc/loop-summaries/agent-sessions/SESSION.json`), written whole when
  Codex reports the thread, and every later turn resumes that exact thread; a client that reports another ends
  the turn as an error. Each attempt keeps Codex's own events, its stderr and its last message beside it
  (`agent-sessions/attempts/SESSION/`), so a turn that died leaves what it said. A session keeps its client, and a
  Codex session cannot start as a fork of a Claude Code conversation: both clients start from the written
  handoff, the brief and its inbox.
- **Compaction is an operation, not a text.** Between cycles the loop compacts the session. `/compact` sent to
  Codex would only be text, so `agent_client.py compact` asks Codex's app server (`thread/compact/start`) and
  waits for the end. Codex's own automatic compaction keeps its own threshold (the model's default: the loop's
  `FEATURE_LOOP_AUTOCOMPACT` is a size for Claude Code's window and is not passed on). When Codex compacts by
  itself in the middle of a turn, `codex exec --json` prints nothing (probed 2026-11-19, CLI 0.170), but the
  thread's log gets a `compacted` line: `agent_client.py` reads the log as the turn goes and tells the loop of
  each one as Claude Code would (`compact_boundary`, with the size of the context it replaced), so a moonshot's
  compaction with no commit is put to its watcher under either client.
- **Permissions.** A Codex turn runs in the workspace-write sandbox with requests to leave it reviewed
  automatically (`sandbox_mode`, `approval_policy = "on-request"`, `approvals_reviewer = "auto_review"`: what
  `--approve-for-me` sets), the counterpart of the `--permission-mode auto` the loops give Claude Code: `sync.py
  commit` writes the repository's store, which is outside a sibling workspace. **Every turn is given them, a
  resumed one too**: `codex exec resume` does not keep a thread's sandbox, and a resumed turn without them is
  read-only with approvals off (the first live rehearsal's second cycle could not commit, and said so). With the
  approval policy alone and no reviewer a headless turn cannot ask, and added writable folders do not open the
  store (tried on CLI 0.169, 2026-11-18). What only a person may do stays refused by the tools themselves, for
  both clients: `sync.py allow approve`, `review accept` and `single_run.py message` check for a person at a
  terminal, and that check knows Codex's mark on the commands it runs as it knows Claude Code's. The network is
  open inside the sandbox (`sandbox_workspace_write.network_access`, the user's word of 2026-11-19), as it is for
  a Claude Code worker: without it a command in the sandbox resolves no host and every fetch waits on the
  automatic reviewer.
- **The allow list and the reviewed findings.** Claude Code is denied the two files by `.claude/settings.json`.
  Codex has no bar that works for them (probed 2026-11-19, CLI 0.170): a file marked `read` in a permission
  profile is patched all the same, once the automatic reviewer lets the request through, and one marked `deny`
  cannot be read by `sync.py` either. So the bar is in the tool, for every client: the commands a person runs
  (`allow approve`, `allow add`, `review accept`) leave a record of each decision on the machine, and `check`
  reports as an error a decision in either file that is neither in a published commit nor in that record
  ([specification](specification.md)). Such a decision waives nothing meanwhile (its finding stays raised),
  `brief_run.py land` and `single_run.py land` ask the same of a workspace's line before they merge it (`sync.py
  decisions --at REV`) and leave it where it is, and a push refuses while `check` has the error: a patch to
  either file is found at the next commit, takes no effect, and reaches neither the default line nor the remote.
  [`.codex/rules/`](../.codex/rules/llm-dlc.rules) says the same for a person's own Codex in a trusted checkout.
- **The same instructions.** Codex reads this repository's `CLAUDE.md` in place (`project_doc_fallback_filenames`,
  passed on the command line because a fresh sibling workspace is not a project Codex trusts, and in
  [`.codex/config.toml`](../.codex/config.toml)). The skills are the files under `.claude/skills/`, reached by
  Codex through relative links in `.agents/skills/`; a skill only the user may start (`publish`,
  `review-findings`) says so for Codex too (`agents/openai.yaml` beside it). `agent_client.py instructions
  --client codex` renders what the model would be given (no model is called) and checks it: `CLAUDE.md`'s first
  and last lines are there, nothing shadows it (`AGENTS.md`), it fits the byte budget, each skill is linked, and
  no user-only skill is offered to a work turn. It prints paths, digests and pass or fail. A brief's preflight
  runs it when a stream is Codex's.
- **Identity and cost.** A Codex started from a Claude Code session would inherit that session's identity and
  have its commits and jobs credited to the watcher: the boundary removes it and keeps who started the loop in
  the binding. A job is submitted under Codex's own thread. Codex reports a turn's tokens and no dollars, so a
  Codex turn's cost is **unknown**, shown as `$?` (or `$1.50+?` beside known dollars) with its tokens in the
  status bar and the summaries, never as nought. The statistics made from a session's log are priced once the
  model has a row in `pricing.json` (OpenAI's list prices for Sol and Astra since 2026-11-19, with the rates of a
  prompt over 272K tokens): what a subscription bills is not that figure.
- **Asking, not typing.** A session that wants a Codex thread's word (an expert's, say) does not type into
  another agent's terminal: a pasted text races the person using it, and the reply has to be read off a screen.
  [`tools/ask_codex.py`](tools/ask_codex.py) `ask --thread NAME --prompt-file FILE` runs one read-only turn of a
  thread of its own and returns the answer as data; the first question to a name says where the thread comes
  from (`--fork-of SESSION` forks an existing session, which is left as it was and never has two writers, or
  `--new`). A question leaves the machine, so it goes through the redaction rules first and a finding refuses
  it. Every exchange is a file (`llm-dlc/loop-summaries/exchanges/` in the default workspace), and so is a
  message the other way: `ask_codex.py mail send|list|read` is a mailbox any session can write to with a shell
  command, read at the receiver's next step. An answer or a message is **advice for the receiving session to
  judge**, never an instruction and never a person's approval. `ask_codex.py note` leaves a line in a session a
  person has open (`codex queue`) and waits for nothing.
- **Traces.** A Codex session is traced as a Claude Code session is: `sync.py` finds the rollouts of the Codex
  sessions that started in the checkout, stores each redacted (policy 5 removes the account identifiers and the
  account usage Codex records), and reads it through [`tools/codex_rollout.py`](tools/codex_rollout.py) as a
  transcript, so a commit a Codex worker makes with `sync.py commit` carries its own session's `LLM-Trace` line
  and `check` verifies it ([specification](specification.md)). A thread that was only asked a question is not a
  session of the checkout.
- **Statistics.** Codex traces a session under its own thread id, not the id the loop gave it, so a loop's record
  says which: `Codex thread THREAD carries session SESSION.`, written once the thread exists. The loop statistics
  (`loop_stats.py`), the published record and the time report (`tool_time.py`) find the run's session by that
  line. A Codex model call is timed from when the model was handed the turn (its items are written only when it
  ends), a command a tool call ran is the call that is timed and filed by what it ran, and a cost that leaves out
  calls of a model with no price is printed as `?` or `$1.50+?`, with a note naming the runs.
- **Hooks.** The two hook commands of `.claude/settings.json` (`sync.py hook` at a turn's end, `sync.py
  hook-commit` after a shell command) take Codex's payload as they take Claude Code's: `transcript_path` is
  the session's rollout. `.codex/hooks.json` names them for a session a person runs in a checkout Codex trusts,
  once that person has reviewed them there (`/hooks`): Codex loads a project's hooks only from a trusted
  project, and runs only hooks someone approved. A loop's worker runs in a fresh sibling workspace, which is
  neither, and the flag that would run them regardless (`--dangerously-bypass-hook-trust`) runs every other
  unreviewed hook as well. So `agent_client.py` runs the two commands itself after each turn it carried, with
  the same payload: `hook-commit` when the turn made a commit without `sync.py` (it traces the commit while it
  is still the working copy's parent; otherwise the next sync does), then `hook`. Neither does anything twice,
  and a failure is written beside the attempt (`*.hooks.log`) and stops nothing. `AGENT_CLIENT_HOOKS=off`
  turns this off.
- **Not yet.** Subagent threads of a Codex session; the proof stages of `/prove-java-change` and the
  standalone verification loop; runtime (released) checkouts.

## Sessions

Newest first. Each row links to the session summary. The [traces overview](traces/README.md) adds them all up, and [loop statistics](traces/loops.md) adds up the loops.

<!-- index:begin (generated by llm-dlc/tools/sync.py) -->
| Started | Session | Prompts | Commits | Status |
|---|---|---|---|---|
| 2026-11-20 22:33 UTC | [01a1fb18-0892-7712-a71d-f57061d8c4ad](traces/01a1fb18-0892-7712-a71d-f57061d8c4ad/summary.md) | 1 | 1 | open |
| 2026-11-20 21:31 UTC | [01a1fade-d8e6-7e30-94b9-6394676147ff](traces/01a1fade-d8e6-7e30-94b9-6394676147ff/summary.md) | 17 | 3 | ended |
| 2026-11-20 19:36 UTC | [01a1fa75-9b59-7523-a2b2-2fc5df1e4912](traces/01a1fa75-9b59-7523-a2b2-2fc5df1e4912/summary.md) | 10 | 5 | ended |
| 2026-11-20 17:53 UTC | [01a1fa17-f729-7003-8f47-6720087cd9c5](traces/01a1fa17-f729-7003-8f47-6720087cd9c5/summary.md) | 20 | 5 | ended |
| 2026-11-20 11:06 UTC | [01a1f8a2-8992-7030-a6ae-946623bc63f9](traces/01a1f8a2-8992-7030-a6ae-946623bc63f9/summary.md) | 0 | 0 | ended |
| 2026-11-20 11:04 UTC | [01a1f8a1-1bc5-75d2-8d27-ee1be35dfcd9](traces/01a1f8a1-1bc5-75d2-8d27-ee1be35dfcd9/summary.md) | 0 | 0 | ended |
| 2026-11-20 10:28 UTC | [01a1f87f-ffb2-7623-91a3-9482bf88a305](traces/01a1f87f-ffb2-7623-91a3-9482bf88a305/summary.md) | 9 | 3 | ended |
| 2026-11-20 09:03 UTC | [01a1f832-32f9-7b30-9476-acf6452b4af0](traces/01a1f832-32f9-7b30-9476-acf6452b4af0/summary.md) | 32 | 8 | ended |
| 2026-11-20 09:01 UTC | [01a1f830-d4fd-7131-b180-8a5b611363f6](traces/01a1f830-d4fd-7131-b180-8a5b611363f6/summary.md) | 0 | 0 | ended |
| 2026-11-20 08:56 UTC | [01a1f82b-a558-7482-b4af-a3a6dfa9ac0c](traces/01a1f82b-a558-7482-b4af-a3a6dfa9ac0c/summary.md) | 1 | 0 | ended |
| 2026-11-20 07:25 UTC | [01a1f7d8-b7b2-7551-93b4-142e06f59f16](traces/01a1f7d8-b7b2-7551-93b4-142e06f59f16/summary.md) | 35 | 7 | ended |
| 2026-11-20 07:24 UTC | [01a1f7d7-6eb1-7742-b379-36bfc2906bec](traces/01a1f7d7-6eb1-7742-b379-36bfc2906bec/summary.md) | 0 | 0 | ended |
| 2026-11-20 06:02 UTC | [01a1f78c-d6a4-7112-ab6e-41fa265d52d0](traces/01a1f78c-d6a4-7112-ab6e-41fa265d52d0/summary.md) | 30 | 8 | ended |
| 2026-11-20 06:01 UTC | [01a1f78b-c6a9-7be1-956d-9da9b51640a5](traces/01a1f78b-c6a9-7be1-956d-9da9b51640a5/summary.md) | 0 | 0 | ended |
| 2026-11-20 04:47 UTC | [01a1f747-9d56-73f1-8af1-082d4f2024c5](traces/01a1f747-9d56-73f1-8af1-082d4f2024c5/summary.md) | 34 | 9 | ended |
| 2026-11-20 04:46 UTC | [01a1f746-d708-7b30-a967-6cea2026945f](traces/01a1f746-d708-7b30-a967-6cea2026945f/summary.md) | 0 | 0 | ended |
| 2026-11-20 04:07 UTC | [01a1f723-3d97-7661-8f40-a29d17f25055](traces/01a1f723-3d97-7661-8f40-a29d17f25055/summary.md) | 17 | 6 | ended |
| 2026-11-20 02:23 UTC | [01a1f6c4-1031-7f00-b30d-c43ece9188a4](traces/01a1f6c4-1031-7f00-b30d-c43ece9188a4/summary.md) | 19 | 13 | ended |
| 2026-11-20 01:54 UTC | [01a1f6a9-c683-75d3-b798-35527ad2b8bf](traces/01a1f6a9-c683-75d3-b798-35527ad2b8bf/summary.md) | 0 | 0 | ended |
| 2026-11-20 01:53 UTC | [01a1f6a8-4655-7232-a3fc-00d65712c59d](traces/01a1f6a8-4655-7232-a3fc-00d65712c59d/summary.md) | 0 | 0 | ended |
| 2026-11-20 00:46 UTC | [01a1f66b-6af1-73e2-b0d6-96aadc5543bc](traces/01a1f66b-6af1-73e2-b0d6-96aadc5543bc/summary.md) | 21 | 11 | ended |
| 2026-11-20 00:45 UTC | [01a1f66a-0b6c-7510-a56c-c6baf75e9623](traces/01a1f66a-0b6c-7510-a56c-c6baf75e9623/summary.md) | 0 | 0 | ended |
| 2026-11-19 23:41 UTC | [01a1f62f-fbb3-7c71-b835-9a48011f7fc6](traces/01a1f62f-fbb3-7c71-b835-9a48011f7fc6/summary.md) | 17 | 14 | ended |
| 2026-11-19 23:40 UTC | [01a1f62e-f24f-7342-99e8-22a7a7fc5f13](traces/01a1f62e-f24f-7342-99e8-22a7a7fc5f13/summary.md) | 0 | 0 | ended |
| 2026-11-19 22:50 UTC | [01a1f601-137a-72b2-a3ab-0227452fd2f5](traces/01a1f601-137a-72b2-a3ab-0227452fd2f5/summary.md) | 16 | 10 | ended |
| 2026-11-19 21:41 UTC | [01a1f5be-43e3-71e0-ac11-7467f893af75](traces/01a1f5be-43e3-71e0-ac11-7467f893af75/summary.md) | 7 | 17 | ended |
| 2026-11-19 21:37 UTC | [01a1f5be-43bd-7532-a80c-5b4f5c304590](traces/01a1f5be-43bd-7532-a80c-5b4f5c304590/summary.md) | 13 | 122 | open |
| 2026-11-19 15:26 UTC | [01a1f467-8590-7ff3-bcdd-e52e5af7e3bc](traces/01a1f467-8590-7ff3-bcdd-e52e5af7e3bc/summary.md) | 7 | 18 | ended |
| 2026-11-19 15:23 UTC | [01a1f467-856b-7d02-9458-ab076e5fef2f](traces/01a1f467-856b-7d02-9458-ab076e5fef2f/summary.md) | 2 | 18 | ended |
| 2026-11-17 18:37 UTC | [Agent brief preservation work 287 308](traces/88045564-cdd1-4d6d-b8b6-9400a81a0b70/summary.md) | 7 | 35 | ended |
| 2026-11-17 12:56 UTC | [f28025bc-e46b-4a87-a943-bfb79dea5465](traces/f28025bc-e46b-4a87-a943-bfb79dea5465/summary.md) | 103 | 177 | open |
| 2026-11-17 12:56 UTC | [9896d870-fb47-4f3c-ba4d-5b1d3e64719c](traces/9896d870-fb47-4f3c-ba4d-5b1d3e64719c/summary.md) | 151 | 28 | open |
| 2026-11-17 12:56 UTC | [f8bc7b54-f877-4ee9-8e3a-b5ffbba621bc](traces/f8bc7b54-f877-4ee9-8e3a-b5ffbba621bc/summary.md) | 163 | 144 | open |
| 2026-11-17 12:56 UTC | [7ece8184-b148-4351-92d8-d634606b823e](traces/7ece8184-b148-4351-92d8-d634606b823e/summary.md) | 84 | 22 | open |
| 2026-11-17 12:37 UTC | [/run-brief invocation options](traces/e61d882b-5ef7-428e-90df-ffe709ac6962/summary.md) | 99 | 489 | ended |
| 2026-11-17 02:54 UTC | [a13e8c12-3309-4127-8c89-e4cfdae07ce6](traces/a13e8c12-3309-4127-8c89-e4cfdae07ce6/summary.md) | 12 | 1 | ended |
| 2026-11-17 02:26 UTC | [6da9b537-ecce-46cf-99fa-7cae16e7ce99](traces/6da9b537-ecce-46cf-99fa-7cae16e7ce99/summary.md) | 1 | 2 | ended |
| 2026-11-17 02:13 UTC | [Window 11 verification loop](traces/b74acbd8-95de-40d7-8793-79948e8c27ae/summary.md) | 11 | 14 | ended |
| 2026-11-17 02:00 UTC | [7a0043cd-fc61-48d4-bca1-fdef53364800](traces/7a0043cd-fc61-48d4-bca1-fdef53364800/summary.md) | 1 | 6 | ended |
| 2026-11-17 01:38 UTC | [217e3061-f107-4c8d-b779-3330a34ecabf](traces/217e3061-f107-4c8d-b779-3330a34ecabf/summary.md) | 1 | 10 | ended |
| 2026-11-17 00:23 UTC | [587c234b-0915-4213-816f-e502a741da0a](traces/587c234b-0915-4213-816f-e502a741da0a/summary.md) | 1 | 21 | ended |
| 2026-11-17 00:10 UTC | [5e11162e-5d2d-4d1e-8380-f13b91726445](traces/5e11162e-5d2d-4d1e-8380-f13b91726445/summary.md) | 1 | 2 | ended |
| 2026-11-16 23:33 UTC | [Test suite improvements from docs](traces/b23a1dcc-0128-4ba1-b4aa-85526c834e11/summary.md) | 8 | 44 | ended |
| 2026-11-16 23:20 UTC | [853b40ba-32fd-4638-8789-b2c3159d775a](traces/853b40ba-32fd-4638-8789-b2c3159d775a/summary.md) | 1 | 9 | ended |
| 2026-11-16 22:43 UTC | [55c066b9-518c-495d-8dfa-4ffaf85839d4](traces/55c066b9-518c-495d-8dfa-4ffaf85839d4/summary.md) | 1 | 5 | ended |
| 2026-11-16 20:48 UTC | [a6490df0-ff44-40c1-b34e-d0de7394edeb](traces/a6490df0-ff44-40c1-b34e-d0de7394edeb/summary.md) | 1 | 7 | ended |
| 2026-11-16 19:50 UTC | [4bd65c9c-5e21-441c-aef9-b9f46ff56d94](traces/4bd65c9c-5e21-441c-aef9-b9f46ff56d94/summary.md) | 1 | 3 | ended |
| 2026-11-16 19:42 UTC | [515f8415-55b4-4a47-8fbe-978fc5054ac2](traces/515f8415-55b4-4a47-8fbe-978fc5054ac2/summary.md) | 1 | 1 | ended |
| 2026-11-16 19:29 UTC | [722674dd-f1af-42c9-a55d-4febdb90b0f1](traces/722674dd-f1af-42c9-a55d-4febdb90b0f1/summary.md) | 1 | 2 | ended |
| 2026-11-16 17:51 UTC | [91a38d39-abe7-456b-bc6b-2e4d71420275](traces/91a38d39-abe7-456b-bc6b-2e4d71420275/summary.md) | 2 | 2 | ended |
| 2026-11-16 17:16 UTC | [77332e8d-0d4e-458f-ab21-4b5ba627dfb0](traces/77332e8d-0d4e-458f-ab21-4b5ba627dfb0/summary.md) | 2 | 2 | ended |
| 2026-11-16 16:09 UTC | [919d1317-7c09-476f-aee3-b72638b3aff0](traces/919d1317-7c09-476f-aee3-b72638b3aff0/summary.md) | 1 | 3 | ended |
| 2026-11-16 15:14 UTC | [0d14bf6f-8e0a-47cf-bce9-778897fc474e](traces/0d14bf6f-8e0a-47cf-bce9-778897fc474e/summary.md) | 3 | 2 | ended |
| 2026-11-16 05:44 UTC | [55c8cba6-01ea-400f-bee3-52e9db3aaba0](traces/55c8cba6-01ea-400f-bee3-52e9db3aaba0/summary.md) | 1 | 8 | ended |
| 2026-11-15 23:45 UTC | [5399f71b-f38b-4670-8fbe-9aa44d5cd46d](traces/5399f71b-f38b-4670-8fbe-9aa44d5cd46d/summary.md) | 3 | 3 | ended |
| 2026-11-15 19:24 UTC | [Prove-java-change skill and in-the-loop runtime](traces/3e8cabab-4a28-4a79-8207-69568d9e8162/summary.md) | 60 | 391 | open |
| 2026-11-15 17:34 UTC | [48807e20-0bdb-4031-8ced-d21d16fc3816](traces/48807e20-0bdb-4031-8ced-d21d16fc3816/summary.md) | 1 | 6 | ended |
| 2026-11-15 17:27 UTC | [Moonshot loop status](traces/6c5c7798-21e3-46a5-b989-5313736bdc7f/summary.md) | 608 | 680 | open |
| 2026-11-15 16:13 UTC | [a4ac2b6c-a5b9-4507-a21e-1b56ae8b2c31](traces/a4ac2b6c-a5b9-4507-a21e-1b56ae8b2c31/summary.md) | 41 | 90 | ended |
| 2026-11-15 14:52 UTC | [Moonshot loop stats backfill](traces/0c1ceb11-1913-4783-af0d-e3fa5724273b/summary.md) | 11 | 12 | ended |
| 2026-11-15 12:23 UTC | [72d38e75-aae0-402e-9b8a-881beec53824](traces/72d38e75-aae0-402e-9b8a-881beec53824/summary.md) | 61 | 21 | ended |
| 2026-11-15 05:45 UTC | [8f6a10f0-126a-4dc8-8126-3348577606af](traces/8f6a10f0-126a-4dc8-8126-3348577606af/summary.md) | 1 | 2 | ended |
| 2026-11-15 05:14 UTC | [d171101b-61c0-427e-9bfc-9ecd379dfd60](traces/d171101b-61c0-427e-9bfc-9ecd379dfd60/summary.md) | 1 | 2 | ended |
| 2026-11-15 02:06 UTC | [5341c50c-7a2a-449a-af31-94af17c66fbe](traces/5341c50c-7a2a-449a-af31-94af17c66fbe/summary.md) | 1 | 6 | ended |
| 2026-11-15 01:41 UTC | [bd59e87b-a013-4704-9c5c-cdab7fe9dd65](traces/bd59e87b-a013-4704-9c5c-cdab7fe9dd65/summary.md) | 1 | 2 | ended |
| 2026-11-15 01:31 UTC | [9afd524c-dd88-4be3-a7d1-e33e52803e1e](traces/9afd524c-dd88-4be3-a7d1-e33e52803e1e/summary.md) | 1 | 3 | ended |
| 2026-11-15 01:10 UTC | [28108fd0-2356-46e1-8340-483cce5ffcd0](traces/28108fd0-2356-46e1-8340-483cce5ffcd0/summary.md) | 1 | 2 | ended |
| 2026-11-15 00:46 UTC | [ba7515ba-1ca9-4219-94c1-906b2b927a57](traces/ba7515ba-1ca9-4219-94c1-906b2b927a57/summary.md) | 1 | 2 | ended |
| 2026-11-15 00:13 UTC | [ddfa720f-c19b-4983-be85-637c5ae723b2](traces/ddfa720f-c19b-4983-be85-637c5ae723b2/summary.md) | 1 | 4 | ended |
| 2026-11-14 23:38 UTC | [1d75f339-9e21-4d1a-b631-a40985de271f](traces/1d75f339-9e21-4d1a-b631-a40985de271f/summary.md) | 1 | 4 | ended |
| 2026-11-14 23:29 UTC | [577f63c1-0bd5-4fa4-9f0e-3c96500c2881](traces/577f63c1-0bd5-4fa4-9f0e-3c96500c2881/summary.md) | 1 | 2 | ended |
| 2026-11-14 22:40 UTC | [8eb322f2-65b0-48fa-be73-1357ad3bd4d7](traces/8eb322f2-65b0-48fa-be73-1357ad3bd4d7/summary.md) | 1 | 2 | ended |
| 2026-11-14 22:28 UTC | [778b368b-7c15-49d4-8a80-52a00eae477a](traces/778b368b-7c15-49d4-8a80-52a00eae477a/summary.md) | 2 | 2 | ended |
| 2026-11-14 21:13 UTC | [Recent sessions summary](traces/4a47a539-a6f1-4f2d-b4c9-828596296714/summary.md) | 16 | 4 | open |
| 2026-11-14 18:25 UTC | [051e402b-750c-4a9d-bdd2-24dfb39add84](traces/051e402b-750c-4a9d-bdd2-24dfb39add84/summary.md) | 222 | 82 | ended |
| 2026-11-14 18:07 UTC | [5e358522-4337-40e7-8791-2a6d6381d778](traces/5e358522-4337-40e7-8791-2a6d6381d778/summary.md) | 1 | 2 | ended |
| 2026-11-14 17:43 UTC | [133eee93-4f78-45c3-95c0-d6bf95c57555](traces/133eee93-4f78-45c3-95c0-d6bf95c57555/summary.md) | 1 | 2 | ended |
| 2026-11-14 17:31 UTC | [Feature loop run status](traces/65eb1a9c-093d-4394-b067-5a27e634424e/summary.md) | 14 | 82 | ended |
| 2026-11-14 17:08 UTC | [278c4037-4ac0-4122-ad69-f61e45f5acb6](traces/278c4037-4ac0-4122-ad69-f61e45f5acb6/summary.md) | 1 | 3 | ended |
| 2026-11-14 16:47 UTC | [c9b766bf-51e8-4b7e-b1f9-94e31b01568c](traces/c9b766bf-51e8-4b7e-b1f9-94e31b01568c/summary.md) | 1 | 3 | ended |
| 2026-11-14 16:30 UTC | [8b430aa4-bc67-4493-ac6d-36a360ce06cc](traces/8b430aa4-bc67-4493-ac6d-36a360ce06cc/summary.md) | 1 | 5 | ended |
| 2026-11-14 15:26 UTC | [Application-core feature streams exiting early](traces/3bb5a1f4-a4d5-4f4a-b511-6037ef3e1256/summary.md) | 58 | 13 | open |
| 2026-11-14 15:26 UTC | [Application-core feature streams exiting early](traces/eaff7dd7-6d26-4a35-811f-cb8e08f4ee79/summary.md) | 35 | 7 | ended |
| 2026-11-14 15:26 UTC | [Application-core feature streams exiting early](traces/70d4b729-3b1f-41d1-a89c-03fd78a71818/summary.md) | 30 | 6 | ended |
| 2026-11-14 15:26 UTC | [Application-core feature streams exiting early](traces/ddf78f27-05e0-438a-81be-8e7620b07bb7/summary.md) | 30 | 7 | ended |
| 2026-11-14 15:11 UTC | [Recent sessions summary](traces/d34058d5-39ed-426b-a9ff-d538463f39cc/summary.md) | 28 | 117 | ended |
| 2026-11-08 19:54 UTC | [50cf0225-8012-4dbb-beb4-05ddf8f97f8d](traces/50cf0225-8012-4dbb-beb4-05ddf8f97f8d/summary.md) | 1 | 7 | ended |
| 2026-11-08 19:00 UTC | [2d3839f7-ca39-4a27-8dc9-a77b4cd776f8](traces/2d3839f7-ca39-4a27-8dc9-a77b4cd776f8/summary.md) | 1 | 2 | ended |
| 2026-11-08 18:04 UTC | [5797b2b5-cc8e-4306-969d-6366320e1840](traces/5797b2b5-cc8e-4306-969d-6366320e1840/summary.md) | 1 | 2 | ended |
| 2026-11-08 14:15 UTC | [637cae8e-d166-477d-b0d2-51161e0c6d62](traces/637cae8e-d166-477d-b0d2-51161e0c6d62/summary.md) | 1 | 3 | ended |
| 2026-11-08 11:45 UTC | [62cecb04-4e17-4d66-b137-718cbe3a0eec](traces/62cecb04-4e17-4d66-b137-718cbe3a0eec/summary.md) | 1 | 2 | ended |
| 2026-11-08 11:26 UTC | [Application-core feature streams exiting early](traces/e9be5afb-09c9-4473-a9e9-38f2fb61ca80/summary.md) | 20 | 48 | ended |
| 2026-11-08 10:22 UTC | [6ca21bdf-4743-4500-90ea-7fe6280624b2](traces/6ca21bdf-4743-4500-90ea-7fe6280624b2/summary.md) | 144 | 59 | ended |
| 2026-11-08 09:39 UTC | [682fe237-e5f3-49f3-9994-944ecc1d3855](traces/682fe237-e5f3-49f3-9994-944ecc1d3855/summary.md) | 1 | 2 | ended |
| 2026-11-08 09:11 UTC | [912944aa-e446-4fd1-9f75-d064ada9f8d8](traces/912944aa-e446-4fd1-9f75-d064ada9f8d8/summary.md) | 1 | 2 | ended |
| 2026-11-08 08:23 UTC | [e0747cf5-ca8d-4647-a377-63e2a73ee3a9](traces/e0747cf5-ca8d-4647-a377-63e2a73ee3a9/summary.md) | 1 | 2 | ended |
| 2026-11-08 07:03 UTC | [9ef76667-69d8-4501-a1e3-a3001d1a7809](traces/9ef76667-69d8-4501-a1e3-a3001d1a7809/summary.md) | 6 | 7 | ended |
| 2026-11-08 06:35 UTC | [201f326a-a536-4002-a0f8-5ac6cc2bbfb7](traces/201f326a-a536-4002-a0f8-5ac6cc2bbfb7/summary.md) | 1 | 4 | ended |
| 2026-11-08 06:05 UTC | [e9fd9c4f-039e-41fc-9828-9d2f1e60b3ac](traces/e9fd9c4f-039e-41fc-9828-9d2f1e60b3ac/summary.md) | 1 | 2 | ended |
| 2026-11-08 05:08 UTC | [Verification loop status](traces/4e390f05-cc89-494e-98ab-c027ea3b76a3/summary.md) | 1 | 1 | ended |
| 2026-11-08 04:52 UTC | [34b4ec0b-987f-413f-b1d9-3ef5149ea8cc](traces/34b4ec0b-987f-413f-b1d9-3ef5149ea8cc/summary.md) | 1 | 3 | ended |
| 2026-11-08 04:34 UTC | [Multi agent feature stream run](traces/73918f92-0381-4271-b3bb-48ca4e45803b/summary.md) | 29 | 5 | ended |
| 2026-11-08 04:34 UTC | [Multi agent feature stream run](traces/aa238023-596d-49bd-8039-52502ec096fc/summary.md) | 61 | 13 | open |
| 2026-11-08 04:34 UTC | [Multi agent feature stream run](traces/b8c9cad1-a1e9-4dff-af3c-fd39c8035d6f/summary.md) | 87 | 15 | ended |
| 2026-11-08 04:34 UTC | [Multi agent feature stream run](traces/3ba3cc03-2dbc-4a1f-ac36-a1cc13b778a9/summary.md) | 63 | 14 | ended |
| 2026-11-08 02:47 UTC | [4c7f9b72-66a3-4ccc-8c6f-fa8e15716d38](traces/4c7f9b72-66a3-4ccc-8c6f-fa8e15716d38/summary.md) | 1 | 3 | ended |
| 2026-11-08 01:17 UTC | [65b61440-529c-4851-a79f-71ca197aa91d](traces/65b61440-529c-4851-a79f-71ca197aa91d/summary.md) | 1 | 2 | ended |
| 2026-11-07 23:23 UTC | [0a31eedb-0668-4cb5-8ee4-63d018293f2f](traces/0a31eedb-0668-4cb5-8ee4-63d018293f2f/summary.md) | 1 | 3 | ended |
| 2026-11-07 23:23 UTC | [807d6ed2-a98d-4f93-8dbb-28d70736eff7](traces/807d6ed2-a98d-4f93-8dbb-28d70736eff7/summary.md) | 30 | 11 | ended |
| 2026-11-07 21:51 UTC | [VM disk space and jj workspaces](traces/a76492ce-f5f9-4f7c-b595-2a44802e60bf/summary.md) | 1 | 4 | ended |
| 2026-11-07 21:50 UTC | [00316fc7-52d4-4009-9502-48e1d40764a8](traces/00316fc7-52d4-4009-9502-48e1d40764a8/summary.md) | 1 | 4 | ended |
| 2026-11-07 21:29 UTC | [2d24d762-29a6-4514-a681-485fd10f1c7e](traces/2d24d762-29a6-4514-a681-485fd10f1c7e/summary.md) | 30 | 28 | ended |
| 2026-11-07 18:55 UTC | [Multi agent feature stream run](traces/3da21514-fe46-49d5-8200-08d3cf89ea17/summary.md) | 26 | 35 | ended |
| 2026-11-07 16:31 UTC | [ed84ffdf-8f6d-4b88-815e-d0f713e92faf](traces/ed84ffdf-8f6d-4b88-815e-d0f713e92faf/summary.md) | 4 | 25 | ended |
| 2026-11-07 16:26 UTC | [367bd874-02ec-44ea-8935-70e651fad013](traces/367bd874-02ec-44ea-8935-70e651fad013/summary.md) | 1 | 2 | ended |
| 2026-11-07 16:26 UTC | [b65d132b-4eb4-46fd-8556-f4cba3311ad1](traces/b65d132b-4eb4-46fd-8556-f4cba3311ad1/summary.md) | 67 | 12 | ended |
| 2026-11-07 16:26 UTC | [a8cc612f-0606-4d4c-af9c-ef4ccb4bfee3](traces/a8cc612f-0606-4d4c-af9c-ef4ccb4bfee3/summary.md) | 21 | 7 | open |
| 2026-11-07 16:26 UTC | [2324d402-3f17-421a-8a85-5b6846d2c728](traces/2324d402-3f17-421a-8a85-5b6846d2c728/summary.md) | 43 | 7 | ended |
| 2026-11-07 12:21 UTC | [2df7775c-45a1-40a7-924b-75602d8ad256](traces/2df7775c-45a1-40a7-924b-75602d8ad256/summary.md) | 38 | 16 | ended |
| 2026-11-07 04:40 UTC | [Verification pipeline proof and model-checking queue](traces/3ef2aade-2b55-4d9e-9079-651a4ca9023c/summary.md) | 4 | 6 | ended |
| 2026-11-07 04:01 UTC | [Next multi-stream loop draft](traces/11f93b59-b830-4090-8775-33313957ef5c/summary.md) | 69 | 16 | ended |
| 2026-11-07 04:01 UTC | [Next multi-stream loop draft](traces/750c8a36-92b9-44e3-adad-ef96dc6aa676/summary.md) | 103 | 22 | open |
| 2026-11-07 04:01 UTC | [Next multi-stream loop draft](traces/be22079e-0c8d-41e4-ace3-12f7f213f1f9/summary.md) | 47 | 15 | ended |
| 2026-11-07 04:01 UTC | [Next multi-stream loop draft](traces/e65240e3-5cf7-41e9-b648-0b36ce9f1129/summary.md) | 41 | 7 | ended |
| 2026-11-07 03:34 UTC | [146ed363-87f6-40b1-a9b7-7accb8190171](traces/146ed363-87f6-40b1-a9b7-7accb8190171/summary.md) | 1 | 4 | ended |
| 2026-11-07 03:26 UTC | [b4548bf9-fa4c-41d3-8501-2dfcfc7ceadf](traces/b4548bf9-fa4c-41d3-8501-2dfcfc7ceadf/summary.md) | 1 | 4 | ended |
| 2026-11-07 02:50 UTC | [3a75b7cc-0877-41e5-8ae0-589e1f0a5306](traces/3a75b7cc-0877-41e5-8ae0-589e1f0a5306/summary.md) | 1 | 4 | ended |
| 2026-11-07 02:26 UTC | [761c7ea1-e32d-4b9b-81ef-1e3ada632637](traces/761c7ea1-e32d-4b9b-81ef-1e3ada632637/summary.md) | 1 | 2 | ended |
| 2026-11-07 01:08 UTC | [38c3ac74-61ce-4832-8fda-851eeac0a3da](traces/38c3ac74-61ce-4832-8fda-851eeac0a3da/summary.md) | 1 | 5 | ended |
| 2026-11-07 00:11 UTC | [c2bd9df4-5f20-4312-95a4-3eb88a60e0cd](traces/c2bd9df4-5f20-4312-95a4-3eb88a60e0cd/summary.md) | 46 | 21 | ended |
| 2026-11-07 00:02 UTC | [6c5734d4-89ff-437e-bc66-c0e159c45d5c](traces/6c5734d4-89ff-437e-bc66-c0e159c45d5c/summary.md) | 1 | 2 | ended |
| 2026-11-06 22:47 UTC | [6f7cf082-efef-4561-8de2-b54b3d27994f](traces/6f7cf082-efef-4561-8de2-b54b3d27994f/summary.md) | 6 | 6 | ended |
| 2026-11-06 20:48 UTC | [Next multi-stream loop draft](traces/ae994066-d1ea-4620-b03e-176a07061175/summary.md) | 16 | 45 | ended |
| 2026-11-06 20:11 UTC | [0c61a765-3997-4763-acd2-113589ff7995](traces/0c61a765-3997-4763-acd2-113589ff7995/summary.md) | 6 | 12 | ended |
| 2026-11-06 19:42 UTC | [VF-004 run_property_decider grep display](traces/2b3fe2be-7d32-44b6-8c87-3100b8426551/summary.md) | 2 | 5 | ended |
| 2026-11-06 19:41 UTC | [b4d45e13-aa3c-46a0-8634-1baa23ce7ebb](traces/b4d45e13-aa3c-46a0-8634-1baa23ce7ebb/summary.md) | 1 | 5 | ended |
| 2026-11-06 19:35 UTC | [62264445-84f6-45b2-bc09-d3dfb62b6b59](traces/62264445-84f6-45b2-bc09-d3dfb62b6b59/summary.md) | 1 | 2 | ended |
| 2026-11-06 19:21 UTC | [e47f34c2-3d13-4e34-97d7-da3f7efc33fe](traces/e47f34c2-3d13-4e34-97d7-da3f7efc33fe/summary.md) | 1 | 2 | ended |
| 2026-11-06 19:15 UTC | [Feature loop run review actions](traces/7b8a1d3b-6fbf-40ab-b647-1f9fc12bc573/summary.md) | 71 | 15 | open |
| 2026-11-06 19:15 UTC | [Feature loop run review actions](traces/63d80e44-36d9-4bcb-9e72-e31c6d9336ef/summary.md) | 71 | 12 | ended |
| 2026-11-06 19:07 UTC | [Agent session transfer warnings](traces/07d0ee30-0145-462d-80fc-8ef65f32f59a/summary.md) | 2 | 3 | ended |
| 2026-11-06 16:53 UTC | [Commit and publish to remote](traces/353e094e-5bc2-42ab-966c-b858752c38d6/summary.md) | 12 | 14 | ended |
| 2026-11-06 15:24 UTC | [setup-repo-on-ryzen-machine](traces/0e86a358-2515-46be-9b1e-0f9d02b4fb2f/summary.md) | 3 | 2 | open |
| 2026-11-06 10:48 UTC | [Feature loop run review actions](traces/3761db96-b870-47f7-aded-2ba264c165f4/summary.md) | 48 | 42 | ended |
| 2026-11-05 23:34 UTC | [Last feature loop results](traces/7cacdb56-4c74-4880-a06e-f98031283c0f/summary.md) | 127 | 30 | ended |
| 2026-11-05 10:47 UTC | [`build.py` orchestration feature loop](traces/cc65240f-1df0-42e0-81ce-41a80fa61028/summary.md) | 54 | 14 | ended |
| 2026-11-04 13:08 UTC | [build.py newProblems schema mismatch](traces/7605134a-8541-491b-9c22-2594d85b8a6e/summary.md) | 6 | 10 | ended |
| 2026-11-04 05:07 UTC | [FEATURE_LOOP_MEMORY_MAX memory limit](traces/6751f657-78ac-484c-8e36-eef607a6c325/summary.md) | 4 | 2 | ended |
| 2026-11-04 04:45 UTC | [Verification pipeline queue](traces/8fc64b88-3223-4fe7-a67d-3a75c5768bbf/summary.md) | 13 | 19 | ended |
| 2026-11-03 23:49 UTC | [Langfuse sync background script](traces/4f570b0b-cc13-4aa1-91b3-c89839f5286b/summary.md) | 5 | 3 | ended |
| 2026-11-03 14:52 UTC | [5dfbc1bc-4bd7-4b48-a637-44ff84065b6b](traces/5dfbc1bc-4bd7-4b48-a637-44ff84065b6b/summary.md) | 93 | 25 | ended |
| 2026-11-03 13:54 UTC | [Overnight Spring Boot feature loop commits](traces/20803daf-7ba0-4214-a79c-415a27f48a7b/summary.md) | 7 | 5 | ended |
| 2026-11-03 13:48 UTC | [sync.py redaction allow list](traces/0d3dce51-36ed-453d-bd2c-6adeaf97b230/summary.md) | 6 | 2 | ended |
| 2026-11-03 13:40 UTC | [Verification pipeline job queue](traces/bb39c22a-5d6e-48b2-af0a-45d8b973d822/summary.md) | 1 | 1 | ended |
| 2026-11-03 13:35 UTC | [Sync.py review findings](traces/52bfcdac-3587-46f2-b2cd-c49c2f7a5021/summary.md) | 6 | 1 | ended |
| 2026-11-03 04:08 UTC | [374d30d0-bacd-47e6-8f29-163603b6560f](traces/374d30d0-bacd-47e6-8f29-163603b6560f/summary.md) | 1 | 1 | ended |
| 2026-11-03 02:23 UTC | [a08d738e-5517-4e20-9807-72e419657081](traces/a08d738e-5517-4e20-9807-72e419657081/summary.md) | 13 | 7 | ended |
| 2026-11-02 00:14 UTC | [Real-world examples folder restructure](traces/dfa830a1-4fb4-4d80-8e2c-d612b759742d/summary.md) | 12 | 7 | ended |
| 2026-11-01 21:47 UTC | [JVM contract bytecode verification skill](traces/2e359813-25c2-4259-888b-42d3a5f0eee6/summary.md) | 12 | 16 | ended |
| 2026-11-01 14:42 UTC | [Feature-loop memory safeguards](traces/a308f9d3-8d8a-42ca-b074-d388818c2418/summary.md) | 45 | 52 | ended |
| 2026-11-01 11:13 UTC | [Feature loop cycle recovery](traces/8316bdd0-1ff3-47df-9d3d-67f2a2bdd1a6/summary.md) | 3 | 1 | ended |
| 2026-10-31 22:46 UTC | [Llm-dlc loop script](traces/b337c438-c453-4e77-9b04-ac89ec125c41/summary.md) | 7 | 3 | ended |
| 2026-10-31 16:29 UTC | [Rust Java formal verification library](traces/360e8b8b-8e0c-4b2a-bd69-25b32f2a54eb/summary.md) | 270 | 69 | ended |
| 2026-10-31 15:07 UTC | [Trace data pipeline for llm-dlc](traces/24d088fa-8a2f-419c-9283-2557487b7d9f/summary.md) | 6 | 7 | ended |
| 2026-10-31 14:07 UTC | [Sync script PII guards](traces/451eff2d-fef0-403d-bccc-98abb77fb2a9/summary.md) | 5 | 5 | ended |
| 2026-10-31 01:39 UTC | [LLM formal verification examples](traces/8194b9db-b315-48b6-b0eb-b6280f96252b/summary.md) | 21 | 11 | ended |
| 2026-10-31 00:53 UTC | [Formal verification example 004 proof](traces/57737931-7b2a-41eb-9b5c-ab2e3cef9b69/summary.md) | 6 | 3 | ended |
| 2026-10-24 14:07 UTC | [WSL Java formal verification setup](traces/560d5e98-2825-4bc2-90e2-39953d65d9c0/summary.md) | 50 | 14 | ended |
| ? | [fix-failing-python-test-suites](traces/4c87308e-7822-4b69-83db-a853166e57e3/summary.md) | 11 | 0 | ended |
| ? | [3048539b-c311-5e68-b776-b0f94623d4ac](traces/3048539b-c311-5e68-b776-b0f94623d4ac/summary.md) | 0 | 0 | ended |
<!-- index:end -->
