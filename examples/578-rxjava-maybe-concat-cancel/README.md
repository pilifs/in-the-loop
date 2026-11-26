# Cancelling Maybe concatenation prevents later subscription side effects

Early cancellation prevented entry into the second successful Maybe. With an empty prefix, both the iterable and array forms entered just the empty and first value sources.

An empty source cannot satisfy firstElement. The cancellation point depends on the first actual value and is independent of array versus iterable representation.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `[1]/complete/1/1` | `[1]/complete/1/0` | matched |
| Control | `[1, 2]/complete/[first, second]` | `[1, 2]/complete/[first, second]` | matched |
| Challenge | `[1]/complete/[empty, first, second] / [1]/complete/[empty, first, second]` | `[1]/complete/[empty, first] / [1]/complete/[empty, first]` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 578`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/ReactiveX/RxJava/pull/5101)

With identical compiled caller bytes, 2.0.6 matched the parent and 2.0.7 matched the landing on all three histories. [Release measurements](../../verification/merged-pr-links/r01-r50/release-observations.json)
