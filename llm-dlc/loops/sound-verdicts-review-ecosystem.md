# Review: jvmcontract against the Java verification ecosystem

An outside review, from a ChatGPT conversation the user shared on 2026-11-05 (https://chatgpt.com/s/t_6aed1c35c7808191ae1f94d00c438532). It read the repository at git commit `c4fa2f64` and compared jvmcontract's native engine and workflow with JBMC, KeY, OpenJML, JPF, SAW, ByteBack, VeriFast, Dafny and proof checkers. It is the input of [`sound-verdicts.md`](sound-verdicts.md), kept here as it was given (citation markers removed). Leave it as it is: corrections go in the brief's commit messages.

---

## My assessment

**Your library has a strong specialization in verifying changes to small Java methods, but its native engine is still an early verification implementation—not yet an assurance peer of established tools such as JBMC or KeY.** Its most compelling features are the regression workflow, precise integer reasoning, and readable counterexamples.

The most important finding from this review is that **some unsupported Java behavior is silently approximated rather than rejected**. I found concrete source paths that appear capable of producing `Verified` for false claims. Fixing those would improve my assessment more than adding another optimization or expanding the supported language subset.

### Scope of this review

I reviewed the repository at [`c4fa2f64772620aba88181aa2b7c1cfe898e44e2`](https://github.com/pilifs/in-the-loop/commit/c4fa2f64772620aba88181aa2b7c1cfe898e44e2). In that snapshot, the crate is named **`jvmcontract`**, and its native checker is implemented in `lib/src/bmc`. I did not find a separately named `jvmchecker` package, so I have treated that native engine as your target and assessed the surrounding workflow separately.

This is a **source review supported by the repository’s committed verification results and primary documentation for competing tools**. I did not run fresh benchmarks or execute the potential false-verification reproducers below.

---

## 1. Where I would rank it

These are qualitative engineering assessments, not measured accuracy scores or competition rankings. The scale is **0 = absent, 1 = early, 2 = limited, 3 = useful, 4 = strong, 5 = leading**. I would not average them: assurance weaknesses cannot be offset by good usability.

| Area | Your current position | Relative assessment |
|---|---:|---|
| **Verification directly over compiled bytecode** | **4/5** | A meaningful strength. JBMC, JPF, SAW’s JVM backend, and ByteBack also work at this level; KeY and OpenJML primarily verify source. |
| **Bit-accurate bounded integer reasoning** | **4/5 for the implemented arithmetic design** | Competitive specialization: overflow, signed arithmetic, shifts, division, and exact arithmetic operations. JBMC remains the stronger general reference implementation. |
| **Regression verification workflow** | **4/5 — surrounding library** | One of your strongest areas. Previous-version specifications, scoped changes, parameter mappings, and result relations form a useful developer interface. SAW is an important comparator. |
| **Counterexample presentation** | **4/5 — surrounding library** | Replay and shrinking make results practical to investigate. They provide useful validation of reported failures. |
| **General Java/JDK semantic coverage** | **2/5** | Substantially narrower than established Java verifiers, with additional concerns about enforcing that boundary. |
| **Modular and inductive verification** | **1/5** | Shared-callee reasoning is useful, but there is no general system of proved method summaries, loop invariants, or inductive heap reasoning comparable to KeY, OpenJML, VeriFast, or Dafny. |
| **Concurrent JVM execution** | **0/5 in the native engine** | JPF is the strongest comparator for schedule exploration. The surrounding TLC integration verifies a separate protocol model. |
| **Independently checkable proof certificates** | **0/5 in the inspected native path** | There is no equivalent of a Lean proof term, a checked SMT certificate, or an independently validated SAT unsatisfiability proof. |
| **Assurance maturity** | **1–2/5** | Good testing and conservative handling of several failure modes, but apparent semantic false-success paths require attention. |
| **Overall performance** | **Not defensibly rankable yet** | Some recorded examples show substantial wins over JBMC. That supports specialization, not an overall speed ranking. |

The scores above distinguish the native engine from features supplied by JBMC, TLC, or the surrounding contract tooling. The implementation and integration boundaries are visible in the [native engine](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/bmc/mod.rs), [property driver](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/property.rs), and [library API](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/lib.rs).

**My practical ranking by purpose would be:**

- **Broad bounded verification of existing Java bytecode:** JBMC ahead of your native engine.
- **Deep sequential Java functional correctness:** KeY and OpenJML ahead; VeriFast is particularly relevant for ownership and heap reasoning.
- **Low-friction verification of a method refactor:** your complete workflow belongs in the strongest comparison group, alongside tools such as SAW, although its assurance needs strengthening.
- **Java thread schedules and deadlocks:** JPF ahead.
- **Independent validation of proofs:** foundational kernels and certificate checkers are several architectural steps ahead.

## 2. Comparison with the Java ecosystem

Most tools commonly called “Java proof checkers” are actually **program verifiers**: they translate programs into a reasoning problem and attempt to establish a property. A smaller proof checker that validates the resulting evidence is a separate component.

| Tool | What it verifies | Where it is ahead of your implementation | Important qualification |
|---|---|---|---|
| **JBMC** | Compiled Java bytecode using bounded symbolic reasoning and SAT/SMT | Broader object, array, runtime-exception, and string machinery; a more established implementation and evaluation history | It still needs bounds and environmental models. Its ordinary verdict is not automatically a separately certified proof of the original JVM program. |
| **KeY** | Java source and JML contracts using Java Dynamic Logic | Sequential object-oriented correctness, heap reasoning, contracts, loops, exceptions, and explicit proof structure | It has selective Java coverage. The current KeY 3.0 matrix excludes runtime concurrency, reflection, and dynamic loading. |
| **OpenJML** | Java source with JML specifications, discharged through SMT | Standard specification vocabulary, modular contracts, invariants, frame conditions, and deductive loop reasoning | It relies on its translation and solver; it is not a small independent proof kernel. |
| **Java PathFinder / Symbolic PathFinder** | Java bytecode in an analysis VM, with state exploration and symbolic extensions | Particularly relevant for execution paths, concurrency defects, deadlocks, and exceptional behavior | Exhaustiveness applies to the modeled state space and configuration. This is a different verification style from deductive contracts. |
| **SAW / Crucible JVM** | Bytecode-level functional specifications and equivalence through symbolic execution | Compositional verification: previously proved `JVMSpec`s can be reused when verifying callers | Its JVM documentation explicitly describes JDK 9+ support as experimental and notes unresolved issues with classes such as `String`. Its broader reputation should not be treated as evidence of unrestricted Java support. |
| **ByteBack** | Bytecode translated through Grimp to Boogie, with contracts and loop invariants | A particularly relevant example of deductive verification at the bytecode level | In the published 2024 version, arithmetic uses mathematical integers/reals and can miss overflow; exception handling and `invokedynamic` are unsupported. Your bit-accurate approach has a real advantage on overflow-sensitive problems. |
| **VeriFast** | Annotated source using modular separation-logic reasoning | Ownership, mutable heap structures, modular proofs, and concurrency reasoning | Its Java frontend is selective; the documented grammar describes support for most of Java 1.0, with many newer constructs excluded. |

### Two comparisons matter particularly

**JBMC is your immediate engineering benchmark.** It addresses essentially the same bounded bytecode-verification problem. A useful claim would be that your engine solves a defined class of regression obligations more efficiently, with a smaller implementation and clearer reports. Establishing that claim requires matching the statement, models, bounds, solver configuration, and accepted semantics.

**SAW and ByteBack are important architectural references.** SAW demonstrates reusable method specifications; ByteBack demonstrates that bytecode verification can use invariants and deductive reasoning. Working at bytecode level does not require remaining permanently limited to unwinding.

KeY also deserves credit for evidence that your current engine does not produce: it saves rule applications and replays them when loading proofs, and its proof bundles can include the necessary source and classpath context. That is substantially more explicit than a solver-result log, although it should not be equated automatically with a tiny, separately verified kernel.

## 3. What is already technically strong

### A. You are reasoning about Java machine arithmetic

The native engine implements bit-vectors for Java integral values, rather than treating `int` and `long` as arbitrary mathematical integers. That matters for exactly the kinds of defects your examples target: overflow, negative remainders, shifting, signed comparisons, and arithmetic exceptions.

The implementation also contains substantive optimization work:

- Hashing of gates and expressions so repeated computations share representations.
- Lazy division and multiplication.
- Validation of candidate arithmetic models, followed by refinement when those models disagree with actual machine arithmetic.
- Targeted identities, including rewriting a quotient multiplied by its divisor using the remainder.
- Path merging when compatible states meet.

These are implemented mechanisms, not only roadmap items. The relevant code is in [the bit-vector engine](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/bmc/bits.rs).

The lazy arithmetic design is sensible: begin with an overapproximation, establish a proof if that larger behavior space is already safe, and refine spurious satisfying models. Its assurance depends on every initial constraint and rewrite being valid. Tests against wrapping arithmetic are useful evidence; proving the arithmetic lemmas would be stronger.

### B. The regression interface is well matched to developer work

Your surrounding library can express more than equality between two identically shaped methods:

- A change is permitted on a declared subset of inputs.
- The old method can have a different name or parameter arrangement.
- Arguments to the old version can be expressions over the new inputs.
- Results can be related by a predicate instead of equality.
- Primitive record components can bridge representation changes.
- Array contents after execution can be compared.
- Identical pure callees can be shared across the two versions.

That is a useful set of abstractions for reviewing real refactors. The [harness generator](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/harness/mod.rs) and [shared-callee implementation](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/shared.rs) contain these mechanisms.

I would describe the advantage as **reducing specification work by reusing the previous implementation**. There is still a specification: the previous behavior, the admitted input domain, the permitted-change predicate, and the observations being compared.

For a bug fix, that distinction matters. Proving preservation outside the changed region says nothing by itself about whether the new behavior inside that region is correct.

### C. Several failure modes are handled properly

The core exploration code refuses to call a proof successful when a feasible loop exceeds its unwinding allowance or when required exploration runs out of budget. The JBMC adapter also distinguishes actual verification success from a misleading “zero failed” summary followed by an error.

Those are important correctness decisions. Likewise, reported counterexamples are replayed and shrunk, and the integration suite includes native/JBMC comparisons. See the [native exploration loop](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/bmc/mod.rs#L487), [JBMC result parser](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/jbmc.rs#L217), and [integration tests](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/tests/integration.rs#L1285).

However, counterexample replay protects the **failure-reporting side**. It does not detect a false success caused by omitting behavior.

Also, the replay interpreter and the proof engines share some JDK models. Agreement under a shared model does not independently establish that the model matches the JVM. Your [model documentation](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/models/README.md) is commendably explicit about some of those differences.

### D. There is evidence that specialization pays off

The repository contains encouraging recorded results:

| Example | Recorded native result | Recorded JBMC comparison | What it supports |
|---|---:|---:|---|
| **141: binary-search rewrite** | Approximately **2 seconds**, arrays up to length 8 | Approximately **101 seconds** in the documented comparison | A substantial advantage for that particular relational array obligation |
| **142: modified UTF-8 encoder fast path** | Approximately **6–7 seconds**, input/output arrays up to length 8 | The documentation reports exhaustion of the configured memory allowance at that bound | Path merging makes a meaningful difference on this example |
| **138: window arithmetic rewrite** | Approximately **0.1 seconds** | Earlier direct arithmetic formulations did not finish within a minute | Recognizing an arithmetic identity can dominate solver performance |

Sources: [example 141](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/examples/141-a-lookupswitch-bisection-rewritten-half-open-proved-equal-to-the-closed-form-on-every-sorted-table/README.md), [example 142](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/examples/142-an-ascii-fast-path-for-the-constant-pool-encoder-proved-equal-to-the-previous-version-at-bound-eight/README.md), and [example 138](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/examples/138-a-window-start-computed-as-the-window-s-index-times-its-length-proved-equal-to-the-remainder-form/README.md).

I would use these as **case studies**, not a general benchmark claim. The README also documents examples where JBMC is faster. A fair performance assessment needs pinned revisions and matching semantics; a narrower model can appear faster simply because it omits difficult behavior.

## 4. Findings that materially lower the assurance ranking

### A. Unmodeled constructors and instance methods can be silently approximated

In the native instruction dispatcher, after attempting to resolve an application method:

- An unresolved constructor is skipped.
- An unresolved instance method returning `void` is skipped.
- An unresolved instance method returning an object produces a fresh, non-null opaque object.

This fallback is broader than an explicit list of harmless operations. Constructors can throw, `void` methods can mutate arguments, and reference-returning methods can return `null` or an existing object. See [the instance-call fallback](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/bmc/mod.rs#L1509).

Consider:

```java
public static int capacity(int n) {
    new java.util.ArrayList<Object>(n);
    return 1;
}
```

With `--assert 'result == 1'` and no declared exceptions, your property semantics require normal return with that result. But `ArrayList(int)` throws `IllegalArgumentException` for a negative capacity.

Tracing the native implementation indicates that it skips this constructor and proceeds to return `1` for every `n`. I found no purity or supported-call preflight in the property driver that would reject the example.

**This is a strong candidate for an incorrect `Verified` result, identified by source inspection. I have not executed the reproduction.**

It also affects `--engine auto`: that mode falls back to JBMC when native returns `Unverifiable`; it does **not** ask JBMC to confirm native successes. The relevant acceptance logic is in the [property driver](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/property.rs#L276).

### B. Monitor instructions lose even single-threaded exceptional behavior

The native implementation handles `MonitorEnter` and `MonitorExit` by popping their operands and continuing.

Consider:

```java
public static int nullMonitor(int n) {
    synchronized ((Object) null) {
        return 1;
    }
}
```

On the JVM, entering a monitor through `null` throws `NullPointerException` before executing the body. This is explicitly part of the instruction semantics.

The native source trace instead reaches `return 1`: neither monitor instruction checks for null or refuses synchronization. Again, the property driver appears to accept the method.

This is another **unexecuted but concrete candidate for false verification**, supported by the [monitor handling](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/bmc/mod.rs#L1584).

The issue exists even when no concurrent execution is being analyzed.

### C. Other semantic boundaries need enforcement

I found several additional concerns in the native representation:

| Finding | Why it matters |
|---|---|
| **No class-initialization execution in the native call path** | A method’s body can appear safe while a required initializer throws or performs relevant behavior. An “already initialized” assumption would need to be explicit and justified. |
| **Object fields are keyed by field name** | Java field hiding permits distinct superclass and subclass fields with the same name. A name-only representation can conflate them. |
| **String and class literals become fresh opaque objects** | Reference identity is observable. Opaque values need restrictions on how they can be used, or faithful identity semantics. |

These findings come from the [native execution implementation](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/bmc/mod.rs). They are source-level concerns, not independently reproduced failures.

A restricted verifier does not need to implement every JVM feature. It does need to ensure that **every accepted program stays within the semantics it actually implements**. Restricting parameter types alone does not enforce that: a method accepting only an `int` can still allocate objects, initialize classes, or synchronize.

### D. The equivalence guarantee is narrower than a reader might assume

Several restrictions are legitimate modeling choices, but they need to be prominent in the result:

| Current behavior | Consequence |
|---|---|
| Native array parameters are fresh and non-null | Calls where two parameters reference the same array, or where a parameter is null, are outside that input model. |
| Default array-parameter bound is 8 | The proof covers every admitted value at those lengths, but establishes nothing about longer input arrays. |
| Record construction rejected by either version skips that input | Method equivalence is checked on the common constructible domain; constructor compatibility is a separate obligation. |
| Exceptions are mapped to a fixed set of categories | Two custom exceptions can fall into the same category. Exact exception class, message, and object state are not all compared. |
| Vacuity is reported without changing `Verified` | A mathematically valid implication that covers no inputs can still look like a successful CI result. |

Sources: [native input construction](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/bmc/mod.rs#L420), [record construction and exception comparison](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/harness/mod.rs), and [vacuity handling](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/equivalence.rs#L727).

The actual regression statement is approximately:

\[
\forall x \in D,\quad
A(x)\Rightarrow
\operatorname{Obs}(P_{\mathrm{old}},x)
=
\operatorname{Obs}(P_{\mathrm{new}},x)
\]

Here, **\(D\)** is the modeled domain, **\(A\)** includes assumptions and permitted-change exclusions, and **Obs** is the chosen set of observations. Making those three things explicit would make the tool much easier to assess and trust.

There is an important positive nuance: bounded model checking does not mean sampling small integer values. Your scalar bit-vectors can cover the full `int` or `long` range. Likewise, refusing a feasible unwinding overrun is stronger than silently proving only a truncated execution. The remaining limitations are the modeled domain and semantics, and the absence of inductive reasoning that could remove practical unwinding requirements.

## 5. Comparison with broader verification and proof-checking systems

### Program verifiers: CBMC and Dafny

**CBMC** is the broader family resemblance: bounded execution, precise machine-level reasoning, and solver-backed assertions. Its C/C++ support is not directly transferable to Java, but its maturity and conservative handling of unsupported behavior are useful references. Its current documentation, for example, explicitly states that calls to functions without bodies trigger verification errors by default.

**Dafny** is ahead in a different dimension: reusable specifications, lemmas, induction, loop invariants, and reasoning about unbounded structures. It uses Boogie and SMT in its ordinary verification path. It does not automatically verify arbitrary existing Java bytecode, so your artifact-level integration solves a different problem.

Your native engine is currently closer to the CBMC family. Adding proved summaries and checked invariants would move it toward the deductive capabilities associated with Dafny, KeY, and OpenJML.

### Proof checkers: the assurance ranking is clearer

For **confidence in accepting a proof within a supported logic**, I would use these tiers:

| Assurance tier | Examples | What they provide |
|---|---|---|
| **Foundational or formally justified checking** | Lean, Rocq, Isabelle; certified checkers such as SMTCoq and `cake_lpr` | Proof acceptance is concentrated in a logical kernel or a checker with a soundness theorem. These systems have different assumptions and execution guarantees, so I would not impose a universal ordering within this group. |
| **Independent certificate checking** | Carcara for supported Alethe proofs; other separately executed SAT/SMT checkers | A checker validates evidence produced by the solver, reducing reliance on the solver implementation. The checker and its supported rules still matter. |
| **Verifier and solver trusted together** | Your current native path; many conventional automated verification workflows | The program translation, symbolic execution, optimizations, and solver result are accepted without a separately checked end-to-end derivation. |

Lean documents kernel acceptance and additional validation of assumptions and theorem meaning; Rocq provides a separate compiled-library checker; Isabelle uses a kernel-based inference architecture. None supplies a Java semantics or a correct bytecode translation merely by being present in the pipeline.

SMTCoq checks supported solver witnesses using a certified checker. CakeML’s checker work goes further on execution assurance, with verified compilation of checkers such as `cake_lpr`. Those guarantees concern their formal input problems, such as CNF unsatisfiability.

Carcara is a useful reporting reference too: it distinguishes fully checked proofs from invalid or incomplete proofs, and its documentation makes clear that skipped rules change what was checked.

In your native path, CaDiCaL’s answer is consumed directly, and the persisted result is principally a verdict, witness data, counters, and a log summary. I found no independently validated unsatisfiability certificate. See [solver invocation](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/bmc/bits.rs#L758) and [result persistence](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/bmc/mod.rs#L530).

**Adding a SAT certificate would improve this ranking, but would not resolve the Java-semantic findings above.** A perfectly checked proof can establish that an incorrectly generated Boolean formula is unsatisfiable.

## 6. What I would prioritize next

### 1. Enforce the supported semantic subset

This is the highest priority.

Replace generic constructor and instance-call fallbacks with explicit models or refusal. Reject monitor instructions until their admitted semantics are implemented. Address field identity, literal identity, and class initialization, either through correct models or clearly enforced restrictions.

The regression suite should include small programs that exercise these boundaries and compare behavior with a real JVM. Agreement between your own symbolic executor and interpreter is useful, but an external semantic reference is especially valuable where they share models.

### 2. Make the result state exactly what was established

Every successful result should carry a structured description of:

- Input domains, nullability, and aliasing assumptions.
- Array and execution bounds, including whether unwinding completeness was established.
- Relevant initialization and environmental assumptions.
- The model versions used.
- The observations compared.
- Non-vacuity status.
- Whether the result was independently checked.

I would give vacuity a distinct operational status and distinguish **non-vacuity established**, **vacuous**, and **non-vacuity unknown**. Today, the optional vacuity field and log messages do not give all consumers that distinction cleanly.

This would also prevent a regression proof about common valid record instances from being mistaken for a proof that the constructors accept the same inputs.

### 3. Establish an independent correctness benchmark before a broad speed claim

Use three groups:

1. **Semantic conformance cases:** exceptions, initialization, aliases, field hiding, reference identity, and machine arithmetic.
2. **Real regressions and CVE-related kernels:** known bad and fixed versions, with independently reviewed properties.
3. **Held-out performance cases:** workloads that did not motivate your optimizations.

Report correctness, supported coverage, runtime, and memory separately. An unsupported case is not a successful verification; an incorrectly accepted property should dominate the assessment.

For CVE work, I would require the vulnerable version to produce a validated counterexample and the fixed version to establish the security property under the same relevant assumptions. A regression-equivalence check can then establish preservation outside the intended change. That combination is much more informative than either result alone.

### 4. Add independent checking at the SAT boundary

Your existing bit-vector/CaDiCaL architecture gives you a practical starting point for proof certificates.

The design needs to account for **every UNSAT decision used to prune exploration**, including its assumptions and any incremental refinements. Checking one unrelated final CNF would not validate all of the decisions that led to `Verified`.

A useful proof bundle would bind together the analyzed class bytes, statement, models, configuration, encoded obligations, and certificates. Initially, the symbolic executor and encoding would remain trusted. Later, a separate validator could check more of the translation and path-coverage argument.

That is a manageable sequence of stronger guarantees.

### 5. Add compositional reasoning where it removes real limits

After the semantic boundary is reliable, I would prioritize:

- Reusable, proved method summaries.
- Loop invariants that are checked for initialization and preservation.
- Explicit frame conditions and heap relationships.
- Proof reuse with precise invalidation when code or dependencies change.

This is also a productive role for an LLM: propose invariants, summaries, and auxiliary lemmas, then require the verifier to establish each obligation. The generated suggestion can remain untrusted.

Your current arithmetic and regression machinery is worth developing. **The change that would most improve my ranking today is to ensure that every native `Verified` result stays inside a precisely defined, faithfully implemented Java subset.** After that, independently checkable evidence would turn the project from a useful specialized verifier into a much stronger answer to “how do we trust the proof?”

---

If you want, I can:

- Explore fixes for unsupported Java behavior
- Propose approaches to strengthen assurance maturity
- Outline steps to integrate checked SMT certificates
