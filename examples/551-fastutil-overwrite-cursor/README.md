# Bulk overwrite advances a repositioned output stream

A three-byte overwrite now advanced the cursor to position three. The next single-byte write left the same five logical bytes as four individual writes.

Splitting the same bytes across calls should leave their destination and the following write position unchanged.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `0/5/[7, 8, 9, 4, 5]` | `3/5/[7, 8, 9, 4, 5]` | matched |
| Control | `7/7/[1, 2, 3, 4, 5, 6, 7]` | `7/7/[1, 2, 3, 4, 5, 6, 7]` | matched |
| Challenge | `1/5/[6, 8, 9, 4, 5] / 4/5/[7, 8, 9, 6, 5]` | `4/5/[7, 8, 9, 6, 5] / 4/5/[7, 8, 9, 6, 5]` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 551`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/vigna/fastutil/pull/384)
