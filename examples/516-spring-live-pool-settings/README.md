# Rejected live pool settings leave management getters consistent

Rejected pool settings now leave the Spring and JDK getters in agreement. A management caller recovered from a rejected size increase and ended at core and maximum two.

The parent advertised the rejected core size and consequently tried another invalid update. Every pool was initialized before inspection and shut down afterward.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · reject | `IllegalArgumentException:-1/1 IllegalArgumentException:0/1 IllegalArgumentException:-10/60` | `IllegalArgumentException:1/1 IllegalArgumentException:1/1 IllegalArgumentException:60/60` | matched |
| Control · accept | `2,3,10/2,3,10` | `2,3,10/2,3,10` | matched |
| Challenge · recover | `IllegalArgumentException/IllegalArgumentException:4,2/1,2` | `IllegalArgumentException/ok:2,2/2,2` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 516` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/26700)
