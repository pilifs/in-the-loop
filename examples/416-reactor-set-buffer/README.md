# Reactor fills a set buffer under bounded demand

The duplicate made the parent time out with no emitted set. The fix completed with {1,2} on one request. Two requests returned two distinct sets and the discard hook saw the duplicate 1 exactly once.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions. Both deployments use the same pin-built reactor-test subscriber. The reactor-core JAR changes with the revision.

Run `python3 examples/tools/build.py 416` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/reactor/reactor-core/pull/3822)
