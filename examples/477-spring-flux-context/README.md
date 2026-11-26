# The subscriber’s Reactor Context reaches a cached Flux on a miss

On a cache miss, the merged Flux saw the subscriber's context. After explicit eviction a new subscription saw the replacement value.

| History | Observation |
|---|---|
| Intent | The parent returned none for both calls. The merge returned t1 on both the miss and the t2 subscriber's hit. A single source subscription stored t1. |
| Control | The Mono miss and hit each returned t1 on both revisions, with one source subscription. |
| Put and eviction | The merged put emitted and stored t1. The eviction emitted t2 and removed the key. The parent changed the cache while its streams emitted none. |
| Challenge | Saving the publisher before attaching a context delivered t1 on the merge. Explicit eviction and a new subscription delivered and cached t2, with two source subscriptions in total. |

The argument that identifies the cache entry is held fixed while the subscriber context changes. Each variant starts with a new application context and cache.

With the prepared Spring cache, run `python3 examples/tools/build.py 477` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #37600](https://github.com/spring-projects/spring-framework/pull/37600)
