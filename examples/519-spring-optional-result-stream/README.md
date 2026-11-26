# Preserve result cardinality and release streams when returning Optional

The new Optional accessors agreed for collections, iterators, and streams. The unsized two-row stream stopped at its second equal reference and closed once, including on the exception path.

Singleton results retained object identity. The existing collection method continued to count equal rows separately.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · cardinality | `absent` | `empty,identical,too-many(1) / empty,identical,too-many(1) / empty,identical,too-many(1)` | matched |
| Control · old | `null,identical,too-many(1)` | `null,identical,too-many(1)` | matched |
| Challenge · closing | `absent` | `too-many(1):read=2:closed=1 / identical:closed=1` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 519` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/27735)
