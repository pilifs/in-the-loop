# Countermodels of a loop invariant

Past `--unwind` iterations the tool's own checker finds an invariant of a loop's further iterations and goes on
from it (`lib/src/bmc/loops.rs`): it runs an iteration from the state the path is in, sets what the iteration
wrote to any value, keeps the candidates (bounds, low bits, not negative, an index into an array) that an iteration
from any state they allow does not break, and the path goes on from the head in that state. A false invariant is a
false proof of everything after the loop. This folder is the challenge stream's attempt to make it keep something
a later iteration breaks (domain-advances, item 4, 2026-11-17). `lo.L.main` runs each loop on the least input whose
late iteration does what the first ones do not, and `lib/tests/loop_countermodels.rs` holds the fixture to what a
JVM says and the checker to its verdicts.

## Tried and found guarded

Each at `--unwind 2`, the false property below: none was proved. Past the bound the checker's witness does not
reproduce, which is no verdict with the loop named, and at `--unwind 7` `late` is refuted.

| entry point (JVM) | what changes late | false property | guarded by |
|---|---|---|---|
| `late(6)` (1) | a local written only once another reaches 5 | `result == 0` | the iteration is run again from the state with what it wrote set to any value, until it writes nothing new (`covered`, `grew`): once `phase` is any value the branch that writes `flag` is taken, and the candidates `phase <= 2` and the like are dropped by Houdini's rounds before they are relied on |
| `callee(7)` (1) | two statics a callee writes, the second once the first reaches 6 | `result == 0` | what is written is read off the states, not off the code (`differences`): a static written in a callee is a static of the state back at the head |
| `aliased(5)` (9) | an array read through one local and written through another | `result == 0` | an array is a place by its allocation (`Place::Cells`, `by_allocation`), whichever name reaches it |
| `twoCells(4)` (102) | a cell written once its difference with another reaches 3 | `result < 100` | candidates are of one number each; two cells written are each any value the candidates allow, with no relation kept between them |
| `boxed(6)` (7) | a field of an object reached through a local and an array's cell | `result == 0` | a field is a place by its object's allocation (`Place::Field`) |
| `nested(5, 5)` (1) | a local written in the fifth round of an inner and an outer loop | `result == 0` | the inner loop is covered inside the outer one's iteration, its writes are any value back at the outer head |
| `large(4)` (4) | 100 cells written at a computed index | `result <= 3` | past a summarized loop the cells of a table of more than 64 are any values (`Obj::unknown`), and every reader of an array's cells in bulk takes such an array for none (`Obj::as_array`) |

Read and not built, with why: a reference an iteration changes, a builder's content, a class newly initialized and
a value left on the operand stack each leave the loop unwound (`differences`); an object the iteration makes is
reached only through a reference it changes; a local dead at the head is forgotten before the iteration
(`Frame::forget_dead`, whose liveness counts an exception handler as a way from its range); the frames below the
loop's are not written by Java code; the candidates kept are shown of every input that reaches the head (`shown`),
and a loop not shown to end is stated as assumed (`ends`). JDK state the engine models outside the path's statics
and objects: none is written by a modelled call (`Logger` levels are constants; `Locale.setDefault` is a gap).

What the same reading found elsewhere: a lemma read the cells of an array that was there before the call through
`clone()`, `Arrays.copyOf` and `MessageDigest.isEqual` without being asked (`lemma-countermodels`, three false
proofs, now refused).

## Audit (2026-11-17)

The results that rest on a loop invariant are 287's (`fixed-guard` and `fixed-security`, bcrypt's key
schedule and rounds). No attempt here gave a false proof, so none is affected by them.
