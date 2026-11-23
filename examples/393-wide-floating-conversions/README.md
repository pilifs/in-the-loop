# Rounding across two Jackson numeric conversion paths

Jackson and Commons Lang convert wide integer and tiny binary64 inputs to binary32 at independently checked rounding boundaries.

| Entry | Statement | Expected |
|---|---|---|
| `NodeChecks#direct` | LongNode.floatValue rounds to the independently computed nearest-even grid point. | established |
| `NodeChecks#same` | The direct and double-intermediate Jackson paths always return equal floats. | refuted |
| `NodeChecks#publicSubnormal` | The halfway tie gives zero and every larger double through 2^-149 gives the least positive float. | established |
| `NodeChecks#wrongSubnormal` | Every positive double in the tiny interval converts to a positive float. | refuted |
| `NodeChecks#commons` | Commons Lang MutableLong.floatValue agrees with the independent integer oracle. | established |
| `ConversionEquivalence#classified` | The two Jackson conversions differ exactly at the two parity-selected neighbors of each midpoint. | established |
| `NodeChecks#intrinsicSubnormal` | A direct JVM conversion at the underflow boundary has the correctly rounded value. | established |
| `NodeChecks#mantissaSubnormal` | The long-bits adapter checks one exponent bin below the least float. | established |

Inspect the ordinary tasks with `python3 examples/tools/build.py --plan 393`. The comparison uses the same product classes for both engines and replays each qualified refutation on the original JVM. [Campaign brief](../../llm-dlc/loops/jbmc-fast-follow-calls-conversions-and-arrays.md)
