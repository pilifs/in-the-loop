# Brief: decide by the solver whether a proof enters a JBMC stub

**Drafted 2026-11-07, and chosen by the user that day** over a `String.format` model ([Decisions](#decisions)). It
starts once the cleanup loop's merge is committed ([`cleanup.md`](cleanup.md)): it changes `lib/src/jbmc_gaps.rs`, which
the cleanup jbmc stream also changes.

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh), run alone in the default workspace:
`llm-dlc/tools/feature-loop.sh llm-dlc/loops/stub-reachability.md`. It makes JBMC's gap preflight count a stub as
entered only when a path the proof checks can reach it. Then it closes VF-015, which waits on exactly that.

**Inputs.** Read these in full before the first piece of work of every cycle:
- this brief;
- `lib/src/jbmc_gaps.rs`'s module doc and `preflight_untimed`, `symbolic`, `entered` and `find_told`, at the merge;
- `verification/findings.md`'s entry VF-015, and the cleanup native stream's N3 in `cleanup.md`'s folded Progress.

## Direction

- **Sound first.** The JVM is the semantic reference, and only JBMC's `VERIFICATION SUCCESSFUL` is a JBMC proof.
- **A gap is left out only on evidence.** A stub is left out of the gaps only when the solver shows that no path within
  the proof's bounds and assumptions enters it. When the check can't tell (a timeout, an unknown, unreadable output),
  the stub stays a gap, as today.
- **`--gaps strict` keeps its meaning**: a proof that enters a stub is no verdict. Only the count of what "enters"
  becomes precise.
- **No model of `String.format`** ([decision 1](#decisions)). Under `--no-refine-strings`, JBMC can't read a format
  string's contents, so a model would be either unsound (assuming every format string is well formed and every
  `toString` pure) or a source of spurious refutations in equivalence checks.

## Where it starts from

Recounted at the cleanup jbmc stream's `@-` on 2026-11-07. Recount it at the merge.
- **The listing.** The preflight first lists JBMC's goto program (`--show-goto-functions`), whose call graph takes
  every branch.
- **The symbolic run.** When that graph reaches a stub, the preflight runs JBMC's symbolic execution alone
  (`symbolic_command`: `--program-only`, with the proof's `--unwind`). A stub none of whose locations appears in the
  formula is left out (`entered`, `Found::unreached`).
- **Why that falls short.** Symbolic execution drops a branch only when it simplifies the condition to false. A
  condition the solver would decide is kept, so is a stub behind an `--assume`.
- **The case.** VF-015's job `20261107-165827-…`, at step 3, runs
  `prove Hex#toDigit --assume 'ch == 1632' --assert 'result == 0'` on commons-codec's old `Hex`:
  - JBMC proves it;
  - the preflight names `String.format(String, Object[])` as entered, called by
    `DecoderException(String, Object...)` on `toDigit`'s exception path;
  - so strict refuses the proof;
  - yet with `ch == 1632`, `Character.digit` (the model) returns 0, and that path is infeasible.

## How to work through it

The [standing rules](brief-template.md#standing-rules) apply, the [timebox](brief-template.md#the-timebox) included:
- one step per cycle;
- check each claim against the code first;
- JBMC runs are queued, never run inline;
- nothing gets weaker;
- docs move with the behaviour;
- a reproducer before a fix.

Verification runs with the pipeline. When everything left waits on jobs, end Progress with
`- Status: waiting on jobs` and the ids, with no other word between them. `run-streams.sh` reads only id-shaped words
there now, but a single loop is rerun by hand.

## The plan

1. **The experiment, as one job.** It reproduces VF-015's step 3 with `--work` kept, then runs JBMC on the same
   harness in two ways:
   - `--cover location`, reading the goals at the entry of the `String.format` stub (expected: not covered);
   - the alternative the session finds in `jbmc --help` and the CProver docs: say, a reachability assertion at the
     call site, from a rewritten harness or goto program.

   Each is timed, beside the proof's own time. The job's description names the expected outcome of each method.
   JBMC 6.11 has `--cover`, though not with `--unwinding-assertions`; check how `--unwind` then bounds the paths.
2. **Choose the method** from the job, and record why under Progress: correct on the case, and cheap next to the
   proof. If neither is correct, or both cost more than the proof itself, stop with `blocked:` and the measurements,
   for the user.
3. **Implement it** in `jbmc_gaps.rs`, as a third step after `symbolic`, only for the stubs the symbolic run still
   enters, within the preflight's budget.
   - A stub the solver shows unreachable joins `Found::unreached`, with its reason named in the note.
   - Unit tests on recorded JBMC output, in the style of `entered`'s, are the reproducer: failing before, passing
     after.
   - The module doc, `lib/README.md`'s gap section and `Preflight::paths`' doc move with it.
4. **The checks, as jobs**:
   - VF-015's job resubmitted unchanged (`pipeline.py resubmit`), its title naming "closes VF-015 when it passes".
     That is N3's second and last attempt under the cleanup timebox. If step 4's replay then fails on
     `StandardCharsets.UTF_8` (`lib/src/interp/natives.rs:373`), that is the interpreter fix VF-015's entry names, and
     it is this brief's next item.
   - A guard that no stub a proof does enter is left out: the gap-preflight tests in `lib/tests/` and the conformance
     corpus under `--engine jbmc` (`the_corpus_agrees_with_the_jvm_under_jbmc_and_auto`), unchanged, expected to pass.

## Done when

| Step | Criterion |
|---|---|
| 1–2 | the method chosen on the job's evidence, or `blocked:` with the measurements |
| 3 | the reproducer fails before and passes after, and the docs are updated |
| 4 | VF-015's job passes (closing it), or is deferred by the timebox with the finding; the guard jobs pass |

## Deferred: not in this loop

- A `String.format` model or any other JDK model ([decision 1](#decisions)).
- JBMC's string solver (`--refine-strings`).
- External JBMC work.

## Decisions

Settled by the user on 2026-11-07:
1. Settle VF-015 by deciding stub reachability with the solver, after the cleanup merge, not by a `String.format`
   model in `lib/models/` and not by running step 3 under `--gaps assume`.

## Progress

- Drafted 2026-11-07 by session `3da21514`, while the cleanup run was still going.
- 2026-11-07: the cleanup loop's merge is committed (`lpvnwkuz`) and pushed, and the loop is done, so this brief starts.
- **Step 1: the experiment is queued.** Job `20261107-233000-stub-reachability-step-1-can-jbmc-s-solv` runs
  [`verification/triage/stub-reachability.sh`](../../verification/triage/stub-reachability.sh). Checked against the
  code first:
  - VF-015's step 3 already keeps `--work`, but a work directory doesn't record JBMC's command. So the script puts
    JBMC behind a wrapper that records each command, its exit and its time, as `vf018.sh` does.
  - The proof takes about 0.1 s (VF-015's `jbmc.log`), so the budget is no concern here.
  - The second method is a probe at the call site. `jbmc --help` (6.11) names `--cover` only in `--unwinding-assertions`'
    line, and JBMC can't write a goto binary for `goto-instrument`, so the probe is a rewritten caller, not a
    rewritten goto program: `DecoderException`'s `String.format` call first calls `Reach.reach`, which does
    `throw new AssertionError()`. That is the assertion jvmcontract's `GapIntrinsics.open` already relies on
    (`jbmc_contracts.rs`), and `shared::redirect_calls` already rewrites call sites for `--gaps advised`. So step 3
    could build the probe from existing parts.
  - Both methods also run on a control, the same prove without `--assume`, where the call is reachable. A method
    that says "unreached" there is wrong.
  - Next: step 2, once the job is collected. Choose by `lib/target/stub-reach/summary.txt` (it comes back in the
    result's outputs), or stop with `blocked:` and the measurements.
- **Step 2: the probe is chosen.** The job passed (collected in `qkrlyslv`). Its log ends with the summary:

  | Run | The proof (jvmcontract's last JBMC run) | A. `--cover location` | B. the probe at the call site |
  |---|---|---|---|
  | case (`ch == 1632`) | proved, 129 ms; strict refuses it on `String.format` | usage error, 3 ms | `Reach.reach`'s assertion SUCCESS, 92 ms |
  | control (no `--assume`) | refuted, 105 ms | usage error, 4 ms | `Reach.reach`'s assertion FAILURE, 90 ms |

  - **A doesn't exist.** JBMC 6.11 answers `Unknown option: --cover`. The `--cover` in `--unwinding-assertions`' help
    line is CBMC's text, carried over, so the brief's "JBMC 6.11 has `--cover`" is wrong.
  - **B is correct on both runs**: the stub is unreached under the assumption and reached without it. It is also cheap:
    one JBMC run of the proof's own size, faster than the proof itself here, and well within the preflight's 60 s cap
    (`PREFLIGHT_SECONDS`).
  - **What step 3 must keep.**
    - The probe counts only when the same run's unwinding assertions all hold. Otherwise paths past the bound were
      cut, and the stub stays a gap. A timeout, an unknown or unreadable output also leaves the stub a gap.
    - A probe as `throw new AssertionError()` ends its path in any case: JBMC either lowers it to an assertion and
      an assumption of false (as remembered, not checked: JBMC's source isn't here) or throws. So a stub reached only
      after another probed call would look unreached, which is unsound. Step 3 either probes one stub per run, or
      guards the probe with `CProver.nondetBoolean()` and falls through to the real call. Its reproducer should
      include two stubs in sequence.
    - The probe goes immediately before each call site of the stub, in every class the listing shows calling it
      (`redirect_calls_directory` over the class path). A stub leaves the gaps only when every one of its probes holds.
  - Next: step 3, the probe in `jbmc_gaps.rs` after `symbolic`, with its reproducer first.
- **Step 3: the probe is the preflight's third step.** After `symbolic`, the stubs it still enters are probed in one
  run (`probe`, `place`, `probe_command`, `probed`):
  - Each call site (the listing's `bytecode-index`) is rewritten to a method `p<k>` of `jvmcontract.StubProbe`. It
    fails an assertion behind `CProver.nondetBoolean()`, and otherwise makes the call. The rewrite uses a new
    `shared::redirect_calls_at`, which also passes where the call site is.
  - A stub is left out (`Found::solved`, and also in `Found::unreached`) only when every one of its probes holds and
    every unwinding assertion holds.
  - It stays a gap when the run is out of time, has no verdict or can't be read. It also stays one when a call site
    has no index, the instruction there doesn't call the stub, or the caller has no class file.
  - `Preflight::probes` records the run, and the note names the reason.
  - The reproducers:
    - unit tests on step 2's recorded case output, and on its control and failure variants;
    - a placement test with two stubs in sequence;
    - a live test, `a_stub_behind_a_condition_only_the_solver_decides_is_no_gap`, on the new `P.sequenced`. Two
      stubs are in sequence, and a third sits behind `n * n == 7`. With the step reduced to a no-op, the old
      behaviour, it fails with the third a gap; with it, it passes. Its JBMC output shows the second stub's probe
      failing past the first's, and confirms step 2's remembered lowering
      (`aborting path on assume(false)` in `StubProbe.p0`).
  - The module doc, `lib/README.md`'s gap section and `Preflight::paths`' doc are updated. The unit suite (215) passes.
  - Next: step 4. Resubmit VF-015's job with the title naming "closes VF-015 when it passes". Submit the guard job:
    the gap tests in `lib/tests/integration.rs` (`jbmc_own_approximations_are_gaps_in_the_same_modes`, the advised and
    contract ones), and the conformance corpus under `--engine jbmc`.
- Status: working

## Loop settings

- session: 807d6ed2-a98d-4f93-8dbb-28d70736eff7
- model: claude-opus-5-5
- effort: high

## Loop until

Stop with `done` once step 4's criterion is met. Stop with `blocked: ...` when step 2 finds no method that is both
correct and cheap, or the user is needed. Set the status to `working` when the cleanup merge is committed, before
starting. Don't take on other gaps or models.
