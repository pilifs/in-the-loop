# Dictionary pages belong to a sequence of column names

The Parquet reader kept the literal field a.b distinct from b nested under a. Reading the changed nested dictionary twice around the unchanged top-level dictionary preserved both identities.

The pin's compiled DictionaryPageReader precedes the same Parquet 1.18.2/Hadoop dependencies on both sides. The complete pinned module needs Thrift 0.23.0.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `[nested-one, nested-two]/[nested-one, nested-two]` | `[one, two]/[nested-one, nested-two]` | matched |
| Control | `[one, two]/[nested-one, nested-two]` | `[one, two]/[nested-one, nested-two]` | matched |
| Challenge | `[new-one, new-two]/[new-one, new-two]/[new-one, new-two]` | `[new-one, new-two]/[one, two]/[new-one, new-two]` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 576`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/parquet-java/pull/3830)
