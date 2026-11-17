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
