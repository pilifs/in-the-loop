# A list copied from a caller-owned array

List construction isolates later slot replacement and retains aliases to the mutable elements.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `ListHistory#fromArray` (lists) | Replacing a source slot leaves the original elements and their shared mutable state visible through List.of. | established |
| `ListHistory#fromCollection` (lists) | List.copyOf(Arrays.asList(source)) isolates the slots and preserves the element identities and mutations. | established |
| `ListHistory#followsSlot` (lists) | The list follows replacement of the first slot in the original caller array. | refuted |

Inspect each strict task with `python3 examples/tools/build.py --plan 376`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm lists --output "$TMPDIR/semantics"
```

## Measured results

The campaign's ordinary native checker decided 0/3 at opening and 3/3 at qualification, with 2 established and 1 refuted on original-JVM replays.

| Entry | Opening native | Qualified native |
|---|---|---|
| lists/fromArray | [open (0.02 s)](../../verification/java-semantics-gap/opening/lists/measurement.json) | [proved (0.02 s)](../../verification/java-semantics-gap/heap-and-gson/lists/measurement.json) |
| lists/fromCollection | [open (0.02 s)](../../verification/java-semantics-gap/opening/lists/measurement.json) | [proved (0.01 s)](../../verification/java-semantics-gap/heap-and-gson/lists/measurement.json) |
| lists/followsSlot | [open (0.01 s)](../../verification/java-semantics-gap/opening/lists/measurement.json) | [refuted (0.03 s)](../../verification/java-semantics-gap/heap-and-gson/lists/measurement.json) |

[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)
