# Retired workflows and commands

What this repository no longer has, what replaced each thing, and where to read it as it was.

Nothing here was removed from the history of work. Every file an entry names is in the repository's history, and
the traces, decision records and results of the runs that used it are untouched. The user decided the retirement
on 2026-11-27: the project converges on one run skill, `/orchestrate-run`, and every other proof workflow is
outdated.

## Where to find what was retired

- **The last commit with everything:** change `ulxlynunxlll`, tagged `before-orchestrate-run` once it is on
  `develop`. Each entry also names the change that removed it; that change's parent is the last commit with it.
- **To read a file as it was:** `jj file show -r 'ulxlynunxlll' PATH`, or with git
  `git show before-orchestrate-run:PATH`.
- **To see what a removal took out:** `jj show --stat CHANGE`, with the change an entry names.

## How this page is kept

- **Status.** An entry is `planned` while its files are still in the repository, and `retired` once they are gone.
- **Names.** Each entry lists the names that should no longer turn up in live files: skills, commands, scripts.
- **The check.** `python3 llm-dlc/tools/retired.py check` lists every live file that names something `retired`
  in a paragraph that does not point at this page, every retired file that is still here, and every historical
  page or finding that names something retired without its line. `llm-dlc/tools/test_retired.py` runs it in the
  default test run, so a new page or docstring that sends a reader to a retired command fails there.
- **Three kinds of file:**
  - *Live* files are instructions and code an agent acts on: `CLAUDE.md`, the READMEs, the operating notes, the
    skills, the tools. They are rewritten, and where they described a retired workflow they point here.
  - *Historical* pages are briefs, results pages and findings that agents still open: the pages of
    `llm-dlc/loops/` that are neither live nor records, and each entry of `verification/findings.md`. Their text
    is left as it was written. One that names something retired gets one dated line that points here, at a
    page's top or as the first line of a finding's entry. `python3 llm-dlc/tools/retired.py banners --write`
    writes the lines that are missing, from this page's entries.
  - *Records* are never edited: `llm-dlc/traces/`, `llm-dlc/index.json`, the decision records, verification
    jobs and results, the queue's copies of the user's briefs and the briefs written for it (the pages
    `llm-dlc/loops/queue.jsonl` names), and the provenance an example carries. Studies that
    pinned the tools of the revision they ran on are records too, and still name retired files
    (`lib/benchmark/external-upgrades/`, `lib/benchmark/startup-facts/freeze.py`, `verification/blind-caller/`):
    they read those files from that revision, never from the working copy.
- **Adding an entry:** give it a `###` heading and the same six lines as the entries below.

## Entries

### single-agent-run

- **Status:** retired
- **What it was:** the skill a watcher ran one agent's run with: a domain run, a setup phase, a generation phase
  and the queue of briefs.
- **Replaced by:** `/orchestrate-run`, the same skill under a new name, with one page for each kind of run. Its
  commands are unchanged: `single_run.py` and `brief_queue.py`, and a run's folder is still `single-NAME`.
- **Names:** `single-agent-run`
- **Files:** `.claude/skills/single-agent-run/`, `.agents/skills/single-agent-run`
- **Removed in:** change `sylnnqzvumoo` (2026-11-27), which renamed it

### multi-agent-brief

- **Status:** retired
- **What it was:** a brief run as parallel streams. A foundation session on Fable 5.2 built what every stream
  would wait for, each stream ran a loop in a jj workspace of its own, and the watcher merged each stream the
  moment it finished. It had inboxes for telling a stream something, a rolling integration line, merge orders
  for lines that conflicted, and helper sessions in tmux panes. It was called `/run-brief` until 2026-11-20. The foundation
  session's prompt, which was the user's text, is `FOUNDATION_PROMPT` in `brief_run.py`.
- **Replaced by:** `/orchestrate-run`. Parallel work is several runs, each in a workspace of its own
  (`single_run.py start NAME --workspace WS`), each landed by `single_run.py land`. The foundation stage is an
  ordinary first run. Nothing replaces the inboxes, the integration line, the helpers or
  the transfer of a session to another machine. What the surviving tools shared with it is in `run_common.py`,
  `landing.py` and `queue_keeping.py`.
- **Names:** `multi-agent-brief`, `run-brief`, `brief_run.py`, `run-streams.sh`, `streams_status.py`,
  `inbox.py`, `integration.py`, `foundations-integration.sh`, `cleanup-integration.sh`,
  `example-targets-integration.sh`, `application-core-integration.sh`, `transfer-session.sh`
- **Files:** `.claude/skills/multi-agent-brief/`, `.agents/skills/multi-agent-brief`,
  `llm-dlc/tools/brief_run.py`, `llm-dlc/tools/run-streams.sh`, `llm-dlc/tools/streams_status.py`,
  `llm-dlc/tools/inbox.py`, `llm-dlc/tools/integration.py`, `llm-dlc/tools/foundations-integration.sh`,
  `llm-dlc/tools/cleanup-integration.sh`, `llm-dlc/tools/example-targets-integration.sh`,
  `llm-dlc/tools/application-core-integration.sh`, `llm-dlc/tools/transfer-session.sh`,
  `llm-dlc/tools/test_brief_run.py`, `llm-dlc/tools/test_inbox.py`, `llm-dlc/tools/test_integration.py`,
  `llm-dlc/tools/test_streams_status.py`
- **Removed in:** change `kkkqupwwxupp` (2026-11-27)

### proof-loop

- **Status:** retired
- **What it was:** the proof run behind `/prove-java-change` in a development checkout. A watcher started a
  session that evaluated the changes and designed their claims, a session that set the examples up, and a proof
  loop that took one example at a time ("Formally prove example NNN as elegantly and efficiently as possible"),
  moving to the next while a proof ran. The user confirmed the claims before a proof started.
- **Replaced by:** `/orchestrate-run`. A list of pull requests is written into a brief by a generation phase,
  which takes the place of the claim design; a setup phase does the mechanical setup; a domain run proves. The
  checks an example needs before a run (`preflight`) and the two product commands the tool had gained
  (`startup-facts`, `public-observation`) are in `examples/tools/`.
  `prove-plan.schema.json`, the plan's format, is kept: the scaffold and one study still write and read it. So
  are `changes.py` (where each example stands) and `doctor.py` (whether the machine is enough, and a loop's
  memory budget), which the surviving tools use.
- **Names:** `watch.py`, `prove-loop.sh`, `watch-summary-template.md`, `prove-plan-template.md`
- **Files:** `.claude/skills/prove-java-change`, `.agents/skills/prove-java-change`, `llm-dlc/tools/watch.py`,
  `llm-dlc/tools/prove-loop.sh`, `llm-dlc/watch-summary-template.md`, `llm-dlc/prove-plan-template.md`,
  `llm-dlc/tools/test_watch.py`, `llm-dlc/tools/test_prove_loop.py`
- **Removed in:** change `ykqmkpuomlqw` (2026-11-27)

### loops-by-hand

- **Status:** retired
- **What it was:** `feature-loop.sh` run by name or with a brief's file. The moonshots repeated one line every
  cycle (`features`, `tla`, `spring`, `relational`); the templated moonshots took one item of a list at a time
  (`prove-examples`, `prove-change`) with a judge outside the session saying when an item was finished; a brief
  ran by name (`engines`, `foundations`, `cleanup`, `application-core`, `example-targets`) or as `FILE.md`, with
  its own loop settings, a Progress section and a status line.
- **Replaced by:** `/orchestrate-run`. `feature-loop.sh` is kept as the loop under a run and has one kind left,
  `single-agent`, which `single_run.py` starts; it refuses the other names with a pointer to this page. The loop statistics still count every earlier loop
  (`llm-dlc/traces/loops.md`).
- **Names:** `feature-loop.sh features`, `feature-loop.sh tla`, `feature-loop.sh spring`,
  `feature-loop.sh relational`, `feature-loop.sh prove-examples`, `feature-loop.sh prove-change`
- **Files:** none: the script is kept
- **Removed in:** change `ykqmkpuomlqw` (2026-11-27)

### verification-loop

- **Status:** retired
- **What it was:** a loop that started a fresh Sonnet 5.5 session running `/run-verification` whenever jobs were
  queued or results waited to be collected.
- **Replaced by:** the watcher of a run keeps the queue itself: `single_run.py wait` collects and commits what is
  back and starts the runner (`verification/pipeline.py run`, no model). A session with no watcher runs
  `/run-verification`, which is kept.
- **Names:** `verification-loop.sh`
- **Files:** `llm-dlc/tools/verification-loop.sh`, `llm-dlc/tools/test_verification_loop.py`
- **Removed in:** change `ykqmkpuomlqw` (2026-11-27)

### plugin-and-runtime-mode

- **Status:** retired
- **What it was:** the published product. The plugin `in-the-loop` installed the skill `/prove-java-change`,
  whose bootstrap cloned the repository onto a user's machine and stood it on a release pinned by the digest of
  its tree. Such a copy ran in *runtime* mode: commits were plain, and nothing was traced, redacted or pushed.
  The last release was 0.10.0, cut on 2026-11-16.
- **Replaced by:** nothing yet. The repository has one mode, development. A product entry built on
  `/orchestrate-run` is future work. What is left of the mode: a commit contributed from such a copy carries an
  `In-The-Loop-Runtime` trailer, which `sync.py` still reads so that it never stamps one, and example numbers
  900 to 999, which were a user's own there, stay unused. The benchmark of external upgrades
  (`lib/benchmark/external-upgrades/`) measured this product at pinned revisions: its operator harness names
  the plugin's files and needs a new product entry before it can measure a later revision.
- **Names:** `prove-java-change`, `bootstrap.py`, `release.py`, `claude_setup.py`, `contribute.py`, `runtime.md`,
  `mode.py`
- **Files:** `plugins/`, `.claude-plugin/`, `llm-dlc/runtime.md`, `llm-dlc/tools/release.py`,
  `llm-dlc/tools/mode.py`, `llm-dlc/tools/claude_setup.py`, `llm-dlc/tools/contribute.py`,
  `llm-dlc/tools/test_release.py`, `llm-dlc/tools/test_mode.py`, `llm-dlc/tools/test_claude_setup.py`,
  `llm-dlc/tools/test_contribute.py`
- **Removed in:** change `vwytpwxyvmrr` (2026-11-27)
