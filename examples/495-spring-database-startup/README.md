# A JDBC startup check can succeed without a validation query

Startup now uses JDBC isValid(1) when no SQL is configured. An invalid first loan and a throwing first loan each closed before the second was validated.

Two distinct connection objects record acquisitions, timeout, calls and closes. The explicit SELECT 1 control records the statement close separately.

Each pin supplies its changed production classes on spring-jdbc 5.2.7.RELEASE. The replay verifies the loaded class origins and all class digests of each compiled slice.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · valid | `IllegalArgumentException []` | `ok [openA, validA(1), closeA]` | matched |
| Control · query | `ok [openA, statementA, SELECT 1, closeStatementA, closeA]` | `ok [openA, statementA, SELECT 1, closeStatementA, closeA]` | matched |
| Challenge · retry | `IllegalArgumentException [] / IllegalArgumentException []` | `ok [openA, validA(1), closeA, openB, validB(1), closeB] / ok [openA, validA(1), closeA, openB, validB(1), closeB]` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 495` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/25305)
