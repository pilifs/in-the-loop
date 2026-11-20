# Apache Commons Text longest common subsequence

On OpenJDK 21.0.13, the public `LongestCommonSubsequence.apply(CharSequence, CharSequence)` agreed with exhaustive
subsequence enumeration on all 225 ordered pairs of strings of length 0–3 over `{a,b}`. The released class and its
source rebuild both reached `algorithmB`. Its bytecode allocates the two score rows with `multianewarray [[I, 2` at
offset 18. The source JAR and the pinned upstream file have the same Git blob. [Release source](https://github.com/apache/commons-text/blob/a70c34e028ab279bb89565606e1ab09011a41bc2/src/main/java/org/apache/commons/text/similarity/LongestCommonSubsequence.java)

| Artifact | Disagreements | Score for `("ab", "aa")` |
|---|---:|---:|
| Published 1.13.1 JAR | 0 / 225 | 1 |
| Original source rebuilt on JDK 21 | 0 / 225 | 1 |
| Same build with the second row sharing the first | 44 / 225 | 2 |

The native baseline stopped at the multidimensional allocation after 0.446 seconds, at 84.3 MiB peak RSS.
That baseline left the score claim open. The bound is four cells per array, unwind 18, with the same two input selectors
and Java oracle used for the JVM run. [Measured run](records/690f0383-3b2c-42fd-9dc3-bcf95393f5db/result.json)

`python3 -I pilot.py --java-home "$JDK21_HOME" --artifacts "$ARTIFACT_DIR"` from this folder checks both pinned
JAR digests, compiles the adapter and the two source variants, disassembles each loaded target, and repeats the
225 comparisons on every artifact. The artifact directory holds the release and sources JARs named in the lock.
`--work DIR` retains the classes in an empty directory. `--native CHECKER` also runs the bounded score claim.
[Artifact lock](sources.lock.json)

The ordinary replay tasks run the public method on the released and altered artifacts. Their Python oracle checks
the score for each word pair and rejects duplicated or missing pairs. The immutable receipts and source claim
are available with `python3 examples/tools/targets/workflow_handoff.py handoff 308` from the repository root.

The original release score claim subsequently passed its strict native check at the original four-cell bound, unwind 18 and 120-second deadline. Bounded multidimensional allocation advanced the first attempt to Integer.valueOf. The next run executed the boxed result and verified the score in 0.726 seconds at 77.8 MiB maximum process RSS. The independent JVM reran all 225 pairs on the release, source rebuild and row-sharing control. [Matrix attempt](records/matrix-transfer.json) · [Boxing transfer](records/boxing-transfer.json)

A second strict release run took 0.997 seconds and 78.7 MiB. The complete checker statement records the guard, asserted score, complete unwind and non-vacuity witness. [Full checker output](records/release-score-native.json) · [Release and independent comparisons](records/release-score-transfer.json)
