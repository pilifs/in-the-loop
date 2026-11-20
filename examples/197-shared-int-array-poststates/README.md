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

JBMC also checked both final roots on the full 71-heap domain. It proved the equivalent early-exit implementation with a non-vacuous result in 2.256 seconds. It refuted the skipped write in 2.071 seconds, and the JVM replay observed the differing left root. Both runs used the same domain, source class digests, array bound of two and unwind of eight as the earlier attempts. The generated observer retains writes before a throw, including when JBMC lacks the exception's superclass. The four-heap control has its own statement. [Full-domain statements and replay](../../verification/wide-array-checks.json) · [Earlier handler refusal](../../verification/results/20261119-164549-197-integrated-jbmc-preserving-and-discr/outputs/verification/foundation-jbmc-array-overlap.json) · [Four-heap control](../../verification/restart-jbmc-grid.json)

Selecting only the right root forced JBMC to produce two references to the same `[0]`. The JVM replay saw `[1]` on the reference and `[0]` on the alternative. On the nine heaps with two distinct non-null roots, each independently `[]`, `[0]` or `[1]`, JBMC proved right-root preservation for both revision pairs. Selecting both roots on those nine heaps exposed the skipped left write on two equal, separately allocated `[0]` arrays. The preserving implementation passed all three comparisons. [Full-domain right-root witness](../../verification/shared-right-array-projection.json) · [Distinct right-root proofs](../../verification/distinct-right-array-projection.json) · [Distinct two-root proof and witness](../../verification/distinct-both-array-projection.json)

The fast-follow regression repeated the original native tasks at array bound two and unwind eight with the same classpaths and JDK. All 71 direct heaps per revision reproduced the original disagreements. Return preservation was established, and the right-root and both-root violations replayed on the JVM. [Regression job](../../verification/results/20261120-042933-recheck-both-array-roots-after-the-fast/result.json)

The numerical checker repeated all three original native verdicts. The reference and skipped-write JVM grids had the same digests as the preceding 71-heap run. [Array-root regression](../../verification/results/20261120-053727-confirm-both-array-roots-after-the-numer/result.json)

The language and list changes retained the three original array-root results at unwind eight and array bound two. All 71 direct heaps on each revision have the prior JVM stream digests. Both distinct poststate witnesses reproduced. [Verification job](../../verification/results/20261120-065325-confirm-shared-array-poststates-after-ch/result.json)

After the JDK map, reader and stream changes, all three original 197 outcomes were rechecked at array bound 2 and unwind 8. Both wrong poststates reproduced independently and all 71 direct JVM rows on each side retained their original hashes. [Final three-claim job](../../verification/results/20261120-083146-recheck-the-two-array-roots-after-sequen/result.json)
