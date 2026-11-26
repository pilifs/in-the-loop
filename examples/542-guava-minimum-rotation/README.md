# Rotating a primitive subarray by the smallest integer distance

Both Guava distributions rotated by Integer.MIN_VALUE in the same direction as the independently rotated boxed list. Changing the cells outside the subrange preserved its five values.

The distance is congruent to 2 modulo 5. Only the subrange participates in its period and its permutation.

## Guava JRE

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `[2, 3, 1]/[3, 1, 2]` | `[3, 1, 2]/[3, 1, 2]` | matched |
| Control | `[2, 3, 1]/[2, 3, 1]` | `[2, 3, 1]/[2, 3, 1]` | matched |
| Challenge | `[9, 3, 4, 5, 1, 2, 8]/[4, 5, 1, 2, 3] / [-7, 3, 4, 5, 1, 2, 42]/[4, 5, 1, 2, 3]` | `[9, 4, 5, 1, 2, 3, 8]/[4, 5, 1, 2, 3] / [-7, 4, 5, 1, 2, 3, 42]/[4, 5, 1, 2, 3]` | matched |

## Guava Android

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `[2, 3, 1]/[3, 1, 2]` | `[3, 1, 2]/[3, 1, 2]` | matched |
| Control | `[2, 3, 1]/[2, 3, 1]` | `[2, 3, 1]/[2, 3, 1]` | matched |
| Challenge | `[9, 3, 4, 5, 1, 2, 8]/[4, 5, 1, 2, 3] / [-7, 3, 4, 5, 1, 2, 42]/[4, 5, 1, 2, 3]` | `[9, 4, 5, 1, 2, 3, 8]/[4, 5, 1, 2, 3] / [-7, 4, 5, 1, 2, 3, 42]/[4, 5, 1, 2, 3]` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 542`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/google/guava/pull/8811)
