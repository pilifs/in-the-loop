# Java formal verification demos

Proofs of concept for formally verifying Java, from source code down to **JVM bytecode** and **native machine code**,
plus distributed-systems protocols running on Kubernetes.

These demos are inspired by [LLM-assisted formal verification at scale](https://www.anthropic.com/research/formal-verification),
which proved properties of compiled RISC-V binaries, not source code.
The demos ask what the equivalent pipelines look like for the JVM.

- [`docs/approaches.md`](docs/approaches.md) lists the approaches by level (source, bytecode, native, distributed), together with the plan for the demos.
- `demos/` holds the demos (coming soon).
- [`docs/traces.md`](docs/traces.md) explains the published LLM traces. Every Claude Code session has a manifest in `traces/<session-id>/`, and each commit points at its log's SHA-256 with an `LLM-Trace:` line.

## Setup (Ubuntu 24.04, native or WSL2, amd64 or arm64)

```bash
setup/ubuntu-wsl/install.sh          # default components; prompts for sudo once, for apt and Docker
exec bash                            # pick up PATH and docker group membership
setup/ubuntu-wsl/doctor.sh           # verify
```

Components are listed below. You can install any subset, for example `install.sh jvm provers`. `install.sh all` installs everything, including the optional components.

| Component | Installs |
|---|---|
| `devtools` | jj (Jujutsu, colocated with git) and gh |
| `system` | apt build tools, Docker Engine, CBMC/JBMC, Z3, .NET 8, opam, the RISC-V cross-compiler, qemu-user with binfmt, and kernel limits for kind |
| `jvm` | SDKMAN with Temurin 25 (default), Temurin 21, GraalVM CE 25 (native-image), Gradle and Maven |
| `k8s` | kubectl, kind, Helm and k9s |
| `verify` | TLA+ (TLC), Alloy, KeY, Jazzer, cvc5, Dafny and Boogie |
| `provers` | Lean 4 (via elan) and Sail (ISA specifications) |
| `rocq` *(optional)* | Rocq via opam. This is slow because it compiles from source. |
| `isabelle` *(optional)* | Isabelle, for Jinja/JinjaThreads JVM semantics (about 1 GB) |
| `acl2` *(optional)* | ACL2, for the M1–M6 JVM models |
| `angr` *(optional)* | angr, for binary symbolic execution, in a venv |

For trace capture, also run `infra/langfuse/up.sh` and `python3 tools/traces/sync.py init`. [`docs/traces.md`](docs/traces.md) has the details.

User-level tools go in `~/.local/bin` and `~/tools`. The installer adds a marked block to `~/.bashrc`.

## License

Code is licensed under Apache-2.0 ([LICENSE](LICENSE)).
The documentation in `docs/` and the traces in `traces/`, including the published logs they point at, are licensed under CC BY 4.0 ([LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0)).

**WSL notes:**
- systemd must be enabled. Put `[boot] systemd=true` in `/etc/wsl.conf`, then run `wsl --shutdown`.
- The installer sets up native Docker Engine inside the distro. If Docker Desktop is installed, quit it or disable its WSL integration, so that two daemons don't compete.
