# Exact UTF-16 comparison and tie identity

Commons Lang and Guava compare two bounded strings over unrestricted UTF-16 units. Guava min exposes which equal reference it retained.

| Entry | Frozen statement | Expected |
|---|---|---|
| `ExactOrder#commons` | Commons Lang returns the first unequal code-unit difference, or the length difference at a shared prefix. | established |
| `ExactOrder#onlySign` | Commons Lang always normalizes the comparison to its sign. | refuted |
| `ExactOrder#guava` | Guava natural ordering returns the exact independent UTF-16 difference. | established |
| `ExactOrder#firstOnTie` | Guava min returns the first reference on a tie and the lesser reference otherwise. | established |
| `ExactOrder#secondOnTie` | Guava min selects the second reference when two distinct strings tie. | refuted |
| `ExactOrder#direct` | String.compareTo agrees with the independent UTF-16 unit oracle. | established |
| `ExactOrder#sameReference` | The identical-reference diagonal preserves comparison and min identity. | established |

Inspect the original tasks with `python3 examples/tools/build.py --plan 395`. [Fast-follow brief](../../llm-dlc/loops/jbmc-fast-follow-calls-conversions-and-arrays.md)
