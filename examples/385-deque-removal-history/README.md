# Remove an element before or after iterator prefetch

JDK deque iterator removal and released Commons filter iterators are checked through the original owner and element identities.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `DequeRemoval#history` (deque) | JDK deque iterator removal and released Commons filter iterators are checked through the original owner and element identities. | established |
| `DequeRemoval#stillReturns` (deque) | The old iterator returns the original next element after its owner removed it. | refuted |
| `DequeRemoval#singleton` (deque) | Prefetch keeps the element pending and removal after consumption follows the underlying singleton policy. | established |
| `DequeRemoval#filtered` (deque) | A pending element prevents delegate removal. Removal after consumption updates the correct original deque. | established |

Inspect each strict task with `python3 examples/tools/build.py --plan 385`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm deque --output "$TMPDIR/semantics"
```

## Measured results

The campaign's ordinary native checker decided 1/4 at opening and 4/4 at qualification, with 3 established and 1 refuted on original-JVM replays.

| Entry | Opening native | Qualified native |
|---|---|---|
| deque/history | [open (0.02 s)](../../verification/java-semantics-gap/opening/deque/measurement.json) | [proved (0.01 s)](../../verification/java-semantics-gap/decimal-transfer/callers/deque/measurement.json) |
| deque/stillReturns | [open (0.02 s)](../../verification/java-semantics-gap/opening/deque/measurement.json) | [refuted (0.05 s)](../../verification/java-semantics-gap/decimal-transfer/callers/deque/measurement.json) |
| deque/singleton | [proved (0.03 s)](../../verification/java-semantics-gap/opening/deque/measurement.json) | [proved (0.02 s)](../../verification/java-semantics-gap/decimal-transfer/callers/deque/measurement.json) |
| deque/filtered | [open (0.02 s)](../../verification/java-semantics-gap/opening/deque/measurement.json) | [proved (0.02 s)](../../verification/java-semantics-gap/decimal-transfer/callers/deque/measurement.json) |

[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)
