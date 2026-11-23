# Exact decimal parsing preserves coefficient and scale

Three adjacent or signed decimals return BigDecimal with the coefficient and scale specified by their text. Float, Integer and malformed controls keep their types. Three explicit exact-decimal strings, each paired with an unchanged short literal and the malformed token 1eE.

Run `python3 examples/tools/build.py 375 --task replay` on the bound artifacts. [Frozen observations](controls/table.json) · [Setup evidence](../../llm-dlc/loops/spring-and-java-data-setup.md)

## Ordinary native follow-up

The Java semantics follow-up decided all four ordinary native claims on both original Commons Lang builds. The parent returned Float for all three precision inputs. The fix returned the exact BigDecimal coefficients at scale 18. Both revisions preserved the two short Floats, the Integer, and the malformed-input exception.

The strict checker took the unchanged public entry with `0 ≤ code < 3`, unwind 256, maximum array length 16,384 and a 120-second deadline. A separate run covered every admitted constant call required for each proof and replayed the parent witness on a fresh JVM.

| Claim | Whole guard | Selector checks |
|---|---|---|
| precise-parent | [refuted](receipts/precise-parent/20261123T140907Z-86ae0d4c/result.json) | [1 checked](records/native-selectors/parent/20261123T140915Z-3cda9f67/tasks/precise-parent/result.json) |
| precise-landed | [established](receipts/precise-landed/20261123T140909Z-c11a7db6/result.json) | [3 checked](records/native-selectors/landed/20261123T140918Z-e98cebd2/tasks/precise-landed/result.json) |
| preserved-parent | [established](receipts/preserved-parent/20261123T140911Z-96d728c9/result.json) | [3 checked](records/native-selectors/parent/20261123T140915Z-3cda9f67/tasks/preserved-parent/result.json) |
| preserved-landed | [established](receipts/preserved-landed/20261123T140913Z-5b128c46/result.json) | [3 checked](records/native-selectors/landed/20261123T140918Z-e98cebd2/tasks/preserved-landed/result.json) |

[Exact runtime classes, raw values and integrated JBMC](../../verification/java-semantics-gap/decimal-transfer/paired/measurement.json) · [Campaign results](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md#commons-lang-decimal-parser)

## Earlier Spring/data results

The ordinary native checker established 0 and refuted 0 of the 4 primary obligations. The finite JVM established 3 and refuted 1. All four ordinary native obligations were open at that measurement.

The three long decimal literals distinguished the historical artifacts. The landed revision returned the exact signed BigDecimal coefficient and scale 18. Both revisions preserved the Float raw bits, the Integer and the malformed-token exception. The landed NumberUtils JAR and class matched example 369. [Opening job](../../verification/results/2026/11/22/20261122-162530-decimal-result-class-coefficient-scale-a/result.json) · [Selector checks](../../verification/results/2026/11/22/20261122-165839-qualified-check-exact-decimal-runtime-ty/result.json) · [Scorecard](../../verification/spring-java-data/data.json)
