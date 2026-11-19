# Operating notes

Rules of practice learned in earlier runs, each with its reason. [`CLAUDE.md`](../CLAUDE.md) points here: read
this page before a merge, a default test run, a build made apart from the checkout, a fetch from outside, or work
in a fresh jj workspace. Any agent reads the same page, whichever client runs it (Claude Code or Codex); until
2026-11-18 these rules were in one client's private memory, where another client, and a fresh workspace, did not
find them.

A rule that another agent would need is written here or in `CLAUDE.md`, not only in a client's own memory.
"The user" is the person who runs this repository. A date is when the rule was learned or decided.

## Temporary files stay off /tmp

On the machine these loops run on, `/tmp` is memory (a tmpfs) with a quota per user, and test runs leave a great
deal there. On 2026-11-18 it filled (about 1.45 million files, VF-036): every shell command still ran, but its
output was lost ("Disk quota used up", EDQUOT), and shell here-documents failed. On 2026-11-17 it ran out of
inodes instead and no command could start (ENOSPC: check `df -i /tmp`).

- Set `TMPDIR` to a folder under `~/.cache/in-the-loop/` for tests, probes and scratch files, and redirect a
  command's output to a file there when the shell loses it. A Codex turn started by `agent_client.py` gets such
  a folder of its own.
- Never put `TMPDIR` inside the checkout for a test run: `llm-dlc/tools/test_claude_setup.py` and
  `test_performance.py` then fail, because the repository's `CLAUDE.md` turns up above their fixtures.
- Deleting what is already in `/tmp` is the user's decision: a run under way has live folders there.

**Why:** a session that cannot see its commands' output cannot work, and one that clears `/tmp` breaks another
session's tests.

## The default test run is run when it is due, not after every change

The user's decision, 2026-11-18: the default test run (`python3 lib/tools/test_costs.py run`) was one of the
biggest bottlenecks of a run with frequent merges. After a merge use `python3 lib/tools/default_run.py
after-merge` (`--final` after a run's last merge), which runs it only when the last one failed or none has
passed in the last hour. And: tests are never run because `lib/tests/costs.json` changed. The inventory is an
indicative file, left to evolve; no rule selects tests from it.

**Why:** the run takes minutes and gigabytes, and it ran after every merge; a `--changed` run that took in all
of `cargo test` because `costs.json` had changed filled a stream's memory and got it killed (VF-037).

## A blocked external artifact: an anonymous, verifiable copy first

When an upstream build needs an artifact that is behind a login or gone (examples 305 and 307, 2026-11-14), look
first for a copy anyone can download and check by hash: the source's git tags, public mirrors of the repository
it came from, the Wayback Machine, published releases or milestones with the same sources (compare git blob
ids). With no independent hash, propose a check of the output: compare the built class with a published
artifact of identical source. Only then a narrower slice of the example. Credentials come last.

**Why:** a reader of the published history must be able to reproduce the build without the user's accounts.

## Reading the web: the headless browser is for reading

Since 2026-11-19 the machine has a browser for pages a plain fetch cannot read, such as pages rendered by
JavaScript: Javadoc, specifications, recent papers, upstream documentation. It is Google's Chrome for Testing
headless shell (pinned at 158.0.8127.36), at `~/.cache/in-the-loop/browsers/current/chrome-headless-shell`.

- **Both clients have it** as the MCP server `chrome-devtools` (`chrome-devtools-mcp@1.13.0`, registered for the
  user in `~/.claude.json` and `~/.codex/config.toml`). It runs headless, with a new empty profile for each
  session (`--isolated`), and with the package's usage statistics to Google turned off. From a shell:
  `chrome-headless-shell --headless --user-data-dir="$(mktemp -d)" --dump-dom URL`.
- **Prefer an API or a plain fetch** where one serves the content (arXiv, OpenAlex, Semantic Scholar, the GitHub
  API, a raw file): the browser is for what they do not reach.
- **Read only.** No logins, no accounts, no forms submitted, nothing posted. Never `--no-sandbox`: Chromium's
  sandbox is what keeps a hostile page from the user's files. It works here because of the AppArmor profile
  `/etc/apparmor.d/chrome-for-testing`, which lets this binary create the user namespaces Ubuntu (23.10 and
  later) otherwise refuses; without it the browser stops with "No usable sandbox!".
- **A download is untrusted data**: each in a new folder of its own, never run, read with scripts kept elsewhere
  (`python3 -I`).
- **Name each source** in a research note by its URL and the date it was read, with the hash of a file that was
  downloaded, so that a reader of the published history can find it again.
- **A newer Chrome** is installed beside the old one (`npx @puppeteer/browsers install chrome-headless-shell@VERSION
  --path ~/.cache/in-the-loop/browsers`) and `current` repointed at it. The AppArmor profile's path pattern covers
  every version, and both registrations name `current`, so nothing else changes.

**Why:** the project needs sources that research APIs do not serve, and a browser that follows links on the open
web must not carry the user's logins or write anywhere in their name.

## Check for a decision before fixing an infrastructure problem met mid-task

Look in [`verification/findings.md`](../verification/findings.md) and the run's decisions
(`python3 llm-dlc/tools/decisions.py list`) before building a fix for something the machine or the tooling did
to you. On 2026-11-17 a per-run `TMPDIR` for the test runner was built and taken out again the same day: the
user had already settled the matter (VF-036, "nothing to change now").

**Why:** the fix was work the user had decided against, in shared code other streams were using.

## A fresh jj workspace

- `python3 lib/tools/test_costs.py estimate` there has none of the session logs the default checkout has, so
  it rewrites the provenance and the `estimated` counts of every row of `lib/tests/costs.json`. Keep the old
  file, run `estimate`, take only the new tests' rows (whole) into the old file, set the changed files' summary
  counts, and run `python3 lib/tools/test_costs.py lint`.
- When the default checkout's `@-` is in the middle of a merge it has two parents, and `jj workspace add -r
  @-` makes a conflicted merge: base the workspace on the line's single commit.
- `python3 llm-dlc/tools/sync.py adopt-logs` brings in the logs of the sessions whose commits the workspace
  holds. Without them `check` reports "log … is neither stored locally nor uploaded" for other sessions' logs;
  those clear at the merge, and are not this workspace's errors. Never copy another workspace's `logs` folders
  into `llm-dlc/traces/` itself: on 2026-11-16 that put 660 logs where they are not ignored, and the next commit
  took them in. Look at `jj diff --stat -r @-` after a commit from a side workspace.

**Why:** each of these cost a session an hour, or put files into a commit that did not belong to it.

## A workspace that goes stale

`sync.py commit` adds `LLM-Trace` lines to earlier commits. Run in another workspace, it rewrites commits a side
line is based on, jj rebases that line, and the side workspace's working copy is stale. `jj workspace
update-stale` then resets the files on disk: edits jj had not yet seen were silently undone (2026-11-06, and
again 2026-11-17), and the working-copy change can be left in two copies.

- Use `python3 llm-dlc/tools/unstale.py`, as `CLAUDE.md` says, never `update-stale` itself.
- In a side workspace, run a jj command (`jj st`) after each batch of edits, so jj has seen them.
- Restore generated files (`llm-dlc/README.md`'s session table, `llm-dlc/index.json`) from `@-`, not from a
  backup: a backup also takes back what the base had gained.

## A library built apart from the checkout

`git archive REV lib | tar -x` gives every file the commit's time. Exported over an earlier export and built
into a `CARGO_TARGET_DIR` that already holds newer artifacts, cargo takes the old library for fresh: on
2026-11-17 a test "showed" a stream's fix failing, on an rlib built from the commit before it. After exporting,
`find lib/src lib/tests lib/models -type f -exec touch {} +`, or use a fresh target folder, and cross-check a
verdict against the CLI of the same build.

**Why:** a report that another line's fix fails, made from a stale build, is false and costs that line a cycle.

## Merging lines that both committed

- Every `sync.py commit` rewrites four generated files (`llm-dlc/index.json`, `llm-dlc/traces/README.md`,
  `llm-dlc/traces/metrics.json`, the session table in `llm-dlc/README.md`), so two lines that both committed
  conflict in all four. After the merge run `python3 llm-dlc/tools/sync.py regenerate`, which rewrites them from
  the session files and lists any other conflict; resolve only what it lists, never the four by hand.
- `check` reads only the commits of `::@`, so a "session … has no manifest" error is not to be expected from
  another workspace's commits.
- One case is known: a stream that merged another stream's commit into its line stamps that commit with its own
  session's `LLM-Trace` line at its next `sync.py commit` (it takes every commit of its line made during the
  session for its own), and `check` on the other line then says the session has no manifest. See which
  workspace made the change (`jj op show`), report it, and don't edit the trace lines: it clears when the lines
  meet (2026-11-17).
- A conflict in `llm-dlc/allowlist.json` whose sides differ only by added proposals is settled as `CLAUDE.md`
  says, with `jj restore --from <side>`, never by writing the file. If an approved entry differs, the merge
  needs the user.
- Where two lines hold copies of the same change, jj can keep both copies of a block with no conflict at all
  (a block of `feature-loop.sh`, 2026-11-16). Compare the merged file with the side that should win, not only
  the conflict hunks.

**Why:** the four conflicts silenced every integration check after the streams' first commits in four runs, and
in one that hid a real bug until the merge.

## Shell commands that set off the commit hook

A shell command whose text holds `jj commit`, `jj ci`, `jj new` or `git commit` sets off this repository's
commit hook in a Claude Code session, whatever the command was for. Commit with `sync.py commit`, and make a
merge with `jj rebase -r @ -d A -d B`. The same holds for a Codex turn that `agent_client.py` carried: it runs the
hook after the turn. For the same reason, never start a headless probe of a client (`claude
-p`, `codex exec`) with a development checkout as its directory, where it would be traced as a session of the
repository: probe from a scratch folder.

## Verification jobs

- A job cannot be withdrawn by deleting its committed job file: the runner reads the files of `@-` and may have
  started it (VF-029, 2026-11-15, a three-hour run stopped by the user 33 minutes in). Lower it with
  `python3 verification/pipeline.py prioritize`, or tell the user.
- Before queuing a long proof-tier job for the tests a change touched, check cheaply whether it can say anything
  new: whether the generated harness bytes differ from the previous commit's, and whether
  `verification/findings.md` already has an open finding on the same tests. If it is not needed, don't queue
  it, and say why in the commit.
- A plain `pipeline.py run` collects nothing until every job of its batch has ended, so one long job delays the
  results of the short ones queued with it.
- `default_tests.py queue` queues a run at `@-`: commit the work first, then queue, then commit the job.

**Why:** a started job burns machine time and leaves a stray result that another agent has to triage.

## The machine's budget

The machine the loops run on has 30 CPUs and 105 GiB, with no swap (since 2026-11-14). 13 GiB and 2 CPUs are
never handed out: they are the user's own terminals, the background sessions and the operating system. Of the
rest, each feature loop takes 12G (`FEATURE_LOOP_MEMORY_MAX=12G`, the user's choice: a 4G cap had processes
killed eight times in one run) and about 2 CPUs, an integration check 6G, and the verification runner what is
left: its table by situation is in the machine's `pipeline.local.toml` (`~/.config/in-the-loop/`), and the
`run-verification` skill says to pick the row that matches. Loops run at half the CPU weight of the user's
terminals. If the machine is resized, the table is redone.

**Why:** memory more than doubled while the CPUs barely grew, so CPUs are what runs out, and a run keeps the
budget it started with.

## Decisions of the user that are written nowhere else

- **Verification pipeline** (2026-11-17): the user plans to rework verification into "a more semantic pipeline
  capability". Until then, add no complexity to `verification/pipeline.py`; what the watcher does with the queue
  is a stopgap.
- **Watching a run** (2026-11-18): three things were left out of the watcher on purpose, not to be patched
  quickly: helping the watcher decide when to stop a run (the user has ideas for later, and "quick fixes may
  present bigger problems than appear at the surface"), the stale cost in summaries (valid, low return), and
  cleaning up workspaces at a run's end ("any unexpected bug may cause us to lose data").
- **Helpers of a brief's run** (2026-11-18): the user names a helper's pane; the watcher never picks a pane or
  starts a helper session itself.
- **The foundation prompt** of a brief's run (`FOUNDATION_PROMPT` in `llm-dlc/tools/brief_run.py`) is the
  user's, kept word for word.
- **Folders** (2026-11-15): the user plans to reorganize the folder structure; until then, move no folders.
- **Workspaces at the end of work**: forgetting a workspace or removing its folder is done at the user's word.
