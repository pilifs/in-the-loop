# Verification pipeline

Proofs and model checks are slow and heavy: a JBMC proof can take half an hour and 3 GB, and a TLC run over a few
hundred thousand states takes minutes. A development agent that runs them inline waits on them, and two agents doing
it at once can exhaust the machine. So they go through a queue instead.

1. The agent that makes a change **submits a job** describing the verification it needs, and commits the job with the
   change, marked *verification pending*. It does not run the proof.
2. A **runner** picks committed jobs up as resources permit. It runs each in a clean export of the job's commit, each
   step in a systemd scope with a hard memory cap and a CPU quota, several jobs at once within a budget.
3. The agent managing the pipeline **collects** the results into `verification/results/`, which applies the files the
   jobs produced (an example's `result.json` and `README.md`) to the working copy, and commits them.
4. Anyone reads the results in a batch with **`report`**.

Everything goes through one command. Since 2026-11-27 it is [`jobs/pipeline.py`](../jobs/pipeline.py), the
pipeline for every kind of job ([`jobs/README.md`](../jobs/README.md)); verification is one workload of it
([`jobs/workloads/verification.py`](../jobs/workloads/verification.py)). [`pipeline.py`](pipeline.py) here is the
same command under the name it always had, and the commands below work with either path:

```bash
python3 verification/pipeline.py submit ...      # write verification/jobs/ID.json
python3 verification/pipeline.py submit --manifest FILE   # a batch: one job a row, and the rows' map in verification/batches/
python3 verification/pipeline.py batch NAME      # a batch row by row; wait --batch NAME blocks until every row is settled
python3 verification/pipeline.py resolve         # write a resolution job for each readiness request nothing answers (the watcher's)
python3 verification/pipeline.py status          # the queue
python3 verification/pipeline.py view            # every job's state and its reason, as data (itl-job-lifecycle/v1)
python3 verification/pipeline.py run             # run what is pending and what is committed meanwhile, then stop
python3 verification/pipeline.py nudge           # say that the queue changed: whoever waits looks at once
python3 verification/pipeline.py wait            # block until a job has finished, or no runner is at work (--json: as data)
python3 verification/pipeline.py prioritize ID --priority 10 --reason "..."   # move jobs up the queue
python3 verification/pipeline.py run --min-priority 10   # run only the jobs at that priority or above
python3 verification/pipeline.py collect         # bring finished results into the repo (--json: as data)
python3 verification/pipeline.py report          # Markdown digest; --format json for agents
python3 verification/pipeline.py resubmit ID --memory 8G
python3 verification/pipeline.py validate        # check job and result files against their schemas
python3 verification/pipeline.py prune --why     # remove kept work directories whose originals are verified, and say why the rest stay
python3 verification/pipeline.py recover         # seal what a killed runner or a failed capture left unsealed
python3 jobs/audit.py                            # reconcile specifications, receipts, indexes and the runner's state (read-only)
```

Tests: `python3 verification/test_pipeline.py` (about 30 s; the systemd tests run where `systemd-run --user` works).

## Layout

| Path | What it is | Written by |
|---|---|---|
| [`README.md`](README.md) | this page: the lifecycle, [submitting a job](#for-agents-making-changes-submitting-a-job), [managing the pipeline](#for-the-agent-managing-the-pipeline), [reading results](#reading-results), [the runner's resources](#running-resources-isolation-configuration), [other backends](#backends-other-machines-and-the-cloud) | |
| [`pipeline.py`](pipeline.py) | the entry point of before 2026-11-27: it runs [`jobs/pipeline.py`](../jobs/pipeline.py), which has every command (`submit`, `status`, `run`, `prioritize`, `collect`, `report`, `resubmit`, `validate`, `prune`, `recover`); [`test_pipeline.py`](test_pipeline.py) tests it through this path | |
| [`/run-verification`](../.claude/skills/run-verification/SKILL.md) | the procedure of the agent that manages the pipeline, as a skill, for a session with no run's watcher keeping the queue | |
| [`capture.py`](capture.py) | hands each run's originals to the private archive before they are cut or removed (see [Originals](#originals-the-whole-logs-and-outputs)); [`test_capture.py`](test_capture.py) tests it | |
| [`layout.py`](layout.py) | where a job and its result are kept, by id: flat, or under the day the job was submitted (see [Two layouts](#two-layouts-flat-and-by-day)); every reader goes through it; [`test_layout.py`](test_layout.py) tests it | |
| [`schema/job.schema.json`](schema/job.schema.json) | the job format | |
| [`schema/result.schema.json`](schema/result.schema.json) | the result format | |
| `jobs/ID.json` | one job, committed with the change it verifies | the submitting agent, with `submit` |
| `results/ID/result.json` | what happened: status, summary, attention, every step's exit, time, memory and verdict lines, the environment | `collect` |
| `results/ID/logs/` | each step's console output, whole if under 2 MB, else its head and tail | `collect` |
| `results/ID/changes.diff` | the job's outputs against its commit; over 1 MiB, the most a commit takes, it is kept gzipped as `changes.diff.gz`, or as `changes.stat`, the files it changes, when that is still over (`collected.changesDiff` says which) | `collect` |
| `results/ID/outputs/` | outputs that were not applied: the job did not pass, or the file changed since | `collect` |
| `results/index.json` | one line per result kept flat, newest first, and under `shards` the days that have an index of their own (`results/YYYY/MM/DD/index.json`, the same lines for that day's results) | `collect` |
| [`findings.md`](findings.md) | what the runs found that needs a person, and the decisions taken, open first, each with what closes it | the managing agent, by hand |
| `priorities.json` | the queue's priorities by job id, each with its reason, over the jobs' own | `prioritize`, committed |
| [`pipeline.toml`](pipeline.toml) | the runner's defaults; `~/.config/in-the-loop/pipeline.local.toml` overrides them for the machine, and `pipeline.local.toml` (not committed) for one checkout | |
| `.state/` (not committed) | the runner's claims, each attempt's record and folders (`attempts/ID/NNN-TOKEN/`: the whole logs, the outputs, the work directory), results not yet collected, the jvmcontract cache, what a runner at work decided about each job it has not started (`scheduling.json`), and what the last collect did (`last-collect.json`) | `run`, `collect` |
| `readiness/KEY.json`, `readiness/receipts/KEY.json` | a readiness request's operation, committed with the job that asks for it, and the receipt its resolution job brings back ([`jobs/README.md`](../jobs/README.md#setup-a-running-case-asks-for)) | `submit --needs-readiness`, a resolution job |
| `batches/NAME.json` | a batch's map: each row of its manifest with the job it is now and the jobs it was ([`jobs/README.md`](../jobs/README.md#a-batch-from-a-manifest)), committed with the batch's jobs | `submit --manifest`, `resubmit` |
| [`../jobs/`](../jobs/README.md) | the pipeline's shared code: the attempt records ([`attempts.py`](../jobs/attempts.py)), the record readers and the reconciliation ([`audit.py`](../jobs/audit.py)) | |

A job is *pending* while it is committed and has no result, *running* while a runner holds its claim, *finished* when
its result is in `.state/results/`, and *collected* once its result is in `results/`. A pending job that will not
start as things are says why, in `status` and in `view`: [`jobs/README.md`](../jobs/README.md#the-state-of-every-job-and-its-reason)
has the states. A job file that is not
committed yet is not run: the runner reads jobs from the latest commit (jj's `@-`), never from the working copy. It
also reads them from `@-` in every other jj workspace of the repository, so a job committed on a branch that another
workspace works on (a stream of a feature loop run in parallel) runs at its own commit without being merged first. Its
result is collected here, in the runner's workspace, and reaches that branch when the branches are merged.

### Two layouts: flat, and by day

Every job until 2026-11-22 is kept flat, `jobs/ID.json` and `results/ID/`: about a thousand entries in each folder by
2026-11-21, a few hundred more a day, against the 3,000 a forge recommends as a folder's width. A job can instead be
kept under the UTC day it was submitted, which its id begins with: `jobs/YYYY/MM/DD/ID.json` and
`results/YYYY/MM/DD/ID/`, with one overflow folder, `undated/`, for an id that begins with no date.

- **Nothing moves.** A job is written once. The runner tests the commit that last touched a job's file when the job
  names no revision, so moving a pending job would change the code it tests; and the flat paths are linked from
  commits, findings and notes. A result goes beside its job: flat for a flat job, in the shard for a sharded one.
- **Readers take both**, through [`layout.py`](layout.py) and nothing else: `pipeline.py` (the queue, `status`,
  `collect`, `commit-paths`, `report`, `resubmit`, `prioritize`, `validate`, results recorded on other heads), the
  loops' statistics in `sync.py`, the test cost inventory, the conductor and the brief's watcher, example acceptance
  and claim history, the capture of originals, and a promotion's inventory. `results/index.json` lists the results kept flat and names, under `shards`, each day
  that has results; a day's own `index.json` lists those, so the first file stops growing once new jobs go by day
  and is then the complete index of everything collected before the switch. Every line gives its result's path
  under `results/`.
- **A receipt is held to a size.** `result.json` lists every output file with its digest, and the readers that
  verify kept outputs against it need every row, so the list is not cut. Six results of November 2026 listed 3,000
  to 5,900 files each (1.5 to 2.9 MB a receipt), from jobs that wrote two files a case; such a producer packs its
  cases now ([`examples/approaches.md`](../examples/approaches.md)). `sync.py check` warns about a result submitted
  since 2026-11-22 whose `result.json` is over 256 KiB (`layout.heavy_receipts`), naming the job. The complete
  inventory of what a job wrote is in the private archive whatever the receipt holds
  (`python3 llm-dlc/tools/artifacts.py list --job ID`).
- **One id, two records.** Identical copies resolve to the flat one, always. Copies that differ are a problem
  `pipeline.py validate` names, and readers still get the flat one.
- **Where new jobs go** is `WRITE` in `layout.py`: `"shards"` since 2026-11-22, when the user switched it on (the
  folders had passed GitHub's 1,000-entry listing); jobs written before then stay flat. `VERIFY_LAYOUT=flat` gives
  the old layout for one command. The pipeline's own tests hold in either layout. A sharded job's `$schema` and its result's are written
  relative to their own depth.
- **Not through the resolver:** the scripts under `lib/benchmark/external-upgrades/` name particular results of
  November 2026 by their flat paths, which stay where they are.

## For agents making changes: submitting a job

Submit a job for anything that runs a prover or a model checker, or that takes more than a minute or more than 1 GB:
`build.py` on a B9, B11 or D1 example, an app's `verify.sh`, `jvmcontract prove`, `equivalence` or `tlc`, the
proof tier of the tests in `lib/` and the Python suites, a real-world example's proof. Keep doing inline what is quick
and what you need in order to go on: compiling, the tests of what you changed and the default test run (`python3
lib/tools/test_costs.py run`, the unit and tool tiers, which is not a job: see CLAUDE.md, Tests), `jvmcontract tla` (which only generates), a TLC run over a few hundred states while you write a model.
A probe is the one exception to the limits above: a single run of a prover or model checker on one claim, to see where
it stops or whether a change helps, may run inline for up to 5 minutes and 4 GB, one at a time, under a cap it cannot
exceed (`systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 choom -n 500 -- timeout 300 COMMAND`). Real-world claims
often need more than 1 GB to show where a checker stops; the cap keeps a runaway probe off the memory loops and jobs count on. Don't
tune memory or time just to fit under it: a run that needs more is a job. The tool tier of the tests keeps its 1 GB.

The slow tests are the proof tier: the ignored Rust tests, tagged `cost:proof:`, and the Python tests tagged
`@cost("proof", ...)`, each with its cost in `lib/tests/costs.json` (see [`lib/README.md`](../lib/README.md#tests)).
`lib/README.md` gives the `submit` command for the whole tier; a job for one change runs only the proof tests whose
inputs it touched. CLAUDE.md allows one exception inline: a single proof-tier test, once, when the change targets it
directly and its row records a past run of it alone under a minute. The slow tests also include, until they move, the
tests marked `retier: pending` in the inventory: proof tier by what they call or took, but still in the default run,
by the user's decision of 2026-11-17. They are a large part of what the default run costs.
While iterating, run the tests of what you changed, not them, unless the change targets one.

A demo example, by id, fills in the step, the outputs, the requirements and the approach. The requirements are the
tools `build.py`'s plan of the run says it calls (`python3 examples/tools/build.py --plan ID` shows them), optional ones
included. A proof by jvmcontract's own checker doesn't require JBMC, and a Box Office B12 run requires `jvmcontract`, so it
gets the verifier built at the job's commit and the build memory reserved. An example `build.py` doesn't run is refused,
with the reason:

```bash
python3 verification/pipeline.py submit --example 146 \
  --title "Example 146: a follower that truncates on a stale append, refuted" \
  --description "The new example 146 changes AppendRule#decide to truncate on any mismatch, stale or not. TLC should find a run under RaftReplicationDelayed.cfg in which a committed entry is lost." \
  --capability jvmcontract:tlc --cpus 1 --memory 2G --duration 8m \
  --estimate-notes "example 104 took 6 min and 1.6 GB under the same configuration"
```

Anything else is a list of bash steps, run from the repo root (or `--cwd`), with the files to bring back:

```bash
python3 verification/pipeline.py submit --kind library \
  --title "Liveness checking in jvmcontract tlc: integration tests" \
  --description "lib/src/tla.rs now passes PROPERTY lines to TLC and parses its temporal violations. The integration tests run TLC on three small models." \
  --capability jvmcontract:tlc --capability tlc:liveness --requires tlc --requires cargo \
  --step "integration tests" "cd lib && cargo test --release --test integration -- tlc" \
  --cpus 2 --memory 2G --duration 6m
```

Then commit the job with the change, and say so in the message: end the summary line with `(verification pending)`
and name the job in a paragraph, so a reader of the history knows the change is not verified yet:

```bash
python3 llm-dlc/tools/sync.py commit -m "Add example 146: a follower that truncates on a stale append (verification pending)" \
  -m "What changed and why ..." -m "Verification pending: job 20261102-224918-example-146-a-follower-that-truncates (verification/jobs/). Compiled and the unit tests pass; the model check was not run."
```

Then carry on with the next thing. Don't wait for the result, and don't run the job yourself to see.

A job that is not a proof or a model check (a build, a test run, a dependency resolution) is written in the second
format, by giving `submit` a `--purpose`: [`jobs/README.md`](../jobs/README.md#a-job-of-the-second-format) says what
it can declare (required outputs, tests a step promises, a step with no network) and what its result then keeps apart.

A job records the session that submitted it (the one Claude Code runs `submit` in, unless `--session` names another),
and the run that session works in (`submitted.run`, read from the loop's systemd scope; absent outside a run).
The loop statistics (`llm-dlc/traces/loops.md`) use that, or failing it the job's name in the commit message, to tie a
job and its result to the loop cycle that submitted it.

**What makes a good job.** The result is read later, in a batch, by someone who did not see your session, so:

- `--title` says what is verified, in one line. `--description` says what the change was, what the job checks, and
  anything a reader would otherwise have to rediscover: the configuration that is known to be slow, the verdict that
  would be surprising.
- `--expected` says what a pass looks like, if `--example` doesn't already: "verified; about 600,000 states under
  the delayed configuration", "exits 0; 71 tests pass". A step that is meant to find a violation can expect its
  tool's failure code with `--expect-exit`.
- `--capability` names what the job exercises, so that results can be read and estimates calibrated per capability:
  the approach (B8, B9, B10, B11, D1; `--example` adds it), the `jvmcontract` command (`jvmcontract:prove`,
  `jvmcontract:equivalence`, `jvmcontract:tlc`, ...), and a feature if there is one (`tlc:liveness`,
  `tlc:coverage`, `jbmc:arrays`, `jbmc:strings`).
- `--link` adds what the job is about: `example:104`, `path:lib/src/tla.rs`, `job:ID`.
- For an example-specific proof driver that uses the ordinary planner's default input length, add
  `--link claim:KEY` with the source claim key from `build.py --plan NNN --task T`. This binds the
  default before the job runs. The acceptance check verifies the job hash and recomputes the key.
  A driver with a different semantic bound needs that bound in the frozen claim.
- `--task T`, with one `--example` of a real-world example with a target sidecar, queues one of its tasks: the job
  runs `build.py NNN --task T`, from the same plan `build.py --plan NNN --task T` prints, and a task whose plan is not
  executable is refused rather than queued.
- One job per thing a reader would want to know separately. Two examples that can fail independently are two jobs;
  four configurations of one example are one.

**Estimates.** They are rough, and that is fine: the runner shares its budget out by them, caps each job at its
memory limit (1.5 times the estimate unless you give `--memory-limit`), and the result reports what was used next to
what was estimated. A job's timeout (4 times the duration, at least 5 minutes, unless you give `--timeout`) is where the
runner starts looking for a hang, not a deadline: past it, a step is stopped only once it has stalled, using under 1%
of a CPU and writing no output for the runner's `stall_window` (10 minutes by default). A step still working is left
to finish, and its result says it overran, since a long run is information about the change and about the machine.
Only the runner's `max_timeout` stops a step that is still working. Start from these, then from `report`'s calibration table. Anything that runs a JVM (TLC, the Box Office
Gradle build) wants 2 CPUs: with 1, its garbage collector and compiler threads are held back by the quota, and the
result says so. Measured here: examples 052 (B11) and 076 (D1) each peaked at about 125 MB, in 36 s and 12 s.

| Work | CPUs | Memory | Duration |
|---|---|---|---|
| B8 or B10 example (`jvmcontract verify`) | 1 | 1G | 1m |
| B9 or B11 example, a small proof (JBMC) | 1 | 1G | 1m |
| a JBMC proof over arrays or strings | 1 | 3G | 10m to 30m; it may run out at the 3 GB a proof gets by default |
| D1 example, up to about 100,000 states | 2 | 1G | 1m |
| D1 example, about a million states, or liveness | 2 | 2G to 3G | 10m to 30m |
| the proof tier, `test_costs.py run --tier proof` (see `lib/README.md`) | 4 | 8G | 1h30m |
| one proof-tier test, by its row in `lib/tests/costs.json` | 1 | 2G | its recorded time: heap's up to about an hour |
| a jvmcontract build, when `lib/` changed | counted by the runner, not by you | | |

A job that asks for more memory than a runner allows (its `job_memory_max`, from the machine's settings below; the
committed default, 4 GB, is a laptop's) is deferred, not run: it waits for a bigger machine. Say so in the description
if you know. `submit` names the settings it judged by, and says so when they were the committed defaults alone.

**The default test run is not a job.** It runs inline, in the session that needs its answer (CLAUDE.md, Tests;
[`lib/README.md`](../lib/README.md#tests)), and a passed run is recorded for the push's gate
(`lib/tools/default_run.py`). From 2026-11-16 to 2026-11-17 it was queued here as a job nobody waited for; the jobs
and results of that time stay as records.

## For the agent managing the pipeline

The procedure is in the [`/run-verification` skill](../.claude/skills/run-verification/SKILL.md). In short: `status`,
then `run` (in the background, or `--watch`), then `collect`, `report`, triage what needs attention, and commit the
results with `sync.py commit --only $(pipeline.py commit-paths)`, which takes its own files and leaves another session's uncommitted. Whatever needs a person (a verdict against a change,
a submitter's error, a decision that changes what the results mean) goes into [`findings.md`](findings.md), which
keeps it after the session ends; an entry is closed only by the check it names.

While a run is under way its watcher keeps the queue itself: at each look `single_run.py wait` collects and commits what is back and starts the runner when jobs wait (see [`llm-dlc/README.md`](../llm-dlc/README.md#unattended-loops)). Until 2026-11-27 a loop of its own, `verification-loop.sh`, started a fresh session on Sonnet running the skill whenever there was work; it is retired ([`llm-dlc/retired.md`](../llm-dlc/retired.md#verification-loop)).

**Who learns of a new job, and when.** Nobody waits out an interval for a job that was announced, and no job waits
for a longer one to end:

- **The commit that queues a job announces it.** `sync.py commit` runs `pipeline.py nudge` when its commit changed
  `verification/jobs/` or `priorities.json`. A nudge only touches a file in the state directory.
- A scoped commit temporarily sets other files aside in jj. The queue waits for a job in those files to receive
  its own commit. This also applies to a job that names a source revision explicitly.
- **A runner at work takes the job into its run.** `run` reads the queue at its start, at once after a nudge, and
  every `poll_seconds` (30) besides, and starts each new job beside the ones running, as the budget allows. It ends
  when nothing runs and nothing is queued, after one last look (`--watch` keeps it going).
- **Each result is collected as it comes.** The agent managing a run waits with `pipeline.py wait`, which returns
  when a job has finished, and collects, triages and commits that result while the others run. A short job's
  result is not held back behind a long one.
- **The watcher of a run** (`single_run.py wait`) announces a job that came while a runner was at work and that
  nobody announced, and starts the runner if none is at work while jobs wait.

The intervals are the backup, for a job that arrives some other way (a merge, a plain `jj commit`, another
workspace). Reading the queue is one git call for all the job files, so a look costs a fraction of a second.

## Originals: the whole logs and outputs

The files in `results/` are cut to fit a commit: a log over 2 MB is its head and tail, a diff over 1 MiB a summary,
a passed job's work directory is deleted, and a rerun of a job replaces what the last run left. Before any of that
happens, [`capture.py`](capture.py) seals the originals into the private archive
([`llm-dlc/tools/artifacts.py`](../llm-dlc/tools/artifacts.py); the contract is in
[the specification](../llm-dlc/specification.md#original-outputs)):

| When | What is sealed | Kind |
|---|---|---|
| the steps have ended, before the logs are cut | every step's whole log | `job-logs` |
| | the outputs the job produced or changed, with the declared ones that never materialized and the ones it deleted | `job-outputs` |
| | the whole `changes.diff` | `job-diff` |
| | for a job that did not pass: what its work directory holds beyond its commit (files identical to the commit are left out) | `job-workdir` |
| the runner has written `result.json` | that file, before `collect` rewrites it | `job-result` |
| `collect` is about to replace a result collected earlier | the earlier one | `job-result` |
| `collect` meets a result staged by a runner that sealed nothing | the staged files, and the whole logs if its run directory is still there | `job-result` and the above |
| `collect` has written the collected `result.json` | that file, with its conflicts | `job-result` |
| a runner starts, or `recover` is run, and an attempt is on record that never finished (its runner was killed) or whose capture failed | that attempt's logs, outputs, diff and work directory, where they are; `partial` for one that never finished | as above |
| the same, and a staged result was set aside unsealed, or a run directory of before 2026-11-27 holds an attempt nobody sealed | the folder as it is, as `partial` | `job-result`, and the above |

Each run of a job is an *attempt*, numbered from 1 on this machine, and `result.json` names the attempt and the
occurrences under `originals`. To read them: `python3 llm-dlc/tools/artifacts.py list --job ID --include-attempts`,
then `fetch OCCURRENCE --to DIR`, which lays the files out under `DIR/verification/results/ID/` and verifies every
byte. An occurrence is `pending` until the uploader (`artifacts.py upload`) has verified it in the store.

This is a shadow of the pipeline, not a step of it: `results/` holds what it held before, and a capture that fails
(a full disk, a damaged journal) fails no job and no collect. It is said on stderr and in `.state/capture.log`, the
result then has no `originals`, and `collect` moves a staged result that nothing sealed to `.state/uncaptured/`
instead of deleting it. `ITL_ORIGINALS_OFF=1` switches capture off; the test runner sets it for every test.

### Attempts: what a rerun keeps, and what may be removed

Every execution of a job is an attempt with a record and folders of its own, made before its first byte is
written, whether or not the archive answers ([`jobs/attempts.py`](../jobs/attempts.py)):

```
.state/attempts/ID/NNN-TOKEN/
    attempt.json    who ran it, when, at which commit; how it ended; where its originals stand; what was released
    result.json     the result as the runner wrote it
    run/            the whole logs, the outputs it produced, the diff
    work/           the export of the commit that its steps ran in
```

- **A rerun clears nothing.** Until 2026-11-27 every run of a job wrote into `.state/runs/ID` and `.state/work/ID`,
  and a rerun cleared them after asking the archive to keep what was there. When the archive could not (a full
  spool), the earlier attempt's bytes went with the folder. The result names its attempt (`attempt.id`,
  `attempt.number`, and the attempts before it under `attempt.previous`).
- **`capture` in the record** says where the attempt's originals stand: `sealed`, `off` (nothing captures here),
  `failed` with the reason, or `recovered`. An attempt whose runner died is `interrupted`.
- **`recover`** seals what nothing sealed: an interrupted attempt, one whose capture failed, a staged result set
  aside, a run directory of before attempts had folders. It seals each where it is and removes nothing. A runner
  does it when it starts. `recover --kept-outputs` also seals the outputs that receipts say were kept and that
  this working copy holds while no commit does (VF-080). Until it succeeds, `python3 jobs/audit.py` lists each
  such attempt as a gap.
- **`prune`** removes a work directory only when all of this holds, and `prune --why` says which did not:
  1. the job's result is collected, and the collected receipt is of this attempt or of a later one;
  2. the original sealed from *this* attempt's work directory, and the attempt's other originals, are
     `remote_verified` in the store, recorded for this job and this attempt;
  3. the folder is still what was sealed: its entries' names, sizes and times are the ones recorded then.

  A passed job's work directory is not an original (the logs, the outputs and the diff are what is kept of it) and
  goes when the job ends, unless `keep_workdirs = "always"`. An attempt that ran while nothing captured originals
  is in no archive, and goes only with `prune --unarchived`. `collect` prunes when it is done, and the brief
  queue's cleanup between two briefs is this same command. Before 2026-11-27 the question was whether the job's
  *latest captured* work directory was verified, which is an earlier attempt's when a later one's capture failed.
- **A work directory of before attempts had folders** (`.state/work/ID`) goes by the same rule, tied to the
  receipt's attempt by the seal its run directory carries (`.state/runs/ID/.captured`): without that seal, or with
  another attempt's, it stays.
- **A collect that was stopped** is finished by the next one. A result whose collected form is already in the
  tree, from the same staged bytes (`collected.staged`), is not written again: the tree keeps what it has, so a
  result that was committed meanwhile is published once.

## Reading results

Read `status`, `summary` and `attention` first. For many results at once, `report` gives the ones that need
attention first, each with its steps' last lines, then the clean passes, then how estimates compared with use;
`report --format json` gives the same for an agent, with each job's description and expectation next to its result.
Filters: `--status failed`, `--capability D1`, `--since 2026-11-02T00:00`, or job ids.

| Status | Meaning | What to do |
|---|---|---|
| `passed` | every step exited as expected | check `attention`; if empty, nothing |
| `failed` | a step's exit was not the expected one: usually the verifier found a problem (a refuted property, an example whose verdict differs from its expectation), sometimes a wrong command | read the step's `tail` and log; tell whoever owns the change |
| `timeout` | a step hit its timeout and gave no verdict | `resubmit` with a longer `--duration` or `--timeout`, or smaller bounds |
| `out-of-memory` | the kernel killed a step at its memory limit, so no verdict; or the machine ran short and the runner stopped the job a second time (`memoryStop`), or the kernel killed it under its own limit when the machine ran out (`limitOoms` 0): `attention` says which | at its own limit: `resubmit` with more `--memory`; if more than a runner allows, it waits for a bigger machine. For the machine's memory: regroup (fewer workers, a higher `--memory` estimate so fewer run beside it, or a smaller job), not a plain rerun |
| `error` | the pipeline could not run the job: a missing tool, a failed jvmcontract build, an export that failed | fix the cause; this is never a verdict |
| `cancelled` | the runner was stopped while the job ran, or stopped the job once because the machine fell under its memory floor (`memoryStop`) | nothing: the next `run` runs it again when there is room, and `collect` leaves it out unless named |

`attention` explains, in words, whatever a reader should look at, including in a pass: JBMC printing `VERIFICATION
ERROR` (no verdict), a log that mentions running out of memory, a process killed at the limit, an estimate off by
more than half, outputs not applied. A pass with nothing in `attention` is clean.

Each step also carries `signals`: the verdict lines lifted out of its log with their line numbers (JBMC's
`VERIFICATION SUCCESSFUL`, `FAILED` and `ERROR`; TLC's "No error has been found", violated invariants and
properties, deadlocks and state counts; jvmcontract's ✓, ✗ and ⚠ lines; build.py's "as expected", "EXPECTED" and `not-executed`, and a target task's "as expected" and "NOT AS EXPECTED";
`cargo test` totals; out-of-memory lines), counted in `signalCounts`. Only `VERIFICATION SUCCESSFUL` from JBMC is a
proof, as everywhere in this repo: an exit of 0 with `jbmc:no-verdict` is not one.

The environment (host, CPU, memory, Java, JBMC, TLC, cargo and rustc versions), the commit, the limits, and the
jvmcontract build (by the tree id of `lib/`) are recorded, so a result can be compared with one from another machine.
A result records its machine under the runner's `machine_name` (the machine's settings; the hostname when it is
empty). `report` names the machine of every result (that name, architecture, WSL, CPUs) and gives its calibration
table per machine, since a duration measured on one says little about another. Every result collected before
2026-11-06 ran on `FilSurface`, an 8-core aarch64 WSL2 laptop, recorded by its hostname; later ones on `vm-1`, a
28-vCPU x86_64 VM, unless they say otherwise.

## Running: resources, isolation, configuration

The runner reads [`pipeline.toml`](pipeline.toml), then the machine's settings, `~/.config/in-the-loop/pipeline.local.toml`
(`$XDG_CONFIG_HOME` moves it; `$VERIFY_MACHINE_CONFIG` names another file, or none when empty, as every test run
sets it), then this checkout's `pipeline.local.toml` (not committed), then `$VERIFY_CONFIG`, then flags. The
machine's file is the one to keep: a jj workspace beside the default one has no gitignored file of its own, and
before 2026-11-17, when it was only the default workspace's, `submit` in a side workspace judged jobs by the
laptop's defaults (4 GB a job on a machine that allows 24 GB):

```bash
python3 verification/pipeline.py run --workers 3 --cpus 6 --memory 6G --job-memory-max 4G
```

- `workers`, `cpus`, `memory`: how many jobs at once, and the CPUs and memory shared out among them. A job starts
  when its CPUs and its memory limit fit in what is left, and when the machine has that much memory available. Jobs
  start in order of priority, then submission time; a job waiting for room is not overtaken.
- **Priorities.** A job's own `priority` (`submit --priority`) is fixed when it is committed. To move a job later,
  when work turns out to wait on its result or it was superseded, use `prioritize ID... --priority N --reason TEXT`
  (`--clear` drops the entry, no ids lists them). It writes `priorities.json`, which overrides the job's own priority
  and is read at the same commit as the jobs, so commit it before running; `status` says when it is not committed,
  and lists the pending jobs in the order they would start, with their priorities. `run --min-priority N` runs only
  the jobs at N or above and leaves the rest pending.
- `max_timeout`, `stall_window`: the hard ceiling on any step, working or not, and how long a step past its timeout
  must be idle and silent to count as hung (see Estimates).
- `job_memory_max`: no job's limit is above it. A bigger job is unschedulable here, and stays pending for a bigger runner.
- `fetch_allow` (default none), `fetch_slots` (default 10), `readiness_dir` (default `~/.cache/in-the-loop/readiness`):
  the URL prefixes a resolution job may fetch from on this runner (with none, a job with a `fetch` step is
  unschedulable here), how many downloads' worth of such jobs run at once, and where prepared bundles and their
  receipts are kept for every checkout of the machine ([`jobs/README.md`](../jobs/README.md#setup-a-running-case-asks-for)).
- `memory_floor` (default 8G, `--memory-floor`, 0 for none): what the machine keeps free for everything that is not
  a job: the watcher, the agents, terminals. No job starts that would take available memory under it. When the machine
  falls under it anyway (an agent's build, a session that grows), the runner stops its newest job at once, then the next
  only if that was not enough. A job stopped this way is `cancelled` and runs again when there is room; stopped a second
  time it is `out-of-memory`, with `memoryStop` saying so, for its submitter to regroup.
- `job_oom_score_adj` (default 1000): every process of a job starts with it, so should the machine run out all the
  same, the kernel's OOM killer takes a job's process first. An agent's test runs and probes take 500 and everything
  else keeps 0 (the order: [llm-dlc/operating-notes.md](../llm-dlc/operating-notes.md#the-kill-order-when-memory-runs-out)).
- `isolation`: `systemd` runs each step in a transient user scope with `MemoryMax` (no swap, so the cap is exact),
  `OOMPolicy=continue` (so one killed process does not stop the rest) and `CPUQuota`, and reads its peak memory and
  CPU time from the cgroup. Anything a step leaves running, such as a Gradle daemon, is stopped with its scope.
  `none` enforces timeouts only, and measures the largest process's peak; use it inside a container that is capped
  already. `auto` picks systemd when it works.
- Inside the cap, the runner sets `JVMCONTRACT_JBMC_MEMORY_MB` to the limit less 512 MB, so that JBMC stops with
  "out of memory" instead of being killed, and `JVMCONTRACT_JAVA_OPTS` to a TLC heap of 60% of the limit (Java's
  default is a quarter of the machine, not of the cap). A job's `env` overrides both.
- The runner points `BUILD_CHECKPOINTS` at `.state/checkpoints`, where `examples/tools/build.py` keeps each TLC
  configuration's completed result under the fingerprint of its inputs. A job run again after a timeout or a failure
  then reruns only the configurations that had not completed; a result is reused only on identical inputs, and the
  example's result says which were. `BUILD_CHECKPOINTS=off` in the runner's environment or a job's `env` keeps none.
- A job that requires `jvmcontract` gets one built from `lib/` at the job's commit, cached by the tree id of `lib/`,
  on `PATH` and in `$JVMCONTRACT`, with that tree id in `$JVMCONTRACT_LIB_TREE` (an external target's verifier record
  names the binary's commit and tree from it). The build is recorded as step 0 when it happens.
- The export is a plain tree inside this repository's own (under `.state/work`), so the runner sets
  `GIT_CEILING_DIRECTORIES` to keep git in a job from taking this repository for the job's. Without it, `git apply`
  skipped every file of a git-format patch and exited 0, and an example ran on its unpatched code.
- `link`: paths outside git that jobs need, linked into every export (none by default; the JDK models that once
  lived in a fork under `libs/` now ship with `jvmcontract`).

The committed defaults suit the WSL laptop (8 cores, 9 GB): they leave room for one development session in the
feature loop's scope (3.5 GB by default). Without it, `--memory 7G` is safe there. A bigger machine sets its own budget
in the machine's settings file, with a comment on what it leaves for the loop (`FEATURE_LOOP_MEMORY_MAX`) and the OS.

## Backends: other machines and the cloud

A job is self-contained by design: a commit, a list of bash steps, resources, and the files to bring back. The
runner only needs `git archive` of the commit, the tools the job requires, and somewhere to write the result
directory. To run jobs elsewhere:

- **Another local machine** with this repo: run `pipeline.py run` there with its own budget, then copy its
  `.state/results/ID/` directories into this checkout's `.state/results/` and `collect` here. Claims are per state
  directory, so give each runner a disjoint set of job ids (`run ID ...`) until claims are shared.
- **A cloud backend** would implement the same contract: claim a job, ship the commit's archive and the job's spec,
  run the steps under the job's limits (a container's memory and CPU limits play the systemd scope's part, with
  `isolation = "none"` inside it), and return the result directory, `result.json` in the format of
  [`result.schema.json`](schema/result.schema.json), logs and outputs. Its place in `pipeline.py` is the `backend`
  setting, which accepts only `local` so far, and the `Runner` class, whose `prepare`, `run_steps` and
  `collect_outputs` are the parts a remote runner replaces. Collection, reporting and the job format stay as they are.

## Limits

- A job runs at the commit that committed it, not at the tip. If its outputs changed in the working copy since,
  `collect` does not overwrite them: it keeps them under `outputs/` and says to rerun the job on the newer commit.
- The whole logs stay on the runner, in each attempt's `run/` folder, which nothing cleans up yet. The result says where.
- Claims are local files. Two runners on different machines need disjoint jobs until there is a shared claim store.
