# Preserve sub-millisecond digits when reducing temporal literals

The planner retained six fractional digits in TIME and TIMESTAMP. Two timestamps one microsecond apart remained distinct after reduction to VARCHAR.

The inputs differ by one representable microsecond. String readback tests the next consumer rather than only a temporal type's declared precision.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `12:34:56.123000/2020-01-01 12:34:56.123000` | `12:34:56.123456/2020-01-01 12:34:56.123456` | matched |
| Control | `12:34:56.123/2020-01-01 12:34:56.123` | `12:34:56.123/2020-01-01 12:34:56.123` | matched |
| Challenge | `2020-01-01 12:34:56/2020-01-01 12:34:56` | `2020-01-01 12:34:56.123456/2020-01-01 12:34:56.123457` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 571`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/calcite/pull/4942)
