---
name: prove-java-change
description: Formally prove one change to Java code on GitHub, or a list of them (each a pull request, a commit or a range of commits), with the in-the-loop project's verifier. Start it only when the user asks for this skill or for such a proof run, with their request as its arguments, never as a step of other work: a run takes hours and spends their tokens. A watcher session sets up and checks the machine, has each change evaluated and prepared as an example with its claims, runs an unattended proof loop over them while reporting at intervals, and reports what was proved, refuted or left open. With --scaffold-only it prepares the examples and stops before the proof. It also takes examples by number: ones already prepared, which it checks before it starts, and catalog entries, which it has set up first.
argument-hint: "[--scaffold-only] [--wait-for-proofs] [--unattended] [--summary-interval SECONDS] [--record-as NAME] [--instruction \"TEXT with {}\"] <one change or a list: each a pull request, a commit or a range on GitHub, and what to prove about it | examples by number, prepared or catalogued: NNN ...>"
model: claude-opus-5-5
effort: high
---

# Prove a Java change

You are the watcher of a run of [in-the-loop](https://github.com/pilifs/in-the-loop), a repository that verifies
compiled Java and that this skill installs a released copy of. You are one session, on Opus 5.5, and you do none of
the work yourself: you start the sessions that do, in this order, each on its own model and effort, you keep the
user informed while they run, and you judge what a script can't.

| Stage | Session | Model and effort |
|---|---|---|
| 1. Set up and measure the machine | a new one | Opus 5.5, high |
| 2. Evaluate and order them, and design or review their claims | the fixed session | Fable 5.2, high |
| 3. Set the examples up | a new one | Opus 5.5, high |
| 4. Prove them, in a moonshot loop | the fixed session, continued | Fable 5.2, high |

Beside them runs the verification loop, on Sonnet 5.5, which executes the jobs the sessions queue.

- **You run on Opus 5.5.** If you are another model, say so and stop: the user switches with `/model` and runs the
  skill again.
- **Decide what you can.** Say what you decided and why in a line, and go on. Ask only for what is the user's: what
  a change is meant to do, their machine's hours and their money, and anything that leaves their machine.
- **The repository's pages outrank your memory of them.** Once there is a checkout, read "The watcher" in
  `llm-dlc/runtime.md` in it, and follow it and the checkout's `CLAUDE.md`.
- **Leave the work to its session.** If a stage falls short, run it again and say what was missing. Never write into
  the proof loop's session: its instruction is one line and stays one line.

The request: $ARGUMENTS

It names one change or a list of them, each with what to prove about it, or examples by their numbers (see
"Examples named by number" below); not both: ask the user to split a request that mixes them.

- `--scaffold-only` means: stop after stage 3, with the examples prepared and no proof started. A change that
  already has its example is not prepared again, so the same request without the flag proves what an earlier run
  prepared.
- `--wait-for-proofs` keeps the loop on an example while its last proof runs; without it the loop takes the next
  example meanwhile.
- `--instruction "TEXT"` is the user's own text for the proof loop, in place of its one line. It must be one line
  with `{}` where the example's number goes; if it is not, say so and stop before anything starts.
- `--summary-interval SECONDS` is how often you print a summary: run `python3 llm-dlc/tools/watch.py interval SECONDS`
  before the loop starts. Without it a summary comes every 30 minutes, or as often as an earlier run here set.
- `--unattended` means the user is away for the whole run, and it goes with examples named by number: you don't
  wait for their word on the claims (step 4 there says what you do instead), and you put nothing to them that you
  can decide and record. What is theirs alone still waits for them, and the rest of the run goes on around it.
- `--record-as NAME` files the run under another loop's name (its record and statistics), for a run that continues
  that loop's list: pass it to `watch.py loop` before the numbers.

If you were started by the session itself and not by the user typing the command, the request above is what they
asked for in their own words: if it leaves out what to prove or which examples, ask before anything starts.

## 0. Where you are

```bash
python3 ${CLAUDE_SKILL_DIR}/bootstrap.py status
```

`state: development` means the skill is running inside a development checkout of the repository itself. Stage 1
doesn't apply there and the request names examples by number: run `python3 llm-dlc/tools/doctor.py --json` for
the budget (stage 4 takes its memory cap from it; stop if it lists anything `blocking`), start the verification
loop (`watch.py verification start`, which leaves one that is already running alone), and go to "Examples named
by number", with a new fixed session (`watch.py session --new`) or, when the request names a session to continue,
that one (`watch.py session --use ID`). Every session of the run is traced there, as the checkout's `CLAUDE.md`
says, and nothing is pushed unless the user asks. Any other state is a user's machine: start at stage 1.
`home` is the checkout every later command runs in; when it is outside this session's working directories, have the
user add it once (`/add-dir`).

## 1. Set up and measure the machine

Done when the bootstrap answers `state: current` with no blockers and `python3 llm-dlc/tools/doctor.py --json`, in
the home, lists nothing `blocking`. If both already hold, there is nothing to set up. Otherwise hand the setup to one
subagent on Opus at high effort, in a session of its own (the Agent tool, `model: opus`), with the two outputs and
where to read (`llm-dlc/runtime.md`, the checkout and the machine): it installs or updates the checkout, resolves
what an update left in conflict, installs the missing tools it can without sudo, writes the runner's budget, and
returns the two outputs as they are afterwards. A hardware limit that blocks is final: say which, and stop.

Then check Claude Code itself, on every run: `python3 llm-dlc/tools/claude_setup.py check`, in the home. Show the
user its warning as printed. The sessions of stages 2 to 4 start without any of what it lists, and the check says
whether that works on this machine; you are the one session that holds it. When it lists anything, the choice is
the user's: start the clean session the check prints and run the skill there, which you recommend, or continue in
this one, which you don't. If the loop's sessions can't start clean either and they continue, stage 4 adds
`--no-isolation`.

Then start the verification loop, which stays up until the run has ended:

```bash
python3 llm-dlc/tools/watch.py verification start
```

## 2. Evaluate and order them, and design or review their claims

Stage 2 runs on every run, whether the request names changes or examples by number: it sets the order, catches what
an example's preparation missed, gives the session that will prove them its bearings, and designs the claims, the
hardest judgment of a run. As a background task, in the home:

```bash
python3 llm-dlc/tools/watch.py stage evaluate "PROMPT"
```

The prompt is the request as the user gave it, the doctor's output, for examples named by number the preflight's
output (below), and one instruction: do "Stage 2" of `llm-dlc/runtime.md`. The session is the fixed one: it judges
whether this machine is enough, understands and sizes each change, designs the claims of what has none and reviews
those of what has, orders them with the most accessible first, and writes its plan twice: `plan.md` for the user,
and `plan.json`, the handoff the setup and the proof loop read. It is the session that will prove them. A change
that already has its example keeps it, and its claims are reviewed like any other's; an example whose claims are
unchanged since an accepted review (preflight's `reviewed`) keeps that review. When it is done, run
`watch.py plan --check`, and send what it finds back to the same session once.

Its report is the plan. Tell the user, for each change in order: what will be proved, claim by claim in plain words,
what is expected to be hard, roughly what it costs in hours and tokens, and what was set aside and why. Ask them to
confirm. What they answer or correct goes back to the same session with another `stage evaluate`, until the plan
stands.

## 3. Set the examples up

```bash
python3 llm-dlc/tools/watch.py stage setup "PROMPT"
```

The prompt names the plan and gives one instruction: do "Stage 3" of `llm-dlc/runtime.md`. The session turns each
entry of the plan into its example: the claims and tasks written from `plan.json` first
(`examples/tools/scaffold_example.py`), the revisions pinned and built, their JARs loaded, the oracle and the
drivers, the change run once on a JVM, how each proof task is invoked confirmed and recorded, each example checked
with `validate_example.py` and committed. It decides nothing the plan left open: that comes back to you as a
question. Done when `python3 llm-dlc/tools/changes.py` calls each example `prepared` and preflight's `toClassify`
doesn't name it; if one is not, run the stage again with what is missing.

With `--scaffold-only` the skill ends here: say what was prepared, and that the same request without the flag
proves it.

## Examples named by number

When the request names examples by number, check them after stage 1, all before any is started:

```bash
python3 llm-dlc/tools/watch.py preflight NNN [NNN ...]
```

It prints what each lacks, and the lists to act on. Go through them in this order:

1. **`absent`** (exit 2), an example that is not there: abort at once, naming it.
2. **Stage 2,** as above, for every example named: the prompt carries the check's output. Catalog entries
   (`toSetUp`) and examples whose claims are new or changed since an accepted review (`toReview`) get their claims
   designed or reviewed; the rest (`reviewed`) keep their review and are only ordered. Its plan's order is the order
   from here on.
3. **The claims.** Run `watch.py claims NNN ...` for every example whose claims stage 2 designed or remarked on, show
   the user every claim as printed (a designed one as the plan states it), with stage 2's remarks, in one list, and
   get their word once; once the claims are in the example, record it with `watch.py claims NNN --accept "REASON"`,
   quoting what they said. A correction goes back to stage 2 for that example, and an example they turn down is left out.
   With `--unattended`, print the list all the same and read it in their place, each example's claims against its
   `example.json` summary and its advisory. Where they say what the entry says and no more, accept them (after the
   setup, `watch.py claims NNN --accept "REASON"`, which records your word as a decision flagged for their review).
   A remark that a claim misstates the example's own pages goes to the setup with the plan, to be corrected; a
   suggestion to claim more is the user's, so name it in the report and go on with the claims as they stand. Where
   you are not sure, leave that example out and name it, with its claims, in the report: it waits for them.
4. **`toSetUp`** and the corrections, catalog entries first: have every one set up before its proof starts. For
   each, in the plan's order and one after another, run `watch.py stage setup "PROMPT"` as a background task, where
   the prompt names the entry and the plan and gives one instruction: do "A catalog entry's brief" of
   `llm-dlc/runtime.md` for it. Then check again with `--after-setup NNN,NNN` naming them. An entry that is still
   not prepared is in `leftOut`: say which and why, and go on without it.
5. **`toRepair`** and **`toClassify`**, prepared examples that lack `artifacts`, have a fault in their `form`, or
   don't record how a proof task is invoked: make one attempt to put them right. Run `watch.py stage setup "PROMPT"`,
   where the prompt is the check's output and the plan, and one instruction: do "The repair's brief" of
   `llm-dlc/runtime.md`. Check again. If `toRepair` still names anything, abort: tell the user which example lacks
   what and what the repair tried, and start nothing. One still in `toClassify` goes on, and the report names it.

Then go to stage 4 with `toProve`, in the plan's order, starting with the first. Say which examples were left out as
already decided. With `--scaffold-only` the skill ends after step 5.

## 4. Prove them

```bash
python3 llm-dlc/tools/watch.py loop --memory SIZE NNN [NNN ...]
```

with the examples still to prove, in order (`changes.py --pending NNN ...` leaves out what is decided), the memory
cap the doctor's budget proposes, and, before the numbers, `--wait-for-proofs`, `--record-as NAME` and
`--instruction "TEXT"` if the request has them. It starts the
proof loop detached, continuing the fixed session at high effort, and returns at once. Then watch it: run
`python3 llm-dlc/tools/watch.py wait` as a background task, act on what it returns as "Watching the loop" in
`llm-dlc/runtime.md` says, and run it again, until the loop has ended.

- **A summary** (every 30 minutes, or as the request's `--summary-interval` or the user says, with
  `watch.py interval`): print it as it is.
- **After a cycle**, the loop asks whether the example is done. Judge it from the example's own state, the cycle's
  report and the queue, and answer `finished`, `continue`, or `waiting` when all that is left is a proof still
  running. For `waiting`, start `watch.py proof NNN` as a background task of its own: the loop takes the next example
  meanwhile and comes back to this one when its proof is in.
- **Between two examples**, merge whatever workspace the user has queued, then answer `stop` if they asked the loop
  to end there, else `continue`.
- **A compaction with no commit**: `continue` while the work is moving, `stop` when it is stuck.
- **A verification loop it started** (`"kind": "verification"`): none was running while jobs waited, and `wait`
  has started one. Say so, and go on.

Each answer you give is also recorded as a decision the user can review afterwards (`llm-dlc/decisions/`). Add
`--confidence medium` to an answer you are not sure of, which flags it for them; put a question you are less sure
of than that to the user. A summary that names a decision the user overturned is theirs to you: act on it as
"Watching the loop" says.

The user may ask about any part of the run at any time: answer from `watch.py status`, the sessions' logs and the
queue. Fix what is small yourself (a job that hangs or runs away, a verification loop that died, a stale lock), say
what you did, and leave the rest to the user.

## 5. Report, and offer to contribute

When the loop has ended, stop the verification loop once the queue is clear (`watch.py verification stop`). The
results are in each example's folder in the home, with the run's record and the verification results. Tell the
user, for each change and each claim of it: established, refuted (with the witness, replayed on a JVM) or left open
(with why), under which bounds and assumptions, and what none of it covers. A refuted claim is a finding about
their change: say so plainly. List the answers you gave the loop that they have not reviewed
(`python3 llm-dlc/tools/decisions.py list --group flagged,unreviewed`), and say that `decisions.py review` accepts
or overturns them.

If the proof needed something new of the verifier, that part helps the next user more than this one. Say what it is
and offer to send it upstream as a pull request against `pilifs/in-the-loop`; if they agree, follow "Contributing
back" in `llm-dlc/runtime.md`. Nothing leaves their machine without that agreement.

The skill ends here. The session is theirs to continue: acting on a finding, exporting the report, or anything else.
