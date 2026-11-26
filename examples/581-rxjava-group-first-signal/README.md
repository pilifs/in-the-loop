# New reactive groups expose their first value or its selector error

The delayed one-item Observable group already delivered 7 on the parent. The Flowable challenge distinguished the revisions: the merge exposed the new group and delivered the selector error to both observers.

The key is known before the value conversion. Independent inner and outer subscribers check where the selector’s failure becomes observable.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `K/[7]/complete/complete` | `K/[7]/complete/complete` | matched |
| Control | `1/K/[7, 8]/complete/complete` | `1/K/[7, 8]/complete/complete` | matched |
| Challenge | `0//[]//same-error / 1/K/[]/same-error/same-error` | `1/K/[]/same-error/same-error / 1/K/[]/same-error/same-error` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 581`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/ReactiveX/RxJava/pull/6664)
