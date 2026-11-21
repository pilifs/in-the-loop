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
| 3. `sync.py checkpoint` to `develop`, outgoing-history checks | Built and rehearsed on a bare remote, cycle 1 (`llm-dlc/tools/checkpoint.py`, 12 tests). The first real checkpoint was made by the watcher on 2026-11-21 at 18:22, after the user merged this line's first cycle into the default line: `develop@origin` is `9f3b19ad`, `main` unchanged at `cfe2dc91` (as this checkout's jj shows them) |
| 4. `sync.py promote` to `main`, promotion receipt and review view | Built and rehearsed on the real history against a bare remote, cycle 2 (`llm-dlc/tools/promote.py`, 9 tests). No real promotion has been made: that is at the user's word |
| Delegated redaction decisions (built off) | Built, switched off, cycle 2 (`llm-dlc/tools/delegation.py`, 9 tests). The user turns it on from their terminal (decision 3) |
| Trace churn: delta cursor, pending trailers, deferred rendering | Done, cycle 2: a commit writes its session's manifest alone, the rest is rendered at a promotion; a cursor over verified trailers; the trailer without future URLs and `sync.py trace` (below) |
| Pipeline day shards behind a shared ID resolver | Readers done, cycle 2: `verification/layout.py`, every reader through it, a flat and a sharded job run side by side in the tests. New jobs still go flat: the switch is one line, left for after a real promotion (below) |
| The records' rule (VF-053, decision 5) | Done, cycle 2: per-case output kept as one pack a folder, read in place; examples 341, 345, 347, 354 and 359 packed in one pass (22,103 files to 5,772), equal to the sealed originals file for file; `check` holds the budget (below). The bytes of the large per-execution files are not cut: that is a question for the user |
| Entry points: `CLAUDE.md`, README, skills, watcher instructions | Done for checkpoints (cycle 1), promotions and delegation (cycle 2) |

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

## Promotions (cycle 2)

- Contract: [the specification, "Promotions"](../specification.md#promotions). For the watcher: `python3 llm-dlc/tools/sync.py promote --rev REV --dry-run` prints the review view and what would block; the same without `--dry-run` promotes, at the user's word only.
- **Rehearsal on the real history, 2026-11-21.** A clone of this line (25 commits past `main` at `cfe2dc91`) with a bare remote on disk, `develop` checkpointed to the line's head, an archive on disk, and the clone's own `promote.py` run for real: the frozen set, the candidate workspace, `adopt-logs`, the trace check twice, the index, the record's commit, the outgoing scan, both pushes, the receipt. Stood in for, so that nothing left the machine and no suite ran: the upload to the public CDN (each log stored in the candidate got the URL it would have) and the covering default run.

  | Step | Measured |
  |---|---|
  | The review view and the plan (`--dry-run` part) | about 3 s |
  | Making the candidate workspace, once (63,964 files, 2.1 GB on disk) | 8 s |
  | Building the record: 37 logs taken, checked, the index written, committed, checked again | 29 s warm |
  | Outgoing scan of the record (1 commit, 10 blobs, 4.1 MB) | 0.7 s |
  | Push of `main`, then of `develop` | 0.2 s each (one disk) |
  | The whole command, record already half built | 34 s |

  The record changed 10 files (84 lines added, 45 removed): 8 sessions' manifests (the URLs), the traces overview, and the summary of 39 lines. `main` and `develop` both ended at the record, whose parent is the frozen commit.
- **What the rehearsal found, and what was done.**
  1. The checkpoint of the commit that added `promote.py` was refused: it edits `llm-dlc/tools/test_performance.py`, a redaction test that has carried a made-up private key since before `main`'s head, and git names an edited file as a new blob. A blob's findings are now compared with those of the same file at the push's bases: values already there pass (counted as `carried` in the receipt), a new value is refused.
  2. Three trailers of this line's commits point at logs that their sessions' manifests in this line's tree do not list: the watcher's session and one other stamped these commits from the default workspace, where their manifests are. A promotion of this line alone blocks on them, by name, three times over (the plan, `check`, the publication gate), and says what resolves it: the landing brings the manifests, and that commit is promoted. This is the brief's "missing receipt for a commit already on `develop`", met on real data. The rehearsal let those three through, named, to exercise the rest.
  3. A record committed and then found wanting was left behind as a jj head; a rebuild now abandons it.
- **Rehearsed again at the end of cycle 2**, on the line as it stands (29 commits past `main`, the record rendered in the candidate by the new code). Checkpoints first: the 27 commits to `4c29c399` coalesced, 6,026 blobs and 392 MB scanned in 12.7 s with nothing kept from before; the commit that packs the records, 67 new blobs of which 45 are packs, opened and scanned in 3.0 s. The dry run named 0 blockers in 2.8 s. The promotion built its record in 55.6 s with every cache cold (a state folder of its own), scanned it in 1.0 s and pushed in 0.3 s: 15 files, the summary of 35 lines, 8 manifests, the index, the two overviews and the README's table, and for this session its `summary.md` and `metrics.json`, rendered in the candidate from the stored log since the transcript is in another workspace's folder. `check --rendered` there: 0 errors. `main` and `develop` on the bare remote both ended at the record `731f299f`. The three trailers of the finding above were let through again, named. A stand-in of the rehearsal's own harness had fallen behind the tools and stopped the first attempt; `promote` now records such a fault as the reason it stopped, and the same command continued the same promotion.
- Also changed with it: `sync.py push`'s publication gate no longer counts a commit that is only on `develop` as having its logs published (it asked `~ ::remote_bookmarks()`, which a `develop` on the remote would have satisfied for every checkpointed commit).

## Delegated redaction decisions (cycle 2, switched off)

- Contract: [the specification, "Redaction", *Delegated decisions*](../specification.md#redaction). `python3 llm-dlc/tools/sync.py delegate status` says "off" on this machine, and nothing here turned it on: no grant, no key and no record exist.
- To turn it on (the user, decision 3): the watcher runs `python3 llm-dlc/tools/sync.py delegate request --run NAME` and reports the code; the user grants it from their own terminal with the `delegate on` form the request prints. `python3 llm-dlc/tools/sync.py delegate off` ends it at once.
- The watcher's three commands are `sync.py delegate approve | withhold | mask`. They are spelled apart from the person's commands on purpose: the project's permission rules deny every agent the person's approval commands by their text, and those rules stay as they are.
- What the tests show (`test_delegation.py`, jj and the process table stood in for): off by default; only the client process that asked is the watcher, whatever another session's environment says; an approval with checked evidence is recorded and waives the finding, and prints no value; a `long-token` with only a stated origin is refused, as is a kind the redactor removes; an entry written by hand, an entry edited after the decision, a line added to or changed in the record, a decision under an older policy and a delegation switched off all fail validation; a log is withheld before publication and sealed in restricted custody; a masked value is out of later logs, unpublished logs that hold it are withheld, and a published one becomes exactly one masked escalation that only a person closes.
- **Not shown yet:** a routine batch decided and then *published* by a real promotion without a person (it needs the delegation on, which is the user's, and a real promotion); the record's copy in the restricted archive compared with the local one by a command (it is sealed there as a stream; the comparison is by `artifacts.py` today).
- Also changed with it: a decision counts as published only when it is on `main`. Before, any immutable commit counted, and commits on `develop` are immutable since cycle 1.

## The trace changes (cycle 2)

Before, `sync.py perf` for an ordinary commit in this workspace, 2026-11-21: 28.5 s, of which the check after the commit 16.4 s (the sessions 9.5 s, of which 4.1 s hashed the 1,907 stored `.gz` logs again and 1.7 s recomputed 207 sessions' metrics; the trailers 5.7 s, of which 4.0 s read a manifest out of the tree of each of 1,543 traced commits; the global files 1.0 s), processing the changed sessions 3.8 s, the index 0.9 s. Each commit wrote 12 generated files: the session's manifest, summary and metrics, and the six global ones.

What changed, and what was measured after:

| Change | Before | After |
|---|---|---|
| Generated files in an ordinary commit | 12, megabytes for a long session | 1: the session's `manifest.json` (the first commit of this kind, `qvkkkpkz`, shows it) |
| Global index and overview rewrites per ordinary commit | 2 of 2 in all 50 commits the brief counted | 0: rendered by `promote`, `push`, `sync`/`render`, `regenerate` |
| The check, warm | 16.4 s | 4.1 s (trailers 0.4 s with 1,540 commits known from the cursor and 3 read; sessions 2.6 s with 1,902 logs found by stat) |
| A commit's trailer | three lines, two of them URLs that served nothing yet | `LLM-Trace: SESSION sha256:LOG`; `sync.py trace REV` resolves it (public, withdrawn, or pending and where) |
| Published commits restamped | none | none: only mutable commits are ever described, and a commit on `develop` is immutable |

- Contract: [the specification, "Workflow", *Rendering*](../specification.md#workflow) and its Identifiers table.
- A promotion's candidate renders before its first check: `sync.py sync` there has no transcripts, so it recomputes each session's metrics and summary from the stored current log and the manifest (which now records the workspace path a summary shortens file names by), then the index; `check --rendered` holds it to that.
- Cost of the change itself: an edit to `redactor.py` or `sync.py` drops caches keyed by the tools, so the first check after this lands rescans every log once (167 s here) and reads every traced commit once.
- **Not done of the brief's section 4:** a session's `metrics.json` is still one file rewritten whole at each rendering (9.8 MB for the largest); "growing event journals out of Git" would mean moving it to the archive with a small summary in git. Session offsets already have a cursor (the transcript cache redacts only what a transcript gained); the commit index of `link_commits` still asks jj for every traced description at each sync (about 1 s).

## Pipeline layout (cycle 2: readers only)

- Contract: [`verification/README.md`, "Two layouts"](../../verification/README.md#two-layouts-flat-and-by-day). `verification/layout.py` is the one place that knows where a job and its result are: flat as all 986 are, or under the UTC day in the job's id. Nothing moves, a result goes beside its job, identical duplicates resolve to the flat copy and differing ones are named by `validate`.
- Readers through it: `pipeline.py` (22 sites: the queue, results on other heads, `status`, `collect`, `commit-paths`, `report`, `resubmit`, `prioritize`, `validate`, the results index), `sync.py` (the loops' statistics), `cost_inventory.py`, `conductor.py`, `brief_run.py`, `accept.py`, `claim_history.py`, `capture.py`, `vm_inventory.py`, `promote.py`. Left on flat paths on purpose: the `external-upgrades` benchmark scripts, which name particular November results.
- The results index is kept by day for results kept by day: `results/index.json` lists the flat ones and names the days, each of which has its own `index.json`; with no sharded result it is byte for byte what it was.
- Shown by `test_pipeline.py`: one flat and one sharded job submitted, run, collected and reported together; the sharded result beside its job with its schema reference at that depth; both recognised as recorded on another head and neither run again, with the source commit unchanged; a resubmission going where new jobs go; a differing duplicate named.
- **Two standing decisions of the user bear on this**, and I read the brief as consistent with both: "add no complexity to `verification/pipeline.py`" (2026-11-17) and "move no folders" (2026-11-15). So the resolver is a module of its own, `pipeline.py` lost its own path arithmetic rather than gaining a second one, nothing was moved, and new jobs still go flat (`WRITE = "flat"`). Switching writers is the brief's step after a real promotion, and is the user's: one line, or `VERIFY_LAYOUT=shards` for one command.

## The records' rule (cycle 2; VF-053, decision 5)

What the records of examples 340 to 359 were, measured before anything changed: 22,103 files and 408.5 MB. By count, 16,376 of the files were per-case output of native-selector runs (`cases/pN/native.json` and `stderr`, 37 MB together); by bytes, most is a few hundred large files (`execution.json` 125 MB in 319 files, `controls.json` 74 MB, `attempt.json` 26 MB, two JVM control outputs 50 MB). VF-053 names the file count as the cost: one folder of 2,865 entries, and every snapshot, checkout and scan walking all of them.

- **The rule** ([`examples/approaches.md`](../../examples/approaches.md), `examples/tools/targets/case_pack.py`): a folder of per-case output is kept as one `cases.tar.gz` beside where it was, the same bytes under the same names, written so that the same files give the same pack. The validator (`native_selectors.validate_result`) reads a case from the folder or from the pack and compares its digest either way, so a plain checkout still checks every case, and a public reader needs no archive. `sync.py check` reports more than 50 loose per-case files in one `cases/` folder as an error that names the command, and more than 2,000 files under one example's `records/`, or 1,000 entries in one folder, as a warning (0 of either on this tree now, 50 ms).
- **Why packed in the repository and not moved to the archive:** the archive is private. Records kept only there would leave a route that today reads "established, 2,865 admitted, 2,865 checked" unable to be checked by anyone without the token, and every validator, page and test that reads it would need a third state. The pack removes the cost VF-053 measured and changes no verdict. The sealed originals stay in the archive as they were (20 occurrences, all `remote_verified`).
- **Applied, one pass:** `case_pack.py pack 341 345 347 354 359`, 2.5 s. 16,376 files became 45 packs, 37.0 MB became 0.9 MB; the 20 examples' records went from 22,103 files to 5,772 (354: 10,037 to 946; 359: 6,374 to 639), and no folder has more than 1,000 entries.
- **Shown:** the handoff of each of the five examples (`workflow_handoff.py handoff NNN`, and `--revision fix` for 354 and 359) is byte for byte what it was before the packing. The five sealed originals, restored from the store with `artifacts.py fetch`, equal the packed records file for file (`case_pack.py verify 341 345 347 354 359 --against DIR`: 16,376 members). With `p1432/native.json` taken out of 359's pack the record became ineligible ("…cases/p1432/native.json does not exist"), with one byte of it changed, ineligible ("different raw checker output"), each time with the other 39 established results unchanged; with the pack put back the output matched again. `validate_example.py` passes for the five.
- **Queued, not yet run:** job `20261121-195020-345-native-selectors-with-the-built-chec` runs example 345's selector route with the real checker, then fails unless a new record was written with its per-case output packed, nothing is left loose, and the claim history validates and cites that record. Until it is in, the packing at the end of a run is shown by the tests of the pack and by the records packed after the fact, not by a run of the checker. Read it with `python3 verification/pipeline.py report 20261121-195020-345-native-selectors-with-the-built-chec` once collected; a failure there is the next cycle's first work.
- **A pass that shows nothing, mine:** the first job I queued for this, `20261121-194629-345-native-selectors-again-the-run-packs`, is recorded as passed in 1.2 s. I had not declared that it requires `jvmcontract`, so its run ended at once with "no built native checker", and its checks were loose enough to accept that (an exit of 1, and the newest record being cited, which an old one was). Its result is on the default line (`1ea85f0d`) and is evidence of nothing; the job above replaces it and cannot pass that way.
- **A hole this would have opened, closed:** the checkpoint's scan read a compressed blob as its compressed bytes, so a credential inside a pack would have gone out unseen. It now reads a gzip blob as what it opens to (every member and whatever follows the last; refused as unread over 256 MiB), with a test of a token inside a pack.
- **Found by doing it:** `sync.py commit --only` named every file it set aside on one command line, and 16,000 were too many. It names what stays now.
- **Not packed:** the copies of such records that four collected job results keep under `verification/results/ID/outputs/` (8,864 per-case files; 5,734 and 3,032 of them in the two repeat jobs of 359 and 354, one folder of 2,865 entries and one of 1,515). A result's `result.json` lists each output file with its digest, so packing them would change a collected result; they stay as collected. A job that runs the selector route from now on collects the packs, since the run packs its own output.
- **Not cut, and for the user:** the bytes. The large per-execution files are few and are read whole by the validators; keeping less of them (a digest and a pointer into the archive) is a decision about what evidence a public reader can re-check. `check` warns before another example passes 2,000 files; nothing bounds bytes.

## Smaller things done in cycle 2

- `prune_workspaces.py` counts a file as recoverable when the private archive holds its exact bytes in an occurrence verified in the store (a capture still waiting for its upload does not count, nor do other bytes of the same length); it says how many files are kept by the archive alone. Its tests no longer read the machine's own archive.
- `sync.py check` warns at 100 commits on neither `develop` nor `main` (6 here now; 0.2 s).
- Both run skills have the watcher say, with each verdict or merge, what waits on a person.
- A selector run packs its own per-case output at its end, so a new record adds no per-case folder to Git.
- Codex's rules (`.codex/rules/llm-dlc.rules`) forbid switching delegation on, as Claude Code's do. Its prefix rules cannot name every command that might read a file, so for Codex the rule about the tokens and the key in `~/.config/in-the-loop/` is `CLAUDE.md`'s alone.

## Acceptance evidence so far

| Exercise of the brief | State after cycle 2 |
|---|---|
| Dirty workspace, reviewer busy, store offline | Shown on a bare remote by `test_checkpoint.py` and by the rehearsal on the real history: a fresh clone reads the code at `develop`; the foreign files' hashes and the working-copy commit are unchanged; the test gate, the session sync and the log upload are patched to fail if called and are not; the receipt lists pending trace logs and the archive's exposure; a credential in a parent commit the tip deleted, an unsafe message and `--all` are refused with the remote unchanged. The checkpoint asks the store nothing, so its being offline changes only the receipt's custody line. **Open:** the same on the real `origin` (the watcher's first push). |
| Concurrent promotion and restart | Shown on a bare remote by `test_promote.py`, with the trace tools' steps and the suite stood in for: a failing default run leaves `main` at P, records the reason, and the same command continues the same promotion once it passes; the covering run is recorded against the record's tree; `develop` moving on does not enlarge the frozen set (2 commits, not 3) and takes the record in by an ordinary merge that keeps the later work; `main` moving is refused before the build and, when it moves between the gate and the push, by the push itself, with nothing forced; a lost push answer followed by a kill is one promotion with one record; a frozen commit whose log is stored nowhere is named and blocks, in a dry run and in a real one, and passes once the log is back; an original the store has not verified blocks until it has, and a job never captured is counted as a gap. On the real history: the rehearsal above, where the missing receipts were real ones. **Open:** a real promotion (the user's word), with the real upload and a real default run in the candidate. |
| Interrupted capture, multiple workers, bad store response | Shown by `test_artifacts.py` and `test_capture.py`: killed before and after the intake record, after the puts and before the receipt; a dead worker's lease; two workers on one object; a store offline, losing its answer, holding other bytes under the same key, holding a truncated object; a full disk (nothing sealed, the job and the collect unharmed, the staged files set aside, not deleted); reused paths keeping each version. No state reads `remote_verified` without the object having been read back. A collector killed (SIGKILL, no handler) with the result's folder wiped and not yet written, and again with the result written and sealed and the staged one not yet released: the next collect finishes both times, the earlier result it had wiped was sealed first and restores, and the archive holds one complete record for each thing a collect did (`test_capture.py`). |
| Recovery with only remote state | Shown with an empty cache and the reader's token, the journal not consulted: `artifacts.py canary` on the real buckets (11 of 11), and the 359 exercise above (two real occurrences, 12,279 files, every byte verified, then offline). In tests on a disk store: the middle of a cut log, failed and conflicted outputs, nested and binary files, any past prefix of a stream. The watcher's private analysis now reads an occurrence its machine never held from the store alone (the verified receipt and inventory, in memory, the read logged first): shown on a disk store by `test_artifacts.py`; on the real restricted bucket it is the watcher's to run (`artifacts.py analyze ID --purpose TEXT` with `ITL_ORIGINALS_HOME` at an empty folder), since no other agent reads that class. **Open:** a promoted attempt (no real promotion yet); a literal second machine. Legacy gaps are listed under "The VM as found". |
| Evidence semantics | Shown for example 359, above. One flat and one sharded job across two heads, neither rerun and the source commit unchanged: `test_pipeline.py`, on a throwaway repository with git branches standing for the heads. |
| Delegated review | The access half is shown by the canary: an ordinary token cannot read a known restricted key, readers cannot write or delete, the public Worker and the public traces' token read neither class. The decision half is built switched off and shown by `test_delegation.py` (the section above): the watcher's approval with checked evidence, a masked value, a withheld log, one masked escalation, and the failures of a forged entry, changed bytes, an edited record and a stale policy. A planted credential is withheld by what was already there: the redactor's own kinds are an error of `check`, refused by the uploader before any PUT and by the checkpoint before any push (`test_checkpoint.py`), and no delegated command can waive them. **Open:** the same with the delegation on, on real findings, through a real promotion: the user's to switch on. |
| Cost and compatibility | Before: `sync.py commit` 19 to 28 s warm and 100 s cold in this workspace; every commit rewrites the global index and overview. After, for a checkpoint on the real history against a disk remote: 0.9 to 2.4 s for one commit, 15 to 17 s for 17 to 23, 0 default-suite calls. A rehearsed promotion of 25 commits: 34 s with the record half built, 8 s more the first time for the candidate workspace, the upload and the suite apart. An ordinary commit: 12 generated files before, 1 after; no global index or overview rewrite; the check 16.4 s before, 4.1 s after, warm; no published commit restamped (the table above). **Open:** the 20-commit comparison on the real remote, with medians, which needs the real `develop`. |

## Run report (end of cycle 2, 2026-11-21)

**Promoted code and tree.** None on the real remote: a promotion is at the user's word. `origin/main` is `cfe2dc91`, as before the run. `origin/develop` exists since 18:22 (`9f3b19ad`, the watcher's first checkpoint, holding cycle 1). This line's head is the last commit of the workspace `dlc-plumbing` (`jj log -r @-` there); its commits since that checkpoint, from `xuumpxym` ("Add sync.py promote") on, are on this line only until the watcher lands and checkpoints them. On a bare remote on disk the whole line was promoted twice in rehearsal (above).

**Archive inventory** (`artifacts.py status`, 19:40): 1,197 occurrences, 3.22 GB of original bytes in 2,552 objects (544 MB stored), every one read back from the store and `remote_verified`; nothing on this machine is a last copy. **Restores shown:** the canary on the real buckets (11 of 11); example 359's records and a job's run directory from an empty cache (12,279 files, every byte verified, `diff -r` clean, then offline); the five packed examples' sealed records (16,376 per-case files and the rest, file for file). **Open custody gaps:** the historical ones under "The VM as found" (88 results that ran on another machine; reruns before 2026-11-21 keep only the last attempt); the redacted log snapshots are derivatives and are not sealed; on this VM the boundary between agents for the restricted class is policy, not the operating system.

**Timings, before and after, on this VM.**

| | Before | After |
|---|---|---|
| `sync.py commit`, warm | 19 to 28 s (100 s cold) | 13.9, 15.9 and 16.4 s for this cycle's three commits after the change, each of which edited the tools and so ran with part of its caches cold; the check inside it 4.1 s warm against 16.4 s |
| Generated files written by a commit | 12 | 1 |
| Code readable on the remote | at a push to `main`: a pause of the run, hours to days apart, the default suite or `--skip-tests` | a checkpoint: 0.9 to 3.5 s for one commit, 13 to 17 s for 17 to 27 commits with nothing cached, no suite, no upload |
| Promotion of 25 to 29 commits (rehearsed; upload and suite stood in for) | | review 3 s, record 29 s warm and 56 s cold, scan 1 s, pushes under 1 s |
| Example records in Git, examples 340 to 359 | 22,103 files, widest folder 2,865 | 5,772 files, widest folder under 1,000 |

Not measured as the brief asks: medians and p95 over 20 commits on the real remote with the network in the path (the checkpoints here went to a disk remote; the one real checkpoint was the watcher's, 15.2 s for 26 commits by its own account), and a real promotion's upload and suite.

**Paths and interfaces a later reorganisation has to keep, or keep readable.**

- `verification/pipeline.py` and its subcommands; `verification/jobs/ID.json` and `verification/results/ID/` for the 986 jobs there are (commits, notes and reports link to them); `verification/results/index.json`; `verification/layout.py` as the one resolver of a job id, flat or `YYYY/MM/DD/`.
- `llm-dlc/traces/SESSION/manifest.json`, `summary.md`, `metrics.json`; `llm-dlc/index.json`; `llm-dlc/traces/README.md` and `metrics.json`; the table in `llm-dlc/README.md`; the manifest and metrics fields the specification documents.
- Commit trailers: the historical three lines (`LLM-Trace`, `LLM-Trace-Summary`, `LLM-Trace-Log`) and the one line new commits carry (`LLM-Trace: SESSION sha256:LOG`); `sync.py trace REV` resolves both. The public CDN's URLs of the logs.
- `llm-dlc/artifacts/YYYY/MM/DD/promotion-ID.json` (`llm-dlc/publication-summary.schema.json`).
- Example records under `examples/NNN-slug/records/`, and the names a result gives its cases (`calls/KEY/cases/pN/native.json`), read through `case_pack.read` from the folder or from `cases.tar.gz`.
- The archive's keys (`occurrences/DATE/ID.json`, `objects/sha256/XX/DIGEST.gz|raw`, `restricted/occurrences/…`, `intents/…`) in the two buckets; on the machine, the spool and journal in `~/.local/share/in-the-loop/originals`, the state in `~/.local/state/llm-traces/` (checkpoint receipts, promotions, outgoing verdicts, trailer cursors, the watcher's decisions ledger), the tokens and the key in `~/.config/in-the-loop/`, and the pinned heads under `refs/itl/pins/`.
- The commands other tools and the skills call: `sync.py commit | check | checkpoint | promote | push | trace | render | review | allow | delegate`, `artifacts.py list | fetch | status | analyze | verify | canary`, `lib/tools/default_run.py`'s record of a passed run, `lib/tools/test_costs.py`.

## What is left, in the order I would take it

1. Smaller: a bound on the bytes of an example's records, once the user says what a public reader must be able to re-check (above); session metrics out of git (above); catalog pages, so a fresh machine lists without one request a receipt; the two set-aside work directories; a command that compares the watcher's record with its sealed copy; the 20-commit cost comparison on the real remote; the bound on a result's receipt arrays (its `outputs` list names every file: 5,905 entries for one job), with the writers' switch.

For the watcher and the user, none of it mine to do: the next checkpoint, once this cycle's commits have landed on the default line (`develop` is at the first cycle's merge, `9f3b19ad`; the commits since are on this line only); a first real promotion, when the user asks (`promote --rev REV --dry-run` first: on this line alone it will name the three logs whose manifests the landing brings); switching the delegation on, if and when the user wants it; the allow-list proposal `a82875ef`.

## Notes for the next cycle

- A new or changed test file in this workspace: save `lib/tests/costs.json`, run `python3 lib/tools/test_costs.py estimate`, take only that file's rows and summary entry into the saved copy, run `lint` (the operating notes, "A fresh jj workspace"). `~/.cache/in-the-loop/tmp/plumbing/take_rows.py OLD.json FILE...` does the taking (with `jj file show -r @- lib/tests/costs.json` as the old copy, the diff is the new tests' rows and their files' counts and nothing else; `keep_committed_rows.py` beside it puts back any committed row an estimate rewrote); then `tag FILE` if the lint asks.
- First: the result of job `20261121-195020-345-native-selectors-with-the-built-chec` (the records' section says what it shows and what a failure means).
- `TMPDIR=~/.cache/in-the-loop/tmp/plumbing` for tests and scratch files. The last rehearsal's folder is kept there (`rehearsal-7o9xy9pc`, 4 GB: the bare remote with the rehearsed `main`, the clone and its candidate); the earlier ones are removed. `rehearse.py` there rebuilds the bare-remote rehearsal (`rehearse.py CHECKOUT REV N`).
- A change to the redactor's literals or rules makes the next `sync.py commit` rescan every log (several minutes, once). The commit of `checkpoint.py` paid that for the three new tokens; the default workspace will pay it once when this line lands.
- A Bash command whose text holds a push or a commit of plain git can be refused by the client: put such steps in a script file and run the file.
- A Bash command whose text holds one of the person-only commands (the allow list's approval, `delegate on`, the reviewed-findings file) is refused by the project's rules, even inside a script that only edits source text. That refusal is the rule working: edit such text with the file tools.
- `rehearse_promote.py FOLDER REAL_CHECKOUT` (beside `rehearse.py`) runs a whole promotion on a folder `rehearse.py` made, with the public upload and the suite stood in for. A scratch script that the scan's worker processes can import needs its `if __name__ == "__main__"` guard: without one, 30 workers each started a promotion of their own, and one commit here took four minutes while they ran.
- Never stop a stuck background command with a pattern that matches its own text: `pkill -f NAME` killed the shell that ran it. Kill by the process's working directory.
- `develop` exists on the real remote since 2026-11-21 18:22 (the watcher's first checkpoint, `9f3b19ad`). A loop's agent still pushes nothing: the watcher checkpoints what has landed.
