# A generation phase

A page of the [`orchestrate-run`](SKILL.md) skill: read it in full before you start or judge a generation run, and
again after a compaction. What [`SKILL.md`](SKILL.md) says of every run holds here too.

When the user gives a **list of pull requests** instead of a brief, a **brief author** writes the brief first. The
brief is then queued right after its list, and goes through a setup phase and a domain run exactly as any other, before
the next list is generated (the user, 2026-11-25: a list proved before the next is written lets the later runs learn
from the earlier ones; `generatedBrief=end` queues it at the end instead, as until then). The three phases each keep a
session of their own, and you orchestrate all three:

| Phase | Agent (default) | Session |
|---|---|---|
| Generation: `single_run.py generate` | Codex Astra 6.2 at ultra effort, compacting at 600k tokens | the brief author's, continued by every generation (`generateSession=previous`), never the domain runs' |
| Setup: `single_run.py setup` | Claude Opus 5.5 at high | a new one for each brief |
| Verification: `single_run.py start` | Codex Astra 6.2 at max | the domain runs', continued by every domain run |

The author's instructions and the brief's format are the user's handoff, `llm-dlc/loops/brief-generation-handoff.md`
(theirs, unchanged), wrapped by the two texts of `llm-dlc/loops/brief-generation-template.md`:

```bash
python3 llm-dlc/tools/single_run.py generate NAME-generate --input LIST.md --output llm-dlc/loops/NAME-brief.md \
  --workspace WORKSPACE
```

The brief author researches and writes; it builds nothing and submits no job. It keeps a record
(`llm-dlc/loops/NAME-brief-generation.md`) of which pull requests are written, and commits the brief and the record
each cycle. A list of twenty pull requests can take several cycles.

Both texts give the author **four rules for each case**, beside the handoff (VF-075, 2026-11-27):
- a claim row with the role `Variation`, which repeats the case's main observation with exactly one input changed (the
  reversal, where the behaviour depends on order) and says what each revision should do;
- the order stated and checked wherever the code under change produces one, never "either order" there;
- the cheapest observation that shows the change: a public call before a database, a broker, a server or a child
  process, with the reason in the technical notes when a heavier one is needed;
- a claim row with the role `Remaining defect` wherever the landed code still looks wrong to the author.

With "The brief is complete" the author gives its own counts of these, and writes them into the record.

**Judge its cycles as any run's:**
- continue while pull requests are left to write;
- stop when it says "The brief is complete" and the record agrees, or when what is left needs the user (a private
  repository, say).

`brief_queue.py`'s `brief` step then checks that the landed brief names every pull request of the list. When one
is missing, it says so and the landing is undone in the queue's record: continue the run
(`single_run.py generate NAME-generate`), and `next --finished` lands it again. A filter stop or a lost session is
handled as for a domain run ([`queue.md`](queue.md), "When a client refuses a session"), with a new name and
`brief_queue.py set NAME run=NEWNAME`. Record a new author's session with
`brief_queue.py defaults --last-generate-session ID`.

The same step counts what the brief shows of the four case rules: the cases with a `Variation` row and those
without, the `Remaining defect` rows, and the cases whose words leave an order open. The count is `caseRules` in the
output of `next`, with a line for the user, and it is in the queue's log. It refuses nothing, and the brief's setup
phase starts as before: pass the line on to the user with the author's own counts, since whether a row keeps its rule
takes reading the case, and the user compares the brief themselves. `brief_queue.py rules FILE` counts any brief the
same way.
