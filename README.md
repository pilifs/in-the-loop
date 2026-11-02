# Java formal verification demos

Proofs of concept for formally verifying Java, from source code down to **JVM bytecode** and **native machine code**,
plus distributed-systems protocols running on Kubernetes.

These demos are inspired by [LLM-assisted formal verification at scale](https://www.anthropic.com/research/formal-verification),
which proved properties of compiled RISC-V binaries, not source code.
The demos ask what the equivalent pipelines look like for the JVM.

The repo has two parts:

## [`examples/`](examples/README.md): formal verification

**Start here.** Two kinds of examples: [`examples/demo/`](examples/demo/README.md), 83 numbered code changes to four subject systems written for this repository, each run through a formal verifier, with the code before and after, the verdict, the counterexamples, the risk, and a comparison with the existing tests; and [`examples/real-world/`](examples/real-world/README.md), pull requests to published Java libraries verified with the `/verify-bytecode` skill, one folder per pull request.

| Path | Content |
|---|---|
| [`examples/README.md`](examples/README.md) | The two kinds of examples, and what is shared between them |
| [`examples/demo/README.md`](examples/demo/README.md) | The table of the 56 demo examples, how to read one, and how to run or add one |
| [`examples/demo/apps/boxoffice/`](examples/demo/apps/boxoffice/README.md) | The first subject system (examples 001 to 012): concert ticketing as two Spring Boot services with Kafka and MongoDB, and the invariants they must keep |
| [`examples/demo/apps/boxoffice/spec/`](examples/demo/apps/boxoffice/spec/README.md) | Its TLA+ model: the two services, Kafka and the clock, checked by TLC over every interleaving |
| [`examples/demo/apps/quorum/`](examples/demo/apps/quorum/README.md) | The second subject system (examples 013 to 022, 057 to 074, 081 to 083): the pure kernels of a replicated system, Raft's vote rule and role machine, quorum arithmetic, backoff, a hybrid logical clock, last-writer-wins and a two-phase-commit coordinator, each with a contract, a property or a TLA+ model (two-phase commit checked for its invariants, its liveness and its refinement of transaction commit; Raft's elections for election safety under six configurations, the liveness of elections under fairness, the election restriction and vote replies that wait on the wire among them), verified by `jvmcontract` |
| [`examples/demo/apps/crosscut/`](examples/demo/apps/crosscut/README.md) | The third subject system (examples 023 to 033, 075 to 080): the kernels behind a Spring Boot service's cross-cutting concerns, the transaction interceptor's rules, a circuit breaker, a retry policy, a token bucket, an `Idempotency-Key` receiver with its TLA+ model, a Kafka partitioner and batch commit, a JWT validator's clock skew and a cache's expiry, verified by `jvmcontract` |
| [`examples/demo/apps/mica/`](examples/demo/apps/mica/README.md) | The fourth subject system (examples 034 to 056): the decision kernels of a small JVM written in Java, the class initialization procedure with its TLA+ model (checked for deadlock), the type checker's assignability relation, access control, `idiv` and `fcmp`, a `lookupswitch` bisection, the exception table, stack map frame offsets, the `Code` attribute's length, constant pool numbering, `max_stack`, javac's switch heuristic, a power-of-two table size and modified UTF-8, verified by `jvmcontract` |
| [`examples/demo/tools/contracts/`](examples/demo/tools/contracts/README.md) | The Java verifiers of examples 001 to 012: behavioural, regression and capability contracts, a CI gate that proves what changed and what did not |
| [`examples/demo/tools/build.py`](examples/demo/tools/build.py) | Runs every demo example and generates its page |
| [`examples/real-world/README.md`](examples/real-world/README.md) | The real-world examples: the pull requests verified so far, and the libraries to try next |
| [`examples/real-world/commons-numbers-223/`](examples/real-world/commons-numbers-223/README.md) | Apache Commons Numbers #223, the `ArithmeticUtils.pow` fix: the witness found from the bytecode alone, the Javadoc proved, and the change proved confined to the one input it names |
| [`examples/approaches.md`](examples/approaches.md) | The approaches by level (source, bytecode, native, distributed), and the plan for the demos |
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
