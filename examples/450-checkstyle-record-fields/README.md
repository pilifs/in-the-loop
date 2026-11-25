# Checkstyle locates hidden fields across an implicit static record

| History | Observed result |
|---|---|
| Intent | The CLI’s one diagnostic on the record parameter quota disappeared on the merge. |
| Control | Both CLIs identified the ordinary member class parameter quota at line 4, column 18. |
| Challenge | Implicit and explicitly static records each reported exactly the nested Reader parameter limit at line 6, column 32. |

The observer launches Checkstyle’s CommandLine Main in a child JVM, checks the actual CLI and HiddenFieldCheck code sources, and reads identifiers from XML line and column positions. The return includes the child exit status.

Run `python3 examples/tools/build.py 450` with the prepared `merged-pr-links-m01-m10` cache. The same compiled caller runs in a fresh JVM for each revision and history. [Predictions and refutations](comparison.json) · [Runtime lock](runtime.json) · [Caller](caller/PublicCaller.java) · [Recorded returns](observations.json) · [Upstream change](https://github.com/checkstyle/checkstyle/pull/14128) · [Build provenance](../../llm-dlc/loops/organic-java-merged-pr-links-m01-m10-brief-setup.md)
