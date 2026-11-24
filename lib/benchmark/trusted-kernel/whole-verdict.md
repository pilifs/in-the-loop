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
