# Find the first NaN in a bounded double array

Two different quiet NaN encodings select the first NaN at or after the clamped start. Both zero signs have the same search index. Each bounded array word is paired with every start from -1 to length+1. The final selector is the five-element infinity and NaN regression.

Run `python3 examples/tools/build.py 373 --task replay` on the bound artifacts. [Frozen observations](controls/table.json) · [Setup evidence](../../llm-dlc/loops/spring-and-java-data-setup.md)

## Recorded results

The ordinary native checker established 3 and refuted 0 of the 4 primary obligations. The finite JVM established 3 and refuted 1. 1 ordinary native obligations remain open.

The parent returned −1 for the named NaN search and the fix returned index 1. The fixed first-match and both revisions’ signed-zero and finite controls were established on the opening native verifier. The grid uses exact quiet-NaN bit patterns and tolerance zero. [Opening job](../../verification/results/2026/11/22/20261122-162530-first-nan-and-preserved-numbers-at-zero/result.json) · [Selector checks](../../verification/results/2026/11/22/20261122-164436-check-nan-searches-with-the-historical-a/result.json) · [Scorecard](../../verification/spring-java-data/data.json)
