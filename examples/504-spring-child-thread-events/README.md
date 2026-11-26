# Recording application events from a test's child threads

New child threads now share the recording test's events. In Jupiter the PER_CLASS and CONCURRENT combination was rejected with global parallelism both enabled and disabled.

An actual EngineTestKit run checks the container error. The event cases create and join both children after the recording test starts.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · child | `[]` | `[child]` | matched |
| Control · parent | `[parent]` | `[parent]` | matched |
| Challenge · both | `child=IllegalStateException parent=[A]` | `child=[A, B] parent=[A, B]` | matched |
| Configuration · guard | `enabled=ran disabled=ran` | `enabled=IllegalStateException disabled=IllegalStateException` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 504` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/30020)
