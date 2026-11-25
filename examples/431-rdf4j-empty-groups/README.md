# RDF4J distinguishes an empty group relation from one unbound row

The parent returned one unbound row for an explicitly grouped empty graph. The fix returned zero. An implicit aggregate still returned one unbound row. Adding the first matching triple made the subquery join produce both markers once.

All RDF4J modules on each classpath came from that side’s setup build. Its independently recorded module hashes are in setup/artifacts.sha256.

| Question | Input |
|---|---|
| Intent | Empty graph, explicit GROUP BY ?x. |
| Control | Empty graph, SELECT (MAX(?v) AS ?m) with the same WHERE and no GROUP BY. |
| Challenge | Place the explicit grouped query as a subquery in `SELECT ?marker WHERE { VALUES ?marker { "a" "b" } { SELECT ?x (MAX(?v) AS ?m) WHERE { ?x <urn:p> ?v } GROUP BY ?x } }`. Add a triple with a different predicate and query, then add `<urn:s> <urn:p> 7` and query again. |

Run `python3 examples/tools/build.py 431` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pins. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/eclipse-rdf4j/rdf4j/pull/1989) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)
