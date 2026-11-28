# Let the build tool fetch what it needs, once, through a door the machine controls

**Implementation brief for `pilifs/in-the-loop` · drafted November 28, 2026, for the user to review and queue**
Written by the agent of the run it follows (`generic-jobs-pipeline`), after that line landed and four of its
review findings were fixed. Its record is
[`in-the-loop-generic-jobs-pipeline-brief-results.md`](in-the-loop-generic-jobs-pipeline-brief-results.md);
the operator's page is [`jobs/README.md`](../../jobs/README.md). Nothing here is queued: a person queues it.

## Outcome

A job that lacks inputs asks once, and its resolution starts the build tool **twice**: once with the network
reachable only through a repository door that admits the sources this machine allows, and once with no network
at all, to prove that what came through the door suffices. Today the same resolution starts the tool once for
every level of the dependency graph the cache lacks, and cannot finish at all for a Maven plugin's closure.

Deliver that fetch phase, show it on the two real cases that the rounds handle badly, run the S batch's setup
control on all 47 offline cases with it, and close the review findings that are still open on the jobs line.

## What the measurements say

Delayed setup works, and its cost is in the wrong place. From the jobs of 2026-11-28
([results, *Gate 4*](in-the-loop-generic-jobs-pipeline-brief-results.md#gate-4-what-has-been-measured)):

| Case | Rounds until ready | Where the time went |
|---|---|---|
| S48, Maven WAR (job `20261128-134250-…`) | 2 | 61 s in the round that failed, 262 s in the one that ran through; 2 files fetched in 0.9 s |
| S11, one Gradle graph of 53 missing modules | 11 | 867 s of 1,028 s in ten rounds that failed; 120 files fetched in 1.2 s |
| Eight S cases, four at a time (job `20261128-023835-…`) | 1, 6, 6, 6, 6, 11, 11, 13 (60 in all) | 5,858.7 s in rounds that failed, 1,001.9 s in rounds that ran through, 1,772.0 s in the eight jobs; 676 files fetched in 4.8 s, 296 of them reused |

Fetching is 0.1 to 0.2 % of a resolution. A failed round is a whole tool start that names one level of the
graph, because an offline Gradle stops at the first configuration it cannot resolve. Maven is worse: it names
one artifact a failure. That is why S48's gate passes only with a **copy** of 770 files of a Maven plugin's
closure, declared under the operation's `reads` and verified by its digest
(`~/.cache/in-the-loop/readiness-gates/s48-home-m2`, `6780dd401eda…`): no resolution fetched them, and by
rounds it would take some hundred Maven starts.

## 1. A repository door, and a fetch run behind it

**The door.** A small repository proxy that the pipeline starts for one resolution, listening on loopback. The
build tool is pointed at it in place of its repositories; the door asks the operation's repositories in their
order, under the rule the fetcher already has (`readiness.authorise`: the allowed folders of
`fetch_allow` and of the grants in `fetch-sources.json`, every redirect checked), verifies each file by the
repository's checksum, keeps it in the runner's pool, lays it in the staging folder in Maven's layout, and
records it as the resolver records a fetch today (source, bytes, seconds, `verifiedBy`, `reused`). A file with
no checksum is served to the tool and marked `unverifiable`, and what is unverifiable is never published.
A request outside the allowed sources is refused, recorded with its URL, and shows where an unauthorised
source shows now (`receipt.asked`, `pipeline.py sources`).

**The fetch run.** The task's own steps, in the clean sandbox it has today (an empty home and `/tmp`, the base
and the declared `reads` read-only), with one difference: a network namespace in which the door is the only
thing that answers. Today a resolution job's step has the host's network, and what restricts it is the
fetcher's own rule; behind the door the restriction is a boundary of the machine's. A probe inside the sandbox
must show it, as the offline probe does: loopback alone, and a direct connection to a repository's address
fails.

**Pointing the tool at the door** is the part that differs by tool, and the operation says which applies:

- Maven: a `settings.xml` in the run's empty home with a mirror of everything on the door. The same file serves
  a Maven that another build starts (Spring Boot's Gradle build runs Maven for its plugin's descriptor: S48).
- Gradle: an init script that sends every repository of the build, its settings and its plugin management to the
  door. The view's existing init script (`ITL_READINESS_GRADLE_INIT`) is the model, and its known limits are
  review finding R8.
- A tool distribution or another single file stays a pinned input with its digest.

**Then the proof, unchanged.** The staging folder becomes the view's bundle and the task runs offline, as a round
does today. Ready means what it means now: the task ran through with no network on the base and the bundle, and
left its declared outputs. If the offline run still lacks something (a file the online run took from a place the
door does not see), the resolution goes on in rounds from there, so the fetch run can only save starts, never
decide readiness. A receipt says which phase fetched each file.

**Where the bundle is laid for the proof.** S48's Maven reads `$HOME/.m2/repository`, which today a step fills
with `cp -a` from the copy. An operation needs a way to say that part of the bundle is laid at a path of the
task's home (`layout.home`, say), so that the offline run and the consumer's steps find it without a copy step
of their own.

## 2. Requests to outside: decide before the run starts

A fetch run asks a repository for everything the build resolves: hundreds of files for a real graph (S48's
closure is 770). [`operating-notes.md`](../operating-notes.md#requests-to-the-web-are-plain-few-and-one-at-a-time)
holds agents to plain, few requests, one at a time, and names "no bulk downloads, no mirroring". A build tool
resolving its dependencies in a setup job is the repository's ordinary practice, and the note was written for
research; a resolution's door sits between the two. **This is the user's to settle before the run**, and the
brief proposes:

- The door asks upstream one request at a time, with a second between two requests to one host, under a plain
  User-Agent that names the tool, and retries a 429 or 503 once after its `Retry-After`.
- A file is asked for once on a machine: the pool answers every later resolution.
- Every test and both controls run against a repository on loopback or a folder (the S control's mirror of the
  retained cache is one). Only S48's gate asks Maven Central, for what its build resolves, once.
- An operation may cap the files and bytes a fetch run may bring (`fetch.maxFiles`, `fetch.maxBytes`), and the
  runner's settings give the default.

If the user decides otherwise, gate 2 below is run from a folder made of the existing copy and says so.

## 3. Findings to retain

| Finding | Control | What this work must keep |
|---|---|---|
| [VF-076](../../verification/findings.md): gaps found one failed job at a time | S48, and the eight-case control | One request a case. No consumer job fails for want of an input the resolution could have fetched |
| [VF-070](../../verification/findings.md): 98 dry runs configured, 41 of 49 first jobs failed for setup reasons, 38 on offline misses; steps passed with no test | The S control on all 47 offline cases | Readiness at the level asked for (`tests-run` needs evidence of tests). A transplant that fails, an absent historical input and a case that needs the network at test time stay what they are |
| S48's pass of the third cycle read `~/.m2` unsaid | The clean sandbox, and the control that names another digest | The fetch run and the proof both run in the clean sandbox. Nothing under the runner's home is read unless the operation declares it |
| The control's first run passed with every case withheld | `gate.py`'s check that a case came ready and ran | Every gate has a check that fails when nothing was exercised |
| A fetch outside the allowed folders | `unauthorized-source`, `pipeline.py sources` | The door refuses it, the receipt names it, and only a person allows a source |

## 4. The review's open findings

The review of 2026-11-28 has these still open
([table](in-the-loop-generic-jobs-pipeline-brief-results.md#the-review-of-2026-11-28-what-three-fresh-readers-found)).
Each gets a test that fails before its fix. In the order an unattended run meets them:

- **C6's last part**: after `resolve` skips a request, does the keeper go on to start the runner for the other
  jobs? **C9**: a runner stopped during preparation or between steps records `error` or `failed`, not
  `cancelled`, so the job never runs again and its dependents are blocked. **C14**: `keep_workdirs = "always"`
  is undone by a collect's own prune.
- **B13**: fetch slots are held for the whole job, the schema says for the fetch step, and no test names
  `fetch_slots`. With the door, a slot is a fetch run, which is the thing worth counting.
- **B14**: two schema files cover about twenty versioned documents. The view, the batch map, the operation, the
  receipt, the collect and wait reports and `itl-fetch-sources/v1` have none.
- **B3, B4**: `report` shows no execution, fulfillment, conclusion or purpose and omits a job that never ran;
  `collected` does not say whether a result is committed or published (the view's `collectedNotCommitted` is a
  first part).
- **R7's redirect rule** has no test: a repository on loopback that redirects to another host gives one, and
  the door needs it.
- **B2, B5, B9, B10, B12**, and **R8, R10, R11**, as their rows say.

## 5. Sequence and gates

1. **The door and the fetch run, on fixtures.** The made-up nested build of `jobs/test_readiness.py` comes ready
   with two tool starts where it takes three rounds. A stand-in tool that names one artifact a failure, with a
   closure of twenty, comes ready with two starts where rounds would take twenty-one. Controls, each with
   nothing published: a request outside the allowed sources; a file whose checksum does not match; a direct
   connection from inside the fetch run; a fetch run that brings nothing the task needs, after which the rounds
   go on.
2. **S48 without the copy.** The operation drops its `reads` of `s48-home-m2`. One request, one resolution: the
   plugin's closure comes through the door from Maven Central, each file verified, and a fresh offline consumer
   reads the four WARs in an empty home, equal to the committed readbacks. This removes gate 3's last
   qualification. Record the files and bytes it asked Central for.
3. **The S control on all 47 offline cases** (`setup-control/gate.py --cases all`), from the mirror folder, with
   the fetch run. Report, for every case: tool starts, wall time, files, reuse, and its job's outcome beside the
   outcome of 2026-11-27. Compare with the eight-case measurement above. Give the job a memory estimate from
   that run (four jobs peaked at 21 GiB against a 24 GiB limit).
4. **The open findings**, in the order of section 4, each committed with its test.
5. **Adopt.** `jobs/README.md`, `ARCHITECTURE.md`, `CLAUDE.md` and the `/run-verification` skill move with each
   change. Update the results page of the line this continues, and VF-076 and VF-070.

## What not to do

- Do not let the fetch run decide readiness. Only the offline run does.
- Do not widen what a machine fetches from. `fetch_allow` and `sources allow` are the user's, and the door reads
  them.
- Do not intercept TLS. The tool speaks plain HTTP to loopback, and the door speaks to the repository itself.
- Do not remove the rounds: they are the fallback, and the only path for a tool the door has no adapter for.
- Do not rerun the 47 cases by rounds first. The user decided on 2026-11-28 that the full control waits for the
  fetch run, so that one run measures both.
