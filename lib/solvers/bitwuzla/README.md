# Bitwuzla, for the solver comparison

Phase 6 of [`engine-priorities.md`](../../../llm-dlc/loops/engine-priorities.md) puts
[Bitwuzla](https://github.com/bitwuzla/bitwuzla) against the CaDiCaL the own checker links (the `cadical` crate's
1.9.5), first on the engine's bit-blasted clauses and then on word-level terms. Nothing in `jvmcontract` depends on it.

[`build.sh`](build.sh) builds a pinned release from source as a verification pipeline job, since it fetches from the
network and takes minutes:

- It installs into `~/tools/bitwuzla/bitwuzla-VERSION`, with `~/tools/bitwuzla/current` pointing at it.
- The library is shared, with the C API's headers and `bitwuzla.pc`. Meson drops the rpath on install, so put the
  record's `libDir` on `LD_LIBRARY_PATH` to run the binary or link the library.
- Meson and ninja come from a venv inside the job. CaDiCaL and SymFPU come from Bitwuzla's own wrap files, at the
  versions its release pins.

[`build.json`](build.json) is the record the job brings back:

- the version, the tag's commit, and the source tarball's sha256;
- the subprojects from their wrap files, with their URLs and digests, the CaDiCaL it links among them;
- GMP, the compiler, the build tools and the machine;
- the answers to three smoke queries, plus the version the C API reports through `pkg-config`.

A later job that uses Bitwuzla requires this record and its install. If the install is missing on a machine, rerun
the build job there.
