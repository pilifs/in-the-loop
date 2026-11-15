# in-the-loop: `/prove-java-change`

**Formally prove a change to Java code, in one command.**

Point Claude Code at a pull request or a commit on GitHub. The skill works out what the change must keep and what it
is meant to do, and states that as claims. A model checker then proves each claim from the compiled bytecode, or
hands you the input where it breaks. Nobody writes a specification.

```
/in-the-loop:prove-java-change <a pull request, a commit or a range on GitHub, and what to prove about it>
```

It runs on your machine, on a released copy of this repository that the skill installs and checks against a hash it
carries. Nothing is traced or uploaded from that copy, and nothing leaves the machine unless you agree to it.

## Try it

```bash
claude plugin marketplace add pilifs/in-the-loop
claude plugin install in-the-loop@in-the-loop
```

Then, in Claude Code on Fable 5.2 at high effort, run the command above. You confirm twice, and the rest is
unattended:

| Step | What happens | You |
|---|---|---|
| 1. Set up and measure | It installs the release, checks its hash, and measures the machine: memory, CPUs, disk and tools | confirm |
| 2. State the claims | It pins the change to two exact commits, sizes it against the closest past examples, compiles it, runs it once on a JVM, and writes each claim in full | confirm the claims and the estimate, in hours and tokens |
| 3. Prove it | A fork of the session runs unattended on one line: "Formally prove example NNN as elegantly and efficiently as possible". Where the verifier can't model your code yet, the loop extends the verifier. It may not change a claim to fit a result | |
| 4. Report | Each claim comes back with one of three answers. If the proof added something to the verifier, it offers to send that upstream as a pull request | decide |

**It needs** Linux, at least 8 GB of memory, 2 CPUs and 10 GB of free disk, and Claude Code with Fable 5.2. Step 1
installs what it can of the rest (jj, a Java 25 JDK, Rust) and says what is missing and what limits the machine.

**It takes** changes on GitHub only, with their dependencies from Maven Central and the other allowed hosts.

## Three answers, and none is the model's opinion

The model writes the claims and drives the tools. The answer to each claim comes from a model checker.

| Answer | What it means |
|---|---|
| **Established** | The claim holds for every input within the bounds the report states, not for a sample of them |
| **Refuted** | A concrete input, shrunk to a small one and run on a real JVM. It is a finding about your change |
| **Left open** | The tools could not decide, and the report says why. It never counts as a pass |

[Example 285](examples/285-spring-boot-cve-2023-34055-unbounded-http-method-labels/README.md) is the proof loop's
first real target, a Spring Boot security fix (CVE-2023-34055, 2.7.17 → 2.7.18) proved on the released JARs:

```
Does the fix bound the "method" metric label?

✗ 2.7.17: refuted      method(request{getMethod()=""}) returns ImmutableTag{key="method", value=""}
                       the same input, run on a JVM, fails too
✓ 2.7.18: established  the label is one of eight names or UNKNOWN, for every request of the domain
✓ preserved            outside the fix, both releases give the same tag
```

Its proof tasks first stopped at things the verifier could not model. The loop extended the verifier, reran the
unchanged claims on the same JARs, and each came out as expected.

## What is in the repository

The skill is under 100 lines. What it stands on is the rest of the repository, and each part's page has its own
layout that says where things are. The folders will be reorganized at some point, so follow the links from these
pages instead of remembered paths.

| Where | What it is | Its layout |
|---|---|---|
| [`plugins/in-the-loop/`](plugins/in-the-loop/skills/prove-java-change/SKILL.md) | The plugin: the skill, the bootstrap that installs and checks a release, and the pin of the release it runs on | [`runtime.md`](llm-dlc/runtime.md#where-things-are) |
| [`llm-dlc/runtime.md`](llm-dlc/runtime.md) | How the skill runs: what each step stands on, the released copy on your machine, the proof loop and its conductor, contributing back, and releases | [Where things are](llm-dlc/runtime.md#where-things-are) |
| [`examples/`](examples/README.md) | 183 changes run through a formal verifier, each with its verdict and the input or trace behind it: 159 written for small systems built to be provable, 24 from published libraries. They are also what the skill sizes your change against | [Find an example](examples/README.md#find-an-example), [Layout](examples/README.md#layout) |
| [`lib/`](lib/README.md) | `jvmcontract`, the verifier, in Rust: a class-file reader, a bytecode interpreter and its own bounded model checker, with JBMC as a second engine. It derives contracts without a JVM and proves without `javac` | [Layout](lib/README.md#layout) |
| [`verification/`](verification/README.md) | The pipeline: proofs never run inside a session. They are queued as jobs and run under memory and CPU caps, each with a recorded result | [Layout](verification/README.md#layout) |
| [`llm-dlc/`](llm-dlc/README.md) | How the repository is built: the unattended loops, and every commit published with the redacted session that made it | [Layout](llm-dlc/README.md#layout) |

## For agents

- [`CLAUDE.md`](CLAUDE.md) is the procedure. `python3 llm-dlc/tools/mode.py` says which of two modes a checkout is in:
  *development*, this repository as its authors work in it, with every session traced and published, or *runtime*,
  the released copy the skill installs, where nothing is traced. [`llm-dlc/runtime.md`](llm-dlc/runtime.md) is the
  runtime side.
- To find examples close to a task: `python3 examples/tools/find.py`
  ([`examples/README.md`](examples/README.md#find-an-example)).
- Proofs and model checks are queued, never run inline
  ([`verification/README.md`](verification/README.md#for-agents-making-changes-submitting-a-job)).
- In this repository the skill runs as `/prove-java-change NNN` on an existing example, without the setup steps.

## Background

The work is inspired by [LLM-assisted formal verification at scale](https://www.anthropic.com/research/formal-verification),
which proved properties of compiled RISC-V binaries, not source code. This repository asks what the equivalent looks
like for the JVM. It started as a set of demos, from source code down to bytecode and native code, with distributed
protocols model-checked in TLA+; [`examples/approaches.md`](examples/approaches.md) has the approaches by level.

It is written almost entirely by models working in unattended loops, and every session is public: each commit
message links the session that made it and carries the SHA-256 of its log
([`llm-dlc/README.md`](llm-dlc/README.md)).

## License

Code is licensed under Apache-2.0 ([LICENSE](LICENSE)).
`examples/approaches.md`, `llm-dlc/specification.md`, and the session records in `llm-dlc/` (`README.md`, `index.json`, `summary-template.md` and `traces/`, including the published logs they point at) are licensed under CC BY 4.0 ([LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0)).
