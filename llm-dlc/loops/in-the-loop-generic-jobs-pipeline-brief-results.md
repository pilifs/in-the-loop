# One jobs pipeline: results

The record of the run on [`in-the-loop-generic-jobs-pipeline-brief.md`](in-the-loop-generic-jobs-pipeline-brief.md)
(queue entry `generic-jobs-pipeline`, 2026-11-27; Claude Fable 5.2, session `43b290ac`, in the workspace
`foundation-domain-streams`). It follows the brief's five release gates. Each row says what is in the repository,
with the commit, and what is still open. The operator's page is [`jobs/README.md`](../../jobs/README.md).

## Where the work stands

| Gate | State | What is in the repository |
|---|---|---|
| 1. Protect and measure: the census | done | `jobs/audit.py`, `jobs/records.py`, the frozen census and manifest of `b52a084f5d11` |
| 1. Protect and measure: retention on retry and prune | done | `jobs/attempts.py`; `prune`, `recover` and a collect that can be run again, in `verification/pipeline.py`; the brief queue's cleanup is that `prune` |
| 2. Switch one queue | in progress | Done: the pipeline is `jobs/pipeline.py`, with `verification/pipeline.py` as its entry point of before; the verification workload and a generic one (`jobs/workloads/`); the second job format's schema; a network-off sandbox. The second format is written by `submit --purpose`, run and collected, and a result of either format keeps execution, fulfillment, each declared output's state, a step's test evidence and network, the workload's conclusion and scoped timing apart (`jobs/lifecycle.py`, `jobs/evidence.py`, `jobs/schema/result.schema.json`). Open: see *What is left*, below |
| 3. Qualify delayed setup (S48) | open | |
| 4. Tune from measurements | open | |
| 5. Adopt and verify | open | |

## Decisions taken in the run, with their reasons

1. **Records stay where they are.** Specifications and receipts stay under `verification/jobs` and
   `verification/results`, and `verification/layout.py` stays the one resolver of their paths. Seven tools outside
   the pipeline load that module by its path (the trace sync, the promotion, the machine's inventory, example
   acceptance, the cost inventory, the queue keeper, three benchmark readers). A second root for new records would
   have to be taught to each, and the brief asks that nothing recorded moves. What becomes neutral is the code and
   the entry point (`jobs/`), not the address of a record.
2. **The audit joins by id and reads a revision from git objects alone.** So the audit of a pinned revision says
   the same whatever is checked out, and its fixtures can be held by a test.
3. **The indexes have one implementation.** `collect` writes them with the function the audit recomputes them
   with (`records.index_documents`).

4. **An attempt gets folders of its own, and nothing is reused.** The brief allows a retry "its own directory" or
   a move of the previous bytes to a recovery location. Folders of their own need no move and no second rule: the
   attempt's folder *is* the identifiable place, `recover` seals whatever is unsealed there, and `prune` releases
   it. The record is written before the first output, whether or not the archive answers.
5. **The attempt's number is the archive's when it can be asked.** So `originals.attempt` in a receipt, the
   archive's coordinates and the folder agree. The id carries a token besides, because two checkouts of one
   machine number apart while the archive cannot be asked.
6. **One rule releases a work directory, and one command applies it.** The brief queue's cleanup had a rule of
   its own (every original of the *job* verified), with the fault the brief names. It now calls `prune`.
7. **A stopped collect is finished, not repeated.** The collected receipt records the digest of the staged
   result it came from. A collect that finds it for the staged result it holds writes nothing and only releases.

8. **The second job format is refused by a runner of before the move, by construction.** A job of `itl-job/v2`
   has no top-level `capabilities` (they are `labels.capability`), which the old runner's own check requires, and
   its `schema` is not the one the old schema allows. A runner still at work from the old code therefore says
   "invalid, not run" and leaves the job pending, instead of running a job whose prerequisites or network policy
   it does not know. A test is to run the pinned old command against such a job.
9. **A job's workload is chosen by its format.** Every job of the first format is the verification workload's and
   runs exactly as before. A job of the second names its workload, `generic` when it names none.
10. **Network policy is explicit and enforced where it is declared.** A step declared `network: none` runs in a
    network namespace with a loopback interface alone (bubblewrap), and its result keeps the probe that showed
    it. `unshare -rn` is refused on this machine (AppArmor restricts unprivileged user namespaces) and bubblewrap
    is not; a systemd user scope's `IPAddressDeny` does nothing here. A job of the first format gets the host's
    network, as it always did.
11. **The originating run is read from the loop's scope.** A loop's agent is given nothing of its run by design,
    but everything it starts is in the systemd scope `feature-loop-single-NAME`. `submit` is to read the run's
    name from there, so a job carries its run without a variable an agent could set or lose.

## What is left, in the order planned

For whoever continues (this run's later cycles): each item is one commit, with its test.

1. *Done (see Gate 2, below).* The second format in `submit`, `validate` and the runner, and the result's blocks.
2. **Scheduling states**: `needs` (waiting, blocked), unschedulable (no adapter, a missing tool, a network that
   cannot be enforced), deferred; a dependent starts as soon as its prerequisite finishes.
3. **The lifecycle view** (`itl-job-lifecycle/v1`): one function, from which `status`, `status --json` (the old
   shape, as a projection), `wait --json`, `collect --json` and the batch views are rendered; a corrupt
   specification as a diagnostic with path and revision; an unreadable queue as unknown, never idle. Then the
   keepers (`queue_keeping.py`, `run_common.py`, `single_run.py`, the `/run-verification` skill) on it, with no
   regular expression over prose, and on `jobs/pipeline.py`.
4. **Manifest fan-out** (`jobs/batch.py`): `submit --manifest`, deterministic ids from batch, row and work
   identity, the published map under `verification/batches/`, convergence of a concurrent or interrupted
   submission, `resubmit` following the map, `wait --batch`, the 49-row fixture.
5. **Old and new together**: the pinned old command and the new one from two workspaces on one lock; the old
   runner refusing a second-format job; a rollback with a job in flight.
6. **Delayed setup** (gate 3): `jobs/readiness.py` (the operation's description and key, receipts, bundles
   published atomically and verified), `jobs/workloads/resolution.py` (online resolution in an isolated home, an
   offline proof in the sandbox, bounded rounds), `needs: readiness`, the nested Gradle and Maven fixture, then
   S48 as one job that runs the new scheduler in a throwaway repository inside it (the default checkout's runner
   is the old code until this line lands).
7. **Fetch admission and its measurements** (gate 4): a ceiling of ten fetch slots, taken while a fetch step runs.
8. **Adoption** (gate 5): `ARCHITECTURE.md`, `CLAUDE.md`, the skills, the script inventory under `verification/`,
   the findings named by the brief.

## Gate 2: the second format, and a result that keeps its questions apart

**What is built.** `submit --purpose` writes a job of `itl-job/v2`; the runner runs it beside jobs of the first
format in one queue; `collect`, `report`, `validate` and `resubmit` take it as any other. A result of either
format now has `execution`, `fulfillment`, `declared`, `timing` and, where the workload concludes something,
`conclusion`; a step of a second-format job has `phase`, `network` and, when it promised tests, `evidence`.

**The three jobs the brief's second gate names**, each a test in `jobs/test_formats.py`, in a throwaway
repository through `jobs/pipeline.py`:

| The brief asks for | What the test shows |
|---|---|
| A non-Java job that produces an artifact, on a host with no checker | On a PATH of a shell, git and coreutils alone (no `java`, `jbmc`, `cargo`, `bwrap`), the job is submitted, runs beside a first-format job, passes, and its artifact comes back with its digest, `declared` as `added` by the attempt that made it. Its record of the machine lists `coreutils`, `git`, `systemd` and no checker. It is collected, reported by its label, validated against the second result schema, and resubmitted as a job that supersedes it |
| A real build and test job | A step that runs two real unit tests has `evidence` of 2 executed, read from its log. A step that promised tests and compiled only exited 0 and is `failed`, with `execution.stopped.reason` `unmet-promise` and no line saying "exited 0, expected 0". A compile that promised nothing passes and is asked for nothing. A regression test expected to fail by assertion (exit 1, a JUnit report naming it) is a fulfilled, passed job; the same job where the build broke before any test is not |
| A verification job whose checker refutes its claim | With a stand-in for JBMC's refutation (its last line and its exit code 10, which the job expects): `status` `passed`, `fulfillment` `fulfilled`, `conclusion.verdict` `refuted`, as a job of the second format and of the first |

Beside them: a required output that is missing fails a job whose only step exited 0 (`execution.status` stays
`passed`), an optional one does not, and an output behind a failed step is `never-reached`; a step with no
network sees `lo` alone and its record keeps the probe; where bubblewrap is absent the job is not started and
`status` gives the reason; a job naming an adapter this checkout lacks is not started either; `--tests` on a job
with no `--purpose` is refused; a job submitted inside a loop's scope carries `submitted.run`, and a resubmission
by hand does not inherit it.

**The timing fixture of the brief** (`jobs/test_lifecycle.py`): the committed receipt of
`20261127-054106-trace-individually-approved-ordinary-ups` gives `elapsed` 41.0 s `measured`, `preparation`
41.0 s `derived`, `requestedSteps` 0 s `not-run` (0 of its planned steps), and `execution.stopped` at step 0,
`preparation`.

**Decisions.**

12. **`status` means fulfilled, for the second format only.** A second-format job whose processes all exited as
    expected and which did not deliver what it declared is `failed`; `execution.status` keeps `passed`. A
    first-format job's outputs were never required and its steps promise nothing, so no first-format result
    changes its status. This is the brief's "a missing required output precludes fulfillment even if the process
    exited zero" without rereading 1,906 receipts by a rule they were not written under.
13. **The blocks are in results of both formats, and derived for the ones before.** One function computes each
    (`jobs/lifecycle.py`), for the runner and for a reader of an old receipt, which marks them `derived`. The
    first result schema names the blocks and stays open, so a reader of before ignores them; the second schema
    describes them, and a test holds the two schemas to the same definition of everything they share.
14. **A machine that cannot do what a job declares does not start it.** A missing adapter and a network that
    cannot be taken away are reasons in the job's plan, beside the ones for memory and CPUs. Nothing of the job
    runs, no attempt is consumed, and `status` gives the reason. (The runner's word for all of them is still
    `deferred`; telling `unschedulable` from `deferred` is the lifecycle view's, below.)
15. **The run's phase is said, not inferred.** `submitted.run` is read from the scope. The phase is not there to
    read (one loop name serves every phase of a run), so `submitted.phase` is set by `--run-phase` when the
    submitter knows it, and is otherwise absent. Unknown is reported as unknown.
16. **Subprocess tests that go through the shared helper are listed as the estimator lists them.** The 11 tests
    of `jobs/test_formats.py` spawn the pipeline through `test_pipeline.Repo`, which the cost estimator's scan of
    a file's own calls does not see, so the inventory has them as `unit`, as it has `verification/test_pipeline.py`'s.
    They take about 1.3 s each. Changing the estimator is outside this brief.

## Gate 1: the census

Measured at `b52a084f5d11` and again at this run's first commit (`c09de656`), with the same result:

- 1,906 job ids, each with a specification, a receipt and one index row; no duplicate, none unmatched; every index
  row's path is its receipt's.
- 1,469 passed, 420 failed, 17 error. On 2026-11-27: 172 rows, 105 passed, 62 failed, 5 error.
- Three jobs of 2026-11-22 have a flat specification and a result under its day.
- The seven index files are, to the byte, what the receipts give.
- No discrepancy.

**Found by the audit, not known before:** 947 kept outputs that receipts name are not in the commit. They belong to
19 jobs of 2026-11-06 to 2026-11-20. 945 have a path the repository's ignore rules leave out (655 compiled classes, 288 under a `target/` folder, 2 in
a `__pycache__/`), and 2 are over the 1 MiB a commit takes. None was sealed as an original: the
jobs predate the capture of originals. 944 of the files, 10 MB, are still on disk in the default checkout, as
ignored files of that one working copy; three are in no checkout of this machine. They are recorded as VF-080.

## Gate 1: retention

**The two risks, as they stood.** `execute` asked the archive to keep an unsealed earlier attempt, and cleared the
job's run directory whatever the answer. `prune_workdirs` asked whether the job's latest *captured* work directory
was verified, which is an earlier attempt's when a later one's capture failed. A third place had the second fault:
the brief queue's cleanup between two briefs removed a work directory when every original *of the job* was
verified.

**Whether history lost bytes this way.** The default checkout's `capture.log` holds one failure since capture
began: a `PermissionError` on 2026-11-22, sealing the work directory of job
`20261122-162529-spring-security-reachable-roles-and-publ`, a job the pipeline could not run (`error`). Its
receipt names a kept work directory that is no longer on disk and no original of it. The log has no line of the
rescue-before-reuse failing. What cannot be shown either way is whether a prune ever removed a later attempt's
unsealed folder: until now nothing recorded which attempt a folder on disk belonged to.

**What is built.**

- Every execution is an attempt with a record and folders of its own (`.state/attempts/ID/NNN-TOKEN/`), on disk
  before its first output. A rerun clears nothing. The result names its attempt and the ones before it.
- `recover` seals what nothing sealed, where it is: an attempt whose runner died, one whose capture failed, a
  staged result set aside, a run directory of the old layout. A runner does it when it starts.
  `recover --kept-outputs` seals VF-080's files from a working copy that still has them.
- `prune` removes a work directory only when the job's result is collected, the collected receipt is of that
  attempt or a later one, the original sealed from that very attempt is verified in the store, and the folder is
  still what was sealed. `prune --why` gives the reason for each that stays.
- A collect stopped after it wrote a result, or after that result was committed, is finished by the next one
  without writing the receipt again.
- The audit lists an interrupted or unsealed attempt, a result set aside and an unsealed old run directory as
  gaps until they are sealed.

**The simulations the brief asked for** (`verification/test_capture.py`, `AttemptsTest`, each on a real spool and
a store on disk):

| Simulation | What the test shows |
|---|---|
| A runner killed mid-step, then a rerun with a full spool | The killed attempt's log and work files are byte for byte on disk after the rerun, which ran in a folder of its own as attempt 2. The audit lists both attempts as only on this machine |
| Successful recovery | With room in the spool, `recover` seals both. The store gives back the killed attempt's log and its work file with the same bytes, under attempt 1 and the attempt's id |
| An older verified occurrence | Attempt 1 is stopped, sealed and verified. Attempt 2 fails with a full spool and is collected. The prune removes attempt 1's folder and keeps attempt 2's, "its originals are not sealed". After `recover` and an upload it removes that one too, and the store gives its file back |
| A work directory changed after it was sealed | Kept: "it changed since" |
| A collect killed after it wrote and sealed, then a commit | The next collect leaves the receipt byte for byte, releases the staged result and offers nothing to commit but the indexes the stopped one never wrote |
