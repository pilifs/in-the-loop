# Javaslang transpose preserves coordinates and rejects ragged matrices

The public transpose rejects nonrectangular inputs and maps each coordinate of rectangular matrices, including the identity fast paths. All heights 0 to 3 and row widths 0 to 2 over the alphabet 0 and 1, ordered first by height and then by row word.

Run `python3 examples/tools/build.py 371 --task replay` on the bound artifacts. [Frozen observations](controls/table.json) · [Setup evidence](../../llm-dlc/loops/spring-and-java-data-setup.md)

## Recorded results

The ordinary native checker established 3 and refuted 1 of the 4 primary obligations. The finite JVM established 3 and refuted 1.

The parent matched the rectangular-or-reject contract on 102 of 400 matrices. Every one of the 298 differences was ragged. The fix matched all 400, including the singleton empty-row identity and the two-row, zero-column shape loss. [Opening job](../../verification/results/2026/11/22/20261122-162530-vavr-matrix-coordinates-and-ragged-rejec/result.json) · [Selector checks](../../verification/results/2026/11/22/20261122-165838-qualified-check-rectangular-and-ragged-i/result.json) · [Scorecard](../../verification/spring-java-data/data.json)

All four named matrices can be replayed directly on either captured JAR. Run `java --class-path PATH/TO/vavr-1829-parent.jar examples/371-javaslang-matrix-transpose/controls/NamedMatrices.java parent` from the repository root. The landed JAR uses the argument `landed`. [Paired observations](records/setup/named-matrices.json)
