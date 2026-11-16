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

The skill ([`SKILL.md`](../plugins/in-the-loop/skills/prove-java-change/SKILL.md)) proves a change to Java code, or
[a list of changes](#many-changes-and-preparing-without-proving), on a user's machine. The session it is started in
is [the watcher](#the-watcher), on Opus 5.5: it runs four stages in order, each in a session of its own model and
effort, and reports. The skill is short on purpose: it says what each stage is for and when to stop, and this
repository holds what the stages stand on.

| Stage | Session | Model, effort | Stands on |
|---|---|---|---|
| 1. Set up and measure the machine | a new one, only when something needs setting up; the check of Claude Code is the watcher's, every run | Opus 5.5, high | [the checkout](#the-checkout-on-a-users-machine), [the machine](#is-the-machine-enough), [what Claude Code has loaded](#what-claude-code-has-loaded) |
| 2. Evaluate and order them, and design or review their claims | the fixed session, on every run | Fable 5.2, high | [its brief](#stage-2-evaluate-and-order-them-and-design-or-review-their-claims): past examples as the measure, the claims designed or reviewed in full, a plan from [`prove-plan-template.md`](prove-plan-template.md) with its data as [`prove-plan.schema.json`](prove-plan.schema.json). [`changes.py`](#many-changes-and-preparing-without-proving) says what is already prepared |
| 3. Set the examples up | a new one | Opus 5.5, high | [its brief](#stage-3-set-the-examples-up): the plan's claims written by [`scaffold_example.py`](../examples/tools/scaffold_example.py), then what the [example-targets loop](loops/example-targets.md) did for examples 285 to 300, for each change of the plan |
| 4. Prove them | the fixed session, continued, in a moonshot loop the watcher watches | Fable 5.2, high | [the proof loop](#the-proof-loop), [watching it](#watching-the-loop) |
| Report, and offer to contribute | the watcher | Opus 5.5 | [contributing back](#contributing-back) |

Beside the stages, the watcher keeps a verification loop running on Sonnet 5.5 for the jobs the sessions queue. The
user confirms once, after stage 2, with the machine's assessment and the plan in front of them; a hardware limit
that blocks ends the run after stage 1. With `--scaffold-only` the skill stops after stage 3.

**GitHub only.** The official plugin proves changes whose revisions are commits on github.com, with dependencies
from the allowed hosts (Maven Central, repo.spring.io, the Gradle hosts), and nothing else: the routes that prepare a
revision refuse any other source ([`examples/README.md`](../examples/README.md#add-an-example)), and the skill does
not work around them. A change in a repository elsewhere, or one not pushed yet, is set aside at stage 2 until it is
on GitHub. The user decided this on 2026-11-15; a local or private source could be added here later, or by a fork of
this repository with its own release.

**In development.** Here the skill is a project skill: `.claude/skills/prove-java-change` links to its folder in the
plugin, so `/prove-java-change NNN [NNN ...]` runs the copy being worked on. The bootstrap answers `development`,
stage 1 doesn't apply (the checkout is the home and its machine is known), and the request names
[examples by number](#examples-named-by-number): the watcher starts the verification
loop, checks them, has stage 2 order them and design or review their claims, has what needs it set up, and takes
them to stage 4 in the plan's order, with traces as for any loop here. The fixed session is a new one (`watch.py session --new`) unless the request names a session to
continue (`watch.py session --use ID`), such as the one an earlier moonshot ran in, which then keeps what it learned.
Every moonshot over examples is run this way from now on.

**Installed.** A user adds this repository as a plugin marketplace and installs the plugin `in-the-loop`; the skill
is then `/in-the-loop:prove-java-change`. The plugin carries only the skill's folder: the skill, its bootstrap and
its pin.

### Many changes, and preparing without proving

```
/in-the-loop:prove-java-change [--scaffold-only] [--wait-for-proofs] [--summary-interval SECONDS] [--instruction "TEXT"] <one change, or a list of them, each with what to prove about it>
/in-the-loop:prove-java-change [--wait-for-proofs] [--unattended] [--summary-interval SECONDS] [--record-as NAME] [--instruction "TEXT"] NNN [NNN ...]
```

The second form names [examples by number](#examples-named-by-number): ones that are already prepared, and
catalog entries, which are set up first.
`--instruction` gives [the proof loop](#the-proof-loop) the user's own text in place of its one line.
`--summary-interval` says how often the watcher prints a summary (every 30 minutes otherwise).
`--unattended` is for a run the user is away from: the watcher accepts the claims of the catalog entries it had set
up itself, as decisions flagged for the user's review, in place of asking.
`--record-as NAME` files the run under another loop's name, for a run that continues that loop's list.

The skill may also be started by the session itself when the user asks for it in their own words, with the request
as its arguments. Nothing else starts it: a run spends hours and tokens, and that is the user's to ask for.

- **A list.** Stage 2 understands and sizes every change before an example is added for any. Then it orders them, the
  most accessible first: a proof that lands early can extend the verifier under the later ones, and a hard one first
  can use up the run. The order is the evaluating session's judgement, from the same reading that sizes each change, and it says
  why. A change that can't be prepared is set aside with its reason, and the others go on.
- **The numbers carry the order.** The examples are added in that order on the next free numbers from 900, so the
  order needs no record of its own. Each example's `provenance` is the request it was prepared from, and its notes
  hold what the preparation learned and why it sits where it does, since its proof may start in a session that never
  saw the preparation.
- **`--scaffold-only`** ends the skill after stage 3: every example is a reproducible scaffold (its revisions
  materialize, the change has run once on a JVM, its claims are frozen), committed, and no proof has started. It is
  the readiness the examples' index calls `scaffolded`
  ([`examples/README.md`](../examples/README.md#run-an-example)).
- **The same request again, without the flag,** proves what was prepared. Nothing remembers a request: stage 2 finds
  each change's example by its source and revisions, keeps it, and prepares only what has none. So a list can also
  grow between runs, and a run that was interrupted is picked up the same way.
- **One after another, or stopping in between.** One run of the [proof loop](#the-proof-loop) takes the examples
  one after another in one session, each for as many cycles as it takes. The user can ask the watcher at any time to
  stop after the example under way (`watch.py stop-after example`), look at its report, and go on with another run.

[`changes.py`](tools/changes.py) is what the skill reads for all of this. It derives each example's state from its
folder (its sidecar, its claims and its receipts) and the verification results its sidecar cites, so nothing is kept
in step by hand:

```bash
python3 llm-dlc/tools/changes.py [NNN ...]             # each example: its state, its change, the request it came from
python3 llm-dlc/tools/changes.py --pending [NNN ...]   # the numbers still to prove, in order: prove-loop.sh's arguments
```

| State | What it means | A proof loop |
|---|---|---|
| `catalogued` | A catalog entry: its revisions are pinned and its sidecar has no task, so nothing is built and nothing states a claim | leaves it out until it is [set up](#examples-named-by-number) |
| `unprepared` | The scaffold is incomplete, and `why` says where: a revision that does not materialize, no replay, a claim that is not frozen, tasks and no proof task among them | leaves it out |
| `prepared` | The scaffold is complete and at least one claim has no answer yet, or was left open | takes it |
| `decided` | Every claim is established or refuted. A refuted claim decides: it is a finding, not work left | leaves it out |
| `unknown` | No target sidecar (a constructed example, named in a development checkout) | takes it when it is named |

Without numbers it lists the checkout's own examples, 900 to 999, by number; with numbers, those, in the order given.

**A claim's answer** is the route's, from a current receipt (`build.py`), or one given beside the route. A session
may decide a claim through an adapter entry and a script of the example's own, run as a verification job, as the
`prove-examples` loop did for examples 286 and 287 (`proofs/prove.py`). That leaves no receipt, so the session
records it in the sidecar, on the task:

```json
"besideRoute": {"answer": "established", "job": "20261115-234439-example-286-fixed-security-through-the-a",
                "by": "proofs/prove.py fixed-security: the frozen claim through the adapter entry, with a lemma",
                "recorded": "2026-11-15"}
```

The record alone decides nothing. `changes.py` counts the answer only while that job's result is in the checkout
(`verification/results/`), `passed`, and the job names the example in its `links.examples`; otherwise the claim
stays open and the row says what is missing. A receipt of the route, once there is one, outranks it. A claim that
is still open also carries `blocked`: the kinds of the observed gaps of the verifier its task stops at. An example
whose open claims all stop at such a gap is still `prepared`: whether a loop has anything left to do on it is a
judgement, [the watcher's](#watching-the-loop).

## Where things are

| Path | What it is |
|---|---|
| [`plugins/in-the-loop/skills/prove-java-change/`](../plugins/in-the-loop/skills/prove-java-change/SKILL.md) | The skill (`SKILL.md`), its [bootstrap](#the-checkout-on-a-users-machine) (`bootstrap.py`) and the pin of [its release](#releases) (`release.json`) |
| [`plugins/in-the-loop/.claude-plugin/plugin.json`](../plugins/in-the-loop/.claude-plugin/plugin.json), [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) | The plugin's manifest and the marketplace entry that installs it |
| `.claude/skills/prove-java-change` | A link to the skill's folder, which makes it a project skill in this repository |
| [`tools/mode.py`](tools/mode.py) | Which [mode](#runtime-mode-and-prove-java-change) a checkout is in; `sync.py` asks it |
| [`tools/doctor.py`](tools/doctor.py) | [Whether the machine is enough](#is-the-machine-enough), and a budget for it |
| [`tools/watch.py`](tools/watch.py), [`watch-summary-template.md`](watch-summary-template.md), [`prove-plan-template.md`](prove-plan-template.md) | [The watcher's](#the-watcher) tool, the summary it prints at intervals, and the plan stage 2 fills in |
| [`tools/claude_setup.py`](tools/claude_setup.py) | [What Claude Code has loaded](#what-claude-code-has-loaded) besides the plugin, and the clean launch |
| [`tools/changes.py`](tools/changes.py) | [Which examples are prepared, decided or still to prove](#many-changes-and-preparing-without-proving) |
| [`tools/prove-loop.sh`](tools/prove-loop.sh), [`tools/feature-loop.sh`](tools/feature-loop.sh) | [The proof loop](#the-proof-loop), and the loop under it |
| [`tools/conductor.py`](tools/conductor.py) | [How the loop and the watcher talk](#the-conductor): the loop's questions, the watcher's verdicts |
| [`tools/contribute.py`](tools/contribute.py) | [What can go upstream](#contributing-back), and a check of a prepared pull request |
| [`tools/release.py`](tools/release.py) | [Cutting a release](#releases) |
| `.in-the-loop-runtime.json` (not committed) | The marker of a runtime checkout, written by the bootstrap |
| `llm-dlc/loop-summaries/prove-change/` (not committed) | The state of a proof loop's run, beside the run's record |

Stages 2 and 3 of the skill stand on the [examples](../examples/README.md#add-an-example), the proofs run through the
[verification pipeline](../verification/README.md), and the verifier is [`lib/`](../lib/README.md).

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
  with the same number. A contribution renumbers it. Among them the numbers are the order they are proved in.
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

## What Claude Code has loaded

Anything a session holds besides the plugin and the checkout is context from somewhere else: another plugin's
skills, an MCP server's or a claude.ai connector's tools and instructions, the user's memory files, their own
skills, agents and hooks. Reaching the session that writes the claims or the one that proves them, it may lead to
unexpected results. Stage 1 checks for it on every run:

```bash
python3 llm-dlc/tools/claude_setup.py check [--json]   # the warning, what is loaded, whether a clean launch works here
python3 llm-dlc/tools/claude_setup.py launch [ARG ...] # start a clean session in this checkout
python3 llm-dlc/tools/claude_setup.py flags            # the clean launch's flags, one per line, for the loop scripts
```

- **A clean session** loads this checkout (its `CLAUDE.md`, its settings, its skills) and nothing of the user's own
  setup. It is a matter of launch flags: `--setting-sources project,local` leaves the user's settings out, and with
  them their plugins, hooks, skills and agents; `--strict-mcp-config` and `ENABLE_CLAUDEAI_MCP_SERVERS=false` leave
  out every MCP server and connector; and the memory files of the user and of the directories above the checkout
  are excluded by path (`claudeMdExcludes`). Nothing in the user's configuration is edited, so nothing has to be put
  back afterwards. Logging in, the model and permissions work as usual.
- **The checkout's own memory always stays**, in both modes: its `CLAUDE.md` and rules, and the notes Claude Code
  keeps for the checkout's folder by itself (its auto memory, under `~/.claude/projects/`). They are what earlier
  sessions learned about this work, and no flag here leaves them out. Seen on 2026-11-16 with Claude Code 2.1.325
  and made-up notes: a clean session held the folder's own `CLAUDE.md` and its auto memory, and not the `CLAUDE.md`
  of the directory above. The user's own memory file was not part of that probe (this machine has none).
- **The sessions the watcher starts are clean by themselves** in a runtime checkout: the evaluation and the setup
  of the examples ([`watch.py`](tools/watch.py)'s stages), the proof loop's cycles, compactions and judge, and the
  verification loop's runs ([`loop-common.sh`](tools/loop-common.sh)'s `isolation`). So everything that states a
  claim or proves one is clean whatever the user's session holds, and `check` proves it on the machine by starting
  one. `prove-loop.sh --no-isolation` starts them as a plain `claude`, for a machine where a clean launch
  does not answer (a login kept in the user's settings, for one). A development checkout's loops are not isolated:
  its authors' setup is theirs.
- **The session the user is in, the watcher, can't unload what it holds.** It does none of the work, but it
  relays the request, judges the cycles and reports, so what it holds can still colour the run. `check` starts two one-word sessions on the smallest
  model, without tools or a transcript, and compares what each reports at start-up: one started as the user's
  session was (its directory and launch flags, from the process `CLAUDE_PID` names), one clean. What only the first
  has is what the session has loaded, with the memory files and hooks it reads and the plugins Claude Code's own
  listing calls enabled. When that is not empty, `check` prints the command of a clean session (`launch`, on
  Opus 5.5 at high effort), where the skill is run again as `/prove-java-change`: the checkout carries the skill
  as a project skill. The user may continue in the session they have instead, which is not recommended.
- **What it can't do.** Settings an administrator manages (`/etc/claude-code/`) apply to every session, and `check`
  lists them. A non-interactive probe can report less than an interactive session holds (it has been seen to
  report no connectors in a directory with a memory file of its own), so the skill adds what the session can see
  in its own context: nothing listed is wrong, and something may be missing. The first probe starts the user's MCP
  servers and runs their session hooks once, as starting Claude Code there does. In a development checkout `check`
  refuses: its hooks would trace the probes.

## The watcher

The session the user starts the skill in is the run's watcher: one session, on Opus 5.5 at high effort, that does
none of the work. It starts the sessions that do, in order, each on the model and effort the user set on 2026-11-16,
keeps the user informed, and judges what a script can't. [`watch.py`](tools/watch.py) is its tool.

```bash
python3 llm-dlc/tools/watch.py stage evaluate "PROMPT"        # stage 2, in the fixed session
python3 llm-dlc/tools/watch.py stage setup "PROMPT"           # stage 3, in a new session
python3 llm-dlc/tools/watch.py preflight NNN ...              # examples named by number: what to set up, what each lacks
python3 llm-dlc/tools/watch.py claims NNN ...                 # what each example claims, for the user to confirm
python3 llm-dlc/tools/watch.py verification start|stop|status # the verification loop, on Sonnet 5.5
python3 llm-dlc/tools/watch.py loop --memory SIZE NNN ...     # stage 4: the proof loop, detached, in the fixed session
python3 llm-dlc/tools/watch.py wait                           # block until there is something for the watcher
python3 llm-dlc/tools/watch.py status                         # where everything stands, for a question about the run
```

- **The fixed session** is the one that evaluates the changes (stage 2, at medium effort) and then proves them
  (stage 4, at high effort): the loop continues it, so the session that proves is the one that planned. Its id is in
  the run's state (`watch.py session`), and a run that proves what an earlier `--scaffold-only` run prepared
  continues the same one. The sessions of stages 1 and 3 are new each time.
- **A stage** is a `claude -p` of its own, started in the checkout, clean in a runtime checkout
  ([what Claude Code has loaded](#what-claude-code-has-loaded)) and traced like any session in a development one. It
  can't ask the user anything: what it can't settle it reports, the watcher asks, and the answer goes back with
  another call of the same stage. Its stream is kept in the run's state (`stage-NAME.jsonl`). In a checkout Claude
  Code has never been opened in, a headless session ignores the allow list of the checkout's settings and says so
  on its first line (seen with Claude Code 2.1.325 on 2026-11-16); it runs in auto mode either way, as the loop's
  sessions do.
- **The verification loop** runs the [jobs](../verification/README.md) the sessions queue, on Sonnet 5.5. The
  watcher starts it before stage 2, since setting an example up already queues work, and stops it once the run has
  ended and the queue is clear. One per repository is enough: `start` leaves a running one alone. The three work
  the queue together, and none waits out an interval: the commit that queues a job announces it, a runner at work
  starts it beside the jobs already running, each result is collected when its job ends, and `watch.py wait`
  announces a job nobody did and starts a verification loop again if none is running while jobs wait (unless the
  watcher stopped it). [`verification/README.md`](../verification/README.md#for-the-agent-managing-the-pipeline) has the
  details; the intervals stay as the backup.
- **The run's state** is in `llm-dlc/loop-summaries/prove-change/` (gitignored): `watch.json` (the fixed session,
  the stages, the last summary), `plan.md`, the stages' streams, and [the loop's own files](#the-proof-loop).

### Stage 2: evaluate and order them, and design or review their claims

For the session `watch.py stage evaluate` starts, on every run. You are given the user's request (changes, each with
what to prove about it, or examples by number with `watch.py preflight`'s output) and the machine's assessment
(`doctor.py`'s output). You evaluate, design and plan; you set nothing up, and you don't start proving. You are also
the session that will prove these examples, in stage 4: what you learn here is where that proof starts from.

Deciding what must be proved is the hardest part of a run and the one that costs most when it is wrong, so it is
done here, by the session that proves, and not left to the setup: the setup produces the artifacts and the evidence
your plan asks for.

1. **The machine.** Say whether it is enough for these examples, what limits it, and what budget follows.
2. **What is already there.** `python3 llm-dlc/tools/changes.py` lists the examples the checkout holds, with the
   change each came from. A change of the request that has one, `prepared` or `decided`, keeps it. Each example
   is one of three to you:
   - **reused** (preflight's `reviewed`): its claims are the ones an accepted review covered, unchanged since. Read
     its page and notes for the order and your own bearings, and don't review its claims again;
   - **reviewed** (`toReview`, prepared): its claims exist and are new or changed since a review. Read them against
     the example's own pages, its advisory and its code, and remark where one misstates what the pages say
     (`misstates`, which the setup corrects as you state it) or where something is missing or too narrow
     (`suggestion`, which is the user's);
   - **designed** (a catalog entry, or a change with no example): nothing states its claims yet. Design them.
3. **Each change.** Its two revisions as exact commits on github.com, what it is meant to change and what it must
   keep. Read the code. A change that is not on GitHub is set aside, not worked around
   ([GitHub only](#prove-java-change)).
4. **Its size.** The closest past examples and what they cost (`examples/tools/find.py`, their notes and receipts,
   `pipeline.py report`), set against the budget: whether a proof is plausible here and what will be hard.
5. **Its claims,** for each example you design, settled in full: the property; the preservation boundary (what the
   change may alter and what it must keep); the bounds that make the claims meaningful, with why each is enough; the
   controls the claims need (inputs that must hold, inputs that must fail, and the constructed mutant that must fail
   the claim); the entry point (the method, an adapter if the route can't enter it, and how inputs are built), with
   which of route, adapter or gap you expect ([how a proof is invoked](#stage-3-set-the-examples-up)); and every
   assumption about the environment (locale, JDK, configuration, the code around the entry). Where the entry's
   summary or advisory leaves the claim open, take the narrowest reading and say so. Write each claim file as
   [`target-claim.schema.json`](../examples/schema/target-claim.schema.json) says, and each task as the sidecar's
   tasks: the setup writes them as they are. Stage 4 may not change a claim to fit a result, so a claim you are not
   sure of is an open question for the user, not a guess.
6. **The order,** the most accessible first: a proof that lands early can extend the verifier under the later ones,
   and a hard one first can use up the run.
7. **The plan.** Fill in [`prove-plan-template.md`](prove-plan-template.md) as
   `llm-dlc/loop-summaries/prove-change/plan.md`, with the next free numbers from 900 for new changes, in that order,
   and write its data as `plan.json` beside it ([`prove-plan.schema.json`](prove-plan.schema.json)): for each example
   whether its claims were designed, reviewed or reused, the designed claims and tasks, your remarks, the controls,
   the entry, the preparation recipe, the validation commands and when the setup is done. Check it with
   `python3 llm-dlc/tools/watch.py plan --check`, and reply with the plan. Commit nothing.

### Stage 3: set the examples up

For the session `watch.py stage setup` starts. You are given the plan. You turn each of its examples into a prepared
one, in the plan's order and under the plan's numbers, as [`examples/README.md`](../examples/README.md#add-an-example)
describes for a real-world example ([285](../examples/285-spring-boot-cve-2023-34055-unbounded-http-method-labels/README.md)
is a worked one, and what the [example-targets loop](loops/example-targets.md) did for 285 to 300 is the model):

1. **The claims, from the plan.** `python3 examples/tools/scaffold_example.py NNN` writes the claim files and the
   tasks `plan.json` designed for the example, checks them against their schemas, and says what is left for you.
   Write no claim of your own, and change none: one that doesn't work as the plan says goes into your report.
2. `example.json` and its target sidecar, filled in from the plan: the source, each revision by its full commit and
   how it is prepared, the controls. Its `provenance` is the change's part of the request as the user gave it, and
   its notes hold what the plan learned and why the change sits where it does in the order.
3. The revisions prepared: their JARs fetched or built, pinned and locked (`build.py --plan NNN`), as the plan's
   preparation recipe says.
4. The change run once on a JVM (the replay task), with the plan's controls, and the mutant's replay.
5. **How each proof task is invoked,** confirmed without attempting the proof and recorded on the task as
   `invocation` ([`target.schema.json`](../examples/schema/target.schema.json)), with the date and what showed it:
   - `route`: the task plans (`build.py --plan NNN --task T`), its target method resolves in the prepared JARs,
     and the claim's expressions compile;
   - `adapter`: the route can't enter the claim (an adapter entry, two dependency closures), and an adapter or
     driver of the example's own compiles against each revision and has run once through the claim's entry;
   - `gap`: neither can be given the task yet. Record the missing capability as an observed blocker of the task
     in the handoff, with the probe that showed it, and as an engineering task in `handoff.next`; the claim stays
     as it is.
6. Each example checked with `python3 examples/tools/validate_example.py --replay NNN`, not the default run
   ([tests in a run](#the-proof-loop)), and committed by itself.

It is done when `changes.py` calls each example `prepared` and `watch.py preflight` doesn't name it in
`toClassify`. You decide nothing the plan left open and change no claim: what does not work as the plan says (a
revision that won't build, a replay that shows something else, an entry that can't be invoked as planned) goes into
your report as a question, with what you found.

### Examples named by number

A request may name examples by number in place of changes: ones an earlier `--scaffold-only` run, another agent or a
person prepared, and catalog entries, which have their revisions pinned and nothing else (examples 288 to 300 are
such). They go through [stage 2](#stage-2-evaluate-and-order-them-and-design-or-review-their-claims) like changes
do: what tells the review apart is whether an example's claims were reviewed, not how the request named it. The
watcher checks them first, and the loop starts on none until the check passes:

```bash
python3 llm-dlc/tools/watch.py preflight NNN [NNN ...]
```

It is a cursory check, from the files alone, and prints for each example what it lacks, by kind:

| Kind | What is checked | For instance | The watcher |
|---|---|---|---|
| `absent` | There is an example of that number | no folder `950-…` | aborts at once: nothing says what it would be |
| `artifacts` | What a proof needs is there: each revision materializes from its lock, and the change has run once on a JVM | no receipt binds a revision to prepared artifacts; no validated replay | one repair, else aborts |
| `form` | The example is formed correctly: `example.json` validates against its schema, the target sidecar loads, every proof task has its claim frozen, and its tasks include a proof task | a sidecar that is not JSON; a claim not frozen | one repair, else aborts |
| `catalogue` | The example is more than a catalog entry: its sidecar has tasks | `"tasks": []` | has it set up; one that fails is left out |

Beside the kinds it says, for each example, whether its claims were reviewed (`review`: `reviewed` when they are the
ones an accepted review covered, by their files' hashes kept beside the decision record; `changed`, `new` or
`catalogued` otherwise) and which proof tasks don't record how they are invoked (`invocation`). Its lists are
`toSetUp`, `toRepair`, `toReview`, `reviewed`, `toClassify`, `leftOut`, `toProve` and `decided`.

The watcher acts in this order:

1. **`absent` (exit 2):** it aborts, naming the example.
2. **Stage 2** for every example named, with the check's output: it designs the claims of the catalog entries,
   reviews those of `toReview`, keeps the review of `reviewed`, and orders them all. Its plan's order is the order
   from here on.
3. **The claims, once.** The watcher shows the user what stage 2 designed or remarked on before anything is set up,
   all in one list (`watch.py claims NNN ...` for claims already in an example: each claim in its file's own words,
   its bounds and assumptions, and the answer expected on each revision; the plan's own words for designed ones),
   and asks for their word once. A correction goes back to stage 2, and an example the user turns down is left out.
   With `--unattended` the watcher reads the claims in the user's place. It still prints the list. For an example
   whose claims say what its entry's summary and advisory say, and no more, it accepts them once they are in the
   example (`watch.py claims NNN --accept "REASON"`): a decision in the run's record, flagged because proving the
   wrong claim costs the loop's hours, which the user reviews afterwards (`decisions.py review`). A `misstates`
   remark goes to the setup with the plan; a `suggestion` is named in the report, and the example goes on as it
   stands. An example whose claims it is not sure of is left out of the loop and named in the report, with its
   claims: that one waits for the user. Either way the acceptance keeps the claim files' hashes, so a later run
   reuses the review while they are unchanged.
4. **`toSetUp`:** a catalog entry is not a fault. The watcher has every one set up before its proof starts, one
   setup session for each, one after another in the plan's order, each with the catalog entry's brief below. Then it
   checks again with `--after-setup NNN,NNN`, naming them: an entry that is still not prepared is in `leftOut` and
   no longer counts against the others. The watcher says which was left out and why, and goes on without it.
5. **`toRepair` and `toClassify`:** a prepared example that lacks something is a fault, and one that doesn't record
   how a proof task is invoked lacks the setup's last deliverable. The watcher makes one attempt to put them right:
   a setup session (`watch.py stage setup`, Opus 5.5 at high effort) given the check's output, the plan and the
   repair's brief below. Then it checks again, and if `toRepair` still names anything it aborts: it says which
   example lacks what, and starts nothing. One still in `toClassify` goes on, and the report names it.
6. **Exit 0:** nothing is lacking. The loop takes `toProve`, in the plan's order; an example already `decided` is
   left out, and the watcher says so. An example without a target sidecar (a constructed one) passes with a note:
   only its `example.json` was checked.

With `--scaffold-only` the skill ends after step 5.

**A catalog entry's brief,** for the session `watch.py stage setup` starts with one entry's number and the plan. You
set that one example up as [stage 3](#stage-3-set-the-examples-up) does, from the plan's entry for it: stage 2 has
designed its claims, its controls and its entry, and you write them with `scaffold_example.py`, then make the
artifacts and the evidence they need. The entry itself (its `example.json`, its sidecar with the revisions already
pinned and the hand-off's blockers, which are predictions, not findings, and its README) is your source for the
rest. Examples [285](../examples/285-spring-boot-cve-2023-34055-unbounded-http-method-labels/README.md) to 289 were
entries like it and are the model.

1. Write the claims and tasks (`scaffold_example.py NNN`). Prepare the revisions (`build.py --plan NNN`), write the
   driver and the oracle, and run the change once on a JVM: the replay task on the release pair, and the plan's
   mutant with its own replay. A replay task runs inline; a preparation that takes more than a minute or 1 GB (a
   revision's own build, for one) is queued as a job (`pipeline.py submit --example NNN --task T`), and you wait for
   its result before going on, since the verification loop is running.
2. Confirm and record how each proof task is invoked (stage 3, step 5).
3. Prove nothing. A probe that shows where the verifier stops belongs to the proof loop; the one that confirms an
   entry can be invoked is yours.
4. Done when `changes.py NNN` calls the example `prepared` and preflight's `toClassify` doesn't name it. Check it
   with `python3 examples/tools/validate_example.py --replay NNN` (it regenerates the router first, then checks the
   form, the plans, the oracle and the replays, and runs the tests that read every example; they find a prepared
   example by themselves, so add it to no test's list), not the default run, commit it by itself, and reply with
   each claim in a sentence, how each proof task is invoked, and anything that did not work as the plan or the entry
   predicted. An entry that can't be set up (a revision that does not build, a change no replay shows) is left as it
   was, with the reason in its notes and in your reply.

**The repair's brief,** for the session `watch.py stage setup` starts with a check's output and the plan. You put
right what the check names, in the examples it names, and nothing else:

1. A missing artifact is made from the example's own files: its revisions prepared again from their lock
   (`build.py --plan NNN`), its replay run again. A revision that no longer builds or a replay that now shows
   something else is not repaired by changing the example: report it.
2. A fault in the form is corrected where the example's own files say what is meant: a field renamed to what the
   schema asks, a path that moved, a claim file a task names and the folder holds under another name.
3. A claim is the user's. Correct one only where the plan's remark says it misstates the example's own pages, as
   the remark states it, and list every claim you changed in your report. Where a proof task or its claim is
   missing and the plan doesn't design it, write none and report that.
4. A proof task with no `invocation`: confirm and record it, as stage 3's step 5 says.
5. Check each example you changed with `validate_example.py --replay NNN`, commit it by itself, and reply with what
   you did, what you could not, and why.

### Watching the loop

`watch.py wait` blocks until one of five things, prints it, and is run again:

| It prints | What the watcher does |
|---|---|
| A summary | Prints it as it is. One comes every 30 minutes (`--summary-interval SECONDS` in the request, or `watch.py interval SECONDS` at any time, changes that; the number is kept for later runs in the same checkout), from [`watch-summary-template.md`](watch-summary-template.md): what changed since the last one first, then the loop (the cycle, how long it has run, the session's tool calls and its last output), the examples (done, waiting on a proof, not started), the example under way (its claims by answer), the verification jobs, and what needs attention |
| A question of the loop's | Judges it and answers with the `conductor.py decide` line printed beside it. The three questions are below |
| A proof that has come in | Tells the user. The loop takes the example up again by itself when it next changes example |
| The loop's end | Reports (the skill's last step), and stops the verification loop once the queue is clear |
| A verification loop it started (`"kind": "verification"`) | Tells the user: none was running while jobs waited, and `wait` has started one. Nothing else to do |

**After each cycle** the loop asks whether the example is done (`cycle`, five minutes to answer). `wait` prints the
example's state beside the question: its claims by answer, which of those answers were given beside the route
(`besideRoute`), which open claims stop at an observed gap of the verifier (`blocked`), its jobs not in yet, and
the example's own words on its outcome (its verdict label and its hand-off). The answers are
[`changes.py`](#many-changes-and-preparing-without-proving)'s: the route's receipts, and answers given beside the
route that a passed job confirms. A session that has just decided a claim beside the route and not yet recorded it
in the sidecar shows as open: the cycle's report says so, and the watcher answers `continue` so the next cycle
records it. An example whose open claims all stop at an observed gap is the judgement this question exists for:
`finished` when closing the gap is more than this run should take on, `continue` when the session is closing it.

- `finished`: every claim has its answer, or what is left needs a person.
- `continue`: the session can still make real progress on it. It gets another cycle, with the same instruction.
- `waiting`: all that is left is to act on the results of verification jobs that are still out, typically the final
  proof. See below.

**Between two examples** the loop asks whether to go on (`example`, two minutes, or two hours while a workspace is
queued to merge). This is the one point where the checkout is still: the session is idle and compacted, and the loop
runs from a private copy of its scripts, so a merge can't pull them from under it.

- The user asks for a merge at any time, and the watcher queues it: `watch.py merge add NAME`. At this question the
  watcher merges each queued workspace into the loop's line, in the loop's checkout: a merge commit of the line's
  tip and the workspace's (`jj new @- NAME@-`), its conflicts resolved, `python3 llm-dlc/tools/sync.py regenerate`
  in a development checkout, the default tests run, the merge committed, then `watch.py merge done NAME`. A merge
  that does not come out clean is undone (`jj abandon`), left queued, and reported to the user.
- The user asks to stop after the example under way at any time: `watch.py stop-after example` (`cycle` ends it
  sooner, `never` takes it back). The loop then ends by itself at this point. The watcher answers `stop` here only
  for what the user asked since, and otherwise `continue`.

**An example that waits on its proof.** By default the loop does not sit idle while an example's last proof runs:
on `waiting` it leaves the example and takes the next one. The watcher starts `watch.py proof NNN` as a background
task of its own, a shell that does nothing but wait for that example's jobs, so it and the user hear when the proof
is in. Whenever the loop leaves an example, it first goes back to the earliest waiting one whose jobs are in, for a
cycle that acts on the result, and only then starts a new one; when only waiting examples are left it waits for the
first to come in. `--wait-for-proofs` in the request turns this off: the example keeps the loop while its jobs run.

**A compaction with no commit** is [the conductor's](#the-conductor) first question, unchanged.

**No answer** never stops the work: a judge of the loop's own answers the cycle question, and the other two default
to going on. So a watcher that is busy, or gone, costs minutes, not the run.

**Every answer is also a decision the user can review.** `conductor.py decide` adds it to the run's decision
record, [`llm-dlc/decisions/`](decisions/)`prove-change.jsonl` (`local-prove-change` in a runtime checkout, so a
user's record never meets one a release carries), with the question, the answers it could have been, the watcher's
reason, and how it is taken back. The user reads them with `python3 llm-dlc/tools/decisions.py list`, and accepts
or overturns one with `decisions.py review`. The loop does not read the record: an overturned verdict is the user's
word to the watcher, whose next summary names it under what needs attention. The watcher then acts as the entry's
undo line says and records what it did as the decision that supersedes it (`decisions.py record`). It adds
`--confidence medium` to an answer it is not sure of, which flags it for review, and puts to the user a question it
is less sure of than that. The record is committed with the run's other changes.

### What the watcher may fix

The user can ask the watcher about any part of the run: `watch.py status` has the loop, the examples and the queue
in one place, the stages' and the loop's streams are in the run's state, and `pipeline.py status` and `report` have
the jobs. The watcher fixes what is small and says what it did:

- a verification job that runs away. The runner stops a step that has stalled by itself; one that is still busy
  far past its estimate runs in a scope of its own (`systemctl --user list-units 'vjob-*'`), which
  `systemctl --user stop` ends, and the runner records the step as failed. `pipeline.py resubmit` queues it again
  with other resources, if that is what it needs ([`verification/README.md`](../verification/README.md));
- a verification loop that died: `watch.py wait` starts one again by itself while jobs wait, and
  `watch.py verification start` does it by hand;
- a job that is queued and not starting: `watch.py verification nudge` has the runner, or the waiting loop, look
  at the queue at once;
- a loop that ended on a cycle with no commit: read why in its record, and start it again on what is left
  (`changes.py --pending`), the example it stopped on last, unless what stopped it would stop the others too;
- a lock or a scope a killed run left behind.

It does not write into the loop's session, change a claim, or decide what is the user's. A session that has written
nothing for twenty minutes is flagged in the summary; it is usually a long command, so the watcher looks before it
acts.

## The proof loop

```bash
llm-dlc/tools/prove-loop.sh --session SESSION --memory SIZE [--instruction TEXT] [--record-as NAME] [--wait-for-proofs] [--no-isolation] NNN [NNN ...]
```

[`prove-loop.sh`](tools/prove-loop.sh) runs [`feature-loop.sh`](tools/feature-loop.sh)'s `prove-change` moonshot over
the examples it is given: "Formally prove example NNN as elegantly and efficiently as possible", on Fable 5.2 at high
effort, the instruction and nothing else. `--instruction TEXT` gives it the user's text in place of that line:
one line, with `{}` where the example's number goes, and still the only thing the session is given (the run's
record keeps it, and the loop statistics tell its cycles by the words before `{}`, so fewer than 16 characters
there leaves the run unmeasured). It works the same in both modes, and the watcher starts it
(`watch.py loop`). Every moonshot over examples is run this way: `prove-examples`, the list 285 to 300 that
`feature-loop.sh` still names, is this loop given those numbers.

- **The session.** With `--session` the loop continues a session that exists: the fixed one, which evaluated the
  changes. With `--fork` it starts as a fork of a session, made in one turn without tools and then compacted, and
  with neither it starts a fresh one.
- **An example keeps the loop** for as many cycles as it takes. After each commit the watcher says whether it is
  finished, goes on, or waits on its proof ([watching the loop](#watching-the-loop)); `--cycles N` caps the run.
  A cycle that makes no commit ends the run, as in every loop.
- **The order** is the order of its arguments, with a waiting example taken up again as its proof comes in. Every
  example it is given is worked on, decided or not: `changes.py --pending` gives the ones still to prove.
- **Tests.** No session of a run runs the default test run before each commit: it takes about 16 minutes, and a
  cycle commits often. A commit is checked by what it changed: `examples/tools/validate_example.py NNN` for an
  example's own files, and the tests of any shared code it touched. The default run comes once an example is done
  and before anything is published, and what it finds is fixed then ([`CLAUDE.md`](../CLAUDE.md#tests)).
- **The jobs.** The proof queues its long runs as [verification jobs](../verification/README.md), as everything here
  does. The watcher's verification loop runs them; started by hand, `prove-loop.sh` starts one itself unless one
  already runs for this repository.
- **Clean sessions.** In a runtime checkout every session of the loop starts with this checkout only, and none of
  the user's own Claude Code setup ([what Claude Code has loaded](#what-claude-code-has-loaded)); `--no-isolation`
  starts them as a plain `claude`.
- **The cap.** The loop runs in a systemd scope with a memory cap (`--memory`; `doctor.py`'s budget proposes one). On
  a machine without systemd user scopes it refuses to start unless `FEATURE_LOOP_UNCAPPED=1` says to run with none.
- **The run's state** is in `llm-dlc/loop-summaries/prove-change/` (gitignored): `run.json` (the session, the
  examples, the process, how it ended), `events.jsonl` (where the loop is and what it asks), `commands` and
  `merge-queue` (what the watcher leaves for it), and its output (`loop.log`). The run's record is beside it, as for
  every loop. One run at a time in a checkout.

### The conductor

This conductor is a moonshot's: the session outside one loop. The conductor of a parallel run of streams
([`loops/stream-conductor.md`](loops/stream-conductor.md): inboxes, the integration line, the decision record) is
another thing with the same name, and its brief's own design of a moonshot conductor (its Design 7) is what this
section is. The two share the decision record: this conductor's verdicts are decisions in it.

[`conductor.py`](tools/conductor.py) is how the loop and the session outside it talk: the loop appends an event to
`events.jsonl` and waits for a verdict file, and the watcher answers with `decide`. The watcher never writes to the
loop's session, whose instruction stays the one line. Any moonshot run with `LOOP_CONDUCTOR` set has one; the proof
loop's is the watcher.

| Question | When | Answers | With no answer in time |
|---|---|---|---|
| `compaction` | The session compacted itself (at 600k tokens) with no commit since the cycle began, or since the last compaction | `continue`, `stop` | The turn goes on (15 minutes, `FEATURE_LOOP_CONDUCTOR_WAIT`); with `FEATURE_LOOP_STOP_ON_COMPACT=1` it stops |
| `cycle` | A cycle has committed | `finished`, `continue`, `waiting` | A judge of the loop's own answers, on Sonnet 5.5, from the cycle's report and commits (5 minutes, `FEATURE_LOOP_JUDGE_WAIT`) |
| `example` | The loop is leaving an example and another is left | `continue`, `stop` | It goes on (2 minutes, `FEATURE_LOOP_EXAMPLE_WAIT`; 2 hours while a merge is queued, `FEATURE_LOOP_MERGE_WAIT`) |

A moonshot has no acceptance criteria, so its context window is its measure, and a compaction with no commit is
where the work is either hard and going well or stuck. A rule can't tell which, and a rule that stopped there
stopped good work, so the loop asks. The conductor judges from outside: the loop's transcript, which the event
names, the commits and the working copy's diff, the jobs, and whether the same failure or file keeps coming back.
`continue` lets the turn run to its next compaction, where the question is asked again if there is still no commit;
`stop` ends the turn and the loop. Lean towards `continue` while the work is moving: an example left unfinished is
fine, since a later run can return to it, and a stop costs a person's attention.

The verdicts and their reasons go into the run's record under the cycle's line, and, for a run directory in a
checkout, into [the decision record](#watching-the-loop) as well. `conductor.py command` leaves the
loop a line as if it were typed in its terminal (`stop`, `item`, a count), which is how `watch.py stop-after` works.

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
