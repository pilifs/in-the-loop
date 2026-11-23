# Unsigned offset checks in Commons Lang nibble conversion

Each nibble and signed offset is checked against a right shift or the method’s exact explicit exception.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `UnsignedNibble#nibble` (nibble) | For offset zero through three the method returns the right-shifted digit. Other offsets raise exactly IndexOutOfBoundsException. | established |
| `UnsignedNibble#left` (nibble) | Offset one retains the nibble shifted left instead of right. | refuted |
| `UnsignedNibble#acceptsNegative` (nibble) | The production method accepts minus one as an offset. | refuted |

Inspect each strict task with `python3 examples/tools/build.py --plan 388`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm nibble --output "$TMPDIR/semantics"
```

## Measured results

The campaign's ordinary native checker decided 0/3 at opening and 3/3 at qualification, with 1 established and 2 refuted on original-JVM replays.

| Entry | Opening native | Qualified native |
|---|---|---|
| nibble/nibble | [open (0.02 s)](../../verification/java-semantics-gap/opening/nibble/measurement.json) | [proved (2.91 s)](../../verification/java-semantics-gap/heap-and-gson/nibble/measurement.json) |
| nibble/left | [open (0.02 s)](../../verification/java-semantics-gap/opening/nibble/measurement.json) | [refuted (0.02 s)](../../verification/java-semantics-gap/heap-and-gson/nibble/measurement.json) |
| nibble/acceptsNegative | [open (0.01 s)](../../verification/java-semantics-gap/opening/nibble/measurement.json) | [refuted (0.03 s)](../../verification/java-semantics-gap/heap-and-gson/nibble/measurement.json) |

[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)
