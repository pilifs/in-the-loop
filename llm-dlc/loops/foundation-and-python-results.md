# Java verification restart evidence

The implementation checkout began at f9693c47, the starter brief on top of main at 11413e85. That line includes the previous foundation merge and the subsequent qualification of example 197's receipts. The following inventory was read before changing the proof route.

## Example 105

Run `python3 examples/tools/targets/workflow_handoff.py handoff 105` to navigate from the source claim to its revisions, receipts, verifier records and pipeline steps. The original receipts and their preparation identities are preserved. [Example 105](../../examples/105-commons-numbers-223-pow-of-minus-two-to-the-31)

| Source claim | Task | Prepared claim | Execution | Recorded conclusion |
|---|---|---|---|---|
| 8a4071f6a417d239 | fix-property | 5955760df7c21aec | 20261114T222911Z-a26d0f04 | Established |
| 8a4071f6a417d239 | fix-property-before | bb2955ce1c93a5d7 | 20261114T222911Z-f3a33202 | Refuted |
| 8a4071f6a417d239 | fix-property-before | bb2955ce1c93a5d7 | 20261115T001438Z-b304cfd0 | Refuted |
| 8a4071f6a417d239 | fix-property-before | d1bb93e6fe366579 | 20261115T051521Z-a8b91f86 | Refuted |
| 1d76c0d0c405f392 | regression | 1e8128d965200158 | 20261114T235516Z-061637d0 | Refuted |
| 6bef0dff1140dc6d | confined-change | 13483ab20b3f6b60 | 20261115T011544Z-71dbed5b | Unresolved |

The current handoff accepts the fixed property. Its JVM-replay requirement leaves the before-property and unrestricted comparison open. The historical before-property verifier records carry interpreter evidence, and the separate controls cover the witness. The confined-change attempt stopped at the StringBuilder constructor. The example README’s 1,083-second JBMC run is a historical measurement of that obligation. [Recorded refusal](../../examples/105-commons-numbers-223-pow-of-minus-two-to-the-31/records/refusals/confined-change.json)

## Two array roots

The merged example 197 already binds the three native receipts to the full 71-input heap domain. A fresh run of the starter oracle on Temurin 21.0.13+9 counted zero return differences, three right-root differences, and 21 combined-root differences. The two integrated JBMC experiments distinguish the mutation and replay it. The preserving runs were refused because JBMC stubs the two generated catch handlers. The smaller distinct-root profile has its own digest. [Native receipts](../../examples/197-shared-int-array-poststates/receipts) · [JBMC profile results](../../verification/results/20261119-164549-197-integrated-jbmc-preserving-and-discr/outputs/verification/foundation-jbmc-array-overlap.json)
