# Deep-clone a coordinate sequence without duplicating its points

Cloning preserved the three coordinates in order. Two equal but distinct points in a second fixture remained independent after one cloned coordinate changed.

Multiplicity is part of the ordered list. Deep copying must isolate subsequent coordinate mutations.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `size=6,points=[0:0, 1:1, 2:2, 0:0, 1:1, 2:2],original=1` | `size=3,points=[0:0, 1:1, 2:2],original=1` | matched |
| Control | `0/[4:5]` | `0/[4:5]` | matched |
| Challenge | `[9:1, 1:1, 1:1, 1:1]/[1:1, 1:1]` | `[9:1, 1:1]/[1:1, 1:1]` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 544`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/locationtech/jts/pull/1168)
