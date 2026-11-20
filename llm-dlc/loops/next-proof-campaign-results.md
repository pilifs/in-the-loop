# Java proof campaign results

The campaign met all four objectives. Across the 14 original examples, 70 of the 99 frozen claim/subject pairs were established and 29 were refuted. All accepted routes agreed. The two holdouts and the 23 earlier startup obligations have their own denominators. [Per-claim ledger, receipts, first blockers and job results](../../verification/next-proof-campaign-results.json)

## Which dependency fixed the page

The application was compiled once against the declared CSV build dependencies. A clean pipeline checkout reproduced the entire observation matrix. Each configuration ran with one of the two full Commons IO builds and one of the two full Commons CSV builds, with Codec fixed. Strict native checking established five of the 12 primary claims and refuted seven. All four positive controls were established. These receipts use Temurin 21.0.13+9, successful JDK class initialization, and the standard system properties table with permitted reads. The decoder checks the possible property values that select its lock policy.

| Commons IO | Commons CSV | Wrong bytes / 96 | Wrong count / 96 | Wrong complete page / 96 |
|---|---|---:|---:|---:|
| Parent | Parent | 48 | 40 | 68 |
| Fix | Parent | 0 | 40 | 40 |
| Parent | Fix | 48 | 0 | 48 |
| Fix | Fix | 0 | 0 | 0 |

All seven independent native counterexamples reproduce at selector 6. Request the first row at record number 2 after previewing and resetting the two-row input. The CSV parent returns an empty page with either IO build. With CSV fixed and IO old, record 2 has fields `["a","ba","b"]`. With both fixed, it has `["a","b"]`. The fixed/fixed native proof covers all 96 inputs. [Application report, artifact provenance and costs](../../examples/345-paged-importer-upgrades/README.md)

The cold finite-JVM comparison took 2.408 s inlined and 3.502 s with checked IO and CSV stages, including their initial cost. An isolated byte client depends on IO alone. In a separate native comparison, the CSV-only update took 0.437 s on the full classpath and 0.084 s with the isolated byte proof reused, including fresh JVM witness replay. Both strategies agreed with an independent clean native recomputation in every scenario. [Finite producer and consumer timings](../../examples/345-paged-importer-upgrades/records/composition.json) · [Native classpath and cache comparison](../../examples/345-paged-importer-upgrades/records/native-preview/20261120T220835Z-91167742/result.json)

## Results by original example

Each numeric cell gives established / refuted. The strict native column includes ordinary checking and complete case analysis over the admitted selectors, on the original classpath. JVM witness only counts counterexamples without an exhaustive or native decision. The scoped startup proofs appear in their own table below. A dash means this route supplied no decision.

| Example | All routes | Exhaustive JVM | Strict native | Compiled schedules | JVM witness only | Scope |
|---|---:|---:|---:|---:|---:|---|
| [332 · Paper property and initialization](../../examples/332-paper-initialization/README.md) | 5 / 1 | 5 / 1 | 5 / 1 | — | — | Nine fresh JVM property sequences per version |
| [333 · ServiceLoader and context loaders](../../examples/333-service-context-loader/README.md) | 7 / 2 | 7 / 2 | — | — | — | Real descriptors and provider construction on two successive loads |
| [334 · Toronto gaps and overlaps](../../examples/334-calendar-offset-transitions/README.md) | 4 / 2 | 4 / 2 | — | — | — | Twelve appointments under two process defaults |
| [335 · Guava signed mean](../../examples/335-guava-signed-mean/README.md) | 2 / 2 | — | 2 / 2 | — | — | All signed int and long pairs |
| [336 · Guava first int-array match](../../examples/336-guava-first-array-match/README.md) | 6 / 2 | — | 6 / 2 | — | — | Lengths 8 and 64, plus an induction certificate for all lengths |
| [337 · JDK range fill through aliases](../../examples/337-jdk-range-fill-alias/README.md) | 4 / 4 | — | 4 / 4 | — | — | Lengths 8 and 64, plus an unbounded frame consumed by the caller |
| [338 · Commons IO reset and EOF](../../examples/338-commons-io-bom-reset/README.md) | 5 / 1 | 5 / 1 | 5 / 1 | — | — | 36 streams per revision with implicit and explicit reset |
| [339 · Commons CSV record numbers](../../examples/339-commons-csv-page-numbers/README.md) | 5 / 3 | 5 / 3 | 5 / 3 | — | — | 24 combinations per revision including repeated hasNext |
| [340 · TreeList after a rejected edit](../../examples/340-treelist-rejected-edit/README.md) | 7 / 1 | 7 / 1 | 7 / 1 | — | — | 112 rejected edits and the same pre-existing iterator |
| [341 · UTF-8 chunk boundaries](../../examples/341-utf8-chunk-boundaries/README.md) | 5 / 1 | 5 / 1 | 0 / 1 | — | — | 5,578 partitions. The native per-chunk violation also replays on the original |
| [342 · Two-thread tickets](../../examples/342-two-thread-tickets/README.md) | 5 / 1 | — | — | 5 / 1 | — | Six bounded schedule properties |
| [343 · JDK synchronized-map reservations](../../examples/343-synchronized-map-reservations/README.md) | 5 / 1 | — | — | 5 / 1 | — | Six bounded schedule properties on the real wrapper |
| [344 · Seat and audit identities](../../examples/344-seat-schedule-reduction/README.md) | 1 / 1 | — | — | 1 / 0 | 0 / 1 | One bounded schedule proof and one original JVM counterexample |
| [345 · Paged importer](../../examples/345-paged-importer-upgrades/README.md) | 9 / 7 | 9 / 7 | 9 / 7 | — | — | 12 primary claims and four positive controls |

There are 65 exhaustive-JVM decisions and 65 strict native decisions, with overlap. Ordinary native checking accounted for 52 of the latter. Complete native case analysis added 13. The compiled schedule checks separately established 11 properties and refuted two. The remaining named-seat control was refuted by an admitted JVM counterexample.

## Arithmetic, heap state and schedules

Guava’s released `LongMath.mean` satisfies a signed 65-bit sum-and-shift specification over all 2¹²⁸ ordered input pairs. The independent JVM oracle uses BigInteger. Guava’s `Ints.indexOf` was proved at both bounded milestones and for every non-null, already allocated legal array. The checked bytecode maintains a prefix with no match, preserves the heap, verifies every exit, and decreases the signed measure `length − cursor`. [Guava mean](../../examples/335-guava-signed-mean/README.md) · [First-match disassembly, SMT and solver answers](../../examples/336-guava-first-array-match/records/array-induction/first-any-length)

For `Arrays.fill`, the arbitrary observed index can lie inside or outside the half-open write range, on an alias or a distinct root. The caller proof reads the actual range forwarded to the JDK. Widening it by one cell generated a satisfiable failing postcondition. A real JVM confirmed that the changed caller produced `[9,9]` for `[4,5]` and the range `[0,1)`. The released caller preserved the second cell. [Fill, caller and invalidation checks](../../examples/337-jdk-range-fill-alias/records/array-induction)

With two platform threads, one call each, fixed allocations and sequentially consistent execution, the synchronized ticket method and block were linearizable. Splitting the read and write returned ticket 1 to both callers and left the counter at 1. On `Collections.synchronizedMap`, the evaluator followed the wrapper’s compiled methods and resolved its mutex to the wrapper itself. An enclosing lock yielded one shared-slot winner. Per-method locking permitted two successes and final size 1. The private HashMap delegate was checked against a real JVM transition table for the two named keys and owners. The receipts cover completed calls and record blocked terminal states and the gate-erased JVM traces. [Ticket histories](../../examples/342-two-thread-tickets/records/monitor-histories) · [Map histories and delegate table](../../examples/343-synchronized-map-reservations/records/monitor-histories)

Exhaustive exploration, identity-aware reduction and an independent sequential oracle agreed on all 12 two-worker corpora and all 36 real JVM histories. With two calls each and a shared audit, reduction cut transitions from 6,186 to 4,002 while wall time rose from 0.031 s to 0.057 s. The by-name control lost 136 of 206 labeled outcomes. The three-worker, one-call extension produced 90 distinct-seat, 198 aliased-seat and 342 shared-audit outcomes. All three algorithms agreed. The live JVM replays cover the two-worker corpus. [Measured two- and three-worker sets](../../examples/344-seat-schedule-reduction/records/schedule-reduction)

## Original startup obligations

Each original and its recorded-startup companion ran again at its frozen bounds. A candidate from a scoped native refutation was admitted against its original guard and assertion in a fresh JVM with no injected initialization. Five originals were refuted this way. The 18 positive results still require the recorded startup conditions. ThreeTen’s observed companion uses unwind 32 and the original uses 16.

| Original subject | Original claims | Refuted on original JVM | Original still open | Recorded-startup established / refuted | First remaining dependency |
|---|---:|---:|---:|---:|---|
| [310](../../examples/310-threeten-complete-hours/records/original-witnesses) | 5 | 1 | 4 | 4 / 1 | ThreeTen chronology service discovery |
| [321](../../examples/321-jfreechart-empty-series-range/records/original-witnesses) | 8 | 2 | 6 | 6 / 2 | JFreeChart process default time zone |
| [327](../../examples/327-joda-monthday-distance/records/original-witnesses) | 10 | 2 | 8 | 8 / 2 | Joda-Time provider property |

The original monolithic searches reach `ServiceLoader.load(Class)`, `TimeZone.getDefault()` and the initial read of the Joda provider name respectively. The service-loader and zone fixtures settle their complete frozen JVM grids. A broader native result requires a checked loader/resource and provider-construction model, or an argument that the observer is independent of those choices. For explicit zones, the corresponding experiment is to bind native lookup to the selected zone-data bytes and prove that changing the process default leaves the observer invariant. For Joda-Time, the next experiment is to trace whether the property-selected provider can affect the frozen MonthDay observations. Proving independence there would discharge the assumption for those positive claims. [Service-loader bindings](../../examples/333-service-context-loader/records/loaders.json) · [JDK image and zone data](../../examples/334-calendar-offset-transitions/records/zone-image.json)

## Holdouts

The unmodified int-array rule initially refused the released `Longs.indexOf(long[],long)` descriptor. The extended translator handles `lload`, `laload` and signed `lcmp` from the real helper. The checked prefix invariant, heap frame, exits and 32-bit termination argument transferred. The solver returned three satisfiable domain checks and eight unsatisfiable proof obligations, including a check that admits distinct 64-bit values with identical low halves. At maximum lengths 8 and 64 the strict native checker established six claims and refuted two. The direct JVM grid covered 1,364 inputs per revision. [Original refusal](../../examples/346-guava-long-array-holdout/records/transfer-baseline.json) · [Released long-array proof](../../examples/346-guava-long-array-holdout/records/array-induction/first-any-length)

The importer holdout kept every original application class hash and both pairs of upstream JARs. The document `abc,😀\nc,d\n` places the non-ASCII field beyond the BOM prefix, so one-byte reads split the scalar at all three interior boundaries. The standalone streaming and BOM decoders already have native proofs of the UTF-16 units and repeated EOF on all eight partitions of U+1F600. The importer independently rechecks the bytes, row count and numbered fields on 32 inputs per configuration. The exhaustive JVM and native routes agreed on all 16 claims, including four positive controls. The number of wrong complete pages fell from 24/32 with both parents to 16/32 with either single fix and 0/32 with both fixes. The monolithic fixed/fixed native job exhausted its 90-second budget. Complete native case analysis proved all 32 admitted inputs. [Four native decoder receipts and unchanged class hashes](../../examples/347-importer-four-byte-field/records/decoder-transfer.json) · [Unicode importer matrix](../../examples/347-importer-four-byte-field/records/matrix/matrix.json)

## Verification scope

The unrestricted native service-loader and zone fixtures remain open. For UTF-8, the JVM checked all 5,578 partitions and found 5,448 per-chunk decoding mismatches. Native checking refuted that original per-chunk claim, and checked the single four-byte scalar under each partition on all three subjects. Five full-grid UTF-8 native claims remain open. Splitting the symbolic workload by source word and proving all cut masks within each word would address the current whole-domain search cost. [UTF-8 observations](../../examples/341-utf8-chunk-boundaries/records/partitions.json) · [Native and finite claim history](../../examples/341-utf8-chunk-boundaries/target.json)

## Regression and pipeline checks

Example 197 retained its three alias properties across 71 heaps. Example 308 checked the release and rebuilt source at length 4, unwind 18, with 225 input pairs per revision. Example 331 met all eleven expectations. One helper timed out in the last batch, then passed individually at the same 25-second checker budget. Both proof-tier comparisons against JBMC passed. [197 alias replay](../../verification/results/20261120-213850-197-recheck-all-71-heaps-with-the-decode/result.json) · [308 LCS](../../verification/results/20261120-213851-308-rerun-release-source-and-225-lcs-pai/result.json) · [331 same-budget retry](../../verification/results/20261120-221803-331-rerun-the-remaining-helper-check-at/result.json) · [JBMC and auto](../../verification/results/20261120-213850-compare-new-decoder-bytecode-with-jbmc-a/result.json) · [Auto confirmation](../../verification/results/20261120-213850-compare-new-decoder-bytecode-with-auto-c/result.json)

The final ledger includes all 110 campaign jobs. 73 passed and 37 recorded a failure. All have a collected result. Earlier timeouts, unsupported operations and partial batches retain their original receipts. A successful retry contributes one disposition to its claim. The implementation descends from the brief’s pinned baseline `4f87fd1fc9cb`. [Job results and individual attempts](../../verification/next-proof-campaign-results.json)
