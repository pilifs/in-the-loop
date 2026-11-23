# Method-reference conversions on Guava and Commons Lang

Java method references widen comparison operands and results, unbox nullable arguments, and respect ComparisonChain short-circuiting.

| Entry | Statement | Expected |
|---|---|---|
| `Lift#primitiveGood` | Widening two ints into Longs.compare and widening its signed result preserves the independent three-way ordering. | established |
| `Lift#primitiveWrong` | Widening two ints into Longs.compare and widening its signed result always gives a nonnegative value. | refuted |
| `Lift#boxedGood` | Unboxing the two Integers into Longs.compare and widening its signed result preserves the independent three-way ordering. | established |
| `Lift#boxedWrong` | Unboxing the two Integers into Longs.compare and widening its signed result always gives a nonnegative value. | refuted |
| `Lift#returnGood` | Widening the signed result of Commons Lang NumberUtils.compare(short,short) preserves the independent three-way ordering. | established |
| `Lift#returnWrong` | Widening the signed result of Commons Lang NumberUtils.compare(short,short) always gives a nonnegative value. | refuted |
| `Lift#boxedNull` | A null Integer throws NullPointerException on an active unboxing call. | established |
| `Lift#staticGood` | The direct Guava call preserves signed three-way ordering. | established |
| `Lift#staticWrong` | The direct Guava call always returns a nonnegative value. | refuted |
| `Chain#good` | An active ComparisonChain preserves the independent signed comparison. | established |
| `Chain#wrong` | An active ComparisonChain always returns a nonnegative value. | refuted |
| `Chain#skipsNull` | A settled comparison skips the null arguments. | established |
| `Chain#rejectsNull` | A tied comparison unboxes the null argument and throws NullPointerException. | established |

Inspect the ordinary tasks with `python3 examples/tools/build.py --plan 392`. The comparison uses the same product classes for both engines and replays each qualified refutation on the original JVM. [Campaign brief](../../llm-dlc/loops/jbmc-fast-follow-calls-conversions-and-arrays.md)
