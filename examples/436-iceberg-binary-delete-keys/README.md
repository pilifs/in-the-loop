# Iceberg reads binary equality deletes and snapshots a nested byte slice

A real Parquet equality delete left IDs 200 and 201 alongside 203 on the parent. The merged table scan returned only 203. A copied nested binary slice also retained AB after a source mutation and preserved the source position.

The table format is v2, the physical data and delete files are Parquet, and the scan projects only the integer ID.

| Question | Input |
|---|---|
| Intent | The four rows and three equal-width delete keys above. |
| Control | Read the same table immediately after appending the data file and before committing a delete. |
| Challenge | Create a nested `GenericRecord` containing a binary field whose ByteBuffer spans [A,B] inside [X,A,B,Y] (position 1, limit 3). Set that nested record on an outer record, call `outer.copy()`, then overwrite the source A with Z by absolute index. |

Run `python3 examples/tools/build.py 436` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are parquet. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/apache/iceberg/pull/12855) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)
