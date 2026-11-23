# Observe an override during superclass construction

Commons Lang’s StrBuilder constructor calls the subclass before its field initializer. A second call observes the initialized receiver and contents.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `ConstructorPhase#history` (construction) | Commons Lang’s StrBuilder constructor calls the subclass before its field initializer. A second call observes the initialized receiver and contents. | established |
| `ConstructorPhase#emptySkips` (construction) | An empty constructor argument skips the append override. | refuted |
| `ConstructorPhase#alreadyInitialized` (construction) | The override observes the subclass field initializer during superclass construction. | refuted |

Inspect each strict task with `python3 examples/tools/build.py --plan 386`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm construction --output "$TMPDIR/semantics"
```

## Measured results

The campaign's ordinary native checker decided 2/3 at opening and 3/3 at qualification, with 1 established and 2 refuted on original-JVM replays.

| Entry | Opening native | Qualified native |
|---|---|---|
| construction/history | [open (0.02 s)](../../verification/java-semantics-gap/opening/construction/measurement.json) | [proved (0.03 s)](../../verification/java-semantics-gap/decimal-transfer/callers/construction/measurement.json) |
| construction/emptySkips | [refuted (0.03 s)](../../verification/java-semantics-gap/opening/construction/measurement.json) | [refuted (0.02 s)](../../verification/java-semantics-gap/decimal-transfer/callers/construction/measurement.json) |
| construction/alreadyInitialized | [refuted (0.03 s)](../../verification/java-semantics-gap/opening/construction/measurement.json) | [refuted (0.02 s)](../../verification/java-semantics-gap/decimal-transfer/callers/construction/measurement.json) |

[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)
