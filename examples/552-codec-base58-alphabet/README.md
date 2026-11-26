# The configured Base58 alphabet determines the wire bytes

The swapped Base58 alphabet emitted 221 for two zero bytes followed by one. A fresh decoder recovered those bytes from the literal, and the independent base-58 carry fixture also matched.

58 is one times 58 plus zero. The leading zero byte adds a separate zero digit before those two positional digits.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `wire=112,decoded=[13, 94]` | `wire=221,decoded=[0, 0, 1]` | matched |
| Control | `wire=112,decoded=[0, 0, 1]` | `wire=112,decoded=[0, 0, 1]` | matched |
| Challenge | `wire=121,decoded=[13, 37]` | `wire=212,decoded=[0, 58]` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 552`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/commons-codec/pull/437)
