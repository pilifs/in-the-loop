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
