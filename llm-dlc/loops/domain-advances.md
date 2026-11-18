# Brief: domain-owned advances in Java change verification

**Status of the brief**: written 2026-11-17 from the user's plan for Phase 2
(`~/code/scripts/analysis/02-verification-architecture-plan.md`, with its inputs beside it: the architecture ranking,
the market review and `03-architecture-overflow.md`), after a foundation stage the user asked for in their own
session: that session did the plan's correctness prerequisites and the acceptance check first, and this brief is
the plan as it stands after them. The user asked for it to be run with `/run-brief`. Not yet run.

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh), run as four streams through `/run-brief
domain-advances` ([`llm-dlc/README.md`](../README.md#a-briefs-run)): [preservation](domain-advances-preservation.md),
[state](domain-advances-state.md), [evidence](domain-advances-evidence.md) and
[challenge](domain-advances-challenge.md). The foundation is done (below), so the run can start with
`--no-foundation`; a second foundation session is not wrong, and has less to find.

## Direction

The goal is new verification capability, found by deciding hard claims about real changes, not a tidier
architecture. Two streams each own one domain outcome across the whole stack; one stream keeps the evidence honest
and the shared tools out of their way; one stream tries to break what the others conclude.

- **An owner owns the outcome, not a layer.** The preservation and state streams may change the harness, the Java
  models, the checker, the pairing, the drivers and the proof strategy together, in one branch, when the problem
  needs it. Nothing in `lib/` is another stream's property. What keeps two streams from colliding is the
  ownership each stream brief states for *this run* and the inbox, not a permanent split.
- **Who may change a candidate solution and what justifies accepting its result are separate.** Change anything;
  an answer counts only when `python3 examples/tools/accept.py NNN` accepts it from what a job left. Nobody sets a
  `besideRoute` record, a README verdict or a "decided" in Progress on the strength of a job that passed.
- **Three things are kept apart**, and a Progress line says which one moved:
  - the *user's intent*: the domain outcome and why it matters (in each stream brief, from the plan);
  - the *working formalization*: a hypothesis about how to state it, which the owner may find wrong and revise,
    saying what changed in meaning;
  - the *accepted claim*: the frozen claim file, its bound, artifacts and evidence. A frozen claim file is never
    edited. A different statement is a new claim file and a new task, and whether it replaces the old one as the
    example's claim is the user's decision (Decisions).
- **A result is one of four things, and says which**: the original claim decided; its formalization corrected (a new
  claim, the old one left as it was); a narrower result established beside an open claim; the intended property
  found false, with a witness that replays on a JVM.
- **After two failed attempts at one hypothesis, record it and change approach** (the timebox, below): what was
  tried, what the evidence showed, what a different approach would be. A failed experiment that is written down is
  a result of this brief.
- **Generalize from a second use, not before the first.** The first success may be specific to one pair of
  methods. A reusable interface (a relational summary, an effect contract, a proof-store key) is extracted when a
  second real consumer shows which parts were accidental.
- **Don't add to the verification pipeline's machinery** (`verification/pipeline.py`, the runner, the collector):
  the user plans to rework it as a whole. Use it as it is.

## Where it starts from

State on 2026-11-17, at the foundation's commits (`qkqpsmqkswql` and the ones after it).

**The examples** (`python3 llm-dlc/tools/changes.py 286 287 288 289 290 307`):

| Example | Stands | Open |
|---|---|---|
| 286 CVE-2022-22968, DataBinder case | decision lemma refuted on 5.3.18, established on 5.3.19 (beside the route, accepted) | `mutant-security` (not accepted: below); `preservation` (a regression check refuses a `String[]` parameter); the two protected-state tasks (stop at `ArrayList.<init>(int)` on the way to `bind`) |
| 287 CVE-2025-22228, BCrypt 72 bytes | security refuted on 6.3.7, established on 6.3.8 (beside the route, accepted); the guard lemma by the route | `mutant-security` (not accepted); `preservation`: never reached the cryptography |
| 288 CVE-2024-38820, DataBinder locale | `fixed-security` verified once (19m42s, no `besideRoute` recorded) | the two refutations time out at 1800 s and preservation at 5400 s (VF-031) |
| 289 CVE-2022-22978, RegexRequestMatcher | all four decided beside the route, accepted | nothing; job `20261117-122454-example-289-the-four-proof-tasks-again-w` reruns them with recorded identities |
| 290 CVE-2023-34035, servlet rules | all four decided beside the route, accepted | VF-033: preservation compares only counts of matchers by type; the fixed verdicts rest on initializers observed on a JVM |
| 307 BCrypt `getBytes(UTF_8)`, positive | replays pass on the source slice | `preservation` and `mutant-preservation`: refused at the nullable `String` password (VF-028), no driver yet |

**What the foundation built** (each with its tests; read the commit messages for the detail):

1. **Three false proofs closed in the checker** (the plan's E0, items 2 and 3). Each was reproduced first; the
   countermodels are [`lib/tests/fixtures/claims/claims/Effects.java`](../../lib/tests/fixtures/claims/claims/Effects.java)
   (its `main` prints what a JVM says) and the tests are in [`lib/tests/claims.rs`](../../lib/tests/claims.rs).
   - `prove --decreases` on a method whose recursive call writes a static field proved a false result: the
     induction hypothesis dropped the write. A method proved by induction is now held to the write checks.
   - With a `throws:` clause, the hypothesis returned a value for an inner call the property says throws. It now
     covers no such call (`the induction does not go through`).
   - A lemma about a getter, proved in the fresh state, stood in for a call made after the caller wrote the field
     (also through a callee, through an array a static holds, for the default locale, and through the lemma's own
     assertion). A lemma's method and its expressions may now read nothing a caller can change
     (`Engine::reads` in [`lib/src/bmc/mod.rs`](../../lib/src/bmc/mod.rs)); `lib/README.md` states the rule.
   - *Audit of existing results*: no example uses `--decreases` directly; 286 and 288 use lemmas about
     `PatternMatchUtils.simpleMatch(String,String)`, which reads no field and no array, so their results did not
     rest on the hole. Job `20261117-122546-examples-286-and-288-the-simplematch-lem` confirms the tightened checks
     still prove them.
   - *Consequence for the preservation stream*: the lemma mechanism as it is (static methods over primitives and
     Strings, result only, reads nothing mutable) cannot summarize `BCrypt.hashpw(byte[], String)`: array
     parameters, and final static tables of ints (`P_orig`, `S_orig`) that the method copies. That is refused
     today by design, not by accident. A summary that reads static tables needs a stated footprint the use site
     checks (the tables are never written), which is the stream's to design.
2. **The acceptance check** (the plan's E1): [`examples/tools/accept.py`](../../examples/tools/accept.py), with
   its controls in `test_accept.py` (wrong conclusion, missing result, changed artifact, trial bound). It replaces
   the old rule in `llm-dlc/tools/changes.py` ("the job passed and names the example"), under which one passed job
   supported either answer. Its first lines list every check. What it found on the saved results:
   - 289's four answers and 290's four are accepted, as the outside review found by hand.
   - 286's and 287's `mutant-security` are **not** accepted: their drivers neither print nor record the mutant
     JAR's hash, so nothing says it was the JAR the mutant replay ran. `changes.py` lists both claims open again.
   - Every accepted answer carries one limit: the jobs recorded no identity of the JARs, the compiled adapter or
     the verifier's binary. 289's driver now writes `evidence.json` with them (`accept.record`), ends the run on a
     mismatched mutant and marks a run at another bound a trial. The other drivers do not yet.
3. **`/tmp` ran out of inodes during this work** (VF-036 in `verification/findings.md`, which the user settled the
   same day: they raised the limit and cleared it, and nothing changes for now). What matters to a stream: a check
   run without `--work` leaves a folder `jvmcontract-equivalence-PID-...` in `/tmp` and never removes it, so a
   driver or a probe you run passes `--work` (under `verification/.work-NNN/...` for a job, under `lib/target/`
   for a probe), and a stream that sees "No space left on device" checks `df -i /tmp` first and tells the watcher.
   The foundation built a per-run `TMPDIR` for `test_costs.py run` and took it out again when it saw the user's
   decision; it is in the history (`vqntqptvslos`) for whoever takes VF-036 up.

**Not done, and whose it is now**: the pairing items of E0 (old and new share JDK state and, without
`--before-classpath`, library statics; exceptions are compared by category, not class: `lib/src/pairing.rs:39-41`,
`:105-146`, `lib/src/harness/mod.rs:39-55`) go to the preservation stream, which changes pairing anyway, with the
challenge stream writing the countermodels first. Observed initialization (290, VF-033) and VF-030's Python proof
tier go to the evidence stream. Reuse (E4) and independent checking (E5) follow consumers: see Deferred.

## How to work through it

The [standing rules](brief-template.md#standing-rules), the [timebox](brief-template.md#the-timebox) and the
[tests](brief-template.md#tests) apply as written. **Verification mode: with the pipeline**; the watcher keeps the
queue. In addition:

- **Start by checking this brief against the code.** It was written by one session in one day; a claim here that
  the code contradicts is a finding, recorded under Progress.
- **A reproducer before a fix, a countermodel before a rule.** A soundness change comes with the false proof it
  closes, reproduced on the checker as it was (a probe: `systemd-run --user --scope -q -p MemoryMax=4G -p
  MemorySwapMax=0 timeout 300 COMMAND`, one at a time), and with what a JVM says of the countermodel.
- **A refusal is better than a false proof, and a refusal is not a result.** Where a mechanism cannot be made
  sound in the cycle, refuse the case by name and say what would make it sound.
- **An answer is recorded only through the acceptance check.** The order is: change, queue the job with the
  driver's `outcome.json` *and* `evidence.json` among its outputs, wait for the result, then set the task's
  `besideRoute` to that job and run `python3 examples/tools/accept.py NNN TASK`, which must accept it; commit the
  record with the check's output in the message. A driver you touch gets 289's three properties first
  (`examples/289-*/proofs/prove.py`): it records identities, it ends the run when the mutant is not the replay's,
  and it marks a trial.
- **A trial bound is for seeing, never for answering.** A proof at a smaller bound establishes nothing about the
  claim's bound; a witness found at a smaller bound does refute it, and the check accepts it.
- **Jobs**: one claim per step, the frozen bound, `--work verification/.work-NNN/SOMETHING` that no accepted job
  already wrote to (an accepted job's outputs must stay as its result records them). Estimates from the last run of
  the same step; the local runner takes at most 4 GiB a job.
- **What you learn about one example goes into its `example.json` notes**; what holds for the checker goes into
  `lib/README.md`. A new capability is described where its command is.
- **Talk through the inbox.** A stream that needs another's decision, breaks another's test, or changes an
  interface another uses sends an item (`python3 llm-dlc/tools/inbox.py send domain-advances-STREAM --kind
  interface|failure ...`) and goes on with what does not depend on the answer.
- **The user decides**: replacing an example's claim with a restated one; anything in `llm-dlc/allowlist.json` or
  `reviewed-findings.json`; a push; clearing `/tmp`; moving a test between cost tiers; any weakening of a bound, a
  gap mode or an expectation. Record these as open decisions and work around them.

## The plan

Three milestones, in the plan's words, and who carries each.

**M1, credible and repeatable acceptance.** Done for 289 and 290 by the foundation; 286 and 287 partly. The
[evidence stream](domain-advances-evidence.md) finishes it: every driver records identities, the two mutant
refutations are rerun and accepted, 289's records move to the job with recorded identities, a preservation result
cannot pass vacuously (an allowed change that covers every input must not establish anything), and the observed
initializers of 290 are bound to what they were observed on.

**M2, useful relational reasoning.** The [preservation stream](domain-advances-preservation.md): decide 287's
BCrypt preservation claim through its approved entry, which needs the two sides' unchanged cryptography related
and not run twice with independent invariants; then transfer the technique to the positive change of 307 (two
spellings of the same UTF-8 conversion); then, with what was learned about cost, 288's preservation as a second
family.

**M3, effects through a real application path.** The [state stream](domain-advances-state.md): the intent
"permitted updates preserve authorization-relevant state", through `DataBinder.bind` as the releases implement
it, on 286's protected-state claims; a first effect contract that the adversarial setter (one that also writes
`isAdmin`) fails; then a second consumer.

**Across all three**, the [challenge stream](domain-advances-challenge.md) reads what the others commit and tries
to refute it: countermodels for each new rule, the formalizations themselves (does the claim say what the intent
needs?), and the pairing and observed-initialization holes the foundation left stated but open.

**Shared, and how it is kept shared**: `lib/src/bmc/mod.rs` is large and three streams will touch it. Keep each
change local to what it is about, commit it the cycle it works, and expect the watcher's merges to meet: the stream
whose merge conflicts resolves it. `examples/tools/accept.py` is the evidence stream's; another stream that needs
a check changed asks through the inbox. `lib/tests/fixtures/claims/claims/Effects.java` and the tests beside it are
the challenge stream's; anyone may add a countermodel file of their own next to it.

**After the streams**: the watcher merges each stream as it finishes; there is no merge loop. What the merged
whole then needs (the default test run, a joint check that M1 to M3 hold together, the push) is the watcher's
report and the user's next brief.

## Done when

| Milestone | Criterion | Stream |
|---|---|---|
| M1 | `accept.py` accepts every `besideRoute` answer of 286, 287, 289 and 290 with no limit about unrecorded artifacts, from jobs whose drivers wrote `evidence.json` | evidence |
| M1 | a control shows that a preservation task whose allowed change covers every input is not accepted as established | evidence |
| M1 | 290's observed initializers are bound to the class bytes, JDK and class path they were observed on, or the verdicts are rerun without them (VF-033's audit) | evidence |
| M2 | 287 `preservation` is decided at its frozen bound through the adapter entry and accepted; or the first failure and two approaches are recorded with their evidence | preservation |
| M2 | the same technique decides 307 `preservation` and refutes `mutant-preservation`, with exact exception classes; or the record of why it does not transfer | preservation |
| M3 | 286's two protected-state tasks are decided through the actual `bind` path and accepted; or the blocker chain is recorded as observed gaps, each with a closure test | state |
| M3 | an effect contract that the adversarial setter fails and the fixture's honest setter meets, used by two consumers | state |
| All | every new soundness rule has a countermodel test that failed before it; every finding of the challenge stream is fixed, refused by name, or recorded as open with its owner | challenge |

A criterion ends as met, not met with its record, or waiting on named jobs. "Or the record" is a real outcome: the
brief is for finding out, and an honest account of a wall is worth more than a claim narrowed until it passes.

## Deferred: not in this loop

- **Reuse of proofs across claims and revisions** (the plan's E4): `lib/src/reuse.rs:229` refuses to cache a proof
  by induction or with lemmas, because the key does not read them. Extend the key only when a stream is repeating
  measurable work (288's simpleMatch lemmas, 85 and 93 s each run, are the candidate), and only for the categories
  it then covers.
- **Other tools and independent checking** (E5: another solver, SAW, Lean, a small checker, SAT certificates):
  only on a concrete trigger a stream writes down (an obstacle the native route cannot express, or a rule with
  several consumers that needs checking independently of its producer). The connection from the tool's theorem to
  the actual Java method is part of the experiment's success criterion.
- **The nineteen larger options** of `~/code/scripts/analysis/03-architecture-overflow.md` (O01 to O19): a
  backlog, promoted by naming a current consumer, the smallest experiment and an exit criterion.
- **A common adapter route** in the example route itself (O08): the drivers stay per example in this brief.
- **Changes to the verification pipeline**, and VF-036.

## Decisions

Settled by the user's plan (2026-11-16) and their instruction for the foundation (2026-11-17):

- Domain ownership across the stack; Opus 5.5 at high effort for the owners and the challenger.
- Known correctness work is not deferred in the name of flexibility: the E0 items come first, and did.
- Acceptance starts with 289's four saved results, then selected 286 and 287 evidence.
- The streams are run by `/run-brief`, started by the user.

Kept for the user: whether a restated claim replaces an example's frozen one (VF-033's option B for 290 is already
chosen: restate preservation to compare what the matchers are); whether 286's and 287's READMEs and verdict labels
should say now that their mutant refutations are no longer counted (the examples' notes say it); when VF-036 (the
temporary folders a check leaves) is taken up.

## Progress

- 2026-11-17, the foundation (the user's own session, on Fable 5.2, in the workspace `domain-advances-foundation`):
  E0 items 2 and 3 closed with countermodels (`qkqpsmqkswql`); the acceptance check, its controls, `changes.py` on it and 289's driver recording identities (`zonotvopnmry`);
  two jobs queued: `20261117-122454-example-289-the-four-proof-tasks-again-w` and
  `20261117-122546-examples-286-and-288-the-simplematch-lem`. This brief and its four stream briefs.
- 2026-11-17, the watcher: merged stream evidence (vqquvmnmmoqx), which says done.
- 2026-11-18, the watcher: merged stream challenge (yulpuuronznk), which says done.
- 2026-11-18, the watcher: merged stream state (kmytvuopwxtu), which says done.
- Status: working

## Loop settings

- session: b2fb688f-0b67-4fc6-b325-9d58ef8c62de
- model: claude-opus-5-5
- effort: high
- streams: preservation, state, evidence, challenge
- new-window: no

## Loop until

A brief of streams has no loop of its own: the watcher merges each stream as it finishes and sets this status.
