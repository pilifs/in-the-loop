# Gson tree numbers retain the requested integral wrapper type

The tree retained Byte, Short and Integer for primitive and wrapper declarations. Narrowing integer 257 and byte 1 produced identical Byte values and numeric JSON text.

Java Number.byteValue discards higher bits for an Integer; 257 and 1 have the same low eight bits. Text alone erases wrapper width.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `Long:1:1/Long:1:1/Long:1:1/Long:1:1/Long:1:1/Long:1:1` | `Byte:1:1/Short:1:1/Integer:1:1/Byte:1:1/Short:1:1/Integer:1:1` | matched |
| Control | `Long:1:1/Long:1:1` | `Long:1:1/Long:1:1` | matched |
| Challenge | `Long:1:1/Long:1:1` | `Byte:1:1/Byte:1:1` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 563`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/google/gson/pull/2998)
