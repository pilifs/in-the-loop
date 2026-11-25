# RxJava detaches the stop subscription on disposal

Disposing the single detached the main on both pins. The fix also detached the stop subscriber immediately. With two Maybe sources the fixed cancellation counters changed from (1,0) to (1,1), and only the second observer completed.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions.

Run `python3 examples/tools/build.py 415` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/ReactiveX/RxJava/pull/6019)
