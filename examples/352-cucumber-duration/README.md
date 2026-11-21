# Cucumber Reporting and Joda-Time

Upgrade Cucumber Reporting · Joda-Time 2.12.5 → 2.12.6  
Caller-visible behavior `Result.getFormattedDuration()` renders the duration stored in a JSON report.  
Result Both versions returned the independently expected string on all 18 durations. A report containing 1,999,999 nanoseconds displayed `0.001`. [Exhaustive JVM observations](records/observations.json)  
Scope UTC and English, seconds in {0, 1, 59}, milliseconds in {0, 1, 999}, and submillisecond remainders of 0 or 999,999 nanoseconds.  
Review action The upgrade preserves millisecond truncation for this grid. Keep the precision assertion if a later formatter or report schema changes.

Jackson read the JSON into the original `Result`. The observer checked its stored duration and the exact string from Joda's formatter. All six independently compiled consumer classes, including the two deserializers loaded by Jackson, matched their published Cucumber Reporting 5.7.8 class files byte for byte on both source revisions. The public `format` task uses those class-identical methods on each dependency. [Source revisions, JDK and ordered JAR digests](materials.json)

The upstream test contains a `0.007` example. PR 1156 merged on 6 February 2024 with one changed file, the POM. The cold offline Maven lifecycle stopped before tests at Maven Enforcer 1.2. The 18 independently executed inputs establish the disclosed finite preservation result. Historical CI coverage beyond the checked-in assertion remains unmeasured. [Original PR identity](records/merged-pr.json) · [Effective models and CI attempts](records/effective-and-ci.json)
