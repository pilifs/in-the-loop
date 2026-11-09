# Brief: example targets, real-world changes as reproducible work packets

**Drafted 2026-11-08, from an outside plan; its [decisions](#decisions) were settled by the user on 2026-11-08.** It starts after the [launch prerequisites](#launch-prerequisites), which include Phase 0.

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh). It **scaffolds** external Java changes, Spring CVEs and
independent upstream changes of the same kinds, as packets a later agent can execute, prove, refute or turn into an
observed capability gap. It does not run the proof campaign. Four streams run in parallel, each a loop of its own with
a short brief that names its items:
- **runtime**: pinned artifacts and builds, original-bytecode adapters, separate-JVM replay;
- **negative**: the CVE catalog, and three deep negative/fix packets;
- **positive**: three independent historical positive packets, their mutation controls, and example 105's migration;
- **workflow**: task plans, receipt ingestion, handoffs, the gap inventory and discovery.

This brief is the instruction for all four. Its own loop, `llm-dlc/tools/feature-loop.sh example-targets` in the default
workspace, merges them once all are finished, then **runs the case packets through the merged infrastructure** and the
joint acceptance ([decision 2](#decisions)).

**Why now.** The repository's examples are almost all constructed. Real changes are what show whether the approach is
feature complete: each packet either reaches a proof task the tool supports, or stops at a reproduced, minimal
capability gap. Ranked across families, those gaps are the work list towards a v1 ([decision 11](#decisions)).

**Inputs.** Read these in full before the first piece of work of every cycle:
- [`example-targets-acceptance.md`](example-targets-acceptance.md), the acceptance contract: Tier A (infrastructure)
  and Tier B (the portfolio).
- Your stream brief, if you are a stream.
- [`example-targets-sources.md`](example-targets-sources.md), which separates current code, earlier research and the
  proposed design.
- [`example-targets-inputs/seeds.json`](example-targets-inputs/seeds.json), the researched revisions, tasks and probes
  of the six deep packets, the linked catalog entry and the optional control. It is research metadata, not a schema
  and not evidence.
- [`verification/findings.md`](../../verification/findings.md)'s open entries, read from the default workspace
  (`$(jj workspace root --name default)/verification/findings.md`). An entry in a file you own is context, not an item.
- This brief's [Where it starts from](#where-it-starts-from), recounted against the code.

The archived registry [`example-targets-inputs/spring-cve-targets.research-2026-11-04.json`](example-targets-inputs/)
is research input for the negative stream's catalog import: its capability descriptions are from an older verifier
(`4c279ba6`) and never override the current code. For background, read the rationale of
[`build-orchestration.md`](build-orchestration.md) (its deferred item 4c is this brief's seam) and
[`application-core.md`](application-core.md)'s for-review list.

**Where the plan comes from.** An outside review drafted it on 2026-11-08, as a coordinator brief, four stream briefs,
an acceptance contract, a source review and a seed file. Shared by the user, it was adapted here to this repository's
briefs. The review read the repository on GitHub at `57f04e55` (main), without building or running anything. It is
evidence, not instructions. Current code and collected job results take precedence over it, and every claim it made
was recounted [below](#where-it-starts-from).

## Direction

- **The deliverable is a case a later agent can continue without repeating the investigation.** That agent can find
  the case, read its exact question, prepare its two versions, reproduce its concrete behaviour, submit a supported
  proof task, or produce a minimal capability-gap packet. A folder with a CVE link and a guessed predicate is only a
  catalog entry.
- **A scaffold can be complete while its proof is unresolved.** Readiness and proof outcome are separate records.
- **Low-input before/after verification still holds**: fixed, externally meaningful observations and inputs;
  agent-proposed internal correspondence; claims that don't change when a proof gets hard. Security intent is an
  explicit property: preservation alone can't decide whether a behaviour is secure.
- **Extend what exists**: the example router, `build.py`'s planning and publication, format 2 (Claim, Attempt,
  Conclusion, Evidence, Bundle), canonical claim keys, gap advice, the proof cache, and `verification/pipeline.py`. Add
  the external-target seam they lack, no second result system, queue or scheduler.
- **Native strict, explicitly**: `--engine native --gaps strict` (the CLI default engine is still JBMC). An optional
  backend is kept only when it checks the same claim. A missing Java model is not a reason to migrate solvers.

## Where it starts from

Recounted 2026-11-08 at `210b9498` (application-core Phase 5 step 1, after its streams' merge `43ed2402`), against the
outside review's claims at `57f04e55`. **Recount again at application-core's final commit** ([prerequisite
2](#launch-prerequisites)): application-core is still delivering capabilities this table names.

| Finding | Evidence | Consequence |
|---|---|---|
| **Real-world examples are refused by the runner.** | `build.py`'s `not_executable()` (`examples/tools/build.py:306-310`): "its report is its README.md, and build.py has no adapter for its project's build". Running all skips them (`:259`); naming one exits 1 (`:261-266`, `:289`). `--render-only` refuses them (`:232-235`). | The new route replaces the refusal only for an example with a target sidecar. The others keep it. |
| **`--plan` is pure.** | `plan()` (`build.py:336-393`): nothing is built, copied or run. Real-world ids appear with `executable: false` and a reason. `plan()`'s adapter is gradle or javac only (`:389`). | `TaskPlan` extends `plan()`; it is the same plan the runner executes and the pipeline submits. |
| **Dependencies are declared, not hashed.** | `claim_record()` (`build.py:764-782`) hashes the patch and the copied trees; dependencies are the string "declared in the build files" or "the JDK" (`:775`), with "the artifacts themselves are not fingerprinted" (`:773-774`). Tools: `attempt_tools()` `:864-887`. There is no Maven path at all. | Bind attempts to the actual JARs, classpath order, JDK and adapter/oracle identities, through the existing claim record. |
| **The pipeline refuses real-world examples before planning.** | `verification/pipeline.py:1585-1587`, before `example_plan()` (`:1588`); tested at `verification/test_pipeline.py:428`. | `submit --example NNN --task T` consumes the same task plan. |
| **The index uses authored labels for real-world examples.** | `render_index()` (`build.py:4448`) takes `verdictLabel` (`:4465`) and writes `verdict: None` (`:4475`); `example.schema.json:115-116` requires `source` and `verdictLabel` for them. | Historical labels stay historical; a new receipt is shown beside them, never instead. |
| **Format 2 exists, with evidence checked before publication.** | `result_format.py` `FORMAT = 2` (`:34`), `pack()` (`:83-102`); `check_result()` (`build.py:958-969`) validates the flat view, the round trip, the stored format and the bundle's sha256s before `publish()` (`:979+`). 45 stored results are format 2, 112 format 1. | One format-2 receipt per task and attempt. No new format. |
| **Authored metadata is closed and has no locks.** | `example.schema.json`: `source` is `{kind, repository, url}` (`:56-64`), `additionalProperties: false` at the top (`:8`) and on every nested object. No commit field, hash, lock or build info. | A sidecar reference is a schema change, made once, in Phase 0. |
| **Five real-world examples, all handwritten.** | 105 (commons-numbers `pow`, all three conclusions positive), 106 (commons-lang `reverse`), 107 (commons-lang `subarray`, mixed: one property ⚠ unverifiable), 108 (jackson-core, unresolved), 109 (commons-codec `Hex.toDigit`, new version ✓, old-version regression ⚠ needs a `Character.digit` model, replay limits on `StandardCharsets.UTF_8` and locale-dependent `String.format`). Each has only `example.json` and `README.md`. | 105 is the calibration migration; 106 its documented fallback. 107–109 stay visible as they are. |
| **A one-sided replay no longer counts as reproduced.** | The outside review attributed this to example 109's record; it is VF-015's step 4, job `20261108-024648` (`findings.md:196-200`). Fixed after `57f04e55`: `witness::differences` is empty when either side couldn't replay (`lib/src/witness.rs:779-786`, test `:1052`), `equivalence.rs:2218-2224`; documented at `lib/README.md:245`. | Rely on it, and keep separate-JVM replay of both sides as the oracle path. VF-015's own remaining work stays deferred by the user. |
| **No fix command; JBMC is the CLI default.** | `lib/src/main.rs`: `Equivalence` `:39-40`, `Prove` `:95-96`, no `fix`; `engine` defaults to `jbmc` (`:579-580`, `:718-719`, `:349`), `gaps` to `strict` (`:591-592`, `:730-731`). | Repair is composed in the target layer from separate tasks; native is always requested explicitly. |
| **No external-target code yet, but the seam is planned.** | No `target.json`, `TaskPlan`, `PreparedTarget` or lock anywhere. `build-orchestration.md:599-604` defers "4c. External artifacts as inputs", with "whether dependencies may be downloaded" left to the user (`:90-91`). | This brief is 4c. The user settled downloads ([decision 1](#decisions)). |
| **Example numbers are reserved only in briefs.** | `application-core.md:266-271` (230–279), `cleanup.md:154-158` (197–229). The highest folder is 196; 197–279 are unused. Nothing in `examples/README.md` or `tags.json`. | This brief reserves 280–329 ([Streams](#streams)). |
| **The machine.** | Temurin JDKs from sdkman under `~/.sdkman/candidates/java/`: `25.0.5.0+8-tem` (the default, `Temurin-25.0.5+8`), `21.0.13.0+9-tem`, and, installed by the planning session on 2026-11-08, `17.0.21.0+9-tem` (`Temurin-17.0.21+9`), `11.0.33.0+10-tem` (`Temurin-11.0.33+10`) and `8.0.512.0+9-tem` (`1.8.0_512-b09`); also GraalVM CE 25, Maven 3.10.0, Gradle 9.8.2 and `/usr/bin/jbmc`. No `~/.m2`. Jobs have cloned from github.com (VF-015's job); nothing has used Maven Central. Jobs run in systemd user scopes with memory caps and no network restriction (`verification/README.md:201`). | Every JDK an upstream build of this portfolio needs is present ([decision 3](#decisions)), and none changes the default. |
| **Application-core** delivers ordinary receivers, bounded Strings and lists, modelled dependency outcomes and reuse in this baseline's Phase 5. | `application-core.md` Progress; open findings VF-023 (JBMC `List.size` stub), VF-018, VF-015 (deferred by the user), VF-002, VF-020. | Probe its actual final revision. A registered flag or a test that accepts an unsupported hook is not proof support. |

Side finding for the coordinator: `result.schema.json`'s `claim.inputs` is closed and has no `contracts` property, so an
advised example's claim (147, 148) would fail `check_result` once VF-002 lets it reach one (not run). Note it in Phase
0's recount; it is not this brief's to fix unless the sidecar's result-schema extension touches the same block.

## How to work through it

The [standing rules](brief-template.md#standing-rules), the [timebox](brief-template.md#the-timebox) included:
- **One step per cycle**, committed with `sync.py commit` in your own workspace.
- **Check each claim against the code first**, this brief's and the seed file's included.
- **Proofs, model checks, heavy upstream builds and benchmark runs are queued**, never run inline. Compiling, unit tests,
  and small JVM conformance runs of a prepared target run inline.
- **Recorded results are evidence, not inputs to edit.** Historical reports (105–109) are never rewritten.
- **Nothing gets weaker.** **Docs move with the behaviour.** **Defer what needs the user, explicitly.** **A
  reproducer before a fix.**
- **Two substantive failures end an item in this loop** (the timebox), recorded with its two jobs or attempts, the
  finding and what a further attempt would cost. An infrastructure failure (the network, the runner) is named as such,
  and doesn't count, but repeated semantic failures are never hidden behind it.

**Verification with the pipeline** ([decision 5](#decisions)), not `verification: separate`. Every job names the
exact revision, task and claim, expected semantic verdict, process expectation, bounds, engine and resource estimate.

**JDKs** ([decision 3](#decisions)). JDKs 25 and 21, the two current LTS releases and the most relevant for Java
development today, are the main targets, and 25 stays sdkman's default. Everything this wave writes (adapters, drivers,
fixtures, the Java parts of the targets modules) is compiled with `--release 21`, so it runs on both. A revision's
concrete controls run on 21 and on 25 wherever its pinned artifacts do, as two JVM identities whose outcomes are compared
and recorded separately; a disagreement between them is a finding, never averaged away. An older JDK (8, 11 or 17) is
used where a revision's build or runtime needs it, never by default, selected by its full path, not by changing
sdkman's default. Each preparation and replay
records the JDK it used, from its `release` file and `java -version`; a different JDK is a different identity.

**Downloads** ([decision 1](#decisions)) are allowed in jobs and in loops, from `github.com` and Maven Central
(`repo.maven.apache.org`) only, and only through hash-pinned acquisition: every fetched file's sha256 is recorded the
first time and checked on every reuse, and a mutable reference (a branch, a `latest`, a dynamic version) is refused.
Planning, linting, discovery and handoff inspection stay offline. Until runtime's acquisition is merged, a stream may
fetch a pinned file by hand to develop a driver, with its sha256 noted; such a run is a note, never evidence, and no
case folder contains downloader code. Heavy fetches and builds are jobs.

### Safety and semantic rules

- **Fixed claims.** Agents choose strategies, faithful adapters, supported engines, case splits and checked summaries.
  They never shrink a security domain, drop exceptional or effect observations, strengthen an assumption, weaken a
  predicate, or silently accept a model to get a better result. A semantically changed proposal is a new claim, linked
  to the original, for review; the original stays unresolved.
- **The vulnerable code is the target.** Never mock it, remove its class initializer, derive the oracle by copying the
  patch's condition, or normalize away the triggering input. A reduced kernel gets a narrower claim and lineage to the
  original, and can't discharge the original's obligation without a checked connection.
- **One property, two identities.** The vulnerable and fixed security tasks share one logical property and domain;
  their claim keys differ because their artifacts do. A narrower diagnostic property gets a new claim with a parent
  link.
- **Introductions are not inferred** from the fix's parent, the earliest affected version, blame or SZZ alone. Record
  candidate, vendor-attributed and experimentally established attribution separately. A merge commit needs an
  explicitly selected parent and a reason.
- **Compatibility includes legitimate inputs.** A patch that rejects everything can satisfy a rejection property and
  still fail the repair experiment. The allowed-change region is justified before any attempt, and never enlarged
  after a counterexample.
- **Positive means an expected outcome for a named claim**, not that the release is secure. An upstream merge or a
  passing test suite is provenance, not proof. A counterexample to a positive is a finding; its expectation is never
  rewritten to make the corpus green.
- **Constructed mutants stay constructed**: a base revision, a patch hash, a new artifact-bound claim key and a link to
  the case. They are sensitivity evidence, never another real CVE or historical success.
- **Evidence is honest**: exit 1, malformed or missing output, a kill or a timeout is not a violation; a one-sided or
  unusable replay is not reproduced; generated-environment replay is labelled model replay; an expected refusal is
  never counted as finding a CVE or proving a fix.
- **Scope labels**: original bytecode; original bytecode under explicit environment models; an extracted source or
  bytecode slice; a constructed surrogate. Concrete tests stay tests, and proved, tested and trusted evidence stay
  distinguishable.

## What each target contains

Every example stays in the numbered router. `example.json` gets one optional reference to a strict, versioned
`target.json` sidecar, a work manifest, not a second specification language. Exact names are frozen in Phase 0.

| Group | Content |
|---|---|
| Identity | Stable logical case and family ids, origin, target role, companion ids, matching rationale, source confidence |
| History | Full repository, revision and parent identities; separately named revision pairs (release, exact fix, introduction); advisory and PR links; introduction confidence; unresolved provenance |
| Preparation | Artifact route (published JAR or pinned upstream build), source selection, toolchain and JDK, exact argument vectors, dependency lock, classpath, source-to-artifact mapping, licences |
| Tasks | Stable task ids; references to existing property and observation contracts; target descriptors, domains, assumptions, bounds, allowed changes, prerequisites, semantic expectations |
| Controls | An independent predicate or oracle, the known trigger, legitimate inputs, positive and refutation controls, expected concrete outcomes per revision, the replay boundary |
| State and handoff | Per-task milestones, latest receipt references, blockers, earlier attempts, the exact next command, and the evidence that would close the item |

A typical packet has `example.json`, `target.json`, `sources.lock.json`, `claims/`, `replay/`, `controls/` and the
generated receipt references. Where a claim, model, contract or witness file already states a fact, refer to it and
hash it; don't duplicate it.

**Two freezes.** The source-level question is frozen before execution. After preparation, the execution claim is bound
to the actual classfiles and JARs, the ordered classpath, the JDK, the resolved dependencies, the harness, oracle and
model identities and the complete options, before the verifier runs, through the existing canonical-key logic,
extended narrowly. A source-only plan is not a bytecode proof.

**Receipts.** One format-2 receipt per task and attempt, earlier attempts kept. The case summary references them.
Vulnerable, fixed, compatibility and introduction results never overwrite each other or collapse into one scalar.

**Legacy reports** without a sidecar stay historical, searchable and non-executable, with a useful reason. Their origin
never changes to get past a gate.

### Readiness is not a verdict

| Milestone | Evidence |
|---|---|
| Catalogued | Research metadata, candidate scope, sources, unresolved items |
| Source locked | Full immutable revisions and artifact references, selected-parent relationships verified |
| Prepared | A reproducible preparation record, exact original artifacts and dependencies, a callable target |
| Oracle validated | Concrete original-JVM controls and usable per-revision observations agree with the independently stated task |
| Claim frozen | Domain, observations, assumptions, intended change, bounds, and artifact and model identities resolved |
| Attempted | A structured execution and evidence receipt for the exact claim |
| Scaffold complete | The next proof step can run, or a reproducible observed capability blocker and a complete handoff say why not |

Conclusions keep their own statuses (`established`, `refuted`, `unresolved`, none), and execution status, expectation
matching, replay status and proof scope stay independent. A build failure leaves a scaffold partial; a predicted
unsupported feature is a hypothesis until a probe reaches it; an actual capability refusal can be a successful
diagnostic while the security claim stays unresolved.

### The capability-gap packet

For each **observed** blocker: case, task and claim, and the exact verifier revision; the minimal command, the failing
operation or diagnostic, artifact and model identities; the smallest faithful reproducer, linked to the original call
path; why the missing semantics affects this claim; the inputs, exceptions, state, effects, bounds and observations it
needs; the likely owner module, related cases and existing findings; the acceptance check that would close it; and the
strategies tried with the next bounded action.

Kinds stay apart: missing Java semantics, input construction, oracle ambiguity, source provenance, build or dependency
failure, replay failure, timeout or resource exhaustion, and a suspected verifier bug. Reuse existing gap ids where they
fit: the corpus adds routing context, not a rival taxonomy. A gap shared by a CVE and its positive companion is
especially informative. Rank by distinct families and blocked obligations, not raw case counts; a priority is an
engineering aid, not evidence.

## Three shared interfaces

Frozen in Phase 0, before the fork:
1. **TaskPlan** (workflow): pure resolution of a named task, its declared claim, required artifacts and tools,
   prerequisites and expected evidence. No network, build, solver or output directory.
2. **PreparedTarget** (runtime): immutable source and artifact identities, toolchain, classpath, dependencies, the
   preparation outcome and its logs. A preparation failure is returned explicitly, with its stage, diagnostic and
   whatever artifacts exist; it never decides a security claim.
3. **Attempt ingestion** (workflow): takes the prepared task and the raw verifier and JVM execution records, validates
   and publishes the format-2 receipt, and derives status and next work without weakening the claim.

Task metadata in, results out, kept apart. A changed predicate, observation set, normalization, encoding, classpath,
model, construction or history domain, or relevant bound invalidates the applicable identity. A timeout change is a
new attempt under the same claim; a changed semantic domain is a different claim; a lower-bound exploration is a
linked diagnostic, never completion.

Entry points stay `build.py --plan` and `verification/pipeline.py submit --example`, with named-task selection,
preparation and replay, and a handoff view added as small adapter operations. Proposed, frozen in Phase 0:

```text
python3 examples/tools/build.py --plan NNN --task fixed-security
python3 examples/tools/find.py --origin real-world --readiness blocked --gap CAPABILITY
python3 verification/pipeline.py submit --example NNN --task fixed-security ...
```

## The portfolio

The 15 CVEs of the archived registry are imported as catalog entries, with their uncertainty and research date, and
CVE-2025-22234 is added as a linked research-only challenge. Three are promoted in place into deep packets, each paired
with an independent historical positive:

| Family | Negative target, release pair | Independent positive | First useful scope |
|---|---|---|---|
| Metric labels | CVE-2023-34055, Boot 2.7.17 → 2.7.18 | Boot `e8de5a6`, the `Outcome` enum | Finite label classification; status-to-label preservation |
| Matching predicates | CVE-2022-22968, Framework 5.3.18 → 5.3.19 | Framework `db9a10b`, `PatternMatchUtils` uses `startsWith` | Case-protected binding predicates; wildcard decisions |
| Password boundaries | CVE-2025-22228, Security 6.3.7 → 6.3.8 | Security `fe9e454`, `StandardCharsets.UTF_8` | Exact UTF-8 byte semantics; that revision's length policy |

Full SHAs, parents, probes and tasks are in the seed file and the stream briefs. These are researched seeds, not
reproduced cases, and the matching is deliberate but imperfect: outcome classification is not the method-label API, a
wildcard optimization proves no binder deny policy, and encoding preservation is no authentication policy. The Boot
property bounds one tag dimension, not whole-server availability. Binder checks separate a helper predicate from actual
protected-property mutation, aliases and nested paths included. BCrypt separates bytes from characters, encoding from
matching, and a local guard from authentication.

**CVE-2025-22234** ([advisory](https://spring.io/security/cve-2025-22234/)): the vendor says the CVE-2025-22228 fix
broke `DaoAuthenticationProvider`'s timing mitigation. 6.3.7 → 6.3.8 stays its own experiment, and 6.3.8 → 6.3.9 is
recorded separately (legacy long-password matching allowed again, new long passwords refused). Output or call equality
can't establish timing noninterference; a cost model is outside this wave. CVE-2024-38820 is the natural next binder
case (locale dependence). URI parsing, resource traversal, servlet dispatch and Spring4Shell stay catalog entries.

**The legacy migration**: example 105 moves to the new route as the supported primitive calibration (106 only with a
documented reason). 107's mixed evidence, 108's unresolved result and 109's replay limits stay visible.

## Launch prerequisites

The planning session is `e9be5afb-09c9-4473-a9e9-38f2fb61ca80`, the conversation that adapted this brief. The streams
fork from it, so Phase 0 is its work, done before any fork ([decision 7](#decisions)).

1. **Application-core finished**: its merge and Phase 5 committed, with its for-review list, and its `run-streams.sh`
   exited. Shared files (`build.py`, `pipeline.py`, the schemas) are touched only after that.
2. **The baseline recounted** at that commit: [Where it starts from](#where-it-starts-from) updated, application-core's
   delivered capabilities probed on the String, list, receiver and environment cases these packets need, and the
   integration contracts run inline.
3. **The inputs committed**: `example-targets-inputs/seeds.json`, and the archived registry with its sha256 checked
   against `e86301abe767bcd9c39c5c9dc8889dfcbb1c22bb45bead53fc630acd0b9c62e5` (the user supplies the file).
4. **Phase 0** ([below](#phase-0-interfaces-hooks-and-fixtures)), committed.
5. **The names**: `example-targets` and `example-targets-STREAM` in `feature-loop.sh` (refusing
   `example-targets-acceptance` and `example-targets-sources`, which aren't briefs), `example-targets` with its four
   streams in `run-streams.sh`, and the integration check `llm-dlc/tools/example-targets-integration.sh`. Both
   launchers are replaced by rename if anything runs from them.
6. **The briefs committed** with their session ids (done 2026-11-08, in the workspace `example-targets-plan`, rebased onto
   application-core's final commit at Phase 0), and the [decisions](#decisions) settled by the user (done 2026-11-08).
7. **Push**, at the user's request.
8. **This brief's status set to `working`**, and the planning session closed. The user then runs
   `FEATURE_LOOP_MEMORY_MAX=4G CARGO_BUILD_JOBS=8 llm-dlc/tools/run-streams.sh example-targets` from the default
   workspace, in tmux. It compacts the planning session once, before the forks.

## Phase 0: interfaces, hooks and fixtures

The planning session, in the default workspace, one step per commit, each with its reproducer or test:
1. **The sidecar schema**: `examples/schema/target.schema.json`, strict and versioned, and the one optional reference
   from `example.schema.json` (allowed for `origin: real-world` only). A sidecar with an unknown field, a mutable
   revision, a path escape or a dependency cycle is refused, with tests.
2. **The three interfaces** under `examples/tools/targets/`: `TaskPlan`, `PreparedTarget` and attempt ingestion, as
   frozen types and functions whose implementations fail closed with a named unsupported result that the owning stream
   replaces.
3. **The hooks**: `build.py --plan NNN --task T` and its real-world gate opened only for a sidecar example;
   `pipeline.py submit --example NNN --task T` consuming the same plan; `render_index()` and `find.py` projections for
   family, role, readiness, claim status and gap; the result-schema extension points for dependency identities, task
   references and controlled evidence paths, format 2 kept and old receipts valid.
4. **Fixtures**, deterministic and local, used by every stream's unit checks: a two-revision adapter fixture (two small
   JARs built from fixture sources, with an original-method call through an adapter), a malformed or incomplete result,
   and a deliberate capability refusal.
5. **The integration contract**, `examples/tools/test_targets_contract.py`: one test per Tier A row that each stream's
   work can reach on the fixtures, each either reaching its final outcome or stopping at the named unsupported result
   its stream hasn't replaced yet.
6. **The numbers and names**: the ranges [below](#streams) recorded, and prerequisite 5.

## Streams

| Loop | Brief | jj workspace | Owns |
|---|---|---|---|
| `example-targets-runtime` | [`example-targets-runtime.md`](example-targets-runtime.md) | `example-targets-runtime` | `examples/tools/targets/runtime*` and its tests and fixtures |
| `example-targets-negative` | [`example-targets-negative.md`](example-targets-negative.md) | `example-targets-negative` | the catalog folders and the three negative packets: their source records, local adapters, oracles, probes and notes |
| `example-targets-positive` | [`example-targets-positive.md`](example-targets-positive.md) | `example-targets-positive` | the three positive packets, their mutation controls, the optional control, and 105's migration data |
| `example-targets-workflow` | [`example-targets-workflow.md`](example-targets-workflow.md) | `example-targets-workflow` | `examples/tools/targets/workflow*`, the sidecar schema after Phase 0, and its tests |
| `example-targets` | this brief | `default` | Phase 0, the merge, Phase 5 and the joint acceptance |

**Runtime produces evidence; workflow classifies it.** Case streams write no downloaders or parsers of their own.

**Shared files have one writer** ([decision 6](#decisions)): the planning session, in Phase 0, writes `build.py`,
`pipeline.py`, `result_format.py`, the shared schemas, `find.py`, `examples/tags.json`, the generated indexes, the
launchers and the integration script. While the streams run, none of them edits these. A stream that needs a change
records an interface request under its Progress and works on what doesn't depend on it; a purely additive line (one
tag, one registration) may go in a block marked with the stream's name, anything else waits for the merge.
`examples/README.md` and `examples/tags.json` take additions only. Application-core's engine files (`lib/`) belong to
no stream here: a gap in them is a capability packet, never an edit.

**Example numbers**, after application-core's 230–279:
- this brief, Phase 0 and Phase 5: 280–284 and 325–329;
- negative 285–304 (the 16 catalog CVEs, the 3 deep packets among them, numbered once);
- positive 305–314;
- runtime 315–319;
- workflow 320–324.

Mutation controls live in their packet's `controls/`, not under numbers of their own. Logical ids in the seed file are
not example numbers.

**Memory** ([decision 8](#decisions)): four streams at 4 GB each plus the integration check's 3.5 GB come to 19.5 GB of
the machine's 46, leaving the runner about 24 GB. Upstream builds and acquisitions are jobs, with their own estimates.

**Each stream can start on its own**: runtime on Phase 0's fixture JARs and one small published upstream method;
negative and positive on history, tasks, oracles and controls; workflow on the fixtures and genuine existing format-2
receipts. **The case packets meet the infrastructure in Phase 5** ([decision 2](#decisions)), never through edits
across branches.

### The integration check

`run-streams.sh` merges the four streams' current `@-` in its `example-targets-integration` workspace whenever one
moves, at most hourly, and runs [`example-targets-integration.sh`](../tools/example-targets-integration.sh) there. The
report goes to `llm-dlc/loop-summaries/example-targets-integration.md` in the default workspace. Its outcomes are
distinct: a merge conflict (reported by `run-streams.sh`), `CONTRACT FAILED` (`test_targets_contract.py`), and
`TESTS FAILED` (`build.py`'s, `pipeline.py`'s and the targets modules' suites, and every sidecar in the tree validated
offline). It runs nothing that downloads or builds upstream code. Each stream reads the report every cycle; a failure in
its files is its next piece of work, and a conflict in an owned interface is recorded, never ignored.

### Reconciling

As [`application-core.md`](application-core.md#reconciling) does, for four streams:
1. Check all four are finished (`done` or `blocked`, not only an inactive scope), and the integration scope inactive.
2. Wait for the verification loop to commit what it left in this working copy. Don't move or commit its files.
3. Record each stream's last turns, and copy their logs.
4. Merge with `jj new @- example-targets-runtime@- example-targets-negative@- example-targets-positive@-
   example-targets-workflow@-`, and commit.
5. Fold their Progress here, every timebox deferral and every interface request first.
6. Forget the five workspaces. Their directories are the user's to delete.

## The plan

### Phase 0 (the planning session, before the fork)

[Above](#phase-0-interfaces-hooks-and-fixtures).

### Phases 1–4: the streams

Each stream works through its brief's items, one step per cycle, against Phase 0's interfaces and fixtures. Runtime's
acquisition and replay are real on its branch (it downloads, pinned). The case streams deliver packets ready for
preparation: source locks checked against upstream, frozen source-level tasks, independent oracles, controls and
drivers, and expected outcomes per revision. Workflow delivers planning, ingestion, handoffs and discovery on the
fixtures and on existing receipts.

### Phase 5: after the merge (this brief's own loop)

1. **The packets through the merged path**: each of the six deep packets prepared by runtime's code (jobs), its controls
   replayed in separate JVMs, its claim frozen and bound to the prepared artifacts, and its probe run, each result
   ingested by workflow's code. A failure in one stream's code is fixed here, with a reproducer.
2. **The calibration**: example 105's migrated task to an actual established or refuted native result (gate A5).
3. **The joint acceptance** ([contract](example-targets-acceptance.md)), on the reconciled revision, through the pipeline
   where it says so. A merge conflict, a compile failure, a contract failure, a pending job and a semantic failure are
   different outcomes; stream-local tests are not integrated acceptance.
4. **The v1 gap inventory** ([decision 11](#decisions)): every observed capability gap, ranked by distinct families and
   blocked obligations, with each one's reproducer, owner module and closure test, published through workflow's
   projection and in the for-review list.
5. **The for-review list**: completed scaffolds, unresolved proof claims, observed capability packets, partial cases,
   pending jobs and timebox deferrals, every Tier A gate and every portfolio row with its state.

## Done when

| Phase | Criterion |
|---|---|
| 0 | A0: the sidecar, three interfaces, hooks, fixtures, contract test, numbers and names committed before the fork |
| 1–4 | Each stream's own acceptance, in its brief, or its items deferred by the timebox with the finding |
| 5 | Tier A passes on the merged revision; every Tier B row has its stated readiness; the gap inventory and the for-review list are complete |

The common infrastructure passes its merged acceptance; every research entry is honestly discoverable; each deep case
has an explicit complete or partial scaffold status; each proof task has its own evidence or reproducible blocker; and
a fresh agent can continue one case from its handoff without re-mining history or guessing what success means. Six
complete deep scaffolds are never reported while any lacks reproducible artifacts or a validated oracle; a case the
timebox stops is delivered partial, with the exact missing row, never replaced by an easier one.

Measure reproducible artifacts, validated oracles, frozen claims, distinct observed gaps, new structured proof and
refutation results, complete replays, and time to the next actionable task, counting every enrolled case, blocked ones
included, by family and assurance scope. This wave makes no detection-rate, prevention or ranking claim.

## Deferred: not in this loop

Full proof completion across the CVE list; unrestricted Spring, container or filesystem models; timing noninterference;
automatic discovery of introducing commits; broad JDK, regex or reflection support; solver migration; a new certificate
platform; a second scheduler; a remote proof store; and the user-deferred findings (VF-015's remaining work). A case
may justify a narrow future library extension: this wave's output is the reproducer, the semantics needed, the claims
affected and the closure test, not an engine rewrite.

## Decisions

Settled by the user on 2026-11-08:
1. **Downloads**: allowed in jobs and in loops, from github.com and Maven Central only, through hash-pinned acquisition
   (sha256 recorded and rechecked; mutable references refused). Planning and discovery stay offline. This settles
   `build-orchestration.md`'s open question for this wave.
2. **Four streams, and the case packets run in Phase 5**: the streams build against Phase 0's frozen interfaces and
   fixtures, and this brief's own loop runs the original-JVM replays and the calibration after the merge (gates A3–A5).
3. **Older JDKs installed**, so each revision is built with its own build tool and a JDK it supports: Temurin 8, 11 and
   17, installed by the planning session on 2026-11-08 beside 21 and 25 ([Where it starts from](#where-it-starts-from)).
   JDKs 25 and 21 are the main targets, as the most relevant for Java development today, and 25 stays the default ([How
   to work through it](#how-to-work-through-it)). The artifact routes are the outside plan's two: a published artifact, or a pinned
   upstream build.
4. **The archived registry** is supplied by the user, and committed with its sha256 checked (prerequisite 3).

Proposed by the planning session and settled by the user on 2026-11-08, as proposed:
5. **Verification with the pipeline**, not separate, so rows can close in the loop.
6. **One writer for shared files**: the planning session in Phase 0; streams make only marked additive edits, and
   record other requests for the merge (as application-core's decision 3).
7. **Phase 0 in the planning session** `e9be5afb`, after application-core finishes, before the fork (the user confirmed
   it in that session). That conversation's
   earlier part is application-core's run and loop tooling; `run-streams.sh` compacts it once before forking.
8. **Memory**: 4 GB per stream scope, about 24 GB for the runner, upstream builds as jobs with their own estimates.
9. **Model and effort**: `claude-opus-5-5` at high effort for every loop.
10. **Example numbers 280–329**, as [allocated](#streams).
11. **The v1 gap inventory** as an explicit Phase 5 output: the user's aim for this wave is to show whether the
    approach is feature complete, and drive towards a v1.
12. **Adaptations to the outside plan**: the claims it got wrong are corrected [above](#where-it-starts-from) (109's
    replay, reservations, the closed schema); its private link to an earlier document is dropped from the published
    sources; its launch metadata is this repository's.

## Progress

- Drafted 2026-11-08 by the planning session, from the outside plan, while application-core's Phase 5 was running. The
  starting point was recounted at `210b9498`. The user settled decisions 1–4.
- 2026-11-08, **decisions 5–12 settled** by the user, as proposed: the pipeline, one writer for shared files, Phase 0 in
  this session after application-core finishes, 4 GB streams and about 24 GB for the runner, `claude-opus-5-5` at high
  effort, example numbers 280–329, the v1 gap inventory as a Phase 5 output, and the adaptations to the outside plan.
- 2026-11-08, **the JDKs installed** by the planning session, at the user's request, out of Phase 0: Temurin 17, 11 and 8
  with sdkman. sdkman made each the default as it installed, despite a declined prompt, so the default was set back to
  `25.0.5.0+8-tem` at once (about two minutes; no job ran and no loop ran `java` meanwhile). Phase 0 has six steps left. Prerequisites 1, 2 and 4–8 are still to do:
  application-core finishes first, and the names are registered in Phase 0, so nothing can launch this loop before it.
- 2026-11-09, **the archived registry committed** (prerequisite 3): the user supplied the outside plan's package, and
  `example-targets-inputs/spring-cve-targets.research-2026-11-04.json` is its `inputs/` file, sha256 `e86301ab…` as
  pinned, with 15 cases and the stale `4c279ba6` verifier review. The package's other files match the text the briefs
  were adapted from.
- Status: blocked: application-core's finish, and Phase 0 by the planning session

## Loop settings

- session: 051e402b-750c-4a9d-bdd2-24dfb39add84
- model: claude-opus-5-5
- effort: high
- integration: llm-dlc/tools/example-targets-integration.sh
- new-window: no

## Loop until

The reconcile comes first. Don't stop before the merge is committed, unless a stream is unfinished or the merge needs
the user. Then Phase 5. Keep the last line of Progress a status: `working`, `waiting on jobs ID ...`, `done`, or
`blocked: ...` with what needs the user. Stop with `done` once Tier A passes on the merged revision, every portfolio row
has its stated readiness, and the gap inventory and for-review list are complete. A missing core result is recorded as
partial or blocked, never as done. Don't turn the scaffolding loop into the proof campaign that follows it, and items
deferred by the timebox count as recorded deferrals, never as a reason to keep going.
