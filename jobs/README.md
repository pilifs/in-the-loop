# The jobs pipeline

Work that should not run in an agent's session is described as a **job**, committed, and run later by a runner
under limits: a proof, a build, a test run, a dependency resolution. This folder holds the pipeline's shared code.
The records it reads and writes are where they have always been, under [`verification/`](../verification/README.md):
`verification/jobs` (specifications) and `verification/results` (receipts), found by job id through
[`verification/layout.py`](../verification/layout.py). Nothing recorded there is moved.

This page is being written with the pipeline: each section describes what is in the repository at the commit it
is read in. What is intended and not built is in [`ARCHITECTURE.md`](../ARCHITECTURE.md#what-is-not-built-yet).

| File | What it is |
|---|---|
| [`pipeline.py`](pipeline.py) | the one implementation of admission, claiming, execution, collection and reporting, and every command. It was `verification/pipeline.py` until 2026-11-27, and that path is still an entry point that runs this file, so every command a job, a hook or a note names keeps working |
| [`workloads/`](workloads) | what a kind of work means: [`generic.py`](workloads/generic.py) (nothing: commands, exit codes, outputs) and [`verification.py`](workloads/verification.py) (the checkers, the build of `jvmcontract`, the verdict lines, numbered examples) |
| [`schema/job.schema.json`](schema/job.schema.json), [`schema/result.schema.json`](schema/result.schema.json) | the second job format, `itl-job/v2` (a purpose, a workload, labels, prerequisites, a permitted environment, required outputs, what a step promises), and its result, `itl-job-result/v2` |
| [`lifecycle.py`](lifecycle.py) | what became of a job, each question apart: what its processes did (`execution`), what it delivered (`fulfillment`), what it cost by scope (`timing`). One function each, for the runner that writes a result and for a reader of a result written before the blocks were kept; [`test_lifecycle.py`](test_lifecycle.py) |
| [`evidence.py`](evidence.py) | what a step did besides exiting: which tests executed, read from JUnit XML reports or the log's summary lines; [`test_evidence.py`](test_evidence.py) |
| [`test_formats.py`](test_formats.py) | the second format end to end, through `jobs/pipeline.py`, in throwaway repositories: a non-Java job on a PATH with no checker, real tests counted, a missing required output, a refuted claim, a step with no network |
| [`sandbox.py`](sandbox.py) | runs a command where the network is demonstrably off, and records how that was shown |
| [`records.py`](records.py) | reads the committed records by id, from a git revision or from a working copy; computes the result indexes from the receipts, for `collect` to write and for the audit to compare |
| [`audit.py`](audit.py) | the reconciliation: a read-only join of specifications, receipts, indexes and the runner's state |
| [`test_audit.py`](test_audit.py) | tests both, on a made-up corpus with one fault at a time and on the corpus of the pinned revision |
| [`attempts.py`](attempts.py) | the record and the folders every execution of a job gets before its first byte; [`test_attempts.py`](test_attempts.py) tests it, and [`verification/test_capture.py`](../verification/test_capture.py) what the runner, `prune` and `recover` do with it |
| [`fixtures/`](fixtures) | the census and the manifest of the corpus at `b52a084f5d11`, the revision the migration started from |

## What the pipeline owns, and what a workload owns

| The pipeline, for every job | A workload, for its kind of work |
|---|---|
| The job's and each attempt's identity, who submitted it and from which run, its case or batch, the source revision, its prerequisites, its resource estimate, its permitted environment, its declared steps and outputs | What a Gradle task, a Maven goal, a test selector or a checker's command means |
| Claiming a job once, scheduling it when it is ready, saying why when it is blocked, deferred or cannot run here, enforcing its budget, capturing its outputs, retrying and superseding | Looking for the tools the work needs and building the ones it builds (`missing`, `prepare`), and what a step's environment needs (`step_env`) |
| The lifecycle, the measured use, the outputs' digests and the links to the evidence | Reading what a log says (`scan`), and what that means for the question asked (`verdicts`, `conclusion`): "the named tests executed", "the claim is refuted" |

A job of the first format (`verification-job/v1`) is the verification workload's, as every job was until
2026-11-27, and runs exactly as it did. A job of the second format names its workload, `generic` when it names
none. A job's **purpose** (`resolve`, `build`, `test`, `verify`, `maintenance`) is kept apart from its labels
(`project`, `tool`, `capability`): a purpose says how to read the result, and a label only groups.

A result's record of its machine lists the pipeline's own tools and those of the job's workload, so a build job's
result does not list checkers and a machine with none installed is not asked for them.

**A job that ran and a claim that held are two things.** The verification workload's `conclusion` reads the
checkers' verdict lines apart from the job's status: `established`, `refuted`, `open`, `mixed`, or `none` when no
checker's line was found, which is never read as established. A job whose every step exits as its specification
expects has passed, and may have refuted its claim.

## A job of the second format

A job that names a **purpose** is written in the second format. Everything else about submitting, committing,
running, collecting and resubmitting it is as for any job ([`verification/README.md`](../verification/README.md)).

```sh
python3 jobs/pipeline.py submit --purpose test --title "Run the parser's tests" \
    --description "What it checks, why, and what a reader of the result should know." \
    --label project:parser --case P07 --requires cargo \
    --phase test --tests 40 --run "cargo test -p parser" \
    --output target/parser-report.json --optional-output target/coverage.txt \
    --cpus 2 --memory 2G --duration 5m
```

| It says | With | What the pipeline does with it |
|---|---|---|
| what kind of work it is | `--purpose resolve\|build\|test\|verify\|maintenance` | Says how to read the result. Kept apart from `--label KEY:VALUE` (`project`, `tool`, `capability`, any other), which only group. `--capability X` is the label `capability:X` |
| which adapter knows what its steps mean | `--workload NAME` | `generic` when it names none: commands, exit codes, outputs, and requirements looked for on PATH. A job whose adapter this checkout does not have is not started, and `status` says why |
| the case it belongs to, and what must come first | `--case`, `--needs JOB` | Recorded. A job that names a prerequisite is not started yet: scheduling by `needs` is the next step of this work, and until then `status` says so |
| what its steps may reach | `--network host\|none\|fetch` | `host` is the machine's network, as every job of the first format has it. `none` is enforced: the step runs in a network namespace with a loopback interface alone ([`sandbox.py`](sandbox.py)), and its record keeps what a probe saw there. A machine that cannot enforce it does not start the job. `fetch` is for a step of a `resolve` job alone |
| that a step runs tests | `--tests MIN`, `--test-reports GLOB`, `--expect-failing TEST` | The step is held to evidence: at least MIN tests executed, read from the reports or else from the log's summary lines (cargo, unittest, pytest, Maven, Gradle). A step that exited as expected and shows none has not kept its promise (VF-070). With `--expect-failing` and `--expect-exit`, a regression test that fails by assertion on the revision before its fix is a fulfilled job, and a build that broke before any test ran is not. A step with no promise (a compile) is asked for nothing |
| which outputs it must leave | `--output PATH` (required), `--optional-output PATH` | A required output that is not there leaves the job unfulfilled, whatever its steps exited with |
| what its steps' time counts as | `--phase resolve\|fetch\|prepare\|build\|test\|proof\|other` | `timing.byPhase` in the result |

`--phase`, `--tests`, `--test-reports` and `--expect-failing` describe the steps given on the same command line.
A job with steps that differ is written as a file ([`schema/job.schema.json`](schema/job.schema.json)) and
submitted with `--from-file`.

A job records the run its submitter works in (`submitted.run`, as `single-NAME`), read from the systemd scope the
loop runs its agent in, so that nobody has to infer it later from times (VF-077). It is not the source revision,
and not who collects. A job of the first format records it too. `submitted.phase` is there when the submitter
says it (`--run-phase`): a loop's agent cannot read its run's phase from where it runs.

### What its result says

One status word used to answer several questions. A result now keeps them apart, in a job of either format
([`schema/result.schema.json`](schema/result.schema.json)):

| Block | The question | Its values |
|---|---|---|
| `execution` | What did the processes do? | The steps planned, run, as expected and skipped; `stopped` names the first step that did not go as expected and why: `exit`, `signal`, `timeout`, `stalled`, `ceiling`, `memory-limit`, `machine-memory`, `cancelled`, `preparation`, `unmet-promise`, or `not-run` |
| `fulfillment` | Did the job deliver what it declared? | `fulfilled`; `unfulfilled`, with every reason (`step`, `promise`, `output`, `skipped`, `preparation`, `not-run`); `undetermined` for a job stopped before it ended, which runs again |
| `declared` | What became of each declared output? | `added`, `modified`, `deleted`, `changed`, `unchanged`, `missing` (every step ran to its exit and it is not there), `never-reached` (the job was stopped, or skipped a step, before it); with `required`, the consumer the job named and the attempt that produced it. The files' digests are under `outputs` |
| a step's `evidence`, `network`, `phase` | What did the step do besides exiting, and with what network? | The tests executed, failed and skipped, the names of the ones that failed, and the source read (`junit-xml`, `log: cargo test`, ..., or `none`: nothing shows any ran); the probe of a step that had no network |
| `conclusion` | What does it mean for the question asked? | The workload's: `established`, `refuted`, `open`, `mixed`, `none` for the verification workload. Absent where the workload concludes nothing |
| `timing` | What did it cost, and of what is each number a measure? | `queueWait`, `elapsed`, `preparation`, `requestedSteps`, each with seconds and a state: `measured` (a measured zero is one), `derived`, `partial`, `not-run`, `unknown` |

`status` stays the one word the indexes and the reports use. For a job of the second format it is `passed` only
when the job is fulfilled: a job whose every process exited as expected and which did not deliver what it
declared is `failed`, and `execution.status` goes on saying `passed`. For a job of the first format nothing
changes: its outputs were never required and its steps promise nothing.

A result written before the blocks were kept (every one collected until 2026-11-27) has none of them. `lifecycle.facets(job, result, derived=True)` computes
them from what it does hold and marks them `derived`: the receipt of `20261127-054106` then says 41 seconds
elapsed, measured, 41 seconds of preparation, derived, and requested steps that were `not-run`, where its index
entry said 0 seconds and its receipt 41.

## Attempts

Every execution of a job is an attempt: a record and folders of its own under `.state/attempts/ID/NNN-TOKEN/`,
made before the attempt writes anything, whether or not the private archive answers. A rerun clears nothing, a
work directory is removed only by a rule its record then names, and what a capture missed is sealed later, where
it is. [`verification/README.md`](../verification/README.md#attempts-what-a-rerun-keeps-and-what-may-be-removed)
has the rules of `prune` and `recover`.

## Reconciling the records

```bash
python3 jobs/audit.py                        # the working copy, and what the runner holds here
python3 jobs/audit.py --rev REV              # a revision, from git objects alone
python3 jobs/audit.py --rev REV --json       # every finding, for a program
python3 jobs/audit.py --rev REV --census     # only the counts
python3 jobs/audit.py --rev REV --expect jobs/fixtures/census-b52a084f5d11.json   # exit 1 if the counts moved
python3 jobs/audit.py manifest FILE --rev REV    # one row a job: paths, git blob ids, the result folder's tree id
python3 jobs/audit.py verify FILE [--rev REV]    # the manifest against git, at its own revision or a later one
```

The audit changes nothing. It joins by job id, never by a path made from another path: 2,897 files of the corpus
are called `result.json` and 1,906 of them are receipts, and three jobs of 2026-11-22 have a flat specification
and a result under its day. It reports at three levels:

| Level | What it is | Examples | Exit |
|---|---|---|---|
| **discrepancy** | two records of one job that cannot both be right | one id with two specifications that differ; a receipt with no job; a job edited after it ran; an index row that is not what its receipt gives, is missing, or has no receipt; a specification, receipt or index that is not JSON, named with its path and revision; a claim for a job that is not here | 1 |
| **gap** | something a record names that the revision does not hold, and that nothing here can restore | a kept output the commit left out, with the reason when it can be told (its path is ignored, or it is over the 1 MiB a commit takes) and the sealed original when there is one; receipts that name no attempt, no submitting session or no originating run; a staged result set aside unsealed | 0 |
| **note** | a fact of the layout | a flat job with its result under a day; one id with two identical specifications | 0 |

An unknown is kept unknown. A receipt that names no attempt is counted as one that names none, not given
attempt 1, and a revision is audited without the runner's state, which the report says in `snapshot.views`.

**The indexes are derived.** `results/index.json` and each day's `index.json` are computed from the receipts by
`records.index_documents`. `collect` writes them with it and the audit compares the committed files with it, so a
stale, missing or extra row is told from the receipts alone. At the pinned revision the function gives all seven
index files back to the byte.

**A row's time has a scope.** An index row's `wallSeconds` is the requested steps' time. A job that failed while
it was being prepared has 0 there and its elapsed time in the receipt's own `wallSeconds`: job
`20261127-054106-trace-individually-approved-ordinary-ups` took 41 s, all of it building the checker.

### The baseline

The corpus at `b52a084f5d11` (2026-11-27), frozen in [`fixtures/census-b52a084f5d11.json`](fixtures/census-b52a084f5d11.json)
and [`fixtures/manifest-b52a084f5d11.jsonl.gz`](fixtures/manifest-b52a084f5d11.jsonl.gz) (1,906 rows, 32,071
files by their git ids):

| Measure | Value |
|---|---|
| Job ids with a specification, a receipt and an index row | 1,906 of 1,906, no duplicate and none unmatched |
| Outcomes | 1,469 passed, 420 failed, 17 error |
| 2026-11-27 | 172 rows: 105 passed, 62 failed, 5 error |
| Flat specification, result under its day | 3, all of 2026-11-22 |
| Discrepancies | 0 |
| Kept outputs a receipt names that the commit does not hold | 947, of 19 jobs: 945 under an ignored path (655 `*.class` files, 288 under a `target/` folder, 2 in a `__pycache__/`), 2 over the commit limit. None was sealed as an original |
| Receipts that name no attempt | 987 (they predate the capture of originals) |
| Receipts that name no submitting session | 213 |
| Receipts that name an originating run | 0: no job recorded one |

`test_audit.py` holds the pipeline to it: the census of the pinned revision is recomputed and compared, and every
row of the manifest must be at the checked-out commit with the same git ids, so a change that moves a pending
specification or rewrites a receipt fails there.
