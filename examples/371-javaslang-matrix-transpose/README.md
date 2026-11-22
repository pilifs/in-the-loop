# Javaslang transpose preserves coordinates and rejects ragged matrices

The public transpose rejects nonrectangular inputs and maps each coordinate of rectangular matrices, including the identity fast paths. All heights 0 to 3 and row widths 0 to 2 over the alphabet 0 and 1, ordered first by height and then by row word.

Run `python3 examples/tools/build.py 371 --task replay` on the bound artifacts. [Frozen observations](controls/table.json) · [Setup evidence](../../llm-dlc/loops/spring-and-java-data-setup.md)

## Recorded results

The ordinary native checker established 3 and refuted 1 of the 4 primary obligations. The finite JVM established 3 and refuted 1.

The parent matched the rectangular-or-reject contract on 102 of 400 matrices. Every one of the 298 differences was ragged. The fix matched all 400, including the singleton empty-row identity and the two-row, zero-column shape loss. [Opening job](../../verification/results/2026/11/22/20261122-162530-vavr-matrix-coordinates-and-ragged-rejec/result.json) · [Selector checks](../../verification/results/2026/11/22/20261122-165838-qualified-check-rectangular-and-ragged-i/result.json) · [Scorecard](../../verification/spring-java-data/data.json)

All four named matrices can be replayed directly on either captured JAR. Run `java --class-path PATH/TO/vavr-1829-parent.jar examples/371-javaslang-matrix-transpose/controls/NamedMatrices.java parent` from the repository root. The landed JAR uses the argument `landed`. [Paired observations](records/setup/named-matrices.json)

## Cell identity through two transposes

Run `python3 -B lib/benchmark/spring-java-data/matrix_references.py --case 012345` from the repository root to replay both historical JARs. The six digits give row-major cells in both a 2 × 3 and a 3 × 2 rectangle. Zero is null. Digits 1 through 7 name distinct objects that all compare equal by value. The output shows the reference at each coordinate after each call.

The same command shows what two incorrect implementations return. Copying each non-null cell preserves value equality and introduces fresh references, printed as −1. Reshaping in row-major order swaps the dimensions and recovers the input on a second call. The first transpose distinguishes it on `012345`. [Caller](companions/MatrixReferences.java) · [JVM controls](companions/MatrixReplay.java)

Both original JARs passed two strict native proofs from ordinary startup. The rectangle proof checked the dimensions and compared the iterated cells by reference with the selected inputs after each transpose and in the original matrix. The six independent choices and two orientations give **524,288 labeled rectangles**. The boundary proof checked outer-list identity for the empty matrix, a single empty row and a single cell. Two or three empty rows collapsed to an empty outer list and stayed empty on the second call. [Parent proofs and observations](records/references/parent/measurement.json) · [Landed proofs and observations](records/references/landed/measurement.json)

Each JVM ran **1,754 rectangles**, one for each of the 877 null and alias patterns in each orientation, plus 40 boundary cases. Numbering non-null objects by first occurrence removes equivalent renamings. The two JVMs emitted byte-identical records. Value-equal copies changed a reference on 1,752 rectangles. The row-major reshape misplaced a reference on 1,724 even though its second application restored every input. [Managed verification](../../verification/results/2026/11/22/20261122-221543-prove-reference-identity-through-both-hi/result.json)
