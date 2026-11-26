# Defer JDBC session settings while preserving physical connection state

Individual client-info and timeout settings now wait for first physical use. One consuming read applied the latest value, preserved the driver's unrelated key, and left the unused handle unmaterialized.

Each physical connection owns separate settings. The control observed an immediate checkout for both a driver-supplied value and a bulk Properties write.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · defer | `1/1/1:125/1:blue:125` | `0/0/0:125/1:blue:125` | matched |
| Control · bulk | `1:driver / 1:{bulk=set}` | `1:driver / 1:{bulk=set}` | matched |
| Challenge · handles | `before=2 after=2 value=green other=driver` | `before=0 after=1 value=green other=driver` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 522` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37261)
