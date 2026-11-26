# Copy a primitive immutable list into a larger array

The primitive list copied four values into the caller’s oversized array. Spare cells retained their sentinels and changing the array left the list intact.

The copied interval is [0,4). Later writes to a caller-owned copy cannot mutate immutable list storage.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `throws java.lang.ArrayIndexOutOfBoundsException` | `true/[0, 1, 2, 3, 77]/0` | matched |
| Control | `false/[0, 1, 2, 3]/[77, 77]` | `false/[0, 1, 2, 3]/[77, 77]` | matched |
| Challenge | `throws java.lang.ArrayIndexOutOfBoundsException` | `true/[0, 1, 2, 3, 77]/0 / true/[0, 1, 2, 3, 88, 88, 88]/0` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 541`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/vigna/fastutil/pull/325)

With identical compiled caller bytes, 8.5.13 matched the parent and 8.5.14 matched the landing on all three histories. [Release measurements](../../verification/merged-pr-links/r01-r50/release-observations.json)
