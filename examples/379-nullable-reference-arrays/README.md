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
