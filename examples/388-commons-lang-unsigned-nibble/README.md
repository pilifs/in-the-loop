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
