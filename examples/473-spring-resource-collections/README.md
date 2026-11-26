# A single classpath resource injected into a collection

An XML context populated both a resource list and a resource set from a single file on the merge.

| History | Observation |
|---|---|
| Intent | The literal singleton failed parent context refresh. On the merge each getter returned the four bytes of ONE followed by LF. |
| Control | Both revisions read exactly the two fixtures from each collection for the two-file pattern, with enumeration order ignored. |
| Challenge | With only one file, both spellings failed in the parent fixture and both returned the same four bytes from each merged collection. |

Each variant gets a fresh class loader and XML context with its own fixture directory. The caller opens every Resource and reads the stream.

With the prepared Spring cache, run `python3 examples/tools/build.py 473` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #31699](https://github.com/spring-projects/spring-framework/pull/31699)
