# A retried Flux completes and publishes the successful cache operation

The merged cache advice resubscribed after failure, delivered the successful attempt, and kept failed-attempt data out of the cache.

| History | Observation |
|---|---|
| Intent | The parent reached the five-second timeout after one source subscription. The merge subscribed twice, delivered a and b and stored that list. |
| Control | A first-attempt success and its cache hit both yielded a and b on both revisions with one source subscription in total. |
| Eviction | The parent timed out and retained the sentinel. The merge delivered a and b on the second subscription and evicted the key. |
| Challenge | The merged subscriber saw partial, a, b. The cache and a subsequent hit contained only a and b. The source count stayed at two. |

Both the caching and retry advisors run on the managed service. Timeouts are paired with an independent source count and cache read.

With the prepared Spring cache, run `python3 examples/tools/build.py 476` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #37403](https://github.com/spring-projects/spring-framework/pull/37403)
