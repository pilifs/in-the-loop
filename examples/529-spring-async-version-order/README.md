# Resolve asynchronous API versions in registration order

A gated first version resolver now wins despite a ready second resolver. When the first failed, the subscriber received that exact error and the second publisher had zero subscriptions.

The parent returned the later value before the gate opened. An immediately empty first resolver selected the fallback on both revisions.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · first | `[2.0]:complete` | `[1.0]:complete` | matched |
| Control · empty | `[2.0]:complete` | `[2.0]:complete` | matched |
| Challenge · error | `[2.0]:complete:B=1` | `[]:sentinel:B=0` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 529` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37096)
