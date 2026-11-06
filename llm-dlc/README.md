# LLM development lifecycle

This folder is the meta example: how this repo is built with an LLM, in the open.
Every change is published together with the LLM session that made it.
For each commit you can read the message, a summary of the session, and the full transcript.

The formal verification work itself is in [`examples/`](../examples/README.md). This folder is about how it was made.

```
llm-dlc/
  README.md                         this file: the procedure, and an index of sessions
  specification.md                  the specification: identifiers, invariants, storage, redaction
  performance.md                    where sync.py's time goes, measured, and why it stays in Python for now
  index.json                        every session and the commits it made (generated)
  pricing.json                      list prices per model, written by hand, used for the metrics
  allowlist.json                    false positives by value: proposed by an agent, approved by a person
  reviewed-findings.json            false positives a person reviewed, by hash, which `check` no longer raises
  summary-template.md               the template for each summary.md
  traces-readme-template.md         the template for traces/README.md
  session-notes/<session-id>.md     optional hand-written note, shown at the top of that session's summary
  traces/README.md                  every session added up: tokens, tools, commits, logs (generated)
  traces/metrics.json               every session added up as data, for charts (generated)
  traces/<session-id>/
    summary.md                      what was asked, what was done, what was committed (generated)
    manifest.json                   detailed metadata: stats, models, tokens, commits, logs (generated)
    metrics.json                    every prompt, model call and tool call as tables, with costs and causes (generated)
    logs/<sha256>.jsonl.gz          redacted transcript snapshots (gitignored, published on the CDN)
  tools/sync.py                     the hook and commands that capture, redact, publish and check traces;
                                    test_review.py and test_performance.py test it, `sync.py perf` times it
  tools/redaction_rules.py          what counts as sensitive, and the stamp that says which files have been checked
  tools/redactor.py                 the redactor and the local caches of its results, keyed on it and the rules alone
  tools/measure.py                  where a command's time goes, for `sync.py perf`
  tools/profile_rules.py            a cold scan's cost rule by rule, the measurements behind performance.md
  tools/metrics.py                  turns logs into the metrics tables; test_metrics.py tests it
  loops/                            briefs for feature-loop.sh: markdown instructions a loop works through
  tools/feature-loop.sh             runs a named instruction or a brief unattended: instruction, commit, compact, repeat, then a summary
  tools/verification-loop.sh        keeps the verification queue empty: a fresh Sonnet session per run of /run-verification
  tools/loop-common.sh              what the two loops share: log lines and the live display of a session
  infra/
    cdn/                            the Cloudflare Worker that serves the logs
    langfuse/                       an optional local Langfuse, for browsing traces
```

## Set up

Once per clone, after the toolchain (`devtools`, from [`examples/setup/ubuntu-wsl`](../examples/setup/ubuntu-wsl/install.sh)):

```bash
python3 llm-dlc/tools/sync.py init        # jj config and aliases, and the pinned wrangler
llm-dlc/infra/langfuse/up.sh              # optional: Langfuse on http://localhost:3000
```

## How a commit points at its session

Each commit message ends with three lines that point at all of this:

```
LLM-Trace-Summary: https://github.com/<owner>/<repo>/blob/main/llm-dlc/traces/<session-id>/summary.md
LLM-Trace-Log: https://terminalvalue.net/raw-traces/<session-id>/<sha256>.jsonl.gz
LLM-Trace: <session-id> sha256:<sha256>
```

The first two are links for readers. The last is the identifier: the SHA-256 of the uncompressed log at the moment of the commit, so the log can be verified.
[`specification.md`](specification.md) has the full specification: identifiers, invariants, storage and redaction.

## Procedure for agents

Claude Code runs this procedure in this repo. `CLAUDE.md` points here, and the hooks and permissions in `.claude/settings.json` let it run without prompts. Other agents should follow the same steps.

**What happens without you.** The repo changes only when something is committed or pushed, so it stays clean between commits. At the end of every turn, a hook only sends finished turns to Langfuse. If a commit is made with plain `jj commit` or `git commit`, a hook traces it straight after, as `sync.py commit` would have. Never edit the generated files or the trailer lines by hand.

**What you do: commit each feature when it is done.**

1. **Scope.** A feature is the smallest change that a reviewer can understand on its own and that leaves the repo working: a demo, a tool, a setup component, a fix, a doc section.
   Commit as soon as one is finished and verified, so `@` never mixes two features. Don't ask before committing.
   A session can make several commits. A feature that spans sessions gets a trailer from each session.
2. **Check what is in `@`:** `jj status` and `jj diff --stat`.
3. **Commit:**
   ```bash
   python3 llm-dlc/tools/sync.py commit -m "Add the bytecode verifier demo" -m "What changed and why, and how it was verified."
   ```
   Each `-m` is one paragraph. The first is the summary line: imperative, at most 72 characters.
   The later paragraphs become the feature's entry under *Changes* in `summary.md`, so write them for a reader who did not see the conversation: what changed, why, and how you verified it.
   Add `Co-Authored-By:` as the last paragraph if your harness asks for it. The trace lines are added after it.
   The command writes the message, syncs the manifest and summary so they match it, and starts a new empty change. `jj trace-commit` is the same command.
4. **Verify:** the command then runs the check of `sync.py check` on what it committed, counting the notes instead of listing them, and must report 0 errors. An error fails the command but leaves the commit in place: fix it and commit the fix. A separate `python3 llm-dlc/tools/sync.py check` is needed only to list the notes, or after a commit made with plain `jj commit`, which the hook traces but does not check.

**Push only when the user asks.** Pushing publishes the log, and a person should read it first; see *Redaction* in [`specification.md`](specification.md#redaction).
```bash
python3 llm-dlc/tools/sync.py scan                   # preview: what was redacted, what a person should look at
python3 llm-dlc/tools/sync.py push --bookmark main   # record outstanding traces, check, upload, check, verify the revision, push
```
`push` refuses to upload a log in which the redaction rules would still change something, and prints a `warn` line for anything they leave to judgment.
Before pushing, this records everything no commit points at yet in one last *Record session traces* commit: conversation after a session's last commit, and sessions with no commit of their own. It moves the bookmark there and leaves `@` empty. It refuses to run while `@` holds uncommitted work.
The user can run the same thing as `/publish`, which commits finished work first.

A session's last words cannot be in the log that a push from inside it publishes, because they come after it. They go out with the next push from any session, or at once if the user exits and runs the command from a terminal.

**Don't:**
- edit a generated `summary.md` to correct or explain a session; add `llm-dlc/session-notes/<session-id>.md` instead
- run `git commit`, which bypasses the jj change IDs that the manifests key on
- run `jj describe` on a pushed commit, or remove `LLM-Trace` lines from any message
- put secrets in prompts, files or command output; they would end up in a published log
- print a raw transcript, `~/.claude.json`, or a real identifier while working on the redactor; test it with made-up values
- mark a finding as a false positive yourself. Propose it instead with `sync.py allow propose ID --reason "why"`, tell the user what it is, and they run `sync.py allow approve` in their own terminal. A finding of a kind the redactor removes (an `ERROR`) can't go on the allow list: they run `sync.py review accept` for it

## Unattended loops

[`tools/feature-loop.sh`](tools/feature-loop.sh) resumes one Claude Code session and repeats the instruction you name, compacting the session after each commit: `features` adds features and examples to jvmcontract, `tla` adds advanced TLA examples, and `spring` makes jvmcontract more useful to expert Spring Boot developers (new models, solvers, examples or other features, built into the library itself where it can be), and `relational` makes relational verification more efficient and accurate, adding examples where appropriate. In place of a name you can give a markdown brief, such as [`loops/sync-performance.md`](loops/sync-performance.md) (make `sync.py` fast): every cycle tells the session to read the brief again in full and take the next piece of work it calls for, so the brief outlives each compact; a brief that changes while the loop runs stops it, and briefs live in `loops/`. A number after the name sets how many cycles to run; without one it runs until stopped. Instead of a number, or after it, you can give instructions for when the work is done, and the session decides when to stop: after each commit, before the compact, it gets one more turn to weigh them against what the run has done and ends its reply with `LOOP: continue` or `LOOP: stop`. A stop ends the loop like running out of cycles, summary included; a reply with neither stops it as needing attention, and the reasons it gave are in the run's record. A number given as well is still an upper limit. It also stops when a cycle makes no commit, because that may mean a person is needed, and it leaves that session uncompacted so its context is there to read.

Each run keeps a record in `llm-dlc/loop-summaries/` (gitignored, so nothing in it is pushed): the instruction, a line for each commit as it lands, so it survives a restart, and how the run ended. When the cycles run out, the loop asks the session for one more turn that only reports: a summary of the run's commits, the verification jobs still pending or failed, and the `sync.py check` warnings to judge before pushing. That summary goes at the end of the record.

A brief can carry its own instructions for when to stop under a `## Loop until` heading, which the loop uses when the command line gives none; a brief with neither runs until the session decides it is done. The loop resumes the session that has always run it, with Fable at high effort. A brief can name its own session, model and effort under a `## Loop settings` heading (`- session: ID`, `- model: ID`, `- effort: LEVEL`), and `FEATURE_LOOP_SESSION`, `FEATURE_LOOP_MODEL` and `FEATURE_LOOP_EFFORT` override both. `FEATURE_LOOP_SESSION=new` starts a fresh session that the run's cycles share, and a session id with no transcript yet, such as one opened in Claude Code but never sent a message, is created by the loop's first turn.

It runs in a systemd scope capped at 3.5 GB (`FEATURE_LOOP_MEMORY_MAX` changes that), so a proof that exhausts memory is killed alone and the session sees it fail. It won't start if less memory than the cap is available, or if `feature-loop.scope` is still active.

```bash
llm-dlc/tools/feature-loop.sh tla 5
llm-dlc/tools/feature-loop.sh spring 8 "Stop once the throws lines cover reactive handlers, or when the next idea would be minor."
llm-dlc/tools/feature-loop.sh llm-dlc/loops/sync-performance.md
```

While it runs, it reads commands typed in its terminal, followed by Enter. It prints them when it starts and a reminder at each cycle:

| Command | Effect |
| --- | --- |
| `+N`, `-N` | run N more or N fewer cycles after the current one (`+` and `-` alone mean 1) |
| `=N`, `N` | run exactly N more cycles after the current one |
| `0`, `stop` | end after the current cycle |
| `inf` | no limit |
| `?`, `help` | where the loop stands, or the list of commands |

A cycle under way always finishes, commit and compact included. When the count reaches 0 the loop exits 0. Ctrl-C stops it at once, with exit status 130. Started without a terminal, it runs the number of cycles it was given.

It commits locally and pushes nothing. It has no spending limit.

[`tools/verification-loop.sh`](tools/verification-loop.sh) does the same for the [verification queue](../verification/README.md). Whenever jobs are queued that this machine can run, or results wait to be collected, it starts a new Claude Code session on Sonnet 5.5 running [`/run-verification`](../.claude/skills/run-verification/SKILL.md), which runs, collects, triages, resubmits and commits until the queue is clear. Each run gets a fresh context, since the work is mechanical. When the queue is clear it checks it every minute (`VERIFICATION_LOOP_POLL` sets the seconds) for jobs committed since, and starts again when one appears.

```bash
llm-dlc/tools/verification-loop.sh
```

A run that leaves work behind, such as jobs it resubmitted, is followed by another, up to 4 in a row (`VERIFICATION_LOOP_RUNS`). A run that leaves exactly what it found isn't repeated: the loop waits until the queue changes, since what is left needs a person. Jobs too big for this machine, and jobs another runner holds, don't start a run. While it runs it reads `stop` (end after the run under way, or at once while waiting), `now` (check the queue at once) and `?` (show the queue) from its terminal, and prints them when it starts. It runs alongside the feature loop, whose scope the skill leaves memory for. It commits locally and pushes nothing.

## Sessions

Newest first. Each row links to the session summary. The [traces overview](traces/README.md) adds them all up.

<!-- index:begin (generated by llm-dlc/tools/sync.py) -->
| Started | Session | Prompts | Commits | Status |
|---|---|---|---|---|
| 2026-11-06 10:48 UTC | [Feature loop run review actions](traces/3761db96-b870-47f7-aded-2ba264c165f4/summary.md) | 11 | 13 | open |
| 2026-11-05 23:34 UTC | [Last feature loop results](traces/7cacdb56-4c74-4880-a06e-f98031283c0f/summary.md) | 127 | 30 | ended |
| 2026-11-05 10:47 UTC | [`build.py` orchestration feature loop](traces/cc65240f-1df0-42e0-81ce-41a80fa61028/summary.md) | 54 | 14 | ended |
| 2026-11-04 13:08 UTC | [build.py newProblems schema mismatch](traces/7605134a-8541-491b-9c22-2594d85b8a6e/summary.md) | 6 | 10 | ended |
| 2026-11-04 05:07 UTC | [FEATURE_LOOP_MEMORY_MAX memory limit](traces/6751f657-78ac-484c-8e36-eef607a6c325/summary.md) | 4 | 2 | ended |
| 2026-11-04 04:45 UTC | [Verification pipeline queue](traces/8fc64b88-3223-4fe7-a67d-3a75c5768bbf/summary.md) | 13 | 19 | ended |
| 2026-11-03 23:49 UTC | [Langfuse sync background script](traces/4f570b0b-cc13-4aa1-91b3-c89839f5286b/summary.md) | 5 | 3 | ended |
| 2026-11-03 14:52 UTC | [5dfbc1bc-4bd7-4b48-a637-44ff84065b6b](traces/5dfbc1bc-4bd7-4b48-a637-44ff84065b6b/summary.md) | 93 | 25 | ended |
| 2026-11-03 13:54 UTC | [Overnight Spring Boot feature loop commits](traces/20803daf-7ba0-4214-a79c-415a27f48a7b/summary.md) | 7 | 5 | ended |
| 2026-11-03 13:48 UTC | [sync.py redaction allow list](traces/0d3dce51-36ed-453d-bd2c-6adeaf97b230/summary.md) | 6 | 2 | ended |
| 2026-11-03 13:40 UTC | [Verification pipeline job queue](traces/bb39c22a-5d6e-48b2-af0a-45d8b973d822/summary.md) | 1 | 1 | ended |
| 2026-11-03 13:35 UTC | [Sync.py review findings](traces/52bfcdac-3587-46f2-b2cd-c49c2f7a5021/summary.md) | 6 | 1 | ended |
| 2026-11-03 04:08 UTC | [374d30d0-bacd-47e6-8f29-163603b6560f](traces/374d30d0-bacd-47e6-8f29-163603b6560f/summary.md) | 1 | 1 | ended |
| 2026-11-03 02:23 UTC | [a08d738e-5517-4e20-9807-72e419657081](traces/a08d738e-5517-4e20-9807-72e419657081/summary.md) | 13 | 7 | ended |
| 2026-11-02 00:14 UTC | [Real-world examples folder restructure](traces/dfa830a1-4fb4-4d80-8e2c-d612b759742d/summary.md) | 12 | 7 | ended |
| 2026-11-01 21:47 UTC | [JVM contract bytecode verification skill](traces/2e359813-25c2-4259-888b-42d3a5f0eee6/summary.md) | 12 | 16 | ended |
| 2026-11-01 14:42 UTC | [Feature-loop memory safeguards](traces/a308f9d3-8d8a-42ca-b074-d388818c2418/summary.md) | 45 | 52 | ended |
| 2026-11-01 11:13 UTC | [Feature loop cycle recovery](traces/8316bdd0-1ff3-47df-9d3d-67f2a2bdd1a6/summary.md) | 3 | 1 | ended |
| 2026-10-31 22:46 UTC | [Llm-dlc loop script](traces/b337c438-c453-4e77-9b04-ac89ec125c41/summary.md) | 7 | 3 | ended |
| 2026-10-31 16:29 UTC | [Rust Java formal verification library](traces/360e8b8b-8e0c-4b2a-bd69-25b32f2a54eb/summary.md) | 270 | 69 | ended |
| 2026-10-31 15:07 UTC | [Trace data pipeline for llm-dlc](traces/24d088fa-8a2f-419c-9283-2557487b7d9f/summary.md) | 6 | 7 | ended |
| 2026-10-31 14:07 UTC | [Sync script PII guards](traces/451eff2d-fef0-403d-bccc-98abb77fb2a9/summary.md) | 5 | 5 | ended |
| 2026-10-31 01:39 UTC | [LLM formal verification examples](traces/8194b9db-b315-48b6-b0eb-b6280f96252b/summary.md) | 21 | 11 | ended |
| 2026-10-31 00:53 UTC | [Formal verification example 004 proof](traces/57737931-7b2a-41eb-9b5c-ab2e3cef9b69/summary.md) | 6 | 3 | ended |
| 2026-10-24 14:07 UTC | [WSL Java formal verification setup](traces/560d5e98-2825-4bc2-90e2-39953d65d9c0/summary.md) | 50 | 14 | ended |
| ? | [3048539b-c311-5e68-b776-b0f94623d4ac](traces/3048539b-c311-5e68-b776-b0f94623d4ac/summary.md) | 0 | 0 | ended |
<!-- index:end -->
