# Round-trip MongoDB CSV records with an empty leading field

The MongoDB CSV preset reparsed the printer’s empty leading column. A later field retained its embedded comma and literal double quote through the public iterator.

The printer must protect delimiters and quotes within a field. The caller’s original strings give an oracle independent of the lexer.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `throws java.io.UncheckedIOException` | `[[a, b], [, x]]` | matched |
| Control | `[[a, b], [c, d]]` | `[[a, b], [c, d]]` | matched |
| Challenge | `throws java.io.UncheckedIOException` | `[[, x], [, comma,"quote]]` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 557`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/commons-csv/pull/412)
