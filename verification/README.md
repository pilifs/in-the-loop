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
python3 verification/pipeline.py run             # run what is pending, then stop; --watch keeps polling
python3 verification/pipeline.py collect         # bring finished results into the repo
python3 verification/pipeline.py report          # Markdown digest; --format json for agents
python3 verification/pipeline.py resubmit ID --memory 8G
python3 verification/pipeline.py validate        # check job and result files against their schemas
```

Tests: `python3 verification/test_pipeline.py` (about 30 s; the systemd tests run where `systemd-run --user` works).

## Layout

| Path | What it is | Written by |
|---|---|---|
| [`schema/job.schema.json`](schema/job.schema.json) | the job format | |
| [`schema/result.schema.json`](schema/result.schema.json) | the result format | |
| `jobs/ID.json` | one job, committed with the change it verifies | the submitting agent, with `submit` |
| `results/ID/result.json` | what happened: status, summary, attention, every step's exit, time, memory and verdict lines, the environment | `collect` |
| `results/ID/logs/` | each step's console output, whole if under 2 MB, else its head and tail | `collect` |
| `results/ID/changes.diff` | the job's outputs against its commit | `collect` |
| `results/ID/outputs/` | outputs that were not applied: the job did not pass, or the file changed since | `collect` |
| `results/index.json` | one line per result, newest first | `collect` |
| [`pipeline.toml`](pipeline.toml) | the runner's defaults; `pipeline.local.toml` (not committed) overrides them per machine | |
| `.state/` (not committed) | the runner's claims, work directories, whole logs, results not yet collected, the jvmcontract cache | `run` |

A job is *pending* while it is committed and has no result, *running* while a runner holds its claim, *finished* when
its result is in `.state/results/`, and *collected* once its result is in `results/`. A job file that is not
committed yet is not run: the runner reads jobs from the latest commit (jj's `@-`), never from the working copy.

## For agents making changes: submitting a job

Submit a job for anything that runs a prover or a model checker, or that takes more than a minute or more than 1 GB:
`build.py` on a B9, B11 or D1 example, an app's `verify.sh`, `jvmcontract prove`, `equivalence` or `tlc`, the
integration tests in `lib/` that call JBMC and TLC, a real-world example's proof. Keep doing inline what is quick and
what you need in order to go on: compiling, unit tests, `cargo test` without the slow tests, `jvmcontract tla` (which
only generates), a TLC run over a few hundred states while you write a model.

A demo example, by id, fills in the step, the outputs, the requirements and the approach:

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
- One job per thing a reader would want to know separately. Two examples that can fail independently are two jobs;
  four configurations of one example are one.

**Estimates.** They are rough, and that is fine: the runner shares its budget out by them, caps each job at its
memory limit (1.5 times the estimate unless you give `--memory-limit`) and stops it at its timeout (4 times the
duration, at least 5 minutes, unless you give `--timeout`), and the result reports what was used next to what was
estimated. Start from these, then from `report`'s calibration table. Anything that runs a JVM (TLC, the Box Office
Gradle build) wants 2 CPUs: with 1, its garbage collector and compiler threads are held back by the quota, and the
result says so. Measured here: examples 052 (B11) and 076 (D1) each peaked at about 125 MB, in 36 s and 12 s.

| Work | CPUs | Memory | Duration |
|---|---|---|---|
| B8 or B10 example (`jvmcontract verify`) | 1 | 1G | 1m |
| B9 or B11 example, a small proof (JBMC) | 1 | 1G | 1m |
| a JBMC proof over arrays or strings | 1 | 3G | 10m to 30m; it may run out at the 3 GB a proof gets by default |
| D1 example, up to about 100,000 states | 2 | 1G | 1m |
| D1 example, about a million states, or liveness | 2 | 2G to 3G | 10m to 30m |
| `cargo test --release` in `lib/` with JBMC and TLC | 2 | 2G | 5m to 10m |
| a jvmcontract build, when `lib/` changed | counted by the runner, not by you | | |

A job that asks for more memory than a runner allows (4 GB a job here) is deferred, not run: it waits for a bigger
machine. Say so in the description if you know.

## For the agent managing the pipeline

The procedure is in the [`/run-verification` skill](../.claude/skills/run-verification/SKILL.md). In short: `status`,
then `run` (in the background, or `--watch`), then `collect`, `report`, triage what needs attention, and commit the
results with `sync.py commit`, keeping out other sessions' files.

To keep the queue empty unattended, run `llm-dlc/tools/verification-loop.sh`: it starts a fresh session on Sonnet running the skill whenever there is work this machine can do, and watches for new jobs in between (see [`llm-dlc/README.md`](../llm-dlc/README.md#unattended-loops)).

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
properties, deadlocks and state counts; jvmcontract's ✓, ✗ and ⚠ lines; build.py's "as expected", "EXPECTED" and `not-executed`;
`cargo test` totals; out-of-memory lines), counted in `signalCounts`. Only `VERIFICATION SUCCESSFUL` from JBMC is a
proof, as everywhere in this repo: an exit of 0 with `jbmc:no-verdict` is not one.

The environment (host, CPU, memory, Java, JBMC, TLC, cargo and rustc versions), the commit, the limits, and the
jvmcontract build (by the tree id of `lib/`) are recorded, so a result can be compared with one from another machine.

## Running: resources, isolation, configuration

The runner reads [`pipeline.toml`](pipeline.toml), then `pipeline.local.toml`, then `$VERIFY_CONFIG`, then flags:

```bash
python3 verification/pipeline.py run --workers 3 --cpus 6 --memory 6G --job-memory-max 4G
```

- `workers`, `cpus`, `memory`: how many jobs at once, and the CPUs and memory shared out among them. A job starts
  when its CPUs and its memory limit fit in what is left, and when the machine has that much memory available. Jobs
  start in order of priority, then submission time; a job waiting for room is not overtaken.
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
  on `PATH` and in `$JVMCONTRACT`. The build is recorded as step 0 when it happens.
- `link`: paths outside git that jobs need, linked into every export (none by default; the JDK models that once
  lived in a fork under `libs/` now ship with `jvmcontract`).

On this machine (8 cores, 9 GB, WSL) the defaults leave room for one development session in the feature loop's 4 GB
scope. Without it, `--memory 7G` is safe.

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
