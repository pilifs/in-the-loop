# Review: where investing in CBMC/JBMC would pay

An outside review, from a ChatGPT conversation the user shared on 2026-11-05 (https://chatgpt.com/s/t_6aed182695088191b92b530db2340e12). It read the repository at git commit `c4fa2f64` and CBMC/JBMC at commit `8e018d0c0ef67`. It is the input of [`sound-verdicts.md`](sound-verdicts.md), kept here as it was given (citation markers removed). Leave it as it is: corrections go in the brief's commit messages.

---

**There are good reasons to maintain a small downstream JBMC branch. The strongest are control over Java semantics and library models, followed by several concrete improvements to arithmetic and array encoding.** I would keep that branch close to upstream initially. Owning the entire shared verification engine would be a much larger commitment than JBMC’s small executable driver suggests.

Your maintenance concern is substantially justified for the **Java-specific implementation and models**. The shared CBMC engine remains actively maintained.

I inspected CBMC/JBMC at commit [`8e018d0c0ef67`](https://github.com/diffblue/cbmc/tree/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3), alongside your adapter at `in-the-loop` commit `c4fa2f647726`. The findings below are from source inspection and current maintenance records. **I did not run new performance benchmarks**, so the rankings reflect expected value and engineering scope, rather than measured speedups.

## 1. How much maintenance risk are you actually taking on?

There are three distinct dependencies here:

| Layer | What I found | Assessment |
|---|---|---|
| **Shared CBMC engine** | Recent releases, current development, substantial solver and encoding infrastructure | Active, large, and expensive to take over completely |
| **JBMC Java frontend** | Very little Java implementation activity over the last year | Your concern about limited Java-specific investment is supported |
| **Java library models** | Old submodule pin, uneven updates, concrete model defects | The clearest layer to bring under your own control |

CBMC’s latest release is **6.11.0, published August 21, 2026**. A JBMC competition artifact was published on **October 25, 2026**, and explicitly identifies its engine as the same one used by CBMC. That is meaningful evidence of continuing upkeep.

However, GitHub’s default-branch history for **`jbmc/src` over the preceding year contains only five commits**. Their subjects concern documentation, diagnostic quoting, and shared C++ representation changes. The wider `jbmc/` tree has 28 commits, including useful build and test maintenance. These counts exclude improvements inherited from shared `src/`, but they support a narrower conclusion: **public Java-specific feature and implementation development is thin**. [Implementation history](https://api.github.com/repos/diffblue/cbmc/commits?path=jbmc/src&since=2025-11-05T00%3A00%3A00Z&per_page=100), [whole JBMC tree history](https://api.github.com/repos/diffblue/cbmc/commits?path=jbmc&since=2025-11-05T00%3A00%3A00Z&per_page=100).

“Tiny” needs qualification. My source count found:

- **1,256 physical C++/header lines** in the JBMC executable driver.
- **36,111 lines** in the Java bytecode frontend.
- Roughly **400,000 lines** across the shared `src` tree, although not all are needed by JBMC.

These counts include comments and blank lines. The [JBMC build target](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/jbmc/src/jbmc/CMakeLists.txt) links substantial symbolic execution, solver, pointer analysis, instrumentation, and utility components.

One particularly relevant maintenance gap: the dedicated upstream **performance and profiling workflows build with `WITH_JBMC=OFF`**. JBMC does have correctness tests in other workflows, but the shared engine’s performance infrastructure does not provide Java end-to-end performance regression coverage. That is something you would want to own even without a fork. [Performance workflow](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/.github/workflows/performance.yaml), [profiling workflow](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/.github/workflows/profiling.yaml).

## 2. My ranking of the opportunities

This ranks **value for your regression-verification workload**, accounting for implementation effort and dependency risk.

| Priority | Area to improve | Expected benefit | Scope |
|---|---|---|---|
| **P0** | Reject unsupported Java semantics; control models and intrinsics | Confidence in successful results; predictable supported subset | Small initial patches, ongoing model work |
| **1** | Share arithmetic encodings and eliminate unnecessary circuitry | Strong potential for integer and long equivalence checks | Several focused backend patches |
| **2** | Improve array representation and constraint generation | Strong potential for your array-heavy memory failures | Medium to substantial |
| **3** | Reuse symbolic prefixes and solvers between paths | Better branch-heavy performance and memory use | Substantial engine work |
| **4** | Reuse compiled models across queries | Better throughput for many checks against the same classes | Medium to substantial API work |
| **5** | Add stronger relational simplification and summaries | Potentially very high for old-versus-new comparisons | Substantial, workload-specific work |
| **6** | Bound trace output and repair option/API inconsistencies | Better operational reliability and fewer pathological costs | Mostly small patches |

There is also useful work in your adapter that requires **no upstream fork**, particularly eliminating redundant stages and improving budgeting and structured output. I cover that below.

## 3. The strongest performance patch candidates

### 3.1 Arithmetic encoding contains concrete avoidable work

This is where I would start backend experiments. There are identifiable inefficiencies small enough to change and evaluate independently.

#### Division and remainder are computed separately

The division encoder calls the underlying divider to obtain **both quotient and remainder**, then returns the quotient. The remainder encoder calls the divider again to obtain **both**, then returns the remainder.

The underlying unsigned divider introduces fresh quotient and remainder variables and constrains their relationship using multiplication, addition, and comparisons. Consequently, code using both `a / b` and `a % b` can pay for two representations of essentially the same division relation. [Division encoder](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/solvers/flattening/boolbv_div.cpp), [remainder encoder](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/solvers/flattening/boolbv_mod.cpp), [divider implementation](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/solvers/flattening/bv_utils.cpp#L1223-L1259).

**Candidate patch:** cache the pair:

```text
(dividend, divisor, width, signedness) → (quotient, remainder)
```

Both operations then use the appropriate projection.

This is particularly relevant to your checks involving identities such as:

```java
(a / b) * b == a - a % b
```

It reduces duplicated encoding and explicitly connects computations the solver would otherwise have to relate. The patch must preserve Java’s zero-divisor exception behavior and `MIN_VALUE / -1` semantics.

**My assessment:** probably the best first performance patch—localized, directly relevant, and straightforward to measure.

#### Signed modular multiplication builds unnecessary sign circuitry

The signed multiplier:

1. Conditionally negates each operand.
2. Performs unsigned multiplication.
3. Computes the result sign.
4. Conditionally negates the result.

That implementation is selected for ordinary signed bitvector multiplication. [Multiplication dispatch](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/solvers/flattening/boolbv_mult.cpp#L58-L76), [signed multiplier](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/solvers/flattening/bv_utils.cpp#L1014-L1029).

For Java’s ordinary wrapping `int` and `long` multiplication, the low \(w\) bits of the product are identical under signed and unsigned interpretation. Therefore, that sign-handling machinery is unnecessary for this particular operation.

**Candidate patch:** use the unsigned multiplier directly for same-width modular integer multiplication. Keep overflow predicates, widened multiplication, fixed point, and floating point on their appropriate paths.

Fewer gates do not guarantee faster SAT solving on every instance, but this is a clean optimization hypothesis with a simple semantic justification.

#### There is expression caching, but less sharing at the Boolean gate level

CBMC already caches conversion of expressions. It would be inaccurate to say it has no common-subexpression reuse.

However, the ordinary CNF implementations of AND, OR, XOR, and conditional selection perform some local simplifications and then create fresh variables and clauses. They do not provide a general canonical cache for repeated equivalent gates on that path. [Expression conversion cache](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/solvers/flattening/boolbv.cpp#L37-L81), [CNF gate construction](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/solvers/sat/cnf.cpp#L263-L376).

**Candidate patch:** structural hashing of Boolean gates, especially where differently shaped source expressions lower to identical circuitry. Measure the cache’s own memory and CPU costs; this is less obviously beneficial than quotient/remainder sharing.

#### Arithmetic refinement becomes eager quickly

`--refine-arithmetic` already exists. For integer multiplication, division, and remainder, though, the implementation adds the full operation encoding after encountering the first inconsistent abstract result. It is therefore a fairly coarse abstraction strategy. [Integer refinement implementation](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/solvers/refinement/refine_arithmetic.cpp#L280-L338).

A more ambitious improvement would add useful word-level identities or selected constraints before expanding the entire operation. That is a plausible extension of the approach in your native engine, but I would do the simpler sharing patches first.

### 3.2 Array encoding has two expensive regimes

This is my strongest candidate for explaining some of your memory problems, although profiling is needed to identify which regime dominates each example.

#### Flattened arrays make symbolic writes expensive

For a finite flattened array, a symbolic write iterates over every element and every bit of that element, selecting either the new value or the old value.

For \(U\) symbolic updates to an \(N\)-element array of \(w\)-bit values, that layer can perform roughly:

\[
O(U N w)
\]

selection work before later simplification. This is a source-derived construction cost, not a runtime prediction. [Symbolic array update implementation](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/solvers/flattening/boolbv_with.cpp#L135-L170).

An equivalence harness can amplify this: it copies arrays, executes both versions, retains successive array states, and compares the results. Small Java methods can consequently generate large formulas.

#### The alternative array encoding constructs quadratic consistency relationships

The array-theory encoding considers pairs of indices to enforce relationships of the form:

\[
i=j \Rightarrow A[i]=A[j].
\]

Its implementation explicitly uses a nested loop over the index set. Even with lazy array constraints, the pair enumeration and conversion of index equalities happen before constraints are queued. [Array consistency construction](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/solvers/flattening/arrays.cpp#L340-L392).

Thus “use array refinement” does not automatically remove all quadratic construction costs.

**What I would investigate:**

- Select representations using read/write counts and index ranges, rather than primarily size thresholds.
- Generate consistency constraints only when an inconsistent candidate model demonstrates they are needed.
- Preserve sparse or persistent update chains longer.
- Specialize fresh, bounded, nonaliasing primitive arrays—the subset your harnesses commonly use.
- Exploit corresponding old/new arrays during relational checking.

There are already useful controls: `--refine-arrays`, `--arrays-uf-always`, `--arrays-uf-never`, and array field-sensitivity options. They should be benchmarked before implementing a new representation.

Also, JBMC already uses a fixed-size backing allocation when an upper bound is available to avoid some variable-length-array costs. A proposal to “add bounded arrays” would duplicate existing work. [Java array allocation lowering](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/jbmc/src/java_bytecode/remove_java_new.cpp#L243-L252).

Your recorded UTF-8 example—native completion at bound eight while the historical JBMC run exhausted its memory allowance—is a good regression case for this investigation. It is evidence of a workload worth optimizing, rather than evidence that one particular encoding change will fix it. [Your example 142](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/examples/142-an-ascii-fast-path-for-the-constant-pool-encoder-proved-equal-to-the-previous-version-at-bound-eight/README.md).

### 3.3 Path exploration does not reuse as much work as it could

JBMC offers both merged symbolic execution and `--paths`, so adding path-by-path execution would not itself be new.

The weakness is how the existing modes manage work.

The default merged mode generates the equation before preparing the solver. This can create a large peak of symbolic state and SSA data, followed by the solver representation. [Merged checker](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/goto-checker/multi_path_symex_checker.cpp#L52-L74).

In path mode:

- Saved paths own copies of their equation and symbolic state.
- Each path ready for solving gets a new property decider.
- That decider constructs a new solver.

Expressions can share internal storage, so this is not necessarily a recursive deep copy of every expression. Nevertheless, the copied prefixes and solver reconstruction are explicit. [Path storage](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/goto-symex/path_storage.h#L40-L54), [per-path decider construction](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/goto-checker/single_path_symex_checker.cpp#L56-L72), [solver construction](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/goto-checker/goto_symex_property_decider.cpp#L19-L31).

A stronger design would combine persistent symbolic prefixes, incremental solver assumptions, retained learned clauses, selective feasibility checks, and selective merging.

**This could be a substantial improvement for your workload. It is also a substantial engine project.** Unmerged path counts can grow exponentially; aggressive merging can produce difficult formulas. Your own experiments already illustrate that tradeoff. The useful improvement is a better policy and better reuse between states.

### 3.4 Repeated-query throughput is poorly served by the current library boundary

Your use case often asks many related questions about nearly identical classes. A compiler-style batch pipeline loses opportunities to reuse parsing, class resolution, lowering, and instrumentation.

JBMC already caches classes within a load and defaults to loading apparently reachable methods. It also has `--symex-driven-lazy-loading`, which delays method conversion until execution reaches it. Therefore, “JBMC loads everything” would be an inaccurate diagnosis. [Class loader](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/jbmc/src/java_bytecode/java_class_loader.cpp#L30-L76), [lazy-loading options](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/jbmc/src/jbmc/jbmc_parse_options.cpp#L339-L352).

The cross-query boundary is much weaker:

- The C++ API initializes C language support and uses global configuration.
- The Rust API explicitly documents that it is not thread-safe.
- The Java frontend requires an initially empty symbol table because loading into existing frontend state is not generally supported.

Sources: [C++ API implementation](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/libcprover-cpp/api.cpp), [Rust API limitations](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/libcprover-rust/readme.md), [Java symbol-table invariant](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/jbmc/src/java_bytecode/java_bytecode_language.cpp#L799-L808).

**Candidate architecture:** an immutable compiled Java model, with isolated state for each query, served by a pool of worker processes.

That offers a controlled route to reuse without first making the whole codebase thread-safe. Cache identity must include classpath contents and order, models, engine version, and relevant semantic options.

JBMC accepts GOTO binaries through `--gb`, but I did not find a ready-made Java export workflow that makes “compile once, query repeatedly” turnkey. In particular, `--outfile` is not automatically a Java compiled-model cache.

### 3.5 Your relational workload deserves its own optimization layer

Checking that two versions agree creates opportunities a general program checker cannot infer cheaply from every harness.

For example, unchanged pure helpers may appear twice under different names. Equivalent arithmetic can have different syntax. Arrays may correspond exactly despite having separate identities in the harness. Ordinary expression caching does not automatically discover those relationships.

Your existing shared-callee mechanism is therefore a useful direction to develop. [Your shared-callee implementation](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/shared.rs).

I would consider:

- Aligning corresponding computations before bit blasting.
- Reusing verified summaries of unchanged helpers.
- Sharing established arithmetic relationships between versions.
- Separating independent output obligations while preserving common setup.

These optimizations may yield more than broad C++ cleanup. Their difficulty is semantic: summaries must account for exceptions, heap mutation, aliasing, and the model assumptions under which they were proved.

### 3.6 Output and option handling contain smaller, worthwhile defects

Two findings are especially concrete.

**Trace rendering can explode after solving has already succeeded in finding a bug.** An open JBMC 6.11 report describes a counterexample trace printing **4,194,304 unknown character entries** for a nondeterministic string. This is an upstream report, not a reproduction I ran. Bounded, sparse trace presentation is a reasonable small patch. [Issue #9165](https://github.com/diffblue/cbmc/issues/9165).

**`--incremental-loop` is advertised but not wired into JBMC’s checker selection in the inspected source.** JBMC inherits the option declaration, but its driver selects only Java single-path or multi-path checkers. CBMC’s driver separately parses and dispatches the incremental-loop mode. [Shared option declarations](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/goto-checker/bmc_util.h#L186-L189), [JBMC dispatch](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/jbmc/src/jbmc/jbmc_parse_options.cpp#L533-L587), [CBMC incremental dispatch](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/cbmc/cbmc_parse_options.cpp#L719-L731).

An execution regression should confirm the externally observed behavior before filing a bug, but the source-level wiring gap is clear. A downstream branch could either implement the mode properly or reject those options explicitly.

## 4. The implementation weakness I would address before performance

**Some unsupported Java behavior is replaced by simplified behavior that is not a general conservative model of the missing operation.**

That matters to dependency risk because it can affect successful verification results.

### Missing methods can lose side effects and exceptions

JBMC generates simple bodies for unavailable Java methods. Ordinary nonvoid methods get nondeterministic return values; ordinary `void` methods get an empty instruction block. These ordinary-method stubs do not generally model arbitrary receiver mutation, argument-array mutation, static mutation, or exceptions. Constructors receive different treatment. [Stub dispatch](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/jbmc/src/jbmc/jbmc_parse_options.cpp#L918-L954), [stub construction](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/jbmc/src/java_bytecode/simple_method_stubbing.cpp#L144-L247).

An arbitrary return value can create false counterexamples. An omitted mutator can instead omit the behavior that would falsify a property. Replaying counterexamples does not protect successful results from that problem.

### Unknown dynamic calls can become zero or null

When an `invokedynamic` operation has not produced the expected synthetic lambda class, the converter falls back to a zero-initialized result—null for references. [Dynamic-call fallback](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/jbmc/src/java_bytecode/java_bytecode_convert_method.cpp#L3089-L3117).

That is a significant concern when expanding support for modern Java or other JVM languages. Accepting the classfile version is not enough to establish support for the bootstrap operations it contains.

These are source-confirmed behaviors; I have not reproduced an end-to-end false-success verdict here.

**My first fork feature would be strict semantic acceptance:** reject reachable missing bodies, unapproved stubs, and unsupported bootstrap operations. Allow abstractions only when they have explicit contracts appropriate to the proof.

### String reasoning is coupled to problematic Character replacements

Your decision to disable string refinement has a concrete basis. The Character intrinsic implementation for `forDigit` ignores the radix and uses `digit <= 10` for its numeric branch. Evaluating that expression at `(10, 16)` produces `':'`; Java specifies `'a'`. [JBMC implementation](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/jbmc/src/java_bytecode/character_refine_preprocess.cpp#L220-L238).

Enabling string refinement initializes these conversions, so choosing a solver strategy also changes which library implementations are used. [Conversion-table initialization](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/jbmc/src/java_bytecode/java_string_library_preprocess.cpp#L1520-L1522).

A useful fork would separate:

- String decision-procedure selection.
- Per-method intrinsic replacement.
- Explicit model overrides and their precedence.

That would let you retain string reasoning while controlling the Java semantics you trust.

### The model bundle needs independent ownership

The current CBMC tree pins `java-models-library` to an **October 2022 revision**. The models repository has newer work, but that does not mean the pinned bundle includes it. [Pinned models tree](https://github.com/diffblue/java-models-library/tree/c7835345cf635279cf59f4a286c05538f8026bd8).

A concrete defect survives in both that revision and current models master: the `Integer.getInteger(String, Integer)` model calls itself unconditionally. [Pinned implementation](https://github.com/diffblue/java-models-library/blob/c7835345cf635279cf59f4a286c05538f8026bd8/src/main/java/java/lang/Integer.java#L873-L875), [reported defect](https://github.com/diffblue/cbmc/issues/9168).

Your configuration extracts real bytecode for selected JDK classes, including `Integer`, so this particular defect is evidence about upstream model quality—not a demonstrated defect in your current configuration. It reinforces the need to pin and test the exact model bundle you actually use. [Your model strategy](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/models/README.md).

## 5. Improvements available in your adapter without a fork

### Remove stages that do not change the proof domain

Your adapter runs:

```text
[0:20] → [-100000:100000] → unrestricted
```

Each stage launches a fresh JBMC invocation. [Stage definition and execution](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/equivalence.rs).

But `--java-assume-inputs-interval` does not constrain primitive-array contents. For a fully modeled array-only harness, such as the intended UTF-8 check, successful runs can repeat the same-domain proof three times.

I would skip interval staging when it cannot change the domain. For scalar inputs, retain it only when its early bug-finding benefit justifies the repeated work.

**This will not fix a run that exhausts memory during its first stage.** It does remove avoidable work from successful checks.

### Give the whole check a deadline

Each stage currently receives the full configured timeout. Native fallback and other retries can extend the overall duration further. I would allocate one whole-check deadline, with explicit budgets for preliminary searches and fallback. [Equivalence execution](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/equivalence.rs#L559-L607), [property execution](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/property.rs#L278-L323).

### Make solver identity part of the result

You already request CaDiCaL by default, which is an important distinction from older or default-MiniSAT comparisons. Upstream currently supports CaDiCaL 3.0.0; replacing an allegedly obsolete SAT solver is not a compelling fork justification by itself. [Your solver selection](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/jbmc.rs#L33-L38), [upstream solver build configuration](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/solvers/CMakeLists.txt#L120-L142).

Record the solver actually selected, its version, and fallback behavior. Historical performance comparisons should be rerun with equivalent solver configurations before using them to justify engine changes.

### Use structured results and preserve phase information

Your parser currently consumes human-oriented text. JBMC already supports `--json-ui`, including structured property results and traces. Moving to that interface should reduce parsing fragility without requiring a fork. [Your parser](https://github.com/pilifs/in-the-loop/blob/c4fa2f64772620aba88181aa2b7c1cfe898e44e2/lib/src/jbmc.rs), [upstream result serialization](https://github.com/diffblue/cbmc/blob/8e018d0c0ef6767172dbbeaa7dcf4abe51c9eda3/src/goto-checker/report_util.cpp#L346-L417).

Keep unsupported input, unwinding failure, timeout, memory exhaustion, solver failure, and counterexample distinct. Those distinctions determine which optimization or fallback is appropriate.

## 6. What I would actually fork

I would start with a maintained patch queue containing four separable changes:

1. **Strict Java mode:** reject missing bodies and unsupported dynamic semantics unless an approved abstraction applies.
2. **Explicit model selection:** separate string solving from Character/JDK replacements, and record the model bundle used.
3. **Shared quotient/remainder encoding.**
4. **Simpler same-width modular multiplication.**

Alongside that, I would fix the adapter’s redundant stages, overall deadline, and structured result handling.

Then I would build a performance corpus around your actual cases: scalar arithmetic, division/remainder identities, binary search, UTF-8 encoding, mutation of bounded arrays, and small object/record examples. Compare both successful proofs and counterexamples, with the same harnesses, bounds, models, exception behavior, and solver.

The measurements should separate:

| Phase | What it tells you |
|---|---|
| Class loading and lowering | Whether compiled-model reuse or better lazy loading will help |
| Symbolic execution | Whether state representation, branching, or merging dominates |
| Solver encoding | Whether arithmetic circuits or array constraints dominate |
| Solving | Whether the remaining problem is primarily SAT/SMT search |
| Trace extraction and output | Whether result handling is consuming the budget |
| Peak memory, SSA size, variables and clauses | Whether a change actually reduces the representation |

Only then would I commit to persistent path solvers or a new array representation.

For dependency management, I would make **JBMC an optional, versioned backend behind an interface you own**, with explicit semantic coverage and proof assumptions. Your native engine can take responsibility for a well-defined subset as its correctness boundary matures; JBMC can remain useful for broader coverage and differential checks.

**My preferred direction is a small JBMC fork for strict semantics, model control, and focused encoding improvements, while continuing to develop your native engine for your specialized workload.** The arithmetic patches offer a practical first performance experiment. Arrays and path reuse offer the larger potential gains. Taking over the whole CBMC engine would require stronger evidence that those gains cannot be obtained through isolated patches.

---

If you want, I can:

- Continue with detailed performance patch suggestions
- Expand on semantic acceptance and correctness improvements
- Describe next steps for integrating a Java model cache
