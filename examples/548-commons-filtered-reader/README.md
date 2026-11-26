# Bulk reads and skip count the characters that survive a filter

A positive-length read skipped a fully discarded chunk and returned the surviving character. Extra leading discarded characters did not change the value following a skip.

Deleting x first leaves ab in every case. Skipping its first retained character can only leave b.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `first=0:,next=1` | `first=1:a,next=-1` | matched |
| Control | `1/b/c/-1` | `1/b/c/-1` | matched |
| Challenge | `1/a/98 / 1/a/98 / 1/b/-1` | `1/b/-1 / 1/b/-1 / 1/b/-1` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 548`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/commons-io/pull/931)
