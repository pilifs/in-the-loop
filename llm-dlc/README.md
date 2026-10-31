# LLM development lifecycle

This folder is the meta example: how this repo is built with an LLM, in the open.
Every change is published together with the LLM session that made it.
For each commit you can read the message, a summary of the session, and the full transcript.

The formal verification work itself is in [`examples/`](../examples/README.md). This folder is about how it was made.

```
llm-dlc/
  README.md                         this file: the procedure, and an index of sessions
  specification.md                  the specification: identifiers, invariants, storage, redaction
  index.json                        every session and the commits it made (generated)
  summary-template.md               the template for each summary.md
  traces-readme-template.md         the template for traces/README.md
  session-notes/<session-id>.md     optional hand-written note, shown at the top of that session's summary
  traces/README.md                  every session added up: tokens, tools, commits, logs (generated)
  traces/<session-id>/
    summary.md                      what was asked, what was done, what was committed (generated)
    manifest.json                   detailed metadata: stats, models, tokens, commits, logs (generated)
    logs/<sha256>.jsonl.gz          redacted transcript snapshots (gitignored, published on the CDN)
  tools/sync.py                     the hook and commands that capture, redact, publish and check traces
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
4. **Verify:** `python3 llm-dlc/tools/sync.py check` must report 0 errors.

**Push only when the user asks.** Pushing publishes the log, and a person should read it first; see *Redaction* in [`specification.md`](specification.md#redaction).
```bash
python3 llm-dlc/tools/sync.py scan                   # preview: what was redacted, what a person should look at
python3 llm-dlc/tools/sync.py push --bookmark main   # record outstanding traces, check, upload, check, push
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

## Sessions

Newest first. Each row links to the session summary. The [traces overview](traces/README.md) adds them all up.

<!-- index:begin (generated by llm-dlc/tools/sync.py) -->
| Started | Session | Prompts | Commits | Status |
|---|---|---|---|---|
| 2026-10-31 14:07 UTC | [Sync script PII guards](traces/451eff2d-fef0-403d-bccc-98abb77fb2a9/summary.md) | 3 | 2 | open |
| 2026-10-31 01:39 UTC | [LLM formal verification examples](traces/8194b9db-b315-48b6-b0eb-b6280f96252b/summary.md) | 21 | 11 | ended |
| 2026-10-31 00:53 UTC | [Formal verification example 004 proof](traces/57737931-7b2a-41eb-9b5c-ab2e3cef9b69/summary.md) | 6 | 3 | ended |
| 2026-10-24 14:07 UTC | [WSL Java formal verification setup](traces/560d5e98-2825-4bc2-90e2-39953d65d9c0/summary.md) | 50 | 14 | ended |
| ? | [3048539b-c311-5e68-b776-b0f94623d4ac](traces/3048539b-c311-5e68-b776-b0f94623d4ac/summary.md) | 0 | 0 | ended |
<!-- index:end -->
