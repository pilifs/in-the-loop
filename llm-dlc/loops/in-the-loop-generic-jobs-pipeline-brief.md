# One jobs pipeline for setup, builds, tests and verification

**Implementation brief for `pilifs/in-the-loop` · November 27, 2026**  
Reviewed against [`develop` at `b52a084f5d11`][head]. The repository now has one development workflow, one run controller and one job queue. Build on that architecture. [Architecture and open capabilities][arch]

## Outcome

A domain agent reaches a Maven integration task that setup never exercised. It submits **one request naming the task and its required output**. The runner resolves the prerequisites, then proves the prepared inputs suffice by running that task offline in a clean work area. Other cases keep moving. The watcher can tell what ran, which inputs were fetched, which attempts failed, which revision produced each artifact, and whether the original question received an answer.

Deliver a general-purpose job interface, a complete account of every submitted job and execution attempt, and an on-demand setup path. The acceptance test for generality is that a non-Java job can use the same submission, scheduling, artifact, reporting and retry services on a host with no checker installed.

## Start by protecting the data already here

I joined the committed job paths, result directory IDs, and root plus daily result indexes on the pinned revision. The figures below are migration fixtures. They describe the **collected Git snapshot**. Host-local attempts, uncollected work and private archive contents have different sources. [Layout rules][layout] · [Root index][index] · [November 27 index][day]

| Snapshot check | Measured baseline |
|---|---|
| Job IDs, result-directory IDs, indexed result IDs | **1,906 in each set**, zero duplicates or unmatched IDs. Every index path points to the corresponding result directory’s `result.json` location. |
| Collected outcomes | **1,469 passed, 420 failed, 17 error**. Of the 172 November 27 rows, 105 passed, 62 failed and 5 recorded an error. Passing jobs can still carry attention flags. |
| Layout compatibility | Three November 22 jobs have **flat specs and dated results**. Joining on the parent directory or guessing a path from the date loses them. Use the layout resolver and join by ID. |
| Timing coverage | One preparation failure recorded **41 seconds elapsed**, a failed step at index zero and **zero requested-step wall seconds**. Its index entry uses the latter. Both numbers make sense once their scope is visible. [Original receipt][prep-time] |

**Exercise two evidence-retention risks before moving the entry point.** On retry, `capture.begin` may return no attempt after failing to rescue an interrupted run, and the runner subsequently clears the old run directory. Separately, pruning asks whether the latest *captured* workdir for a job was remotely verified. That can be an older attempt if a newer capture failed. The snapshot establishes ID parity. Whether either failure has cost historical bytes is unknown. [Retry][retry] · [Capture][capture] · [Prune][prune] · [Archive query][archive-lookup]

Give each execution a durable attempt identity before writing its first outputs, even when private capture is unavailable. A retry gets its own directory or moves the previous bytes intact to an identifiable recovery location before reuse. Prune only when the exact attempt and content to be removed have a matching collected receipt and verified remote occurrence under the archive policy. A failed capture must produce a durable, visible recovery state. Simulate a full spool, a runner kill and an older verified occurrence. Show that the latest bytes survive restart and that successful recovery restores the expected digest. Keep private originals and restricted access under the existing archive owner.

## 1. Give ordinary work a generic contract

Introduce a neutral entry point such as `jobs/pipeline.py` and update the watcher and idle-queue skill to use it. The path is a design suggestion. **One implementation must still own admission, claiming, execution, collection and reporting.** The current pipeline already accepts ordered shell steps, expected exit codes, budgets, outputs and a pinned source revision. Keep those strengths. Move numbered-example preparation, Java/checker discovery and build, proof-signal parsing, and proof-specific post-collection work behind the verification workload. Make their outputs available as typed evidence. [Current CLI][runner] · [Job contract][job-spec] · [Result contract][result-spec] · [Queue keeper][keeper]

| Generic responsibility | Workload responsibility |
|---|---|
| Job and attempt IDs, submitter/run/phase, case or batch, source identity, prerequisites, resource estimates, permitted environment, declared steps and outputs | What a Gradle task, Maven goal, Python test selector or checker invocation means |
| Claim once, schedule when ready, record blocked/unschedulable/deferred reasons, enforce budgets, capture outputs, retry and supersede | Qualify an offline dependency set, verify which tests executed, extract a proof verdict, or validate a produced artifact |
| Publish lifecycle, measured resource use, output digests and evidence links | Publish the scoped interpretation, such as “named tests executed” or “preservation claim refuted” |

Keep workload **purpose** (resolve, build, test, verify, maintenance) distinct from project, tool and capability labels. Allow a simple job with one command and no dependencies. Preserve the v1 formats, explicit revision and implicit source-commit selection, `--example` / `--task`, existing commands, configuration overrides, archive coordinates and historical links through compatibility adapters. Update both keeper paths and process detection together. One still-running legacy runner and a new CLI in another workspace must share the same exclusion mechanism. Keep old records in place. Moving a pending spec can change the revision the old runner infers. [Existing runner lock][lock] · [Process detection][pid] · [Run skill][skill]

Add manifest fan-out through ordinary submission. Validate a whole batch, bind stable row identities to job IDs and publish the map. Concurrent or interrupted submission of the same manifest must converge. Revisions, task selections or inputs that change get distinct work identities. A retry of the same job and a new job that supersedes an old spec remain distinguishable. Provide a typed way to watch the named batch while the existing queue-wide wait continues to work. Use a 49-row fixture with one blocked case, one expected failure and a resubmission. Independent rows must finish and appear in the report.

## 2. Make missing data visible at the point of use

Build a single versioned, machine-readable lifecycle view, then render CLI, watcher, batch and historical reports from it. Today `status --json` contains formatted strings, the keeper parses prose to reconstruct state, and `report` starts from collected receipts. Cancelled work is normally eligible to run again and excluded from automatic collection. Keep that scheduling behavior and include each attempt in history. [Status][status] · [Collector][collect] · [Report][report] · [Keeper adapter][keeper]

| What the reader asks | Evidence the pipeline must retain or explicitly mark unavailable |
|---|---|
| What became of every submitted case? | Batch row and admission outcome, uncommitted versus committed work, prerequisite IDs, queued/blocked/deferred reason, current claim and host, attempts, cancellations and supersessions. A corrupt spec gets a diagnostic carrying its path and revision. An unknown queue read cannot mean idle. |
| What actually ran? | Planned and executed steps including preparation, expected exit policy, timing, exit/signal/timeout/OOM/stop reason, skipped steps and why. Record actual test suite, executed count and the evidence source for a step promising tests. Keep compile-only steps valid. Record an expected failing assertion without turning it into a build failure. |
| What was produced? | For each declared output, distinguish required, optional, present and unchanged, added/modified/deleted, missing and never reached. Bind its digest, source, producer attempt and downstream consumer. A missing required output precludes fulfillment even if the process exited zero. |
| Can the result be recovered and trusted? | Keep execution, fulfillment, capture, collection, application/conflict, hook result, commit/publication and domain conclusion separate. A successful job can refute a claim. A successful process with a failed publication hook still needs attention. Store archive occurrence IDs, capture state and verified digest without publishing restricted content. |
| What did the work cost? | Report queue and prerequisite wait, resolution/fetch, preparation, build/test/proof and total elapsed time where measurable. Preserve CPU, peak memory, host and measurement source. Use measured zero, unknown and partial explicitly. Show overlapping parallel wall time as elapsed plus per-attempt work. Model spend belongs to a linked run and is reported once where available. |
| What can the reporter see? | Emit the snapshot revision, queue heads, hosts included and whether live, collected and archive views were available. A result on another head has its own state. An inaccessible machine or private occurrence leaves an explicit gap. Give each aggregate a denominator, its unit and a drill-down to its rows. |

**Reconciliation is a deliverable.** Provide a read-only audit command that joins expected batch rows, committed specs, live claims/attempts, local terminal records, collected receipts, indexes and permitted archive metadata. Recompute indexes from authoritative records. Flag duplicate identities with different content, stale/missing index rows, orphan receipts, malformed inputs, missing attempt links and missing required artifacts. Preserve historical records and label any provenance gaps that cannot be reconstructed. Make status/collection outputs structured enough that keepers need no regex over English. Before migration, generate a manifest of paths and Git blob IDs for every committed spec, receipt and collected output. Include archive occurrence IDs and digests where access permits. During migration compare old and new views and verify the manifest against Git and the available archive. Exercise collection interrupted after copying bytes and again after committing them. Retrying must finish publication once and preserve the source bytes. Release only after all 1,906 baseline IDs, outcomes and paths reconcile, and deliberate corruption, cancellation and interrupted collection produce the expected discrepancies. [Index and report code][report] · [Collector and post-collection hook][collect] · [Metrics semantics][usage]

## 3. Let a running case request more setup

**Spring Boot S48, example 635, PR #51551.** Initial setup prepared the tasks known then. Later, the domain investigation needed the original Spring Boot Maven plugin integration harness. Its `createResolvedBom` stage needed ActiveMQ BOM 6.1.8, retained cache contents exposed a zero-padded hash issue, and `prepareMavenBinaries` needed the Maven 3.9.13 distribution. Five investigation rounds consumed about 45 minutes. The first round split parent and fix, so the committed results contain **six job IDs, five failed and one successful**. The successful job measured four real WARs and corroborated two already-counted questions. [VF-076][vf76] · [S48 results][s48] · [Replay][replay] · [Successful job][war-job]

Use a deterministic **task-level resolution job** as the default recovery. The consumer declares the operation it needs, such as building and inspecting the upstream plugin’s WAR on both pins. It should not have to guess the first missing coordinate or ask a model to rerun setup for each transitive dependency.

1. **Describe readiness precisely.** Bind revision, module, task/goal and profiles, wrapper and toolchain, repositories and configuration, relevant platform, required outputs and the consumer. Distinguish a task graph that configures, dependencies that resolve, artifacts that build, integration tests that actually run and a packaged result that can be read.
2. **Admit one logical request.** If the initial setup already certified this exact operation, link and reuse its receipt. Otherwise place only the affected consumer in a prerequisite-wait state. The watcher admits the resolution job through the same scheduler. Only an authorized fetch phase gets the configured repository/network access. A missing, drifting or unverified historical artifact receives a named outcome.
3. **Resolve the actual task graph.** Include BOMs, build plugins and their dependencies, test configurations, generated artifacts, nested Maven/Gradle invocations and tool distributions when the requested operation uses them. Allow bounded internal discovery rounds with progress and diagnostics. Partial discovery is a legitimate outcome. Detect cycles and repeated no-progress states. Use isolated staging, verify digests and publish completed bundles atomically. One failing concurrent consumer must not poison the shared cache.
4. **Prove the handoff offline.** Use a clean worker with only the pinned inputs and prepared bundle available. Run the original consumer under demonstrably disabled network access, with no inherited mutable cache. Record the exact task, artifacts and evidence of the offline condition. A build-tool offline flag alone cannot constrain scripts or a nested tool that downloads its own distribution. Preserve substituted or reconstructed inputs as separately qualified evidence. [Existing replay and pinning][replay]
5. **Resume and account once.** Wake the original consumer on a matching readiness receipt. Record every resolution attempt and both pins. Deduplicate identical prerequisites across cases without conflating different toolchains or profiles. Report preparation attempts separately from the count of original domain questions answered.

**Pass condition.** Replay S48 from an initially insufficient cache. One logical request must get the original task ready on both revisions and a fresh offline consumer must independently read four WARs. On the parent, both readbacks must show the absent manifest pointers and payload. On the fix, both must identify CycloneDX at `WEB-INF/classes/META-INF/sbom/application.cdx.json` and read the original bytes, including when a decoy entry appears first. Withhold the BOM from all authorized sources, supply a wrong Maven digest, and simulate an unavailable repository on a cold cache in separate controls. Each must report the failing stage and withhold readiness. An unrelated runnable job must finish during the wait. A failed consumer process per missing artifact fails the recovery gate. Cheap setup-only probes beneath the one request are expected. [Parent readback][parent] · [Landing readback][fix]

## Findings to retain in the implementation

| Finding | How to use it |
|---|---|
| **VF-076 and VF-070** | Use the S48 on-demand gate above and the separate S-batch initial-setup control. All 98 task-graph dry runs configured. Yet 41 of 49 initial jobs failed for setup reasons, including 38 offline misses. R49/R50 also demonstrated passing steps with zero tests. Verify task-specific readiness and suite evidence. Preserve legitimate transplant failures, absent historical inputs and reasons a signature could not be verified. [Setup record][s-setup] · [Findings register][findings] |
| **VF-072 and VF-069** | Manifest fan-out, typed named-batch completion and watcher-owned continuation replace handwritten lane scripts and self-matching process waits. A normal setup export and a producer isolated from its evaluator are distinct capabilities. Keep sealed producer execution an explicitly qualified profile. |
| **VF-051 and VF-060** | The shared jj-store lock and the conflict check at export already have tests despite the historical open headers. Preserve them across the rename. Exercise the old and new CLIs from two workspaces, and ensure a conflicted source is visible as a refusal with no payload executed. Update a finding’s current disposition only against its stated closure evidence. [Regression tests][tests] |
| **VF-020, VF-029 and VF-030** | Use oversized diffs, intentionally uncollected cancellations and fail-fast skipping as historical controls. Preserve compressed/stat-only public representations and their original references. A withdrawn job or a test after the failing step cannot acquire a passing result during backfill. [Findings register][findings] |
| **VF-025** | The original warning about three 1.4 MiB JARs was corrected by inspecting the collect commit. Use their Git blob identities to distinguish worktree presence, commit inclusion and remote publication. [Corrected finding][vf25] |
| **VF-077, VF-078 and VF-079** | Keep public projections within the existing redaction and publication policy. Carry an explicit originating run ID on newly submitted jobs and distinguish it from the source revision and collector. Historical timing alone cannot establish authorship. Report missing publication or cost explicitly. Run-session billing and the interpretation of legacy trace lines remain with their existing owners. [Findings register][findings] |

## Clean up scripts without breaking replay

Inventory executable files under `verification/` and their callers before moving them. Classify each as shared runner code, workload adapter, test, supported campaign replay, historical-only tool, compatibility entry point or orphan candidate. Inspect CLI strings in committed job specs, queued specs, dynamic imports, manifests, hooks, skills, docs, tests and any external consumers the repository declares. Record the owning consumer or retirement basis, last usable revision and replay check. A lack of Python imports is weak evidence here.

Two controls prevent expensive mistakes. **All five scripts in `verification/triage/` have explicit historical job callers.** The merged-PR qualification test also modifies its import path to load campaign-local `audit.py` and `qualify.py`. Retain active replay paths. For a genuinely superseded script, use the existing retirement register with a replacement or last working revision, and show pinned replay still resolves. Extend the retirement check’s live-path coverage to the new jobs namespace. Delete only confirmed orphans in a separate reversible change. An inventory with zero justified removals is an acceptable result. [Historical triage job][triage] · [Dynamic imports][qual-test] · [Retirement procedure][retired]

## Sequence and release gates

1. **Protect and measure.** Freeze the corpus census, add the archive-failure and retry tests, and implement the reconciliation report. Run it on the pinned corpus plus a small faulty fixture before migrating the entry point.
2. **Switch one queue.** Prove the generic path with a non-Java artifact-producing job, a real build/test job, and a verification job whose checker refutes its claim. A 49-row manifest interrupted and submitted twice must produce exactly 49 ordinary job IDs. Keep the compatibility path through a full watcher submit → run → collect → report cycle and demonstrate rollback with a job in flight.
3. **Qualify delayed setup.** Pass S48 plus a synthetic nested Gradle/Maven fixture whose second stage discovers a previously unknown prerequisite. Share only identical verified requests, reject stale bundles, and show unrelated work finishing during the wait.
4. **Tune from measurements.** Separate fetch-bound admission from CPU/memory scheduling. Start with the architecture’s suggested configurable ceiling of ten fetch-bound tasks, accounting for subtask concurrency. Record queue wait, fetch throughput, cache reuse and local work before changing it. Use those measurements to decide whether remote execution is worth adding under the same contract. [Capacity direction][arch]
5. **Adopt and verify.** Update `ARCHITECTURE.md`, operator guidance, schemas, fixtures, producer and consumer commands together. Record corpus parity, deliberately detected discrepancies, S48 outcomes, retired scripts and remaining unknowns. On the next natural large batch compare avoidable consumer retries, unexplained cases, missing telemetry, offline readiness, capture failures and elapsed time to first useful result. The default views must let a reader explain every case, including the ones that never ran.

[head]: https://github.com/pilifs/in-the-loop/tree/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3
[arch]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/ARCHITECTURE.md
[layout]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/layout.py
[index]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/results/index.json
[day]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/results/2026/11/27/index.json
[prep-time]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/results/2026/11/27/20261127-054106-trace-individually-approved-ordinary-ups/result.json
[retry]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/pipeline.py#L1049
[capture]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/capture.py#L144
[prune]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/pipeline.py#L1755
[archive-lookup]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/llm-dlc/tools/artifacts.py#L613
[runner]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/pipeline.py
[job-spec]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/schema/job.schema.json
[result-spec]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/schema/result.schema.json
[keeper]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/llm-dlc/tools/queue_keeping.py
[lock]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/pipeline.py#L1531
[pid]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/pipeline.py#L1451
[skill]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/.claude/skills/run-verification/SKILL.md
[status]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/pipeline.py#L1644
[collect]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/pipeline.py#L1797
[report]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/pipeline.py#L1907
[usage]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/pipeline.py#L1305
[vf76]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/findings.md#L125
[s48]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/llm-dlc/loops/spring-boot-merged-pr-links-s01-s50-brief-results.md#L95
[replay]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/merged-pr-links/s01-s50/maven-war/replay.py
[war-job]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/results/2026/11/27/20261127-145103-read-both-original-maven-wars-with-a-pin/result.json
[parent]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/merged-pr-links/s01-s50/maven-war/parent.json
[fix]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/merged-pr-links/s01-s50/maven-war/fix.json
[s-setup]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/llm-dlc/loops/spring-boot-merged-pr-links-s01-s50-brief-setup.md#L481
[findings]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/findings.md
[tests]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/test_pipeline.py
[triage]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/jobs/20261108-091002-vf-023-s-second-probe-which-ingredient-o.json
[qual-test]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/test_merged_pr_qualification.py
[retired]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/llm-dlc/retired.md
[vf25]: https://github.com/pilifs/in-the-loop/blob/b52a084f5d11fbf34f82d7a8cce1ea39938afdd3/verification/findings.md#L2006
