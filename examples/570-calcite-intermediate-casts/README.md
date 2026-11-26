# Nested SQL casts retain intermediate precision and formatting

Calcite preserved the four SCOTT.EMP display strings. The nested truncating cast now returned 6.6, matching the separately fetched and rebound VARCHAR.

Fetching and rebinding the intermediate prevents the optimizer from eliding it across the two statements. 20/3 has additional fractional digits before truncation.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `20/20/800.00/20` | `20.0/20.00/800.0000/20` | matched |
| Control | `20/20` | `20/20` | matched |
| Challenge | `6.6/6.666666666666667/6.6` | `6.6/6.6/6.6` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 570`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/calcite/pull/5345)
