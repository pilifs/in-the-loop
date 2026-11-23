# Caller-owned rows in public array operations

Bounded nullable arrays preserve independent row widths, primitive values and shared identities across Commons Lang, Collections and Math.

| Entry | Statement | Expected |
|---|---|---|
| `RaggedProof#reversed` | Reversal swaps row references and retains the observable alias on mutation. | established |
| `RaggedProof#wrong` | Reversal never changes the first slot. | refuted |
| `RaggedProof#iter` | The iterator reads the replaced second slot and reset returns it to the first row. | established |
| `RaggedProof#snapshot` | The iterator always retains the original second slot. | refuted |
| `RaggedProof#distinct` | Nonempty rows are always distinct. | refuted |
| `RowIdentities#nonNullOuter` | The outer array is always non-null. | refuted |
| `RowIdentities#noEmptyOuter` | The outer array is never empty. | refuted |
| `RowIdentities#noDistinctEqualRows` | Two distinct one-cell rows cannot both contain Integer.MIN_VALUE. | refuted |
| `MadeRows#reverse` | Constructed rows preserve reversal and alias visibility. | established |
| `MadeRows#iterator` | The live iterator observes replacement on explicitly constructed rows. | established |
| `MadeRows#alwaysDistinct` | The constructed nonempty rows always have distinct identities. | refuted |
| `MatrixRows#rectangular` | Two non-null rows of equal width return normally. | established |
| `MatrixRows#singleShape` | A one-row matrix containing null returns normally. | established |
| `MatrixRows#shape` | Mismatch agrees with row lengths and exposes the expected width. | established |
| `MatrixRows#same` | All matrices with two non-null rows return normally. | refuted |
| `MatrixRows#noNull` | A single null row throws NullPointerException. | refuted |

Inspect the ordinary tasks with `python3 examples/tools/build.py --plan 394`. The comparison uses the same product classes for both engines and replays each qualified refutation on the original JVM. [Campaign brief](../../llm-dlc/loops/jbmc-fast-follow-calls-conversions-and-arrays.md)

## Measured results

Ordinary native 16/16. Both dimensions and every cell are independent at the direct entry. An alias names an earlier row, while equal separate rows have their own cell lists. The 209-graph JVM census contains 12 shared nonempty cases. The direct Commons Math transfer retains actual and expected mismatch dimensions.

| Original entry | Opening native | Final native | Integrated JBMC | Ordinary task receipt |
|---|---|---|---|---|
| RaggedProof#reversed | entry refused | proved | open | [established](receipts/ragged-proof-reversed/20261123T175707Z-1b7412ef/result.json) |
| RaggedProof#wrong | entry refused | refuted | refuted | [refuted](receipts/ragged-proof-wrong/20261123T175709Z-d9e1b917/result.json) |
| RaggedProof#iter | entry refused | proved | open | [established](receipts/ragged-proof-iter/20261123T175712Z-c6e65ff5/result.json) |
| RaggedProof#snapshot | entry refused | refuted | refuted | [refuted](receipts/ragged-proof-snapshot/20261123T175715Z-782bde6e/result.json) |
| RaggedProof#distinct | entry refused | refuted | refuted | [refuted](receipts/ragged-proof-distinct/20261123T175718Z-4ba33cc0/result.json) |
| RowIdentities#nonNullOuter | entry refused | refuted | refuted | [refuted](receipts/row-identities-non-null-outer/20261123T175721Z-1a85d62d/result.json) |
| RowIdentities#noEmptyOuter | entry refused | refuted | refuted | [refuted](receipts/row-identities-no-empty-outer/20261123T175723Z-d3df30ad/result.json) |
| RowIdentities#noDistinctEqualRows | entry refused | refuted | refuted | [refuted](receipts/row-identities-no-distinct-equal-rows/20261123T175726Z-49f781c2/result.json) |
| MadeRows#reverse | proved | proved | open | [established](receipts/made-rows-reverse/20261123T175728Z-6b282d04/result.json) |
| MadeRows#iterator | proved | proved | open | [established](receipts/made-rows-iterator/20261123T175730Z-74723008/result.json) |
| MadeRows#alwaysDistinct | refuted | refuted | refuted | [refuted](receipts/made-rows-always-distinct/20261123T175732Z-82e316a9/result.json) |
| MatrixRows#rectangular | entry refused | proved | open | [established](receipts/matrix-rows-rectangular/20261123T175734Z-92106f55/result.json) |
| MatrixRows#singleShape | entry refused | proved | open | [established](receipts/matrix-rows-single-shape/20261123T175736Z-98476e3d/result.json) |
| MatrixRows#shape | entry refused | proved | open | [established](receipts/matrix-rows-shape/20261123T175738Z-7d392230/result.json) |
| MatrixRows#same | entry refused | refuted | refuted | [refuted](receipts/matrix-rows-same/20261123T175740Z-9a40c62b/result.json) |
| MatrixRows#noNull | entry refused | refuted | refuted | [refuted](receipts/matrix-rows-no-null/20261123T175742Z-ea990a08/result.json) |

[Paired measurements](../../verification/jbmc-fast-follow/successor/rows/paired/measurement.json) · [Campaign results](../../llm-dlc/loops/jbmc-fast-follow-calls-conversions-and-arrays-results.md)
