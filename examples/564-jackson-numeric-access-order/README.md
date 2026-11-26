# Numeric accessors return the current token at its requested precision

After reading decimal 2.5, the integer view of the next token 7.5 now returned 7. Reading a large number as double first preserved all digits on a later BigInteger access.

BigInteger on the original decimal text is an independent exact oracle, unaffected by the consumer’s earlier request for a double.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `DOUBLE/2/7.5/7.5` | `DOUBLE/7/7.5/7.5` | matched |
| Control | `7/7.0/END_ARRAY` | `7/7.0/END_ARRAY` | matched |
| Challenge | `12345678901234568000000:true/12345678901234567890123:true` | `12345678901234567890123:true/12345678901234567890123:true` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 564`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/FasterXML/jackson-core/pull/1816)

With identical compiled caller bytes, 2.21.8 matched the parent and 2.21.9 matched the landing on all three histories. [Release measurements](../../verification/merged-pr-links/r01-r50/release-observations.json)
