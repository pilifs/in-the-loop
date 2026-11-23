# Successive Spring edits preserve bean identity and binding errors

One Spring Framework 6.2.3 DataBinder receives three edits on a fresh bean. The primary and backup references begin shared or distinct. Each of the six edit orders records both children's names and counts, reference identity, and the field error after each call. The error carries the rejected text `oops` even after a successful write. A fresh binder over the same bean starts with an empty ledger. [Application](application/springwork/BindingHistory.java) · [Independent observations](controls/table.json)

Run `python3 examples/tools/build.py 368 --task replay` for the 12 histories and their controls. The `beans-release` and `ledger-release` tasks check the two properties independently.

## Recorded results

The ordinary native checker established 0 and refuted 0 of the 2 primary obligations. The finite JVM established 2 and refuted 0. 2 ordinary native obligations remain open.

Both release claims now enter the introspection cache and execute the factory map's inherited lookup. The first strict refusal is `Object.hashCode()` in `ConcurrentReferenceHashMap.getHash` at line 223. The combined Framework 6.1.7 control still stops at `CachedIntrospectionResults.<clinit>`. [Managed startup run](../../verification/results/2026/11/23/20261123-011836-recheck-all-ordinary-spring-claims-after/result.json)

The binder retained the rejected backup.count value after a successful primary.count write. Every prefix matched the independent model on Framework 6.2.3 and on the Security 6.3.0 / Framework 6.1.7 dependency graph. [Opening job](../../verification/results/2026/11/22/20261122-161543-spring-binder-edits-and-the-persistent-f/result.json) · [Selector checks](../../verification/results/2026/11/22/20261122-164436-recheck-spring-binder-prefixes-from-ordi/result.json) · [Scorecard](../../verification/spring-java-data/spring.json)

Across the six orders, the combined-graph JVM receipts contain all 15 distinct nonempty edit prefixes for each bean layout. A caller can therefore look up the state after any sequence of admitted edits from this family, including a lone valid count edit after two declines. The role-gated caller measures the empty sequence on a separate fresh binder. [Gated edits in example 370](../370-spring-role-hierarchy/README.md#gating-every-edit)
