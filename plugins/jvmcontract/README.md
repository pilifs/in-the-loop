# `/verify-bytecode` and `/add-tla-model`: formal verification for Java, in Claude Code

Two [Claude Code](https://code.claude.com) skills over [`jvmcontract`](../../lib/README.md), installed by one command. **`/verify-bytecode`** takes a pull request: it compiles the code before and after, runs the verifier over the compiled bytecode, and reports what was proved, what was refuted (with the input), and what it could not check. **`/add-tla-model`** takes your own project: it finds the code that decides what happens next, derives its behaviour from the bytecode, writes a TLA+ model of the system around it with the invariants you state, checks them with TLC over every interleaving within bounds, and wires the check into your build. [Below](#add-tla-model-check-your-own-invariants-with-a-tla-model).

```
/verify-bytecode https://github.com/apache/commons-numbers/pull/223
```

```
✗ Behaviour of org.apache.commons.numbers.core.ArithmeticUtils#pow(int, int) changed:
  pow(k=-2, e=31)
    before: throws ArithmeticException("integer overflow")
    after:  -2147483648
  (found by JBMC 6.11.0 in 184.7 s searching inputs in [-100000:100000], replayed in the interpreter; domain k: int × e: int)
```

That is the one input the pull request set out to fix, found from the bytecode alone, with no test and no specification written. The skill then proves the fix as a property: `pow(-2, 31) == -2147483648` holds on the new version (1.0 s) and fails on the old one with the `ArithmeticException` above (0.7 s). It proves the Javadoc on the new version, `@throws IllegalArgumentException if e < 0` with the documented results for `k` in `{-1, 0, 1}`, in 1.4 seconds. And with `--unchanged-unless 'k == -2 && e == 31'`, the statement a reviewer approves, JBMC proves that the new `pow` behaves as the old one on every other input: all 2^64 of them, in 18 minutes. That full-domain proof over chained 32-bit multiplications is the expensive one; the skill runs it in the background with a budget and reports how far it got.

Nobody writes a specification. The previous version of the method is the specification for a regression proof; the Javadoc is the specification for a property proof; the types are the specification for a behavioural contract; and the bytecode itself is the specification for what a module can reach. Every verdict is *verified*, *violation* with a concrete witness, or *unverifiable* with the reason. "We could not check" is never reported as "fine".

## Install

One command. It needs `git` and never asks for `sudo`:

```bash
curl -fsSL https://terminalvalue.net/verify-bytecode-skill/install.sh | bash
```

It copies the two skills into `~/.claude/skills/`, builds and installs `jvmcontract` with cargo (installing Rust first if there is no cargo), downloads TLC into `~/tools` if there is none, and checks for the tools the skills use, printing how to get any that are missing:

| Tool | For | Without it |
|---|---|---|
| a JDK (`javac`) | compiling the pull request | nothing works |
| [JBMC](https://github.com/diffblue/cbmc) (`jbmc`) | regression and property proofs | behavioural contracts and the module-level diffs still run |
| [`gh`](https://cli.github.com), logged in | reading the pull request | nothing works |
| `mvn` or `gradle` | projects without a wrapper | projects with `mvnw`/`gradlew` build anyway |
| `jq` | reading the pull request's metadata | the fetch script fails |
| [TLC](https://github.com/tlaplus/tlaplus) (`~/tools/tla2tools.jar`) | checking TLA+ models | installed by the script; `NO_TLC=1` skips it, and `/add-tla-model` then writes a model it cannot check |

The same script, read first: [`install.sh`](install.sh). Rerun it to update the skills; `JVMCONTRACT_UPGRADE=1` also rebuilds the verifier; `VERIFY_BYTECODE_SKILLS=verify-bytecode` installs one skill only. To remove everything: `rm -rf ~/.claude/skills/verify-bytecode ~/.claude/skills/add-tla-model && cargo uninstall jvmcontract && rm ~/tools/tla2tools.jar`.

**As a plugin instead.** Claude Code 2.1.292 or later installs the plugin from this repository's marketplace in one command, and the skills are then `/jvmcontract:verify-bytecode` and `/jvmcontract:add-tla-model`:

```bash
claude plugin install jvmcontract --marketplace pilifs/in-the-loop
```

The plugin does not install `jvmcontract` or TLC itself; each skill tells you how when it finds them missing (`cargo install --git https://github.com/pilifs/in-the-loop --locked jvmcontract`; `bash scripts/install-tlc.sh` in the `add-tla-model` skill).

**Model.** Both skills set `model: opus` in their front matter ([one](skills/verify-bytecode/SKILL.md), [two](skills/add-tla-model/SKILL.md)), which is Claude Opus 5.5 on the Anthropic API. The work is judgment-heavy: reading a diff to find the changed methods, deciding which proof fits each, translating Javadoc into assumptions and assertions, reading a witness; or reading a codebase for the state machine inside it and writing each transaction as a TLA+ action. To pin the version, edit the line to `model: claude-opus-5-5`; to use whatever model the session runs, delete it.

## Use

```
/verify-bytecode <pull request> [--post] [--only pkg.Class#method ...] [hints]
```

The pull request is a URL, `owner/repo#N`, or `N` for the repository you are in. `--post` posts the report as a comment on the pull request when it is done; without it nothing is written anywhere but a working directory. `--only` restricts the targets. Anything else is a hint: the intended change ("only for groups of eight or more"), a property to prove, a module to build.

What happens, in order (the skill says so as it goes):

1. **Fetch**: `gh` reads the pull request; the commit the branch left the base at and the head commit are checked out side by side.
2. **Scope**: the changed `.java` files under main source sets, their module, and every method whose body or signature changed, was added or removed.
3. **Build** both versions with the project's Maven or Gradle build, same JDK. This runs the pull request's build scripts, as you would when checking out the branch; Claude Code asks for permission first. If the module does not build, the changed files are compiled alone when they depend only on the JDK, and the report says so.
4. **Prove** each changed method with the proof its shape allows (next section), one at a time, within a memory and time budget.
5. **Diff** the module's capability contract (what its bytecode can reach: clock, network, reflection, class loading, ...) and its public API contract, before and after. A new capability is the headline of the report whatever the pull request says it is about.
6. **Report**: a verdict table, each finding with its witness and the exact command, what was not covered and why, and how to reproduce it. The working directory with every harness and JBMC log is left in place.

## What it proves

| The changed method is | The skill proves | Verdicts |
|---|---|---|
| `static`, with primitive parameters or arrays of integral or boolean elements, present in both versions | The new bytecode behaves as the old one on every input (**regression proof**: both versions in one program, a generated harness, JBMC). If the pull request says the behaviour changes for some inputs, the change is proved confined to them with `--unchanged-unless`. | Verified over the whole domain; or a violation with the input, shrunk, and what each version did on it |
| the same, with a Javadoc `@throws`, `@return` or `@param` claim | The claim, on every input (**property proof**), on the new version and, for a fix, on the old one, where it should fail | Verified; or the input on which the code breaks its own documentation |
| pure, with finitely many inputs (enums, booleans, records and sealed types) | Its complete behaviour, every input executed in a bytecode interpreter under an effect monitor (**behavioural contract**), before and after, diffed | Equal; or the cases that changed, listed |
| anything else: `String` or object parameters, instance methods with state, constructors | Nothing per method. The report says so, with the reason. | The module-level diffs still cover the change |

The limits are the tool's, described in the [library README](../../lib/README.md#limits): arrays are bounded in length, 64-bit division on both sides of a comparison can exhaust the solver, loops beyond the unwinding bound are reported as unverifiable, and the interpreter models a subset of the JDK. The skill reports a bound as a bound.

## Libraries to try it on

Good subjects have small Maven or Gradle builds, an active pull request flow, and static utility methods over primitives and primitive arrays. The list of libraries and classes where the proofs land, and the pull requests already verified, are in [`examples/real-world/`](../../examples/real-world/README.md), starting with [Apache Commons Numbers #223](../../examples/real-world/commons-numbers-223/README.md), the `pow` fix above.

What does not work well: `String`-heavy libraries (jsoup, Commons Text), anything whose build takes longer than the proofs (Guava, Netty), and methods whose only parameters are objects.

## `/add-tla-model`: check your own invariants with a TLA+ model

A method proof stops at the method. The failures that matter in a system of services, queues and timers live in the interleavings nobody thought of: a lease that expires while a message is in flight, a retry that lands after the state has moved on, a probe that closes a breaker too early. TLC enumerates them. This skill adds a TLA+ model to your project and checks the rules you care about, in your system's terms, over every interleaving within small bounds:

```
/add-tla-model com.example.orders.OrderLifecycle#decide "no two confirmed orders share a seat" "captured money is on a confirmed order or being refunded"
```

Run in your project's directory. The target and the invariants are optional: without a target it looks for the state machine in the code; without invariants it asks what the system must never do. What happens, in order:

1. **Find the kernel.** The code that decides what happens next: a pure static method `decide(State, Input)` over an enum and a sealed input type, returning a transition with effects, "unchanged" or "rejected". If your project has one (an `OrderLifecycle`, a `Coordinator`, a `CircuitBreaker` state machine), it is used as is. If the logic is spread over handlers (`if (order.status == PENDING) { ... order.setStatus(CONFIRMED) }` in three services), the skill proposes the kernel, one record per thing that can happen and one effect per thing the handler then does, shows the handler lines it replaces, and asks before changing any Java. `--no-refactor` keeps the Java as it is and transcribes the rule by hand, marked as such.
2. **Derive, don't transcribe.** `jvmcontract derive` executes the kernel on every input and writes its behavioural contract (`44 cases`); `jvmcontract tla` turns the contract into the TLA+ operator `Decide(state, input)`. The model calls that operator, so the state machine in the model is the one the bytecode implements, proved on every build, not a copy someone has to keep in sync.
3. **Write the model.** One action per transaction, named after the Java operation it stands for; one variable per table, queue and timer; the environment (a clock, a dependency going down, a redelivered message); and your invariants, one line each, in a `.tla` and a `.cfg` with small bounds.
4. **Check.** `jvmcontract tlc` runs TLC: every invariant holds in N states, or the shortest interleaving that breaks one, step by step. A violation is read against the Java before anything changes: a bug, a model mistake, or a rule that needs restating, and the skill says which. A verified model is then broken once on purpose, to show the invariants can fail at all.
5. **Wire it in.** `spec/check.sh` derives the contract from the current classes, fails with a diff if what the kernel decides has changed (so the change is reviewed like an API change and accepted with `--update`), regenerates the operator and runs TLC; one Gradle task, Maven execution or CI step calls it. A `spec/README.md` says what the model covers, what it leaves out, and what a pass means.

**A real run.** The [Crosscut](../../examples/demo/apps/crosscut/README.md) module has a circuit breaker kernel, `CircuitBreaker#decide`, with a 44-case contract and no model. Following the skill's procedure produced [`spec/CircuitBreaker.tla`](../../examples/demo/apps/crosscut/spec/CircuitBreaker.tla): the component that owns the breaker (its sliding window, probe cap and wait timer), a dependency that goes up and down, and five invariants, among them *an open breaker lets nothing through until its wait has elapsed* and *half-open closes only once every permitted probe has completed*.

```
$ jvmcontract derive net.terminalvalue.crosscut.resilience.CircuitBreaker#decide --classes build/main > spec/CircuitBreaker.decide.contract
(44 cases, 11 methods proven pure, trusting java.lang.Enum.ordinal, ...)
$ jvmcontract tla spec/CircuitBreaker.decide.contract spec/CircuitBreakerContract.tla
wrote spec/CircuitBreakerContract.tla: 33 cases
$ jvmcontract tlc spec/CircuitBreaker.tla
✓ every invariant holds in 102 distinct states, depth 19, in 0 s (TLC 2.19)
```

With the kernel of [example 026](../../examples/demo/026-half-open-breaker-that-closes-on-the-first-good-probe/README.md) compiled in instead (half-open closes on the first good probe), `check.sh` first stops on the two contract rows that changed, and after `--update` the regenerated operator makes the model report:

```
✗ invariant ClosedOnlyAfterEveryProbe is violated after 10 steps, depth 10, in 0 s (TLC 2.19)
  1. Initial predicate: closedEarly = FALSE, current = 0, dependency = "DOWN", ..., state = "CLOSED"
  2. Request: current = 1
  3. Request: current = 2
  4. Complete: current = 1, window = <<TRUE>>
  5. Complete: current = 0, state = "OPEN", waitLeft = 2, window = <<TRUE, TRUE>>
  6. Tick: waitLeft = 1
  7. Tick: waitLeft = 0
  8. Request: current = 1, state = "HALF_OPEN", window = <<>>
  9. DependencyFlips: dependency = "UP"
  10. Complete: closedEarly = TRUE, current = 0, state = "CLOSED"
```

Two failures open the breaker, the wait elapses, one probe is permitted, the dependency comes back, and that single probe closes it. Writing the model also forced a decision the kernel leaves to its owner into the open: which outcomes the owner reports. An owner that reports every outcome counts a straggler from before the breaker opened as a probe; the model stamps each call with its metrics generation and drops the stale ones, and its README says so. The four earlier models in this repository ([orders and payments across two services](../../examples/demo/apps/boxoffice/spec/README.md), [two-phase commit](../../examples/demo/apps/quorum/spec/README.md), [an idempotency key under retries](../../examples/demo/apps/crosscut/spec/README.md), [class initialization under racing threads](../../examples/demo/apps/mica/spec/README.md)) follow the same construction and are the style the skill writes in.

**What a pass means.** Within the bounds of the `.cfg`, no interleaving of the modelled actions reaches a state that violates the invariants. It does not prove the Java correct: the actions are a hand-written account of what each transaction reads and writes, and are as faithful as that reading. The part that is not hand-written is the decision rule, generated from a contract proved against the bytecode. The skill's reports and READMEs say this every time.

**Where it fits.** Code that keeps an entity's state and moves it on events: order, booking and subscription lifecycles; payment and refund sagas; outbox relays and inboxes; idempotency keys and deduplication; leases, locks and leader election; circuit breakers, retries and rate limiters; workflow and approval engines; anything with a `status` column and three services that write it. What it does not fit: computation without state (use `/verify-bytecode`), liveness ("every order eventually settles", which needs fairness and a temporal property), and systems whose state space has no small bound that keeps the interesting interleavings.

Options: `--spec-dir DIR` (default `spec/` in the kernel's module), `--deadlock` (also report a state in which nothing can move), `--no-refactor`.

## How it is built

[`SKILL.md`](skills/verify-bytecode/SKILL.md) is the procedure, [`reference.md`](skills/verify-bytecode/reference.md) the tool's commands, expression language and limits for the agent, [`report-template.md`](skills/verify-bytecode/report-template.md) the report's shape. Two scripts do the mechanical parts deterministically: [`fetch-pr.sh`](skills/verify-bytecode/scripts/fetch-pr.sh) checks out the merge base and the head of a pull request, and [`build.sh`](skills/verify-bytecode/scripts/build.sh) compiles one module with Maven or Gradle and prints its class directory and dependency classpath (with [`gradle-classpath.gradle`](skills/verify-bytecode/scripts/gradle-classpath.gradle), an init script that works under the configuration cache).

For `/add-tla-model`, [`SKILL.md`](skills/add-tla-model/SKILL.md) is the procedure and [`reference.md`](skills/add-tla-model/reference.md) the kernel's shape, the model recipe, the TLA+ that bites and how to read TLC; [`templates/check.sh`](skills/add-tla-model/templates/check.sh) and [`templates/README.md`](skills/add-tla-model/templates/README.md) are what it writes into a project's `spec/`; [`find-classes.sh`](skills/add-tla-model/scripts/find-classes.sh) locates a module's compiled classes without building, and [`install-tlc.sh`](skills/add-tla-model/scripts/install-tlc.sh) downloads `tla2tools.jar`.

The verifier is [`lib/`](../../lib/README.md), a Rust crate with no JVM in the loop. The [demo examples](../../examples/demo/README.md) of this repository are 56 code changes run through it, each with the verdict and what the existing tests did; the [real-world examples](../../examples/real-world/README.md) are pull requests to published libraries, verified with this skill. The sessions that built all of it are published in [`llm-dlc/`](../../llm-dlc/README.md).
