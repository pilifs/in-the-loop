# Feature loop: example-targets-runtime

Started 2026-11-14 15:26:46 UTC, no limit on cycles, session 3bb5a1f4-a4d5-4f4a-b511-6037ef3e1256, claude-opus-5-5 at high effort, after change qpvlyptuzssruqtxruvqznvkntkoknup.

> Work on the brief in `llm-dlc/loops/example-targets-runtime.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'qpvlyptuzssruqtxruvqznvkntkoknup..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next, and if it ends with a `- Status:` line, keep that line current there too: `working` while a piece of work that needs only you is left, otherwise the status the brief's `## Loop until` gives for stopping (`waiting on jobs ID ...` with the job ids, `done`, or `blocked: ...` with what needs the user or another stream). If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `llm-dlc/loops/example-targets-runtime.md` at sha256 ab8f272168fe42ea6d06a4a603e829f62a1677726cfe8791a9b612ad69370a8e.

After each commit the session decides whether to go on:

> Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with `waiting on jobs ID ...`. Stop with `done` when R1–R5 and your acceptance pass, or each is deferred by the timebox with the finding. Stop with `blocked: ...` when what is left needs the user or another stream, and is recorded under Progress. Don't grow into general Spring emulation or a broad CVE campaign. Anything new you find goes under Progress, for the main brief's for-review list.

## Commits

Session 3bb5a1f4-a4d5-4f4a-b511-6037ef3e1256 was forked from session e9be5afb-09c9-4473-a9e9-38f2fb61ca80.

- cycle 1, 2026-11-14 15:38:04, `muqvuqyqpwyz`: example-targets runtime R1: source locks and the fixture route's preparation
  - decided to continue: The loop should go on. This run has one commit, cycle 1's `muqvuqyq`, which finished R1 on the fixture route. Most items still have steps that need only my own work: - R4's separate-JVM controls on the fixture, for A3/A4; - R2's published-artifact route, with Maven Central acquisition and a cache that checks hashes; - R3's `run_verifier`, once `jvmcontract` is compiled inline; - R5's slice. Nothing waits on jobs yet, and nothing is blocked on the user or another stream.
- cycle 2, 2026-11-14 15:48:47, `tvvqulnktmut`: example-targets runtime R4: each fixture revision's controls in its own JVM, per JDK
  - decided to continue: This run has two commits: R1 on the fixture route (`muqvuqyq`) and R4's separate-JVM controls (`tvvqulnk`). Contract rows A2 and A3/A4 now pass. Three items still have steps that need only my own work: R2's published-artifact route (Maven Central downloads with a cache that rechecks hashes), R3's `run_verifier` once `jvmcontract` is compiled inline, and R5's slice on a pinned spring-core method. Nothing waits on jobs yet, and nothing is blocked on the user or another stream.
- cycle 3, 2026-11-14 16:00:39, `uoztsmtquttr`: example-targets runtime R2: the published-artifact route, hash-pinned acquisition and a rechecked cache
  - decided to continue: This run has three commits so far: R1 on the fixture route, R4's separate-JVM controls, and now R2's published-artifact route with downloads that check each file's hash and a cache that rechecks on reuse. Three items still have steps that need only my own work. They are R5's slice on the already pinned spring-core JAR, R3's `run_verifier` once `jvmcontract` is compiled inline, and writing and submitting the upstream-build route as a job. No jobs are pending yet, and nothing left waits on the user or another stream.
- cycle 4, 2026-11-14 16:12:26, `zuzrkvturtxk`: example-targets runtime R5: the vertical slice on PatternMatchUtils.simpleMatch from published spring-core
  - decided to continue: This run has four commits: R1 on the fixture route, R4's separate-JVM controls, R2's published-artifact route and now R5's slice on published spring-core. Two items still need only my own work: R3's `run_verifier`, once `jvmcontract` is compiled inline in this workspace, and writing and submitting the upstream build route's job. No jobs are pending, and nothing left waits on the user or another stream, so the loop should go on.
- cycle 5, 2026-11-14 16:30:16, `qktukqzvvsyx`: example-targets runtime R3: run_verifier, jvmcontract on the prepared original artifacts (verification pending)
  - decided to continue: This run has five commits: R1, R4, R2's published-artifact route, R5's slice, and now R3's `run_verifier`, whose real-verifier check waits on job `20261114-162937-example-targets-runtime-r3-run-verifier`. Not everything waits on that job. Three pieces still need only my own work: reading workflow's `published` list shape, preparing constructed mutants, and building the upstream-build route and writing its job. All three are recorded under Progress, and none needs the user or another stream.
- cycle 6, 2026-11-14 16:46:38, `okmwswxnonkr`: example-targets runtime: VF-024, equivalence on class directories, recorded parameter names, the fixture recipe's flags (verification pending)
  - decided to continue: This run has seven commits: R1, R4, R2's published route, R5, R3, W1's `published` list, and the VF-024 fixes. Only the R3 rerun (`20261114-164239-…`) is waiting on a job. The upstream-build route still needs only my own work: the checkout, the build-tool and JDK recording, unit tests with a stand-in build tool, then 105's real pinned revisions as a job. 105, 305 and 307 need that route, and A5 runs on 105. Constructed-mutant preparation, which builds on that checkout, also comes after it, so the loop isn't waiting only on jobs or blocked.
- cycle 7, 2026-11-14 17:26:10, `npvxmlwzpwmk`: example-targets runtime R2: the upstream-build route, the pinned commit checked out and built by its own Maven (verification pending)
  - decided to continue: Constructed-mutant preparation still needs only my own work. W1 gives mutants a defined shape, and the positive and negative streams have since added mutants to their packets (306's dropped-prefix mutant, the 285 packet's). The memory also records a trial integration that found three errors between runtime and workflow, which the next cycle should look at; and `runtime_upstream.py` and `test_runtime_upstream.py` changed on disk after my commit, so the next cycle has to check first whose change that is. Only the two jobs, `20261114-164239-…` and `20261114-170353-…`, are waiting, so the loop isn't down to jobs alone.
- cycle 8, 2026-11-14 17:42:44, `nptowlpnxuzn`: example-targets runtime R2: the upstream build's dependency classpath filtered to the runtime scope (verification pending)
  - decided to continue: Constructed-mutant preparation still needs only my own work: a mutant is still Unsupported in `lock`, and W1 has already defined the mutant entry and the patch-then-build request. Only the upstream rerun job, `20261114-174017`, is waiting, so the loop isn't down to jobs alone. R1–R5 are otherwise in place, and the integration report's failures in my files are fixed.
- cycle 9, 2026-11-14 18:06:57, `wkkwovlzqrns`: example-targets runtime R2: constructed mutants prepared on all three routes, their base patched with git apply, then built (verification pending)
  - decided to stop: The loop should stop: everything left waits on a job. R1–R5 are done and every acceptance row has its evidence, including the upstream-build route on a real pinned revision (whose rerun passed) and constructed-mutant preparation, now implemented on all three routes. The one open piece is job `20261114-180443-example-targets-runtime-r2-a-constructed`, the published-route mutant on real spring-core bytes, and the brief's status already says it is waiting on that job.

## Summary

# Example-targets runtime stream: feature loop summary (9 cycles, 11 commits)

The loop stopped with **`waiting on jobs ID 20261114-180443-example-targets-runtime-r2-a-constructed`**. R1–R5 are implemented, and every acceptance row has passing evidence except one: the published-route constructed mutant on real spring-core bytes, which is still queued. The working copy is empty.

## Commits (oldest first)

| Change | What it adds | How it was verified |
|---|---|---|
| `muqvuqyq` **R1: source locks and the fixture route** | `runtime.lock()` locks and hashes every source, adapter, driver and oracle offline. `runtime.prepare()` for `route: fixture` reproduces `build_fixtures.py`'s recipe byte for byte, records the ordered classpath and the target's origin, and writes `prepared.json`. A preparation is refused, with the stage that failed, when a class appears twice on the classpath, the target method is missing, the adapter never calls the target, the compile fails, a source changes after the lock, or the work directory is stale. New modules: `runtime_jdk.py` and `runtime_jar.py`, a small class-file reader. | Contract A2: 3 pass. `test_runtime.py`: 19 tests. |
| `tvvqulnk` **R4: controls per JVM, per JDK** | `run_controls()` runs each revision's driver in its own JVM, with a fixed environment that inherits nothing (`JAVA_TOOL_OPTIONS` and `CLASSPATH` included). It runs on each JDK the entry names, by full path. Each record names the JDK, the commit, every classpath entry with its hash and role, and the inputs. | Unit tests and the integration script. |
| `uoztsmtq` **R2: the published-artifact route** | Locks that pin each JAR by hash, offline. Dynamic versions (ranges, LATEST, SNAPSHOT) and `network: true` are refused. JARs come from Maven Central into a cache that is rechecked on every use. | Unit tests. |
| `zuzrkvtu` **R5: the vertical slice** | `runtime_slice.py` runs `PatternMatchUtils.simpleMatch` from published spring-core 5.3.18 and 5.3.19 end to end. Its case folder is `runtime_simplematch/`. | Ran end to end offline from the cache. Integration script exits 0. |
| `qktukqzv` **R3: `run_verifier`** | Runs jvmcontract on the prepared original artifacts. Calibration job queued. | First job **failed** (VF-024, below). Fixed in `okmwswxn`. |
| `qlvsxysy` **W1's `published` list accepted** | Published revisions can carry their JARs as workflow W1's `published` list. The old shape still locks to the same lock, and mixed or malformed shapes are refused. | `test_runtime.py`: 52 tests. Slice passed offline. |
| `okmwswxn` **VF-024 fix** | Equivalence checks work on class directories. Parameter names are read from the class file (MethodParameters or LocalVariableTable). The fixture recipe takes extra javac flags (`--fixture-javac-flag=-parameters`). | Job `…164239` **passed**: all five expected verdicts. VF-024 is closed. |
| `npvxmlwz` **R2: the upstream-build route** | Checks out the pinned commit and builds it with its own Maven. The build must leave tracked files unchanged, and the recorded parent is checked. | Job `…170353` **passed** on example 105's two commons-numbers commits (59 s, 858 MiB). Before disagrees with the oracle only at `pow(-2, 31)`, after nowhere, and JDK 21 and 25 agree. |
| `pvwsoqrk` **Receipts and W1 claims** | Fixes from the 17:13 integration report. Runs now write receipts under a copy of the case folder, where `route.run` expects them, never into the repository. W1's shipped claims are tolerated. | The three integration failures are fixed. Integration script exits 0. |
| `nptowlpn` **Runtime-scope classpath** | The upstream build's dependency classpath was found to include test-scope JARs: the scope filter used the wrong property name. It now uses `-DincludeScope=runtime`. | Rerun job `…174017` **passed** (57.5 s, 783 MiB). Classpath is exactly original, adapter and driver. Same verdicts as before. |
| `wkkwovlz` **R2: constructed mutants on all three routes** | A sidecar can declare a mutant (base revision plus patch, W1's shape). On every route the patch is applied to the base with `git apply` (checked first) and the result is built. On the published route, the patched `.java` is recompiled against the base JARs with matching `--release`, `-g` and `-parameters`, and the new classes replace the base's in a copy of the JAR. The same files are also compiled unpatched, to show how much the compiler alone changes the bytes. Signed JARs, stale nested classes, release-specific class copies and mismatched debug attributes are refused. Adds `runtime_simplematch/mutation.json` and `mutant/suffix-anywhere.patch`: `endsWith` becomes `contains`. | `test_runtime.py` 63 tests and `test_runtime_upstream.py` 22. The fixture-route mutant equals `build_fixtures.py`'s `mutant.jar` byte for byte. The mutation pair replays as recorded on all three routes. Integration script exits 0: contract 8 pass and 8 skip, targets 125, `test_build` 190, `test_pipeline` 29. Real-bytes job **pending**. |

## Verification jobs

- **Pending:** `20261114-180443-example-targets-runtime-r2-a-constructed` (2 CPU, 3 GiB, about 15 min, at `b5e28e26`).
  - It prepares spring-core 5.3.19 and its constructed mutant, then replays both.
  - Expected: the mutant disagrees with the oracle at `("*bc","bcx")`, `("a*c*e","abced")` and `("*a*b","acba")`, 5.3.19 nowhere, and JDK 21 and 25 agree.
  - The three disagreements are a Python model's prediction, not yet evidence.
  - If the job passes as expected, the stream can be marked `done`.
- **Failed, but superseded:** `20261114-162937-example-targets-runtime-r3-run-verifier` (VF-024). Its fix passed as `…164239`, so nothing is needed except closing it out when you triage.
- Passed: `…164239`, `…170353`, `…174017`.

## `sync.py check`

- **0 warnings** for you to judge.
- **33 errors** ("session … has no manifest" or "points at log … the manifest does not list"). None is on this run's commits.
  - They are on other sessions' changes in the ancestry: `tlmknmsz`, `plxytuvu`, `mpqzpuvo`, `orwvprts`, `ylkxyuvy` and others.
  - These look like the trace files after a merge, which `python3 llm-dlc/tools/sync.py regenerate` should fix. I left them alone because they aren't this session's.
  - The push won't be clean until they are fixed.

## Needs your input (decisions for the merge)

1. **`build_fixtures.py` should compile with `-parameters`** (from VF-024).
   - Phase 0's fixture classes record no parameter names, so jvmcontract calls `Gate.allowed`'s parameter `arg0`. The sidecar and claim files say `code` and `field`.
   - The fix belongs to the coordinator: add `JAVAC_FLAGS = ("-parameters",)` to `build_fixtures.py`. The fixture JAR hashes then change in both places alike.
   - The alternative is to rewrite the claims to use `arg0`.
   - Until then, contract A5's fixture rows will fail at the merge.
2. **Moving `mutation.json` into `target.json`.** Once W1's schema is merged, `runtime_simplematch/mutation.json` moves into the slice's `target.json` unchanged. Positive's example 306 can then declare its `controls/drop-prefix.patch` as a W1 `mutant` of `release-after`, which is acceptance A4's "nearby constructed mutation".
3. **Optional additions to the shared interface:**
   - `PreparedTarget.blocker` and `PreparedTarget.workdir`. Today the blocker lives in `source`, and the work directory is found by `route.py`'s layout convention.
   - A claim-schema key that names an adapter entry point. Without it, the verifier can't go through an adapter, and such tasks stay capability gaps or need `--plan`.

## Other items for review

- A mutant's JAR has role `original`, the slot under test. Its origin starts `constructed:`, and its record and verifier scope (`constructed-mutation`) name the base and the patch.
- On the published route, that the commit's source matches the published JAR is taken from the sidecar and recorded as unchecked. The `unpatchedRecompile` record shows how much of the mutant's difference comes from the compiler rather than the patch.
- The published-route dependency closure is only what the lock declares; no POM is resolved. A missing dependency shows up as a `NoClassDefFoundError` in the controls, which counts as a replay failure, not a result.
- There is no checkout or build cache: every upstream preparation fetches its commit and plugins again. The acceptance allows a cache but doesn't need one.
- A killed control run records exit code `-9` (as `build.py` does), but the constructed `bad-runs.json` record has `None`. Either way its status is `killed`. This one is for workflow's W2.
- For the negative and positive streams: `PatternMatchUtils.class` is byte-identical in spring-core 5.3.18 and 5.3.19. The CVE-2022-22968 fix changed `DataBinder`, so a packet that reaches `simpleMatch` calls the same code in both versions.
- Nothing was pushed.

Ended 2026-11-14 18:09:12 after 9 cycle(s): the session decided to stop; the brief says waiting on jobs ID 20261114-180443-example-targets-runtime-r2-a-constructed.
