# Feature loop: example-targets-runtime

Started 2026-11-14 18:19:12 UTC, no limit on cycles, session 3bb5a1f4-a4d5-4f4a-b511-6037ef3e1256, claude-opus-5-5 at high effort, after change wkkwovlzqrnszuttnmqwquyuyyzwvprx.

> Work on the brief in `llm-dlc/loops/example-targets-runtime.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'wkkwovlzqrnszuttnmqwquyuyyzwvprx..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next, and if it ends with a `- Status:` line, keep that line current there too: `working` while a piece of work that needs only you is left, otherwise the status the brief's `## Loop until` gives for stopping (`waiting on jobs ID ...` with the job ids, `done`, or `blocked: ...` with what needs the user or another stream). If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `llm-dlc/loops/example-targets-runtime.md` at sha256 ab8f272168fe42ea6d06a4a603e829f62a1677726cfe8791a9b612ad69370a8e.

After each commit the session decides whether to go on:

> Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with `waiting on jobs ID ...`. Stop with `done` when R1–R5 and your acceptance pass, or each is deferred by the timebox with the finding. Stop with `blocked: ...` when what is left needs the user or another stream, and is recorded under Progress. Don't grow into general Spring emulation or a broad CVE campaign. Anything new you find goes under Progress, for the main brief's for-review list.

## Commits

- cycle 1, 2026-11-14 18:23:23, `qrsyzzwuqwrx`: example-targets runtime: the constructed-mutant job passed, R1-R5 and the acceptance done; VF-025's JARs needn't be in the history
  - decided to stop: The loop should stop, because the brief's stop condition for `done` is met: R1–R5 and every acceptance row now pass. The last job, the constructed mutant on real spring-core bytes, passed with exactly the three predicted disagreements, and the brief's status already reads `done`. What is left either needs the user (closing VF-025 means editing the shared `.gitignore` on main) or belongs to the merge, such as `build_fixtures.py` compiling with `-parameters` and moving `mutation.json` into `target.json`. All of it is recorded under Progress.

## Summary

# Example-targets runtime: end of feature loop (1 cycle)

The stream's brief status is now **`done`**. All of R1–R5 and the runtime acceptance rows pass. Nothing was pushed.

## Commit this run

### `qrsyzzwu` (5f5da4ae): the constructed-mutant job passed; R1–R5 and the acceptance done; VF-025's JARs needn't be in the history

**What it adds:**
- **The mutant job's results**, recorded in `examples/tools/targets/runtime_simplematch/README.md`. The job built a mutant of spring-core 5.3.19's `PatternMatchUtils.simpleMatch`: the patch was applied with `git apply` and the file recompiled into a copy of the published JAR.
  - **Base 5.3.19:** agrees with the oracle on all 45 probes, on JDK 21 and on JDK 25.
  - **The mutant:** disagrees on exactly three probes, the ones predicted: `("*bc","bcx")`, `("a*c*e","abced")` and `("*a*b","acba")`. Each gives `true` where the statement says `false`. The two JDKs agree.
  - **The recompile was faithful:** javac 25 used `--release 8 -g -parameters`, the flags read off the published class.
  - **One caveat is recorded:** recompiling the *unpatched* file doesn't give a byte-identical class (`b45705e5…` against the published `8562b278…`). So the mutant differs from 5.3.19 by the patch and by the compiler.
- **Updates to the brief's `## Progress`:**
  - an entry on the job's result;
  - this loop's decision on VF-025 (below);
  - a row-by-row record that R1–R5 and the acceptance pass;
  - the list of items left for the merge;
  - `Status: done`.

**How it was verified:**
- Job `20261114-180443-example-targets-runtime-r2-a-constructed` passed (2 steps, 6.2 s, peak 197 MiB).
- I read its logs, `changes.diff` and `prepared.json`. The mutant's patched-file hash, base commit, classpath and class/JAR hashes match what was submitted.
- The integration report (last written 17:28) shows no failure in runtime's files.
- The only open finding in runtime's files is VF-025.

## Verification jobs

On main, none of this stream's jobs is pending or running.

| Job | Result |
|---|---|
| `20261114-162937` R3 run_verifier | **failed**. This was before VF-024's fix, and `20261114-164239` supersedes it. |
| `20261114-164239` R3 after VF-024 | passed |
| `20261114-170353` R2 upstream-build route | passed |
| `20261114-174017` R2 upstream-build rerun with the scope filter | passed |
| `20261114-180443` R2 constructed mutant | passed |

This workspace's copy of the queue still lists all five as "pending". That is only because the workspace hasn't been updated since main collected them. The results above are from the default workspace.

## `sync.py check`

- **0 warnings** for you to judge, and 198 notes.
- **34 errors**, none from this run's session. They are all "session … has no manifest" or "points at a log the manifest does not list".
  - They sit on other sessions' changes: eaff7dd7, 70d4b729, ddf78f27, 133eee93, 278c4037, c9b766bf, 8b430aa4, and 5e358522 (the verification loop).
  - These look like the merged-streams case, so `python3 llm-dlc/tools/sync.py regenerate` after the merge should clear them. I didn't touch them.
  - Until they're cleared, a push from this workspace will hit them.

## Needs your input

1. **Closing VF-025 (the spring-core JARs exceed jj's 1 MiB snapshot limit).** This loop decided the three 1.4 MiB JARs needn't be in the history: the two published ones are re-acquired by their recorded sha256, and the mutant is rebuilt by its recorded command.
   - Closing the finding needs one of two things:
     - `runtime-mutant/**/spring-core-5.3.19.jar` added to `.gitignore` on main;
     - or a size-limit decision shared with VF-020.
   - Either is a shared file or policy decision for you or the coordinator.
   - Separately, later jobs should delete `prepare/*/lib/` in their cleanup step.
2. **Merge items, recorded under Progress for the main brief's for-review list:**
   - **`build_fixtures.py`** should compile with `-parameters`.
   - **`mutation.json`** moves into `target.json`, with example 306's `drop-prefix` expressed as a W1 mutant.
   - **`PreparedTarget`** gains the optional `blocker` and `workdir` fields.
   - **The claim key** for an adapter entry point needs to be settled with the workflow stream.

## Also worth noting

- The integration report hasn't been rewritten since 17:28. It doesn't yet reflect this stream's last two commits.
- The brief itself needed no correction this cycle.

Ended 2026-11-14 18:25:19 after 1 cycle(s): the session decided to stop; the brief says done.
