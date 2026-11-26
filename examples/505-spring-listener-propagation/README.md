# Class-level transaction propagation on event listeners

Event listener creation now rejects class-level REQUIRED. The method-level NOT_SUPPORTED override refreshed and received exactly one fallback event outside a transaction.

The forbidden and permitted method controls call the factory directly. The delivery history registers a managed listener with transaction management enabled.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · class | `accepted` | `IllegalStateException` | matched |
| Control · method | `IllegalStateException/accepted` | `IllegalStateException/accepted` | matched |
| Challenge · receipt | `[receipt]` | `[receipt]` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 505` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/33470)
