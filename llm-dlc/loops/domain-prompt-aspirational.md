# Domain prompt template: aspirational

The two texts a queued brief's domain run is given by default ([`brief_queue.py`](../tools/brief_queue.py),
`prompt=aspirational`). They are the user's own words, sent with each brief from 2026-11-21 to 2026-11-23.
`{brief}` is the brief's path as the user gave it, under `~/code/scripts/analysis/`. A brief that needs other
texts names another template (`domain-prompt-NAME.md`, with the same two sections). A run's continue message is
still the user's to change mid-run, with `single_run.py message`. This file is not itself a brief: don't run a
loop on it.

## First text

Review and implement {brief}. The last few runs have gone quite well, so be aspirational with how you approach the work to maximize quality and efficiency.

## Continue message

Continue to review and implement {brief}. The last few runs have gone quite well, so be aspirational with how you approach the work to maximize quality and efficiency.
