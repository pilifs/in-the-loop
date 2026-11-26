# Joined data buffers reach the destination byte for byte

The merged synchronous writer traversed every component, including when the destination accepted one byte at a time.

| History | Observation |
|---|---|
| Intent | The two-component write completed and emitted one buffer on both revisions. The file contained only foo on the parent and foobar on the merge. |
| Control | A contiguous buffer produced foobar on disk on both revisions. |
| Challenge | With pieces f, oob and ar, the one-byte synchronous writer left f on the parent and foobar on the merge. The asynchronous file write left XXfoobar on both. |

The caller counts the readable components before writing, releases the emitted buffer, closes the channel and independently reads the destination file.

With the prepared Spring cache, run `python3 examples/tools/build.py 467` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #36714](https://github.com/spring-projects/spring-framework/pull/36714)
