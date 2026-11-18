# Countermodels of the acceptance check

The challenge stream of `domain-advances` (2026-11-17), item 7. `examples/tools/accept.py` lets a job's collected
outcome stand in for a proof task's answer given beside the route. Each control below is evidence that `accept.py` on
the evidence stream's line (`krptozvm`, the same file since `ymzlyksq`) accepts for an answer the evidence does not give.
Each is a test written against `test_accept.py`'s own made-up checkout (`Checkout`, `beside`, `rewrite`). Each fails
there today because the answer is accepted: 7 tests, 10 failures with the subtests.

| Control | What `accept.py` takes as the same | Where | The answer it accepts |
|---|---|---|---|
| An outcome about another method whose name the entry contains | `entry in named`: the outcome's target is a *substring* of the invocation's entry or of any assumption's text | `entry` | `GateAdapter#allowed`, `adapter.GateAdapter#allowedTwice` (another package) and `GateAdapter#allowed` each stand for `fixture.adapter.GateAdapter#allowedTwice` |
| An outcome about a method an assumption mentions | the same test, on a claim's assumption that names `fixture.RegexGate#field` as how the input is read | `entry` | a refutation of `RegexGate#field` for the task on `RegexGate#allowed` |
| A step that ran a driver at another path | any word that ends in `proofs/prove.py` and contains the example's folder | `step` | `python3 /elsewhere/examples/900-…/proofs/prove.py`, a driver of another checkout, reported in `identity.driver` as the source commit's; and `echo examples/900-…/proofs/prove.py …`, no driver run at all |
| A witness null where the claim says not null | the domain check compares the outcome's *stated* nullable parameters with the claim's, never the witness's values | `domain` | a refutation by `allowed(field=null)` of a claim with no nullable parameter |
| A witness the claim's assumption excludes | nothing holds the witness to the assumption; a replay that reproduced the assertion's failure says nothing of the assumption | `domain` or `replay` | a refutation by `allowed(field="ab")` of a claim assuming `field.length() == 3` |
| A pair run with an allowed change the task does not allow | for a task with no `allowedChange` the expressions check says "the task allows no change" without reading the pair or the outcome's text | `expressions` | `preservation` established everywhere from a pair that skipped `code == 97`, where the versions differ |
| A task bound below the claim's | `want` is the claim's bound overridden by the task's `bounds` | `domain` | a proof at 2 established for a claim of bound 8, the trial-bound control by another route |

The brief's four suggestions map onto these:
- *An outcome from another claim with the same expressions*: the first two. The expressions are compared, but the entry they are about is matched as a substring.
- *A job whose step ran a different driver at the same path*: the third.
- *A witness inside the bound but outside the assumption*: the fourth and fifth.
- *A pair's vacuity witness inside the allowed change*: guarded where the task has a change, since `vacuity.outside` must be the task's change, and the checker sets it only from the check of `meantToChange` (`pairing::compared`, `ymzlyksq`). It is open where the task has none, which is the sixth.

## Tried and found guarded

- **An allowed change that is a prefix of the one the pair ran** (task `code == 9`, pair `code == 97`). The
  expressions check passes, since it tests `allowed in text`, a substring. But `non-vacuous` refuses it: the outcome's
  `vacuity.outside` is the change the pair ran, which is not the task's. An outcome from before `outside` existed
  is unbound there.
- **An outcome of another task of the same claim** (the mutant's for `fixed-security`). The step is chosen by the
  task's id, and the outcome is read from `WORK/TASK/outcome.json`, so only a driver that wrote another revision's
  outcome under this task's name gets one through. Then, where the driver records `evidence.json`, `artifacts`
  holds the revisions it recorded to the task's.
- **A proof at a larger unwinding than the claim's** (307 states `unwind: 513`). `complete` asks the outcome to say
  its unwinding is complete, which is what the claim's unwinding is for.

## Fix options, for the evidence stream

- `entry`: match whole names. Take the `Class#method` tokens of the entry and the assumptions
  (`[\w.$]+#[\w$]+`) and require the outcome's target to equal one, or better the one the claim names as "the
  adapter entry". 286's and 287's tasks have no invocation entry and pass today only through an assumption's text
  (`the parameters are those of the adapter entry example287.adapter.PasswordMatchAdapter#matches(...)`), so a
  token match must keep that route.
- `step`: require the program to be `python3` (or `python3 -I`), and the driver word to be exactly
  `{folder}/proofs/prove.py`, relative to the job's checkout. Where the driver records `evidence.json`, compare
  its `driver.sha256` with the driver at the source commit, which the identity already reads.
- `domain`: hold each null value among the witness's inputs to the claim's `nullable`. For the assumption, ask
  the outcome or its replay to record that the assumption held on the witness, and leave the answer unbound
  where it does not. `accept.py` cannot evaluate Java, so it can only refuse what no record shows.
- `expressions`: for an equivalence task with no allowed change, require the generated pair to have no
  `meantToChange` and the outcome's text not to say "meant to affect".
- `domain`: take the claim's bound alone, or refuse a task bound below it.

## The controls

To be added to `examples/tools/test_accept.py`, or beside it, with the fix:

```python
#!/usr/bin/env python3
"""Controls of accept.py: evidence it accepts for an answer the evidence does not give. Each test fails while the
check accepts it."""
from __future__ import annotations

import hashlib
import json
import unittest

from test_accept import Checkout, rewrite, sha


def task_of(t: dict, task_id: str) -> dict:
    return next(x for x in t["tasks"] if x["id"] == task_id)


class Controls(Checkout):
    def test_an_outcome_about_another_method_whose_name_the_entry_contains_is_refused(self):
        """The entry check asks whether the outcome's target is a substring of the invocation's entry or of an
        assumption's text, so an outcome about `GateAdapter#allowed` stands in for one about
        `GateAdapter#allowedTwice`, the entry the task names: the same expressions over other code."""
        paths = self.beside("regex-probe", "refuted")
        self.edit("target.json", lambda t: task_of(t, "regex-probe").update(invocation={
            "how": "adapter", "checked": "2026-01-02", "evidence": "made up",
            "entry": "fixture.adapter.GateAdapter#allowedTwice(Ljava/lang/String;)Z, made up"}))
        rewrite(self.root, paths, lambda o: o.update(target="fixture.adapter.GateAdapter#allowedTwice"))
        self.assertTrue(self.check("regex-probe")["accepted"], "the entry the task names")
        for other in ("fixture.adapter.GateAdapter#allowed", "adapter.GateAdapter#allowedTwice", "GateAdapter#allowed"):
            with self.subTest(other=other):
                rewrite(self.root, paths, lambda o: o.update(target=other))
                self.refused("regex-probe", "entry", other)

    def test_an_outcome_about_a_method_an_assumption_mentions_is_refused(self):
        """A method the claim's assumptions name in passing (how the input is built) is not the entry."""
        paths = self.beside("regex-probe", "refuted")
        self.edit("claims/regex-probe.json", lambda c: c.update(assumptions=[
            {"text": "the field is read by fixture.RegexGate#field from the request, made up"}]))
        self.beside("regex-probe", "refuted")  # the ledger freezes the edited claim
        rewrite(self.root, paths, lambda o: o.update(target="fixture.RegexGate#field"))
        self.refused("regex-probe", "entry", "fixture.RegexGate#field")

    def test_a_step_that_ran_a_driver_at_another_path_is_refused(self):
        """The step check takes any word that ends in proofs/prove.py and contains the example's folder: a driver of
        another checkout, which the identity then names as this commit's, or no driver run at all."""
        for run in ("python3 /elsewhere/examples/900-made-up-change/proofs/prove.py fixed-security --timeout 60 --work verification/.work-900",
                    "echo examples/900-made-up-change/proofs/prove.py fixed-security --work verification/.work-900"):
            with self.subTest(run=run):
                paths = self.beside("fixed-security", "established")
                spec = json.loads((self.root / paths["job"]).read_text())
                result = json.loads((self.root / paths["result"]).read_text())
                spec["steps"][0]["run"] = result["steps"][0]["run"] = run
                (self.root / paths["job"]).write_text(json.dumps(spec))
                result["job"]["sha256"] = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
                (self.root / paths["result"]).write_text(json.dumps(result))
                self.refused("fixed-security", "step", "prove.py")

    def test_a_refutation_whose_witness_is_null_where_the_claim_says_not_null_is_refused(self):
        """The domain check holds the witness to the claim's bound but not to its nullable parameters: a witness
        with field null refutes a claim over non-null fields only, which it lies outside."""
        paths = self.beside("regex-probe", "refuted")
        rewrite(self.root, paths, lambda o: o.update(counterexample={"input": "allowed(field=null)", "inputs": [
            {"name": "field", "type": "java.lang.String", "value": None}]}))
        self.refused("regex-probe", "domain", "null")

    def test_a_refutation_whose_witness_the_claims_assumption_excludes_is_refused_or_left_unbound(self):
        """Nothing holds the witness to the claim's assumption: a replay that reproduced the assertion's failure says
        nothing of whether the input was assumed. A witness of length 2 refutes a claim about length 3 only."""
        self.edit("claims/regex-probe.json", lambda c: c.update(assume="field.length() == 3"))
        paths = self.beside("regex-probe", "refuted")
        r = self.check("regex-probe")
        self.assertFalse(r["accepted"], "witness allowed(field=\"ab\") is outside `field.length() == 3`, and no record says it is inside")

    def test_a_pair_run_with_an_allowed_change_the_task_does_not_allow_is_refused(self):
        """The expressions check asks nothing of the pair when the task allows no change, so a pair that ran with
        `code == 97` establishes `preservation` everywhere, where the versions differ at 97."""
        paths = self.beside("preservation", "established")
        self.edit("target.json", lambda t: task_of(t, "preservation").pop("allowedChange"))
        self.assertIn("meant to affect (`code == 97`", json.loads((self.root / paths["outcome"]).read_text())["output"])
        self.refused("preservation", "expressions", "code == 97")

    def test_a_task_bound_below_the_claims_does_not_establish_the_claim(self):
        """`want` is the claim's bound overridden by the task's, so a task that lowers it to 2 makes a proof at 2
        the claim's bound of 8: the trial-bound control by another route."""
        self.bound("fixed-security", 8)
        self.edit("target.json", lambda t: task_of(t, "fixed-security").update(bounds={"maxArrayLength": 2}))
        self.beside("fixed-security", "established")
        self.refused("fixed-security", "domain", "8")


if __name__ == "__main__":
    unittest.main()
```

## Audit

Which accepted answers rest on these holes. It was read on the evidence line at `krptozvm` from its collected
outcomes, on 2026-11-17. `accept.py` there accepts 13 answers, each with no limit, when it is given the source commits:
- 286's and 287's `vulnerable-security`, `fixed-security` and `mutant-security`;
- 288's `fixed-security`;
- 289's and 290's `vulnerable-security`, `fixed-security` and `mutant-security`.

It refuses 289's and 290's `preservation`, because their outcomes do not say where their witnesses lie.
- *Entry.* Every outcome is about the entry its claim or task names:
  - 288, 289 and 290 have the full `Class#method` of the invocation's entry.
  - 286 and 287 have no invocation entry. Their outcomes' targets, `example286.adapter.BinderDecisionAdapter#allowed`
    and `example287.adapter.PasswordMatchAdapter#matches`, are named whole in the claim's first assumption.
  - Not affected, but they pass only by the substring route, so a fix has to keep them.
- *Step.* Every step runs `python3 examples/NNN-…/proofs/prove.py`, relative to the job's checkout, and each
  `evidence.json` records the driver whose hash is the source commit's. Not affected.
- *Witness.* Every null input of an accepted refutation is of a parameter the claim makes nullable: 289's `query`
  and 286's `allowedPatterns`. Each witness was reproduced on a JVM by the checker's harness, which assumes the
  claim's `assume`. Not affected, though no record says the assumption held.
- *Allowed change.* Every equivalence task of the run has an `allowedChange`: 288, 289 and 290. Not affected.
- *Task bounds.* No task of the run has `bounds`. Not affected.

Nothing for the watcher.

## Past the fix (`kqxwrwrx`)

The evidence stream's fix for these seven (`domain-advances-evidence-I007`) holds. The seven controls above, run
against `accept.py` at `kqxwrwrx`, all pass. The same commit's `test_accept.py` passes its 38 tests.

What the fix leaves is in the step check. `driver_steps` reads a step's words up to the task's name and the first
`--work`. The pipeline runs the whole step with `bash -c` (`verification/pipeline.py`, `WRAPPER`). Everything else
in the job, and everything after those words, is unread. Four controls, 7 failures with the subtests, each accepted
at `kqxwrwrx` with no limit:

| Control | What the step check does not read | The answer it accepts |
|---|---|---|
| A step that goes on past the driver in the shell | what follows the task's name: `; cp verification/forged.json W/fixed-security/outcome.json`, `&& sed -i s/violation/verified/ …` | the forged outcome. evidence.json does not hash the outcome, so nothing ties it to the driver's run |
| A step before the driver that replaces it | the job's other steps: `cp /elsewhere/prove.py examples/…/proofs/prove.py`, or `cp -r verification/forged/. W` | whatever the replaced driver or the copied folder leaves. The driver hash in evidence.json is written by the driver that ran, which can name the source commit's |
| `--work` given twice | the step check takes the first `--work`; the driver's argparse keeps the last, and `--work=DIR` is not read as one at all | an outcome under a folder the driver step did not write |
| `--jvmcontract PATH` | every driver takes it. The pipeline puts the build of the source commit's `lib/` first on `PATH`, which is the default | an outcome from another binary (another workspace's build, a stand-in script). evidence.json records its sha256, which nothing compares, and the identity still names the job's lib tree |

**Fix options**, for the evidence stream:
- Refuse a step that is not exactly `python3 [-I] <folder>/proofs/prove.py TASK` followed by known flags:
  - `--timeout N`, `--work DIR` once, and the trial flags;
  - no shell operator (`shlex.shlex(..., punctuation_chars=True)` sees `;`, `&&`, `|`, `>`);
  - no `--jvmcontract` and no `--jars`. The driver checks the JARs' hashes, so `--jars` only costs a fallback.
- Refuse a job any of whose steps before the chosen one is not such a run.
- Or have the driver hash the outcome into evidence.json and record the binary's hash, and have the pipeline
  record the hash of the binary it built (`result.jvmcontract`), so that the two can be compared.

Every step of the 13 accepted answers' jobs is such a run, so either fix keeps them.

The controls, beside `test_accept.py` (they reuse `DriverRecord.recorded`, so its own tests run again under this
class):

```python
#!/usr/bin/env python3
"""Controls of accept.py's step check past kqxwrwrx: a job's step that ran the example's driver, and did something
else besides, or ran it on something else. Each test fails while the check accepts it."""
from __future__ import annotations

import hashlib
import json
import unittest

from test_accept import AsCommitted, DriverRecord

DRIVER = "examples/900-made-up-change/proofs/prove.py"
WORK = "verification/.work-900"


class StepControls(DriverRecord):
    def steps(self, paths: dict, runs: list[str]) -> None:
        """The job's steps are RUNS, each passed, the last one's log the step's log; the result records the job as
        the runner read it."""
        spec = json.loads((self.root / paths["job"]).read_text())
        result = json.loads((self.root / paths["result"]).read_text())
        log = result["steps"][0]["log"]
        spec["steps"] = [{"name": f"step {i}", "run": run} for i, run in enumerate(runs, 1)]
        result["steps"] = [{"index": i, "status": "passed", "run": run, "log": log} for i, run in enumerate(runs, 1)]
        (self.root / paths["job"]).write_text(json.dumps(spec))
        result["job"]["sha256"] = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
        (self.root / paths["result"]).write_text(json.dumps(result))

    def accepted_as_it_is(self) -> AsCommitted:
        paths = self.recorded()
        committed = AsCommitted(self.root)
        r = self.check("fixed-security", committed)
        self.assertTrue(r["accepted"], r.get("why"))
        self.assertEqual(r["limits"], [], "the evidence an honest job leaves")
        self.paths = paths
        return committed

    def test_a_step_that_goes_on_past_the_driver_in_the_shell_is_refused(self):
        """The pipeline runs a step with `bash -c`, and the step check reads its words only up to the task's name:
        what follows a `;` or a `&&` runs after the driver and can write the outcome it collected. The outcome is then
        not the driver's, and no record says so (evidence.json does not hash the outcome)."""
        committed = self.accepted_as_it_is()
        for after in (f" ; cp verification/forged.json {WORK}/fixed-security/outcome.json",
                      f" && sed -i s/violation/verified/ {WORK}/fixed-security/outcome.json"):
            with self.subTest(after=after):
                self.steps(self.paths, [f"python3 {DRIVER} fixed-security --timeout 60 --work {WORK}{after}"])
                r = self.check("fixed-security", committed)
                self.assertFalse(r["accepted"], f"the outcome is whatever{after} left")

    def test_a_step_before_the_driver_that_replaces_it_is_refused(self):
        """A job's earlier step can replace the driver in the job's checkout (a `git archive` of the source commit)
        before the step that runs it. The driver that runs then writes evidence.json, and can name in it the source
        commit's driver hash, which is all the artifacts check compares: accepted with no limit. Or an earlier step
        writes the outcome folder itself."""
        committed = self.accepted_as_it_is()
        driver = f"python3 {DRIVER} fixed-security --timeout 60 --work {WORK}"
        for first in (f"cp /elsewhere/prove.py {DRIVER}", f"cp -r verification/forged/. {WORK}"):
            with self.subTest(first=first):
                self.steps(self.paths, [first, driver])
                r = self.check("fixed-security", committed)
                self.assertFalse(r["accepted"], f"step 1, `{first}`, decides what the driver step leaves")

    def test_the_outcome_read_is_the_one_the_driver_wrote_where_work_is_given_twice(self):
        """The step check takes the first `--work`; the driver's argparse keeps the last (and `--work=DIR` is not
        read as one at all). The outcome read is then one the step did not write."""
        committed = self.accepted_as_it_is()
        for twice in (f"--work {WORK} --work verification/.work-elsewhere", f"--work {WORK} --work=verification/.work-elsewhere"):
            with self.subTest(twice=twice):
                self.steps(self.paths, [f"python3 {DRIVER} fixed-security --timeout 60 {twice}"])
                r = self.check("fixed-security", committed)
                self.assertFalse(r["accepted"], f"the driver wrote verification/.work-elsewhere, and {WORK} is read")

    def test_a_step_that_runs_the_driver_on_another_checker_binary_is_refused(self):
        """Every driver takes `--jvmcontract PATH`. The pipeline builds the checker from lib/ at the job's source
        commit and puts it first on PATH, which is the driver's default; a step that names another binary (another
        workspace's build, a stand-in script) gets an outcome from it. evidence.json records its sha256, which nothing
        compares, and the result's identity still names the job's lib tree."""
        committed = self.accepted_as_it_is()
        self.steps(self.paths, [f"python3 {DRIVER} fixed-security --jvmcontract /elsewhere/lib/target/release/jvmcontract "
                                f"--timeout 60 --work {WORK}"])
        r = self.check("fixed-security", committed)
        self.assertFalse(r["accepted"], "the outcome is another binary's, and the identity says the job's lib tree")


if __name__ == "__main__":
    unittest.main()
```

### Tried past the fix, and guarded

- **A witness on which the assumption throws** (a nullable parameter that an assume dereferences unguarded). The JVM
  replay counts only an `AssertionError` from `check` as reproduced (`jvm_witness::Check::Refuted`). A gate that
  throws is `Threw`, which `property.rs` reports as unverifiable. None of 286 to 290's assumes dereferences a nullable
  parameter unguarded.
- **The gate's record**. `PropertyHarness.java` is the checker's rendering "for readers" (`harness::property_source`).
  The JVM runs the generated class file. Both come from the same assume text, so the record is the checker's word,
  not the class file's. Over objects (`property_source_over`) the objects are made before the gate, so `gates_on`
  finds no gate first and leaves the answer unbound, which is conservative.
- **A null witness input**. The checker writes a null as JSON `null` (`witness.rs`), which the null check reads.
  Not tried: a null component (`p.c`, `this.c`). The claims' `nullable` names parameters, so whether a component may
  be null is a question for the claim language, not for this check.
- **Entry tokens**. Each of the 13 tasks' invocation entries names one `Class#method`, so a second token cannot occur
  there. The adapter-entry route reads "adapter entry X#m" anywhere in an assumption, including a negated sentence.
  No claim has one.

### Audit, past the fix

Every step of the jobs behind the 13 accepted answers is a plain driver run:
- `python3 <folder>/proofs/prove.py TASK --timeout N --work verification/.work-NNN/recorded`;
- one `--work` each, no `--jvmcontract`, no shell operator;
- each job's other steps are driver runs of its other tasks.

No accepted answer rests on these holes, so there is nothing for the watcher.

## Past the step check's fix (`wxpoysws`)

The four controls above are the evidence stream's own `StepsPastTheFix` tests at `wxpoysws`, and they pass there. One
residue, guarded today by other checks:

- *An absolute `--work`*. "No later step writes the same outcome folder" compares each step's `--work` word after
  `posixpath.normpath`. The pipeline runs every step in `<state>/work/<job id>`, which is known when the job file is
  written. So a later plain driver run with `--work <state>/work/<job id>/out` writes the chosen step's outcome folder
  `out/TASK`, and the check does not see it.
- What such a step can write there, with the flags a step may give:
  - a run of the same task at another bound;
  - a run of another example's task of the same name (`fixed-security` is a task of 287 to 290).
- The domain check refuses the first, since an established outcome below the claim's `maxArrayLength` fails, and
  every claim of 286 to 290 and 307 states one. The entry check refuses the second.
- Not guarded, for a claim with no bound: `domain` says OK when "the claim states no bound on lengths, and the step
  overrides none", from the chosen step's flags, without reading the outcome's own bound.
- The fix: compare the folders resolved against the work root, or refuse an absolute `--work`.
