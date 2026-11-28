# A queue of briefs

A page of the [`orchestrate-run`](SKILL.md) skill: read it in full before you add to the queue or hand over between
two briefs, and again after a compaction. What [`SKILL.md`](SKILL.md) says of every run holds here too.

When the user queues briefs, they run one after the other, each as a run of this skill with a setup phase first.
The queue is data, not your memory: [`llm-dlc/tools/brief_queue.py`](../../../llm-dlc/tools/brief_queue.py)
keeps it in `llm-dlc/loop-summaries/queue.json`, logs every change to the committed `llm-dlc/loops/queue.jsonl`,
and does the handover between two briefs. Any session may add, move or remove a brief; a session that takes the
watcher's place reads `brief_queue.py status` and carries on.

- **Adding.** A brief copied or linked into the user's inbox (`~/code/scripts/analysis/queue/`) is added by the
  next `inbox` or `next`, in the order the files were put there. A link to the user's original makes that original
  the brief's source, so its setup notes go there. `brief_queue.py add BRIEF [--first | --after NAME] [KEY=VALUE ...]`
  adds any other. Each brief's copy goes into `llm-dlc/loops/` unchanged and is committed. The defaults are what
  the user asked for with each brief until now:
  - an Opus 5.5 setup phase;
  - Codex Astra 6.2 at max effort, continuing the session of the domain run before it;
  - the workspace the domain runs share, and no limit on cycles;
  - the two "aspirational" texts of `llm-dlc/loops/domain-prompt-aspirational.md`.

  A brief overrides a default with `KEY=VALUE`, or with `queue.KEY: VALUE` lines in a `---` block at its top.
- **A list of pull requests** is added the same way, by the inbox or `add`. A file whose every line is a GitHub
  pull request's link is taken for one, and `--generate` says so for any other. Its entry is a generation
  (see [`generation.md`](generation.md)):
  - The list's copy goes into `llm-dlc/loops/`.
  - The author writes the brief into `llm-dlc/loops/NAME-brief.md`.
  - Once it is landed and checked, its copy goes beside the list as `NAME-brief.md` and is **queued right after the
    list** as the brief `NAME-brief` (`generatedBrief=next`, the default; `end` puts it at the end of the queue). That copy then counts as the user's original: the setup notes go there, and the
    domain run's texts name it. From the brief on, nothing differs from a brief the user wrote.

  Until the queue is further productized, you manage its order (the user, 2026-11-25): `move` a generated brief
  if another order serves the user better, and tell them.
- **The handover is `brief_queue.py next`.** Run it when a brief's run has finished, with `--finished`, and when
  the queue has nothing running. It does every step that is due and records each:
  - land the run;
  - checkpoint develop;
  - clear the work folders of failed jobs whose originals are in the archive;
  - move the workspace onto the line;
  - start the next brief's setup run. After the setup run: land it, put its notes into both copies of the brief,
    and start the domain run.
  - For a list of pull requests: start its generation run. After it: land it, check the brief (the `brief` step),
    put its copy beside the list, queue that right after the list (or at the end), and checkpoint develop.

  A step that fails is named, and the next call carries on from it. It never promotes `main` and never runs the
  default tests: tell the user when a brief is done, and they decide both.
- **A hold pauses the queue between briefs.** When the user asks to pause after the run under way (to work on the
  code by hand, say), run `brief_queue.py hold --reason "..."`. The handover goes on as usual: `next --finished`
  still lands the run, checkpoints develop and clears what is safe to clear, but it starts no run (no generation,
  setup or domain run) and says so. `status` shows the hold. Only the user ends it: when they say to resume, run
  `brief_queue.py resume` and then `next`, which starts what is due from develop as it is then. To pause after a
  later brief instead, set it `brief_queue.py set NAME holdAfter=yes`: the briefs before it run on, and the queue
  holds itself once that brief is done.
- **"Finished" is your judgment, as `stop` is.** A setup run that stopped to wait on its jobs is not finished:
  `single_run.py jobs`, then `start`, as [`setup.md`](setup.md) says. The setup run is watched by that page's rules,
  and the domain run by [`SKILL.md`](SKILL.md).
- **A waiting brief makes a plateau a reason to stop.** The user wants runs to go on while they advance. But when
  a brief is waiting and the run has had two cycles in a row with no claim decided, answer `stop`, give that as
  the reason, and hand over with `next --finished`.
- **When a client refuses a session** (Codex's cybersecurity filter, say), start the brief's domain run again by
  hand:
  - use a new name and a new session, with the queue's prompt files (`~/.cache/in-the-loop/prompts/NAME-*.txt`);
  - point the queue at it with `brief_queue.py set NAME run=NEWNAME`;
  - for later briefs to continue the new session, nothing is needed: `previous` follows the queue's last start of
    the same client, kept per client, so a Codex brief never continues a Claude session or the reverse. For a run
    started by hand, record it with `brief_queue.py defaults --last-session ID --last-session-client CLIENT`.
- **Report from the queue:** `brief_queue.py report` gives each brief's runs, legs and landing.
