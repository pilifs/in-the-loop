# A transaction releases its connection after an auto-commit restore error

A failed auto-commit restore now still releases the R2DBC loan. A rollback failure retained its translated cause and another checkout obtained the freed slot.

Only a subscription to the driver's cold close publisher credits the slot. A second checkout tests that independently.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · restore | `IllegalTransactionStateException cause=false commits=1 rollbacks=0 restores=1 closes=0` | `ok commits=1 rollbacks=0 restores=1 closes=1` | matched |
| Control · success | `ok commits=1 rollbacks=0 restores=1 closes=1` | `ok commits=1 rollbacks=0 restores=1 closes=1` | matched |
| Challenge · slot | `R2dbcTimeoutException cause=false commits=0 rollbacks=1 restores=1 closes=0 next=false` | `BadSqlGrammarException cause=true commits=0 rollbacks=1 restores=1 closes=1 next=true` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 497` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/29703)
