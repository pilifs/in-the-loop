# Decimal values are valid at exactly the declared precision

Both vector widths accepted magnitude 999.99 at precision five. The four-digit and six-digit controls remained distinct, and values transferred by public setters preserved sign and scale.

Logical decimal precision and scale are unchanged by backing width. Crossing two public setters and readers checks both sign and logical scale.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `ValidateException/[999.99, -999.99] / ValidateException/[999.99, -999.99]` | `ok/[999.99, -999.99] / ok/[999.99, -999.99]` | matched |
| Control | `ok/ValidateException / ok/ValidateException` | `ok/ValidateException / ok/ValidateException` | matched |
| Challenge | `ValidateException/[-999.99, 999.99] / ValidateException/[-999.99, 999.99]` | `ok/[-999.99, 999.99] / ok/[-999.99, 999.99]` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 573`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/arrow-java/pull/1342)
