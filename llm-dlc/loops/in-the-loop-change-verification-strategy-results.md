# Verification results for an application change

The change planner found both Retrofit converter directions in the built module and reproduced their different outcomes through Retrofit's public factory. All six incremental evaluations matched clean recomputation. The held-back Petclinic migration exercised a real validation and persistence path and exposed a startup failure specific to the old binary on the new runtime. [Runner and commands](../../lib/benchmark/change-verification/README.md) · [Frozen evaluation](../../verification/change-verification/evaluation.json)

In the inspected comparator, the empty slice passed to `effects::check_builds` selects all discovered entry IDs. The new planner supplies each ordered launch through `jvmcontract observations --classpath` and compares the resulting specifications with `--against`. A matched declaration yields an obligation. Its verdict comes from a qualified execution or proof receipt. [Comparator](../../lib/src/compare.rs) · [Entry filter](../../lib/src/effects.rs) · [Launch inventory](../../examples/tools/targets/change_inventory.py)

## Original callers and the next change

| Case | Original-scope result | Evidence |
|---|---|---|
| Example 345, 12 primary claims | Five established and seven refuted. Each of the four positive controls held. Fresh JVMs returned wrong complete pages on 68, 40, 48 and 0 of the 96 inputs for parent/parent, fix/parent, parent/fix and fix/fix. | [Importer evaluation](../../verification/change-verification/importer.json) |
| Wire response, registered | Both deployments decoded the historical phone number and the short companion correctly. | [Public response invocations](../../verification/change-verification/wire/response.json) |
| Wire request, additional | The old converter wrote both expected protobuf messages. The new converter threw `java.lang.NoSuchMethodError` from the original request method for both. | [Public request invocations and escaping frames](../../verification/change-verification/wire/request.json) |

The Wire inventory found five methods. The two typed converters had finite observers. Three factory operations still need their own domains and observations. The production classpaths contained five and eight artifacts, and the separate test launches contained eleven and fourteen. The planner graded the two converter directions against the historical receipts after discovery and execution. The V3 historical denominator and its 8/12 expansion gate remain separate. [Discovery and matrix](../../verification/change-verification/wire/summary.json)

| Wire update | Original JVM sides executed, out of four | Incremental wall | Independent clean wall |
|---|---:|---:|---:|
| Cold | 4 | 16.49 s | 16.32 s |
| Exact | 1 | 7.68 s | 16.99 s |
| Test-only resource | 1 | 7.52 s | 16.65 s |
| Production resource | 2 | 10.94 s | 16.81 s |
| Okio 1.15.0 first | 2 | 10.39 s | 16.59 s |
| Okio 2.4.1 first | 2 | 8.89 s | 15.42 s |

The exact rerun reused both reads and the old write. It replayed the new write at the public entry. A production resource or a classpath-order change reopened both new-side observations. Putting Okio 2.4.1 first restored the writes on the attribution control. The measured production migration uses Retrofit's selected Okio 1.15.0. Each row includes planning, classpath binding, observer preparation, cache handling and JVM execution. The receipt also records CPU and peak process RSS. [Wire measurements](../../verification/change-verification/wire/summary.json)

On 345, a CSV-only change reused all 24 isolated IO facts. An IO change recomputed the 24 IO facts and all 12 reachable CSV inputs. An unrelated class edit reused both producers. Both artifact fixes were necessary for all complete pages to agree. Changing which duplicate IO and CSV providers appeared first also reproduced the clean reference streams byte for byte. Across all these controls there were zero incremental/clean disagreements. The positive conclusions cover the frozen domains and runtime assumptions in the respective plans. [Importer measurements](../../verification/change-verification/importer.json)

## Held-back migration

We selected Spring Petclinic's upstream migration from POM history, and registered three workflows, example form inputs, accepted differences and resource limits before inspecting the application. Both deployments used Temurin 17. The original POMs target Java 8 and Java 17 class files. The final measurements use their Maven resource and compiler goals, then run the resulting production classes on the original ordered graphs. Each launch used one loopback web server, a fresh H2 database, English locale, UTC and disabled DevTools restarts. Coverage is the owner form, validation response and saved-owner readback. [Registration](../../lib/benchmark/change-verification/petclinic.json) · [Upstream migration](https://github.com/spring-projects/spring-petclinic/commit/1315cf6e1f1e88e4850e5573388a89ba4469df07)

| Deployment question | Result |
|---|---|
| Original client and runtime | All three workflows passed, including the rejected form and the valid owner retrieved by both ID and last name. |
| Original binary on the Boot 3 runtime | Startup failed because the application owner class was not a managed entity. The two business workflows stayed open. |
| Unchanged source against the new graph | Compilation failed on removed `javax` persistence and validation APIs. |
| Adapted client and runtime | All three registered workflows passed. The comparator found all four participating HTTP route declarations on both revisions. Other discovered routes have explicit open dispositions. |

The cold full-process run took **39.53 s**. The exact rerun took **13.53 s** against **28.91 s** for clean recomputation with the same populated Maven cache, a **53.2% reduction**. Both rebuilt all production sources, resolved the two graphs, and repeated unchanged-source compilation. The exact run reused the two successful deployments and repeated the failed mixed startup. Every registered verdict, typed observation, execution key and scope agreed. [Full-process cost and receipts](../../verification/change-verification/petclinic-cost.json)

| Petclinic pass | Aggregate CPU | Peak process RSS | Application preparation |
|---|---:|---:|---:|
| Cold | 63.82 s | 319.1 MiB | 15.81 s |
| Exact | 23.00 s | 240.9 MiB | 5.46 s |
| Clean | 54.20 s | 310.2 MiB | 5.30 s |

This migration meets the equal-coverage cost gate on its three frozen workflows with zero contradicted assurances. The sample is one held-back application and one paired timing on this machine.

The earlier measurement of both clients compiled for Java 17 is retained as a separate control. A first attempt failed in the Python HTTP observer after compiling both applications. The corrected attempt and the original-target measurement keep their own receipts. Tooling and adapter work was performed in this run. The persistent records contain the observation code and the intent decisions. Per-claim human and inference effort is unmeasured. [Earlier deployment control](../../verification/change-verification/petclinic.json) · [Application entries and shared startup prerequisite](../../verification/change-verification/petclinic-plan.json)

## Checker routes and trust

The 15 Java semantic families were rerun on all 60 frozen statements, followed by stock receiver construction, nine physical check sites and the original CSV receiver. Strict native established 33, refuted 24 on the JVM and left three open. Integrated JBMC established seven and refuted 17. Two other positive JBMC answers contradicted the original JVM and remain identified as such. The plan preserves whether each generated site was reachable separately from its failure query. The earlier 23-case receiver cohort still has 34 open unrestricted paired overloads. [Qualified per-node portfolio](../../verification/change-verification/portfolio.json)

All 16 Spring primary claims have finite JVM decisions. Eight have direct ordinary-native decisions, increasing to ten with the two startup counterexamples. The bean-state and error-ledger roots on the same release binding share their first open operation. Solving it calls for two ordinary-entry retries. For Petclinic, starting the actual application is the shared prerequisite for validation and persistence. Each has its own HTTP and database observations. [Spring and receiver portfolio](../../verification/change-verification/portfolio.json) · [Petclinic dependency edges](../../verification/change-verification/petclinic-plan.json)

The independent Guava checker re-established the public first-match theorems for both `Ints` and `Longs`, conditional on successful initialization. The bounded SAT experiment independently checked all eight Guava and ten prefix-sum UNSAT queries. A modified historical producer accepted a heap-writing method and reproduced its own false result. The independent checker found the store at PC 25, with the JVM confirming that input `[7]` became `[0]`. The planner records each formula certificate at its query and the method theorem at its Java entry. [Trusted-kernel evidence](../../lib/benchmark/trusted-kernel/README.md) · [Fault control](../../lib/benchmark/trusted-kernel/historical-frame-control.json)

| Frozen task | CaDiCaL | Bitwuzla word encoding | Disposition |
|---|---:|---:|---|
| Eclipse fixed insertion return | 17.76 s | 11.60 s | Established on both |
| Eclipse parent insertion contents | 6.94 s | 3.06 s | Refuted and replayed on both |
| Importer fixed/fixed monolithic page | 61.01 s | 68.16 s | Both reached the 60 s checker limit |

The times include the caller attempt and witness handling. Each task shared 1.60–1.83 s of preparation. The experiment supports an opt-in word-level retry for the measured Eclipse cases. The importer gained its complete conclusion from its checked partitions. Each timing is one trial on the shared runner. [Equal-scope solver receipts](../../verification/change-verification/solvers/summary.json)

The historical organic scorecard now reproduces byte for byte. Its six primary cases retain 39/46 strict-native and 46/46 finite decisions. A current recount includes the later JavaParser startup-conditioned receipt. [Pinned receipt trees](../../lib/benchmark/organic-java/receipt-set.json) · [Published scorecard](../../verification/organic-java-pr-campaign.json)
