---
name: review-findings
description: Walk through what sync.py flags, one finding at a time, and prepare the commands that settle them.
disable-model-invocation: true
---

Go through the findings `sync.py` raises with the user, and help them decide each one. The user decides. You show the evidence, recommend, and write down what they chose.

**You never record a decision.** Accepting a finding is a person's call, made in their own terminal, where they see the real value. Don't run `sync.py review accept`, don't edit `llm-dlc/reviewed-findings.json`, and don't suggest the `!` prefix, because it runs in this session and is refused. If a command is refused, that is the safeguard working. Say so and carry on: don't look for a way around it.

Output lands in a published transcript, so use only the masked commands below. Don't open a raw transcript or a log to see a value, and don't ask the user to paste one.

1. Run `python3 llm-dlc/tools/sync.py check` and `python3 llm-dlc/tools/sync.py review`.
   If `check` reports an `ERROR` that is not a finding (a missing log, a stale file), name it and offer to fix it.
   `check` also says how many logs it left out because they are older than the redaction rules' stamp. Findings in those logs aren't reported, so say so if the note appears.
   If there is nothing open, say so and stop.

2. Group the findings by kind and by what they look like, so that the user decides a group at a time. Run `python3 llm-dlc/tools/sync.py review show ID` for each one, to see where it occurs. Don't guess from the masked value alone.

3. For each group, in order of risk (`ERROR` before `warn`, and a token or credential before a path), tell the user in a sentence or two what it appears to be and why, and give your recommendation. Then ask with AskUserQuestion:
   - **False positive**: goes on the list to accept, with a reason in the user's terms.
   - **Real**: stays open. Say what fixes it. It might be a new rule in `llm-dlc/tools/redaction_rules.py`, followed by `sync.py stamp`, or, for a log already published, `sync.py unpublish SID SHA --reason TEXT`, which is the user's call. A log that isn't uploaded yet can't be published until this is settled.
   - **Skip for now**: stays open, and comes up again next time.

   Findings of kind `local-secret` or `account-id` can never be accepted, so they are always real. If the excerpt is too little to judge by, say so, and tell the user that `sync.py review accept` prints the real value in their terminal before it asks for confirmation.

4. Give the commands for the user to run in their own terminal, not in this session, as one block with one command per reason:

   ```bash
   python3 llm-dlc/tools/sync.py review accept ID ID --reason "why"
   ```

   Each one prints the real values and asks them to type `false positive`. Remind them to read those values before confirming, since you have seen only masked ones.

5. When they say they're done, run `python3 llm-dlc/tools/sync.py review` and report what is still open. Then commit the updated list, following `CLAUDE.md`. List anything that was skipped or marked real, with the fix it still needs.
