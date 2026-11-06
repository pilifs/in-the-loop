# Verification findings and decisions

What the verification runs turned up that needs a person: verdicts against a change, failures a submitter has to
fix, and decisions the managing agent took that change what the results mean. The agent running
[`/run-verification`](../.claude/skills/run-verification/SKILL.md) adds an entry whenever a run produces one, and
updates or closes entries when a later run settles them. Results themselves stay in [`results/`](results/); this
page is the short list of what is still open, and what was decided, so that nothing is lost between sessions.

Each entry has an id (`VF-NNN`, never reused), and these fields:

- **Status**: `open` (needs someone), `decided` (a decision was taken and is recorded here, nothing to do), or
  `closed` (settled: say by what, with the job or commit). Open entries come first, newest first; the rest follow.
- **Raised**: the date, the machine (`runner.host`), and the run's job ids and the commit they ran at.
- **Found**: what happened, with the evidence a reader needs without the logs.
- **Needs**: what would settle it, and who should act: the submitter, a brief's loop, or the user.
- **Tracked in**: where the work lives, if anywhere else (a brief's Progress, an example's notes).
- **Closes when**: the check that settles it, usually a job to rerun unchanged.

## Open

### VF-002: examples 147, 148 and 149 never reach a proof

- **Status**: open
- **Raised**: 2026-11-06 on `vm-1`. Jobs `20261106-053555-example-147-b11-advised-contracts-a-cont`,
  `20261106-053555-example-148-b11-advised-contracts-full-j` (at `ef5d434c48db`) and
  `20261106-061323-example-149-b11-contract-library-full-ji` (at `8ea88f97e447`).
- **Found**: each fails within a second with "the patch does not change the subject file
  examples/apps/crosscut/src/main/java/net/terminalvalue/crosscut/retry/Jitter.java". The patches create that file
  (`--- /dev/null`), and `build.py`'s `excerpts()` requires the subject to exist before the patch. Deterministic: it
  fails the same on any machine, at the jobs' commits and still on 2026-11-06.
- **Needs**: either `excerpts()` accepts a subject the patch creates (an empty before side), or the examples' patches
  stop creating it. For whoever owns the advised-contracts examples (Phase 3 of the sound-verdicts brief).
- **Tracked in**: [`llm-dlc/loops/sound-verdicts.md`](../llm-dlc/loops/sound-verdicts.md#progress) (the entry of
  2026-11-06 on `vm-1`), and the notes of examples 147, 148 and 149.
- **Closes when**: the three jobs, resubmitted after the fix, pass with each example's expected verdict.

### VF-001: JBMC verdicts the JVM contradicts, passed through by `--engine auto`

- **Status**: open
- **Raised**: 2026-11-06 on `vm-1`. Jobs `20261106-021741-conformance-corpus-under-jbmc-and-engine` and
  `20261106-024336-conformance-corpus-under-engine-auto-con`, both at `470be6c5ff8b`, JBMC 6.11.0.
- **Found**: the conformance corpus (54 methods, 93 claims, the JVM as reference) disagrees with JBMC in both
  directions:
  - **JBMC proves seven claims the JVM refutes**, under `--gaps strict`: `capacity`, `builderCapacity`,
    `mapCapacity`, `setCapacity` and `loadFactor` (JDK constructors that throw on a negative capacity or a load
    factor of 0 or less; JBMC's library models, pinned to 2022, return normally), `nullMonitor`
    (`synchronized ((Object) null)` throws `NullPointerException` on the JVM), `firstByte` (`Random.nextBytes`) and
    `pairsEqual` (a record's `equals` through `invokedynamic`).
  - **JBMC reports violations the JVM does not reproduce** on `caught(n=0)` and `nestedHandler(n=0)`, which catch the
    `ArithmeticException` of an integer division by zero. The tool's own checker proves both and the JVM agrees.
    Either JBMC's semantics or a flag jvmcontract does not pass (such as `--throw-runtime-exceptions`).
  - **`--engine auto` takes JBMC's wrong `Verified`** for `loadFactor` and `pairsEqual`, where the own checker has no
    verdict, under strict and under assume. This part is jvmcontract's, not JBMC's.
- **Needs**: Phase 1 of the sound-verdicts brief is not done, though the brief read as if it were. Its criterion is
  that no engine, nor `--engine auto`, gives `Verified` under strict for a claim the JVM refutes. Closing it means
  treating JBMC's verdicts on JDK calls its models stand in for as gaps under strict, making `synchronized (null)`
  and division by zero behave as on the JVM under JBMC (or refusing them), and not letting auto take a JBMC
  `Verified` unchecked. For the sound-verdicts loop, or a loop of its own; the user is deciding how to take it on.
- **Tracked in**: [`llm-dlc/loops/sound-verdicts.md`](../llm-dlc/loops/sound-verdicts.md#progress) (the entry of
  2026-11-06 on `vm-1`), with every disagreement; the logs in each job's `results/ID/logs/`.
- **Closes when**: both jobs, resubmitted unchanged after the fix, pass.

## Decided and closed

None yet.
