# Eclipse JDT formats a real region after an empty first line

The public formatter threw StringIndexOutOfBoundsException on the parent. The fixed edit produced the exact LF and CRLF texts, preserved the leading break and was idempotent on CRLF. Both single-region controls held.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions. Each pin supplies its formatter overlay. The rest of its linewrap package comes from JDT Core 3.47.0. The other packages retain their release signatures so the public factory can load ECJ on a plain classpath.

Run `python3 examples/tools/build.py 420` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/eclipse-jdt/eclipse.jdt.core/pull/5380)
