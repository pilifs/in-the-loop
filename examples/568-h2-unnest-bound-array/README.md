# Keep bound integers through UNNEST and ARRAY_AGG

H2 returned the bound integers instead of two nulls. Aggregate and scalar queries agreed after rebinding the same statements, including duplicate 7 and a later negative value.

The scalar-row query independently exposes the current bindings. Changing both values detects a result frozen at prepare time or cached on reuse.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `[null, null]/[null, null]` | `[1, 2]/[1, 2]` | matched |
| Control | `[1, 2]/[1, 2]` | `[1, 2]/[1, 2]` | matched |
| Challenge | `[null, null]/[null, null]/[7, 7] / [null, null]/[null, null]/[-4, 9]` | `[7, 7]/[7, 7]/[7, 7] / [-4, 9]/[-4, 9]/[-4, 9]` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 568`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/h2database/h2database/pull/4034)
