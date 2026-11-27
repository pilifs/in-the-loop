# From a Java PR link to a checked public observation

**Product implementation brief for `pilifs/in-the-loop`** · Baseline [`develop` at `5f0b23893448`][head]

Give the watcher a merged Java PR URL. It should propose a falsifiable change in public behavior, find the entry and receiver that expose it, run the same caller on the two original deployments, and show the evidence behind its verdict. If it needs the owner’s judgment, the report should identify the decision. “Both of these public observations are reachable. Which one matters to your caller?” is a better handoff than “write a harness.”

**The first release question is whether the product can recover customer intent on an unseen case.** Settle that with a frozen 20-PR draw. Use two historical misses to build trace-guided discovery, and five independently audited PRs to qualify the composed workflow. Run through the existing watcher and single-agent process. The thresholds below are proposed release targets. The historical numbers are measurements from the pinned revision.

## What we can already rely on

| Capability | What shipped | What the next run must demonstrate |
|---|---|---|
| Entry and class binding | On Log4j #1173, binary discovery ranked the correct core method second of 22 with the questions withheld. Both public questions kept API then core. The final gate reproduced 283 class bindings on 21 launch graphs. | Find a public history when a call crosses a runtime dispatch or the changed method runs later in that history. The frozen Parquet result proposed three changed writer methods and missed both nominated public histories. [Brief 22 results][r22] |
| Generated callers | With reviewed registrations, 31/31 questions on 13 cases produced complete two-sided observations. The finite evaluator established 26, refuted three, and left two open because the parent contradicted its registered baseline. Before repairs the frozen transfer observed 5/14 questions and 2/5 whole cases. | Discover and measure the intended behavior without the campaign supplying its entry, input meanings and observation fields. Earlier blind draws recovered zero registered primaries on 16 projects and zero across 44 candidate callers on 13 projects. A fresh blind run was never scored in brief 23. [Brief 23 results][r23] · [Freeze contract][freeze] |
| Corpus and URL intake | Batch audits L–R cover 165 examples (423–587) and 506 questions. P/Q/R contribute 110 PRs and 336 questions. The JSON-java #552 campaign already captured predictions and evidence before opening its upstream reference. | Measure transfer across many new cases and reproduce a whole historical batch from links alone. Example 484, Spring #36626, was explicitly used in brief 23’s transfer and repair. It belongs in development. P and Q are Spring batches, so report cross-project transfer separately. [P audit][p] · [Q audit][q] · [R audit][r] · [484 registration][mail] · [URL intake precedent][url] |

## A. Freeze the generator and take a blind draw

**First, build the smallest missing operation.** On Spring 458, pass a configured `DecimalFormat` to the public three-argument `NumberUtils.parseNumber`. Retain that exact argument, read `isParseBigDecimal()` after return, and attach both observations to the call. Compare both initial flag settings, run both revisions, and challenge the observer with a different formatter initialized to the same value and a getter moved before the call. Both planted callers must lose qualification even if every returned value agrees. A missing locale or formatter may still require review. Deliver this through ordinary numbered setup, scaffold-only and resume. [Existing setup stop][numbered] · [Review adapter][review] · [Generated caller and rescore path][gen]

Then qualify three reusable operations on disclosed cases. Design around object identity, action order and public readback. Charge every new recipe and fixture fact to development. These are the worked examples the agent **may see** before the freeze.

| Development exercise | What the caller must retain and measure | Falsifier |
|---|---|---|
| Lucene #15727, J14 | Build a parent/child index, close and reopen it, run the filtered sort, read both hit count and ordered ID/value pairs, including a missing value. Preserve the refuted historical prediction. | A fresh empty index or a projection that checks only the hit count cannot qualify. |
| Spring #37193, 466 | Construct through the accessible response interface, subscribe, and read the full ordered event sequence or the terminal error and its cause. | Reject a caller that constructs a publisher without subscribing, or reports only the inner exception. The original parent-baseline mismatch stays in the record. |
| Spring #36626, 484 | Retain a message and its copy across three mutations, sample both in order, and exercise the getter-only subclass. | A freshly reconstructed copy, or the same handle passed off as both objects, must fail correspondence. |

Use the archived calls to check development work. Build shared behavior into the existing recipe selection, review and replay modules. A switch on a PR number, an example ID or a known result fails the transfer objective. [Disclosed case histories and falsifiers][r23] · [Shared recipe selection][recipes]

### The 20-case evaluation

1. **Seal the inventory.** The evaluator starts with P 478–507, Q 508–537, and R 538–587. Join by canonical repository, PR, revision pair and aliases against previous development, frozen transfers, numbered handoffs, shared recipes and this round’s development cases. Exclude 484 and all other confirmed exposures. Also exclude R examples 539 and 551: the queued preservation and unexamined-bytecode brief reserves them for its frozen-pattern transfer, so their answer-bearing files must stay unseen (the user, 2026-11-27). Publish exclusion reasons and counts. Distinguish a new PR in a familiar project from a previously unseen project. A shared API family is worth reporting even when the PR is eligible.
2. **Freeze before drawing.** Record the source, recipe set, model/prompt if used, tool permissions, JDK/build policy, ranking rule, resource limits, and case-selection procedure. Retain the existing recipe-inspection cap of 64 or publish its replacement and rationale before the draw. An evaluator separate from the producer commits the eligibility manifest, seed and selection rule, then draws **5 P, 5 Q and 10 R** without replacement. Draw R across distinct projects where eligible. Keep every selected case in the denominator, including build failures. Use a sealed fresh context and checkout view for each case. Include the known-case trace work in the freeze if its effect will be measured on this draw. Record a denied attempt to read an evaluator-only sentinel, reusing the brief 23 isolation test.
3. **Define what “blind” buys.** For the headline attempt the producer gets the PR URL, its public description, production diff and declarations, builds, original dependencies and public API documentation. It may derive changed selectors. Keep upstream tests, test diff hunks and embedded test listings out of this first view. Strip any local example ID, historical registration, authored caller, expected value, fixture recipe, prior receipt and audit. `comparison.json` carries answer-bearing fields. Freeze a predicted behavior, public history, observable fields, one primary candidate and any ranked alternatives *before* either revision is measured. Log which upstream material was visible, including behavior disclosed in the PR description.
4. **Run two diagnostics on the same draw.** After all primary attempts are sealed, run (i) the frozen producer with original upstream tests available for tracing, and (ii) the frozen generator with a reviewed semantic registration but historical callers and evaluator outcomes withheld. Start each from the same frozen snapshot in a fresh context. These measure the gain from test evidence and from supplied intent. Preserve all three results before changing shared code. Report the paired gain or loss against the blind run on each PR. Repairs on revealed cases get a fourth column. A subsequent claim of improved blind performance requires another untouched draw.
5. **Score the top choice at the PR level.** Before unmasking, the evaluator commits one primary Intent per PR, using a deterministic rule for multiple Intent rows, and its required histories, bindings, inputs, observation fields and side scopes. Count one cold success when the selected primary is semantically equivalent and the corresponding history produces independently qualified observations and the correct finite disposition for every required side. Equivalent public routes can earn credit with evidence. Matching strings, reaching a changed body, or generating an interesting different claim earns separate diagnostic credit. Publish rank-at-three and alternate useful claims. Show all challenge/control outcomes separately.

**Ship when at least 8/20 cold primaries qualify, including at least 3/10 R primaries, and every planted false qualification is rejected.** This target requires a material gain over zero and prevents a Spring-only success. Publish exact fractions even if it misses. Per PR, show where it stopped along deployment → candidate → bound public entry → generated and old-API compiled caller → required-side reach → all fields observed → scored primary. Break out qualifying refutations, incorrect parent baselines, preparation failures, reviewed-input assistance and case-specific edits. A well-diagnosed abstention is valuable product output and still a missed cold primary. [Historical blind and reviewed scores][obs-score] · [Numbered handoff][handoff]

## B. Use traces to rank public histories

Extend the existing static ranking with evidence from the **original upstream test launch**, including child test JVMs where needed. Bind each event to revision, ordered deployment, JDK, defining loader, class digest and JVM member descriptor. Keep the raw event sequence. Link a body hit to a public operation by an observed stack edge, a later operation in the same retained history, or a qualified asynchronous handoff. Record which relationship was witnessed. Identify the outer production API boundary separately from the test runner and helper frames. Compare each traced run with a plain JVM run over the same input. Absence of a hit describes that run’s coverage. [Static discovery][discover] · [Existing JDI tracer][tracer] · [Current history checks][reach]

| Worked exercise | Acceptance on the original deployments | Negative control |
|---|---|---|
| Parquet J08, page and file histories | Withhold the nominated entry names, old callers and saved observations from the ranking process. Freeze test-selection and ranking policy first. On the original 113-root deployments, rank both the `FallbackValuesWriter.getBytes()` page history and `ParquetWriter.write` file history in a declared top five. Report static and trace-assisted rank, actual dispatch target and history relation on each side. Score nominations before revealing the ten historical observations. | The distinct-page sequence changes across revisions. The reopened-file histories agree. Both routes must earn reach credit. Repeat with the overlay reversed and show the changed binding. A reset later in the history cannot be reported as a nested call under an earlier public return. [First ranking][parquet-first] · [Physical observations][parquet-real] · [Reversed order][parquet-reverse] |
| Spring 466, detached callback | First reproduce the existing same-thread `buildEvent` under `Flux.blockLast` after `bodyToFlux` returns. In a labelled scheduler-hop exercise on the original libraries, interleave two subscriptions on a reused worker. Carry provenance from subscription/dispatch to execution and the actual changed body. Verify ordered events, completion, error and cancellation where exercised. | Add an unrelated task with the same callback class, cancel one subscription, and remove the handoff evidence. Attribute only identified invocations. A thread name, timestamp, identical payload or matching stack on a worker is insufficient. Without a causal link the detached event stays unattributed. [Spring and Lucene history receipts][r23] |

These historical cases were disclosed to the builders. Describe success as masked recovery on known cases. Publish original-test coverage gaps as such. A custom test that demonstrates the missing mechanism is a separate result. Feed the qualified ranking into ordinary Stage 2 selection and keep alternative public observations visible where the tests exercise more than one plausible claim.

## C. Qualify the composed pipeline from five PR links

Run N01–N05 from the [five-line URL list][n-list] in a fresh workspace. Use the ordinary single-agent run to pin parent and landing, build both, discover and bind the entry, register intent and scoped predictions, generate the caller, execute, and publish. Existing shared producers and dependency caches are legitimate inputs. Keep numbered example directories, case-specific scripts, prepared manifests with entry hints, tests written by the earlier campaign, and prior audits outside the producer view. Freeze results before comparison. Record test-assisted routes and every owner-supplied decision. The independent batch replay is the evaluator. [Runtime stages and commands][runtime] · [Prospective URL freeze][url-freeze]

| PR | Historical readback the evaluator must be able to compare |
|---|---|
| N01 · Commons CLI #450 | Retry a failed parse with a fresh parser against the same option definition and check the retained successful command line. |
| N02 · HdrHistogram #145 | Grow and reset, then call equality in both directions. One receiver direction throws on the parent. Include the equal-total, different-interior-count control. |
| N03 · ThreeTen-Extra #463 | Add the measured backward period back to the start date. Check the resulting epoch day against an independent ISO calculation. |
| N04 · Esri Geometry #329 | Reverse the touching line and inspect the retained edges. In the overlap case keep the measured parent outcome labelled **observed without a registered prediction**. |
| N05 · Spring JDBC #37322 | Use the original MySQL 9.1.0 sidecar and an independent connection. Distinguish rollback (durable row 98) from successful commit followed by restoration failure (100), even though both surface the same Spring exception. A missing database is a deployment stop. |

**Acceptance is semantic parity on 5/5 deployments and 17/17 historical questions.** Compare per PR, role, input/history, side, observation, scope and disposition. Expose omissions and additions. The oracle recorded 34 fresh JVM executions, seven intended changes, five unchanged controls, and 17 matching fixed predictions. Generated source and transient process identifiers may differ. A different well-founded claim may be useful while still missing historical coverage. Run the independent check with `python3 verification/merged-pr-links/audit.py --campaign n01-n05 --replay` on the prepared evaluator cache. Identical totals alone cannot pass. [N results][n-results] · [Machine audit][n-audit]

N has no fixed-side refutations. Add the M04 Commons Compress preamble offset, M06 Agrona entry/hash consistency, and M09 libGDX reused-polygon bounds as adverse controls. The historical requirements are violated on all three merged revisions. M09 also fails on the parent. Preserve the measured contradictions and their historical side scopes. This qualifies the historical regression path. For prospective transfer, report A separately. [M results and witnesses][m-results]

## D. Advance strict proof only where the evidence supports it

Check the current queue and results at execution start. At this review, brief 24 had an `add` entry and a committed brief, with no published results on `develop`. Its documented POI #1420 stop is Log4j enumerating the **live system-properties table**. A reported POI timezone write needs its own original evidence. Reuse any startup-fact work that has landed by execution time. A captured launch timezone and the behavior of a mutable process default between calls are distinct obligations. A–C can proceed independently. [Queue][queue] · [Brief 24][startup] · [Recorded initializer profile][obs-native]

| Opportunity | Smallest credible qualification |
|---|---|
| Log4j #1173, process timezone | Reproduce strict `UpgradeProbe#schedule()Z` on both original classpaths. The recorded first read is `TimeZone.getDefault()` in `UpgradeProbe.observe`. Qualify the consumed operations under pinned JDK/profile, testing default reads, change/restore and isolation of the returned object where used. Replay the eight histories crossing GMT+10/GMT−10, explicit/omitted zone and ordinary/time-based scheduling. Preserve the four refuted explicit predictions and four holding controls. Publish the strict outcome or exact next gap, and reject a swapped profile. Claim strict closure only when the original query decides at its stated scope. [Strict refusal][zone] · [JVM profile evidence][zone-jvm] |
| Commons IO #520, native helper | Re-run the strict generated `CheckedHelperUse` query for the six actual `Math.min(II)I` tuples. The existing finite basis supports two questions and records 14/20 old/new applications for rewinds and 10/10 for preservation. The archived native query names its first failure, `class not found: java.lang.Math`, while the finite certificate binds `java.base`. Start by resolving the actual runtime-image class in the native lemma query. Bind the executing helper bytes and show which substitutions the native checker consumed. A missing used row should reopen its dependent question. A wrong value, wrong binding or absent consumption must fail qualification. Preserve the existing finite evidence if strict remains unverifiable. [Archived native query and finite certificate][helper-receipt] · [Helper qualification][helpers] |
| Stock JBMC, VF-071 | On JDK 21, qualify the actual stock invocation’s selected versioned **subject and helper**, verify 5 and refute 3. Preserve the JDK 8/17 base value 3, earlier-shadow winner and paired/equivalence guards. Keep the current refusal wherever backend binding cannot be demonstrated. [Stock binding finding][vf71] |
| Custom loaders and ambiguous intent | Example 333 has 16 two-call sequences on each of three revisions. Reproduce child/context selection, restore the loader after success and failure, and distinguish original byte reads 65/66 from compensating reads that both return 65. For an unknown physical layout ask for the missing URL-to-artifact mapping. For two qualified but semantically different observations, show both and request the owner’s choice. Preserve the exact native limitation until its delegation rule is qualified. [Loader evidence][loaders] · [Binding handoffs][r22] |

## Deliver through the watcher

Use ordinary Stage 2 review, Stage 3 `scaffold_example.py bind` / `generate`, numbered `build.py` resume, and the change-plan replay, receipt verification and rescore paths. Extend shared modules where the product consumes the evidence. Keep corpus selection, hidden registrations and audits in the evaluator. Persist the producer revision, assistance level, data visible at each stage, before/after bindings, caller source and bytecode digests, fixture and JDK identities, rank and provenance, raw observations, predicate identity and exact reason for every open result. [Runtime contract][runtime] · [Observer generator][gen] · [Entry discovery][discover]

The watcher result should answer four questions. What behavior did the product predict? What did each original revision do? Which claim does that establish or refute? What still requires a decision? Show cold, test-assisted, reviewed and repaired scores side by side. Distinguish a JVM observation, a finite adjudication, a profile-conditional result and a strict backend verdict. Repeat a clean and a warm run, change an oracle alone to rescore identical raw evidence, and replace a relevant JAR or fixture to require a fresh dependent observation. Report manual facts and caller edits, candidate inspections, test/JVM launches and cache actions. Call a gate met only on its own evidence. If A misses while B or C passes, publish both outcomes and the first recurring cause of missed cold primaries.

[head]: https://github.com/pilifs/in-the-loop/tree/5f0b2389344879610f907ac9ee5b048dd59c9df8
[r22]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/llm-dlc/loops/in-the-loop-classpath-and-entry-discovery-brief-results.md
[r23]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/llm-dlc/loops/in-the-loop-generated-observers-and-callers-brief-results.md
[freeze]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/generated-observers/freeze.json
[p]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/merged-pr-links/p01-p30/audit.json
[q]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/merged-pr-links/q01-q30/audit.json
[r]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/merged-pr-links/r01-r50/audit.json
[mail]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/generated-observers/registrations/484.json
[url]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/llm-dlc/loops/organic-java-pr-capability-composition-fast-follow-results.md#one-prospective-url-intake
[numbered]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/generated-observers/receipts/numbered-input-stops.zip
[review]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/examples/tools/targets/observer_review.py
[gen]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/examples/tools/targets/observer_generation.py
[recipes]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/examples/tools/targets/observer_recipes.py
[obs-score]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/generated-observers/scorecard.json
[handoff]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/generated-observers/numbered_handoff.py
[discover]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/examples/tools/targets/entry_discovery.py
[tracer]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/examples/tools/targets/java/UpgradeTrace.java
[reach]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/generated-observers/history_reach.py
[parquet-first]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/classpath-entry-discovery/parquet-first.json
[parquet-real]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/classpath-entry-discovery/parquet-observations.json
[parquet-reverse]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/classpath-entry-discovery/parquet-reversed.json
[n-list]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/llm-dlc/loops/organic-java-merged-pr-links-n01-n05.md
[runtime]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/llm-dlc/runtime.md
[url-freeze]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/lib/benchmark/organic-composition/url-only/before-reference.json
[n-results]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/llm-dlc/loops/organic-java-merged-pr-links-n01-n05-brief-results.md
[n-audit]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/merged-pr-links/n01-n05/audit.json
[m-results]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/llm-dlc/loops/organic-java-merged-pr-links-m01-m10-brief-results.md
[queue]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/llm-dlc/loops/queue.jsonl
[startup]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/llm-dlc/loops/in-the-loop-jvm-startup-facts-brief.md
[obs-native]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/lib/src/observed.rs
[zone]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/classpath-entry-discovery/log4j-strict.json
[zone-jvm]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/organic-composition/log4j/processes.json
[helpers]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/examples/tools/targets/change_helpers.py
[helper-receipt]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/generated-observers/receipts/io-helper.zip
[vf71]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/findings.md#vf-071-stock-jbmc-requires-qualification-for-an-active-versioned-application-class
[loaders]: https://github.com/pilifs/in-the-loop/blob/5f0b2389344879610f907ac9ee5b048dd59c9df8/verification/classpath-entry-discovery/loaders.json

## Setup Agent Notes

### What is ready, and where

- **The whole draw inventory, P 478–507, Q 508–537 and R 538–587, is checked**: every deployment file matches its
  `runtime.json` digest, the JDKs match, and there is a worktree at each pin
  ([Examples: deployments and pins](#examples-deployments-and-pins); rows in
  `~/.cache/in-the-loop/blind-caller-pr-verification/logs/examples.json`). The caches are
  `~/.cache/in-the-loop/{spring-pr-links-p01-p30,spring-pr-links-q01-q30,merged-pr-links-r01-r50}`, with worktrees
  `worktrees/P01-{parent,fix}` … `Q30-…`, `R01-<project>-{parent,fix}` … `R50-…`.
- **N01–N05** (examples 453–457, `~/.cache/in-the-loop/merged-pr-links-n01-n05`) and the adverse controls **M04, M06,
  M09** (examples 446, 448, 451, `~/.cache/in-the-loop/merged-pr-links-m01-m10`) are checked the same way. The MySQL
  sidecar image `mysql@sha256:0255b469f0135a0236d672d60e3154ae2f4538b146744966d96440318cc822c6` and Connector/J 9.1.0
  are in place ([N01–N05 setup notes](organic-java-merged-pr-links-n01-n05-brief-setup.md#setup-agent-notes)).
- **Development cases**: 458, 466 and 484 read `runtime.json` against `~/.cache/in-the-loop/spring-pr-links-o01-o20`
  (458, 466) and `~/.cache/in-the-loop/spring-pr-links-p01-p30` (484). J14 (Lucene #15727) reads
  `verification/product-behaviour/cases/J14/bindings.json` under `~/.cache/in-the-loop/organic-pr-20`.
- **Part B upstream test launches, in a plain JVM (no Gradle or Maven)**:
  - Spring 466: `~/.cache/in-the-loop/blind-caller-pr-verification/scripts/o09_upstream_test.sh TESTROLE CLASSROLE JDK [OUT]`
    compiles and runs `ServerSentEventHttpMessageReaderTests` on the kept 202-entry spring-web test classpath
    `~/.cache/in-the-loop/spring-pr-links-o01-o20/artifacts/O09-{fix,parent}/spring-web.testRuntimeClasspath.txt`,
    with the JUnit console 6.1.2 at `~/.cache/in-the-loop/blind-caller-pr-verification/releases/junit6-console/lib/junit-platform-console-standalone-6.1.2.jar`.
  - Parquet J08: `~/.cache/in-the-loop/blind-caller-pr-verification/scripts/j08_upstream_tests.sh {compile ROLE | classpath ROLE GRAPH | run ROLE GRAPH [selectors]}`.
    The compiled `parquet-column` and `parquet-hadoop` test trees of both pins are in
    `~/.cache/in-the-loop/blind-caller-pr-verification/upstream-tests/J08/{fix,parent}/`, and run over the original
    113-entry graphs of `verification/product-behaviour/cases/J08/bindings.json`. Commands and digests are in
    [the J08 section](#parquet-3638-j08-the-upstream-test-trees-over-the-original-113-entry-graphs).
- Log4j #1173 and Commons IO #520 read `lib/benchmark/organic-composition/{log4j,io}/{old,new}/prepared.json`.
  Jar digests are in [Other inputs](#other-inputs-j08-j14-log4j-1173-commons-io-520).
- JDKs 8, 11, 17, 21.0.13 and 25.0.5 are in `~/.sdkman/candidates/java/`; the default `java` is 25.0.5. JBMC 6.11.0
  is at `/usr/bin/jbmc`. `lib/target/release/jvmcontract` is current at `524b1fbd9277032681921afbeac09d218d156147`
  (sha256 `aa6a6e26a770316bd80bd3c2c9d1f67ed55e1f7b3fa77a90fe3854ad7e7e69c6`). Identities are in [Tools](#tools).

### What was verified on a JVM

- The registered observations of 458, 466, 484, J08, J14 and Commons IO, re-run in fresh JVMs on the original
  deployments, equal the committed receipts ([What was run](#what-was-run-on-a-jvm)).
- Spring 466's landed test, on JDKs 25 and 17: the fix's test passes on the fix (14/14) and fails on the parent only in
  `ignoreInvalidRetry`, with `NumberFormatException: For input string: "none"`. The parent's test passes on both (13/13).
- Parquet J08: the landed `TestDictionary` passes on the fix graph (24) and fails on the parent graph in
  `testDictionaryWriterReusableAfterFirstPageFallBack` and `testDictionaryWriterReusableAfterFallBack`. Upstream
  `TestParquetWriter` (31 tests, the public file path) passes on both graphs.
- Example 333 validates.
- **Job `20261127-032247-setup-replay-the-p-q-r-n-and-m-public-ob` passed.** Every historical P, Q, R, N and M
  observation was replayed in fresh JVMs on the original deployments at `5c57e715acb8e32f1ed7fc1dc2f7ba684882837c`,
  including the MySQL 9.1.0 and Postgres 17 sidecars. Each audit equals its committed `audit.json` byte for byte. The
  110-case draw inventory, N01–N05 and the M controls are re-run, not only digest-checked.
- **Job `20261127-032259-setup-run-parquet-3638-s-upstream-parque` passed.** Parquet's whole `parquet-column` and
  `parquet-hadoop` suites (138 classes) ran on the original 113-entry graphs, fix on fix, parent on parent, and fix on
  parent. The fix-on-fix and parent-on-parent failure lists are identical. Fix-on-parent adds exactly the two landed
  `TestDictionary` tests. The 24 failures and 24 aborts common to both pins are causes of the deployment, listed in
  [the whole suites](#the-whole-suites-job-2-passed).
- One of those shared failures was this setup's own: `TestParquetWriterError#testInSeparateProcess`, whose child JVM
  got only the launcher jar as its classpath. The launch now uses `-cp`, and a probe shows the test passing on the fix
  graph (57/57 with `TestDictionary` and `TestParquetWriter`). On the parent graph, only the two landed tests fail.
- Both results are in commits that this line has not merged: `dc6fd6c8f17f` and `2c45066adba0` (the latter also
  holds the first). `pipeline.py status` lists both jobs as "in commit 2c45066adba0 … merge it".

### What to know before starting

- **Producer-view hygiene.** These all hold historical callers, receipts or actual outcomes:
  - the examples' `caller/`, `observations.json` and `comparison.json`;
  - `verification/merged-pr-links/*/audit.json` and `repeated-audit.json`;
  - `verification/product-behaviour/cases/J*/{case,physical}.json` and `UpgradeProbe.java`;
  - this setup's `~/.cache/in-the-loop/blind-caller-pr-verification/probes/` and `logs/replay-*`, `physical-*`, `io-observe.txt`.

  The worktrees hold the upstream tests and test diffs, which the brief keeps out of the first blind view. The compiled
  test trees under `upstream-tests/` are upstream tests too: they belong to the test-assisted diagnostic and part B,
  not to the headline attempt.
- **J08's test launch is over overlays, not a pin build.** The pins' build needs a `thrift` 0.23.0 binary. The graph is
  the pin's two changed `parquet-column` classes (8 overlay classes) over released Parquet 1.18.2, Hadoop 3.3.0 and an
  unshaded fastutil 8.5.19. The upstream `parquet-hadoop` tests run against 1.18.2's `parquet-hadoop`, not the pin's.
  Label trace evidence from it that way. `brotli-codec` 0.1.1 (runtime-only, not on Central) is absent. The six
  network `InterOpTester` classes are left out of the job.
- **Which upstream tests run usefully on J08's graphs.** 24 tests fail on both pins for reasons of the deployment, not
  #3638: 20 from version skew against 1.18.2 (NaN counts, float16, column orders), one from the missing Brotli codec,
  two from heap at the default `-Xmx`, and `TestParquetWriterError#testInSeparateProcess` from the old launch, now
  fixed. A further 24 abort because Hadoop 3.3.0 has no vectored IO. A selection policy should treat these as
  coverage gaps of the overlay, and they are listed by name in each run's `summary.txt`.
- Launch J08 tests with `j08_upstream_tests.sh run` or `j08_suite.sh`. Both now start the console launcher from
  `-cp`, so a child test JVM inherits the whole classpath. A tracer that must follow a child JVM needs the same
  `java.class.path`.
- **Spring 466's classpath has snapshot dependencies**: `reactor-core` and `reactor-test` `3.9.0-SNAPSHOT`, and
  micrometer `1.18.0-SNAPSHOT` on the P cases. They are fixed bytes, digest-checked, from the O, P and Q setups'
  Gradle homes. Do not re-resolve them. Gradle's test JVM for O09 was JDK 25 with `--release 17`; example 466's
  runtime is JDK 17. The landed test behaves the same on both.
- `$R/worktrees/R47-picocli-parent` (example 584) reports 18 `docs/*.html` files as modified. They differ only in line
  endings, and no source differs ([details](#examples-deployments-and-pins)).
- R05 (542) and R09 (546) have two deployments each (`jre`, `android`). R39 (576) and R42 (579) are overlays: R42's
  pinned build cannot be configured from public sources
  ([R setup](organic-java-merged-pr-links-r01-r50-brief-setup.md)). Examples 518 and 457 start Docker services.
- `zero-allocation-hashing-0.27ea1.jar`'s signature could not be checked; only its sha1 matched Central.
- Brief 24 (JVM startup facts) has landed at this head, so part D can reuse it. Job
  `20261126-200411-replay-log4j-public-entry-bindings-and-s` failed and is not setup's to fix.
- Run `public_comparison` as `PYTHONPATH=examples/tools python3 -m targets.public_comparison NNN`: the plain script
  path fails on its import. `validate_example.py 333` takes about 3 minutes. pytest is not installed; use `unittest`
  or `lib/tools/test_costs.py`.

### What is left for the domain work on purpose

- Everything the brief builds or measures:
  - the retained-argument operation on 458 and its planted callers;
  - the three development exercises;
  - the sealed inventory, the exclusions, the freeze, the seed and the draw;
  - the blind, test-assisted and reviewed attempts, and scoring;
  - trace-guided ranking and the scheduler-hop exercise;
  - the N01–N05 fresh-workspace run;
  - every part D qualification.
- Choosing which upstream test classes the trace launch uses (the policy to freeze), attaching the tracer
  (`examples/tools/targets/java/UpgradeTrace.java`), and the plain-JVM comparison runs.
- What goes into each producer view, and what stays with the evaluator.
- Any example ids, registrations, scaffolds or claims.
