# Runtime mode and `/prove-java-change`

This repository runs in one of two modes. `python3 llm-dlc/tools/mode.py` prints which.

| | Development | Runtime |
|---|---|---|
| What it is | the repository as its authors work in it | a released copy on a user's machine, set up by the `/prove-java-change` skill |
| How it is told | no marker | `.in-the-loop-runtime.json` at the root, written by the skill's bootstrap, gitignored |
| A commit | carries its session's trace ([`README.md`](README.md)) | plain, with an `In-The-Loop-Runtime: VERSION sha256:DIGEST` trailer naming the release it was made on |
| Transcripts | redacted, summarized, published with a push | never read |
| A push | `sync.py push`, when the user asks | none: the work stays on the machine, except a contribution the user agrees to |
| Langfuse, the CDN, the allow list, the redaction rules | in use | off |
| Verification pipeline, loops, tests, examples | the same in both | the same in both |

The commands are the same in both modes, so an agent follows one procedure: [`tools/mode.py`](tools/mode.py) decides
what `sync.py commit`, `sync.py check` and the hooks in `.claude/settings.json` do. This page is the runtime side: the
skill that sets it up, the proof loop, contributions and releases.

## `/prove-java-change`

The skill ([`SKILL.md`](../plugins/in-the-loop/skills/prove-java-change/SKILL.md)) proves a change to Java code on a
user's machine, in four steps, orchestrated by Fable 5.2 at high effort. It is short on purpose: it says what each
step is for and when to stop, and this repository holds what the steps stand on.

| Step | Runs in | Stands on |
|---|---|---|
| 1. Set up, verify and measure the machine | a subagent on Opus, only when something needs setting up | [the checkout](#the-checkout-on-a-users-machine), [the machine](#is-the-machine-enough) |
| 2. Assess the change and set the example up | the orchestrating session | what the [example-targets loop](loops/example-targets.md) did for examples 285 to 300, for one change. [`examples/README.md`](../examples/README.md#add-an-example): past examples as the measure (`find.py`, their notes and receipts, `pipeline.py report`'s calibration), a target sidecar with its claims, `build.py --plan` and a replay task |
| 3. Prove it | a fork of that session, in a moonshot loop it conducts | [the proof loop](#the-proof-loop) |
| 4. Report, and offer to contribute | the orchestrating session | [contributing back](#contributing-back) |

The user confirms after steps 1 and 2, and a blocker is settled before the next step starts.

**GitHub only.** The official plugin proves changes whose revisions are commits on github.com, with dependencies
from the allowed hosts (Maven Central, repo.spring.io, the Gradle hosts), and nothing else: the routes that prepare a
revision refuse any other source ([`examples/README.md`](../examples/README.md#add-an-example)), and the skill does
not work around them. A change in a repository elsewhere, or one not pushed yet, is a blocker at step 2 until it is
on GitHub. The user decided this on 2026-11-15; a local or private source could be added here later, or by a fork of
this repository with its own release.

**In development.** Here the skill is a project skill: `.claude/skills/prove-java-change` links to its folder in the
plugin, so `/prove-java-change NNN` runs the copy being worked on. The bootstrap answers `development`, steps 1 and 2
don't apply (the checkout is the home, its machine is known and the example exists), and the skill goes straight to
step 3 on the examples named, with traces as for any loop here, and reports as in step 4.

**Installed.** A user adds this repository as a plugin marketplace and installs the plugin `in-the-loop`; the skill
is then `/in-the-loop:prove-java-change`. The plugin carries only the skill's folder: the skill, its bootstrap and
its pin.

## Procedure for agents in a runtime checkout

It replaces [`README.md`'s procedure](README.md#procedure-for-agents) and the trace rules of `CLAUDE.md`. Everything
else in `CLAUDE.md` holds: verification jobs are queued, tests have tiers, examples keep their notes.

- **Commit each feature when it is done**, as in development, with the same command:
  `python3 llm-dlc/tools/sync.py commit -m "Summary line" -m "What changed, why, and how it was verified."`
  It writes the message with the release's trailer and starts a new change. A plain `jj commit` is as good; never
  `git commit`.
- **Nothing is published.** `sync.py push`, `upload`, `scan`, `review`, `allow`, `stamp` and `langfuse` refuse to run,
  and the hooks do nothing. Don't push to any remote. The one exception is a contribution upstream, after the user
  agrees to it.
- **A new example takes a number from 900 to 999**, which no release uses, so that an update never brings an example
  with the same number. A contribution renumbers it.
- **The work is the user's.** It lives as commits on top of the release commit, and an update moves them onto the next
  release. Don't rewrite or abandon the release commit or anything below it.

## The checkout on a user's machine

[`bootstrap.py`](../plugins/in-the-loop/skills/prove-java-change/bootstrap.py) ships with the skill and is the only
part that runs before there is a checkout:

```bash
python3 bootstrap.py status     # JSON: mode, state (absent, current, outdated, broken, development), blockers
python3 bootstrap.py install    # clone into the home and stand on the pinned release, verified by its digest
python3 bootstrap.py update     # fetch, find the pinned release, rebase the local work onto it
```

The home is `$IN_THE_LOOP_HOME`, by default `~/.local/share/in-the-loop`: a jj checkout colocated with git, standing
on the release commit, with the user's work on top. jj is required: the commit procedure, the job queue (jobs are read
from `@-`) and updates (a rebase of the user's line) all go through it.

`state: current` means all of: the installed release is the one this copy of the skill is pinned to; the release
commit's tree hashes to the pin's digest, recomputed; the working copy descends from it; and the skill's files in that
commit are the bytes of the skill that is running. Setup is needed only when the state is anything else. After an
update, conflicts in the user's commits are listed for the agent to resolve.

Inside a development checkout the bootstrap answers `development`: there is nothing to install, and the checkout is
the home.

## Is the machine enough

```bash
python3 llm-dlc/tools/doctor.py           # a table: each check, what was found, what is wanted
python3 llm-dlc/tools/doctor.py --json    # the same as data, with a proposed budget; exit 1 if anything blocks
```

[`doctor.py`](tools/doctor.py) only looks: it installs and changes nothing. It has three levels.

- **Blocking**: a proof can't run here. A hardware limit (memory, CPUs or disk below the smallest machine this
  repository has run on) or another operating system is blocking by itself, and no setup removes it. A missing tool
  that every proof needs is blocking until it is installed, which
  [`examples/setup/ubuntu/install.sh`](../examples/setup/ubuntu/install.sh) does by component (`devtools` for jj and
  Rust, `jvm` for the JDKs); a runtime machine needs none of its Docker, Kubernetes or proof-assistant components.
- **Limits**: the machine works with less, and the check says what is lost: without JBMC, only what the tool's own
  checker decides; without systemd user scopes, no memory cap; without the JDKs under sdkman, no replay.
- **Ok.**

Its `budget` shares the machine out as [`verification/README.md`](../verification/README.md#running-resources-isolation-configuration)
describes: a reserve for the person and the operating system, one loop's memory cap, and the rest to the verification
runner. It is a proposal: the runner's share goes into `verification/pipeline.local.toml` (not committed), and the
loop's is its memory cap (`FEATURE_LOOP_MEMORY_MAX`).

## The proof loop

```bash
llm-dlc/tools/prove-loop.sh --fork SESSION --memory SIZE NNN [NNN ...]
```

[`prove-loop.sh`](tools/prove-loop.sh) runs [`feature-loop.sh`](tools/feature-loop.sh)'s `prove-change` moonshot over
the examples it is given, one per cycle: "Formally prove example NNN as elegantly and efficiently as possible", on
Fable 5.2 at high effort, the instruction and nothing else. It works the same in both modes.

- **The fork.** With `--fork`, the loop's session starts as a fork of the session that prepared the example, made in
  one turn without tools and then compacted, so the loop begins knowing what the preparation learned and needs no
  brief. The parent goes on untouched and may be mid-turn. Without `--fork` the loop starts a fresh session.
- **The jobs.** The proof queues its long runs as [verification jobs](../verification/README.md), as everything here
  does. `prove-loop.sh` starts the [verification loop](README.md#unattended-loops) for them unless one already runs
  for this repository, and stops it when the loop has ended and the queue is clear.
- **The cap.** The loop runs in a systemd scope with a memory cap (`--memory`; `doctor.py`'s budget proposes one). On
  a machine without systemd user scopes it refuses to start unless `FEATURE_LOOP_UNCAPPED=1` says to run with none.
- **The run's state** is in `llm-dlc/loop-summaries/prove-change/` (gitignored): `run.json` (the session, the
  examples, how it ended), `events.jsonl`, and the verification loop's log. The run's record is beside it, as for
  every loop. One run at a time in a checkout.

### The conductor

A moonshot has no acceptance criteria, so its context window is its measure: the session compacts itself at 600k
tokens, and a compaction with no commit since the cycle began, or since the last compaction, is where the work is
either hard and going well or stuck. A rule can't tell which. A loop by itself stops there; this one asks first. It
appends the event to `events.jsonl`, lets the turn go on, and waits fifteen minutes (`FEATURE_LOOP_CONDUCTOR_WAIT`,
in seconds) for a verdict:

```bash
python3 llm-dlc/tools/conductor.py wait llm-dlc/loop-summaries/prove-change      # blocks until there is something to judge
python3 llm-dlc/tools/conductor.py decide llm-dlc/loop-summaries/prove-change N continue --reason "..."
```

The session that started the loop is its conductor. It runs `wait` as a background task, so it is called back when
there is something to judge or the loop has ended (exit 3 means neither yet: wait again). It judges from outside: the
loop's transcript, which the event names, the commits and the working copy's diff, the jobs, and whether the same
failure or file keeps coming back. Then it answers and waits again.

- `continue` lets the turn run to its next compaction, where the question is asked again if there is still no commit.
- `stop`, or no answer in time, ends the turn and the loop, as the rule alone would have.
- Lean towards `continue` while the work is moving. An example left unfinished is fine, since a later run can return
  to it, and a stop costs a person's attention.

The verdict and its reason go into the run's record under the cycle's line. The conductor never writes to the loop's
session, whose instruction stays the one line.

## Contributing back

A runtime checkout's results stay on the user's machine: the example's folder (`receipts/`, its page, its notes),
`verification/results/` and `verification/findings.md`, and the run's record. Nothing of it is pushed anywhere.

When a proof needed something new of the tool (a model, a checker extension, a route), that part is worth more to the
next user than to this one, and it can go back as a pull request against `pilifs/in-the-loop`. The commits of a
runtime checkout have no traces, so they don't follow the development procedure; this is theirs.

```bash
python3 llm-dlc/tools/contribute.py status      # the local commits, and what of them can travel
python3 llm-dlc/tools/contribute.py check REV   # a prepared contribution, checked before it is pushed
```

A contribution is a branch from the upstream `main`, never the user's line as it is:

1. **What travels:** the library (`lib/`), the tools and schemas (`examples/tools/`, `examples/schema/`), their tests,
   their documentation, and an example whose every source is public (commits on github.com, JARs on an allowed host),
   renumbered to the next free number upstream.
2. **What stays:** `verification/jobs/`, `verification/results/` and `verification/findings.md` (the user's machine's
   records: upstream runs the proofs again on its own), an example whose sources are local, and anything that names
   the user's home directory, user name or host. `check` looks for each and never prints the line it found one in.
3. **How:** fetch upstream, duplicate the chosen commits onto its `main` (`jj duplicate -d main@origin`), drop what
   stays, regenerate what is generated (`build.py --index-only`, `test_costs.py estimate`), run the default tests,
   and run `contribute.py check`. Each commit keeps its `In-The-Loop-Runtime` trailer.
4. **The pull request**, only once the user agrees: push the branch to their fork (`gh repo fork --remote`, then
   `jj git push --remote fork --bookmark NAME`) and open it with `gh pr create --repo pilifs/in-the-loop`, with the
   body `check` prints: the release it was built on, what it adds, how it was verified and what was not run.

**For the maintainers.** A contributed commit has no trace, by design, and its trailer says so: `sync.py` never
stamps a session on a commit that carries it. Review it as any change, queue its proofs in the pipeline here (the
contributor's results did not travel), and merge.

## Releases

A release is one commit: the skill at a version, and the repository it runs on, pinned to each other by the sha256
digest of the commit's tree, which the skill carries in
`plugins/in-the-loop/skills/prove-java-change/release.json`, beside its bootstrap.

```bash
python3 llm-dlc/tools/release.py cut [VERSION] [--note TEXT]   # make @ a release, commit it, verify it
python3 llm-dlc/tools/release.py status                        # the last release, the commits since, pushed or not
python3 llm-dlc/tools/release.py verify
```

- **The digest** is over one line per file of the commit (mode, sha256 of its bytes, path). It leaves out the pin
  itself, which can't hold its own hash, and the files `sync.py` regenerates on every commit (`llm-dlc/traces/`,
  `llm-dlc/index.json`, `llm-dlc/README.md`), listed in the pin. It is of content only, so the trace lines added to a
  commit's message later don't move it.
- **Cutting** writes the version into the plugin and the marketplace, then the pin from `@`'s tree, commits with
  `sync.py commit`, and verifies the commit. It refuses while `@` holds other uncommitted work. It can be run at any
  commit, as often as wanted: a version is only a name for a digest.
- **Finding** a release needs no tag: the bootstrap looks through the history of the pin for the commit that carries
  this version and digest and accepts it only when its tree hashes to the digest again. One implementation of the
  digest serves both sides, in `bootstrap.py`.
- **The skill changes only in a release.** The plugin is installed from the tip of `main`, and a copy of the skill
  that is not its release's bytes refuses to run. So a change to anything in the skill's folder is followed by a cut
  before `main` is pushed; `release.py status` exits 1 while one is owed.
- **A release reaches users when `main` is pushed with it**, which stays the user's call. A copy of the skill installed
  earlier keeps its own pin and its own release until the plugin is updated (`claude plugin update`); its version in
  `plugin.json` is what tells Claude Code there is an update.
- **Trying a release before pushing it:** put a bookmark on the release commit and install from this clone:
  `IN_THE_LOOP_REPOSITORY=/path/to/this/repo IN_THE_LOOP_REF=BOOKMARK IN_THE_LOOP_HOME=/tmp/try python3
  bootstrap.py install`, run from a copy of the skill's folder outside the repository (inside it, the bootstrap
  sees a development checkout).
