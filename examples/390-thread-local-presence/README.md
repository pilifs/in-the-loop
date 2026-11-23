# A stored null differs from an absent thread-local binding

Two keys with counting suppliers expose their initializations, fresh references and stored nulls, including the Spring factory.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `ThreadLocalHistory#kernel` (locals) | All four histories preserve per-key bindings and supplier counts on ThreadLocal. | established |
| `ThreadLocalHistory#spring` (locals) | All four histories preserve per-key bindings and supplier counts on NamedThreadLocal.withInitial. | established |
| `ThreadLocalHistory#nullInitializes` (locals) | Reading a stored null calls the initializer again. | refuted |

Inspect each strict task with `python3 examples/tools/build.py --plan 390`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm locals --output "$TMPDIR/semantics"
```

## Measured results

The campaign's ordinary native checker decided 1/3 at opening and 3/3 at qualification, with 2 established and 1 refuted on original-JVM replays.

| Entry | Opening native | Qualified native |
|---|---|---|
| locals/kernel | [open (0.02 s)](../../verification/java-semantics-gap/opening/locals/measurement.json) | [proved (0.04 s)](../../verification/java-semantics-gap/qualified/locals/measurement.json) |
| locals/spring | [open (0.02 s)](../../verification/java-semantics-gap/opening/locals/measurement.json) | [proved (0.03 s)](../../verification/java-semantics-gap/qualified/locals/measurement.json) |
| locals/nullInitializes | [refuted (0.14 s)](../../verification/java-semantics-gap/opening/locals/measurement.json) | [refuted (0.14 s)](../../verification/java-semantics-gap/qualified/locals/measurement.json) |

[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)
