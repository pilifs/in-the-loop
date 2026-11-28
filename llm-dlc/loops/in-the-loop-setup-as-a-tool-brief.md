# Setup as a tool: a `/run-setup` skill, an input lock, and a fetch run behind a door the machine controls

**Implementation brief for `pilifs/in-the-loop` · November 28, 2026**
This builds on [`in-the-loop-build-driven-fetch-brief.md`](in-the-loop-build-driven-fetch-brief.md), which the agent of `generic-jobs-pipeline` drafted after its line landed, and **supersedes it**. It keeps that draft's design for the fetch run whole (part B) and puts it inside a larger outcome: setup becomes a tool and a skill. It was revised with that agent on 2026-11-28, against the decisions the user took and the code built that day.
- **Read first:** that run's record, [`in-the-loop-generic-jobs-pipeline-brief-results.md`](in-the-loop-generic-jobs-pipeline-brief-results.md); the operator's page, [`jobs/README.md`](../../jobs/README.md); and [`ARCHITECTURE.md`](../../ARCHITECTURE.md).
- **The register of what was retired** is [`llm-dlc/retired.md`](../retired.md).

## Outcome

Setup is a skill, **`/run-setup`**, backed by jobs. Given a case's pins and the tasks it must run, it produces:
- a **verified input lock**;
- a **readiness receipt** for each pin and task;
- a **setup record** in the same sections every time.

Two callers use it, with the same few inputs:
- the queue's setup phase, for a batch;
- a domain agent in the middle of its proof work, for one case that needs more.

The agent's part shrinks to judgment: which build configuration to use, whether to fall back to released inputs, and whether a case is set up correctly. The recipe is no longer something an agent writes again for every batch.

The recipe is the one the setup agents have repeated since the O batch:
- bare mirrors, pins and digest or signature checks;
- resolving everything online before an offline run;
- looking for dead repositories on public mirrors;
- swapping in released JARs, matched by the git blob ids of the changed files, when a build can't be configured.

The O, P, Q and R batches' `release-inputs.json` files (for example [`verification/merged-pr-links/q01-q30/release-inputs.json`](../../verification/merged-pr-links/q01-q30/release-inputs.json)) are already input locks written by hand. A tool writes them now.

Resolution goes through a **fetch run behind a door the machine controls** (part B). The build tool starts twice: once to fetch through the door, once offline to prove what came through suffices. Today the rounds cost one tool start per level of the dependency graph, and they can't finish a Maven plugin's closure at all.

**The acceptance test is a representative sample, not the whole batch (the user, 2026-11-28).** Six S cases are set up from their pins through `/run-setup`, from empty dependency caches and a mirror built from what this machine holds. The eight cases measured on 2026-11-28 are set up again from the state the first pass left, for a direct comparison with rounds. Both resolve from mirrors on this machine. All 47 offline cases are a later run's, once this one gives confidence.

**What this machine holds comes first (the user, 2026-11-28).** "If we can avoid downloading outside stuff, we should, for efficiency and consistency."
- **In this brief:** every gate is built to run on fixtures, a repository on loopback, or a mirror made from what this machine already holds, and none depends on a request to outside. A mirror on the machine needs no permission and no setting ([`jobs/README.md`](../../jobs/README.md#setup-a-running-case-asks-for)).
- **A request to outside isn't a fault.** Where the work needs a file this machine doesn't hold, a source the user has allowed may be asked for it, through the machine's queue. It's counted in the receipt (`fetch.outside`), and the gate's report says how many files were asked for and why no local mirror served them.
- **No switch.** Nothing on the machine turns outside fetching off, and this brief builds nothing of the kind: the user decided against one on 2026-11-28, and [VF-083](../../verification/findings.md) keeps the question for a later review. What keeps a gate local is its operation, which names mirrors on this machine and no other repository.
- **Online use on purpose comes next:** the door's online path is built and tested against loopback, then exercised against a real repository for the first time in a small follow-up run that the user queues, observes and adjusts in a real-world case.
- **So the design must make that run easy to observe:** every request the door sends upstream is recorded, with its URL, source, bytes and time.

## What the measurements say

Delayed setup works, and its cost is in the wrong place. From the jobs of 2026-11-28 ([results, *Gate 4*](in-the-loop-generic-jobs-pipeline-brief-results.md#gate-4-what-has-been-measured)):

| Case | Rounds until ready | Where the time went |
|---|---|---|
| S48, Maven WAR (job `20261128-134250-…`) | 2 | 61 s in the round that failed, 262 s in the one that ran through; 2 files fetched in 0.9 s |
| S11, one Gradle graph of 53 missing modules | 11 | 867 s of 1,028 s in ten rounds that failed; 120 files fetched in 1.2 s |
| Eight S cases, four at a time (job `20261128-023835-…`) | 1, 6, 6, 6, 6, 11, 11, 13 (60 in all) | 5,858.7 s in rounds that failed, 1,001.9 s in rounds that ran through, 1,772.0 s in the eight jobs; 676 files fetched in 4.8 s, 296 of them reused |

**Fetching is 0.1 to 0.2 % of a resolution.**
- **Gradle:** a failed round is a whole tool start that names one level of the graph, because an offline Gradle stops at the first configuration it can't resolve.
- **Maven is worse:** it names one artifact per failure. That's why S48's gate passes only with a **copy** of a Maven plugin's closure (282 artifacts: 206 POMs and 76 JARs, 12.5 MiB; the folder has 770 files with their checksums and Maven's own markers), declared under the operation's `reads` and verified by its digest (`~/.cache/in-the-loop/readiness-gates/s48-home-m2`, `6780dd401eda…`). No resolution fetched those files, and by rounds it would take a hundred or so Maven starts.

**The setup the acceptance test compares against** (S batch, 2026-11-27; VF-070):
- an Opus setup agent configured 98 dry runs;
- 41 of the 49 first jobs failed for setup reasons, 38 of them on offline misses;
- several steps passed with no test run;
- setup took about five hours, against 45 to 60 minutes for a batch's verification.

## Part A. `/run-setup`: the skill and its tools

### A1. The skill

The skill is `.claude/skills/run-setup/SKILL.md`, templated like `/run-verification`: a short page of numbered steps, what the skill never does, and the commands it runs.

**What it takes,** short and the same for both callers:
- **One case:** the repository, and the revisions or the pull request link that names them.
- **The tasks:** each task to make ready (a Gradle or Maven task, or a command), with the readiness level it needs. The levels are the ones `jobs/readiness.py` has (`configures`, `resolves`, `builds`, `tests-run`, `readable`), and two matter here:
  - `builds`;
  - `tests-run`, which needs evidence that tests ran. The S batch needs this from the start.
- **Optional:** a JDK and a build-tool hint.
- **For a batch:** a manifest with one row per case, the same fields, submitted through the fan-out that exists (`jobs/pipeline.py submit --manifest`).
- **Where to resolve from:** the repositories to ask, in order, mirrors on this machine first. This is the one thing that decides whether anything is asked outside, so the skill runs the same way from a local mirror and from a remote repository, with no mode and no setting. A local mirror needs no permission; an outside source must be one the machine allows.

**A command behind it.** The skill's logic is a command with tests (`jobs/setup.py`, say), and the skill page calls it. From the inputs above it writes the pin job, the readiness operations and the manifest, and from the lock and the receipts it writes the setup record. A skill page can't be tested and its command can, so the page holds the steps and the judgment, and nothing a test should cover.

**What it does:** it never fetches, clones or builds inline. It submits jobs, waits for them (`jobs/pipeline.py wait`, as a background task), and reads their results:
1. a **pin job** (A2), which writes or extends the input lock;
2. a **resolution job** per task, which fetches through the door (part B) and proves readiness offline;
3. where a build can't be configured, the **released-input job** (A3), as the agent decides.

**What it returns:**
- the **input lock**;
- the **receipts**;
- the **setup record**, in fixed sections:
  - what was asked;
  - what is ready, at which level, by which receipt;
  - what was withheld and why;
  - the judgment calls made, and by whom;
  - what a domain agent may and may not rely on.

The record replaces the free-form "Setup Agent Notes". The proof work then always starts from the same place, and `single_run.py`'s `notes` step reads its sections.

**Who may call it:**
- **Working agents may call it.** Unlike `/orchestrate-run`, it's not the user's alone in Codex: say so in the skill's `agents/openai.yaml`, and keep `agent_client.py instructions --client codex`'s parity check passing.
- **It may submit jobs, and nothing more.** It never starts a session, a run or a model call, so the nested-run guard (VF-045) and ARCHITECTURE.md's rule ("a run's agent starts none") hold as they are.

**Mid-proof setup:** a domain agent that needs more for a case calls `/run-setup` with the case, the task and what it's missing. That becomes today's readiness request (`jobs/readiness.py`), so the agent's job waits for the receipt and resumes. The skill is the front door to the delayed setup that exists.

**What the agent still decides:** which build configuration to try; whether to fall back to released inputs and on what evidence; whether a receipt's level is enough for the claims; and when to stop and report. Each decision goes into the record with its reason.

### A2. Pin, mirror and verify: the input lock

The **pin job** writes an input lock, one schema that generalises the `release-inputs.json` files of O to R. It holds:
- **the sources:** a bare mirror of each repository in the runner's pool, each revision pinned by commit id and checked to be in the mirror.
  - **Here, offline:** the pin job takes a git mirror this machine already holds (`~/.cache/in-the-loop/git-mirrors/`, where the S batch's worktrees keep their objects). `~/.cache/in-the-loop/readiness-gates/s-setup-mirror` is something else: a mirror of dependency modules in Maven's layout, which gate 4 serves as the door's upstream.
  - **The online path** (`git clone --mirror` once per machine; a git host is an outside source like any other and must be one the machine allows) is written and tested against a repository on loopback, and is first used on purpose in the follow-up run;
- **signatures,** where a project publishes them: signed tags and commits, and the Maven `.asc` beside a published artifact.
  - **A signature that fails to verify blocks the pin.**
  - **A missing signature is recorded,** and doesn't block.
  - **A signature whose key isn't on this machine is recorded as not checked,** with the key's id, and doesn't block. No key is looked up outside: the keys are the ones a batch's setup retained (the S setup kept its own beside its cache), and adding one is the user's.
- **tool distributions:** the Gradle wrapper's distribution, a Maven distribution and the JDK, each pinned by its digest. A wrapper whose distribution the build doesn't pin is pinned here, so it no longer ends `undiagnosed`;
- **released inputs,** when A3 is used: each with its coordinates, digest and the evidence that matched it.

The lock is a committed file beside the batch (`verification/batches/` or the batch's own folder), with a schema under `jobs/schema/`. A receipt names the lock entry it used.

### A3. Released inputs, matched by blob ids

Since O and P, a setup agent has swapped in released JARs when a build can't be configured, matching them by the git blob ids of the changed files. This makes that a job:
- **The input:** a case's changed files and the candidate releases.
- **The work:** it reads each release's sources artifact and compares blob ids.
- **The result:** a released input in the lock, with the evidence of the match (which files, which blobs, which release).

The result is recorded honestly, as a released-input setup and not as a build of the revision. The setup record says which claims it can and can't support, as O and P recorded by hand.

### A4. Dead repositories and replacement mirrors

Historical builds name repositories that have moved or gone, such as old `repo.spring.io` paths. Part B's door asks the operation's repositories in order. Add a **list of replacements**, each a dead repository's URL and the mirror that stands in for it. The user approves an entry with the same person-only command that allows a source (`pipeline.py sources`), and it is kept with those grants. The door asks the replacement **instead of** the dead repository, and records which one served each file: asking the dead one first would cost a failed request for every file. An agent only proposes an entry, with its evidence: only a person adds one. A stand-in that is a mirror on this machine needs no entry at all: the operation names it, since the door asks the operation's repositories and never the ones the build file names.

### A5. The queue's setup phase uses the skill

Rewrite [`llm-dlc/loops/setup-agent-template.md`](setup-agent-template.md), and the setup page of `/orchestrate-run`, around `/run-setup`:
- the phase stays an Opus setup agent, but it calls the skill, once for a batch;
- it makes and records the judgment calls;
- it doesn't do the recipe itself.

The `notes` step then reads the setup record's sections into the brief.

## Part B. A repository door, and a fetch run behind it

This part is the earlier draft's design, unchanged in substance.

**The door.** A small repository proxy that the pipeline starts for one resolution, listening on loopback. The build tool is pointed at it in place of its repositories.
- **Where it asks:** the operation's repositories, in their order, each through its approved replacement where it has one (A4). It works under the rule the fetcher already has (`readiness.authorise`: a mirror on the machine itself with no permission; outside, the allowed folders of `fetch_allow` and of the grants in `fetch-sources.json`; every redirect checked, and none followed from outside into the machine), and every request it sends outside takes its turn in the machine's one queue (`readiness.turn`).
- **What it does with each file:**
  - verifies it by the repository's checksum;
  - keeps it in the runner's pool;
  - lays it in the staging folder in Maven's layout;
  - records it as the resolver records a fetch today (source, bytes, seconds, `verifiedBy`, `reused`).
- **A file with no checksum** is served to the tool and marked `unverifiable`, and what is unverifiable is never published.
- **A request to an outside source that isn't allowed** is refused and recorded with its URL. It shows where an unauthorised source shows now (`receipt.asked`, `pipeline.py sources`).

**The fetch run.** The task's own steps, in the clean sandbox it has today (an empty home and `/tmp`, the base and the declared `reads` read-only), with one difference: a network namespace in which the door is the only thing that answers.
- **The change:** today a resolution job's step has the host's network, and only the fetcher's own rule restricts it. Behind the door, the restriction is a boundary of the machine's.
- **The probe:** a probe inside the sandbox must show it, as the offline probe does: loopback alone, and a direct connection to a repository's address fails.

**Pointing the tool at the door** differs by tool, and the operation says which applies:
- **Maven:** a `settings.xml` in the run's empty home, with a mirror of everything on the door. The same file serves a Maven that another build starts: Spring Boot's Gradle build runs Maven for its plugin's descriptor (S48).
- **Gradle:** an init script that sends every repository of the build, its settings and its plugin management to the door. The view's existing init script (`ITL_READINESS_GRADLE_INIT`) is the model, and its known limits are review finding R8. With plugin management through the door, a plugin asked for by its id no longer ends `undiagnosed`.
- **A tool distribution or another single file** stays a pinned input with its digest, pinned by A2.

**Then the proof, unchanged.** The staging folder becomes the view's bundle, and the task runs offline, as a round does today.
- **Ready means what it means now:** the task ran through with no network on the base and the bundle, and left its declared outputs.
- **If the offline run still lacks something** (a file the online run took from a place the door doesn't see), the resolution goes on in rounds from there. So the fetch run can only save starts; it never decides readiness.
- **A receipt says which phase fetched each file.**

**Where the bundle is laid for the proof.** S48's Maven reads `$HOME/.m2/repository`, which today a step fills with `cp -a` from the copy. An operation needs a way to say that part of the bundle is laid at a path in the task's home (`layout.home`, say), so that the offline run and the consumer's steps find it without a copy step of their own.

### B1. Requests to outside: the rule that exists, and what the door adds

The rule is decided and partly built (the user, 2026-11-28): [`operating-notes.md`, *Fetches of a build's inputs go through one queue*](../operating-notes.md#fetches-of-a-builds-inputs-go-through-one-queue). A build's dependencies are what a repository is for, and the number of files isn't what is limited: the number of requests open at once is.
- **What the resolver already does** (`jobs/readiness.py`): every request to a repository outside the machine waits its turn in one queue for the whole machine, 0.2 seconds after the last one to the same host; a 429 or 503 is asked once more, after its `Retry-After`, and never a third time; a file is asked for once per machine (the pool); a resolution that asks outside for more than 1,000 files or 1 GiB **warns and isn't stopped**, in its receipt and its job's `attention`.
- **What the door must add:** its upstream requests go through that same queue and that same retry rule, whatever the build tool's own parallelism; what it asks is counted in the receipt (`fetch.outside`) and warned about by the same numbers; and it sends no header that names the user or the project.
- **Concurrency:** at most ten fetch runs at once on a machine, the ceiling the runner already has (`fetch_slots`), counted per fetch run (B13 in part C). Their upstream requests still go one at a time.
- **Local first:** every test, every control and every gate is built to run against a repository on loopback or a folder, which take no turn in the queue and aren't counted as asked of outside. The online path is exercised against a loopback "upstream" that plays the remote repository, including its 429s, 503s, redirects and checksum files. In those tests the loopback repository is made to count as outside (`fetch_local`, as `jobs/test_delayed_setup.py` does), or the queue and the count are never exercised.
- **No switch for it:** whether a resolution asks outside is decided by the repositories its operation names, and by nothing else (VF-083).

### B2. Findings to retain

| Finding | Control | What this work must keep |
|---|---|---|
| [VF-076](../../verification/findings.md): gaps found one failed job at a time | S48, and the eight-case control | One request per case. No consumer job fails for want of an input the resolution could have fetched |
| [VF-070](../../verification/findings.md): 98 dry runs configured; 41 of 49 first jobs failed for setup reasons, 38 on offline misses; steps passed with no test | The acceptance test (part D, gate 4) | Readiness at the level asked for (`tests-run` needs evidence of tests). A transplant that fails, an absent historical input, and a case that needs the network at test time stay what they are |
| [VF-072](../../verification/findings.md) item 6: setup agents built inline and split cases across forks | The acceptance test | The setup agent runs no build, clone or fetch inline: everything goes through `/run-setup`'s jobs |
| S48's pass of the third cycle read `~/.m2` without declaring it | The clean sandbox, and the control that names another digest | The fetch run and the proof both run in the clean sandbox. Nothing under the runner's home is read unless the operation declares it |
| The control's first run passed with every case withheld | `gate.py`'s check that a case came ready and ran | Every gate has a check that fails when nothing was exercised |
| A fetch from an outside source the machine hasn't allowed | `unauthorized-source`, `pipeline.py sources` | The door refuses it, the receipt names it, and only a person allows an outside source or a replacement. A mirror on the machine needs neither |

## Part C. The review's open findings on this path

The review of 2026-11-28 left these open ([table](in-the-loop-generic-jobs-pipeline-brief-results.md#the-review-of-2026-11-28-what-three-fresh-readers-found)); C3, C5, C7, R2 and the first part of C6 were fixed after the landing and aren't here. Fix the ones this work runs into. Each gets a test that fails before its fix:
- **C6, its last part:** after `resolve` skips a request, does the keeper go on to start the runner for the other jobs?
- **C9:** a runner stopped during preparation or between steps records `error` or `failed`, not `cancelled`. The job then never runs again, and its dependents are blocked.
- **C14:** a collect's own prune undoes `keep_workdirs = "always"`.
- **B13:** fetch slots are held for the whole job, while the schema says for the fetch step, and no test names `fetch_slots`. With the door, a slot is a fetch run, which is the thing worth counting.
- **R7:** the fetcher's redirect rule got its first test on 2026-11-28 (a mirror on loopback that sends the fetcher on to a host that isn't allowed is refused, with the address named). The door needs the same test of its own. The other direction, an outside source that redirects into the machine, is tested at `authorise` alone and not end to end.
- **R8:** the Gradle init script's known limits.
- **B7, its open part:** a wrapper whose distribution the build doesn't pin. A2's pin job closes it.
- **C8, its open part:** the README doesn't yet say that a Gradle step needs `--test-reports` for its tests to count.
- **The flaky test:** one of the 52 tests in `verification/test_pipeline.py` failed once in three runs, and its name wasn't captured. It hasn't failed in the runs since. Run the file some twenty times: fix it if it shows, and record that it didn't if it doesn't.

**Left for a later cleanup brief,** not this one: B2, B3, B4, B5, B9, B10, B11, B12, B14, R10 and R11 (the reporting and schema findings), and the open parts of B6, B16, R5 and R9. List them as left in the results page.

## Part D. Sequence, gates and stop points

The gates are in order. Each is committed with its tests. **The watcher may stop the run at the end of any gate**, so each gate must leave the line landable.

**The runner at work is the landed code.** The run's jobs execute on the watcher's runner, in the default checkout, which doesn't have this line's changes until it lands. What runs inside a job's own step (the resolver, the door, the fetch run) is this line's code, from the job's commit. A change to the runner itself (C9, C14, B13) is shown in a throwaway repository, as the last run's gates were.

**Review (the user, 2026-11-28).** One independent review by readers who didn't write the line, given the brief and the code and not the author's conclusions, **once, at the end**. Before gate 4, do the cheaper checks that are representative: rerun every control of gates 1 to 3 and confirm each fails when the thing it guards is taken out; and have one fresh reader go through the two things gate 4's numbers rest on, the door's verification of what it serves and the offline proof. Fix or list what they find before the gate's numbers are taken.

1. **The door and the fetch run, on fixtures.**
   - The made-up nested build of `jobs/test_readiness.py` comes ready with two tool starts, where it takes three rounds.
   - A stand-in tool that names one artifact per failure, with a closure of twenty, comes ready with two starts, where rounds would take twenty-one.
   - Controls, each with nothing published:
     - a request to an outside source that isn't allowed;
     - a file whose checksum doesn't match;
     - a direct connection from inside the fetch run;
     - a fetch run that brings nothing the task needs, after which the rounds go on.
   - With these: C9, C14, B13, R7 and the flaky test.
2. **S48 without the copy in its `reads`.** The operation drops its `reads` of `s48-home-m2`. That folder becomes instead a repository on loopback, served as the door's "upstream" in Maven's layout, each file checked against its digest. It's a Maven *local* repository, which isn't quite a remote one (its metadata files carry the repository's id in their names, and it has marker files of Maven's own): the gate says how it was served.
   - **One request, one resolution:** the plugin's closure comes through the door from that repository, each file verified.
   - **The proof:** a fresh offline consumer reads the four WARs in an empty home, equal to the committed readbacks.
   - **What it shows:** a Maven plugin's closure resolved by one fetch run through the door, which rounds can't do, with no copy step and no declared read.
   - **What it doesn't:** the bytes are still the copy made on 2026-11-28, verified by the checksums inside that copy. Gate 3's qualification changes from "a declared folder" to "resolved through the door from a local copy". It's removed only when Maven Central serves the same closure, which is the follow-up run's.
   - **Record:** the files and bytes the door served, and which it would have asked Central for.
3. **`/run-setup` and its tools.**
   - The skill (A1), the pin job and the input lock (A2), with signatures checked;
   - the setup record's sections, read by `notes`;
   - the setup template rewritten around the skill (A5);
   - C6;
   - the Codex parity check passing for a skill that working agents may call.

   **Its test:** a domain agent's mid-proof request goes through the skill for one S case, on fixtures.
4. **The acceptance test: a representative sample.** The whole batch is a later run's (the user, 2026-11-28): this gate is sized to give confidence without tying the machine up, about an hour and a half of the runner in all. Its operations name mirrors on this machine and no other repository, so it's expected to ask nothing of outside, and its report gives the count (`fetch.outside`).
   - **From the pins, six cases.** Each starts with empty dependency caches. The door's upstream is a mirror in Maven's layout built from everything the retained S cache holds (8,120 files, 2.9 GiB, 294 snapshot versions among them), and the pin job takes the git mirror this machine holds. The six, and why each:
     - **S11:** the heaviest graph measured, eleven rounds and 53 missing modules;
     - **S01:** snapshot dependencies, on which the control's first run went wrong;
     - **S46:** ready in one round, and its transplant fails as it did on 2026-11-27, which must stay a failure of the transplant;
     - **S03** and **S15:** the oldest Gradle of the batch (9.5.0) and another (9.6.1), on other modules;
     - **S16:** no build at all, set up from released inputs (A3) out of the release sets this machine holds.
   - **From the first pass's state, the eight measured cases** (S01, S02, S08, S11, S15, S25, S42, S46): the cache as the setup's first pass left it, and `s-setup-mirror` as the door's upstream, as in the control of 2026-11-28. This is the like-for-like: the same eight took 60 rounds and 5,858.7 s in rounds that failed.
   - **What is reused from 2026-11-27, and said:** the task table (`cases.tsv`: each case's modules and test classes) and the batch's init scripts. Those are the setup agent's judgment calls. The gate replays the recipe, not the judgment.
   - **A case the mirror can't serve** ends `withheld`, with what it lacks named. That list is the follow-up run's input. Don't fill it from outside to make the gate pass: the gate measures setup from what the machine holds.
   - **Report, for every case:**
     - its tool starts, wall time, files and reuse;
     - its readiness level;
     - its job's outcome, beside the outcome of 2026-11-27.
   - **Then compare:** the eight with their measurement by rounds, and the six with what the 2026-11-27 setup spent on those cases, as far as its record says.
   - **The aims:**
     - no consumer job fails for a setup reason it could have been given offline;
     - no inline build by the setup agent;
     - two tool starts per pin where rounds took six at the median.
   - **Memory:** give each resolution job its estimate from the eight-case run (four at a time peaked at 21 GiB against a 24 GiB limit).
   - **Not here:** all 47 cases, and a comparison of whole-batch wall time with the five hours of 2026-11-27. Both are a later run's.
5. **Adopt.**
   - Move `jobs/README.md`, `ARCHITECTURE.md`, `CLAUDE.md`, the `/run-verification` skill, the `/orchestrate-run` setup page and the operating notes with each change.
   - Update the results page of the line this continues, and VF-070, VF-072 and VF-076.
   - Say in `ARCHITECTURE.md` what of setup is still not built.
   - **End with a short brief for the follow-up run,** for the user to review and queue. It should name:
     - one or two real cases;
     - the sources and replacement mirrors they need;
     - what the door will ask upstream, and the ceiling above which it warns;
     - what to watch, and how to stop it.

     Start from the cases gate 4 left `withheld` for want of an input this machine didn't hold.

## What not to do

- **Readiness:** don't let the fetch run decide readiness. Only the offline run does.
- **Sources:** don't widen what a machine fetches from outside. `fetch_allow`, `sources allow` and the replacements are the user's, and the door reads them. An agent proposes and a person adds. A mirror on the machine itself needs no permission (the user, 2026-11-28).
- **TLS:** don't intercept it. The tool speaks plain HTTP to loopback, and the door speaks to the repository itself.
- **The rounds:** don't remove them. They're the fallback, and the only path for a tool the door has no adapter for.
- **The 47 cases:** don't run the whole batch here, by rounds or through the door. The acceptance test is the sample of gate 4, and the full batch is a later run's (the user, 2026-11-28).
- **Outside requests:** don't build a gate that depends on one, and don't ask outside for what a mirror on this machine can serve. A request to an allowed source for something the machine lacks isn't a fault: count it and say why. The door's first use against a real repository on purpose is the follow-up run's, which the user queues and observes.
- **A switch:** don't build a setting that turns outside fetching off. The user decided against one (VF-083).
- **Inline work:** don't let `/run-setup` or the setup agent fetch, clone or build inline. Everything goes through jobs.
- **Starting things:** don't let `/run-setup` start a session, a run or a model call. It submits jobs.
- **Released inputs:** don't count a released-input setup as a build of the revision. Say what it can support.
