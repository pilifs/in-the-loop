# Skipped characters, bounds, and the underlying reader position

The global bound now limits the underlying skip to three. A mark with a two-character read-ahead limit stopped reads at two, but skip advanced the same delegate to four.

The read predicate checks markedAt and readAheadLimit. The landed skip predicate uses only the global remaining count. Direct delegate read distinguishes positions 2 and 4.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `5/-1/5` | `3/-1/3` | matched |
| Control | `1/1/2/-1;request3=1/-1/-1/-1` | `1/1/2/-1;request3=1/1/2/-1` | matched |
| Challenge | `0/1/-1;4/4` | `0/1/-1;4/4` | refuted |

With the prepared R-series cache, run `python3 examples/tools/build.py 549`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/commons-io/pull/860)

With identical compiled caller bytes, 2.22.0 matched the parent on all three histories. With the same mark(2) at offsets zero, one and two, the read windows contained two, one and zero characters. The direct delegate read confirmed the cursor position, and reset returned to the same restricted window on both pins and 2.22.0. [Release measurements](../../verification/merged-pr-links/r01-r50/release-observations.json) · [Additional comparisons](../../verification/merged-pr-links/r01-r50/followup-observations.json)
