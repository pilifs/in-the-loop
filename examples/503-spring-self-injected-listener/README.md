# A self-injected proxied listener receives each published event once

The self-injected proxied listener now receives one callback per event. Its advice and the independent listener observed identical event objects on both publications.

The original package-scanned application, event publisher, eager listener and aspect come from the upstream test source. The repeated history adds an event-specific aspect and a separate listener.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · self | `callbacks=2` | `callbacks=1` | matched |
| Control · plain | `ordered=true count=2` | `ordered=true count=2` | matched |
| Challenge · advice | `first=2/1/1 second=2/1/1 identities=true` | `first=1/1/1 second=1/1/1 identities=true` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 503` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/28322)
