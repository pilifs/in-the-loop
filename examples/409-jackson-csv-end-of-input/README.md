# Jackson CSV identifies the end of a quoted array row

The fix stopped advertising a phantom row at EOF. With two quoted rows it also reported EOF before the second real row. The parent advertised that row and then threw MismatchedInputException. The explicit bean schema worked on both sides.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions. The CSV module comes from each source pin, built against released Jackson 3.2.0 dependencies because the snapshot graph is unavailable.

Run `python3 examples/tools/build.py 409` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/FasterXML/jackson-dataformats-text/pull/625)
