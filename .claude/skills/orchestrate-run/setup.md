# A setup phase

A page of the [`orchestrate-run`](SKILL.md) skill: read it in full before you start or judge a setup run, and again
after a compaction. What [`SKILL.md`](SKILL.md) says of every run holds here too.

With `--setup`, or when the user asks for setup to be done first, a **setup agent** does the brief's mechanical
setup before the run you were asked for (the domain run) starts. It fetches the sources at the pinned revisions,
the dependencies of both sides of every pair, the build tools and JDKs. It verifies hashes and signatures, builds
the original artifacts, checks that the original regressions behave as the brief says, and writes all of it down.
The domain agent then starts the real work at once.

The first setup phase was on 2026-11-22. Claude Opus 5.5 set up the Spring and Java data brief in two cycles, and
Codex Astra then scaffolded and scored the whole brief in its first cycle without fetching anything. Use one for a
brief that names upstream sources, releases or builds; work inside this repository needs none.

```bash
python3 llm-dlc/tools/single_run.py setup NAME-setup --brief FILE [--workspace WS] [--model ID] [--cycles N]
```

- **Its texts are the repository's,** [`llm-dlc/loops/setup-agent-template.md`](../../../llm-dlc/loops/setup-agent-template.md),
  with the brief and the record filled in. `setup` refuses texts of your own. They are no more yours to change
  than a user's are: a run the template no longer serves is ended, and the template is changed by a commit, as
  any other file is.
- **The agent is Claude Opus 5.5 at high effort** unless `--client`, `--model` or `--effort` say otherwise. Give it
  the workspace the domain run will use, so that what it commits is there.
- **Watch it as any run, with one more judgment: that it keeps to its role.** It writes one record
  (`llm-dlc/loops/BRIEF-setup.md` by default, or `--record`) and commits nothing else of its own but the jobs it
  queues. If a commit of it touches `lib/`, `examples/`, claims, sidecars or adapters, or a third cycle starts
  without setup being complete, answer `stop`: it has drifted into the domain work, which the domain agent does.
- **When only its jobs are left,** it says so and names them. Answer `stop` with that as the reason, run
  `single_run.py jobs NAME-setup` as a background task, and when it returns, `single_run.py setup NAME-setup`
  (or `start`) continues it to record their results.
- **Something refused** (the classifier, a permission) is recorded by the agent and not worked round. A public
  repository that has gone away is different: it may take the same coordinates from Maven Central or the Gradle
  Plugin Portal with their checksums verified, without changing the upstream build files, and records the
  substitution. An artifact that is nowhere else stays a gap, for the user or the domain agent.
- **When it says setup is complete,** answer `stop`. Then:
  - land it if it had a workspace;
  - read the `## Setup Agent Notes` section its record ends with, and send it back with `start` if anything the
    domain agent needs is missing;
  - run `single_run.py notes NAME-setup`, which puts the section into the brief. Add `--to FILE` for each other
    copy the domain agent reads, such as the user's original when the prompt names that one;
  - commit the copy in the checkout;
  - start the domain run with the user's texts, as step 1 of [`SKILL.md`](SKILL.md#1-start-it) says, in the same
    workspace.

  Tell the user in a few lines what was set up, what was verified and what could not be done.
