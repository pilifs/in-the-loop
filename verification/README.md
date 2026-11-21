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

Everything goes through [`pipeline.py`](pipeline.py):

```bash
python3 verification/pipeline.py submit ...      # write verification/jobs/ID.json
python3 verification/pipeline.py status          # the queue
python3 verification/pipeline.py run             # run what is pending and what is committed meanwhile, then stop
python3 verification/pipeline.py nudge           # say that the queue changed: whoever waits looks at once
python3 verification/pipeline.py wait            # block until a job has finished, or no runner is at work
python3 verification/pipeline.py prioritize ID --priority 10 --reason "..."   # move jobs up the queue
python3 verification/pipeline.py run --min-priority 10   # run only the jobs at that priority or above
python3 verification/pipeline.py collect         # bring finished results into the repo
python3 verification/pipeline.py report          # Markdown digest; --format json for agents
python3 verification/pipeline.py resubmit ID --memory 8G
python3 verification/pipeline.py validate        # check job and result files against their schemas
```

Tests: `python3 verification/test_pipeline.py` (about 30 s; the systemd tests run where `systemd-run --user` works).

## Layout

| Path | What it is | Written by |
|---|---|---|
| [`README.md`](README.md) | this page: the lifecycle, [submitting a job](#for-agents-making-changes-submitting-a-job), [managing the pipeline](#for-the-agent-managing-the-pipeline), [reading results](#reading-results), [the runner's resources](#running-resources-isolation-configuration), [other backends](#backends-other-machines-and-the-cloud) | |
| [`pipeline.py`](pipeline.py) | every command: `submit`, `status`, `run`, `prioritize`, `collect`, `report`, `resubmit`, `validate`; [`test_pipeline.py`](test_pipeline.py) tests it | |
| [`/run-verification`](../.claude/skills/run-verification/SKILL.md) | the procedure of the agent that manages the pipeline, as a skill; [`llm-dlc/tools/verification-loop.sh`](../llm-dlc/tools/verification-loop.sh) runs it unattended | |
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
| `.state/` (not committed) | the runner's claims, work directories, whole logs, results not yet collected, the jvmcontract cache | `run` |

A job is *pending* while it is committed and has no result, *running* while a runner holds its claim, *finished* when
its result is in `.state/results/`, and *collected* once its result is in `results/`. A job file that is not
committed yet is not run: the runner reads jobs from the latest commit (jj's `@-`), never from the working copy. It
also reads them from `@-` in every other jj workspace of the repository, so a job committed on a branch that another
workspace works on (a stream of a feature loop run in parallel) runs at its own commit without being merged first. Its
result is collected here, in the runner's workspace, and reaches that branch when the branches are merged.

### Two layouts: flat, and by day

Every job so far is kept flat, `jobs/ID.json` and `results/ID/`: about a thousand entries in each folder by
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
- **One id, two records.** Identical copies resolve to the flat one, always. Copies that differ are a problem
  `pipeline.py validate` names, and readers still get the flat one.
- **Where new jobs go** is `WRITE` in `layout.py`: `"flat"` today. Switching it to `"shards"` is one line, for the
  user to decide once a real batch has been promoted with the readers above (the brief's order: readers first, then
  writers); `VERIFY_LAYOUT=shards` does it for one command. A sharded job's `$schema` and its result's are written
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
exceed (`systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 timeout 300 COMMAND`). Real-world claims
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

A job records the session that submitted it (the one Claude Code runs `submit` in, unless `--session` names another).
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

To keep the queue empty unattended, run `llm-dlc/tools/verification-loop.sh`: it starts a fresh session on Sonnet running the skill whenever there is work this machine can do, and watches for new jobs in between (see [`llm-dlc/README.md`](../llm-dlc/README.md#unattended-loops)).

**Who learns of a new job, and when.** Nobody waits out an interval for a job that was announced, and no job waits
for a longer one to end:

- **The commit that queues a job announces it.** `sync.py commit` runs `pipeline.py nudge` when its commit changed
  `verification/jobs/` or `priorities.json`. A nudge only touches a file in the state directory.
- A scoped commit temporarily sets other files aside in jj. The queue waits for a job in those files to receive
  its own commit. This also applies to a job that names a source revision explicitly.
- **A runner at work takes the job into its run.** `run` reads the queue at its start, at once after a nudge, and
  every `poll_seconds` (30) besides, and starts each new job beside the ones running, as the budget allows. It ends
  when nothing runs and nothing is queued, after one last look (`--watch` keeps it going).
- **A verification loop waiting for work looks at once** after a nudge, and every `VERIFICATION_LOOP_POLL` seconds
  (60) besides.
- **Each result is collected as it comes.** The agent managing a run waits with `pipeline.py wait`, which returns
  when a job has finished, and collects, triages and commits that result while the others run. A short job's
  result is not held back behind a long one.
- **The watcher of a proof loop** ([`watch.py`](../llm-dlc/tools/watch.py)) announces a job it sees queued that
  nobody announced, and starts a verification loop if none is running while jobs wait.

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
| a job starts and its run directory holds an attempt nobody sealed (its runner was killed) | that attempt's logs, outputs, diff and work directory, as `partial` | as below |
| the steps have ended, before the logs are cut | every step's whole log | `job-logs` |
| | the outputs the job produced or changed, with the declared ones that never materialized and the ones it deleted | `job-outputs` |
| | the whole `changes.diff` | `job-diff` |
| | for a job that did not pass: what its work directory holds beyond its commit (files identical to the commit are left out) | `job-workdir` |
| the runner has written `result.json` | that file, before `collect` rewrites it | `job-result` |
| `collect` is about to replace a result collected earlier | the earlier one | `job-result` |
| `collect` meets a result staged by a runner that sealed nothing | the staged files, and the whole logs if its run directory is still there | `job-result` and the above |
| `collect` has written the collected `result.json` | that file, with its conflicts | `job-result` |

Each run of a job is an *attempt*, numbered from 1 on this machine, and `result.json` names the attempt and the
occurrences under `originals`. To read them: `python3 llm-dlc/tools/artifacts.py list --job ID --include-attempts`,
then `fetch OCCURRENCE --to DIR`, which lays the files out under `DIR/verification/results/ID/` and verifies every
byte. An occurrence is `pending` until the uploader (`artifacts.py upload`) has verified it in the store.

This is a shadow of the pipeline, not a step of it: `results/` holds what it held before, and a capture that fails
(a full disk, a damaged journal) fails no job and no collect. It is said on stderr and in `.state/capture.log`, the
result then has no `originals`, and `collect` moves a staged result that nothing sealed to `.state/uncaptured/`
instead of deleting it. `ITL_ORIGINALS_OFF=1` switches capture off; the test runner sets it for every test.

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
| `out-of-memory` | the kernel killed a step at its memory limit, so no verdict | `resubmit` with more `--memory`; if more than a runner allows, it waits for a bigger machine |
| `error` | the pipeline could not run the job: a missing tool, a failed jvmcontract build, an export that failed | fix the cause; this is never a verdict |
| `cancelled` | the runner was stopped while the job ran | nothing: the next `run` runs it again, and `collect` leaves it out unless named |

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
- `job_memory_max`: no job's limit is above it. A bigger job is deferred, and stays pending for a bigger runner.
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
- The whole logs stay on the runner, in `.state/runs/`, which nothing cleans up yet. The result says where.
- Claims are local files. Two runners on different machines need disjoint jobs until there is a shared claim store.
