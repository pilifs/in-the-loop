---
name: publish
description: Commit finished work and publish it with its session traces, leaving the repo clean.
disable-model-invocation: true
---

Publish this repo. The user asked for it by running this skill, so pushing is authorized for this run only.

1. Run `jj status`. If `@` has unfinished work, stop and say what is unfinished.
   Otherwise, if it has finished work, commit it:
   `python3 llm-dlc/tools/sync.py commit -m "Summary" -m "What changed, why, and how it was verified."`
2. Run `python3 llm-dlc/tools/sync.py push --bookmark main`.
   It records all outstanding traces in one last commit, uploads the logs, runs `check`, pushes, and leaves `@` empty.
3. Report the pushed commit and any failure, as shown in the command's output.
   This turn's closing reply cannot be in the log it just published. The next push carries it.
   To publish it now, the user can exit and run the same command from a terminal.
