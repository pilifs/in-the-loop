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
| [`scheduling.py`](scheduling.py) | whether a committed job may start, and why not: its prerequisites and its state, one decision for the runner and for every view; [`test_scheduling.py`](test_scheduling.py) |
| [`readiness.py`](readiness.py) | setup a running case asks for: an operation, its resolution in rounds by running the task offline, the bundle and the receipt; [`workloads/resolution.py`](workloads/resolution.py) is the resolution job's adapter. [`test_readiness.py`](test_readiness.py) resolves a made-up nested build against a repository served on this machine, and [`test_delayed_setup.py`](test_delayed_setup.py) takes it through the pipeline with a runner at work |
| [`batch.py`](batch.py) | a batch of jobs from one manifest: one ordinary job a row, ids the manifest alone decides, and the map from rows to jobs; [`test_batch.py`](test_batch.py) tests the map's rules in process, and [`test_fanout.py`](test_fanout.py) runs the 49 rows of [`fixtures/batch-49.json`](fixtures/batch-49.json) end to end |
| [`test_coexistence.py`](test_coexistence.py) | the pipeline of the pinned revision (read from git) and this one on one repository: a runner of before does not run a second-format job and says so, the two share the runner's locks and see each other at work, and a job in flight when the runners are swapped is run again by the other with the first attempt kept |
| [`script_inventory.py`](script_inventory.py) | the scripts under `verification/` with who calls each (committed jobs' command lines, tests, other code, live pages, and the records of past runs, which show use and keep nothing usable) and a class for each, no stronger than the callers that give it; it writes [`verification/scripts.md`](../verification/scripts.md). [`test_script_inventory.py`](test_script_inventory.py) holds the page to the scripts that are there, and the two controls |
| [`test_view.py`](test_view.py) | the lifecycle view, the typed `wait` and `collect`, and a queue that could not be read, in throwaway repositories |
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
| the case it belongs to, and what must come first | `--case`, `--needs JOB` | The job starts once that job, or one that supersedes it, has passed. Until then it waits. If the prerequisite ended without passing, the job is blocked: nothing of it runs, no attempt is consumed, and resubmitting the prerequisite releases it with its own file unchanged |
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

## Setup a running case asks for

A case reaches a task its setup never exercised. It does not rerun setup, guess the first missing coordinate, or
fail once for every missing artifact (VF-076). It says what it needs done, once, and waits:

```sh
python3 jobs/pipeline.py submit --purpose test --case S48 --title "..." --description "..." \
    --needs-readiness operation.json --network none --output out/readback.json --run "tools/read_wars.sh"
```

`operation.json` is a **readiness operation** (`itl-readiness-operation/v1`, [`readiness.py`](readiness.py)): what
"ready" means for this task.

| It binds | With |
|---|---|
| which task this is | `describes`: the project, revisions, module, task or goal, profiles, wrapper, toolchain, platform, configuration. Anything that would make it another operation |
| how far "ready" goes | `level`: `configures`, `resolves`, `builds`, `tests-run` or `readable`. A task graph that configures is not dependencies that resolve, and neither is a packaged result that was read. `tests-run` is shown, not said: the offline run must leave evidence of tests that executed (`task.tests`: `reports`, JUnit XML under `$ITL_READINESS_OUT`, and `min`; with no reports the log's summary lines are read), and a task that ran through with none is withheld as `tests-not-shown` |
| the prepared inputs it starts from | `base.path`, on the runner. `base.without` leaves paths out, and `base.asOf` (`time`, and the folders `under` which it holds) leaves out every file written after a time, by the files' own times: an earlier state of a cache in one line. The receipt then says `reconstructed` (not the base as it stands), how many paths `asOf` left out, and repeats `base.why`, where the operation says whether that state is one the base was ever in |
| what else on the runner the task reads | `reads`: whole paths beside the base, bound read-only (a JDK under `~/.sdkman`). Nothing else under the runner's home is there (below) |
| how the view is laid | `view.env`, the variable the task finds it by; `view.walk`, the folders a tool walks |
| the task itself | `task.steps`: the commands the consumer will run, run here the same way; `task.env` for variables they need. `task.independent` says the steps do not depend on each other (one a pin): then each runs though another failed, and one round learns what all of them lack |
| what it must leave | `outputs`: files under `$ITL_READINESS_OUT`, optionally equal to a committed JSON file or a digest |
| where a discovered input may come from | `repositories` (Maven layout) and `pinned` inputs with their digests (a tool distribution) |
| how the consumer finds the result | `view.env`: the variable that names the prepared view |

Its **key** is the digest of all of that but the title, who asks and the estimate. Two cases that need the same
operation share one request (`verification/readiness/KEY.json`, committed with the first job that asks) and one
resolution; another toolchain or profile is another key.

**What happens.** The job that asks is `waiting`, alone: every other job goes on. The view lists the request
under `readiness`, `unanswered` while no receipt is ready or withheld and no job is on its way. The watcher
admits a **resolution job** for it by committing what `python3 jobs/pipeline.py resolve` writes
([`queue_keeping.py`](../llm-dlc/tools/queue_keeping.py) does it at each look), and that job runs through the same
scheduler as any other, on a runner whose settings name the sources it may fetch from (`fetch_allow`; with none,
a job that fetches is unschedulable), within the runner's fetch slots. Only a resolution job's steps are told
those sources.

**What a step on a view is given.** The view by the variable the operation names (and `ITL_READINESS_VIEW`),
and three things for the build tools. `ITL_READINESS_M2` is the view's Maven-layout folder: the base's modules
and the fetched ones, one tree, which a Maven build takes as its local repository or a mirror.
`ITL_READINESS_FETCHED_M2` is the fetched modules alone, in the same layout, each whole. And
`ITL_READINESS_GRADLE_INIT` is an init script written into the view: a Gradle build run as `gradle --offline -I
"$ITL_READINESS_GRADLE_INIT" ...` gets a file repository over the fetched modules, ahead of its own
repositories, for its projects, its build scripts' class paths and its plugins. Over the fetched ones alone,
because a Maven local repository often holds a module's POM with no JAR, and Gradle, having read a POM in a
repository, looks for the JAR nowhere else. It needs one because Gradle offline reads a remote
repository's modules from its own cache and nowhere else, and nothing but Gradle can write that cache with its
records; a file repository is read whatever `--offline` says. A module whose POM says it was published with
Gradle's module metadata is fetched with its `.module` file, which Gradle then requires. A build that keeps its
repositories in its settings gets the repository there; plugins of the settings script itself are resolved
before the script runs and are not served. The gate for it is
[`verification/merged-pr-links/s01-s50/gradle-module/gate.py`](../verification/merged-pr-links/s01-s50/gradle-module/gate.py),
on a compile of Spring Boot's core module with a library taken out of every cache.

The resolution is **rounds**: lay the base and what is staged so far into a view; run the task with no network
(a network namespace with loopback alone, the base bound read-only) and read its log for what it could not find;
fetch exactly that, verified (a repository's own checksum for a coordinate, the operation's digest for a pinned
input), into staging; go again. A second stage that asks for a prerequisite nobody knew of is one more round.
A module is fetched as its POM, its Gradle module metadata when the POM names it, and its main JAR, with the
parent POMs its POM names, as far up as a repository has them (no tool reads a POM without them); a file a tool
names beside those (a classifier's JAR: `Could not find a-1.0-linux.jar (g:a:1.0)`) is fetched by its name.

**The task runs on prepared inputs alone** ([`sandbox.py`](sandbox.py), `alone`), in a resolution's rounds and
in every step of a job that needs a readiness (such a job's steps all have no network; `submit` sets it, and a
job that says otherwise is not valid). Its home directory is an empty folder of that run's own and so is `/tmp`;
it can write in its work, and read the view, the base, the bundle and what the operation `reads`. So no
`~/.m2`, no `~/.gradle`, no settings of the user's: a build that passes read its inputs from the base and the
bundle, or it did not pass. The variables that point a build tool at a cache or a home of its own
(`GRADLE_USER_HOME`, `MAVEN_OPTS` and the like, `sandbox.CACHE_VARIABLES`) are not handed down, and the task sets
its own. A resolution's task also gets `ITL_READINESS_SCRATCH`, a folder that lasts from round to round, for a
build's compiled scripts. The rest of the machine (`/usr`, `/etc`) is as it is.

**A file fetched once is not asked for again.** What a resolution fetched and verified is kept in the store's
pool by the address it came from. Another resolution that needs it (another case with the same dependencies)
copies it from there, after checking its bytes against what was recorded, and its receipt counts it under
`fetch.reused`. A source the runner does not authorise is not served from the pool either.
It ends `ready` when the task ran through offline and left its outputs, and then the staged files are published
as a read-only **bundle** by one rename, with a **receipt**: the operation, every round with what it lacked and
what was fetched from where, the probe of the offline run, the outputs' digests, the bundle's digest. Otherwise
readiness is withheld, with the stage and a named outcome, and nothing is published:

| Outcome | Stage | What it means |
|---|---|---|
| `absent` | fetch | every authorised source answered, and none has it |
| `repository-unavailable` | fetch | a source could not be asked. Not the same as absent |
| `digest-mismatch` | fetch | what came is not what the repository's checksum or the operation's digest says |
| `unauthorized-source` | fetch | the source is not one this runner may fetch from. Nothing was asked of it |
| `undiagnosed` | consumer | the task failed offline and named nothing it lacks |
| `no-progress` | consumer | it asks again for what it was given: a second tool of the task reads another place than the files were laid in. The reason quotes its line |
| `round-limit` | rounds | the operation's rounds were not enough |
| `output-mismatch` | outputs | the task ran, and an output is missing or is not what was declared |
| `tests-not-shown`, `tests-not-as-declared` | level | the task ran through at the level `tests-run`, and nothing shows a test that executed, or tests failed that the operation did not say would |
| `offline-unenforceable` | consumer | this runner cannot take the network away, so nothing was proved |

**The handover.** A ready receipt wakes the job that asked. Before its steps, the runner reads the bundle in
full against the receipt (one that changed since is handed to nobody, and the job is `blocked` until it is
resolved again), lays it over the base as a view of that attempt's own, and gives the steps the variable the
operation names. Its steps run on prepared inputs alone, as above: the base and the bundle read-only, an empty
home, and each step's record says so (`network.alone`). The job's result records the bundle it ran on (`readiness`), and the resolution
job's result carries the receipt as its `conclusion`, `ready` or `withheld`, apart from the count of anything
the case itself was asked. A withheld readiness blocks its consumer with the outcome's name; once the cause is
put right, `python3 jobs/pipeline.py resolve KEY --again` resolves the same request again, and the receipt keeps
the earlier attempts.

What it does not do: it restricts fetching to the operation's repositories under the runner's `fetch_allow` by
its own fetcher, not by a firewall around the resolution job, whose step has the host's network. It discovers
Maven coordinates from the lines Gradle and Maven print for a module they could not find or do not have cached
for offline mode (`readiness.MISSING`, and `MISSING_FILE` for a file of a module), and nothing else: a task that
fails offline for another kind of missing input (a Gradle plugin asked for by its id, a wrapper's distribution
that the operation did not pin) ends `undiagnosed`, which is a legitimate outcome and names the log to read. A
snapshot is fetched by its plain name, which a repository of releases and a folder have and a snapshot
repository does not: there it ends `absent`.

**For the runner's operator.** `fetch_allow` is empty until the machine's settings name sources
(`[runner] fetch_allow = ["https://repo.maven.apache.org/maven2/"]` in the machine's `pipeline.toml`), and with
none a resolution job is `unschedulable` and says so: which sources a machine fetches from is its owner's to
say. `fetch_slots` (ten) is how many fetching jobs run at once.

A view over a large base is cheap: a folder on the way to something laid over or left out is made, and every
other folder is one link (the S cache of 34 GB is laid in 0.2 s, as 4,700 links). `view.walk` names the folders
a tool walks, which are laid file by file, since a walk does not follow a linked folder; a `without` path that
ends in a slash leaves an empty folder of the view's own in its place.

The first real request is S48's
([`readiness-operation.json`](../verification/merged-pr-links/s01-s50/maven-war/readiness-operation.json)), replayed
by [`readiness_gate.py`](../verification/merged-pr-links/s01-s50/maven-war/readiness_gate.py) beside it.

## A batch from a manifest

A batch of cases is said once, in a manifest: a template of a job and the rows that fill it in
([`fixtures/batch-49.json`](fixtures/batch-49.json) is one).

```sh
python3 jobs/pipeline.py submit --manifest batch.json --dry-run   # the whole batch is checked, and nothing written
python3 jobs/pipeline.py submit --manifest batch.json             # one job a row, and verification/batches/NAME.json
python3 jobs/pipeline.py wait --batch NAME                        # until every row has a result or will not start
python3 jobs/pipeline.py batch NAME                               # row by row: job, state, reason, result, earlier jobs
```

```json
{"schema": "itl-job-batch/v1", "batch": "boot-s-setup", "title": "...", "created": "2026-11-28T09:00:00+00:00",
 "submitted": {"by": "the watcher", "run": "single-boot-s"},
 "template": {"title": "Build {row}", "description": "...", "purpose": "build", "resources": {"memory": "4G"},
              "steps": [{"name": "build", "run": "tools/build_case.sh {row} {module}"}], "outputs": ["out/{row}"]},
 "rows": [{"row": "S01", "vars": {"module": "core"}},
          {"row": "S02", "vars": {"module": "web"}, "override": {"needs": [{"row": "S01"}], "priority": 5}}]}
```

`{name}` in any string of the template is the row's variable (`{row}` its own name, `{batch}` the batch's), a
row's `override` replaces top-level keys of the job, and a prerequisite may name another row. Each row becomes an
ordinary job of the second format: committed, scheduled, retried and collected like any other.

| The rule | Why |
|---|---|
| The whole batch is checked before any of it is written: every row's job against the schema, duplicate rows, a variable no row gives, a prerequisite on a row that is not there, prerequisites in a circle | A batch half submitted because row 31 was wrong is two batches to reason about |
| A job's id is the manifest's `created` time, the batch, the row and the first characters of the row's **work identity**: the digest of its steps, environment, outputs, requirements, prerequisites, source revision, purpose, workload and case | Submitting the same manifest again, from another session or workspace or after a submission was killed, writes the same files with the same bytes. There is no clock and no session in what a submission writes; who the batch is submitted for is said in the manifest |
| A row whose work changed (another revision, another task, other inputs) gets a new job that `supersedes` the old one. A changed title, estimate or priority changes no id | Other work is another identity. The old job stays as it was committed |
| A `resubmit` of a row's job (the same work, other resources) makes the row that job, and the map says so; a rerun of the same job is another attempt of it | The three stay apart in the row's history: one entry a job, with its work identity and why it came |
| A row the manifest no longer has keeps its jobs and is listed as withdrawn | Nothing goes silently |

`wait --batch NAME` blocks until every row is **settled**: it has a result, or it will not start as things are
(blocked, unschedulable, invalid). It exits 0 then, 3 when `--timeout` came first, 4 when the queue could not be
read; `--json` gives `itl-job-batch-wait/v1` with every row. The queue-wide `wait` works as before beside it.
`batch NAME --json` is `itl-job-batch-view/v1`: totals in rows with what they are out of, and each row's current
job with its state, reason, result and attempts, and the jobs it had before with theirs. A row whose job nobody
can find is `missing`, and counted as that. The audit joins every map with the specifications both ways.

## The state of every job, and its reason

`python3 jobs/pipeline.py view` prints one document, `itl-job-lifecycle/v1`, with every job the queue's commits
hold, every job file not yet committed, and every result this machine has: each with **one state and the reason
for it**, its prerequisites, its claim, its attempts and its result. `status` is that view as lines, the keepers
([`queue_keeping.py`](../llm-dlc/tools/queue_keeping.py), [`run_common.py`](../llm-dlc/tools/run_common.py)) read it
as data, and nothing else decides what state a job is in.

| State | What it means | What changes it |
|---|---|---|
| `uncommitted` | Its file is in the working copy and in no commit of the queue | Commit it |
| `invalid` | Its file is not a job: not JSON, or not as its schema says. The reason carries the path and the revision it was read at | Fix the file |
| `unschedulable` | This machine cannot run it as written: more memory or CPUs than the runner allows a job, an adapter this checkout lacks, a step with no network where none can be enforced | Resubmit it, or run it elsewhere. Waiting does not help |
| `blocked` | A prerequisite ended without passing, is a job nobody submitted, or cannot itself start here. No attempt is consumed | Resubmit the prerequisite: the job that supersedes it releases this one |
| `waiting` | A prerequisite has not finished | The prerequisite passing |
| `deferred` | It could run, and a runner at work is holding it back: no room, a job ahead of it waiting for room, a priority under the runner's minimum. Only a runner at work says this (`.state/scheduling.json`) | Room, or a runner started without that limit |
| `queued` | Nothing stands in its way | A runner |
| `running` | A runner holds its claim: this workspace's, or the runner of another workspace of the repository, which the row's `claim` then names (`where: another-workspace`, its root and pid) | |
| `finished` | Its result is on this machine and not collected: in this workspace's state, or staged in the workspace whose runner ran it (`result.where` is then `staged-elsewhere`, with its root) | `collect`, in the workspace that holds it |
| `collected` | Its result is in `verification/results/` | |
| `recorded-elsewhere` | Its result is in a commit this working copy is not on (`result.commit`, and `result.change` in jj, where a working-copy commit gets another id when it is described and the change stays). It is not run again | Merge that commit |

A job stopped before it ended (cancelled) is none of the last four: it runs again, so it is `queued` or whatever
stands in its way, and the stopped attempt is in its `attempts`, with a `cancelled` block.

The view says what it could read and what it could not: the snapshot's revision, the queue's commits, and for the
queue, this machine's state, the collected results, the other heads and the private archive whether each was
`available`. **A queue that could not be read is not an empty queue**: `idle` is then `null`, `view` exits 4,
`status` begins with what was NOT READ, and the keepers take it as unknown and start or stop nothing on it.
`idle` is `true` only when nothing is queued, deferred, waiting, running or waiting to be collected; a job that
is blocked, unschedulable or invalid is nobody's to wait for. Every count in `totals` has its unit and what it is
out of, and `view --state STATE`, `--case` and `--batch` list the rows behind one (the totals stay the whole queue's).

**The runner may be in another workspace.** A repository has one runner at a time, whichever workspace it was
started in (the lock all workspaces share, VF-051), and an agent that submits from a workspace of its own is not
where it is: the watcher's runner, in the default workspace, runs its jobs. The view reads that lock, without
taking it, and says so in `runner.elsewhere` (the runner's pid, its workspace and the jobs it has claimed
there). A job it has claimed is `running` here too, with the workspace in its reason; one it has not yet claimed
is `queued`, and the reason names the runner that will find it. When the job has ended there it is `finished`
here, whether or not that runner is still at work, until that workspace's collect commits its result; from
then it is `recorded-elsewhere` until the commit is merged. So a job submitted from a workspace is never
`queued` again between its start and its merge. The attempt and the logs stay in that workspace's state. `wait` in a workspace with no runner still answers `no-runner` at
once, and names the one elsewhere: it has nothing here to wait for.

`view ID...` opens those jobs' collected receipts and gives each result with its questions apart (`execution`,
`fulfillment`, `timing`, `conclusion`, `declared`, the attempt, the ids of the occurrences sealed in the private
archive and what was collected), derived for a receipt that did not keep them. Without ids a collected job is
given from the result index, since a queue of 1,900 receipts is otherwise 1,900 files to open.

`wait --json` (`itl-job-wait/v1`: `finished`, `no-runner` or `timeout`) and `collect --json` (`itl-job-collect/v1`:
each result collected with what was applied, each hook's exit code, and the commit message) say as data what
their lines say. A hook after a collect has an outcome of its own: the results are collected whatever it exits
with, and a hook that failed is kept (`.state/last-collect.json`) and named by `status` and `view` until a later
collect runs it again.

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
