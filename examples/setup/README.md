# Setup

The toolchain for the examples and for the approaches in [`approaches.md`](../approaches.md).
The examples so far need only Java 25 (and Docker for Box Office's end-to-end tests); the rest is for the approaches still to be tried.

## Ubuntu 24.04, native or WSL2, amd64 or arm64

```bash
examples/setup/ubuntu-wsl/install.sh          # default components; prompts for sudo once, for apt and Docker
exec bash                                     # pick up PATH and docker group membership
examples/setup/ubuntu-wsl/doctor.sh           # verify
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

User-level tools go in `~/.local/bin` and `~/tools`. The installer adds a marked block to `~/.bashrc`.

**WSL notes:**
- systemd must be enabled. Put `[boot] systemd=true` in `/etc/wsl.conf`, then run `wsl --shutdown`.
- The installer sets up native Docker Engine inside the distro. If Docker Desktop is installed, quit it or disable its WSL integration, so that two daemons don't compete.
