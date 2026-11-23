# Independent Java proof experiment

**Fund one more semantic claim family, starting with the single-root write frame of JDK `Arrays.fill` in example 337.** The Rust checker established the complete public `Ints.indexOf` and `Longs.indexOf` contracts on Guava 33.4.8-jre. For every legal array length and signed cell and target, each call terminates, returns the first match or exactly −1, and preserves the heap. The assumptions include verified classes and successful initialization. Six rebound behavioral mutants failed with checked witnesses. A different wrapper layout and a same-value store both passed. The controls recorded zero false acceptances. [Frozen protocol](protocol.md) · [Assurance argument and trusted components](assurance.md) · [Case table and bundle digests](evidence/cases.json)

## What the independent check caught

| Rebound control | Historical Python/Z3 rule | Independent evidence |
|---|---|---|
| Last match / start at one | Unsupported bytecode shapes | Returned 1 on `[7,7]` / returned −1 on `[7]` |
| Miss returns zero | Unresolved postcondition | Empty array returned 0 |
| Correct result, damaged heap | Frame expected UNSAT and obtained SAT | `[7]`, target 7, returned 0 with heap `[0]` |
| No loop progress | Unresolved decrease | Identical state repeated at helper PC 3 on `[7]`, target 8 |
| Truncated long comparison | Unsupported operation | `[0,4294967296]`, target 4294967296, returned 0 instead of 1 |
| Extra wrapper local / same-value store | Unsupported / established | Both proved on their rebound bytes |

An experimental issuer given a false frame premise supplied all the expected obligation keys and the mutant's correct digest. The consumer caught the store at PC 25 and replayed its effect. Omitting one exit's frame or substituting the other exit's frame also failed. The consumer was denied reads of the existing producer, verdict and cache. The historical producer was exercised in its original form. The behavior of a deliberately faulted historical producer remains unmeasured. [Issuer, controls and access checks](evidence/transfer/results.json)

Lean 4.36.0 independently checked the scalar class from its complete 256 bytes. The `(I)I` bodies for multiply, add and shifted add are `05 1a 68 ac`, `1a 1a 60 ac` and `1a 1a 60 04 60 ac`. For every 32-bit input, multiply and add return `x+x` with the same heap. The shifted version differs at zero. Both theorems use `propext`, `Classical.choice` and `Quot.sound`. A Lean Guava proof would also require the larger constant pool, branching, private calls and loop induction. [Kernel source](Scalar.lean) · [Axiom output and checkpoint](evidence/scalar/measurements.json)

## Cost of reuse

The original 336 and 346 comparisons matched every historical obligation on JDK 21 and Z3 5.3.3. The additional SAT domain check for 346 admitted distinct longs with equal low halves. The setup agent supplied the pinned tools and releases. The implementation agent made the proof corrections and used the published JAR, both existing wrapper/helper solutions, and their archived obligations. The release `Ints.class` digest ends in `4edbb`. [Baseline receipts](evidence/baseline) · [Artifact and tool setup](../../../llm-dlc/loops/in-the-loop-trusted-kernel-experiment-brief-setup.md)

| Stage | Observed effort |
|---|---|
| Fixed setup | Frozen external requests, a 209-line Rust class reader, a modular scalar evaluator, and a 125-line Lean decoder and proof. A missing Lean list combinator and read access to the runtime's random device required two adjustments. |
| First loop family after the scalar checkpoint | 425 new Rust acceptance lines for decoding, dispatch and induction, plus 180 for checked refutations. |
| Known 336 → 346 transfer | The sealed int binary first refused the long descriptor. Two acceptance files gained 66 lines and lost 17. Concrete witness handling gained 54 and lost 10. The issuer, certificate format, prefix invariant, overflow argument, frame and termination rules carried over. The additional `lcmp` instruction moved the count from 34 to 35 obligations. |
| Held-back equivalent wrapper | A rebound request and fresh certificate, with zero rule changes. The width and layout transfers give best-case costs for compatible claims. |

The implementation session recorded 213 model calls, 272,832 uncached input tokens, 121,567 output tokens and 47,149,696 cached input tokens through 20:11 UTC. The repository's list-price subtotal was $33.92. Prior setup was $2.75. The routes shared setup and ran concurrently. This subtotal excludes subsequent reporting and watcher work. [Effort and accounting scope](evidence/effort.json)

## Operating cost

Three fresh processes per measurement on AMD RYZEN AI MAX+ 395 w/ Radeon 8060S. A small native parent isolates the child's peak resident memory from Python's pre-exec memory. Rust compilation took 859 ms and 174.2 MiB. Lean checking includes elaboration of its 4,448-byte module. The historical comparison reruns its producer. The first baseline and scalar jobs encountered CPU throttling. The table uses the later two-CPU measurement job. [Individual samples and build costs](evidence/costs.json)

| Route and case | Certificate bytes | Generate, time / peak RSS | Check, time / peak RSS |
|---|---:|---:|---:|
| Rust · scalar | 173 | 220 ms / 55.7 MiB | 1.26 ms / 1.8 MiB |
| Lean · scalar | 173 | 220 ms / 55.7 MiB | 1.27 s / 1.59 GiB |
| Rust · Ints | 1,064 | 291 ms / 63.2 MiB | 1.35 ms / 1.8 MiB |
| Rust · Longs | 1,111 | 284 ms / 61.3 MiB | 1.11 ms / 1.8 MiB |
| SAT/LRAT · Guava query 23 | 15,934 | 2.26 ms / 5.4 MiB | 2.56 ms / 13.0 MiB |
| SAT/LRAT · prefix-sums query 18 | 15,921 | 2.23 ms / 5.8 MiB | 3.14 ms / 15.0 MiB |
| Historical Python/Z3 · Ints | 4,094 | 1.18 s / 103.4 MiB | 1.19 s / 104.6 MiB |
| Historical Python/Z3 · Longs | 4,705 | 1.14 s / 101.5 MiB | 1.19 s / 104.6 MiB |

With the external request and original class bytes included, the portable proof inputs total 11,053 bytes for Ints and 10,897 for Longs. The compiled consumer is shared.

CaDiCaL 1.9.5 and cake_lpr `033aad53` certified **8/8 Guava and 10/10 prefix-sums UNSAT calls**. The normal Guava launcher filtered the transcript setting. Instrumenting that setting preserved the proof's native statistics and exposed a separate reachability probe. The first coverage report subtracted both streams from the main proof's counter. The raw logs give 24 main calls and two probe calls, with 0 constant-false shortcuts. [Corrected per-pass accounting](evidence/bounded-sat/accounting.json)

Guava's eight proofs took 20.5 ms to generate and 27.2 ms for one check of each, excluding the native verifier run. They occupy 27,157 bytes packed. Query 23 used 48,803 bytes of DIMACS, 25 assumption units and a 15,934-byte proof. The truncated proof and satisfiable formula both lost the checker's UNSAT signal. Production integration would still need coverage accounting and durable formula/proof binding for every relevant solve. [Guava proof inventory](evidence/bounded-sat/guava/queries.json) · [Prefix-sums inventory](evidence/bounded-sat/prefix-sums/queries.json)

## Next family

The frozen independent checker refused all three range-fill requests. The historical route established the original fill and caller. Its extra-write caller remained unresolved at the caller-read obligation. A separately bound JVM run supplied a counterexample. With both roots equal to `[11]`, empty range `[0,0)`, value 7 and `k=0`, the extra caller returned 7 and changed the heap to `[7]`. The original returned 11. The JVM covered 50 fills and 75 cases per caller. The extra caller produced 4 wrong observations and 31 frame differences. [Range-fill evidence](evidence/range-fill.json)

A fill proof needs range checking, an invariant for the written prefix and preservation outside the range. The caller adds alias identity and independently sized roots. Budget this as another induction family. It takes priority over widening read-only opcode coverage or porting Guava induction to Lean. A production rollout requires a separate decision.

## Replay

From the repository root on the pinned Linux toolchain:

```bash
K=lib/benchmark/trusted-kernel
python3 -B "$K/consumer.py" rust "$K/requests/Ints.request" "$K/evidence/transfer/Ints/evidence.cert" "$K/inputs/Ints.bin" "$K/inputs/IntsMethodsForWeb.bin"
python3 -B "$K/consumer.py" rust "$K/requests/Longs.request" "$K/evidence/transfer/Longs/evidence.cert" "$K/inputs/Longs.bin"
python3 -B "$K/consumer.py" lean "$K/requests/add.request" "$K/evidence/scalar/add.cert" "$K/inputs/Scalar.bin"
python3 -B "$K/bounded_sat.py" --check
python3 -B "$K/decision_evidence.py" --check
```

Use `shifted.request` and `shifted.cert` together for the Lean negative. The Rust CLI accepts user-supplied inputs. Exit 0 means accepted, 2 rejected, and 3 unsupported. The clean-replay job rebuilt the frozen and final consumers and replayed their saved cases. [Clean replay receipt](evidence/clean-replay.json)
