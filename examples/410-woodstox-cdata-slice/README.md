# Woodstox validates and repairs selected character slices

Both writers round-tripped the safe slice as OK. The fixed writer reported array index 5 in both rejection histories and round-tripped the selected text with two embedded delimiters when repair was enabled.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions. The ordinary text slice runs on both writers. Delimiter recognition, repair and replacement diagnostics are measured on the corrected writer.

Run `python3 examples/tools/build.py 410` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/FasterXML/woodstox/pull/335)
