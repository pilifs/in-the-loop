# Apache Commons CLI preserves option defaults across parses

| History | Public observation |
|---|---|
| Intent | The parent returned first twice and stored it on the definition. The merge returned first then second, left the registered values null after both calls, and preserved first on the retained result. |
| Control | The preloaded preset was the sole stored value and the returned value on both revisions. |
| Challenge | Both failed parses named the missing flag r. On retry, the parent returned discarded and the merge returned retry. A fresh invocation returned retry on both. All four successful retries contained r and had an empty argument list. |

The successful sequence retains its first CommandLine and reads the definition after each call. The failed sequence switches to a fresh parser and compares its retry with separate fresh definitions.

Run `python3 examples/tools/build.py 453` with the prepared `merged-pr-links-n01-n05` cache. Each revision and history starts a fresh JVM with the same compiled caller. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observations](observations.json) · [Upstream PR](https://github.com/apache/commons-cli/pull/450) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-n01-n05-brief-setup.md)
