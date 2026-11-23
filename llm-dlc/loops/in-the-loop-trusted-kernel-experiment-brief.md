# Is an independently checked Java proof worth the effort?

**Execution brief · 22 November 2026**

Build a checker that can accept or reject a precise claim about the actual Guava `Ints.indexOf` class bytes. Then freeze it and measure what it costs to check `Longs.indexOf`. The project already has evidence for both claims. The experiment earns its keep if it can remove a meaningful component from the acceptance decision, detect an error in evidence the producer could have supplied, and carry that gain to the second method at a reasonable cost. A small SAT-certificate experiment gives us a cheaper investment to compare against. [Original discussion][chat] · [Pinned develop commit][head]

## What exists at the starting commit

Use `d717edd200ec3a781b7c7e179200e4a7dc549740` as the reference. If executing on newer `develop`, record the actual commit and any changes to these paths or results before comparing costs. The figures below are checked-in results.

| Case | Existing evidence | What the experiment adds |
|---|---|---|
| 336 · Guava `Ints.indexOf(int[], int)` | The public wrapper forwards the whole array to a private range helper. The any-length record has two SAT domain checks and eight UNSAT obligations for the entries, exits, safety, frame and termination. | Check the whole public call from the release bytes in a fresh process. A proof that begins at the first instruction of the private loop leaves the wrapper outside its claim. [Record][ints] |
| 346 · Guava `Longs.indexOf(long[], long)` | The same Guava 33.4.8-jre JAR. The old rule first refused the long descriptor. The extended rule records three SAT domain checks and eight UNSAT obligations, including a check that admits distinct values with the same low 32 bits. | Measure the incremental effort to support 64-bit cells and target, category-2 locals and `lcmp`, while all lengths, indices, return values and the loop variant stay 32-bit. [Transfer refusal][refusal] · [Completed record][longs] |
| 337 · JDK range fill, optional | The caller observes a range fill through shared or distinct array roots. The bounded extra-write claims are refuted. The any-length extra-write caller is **unresolved** because a caller-read obligation expected UNSAT and obtained SAT. | Test whether the next investment buys support for mutation, frame reasoning and aliases. Preserve the distinction between failure to prove and a checked counterexample. [Tasks][fill] · [Caller record][extra] |

The current induction route prepares class files, reads `javap` output, constructs verification conditions in Python and asks Z3 to solve them. The adapter qualifies class initialization and compares saved records. Its `--compare` can successfully reproduce an unresolved result. Record the disposition and individual obligations. A zero exit or matching digest alone cannot establish the method theorem. [Producer][producer] · [Adapter][adapter] · [Existing standalone tests][induction-tests]

## Freeze the claim before writing the checker

The external request supplies the artifact, method owner/name/descriptor, statement and assumptions. The producer supplies evidence. Both Rust and Lean get the same logical interface.

```text
check(actual_class_bytes, requested_claim, assumptions, certificate)
    → accepted(checked_statement) | rejected(reason) | unsupported(reason)
```

For 336, ask for the following theorem. Start after successful class initialization, in single-threaded execution, with the pinned class resolution, ordinary JVM execution and an already allocated non-null `int[] a`. For **every** legal length and every signed Java `int x`, the public call terminates normally. It returns the least index `i` with `a[i] == x`, or `-1` exactly when no index matches. The heap at return equals the heap at entry. Cover empty arrays, repeated matches, signed extrema and index arithmetic up to the largest representable legal length. Treat VM resource failures and asynchronous termination as environmental exclusions. State whether well-formed/verified classes are an assumption. Record initializing classes as a separate precondition unless the checker actually discharges it.

Bind `Ints#indexOf([II)I` and its private `indexOf([IIII)I` in `com.google.common.primitives`. Check constant-pool call resolution and that the public method passes `0` and the actual array length. For 346, substitute `Longs#indexOf([JJ)I`, helper `indexOf([JJII)I`, and all signed 64-bit target and cell values. Keep the other obligations fixed. Both release classes come from `com.google.guava:guava:33.4.8-jre`, JAR SHA-256 `f3d7f57f67fd622f4d468dfdd692b3a5e3909246c28017ac3263405f0fe617ed`. Bind the actual class entries by digest and descriptor, including any supporting classes used to justify resolution or initialization. [336 target][int-target] · [346 target][long-target]

## Run order

Keep the work in an opt-in experiment directory or branch. Compare Rust and Lean on the same compiled methods, theorem and controls. Record the implementation changes and human interventions each route requires, including failed approaches.

| Stage | Work and exit condition |
|---|---|
| 1. Establish the baseline | Freeze the claim, assumptions, controls and effort measures. Extract the pinned class bytes, record tool versions and reproduce the two existing results. Record any historical toolchain or comparison mismatch. |
| 2. Compare the prototypes | Run Rust and Lean on the same scalar theorem over actual compiled methods, `2*x == x+x` for every Java `int` with wraparound. Check both methods and reject `x+x+1`. Run the SAT comparator in parallel. |
| 3. Check the public method in 336 | Pick one semantic route and take 336 end to end. Rust is the starting preference. Prefer Lean if it checks the same theorem against the actual class bytes and removes more trusted proof logic at an acceptable review cost. Record the other route's strongest result and any blocker. |
| 4. Transfer the frozen checker to 346 | Snapshot the checker, certificate format, theorem and passing 336 evidence. Try 346 **before editing**. Record the first result and each change needed for transfer. Rerun 336 and its controls. Start the optional 337 case only after both required examples and their controls are complete. |
| 5. Replay and decide | Recheck from clean inputs, run held-back controls and write the decision. For any incomplete stage, identify the missing rule, bytecode link or tool prerequisite. Preserve the strongest completed result and the first failure. |

Run both baseline commands from the repository root.

```sh
python3 examples/tools/build.py 336 --array-induction first-any-length --compare
python3 examples/tools/build.py 346 --array-induction first-any-length --compare
```

Use the example preparer for the published artifacts and its JDK 21 configuration. The repository has a `2*x` fixture and compiled-test inputs for `x*2` and `x+x`. Freeze the chosen scalar method descriptors and both resulting byte sequences. The paired scalar theorem is an experiment deliverable. [Scalar fixture][scalar] · [Integration fixtures][scalar-pair]

## How each route earns its result

**Rust semantic checker.** Accept hints for PCs, invariants and the decreasing measure. Starting from the requested class bytes, resolve the method and call, recover reachable instructions and edges, and check every applicable rule. Establish the loop bounds and the absence of an earlier match at entry and after each iteration. Show every load is safe, each exit satisfies the requested result, the heap is preserved and `length − i` strictly decreases without Java-int overflow. Account for exceptional control flow or show it is infeasible under the assumptions. Reject unsupported reachable operations. Key obligations by method, PC/edge and kind so the two exits cannot satisfy one another's obligations. The existing Rust class reader is a reasonable starting point. Count every shared decoding or semantic dependency in the trusted base. A Rust acceptance rests on the correctness of these rules. [Class-file decoder][decoder] · [JVM instruction semantics][jvms]

**Lean comparison.** Start with the same byte arrays, theorem and assumptions. The checked theorem must connect decoding those bytes to the stated execution semantics. An evaluator proof, a small verified rule or a certificate checked by a proved-sound function are all eligible. Save the final theorem, exact Lean version, `#print axioms` output and a clean check command. Require zero `sorry` and zero unreviewed axioms. Identify any trusted parsing, native evaluation, foreign code or asserted correspondence. A proof over a hand-transcribed program is a useful partial milestone. Record the remaining cost to connect it to the actual bytes. [Lean axioms][lean] · [JVM class-file format][class-spec]

**SAT/LRAT comparator.** Use the native bit-blasted path on a real bounded claim, for example `python3 examples/tools/build.py 336 --task first-8-release` with `JVMCONTRACT_TRANSCRIPTS` set to a fresh directory. The any-length route above uses Z3. Select one observed UNSAT call from the incremental transcript. If that task yields no suitable call, try one recorded native workload such as `held/prefix-sums` and name the substitution. Export only the clauses preceding that solve and add a unit clause for each of **that call's** assumptions. Pin the transcript, query index, DIMACS and tool versions. Produce an LRAT proof with a pinned CaDiCaL 1.9.5 CLI, then run `cake_lpr query.cnf query.lrat` in a fresh process. Require verified UNSAT, rejection of a damaged proof and no acceptance on a known satisfiable query. Record the proof size and peak memory used by the proof generator and checker separately. Report the fraction of observed UNSAT queries certified and any decisions the engine settled without a solver call. The certificate establishes UNSAT for the exported formula. Deriving the right formula and covering every execution still depend on the verifier. [Native transcript format][transcripts] · [Solver workloads][solvers] · [CaDiCaL LRAT example][lrat] · [cake_lpr][cake]

## Controls that distinguish the trust gained

Run the existing path and the new checker against the same in-scope controls wherever possible. Capture one concrete JVM input/output for each behavioral mutant and keep one mutation or equivalent implementation held back until the checker is frozen.

| Control | Expected observation |
|---|---|
| Fresh, correctly rebound last-match mutant | On `[7, 7]` with target `7`, the public method returns 1. Its first-match theorem must fail. Input preservation can still hold. |
| Wrong wrapper or helper | Start the helper at 1, or change the miss result to 0. The singleton-at-index-zero and empty-array cases distinguish the respective behaviors. Checking the original helper alone must never accept the changed public theorem. |
| Correct return, damaged heap | Compile a variant that saves its correct result and then changes a nonempty input cell before returning. The combined theorem must fail even where the returned index is correct. |
| Width and termination | Compare long elements that differ by 2³², for example `[0, 4294967296]` and target `4294967296`. A truncating comparison wrongly returns 0. A no-progress loop on a nonmatch must fail the termination claim. |
| Evidence substitution or omission | Swap class/certificate/descriptor, weaken the requested property inside the certificate, or remove one return-edge/frame obligation. The consumer must still enforce the external request and all reachable obligations. |
| Valid, unfamiliar implementation | Try a harmless local-variable/layout change under the same claim. Record acceptance or the exact unsupported rule. This exposes recognition of one compiled shape. |

**Also test a fault in the producer itself.** On a disposable copy, have the producer replace the failing frame obligation of the heap-writing variant with a tautology. Let it regenerate its own formula, answers and digests. Record exactly which existing acceptance or replay step detects the fault, then give the same externally requested theorem and altered evidence to the independent checker. If the independent check catches a substitution the existing path accepts, identify the responsible rule. If both catch it, credit both.

For semantic mutants, regenerate class hashes and allow a fresh certificate attempt. A stale-hash failure demonstrates binding only. A refusal at an unsupported opcode demonstrates a coverage limit. Credit semantic discrimination when the good case passes and the bad case fails for a relevant supported rule, or a checked witness refutes it. Count a false acceptance even if a subsequent fix repairs it. Retain the failing bundle and rerun every control after repair.

For the optional 337 case, run `fill-any-length`, then `caller-any-length`, then `caller-extra-any-length`. Use valid half-open ranges, shared or distinct roots, and independent legal lengths for distinct arrays. Check both the write frame and the caller's observation. Report which statements the checker establishes, refuses or refutes. [337 contract and controls][fill]

## Evidence and investment decision

Deliver one replay command for each completed route, a minimal immutable evidence bundle and a short decision record. Include a machine-readable case table keyed by route, class digest, requested claim, control and checker version. Record the expected and actual outcomes and the reason for each rejection. The semantic recheck must run in a fresh process with the producer, its verdict and its caches unavailable. Supply the original bytes, external claim/assumptions, certificate and pinned checker dependencies. Record any solver or decoder still needed by the consumer. A second person or agent should be able to change the requested theorem or exchange the certificate and reproduce the corresponding outcome.

| Record for each route | Measure |
|---|---|
| Assurance | Exact strongest accepted statement and domain, residual trusted components and why, which components can now be wrong without causing acceptance, supported/unsupported obligations, positive and negative outcomes for each control. |
| Build effort | Describe the changes, failed attempts and human interventions for setup, decoding and byte binding, JVM semantics, proof work, integration, debugging and review. Include token use or monetary cost where available. |
| Cost to reuse | Record the frozen 346 result before edits, the trusted rules, functions and lines that changed, any producer-only changes, and which invariants, theorems and controls carried over. Record which parts of the existing Guava solution the agent consulted. 346 is a transfer case the project already knows. |
| Cost to operate | On the same hardware, record evidence bytes per case and peak memory for generation and checking. Record build and setup separately. Report median peak memory across three fresh checks. |

**Advance the semantic checker** for one further claim family if 336 and 346 both pass at full scope from original bytes, meaningful rebound mutants fail semantically, a fresh consumer reproduces the result, and the team can identify a producer error that has lost the ability to cause acceptance. Compare the trusted rules, proofs and human interventions needed to add 346 with those needed for 336 after the scalar checkpoint. Identify what carried over and what had to be built again. If transfer requires substantial new work, explain what a follow-up would cost before recommending it. Estimate fixed setup cost versus cost per additional compatible claim from the two runs, with the observed 336→346 transfer as a best-case estimate. Name the next claim that would benefit and the capability work it would displace.

**Advance only the SAT certificate work** if it independently checks a real query at an acceptable measured cost and the semantic route stalls on bytecode binding, proof maintenance or reuse. Price the next step required to cover all UNSAT decisions that matter to one bounded claim.

**Defer broader investment** if only the scalar or a manually modeled method passes, if an unexplained false acceptance remains, or if the trusted checker duplicates the producer at comparable maintenance cost. Name the closest missing rule and the implementation and proof work a follow-up experiment would require to change the decision. Ground the funding decision in replayable evidence. A production rollout would be a separate decision.

[chat]: https://chatgpt.com/c/6b025d8b-83b4-83e9-ac93-ad0bf2ea79c5
[head]: https://github.com/pilifs/in-the-loop/commit/d717edd200ec3a781b7c7e179200e4a7dc549740
[ints]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/examples/336-guava-first-array-match/records/array-induction/first-any-length/58996c50200b0046ffaa/result.json
[longs]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/examples/346-guava-long-array-holdout/records/array-induction/first-any-length/0e84bb986daf03cbffef/result.json
[refusal]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/examples/346-guava-long-array-holdout/records/transfer-baseline.json
[int-target]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/examples/336-guava-first-array-match/target.json
[long-target]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/examples/346-guava-long-array-holdout/target.json
[fill]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/examples/337-jdk-range-fill-alias/target.json
[extra]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/examples/337-jdk-range-fill-alias/records/array-induction/caller-extra-any-length/98d5d5ae53cf2d12ce0c/result.json
[producer]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/python/jvm_array_induction.py
[adapter]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/examples/tools/targets/array_induction.py
[induction-tests]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/python/test_jvm_array_induction.py
[decoder]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/classfile/bytecode.rs
[scalar]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/tests/fixtures/java/fixtures/Overloads.java#L15
[scalar-pair]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/tests/integration.rs#L464
[transcripts]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/src/bmc/transcript.rs
[solvers]: https://github.com/pilifs/in-the-loop/blob/d717edd200ec3a781b7c7e179200e4a7dc549740/lib/solvers/README.md
[jvms]: https://docs.oracle.com/javase/specs/jvms/se21/html/jvms-6.html
[class-spec]: https://docs.oracle.com/javase/specs/jvms/se21/html/jvms-4.html
[lean]: https://lean-lang.org/doc/reference/latest/Axioms/
[lrat]: https://github.com/marijnheule/coch-demo
[cake]: https://github.com/tanyongkiam/cake_lpr

## Setup Agent Notes

### What is ready, and where

`$B` = `~/.cache/in-the-loop/trusted-kernel`.
- The release jar `guava-33.4.8-jre.jar` (sha256 `f3d7f57f…e617ed`, = brief) and its runtime graph, signature- and
  checksum-checked: `$B/releases/guava-33.4.8-jre/lib/`; sources jars beside it. The preparer's cache
  (`~/.cache/in-the-loop/targets/sha256/`) already holds what 336 and 346 list.
- The class bytes, extracted: `$B/classes/guava-33.4.8-jre/com/google/common/primitives/`. `Ints.class`
  `ae581f72…4edbb`, `IntsMethodsForWeb.class` (its superclass) `a31b9770…17bd6`, `Longs.class` `b8c75a5f…96d9`; all
  equal to the existing records. `javap` of each: `$B/logs/javap-*.txt`.
- Guava source at the release commit `f06690fa`: `$B/src/guava-33.4.8`.
- CaDiCaL 1.9.5 CLI: `$B/src/cadical-1.9.5/build/cadical`. `cake_lpr`: `$B/src/cake_lpr-033aad53/cake_lpr`. LRAT
  round-trip example: `$B/probes/lrat-smoke/`.
- Lean `v4.36.0` and `v4.35.0`, both checked file by file against their release archives.
- JDK 21 (Temurin 21.0.13+9), Z3 5.3.3 (the records' binary, same digest), and the checker built at this head.

### What was verified on a JVM

On Temurin 21.0.13 with the release jar: `Ints.indexOf([7,7],7) = 0`, empty → −1, `[5]`/5 → 0, signed extrema at
both ends, and `Longs.indexOf([0, 2^32], 2^32) = 1` (no truncation), `[2^32]`/0 → −1, `Long` extrema; every input
array unchanged, and the classes the JVM loaded have the digests above (`$B/logs/jvm-guava-indexof.txt`, 14 of 14).
None of the brief's mutants exists yet.

### What to know before starting

- This head is `3471332a3`, 150 commits after the brief's `d717edd2`. Of the linked paths, only
  `lib/tests/integration.rs` changed (one test added after line 549); the `#L464` scalar lines are unchanged.
- **`cake_lpr` exits 0 when it rejects.** Read stdout for `s VERIFIED UNSAT`. It rejected a truncated proof, a proof
  with one literal flipped, and a proof against a satisfiable formula, all with exit 0.
- `cake_lpr` is at its upstream head, whose README says it is the last release before it is "superseded by a new
  checker in this repository": pin `033aad53`, not the branch. Heap and stack sizes are flags
  (`--CML_HEAP_SIZE=<MiB>`), no longer environment variables.
- The checker's bundled solver is CaDiCaL 1.9.5 (crate `cadical` 0.1.16), differing from the upstream tag only in
  Windows portability code, so the brief's pinned CLI is the same solver as the engine's.
- `lean` follows elan's `stable` channel and moved to v4.36.0 during this setup. Pin a toolchain (a
  `lean-toolchain` file or `elan run leanprover/lean4:vX`) before recording "the exact Lean version".
- The scalar fixtures are compiled by the tests with javac 25 (`-parameters -g -proc:none`), not JDK 21, and the
  fixture folder does not compile with JDK 21 (`TrafficLight.java` uses `_`). `Overloads.twice(int)` is
  `iconst_2; iload_0; imul; ireturn` under javac 25.
- GNU `time` is absent; the `resource.getrusage(RUSAGE_CHILDREN)` line above gives peak memory.
- Nothing here is a snapshot: every input is a pinned release, tag or commit.

### What is left for the domain work on purpose

- The two Stage 1 baseline runs (`build.py 336|346 --array-induction first-any-length --compare`), which run the
  verifier on the existing claims: submit them as jobs (B11) or run them as the brief and `CLAUDE.md` allow.
- The `first-8-release` transcript for the SAT comparator, the choice of query, the DIMACS export and its LRAT proof.
- The claim, assumptions, certificate format, the scalar pair (methods, JDK, frozen bytes), all controls and mutants,
  the Rust and Lean checkers, and the optional 337 runs.

## Results

The independent Rust consumer proved both original public Guava calls at full scope. The frozen int checker first refused the long descriptor. The transfer added 49 net lines on the acceptance path and kept the certificate format and induction invariant. Six rebound behavioral mutants have checked witnesses. The Lean scalar theorem is bound to the compiled bytes. The LRAT comparison certified every observed UNSAT in the bounded Guava task and the prefix-sums workload.

The follow-up proved the exact JDK range-fill frame and example 337's original caller observation for every valid range and both alias relationships. Its extra-write caller has a checked counterexample on a shared singleton. The historical producer's caller-read obligation remains unresolved. A second caller control reaches a bounds exception with distinct arrays of lengths zero and one. The clean Rust checks of the original fill and caller took 1.24 and 1.28 ms. [Decision, costs and replay commands](../../lib/benchmark/trusted-kernel/README.md) · [Per-case results and artifact digests](../../lib/benchmark/trusted-kernel/evidence/cases.json)
