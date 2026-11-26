# Avro duration converts three unsigned fixed-width fields without losing their units

The logical Avro reader decoded the three independently written duration words in order. Both the logical and raw readers preserved the maximum unsigned millisecond value.

The maximum unsigned 32-bit word is all ones, distinct from signed −1. A second reader without conversion exposes the physical field boundary.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `throws java.lang.NoClassDefFoundError` | `1/2/3` | matched |
| Control | `010000000200000003000000` | `010000000200000003000000` | matched |
| Challenge | `throws java.lang.NoClassDefFoundError` | `0100000002000000ffffffff/1/2/4294967295 / 010000000200000000000000/1/2/0` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 575`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/avro/pull/2520)

With identical compiled caller bytes, 1.11.3 matched the parent and 1.12.0 matched the landing on all three histories. [Release measurements](../../verification/merged-pr-links/r01-r50/release-observations.json)
