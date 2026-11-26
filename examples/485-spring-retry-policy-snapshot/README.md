# A built retry policy keeps its exception rules

A built retry policy now keeps its original exception rules. Its executor retried the file exception and returned 7 while the newer policy stopped after one call.

Both operations have independent invocation counters. The budgets and thrown exception classes are the same.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · old | `true,false` | `false,true` | matched |
| Control · new | `true,true,false` | `true,true,false` | matched |
| Challenge · execute | `1:RetryException / 1:RetryException` | `2:7 / 1:RetryException` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 485` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37596)
