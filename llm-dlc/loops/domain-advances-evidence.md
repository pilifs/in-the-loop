# Brief: domain advances, the evidence stream

A stream of [domain-advances.md](domain-advances.md), which is the instruction: read it in full first, its
Direction and "How to work through it" above all. You keep accepted results honest and the shared tools out of the
two domain owners' way. Yours is support work by its current character: if a piece of it turns out to be the hard
problem, say so in Progress and take it on as one.

## The outcome

**Intent.** A reported result can be believed without reconstructing an audit: one command says, from what a job
left, whether an example's answer is the answer its evidence gives, and what it still rests on.

**Where it stands.** [`examples/tools/accept.py`](../../examples/tools/accept.py) does this for an answer given
beside the route; its first lines list the checks, `test_accept.py` holds the controls, and
`llm-dlc/tools/changes.py` counts an answer only when it accepts. On the saved results: 289 and 290 accepted (eight
answers); 286's and 287's `mutant-security` refused (the mutant JAR's hash is in no record); every accepted answer
carries the limit that the JARs, the compiled adapter and the verifier's binary were not recorded. 289's driver now
records them (`evidence.json`, by `accept.record`); the others do not.

## Your work

1. **Collect the foundation's two jobs** when they are back (the watcher collects; you read):
   `20261117-122454-example-289-the-four-proof-tasks-again-w` and
   `20261117-122546-examples-286-and-288-the-simplematch-lem`. For 289: set each task's `besideRoute.job` to the
   new job (the `by` text says what changed), run `python3 examples/tools/accept.py 289`, which must accept all
   four **with no limit about unrecorded artifacts**, and commit with its output. If the `artifacts` check refuses
   something, that is a finding about the driver's record or the check: fix the one that is wrong. For the lemma
   job: a refusal of the simpleMatch lemma under the tightened checks names what was read; send it to the
   challenge stream and record it in the examples' notes.
2. **The other drivers** (`examples/{286,287,288,290}-*/proofs/prove.py`): each gets 289's three properties. It
   records identities (`accept.record`); it ends the run when the mutant's JAR is not the one the mutant replay ran
   (286 and 287 compare nothing today; 290 prints only); a run with a bound or unwind override is marked a trial.
   The four drivers repeat most of 289's code. Share what is the same in a module under `examples/tools/` only as
   far as it removes repetition you are touching anyway; each example keeps its own entry, lemmas, models and
   observed initializers. The domain owners will be editing 286's, 287's and 288's drivers for their own tasks:
   do this step first, announce it through their inboxes (`--kind interface`), and keep the change to the shared
   properties.
3. **Rerun what is no longer accepted.** 286 `mutant-security` and 287 `mutant-security`, each as a job at the
   frozen bound with its new driver and a `--work` folder of its own; then the records and `accept.py`. Rerun the
   other accepted answers of 286, 287 and 290 the same way, so that every `besideRoute` answer is accepted with no
   limit (the Done-when's first row). 288 has no `besideRoute`: its one verified task (`fixed-security`, job
   `20261116-201436-example-288-fixed-security-through-the-a`) was never recorded; record it only from a run the
   check accepts.
4. **A preservation result must not pass vacuously.** The check asks an establishment for a witness that reaches
   the property (`stated.vacuity`). For a pair, that witness must lie inside the assumption *and outside the
   allowed change*: a task whose allowed change covers every input agrees on nothing and must not be accepted as
   established. Find out what the checker's probe guarantees for a pair (`lib/src/equivalence.rs`, the `probe`
   run in `search.runs`), write the control (289's preservation with `--unchanged-unless true` as a probe: it
   must come out vacuous, or the engine has a hole, which is then the preservation stream's and yours to close),
   and make `accept.py` refuse an establishment whose witness is inside the allowed change or whose outcome does
   not say.
5. **Observed initialization** (the plan's E0, item 5; VF-033's audit). `prove --observed-initializer` gives a
   class the static state a JVM left (`lib/src/observed.rs`); 290's `fixed-security` and `preservation` rest on
   five such observations. Bind an observation to what it was observed on: the class's bytes, the classes its
   initializer ran, the JDK and the class path order, the default locale and the properties it read; a missing or
   mismatched observation must end the run, never fall back to a Java default. The outside review's countermodel:
   `A.<clinit> { B.x = 1; k = 7; }` satisfies the stated conditions, and after reading `A.k` the checker sees
   `B.x == 0` where Java sees 1, because only the observed class's own fields are imported. Reproduce it (the
   challenge stream may get there first: coordinate), then refuse an initializer that writes another class's
   static, or carry the write. The state stream needs the same binding for reflection it observes: agree the
   format with it through the inbox before changing it.
6. **The proof tier's Python half** (VF-030, open): the Python tests tagged `@cost("proof")` have not run as a
   job since example 286's engine changes. Queue them as a job of their own
   (`python3 lib/tools/test_costs.py run --tier proof --only python`), and the Rust proof tier for the tests whose
   inputs the foundation's checker changes touched. Close or update VF-030 from the results.
7. **Standing support**, as it comes up: a domain owner blocked by a tool, a fixture or a job is unblocked before
   your own next step. Measure what the run costs them: in Progress, each time, what was repeated work (a driver
   rebuilt by hand, a result reconstructed, an estimate that was far off).

## What you own in this run

`examples/tools/accept.py` and `test_accept.py`; the acceptance side of `llm-dlc/tools/changes.py`; the shared
properties of every `proofs/prove.py`; `lib/src/observed.rs` as far as binding an observation goes;
`verification/findings.md` entries VF-030 and VF-033 (the audit half; restating 290's preservation claim is the
user's chosen option B and needs a new frozen claim: prepare it, and record the freeze as theirs to give).
Don't change `verification/pipeline.py`.

## Done when

- `accept.py` accepts every `besideRoute` answer of 286, 287, 289 and 290 with no limit about unrecorded
  artifacts.
- The vacuity control exists and passes.
- An observation is bound to what it was observed on, the countermodel is refused or carried, and 290's notes
  record the audit; or the verdicts are rerun without observed initializers.
- VF-030 is closed or says exactly what is left.

## Progress

- Nothing yet.
- Status: working

## Loop settings

- session: 7ece8184-b148-4351-92d8-d634606b823e
- model: claude-opus-5-5
- effort: high
- workspace: domain-advances-evidence

## Loop until

Steps 1 to 6 in order, 7 whenever it comes up. Stop with `waiting on jobs ID ...` when what is left waits on jobs,
`done` when the criteria are met or recorded as the brief allows, `blocked: ...` when the next step is the user's.
Keep the last line of Progress a status.
