# One jobs pipeline: results

The record of the run on [`in-the-loop-generic-jobs-pipeline-brief.md`](in-the-loop-generic-jobs-pipeline-brief.md)
(queue entry `generic-jobs-pipeline`, 2026-11-27; Claude Fable 5.2, session `43b290ac`, in the workspace
`foundation-domain-streams`). It follows the brief's five release gates. Each row says what is in the repository,
with the commit, and what is still open. The operator's page is [`jobs/README.md`](../../jobs/README.md).

## Where the work stands

| Gate | State | What is in the repository |
|---|---|---|
| 1. Protect and measure: the census | done | `jobs/audit.py`, `jobs/records.py`, the frozen census and manifest of `b52a084f5d11` |
| 1. Protect and measure: retention on retry and prune | open | |
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
