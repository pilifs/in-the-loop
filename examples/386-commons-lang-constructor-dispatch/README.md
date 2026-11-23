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
