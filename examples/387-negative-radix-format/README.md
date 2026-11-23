# Format a negative integer in radix sixteen

An independent ASCII digit calculation checks the sign and order of both digits from 16 through 255.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `RadixDigits#hex` (radix) | The result consists of a minus sign and the two independently computed hexadecimal digits in order. | established |
| `RadixDigits#lowFirst` (radix) | The low nibble supplies the first digit after the minus sign. | refuted |

Inspect each strict task with `python3 examples/tools/build.py --plan 387`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm radix --output "$TMPDIR/semantics"
```
