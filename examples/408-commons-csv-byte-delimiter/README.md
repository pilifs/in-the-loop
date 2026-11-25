# Commons CSV reports restartable UTF-8 byte positions

The parent iterator wrapped a CharacterCodingException. The fix reported the second record at byte 8 with LF and byte 9 with CRLF. Reopening at byte 9 returned exactly the second record at local offset zero.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions.

Run `python3 examples/tools/build.py 408` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/apache/commons-csv/pull/613)
