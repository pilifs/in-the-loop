# Retrieve asynchronous values from a Boot-configured Caffeine cache

Checks synchronous and asynchronous reads from Boot-managed named and on-demand Caffeine caches.

The named-cache prediction asks whether the future itself delivers the stored string. The caller also reads Cache.ValueWrapper.get() when Spring returns that documented wrapper. These two readbacks keep the Java result type and logical cache value distinct.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `value:false:unavailable` | `value:true:wrapped:value` | refuted |
| Control | `value:false` | `value:false` | matched |
| Challenge | `throws java.lang.IllegalStateException` | `value/value` | matched |

Replay with `python3 examples/tools/build.py 613` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51844)
