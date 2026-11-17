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

- 2026-11-17, cycle 1. **Step 1** waits: both foundation jobs (`20261117-122454-…-289-…`, `20261117-122546-…-286-and-288-…`)
  were still pending, not started, so step 2 went first (it needs neither, and the brief asks for it before the
  owners edit the drivers).
- **Step 2 done** (the other drivers). `examples/tools/beside_route.py` holds what every driver does the same way,
  and all five drivers (286 to 290, 289's included) run through it, each keeping its own entry, lemmas, models,
  observed initializers and verifier arguments: the pinned JARs; the mutant, built by the route's published-mutant
  recipe and ending the run when its JAR is not the one the newest mutant replay's receipt records; `accept.record`
  writing `evidence.json`; and `--max-array-length` or `--unwind` (now on every driver) marking the run a trial in
  the record and on its last line. *Finding*: 286's, 287's and 288's old drivers built their mutant another way
  (a fixed `--release`, no `-g`/`-parameters`, every entry recompressed), so their JAR was not the replay's bytes;
  the shared recipe, run offline on the pinned JARs, gives each of the five examples exactly the JAR its mutant
  replay ran (286 `48323d21…`, 287 `1d099295…`, 288 `5c72df16…`, 289 `a3a3dbff…`, 290 `4ee35d0b…`). Tests:
  `examples/tools/test_beside_route.py` (trial marking; every driver uses the module; on a made-up example with a
  real JAR, a mutant with no receipt or another hash ends the run, the replay's one is recorded as constructed, and
  a run leaves `evidence.json` marked a trial); `validate_example.py` 286 to 290 pass. Announced to the
  preservation and state inboxes (`--kind interface`).
- Repeated work measured (step 7): none for the owners yet.
- Inbox: `domain-advances-evidence-I001` (test_brief_run.py's watcher-inheriting test may hang or fail in a stream):
  noted; it did not come up in this cycle's `run --changed`, and I will neither change it nor block on it.
- Next: step 3, the reruns of 286 and 287 `mutant-security` with the new drivers (independent of step 1), then
  step 1 when its jobs are back.
- 2026-11-17, cycle 2. **Step 1, 289's half, done.** Job `20261117-122454-…-289-…` passed (1m33s, the same four
  verdicts); the watcher collected it on the default line (`pulrzyrl`), and this workspace took its result folder and
  `verification/.work-289/recorded` from there as they are (no merge). Each 289 task's `besideRoute.job` names it,
  and `accept.py 289` accepts all four **with no limit**, the `artifacts` check `ok` on each. *Finding, the check's*:
  its first run refused `mutant-security`, because the driver records the mutant's class path under the revision
  `mutant` (rightly: that is the class path it ran) and the check looked the base's JARs up under that revision,
  where target.json pins none. The check now looks a constructed mutant's JARs up under its base (its own JAR stays
  the `mutant` check's); `test_accept.py` has a control for it (fails without the fix), and its checkout test now
  holds 289 to the new job with no limit. The lemma job (`20261117-122546-…-286-and-288-…`) is still pending, not
  started.
- Repeated work measured (step 7): none for the owners; the state stream's 286 driver commit (`tvxyzwqv`) builds on
  the shared module, so nothing there was rebuilt by hand.
- Inbox: no open items.
- Next: step 3, the reruns of 286 and 287 `mutant-security` (and the other accepted answers of 286, 287, 290) as
  jobs with the new drivers; the lemma half of step 1 when its job is back.
- 2026-11-17, cycle 3. **Step 3 queued.** The lemma job is still pending, so the reruns went first, one job per
  example, each task at the frozen bound through its new driver into `verification/.work-NNN/recorded` (the earlier
  outputs stay as their results record them), every step run whatever the one before gave, `outcome.json` and
  `evidence.json` among the outputs: `20261117-133148-example-286-the-three-answers-beside-the` (vulnerable, fixed
  with its lemma, mutant), `20261117-133148-example-287-the-three-answers-beside-the` (the same three),
  `20261117-133148-example-288-fixed-security-again-with-th` (288's one verified task, recorded only if `accept.py`
  accepts it) and `20261117-133148-example-290-the-four-answers-beside-the` (the four, with the same observed
  initializers; their audit is step 5). Estimates from the earlier jobs' measured steps (286: 492 to 1015 s at 1.6
  GiB; 287: 659 to 823 s at 3.0 GiB; 288: 1182 s; 290: under 15 s each). The 286 and 288 runs prove the simpleMatch
  lemma under the tightened checks too, so they also answer what the lemma job asks, with the record. The other
  streams' changes to 286's and 287's drivers since step 2 add their own tasks only (no claim or target change), so
  a rerun from this line's drivers holds after the merge: `accept.py` reads the driver at the job's own commit.
- Repeated work measured (step 7): none; the state and preservation streams built 286's and 287's new tasks on the
  shared module rather than beside it.
- Inbox: `domain-advances-evidence-I002` (286's driver already has the three properties, state stream `tvxyzwqv`):
  taken; that driver is built on this stream's step 2 (`beside_route`), its security tasks run the same code as this
  line's, so 286's `mutant-security` is rerun with it as the item asks, and `ENTRIES` and the per-claim models stay in
  286's driver. `domain-advances-evidence-I003` (287's driver has them, preservation stream `oqsnoyom`): taken the
  same way; 287's equivalence branch is the preservation stream's and untouched, and the rerun of `mutant-security`
  uses the shared recipe (the replay's JAR, `1d099295…`).
- *Finding, the trace check's* (`sync.py check`): the preservation stream's session (`f28025bc`) merged this line's
  step 2 commit (`rkxyyqwn`) and stamped it with its own trace line, whose manifest only its line holds, so every
  commit here failed with "session f28025bc has no manifest". The check already made a note of a shared commit
  restamped elsewhere when the other workspace's manifest lists the log, but only for a session this tree knew; it
  now does the same for a session it has no manifest of, unless the commit's own tree held one (then a merge lost
  it, still an error). Two controls in `llm-dlc/tools/test_workspaces.py`.
- Next: step 4 (the vacuity control) while the step 3 jobs and the lemma job run; then the records and `accept.py`
  for 286, 287, 288 and 290, and the lemma half of step 1, when they are back.
- 2026-11-17, cycle 4. **Step 1 done.** The lemma job (`20261117-122546-…-286-and-288-…`) passed: under the tightened
  lemma checks the simpleMatch lemma is still proved by induction (286 in 74.2 s, 288 in 108.5 s) and each
  `fixed-security` verified with it (918 s, 1037.5 s); nothing was refused, so nothing goes to the challenge stream.
  Recorded in 286's and 288's notes. **Step 3, 290's part, done.** `20261117-133148-…-290-…` passed (45.9 s, the same
  four verdicts and path counts as the earlier job); each 290 task's `besideRoute.job` names it, and `accept.py 290`
  accepts all four with no limit, `artifacts` ok on each. Both result folders and their work folders came from the
  default line as they are (`jj restore` from `wwqnnzwp` and `swltxzml`, no merge). Still running: the 286, 287 and
  288 reruns.
- Repeated work measured (step 7): none; the lemma job and 290's rerun came in under their estimates (0.71 and 0.08
  of the duration), so nothing was resubmitted.
- Inbox: `domain-advances-evidence-I004` (make `an_observed_initializer_is_bound_to_what_it_was_observed_on` pass:
  refuse or carry the crossed, lowered and configured countermodels of `mqkqvvmw`): taken as step 5's work, which
  comes after step 4 by the brief's order; its audit of 290 (no other class's static written, the locale read only
  into a field the observation does not hold) goes into 290's notes with step 5.
- Next: step 4 (the vacuity control); the records and `accept.py` for 286, 287 and 288 when their jobs are back.
- 2026-11-17, cycle 5. **Step 4 done: the engine had the hole.** What the probe guarantees for a pair: 289's and 290's
  preservation go through `lib/src/pairing.rs`, where `RegressionPair.agree` returns true on an input inside the allowed
  change without calling either version, and the property check's probe asks only for an input of the assumption. So
  the probe's witness was inside the assumption, not known to be outside the change. The control, 289's preservation
  through its own driver with only `--unchanged-unless` replaced by `true` (a capped probe, 5 s): verified and
  *non-vacuous* before the fix. 290's recorded witness, `servlets=[]`, does lie inside its change. The fix (this stream's
  and the preservation stream's area): a verified pair with an allowed change is checked once more, `meantToChange`
  against `result` over the same assumption, domain and class path. A proof makes the statement vacuous; a witness, replayed
  as any is, becomes the statement's, with `stated.vacuity.outside` naming the change. The regression harness's own probe
  marks `outside` too, since its harness returns before the probe on an input in the scope. Now the `true` control is
  vacuous; 289 with its own change is non-vacuous with `servletPath=""` (0.3 s more), 290 with `servlets=[0]` (both capped
  probes, notes in each example). `accept.py` refuses an establishment of a task with an allowed change whose outcome does
  not say its witness lies outside that change (`unbound`), or names another change (`fail`). Controls:
  `lib/tests/pairing.rs` `a_pairs_proof_is_vacuous_when_the_allowed_change_covers_every_assumed_input` (fails without the
  fix: NonVacuous), three cases in `test_accept.py`. *Consequence*: 289's and 290's preservation answers are now refused
  (their outcomes predate `outside`), and so the Done-when's first row needs them rerun on a checker with this fix.
- Repeated work measured (step 7): the preservation stream's job `20261117-134306-…-289-and-290-preservation-again` (~10 min)
  will be refused as its outcomes are written, having run without this fix. One rerun of both after the merge answers
  both its change and this one.
- Inbox: `domain-advances-evidence-I005` (accept 289's and 290's preservation from job `20261117-134306`, and perhaps check
  that the pair has `thrown(t, ...)` and `fresh()`): taken in part. That job's outcomes say nothing of `outside`, so
  `accept.py` refuses them as this cycle's check stands, and they are not recorded as they are. The answer comes from one
  rerun of 289's and 290's preservation on a checker with both `zmvkptqz` and this fix, which needs the two lines merged
  (`zmvkptqz` is on neither this line nor the default one yet). The check on the pair's source waits until `zmvkptqz`
  is here, so that it is tested against what the generator writes. Sent to the preservation stream's inbox.
- Next: step 5 (observed initialization, with I004); the records and `accept.py` for 286, 287 and 288 when their jobs
  are back (still pending, not started); the rerun of 289's and 290's preservation once this line and `zmvkptqz` meet.
- 2026-11-17, cycle 6. **Step 3, 288's part, done.** `20261117-133148-…-288-…` passed (20m39s, 1.4 GiB, under its 25 min
  estimate): the simpleMatch lemma proved by induction (106.0 s), `fixed-security` verified (1130.9 s, 4678 paths), not
  vacuous. Its result folder and `verification/.work-288/recorded` came from the default line as they are (`jj restore`
  from `vyspnsorlxnr`). The task now has a `besideRoute` naming that job, and `accept.py 288` accepts it with no limit,
  every check ok (13), `artifacts` among them; 288's notes say so and its verdict label names this one answer, the other
  three still undecided at the frozen bound (VF-031). Step 3 still waits on 286's and 287's reruns (pending, not
  started) and on the 289/290 preservation rerun.
- Step 5 needs `mqkqvvmw` (the challenge stream's fixtures, `lib/tests/observed_countermodels.rs` and
  `ClassPath::refused`), which is on neither this line nor the default one: the next cycle merges it here first.
- Repeated work measured (step 7): none.
- Inbox: `domain-advances-evidence-I006` (say what the binding changes in `Slot`, `Object` and the observation's
  identity before changing `observed.rs`): answered here and by an item to `domain-advances-state`, before any change.
  `Slot` and `Object` do not change: the state stream adds held kinds as new `Object` variants (an empty
  `ConcurrentHashMap`, a bean class's property descriptors), and the binding never reads inside them. `Observed` gains
  one record of what it was observed on, written by the observer on its line as `"on": {...}`: the class file's sha256
  and the class path entry it came from; the class path, in order, with each entry's sha256; the classes initialized
  while it was observed, each with its class file's sha256; the JDK (`java.version`, `java.vendor`, `java.home`'s
  release); the default locale (all three categories); and the system properties read during the initialization, with
  the value each had (or none). Identity: an observation stays keyed by the class's internal name, and the check takes
  it only where the bytes it loads for that class are the bound ones; any mismatch or missing record ends the run by
  name. A held object the state stream observes for reflection binds to its class's bytes the same way, through the
  same record.
- Next: merge `mqkqvvmw` onto this line, then step 5 (the binding, I004's test, the countermodel); 286's and 287's
  records when their jobs are back; the 289/290 preservation rerun once this line and `zmvkptqz` meet.
- 2026-11-17, cycle 7. **Step 3, 286's part, done.** `20261117-133148-…-286-…` passed (36m01s, 1.4 GiB, under its 40 min
  estimate): each run proved the simpleMatch lemma by induction first (87.6 to 111.1 s); vulnerable-security refuted
  (414.6 s), fixed-security verified and not vacuous (1060.3 s), mutant-security refuted (373.6 s) on the JAR the mutant
  replay ran (`48323d21…`), both witnesses run on a JVM. Its result folder and `verification/.work-286/recorded` came
  from the default line as they are (`jj restore` from `qzwtllkx`, no merge). Each 286 task's `besideRoute` names that
  job, and `accept.py 286` accepts all three with no limit (12, 13 and 13 checks ok); 286's notes say so. Step 3 still
  waits on 287's rerun (`20261117-133148-…-287-…`, pending, not started) and the 289/290 preservation rerun.
- Repeated work measured (step 7): none.
- Inbox: no open items.
- Next: merge `mqkqvvmw` onto this line, then step 5 (the binding, I004's test, the countermodel); 287's records when
  its job is back; the 289/290 preservation rerun once this line and `zmvkptqz` meet.
- 2026-11-17, cycle 8. **`mqkqvvmw` merged** (`tswurxzv`, with `yypzyxmw` under it). **Step 5, the binding, done.**
  The observer (`lib/src/observed/ObservedInitializer.java`) now says what it observed on, as I006 agreed: `Slot` and
  `Object` unchanged, `Observed` gains `on` (`On`): the class file's sha256 and location, the class path in order, the
  JDK's vendor and home, the default locale (default, formatting, display), the system properties the class path's
  code read with their values (the JDK's reads of its own configuration, as it opens a JAR, are not the
  initializer's: the first probe listed a dozen, `java.home`'s path among them), and each class of the class path
  the initialization also initialized (from `-Xlog:class+init`), with its sha256 and static state. `observe` ends the
  run where it is not bound: a line with no `on`; another class path; a class file the tool reads otherwise or not at
  all; a class also initialized whose class file differs or whose state differs from its state initialized alone in
  a JVM of its own (the countermodel `A.<clinit> { B.x = 1; k = 7; }`: refused, "its field x was 1 after it and is 0
  alone"); a default locale of `tr`, `az` or `lt`, which the check takes the JVM's not to be. The locale and the
  properties are stated in what the result rests on. I004's test, `an_observed_initializer_is_bound_to_what_it_was_observed_on`,
  is in `lib/tests/observed_countermodels.rs` and passes (crossed and lowered refused, configured stated as
  `oc.value = "xyz"`), with four unit tests in `observed.rs`. 290 still binds: capped probes of fixed-security and
  preservation with the new checker verified both again with the same path counts (659, 573); ClassUtils's and
  UrlPathHelper's initializations initialize nine classes of the class path between them, each the same alone.
  290's notes record the audit and the binding; VF-033 has its audit half done and says the restated claim is left.
  Not covered, and stated: a field the observation holds nothing of in a class also initialized, and a write of the
  value a field already had.
- Repeated work measured (step 7): none.
- Inbox: no open items.
- Next: 287's records and `accept.py 287` (its job `20261117-133148-…-287-…` is back, collected on the default line
  while this cycle ran); step 5's last piece, 290's restated preservation claim (option B), prepared with its freeze
  recorded as the user's; then step 6 (VF-030); the 289/290 preservation rerun once this line and `zmvkptqz` meet.
- 2026-11-17, cycle 9. **Step 3, 287's part, done.** `20261117-133148-…-287-…` passed (44m48s, 3.0 GiB, against its 45 min
  estimate): vulnerable-security refuted (948.5 s) and mutant-security refuted (966.9 s), both at a candidate of 25
  characters and 73 UTF-8 bytes against a valid `$2a$04$` hash, where `matches` returns false instead of throwing, each
  run on a JVM, the mutant's JAR the replay's (`1d099295…`); fixed-security verified and not vacuous (746.0 s). Its
  result folder and `verification/.work-287/recorded` came from the default line as they are (`jj restore` from
  `lwoqsztz`, no merge). Each 287 task's `besideRoute` names that job, and `accept.py 287` accepts all three with no limit
  (12, 13 and 13 checks); 287's notes say so. With 286, 288 and 290 done, step 3 waits only on the rerun of 289's and
  290's preservation, which needs `zmvkptqz` (still on neither this line nor the default one).
- Repeated work measured (step 7): none; the job's estimate was right (0.996 of it).
- Inbox: no open items.
- Next: step 5's last piece, 290's restated preservation claim (option B), prepared with its freeze recorded as the
  user's; then step 6 (VF-030); the 289/290 preservation rerun once this line and `zmvkptqz` meet.
- 2026-11-17, cycle 10. **Step 5 done as far as it is mine: 290's restated preservation claim is prepared, its freeze the
  user's.** `claims/lone-dispatcher-matchers-preserved.json` (sha256 `4185eea3…`) keeps the old claim's table, assumption,
  allowed change, observations and bound and compares what the matchers are: the same exact classes in the same order, each
  with the same pattern, HTTP method and servlet path, for both overloads, or the same exception category. Its entry is a
  new adapter class, `MatcherDescriptionAdapter#describe`, one line per matcher: its exact class, then the library's own
  `toString()` with its length (an `MvcRequestMatcher`'s pattern and method are private, so the rendering is the only way
  to read them). `MatcherSelectionAdapter` is unchanged, since the frozen claims and the accepted answers name it. On a
  JVM, both releases on 168 probes: all 28 with the DispatcherServlet alone agree, 132 of the rest differ where the fix
  changes the selection by design. The claim states that a null pattern and `"null"` render alike, which the same probes
  show. Two capped probes through the driver in a scratch copy, with the task pointed at the new claim:
  - at bound 1, a trial, the checker stops at its first gap, `StringBuilder.append(Object)` in `MvcRequestMatcher.toString`
    (the HTTP method), unverifiable;
  - at the frozen bound 8 it reached the 4 GiB cap after 133 s.

  So the proof needs that gap closed in the checker (an enum constant appended), and then one job. The freeze is recorded as
  the user's in VF-033 and in 290's notes: the hash in a claims ledger, the task's `claim` pointed at the file, and the
  adapter source added to `preparation.adapters`. `proofs/prove.py` picks `describe` by the task's claim (`ENTRIES`).
  `accept.py`'s task check now compares the adapter sources listed at the job's commit, the ones it compiled. A source
  listed since is reported, not refused, so the freeze leaves 290's three security answers accepted. The control
  (`test_accept.py`) fails on the old check.
- Repeated work measured (step 7): none.
- Inbox: no open items.
- Next: step 6 (VF-030: the Python proof tier as a job, the Rust proof tier for the tests the foundation's checker
  changes touched, and why the estimate counts 0 Python proof tests); the 289/290 preservation rerun once this line and
  `zmvkptqz` meet.
- 2026-11-17, cycle 11. **Step 6: the Python half is settled and the Rust half is queued.**
  - *Why the estimate counts 0 Python proof tests*: there are none. No Python test is tagged `@cost("proof")`, now or at
    VF-030's own job (`8594e6b7adb1`). The tag appears only in the tier tools and the lint's fixtures, so
    `run --tier proof --only python` runs nothing and was not queued; the brief's step 6 assumed otherwise.
  - Every Python test is in the default run. I ran it inline at this line's head and it passed (tree `bc1caa8a8827`,
    54 of 54), after the foundation's checker changes and this line's.
  - The Rust proof tier, for the own checker's changes since the last proof-tier jobs (the foundation's `qkqpsmqk`, this
    line's pair and observation checks), is job `20261117-152112-the-rust-proof-tier-after-the-domain-adv`. It runs the
    whole tier with `--no-fail-fast`, including VF-018's three (closed; they run the own checker) and the seven tests
    `wvvtwkos` moved; ~55 min.
  - VF-030 is updated: it closes when that job passes.
- Repeated work measured (step 7): none.
- Inbox: `domain-advances-evidence-I007` (seven controls in which `accept.py` accepts an answer the evidence does not
  give: `entry` by substring, `step` by any word ending in the driver's path, `domain` not holding the witness to
  `nullable`, the assumption or the claim's bound, `expressions` with no allowed change). Taken as the next cycle's work,
  since it is this stream's own check and none of the 13 accepted answers rests on these holes (per the item's audit).
- Next: I007 (the controls from `zwrpkwnl`'s README into `test_accept.py`, and `accept.py` refusing or leaving each
  unbound); VF-030 when its job is back; the 289/290 preservation rerun once this line and `zmvkptqz` meet.
- 2026-11-17, cycle 12. **I007 done: the seven controls are in `test_accept.py` (`Countermodels`) and `accept.py` refuses
  or leaves each unbound.** The holes it closes, by check:
  - `entry`: whole `Class#method` names, the invocation's entry or the one an assumption names as the "adapter entry"
    (286's and 287's route), never a part of one or a method an assumption mentions otherwise;
  - `step`: exactly `python3 [-I] <folder>/proofs/prove.py TASK`; and `artifacts` holds `evidence.json`'s driver hash to
    the driver at the job's source commit;
  - `domain`: the claim's bound alone, a task's `bounds` no longer lowering it; a witness's null input must be of a
    parameter the claim makes nullable;
  - `replay`: where the claim assumes something, a refutation needs a record that the assumption held on its witness.
    The record is the harness source the job collected (`work/harness/PropertyHarness.java`). Its `check` returns
    first wherever the outcome's assumption does not hold, so the JVM's failure of that harness is on an assumed input.
    Without that source as the job wrote it the answer is unbound. Every claim of 286 to 290 has an `assume`, and all
    eight refutations' harnesses gate on it exactly;
  - `expressions`: a task with no allowed change is refused when the generated pair has `meantToChange` or the outcome
    says it ran with one.

  Each control fails on the old check: 8 tests, 11 failures with subtests, the README's 10 and the driver hash. Beside
  each is the evidence of the same kind that is still accepted. `accept.py 286` to `290` still accepts the same 13
  answers with no limit; 289's and 290's preservation are still refused for `outside`. `test_accept.py` 38 tests and
  `run --changed` 7 of 7 pass.
- Repeated work measured (step 7): `llm-dlc/tools/test_brief_run.py` (I001) failed once in `run --changed` and passed
  on its second run, about 49 s.
- Inbox: no open items. `domain-advances-evidence-I007` was acknowledged in cycle 11 and is done here.
- Next:
  - VF-030, when job `20261117-152112-the-rust-proof-tier-after-the-domain-adv` is back (pending, not started).
  - The 289/290 preservation rerun, once this line and `zmvkptqz` meet (still on neither line).
  - 290's restated claim waits on the user's freeze.

  Nothing else needs only me.
  Then blocked: the 289/290 preservation rerun needs `zmvkptqz` merged onto this line, and 290's restated claim
  needs the user's freeze.
- Status: waiting on jobs 20261117-152112-the-rust-proof-tier-after-the-domain-adv

## Loop settings

- session: 7ece8184-b148-4351-92d8-d634606b823e
- model: claude-opus-5-5
- effort: high
- workspace: domain-advances-evidence

## Loop until

Steps 1 to 6 in order, 7 whenever it comes up. Stop with `waiting on jobs ID ...` when what is left waits on jobs,
`done` when the criteria are met or recorded as the brief allows, `blocked: ...` when the next step is the user's.
Keep the last line of Progress a status.
