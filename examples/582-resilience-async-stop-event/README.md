# A retry interval of zero and a negative stopping interval have different outcomes

The asynchronous retry scheduled the zero-delay attempt and stopped on a negative exceptional interval. With a retryable result, it announced a negative-delay retry even though the supplier ran only once.

The exceptional path branches on the sign before event publication. AsyncContext.onResult publishes RetryOnRetryEvent before returning its interval, and the async decorator stops at a negative value.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `calls=1,retries=[0],errors=0,same-error` | `calls=2,retries=[0],errors=1,same-error` | matched |
| Control | `calls=2,retries=[1],errors=0,ok` | `calls=2,retries=[1],errors=0,ok` | matched |
| Challenge | `calls=1,retries=[-1],errors=0,again` | `calls=1,retries=[-1],errors=0,again` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 582`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/resilience4j/resilience4j/pull/2067)

The caller ran on Resilience4j 2.1.0, 2.2.0. A negative interval for a retryable result ended the stage after one call on both releases. Only 2.2.0 emitted the −1 ms retry event. Both original PR pins also emitted it. [Release measurements](../../verification/merged-pr-links/r01-r50/release-observations.json) · [Additional comparisons](../../verification/merged-pr-links/r01-r50/upstream.md)
