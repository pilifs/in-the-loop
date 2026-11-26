# Cycle detection in a disconnected undirected graph

Both Guava distributions detected the triangle after an isolated node disabled the edge-count shortcut. Adding another acyclic component preserved the positive result.

The triangle remains intact. The extra components change the edge-to-node count, which governs the shortcut described by the PR.

## Guava JRE

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `false` | `true` | matched |
| Control | `false` | `false` | matched |
| Challenge | `true/false` | `true/true` | matched |

## Guava Android

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `false` | `true` | matched |
| Control | `false` | `false` | matched |
| Challenge | `true/false` | `true/true` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 546`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/google/guava/pull/8801)
