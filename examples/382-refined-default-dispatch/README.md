# Default interface methods on a refined receiver

Interface order, a class override and a qualified super call determine the result for every signed int.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `DefaultDispatch#dispatch` (dispatch) | Both declaration orders select the refined default and the class override wins, at every int value. | established |
| `DefaultDispatch#firstDeclared` (dispatch) | The first-listed base interface wins over the more specific default. | refuted |

Inspect each strict task with `python3 examples/tools/build.py --plan 382`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm dispatch --output "$TMPDIR/semantics"
```

## Measured results

The campaign's ordinary native checker decided 0/2 at opening and 2/2 at qualification, with 1 established and 1 refuted on original-JVM replays.

| Entry | Opening native | Qualified native |
|---|---|---|
| dispatch/dispatch | [JVM-contradicted violation (0.03 s)](../../verification/java-semantics-gap/opening/dispatch/measurement.json) | [proved (0.01 s)](../../verification/java-semantics-gap/decimal-transfer/callers/dispatch/measurement.json) |
| dispatch/firstDeclared | [JVM-contradicted proof (0.02 s)](../../verification/java-semantics-gap/opening/dispatch/measurement.json) | [refuted (0.02 s)](../../verification/java-semantics-gap/decimal-transfer/callers/dispatch/measurement.json) |

[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)
