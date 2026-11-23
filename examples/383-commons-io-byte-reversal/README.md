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

## Measured results

The campaign's ordinary native checker decided 2/4 at opening and 4/4 at qualification, with 2 established and 2 refuted on original-JVM replays.

| Entry | Opening native | Qualified native |
|---|---|---|
| endian/reverseInt | [open (0.02 s)](../../verification/java-semantics-gap/opening/endian/measurement.json) | [proved (0.01 s)](../../verification/java-semantics-gap/heap-and-gson/endian/measurement.json) |
| endian/reverseLong | [open (0.02 s)](../../verification/java-semantics-gap/opening/endian/measurement.json) | [proved (0.01 s)](../../verification/java-semantics-gap/heap-and-gson/endian/measurement.json) |
| endian/rotateInt | [refuted (0.04 s)](../../verification/java-semantics-gap/opening/endian/measurement.json) | [refuted (0.02 s)](../../verification/java-semantics-gap/heap-and-gson/endian/measurement.json) |
| endian/rotateLong | [refuted (0.02 s)](../../verification/java-semantics-gap/opening/endian/measurement.json) | [refuted (0.03 s)](../../verification/java-semantics-gap/heap-and-gson/endian/measurement.json) |

[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)
