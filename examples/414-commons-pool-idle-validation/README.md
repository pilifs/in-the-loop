# Commons Pool destroys an idle object when validation throws

Both pool variants rethrew the original exception object. The parent stranded A and exhausted its single slot. The fix destroyed A once, created a distinct B and accepted its return with one idle and zero active.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions.

Run `python3 examples/tools/build.py 414` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/apache/commons-pool/pull/85)
