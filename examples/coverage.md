# Which engine decides each recorded JBMC example

An inventory of the 41 recorded examples JBMC proves (B9 and B11 on the javac apps Quorum, Crosscut and Mica, 43
obligations): for each obligation, which engine decides it under `--gaps strict` and what stops the other. It ranks
the semantic extensions of the tool's own checker that would decide most of what only JBMC decides now
([`engine-priorities.md`](../llm-dlc/loops/engine-priorities.md), Phase 4c).

## Measured: job `20261107-000039`, at `98bab485`

Both engines ran every example under strict, at a commit before the own checker ran class initializers (Phase 5).
The two per-obligation tables are that job's outputs, `lib/target/jobs/4a-coverage/jbmc-gaps.json` and
`native-gaps.json` (in its `changes.diff` under `verification/results/`). Regenerate the table below with:

```bash
python3 examples/tools/gap_table.py --inventory jbmc-gaps.json native-gaps.json
```

The command lists every obligation. Here, the 35 that both engines decide are folded into one line.

- **Both, with the same status (35):** 015, 016, 017, 018, 022, 023, 024, 027, 031, 032, 033, 034, 036, 044, 045, 046,
  047, 048, 049, 050, 051, 053, 054, 055, 056, 120, 121, 122, 123, 126, 128, 129, 130, 131, 134. No obligation is
  decided differently by the two engines.
- **JBMC only (5), neither (3), the own checker only (0):**

| Obligation | JBMC | Own checker | Decided by | What stops the other |
|---|---|---|---|---|
| 013#0 | refuted | unresolved | JBMC only | own checker: gap class-initializer:before.net.terminalvalue.quorum.raft.TermOrder.<clinit> |
| 035#0 | refuted | unresolved | JBMC only | own checker: outside the fragment: a float parameter |
| 037#0 | unresolved | unresolved | neither | JBMC: JBMC proved it, but runs 1 construct otherwise than the JVM (unmasked-shift at net.terminalvalue.mica.rt.SymbolTable.tableSizeFor:18), so the proof is refused under every --gaps mode; own checker: gap jdk-static-method:java.lang.Integer.numberOfLeadingZeros |
| 052#0 | established | unresolved | JBMC only | own checker: a loop was not fully unwound with --unwind 16 (PropertyHarness.check at pc 238) |
| 071#0 | unresolved | unresolved | neither | JBMC: gap jdk-constructor:java.lang.Enum.<init>, jdk-static-method:java.util.List.copyOf, jdk-static-method:java.util.List.of; own checker: gap class-initializer:net.terminalvalue.quorum.raft.TermOrder.<clinit> |
| 071#1 | unresolved | unresolved | neither | as 071#0 |
| 071#2 | refuted | unresolved | JBMC only | own checker: gap class-initializer:net.terminalvalue.quorum.raft.TermOrder.<clinit> |
| 127#0 | established | unresolved | JBMC only | own checker: gap jdk-static-method:java.lang.Long.numberOfLeadingZeros |

The own checker stops at the first gap it is refused at, so a row names only that one. A proof of 037 by JBMC is
correct (checked on all 2^32 ints, in 037's notes), but JBMC's shift is not the JVM's, so no mode lets it stand.

## Since then: static scans, nothing proved

The own checker's gap scan (`build.py --scan-gaps`, 7 November 2026, JDK 25.0.5, recorded in each example's notes)
at the commit that adds this page:

- **013, 071:** the class-initializer gaps are gone. Phase 5 runs JVMS §5.5 initializers and enums, and 4b counted
  only enums and their switch maps among the apps' 49 initializers. What remains is `List.copyOf` and `List.of`
  (`jdk-static-method`). Their models in `lib/models` are on JBMC's class path only, and the own checker doesn't run
  them.
- **037, 127:** unchanged, `Integer.numberOfLeadingZeros` and `Long.numberOfLeadingZeros`.
- **035, 052:** no gap. 035 is refused for its floating-point arithmetic, and 052 for the unwinding bound.

On JBMC's side, 071#0 and #1 wait on job `20261107-012013`, which reruns them with the preflight's path-aware stub
check. 037 stays refused: the defect is in stock JBMC.

None of this is a verdict yet. A strict rerun of the eight obligations on both engines would measure it.

## The next extensions, ranked

By how many obligations each would move, then by cost:

1. **`Integer.numberOfLeadingZeros` and `Long.numberOfLeadingZeros`, exact in the own checker** (with
   `models_jdk_static`). Effect:
   - **037#0** goes from neither to the own checker. Stock JBMC can't decide it.
   - **127#0** goes from JBMC only to both.

   Cost: small. The count is a priority encoder over the argument's bits, and a conformance case checks it against
   the JVM.
2. **The own checker's unwinding bound, counted per entry of a loop.** Effect: **052#0** goes from JBMC only to both.
   - Cause: `Engine::jump` in `lib/src/bmc/mod.rs` counts back edges per path and per `(class, method, target)`, and
     never resets the count when the loop is left.
   - The property's `\max` over `k` of a `\sum` over `i < k` is two nested loops in the harness
     (`harness/expr.rs` compiles each quantifier as a loop). Over an array of length 8, one path takes the inner back
     edge up to 36 times.
   - JBMC proved the property with unwinding assertions at 16.
   - The cause still needs a reproducer. The current count is incomplete, not unsound: a path cut short is no verdict.
3. **The own checker running the `List` models** (`List.of`, `List.copyOf`, `ImmutableCollections`). Effect:
   - **013#0** and **071#2** go from JBMC only to both.
   - **071#0** and **#1** go to the own checker, and to both if job `-012013` stands.

   Cost: medium. The models are JBMC-only today, and running them needs interface dispatch over the models' list
   classes. Arrays of references already run.
4. **Floating point in the own checker.** Effect: **035#0**, the one known case.

   Cost: large. IEEE 754 arithmetic and comparison in the bit-blaster. JBMC decides it today.

Items 1 to 3 would leave **035#0** as the only obligation of the 43 that the own checker doesn't decide.
