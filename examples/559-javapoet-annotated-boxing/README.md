# Box and unbox annotated primitive type names

Annotated boolean boxed and unboxed successfully. Two distinct type-use annotations on an independently built Integer survived both conversions in their original order.

The two distinct annotations reveal duplication, reversal or loss. Starting with a separately constructed wrapper exercises equality across instances.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `throws java.lang.AssertionError` | `java.lang.Boolean/[A]/true/boolean/[A]/true` | matched |
| Control | `java.lang.Boolean/true/true/[]` | `java.lang.Boolean/true/true/[]` | matched |
| Challenge | `throws java.lang.UnsupportedOperationException` | `int/[A, B]/java.lang.Integer/[A, B]/true` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 559`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/square/javapoet/pull/986)
