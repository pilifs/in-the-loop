# Enum lookup returns the original constant

Two equal-but-distinct names, null, lowercase and unknown strings distinguish constant identity and the two lookup exceptions.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `EnumNames#lookup` (enum) | Two separately allocated valid names recover the canonical constants, null raises NPE, and both invalid names raise IAE. | established |
| `EnumNames#ordinal` (enum) | Both original constants have the expected ordinal. | established |
| `EnumNames#alwaysZero` (enum) | Both original enum constants have ordinal zero. | refuted |

Inspect each strict task with `python3 examples/tools/build.py --plan 389`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm enum --output "$TMPDIR/semantics"
```

## Measured results

The campaign's ordinary native checker decided 2/3 at opening and 3/3 at qualification, with 2 established and 1 refuted on original-JVM replays.

| Entry | Opening native | Qualified native |
|---|---|---|
| enum/lookup | [open (0.02 s)](../../verification/java-semantics-gap/opening/enum/measurement.json) | [proved (0.03 s)](../../verification/java-semantics-gap/qualified/enum/measurement.json) |
| enum/ordinal | [proved (0.02 s)](../../verification/java-semantics-gap/opening/enum/measurement.json) | [proved (0.02 s)](../../verification/java-semantics-gap/qualified/enum/measurement.json) |
| enum/alwaysZero | [refuted (0.03 s)](../../verification/java-semantics-gap/opening/enum/measurement.json) | [refuted (0.03 s)](../../verification/java-semantics-gap/qualified/enum/measurement.json) |

[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)
