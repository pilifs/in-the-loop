# Brief: a conductor for parallel streams

**Draft, 2026-11-14. Not to start until example-targets is merged and done**: it changes `run-streams.sh`,
`feature-loop.sh` and how streams talk, which the running loop uses. The decisions below are open for the user.

## Direction

Today a parallel run has two phases with nothing between them. The streams work blind to each other, and one merge loop
reconciles everything once the last of them stops. All the coordination work waits for the end, then lands on the merge
loop and on the user at once:
- interface requests between streams;
- disagreements only a merged tree shows;
- questions a stream can't settle itself;
- warnings and allow-list proposals.

A **conductor** is a fifth loop that runs beside the streams and does that work as it comes up:
- keeps a merged, tested revision of the streams current;
- routes what one stream needs from another;
- settles the decisions delegated to it and queues the rest for the user, with options and a recommendation;
- merges each stream as it finishes, so its Phase 5 work starts at once.

The final merge then becomes a formality, and the user is asked things while the answers can still change the work.

## Where it starts from

What the last four runs spent after their streams stopped, and what a conductor would have caught earlier:

| Run | What waited for the end | Cost |
|---|---|---|
| foundations (2026-11-07) | The integration check stopped at generated-file conflicts from 05:01; a real `serde(default)` bug surfaced only at the merge. | A defect found hours late. |
| cleanup (2026-11-07) | A for-review list of three user decisions (VF-018, VF-001, VF-020) and the new findings, reviewed in a separate session after the push. | A review session after the run. |
| application-core (2026-11-08) | Seven interface requests (Phase 5 step 1). Two allocation-bound decisions, asked only once the merge loop was blocked. Three streams stopped "working" after a clean stop and needed a restart. | Streams done ~11:57, Phase 5 done 22:15. |
| example-targets (2026-11-14, running) | Positive stopped `done` at 16:28 with a build-route question (answered by the user in another session). The integration check stopped at conflicts from 16:28, with two runtime×workflow disagreements found by a manual check at 17:13. Two streams' logs carry long-token findings, and 15 allow-list proposals await the user. | Ongoing. |

Already in place (`xyootzvm`):
- `sync.py regenerate` settles the generated trace files after any merge, and the integration check uses it.
- `check` reads only the history of `@`, so a stream's commits no longer show as errors elsewhere.

The conductor builds on both.

## Design

### 1. A rolling integration line

The conductor owns the `NAME-integration` workspace, which today only runs the check.
- **Each time a stream commits**, it merges the streams' `@-`, runs `regenerate`, and runs the brief's integration script.
- **A passing merge is committed** on the integration line, never pushed and never committed in the default workspace.
  The line always holds the newest merge known to work.
- **A failing merge is not committed.** The conductor reads the failure, works out which streams' changes disagree from
  the files and tracebacks, and writes to each stream's inbox (2): the failing test, the two sides, and a proposed rule.
  This is what was done by hand for runtime and workflow on 2026-11-14.
- **A real textual conflict** (source, not generated files) goes to the inboxes of both streams that touched the file.

### 2. Inboxes, not brief edits

A stream can't be told anything today except through the integration report. Editing its brief stops its loop, and its
Progress is its own.
- **Each stream gets an inbox** in the default workspace: `llm-dlc/loop-summaries/NAME-STREAM-inbox.md`, gitignored like
  the reports. `feature-loop.sh` adds one sentence to every cycle's instruction: read the inbox, and acknowledge each item
  by its id in the commit's Progress update.
- **What goes in an inbox:** integration failures, the other stream's interface decisions, the user's answers, and
  "you're unblocked".
- **Precedence**, stated in the instruction: the brief, then the user's decisions, then the conductor's messages. A message
  that contradicts the brief is to be reported, not obeyed.
- **Streams still talk to the conductor through their commits and Progress**, which it reads. An interface request is a
  Progress line as now, but it is answered the same day, not at the merge.

### 3. Decisions: delegated, or queued for the user

A stream that needs a decision today stops `blocked:` or `done` with a question, and nothing happens until a person
reads it. With a conductor:
- **Delegated decisions** are listed in the main brief under `## Delegated decisions`, by kind. Examples: how two
  streams' interfaces meet, which of two equivalent test fixes, naming and numbering, the order of independent items.
  - The conductor settles these, records each in the main brief's Progress as "decided by the conductor, reviewable",
    and posts it to the inboxes.
  - It never decides scope, downloads or network policy, security, verification bounds, acceptance criteria, or
    anything the brief's Decisions already settled. Those go to the user.
- **User decisions go into a queue**, `llm-dlc/loop-summaries/NAME-decisions.md`. Each entry carries its id, the
  question, the options with their consequences, the conductor's recommendation, and which streams wait on it. The
  status bar shows "N decisions waiting".
  - The user answers in any session ("decision 3: a"), which writes the answer into the queue file.
  - The conductor applies the answer. It records it in the main brief's Decisions, which is allowed because the merge
    loop hasn't started, then tells the inboxes and sets the stream back to running.
  - A stream that stopped `blocked:` on a decision is restarted by `run-streams.sh` once its inbox says it's
    unblocked. That needs a small change: a blocked stream is re-run when its inbox changes.
- **A stream is never left waiting for the end of the run** for a decision it asked for during the run.

### 4. Merge each stream as it finishes

When a stream is `done`, with no inbox items open and no jobs pending, the conductor:
1. records its last turns and copies its logs (today's reconcile steps 3 and 4, for one stream);
2. merges it into the default line with `regenerate`, and forgets its workspace.

Its Phase 5 items (for example, positive's P3 preparation after decision 1's extension) can then run in the conductor or
in a short loop of their own while the other streams continue. The final merge is just the last streams plus what the
integration line has already tested.

### 5. Upkeep the user does today

- Restart a stream that stopped `working` after a clean stop (the application-core bug), instead of counting it done.
- Collect `check` warnings and allow-list proposals into the decisions queue. The user still approves in their own
  terminal; the conductor never approves.
- Keep `findings.md` entries linked to the stream that owns them, and tell that stream when the verification loop
  closes or opens one (VF-024 was opened and closed today with no message to runtime).
- Tell the verification runner when the number of running loops changes, so it can move to a larger budget row in
  `pipeline.local.toml`.

### How it runs

The conductor is a `feature-loop.sh` loop in the default workspace (`NAME-conductor`), started by `run-streams.sh` in
place of today's `integrate()` bash loop.
- **It wakes on events, not on a fixed cycle.** `run-streams.sh` already watches for each of them and starts one
  conductor cycle when any happens: a stream's `@-` moves, a stream's status changes, the verification loop commits, the
  decisions file changes, or an hour passes.
- **It keeps one session for the run**, compacted as usual, so it remembers what it routed.
- **Its brief** is the main brief's `## Conductor` section, plus a short standing brief in `brief-template.md`.

## The plan

1. **Inboxes:** the file convention, the sentence in `feature-loop.sh`'s instruction, and the precedence rule. Tested on a
   two-stream fixture run.
2. **Rolling integration line:** `integrate()` replaced by commits on the integration line, with the failure triage
   written to inboxes. This keeps today's report file for the status bar.
3. **The conductor loop:** event-driven wake-ups in `run-streams.sh`, a `NAME-conductor` scope with a small cap, and
   `## Delegated decisions` and `## Conductor` in the brief template.
4. **The decisions queue:** the file format, the status bar count, re-running a stream blocked on a decision when its
   inbox unblocks it, and recording answers in Decisions.
5. **Merge on finish:** per-stream reconcile and early Phase 5.
6. **Measure it on the next parallel run**, against the table above:
   - the time from the last stream finishing to the brief being `done`;
   - integration checks that ran versus stopped;
   - questions answered during the run versus at the end;
   - decisions the conductor made that the user overturned.

Each step is one commit with its tests. Steps 1–2 are useful without the conductor session, as a cheaper intermediate.

## Decisions (open, for the user)

1. **Model and cost:** the conductor on Opus like the streams, or on Sonnet with an Opus cycle only for decisions?
   Proposed: Sonnet for routing and upkeep, Opus for a decision or a failure triage.
2. **What may be delegated:** the list in Design 3. Proposed as written. The user may widen or narrow it per brief.
3. **Notification:** how the user hears of a queued decision. Options: the status bar only, a push notification, or
   both. Proposed: both, for decisions that block a stream.
4. **Merge on finish:** merge each finished stream into the default line early (Design 4), or keep one final merge but
   from the integration line. Proposed: early, since it starts Phase 5 work sooner.
5. **Sync points** (not in the plan): streams could rebase onto the integration line between cycles, to see each
   other's interface changes. Rebasing a running stream's base risks the staleness in [jj workspace goes stale], and the
   inbox covers most of the need. Proposed: not now.

## Risks

- **Commits in the default workspace collide** with the verification loop's, which sweeps uncommitted files. The
  conductor commits each edit at once and keeps others' files out, as run-verification's step 6 does.
- **A wrong delegated decision** costs a rework. Each one is listed as reviewable, the delegated kinds are reversible by
  design, and the merge loop's for-review list includes them.
- **Inbox instructions that drift from the brief.** The precedence rule, and a stream reports a contradiction instead of
  following it.
- **Cost:** another session. Waking on events keeps it mostly idle, and today's coordination already costs a merge
  loop's hours plus the user's.

## Done when

The next parallel run uses the conductor:
- no integration check stops at generated files;
- every interface request is answered during the run;
- every user decision is asked while its stream runs;
- the time from the last stream finishing to the brief being `done` is at most an hour, apart from Phase 5's own jobs.

## Progress

- 2026-11-14, drafted after the user asked for a runtime orchestrator, from today's example-targets run and the last
  three runs' records.
- Status: draft: the user's decisions above, after example-targets is done
