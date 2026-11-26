# Concatenation delivers later values before a delayed inner error

Reactor delivered all four items before the identical delayed error. Hiding the callable source preserved the signals with one outstanding request at a time.

Each pin's original FluxConcatMap and FluxFlatMap classes precede the same Reactor Core 3.1.1.RELEASE. The historical Gradle plugins are unavailable.

The physical callers run on Temurin 8u512, the Java major reported for Reactor 3.1.0.RELEASE.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `[1, 2]/same-error` | `[1, 2, 3, 4]/same-error` | matched |
| Control | `[1, 2, 3, 4]/complete` | `[1, 2, 3, 4]/complete` | matched |
| Challenge | `[1, 2]/same-error/demand=true / [1, 2, 3, 4]/same-error/demand=true` | `[1, 2, 3, 4]/same-error/demand=true / [1, 2, 3, 4]/same-error/demand=true` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 579`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/reactor/reactor-core/pull/937)

With identical compiled caller bytes, 3.1.0.RELEASE, 3.1.1.RELEASE matched the parent and 3.1.2.RELEASE matched the landing on all three histories. [Release measurements](../../verification/merged-pr-links/r01-r50/release-observations.json)
