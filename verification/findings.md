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

### VF-020: a passed job's `changes.diff` (1.2 MiB) is not committed, because jj refuses to snapshot new files over 1 MiB

- **Status**: open
- **Raised**: 2026-11-07 on `vm-1`, job `20261107-163056-vf-009-triage-a-class-initializer-that-t` (at `2c352d909f21`),
  collected in the commit that records the run of 2026-11-07 (VF-009's triage).
- **Found**: `collect` wrote `verification/results/20261107-163056-vf-009-triage-a-class-initializer-that-t/changes.diff`
  (1,234,232 bytes: the diff of the 168 output files, most of them `lib/target/vf009` class files and goto listings).
  jj's `snapshot.max-new-file-size` is 1 MiB, so every `jj` command prints "Refused to snapshot some files" and the
  file is left out of the commit. The rest of the result (`result.json`, the logs) is committed. I did not raise the
  limit or edit the result.
- **Again** in the next run: `verification/results/20261107-171442-vf-009-s-guard-measured-the-41-recorded/changes.diff`
  (1.3 MiB) was also left out. Two results so far lack their diff; both jobs passed.
- **Needs**: a decision by the user: raise the limit for this repository (`jj config set --repo
  snapshot.max-new-file-size 2097152`), or have `collect` leave out a `changes.diff` over the limit (or compress it),
  or have jobs keep their scratch output out of the declared outputs. The job's `outputs` listed `lib/target/vf009`,
  which is build output; a submitter's call for the jobs that follow.
- **Closes when**: `jj st` shows no refused file after a collect, or the result is recorded as lacking its diff on
  purpose.
- **Decided** by the user on 2026-11-07: `collect` handles the size. A `changes.diff` over jj's limit is written
  gzipped (`changes.diff.gz`), or, if that is still over, as a `--stat` summary, and `result.json`'s `changesDiff`
  says which. The limit stays at 1 MiB.
- **Fixed** 2026-11-07 in the commit that adds `keep_diff` to `verification/pipeline.py`: `collect` keeps a
  `changes.diff` over 1 MiB as `changes.diff.gz`, or as `changes.stat` (the files it changes, with lines added and
  removed) when even gzipped it is over, and records the original size in `collected.changesDiff`
  (`test_pipeline.py`, `test_a_diff_over_the_commit_limit_is_kept_gzipped_or_as_a_summary`).
  - Contrary to the entry above, both diffs did reach the repository. `git ls-tree` shows the first, 1,234,232
    bytes, committed in `pkuvkyln` and the second, 1,359,746 bytes, in `rzmrlklw`; both have been pushed. How they
    got past the limit is not known. Neither result lacks its diff, and they are left as they are.
- **Closes when**, now: the next `collect` of a job whose diff is over 1 MiB leaves `jj st` with no refused file.

### VF-018: JBMC doesn't finish within 600 s on four of H5's regression proofs over objects under a correspondence

- **Status**: open
- **Raised**: 2026-11-07 on `vm-1`. Four of the heap stream's H5 jobs, each one ignored test of `lib/tests/heap.rs`
  under `--engine jbmc` and `auto --confirm`, each failed after about 22 minutes:
  - `20261107-080218-output-relations-under-a-correspondence` at `9b9c3a34`: `objects.Kernel#price` (`heap.rs:986`);
  - `20261107-083358-computed-input-equations-under-a-corresp` at `a405b89a`: `prices.Prices#total` (`heap.rs:1172`);
  - `20261107-092158-input-equations-that-read-a-primitive-pa` at `e7e61dbd`: `lines.Lines#reprice` (`heap.rs:1472`);
  - `20261107-115201-input-equations-that-read-another-object` at `0348f57c`: `orders.Orders#reprice` (`heap.rs:1685`).
- **Found**: each fails on its first JBMC run, with `Jbmc confirm=false after …: Unverifiable (expected Verified, on
  a JVM false)` and "JBMC did not finish within 600 s". The own checker proves each claim. JBMC gives no verdict,
  which is sound but not what the tests expect. The other four H5 jobs, over the same harness machinery, passed in
  2 to 6 minutes: `-085410`, `-104658`, `-112033` and `-121516`. Not read further: the harness JBMC is given (its
  size, the unwinding, how the correspondence's equations are encoded for it), or whether these proofs are simply
  beyond JBMC in 600 s.
- **Needs**: triage of one of the four as a quick job: JBMC on the generated harness with its statistics, and
  whether a smaller encoding (fewer objects, a tighter unwind, the equations as assumptions) lets it finish.
  - If the harness can be made tractable, do it, with the tests unchanged.
  - If not, the tests' expectation that JBMC agrees is the question. Accepting JBMC's timeout as no verdict would
    relax a check, so it is for the user to decide.

  For the cleanup loop's jbmc stream.
- **Tracked in**: [`llm-dlc/loops/cleanup-jbmc.md`](../llm-dlc/loops/cleanup-jbmc.md) (J3).
- **Closes when**: the four jobs, resubmitted unchanged at a fixing commit, pass; or the user decides the
  expectation, and the jobs pass under it.
- **Rerun with an 1800 s JBMC limit** 2026-11-07 on `vm-1`, at `cf2205fc56a3` (the four jobs
  `20261107-164356-vf-018-*`, 6 GiB limit each, peak 1.5 GiB): one passed, three failed alike.
  - `prices.Prices#total` passed: its test finished in 3185 s, so JBMC gave a verdict inside 1800 s (it is
    tractable, about 5 times slower than the 600 s default suggested).
  - `objects.Kernel#price` (`heap.rs:1070`), `lines.Lines#reprice` (`heap.rs:1570`) and `orders.Orders#reprice`
    (`heap.rs:1746`) failed after 3606 to 3688 s with "JBMC did not finish within 1800 s", `Unverifiable (expected
    Verified, on a JVM false)`. Tripling the limit did not help them, so a longer limit is not the way out for these
    three: the harness or its encoding needs triage, or the expectation is the user's decision, as above.
  - Memory was never the limit (peak 1.6 GiB of 6).
- **Decided** by the user on 2026-11-07: triage the harness, with the tests' expectation unchanged. A quick job runs
  JBMC on one of the three generated harnesses with its statistics, then on smaller encodings (fewer objects, a
  tighter unwind, the equations as assumptions). If one finishes, the harness generator adopts it and the three jobs
  are resubmitted unchanged.
- **Triage queued** 2026-11-07: job `20261107-224523-vf-018-triage-what-jbmc-is-given-for-h5` runs
  `verification/triage/vf018.sh` on `objects.Kernel#price`. It records the commands the test gives JBMC, measures the
  harness and goto program, and reruns the first proof with JBMC's statistics, as given and at `--unwind` 8, 4 and 2
  and with `--slice-formula`, 900 s each. The encoding to try next (fewer objects, the equations as assumptions)
  follows from where its time goes.
- **Triage ran** 2026-11-08 on `vm-1`: `20261107-224523-vf-018-triage-what-jbmc-is-given-for-h5` (at `8aac19618c9d`)
  passed (1h21m; its outputs `lib/target/vf018/summary.txt` and `proof-command.txt` were applied). What it shows for
  `objects.Kernel#price`: the harness is small (211 bytecode instructions over 2 methods, 12 KiB; goto program of
  3186 lines), symex takes 0.009 s and produces 518 steps and 1 VCC, and the formula is 18358 variables and 77108
  clauses. The solver, not the encoding of the program, is where the time goes: as given (`--unwind 16`), at
  `--unwind` 8, 4 and 2, and with `--slice-formula` (15753 variables, 76395 clauses), JBMC did not finish within
  900 s in any of the five runs, and the formula is the same size at every unwind, so the unwinding is not what
  makes it hard. **Needs**: the next triage is on what the 77k clauses are (JBMC's output with `--show-vcc`, or
  which equations of the correspondence are arithmetic that a SAT solver finds hard), and then fewer objects or
  the equations as assumptions, as the entry's plan says; the cleanup loop's jbmc stream. Still open.

### VF-015: example 109's old `toDigit` refuted, but its witness can't be replayed: the interpreter can't read `StandardCharsets.UTF_8`

- **Status**: open
- **Raised**: 2026-11-07, from the inventory of failed results for the cleanup loop. Job
  `20261103-010716-example-109-revisited-hex-todigit-s-regr` at `4abee307b922`, on `FilSurface`, failed on
  2026-11-03. It was never rerun or tracked.
- **Found**: step 3 ("old toDigit decodes the Arabic-Indic zero") exited 1. JBMC 6.11.0 found `ch == 1632`, but the
  interpreter could not replay it: `outcome: <could not replay: <unsupported: reads static field
  java.nio.charset.StandardCharsets.UTF_8>>` (`lib/src/interp/natives.rs:373`). The two steps after it were
  skipped. The JDK models have shipped with jvmcontract since, so the failure may have changed.
- **Needs**: a rerun at the current commit first. Then, if it fails the same way, the interpreter reads
  `StandardCharsets`' constants as the JVM has them. For the cleanup loop's native stream.
- **Tracked in**: [`llm-dlc/loops/cleanup-native.md`](../llm-dlc/loops/cleanup-native.md) (N3).
- **Closes when**: the job, resubmitted at a fixing commit, passes.
- **Rerun** 2026-11-07 on `vm-1`: job `20261107-165827-example-109-revisited-hex-todigit-s-regr` (at `86e4ce7d220f`) failed at step 3, differently. The witness replay is no longer the problem (JBMC now proves the old `toDigit` for `0x0660`). Now `jvmcontract` refuses the result under `--gaps strict`: "JBMC proved it, but reaches 1 construct it approximates without implementing, and refused it: `jdk-static-method:java.lang.String.format(String, Object[])`" (a stub JBMC returns null or any object for). Steps 4 and 5 were skipped. **Needs**: a decision on whether the job should pass `--gaps assume` or advised (the job's step, the submitter's), or a model of `String.format` (the exception path of `Hex.toDigit` calls it); the cleanup loop's native stream. The entry stays open.
- **Rerun** 2026-11-08 on `vm-1`: job `20261108-011411-vf-015-example-109-revisited-hex-todigit` (at `1b376e0f1e77`) got further. The gap preflight now asks JBMC's solver and finds no path reaches the `String.format` stub, so step 3 (old `toDigit` for `0x0660`) passes and step 4 (the change found, witness replayed) passes as expected. Step 5 ("nothing else changed on ASCII", expected: verified over every char x int) exits 1: `Hex#toDigit cannot be verified: an unexpected property failed: java::EquivalenceHarness.check:(CI)V.1`, with 4 `throwing-initializer` defect notes (JBMC runs `CharEncoding.<clinit>` and `Hex.<clinit>`, before and after, as possibly throwing NullPointerException, and `catch (java.lang.Error)` in the harness) and the `String.format` gap note. **Needs**: whoever owns the stream (stub-reachability loop, cleanup native stream) to decide whether the harness's `catch (Error)` and the initializers' possible NPE (probably the JDK stub for `StandardCharsets`/`Charset`) make property `check.1` fail spuriously (then a model or an `--unwind`/assumption fix), or a real difference. Logs: `verification/results/20261108-011411-vf-015-example-109-revisited-hex-todigit/logs/5-*.log`. The entry stays open.
- **Triaged** 2026-11-08 by the stub-reachability loop, from that job's `work-change/jbmc.log` and
  `work-ascii/jbmc.log`. Neither the initializers nor a stub is the cause. Property `check.1` is JBMC's "no uncaught
  exception", and both traces end the same way: the old `toDigit` is called on an ASCII char that is no hex digit
  (`ch = 0` in step 5), constructs `DecoderException` and throws it, and the exception leaves `EquivalenceHarness.check`.
  `DecoderException` is a checked exception (it extends `java.lang.Exception`), and the equivalence harness's call
  handlers (`lib/src/harness/mod.rs`, `harness::EXCEPTIONS`) catch only the listed unchecked exceptions,
  `RuntimeException` and `Error`. So every equivalence over a method that throws a checked exception can't be verified.
  That includes step 4: its `test $? -eq 1` took "cannot be verified" for the change being found, so its pass shows
  nothing. **Deferred by the timebox**: it is N3's second failed attempt in a row, after `20261107-165827-…`, so the
  loops don't try again. **Needs**: the equivalence harness to tell apart the exceptions the two versions declare (a
  handler for each class in their `throws` clauses, then `java.lang.Exception`, as the property harness already
  handles a declared exception). Then this job, resubmitted with step 4 checking for a found change rather than exit 1,
  in a session a person starts. That is a harness change with unit tests, plus one job of a few seconds of JBMC.
  Recorded in [`llm-dlc/loops/stub-reachability.md`](../llm-dlc/loops/stub-reachability.md)'s Progress.

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
- **Seen again** 2026-11-07 on `vm-1`, in jobs `20261107-163046-example-147-b11-advised-contracts-a-cont`,
  `20261107-163047-example-148-b11-advised-contracts-full-j` and `20261107-163049-example-149-b11-contract-library-full-ji`
  (at `d32ddc64d1a4`, resubmitted unchanged by the cleanup loop's examples stream after the `excerpts()` fix). The
  subject check is no longer what stops them. Now each fails in 0.2 s at "apply the patch": `git apply` reports
  `crosscut/src/test/java/net/terminalvalue/crosscut/Tests.java:19: patch does not apply`. The three patches add
  their test classes to the suite list in `Tests.java`, whose context has since changed (the list gained entries
  with examples 150 to 152 and the later crosscut examples). I checked with `git apply --check` that they don't
  apply to the current tree either, so a rerun alone won't help. **Needs**: regenerate the three `change.patch` files
  against the current crosscut app (the examples stream; the patches also change `properties.contract` and
  `Jitter.java`, which should be unaffected), then resubmit. VF-002 stays open.
- **Rerun** 2026-11-07 on `vm-1`: jobs `20261107-165152-example-147-b11-advised-contracts-a-cont`, `-148-` and `-149-` at `35a9ea8fadaa`, after regenerating the patches. 149 **passed** (verified as expected, results applied). 147 and 148 fail in 3 s in `stage_contracts` (`build.py:432`): `FileNotFoundError: .../.build-py/examples-*/attempts/147/attempt-*/gaps.contracts`: `shutil.copyfile(folder / name, target)` reads `gaps.contracts` from the attempt's directory, where `build.py` hasn't copied it from the example's folder (149 uses the contract library, not a `gaps.contracts`). **Needs**: `stage_contracts` reads the example's own folder (the examples stream), then resubmit 147 and 148. The entry stays open until both pass.
- **Deferred by the timebox** of the cleanup loop after `stage_contracts` and `contracts_digest` were fixed
  (`xmsmzwoy`). **Decided** by the user on 2026-11-07: correct the wording of 148 and 149, whose titles, summaries
  and jobs named three contracts ("1 proved, 2 tested") although, with `Integer.numberOfLeadingZeros` no longer a gap,
  only the two tested ones may appear, and resubmit 147 and 148. For 148, the user decided to run it first and
  reword it after: its point was a contract proved against the JDK's bytecode, and only the run shows whether the
  agent's contract for `numberOfLeadingZeros` is still proved and counted.
- **Resubmitted** 2026-11-07 as `20261107-223430-example-147-b11-advised-contracts-a-cont` and
  `20261107-223430-example-148-b11-advised-contracts-full-j`, with 149's summary, explanation and resolution corrected
  to two contracts in the same commit (its passing result already reads `relying on 2 contracts ..., 2 tested`).
  148's job expects the verdict alone. VF-002 closes when both pass; 148 is then reworded to what its result shows.
- **Failed again** 2026-11-08 on `vm-1`: `20261107-223430-example-147-b11-advised-contracts-a-cont` and
  `20261107-223430-example-148-b11-advised-contracts-full-j` (at `a8b76de9c96f` and `b521d26a73ab`), each in 3.6 s,
  with the same `FileNotFoundError` as on 2026-11-07: `build.py:432` in `stage_contracts`, `shutil.copyfile(folder /
  name, target)` where `folder` is the run's attempt directory
  (`.build-py/examples-*/attempts/147/attempt-*/gaps.contracts`), not the example's folder, which holds
  `gaps.contracts` (committed). `run()` calls `RUNNERS[app][approach](out, example, tmp, module, result)`
  (`build.py:692`) with `out`, so `run_tool_property(folder, ...)` (`build.py:2365`) receives the attempt directory.
  So the earlier fix to `stage_contracts` and `contracts_digest` did not reach this call. It is `build.py`'s, not the
  pipeline's or the jobs': they are as they should be. I did not fix it or resubmit, since it would fail the same.
  **Needs**: the examples stream or whoever owns `build.py` passes the example's folder to `stage_contracts` (check
  `advice_record`, which gets the same `folder`), with a unit test that runs a B11 example with `approach.contracts`
  through `run()`; then resubmit 147 and 148 unchanged. VF-002 stays open.

## Decided and closed

### VF-001: JBMC verdicts the JVM contradicts, passed through by `--engine auto`

- **Status**: closed 2026-11-08, by jobs `20261107-222356-conformance-corpus-under-jbmc-and-engine` and
  `20261107-222356-conformance-corpus-under-engine-auto-con` (at `1e430db14391`, `mkdir -p target` added): each ran
  its test (`the_corpus_agrees_with_the_jvm_under_jbmc_and_auto`, `..._under_auto_confirm`) and passed, 1 passed, 0 failed
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
- **Rerun** 2026-11-07 on `vm-1`: jobs `20261107-172721-conformance-corpus-under-jbmc-and-engine` and `20261107-172721-conformance-corpus-under-engine-auto-con` (at `a1e29ec6a2e7`) both **failed**, for the same reason, none to do with the tests: their step is `cd lib && ... cargo test ... | tee target/conformance-*.log` with no `mkdir -p target`, and in a clean checkout `lib/target` does not exist when `tee` starts. The first job's log says `tee: target/conformance-jbmc.log: No such file or directory` and the step exited 1 although the test output shows `test result: ok. 2 passed; 0 failed`, 1236 s (so both corpus tests pass at this commit); the second was killed with SIGTERM after 22 s: not `tee`, but the runner's scope-name collision with its twin (the ids share 40 characters; see VF-021, fixed). A job that didn't pass doesn't close this entry. **Needs**: resubmit both with `mkdir -p target` before the pipe (as the jbmc-initializers job does), the cleanup loop's jbmc stream; the scope collision no longer applies. Closes then, if they pass.
- **Decided** by the user on 2026-11-07: resubmit both with `mkdir -p target &&` before the pipe, nothing else
  changed. The first job's "2 passed, 0 failed" is not taken as the check.
- **Resubmitted** 2026-11-07 as `20261107-222356-conformance-corpus-under-jbmc-and-engine` and
  `20261107-222356-conformance-corpus-under-engine-auto-con`, with `mkdir -p target &&` before the step's test
  command and nothing else changed. VF-001 closes when both pass.

### VF-013: the loops' run records are never published: they are gitignored, and unredacted

- **Status**: closed 2026-11-07, by `mmrwolwp` (`sync.py` publishes each record redacted under
  `llm-dlc/traces/<session>/runs/`, listed in the session's `summary.md`; `llm-dlc/tools/test_runs.py`, 8 tests, covers
  it) and `lrwynvul`, which published the records with `check` at 0 errors. On 2026-11-07, after the cleanup loop, all
  21 run records in `llm-dlc/loop-summaries/` had a published copy, `test_runs.py` passed and `check` gave 0 errors
  and 0 warnings. The two other files there, `cleanup-integration.md` and `foundations-integration.md`, are the
  integration scripts' notes, not `feature-loop.sh` run records, and are not published.
- **Raised**: 2026-11-07, while deleting the engine-priorities stream workspaces, whose 6 run records existed nowhere
  else (copied into `llm-dlc/loop-summaries/` first). Not a job failure.
- **Found**: `llm-dlc/tools/feature-loop.sh` writes a record of each run to `llm-dlc/loop-summaries/` (gitignored,
  `.gitignore:47`). It holds the start, cycle limit, session, model and effort, the brief's path and sha256, the
  instruction every cycle was given, a line per commit as it landed, the session's closing summary, and how the run
  ended. The summary is also the session's last turn (published, redacted, with its transcript), and the commits are in
  git. But nothing else records which commits belong to which run, or how and when each run stopped. The 7 records
  now are 7 to 18 KB each. Six of the seven hold unredacted local paths (the brief's path in the instruction and
  header), so removing them from `.gitignore` would publish them raw.
- **Needs** (option 1, chosen by the user): `sync.py` publishes each record redacted, beside the session it belongs to.
  - It reads the session id from the record's header.
  - It redacts the record with the same `Redactor` the transcripts use.
  - It writes the copy to `llm-dlc/traces/<session>/runs/<record>.md`, and links it from that session's `summary.md`
    (a list of runs: start, end, cycles, how it ended).
  - `check` scans the published copies like any other published file, and a finding in one is an error as for a log.
  - A record the loop is still writing (no `Ended` line yet) is republished as it grows, or held back until it ends.
  - Reproducer first: a test with made-up paths and a made-up session, which shows a record published unredacted, or
    not at all, before the change.
  - The redaction rules don't change, so no stamp is needed. `traces-readme-template.md` and `llm-dlc/README.md` say
    where the runs are.
  - The 7 existing records are published on the first `sync.py commit` after the change.
  - Option 2, R2 with the logs, was set aside: the records are small and are best read on GitHub next to the summary.
- **Tracked in**: `llm-dlc/loops/engine-priorities.md` (Progress, "Flagged for later").
- **Closes when**: `sync.py`'s tests cover it, and after a commit every record in `llm-dlc/loop-summaries/` has a
  redacted copy under its session's trace, linked from its summary, with `check` at 0 errors.

### VF-011: the own checker counts a loop's unwinding over the whole path, so example 052 is left to JBMC

- **Status**: closed 2026-11-07, by job `20261107-171502-vf-011-example-052-under-strict-on-the-o` (at
  `c6f34f8cb771`, `vm-1`, passed in 3m17s): 052 under strict on the own checker, with unwinding counted per entry of a
  loop, is established with no gap. The fix may turn other "not fully unwound" results into verdicts or timeouts;
  `lib/benchmark/results.json` was regenerated after it (2829 runs).
- **Raised**: 2026-11-07, from job `20261107-000039-the-41-recorded-jbmc-examples-under-stri` (at `98bab485`, `vm-1`) and
  the coverage inventory `examples/coverage.md` (commit `unvpruot`). Not a job failure.
- **Found**: under `--gaps strict`, obligation `052#0` is established by JBMC (with unwinding assertions at 16) and
  unresolved on the own checker: "a loop was not fully unwound with --unwind 16 (PropertyHarness.check at pc 238)".
  As read, not yet reproduced: `Engine::jump` in `lib/src/bmc/mod.rs` counts back edges per path and per
  `(class, method, target)`, and never resets the count when the loop is left. The property's `\max` over `k` of a
  `\sum` over `i < k` is two nested loops in the harness (`harness/expr.rs` compiles each quantifier as a loop), so over
  an array of length 8 one path takes the inner back edge up to 36 times. The count is incomplete, not unsound: a
  path cut short gives no verdict.
- **Needs**: a reproducer first (a nested loop whose inner loop runs fewer than the bound each time but more in total),
  then counting per entry of a loop. Ranked second among the own checker's extensions in `examples/coverage.md`.
- **Tracked in**: `examples/coverage.md` (extension 2), `llm-dlc/loops/engine-priorities.md` (Next, item 9).
- **Closes when**: a job runs 052 under strict on the own checker (`approach.engine` set to native in a copy) and it is
  established with no gap.

### VF-021: two of VF-010's benchmark jobs were killed by SIGTERM, with no output, and no verdict comparison across its fix was made

- **Status**: closed by job `20261107-184603-vf-010-s-benchmark-compared-the-own-chec` (at `df6b1c2e7e1e`, 2026-11-07, `vm-1`): the own checker's 557 runs at the fix and at its parent: 0 new, 0 gone, verdicts changed 0, formulas grown past 10% 0, paths or merges changed 0. The benchmark pair that fed it passed after the runner's scope-name fix.
- **Raised**: 2026-11-07 on `vm-1`. Jobs `20261107-165544-vf-010-s-benchmark-at-the-fix-run-1-of-2` (at `f606b0d80e31`, killed after 2m19s) and `20261107-165544-vf-010-s-benchmark-at-the-fix-s-parent-r` (at `c307e721bdc3`, after 0.2 s).
- **Found**: each step (`cargo build --release -q` then `python3 lib/benchmark/run.py --engines native --out ...`) ended with signal SIGTERM, not a timeout (`timedOut` false, not cancelled, no stop reason), peak 1.5 GiB and 574 MiB against 3 GiB limits, and no output file written. Three other jobs ran at the same time and finished normally (the VF-010 reproducer and integration tests at the fix, and example 109). Cause found (by the submitter, confirmed by me in `verification/pipeline.py`): the runner named each step's systemd scope `vjob-<id[:40]>-<step>`, and the two ids share their first 40 characters, so each job's step stopped the other's as a leftover of the same name. Fixed in the runner: the scope name is now the first 30 characters of the id and a hash of the whole id (`scope_id`). The same collision stopped job `20261107-172721-conformance-corpus-under-engine-auto-con` (VF-001) beside its twin.
- **Seen again, resolved in part** 2026-11-07 on `vm-1`: the resubmitted pair `20261107-183538-vf-010-s-benchmark-at-the-fix-run-1-of-2` (at `f606b0d80e31`) and `20261107-183544-vf-010-s-benchmark-at-the-fix-s-parent-r` (at `c307e721bdc3`), with ids that differ early, both passed (3m11s each) and their outputs are applied.
- **Needs**: the submitter (cleanup loop's native stream) queues the comparison job on the two outputs.
- **Tracked in**: [`llm-dlc/loops/cleanup-native.md`](../llm-dlc/loops/cleanup-native.md) (N1).
- **Closes when**: the two benchmark jobs pass and the comparison shows no recorded own-checker verdict changed with the fix.

### VF-014: H1's benchmark comparison fails on 8 verdicts that changed because `lib/benchmark/results.json` is stale, not because of symbolic references

- **Status**: closed by job `20261107-183328-vf-014-h1-isolated-run-3-of-3-the-benchm` (at `7315cda22a96`, 2026-11-07, `vm-1`): the comparison of H1's own-checker verdicts with H1's parent's passed (0.2 s): 'verdicts changed: 0', the only new runs the 24 of the swaps cases H1 added. The stale `results.json` was the cause, not H1.
- **Raised**: 2026-11-07 on `vm-1` (run with `--memory 8G --workers 2`). Job
  `20261107-041414-symbolic-references-in-the-own-checker-h` at `73c514ad00a7`: step 1 (the whole benchmark on the own
  checker, 557 runs) passed; step 2 (compare with job `20261106-201041`) exited 1.
- **Found**: 8 own-checker verdicts differ from `lib/benchmark/results.json`, all on three conformance cases whose
  recorded verdict was `unverifiable` because of a class-initializer gap: `boom/1` (strict, advised: unverifiable ->
  violation; assume: verified -> violation), `inherited/1` (same three), `quiet/1` (strict, advised: unverifiable ->
  verified). The same cases account for the 4 "clauses grown" (1 -> 230) and the 3 "paths or merges changed" (paths
  None -> 1, merges None -> 0): the recorded runs stopped at the gap and solved nothing. 201 runs are "new" (cases the
  recording predates). The new verdicts agree with JBMC's recorded ones (`boom` violation, `quiet` verified). This reads
  as the own checker having gained class initializers since the recording, not as an effect of H1, but the job does
  not isolate the two: no run in the recording exercises a merge of different references, so H1's "same run as before"
  claim is untested by it, apart from the absence of any other changed run. I did not verify the class-initializer
  attribution against the git history of `lib/src/bmc/`.
- **Needs**: the foundations-heap loop (or whoever owns `lib/benchmark/results.json`) regenerates the recording on the
  current engine, so that the reference includes the 201 new runs and the class-initializer verdicts, then resubmits
  unchanged (`pipeline.py resubmit 20261107-041414-symbolic-references-in-the-own-checker-h`). Alternatively compare
  against a run at H1's parent commit, which isolates H1.
- **Tracked in**: `llm-dlc/loops/foundations-heap.md` step H1 (not yet updated).
- **Closes when**: the resubmitted job passes against a recording made at a commit without H1, or H1's parent.
- **Isolated runs** 2026-11-07 on `vm-1`: jobs `20261107-164450-vf-014-h1-isolated-run-1-of-2-the-benchm` (at H1's parent `b927e5df1be9`) and `-run-2-of-2-` (at H1 `ddbb54bac206`) both passed in 2m42s and 2m45s. Their outputs (`lib/target/benchmark-native.json`) stay in each job's `outputs/` and were not applied to the working copy (the files differ from the jobs' commits). The comparison job the descriptions name is the submitter's to queue; the entry stays open until it passes.
- **Closed** 2026-11-07 on `vm-1`, by the job above, run after runs 1 and 2 (`20261107-164450-…`) passed.
- **Fresh benchmark** 2026-11-07 on `vm-1`: job `20261107-183709-vf-014-a-fresh-lib-benchmark-results-jso` (at `c9995ae17d82`) passed in 1h37m (peak 6.0 GiB against an estimate of 4.5): no false success or alarm on any engine, mode or staging policy. `lib/benchmark/results.json` and `RESULTS.md` were replaced by collect (applied, no conflicts), so the stale file is gone.

### VF-019: under `auto --confirm`, the six nullable and may-alias claims of H2 get "no engine wrote a harness", which the conformance test counts as a disagreement

- **Status**: closed by job `20261107-172721-nullable-and-one-array-parameters-in-pro` (at `a1e29ec6a2e7`, 2026-11-07, `vm-1`): both ignored conformance tests passed.
- **Raised**: 2026-11-07 on `vm-1`. Job `20261107-043420-nullable-and-one-array-parameters-in-pro` at `d404b15cbac6`
  (heap stream, H2's first step).
  - Step 1's `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto` passed.
  - `the_corpus_agrees_with_the_jvm_under_auto_confirm` (`tests/conformance.rs:859`) failed with 20 disagreements.
- **Found**: 84 cases, 166 claims, 332 runs. The 20 disagreements are of two kinds:
  - **8 are VF-009's**: `boomTwice` and `enumBroken` at `n=0`, under strict and assume, unchanged.
  - **12 are new**: the six claims H2 widened, under `--gaps Strict` and `Assume`, each reported as "no engine wrote
    a harness". The claims are `twoArrays` with `may alias a,b` (two claims), `length` with `nullable a` (two), and
    `lengthOrMinusOne` with `nullable a` (two).

  The job's description expected these six to be refused under JBMC and `--confirm` (JBMC can't take a nullable or
  aliased input). So the refusal happens, but `--confirm` reports it as no harness at all, not as a named refusal,
  and the test counts it as a disagreement with the JVM. Not yet read in the code: whether `--confirm` refuses with
  a reason, or fails to make a harness and says nothing.
- **Needs**: `--confirm` refuses these with a named reason (an unverifiable result naming the input JBMC can't
  take). The test then reads a named refusal as no verdict, not a disagreement, as the heap stream's rule says:
  "`--confirm` refuses rather than confirming a different claim". This must not weaken the test: an unnamed "no
  harness" stays a failure. For the cleanup loop's jbmc stream, with VF-009, since the same test closes both.
- **Tracked in**: [`llm-dlc/loops/cleanup-jbmc.md`](../llm-dlc/loops/cleanup-jbmc.md) (J1).
- **Closes when**: job `20261107-043420-nullable-and-one-array-parameters-in-pro`, resubmitted unchanged at a fixing
  commit, passes.
- **Closed** 2026-11-07 on `vm-1`: job `20261107-172721-nullable-and-one-array-parameters-in-pro` (at `a1e29ec6a2e7`), the same job resubmitted after VF-009's fix, passed: both ignored conformance tests, `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto` and `the_corpus_agrees_with_the_jvm_under_auto_confirm`, in 1236 s. The six claims read as refused by name, no verdict, as the job expected.

### VF-017: examples 150, 151 and 152 fail on the result schema, which has no `object` parameter kind

- **Status**: closed by jobs `20261107-164043-example-150-crosscut-retry-throttle-a-re`, `-151-` and `-152-` (at
  `e7270fd85890`, 2026-11-07, `vm-1`): each passed in about 6 s with `example:as-expected`, 5 outputs applied each.
  The schema fix landed, and the three results are recorded.
- **Raised**: 2026-11-07 on `vm-1`. Jobs `20261107-064330-example-150-crosscut-retry-throttle-a-re`,
  `20261107-064331-example-151-…` and `20261107-064331-example-152-…`, at `224431e7bb68` (heap stream).
- **Found**: each fails within 5 s, after `jvmcontract equivalence` exits 0, as `build.py` validates the result:
  `result.json: 'object' is not one of ['primitive', 'array', 'record']`. The path in the schema is
  `$defs/statement/properties/domain/properties/parameters/items/properties/kind` in
  `examples/schema/result.schema.json`. It is unchanged at `main` (`34e1d87b`), so the three examples can't be
  recorded there either. H2's object parameters write `kind: object`, and the schema was never extended for them.
- **Needs**: the schema allows `object`, with whatever else an object parameter's domain entry carries (its
  constructor, nullability, aliasing: check the statement jvmcontract writes). Then a `test_build.py` case
  validating such a result. For the cleanup loop's examples stream.
- **Tracked in**: [`llm-dlc/loops/cleanup-examples.md`](../llm-dlc/loops/cleanup-examples.md) (E1).
- **Closes when**: the three jobs, resubmitted after the fix, pass with each example's expected verdict: 150
  verified; 151 a violation differing only in `result == throttle`; 152 verified within the constructor-made domain.

### VF-016: examples 160 and 161 fail before any proof: their subject is a caller the patch doesn't change

- **Status**: closed by jobs `20261107-165152-example-160-a-changed-refill-helper-prov` and `20261107-165153-example-161-a-refill-helper-aligned-to-t` (at `35a9ea8fadaa`, 2026-11-07, `vm-1`): both passed as expected.
- **Raised**: 2026-11-07 on `vm-1`. Jobs `20261107-053635-example-160-a-changed-refill-helper-prov` and
  `20261107-053635-example-161-a-refill-helper-aligned-to-t`, at `85ee8db14dfb` (summaries stream).
- **Found**: each fails in 0.2 s with "the patch does not change the subject file
  examples/apps/crosscut/src/main/java/net/terminalvalue/crosscut/ratelimit/RetryAfter.java"
  (`examples/tools/build.py:3523`). The examples are about a changed helper, `TokenBucket`, proved on its own and
  then used in its caller's proof. So the subject (`RetryAfter#nanosUntilToken`) is the caller, and the patch only
  touches `TokenBucket.java`. The check is the same one VF-002 trips on, for another reason: there the patch creates
  the subject, here it leaves it alone.
- **Needs**: `build.py` takes a subject the patch doesn't change, when the change is in the subject's code closure.
  Its excerpts then show the changed file. Or the examples name the helper's file and keep the caller as the
  symbol. For the cleanup loop's examples stream, with VF-002.
- **Tracked in**: [`llm-dlc/loops/cleanup-examples.md`](../llm-dlc/loops/cleanup-examples.md) (E1).
- **Closes when**: both jobs, resubmitted after the fix, pass with their expected verdicts: 160 verified with
  `lastAfter` shared, 161 a violation with no helper shared.
- **Seen again** 2026-11-07 on `vm-1`, in jobs `20261107-163050-example-160-a-changed-refill-helper-prov` and
  `20261107-163051-example-161-a-refill-helper-aligned-to-t` (at `d32ddc64d1a4`, resubmitted by the cleanup loop's
  examples stream). The subject check is fixed: the patch applies, the crosscut tests run, and `jvmcontract
  equivalence` runs (0.4 s; it exited 0 for 160 and 1 for 161, which for 161 is the expected violation). Both then
  fail in `build.py` after the proof, validating the result: `result.json: Additional properties are not allowed
  ('proofCache' was unexpected)`. `claim_scope` (`examples/tools/build.py:795`, from `85ee8db`) writes
  `scope.proofCache` for a B9 proof with the proof cache, but `examples/schema/result.schema.json` (statement's
  `scope`, around line 1161) doesn't list it, and is unchanged at the current `main`. **Needs**: the schema allows
  `proofCache` in a claim's scope, with a `test_build.py` case validating such a result; the cleanup loop's examples
  stream. Then resubmit both jobs unchanged.
- **Closed** 2026-11-07 on `vm-1`: jobs `20261107-165152-example-160-a-changed-refill-helper-prov` and `20261107-165153-example-161-a-refill-helper-aligned-to-t` (at `35a9ea8fadaa`) passed in 7 s each, 160 verified and 161 a violation, both `as expected`; the schema now accepts `proofCache`. Results applied.

### VF-010: the own checker's regression proof of `Pricing#total` sometimes runs out of time: its branch probes depend on wall-clock time

- **Status**: closed by jobs `20261107-165544-vf-010-s-reproducer-at-the-fix-pricing-t` and `20261107-165544-vf-010-s-integration-tests-at-the-fix-li` (at `f606b0d80e31`, 2026-11-07, `vm-1`): 8 of 8 alike, 64 integration tests passed. The verdict comparison is still to do (VF-021).
- **Raised**: 2026-11-06 on cvm, inline, while triaging job `20261106-203452`; seen again in full inline suite runs on
  2026-11-06 and 2026-11-07 (commits `xrrxwxny`, `vrkpmtqv`, `pkuyvwwp`).
- **Found**: `the_tools_own_checker_agrees_with_jbmc_on_integer_proofs` (`lib/tests/integration.rs`) fails now and then
  on the own checker's regression proof of `fixtures.Pricing#total` (the rounding refactor) and passes alone. Of 8
  identical runs of `jvmcontract equivalence --target 'fixtures.Pricing#total' --engine native --timeout 40`, 6 found
  the violation in about 4 s (13 solver calls, 2 of 2 divisions built in full) and 2 ran out of time at the 8th solver
  call (0 of 2 built). As read: the branch probes (`bmc/mod.rs`, `probe`) are given as long as the solver calls so far
  took, at least a second, so which side of a branch is left undecided, and with it the path order and the queries,
  depends on the machine's speed. One order leaves a query that doesn't finish.
- **Needs**: probe budgets that don't depend on wall-clock time (a count of conflicts or of solver calls, say), with
  the 8-run reproducer above showing every run alike.
- **Tracked in**: `llm-dlc/loops/engine-priorities-jbmc.md` (step 3's notes), `llm-dlc/loops/engine-priorities.md` (Next,
  item 8).
- **Closes when**: the reproducer gives the same answer in 8 of 8 runs, and a job runs the integration tests with no
  failure.
- **Reproducer before the fix, 2026-11-07 on `vm-1`** (28 CPUs, x86_64), job
  `20261107-163057-vf-010-s-reproducer-before-the-fix-prici` at `c307e721bdc3`: it did **not** reproduce here. All 8
  runs found the violation in 3.1 to 4.8 s with identical numbers (5 paths, 13 solver calls, 120989 variables, 412482
  clauses). The job's step exits 1 when all 8 agree, which it expected to be the other way round, so the job is
  recorded as failed; it is not a verdict on any code. So `vm-1` can't show the problem before the fix, and so can't
  show it gone after: the 2 of 8 runs that timed out were on `cvm` (a slower machine). Whoever fixes it should check
  the fix by the probe budget no longer reading the clock (a code check, or a count of solver calls that is the same
  across the runs), and run the reproducer on `cvm` for the before/after.
- **Closed** 2026-11-07 on `vm-1`: at the fix (`f606b0d80e31`) job `20261107-165544-vf-010-s-reproducer-at-the-fix-pricing-t` passed (8 of 8 runs found the violation, 3.1 s each, the same numbers every time: 6 paths, 12 solver calls) and `20261107-165544-vf-010-s-integration-tests-at-the-fix-li` passed (64 passed, 0 failed). Caveat: `vm-1` did not reproduce the problem before the fix either (see above), so this shows the fix is stable and breaks nothing, not that it cures the timeouts seen on `cvm`. The benchmark pair that compares recorded verdicts across the fix did not run: both jobs were killed by SIGTERM (VF-021).

### VF-009: `auto --confirm` disagrees with the JVM on `boomTwice` and `enumBroken`: JBMC's refutation at `n=0` is spurious, the own checker is right

- **Status**: closed by job `20261107-172721-jbmc-s-extra-initializers-named-and-refu` (at `a1e29ec6a2e7`, 2026-11-07, `vm-1`): the `auto --confirm` and JBMC corpus tests passed.
- **Raised**: 2026-11-07 on `vm-1`. Job `20261107-010728-jbmc-s-extra-initializers-named-and-refu` (at `254f1d7a4893`), step 2 (steps 1 and 3 passed: the corpus under JBMC and auto, and the draft report's example).
- **Found**: `the_corpus_agrees_with_the_jvm_under_auto_confirm` (tests/conformance.rs:792) has 8 disagreements, all on
  `boomTwice [assert result == 2]` and `enumBroken [assert result == 12]`, under `--gaps Strict` and `Assume`: Auto
  reports a violation at `n=0` that the JVM does not reproduce (the interpreter gives 2 and 12, the harness holds), and
  `--confirm` says the engines disagree: the own checker proves the property on every input and JBMC 6.11.0 refutes it
  on `n=0`. The same shape as VF-007 (closed by job `20261106-231317`) but on methods that run an exception handler
  twice and an enum initializer; the job's change (extra initializers named and refused in the preflight) did not
  cover them. Step 3's JBMC output ("1 of 13 failed") is the expected violation of that example.
- **Needs**: the engine-priorities-jbmc loop: why JBMC refutes `boomTwice(n=0)` and `enumBroken(n=0)` (a class
  initializer JBMC runs that the JVM does not? the `--throw-runtime-exceptions` path?), and refuse or model it.
- **Tracked in**: [`llm-dlc/loops/engine-priorities-jbmc.md`](../llm-dlc/loops/engine-priorities-jbmc.md). Deferred by
  the user on 2026-11-07, untriaged, until after the foundations loop; a candidate for the draft brief
  [`llm-dlc/loops/jbmc-upstream.md`](../llm-dlc/loops/jbmc-upstream.md) if JBMC's handling of a throwing initializer
  turns out to be the cause. Both methods are cases the engines-native stream added in Phase 5, step 3 (`ulstzomt`):
  the rest of that stream's cases agree with the JVM under JBMC and `auto` (jobs `20261107-012013`, `20261107-022319`),
  so this finding is all that is left of the engine-priorities brief's "conformance job for the native stream's step 3
  cases" (Next, item 8).
- **Closes when**: the same job, resubmitted unchanged at a fixing commit, has step 2 pass.
- **Triage run** 2026-11-07 on `vm-1`: job `20261107-163056-vf-009-triage-a-class-initializer-that-t` (at
  `2c352d909f21`, passed, 2m25s; it is evidence, it closes nothing). Step 1, the fixture
  `lib/tests/fixtures/jbmc-defects/F.java`: on the JVM `java -ea` prints `all hold, runs 4`. Stock JBMC 6.11.0 gives
  `VERIFICATION FAILED` on `wrapped`, `erroneous`, `once`, `enumWrapped`, `boomTwice` and `enumBroken`, and
  `VERIFICATION SUCCESSFUL` on `error`, alike with no flags, with `--throw-runtime-exceptions`, and with the flags
  jvmcontract passes. So the hypothesis holds: the divergence is in JBMC, not in jvmcontract's adapter. JBMC doesn't
  wrap a throw in a class initializer in `ExceptionInInitializerError` and doesn't mark the class erroneous
  (`NoClassDefFoundError` at its next use). Step 2, the corpus's two methods through `jvmcontract prove`: under
  `--engine jbmc` and `auto --confirm` both report a counterexample at `n=0` that "does not reproduce" in the
  interpreter, and `--confirm` reports the engines disagreeing, as in the entry. The log has the goto listings and each
  run's work directory. **Needs** (now more specific): refuse a target whose reachable code runs a class
  initializer that can throw (the preflight), or model the wrapping; a candidate for `jbmc-upstream.md`.
- **Seen again** 2026-11-07, unchanged (the same 8 disagreements), in job
  `20261107-043420-nullable-and-one-array-parameters-in-pro`, beside VF-019's 12. Taken by the cleanup loop's jbmc
  stream ([`cleanup-jbmc.md`](../llm-dlc/loops/cleanup-jbmc.md), J1).
- **Closed** 2026-11-07 on `vm-1`: job `20261107-172721-jbmc-s-extra-initializers-named-and-refu` (at `a1e29ec6a2e7`) passed all 3 steps: `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto` and `the_corpus_agrees_with_the_jvm_under_auto_confirm` both ok, and the draft report's example gives JBMC's two failures. The resubmitted VF-019 job passed `auto_confirm` as well. A guard job, `20261107-171442-vf-009-s-guard-measured-the-41-recorded` (3 steps passed), shows the fix costs no recorded JBMC example: step 1 is as in `-000039` (only 037 differs, a JBMC defect), and no throwing-initializer line appears.

### VF-012: the own checker raises a false alarm on `conformance/leadingZerosLong/2`, so the benchmark step exits 1 and the encoding-timing check never ran

- **Status**: closed by job `20261107-033320-the-own-checker-s-encoding-timed-whole-p` (at `dc03b87fb961`, `vm-1`, 2026-11-07): both steps passed, so no false alarm and the timing comparison ran and passed
- **Raised**: 2026-11-07 on `vm-1` (run with `--memory 7G --workers 3`). Job
  `20261107-032249-the-own-checker-s-encoding-timed-whole-p` at `58b89dd9ce1c`.
- **Found**: step 1 (`lib/benchmark/run.py --engines native`) ran all 533 own-checker runs in 143 s and exited 1,
  because three runs are classed `false-alarm`: `conformance/leadingZerosLong/2` under strict, assume and advised. The
  own checker reports `violation` with witness `48` in 0.04 s (610 variables, 2114 clauses), and the JVM replay says
  `witnessOnTheJvm: holds`, i.e. the witness is spurious. The case is not in the committed `lib/benchmark/results.json`
  (new since that run, probably from the numberOfLeadingZeros change), so this is not a regression of the encoding
  timing. Step 2 (no run flagged `phasesExcess`; median seconds ratio against job `20261106-201041` at most 1.10) was
  skipped. Read from the saved JSON in the work directory: 0 of 533 runs carry `phasesExcess`, which is promising but
  is not the check the job names, and the ratio was not computed. No other reference disagreement.
- **Needs**: whoever owns the `Long.numberOfLeadingZeros` modelling in the own checker (the engine-priorities loop)
  fixes the encoding behind case `leadingZerosLong/2` or marks the case as expected-unsupported; then the job is
  resubmitted unchanged (`pipeline.py resubmit 20261107-032249-the-own-checker-s-encoding-timed-whole-p`).
- **Update 2026-11-07 (cause found, fixed in the benchmark runner)**: the own checker's witness is right, and the JVM
  replay misread it. Run inline, `jvmcontract prove ... 'conformance.Conformance#leadingZerosLong' --assert
  'result < 64' --engine native --gaps strict` reports `leadingZerosLong(arg0=0)`, outcome 64, which the JVM bears out.
  The tool writes a `long` input as a decimal string (`"0"`), and `lib/benchmark/run.py`'s `token()` took any
  one-character string for a `char` and passed its code unit: `ord('0')`, 48, where `numberOfLeadingZeros(48)` is 58.
  Every single-digit `long`, `float` or `double` witness, alone or in an array, was misread that way. This case is the
  first in the corpus whose witness is one. `witness_arguments` now reads an input as a `char` only if its declared
  type is one. `test_a_long_or_a_double_witness_of_one_digit_is_its_value_not_a_char` failed before the fix
  (`48;[48,-2,55];53`) and passes after it. Step 2's check run by hand on the job's saved
  `lib/target/benchmark-native.json`: 0 of 533 runs flagged, median ratio 0.963 (quartiles 0.871 to 1.006) over the 29
  runs of 0.1 s or more, 31.5 s against 32.0 s over the 356 paired runs. Resubmitted unchanged.
- **Tracked in**: the job's `logs/1-benchmark-own-checker-only.log`.
- **Closes when**: the resubmitted job passes (no false alarm, no `phasesExcess`, median ratio at most 1.10).
- **Result**: 533 own-checker runs, 0 flagged `phasesExcess` (reference job: 1 of 356); median seconds ratio 0.974 over 29 runs of 0.1 s or more (quartiles 0.872 to 1.002).

### VF-008: the conformance corpus under JBMC and auto: JBMC says `Verified` on `declaring`, which the JVM refutes

- **Status**: closed by job `20261107-012013-jbmc-s-stubs-on-no-path-are-no-gaps-exam` (at `8b45798e6417`, 2026-11-07, `vm-1`): step 5 ran `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto` and it passed (646 s). Not the same job resubmitted, but the same test.
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-203501-examples-071-and-013-under-strict-with-t` (at `7457928f1864`), step 6.
- **Found**: `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto` (tests/conformance.rs:749) reports 1 disagreement out of
  73 cases: `declaring [assert result == n + 107]`, `--gaps strict` on JBMC says Verified ("2 properties proved over
  n: int in 0.2 s; loops unwound 16 times with unwinding assertions") and the JVM refutes it. This is the unsoundness
  VF-001 describes, now on a case the strict policy was meant to cover.
- **Needs**: the engine-priorities-jbmc loop (or whoever owns the JBMC staging policy) to find why strict lets this
  proof through (a model or exception path unmodelled?), and add the case to the brief's Progress.
- **Tracked in**: [`llm-dlc/loops/engine-priorities-jbmc.md`](../llm-dlc/loops/engine-priorities-jbmc.md); see also VF-001.
- **Closes when**: the same job, resubmitted unchanged at a fixing commit, has step 6 pass.

### VF-005: example 071 under strict: the first two proofs are `unverifiable` on JDK 25.0.5 where the job expects `verified` with no gap

- **Status**: closed by job `20261107-024759-jbmc-s-stubs-on-no-path-are-no-gaps-exam` (at `854a0d8f756e`, 2026-11-07, `vm-1`): step 3, `071: the first two proofs stand with no gap`, passed, with obligations 0 and 1 verified and no gaps (the `Collection` stubs reached by JBMC's call graph and never entered), after the preflight's index fix (`xmslpytz`). Not the same job resubmitted, but the same assertion.
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-203501-examples-071-and-013-under-strict-with-t` (at `7457928f1864`), step 3 (steps 1, 2, 4 and 5 passed: 013 under strict, and the contract library recorded on this JDK).
- **Found**: the assertion that obligations 0 and 1 of example 071's result are `verified` with no gaps fails: they are
  `unverifiable` with gaps `jdk-reference-method:java.util.Collection.toArray()...@jdk-25.0.5` and
  `jdk-primitive-method:java.util.Collection.isEmpty()Z@jdk-25.0.5`. Step 2 ran the example's own build as expected,
  so the example stands and the expectation about the models (Enum and List) is what does not hold: the models were
  not enough on JDK 25.0.5, or the recorded library does not cover `Collection`. (The 41-example job saw 071#0 and 071#1 unresolved on `Enum.<init>`/`List.of`, a different gap set.)
- **Update 2026-11-07**: job `20261107-012013-jbmc-s-stubs-on-no-path-are-no-gaps-exam` (at `8b45798e6417`, `vm-1`) step 3 fails
  in a new way: the stubs on no path are now named as "no gaps" in the output (`note: JBMC's call graph reaches 2 stubs
  ... never enters ... no gaps: Collection.isEmpty(), Collection.toArray()`), but obligations 0 and 1 are still
  `unverifiable` with an empty gap list, where the job expects `verified`. Steps 2 (071 build), 4 (013 under strict) and 5 (corpus) passed.
  So the gap is gone and the verdict is not: something else in the strict path still withholds the proof.
- **Needs**: the submitter to say whether the `Collection` methods should be modelled or the expectation relaxed, and
  why an obligation with no gaps is `unverifiable` (see the verifier-output.txt of the job's 071 output).
- **Tracked in**: [`llm-dlc/loops/engine-priorities.md`](../llm-dlc/loops/engine-priorities.md).
- **Closes when**: the job, resubmitted unchanged at a commit that fixes it, passes step 3.

### VF-007: engine-priorities step 3: escaping exceptions: `auto --confirm` disagrees with the JVM on 12 claims, and an integration test times out

- **Status**: closed by job `20261106-231317-jbmc-s-defects-under-confirm-the-unmaske` (at `14607996bdca`, 2026-11-06, `vm-1`): the same three commands as `20261106-203452`, all three steps passed (33m53s, peak 1.3 GiB). The `Pricing#total` timeout did not recur.
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-203452-jbmc-s-escaping-exceptions-named-and-ref` (at `ffb68ef59525`), steps 1 and 3. Step 2 (corpus under JBMC and auto) passed.
- **Found**: step 3 (`the_corpus_agrees_with_the_jvm_under_auto_confirm`, tests/conformance.rs:689) has 12
  disagreements, all on methods that catch an exception (`caught`, `caughtAsRuntime`, `nestedHandler`, with `n=0`):
  Auto under `--gaps Strict` and `Assume` reports a violation the JVM does not reproduce (the harness holds), and
  `--confirm` says the engines disagree: the tool's own checker proves `n != 0 || result == -1` and JBMC refutes it on
  `n=0`, while the interpreter gives -1. So JBMC's counterexample is spurious on caught exceptions (not the checker).
  Step 1: integration test `the_tools_own_checker_agrees_with_jbmc_on_integer_proofs` (tests/integration.rs:1431) got
  Unverifiable ("the solver did not finish within the time limit") for `fixtures.Pricing#total`, expected Violation;
  62 other tests passed (703 s). That one may be a time limit on a 2 CPU job rather than a logic fault: not rerun to tell.
- **Needs**: the engine-priorities-jbmc loop: fix the handling of caught exceptions in the JBMC path, and decide whether
  the `Pricing#total` test needs a larger solver limit or a fixed expectation.
- **Tracked in**: [`llm-dlc/loops/engine-priorities-jbmc.md`](../llm-dlc/loops/engine-priorities-jbmc.md).
- **Closes when**: the same job, resubmitted unchanged, passes all three steps.

### VF-006: engine-priorities step 4a: the 41-example gap-table job fails on a schema error, so no table exists

- **Status**: closed by job `20261107-000039-the-41-recorded-jbmc-examples-under-stri` (at `98bab48570e6`, 2026-11-07, `vm-1`): all three steps passed (4m22s, peak 1.1 GiB); 41 examples, 43 obligations in the table on both engines. 5 of 43 obligations differ in status between jbmc and native (013#0, 035#0, 052#0, 071#2, 127#0), as the brief wanted listed; 6 native obligations have no verdict at a gap (013#0, 037#0, 071#0, 071#1, 071#2, 127#0), and 037#0 is refused at a JBMC defect. Those are results for step 4a, not failures of the job.
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-204220-the-41-recorded-jbmc-examples-under-stri` (at `61f5e48d1abf`).
- **Found**: steps 1 and 2 stop at "result.json: Additional properties are not allowed ('sat' was unexpected)" on
  example 013, in the result schema check of `build.py`'s attempt. Only 9 of the 41 examples reached the table (32 skipped as "not format 2"), so step 3's assertion `9 examples in the table, not 41` also fails. The same schema complaint ('newProblems' unexpected) is in older B12 results, so the result schema may lag the writer.
- **Update 2026-11-06**: rerun `20261106-231837-the-41-recorded-jbmc-examples-under-stri` (at `835d5f28cbfd`, `vm-1`) fails again in a new way: step 2 (own checker) exits 1 at "result.json: Additional properties are not allowed ('phasesExcess' was unexpected)" on a `jvmcontract prove` attempt (attempt 018), so `sat` is fixed but the schema still lags the writer on another field. Steps 1 passed. Only 12 of 41 examples reach the table (29 skipped as "not format 2"), so step 3 again fails with `12 examples in the table, not 41`. Example 013 differs from its expected verdict (013#0 unresolved on `TermOrder.<clinit>`); 071#0 and 071#1 are unresolved on `Enum.<init>`, `List.copyOf`, `List.of` (see VF-005).
- **Needs**: the submitter (engine-priorities step 4a): add `sat` and `phasesExcess` to the result schema (or stop writing them; check every field the writer emits against it), check that the 41 examples carry format-2 results with gaps recorded, then resubmit.
- **Tracked in**: [`llm-dlc/loops/engine-priorities.md`](../llm-dlc/loops/engine-priorities.md).
- **Closes when**: the job, resubmitted, passes with 41 examples in the table.

### VF-004: the CBMC 6.11.0 source-reading job's grep for `run_property_decider` matches nothing

- **Status**: closed (job `20261106-194328-cbmc-6-11-0-s-source-times-runtime-post`, passed 2026-11-06 at `3feadaf0f7a2`: the corrected grep matched and all three checks found their strings)
- **Raised**: 2026-11-06 on `vm-1` (run with `--memory 8G --workers 2`). Job
  `20261106-192959-cbmc-6-11-0-s-source-times-runtime-post` at `b4c0164b852f`.
- **Found**: both files download (sha256 in the log) and step 1 prints the `== bmc_util.cpp: run_property_decider`
  header, then exits 1 after 0.4 s with no further output. Under `set -euo pipefail` the next command,
  `grep -n -A45 "^decision_proceduret::resultt run_property_decider" bmc_util.cpp`, matched nothing: that return type
  and line layout is not how 6.11.0 declares the function (likely a different return type or the name on its own line
  after the type). So the job never reached the `Runtime Solver` / `Runtime Post-process` / `finish_eager_conversion`
  checks. This is a defect in the job's step, not a finding about CBMC. I did not edit the step.
- **Needs**: the submitter resubmits with a pattern that matches (for instance `grep -n -B2 -A45 "run_property_decider("`),
  or drops the `-n -A` display and keeps the three `grep -q` checks.
- **Tracked in**: the job's `logs/1-fetch-and-show-cbmc-6-11-0-s-s.log`.
- **Closes when**: the corrected job passes.

### VF-003: Bitwuzla 0.8.2 builds but the installed binary cannot load `libcadical.so`

- **Status**: closed (job `20261106-194049-bitwuzla-0-8-2-built-from-source-cadical`, passed 2026-11-06 at `66dd857b6891`: CaDiCaL linked static, `bitwuzla --version` 0.8.2, three smoke queries gave the expected sat/unsat, C API through pkg-config works)
- **Raised**: 2026-11-06 on this 24-CPU host (run with `--memory 8G --workers 2`). Job
  `20261106-192008-bitwuzla-0-8-2-built-from-source-for-the` at `3853fcc7e8b7`.
- **Found**: `lib/solvers/bitwuzla/build.sh 0.8.2` downloads, compiles (217 targets, 24 s, peak 1.9 GiB) and installs into
  `~/tools/bitwuzla/bitwuzla-0.8.2`, then its check exits 127: `bitwuzla: error while loading shared libraries:
  libcadical.so: cannot open shared object file`. The shared-library build links CaDiCaL as a shared subproject, but
  no `libcadical.so` exists anywhere under `~/tools/bitwuzla`: meson did not install it (or no rpath points at it).
  Deterministic; not a resource problem. The partial install is left in place.
- **Needs**: whoever owns the solver comparison fixes `build.sh`: install CaDiCaL's library into the prefix with an
  rpath, or build CaDiCaL static, and check with `ldd` before the version smoke test.
- **Tracked in**: the job's `logs/1-build-bitwuzla-0-8-2.log`.
- **Closes when**: the job, resubmitted after the fix, passes.

None yet.
