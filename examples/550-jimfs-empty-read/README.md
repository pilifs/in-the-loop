# A zero-length file read still returns zero after observed EOF

A zero-length file read returned zero after EOF. An empty slice at the end of the destination still alternated correctly with positive reads and left every sentinel intact.

The endpoint is a valid empty slice. No call can create data in an empty file.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `-1/true` | `0/true` | matched |
| Control | `0/true/1` | `0/true/1` | matched |
| Challenge | `-1/-1/-1/true` | `0/-1/0/true` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 550`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/google/jimfs/pull/435)

With identical compiled caller bytes, 1.3.1 matched the parent and 1.3.2 matched the landing on all three histories. [Release measurements](../../verification/merged-pr-links/r01-r50/release-observations.json)
