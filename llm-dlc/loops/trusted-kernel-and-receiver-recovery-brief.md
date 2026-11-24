# Independently check the proof, then recover the public caller

**Aspirational execution brief for `pilifs/in-the-loop` · Baseline [`develop` at `867fa025`][head]**

**Mission.** Settle whether a mistake in the historical Java proof producer can still cause a false theorem to be accepted. Carry the independent checker to a second implementation of a range fill, and certify the SAT evidence behind one whole ordinary native verdict. In parallel, resume the interrupted receiver campaign at the real JVM properties table and recover a previously blocked public library caller. Each investigation can ship and be evaluated independently.

**First launch.** Start the trusted-kernel work at VF-057 and the receiver work at VF-058. On a single execution slot, run VF-057 first, save its receipt, and attempt the Configuration caller before the stretch work. The examples below pin the questions and observations. Agents choose the implementation, solver and experiments that get them to an answer.

## Restart from the promoted evidence

| Work already on develop | Opening position for this run |
|---|---|
| Independent Rust checker | From original release bytes, it established total first-match search with an unchanged heap on Guava `Ints.indexOf` and `Longs.indexOf`, the exact write frame of the JDK int range fill (37 obligations), and the aliased caller in #337 (51). It independently refuted the extra-write caller. The 111-row table counts controls and multiple checking routes. [Results][kernel] · [Cases][cases] |
| Historical producer and Lean | The experimental issuer's bad frame was caught. The historical Python/Z3 producer has only been exercised unchanged. Lean 4.36.0 established the scalar claim from the complete 256-byte class; there is no like-for-like Lean result on Guava. [VF-057][vf57] · [Assurance argument][assurance] |
| Bounded SAT evidence | All 8 observed Guava UNSAT calls and all 10 prefix-sums UNSAT calls already have checked LRAT proofs. The ordinary verdict does not yet require complete, correctly associated evidence. [Accounting][accounting] · [Current proof checks][lrat] |
| Receiver and JBMC campaigns | Receiver cycle 2 ended with no new commit. Guava already has 8/8, Commons Lang 6/6, CSV 4/4, and JGraphT its 25-graph/150-transition JVM audit. The separate JBMC fast-follow finished at 49/49 strict native; #375’s four decimal claims are decided. JavaParser is still 2/8 at ordinary scope. The user deferred the three ordinary thread claims under VF-056. [VF-058][vf58] · [Receiver results][receivers] · [JBMC fast-follow][jbmc-results] |

Start a new run from the promoted commit or its actual successor in a clean worktree, using the committed receipts as the handoff. An interrupted cycle with no new decision remains open. The proposed queue helper and aspirational prompt file in the draft were absent at this pin; the existing single-run workflow can consume this brief. Verify that the pinned class bytes, JDK, Z3, Rust toolchain, CaDiCaL, `cake_lpr` and optional Lean cache still match the [setup record][setup]. Restore only missing inputs. Check these inventories first, then rebuild and replay the specific rows used in each comparison. The inventory checks validate saved evidence; record fresh execution separately.

```sh
K=lib/benchmark/trusted-kernel
python3 -B "$K/decision_evidence.py" --check
python3 -B "$K/range_qualification.py" --check
python3 -B "$K/frame_witness.py" --check
python3 -B "$K/bounded_sat.py" --check
python3 -B lib/benchmark/receiver-discovery/results.py --check
```

## 1. Close the unresolved investment test · VF-057

Use a disposable checkout of the **historical producer**, its actual adapter and the two existing intentionally incorrect benchmark classes. Pin the external theorem, assumptions, class bytes, expected behavior and independent checker before editing the producer. For each trial, regenerate the verification conditions, solver answers, hashes and producer receipt normally.

| Historical trial | Unchanged outcome | Single test change and independent observation |
|---|---|---|
| Correct index, damaged heap | The heap-writing variant returns 0 on `[7]` with target 7 and changes the cell to 0. Historical query 10, “preserve the input heap,” expected UNSAT and obtained SAT | Replace the failing frame obligation with a tautology in the test copy. The independent checker must still account for the actual store at helper PC 25. On `[0]`, target 0, the same store preserves the old value; include that control |
| Wrong miss, absent exit check | The miss variant returns 0 on an empty array. The theorem requires −1. Query 4, “return the earliest match or minus one,” is the unexpected SAT result | Omit that exit obligation in a separate run. Require the independent checker to identify the missing requirement or replay the wrong return. Compare against the honest class returning −1 |

Run the unmodified positive through the same path. For each trial preserve **five answers**: what the producer reports, what Z3 says about the regenerated formula, what the ordinary record/compare path does with and without an independently retained pristine receipt, what the fresh Rust consumer says, and what the original JVM does. Reproducing a faulty producer’s internally consistent receipt is a different capability from detecting a changed receipt against a known good copy. [Historical producer][producer] · [Ordinary adapter][adapter] · [Frozen frame and JVM evidence][frame] · [Exit control][transfer]

Historical output is SMT and the Rust consumer takes a compact certificate. Save both digests and document any untrusted translation into hints. Give Rust the **same external request and original artifact**; let it derive its own required edges, exits and frame. A syntax error or a mismatched digest demonstrates an integrity check. To earn the semantic result, present well-formed, freshly rebound evidence and identify the bytecode rule or checked witness that defeats the false claim.

**Decision.** Record the first effective detector on each route, including any existing historical protection that works. If an erroneous producer establishes a false theorem on its own regenerated evidence and the independent route refuses or refutes that same theorem for a semantic reason, identify the exact producer decision removed from trust. If the historical route catches both, report what the second opinion adds on these cases and reassess the rollout. A false acceptance on the independent route blocks promotion of that family. If neither historical experiment distinguishes the independent checker, keep the recommendation provisional. Close VF-057 with the observed result and its implication for investment.

## 2. Measure what transfers without rebuilding the checker around the example

**First, JDK `Arrays.fill(long[], int, int, long)`.** Use Temurin 21.0.13+9 and the descriptor `([JIIJ)V`. For every non-null array, arbitrary 64-bit cells and fill value, and all valid signed indices `0 ≤ from ≤ to ≤ length`, prove normal termination, the value throughout `[from,to)`, and the entry heap everywhere else. Include empty and whole intervals. The cursor is still an int; the long value occupies slots 3–4, the cursor moves to 5, and the store is `lastore` at PC 20. Freeze the int-capable binary and record its first response before changing code. [Pinned disassembly][disasm] · [Range rule][range]

Planning preflight on the unchanged Rust source and matching 59,937-byte `Arrays.class` gave **exit 3, unsupported range-fill descriptors**. The original int and caller controls still accepted 37 and 51 obligations. A physical JVM passed all 245 small valid-range controls. Narrowing the value to 32 bits changed 80 observations; extending the interval by one cell where possible changed 140. A one-cell write of `4294967296L` distinguishes 64-bit value handling immediately. Repeat the checks under the managed runner’s process isolation. Retain changes to the trusted rule, issuer and witness handling as separate effort figures.

**Calibrate the cost of reuse.** Rebind the original least-index requests to Guava 31.1-jre and to Apache Beam’s relocated Guava (`org.apache.beam:beam-vendor-guava-32_1_2-jre:0.1`). In planning, the frozen Rust checker accepted all four original int/long entrypoints with **zero rule changes**, 34 and 35 obligations respectively. All four old certificates were rejected until bound to the new request. The JVM checked 780 int and 1,554 long calls per JAR. Use these positive cases to test dependency identity in the second-opinion path. They establish portability across releases and packaging of the same upstream code. Fastutil below tests transfer to a different implementation. [Older Guava release][guava31] · [Beam release][beam]

**Next, fastutil’s released `IntArrays.fill(int[], int, int, int)`.** Freeze the post-JDK checker before specializing it for `it.unimi.dsi:fastutil:8.5.15`. Use exactly the same valid-range theorem on the release bytes. When `from == 0`, fastutil writes backward; otherwise it writes forward. The valid-range check also crosses a class boundary. Verify the actual helper resolution, both loop exits and both frames. A descending counter reaches −1 on the final unsuccessful post-decrement test; a forward-loop invariant copied verbatim will miss this. [Release source][fastutil]

The frozen checker at the planning commit already refused the fastutil range descriptors before examining the loop. The physical JVM passed **7,745** checks over lengths 0–4, all arrays over `{-1,0,1}`, every valid range and five fill values. Of these, 2,735 used the zero-origin branch and 5,010 the other branch. Use `[0,2)` with a distinctive last value to expose an omitted descending-loop write, and the empty interior interval `[1,1)` to expose a stray write. Preserve the pre-edit refusal, any changes, and the first outcome on each branch. This is a disclosed cross-library transfer; its evidentiary value comes from freezing the checker before the attempt.

**Then try one unfamiliar semantic case.** Choose according to what the first two trials reveal.

| Case | Question and acceptance |
|---|---|
| **Guava `Shorts.indexOf` and `Chars.indexOf`**, 33.4.8-jre | Can the existing first-match/termination/frame theorem survive the difference between sign-extending `saload` and zero-extending `caload`? Keep both bytecode descriptors and the full 16-bit domains. A preflight JVM grid used six boundary bit patterns, including `0x8000` and `0xffff`. On each type 33 of 216 calls distinguished a wrong extension applied only to the loaded cell. Qualify one width interpretation, freeze it and run the other. [Release bytes][guava] |
| **Commons Lang `ArrayUtils.reverse(int[], int, int)`**, 3.17.0 | This requires two cursors and a relation to the entry heap. Prove that each cell of a valid range receives its original mirror and all other cells remain unchanged. Check reference aliases and empty/singleton ranges. Then test the stronger claim that *every* pair of signed bounds is safely clipped. On the original JVM, `reverse(new int[0], 0, Integer.MIN_VALUE)` throws `ArrayIndexOutOfBoundsException`: subtracting one at PC 18 wraps and PC 30 reads before any store. With start `Integer.MAX_VALUE` the loop skips; null returns normally. A 44,165-call grid had 40,525 normal outcomes and 3,640 exact exceptions with the original array preserved. A JVM witness refutes total clipping; a universal proof of the narrower theorem is a separate achievement. [Release source][reverse] |

Rerun existing Guava and #337 controls after each accepted extension. Preserve formerly unresolved historical rows alongside new independent evidence. Favor reuse that survives the second release library. A named first unsupported instruction on the unfamiliar case is a better handoff than a claim weakened to the few inputs that passed.

## 3. Certify a complete bounded verdict through the ordinary entry

Start with **example 336, `first-8-release`**. Use the registered normal entry `python3 examples/tools/build.py 336 --task first-8-release` and make certified execution opt-in through that path. First show whether the ordinary launcher propagated the request for certification. The earlier experiment had to instrument its environment forwarding to obtain the transcripts. Use `held/prefix-sums` as the second workload. The existing prefix reconstruction already turns the active incremental clause prefix and assumptions-as-unit-clauses into checkable DIMACS. Reuse it. [Capture and qualification][bounded] · [Transcript implementation][transcript] · [Solver boundary][bits]

| Opening workload | Accounting the new path must explain |
|---|---|
| Guava 336 | Main proof: 24 calls, 16 SAT and 8 UNSAT. Separate reachability probe: 2 SAT. Zero constant-false shortcuts. Keep pass identities even when the same process hosts both |
| Prefix sums | One historical stream, 8 SAT and 10 UNSAT. Reproduce all ten certificates |
| Jackson **#393** | Run `conversion-equivalence-classified` from the original entry. The recorded main proof made **19 solver attempts** and classified exactly 16,777,216 disagreements among 2⁵⁴ longs. Discover each attempt’s disposition on the instrumented build. Pair it with `node-checks-same`, an eight-attempt refutation with a JVM-replayed witness. [Positive][jackson-proof] · [Negative][jackson-refutation] |
| UTF-16 **#395**, `exact-order-same-reference` | The recorded main proof reached its target and made **zero** solver calls. Correct output explains the solver-free proof and separately accounts for any reachability pass. A ratio of 0/0 supplies no SAT assurance. [Receipt][zero] |

Bind each event to the independently supplied request, program and classpath, assumptions and bounds, run/pass identity, call ordinal, formula (including assumption units), return status and proof digest if applicable. Reconcile the inventory against the verifier’s actual call boundary. Identify SAT, UNSAT, unknown/interrupted, and solver-free decisions. Explain how SAT models used for reachability or refinement are validated or retained as dependencies. A counter derived solely from the emitted proof files cannot reveal a missing call.

**Acceptance.** In a fresh process, every relevant UNSAT event on the selected ordinary verdict has exactly one matching proof checked by the pinned `cake_lpr`. Check successful process completion **and** its exact `s VERIFIED UNSAT` output line. Remove a proof, duplicate a different event to keep the count constant, swap formulas with different assumption units, and transplant a valid bundle to a different top-level request. Each control must withhold the certified verdict and name the first unmatched item. Preserve the underlying ordinary disposition for diagnosis. Test the legitimate zero-call case too.

A planning replay reconstructed all 18 archived proof inputs. A source-matched local build of `cake_lpr` accepted all 18 and rejected all 146 wrong within-workload pairings. Its executable digest differed from the VM’s pinned build. The new result sought here is **ordinary verdict-level coverage and binding**. Measure generation, verification, storage and end-to-end overhead with the feature on and off. Attribute assurance specifically to the checked UNSAT answers. The JVM encoding, path coverage, constant folding and every assumption used to construct the formulas still have owners.

## 4. Give Lean one useful rule and give the second opinion a rollout decision

**Lean’s job is the range-branch rule.** On the four phases (guard, entry, exhausted, iteration), take the actual Rust decisions for the five ordered terms `0, from, cursor, to, length` and the six signed comparisons. For each accepted Boolean decision prove that every admitted Java-index valuation gives the same result. In the iteration phase `cursor < to`; on exhaustion `cursor == to`. An empty valid range is the boundary control for a mistaken strict comparison. [Actual Rust branch rule][branch] · [Existing scalar proof][lean]

A planning experiment exported 600 entries from the compiled Rust rule. Lean 4.36.0 checked all 336 accepted decisions (168 true and 168 false); Rust declined 264. A disposable variant accepting `from < to` unconditionally in the guard changed one row. Lean failed to prove it, and the all-zero valuation explains why. Turn this into a durable, source- and build-bound check, with explicit term/test mappings, recorded axioms and a repeatable negative control. Lean also checked the generic prefix-extension, non-overflowing 32-bit increment and decreasing-distance lemmas in isolation. Connect one actual forward back edge in both JDK fill overloads to those facts. Mutate the selected cursor or stored operand and show which link fails. An abstract table agreement alone does not prove the decoder, reachable phase invariant, heap update, compiled binary or the whole Java method. Record exactly which implication Lean checks; stop there if a stronger bridge requires a new project.

**Decision on an opt-in Rust second opinion.** Pilot it on original #336, #346 and #337 entries once the historical-producer trial is resolved, the JDK long transfer is qualified, and the earlier controls still pass. Record the fastutil cost before proposing wider adoption. The caller owns the external request and independently pins the actual bytes, method/descriptor, theorem, environment and dependencies. For a #337 caller this includes **both** caller and callee. Demonstrate that submitting a valid callee-only receipt cannot certify the caller. Reuse the frozen checker binary; start a fresh consumer with only its declared inputs, and verify isolation on the managed runner. [Request format][protocol] · [Rust consumer][consumer] · [Isolated execution][replay]

Return a distinct assurance result for (a) independent establishment, (b) a checked behavioral counterexample, (c) malformed or misbound evidence, and (d) unsupported scope. Exit 2 alone cannot distinguish a witness from bad evidence. A direct contradiction blocks an independently established verdict and keeps both original receipts. Preserve the environment assumptions, including initialized verified classes and the declared execution model. The selected semantic rules remain trusted except where a checked correspondence replaces them. The previously reported roughly millisecond Rust checks used a prebuilt consumer; compare preparation, compilation, isolation, certificate generation and fresh checking separately from the full ordinary run. Report measured effort, token/cost figures where available, and trusted-code changes per compatible or genuinely new family. These are observations for the investment decision, not staffing or time limits.

## 5. Resume the other interrupted run · VF-058

This track can start alongside VF-057. The immediate target is four ordinary side claims across two Commons Configuration upgrades. It does not depend on a semantic kernel for all of Java startup.

1. **Start with the live table.** Use a fresh JVM and a private test key. Read `System.getProperties()` twice, install a new String value, read it through the original table, and let a class initializer save that reference. Replace it with an equal-valued, distinct String via `System.setProperty`. Observe the identity of the returned old value, the new table value and the initializer’s saved value. Then install a child `Properties` with the old table as defaults. The child’s `containsKey` is false and `get` returns null while `getProperty` finds the inherited value. Removing it from the parent affects the live lookup and leaves the saved reference intact. This sequence ran on OpenJDK 21.0.13. It distinguishes the exact operations the real initializer uses. State the allowed single-threaded process prestates in each claim. [Configuration initializer][config-source]
2. **Run JSON, then YAML on the frozen implementation.** The original public caller constructs a fresh configuration, reads a document and inspects a named string list. Both dependency sides of #565 and #601 progressed beyond the prior tree-model blocker and stop in `ConfigurationInterpolator$DefaultPrefixLookupsHolder.<clinit>` at its properties read. The four JVM observations per side are `"[red, blue]"`, `"[Ada]"`, `"[7]"`, and `null`. Recheck the full original entry and two fresh live trees in both read orders. Publish the four side-level verdicts, the 16 input observations and whether the same change handled YAML. If lookup advances but parsing stops later, identify that instruction. [JSON receipt][json] · [YAML receipt][yaml]
3. **Test which startup facts transfer.** On JavaParser #4538 keep the two original parent violations and rerun the six open ordinary claims. Test missing and arbitrary supplied separators, subsequent erroneous-class behavior, and fresh default startup. On Commons Compress #767 / XZ, absent and `Dummy` select the dummy cache, `Basic` selects another singleton, and invalid values have a distinct first-use/repeated-use failure sequence. These observations and the existing ordinary counterexample on an admitted nondefault prestate are controls. In successful frame profiles the known next operations are the `DataInputStream` constructor and the `LinkedHashMap` constructor. Recheck all four frozen frame outputs against both versions. Distinguish a proof for fixed process settings, a witness at an admitted ordinary prestate, and proof for every originally admitted state. [JavaParser][javaparser] · [XZ][xz] · [Ordinary XZ witness][xz-witness]
4. **Recount the same population.** Across 23 historical receiver-blocked cases, 16 reach both original methods on the JVM for all registered inputs. The starting native totals are 4/46 ordinary caller sides, 2/23 complete pairs and 0/34 unrestricted paired overloads. Keep all three denominators. Target one newly decided original side followed by a complete pair or independent transfer. VF-058 can record a remaining frontier as out of scope with a concrete reason and owner. The previously deferred ordinary thread-construction frontier stays with VF-056. [Cohort and reproduction][receivers] · [VF-056][vf56]

## What to hand back

- **One decision per finding.** For VF-057, show the producer error, first effective detector, resulting trust boundary and rollout recommendation. For VF-058, show the first newly decided ordinary caller or the first remaining blocker on each attempted frontier, with its actual scope. Preserve any contradictory or incomplete evidence.
- **One comparative results table.** Give each request a stable key. Record opening and final dispositions, independent or primary route, admitted inputs, source and binary identities, refusal or witness, reusable changes and replay command. Keep the old baselines reproducible. Report a bounded or conditional decision at its own scope.
- **One choice for the next investment.** Recommend expanding the semantic checker, expanding whole-verdict LRAT, advancing the startup work, or leaving a route experimental. Ground that choice in a caught error, an independently supported ordinary verdict, or an improvement that survived transfer to a second release. Save checkpoints at each of those decision points so a later worker can resume from a proven result.

The core deliverables are the historical fault comparison, the long-fill transfer, one ordinary whole-verdict certification, and the two Configuration upgrades revisited. The strongest extensions are fastutil’s two different loops, Jackson’s classification with a replayed counterexample alongside it, and Lean connected to an executed rule. The remaining examples are available when they expose a new question. End a line of investigation once its evidence settles the investment decision or identifies the specific research dependency that prevents it.

**Continuation prompt for the runner.** Take the hardest unanswered claim whose result would change the decision. Run the original entry, record the first unproved step, and try a second case that distinguishes the leading explanations. Publish a new proof, a replayed counterexample, or a narrower, evidence-backed boundary. If another brief is waiting, apply the draft’s two-completed-cycles-without-a-new-decision handoff rule. Preserve the current worktree commit and next runnable claim at handoff. An interrupted turn is not a completed cycle.

## Release and preflight identities

| Material | Identity and interpretation |
|---|---|
| JDK range fill | Temurin 21.0.13+9 `java/util/Arrays.class`, SHA-256 `4a41d89cb79284298b95303a66b3738955d22694f9b34016d87241d9ae8193ab`. Planning repeated the byte-bound int/long comparison in a local process. Managed isolation remains part of execution |
| Guava 33.4.8-jre | Maven `com.google.guava:guava:33.4.8-jre`; include the release superclass where required. The frozen Rust checker refused both 16-bit search descriptors. [Release JAR][guava] |
| fastutil 8.5.15 | JAR SHA-256 `cffeb6673bdf1e6e4377d684df2f55ac359cf5cf6df613e05e62deeea500936a`. The frozen checker refused the range descriptors before a semantic proof. Its public overload is deprecated in this pinned release and remains a reproducible test of existing client bytecode. [Release source][fastutil] |
| Commons Lang 3.17.0 | JAR SHA-256 `6ee731df5c8e5a2976a1ca023b6bb320ea8d3539fbe64c8a1d5cb765127c33b4`, `ArrayUtils.class` SHA-256 `f21e4f7f69b2d98bed01748bd5b711b47458007ee762d07f1e4c4c32147bc8cc`. Reverse preflight used lengths 0–5 over `{-1,0,1}`, plus null, and all ordered bound pairs from `{MIN,-2,-1,0,1,2,3,4,5,6,MAX}`. JVM counts are finite observations |
| Managed tools | Recover the pinned identities from the setup and receipts. Source-matched corroboration, newly compiled test binaries and previously published official receipts retain their separate provenance. [Setup][setup] · [Replay commands][kernel] |

[vf57]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/verification/findings.md#L52
[vf58]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/verification/findings.md#L21
[vf56]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/verification/findings.md#L73
[receivers]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/llm-dlc/loops/receiver-construction-and-property-discovery-results.md
[jbmc-results]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/llm-dlc/loops/jbmc-fast-follow-calls-conversions-and-arrays-results.md
[kernel]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel/README.md
[cases]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel/evidence/cases.json
[assurance]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel/assurance.md
[accounting]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel/evidence/bounded-sat/accounting.json
[lrat]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel/lrat.py
[setup]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/llm-dlc/loops/in-the-loop-trusted-kernel-experiment-brief-setup.md
[producer]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/python/jvm_array_induction.py#L309-L329
[adapter]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/examples/tools/targets/array_induction.py#L235-L289
[frame]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel/evidence/frame-witness/results.json
[transfer]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel/evidence/transfer/results.json
[disasm]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/examples/337-jdk-range-fill-alias/records/array-induction/fill-any-length/6b85ebd4829039081f32/class.javap
[range]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel/range.rs
[bounded]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel/bounded_sat.py
[transcript]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/src/bmc/transcript.rs
[bits]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/src/bmc/bits.rs
[jackson-proof]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/examples/393-wide-floating-conversions/receipts/conversion-equivalence-classified/20261123T175658Z-a06b7e22/result.json
[jackson-refutation]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/examples/393-wide-floating-conversions/receipts/node-checks-same/20261123T175647Z-adfae7f5/result.json
[zero]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/examples/395-exact-utf16-comparison/receipts/exact-order-same-reference/20261123T175757Z-81562309/result.json
[branch]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel/range.rs#L104-L132
[lean]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel/Scalar.lean
[protocol]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel/protocol.md
[consumer]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel/main.rs
[replay]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/lib/benchmark/trusted-kernel/replay.py
[json]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/verification/receiver-discovery/qualification/commons-configuration-565/measurement.json
[yaml]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/verification/receiver-discovery/qualification/commons-configuration-601/measurement.json
[javaparser]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/verification/receiver-discovery/transfer/javaparser/measurement.json
[xz]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/verification/receiver-discovery/transfer/xz/measurement.json
[xz-witness]: https://github.com/pilifs/in-the-loop/blob/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d/verification/receiver-discovery/transfer/xz-ordinary-witnesses/measurement.json
[head]: https://github.com/pilifs/in-the-loop/tree/867fa025a5b4ee4fecf312a3bd304c3c831c8e3d
[fastutil]: https://github.com/vigna/fastutil/blob/355d8ebfaf2bcc4032cc1c25bec9f3fe827f8175/drv/Arrays.drv#L377
[guava]: https://repo.maven.apache.org/maven2/com/google/guava/guava/33.4.8-jre/
[guava31]: https://repo.maven.apache.org/maven2/com/google/guava/guava/31.1-jre/
[beam]: https://repo.maven.apache.org/maven2/org/apache/beam/beam-vendor-guava-32_1_2-jre/0.1/
[reverse]: https://github.com/apache/commons-lang/blob/29ccc7665f3bc5d84155a3092ab2209a053324e6/src/main/java/org/apache/commons/lang3/ArrayUtils.java
[config-source]: https://github.com/apache/commons-configuration/blob/d2101a20e2b74ced47ae57dd3b6d1d90b03d409b/src/main/java/org/apache/commons/configuration2/interpol/ConfigurationInterpolator.java#L166-L172
