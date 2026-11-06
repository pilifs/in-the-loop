# Outside review: the engines after the sound-verdicts loop

A review of this repository at `6cea609e` (2026-11-06), after the sound-verdicts loop, reading `lib/benchmark/results.json`
and the JBMC jobs' recorded outputs. Kept verbatim as the input to [`engine-priorities.md`](engine-priorities.md). Its
figures were rechecked against `results.json` when the draft was written. Its closing offers were addressed to the user.

---

I reviewed the newly pushed artifacts at [`6cea609`](https://github.com/pilifs/in-the-loop/tree/6cea609e55c5eff4b90bfce7b14b114e7cf6553e), including the raw benchmark results and the JBMC jobs’ recorded outputs.

**The native-first recommendation is now better supported, but I would change two immediate priorities: fix the phase accounting, and test a different JBMC staging policy before doing any fork work.** The raw results reveal substantial repeated solving that the summarized phase table obscured.

They also identify concrete coverage work: application class initialization for native, and two individual property proofs in example 071 that depend on incomplete models.

## 1. What the published benchmark establishes

The benchmark contains **712 runs**, executed at `b2e3b9c5`, before the bucket functional-consistency fix. Its published results confirm the reported absence of false successes under strict/advised and absence of reported false alarms. The older bucket timeout remains in these figures; it should not be silently replaced with the later successful result. [Benchmark report](https://github.com/pilifs/in-the-loop/blob/6cea609e55c5eff4b90bfce7b14b114e7cf6553e/lib/benchmark/RESULTS.md)

I compared the engines case by case under matching modes:

| Mode | Cases | Both decide correctly | Native alone decides correctly | JBMC alone decides correctly | Neither decides |
|---|---:|---:|---:|---:|---:|
| Strict | 120 | 98 | **10** | **3** | 9 |
| Advised | 118 | 102 | **9** | **3** | 4 |

That gives native **108/120** correct decisive results under strict, versus **101/120** for JBMC. Under advised, the corresponding counts are **111/118** and **105/118**. The different denominators reflect examples 141/142 being run only under strict.

**Native was faster in every jointly correct paired observation: 98/98 under strict and 102/102 under advised.** These are single-run observations on this corpus, rather than a general claim about all Java verification workloads. They nevertheless provide strong evidence for the default engine choice. These counts are calculated from the [raw results](https://github.com/pilifs/in-the-loop/blob/6cea609e55c5eff4b90bfce7b14b114e7cf6553e/lib/benchmark/results.json).

### The formula advantage is sometimes larger than the summary suggested

| Case | Native time | JBMC time/outcome | Native clauses | JBMC clauses | JBMC/native clause ratio |
|---|---:|---:|---:|---:|---:|
| Bounded binary search | 2.797 s | 58.580 s | 240,144 | 3,281,450 | **13.7×** |
| Example 141 | 2.191 s | 65.166 s | 137,013 | 4,718,689 | **34.4×** |
| Prefix sums | 0.197 s | 4.651 s | 5,637 | 959,836 | **170×** |
| Reverse | 0.214 s | OOM | 59,707 | 17,233,885 | **289×** |

Example 141’s missing time is now available: native is approximately **29.7× faster** in the configured end-to-end check. Prefix sums is another particularly strong result: approximately **23.6× faster**, with a much larger clause-count difference than the earlier 10–35× description.

The OOM case does not support a completed-runtime speedup ratio. Also, these remain the existing formula metrics—native’s accumulated incremental formula versus JBMC’s reported formulas—not identical post-preprocessing SAT instances. [Raw measurements](https://github.com/pilifs/in-the-loop/blob/6cea609e55c5eff4b90bfce7b14b114e7cf6553e/lib/benchmark/results.json)

## 2. The biggest new performance finding: JBMC’s staged search is expensive

The raw `solver.runs` show how much of the reported latency comes from preliminary restricted-input checks:

| Case | Overall JBMC time | First restricted stage | Second restricted stage | Final full-input-range run |
|---|---:|---:|---:|---:|
| Binary search | **58.580 s** | 15.112 s, timeout | 15.134 s, timeout | **28.108 s, verified** |
| Example 141 | **65.166 s** | 15.196 s, timeout | 15.156 s, timeout | **34.597 s, verified** |
| Checksum fix-confined | **18.463 s** | 5.726 s, verified | 6.072 s, verified | **6.500 s, verified** |
| Lower bound | **7.210 s** | 2.310 s, verified | 2.207 s, verified | **2.517 s, verified** |
| Floor-mod, wide modulus | **15.503 s** | 0.051 s, verified | 15.042 s, timeout | **0.251 s, counterexample** |

“Full input range” here retains the same array and loop bounds. These are observed stage durations, not predictions of how an isolated full-range-first run would perform. [Per-stage results](https://github.com/pilifs/in-the-loop/blob/6cea609e55c5eff4b90bfce7b14b114e7cf6553e/lib/benchmark/results.json)

This changes an important part of my previous assessment:

**Startup optimization has limited value on these hard cases, but adapter-level work selection can have substantial value.** An adapter can save expensive solving by avoiding unproductive queries.

The wide-modulus case illustrates this especially well. Its intermediate restricted query consumes 15 seconds, while the final query finds a counterexample in a quarter-second. Its largest reported JBMC formula is also *smaller* than native’s: 40,640 versus 55,638 clauses. The configured pipeline loses badly even though its final obligation is solved quickly.

That suggests a concrete, inexpensive experiment:

1. Compare the current staged policy with **full-input-range first**.
2. Compare a third policy with **one tightly budgeted preliminary search**.
3. Preserve the same overall deadline, semantic bounds, models, and evidence rules.
4. Measure both successful proofs and counterexample discovery.
5. Use the existing witness-shrinking machinery after finding a counterexample where appropriate.

Your current code already removes stages that do not restrict the domain. The remaining question is whether stages that *do* restrict it are worth attempting. That is a different optimization, and the new data now gives it a clear justification. See [`deadline.rs`](https://github.com/pilifs/in-the-loop/blob/6cea609e55c5eff4b90bfce7b14b114e7cf6553e/lib/src/deadline.rs).

The explicit `--confirm` path already performs a full-range confirmation, so this experiment belongs primarily in ordinary JBMC checking and fallback policy.

Even if those preliminary stages disappeared, native would retain a substantial advantage on the major array examples: the observed final JBMC run alone is about **10× native’s entire binary-search check**, and **16× native’s entire example-141 check**. The staging opportunity strengthens the case for improving stock JBMC’s integration before carrying core patches.

## 3. There is a real phase-accounting defect

The published phase table contains impossible totals. For JBMC array mutation, it reports **40% encoding plus 87% solving**, before the other phases.

This is not just rounding. For strict reverse:

- End-to-end wall time: **15.887 s**
- Reported encoding: **7.980 s**
- Reported solving: **13.753 s**
- Sum of all reported phases: **22.011 s**

I traced the cause through both your code and the source for the actual upstream release, CBMC/JBMC 6.11.0:

- [`run_property_decider()`](https://github.com/diffblue/cbmc/blob/820ff0f555b43fb78e0cd9332e498461bd14244b/src/goto-checker/bmc_util.cpp) measures the whole decision-procedure call as `Runtime Solver`.
- Inside that call, [`prop_conv_solvert::dec_solve()`](https://github.com/diffblue/cbmc/blob/820ff0f555b43fb78e0cd9332e498461bd14244b/src/solvers/prop/prop_conv_solver.cpp) performs `finish_eager_conversion()` and reports its duration as `Runtime Post-process`.
- Your [`phases.rs`](https://github.com/pilifs/in-the-loop/blob/6cea609e55c5eff4b90bfce7b14b114e7cf6553e/lib/src/phases.rs) adds post-processing to encoding **and** the enclosing solver duration to solving.

The timers overlap. Clamping the residual `other` field to zero leaves that overlap intact.

**This affects the attribution of time, not the measured wall times, outcomes, or clause counts.** The native advantage remains. However, I would withdraw the broad reliance on “82–99% solving on both engines” until the JBMC accounting is corrected.

The native timings independently support the underlying priority:

- Binary search: approximately **89.6%** solving.
- Example 141: approximately **87.5%**.
- Example 142: approximately **94.2%**.

For the repair, account for nested timers per solver invocation, handle interrupted invocations separately, and check that exclusive phase totals agree with elapsed time within a reasonable tolerance. A small set of captured output fixtures covering success, timeout, and OOM would be useful here. Normalizing percentages to 100% would conceal the underlying problem.

## 4. The newer JBMC runs close integration work, with some important distinctions

I checked the recorded differential data embedded in the jobs’ `changes.diff` files.

| Job | Recorded status | What the artifacts establish |
|---|---|---|
| `-073804`: initial reader comparison | Failed | **78 JSON/text comparisons, zero disagreements**. Five examples had unapplied patches and did not produce their intended outcomes. |
| `-123940`: corrected five-example rerun | Passed | **10 comparisons, zero disagreements**. All five examples recover their expected outcomes. |
| `-082917`: JBMC gap inventory | Failed | All **41 examples** produce their expected outcomes; the subsequent table-generation script fails on the newer result schema. |

Sources: [initial differential](https://github.com/pilifs/in-the-loop/blob/6cea609e55c5eff4b90bfce7b14b114e7cf6553e/verification/results/20261106-073804-jbmc-read-through-json-ui-agrees-with-th/result.json), [corrected rerun](https://github.com/pilifs/in-the-loop/blob/6cea609e55c5eff4b90bfce7b14b114e7cf6553e/verification/results/20261106-123940-jbmc-s-two-readings-on-the-five-recorded/result.json), and [gap-inventory job](https://github.com/pilifs/in-the-loop/blob/6cea609e55c5eff4b90bfce7b14b114e7cf6553e/verification/results/20261106-082917-jbmc-s-own-approximations-as-gaps-every/result.json).

### The JSON migration is complete

Across the two reader jobs, there are **88 paired comparisons with no disagreements**, collectively covering the recorded JBMC examples after the corrected rerun. These compare verdicts, ending classifications, property counts, and canonical counterexample inputs.

That is good evidence for removing the old text reader, which the latest code has done. It validates the output migration; it is not an independent verification of JBMC’s Java semantics.

The initial example-134 result also deserves careful interpretation: it took about **1,049 seconds** on the unintended unpatched input, then **0.7 seconds** with the patch properly applied. That is a pipeline/input correction, not a solver speedup. The fixes that now reject skipped patches are materially useful.

### Strict’s impact is visible only at the obligation level

The recovered gap analysis, recorded in the repository’s progress notes, reports:

- 41 examples and 43 obligations, run under **assume**.
- Only examples **013 and 071** reach the identified JBMC gaps.
- The relevant calls are `Enum.<init>(String,int)`, `List.copyOf`, and `List.of`.
- Under strict, **071’s first two successful property proofs would become no verdict**.
- Its third property remains refuted, so the example’s overall violation label remains unchanged.
- Example 013’s refutation also remains.

Thus, “strict changes no example verdict” does **not** mean all individual proofs survive. The new per-obligation `gap_table.py` is the right reporting level. [Recorded findings and decisions](https://github.com/pilifs/in-the-loop/blob/6cea609e55c5eff4b90bfce7b14b114e7cf6553e/llm-dlc/loops/sound-verdicts.md)

The strict default is now implemented for subsequent recorded-example runs. The historical gap job was not a strict rerun; its strict impact was projected from the recorded gaps.

One publication detail remains: the gap job’s complete build log is committed, but the repaired per-obligation JSON used to reconstruct the gap table is not. The precise gap inventory is corroborated by the committed notes and example metadata. Saving that recovered table alongside the job would make it directly reproducible from the published artifacts.

These results lower the urgency of a generic strict-mode JBMC fork. The adapter is already addressing the demonstrated workload. Restoring 071’s two successful properties, if valuable, is a focused model/contract task—subject to correctly representing the relevant list and enum behavior.

## 5. The coverage results give us a more concrete native roadmap

### Application class initialization is the clearest benchmark-specific extension

All **three JBMC-only wins** under both strict and advised involve application class initializers:

| Case | Native | JBMC |
|---|---|---|
| `boom/1` | Refuses `Boom.<clinit>` | Correct violation |
| `inherited/1` | Refuses `Base.<clinit>` | Correct violation |
| `quiet/1` | Refuses `Quiet.<clinit>` | Correct verification |

This is more useful than a generic recommendation to “expand Java support.” It identifies a real fallback category and a concrete candidate for reducing dependence on JBMC.

I would assess scoped native class-initialization support against its frequency in your actual methods. A different SAT or SMT solver will not close this gap: it is missing execution semantics. [Case-level evidence](https://github.com/pilifs/in-the-loop/blob/6cea609e55c5eff4b90bfce7b14b114e7cf6553e/lib/benchmark/results.json)

### The broader examples still justify retaining JBMC

The 41-example run includes **035**, the NaN comparison regression, and records its expected violation. Native currently refuses the relevant floating-point arithmetic, while JBMC finds the counterexample. That is a concrete complementary capability outside the integer/primitive-array benchmark. [Example 035](https://github.com/pilifs/in-the-loop/blob/6cea609e55c5eff4b90bfce7b14b114e7cf6553e/examples/035-nan-compared-with-equals-turns-fcmpl-into-fcmpg/README.md)

So the benchmark’s three unique JBMC wins should not be interpreted as its entire remaining value. A matched native/JBMC coverage inventory over the broader recorded examples would help choose which dependency-reducing semantic extensions matter most.

### Witness validation is demonstrably doing useful work

For `caught/1` and `nestedHandler/1`, JBMC produces counterexample candidates that the wrapper’s interpreter rejects. The tool returns **unverifiable / witness not reproduced**, preventing those candidates from becoming reported false alarms.

That supports keeping the validation boundary intact through future solver work. It also provides two small cases for targeted investigation. The diagnostic’s suggestion of missing modeled bodies is not an established root cause; the raw artifacts alone do not identify whether the discrepancy lies in models, exception handling, translation, or trace interpretation. [Raw results](https://github.com/pilifs/in-the-loop/blob/6cea609e55c5eff4b90bfce7b14b114e7cf6553e/lib/benchmark/results.json)

## 6. Revised next steps

I would now use this order:

| Priority | Work | Why the new artifacts support it |
|---|---|---|
| **Immediate** | Correct JBMC phase accounting | Precise phase shares currently overlap and could misdirect optimization |
| **Immediate** | Compare staged versus full-range-first JBMC checking | Several cases spend substantial time on preliminary queries; no fork is needed |
| **Next native coverage investigation** | Application class initialization | It accounts for every JBMC-only win in the benchmark |
| **Next infrastructure work** | Capture incremental queries and introduce the narrow SAT interface | Separates query scheduling, encoding, and solver effects |
| **Next solver experiments** | Newer CaDiCaL, then typed bitvector/array obligations for Bitwuzla and Z3 | Still well motivated; the new runs do not compare alternative solvers |
| **Targeted model work** | Recover 071’s two property proofs where useful | A specific remaining coverage need |
| **Deferred** | Substantial JBMC engine fork | No new result makes it the best investment |

The solver recommendation remains, with stronger evidence for preserving incrementality: native makes **942 solver calls** for bounded binary search and **1,044** for example 141. A backend that looks good on one exported final CNF may behave differently across that sequence. Record both fixed query transcripts and full-check performance.

The benchmark export should also retain the actual SAT solver signature/configuration. It currently records the JBMC and checker versions, but does not preserve the exact SAT backend identity in `results.json`. That is a small metadata addition with direct value for the planned comparisons.

**I would keep stock JBMC, improve which queries the adapter asks it to solve, and put the larger engineering effort into native semantic coverage and controlled solver/encoding experiments.** The new evidence makes a performance fork less compelling while identifying useful work that can improve both engines’ practical value immediately.

---

If you want, I can:

- Suggest detailed plan for correcting JBMC phase accounting
- Design experiment comparing JBMC staged policies
- Outline steps to implement native class initialization support
