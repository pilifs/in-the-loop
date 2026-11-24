# Domain prompt template: scaffold-first

The aspirational texts ([`domain-prompt-aspirational.md`](domain-prompt-aspirational.md)) with one more direction,
which the user added on 2026-11-24 after the first run of the beyond-JBMC brief: do the investigation and claim
scaffolding of each case before starting to solve it. In that run the solver was rarely where a case was lost: the
automatic workflow reached a public method in 12 of 16 unfamiliar upgrades and decided none (VF-063). A queued
brief takes these texts with `prompt=scaffold-first`. `{brief}` is the brief's path as the user gave it. A run's
continue message is still the user's to change mid-run, with `single_run.py message`. This file is not itself a
brief: don't run a loop on it.

## First text

Review and implement {brief}. The last few runs have gone quite well, so be aspirational with how you approach the work to maximize quality and efficiency. If an earlier run of this brief left results (its results file in llm-dlc/loops/, and open findings in verification/findings.md), build on them rather than repeat them. For each case, do the investigation and claim scaffolding before you start solving: find the public entry and the observation that changed, build a caller and run it on both original releases, recover the class loaders, resources and startup state it needs, and register the question, its expected behaviour and an unchanged control. Record where scaffolding stopped as carefully as where the solver stopped: in recent runs most undecided cases were lost there. New checker capabilities that extend our lead over JBMC are welcome alongside this work, as are the open fixes earlier runs named.

## Continue message

Continue to review and implement {brief}. The last few runs have gone quite well, so be aspirational with how you approach the work to maximize quality and efficiency. Keep scaffolding ahead of solving: finish the investigation, the caller and the registered question of a case before working on its proof. Extending our lead over JBMC with new capabilities and finishing the open fixes are both worth doing.
