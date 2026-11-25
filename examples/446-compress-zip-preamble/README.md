# Commons Compress reads entries and reports the ZIP preamble

| History | Observed result |
|---|---|
| Intent | The parent found zero entries in the prefixed fixture. The merge returned its named 50-byte body, offset 15 and the complete 15-byte prefix. |
| Control | Removing 15 bytes restored the same entry and body on both revisions. The new accessors reported zero and null on the merge. |
| Challenge | Both generated files had a local header at byte 15 and yielded the complete body. The writer-produced file reported offset zero and a null prefix. |

The registered return explicitly marks the prefix API as unavailable on the parent. The physical offset of each generated ZIP32 file is measured independently from its byte array. The fixture digest matches the one recorded by setup.

Run `python3 examples/tools/build.py 446` with the prepared `merged-pr-links-m01-m10` cache. The same compiled caller runs in a fresh JVM for each revision and history. [Predictions and refutations](comparison.json) · [Runtime lock](runtime.json) · [Caller](caller/PublicCaller.java) · [Recorded returns](observations.json) · [Upstream change](https://github.com/apache/commons-compress/pull/334) · [Build provenance](../../llm-dlc/loops/organic-java-merged-pr-links-m01-m10-brief-setup.md)
