# Setup

The toolchain for the examples and for the approaches in [`approaches.md`](../approaches.md).
The examples need Java 25, JBMC (from the `system` component) and TLC (from `verify`), plus Docker for Box Office's end-to-end tests; the rest is for the approaches still to be tried.

## Ubuntu 24.04 or 26.04, amd64 or arm64

On a machine, a VM or WSL2:

```bash
examples/setup/ubuntu/install.sh      # default components; prompts for sudo once, for apt and Docker
exec bash                             # pick up PATH and docker group membership
examples/setup/ubuntu/doctor.sh       # verify
```

Components are listed below. You can install any subset, for example `install.sh jvm provers`. `install.sh all` installs everything, including the optional components.

| Component | Installs |
|---|---|
| `devtools` | jj (Jujutsu, colocated with git), gh, Node.js, and Rust (rustup, for [`lib/`](../../lib/README.md)) |
| `system` | apt build tools, Docker Engine, CBMC/JBMC, Z3, the .NET SDK, opam, the RISC-V cross-compiler, qemu-user with binfmt, and kernel limits for kind |
| `jvm` | SDKMAN with Temurin 25 (default), Temurin 21, GraalVM CE 25 (native-image), Gradle and Maven |
| `k8s` | kubectl, kind, Helm and k9s |
| `verify` | TLA+ (TLC), Alloy, KeY, Jazzer, cvc5, Dafny and Boogie |
| `provers` | Lean 4 (via elan) and Sail (ISA specifications) |
| `rocq` *(optional)* | Rocq via opam. This is slow because it compiles from source. |
| `isabelle` *(optional)* | Isabelle, for Jinja/JinjaThreads JVM semantics (about 1 GB) |
| `acl2` *(optional)* | ACL2, for the M1–M6 JVM models |
| `angr` *(optional)* | angr, for binary symbolic execution, in a venv |

User-level tools go in `~/.local/bin` and `~/tools`. The installer adds a marked block to `~/.bashrc` (and `~/.zshrc`
when zsh is the shell).

**What differs between releases** is decided in one place, `release_profile` in `install.sh`, and nowhere else. Any
other release stops the installer until it has a case of its own there.

| | 24.04 | 26.04 |
|---|---|---|
| .NET SDK | 8 | 10, with launchers that let Dafny and Boogie (built for 8) roll forward |
| user-mode QEMU | `qemu-user-static` | `qemu-user` and `qemu-user-binfmt` |
| CBMC `.deb` | 24.04's | 26.04's once Diffblue publishes one, else 24.04's |
| coreutils | GNU, the default | GNU linked into `~/.local/lib/gnu-coreutils` and put first on `PATH` (`.bashrc`, `.profile`, `.zshrc`), since the default uutils behave differently (`timeout -s KILL` exits 124, not 137) and `build-essential` depends on them |

**WSL notes:**
- systemd must be enabled. Put `[boot] systemd=true` in `/etc/wsl.conf`, then run `wsl --shutdown`.
- The installer sets up native Docker Engine inside the distro. If Docker Desktop is installed, quit it or disable its WSL integration, so that two daemons don't compete.
