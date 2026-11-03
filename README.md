# Java formal verification demos

Proofs of concept for formally verifying Java, from source code down to **JVM bytecode** and **native machine code**,
plus distributed-systems protocols running on Kubernetes.

These demos are inspired by [LLM-assisted formal verification at scale](https://www.anthropic.com/research/formal-verification),
which proved properties of compiled RISC-V binaries, not source code.
The demos ask what the equivalent pipelines look like for the JVM.

The repo has two parts:

## [`examples/`](examples/README.md): formal verification

**Start here.** 109 examples in one folder, each a code change run through a formal verifier, with the verdict, the witness and why it matters: 104 constructed over four subject systems written for this repository, with the code before and after, the counterexamples and a comparison with the existing tests, and 5 pull requests and commits to published libraries verified from their bytecode with `/verify-bytecode`. The examples are a router: each is tagged by domain, defect and technique, and `examples/tools/find.py` finds the ones closest to a task.

| Path | Content |
|---|---|
| [`examples/README.md`](examples/README.md) | The router: how to find an example, the subject systems and approaches, every example in a table and by tag, how to run or add one, and where notes go |
| [`examples/index.json`](examples/index.json), [`examples/tags.json`](examples/tags.json), [`examples/tools/find.py`](examples/tools/find.py) | Every example with its tags and notes, the tag vocabulary, and the search over them |
| [`examples/apps/boxoffice/`](examples/apps/boxoffice/README.md) | The first subject system: concert ticketing as two Spring Boot services with Kafka and MongoDB, and the invariants they must keep, with its [TLA+ model](examples/apps/boxoffice/spec/README.md) |
| [`examples/apps/quorum/`](examples/apps/quorum/README.md) | The second: the pure kernels of a replicated system, Raft's election and replication rules, quorum arithmetic, backoff, a hybrid logical clock, last-writer-wins and two-phase commit, with [TLA+ models](examples/apps/quorum/spec/README.md) of two-phase commit, Raft election and Raft replication |
| [`examples/apps/crosscut/`](examples/apps/crosscut/README.md) | The third: the kernels behind a Spring Boot service's cross-cutting concerns, transaction rollback, a circuit breaker, a retry policy, a token bucket, an `Idempotency-Key` receiver, Kafka, JWT and cache expiry, with [TLA+ models](examples/apps/crosscut/spec/README.md) |
| [`examples/apps/mica/`](examples/apps/mica/README.md) | The fourth: the decision kernels of a small JVM written in Java, class initialization with its [TLA+ model](examples/apps/mica/spec/README.md), the type checker, access control, the interpreter's arithmetic, class-file structures and modified UTF-8 |
| [`examples/tools/contracts/`](examples/tools/contracts/README.md) | The Java verifiers of the Box Office examples: behavioural, regression and capability contracts, a CI gate that proves what changed and what did not |
| [`examples/tools/build.py`](examples/tools/build.py) | Runs the constructed examples, generates their pages, and generates the router |
| [`examples/approaches.md`](examples/approaches.md) | The approaches by level (source, bytecode, native, distributed), and the research plan |
| [`examples/setup/`](examples/setup/README.md) | The toolchain installer for Ubuntu and WSL2 |

## [`lib/`](lib/README.md): the verifiers as a Rust library

`jvmcontract`, a Rust crate and command line that ports the verifiers of the examples (behavioural, regression and capability contracts, and the TLA+ generator) and goes further: it derives contracts without a JVM, by interpreting the bytecode under an effect monitor that makes the purity proof complete over the domain; it generates its JBMC harnesses as bytecode, so no Java compiler is in the proof pipeline; and it adds property proofs (a postcondition or a law, stated next to the code and proved over every input), API contracts, per-dependency capability contracts, a TLC runner and a state-machine view of a contract.
It reproduces the contracts the Java tool committed for Box Office, which its tests check, and it is the verifier behind examples 013 to 054.

| Path | Content |
|---|---|
| [`lib/README.md`](lib/README.md) | What it verifies, how each verdict is proved, the commands, and the library API |
| [`lib/src/`](lib/src) | The crate: a class-file reader, the JDK image reader, the interpreter, and one module per contract kind |
| [`lib/tests/`](lib/tests) | Integration tests over Java fixtures compiled at test time, and against the committed Box Office contracts |

## [`plugins/`](plugins/jvmcontract/README.md): the verifier as Claude Code skills

`/verify-bytecode <pull request>`, a Claude Code skill that compiles a Java pull request before and after, runs `jvmcontract` over the bytecode, and reports what was proved, what was refuted (with the input) and what it could not check; and `/add-tla-model`, which adds a TLA+ model to a Java project around its decision kernel, derived from the bytecode, and checks the user's invariants with TLC. One-command install, as personal skills or as a plugin from this repository's marketplace.

| Path | Content |
|---|---|
| [`plugins/jvmcontract/README.md`](plugins/jvmcontract/README.md) | Install, what each skill proves, and libraries to try them on |
| [`plugins/jvmcontract/skills/verify-bytecode/`](plugins/jvmcontract/skills/verify-bytecode/SKILL.md) | `/verify-bytecode`: verify a pull request. The procedure, the tool reference for the agent, the report template, and the fetch and build scripts |
| [`plugins/jvmcontract/skills/add-tla-model/`](plugins/jvmcontract/skills/add-tla-model/SKILL.md) | `/add-tla-model`: add a TLA+ model to a Java project and check custom invariants with TLC. The procedure, the TLA+ reference for the agent, the `check.sh` and README templates, and the scripts that find classes and install TLC |
| [`plugins/jvmcontract/install.sh`](plugins/jvmcontract/install.sh) | The installer behind `curl -fsSL https://terminalvalue.net/verify-bytecode-skill/install.sh \| bash` |
| [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) | The marketplace, for `claude plugin install jvmcontract --marketplace pilifs/in-the-loop` |

## [`verification/`](verification/README.md): the verification pipeline

Proofs and model checks don't run inside development sessions: a session queues them as jobs, committed with the change and marked verification pending, and a runner executes them under memory and CPU limits, several at a time, and brings the results back for a batch read.

| Path | What it is |
|---|---|
| [`verification/README.md`](verification/README.md) | The lifecycle, how to submit a job, how to read a result, the runner's resources, and how a cloud backend would fit |
| [`verification/pipeline.py`](verification/pipeline.py) | `submit`, `status`, `run`, `collect`, `report`, `resubmit`, `validate` |
| [`verification/schema/`](verification/schema) | The job and result formats |
| [`verification/jobs/`](verification/jobs), [`verification/results/`](verification/results) | Jobs as submitted, and what happened when each ran |
| [`.claude/skills/run-verification/`](.claude/skills/run-verification/SKILL.md) | `/run-verification`: the procedure for the agent that manages the pipeline |

## [`llm-dlc/`](llm-dlc/README.md): the LLM development lifecycle

A meta example. This repo is written with an LLM, and every commit is published with the session that made it: what was asked, what the agent did, what it cost, and the full redacted transcript.
Each commit message links to its session and carries the SHA-256 of the log as it stood at that commit, so anyone can download the log and verify it.
The folder also holds everything that makes this work:

| Path | Content |
|---|---|
| [`llm-dlc/README.md`](llm-dlc/README.md) | The procedure agents follow, and the index of sessions |
| [`llm-dlc/specification.md`](llm-dlc/specification.md) | The specification: identifiers, invariants, metrics, storage and redaction |
| [`llm-dlc/traces/README.md`](llm-dlc/traces/README.md) | Every session added up: prompts, tokens, tools, commits and logs |
| [`llm-dlc/traces/`](llm-dlc/traces) | One folder per session: a readable `summary.md`, the `manifest.json` metadata, and `metrics.json`, with every prompt, model call and tool call as data |
| [`llm-dlc/traces/metrics.json`](llm-dlc/traces/metrics.json) | Cost, time and cache behaviour over all sessions, by model, tool, day, session and commit |
| [`llm-dlc/tools/sync.py`](llm-dlc/tools/sync.py) | The hooks and commands that capture, redact, publish and check the traces |
| [`llm-dlc/tools/metrics.py`](llm-dlc/tools/metrics.py) | Turns each log into the metrics tables, priced from [`llm-dlc/pricing.json`](llm-dlc/pricing.json) |
| [`llm-dlc/session-notes/`](llm-dlc/session-notes) | Hand-written notes on sessions, for what a log and its commits cannot say |
| [`llm-dlc/infra/cdn/`](llm-dlc/infra/cdn) | The Cloudflare Worker that serves the published logs |
| [`llm-dlc/infra/langfuse/`](llm-dlc/infra/langfuse) | An optional local Langfuse for browsing traces |

## License

Code is licensed under Apache-2.0 ([LICENSE](LICENSE)).
`examples/approaches.md`, `llm-dlc/specification.md`, and the session records in `llm-dlc/` (`README.md`, `index.json`, `summary-template.md` and `traces/`, including the published logs they point at) are licensed under CC BY 4.0 ([LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0)).
