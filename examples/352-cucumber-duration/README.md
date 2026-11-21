# Cucumber Reporting and Joda-Time

Upgrade Cucumber Reporting · Joda-Time 2.12.5 → 2.12.6  
Caller-visible behavior `Result.getFormattedDuration()` renders the duration stored in a JSON report.  
Result Both versions returned the independently expected string on all 18 durations. A report containing 1,999,999 nanoseconds displayed `0.001`. [Exhaustive JVM observations](records/observations.json)  
Scope UTC and English, seconds in {0, 1, 59}, milliseconds in {0, 1, 999}, and submillisecond remainders of 0 or 999,999 nanoseconds.  
Review action The upgrade preserves millisecond truncation for this grid. Keep the precision assertion if a later formatter or report schema changes.

Jackson read the JSON into the original `Result`. The observer checked its stored duration and the exact string from Joda's formatter. All six independently compiled consumer classes, including the two deserializers loaded by Jackson, matched their published Cucumber Reporting 5.7.8 class files byte for byte on both source revisions. The public `format` task uses those class-identical methods on each dependency. [Source revisions, JDK and ordered JAR digests](materials.json)

PR 1156 merged on 6 February 2024 with one changed file, the POM. The cold offline Maven attempt stopped at Maven Enforcer 1.2. Reproducing the original Linux JDK 11 workflow with serial dependency resolution completed all 665 reported tests on each side, including 27 skips and zero errors or failures. All six original `ResultTest` cases passed on each revision. A separate JVM replay of the unchanged test fixture loaded nine source-built client classes and returned `0.007` for 7,040,000 nanoseconds on each Joda release. The 18-input calibration covers additional truncation boundaries. [Original PR](records/merged-pr.json) · [Full Linux CI](records/full-linux-ci/result.json) · [Original fixture replay](records/original-test-fixture.json) · [Earlier offline builds](records/effective-and-ci.json)
