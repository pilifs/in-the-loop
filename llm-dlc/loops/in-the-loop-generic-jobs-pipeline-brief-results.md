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
| 2. Switch one queue | open | |
| 3. Qualify delayed setup (S48) | open | |
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
