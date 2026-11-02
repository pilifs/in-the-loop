---
name: run-verification
description: Manage the verification pipeline. Run the queued proof and model-checking jobs within the machine's budget, collect and commit their results, triage what failed, and resubmit what ran out of time or memory.
---

You manage the verification pipeline described in `verification/README.md`. Development agents queue jobs and move
on; you run them, bring the results back, and make them easy to read. Read the README's sections on reading results
and on running before you start, if you have not this session.

**What you never do.** You don't change a job's steps or expectations to make it pass, edit a result, or report a
job as verified that did not pass. Only JBMC's `VERIFICATION SUCCESSFUL` is a proof. You don't fix the code a failing
job verifies: that belongs to whoever made the change, and your report is how they hear of it. You don't run a job's
commands by hand to see: the runner is how they run, under limits.

1. **Look first.** `jj st` and `jj log -r 'ancestors(@, 5)'`: another session may have uncommitted files, which a
   commit of yours would sweep in (see step 5). Then `python3 verification/pipeline.py status`. Say what is pending,
   what is running (another runner holds those claims), what finished but was not collected, and what cannot run
   here and why.

2. **Run.** `python3 verification/pipeline.py run`, in the background (Bash with `run_in_background`), since it runs
   until the queue is empty and a job can take an hour. Give it the budget the machine has now: check
   `free -h` and whether `feature-loop.scope` is active (`systemctl --user is-active feature-loop.scope`), which
   takes 4 GB. With the loop running, the defaults fit. Without it, `--memory 7G --workers 3`. Use `--watch` only
   when the user asks for the pipeline to keep going; it does not stop by itself. While it runs, don't start proofs
   of your own, and don't start a second runner: it refuses while the first holds the lock.

3. **Collect.** When the run finishes, `python3 verification/pipeline.py collect`. It moves results into
   `verification/results/`, applies the outputs of jobs that passed to the working copy unless a file changed since
   the job's commit, regenerates the examples table, and prints a commit message. If a hook after collecting fails,
   say so with its output.

4. **Triage.** `python3 verification/pipeline.py report` (Markdown, for you and the user) or `--format json` (to
   go through many). For each result that needs attention, decide which of these it is, from its `attention`,
   `signals` and the steps' `tail`, and the job's `description` and `expected`:
   - **A verdict**: the verifier ran and found something (a refuted property, a violated invariant, an example whose
     verdict differs from its expectation). That is a finding about the change, not about the pipeline. Report it
     with the evidence: the job, the step, the lines, the commit.
   - **Out of time or memory**: no verdict. If the usage suggests a bigger estimate would fit this machine,
     `python3 verification/pipeline.py resubmit ID --memory ... --duration ...` and commit the new job. If it needs
     more than this runner allows (`job_memory_max`), leave it deferred and say it needs a bigger machine.
   - **An error**: the pipeline could not run it (a tool missing, jvmcontract did not build, a step's command wrong).
     Fix what is the pipeline's; tell the submitter what is theirs.
   - **Outputs not applied** (`collected.conflicts`): the files changed since the job's commit, so the result is
     stale. Resubmit at the newer commit (`resubmit ID`; it runs at the commit that commits it).
   - **A pass with attention**: an estimate far off is worth a line in your report and nothing else; JBMC with no
     verdict, or a process killed at the limit, in a pass is worth looking into.

5. **Commit.** Follow `CLAUDE.md`: `python3 llm-dlc/tools/sync.py commit` with the message `collect` printed,
   reworded for a reader who did not see the run, then `sync.py check`. The commit should hold only
   `verification/results/`, the outputs `collect` applied, the regenerated `examples/demo/README.md` and
   `examples/demo/index.json`, and any jobs you resubmitted. If `jj st` shows other files, they are another
   session's: keep them out by moving them into a change of their own below yours, committing, and moving them back
   on top:

   ```bash
   jj split -r @ -m "wip: another session's files" PATH ...   # their files, now the parent of @
   OTHER=$(jj log --no-graph -r @- -T change_id)
   python3 llm-dlc/tools/sync.py commit -m "..." -m "..."
   jj rebase -r "$OTHER" -A "$(jj log --no-graph -r @- -T change_id)"
   jj squash --from "$OTHER" --into @ -u                       # their files uncommitted again, on top
   ```

   The files on disk don't change, so the other session is not disturbed. Push only if the user asks.

6. **Report.** Tell the user, in this order: verdicts that need someone (with the job ids and what was found), jobs
   that need a bigger machine or a rerun, errors, then a count of clean passes and how long the run took. Note any
   capability whose estimates are far off in the calibration table, so submitters can correct them.
