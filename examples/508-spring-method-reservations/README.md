# Reserve each generated method name separately

Reserving two generated method names now produces apply1 and test1. A peer reserved one name at a time and returned the same four names, including the free applyTest spelling.

Both callers obtained a fresh GeneratedClass through DefaultGenerationContext. The parent threw while reserving the pair.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · names | `IllegalStateException` | `apply1,test1` | matched |
| Control · single | `apply1,test` | `apply1,test` | matched |
| Challenge · peer | `IllegalStateException` | `test1,applyTest,apply1,test2 / test1,applyTest,apply1,test2` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 508` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/36912)
