# Stream brief: engine priorities, the own checker and the solver

One of two streams of [`engine-priorities.md`](engine-priorities.md) that run in parallel, each in its own jj
workspace on its own branch. The other is [`engine-priorities-jbmc.md`](engine-priorities-jbmc.md). Once both have
stopped, a reconcile loop merges them; [Streams](engine-priorities.md#streams) in the main brief says how.

Run with `llm-dlc/tools/feature-loop.sh engines-native`, from this stream's workspace
(`jj workspace root --name native`): the loop refuses any other.

**The main brief is the instruction.** Read [`engine-priorities.md`](engine-priorities.md) in full every cycle, and its
input [`engine-priorities-review.md`](engine-priorities-review.md) too. Its direction, evidence, working rules,
deferrals and decisions all apply here. This file only says which part of its plan is yours, and keeps your Progress.
Don't edit the main brief, the other stream's brief, or anything outside this file's `## Progress` section.

## Your phases

1. **1c** the Bitwuzla build job, queued first: it's long, and Phase 6 waits on it;
2. **4b** class initializers counted by shape, with `jvmcontract gaps` scans (static, inline). It decides Phase 5's
   scope, so it comes before Phase 5 here;
3. **5** class initializers in the own checker to the scope 4b supports, the `Enum.<init>`, `List.of` and
   `List.copyOf` models, and the queued strict rerun of 071 and 013;
4. **6a–6d** transcripts, the solver interface, the comparison job and the written recommendation.

Phase 5 is the core of this stream; do it before Phase 6 apart from 1c. While a Phase 5 job runs, go on with 6a and
6b.

Not yours: 1a, 1b, 2, 3, 4a and 4c. The JBMC stream defines how a result records its SAT backend (1b). Until that is
merged, record Bitwuzla's version and configuration in the Phase 6 job's own outputs; the reconcile loop fits them
into 1b's shape.

## Boundaries

You own the own checker and the solver: `lib/src/bmc/`, `lib/models/`, the new solver interface, the Bitwuzla build
and the Phase 6 transcripts, with their tests.

The JBMC stream owns `lib/src/jbmc.rs`, `jbmc_gaps.rs`, `jbmc_contracts.rs`, `phases.rs`, `deadline.rs`,
`lib/benchmark/` and `examples/tools/gap_table.py`. Don't change them. If your work needs a change there, record it
under Progress for the reconcile loop and work around it. Phase 6's comparison job therefore writes its own table
rather than changing the benchmark's.

Some files both streams may touch: `lib/src/main.rs` and `lib.rs` (CLI options, module list), `lib/tests/conformance.rs`
and `lib/tests/conformance/`, `lib/src/interp/`, `witness.rs`, `shrink.rs`, `Cargo.toml`. In those, add rather than
rewrite: new options, new cases and new functions, not reorganizations. Name every change to one of them under
Progress, so the reconcile loop knows where to look. The models in `lib/models` are on JBMC's class path as well: they
are yours, but say under Progress which JBMC results they may change.

## Working in a stream

- **Commit only here**, with `sync.py commit` as CLAUDE.md says. Never push, merge, rebase onto another branch, or
  move a bookmark. The branch is this workspace's `@-` line; the reconcile loop merges it.
- **Jobs.** Submit and commit jobs as usual. The runner works in the default workspace and also runs jobs committed
  here, at this commit (see `verification/README.md`). Results are collected there, not here: read them with
  `python3 "$(jj workspace root --name default)/verification/pipeline.py" report` and `status`, and the files under
  that workspace's `verification/results/`. Record what you take from a result under Progress with the job id. Its
  outputs (071's and 013's example pages, say) reach this branch only at the merge, so don't copy them in by hand; the
  reconcile loop updates the examples' `notes` from them.
- **Another session is not your concern** beyond the loop's usual rule: the JBMC stream works in its own directory
  and never touches this working copy.
- **Where you started.** Your session is a fork of the conversation that planned the streams (session `3761db96`,
  compacted), so you share its context with the other stream. What it settled is in the briefs; where your memory of
  it and a brief differ, the brief wins.

## Progress

- Nothing yet.

## Loop settings

- session: 63d80e44-36d9-4bcb-9e72-e31c6d9336ef
- model: claude-opus-5-5
- effort: high
- workspace: native
- fork: 3761db96-b870-47f7-aded-2ba264c165f4

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. Phase 5 is the core of this stream:
don't stop before it is done unless a step waits on a job or on the user. When everything left waits on a job, say so
under Progress with the job ids and stop: the loop is continued by running the same command once the results are
back. Stop when your phases are done, or what is left needs the user's input and is recorded under Progress as
deferred. Don't go on to polish, and don't start work that belongs to the other stream or the reconcile loop.
