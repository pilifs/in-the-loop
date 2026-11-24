# Beyond JBMC on Java change verification

The campaign starts at `837c9fb9a25f7931493a774d0c2c744f63260081`. Its populations are the archived 187 claims, the disclosed casebook, the historical 32 automatic upgrade questions, and the sealed 16. A row retains its original question when an engine supports only a narrower domain. [Execution brief](../../../llm-dlc/loops/beyond-jbmc-java-change-verification-campaign.md)

## Historical comparison

The ordered manifest binds each archived ID to its assertion or equivalence condition, input graph, expected outcome and archived classification. The default graph for a property with no named classes is `conformance`. The source graphs include both inputs of each recorded patch and the independent JVM oracles. The November 7 archive has 133 decisions in common, 24 native only, 13 integrated JBMC only and 17 neither. [Manifest](historical/manifest.json) · [Original report](../results.json)

Run `python3 lib/benchmark/beyond-jbmc/history.py check` to verify all 187 claims and the 57 original program and oracle files. The historical source patch removes the 22 lines added to the conformance fixture since that run. Compilation requires the original Java source digest. Changes to later test expectation annotations do not affect the archived statements. The independent copy of the archive is at `~/.cache/in-the-loop/beyond-jbmc/historical/results-867fa025.json`.

Queue `history.py opening` or `history.py closing` for a fresh measurement. Both use the exact-ID entry point, strict mode, staged integrated JBMC, the historical unwind of 16, array bound of 8, 120-second setting and 200,000-input JVM search. The result directory contains the benchmark JSON, compiled class digests, per-run argv, stdout, stderr and generated harnesses. Timing includes the solver process and its children. The proof cache is disabled. The operating-system page cache is unmeasured.

## Comparator and adjudication policy

Use the Ubuntu 24.04 JBMC 6.11.0 binary with its own packaged Java models for the primary stock column. Use its packaged string refinement, runtime exceptions and unwinding assertions, unless a case explicitly prespecifies a different exception property. For a matched comparison, give both engines the same input construction, entry guard, observations and distinct version bindings. Record any different object-factory assumptions alongside the stock result. A second named stock profile may use the exact class bytes bound by the subject's JDK for a documented model discrepancy. Bind those bytes and the scope before measuring that profile. Compare with the union of qualified comparator decisions.

Retain the literal assertion ID, status, post-call false control, unwind failures and the invocation of each standalone run. An unreachable or missing target, a failed unwinding assertion, or a difference in the input universe prevents matched proof credit. A counterexample earns credit when the original JVM reproduces the named observation on that input. A decision contradicted by the JVM, bytecode or an independent specification stays visible as a wrong decision. Keep unresolved disagreements, timeouts and unsupported rows in the denominator. [Campaign criteria](../../../llm-dlc/loops/beyond-jbmc-java-change-verification-campaign.md#3-decide-whether-the-advances-transfer)
