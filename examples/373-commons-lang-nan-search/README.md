# Find the first NaN in a bounded double array

Two different quiet NaN encodings select the first NaN at or after the clamped start. Both zero signs have the same search index. Each bounded array word is paired with every start from -1 to length+1. The final selector is the five-element infinity and NaN regression.

Run `python3 examples/tools/build.py 373 --task replay` on the bound artifacts. [Frozen observations](controls/table.json) · [Setup evidence](../../llm-dlc/loops/spring-and-java-data-setup.md)
