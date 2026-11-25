# Commons Collections keeps occurrence counts across view removals

Both distinct views lost the selected key on the parent while retaining its old size. The fixed views agree with the surviving occurrences after removal, reinsertion and removal through the other view.


| Question | Input |
|---|---|
| Intent | Independently remove the first key through each view on a fresh fixture. |
| Control | Use the ordinary occurrence iterator on the fresh multiset, call next and remove once. |
| Challenge | On the merge remove all three A through one view (advance until A), re-add A once, then remove B through a fresh iterator of the other view. Swap the view roles and repeat. |

Run `python3 examples/tools/build.py 424` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pins. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/apache/commons-collections/pull/701) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)
