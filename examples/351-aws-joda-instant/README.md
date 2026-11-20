# AWS SDK and Joda-Time

Upgrade AWS SDK for Java · Joda-Time 2.8.1 → 2.10.5  
Caller-visible behavior The SDK formats and parses ISO timestamps. Its public parser has a workaround for the largest signed millisecond instant.  
Result The protected formatter changed from throwing `IllegalFieldValueException` to returning `Long.MAX_VALUE`. The public SDK round-tripped the maximum instant and the ordinary date under both dependencies. [Direct and public SDK observations](records/observations.json)  
Scope Two exact instants in UTC and English on Temurin 8. The six independently compiled consumer classes matched their published AWS SDK 1.11.664 class files byte for byte.  
Review action Update the test that requires the Joda limitation. Keep a separate round-trip assertion on the public SDK method.

Both versions print `292278994-08-17T07:12:55.807Z` for the maximum instant. For `2000-01-01T00:00:00.123Z`, both the protected formatter and public SDK return 946684800123 milliseconds. The original `DateUtilsTest.testIssue233JodaTimeLimit` ran exactly once per fresh report. Its new-side error comes from the test calling `fail` after parsing unexpectedly succeeded. The public `roundtrip` verifier task covers the two public-method calls. [Old testcase](records/testcase-old.xml) · [New testcase](records/testcase-new.xml) · [Ordered binary and source locks](materials.json)

The production module's POM was the sole source-tree change. The cold offline module test stopped at Maven Resources 2.6, and the original whole-reactor command stopped at the missing Felix bundle plugin. The selected test ran independently with the authentic Surefire provider. [Effective models and lifecycle attempts](records/effective-and-ci.json) · [Published tags](records/tags.txt)
