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
| 2. Capture adapters in shadow mode | Runner and collector done, cycle 1 (`verification/capture.py`). Still to wire: transcripts at each commit, example records written outside jobs, the loops' run records |
| 3. `sync.py checkpoint` to `develop`, outgoing-history checks | Not started |
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

## Notes for the next cycle

- A new test file in this workspace: run `python3 lib/tools/test_costs.py estimate` with the old `lib/tests/costs.json` saved, then take only the new file's rows and its summary entry into the old file, and run `lint` (the operating notes, "A fresh jj workspace").
- `TMPDIR=~/.cache/in-the-loop/tmp/plumbing` for tests and scratch files.
