# java-diff-utils renders explicit and implicit equal rows

Explicit equal lines changed from CHANGE to EQUAL. The customized prefix and suffix were each decorated once in both representations.


| Question | Input |
|---|---|
| Intent | Render the two-line fixture with explicit equal parts and inline markup disabled. |
| Control | Generate the patch with equal parts omitted, leaving the visible documents and renderer fixed. |
| Challenge | Put an unchanged tail after the changed pair. Set the public builder’s equality processor to prefix each unchanged line with `EQ-`. Render both explicit and implicit equal parts on the merge. |

Run `python3 examples/tools/build.py 426` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pins. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/java-diff-utils/java-diff-utils/pull/233) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)
