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

## Measured results

Ordinary native 8/8. The Jackson conversions disagree at 16,777,216 of the 2⁵⁴ admitted long values. The direct binary64 underflow interval contains 2⁵² + 1 values, including the halfway input that rounds to positive zero.

| Original entry | Opening native | Final native | Integrated JBMC | Ordinary task receipt |
|---|---|---|---|---|
| NodeChecks#direct | open | proved | proved | [established](receipts/node-checks-direct/20261123T175644Z-8930bcde/result.json) |
| NodeChecks#same | open | refuted | refuted | [refuted](receipts/node-checks-same/20261123T175647Z-adfae7f5/result.json) |
| NodeChecks#publicSubnormal | entry refused | proved | proved | [established](receipts/node-checks-public-subnormal/20261123T175650Z-67315f52/result.json) |
| NodeChecks#wrongSubnormal | entry refused | refuted | refuted | [refuted](receipts/node-checks-wrong-subnormal/20261123T175653Z-07357b73/result.json) |
| NodeChecks#commons | open | proved | proved | [established](receipts/node-checks-commons/20261123T175655Z-932ae667/result.json) |
| ConversionEquivalence#classified | open | proved | proved | [established](receipts/conversion-equivalence-classified/20261123T175658Z-a06b7e22/result.json) |
| NodeChecks#intrinsicSubnormal | entry refused | proved | proved | [established](receipts/node-checks-intrinsic-subnormal/20261123T175701Z-4ee8468e/result.json) |
| NodeChecks#mantissaSubnormal | open | proved | unreproduced witness | [established](receipts/node-checks-mantissa-subnormal/20261123T175703Z-c6c8cecb/result.json) |

[Paired measurements](../../verification/jbmc-fast-follow/successor/numeric/paired/measurement.json) · [Campaign results](../../llm-dlc/loops/jbmc-fast-follow-calls-conversions-and-arrays-results.md)
