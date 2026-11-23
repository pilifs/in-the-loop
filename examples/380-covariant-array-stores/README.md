# A covariant store preserves the old cell on failure

A single store and a released Commons iterator expose the exception type and the original cell through a retained reference.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `ArrayStores#history` (stores) | A single store and a released Commons iterator expose the exception type and the original cell through a retained reference. | established |
| `ArrayStores#alwaysSucceeds` (stores) | An incompatible object can be stored in a String array through its Object[] view. | refuted |
| `IteratorStores#history` (store-iterator) | A single store and a released Commons iterator expose the exception type and the original cell through a retained reference. | established |

Inspect each strict task with `python3 examples/tools/build.py --plan 380`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm stores store-iterator --output "$TMPDIR/semantics"
```

## Measured results

The campaign's ordinary native checker decided 0/3 at opening and 3/3 at qualification, with 2 established and 1 refuted on original-JVM replays.

| Entry | Opening native | Qualified native |
|---|---|---|
| stores/history | [open (0.02 s)](../../verification/java-semantics-gap/opening/stores/measurement.json) | [proved (0.02 s)](../../verification/java-semantics-gap/heap-and-gson/stores/measurement.json) |
| stores/alwaysSucceeds | [open (0.02 s)](../../verification/java-semantics-gap/opening/stores/measurement.json) | [refuted (0.02 s)](../../verification/java-semantics-gap/heap-and-gson/stores/measurement.json) |
| store-iterator/history | [open (0.02 s)](../../verification/java-semantics-gap/opening/store-iterator/measurement.json) | [proved (0.02 s)](../../verification/java-semantics-gap/heap-and-gson/store-iterator/measurement.json) |

[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)
