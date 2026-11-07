# Feature loop: engine-priorities

Started 2026-11-07 00:11:40 UTC, no limit on cycles, session c2bd9df4-5f20-4312-95a4-3eb88a60e0cd, claude-opus-5-5 at high effort, after change lxlxyvstqozvxtvksoswvvoyrwsnkuzn.

> Work on the brief in `llm-dlc/loops/engine-priorities.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'lxlxyvstqozvxtvksoswvvoyrwsnkuzn..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `llm-dlc/loops/engine-priorities.md` at sha256 c5da523862fa9c9770691fa2f7c09b2c18e27b8f4dc37a88b1b4aa1b5177434f.

After each commit the session decides whether to go on:

> The reconcile comes first; don't stop before the merge is committed unless a stream is still running or the merge needs the user. Keep the last line of Progress a status, as the stream briefs describe: `working`, `waiting on jobs ID ...` (stop then: `run-streams.sh` runs this loop again once they are back), `done` when the brief is finished, or `blocked: ...` with what needs the user. Your last cycle's commit sets `done` or `blocked`, and the Progress above it is what the user reads first. After it, go on while a cycle can still realize a substantial part of the reasonably attainable value of this brief. The user prefers the loop to run as long as possible, so when in doubt, continue. Phases 1, 2 and 5 are the brief's core: don't stop before they're done unless they are blocked on the user or on a job. Stop when most of the rest has been realized: the remaining steps are small or speculative next to what is done, or what is left needs the user's input (a decision, network access) and has been recorded as deferred. Don't go on to polish, and don't stop while a step that needs nothing from the user is still open.

## Commits

- cycle 1, 2026-11-07 00:22:04, `qvtplyrruqmm`: Fold the engine streams' Progress into the engine-priorities brief
  - decided to continue: The merge is committed, but Phase 5, one of the brief's core phases, isn't done: example 071's two proofs still have no verdict under strict. The fix, a stub check that follows paths in `jbmc_gaps.rs`, needs nothing from you. Other open steps need no input either and matter more than polish: the `declaring` false proof under strict, applying the contract library recorded on JDK 25.0.5, the 4c coverage inventory, and the examples' notes.
- cycle 2, 2026-11-07 00:47:14, `xrrxwxnykxws`: Take the contract library's JDK 25.0.5 records from job 20261106-203501
  - decided to continue: Phase 5 is still unfinished: example 071's two proofs have no verdict under strict until `jbmc_gaps.rs` checks stubs along paths, and that work plus its rerun job needs nothing from you. There is also an open false proof: on the `declaring` case, `--engine jbmc` claims a proof under strict that the JVM refutes, so `jbmc_gaps.rs` should refuse it. Neither is polish; after them come 4c and the examples' notes.
- cycle 3, 2026-11-07 01:07:55, `pkuyvwwpopls`: JBMC runs class initializers the JVM does not: the preflight names them as extra-initializer and refuses a JBMC proof through one (verification pending)
  - decided to continue: Phase 5, one of the brief's core phases, is still not done: 071's two proofs only stand under strict once `jbmc_gaps.rs` checks for stubs along the paths a proof can take, not across the whole call graph. That work and its rerun of 071 and 013 need nothing from the user, and job `20261107-010728` doesn't block them. After that, 4c's coverage inventory and the examples' notes are also open and need no input, so a cycle can still do real work.
- cycle 4, 2026-11-07 01:20:47, `qsnwzrrzutyy`: A stub JBMC's call graph reaches on no path the proof takes is no gap: the preflight reads JBMC's symbolic execution (verification pending)
  - decided to continue: Phase 5's last piece is now committed. Whether it holds depends on job `20261107-012013`, and job `20261107-010728` is also still running, but neither blocks the other open work. Item 4, the coverage inventory that Phase 4's done-criterion requires, is still open and needs nothing from the user. So are item 6 (Bitwuzla's version in 1b's record) and item 7 (the `test_build.py` and `test_performance.py` failures), so a cycle can still do substantial work.
- cycle 5, 2026-11-07 01:27:22, `unvpruotttxv`: A coverage inventory of the recorded JBMC examples: which engine decides each obligation under strict, what stops the other, and the own checker's next extensions ranked (Phase 4c)
  - decided to continue: With 4c committed, Phase 4's done-criterion is met, and the core phases now wait only on jobs `20261107-010728` and `20261107-012013`. Several steps that need nothing from the user are still open and worth a cycle each. Items 9 (an exact `numberOfLeadingZeros` and the per-entry loop bound) would let the own checker decide 037, 127 and 052. Item 6 is Bitwuzla's version in 1b's record, and item 7 is the Python suite failures.
- cycle 6, 2026-11-07 01:47:02, `xmunlmmrqqts`: A result's SAT solver record names the solver the checks ran on: Bitwuzla, with its version, library digest and build, when JVMCONTRACT_SOLVER chooses it
  - decided to continue: The loop should go on. Job `20261107-010728` came back failed, and triaging it once it's collected is substantial work that needs nothing from the user. Phase 5's core criterion, 071's two proofs under strict, still waits on `-012013`. Item 9 is also open and needs nothing from the user: an exact `numberOfLeadingZeros` and the loop bound counted per entry of a loop would let the own checker decide 037, 127 and 052. Item 7, the `test_build.py` and `test_performance.py` failures, is open too.
- cycle 7, 2026-11-07 02:31:56, `vrkpmtqvyosm`: The own checker computes Integer and Long.numberOfLeadingZeros exactly, so examples 037 and 127 meet no gap under strict (verification pending)
  - decided to continue: The loop should go on. Phase 5 is part of the brief's core, and its last criterion is still open. Job `-012013` came back with 071's first two obligations still giving no verdict, even with no gap left (VF-005). Finding why needs nothing from the user and is not waiting on a job. Also open and needing nothing from the user: VF-009 (JBMC's spurious refutations of `boomTwice` and `enumBroken` under `--confirm`), the unwinding bound counted per loop entry, which would decide 052, and items 7 and 8.
- cycle 8, 2026-11-07 02:49:41, `xmslpytzqtlx`: JBMC's preflight reads its goto listing by instruction index, not byte offset, so 071's two proofs are no longer refused on initializers JBMC does not run (verification pending)

## Summary

# Engine-priorities loop: summary of the run (8 cycles, 2026-11-06 to 2026-11-07)

The run covers 37 revisions, from `nzxrwvum` to `xmslpytz`. They include the two engine streams (engines-jbmc and engines-native) that were merged into this loop, the merge itself, and this loop's own work after it. The working copy is clean, and nothing has been pushed.

## Commits, oldest first

### Measuring and recording (Phases 1a–1c, 6a–6b)
- **`snprkxtx`: JBMC's phase times are no longer double-counted.** "Runtime Post-process" is counted once, and a run whose phases add up to more than its own time is flagged `phasesExcess`. Tested against real JBMC 6.11.0 output kept as fixtures. Job `-192959` failed on its own grep and was resubmitted as `-194328`, which passed; `tvquoumw` records that CBMC's source nests the timers as assumed.
- **`olttywtt`: every result names its SAT solver, version and configuration**, on both engines. Covered by unit and runner tests; the installed JBMC links CaDiCaL 3.0.0.
- **`xzrpqnvr`:** proposes the 7 mangled C++ symbol names found in session `7b8a1d3b`'s logs for the allow list. They need your decision (see below).
- **`wnktqxrt`: the own checker's solver calls can be recorded as replayable incremental CNF transcripts.** A 460-call proof replays in 0.178 s against 0.179 s recorded. The commit also fixed a compile race in `conformance.rs`.
- **`syntvmqp`: the own checker's SAT solver now sits behind a narrow `Sat` interface.** Unit tests pass, and transcripts replay with no contradiction.
- **`nzxrwvum`, `mwxvlkzz`: a Bitwuzla 0.8.2 build from source.** The first job (`-192008`) failed because the installed binary couldn't load `libcadical.so`. CaDiCaL is now linked in statically, and job `-194049` passed.

### JBMC staging and the benchmark (Phases 2a–2c)
- **`uykqwxvr`: `--jbmc-staging` chooses `staged`, `full-range` or `tight`.** Covered by unit tests and an end-to-end test against a stand-in JBMC.
- **`xtkwolst`: the benchmark compares the three policies**, proofs and counterexamples separately. Job `-201041` passed.
- **`pxqzmomt`: JBMC doesn't mask right-shift distances, which gave false proofs.** The preflight now names an `unmasked-shift` defect and refuses a JBMC proof through one. Two conformance claims reproduce the false proofs. The fixture test fails with the detection disabled.
- **`wvkxpmzx`: `full-range` is now JBMC's default**, on job `-201041`'s evidence: the same proofs, about half the time on the hard cases, and counterexamples in 9 s against 27 s.

### JBMC defects and `--confirm` (Phase 3)
- **`svvrpymr`: JBMC lets a runtime exception escape the handler that catches it on the JVM.** There are two shapes: one is JBMC's, the other comes from our stubbed exception classes. The preflight names both and refuses a JBMC proof through either. Two upstream reports are drafted, not filed. Job `-203452` failed and led to the next commit.
- **`xzvyuwxp`: under `--confirm`, a JBMC refutation through a named defect whose witness doesn't reproduce is now no verdict.** A new test fails with the fix disabled. The rerun, `-231317`, passed with all 12 earlier disagreements gone.

### Strict tables for the 41 recorded JBMC examples (Phases 4a–4c)
- **`xrrrwlrm`: both engines run under `--gaps strict` and are tabulated per obligation.**
  - `tokyzsls` and `xyplqrtn` fix the result schema, which refused the new `sat` and `phasesExcess` fields. Those fixes stopped jobs `-204220` and `-231837`.
  - `pmoympwn` records the passing run, `-000039`. Of 43 obligations, the engines agree on all 35 they both decide. JBMC alone decides 5, the own checker alone none, and neither 3.
- **`wnxlynrs` (4b): class initializers counted by shape.** All 49 in the apps are enums and their switch maps.
- **`unvpruot` (4c): `examples/coverage.md`.** It says which engine decides each obligation and why the other doesn't, and ranks the own checker's next extensions. Built with `gap_table.py --inventory`, which has unit tests.

### The own checker's coverage (Phase 5)
- **`kumppqkz`: the own checker runs application class initializers as the JVM specification does** (JVMS 5.5). That includes `ExceptionInInitializerError` and then `NoClassDefFoundError`. 8 new conformance cases (16 claims) agree with the JVM on JDK 25.0.5.
- **`knlrwnqu`: models of `Enum.<init>`, `List.of` and `List.copyOf` for JBMC**, checked on the JVM.
- **`ulstzomt`: enums now run in the own checker**: arrays of references, Enum's model and switch maps. Suites pass.

### Solvers (Phases 6c–6d)
- **`osspkxkz`, `wqskvlym`, `ulsqmxuq`: Bitwuzla behind the solver interface**, chosen with `JVMCONTRACT_SOLVER`, with options by name and an opt-in word-level mode (`bitwuzla-words`). Covered by unit and engine tests on both solvers.
- **`tpytwvmv` (6d): a recommendation to keep CaDiCaL with bit-blasting as the default**, written up in `lib/solvers/README.md`. Jobs `-224616` and `-230455` passed:
  - given our clauses, Bitwuzla is 2 to 43 times slower;
  - given word-level terms, it is at most 1.93 times faster.

### Merge and this loop's work
- **`lukovtll`, `ulsslrtx`, `pkyqqotr`, `qvtplyrr`: the two streams' traces recorded, the streams merged, and their Progress folded into one brief.** One merge conflict was resolved and two tests fixed.
- **`xrrxwxny`: the contract library's JDK 25.0.5 records taken from job `-203501`.** This clears the 12 conformance claims that failed for want of a record.
- **`pkuyvwwp`: JBMC runs class initializers the JVM doesn't, which gave a false JBMC proof** (`declaring/2`: n + 107 where the JVM returns n + 7). The preflight now names this `extra-initializer`. A third upstream report is drafted.
- **`qsnwzrrz`: a stub that JBMC's call graph reaches but no path of the proof enters is no longer a gap.** The preflight now reads JBMC's symbolic execution, without solving anything. Tested on real JBMC.
- **`xmunlmmr`: Bitwuzla's solver record names Bitwuzla.** It used to say CaDiCaL even when Bitwuzla ran. Reproduced before the fix, then covered by a unit test.
- **`tnxrkmyk`: results of jobs `-012013` and `-010728` recorded.** `-012013` closed VF-008; `-010728` opened VF-009.
- **`vrkpmtqv`, `vpvqksyo`: the own checker computes `numberOfLeadingZeros` exactly**, with reproducers checked on the JVM first. Job `-022319` passed: examples 037 and 127 are now established under strict with no gap, and the 152-claim corpus agrees with the JVM.
- **`xmslpytz`: fixes VF-005.** The preflight looked up JBMC's listing by byte offset, but JBMC numbers instructions by their position in the method.
  - The wrong lookup invented the two initializer defects that blocked example 071's first two proofs.
  - It also missed real ones, a false-proof risk.
  - A new test on JBMC's real listing fails with the old lookup and passes with the fix. Unit 179, conformance 9 and integration 64 pass.

## Verification jobs
- **Running: `20261107-024759`.** It reruns examples 071 and 013 under strict, plus the corpus, after the VF-005 fix. VF-005 closes if 071's proofs stand; 071's and 013's notes then need updating.
- **Failed and still open: `20261107-010728` (VF-009).** Under `auto --confirm`, JBMC refutes `boomTwice` and `enumBroken` at n = 0. Both run an initializer that throws. Not yet triaged; it is the next item.
- **Failed and superseded by passing reruns:** `-192008`, `-192959`, `-203452`, `-203501`, `-204220`, `-231837`, and `-012013`, whose rerun is the running `-024759`.
- The report lists 50 failed jobs in total. The others are from before this run, such as `20261103-002843` (a Mica patch that no longer applies) and `20261103-010716`.

## Warnings to judge before pushing
`sync.py check` reports 0 errors and 15 warnings:
- **7 allow-list proposals** await you. They are the mangled C++ symbol names (MiniSat and CaDiCaL classes) from reading `/usr/bin/jbmc`'s strings. Approve them in your terminal with `python3 llm-dlc/tools/sync.py allow approve` if you agree they're harmless.
- **14 logs of session `7b8a1d3b`** are each flagged `long-token ×14` for the same `_ZZ…` symbols. They clear once you decide on the proposals.

## Needs your input
- **A push**: `python3 llm-dlc/tools/sync.py push --bookmark main`, after judging the warnings above.
- **Three upstream JBMC reports, drafted and not filed**, in `lib/tests/fixtures/jbmc-defects/README.md`:
  - exceptions escaping their handler;
  - unmasked right shifts;
  - extra class initializers.

  Filing them is your call.
- **Which engine the recorded examples use.** The JBMC examples still record `--engine jbmc`. Whether they move to `native` or `auto` hasn't been decided; `examples/coverage.md` has the data for it.
- **Disk:** `../in-the-loop-jbmc` (0.5 GB) and `../in-the-loop-native` (2.2 GB) are the forgotten stream workspaces, with their run records. They're yours to delete.

## Still open, needing nothing from you
These are in the brief's Next list:
- VF-009 triage;
- the `test_build.py` (35 `KeyError: 'verdict'`) and `test_performance.py` failures, both from before the merge;
- the `Pricing#total` wall-clock flake;
- the encoding that falsely flags short runs as `phasesExcess`;
- the conformance job for the native stream's step 3 cases;
- the own checker's unwinding bound counted per entry of a loop (example 052).

The brief's status is still `working`.

Ended 2026-11-07 02:51:53 after 8 cycle(s).
