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
compiles; a one-sided replay no longer counts as reproduced (`witness.rs:812-820`). Temurin JDKs 8, 11, 17, 21 and 25 are installed
(21 and 25 the main targets, 25 the default; the main brief's JDK rule).

Phase 0 delivered (2026-11-09; the main brief's [Phase 0](example-targets.md#phase-0-interfaces-hooks-and-fixtures)):
`examples/tools/targets/runtime.py`, whose `prepare`, `run_controls` and `run_verifier` are stubs returning
`Unsupported` for you to replace, behind the frozen types in `interfaces.py` (a `TaskPlan`'s `artifacts` entries tell
you each revision's route and sources); the fixtures (`targets/fixtures/`, with `build_fixtures.py`, which the fixture
route builds with); and the contract rows that are yours, A2 and A3/A4 on the fixture, and A5's runtime half, in
`examples/tools/test_targets_contract.py`. They stop at your stubs now, and your work turns them into passes.

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
a JDK it supports, selected by its full path under `~/.sdkman/candidates/java/`. Original sources stay untouched; adapters compile separately. Record
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

Each relevant revision runs in its own JVM and classpath, on JDKs 21 and 25 wherever its artifacts do, and otherwise on
the JDK it needs. The case's independently authored oracle checks the security
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

- **Yours**: `examples/tools/targets/runtime*`, `test_runtime.py` (rewrite its stub tests as you replace each stub), your
  other focused tests and fixtures in files of your own, and example numbers 315–319 if you need any.
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

- Forked after the main brief's [launch prerequisites](example-targets.md#launch-prerequisites), Phase 0 included, on
  2026-11-14.
- 2026-11-14, **R1 on the fixture route**: `runtime.lock(plan, revision)` (new, offline: the source lock, every
  selected source, adapter, driver and oracle path inside the folder, links included, and hashed; nothing fetched or
  built) and `runtime.prepare()` for `route: fixture` (build_fixtures.py's recipe, byte for byte, with the JDK it
  would use resolved to its real home; the original, adapter, driver and oracle hashed; the ordered classpath; the
  target's origin; `prepared.json` in the work directory). It refuses, as `failed` with its stage, diagnostic and the
  artifacts that exist: a class on more than one classpath entry (`classpath`), a target method the original doesn't
  declare (`target`), an adapter that never references the target method (`adapter`), a compile failure (`build`),
  sources changed between lock and build, and a work directory that isn't an earlier preparation's (`workdir`).
  `published-artifact` and `upstream-build` return Unsupported (not a Phase 0 stub) until R2. New modules
  `runtime_jdk.py` (installed JDKs by full path, identity from `release` and `java -version`) and `runtime_jar.py` (a
  small class-file reader). Contract A2: 3 pass. `test_runtime.py` rewritten: 19 tests.
- 2026-11-14, **R4 on the fixture route**: `runtime.run_controls()` runs each revision's driver in its own JVM, on its
  own prepared classpath, on each JDK its artifact entry names (`jdks`, else the one it was built with), by full path,
  on the oracle's `PROBES`. The JVM gets a fixed environment (`C.UTF-8`, UTC, en-US, UTF-8 streams, `-Xmx512m`) and
  inherits nothing, `JAVA_TOOL_OPTIONS` and `CLASSPATH` included. Each record names the JDK (`java -version`, home,
  `release`), the commit, every classpath entry with its sha256 and role, the driver, where its inputs came from (the
  oracle and its hash), the environment and flags, and `replay: original-jvm` (`model` once a `stub` artifact is on
  the classpath). Before a JVM starts, the classpath's bytes are rechecked against the preparation. These give a
  `not-started` record, never a skipped one: a revision with no preparation (one-sided), one that isn't
  artifacts-ready, bytes changed since preparation, a `prepared.json` that isn't the PreparedTarget given, a missing
  JDK, and a JDK older than the classes (from their class-file version). A kill, a timeout (`CONTROL_TIMEOUT`, 120 s),
  a line that isn't a JSON object, and inputs missing or out of order give no observations; exit 1 with complete
  output stays raw, its exit code kept. Nothing here applies the oracle. `controls/controls.json` says why each record
  without observations has none. The lock now names the driver's main class. Contract A3/A4: 2 pass (contract: 8 pass,
  8 skip, 6 at workflow's stubs and A5's 2 for want of `jvmcontract`). `test_runtime.py`: 28 tests. The integration
  script exits 0.
- **Interface request** (for the merge; `interfaces.py` is the coordinator's): `PreparedTarget` doesn't carry its work
  directory, so `run_controls` finds the preparation by `route.py`'s layout (`<attempt>/prepare/<revision>` beside
  `<attempt>/controls`) and runs it only if its `prepared.json` is the PreparedTarget given. An additive
  `workdir: Optional[str] = None` would remove the convention. It isn't in `source`, because that would put a
  temporary path into what claims are bound to.
- For review (workflow's W2): a killed record's `exitCode` is the negative signal, as `build.py`'s stages record it
  (`-9`). The constructed `bad-runs.json` record has `None`. Either way `status` is `killed`.
- 2026-11-14, **R2's published-artifact route**: `lock()` and `prepare()` take `route: published-artifact`. The lock
  is offline. It needs the revision's full commit, kept as recorded linkage beside any `tag` and `release` and marked
  unchecked against the bytes. It also needs the JAR's `coordinates`, `url` and `sha256`, and each declared dependency
  under `dependencies`, in classpath order. The lock refuses:
  - a dynamic or mutable version (a range, `+`, LATEST, RELEASE, a SNAPSHOT);
  - a missing or malformed sha256;
  - a URL that isn't https on Maven Central or github.com;
  - a Central URL that names another file;
  - an artifact listed twice.

  Preparation acquires each JAR through the new `runtime_maven.py`:
  - it uses a content-addressed cache (`~/.cache/in-the-loop/targets`, or `TARGETS_CACHE`) and rechecks every
    restore. A corrupt entry is moved aside, reported and fetched again;
  - on a miss it fetches into a new empty directory, over https, following redirects only to github's content hosts.
    It checks the bytes against the lock before caching or using them. Different bytes fail at `acquire`, uncached and
    unbuilt;
  - it fetches only when the plan's `network` allows. Otherwise it uses the cache alone.

  The cache and fetch log (`logs/acquire.log`) stays out of `source`, so a cache hit gives the same PreparedTarget.
  Each JAR is an Artifact with its coordinates and origin URL. The classpath is driver, adapter, original, then the
  dependencies in order. The fixture route's checks apply: shadowing across dependencies, the target method and the
  adapter's call. Every failed preparation now carries `source.blocker`: stage, command, diagnostic, needed semantics
  and next action (the acceptance's handoff row). A missing hash's command is the one that records it:
  `python3 -I examples/tools/targets/runtime_maven.py pin G:A:V`. That command fetches the JAR from Central, checks
  it against Central's `.sha1`, caches it and prints the sidecar entry. `test_runtime.py`: 39 tests, against a local
  stand-in for Central. They cover:
  - a lock that fetches nothing;
  - classpath order and origins;
  - a cache hit and a corrupt cache entry;
  - a hash mismatch;
  - eight lock blockers;
  - a shadowing dependency;
  - `network: false`;
  - both published revisions' controls on JDK 21 and 25, read by the fixture's oracle.

  The integration script exits 0: contract 8 pass and 8 skip, targets suite 79, `test_build` 190, `test_pipeline` 29.
  Note, not evidence: `pin org.springframework:spring-core:5.3.19` fetched the real JAR, sha256 `1af06bd4…7992`, and
  it matched Central's `.sha1`.
- **Interface request** (workflow's W1, `plan_task`): a published revision's `artifacts` entry should carry:
  - the history's `commit`, and its `tag`/`release`;
  - the JAR's `coordinates`/`url`/`sha256`;
  - its other `preparation.artifacts` items as `dependencies`, in classpath order. The sidecar allows several items
    per revision, and the TaskPlan has one entry per revision;
  - `network: true` on the plan.
- For review: the blocker sits in `source` because PreparedTarget has no field for it. An additive
  `blocker: Optional[Mapping] = None` would be cleaner. The dependency closure is what the lock declares: no POM is
  resolved (no Maven emulation). A missing dependency shows up as a NoClassDefFoundError in the controls, which is a
  replay failure, not a result.
- 2026-11-14, **R5's slice**: `runtime_slice.py` runs one small published upstream method end to end, with
  `runtime_simplematch/` as its case folder. That folder isn't an example and isn't in the router; its plan uses 315,
  from this stream's range. The method is `PatternMatchUtils.simpleMatch(String, String)` from spring-core 5.3.18 and
  5.3.19. The sidecar:
  - is a valid `example-target/v1`;
  - names the release tags by full commit, checked with `git ls-remote` (`707a24c4…`, `cedb5874…`);
  - pins each release's spring-core JAR and spring-jcl, its one compile dependency per its POM, by URL and sha256.
    `runtime_maven.py pin` recorded each sha256 and checked it against Central's `.sha1`.

  The adapter only calls the method. The driver reads each input as a JSON pair of strings or nulls. The oracle is
  written from the Javadoc: 45 probes, covering nulls, every pattern style, adjacent stars, backtracking, case, a line
  break, regex metacharacters and a non-BMP character.

  The path: the sidecar becomes the TaskPlan asked of W1, then `prepare` (acquisition, the checked cache, the adapter
  and driver built, the classpath checked), then `run_controls`, then `workflow.ingest`, called as `route.run` calls
  it. Ingestion is still W2's stub, so it answers Unsupported.

  Run inline, once from an empty cache (all 4 JARs fetched from Central and checked) and once `--offline`:
  - both releases are artifacts-ready, the target loaded from spring-core's JAR;
  - each release's driver ran in its own JVM on JDK 21 and 25: 4 records, each exited 0 with 45 observations and no
    oracle problems;
  - JDK 21 and 25 agree on each release.

  Tests, `test_runtime.py` 43 (4 new):
  - the sidecar is valid and both releases lock offline;
  - offline with an empty cache, preparation is a blocker at `acquire` with its command and next action;
  - the oracle isn't vacuous: it rejects five plausible wrong implementations, and a missing probe raises;
  - the end-to-end slice runs from a private copy of the four cache entries. It is skipped, never faked, when the
    cache lacks them.

  The fixture half of R5 is R1, R2 and R4's (the fixture JARs on both routes). The integration script exits 0:
  contract 8 pass and 8 skip, targets suite 83 (the slice's end-to-end test ran, offline), `test_build` 190,
  `test_pipeline` 29.
- Found (for review, the negative and positive streams): `org/springframework/util/PatternMatchUtils.class` is
  byte-identical in spring-core 5.3.18 and 5.3.19 (sha256 `8562b278…ff28`). The CVE-2022-22968 fix changed
  `DataBinder`, not this method, so a binder packet that reaches `simpleMatch` has the same callee on both sides.
- **Note for the positive stream and Phase 5, what 105's migration needs from runtime.** Taken from 105's `README.md`
  and `example.json`, not checked against upstream:
  - **Revisions.** The recorded run compared the PR's head `79aa4643` with `e7c172d2`, the commit the squash merge
    landed on. Both are short SHAs, so the sidecar needs full ones. Neither is a release, so the published-artifact
    route can't serve that pair. The published route could serve a release pair of `commons-numbers-core`, such as
    the release before and after the fix, but only once the positive stream shows that `pow(int, int)` is the change
    between them. That would be a different pair, not the recorded one.
  - **Build route.** The PR pair needs the upstream-build route: Maven, through the revision's wrapper if it has one,
    otherwise a pinned Maven distribution fetched by hash, which the route doesn't do yet. 105's historical run
    compiled `ArithmeticUtils.java` alone with `javac`, because its sandbox refused the Maven build. Reused, that is
    an extracted source slice, not original bytecode, and needs that scope label.
  - **JDK and classpath.** The bytecode targets an old release. The controls can run on 21 and 25. The method is
    `int`-only and has no dependencies, so the classpath is the one JAR. A fixture-shaped `int` driver fits, with
    `pow(-2, 31)` as the trigger and `k` in {-1, 0, 1} as legitimate inputs.
- 2026-11-14, **R3's `run_verifier`** replaces Phase 0's stub. It runs `jvmcontract` on the prepared original
  artifacts only, never the adapter or driver, and returns one raw `verifier` ExecutionRecord.
  - A prove task runs `prove` on its revision's original JAR, with the dependencies on the classpath in order and
    the claim's assume, assert, throws, nullable and may-alias. An equivalence task runs `equivalence` between the
    pair's originals, `--unchanged-unless` the task's allowed change. Its revision is None.
  - Both get the plan's `--engine` and `--gaps` (a missing one is refused, never the CLI default), the claim's bounds,
    its construction plan and gap contracts (each rechecked against the claim's sha256), and `--json`. The paths are
    relative to the attempt directory, the verifier's cwd. The claim keys are the ones workflow's W1 `plan_task`
    gives.
  - The environment is fixed and recorded as the controls' is. The JDK is 25 when every revision runs on it, given
    by full path in `JAVA_HOME` and `PATH`. Only the runner's `JVMCONTRACT_*` memory settings pass through.
  - Recorded in `identities`:
    - the jvmcontract digest, the JDK, the engine, gaps and bounds;
    - each revision's commit and its verifier classpath, with sha256s;
    - the **scope**: a label (`original-bytecode`, `original-bytecode-under-models`, `constructed-mutation` or
      `constructed-fixture`), the loaded class with its sha256 and origin, the models and assumptions, and the note
      that the adapter isn't on the verifier's classpath;
    - the **capability probe**: `jvmcontract gaps` on each revision, a static scan that proves nothing, with its
      argv and the gaps it lists.
  - Raw, as the controls are. These give a `not-started` record: a one-sided pair, a revision that isn't
    artifacts-ready, bytes changed since preparation, a missing JDK. A kill, a timeout (600 s, jvmcontract's own, plus
    120 s grace) or output that isn't the `--json` outcome gives no observations.
  - These are Unsupported, not stubs, because the task can't be attempted as stated: a replay or compare task, a
    missing engine or gap mode, claim models (no route passes them yet), a bound with no option, a claim file changed
    since it was frozen, an equivalence pair whose dependency closures differ (one classpath for both), no built
    jvmcontract (with the build command), and a work directory that isn't ours.
  - `verifier/verifier.json` keeps the record.
  - `test_runtime.py`: 51 tests. The stub test is gone, and 8 verifier tests run against a stand-in jvmcontract that
    records its argv, cwd and environment, because no proof runs inline. One of them shows the job's reading isn't
    vacuous: a "verified" for a refuted task, and a refusal that doesn't name `java.util.regex`, are both not as
    expected.
- **Found and fixed while dry-running the job: the fixture's `regex-probe` failed preparation at `adapter`.** The
  fixture's one adapter calls `Gate.allowed`, not the probe's `RegexGate.allowed`. After the merge, contract A5's
  regex-probe row would have failed on runtime's check. Now:
  - a replay task's adapter must still call the target (its controls are the task's evidence);
  - a proof task records which original methods its adapter calls (`adapterCalls`, `adapterCallsTarget`) instead,
    since its verifier never goes through the adapter;
  - `run_controls` doesn't run controls whose adapter doesn't call the task's target. They give `not-started`,
    because they aren't the task's evidence;
  - shadowing is refused for every task, as before.
- A `mutant` entry in the plan (workflow's W1 constructed mutants, `zvnrtxsunllx`) is now Unsupported in `lock`. It
  isn't a Phase 0 stub, and it never prepares the base unpatched.
- **The calibration job**: `runtime_calibrate.py` runs the fixture's five proof tasks through `prepare` and
  `run_verifier` with the real jvmcontract, native and strict, and hands each record to `workflow.ingest`. Until W2,
  that answers Phase 0's Unsupported. Each task's claim is a stand-in: the properties workflow's
  `fixtures/claims/*.json` state on its branch, in its `plan_task`'s claim keys. Expected:
  - `vulnerable-security` and `mutant-security`: a violation;
  - `fixed-security` and `preservation`: verified;
  - `regex-probe`: unverifiable, naming `java.util.regex`.

  Dry runs inline, with no jvmcontract and with a stand-in, exercised the plumbing. Queued as job
  `20261114-162937-example-targets-runtime-r3-run-verifier`, which also runs the contract with `JVMCONTRACT` set, so
  A5 gets past its skip and stops at workflow's task-plan stub. Its result is pending. The integration script exits
  0: contract 8 pass and 8 skip, targets suite 91, `test_build` 190, `test_pipeline` 29.
- **For the merge** (workflow's W1, seen read-only on its branch). A published revision's entry carries its JARs as
  `published` (a list, with `coordinates`/`url`/`sha256` copied up only when there is one). `lock` reads the first
  item plus `dependencies`, as asked under the interface request above. Runtime should accept `published` as well,
  in order: the original, then the dependencies. That is the next small piece.
- Interface request, for review: the verifier can't yet go *through* an adapter (an instance method whose receiver
  only the adapter can construct, for example). The claim schema has no key that names an adapter entry point.
  Until it has, such a task needs a construction plan (`--plan`) or stays a capability gap.
- 2026-11-14, **W1's `published` list accepted**: a published revision's entry may now carry its JARs as workflow's
  W1 gives them, `published` in classpath order (the original first, then the dependencies), a lone item's keys copied
  up. The earlier shape (the original's keys on the entry, `dependencies` beside them) still locks, to the same lock.
  Refused at `lock`: both lists at once, an empty or malformed list, and a copied-up key that isn't the first item's.
  The slice now builds W1's shape. `test_runtime.py`: 52 tests. The slice's end-to-end run passed offline from the
  cache.
- The integration report of 2026-11-14 16:28 shows the streams conflicting only in generated files
  (`llm-dlc/README.md`, `llm-dlc/index.json`, `llm-dlc/traces/README.md`, `llm-dlc/traces/metrics.json`), none of them
  runtime's: the script didn't run. Nothing to coordinate from here; `sync.py` regenerates them.
- Read-only over the case streams' sidecars: 105, 305 and 307 use `upstream-build` (Maven, the Maven wrapper and the
  Gradle wrapper, on JDK 11, 8 and 8). No sidecar declares a mutant yet. So the upstream-build route comes before
  mutant preparation.
- 2026-11-14, **the calibration job failed: VF-024** (`20261114-162937-example-targets-runtime-r3-run-verifier`, at
  `b397033c`, 45 s, collected as `orwvprts`). Its contract step passed (8 pass, 8 skip). No task got its expected
  verdict, for three reasons, each now handled:
  1. **Parameter names, a Phase 0 inconsistency.** `build_fixtures.py` compiles without `-parameters` or `-g`, so the
     fixture's classes record no parameter names, and jvmcontract calls `Gate.allowed`'s parameter `arg0`. Phase 0's
     own sidecar (`allowedChange: "code == 97"`) and workflow's claim files say `code`, and RegexGate's say `field`.
     So the three security tasks, and preservation's `--unchanged-unless`, aren't well-formed for Phase 0's bytes.
     Contract A5's fixture rows will fail the same way at the merge. Runtime can't fix it alone: the fixture route
     must reproduce `build_fixtures.py` byte for byte, which contract A2 checks. Changes:
     - `_fixture_recipe()` now also takes an optional `JAVAC_FLAGS` from `build_fixtures.py`, and every javac of the
       route gets those flags;
     - the verifier's scope records, per revision, the target's parameter names and where they come from
       (`MethodParameters`, the `LocalVariableTable`, or nowhere). These are the names a claim can use. New
       `runtime_jar.parameter_names`, read as jvmcontract reads them.
  2. **Equivalence wants class directories** (`Not a directory`). `run_verifier` now extracts each side's original
     JAR into `verifier/classes/<revision>`, records the extraction (`identities.classes`), and passes those. A test
     checks the extracted classes match the JAR byte for byte, and refuses an entry outside the JAR's root.
  3. **regex-probe refuses before it reaches the regex.** The strict proof stops at the `String` parameter ("a value
     adapter is built for it, but this check doesn't take one yet"). The capability probe (`jvmcontract gaps`, in
     `identities.probe`) names `Pattern.compile`, `Pattern.matcher` and `Matcher.matches`. The verdict,
     `unverifiable`, is the expected unresolved. The calibration now reports `refusalNamesRegex` and
     `probeNamesRegex` apart, and needs one of them.
  - **Request for the merge (the coordinator, `build_fixtures.py`):** add `JAVAC_FLAGS = ("-parameters",)` and pass
    it to its javac. Runtime follows automatically, and the fixture JARs' hashes change in both places alike.
    Otherwise, workflow's claim files and Phase 0's sidecar would have to use `arg0`.
  - For review: the fixture's capability refusal is named by the probe, not by the proof's own refusal. A strict
    proof through `java.util.regex` would need a String-parameter check first.
  - Rerun as job `20261114-164239-example-targets-runtime-r3-after-vf-024`. Its calibration runs with
    `--fixture-javac-flag=-parameters`, recorded as that variant in `calibration.json` and in every preparation's
    recipe. It is the calibration of the asked-for recipe, not of Phase 0's bytes. Its contract step runs on Phase 0's
    bytes. `test_runtime.py`: 55 tests (3 new: the reader across no flags, `-g` and `-parameters`; the escaping
    entry; and recipe flags reaching javac, giving other bytes and recorded names). The integration script exits 0:
    contract 8 pass and 8 skip, targets suite 94 (run before the escaping-entry test was added), `test_build` 190,
    `test_pipeline` 29.
- Next:
  1. The rerun's result (`20261114-164239-example-targets-runtime-r3-after-vf-024`).
  2. The upstream-build route, with 105's pinned revisions as its job.
  3. Prepare a constructed `mutant` (its base patched, then built), on the upstream-build checkout first.
- Status: working

## Loop settings

- session: 3bb5a1f4-a4d5-4f4a-b511-6037ef3e1256
- model: claude-opus-5-5
- effort: high
- memory: 12G
- workspace: example-targets-runtime
- fork: e9be5afb-09c9-4473-a9e9-38f2fb61ca80

## Loop until

Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with
`waiting on jobs ID ...`. Stop with `done` when R1–R5 and your acceptance pass, or each is deferred by the timebox with
the finding. Stop with `blocked: ...` when what is left needs the user or another stream, and is recorded under
Progress. Don't grow into general Spring emulation or a broad CVE campaign. Anything new you find goes under Progress,
for the main brief's for-review list.
