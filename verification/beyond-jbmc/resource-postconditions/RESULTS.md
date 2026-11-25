# Paired resource postconditions

Strict native decided all 30 registered statements on five original deployment pairs. It proved 17 and refuted 13. Each refutation carries the actual before and after return, both original typed calls, the admitted input, and a reproduced JVM witness. The two direct calls run in separate original JVMs. The replay evaluates the scalar predicate on those operands, including the input assumption and the intended-change guard. A guard or postcondition outside the scalar evaluator leaves the witness open. [Preregistered Java observations and relations](registrations) · [All measurements and raw executions](measured)

| Original deployment | All-input equality | Selected-key equality | Missing-key equality | Equality outside the selected key | Increment on selected key | Inequality at missing key |
|---|---|---|---|---|---|---|
| Ordinary packaged resource | Refuted | Refuted | Proved | Proved | Proved | Refuted |
| Compensating return | Proved | Proved | Proved | Proved | Refuted | Refuted |
| Thread context loader | Refuted | Refuted | Proved | Proved | Proved | Refuted |
| Released Annotation Indexer | Refuted | Refuted | Proved | Proved | Proved | Refuted |
| Released dom4j missing service | Proved | Proved | Proved | Proved | Refuted | Refuted |

The indexer returned 112 and 113 at the selected key. Both originals returned −1 at the missing key, which refutes the requested inequality even though the returns are equal. The compensating case shows the opposite danger of treating a changed provider as a changed result. All five registrations were reconstructed from their original classpaths and checked against an independent Java predicate before measuring. [Indexer witnesses](measured/index/summary.json) · [Compensating witnesses](measured/compensating/summary.json)

The same executable, `0ff2ba882133`, then repeated all 187 historical IDs on the pinned JDK 25. It preserved all 94 proofs, 85 reproduced refutations and eight open dispositions. All 25 original JVM references agreed. All three jobs passed. [Historical measurements](historical-native/results.json.gz) · [Source-bound job receipts](receipts.json)

`python3 -B lib/benchmark/beyond-jbmc/blind/continuation_audit.py resources` checks the output hashes, source-bound registrations, original witnesses and exact historical population. [Audit](../../../lib/benchmark/beyond-jbmc/blind/continuation_audit.py)
