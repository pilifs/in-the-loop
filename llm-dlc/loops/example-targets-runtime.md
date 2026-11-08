# Stream brief: example targets, pinned artifacts and JVM replay

One of four streams of [`example-targets.md`](example-targets.md) that run in parallel, each in its own jj workspace on
its own branch. The others are [`example-targets-negative.md`](example-targets-negative.md),
[`example-targets-positive.md`](example-targets-positive.md) and [`example-targets-workflow.md`](example-targets-workflow.md).
Once all four are finished, the main brief's loop merges them ([Reconciling](example-targets.md#reconciling)) and runs
the case packets through what you built.

Started with the others by `llm-dlc/tools/run-streams.sh example-targets` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh example-targets-runtime` from this stream's workspace
(`jj workspace root --name example-targets-runtime`).

**The main brief is the instruction.** Read [`example-targets.md`](example-targets.md) and the acceptance contract
[`example-targets-acceptance.md`](example-targets-acceptance.md) in full every cycle, with their inputs. Their direction,
starting point, working rules, safety rules, downloads policy, deferrals and decisions all apply here. This file says
which items are yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section.

**Every cycle, read the integration check first**:
`$(jj workspace root --name default)/llm-dlc/loop-summaries/example-targets-integration.md`, if it exists. A failure in
your files is your next piece of work; a conflict in a file you own is a coordination task, recorded under Progress.

## Goal

Make an external target reproducible: resolve its pinned implementation, prepare its exact classpath, run a faithful
concrete driver in a separate JVM per revision, and hand artifacts and raw execution records to workflow. This stream
never decides whether a security claim holds.

## Starting evidence

Recounted in the main brief's [Where it starts from](example-targets.md#where-it-starts-from). In short: `build.py`
refuses real-world examples, and its claim record names dependencies as "declared in the build files" without hashing
them, for Gradle only (there is no Maven path); the verifier already generates harnesses, relocates the previous
version's classes and records statements, so reuse it through the current commands; application-core's construction
and value adapters still refuse what they don't support, so a Spring receiver or String isn't proof-ready because it
compiles; a one-sided replay no longer counts as reproduced (`witness.rs:779-786`). Phase 0 installs JDKs 8, 11 and 17
beside 25 and 21.

## Your items

### R1. The preparation boundary

Implement Phase 0's `PreparedTarget` and the raw execution record that workflow's ingestion consumes. Keep two
milestones apart:
1. **Source locked**: immutable revision or artifact coordinates, selected paths and descriptors, source provenance,
   the adapter recipe and the proposed obligations. No bytes need have been fetched or built.
2. **Artifacts ready**: sources and dependencies resolved, the build complete, and the original classes, resources,
   ordered classpath, toolchain, adapter and driver bytes hashed.

Only the second supplies a proof attempt's resolved identities, and workflow freezes the executable claim before any
proof. Use the existing digest utilities and canonical claim functions; define no competing key. A partial preparation
returns its stage, diagnostic and whatever artifacts exist, never an empty success.

### R2. Two artifact routes

**Pinned upstream build** ([decision 3](example-targets.md#decisions)): fetch the exact commit into an isolated
checkout, verify ancestry where asked, and run the recorded recipe with the revision's own build tool (its wrapper) and
a JDK it supports, from the ones Phase 0 installed. Original sources stay untouched; adapters compile separately. Record
the wrapper and build-tool version, the JDK identity, compiler flags, dependency resolution, resources, and the produced
class and JAR hashes. A build-enabling patch is separate recorded bytes with a scope review, never hidden in the
checkout. Upstream builds are jobs.

**Published artifact**: fetch a specific published JAR and its dependencies from Maven Central, check the recorded
checksums, and keep the source and release linkage separately. A release label supports no source-rebuild or
introducing-commit experiment, and a mutable repository URL is not an artifact identity.

For both: record every dependency actually on the classpath, its order, duplicate-class resolution and the loaded
target's origin. Before and after have separate closures; sharing a dependency needs evidence that both use those exact
bytes. Include the locale, charset, configuration and resources that matter. Unresolved dynamic versions and missing
hashes are preparation blockers. Downloads follow the main brief's [policy](example-targets.md#how-to-work-through-it):
github.com and Maven Central, sha256 recorded and rechecked.

A content-addressed acquisition and build cache may reuse identical preparation inputs, rechecking hashes on restore. A
cache hit is preparation reuse, not proof evidence. Planning and validation stay offline; acquisition is an explicit
later stage.

### R3. The implementation boundary

An adapter may construct inputs, invoke original methods and expose observations. Its source, compiled bytes,
transformations and domain restrictions are recorded, and a check shows it calls the selected upstream method without
shadowing its class. Distinguish:
- original published or source-built upstream bytecode;
- upstream bytecode reached through a declared adapter;
- a source slice or extracted kernel;
- a constructed surrogate or mutation.

Proof records keep these distinctions and their assumptions. An original-body call with modelled dependencies still has
a model boundary. A current application-core refusal produces a capability probe and a handoff, never a substitute
implementation.

### R4. Independent concrete controls

Each relevant revision runs in its own JVM and classpath. The case's independently authored oracle checks the security
or preservation statement; it never uses the implementation under test as its expected-value function. Record complete
normal or exceptional outcomes, inputs, relevant mutations and identities, and process completion, before a witness is
called reproduced.

Return stdout, stderr, status, tool and artifact identities and structured observations to workflow. Missing,
malformed, killed, timed-out or one-sided output is an execution or replay problem, not a violation, and an unexpected
throw is a failure to interpret, never a successful rejection. Replay with generated dependency stubs is labelled model
replay.

### R5. A small vertical slice on this branch

Prove the path end to end before Phase 5: on Phase 0's fixture JARs, then on one small published upstream method (for
example `PatternMatchUtils.simpleMatch` from a pinned `spring-core` JAR), through acquisition, preparation, a
separate-JVM driver and a raw execution record that Phase 0's ingestion interface accepts. Inventory what 105's
migration will need from you (its historical revisions, build route and JDK) as a note for the positive stream and
Phase 5. Phase 5 runs the six deep packets and 105's calibration through this path.

## Ownership and cooperation

- **Yours**: `examples/tools/targets/runtime*`, its focused tests and fixtures, and example numbers 315–319 if you need
  any.
- **Not yours**: `build.py`, `pipeline.py`, result and report schemas and the launchers (the coordinator); task planning
  and ingestion (workflow); case folders, local adapters and oracles (negative and positive). Ask through Progress.
- Your tests go in files of your own.

## Acceptance

At your finish, on your branch:
| Area | Evidence |
|---|---|
| Preparation | Both routes have focused tests, the upstream-build route on one real pinned revision as a job; source locks and resolved artifact locks stay distinct; stale bytes, a hash mismatch and classpath shadowing are detected |
| Execution | Complete per-revision outcomes reach the ingestion interface; malformed, killed, timed-out and one-sided replays stay failures or unresolved records |
| Slice | R5 runs on the fixtures and one published upstream method |
| Handoff | A preparation blocker returns its command, diagnostic, needed semantics and next action |

Your share of Tier A (A2, and the runtime half of A3–A5) is checked again in Phase 5 on the merged revision.

## Working rules

The main brief's [How to work through it](example-targets.md#how-to-work-through-it): the pipeline, the two-failure
timebox, and the downloads policy. Queue upstream builds and heavy acquisitions, and record each job's revision and id.
Small unit and JVM conformance checks run inline.

## Progress

- Not started. Forks after the main brief's [launch prerequisites](example-targets.md#launch-prerequisites), Phase 0
  included.
- Status: working

## Loop settings

- session: 3bb5a1f4-a4d5-4f4a-b511-6037ef3e1256
- model: claude-opus-5-5
- effort: high
- memory: 4G
- workspace: example-targets-runtime
- fork: e9be5afb-09c9-4473-a9e9-38f2fb61ca80

## Loop until

Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with
`waiting on jobs ID ...`. Stop with `done` when R1–R5 and your acceptance pass, or each is deferred by the timebox with
the finding. Stop with `blocked: ...` when what is left needs the user or another stream, and is recorded under
Progress. Don't grow into general Spring emulation or a broad CVE campaign. Anything new you find goes under Progress,
for the main brief's for-review list.
