# UTF-16 prefix matching at a signed offset

An independent charAt loop checks all offsets and strings of up to four UTF-16 units. The empty prefix also matches at the end.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `OffsetPrefix#small` (prefix) | Both prefixes give the expected truth value for every offset from -1 through six. | established |
| `OffsetPrefix#beforeEnd` (prefix) | An empty prefix matches strictly before the final offset. | refuted |
| `OffsetPrefix#wide` (prefix) | For independent bounded UTF-16 inputs and any signed offset the public method agrees with the charAt oracle. | established |
| `OffsetPrefix#nullPrefix` (prefix) | A null prefix raises NullPointerException at a valid offset. | established |

Inspect each strict task with `python3 examples/tools/build.py --plan 378`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm prefix --output "$TMPDIR/semantics"
```
