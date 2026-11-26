# Discard every concatenated source value before thenMany emits its tail

thenMany emitted only the tail after successful concatenation. When the second source failed, the identical error reached the subscriber without an earlier value or a tail subscription.

The receiver’s completion is the condition for starting the tail. An error terminates that receiver even after earlier values.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `[a, c]/complete` | `[c]/complete` | matched |
| Control | `[c]/complete` | `[c]/complete` | matched |
| Challenge | `[a]/same-error/tail=0` | `[]/same-error/tail=0` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 580`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/reactor/reactor-core/pull/3783)
