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
| 1. Inventory and protect the VM | Next |
| 2. Capture adapters in shadow mode (runner, collector, records, transcripts) | Next |
| 3. `sync.py checkpoint` to `develop`, outgoing-history checks | Not started |
| 4. `sync.py promote` to `main`, promotion receipt and review view | Not started |
| Delegated redaction decisions (built off) | Not started |
| Trace churn: delta cursor, pending trailers, deferred rendering | Not started |
| Pipeline day shards behind a shared ID resolver | Not started |
| Entry points: `CLAUDE.md`, README, skills, watcher instructions | Not started |

## The archive

- Contract: [the specification, "Original outputs"](../specification.md#original-outputs).
- Canary on the real store, 2026-11-21: custody for both classes (4 objects put, read back and receipted), a listing by run and a restore of every member from an empty cache, the same fetch offline, a restricted occurrence listed and refused; the ordinary token refused a GET of a known restricted key, a PUT and a DELETE (HTTP 403 each); the restricted token read its class and was refused the ordinary class and a PUT; the public traces' token was refused both; the public Worker answered 404 for the canary's keys.
- Residual exposure, for the report: every agent on this VM runs as the same Unix user, so the restricted token's file is readable by any of them. The bucket boundary holds against the ordinary *token*; on this VM the boundary between agents is policy (the tool reads the restricted class only in `analyze`, and the clients' permission rules will deny the file), not the operating system.

## Notes for the next cycle

- A new test file in this workspace: run `python3 lib/tools/test_costs.py estimate` with the old `lib/tests/costs.json` saved, then take only the new file's rows and its summary entry into the old file, and run `lint` (the operating notes, "A fresh jj workspace").
- `TMPDIR=~/.cache/in-the-loop/tmp/plumbing` for tests and scratch files.
