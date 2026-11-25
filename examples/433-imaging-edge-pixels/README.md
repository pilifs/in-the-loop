# Commons Imaging reads the rectangular corner of a JPEG-compressed TIFF

The corrected decoder matched all 16,129 reference pixels within tolerance. The six bottom-right pixels were bit-identical through the whole-image and regional APIs. The original 264×264 control passed on both revisions.

The original 264×264 image control runs on both revisions. The small image and its rectangular edge comparison run on the fixed decoder. The earlier setup independently recorded a parent bounds exception in the transplanted upstream tests.

| Question | Input |
|---|---|
| Intent | Read the complete 127×127 RGB JPEG-in-TIFF and compare it with the paired reference TIFF. |
| Control | Use the existing 264×264 pair TestJpegTiles264x264.tiff and TestSample264x264.tiff. |
| Challenge | On the merge use the same 127×127 compressed file. Compare a regional decode of (x=124,y=125,width=3,height=2) with the corresponding rectangle from its whole-image decode. |

Run `python3 examples/tools/build.py 433` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pins. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/apache/commons-imaging/pull/335) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)

The four TIFF fixtures are copied byte-for-byte from the Apache Commons Imaging test resources at the merge. Their individual SHA-256 digests appear in the observation receipt. [Upstream test resources](https://github.com/apache/commons-imaging/tree/cbdb978098a042cb5fd2a768f6d8575835c28278/src/test/resources/data/images/tiff/14)
