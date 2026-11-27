# in-the-loop

**Formal proofs of changes to Java code, made by models and checked by a model checker.**

Given a change to Java code (a pull request, a commit, a release), the work here states what the change must keep
and what it is meant to do as claims, and a model checker then proves each claim from the compiled bytecode, or
hands back the input where it breaks. Nobody writes a specification. The repository holds the verifier, the
changes it has been run on, and the whole record of how models built both.

The work is done in **runs**: one agent works toward one outcome while a watcher session outside it judges, after
each of the agent's context windows, whether it gets another. A person starts a run in this repository with
`/orchestrate-run` ([`.claude/skills/orchestrate-run`](.claude/skills/orchestrate-run/SKILL.md)), from a prompt, a
brief, or a list of pull requests that is first written into a brief.

Until 2026-11-27 this page offered a plugin, `/in-the-loop:prove-java-change`, which installed a released copy of
the repository on a user's machine and proved a change there. It is retired, with its last release, 0.10.0:
[`llm-dlc/retired.md`](llm-dlc/retired.md#plugin-and-runtime-mode) says what it was and where to read it. There is
no installable product at the moment.

## Three answers, and none is the model's opinion

The model writes the claims and drives the tools. The answer to each claim comes from a model checker.

| Answer | What it means |
|---|---|
| **Established** | The claim holds for every input within the bounds the report states, not for a sample of them |
| **Refuted** | A concrete input, shrunk to a small one and run on a real JVM. It is a finding about your change |
| **Left open** | The tools could not decide, and the report says why. It never counts as a pass |

[Example 285](examples/285-spring-boot-cve-2023-34055-unbounded-http-method-labels/README.md) is the first real
target, a Spring Boot security fix (CVE-2023-34055, 2.7.17 → 2.7.18) proved on the released JARs:

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

Each part's page has its own layout that says where things are. The folders will be reorganized at some point, so
follow the links from these pages instead of remembered paths.

| Where | What it is | Its layout |
|---|---|---|
| [`examples/`](examples/README.md) | 183 changes run through a formal verifier, each with its verdict and the input or trace behind it: 159 written for small systems built to be provable, 24 from published libraries. | [Find an example](examples/README.md#find-an-example), [Layout](examples/README.md#layout) |
| [`lib/`](lib/README.md) | `jvmcontract`, the verifier, in Rust: a class-file reader, a bytecode interpreter and its own bounded model checker, with JBMC as a second engine. It derives contracts without a JVM and proves without `javac` | [Layout](lib/README.md#layout) |
| [`verification/`](verification/README.md) | The pipeline: proofs are queued as jobs, not run inside a session, and run under memory and CPU caps, each with a recorded result | [Layout](verification/README.md#layout) |
| [`llm-dlc/`](llm-dlc/README.md) | How the repository is built: runs and the tools under them, every commit published with the redacted session that made it, and [what was retired](llm-dlc/retired.md) | [Layout](llm-dlc/README.md#layout) |

## For agents

- [`CLAUDE.md`](CLAUDE.md) is the procedure: every session is traced and published with the commits it made.
- To find examples close to a task: `python3 examples/tools/find.py`
  ([`examples/README.md`](examples/README.md#find-an-example)).
- Proofs and model checks are queued as jobs
  ([`verification/README.md`](verification/README.md#for-agents-making-changes-submitting-a-job)). `CLAUDE.md` says
  the little that may run inline.
- A run is started by a person, or by a watcher at a person's word, with `/orchestrate-run`; an agent never starts
  one as a step of its own work. [`llm-dlc/retired.md`](llm-dlc/retired.md) lists the workflows that came before it.

## Background

The work is inspired by [LLM-assisted formal verification at scale](https://www.anthropic.com/research/formal-verification),
which proved properties of compiled RISC-V binaries, not source code. This repository asks what the equivalent looks
like for the JVM. It started as a set of demos, from source code down to bytecode and native code, with distributed
protocols model-checked in TLA+; [`examples/approaches.md`](examples/approaches.md) has the approaches by level.

It is written almost entirely by models working in unattended runs, and every session is public: each commit
message links the session that made it and carries the SHA-256 of its log
([`llm-dlc/README.md`](llm-dlc/README.md)).

## License

Code is licensed under Apache-2.0 ([LICENSE](LICENSE)).
`examples/approaches.md`, `llm-dlc/specification.md`, and the session records in `llm-dlc/` (`README.md`, `index.json`, `summary-template.md` and `traces/`, including the published logs they point at) are licensed under CC BY 4.0 ([LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0)).
