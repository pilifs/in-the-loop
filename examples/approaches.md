# Verifying Java below the source: approaches

Status: brainstorm / research plan. Each approach names the tools that
[`setup/ubuntu-wsl/install.sh`](setup/ubuntu-wsl/install.sh) installs for it.

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

Findings (October 2026): JBMC 6.11 does not handle pattern-matching bytecode as it ships. It treats the `typeSwitch`
invokedynamic of a pattern `switch` as an unknown value, so it reports spurious failures, and it has no models for
`List.of`, `List.copyOf` or record `equals`. A bytecode pre-pass that lowers `typeSwitch` to `instanceof` chains is a
prerequisite for state machines like `OrderLifecycle`. Plain arithmetic, branches and exceptions in Java 25 class files
work, and `java.lang.Math` works when its real bytecode is put on JBMC's classpath instead of its models; B9 relies on that.

### B8. Behavioural contracts (POC in [`tools/contracts`](demo/tools/contracts/README.md))

Treat verification as a contract that changes only when the developer intends it to. For a method, the contract is
the outcome of every input, derived from the bytecode and checked in. The build fails on any drift, and the pull-request
diff of the contract shows reviewers each changed case. The proof has three steps:

1. Purity is proved from bytecode, by a closed-world walk through sealed hierarchies with a small trusted JDK list.
2. The input domain is derived from types: enums, booleans, records and sealed interfaces are finite.
3. Every input is executed.

It runs in `./gradlew check` and emits SARIF for GitHub and SonarQube. On Box Office it caught a refactor that changed
null handling, which the agent that wrote the refactor believed was equivalent ([examples 001 to 005](demo/README.md)). On Crosscut
it catches a transaction rollback rule rewritten without its `Error` half ([025](demo/README.md)) and a circuit breaker that closes on
its first good probe ([026](demo/README.md)), each as a one- or two-line diff of the contract. On Mica, a JVM's own kernels, it catches
a type checker that lets an uninitialized object pass as an `Object` ([038](demo/README.md), two of 289 pairs) and an access control
without the receiver rule for `protected` ([039](demo/README.md), one of 120 cases), and shows JEP 181's nestmate access as a four-line
diff ([040](demo/README.md)).

### B9. Regression verification (POC in [`tools/contracts`](demo/tools/contracts/README.md#regression-verification-methods-with-unbounded-inputs))

The same contract idea for methods whose inputs are not finite, such as a `long` price and an `int` seat count. The
statement is "the new bytecode behaves as the old bytecode on every input, except the inputs the developer declared
as changed", and it is proved with JBMC (B5) rather than by execution: both versions are compiled into one program,
a generated harness asserts the statement, and the solver either proves it or produces an input on which the two
versions differ, which the tool replays on the JVM. The developer's declaration (`seats >= 8`, say) is Java, so it is
checked by the compiler and committed with the change as its scope. This is the "measure the patch" idea of the post:
prove how few inputs a change touches. [Examples 006 to 008](demo/README.md) show a rounding refactor refuted, a feature
proved confined to its declared inputs, and a declared scope shown to be wrong; [027](demo/README.md) refutes a switch
rewrite of a retry policy that drops the 5xx statuses it did not name. On Mica, [035](demo/README.md) refutes a NaN check
written as `== Float.NaN` with a NaN witness (floats are bit-vectors to the solver), [036](demo/README.md) refutes javac's
switch-lowering heuristic computed in `int`, and [037](demo/README.md) proves the JDK 11 rewrite of `tableSizeFor` equal to the
JDK 8 one on all 2^32 inputs, with the JDK's own bytecode of `Integer.numberOfLeadingZeros` in the proof.

### B10. Capability contracts (POC in [`tools/contracts`](demo/tools/contracts/README.md#capability-contracts-what-a-module-can-do))

A different property under the same lockfile-and-diff workflow: what a module is *able to do*. From the compiled
classes, list every call to a JDK entry point that reaches beyond pure computation (the clock, randomness, files, the
network, processes, environment, threads, reflection, class loading, native code, serialization, JNDI, scripting),
grouped by capability, together with the libraries the module calls. Check it in; fail the build when it changes.
The claim is one of absence: bytecode that never names the entry points of a capability cannot exercise it, and the
ways around that (reflection, method handles, class loaders, native code) are capabilities on the list themselves.
It is a sound closed-world check, not a heuristic, and it is cheap. [Example 009](demo/README.md) catches a codec that
starts loading classes named by Kafka payloads, the mechanism of the Jackson deserialization CVEs, with no CVE database;
[028](demo/README.md) catches a `Thread.sleep` added to a retry policy that was pure so that it could run on any thread;
[041](demo/README.md) catches a bytecode interpreter that starts resolving host methods by a name from the guest's constant pool.

### B11. Property proofs (in [`lib/`](../lib/README.md#how-a-property-proof-works))

The lockfile idea applied to a statement the developer makes: a postcondition such as "a retry delay is between the
base and the cap", or a law such as "`winner(a, b) == 1 - winner(b, a)`", written as a Java boolean expression over a
method's parameters, its `result`, and the method itself, and committed next to the code in `properties.contract`.
A generated bytecode harness assumes the precondition, calls the method once, and asserts the property; JBMC (B5)
proves it over every input or produces one that violates it, which the tool replays. This is the "fuzz harness is the
spec" idea of the post with the sampling removed: a property-based test states the same theorem and tries a few
hundred inputs, the prover tries them all. [Examples 015 to 018, 022 and 071](demo/README.md) prove quorum intersection, backoff
bounds, the monotonicity and symmetry of a hybrid logical clock, the antisymmetry of last-writer-wins and the election
restriction of Raft's vote rule, and refute five plausible rewrites of them. [Examples 023, 024 and 031 to 033](demo/README.md) do the same for a Kafka partitioner, a
JWT validator's clock skew, a token bucket's refill, a batch listener's commit and a cache's expiry. [Examples 034, 044
and 045](demo/README.md) state three sentences of the JVM specification as properties: `idiv` by -1 negates (so
`Integer.MIN_VALUE / -1` returns the dividend without an exception), no byte of a modified UTF-8 constant is zero, and the
bisection of a `lookupswitch` stays in bounds for every size a `Code` attribute allows, which is the assumption that makes
`(low + high) / 2` safe there and nowhere else. [Examples 046 to 048](demo/README.md) quantify over arrays, in JML's syntax
(`\forall int i; 0 <= i && i < a.length; ...`), which the tool compiles to loops in the harness: the full correctness of
the `lookupswitch` bisection on every sorted table up to a bound, which entry of an exception table a thrown exception
reaches, and that no byte an encoder writes is zero or in `0xf0` to `0xff`, read from the buffer after the call.
[Examples 049 to 052](demo/README.md) use JML's generalized quantifiers, `\sum`, `\num_of` and `\max`, which fold a value over
the range: the stack map frame offsets as `k` plus the sum of the deltas (with a law stated by calling the reader on the
previous frame), the length of a `Code` attribute, constant pool numbering around a `long`, and `max_stack` as the largest
prefix sum, a `\max` over a `\sum`. The refuting inputs of 050 and 051 are shrunk by the tool, which runs the harness
class in its own interpreter on smaller inputs until none fails, so the witness on the page is one nested attribute of
length zero, and one `long` constant at position 0. [Examples 053 and 054](demo/README.md) declare the exceptional behaviour,
as JML's `signals` clause does: `throws: ArithmeticException when divisor == 0` says that the method throws exactly
there and returns everywhere else, and the prover covers both paths, so that an `idiv` which drops its zero check is
proved to throw where the check did, and a class file check which rejects a handler range ending at `code_length` is
refuted on a method of one byte. Until then the exception was assumed away (`assume: divisor != 0`), and the
exceptional path was the tests' alone.
[Examples 055 and 056](demo/README.md) state what a method that writes into an array did to it, against what it received,
with JML's `\old`: `(\forall int i; result <= i && i < out.length; out[i] == \old(out[i]))` is a frame condition, the
bytes past what the encoder wrote are as they were, which refutes an encoder that zero-terminates the string into the
caller's buffer; and `keys[j] == \old(keys[i]) && offsets[j] == \old(offsets[i])` under a `\forall` and an `\exists`,
with the keys sorted, is an in-place sort proved a permutation that keeps each offset with its key, which refutes a
sort whose comparison is a difference, on two keys just over 2^31 apart. The harness copies the arrays before the
call, as long as the bound on them, and the block sets the unwinding bound a sort of four pairs needs (`unwind: 5`).

A limit found while writing them: JBMC's SAT backend proves linear arithmetic, comparisons, shifts and a single
division quickly, and gets stuck on identities between divisions and multiplications, such as "the parts of an
amount split `n` ways add up to the amount" with `floorDiv` inside a loop, which did not finish in four minutes.
Properties of that kind need an SMT backend or a deductive prover (level A), and are better stated as laws the
solver can check without reasoning about division.

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

The subject system is [Box Office](demo/apps/boxoffice/README.md): concert ticketing as two services over Kafka and MongoDB.
Its README lists the invariants to verify and the known gaps to find.

| # | Approach | Tools |
|---|---|---|
| D1 | **Protocol model checking** (POC in [`apps/boxoffice/spec`](demo/apps/boxoffice/spec/README.md)): a TLA+ model with one action per service transaction, relay and clock tick; TLC checks the README's safety invariants over every interleaving within small bounds. The order state machine in the model is generated from its B8 contract, so the proven bytecode behaviour is what the model runs. [Examples 011 and 012](demo/README.md). The same construction around a two-phase-commit coordinator ([`apps/quorum/spec`](demo/apps/quorum/spec/README.md)): [examples 020 and 021](demo/README.md); that model also states fairness conditions and a liveness property (every participant eventually decides), and is checked to implement Lamport and Gray's transaction-commit specification, a refinement TLC checks step by step: [examples 057 and 058](demo/README.md); a second configuration checks an inductive invariant of that model, four conjuncts about the votes counted and in flight, which proves atomicity by induction and finds a wrong second decision in one step: [examples 067 and 068](demo/README.md). Around the Raft role machine of the same library ([`RaftElection.tla`](demo/apps/quorum/spec/RaftElection.tla)), with election safety as an invariant and two action properties, `[][A]_v` formulas that constrain each step rather than each state (terms never decrease, a leader never campaigns): [examples 059 to 061](demo/README.md). The same model is checked under two more configurations, an inductive invariant from every state it admits, which proves election safety by induction and gives one-step counterexamples, and four servers under a symmetry set; an example's verdict is the first configuration that fails: [example 062](demo/README.md). A fourth configuration checks liveness under fairness conditions (a timer that nothing resets fires, a candidate asks for the votes it lacks, a leader sends its heartbeats), with each action's enabling condition written out as a state predicate so that TLC need not compute `ENABLED` on every step of the liveness check: a run that stays within the term budget elects a leader, and a leader whose term the cluster has left steps down. A retry rule can keep every safety property and break the first, and TLC shows the run: [examples 063 to 065](demo/README.md). An invariant that no reachable state lets the generated kernel throw turns the kernel's `IllegalStateException`, a claim that an input never occurs, into a checked theorem, and a claim extended to an input split votes deliver fails in four steps: [example 066](demo/README.md). The vote rule is the same model's second generated operator, brought in as an instance, and a fifth configuration gives one server the log a deposed leader left behind, which a leader elected without the election restriction would overwrite: a vote that moves within a term elects two leaders, and a vote rule without the restriction elects the server left behind, which only that configuration can see: [examples 069 and 070](demo/README.md); the arithmetic around the rule, which the model repeats rather than generates, is covered by property proofs instead ([example 071](demo/README.md)). Every model-checking verdict now comes with what it rests on: TLC's coverage of the generated operators, read back row by row, says which rows of each contract a step of the model takes under each configuration and which none does, and a verified verdict that no run bears on, because the rows the change altered are never taken, is labelled vacuous. A vote rule that refuses a repeat request is dead to a model whose RPCs never ask twice, a follower that leads on a late majority is dead to one that counts votes in the step that grants them, and both verify vacuously; a vote rule that throws on a term not adopted has nine rows never taken, which the `KernelNeverThrows` invariant turns into the theorem the change asked for: [examples 072 to 074](demo/README.md). And around an `Idempotency-Key` receiver with a client retrying against it ([`apps/crosscut/spec`](demo/apps/crosscut/spec/README.md)): [examples 029 and 030](demo/README.md); a second configuration of that model lets the record's time to live pass at any point, which exercises the kernel's `Expired` rows that the first never takes, with at-most-once counted per lifetime of the record and the replay invariant stated at the moment of the reply: a sweeper that releases a record in progress by its age alone lets a retry execute beside the first attempt, a record that drops its response but keeps its key replays a response that is gone, and a record that expires into a tombstone refusing late retries is proved safe under both: [examples 078 to 080](demo/README.md). The election model gained a configuration of the same kind, [`RaftElectionDelayed.cfg`](demo/apps/quorum/spec/RaftElectionDelayed.cfg), in which the reply to a vote request waits on the wire as a step of its own, so that the role machine's rows for a reply from a term the candidate has left, which a one-step RPC never produces and the five other configurations verify vacuously, are taken: a role machine that adopts such a term sends a term backwards, one that holds such a reply impossible throws on a routine late reply, and the logging of such replies is verified: [examples 081 to 083](demo/README.md). And a seventh, [`RaftElectionHistory.cfg`](demo/apps/quorum/spec/RaftElectionHistory.cfg), in which two history variables record every term a server has led and every vote cast, so that what the paper claims of a whole run, at most one leader elected per term and one vote per server per term, is an invariant: a candidate that stands down for a rival of its own term votes twice in it, a leader that yields to a candidate of its own term lets the term elect twice, one after the other, with every state invariant intact under the six other configurations, and a leader that answers such a candidate with its heartbeats is proved the term's only leader: [examples 084 to 086](demo/README.md). The two-phase-commit model gained two configurations of its own, [`TwoPhaseCommitCrash.cfg`](demo/apps/quorum/spec/TwoPhaseCommitCrash.cfg) and [`TwoPhaseCommitCrashInductive.cfg`](demo/apps/quorum/spec/TwoPhaseCommitCrashInductive.cfg), in which the coordinator may crash between steps or after logging a decision and before sending it, and restarts on a recovery rule that is the model's second generated operator: a restart that aborts whatever was logged reverses a commit a participant has applied, a restart with nothing to redo leaves a logged decision unsent and a prepared participant waiting forever, and a restart that resumes collecting is proved safe and live, by search and by induction: [examples 087 to 089](demo/README.md). The same model, under a fifth configuration, holds the Java nodes around the coordinator to itself, trace validation: the nodes run through scripted scenarios with crashes injected, the state after each step recorded in the model's variables, and TLC walks each recorded run and checks every step against the model's next-state relation as an action property, which catches a node that broadcasts before it logs and one that loses its counted votes in a crash, changes to the glue no contract and no other configuration sees, and passes a participant that votes no when it gives up: [examples 090 to 092](demo/README.md). Two more configurations let the participants crash, between steps or between logging a vote and sending it, and restart on the participant's rule, a third generated operator, from `Participant#decide`: a participant that releases its locks on restart breaks atomicity, a participant node that sends its vote before logging it is caught by its recorded run, and one that votes no on restart rather than wait for the timer is proved safe and live: [examples 093 to 095](demo/README.md). A second Raft model, [`RaftReplication.tla`](demo/apps/quorum/spec/RaftReplication.tla), has the logs live, around two more generated operators, the follower's append rule and the leader's commit rule, beside the role machine and the vote rule, and checks log matching, leader completeness and state machine safety, with an action property that no committed entry is ever overwritten, under two configurations, three terms with two entries and the four terms of the paper's figure 8: a follower that takes entries after a conflicting previous entry breaks log matching in twelve steps, a leader that commits an earlier term's entry by counting replicas is verified by three terms and caught by four, a rival elected without the entry about to overwrite it, and a follower that drops a conflicting previous entry at once is proved safe: [examples 096 to 098](demo/README.md). The replication model is then checked for liveness under fairness as the election model is, a third configuration with three temporal properties for the runs that stay within the term budget: every entry in a leader's log reaches every follower, every follower learns the leader's commits, and an entry a leader appends in its term is committed unless the leader is deposed; a follower that leaves its commit index alone on a heartbeat leaves the followers behind the leader for good, a follower that refuses to overwrite a conflicting entry never catches up, refusing the same request forever, and a follower that takes the commit index on the heartbeat after an entry is proved safe and live: [examples 099 to 101](demo/README.md#the-examples). And around a circuit breaker with the component that owns it, in the same module, checked for its invariants and, under fairness, for three liveness properties each written for a different fate of the dependency: an open breaker that restarts its wait on each refused call never probes again under a caller that keeps calling, and a half-open breaker that starts the probes over on a failed one never gives a dead dependency its wait, each found as a run that goes on forever while every invariant holds, and each invisible to the other two properties; a half-open breaker that judges its probes by their failure rate, as Resilience4j does, is proved safe and live: [examples 075 to 077](demo/README.md). And around the class initialization procedure of JVMS §5.5 with threads racing for one class ([`apps/mica/spec`](demo/apps/mica/spec/README.md)), checked for deadlock as well as for its invariants: [examples 042 and 043](demo/README.md) | TLC |
| D2 | **TLA+ trace validation:** instrument the Java service, and check that recorded traces are behaviours of the D1 model | TLC, plus a `kind` cluster with fault injection (Chaos Mesh via Helm) to cover partitions and crashes |
| D3 | **P with PObserve:** runtime monitoring of Java services against P specs | P compiler (.NET) |
| D4 | **Refinement down to bytecode:** prove each message handler's bytecode (B1) refines its TLA+ action, so the TLA+ invariants hold for the shipped code | Lean + TLA+ (ambitious) |

## Cross-cutting: making AI-written proofs trustworthy

The post warns about reward hacking: making a theorem provable by changing the program until it is trivial.
Every demo should guard against this:

- **Freeze statements.** `spec/` and the exporter are hashed. CI fails when an agent's diff touches them.
- **No escape hatches.** Reject `sorry`, `admit`, and new `axiom`s, and audit `#print axioms` for each theorem.
- **Measure patches.** When a fix is needed, prove how few inputs it changes, as the post did.
- **Mine statements** from existing JUnit, jqwik and Jazzer tests, rather than hand-writing them.

## Proposed demo sequence

Done so far, as the numbered [examples](demo/README.md): B8 (001 to 005), B9 (006 to 008), B10 (009 and 010) and D1 (011 and 012) on Box Office.
The four verifiers behind them are also a Rust library and command line, [`lib/`](../lib/README.md) (`jvmcontract`), which derives
behavioural contracts without a JVM by interpreting the bytecode (a first, small step towards the executable semantics of B1 and B2),
proves purity dynamically over the executed domain, generates its JBMC harnesses as bytecode, and adds API contracts, per-dependency
capability contracts, property proofs (B11) and a TLC runner.
Examples 013 to 022 run that tool over [Quorum](demo/apps/quorum/README.md), a library of distributed-systems kernels: Raft's vote rule and
role machine, quorum arithmetic, backoff, a hybrid logical clock, last-writer-wins and a two-phase-commit coordinator with its TLA+ model.
Examples 023 to 033 and 075 to 080 run it over [Crosscut](demo/apps/crosscut/README.md), the kernels inside a Spring Boot service's cross-cutting concerns:
the transaction interceptor's rules, a circuit breaker with its TLA+ model, a retry policy, a token bucket, an idempotent receiver with its TLA+ model, a Kafka
partitioner and batch commit, a JWT validator's clock skew and a cache's expiry.
Examples 034 to 056 run it over [Mica](demo/apps/mica/README.md), the decision kernels of a small JVM written in Java: class initialization
with its TLA+ model, the type checker's assignability relation, access control, `idiv` and `fcmp`, a `lookupswitch` bisection and the
sort of its pairs, the exception table's handler lookup, stack map frame offsets, the length of a `Code` attribute, constant pool numbering, `max_stack`,
javac's switch heuristic, a power-of-two table size and modified UTF-8.
Still to do:

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
