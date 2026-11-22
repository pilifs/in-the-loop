# Boxed parsing into fresh ragged rows

The compiled client maps real Commons Lang `NumberUtils::toInt` over each row, then invokes the two typed array factories. The 187 selectors cover every zero-, one- and two-token word in six specified layouts plus the empty matrix. The eight-row regression separately checks 28 pairs, mutation isolation and an identity-memoizing control. [Client](application/datawork/RowMapper.java) · [Independent observations](controls/table.json)

Run `python3 examples/tools/build.py 369 --task replay` for both the grid and the named regression. The `values-landed` and `fresh-landed` tasks check values and allocation.

## Recorded results

The ordinary native checker established 2 and refuted 0 of the 2 primary obligations. The finite JVM established 2 and refuted 0.

The exhaustive JVM companion visited 33,729 matrices over all inputs and all realizable row aliases within height three, width two and the five-token alphabet. The four bootstrap sites include a primitive int result that the SAM exposes as Integer. [Opening job](../../verification/results/2026/11/22/20261122-161543-boxed-parser-values-and-independent-resu/result.json) · [Selector checks](../../verification/results/2026/11/22/20261122-165838-qualified-prove-boxed-row-values-and-mut/result.json) · [Scorecard](../../verification/spring-java-data/data.json)
