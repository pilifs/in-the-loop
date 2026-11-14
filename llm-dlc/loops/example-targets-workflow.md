# Stream brief: example targets, tasks, receipts and handoffs

One of four streams of [`example-targets.md`](example-targets.md) that run in parallel, each in its own jj workspace on
its own branch. The others are [`example-targets-runtime.md`](example-targets-runtime.md),
[`example-targets-negative.md`](example-targets-negative.md) and [`example-targets-positive.md`](example-targets-positive.md).
Once all four are finished, the main brief's loop merges them ([Reconciling](example-targets.md#reconciling)) and runs
the case packets through what you and runtime built.

Started with the others by `llm-dlc/tools/run-streams.sh example-targets` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh example-targets-workflow` from this stream's workspace
(`jj workspace root --name example-targets-workflow`).

**The main brief is the instruction.** Read [`example-targets.md`](example-targets.md) and the acceptance contract
[`example-targets-acceptance.md`](example-targets-acceptance.md) in full every cycle, with their inputs. Their direction,
starting point, working rules, safety rules, downloads policy, deferrals and decisions all apply here. This file says
which items are yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section.

**Every cycle, read the integration check first**:
`$(jj workspace root --name default)/llm-dlc/loop-summaries/example-targets-integration.md`, if it exists. A failure in
your files is your next piece of work; a conflict in a file you own is a coordination task, recorded under Progress.

## Goal

Make each external example a durable set of tasks another agent can resume without rediscovering its revisions, claim,
oracle or blocker, on the router, the pipeline, the canonical claim machinery and format 2. A case's authored
expectations stay apart from what an attempt established. A reproducible Spring case may expose a real checker
limitation: keep it as an actionable result, and never weaken the property or set the expectation to `unverifiable` to
make the run green.

## Starting evidence

Recounted in the main brief's [Where it starts from](example-targets.md#where-it-starts-from). In short: `build.py
--plan` resolves a plan without executing anything (`plan()`, `build.py:336-393`); `result_format.py` keeps Claim,
Attempt, Conclusion, Evidence and Bundle apart (`pack()`, `:83-102`), and `check_result()` validates and hashes evidence
before `publish()`; real-world examples are refused by `build.py` and by `pipeline.py` before planning, and indexed by
their authored labels; `example.schema.json` is closed.

Phase 0 delivered (2026-11-09; the main brief's [Phase 0](example-targets.md#phase-0-interfaces-hooks-and-fixtures)):
the sidecar schema and `examples/tools/targets/sidecar.py`, now yours; `workflow.py`, whose `plan_task`, `ingest` and
`handoff` are stubs returning `Unsupported` for you to replace and whose `project` states only what the sidecar says;
the hooks in `build.py`, `pipeline.py`, `render_index()` and `find.py`, through `route.py`; the result schema's
`claim.target`; the fixtures; and the contract rows that are yours, A1, A6 and A7, and A5's ingestion half, in
`examples/tools/test_targets_contract.py`. They stop at your stubs now, and your work turns them into passes.

## Your items

### W1. The authored task manifest

Phase 0 freezes the sidecar schema; you own it from then, with additive changes recorded for the merge. Implement
`TaskPlan` behind Phase 0's hook: resolve a named task from local metadata (revisions, claim inputs, prerequisites,
tools, outputs, preparation needs), with no network, build, solver or output directory. Each task names its target
descriptor, property or preservation relation, domain, observations, explicit bounds, allowed-change region, models,
expected semantic outcome and prerequisite tasks. Refuse unknown fields and cyclic dependencies, and resolve default
bounds before a claim is frozen. Vulnerable and fixed tasks share the predicate and domain and get different
artifact-bound identities; compatibility is its own task; an introduction task stays unavailable until ancestry and an
independent oracle justify it. Positive tasks use the same path, their mutants with their own provenance.

Readiness is independent milestones (provenance locked, artifacts prepared, oracle replay validated, claim frozen,
capability probed, attempt recorded), from which catalogued, partial, scaffolded, executable and blocked summaries are
derived. None is a proof verdict.

### W2. Attempt ingestion

Implement ingestion behind Phase 0's interface: bind the resolved claim to runtime's prepared artifacts, take the raw
verifier and JVM records, and publish one format-2 receipt per task and attempt, earlier attempts kept. A case summary
references receipts; it never overwrites the vulnerable, fixed and preservation outcomes or invents a combined proof.
Execution status, semantic conclusion, expectation matching, proof scope and replay status stay distinct. Keep the
current malformed-output, kill, witness and bundle checks; exit 1 is no violation; a capability refusal is unresolved;
a preparation failure is a preparation failure; a one-sided replay is not reproduced; generated-environment replay is
model replay. A changed artifact, adapter, predicate, model or domain makes old evidence inapplicable; a strategy change
is a new attempt under the same claim, a semantic change a linked new claim. Result-schema extensions beyond Phase 0's
are interface requests.

### W3. Handoffs and the gap inventory

Export a compact task packet: immutable inputs, exact commands, current receipts, the next prerequisite and one
recommended action, and for an observed gap the main brief's packet (reproducer, diagnostic, verifier revision, Java
semantics needed, likely module, closure test). Predicted limitations stay apart from observed refusals, and build
failures from library limits. Another agent resumes a blocker without editing the claim; a narrower kernel is a
separate task with explicit correspondence work, the original kept unresolved. Build the inventory projection that
Phase 5's v1 ranking reads: gaps grouped across families, by blocked obligations.

### W4. Discovery and scheduling

Implement behind Phase 0's `find.py` and index hooks: family, role, readiness, claim status and gap filters, every
catalogued and blocked target discoverable, and 105–109's historical reports clearly apart from current receipts.
Submission consumes the same plan the runner executes; the handoff export goes through this workflow, not a second
scheduler; native tasks get no mandatory JBMC dependency.

## Ownership and cooperation

- **Yours**: `examples/tools/targets/workflow*`, the sidecar schema and `sidecar.py` after Phase 0, `test_workflow.py`
  (rewrite its stub tests as you replace each stub), `test_sidecar.py`, your other tests, the fixture's claim files
  (`targets/fixtures/claims/`, with the `claim` keys in `fixtures/target.json` that name them), and example numbers
  320–324 if you need any.
- **Not yours**: `build.py`, `pipeline.py`, `result_format.py`, the shared result schemas, `find.py`, the generated
  indexes, tags and launchers, `interfaces.py`, `route.py` and the contract test (the coordinator, behind Phase 0's
  hooks); acquisition, builds, adapters and JVM execution
  (runtime); case folders (negative and positive). Ask through Progress.

## Acceptance

At your finish, on your branch:
| Requirement | Evidence |
|---|---|
| Pure planning, strict manifests | Offline tests; invalid revisions, fields, paths and task dependencies refused |
| Durable multi-task results | Separate vulnerable, fixed and preservation receipts on the fixtures; old attempts kept; stale-input checks pass |
| Honest ingestion | Kill, malformed output, a false exit-code match and incomplete replay rejected |
| Resumable work | An isolated test session resumes a fixture handoff from its referenced inputs only |

In Phase 5: A1, A6 and A7 on the merged revision, with the real packets.

## Working rules

The main brief's [How to work through it](example-targets.md#how-to-work-through-it): the pipeline, the two-failure
timebox and the safety rules. Planning and discovery never touch the network.

## Progress

- Forked 2026-11-14 after the main brief's [launch prerequisites](example-targets.md#launch-prerequisites), Phase 0
  included.
- 2026-11-14, **W1 planning**: `workflow.plan_task()` resolves a task from the sidecar and its claim file alone (no
  network, process or write), and A1's planning row passes. A claim file is `example-target-claim/v1`
  ([`examples/schema/target-claim.schema.json`](../../examples/schema/target-claim.schema.json), new and mine):
  property, kind (property, or preservation/compatibility), statement, `assume` (the domain), `assert`, `throws`,
  `nullable`, `mayAlias`, observations, assumptions with their basis, bounds, models, construction plan and gap
  contracts. `TaskPlan.claim` carries all of it, with the task's `allowedChange`, the bounds resolved (jvmcontract's
  defaults `unwind` 16 and `maxArrayLength` 8 stated, and listed in `defaultBounds`), every referenced file and
  applicable control hashed, and `key`, the source-level claim's canonical digest (build.py's `canonical_digest`):
  vulnerable, fixed and mutant tasks sharing a claim file share it; the engine is left out (a strategy), the gap mode
  kept. Refused by name: no preparation (catalogued), a route missing its artifacts or build, a proof task without an
  explicit engine or gap mode, a prove task without a claim file, a claim file missing, invalid, of the wrong kind,
  outside the folder or at odds with the task's bounds, a replay without an oracle and a driver, and an introduction
  task until the introduction is `established` with an oracle control. The fixture's claim files are
  `fixtures/claims/` (gate-security for the three security tasks, gate-preservation, regex-probe). `test_workflow.py`
  24 tests; the integration script passes (contract 4 pass and 12 at stubs, targets suite 61, `test_build.py` 190,
  `test_pipeline.py` 29).
- **For the merge** (coordination, not blocking):
  - *Negative and positive*: a task's `claim` file is read as `example-target-claim/v1`. A claim file in another shape
    leaves the sidecar valid and the task unplannable, with the schema error as its `notExecuted`.
  - *Runtime*: `run_verifier` can build its argv from `plan.claim` (`assume`, `assert`, `throws`, `nullable`,
    `mayAlias`, `allowedChange`, `bounds`, `plan`, `contracts`); the contract test's own `fixture_plan()` carries only
    `task`, `allowedChange` and `bounds`. Artifact entries add two keys to `ARTIFACT_SOURCE`: `parent` (a commit's
    selected parent) and `published` (every published artifact of the revision; the singular `coordinates`, `url` and
    `sha256` only when there is exactly one).
  - *Coordinator*: the fixtures' README could list `claims/` (its table is the coordinator's).
  - *Positive (and negative)*: a constructed mutant is now a revision (below): `{"mutant": {"base", "patch",
    "sha256", "description"}}`, as the `after` of a `mutation` pair whose `before` is its base.
  - *Runtime*: a mutant's artifact entry has no `commit` or `fixture`; `mutant` carries `base` (its revision name and
    commit or fixture, and on the published-artifact route the base's `published` list), `patch` (path and sha256,
    checked at planning) and `description`. Preparing it means the base's sources with the patch applied (`git apply`
    in the source root), then the route's build, or on the published-artifact route the patched sources compiled
    against the base's artifacts; the sha256 is rechecked before applying. A preparation that ignores the key fails
    on the missing commit instead of building the base unpatched.
- 2026-11-14, **W1 constructed mutants**: an additive revision kind in `target.schema.json`, `mutant` (base revision,
  patch file in the folder, its sha256, the mutation in words), for any role. `sidecar.py` keeps it constructed: its
  base is a commit or fixture revision (one patch deep, never its own base), it has no parent, tag or release, no
  published artifact names it, and it appears only as the `after` of a `mutation` pair against its own base; a
  mutation pair's `after` is never an upstream commit, and a mutant never sits in an exact-fix, positive, release or
  introduction pair. Planning resolves a mutant on its base's route: no `commit` or `fixture` in its entry (above), the
  patch's sha256 checked against the lock and a mismatch or missing patch refused at `prepare` ("a changed mutant is a
  different control"), git (and javac on the published-artifact route) required. A mutant task shares the source
  claim's `key` with the fixed task of the same claim file; the artifact-bound identity (W2) separates them through the
  patch hash. The other streams' 19 current sidecars still pass the stricter checks. Tests: `test_sidecar.py` 18 (3
  new), `test_workflow.py` 29 (5 new); the integration script passes (contract 4 pass, 12 at stubs; targets suite 69,
  `test_build.py` 190, `test_pipeline.py` 29).
- **Check errors that aren't this branch's** (for review, as earlier parallel loops recorded them): since the other
  streams committed, `sync.py check` here reports "session … has no manifest" for their commits, which it sees in the
  shared repository while their trace manifests are only in their own trees: `muqvuqyqpwyz` (runtime R1),
  `pomrmppunkzt` (negative N0) and `rzvwqpqtuumn` (positive's source locks). Commit `zvnrtxsunllx` stands with those 3
  errors and none of its own; they clear at the merge.
- 2026-11-14, **W1 readiness milestones**: `workflow.readiness(folder, example, target)` and `task_readiness()` derive,
  offline and read-only, each task's six milestones (`provenanceLocked`, `artifactsPrepared`, `oracleValidated`,
  `claimFrozen`, `capabilityProbed`, `attemptRecorded`), each reached, not reached or not applicable with its evidence,
  from the sidecar, its files and the folder's receipts; and a summary per task and per target: catalogued (no
  preparation), partial (a scaffold milestone missing, or an observed provenance, build, oracle or replay blocker),
  scaffolded (a reproducible scaffold, proof support not yet probed), executable (probed by a completed current
  attempt, no observed capability blocker) and blocked (an observed java-semantics, input-construction, verifier-bug or
  resources blocker on a sound scaffold). None reads a conclusion as a verdict. Provenance needs `sourceConfidence`
  checked-upstream or reproduced and a plan that isn't refused at `prepare` (a changed mutant patch unlocks it; open
  `history.unresolved` questions are listed); a revision is prepared when some receipt binds it from the same artifact
  source and adapter sources; the oracle is validated when a replay task covering the revision has a current attempt
  that completed with expectation `yes`; a predicted blocker is no probe, nor is an observed one whose packet file is
  missing. A receipt counts only beside a `plan.json` (`workflow.plan_record()`: the plan, `attempt_inputs()` and
  their key), so a changed claim file, control, adapter, artifact source or bound makes it stale (listed, never
  counted); a receipt that isn't JSON, isn't format 2, lacks `plan.json` or is filed under another task is listed as
  unreadable. W2 writes `plan.json` and sets a replay's expectation to `yes` only when every side replayed and the
  oracle matched. On the fixture today every task is partial: no receipt exists yet (the recorded controls are Phase
  0's records, not receipts). Tests: `test_workflow.py` 37 (8 new); the integration script passes (contract 4 pass, 12
  at stubs; targets suite 77, `test_build.py` 190, `test_pipeline.py` 29).
- **For the merge** (coordination, for W4): `test_route.py`'s `IndexAndFindTest` (the coordinator's) asserts the
  index projection's `readiness` is None and that `find.py --readiness blocked` matches nothing, Phase 0's stub
  behaviour. When W4 projects `readiness()` into `project()`, its stub sidecar (no preparation) derives `catalogued`,
  and that assertion needs the coordinator's update at the merge; W4 records the exact line then.
- **Open for W2**: `result.schema.json`'s `claim.target.revisions` takes 40-hex commit SHAs only, and A6 expects the
  fixture's `before` and `after` there, which have no commit. W2 decides whether an honest content identity fits
  (the fixture sources' git tree id is 40-hex, but isn't a commit), or records an interface request.
- Next: W2 ingestion (`ingest`, with `plan.json` beside each receipt), then the readiness tests over its receipts.
- Status: working

## Loop settings

- session: eaff7dd7-6d26-4a35-811f-cb8e08f4ee79
- model: claude-opus-5-5
- effort: high
- memory: 12G
- workspace: example-targets-workflow
- fork: e9be5afb-09c9-4473-a9e9-38f2fb61ca80

## Loop until

Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with
`waiting on jobs ID ...`. Stop with `done` when W1–W4 and your acceptance pass, or each is deferred by the timebox with
the finding. Stop with `blocked: ...` when what is left needs the user or another stream, and is recorded under
Progress. No scheduler replacement, result-format migration or engine work. Anything new you find goes under Progress,
for the main brief's for-review list.
