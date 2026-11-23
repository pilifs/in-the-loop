# What an acceptance establishes

The external request binds an owner, two method names and descriptors, the original class digest, the theorem and its assumptions. The certificate binds the digest of that request. Its remaining lines are untrusted hints and claimed obligations. The Rust consumer starts at PC 0 of the public method. Its acceptance path reads the supplied bytes once, checks their SHA-256, resolves the class and methods from the constant pool, and interprets their reachable instructions. A class with exception handlers on either selected method, an unrepresented cycle, or a reachable unsupported instruction yields a refusal. The starting assumptions and release digests are in the [frozen protocol](protocol.md).

## Array induction

Let `A` be the array at entry and `n` its Java length. At the supplied loop head the checker establishes that the heap still equals the entry heap, `0 ≤ i ≤ n`, and every cell in `A[0..i)` differs from the target. The public call must pass the original reference and target, zero, and the length obtained from that reference. The constant-pool method reference must resolve to the requested private static helper in that same class.

The checker follows the actual branch offsets for three exhaustive cases.

| State at the loop head | What the bytecode must establish |
|---|---|
| `i = n` | Return −1 with the frame intact. The prefix covers the whole array. |
| `i < n` and `A[i] = target` | Return `i` with the frame intact. The prefix excludes an earlier match. |
| `i < n` and `A[i] ≠ target` | Re-enter at `i + 1` on an empty stack, with the other live locals accounted for and the extended prefix intact. |

An array access requires the non-null admitted root and an in-bounds index. A store back to the current cell may preserve the frame when the value is known equal to its old value. Each return requires a result and a frame obligation keyed separately by method descriptor and PC. Branch edges and induction edges carry their own keys. Since `i < n ≤ Integer.MAX_VALUE`, incrementing on the back edge cannot overflow. The Java-int measure `n − i` is nonnegative and falls by exactly one. The wrapper must return the established helper result.

The long transfer keeps this invariant, the three cases and all index arithmetic. The target occupies slots 1 and 2. The helper's start and end move to slots 3 and 4. A `laload` yields the entire 64-bit cell, and the zero result of `lcmp` means equality of both words. An ordered comparison whose sign the abstraction cannot establish remains unsupported. [JVM instruction semantics](https://docs.oracle.com/javase/specs/jvms/se21/html/jvms-6.html)

When a proof attempt fails, a separate concrete interpreter can reproduce an admitted counterexample starting at the public call. It tracks the entire small input heap, locals, stack and PC. A repeated complete state within a deterministic invocation establishes a cycle. Exhausting the replay budget supplies no witness. The JVM driver records the identity of the class it loaded, the result and the array after return. For the no-progress mutant it records entry followed by a timeout. The repeated-state check supplies the termination evidence.

## Trusted dependencies

| Route | Dependencies of the measured result |
|---|---|
| Rust | The independent class reader, request and edge matching, instruction transfer rules, prefix induction, the shared SHA-256 implementation, Rust compilation and runtime, and the stated correspondence to verified JVM execution. The witness interpreter is also trusted for refutations. The released class bytes are the input. The Python rule, hints issuer, `javap`, Z3, previous verdicts and proof cache are outside the isolated acceptance process. |
| Lean | Lean 4.36.0, its kernel and standard library, the file-to-literal elaborator, the external request adapter, the restricted class decoder and the correspondence of the stack evaluator to the scalar JVM instructions. The proof term checks modular arithmetic over `BitVec 32` and preservation of an arbitrary heap. The byte reader obtains the entire 256-byte file inside the clean process. The recorded foundations are propositional extensionality, classical choice and quotient soundness. [Lean axioms](https://lean-lang.org/doc/reference/latest/Axioms/) |
| SAT/LRAT | The transcript and its association with the requested workload, extraction of the clause prefix and assumption units, the pinned CakeML checker, and the toolchain in which it was built. CaDiCaL supplies an independently checked proof. Translating JVM behavior to a complete set of correct formulas remains the verifier's responsibility. |

All routes rely on the supplied artifact and platform identities. Success of JVM class initialization is an external precondition. The experiment checks a restricted subset of class files and instructions. The Rust array rules have a reviewable induction argument and executable controls. The Lean kernel proof covers the scalar methods.

## Range-fill extension

The external request `range-fill-frame-v1` selects a public static int-array fill and its package-static range check. For a non-null array and signed Java indices satisfying `0 ≤ from ≤ to ≤ a.length`, it asks for normal termination, the supplied value at every index in `[from,to)`, and the entry value at every other heap location. The checker resolves the call in the actual constant pool, verifies its arguments, and follows each branch of `rangeCheck` that is reachable on this domain. The domain includes empty intervals, an empty array and an upper bound equal to `Integer.MAX_VALUE`. [JDK range-fill contract](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/Arrays.html#fill(int%5B%5D,int,int,int))

At loop entry the written interval `[from,i)` is empty. At the cut point the checker requires `from ≤ i ≤ to`, the fill value throughout that interval and the entry heap everywhere else. When `i < to`, the actual store to `a[i]` extends the prefix. The upper bound proves that incrementing the signed cursor is safe and that `to − i` decreases. When `i == to`, the invariant gives the exact frame at the void return. The checker verifies the operand stack and other live locals at the back edge. Unsupported reachable instructions, an ambiguous guard or an unrepresented cycle stop the proof. [JVM store semantics](https://docs.oracle.com/javase/specs/jvms/se21/html/jvms-6.html#jvms-6.5.iastore)

The caller request `range-fill-caller-frame-observation-v1` adds a non-null `other`, `0 ≤ k < other.length`, and a `callee` line binding the defining class and digest. Both classes are assumed initialized and verified under the stated JVM environment, with the bound callee accessible under module resolution. The checker proves the fill in the same invocation before applying its frame at the actual static call. It checks the observation and full write frame for shared roots with `k` inside or outside the interval, and for distinct roots of independently legal lengths. For shared roots inside the interval the result is the fill value. In the other cases it is the entry value of `other[k]`.

The same caller interpreter can run concrete controls from method entry with the proved callee semantics. A completed execution that changes the wrong cell, returns the wrong value or reaches a checked bounds exception refutes the combined theorem. Ordinary JVM observations provide a second comparison. The Rust class reader, bytecode rules, induction argument and correspondence with the JVM remain trusted. The release JDK supplies the pinned bytes for replay. The checking process reads only those bytes, its executable and the supplied request and certificate.
