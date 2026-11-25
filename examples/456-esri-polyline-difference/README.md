# Esri Geometry restores the surviving segments of a closed polyline

| History | Public observation |
|---|---|
| Intent | Both A–T and T–A threw GeometryException on the parent. Each merged call returned one copy of every edge of both loops, with length 15261.368605810665. The brief left the reverse parent outcome open. |
| Control | Both revisions preserved the five open edges, length 7794.600029974981. Neither a closing edge nor any remote segment appeared. |
| Challenge | Extending T–A to B removed exactly A–B on both revisions. Each of the ten surviving edges occurred once. The length was 13326.118751140732, equal to the original length minus hypot(1914, −286). The parent observation had no prediction. |

The oracle sweeps each original edge against the actual returned segments and checks the converse for foreign geometry. It counts nonzero intervals, handles split or reversed edges and implicit closure, and checks absolute length error within 1e−7 coordinate units. Collinearity uses perpendicular distance at most 1e−8.

Run `python3 examples/tools/build.py 456` with the prepared `merged-pr-links-n01-n05` cache. Each revision and history starts a fresh JVM with the same compiled caller. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observations](observations.json) · [Upstream PR](https://github.com/Esri/geometry-api-java/pull/329) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-n01-n05-brief-setup.md)
