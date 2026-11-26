# Resolve nested record component types before choosing a JSON adapter

Moshi resolved nested scalars, lists and map values to Long. Alternating Long, String and Long wrappers in the same adapter cache preserved the type of every component.

Identical raw component declarations can represent different parameterized types. Reusing the same adapter cache exercises that distinction.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `throws java.lang.IllegalArgumentException` | `Long:1/[Long:2, Long:3, Long:4]/Long:5/true` | matched |
| Control | `String:plain` | `String:plain` | matched |
| Challenge | `throws java.lang.IllegalArgumentException` | `Long:1/[Long:2, Long:3, Long:4]/Long:5/true / String:x/[String:y, String:z]/String:w/true / Long:1/[Long:2, Long:3, Long:4]/Long:5/true` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 562`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/square/moshi/pull/1442)
