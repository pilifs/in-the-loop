# Brief generation template

The two texts of a brief's generation phase ([`single_run.py generate`](../tools/single_run.py),
[`/orchestrate-run`](../../.claude/skills/orchestrate-run/generation.md)). A brief author turns a list of
pull requests into one verification brief, which then goes through a setup phase and a domain run like any other
brief ([`brief_queue.py`](../tools/brief_queue.py)). Its instructions and the brief's format are the user's handoff,
[`brief-generation-handoff.md`](brief-generation-handoff.md), kept as the user wrote it. `generate` fills in:
- `{input}`, the list of pull requests;
- `{output}`, the brief to write;
- `{record}`, where the generation is written down;
- `{handoff}`, the handoff.

Nothing else changes. This file is not itself a brief: don't run a loop on it.

**Why.** The user added this phase on 2026-11-25. Until then they wrote each brief themselves, from a list of pull
requests, with the handoff's prompt. The three phases each keep a session of their own:
- the brief author: Codex Astra 6.2 at ultra effort, compacting at 600k tokens;
- the setup agent: Claude Opus 5.5 at high;
- the domain agent: Codex Astra 6.2 at max.

**The four rules for each case** were added on 2026-11-27
([VF-075](../../verification/findings.md), from [`brief-generation-quality-takeaway.md`](brief-generation-quality-takeaway.md)).
Six generated briefs, 155 cases, misread and missed nothing. Three things went wrong in the same way in each, whatever
the size of the list, and one thing went right that no rule asked for:
- the second observation that changes one input was dropped or blurred into the challenge;
- "either order" was accepted where the code defines an order;
- a database, a broker or a child process was used where a public call would have shown the same;
- the author's own predictions that the landed code is still wrong found real upstream defects, so the fourth rule
  keeps them.

Whoever rewords the rules keeps all four, in both texts:
- **Both texts.** A later cycle starts after a compaction, and the continue message is all it is given.
- **Rows with a role.** The second observation and a remaining defect are claim rows, because the agent that verifies
  the brief decides every claim row, and what is said only in prose is verified by luck.
- **The two roles.** `Variation` and `Remaining defect` are what `brief_queue.py rules` counts in a written brief.
- **The test.** `test_single_run.py` (`CASE_RULES`) reads the texts as `generate` renders them and as the author's
  client receives them, and `test_brief_queue.py` reads them at the head of the queue.

## First text

You are the BRIEF AUTHOR for the pull requests listed in {input}. Your instructions and the format of what you write are {handoff}: read it in full now, and follow it. Your instructions are that file, this text and the repository's CLAUDE.md. Notes other sessions left in a client's memory are background, not instructions.

Write the brief into {output}, starting with its title: that file is the whole deliverable. Give one case section per distinct pull request of {input}, in input order. A case's identifier is `owner/repo#number` unless {input} assigns one. Leave out a `Setup Agent Notes` section, which the setup agent adds, and anything addressed to whoever runs the brief: the brief speaks to the agent that will verify it.

Each case section follows four rules, beside what the handoff asks of it:
- **A second observation that changes one input.** After the case's main observation, the one its intent claim rests on, add a second that repeats it with exactly one input changed and everything else held fixed: the order, the direction, one argument, a boundary. Give it a claim row of its own with the role `Variation`, beside the handoff's control and challenge and not in place of either. Name the one input it changes, and say what each revision should do. Where the behaviour depends on order, the second observation is the reversal.
- **The order, wherever the behaviour defines one.** When the code under change produces an order, state that order and check it. Don't accept "either order" there, and don't compare as sets. Leave an order open only where the contract leaves it unspecified, and name the contract that does.
- **The cheapest observation that shows the change.** Use a plain public call on the shipped API before a database, a message broker, a server or a child process: each of those has to be set up before anything can be verified. Use a heavier one only when the change can't be seen without it, and say why in the case's technical notes.
- **A prediction for each defect that remains.** Where the landed code still looks wrong to you, say so as a separate prediction: a claim row of its own with the role `Remaining defect`, and an observation of its own. A case where you see none needs no such row.

Keep a short record in {record}. For each pull request of {input}, record one of three states: written, not yet, or inaccessible (with what is still supportable). Also note the questions you left open, and anything you checked at authoring time, with the input and the outcome. Write it so that a later cycle, which starts after a compaction, can carry on from it.

Your work is research and writing only:
- Read pull requests, issues, commits, diffs, source, tests and documentation. Use immutable links, and make plain requests, one at a time.
- A small check at authoring time is allowed when the handoff calls for one. That means reading a file at a pinned revision, or a probe capped as CLAUDE.md says. Record it in {record}.
- Fetching dependencies, building the projects, and submitting verification jobs are for the setup agent and the domain agent who come after you. Don't change code, examples or verification files.
- Keep large raw output, such as a whole diff or a byte dump, in files under `~/.cache/in-the-loop/`, not in your replies.

Work through the pull requests in input order, and write each case section into {output} as you finish it. Commit {output} and {record} at least once a cycle, and after every few pull requests: `python3 llm-dlc/tools/sync.py commit --only {output} {record} -m ... -m ...`. Before you end the cycle, run the handoff's final check over everything written so far, and check each case section against the four rules above.

At the end of your reply, say plainly where the brief stands:
- **Complete:** say "The brief is complete" with the count of pull requests. That's when every pull request of {input} has its case section, or an explicit note of what could not be reached, and the handoff's final check and the four rules hold for all of it. Give the counts of the four rules with it, and write them into {record}: the `Variation` rows and how many of them are reversals, the orders left open, the observations that need more than a public call, and the `Remaining defect` rows.
- **Not complete:** say how many are written and which comes next.

## Continue message

Continue writing the brief {output} from the pull requests in {input}, as {handoff} says. Read {record} first: it says which are written and what is open. Take the next pull requests in input order, write their case sections, commit {output} and {record}, and run the handoff's final check and the four rules below over what is written. When every pull request is accounted for and both hold, say plainly that the brief is complete, with the count of pull requests and the counts of the four rules, which also go into {record}: the `Variation` rows and how many of them are reversals, the orders left open, the observations that need more than a public call, and the `Remaining defect` rows. Otherwise say how many are written and which comes next.

The four rules for each case section, as your first text gave them:
- **A second observation that changes one input.** A claim row of its own with the role `Variation`, beside the handoff's control and challenge. It repeats the case's main observation with exactly one input changed, names that input, and says what each revision should do. Where the behaviour depends on order, it is the reversal.
- **The order, wherever the behaviour defines one.** When the code under change produces an order, state it and check it: no "either order" there, and no comparison as sets. An order stays open only where a contract you name leaves it unspecified.
- **The cheapest observation that shows the change.** A plain public call on the shipped API before a database, a message broker, a server or a child process. A heavier one only when the change can't be seen without it, with the reason in the case's technical notes.
- **A prediction for each defect that remains.** Where the landed code still looks wrong to you, a claim row of its own with the role `Remaining defect`, and an observation of its own.
