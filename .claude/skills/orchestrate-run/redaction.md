# Redaction decisions, when the user delegated them

A page of the [`orchestrate-run`](SKILL.md) skill: read it in full before you decide a finding yourself, and again
after a compaction.

By default every redaction decision is the user's: a finding is proposed (`sync.py allow propose ID --reason
"why"`), relayed to them, and waits for them without holding the run. `python3 llm-dlc/tools/sync.py delegate
status` says whether they delegated the routine ones to you for this run. Don't set that up yourself and don't
press for it. When they want it, run `python3 llm-dlc/tools/sync.py delegate request --run NAME` and give them the
code it prints; they grant it from their own terminal (`sync.py delegate on CODE`). The grant is this session's
alone: an agent you start has none, and it ends with this session or at `sync.py delegate off`.

While it is on, for each open finding (`sync.py review` lists them masked, `review show ID` shows where):

| What it is | What you do |
|---|---|
| A value whose origin the tool can check: it is in a file `main` publishes, a committed fixture, a digest or object of this repository, a log's own name | `sync.py delegate approve ID... --evidence KIND:DETAIL --reason "why"`. Name each id; the command checks the evidence, records the decision and commits it. A `long-token` with no such origin is not approved: its shape establishes nothing |
| An ambiguous value that can go without changing what the log says | `sync.py delegate mask ID... --reason "why"`: later logs omit it, and logs not yet uploaded that hold it are withheld. Or `sync.py delegate withhold SESSION SHA256 --reason "why"` for one log |
| A credible live credential, personal data, something already published, or anything that would make more public | Contain what you can (withhold what is not uploaded), then one `sync.py review escalate ID... --reason "what remains to decide" --contained "what was done"`, and tell the user. Go on with the checkpoints and work it does not touch |

Never print a value, and never work round a refusal: a refused approval is proposed and left for the user. What
the redactor removes (`ERROR` findings), a published log and `review accept` stay theirs whatever is delegated.
