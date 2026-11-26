# A remapping that yields null still reports a present key

A null remap now returns a defined option. A second callback saw the stored null, restored the value, and left the original persistent map intact.

A second lookup distinguishes a stored null from absence. The original receiver provides an independent check of persistent updates.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `false/-/true/null` | `true/null/true/null` | matched |
| Control | `false/0/1/v` | `false/0/1/v` | matched |
| Challenge | `(1,null)/1/restored/restored/v` | `(1,null)/1/restored/restored/v` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 540`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/vavr-io/vavr/pull/3276)
