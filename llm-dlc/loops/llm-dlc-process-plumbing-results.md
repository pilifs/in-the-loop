# LLM-DLC process plumbing: where the run stands

The record of the single-agent run `dlc-process-plumbing` on [the brief](llm-dlc-process-plumbing.md), kept by the agent as it works. It says what is built, what was measured, what the user decided beforehand, and what is still open. The acceptance table at the end follows the brief's.

## Decisions the user took before the run (2026-11-21)

1. **`develop`.** A local bare remote first. The first push to the real `develop` waits for a cycle's end, where the watcher checks the outgoing commits and pushes; later checkpoints go out under the new command's own checks.
2. **Storage.** Two private R2 buckets, `in-the-loop-originals` and `in-the-loop-originals-restricted`, and three scoped tokens in `~/.config/in-the-loop/`. A smoke test of all three passed before the run (31 of 31).
3. **Delegated redaction** is built switched off. The user turns it on from their own terminal; until then approvals stay a person's.
4. **Work directories.** The runner keeps those of failed jobs (`keep_workdirs = "failed"`); the disk guard stays on.
5. **Records (VF-053).** No trim before the run: the run inventories and captures the records, proves that example 359 restores, then slims them by its rule.

## Sequence

| Step of the brief | State |
|---|---|
| The archive tool: spool, journal, verified upload, list and fetch (`llm-dlc/tools/artifacts.py`) | Done, cycle 1. 33 unit tests; `artifacts.py canary` passes 11 of 11 on the real buckets |
| 1. Inventory and protect the VM | Done, cycle 1: measured, heads pinned, 1,182 occurrences sealed; their upload was started the same hour (see below) |
| 2. Capture adapters in shadow mode | Runner and collector (`verification/capture.py`) and source transcripts at each `sync.py commit` (`sync.seal_transcripts`) done, cycle 1. Still to wire: example records written outside jobs, the loops' run records as they are written (both are sealed by `vm_inventory.py protect` until then) |
| 3. `sync.py checkpoint` to `develop`, outgoing-history checks | Built and rehearsed on a bare remote, cycle 1 (`llm-dlc/tools/checkpoint.py`, 12 tests). The first push to the real `develop` is the watcher's (decision 1) |
| 4. `sync.py promote` to `main`, promotion receipt and review view | Not started |
| Delegated redaction decisions (built off) | Not started |
| Trace churn: delta cursor, pending trailers, deferred rendering | Not started |
| Pipeline day shards behind a shared ID resolver | Not started |
| Entry points: `CLAUDE.md`, README, skills, watcher instructions | Not started |

## The VM as found (2026-11-21, `python3 llm-dlc/tools/vm_inventory.py measure`)

| What | Measured |
|---|---|
| Remote | `origin/main` at `cfe2dc91`; no `develop` |
| Local history | 8 heads (one per workspace, and one unreferenced merge), 65 mutable commits, 18 unpushed on the default line |
| Stores | git 3.4 GB on disk (1.0 GB packed, 165,851 loose objects); jj 170 MB |
| Tree at the line's head | 63,964 files, 1.51 GB by path: `verification/results` 23,618 files and 665 MB, example `records/` 23,303 files and 421 MB, `llm-dlc/traces` 688 files and 74 MB |
| Widest directories | two `cases/` folders of example 359 with 2,865 entries each (one under `examples/`, one repeated under `verification/results/…/outputs/`), four of example 354 with 1,515 |
| Largest files | `llm-dlc/traces/01a1f5be-…/metrics.json` 9.8 MB, `lib/benchmark/results.json` 5.8 MB, another session's `metrics.json` 3.6 MB |
| A push of every head | 12,229 objects, 6,304 blobs of 766 MB unpacked; 5 blobs over 5 MiB, all versions of the one `metrics.json` |
| Runner state (default workspace) | 899 run directories (1.42 GB, the whole logs, outputs and diffs), 11 kept work directories (4.9 GB), 2 set aside (2.0 GB), nothing staged |
| Runner state (`foundation-domain-streams`) | 11 run directories, 5 work directories (1.4 GB) |
| Collected results | 986, of which 88 ran on another machine; no step log was ever cut (none exceeded 2 MB); 123 diffs were cut to `changes.diff.gz` or `changes.stat` |
| Traces | 207 sessions, 2,200 logs referenced, 31 not uploaded, 1,894 snapshots stored here (9.8 GB); the upload record lists 761 verified |
| Source transcripts | Claude Code: 372 files in 29 folders, 934 MB. Codex: 68 rollouts, 292 MB |
| Private run records | default workspace 372 files, `foundation-domain-streams` 149, archived workspaces 12: 73 MB together |

What existed only on this machine, and what was done about each:

- **Unpushed commits and side heads.** `vm_inventory.py pin` wrote a git ref under `refs/itl/pins/20261121/` for each of the 8 heads. jj neither imports nor moves that namespace, so no `jj util gc`, `git gc` or abandoned operation can drop them.
- **Run directories, work directories, run records, transcripts, example records.** `vm_inventory.py protect` sealed them into the spool in 2 minutes: 910 run directories (1.42 GB, one `job-run` occurrence a job, laid out as `verification/results/ID/`), 16 kept work directories as what each holds beyond its commit (77 MB of 6.3 GB), 4 folders of run records (73 MB, restricted), 209 transcripts as streams and 23 folders of their side files (1.23 GB, restricted), and the `records/` of examples 340 to 359 (20 trees, 409 MB). 3.21 GB of originals became 541 MB stored, in 2,522 objects. The upload started at once (`artifacts.py upload --drain`).
- **Not sealed, and why.** `lib/target` (24 GB) and the runner's `cargo-target` and `tools` are build outputs. The 1,894 redacted log snapshots are derivatives: 761 are on the public CDN, and the rest can be made again from the transcripts, which are sealed. The two set-aside work directories (2.0 GB, `20261106-first-vm-run-raw-hostname` and `20261115-181435-object-comparisons-cancelled`) have no result that names their commit, so their difference from it cannot be taken: they are left in place and listed here as an open item.
- **Known historical gaps.** 88 results ran on another machine (`FilSurface`): their run directories never were on this VM, and for those whose diff was cut the whole diff is gone. Run directories of jobs rerun before 2026-11-21 hold only the last attempt.

## The archive

- Contract: [the specification, "Original outputs"](../specification.md#original-outputs).
- Canary on the real store, 2026-11-21: custody for both classes (4 objects put, read back and receipted), a listing by run and a restore of every member from an empty cache, the same fetch offline, a restricted occurrence listed and refused; the ordinary token refused a GET of a known restricted key, a PUT and a DELETE (HTTP 403 each); the restricted token read its class and was refused the ordinary class and a PUT; the public traces' token was refused both; the public Worker answered 404 for the canary's keys.
- Residual exposure, for the report: every agent on this VM runs as the same Unix user, so the restricted token's file is readable by any of them. The bucket boundary holds against the ordinary *token*; on this VM the boundary between agents is policy (the tool reads the restricted class only in `analyze`, and the clients' permission rules will deny the file), not the operating system.

## Example 359 from hydrated evidence (2026-11-21)

The brief's exercise on evidence semantics, on the line's commit `7d865e55`, with the capturing machine's journal not consulted (an empty cache, `fetch` reading the store with the reader's token):

1. The commit was exported with `git archive` into a folder that is not a repository, without example 359's `records/` and without the copy of them that job `20261121-155348-repeat-organic-java-example-359-on-the-f` kept under `verification/results/…/outputs/`.
2. `artifacts.py fetch 20261121T172939Z-8e27fdd9aec8cf9f --to EXPORT` restored the example's records: 9,478 members, 6,374 files, 97,518,492 bytes, in 2.5 s; the same fetch `--offline` from the cache took 0.7 s. `artifacts.py fetch 20261121T172814Z-aa2c44f0e9e6386a --to EXPORT` restored the job's run directory in the layout of `verification/results/ID/`: 5,905 files, 64,636,772 bytes, in 1.8 s. `diff -r` against the checkout found no difference in either tree.
3. `python3 examples/tools/targets/workflow_handoff.py handoff 359 --revision fix` in the export gave, for `contents-fix`, native selectors **established, 2,865 admitted, 2,865 checked, no first blocker**, for both records, and the same routes, counts and coverage for all four claim subjects as the same command in the checkout.
4. With `calls/2df1780ebf1bce4149bd/cases/p1432/native.json` of one record removed, that record became **ineligible** ("…native.json does not exist"); with one byte of it changed, **ineligible** ("different raw checker output"). Each time the other selector record stayed established at 2,865 of 2,865 and the four finite-JVM routes stayed established. With the file put back the output matched the checkout's again.

Still to show for this row of the acceptance table: one historic flat job and one sharded job across different jj heads (the shards are not built yet).

## Checkpoints

- Contract: [the specification, "Checkpoints"](../specification.md#checkpoints).
- **For the watcher, the first real push** (decision 1): from the default workspace, once this line has landed there,
  `python3 llm-dlc/tools/sync.py checkpoint --bootstrap` creates `develop` at `main`'s commit (no object is sent), then
  `python3 llm-dlc/tools/sync.py checkpoint --rev @- --dry-run` prints the receipt and every refusal without pushing, and
  the same without `--dry-run` pushes. Later checkpoints go out under the command's own checks.
- **Rehearsal on the real history, 2026-11-21.** A bare remote on disk was given `main` at `cfe2dc91` and a clone of this
  line its 20 commits (15 on the first-parent path). Nothing touched the real origin.

  | Checkpoint | Commits | New blobs | Bytes scanned | Scan | Push | Total |
  |---|---:|---:|---:|---:|---:|---:|
  | `--bootstrap` | 0 | 0 | 0 | | | 0.2 s |
  | first commit after `main` | 1 | 13 | 14.8 MB | 1.9 s | 0.3 s | 2.3 s |
  | 17 commits coalesced, nothing kept from before | 17 | 5,877 | 349 MB | 11.4 s | 3.5 s | 15.0 s |
  | one commit | 1 | 14 | 4.9 MB | 0.7 s | 0.2 s | 0.9 s |
  | one commit | 1 | 14 | 6.0 MB | 0.7 s | 0.2 s | 1.0 s |
  | the same revision again | 0 | | | | | 0.1 s |

  Every run exited 0 with the working copy unread. The receipts counted 26 trace logs pending and 1 public for the 17
  commits. The push here is a copy on one disk: the real one adds the network.
- Why the redactor's rules are not applied whole to every outgoing blob: on the 18 commits unpushed on 2026-11-21, they
  flag 5,153 blobs for the home path and the user name (result and receipt files of the kind `main` already publishes)
  and 109 for `KEY=value` in fixtures and prose. Recognisable credential formats and this machine's own secrets and
  account identifiers flag none, and are what is refused everywhere; trace files get the whole rule set, as `check` gives them.
- Timings before the change, for comparison (`sync.py perf`, this workspace, 18 to 21 unpushed commits):
  `sync.py commit` took 27.9 s, 99.7 s (caches cold), 22.0 s and 19.4 s, of which the check after the commit 13 to 16 s
  warm. A push to `main` on 2026-11-21 took the watcher a pause of the run and `--skip-tests`.

## Notes for the next cycle

- A new test file in this workspace: run `python3 lib/tools/test_costs.py estimate` with the old `lib/tests/costs.json` saved, then take only the new file's rows and its summary entry into the old file, and run `lint` (the operating notes, "A fresh jj workspace").
- `TMPDIR=~/.cache/in-the-loop/tmp/plumbing` for tests and scratch files.
