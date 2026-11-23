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

## Measured results

Ordinary native 7/7. The JVM checked 5,329 boundary pairs. Sign normalization failed on 4,756, and Guava min kept the first reference on all 73 equal-valued distinct ties.

| Original entry | Opening native | Final native | Integrated JBMC | Ordinary task receipt |
|---|---|---|---|---|
| ExactOrder#commons | open | proved | entry refused | [established](receipts/exact-order-commons/20261123T175745Z-7551c733/result.json) |
| ExactOrder#onlySign | open | refuted | entry refused | [refuted](receipts/exact-order-only-sign/20261123T175747Z-8673e13a/result.json) |
| ExactOrder#guava | open | proved | entry refused | [established](receipts/exact-order-guava/20261123T175749Z-8b187587/result.json) |
| ExactOrder#firstOnTie | open | proved | entry refused | [established](receipts/exact-order-first-on-tie/20261123T175751Z-91f9b6ce/result.json) |
| ExactOrder#secondOnTie | open | refuted | entry refused | [refuted](receipts/exact-order-second-on-tie/20261123T175753Z-8e325330/result.json) |
| ExactOrder#direct | open | proved | entry refused | [established](receipts/exact-order-direct/20261123T175755Z-92f00fee/result.json) |
| ExactOrder#sameReference | open | proved | entry refused | [established](receipts/exact-order-same-reference/20261123T175757Z-81562309/result.json) |

[Paired measurements](../../verification/jbmc-fast-follow/successor/strings/paired/measurement.json) · [Campaign results](../../llm-dlc/loops/jbmc-fast-follow-calls-conversions-and-arrays-results.md)
