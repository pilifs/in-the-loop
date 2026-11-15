# Runtime mode and releases

This repository runs in one of two modes. `python3 llm-dlc/tools/mode.py` prints which.

| | Development | Runtime |
|---|---|---|
| What it is | the repository as its authors work in it | a released copy on a user's machine, set up by the `/prove-java-change` skill |
| How it is told | no marker | `.in-the-loop-runtime.json` at the root, written by the skill's bootstrap, gitignored |
| A commit | carries its session's trace ([`README.md`](README.md)) | plain, with an `In-The-Loop-Runtime: VERSION sha256:DIGEST` trailer naming the release it was made on |
| Transcripts | redacted, summarized, published with a push | never read |
| A push | `sync.py push`, when the user asks | none: the work stays on the machine, except a contribution the user agrees to |
| Langfuse, the CDN, the allow list, the redaction rules | in use | off |
| Verification pipeline, loops, tests, examples | the same in both | the same in both |

The commands are the same in both modes, so an agent follows one procedure: [`tools/mode.py`](tools/mode.py) decides
what `sync.py commit`, `sync.py check` and the hooks in `.claude/settings.json` do. This page is the runtime side, and
the release process that feeds it.

## Procedure for agents in a runtime checkout

It replaces [`README.md`'s procedure](README.md#procedure-for-agents) and the trace rules of `CLAUDE.md`. Everything
else in `CLAUDE.md` holds: verification jobs are queued, tests have tiers, examples keep their notes.

- **Commit each feature when it is done**, as in development, with the same command:
  `python3 llm-dlc/tools/sync.py commit -m "Summary line" -m "What changed, why, and how it was verified."`
  It writes the message with the release's trailer and starts a new change. A plain `jj commit` is as good; never
  `git commit`.
- **Nothing is published.** `sync.py push`, `upload`, `scan`, `review`, `allow`, `stamp` and `langfuse` refuse to run,
  and the hooks do nothing. Don't push to any remote. The one exception is a contribution upstream, after the user
  agrees to it.
- **A new example takes a number from 900 to 999**, which no release uses, so that an update never brings an example
  with the same number. A contribution renumbers it.
- **The work is the user's.** It lives as commits on top of the release commit, and an update moves them onto the next
  release. Don't rewrite or abandon the release commit or anything below it.

## The checkout on a user's machine

[`bootstrap.py`](../plugins/in-the-loop/skills/prove-java-change/bootstrap.py) ships with the skill and is the only
part that runs before there is a checkout:

```bash
python3 bootstrap.py status     # JSON: mode, state (absent, current, outdated, broken, development), blockers
python3 bootstrap.py install    # clone into the home and stand on the pinned release, verified by its digest
python3 bootstrap.py update     # fetch, find the pinned release, rebase the local work onto it
```

The home is `$IN_THE_LOOP_HOME`, by default `~/.local/share/in-the-loop`: a jj checkout colocated with git, standing
on the release commit, with the user's work on top. jj is required: the commit procedure, the job queue (jobs are read
from `@-`) and updates (a rebase of the user's line) all go through it.

`state: current` means all of: the installed release is the one this copy of the skill is pinned to; the release
commit's tree hashes to the pin's digest, recomputed; the working copy descends from it; and the skill's files in that
commit are the bytes of the skill that is running. Setup is needed only when the state is anything else. After an
update, conflicts in the user's commits are listed for the agent to resolve.

Inside a development checkout the bootstrap answers `development`: there is nothing to install, and the checkout is
the home.

## Releases

A release is one commit: the skill at a version, and the repository it runs on, pinned to each other by the sha256
digest of the commit's tree, which the skill carries in
`plugins/in-the-loop/skills/prove-java-change/release.json`, beside its bootstrap.

```bash
python3 llm-dlc/tools/release.py cut [VERSION] [--note TEXT]   # make @ a release, commit it, verify it
python3 llm-dlc/tools/release.py status                        # the last release, the commits since, pushed or not
python3 llm-dlc/tools/release.py verify
```

- **The digest** is over one line per file of the commit (mode, sha256 of its bytes, path). It leaves out the pin
  itself, which can't hold its own hash, and the files `sync.py` regenerates on every commit (`llm-dlc/traces/`,
  `llm-dlc/index.json`, `llm-dlc/README.md`), listed in the pin. It is of content only, so the trace lines added to a
  commit's message later don't move it.
- **Cutting** writes the version into the plugin and the marketplace, then the pin from `@`'s tree, commits with
  `sync.py commit`, and verifies the commit. It refuses while `@` holds other uncommitted work. It can be run at any
  commit, as often as wanted: a version is only a name for a digest.
- **Finding** a release needs no tag: the bootstrap looks through the history of the pin for the commit that carries
  this version and digest and accepts it only when its tree hashes to the digest again. One implementation of the
  digest serves both sides, in `bootstrap.py`.
- **A release reaches users when `main` is pushed with it**, which stays the user's call. A copy of the skill installed
  earlier keeps its own pin and its own release until the plugin is updated (`claude plugin update`); its version in
  `plugin.json` is what tells Claude Code there is an update.
- **Trying a release before pushing it:** put a bookmark on the release commit and install from this clone:
  `IN_THE_LOOP_REPOSITORY=/path/to/this/repo IN_THE_LOOP_REF=BOOKMARK IN_THE_LOOP_HOME=/tmp/try python3
  bootstrap.py install`, run from a copy of the skill's folder outside the repository (inside it, the bootstrap
  sees a development checkout).
