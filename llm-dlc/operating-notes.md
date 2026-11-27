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

## The default test run belongs to a promotion, not to a landing

The user's decision, 2026-11-18: the default test run (`python3 lib/tools/test_costs.py run`) was one of the
biggest bottlenecks of a run with frequent merges, so after a merge it ran only when due
(`python3 lib/tools/default_run.py after-merge`). Since the process-plumbing brief of 2026-11-21 it is owed only
at a promotion to `main` and at a release, which run it themselves when no passed run covers the commit: not
when an example is done, not when a stream or a run lands, not after a merge. A checkpoint to `develop`
(`sync.py checkpoint`) runs none and confers no test status. Any agent may still run it when it answers a
development question, with `after-merge` (in a memory cap of its own) rather than the bare run. And: tests are
never run because `lib/tests/costs.json` changed. The inventory is an indicative file, left to evolve; no rule
selects tests from it.

**Why:** the run takes minutes and gigabytes, and it ran after every merge; a `--changed` run that took in all
of `cargo test` because `costs.json` had changed filled a stream's memory and got it killed (VF-037).

## Checkpoints and the private archive

- `sync.py checkpoint --rev REV` is how code reaches the remote between promotions, and it is the watcher's to
  run ([`specification.md`](specification.md#checkpoints)). It never forces: when `develop` moved on the remote,
  fetch and bring the line onto it. A refusal names the path or commit and the kind, never the value; a
  credential that reached a commit is taken out of the history before the line is checkpointed, not waived.
- Once a commit is on `develop` it is immutable for jj (the repository's `immutable_heads()` names
  `develop@origin`): `sync.py commit` no longer stamps it, and `jj describe` on it is refused. Don't work round
  that with `--ignore-immutable`: others have fetched the commit.
- `sync.py promote --rev REV` builds in the jj workspace `promote` (the folder `REPO-promote`), which is for
  promotions only: don't work there, and don't remove it (it is moved, not remade, at each promotion; its first
  checkout takes a minute, and a default run there builds `lib/target` anew). To have the gate reuse a run
  instead of running one, run the default run on the commit to be promoted, with nothing uncommitted, before
  asking: a pass of that tree covers the record on top of it. A promotion that stopped is continued by the same
  command; its state is in `~/.local/state/llm-traces/promotions/`, and nothing there is edited by hand.
- When `main` moved under a promotion (someone else promoted), merge `main` into the line by an ordinary merge,
  checkpoint the merge and promote that. Never force `main` or `develop`.
- Redaction decisions are a person's unless `python3 llm-dlc/tools/sync.py delegate status` says a person
  delegated them to a run's watcher. A watcher that wants that asks (`sync.py delegate request --run NAME`) and
  tells the user the code; it never sets it up for itself, and a worker never decides. `sync.py delegate off`
  ends it at once, from any shell, and is the thing to run when the trust boundary changes (another contributor on
  the machine, a client whose rules cannot keep agents from the key in `~/.config/in-the-loop/`).
- Originals are sealed by the tools that produce them (the runner, the collector, `sync.py commit` for
  transcripts) and uploaded in the background. `python3 llm-dlc/tools/artifacts.py status` says what is still on
  this machine only; `upload --drain` finishes what a dead uploader left. Before removing a run directory, a work
  directory or a workspace by hand, check that what it holds is `remote_verified`
  (`artifacts.py list --job ID --include-attempts`), or run `python3 llm-dlc/tools/vm_inventory.py protect` first.
- A test that runs the pipeline or `sync.py` must not seal into this machine's archive: the test runner sets
  `ITL_ORIGINALS_OFF=1`, and a test of capture itself points `ITL_ORIGINALS_HOME` and `ITL_ORIGINALS_STORE` at a
  temporary folder.

**Why:** a force or a rewrite of a published commit breaks every reader of `develop`, and the archive is the only
whole copy of what the pipeline cuts to fit a commit.

## A blocked external artifact: an anonymous, verifiable copy first

When an upstream build needs an artifact that is behind a login or gone (examples 305 and 307, 2026-11-14), look
first for a copy anyone can download and check by hash: the source's git tags, public mirrors of the repository
it came from, the Wayback Machine, published releases or milestones with the same sources (compare git blob
ids). With no independent hash, propose a check of the output: compare the built class with a published
artifact of identical source. Only then a narrower slice of the example. Credentials come last.

**Why:** a reader of the published history must be able to reproduce the build without the user's accounts.

## Blinded studies on a repository that publishes transcripts

In an evaluation with sequestered references, keep case-specific shell input, stdout and stderr inside the curator workspace. A failed command and a JSON map's keys each exposed an original module path during the 2026-11-21 external upgrade run. Use opaque command arguments and capture both streams before the private command starts. Only explicitly shaped progress counts, booleans, fixed dispositions and evidence digests should reach the session. Record any prior exposure on the candidate and tell the user before publishing. The evaluation's [private capture filter](../lib/benchmark/external-upgrades/curation/README.md#keep-private-command-output-out-of-session-traces) includes a process-start example.

## Reading the web: the headless browser is for reading

Since 2026-11-19 the machine has a browser for pages a plain fetch cannot read, such as pages rendered by
JavaScript: Javadoc, specifications, recent papers, upstream documentation. It is Google's Chrome for Testing
headless shell (pinned at 158.0.8127.36), at `~/.cache/in-the-loop/browsers/current/chrome-headless-shell`.

- **Both clients have it** as the MCP server `chrome-devtools` (`chrome-devtools-mcp@1.13.0`, registered for the
  user in `~/.claude.json` and `~/.codex/config.toml`). It runs headless, with a new empty profile for each
  session (`--isolated`), and with the package's usage statistics to Google turned off. From a shell:
  `chrome-headless-shell --headless --user-data-dir="$(mktemp -d)" --dump-dom URL`.
- **Where to look** for a given question (a JDK guarantee, a solver's operator, a Spring fix, a published
  technique, another tool) is in the [research router](research-router.md), host by host.
- **Prefer an API or a plain fetch** where one serves the content (arXiv, OpenAlex, Semantic Scholar, the GitHub
  API, a raw file): the browser is for what they do not reach.
- **Navigating to retrieve material, nothing more.** Clicking, typing into a search box, choosing from a menu
  or filling a form that finds or opens material are fine, as a person browsing the site would do them. No
  logins, no accounts, nothing posted, and no file uploaded: `upload_file` is turned off for both clients
  (a deny rule in `~/.claude/settings.json`, `disabled_tools` in `~/.codex/config.toml`). The user set this on
  2026-11-19, to be reviewed later.
- **Never `--no-sandbox`**: Chromium's sandbox is what keeps a hostile page from the user's files. It works here
  because of the AppArmor profile `/etc/apparmor.d/chrome-for-testing`, which lets this binary create the user
  namespaces Ubuntu (23.10 and later) otherwise refuses; without it the browser stops with "No usable sandbox!".
- **What a page returns is published**: each browser or fetch call and its result are in the session's log, which
  is redacted and published with the commits. Take the part the question needs (`evaluate_script` on one
  section, a short excerpt) rather than a whole page's snapshot, and quote no more of it than a note needs.
- **A download is untrusted data**: each in a new folder of its own, never run, read with scripts kept elsewhere
  (`python3 -I`).
- **Name each source** in a research note by its URL and the date it was read, with the hash of a file that was
  downloaded, so that a reader of the published history can find it again.
- **A newer Chrome** is installed beside the old one (`npx @puppeteer/browsers install chrome-headless-shell@VERSION
  --path ~/.cache/in-the-loop/browsers`) and `current` repointed at it. The AppArmor profile's path pattern covers
  every version, and both registrations name `current`, so nothing else changes.

**Why:** the project needs sources that research APIs do not serve, and a browser that follows links on the open
web must not carry the user's logins or write anywhere in their name.

## Requests to the web are plain, few and one at a time

Every request an agent sends leaves from the user's own address, and a site that takes it for a scraper or a bot
can block that address for the user too. The user decided on 2026-11-19 that agents read the web only in plain,
targeted requests at a low volume. This holds for every tool: `curl`, a script, WebFetch, the headless browser.

- **Plain.** The tool's own User-Agent, never one made to look like a person's browser, and no header that names
  the user or the project. No proxy, VPN or other address to send from.
- **A site that only refuses scripts** (a 403 to `curl`, a page that needs JavaScript) may be read with the
  headless browser, once, as it is: its own identity, no stealth plugins, no flags that hide that it is headless.
- **A check meant for a person ends the attempt**: a CAPTCHA, a "verify you are human" box or puzzle, a login
  wall, HTTP 451, or a check that refuses the browser too. It is never solved or worked round: read the same
  content from another source (an API, a mirror, the arXiv copy, the release on Maven Central), or report that
  it could not be read. A 429 or 503 may be retried once, after its `Retry-After`; a second refusal ends it.
- **One at a time.** No parallel requests (`xargs -P`, threads, several fetches to one host in one turn), at
  least a second between two requests to one host, and an API's own published limit where it is slower (arXiv's
  3 seconds, NVD's 6 without a key).
- **Few.** The requests the question needs, a few dozen at most for a task. No crawling, no following links
  beyond the question, no bulk downloads, no mirroring: where many files are needed, one archive (a git clone, a
  release JAR, a Zenodo record) rather than many pages. A page fetched once is read again from the saved copy.
- **Runs that go on side by side share the address**, with their watchers, so each keeps its research to what
  its task needs.
- **Checking links** (a page's sources, the research router) follows the same rules: one at a time, `HEAD` where
  the server takes it.

**Why:** the user's address is theirs, used for everything else they do. On 2026-11-19 a check of a page's 60 links
sent 12 requests at a time with a browser-like User-Agent: the kind of traffic this rule is there to prevent.

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
  those clear at the merge, and are not this workspace's errors. Any agent may run it without asking, the user
  said on 2026-11-20, and it needs no escalation in Codex's sandbox: it reads the workspaces without a snapshot.
  Never copy another workspace's `logs` folders
  into `llm-dlc/traces/` itself: on 2026-11-16 that put 660 logs where they are not ignored, and the next commit
  took them in. Look at `jj diff --stat -r @-` after a commit from a side workspace.

**Why:** each of these cost a session an hour, or put files into a commit that did not belong to it.

## A workspace that goes stale

`sync.py commit` adds `LLM-Trace` lines to earlier commits. Run in another workspace, it rewrites commits a side
line is based on, jj rebases that line, and the side workspace's working copy is stale. `jj workspace
update-stale` then resets the files on disk: edits jj had not yet seen were silently undone (2026-11-06, and
again 2026-11-17), and the working-copy change can be left in two copies.

- Use `python3 llm-dlc/tools/unstale.py`, as `CLAUDE.md` says, never `update-stale` itself.
- A loop does this itself. `feature-loop.sh` reads `@-` before and after each turn, while its agent isn't working.
  On a stale working copy it runs `unstale.py` there, and says so in its log and summary. It stops for a person
  only when `unstale.py` can't recover. Before 2026-11-24 the loop ended on it with status 1. On 2026-11-23
  21:15 that ended trusted-kernel's second cycle before its verdict, after a turn that had gone well.
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
  the session files and lists any other conflict; resolve only what it lists, never the four by hand. (Since
  2026-11-21 a commit writes its session's manifest alone and these files are rendered at a promotion, so two
  lines conflict in them only when one of them rendered: by `sync.py sync`, a push, or tools from before.)
- A session's own `metrics.json` or `summary.md` left conflicted by a merge is settled the same way, by rendering:
  `python3 llm-dlc/tools/sync.py sync SESSION`, never by hand. The files are functions of the session's log and
  manifest. It is to be expected once, when a line whose tools still write the per-call tables into
  `metrics.json` meets one whose tools do not (2026-11-21).
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

## A landing that conflicts

`single_run.py land NAME` (and the brief queue's handover, which calls the same code in `landing.py`) takes back a
merge that conflicts in real work and says in which files. Two ways on:

- **Have the session that wrote the work rebuild on the line as it is now.** This is the default: it knows what
  both sides meant. Its run is continued (`single_run.py start NAME`), it brings its own line onto the default
  line's last commit and settles what meets, and the run is landed again.
- **Resolve it by hand**, when the conflict is small and you can see how both sides meet. In the default
  workspace, with nothing uncommitted there:
  1. make the merge of the line's last commit and the workspace's:
     `jj rebase -r @ -d @- -d WORKSPACE@-` (the working-copy change becomes the merge; the words for making a new
     change would set off the commit hook, see below);
  2. run `python3 llm-dlc/tools/sync.py regenerate`, which settles the generated trace files and lists every other
     conflict;
  3. resolve what it lists, and nothing else;
  4. run the tests of what came in (`python3 lib/tools/test_costs.py run --changed`);
  5. commit the merge with `sync.py commit`, saying what met and how it was settled;
  6. run `single_run.py land NAME` again: it finds the line has the work and records the landing.

  A merge that does not come out clean is taken back (`jj abandon` the merge, with the working copy back on the
  line's last commit) and reported to the user.

**Why:** until 2026-11-27 this procedure was written only on the page of the proof run's watcher, which is retired
([`retired.md`](retired.md)), and two skills pointed there for it.

## A test of the trace tools writes nowhere in the checkout

A test that calls `sync.cmd_sync`, `cmd_push` or `cmd_regenerate` either points `sync.TRACES` (and what is
derived from it) at a folder of its own, or stands in for every step that writes under `llm-dlc/traces/`.
After running such tests, `jj st` should list nothing under `llm-dlc/traces/` that you did not mean; if it
does, `jj restore --from @- llm-dlc/traces` puts the files back, and the test is what to fix.

**Why:** `test_performance`'s `Sync` test stood in for some of a sync's steps and let the others run on the
real tree. It went unseen while every commit kept the generated files current. Once rendering was deferred it
rewrote the checkout's stale summaries on each run, and on 2026-11-21 a new rendering step rewrote all 207
session files there in one test run (seen in `jj st` before the commit, and put back).

## Shell commands that set off the commit hook

A shell command whose text holds `jj commit`, `jj ci`, `jj new` or `git commit` sets off this repository's
commit hook in a Claude Code session, whatever the command was for. Commit with `sync.py commit`, and make a
merge with `jj rebase -r @ -d A -d B`. The same holds for a Codex turn that `agent_client.py` carried: it runs the
hook after the turn. For the same reason, never start a headless probe of a client (`claude
-p`, `codex exec`) with a development checkout as its directory, where it would be traced as a session of the
repository: probe from a scratch folder.

## Waiting for a command to finish: not by `pgrep -f` on its text

Don't wait for another command with `until ! pgrep -f 'python3 llm-dlc/tools/sync.py commit'; do sleep 10; done`
or anything like it. The waiting shell's own command line holds the pattern, so `pgrep -f` always finds it and the
loop never ends. Two setup agents sat in such loops on 2026-11-25, long after their commits had landed; the second
had four of them, the oldest 40 minutes old. Run the command in the foreground, or wait on its process id
(`wait PID`, or `while kill -0 PID 2>/dev/null; do sleep 10; done`). If you must match by name, use a pattern that
can't match itself, such as `pgrep -f '[s]ync.py commit'`.

A watcher that finds a run held by such a loop ends it with `python3 llm-dlc/tools/single_run.py unhang NAME` (since
2026-11-26; `--dry-run` first names what it would end). It ends only a wait loop at least ten minutes old whose
`pgrep -f` pattern nothing but the loop itself matches, by its pid, and records it in the run's `unhang.jsonl`. It
replaced the user's delegation of 2026-11-26 to end such loops by hand (VF-069).

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
- A job declares every tool its steps call (`--requires jvmcontract`, `java`, `javac`, ...), and its pass must
  depend on something only a real run produces: a new record, a count, a named line of output. Without the
  requirement a step that calls the checker ends at once with "no built native checker"; a step written to accept
  an exit of 1 (which a run with refuted claims also ends with) then passes on nothing. Job
  `20261121-194629-345-native-selectors-again-the-run-packs` passed that way in 1.2 s (2026-11-21); a result that is
  much faster than its estimate is read before it is believed.

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

## The kill order when memory runs out

The user's rule (2026-11-24): should the machine run short of memory, no open tmux window goes first, nor any
session, watcher or agent. Verification jobs go first, and the agents then decide how to regroup. The order:

| Goes | What | How |
|---|---|---|
| first | every process of a verification job | the runner keeps `memory_floor` (8G) free, and under it stops its newest job at once; each step starts at `oom_score_adj` 1000 (`job_oom_score_adj`) |
| second | an agent's test run (`test_costs.py run`, so `default_run.py` too) and a capped probe | `oom_score_adj` 500 (`join_kill_order`, `choom -n 500` in the probe command) |
| last | the tmux windows: Claude and Codex sessions, the watcher, a loop's agent, the runner | `oom_score_adj` 0, as they start |

- An ordinary user can raise a process's `oom_score_adj` but never lower it, so the order is made by raising the jobs,
  not by protecting the sessions. A scope's `OOMScoreAdjust=` is refused for scopes on this systemd: the step wrapper
  writes `/proc/self/oom_score_adj` instead, and whatever it starts inherits it.
- A cap still kills inside its own scope first: a job over its `MemoryMax`, or a loop over its cap, loses its own
  biggest process. Start a heavy inline command (a build, a long script) with `choom -n 500 --`, so that inside a
  loop's cap it dies before the agent does.
- **Regrouping.** A job the runner stopped for the machine's memory is `cancelled` and runs again when there is
  room. A second time, it is `out-of-memory` with `memoryStop`, as is a job the kernel killed under its own limit
  (`limitOoms` 0; `attention` says so). Neither is a verdict, nor a reason to give the job more memory: run fewer
  workers, raise its `--memory` estimate so fewer run beside it, or split it, and find what took the room.

**Why:** on 2026-11-22 a global OOM killed the watcher's window, with the runner in it, and at 04:16 on 2026-11-24 a
loop's 20G cap killed a process beside its Codex agent. Every process had `oom_score_adj` 0, so the kernel took the
biggest, whoever's it was.

## Decisions of the user that are written nowhere else

- **Verification pipeline** (2026-11-17): the user plans to rework verification into "a more semantic pipeline
  capability". Until then, add no complexity to `verification/pipeline.py`; what the watcher does with the queue
  is a stopgap.
- **Watching a run** (2026-11-18): three things were left out of the watcher on purpose, not to be patched
  quickly: helping the watcher decide when to stop a run (the user has ideas for later, and "quick fixes may
  present bigger problems than appear at the surface"), the stale cost in summaries (valid, low return), and
  cleaning up workspaces at a run's end ("any unexpected bug may cause us to lose data").
- **Sessions beside a run** (2026-11-18, said of the helpers a brief's streams had): the user names a session
  and its pane; a watcher never picks a pane or starts a session beside its run itself.
- **The foundation prompt** of a brief's streams was the user's, kept word for word. That workflow is retired
  ([`retired.md`](retired.md#multi-agent-brief)); the text is `FOUNDATION_PROMPT` in `brief_run.py` at the last
  commit that has it.
- **Folders** (2026-11-15): the user plans to reorganize the folder structure; until then, move no folders.
- **Workspaces at the end of work**: forgetting a workspace or removing its folder is done at the user's word.
