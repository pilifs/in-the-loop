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

## Measured results

Ordinary native 13/13. The integrated Guava (0, 1) witness originally exited during replay. The same input now returns a signed negative long through the method reference. A settled ComparisonChain skips null unboxing and a tied chain performs it.

| Original entry | Opening native | Final native | Integrated JBMC | Ordinary task receipt |
|---|---|---|---|---|
| Lift#primitiveGood | open | proved | proved | [established](receipts/lift-primitive-good/20261123T175607Z-a0c0ae53/result.json) |
| Lift#primitiveWrong | open | refuted | refuted | [refuted](receipts/lift-primitive-wrong/20261123T175610Z-62a64258/result.json) |
| Lift#boxedGood | open | proved | proved | [established](receipts/lift-boxed-good/20261123T175613Z-47350036/result.json) |
| Lift#boxedWrong | open | refuted | refuted | [refuted](receipts/lift-boxed-wrong/20261123T175616Z-269ad62c/result.json) |
| Lift#returnGood | open | proved | proved | [established](receipts/lift-return-good/20261123T175619Z-9a1d025a/result.json) |
| Lift#returnWrong | open | refuted | refuted | [refuted](receipts/lift-return-wrong/20261123T175622Z-a4f3d13e/result.json) |
| Lift#boxedNull | open | proved | proved | [established](receipts/lift-boxed-null/20261123T175625Z-884e700b/result.json) |
| Lift#staticGood | proved | proved | proved | [established](receipts/lift-static-good/20261123T175628Z-2d803720/result.json) |
| Lift#staticWrong | refuted | refuted | refuted | [refuted](receipts/lift-static-wrong/20261123T175630Z-d2927ef7/result.json) |
| Chain#good | open | proved | unreproduced witness | [established](receipts/chain-good/20261123T175633Z-93ff59ec/result.json) |
| Chain#wrong | open | refuted | unreproduced witness | [refuted](receipts/chain-wrong/20261123T175636Z-377322c5/result.json) |
| Chain#skipsNull | proved | proved | open | [established](receipts/chain-skips-null/20261123T175638Z-ee77ce49/result.json) |
| Chain#rejectsNull | open | proved | open | [established](receipts/chain-rejects-null/20261123T175641Z-98494327/result.json) |

[Paired measurements](../../verification/jbmc-fast-follow/successor/callbacks/paired/measurement.json) · [Campaign results](../../llm-dlc/loops/jbmc-fast-follow-calls-conversions-and-arrays-results.md)
