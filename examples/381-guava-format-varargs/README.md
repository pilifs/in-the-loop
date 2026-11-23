# Guava formatting preserves the caller’s varargs

The historical formatters receive Integer[] and Object[] with the same three references. The caller observes returned text, the exact exception and the final slots.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `FormatHistory#retained` (guava-parent) | Both array types produce the requested text while preserving all three slots by reference. | refuted |
| `FormatHistory#parentBehavior` (guava-parent) | The typed array throws before any write and the genuine Object[] is filled with the three formatted strings. | established |
| `FormatHistory#retained` (guava-fix) | Both array types produce the requested text while preserving all three slots by reference. | established |
| `FormatHistory#parentBehavior` (guava-fix) | The typed array throws before any write and the genuine Object[] is filled with the three formatted strings. | refuted |

Inspect each strict task with `python3 examples/tools/build.py --plan 381`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm guava-parent guava-fix --output "$TMPDIR/semantics"
```
