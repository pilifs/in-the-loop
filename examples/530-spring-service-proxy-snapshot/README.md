# Isolate HTTP clients built from a reused service-proxy builder

Factories built from one service-proxy builder now isolate both late advice and request processors. Only the later factory added the transport header, even when a fresh client came from the first factory afterward.

The advice test counted actual adapter calls. The header test ran all three service methods to the adapter without short-circuiting.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · advice | `[late, late]:[]` | `[base, late]:[[]]` | matched |
| Control · same | `[base, base]:[[], []]` | `[base, base]:[[], []]` | matched |
| Challenge · header | `[base, base, base]:[[late], [late], [late]]` | `[base, base, base]:[[], [late], []]` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 530` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37601)
