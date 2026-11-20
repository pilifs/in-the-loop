# Can the verifier help review a dependency upgrade?

On the disclosed rxjava-jdbc change, existing CI already detected a different list of generated keys. Replaying two call shapes and reading the table explained the consequence: the same two rows were inserted, and only the multi-row statement exposed a different list. On the AWS change, the historical test failed even though the SDK's public parser still round-tripped its caller's timestamp. These are independently reproduced calibration findings. The blinded product score and prospective impact are still unmeasured. [Public case ledger](../../verification/external-upgrade-calibrations.json)

| Evaluation | Population | Current result |
|---|---:|---|
| V0 retrospective | 12 changes and 12 scoped preservations | Cohort selection in progress. No scored first reports have been opened. |
| V0 and V1 transfer | 8 untouched upgrades | Reserve selection in progress. No paired scores. |
| Prospective advisory pilot | First 5 eligible PRs from each of 3 consenting teams | No team decisions collected. The retrospective investment gate has yet to be evaluated. |

At 00:09 UTC on 21 November the separate curator had independently reproduced and signed one eligible behavioral reference. Its four fresh named tests, four direct JVM replays, preserving companion and crossed library substitutions survived a packet-only rebuild. The signed roster is still open. The source docket contains 123 CompSuite and 571 BUMP records. A registry label alone earns no admission.

The isolated command environment completed a real synthetic V0 proof. Both original JDK controls returned 42, and attempts to read synthetic private references, earlier reports and sibling cases were denied. The normal authenticated model client also advertises file and cross-session tools whose confinement was not demonstrated. Scored launches await an isolated normal client or equivalent verified controls. [Operator admission evidence](../../lib/benchmark/external-upgrades/operator/README.md)

V0 is the accepted importer and array merge at `e7cdfb6a6edea96c8653ee87a7c1e2ef3f602665`. The five disclosed checks used the same executable, Temurin 21.0.13+9 and word-level Bitwuzla configuration. All 459 protected files verified before and after each public workflow invocation. Supplied observers and replay evidence belong to the calibration results. [Product lock](../../lib/benchmark/external-upgrades/v0.json) · [Selection, blinding and grading rules](../../lib/benchmark/external-upgrades/protocol.md) · [Measured opening costs and matched budgets](../../lib/benchmark/external-upgrades/budget.json)

## What the disclosed clients do

| Client | Independent result | First step V0 could not check |
|---|---|---|
| [rxjava-jdbc / H2](../../examples/348-rxjava-jdbc-generated-keys/README.md) | One two-row insert returned `[2]` before and `[1,2]` after. Two separate inserts returned `[1,2]` on both. All four fresh databases held both rows. Three of the 454 original tests failed on the upgrade, all through the same inherited assertion. | Opening the JDBC connection. The H2 POM entry has test scope, which excludes the case from the production cohort. |
| [Commons Text / Commons Lang](../../examples/349-commons-text-csv-upgrade/README.md) | All 156 short CSV fields returned the exact expected characters on both pins. Removing quote doubling broke 71, including a field consisting of one quote. All 34 original string-escape tests passed on each release. | Artifact intake rejected a legal modified UTF-8 NUL in the original class file before invoking the checker. |
| [Rocker / ANTLR](../../examples/350-rocker-with-declaration/README.md) | Both builds rejected the trailing comma at line 1, column 18 and accepted the valid declaration. Changing just the runtime reproduced the new diagnostic. Both the generated parser sources and the runtime changed in the original pair. | `WeakHashMap` construction in ANTLR initialization on the runtime-only control. |
| [AWS SDK / Joda-Time](../../examples/351-aws-joda-instant/README.md) | The protected formatter newly parsed the maximum signed instant. The public SDK still round-tripped both that instant and the ordinary-date companion under both versions. | Constructing `java.util.Date(long)` for the public-method claim. |
| [Cucumber Reporting / Joda-Time](../../examples/352-cucumber-duration/README.md) | Jackson deserialized 18 durations on each side. All displayed exactly three digits of truncated milliseconds. The six compiled client classes matched their published binaries. | Selecting Jackson's release-specific class in a multi-release JAR. |

The pinned native workflow left all five disclosed claims open. The JDBC, time, initialization and class-file limitations arose at different stages. The next product repair is to be selected from the number of distinct blinded PR decisions it could change. [Per-case runtime, qualification and original first blockers](../../verification/external-upgrade-calibrations.json)

## CI and CompCheck

The stock CompSuite wrapper printed success on both H2 tags when an offline build extension was missing. It produced zero fresh Surefire reports. Running the real original test suite with its historical provider produced 454 tests on each pin, two skips per pin, and three upgraded-side assertion failures. All 105 independently built production classes matched the published release bytes. [Wrapper outcomes](../../examples/348-rxjava-jdbc-generated-keys/records/compsuite-cli.json) · [Whole test-set results](../../examples/348-rxjava-jdbc-generated-keys/records/whole-suite.json)

CompCheck's two stock AWS runs emitted an empty call context on a cold offline Maven build. Supplying byte-identical compiled client code allowed both variants to derive the same context. With its published knowledge CompCheck matched the prior AWS incident and stopped before generating a test. With only the two records for that incident removed, it found no matching API entry. Neither treatment produced a validated test. The pinned registries have 13 exact overlapping CompSuite entries out of 123. [Paired CompCheck report](../../lib/benchmark/external-upgrades/baselines/compcheck-aws.md) · [Independent registry join](../../lib/benchmark/external-upgrades/curation/registry_overlap.py)
