# Brief: JBMC's upstream defects

**Status of the brief**: drafted 2026-11-07, not approved. It runs after the foundations loop, together with the
findings the user selects then (see [Decisions](#decisions)). Until the user approves it, no loop runs on it.

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh), run alone. The `engine-priorities` loop found three
places where JBMC 6.11.0 runs Java bytecode otherwise than the JVM, guarded each in the tool's preflight, and drafted
a report for each. This loop makes each report ready for the user to file, with every claim in it backed by a recorded
run. It also prepares what the tool needs when a fixed JBMC arrives. It files nothing and contacts no one.

**Inputs.** Read these in full before the first piece of work of every cycle:
- [`lib/tests/fixtures/jbmc-defects/README.md`](../../lib/tests/fixtures/jbmc-defects/README.md): the four causes, the
  fixture's table, and the three drafted reports;
- [`verification/findings.md`](../../verification/findings.md): the open findings, VF-009 among them;
- this brief's [Progress](#progress).

## Direction

- **The reports are for the user to file.** Nothing outward-facing: no issue, comment, pull request or mail. Network
  access only in a job whose description says so (CLAUDE.md).
- **Every claim in a report is backed by a recorded run**: a pipeline job's log of stock JBMC and of the JVM on the
  report's own example, exactly as the report gives it. A claim no job has backed is taken out or marked as unchecked.
- **The guards stay until a fixed JBMC is measured.** The preflight's `return-past-handler`, `unmasked-shift` and
  `extra-initializer` (`lib/src/jbmc_gaps.rs`, `Defect`) are what keep JBMC's false proofs out under every `--gaps`
  mode. A guard is lifted for a JBMC version only when a job shows that version agrees with the JVM on the defect's
  fixture methods and corpus claims.
- **The JVM is the semantic reference**, as in every loop here.

## Where it starts from

As of commit `xmslpytz` (2026-11-07), JBMC 6.11.0 (`cbmc-6.11.0`) with the options every run passes
(`--throw-runtime-exceptions`, `--no-refine-strings`, CaDiCaL), JDK 25.0.5:

| Cause | What JBMC does | Preflight | False proofs in the corpus | Report's evidence |
|---|---|---|---|---|
| 1 | computes a returned value after the try range ends, so its runtime exception escapes the handler (`return 10 / n`) | `return-past-handler` | `caught/3` | inline runs during step 3 (`svvrpymr`); no job log of the report's `E.java` |
| 3 | right-shifts (`ishr`, `iushr`, `lshr`, `lushr`) by the whole distance instead of its low 5 or 6 bits | `unmasked-shift` | `shiftRight/3`, `shiftUnsigned/3` | inline runs and the `--show-goto-functions` listing (`pxqzmomt`); no job log of the report's `S.java` |
| 4 | initializes the class an instruction names rather than the declaring class, and every superinterface | `extra-initializer` | `declaring/2`, `defaults/3` | job `20261107-010728`, step 3: `VERIFICATION FAILED` on both `I.field` and `I.iface`, as the report says (`lib/target/report-i.log`) |

- Cause 2 (JBMC's stub of a JDK exception class has no superclass, so `catch (RuntimeException e)` misses an
  `ArithmeticException`) is this repository's class path, not JBMC's: its fix is models of the exception classes in
  `lib/models`, and its guard is `stubbed-handler`. It is not reported upstream.
- The fixture `lib/tests/fixtures/jbmc-defects/p/D.java` has one method per shape, and
  `the_preflight_names_where_jbmc_runs_the_bytecode_otherwise_than_the_jvm` and
  `the_preflight_reads_jbmc_listing_by_instruction_index` check the preflight against JBMC's real listing.
- Whether any of the three is already reported or fixed upstream (the CBMC repository's issues and releases after
  6.11.0) has not been checked: that needs the network.

## How to work through it

The standing rules of `llm-dlc/loops/brief-template.md` (on the `foundations-draft` branch until the foundations loop
merges), the timebox included: one step per cycle; check each claim against the code first; proofs and JBMC runs
queued, never inline (a `--show-goto-functions` listing, nothing solved, is fine inline); recorded results are
evidence; nothing gets weaker; docs move with the behaviour; defer what needs the user, explicitly; a reproducer before
a fix. Verification runs with the pipeline.

## The plan

1. **Each report's example, recorded.** One job, no network: write `E.java` and `S.java` from the reports next to
   `I.java` in `lib/tests/fixtures/jbmc-defects/`, and run each method of all three on the JVM (`java -ea`) and on
   stock JBMC 6.11.0 with the command line each report gives. Keep the logs. Bring each report's text in line with what
   the logs say.
2. **Upstream's state, checked** (a job that says it reaches the network, if the user agrees: see Decisions): the
   CBMC issues that match each defect, and whether a JBMC release after 6.11.0 changes any of them. A matching issue
   turns its report into a comment for the user to add there, with our example.
3. **The reports finished**: each self-contained (versions, the example, the command, what the JVM gives, what JBMC
   gives, where in JBMC's output it shows, and a suggested fix), in one place for the user, with the job ids behind
   every claim.
4. **Ready for a fixed JBMC**: a job, kept in `verification/`, that runs the fixture methods and the six corpus claims
   above on a given JBMC executable, and says per defect whether that version agrees with the JVM. The preflight
   keys each guard by JBMC version only once such a job has shown a version fixed. Until then nothing about the guards
   changes.
5. **Optional, if the user decides so: patches.** For cause 3, the smallest, a patch to JBMC's bytecode conversion
   that masks the right shifts' distance as it does the left shifts', built from source and run through step 4's job
   in a job. Drafted for the user, never submitted.

## Done when

| Step | Criterion |
|---|---|
| 1 | Each report's example has a job log on the JVM and on JBMC 6.11.0, and the report's text matches it |
| 2 | Each defect's upstream state is recorded, or the step is deferred by the user's decision |
| 3 | Three reports the user can file as they stand, each claim with its job id |
| 4 | The fixed-JBMC job exists and has run once on 6.11.0, reporting all three defects present |
| 5 | Done or declined by the user |

## Deferred: not in this loop

- Filing the reports, and anything else outward-facing: the user's.
- Cause 2's exception-class models in `lib/models`: this repository's own work, for a models or engine loop.
- VF-009 (JBMC's spurious refutations of `boomTwice` and `enumBroken` under `--confirm`) is deferred, and joins this loop
  only if the user selects it (Decisions): it may be a fourth JBMC defect (a throwing class initializer), or a gap in
  the tool's `--confirm` rule.

## Decisions

Open, for the user before the loop runs:
1. Approve the brief, and the findings that join it (VF-009 is the likely candidate).
2. Whether step 2 may run a job that reaches the network to read CBMC's issues and releases, or whether the user
   checks upstream themselves.
3. Whether step 5 (a JBMC patch for cause 3, built from source) is in scope.
4. Where the finished reports go: kept in the fixture README as now, or one file per report for pasting.

## Candidate reports

Added by the cleanup loops, for the user to select (decision 1). Each one is evidence and a draft, never filed.

### Cause 5: a class initializer's exception reaches the caller unwrapped (VF-009)

Added by the `cleanup-jbmc` stream on 2026-11-07. Guarded in the preflight as `throwing-initializer` (`lib/src/jbmc_gaps.rs`).

- **What the JVM does** (JVMS §5.5):
  - An initializer that completes abruptly with an exception that is not an `Error` is wrapped in
    `ExceptionInInitializerError` (step 11).
  - The class is marked erroneous (step 12), so every later use throws `NoClassDefFoundError` (step 5), without
    running the initializer again.
  - An `Error` is thrown as it is.
- **The example**: `lib/tests/fixtures/jbmc-defects/F.java`, one void method per part, each with one assertion.
  `java -ea F` holds them all on JDK 25.0.5 (`all hold, runs 4`).
- **What JBMC 6.11.0 does**, in job `20261107-163056-vf-009-triage-a-class-initializer-that-t` (step 1, log
  `1-the-fixture-on-the-jvm-and-sto.log`). It was run with no options, with `--throw-runtime-exceptions`, and with
  the options jvmcontract passes, and gives the same verdicts each way:

  | Method | Class | On the JVM | JBMC |
  |---|---|---|---|
  | `wrapped` | `F$Wrap`, whose initializer throws an `IllegalStateException` | the caller catches an `ExceptionInInitializerError` | `assertion.1` fails: the `IllegalStateException` reaches the caller as it is |
  | `enumWrapped` | the enum `F$Divide`, whose constructor divides by zero | the caller catches an `ExceptionInInitializerError` | `assertion.1` fails under `--throw-runtime-exceptions`: the `ArithmeticException` reaches the caller. Without the option, the division is a failed check |
  | `error` | `F$Fatal`, whose initializer throws an `InternalError` | the caller catches the `InternalError` | `VERIFICATION SUCCESSFUL`, as on the JVM |
  | `boomTwice`, `enumBroken` | copies of the corpus's | 2 and 12 | `no uncaught exception` fails: the unwrapped exception passes the `catch (ExceptionInInitializerError)` |

- **Where it shows in JBMC's program.** JBMC wraps each `<clinit>` in a `<clinit_wrapper>`. In the
  `--show-goto-functions` listings that step 2 kept (now `lib/tests/fixtures/jbmc-defects/vf009/`), the wrapper
  sets `clinit_already_run := true` and then calls `<clinit>` with no handler around the call. When an exception is
  in flight after it, the wrapper returns with it:

  ```
  IF ¬(java::conformance.Conformance$Boom::clinit_already_run ⇔ false) THEN GOTO 1
  ASSIGN java::conformance.Conformance$Boom::clinit_already_run := true
  CALL java::conformance.Conformance$Boom.<clinit>:()V()
  IF java::@inflight_exception = NULL THEN GOTO 1
  1: END_FUNCTION
  ```

  From that listing,
  not from a separate run: a later use of the class finds it initialized, and runs on with its static fields at
  their defaults, where the JVM throws `NoClassDefFoundError`.
  - `F.erroneous` and `F.once` were meant to test this, but their `catch (Throwable)` misses JBMC's stub of
    `IllegalStateException`, which has no superclass. That is cause 2, this repository's class path, so they don't
    decide it.
- **Through jvmcontract** (step 2, log `2-the-corpus-methods-through-jvm.log`):
  - `prove` refutes `conformance.Conformance#boomTwice` (`result == 2`) and `#enumBroken` (`result == 12`) on
    `n=0`, under `--engine jbmc` and under `auto --confirm` (strict and assume).
  - The interpreter returns 2 and 12, as the JVM does (VF-009).
- **A suggested fix**, for the report: have the `<clinit_wrapper>` catch what `<clinit>` throws. It would wrap
  anything that is not an `Error` in a new `ExceptionInInitializerError`, set a per-class `clinit_failed` flag, and
  throw `NoClassDefFoundError` at entry when the flag is set.
- **Unchecked**: whether this is reported or fixed upstream, which needs the network (decision 2).

## Progress

- Nothing yet.
- Status: draft, not approved

## Loop settings

`new` starts a fresh session. Replace it with that session's id once the loop has run, so that a later run resumes
it. A value takes no comment on its line.

- session: new
- model: claude-opus-5-5
- effort: high

## Loop until

Steps 1, 3 and 4, then 2 and 5 as the user decided. Stop when the reports are ready for the user and the fixed-JBMC
job has run, or when what is left needs the user. Keep the last line of Progress a status (`working`, `waiting on jobs
ID ...`, `done` or `blocked: ...`). Items deferred by the timebox are recorded deferrals, never a reason to keep going.
