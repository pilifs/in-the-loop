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
| 3. Qualify delayed setup (S48) | in progress | Done: readiness operations, resolution in rounds, bundles and receipts (`jobs/readiness.py`), the scheduler's wait and wake, the watcher's admission, the fetch authorisation and slots, and the synthetic nested fixture with its controls. Open: S48 itself, on the real cache, as a job |
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
2. *Done (see Gate 2: states and the view, below).* Scheduling by prerequisites, and the states with their reasons.
3. *Done (same section).* The lifecycle view, `status` rendered from it, the typed `wait` and `collect`, and the
   keepers on it and on `jobs/pipeline.py`. Left of it: the batch views, with fan-out (next).
4. *Done (see Gate 2: fan-out, below).* Manifest fan-out, the map, the batch's wait and view, the 49-row fixture.
5. *Done (see Gate 2: the pipeline of before beside this one, below).*
6. **Delayed setup** (gate 3). *The mechanism and the synthetic fixture are done (see Gate 3, below).* Left:
   **S48 for real**: an operation for `verification/merged-pr-links/s01-s50/maven-war/replay.py` on both pins
   (base: the S cache, `without` the ActiveMQ BOM 6.1.8 and the Maven 3.9.13 distribution; pinned: that
   distribution with its SHA-512; repositories: Maven Central; outputs equal to `parent.json` and `fix.json`),
   its three controls, and an unrelated job, run as **one first-format job** whose step runs this scheduler in a
   throwaway repository (the default checkout's runner is the old code until this line lands). The passed job
   of 2026-11-27 took 295 s, 5.5 GB and 3 CPUs for the two sides; a resolution runs the task once a round.
7. **Fetch admission and its measurements** (gate 4). *Admission is built* (`fetch_allow`, `fetch_slots`, a
   receipt's fetched bytes and seconds, `timing.byPhase`). Left: measurements from a real batch, which none has
   run on yet.
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

## Gate 2: states and the view

**What is built.** One decision says whether a committed job may start and why not (`jobs/scheduling.py`), and the
runner and the view both ask it. One view (`jobs/pipeline.py view`, `itl-job-lifecycle/v1`) has every job with one
state and its reason; `status` is that view as lines, `status --json` its lines by heading as before, and the
keepers read the view as data.

| The brief asks | What a test shows (`jobs/test_formats.py` `Prerequisites`, `jobs/test_view.py`, `jobs/test_scheduling.py`) |
|---|---|
| Prerequisite ids; blocked, unschedulable and deferred reasons | A dependent waits for its prerequisite and starts after it finished. One whose prerequisite failed is blocked, with no result and no attempt folder, and runs once the prerequisite is resubmitted at a commit where it passes, its own file unchanged. One whose prerequisite cannot run here is left waiting by the runner, which ends, and is `blocked` in the view with the first cause. With one worker, the second job is `deferred`, "all workers busy", as a job's own step read it from the view during the run |
| Uncommitted versus committed work; a corrupt spec with path and revision | A job file not committed is `uncommitted`. A committed file that is not JSON is `invalid`, with its path and the commit it was read at |
| An unknown queue read cannot mean idle | With a repository git cannot read, `view` exits 4 with `idle` null and no jobs, `status` begins with NOT READ, and the keepers return unknown, not zero (`llm-dlc/tools/test_queue_keeping.py`, `test_run_common.py`) |
| Aggregates with a denominator and a drill-down | `totals` has its unit, what it is out of and the states adding up to it; `view --state` lists the rows and says how many of how many |
| Keepers need no regex over English | `queue_keeping.py` and `run_common.py` read the view, `collect --json` and the runner's flag in the view; the three regular expressions over the pipeline's lines and the `"; cannot run here:"` test are gone. The `/run-verification` skill names `jobs/pipeline.py` and the states |
| A successful process with a failed hook still needs attention | A collect whose hook exits 3 collects and applies the result, reports the hook with its output, and `status` and `view` go on naming it; the watcher's keeper puts it in `attention` |
| Results derived for a receipt of before | A receipt with the blocks removed comes back from `view ID` with them, `derived` |

**Decisions.**

17. **The runner's word for a job it will never start is `unschedulable`.** It was `deferred`, which now means
    what it says: held back for now, by a runner at work. Nothing read the runner's log for that word.
18. **`status --json` keeps its shape.** It is the view projected onto the headings of before. A row of a job that
    is invalid, unschedulable or blocked carries "; cannot run here:", as an unrunnable job's always did, so a
    reader of before does not take it for runnable. New readers use `view`.
19. **The view gives a collected job from the result index, and opens the receipt when the job is asked for.**
    1,906 receipts are otherwise 1,906 files to open on every look of a keeper.
20. **A waiting job whose prerequisite cannot start is blocked, in the view.** The runner leaves it waiting and
    ends (it cannot tell that another machine will not run the prerequisite); the view, which sees every job's
    state, names the first cause. `idle` does not wait for it.
21. **A readiness prerequisite blocks until receipts are read** (gate 3): a job that asks for one is not run
    unprepared in the meantime.

## Gate 2: fan-out

**What is built.** `submit --manifest FILE` checks a whole batch and writes one ordinary job for each row, with
the rows' map in `verification/batches/NAME.json`; `resubmit` moves a row to the job that replaces it;
`wait --batch NAME` blocks until every row is settled; `batch NAME` is the batch row by row; the audit joins
every map with the specifications both ways.

**The 49-row fixture** (`jobs/fixtures/batch-49.json`; `jobs/test_fanout.py` runs it through `jobs/pipeline.py`
in a throwaway repository, about 7 s; `jobs/test_batch.py` tests the map's rules in process):

| The brief asks | What the tests show |
|---|---|
| A 49-row manifest interrupted and submitted twice gives exactly 49 ordinary job ids | After the first submission 29 of the jobs' files and the map are removed, as a submission killed after 20 leaves it. The second writes 29 and leaves 20, the third writes nothing, and the 49 ids are the first's. In process, a submission killed at its 21st write and run twice more ends with the same 49 files to the byte |
| Concurrent submission converges | Four submissions at once end with the bytes one submission writes |
| One blocked case | R14 needs R13, which fails: R14 is `blocked`, with no result and no attempt, and is in the batch's view with the reason |
| One expected failure | R20's test fails by assertion and exits 1, as the row says it will: `passed`, `fulfilled`, with the report's evidence |
| A resubmission | R13 is resubmitted with more memory and passes. The row's history has two jobs with one work identity, the first `failed` and the second `passed`, each with one attempt. R14 then runs, its own file unchanged. 50 job files in all, and submitting the manifest again changes none |
| Independent rows finish and appear in the report | 47 rows pass in the first run beside the failed and the blocked one, and all 48 that ran are in `report`. The batch's wait says `settled` with 48 finished and 1 blocked |
| A typed way to watch the batch, and the queue-wide wait still works | `wait --batch --json` gives the outcome and every row; `wait --json` beside it says `finished` |
| Changed revisions or inputs get distinct work identities | Another input and another source revision each give a new job id that supersedes the old one; a changed title or estimate gives none |
| A retry and a supersession stay distinguishable | A rerun is an attempt of one job; a resubmission is a second job with the same work; changed work is a second job with other work. The map's history has the work identity and the reason of each |

**Decisions.**

22. **A submission of a manifest writes no clock and no session.** The ids begin with the manifest's `created`
    time, which a manifest must have, and a job's `submitted` block is the manifest's. Two workspaces that submit
    the same manifest write the same bytes, so their lines merge without a conflict. Who ran a submission is in
    that session's own record.
23. **The estimate is not work.** A row's work identity leaves out the title, the resources and the priority: a
    manifest whose estimate was corrected gives no new jobs. A row that needs other resources is resubmitted.
24. **The audit's census does not count batches.** It is the corpus as frozen before there were any; the
    batches' join is a block of its own in the report.

## Gate 2: the pipeline of before beside this one

`jobs/test_coexistence.py` takes `verification/pipeline.py`, `layout.py` and `capture.py` as they are at
`b52a084f5d11` out of git, and runs them beside this checkout's code on one throwaway repository.

| The brief asks | What the test shows |
|---|---|
| A still-running legacy runner and a new command share one exclusion | With the old runner at work on a state directory, this code's `run` is refused ("another runner is using"), and its `wait --json` and `view` name the old runner's pid as at work. The other way round, the old `run` is refused and the old `wait` names this runner. Across two workspaces of one repository the lock of VF-051 turns the second away whichever code holds it, both ways |
| The v1 formats and commands are preserved | The old runner runs a first-format job written by this code's `submit`, and the old `collect` collects it. `verification/test_pipeline.py`'s 52 tests go on running every command through the old entry point |
| A second-format job is safe on an old runner | The old runner says "invalid, not run" for it and runs nothing of it; this runner then runs it, and does not run again the job the old collector collected |
| Rollback with a job in flight | This runner is killed (SIGKILL, its whole process group) while a job runs. The old runner takes the queue as it finds it, runs the job again, and the old `collect` collects it and applies its output. The killed attempt's log is byte for byte where it was; this code's `view` shows the job `collected` with one `interrupted` attempt, the audit reports no discrepancy and lists the attempt under what is only on this machine; a later run of this runner starts nothing and removes nothing |

What is not shown by a test: the compatibility path through the *watcher's* own cycle on the real pipeline (its
keeper is tested against a stand-in for the pipeline, and the pipeline against throwaway repositories, not the
two together), and the default checkout's runner, which is the old code until this line lands.

## Gate 3: delayed setup, on the synthetic fixture

**The fixture.** A stand-in for a nested build (`jobs/test_readiness.py`, `BUILD`): its first stage needs a tool
distribution and a BOM, and its second stage, a nested tool, asks for its own module only once the first is
satisfied. It refuses to pass if it can reach the repository or write into the prepared inputs. The repository is
an HTTP server on 127.0.0.1, which a process in the offline sandbox cannot reach.

| The brief asks | What a test shows |
|---|---|
| One logical request; a second stage that discovers a previously unknown prerequisite | One resolution, three rounds: the declared tool is fetched and the BOM found missing; the nested tool's module, which nobody named, is found missing; the third runs through. Four files, each verified, each with its source |
| Only the affected consumer waits; an unrelated runnable job finishes during the wait | With a runner at work (`--watch`): the unrelated job finishes while both consumers are `waiting`, the view lists the request `unanswered` with who asks, and nothing has been fetched by anyone |
| The watcher admits the resolution job through the same scheduler | `resolve` writes one job for the one request, the commit admits it, and a second `resolve` writes none while it is on its way. The watcher's keeper does the same at a look (`test_queue_keeping.py`) |
| Only an authorised fetch phase gets network access | A runner whose `fetch_allow` is empty does not start a job that fetches. A source outside it is not asked. Only a resolution job's steps are given the list |
| Prove the handoff offline, with no inherited mutable cache | The resolver's last round and each consumer run with a probe that saw `lo` alone; the consumer itself fails if it can connect to the repository, or if it can append to a file of the base (bound read-only) |
| Wake the consumer on a matching receipt; account once | Both consumers start after the resolution finished, each ran once (no earlier attempt), and each result names the bundle digest the resolution's conclusion names |
| Share only identical verified requests | A second case with another title and consumer has the same key: one request file, one resolution, each file asked of the repository once. Another toolchain, or another task, is another key |
| Reject stale bundles | A bundle file changed after its receipt: `blocked`, "its bundle is not what the receipt names", and a resolution run again replaces it and keeps the earlier attempt on record |
| Withheld BOM, wrong digest, unavailable repository: each reports the failing stage and withholds readiness | `absent`, `digest-mismatch` and `repository-unavailable`, each at the `fetch` stage, with nothing published. Through the pipeline, the withheld BOM blocks the consumer by that name, it runs nothing and fails nothing, and after the BOM is back `resolve KEY --again` makes it ready and the consumer runs |
| A failing consumer must not poison the shared cache | A failed resolution's staging goes to `failed/`, never to `bundles/`; the published bundle is read-only and bound read-only where it is used |
| Partial discovery is a legitimate outcome; cycles and no-progress are detected | `undiagnosed` when the task fails and names nothing; `no-progress` when it asks again for what it was given; `round-limit` |

**Decisions.**

25. **Resolution is discovery by running the task offline.** The task itself, in the sandbox, is the oracle for
    what is missing and for when it is enough. The resolver adds verified inputs and nothing else. It does not
    resolve a dependency graph of its own, so it cannot disagree with the build tool about what the task needs.
26. **Admission is a commit.** The pipeline writes the resolution job; the watcher commits it. Fetching is then
    a job like any other, in the queue, with a result, on a runner that says where it may fetch from.
27. **The estimate and who asks are not the operation's identity.** A second case reuses the first one's
    receipt; a corrected estimate does not make a new request.
28. **The runner's readiness store is the machine's**, beside the caches it prepares over
    (`~/.cache/in-the-loop/readiness`), so every checkout and workspace shares a resolution. Tests use a store
    of their own.
29. **Fetch slots are held for a job's whole run**, not only while its fetch step runs: simpler, and never more
    than the ceiling. Finer accounting waits for a measurement that shows it matters.

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
