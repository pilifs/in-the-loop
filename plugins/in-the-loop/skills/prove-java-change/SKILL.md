---
name: prove-java-change
description: Formally prove one change to Java code on GitHub, or a list of them (each a pull request, a commit or a range of commits), with the in-the-loop project's verifier. A watcher session sets up and checks the machine, has each change evaluated and prepared as an example with its claims, runs an unattended proof loop over them while reporting at intervals, and reports what was proved, refuted or left open. With --scaffold-only it prepares the examples and stops before the proof. It also takes examples by number: ones already prepared, which it checks before it starts, and catalog entries, which it has set up first.
argument-hint: "[--scaffold-only] [--wait-for-proofs] [--instruction \"TEXT with {}\"] <one change or a list: each a pull request, a commit or a range on GitHub, and what to prove about it | examples by number, prepared or catalogued: NNN ...>"
disable-model-invocation: true
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
| 2. Evaluate the changes and order them | the fixed session | Fable 5.2, medium |
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

## 0. Where you are

```bash
python3 ${CLAUDE_SKILL_DIR}/bootstrap.py status
```

`state: development` means the skill is running inside a development checkout of the repository itself. Stage 1
doesn't apply there and the request names examples by number: start the verification loop and go to "Examples
named by number", with a new fixed session (`watch.py session --new`) or, when the request names a session to
continue, that one (`watch.py session --use ID`). Any other state is a user's machine: start at stage 1.
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

## 2. Evaluate the changes and order them

As a background task, in the home:

```bash
python3 llm-dlc/tools/watch.py stage evaluate "PROMPT"
```

The prompt is the request as the user gave it, the doctor's output, and one instruction: do "Stage 2" of
`llm-dlc/runtime.md`. The session is the fixed one: it judges whether this machine is enough for these changes,
understands and sizes each change, orders them with the most accessible first, and writes its plan, with every claim
stated in full. It is the session that will prove them. A change that already has its example keeps it.

Its report is the plan. Tell the user, for each change in order: what will be proved, claim by claim in plain words,
what is expected to be hard, roughly what it costs in hours and tokens, and what was set aside and why. Ask them to
confirm. What they answer or correct goes back to the same session with another `stage evaluate`, until the plan
stands.

## 3. Set the examples up

```bash
python3 llm-dlc/tools/watch.py stage setup "PROMPT"
```

The prompt names the plan and gives one instruction: do "Stage 3" of `llm-dlc/runtime.md`. The session turns each
entry of the plan into its example: the revisions pinned and built, their JARs loaded, the sidecar and the claims
filled in as the plan states them, the change run once on a JVM, each example committed. It decides nothing the plan
left open: that comes back to you as a question. Done when `python3 llm-dlc/tools/changes.py` calls each example
`prepared`; if one is not, run the stage again with what is missing.

With `--scaffold-only` the skill ends here: say what was prepared, and that the same request without the flag
proves it.

## Examples named by number

When the request names examples by number, stage 2 doesn't run. After stage 1, check them, all before any is
started:

```bash
python3 llm-dlc/tools/watch.py preflight NNN [NNN ...]
```

It prints what each lacks, and the lists to act on. Go through them in this order:

1. **`absent`** (exit 2), an example that is not there: abort at once, naming it.
2. **`toRepair`**, prepared examples that lack `artifacts` or have a fault in their `form`: make one attempt to put
   them right. Run `watch.py stage setup "PROMPT"`, where the prompt is the check's output and one instruction: do
   "The repair's brief" of `llm-dlc/runtime.md`. Check again. If `toRepair` still names anything, abort: tell the
   user which example lacks what and what the repair tried, and start nothing.
3. **`toSetUp`**, catalog entries, which have revisions and nothing else: have every one set up before the loop
   starts. For each, in the order given and one after another, run `watch.py stage setup "PROMPT"` as a background
   task, where the prompt names the entry and gives one instruction: do "A catalog entry's brief" of
   `llm-dlc/runtime.md` for it. Then check again with `--after-setup NNN,NNN` naming them. An entry that is still
   not prepared is in `leftOut`: say which and why, and go on without it.
4. **The claims.** If anything was set up, or the repair wrote a claim, run `watch.py claims NNN ...` for those
   examples, show the user every claim as printed, in one list, and get their word once. A correction goes to
   another setup session for that example, and an example they turn down is left out.

Then go to stage 4 with `toProve`, in the order given, starting with the first. Say which examples were left out as
already decided. With `--scaffold-only` the skill ends after step 4.

## 4. Prove them

```bash
python3 llm-dlc/tools/watch.py loop --memory SIZE NNN [NNN ...]
```

with the examples still to prove, in order (`changes.py --pending NNN ...` leaves out what is decided), the memory
cap the doctor's budget proposes, and, before the numbers, `--wait-for-proofs` and `--instruction "TEXT"` if the
request has them. It starts the
proof loop detached, continuing the fixed session at high effort, and returns at once. Then watch it: run
`python3 llm-dlc/tools/watch.py wait` as a background task, act on what it returns as "Watching the loop" in
`llm-dlc/runtime.md` says, and run it again, until the loop has ended.

- **A summary** (every 10 minutes, or as the user asks with `watch.py interval`): print it as it is.
- **After a cycle**, the loop asks whether the example is done. Judge it from the example's own state, the cycle's
  report and the queue, and answer `finished`, `continue`, or `waiting` when all that is left is a proof still
  running. For `waiting`, start `watch.py proof NNN` as a background task of its own: the loop takes the next example
  meanwhile and comes back to this one when its proof is in.
- **Between two examples**, merge whatever workspace the user has queued, then answer `stop` if they asked the loop
  to end there, else `continue`.
- **A compaction with no commit**: `continue` while the work is moving, `stop` when it is stuck.

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
