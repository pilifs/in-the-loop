# Examples

Two kinds of examples, in two folders. Both run a formal verifier over compiled Java and report a verdict with its witness: *verified*, *violation* with the input or the trace, or *unverifiable* with the reason. They differ in where the code comes from.

| Folder | What it holds | Whose code |
|---|---|---|
| [`demo/`](demo/README.md) | 80 numbered code changes, each run through a verifier, with the verdict, the witness, the risk, and what the existing tests did | Four subject systems written for this repository: a ticketing system, a library of replication kernels, the cross-cutting kernels of a Spring Boot service, and a small JVM. Under [`demo/apps/`](demo/README.md#layout) |
| [`real-world/`](real-world/README.md) | Pull requests to published Java libraries, verified from their bytecode with the [`/verify-bytecode`](../plugins/jvmcontract/README.md) skill: one folder per pull request, with the report and the commands that reproduce the proofs | The libraries' own: Apache Commons Numbers so far, with a list of libraries to try next |

The demo examples are constructed. Each is a change a developer could plausibly make, chosen to show what one verification approach catches that code review and tests miss, or lets through. The subject systems exist so that the examples can patch them, and so that a reader can run every example end to end on one machine, from the patch to the verdict. **Start with [`demo/`](demo/README.md)** to see what each approach does.

The real-world examples take pull requests as they came, to libraries with their own builds, tests and Javadoc. They show what the same verifiers do when nothing was arranged for them: which changed methods a proof reaches, how long it takes, and what has to be left to the module-level contracts. **Go to [`real-world/`](real-world/README.md)** to see the verifiers on code nobody here wrote, or to pick the next library to try.

Shared by both:

| Path | Content |
|---|---|
| [`approaches.md`](approaches.md) | The verification approaches by level (source, bytecode, native, distributed), numbered as the examples cite them, and the research plan |
| [`setup/`](setup/README.md) | The toolchain installer for Ubuntu and WSL2: the JDK, JBMC, TLC, Rust and the rest |
| [`../lib/`](../lib/README.md) | `jvmcontract`, the Rust verifier behind both kinds of example |
