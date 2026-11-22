# Exact decimal parsing preserves coefficient and scale

Three adjacent or signed decimals return BigDecimal with the coefficient and scale specified by their text. Float, Integer and malformed controls keep their types. Three explicit exact-decimal strings, each paired with an unchanged short literal and the malformed token 1eE.

Run `python3 examples/tools/build.py 375 --task replay` on the bound artifacts. [Frozen observations](controls/table.json) · [Setup evidence](../../llm-dlc/loops/spring-and-java-data-setup.md)

## Recorded results

The ordinary native checker established 0 and refuted 0 of the 4 primary obligations. The finite JVM established 3 and refuted 1. 4 ordinary native obligations remain open.

The three long decimal literals distinguished the historical artifacts. The landed revision returned the exact signed BigDecimal coefficient and scale 18. Both revisions preserved the Float raw bits, the Integer and the malformed-token exception. The landed NumberUtils JAR and class matched example 369. [Opening job](../../verification/results/2026/11/22/20261122-162530-decimal-result-class-coefficient-scale-a/result.json) · [Selector checks](../../verification/results/2026/11/22/20261122-165839-qualified-check-exact-decimal-runtime-ty/result.json) · [Scorecard](../../verification/spring-java-data/data.json)
