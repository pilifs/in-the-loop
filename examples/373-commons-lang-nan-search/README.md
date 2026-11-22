# Find the first NaN in a bounded double array

Two different quiet NaN encodings select the first NaN at or after the clamped start. Both zero signs have the same search index. Each bounded array word is paired with every start from -1 to length+1. The final selector is the five-element infinity and NaN regression.

Run `python3 examples/tools/build.py 373 --task replay` on the bound artifacts. [Frozen observations](controls/table.json) · [Setup evidence](../../llm-dlc/loops/spring-and-java-data-setup.md)

## Recorded results

On the primary zero-tolerance grid, the ordinary native checker established three of four obligations. The parent NaN claim remains open natively. The finite JVM established three claims and refuted the parent claim.

The parent returned −1 for the named NaN search and the fix returned index 1. The fixed first-match and both revisions’ signed-zero and finite controls were established on the opening native verifier. The grid uses exact quiet-NaN bit patterns and tolerance zero. [Opening job](../../verification/results/2026/11/22/20261122-162530-first-nan-and-preserved-numbers-at-zero/result.json) · [Selector checks](../../verification/results/2026/11/22/20261122-164436-check-nan-searches-with-the-historical-a/result.json) · [Scorecard](../../verification/spring-java-data/data.json)

## Positive tolerance

Strict native proofs on both historical JARs established the first matching index and preservation of both cells’ raw bits. Each cell comes from an independent 64-bit word, and the starting index ranges over every Java `int`. The caller preserves finite values, signed zeros, infinities and quiet NaN payloads. It quiets signaling NaNs before the public call. The three centers and fixed tolerance bound the library’s floating-point additions and subtractions. [Paired proof job](../../verification/results/2026/11/22/20261122-182432-prove-inclusive-positive-tolerance-on-bo/result.json)

At tolerance 0.25, a search for 0.5 in `[0.25, 0.75]` returned index 0 from start 0 and index 1 from start 1. Replacing the first cell with the double immediately below 0.25 moved the first match to index 1. Moving the second cell just above 0.75 then gave −1. Both historical JARs matched the exact-rational oracle on all 18,900 cases across the three search centers −0.5, 0 and 0.5.

From the repository root, run `python3 lib/benchmark/spring-java-data/positive_tolerance.py --physical-only --output "$TMPDIR/tolerance-replay"` to reproduce both JVM grids. Each compressed observation contains the original public index, both post-call bit patterns, and the verifier adapter’s return. [Symbolic caller](companions/ToleranceSearch.java) · [Independent oracle and replay reader](../../lib/benchmark/spring-java-data/positive_tolerance.py)
