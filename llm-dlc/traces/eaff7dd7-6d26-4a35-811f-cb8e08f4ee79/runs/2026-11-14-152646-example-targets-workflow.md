# Feature loop: example-targets-workflow

Started 2026-11-14 15:26:46 UTC, no limit on cycles, session eaff7dd7-6d26-4a35-811f-cb8e08f4ee79, claude-opus-5-5 at high effort, after change qpvlyptuzssruqtxruvqznvkntkoknup.

> Work on the brief in `llm-dlc/loops/example-targets-workflow.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'qpvlyptuzssruqtxruvqznvkntkoknup..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next, and if it ends with a `- Status:` line, keep that line current there too: `working` while a piece of work that needs only you is left, otherwise the status the brief's `## Loop until` gives for stopping (`waiting on jobs ID ...` with the job ids, `done`, or `blocked: ...` with what needs the user or another stream). If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `llm-dlc/loops/example-targets-workflow.md` at sha256 c180ffc7a70a10b6389eb5a816a8feb97eeb7b61be6e2f75471a5a4413bb8c0e.

After each commit the session decides whether to go on:

> Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with `waiting on jobs ID ...`. Stop with `done` when W1–W4 and your acceptance pass, or each is deferred by the timebox with the finding. Stop with `blocked: ...` when what is left needs the user or another stream, and is recorded under Progress. No scheduler replacement, result-format migration or engine work. Anything new you find goes under Progress, for the main brief's for-review list.

## Commits

Session eaff7dd7-6d26-4a35-811f-cb8e08f4ee79 was forked from session e9be5afb-09c9-4473-a9e9-38f2fb61ca80.

- cycle 1, 2026-11-14 15:35:12, `wqsyopqlqlno`: example-targets W1: pure task planning from the sidecar and a frozen claim file
  - decided to continue: The loop should go on. This run has one commit so far, the W1 planning step. Several steps that need only my own work are still open: W1's mutant revisions and readiness milestones, receipt ingestion (W2), handoffs and the gap inventory (W3), and discovery and scheduling (W4). None of them waits on a job, the user or another stream, because they can all be built and tested on the fixtures.
- cycle 2, 2026-11-14 15:42:29, `nrpqnlolqstu`: example-targets workflow: record the check errors that are other streams' commits
  - decided to continue: The loop should go on. This run has committed two W1 steps, task planning and constructed mutant revisions, plus a note recording the check errors that come from the other streams' commits. W1's readiness milestones, W2's receipt ingestion, W3's handoffs and gap inventory, and W4's discovery projection are all still open. Each can be built and tested on the fixtures with my own work alone, without waiting on a job, the user or another stream.
- cycle 3, 2026-11-14 15:54:02, `onssronowxlk`: example-targets W1: readiness milestones per task, and the summaries derived from them
  - decided to continue: The loop should go on. This run has committed W1's task planning, constructed mutants and readiness milestones, plus a note on the other streams' check errors, so W1 is done. W2's receipt ingestion, W3's handoffs and gap inventory, and W4's discovery projection are still open, and each can be built and tested on the fixtures with my own work alone. The one open schema question, fixture revisions in `claim.target.revisions`, is part of the W2 step: I either find an honest identity that fits or record an interface request, and neither needs a job or the user.
- cycle 4, 2026-11-14 16:11:15, `monsvovyynrm`: example-targets W2: attempt ingestion, one format-2 receipt per task and attempt bound to the prepared artifacts
  - decided to continue: The loop should go on. This run has committed W1 (planning, mutants, readiness) and now W2 (ingestion, with A6 passing), but W3 (the handoff packet and gap inventory, which A1's handoff row and A7 wait on) and W4 (the discovery projection) are still stubs. Both can be built and tested on the fixtures with my own work alone, and nothing left waits on a job, the user or another stream.
- cycle 5, 2026-11-14 16:24:00, `qyzrtrwrwwlo`: example-targets W3: the handoff packet and the gap inventory, offline, with the observed gap's packet
  - decided to continue: The loop should go on. This run has committed W1, W2 and now W3, and contract rows A1, A6 and A7 pass. W4 is left: `project()` has to feed readiness, claim statuses and gaps to `find.py` and the index, with 105–109's historical reports kept apart. I can build and test that on the fixtures alone, without a job, the user or another stream.
- cycle 6, 2026-11-14 16:35:22, `nqztmpwynrtr`: example-targets W4: the index projection for find.py, claim statuses from current receipts and historical labels apart
  - decided to stop: The loop should stop. This run has committed W1 (planning, mutants, readiness), W2 (ingestion), W3 (handoffs and the gap inventory) and now W4 (discovery), and the stream's acceptance table and contract rows A1, A6 and A7 pass on this branch. What remains is the one-line `test_route.py:132` change, plus turning on `READINESS_IN_INDEX`, at the merge; Phase 5 then runs the real packets. Both belong to the coordinator and the main loop, and both are recorded under Progress, so the brief's status already says `done`.

## Summary

# Example-targets workflow stream: run summary

The workflow stream is finished. Its brief's status is `done`: W1–W4 and the stream's acceptance table pass on this branch (`example-targets-workflow`, base `qpvlyptu`). The run made 7 commits, oldest first. Nothing was pushed.

## Commits

**`wqsyopql`: W1, task planning from the sidecar and a frozen claim file**
- **Adds:** `workflow.plan_task()`, which turns a named task of a `target.json` sidecar into a full plan using only local files. It runs nothing and writes nothing.
  - The plan lists the revisions, artifact sources, tools, engine, gap mode, expected outcome, prerequisites and outputs.
  - A new claim-file format, `example-target-claim/v1`, comes with its schema. Tasks that share a claim file share one claim key.
  - Tasks that can't be planned are refused by name, and `build.py --plan` shows them as not executed.
  - The fixture gets three claim files. This is the one fixture edit the brief allows this stream.
- **Verified:** `test_workflow.py` 24 tests. The integration script passes, and contract row A1 (planning) passes.

**`zvnrtxsu`: W1, constructed mutant revisions**
- **Adds:** a third kind of revision to the sidecar schema (the change is additive). It is a mutant made from a base revision plus one patch, with the patch's sha256 and a description of the mutation.
  - `sidecar.py` keeps it apart from real commits: no upstream parent, tag or published artifact.
  - Planning checks the patch hash and refuses a changed or missing patch.
- **Verified:** `test_sidecar.py` 18 tests and `test_workflow.py` 29. The other streams' 19 sidecars still pass. The integration script exits 0.

**`nrpqnlol`: records the `sync.py check` errors that come from other streams' commits**
- **Adds:** only a Progress entry; no code changed.

**`onssrono`: W1, readiness per task**
- **Adds:** `workflow.readiness()` and `task_readiness()`, which work out six milestones per task, offline, and a summary per task and per target: catalogued, partial, scaffolded, executable or blocked.
  - A receipt counts only when it sits beside a `plan.json` that matches the current inputs. Stale and unreadable receipts are listed but never counted.
  - A predicted blocker never counts as a probe.
- **Verified:** `test_workflow.py` 37 tests. The integration script exits 0.

**`monsvovy`: W2, attempt ingestion**
- **Adds:** `workflow.ingest()` (new file `workflow_ingest.py`). For each task and attempt it publishes one format-2 receipt, tied to the prepared artifacts by sha256, with the evidence beside it.
  - Earlier attempts are kept.
  - Nothing is published unless `build.py`'s `check_result()` passes.
  - A replay decides no claim.
  - A fixture revision is identified by the git tree id of its sources.
  - Records that can't be tied to the prepared artifacts are refused, and nothing is published for them.
- **Verified:**
  - `test_workflow.py` 46 tests. Mutations of the expectation, the reproduced flag and the witness rule were each caught.
  - Contract A6 passes 3 of 3.
  - With the runtime stream's R4 laid over a scratch copy, the fixture's replays produced completed receipts.

**`qyzrtrwr`: W3, the handoff packet and the gap inventory**
- **Adds:** `workflow.handoff()` (new file `workflow_handoff.py`). It exports one task's packet without running anything:
  - its inputs, by path and sha256;
  - the exact commands, with proofs going through `pipeline.py submit`;
  - its receipts and readiness, and the first unmet prerequisite;
  - one recommended next command;
  - its gaps, with observed and predicted kept apart.

  An observed gap carries the capability-gap packet the brief describes. `inventory()` groups gaps across targets and ranks them.
- **Verified:**
  - `test_workflow.py` 53 tests. One test copies only the inputs a packet lists and gets the same packet back.
  - Contract A1 (handoff) and A7 pass.
  - Run read-only over the other streams' 19 sidecars: 9 gap groups, all predicted.

**`nqztmpwy`: W4, discovery through `find.py`**
- **Adds:**
  - **The index row.** `workflow_discovery.py` (new) writes the index row that `find.py` reads for `--family`, `--role`, `--readiness`, `--claim-status` and `--gap`. Claim statuses come only from the latest receipt that is still current. Stale receipts, predicted gaps and gaps whose evidence file is missing are kept apart. A historical `verdictLabel` stays beside the row, never inside `claims`.
  - **A fix to W2's attempt ids.** Two attempts in the same second used to sort at random, so "latest" was undefined. The microseconds now go into the id's suffix, which keeps the pattern the result schema requires.
- **Verified:**
  - `test_workflow.py` 57 tests, and the targets suite 97.
  - Contract: 9 pass, 7 skip.
  - The integration script exits 0 (`test_build` 190, `test_pipeline` 29).
  - Five mutations each made a test fail.
  - Run read-only over the other streams' 20 sidecars: 13 catalogued and 7 partial, with no claim status and only predicted gaps.

## Verification jobs

- **This stream submitted none,** so none of its own are pending or failed.
- **One job is pending, from the runtime stream:** `20261114-162937-example-targets-runtime-r3-run-verifier`.
- **85 failed jobs in the report** are from earlier loops (early November), not this run.

## Before pushing: `sync.py check`

- **0 warnings** to judge.
- **19 errors.** They are all the same kind: "session … has no manifest", plus one "points at log … that the manifest does not list" on `orwvprtsppyz`.
  - Every one is on a commit by the runtime, negative or positive stream, not on this stream's.
  - They appear because this workspace sees those commits in the shared repository, but their trace manifests are only in their own workspaces.
  - They should clear at the merge. It's recorded under Progress (`nrpqnlol`).
  - If any are still there after the merge, they need looking at.

## For the merge and the coordinator

These are recorded under the brief's Progress as requests, because they touch the coordinator's files:

1. **Turn on readiness in the index.** Set `workflow_discovery.READINESS_IN_INDEX = True`, and in `test_route.py:132` change the expected `None` to `"catalogued"`. Until then the row's `readiness` is `None`, with an `unsupported` note; the per-task readiness is already in the row.
2. **`result.schema.json`:**
   - It still requires `existingTests` and before/after excerpts, which target tasks don't have. Receipts fill them with an explicit `none: …` for now.
   - `claim.target.revisions` says "full commit SHA", which a fixture revision can't have.
3. **Handoff:**
   - Add a verifier commit to the records.
   - Fix the packet-file shapes.
   - Add a `build.py`/`find.py` entry point for the handoff view.
4. **Runtime:** decide how to prepare a mutant revision's artifacts (from `zvnrtxsu`).
5. **Phase 5:** run A1, A6 and A7 with the real packets, once the streams are merged.

## For your review

- **`find.py --readiness` matches only the target's summary,** where `partial` wins over `blocked`. A target with one blocked task can therefore show up as partial, not blocked.
- **The brief's description of fixture revisions is incomplete.** A revision's directory isn't all of its sources: `gate/both` is compiled into every JAR.

Nothing waits on credentials or a decision of yours for this stream itself. The merge, the coordinator's items above and Phase 5 are next.

Ended 2026-11-14 16:37:14 after 6 cycle(s): the session decided to stop; the brief says done.
