# Brief: example targets, real-world changes as reproducible work packets

**Drafted 2026-11-08, from an outside plan; its [decisions](#decisions) were settled by the user on 2026-11-08; [Phase 0](#phase-0-interfaces-hooks-and-fixtures) was done on 2026-11-09.** It starts after the [launch prerequisites](#launch-prerequisites).

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

Recounted 2026-11-08 at `210b9498` against the outside review's claims at `57f04e55`, and **again on 2026-11-09 at
application-core's final commit, `a7abc155`** ([prerequisite 2](#launch-prerequisites)). Line numbers are
`a7abc155`'s, before Phase 0's edits (which add a few lines near the top of `build.py`, and the seam this table says
is missing). Two rows changed: application-core is done, and VF-023 is closed; the rest moved only in line numbers,
some of which were already off at `210b9498`.

| Finding | Evidence | Consequence |
|---|---|---|
| **Real-world examples are refused by the runner.** | `build.py`'s `not_executable()` (`examples/tools/build.py:306-310`): "its report is its README.md, and build.py has no adapter for its project's build". Running all skips them (`:259`); naming one exits 1 (`:261-266`, `:289`). `--render-only` refuses them (`:232-235`). | The new route replaces the refusal only for an example with a target sidecar. The others keep it. |
| **`--plan` is pure.** | `plan()` (`build.py:336-393`): nothing is built, copied or run. Real-world ids appear with `executable: false` and a reason. `plan()`'s adapter is gradle or javac only (`:389`). | `TaskPlan` extends `plan()`; it is the same plan the runner executes and the pipeline submits. |
| **Dependencies are declared, not hashed.** | `claim_record()` (`build.py:764-782`) hashes the patch and the copied trees; dependencies are the string "declared in the build files" or "the JDK" (`:775`), with "the artifacts themselves are not fingerprinted" (`:773-774`). Tools: `attempt_tools()` `:864-887`. There is no Maven path at all. | Bind attempts to the actual JARs, classpath order, JDK and adapter/oracle identities, through the existing claim record. |
| **The pipeline refuses real-world examples before planning.** | `verification/pipeline.py:1585-1587`, before `example_plan()` (`:1588`); tested at `verification/test_pipeline.py:428`. | `submit --example NNN --task T` consumes the same task plan. |
| **The index uses authored labels for real-world examples.** | `render_index()` (`build.py:4448`) takes `verdictLabel` (`:4465`) and writes `verdict: None` (`:4475`); `example.schema.json:115-116` requires `source` and `verdictLabel` for them. | Historical labels stay historical; a new receipt is shown beside them, never instead. |
| **Format 2 exists, with evidence checked before publication.** | `result_format.py` `FORMAT = 2` (`:37`), `pack()` (`:81-98`); `check_result()` (`build.py:958-969`) validates the flat view, the round trip, the stored format and the bundle's sha256s before `publish()` (`:979+`). 45 stored results are format 2, 112 format 1. | One format-2 receipt per task and attempt. No new format. |
| **Authored metadata is closed and has no locks.** | `example.schema.json`: `source` is `{kind, repository, url}` (`:56-64`), `additionalProperties: false` at the top (`:8`) and on every nested object. No commit field, hash, lock or build info. | A sidecar reference is a schema change, made once: Phase 0 added `example.json`'s optional `target`. |
| **Five real-world examples, all handwritten.** | 105 (commons-numbers `pow`, all three conclusions positive), 106 (commons-lang `reverse`), 107 (commons-lang `subarray`, mixed: one property ⚠ unverifiable), 108 (jackson-core, unresolved), 109 (commons-codec `Hex.toDigit`, new version ✓, old-version regression ⚠ needs a `Character.digit` model, replay limits on `StandardCharsets.UTF_8` and locale-dependent `String.format`). Each has only `example.json` and `README.md`. | 105 is the calibration migration; 106 its documented fallback. 107–109 stay visible as they are. |
| **A one-sided replay no longer counts as reproduced.** | The outside review attributed this to example 109's record; it is VF-015's step 4, job `20261108-024648` (`findings.md:196-200`). Fixed after `57f04e55`: `witness::differences` is empty when either side couldn't replay (`lib/src/witness.rs:812-820`, test `:1094`), `equivalence.rs:584-591` and `:2278-2281`; documented at `lib/README.md:250`. | Rely on it, and keep separate-JVM replay of both sides as the oracle path. VF-015's own remaining work stays deferred by the user. |
| **No fix command; JBMC is the CLI default.** | `lib/src/main.rs`: `Equivalence` `:40`, `Prove` `:96`, no `fix`; `engine` defaults to `jbmc` (`:592`, `:737`, `:359`), `gaps` to `strict` (`:604`, `:749`, `:362`). | Repair is composed in the target layer from separate tasks; native is always requested explicitly. |
| **No external-target code yet, but the seam is planned.** | No `target.json`, `TaskPlan`, `PreparedTarget` or lock anywhere. `build-orchestration.md:599-604` defers "4c. External artifacts as inputs", with "whether dependencies may be downloaded" left to the user (`:90-92`). | This brief is 4c. The user settled downloads ([decision 1](#decisions)). Phase 0 added the seam ([below](#phase-0-interfaces-hooks-and-fixtures)). |
| **Example numbers are reserved only in briefs.** | `application-core.md:299-304` (230–279), `cleanup.md:154-158` (197–229). The highest folder is 196; 197–279 are unused. Nothing in `examples/README.md` or `tags.json`. | This brief reserves 280–329 ([Streams](#streams)); Phase 0 recorded it in `examples/README.md`. |
| **The machine.** | Temurin JDKs from sdkman under `~/.sdkman/candidates/java/`: `25.0.5.0+8-tem` (the default, `Temurin-25.0.5+8`), `21.0.13.0+9-tem`, and, installed by the planning session on 2026-11-08, `17.0.21.0+9-tem` (`Temurin-17.0.21+9`), `11.0.33.0+10-tem` (`Temurin-11.0.33+10`) and `8.0.512.0+9-tem` (`1.8.0_512-b09`); also GraalVM CE 25, Maven 3.10.0, Gradle 9.8.2 and `/usr/bin/jbmc`. No `~/.m2`. Jobs have cloned from github.com (VF-015's job); nothing has used Maven Central. Jobs run in systemd user scopes with memory caps and no network restriction (`verification/README.md:201`). | Every JDK an upstream build of this portfolio needs is present ([decision 3](#decisions)), and none changes the default. |
| **Application-core is done** (its final job `20261108-214557` passed at `47358229`; `application-core.md:1606-1619`). Under `--engine native --gaps strict`: a **String** parameter of a regression check is bounded UTF-16 with content, never null (`length`, `isEmpty`, `charAt`, `equals`, `startsWith`, concatenation), and refused in a property check, as a result, as a plan root, null, or in a `List<String>`; a **list** only from `List.of`/`copyOf`, at most 10 elements of one application class built from primitives, with `contains`, `indexOf`, `equals` and `hashCode` gaps; a **receiver** made by its one usable constructor or a `--plan`, an application-interface dependency passed null (refused if reached); **environment** outcomes through `CallModel` and DTO plans (`lib/README.md:230-236`, `:318-324`, `:352-362`). Regex, locale-dependent methods and reflection are outside the interpreter (`:210`, `:405-410`), `invokeinterface` dispatches only to application methods, an enum or static initializer only inside the fragment (`:334`), no floating point. | VF-023 is closed; open: VF-020, VF-018, VF-015 (deferred by the user), VF-002. Spring's regex (BCrypt hash validation, `RegexRequestMatcher`), `toLowerCase` locale, `HttpServletRequest` interfaces and enum initializers are where the packets' probes will likely stop: each is a prediction until a probe reaches it. Whether real Spring code stays in the fragment takes a queued probe, never an inline proof. |

Side finding for the coordinator: `result.schema.json`'s `claim.inputs` was closed with no `contracts` property, though
`build.py`'s `claim_record()` writes one under `--gaps advised`, so an advised example's claim (147, 148) would have
failed `check_result` once VF-002 lets it reach one. Phase 0 step 3 touched that block, and added it (`lrxtyuux`).

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
   exited. Shared files (`build.py`, `pipeline.py`, the schemas) are touched only after that. *Done: `a7abc155`,
   2026-11-08.*
2. **The baseline recounted** at that commit: [Where it starts from](#where-it-starts-from) updated, application-core's
   delivered capabilities probed on the String, list, receiver and environment cases these packets need, and the
   integration contracts run inline. *Done 2026-11-09: the table's application-core row says what the native checker
   supports and refuses for each, from its brief and `lib/README.md` (no proof was run inline); application-core's
   Python suites pass, and its cargo suites, last run by its final job, weren't rerun.*
3. **The inputs committed**: `example-targets-inputs/seeds.json`, and the archived registry with its sha256 checked
   against `e86301abe767bcd9c39c5c9dc8889dfcbb1c22bb45bead53fc630acd0b9c62e5` (the user supplies the file). *Done:
   `tspropkox` and `xuzwwrwx`.*
4. **Phase 0** ([below](#phase-0-interfaces-hooks-and-fixtures)), committed. *Done 2026-11-09.*
5. **The names**: `example-targets` and `example-targets-STREAM` in `feature-loop.sh` (refusing
   `example-targets-acceptance` and `example-targets-sources`, which aren't briefs), `example-targets` with its four
   streams in `run-streams.sh`, and the integration check `llm-dlc/tools/example-targets-integration.sh`. Both
   launchers are replaced by rename if anything runs from them. *Done in Phase 0 step 6.*
6. **The briefs committed** with their session ids (done 2026-11-08, in the workspace `example-targets-plan`, rebased onto
   application-core's final commit on 2026-11-09, and that workspace forgotten), and the [decisions](#decisions)
   settled by the user (done 2026-11-08).
7. **Push**, at the user's request.
8. **This brief's status set to `working`**, and the planning session closed. The user then runs
   `FEATURE_LOOP_MEMORY_MAX=12G CARGO_BUILD_JOBS=8 llm-dlc/tools/run-streams.sh example-targets` from the default
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

**Done 2026-11-09**, one commit per step: `ptroqoqm` (1), `quzmrkzx` (2), `lrxtyuux` (3), `ynzpqxsv` (4), `pqulqqlx`
(5), and step 6's commit. What the streams build against:
- **The sidecar**: [`examples/schema/target.schema.json`](../../examples/schema/target.schema.json) (`example-target/v1`)
  and [`examples/tools/targets/sidecar.py`](../../examples/tools/targets/sidecar.py), which checks what the schema
  can't (paths inside the folder, links included; defined revisions, pairs and tasks; unique ids; no prerequisite
  cycle; no mutable version). `example.json`'s optional `target` is always `target.json`, real-world only, and
  `build.py`'s `load_example()` checks the sidecar whenever an example is read. A task may state `allowedChange` (the
  inputs a preservation task leaves out); a replay names a revision or a pair; a `control` may use fixture revisions.
- **The interfaces**: [`interfaces.py`](../../examples/tools/targets/interfaces.py) freezes `TaskPlan` (with `folder`,
  and `artifacts` entries of the `ARTIFACT_SOURCE` shape), `PreparedTarget`, `ExecutionRecord`, `Receipt` and
  `Unsupported`, and the functions `workflow.plan_task`, `ingest`, `handoff` and `project`, and `runtime.prepare`,
  `run_controls` and `run_verifier`. Each stub returns `Unsupported` naming its stream, its reason saying "Phase 0's
  stub". `test_interfaces.py` freezes signatures and field order: a field added later needs a default.
- **The hooks**: `build.py --plan NNN --task T`, `build.py NNN --task T` and `pipeline.py submit --example NNN --task
  T`, all through [`route.py`](../../examples/tools/targets/route.py), which stops at the first `Unsupported`; the
  index's `target` projection and `find.py --family/--role/--readiness/--claim-status/--gap`; `result.schema.json`'s
  `claim.target`, `inputs.dependencies: pinned in target.dependencies`, a null patch only with a target, and `records/`
  bundle paths. Old receipts stay valid (all 157 checked).
- **The fixtures**: [`examples/tools/targets/fixtures/`](../../examples/tools/targets/fixtures/README.md), a
  two-revision `int` fixture with a mutant and a regex capability refusal, deterministic JARs, recorded JVM controls on
  JDK 21 and 25, a recorded `jvmcontract gaps` refusal, and constructed bad runs and receipts.
- **The contract**: [`examples/tools/test_targets_contract.py`](../../examples/tools/test_targets_contract.py), rows A0,
  A1, A2, A3/A4 and A5 on the fixture, A6 and A7. At Phase 0's end, A0's three tests pass and the other 13 stop at their
  stream's stub.

## Streams

| Loop | Brief | jj workspace | Owns |
|---|---|---|---|
| `example-targets-runtime` | [`example-targets-runtime.md`](example-targets-runtime.md) | `example-targets-runtime` | `examples/tools/targets/runtime*`, `test_runtime.py` and further tests and fixtures of its own |
| `example-targets-negative` | [`example-targets-negative.md`](example-targets-negative.md) | `example-targets-negative` | the catalog folders and the three negative packets: their source records, local adapters, oracles, probes and notes |
| `example-targets-positive` | [`example-targets-positive.md`](example-targets-positive.md) | `example-targets-positive` | the three positive packets, their mutation controls, the optional control, and 105's migration data |
| `example-targets-workflow` | [`example-targets-workflow.md`](example-targets-workflow.md) | `example-targets-workflow` | `examples/tools/targets/workflow*`, the sidecar schema and `sidecar.py` after Phase 0, `test_workflow.py`, `test_sidecar.py` and its other tests |
| `example-targets` | this brief | `default` | Phase 0, the merge, Phase 5 and the joint acceptance |

**Runtime produces evidence; workflow classifies it.** Case streams write no downloaders or parsers of their own.

**Shared files have one writer** ([decision 6](#decisions)): the planning session, in Phase 0, writes `build.py`,
`pipeline.py`, `result_format.py`, the shared schemas, `find.py`, `examples/tags.json`, the generated indexes, the
launchers and the integration script, and also `targets/interfaces.py`, `targets/route.py`, their tests, the fixtures
and the contract test. While the streams run, none of them edits these, with one exception: workflow may add the
fixture's claim files (`fixtures/claims/`) and the `claim` keys in `fixtures/target.json` that refer to them. A stream that needs a change
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
   example-targets-workflow@-`, then run `python3 llm-dlc/tools/sync.py regenerate`, which settles the generated trace
   files' conflicts and lists any other (exit 1). Resolve those, and commit. Commits only a stream's line held are
   checked here once merged: `check` reads the history of `@`, so the streams' "has no manifest" errors end with the
   merge.
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
   **Extended by the user on 2026-11-14**, answering the positive stream's question on P1's and P3's build route (its
   option (a)): **repo.spring.io, services.gradle.org and plugins.gradle.org** are allowed too, under the same
   hash-pinned acquisition (a SNAPSHOT is a mutable reference and stays refused). This gives P3 (307) its pinned upstream
   build (Gradle 5.5.1, repo.spring.io/plugins-snapshot's plugins, plugins.gradle.org, the 5.2.0.RC1 milestone). It
   doesn't make P1's (305) exact-commit build reproducible, since both its commits pin SNAPSHOT versions: P1 stays
   without an upstream build route, recorded as that blocker, never counted as a success; its published-artifact
   evidence (2.2.0.RELEASE carries after's class) stands as it is. The runtime stream's `runtime_maven.py` allows only
   Central and github.com (`HOSTS`, `REDIRECT_HOSTS`): widening it is a merge-time item (Progress).
   **Extended again by the user on 2026-11-14**, after the merge found P3's build plugin behind repo.spring.io's
   login: **maven.aliyun.com** (Alibaba Cloud's anonymous mirror of Spring's plugin repository) is allowed too, with
   the same hash-pinned acquisition, for P3's four Spring Gradle plugins. No independent hash of them exists, so P3's
   build job also compares the `before` `BCrypt.class` it builds with Spring Security 5.2.0.M4's published one. P1
   (305) takes the narrower slice instead, checked against Boot 2.2.0.M6's published classes (Progress, the user's
   decisions of 2026-11-14).
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
- 2026-11-09, **Phase 0 done** by the planning session, after application-core's final commit `a7abc155`, onto which the
  drafted commits were rebased (the `example-targets-plan` workspace forgotten; its directory is the user's to delete).
  The baseline was recounted (application-core done, VF-023 closed, line numbers moved), with a subagent's read-only
  report and no proof run. Six commits, listed under [Phase 0](#phase-0-interfaces-hooks-and-fixtures). Step 1 broke
  `verification/test_pipeline.py`'s stub repo, which didn't copy `examples/tools/targets/`, and step 3 fixed it. The
  integration script passes on the default workspace: the contract (3 pass, 13 stop at their stubs), the targets suite
  (41), `test_build.py` (190), `test_pipeline.py` (29) and every sidecar validated. For review: the fixture's
  `example.json` says `origin: real-world` only because the route takes one; its sidecar's role is `control`. The
  recorded gap scan used a `jvmcontract` built before application-core's last `lib/src` change (noted in the
  fixtures' README).
- 2026-11-14, **pushed** (prerequisite 7, `xsusnqss`). The VM was resized to 30 vCPUs and 105 GiB, so each loop's cap
  is now 12G (the four streams' `- memory:`, this brief's, and the launch command), up from 4G, which OOM-killed
  processes 8 times during application-core; the integration check's scope is 6G (`run-streams.sh`).
- 2026-11-14, **decision 1 extended by the user** (see [Decisions](#decisions)): repo.spring.io, services.gradle.org and
  plugins.gradle.org are allowed, hash-pinned. At the merge: widen `runtime_maven.py`'s `HOSTS` and `REDIRECT_HOSTS` to
  them, with a test that any other host is still refused; then prepare P3 (307) by its pinned upstream build, as a job.
  P1 (305) stays blocked on its SNAPSHOT pins. The positive stream finished `done` before the decision, so this falls to
  this loop.
- 2026-11-14, **the reconcile, steps 1–3 done; step 4, the merge, needs the user** (nothing merged or committed here).
  - **Step 1**: all four streams finished `done`: runtime at `qrsyzzwu`, negative `zuoknpln`, positive `uzxpwmku`,
    workflow `nqztmpwy`. No stream scope or integration scope was active, and no job was pending.
  - **Steps 2–3**: each stream's last turns are recorded on its branch (`Record session traces`: runtime `xvvuxmqs`,
    negative `mqnnxzkt`, positive `kxqozyus`, workflow `svrtnrlo`), and their 35 logs not yet here were copied in.
    Negative's commit also carries the 8 allow-list proposals its last turn left uncommitted. Each of those commits
    reported 34–42 "session … has no manifest" errors, from the workspaces' old `sync.py`, before `xyootzvm`; they end
    with the merge.
  - **Step 4 needs the user.** `jj new @- example-targets-{runtime,negative,positive,workflow}@-` followed by
    `sync.py regenerate` leaves one conflict, `llm-dlc/allowlist.json`. Positive (`vwsxyvlr`) added 15 proposals and
    negative 8, all to the same base of 23. Their union has 46 entries, and no id differs between the sides. Writing
    the file is refused to this loop, and so is taking one side with `jj restore`, which was denied as undermining
    oversight. The merge was therefore backed out, uncommitted. **The user's options**: resolve that one file in the
    merge (the union, or positive's side, after which this loop re-proposes negative's 8 with `sync.py allow propose`,
    giving the same reasons), then let this loop commit the merge; or allow this loop to resolve such a conflict.
  - **The merged tree, checked before backing out**: `example-targets-integration.sh` passes everything but contract
    A5: the targets suite (181), `test_build.py` (190), `test_pipeline.py` (29), every sidecar's plan, and contract rows
    A0–A4, A6 and A7. The trial merge's 3 runtime×workflow errors are gone. A5 fails because all four fixture proof
    tasks come back `unresolved`: the claims say `code`, but the fixture's classes record no parameter names (`arg0`).
    This is VF-024's first point, reached now that the route runs end to end. Runtime asked for the fix as an
    interface request: compile Phase 0's fixture recipe with `-parameters` (`runtime_calibrate.py`'s
    `--fixture-javac-flag`). It is Phase 5 step 1's first item after the merge, with A5 as its reproducer.
  - **Next**: commit the merge (step 4); fold the streams' Progress, deferrals and interface requests here (step 5);
    forget the five workspaces (step 6); then Phase 5, starting with the fixture recipe and A5, and runtime's
    `runtime_maven.py` hosts for P3.
- 2026-11-14, **the reconcile, step 4 done: the streams merged** (this commit, a merge of the default line and the four
  streams' record commits `xvvuxmqs`, `mqnnxzkt`, `kxqozyus`, `svrtnrlo`).
  - **The user's decision**: they allowed this loop, and future ones, to resolve this kind of conflict, now an
    exception in `CLAUDE.md`'s allow-list rule. For this merge they chose positive's side.
  - **The resolution**: `jj restore --from example-targets-positive@- llm-dlc/allowlist.json` gave positive's 38
    entries (23 approved, 15 proposed). Negative's 8 were then re-proposed with `sync.py allow propose`, giving their
    original reasons: 7 bcrypt test hashes of example 287's probes, and dd2fcadc, Spring Security's public test
    vector. The file now has the same 46 ids as the union, with every approved entry unchanged. All 23 proposals
    still wait for a person's `sync.py allow approve`. `sync.py regenerate` resolved the four generated files.
  - **Checked on the merge**: `example-targets-integration.sh` gives the same result as on the trial merge. The
    targets suite (181), `test_build.py` (190), `test_pipeline.py` (29), `build.py --plan` and contract rows A0–A4,
    A6 and A7 all pass. Only A5 fails, on VF-024's parameter names, so the script exits 1 until Phase 5 step 1.
  - **Next**: fold the streams' Progress, deferrals and interface requests here (step 5); forget the five workspaces
    (step 6); then Phase 5, starting with the fixture recipe's `-parameters` and contract A5, and runtime's
    `runtime_maven.py` hosts for P3.
- 2026-11-14, **the reconcile, steps 5–6 done: the streams' Progress folded here, the workspaces forgotten.**
  - **Step 6**: the workspaces `example-targets-runtime`, `-negative`, `-positive`, `-workflow` and `-integration`
    are forgotten. Their directories, `../in-the-loop-example-targets-*`, are the user's to delete. The integration
    workspace's `@` was an empty trial-merge revision, still conflicted, so nothing is lost with it.
  - **Deferred by the timebox**: none, in any stream. No blocker was attempted by a verifier on a real packet, so
    every gap in the case packets is still `observed: false` ("Predicted ..."). **Deferred for the user**: the
    positive stream's build-route question for P1 (305) and P3 (307), answered by decision 1's extension (above).
    P1 stays without an upstream build, on its SNAPSHOT pins. P4, the optional `d676147` control, wasn't done.
  - **Interface requests that waited for the merge**, Phase 5 step 1's work, grouped by the owner of the file
    (each checked against the merged code on 2026-11-14 and still open):
    1. **The fixture recipe** (coordinator's `fixtures/build_fixtures.py`): `JAVAC_FLAGS = ("-parameters",)`, so the
       fixture classes keep the parameter names the sidecar (`code == 97`) and the claim files (`code`, RegexGate's
       `field`) use. Runtime's `_fixture_recipe()` already reads an optional `JAVAC_FLAGS`. The fixture JARs'
       hashes change, and the recorded controls and the gap scan with them. Contract A5 is its reproducer
       (runtime, VF-024's closure covered the recipe with `-parameters`, not Phase 0's bytes).
    2. **The download hosts** (runtime's `runtime_maven.py`): widen `HOSTS` and `REDIRECT_HOSTS` to repo.spring.io,
       services.gradle.org and plugins.gradle.org (decision 1's extension), with a test that any other host is
       still refused. Runtime's Gradle `toolchain` blocker ("outside the downloads policy") goes with it. Then P3
       (307) by its pinned upstream build, as a job.
    3. **Constructed mutants as revisions** (the six packets' sidecars; negative's and positive's request 1, settled
       on the other branches: workflow's W1 `mutant` revision kind, `zvnrtxsu`, and runtime's preparation of it on all
       three routes, `wkkwovlz`). 285, 286, 287, 305, 306 and 307 still declare their mutant as a `controls` entry of
       kind `mutation`. Each becomes a W1 `mutant`, the `after` of a `mutation` pair over its base, with a task and
       claim key of its own. Runtime's slice `runtime_simplematch/mutation.json` moves into its `target.json` the same
       way, and 306's `drop-prefix.patch` gives A4 its nearby mutation.
    4. **The router** (coordinator's generated files; negative's and positive's request 2): `build.py --index-only`,
       so `examples/README.md` and `index.json` list 285–300 and 305–307. The index has none of them today.
    5. **Readiness in the index** (workflow's `workflow_discovery.py` and the coordinator's `test_route.py:132`): set
       `READINESS_IN_INDEX = True` and change that test's expected `None` to `"catalogued"`. Until then
       `find.py --readiness` matches nothing.
    6. **Companions** (positive's request 3): link 305–307 to 285–287.
    7. **Interfaces, additive** (coordinator's `interfaces.py`, runtime's requests): `PreparedTarget.workdir:
       Optional[str] = None`, kept out of `source`, so that `run_controls` and ingestion stop deriving the
       preparation from `route.py`'s layout. Ingestion bundles no raw stdout and stderr until it has it (workflow's
       request). And `PreparedTarget.blocker: Optional[Mapping] = None`, for the blocker now in `source.blocker`.
    8. **The result schema** (coordinator's `result.schema.json`, workflow's requests): allow `existingTests` and
       `before`/`after` to be null when `claim.target` is present. Until then a target receipt writes "none: a target
       task's attempt runs no module tests" with `passed: false`, which nothing may read as a test failure. Also,
       `claim.target.revisions`' description should say a fixture revision's id is its source tree's, and a mutant's
       its base's.
    9. **A driver's invocation** (negative's request 3): a field or convention for a `driver` control's main class,
       its arguments (`controls/oracle.py argv`) and the oracle's `check(lines)` and `compare(before, after)`.
       Runtime's lock names the main class and runs the oracle's `PROBES`, which doesn't match 285–287's entry
       points; to be confirmed when 285 is prepared.
    10. **Smaller ones**: a verifier record's `identities.commit` (the `lib/` commit of the binary), so a packet stops
        listing `verifier.commit` as missing; a claim-schema key for an adapter entry point (the verifier can't go
        through an adapter yet, so such a task needs `--plan` or stays a gap); the handoff beside `--plan` in
        `build.py` or `find.py`, and `find.py` matching a task's readiness (both optional); the fixtures README
        listing `claims/`.
    11. **VF-025** (`.gitignore`, the user's or this loop's): ignore `runtime-mutant/**/spring-core-5.3.19.jar`, or
        decide jj's 1 MiB limit together with VF-020. Later runtime jobs should delete `prepare/*/lib/` in cleanup.
  - **The case packets at the merge, by the streams' accounts**, all source-locked and none prepared, replayed or
    probed by a job (every run was a developer note on Temurin 21 and 25):
    - negative: the catalog 285–300 (16 CVEs, 301–304 free) checked against upstream; 285 (4 tasks, 15 probes), 286
      (6 tasks, 46 probes, `Locale.ROOT`) and 287 (6 tasks, 33 probes against 9 independent pyca hashes) ready for
      preparation by the published-artifact route; 300 research-only, its 6.3.9 policy a proposed contract;
    - positive: 306 complete (40 probes, spring-core 5.3.6/5.3.7 published, the A4 candidate); 305 partial (no
      upstream build); 307 partial (45 probes, the UTF-8 conversion lemma not written, its upstream build now
      allowed); 105 migrated (`pow-minus-two.json` for A5, 75 probes, `PowDriver.java`), its upstream Maven build of
      each commit on JDK 11 predicted to need Central only, with 106 an unused fallback. Its claims were checked
      against a copy of workflow's W1 before the merge, so they are rechecked on the merged planner;
    - runtime: R1–R5 done; five jobs, all collected, the last four passed (`20261114-164239`, `-170353`,
      `-174017`, `-180443`); VF-024 closed, VF-025 open;
    - workflow: W1–W4 done, no jobs; A1, A6 and A7 pass on the fixture and wait for real packets. Over the merged
      sidecars, every gap group of the inventory is predicted, none observed.
  - **Found by the streams, for the for-review list** (each in its stream's Progress, with lines):
    - runtime: a killed record's `exitCode` is `-9` in `build.py` but `None` in `bad-runs.json`; no POM is resolved,
      so the dependency closure is what the lock declares; `PatternMatchUtils.class` is byte-identical in 5.3.18 and
      5.3.19 (CVE-2022-22968's fix is in `DataBinder`); regex-probe's refusal is named by the probe, not a proof; no
      checkout or build cache; the published route's commit-to-JAR link is recorded, not checked;
    - negative: 285's frozen labels are version-specific and a null `getMethod()` is outside its domain; 286's
      final-sigma and `tr-TR` behaviour of 5.3.19; 287's 25 lone surrogates match 25 `?`, a cost-31 stored hash
      never terminates, and 6.3.8 locks out stored long passwords; 300's possible non-timing distinguisher on 6.3.8,
      read from source, not run;
    - positive: 305's mutant satisfies the finite-outcome property by design, and a range property can't be stated
      through the response parameter; 307's gap scan refuses the changed conversion itself;
    - workflow: a replay's expectation comes from its pair's kind, as the sidecar states none per revision;
      `build_fixtures.py` compiles RegexGate into every revision's JAR, outside the tree id; `partial` beats
      `blocked` in a target's summary.
  - **Checked**: `sync.py check` reports 0 errors at the merge, so the streams' "has no manifest" errors are gone,
    as expected. Each open request above was checked against the merged code (`HOSTS`, `READINESS_IN_INDEX`,
    `build_fixtures.py`, `examples/index.json`, the six sidecars' mutants, `result.schema.json`).
  - **Next**: Phase 5 step 1's requests, in the order above, each a cycle with its reproducer: first the fixture
    recipe, which makes contract A5 pass, then the hosts.
- 2026-11-14, **Phase 5 step 1, request 1 done: the fixture recipe records parameter names**, and contract A5
  passes.
  - **Reproducer**: on the merge, `test_targets_contract.py`'s A5 failed: `fixed-security` came back `unresolved`,
    not `established`, because the claims say `code` and the classes recorded only `arg0`.
  - **The fix**: `build_fixtures.py` has `JAVAC_FLAGS = ("-parameters",)` and records the flags in its manifest.
    `runtime.py`'s fixture route already read them; its toolchain record's `build.flags` now lists them too, where it
    used to omit them. `make_records.py` remade `records/`: every fixture JAR's sha256 changed, and nothing else did.
    The controls' outputs and oracle verdicts are the same on JDK 21 and 25, and the gap scan names the same three
    regex calls.
  - **Tests**: three runtime tests had pinned the old bytes, and now expect the new ones:
    - the verifier's scope says `code` from `MethodParameters`;
    - the flags test now builds its no-names variant with the flags taken away, and checks that variant's `arg0`
      scope, which had lost its only test;
    - the published-route mutant recompiles with `-parameters`, since it copies the base classes' `MethodParameters`.
      It still gives `build_fixtures.py`'s own mutant bytes.
  - **Documentation**: `runtime_calibrate.py`'s docstring is updated. The fixtures README now has the flag, the
    remade records and a `claims/` row, which covers request 10's README item.
  - **Checked**: `example-targets-integration.sh` exits 0:
    - the contract's 16 tests all pass and none stops at a stub, so the fixture's A0–A7 rows pass;
    - the targets suite (181), `test_build.py` (190), `test_pipeline.py` (29) and `build.py --plan` all pass.
  - **A caveat**: the contract's A5 proofs ran on `lib/target/release/jvmcontract` (sha256 `7462d0c9…`), built on
    2026-11-08 before `yrlkzqvw`, as the fixtures README says. Tier A's A5 proper is example 105's calibration
    (Phase 5 step 2), and it runs as a job, which builds its own binary from `lib/`.
  - **Next**: request 2, the download hosts in `runtime_maven.py`, with a test that other hosts are still refused;
    then P3 (307)'s pinned upstream build, as a job.
- 2026-11-14, **Phase 5 step 1, request 2 done: the download hosts widened.** P3 (307)'s upstream build isn't queued,
  because its build plugin is behind credentials.
  - **Reproducer**: a new test, `test_the_three_hosts_decision_1s_extension_allows_and_no_other`, failed on the merge.
    `allowed()` refused a repo.spring.io URL.
  - **The fix**: `runtime_maven.HOSTS` now holds Central, github.com, repo.spring.io, services.gradle.org and
    plugins.gradle.org. `REDIRECT_HOSTS` adds only github.com's two content hosts, as before. The refusal messages
    name the five hosts (`HOST_NAMES`). The test also checks what stays refused:
    - other hosts and look-alikes: `repo.spring.io.example.org`, spring.io, gradle.org and jcenter;
    - the Gradle CDNs, downloads.gradle.org and plugins-artifacts.gradle.org, neither allowed nor followed as a
      redirect;
    - http, a user name or a port in the URL;
    - a SNAPSHOT on repo.spring.io.
  - **What wasn't done, and why**: the Gradle route. Runtime's Gradle blocker no longer cites the policy, but it
    stays a blocker that now says what is missing: no Gradle route yet. Such a route would fetch the wrapper's
    distribution by sha256, hold the build's repositories to `HOSTS` with an init script, and hash every file the
    build resolves. A distribution on any other host still blocks as outside the policy (new test). The route wasn't
    built because its one user can't use it:
    - **P3 (307)**: HEAD requests on 2026-11-14 found `io.spring.gradle:spring-build-conventions:0.0.23.RELEASE`, its
      buildscript plugin, on no anonymous repository:
      - repo.spring.io's plugins-snapshot, plugins-release, release, libs-release and libs-milestone answer 401;
      - its milestone and snapshot repositories answer 404;
      - plugins.gradle.org redirects (303) to Maven Central, which answers 404.
      Boot's 2.2.0.M3 plugin and spring-jcl 5.2.0.RC1 are on repo.spring.io/milestone (200). services.gradle.org
      redirects the 5.5.1 distribution to github.com, and its `.sha256` to downloads.gradle.org. So a build job would
      stop at its buildscript.
    - **307's records**: its target.json blocker (still `observed: false`: no build ran), handoff, notes and README now
      say this. They name the alternative: the extracted-source slice, each commit's `BCrypt.java` compiled alone,
      with a narrower claim of its own.
    - **305**: its blocker's "even if decision 1 were extended" now reads "even with decision 1's extension". P1 stays
      blocked on its SNAPSHOT pins.
  - **For the for-review list**: whether repo.spring.io credentials or the 307 slice is wanted. The user decides;
    neither is in this loop. Until then, P3 is delivered partial at "source locked".
  - **Checked**: `example-targets-integration.sh` exits 0. The contract (16), the targets suite (183, two of them
    new), `test_build.py` (190), `test_pipeline.py` (29) and `build.py --plan` all pass.
  - **Next**: request 3, the six packets' constructed mutants as W1 `mutant` revisions (285–287, 305–307), with
    runtime's `runtime_simplematch/mutation.json` moved into its target.json.
- 2026-11-14, **Phase 5 step 1, request 3 done: the constructed mutants are revisions.**
  - **Reproducer**: a new test, `examples/tools/targets/test_packets.py`, failed on the six packets and on the slice.
    No packet had a `mutant` revision, a `mutation` pair or a mutant task. The slice still had its `mutation.json`.
  - **The change**: each packet's `controls` patch is now W1's revision `mutant`. Its base is the old control's
    revision (`fixed-release` for 285–287, `after` for 305 and 307, `release-after` for 306). The patch's sha256 is
    unchanged, and each revision says in words what it breaks. Each packet also gains:
    - a `mutation` pair, from the base to `mutant`;
    - `mutant-replay`, the concrete controls on that pair, where the base must hold and the mutant fail (ingestion's
      expectation for a mutation pair);
    - a claim task, expected `refuted`: `mutant-security` (285–287, `fixed-security`'s claim file on the mutant) or
      `mutant-preservation` (305–307, `preservation`'s claim over the mutation pair). 306's is gate A4's "nearby
      constructed mutation fails the same claim and control".

    The `mutation` control stays, now on the revision `mutant`, as in the fixture. The source-level claim key is the
    reference task's (one property). The attempt's inputs differ, and runtime binds the claim to
    `mutant:<base commit>+<patch sha256>`.
  - **Side effect**: the patch is no longer among `fixed-security`'s controls (285–287) or `replay`'s (305–307). So
    those plans' input keys changed, and `replay`'s claim key too for 305–307. No packet has a receipt, so nothing went
    stale.
  - **The slice**: `runtime_simplematch/mutation.json` moved into its `target.json` unchanged. `runtime_slice.py` no
    longer merges it.
  - **Docs**: each packet's README lists the two tasks (and, for 285–287, the `mutant` revision). Each `example.json`
    has a note. The slice's README is updated.
  - **For review**: 287's `mutant-security` reaches only the multibyte triggers. The unguarded byte entry is
    `fixed-guard`'s target, so no task states a mutant claim on it.
  - **Checked**:
    - `example-targets-integration.sh` exits 0: the contract (16), the targets suite (187, four new), `test_build.py`
      (190), `test_pipeline.py` (29) and `build.py --plan`;
    - `build.py --plan` gives an executable plan for 306 `mutant-preservation`, 285 `mutant-security` and 307
      `mutant-replay`.

    No mutant was prepared: those are Phase 5's packet jobs.
  - **Next**: request 4, `build.py --index-only`, so the router lists 285–300 and 305–307.
- 2026-11-14, **Phase 5 step 1, request 4 done: the router lists the packets.**
  - **Reproducer**: a new test, `test_packets.py`'s `RouterTest`, failed for 19 folders, 285–300 and 305–307. It
    checks that `examples/index.json` and `examples/README.md`'s table list every numbered folder, that each sidecar
    example's entry has a `target` projection, and that the six packets' roles are negative or positive.
  - **The change**: `build.py --index-only` regenerated both files. Nothing else changed:
    - the 19 folders gained rows, tag links and index entries;
    - 105's entry gained its migration notes and its `target` projection (role `calibration`). Its historical
      `verdictLabel` stays as it was;
    - no other entry changed.

    `find.py --family spring-data-binding` now finds 286, 288, 299 and 306, and `--role positive` finds 305–307.
    `--readiness` still matches nothing, as every projection's `readiness` is `null` until request 5.
  - **Found, for request 6** (the companions, which edits 305–307's `example.json` anyway):
    - the `external-target` tag lists 285–300 only, not 105 or 305–307, though all four have a sidecar;
    - 306 is tagged `request-binding`, whose description is a handler parameter that can't bind. `PatternMatchUtils`
      is closer to `data-binding`, the tag 286, 288 and 299 use.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (188, one new),
    `test_build.py` (190), `test_pipeline.py` (29) and `build.py --plan`.
  - **Next**: request 5, `READINESS_IN_INDEX = True` in `workflow_discovery.py`, with `test_route.py:132` expecting
    `"catalogued"`, then the index regenerated again.
- 2026-11-14, **Phase 5 step 1, request 5 done: the index carries each target's readiness.**
  - **Reproducer**: a new test, `test_packets.py`'s `test_every_target_projection_carries_its_readiness`, failed for
    all 20 sidecar examples (105, 285–300, 305–307): each projection's `readiness` was null, with the `unsupported`
    hold.
  - **The change**: `workflow_discovery.READINESS_IN_INDEX = True`, its comment and docstring updated.
    - `test_route.py`'s `IndexAndFindTest` now expects the stub sidecar's readiness to be `"catalogued"`. It also
      checks that `find.py --readiness catalogued` finds it, and that `blocked` still matches nothing.
    - `test_workflow.py`'s two tests that assumed the flag was off now take the projection as the default. They keep
      the hold as the flag-off case: `readiness` null, `unsupported` set, and `find --readiness` matching nothing.
    - `build.py --index-only` regenerated `examples/index.json`. Only each target's `readiness` changed, and the
      `unsupported` line went.
  - **What the index now says**: the 13 catalog entries (288–300) are `catalogued`. The six deep packets and 105 are
    `partial`, as is each of their tasks, since nothing is prepared yet. `find.py --readiness catalogued --limit 50`
    finds the 13; the default `--limit 10` shows the first ten. Nothing is `scaffolded`, `executable` or `blocked`
    until Phase 5's packet jobs.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (189, one new),
    `test_build.py` (190), `test_pipeline.py` (29) and `build.py --plan`.
  - **Next**: request 6, the companions: link 305–307 to 285–287, add the `external-target` tag to 105 and 305–307,
    and decide between `data-binding` and `request-binding` for 306.
- 2026-11-14, **Phase 5 step 1, request 6 done: the companions linked, the tags fixed.**
  - **Reproducer**: a new test, `test_packets.py`'s `CompanionTest`, failed 10 times. It checks three things:
    - each family's negative and positive name each other in `identity.companions`, and the positive's `matching`
      names its negative's number;
    - `external-target` tags exactly the examples that have a `target.json`;
    - each positive carries its family's domain tag (`metrics`, `data-binding`, `password-hashing`), and no packet
      carries `request-binding`.
  - **The change**:
    - 305, 306 and 307's sidecars name 285, 286 and 287 as their companions. Each `matching` names that number beside
      the CVE it already cited. 285–287 already named their positives.
    - Tags: 105 gains `external-target`; 305 gains `metrics` and `external-target`; 307 gains `password-hashing` and
      `external-target`.
    - 306's `request-binding` became `data-binding`. `request-binding` is a defect tag for a handler parameter that
      can't bind, and `PatternMatchUtils.simpleMatch` is not one. `data-binding` is the domain of `DataBinder`'s field
      checks, which call it, and the tag 286, 288 and 299 use.
    - Each of the four `example.json` files has a note saying what changed and why.
    - `build.py --index-only` regenerated the router. `find.py --tag external-target --limit 50` now finds all 20
      sidecar examples.
  - **Left as it was**: 307's `authentication` tag, whose description is about tokens (JWT), fits it poorly.
    `password-hashing` now carries the family. 306 doesn't link 288 or 299, which are 286's companions and not its own.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (192, three new),
    `test_build.py` (190), `test_pipeline.py` (29) and `build.py --plan`.
  - **Next**: request 7, `PreparedTarget.workdir: Optional[str] = None` and `blocker: Optional[Mapping] = None` in
    `interfaces.py`, with `run_controls` and ingestion reading them instead of `route.py`'s layout and
    `source.blocker`.
- 2026-11-14, **Phase 5 step 1, request 7 done: a preparation names its directory and its blocker.**
  - **Reproducer**: three new tests failed on `krnmkrsm`, and 14 existing ones errored once they read `.blocker`:
    - `test_interfaces.py`: `PreparedTarget`'s frozen fields end with `workdir` and `blocker`, both None by default;
    - `test_runtime.py`: a preparation names its directory, and a temporary path stays out of `source`. A failed
      build carries `blocker` and no `source.blocker`. A preparation made outside `<attempt>/prepare/<revision>` runs
      its controls, and one that names no directory doesn't. Before the change, `run_controls` looked for it under
      route.py's layout and refused it.
  - **The change**:
    - `interfaces.py` appends `workdir: Optional[str] = None` and `blocker: Optional[Mapping] = None` to
      `PreparedTarget`, an additive change with defaults, as its docstring allows.
    - `runtime.prepare()` sets `workdir` (absolute) on every preparation made once its directory exists, the failed
      ones included, since their logs are there, and writes it to `prepared.json`. A source lock has none.
    - `_failed()` puts the blocker in the field, never in `source`. `runtime_slice.py` reads it from there.
    - `run_controls` and `run_verifier` find the preparation by `prepared.workdir`, still only if its `prepared.json`
      is the PreparedTarget given. One without a directory is a not-started record.
    - `runtime.py`'s docstring is updated. The cache-hit test now compares two preparations without their directories,
      which differ by design and are no identity.
  - **What the request got wrong** (workflow's half): ingestion never derived the preparation from a directory, and
    `workdir` doesn't let it bundle the raw stdout and stderr. An `ExecutionRecord`'s stream paths are relative to the
    attempt's directory, not a preparation's, and ingestion is still given neither. So it still bundles none, and
    `attempt.stages` keeps the relative paths. Closing that needs the attempt's directory passed to `ingest` (a
    frozen signature) or absolute stream paths. It goes on the for-review list, not into this loop.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (195, three new),
    `test_build.py` (190), `test_pipeline.py` (29) and `build.py --plan`.
  - **Next**: request 8, `result.schema.json`: null `existingTests` and `before`/`after` allowed when `claim.target`
    is present, and `claim.target.revisions`' description fixed.
- 2026-11-14, **Phase 5 step 1, request 8 done: a target receipt says it ran no module tests.**
  - **Reproducer**: a new test, `test_workflow.py`'s
    `test_a_target_receipt_runs_no_module_tests_and_has_no_patch_excerpt`, failed on `ptnszuvl`. A replay's receipt
    carried `existingTests` with the "none: …" task and `passed: false`.
  - **The schema** (`result.schema.json`):
    - `existingTests`, `before` and `after` may be null. A top-level `if`/`then` keeps all three objects unless the
      result has a `claim` with a `target`. So a constructed example's result, or a format-1 result without a claim,
      still needs them. The test checks each of the three refused as null without `claim.target`.
    - `claim.target.revisions`' description now gives each identity: a commit SHA; for a fixture revision, the git
      tree id of its source directory; for a mutant, its base's, with the patch among the claim's files.
  - **Ingestion** (`workflow_ingest.publish`) writes `existingTests: null`, so no test failure is implied. It keeps
    `before` and `after` as the lines of target.json that name the first and last revision. `before` is null for a
    task on one revision, where it used to repeat `after`. The `NOT_RUN` placeholder is gone.
  - **Old receipts**: all 259 stored results (examples, the fixtures and `verification/results/`) give the same
    outcome under the old and the new schema. 258 are valid, and the fixtures' deliberately incomplete receipt is
    refused by both. No reader outside ingestion meets a target receipt's `existingTests`: `render_index()` loads
    `result.json` only for constructed examples.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (196, one new),
    `test_build.py` (190), `test_pipeline.py` (29) and `build.py --plan`.
  - **Next**: request 9, a `driver` control's invocation (main class, arguments, the oracle's `check` and `compare`)
    for 285–287, checked against runtime's lock and controls runner.
- 2026-11-14, **Phase 5 step 1, request 9 done: one oracle convention for the runner and ingestion.** The request named
  285–287, but all seven packets were affected, 105 and 305–307 too.
  - **What was wrong**:
    - *Runner*: `run_controls` took its inputs from the oracle's `PROBES` list. It expected each driver line to echo
      one input as `input`, in order. No packet oracle has `PROBES`: 285–287's drivers print a JVM line first, and
      306, 307 and 105 take two arguments per probe. 105's `PROBES` was a `Path`, which would have raised a
      `TypeError`, not a refusal.
    - *Preparation*: it copied only `oracle.py`, so a prepared oracle couldn't find the probes file it reads.
    - *Ingestion*: it called `check(lines)` and read the result as `(input, problem)` pairs. 305–307 and 105's
      `check` need more arguments, so every replay would have errored. 285–287's `check` returns a dict, read as
      character pairs (`['j', 'v']` from `"jvm"`). So a fixed release would have counted as violating.
  - **Reproducer**: `test_packets.py`'s `OracleConventionTest`, 5 tests. On `vukqmmvo`'s code they gave 15 failures
    and 2 errors.
  - **The convention** (runtime.py's docstring):
    - *Inputs*: the oracle's `driver_args()`, the whole argument vector, if it defines one, else its `PROBES` (the
      fixture's and the slices' form, unchanged). The record's `inputs.from` names which was used.
    - *Lines*: under `driver_args`, every JSON-object line the driver prints is kept, its identity line included. The
      oracle itself matches the lines to its probes. A line that isn't JSON, or no line at all, still gives no
      observations.
    - *Reading*: ingestion uses `problems(lines)` if the oracle defines it, else `check(lines)`. A result that isn't
      a list of `(input, problem)` pairs is an error, never a verdict, and so is a `SystemExit`.
    - *Probes files*: the preparation locks the sidecar's `probe` and `trigger` controls with the oracle. It copies
      them where they sit relative to it, refuses a path that would leave the work directory, and refuses a copy over
      a file the preparation already holds.
    - *Main class*: as before, the class the driver's source file declares, by its path under its source root (it
      resolves for all seven).
  - **Not part of the runner**: `compare`/`differences`, each packet's pair comparison. Each stays the packet's
    developer tool. Ingestion reads each revision's problems against what its pair's kind expects, and the
    preservation tasks are proof tasks.
  - **The seven oracles**: each gains `driver_args()` (equal to its `argv` command's output) and `problems(lines)`, on
    top of its unchanged logic. The CLI is unchanged.
    - 285–287: the property's failures, then the legitimate controls'.
    - 305–307: their `check`, with the coverage check that their `main` makes.
    - 105: disagreements with the Javadoc's contract, without the declared deviations. So before violates at
      (-2)^31 and after holds, as the exact-fix pair expects. Its constant is now `PROBES_FILE`.

    Each `example.json` gains a note, and the index is regenerated. No file pinned the oracles' old hashes, and no
    packet has a receipt.
  - **What the tests check**:
    - each packet's oracle part is prepared by `_add_controls`, and the runner's arguments equal `oracle.py argv`;
    - ingestion reads a constructed replay the statement accepts as no problems (all but 307, which has no
      constructed implementation), and one it doesn't as pairs (105's only at `[-2, 31]`, 285's at its triggers);
    - an incomplete replay is an error;
    - the dict and `SystemExit` cases;
    - the runner's refusals;
    - `_observations` under each convention.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (201, five new),
    `test_build.py` (190), `test_pipeline.py` (29) and `build.py --plan`. No driver was run against real JARs: the
    packets' preparations are Phase 5's jobs.
  - **Next**: request 10's remaining items: a verifier record's `identities.commit`, and a claim-schema key for an
    adapter entry point (or a recorded reason to leave it a gap). The handoff beside `--plan` and `find.py`'s task
    readiness are optional. The fixtures README's `claims/` row was done with request 1.
- 2026-11-14, **Phase 5 step 1, request 10 done: a verifier record names the `lib/` its binary was built from; no
  adapter entry-point key, for a recorded reason.**
  - **Reproducer**: three new tests failed on `kmqzoypl`:
    - `test_runtime.py`'s `test_a_pipeline_jobs_own_build_names_the_lib_commit_it_was_built_from`: the record had no
      `identities.commit`;
    - `test_workflow.py`'s `test_a_verifier_record_that_names_its_lib_commit_completes_the_packets_verifier`: the gap
      packet's `verifier` had no `libTree`;
    - `test_pipeline.py`'s `test_a_jobs_own_jvmcontract_is_named_by_the_lib_tree_it_was_built_from`: a job's
      environment had no `JVMCONTRACT_LIB_TREE`.
  - **The change**:
    - `pipeline.py`'s `step_env` sets `JVMCONTRACT_LIB_TREE` to the git tree id of the `lib/` the job's jvmcontract was
      built from (or reused from a build of the same tree). It drops one inherited from the runner's environment, so
      a job without its own build has none. `verification/README.md` says so.
    - `runtime.run_verifier` records `identities.commit` and `identities.libTree` (`_verifier_build`): the job's
      `VERIFY_SOURCE_COMMIT` and that tree. They are recorded only when `$JVMCONTRACT` is the binary that ran and both
      values are 40 hex digits. Any other binary, such as `lib/target/release`'s or a `$JVMCONTRACT` set by hand, names
      neither, since nothing records what it was built from. The sha256 stays the binary's identity either way.
    - `workflow_handoff.recorded_scan` puts `libTree` with the packet's `verifier`, not its `artifacts`. A packet keeps
      listing `verifier.commit` as missing when the commit is null: the fixture's gap record (a developer build)
      still does, as its test expects.
  - **The adapter entry point is left a gap**, as the request allowed. No packet needs the key: all 41 tasks
    of the seven packets (28 with a claim) name their original method. The claim schema already has `plan`, which
    jvmcontract uses to build a receiver. A key that sends the verifier through an adapter would put the adapter's code inside the proof,
    which changes the scope. It would also need a `lib/` capability this wave doesn't edit. So a receiver or argument
    only an adapter can build (286's `DataBinder`, 287's encoder, 285's `HttpServletRequest`) needs a construction
    `plan` or stays a capability gap, observed once a packet's verifier job reaches it. `run_verifier`'s docstring
    says this. It goes into the v1 gap inventory (step 4) when it is observed.
  - **Not done** (optional in the request): the handoff beside `--plan` in `build.py` or `find.py`, and `find.py`
    matching a task's readiness. `workflow.handoff` and the index's per-task readiness already give both.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (203, two new),
    `test_build.py` (190), `test_pipeline.py` (30, one new) and `build.py --plan`.
  - **Next**: request 11, VF-025: ignore `runtime-mutant/**/spring-core-5.3.19.jar` in `.gitignore`, note it in that
    example's notes, and have later runtime jobs delete `prepare/*/lib/` in cleanup. Then the packets' preparation
    jobs.
- 2026-11-14, **Phase 5 step 1, request 11 done: VF-025 closed. The JARs were committed, so no ignore rule was
  added.** This finishes step 1's interface requests.
  - **What was found**: the request assumed the three 1.4 MiB spring-core JARs of job `20261114-180443` were outside
    the history. They aren't. `jj file list` shows all three at the collect commit `msotkvrv`, and `jj st` shows no
    refused file. The reason is `sync.py`'s `jj()`, which snapshots with `snapshot.max-new-file-size=100MiB` ("must
    not skip files"). So a `sync.py commit` takes what a plain `jj` command refused, and the warning VF-025 saw lasted
    only until the collect's own commit. This also explains how VF-020's two diffs "got past the limit". A
    `.gitignore` rule does nothing to tracked files, so it was left out.
  - **The change**:
    - VF-025 moved to `verification/findings.md`'s closed entries, with a correction under its original text, which
      is kept;
    - `runtime_simplematch/README.md`, the slice's notes, now says the JARs are in the history. It also gives the
      cleanup rule for later jobs: a job that keeps a preparation directory as its output deletes `prepare/*/lib/`
      beside the checkout. A packet task's job (`pipeline.py submit --example NNN --task T`) needs no cleanup step:
      it prepares under scratch space (`build.py`'s `scratch()/targets`), and its one output is `receipts/<task>`.
  - **For the for-review list**: `msotkvrv` is not pushed. Whether its JARs (two distinct blobs, about 3 MB:
    Apache-2.0 published artifacts and a mutant `runtime_slice.py` rebuilds) go into the published history is the
    user's call. Keeping them out means rewriting that commit before the push, which is not this loop's to do.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (203), `test_build.py`
    (190), `test_pipeline.py` (30) and `build.py --plan`. `jj st` lists only this commit's two files.
  - **Next**: the packets through the merged path. First submit the preparation and replay jobs of the six packets
    and 105 with `pipeline.py submit --example NNN --task T`. Start with the replay tasks that gates A3 (285–287) and
    A4 (306, with `mutant-replay`) need. Each job names its revision, task, expected outcome and resources.
- 2026-11-14, **Phase 5 step 1: the replay jobs of gates A3 and A4 queued**, after two fixes that every replay job would
  have failed on.
  - **Fix 1: `build.py NNN --task T` exited 1 after every replay.** It compared the receipt's status with the task's
    `expected`, but a replay decides no claim: its status is always None and its task states no `expected`. So even a
    replay that reproduced would have failed its job. The docstring already said "exits 0 only when ingestion found
    it as the task expected", so the code now does that and reads the receipt's `matchesExpected`. This also closes a
    gap for proof tasks: a vacuous `established` no longer exits 0.
    - Reproducer: `test_route.py`'s `test_a_task_run_exits_0_only_when_its_receipt_matches_what_the_task_expects`. On
      the old code, a matching replay exited 1.
    - The pipeline: a replay job's `expected` text now says what a replay must show, not "none stated". Two new
      `scan_signals` patterns pick up a target task's "as expected" and "NOT AS EXPECTED" lines (new
      `test_pipeline.py` test). Both READMEs say this.
  - **Fix 2: ingestion read every `release` pair as a fix.** `workflow_ingest.SIDES` had `release` give "before
    violates, after holds". The schema defines a `release` pair only as "a release comparison". 306's `replay` runs
    its release pair 5.3.6 → 5.3.7, around a behaviour-preserving change. Its README and hand replay say both releases
    hold, so its A4 replay would have been recorded as not expected. A release pair's sides now follow the case's
    role: a negative case's vulnerable release violates and its fixed one holds; for a positive case both hold; for
    any other role (the fixture's control, runtime's calibration slices) the pair gives no expectation.
    - Reproducer: `test_packets.py`'s `ReplayExpectationTest`. It checks the expected sides of all 13 replay tasks of
      the seven packets against their READMEs. On the old code, 306's `replay` and the role rule failed.
    - 306's `example.json` has a note, and its sidecar is unchanged. The workflow stream's brief still describes the
      old rule (`example-targets-workflow.md:219`, a finished stream's record, left as it is).
  - **Queued** at this commit, each a `build.py NNN --task T` job with 2 CPUs:
    - `20261114-214754-example-targets-phase-5-gate-a3-example`: 285 `replay`, Boot 2.7.17 → 2.7.18, 14 pinned JARs.
    - `20261114-214818-example-286-replay-gate-a3-cve-2022-2296`: 286 `replay`, Framework 5.3.18 → 5.3.19.
    - `20261114-214818-example-287-replay-gate-a3-cve-2025-2222`: 287 `replay`, Security 6.3.7 → 6.3.8.
    - `20261114-214818-example-306-replay-gate-a4-framework-db9`: 306 `replay`, spring-core 5.3.6 → 5.3.7, both
      expected to hold.
    - `20261114-214818-example-306-mutant-replay-gate-a4-the-ne`: 306 `mutant-replay`, 5.3.7 against `drop-prefix`.
      The mutant is built from the base commit fetched at depth 1. 5.3.7 must hold and the mutant violate.

    Each expects "as expected" and exit 0, with every revision on JDK 21 and 25 and a receipt under
    `receipts/<task>/`. 2–3 GiB each, 10–15 minutes estimated (R2's comparable job took 7 s).
  - **Not run inline**: a trial of 306's replay outside the pipeline was refused by the session's permissions, which
    fits this brief's "prepared by runtime's code (jobs)". So these jobs are the first real packets on the merged
    path.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (206, two new),
    `test_build.py` (190), `test_pipeline.py` (31, one new) and `build.py --plan`.
  - **Next**: Phase 5 step 2, the 105 calibration (A5), as a job. Check `build.py --plan 105 --task fix-property` and
    the other proof tasks, and how its pinned upstream Maven build on JDK 11 is prepared. Once the five jobs above are
    collected, read their receipts. Then queue the other replays: 285–287 `mutant-replay`, 105's `replay`, and 307's
    `replay` and `mutant-replay` (307 only if its route is not blocked; 305 is blocked on its SNAPSHOT pins).
- 2026-11-14, **Phase 5 step 2: the calibration's two proof jobs queued (gate A5)**, after a fix without which both
  would have ended in an error before running.
  - **Fix: the runner refused every upstream-build task as "missing on this machine: maven".** build.py's plan for
    105's tasks requires `maven` (`workflow.BUILD_TOOLS`). `pipeline.missing_tools` looked that name up on PATH, where
    no executable is called `maven`. Runtime builds with the highest Maven under `$TARGETS_MAVEN_CANDIDATES`
    (sdkman's candidates) by full path, and runtime's own R2 job only got past this because it listed no `maven`.
    `missing_tools` now asks `installed_maven()` the same question runtime does: is there an install other than
    `current` or a link? The job schema's `requires` description and `--requires`' help name it.
    - Reproducer: `test_pipeline.py`'s `MissingToolsTest`, which failed on `ykxtqwmt` (`['maven']` where `[]` was
      expected). It also checks that an empty candidates directory, or `current` alone, still counts as missing.
  - **The plan**, checked offline: `build.py --plan 105 --task fix-property` and `fix-property-before` are executable.
    Each runs one revision (`after` or `before`) by the upstream-build route, Maven 3.10.0 on JDK 11, with native,
    strict, unwind 16 and `claims/pow-minus-two.json` (key `8a4071f6a417d239` for both tasks). Their `replay`
    prerequisite only orders the handoff: the route runs each task's own controls before the verifier. The parameter
    names `k` and `e` come from the LocalVariableTable that Maven's default `-g` writes, which jvmcontract reads when
    there is no MethodParameters. Runtime's job `20261114-174017` already built both commits by this recipe in 59 s.
  - **Queued** at this commit, each a `build.py 105 --task T` job requiring the runner's own jvmcontract, with 2 CPUs,
    3 GiB and 15 minutes:
    - `20261114-215343-example-105-fix-property-gate-a5-arithme`: `fix-property` on 8cfc04e8, expected established;
    - `20261114-215345-example-105-fix-property-before-gate-a5`: `fix-property-before` on e7c172d2, expected refuted
      with the witness (-2, 31), which the replay reproduces on JDK 21 and 25.

    A5 passes on these only if each prints "as expected" and its receipt shows the conclusion and witness. An
    `unresolved` result is recorded as such, and is not a pass.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (206), `test_build.py`
    (190), `test_pipeline.py` (32, one new) and `build.py --plan`.
  - **Next**: nothing in Phase 5 is left that doesn't wait on these seven jobs. Each later step reads their receipts:
    the remaining replays (285–287 `mutant-replay`, 105 `replay`), step 1's proof tasks and probes, the joint
    acceptance, the gap inventory and the for-review list. Once they are collected, read each receipt, fix a failure
    with a reproducer (two substantive failures per item), then queue the rest.
- 2026-11-14, **the user's decisions on four for-review items** (a review with the user after the run stopped; the
  lookups were HEAD requests and small metadata fetches on 2026-11-14).
  - **P3 (307): the upstream build, with its plugin from an anonymous mirror and an output check.**
    - `spring-build-conventions 0.0.23.RELEASE` is served without login by Alibaba Cloud's mirror of Spring's plugin
      repository, `https://maven.aliyun.com/repository/spring-plugin/`: 416,730 bytes, sha256
      `65b65633191873ed903a7a74d32420cd6dcbe377783acd2a090fb69609746c74` (the mirror's sha1 `753001a6…` agrees). The
      mirror cached it on 2019-02-26; its `META-INF/` is dated 2019-01-10 18:52, the minute of upstream's commit
      "Release 0.0.23.RELEASE" (`f373956f` in `github.com/spring-gradle-plugins/spring-build-conventions`).
    - No independent hash exists: repo.spring.io's checksums answer 401 like the JAR, and the Wayback Machine has no
      capture. Building the plugin from its tag doesn't avoid the mirror either: three of its compile dependencies,
      `docbook-reference-plugin 0.3.1`, `propdeps-plugin 0.0.10.RELEASE` and `spring-io-plugin 0.0.8.RELEASE`, are
      also only there (Central and plugins.gradle.org 404). Security's buildscript resolves them transitively, so the
      build needs all four from the mirror.
    - **Decided**: the download hosts gain `maven.aliyun.com` (an extension of decision 1), each file pinned by
      sha256. The build job also compares the `BCrypt.class` it builds for `before` with Spring Security 5.2.0.M4's
      published one (before's `BCrypt.java` equals 5.2.0.M4's, and repo.spring.io/milestone serves 5.2.0.M4
      anonymously). A match shows that the plugins left the proved class alone, whoever served them. A mismatch is
      recorded as a blocker. The commit's sources stay unedited: the route points the buildscript's repository
      lookups at the mirror, for example with a Gradle init script.
  - **P1 (305): the narrower slice, checked against Boot 2.2.0.M6's published classes.**
    - The SNAPSHOTs that the two commits (2019-09-05) resolved are gone. repo.spring.io/snapshot is anonymous but
      keeps only each SNAPSHOT's last builds (spring-data-commons `2.2.0.BUILD-SNAPSHOT`: only 2019-09-30's), and
      the Aliyun mirror carries no snapshots.
    - Boot 2.2.0.M6 (tag `fb75cbbc`) has after's exact `WebMvcTags.java` (`78c4c0b9…`) and `Outcome.java`
      (`dcbc759e…`), by git blob id (the GitHub contents API). Its `spring-boot-actuator` JAR is on
      repo.spring.io/milestone (200). M5's `WebMvcTags.java` (`477d7b42…`) is neither side's, so no published pair
      exists.
    - **Decided**: each commit's `WebMvcTags` and `Outcome` compiled outside the upstream build against spring-web
      5.2.0.RC2 (repo.spring.io/milestone), micrometer-core 1.2.0 and javax.servlet-api 4.0.1 (Central), a separately
      labelled scope. M6's published classes are replayed beside the `after` slice as an independent check that the
      slice behaves like Spring's own build. Substituting the 2019-09-30 SNAPSHOTs was rejected.
  - **`msotkvrv`'s JARs are published** as they are; no history rewrite. That for-review item is closed.
  - **307's `authentication` tag is dropped**, because the vocabulary entry means tokens and their validation. 307
    keeps `password-hashing` and `text-encoding`. 300 keeps the tag (`DaoAuthenticationProvider`'s login timing).
    Done in this commit: 307's `example.json` (tag and a note), and the router regenerated with
    `build.py --index-only`.
  - **Checked**: `test_packets.py` (16) passes.
  - **Next**, before the seven pending jobs are read:
    1. the host extension in `runtime_maven.py`, with a reproducer;
    2. 307's Gradle route with the mirror and the 5.2.0.M4 output check, queued as a job;
    3. 305's slice route and the M6 replay, queued.

    The seven jobs still pending:
    - `20261114-214754-example-targets-phase-5-gate-a3-example`
    - `20261114-214818-example-286-replay-gate-a3-cve-2022-2296`
    - `20261114-214818-example-287-replay-gate-a3-cve-2025-2222`
    - `20261114-214818-example-306-replay-gate-a4-framework-db9`
    - `20261114-214818-example-306-mutant-replay-gate-a4-the-ne`
    - `20261114-215343-example-105-fix-property-gate-a5-arithme`
    - `20261114-215345-example-105-fix-property-before-gate-a5`

    Once they are collected, read each receipt as the previous entry's Next says.
- 2026-11-14, **the seven jobs read: gates A3, A4 and A5 pass on their receipts. 286's replay failed on a runtime
  defect, now fixed and resubmitted** (VF-026). The verification loop collected the jobs in `kkppnnuy`.
  - **A3 (original negative replay) passes, on 285 and 287**. Each was a published-artifact replay at `863e1015`,
    every revision on JDK 21.0.13 and 25.0.5, each run exiting 0 with structured observations, read by the packet's
    independent oracle:
    - **285** (Boot 2.7.17 → 2.7.18, 16 observations a run): 2.7.17 violates the frozen label set at `connect`,
      `empty-token`, `long-token`, `lowercase-get` and `xscf`. 2.7.18 shows no problem, so its security response holds
      on the same triggers and the legitimate probes keep their labels. The oracle reports a legitimate control's
      failure as a problem too.
    - **287** (Security 6.3.7 → 6.3.8, 34 observations a run): 6.3.7 violates at 12 overlong triggers (ASCII,
      multibyte, split-character, supplementary, 73 and 80 bytes). 6.3.8 shows no problem.
  - **A4 (independent positive replay) passes, on 306**: `replay` (spring-core 5.3.6 → 5.3.7, 40 observations a
    run): both releases hold. `mutant-replay`: 5.3.7 holds, and the constructed `drop-prefix` mutant violates the same
    oracle at its prefix probes (`abc*` against `xbcdef` among them).
  - **A5 (supported verifier calibration) passes, on 105**, through the upstream-build route (Maven on JDK 11), the
    runner's own jvmcontract, native and strict:
    - `fix-property` on 8cfc04e8 is `established`, not vacuous ("`pow(k=-2, e=0)` reaches the calls"): 1 property
      over `k: int × e: int`, unwind 16 with unwinding assertions, 3.0 s.
    - `fix-property-before` on e7c172d2 is `refuted` with the witness `pow(-2, 31)`, which throws
      `ArithmeticException("integer overflow")`, replayed in the interpreter.
    - Each receipt's JVM controls on JDK 21 and 25 exited 0. **For review**: what those controls observed isn't in
      the receipt: ingestion bundles no raw streams, the same item as request 7's. So the JVM side of the witness is
      the job's, not the receipt's.
  - **286's replay** (`20261114-214818-…`) never ran a driver: "revision vulnerable-release is failed, not
    artifacts-ready". The job's kept work directory has the reason in the preparation's `prepared.json`: stage
    `adapter`, "never references `DataBinder#isAllowed`".
    - 286's `ExposedDataBinder extends DataBinder` calls the protected `isAllowed(field)` unqualified. javac writes
      that as a Methodref owned by the subclass (`javap`: `invokevirtual isAllowed:(Ljava/lang/String;)Z`). Runtime's
      `_check_classpath` counted only references owned by an original class. So the cause is not 5.3.18's JARs:
      5.3.19 and the mutant would have failed the same way.
    - **Reproducer**: `test_runtime.py`'s `InheritedCallTest` (3 tests). On the old code, a subclass's unqualified
      call gave 286's diagnostic.
    - **Fix**: `runtime_jar.super_class` and `resolve_method` resolve a reference owned by an adapter class up the
      superclass chain, as the JVM does (JVMS 5.4.3.3's class step). The search stops at a class whose bytes aren't
      on the classpath, never guessing. `_check_classpath` resolves through the classpath's first holders. An
      override that doesn't call `super` still doesn't count. The adapter is unchanged. `runtime.py`'s docstring says
      this.
    - **Checked on the real bytes**: the check, rerun offline on the job's kept 5.3.18 JARs, now finds
      `DataBinder#isAllowed` among the adapter's six original calls.
    - **Side effect**: a proof task whose adapter reaches its target through a subclass now records
      `adapterCallsTarget: true`, so its controls run. That is 286's `isAllowed` and `bind` tasks.
    - **Resubmitted**: `20261114-223812-example-286-replay-gate-a3-cve-2022-2296`, expecting "as expected". VF-026 has
      the cause and the job, and stays open until the job passes. 286's `example.json` has a note.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (209, three new),
    `test_build.py` (190), `test_pipeline.py` (32) and `build.py --plan`.
  - **Next**: the user's decisions: the `maven.aliyun.com` host in `runtime_maven.py`, with a reproducer; then 307's
    Gradle route with the 5.2.0.M4 output check, as a job; then 305's slice and the M6 replay. After them, the
    remaining replays (285–287 `mutant-replay`, 105 `replay`) and step 1's proof tasks and probes, then the joint
    acceptance. 286's resubmitted replay runs meanwhile.
- 2026-11-14, **the `maven.aliyun.com` host allowed, for Spring's plugin repository only** (decision 1's second
  extension).
  - **Reproducer**: a new test, `test_runtime.py`'s `test_the_aliyun_mirror_is_allowed_for_springs_plugin_repository_only`,
    failed on `nrxvrqpx`: `allowed()` refused the mirror's `spring-build-conventions 0.0.23.RELEASE` URL.
  - **The change** (`runtime_maven.py`): `HOSTS` gains `maven.aliyun.com`, and a new `PATH_PREFIXES` holds it to
    `/repository/spring-plugin/`, since the user allowed the mirror for P3's Spring plugins, not the mirror as a whole.
    A path that leaves the prefix by a `.` or `..` segment or a percent-encoding is refused, because a server would
    resolve it after the check. `HOST_NAMES`, and the docstrings of `runtime.py` and `runtime_upstream.py`, name it.
    Every caller goes through `allowed()`, the redirect check included.
  - **What the test refuses**: the mirror's other repositories (`public`, `central`), `spring-pluginx`, the bare
    prefix, dot segments and `%2e%2e`, http, a user name or port, and the look-alikes `maven.aliyun.com.example.org`,
    `aliyun.com` and `mirrors.aliyun.com`. A SNAPSHOT stays refused there too. The earlier host test still passes.
  - **Not yet changed**: 307's target.json blocker, handoff and README still say the plugin needs credentials. The
    Gradle route's cycle rewrites them along with the route.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (210, one new),
    `test_build.py` (190), `test_pipeline.py` (32) and `build.py --plan`.
  - **Next**: 307's Gradle route. Fetch the 5.5.1 wrapper distribution by sha256, then use an init script that sends
    the buildscript's repositories to the mirror and the allowed hosts. Hash every file the build resolves, and compare
    `before`'s `BCrypt.class` with Spring Security 5.2.0.M4's published one. Queue it as a job. Then 305's slice and
    the M6 replay.
  - **286's resubmitted replay passed** (`20261114-223812-…`, collected in `kxzlrsou`, which marks VF-026 closed). Its
    receipt `receipts/replay/20261114T224026Z-eca417ca` shows 5.3.18 violating the oracle at 12 triggers on JDK 21 and
    25: 8 helper-predicate ones (`Age`, `AGE`, `Touchy`, `someMap[key3]`, …) and 4 actual protected-property
    mutations through `bind`. 5.3.19 shows no problem on either JDK. So **A3 passes on all three negative packets**,
    285, 286 and 287. VF-026's entry still sits under `findings.md`'s Open heading, with a closed status, as the
    collect left it.
- 2026-11-14, **307's Gradle route not built: the decided build can't resolve its buildscript, so the route needs
  the user again.** These are lookups (HEAD requests and pinned fetches through `runtime_maven.fetch`, all in 307's
  `sources.lock.json` under `buildRoute`), not a build.
  - **What is in reach and pinned**:
    - the 5.5.1 distribution, sha256 `222a03fc…`. That is Gradle's published checksum from gradle.org's checksum
      page. The wrapper properties record none, services.gradle.org sends the `.sha256` to downloads.gradle.org, and
      the github.com release has no `.sha256`;
    - the four Spring plugins on the mirror, each with its sha1 agreeing: spring-build-conventions `65b65633…`, as
      the user's lookup found, and docbook-reference-plugin, propdeps-plugin and spring-io-plugin.
  - **What isn't** (the buildscript's transitive closure, which Gradle resolves before compiling anything):
    - plugins.gradle.org serves every plugin it hosts by a 303 redirect to `plugins-artifacts.gradle.org`, which
      `runtime_maven.py` doesn't follow. Six of the buildscript's plugins are such: gretty 2.2.0,
      build-info-extractor-gradle 4.7.5, gradle-versions-plugin 0.17.0, asciidoctor-gradle-plugin 1.5.8.1,
      gradle-ssh-plugin 2.9.0 and nohttp-gradle 0.0.2.RELEASE. Of these, nohttp-gradle is also on Central, and three
      others on the spring-plugin mirror;
    - at least two second-level dependencies were published only to JCenter, which now redirects to Central, where
      they 404: `org.gretty:gretty-core:2.2.0` and `org.jfrog.buildinfo:build-info-extractor:2.11.3`. They also 404
      on repo.spring.io/milestone and the spring-plugin mirror, and answer 401 on repo.spring.io's plugins-release
      and libs-release. Only maven.aliyun.com's `jcenter`, `public` and `gradle-plugin` repositories serve them. The
      closure wasn't enumerated further.
  - **Why no route was built**: the decided route can't run its buildscript, and 307 is its only user. Building it
    anyway would be a speculative piece that a choice of the slice would discard.
  - **A fact for the decision**: before's `BCrypt.java` compiled alone, by hand (a note), with javac 1.8.0_512 and
    `-g -source 1.8 -target 1.8 -encoding UTF-8`, gives a `BCrypt.class` byte-identical to the published one.
    - The published class is the one in Spring Security 5.2.0.M4's JAR on repo.spring.io/milestone: JAR sha256
      `8871c1fe…` (its sha1 agrees with the repository's), class sha256 `0b137406…`, built with Oracle 1.8.0_201.
    - Without `-g`, or with `-parameters` added, the bytes differ.
    - So an extracted-source slice reproduces Spring's own build of before's class exactly. That holds for this
      class, and by the same recipe for after's, which has no published counterpart.
  - **The user's options**, in 307's handoff:
    - (a) the upstream build, if plugins-artifacts.gradle.org may be followed as plugins.gradle.org's redirect host
      and maven.aliyun.com's JCenter mirror may serve the JCenter-only modules, each file hashed. The Gradle route
      is then built (distribution by sha256, an init script with content filters holding the mirror to its modules,
      every resolved file hashed) and queued, with before's class compared with M4's;
    - (b) the slice, each commit's `BCrypt.java` compiled with javac 8 `-g`, before's class checked byte for byte
      against M4's. It reuses the slice route 305 gets next. This loop recommends (b): it is the user's stated
      order (an anonymous verifiable copy, then a slice), and its before side already equals the published bytes.
  - **Changed**: 307's target.json blocker and next, README, an `example.json` note and `sources.lock.json`
    (`buildRoute`, and 5.2.0.M4's published JAR and class hashes with the slice compile); `runtime_upstream.py`'s
    docstring; the index regenerated.
  - **Out of date in the brief**: decision 1's second extension says the mirror gives P3 its build, and the Progress
    entry of the user's decisions says the build needs the four plugins from the mirror. Both predate these lookups.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (210),
    `test_build.py` (190), `test_pipeline.py` (32) and `build.py --plan`.
  - **For the user**: 307's route, (a) or (b). P3 stays partial at "source locked" until then.
  - **Next**: 305's slice route and the M6 replay, needing only this loop: compile each commit's `WebMvcTags` and
    `Outcome` against spring-web 5.2.0.RC2, micrometer-core 1.2.0 and javax.servlet-api 4.0.1, as a separately
    labelled scope, and replay Boot 2.2.0.M6's published classes beside the after slice. Build it so 307 can reuse
    it if the user chooses (b). Then the remaining replays (285–287 `mutant-replay`, 105 `replay`).
- 2026-11-14, **305's source-slice route built, and its three replay jobs queued** (the user's decision on P1).
  - **A fact found first** (a note: a hand fetch and compile): the after slice's `WebMvcTags.class` and `Outcome.class`
    are byte-identical to Boot 2.2.0.M6's published ones.
    - The recipe: javac 1.8.0_512 with `-g -parameters -source 1.8 -target 1.8 -encoding UTF-8`, against six pinned
      JARs. M6 (`fb75cbbc`) carries after's two files.
    - With `-g` alone the bytes differ.
    - Before has no published counterpart.
  - **Two things the decision didn't foresee**:
    - repo.spring.io serves its larger JARs by a 302 to its own storage (`jfrog-prod-use1-shared-virginia-main.s3.
      amazonaws.com/aol-springsource/filestore/<sha1>`). `runtime_maven.py` refused it, so the allowed milestone
      repository served nothing. It now follows that one redirect, from repo.spring.io only and only under that path
      (`ORIGIN_REDIRECTS`). The bytes are still checked against the sha256.
    - `WebMvcTags` imports `HandlerMapping` and `StringUtils`, so the slice also needs spring-webmvc and spring-core
      (with spring-jcl) from the same Framework 5.2.0.RC2 milestone, beside the three JARs the decision named.
  - **The route** (`source-slice`), reusable by 307 under option (b):
    - Schema: the route; `preparation.slice` (files per revision, the JDK, javac flags from a closed list); a
      revision's own `route: published-artifact`, for a published reference on this route only; the pair kind
      `correspondence`; and repo.spring.io in an artifact's URL pattern.
    - `sidecar.py`: the slice names files for exactly the revisions it compiles. A published reference is no mutant's
      base, lists its JARs, and is compared only in a correspondence pair.
    - Workflow's planner gives each revision its own route. A slice entry carries `slice` and its `published` JARs,
      and so does a mutant's base.
    - Runtime: `_lock_slice` (offline) and `_prepare_slice`:
      - the JARs are acquired, and the commit is checked out with its parent;
      - a mutant's patch is applied there, and may change only the slice's files;
      - each file is hashed and named by its git blob id;
      - the files are compiled alone by the recorded JDK, with `-implicit:none`, `-proc:none` and an empty source
        path;
      - a class no file declares is refused.

      The verifier's scope label is `extracted-source-slice`.
    - Ingestion: a correspondence matches only when both sides show the same observations and oracle problems on
      every JDK. A slice receipt's claim gains `target.scopes` per revision (result schema, additive). No other
      route's claim changes.
  - **305's sidecar**: the route `source-slice`, and a new revision `release-m6` (M6's actuator JAR plus the slice's
    six JARs). There is a new pair `m6-correspondence`, and a new task `m6-replay` (relation `calibration`). The
    build blocker stays, for the exact commits' own builds, with the slice as the decided scope. Its
    `sources.lock.json`, README and a note record the pins and the byte identity. The index is regenerated.
  - **Tests**, 10 new, all offline:
    - the storage redirect, and what stays refused;
    - five of the slice route against the local stand-ins: the lock and its refusals; the fixture recipe's bytes
      from a slice; a missing file, offline and a stray class; the slice mutant; and the mutation pair's replay;
    - the sidecar's slice rules;
    - 305's plans and locks, the correspondence reading, and the scopes.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (220, ten new),
    `test_build.py` (190), `test_pipeline.py` (32) and `build.py --plan`.
  - **Queued**, each `build.py 305 --task T` with 2 CPUs, 3 GiB and 20 minutes:
    - `20261114-232734-example-305-replay-p1-source-slice-route`: before and after both hold;
    - `20261114-232734-example-305-m6-replay-p1-s-check-against`: the after slice and M6's JAR alike;
    - `20261114-232735-example-305-mutant-replay-p1-s-mutation`: after holds, the mutant violates at 200.
  - **For the for-review list**:
    - following repo.spring.io's storage redirect is this loop's reading of decision 1's extension, as github.com's
      content hosts are followed;
    - spring-webmvc and spring-core were added to the decided JARs;
    - the M6 correspondence runs M6's JAR on the slice's dependencies, not on M6's own POM's.
  - **Next**: the remaining replays, which need only this loop: 285–287 `mutant-replay` and 105 `replay`, queued.
    Then read 305's three jobs when they are collected. Then step 1's proof tasks and probes, the joint acceptance,
    the gap inventory and the for-review list. 307 still waits on the user's route choice; under (b) it reuses this
    route as it is.
- 2026-11-14, **305's three slice jobs read: all pass, so P1 is a reproducible scaffold at the slice's scope. The
  remaining four replays queued.**
  - **305** (collected in `xoqmqynm`), each on JDK 21.0.13 and 25.0.5, each run exiting 0 with structured observations:
    - `replay` (`receipts/replay/20261114T232950Z-89be94d5`): the before and after slices both hold the oracle, as a
      positive pair expects;
    - `m6-replay` (`20261114T232949Z-d7367f92`): the after slice and Boot 2.2.0.M6's published actuator JAR show the
      same observations and no problem, as the correspondence expects. So the slice behaves like Spring's own build of
      after, on top of the byte identity found by hand;
    - `mutant-replay` (`20261114T232951Z-3c5edba8`): after holds, and the status-200 mutant fails at 200 alone
      (`outcome=INFORMATIONAL` where the statement says `SUCCESS`).
    - Each receipt's `claim.target.scopes` labels the slices `extracted-source-slice`, M6 `original-bytecode` and the
      mutant `constructed-mutation-of-a-slice`. The index now gives 305 `scaffolded` on every task.
    - 305's README state, handoff `next` and a note record this; the index is regenerated. No proof was attempted: its
      four native tasks are step 1's proof work.
  - **Queued** at this commit, each a `build.py NNN --task T` job with 2 CPUs, 3 GiB and 20 minutes, plans checked
    offline first (all executable):
    - `20261114-233239-example-285-mutant-replay-phase-5-step-1`: 2.7.18 holds; the `raw-method-fallback` mutant fails
      at the five triggers and no legitimate probe;
    - `20261114-233239-example-286-mutant-replay-phase-5-step-1`: 5.3.19 holds; the `pattern-side-unnormalized` mutant
      fails at 13 probes, `favouriteColour` among them;
    - `20261114-233239-example-287-mutant-replay-phase-5-step-1`: 6.3.8 holds; the `char-count-guard` mutant fails at
      the multibyte triggers and the unguarded byte entry;
    - `20261114-233239-example-105-replay-phase-5-commons-numbe`: before fails at (-2, 31) alone; after holds.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (220), `test_build.py`
    (190), `test_pipeline.py` (32) and `build.py --plan`.
  - **Next**: step 1's proof tasks and probes, queued after checking each plan offline: the six packets' security,
    preservation and mutant claim tasks (305's four on the slice; 307's wait on the user's route choice), each
    expected to reach its stated conclusion or an observed capability refusal. Then read the four replays above when
    collected, then the joint acceptance (A1, A2, A6, A7, A8), the gap inventory and the for-review list.
- 2026-11-14, **Phase 5 step 1: every claim task of the five buildable packets queued, and 105's two preservation
  tasks** (24 jobs). Each is `build.py NNN --task T`, native and strict, with the runner's own jvmcontract.
  - **The plans, checked offline first**: `build.py --plan NNN --task T` gives an executable plan for all 25 claim
    tasks, 307's `preservation` included. 307's isn't queued, because its route still waits on the user's choice: its
    plan is executable, but its preparation would stop at the Gradle blocker.
  - **What each job states**: its expected conclusion, from the task's `expected` (`refuted` for the vulnerable
    releases and the mutants, `established` for the fixed releases and the preservation tasks, `refuted` for 105's
    plain `regression`). It also names the stop this loop predicts, and says that a capability refusal is a
    diagnostic, not a pass. Such a refusal gives an unresolved receipt, prints NOT AS EXPECTED and exits 1. It is read
    as an observed gap for step 4, and the claim stays unresolved. The receipt comes back under the result's
    `outputs/` either way.
  - **The predictions, still predictions**:
    - 285 and 305: the argument is a library interface (`HttpServletRequest`, `HttpServletResponse`);
    - 305: also `Outcome`'s static initializer;
    - 286: the `DataBinder` receiver, which only the adapter builds and no claim gives a `plan` for;
    - 287: the encoder receiver, `String.getBytes(UTF_8)`, and the stored hash as a String in a property check.
    306 (two Strings, maxArrayLength 6) and 105 (two ints) are inside the supported domain.
  - **Queued**, 2 CPUs each; 4 GiB and 30 minutes for 285–287 and 305, 3 GiB and 20 minutes for 306 and 105:
    - 285: `20261114-234211-example-285-vulnerable-security-phase-5`, `…-285-fixed-security-phase-5-step`,
      `…-285-preservation-phase-5-step-1`, `…-285-mutant-security-phase-5-step`;
    - 286: `20261114-234211-example-286-vulnerable-security-phase-5`, `20261114-234212-example-286-fixed-security-
      phase-5-step`, `…-286-preservation-phase-5-step-1`, `…-286-vulnerable-protected-state-m`,
      `…-286-fixed-protected-state-mutati`, `…-286-mutant-security-phase-5-step`;
    - 287: `20261114-234212-example-287-vulnerable-security-phase-5`, `…-287-fixed-security-phase-5-step`,
      `20261114-234213-example-287-preservation-phase-5-step-1`, `…-287-vulnerable-guard-phase-5-ste`,
      `…-287-fixed-guard-phase-5-step-1-b`, `…-287-mutant-security-phase-5-step`;
    - 305: `20261114-234213-example-305-preservation-phase-5-step-1`, `…-305-finite-outcome-before-phase`,
      `…-305-finite-outcome-after-phase-5`, `…-305-mutant-preservation-phase-5`;
    - 306: `20261114-234213-example-306-preservation-phase-5-step-1`, `20261114-234214-example-306-mutant-preservation-
      phase-5`;
    - 105: `20261114-234214-example-105-regression-phase-5-step-1-ar`, `…-105-confined-change-phase-5-step`.
  - **The four replays queued last cycle** have all finished as passed, but the verification loop hasn't collected
    them yet. Their receipts are read once it has.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (220), `test_build.py`
    (190), `test_pipeline.py` (32) and `build.py --plan`.
  - **Next**: the joint acceptance's rows that the receipts already in the tree can show: A1 (offline planning, lint,
    discovery and handoff), A2 (preparation integrity, from the replay receipts), A6 (distinct receipts) and A7 (an
    isolated session following one packet's exported handoff). Then read the four replays once collected, and the 24
    jobs above, for A8, the gap inventory and the for-review list.
- 2026-11-15, **Phase 5 step 3, the joint acceptance: A1, A2 and A6 pass on the real packets and their receipts.
  A1 found that a target's blocker reached no task's handoff, now fixed. A7's isolated session followed 105's
  exported handoff and queued its job.**
  - **The four replays** (collected in `mtvwvktk`), all as expected on JDK 21 and 25:
    - 105 `replay`: before fails at (-2, 31) alone, and after holds;
    - 285–287 `mutant-replay`: the fixed release holds. The mutant fails at 5, 13 and 7 probes, as predicted:
      - 285: the five triggers;
      - 286: helper and `bind` probes, `favouriteColour` among them;
      - 287: the multibyte triggers and the unguarded `bytes-73-*` entry.

    So every packet but 307 has its constructed mutation replayed and caught by its oracle.
  - **A1's defect**:
    - What was wrong: `workflow.task_blockers` kept only blockers naming the task. 305's and 307's blockers name
      none, though discovery (`workflow_discovery.gaps`) reads them as the target's. So 307's predicted Gradle build
      blocker was in none of its four handoffs. Its replay handoff said to run the replay, with no word of the build.
      The gap inventory also skipped every task whose blockers name no task, so 305's and 307's predicted gaps were
      missing from it.
    - Reproducers, both failing on the old code: `test_workflow.py`'s `test_a_blocker_naming_no_task_is_the_targets`,
      and `test_acceptance.py`'s blocker test (24 subtests).
    - Fix: a blocker that names no task applies to every task of its target. A capability-kind one applies only to
      the tasks that run the verifier, since a replay runs none. The inventory reads the same function.
      `target.schema.json` describes an omitted `task`, and the handoff docstring says it too. A prediction still
      blocks nothing: `next` is unchanged, and so is the index (`build.py --index-only` gives no diff).
  - **A new test, `examples/tools/targets/test_acceptance.py`**: 13 tests, offline, over the 20 sidecar examples and
    the 15 receipts now in the tree.
    - A1: every task of every sidecar plans and hands off with no network, subprocess or write. A native task needs no
      JBMC, and a task that acquires says so. Each recorded blocker is in the handoff of every task it blocks.
      Discovery's projection equals the committed index.
    - A2: each receipt's revisions are the sidecar's commits; a mutant's JVM records name
      `mutant:<base>+<patch sha256>`. Each JVM record:
      - names a JDK `release` file;
      - runs the claim's classpath in order, role and sha256;
      - uses the oracle hash in the claim;
      - runs on both JDK 21 and 25.

      Every library JAR, and a published revision's original, is a sidecar pin. The refusals (wrong bytes, a shadowed
      class, an escaping path) are runtime's and the sidecar's unit tests, named so a rename is noticed.
    - A6: each receipt passes `build.check_result` (schema, round trip, bundle) with its `plan.json` beside it. Attempt
      ids are distinct, and each claim id belongs to one task. Execution, conclusion, expectation, scope and replay
      stay separate fields: a replay concludes nothing; a proof is native and not vacuous; a refutation carries its
      witness. Each receipt is its task's current one, and none is stale.
  - **A7, the isolated session**: a subagent got only `workflow_handoff.py handoff 105 fix-property-before`'s export
    (sha256 `de11d49c…`). It was told to read nothing but the packet, its inputs and the receipt it names. It found:
    - all 6 inputs matched their sha256;
    - `build.py --plan` equals the packet field by field (claim key `8a4071f6a417d239`, bounds, native, strict,
      refuted);
    - the receipt's witness is `pow(-2, 31)`.

    It queued the attempt with the packet's own command:
    `20261114-235737-example-105-task-fix-property-before-the`. It expects the same refutation under the same key.
    **A7 passes once that job comes back as expected.** It needed nothing outside the packet, and reported four
    things for the for-review list:
    - a property check's receipt has `evidence.replay: null`, and its witness replay is stated only in the proof text
      (an equivalence's, like 105 `regression`, has the structured `{"by": "interpreter", "reproduced": true}`);
    - a one-revision task's witness names its classes `after`;
    - the receipt's `claim.id` (`bb2955ce…`) is not the frozen claim key, and nothing says which a reader compares;
    - the claim's assumptions cite `records/pow-gaps.json`, which the handoff doesn't list as an input.
  - **The 24 proof jobs** were collected by the verification loop in `ynvtsvxs`, with **VF-027** opened. 105
    `regression` is `refuted` as expected: witness `pow(-2, 31)`, replayed in the interpreter, after 223 s. The
    other 23 give no verdict. VF-027 gives five causes:
    1. an interface parameter (285, 305);
    2. a receiver the checker can't build (286, 287);
    3. a `String` parameter outside a regression check, or a nullable one (287's guard tasks; 306
       `mutant-preservation`);
    4. different dependency closures for the two sides, so the four `preservation` tasks weren't executed;
    5. 105 `confined-change` refused at `StringBuilder.<init>` under strict.

    Not read further this cycle.
  - **Checked**: `example-targets-integration.sh` exits 0: the contract (16), the targets suite (234: 13 in
    `test_acceptance.py` and one in `test_workflow.py` are new), `test_build.py` (190), `test_pipeline.py` (32) and
    `build.py --plan`.
  - **Next**: read the 24 jobs' receipts (VF-027) for step 4, the v1 gap inventory. Each cause observed on a task
    becomes an observed blocker of that task, citing its verifier output. The claims and expectations stay as they
    are: an observed refusal is a diagnostic, and the claim stays unresolved. Then A8 (examples keep their outcomes;
    native without JBMC; the queued acceptance jobs), and step 5, the for-review list. A7's job runs meanwhile.
- Status: working

## Loop settings

- session: 051e402b-750c-4a9d-bdd2-24dfb39add84
- model: claude-opus-5-5
- effort: high
- memory: 12G
- integration: llm-dlc/tools/example-targets-integration.sh
- new-window: no

## Loop until

The reconcile comes first. Don't stop before the merge is committed, unless a stream is unfinished or the merge needs
the user. Then Phase 5. Keep the last line of Progress a status: `working`, `waiting on jobs ID ...`, `done`, or
`blocked: ...` with what needs the user. Stop with `done` once Tier A passes on the merged revision, every portfolio row
has its stated readiness, and the gap inventory and for-review list are complete. A missing core result is recorded as
partial or blocked, never as done. Don't turn the scaffolding loop into the proof campaign that follows it, and items
deferred by the timebox count as recorded deferrals, never as a reason to keep going.
