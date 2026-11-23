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
