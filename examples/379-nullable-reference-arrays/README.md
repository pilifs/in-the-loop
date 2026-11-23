# Nullable array cells and runtime receiver types

Direct array arguments distinguish null, empty, null-element and object-element heaps. Constructed histories observe aliasing, dispatch and Gson’s requested class.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `ReferenceCells#categories` (arrays) | The range covers the four kinds of nullable Item[] inputs. | established |
| `ReferenceCells#noNullCell` (arrays) | The first cell can never be null in a nonempty array. | refuted |
| `ReferenceCells#noItemCell` (arrays) | The first cell can never contain an item in a nonempty array. | refuted |
| `ReferenceCells#followsAlias` (arrays) | Incrementing through one slot affects the other exactly when the original items were shared, including overflow. | established |
| `ReferenceCells#alwaysShares` (arrays) | Equal-valued initial references always share the later field write. | refuted |
| `ReceiverScope#exact` (receiver) | The declared-parent assertion holds for null and an exact parent. | established |
| `ReceiverScope#parentOrChild` (receiver) | The declared-parent assertion holds for null, an exact parent and a legal child. | refuted |
| `GsonRequestedClass#compatible` (gson-parent) | Every compatible request returns its expected concrete Gson class. | established |
| `GsonRequestedClass#syntax` (gson-parent) | Every incompatible request raises exactly JsonSyntaxException. | refuted |
| `GsonRequestedClass#compatible` (gson-fix) | Every compatible request returns its expected concrete Gson class. | established |
| `GsonRequestedClass#syntax` (gson-fix) | Every incompatible request raises exactly JsonSyntaxException. | established |

Inspect each strict task with `python3 examples/tools/build.py --plan 379`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm arrays receiver gson-parent gson-fix --output "$TMPDIR/semantics"
```

## Measured results

The campaign's ordinary native checker decided 4/11 at opening and 11/11 at qualification, with 6 established and 5 refuted on original-JVM replays.

| Entry | Opening native | Qualified native |
|---|---|---|
| arrays/categories | [open (0.00 s)](../../verification/java-semantics-gap/opening/arrays/measurement.json) | [proved (0.02 s)](../../verification/java-semantics-gap/decimal-transfer/callers/arrays/measurement.json) |
| arrays/noNullCell | [open (0.00 s)](../../verification/java-semantics-gap/opening/arrays/measurement.json) | [refuted (0.07 s)](../../verification/java-semantics-gap/decimal-transfer/callers/arrays/measurement.json) |
| arrays/noItemCell | [open (0.00 s)](../../verification/java-semantics-gap/opening/arrays/measurement.json) | [refuted (0.06 s)](../../verification/java-semantics-gap/decimal-transfer/callers/arrays/measurement.json) |
| arrays/followsAlias | [proved (0.02 s)](../../verification/java-semantics-gap/opening/arrays/measurement.json) | [proved (0.02 s)](../../verification/java-semantics-gap/decimal-transfer/callers/arrays/measurement.json) |
| arrays/alwaysShares | [refuted (0.02 s)](../../verification/java-semantics-gap/opening/arrays/measurement.json) | [refuted (0.02 s)](../../verification/java-semantics-gap/decimal-transfer/callers/arrays/measurement.json) |
| receiver/exact | [proved (0.02 s)](../../verification/java-semantics-gap/opening/receiver/measurement.json) | [proved (0.02 s)](../../verification/java-semantics-gap/decimal-transfer/callers/receiver/measurement.json) |
| receiver/parentOrChild | [refuted (0.03 s)](../../verification/java-semantics-gap/opening/receiver/measurement.json) | [refuted (0.02 s)](../../verification/java-semantics-gap/decimal-transfer/callers/receiver/measurement.json) |
| gson-parent/compatible | [open (0.02 s)](../../verification/java-semantics-gap/opening/gson-parent/measurement.json) | [proved (7.34 s)](../../verification/java-semantics-gap/decimal-transfer/callers/gson-parent/measurement.json) |
| gson-parent/syntax | [open (0.03 s)](../../verification/java-semantics-gap/opening/gson-parent/measurement.json) | [refuted (9.19 s)](../../verification/java-semantics-gap/decimal-transfer/callers/gson-parent/measurement.json) |
| gson-fix/compatible | [open (0.02 s)](../../verification/java-semantics-gap/opening/gson-fix/measurement.json) | [proved (7.78 s)](../../verification/java-semantics-gap/decimal-transfer/callers/gson-fix/measurement.json) |
| gson-fix/syntax | [open (0.02 s)](../../verification/java-semantics-gap/opening/gson-fix/measurement.json) | [proved (0.12 s)](../../verification/java-semantics-gap/decimal-transfer/callers/gson-fix/measurement.json) |

The direct mutation controls reconstructed a shared object and two distinct objects with equal maximal int fields. On every incompatible public Gson call the parent threw ClassCastException and the fix threw JsonSyntaxException. The native checker also verified all five compatible selections on both builds.

[Direct mutation controls](../../verification/java-semantics-gap/heap-and-gson/histories/measurement.json) · [Parent exception proof](../../verification/java-semantics-gap/heap-and-gson/gson-parent/exception-control/measurement.json) · [Fix counterexample](../../verification/java-semantics-gap/heap-and-gson/gson-fix/exception-control/measurement.json)

[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)
