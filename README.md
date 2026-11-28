# in-the-loop

**What a change to Java code does to its callers, stated as claims and answered by a checker or the original JVM.**

Given two revisions of a Java application or library, in-the-loop checks what a caller should see change and what
it should still be able to rely on. A domain agent states the claims. A checker can establish one within its
stated bounds, find a counterexample, or leave it open with a reason. Runs can also report exactly what an original
JVM did on a registered call history. Each result identifies the evidence and scope behind it. Nobody writes a
specification. The repository holds the verifier, more than 500 changes it has been run on, and the whole record
of how models built both.

## Three answers, and none is the model's opinion

The model writes the claims and drives the tools. The answer to each claim comes from a model checker, or from
the original JVM running a registered call history.

| Answer | What it means |
|---|---|
| **Established** | The claim holds for every input within the bounds the report states, not for a sample of them |
| **Refuted** | A concrete input, shrunk to a small one and run on a real JVM. It is a finding about the change |
| **Left open** | The tools could not decide, and the report says why. It never counts as a pass |

An **observation** is a fourth kind of result, and a narrower one: what the original JVM did on the inputs,
history and environment recorded, not on every input. A declared finite domain run exhaustively can establish that
domain.

[Example 285](examples/285-spring-boot-cve-2023-34055-unbounded-http-method-labels/README.md) is the first real
target, a Spring Boot security fix (CVE-2023-34055, 2.7.17 → 2.7.18) proved on the released JARs:

```
Does the fix bound the "method" metric label?

✗ 2.7.17: refuted      method(request{getMethod()=""}) returns ImmutableTag{key="method", value=""}
                       the same input, run on a JVM, fails too
✓ 2.7.18: established  the label is one of eight names or UNKNOWN, for every request of the domain
✓ preserved            outside the fix, both releases give the same tag
```

Its proof tasks first stopped at things the verifier could not model. The work extended the verifier, reran the
unchanged claims on the same JARs, and each came out as expected.

[Example 586](examples/586-junit-dynamic-suite-leaves/README.md) is an observation, with no proof. It ran the same
compiled caller on both JUnit deployments. On the fix, a suite with two dynamically registered tests succeeded,
where the parent failed it with `NoTestsDiscoveredException`. The control, an empty dynamic container, still failed
on both. [Example 338](examples/338-commons-io-bom-reset/README.md), Commons IO's byte-order-mark stream after a
reset, is followed claim by claim in [`ARCHITECTURE.md`](ARCHITECTURE.md#how-a-change-is-proven).

## What is here

Each part's page has its own layout that says where things are. The folders will be reorganized at some point, so
follow the links from these pages instead of remembered paths.

| Where | What it is | Its layout |
|---|---|---|
| [`examples/`](examples/README.md) | More than 500 changes run through a formal verifier, each with its verdict and the input or trace behind it. More than half are changes to published libraries, such as Spring Boot, Spring Framework and Kafka; the rest were written for small systems built to be provable. The [router](examples/README.md#all-examples) lists them all, with current counts | [Find an example](examples/README.md#find-an-example), [Layout](examples/README.md#layout) |
| [`lib/`](lib/README.md) | `jvmcontract`, the verifier, in Rust: a class-file reader, a bytecode interpreter and its own bounded model checker, with JBMC as a second engine. It derives contracts without a JVM and proves without `javac` | [Layout](lib/README.md#layout) |
| [`jobs/`](jobs/README.md) | The job pipeline: builds, tests, setup and proofs are queued as jobs, not run inside a session, and run under memory and CPU caps, each with a recorded result. `python3 jobs/pipeline.py view` gives every job one state and its reason | [What it owns](jobs/README.md#what-the-pipeline-owns-and-what-a-workload-owns) |
| [`verification/`](verification/README.md) | The verification workload on that pipeline (preparing and interpreting proof jobs), its artifacts, and the historical jobs and results | [Layout](verification/README.md#layout) |
| [`llm-dlc/`](llm-dlc/README.md) | How the repository is built: runs and the tools under them, every commit published with the redacted session that made it, and [what was retired](llm-dlc/retired.md) | [Layout](llm-dlc/README.md#layout) |

## Explore it, or reproduce a result

**Explore it with an agent.** The quickest way in is to clone the repository and ask a coding agent about it.
Everything here is linked, and all of it is public:

- **An example** has a page with its verdict and the input or trace behind it, beside the `example.json` and
  `result.json` the page is generated from. `python3 examples/tools/find.py` searches them all.
- **A proof that ran as a job** has its description in `verification/jobs/`, which names the session that
  submitted it, and its recorded result in `verification/results/`, which names the commit it ran on.
- **A commit** ends its message with one or more `LLM-Trace` lines. Each links a session and the SHA-256 of its
  redacted log. A line says the session was at work when the commit was made; several lines on one commit do not
  say which session wrote it ([VF-079](verification/findings.md)).
- **A session** has a summary at `llm-dlc/traces/<session-id>/summary.md`, with what it was asked, what it
  committed, and a link to its full redacted transcript; `metrics.json` beside it has its tokens and costs.
- **What went wrong and what was decided** is in [`verification/findings.md`](verification/findings.md) and in
  the decision records under `llm-dlc/decisions/`.

So a question such as "which session proved example 285, what did the verifier lack at first, and what did the
work cost?" can be answered from a checkout alone.

**Reproduce one result.** [The path a change takes](ARCHITECTURE.md#the-path-the-project-is-built-around) shows
where a result like this one comes from. On Ubuntu 24.04 or 26.04 ([`examples/setup/`](examples/setup/README.md) has the
components and what each installs):

```bash
examples/setup/ubuntu/install.sh        # the toolchain; prompts for sudo once
exec bash                               # pick up PATH
examples/setup/ubuntu/doctor.sh         # verify it
python3 examples/tools/build.py 002     # run one constructed example and rewrite its page
```

The last command ends with `002-equality-refactor-changes-null-handling: violation (as expected)`: a refactor
believed equivalent that changes how a null is handled, found by the verifier. It takes about 20 seconds once
Gradle has the build's dependencies. [Run an example](examples/README.md#run-an-example) has the rest.

**What it takes.** Reproducing a constructed example needs little. The tools accept a machine from 8 GB of
memory, 2 CPUs and 10 GB of free disk, and are comfortable from 16 GB, 4 CPUs and 25 GB;
`python3 llm-dlc/tools/doctor.py` measures yours and says what it limits. Running the workflow that produced this
repository is another matter. A run keeps an agent session, the verifier's builds and a queue of proofs going for
hours, a real-world target builds a whole upstream project, and a single proof job may run for up to six hours.
That takes a large Linux machine and the model usage of sessions that run that long, so it is for people who want
to work on the verifier itself, not for a first look.

## How it is built

The repository is written almost entirely by models, in **runs**: one agent works toward one outcome while a
watcher session outside it judges, after each of the agent's context windows, whether it gets another. A run
starts from a prompt, from a brief, or from a list of pull requests that a first phase writes into a brief
(`/orchestrate-run`: [`llm-dlc/README.md`](llm-dlc/README.md#a-single-agents-run)). The proofs it needs are
queued as jobs and run beside it, under memory and CPU caps. Every session is public: each commit links the
sessions at work when it was made, with the SHA-256 of each one's log.

[`ARCHITECTURE.md`](ARCHITECTURE.md) is the map, and [its diagram](ARCHITECTURE.md#the-path-the-project-is-built-around)
follows a brief from the queue through setup, the domain agent's claims and the checkers to landing. It also says
who owns what, which record answers which question, and what is not built yet.

## Status

There is no installable product at the moment. Until 2026-11-27 this page offered a plugin,
`/in-the-loop:prove-java-change`, which installed a released copy of the repository and proved a change on your
machine. It is retired with its last release, 0.10.0:
[`llm-dlc/retired.md`](llm-dlc/retired.md#plugin-and-runtime-mode) says what it was and where to read it.

## For agents

- [`CLAUDE.md`](CLAUDE.md) is the procedure: every session is traced and published with the commits it made.
- To find examples close to a task: `python3 examples/tools/find.py`
  ([`examples/README.md`](examples/README.md#find-an-example)).
- Proofs, model checks, builds and setup are queued as jobs ([`jobs/README.md`](jobs/README.md); for proof jobs,
  [`verification/README.md`](verification/README.md#for-agents-making-changes-submitting-a-job)). `CLAUDE.md` says
  the little that may run inline.
- A run is started by a person, or by a watcher at a person's word, with `/orchestrate-run`; an agent never starts
  one as a step of its own work. [`llm-dlc/retired.md`](llm-dlc/retired.md) lists the workflows that came before it.

## Background

The work is inspired by [LLM-assisted formal verification at scale](https://www.anthropic.com/research/formal-verification),
which proved properties of compiled RISC-V binaries, not source code. This repository asks what the equivalent looks
like for the JVM. It started as a set of demos, from source code down to bytecode and native code, with distributed
protocols model-checked in TLA+; [`examples/approaches.md`](examples/approaches.md) has the approaches by level.

## License

Code is licensed under Apache-2.0 ([LICENSE](LICENSE)).
`examples/approaches.md`, `llm-dlc/specification.md`, and the session records in `llm-dlc/` (`README.md`, `index.json`, `summary-template.md` and `traces/`, including the published logs they point at) are licensed under CC BY 4.0 ([LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0)).
