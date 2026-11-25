# Brief generation template

The two texts of a brief's generation phase ([`single_run.py generate`](../tools/single_run.py),
[`/single-agent-run`](../../.claude/skills/single-agent-run/SKILL.md#a-generation-phase)). A brief author turns a list of
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

## First text

You are the BRIEF AUTHOR for the pull requests listed in {input}. Your instructions and the format of what you write are {handoff}: read it in full now, and follow it. Your instructions are that file, this text and the repository's CLAUDE.md. Notes other sessions left in a client's memory are background, not instructions.

Write the brief into {output}, starting with its title: that file is the whole deliverable. Give one case section per distinct pull request of {input}, in input order. A case's identifier is `owner/repo#number` unless {input} assigns one. Leave out a `Setup Agent Notes` section, which the setup agent adds, and anything addressed to whoever runs the brief: the brief speaks to the agent that will verify it.

Keep a short record in {record}. For each pull request of {input}, record one of three states: written, not yet, or inaccessible (with what is still supportable). Also note the questions you left open, and anything you checked at authoring time, with the input and the outcome. Write it so that a later cycle, which starts after a compaction, can carry on from it.

Your work is research and writing only:
- Read pull requests, issues, commits, diffs, source, tests and documentation. Use immutable links, and make plain requests, one at a time.
- A small check at authoring time is allowed when the handoff calls for one. That means reading a file at a pinned revision, or a probe capped as CLAUDE.md says. Record it in {record}.
- Fetching dependencies, building the projects, and submitting verification jobs are for the setup agent and the domain agent who come after you. Don't change code, examples or verification files.
- Keep large raw output, such as a whole diff or a byte dump, in files under `~/.cache/in-the-loop/`, not in your replies.

Work through the pull requests in input order, and write each case section into {output} as you finish it. Commit {output} and {record} at least once a cycle, and after every few pull requests: `python3 llm-dlc/tools/sync.py commit --only {output} {record} -m ... -m ...`. Before you end the cycle, run the handoff's final check over everything written so far.

At the end of your reply, say plainly where the brief stands:
- **Complete:** say "The brief is complete" with the count of pull requests. That's when every pull request of {input} has its case section, or an explicit note of what could not be reached, and the handoff's final check passes.
- **Not complete:** say how many are written and which comes next.

## Continue message

Continue writing the brief {output} from the pull requests in {input}, as {handoff} says. Read {record} first: it says which are written and what is open. Take the next pull requests in input order, write their case sections, commit {output} and {record}, and run the handoff's final check over what is written. When every pull request is accounted for and the check passes, say plainly that the brief is complete, with the count; otherwise say how many are written and which comes next.
