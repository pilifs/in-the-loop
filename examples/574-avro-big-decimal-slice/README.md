# Preserve a decimal’s individual scale in an Avro bytes field

Avro’s new converter preserved the scale difference between 12.3 and 12.30. It read a standalone encoding as 12.30 but decoded a slice exposing identical bytes as the preceding 7.

The two views expose the same byte sequence, and the prefix is itself one complete encoding. The comparison needs no assumption about interoperability with another language.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `throws java.lang.NoClassDefFoundError` | `123@1/1230@2` | matched |
| Control | `-1230@2` | `-1230@2` | matched |
| Challenge | `throws java.lang.NoClassDefFoundError` | `1230@2/7@0` | refuted |

With the prepared R-series cache, run `python3 examples/tools/build.py 574`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/avro/pull/2282)
