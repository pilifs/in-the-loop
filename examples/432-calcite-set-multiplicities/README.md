# Calcite preserves bag multiplicity across projected set operations

The same planner hook as the upstream SQL fixture enabled the transpose rule on JDBC. EXCEPT and INTERSECT now compare the full rows. Changing only the right bag changed the fixed counts from 2/1 to 0/3.

The JDBC caller also ran with a public planner listener on both pins. Field trimming removed the outer projection over UNION ALL before optimization. Other optimizer rules fired, the transpose rule received zero attempts, and both tens survived. For EXCEPT ALL and INTERSECT ALL, both pins attempted the rule. Only the parent produced its projection rewrite.

| Question | Input |
|---|---|
| Intent | Singleton inputs above, EXCEPT ALL and INTERSECT ALL. |
| Control | Change only the operator to UNION ALL. |
| Challenge | Keep every y at 10. Use left input VALUES (1,10),(1,10),(2,10) and right input VALUES (1,10),(3,10),(3,10). Then replace the right input by a copy of the left. |

Run `python3 examples/tools/build.py 432` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pins. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/apache/calcite/pull/5378) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)

Run `python3 examples/432-calcite-set-multiplicities/controls/planner.py` to repeat 12 fresh instrumented JVMs. The listener records the converted and trimmed relational trees, attempts of the transpose rule, successful transformations and all JDBC rows. The original caller class and loaded Calcite providers are checked on every deployment. [Planner evidence](controls/planner.json) · [Public listener](controls/PlannerHistory.java) · [Upstream field trimming](https://github.com/apache/calcite/blob/5f48eec8d5e3f25df641393c9440e086646868b7/core/src/main/java/org/apache/calcite/sql2rel/RelFieldTrimmer.java)
