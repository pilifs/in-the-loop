# A rejected unique key leaves both collection views intact

A rejected duplicate left the original list, iterator and lookup in agreement. Rebuilding the index then admitted a distinct key.

Rebuilding solely from the caller-owned collection independently checks whether the earlier exception left a valid unique index.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `IllegalArgumentException/[01, 1]/[01, 1]/01` | `IllegalArgumentException/[01]/[01]/01` | matched |
| Control | `[01, 2]/[01, 2]/01/2` | `[01, 2]/[01, 2]/01/2` | matched |
| Challenge | `throws java.lang.IllegalArgumentException` | `ok/[01, 2]/01/2` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 539`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/commons-collections/pull/688)

With identical compiled caller bytes, 4.5.0 matched the parent and 4.6.0 matched the landing on all three histories. Release 4.6.0 also evaluated the key transformer when a nonunique backing set rejected an identical element. Both PR pins accepted the same first insert and skipped this extra callback. [Release measurements](../../verification/merged-pr-links/r01-r50/release-observations.json) · [Additional comparisons](../../verification/merged-pr-links/r01-r50/followup-observations.json)
