# Two nullable array roots and three poststate claims

The reference writes `left[0] = 1` when both arrays are non-null and nonempty. The alternative skips the write.
Both return zero. There are 71 input heaps up to renaming objects. Each array has at most two cells in
`{0,1}`. The JVM enumeration includes seven shared pairs and 49 distinct non-null pairs, including distinct
arrays with equal contents.

| Frozen claim | JVM disagreements | Public native check |
|---|---:|---|
| Return value | 0 / 71 | Bounded agreement |
| Right root's final contents | 3 / 71 | Refuted on a shared array |
| Both roots' final contents | 21 / 71 | Refuted on a write visible through the left root |

For two references to one `[0]`, the right-root observation is `[1]` on the reference and `[0]` on the alternative.
With separate `[0]` arrays, both right roots finish at `[0]`. The JVM replay records the actual selected values on
each side, the typed descriptors, and the input identity. The checker takes an independent set of scalar inputs for
the two lengths, the cells, nullability and sharing, then builds a fresh heap for each call.

The `replay` task enumerates the heaps on each artifact. The three proof tasks are `return-only`, `right-root`
and `both-roots`. From the repository root, `python3 examples/tools/build.py --plan 197` prints their plans and
`python3 examples/tools/targets/workflow_handoff.py handoff 197` shows their receipts by claim and revision.
The generated observer is also checked on every heap. Cloning a shared argument, omitting the comparison and
observing the other root each fail that check. [Native integration tests](../../lib/tests/paired_array_roots.rs)
