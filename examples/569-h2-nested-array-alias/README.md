# Nested JDBC arrays reach Java aliases with their row structure intact

H2 passed two ragged rows to the Java alias. Both a typed Short[][] result and a second alias returning scalar text preserved the row boundaries.

All values fit both Java numeric types. The second alias independently observes the SQL result as its own argument and returns a scalar that bypasses JDBC nested-array result conversion.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `sqlstate=HY000/JdbcSQLNonTransientException` | `Integer[][]:[[1, 2], [3]]` | matched |
| Control | `Object[]:[1, 2]` | `Object[]:[1, 2]` | matched |
| Challenge | `sqlstate=HY000/JdbcSQLNonTransientException` | `Short[][]:[[1, 2], [3]]/[[1, 2], [3]]` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 569`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/h2database/h2database/pull/2614)
