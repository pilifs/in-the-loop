# JBMC 6.11.0's output, for its phases

Real runs of JBMC 6.11.0 (`cbmc-6.11.0`, x86_64 Linux), captured on 2026-11-06 for Phase 1a of
[`engine-priorities.md`](../../../../llm-dlc/loops/engine-priorities.md): `lib/src/phases.rs` reads JBMC's phases from
them, and its tests check that the phases are exclusive and add up to the run's time. Every run used the adapter's
options: `--trace --throw-runtime-exceptions --unwinding-assertions --json-ui --timestamp monotonic
--no-refine-strings --sat-solver cadical`.

| File | Run | How it ended | Seconds |
|---|---|---|---:|
| `proof.log` | `jvmcontract equivalence --engine jbmc --gaps strict --timeout 60 --unwind 16 --max-array-length 8` on the benchmark's `held/prefix-sums` (`lib/benchmark/src/v1`, `v2`) | verified | 3.160 |
| `timeout.log` | the same with `--timeout 2` | cut off by its budget of 1.921 s while solving | 1.980 |
| `memory.log` | the same on `held/reverse`, under `JVMCONTRACT_JBMC_MEMORY_MB=700` | out of memory, in the solver call before CaDiCaL started | 1.104 |
| `two-calls.log` | `jbmc Two --function Two.split --unwind 16` on [`Two.java`](Two.java), with the options above | two counterexamples, one solver call each | 0.010 |

The first three are the adapter's logs (`jbmc.log` in the work directory), with the line it adds when it stops a run;
the seconds are the run's, as the adapter timed it (`search.runs[].seconds`). The last is JBMC's output alone, timed
around the process.

What they show, which `phases.rs` relies on:

- **`Runtime Solver` includes `Runtime Post-process`.** In `proof.log`, `Running propositional reduction` is printed at
  10919.279425 and `Runtime Solver: 2.95533s` at 10922.234776, 2.955351 s later: the solver's time is that whole
  interval. `Runtime Post-process: 0.175236s` is printed inside it, at 10919.454702, 0.175277 s after the call began.
  Adding both, as `phases.rs` did before, counted the post-processing twice.
- **A solver call that runs out of memory before CaDiCaL starts** prints `Runtime Solver` but neither
  `Runtime Post-process` nor CaDiCaL's `N variables, M clauses` (`memory.log`): its time was post-processing.
- **A later solver call in the same run** has no `Runtime Post-process`, only CaDiCaL's line (`two-calls.log`).
- **A run that is killed loses its last message**: JBMC writes each JSON item once the next one begins, so
  `timeout.log` ends at `Runtime Post-process`, without the `N variables, M clauses` printed just after it.
