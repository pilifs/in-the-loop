# `/verify-bytecode`: formal verification of a Java pull request, in Claude Code

A [Claude Code](https://code.claude.com) skill. You point it at a pull request; it compiles the code before and after, runs [`jvmcontract`](../../lib/README.md) over the compiled bytecode, and reports what was proved, what was refuted (with the input), and what it could not check.

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

That is the one input the pull request set out to fix, found from the bytecode alone, with no test and no specification written. The skill then proves the fix as a property: `pow(-2, 31) == -2147483648` holds on the new version (1.0 s) and fails on the old one with the `ArithmeticException` above (0.7 s). It proves the Javadoc on the new version, `@throws IllegalArgumentException if e < 0` with the documented results for `k` in `{-1, 0, 1}`, in 1.4 seconds. And it asks JBMC to prove the change confined with `--unchanged-unless 'k == -2 && e == 31'`, which is the statement a reviewer approves; that full-domain proof over chained 32-bit multiplications is the expensive one, and the report says how far it got within its budget.

Nobody writes a specification. The previous version of the method is the specification for a regression proof; the Javadoc is the specification for a property proof; the types are the specification for a behavioural contract; and the bytecode itself is the specification for what a module can reach. Every verdict is *verified*, *violation* with a concrete witness, or *unverifiable* with the reason. "We could not check" is never reported as "fine".

## Install

One command. It needs `git` and never asks for `sudo`:

```bash
curl -fsSL https://terminalvalue.net/verify-bytecode-skill/install.sh | bash
```

It copies the skill into `~/.claude/skills/verify-bytecode`, builds and installs `jvmcontract` with cargo (installing Rust first if there is no cargo), and checks for the tools the skill uses, printing how to get any that are missing:

| Tool | For | Without it |
|---|---|---|
| a JDK (`javac`) | compiling the pull request | nothing works |
| [JBMC](https://github.com/diffblue/cbmc) (`jbmc`) | regression and property proofs | behavioural contracts and the module-level diffs still run |
| [`gh`](https://cli.github.com), logged in | reading the pull request | nothing works |
| `mvn` or `gradle` | projects without a wrapper | projects with `mvnw`/`gradlew` build anyway |
| `jq` | reading the pull request's metadata | the fetch script fails |

The same script, read first: [`install.sh`](install.sh). Rerun it to update the skill; `JVMCONTRACT_UPGRADE=1` also rebuilds the verifier. To remove everything: `rm -rf ~/.claude/skills/verify-bytecode && cargo uninstall jvmcontract`.

**As a plugin instead.** Claude Code 2.1.292 or later installs the plugin from this repository's marketplace in one command, and the skill is then `/jvmcontract:verify-bytecode`:

```bash
claude plugin install jvmcontract --marketplace pilifs/in-the-loop
```

The plugin does not install `jvmcontract` itself; the skill tells you how when it finds it missing (`cargo install --git https://github.com/pilifs/in-the-loop --locked jvmcontract`).

**Model.** The skill sets `model: opus` in its [front matter](skills/verify-bytecode/SKILL.md), which is Claude Opus 5.5 on the Anthropic API. The work is judgment-heavy: reading a diff to find the changed methods, deciding which proof fits each, translating Javadoc into assumptions and assertions, and reading a witness. To pin the version, edit the line to `model: claude-opus-5-5`; to use whatever model the session runs, delete it.

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

Good subjects have small Maven or Gradle builds, an active pull request flow, and static utility methods over primitives and primitive arrays. Five popular ones, with the classes where the proofs land:

| Library | Build | Where the proofs land | Try |
|---|---|---|---|
| [Apache Commons Numbers](https://github.com/apache/commons-numbers) | Maven, multi-module | `ArithmeticUtils` (`gcd`, `lcm`, `pow`, `isPowerOfTwo`, `remainderUnsigned`, `divideUnsigned`), `Precision`, `DD` | [#223](https://github.com/apache/commons-numbers/pull/223), the `pow` fix above: regression proof, confined change, and the Javadoc proved |
| [Joda-Time](https://github.com/JodaOrg/joda-time) | Maven, one module | `org.joda.time.field.FieldUtils` (`safeAdd`, `safeSubtract`, `safeMultiply`, `safeNegate`, `safeToInt`, `safeMultiplyToInt`), with `@throws ArithmeticException` in every Javadoc | any pull request touching `FieldUtils`; or `--only org.joda.time.field.FieldUtils#safeMultiply(long, int)` on a recent one, to see the overflow contract proved |
| [Apache Commons Codec](https://github.com/apache/commons-codec) | Maven, one module | `Hex` (`encodeHex(byte[])`, `decodeHex(char[])`), `BaseNCodec` helpers, `PureJavaCrc32`, `MurmurHash3` (`hash32x86(byte[], int, int, int)`) | pull requests to `binary/` and `digest/`: regression proofs over `byte[]` and `char[]`, bounded in length |
| [jackson-core](https://github.com/FasterXML/jackson-core) | Maven, one module | `com.fasterxml.jackson.core.io.NumberOutput` (`outputInt(int, char[], int)`, `outputLong`, `divBy1000`), `NumberInput`, `CharTypes` | pull requests to `io/`: the number formatters are static, over `int`, `long` and `char[]` |
| [Apache Commons Lang](https://github.com/apache/commons-lang) | Maven, one module | `ArrayUtils` over primitive arrays (`indexOf(int[], int)`, `reverse(int[])`, `isSorted(int[])`), `BooleanUtils` (`toBoolean(int)`, `and(boolean...)`), `CharUtils`, `NumberUtils.compare` | the primitive-array methods: regression proofs that compare what each version leaves in the array |

What does not work well: `String`-heavy libraries (jsoup, Commons Text), anything whose build takes longer than the proofs (Guava, Netty), and methods whose only parameters are objects.

## How it is built

[`SKILL.md`](skills/verify-bytecode/SKILL.md) is the procedure, [`reference.md`](skills/verify-bytecode/reference.md) the tool's commands, expression language and limits for the agent, [`report-template.md`](skills/verify-bytecode/report-template.md) the report's shape. Two scripts do the mechanical parts deterministically: [`fetch-pr.sh`](skills/verify-bytecode/scripts/fetch-pr.sh) checks out the merge base and the head of a pull request, and [`build.sh`](skills/verify-bytecode/scripts/build.sh) compiles one module with Maven or Gradle and prints its class directory and dependency classpath (with [`gradle-classpath.gradle`](skills/verify-bytecode/scripts/gradle-classpath.gradle), an init script that works under the configuration cache).

The verifier is [`lib/`](../../lib/README.md), a Rust crate with no JVM in the loop. The [examples](../../examples/README.md) of this repository are 56 code changes run through it, each with the verdict and what the existing tests did. The sessions that built all of it are published in [`llm-dlc/`](../../llm-dlc/README.md).
