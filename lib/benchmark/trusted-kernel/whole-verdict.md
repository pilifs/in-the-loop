# Checking all SAT calls of a native verdict

Run a strict native proof through the ordinary target route with the pinned CaDiCaL 1.9.5 generator and cake_lpr checker available on the machine.

```sh
python3 examples/tools/build.py 336 --task first-8-release --certify-lrat
```

The command prints the ordinary receipt path and the assurance result. The sibling `lrat/` directory contains the caller's request, the observed native boundary, the proof bundle and `assurance.json`. The exit code requires both the expected ordinary result and completed assurance. A failed check preserves the ordinary verdict and records the first missing or mismatched item. An ordinary run without the option uses its original settings.

The target runner freezes the claim, selected methods, ordered artifact digests, JDK, assumptions, bounds, checker identity, invocation and execution ID before launching the verifier. Each native log names its own clause transcript and independently records every attempt at the call boundary. The runner reconciles those passes with the ordinary verifier's structured search report, including a separate reachability pass when one ran. An interrupted or unmatched pass withholds assurance.

For each call, replay reconstructs the clauses present at that point and appends the assumptions as unit clauses. It checks the actual SAT assignment against all of them, including the assignments used in refinement and reachability. For each UNSAT call it requires exactly one LRAT proof and a successful exit from the pinned checker with the exact line `s VERIFIED UNSAT`. A constant-false assumption records a decision before the solver. A pass with zero solver calls can account for the ordinary verdict's SAT use without conferring any LRAT assurance on Java reasoning. A refutation also retains its original JVM witness.

Keep the request and boundary from the trusted local run. Supply those independently when checking a saved or transported bundle in a fresh process.

```sh
python3 -B lib/python/jvmcontract_lrat.py --check \
    "$L/lrat/request.json" "$L/lrat/boundary.json" "$L/lrat/evidence.zip"
```

Here `L` is the directory containing the ordinary `result.json`. The generator and checker may be supplied with `KERNEL_CADICAL` and `KERNEL_CAKE`. Their executable digests are pinned. The transcript captures what the encoder sent to the solver. The Java semantics, harness, path exploration, constant folding, launcher and observation of that boundary are still trusted. The qualification job exercises missing evidence, a duplicate that preserves the count, exchanged formulas and assumption units, exchanged well-formed proofs, and a bundle presented for another request. [Qualification driver](verdict_qualification.py)

## Managed ordinary executions on 2026-11-24

The five requests accounted for 38 SAT assignments and 33 independently checked UNSAT proofs. The four registered example tasks filtered the external transcript-directory setting in their ordinary runs. Their explicit certification runs retained every native pass. Both jobs used native binary `64034b325724d66d46c984b8090ab3691f85fb99f93bae9c6c358d26046121b0` from library tree `0e38af39be296e9cd072b741fbf3a91f90f2e6e8`. [Core job](../../../verification/results/2026/11/24/20261124-043118-certify-the-ordinary-guava-verdict-and-h/result.json) · [Extension job](../../../verification/results/2026/11/24/20261124-043118-check-jackson-and-utf-16-ordinary-sat-ev/result.json)

| Ordinary request | Disposition | Native attempts by pass | Ordinary s | Certified s | Generation s | Fresh check s | Bundle bytes |
|---|---|---|---:|---:|---:|---:|---:|
| `336/first-8-release` | established | 1-proof 16 SAT, 8 UNSAT / 2-probe 2 SAT | 1.539 | 1.656 | 0.065 | 0.116 | 54,815 |
| `held/prefix-sums` | established | 1-proof 8 SAT, 10 UNSAT | 0.030 | 0.216 | 0.058 | 0.122 | 55,804 |
| `393/conversion-equivalence-classified` | established | 1-proof 7 SAT, 12 UNSAT | 2.285 | 2.875 | 0.386 | 0.404 | 532,559 |
| `393/node-checks-same` | refuted | 1-proof 5 SAT, 3 UNSAT | 2.337 | 2.991 | 0.094 | 0.151 | 112,627 |
| `395/exact-order-same-reference` | established | 1-proof zero calls | 2.313 | 3.845 | 0.002 | 0.071 | 2,662 |

Each wall time covers one end-to-end execution on the managed host. The certified time includes generation and the first fresh check. Bundle bytes count the compressed clause streams, SAT valuations, LRAT proofs and event manifest. The qualification driver's additional fresh replay and independent Guava reconstruction fall outside the Guava wall time. [Core measurements](../../../verification/trusted-kernel-recovery/lrat/core/summary.json) · [Extension measurements](../../../verification/trusted-kernel-recovery/lrat/extensions/summary.json)

For Guava, a second observer reconstructed the request from the pre-certification claim and actual launch journal. It reconciled the proof and reachability passes with their native logs before reading the bundle. The fresh verifier checked both passes against that independently retained boundary. Removing the proof for event 2, replacing event 2 with a duplicate of event 5, exchanging formula and assumption units, and exchanging valid proof files all withheld assurance at `1-proof/2`. Submitting the valid Guava bundle under the prefix-sums request failed the request binding. [Independent recheck](../../../verification/trusted-kernel-recovery/lrat/core/independent-guava/recheck.json) · [Native origin](../../../verification/trusted-kernel-recovery/lrat/core/independent-guava/native-origin.tar.gz)

Jackson's classifier covers `[2⁵⁴, 2⁵⁵)`. Each of the 8,388,608 midpoint bins has two parity-selected disagreements, giving 16,777,216 values. The ordinary refutation first withheld assurance because its recorded `NodeChecks#same` selector omitted the method descriptor and its existing witness had run in the interpreter. The fresh JVM replay resolved the unique `(J)Z` declaration from the original class and used the checker's ordered classpath. On input `18014401730707454L`, the method returned `false` normally. [First withheld result](../../../verification/results/2026/11/24/20261124-035004-check-whole-verdict-lrat-on-the-complete/result.json) · [Replayed Jackson witness](../../../verification/trusted-kernel-recovery/lrat/extensions/node-checks-same/boundary.json)

The UTF-16 case calls `ObjectUtils.compare(a, a)` and checks that `Ordering.natural().min(a, a)` returns `a`, for non-null strings of up to two code units. Symbolic execution decided the same-reference path with zero solver calls. The ordinary harness admitted every input in its domain and required no reachability pass. The boundary accounts for that execution with zero LRAT proofs. [UTF-16 ordinary receipt](../../../verification/trusted-kernel-recovery/lrat/extensions/exact-order-same-reference/ordinary.json) · [UTF-16 assurance](../../../verification/trusted-kernel-recovery/lrat/extensions/exact-order-same-reference/assurance.json)

Regenerate the table from the completed receipts with the following command.

```sh
python3 -B lib/benchmark/trusted-kernel/verdict_qualification.py --report --output verification/trusted-kernel-recovery/lrat
```
