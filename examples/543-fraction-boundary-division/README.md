# Representable quotients at the signed integer boundary

The quotient of Integer.MIN_VALUE by itself now reduces to one. Two representations of the same negative divisor also produced the same exact reduced pair.

Dividing the first divisor’s numerator and denominator by two gives the second representation exactly.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `ArithmeticException` | `1/1` | matched |
| Control | `ArithmeticException;3/2` | `ArithmeticException;3/2` | matched |
| Challenge | `ArithmeticException;-1/1073741824` | `-1/1073741824;-1/1073741824` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 543`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/commons-lang/pull/1865)
