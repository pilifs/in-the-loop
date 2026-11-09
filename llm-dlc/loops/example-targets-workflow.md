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

- Not started. Forks after the main brief's [launch prerequisites](example-targets.md#launch-prerequisites), Phase 0
  included.
- Status: working

## Loop settings

- session: eaff7dd7-6d26-4a35-811f-cb8e08f4ee79
- model: claude-opus-5-5
- effort: high
- memory: 4G
- workspace: example-targets-workflow
- fork: e9be5afb-09c9-4473-a9e9-38f2fb61ca80

## Loop until

Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with
`waiting on jobs ID ...`. Stop with `done` when W1–W4 and your acceptance pass, or each is deferred by the timebox with
the finding. Stop with `blocked: ...` when what is left needs the user or another stream, and is recorded under
Progress. No scheduler replacement, result-format migration or engine work. Anything new you find goes under Progress,
for the main brief's for-review list.
