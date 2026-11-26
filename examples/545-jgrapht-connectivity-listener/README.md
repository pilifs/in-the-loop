# Edits to a listened-to graph keep connectivity queries current

A graph listener accepted edits before the first full connectivity query. Reused and fresh inspectors agreed after adding an edge to a partially queried directed or undirected graph.

The inspector defines weak connectivity for directed graphs. Query order and edge orientation cannot partition this underlying connected graph.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `throws java.lang.NullPointerException` | `[a, b]` | matched |
| Control | `[[a, b, c]]/true` | `[[a, b, c]]/true` | matched |
| Challenge | `throws java.lang.NullPointerException` | `[a, b]->[a, b, c]/[a, b, c] / [a, b]->[a, b, c]/[a, b, c]` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 545`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/jgrapht/jgrapht/pull/1379)
