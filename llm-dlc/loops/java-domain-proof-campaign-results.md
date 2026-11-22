# Java domain proof campaign results

The campaign verifier decided **8/20 ordinary public obligations**, up from **4/20** at opening. Six were established and two parent counterexamples replayed. The finite JVM decided **20/20**, with 15 establishments and five refutations. All five historical failures reproduced. The named upstream tests recorded 23 expected parent failures, one passing parent control and 24 fixed passes. [Per-obligation scorecard](../../verification/java-domain-proof/scorecard.json)

| Change and final job | Opening native | Final native, established / replayed | Finite JVM | Recorded-startup public claims | Narrower evidence |
|---|---:|---:|---:|---|---|
| [Parquet #3333](../../verification/results/20261122-123421-final-java-domain-363-parquet-nested-bin/result.json) | 0/4 | 3 / 1 | 4/4 | — | Strict read-only child proof through backing length 47 |
| [Avro #1381](../../verification/results/20261122-123421-final-java-domain-364-avro-enum-namespac/result.json) | 0/4 | 0 / 0 | 4/4 | 0/4 | Jackson factory established on both classpaths. Given the default Boolean policy, Avro name validation is established for the ASCII grid. |
| [Jackson #1415](../../verification/results/20261122-123421-final-java-domain-365-jackson-async-toke/result.json) | 0/4 | 0 / 0 | 4/4 | — | An explicitly constructed parser matched all 128 factory traces per revision on the JVM |
| [Commons CSV #218](../../verification/results/20261122-123421-final-java-domain-366-commons-csv-delimi/result.json) | 4/4 | 3 / 1 | 4/4 | — | Capped-reader progress, EOF and prefix preservation established |
| [Avro #3730](../../verification/results/20261122-123422-final-java-domain-367-avro-union-array-d/result.json) | 0/4 | 0 / 0 | 4/4 | 0/4 | One-byte decoding, exhaustion and the public UTF name validator established on both classpaths |

Each PR contributes four obligations. Both measurements used the same guards, JARs, entry bytecode, JVM oracles and 60-second symbolic budget. The subject was Temurin 21.0.13+9-LTS. All final public jobs used source `cc04c56c3c89` and executable SHA-256 `4884acc1723508af16c871b38df177bf65ada3421fec4af82f753ec74fecc900`. The earlier six PRs retain 39/46 ordinary and 46/46 finite. Avro #729 retains 2/4 ordinary, 4/4 with recorded startup and 4/4 finite. [Earlier results](domain-foundations-strategy-results.md)

## What the native checker decided

Parquet’s unsplit queries timed out after the checker learned the builder’s heap-buffer transfer. Native checks covering every admitted selector established the fixed extent and both fresh-view claims. Parent selector 36 reproduced the empty child with 25 bytes of padding and a one-byte sibling. Position 35 and limit 41 exposed six bytes. The fix kept position and limit at 35 and threw on the next read. [Parquet receipts](../../examples/363-parquet-nested-binary/records/final/run.json)

CSV’s parent parsed `a||b||` as two fields ending in `b|`. The fix returned three fields ending in the empty string. A separate conforming reader restricted to one character per read parsed `a|||b|||c` as one field on the fix. At caps one, two and three, 8, 2 and 8 fixed field vectors differed from StringReader. The checker established the capped reader’s progress, range and EOF contract and all prefix controls. [CSV receipts](../../examples/366-commons-csv-delimiter-lookahead/records/final/run.json) · [Short-read experiment](../../verification/results/20261122-124440-csv-short-reads-at-three-reader-caps/result.json)

Jackson’s parent matched the unpadded offset trace on 32 of 128 schedules. All 128 fixed traces matched. Both revisions preserved token kinds and EOF. [JVM offsets](../../examples/365-jackson-async-token-offsets/records/opening-bound/finite/offsets-parent.json)

## What transferred

Both routes established the fixed public Parquet extent on all 64 inputs. The measured downstream cost was **13.33 s with reuse disabled and 13.57 s with checked reuse enabled**, a 0.23 s increase in this pair. Replaying the Avro producer and its original sites on the new verifier cost a separate 4.46 s, including 0.127 s to recertify the narrow theorem. Charging that one-time expense to this use gives 18.03 s. [Decided public comparison](../../verification/results/20261122-125536-price-checked-avro-reuse-on-the-decided/result.json)

| Downstream route | Wide proof | Original call-site checks | Public native checker | Whole public workflow |
|---|---:|---:|---:|---:|
| Fresh wide certificate | 0.030 s | 6.58 s | 2.82 s | 6.05 s |
| Checked narrow certificate plus fresh wide certificate | 0.021 s | 6.69 s | 2.97 s | 6.24 s |

The cached narrow certificate took 0.00019 s to validate. Both routes still ran the wide proof and all 64 native calls.

The debugger bound both actual Parquet wrap sites on every input. Avro #198 extended the six-byte wrap theorem used in #729 to 20. That bound covered 26/64 value wraps and 32/64 metadata wraps. The maximum backing length was 47. The read-only child proof covered indexed contents, independent cursors and exhaustion. Changed bounds, providers and observables each invalidated the old evidence. Call-site qualification used the certificate. The public checker executed the builder bytecode on both routes. [Producer and site evidence](../../verification/java-domain-proof/parquet-transfer/measurement.json)

In Avro #1381, `readEnum` called `BinaryDecoder.readInt`. In #3730, the fast reader called it for the preserved marker. Both experiments used the same compiled harness and JDK. All five inspected Avro provider classes changed, as did the bytecode and constant pools of both traced methods. The later reader reused the harness and site checks. Its own native proof established decoding wire bytes 0, 1 and 2 followed by EOF. On the earlier reader, recording Utf8 startup exposed another property lookup. The separate JVM resolver controls observed the correct symbol adjustments and short-name rejection. [Enum reader](../../verification/results/20261122-124846-trace-and-check-the-original-avro-reader/result.json) · [Resolver and Utf8](../../verification/results/20261122-125537-qualify-avro-enum-actions-and-the-utf8-d/result.json)

For recorded startup, both experiments initialized `Schema`, `GenericData` and `GenericDatumReader` together with two processors, an empty environment and working directory `/`. The receipts pin the observed classes and state digests.

The capstone required selecting the union’s array member and passing that schema to `GenericData.newArray`. Both standard readers handled the default in binary and JSON. The fast parent threw during construction. The fast fix returned the empty array and preserved all markers. Every reader mode rejected the missing required field. [Fast-reader experiment](../../verification/results/20261122-124847-check-367-fast-reader-producers-and-call/result.json)

## What the two Avro name validators share

The follow-up verifier established all ten name-validation queries. The campaign verifier stopped at `Character.isLetterOrDigit(char)` on the same ten. The extension handles ASCII letters and digits and retains a strict gap for other UTF-16 units. The paired job used source `78923c2e419c` and executable SHA-256 `2b31cb1c7508723ff9ea48b4358baeaa4248796d2c62186d4dcf22efc612e726`. [Managed comparison](../../verification/results/20261122-133607-prove-the-name-validation-consumer-on-fo/result.json)

| Feature | Value returned by the name-policy lookup | Lookups observed on parent / fix | Follow-up native proofs on parent / fix |
|---|---|---:|---:|
| Avro #1381 | `Boolean.TRUE` | 120 / 120 | 2 / 2 |
| Avro #3730 | `NameValidator.UTF_VALIDATOR` | 52 / 52 | 3 / 3 |

The debugger observed the policy object returned by `ThreadLocal.get()` inside all 32 frozen public reader calls. Both Avro versions pass the supplier through their own factory to the JDK. Their supplier and validation bytecode differ. The companion executes a copy of each original supplier and takes its value as an explicit input at the lookup. It checks that every subsequent consumer instruction and its constant-pool references agree with the original class. Substituting a different field, instruction or pool entry failed qualification on all four JARs. [Earlier reader](../../verification/java-domain-proof/name-validation/364/fix/measurement.json) · [Later reader](../../verification/java-domain-proof/name-validation/367/fix/measurement.json)

Each pair established the expected outcome for 18 named cases and every two-character ASCII name, including rejection with `SchemaParseException`. The original JVM agreed on all 16,384 character pairs per artifact. A permissive thread policy accepted all four invalid named cases. The two additional capstone proofs executed the unmodified public UTF validator on the 18 cases. A native proof of the full reader still needs to derive the thread-local value from startup. Both ordinary readers stop earlier in SLF4J. The 20 original public obligations retain their campaign measurements. [Per-query receipts and costs](../../verification/java-domain-proof/scorecard.json)

## Timeboxed deferrals

Twelve ordinary obligations remain open after the opening, final and partitioned queries. Two PRs met the fixed changed-behavior target of three. Both public Avro decodes remain open. Resource estimates below cover the next paired check after implementation.

| Public claims | Two measured attempts | First remaining producer and the next bounded experiment |
|---|---|---|
| Avro #1381, four | [Opening](../../verification/results/20261122-063655-qualify-364-original-artifacts-and-compl/result.json) · [Final](../../verification/results/20261122-123421-final-java-domain-364-avro-enum-namespac/result.json) | Queue construction now runs. SLF4J's `Util.safeGetSystemProperty` then reads an unknown setting. With three original startup roots captured, both public claims on both JARs stop at `Schema.validateNames.get()`. The separate record-field helper stops at `Schema.FIELD_RESERVED`. The follow-up establishes the validation code given the default Boolean. Deriving that Boolean at the lookup would connect it to the reader (about 2 CPUs, 3 GiB and 5 minutes after implementation). |
| Jackson #1415, four | [Opening](../../verification/results/20261122-121129-measure-the-original-jackson-opening-cla/result.json) · [Final](../../verification/results/20261122-123421-final-java-domain-365-jackson-async-toke/result.json) | The two property-comparison outcomes now reach `ThreadLocal` and `ReferenceQueue` construction. Supplying an explicit context reaches `AtomicReferenceArray` construction in the fresh recycler. A separate paired run could first qualify that allocation for one refill, then repeat the partitioned schedules (about 2 CPUs, 3 GiB and 5 minutes). [Explicit-context job](../../verification/results/20261122-124440-jackson-logical-offsets-with-an-explicit/result.json) |
| Avro #3730, four | [Opening](../../verification/results/20261122-122655-bind-the-four-avro-default-opening-rows/result.json) · [Final](../../verification/results/20261122-123422-final-java-domain-367-avro-union-array-d/result.json) | SLF4J's `ThreadLocalMapOfStacks` allocates a thread-local. Captured startup reaches Avro name validation, where `Schema.VALIDATE_NAMES` contains a supplied thread-local with an opaque referent. The follow-up establishes the public UTF validator. A single-thread proof of the value returned at the lookup would connect it to the reader (about 2 CPUs, 4 GiB and 5 minutes). |

The machine-readable scorecard can be recounted with `python3 lib/benchmark/java-domain-proof/scorecard.py --check --require-complete`. The normal workflow exposes each frozen entry with `python3 examples/tools/build.py --plan 363`. The Parquet fixed extent uses `python3 examples/tools/build.py 363 --native-selectors extent-fix --checker-seconds 60 --first 36` in a managed job. [Recount implementation](../../lib/benchmark/java-domain-proof/scorecard.py)
