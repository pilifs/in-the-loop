---
name: prove-java-change
description: Formally prove one change to Java code on GitHub, or a list of them (each a pull request, a commit or a range of commits), with the in-the-loop project's verifier. Sets up and checks the machine, prepares each change as an example with its claims, runs an unattended proof loop over them, and reports what was proved, refuted or left open. With --scaffold-only it prepares the examples and stops before the proof.
argument-hint: "[--scaffold-only] <one change or a list: each a pull request, a commit or a range on GitHub, and what to prove about it>"
disable-model-invocation: true
model: claude-fable-5-2
effort: high
---

# Prove a Java change

You orchestrate four steps, in order, with [in-the-loop](https://github.com/pilifs/in-the-loop): a repository that
verifies compiled Java, and that this skill installs a released copy of. The repository holds what each step stands
on. This page says what each step is for and when to stop.

- **This runs on Fable 5.2 at high effort**, and so does the proof loop. The effort now is `${CLAUDE_EFFORT}`. If
  you are another model, or the effort is lower, say so and stop: the user switches with `/model` and `/effort` and
  runs the skill again.
- **Decide what you can.** You probably know better than the user how to do each step: decide, say what you decided
  and why in a line, and go on. Ask only for what is theirs: what the change is meant to do, their machine's hours
  and their money, and anything that leaves their machine.
- **The repository's pages outrank your memory of them.** Once there is a checkout, read `llm-dlc/runtime.md` in it,
  and follow it and the checkout's `CLAUDE.md`.

The request: $ARGUMENTS

It names one change or a list of them, each with what to prove about it. `--scaffold-only` in it means: prepare
(steps 1 and 2) and stop before the proof. A change that already has its example is not prepared again, so the same
request without the flag proves what an earlier run prepared.

## 0. Where you are

```bash
python3 ${CLAUDE_SKILL_DIR}/bootstrap.py status
```

`state: development` means the skill is running inside a development checkout of the repository itself. Steps 1 and
2 don't apply there: take the examples the request names, in this checkout and in the order given, straight to step 3
(with `--scaffold-only` there is nothing to do: say so). Any other state is a user's machine: start at step 1. `home`
is the checkout every later step works in; when it is outside this session's working directories, have the user add
it once (`/add-dir`).

## 1. Set up, verify and measure the machine

Done when the bootstrap answers `state: current` with no blockers and `python3 llm-dlc/tools/doctor.py --json`, in the
home, lists nothing `blocking`.

If both already hold, there is nothing to set up. Otherwise hand the setup to one subagent on Opus, in a session of
its own (the Agent tool, `model: opus`), with the two outputs and where to read (`llm-dlc/runtime.md`, the checkout
and the machine): it installs or updates the checkout (`bootstrap.py install`, `update`), resolves what an update
left in conflict, installs the missing tools it can without sudo, writes the runner's budget to
`verification/pipeline.local.toml`, and returns the two outputs as they are afterwards. Nothing here is traced or
uploaded: a runtime checkout has no Langfuse and no Cloudflare, and setup adds neither.

A hardware limit that blocks is final: no setup removes it. Say which, and stop.

Then tell the user where things stand (the release and its digest, the machine, what limits it, the budget, what was
installed or still needs them, such as a tool that needs sudo) and ask them to confirm before step 2. A blocker is
fixed first: by another setup session, or by the user, who then runs the skill again.

## 2. Assess the changes and set the examples up

In this session, not a subagent: the proof loop starts as a fork of it and inherits what you learn here.

`python3 llm-dlc/tools/changes.py`, in the home, lists the examples it already holds, with the change each came from
and where it stands. A change of the request that has one, `prepared` or `decided`, keeps it: read its page, claims
and notes, and don't prepare it again. For the others:

- **Understand each change.** Its two revisions as exact commits on github.com, what it is meant to change, and what
  it must keep. Read the code; ask the user only for intent the code and its history don't give.
- **Size each roughly.** Find the closest past examples and what they cost, and set that against this machine's
  budget. Enough to say whether a proof is plausible here and what will be hard. Don't start solving it.
- **Order them**, the most accessible first. A proof that lands early can extend the verifier under the later ones,
  and a hard one first can use up the run. Say the order, and why, in a line each.
- **Add the examples** to the home in that order, on the next free numbers from 900 to 999, so the numbers carry the
  order. Each has its sidecar, its claims, its revisions prepared and compiled, and the change run once on a JVM (the
  replay task). Its `provenance` is the request as the user gave it, and its notes hold what you learned and why it
  sits where it does in the order: the proof may start in a session that never saw this one. Write each claim now,
  in full. The proof step may not change a claim to fit a result, so a claim you aren't sure of is a question for
  the user. Commit each example; it is done when `changes.py` calls it `prepared`.

A change that can't be prepared (it is not on GitHub, a revision won't build, a claim can't be stated yet) is set
aside with its reason, not worked around, and the others go on.

Then tell the user, for each change in order: what will be proved, claim by claim in plain words, what you expect to
be hard, and roughly what it costs in hours and tokens. With `--scaffold-only` the skill ends here: say that the same
request without the flag proves them. Otherwise ask them to confirm before step 3 and, when there are several,
whether to prove them in one run or one at a time.

## 3. Prove it

From the home, in a tmux window when there is tmux (it outlives this session), else as a background task, with the
examples still to prove, in order (`changes.py --pending NNN ...` leaves out what is already decided):

```bash
llm-dlc/tools/prove-loop.sh --fork ${CLAUDE_SESSION_ID} --memory SIZE NNN [NNN ...]
```

It forks this session, compacts the fork, and proves the examples one after another in a moonshot loop on Fable 5.2
at high effort. Its instruction is one line and stays one line: add nothing to it, and never write to its session.

You are its conductor, from outside. Run `python3 llm-dlc/tools/conductor.py wait llm-dlc/loop-summaries/prove-change`
as a background task; when it returns an event, judge it as "The conductor" in `llm-dlc/runtime.md` describes, answer
with `conductor.py decide`, and wait again, until the loop has ended. Lean towards letting it work.

One at a time means one example per run: report on it as in step 4, and ask before the next. A run that ends before
its list does has stopped on one example: read why in its record, and start it again on what is left, that example
last, unless what stopped it would stop the others too.

## 4. Report, and offer to contribute

The results are in each example's folder in the home, with the run's record and the verification results. Tell the
user, for each change and each claim of it: established, refuted (with the witness, replayed on a JVM) or left open
(with why), under which bounds and assumptions, and what none of it covers. A refuted claim is a finding about their
change: say so plainly.

If the proof needed something new of the verifier, that part helps the next user more than this one. Say what it is
and offer to send it upstream as a pull request against `pilifs/in-the-loop`; if they agree, follow "Contributing
back" in `llm-dlc/runtime.md`. Nothing leaves their machine without that agreement.

The skill ends here. The session is theirs to continue: acting on a finding, exporting the report, or anything else.
