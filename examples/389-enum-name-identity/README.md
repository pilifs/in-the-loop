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
