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
| [`records.py`](records.py) | reads the committed records by id, from a git revision or from a working copy; computes the result indexes from the receipts, for `collect` to write and for the audit to compare |
| [`audit.py`](audit.py) | the reconciliation: a read-only join of specifications, receipts, indexes and the runner's state |
| [`test_audit.py`](test_audit.py) | tests both, on a made-up corpus with one fault at a time and on the corpus of the pinned revision |
| [`attempts.py`](attempts.py) | the record and the folders every execution of a job gets before its first byte; [`test_attempts.py`](test_attempts.py) tests it, and [`verification/test_capture.py`](../verification/test_capture.py) what the runner, `prune` and `recover` do with it |
| [`fixtures/`](fixtures) | the census and the manifest of the corpus at `b52a084f5d11`, the revision the migration started from |

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
