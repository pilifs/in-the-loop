# Java formal verification demos

Proofs of concept for formally verifying Java, from source code down to **JVM bytecode** and **native machine code**,
plus distributed-systems protocols running on Kubernetes.

These demos are inspired by [LLM-assisted formal verification at scale](https://www.anthropic.com/research/formal-verification),
which proved properties of compiled RISC-V binaries, not source code.
The demos ask what the equivalent pipelines look like for the JVM.

The repo has two parts:

## [`examples/`](examples/README.md): formal verification

**Start here.** Numbered examples of code changes run through a formal verifier, each with the code before and after, the verdict, the counterexamples, the risk, and a comparison with the existing tests.
The folder also holds everything the examples need:

| Path | Content |
|---|---|
| [`examples/README.md`](examples/README.md) | The table of contents |
| [`examples/approaches.md`](examples/approaches.md) | The approaches by level (source, bytecode, native, distributed), and the plan for the demos |
| [`examples/apps/boxoffice/`](examples/apps/boxoffice/README.md) | The subject system: concert ticketing as two Spring Boot services with Kafka and MongoDB, and the invariants they must keep |
| [`examples/apps/boxoffice/spec/`](examples/apps/boxoffice/spec/README.md) | Its TLA+ model: the two services, Kafka and the clock, checked by TLC over every interleaving |
| [`examples/tools/contracts/`](examples/tools/contracts/README.md) | The verifiers: behavioural, regression and capability contracts, a CI gate that proves what changed and what did not |
| [`examples/tools/build.py`](examples/tools/build.py) | Runs every example and generates its page |
| [`examples/setup/`](examples/setup/README.md) | The toolchain installer for Ubuntu and WSL2 |

## [`llm-dlc/`](llm-dlc/README.md): the LLM development lifecycle

A meta example. This repo is written with an LLM, and every commit is published with the session that made it: a readable summary, metadata, and the full transcript, linked from the commit message.
The folder holds the procedure and session index, the [specification](llm-dlc/specification.md), the published traces, the tooling that captures and checks them, and the CDN and Langfuse infrastructure.

## License

Code is licensed under Apache-2.0 ([LICENSE](LICENSE)).
`examples/approaches.md`, `llm-dlc/specification.md`, and the session records in `llm-dlc/` (`README.md`, `index.json`, `summary-template.md` and `traces/`, including the published logs they point at) are licensed under CC BY 4.0 ([LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0)).
