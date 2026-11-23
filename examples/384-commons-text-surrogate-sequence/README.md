# Decode a surrogate pair through CharSequence

The public Commons Text translator receives a two-unit sequence at either offset. Its consumed count and writer effects are independently observable.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `SurrogateUnits#translate` (surrogates) | The translator consumes exactly the unpaired surrogate at the selected offset and writes no units. | established |
| `SurrogateUnits#removeEvery` (surrogates) | The translator consumes every surrogate at the first offset, including the high half of a valid pair. | refuted |

Inspect each strict task with `python3 examples/tools/build.py --plan 384`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm surrogates --output "$TMPDIR/semantics"
```

## Measured results

The campaign's ordinary native checker decided 0/2 at opening and 2/2 at qualification, with 1 established and 1 refuted on original-JVM replays.

| Entry | Opening native | Qualified native |
|---|---|---|
| surrogates/translate | [open (0.02 s)](../../verification/java-semantics-gap/opening/surrogates/measurement.json) | [proved (0.02 s)](../../verification/java-semantics-gap/qualified/surrogates/measurement.json) |
| surrogates/removeEvery | [open (0.02 s)](../../verification/java-semantics-gap/opening/surrogates/measurement.json) | [refuted (0.10 s)](../../verification/java-semantics-gap/qualified/surrogates/measurement.json) |

[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)
