# Count complete units between offset dates in either direction

Two midnights five hours apart now counted as zero whole days in either direction. DAYS and WEEKS also agreed with independent epoch-day arithmetic at the supported extremes.

MIN’s +18:00 and MAX’s −18:00 add 36 hours to the epoch-day interval. A whole week contains seven days.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `-1/0:oracle=0/0` | `0/0:oracle=0/0` | matched |
| Control | `2/-2:oracle=2/-2` | `2/-2:oracle=2/-2` | matched |
| Challenge | `throws java.time.DateTimeException` | `days=true/weeks=true/antisymmetric=true` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 577`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/ThreeTen/threeten-extra/pull/433)
