# Bitwuzla, for the solver comparison

Phase 6 of [`engine-priorities.md`](../../../llm-dlc/loops/engine-priorities.md) puts
[Bitwuzla](https://github.com/bitwuzla/bitwuzla) against the CaDiCaL the own checker links (the `cadical` crate's
1.9.5), first on the engine's bit-blasted clauses and then on word-level terms. Nothing in `jvmcontract` links it:
[`src/bmc/bitwuzla.rs`](../../src/bmc/bitwuzla.rs) loads the C API at run time, from `JVMCONTRACT_BITWUZLA` (the library, or
the install directory) or else `~/tools/bitwuzla/current`, and refuses a version other than 0.8.2, whose enum values it
is written with. `JVMCONTRACT_SOLVER=bitwuzla` runs a process's checks on it, and `jvmcontract transcript --solver
bitwuzla FILE` replays a transcript on it. Either takes Bitwuzla's options after a colon, by the long names of its
command line: `bitwuzla:preprocess=0,rewrite-level=0`. The binding reads each option's range or modes from the
library (`bitwuzla_get_option_info`) and refuses a value outside them before setting it, since the C API aborts the
process on one; it refuses `produce-models`, `time-limit-per` and `sat-solver`, which it sets itself, and string
options. The solver's signature, which results and transcripts record, lists the options set.

[`../compare.py`](../compare.py) is the comparison of Phase 6c on the engine's clauses: the benchmark's five
workloads where the formula's size dominates (binary search, examples 141 and 142, reverse, prefix sums), each as a
full check under strict and as CaDiCaL's transcripts replayed, on CaDiCaL, on Bitwuzla's defaults and on Bitwuzla
with `preprocess=0`, three times each. It reuses `lib/benchmark/run.py`'s cases and command lines without changing
them, and writes `bit-blasted.json` and `bit-blasted.md` to its `--out`. It runs as a pipeline job; its tests
(`python3 -m unittest lib/solvers/test_compare.py`) run nothing.

`JVMCONTRACT_SOLVER=bitwuzla-words` (with options as above) is the word-level prototype: the engine gives Bitwuzla
its gates as Boolean terms and each arithmetic operation, comparison, shift by a symbolic amount and `ite` of two
values as one bit-vector term (`Terms` in [`src/bmc/sat.rs`](../../src/bmc/sat.rs)), instead of bit-blasting them,
and Bitwuzla bit-blasts what its rewriting leaves. Arrays stay the engine's bounded cells, read and written through
`ite`s over the index, with no array theory. Such a check keeps no transcript, since there are no clauses to record.
`compare.py --words` runs the same full checks on CaDiCaL and on it, with and without `preprocess`, and writes
`word-level.json` and `word-level.md`.

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
