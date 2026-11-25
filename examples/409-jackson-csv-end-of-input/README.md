# Jackson CSV identifies the end of a quoted array row

The fix stopped advertising a phantom row at EOF. The brief's unwrapped, schema-less iterator stopped after the first of two quoted rows on the merge. The parent advertised the second row, then threw `MismatchedInputException`. The explicit bean schema worked on both sides.

Jackson documents array wrapping for iteration over schema-less `String[]` rows. With that setting, repeated lookahead read both one-cell rows on both pins, 3.3.0 and the current development revision. An independent unwrapped token reader also emitted both row arrays. The original challenge predicted multirow behavior for the wrong configuration. [Disambiguating controls](../../verification/merged-pr-links/upstream/409-wrapping.json) · [Release and development replay](../../verification/merged-pr-links/upstream/409.json)

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions. The CSV module comes from each source pin, built against released Jackson 3.2.0 dependencies because the snapshot graph is unavailable.

Run `python3 examples/tools/build.py 409` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/FasterXML/jackson-dataformats-text/pull/625)
