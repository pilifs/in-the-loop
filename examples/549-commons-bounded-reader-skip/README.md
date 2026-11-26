# Skipped characters, bounds, and the underlying reader position

The global bound now limits the underlying skip to three. A mark with a two-character read-ahead limit stopped reads at two, but skip advanced the same delegate to four.

The read predicate checks markedAt and readAheadLimit. The landed skip predicate uses only the global remaining count. Direct delegate read distinguishes positions 2 and 4.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `5/-1/5` | `3/-1/3` | matched |
| Control | `1/1/2/-1;request3=1/-1/-1/-1` | `1/1/2/-1;request3=1/1/2/-1` | matched |
| Challenge | `0/1/-1;4/4` | `0/1/-1;4/4` | refuted |

With the prepared R-series cache, run `python3 examples/tools/build.py 549`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/commons-io/pull/860)
