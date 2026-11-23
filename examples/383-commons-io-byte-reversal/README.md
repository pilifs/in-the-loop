# Reverse every byte of an int or long

Commons IO’s released swap methods are compared with the JDK for every word. Rotation supplies a distinct incorrect rule.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `ByteReversal#reverseInt` (endian) | The original 32-bit swap agrees with JDK byte reversal for every bit pattern. | established |
| `ByteReversal#reverseLong` (endian) | The original 64-bit swap agrees with JDK byte reversal for every bit pattern. | established |
| `ByteReversal#rotateInt` (endian) | The original 32-bit swap agrees with half-word rotation. | refuted |
| `ByteReversal#rotateLong` (endian) | The original 64-bit swap agrees with half-word rotation. | refuted |

Inspect each strict task with `python3 examples/tools/build.py --plan 383`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm endian --output "$TMPDIR/semantics"
```
