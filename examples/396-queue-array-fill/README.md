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
