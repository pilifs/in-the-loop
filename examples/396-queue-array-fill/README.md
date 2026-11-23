# Circular queue histories and reference-array fill

Commons Collections queue histories and Commons Lang ArrayFill observe replacement, identity and covariant array stores.

| Entry | Frozen statement | Expected |
|---|---|---|
| `QueueFill#queue` | The four operations preserve queue size, capacity, head, poll and indexed identities on every history. | established |
| `QueueFill#fullMeansOccupied` | isFull agrees with occupying both slots throughout the four operations. | refuted |
| `QueueFill#fill` | ArrayFill returns the original array, replaces both stale slots and retains the shared mutable object. | established |
| `QueueFill#staleSurvives` | The old reference always survives in the second slot after a fill. | refuted |
| `QueueFill#covariant` | Filling a typed empty array succeeds; a nonempty incompatible store throws and preserves its first cell. | established |

Inspect the original tasks with `python3 examples/tools/build.py --plan 396`. [Fast-follow brief](../../llm-dlc/loops/jbmc-fast-follow-calls-conversions-and-arrays.md)

## Measured results

Ordinary native 5/5. The independent two-slot oracle checked all 256 histories. Full occupancy disagreed with isFull on 128. Reference fill preserves the array and replacement identity and checks covariance on the first store.

| Original entry | Opening native | Final native | Integrated JBMC | Ordinary task receipt |
|---|---|---|---|---|
| QueueFill#queue | open | proved | open | [established](receipts/queue-fill-queue/20261123T175759Z-e2bd4a3f/result.json) |
| QueueFill#fullMeansOccupied | refuted | refuted | refuted | [refuted](receipts/queue-fill-full-means-occupied/20261123T175801Z-d94569f4/result.json) |
| QueueFill#fill | open | proved | unreproduced witness | [established](receipts/queue-fill-fill/20261123T175803Z-a0d22aca/result.json) |
| QueueFill#staleSurvives | open | refuted | open | [refuted](receipts/queue-fill-stale-survives/20261123T175805Z-54c3ed67/result.json) |
| QueueFill#covariant | open | proved | unreproduced witness | [established](receipts/queue-fill-covariant/20261123T175806Z-e2464b5d/result.json) |

[Paired measurements](../../verification/jbmc-fast-follow/successor/queue/paired/measurement.json) · [Campaign results](../../llm-dlc/loops/jbmc-fast-follow-calls-conversions-and-arrays-results.md)
