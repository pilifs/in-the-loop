# Verifying Java below the source: approaches

Status: brainstorm / research plan. Each approach names the tools that
[`setup/ubuntu-wsl/install.sh`](../setup/ubuntu-wsl/install.sh) installs for it.

## Starting point

Anthropic and Theorem ([LLM-assisted formal verification at scale](https://www.anthropic.com/research/formal-verification),
Oct 2026) proved that 239 OSS-Fuzz entry points in 123 libraries never crash on any input under 64 MB.
They did not verify source code. They verified **compiled RISC-V binaries** against a Rocq model
of a Linux process ([theorem-labs/rocq-linux-process-semantics](https://github.com/theorem-labs/rocq-linux-process-semantics)).
Claude wrote the proofs, and the Rocq kernel checked them. The pipeline:

1. Take an existing fuzz target, an entry point where any crash is a bug.
2. Compile it to a static riscv64 binary.
3. Generate the statement from three parts: the binary, the ISA and OS semantics, and "halts with status 0 or 2".
4. An agent writes the proof. When a proof is blocked by a real bug, the agent patches the code and the statement is regenerated.

Three properties of that design are worth copying for the JVM:

- **The fuzz harness is the spec.** No one writes a spec by hand. "This test never fails, on all inputs" is the theorem.
- **The artifact you ship is what you prove.** Verifying a binary sidesteps trust in the compiler. The trusted base is the semantics, the kernel checker, and the hardware.
- **Proofs about shared code are reusable.** Runtime and library code shared across targets is proven once and reused, the way Mathlib is.

[OSS Verify](https://github.com/theorem-labs/oss-verify) already accepts `language: jvm`. It supports
halts statements only, and notes that "JVM binaries are not byte-reproducible yet". How it turns a JVM target into a
riscv64 binary is not documented publicly. That open question shapes several approaches below.

## What "crash" means for Java

Memory safety is mostly given on the JVM, so a Java statement must say something else. Candidates, weakest first:

| Statement | Meaning for `fuzzerTestOneInput(byte[])` (Jazzer) |
|---|---|
| **Halts** | Terminates within a fuel or step budget on every input below N bytes |
| **No uncaught throwable** | No `RuntimeException` or `Error` escapes, so no NPE, AIOOBE, CCE, ArithmeticException, or `AssertionError` from `assert`/`abort` |
| **No resource blowup** | Heap and stack stay within budget, so no `OutOfMemoryError` or `StackOverflowError` |
| **Functional** | Output agrees with a reference model, such as RFC conformance in the zlib case study, or a Cryptol or Lean spec |
| **Protocol** | Each node's handler refines an action of a TLA+ or P spec (see level D) |

## Level A: source (baseline for comparison)

| Approach | Tools |
|---|---|
| JML contracts proved deductively | KeY (installed). OpenJML has no ARM64 build. |
| Write in Dafny, verify, compile to Java | Dafny |
| Pluggable type systems (nullness, units, locks) | Checker Framework, as a Gradle dependency |

These are useful as a control group: the same function verified at the source level, then at levels B and C.
That makes it easy to show what each lower level adds, and what it costs.

## Level B: JVM bytecode

### B1. JVM bytecode semantics in a proof assistant (the flagship)

This mirrors the post directly, with Theorem's RISC-V semantics replaced by a **JVM bytecode semantics**:

```
.class --(ASM/SootUp exporter, Gradle task)--> Lean terms --+
JVM semantics (Lean, written with Claude) --------------------+--> theorem: ∀ input < N bytes, no uncaught throwable
Jazzer harness ("this fuzz test always passes") --------------+         proof: Claude; checked by the Lean kernel
```

- **Language: Lean 4.** It installs cleanly on ARM64, and it gives an executable semantics for free, which B2 needs.
  The semantics can also be written in Rocq to share infrastructure with Theorem's process model (`install.sh rocq`).
- **Start small:** int and long arithmetic, arrays, objects, static and virtual calls, exceptions, and `java.lang` stubs.
  Grow the subset as demos need it.
- **Lower trust:** class files are imported by a small, auditable exporter. Lean never trusts `javac`.
- **Language-agnostic:** one bytecode semantics covers Java, Kotlin, Scala and Clojure. Source verifiers cannot.

### B2. Validate the semantics against real JVMs

A proof is only as good as its semantics. The post's answer was empirical:
their Rust Python interpreter matched CPython on 99.95% of 1.7M random programs,
and Claude-written x86 semantics turned up hundreds of errors in the official docs. For the JVM:

- Make the Lean semantics executable, and run it as an interpreter on generated class files.
- Generate class files with ASM, or let **Jazzer** mutate them guided by coverage of the Lean interpreter.
- Compare observable behaviour with HotSpot, OpenJ9 and GraalVM.
  Every disagreement is a bug in the semantics, in a JVM, or in the JVMS text.

### B3. Reuse existing mechanized JVMs

| Model | Notes |
|---|---|
| **Jinja / JinjaThreads** (Isabelle AFP) | Source and bytecode semantics, a verified compiler, and the Java Memory Model. Install with `install.sh isabelle`. |
| **ACL2 M1–M6** (J Moore) | M6 executes real class files. Install with `install.sh acl2`. |

Question for these: is it cheaper to extend one of them than to write B1 from scratch with Claude?

### B4. Bytecode to an intermediate verification language

Lift bytecode to an intermediate representation, and let an existing verifier generate verification conditions:

- `.class` → SootUp Jimple → **Boogie** (the approach of the *ByteBack* research tool) or Why3.
  Boogie and Dafny are installed.
- **SAW** `jvm_verify`: proves that bytecode is equivalent to a Cryptol spec, which suits crypto and codecs.
  SAW only ships x86-64 Linux builds, so on ARM64 it has to run under emulation (qemu binfmt is installed).

### B5. Model checking and bounded checking of bytecode

| Tool | What it checks |
|---|---|
| **JBMC** (installed with CBMC) | Bounded model checking of bytecode for exceptions and assertions, with an SMT backend |
| **Java PathFinder** | Explicit-state model checking of thread interleavings: deadlocks and races. Built per demo. |
| **Lincheck** (Gradle dependency) | Linearizability of concurrent data structures |

These give fast, cheap counterexamples. Run them before attempting a B1 proof.

Finding (October 2026): JBMC 6.11 does not handle Java 21+ bytecode as it ships. It treats the `typeSwitch` invokedynamic of a
pattern `switch` as an unknown value, so it reports spurious failures. It also has no models for `List.of`, `List.copyOf`,
record `equals` or `Math.multiplyExact`. A bytecode pre-pass that lowers `typeSwitch` to `instanceof` chains is a prerequisite.

### B8. Behavioural contracts (POC in [`tools/contracts`](../tools/contracts/README.md))

Treat verification as a contract that changes only when the developer intends it to. For a method, the contract is
the outcome of every input, derived from the bytecode and checked in. The build fails on any drift, and the pull-request
diff of the contract shows reviewers each changed case. The proof has three steps:

1. Purity is proved from bytecode, by a closed-world walk through sealed hierarchies with a small trusted JDK list.
2. The input domain is derived from types: enums, booleans, records and sealed interfaces are finite.
3. Every input is executed.

It runs in `./gradlew check` and emits SARIF for GitHub and SonarQube. On Box Office it caught a refactor that changed
null handling, which the agent that wrote the refactor believed was equivalent. Infinite domains are the next step:
equivalence of old and new bytecode, outside the declared changes, using JBMC (after the pre-pass above) or an SMT solver.

### B6. Proof-carrying bytecode (outside the box)

The JVM's own bytecode verifier is already a proof checker: `StackMapTable` frames are type certificates.
This approach extends that idea:

- Attach a proof certificate as a custom class-file attribute.
- A `-javaagent` or a custom `ClassLoader` checks the certificate at load time,
  and refuses classes that have no proof of "no uncaught NPE".
- Necula's PCC, applied at the JVM loading boundary.

### B7. Per-compile translation validation

Do not verify `javac`. Instead, for each build, prove that each method's bytecode refines its source-level contract
(JML or Dafny) under B1's semantics. Any compiler that targets the JVM, such as `kotlinc`, `scalac` or obfuscators,
is then checked rather than trusted.

## Level C: native code

### C1. GraalVM native-image to an ISA semantics (the closest to the post)

`native-image` compiles a closed world AOT into a single executable with no JIT,
so the result is a fixed artifact you can prove things about, just like the post's binaries.

- **Targets:** `aarch64`, the host. Arm's spec can be turned into proof-assistant definitions via **Sail** (installed).
  Or `riscv64`, to reuse Theorem's Rocq process model directly.
  Whether native-image can target riscv64 still needs checking.
  `gcc-riscv64-linux-gnu` and `qemu-riscv64-static` are installed for running such binaries.
- **Size:** the SubstrateVM runtime (GC, threads, exceptions) adds many megabytes,
  compared with a median of 18K instructions in the post. The Mathlib argument applies:
  prove the runtime once (Serial GC, single thread), then reuse that proof for every target.

### C2. Prove the interpreter, not the program

Compile a JVM, interpreter only (`-Xint`) or a small embedded VM, as a static riscv64 binary.
The statement is then "this VM, running this class file, halts".
This is presumably close to what OSS Verify does for `jvm`.
The cost is huge up front, but the proof covers every program.

### C3. JIT translation validation (outside the box)

Capture the machine code that HotSpot C2 or Graal emits for a hot method
(`-XX:+PrintAssembly` with `hsdis`, or Graal's IGV graphs).
Then prove that it refines that method's bytecode semantics from B1, using the aarch64 Sail semantics.
Each proof is per method and small, and it ties levels B and C together.
Real JIT miscompilations exist, which makes it a compelling demo.

### C4. Binary symbolic execution as a scout

Run **angr** (`install.sh angr`) over a native-image binary to find crashing inputs cheaply, before attempting C1.

## Level D: distributed systems

The subject system is [Box Office](../apps/boxoffice/README.md): concert ticketing as two services over Kafka and MongoDB.
Its README lists the invariants to verify and the known gaps to find.

| Approach | Tools |
|---|---|
| **TLA+ trace validation:** instrument the Java service, and check that recorded traces are behaviours of the spec | TLC, plus a `kind` cluster with fault injection (Chaos Mesh via Helm) to cover partitions and crashes |
| **P with PObserve:** runtime monitoring of Java services against P specs | P compiler (.NET) |
| **Refinement down to bytecode:** prove each message handler's bytecode (B1) refines its TLA+ action, so the TLA+ invariants hold for the shipped code | Lean + TLA+ (ambitious) |

## Cross-cutting: making AI-written proofs trustworthy

The post warns about reward hacking: making a theorem provable by changing the program until it is trivial.
Every demo should guard against this:

- **Freeze statements.** `spec/` and the exporter are hashed. CI fails when an agent's diff touches them.
- **No escape hatches.** Reject `sorry`, `admit`, and new `axiom`s, and audit `#print axioms` for each theorem.
- **Measure patches.** When a fix is needed, prove how few inputs it changes, as the post did.
- **Mine statements** from existing JUnit, jqwik and Jazzer tests, rather than hand-writing them.

## Proposed demo sequence

| # | Demo | Level | Tools |
|---|---|---|---|
| 00 | One small function (ring buffer or varint codec) verified at the source level | A | KeY, Dafny |
| 01 | Tiny JVM semantics in Lean, a class-file exporter, and a proof that the function never throws | B1 | Lean, ASM |
| 02 | Differential testing of the Lean JVM against HotSpot and GraalVM | B2 | Lean, Jazzer |
| 03 | The same function under JBMC; a concurrent queue under JPF and Lincheck | B5 | JBMC, JPF |
| 04 | native-image the function, inspect and scout it with angr, and attempt an aarch64 or riscv64 proof | C1/C4 | GraalVM, Sail, angr |
| 05 | Raft or a lease service on `kind`, with TLA+ trace validation under chaos | D | TLC, kind, Helm |
| 06 | JIT translation validation for one C2-compiled method (stretch goal) | C3 | hsdis, Lean, Sail |

## Open questions

- How does OSS Verify build `jvm` targets? An AOT-compiled binary, or a whole VM?
- Can GraalVM native-image target linux-riscv64 today, and can it produce reproducible bytes?
- Lean or Rocq for B1? Lean favours iteration speed and executability. Rocq allows reuse of Theorem's models.
- How much of `java.lang` must be modelled before real Jazzer targets (such as from OSS-Fuzz Java projects) become tractable?
